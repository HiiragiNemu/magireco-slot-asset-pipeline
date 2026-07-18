#!/usr/bin/env python3
"""Build one evidence-bound independent no-BGM Chinese scene candidate.

This is intentionally separate from the archive-complete 2x3 edition tools.
It accepts only the named ``bilibili_no_bgm_zh_v1`` release contract, rebuilds
audio from hash-bound official OGG sources, preserves the native visual grid,
and publishes a BUILD_READY marker only after automatic QA succeeds.  Human
playback approval and Bilibili release approval are deliberately out of scope.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_audio_base_masters as audio_gate
    from .independent_release_contract import (
        RELEASE_PROFILE,
        build_build_ready_marker,
        release_contract,
        validate_build_ready_marker,
        validate_release_contract,
    )
    from .output_path_contract import (
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )
except ImportError:  # direct script execution
    import build_audio_base_masters as audio_gate  # type: ignore
    from independent_release_contract import (  # type: ignore
        RELEASE_PROFILE,
        build_build_ready_marker,
        release_contract,
        validate_build_ready_marker,
        validate_release_contract,
    )
    from output_path_contract import (  # type: ignore
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )


PLAN_SCHEMA = "magireco-independent-scene-build-plan-v1"
LAYOUT_SCHEMA = "magireco-project-zh-video-subtitle-layout-v1"
MANIFEST_SCHEMA = "magireco-independent-scene-release-manifest-v1"
QA_SCHEMA = "magireco-independent-scene-automated-qa-v1"
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
SRT_BLOCK_RE = re.compile(
    r"(?:^|\n)\s*\d+\s*\n"
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(?P<text>.*?)(?=\n\s*\d+\s*\n\d{2}:|\Z)",
    re.DOTALL,
)
ROOT_NAMES = frozenset({"research", "audio", "repo"})
EVENT_FIELDS = frozenset(
    {
        "event",
        "frame_count",
        "presentation_samples",
        "v20_manifest",
        "runtime_manifest",
        "composition_plan",
        "clean_visual",
        "clean_render_manifest",
        "official_ja_srt",
        "audio_layers",
        "dialogue_cues",
        "excluded_voice_requests",
        "excluded_source_cues",
        "oracle",
    }
)
EXPECTED_FIELDS = frozenset(
    {
        "ordered_events",
        "width",
        "height",
        "frame_rate",
        "total_frames",
        "sample_rate",
        "audio_channels",
        "total_presentation_samples",
        "dialogue_cue_count",
    }
)
PLAN_FIELDS = frozenset(
    {
        "schema",
        "release_id",
        "release_contract",
        "expected",
        "events",
        "layout_profile",
        "font",
    }
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--research-root", required=True)
    parser.add_argument("--audio-root", required=True)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def exact_fields(value: Mapping[str, Any], fields: frozenset[str], *, label: str) -> None:
    actual = frozenset(value)
    if actual != fields:
        raise ValueError(
            f"{label} fields differ: missing={sorted(fields - actual)}, "
            f"unknown={sorted(actual - fields)}"
        )


def positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def normalize_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value.strip()):
        raise ValueError(f"{label} requires a full SHA-256")
    return value.strip().upper()


def safe_relative_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty relative path")
    raw = value.strip().replace("\\", "/")
    path = Path(raw)
    if path.is_absolute() or path.drive or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must remain below its declared root")
    if ":" in raw or "\x00" in raw:
        raise ValueError(f"{label} contains a forbidden path character")
    return path


def resolve_locator(
    locator: Any,
    *,
    roots: Mapping[str, Path],
    label: str,
) -> tuple[Path, dict[str, str]]:
    if not isinstance(locator, Mapping):
        raise ValueError(f"{label} locator must be an object")
    exact_fields(locator, frozenset({"root", "path", "sha256"}), label=f"{label} locator")
    root_name = locator.get("root")
    if root_name not in ROOT_NAMES or root_name not in roots:
        raise ValueError(f"{label} locator has unsupported root {root_name!r}")
    relative = safe_relative_path(locator.get("path"), label=f"{label} path")
    root = Path(roots[str(root_name)]).resolve(strict=True)
    path = (root / relative).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} locator escapes root {root_name}") from error
    if not path.is_file():
        raise ValueError(f"{label} is not a file: {path}")
    expected_sha256 = normalize_sha256(locator.get("sha256"), label=f"{label} SHA-256")
    actual_sha256 = file_sha256(path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"{label} SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    snapshot = {
        "label": label,
        "root": str(root_name),
        "relative_path": relative.as_posix(),
        "absolute_path": str(path),
        "sha256": actual_sha256,
    }
    return path, snapshot


def rehash_sources(snapshots: Sequence[Mapping[str, str]]) -> None:
    for row in snapshots:
        path = Path(row["absolute_path"])
        if not path.is_file():
            raise RuntimeError(f"source disappeared during build: {row['label']}")
        actual = file_sha256(path)
        if actual != row["sha256"]:
            raise RuntimeError(
                f"source changed during build: {row['label']} expected "
                f"{row['sha256']}, got {actual}"
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
    hours, remainder = divmod(max(0, value_ms), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_srt(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    cues: list[dict[str, Any]] = []
    for match in SRT_BLOCK_RE.finditer(text):
        cues.append(
            {
                "start_ms": srt_time_ms(match.group("start")),
                "end_ms": srt_time_ms(match.group("end")),
                "text": match.group("text").strip(),
            }
        )
    return cues


def write_srt(path: Path, cues: Sequence[Mapping[str, Any]]) -> None:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        text = cue.get("text", cue.get("zh_text", ""))
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"SRT cue {index} has no text")
        blocks.append(
            f"{index}\n{format_srt_time(int(cue['start_ms']))} --> "
            f"{format_srt_time(int(cue['end_ms']))}\n{text}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        rendered = subprocess.list2cmdline(list(command))
        raise RuntimeError(
            f"command failed ({result.returncode}): {rendered}\n"
            f"{result.stderr[-4000:]}"
        )
    return result


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError(f"ffprobe returned invalid JSON for {path}")
    return value


def media_streams(probe_value: Mapping[str, Any], kind: str) -> list[dict[str, Any]]:
    streams = probe_value.get("streams", [])
    if not isinstance(streams, list):
        return []
    return [row for row in streams if isinstance(row, dict) and row.get("codec_type") == kind]


def frame_count(video: Mapping[str, Any]) -> int:
    value = video.get("nb_read_frames") or video.get("nb_frames")
    try:
        result = int(str(value))
    except (TypeError, ValueError) as error:
        raise RuntimeError("video stream lacks an exact decoded frame count") from error
    if result <= 0:
        raise RuntimeError("video stream has a non-positive frame count")
    return result


def stream_bit_rate(stream: Mapping[str, Any], *, label: str) -> int:
    try:
        value = int(str(stream.get("bit_rate")))
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} lacks an auditable bit rate") from error
    if value <= 0:
        raise RuntimeError(f"{label} has a non-positive bit rate")
    return value


def packet_hash(path: Path, *, kind: str, ffmpeg: str) -> str:
    selector = "v:0" if kind == "video" else "a:0"
    result = run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            f"0:{selector}",
            "-c",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        capture=True,
    )
    match = re.search(r"SHA256=([0-9a-fA-F]{64})", result.stdout)
    if not match:
        raise RuntimeError(f"failed to parse {kind} packet SHA-256 for {path}")
    return match.group(1).upper()


def decoded_pcm_audit(path: Path, ffmpeg: str) -> dict[str, Any]:
    process = subprocess.Popen(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    digest = hashlib.sha256()
    byte_count = 0
    while True:
        block = process.stdout.read(1024 * 1024)
        if not block:
            break
        digest.update(block)
        byte_count += len(block)
    assert process.stderr is not None
    stderr = process.stderr.read().decode("utf-8", errors="replace")
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"PCM decode failed for {path}: {stderr[-4000:]}")
    if byte_count % 4:
        raise RuntimeError(f"decoded stereo s16 PCM is not sample aligned: {path}")
    return {
        "sample_format": "s16le",
        "sample_rate": 48000,
        "channels": 2,
        "presentation_samples": byte_count // 4,
        "byte_count": byte_count,
        "sha256": digest.hexdigest().upper(),
    }


def volume_audit(path: Path, ffmpeg: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "volumedetect",
            "-f",
            "null",
            os.devnull,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"volumedetect failed for {path}: {result.stderr[-4000:]}")
    mean = re.search(r"mean_volume:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", result.stderr, re.I)
    peak = re.search(r"max_volume:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", result.stderr, re.I)
    if not mean or not peak:
        raise RuntimeError(f"volumedetect did not return volume metrics for {path}")
    return {"mean_volume_db": mean.group(1), "max_volume_db": peak.group(1)}


def user_verified_audio_oracle_audit(
    *,
    final_video: Path,
    events: Sequence[Mapping[str, Any]],
    ffmpeg: str,
    ffprobe: str,
) -> list[dict[str, Any]]:
    """Compare each new event interval with the exact v19 user-heard bytes."""

    rows: list[dict[str, Any]] = []
    for event in events:
        oracle_path = Path(
            event["oracle"]["user_verified_media"]["absolute_path"]
        )
        oracle_probe = probe(oracle_path, ffprobe)
        audio_streams = media_streams(oracle_probe, "audio")
        if len(audio_streams) != 1:
            raise RuntimeError(f"{event['event']} user-verified oracle lacks audio")
        audio = audio_streams[0]
        if int(audio.get("sample_rate", 0)) != 48000 or int(audio.get("channels", 0)) != 2:
            raise RuntimeError(f"{event['event']} user-verified oracle format changed")
        try:
            oracle_samples = int(audio["duration_ts"])
            time_base = Fraction(str(audio["time_base"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            raise RuntimeError(
                f"{event['event']} user-verified oracle lacks sample timing"
            ) from error
        if time_base != Fraction(1, 48000) or not 0 < oracle_samples <= int(
            event["presentation_samples"]
        ):
            raise RuntimeError(f"{event['event']} user-verified oracle grid changed")
        start_sample = int(event["start_sample"])
        result = run(
            [
                ffmpeg,
                "-hide_banner",
                "-nostats",
                "-loglevel",
                "info",
                "-i",
                str(final_video),
                "-i",
                str(oracle_path),
                "-filter_complex",
                (
                    f"[0:a]atrim=start_sample={start_sample}:"
                    f"end_sample={start_sample + oracle_samples},"
                    "asetpts=PTS-STARTPTS[new];"
                    f"[1:a]atrim=end_sample={oracle_samples},"
                    "asetpts=PTS-STARTPTS[old];"
                    "[new][old]apsnr[out]"
                ),
                "-map",
                "[out]",
                "-f",
                "null",
                os.devnull,
            ],
            capture=True,
        )
        values = re.findall(
            r"PSNR ch\d+:\s*(inf|\d+(?:\.\d+)?)\s*dB",
            result.stderr,
            re.IGNORECASE,
        )
        if len(values) != 2:
            raise RuntimeError(f"{event['event']} oracle APSNR was not auditable")
        psnr = [math.inf if value.lower() == "inf" else float(value) for value in values]
        if min(psnr) < 80.0:
            raise RuntimeError(
                f"{event['event']} differs materially from the user-verified "
                f"audio oracle: {psnr} dB"
            )
        rows.append(
            {
                "event": event["event"],
                "oracle_presentation_samples": oracle_samples,
                "psnr_db_by_channel": [
                    "inf" if math.isinf(value) else round(value, 3) for value in psnr
                ],
                "minimum_required_psnr_db": 80.0,
                "status": "passed",
            }
        )
    return rows


def validate_layout(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("subtitle layout profile must be an object")
    required = frozenset(
        {
            "schema",
            "profile_id",
            "approval_status",
            "original_game_layout",
            "target_width",
            "target_height",
            "alignment",
            "font_family",
            "font_size",
            "primary_colour",
            "outline_colour",
            "border_style",
            "outline",
            "shadow",
            "margin_v",
            "margin_lr",
            "max_lines",
            "safe_area",
            "notes",
        }
    )
    exact_fields(value, required, label="subtitle layout profile")
    fixed = {
        "schema": LAYOUT_SCHEMA,
        "profile_id": "project_approved_zh_video_subtitle_layout_v1",
        "approval_status": "pending_owner_review",
        "original_game_layout": False,
        "alignment": "bottom_center",
        "font_family": "Noto Sans SC",
        "primary_colour": "&H00FFFFFF",
        "outline_colour": "&H00000000",
        "border_style": 1,
        "shadow": 0,
        "max_lines": 2,
    }
    for field, expected in fixed.items():
        if type(value.get(field)) is not type(expected) or value.get(field) != expected:
            raise ValueError(f"subtitle layout fixed field mismatch: {field}")
    for field in ("target_width", "target_height", "font_size", "margin_v", "margin_lr"):
        positive_int(value.get(field), label=f"layout {field}")
    outline = value.get("outline")
    if isinstance(outline, bool) or not isinstance(outline, (int, float)) or outline <= 0:
        raise ValueError("layout outline must be positive")
    if not isinstance(value.get("safe_area"), Mapping):
        raise ValueError("layout safe_area must be an object")
    return dict(value)


def validate_plan(
    plan_path: Path,
    *,
    roots: Mapping[str, Path],
) -> dict[str, Any]:
    plan = read_json(plan_path)
    exact_fields(plan, PLAN_FIELDS, label="independent scene plan")
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"unsupported plan schema: {plan.get('schema')!r}")
    release_id = validate_output_identifier(plan.get("release_id"), label="release id")
    contract = validate_release_contract(plan.get("release_contract"))
    if contract != release_contract(RELEASE_PROFILE):
        raise ValueError("independent plan release contract mismatch")

    expected = plan.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError("plan expected must be an object")
    exact_fields(expected, EXPECTED_FIELDS, label="plan expected")
    ordered_events = expected.get("ordered_events")
    if not isinstance(ordered_events, list) or not ordered_events:
        raise ValueError("expected ordered_events must be a non-empty list")
    ordered_events = [
        validate_output_identifier(event, label="ordered event") for event in ordered_events
    ]
    if len(set(ordered_events)) != len(ordered_events):
        raise ValueError("expected ordered_events contains duplicates")
    for field in (
        "width",
        "height",
        "total_frames",
        "sample_rate",
        "audio_channels",
        "total_presentation_samples",
        "dialogue_cue_count",
    ):
        positive_int(expected.get(field), label=f"expected {field}")
    if expected.get("frame_rate") != "30/1":
        raise ValueError("independent scene currently requires native 30/1 video")
    if expected.get("sample_rate") != 48000 or expected.get("audio_channels") != 2:
        raise ValueError("independent scene requires AAC-compatible 48 kHz stereo")

    snapshots: list[dict[str, str]] = [
        {
            "label": "independent scene build plan",
            "root": "plan",
            "relative_path": plan_path.name,
            "absolute_path": str(plan_path.resolve()),
            "sha256": file_sha256(plan_path),
        }
    ]
    layout_path, layout_snapshot = resolve_locator(
        plan.get("layout_profile"), roots=roots, label="layout profile"
    )
    snapshots.append(layout_snapshot)
    layout = validate_layout(read_json(layout_path))
    font_path, font_snapshot = resolve_locator(plan.get("font"), roots=roots, label="font")
    snapshots.append(font_snapshot)

    events_value = plan.get("events")
    if not isinstance(events_value, list) or len(events_value) != len(ordered_events):
        raise ValueError("plan events must match expected ordered_events length")
    resolved_events: list[dict[str, Any]] = []
    total_frames = 0
    total_samples = 0
    total_cues = 0
    all_scene_cues: list[dict[str, Any]] = []
    sample_offset = 0

    for event_index, row in enumerate(events_value):
        if not isinstance(row, Mapping):
            raise ValueError(f"event row {event_index} must be an object")
        exact_fields(row, EVENT_FIELDS, label=f"event row {event_index}")
        event = validate_output_identifier(row.get("event"), label="event")
        if event != ordered_events[event_index]:
            raise ValueError(f"event order mismatch at index {event_index}: {event}")
        event_frames = positive_int(row.get("frame_count"), label=f"{event} frame_count")
        event_samples = positive_int(
            row.get("presentation_samples"), label=f"{event} presentation_samples"
        )
        if event_samples * 30 != event_frames * 48000:
            raise ValueError(f"{event} frame/sample presentation grids differ")

        resolved_paths: dict[str, Path] = {}
        event_snapshots: dict[str, dict[str, str]] = {}
        for field in (
            "v20_manifest",
            "runtime_manifest",
            "composition_plan",
            "clean_visual",
            "clean_render_manifest",
            "official_ja_srt",
        ):
            path, snapshot = resolve_locator(
                row.get(field), roots=roots, label=f"{event} {field}"
            )
            resolved_paths[field] = path
            event_snapshots[field] = snapshot
            snapshots.append(snapshot)

        manifest = read_json(resolved_paths["v20_manifest"])
        runtime_manifest = read_json(resolved_paths["runtime_manifest"])
        composition = read_json(resolved_paths["composition_plan"])
        clean_report = read_json(resolved_paths["clean_render_manifest"])
        if manifest.get("event") != event or runtime_manifest.get("event") != event:
            raise ValueError(f"{event} source manifest event mismatch")
        if composition.get("event") != event or manifest.get("composition_plan") != composition:
            raise ValueError(f"{event} composition plan mismatch")
        quality = manifest.get("quality_gates")
        if not isinstance(quality, Mapping) or not all(
            quality.get(field) is True
            for field in ("ready", "render_ready", "audio_timeline_ready", "composition_resolved")
        ):
            raise ValueError(f"{event} v20 manifest is not technically ready")
        if composition.get("model") != "linear_full_frame_sequence":
            raise ValueError(f"{event} is not a clean linear full-frame plan")
        if composition.get("extension_policy") != "hold_last_frame":
            raise ValueError(f"{event} does not use the proven tail-hold policy")
        excluded_ids = {str(value) for value in composition.get("excluded_audio_request_ids", [])}
        if "1681" not in excluded_ids:
            raise ValueError(f"{event} composition does not exclude gold-band request 1681")
        native = composition.get("native_dimensions", {})
        if native != {"width": expected["width"], "height": expected["height"]}:
            raise ValueError(f"{event} native dimensions mismatch")
        if clean_report.get("event") != event:
            raise ValueError(f"{event} clean render report event mismatch")
        clean_hash = file_sha256(resolved_paths["clean_visual"])
        if str(clean_report.get("output_sha256", "")).upper() != clean_hash:
            raise ValueError(f"{event} clean render report does not bind clean visual")

        source_audio = manifest.get("audio")
        if not isinstance(source_audio, list):
            raise ValueError(f"{event} v20 manifest audio is not a list")
        source_by_request = {
            str(item.get("request_id")): item
            for item in source_audio
            if isinstance(item, Mapping)
        }
        layers_value = row.get("audio_layers")
        if not isinstance(layers_value, list) or not layers_value:
            raise ValueError(f"{event} audio_layers must be non-empty")
        layers: list[dict[str, Any]] = []
        for layer_index, layer in enumerate(layers_value):
            if not isinstance(layer, Mapping):
                raise ValueError(f"{event} audio layer {layer_index} must be an object")
            exact_fields(
                layer,
                frozenset({"role", "request_id", "ogg_name", "start_ms", "duration_ms", "source"}),
                label=f"{event} audio layer {layer_index}",
            )
            role = layer.get("role")
            if role not in {"scene_se", "voice"}:
                raise ValueError(f"{event} audio layer {layer_index} has forbidden role {role!r}")
            request_id = str(layer.get("request_id", ""))
            if request_id == "1681" or request_id not in source_by_request:
                raise ValueError(f"{event} audio layer has unknown/forbidden request {request_id}")
            source_row = source_by_request[request_id]
            start_ms = nonnegative_int(layer.get("start_ms"), label=f"{event} {request_id} start_ms")
            duration_ms = positive_int(layer.get("duration_ms"), label=f"{event} {request_id} duration_ms")
            if (
                source_row.get("ogg_name") != layer.get("ogg_name")
                or int(source_row.get("start_ms")) != start_ms
                or int(source_row.get("duration_ms")) != duration_ms
            ):
                raise ValueError(f"{event} audio layer {request_id} differs from v20 evidence")
            audio_path, audio_snapshot = resolve_locator(
                layer.get("source"), roots=roots, label=f"{event} audio request {request_id}"
            )
            snapshots.append(audio_snapshot)
            layers.append(
                {
                    "role": role,
                    "request_id": request_id,
                    "ogg_name": str(layer.get("ogg_name")),
                    "start_ms": start_ms,
                    "duration_ms": duration_ms,
                    "path": audio_path,
                    "source": audio_snapshot,
                }
            )
        if {layer["request_id"] for layer in layers} != set(source_by_request):
            raise ValueError(f"{event} audio plan must account for every v20 audio request")
        if sum(layer["role"] == "scene_se" for layer in layers) != 1:
            raise ValueError(f"{event} requires exactly one verified scene-SE layer")

        dialogue_value = row.get("dialogue_cues")
        if not isinstance(dialogue_value, list):
            raise ValueError(f"{event} dialogue_cues must be a list")
        manifest_subtitles = manifest.get("subtitles")
        if not isinstance(manifest_subtitles, list):
            raise ValueError(f"{event} v20 subtitles must be a list")
        official_cues = parse_srt(resolved_paths["official_ja_srt"])
        dialogue: list[dict[str, Any]] = []
        for cue_index, cue in enumerate(dialogue_value):
            if not isinstance(cue, Mapping):
                raise ValueError(f"{event} dialogue cue {cue_index} must be an object")
            exact_fields(
                cue,
                frozenset(
                    {
                        "request_id",
                        "speaker_code",
                        "start_ms",
                        "end_ms",
                        "ja_text",
                        "zh_text",
                        "translation_status",
                    }
                ),
                label=f"{event} dialogue cue {cue_index}",
            )
            request_id = str(cue.get("request_id", ""))
            start_ms = nonnegative_int(cue.get("start_ms"), label=f"{event} cue start_ms")
            end_ms = positive_int(cue.get("end_ms"), label=f"{event} cue end_ms")
            ja_text = str(cue.get("ja_text", "")).strip()
            zh_text = str(cue.get("zh_text", "")).strip()
            if end_ms <= start_ms or not ja_text or not zh_text:
                raise ValueError(f"{event} dialogue cue {cue_index} is invalid")
            if cue.get("translation_status") != "machine_draft_pending_owner":
                raise ValueError(f"{event} dialogue cue {cue_index} claims unapproved translation")
            matching = [
                item
                for item in manifest_subtitles
                if isinstance(item, Mapping)
                and str(item.get("voice_request_id", "")) == request_id
                and int(item.get("start_ms", -1)) == start_ms
                and int(item.get("end_ms", -1)) == end_ms
                and str(item.get("text", "")).strip() == ja_text
                and item.get("subtitle_source") == "official_runtime_capture"
            ]
            if len(matching) != 1:
                raise ValueError(f"{event} dialogue cue {cue_index} lacks one runtime binding")
            audio_match = [layer for layer in layers if layer["request_id"] == request_id]
            if len(audio_match) != 1 or audio_match[0]["role"] != "voice":
                raise ValueError(f"{event} dialogue cue {cue_index} lacks one voice source")
            dialogue.append(
                {
                    "event": event,
                    "event_cue_index": cue_index,
                    "request_id": request_id,
                    "speaker_code": str(cue.get("speaker_code", "")),
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "ja_text": ja_text,
                    "zh_text": zh_text,
                    "translation_status": "machine_draft_pending_owner",
                    "source_ja_cue_sha256": canonical_sha256(
                        {
                            "event": event,
                            "request_id": request_id,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "text": ja_text,
                        }
                    ),
                    "voice_source_sha256": audio_match[0]["source"]["sha256"],
                }
            )
        if official_cues != [
            {"start_ms": cue["start_ms"], "end_ms": cue["end_ms"], "text": cue["ja_text"]}
            for cue in dialogue
        ]:
            raise ValueError(f"{event} official Japanese SRT differs from dialogue plan")

        excluded_voice_value = row.get("excluded_voice_requests")
        if not isinstance(excluded_voice_value, list):
            raise ValueError(f"{event} excluded_voice_requests must be a list")
        excluded_voice: list[dict[str, str]] = []
        for exclusion in excluded_voice_value:
            if not isinstance(exclusion, Mapping):
                raise ValueError(f"{event} excluded voice row must be an object")
            exact_fields(exclusion, frozenset({"request_id", "reason"}), label=f"{event} excluded voice")
            request_id = str(exclusion.get("request_id", ""))
            reason = str(exclusion.get("reason", "")).strip()
            matching = [layer for layer in layers if layer["request_id"] == request_id]
            if len(matching) != 1 or matching[0]["role"] != "voice" or not reason:
                raise ValueError(f"{event} excluded voice {request_id} is not auditable")
            excluded_voice.append({"request_id": request_id, "reason": reason})
        included_voice_ids = {cue["request_id"] for cue in dialogue}
        excluded_voice_ids = {item["request_id"] for item in excluded_voice}
        all_voice_ids = {layer["request_id"] for layer in layers if layer["role"] == "voice"}
        if included_voice_ids & excluded_voice_ids or included_voice_ids | excluded_voice_ids != all_voice_ids:
            raise ValueError(f"{event} every voice must be included or explicitly excluded")

        excluded_source_value = row.get("excluded_source_cues")
        if not isinstance(excluded_source_value, list):
            raise ValueError(f"{event} excluded_source_cues must be a list")
        excluded_source: list[dict[str, Any]] = []
        for exclusion in excluded_source_value:
            if not isinstance(exclusion, Mapping):
                raise ValueError(f"{event} excluded source cue must be an object")
            exact_fields(
                exclusion,
                frozenset(
                    {"text", "start_ms", "end_ms", "voice_request_id", "z2d_name", "subtitle_source", "reason"}
                ),
                label=f"{event} excluded source cue",
            )
            projection = {
                "text": str(exclusion.get("text", "")),
                "start_ms": int(exclusion.get("start_ms", -1)),
                "end_ms": int(exclusion.get("end_ms", -1)),
                "voice_request_id": str(exclusion.get("voice_request_id", "")),
                "z2d_name": str(exclusion.get("z2d_name", "")),
                "subtitle_source": str(exclusion.get("subtitle_source", "")),
            }
            matches = [
                source
                for source in manifest_subtitles
                if isinstance(source, Mapping)
                and all(source.get(field) == value for field, value in projection.items())
            ]
            if (
                len(matches) != 1
                or projection["subtitle_source"] != "graphical_display_text"
                or projection["voice_request_id"]
                or not str(exclusion.get("reason", "")).strip()
            ):
                raise ValueError(f"{event} graphical-only exclusion is not proven")
            excluded_source.append(
                {
                    **projection,
                    "reason": str(exclusion.get("reason")).strip(),
                    "source_cue_sha256": canonical_sha256(projection),
                }
            )
        graphical_rows = [
            item
            for item in manifest_subtitles
            if isinstance(item, Mapping) and item.get("subtitle_source") == "graphical_display_text"
        ]
        if len(excluded_source) != len(graphical_rows):
            raise ValueError(f"{event} must explicitly exclude every graphical-only cue")

        oracle_value = row.get("oracle")
        if not isinstance(oracle_value, Mapping):
            raise ValueError(f"{event} oracle must be an object")
        exact_fields(
            oracle_value,
            frozenset({"user_verified_media", "render_manifest", "qa_summary", "qa_audit"}),
            label=f"{event} oracle",
        )
        oracle: dict[str, dict[str, str]] = {}
        for field, locator in oracle_value.items():
            oracle_path, oracle_snapshot = resolve_locator(
                locator, roots=roots, label=f"{event} oracle {field}"
            )
            snapshots.append(oracle_snapshot)
            oracle[field] = {**oracle_snapshot, "absolute_path": str(oracle_path)}

        for cue in dialogue:
            scene_start = round(Fraction(sample_offset * 1000, int(expected["sample_rate"])) + cue["start_ms"])
            scene_end = round(Fraction(sample_offset * 1000, int(expected["sample_rate"])) + cue["end_ms"])
            all_scene_cues.append(
                {
                    **cue,
                    "start_ms": scene_start,
                    "end_ms": scene_end,
                    "event_start_sample": sample_offset,
                }
            )

        resolved_events.append(
            {
                "event": event,
                "frame_count": event_frames,
                "presentation_samples": event_samples,
                "start_frame": total_frames,
                "end_frame": total_frames + event_frames,
                "start_sample": sample_offset,
                "end_sample": sample_offset + event_samples,
                "paths": resolved_paths,
                "sources": event_snapshots,
                "audio_layers": layers,
                "dialogue_cues": dialogue,
                "excluded_voice_requests": excluded_voice,
                "excluded_source_cues": excluded_source,
                "oracle": oracle,
            }
        )
        total_frames += event_frames
        total_samples += event_samples
        total_cues += len(dialogue)
        sample_offset += event_samples

    if total_frames != expected["total_frames"]:
        raise ValueError("event frame counts do not equal expected total_frames")
    if total_samples != expected["total_presentation_samples"]:
        raise ValueError("event sample counts do not equal expected total_presentation_samples")
    if total_cues != expected["dialogue_cue_count"]:
        raise ValueError("event dialogue cues do not equal expected dialogue_cue_count")
    if int(layout["target_width"]) != expected["width"] or int(layout["target_height"]) != expected["height"]:
        raise ValueError("subtitle layout target differs from native video dimensions")
    for previous, current in zip(all_scene_cues, all_scene_cues[1:]):
        if current["start_ms"] < previous["start_ms"]:
            raise ValueError("scene subtitle cues are not chronologically ordered")
    total_duration_ms = round(Fraction(total_samples * 1000, int(expected["sample_rate"])))
    if any(cue["end_ms"] > total_duration_ms for cue in all_scene_cues):
        raise ValueError("scene subtitle cue extends past the presentation grid")

    return {
        "plan": plan,
        "plan_path": plan_path.resolve(),
        "plan_sha256": file_sha256(plan_path),
        "release_id": release_id,
        "release_contract": contract,
        "expected": dict(expected),
        "events": resolved_events,
        "layout": layout,
        "layout_path": layout_path,
        "layout_sha256": layout_snapshot["sha256"],
        "font_path": font_path,
        "font_sha256": font_snapshot["sha256"],
        "scene_cues": all_scene_cues,
        "source_snapshots": snapshots,
        "duration_ms": total_duration_ms,
    }


def validate_source_media(resolved: Mapping[str, Any], *, ffprobe: str) -> list[dict[str, Any]]:
    expected = resolved["expected"]
    audits: list[dict[str, Any]] = []
    for event in resolved["events"]:
        clean_probe = probe(event["paths"]["clean_visual"], ffprobe)
        videos = media_streams(clean_probe, "video")
        if len(videos) != 1 or media_streams(clean_probe, "audio") or media_streams(clean_probe, "subtitle"):
            raise RuntimeError(f"{event['event']} clean visual stream contract failed")
        video = videos[0]
        if (
            video.get("codec_name") != "h264"
            or int(video.get("width", 0)) != expected["width"]
            or int(video.get("height", 0)) != expected["height"]
            or video.get("r_frame_rate") != expected["frame_rate"]
            or frame_count(video) != event["frame_count"]
        ):
            raise RuntimeError(f"{event['event']} clean visual native grid mismatch")
        audio_audits = []
        for layer in event["audio_layers"]:
            audio_probe = probe(layer["path"], ffprobe)
            audio_streams = media_streams(audio_probe, "audio")
            if len(audio_streams) != 1 or media_streams(audio_probe, "video"):
                raise RuntimeError(f"{event['event']} {layer['request_id']} OGG stream contract failed")
            stream = audio_streams[0]
            if int(stream.get("sample_rate", 0)) != 48000 or int(stream.get("channels", 0)) not in {1, 2}:
                raise RuntimeError(f"{event['event']} {layer['request_id']} OGG format mismatch")
            audio_audits.append(
                {
                    "request_id": layer["request_id"],
                    "role": layer["role"],
                    "sample_rate": 48000,
                    "channels": int(stream["channels"]),
                }
            )
        audits.append(
            {
                "event": event["event"],
                "clean_visual": {
                    "codec": "h264",
                    "width": int(video["width"]),
                    "height": int(video["height"]),
                    "frame_rate": video["r_frame_rate"],
                    "frame_count": frame_count(video),
                    "video_packet_sha256": "",
                },
                "audio_sources": audio_audits,
            }
        )
    return audits


def build_event_pcm(
    event: Mapping[str, Any],
    *,
    output: Path,
    ffmpeg: str,
) -> dict[str, Any]:
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for layer in event["audio_layers"]:
        command.extend(["-i", str(layer["path"])])
    filters: list[str] = []
    labels: list[str] = []
    for index, layer in enumerate(event["audio_layers"]):
        label = f"a{index}"
        filters.append(
            f"[{index}:a:0]adelay={layer['start_ms']}:all=1,"
            "aresample=48000,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
            f"[{label}]"
        )
        labels.append(f"[{label}]")
    samples = int(event["presentation_samples"])
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.95,apad=whole_len={samples},"
        f"atrim=end_sample={samples},asetpts=N/SR/TB[mix]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[mix]",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(output),
        ]
    )
    run(command)
    expected_bytes = samples * 2 * 4
    if output.stat().st_size != expected_bytes:
        raise RuntimeError(
            f"{event['event']} PCM byte count mismatch: expected {expected_bytes}, "
            f"got {output.stat().st_size}"
        )
    return {
        "event": event["event"],
        "presentation_samples": samples,
        "byte_count": expected_bytes,
        "sha256": file_sha256(output),
    }


def concat_binary(sources: Sequence[Path], output: Path) -> None:
    with output.open("wb") as target:
        for source_path in sources:
            with source_path.open("rb") as source:
                shutil.copyfileobj(source, target, 1024 * 1024)


def ffconcat_quote(path: Path) -> str:
    value = path.resolve().as_posix().replace("'", "'\\''")
    return f"file '{value}'"


def subtitle_filter(layout: Mapping[str, Any], *, srt_path: str, fonts_dir: str) -> str:
    style = (
        f"FontName={layout['font_family']},FontSize={layout['font_size']},"
        f"PrimaryColour={layout['primary_colour']},"
        f"OutlineColour={layout['outline_colour']},"
        f"BorderStyle={layout['border_style']},Outline={layout['outline']},"
        f"Shadow={layout['shadow']},MarginV={layout['margin_v']},"
        f"MarginL={layout['margin_lr']},MarginR={layout['margin_lr']},Alignment=2"
    )
    return (
        f"subtitles=filename='{srt_path}':fontsdir='{fonts_dir}':charenc=UTF-8:"
        f"force_style='{style}'"
    )


def artifact(path: Path, root: Path) -> dict[str, str]:
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "sha256": file_sha256(path),
    }


def build_review_form(path: Path, *, resolved: Mapping[str, Any], video_name: str) -> None:
    text = f"""# {resolved['release_id']} 人工播放审查表

