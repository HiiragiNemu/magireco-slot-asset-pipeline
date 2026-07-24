#!/usr/bin/env python3
"""Fail-closed aggregate audit for v24 no-BGM family production batches.

The family builder publishes one ``BATCH_REVIEW_READY.json`` inside each
release directory.  This auditor deliberately treats that marker as an index,
not as proof: every listed artifact is re-hashed, the bound manifest and QA
report are cross-checked, and the actual media streams are inspected with
FFprobe.  Reports are written only after every batch and family passes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from . import build_audio_base_masters as audio_gate
    from .build_independent_scene_release import packet_hash
except ImportError:  # direct script execution
    import build_audio_base_masters as audio_gate  # type: ignore
    from build_independent_scene_release import packet_hash  # type: ignore


REPORT_SCHEMA = "magireco-no-bgm-mass-production-audit-v24"
BATCH_SCHEMA = "magireco-no-bgm-story-family-editions-batch-v1"
READY_SCHEMA = "magireco-no-bgm-story-family-editions-ready-v1"
MANIFEST_SCHEMA = "magireco-no-bgm-story-family-editions-v1"
QA_SCHEMA = "magireco-no-bgm-story-family-editions-qa-v1"
REQUIRED_EDITIONS = ("none", "ja", "zh")
FAMILY_NAME_PATTERN = r"ac[0-9]+(?:_[A-Za-z0-9]+)*"
RELEASE_DIR_RE = re.compile(
    rf"^{FAMILY_NAME_PATTERN}_full_no_bgm_editions_v[0-9]+$"
)
FAMILY_RE = re.compile(rf"^{FAMILY_NAME_PATTERN}$")
EVENT_RE = re.compile(r"^(ac[0-9]+)(?:_[0-9]+)+$")
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
SRT_TIMING_RE = re.compile(
    r"^(?P<start>\d{2,}:\d{2}:\d{2},\d{3})\s*-->\s*"
    r"(?P<end>\d{2,}:\d{2}:\d{2},\d{3})$"
)
REQUIRED_VOICE_SUBTITLE_BINDINGS = (
    {
        "event": "ac0911_010",
        "voice_request_id": "8041",
        "text": "私もチャレンジした方がいいのかな",
    },
    {
        "event": "ac5303_003",
        "voice_request_id": "5172",
        "text": "ふざけるなふざけるなふざけるな",
    },
)
REQUIRED_ARTIFACTS = frozenset(
    {
        "qa",
        "review_form",
        "clean_visual_master",
        "no_bgm_audio_master",
        "video_none",
        "video_ja",
        "video_zh",
        "subtitles_ja",
        "subtitles_zh",
        "manifest",
    }
)
REQUIRED_QA_CHECKS = frozenset(
    {
        "source_hashes_unchanged",
        "all_events_technical_ready",
        "clean_visual_master_shared",
        "no_bgm_layers_present",
        "retained_audio_roles_are_evidence_bound_voice_or_scene_se",
        "unresolved_audio_layer_count_zero",
        "audio_role_overrides_exact_hash_bound",
        "zero_inserted_black_frames",
        "native_dimensions_30fps_no_upscale",
        "exact_frame_and_sample_grid",
        "aac_encoded_once_and_packet_identical",
        "selected_srt_files_round_trip",
        "speaker_prefix_requires_cue_evidence",
        "human_and_publication_status_false",
    }
)
CSV_FIELDS = (
    "batch_root",
    "family_root",
    "release_id",
    "family",
    "status",
    "event_count",
    "dialogue_cue_count",
    "duration_ms",
    "width",
    "height",
    "frame_rate",
    "video_codec",
    "audio_codec",
    "audio_sample_rate",
    "audio_channels",
    "audio_layer_count",
    "voice_layer_count",
    "scene_se_layer_count",
    "unresolved_audio_layer_count",
    "video_none",
    "video_none_sha256",
    "video_ja",
    "video_ja_sha256",
    "video_zh",
    "video_zh_sha256",
    "manifest_sha256",
    "qa_sha256",
    "ready_sha256",
)


class AuditError(ValueError):
    """Raised whenever an input cannot be promoted by this audit."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AuditError(f"cannot read JSON {path}: {error}") from error
    _require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def file_sha256(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise AuditError(f"cannot hash artifact {path}: {error}") from error
    return digest.hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _sha256(value: Any, *, label: str) -> str:
    text = str(value)
    _require(bool(SHA256_RE.fullmatch(text)), f"{label} is not a SHA-256")
    return text.upper()


def _nonnegative_int(value: Any, *, label: str) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{label} is not a nonnegative integer",
    )
    return int(value)


def _positive_int(value: Any, *, label: str) -> int:
    result = _nonnegative_int(value, label=label)
    _require(result > 0, f"{label} must be positive")
    return result


def _nonnegative_number(value: Any, *, label: str) -> float:
    _require(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= 0,
        f"{label} is not a nonnegative number",
    )
    return float(value)


def _srt_time_ms(value: str, *, label: str) -> int:
    try:
        hours, minutes, remainder = value.split(":")
        seconds, milliseconds = remainder.split(",")
        parts = tuple(int(item) for item in (hours, minutes, seconds, milliseconds))
    except (TypeError, ValueError) as error:
        raise AuditError(f"{label} has an invalid SRT timestamp: {value!r}") from error
    hour, minute, second, millisecond = parts
    _require(
        hour >= 0
        and 0 <= minute < 60
        and 0 <= second < 60
        and 0 <= millisecond < 1000,
        f"{label} has an out-of-range SRT timestamp: {value!r}",
    )
    return hour * 3_600_000 + minute * 60_000 + second * 1000 + millisecond


