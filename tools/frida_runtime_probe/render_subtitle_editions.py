#!/usr/bin/env python3
"""Create native-resolution subtitle editions from verified audible base videos."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path

try:
    from .composition_contract import presentation_sample_count
    from .output_path_contract import (
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )
    from .subtitle_edition_contract import (
        AUDIO_PROFILES,
        LEGACY_AUDIO_PROFILE,
        SUPPORTED_EDITIONS,
        build_edition_plan,
        load_font_config,
    )
except ImportError:  # direct script execution
    from composition_contract import presentation_sample_count  # type: ignore
    from output_path_contract import (  # type: ignore
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )
    from subtitle_edition_contract import (  # type: ignore
        AUDIO_PROFILES,
        LEGACY_AUDIO_PROFILE,
        SUPPORTED_EDITIONS,
        build_edition_plan,
        load_font_config,
    )


SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
BASE_MASTER_SCHEMA = "magireco-audio-base-master-render-v1"
BASE_MASTER_READY_SCHEMA = "magireco-audio-base-master-transaction-ready-v1"
BASE_MASTER_READY_PUBLICATION_RULE = (
    "both profile videos and both base-master sidecars are non-publishable "
    "unless this marker exists with this SHA-256"
)
VIDEO_TIMELINE_SCHEMA = "magireco-video-presentation-timeline-v1"
SUBTITLE_BATCH_READY_SCHEMA = "magireco-subtitle-edition-batch-ready-v1"
SUBTITLE_BATCH_READY_FILENAME = "SUBTITLE_EDITIONS_READY.json"
SUBTITLE_BATCH_PUBLICATION_RULE = (
    "no event edition is publishable unless the complete staged batch has a "
    "passed source rehash and this final READY marker"
)
SOURCE_SNAPSHOT_SCHEMA = "magireco-subtitle-render-source-snapshot-v1"
SRT_TIMING_RE = re.compile(
    r"^(?P<sh>\d{2,}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})"
    r" --> "
    r"(?P<eh>\d{2,}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument(
        "--base-video-dir",
        help="legacy unclassified-audio base directory",
    )
    parser.add_argument("--with-bgm-base-video-dir")
    parser.add_argument("--no-bgm-base-video-dir")
    parser.add_argument("--out-root", required=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="explicitly replace an existing complete subtitle batch",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--only", nargs="*")
    parser.add_argument(
        "--edition",
        action="append",
        choices=SUPPORTED_EDITIONS,
        dest="editions",
        help="repeat to request none/ja/zh; verified default is the full three variants",
    )
    parser.add_argument("--font-config")
    parser.add_argument(
        "--expected-event-index",
        help=(
            "publication batch index JSON binding the exact event order and "
            "source manifest SHA-256; mandatory outside --dry-run/legacy mode"
        ),
    )
    parser.add_argument(
        "--audio-profile",
        action="append",
        choices=AUDIO_PROFILES,
        dest="audio_profiles",
        help="repeat to select verified with_bgm/no_bgm masters",
    )
    parser.add_argument(
        "--legacy-two-edition",
        action="store_true",
        help="explicitly use --base-video-dir and old unclassified none+ja output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate tracks, shared timing, font source/hash/coverage without rendering",
    )
    return parser.parse_args()


def srt_time(milliseconds: int) -> str:
    value = max(milliseconds, 0)
    hours, value = divmod(value, 3_600_000)
    minutes, value = divmod(value, 60_000)
    seconds, millis = divmod(value, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def link_or_copy(source: Path, target: Path) -> str:
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,profile,level,width,height,r_frame_rate,"
            "pix_fmt,time_base,bit_rate,sample_rate,channels,channel_layout,"
            "avg_frame_rate,duration,start_time,nb_frames,nb_read_frames:"
            "format=duration,start_time",
            "-count_frames",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def _positive_fraction(value: object, *, label: str) -> Fraction:
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise RuntimeError(f"{label} is not a valid rational: {value!r}") from error
    if result <= 0:
        raise RuntimeError(f"{label} must be positive: {value!r}")
    return result


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _nearest_positive_integer(value: Fraction) -> int:
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def validate_video_timeline_payload(
    payload: dict,
    *,
    expected_duration_ms: int,
    expected_frame_rate: str,
    label: str,
) -> dict[str, object]:
    """Validate ffprobe frame and packet timestamps, then hash their CFR timeline.

    Stream-level ``r_frame_rate``/``nb_frames`` metadata is not sufficient: a VFR
    file can advertise 30 fps while containing a missing, duplicated, or shifted
    presentation timestamp.  This gate therefore audits every decoded frame and
    every encoded packet using exact rational arithmetic.
    """

    if expected_duration_ms <= 0:
        raise RuntimeError(f"{label} expected duration must be positive")
    expected_rate = _positive_fraction(
        expected_frame_rate, label=f"{label} expected frame rate"
    )
    if expected_rate != Fraction(30, 1):
        raise RuntimeError(
            f"{label} verified presentation rate {expected_frame_rate!r} != 30/1"
        )
    streams = payload.get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise RuntimeError(f"{label} timeline probe must return exactly one stream")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise RuntimeError(f"{label} timeline probe stream is malformed")
    time_base = _positive_fraction(
        stream.get("time_base"), label=f"{label} stream time_base"
    )
    for field in ("r_frame_rate", "avg_frame_rate"):
        actual_rate = _positive_fraction(
            stream.get(field), label=f"{label} stream {field}"
        )
        if actual_rate != expected_rate:
            raise RuntimeError(
                f"{label} stream {field} {_fraction_text(actual_rate)} != "
                f"{_fraction_text(expected_rate)}"
            )

    combined = payload.get("packets_and_frames")
    if isinstance(combined, list):
        frames = [row for row in combined if row.get("type") == "frame"]
        packets = [row for row in combined if row.get("type") == "packet"]
    else:
        frames = payload.get("frames")
        packets = payload.get("packets")
    if not isinstance(frames, list) or not frames:
        raise RuntimeError(f"{label} timeline probe returned no decoded frames")
    if not isinstance(packets, list) or not packets:
        raise RuntimeError(f"{label} timeline probe returned no encoded packets")

    def timestamp(row: object, field: str, kind: str, index: int) -> Fraction:
        if not isinstance(row, dict) or row.get(field) in (None, "", "N/A"):
            raise RuntimeError(
                f"{label} {kind} {index} lacks integer {field} timestamp"
            )
        try:
            tick = int(row[field])
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                f"{label} {kind} {index} has invalid {field} timestamp"
            ) from error
        return tick * time_base

    frame_pts = [
        timestamp(row, "best_effort_timestamp", "frame", index)
        for index, row in enumerate(frames)
    ]
    frame_duration = Fraction(1, 1) / expected_rate
    if abs(frame_pts[0]) > frame_duration:
        raise RuntimeError(
            f"{label} first presentation timestamp {_fraction_text(frame_pts[0])} "
            "is more than one frame from zero"
        )
    for index, (previous, current) in enumerate(
        zip(frame_pts, frame_pts[1:]), start=1
    ):
        delta = current - previous
        if delta <= 0:
            raise RuntimeError(
                f"{label} presentation timestamps are not strictly monotonic "
                f"at frame {index}"
            )
        if delta != frame_duration:
            raise RuntimeError(
                f"{label} VFR/discontinuous presentation timeline at frame "
                f"{index}: delta {_fraction_text(delta)} != "
                f"{_fraction_text(frame_duration)}"
            )

    frame_count = len(frame_pts)
    expected_frame_count = _nearest_positive_integer(
        Fraction(expected_duration_ms, 1000) * expected_rate
    )
    if frame_count != expected_frame_count:
        raise RuntimeError(
            f"{label} decoded frame count {frame_count} != expected "
            f"{expected_frame_count}"
        )
    presentation_duration = frame_pts[-1] - frame_pts[0] + frame_duration
    expected_duration = Fraction(expected_duration_ms, 1000)
    if abs(presentation_duration - expected_duration) > frame_duration:
        raise RuntimeError(
            f"{label} presentation duration "
            f"{_fraction_text(presentation_duration)} differs from expected "
            f"{_fraction_text(expected_duration)} by more than one frame"
        )

    for field in ("nb_frames", "nb_read_frames"):
        value = stream.get(field)
        if value not in (None, "", "N/A"):
            try:
                metadata_count = int(value)
            except (TypeError, ValueError) as error:
                raise RuntimeError(f"{label} stream {field} is invalid") from error
            if metadata_count != frame_count:
                raise RuntimeError(
                    f"{label} stream {field} {metadata_count} != audited "
                    f"frame count {frame_count}"
                )
    stream_duration_text = stream.get("duration")
    if stream_duration_text not in (None, "", "N/A"):
        stream_duration = _positive_fraction(
            stream_duration_text, label=f"{label} stream duration"
        )
        if abs(stream_duration - expected_duration) > frame_duration:
            raise RuntimeError(
                f"{label} stream duration {_fraction_text(stream_duration)} "
                f"differs from expected {_fraction_text(expected_duration)} "
                "by more than one frame"
            )

    packet_rows: list[tuple[Fraction, Fraction, Fraction]] = []
    for index, row in enumerate(packets):
        pts = timestamp(row, "pts", "packet", index)
        dts = timestamp(row, "dts", "packet", index)
        duration = timestamp(row, "duration", "packet", index)
        if duration != frame_duration:
            raise RuntimeError(
                f"{label} packet {index} duration {_fraction_text(duration)} != "
                f"one 30 fps frame {_fraction_text(frame_duration)}"
            )
        packet_rows.append((pts, dts, duration))
    if len(packet_rows) != frame_count:
        raise RuntimeError(
            f"{label} encoded packet count {len(packet_rows)} != decoded frame "
            f"count {frame_count}"
        )
    for index, (previous, current) in enumerate(
        zip(packet_rows, packet_rows[1:]), start=1
    ):
        dts_delta = current[1] - previous[1]
        if dts_delta != frame_duration:
            raise RuntimeError(
                f"{label} packet decode timeline is discontinuous at packet "
                f"{index}: delta {_fraction_text(dts_delta)}"
            )
    packet_rows_by_pts = sorted(packet_rows, key=lambda row: row[0])
    packet_pts = [row[0] for row in packet_rows_by_pts]
    if packet_pts != frame_pts:
        raise RuntimeError(
            f"{label} packet presentation timestamps do not match decoded frames"
        )

    canonical_timeline = {
        "schema": VIDEO_TIMELINE_SCHEMA,
        "frame_rate": _fraction_text(expected_rate),
        "frame_pts": [_fraction_text(value) for value in frame_pts],
        "packet_pts_in_presentation_order": [
            _fraction_text(value) for value in packet_pts
        ],
        "packet_durations_in_presentation_order": [
            _fraction_text(row[2]) for row in packet_rows_by_pts
        ],
    }
    timeline_sha256 = canonical_sha256(canonical_timeline)
    return {
        "schema": VIDEO_TIMELINE_SCHEMA,
        "status": "passed",
        "timeline_sha256": timeline_sha256,
        "frame_rate": _fraction_text(expected_rate),
        "stream_time_base": _fraction_text(time_base),
        "frame_count": frame_count,
        "expected_frame_count": expected_frame_count,
        "packet_count": len(packet_rows),
        "first_pts": _fraction_text(frame_pts[0]),
        "last_pts": _fraction_text(frame_pts[-1]),
        "presentation_duration": _fraction_text(presentation_duration),
        "expected_duration_ms": expected_duration_ms,
    }


def probe_video_timeline(
    path: Path,
    ffprobe: str,
    *,
    expected_duration_ms: int,
    expected_frame_rate: str,
    label: str,
) -> dict[str, object]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_packets",
            "-show_frames",
            "-show_entries",
            "stream=index,time_base,r_frame_rate,avg_frame_rate,duration,"
            "nb_frames,nb_read_frames:frame=best_effort_timestamp:"
            "packet=pts,dts,duration",
            "-count_frames",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} ffprobe timeline output is invalid JSON") from error
    return validate_video_timeline_payload(
        payload,
        expected_duration_ms=expected_duration_ms,
        expected_frame_rate=expected_frame_rate,
        label=label,
    )


def audio_hash(path: Path, ffmpeg: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip().split("=", 1)[-1].upper()


def decoded_pcm_hash(path: Path, ffmpeg: str) -> str:
    """Hash decoded 48 kHz stereo PCM, catching same-PCM re-encodes."""

    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip().split("=", 1)[-1].upper()


def video_packet_hash(path: Path, ffmpeg: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip().split("=", 1)[-1].upper()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest().upper()


def event_contract_projection_sha256(event_manifest_path: Path) -> str:
    """Hash the event contract while excluding cyclic base-sidecar pointers."""

    payload = json.loads(event_manifest_path.read_text(encoding="utf-8"))
    projection = copy.deepcopy(payload)
    profiles = projection.get("audio_master_contract", {}).get("profiles", {})
    if isinstance(profiles, dict):
        for profile in profiles.values():
            if isinstance(profile, dict):
                profile.pop("base_master_manifest", None)
    return canonical_sha256(projection)


def video_encoding_signature(stream: dict) -> tuple[object, ...]:
    return (
        str(stream.get("codec_name", "")),
        str(stream.get("profile", "")),
        str(stream.get("level", "")),
        int(stream.get("width", 0)),
        int(stream.get("height", 0)),
        str(stream.get("pix_fmt", "")),
        str(stream.get("r_frame_rate", "")),
    )


def audio_encoding_signature(stream: dict) -> tuple[str, ...]:
    return tuple(
        str(stream.get(key, ""))
        for key in (
            "codec_name",
            "sample_rate",
            "channels",
            "channel_layout",
            "time_base",
        )
    )


def x264_profile_argument(profile: object) -> str:
    normalized = str(profile).strip().casefold().replace(" ", "")
    aliases = {
        "baseline": "baseline",
        "constrainedbaseline": "baseline",
        "main": "main",
        "high": "high",
        "high10": "high10",
    }
    if normalized not in aliases:
        raise RuntimeError(f"unsupported native H.264 profile: {profile!r}")
    return aliases[normalized]


def x264_level_argument(level: object) -> str:
    try:
        numeric = int(level)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"invalid native H.264 level: {level!r}") from error
    if numeric <= 0:
        raise RuntimeError(f"invalid native H.264 level: {level!r}")
    return f"{numeric // 10}.{numeric % 10}"


def _required_sha256(value: object, *, field: str) -> str:
    normalized = str(value or "").strip().upper()
    if not SHA256_RE.fullmatch(normalized):
        raise RuntimeError(f"{field} must be a full SHA-256")
    return normalized


def _probe_duration_ms(payload: dict, *, label: str) -> int:
    try:
        seconds = float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"{label} lacks a valid container duration") from error
    if not (seconds > 0):
        raise RuntimeError(f"{label} has a non-positive duration")
    return round(seconds * 1000)


def validate_stream_coverage(
    stream: dict, *, expected_duration_ms: int, label: str
) -> None:
    try:
        start_ms = round(float(stream["start_time"]) * 1000)
        duration_ms = round(float(stream["duration"]) * 1000)
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"{label} lacks start_time/duration") from error
    if abs(start_ms) > 34:
        raise RuntimeError(f"{label} starts at {start_ms} ms instead of zero")
    if abs(duration_ms - expected_duration_ms) > 67:
        raise RuntimeError(
            f"{label} duration {duration_ms} ms != {expected_duration_ms} ms"
        )


def validate_native_audio_signature(stream: dict, *, label: str) -> None:
    actual = (
        str(stream.get("codec_name", "")),
        str(stream.get("sample_rate", "")),
        int(stream.get("channels", 0)),
        str(stream.get("channel_layout", "")),
    )
    expected = ("aac", "48000", 2, "stereo")
    if actual != expected:
        raise RuntimeError(f"{label} audio signature {actual} != {expected}")


def _resolve_transaction_path(
    value: object, *, relative_to: Path, field: str
) -> Path:
    path_text = str(value or "").strip()
    if not path_text:
        raise RuntimeError(f"{field} is missing")
    path = Path(path_text)
    if not path.is_absolute():
        path = relative_to / path
    return path.resolve()


def _read_json_bytes(path: Path, *, label: str) -> tuple[bytes, dict]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON root must be an object")
    return raw, payload


def validate_transaction_ready_marker(
    *,
    event: str,
    profile: str,
    base_path: Path,
    base_manifest_path: Path,
    base_manifest: dict,
    expected_event_contract_sha256: str,
) -> dict:
    """Require the final marker for the complete two-profile audio transaction.

    The v1 transaction deliberately avoids a hash cycle: the marker binds both
    final video paths/hashes and both sidecar paths, while each sidecar embeds
    the marker hash.  This consumer therefore verifies both directions and
    refuses a partial promotion where either sidecar, either video, or the
    marker is missing or inconsistent.
    """

    if profile not in AUDIO_PROFILES:
        raise RuntimeError(f"unsupported transaction audio profile: {profile}")
    reference = base_manifest.get("transaction_ready_marker")
    if not isinstance(reference, dict):
        raise RuntimeError(
            f"{event} {profile} lacks a transaction_ready_marker"
        )
    locator = str(reference.get("locator", "")).strip()
    if not locator:
        raise RuntimeError(
            f"{event} {profile} transaction_ready_marker needs a locator"
        )
    ready_path = _resolve_transaction_path(
        reference.get("path"),
        relative_to=base_manifest_path.parent,
        field=f"{event} {profile} transaction_ready_marker path",
    )
    if not ready_path.is_file():
        raise FileNotFoundError(ready_path)
    expected_ready_sha256 = _required_sha256(
        reference.get("sha256"),
        field=f"{event} {profile} transaction ready marker sha256",
    )
    ready_bytes, ready_payload = _read_json_bytes(
        ready_path, label=f"{event} audio transaction ready marker"
    )
    actual_ready_sha256 = hashlib.sha256(ready_bytes).hexdigest().upper()
    if actual_ready_sha256 != expected_ready_sha256:
        raise RuntimeError(
            f"{event} {profile} transaction ready marker SHA-256 mismatch"
        )

    expected_event_contract_sha256 = _required_sha256(
        expected_event_contract_sha256,
        field=f"{event} source event contract sha256",
    )
    marker_checks = {
        "schema": BASE_MASTER_READY_SCHEMA,
        "status": "ready",
        "publishable": True,
        "event": event,
        "source_event_contract_sha256": expected_event_contract_sha256,
        "publication_rule": BASE_MASTER_READY_PUBLICATION_RULE,
    }
    for field, expected in marker_checks.items():
        actual = ready_payload.get(field)
        if field.endswith("sha256"):
            actual = str(actual or "").upper()
        if actual != expected:
            raise RuntimeError(
                f"{event} transaction ready marker {field} mismatch: "
                f"actual={actual!r}, expected={expected!r}"
            )

    marker_profiles = ready_payload.get("profiles")
    if not isinstance(marker_profiles, dict) or set(marker_profiles) != set(
        AUDIO_PROFILES
    ):
        raise RuntimeError(
            f"{event} transaction ready marker must contain exactly "
            f"{list(AUDIO_PROFILES)}"
        )

    resolved_current_manifest = base_manifest_path.resolve()
    resolved_current_video = base_path.resolve()
    transaction_video_paths: set[Path] = set()
    transaction_manifest_paths: set[Path] = set()
    for sibling_profile in AUDIO_PROFILES:
        row = marker_profiles.get(sibling_profile)
        if not isinstance(row, dict) or set(row) != {
            "video",
            "video_sha256",
            "base_master_manifest",
            "audio_timeline_sha256",
        }:
            raise RuntimeError(
                f"{event} transaction ready marker {sibling_profile} row is "
                "incomplete"
            )
        sibling_video = _resolve_transaction_path(
            row.get("video"),
            relative_to=ready_path.parent,
            field=f"{event} {sibling_profile} ready video",
        )
        sibling_manifest_path = _resolve_transaction_path(
            row.get("base_master_manifest"),
            relative_to=ready_path.parent,
            field=f"{event} {sibling_profile} ready base manifest",
        )
        transaction_video_paths.add(sibling_video)
        transaction_manifest_paths.add(sibling_manifest_path)
        if not sibling_video.is_file():
            raise FileNotFoundError(sibling_video)
        if not sibling_manifest_path.is_file():
            raise FileNotFoundError(sibling_manifest_path)
        expected_video_sha256 = _required_sha256(
            row.get("video_sha256"),
            field=f"{event} {sibling_profile} ready video sha256",
        )
        if file_sha256(sibling_video) != expected_video_sha256:
            raise RuntimeError(
                f"{event} {sibling_profile} transaction video SHA-256 mismatch"
            )
        marker_audio_timeline_sha256 = _required_sha256(
            row.get("audio_timeline_sha256"),
            field=f"{event} {sibling_profile} ready audio timeline sha256",
        )

        if sibling_manifest_path == resolved_current_manifest:
            sibling_manifest = base_manifest
        else:
            _, sibling_manifest = _read_json_bytes(
                sibling_manifest_path,
                label=f"{event} {sibling_profile} transaction sidecar",
            )
        sibling_checks = {
            "schema": BASE_MASTER_SCHEMA,
            "status": "passed",
            "publishable": True,
            "event": event,
            "audio_profile": sibling_profile,
            "source_event_contract_sha256": expected_event_contract_sha256,
            "audio_timeline_sha256": marker_audio_timeline_sha256,
            "output_sha256": expected_video_sha256,
        }
        for field, expected in sibling_checks.items():
            actual = sibling_manifest.get(field)
            if field.endswith("sha256"):
                actual = str(actual or "").upper()
            if actual != expected:
                raise RuntimeError(
                    f"{event} {sibling_profile} transaction sidecar {field} "
                    f"mismatch: actual={actual!r}, expected={expected!r}"
                )
        sibling_output = _resolve_transaction_path(
            sibling_manifest.get("output"),
            relative_to=sibling_manifest_path.parent,
            field=f"{event} {sibling_profile} transaction sidecar output",
        )
        if sibling_output != sibling_video:
            raise RuntimeError(
                f"{event} {sibling_profile} transaction sidecar output path "
                "does not match the ready marker"
            )
        sibling_ready_reference = sibling_manifest.get(
            "transaction_ready_marker"
        )
        if not isinstance(sibling_ready_reference, dict):
            raise RuntimeError(
                f"{event} {sibling_profile} transaction sidecar lacks the "
                "ready marker reference"
            )
        sibling_ready_path = _resolve_transaction_path(
            sibling_ready_reference.get("path"),
            relative_to=sibling_manifest_path.parent,
            field=f"{event} {sibling_profile} sidecar ready marker path",
        )
        sibling_ready_sha256 = _required_sha256(
            sibling_ready_reference.get("sha256"),
            field=f"{event} {sibling_profile} sidecar ready marker sha256",
        )
        sibling_ready_locator = str(
            sibling_ready_reference.get("locator", "")
        ).strip()
        if (
            sibling_ready_path != ready_path
            or sibling_ready_sha256 != actual_ready_sha256
            or sibling_ready_locator != locator
        ):
            raise RuntimeError(
                f"{event} {sibling_profile} transaction sidecar ready marker "
                "reference is inconsistent"
            )

        if sibling_profile == profile:
            if sibling_manifest_path != resolved_current_manifest:
                raise RuntimeError(
                    f"{event} {profile} ready marker points to a different "
                    "base master manifest"
                )
            if sibling_video != resolved_current_video:
                raise RuntimeError(
                    f"{event} {profile} ready marker points to a different "
                    "base video"
                )

    if len(transaction_video_paths) != len(AUDIO_PROFILES) or len(
        transaction_manifest_paths
    ) != len(AUDIO_PROFILES):
        raise RuntimeError(
            f"{event} transaction ready marker does not identify two distinct "
            "profile videos and sidecars"
        )

    return {
        "path": str(ready_path),
        "sha256": actual_ready_sha256,
        "locator": locator,
        "marker": ready_payload,
    }


def validate_base_master_manifest(
    *,
    event: str,
    profile: str,
    base_path: Path,
    profile_contract: dict,
    event_manifest_path: Path,
    base_probe: dict,
    audio_packet_sha256: str,
    decoded_pcm_sha256: str,
    video_packet_sha256: str,
    video_timeline_sha256: str,
) -> dict:
    """Bind a named MP4 to the audited layer timeline that created it."""

    reference = profile_contract.get("base_master_manifest")
    if not isinstance(reference, dict):
        raise RuntimeError(
            f"{event} {profile} lacks an evidence-bound base_master_manifest"
        )
    path_text = str(reference.get("path", "")).strip()
    locator = str(reference.get("locator", "")).strip()
    if not path_text or not locator:
        raise RuntimeError(
            f"{event} {profile} base_master_manifest needs path and locator"
        )
    reference_path = Path(path_text)
    if not reference_path.is_absolute():
        reference_path = event_manifest_path.parent / reference_path
    reference_path = reference_path.resolve()
    if not reference_path.is_file():
        raise FileNotFoundError(reference_path)
    expected_reference_sha256 = _required_sha256(
        reference.get("sha256"), field=f"{event} {profile} base manifest sha256"
    )
    actual_reference_sha256 = file_sha256(reference_path)
    if expected_reference_sha256 != actual_reference_sha256:
        raise RuntimeError(
            f"{event} {profile} base manifest SHA-256 mismatch"
        )
    try:
        payload = json.loads(reference_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"{event} {profile} base master manifest is not valid JSON"
        ) from error
    event_manifest = json.loads(event_manifest_path.read_text(encoding="utf-8"))
    expected_duration_ms = int(event_manifest["render_duration_ms"])
    expected_presentation_samples = presentation_sample_count(event_manifest)
    actual_duration_ms = _probe_duration_ms(
        base_probe, label=f"{event} {profile} base"
    )
    if abs(actual_duration_ms - expected_duration_ms) > 67:
        raise RuntimeError(
            f"{event} {profile} base duration {actual_duration_ms} ms != "
            f"event duration {expected_duration_ms} ms"
        )
    expected_event_contract_sha256 = event_contract_projection_sha256(
        event_manifest_path
    )
    checks = {
        "schema": BASE_MASTER_SCHEMA,
        "status": "passed",
        "publishable": True,
        "event": event,
        "audio_profile": profile,
        "source_event_contract_sha256": expected_event_contract_sha256,
        "voice_se_timeline_sha256": str(
            profile_contract.get("voice_se_timeline_sha256", "")
        ),
        "audio_timeline_sha256": str(
            profile_contract.get("audio_timeline_sha256", "")
        ),
        "output": str(base_path.resolve()),
        "output_sha256": file_sha256(base_path),
        "output_audio_packet_sha256": audio_packet_sha256,
        "output_decoded_pcm_sha256": decoded_pcm_sha256,
        "output_video_packet_sha256": video_packet_sha256,
        "output_video_timeline_sha256": video_timeline_sha256,
        "duration_ms": actual_duration_ms,
        "presentation_sample_count": expected_presentation_samples,
        "audio_encoding_signature": list(
            audio_encoding_signature(
                next(
                    stream
                    for stream in base_probe["streams"]
                    if stream.get("codec_type") == "audio"
                )
            )
        ),
        "video_encoding_signature": list(
            video_encoding_signature(
                next(
                    stream
                    for stream in base_probe["streams"]
                    if stream.get("codec_type") == "video"
                )
            )
        ),
    }
    for field, expected in checks.items():
        actual = payload.get(field)
        if field.endswith("sha256"):
            actual = str(actual or "").upper()
            expected = str(expected).upper()
        if actual != expected:
            raise RuntimeError(
                f"{event} {profile} base master {field} mismatch: "
                f"actual={actual!r}, expected={expected!r}"
            )
    source_layers = payload.get("source_layers")
    if not isinstance(source_layers, dict) or set(source_layers) != {
        "voice_se",
        "bgm_layers",
    }:
        raise RuntimeError(
            f"{event} {profile} base master source_layers are incomplete"
        )
    if canonical_sha256(source_layers) != str(
        profile_contract.get("audio_timeline_sha256", "")
    ).upper():
        raise RuntimeError(
            f"{event} {profile} base master source_layers do not match the "
            "audited audio timeline"
        )
    qa = payload.get("qa")
    if not isinstance(qa, dict) or qa.get("status") != "passed" or qa.get(
        "errors"
    ) not in ([], None):
        raise RuntimeError(f"{event} {profile} base master QA is not passed")
    ready_marker = validate_transaction_ready_marker(
        event=event,
        profile=profile,
        base_path=base_path,
        base_manifest_path=reference_path,
        base_manifest=payload,
        expected_event_contract_sha256=expected_event_contract_sha256,
    )
    return {
        "path": str(reference_path),
        "sha256": actual_reference_sha256,
        "locator": locator,
        "manifest": payload,
        "transaction_ready_marker": ready_marker,
    }


def validate_audio_master_distinction(
    audio_packet_sha256_by_profile: dict[str, str],
    decoded_pcm_sha256_by_profile: dict[str, str],
) -> None:
    if set(audio_packet_sha256_by_profile) != set(AUDIO_PROFILES):
        return
    if len(set(audio_packet_sha256_by_profile.values())) != 2:
        raise RuntimeError(
            "verified with_bgm/no_bgm masters have identical audio packet hashes"
        )
    if len(set(decoded_pcm_sha256_by_profile.values())) != 2:
        raise RuntimeError(
            "verified with_bgm/no_bgm masters decode to identical PCM"
        )


def validate_video_identity_across_audio_masters(
    *,
    event: str,
    profiles: list[str],
    editions: list[str],
    source_packet_sha256_by_profile: dict[str, str],
    source_timeline_sha256_by_profile: dict[str, str],
    packet_sha256_by_profile_and_edition: dict[str, dict[str, str]],
    timeline_sha256_by_profile_and_edition: dict[str, dict[str, str]],
) -> None:
    """Require both encoded identity and presentation identity across masters."""

    expected_profiles = set(profiles)
    mappings = {
        "source packet": source_packet_sha256_by_profile,
        "source timeline": source_timeline_sha256_by_profile,
        "edition packet": packet_sha256_by_profile_and_edition,
        "edition timeline": timeline_sha256_by_profile_and_edition,
    }
    for label, mapping in mappings.items():
        if set(mapping) != expected_profiles:
            raise RuntimeError(
                f"{event} {label} identity does not cover every audio master"
            )
    if len(set(source_packet_sha256_by_profile.values())) != 1:
        raise RuntimeError(
            f"{event} audio masters do not share the same encoded video stream"
        )
    if len(set(source_timeline_sha256_by_profile.values())) != 1:
        raise RuntimeError(
            f"{event} audio masters do not share the same video presentation timeline"
        )
    for edition in editions:
        try:
            packet_hashes = {
                packet_sha256_by_profile_and_edition[profile][edition]
                for profile in profiles
            }
            timeline_hashes = {
                timeline_sha256_by_profile_and_edition[profile][edition]
                for profile in profiles
            }
        except KeyError as error:
            raise RuntimeError(
                f"{event} {edition} video identity is incomplete"
            ) from error
        if len(packet_hashes) != 1:
            raise RuntimeError(
                f"{event} {edition} video packets differ between audio masters"
            )
        if len(timeline_hashes) != 1:
            raise RuntimeError(
                f"{event} {edition} video timelines differ between audio masters"
            )


def write_srt(path: Path, cues: list[dict[str, object]]) -> None:
    lines: list[str] = []
    for index, row in enumerate(cues, 1):
        lines.extend(
            [
                str(index),
                f"{srt_time(int(row['start_ms']))} --> "
                f"{srt_time(int(row['end_ms']))}",
                str(row["text"]),
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _srt_timestamp_ms(match: re.Match[str], prefix: str) -> int:
    hours = int(match.group(f"{prefix}h"))
    minutes = int(match.group(f"{prefix}m"))
    seconds = int(match.group(f"{prefix}s"))
    milliseconds = int(match.group(f"{prefix}ms"))
    if minutes >= 60 or seconds >= 60:
        raise RuntimeError("SRT timestamp minute/second is outside 00..59")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def read_srt_strict(path: Path) -> list[dict[str, object]]:
    """Read the exact SRT grammar emitted by :func:`write_srt`.

    This intentionally does not use a forgiving subtitle parser.  A player may
    silently recover from a missing index, malformed separator, or shifted cue;
    the publication gate must instead authenticate the materialized file that
    FFmpeg actually consumes.
    """

    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f"SRT is not readable UTF-8: {path}") from error
    if value == "":
        return []
    if value.startswith("\ufeff"):
        raise RuntimeError(f"SRT has an unexpected UTF-8 BOM: {path}")
    # Path.read_text() normalizes native CRLF.  A remaining carriage return is
    # therefore embedded data and not output generated by write_srt().
    if "\r" in value:
        raise RuntimeError(f"SRT contains an embedded carriage return: {path}")
    if not value.endswith("\n"):
        raise RuntimeError(f"SRT does not end at a cue boundary: {path}")

    result: list[dict[str, object]] = []
    for expected_index, block in enumerate(value[:-1].split("\n\n"), 1):
        lines = block.split("\n")
        if len(lines) < 3:
            raise RuntimeError(
                f"SRT cue {expected_index} is incomplete in {path}"
            )
        if lines[0] != str(expected_index):
            raise RuntimeError(
                f"SRT cue index {lines[0]!r} != {expected_index} in {path}"
            )
        timing = SRT_TIMING_RE.fullmatch(lines[1])
        if timing is None:
            raise RuntimeError(
                f"SRT cue {expected_index} has malformed timing in {path}"
            )
        text = "\n".join(lines[2:])
        if not text.strip():
            raise RuntimeError(f"SRT cue {expected_index} has blank text in {path}")
        result.append(
            {
                "cue_index": expected_index - 1,
                "start_ms": _srt_timestamp_ms(timing, "s"),
                "end_ms": _srt_timestamp_ms(timing, "e"),
                "text": text,
            }
        )
    return result


def _cue_projection(cues: object, *, label: str) -> list[dict[str, object]]:
    if not isinstance(cues, list):
        raise RuntimeError(f"{label} cues must be a list")
    projection: list[dict[str, object]] = []
    for index, row in enumerate(cues):
        if not isinstance(row, dict):
            raise RuntimeError(f"{label} cue {index} must be an object")
        try:
            projection.append(
                {
                    "cue_index": index,
                    "start_ms": int(row["start_ms"]),
                    "end_ms": int(row["end_ms"]),
                    "text": str(row["text"]),
                }
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(f"{label} cue {index} is incomplete") from error
    return projection


def validate_srt_against_edition_plan(
    path: Path,
    cues: object,
    *,
    event: str,
    language: str,
) -> dict[str, object]:
    """Strictly round-trip every cue written for an edition plan."""

    expected = _cue_projection(cues, label=f"{event} {language} edition plan")
    actual = read_srt_strict(path)
    if len(actual) != len(expected):
        raise RuntimeError(
            f"{event} {language} SRT cue count {len(actual)} != edition plan "
            f"{len(expected)}"
        )
    for index, (actual_cue, expected_cue) in enumerate(zip(actual, expected)):
        for field in ("cue_index", "start_ms", "end_ms", "text"):
            if actual_cue[field] != expected_cue[field]:
                raise RuntimeError(
                    f"{event} {language} SRT cue {index} {field} mismatch: "
                    f"actual={actual_cue[field]!r}, "
                    f"expected={expected_cue[field]!r}"
                )
    return {
        "status": "passed",
        "cue_count": len(actual),
        "cue_projection_sha256": canonical_sha256(actual),
        "srt_sha256": file_sha256(path),
    }


def load_expected_event_index(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "magireco-edition-batch-index-v1":
        raise ValueError("unexpected edition batch index schema")
    raw_events = payload.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("edition batch index events must be non-empty")
    events = []
    seen = set()
    for index, row in enumerate(raw_events):
        if not isinstance(row, dict):
            raise ValueError(f"edition batch index row {index} is not an object")
        event = str(row.get("event", "")).strip()
        manifest_sha256 = _required_sha256(
            row.get("manifest_sha256"),
            field=f"edition batch index row {index} manifest_sha256",
        )
        if not event or event in seen:
            raise ValueError(f"edition batch index has blank/duplicate event {event!r}")
        seen.add(event)
        events.append({"event": event, "manifest_sha256": manifest_sha256})
    return {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "locator": str(payload.get("locator", "")).strip(),
        "events": events,
    }


def capture_render_source_snapshot(
    planned: list[tuple[Path, dict[str, object]]],
    base_video_dirs: dict[str, Path],
    *,
    expected_event_index: dict[str, object] | None = None,
) -> dict[str, object]:
    """Hash every immutable input before or after a complete render batch."""

    paths: dict[Path, set[str]] = {}

    def add(path: Path, role: str) -> None:
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        paths.setdefault(resolved, set()).add(role)

    if expected_event_index is not None:
        add(
            Path(str(expected_event_index["path"])),
            "expected_event_index",
        )

    for manifest_path, plan in planned:
        event_manifest = manifest_path.resolve()
        try:
            event = str(json.loads(event_manifest.read_text(encoding="utf-8"))["event"])
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError) as error:
            raise RuntimeError(
                f"source manifest is not valid event JSON: {event_manifest}"
            ) from error
        add(event_manifest, f"{event}:source_manifest")

        requested_profiles = plan.get("requested_audio_profiles")
        if not isinstance(requested_profiles, list):
            raise RuntimeError(f"{event} edition plan lacks audio profiles")
        for profile_value in requested_profiles:
            profile = str(profile_value)
            try:
                base_path = base_video_dirs[profile] / f"{event}.mp4"
            except KeyError as error:
                raise RuntimeError(
                    f"{event} has no base directory for {profile}"
                ) from error
            add(base_path, f"{event}:{profile}:base_video")

        tracks = plan.get("tracks")
        if not isinstance(tracks, dict):
            raise RuntimeError(f"{event} edition plan lacks tracks")
        for language, track in tracks.items():
            if not isinstance(track, dict):
                raise RuntimeError(f"{event} {language} track is malformed")
            cues = track.get("cues")
            if isinstance(cues, list) and cues:
                font = track.get("font")
                if not isinstance(font, dict):
                    raise RuntimeError(
                        f"{event} {language} track has cues without a font"
                    )
                add(
                    Path(str(font.get("path", ""))),
                    f"{event}:{language}:font",
                )

        audio_contract = plan.get("audio_master_contract")
        if not isinstance(audio_contract, dict):
            continue
        contract_profiles = audio_contract.get("profiles")
        if not isinstance(contract_profiles, dict):
            raise RuntimeError(f"{event} audio master profiles are malformed")
        for profile_value in requested_profiles:
            profile = str(profile_value)
            contract = contract_profiles.get(profile)
            if not isinstance(contract, dict):
                raise RuntimeError(f"{event} lacks {profile} audio contract")
            sidecar_reference = contract.get("base_master_manifest")
            if not isinstance(sidecar_reference, dict):
                raise RuntimeError(
                    f"{event} {profile} lacks a base master sidecar reference"
                )
            sidecar_path = _resolve_transaction_path(
                sidecar_reference.get("path"),
                relative_to=event_manifest.parent,
                field=f"{event} {profile} base master sidecar",
            )
            add(sidecar_path, f"{event}:{profile}:base_master_sidecar")
            _, sidecar = _read_json_bytes(
                sidecar_path,
                label=f"{event} {profile} base master sidecar",
            )
            ready_reference = sidecar.get("transaction_ready_marker")
            if not isinstance(ready_reference, dict):
                raise RuntimeError(
                    f"{event} {profile} sidecar lacks transaction READY"
                )
            ready_path = _resolve_transaction_path(
                ready_reference.get("path"),
                relative_to=sidecar_path.parent,
                field=f"{event} {profile} transaction READY",
            )
            add(ready_path, f"{event}:audio_transaction_READY")
            _, ready = _read_json_bytes(
                ready_path,
                label=f"{event} audio transaction READY",
            )
            marker_profiles = ready.get("profiles")
            if not isinstance(marker_profiles, dict):
                raise RuntimeError(
                    f"{event} audio transaction READY lacks profiles"
                )
            # Bind every path named by READY, not only the paths selected by the
            # current plan.  This catches a sibling sidecar/video replacement.
            for sibling_profile, row in marker_profiles.items():
                if not isinstance(row, dict):
                    raise RuntimeError(
                        f"{event} READY profile {sibling_profile} is malformed"
                    )
                add(
                    _resolve_transaction_path(
                        row.get("video"),
                        relative_to=ready_path.parent,
                        field=f"{event} {sibling_profile} READY video",
                    ),
                    f"{event}:{sibling_profile}:READY_video",
                )
                add(
                    _resolve_transaction_path(
                        row.get("base_master_manifest"),
                        relative_to=ready_path.parent,
                        field=f"{event} {sibling_profile} READY sidecar",
                    ),
                    f"{event}:{sibling_profile}:READY_sidecar",
                )

    rows = []
    for path in sorted(paths, key=lambda value: str(value).casefold()):
        rows.append(
            {
                "path": str(path),
                "roles": sorted(paths[path]),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return {
        "schema": SOURCE_SNAPSHOT_SCHEMA,
        "sources": rows,
        "snapshot_sha256": canonical_sha256(rows),
    }


def assert_render_source_snapshot_unchanged(
    start: dict[str, object], end: dict[str, object]
) -> None:
    if start.get("schema") != SOURCE_SNAPSHOT_SCHEMA or end.get(
        "schema"
    ) != SOURCE_SNAPSHOT_SCHEMA:
        raise RuntimeError("render source snapshot schema mismatch")
    if start.get("snapshot_sha256") == end.get("snapshot_sha256"):
        return
    start_rows = {
        str(row["path"]): row
        for row in start.get("sources", [])
        if isinstance(row, dict) and "path" in row
    }
    end_rows = {
        str(row["path"]): row
        for row in end.get("sources", [])
        if isinstance(row, dict) and "path" in row
    }
    changes = []
    for path in sorted(set(start_rows) | set(end_rows), key=str.casefold):
        before = start_rows.get(path)
        after = end_rows.get(path)
        if before != after:
            changes.append(
                {
                    "path": path,
                    "start_sha256": None if before is None else before.get("sha256"),
                    "end_sha256": None if after is None else after.get("sha256"),
                }
            )
    raise RuntimeError(
        "render source changed during batch; refusing TOCTOU publication: "
        + json.dumps(changes, ensure_ascii=False, sort_keys=True)
    )


def subtitle_edition_paths(
    out_root: Path, event: str, language: str
) -> tuple[Path, Path]:
    event = validate_output_identifier(event, label="event")
    if language == "ja":
        paths = (
            out_root / "with_subtitles" / f"{event}__subtitles.mp4",
            out_root / "subtitles" / f"{event}.srt",
        )
    else:
        paths = (
            out_root
            / f"with_subtitles_{language}"
            / f"{event}__{language}_subtitles.mp4",
            out_root / f"subtitles_{language}" / f"{event}.{language}.srt",
        )
    return tuple(
        ensure_resolved_containment(out_root, path, label=f"{event} subtitle output")
        for path in paths
    )


def profile_edition_paths(
    out_root: Path,
    event: str,
    audio_profile: str,
    subtitle_edition: str,
) -> tuple[Path, Path | None]:
    event = validate_output_identifier(event, label="event")
    if audio_profile == LEGACY_AUDIO_PROFILE:
        if subtitle_edition == "none":
            path = out_root / "without_subtitles" / f"{event}.mp4"
            return (
                ensure_resolved_containment(
                    out_root, path, label=f"{event} subtitle-free output"
                ),
                None,
            )
        return subtitle_edition_paths(out_root, event, subtitle_edition)
    profile_root = out_root / audio_profile
    if subtitle_edition == "none":
        paths: tuple[Path, Path | None] = (
            profile_root / "without_subtitles" / f"{event}.mp4",
            None,
        )
    if subtitle_edition == "ja":
        paths = (
            profile_root / "with_subtitles" / f"{event}__subtitles.mp4",
            out_root / "subtitles" / "ja" / f"{event}.ja.srt",
        )
    elif subtitle_edition != "none":
        paths = (
            profile_root
            / f"with_subtitles_{subtitle_edition}"
            / f"{event}__{subtitle_edition}_subtitles.mp4",
            out_root
            / "subtitles"
            / subtitle_edition
            / f"{event}.{subtitle_edition}.srt",
        )
    return (
        ensure_resolved_containment(
            out_root, paths[0], label=f"{event} edition video output"
        ),
        (
            ensure_resolved_containment(
                out_root, paths[1], label=f"{event} subtitle output"
            )
            if paths[1] is not None
            else None
        ),
    )


def render_one(
    manifest_path: Path,
    edition_plan: dict[str, object],
    base_video_dirs: dict[str, Path],
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    publication_root: Path | None = None,
) -> dict[str, object]:
    publication_root = (
        out_root.resolve() if publication_root is None else publication_root.resolve()
    )
    resolved_out_root = out_root.resolve()

    def published(path: Path) -> Path:
        return publication_root / path.resolve().relative_to(resolved_out_root)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    event = validate_output_identifier(manifest["event"], label="manifest event")
    plan_event_value = edition_plan.get("event")
    if plan_event_value not in (None, ""):
        plan_event = validate_output_identifier(
            plan_event_value, label="edition plan event"
        )
        if plan_event != event:
            raise RuntimeError(f"edition plan event mismatch for {event}")
    output_manifest_path = ensure_resolved_containment(
        out_root,
        out_root / "manifests" / f"{event}.json",
        label=f"{event} copied manifest output",
    )
    render_manifest_path = (
        resolve_output_child(out_root, event, label="event") / "render_manifest.json"
    )
    manifest_method = link_or_copy(manifest_path, output_manifest_path)
    expected = manifest["native_dimensions"]
    expected_signature = (
        int(expected["width"]),
        int(expected["height"]),
        str(manifest["native_frame_rate"]),
    )
    plan_tracks = edition_plan["tracks"]
    assert isinstance(plan_tracks, dict)
    subtitle_layout = edition_plan.get("subtitle_layout")
    requested_editions = edition_plan["requested_editions"]
    requested_profiles = edition_plan["requested_audio_profiles"]
    assert isinstance(requested_editions, list)
    assert isinstance(requested_profiles, list)
    verified_matrix = set(requested_profiles) == set(AUDIO_PROFILES)
    if verified_matrix:
        try:
            render_duration_ms = int(manifest["render_duration_ms"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(
                f"{event} verified render requires render_duration_ms"
            ) from error
        if render_duration_ms <= 0:
            raise RuntimeError(f"{event} render_duration_ms must be positive")

    track_assets: dict[str, dict[str, object]] = {}
    for language in requested_editions:
        if language == "none":
            continue
        track = plan_tracks[language]
        cues = track["cues"]
        font = track["font"]
        _, subtitle_path = profile_edition_paths(
            out_root, event, requested_profiles[0], language
        )
        assert subtitle_path is not None
        write_srt(subtitle_path, cues)
        srt_validation = validate_srt_against_edition_plan(
            subtitle_path,
            cues,
            event=event,
            language=language,
        )
        staged_font = ""
        font_method = ""
        staged_font_path: Path | None = None
        if cues:
            if not isinstance(font, dict):
                raise RuntimeError(f"{event} {language} has cues without a font binding")
            source_font = Path(str(font["path"])).resolve()
            staged_font_path = (
                out_root
                / "fonts"
                / event
                / language
                / (str(font["sha256"])[:16] + source_font.suffix.lower())
            )
            font_method = link_or_copy(source_font, staged_font_path)
            staged_font = str(published(staged_font_path))
        track_assets[language] = {
            "cues": cues,
            "font": font,
            "subtitle_path": subtitle_path,
            "staged_font_path": staged_font_path,
            "staged_font": staged_font,
            "font_stage_method": font_method,
            "srt_validation": srt_validation,
        }

    edition_matrix: dict[str, dict[str, object]] = {}
    audio_sha256_by_profile: dict[str, str] = {}
    source_video_sha256_by_profile: dict[str, str] = {}
    source_audio_signature_by_profile: dict[str, tuple[str, ...]] = {}
    video_packet_sha256_by_profile_and_edition: dict[str, dict[str, str]] = {}
    video_timeline_sha256_by_profile_and_edition: dict[str, dict[str, str]] = {}
    video_timeline_audit_by_profile_and_edition: dict[
        str, dict[str, dict[str, object]]
    ] = {}
    decoded_pcm_sha256_by_profile: dict[str, str] = {}
    base_master_manifests: dict[str, dict[str, object]] = {}
    source_video_timeline_sha256_by_profile: dict[str, str] = {}
    source_video_timeline_audit_by_profile: dict[str, dict[str, object]] = {}
    first_none_method = ""
    first_ja_method = ""
    for profile in requested_profiles:
        base_path = base_video_dirs[profile] / f"{event}.mp4"
        if not base_path.is_file():
            raise FileNotFoundError(
                f"missing verified {profile} base video: {base_path}"
            )
        base_probe = probe(base_path, ffprobe)
        base_video_streams = [
            stream
            for stream in base_probe["streams"]
            if stream.get("codec_type") == "video"
        ]
        if verified_matrix and len(base_video_streams) != 1:
            raise RuntimeError(
                f"{event} {profile} must have exactly one verified video stream"
            )
        if not base_video_streams:
            raise RuntimeError(f"{event} {profile} base has no video stream")
        base_video = base_video_streams[0]
        base_signature = (
            int(base_video["width"]),
            int(base_video["height"]),
            str(base_video["r_frame_rate"]),
        )
        if base_signature != expected_signature:
            raise RuntimeError(
                f"{event} {profile} base signature {base_signature} != "
                f"manifest {expected_signature}"
            )
        base_audio_streams = [
            stream
            for stream in base_probe["streams"]
            if stream.get("codec_type") == "audio"
        ]
        if verified_matrix and len(base_audio_streams) != 1:
            raise RuntimeError(
                f"{event} {profile} must have exactly one verified audio stream"
            )
        if base_audio_streams:
            source_audio_signature_by_profile[profile] = audio_encoding_signature(
                base_audio_streams[0]
            )
        target_video_bitrate = 0
        if verified_matrix:
            validate_stream_coverage(
                base_video,
                expected_duration_ms=render_duration_ms,
                label=f"{event} {profile} video stream",
            )
            validate_stream_coverage(
                base_audio_streams[0],
                expected_duration_ms=render_duration_ms,
                label=f"{event} {profile} audio stream",
            )
            validate_native_audio_signature(
                base_audio_streams[0], label=f"{event} {profile}"
            )
            if str(base_video.get("codec_name", "")) != "h264":
                raise RuntimeError(
                    f"{event} {profile} base video is not native H.264"
                )
            try:
                target_video_bitrate = int(base_video.get("bit_rate", 0))
            except (TypeError, ValueError) as error:
                raise RuntimeError(
                    f"{event} {profile} has invalid native video bitrate"
                ) from error
            if target_video_bitrate <= 0:
                raise RuntimeError(
                    f"{event} {profile} lacks an auditable native video bitrate"
                )
            frame_count_value = base_video.get("nb_read_frames") or base_video.get(
                "nb_frames"
            )
            try:
                frame_count = int(frame_count_value)
                rate_num, rate_den = (
                    int(value) for value in str(manifest["native_frame_rate"]).split("/", 1)
                )
                expected_frames = round(
                    render_duration_ms * rate_num / rate_den / 1000
                )
            except (TypeError, ValueError, ZeroDivisionError) as error:
                raise RuntimeError(
                    f"{event} {profile} lacks auditable frame count/rate"
                ) from error
            if abs(frame_count - expected_frames) > 1:
                raise RuntimeError(
                    f"{event} {profile} frame count {frame_count} != "
                    f"expected {expected_frames}"
                )
        base_audio_sha256 = audio_hash(base_path, ffmpeg)
        base_decoded_pcm_sha256 = (
            decoded_pcm_hash(base_path, ffmpeg) if verified_matrix else ""
        )
        base_video_packet_sha256 = video_packet_hash(base_path, ffmpeg)
        base_video_timeline = (
            probe_video_timeline(
                base_path,
                ffprobe,
                expected_duration_ms=render_duration_ms,
                expected_frame_rate=str(manifest["native_frame_rate"]),
                label=f"{event} {profile} base video",
            )
            if verified_matrix
            else {}
        )
        base_video_timeline_sha256 = str(
            base_video_timeline.get("timeline_sha256", "")
        )
        audio_sha256_by_profile[profile] = base_audio_sha256
        decoded_pcm_sha256_by_profile[profile] = base_decoded_pcm_sha256
        source_video_sha256_by_profile[profile] = base_video_packet_sha256
        source_video_timeline_sha256_by_profile[profile] = (
            base_video_timeline_sha256
        )
        source_video_timeline_audit_by_profile[profile] = base_video_timeline
        if verified_matrix:
            audio_contract = edition_plan.get("audio_master_contract")
            contract_profiles = (
                audio_contract.get("profiles", {})
                if isinstance(audio_contract, dict)
                else {}
            )
            profile_contract = contract_profiles.get(profile)
            if not isinstance(profile_contract, dict):
                raise RuntimeError(
                    f"{event} has no validated audio contract for {profile}"
                )
            base_master_manifests[profile] = validate_base_master_manifest(
                event=event,
                profile=profile,
                base_path=base_path,
                profile_contract=profile_contract,
                event_manifest_path=manifest_path,
                base_probe=base_probe,
                audio_packet_sha256=base_audio_sha256,
                decoded_pcm_sha256=base_decoded_pcm_sha256,
                video_packet_sha256=base_video_packet_sha256,
                video_timeline_sha256=base_video_timeline_sha256,
            )
        without_path, _ = profile_edition_paths(out_root, event, profile, "none")
        without_method = link_or_copy(base_path, without_path)
        without_audio_sha256 = audio_hash(without_path, ffmpeg)
        without_video_packet_sha256 = video_packet_hash(without_path, ffmpeg)
        without_video_timeline = (
            probe_video_timeline(
                without_path,
                ffprobe,
                expected_duration_ms=render_duration_ms,
                expected_frame_rate=str(manifest["native_frame_rate"]),
                label=f"{event} {profile}.none video",
            )
            if verified_matrix
            else {}
        )
        without_video_timeline_sha256 = str(
            without_video_timeline.get("timeline_sha256", "")
        )
        without_decoded_pcm_sha256 = (
            decoded_pcm_hash(without_path, ffmpeg) if verified_matrix else ""
        )
        if (
            without_audio_sha256 != base_audio_sha256
            or without_video_packet_sha256 != base_video_packet_sha256
            or (
                verified_matrix
                and without_video_timeline_sha256 != base_video_timeline_sha256
            )
            or (
                verified_matrix
                and without_decoded_pcm_sha256 != base_decoded_pcm_sha256
            )
        ):
            raise RuntimeError(
                f"{event} {profile}.none changed packets/PCM while staging"
            )
        if not first_none_method:
            first_none_method = without_method
        profile_editions: dict[str, dict[str, object]] = {
            "none": {
                "language": "none",
                "video": str(published(without_path)),
                "subtitles": "",
                "video_method": without_method,
                "audio_sha256": without_audio_sha256,
                "decoded_pcm_sha256": without_decoded_pcm_sha256,
                "video_packet_sha256": without_video_packet_sha256,
                "video_timeline_sha256": without_video_timeline_sha256,
                "video_timeline_audit": without_video_timeline,
                "video_sha256": file_sha256(without_path),
                "subtitle_sha256": "",
                "probe": base_probe,
            }
        }
        for language in requested_editions:
            if language == "none":
                continue
            assets = track_assets[language]
            cues = assets["cues"]
            with_path, subtitle_path = profile_edition_paths(
                out_root, event, profile, language
            )
            assert subtitle_path is not None
            # Re-read the exact staged SRT immediately before each consumer.
            # This makes a prior worker/process edit fail closed.
            before_srt = validate_srt_against_edition_plan(
                subtitle_path,
                cues,
                event=event,
                language=language,
            )
            if before_srt != assets["srt_validation"]:
                raise RuntimeError(
                    f"{event} {language} SRT changed after initial round-trip"
                )
            if not cues:
                with_method = link_or_copy(base_path, with_path)
            else:
                font = assets["font"]
                staged_font_path = assets["staged_font_path"]
                if not isinstance(font, dict) or not isinstance(
                    staged_font_path, Path
                ):
                    raise RuntimeError(
                        f"{event} {language} has no staged verified font"
                    )
                if not isinstance(subtitle_layout, dict) or not isinstance(
                    subtitle_layout.get("style"), dict
                ):
                    raise RuntimeError(
                        f"{event} {language} has no verified subtitle layout"
                    )
                style = subtitle_layout["style"]
                with_path.parent.mkdir(parents=True, exist_ok=True)
                relative_subtitle = subtitle_path.relative_to(out_root).as_posix()
                relative_fonts = (
                    staged_font_path.parent.relative_to(out_root).as_posix()
                )
                subtitle_filter = (
                    f"subtitles=filename='{relative_subtitle}':"
                    f"fontsdir='{relative_fonts}':"
                    f"force_style='FontName={font['family']},"
                    f"FontSize={style['font_size']},"
                    f"PrimaryColour={style['primary_colour']},"
                    f"OutlineColour={style['outline_colour']},"
                    f"BorderStyle={style['border_style']},"
                    f"Outline={style['outline']},Shadow={style['shadow']},"
                    f"MarginV={style['margin_v']},Alignment={style['alignment']}'"
                )
                subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(base_path),
                        "-vf",
                        subtitle_filter,
                        "-c:v",
                        "libx264",
                        "-preset",
                        "slow",
                        "-b:v",
                        str(target_video_bitrate),
                        "-maxrate",
                        str(target_video_bitrate),
                        "-bufsize",
                        str(target_video_bitrate * 2),
                        "-profile:v",
                        x264_profile_argument(base_video.get("profile")),
                        "-level:v",
                        x264_level_argument(base_video.get("level")),
                        "-pix_fmt",
                        str(base_video.get("pix_fmt") or "yuv420p"),
                        "-c:a",
                        "copy",
                        "-movflags",
                        "+faststart",
                        str(with_path),
                    ],
                    cwd=out_root,
                    check=True,
                )
                with_method = "rendered_video_audio_copy"
            after_srt = validate_srt_against_edition_plan(
                subtitle_path,
                cues,
                event=event,
                language=language,
            )
            if after_srt != assets["srt_validation"]:
                raise RuntimeError(
                    f"{event} {language} SRT changed while rendering"
                )
            with_probe = probe(with_path, ffprobe)
            with_video = next(
                stream
                for stream in with_probe["streams"]
                if stream.get("codec_type") == "video"
            )
            output_signature = (
                int(with_video["width"]),
                int(with_video["height"]),
                str(with_video["r_frame_rate"]),
            )
            if output_signature != expected_signature:
                raise RuntimeError(
                    f"{event} {profile}.{language} output {output_signature} "
                    f"!= {expected_signature}"
                )
            if verified_matrix and video_encoding_signature(with_video) != video_encoding_signature(
                base_video
            ):
                raise RuntimeError(
                    f"{event} {profile}.{language} changed native video encoding signature"
                )
            if verified_matrix and cues:
                try:
                    output_video_bitrate = int(with_video.get("bit_rate", 0))
                except (TypeError, ValueError) as error:
                    raise RuntimeError(
                        f"{event} {profile}.{language} has invalid video bitrate"
                    ) from error
                if output_video_bitrate <= 0 or abs(
                    output_video_bitrate - target_video_bitrate
                ) > max(10_000, round(target_video_bitrate * 0.05)):
                    raise RuntimeError(
                        f"{event} {profile}.{language} bitrate "
                        f"{output_video_bitrate} differs from native "
                        f"{target_video_bitrate}"
                    )
            edition_audio_sha256 = audio_hash(with_path, ffmpeg)
            if edition_audio_sha256 != base_audio_sha256:
                raise RuntimeError(
                    f"{event} {profile}.{language} audio differs from none edition"
                )
            edition_decoded_pcm_sha256 = (
                decoded_pcm_hash(with_path, ffmpeg) if verified_matrix else ""
            )
            if verified_matrix and edition_decoded_pcm_sha256 != base_decoded_pcm_sha256:
                raise RuntimeError(
                    f"{event} {profile}.{language} decoded PCM differs from none edition"
                )
            if language == "ja" and not first_ja_method:
                first_ja_method = with_method
            edition_video_packet_sha256 = video_packet_hash(with_path, ffmpeg)
            edition_video_timeline = (
                probe_video_timeline(
                    with_path,
                    ffprobe,
                    expected_duration_ms=render_duration_ms,
                    expected_frame_rate=str(manifest["native_frame_rate"]),
                    label=f"{event} {profile}.{language} video",
                )
                if verified_matrix
                else {}
            )
            edition_video_timeline_sha256 = str(
                edition_video_timeline.get("timeline_sha256", "")
            )
            if (
                verified_matrix
                and edition_video_timeline_sha256 != base_video_timeline_sha256
            ):
                raise RuntimeError(
                    f"{event} {profile}.{language} changed the audited video timeline"
                )
            profile_editions[language] = {
                "language": language,
                "video": str(published(with_path)),
                "subtitles": str(published(subtitle_path)),
                "video_method": with_method,
                "audio_sha256": edition_audio_sha256,
                "decoded_pcm_sha256": edition_decoded_pcm_sha256,
                "video_packet_sha256": edition_video_packet_sha256,
                "video_timeline_sha256": edition_video_timeline_sha256,
                "video_timeline_audit": edition_video_timeline,
                "font": assets["font"],
                "staged_font": assets["staged_font"],
                "font_stage_method": assets["font_stage_method"],
                "probe": with_probe,
                "video_sha256": file_sha256(with_path),
                "subtitle_sha256": file_sha256(subtitle_path),
                "srt_round_trip": after_srt,
            }
        audio_contract = edition_plan.get("audio_master_contract")
        contract_profiles = (
            audio_contract.get("profiles", {})
            if isinstance(audio_contract, dict)
            else {}
        )
        edition_matrix[profile] = {
            "audio_profile": profile,
            "audio_sha256": base_audio_sha256,
            "audio_master": contract_profiles.get(profile, {}),
            "editions": profile_editions,
        }
        video_packet_sha256_by_profile_and_edition[profile] = {
            edition: str(row["video_packet_sha256"])
            for edition, row in profile_editions.items()
        }
        video_timeline_sha256_by_profile_and_edition[profile] = {
            edition: str(row["video_timeline_sha256"])
            for edition, row in profile_editions.items()
        }
        video_timeline_audit_by_profile_and_edition[profile] = {
            edition: dict(row["video_timeline_audit"])
            for edition, row in profile_editions.items()
        }

    validate_audio_master_distinction(
        audio_sha256_by_profile, decoded_pcm_sha256_by_profile
    )
    if verified_matrix:
        validate_video_identity_across_audio_masters(
            event=event,
            profiles=requested_profiles,
            editions=requested_editions,
            source_packet_sha256_by_profile=source_video_sha256_by_profile,
            source_timeline_sha256_by_profile=(
                source_video_timeline_sha256_by_profile
            ),
            packet_sha256_by_profile_and_edition=(
                video_packet_sha256_by_profile_and_edition
            ),
            timeline_sha256_by_profile_and_edition=(
                video_timeline_sha256_by_profile_and_edition
            ),
        )
    if verified_matrix and len(set(source_audio_signature_by_profile.values())) != 1:
        raise RuntimeError(
            f"{event} audio masters do not share one codec/sample/channel signature"
        )

    legacy_editions = edition_matrix.get(LEGACY_AUDIO_PROFILE, {}).get(
        "editions", {}
    )
    ja_output = legacy_editions.get("ja", {})
    render_manifest = {
        "schema": "magireco-native-subtitle-event-editions-v3",
        "legacy_schema_compatible": bool(legacy_editions),
        "event": event,
        "source_manifest": str(manifest_path.resolve()),
        "source_manifest_sha256": file_sha256(manifest_path),
        "without_subtitles": legacy_editions.get("none", {}).get("video", ""),
        "with_subtitles": ja_output.get("video", ""),
        "subtitles": ja_output.get("subtitles", ""),
        "editions": legacy_editions,
        "edition_matrix": (
            {}
            if LEGACY_AUDIO_PROFILE in edition_matrix
            else edition_matrix
        ),
        "edition_plan": edition_plan,
        "subtitle_layout": subtitle_layout,
        "shared_audio_sha256": audio_sha256_by_profile.get(
            LEGACY_AUDIO_PROFILE, ""
        ),
        "audio_sha256_by_profile": audio_sha256_by_profile,
        "decoded_pcm_sha256_by_profile": decoded_pcm_sha256_by_profile,
        "base_master_manifests": base_master_manifests,
        "source_video_sha256_by_profile": source_video_sha256_by_profile,
        "source_video_timeline_sha256_by_profile": (
            source_video_timeline_sha256_by_profile
        ),
        "source_video_timeline_audit_by_profile": (
            source_video_timeline_audit_by_profile
        ),
        "source_audio_signature_by_profile": {
            profile: list(signature)
            for profile, signature in source_audio_signature_by_profile.items()
        },
        "video_packet_sha256_by_profile_and_edition": (
            video_packet_sha256_by_profile_and_edition
        ),
        "video_timeline_sha256_by_profile_and_edition": (
            video_timeline_sha256_by_profile_and_edition
        ),
        "video_timeline_audit_by_profile_and_edition": (
            video_timeline_audit_by_profile_and_edition
        ),
        "native_dimensions": manifest["native_dimensions"],
        "native_frame_rate": manifest["native_frame_rate"],
    }
    render_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    render_manifest_path.write_text(
        json.dumps(render_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "event": event,
        "width": expected_signature[0],
        "height": expected_signature[1],
        "frame_rate": expected_signature[2],
        "subtitle_count": int(plan_tracks.get("ja", {}).get("cue_count", 0)),
        "without_subtitles_method": first_none_method,
        "with_subtitles_method": first_ja_method,
        "manifest_method": manifest_method,
        "render_manifest": str(published(render_manifest_path)),
        "shared_audio_sha256": audio_sha256_by_profile.get(
            LEGACY_AUDIO_PROFILE, ""
        ),
        "audio_sha256_by_profile": audio_sha256_by_profile,
        "decoded_pcm_sha256_by_profile": decoded_pcm_sha256_by_profile,
        "base_master_manifests": base_master_manifests,
        "source_video_sha256_by_profile": source_video_sha256_by_profile,
        "source_video_timeline_sha256_by_profile": (
            source_video_timeline_sha256_by_profile
        ),
        "editions": legacy_editions,
        "edition_matrix": edition_matrix,
        "edition_plan": edition_plan,
    }


def _build_batch_summary(
    *,
    rows: list[dict[str, object]],
    planned: list[tuple[Path, dict[str, object]]],
    manifest_root: Path,
    base_video_dirs: dict[str, Path],
    out_root: Path,
    expected_event_index: dict[str, object] | None,
    legacy_two_edition: bool,
    source_snapshot_start: dict[str, object],
    source_snapshot_end: dict[str, object],
) -> dict[str, object]:
    return {
        "schema": "magireco-native-subtitle-editions-v4",
        "legacy_schema_compatible": legacy_two_edition,
        "events": len(rows),
        "native_resolution_preserved": len(rows),
        "without_subtitles_hardlinks": sum(
            edition.get("video_method") == "hardlink"
            for row in rows
            for profile in row["edition_matrix"].values()
            for language, edition in profile["editions"].items()
            if language == "none"
        ),
        "subtitle_video_renders": sum(
            edition.get("video_method") == "rendered_video_audio_copy"
            for row in rows
            for profile in row["edition_matrix"].values()
            for language, edition in profile["editions"].items()
            if language != "none"
        ),
        "subtitle_free_hardlinks": sum(
            edition.get("video_method") == "hardlink"
            for row in rows
            for profile in row["edition_matrix"].values()
            for language, edition in profile["editions"].items()
            if language != "none"
        ),
        "manifest_root": str(manifest_root),
        "base_video_dirs": {
            profile: str(path) for profile, path in base_video_dirs.items()
        },
        "out_root": str(out_root),
        "requested_editions": (
            planned[0][1]["requested_editions"] if planned else []
        ),
        "requested_audio_profiles": (
            planned[0][1]["requested_audio_profiles"] if planned else []
        ),
        "expected_event_index": expected_event_index,
        "publication_eligible": not legacy_two_edition,
        "batch_transaction": {
            "schema": SUBTITLE_BATCH_READY_SCHEMA,
            "status": "staged_and_rehashed",
            "source_snapshot_start_sha256": source_snapshot_start[
                "snapshot_sha256"
            ],
            "source_snapshot_end_sha256": source_snapshot_end[
                "snapshot_sha256"
            ],
            "source_rehash_match": True,
            "ready_marker": str(out_root / SUBTITLE_BATCH_READY_FILENAME),
            "publication_rule": SUBTITLE_BATCH_PUBLICATION_RULE,
        },
        "source_snapshot": source_snapshot_end,
        "events_detail": rows,
    }


def _write_batch_ready_marker(
    *,
    staging_root: Path,
    publication_root: Path,
    summary: dict[str, object],
    source_snapshot_start: dict[str, object],
    source_snapshot_end: dict[str, object],
) -> dict[str, object]:
    summary_path = staging_root / "subtitle_editions_summary.json"
    event_rows = []
    details = summary.get("events_detail")
    if not isinstance(details, list):
        raise RuntimeError("subtitle batch summary lacks event details")
    for row in details:
        if not isinstance(row, dict):
            raise RuntimeError("subtitle batch summary event row is malformed")
        event = validate_output_identifier(
            row.get("event", ""), label="subtitle batch event"
        )
        staged_manifest = staging_root / event / "render_manifest.json"
        if not event or not staged_manifest.is_file():
            raise RuntimeError(f"subtitle batch lacks render manifest for {event!r}")
        event_rows.append(
            {
                "event": event,
                "render_manifest": str(
                    publication_root / event / "render_manifest.json"
                ),
                "render_manifest_sha256": file_sha256(staged_manifest),
            }
        )
    marker = {
        "schema": SUBTITLE_BATCH_READY_SCHEMA,
        "status": "ready",
        "publishable": bool(summary.get("publication_eligible")),
        "publication_rule": SUBTITLE_BATCH_PUBLICATION_RULE,
        "batch_id": uuid.uuid4().hex,
        "events": len(event_rows),
        "source_rehash": {
            "status": "passed",
            "start_sha256": source_snapshot_start["snapshot_sha256"],
            "end_sha256": source_snapshot_end["snapshot_sha256"],
            "match": True,
            "source_count": len(source_snapshot_end["sources"]),
        },
        "expected_event_index": summary.get("expected_event_index"),
        "summary": {
            "path": str(publication_root / summary_path.name),
            "sha256": file_sha256(summary_path),
        },
        "event_manifests": event_rows,
    }
    ready_path = staging_root / SUBTITLE_BATCH_READY_FILENAME
    ready_path.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(publication_root / SUBTITLE_BATCH_READY_FILENAME),
        "sha256": file_sha256(ready_path),
        "marker": marker,
    }


def _published_batch_file(value: object, *, out_root: Path, field: str) -> Path:
    path = Path(str(value or "")).resolve()
    try:
        path.relative_to(out_root.resolve())
    except ValueError as error:
        raise RuntimeError(f"{field} escapes the subtitle publication root") from error
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def verify_promoted_event_outputs(
    *, event: str, render_manifest: dict, out_root: Path
) -> None:
    """Rehash every promoted video/SRT/font named by one event manifest."""

    event = validate_output_identifier(event, label="promoted event")
    plan = render_manifest.get("edition_plan")
    tracks = plan.get("tracks") if isinstance(plan, dict) else None
    if not isinstance(tracks, dict):
        raise RuntimeError(f"{event} promoted render manifest lacks edition tracks")
    matrix = render_manifest.get("edition_matrix")
    groups: list[dict] = []
    if isinstance(matrix, dict) and matrix:
        for profile, group in matrix.items():
            if not isinstance(group, dict) or not isinstance(
                group.get("editions"), dict
            ):
                raise RuntimeError(
                    f"{event} promoted {profile} edition group is malformed"
                )
            groups.append(group["editions"])
    else:
        editions = render_manifest.get("editions")
        if not isinstance(editions, dict) or not editions:
            raise RuntimeError(f"{event} promoted render manifest lacks editions")
        groups.append(editions)

    for editions in groups:
        for language, row in editions.items():
            if not isinstance(row, dict):
                raise RuntimeError(
                    f"{event} promoted {language} edition is malformed"
                )
            video = _published_batch_file(
                row.get("video"),
                out_root=out_root,
                field=f"{event} {language} video",
            )
            if file_sha256(video) != _required_sha256(
                row.get("video_sha256"), field=f"{event} {language} video sha256"
            ):
                raise RuntimeError(
                    f"{event} promoted {language} video SHA-256 mismatch"
                )
            subtitle_value = str(row.get("subtitles", "")).strip()
            if language == "none":
                if subtitle_value:
                    raise RuntimeError(
                        f"{event} subtitle-free edition names a subtitle file"
                    )
                continue
            subtitle = _published_batch_file(
                subtitle_value,
                out_root=out_root,
                field=f"{event} {language} SRT",
            )
            if file_sha256(subtitle) != _required_sha256(
                row.get("subtitle_sha256"),
                field=f"{event} {language} subtitle sha256",
            ):
                raise RuntimeError(
                    f"{event} promoted {language} SRT SHA-256 mismatch"
                )
            track = tracks.get(language)
            if not isinstance(track, dict):
                raise RuntimeError(f"{event} promoted {language} track is missing")
            validate_srt_against_edition_plan(
                subtitle,
                track.get("cues"),
                event=event,
                language=str(language),
            )
            staged_font_value = str(row.get("staged_font", "")).strip()
            cues = track.get("cues")
            if isinstance(cues, list) and cues:
                staged_font = _published_batch_file(
                    staged_font_value,
                    out_root=out_root,
                    field=f"{event} {language} staged font",
                )
                font = row.get("font")
                if not isinstance(font, dict) or file_sha256(
                    staged_font
                ) != _required_sha256(
                    font.get("sha256"), field=f"{event} {language} font sha256"
                ):
                    raise RuntimeError(
                        f"{event} promoted {language} font SHA-256 mismatch"
                    )
            elif staged_font_value:
                raise RuntimeError(
                    f"{event} cue-free {language} edition unexpectedly stages a font"
                )


def verify_promoted_subtitle_batch(out_root: Path) -> dict[str, object]:
    ready_path = out_root / SUBTITLE_BATCH_READY_FILENAME
    _, marker = _read_json_bytes(
        ready_path, label="promoted subtitle batch READY"
    )
    checks = {
        "schema": SUBTITLE_BATCH_READY_SCHEMA,
        "status": "ready",
        "publication_rule": SUBTITLE_BATCH_PUBLICATION_RULE,
    }
    for field, expected in checks.items():
        if marker.get(field) != expected:
            raise RuntimeError(
                f"promoted subtitle batch READY {field} mismatch"
            )
    rehash = marker.get("source_rehash")
    if not isinstance(rehash, dict) or rehash.get("status") != "passed" or rehash.get(
        "match"
    ) is not True:
        raise RuntimeError("promoted subtitle batch lacks a passed source rehash")
    start_sha256 = _required_sha256(
        rehash.get("start_sha256"), field="subtitle batch start source snapshot"
    )
    end_sha256 = _required_sha256(
        rehash.get("end_sha256"), field="subtitle batch end source snapshot"
    )
    if start_sha256 != end_sha256:
        raise RuntimeError("promoted subtitle batch source rehash differs")
    summary = marker.get("summary")
    if not isinstance(summary, dict):
        raise RuntimeError("promoted subtitle batch lacks summary binding")
    summary_path = Path(str(summary.get("path", ""))).resolve()
    expected_summary_path = (out_root / "subtitle_editions_summary.json").resolve()
    if summary_path != expected_summary_path or not summary_path.is_file():
        raise RuntimeError("promoted subtitle batch summary path mismatch")
    if file_sha256(summary_path) != _required_sha256(
        summary.get("sha256"), field="subtitle batch summary sha256"
    ):
        raise RuntimeError("promoted subtitle batch summary SHA-256 mismatch")
    try:
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("promoted subtitle batch summary is invalid JSON") from error
    if marker.get("publishable") is not bool(
        summary_payload.get("publication_eligible")
    ):
        raise RuntimeError("promoted subtitle batch publishable flag mismatch")
    snapshot = summary_payload.get("source_snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema") != SOURCE_SNAPSHOT_SCHEMA
        or snapshot.get("snapshot_sha256") != end_sha256
    ):
        raise RuntimeError("promoted subtitle batch source snapshot binding mismatch")

    event_rows = marker.get("event_manifests")
    if not isinstance(event_rows, list) or len(event_rows) != int(
        marker.get("events", -1)
    ):
        raise RuntimeError("promoted subtitle batch event manifest list mismatch")
    seen = set()
    for row in event_rows:
        if not isinstance(row, dict):
            raise RuntimeError("promoted subtitle event binding is malformed")
        event = validate_output_identifier(
            row.get("event", ""), label="promoted event"
        )
        if event in seen:
            raise RuntimeError("promoted subtitle event binding is blank/duplicate")
        seen.add(event)
        path = Path(str(row.get("render_manifest", ""))).resolve()
        expected = (out_root / event / "render_manifest.json").resolve()
        if path != expected or not path.is_file():
            raise RuntimeError(
                f"promoted subtitle render manifest path mismatch for {event}"
            )
        if file_sha256(path) != _required_sha256(
            row.get("render_manifest_sha256"),
            field=f"{event} render manifest sha256",
        ):
            raise RuntimeError(
                f"promoted subtitle render manifest SHA-256 mismatch for {event}"
            )
        try:
            render_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"promoted subtitle render manifest is invalid JSON for {event}"
            ) from error
        verify_promoted_event_outputs(
            event=event,
            render_manifest=render_payload,
            out_root=out_root,
        )
    return marker


def _remove_owned_batch_directory(path: Path, out_root: Path) -> None:
    resolved = path.resolve()
    parent = out_root.parent.resolve()
    allowed_prefixes = (
        f".{out_root.name}.staging-",
        f".{out_root.name}.previous-",
        f".{out_root.name}.failed-",
    )
    if resolved.parent != parent or not resolved.name.startswith(allowed_prefixes):
        raise RuntimeError(f"refusing to remove non-transaction directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def promote_staged_subtitle_batch(
    staging_root: Path,
    out_root: Path,
    *,
    overwrite: bool = False,
) -> dict:
    """Promote a complete batch while retaining the prior root until verified."""

    staging_root = staging_root.resolve()
    out_root = out_root.resolve()
    if staging_root.parent != out_root.parent:
        raise RuntimeError("subtitle staging and publication roots must share a parent")
    if not (staging_root / SUBTITLE_BATCH_READY_FILENAME).is_file():
        raise RuntimeError("subtitle staging batch lacks its final READY marker")
    if out_root.exists() and not out_root.is_dir():
        raise RuntimeError(f"subtitle publication root is not a directory: {out_root}")
    if out_root.exists() and not overwrite:
        raise FileExistsError(
            "subtitle publication root already exists; pass --overwrite: "
            f"{out_root}"
        )

    token = uuid.uuid4().hex
    previous_root = out_root.parent / f".{out_root.name}.previous-{token}"
    failed_root = out_root.parent / f".{out_root.name}.failed-{token}"
    had_previous = out_root.exists()
    if had_previous:
        os.replace(out_root, previous_root)
    try:
        os.replace(staging_root, out_root)
        marker = verify_promoted_subtitle_batch(out_root)
    except BaseException:
        if out_root.exists():
            os.replace(out_root, failed_root)
        if had_previous and previous_root.exists():
            os.replace(previous_root, out_root)
        _remove_owned_batch_directory(failed_root, out_root)
        raise
    if previous_root.exists():
        _remove_owned_batch_directory(previous_root, out_root)
    return marker


def execute_render_batch(
    *,
    planned: list[tuple[Path, dict[str, object]]],
    base_video_dirs: dict[str, Path],
    out_root: Path,
    workers: int,
    ffmpeg: str,
    ffprobe: str,
    manifest_root: Path,
    expected_event_index: dict[str, object] | None,
    legacy_two_edition: bool,
    overwrite: bool = False,
) -> dict[str, object]:
    """Render and publish one all-or-nothing event-edition batch."""

    # Read-only, whole-batch path preflight.  It runs before the publication
    # parent or staging directory is created, while render_one repeats the
    # validation after rereading each source manifest to close a replacement
    # window.
    seen_events: set[str] = set()
    for manifest_path, plan in planned:
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_event = validate_output_identifier(
            source_manifest.get("event"), label="manifest event"
        )
        plan_event_value = plan.get("event")
        if plan_event_value not in (None, ""):
            plan_event = validate_output_identifier(
                plan_event_value, label="edition plan event"
            )
            if plan_event != manifest_event:
                raise RuntimeError(
                    f"edition plan event mismatch for {manifest_event}"
                )
        if manifest_event in seen_events:
            raise ValueError(f"duplicate subtitle output event: {manifest_event}")
        seen_events.add(manifest_event)

    out_root = out_root.resolve()
    if out_root.exists() and not overwrite:
        raise FileExistsError(
            "subtitle publication root already exists; pass --overwrite: "
            f"{out_root}"
        )

    source_snapshot_start = capture_render_source_snapshot(
        planned,
        base_video_dirs,
        expected_event_index=expected_event_index,
    )
    protected_roots = {
        manifest_root.resolve(),
        *(Path(path).resolve() for path in base_video_dirs.values()),
        *(
            Path(str(row["path"])).resolve().parent
            for row in source_snapshot_start["sources"]
        ),
    }
    for protected_root in protected_roots:
        try:
            out_root.relative_to(protected_root)
            overlaps = True
        except ValueError:
            try:
                protected_root.relative_to(out_root)
                overlaps = True
            except ValueError:
                overlaps = False
        if overlaps:
            raise RuntimeError(
                "subtitle output root overlaps a protected input root: "
                f"output={out_root}, input={protected_root}"
            )

    out_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = out_root.parent / (
        f".{out_root.name}.staging-{uuid.uuid4().hex}"
    )
    staging_root.mkdir()
    try:
        rows: list[dict[str, object]] = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(
                    render_one,
                    path,
                    plan,
                    base_video_dirs,
                    staging_root,
                    ffmpeg,
                    ffprobe,
                    out_root,
                ): path
                for path, plan in planned
            }
            for completed, future in enumerate(as_completed(futures), 1):
                row = future.result()
                rows.append(row)
                print(
                    f"[{completed}/{len(futures)}] {row['event']}",
                    flush=True,
                )

        source_snapshot_end = capture_render_source_snapshot(
            planned,
            base_video_dirs,
            expected_event_index=expected_event_index,
        )
        assert_render_source_snapshot_unchanged(
            source_snapshot_start, source_snapshot_end
        )
        rows.sort(key=lambda row: str(row["event"]))
        summary = _build_batch_summary(
            rows=rows,
            planned=planned,
            manifest_root=manifest_root,
            base_video_dirs=base_video_dirs,
            out_root=out_root,
            expected_event_index=expected_event_index,
            legacy_two_edition=legacy_two_edition,
            source_snapshot_start=source_snapshot_start,
            source_snapshot_end=source_snapshot_end,
        )
        (staging_root / "subtitle_editions_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        ready_reference = _write_batch_ready_marker(
            staging_root=staging_root,
            publication_root=out_root,
            summary=summary,
            source_snapshot_start=source_snapshot_start,
            source_snapshot_end=source_snapshot_end,
        )
        promote_staged_subtitle_batch(
            staging_root,
            out_root,
            overwrite=overwrite,
        )
        summary["batch_ready_marker"] = {
            "path": ready_reference["path"],
            "sha256": ready_reference["sha256"],
        }
        return summary
    except BaseException:
        if staging_root.exists():
            _remove_owned_batch_directory(staging_root, out_root)
        raise


def main() -> int:
    args = parse_args()
    manifest_root = Path(args.manifest_root).resolve()
    manifest_dir = manifest_root / "events"
    if not manifest_dir.is_dir():
        manifest_dir = manifest_root
    if args.legacy_two_edition:
        if not args.base_video_dir:
            raise SystemExit(
                "--legacy-two-edition requires --base-video-dir"
            )
        base_video_dirs = {
            LEGACY_AUDIO_PROFILE: Path(args.base_video_dir).resolve()
        }
    else:
        if args.base_video_dir:
            raise SystemExit(
                "unclassified --base-video-dir is forbidden for the verified "
                "matrix; use the two named audio-master directories"
            )
        declared_dirs = {
            "with_bgm": args.with_bgm_base_video_dir,
            "no_bgm": args.no_bgm_base_video_dir,
        }
        requested_profiles = list(args.audio_profiles or AUDIO_PROFILES)
        missing_dir_args = [
            profile for profile in requested_profiles if not declared_dirs[profile]
        ]
        if missing_dir_args:
            raise SystemExit(
                "missing verified base-video directory argument(s): "
                + ", ".join(missing_dir_args)
            )
        base_video_dirs = {
            profile: Path(declared_dirs[profile]).resolve()
            for profile in requested_profiles
        }
    out_root = Path(args.out_root).resolve()
    font_config = load_font_config(
        Path(args.font_config).resolve() if args.font_config else None
    )

    manifests = []
    for path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (
            manifest.get("quality_gates", {}).get("ready")
            and (not args.only or manifest["event"] in set(args.only))
        ):
            manifests.append(path)

    if not manifests:
        raise SystemExit("no quality-ready event manifests selected")

    planned = []
    for path in manifests:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        event = validate_output_identifier(
            manifest["event"], label="manifest event"
        )
        plan = build_edition_plan(
            manifest,
            editions=args.editions,
            audio_profiles=args.audio_profiles,
            legacy_compat=args.legacy_two_edition,
            font_config=font_config,
            manifest_path=path,
        )
        for profile in plan["requested_audio_profiles"]:
            base_path = base_video_dirs[profile] / f"{event}.mp4"
            if not base_path.is_file():
                raise FileNotFoundError(
                    f"missing verified {profile} base video: {base_path}"
                )
        planned.append(
            (
                path,
                plan,
            )
        )

    expected_event_index = None
    if args.expected_event_index:
        expected_event_index = load_expected_event_index(
            Path(args.expected_event_index).resolve()
        )
        if not expected_event_index["locator"]:
            raise SystemExit("expected event index requires a non-empty locator")
        expected_rows = expected_event_index["events"]
        actual_by_event = {
            str(json.loads(path.read_text(encoding="utf-8"))["event"]): path
            for path, _ in planned
        }
        expected_events = [str(row["event"]) for row in expected_rows]
        if set(actual_by_event) != set(expected_events):
            raise SystemExit(
                "selected event manifests do not exactly match expected event index"
            )
        for row in expected_rows:
            path = actual_by_event[str(row["event"])]
            if file_sha256(path) != str(row["manifest_sha256"]):
                raise SystemExit(
                    f"event manifest SHA-256 mismatch for {row['event']}"
                )
        plan_by_event = {
            str(json.loads(path.read_text(encoding="utf-8"))["event"]): (path, plan)
            for path, plan in planned
        }
        planned = [plan_by_event[event] for event in expected_events]

    if args.dry_run:
        summary = {
            "schema": "magireco-native-subtitle-editions-dry-run-v2",
            "dry_run": True,
            "rendered": False,
            "events": len(planned),
            "requested_editions": (
                planned[0][1]["requested_editions"] if planned else []
            ),
            "requested_audio_profiles": (
                planned[0][1]["requested_audio_profiles"] if planned else []
            ),
            "edition_count_per_event": (
                planned[0][1]["edition_count"] if planned else 0
            ),
            "plans": [plan for _, plan in planned],
            "publication_eligible": False,
            "expected_event_index": expected_event_index,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if not args.legacy_two_edition:
        if expected_event_index is None:
            raise SystemExit(
                "publication rendering requires --expected-event-index; "
                "unindexed subsets are dry-run only"
            )
        if args.only:
            raise SystemExit("publication rendering forbids --only subsets")
        for _, plan in planned:
            if set(plan["requested_audio_profiles"]) != set(AUDIO_PROFILES) or set(
                plan["requested_editions"]
            ) != set(SUPPORTED_EDITIONS):
                raise SystemExit(
                    "publication rendering requires the complete 2x3 edition "
                    "matrix; subset requests are dry-run only"
                )

    summary = execute_render_batch(
        planned=planned,
        base_video_dirs=base_video_dirs,
        out_root=out_root,
        workers=args.workers,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
        manifest_root=manifest_root,
        expected_event_index=expected_event_index,
        legacy_two_edition=args.legacy_two_edition,
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "events_detail"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