候选：`{video_name}`\u0020\u0020
公开规格名称：**无 BGM 中文字幕版（保留原始对白与音效）**\u0020\u0020
当前状态：自动 QA 已完成后才能填写；人工播放与 Bilibili 发布尚未批准。

请完整播放视频，并逐项填写：

- [ ] 画面完整，没有缺帧、黑帧或意外老虎机前景
- [ ] 事件顺序为 ac7114_001 → ac7115_001 → ac7116_001
- [ ] 三个事件边界自然，没有自动插入黑场
- [ ] 所有可验证对白均存在，角色与语音正确
- [ ] 原始 SE 正确，没有金带 request 1681
- [ ] 没有意外 BGM
- [ ] 中文字幕只有对白，没有“ごめんね…”图形文字、UI、标题或名牌
- [ ] 9 条中文意思、角色称呼和语气正确
- [ ] 字幕没有错字，换行自然
- [ ] 字幕没有遮挡人物面部或关键画面
- [ ] 字幕没有过长、闪现或异常重叠（两处官方短重叠除外）
- [ ] 音画同步
- [ ] 开头与结尾自然；尾帧 hold 与持续语音可接受

审核结论：

```text
HUMAN_PLAYBACK_APPROVED =
BILIBILI_RELEASE_READY =
需要修改：
```

