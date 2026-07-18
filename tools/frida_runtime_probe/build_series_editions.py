#!/usr/bin/env python3
"""Build auditable stream-copy series editions from QA-passed event pairs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

try:
    from .output_path_contract import (
        resolve_output_child,
        validate_output_identifier,
    )
    from .subtitle_edition_contract import (
        AUDIO_PROFILES,
        LEGACY_AUDIO_PROFILE,
        SUPPORTED_EDITIONS,
        normalize_render_edition_matrix,
        normalize_requested_audio_profiles,
        normalize_requested_editions,
    )
except ImportError:  # direct script execution
    from output_path_contract import (  # type: ignore
        resolve_output_child,
        validate_output_identifier,
    )
    from subtitle_edition_contract import (  # type: ignore
        AUDIO_PROFILES,
        LEGACY_AUDIO_PROFILE,
        SUPPORTED_EDITIONS,
        normalize_render_edition_matrix,
        normalize_requested_audio_profiles,
        normalize_requested_editions,
    )


SRT_BLOCK_RE = re.compile(
    r"(?:^|\n)\s*\d+\s*\n"
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(?P<text>.*?)(?=\n\s*\d+\s*\n\d{2}:|\Z)",
    re.DOTALL,
)
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
SERIES_ORDER_SCHEMA = "magireco-series-order-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", action="append", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--series", action="append", required=True)
    parser.add_argument(
        "--preserve-event-separately",
        action="append",
        default=[],
        help=(
            "QA-passed event intentionally omitted from the long stream-copy edition "
            "because its native stream signature differs; repeat as needed"
        ),
    )
    parser.add_argument("--production-manifest-root", default="")
    parser.add_argument(
        "--order-manifest",
        action="append",
        default=[],
        help=(
            "evidence-bound narrative/runtime order JSON; repeat once per series"
        ),
    )
    parser.add_argument(
        "--require-complete-family",
        action="store_true",
        default=True,
        help="deprecated compatibility spelling; completeness is the default",
    )
    parser.add_argument(
        "--review-only",
        action="store_true",
        help=(
            "allow incomplete, legacy, or naturally sorted review output; the "
            "result is explicitly non-publishable"
        ),
    )
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--edition",
        action="append",
        choices=SUPPORTED_EDITIONS,
        dest="editions",
        help="repeat to build none/ja/zh; default remains legacy none+ja",
    )
    parser.add_argument(
        "--audio-profile",
        action="append",
        choices=AUDIO_PROFILES,
        dest="audio_profiles",
    )
    parser.add_argument("--legacy-two-edition", action="store_true")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def event_sort_key(event: str) -> tuple:
    return tuple(
        int(token) if token.isdigit() else token.casefold()
        for token in re.split(r"(\d+)", event)
    )


def srt_time_ms(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int(milliseconds)
    )


def format_srt_time(value_ms: int) -> str:
    value_ms = max(0, value_ms)
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def shifted_srt_cues(text: str, offset_ms: int) -> list[dict]:
    cues: list[dict] = []
    normalized = text.replace("\r\n", "\n").strip()
    for match in SRT_BLOCK_RE.finditer(normalized):
        cues.append(
            {
                "start_ms": srt_time_ms(match.group("start")) + offset_ms,
                "end_ms": srt_time_ms(match.group("end")) + offset_ms,
                "text": match.group("text").strip(),
            }
        )
    return cues


def write_srt(path: Path, cues: list[dict]) -> None:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_srt_time(int(cue['start_ms']))} --> "
            f"{format_srt_time(int(cue['end_ms']))}\n"
            f"{cue['text']}"
        )
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,profile,level,width,height,pix_fmt,"
            "r_frame_rate,avg_frame_rate,time_base,sample_rate,channels,channel_layout,duration:"
            "format=duration,size,bit_rate",
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


def stream_signature(payload: dict) -> dict:
    video = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "video"
    )
    audio = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "audio"
    )
    return {
        "video": {
            key: video.get(key, "")
            for key in (
                "codec_name",
                "profile",
                "level",
                "width",
                "height",
                "pix_fmt",
                "r_frame_rate",
                "time_base",
            )
        },
        "audio": {
            key: audio.get(key, "")
            for key in (
                "codec_name",
                "sample_rate",
                "channels",
                "channel_layout",
                "time_base",
            )
        },
    }


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


def ffconcat_line(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{value}'"


def concat_copy(
    sources: list[Path],
    list_path: Path,
    output_path: Path,
    ffmpeg: str,
    overwrite: bool,
) -> None:
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(path) for path in sources)
        + "\n",
        encoding="utf-8",
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def load_qa_audit(root: Path) -> dict[str, dict]:
    path = root / "full_qa_audit.csv"
    if not path.is_file():
        raise FileNotFoundError(f"QA audit is required: {path}")
    report_sha256 = file_sha256(path)
    result: dict[str, dict] = {}
    for line_number, row in enumerate(read_csv(path), start=2):
        event = str(row.get("event", "")).strip()
        if not event:
            raise ValueError(f"QA audit has no event at {path}:{line_number}")
        if event in result:
            raise ValueError(f"duplicate QA event {event}: {path}:{line_number}")
        result[event] = {
            "status": str(row.get("status", "")).strip(),
            "report_path": str(path.resolve()),
            "report_sha256": report_sha256,
            "row_locator": f"CSV row {line_number}",
            "row_sha256": canonical_sha256(row),
            "row": row,
        }
    return result


def load_qa_status(root: Path) -> dict[str, str]:
    """Compatibility view used by older callers and tests."""

    return {
        event: row["status"] for event, row in load_qa_audit(root).items()
    }


def _resolve_evidence_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def load_series_order_manifest(path: Path, *, expected_series: str) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"series order manifest is required: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SERIES_ORDER_SCHEMA:
        raise ValueError(
            f"series order manifest schema must be {SERIES_ORDER_SCHEMA!r}: {path}"
        )
    if str(payload.get("series", "")).strip() != expected_series:
        raise ValueError(f"series order manifest series mismatch: {path}")
    ordered_events = payload.get("ordered_events")
    if not isinstance(ordered_events, list) or not ordered_events:
        raise ValueError(f"series order manifest has no ordered_events: {path}")
    ordered_events = [str(event).strip() for event in ordered_events]
    if any(not event for event in ordered_events):
        raise ValueError(f"series order manifest has an empty event: {path}")
    if len(set(ordered_events)) != len(ordered_events):
        raise ValueError(f"series order manifest has duplicate events: {path}")
    if any(not event.startswith(f"{expected_series}_") for event in ordered_events):
        raise ValueError(f"series order manifest contains another family: {path}")
    if payload.get("complete") is not True:
        raise ValueError(
            f"series order manifest must explicitly declare complete=true: {path}"
        )
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError(f"series order manifest has no evidence object: {path}")
    kind = str(evidence.get("kind", "")).strip()
    if not kind:
        raise ValueError(f"series order evidence.kind is required: {path}")
    fields = evidence.get("fields")
    required_fields = {"ordered_events", "family_completeness"}
    if not isinstance(fields, list) or not required_fields.issubset(
        {str(field) for field in fields}
    ):
        raise ValueError(
            "series order evidence.fields must cover ordered_events and "
            f"family_completeness: {path}"
        )
    references = evidence.get("references")
    if not isinstance(references, list) or not references:
        raise ValueError(f"series order evidence.references is required: {path}")
    audited_references = []
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            raise ValueError(f"series order evidence reference {index} is invalid")
        evidence_path = _resolve_evidence_path(
            str(reference.get("path", "")).strip(), path
        )
        if not evidence_path.is_file():
            raise FileNotFoundError(
                f"series order evidence reference does not exist: {evidence_path}"
            )
        declared_sha256 = str(reference.get("sha256", "")).strip().upper()
        if not SHA256_RE.fullmatch(declared_sha256):
            raise ValueError(
                f"series order evidence reference {index} has no full SHA-256"
            )
        actual_sha256 = file_sha256(evidence_path)
        if declared_sha256 != actual_sha256:
            raise ValueError(
                f"series order evidence reference SHA-256 mismatch: {evidence_path}"
            )
        locator = str(reference.get("locator", "")).strip()
        if not locator:
            raise ValueError(
                f"series order evidence reference {index} has no locator"
            )
        audited_references.append(
            {
                "path": str(evidence_path),
                "sha256": actual_sha256,
                "locator": locator,
            }
        )
    return {
        "schema": SERIES_ORDER_SCHEMA,
        "series": expected_series,
        "complete": True,
        "ordered_events": ordered_events,
        "evidence": {
            "kind": kind,
            "fields": sorted({str(field) for field in fields}),
            "references": audited_references,
        },
        "manifest_path": str(path),
        "manifest_sha256": file_sha256(path),
        "manifest_locator": "ordered_events",
    }


def resolve_manifest_file(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def discover_events(
    input_roots: list[Path], *, allow_legacy: bool = False
) -> dict[str, dict]:
    events: dict[str, dict] = {}
    for root in input_roots:
        qa_audit = load_qa_audit(root)
        for render_path in sorted(root.glob("*/render_manifest.json")):
            payload = json.loads(render_path.read_text(encoding="utf-8"))
            event = str(payload.get("event", "")).strip()
            if not event:
                raise ValueError(f"render manifest has no event: {render_path}")
            qa_binding = qa_audit.get(event)
            if qa_binding is None or qa_binding["status"] != "passed":
                continue
            if event in events:
                raise ValueError(
                    f"duplicate QA-passed event {event}: "
                    f"{events[event]['render_manifest_path']} and {render_path}"
                )
            normalized_matrix = normalize_render_edition_matrix(
                payload, allow_legacy=allow_legacy
            )
            edition_matrix: dict[str, dict] = {}
            for profile, profile_row in normalized_matrix.items():
                edition_paths: dict[str, dict[str, Path | str]] = {}
                for edition, edition_row in profile_row["editions"].items():
                    video_path = resolve_manifest_file(
                        edition_row["video"], render_path
                    )
                    if not video_path.is_file():
                        raise FileNotFoundError(
                            f"{event} missing {profile}.{edition} video: {video_path}"
                        )
                    subtitle_value = edition_row.get("subtitles", "")
                    subtitle_path = (
                        resolve_manifest_file(subtitle_value, render_path)
                        if subtitle_value
                        else None
                    )
                    if edition != "none" and (
                        subtitle_path is None or not subtitle_path.is_file()
                    ):
                        raise FileNotFoundError(
                            f"{event} missing {profile}.{edition} subtitles: "
                            f"{subtitle_path}"
                        )
                    edition_paths[edition] = {
                        "language": edition_row.get("language", edition),
                        "video_path": video_path,
                        "subtitle_path": subtitle_path or "",
                    }
                edition_matrix[profile] = {
                    "audio_sha256": profile_row.get("audio_sha256", ""),
                    "editions": edition_paths,
                }
            legacy_editions = edition_matrix.get(
                LEGACY_AUDIO_PROFILE, {}
            ).get("editions", {})
            none_path = legacy_editions.get("none", {}).get("video_path", "")
            ja_row = legacy_editions.get("ja", {})
            events[event] = {
                "event": event,
                "render_manifest": payload,
                "render_manifest_path": str(render_path.resolve()),
                "edition_matrix": edition_matrix,
                "editions": legacy_editions,
                "without_path": none_path,
                "with_path": ja_row.get("video_path", ""),
                "subtitle_path": ja_row.get("subtitle_path", ""),
                "qa_root": str(root.resolve()),
                "qa_binding": qa_binding,
            }
    return events


def family_state(series: str, manifest_root: Path | None) -> dict:
    if manifest_root is None:
        return {}
    event_dir = manifest_root / "events"
    if not event_dir.is_dir():
        event_dir = manifest_root
    rows = []
    seen_events: set[str] = set()
    for path in sorted(event_dir.glob(f"{series}_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        event = str(payload.get("event", path.stem)).strip()
        if not event.startswith(f"{series}_"):
            raise ValueError(
                f"production manifest belongs to another family: {path} -> {event}"
            )
        if event in seen_events:
            raise ValueError(f"duplicate production manifest event {event}")
        seen_events.add(event)
        rows.append(
            {
                "event": event,
                "ready": bool(payload.get("quality_gates", {}).get("ready")),
                "errors": payload.get("quality_gates", {}).get("errors", []),
            }
        )
    return {
        "production_manifest_root": str(manifest_root.resolve()),
        "known_family_events": len(rows),
        "ready_family_events": sum(row["ready"] for row in rows),
        "not_ready_family_events": [row for row in rows if not row["ready"]],
        "ready_event_names": [row["event"] for row in rows if row["ready"]],
    }


def series_edition_paths(
    series_dir: Path,
    series: str,
    edition: str,
    audio_profile: str = LEGACY_AUDIO_PROFILE,
) -> tuple[Path, Path | None]:
    if audio_profile != LEGACY_AUDIO_PROFILE:
        profile_dir = series_dir / audio_profile
        if edition == "none":
            return (
                profile_dir / "without_subtitles" / f"{series}__series.mp4",
                None,
            )
        video_dir = "with_subtitles" if edition == "ja" else f"with_subtitles_{edition}"
        video_suffix = "subtitles" if edition == "ja" else f"{edition}_subtitles"
        return (
            profile_dir / video_dir / f"{series}__series__{video_suffix}.mp4",
            series_dir / "subtitles" / edition / f"{series}__series.{edition}.srt",
        )
    if edition == "none":
        return series_dir / "without_subtitles" / f"{series}__series.mp4", None
    if edition == "ja":
        return (
            series_dir / "with_subtitles" / f"{series}__series__subtitles.mp4",
            series_dir / "subtitles" / f"{series}__series.srt",
        )
    return (
        series_dir
        / f"with_subtitles_{edition}"
        / f"{series}__series__{edition}_subtitles.mp4",
        series_dir / f"subtitles_{edition}" / f"{series}__series.{edition}.srt",
    )


def candidate_edition(row: dict, profile: str, edition: str) -> dict:
    return row["edition_matrix"][profile]["editions"][edition]


def validate_qa_binding(row: dict) -> dict:
    event = row["event"]
    original = row.get("qa_binding")
    if not isinstance(original, dict):
        raise ValueError(f"{event} has no bound QA provenance")
    refreshed = load_qa_audit(Path(row["qa_root"])).get(event)
    if refreshed is None or refreshed.get("status") != "passed":
        raise ValueError(f"{event} is no longer passed in its bound QA report")
    for field in ("report_path", "report_sha256", "row_locator", "row_sha256"):
        if refreshed.get(field) != original.get(field):
            raise ValueError(f"{event} QA provenance changed after discovery: {field}")
    return {
        "path": refreshed["report_path"],
        "sha256": refreshed["report_sha256"],
        "locator": refreshed["row_locator"],
        "row_sha256": refreshed["row_sha256"],
        "status": "passed",
    }


def _declared_hash(value: object, *, label: str) -> str:
    result = str(value or "").strip().upper()
    if not SHA256_RE.fullmatch(result):
        raise ValueError(f"{label} has no full declared SHA-256")
    return result


def validate_source_render_manifest(
    row: dict,
    requested_profiles: list[str],
    requested_editions: list[str],
    ffmpeg: str,
    *,
    strict: bool,
) -> dict:
    """Recompute all source declarations before a series can be published."""

    event = row["event"]
    render_manifest_path = Path(row["render_manifest_path"])
    payload = row["render_manifest"]
    raw_matrix = payload.get("edition_matrix")
    if strict and not isinstance(raw_matrix, dict):
        raise ValueError(
            f"{event} publication requires a verified edition_matrix"
        )
    if not isinstance(raw_matrix, dict):
        return {
            "verified": False,
            "render_manifest_path": str(render_manifest_path),
            "render_manifest_sha256": file_sha256(render_manifest_path),
            "profiles": {},
        }

    profile_audit: dict[str, dict] = {}
    packet_hashes_by_edition: dict[str, set[str]] = {
        edition: set() for edition in requested_editions
    }
    actual_audio_by_profile: dict[str, set[str]] = {}
    for profile in requested_profiles:
        raw_profile = raw_matrix.get(profile)
        if not isinstance(raw_profile, dict):
            raise ValueError(f"{event} has no declared profile {profile}")
        raw_editions = raw_profile.get("editions")
        if not isinstance(raw_editions, dict):
            raise ValueError(f"{event} {profile} has no declared editions")
        declared_profile_audio = _declared_hash(
            raw_profile.get("audio_sha256"),
            label=f"{event} {profile}.audio_sha256",
        )
        edition_audit: dict[str, dict] = {}
        audio_hashes: set[str] = set()
        for edition in requested_editions:
            raw_edition = raw_editions.get(edition)
            if not isinstance(raw_edition, dict):
                raise ValueError(f"{event} has no declaration for {profile}.{edition}")
            resolved = candidate_edition(row, profile, edition)
            video_path = resolved["video_path"]
            subtitle_path = resolved["subtitle_path"]
            actual_video_sha256 = file_sha256(video_path)
            declared_video_sha256 = _declared_hash(
                raw_edition.get("video_sha256"),
                label=f"{event} {profile}.{edition}.video_sha256",
            )
            if actual_video_sha256 != declared_video_sha256:
                raise ValueError(
                    f"{event} {profile}.{edition} video SHA-256 declaration mismatch"
                )
            actual_audio_sha256 = audio_hash(video_path, ffmpeg)
            declared_audio_sha256 = _declared_hash(
                raw_edition.get("audio_sha256"),
                label=f"{event} {profile}.{edition}.audio_sha256",
            )
            if actual_audio_sha256 != declared_audio_sha256:
                raise ValueError(
                    f"{event} {profile}.{edition} audio SHA-256 declaration mismatch"
                )
            actual_packet_sha256 = video_packet_hash(video_path, ffmpeg)
            declared_packet_sha256 = _declared_hash(
                raw_edition.get("video_packet_sha256"),
                label=f"{event} {profile}.{edition}.video_packet_sha256",
            )
            if actual_packet_sha256 != declared_packet_sha256:
                raise ValueError(
                    f"{event} {profile}.{edition} video packet declaration mismatch"
                )
            actual_subtitle_sha256 = ""
            declared_subtitle_sha256 = str(
                raw_edition.get("subtitle_sha256", "")
            ).strip().upper()
            if edition == "none":
                if subtitle_path or declared_subtitle_sha256:
                    raise ValueError(
                        f"{event} {profile}.none must not declare subtitles"
                    )
            else:
                if not isinstance(subtitle_path, Path):
                    raise ValueError(f"{event} {profile}.{edition} has no subtitle")
                actual_subtitle_sha256 = file_sha256(subtitle_path)
                declared_subtitle_sha256 = _declared_hash(
                    declared_subtitle_sha256,
                    label=f"{event} {profile}.{edition}.subtitle_sha256",
                )
                if actual_subtitle_sha256 != declared_subtitle_sha256:
                    raise ValueError(
                        f"{event} {profile}.{edition} subtitle SHA-256 declaration mismatch"
                    )
            audio_hashes.add(actual_audio_sha256)
            packet_hashes_by_edition[edition].add(actual_packet_sha256)
            edition_audit[edition] = {
                "video": str(video_path),
                "video_sha256": actual_video_sha256,
                "video_packet_sha256": actual_packet_sha256,
                "audio_sha256": actual_audio_sha256,
                "subtitles": str(subtitle_path) if subtitle_path else "",
                "subtitle_sha256": actual_subtitle_sha256,
            }
        if audio_hashes != {declared_profile_audio}:
            raise ValueError(
                f"{event} {profile} actual editions do not share declared audio"
            )
        actual_audio_by_profile[profile] = audio_hashes
        profile_audit[profile] = {
            "audio_sha256": declared_profile_audio,
            "editions": edition_audit,
        }
    if len(requested_profiles) > 1:
        for edition, hashes in packet_hashes_by_edition.items():
            if len(hashes) != 1:
                raise ValueError(
                    f"{event} {edition} video packets differ by audio profile"
                )
    if set(requested_profiles) == set(AUDIO_PROFILES) and len(
        {next(iter(values)) for values in actual_audio_by_profile.values()}
    ) != 2:
        raise ValueError(f"{event} with_bgm/no_bgm actual audio is identical")
    return {
        "verified": True,
        "render_manifest_path": str(render_manifest_path),
        "render_manifest_sha256": file_sha256(render_manifest_path),
        "profiles": profile_audit,
    }


def _load_verified_scene_builder():
    """Load the strict scene compositor without creating an import cycle.

    ``build_scene_editions`` imports this module for its shared discovery and
    source-declaration gates.  Publication series therefore imports it only
    after both modules have finished initialization and a build is actually
    requested.
    """

    try:
        from . import build_scene_editions as scene_gate
    except ImportError:  # direct script execution
        import build_scene_editions as scene_gate  # type: ignore
    return scene_gate


def _load_json_object(path: Path, *, label: str) -> tuple[bytes, dict]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{label} is not valid UTF-8 JSON: {path}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON root is not an object: {path}")
    return raw, payload


def _series_release_checkpoint(stage: str) -> None:
    """Named no-op boundary used by transaction regression tests."""

    del stage


def _staged_release_path(
    serialized_path: str,
    *,
    staging_series_dir: Path,
    published_series_dir: Path,
    label: str,
) -> Path:
    """Resolve one final serialized release path back into its staging tree."""

    path = Path(str(serialized_path)).resolve()
    try:
        relative = path.relative_to(published_series_dir.resolve())
    except ValueError as error:
        raise RuntimeError(
            f"{label} is outside the published series directory: {path}"
        ) from error
    staged = staging_series_dir.resolve() / relative
    if not staged.is_file():
        raise RuntimeError(f"{label} is absent from the staged release: {staged}")
    return staged


def _validate_staged_series_release(
    *,
    series: str,
    staging_series_dir: Path,
    published_series_dir: Path,
    expected_ordered_events: list[str],
    expected_family_state: dict,
) -> tuple[dict, dict]:
    """Re-open and hash the complete series candidate before promotion."""

    manifest_path = staging_series_dir / "series_manifest.json"
    ready_path = staging_series_dir / "READY.json"
    _, manifest = _load_json_object(
        manifest_path, label=f"{series} staged series manifest"
    )
    _, ready = _load_json_object(ready_path, label=f"{series} staged series READY")
    expected_manifest_path = str(
        (published_series_dir / "series_manifest.json").resolve()
    )
    manifest_sha256 = file_sha256(manifest_path)
    expected_ready = {
        "schema": "magireco-series-editions-ready-v1",
        "status": "READY",
        "series": series,
        "manifest": expected_manifest_path,
        "manifest_sha256": manifest_sha256,
        "family_state_sha256": canonical_sha256(expected_family_state),
        "ordered_events": expected_ordered_events,
        "event_count": len(expected_ordered_events),
    }
    for field, expected in expected_ready.items():
        actual = ready.get(field)
        if field.endswith("sha256"):
            actual = str(actual or "").upper()
        if actual != expected:
            raise RuntimeError(
                f"{series} staged series READY {field} mismatch: "
                f"actual={actual!r}, expected={expected!r}"
            )
    if (
        manifest.get("schema") != "magireco-series-editions-v4"
        or manifest.get("status") != "passed"
        or manifest.get("publishable") is not True
        or manifest.get("release_eligible") is not True
        or [str(row.get("event", "")) for row in manifest.get("sources", [])]
        != expected_ordered_events
        or manifest.get("family_state") != expected_family_state
    ):
        raise RuntimeError(f"{series} staged series manifest failed release gates")

    matrix = manifest.get("outputs", {}).get("edition_matrix", {})
    sha_matrix = manifest.get("output_sha256", {}).get("edition_matrix", {})
    if set(matrix) != set(AUDIO_PROFILES) or set(sha_matrix) != set(AUDIO_PROFILES):
        raise RuntimeError(f"{series} staged series audio profile matrix is incomplete")
    for profile in AUDIO_PROFILES:
        editions = matrix.get(profile, {}).get("editions", {})
        declared_editions = sha_matrix.get(profile, {})
        if set(editions) != set(SUPPORTED_EDITIONS) or set(
            declared_editions
        ) != set(SUPPORTED_EDITIONS):
            raise RuntimeError(
                f"{series} staged series {profile} edition matrix is incomplete"
            )
        for edition in SUPPORTED_EDITIONS:
            row = editions[edition]
            declared = declared_editions[edition]
            video_path = _staged_release_path(
                str(row.get("video", "")),
                staging_series_dir=staging_series_dir,
                published_series_dir=published_series_dir,
                label=f"{series} {profile}.{edition} video",
            )
            actual_video_sha256 = file_sha256(video_path)
            if actual_video_sha256 != str(row.get("video_sha256", "")).upper() or (
                actual_video_sha256 != str(declared.get("video", "")).upper()
            ):
                raise RuntimeError(
                    f"{series} staged {profile}.{edition} video hash mismatch"
                )
            subtitle_text = str(row.get("subtitles", "")).strip()
            declared_subtitle = str(declared.get("subtitles", "")).upper()
            if edition == "none":
                if subtitle_text or declared_subtitle:
                    raise RuntimeError(
                        f"{series} staged {profile}.{edition} unexpectedly has subtitles"
                    )
            else:
                subtitle_path = _staged_release_path(
                    subtitle_text,
                    staging_series_dir=staging_series_dir,
                    published_series_dir=published_series_dir,
                    label=f"{series} {profile}.{edition} subtitles",
                )
                actual_subtitle_sha256 = file_sha256(subtitle_path)
                if actual_subtitle_sha256 != str(
                    row.get("subtitle_sha256", "")
                ).upper() or actual_subtitle_sha256 != declared_subtitle:
                    raise RuntimeError(
                        f"{series} staged {profile}.{edition} subtitle hash mismatch"
                    )

    component_reference = ready.get("component_scene_ready", {})
    if not isinstance(component_reference, dict):
        raise RuntimeError(f"{series} staged READY lacks component scene reference")
    component_archive = _staged_release_path(
        str(component_reference.get("path", "")),
        staging_series_dir=staging_series_dir,
        published_series_dir=published_series_dir,
        label=f"{series} component scene READY archive",
    )
    if file_sha256(component_archive) != str(
        component_reference.get("sha256", "")
    ).upper():
        raise RuntimeError(f"{series} component scene READY archive hash mismatch")
    if ready.get("edition_matrix_sha256") != manifest.get("output_sha256", {}).get(
        "edition_matrix"
    ):
        raise RuntimeError(f"{series} staged READY edition matrix mismatch")

    _series_release_checkpoint("postwrite_hash_validation")
    return manifest, ready


def _build_verified_publication_series_in_staging(
    *,
    series: str,
    selected: list[dict],
    staging_series_dir: Path,
    published_series_dir: Path,
    manifest_root: Path,
    ffmpeg: str,
    ffprobe: str,
    order_contract: dict,
    family_manifest_state: dict,
) -> dict:
    """Build and finalize a modern series entirely below one staging tree.

    Modern series and explicit multi-family scenes have the same media
    correctness problem: independently encoded event AAC streams must not be
    packet-concatenated.  The scene compositor already enforces every v20
    source/READY/base-sidecar/edition-plan gate and constructs one exact PCM
    timeline followed by one AAC encode per audio profile.  This wrapper adds
    the family/order evidence and promotes the scene component into a
    series-specific manifest and READY marker.
    """

    ordered_events = [str(row["event"]) for row in selected]
    if ordered_events != list(order_contract.get("ordered_events", [])):
        raise RuntimeError(
            f"{series} selected events differ from the bound order contract"
        )

    scene_gate = _load_verified_scene_builder()
    component_summary = scene_gate._build_verified_scene_in_staging(
        series,
        selected,
        staging_series_dir,
        published_series_dir,
        manifest_root,
        ffmpeg,
        ffprobe,
        True,
    )
    if (
        component_summary.get("status") != "passed"
        or component_summary.get("publishable") is not True
        or component_summary.get("release_eligible") is not True
        or list(component_summary.get("ordered_events", [])) != ordered_events
    ):
        raise RuntimeError(f"{series} strict scene component is not publishable")

    series_dir = staging_series_dir
    component_manifest_path = series_dir / "scene_manifest.json"
    component_ready_path = series_dir / "READY.json"
    component_ready_raw, component_ready = _load_json_object(
        component_ready_path, label=f"{series} strict scene READY"
    )
    _, component_manifest = _load_json_object(
        component_manifest_path, label=f"{series} strict scene manifest"
    )
    if component_manifest.get("schema") != "magireco-scene-editions-v3":
        raise RuntimeError(f"{series} strict scene manifest schema mismatch")
    if (
        component_manifest.get("status") != "passed"
        or component_manifest.get("publishable") is not True
        or component_manifest.get("release_eligible") is not True
        or [str(row.get("event", "")) for row in component_manifest.get("sources", [])]
        != ordered_events
    ):
        raise RuntimeError(f"{series} strict scene manifest failed source/order gates")
    expected_component_manifest_sha256 = file_sha256(component_manifest_path)
    ready_checks = {
        "schema": "magireco-scene-editions-ready-v1",
        "status": "READY",
        "scene": series,
        "manifest": str((published_series_dir / "scene_manifest.json").resolve()),
        "manifest_sha256": expected_component_manifest_sha256,
        "ordered_events": ordered_events,
        "event_count": len(ordered_events),
    }
    for field, expected in ready_checks.items():
        actual = component_ready.get(field)
        if field.endswith("sha256"):
            actual = str(actual or "").upper()
        if actual != expected:
            raise RuntimeError(
                f"{series} strict scene READY {field} mismatch: "
                f"actual={actual!r}, expected={expected!r}"
            )

    refreshed_order_contract = load_series_order_manifest(
        Path(str(order_contract["manifest_path"])), expected_series=series
    )
    if refreshed_order_contract != order_contract:
        raise RuntimeError(f"{series} order manifest/evidence changed during build")
    refreshed_family_state = family_state(series, manifest_root)
    if refreshed_family_state != family_manifest_state:
        raise RuntimeError(f"{series} production family state changed during build")
    _series_release_checkpoint("order_family_refresh")

    component_ready_archive = (
        series_dir / "audit" / "series_component_scene_ready.json"
    )
    component_ready_archive.parent.mkdir(parents=True, exist_ok=True)
    component_ready_archive.write_bytes(component_ready_raw)
    component_ready_reference = {
        "path": str(
            (
                published_series_dir
                / "audit"
                / "series_component_scene_ready.json"
            ).resolve()
        ),
        "sha256": file_sha256(component_ready_archive),
        "locator": "strict scene compositor READY before series promotion",
    }
    _series_release_checkpoint("component_ready_archive_write")

    output_matrix = component_manifest["outputs"]["edition_matrix"]
    audio_sha256_by_profile = {
        profile: str(profile_row.get("audio_sha256", ""))
        for profile, profile_row in output_matrix.items()
    }
    series_manifest = {
        "schema": "magireco-series-editions-v4",
        "legacy_schema_compatible": False,
        "series": series,
        "status": "passed",
        "errors": [],
        "build_mode": "publication",
        "publishable": True,
        "release_eligible": True,
        "direct_stream_copy": False,
        "media_processing": component_manifest.get("media_processing", {}),
        "ordering": "evidence-bound narrative/runtime order",
        "order_contract": order_contract,
        "event_count": len(ordered_events),
        "expected_duration_ms": component_manifest["expected_duration_ms"],
        "subtitle_cue_count": component_manifest.get(
            "subtitle_cue_count_by_language", {}
        ).get("ja", 0),
        "subtitle_cue_count_by_language": component_manifest.get(
            "subtitle_cue_count_by_language", {}
        ),
        "requested_editions": list(SUPPORTED_EDITIONS),
        "requested_audio_profiles": list(AUDIO_PROFILES),
        "stream_signature": component_manifest["stream_signature"],
        "family_state": family_manifest_state,
        "preserved_separately": [],
        "component_scene": {
            "manifest": str(
                (published_series_dir / "scene_manifest.json").resolve()
            ),
            "manifest_sha256": expected_component_manifest_sha256,
            "ready": component_ready_reference,
        },
        "outputs": component_manifest["outputs"],
        "output_sha256": component_manifest["output_sha256"],
        "audio_sha256_by_profile": audio_sha256_by_profile,
        "probes_by_matrix": component_manifest.get("probes_by_matrix", {}),
        "video_timeline_audits_by_matrix": component_manifest.get(
            "video_timeline_audits_by_matrix", {}
        ),
        "sources": component_manifest["sources"],
    }
    series_manifest_path = series_dir / "series_manifest.json"
    series_manifest_path.write_text(
        json.dumps(series_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _series_release_checkpoint("series_manifest_write")

    final_ready = {
        "schema": "magireco-series-editions-ready-v1",
        "status": "READY",
        "series": series,
        "manifest": str(
            (published_series_dir / "series_manifest.json").resolve()
        ),
        "manifest_sha256": file_sha256(series_manifest_path),
        "component_scene_ready": component_ready_reference,
        "order_manifest": {
            "path": str(order_contract["manifest_path"]),
            "sha256": str(order_contract["manifest_sha256"]),
            "locator": str(order_contract["manifest_locator"]),
        },
        "family_state_sha256": canonical_sha256(family_manifest_state),
        "ordered_events": ordered_events,
        "event_count": len(ordered_events),
        "edition_matrix_sha256": component_ready["edition_matrix_sha256"],
        "audio_masters": component_ready["audio_masters"],
    }
    final_ready_temp = component_ready_path.with_suffix(".series-ready.tmp")
    final_ready_temp.write_text(
        json.dumps(final_ready, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    final_ready_temp.replace(component_ready_path)
    _series_release_checkpoint("series_ready_switch")

    _validate_staged_series_release(
        series=series,
        staging_series_dir=staging_series_dir,
        published_series_dir=published_series_dir,
        expected_ordered_events=ordered_events,
        expected_family_state=family_manifest_state,
    )

    stream_signature_value = component_manifest["stream_signature"]
    return {
        "series": series,
        "status": "passed",
        "publishable": True,
        "release_eligible": True,
        "event_count": len(ordered_events),
        "preserved_separately_count": 0,
        "duration_ms": int(component_summary["duration_ms"]),
        "subtitle_cue_count": series_manifest["subtitle_cue_count"],
        "subtitle_cue_count_by_language": series_manifest[
            "subtitle_cue_count_by_language"
        ],
        "requested_editions": list(SUPPORTED_EDITIONS),
        "requested_audio_profiles": list(AUDIO_PROFILES),
        "width": stream_signature_value["video"]["width"],
        "height": stream_signature_value["video"]["height"],
        "frame_rate": stream_signature_value["video"]["r_frame_rate"],
        "audio_sample_rate": stream_signature_value["audio"]["sample_rate"],
        "audio_channels": stream_signature_value["audio"]["channels"],
        "manifest": str(
            (published_series_dir / "series_manifest.json").resolve()
        ),
        "ready_marker": str((published_series_dir / "READY.json").resolve()),
    }


def build_verified_publication_series(
    *,
    series: str,
    selected: list[dict],
    out_root: Path,
    manifest_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
    order_contract: dict,
    family_manifest_state: dict,
) -> dict:
    """Build and publish one complete series with one rollback-safe promotion.

    Scene media, refreshed order/family evidence, both manifests, the archived
    scene READY, final series READY, and the complete post-write hash audit are
    all completed in a same-volume sibling staging tree.  The published series
    is replaced only after every one of those operations succeeds.
    """

    series = validate_output_identifier(series, label="series")
    published_series_dir = resolve_output_child(out_root, series, label="series")
    published_ready = published_series_dir / "READY.json"
    if published_ready.exists() and not overwrite:
        raise FileExistsError(
            "READY series release already exists; pass --overwrite: "
            f"{published_series_dir}"
        )
    if published_series_dir.exists() and not overwrite:
        raise FileExistsError(
            "series output already exists; pass --overwrite: "
            f"{published_series_dir}"
        )

    out_root.mkdir(parents=True, exist_ok=True)
    staging_container = Path(
        tempfile.mkdtemp(
            prefix=f".series-staging-{uuid.uuid4().hex[:12]}-",
            dir=out_root,
        )
    )
    staging_series_dir = staging_container / "release"
    try:
        summary = _build_verified_publication_series_in_staging(
            series=series,
            selected=selected,
            staging_series_dir=staging_series_dir,
            published_series_dir=published_series_dir,
            manifest_root=manifest_root,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            order_contract=order_contract,
            family_manifest_state=family_manifest_state,
        )
        scene_gate = _load_verified_scene_builder()
        scene_gate._promote_scene_release(
            staging_scene_dir=staging_series_dir,
            published_scene_dir=published_series_dir,
            overwrite=overwrite,
        )
        return summary
    finally:
        shutil.rmtree(staging_container, ignore_errors=True)


def build_series(
    series: str,
    candidates: dict[str, dict],
    preserve_separately: set[str],
    out_root: Path,
    manifest_root: Path | None,
    require_complete: bool,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
    editions: list[str] | None = None,
    audio_profiles: list[str] | None = None,
    legacy_compat: bool = False,
    order_manifest_path: Path | None = None,
    review_only: bool = False,
) -> dict:
    series = validate_output_identifier(series, label="series")
    requested_editions = normalize_requested_editions(
        editions, legacy_compat=legacy_compat
    )
    requested_profiles = normalize_requested_audio_profiles(
        audio_profiles, legacy_compat=legacy_compat
    )
    publication_mode = not review_only and not legacy_compat
    if publication_mode and (
        set(requested_editions) != set(SUPPORTED_EDITIONS)
        or set(requested_profiles) != set(AUDIO_PROFILES)
    ):
        raise ValueError(
            f"{series} partial edition/audio matrix is review-only; publication "
            "requires none/ja/zh for both with_bgm and no_bgm"
        )
    if publication_mode and not require_complete:
        raise ValueError(
            f"{series} publication cannot disable complete-family validation"
        )
    all_family_candidates = {
        event: row
        for event, row in candidates.items()
        if event.startswith(f"{series}_")
    }
    if not all_family_candidates:
        raise ValueError(f"{series} has zero QA-passed events")
    family_preserved = sorted(
        event
        for event in preserve_separately
        if event.startswith(f"{series}_")
    )
    if publication_mode and family_preserved:
        raise ValueError(
            f"{series} publication cannot omit separately preserved events"
        )
    order_contract = (
        load_series_order_manifest(order_manifest_path, expected_series=series)
        if order_manifest_path is not None
        else None
    )
    if publication_mode and order_contract is None:
        raise ValueError(
            f"{series} publication requires an evidence-bound order manifest"
        )
    if order_contract is not None:
        ordered_names = order_contract["ordered_events"]
        unknown_ordered = [
            event for event in ordered_names if event not in all_family_candidates
        ]
        if unknown_ordered:
            raise ValueError(
                f"{series} order manifest events are not QA-passed inputs: "
                f"{unknown_ordered}"
            )
        if publication_mode and set(ordered_names) != set(all_family_candidates):
            missing = sorted(set(all_family_candidates) - set(ordered_names))
            raise ValueError(
                f"{series} order manifest is not the exact complete input list; "
                f"missing={missing}"
            )
        selected = [
            all_family_candidates[event]
            for event in ordered_names
            if event not in preserve_separately
        ]
        ordering = "evidence-bound narrative/runtime order"
    else:
        selected = sorted(
            [
                row
                for event, row in all_family_candidates.items()
                if event not in preserve_separately
            ],
            key=lambda row: event_sort_key(row["event"]),
        )
        ordering = "natural identifier order (review-only, not narrative evidence)"
    if not selected:
        raise ValueError(f"{series} has zero selected events")
    if publication_mode and len(selected) < 2:
        raise ValueError(
            f"{series} single-event output is review-only, not a publishable series"
        )
    for row in selected:
        missing_profiles = [
            profile
            for profile in requested_profiles
            if profile not in row["edition_matrix"]
        ]
        missing_editions = [
            f"{profile}.{edition}"
            for profile in requested_profiles
            if profile in row["edition_matrix"]
            for edition in requested_editions
            if edition not in row["edition_matrix"][profile]["editions"]
        ]
        if missing_profiles or missing_editions:
            raise ValueError(
                f"{row['event']} is missing profiles={missing_profiles}, "
                f"editions={missing_editions}"
            )

    state = family_state(series, manifest_root)
    if publication_mode and not state:
        raise ValueError(
            f"{series} publication requires --production-manifest-root"
        )
    selected_names = {row["event"] for row in selected}
    unknown_preserved = sorted(set(family_preserved) - set(candidates))
    if unknown_preserved:
        raise ValueError(
            f"{series} separately preserved events are not QA-passed inputs: "
            f"{unknown_preserved}"
        )
    missing_ready = sorted(
        set(state.get("ready_event_names", []))
        - selected_names
        - set(family_preserved)
    )
    not_ready = state.get("not_ready_family_events", [])
    known_ready_names = set(state.get("ready_event_names", []))
    if publication_mode and (
        state.get("known_family_events", 0) == 0
        or not_ready
        or known_ready_names != set(all_family_candidates)
    ):
        raise ValueError(
            f"{series} production manifests do not prove one exact ready family; "
            f"ready_only={sorted(known_ready_names - set(all_family_candidates))}, "
            f"input_only={sorted(set(all_family_candidates) - known_ready_names)}, "
            f"not_ready={[row['event'] for row in not_ready]}"
        )
    if require_complete and publication_mode and (missing_ready or not_ready):
        raise ValueError(
            f"{series} is not a complete family; missing ready={missing_ready}, "
            f"not ready={[row['event'] for row in not_ready]}"
        )

    if publication_mode:
        assert order_contract is not None
        assert manifest_root is not None
        return build_verified_publication_series(
            series=series,
            selected=selected,
            out_root=out_root,
            manifest_root=manifest_root,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            overwrite=overwrite,
            order_contract=order_contract,
            family_manifest_state=state,
        )

    source_rows: list[dict] = []
    preserved_rows: list[dict] = []
    expected_signature: dict | None = None
    offset_ms = 0
    combined_cues_by_language: dict[str, list[dict]] = {
        edition: [] for edition in requested_editions if edition != "none"
    }
    matrix_keys = [
        (profile, edition)
        for profile in requested_profiles
        for edition in requested_editions
    ]
    for order, row in enumerate(selected, start=1):
        qa_provenance = validate_qa_binding(row)
        render_source_audit = validate_source_render_manifest(
            row,
            requested_profiles,
            requested_editions,
            ffmpeg,
            strict=publication_mode,
        )
        edition_probes = {
            key: probe(candidate_edition(row, *key)["video_path"], ffprobe)
            for key in matrix_keys
        }
        edition_signatures = {
            key: stream_signature(item) for key, item in edition_probes.items()
        }
        without_signature = edition_signatures[(requested_profiles[0], "none")]
        if any(
            signature != without_signature
            for signature in edition_signatures.values()
        ):
            raise ValueError(f"edition stream mismatch: {row['event']}")
        if expected_signature is None:
            expected_signature = without_signature
        elif without_signature != expected_signature:
            raise ValueError(f"series stream mismatch: {row['event']}")
        duration_ms = round(
            float(
                edition_probes[(requested_profiles[0], "none")]["format"][
                    "duration"
                ]
            )
            * 1000
        )
        for (profile, edition), item in edition_probes.items():
            edition_duration_ms = round(float(item["format"]["duration"]) * 1000)
            if abs(edition_duration_ms - duration_ms) > 50:
                raise ValueError(
                    f"edition duration mismatch: {row['event']} "
                    f"{profile}.{edition}"
                )

        event_cues: dict[str, list[dict]] = {}
        for language in combined_cues_by_language:
            subtitle_paths = [
                candidate_edition(row, profile, language)["subtitle_path"]
                for profile in requested_profiles
            ]
            subtitle_hashes = {file_sha256(path) for path in subtitle_paths}
            if len(subtitle_hashes) != 1:
                raise ValueError(
                    f"subtitle source differs by audio profile: "
                    f"{row['event']} {language}"
                )
            subtitle_path = subtitle_paths[0]
            unshifted = shifted_srt_cues(
                subtitle_path.read_text(encoding="utf-8"), 0
            )
            event_cues[language] = unshifted
            combined_cues_by_language[language].extend(
                {
                    **cue,
                    "start_ms": int(cue["start_ms"]) + offset_ms,
                    "end_ms": int(cue["end_ms"]) + offset_ms,
                }
                for cue in unshifted
            )
        cue_timelines = {
            language: [
                (int(cue["start_ms"]), int(cue["end_ms"])) for cue in cues
            ]
            for language, cues in event_cues.items()
        }
        if cue_timelines and len({tuple(value) for value in cue_timelines.values()}) != 1:
            raise ValueError(f"subtitle timeline mismatch: {row['event']}")

        edition_source_audit: dict[str, dict] = {}
        for profile in requested_profiles:
            profile_audit: dict[str, dict[str, str]] = {}
            for edition in requested_editions:
                edition_row = candidate_edition(row, profile, edition)
                subtitle_path = edition_row["subtitle_path"]
                profile_audit[edition] = {
                    "video": str(edition_row["video_path"]),
                    "video_sha256": file_sha256(edition_row["video_path"]),
                    "subtitles": str(subtitle_path) if subtitle_path else "",
                    "subtitle_sha256": (
                        file_sha256(subtitle_path) if subtitle_path else ""
                    ),
                }
            edition_source_audit[profile] = profile_audit
        legacy_audit = edition_source_audit.get(LEGACY_AUDIO_PROFILE, {})
        ja_audit = legacy_audit.get("ja", {})
        legacy_none = legacy_audit.get("none", {})
        source_rows.append(
            {
                "order": order,
                "event": row["event"],
                "start_ms": offset_ms,
                "end_ms": offset_ms + duration_ms,
                "duration_ms": duration_ms,
                "subtitle_cues": len(event_cues.get("ja", [])),
                "without_subtitles": legacy_none.get("video", ""),
                "with_subtitles": ja_audit.get("video", ""),
                "subtitles": ja_audit.get("subtitles", ""),
                "render_manifest": row["render_manifest_path"],
                "render_manifest_sha256": render_source_audit[
                    "render_manifest_sha256"
                ],
                "qa_report": qa_provenance["path"],
                "qa_report_sha256": qa_provenance["sha256"],
                "qa_locator": qa_provenance["locator"],
                "qa_row_sha256": qa_provenance["row_sha256"],
                "without_sha256": legacy_none.get("video_sha256", ""),
                "with_sha256": ja_audit.get("video_sha256", ""),
                "subtitle_sha256": ja_audit.get("subtitle_sha256", ""),
                "editions_json": json.dumps(
                    edition_source_audit, ensure_ascii=False, sort_keys=True
                ),
                "verified_source_declarations_json": json.dumps(
                    render_source_audit, ensure_ascii=False, sort_keys=True
                ),
            }
        )
        offset_ms += duration_ms

    for event in family_preserved:
        row = candidates[event]
        qa_provenance = validate_qa_binding(row)
        render_source_audit = validate_source_render_manifest(
            row,
            requested_profiles,
            requested_editions,
            ffmpeg,
            strict=False,
        )
        missing_profiles = [
            profile
            for profile in requested_profiles
            if profile not in row["edition_matrix"]
        ]
        missing_editions = [
            f"{profile}.{edition}"
            for profile in requested_profiles
            if profile in row["edition_matrix"]
            for edition in requested_editions
            if edition not in row["edition_matrix"][profile]["editions"]
        ]
        if missing_profiles or missing_editions:
            raise ValueError(
                f"{event} preserved input missing profiles={missing_profiles}, "
                f"editions={missing_editions}"
            )
        preserved_probes = {
            key: probe(candidate_edition(row, *key)["video_path"], ffprobe)
            for key in matrix_keys
        }
        preserved_signatures = {
            edition: stream_signature(item)
            for edition, item in preserved_probes.items()
        }
        without_signature = preserved_signatures[(requested_profiles[0], "none")]
        if any(
            signature != without_signature
            for signature in preserved_signatures.values()
        ):
            raise ValueError(f"edition stream mismatch: {event}")
        preserved_editions: dict[str, dict] = {}
        for profile in requested_profiles:
            profile_editions = {}
            for edition in requested_editions:
                edition_row = candidate_edition(row, profile, edition)
                subtitle_path = edition_row["subtitle_path"]
                profile_editions[edition] = {
                    "video": str(edition_row["video_path"]),
                    "video_sha256": file_sha256(edition_row["video_path"]),
                    "subtitles": str(subtitle_path) if subtitle_path else "",
                    "subtitle_sha256": (
                        file_sha256(subtitle_path) if subtitle_path else ""
                    ),
                }
            preserved_editions[profile] = profile_editions
        legacy_audit = preserved_editions.get(LEGACY_AUDIO_PROFILE, {})
        ja_audit = legacy_audit.get("ja", {})
        legacy_none = legacy_audit.get("none", {})
        preserved_rows.append(
            {
                "event": event,
                "reason": (
                    "native_stream_signature_differs_from_long_edition; "
                    "preserved_as_original_event_without_scaling"
                ),
                "stream_signature": without_signature,
                "without_subtitles": legacy_none.get("video", ""),
                "with_subtitles": ja_audit.get("video", ""),
                "subtitles": ja_audit.get("subtitles", ""),
                "render_manifest": row["render_manifest_path"],
                "render_manifest_sha256": render_source_audit[
                    "render_manifest_sha256"
                ],
                "qa_provenance": qa_provenance,
                "without_sha256": legacy_none.get("video_sha256", ""),
                "with_sha256": ja_audit.get("video_sha256", ""),
                "subtitle_sha256": ja_audit.get("subtitle_sha256", ""),
                "editions": preserved_editions,
            }
        )

    series_dir = resolve_output_child(out_root, series, label="series")
    audit_dir = series_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    edition_outputs: dict[str, dict[str, dict[str, Path | None]]] = {}
    written_subtitles: dict[str, Path] = {}
    for profile in requested_profiles:
        profile_outputs: dict[str, dict[str, Path | None]] = {}
        for edition in requested_editions:
            video_output, subtitle_output = series_edition_paths(
                series_dir, series, edition, profile
            )
            concat_stem = f"{profile}__{edition}"
            concat_copy(
                [
                    candidate_edition(row, profile, edition)["video_path"]
                    for row in selected
                ],
                audit_dir / f"{concat_stem}.ffconcat",
                video_output,
                ffmpeg,
                overwrite,
            )
            if subtitle_output is not None and edition not in written_subtitles:
                subtitle_output.parent.mkdir(parents=True, exist_ok=True)
                write_srt(subtitle_output, combined_cues_by_language[edition])
                written_subtitles[edition] = subtitle_output
            profile_outputs[edition] = {
                "video": video_output,
                "subtitles": subtitle_output,
            }
        edition_outputs[profile] = profile_outputs
    legacy_outputs = edition_outputs.get(LEGACY_AUDIO_PROFILE, {})
    without_output = legacy_outputs.get("none", {}).get("video")
    ja_output = legacy_outputs.get("ja", {})
    with_output = ja_output.get("video")
    subtitle_output = ja_output.get("subtitles")
    write_csv(
        audit_dir / "series_index.csv",
        source_rows,
        [
            "order",
            "event",
            "start_ms",
            "end_ms",
            "duration_ms",
            "subtitle_cues",
            "without_subtitles",
            "with_subtitles",
            "subtitles",
            "render_manifest",
            "render_manifest_sha256",
            "qa_report",
            "qa_report_sha256",
            "qa_locator",
            "qa_row_sha256",
            "without_sha256",
            "with_sha256",
            "subtitle_sha256",
            "editions_json",
            "verified_source_declarations_json",
        ],
    )

    output_probes = {
        (profile, edition): probe(row["video"], ffprobe)
        for profile, profile_rows in edition_outputs.items()
        for edition, row in profile_rows.items()
    }
    errors: list[str] = []
    if order_contract is not None:
        refreshed_order_contract = load_series_order_manifest(
            Path(order_contract["manifest_path"]), expected_series=series
        )
        if refreshed_order_contract != order_contract:
            errors.append("order_manifest_or_evidence_changed_during_build")
    for row in source_rows:
        if file_sha256(Path(row["qa_report"])) != row["qa_report_sha256"]:
            errors.append(f"{row['event']}_qa_report_changed_during_build")
        if (
            file_sha256(Path(row["render_manifest"]))
            != row["render_manifest_sha256"]
        ):
            errors.append(f"{row['event']}_render_manifest_changed_during_build")
    for (profile, edition), item in output_probes.items():
        if stream_signature(item) != expected_signature:
            errors.append(f"{profile}.{edition}_stream_signature_changed")
    output_durations_ms = {
        key: round(float(item["format"]["duration"]) * 1000)
        for key, item in output_probes.items()
    }
    without_duration_ms = output_durations_ms[(requested_profiles[0], "none")]
    tolerance_ms = max(100, len(selected) * 35)
    for (profile, edition), duration_ms in output_durations_ms.items():
        if abs(duration_ms - offset_ms) > tolerance_ms:
            errors.append(f"{profile}.{edition}_duration_mismatch")
    output_audio_hashes = {
        (profile, edition): audio_hash(row["video"], ffmpeg)
        for profile, profile_rows in edition_outputs.items()
        for edition, row in profile_rows.items()
    }
    output_video_packet_hashes = {
        (profile, edition): video_packet_hash(row["video"], ffmpeg)
        for profile, profile_rows in edition_outputs.items()
        for edition, row in profile_rows.items()
    }
    if len(requested_profiles) > 1:
        for edition in requested_editions:
            if len(
                {
                    output_video_packet_hashes[(profile, edition)]
                    for profile in requested_profiles
                }
            ) != 1:
                errors.append(
                    f"{edition}_video_packet_mismatch_between_audio_profiles"
                )
    audio_sha256_by_profile: dict[str, str] = {}
    for profile in requested_profiles:
        profile_hashes = {
            output_audio_hashes[(profile, edition)]
            for edition in requested_editions
        }
        if len(profile_hashes) != 1:
            errors.append(f"{profile}_subtitle_edition_audio_mismatch")
        else:
            audio_sha256_by_profile[profile] = next(iter(profile_hashes))
    if (
        set(requested_profiles) == set(AUDIO_PROFILES)
        and len(set(audio_sha256_by_profile.values())) != 2
    ):
        errors.append("audio_master_profiles_identical")
    without_audio_hash = audio_sha256_by_profile.get(
        LEGACY_AUDIO_PROFILE, ""
    )

    output_manifest_matrix: dict[str, dict] = {}
    output_sha256_matrix: dict[str, dict] = {}
    for profile, profile_rows in edition_outputs.items():
        manifest_editions: dict[str, dict[str, str]] = {}
        sha_editions: dict[str, dict[str, str]] = {}
        for edition, row in profile_rows.items():
            video_output = row["video"]
            subtitle_output_for_edition = row["subtitles"]
            actual_video_sha256 = file_sha256(video_output)
            actual_subtitle_sha256 = (
                file_sha256(subtitle_output_for_edition)
                if subtitle_output_for_edition is not None
                else ""
            )
            manifest_editions[edition] = {
                "language": edition,
                "video": str(video_output.resolve()),
                "subtitles": (
                    str(subtitle_output_for_edition.resolve())
                    if subtitle_output_for_edition is not None
                    else ""
                ),
                "audio_sha256": output_audio_hashes[(profile, edition)],
                "video_sha256": actual_video_sha256,
                "video_packet_sha256": output_video_packet_hashes[
                    (profile, edition)
                ],
                "subtitle_sha256": actual_subtitle_sha256,
            }
            sha_editions[edition] = {
                "video": actual_video_sha256,
                "video_packet": output_video_packet_hashes[(profile, edition)],
                "subtitles": actual_subtitle_sha256,
            }
        output_manifest_matrix[profile] = {
            "audio_profile": profile,
            "audio_sha256": audio_sha256_by_profile.get(profile, ""),
            "editions": manifest_editions,
        }
        output_sha256_matrix[profile] = sha_editions
    output_manifest_editions = output_manifest_matrix.get(
        LEGACY_AUDIO_PROFILE, {}
    ).get("editions", {})
    output_sha256_by_edition = output_sha256_matrix.get(
        LEGACY_AUDIO_PROFILE, {}
    )
    probes_by_matrix = {
        profile: {
            edition: output_probes[(profile, edition)]
            for edition in requested_editions
        }
        for profile in requested_profiles
    }
    audio_hashes_by_matrix = {
        profile: {
            edition: output_audio_hashes[(profile, edition)]
            for edition in requested_editions
        }
        for profile in requested_profiles
    }

    manifest = {
        "schema": "magireco-series-editions-v3",
        "legacy_schema_compatible": legacy_compat,
        "series": series,
        "status": (
            "failed"
            if errors
            else ("passed" if publication_mode else "review_only")
        ),
        "errors": errors,
        "build_mode": "publication" if publication_mode else "review_only",
        "publishable": publication_mode and not errors,
        "release_eligible": publication_mode and not errors,
        "direct_stream_copy": True,
        "ordering": ordering,
        "order_contract": order_contract,
        "event_count": len(selected),
        "expected_duration_ms": offset_ms,
        "subtitle_cue_count": len(combined_cues_by_language.get("ja", [])),
        "subtitle_cue_count_by_language": {
            language: len(cues)
            for language, cues in combined_cues_by_language.items()
        },
        "requested_editions": requested_editions,
        "requested_audio_profiles": requested_profiles,
        "stream_signature": expected_signature,
        "family_state": state,
        "preserved_separately": preserved_rows,
        "outputs": {
            "without_subtitles": (
                str(without_output.resolve()) if without_output else ""
            ),
            "with_subtitles": str(with_output.resolve()) if with_output else "",
            "subtitles": str(subtitle_output.resolve()) if subtitle_output else "",
            "editions": output_manifest_editions,
            "edition_matrix": (
                {} if legacy_compat else output_manifest_matrix
            ),
            "series_index": str((audit_dir / "series_index.csv").resolve()),
        },
        "output_sha256": {
            "without_subtitles": (
                file_sha256(without_output) if without_output else ""
            ),
            "with_subtitles": file_sha256(with_output) if with_output else "",
            "subtitles": file_sha256(subtitle_output) if subtitle_output else "",
            "editions": output_sha256_by_edition,
            "edition_matrix": (
                {} if legacy_compat else output_sha256_matrix
            ),
        },
        "edition_audio_sha256": without_audio_hash,
        "audio_sha256_by_profile": audio_sha256_by_profile,
        "edition_audio_sha256_by_matrix": audio_hashes_by_matrix,
        "probe_without_subtitles": probes_by_matrix.get(
            LEGACY_AUDIO_PROFILE, {}
        ).get("none", {}),
        "probe_with_subtitles": probes_by_matrix.get(
            LEGACY_AUDIO_PROFILE, {}
        ).get("ja", {}),
        "probes_by_matrix": probes_by_matrix,
        "sources": source_rows,
    }
    manifest_path = series_dir / "series_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(f"{series} series QA failed: {errors}")
    return {
        "series": series,
        "status": "passed" if publication_mode else "review_only",
        "publishable": publication_mode,
        "release_eligible": publication_mode,
        "event_count": len(selected),
        "preserved_separately_count": len(preserved_rows),
        "duration_ms": without_duration_ms,
        "subtitle_cue_count": len(combined_cues_by_language.get("ja", [])),
        "subtitle_cue_count_by_language": {
            language: len(cues)
            for language, cues in combined_cues_by_language.items()
        },
        "requested_editions": requested_editions,
        "requested_audio_profiles": requested_profiles,
        "width": expected_signature["video"]["width"],
        "height": expected_signature["video"]["height"],
        "frame_rate": expected_signature["video"]["r_frame_rate"],
        "audio_sample_rate": expected_signature["audio"]["sample_rate"],
        "audio_channels": expected_signature["audio"]["channels"],
        "manifest": str(manifest_path.resolve()),
    }


def index_order_manifests(paths: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in paths:
        path = Path(value).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"series order manifest is required: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        series = str(payload.get("series", "")).strip()
        if not series:
            raise ValueError(f"series order manifest has no series: {path}")
        if series in result:
            raise ValueError(f"duplicate series order manifest for {series}")
        result[series] = path
    return result


def main() -> int:
    args = parse_args()
    requested_series = [
        validate_output_identifier(series, label="series")
        for series in args.series
    ]
    input_roots = [Path(path).resolve() for path in args.input_root]
    candidates = discover_events(
        input_roots, allow_legacy=args.legacy_two_edition
    )
    out_root = Path(args.out_root).resolve()
    manifest_root = (
        Path(args.production_manifest_root).resolve()
        if args.production_manifest_root
        else None
    )
    order_manifests = index_order_manifests(args.order_manifest)
    unknown_order_series = sorted(set(order_manifests) - set(requested_series))
    if unknown_order_series:
        raise ValueError(
            f"order manifest supplied for an unrequested series: {unknown_order_series}"
        )
    out_root.mkdir(parents=True, exist_ok=True)
    review_only = args.review_only or args.legacy_two_edition
    rows = []
    for series in requested_series:
        row = build_series(
            series,
            candidates,
            set(args.preserve_event_separately),
            out_root,
            manifest_root,
            args.require_complete_family,
            args.ffmpeg,
            args.ffprobe,
            args.overwrite,
            args.editions,
            args.audio_profiles,
            args.legacy_two_edition,
            order_manifests.get(series),
            review_only,
        )
        rows.append(row)
        print(
            f"[{row['status']}] {series}: {row['event_count']} events",
            flush=True,
        )
    summary = {
        "schema": "magireco-series-build-summary-v3",
        "legacy_two_edition_compatibility": args.legacy_two_edition,
        "build_mode": "review_only" if review_only else "publication",
        "publishable": bool(rows) and all(row["publishable"] for row in rows),
        "requested_editions": normalize_requested_editions(
            args.editions, legacy_compat=args.legacy_two_edition
        ),
        "requested_audio_profiles": normalize_requested_audio_profiles(
            args.audio_profiles, legacy_compat=args.legacy_two_edition
        ),
        "series_count": len(rows),
        "passed": sum(row["status"] == "passed" for row in rows),
        "review_only": sum(row["status"] == "review_only" for row in rows),
        "failed": 0,
        "direct_stream_copy": True,
        "series": rows,
    }
    (out_root / "series_build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
