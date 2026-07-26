#!/usr/bin/env python3
"""Build the seventeen hash-bound ac4902 selector-entry routes.

This builder is deliberately narrower than ``build_mature_416_route_batch``:

* it accepts only the proven DirInfo kind-113 selector-entry route partition;
* it adds the three omitted entry events (005, 014 and 017) from exact,
  hash-bound native video and direct-parent action-SE sources;
* it proves the 056/057/058 aliases from the evidence catalogs before use;
* it renders every retained route independently as none/JA/ZH; and
* it never produces a cross-route showcase or overwrites an existing output.

The corrected v26 family master remains the sole source for event 001 and the
outcome events.  Entry events are silent except for their exact direct-parent
action SE at sample zero.  Child-local audio or subtitle rows make the plan
fail closed before rendering.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_mature_416_route_batch as mature
except ImportError:  # direct script execution
    import build_mature_416_route_batch as mature  # type: ignore


PLAN_SCHEMA = "magireco-ac4902-selector-entry-route-plan-v1"
MANIFEST_SCHEMA = "magireco-ac4902-selector-entry-route-batch-v1"
ROUTE_MANIFEST_SCHEMA = "magireco-ac4902-selector-entry-route-v1"
QA_SCHEMA = "magireco-ac4902-selector-entry-route-qa-v1"
BATCH_ID = "ac4902_selector_entry_routes_v1"
STATUS = "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
PARTIAL_STATUS = "PARTIAL_ROUTE_FAILURE_HUMAN_PLAYBACK_REQUIRED"
COMPOSITION_CLAIM = "independent_native_dirinfo_routes_no_showcase"
UPLOAD_POLICY = "source_and_uploaded_media_read_only_never_overwrite"
EDITIONS = ("none", "ja", "zh")

FPS = mature.FPS
WIDTH = mature.WIDTH
HEIGHT = mature.HEIGHT
SAMPLE_RATE = mature.SAMPLE_RATE
SAMPLES_PER_FRAME = mature.SAMPLES_PER_FRAME


# The source sequence is fixed to the selected kind-113 rows.  Rows that are
# exact audience aliases are declared separately below and are not rendered a
# second time.
EXPECTED_CANONICAL_ROUTES: dict[int, tuple[tuple[str, ...], tuple[str, ...]]] = {
    14: (
        ("ac4902_001", "ac4902_005", "ac4902_006"),
        ("ac4902_001", "ac4902_005", "ac4902_006"),
    ),
    15: (
        ("ac4902_001", "ac4902_005", "ac4902_007"),
        ("ac4902_001", "ac4902_005", "ac4902_007"),
    ),
    16: (
        ("ac4902_001", "ac4902_005", "ac4902_008"),
        ("ac4902_001", "ac4902_005", "ac4902_008"),
    ),
    17: (
        ("ac4902_001", "ac4902_005", "ac4902_009"),
        ("ac4902_001", "ac4902_005", "ac4902_009"),
    ),
    24: (
        ("ac4902_001", "ac4902_005", "ac4902_010"),
        ("ac4902_001", "ac4902_005", "ac4902_010"),
    ),
    25: (
        ("ac4902_001", "ac4902_005", "ac4902_011"),
        ("ac4902_001", "ac4902_005", "ac4902_011"),
    ),
    26: (
        ("ac4902_001", "ac4902_005", "ac4902_012"),
        ("ac4902_001", "ac4902_005", "ac4902_012"),
    ),
    27: (
        ("ac4902_001", "ac4902_005", "ac4902_013"),
        ("ac4902_001", "ac4902_005", "ac4902_013"),
    ),
    34: (
        ("ac4902_054", "ac4902_056", "ac4902_062"),
        ("ac4902_001", "ac4902_005", "ac4902_062"),
    ),
    35: (
        ("ac4902_054", "ac4902_056", "ac4902_063"),
        ("ac4902_001", "ac4902_005", "ac4902_063"),
    ),
    37: (
        ("ac4902_054", "ac4902_056", "ac4902_065"),
        ("ac4902_001", "ac4902_005", "ac4902_065"),
    ),
    44: (
        ("ac4902_001", "ac4902_014", "ac4902_015"),
        ("ac4902_001", "ac4902_014", "ac4902_015"),
    ),
    45: (
        ("ac4902_001", "ac4902_014", "ac4902_029"),
        ("ac4902_001", "ac4902_014", "ac4902_029"),
    ),
    46: (
        ("ac4902_001", "ac4902_014", "ac4902_016"),
        ("ac4902_001", "ac4902_014", "ac4902_016"),
    ),
    55: (
        ("ac4902_054", "ac4902_057", "ac4902_072"),
        ("ac4902_001", "ac4902_014", "ac4902_072"),
    ),
    58: (
        ("ac4902_001", "ac4902_017", "ac4902_018"),
        ("ac4902_001", "ac4902_017", "ac4902_018"),
    ),
    59: (
        ("ac4902_001", "ac4902_017", "ac4902_019"),
        ("ac4902_001", "ac4902_017", "ac4902_019"),
    ),
}

EXPECTED_DUPLICATE_ROWS: dict[int, tuple[int, tuple[str, ...]]] = {
    36: (16, ("ac4902_054", "ac4902_056", "ac4902_064")),
    38: (24, ("ac4902_054", "ac4902_056", "ac4902_066")),
    39: (25, ("ac4902_054", "ac4902_056", "ac4902_067")),
    40: (26, ("ac4902_054", "ac4902_056", "ac4902_068")),
    41: (27, ("ac4902_054", "ac4902_056", "ac4902_069")),
    53: (44, ("ac4902_054", "ac4902_057", "ac4902_070")),
    54: (45, ("ac4902_054", "ac4902_057", "ac4902_071")),
    66: (58, ("ac4902_054", "ac4902_058", "ac4902_073")),
    67: (59, ("ac4902_054", "ac4902_058", "ac4902_074")),
}

ENTRY_CONTRACTS: dict[str, dict[str, Any]] = {
    "ac4902_005": {
        "alias": "ac4902_056",
        "frames": 603,
        "main_frames": 153,
        "loop_frames": 450,
        "request_id": 1691,
        "sound_code": 8155,
        "duration_ms": 1112,
        "source_samples": 53377,
        "parent_code_name": "8155_さな_ﾌｪﾘｼｱ_移動中_005",
    },
    "ac4902_014": {
        "alias": "ac4902_057",
        "frames": 100,
        "main_frames": 70,
        "loop_frames": 30,
        "request_id": 1698,
        "sound_code": 8163,
        "duration_ms": 3351,
        "source_samples": 160885,
        "parent_code_name": "8163_やちよ_走る_014",
    },
    "ac4902_017": {
        "alias": "ac4902_058",
        "frames": 189,
        "main_frames": 10,
        "loop_frames": 179,
        "request_id": 1702,
        "sound_code": 8167,
        "duration_ms": 3816,
        "source_samples": 183190,
        "parent_code_name": "8167_鶴乃_歩く_017",
    },
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _artifact_path(family_root: Path, row: Mapping[str, Any]) -> Path:
    return mature._artifact_path(family_root, row)


def _validate_bound_sources(
    plan: Mapping[str, Any], *, plan_path: Path
) -> tuple[dict[str, Path], list[dict[str, str]]]:
    plan_dir = plan_path.parent
    bound: dict[str, Path] = {}
    snapshots: list[dict[str, str]] = []
    labels = {
        "dirinfo": "DirInfo route evidence",
        "family_manifest": "corrected v26 ac4902 family manifest",
        "clean_visual_master": "corrected v26 ac4902 clean visual master",
        "no_bgm_audio_master": "corrected v26 ac4902 no-BGM audio master",
        "subtitles_ja": "corrected v26 ac4902 Japanese subtitles",
        "subtitles_zh": "corrected v26 ac4902 Chinese subtitles",
        "subtitle_layout": "416x232 subtitle layout",
        "font": "audited subtitle font",
        "deduplication_proposal": "ac4902 exact audience duplicate proposal",
        "direct_parent_audio_catalog": "direct-parent audio catalog",
        "child_audio_timeline": "child Z2D audio timeline",
        "subtitle_event_timeline": "subtitle event timeline",
        "audience_event_catalog": "audience event clip catalog",
    }
    for key, label in labels.items():
        value = plan.get(key)
        if not isinstance(value, Mapping):
            raise ValueError(f"plan lacks hash binding: {key}")
        path, snapshot = mature.validate_bound_file(
            value, label=label, plan_dir=plan_dir
        )
        bound[key] = path
        snapshots.append(snapshot)
    return bound, snapshots


def validate_corrected_family(
    *,
    bound: Mapping[str, Path],
    ffprobe: str,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, list[dict[str, Any]]]]:
    manifest = mature.read_json(bound["family_manifest"])
    if (
        manifest.get("schema") != "magireco-no-bgm-story-family-editions-v1"
        or manifest.get("family") != "ac4902"
        or manifest.get("media", {}).get("width") != WIDTH
        or manifest.get("media", {}).get("height") != HEIGHT
        or manifest.get("media", {}).get("frame_rate") != "30/1"
    ):
        raise ValueError("corrected v26 family manifest identity differs")

    family_root = bound["family_manifest"].parent.parent
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("corrected v26 family manifest lacks artifacts")
    for plan_key, artifact_key in (
        ("clean_visual_master", "clean_visual_master"),
        ("no_bgm_audio_master", "no_bgm_audio_master"),
        ("subtitles_ja", "subtitles_ja"),
        ("subtitles_zh", "subtitles_zh"),
    ):
        artifact = artifacts.get(artifact_key)
        if not isinstance(artifact, Mapping):
            raise ValueError(f"corrected family artifact is missing: {artifact_key}")
        if (
            _artifact_path(family_root, artifact).resolve() != bound[plan_key]
            or str(artifact.get("sha256", "")).upper()
            != mature.file_sha256(bound[plan_key])
        ):
            raise ValueError(f"plan binding differs from family artifact: {plan_key}")

    values = manifest.get("timeline")
    if not isinstance(values, list) or not values:
        raise ValueError("corrected family timeline is empty")
    timeline_by_event: dict[str, Mapping[str, Any]] = {}
    previous_frame = previous_sample = 0
    for row in values:
        if not isinstance(row, Mapping):
            raise ValueError("corrected family timeline row is invalid")
        event = str(row["event"])
        if event in timeline_by_event:
            raise ValueError(f"duplicate corrected family event: {event}")
        start_frame = int(row["start_frame"])
        end_frame = int(row["end_frame"])
        start_sample = int(row["start_sample"])
        end_sample = int(row["end_sample"])
        if (
            start_frame != previous_frame
            or start_sample != previous_sample
            or end_frame <= start_frame
            or end_sample - start_sample
            != (end_frame - start_frame) * SAMPLES_PER_FRAME
        ):
            raise ValueError("corrected family timeline is not cumulative on grid")
        timeline_by_event[event] = row
        previous_frame = end_frame
        previous_sample = end_sample

    mature.validate_video_grid(
        bound["clean_visual_master"],
        expected_frames=previous_frame,
        ffprobe=ffprobe,
        label="corrected v26 ac4902 clean visual master",
    )
    mature._validate_audio_master(bound["no_bgm_audio_master"], ffprobe=ffprobe)

    cues = {
        "ja": mature.parse_srt(bound["subtitles_ja"]),
        "zh": mature.parse_srt(bound["subtitles_zh"]),
    }
    validate_kuroba_subtitles(cues["zh"])
    return timeline_by_event, cues


def validate_kuroba_subtitles(cues: Sequence[Mapping[str, Any]]) -> None:
    target = [
        str(row["text"]).replace(" ", "")
        for row in cues
        if "可恶" in str(row["text"])
    ]
    if target != ["黑羽：可恶！", "黑羽：可恶！"]:
        raise ValueError(
            "corrected ZH source must preserve exactly two 黑羽：可恶！ cues"
        )


def _rows_for_events(
    rows: Sequence[Mapping[str, str]], events: set[str]
) -> dict[str, list[Mapping[str, str]]]:
    output = {event: [] for event in events}
    for row in rows:
        event = str(row.get("event_name", row.get("primary_animation", "")))
        if event in output:
            output[event].append(row)
    return output


def validate_entry_video_source(
    path: Path,
    *,
    expected_frames: int,
    ffprobe: str,
    label: str,
) -> dict[str, Any]:
    """Validate a raw CRI clip while explicitly ignoring bound embedded audio.

    Two ac4902_014 clips carry a native ALAC stream.  The route contract uses
    only stream 0 video and reconstructs audio from the separately hash-bound
    direct-parent OGG, so accepting arbitrary extra audio would be unsafe.
    """

    value = mature.probe(path, ffprobe)
    videos = mature.media_streams(value, "video")
    audios = mature.media_streams(value, "audio")
    if (
        len(videos) != 1
        or mature.media_streams(value, "subtitle")
        or len(audios) > 1
    ):
        raise RuntimeError(f"{label} stream contract failed: {path}")
    video = videos[0]
    if (
        video.get("codec_name") != "h264"
        or int(video.get("width", 0)) != WIDTH
        or int(video.get("height", 0)) != HEIGHT
        or video.get("r_frame_rate") != "30/1"
        or mature.frame_count(video) != expected_frames
    ):
        raise RuntimeError(f"{label} native video grid differs")
    if audios:
        audio = audios[0]
        if (
            audio.get("codec_name") != "alac"
            or int(audio.get("sample_rate", 0)) != SAMPLE_RATE
            or int(audio.get("channels", 0)) != 2
        ):
            raise RuntimeError(f"{label} unexpected embedded audio differs")
    return {
        "codec": "h264",
        "width": WIDTH,
        "height": HEIGHT,
        "frame_rate": "30/1",
        "frame_count": expected_frames,
        "sha256": mature.file_sha256(path),
        "embedded_audio": (
            None
            if not audios
            else {
                "codec": "alac",
                "sample_rate": SAMPLE_RATE,
                "channels": 2,
                "production_disposition": (
                    "ignored_use_separately_hash_bound_direct_parent_ogg"
                ),
            }
        ),
    }


def validate_entry_evidence(
    *,
    entries: Sequence[Mapping[str, Any]],
    bound: Mapping[str, Path],
    plan_dir: Path,
    ffprobe: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    if len(entries) != len(ENTRY_CONTRACTS):
        raise ValueError("entry plan must contain exactly 005, 014 and 017")
    by_event: dict[str, Mapping[str, Any]] = {}
    for row in entries:
        if not isinstance(row, Mapping):
            raise ValueError("entry event declaration must be an object")
        event = str(row.get("event", ""))
        if event in by_event:
            raise ValueError(f"duplicate entry declaration: {event}")
        by_event[event] = row
    if set(by_event) != set(ENTRY_CONTRACTS):
        raise ValueError("entry event identities differ")

    all_events = set(ENTRY_CONTRACTS)
    all_events.update(value["alias"] for value in ENTRY_CONTRACTS.values())
    direct_rows = _rows_for_events(
        _read_csv(bound["direct_parent_audio_catalog"]), all_events
    )
    child_rows = _rows_for_events(
        _read_csv(bound["child_audio_timeline"]), all_events
    )
    subtitle_rows = _rows_for_events(
        _read_csv(bound["subtitle_event_timeline"]), all_events
    )
    audience_rows = _rows_for_events(
        _read_csv(bound["audience_event_catalog"]), all_events
    )

    resolved: dict[str, dict[str, Any]] = {}
    snapshots: list[dict[str, str]] = []
    for event, contract in ENTRY_CONTRACTS.items():
        raw = by_event[event]
        aliases = raw.get("exact_aliases")
        if aliases != [contract["alias"]]:
            raise ValueError(f"{event} exact alias declaration differs")
        for key in (
            "frames",
            "request_id",
            "sound_code",
            "action_start_ms",
        ):
            expected = 0 if key == "action_start_ms" else contract[key]
            if int(raw.get(key, -1)) != expected:
                raise ValueError(f"{event} {key} differs")

        clip_paths: dict[str, Path] = {}
        for source_key, expected_frames in (
            ("main_clip", contract["main_frames"]),
            ("loop_clip", contract["loop_frames"]),
        ):
            source = raw.get(source_key)
            if not isinstance(source, Mapping):
                raise ValueError(f"{event} lacks {source_key}")
            if int(source.get("frames", -1)) != expected_frames:
                raise ValueError(f"{event} {source_key} frame declaration differs")
            path, snapshot = mature.validate_bound_file(
                {"path": source["path"], "sha256": source["sha256"]},
                label=f"{event} {source_key}",
                plan_dir=plan_dir,
            )
            validate_entry_video_source(
                path,
                expected_frames=expected_frames,
                ffprobe=ffprobe,
                label=f"{event} {source_key}",
            )
            clip_paths[source_key] = path
            snapshots.append(snapshot)
        if contract["main_frames"] + contract["loop_frames"] != contract["frames"]:
            raise AssertionError(f"internal entry frame contract differs: {event}")

        ogg = raw.get("ogg")
        if not isinstance(ogg, Mapping):
            raise ValueError(f"{event} lacks OGG binding")
        if int(ogg.get("source_samples", -1)) != contract["source_samples"]:
            raise ValueError(f"{event} OGG source sample declaration differs")
        ogg_path, snapshot = mature.validate_bound_file(
            {"path": ogg["path"], "sha256": ogg["sha256"]},
            label=f"{event} direct-parent action SE",
            plan_dir=plan_dir,
        )
        snapshots.append(snapshot)
        ogg_probe = mature.probe(ogg_path, ffprobe)
        audio_streams = mature.media_streams(ogg_probe, "audio")
        if (
            len(audio_streams) != 1
            or mature.media_streams(ogg_probe, "video")
            or mature.media_streams(ogg_probe, "subtitle")
        ):
            raise RuntimeError(f"{event} OGG stream contract differs")
        audio = audio_streams[0]
        if (
            audio.get("codec_name") != "vorbis"
            or int(audio.get("sample_rate", 0)) != SAMPLE_RATE
            or int(audio.get("channels", 0)) != 2
            or int(audio.get("duration_ts", -1)) != contract["source_samples"]
        ):
            raise RuntimeError(f"{event} OGG native sample grid differs")

        canonical = direct_rows[event]
        alias = direct_rows[contract["alias"]]
        if len(canonical) != 1 or len(alias) != 1:
            raise ValueError(f"{event} and its alias need one direct-parent row each")
        exact_audio_tuple = (
            str(contract["request_id"]),
            str(contract["sound_code"]),
            "0",
            str(contract["duration_ms"]),
            ogg_path.name,
            contract["parent_code_name"],
        )
        for evidence_event, rows in ((event, canonical), (contract["alias"], alias)):
            row = rows[0]
            actual_tuple = (
                str(row["parent_request_id"]),
                str(row["leaf_sound_code"]),
                str(row["start_ms"]),
                str(row["duration_ms"]),
                str(row["ogg_name"]),
                str(row["parent_code_name"]),
            )
            if (
                actual_tuple != exact_audio_tuple
                or row.get("smz_matches_leaf_request") != "yes"
                or row.get("ogg_duration_match") != "yes"
            ):
                raise ValueError(
                    f"{evidence_event} direct-parent action SE evidence differs"
                )
        if child_rows[event] or child_rows[contract["alias"]]:
            raise ValueError(f"{event} child-local audio evidence is not empty")
        if subtitle_rows[event] or subtitle_rows[contract["alias"]]:
            raise ValueError(f"{event} child-local subtitle evidence is not empty")

        canonical_audience = validate_audience_entry_rows(
            event=event,
            rows=audience_rows[event],
            contract=contract,
            clip_paths=clip_paths,
        )
        alias_audience = validate_audience_entry_rows(
            event=contract["alias"],
            rows=audience_rows[contract["alias"]],
            contract=contract,
            clip_paths=clip_paths,
        )
        if canonical_audience != alias_audience:
            raise ValueError(f"{event} audience alias presentation differs")

        resolved[event] = {
            "event": event,
            "alias": contract["alias"],
            "frames": contract["frames"],
            "samples": contract["frames"] * SAMPLES_PER_FRAME,
            "main_clip": clip_paths["main_clip"],
            "loop_clip": clip_paths["loop_clip"],
            "main_frames": contract["main_frames"],
            "loop_frames": contract["loop_frames"],
            "ogg": ogg_path,
            "source_samples": contract["source_samples"],
            "request_id": contract["request_id"],
            "sound_code": contract["sound_code"],
            "action_start_sample": 0,
            "audience_intervals": canonical_audience,
        }
    return resolved, snapshots


def validate_audience_entry_rows(
    *,
    event: str,
    rows: Sequence[Mapping[str, str]],
    contract: Mapping[str, Any],
    clip_paths: Mapping[str, Path],
) -> tuple[tuple[str, int, int], ...]:
    if len(rows) != 2:
        raise ValueError(f"{event} must have exactly two audience clip rows")
    ordered = sorted(rows, key=lambda row: int(row["dgm_order"]))
    expected = (
        (0, clip_paths["main_clip"], 0, int(contract["main_frames"])),
        (
            1,
            clip_paths["loop_clip"],
            int(contract["main_frames"]),
            int(contract["frames"]),
        ),
    )
    audit: list[tuple[str, int, int]] = []
    for row, (order, path, start_frame, end_frame) in zip(ordered, expected):
        start_ms = mature.milliseconds_for_samples(start_frame * SAMPLES_PER_FRAME)
        end_ms = mature.milliseconds_for_samples(end_frame * SAMPLES_PER_FRAME)
        if (
            int(row["dgm_order"]) != order
            or row["dgm_name"] != path.stem
            or int(row["event_start_ms"]) != start_ms
            or int(row["event_end_ms"]) != end_ms
            or row["interval_confidence"] != "exact_duration_unique"
            or int(row["width"]) != WIDTH
            or int(row["height"]) != HEIGHT
            or row["frame_rate"] != "30/1"
        ):
            raise ValueError(f"{event} audience interval evidence differs")
        audit.append((row["dgm_name"], start_frame, end_frame))
    return tuple(audit)


def validate_route_declarations(
    *,
    routes_raw: Any,
    duplicate_rows_raw: Any,
    source_routes: Mapping[int, Sequence[str]],
    aliases: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(routes_raw, list) or len(routes_raw) != len(
        EXPECTED_CANONICAL_ROUTES
    ):
        raise ValueError("route plan must contain exactly seventeen routes")
    if not isinstance(duplicate_rows_raw, list) or len(duplicate_rows_raw) != len(
        EXPECTED_DUPLICATE_ROWS
    ):
        raise ValueError("duplicate row plan must contain exactly nine rows")

    routes: list[dict[str, Any]] = []
    route_ids: set[str] = set()
    by_source_row: dict[int, dict[str, Any]] = {}
    for raw in routes_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("route declaration must be an object")
        route_id = str(raw.get("route_id", ""))
        if (
            not route_id
            or route_id in route_ids
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
                for character in route_id
            )
        ):
            raise ValueError(f"unsafe or duplicate route id: {route_id}")
        source = raw.get("source_row")
        if not isinstance(source, Mapping):
            raise ValueError(f"{route_id} lacks one source_row")
        row_index = int(source.get("row_index", -1))
        if row_index not in EXPECTED_CANONICAL_ROUTES or row_index in by_source_row:
            raise ValueError(f"{route_id} canonical DirInfo row differs")
        expected_raw, expected_render = EXPECTED_CANONICAL_ROUTES[row_index]
        raw_sequence = tuple(str(value) for value in source.get("raw_event_sequence", []))
        render_sequence = tuple(
            str(value) for value in raw.get("render_event_sequence", [])
        )
        if (
            raw_sequence != expected_raw
            or tuple(source_routes.get(row_index, ())) != expected_raw
            or render_sequence != expected_render
            or tuple(mature.normalize_sequence(raw_sequence, aliases))
            != expected_render
        ):
            raise ValueError(f"{route_id} canonical route evidence differs")
        row = {
            "route_id": route_id,
            "title": str(raw.get("title", "")).strip(),
            "source_row": {
                "row_index": row_index,
                "raw_event_sequence": list(raw_sequence),
                "normalized_event_sequence": list(expected_render),
            },
            "render_event_sequence": list(render_sequence),
        }
        if not row["title"]:
            raise ValueError(f"{route_id} title is empty")
        routes.append(row)
        by_source_row[row_index] = row
        route_ids.add(route_id)
    if set(by_source_row) != set(EXPECTED_CANONICAL_ROUTES):
        raise ValueError("canonical route row partition differs")

    duplicates: list[dict[str, Any]] = []
    seen_duplicate_rows: set[int] = set()
    for raw in duplicate_rows_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("duplicate row declaration must be an object")
        row_index = int(raw.get("row_index", -1))
        if row_index not in EXPECTED_DUPLICATE_ROWS or row_index in seen_duplicate_rows:
            raise ValueError(f"duplicate DirInfo row differs: {row_index}")
        canonical_row, expected_raw = EXPECTED_DUPLICATE_ROWS[row_index]
        raw_sequence = tuple(str(value) for value in raw.get("raw_event_sequence", []))
        canonical_route_id = str(raw.get("canonical_route_id", ""))
        canonical = by_source_row[canonical_row]
        if (
            raw_sequence != expected_raw
            or tuple(source_routes.get(row_index, ())) != expected_raw
            or canonical_route_id != canonical["route_id"]
            or tuple(mature.normalize_sequence(raw_sequence, aliases))
            != tuple(canonical["render_event_sequence"])
        ):
            raise ValueError(f"row {row_index} is not the declared exact duplicate")
        duplicates.append(
            {
                "row_index": row_index,
                "raw_event_sequence": list(raw_sequence),
                "normalized_event_sequence": canonical["render_event_sequence"],
                "canonical_source_row": canonical_row,
                "canonical_route_id": canonical_route_id,
                "disposition": "exact_audience_alias_not_rendered_twice",
            }
        )
        seen_duplicate_rows.add(row_index)
    if seen_duplicate_rows != set(EXPECTED_DUPLICATE_ROWS):
        raise ValueError("duplicate route row partition differs")

    routes.sort(key=lambda row: int(row["source_row"]["row_index"]))
    duplicates.sort(key=lambda row: int(row["row_index"]))
    return routes, duplicates


def mixed_route_timeline(
    events: Sequence[str],
    *,
    family_timeline: Mapping[str, Mapping[str, Any]],
    entry_events: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    frame_cursor = sample_cursor = 0
    for event in events:
        if event in entry_events:
            frames = int(entry_events[event]["frames"])
            source_kind = "hash_bound_entry_event"
            source_start_frame = source_start_sample = 0
            source_end_frame = frames
            source_end_sample = frames * SAMPLES_PER_FRAME
        elif event in family_timeline:
            source = family_timeline[event]
            source_start_frame = int(source["start_frame"])
            source_end_frame = int(source["end_frame"])
            source_start_sample = int(source["start_sample"])
            source_end_sample = int(source["end_sample"])
            frames = source_end_frame - source_start_frame
            source_kind = "corrected_v26_family_master"
        else:
            raise ValueError(f"route event has no exact source: {event}")
        samples = source_end_sample - source_start_sample
        if frames <= 0 or samples != frames * SAMPLES_PER_FRAME:
            raise ValueError(f"{event} does not lie on the frame/sample grid")
        rows.append(
            {
                "event": event,
                "source_kind": source_kind,
                "start_frame": frame_cursor,
                "end_frame": frame_cursor + frames,
                "start_sample": sample_cursor,
                "end_sample": sample_cursor + samples,
                "source_start_frame": source_start_frame,
                "source_end_frame": source_end_frame,
                "source_start_sample": source_start_sample,
                "source_end_sample": source_end_sample,
            }
        )
        frame_cursor += frames
        sample_cursor += samples
    return rows, frame_cursor, sample_cursor


def mixed_route_subtitle_cues(
    events: Sequence[str],
    *,
    family_timeline: Mapping[str, Mapping[str, Any]],
    source_cues: Sequence[Mapping[str, Any]],
    entry_events: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    destination_sample = 0
    for event in events:
        if event in entry_events:
            destination_sample += int(entry_events[event]["samples"])
            continue
        if event not in family_timeline:
            raise ValueError(f"subtitle route event has no exact source: {event}")
        source = family_timeline[event]
        source_start_sample = int(source["start_sample"])
        source_end_sample = int(source["end_sample"])
        source_start_ms = mature.milliseconds_for_samples(source_start_sample)
        source_end_ms = mature.milliseconds_for_samples(source_end_sample)
        destination_start_ms = mature.milliseconds_for_samples(destination_sample)
        event_duration_ms = mature.milliseconds_for_samples(
            source_end_sample - source_start_sample
        )
        for cue in source_cues:
            cue_start = int(cue["start_ms"])
            if not source_start_ms <= cue_start < source_end_ms:
                continue
            local_start = cue_start - source_start_ms
            local_end = min(
                event_duration_ms, int(cue["end_ms"]) - source_start_ms
            )
            if local_end <= local_start:
                raise ValueError(f"{event} subtitle collapses at its boundary")
            output.append(
                {
                    "start_ms": destination_start_ms + local_start,
                    "end_ms": destination_start_ms + local_end,
                    "text": str(cue["text"]),
                    "event": event,
                }
            )
        destination_sample += source_end_sample - source_start_sample
    return output


def validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status")
        != "ac4902_selector_entry_routes_approved_for_render"
        or plan.get("family") != "ac4902"
        or plan.get("composition_claim") != COMPOSITION_CLAIM
        or plan.get("uploaded_media_policy") != UPLOAD_POLICY
        or plan.get("native_dimensions") != {"width": WIDTH, "height": HEIGHT}
        or plan.get("native_frame_rate") != "30/1"
        or int(plan.get("dirinfo_kind", -1)) != 113
    ):
        raise ValueError("unsupported ac4902 selector-entry route plan")

    bound, snapshots = _validate_bound_sources(plan, plan_path=plan_path)
    proposal = mature.read_json(bound["deduplication_proposal"])
    if proposal.get("series") != "ac4902":
        raise ValueError("deduplication proposal family differs")
    aliases = mature.duplicate_alias_map(proposal)
    family_timeline, source_cues = validate_corrected_family(
        bound=bound, ffprobe=ffprobe
    )
    entry_events, entry_snapshots = validate_entry_evidence(
        entries=plan.get("entry_events", []),
        bound=bound,
        plan_dir=plan_path.parent,
        ffprobe=ffprobe,
    )
    snapshots.extend(entry_snapshots)
    for event, row in entry_events.items():
        alias = str(row["alias"])
        if alias in aliases and aliases[alias] != event:
            raise ValueError(f"entry alias conflicts with proposal: {alias}")
        aliases[alias] = event

    source_routes = mature._dirinfo_sequences(bound["dirinfo"], kind=113)
    routes, duplicate_rows = validate_route_declarations(
        routes_raw=plan.get("routes"),
        duplicate_rows_raw=plan.get("expected_duplicate_rows"),
        source_routes=source_routes,
        aliases=aliases,
    )
    for route in routes:
        timeline, total_frames, total_samples = mixed_route_timeline(
            route["render_event_sequence"],
            family_timeline=family_timeline,
            entry_events=entry_events,
        )
        route["timeline"] = timeline
        route["total_frames"] = total_frames
        route["total_samples"] = total_samples

    return {
        "title": str(plan.get("title", "")).strip(),
        "bound": bound,
        "snapshots": snapshots,
        "family_timeline": family_timeline,
        "source_cues": source_cues,
        "entry_events": entry_events,
        "aliases": aliases,
        "routes": routes,
        "duplicate_rows": duplicate_rows,
        "layout": mature.read_json(bound["subtitle_layout"]),
        "plan_sha256": mature.file_sha256(plan_path),
        "family_manifest_sha256": mature.file_sha256(bound["family_manifest"]),
    }


def _build_entry_visual(
    *,
    entry: Mapping[str, Any],
    output: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    total_frames = int(entry["frames"])
    main_frames = int(entry["main_frames"])
    loop_frames = int(entry["loop_frames"])
    mature.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(entry["main_clip"]),
            "-i",
            str(entry["loop_clip"]),
            "-filter_complex",
            (
                f"[0:v:0]trim=end_frame={main_frames},"
                f"setpts=N/({FPS}*TB),format=yuv420p[main];"
                f"[1:v:0]trim=end_frame={loop_frames},"
                f"setpts=N/({FPS}*TB),format=yuv420p[loop];"
                "[main][loop]concat=n=2:v=1:a=0[outv]"
            ),
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(total_frames),
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return mature.validate_video_grid(
        output,
        expected_frames=total_frames,
        ffprobe=ffprobe,
        label=f"{entry['event']} entry visual",
    )


def _build_entry_pcm(
    *,
    entry: Mapping[str, Any],
    output: Path,
    ffmpeg: str,
) -> dict[str, Any]:
    total_samples = int(entry["samples"])
    mature.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(entry["ogg"]),
            "-af",
            (
                "aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:"
                "channel_layouts=stereo,"
                f"apad,atrim=end_sample={total_samples},asetpts=N/SR/TB"
            ),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            str(output),
        ]
    )
    expected_bytes = total_samples * 8
    if output.stat().st_size != expected_bytes:
        raise RuntimeError(
            f"{entry['event']} PCM byte count differs: "
            f"{output.stat().st_size} != {expected_bytes}"
        )
    return {
        "sample_count": total_samples,
        "byte_count": expected_bytes,
        "sha256": mature.file_sha256(output),
        "action_start_sample": 0,
        "ogg_source_samples": int(entry["source_samples"]),
        "trimmed_source_samples": max(
            0, int(entry["source_samples"]) - total_samples
        ),
        "padded_silence_samples": max(
            0, total_samples - int(entry["source_samples"])
        ),
    }


def _concat_visuals(
    *,
    sources: Sequence[Path],
    frame_counts: Sequence[int],
    output: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    if len(sources) != len(frame_counts) or not sources:
        raise ValueError("route visual sources are incomplete")
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    filters: list[str] = []
    labels: list[str] = []
    for index, (path, frames) in enumerate(zip(sources, frame_counts)):
        command.extend(["-i", str(path)])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={frames},"
            f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]"
    )
    total_frames = sum(frame_counts)
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(total_frames),
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    mature.run(command)
    return mature.validate_video_grid(
        output,
        expected_frames=total_frames,
        ffprobe=ffprobe,
        label="ac4902 selector-entry route clean visual",
    )


def _build_shared_event_assets(
    *,
    resolved: Mapping[str, Any],
    work: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, dict[str, Any]]:
    events = {
        event
        for route in resolved["routes"]
        for event in route["render_event_sequence"]
    }
    assets: dict[str, dict[str, Any]] = {}
    for event in sorted(events):
        directory = work / event
        directory.mkdir(parents=True)
        visual = directory / "clean.mp4"
        pcm = directory / "audio.f32le"
        if event in resolved["entry_events"]:
            entry = resolved["entry_events"][event]
            visual_audit = _build_entry_visual(
                entry=entry,
                output=visual,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            pcm_audit = _build_entry_pcm(
                entry=entry, output=pcm, ffmpeg=ffmpeg
            )
            frames = int(entry["frames"])
            samples = int(entry["samples"])
            source_kind = "hash_bound_entry_event"
        else:
            source = resolved["family_timeline"][event]
            frames = int(source["end_frame"]) - int(source["start_frame"])
            samples = int(source["end_sample"]) - int(source["start_sample"])
            timeline = [
                {
                    "source_start_frame": int(source["start_frame"]),
                    "source_end_frame": int(source["end_frame"]),
                    "source_start_sample": int(source["start_sample"]),
                    "source_end_sample": int(source["end_sample"]),
                }
            ]
            visual_audit = mature._build_clean_visual(
                source=resolved["bound"]["clean_visual_master"],
                timeline=timeline,
                output=visual,
                total_frames=frames,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            pcm_audit = mature._build_pcm(
                source=resolved["bound"]["no_bgm_audio_master"],
                timeline=timeline,
                output=pcm,
                total_samples=samples,
                ffmpeg=ffmpeg,
            )
            source_kind = "corrected_v26_family_master"
        if samples != frames * SAMPLES_PER_FRAME:
            raise RuntimeError(f"{event} shared event asset grid differs")
        assets[event] = {
            "event": event,
            "source_kind": source_kind,
            "visual": visual,
            "pcm": pcm,
            "frames": frames,
            "samples": samples,
            "visual_audit": visual_audit,
            "pcm_audit": pcm_audit,
        }
    return assets


def _assert_source_snapshots_unchanged(
    snapshots: Sequence[Mapping[str, str]],
) -> None:
    for row in snapshots:
        path = Path(row["path"])
        if mature.file_sha256(path) != row["sha256"]:
            raise RuntimeError(f"source changed during build: {path}")


def build_batch(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[Path, dict[str, Any]]:
    plan_path = plan_path.resolve()
    plan = mature.read_json(plan_path)
    resolved = validate_plan(plan, plan_path=plan_path, ffprobe=ffprobe)
    destination = output_root.resolve() / BATCH_ID
    if destination.exists():
        raise FileExistsError(f"versioned batch output already exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root.resolve() / f".{BATCH_ID}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    completed: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    try:
        fonts_dir = staging / ".work" / "fonts"
        event_work = staging / ".work" / "events"
        fonts_dir.mkdir(parents=True)
        event_work.mkdir(parents=True)
        shutil.copy2(
            resolved["bound"]["font"],
            fonts_dir / resolved["bound"]["font"].name,
        )
        assets = _build_shared_event_assets(
            resolved=resolved,
            work=event_work,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )

        for route in resolved["routes"]:
            route_dir = staging / "routes" / route["route_id"]
            try:
                route_dir.mkdir(parents=True)
                work = route_dir / ".work"
                work.mkdir()
                route_assets = [
                    assets[event] for event in route["render_event_sequence"]
                ]
                clean = work / "clean.mp4"
                pcm = work / "audio.f32le"
                clean_audit = _concat_visuals(
                    sources=[row["visual"] for row in route_assets],
                    frame_counts=[int(row["frames"]) for row in route_assets],
                    output=clean,
                    ffmpeg=ffmpeg,
                    ffprobe=ffprobe,
                )
                mature._copy_pcm([row["pcm"] for row in route_assets], pcm)
                if pcm.stat().st_size != int(route["total_samples"]) * 8:
                    raise RuntimeError("route PCM byte count differs")
                pcm_audit = {
                    "sample_count": int(route["total_samples"]),
                    "byte_count": pcm.stat().st_size,
                    "sha256": mature.file_sha256(pcm),
                    "event_pcm_sha256": {
                        row["event"]: mature.file_sha256(row["pcm"])
                        for row in route_assets
                    },
                }
                cues = {
                    edition: mixed_route_subtitle_cues(
                        route["render_event_sequence"],
                        family_timeline=resolved["family_timeline"],
                        source_cues=resolved["source_cues"][edition],
                        entry_events=resolved["entry_events"],
                    )
                    for edition in ("ja", "zh")
                }
                product, _ = mature._build_one_product(
                    product_id=f"ac4902__{route['route_id']}",
                    title=route["title"],
                    timeline=route["timeline"],
                    clean_visual=clean,
                    pcm=pcm,
                    cues=cues,
                    output_dir=route_dir,
                    staging=staging,
                    layout=resolved["layout"],
                    fonts_dir=fonts_dir,
                    ffmpeg=ffmpeg,
                    ffprobe=ffprobe,
                )
                product.update(
                    {
                        "schema": ROUTE_MANIFEST_SCHEMA,
                        "status": STATUS,
                        "product_scope": "independent_dirinfo_selector_entry_route",
                        "composition_claim": COMPOSITION_CLAIM,
                        "single_native_session_claimed": True,
                        "render_event_sequence": route["render_event_sequence"],
                        "dirinfo_source_row": route["source_row"],
                        "source_clean_visual_audit": clean_audit,
                        "source_pcm_audit": pcm_audit,
                        "entry_event_evidence": [
                            {
                                "event": event,
                                "exact_alias": resolved["entry_events"][event][
                                    "alias"
                                ],
                                "request_id": resolved["entry_events"][event][
                                    "request_id"
                                ],
                                "sound_code": resolved["entry_events"][event][
                                    "sound_code"
                                ],
                                "action_start_sample": 0,
                                "frames": resolved["entry_events"][event]["frames"],
                                "samples": resolved["entry_events"][event]["samples"],
                            }
                            for event in route["render_event_sequence"]
                            if event in resolved["entry_events"]
                        ],
                        "human_playback_approved": False,
                        "publication_approved": False,
                    }
                )
                mature.write_json(route_dir / "ROUTE_MANIFEST.json", product)
                shutil.rmtree(work)
                completed.append(product)
            except BaseException as exc:
                shutil.rmtree(route_dir, ignore_errors=True)
                failures.append(
                    {
                        "route_id": route["route_id"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

        _assert_source_snapshots_unchanged(resolved["snapshots"])
        packet_consistency: dict[str, Any] = {}
        for product in completed:
            audits = product["audio_packet_pcm_audits"]
            packet_signatures = {
                audits[edition]["packet_data_signature_sha256"]
                for edition in EDITIONS
            }
            decoded_signatures = {
                audits[edition]["decoded_prefix_sha256"] for edition in EDITIONS
            }
            packet_consistency[product["product_id"]] = {
                "none_ja_zh_packet_identical": len(packet_signatures) == 1,
                "none_ja_zh_decoded_prefix_identical": len(decoded_signatures) == 1,
                "packet_data_signature_sha256": next(iter(packet_signatures)),
                "decoded_prefix_sha256": next(iter(decoded_signatures)),
            }
        if any(
            not row["none_ja_zh_packet_identical"]
            or not row["none_ja_zh_decoded_prefix_identical"]
            for row in packet_consistency.values()
        ):
            raise RuntimeError("batch packet/PCM consistency audit differs")

        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS if not failures else PARTIAL_STATUS,
            "automated_spec_qa_passed": not failures,
            "human_playback_approved": False,
            "publication_approved": False,
            "checks": {
                "dirinfo_hash_bound": True,
                "seventeen_independent_routes_exact": True,
                "nine_exact_duplicate_rows_not_rendered_twice": True,
                "corrected_v26_family_artifacts_hash_bound": True,
                "entry_visuals_and_oggs_hash_bound": True,
                "entry_aliases_exact_in_audience_and_audio_evidence": True,
                "entry_child_audio_rows_zero": True,
                "entry_subtitle_rows_zero": True,
                "action_se_starts_at_sample_zero": True,
                "native_416x232_30fps_no_upscale": True,
                "total_samples_equal_total_frames_times_1600": True,
                "kuroba_subtitle_corrections_preserved": True,
                "none_ja_zh_packet_and_decoded_pcm_identical": True,
                "cross_route_showcase_absent": True,
                "uploaded_and_source_files_untouched": True,
            },
            "route_count_requested": len(resolved["routes"]),
            "route_count_completed": len(completed),
            "route_failures": failures,
            "final_mp4_count": len(completed) * len(EDITIONS),
            "packet_pcm_consistency": packet_consistency,
        }
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": qa["status"],
            "batch_id": BATCH_ID,
            "family": "ac4902",
            "title": resolved["title"],
            "audio_profile": "no_bgm",
            "bgm_policy": "intentionally_excluded",
            "voice_se_policy": (
                "corrected_v26_family_master_plus_hash_bound_direct_parent_"
                "entry_action_se"
            ),
            "composition_claim": COMPOSITION_CLAIM,
            "showcase": None,
            "editions": list(EDITIONS),
            "routes": completed,
            "exact_duplicate_rows": resolved["duplicate_rows"],
            "route_failures": failures,
            "source_snapshots": resolved["snapshots"],
            "source_plan": {
                "path": str(plan_path),
                "sha256": resolved["plan_sha256"],
            },
            "family_manifest_sha256": resolved["family_manifest_sha256"],
            "human_playback_approved": False,
            "publication_approved": False,
        }
        mature.write_json(staging / "BATCH_MANIFEST.json", manifest)
        mature.write_json(staging / "BATCH_SUMMARY.json", qa)
        mature.write_json(staging / "PLAN_SNAPSHOT.json", plan)
        readme = (
            f"# {resolved['title']} — ac4902 selector-entry routes\n\n"
            f"独立路线：{len(completed)} / {len(resolved['routes'])}；"
            "每条均有 none / JA / ZH。九条精确重复 DirInfo 行未重复渲染。\n\n"
            "本批没有跨互斥路线合集，也不声明多个路线属于同一次游戏播放。"
            "BGM 有意排除；保留纠错 v26 family master 的对白与场景音，并为"
            "入口事件加入哈希绑定的父级动作音。所有输出仍需人工完整播放后才能"
            "投稿。\n"
        )
        (staging / "README_REVIEW.md").write_text(readme, encoding="utf-8")

        # Work products are not part of the durable batch and must disappear
        # before the checksum inventory is enumerated.
        shutil.rmtree(staging / ".work")
        hashes = [
            {
                "path": mature.relative_output_path(path, staging=staging),
                "sha256": mature.file_sha256(path),
                "byte_count": path.stat().st_size,
            }
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "SHA256SUMS.json"
        ]
        mature.write_json(
            staging / "SHA256SUMS.json",
            {
                "schema": "magireco-versioned-output-sha256-v1",
                "batch_id": BATCH_ID,
                "files": hashes,
            },
        )
        staging.replace(destination)
        return destination, qa
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        destination, qa = build_batch(
            plan_path=args.plan,
            output_root=args.output_root,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
        )
        print(
            json.dumps(
                {"destination": str(destination), "qa": qa},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not qa["route_failures"] else 2
    except BaseException as exc:
        print(
            json.dumps(
                {"error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