def _parse_srt_strict(path: Path, *, label: str) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except (OSError, UnicodeError) as error:
        raise AuditError(f"cannot read {label}: {error}") from error
    stripped = text.strip()
    if not stripped:
        return []
    blocks = re.split(r"\n[ \t]*\n", stripped)
    cues: list[dict[str, Any]] = []
    for expected_index, block in enumerate(blocks, start=1):
        lines = block.split("\n")
        _require(len(lines) >= 3, f"{label} cue {expected_index} is incomplete")
        _require(
            lines[0].strip() == str(expected_index),
            f"{label} cue index differs at {expected_index}",
        )
        match = SRT_TIMING_RE.fullmatch(lines[1].strip())
        _require(match is not None, f"{label} cue {expected_index} timing is invalid")
        assert match is not None
        start_ms = _srt_time_ms(
            match.group("start"), label=f"{label} cue {expected_index} start"
        )
        end_ms = _srt_time_ms(
            match.group("end"), label=f"{label} cue {expected_index} end"
        )
        cue_text = "\n".join(lines[2:]).strip()
        _require(bool(cue_text), f"{label} cue {expected_index} text is blank")
        _require(
            end_ms > start_ms,
            f"{label} cue {expected_index} interval is not positive",
        )
        cues.append({"start_ms": start_ms, "end_ms": end_ms, "text": cue_text})
    return cues


def _audit_srt_pair(
    *,
    ja_path: Path,
    zh_path: Path,
    expected_cues: int,
    duration_ms: int,
) -> dict[str, Any]:
    ja = _parse_srt_strict(ja_path, label="Japanese SRT")
    zh = _parse_srt_strict(zh_path, label="Chinese SRT")
    _require(
        len(ja) == expected_cues,
        f"Japanese SRT cue count differs: expected {expected_cues}, got {len(ja)}",
    )
    _require(
        len(zh) == expected_cues,
        f"Chinese SRT cue count differs: expected {expected_cues}, got {len(zh)}",
    )
    ja_timing = [(row["start_ms"], row["end_ms"]) for row in ja]
    zh_timing = [(row["start_ms"], row["end_ms"]) for row in zh]
    _require(ja_timing == zh_timing, "Japanese/Chinese SRT cue timings differ")
    _require(
        all(end_ms <= duration_ms for _, end_ms in ja_timing),
        "subtitle cue extends beyond the family presentation duration",
    )
    return {
        "cue_count": expected_cues,
        "timing_sha256": canonical_sha256(ja_timing),
        "ja_text_sha256": canonical_sha256([row["text"] for row in ja]),
        "zh_text_sha256": canonical_sha256([row["text"] for row in zh]),
    }


def _audit_actual_audio(
    path: Path,
    *,
    expected_samples: int,
    ffmpeg: str,
    ffprobe: str,
    label: str,
) -> dict[str, Any]:
    try:
        actual_probe = run_ffprobe(path, ffprobe)
        streams = _streams(actual_probe, "audio", label=label)
        _require(len(streams) == 1, f"{label} does not have one audio stream")
        packet_sha256 = packet_hash(path, kind="audio", ffmpeg=ffmpeg)
        timeline = audio_gate._audio_packet_timeline(
            output=path,
            audio_stream=streams[0],
            expected_samples=expected_samples,
            ffprobe=ffprobe,
        )
        decoded_pcm = audio_gate._effective_decoded_pcm_audit(
            output=path,
            expected_samples=expected_samples,
            ffmpeg=ffmpeg,
        )
    except AuditError:
        raise
    except Exception as error:
        raise AuditError(f"{label} actual audio audit failed: {error}") from error
    return {
        "audio_packet_sha256": packet_sha256,
        "audio_timeline": timeline,
        "decoded_pcm": decoded_pcm,
    }