注意：当前中文字幕与布局均为待项目所有者确认的候选；本表未填写前，
`EDITION_BUILD_READY.json` 中相应人工状态保持 `false`。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def verify_published_release(root: Path, resolved: Mapping[str, Any]) -> None:
    marker_path = root / "EDITION_BUILD_READY.json"
    marker = validate_build_ready_marker(read_json(marker_path))
    if marker["release_id"] != resolved["release_id"]:
        raise RuntimeError("published BUILD_READY release id mismatch")
    for row in marker["artifacts"].values():
        path = (root / safe_relative_path(row["path"], label="BUILD_READY artifact path")).resolve()
        ensure_resolved_containment(root, path, label="published artifact")
        if not path.is_file() or file_sha256(path) != row["sha256"]:
            raise RuntimeError(f"published artifact hash mismatch: {row['path']}")
    manifest_path = root / marker["artifacts"]["manifest"]["path"]
    manifest = read_json(manifest_path)
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("release_id") != resolved["release_id"]:
        raise RuntimeError("published release manifest identity mismatch")
    rehash_sources(resolved["source_snapshots"])


def promote_release(
    *,
    staging: Path,
    destination: Path,
    out_root: Path,
    overwrite: bool,
    resolved: Mapping[str, Any],
) -> None:
    ensure_resolved_containment(out_root, staging, label="release staging")
    ensure_resolved_containment(out_root, destination, label="release destination")
    backup = resolve_output_child(
        out_root,
        f".{resolved['release_id']}.backup.{uuid.uuid4().hex}",
        label="release backup",
    )
    had_previous = destination.exists()
    if had_previous and not overwrite:
        raise FileExistsError(f"release already exists: {destination}")
    try:
        if had_previous:
            destination.rename(backup)
        staging.rename(destination)
        verify_published_release(destination, resolved)
    except Exception:
        if destination.exists():
            ensure_resolved_containment(out_root, destination, label="failed release destination")
            shutil.rmtree(destination)
        if backup.exists():
            backup.rename(destination)
        raise
    else:
        if backup.exists():
            ensure_resolved_containment(out_root, backup, label="release backup cleanup")
            shutil.rmtree(backup)


