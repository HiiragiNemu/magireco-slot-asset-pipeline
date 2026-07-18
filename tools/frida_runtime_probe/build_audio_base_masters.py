#!/usr/bin/env python3
"""Render the two evidence-bound audio base masters for one clean event video.

This tool deliberately implements only the audio semantics that can be mapped
to FFmpeg without inference: constant linear/dB voice or SE gain, non-looping
BGM, and instantaneous (step) BGM gain changes.  Game-parameter gain, fades,
and looping are rejected instead of being approximated.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

try:
    from .composition_contract import (
        composition_contract_projection,
        composition_contract_sha256,
        presentation_sample_count,
    )
    from .render_subtitle_editions import (
        BASE_MASTER_SCHEMA,
        audio_encoding_signature,
        audio_hash,
        canonical_sha256,
        decoded_pcm_hash,
        event_contract_projection_sha256,
        file_sha256,
        probe,
        probe_video_timeline,
        validate_audio_master_distinction,
        validate_native_audio_signature,
        video_encoding_signature,
        video_packet_hash,
    )
    from .subtitle_edition_contract import (
        AUDIO_PROFILES,
        AUDIO_PROFILE_NO_BGM,
        AUDIO_PROFILE_WITH_BGM,
        inspect_audio_asset,
        validate_audio_master_contract,
    )
except ImportError:  # direct script execution
    from composition_contract import (  # type: ignore
        composition_contract_projection,
        composition_contract_sha256,
        presentation_sample_count,
    )
    from render_subtitle_editions import (  # type: ignore
        BASE_MASTER_SCHEMA,
        audio_encoding_signature,
        audio_hash,
        canonical_sha256,
        decoded_pcm_hash,
        event_contract_projection_sha256,
        file_sha256,
        probe,
        probe_video_timeline,
        validate_audio_master_distinction,
        validate_native_audio_signature,
        video_encoding_signature,
        video_packet_hash,
    )
    from subtitle_edition_contract import (  # type: ignore
        AUDIO_PROFILES,
        AUDIO_PROFILE_NO_BGM,
        AUDIO_PROFILE_WITH_BGM,
        inspect_audio_asset,
        validate_audio_master_contract,
    )


EVENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SAMPLES_PER_MILLISECOND = 48
SUPPORTED_VOLUME_UNITS = {"linear", "db"}
SUPPORTED_STEP_KINDS = {"initial", "duck", "restore", "stop"}
CLEAN_VISUAL_RENDER_SCHEMA = "magireco-clean-visual-render-v1"
READY_SCHEMA = "magireco-audio-base-master-transaction-ready-v1"


def _path_lexists(path: Path) -> bool:
    """Return true for every directory entry, including dangling symlinks."""

    return os.path.lexists(path)


@contextmanager
def _event_promotion_mutex(lock_path: Path):
    """Hold a short, process-scoped lock around check-and-promotion.

    The lock file is intentionally persistent: the operating-system lock, not
    deletion of a pathname, defines ownership.  A process crash therefore
    releases the mutex without leaving a stale lock that blocks future builds.
    """

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError(
                    f"audio-base-master promotion is already active: {lock_path}"
                ) from error
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError(
                    f"audio-base-master promotion is already active: {lock_path}"
                ) from error
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _link_staged_file_no_replace(staged_path: Path, final_path: Path) -> None:
    """Atomically publish one same-volume file without replacing a target."""

    try:
        os.link(staged_path, final_path, follow_symlinks=False)
    except FileExistsError as error:
        raise FileExistsError(
            "concurrent output appeared during audio-base-master promotion; "
            f"refusing to overwrite it: {final_path}"
        ) from error


def _rollback_owned_hardlink(staged_path: Path, final_path: Path) -> None:
    """Remove ``final_path`` only while it still names our staged inode."""

    try:
        staged_stat = staged_path.stat(follow_symlinks=False)
        final_stat = final_path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    owned = (
        not final_path.is_symlink()
        and staged_stat.st_dev == final_stat.st_dev
        and staged_stat.st_ino == final_stat.st_ino
    )
    if owned:
        final_path.unlink()


def _promote_audio_base_master_transaction(
    *,
    staged_artifacts: Sequence[tuple[Path, Path]],
    staged_ready: Path,
    final_ready: Path,
    lock_path: Path,
) -> None:
    """Publish both profiles transactionally, with READY linked last.

    Staging lives below ``out_root`` and therefore on the destination volume.
    Hard-link creation provides an atomic no-replace primitive on both NTFS and
    POSIX filesystems.  The event mutex serializes conforming builders; the
    no-replace operation still fails closed against an uncoordinated writer
    that creates a target after the final existence check.
    """

    publish_pairs = [*staged_artifacts, (staged_ready, final_ready)]
    normalized_targets = [
        os.path.normcase(os.path.abspath(final_path))
        for _, final_path in publish_pairs
    ]
    if len(set(normalized_targets)) != len(normalized_targets):
        raise RuntimeError("audio-base-master promotion contains duplicate targets")
    for staged_path, _ in publish_pairs:
        if staged_path.is_symlink() or not staged_path.is_file():
            raise RuntimeError(
                f"staged promotion artifact is not a file: {staged_path}"
            )

    with _event_promotion_mutex(lock_path):
        for _, final_path in publish_pairs:
            final_path.parent.mkdir(parents=True, exist_ok=True)
        existing = [
            final_path
            for _, final_path in publish_pairs
            if _path_lexists(final_path)
        ]
        if existing:
            raise FileExistsError(f"refusing to overwrite output(s): {existing}")
        for staged_path, final_path in publish_pairs:
            if staged_path.stat().st_dev != final_path.parent.stat().st_dev:
                raise RuntimeError(
                    "audio-base-master staging and destination are not on the "
                    f"same volume: {staged_path} -> {final_path}"
                )

        promoted: list[tuple[Path, Path]] = []
        try:
            for staged_path, final_path in publish_pairs:
                _link_staged_file_no_replace(staged_path, final_path)
                promoted.append((staged_path, final_path))
        except BaseException:
            for staged_path, final_path in reversed(promoted):
                _rollback_owned_hardlink(staged_path, final_path)
            raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build exactly two native-video AAC masters from an audited event "
            "audio_master_contract"
        )
    )
    parser.add_argument("--event-manifest", required=True)
    parser.add_argument("--clean-visual", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument(
        "--aac-bitrate",
        type=int,
        help="optional assertion; must equal audio_master_contract.output_encoding.bit_rate",
    )
    return parser.parse_args(argv)


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"media command failed: {command[0]}") from error


def _stream(payload: dict[str, Any], media_type: str, *, label: str) -> dict[str, Any]:
    streams = [
        row
        for row in payload.get("streams", [])
        if row.get("codec_type") == media_type
    ]
    if len(streams) != 1:
        raise RuntimeError(
            f"{label} must contain exactly one {media_type} stream; "
            f"found {len(streams)}"
        )
    return streams[0]


def _duration_ms(payload: dict[str, Any], *, label: str) -> int:
    try:
        duration = float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"{label} has no valid container duration") from error
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError(f"{label} has an invalid container duration")
    return round(duration * 1000)


def _resolve_reference(
    value: object,
    *,
    manifest_path: Path,
    label: str,
) -> tuple[Path, dict[str, str]]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be an evidence-bound artifact reference")
    path_text = str(value.get("path", "")).strip()
    expected_sha256 = str(value.get("sha256", "")).strip().upper()
    locator = str(value.get("locator", "")).strip()
    if not path_text or not re.fullmatch(r"[0-9A-F]{64}", expected_sha256) or not locator:
        raise RuntimeError(f"{label} requires path, full SHA-256, and locator")
    path = Path(path_text)
    if not path.is_absolute():
        path = manifest_path.parent / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_sha256 = file_sha256(path)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"{label} SHA-256 mismatch")
    return path, {
        "path": str(path),
        "sha256": actual_sha256,
        "locator": locator,
    }


def _load_clean_visual_binding(
    *,
    manifest: dict[str, Any],
    manifest_path: Path,
    event: str,
    clean_visual: Path,
) -> dict[str, Any]:
    binding = manifest.get("clean_visual_master")
    if not isinstance(binding, dict):
        raise RuntimeError(
            "event manifest lacks evidence-bound clean_visual_master; an "
            "arbitrary same-shape MP4 cannot become a publishable master"
        )
    artifact_path, artifact_reference = _resolve_reference(
        binding.get("artifact"),
        manifest_path=manifest_path,
        label="clean_visual_master.artifact",
    )
    if artifact_path != clean_visual:
        raise RuntimeError(
            "--clean-visual does not match the evidence-bound artifact path"
        )
    report_path, report_reference = _resolve_reference(
        binding.get("render_manifest"),
        manifest_path=manifest_path,
        label="clean_visual_master.render_manifest",
    )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("clean visual render manifest is not valid JSON") from error
    fixed_checks = {
        "schema": CLEAN_VISUAL_RENDER_SCHEMA,
        "status": "passed",
        "publishable": True,
        "event": event,
        "output": str(clean_visual),
        "output_sha256": artifact_reference["sha256"],
    }
    for field, expected in fixed_checks.items():
        actual = report.get(field)
        if field.endswith("sha256"):
            actual = str(actual or "").upper()
        if actual != expected:
            raise RuntimeError(
                f"clean visual render manifest {field} mismatch: "
                f"actual={actual!r}, expected={expected!r}"
            )
    composition_sha256 = str(
        report.get("source_composition_contract_sha256", "")
    ).upper()
    if not re.fullmatch(r"[0-9A-F]{64}", composition_sha256):
        raise RuntimeError(
            "clean visual render manifest lacks source composition contract hash"
        )
    expected_projection = composition_contract_projection(manifest)
    expected_composition_sha256 = composition_contract_sha256(manifest)
    if composition_sha256 != expected_composition_sha256:
        raise RuntimeError(
            "clean visual source composition contract does not match the current "
            "event manifest"
        )
    if report.get("source_composition_contract") != expected_projection:
        raise RuntimeError(
            "clean visual render manifest composition projection does not match "
            "the current event manifest"
        )
    qa = report.get("qa")
    if not isinstance(qa, dict) or qa.get("status") != "passed" or qa.get(
        "errors"
    ) not in ([], None):
        raise RuntimeError("clean visual render manifest QA is not passed")
    return {
        "artifact": artifact_reference,
        "render_manifest": report_reference,
        "report": report,
    }


def _rate_parts(value: object, *, label: str) -> tuple[int, int]:
    try:
        numerator, denominator = (int(part) for part in str(value).split("/", 1))
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not a rational frame rate") from error
    if numerator <= 0 or denominator <= 0:
        raise RuntimeError(f"{label} is not a positive frame rate")
    return numerator, denominator


def _validate_clean_visual(
    *,
    clean_visual: Path,
    manifest: dict[str, Any],
    ffprobe: str,
    ffmpeg: str,
) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, object]]:
    payload = probe(clean_visual, ffprobe)
    video = _stream(payload, "video", label="clean visual")
    if str(video.get("codec_name", "")) != "h264":
        raise RuntimeError("clean visual must contain native H.264 video")
    expected_dimensions = manifest.get("native_dimensions")
    if not isinstance(expected_dimensions, dict):
        raise RuntimeError("event manifest lacks native_dimensions")
    actual_signature = (
        int(video.get("width", 0)),
        int(video.get("height", 0)),
        str(video.get("r_frame_rate", "")),
    )
    expected_signature = (
        int(expected_dimensions.get("width", 0)),
        int(expected_dimensions.get("height", 0)),
        str(manifest.get("native_frame_rate", "")),
    )
    if actual_signature != expected_signature:
        raise RuntimeError(
            f"clean visual signature {actual_signature} != manifest "
            f"{expected_signature}; scaling/upscaling is forbidden"
        )
    try:
        render_duration_ms = int(manifest["render_duration_ms"])
        start_ms = round(float(video["start_time"]) * 1000)
        stream_duration_ms = round(float(video["duration"]) * 1000)
        bit_rate = int(video["bit_rate"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            "clean visual lacks auditable start, duration, or bitrate"
        ) from error
    if render_duration_ms <= 0:
        raise RuntimeError("render_duration_ms must be positive")
    if abs(start_ms) > 1:
        raise RuntimeError(f"clean visual begins at {start_ms} ms instead of zero")
    if stream_duration_ms != render_duration_ms:
        raise RuntimeError(
            f"clean visual stream duration {stream_duration_ms} ms != "
            f"render_duration_ms {render_duration_ms} ms"
        )
    if _duration_ms(payload, label="clean visual") != render_duration_ms:
        raise RuntimeError("clean visual container does not cover the exact render duration")
    if bit_rate <= 0:
        raise RuntimeError("clean visual has no auditable positive video bitrate")
    rate_numerator, rate_denominator = _rate_parts(
        manifest["native_frame_rate"], label="native_frame_rate"
    )
    expected_frames = round(
        render_duration_ms * rate_numerator / rate_denominator / 1000
    )
    try:
        frame_count = int(video.get("nb_read_frames") or video["nb_frames"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("clean visual lacks an auditable frame count") from error
    if frame_count != expected_frames:
        raise RuntimeError(
            f"clean visual frame count {frame_count} != expected {expected_frames}"
        )
    timeline = probe_video_timeline(
        clean_visual,
        ffprobe,
        expected_duration_ms=render_duration_ms,
        expected_frame_rate=str(manifest["native_frame_rate"]),
        label="clean visual",
    )
    return payload, video, video_packet_hash(clean_visual, ffmpeg), timeline


def _validate_clean_visual_report(
    *,
    binding: dict[str, Any],
    video: dict[str, Any],
    video_packet_sha256: str,
    video_timeline: dict[str, object],
    render_duration_ms: int,
) -> None:
    report = binding["report"]
    checks = {
        "output_video_packet_sha256": video_packet_sha256,
        "output_video_timeline_sha256": str(video_timeline["timeline_sha256"]),
        "duration_ms": render_duration_ms,
        "video_encoding_signature": list(video_encoding_signature(video)),
    }
    for field, expected in checks.items():
        actual = report.get(field)
        if field.endswith("sha256"):
            actual = str(actual or "").upper()
            expected = str(expected).upper()
        if actual != expected:
            raise RuntimeError(
                f"clean visual render manifest {field} mismatch: "
                f"actual={actual!r}, expected={expected!r}"
            )


def _gain(value: object, unit: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{label} volume must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise RuntimeError(f"{label} volume must be finite")
    normalized_unit = str(unit)
    if normalized_unit not in SUPPORTED_VOLUME_UNITS:
        raise RuntimeError(
            f"{label} uses unsupported/ambiguous volume unit "
            f"{normalized_unit!r}; only linear and db are renderable"
        )
    if normalized_unit == "linear":
        if numeric < 0:
            raise RuntimeError(f"{label} linear gain must be non-negative")
        return numeric
    try:
        gain = math.pow(10.0, numeric / 20.0)
    except OverflowError as error:
        raise RuntimeError(f"{label} dB gain cannot be represented") from error
    if not math.isfinite(gain):
        raise RuntimeError(f"{label} dB gain cannot be represented")
    return gain


def _channel_filter(media: dict[str, Any], *, label: str) -> str:
    """Map only unambiguous mono/stereo source layouts to stereo."""

    try:
        channels = int(media["channels"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"{label} lacks an auditable channel count") from error
    layout = str(media.get("channel_layout", "")).strip()
    if channels == 1 and layout in {"", "mono"}:
        pan = "pan=stereo|c0=c0|c1=c0"
    elif channels == 2 and layout in {"", "stereo"}:
        pan = "pan=stereo|c0=c0|c1=c1"
    else:
        raise RuntimeError(
            f"{label} source layout channels={channels}, layout={layout!r} "
            "has no audited stereo mapping"
        )
    return (
        "aresample=48000,"
        f"{pan},"
        "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    )


def _validate_step_transitions(layer: dict[str, Any], *, label: str) -> list[dict[str, Any]]:
    if layer.get("loop") is not False:
        raise RuntimeError(
            f"{label} uses loop semantics; exact loop phase rendering is not "
            "implemented and will not be approximated"
        )
    transitions = layer.get("volume_transitions")
    if not isinstance(transitions, list) or not transitions:
        raise RuntimeError(f"{label} has no explicit volume transitions")
    audited: list[dict[str, Any]] = []
    previous_gain: float | None = None
    stopped = False
    for index, row in enumerate(transitions):
        kind = str(row.get("kind", ""))
        transition_label = f"{label} transition {index}"
        if kind == "fade":
            raise RuntimeError(
                f"{transition_label} is a fade without an audited interpolation "
                "curve; it will not be guessed"
            )
        if kind not in SUPPORTED_STEP_KINDS:
            raise RuntimeError(f"{transition_label} is not a supported step kind")
        if index == 0 and kind != "initial":
            raise RuntimeError(f"{label} must begin with an initial step")
        if index > 0 and kind == "initial":
            raise RuntimeError(f"{transition_label} repeats initial semantics")
        if stopped:
            raise RuntimeError(f"{transition_label} occurs after a stop step")
        gain = _gain(
            row.get("volume"), row.get("volume_unit"), label=transition_label
        )
        if previous_gain is not None:
            if kind == "duck" and gain > previous_gain:
                raise RuntimeError(f"{transition_label} raises gain instead of ducking")
            if kind == "restore" and gain < previous_gain:
                raise RuntimeError(
                    f"{transition_label} lowers gain instead of restoring it"
                )
        if kind == "stop":
            if not math.isclose(gain, 0.0, abs_tol=1e-12):
                raise RuntimeError(f"{transition_label} stop gain is not zero")
            stopped = True
        audited.append({**row, "render_gain": gain})
        previous_gain = gain
    return audited


def validate_supported_render_semantics(audio_contract: dict[str, Any]) -> None:
    """Reject contract features whose exact engine meaning is not implemented."""

    for index, row in enumerate(audio_contract["voice_se_timeline"]):
        _gain(row.get("volume"), row.get("volume_unit"), label=f"voice/SE {index}")
        _channel_filter(row["source_media"], label=f"voice/SE {index}")
        source_duration_ms = int(row["source_media"]["duration_ms"])
        if int(row["source_offset_ms"]) + int(row["duration_ms"]) > source_duration_ms:
            raise RuntimeError(f"voice/SE {index} would read past its source")
    profiles = audio_contract["profiles"]
    if set(profiles) != set(AUDIO_PROFILES):
        raise RuntimeError("validated contract must contain exactly with_bgm and no_bgm")
    if profiles[AUDIO_PROFILE_NO_BGM]["bgm_layers"]:
        raise RuntimeError("no_bgm must exclude every BGM layer")
    if not profiles[AUDIO_PROFILE_WITH_BGM]["bgm_layers"]:
        raise RuntimeError("with_bgm must contain evidenced BGM")
    for index, layer in enumerate(profiles[AUDIO_PROFILE_WITH_BGM]["bgm_layers"]):
        label = f"BGM layer {index}"
        _gain(layer.get("volume"), layer.get("volume_unit"), label=label)
        _channel_filter(layer["source"]["media"], label=label)
        _validate_step_transitions(layer, label=label)
        source_duration_ms = int(layer["source"]["media"]["duration_ms"])
        needed_ms = int(layer["source_offset_ms"]) + (
            int(layer["end_ms"]) - int(layer["start_ms"])
        )
        if needed_ms > source_duration_ms:
            raise RuntimeError(f"{label} would read past its non-loop source")


def _validate_output_encoding(
    raw_contract: dict[str, Any], *, requested_bitrate: int | None
) -> dict[str, Any]:
    value = raw_contract.get("output_encoding")
    if not isinstance(value, dict):
        raise RuntimeError(
            "audio_master_contract lacks an explicit output_encoding contract"
        )
    try:
        bit_rate = int(value["bit_rate"])
        sample_rate = int(value["sample_rate"])
        channels = int(value["channels"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("output_encoding has invalid numeric fields") from error
    actual = {
        "codec": str(value.get("codec", "")),
        "sample_rate": sample_rate,
        "channels": channels,
        "channel_layout": str(value.get("channel_layout", "")),
        "bit_rate": bit_rate,
    }
    expected_fixed = {
        "codec": "aac",
        "sample_rate": 48000,
        "channels": 2,
        "channel_layout": "stereo",
    }
    if {key: actual[key] for key in expected_fixed} != expected_fixed:
        raise RuntimeError(
            f"unsupported output_encoding {actual}; expected AAC 48 kHz stereo"
        )
    if bit_rate < 64_000 or bit_rate > 512_000:
        raise RuntimeError("output_encoding.bit_rate is outside 64k..512k")
    if requested_bitrate is not None and requested_bitrate != bit_rate:
        raise RuntimeError(
            f"--aac-bitrate {requested_bitrate} != evidence-bound target {bit_rate}"
        )
    return actual


def _collect_bound_artifacts(
    value: object,
    *,
    result: dict[Path, str],
    label: str,
) -> None:
    if isinstance(value, dict):
        path_text = str(value.get("path", "")).strip()
        sha256 = str(value.get("sha256", "")).strip().upper()
        if path_text and re.fullmatch(r"[0-9A-F]{64}", sha256):
            path = Path(path_text).resolve()
            previous = result.get(path)
            if previous is not None and previous != sha256:
                raise RuntimeError(f"{label} binds conflicting hashes for {path}")
            result[path] = sha256
        for key, child in value.items():
            _collect_bound_artifacts(
                child, result=result, label=f"{label}.{key}"
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _collect_bound_artifacts(
                child, result=result, label=f"{label}[{index}]"
            )


def _source_integrity_snapshot(
    *,
    event_manifest_path: Path,
    audio_contract: dict[str, Any],
    clean_visual_binding: dict[str, Any],
) -> dict[Path, str]:
    result = {event_manifest_path: file_sha256(event_manifest_path)}
    _collect_bound_artifacts(
        audio_contract, result=result, label="audio_master_contract"
    )
    _collect_bound_artifacts(
        clean_visual_binding, result=result, label="clean_visual_master"
    )
    _assert_source_integrity(result)
    return result


def _assert_source_integrity(snapshot: dict[Path, str]) -> None:
    for path, expected_sha256 in snapshot.items():
        if not path.is_file():
            raise RuntimeError(f"bound source disappeared during render: {path}")
        actual_sha256 = file_sha256(path)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"bound source changed during render: {path}; "
                f"expected={expected_sha256}, actual={actual_sha256}"
            )


def _number(value: float) -> str:
    if math.isclose(value, 0.0, abs_tol=1e-15):
        return "0"
    return format(value, ".17g")


def _profile_filter_graph(
    *, profile_contract: dict[str, Any], render_sample_count: int
) -> tuple[list[str], str]:
    """Return source paths and a deterministic 48 kHz stereo mix graph."""

    source_paths: list[str] = []
    filters: list[str] = [
        "anullsrc=r=48000:cl=stereo,"
        f"atrim=end_sample={render_sample_count},"
        "asetpts=PTS-STARTPTS[silence]"
    ]
    mix_labels = ["[silence]"]
    voice_rows = profile_contract["voice_se"]
    for index, row in enumerate(voice_rows):
        source_paths.append(str(row["path"]))
        input_index = len(source_paths)
        offset_sample = int(row["source_offset_ms"]) * SAMPLES_PER_MILLISECOND
        end_sample = offset_sample + int(row["duration_ms"]) * SAMPLES_PER_MILLISECOND
        delay_ms = int(row["start_ms"])
        gain = _gain(
            row["volume"], row["volume_unit"], label=f"voice/SE {index}"
        )
        output_label = f"voice_se_{index}"
        channel_filter = _channel_filter(
            row["source_media"], label=f"voice/SE {index}"
        )
        filters.append(
            f"[{input_index}:a:0]{channel_filter},"
            f"atrim=start_sample={offset_sample}:end_sample={end_sample},"
            "asetpts=PTS-STARTPTS,"
            f"volume={_number(gain)},adelay={delay_ms}:all=1[{output_label}]"
        )
        mix_labels.append(f"[{output_label}]")
    bgm_layers = profile_contract["bgm_layers"]
    for layer_index, layer in enumerate(bgm_layers):
        transitions = _validate_step_transitions(
            layer, label=f"BGM layer {layer_index}"
        )
        layer_start_ms = int(layer["start_ms"])
        layer_end_ms = int(layer["end_ms"])
        source_offset_ms = int(layer["source_offset_ms"])
        # Each constant-gain interval is trimmed on an exact 48-sample/ms
        # boundary.  FFmpeg's volume eval=frame would move a requested step to
        # an arbitrary audio-frame edge, so it is intentionally not used.
        for transition_index, transition in enumerate(transitions):
            interval_start_ms = int(transition["at_ms"])
            interval_end_ms = (
                int(transitions[transition_index + 1]["at_ms"])
                if transition_index + 1 < len(transitions)
                else layer_end_ms
            )
            if interval_end_ms == interval_start_ms:
                continue
            source_paths.append(str(layer["source"]["path"]))
            input_index = len(source_paths)
            relative_start_ms = interval_start_ms - layer_start_ms
            offset_sample = (
                source_offset_ms + relative_start_ms
            ) * SAMPLES_PER_MILLISECOND
            end_sample = offset_sample + (
                interval_end_ms - interval_start_ms
            ) * SAMPLES_PER_MILLISECOND
            output_label = f"bgm_{layer_index}_step_{transition_index}"
            channel_filter = _channel_filter(
                layer["source"]["media"], label=f"BGM layer {layer_index}"
            )
            filters.append(
                f"[{input_index}:a:0]{channel_filter},"
                f"atrim=start_sample={offset_sample}:end_sample={end_sample},"
                "asetpts=PTS-STARTPTS,"
                f"volume={_number(float(transition['render_gain']))},"
                f"adelay={interval_start_ms}:all=1[{output_label}]"
            )
            mix_labels.append(f"[{output_label}]")
    if len(mix_labels) == 1:
        filters.append("[silence]anull[aout]")
    else:
        filters.append(
            "".join(mix_labels)
            + f"amix=inputs={len(mix_labels)}:duration=longest:"
            "dropout_transition=0:normalize=0,"
            f"atrim=end_sample={render_sample_count},"
            "asetpts=PTS-STARTPTS[aout]"
        )
    return source_paths, ";".join(filters)


def _render_profile(
    *,
    clean_visual: Path,
    source_paths: list[str],
    filter_graph: str,
    output: Path,
    ffmpeg: str,
    aac_bitrate: int,
) -> None:
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(clean_visual)]
    for source in source_paths:
        command.extend(["-i", source])
    command.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            str(aac_bitrate),
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    _run(command)


def _audit_preencode_mix(
    *,
    clean_visual: Path,
    source_paths: list[str],
    filter_graph: str,
    render_sample_count: int,
    ffmpeg: str,
) -> dict[str, Any]:
    """Stream the float mix once, rejecting clipping and sample-count drift."""

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(clean_visual),
    ]
    for source in source_paths:
        command.extend(["-i", source])
    command.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "[aout]",
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "-",
        ]
    )
    digest = hashlib.sha256()
    peak = 0.0
    value_count = 0
    carry = b""
    with tempfile.TemporaryFile() as error_output:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=error_output,
            )
        except OSError as error:
            raise RuntimeError(f"unable to start media command: {ffmpeg}") from error
        assert process.stdout is not None
        with process.stdout:
            while True:
                block = process.stdout.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
                data = carry + block
                complete_size = len(data) - (len(data) % 4)
                values = array.array("f")
                values.frombytes(data[:complete_size])
                if values.itemsize != 4:
                    process.kill()
                    process.wait()
                    raise RuntimeError("host float representation is not 32-bit")
                for value in values:
                    if not math.isfinite(value):
                        process.kill()
                        process.wait()
                        raise RuntimeError(
                            "pre-encode mix contains non-finite samples"
                        )
                    peak = max(peak, abs(float(value)))
                value_count += len(values)
                carry = data[complete_size:]
        return_code = process.wait()
        error_output.seek(0)
        error_text = error_output.read().decode("utf-8", errors="replace")
    if return_code != 0:
        raise RuntimeError(f"pre-encode mix audit failed: {error_text.strip()}")
    if carry:
        raise RuntimeError("pre-encode PCM ended on a partial float sample")
    expected_values = render_sample_count * 2
    if value_count != expected_values:
        raise RuntimeError(
            f"pre-encode mix has {value_count // 2} samples/channel; "
            f"expected {expected_values // 2}"
        )
    if peak >= 1.0:
        raise RuntimeError(
            f"pre-encode linear sum peak {peak:.9f} would clip; no audited "
            "limiter/compressor law is available"
        )
    return {
        "sample_format": "f32le",
        "sample_rate": 48000,
        "channels": 2,
        "sample_count_per_channel": value_count // 2,
        "peak_absolute": peak,
        "pcm_sha256": digest.hexdigest().upper(),
        "mix_law": "linear_sum_no_normalization_no_limiter_peak_below_one",
    }


def _json_command(command: list[str], *, label: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise RuntimeError(f"unable to audit {label}") from error


def _audio_packet_timeline(
    *,
    output: Path,
    audio_stream: dict[str, Any],
    expected_samples: int,
    ffprobe: str,
) -> dict[str, Any]:
    try:
        time_base = Fraction(str(audio_stream["time_base"]))
    except (KeyError, ValueError, ZeroDivisionError) as error:
        raise RuntimeError("AAC stream has no valid time_base") from error
    if time_base != Fraction(1, 48000):
        raise RuntimeError(f"AAC time_base {time_base} != 1/48000")
    packet_payload = _json_command(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_packets",
            "-show_entries",
            "packet=pts,dts,duration:packet_side_data=side_data_type,skip_samples,discard_padding",
            "-of",
            "json",
            str(output),
        ],
        label=f"{output} AAC packets",
    )
    packets = packet_payload.get("packets")
    if not isinstance(packets, list) or not packets:
        raise RuntimeError("AAC output has no auditable packets")
    normalized_packets: list[dict[str, int]] = []
    previous_end: int | None = None
    for index, row in enumerate(packets):
        try:
            pts = int(row["pts"])
            dts = int(row["dts"])
            duration = int(row["duration"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(f"AAC packet {index} lacks integer timing") from error
        if duration <= 0 or dts != pts:
            raise RuntimeError(f"AAC packet {index} has invalid DTS/duration")
        if previous_end is not None and pts != previous_end:
            raise RuntimeError(
                f"AAC packet timeline gap/overlap at {index}: "
                f"pts={pts}, expected={previous_end}"
            )
        skip_samples = 0
        discard_padding = 0
        for side_data in row.get("side_data_list", []):
            if str(side_data.get("side_data_type", "")) == "Skip Samples":
                skip_samples = int(side_data.get("skip_samples", 0))
                discard_padding = int(side_data.get("discard_padding", 0))
        normalized_packets.append(
            {
                "pts": pts,
                "dts": dts,
                "duration": duration,
                "skip_samples": skip_samples,
                "discard_padding": discard_padding,
            }
        )
        previous_end = pts + duration
    first = normalized_packets[0]
    if first["pts"] + first["skip_samples"] != 0:
        raise RuntimeError(
            "AAC encoder priming is not exactly removed at presentation time zero"
        )
    if any(row["discard_padding"] < 0 for row in normalized_packets):
        raise RuntimeError("AAC packet has negative discard padding")
    if any(row["skip_samples"] for row in normalized_packets[1:]):
        raise RuntimeError("AAC has an unexpected non-initial skip_samples marker")
    if any(row["discard_padding"] for row in normalized_packets[:-1]):
        raise RuntimeError("AAC has an unexpected non-final discard_padding marker")
    assert previous_end is not None
    packet_presentation_end = (
        previous_end - normalized_packets[-1]["discard_padding"]
    )
    if packet_presentation_end != expected_samples:
        raise RuntimeError(
            "AAC packet presentation endpoint is not the exact render sample count"
        )

    frame_payload = _json_command(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_frames",
            "-show_entries",
            "frame=pts,duration,pkt_duration,nb_samples",
            "-of",
            "json",
            str(output),
        ],
        label=f"{output} decoded AAC frames",
    )
    frames = frame_payload.get("frames")
    if not isinstance(frames, list) or not frames:
        raise RuntimeError("AAC output has no auditable decoded frames")
    normalized_frames: list[dict[str, int]] = []
    expected_pts = 0
    for index, row in enumerate(frames):
        try:
            pts = int(row["pts"])
            nb_samples = int(row["nb_samples"])
            duration = int(row.get("duration", row.get("pkt_duration")))
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(f"AAC frame {index} lacks sample timing") from error
        if pts != expected_pts or nb_samples <= 0 or duration <= 0:
            raise RuntimeError(
                f"AAC decoded frame gap/overlap at {index}: "
                f"pts={pts}, expected={expected_pts}, samples={nb_samples}, "
                f"duration={duration}"
            )
        normalized_frames.append(
            {"pts": pts, "nb_samples": nb_samples, "duration": duration}
        )
        expected_pts += nb_samples
    raw_padding_samples = expected_pts - expected_samples
    if raw_padding_samples < 0 or raw_padding_samples >= 1024:
        raise RuntimeError(
            f"AAC decoded frame padding {raw_padding_samples} samples is invalid"
        )
    for row in normalized_frames[:-1]:
        if row["duration"] != row["nb_samples"]:
            raise RuntimeError("AAC has a shortened non-final decoded frame")
    final_frame = normalized_frames[-1]
    if final_frame["duration"] > final_frame["nb_samples"]:
        raise RuntimeError("AAC final presentation duration exceeds decoded samples")
    if sum(row["duration"] for row in normalized_frames) != expected_samples:
        raise RuntimeError("AAC decoded-frame presentation durations do not sum exactly")
    if final_frame["pts"] + final_frame["duration"] != expected_samples:
        raise RuntimeError("AAC final decoded-frame presentation endpoint is not exact")
    presentation_packets = [
        {
            "pts": row["pts"],
            "duration": row["duration"] - row["discard_padding"],
        }
        for row in normalized_packets
        if row["pts"] >= 0
    ]
    frame_intervals = [
        {"pts": row["pts"], "duration": row["duration"]}
        for row in normalized_frames
    ]
    if presentation_packets != frame_intervals:
        raise RuntimeError(
            "AAC non-negative packet intervals differ from decoded frame intervals"
        )
    timeline = {
        "schema": "magireco-aac-presentation-timeline-v1",
        "time_base": "1/48000",
        "expected_presentation_samples": expected_samples,
        "packet_count": len(normalized_packets),
        "first_packet_pts": first["pts"],
        "encoder_priming_samples": first["skip_samples"],
        "packet_raw_end_sample": previous_end,
        "packet_presentation_end_sample": packet_presentation_end,
        "decoded_frame_count": len(normalized_frames),
        "raw_decoded_sample_count_per_channel": expected_pts,
        "raw_decoder_padding_samples": raw_padding_samples,
        "packets": normalized_packets,
        "frames": normalized_frames,
    }
    timeline["timeline_sha256"] = canonical_sha256(timeline)
    return timeline


def _effective_decoded_pcm_audit(
    *, output: Path, expected_samples: int, ffmpeg: str
) -> dict[str, Any]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(output),
        "-map",
        "0:a:0",
        "-af",
        f"atrim=end_sample={expected_samples},asetpts=PTS-STARTPTS",
        "-c:a",
        "pcm_s16le",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-f",
        "s16le",
        "-",
    ]
    digest = hashlib.sha256()
    byte_count = 0
    with tempfile.TemporaryFile() as error_output:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=error_output,
            )
        except OSError as error:
            raise RuntimeError(f"unable to start media command: {ffmpeg}") from error
        assert process.stdout is not None
        with process.stdout:
            for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
                digest.update(block)
                byte_count += len(block)
        return_code = process.wait()
        error_output.seek(0)
        error_text = error_output.read().decode("utf-8", errors="replace")
    if return_code != 0:
        raise RuntimeError(f"effective PCM audit failed: {error_text.strip()}")
    expected_bytes = expected_samples * 2 * 2
    if byte_count != expected_bytes:
        raise RuntimeError(
            f"effective decoded PCM has {byte_count} bytes; expected {expected_bytes}"
        )
    return {
        "sample_format": "s16le",
        "sample_rate": 48000,
        "channels": 2,
        "sample_count_per_channel": expected_samples,
        "byte_count": byte_count,
        "pcm_sha256": digest.hexdigest().upper(),
    }


def _qa_output(
    *,
    output: Path,
    expected_duration_ms: int,
    expected_audio_samples: int,
    expected_frame_rate: str,
    clean_video: dict[str, Any],
    clean_video_packet_sha256: str,
    clean_video_timeline_sha256: str,
    target_audio_bit_rate: int,
    ffprobe: str,
    ffmpeg: str,
) -> dict[str, Any]:
    payload = probe(output, ffprobe)
    video = _stream(payload, "video", label=str(output))
    audio = _stream(payload, "audio", label=str(output))
    if _duration_ms(payload, label=str(output)) != expected_duration_ms:
        raise RuntimeError(f"{output} does not cover the exact render duration")
    for stream, stream_label in ((video, "video"), (audio, "audio")):
        try:
            start_ms = round(float(stream["start_time"]) * 1000)
            duration_ms = round(float(stream["duration"]) * 1000)
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(f"{output} {stream_label} lacks timing") from error
        if abs(start_ms) > 1 or duration_ms != expected_duration_ms:
            raise RuntimeError(
                f"{output} {stream_label} coverage is start={start_ms} ms, "
                f"duration={duration_ms} ms"
            )
    validate_native_audio_signature(audio, label=str(output))
    try:
        actual_audio_bit_rate = int(audio["bit_rate"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"{output} lacks an auditable AAC bitrate") from error
    bit_rate_tolerance = max(2_000, round(target_audio_bit_rate * 0.10))
    if abs(actual_audio_bit_rate - target_audio_bit_rate) > bit_rate_tolerance:
        raise RuntimeError(
            f"{output} AAC bitrate {actual_audio_bit_rate} is outside target "
            f"{target_audio_bit_rate} +/- {bit_rate_tolerance}"
        )
    if video_encoding_signature(video) != video_encoding_signature(clean_video):
        raise RuntimeError(f"{output} changed the native video encoding signature")
    output_video_packet_sha256 = video_packet_hash(output, ffmpeg)
    if output_video_packet_sha256 != clean_video_packet_sha256:
        raise RuntimeError(f"{output} changed original H.264 video packets")
    video_timeline = probe_video_timeline(
        output,
        ffprobe,
        expected_duration_ms=expected_duration_ms,
        expected_frame_rate=expected_frame_rate,
        label=f"{output} video",
    )
    if video_timeline["timeline_sha256"] != clean_video_timeline_sha256:
        raise RuntimeError(f"{output} changed the original video presentation timeline")
    audio_timeline = _audio_packet_timeline(
        output=output,
        audio_stream=audio,
        expected_samples=expected_audio_samples,
        ffprobe=ffprobe,
    )
    effective_pcm = _effective_decoded_pcm_audit(
        output=output,
        expected_samples=expected_audio_samples,
        ffmpeg=ffmpeg,
    )
    return {
        "probe": payload,
        "video": video,
        "audio": audio,
        "output_sha256": file_sha256(output),
        "output_audio_packet_sha256": audio_hash(output, ffmpeg),
        "output_decoded_pcm_sha256": decoded_pcm_hash(output, ffmpeg),
        "output_video_packet_sha256": output_video_packet_sha256,
        "output_video_timeline_sha256": video_timeline["timeline_sha256"],
        "output_video_timeline": video_timeline,
        "output_audio_timeline_sha256": audio_timeline["timeline_sha256"],
        "output_audio_timeline": audio_timeline,
        "output_effective_decoded_pcm": effective_pcm,
        "actual_audio_bit_rate": actual_audio_bit_rate,
    }


def build_audio_base_masters(
    *,
    event_manifest_path: Path,
    clean_visual_path: Path,
    out_root: Path,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    aac_bitrate: int | None = None,
) -> dict[str, Any]:
    """Build exactly ``with_bgm`` and ``no_bgm`` base masters and sidecars."""

    event_manifest_path = event_manifest_path.resolve()
    clean_visual_path = clean_visual_path.resolve()
    out_root = out_root.resolve()
    if not event_manifest_path.is_file():
        raise FileNotFoundError(event_manifest_path)
    if not clean_visual_path.is_file():
        raise FileNotFoundError(clean_visual_path)
    if aac_bitrate is not None and aac_bitrate <= 0:
        raise ValueError("aac_bitrate must be positive")
    try:
        manifest = json.loads(event_manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("event manifest is not valid UTF-8 JSON") from error
    event = str(manifest.get("event", "")).strip()
    if not EVENT_RE.fullmatch(event) or event in {".", ".."}:
        raise RuntimeError(f"unsafe or blank event identifier: {event!r}")
    clean_visual_binding = _load_clean_visual_binding(
        manifest=manifest,
        manifest_path=event_manifest_path,
        event=event,
        clean_visual=clean_visual_path,
    )
    raw_contract = manifest.get("audio_master_contract")
    raw_profiles = (
        raw_contract.get("profiles") if isinstance(raw_contract, dict) else None
    )
    if not isinstance(raw_profiles, dict) or set(raw_profiles) != set(AUDIO_PROFILES):
        raise RuntimeError(
            "event manifest must declare exactly with_bgm and no_bgm profiles"
        )
    assert isinstance(raw_contract, dict)
    output_encoding = _validate_output_encoding(
        raw_contract, requested_bitrate=aac_bitrate
    )
    target_aac_bitrate = int(output_encoding["bit_rate"])
    audio_contract = validate_audio_master_contract(
        manifest,
        requested_profiles=AUDIO_PROFILES,
        manifest_path=event_manifest_path,
        media_inspector=lambda path: inspect_audio_asset(path, ffprobe=ffprobe),
    )
    validate_supported_render_semantics(audio_contract)
    render_duration_ms = int(manifest["render_duration_ms"])
    render_audio_sample_count = presentation_sample_count(manifest)
    (
        clean_probe,
        clean_video,
        clean_video_packet_sha256,
        clean_video_timeline,
    ) = _validate_clean_visual(
        clean_visual=clean_visual_path,
        manifest=manifest,
        ffprobe=ffprobe,
        ffmpeg=ffmpeg,
    )
    _validate_clean_visual_report(
        binding=clean_visual_binding,
        video=clean_video,
        video_packet_sha256=clean_video_packet_sha256,
        video_timeline=clean_video_timeline,
        render_duration_ms=render_duration_ms,
    )
    source_integrity = _source_integrity_snapshot(
        event_manifest_path=event_manifest_path,
        audio_contract=audio_contract,
        clean_visual_binding=clean_visual_binding,
    )
    ready_path = (
        out_root / "transactions" / f"{event}.audio_base_masters.ready.json"
    )
    final_paths = {
        profile: {
            "video": out_root / profile / f"{event}.mp4",
            "manifest": out_root / profile / f"{event}.base_master.json",
        }
        for profile in AUDIO_PROFILES
    }
    existing = [
        path
        for paths in final_paths.values()
        for path in paths.values()
        if _path_lexists(path)
    ]
    if _path_lexists(ready_path):
        existing.append(ready_path)
    if existing:
        raise FileExistsError(f"refusing to overwrite output(s): {existing}")
    out_root.mkdir(parents=True, exist_ok=True)
    event_contract_sha256 = event_contract_projection_sha256(event_manifest_path)
    qa_by_profile: dict[str, dict[str, Any]] = {}
    preencode_by_profile: dict[str, dict[str, Any]] = {}
    filter_graph_by_profile: dict[str, str] = {}
    sidecars: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(
        prefix=f".{event}.audio-base-master-", dir=out_root
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        for profile in AUDIO_PROFILES:
            profile_contract = audio_contract["profiles"][profile]
            source_layers = {
                "voice_se": audio_contract["voice_se_timeline"],
                "bgm_layers": profile_contract["bgm_layers"],
            }
            stage_video = temporary_root / f"{profile}.mp4"
            source_paths, filter_graph = _profile_filter_graph(
                profile_contract=source_layers,
                render_sample_count=render_audio_sample_count,
            )
            filter_graph_by_profile[profile] = filter_graph
            preencode_by_profile[profile] = _audit_preencode_mix(
                clean_visual=clean_visual_path,
                source_paths=source_paths,
                filter_graph=filter_graph,
                render_sample_count=render_audio_sample_count,
                ffmpeg=ffmpeg,
            )
            _render_profile(
                clean_visual=clean_visual_path,
                source_paths=source_paths,
                filter_graph=filter_graph,
                output=stage_video,
                ffmpeg=ffmpeg,
                aac_bitrate=target_aac_bitrate,
            )
            qa_by_profile[profile] = _qa_output(
                output=stage_video,
                expected_duration_ms=render_duration_ms,
                expected_audio_samples=render_audio_sample_count,
                expected_frame_rate=str(manifest["native_frame_rate"]),
                clean_video=clean_video,
                clean_video_packet_sha256=clean_video_packet_sha256,
                clean_video_timeline_sha256=str(
                    clean_video_timeline["timeline_sha256"]
                ),
                target_audio_bit_rate=target_aac_bitrate,
                ffprobe=ffprobe,
                ffmpeg=ffmpeg,
            )
            qa = qa_by_profile[profile]
            final_video = final_paths[profile]["video"]
            sidecars[profile] = {
                "schema": BASE_MASTER_SCHEMA,
                "status": "passed",
                "publishable": True,
                "event": event,
                "audio_profile": profile,
                "source_event_contract_sha256": event_contract_sha256,
                "voice_se_timeline_sha256": profile_contract[
                    "voice_se_timeline_sha256"
                ],
                "audio_timeline_sha256": profile_contract[
                    "audio_timeline_sha256"
                ],
                "source_layers_sha256": canonical_sha256(source_layers),
                "output": str(final_video),
                "output_sha256": qa["output_sha256"],
                "output_audio_packet_sha256": qa[
                    "output_audio_packet_sha256"
                ],
                "output_decoded_pcm_sha256": qa[
                    "output_decoded_pcm_sha256"
                ],
                "output_raw_padded_decoded_pcm_sha256": qa[
                    "output_decoded_pcm_sha256"
                ],
                "output_video_packet_sha256": qa[
                    "output_video_packet_sha256"
                ],
                "output_video_timeline_sha256": qa[
                    "output_video_timeline_sha256"
                ],
                "output_audio_timeline_sha256": qa[
                    "output_audio_timeline_sha256"
                ],
                "output_effective_decoded_pcm_sha256": qa[
                    "output_effective_decoded_pcm"
                ]["pcm_sha256"],
                "duration_ms": render_duration_ms,
                "presentation_sample_count": render_audio_sample_count,
                "audio_encoding_signature": list(
                    audio_encoding_signature(qa["audio"])
                ),
                "video_encoding_signature": list(
                    video_encoding_signature(qa["video"])
                ),
                "source_layers": source_layers,
                "source_clean_visual": {
                    "artifact": clean_visual_binding["artifact"],
                    "render_manifest": clean_visual_binding[
                        "render_manifest"
                    ],
                    "video_packet_sha256": clean_video_packet_sha256,
                    "video_timeline_sha256": clean_video_timeline[
                        "timeline_sha256"
                    ],
                    "video_encoding_signature": list(
                        video_encoding_signature(clean_video)
                    ),
                },
                "render_method": {
                    "video": "stream_copy_no_scale",
                    "audio": "linear_sum_no_normalization_aac_48000_stereo",
                    "output_encoding_contract": output_encoding,
                    "actual_audio_bit_rate": qa["actual_audio_bit_rate"],
                    "filter_graph": filter_graph_by_profile[profile],
                },
                "preencode_mix_audit": preencode_by_profile[profile],
                "audio_presentation_timeline": qa["output_audio_timeline"],
                "effective_decoded_pcm_audit": qa[
                    "output_effective_decoded_pcm"
                ],
                "qa": {
                    "status": "passed",
                    "errors": [],
                    "checks": {
                        "exact_render_duration": True,
                        "exact_aac_packet_sample_timeline": True,
                        "exact_effective_decoded_sample_count": True,
                        "unclipped_linear_mix_peak_below_one": True,
                        "native_video_packets_preserved": True,
                        "aac_48000_stereo": True,
                        "voice_se_contract_shared": True,
                        "bgm_layer_count": len(profile_contract["bgm_layers"]),
                        "no_bgm_excludes_bgm": (
                            profile != AUDIO_PROFILE_NO_BGM
                            or not profile_contract["bgm_layers"]
                        ),
                    },
                },
            }
        validate_audio_master_distinction(
            {
                profile: qa_by_profile[profile]["output_audio_packet_sha256"]
                for profile in AUDIO_PROFILES
            },
            {
                profile: qa_by_profile[profile]["output_decoded_pcm_sha256"]
                for profile in AUDIO_PROFILES
            },
        )
        if len(
            {
                qa_by_profile[profile]["output_effective_decoded_pcm"][
                    "pcm_sha256"
                ]
                for profile in AUDIO_PROFILES
            }
        ) != 2:
            raise RuntimeError(
                "with_bgm/no_bgm effective presentation PCM is identical"
            )
        if len(
            {
                qa_by_profile[profile]["output_video_packet_sha256"]
                for profile in AUDIO_PROFILES
            }
        ) != 1:
            raise RuntimeError("the two independently rendered masters differ in video packets")
        if len(
            {
                qa_by_profile[profile]["output_video_timeline_sha256"]
                for profile in AUDIO_PROFILES
            }
        ) != 1:
            raise RuntimeError(
                "the two independently rendered masters differ in video timeline"
            )
        ready_payload = {
            "schema": READY_SCHEMA,
            "status": "ready",
            "publishable": True,
            "event": event,
            "source_event_contract_sha256": event_contract_sha256,
            "profiles": {
                profile: {
                    "video": str(final_paths[profile]["video"]),
                    "video_sha256": qa_by_profile[profile]["output_sha256"],
                    "base_master_manifest": str(
                        final_paths[profile]["manifest"]
                    ),
                    "audio_timeline_sha256": sidecars[profile][
                        "audio_timeline_sha256"
                    ],
                }
                for profile in AUDIO_PROFILES
            },
            "publication_rule": (
                "both profile videos and both base-master sidecars are "
                "non-publishable unless this marker exists with this SHA-256"
            ),
        }
        stage_ready = temporary_root / "transaction.ready.json"
        stage_ready.write_text(
            json.dumps(ready_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        ready_reference = {
            "path": str(ready_path),
            "sha256": file_sha256(stage_ready),
            "locator": f"complete two-profile audio transaction for {event}",
        }
        for profile in AUDIO_PROFILES:
            sidecars[profile]["transaction_ready_marker"] = ready_reference
            sidecars[profile]["source_integrity"] = {
                str(path): sha256
                for path, sha256 in sorted(
                    source_integrity.items(), key=lambda row: str(row[0])
                )
            }
            sidecars[profile]["source_integrity_sha256"] = canonical_sha256(
                sidecars[profile]["source_integrity"]
            )
        # The final read happens after all media commands and immediately
        # before any publishable byte is promoted out of staging.
        _assert_source_integrity(source_integrity)
        for profile in AUDIO_PROFILES:
            stage_manifest = temporary_root / f"{profile}.base_master.json"
            stage_manifest.write_text(
                json.dumps(sidecars[profile], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        _promote_audio_base_master_transaction(
            staged_artifacts=[
                *[
                    (
                        temporary_root / f"{profile}.mp4",
                        final_paths[profile]["video"],
                    )
                    for profile in AUDIO_PROFILES
                ],
                *[
                    (
                        temporary_root / f"{profile}.base_master.json",
                        final_paths[profile]["manifest"],
                    )
                    for profile in AUDIO_PROFILES
                ],
            ],
            staged_ready=stage_ready,
            final_ready=ready_path,
            lock_path=(
                out_root
                / "transactions"
                / f".{event}.audio_base_masters.promotion.lock"
            ),
        )
    result_profiles: dict[str, Any] = {}
    for profile in AUDIO_PROFILES:
        sidecar_path = final_paths[profile]["manifest"]
        result_profiles[profile] = {
            "video": str(final_paths[profile]["video"]),
            "video_sha256": file_sha256(final_paths[profile]["video"]),
            "base_master_manifest": {
                "path": str(sidecar_path),
                "sha256": file_sha256(sidecar_path),
                "locator": f"complete {profile} base master for {event}",
            },
        }
    return {
        "schema": "magireco-audio-base-master-build-result-v1",
        "status": "passed",
        "event": event,
        "source_event_contract_sha256": event_contract_sha256,
        "source_clean_visual": {
            "artifact": clean_visual_binding["artifact"],
            "render_manifest": clean_visual_binding["render_manifest"],
            "video_packet_sha256": clean_video_packet_sha256,
            "video_timeline_sha256": clean_video_timeline["timeline_sha256"],
            "probe": clean_probe,
        },
        "transaction_ready_marker": {
            "path": str(ready_path),
            "sha256": file_sha256(ready_path),
            "locator": f"complete two-profile audio transaction for {event}",
        },
        "profiles": result_profiles,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_audio_base_masters(
        event_manifest_path=Path(args.event_manifest),
        clean_visual_path=Path(args.clean_visual),
        out_root=Path(args.out_root),
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
        aac_bitrate=args.aac_bitrate,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