def _editions(value: Any, *, label: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{label} is not a list")
    result = tuple(str(item) for item in value)
    _require(
        result == REQUIRED_EDITIONS,
        f"{label} must be exactly {list(REQUIRED_EDITIONS)}, got {list(result)}",
    )
    return result


def _contained_file(root: Path, relative_value: Any, *, label: str) -> Path:
    relative = Path(str(relative_value))
    _require(not relative.is_absolute(), f"{label} path must be relative")
    try:
        resolved = (root / relative).resolve(strict=True)
    except OSError as error:
        raise AuditError(f"{label} is missing or inaccessible: {error}") from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise AuditError(f"{label} escapes family root: {relative_value}") from error
    _require(resolved.is_file(), f"{label} is not a file: {resolved}")
    return resolved


def run_ffprobe(path: Path, ffprobe: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        raise AuditError(f"cannot execute FFprobe {ffprobe!r}: {error}") from error
    if result.returncode != 0:
        raise AuditError(
            f"FFprobe failed for {path}: {result.stderr[-2000:].strip()}"
        )
    try:
        value = json.loads(result.stdout, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, AuditError) as error:
        raise AuditError(f"FFprobe returned invalid JSON for {path}: {error}") from error
    _require(isinstance(value, dict), f"FFprobe root is not an object: {path}")
    return value


def _streams(probe: Mapping[str, Any], kind: str, *, label: str) -> list[dict[str, Any]]:
    value = probe.get("streams")
    _require(isinstance(value, list), f"{label} has no FFprobe stream list")
    rows = [
        dict(row)
        for row in value
        if isinstance(row, Mapping) and row.get("codec_type") == kind
    ]
    return rows


def _frame_count(stream: Mapping[str, Any], *, label: str) -> int:
    for key in ("nb_read_frames", "nb_frames"):
        value = str(stream.get(key, ""))
        if value.isdigit():
            return int(value)
    raise AuditError(f"{label} lacks an exact FFprobe frame count")


def _validate_video_stream(
    stream: Mapping[str, Any],
    *,
    label: str,
    width: int,
    height: int,
    frame_count: int,
) -> None:
    _require(stream.get("codec_name") == "h264", f"{label} video is not H.264")
    _require(int(stream.get("width", 0)) == width, f"{label} width differs")
    _require(int(stream.get("height", 0)) == height, f"{label} height differs")
    _require(stream.get("r_frame_rate") == "30/1", f"{label} is not 30 fps")
    _require(
        _frame_count(stream, label=label) == frame_count,
        f"{label} frame count differs",
    )


def _validate_audio_stream(stream: Mapping[str, Any], *, label: str) -> None:
    _require(stream.get("codec_name") == "aac", f"{label} audio is not AAC")
    _require(int(stream.get("sample_rate", 0)) == 48000, f"{label} is not 48 kHz")
    _require(int(stream.get("channels", 0)) == 2, f"{label} is not stereo")


def _validate_media(
    path: Path,
    *,
    label: str,
    kind: str,
    width: int,
    height: int,
    frame_count: int,
    ffprobe: str,
    probe_func: Callable[[Path, str], Mapping[str, Any]],
) -> None:
    probe = probe_func(path, ffprobe)
    videos = _streams(probe, "video", label=label)
    audios = _streams(probe, "audio", label=label)
    subtitles = _streams(probe, "subtitle", label=label)
    all_streams = probe.get("streams")
    _require(isinstance(all_streams, list), f"{label} has no stream list")
    if kind == "edition":
        _require(
            len(videos) == 1
            and len(audios) == 1
            and not subtitles
            and len(all_streams) == 2,
            f"{label} stream contract differs",
        )
        _validate_video_stream(
            videos[0],
            label=label,
            width=width,
            height=height,
            frame_count=frame_count,
        )
        _validate_audio_stream(audios[0], label=label)
    elif kind == "clean_visual":
        _require(
            len(videos) == 1
            and not audios
            and not subtitles
            and len(all_streams) == 1,
            f"{label} clean-visual stream contract differs",
        )
        _validate_video_stream(
            videos[0],
            label=label,
            width=width,
            height=height,
            frame_count=frame_count,
        )
    elif kind == "audio_master":
        _require(
            not videos
            and len(audios) == 1
            and not subtitles
            and len(all_streams) == 1,
            f"{label} audio-master stream contract differs",
        )
        _validate_audio_stream(audios[0], label=label)
    else:
        raise AuditError(f"unsupported media audit kind {kind!r}")


def _summary_family_dirs(
    batch_root: Path, summary: Mapping[str, Any]
) -> tuple[Path, ...]:
    raw_families = summary.get("families")
    _require(
        isinstance(raw_families, list) and raw_families,
        f"{batch_root} summary has no families",
    )
    resolved: list[Path] = []
    for index, raw in enumerate(raw_families):
        candidate = Path(str(raw))
        if not candidate.is_absolute():
            candidate = batch_root / candidate
        try:
            family_root = candidate.resolve(strict=True)
        except OSError as error:
            raise AuditError(
                f"{batch_root} summary family {index} is inaccessible: {error}"
            ) from error
        _require(
            family_root.parent == batch_root,
            f"{batch_root} summary family is not a direct child: {family_root}",
        )
        _require(
            RELEASE_DIR_RE.fullmatch(family_root.name) is not None,
            f"{batch_root} summary family has invalid release name: {family_root.name}",
        )
        _require(family_root not in resolved, f"duplicate family path: {family_root}")
        resolved.append(family_root)

    discovered = {
        child.resolve()
        for child in batch_root.iterdir()
        if child.is_dir() and RELEASE_DIR_RE.fullmatch(child.name)
    }
    _require(
        set(resolved) == discovered,
        f"{batch_root} summary/discovered family sets differ: "
        f"summary={sorted(str(path) for path in resolved)}, "
        f"discovered={sorted(str(path) for path in discovered)}",
    )
    return tuple(sorted(resolved, key=lambda path: path.name))


def _artifact_paths(
    family_root: Path, marker: Mapping[str, Any]
) -> tuple[dict[str, Path], dict[str, str]]:
    artifacts = marker.get("artifacts")
    _require(isinstance(artifacts, dict), f"{family_root} READY lacks artifacts")
    _require(
        set(artifacts) == REQUIRED_ARTIFACTS,
        f"{family_root} READY artifact set differs: "
        f"missing={sorted(REQUIRED_ARTIFACTS - set(artifacts))}, "
        f"extra={sorted(set(artifacts) - REQUIRED_ARTIFACTS)}",
    )
    expected_set_hash = _sha256(
        marker.get("artifact_set_sha256"),
        label=f"{family_root} artifact_set_sha256",
    )
    _require(
        canonical_sha256(artifacts) == expected_set_hash,
        f"{family_root} artifact set hash differs",
    )

    paths: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    seen_paths: set[Path] = set()
    for name, raw in artifacts.items():
        _require(
            isinstance(name, str) and name,
            f"{family_root} has an invalid artifact name",
        )
        _require(
            isinstance(raw, Mapping) and set(raw) == {"path", "sha256"},
            f"{family_root} artifact {name} fields differ",
        )
        path = _contained_file(
            family_root,
            raw["path"],
            label=f"{family_root.name} artifact {name}",
        )
        _require(path not in seen_paths, f"{family_root} artifact path is duplicated: {path}")
        seen_paths.add(path)
        expected = _sha256(
            raw["sha256"],
            label=f"{family_root.name} artifact {name} SHA-256",
        )
        actual = file_sha256(path)
        _require(
            actual == expected,
            f"{family_root} artifact {name} SHA-256 differs: "
            f"expected {expected}, got {actual}",
        )
        paths[name] = path
        hashes[name] = actual
    return paths, hashes


def _validate_timeline(
    manifest: Mapping[str, Any], qa: Mapping[str, Any], *, label: str
) -> tuple[int, int, int]:
    events = manifest.get("ordered_events")
    timeline = manifest.get("timeline")
    _require(isinstance(events, list) and events, f"{label} has no ordered events")
    _require(
        len(events) == len(set(str(event) for event in events)),
        f"{label} has duplicate ordered events",
    )
    _require(
        isinstance(timeline, list) and len(timeline) == len(events),
        f"{label} timeline/event counts differ",
    )
    _require(qa.get("events") == events, f"{label} QA event order differs")
    _require(qa.get("timeline") == timeline, f"{label} QA timeline differs")

    expected_frame = 0
    expected_sample = 0
    for index, (event, row) in enumerate(zip(events, timeline, strict=True)):
        _require(isinstance(row, Mapping), f"{label} timeline row {index} is invalid")
        _require(row.get("event") == event, f"{label} timeline event order differs")
        start_frame = _nonnegative_int(
            row.get("start_frame"), label=f"{label} timeline start_frame"
        )
        end_frame = _positive_int(
            row.get("end_frame"), label=f"{label} timeline end_frame"
        )
        start_sample = _nonnegative_int(
            row.get("start_sample"), label=f"{label} timeline start_sample"
        )
        end_sample = _positive_int(
            row.get("end_sample"), label=f"{label} timeline end_sample"
        )
        gap = _nonnegative_int(
            row.get("inserted_gap_frames"), label=f"{label} inserted_gap_frames"
        )
        _require(gap == 0, f"{label} contains inserted black/gap frames")
        _require(
            start_frame == expected_frame and end_frame > start_frame,
            f"{label} frame timeline is not contiguous",
        )
        _require(
            start_sample == expected_sample and end_sample > start_sample,
            f"{label} sample timeline is not contiguous",
        )
        expected_frame = end_frame
        expected_sample = end_sample
    _require(
        expected_sample == expected_frame * 1600,
        f"{label} final 30 fps / 48 kHz grid differs",
    )
    return len(events), expected_frame, expected_sample


def _audit_family(
    batch_root: Path,
    family_root: Path,
    *,
    ffmpeg: str,
    ffprobe: str,
    probe_func: Callable[[Path, str], Mapping[str, Any]],
) -> dict[str, Any]:
    marker_path = family_root / "BATCH_REVIEW_READY.json"
    _require(marker_path.is_file(), f"{family_root} lacks BATCH_REVIEW_READY.json")
    marker = read_json(marker_path)
    marker_hash = file_sha256(marker_path)
    _require(marker.get("schema") == READY_SCHEMA, f"{family_root} READY schema differs")
    _require(
        marker.get("status") == "AUTOMATED_QA_PASSED",
        f"{family_root} READY status is not passed",
    )
    release_id = str(marker.get("release_id", ""))
    family = str(marker.get("family", ""))
    _require(release_id == family_root.name, f"{family_root} release ID differs")
    _require(FAMILY_RE.fullmatch(family) is not None, f"{family_root} family is invalid")
    _editions(marker.get("selected_editions"), label=f"{family_root} READY editions")
    _require(
        marker.get("readiness", {}).get("AUTOMATED_QA_PASSED") is True,
        f"{family_root} READY readiness is false",
    )

    artifact_paths, artifact_hashes = _artifact_paths(family_root, marker)
    manifest = read_json(artifact_paths["manifest"])
    qa = read_json(artifact_paths["qa"])

    _require(
        manifest.get("schema") == MANIFEST_SCHEMA,
        f"{family_root} manifest schema differs",
    )
    _require(
        manifest.get("status") == "AUTOMATED_QA_PASSED",
        f"{family_root} manifest status is not passed",
    )
    _require(manifest.get("release_id") == release_id, f"{family_root} manifest release differs")
    _require(manifest.get("family") == family, f"{family_root} manifest family differs")
    _editions(
        manifest.get("selected_editions"),
        label=f"{family_root} manifest editions",
    )
    _require(manifest.get("audio_profile") == "no_bgm", f"{family_root} is not no_bgm")
    _require(
        manifest.get("bgm_policy") == "intentionally_excluded",
        f"{family_root} BGM policy differs",
    )
    _require(
        manifest.get("voice_se_policy") == "preserve_verified_evidence_bound_original",
        f"{family_root} voice/SE policy differs",
    )
    _require(
        manifest.get("artifacts")
        == {
            key: value
            for key, value in marker["artifacts"].items()
            if key != "manifest"
        },
        f"{family_root} manifest/READY artifact maps differ",
    )
    _require(
        manifest.get("readiness", {}).get("AUTOMATED_QA_PASSED") is True,
        f"{family_root} manifest readiness is false",
    )

    media = manifest.get("media")
    _require(isinstance(media, Mapping), f"{family_root} manifest lacks media")
    width = _positive_int(media.get("width"), label=f"{family_root} width")
    height = _positive_int(media.get("height"), label=f"{family_root} height")
    _require(media.get("frame_rate") == "30/1", f"{family_root} manifest is not 30 fps")
    _require(media.get("video_codec") == "h264", f"{family_root} manifest is not H.264")
    _require(media.get("audio_codec") == "aac", f"{family_root} manifest is not AAC")
    _require(
        media.get("audio_sample_rate") == 48000,
        f"{family_root} manifest is not 48 kHz",
    )
    _require(media.get("audio_channels") == 2, f"{family_root} manifest is not stereo")
    _require(media.get("upscaled") is False, f"{family_root} claims upscaling")
    bit_rates = media.get("edition_video_bit_rates")
    _require(
        isinstance(bit_rates, Mapping) and set(bit_rates) == set(REQUIRED_EDITIONS),
        f"{family_root} edition bit-rate map differs",
    )
    for edition in REQUIRED_EDITIONS:
        _positive_int(bit_rates[edition], label=f"{family_root} {edition} video bit rate")

    _require(qa.get("schema") == QA_SCHEMA, f"{family_root} QA schema differs")
    _require(qa.get("status") == "passed", f"{family_root} QA status is not passed")
    _require(qa.get("family") == family, f"{family_root} QA family differs")
    _editions(qa.get("selected_editions"), label=f"{family_root} QA editions")
    checks = qa.get("checks")
    _require(isinstance(checks, Mapping), f"{family_root} QA checks are missing")
    _require(
        REQUIRED_QA_CHECKS.issubset(checks),
        f"{family_root} QA lacks required checks: "
        f"{sorted(REQUIRED_QA_CHECKS - set(checks))}",
    )
    _require(
        all(value is True for value in checks.values()),
        f"{family_root} QA contains a non-passing check",
    )

    role_counts = qa.get("audio_role_counts")
    _require(isinstance(role_counts, Mapping), f"{family_root} QA lacks audio role counts")
    _require(
        set(role_counts) == {"voice", "scene_se", "unsubtitled_audio"},
        f"{family_root} QA audio role keys differ",
    )
    voice_count = _nonnegative_int(
        role_counts["voice"], label=f"{family_root} voice role count"
    )
    scene_se_count = _nonnegative_int(
        role_counts["scene_se"], label=f"{family_root} scene-SE role count"
    )
    unresolved_count = _nonnegative_int(
        role_counts["unsubtitled_audio"],
        label=f"{family_root} unresolved role count",
    )
    _require(unresolved_count == 0, f"{family_root} has unresolved audio layers")
    audio_layer_count = _positive_int(
        qa.get("audio_layer_count"), label=f"{family_root} audio layer count"
    )
    _require(
        voice_count + scene_se_count == audio_layer_count,
        f"{family_root} audio role counts do not sum to layer count",
    )

    event_count, total_frames, total_samples = _validate_timeline(
        manifest, qa, label=str(family_root)
    )
    _require(
        qa.get("total_frames") == total_frames,
        f"{family_root} QA total frame count differs",
    )
    _require(
        qa.get("total_presentation_samples") == total_samples,
        f"{family_root} QA total sample count differs",
    )
    duration_ms = round(total_samples * 1000 / 48000)
    _require(qa.get("duration_ms") == duration_ms, f"{family_root} QA duration differs")
    _require(media.get("duration_ms") == duration_ms, f"{family_root} media duration differs")
    dialogue_cue_count = _nonnegative_int(
        manifest.get("dialogue_cue_count"),
        label=f"{family_root} dialogue cue count",
    )
    _require(
        qa.get("dialogue_cue_count") == dialogue_cue_count,
        f"{family_root} QA dialogue cue count differs",
    )
    subtitle_audit = _audit_srt_pair(
        ja_path=artifact_paths["subtitles_ja"],
        zh_path=artifact_paths["subtitles_zh"],
        expected_cues=dialogue_cue_count,
        duration_ms=duration_ms,
    )

    media_audits = qa.get("edition_media_audits")
    _require(
        isinstance(media_audits, Mapping)
        and set(media_audits) == set(REQUIRED_EDITIONS),
        f"{family_root} QA edition media audits differ",
    )
    master_packet_hash = _sha256(
        qa.get("audio_master_packet_sha256"),
        label=f"{family_root} audio master packet SHA-256",
    )
    for edition in REQUIRED_EDITIONS:
        audit = media_audits[edition]
        _require(
            isinstance(audit, Mapping),
            f"{family_root} {edition} media audit is invalid",
        )
        _require(
            audit.get("frame_count") == total_frames,
            f"{family_root} {edition} QA frame count differs",
        )
        _require(
            _sha256(
                audit.get("audio_packet_sha256"),
                label=f"{family_root} {edition} audio packet SHA-256",
            )
            == master_packet_hash,
            f"{family_root} {edition} audio packet identity differs",
        )

    for edition in REQUIRED_EDITIONS:
        _validate_media(
            artifact_paths[f"video_{edition}"],
            label=f"{family} {edition}",
            kind="edition",
            width=width,
            height=height,
            frame_count=total_frames,
            ffprobe=ffprobe,
            probe_func=probe_func,
        )
    _validate_media(
        artifact_paths["clean_visual_master"],
        label=f"{family} clean visual master",
        kind="clean_visual",
        width=width,
        height=height,
        frame_count=total_frames,
        ffprobe=ffprobe,
        probe_func=probe_func,
    )
    _validate_media(
        artifact_paths["no_bgm_audio_master"],
        label=f"{family} no-BGM audio master",
        kind="audio_master",
        width=width,
        height=height,
        frame_count=total_frames,
        ffprobe=ffprobe,
        probe_func=probe_func,
    )
    actual_master_audio = _audit_actual_audio(
        artifact_paths["no_bgm_audio_master"],
        expected_samples=total_samples,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        label=f"{family} no-BGM audio master",
    )
    _require(
        actual_master_audio["audio_packet_sha256"] == master_packet_hash,
        f"{family_root} actual audio-master packet SHA-256 differs from QA",
    )
    _require(
        qa.get("audio_master_timeline") == actual_master_audio["audio_timeline"],
        f"{family_root} actual audio-master timeline differs from QA",
    )
    _require(
        qa.get("audio_master_decoded_pcm") == actual_master_audio["decoded_pcm"],
        f"{family_root} actual audio-master decoded PCM differs from QA",
    )
    actual_edition_audio: dict[str, dict[str, Any]] = {}
    for edition in REQUIRED_EDITIONS:
        actual = _audit_actual_audio(
            artifact_paths[f"video_{edition}"],
            expected_samples=total_samples,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            label=f"{family} {edition}",
        )
        _require(
            actual == actual_master_audio,
            f"{family_root} {edition} actual audio differs from the master",
        )
        declared = media_audits[edition]
        _require(
            declared.get("audio_packet_sha256")
            == actual["audio_packet_sha256"],
            f"{family_root} {edition} actual audio packet SHA-256 differs from QA",
        )
        _require(
            declared.get("audio_timeline") == actual["audio_timeline"],
            f"{family_root} {edition} actual audio timeline differs from QA",
        )
        _require(
            declared.get("decoded_pcm") == actual["decoded_pcm"],
            f"{family_root} {edition} actual decoded PCM differs from QA",
        )
        actual_edition_audio[edition] = actual
    for name, path in artifact_paths.items():
        _require(
            file_sha256(path) == artifact_hashes[name],
            f"{family_root} artifact {name} changed during audit",
        )
    _require(
        file_sha256(marker_path) == marker_hash,
        f"{family_root} READY changed during audit",
    )

    edition_videos = {
        edition: {
            "path": str(artifact_paths[f"video_{edition}"]),
            "sha256": artifact_hashes[f"video_{edition}"],
        }
        for edition in REQUIRED_EDITIONS
    }
    return {
        "batch_root": str(batch_root),
        "family_root": str(family_root),
        "release_id": release_id,
        "family": family,
        "status": "passed",
        "selected_editions": list(REQUIRED_EDITIONS),
        "ordered_events": list(manifest["ordered_events"]),
        "event_count": event_count,
        "dialogue_cue_count": dialogue_cue_count,
        "duration_ms": duration_ms,
        "total_frames": total_frames,
        "total_presentation_samples": total_samples,
        "width": width,
        "height": height,
        "frame_rate": "30/1",
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "audio_layer_count": audio_layer_count,
        "audio_role_counts": {
            "voice": voice_count,
            "scene_se": scene_se_count,
            "unsubtitled_audio": unresolved_count,
        },
        "subtitle_audit": subtitle_audit,
        "actual_audio_master_audit": actual_master_audio,
        "actual_edition_audio_audits": actual_edition_audio,
        "edition_videos": edition_videos,
        "manifest": {
            "path": str(artifact_paths["manifest"]),
            "sha256": artifact_hashes["manifest"],
        },
        "qa": {
            "path": str(artifact_paths["qa"]),
            "sha256": artifact_hashes["qa"],
        },
        "ready": {"path": str(marker_path), "sha256": marker_hash},
    }


def _audit_required_voice_binding(
    manifest_path: Path,
    manifest: Mapping[str, Any],
    expected: Mapping[str, str],
) -> dict[str, Any]:
    event = expected["event"]
    request_id = expected["voice_request_id"]
    label = f"{event} request {request_id}"
    audio = manifest.get("audio")
    subtitles = manifest.get("subtitles")
    _require(isinstance(audio, list), f"{manifest_path} lacks an audio list")
    _require(isinstance(subtitles, list), f"{manifest_path} lacks a subtitle list")

    audio_rows = [
        row
        for row in audio
        if isinstance(row, Mapping)
        and str(row.get("request_id", "")).strip() == request_id
    ]
    subtitle_rows = [
        row
        for row in subtitles
        if isinstance(row, Mapping)
        and str(row.get("voice_request_id", "")).strip() == request_id
    ]
    _require(len(audio_rows) == 1, f"{label} does not have one exact audio row")
    _require(
        len(subtitle_rows) == 1,
        f"{label} does not have one exact voice-bound subtitle row",
    )
    audio_row = audio_rows[0]
    subtitle_row = subtitle_rows[0]
    _require(
        audio_row.get("source") in {"z2d_req_sound", "event_audio_component"},
        f"{label} audio source is not evidence-bound",
    )
    _require(
        bool(str(audio_row.get("path", "")).strip()),
        f"{label} audio path is blank",
    )
    _require(
        bool(str(audio_row.get("evidence", "")).strip()),
        f"{label} audio evidence is blank",
    )
    audio_start = _nonnegative_number(
        audio_row.get("start_ms"), label=f"{label} audio start"
    )
    audio_duration = _nonnegative_number(
        audio_row.get("duration_ms"), label=f"{label} audio duration"
    )
    _require(audio_duration > 0, f"{label} audio duration is not positive")

    _require(
        str(subtitle_row.get("text", "")).strip() == expected["text"],
        f"{label} verified subtitle text differs",
    )
    _require(
        subtitle_row.get("subtitle_source") == "official_voice_asr_verified",
        f"{label} subtitle source is not official_voice_asr_verified",
    )
    _require(
        bool(str(subtitle_row.get("speaker_code", "")).strip()),
        f"{label} subtitle speaker is blank",
    )
    _require(
        bool(str(subtitle_row.get("evidence", "")).strip()),
        f"{label} subtitle evidence is blank",
    )
    subtitle_start = _nonnegative_number(
        subtitle_row.get("start_ms"), label=f"{label} subtitle start"
    )
    subtitle_end = _nonnegative_number(
        subtitle_row.get("end_ms"), label=f"{label} subtitle end"
    )
    voice_start = _nonnegative_number(
        subtitle_row.get("voice_start_ms"), label=f"{label} voice start"
    )
    _require(subtitle_end > subtitle_start, f"{label} subtitle interval is invalid")
    _require(
        voice_start == audio_start,
        f"{label} subtitle voice start does not bind to its audio row",
    )
    _require(
        subtitle_start >= voice_start,
        f"{label} subtitle starts before its bound voice",
    )

    reconciliation = manifest.get("reviewed_subtitle_reconciliation")
    reconciliation_accepted = False
    if reconciliation:
        _require(
            isinstance(reconciliation, Mapping),
            f"{label} subtitle reconciliation is invalid",
        )
        accepted = reconciliation.get(
            "accepted_current_voice_override_candidates", []
        )
        excluded = reconciliation.get("excluded_current_voice_candidates", [])
        _require(
            isinstance(accepted, list) and isinstance(excluded, list),
            f"{label} subtitle reconciliation candidate lists are invalid",
        )
        accepted_rows = [
            row
            for row in accepted
            if isinstance(row, Mapping)
            and str(row.get("voice_request_id", "")).strip() == request_id
        ]
        excluded_rows = [
            row
            for row in excluded
            if isinstance(row, Mapping)
            and str(row.get("voice_request_id", "")).strip() == request_id
        ]
        _require(
            not excluded_rows,
            f"{label} is still listed as an excluded current voice candidate",
        )
        if accepted_rows:
            _require(
                len(accepted_rows) == 1
                and str(accepted_rows[0].get("text", "")).strip()
                == expected["text"],
                f"{label} accepted reconciliation candidate differs",
            )
            reconciliation_accepted = True

    return {
        "event": event,
        "voice_request_id": request_id,
        "text": expected["text"],
        "speaker_code": str(subtitle_row["speaker_code"]).strip(),
        "subtitle_source": str(subtitle_row["subtitle_source"]),
        "subtitle_evidence": str(subtitle_row["evidence"]).strip(),
        "audio_source": str(audio_row["source"]),
        "audio_start_ms": audio_start,
        "audio_duration_ms": audio_duration,
        "subtitle_start_ms": subtitle_start,
        "subtitle_end_ms": subtitle_end,
        "reconciliation_accepted_current_candidate": reconciliation_accepted,
        "event_manifest_path": str(manifest_path),
        "event_manifest_sha256": file_sha256(manifest_path),
    }


def _audit_manifest_roots(
    manifest_roots: Sequence[Path],
    *,
    audited_events: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _require(bool(manifest_roots), "at least one event-production manifest root is required")
    resolved_roots: list[Path] = []
    for raw_root in manifest_roots:
        try:
            root = Path(raw_root).resolve(strict=True)
        except OSError as error:
            raise AuditError(
                f"event-production manifest root is inaccessible: {raw_root}: {error}"
            ) from error
        _require(root.is_dir(), f"manifest root is not a directory: {root}")
        _require(root not in resolved_roots, f"duplicate manifest root: {root}")
        resolved_roots.append(root)

    root_rows: list[dict[str, Any]] = []
    event_records: dict[str, tuple[Path, dict[str, Any], str]] = {}
    for root in resolved_roots:
        summary_path = root / "event_production_summary.json"
        events_dir = root / "events"
        _require(
            summary_path.is_file(),
            f"{root} lacks event_production_summary.json",
        )
        _require(events_dir.is_dir(), f"{root} lacks an events directory")
        summary = read_json(summary_path)
        summary_hash = file_sha256(summary_path)
        event_count = _positive_int(
            summary.get("events"), label=f"{root} summary events"
        )
        ready_count = _nonnegative_int(
            summary.get("ready_events"), label=f"{root} summary ready events"
        )
        failed_count = _nonnegative_int(
            summary.get("failed_events"), label=f"{root} summary failed events"
        )
        _require(
            ready_count == event_count and failed_count == 0,
            f"{root} is not an all-ready event-production manifest root",
        )
        paths = sorted(events_dir.glob("*.json"), key=lambda path: path.name)
        _require(
            len(paths) == event_count,
            f"{root} summary/event-manifest counts differ",
        )
        root_hashes: dict[str, str] = {}
        for event_path in paths:
            event = event_path.stem
            _require(
                EVENT_RE.fullmatch(event) is not None,
                f"{event_path} has an invalid event name",
            )
            _require(event not in event_records, f"duplicate event across manifest roots: {event}")
            manifest = read_json(event_path)
            _require(
                manifest.get("event") == event,
                f"{event_path} event identity differs",
            )
            gates = manifest.get("quality_gates")
            _require(
                isinstance(gates, Mapping),
                f"{event_path} lacks quality gates",
            )
            for gate in (
                "all_clips_exist",
                "all_clip_source_hashes_bound",
                "all_audio_exist",
                "composition_resolved",
                "audio_timeline_ready",
                "render_ready",
                "ready",
            ):
                _require(
                    gates.get(gate) is True,
                    f"{event_path} quality gate {gate} is not true",
                )
            errors = gates.get("errors")
            _require(
                isinstance(errors, list) and not errors,
                f"{event_path} has production errors",
            )
            digest = file_sha256(event_path)
            event_records[event] = (event_path, manifest, digest)
            root_hashes[event] = digest
        _require(
            file_sha256(summary_path) == summary_hash,
            f"{summary_path} changed during audit",
        )
        root_rows.append(
            {
                "path": str(root),
                "summary_path": str(summary_path),
                "summary_sha256": summary_hash,
                "event_count": event_count,
                "ready_event_count": ready_count,
                "failed_event_count": failed_count,
                "event_manifest_set_sha256": canonical_sha256(root_hashes),
            }
        )

    accepted: list[dict[str, Any]] = []
    for expected in REQUIRED_VOICE_SUBTITLE_BINDINGS:
        event = expected["event"]
        _require(
            event in audited_events,
            f"required voice-subtitle event is absent from audited batches: {event}",
        )
        _require(
            event in event_records,
            f"required voice-subtitle event is absent from manifest roots: {event}",
        )
        event_path, manifest, _ = event_records[event]
        accepted.append(
            _audit_required_voice_binding(event_path, manifest, expected)
        )

    for event, (path, _manifest, digest) in event_records.items():
        _require(
            file_sha256(path) == digest,
            f"{event} event manifest changed during audit",
        )
    return root_rows, accepted


def audit_batch_roots(
    batch_roots: Sequence[Path],
    *,
    manifest_roots: Sequence[Path] = (),
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    probe_func: Callable[[Path, str], Mapping[str, Any]] = run_ffprobe,
) -> dict[str, Any]:
    _require(bool(batch_roots), "at least one batch root is required")
    resolved_roots: list[Path] = []
    for raw_root in batch_roots:
        try:
            root = Path(raw_root).resolve(strict=True)
        except OSError as error:
            raise AuditError(f"batch root is inaccessible: {raw_root}: {error}") from error
        _require(root.is_dir(), f"batch root is not a directory: {root}")
        _require(root not in resolved_roots, f"duplicate batch root: {root}")
        resolved_roots.append(root)

    family_rows: list[dict[str, Any]] = []
    batch_rows: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    seen_releases: set[str] = set()
    for root in resolved_roots:
        summary_path = root / "BATCH_SUMMARY.json"
        _require(summary_path.is_file(), f"{root} lacks BATCH_SUMMARY.json")
        summary = read_json(summary_path)
        summary_hash = file_sha256(summary_path)
        _require(summary.get("schema") == BATCH_SCHEMA, f"{root} batch schema differs")
        _require(
            summary.get("status") == "AUTOMATED_QA_PASSED",
            f"{root} batch status is not passed",
        )
        _editions(summary.get("selected_editions"), label=f"{root} batch editions")
        family_dirs = _summary_family_dirs(root, summary)
        start_count = len(family_rows)
        for family_root in family_dirs:
            row = _audit_family(
                root,
                family_root,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                probe_func=probe_func,
            )
            _require(
                row["family"] not in seen_families,
                f"duplicate family across batch roots: {row['family']}",
            )
            _require(
                row["release_id"] not in seen_releases,
                f"duplicate release across batch roots: {row['release_id']}",
            )
            seen_families.add(row["family"])
            seen_releases.add(row["release_id"])
            family_rows.append(row)
        _require(
            file_sha256(summary_path) == summary_hash,
            f"{root} BATCH_SUMMARY.json changed during audit",
        )
        batch_rows.append(
            {
                "path": str(root),
                "summary_path": str(summary_path),
                "summary_sha256": summary_hash,
                "family_count": len(family_rows) - start_count,
            }
        )

    family_rows.sort(key=lambda row: (row["family"], row["release_id"]))
    audited_events = {
        event for row in family_rows for event in row["ordered_events"]
    }
    manifest_root_rows, accepted_voice_candidates = _audit_manifest_roots(
        manifest_roots,
        audited_events=audited_events,
    )
    dimension_counts: dict[str, int] = {}
    for row in family_rows:
        key = f"{row['width']}x{row['height']}"
        dimension_counts[key] = dimension_counts.get(key, 0) + 1
    return {
        "schema": REPORT_SCHEMA,
        "status": "passed",
        "required_editions": list(REQUIRED_EDITIONS),
        "batch_root_count": len(batch_rows),
        "manifest_root_count": len(manifest_root_rows),
        "family_count": len(family_rows),
        "event_count": sum(row["event_count"] for row in family_rows),
        "edition_video_count": len(family_rows) * len(REQUIRED_EDITIONS),
        "total_duration_ms": sum(row["duration_ms"] for row in family_rows),
        "total_frames": sum(row["total_frames"] for row in family_rows),
        "total_presentation_samples": sum(
            row["total_presentation_samples"] for row in family_rows
        ),
        "native_dimension_counts": dict(sorted(dimension_counts.items())),
        "legacy_reviewed_subtitle_reconciliation_qa_used": False,
        "accepted_current_voice_override_candidates": accepted_voice_candidates,
        "batches": batch_rows,
        "manifest_roots": manifest_root_rows,
        "families": family_rows,
    }


def _csv_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family in report["families"]:
        videos = family["edition_videos"]
        rows.append(
            {
                "batch_root": family["batch_root"],
                "family_root": family["family_root"],
                "release_id": family["release_id"],
                "family": family["family"],
                "status": family["status"],
                "event_count": family["event_count"],
                "dialogue_cue_count": family["dialogue_cue_count"],
                "duration_ms": family["duration_ms"],
                "width": family["width"],
                "height": family["height"],
                "frame_rate": family["frame_rate"],
                "video_codec": family["video_codec"],
                "audio_codec": family["audio_codec"],
                "audio_sample_rate": family["audio_sample_rate"],
                "audio_channels": family["audio_channels"],
                "audio_layer_count": family["audio_layer_count"],
                "voice_layer_count": family["audio_role_counts"]["voice"],
                "scene_se_layer_count": family["audio_role_counts"]["scene_se"],
                "unresolved_audio_layer_count": family["audio_role_counts"][
                    "unsubtitled_audio"
                ],
                "video_none": videos["none"]["path"],
                "video_none_sha256": videos["none"]["sha256"],
                "video_ja": videos["ja"]["path"],
                "video_ja_sha256": videos["ja"]["sha256"],
                "video_zh": videos["zh"]["path"],
                "video_zh_sha256": videos["zh"]["sha256"],
                "manifest_sha256": family["manifest"]["sha256"],
                "qa_sha256": family["qa"]["sha256"],
                "ready_sha256": family["ready"]["sha256"],
            }
        )
    return rows


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_reports(report: Mapping[str, Any], *, json_path: Path, csv_path: Path) -> None:
    json_path = json_path.resolve()
    csv_path = csv_path.resolve()
    _require(json_path != csv_path, "JSON and CSV output paths must differ")
    json_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_csv_rows(report))
    _atomic_write(json_path, json_text)
    _atomic_write(csv_path, buffer.getvalue())


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-root", action="append", required=True)
    parser.add_argument("--manifest-root", action="append", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = audit_batch_roots(
            [Path(value) for value in args.batch_root],
            manifest_roots=[Path(value) for value in args.manifest_root],
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
        )
        write_reports(
            report,
            json_path=Path(args.out_json),
            csv_path=Path(args.out_csv),
        )
    except Exception as error:
        print(f"v24 no-BGM aggregate audit failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schema": REPORT_SCHEMA,
                "status": "passed",
                "batch_root_count": report["batch_root_count"],
                "manifest_root_count": report["manifest_root_count"],
                "family_count": report["family_count"],
                "edition_video_count": report["edition_video_count"],
                "out_json": str(Path(args.out_json).resolve()),
                "out_csv": str(Path(args.out_csv).resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