def build_release(
    resolved: Mapping[str, Any],
    *,
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> Path:
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    destination = resolve_output_child(out_root, resolved["release_id"], label="release id")
    staging = resolve_output_child(
        out_root,
        f".{resolved['release_id']}.staging.{uuid.uuid4().hex}",
        label="release staging",
    )
    lock_path = resolve_output_child(
        out_root, f".{resolved['release_id']}.lock", label="release lock"
    )
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(f"another release build holds {lock_path}") from error
    os.close(lock_fd)
    try:
        if staging.exists():
            raise RuntimeError(f"unexpected pre-existing staging directory: {staging}")
        staging.mkdir(parents=False)
        work = staging / "work"
        work.mkdir()
        (work / "fonts").mkdir()
        staged_font = work / "fonts" / resolved["font_path"].name
        try:
            os.link(resolved["font_path"], staged_font)
        except OSError:
            shutil.copy2(resolved["font_path"], staged_font)

        source_media_audits = validate_source_media(resolved, ffprobe=ffprobe)
        for audit, event in zip(source_media_audits, resolved["events"]):
            audit["clean_visual"]["video_packet_sha256"] = packet_hash(
                event["paths"]["clean_visual"], kind="video", ffmpeg=ffmpeg
            )

        subtitle_path = staging / "subtitles" / f"{resolved['release_id']}__zh_dialogue.srt"
        write_srt(subtitle_path, resolved["scene_cues"])
        if parse_srt(subtitle_path) != [
            {"start_ms": cue["start_ms"], "end_ms": cue["end_ms"], "text": cue["zh_text"]}
            for cue in resolved["scene_cues"]
        ]:
            raise RuntimeError("written Chinese SRT failed cue round-trip")

        event_pcm_paths: list[Path] = []
        event_pcm_audits: list[dict[str, Any]] = []
        for event in resolved["events"]:
            event_pcm = work / f"{event['event']}.f32le"
            event_pcm_audits.append(
                build_event_pcm(event, output=event_pcm, ffmpeg=ffmpeg)
            )
            event_pcm_paths.append(event_pcm)
        scene_pcm = work / "scene_no_bgm.f32le"
        concat_binary(event_pcm_paths, scene_pcm)
        expected_pcm_bytes = int(resolved["expected"]["total_presentation_samples"]) * 8
        if scene_pcm.stat().st_size != expected_pcm_bytes:
            raise RuntimeError("scene PCM does not equal the exact presentation grid")
        scene_pcm_sha256 = file_sha256(scene_pcm)

        masters = staging / "masters"
        masters.mkdir()
        audio_master = masters / f"{resolved['release_id']}__no_bgm_audio_master.m4a"
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "f32le",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-i",
                str(scene_pcm),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(audio_master),
            ]
        )
        master_probe = probe(audio_master, ffprobe)
        master_audio_streams = media_streams(master_probe, "audio")
        if len(master_audio_streams) != 1:
            raise RuntimeError("AAC master lacks exactly one audio stream")
        expected_audio_samples = int(
            resolved["expected"]["total_presentation_samples"]
        )
        master_timeline = audio_gate._audio_packet_timeline(
            output=audio_master,
            audio_stream=master_audio_streams[0],
            expected_samples=expected_audio_samples,
            ffprobe=ffprobe,
        )
        master_pcm = audio_gate._effective_decoded_pcm_audit(
            output=audio_master,
            expected_samples=expected_audio_samples,
            ffmpeg=ffmpeg,
        )

        concat_list = work / "clean_visuals.ffconcat"
        concat_list.write_text(
            "ffconcat version 1.0\n"
            + "\n".join(
                ffconcat_quote(event["paths"]["clean_visual"])
                for event in resolved["events"]
            )
            + "\n",
            encoding="utf-8",
        )
        clean_scene = masters / f"{resolved['release_id']}__clean_visual_master.mp4"
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-map",
                "0:v:0",
                "-an",
                "-c:v",
                "copy",
                "-movflags",
                "+faststart",
                str(clean_scene),
            ]
        )
        clean_probe = probe(clean_scene, ffprobe)
        clean_videos = media_streams(clean_probe, "video")
        if len(clean_videos) != 1 or frame_count(clean_videos[0]) != resolved["expected"]["total_frames"]:
            raise RuntimeError("clean scene concat frame count mismatch")

        video_dir = staging / "video"
        video_dir.mkdir()
        final_video = video_dir / f"{resolved['release_id']}__no_bgm_zh.mp4"
        filter_value = subtitle_filter(
            resolved["layout"],
            srt_path=subtitle_path.relative_to(staging).as_posix(),
            fonts_dir=(work / "fonts").relative_to(staging).as_posix(),
        )
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                clean_scene.relative_to(staging).as_posix(),
                "-i",
                audio_master.relative_to(staging).as_posix(),
                "-vf",
                filter_value,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-frames:v",
                str(resolved["expected"]["total_frames"]),
                "-movflags",
                "+faststart",
                final_video.relative_to(staging).as_posix(),
            ],
            cwd=staging,
        )

        final_probe = probe(final_video, ffprobe)
        videos = media_streams(final_probe, "video")
        audios = media_streams(final_probe, "audio")
        subtitles = media_streams(final_probe, "subtitle")
        if len(videos) != 1 or len(audios) != 1 or subtitles:
            raise RuntimeError("final media stream count contract failed")
        video = videos[0]
        audio = audios[0]
        if (
            video.get("codec_name") != "h264"
            or int(video.get("width", 0)) != resolved["expected"]["width"]
            or int(video.get("height", 0)) != resolved["expected"]["height"]
            or video.get("r_frame_rate") != resolved["expected"]["frame_rate"]
            or frame_count(video) != resolved["expected"]["total_frames"]
        ):
            raise RuntimeError("final video native presentation contract failed")
        if (
            audio.get("codec_name") != "aac"
            or int(audio.get("sample_rate", 0)) != 48000
            or int(audio.get("channels", 0)) != 2
        ):
            raise RuntimeError("final AAC 48 kHz stereo contract failed")
        final_timeline = audio_gate._audio_packet_timeline(
            output=final_video,
            audio_stream=audio,
            expected_samples=expected_audio_samples,
            ffprobe=ffprobe,
        )
        final_pcm = audio_gate._effective_decoded_pcm_audit(
            output=final_video,
            expected_samples=expected_audio_samples,
            ffmpeg=ffmpeg,
        )
        if final_pcm != master_pcm:
            raise RuntimeError("final MP4 did not preserve the AAC master PCM exactly")
        if final_timeline["timeline_sha256"] != master_timeline["timeline_sha256"]:
            raise RuntimeError("final MP4 did not preserve the AAC presentation timeline")
        master_packet = packet_hash(audio_master, kind="audio", ffmpeg=ffmpeg)
        final_packet = packet_hash(final_video, kind="audio", ffmpeg=ffmpeg)
        if master_packet != final_packet:
            raise RuntimeError("final MP4 did not copy the AAC master packets exactly")
        volume = volume_audit(final_video, ffmpeg)
        if volume["max_volume_db"].lower() == "-inf" or float(volume["max_volume_db"]) > 0.5:
            raise RuntimeError("final audio is silent or exceeds the QA peak ceiling")
        oracle_regression = user_verified_audio_oracle_audit(
            final_video=final_video,
            events=resolved["events"],
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )

        review_frames_dir = staging / "review" / "layout_frames"
        review_frames_dir.mkdir(parents=True)
        frame_artifacts: list[dict[str, Any]] = []
        for index, cue in enumerate(resolved["scene_cues"], start=1):
            midpoint_ms = (int(cue["start_ms"]) + int(cue["end_ms"])) // 2
            frame_path = review_frames_dir / f"cue_{index:02d}.png"
            run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{midpoint_ms / 1000.0:.3f}",
                    "-i",
                    str(final_video),
                    "-frames:v",
                    "1",
                    str(frame_path),
                ]
            )
            frame_artifacts.append(
                {
                    "cue_index": index,
                    "midpoint_ms": midpoint_ms,
                    **artifact(frame_path, staging),
                }
            )

        review_form = staging / "review" / "HUMAN_PLAYBACK_REVIEW.md"
        build_review_form(review_form, resolved=resolved, video_name=final_video.name)
        video_bit_rate = stream_bit_rate(video, label="final video")
        audio_bit_rate = stream_bit_rate(audio, label="final audio")
        media = {
            "duration_ms": resolved["duration_ms"],
            "width": int(video["width"]),
            "height": int(video["height"]),
            "frame_rate": str(video["r_frame_rate"]),
            "video_codec": "h264",
            "video_bit_rate": video_bit_rate,
            "audio_codec": "aac",
            "audio_bit_rate": audio_bit_rate,
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "audio_channel_layout": str(audio.get("channel_layout") or "stereo"),
            "upscaled": False,
        }
        if not 300_000 <= video_bit_rate <= 8_000_000:
            raise RuntimeError(f"final H.264 bit rate is outside the native-scale QA range: {video_bit_rate}")

        # Raw PCM, the concat control file, and the staged font are build-only
        # products.  Their hashes are retained in QA, but the durable release
        # keeps only the reusable masters and review artifacts.
        ensure_resolved_containment(staging, work, label="release work cleanup")
        shutil.rmtree(work)
        rehash_sources(resolved["source_snapshots"])
        qa_path = staging / "qa" / "automated_qa.json"
        qa = {
            "schema": QA_SCHEMA,
            "status": "passed",
            "release_id": resolved["release_id"],
            "release_profile": RELEASE_PROFILE,
            "checks": {
                "source_hashes_verified_before_build": True,
                "source_hashes_verified_after_render": True,
                "explicit_event_order": True,
                "no_inserted_black_frames": True,
                "native_dimensions": True,
                "native_frame_rate": True,
                "exact_video_frame_count": True,
                "exact_audio_presentation_samples": True,
                "h264_reasonable_native_scale_bitrate": True,
                "aac_48000_stereo": True,
                "audio_encoded_once_then_packet_copied": True,
                "audio_master_and_final_packet_hash_equal": True,
                "audio_master_and_final_pcm_hash_equal": True,
                "user_verified_audio_oracle_regression": True,
                "bgm_layers_empty": True,
                "all_voice_and_se_sources_hash_bound": True,
                "gold_band_request_1681_excluded": True,
                "graphical_only_subtitle_excluded": True,
                "chinese_srt_round_trip": True,
                "dialogue_cue_count": len(resolved["scene_cues"]) == resolved["expected"]["dialogue_cue_count"],
                "no_upscale": True,
            },
            "expected": resolved["expected"],
            "media": media,
            "audio": {
                "policy": "no_bgm",
                "bgm_layers": [],
                "mix": "unity gain per official OGG; amix normalize=0; alimiter=0.95",
                "event_pcm": event_pcm_audits,
                "source_scene_pcm_f32le_sha256": scene_pcm_sha256,
                "master_audio_packet_sha256": master_packet,
                "final_audio_packet_sha256": final_packet,
                "master_audio_presentation_timeline": master_timeline,
                "final_audio_presentation_timeline": final_timeline,
                "master_decoded_pcm": master_pcm,
                "final_decoded_pcm": final_pcm,
                "volume": volume,
                "user_verified_oracle_regression": oracle_regression,
            },
            "video": {
                "source_events": source_media_audits,
                "clean_scene_packet_sha256": packet_hash(clean_scene, kind="video", ffmpeg=ffmpeg),
                "final_video_packet_sha256": packet_hash(final_video, kind="video", ffmpeg=ffmpeg),
                "final_frame_count": frame_count(video),
            },
            "subtitles": {
                "scope": "zh_dialogue_only",
                "cue_count": len(resolved["scene_cues"]),
                "srt_sha256": file_sha256(subtitle_path),
                "translation_status": "machine_draft_pending_owner",
                "layout_approval_status": resolved["layout"]["approval_status"],
            },
            "review_layout_frames": frame_artifacts,
            "warnings": [
                "Chinese translation and layout await project-owner review.",
                "Automated QA does not grant Bilibili release approval.",
                "This product intentionally excludes BGM and is not the complete original game mix.",
            ],
        }
        if not all(qa["checks"].values()):
            raise RuntimeError("one or more automated QA checks failed")
        write_json(qa_path, qa)

        manifest_path = staging / "manifests" / "scene_release_manifest.json"
        source_rows = [dict(row) for row in resolved["source_snapshots"]]
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": "AUTOMATED_QA_PASSED",
            "release_id": resolved["release_id"],
            "release_contract": resolved["release_contract"],
            "release_profile": resolved["release_contract"]["release_profile"],
            "audio_profile": resolved["release_contract"]["audio_profile"],
            "subtitle_profile": resolved["release_contract"]["subtitle_profile"],
            "release_scope": resolved["release_contract"]["release_scope"],
            "bgm_policy": resolved["release_contract"]["bgm_policy"],
            "voice_se_policy": resolved["release_contract"]["voice_se_policy"],
            "archive_complete": False,
            "six_edition_complete": False,
            "translation_status": "machine_draft_pending_owner",
            "human_review_status": "pending",
            "readiness": {
                "BUILD_READY": True,
                "AUTOMATED_QA_PASSED": True,
                "HUMAN_PLAYBACK_APPROVED": False,
                "BILIBILI_RELEASE_READY": False,
            },
            "publishable": False,
            "plan": {
                "path": str(resolved["plan_path"]),
                "sha256": resolved["plan_sha256"],
            },
            "ordered_events": [event["event"] for event in resolved["events"]],
            "timeline": [
                {
                    "event": event["event"],
                    "start_frame": event["start_frame"],
                    "end_frame": event["end_frame"],
                    "start_sample": event["start_sample"],
                    "end_sample": event["end_sample"],
                    "inserted_gap_frames": 0,
                }
                for event in resolved["events"]
            ],
            "media": media,
            "audio_contract": {
                "audio_profile": "no_bgm",
                "bgm_policy": "intentionally_excluded",
                "bgm_layers": [],
                "voice_se_policy": "preserve_verified_original",
                "mix_algorithm": "unity gain; amix normalize=0; alimiter=0.95; exact event sample trim/pad; one AAC encode",
                "layers": [
                    {
                        key: value
                        for key, value in layer.items()
                        if key != "path"
                    }
                    for event in resolved["events"]
                    for layer in event["audio_layers"]
                ],
                "user_verified_v19_oracles": [
                    {"event": event["event"], **event["oracle"]}
                    for event in resolved["events"]
                ],
                "user_verified_oracle_regression": oracle_regression,
            },
            "subtitle_contract": {
                "profile": "zh_dialogue_only",
                "cue_count": len(resolved["scene_cues"]),
                "cues": resolved["scene_cues"],
                "excluded_voice_requests": [
                    {"event": event["event"], **item}
                    for event in resolved["events"]
                    for item in event["excluded_voice_requests"]
                ],
                "excluded_source_cues": [
                    {"event": event["event"], **item}
                    for event in resolved["events"]
                    for item in event["excluded_source_cues"]
                ],
                "layout": {
                    "profile": resolved["layout"],
                    "path": str(resolved["layout_path"]),
                    "sha256": resolved["layout_sha256"],
                },
                "font": {
                    "family": resolved["layout"]["font_family"],
                    "path": str(resolved["font_path"]),
                    "sha256": resolved["font_sha256"],
                    "original_game_glyphs": False,
                },
            },
            "sources": source_rows,
            "artifacts": {
                "video": artifact(final_video, staging),
                "subtitles": artifact(subtitle_path, staging),
                "automated_qa": artifact(qa_path, staging),
                "human_review_form": artifact(review_form, staging),
                "no_bgm_audio_master": artifact(audio_master, staging),
                "clean_visual_master": artifact(clean_scene, staging),
                "layout_frames": frame_artifacts,
            },
        }
        write_json(manifest_path, manifest)

        ready_artifacts = {
            "video": {
                "path": final_video.relative_to(staging).as_posix(),
                "sha256": file_sha256(final_video),
            },
            "subtitles": {
                "path": subtitle_path.relative_to(staging).as_posix(),
                "sha256": file_sha256(subtitle_path),
            },
            "manifest": {
                "path": manifest_path.relative_to(staging).as_posix(),
                "sha256": file_sha256(manifest_path),
            },
            "qa_report": {
                "path": qa_path.relative_to(staging).as_posix(),
                "sha256": file_sha256(qa_path),
            },
        }
        marker = build_build_ready_marker(
            release_id=resolved["release_id"],
            ordered_events=resolved["expected"]["ordered_events"],
            dialogue_cue_count=resolved["expected"]["dialogue_cue_count"],
            media=media,
            artifacts=ready_artifacts,
        )
        write_json(staging / "EDITION_BUILD_READY.json", marker)
        validate_build_ready_marker(read_json(staging / "EDITION_BUILD_READY.json"))
        rehash_sources(resolved["source_snapshots"])
        promote_release(
            staging=staging,
            destination=destination,
            out_root=out_root,
            overwrite=overwrite,
            resolved=resolved,
        )
        return destination
    except Exception:
        if staging.exists():
            ensure_resolved_containment(out_root, staging, label="failed release staging")
            shutil.rmtree(staging)
        raise
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    roots = {
        "research": Path(args.research_root),
        "audio": Path(args.audio_root),
        "repo": Path(args.repo_root),
    }
    try:
        resolved = validate_plan(Path(args.plan), roots=roots)
        source_media = validate_source_media(resolved, ffprobe=args.ffprobe)
        if args.validate_only:
            print(
                json.dumps(
                    {
                        "status": "validated",
                        "release_id": resolved["release_id"],
                        "release_profile": RELEASE_PROFILE,
                        "ordered_events": resolved["expected"]["ordered_events"],
                        "total_frames": resolved["expected"]["total_frames"],
                        "total_presentation_samples": resolved["expected"]["total_presentation_samples"],
                        "dialogue_cue_count": len(resolved["scene_cues"]),
                        "source_file_count": len(resolved["source_snapshots"]),
                        "source_media": source_media,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        destination = build_release(
            resolved,
            out_root=Path(args.out_root),
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
            overwrite=args.overwrite,
        )
        marker_path = destination / "EDITION_BUILD_READY.json"
        print(
            json.dumps(
                {
                    "status": "AUTOMATED_QA_PASSED",
                    "release": str(destination),
                    "build_ready": str(marker_path),
                    "build_ready_sha256": file_sha256(marker_path),
                    "human_playback_approved": False,
                    "bilibili_release_ready": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
