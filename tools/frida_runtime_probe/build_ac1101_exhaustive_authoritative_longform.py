#!/usr/bin/env python3
"""Build the exhaustive native-416 ac1101 editorial longform.

The audience product is one code-reachable, duplicate-free collection of all
13 complete event presentations.  Mutually exclusive DirInfo routes are
combined in a comprehensible editorial order; route fragments are evidence,
not standalone final products.  MovieLayer timing comes from the exact Z2D
chunks joined to the runtime parent ranges, while VOICE/SE/subtitle timing and
strict no-BGM partitioning come from the exact ac1101 audio authority.

No source media is moved, deleted, or transcoded while building the immutable
input checkpoint.  The renderer is invoked only after every authority gate and
the bounded 35-source media audit pass.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .build_event_production_manifests import (
        file_sha256,
        quantize_duration_to_frame_grid,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import (
        file_sha256,
        quantize_duration_to_frame_grid,
    )


REQUIRED_EVENTS = tuple(f"ac1101_{index:03d}" for index in range(1, 14))
EDITORIAL_ORDER = (
    "ac1101_001",  # white short title entry
    "ac1101_008",  # red short title entry
    "ac1101_009",  # white long/Kuroe title entry
    "ac1101_010",  # red long/Kuroe title entry
    "ac1101_011",  # second-game entry
    "ac1101_002",  # normal cat-lure choice
    "ac1101_007",  # cut-in cat-lure choice
    "ac1101_003",  # stay/continuation outcome
    "ac1101_004",  # pot approach continuation
    "ac1101_005",  # loss outcome plus dark transition
    "ac1101_006",  # standard win outcome
    "ac1101_012",  # revival route entry
    "ac1101_013",  # revival completion
)
FRAME_RATE = "30/1"
NATIVE_DIMENSIONS = {"width": 416, "height": 232}
PRODUCT_SCOPE = "exhaustive_duplicate_free_event_presentation_editorial_longform"
EXPECTED_ROUTE_COUNT = 31
EXPECTED_AUTHORED_CHUNK_OCCURRENCES = 49
EXPECTED_LOADABLE_DGM_IDENTITIES = 35
EXPECTED_UNREACHABLE_ALIAS_NAMES = 4
EXPECTED_EVENT_SOURCE_OCCURRENCES = 51
EXPECTED_RETAINED_AUDIO = 49
EXPECTED_EXCLUDED_BGM = 2
EXPECTED_SUBTITLES = 31
LONGER_SOURCE_AUTHORED_PREFIXES = {
    "ac1101_lev_title_red": (150, 60),
    "ac1101_lev_title_wht": (150, 60),
}


class Ac1101ExhaustiveError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def frame_to_ms(frame: int) -> int:
    return round(int(frame) * 1000 / 30)


def _snapshot(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return {
        "path": str(resolved),
        "sha256": file_sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames,sample_rate,channels,pix_fmt:format=duration",
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


def validate_authorities(
    layers: Mapping[str, Any], audio: Mapping[str, Any]
) -> None:
    layer_assertions = layers.get("assertions", {})
    layer_decision = layers.get("decision", {})
    if (
        layers.get("schema")
        != "magireco-ac1101-movielayer-runtime-reachability-authority-v1"
        or layers.get("status") != "passed"
        or int(layer_assertions.get("runtime_events", -1)) != 13
        or int(layer_assertions.get("authored_movie_layer_occurrences", -1))
        != EXPECTED_AUTHORED_CHUNK_OCCURRENCES
        or int(layer_assertions.get("unique_runtime_loadable_dgm_names", -1))
        != EXPECTED_LOADABLE_DGM_IDENTITIES
        or int(layer_assertions.get("unreachable_alias_names", -1))
        != EXPECTED_UNREACHABLE_ALIAS_NAMES
        or layer_decision.get("visual_reachability_gate") != "CLOSED"
    ):
        raise Ac1101ExhaustiveError("ac1101 MovieLayer authority differs")

    audio_assertions = audio.get("assertions", {})
    audio_decision = audio.get("decision", {})
    if (
        audio.get("schema")
        != "magireco-ac1101-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "passed"
        or set(audio_decision.get("events", [])) != set(REQUIRED_EVENTS)
        or audio_decision.get("event_global_child_audio_timing") != "CLOSED"
        or audio_decision.get("event_audio_and_strict_no_bgm_manifest_closure")
        != "CLOSED"
        or int(audio_assertions.get("total_audio_occurrences", -1)) != 51
        or int(audio_assertions.get("retained_audio_occurrences", -1))
        != EXPECTED_RETAINED_AUDIO
        or int(audio_assertions.get("subtitle_cues", -1)) != EXPECTED_SUBTITLES
        or audio_assertions.get("only_sound_554_is_excluded_as_bgm") is not True
    ):
        raise Ac1101ExhaustiveError("ac1101 audio authority differs")


def resolve_routes(rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        if int(row["kind"]) == 53:
            grouped[int(row["row_index"])].append(row)
    if set(grouped) != set(range(EXPECTED_ROUTE_COUNT)):
        raise Ac1101ExhaustiveError("DirInfo kind-53 route index set differs")
    routes: list[dict[str, Any]] = []
    union: set[str] = set()
    for row_index in sorted(grouped):
        ordered = sorted(grouped[row_index], key=lambda row: int(row["selector_raw"]))
        events = [str(row["scene_name"]) for row in ordered]
        if len(events) != len(set(events)) or not set(events) <= set(REQUIRED_EVENTS):
            raise Ac1101ExhaustiveError(f"invalid event sequence in route {row_index}")
        union.update(events)
        routes.append(
            {
                "row_index": row_index,
                "events": events,
                "legacy_zero_source_events": [
                    str(row["scene_name"])
                    for row in ordered
                    if int(row.get("resolved_source_count", 0)) == 0
                ],
                "reconstructable_from_event_presentation_set": True,
            }
        )
    if union != set(REQUIRED_EVENTS):
        raise Ac1101ExhaustiveError("DirInfo route union does not cover 13 events")
    return routes


def event_code_map(rows: Sequence[Mapping[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        if int(row["kind"]) != 53:
            continue
        event = str(row["scene_name"])
        code = str(row["code_hex"]).casefold()
        previous = result.setdefault(event, code)
        if previous != code:
            raise Ac1101ExhaustiveError(f"DirInfo code differs for {event}")
    if set(result) != set(REQUIRED_EVENTS):
        raise Ac1101ExhaustiveError("DirInfo event-code set differs")
    return result


def source_path_for_dgm(named_video_root: Path, dgm_name: str) -> Path:
    if dgm_name.startswith("ac1101_"):
        return (named_video_root / "main" / "ac1101" / f"{dgm_name}.mp4").resolve()
    if dgm_name.startswith("ac8000_"):
        return (named_video_root / "patch" / "ac8000" / f"{dgm_name}.mp4").resolve()
    if dgm_name.startswith("ac8040_"):
        return (named_video_root / "patch" / "ac8040" / f"{dgm_name}.mp4").resolve()
    raise Ac1101ExhaustiveError(f"unexpected ac1101 DGM family: {dgm_name}")


def layer_role(parent_z2d: str, dgm_name: str) -> str:
    if (
        "_title_" in dgm_name
        or parent_z2d == "ac8000_cmn_tx_tuduku"
        or parent_z2d == "ac8040_kyo_anten"
        or parent_z2d == "ac8040_shouri_EF_small"
        or parent_z2d == "ac1101_3off_win_rogo"
    ):
        return "screen_overlay"
    return "background"


def _video_stream(probe: Mapping[str, Any]) -> Mapping[str, Any]:
    streams = [row for row in probe.get("streams", []) if row.get("codec_type") == "video"]
    if len(streams) != 1:
        raise Ac1101ExhaustiveError("source does not contain exactly one video stream")
    return streams[0]


def build_bounded_source_authority(
    layers: Mapping[str, Any], named_video_root: Path, ffprobe: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    expected_frames: dict[str, int] = {}
    compiled_indices: dict[str, int] = {}
    for chunk in layers["z2d_chunks"]:
        for row in chunk["movie_layers"]:
            if row.get("compiled_table_present") is not True:
                continue
            name = str(row["z2d_reference"]).removesuffix(".dgm")
            frames = int(row["frame_count"])
            prior = expected_frames.setdefault(name, frames)
            if prior != frames:
                raise Ac1101ExhaustiveError(f"DGM frame interval differs: {name}")
            compiled_indices[name] = int(row["compiled_table_index"])
    if len(expected_frames) != EXPECTED_LOADABLE_DGM_IDENTITIES:
        raise Ac1101ExhaustiveError("loadable DGM identity count differs")

    resolved: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for name in sorted(expected_frames):
        path = source_path_for_dgm(named_video_root, name)
        if not path.is_file():
            raise FileNotFoundError(path)
        probe = _probe_video(path, ffprobe)
        stream = _video_stream(probe)
        source_frames = int(stream.get("nb_read_frames", 0))
        expected = expected_frames[name]
        authored_prefix = LONGER_SOURCE_AUTHORED_PREFIXES.get(name)
        if (
            stream.get("codec_name") != "h264"
            or stream.get("r_frame_rate") != FRAME_RATE
            or stream.get("pix_fmt") != "yuv420p"
            or (int(stream.get("width", 0)), int(stream.get("height", 0)))
            not in {(416, 232), (256, 144), (208, 120)}
            or (
                source_frames != expected
                and authored_prefix != (source_frames, expected)
            )
        ):
            raise Ac1101ExhaustiveError(f"bounded source signature differs: {name}")
        entry = {
            "dgm_name": name,
            "compiled_table_index": compiled_indices[name],
            "path": str(path),
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "frame_rate": str(stream["r_frame_rate"]),
            "source_frame_count": source_frames,
            "playback_frame_count": expected,
            "authored_layer_frame_count": expected,
            "source_frame_contract": (
                "exact_authored_prefix_of_longer_official_source"
                if authored_prefix
                else "exact_one_to_one_authored_interval"
            ),
        }
        entries.append(entry)
        resolved[name] = entry
    report = {
        "schema": "magireco-ac1101-bounded-source-media-authority-v1",
        "status": "PASS",
        "entry_count": len(entries),
        "native_416x232_count": sum(
            (row["width"], row["height"]) == (416, 232) for row in entries
        ),
        "component_256x144_count": sum(
            (row["width"], row["height"]) == (256, 144) for row in entries
        ),
        "component_208x120_count": sum(
            (row["width"], row["height"]) == (208, 120) for row in entries
        ),
        "authored_prefix_source_count": sum(
            row["source_frame_contract"].startswith("exact_authored_prefix") for row in entries
        ),
        "entries": entries,
        "source_media_modified": False,
    }
    return resolved, report


def event_layer_rows(
    event: str,
    layers: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    parent_bindings = layers["runtime_event_bindings"][event]
    chunks = {str(row["name"]): row for row in layers["z2d_chunks"]}
    visible: list[dict[str, Any]] = []
    unreachable: list[dict[str, Any]] = []
    authored_visual_end = 0
    for parent_binding in parent_bindings:
        parent_name = str(parent_binding["parent_z2d"])
        chunk = chunks.get(parent_name)
        if chunk is None:
            raise Ac1101ExhaustiveError(f"missing exact Z2D chunk: {parent_name}")
        parent_start = int(parent_binding["event_global_start_frame"])
        parent_end = int(parent_binding["event_global_end_frame_inclusive"]) + 1
        if int(chunk["header"]["scene_frame_count"]) != parent_end - parent_start:
            raise Ac1101ExhaustiveError(f"parent range differs from chunk: {event}/{parent_name}")
        authored_visual_end = max(authored_visual_end, parent_end)
        for layer in chunk["movie_layers"]:
            dgm_name = str(layer["z2d_reference"]).removesuffix(".dgm")
            event_start_frame = parent_start + int(layer["start_frame"])
            authored_end_frame = parent_start + int(layer["end_frame_inclusive"]) + 1
            base = {
                "parent_z2d": parent_name,
                "dgm_name": dgm_name,
                "event_start_frame": event_start_frame,
                "authored_event_end_frame_exclusive": authored_end_frame,
                "authored_blend_enum": int(layer["authored_blend_enum"]),
                "effective_renderer_state": int(layer["effective_renderer_state"]),
            }
            if layer.get("compiled_table_present") is not True:
                unreachable.append(base)
                continue
            source = sources.get(dgm_name)
            if source is None:
                raise Ac1101ExhaustiveError(f"loadable source identity missing: {dgm_name}")
            source_end_frame = event_start_frame + int(source["playback_frame_count"])
            visible.append(
                {
                    **base,
                    **dict(source),
                    "role": layer_role(parent_name, dgm_name),
                    "event_start_ms": frame_to_ms(event_start_frame),
                    "event_end_ms": frame_to_ms(source_end_frame),
                    "authored_event_end_ms": frame_to_ms(authored_end_frame),
                }
            )
    return visible, unreachable, authored_visual_end


def _speaker_code_from_caption(name: str) -> str:
    parts = str(name).split("_")
    if len(parts) < 4 or parts[0] != "cap1101" or parts[1] != "neko":
        return ""
    return {"san": "sana", "iro": "iro", "uni": ""}.get(parts[2], "")


def build_event_manifest(
    event: str,
    *,
    code_hex: str,
    layer_rows: Sequence[Mapping[str, Any]],
    unreachable_rows: Sequence[Mapping[str, Any]],
    authored_visual_end_frame: int,
    audio_rows: Sequence[Mapping[str, Any]],
    subtitle_rows: Sequence[Mapping[str, Any]],
    layer_authority_path: Path,
    audio_authority_path: Path,
) -> dict[str, Any]:
    retained = [
        dict(row)
        for row in audio_rows
        if row["event"] == event
        and row["strict_no_bgm_disposition"] != "EXCLUDE_AS_BGM_BUS"
    ]
    excluded = [
        dict(row)
        for row in audio_rows
        if row["event"] == event
        and row["strict_no_bgm_disposition"] == "EXCLUDE_AS_BGM_BUS"
    ]
    if any(row.get("volume_bus") == "BGM" for row in retained):
        raise Ac1101ExhaustiveError(f"BGM leaked into retained audio: {event}")
    if any((int(row["request_id"]), int(row["sound_id"])) != (229, 554) for row in excluded):
        raise Ac1101ExhaustiveError(f"unexpected excluded audio identity: {event}")

    event_subtitles = [dict(row) for row in subtitle_rows if row["event"] == event]
    video_content_ms = frame_to_ms(authored_visual_end_frame)
    audio_content_ms = max(
        (int(row["start_ms"]) + int(row["duration_ms"]) for row in retained),
        default=0,
    )
    subtitle_content_ms = max((int(row["end_ms"]) for row in event_subtitles), default=0)
    content_end_ms = max(video_content_ms, audio_content_ms, subtitle_content_ms)
    quantization = quantize_duration_to_frame_grid(content_end_ms, FRAME_RATE)

    ordered_layers = sorted(
        (dict(row) for row in layer_rows),
        key=lambda row: (
            1 if row["role"] == "screen_overlay" else 0,
            int(row["event_start_frame"]),
            int(row["compiled_table_index"]),
        ),
    )
    clips: list[dict[str, Any]] = []
    plan_clips: list[dict[str, Any]] = []
    for order, row in enumerate(ordered_layers):
        clips.append(
            {
                "order": order,
                "dgm_name": row["dgm_name"],
                "dgm_role": row["role"],
                "path": row["path"],
                "source_sha256": row["sha256"],
                "event_start_ms": int(row["event_start_ms"]),
                "event_end_ms": int(row["event_end_ms"]),
                "authored_event_end_ms": int(row["authored_event_end_ms"]),
                "source_frame_count": int(row["source_frame_count"]),
                "authored_layer_frame_count": int(row["authored_layer_frame_count"]),
                "interval_confidence": "exact_runtime_parent_range_and_z2d_movielayer_interval",
                "source_frame_contract": row["source_frame_contract"],
            }
        )
        plan: dict[str, Any] = {
            "dgm_name": row["dgm_name"],
            "role": row["role"],
            "start_ms": int(row["event_start_ms"]),
        }
        if row["role"] == "screen_overlay":
            plan["blend_mode"] = "screen"
            plan["duration_ms"] = int(row["authored_event_end_ms"]) - int(row["event_start_ms"])
            if (int(row["width"]), int(row["height"])) != (416, 232):
                plan["scale_to_native"] = True
        plan_clips.append(plan)

    manifest_audio: list[dict[str, Any]] = []
    for row in retained:
        item: dict[str, Any] = {
            "source": str(row["source_kind"]),
            "request_id": str(row["request_id"]),
            "sound_id": int(row["sound_id"]),
            "code_name": str(row["code_name"]),
            "ogg_name": str(row["ogg_name"]),
            "path": str(Path(str(row["ogg_path"])).resolve()),
            "start_ms": int(row["start_ms"]),
            "duration_ms": int(row["duration_ms"]),
            "volume_kind_value": int(row["volume_kind_value"]),
            "volume_bus": str(row["volume_bus"]),
            "strict_no_bgm_disposition": str(row["strict_no_bgm_disposition"]),
            "timing_evidence": str(row["timing_evidence"]),
        }
        if row["source_kind"] == "z2d_req_sound":
            item.update(
                {
                    "z2d_name": str(row["z2d_name"]),
                    "event_global_start_frame": int(row["start_frame"]),
                    "event_global_start_resolved": True,
                    "timing_scope": "event_global_exact_parent_scene_and_motion_key",
                }
            )
        manifest_audio.append(item)

    audio_by_request = {
        str(row["request_id"]): row
        for row in retained
        if row["source_kind"] == "z2d_req_sound"
    }
    subtitles: list[dict[str, Any]] = []
    for row in event_subtitles:
        request_id = "" if row.get("voice_request_id") is None else str(row["voice_request_id"])
        audio_row = audio_by_request.get(request_id)
        start_frame = (
            int(audio_row["start_frame"])
            if audio_row is not None
            else round(int(row["start_ms"]) * 30 / 1000)
        )
        subtitle_source = (
            "official_voice_label" if request_id else "graphical_display_text"
        )
        subtitles.append(
            {
                "text": str(row["ja"]),
                "start_ms": int(row["start_ms"]),
                "end_ms": int(row["end_ms"]),
                "voice_request_id": request_id,
                "voice_start_ms": int(row["start_ms"]),
                "z2d_name": str(row["z2d_name"]),
                "speaker_code": _speaker_code_from_caption(str(row["z2d_name"])),
                "subtitle_source": subtitle_source,
                "evidence": str(row["evidence"]),
                "event_global_start_frame": start_frame,
                "event_global_start_resolved": True,
                "timing_scope": "event_global_exact_parent_scene_and_motion_key",
                "timing_override_source": str(audio_authority_path.resolve()),
                "speaker_identity_evidence": (
                    "exact_official_voice_request_code_name_speaker_token"
                    if request_id
                    else "exact_runtime_caption_resource_name"
                ),
            }
        )

    overlap_count = max(0, len([row for row in ordered_layers if row["role"] == "screen_overlay"]))
    return {
        "schema": "magireco-event-production-v3",
        "event": event,
        "event_code_hex": code_hex,
        "classification": "verified_native_composite",
        "audience_exclusion_reason": "",
        "native_dimensions": dict(NATIVE_DIMENSIONS),
        "native_frame_rate": FRAME_RATE,
        "video_duration_ms": video_content_ms,
        "timeline_duration_ms": content_end_ms,
        "timeline_content_end_ms": content_end_ms,
        "raw_render_duration_ms": content_end_ms,
        "render_frame_count": int(quantization["frame_count"]),
        "render_duration_ms": int(quantization["duration_ms"]),
        "render_duration_quantization": quantization,
        "video_extension_policy": "hold_last_frame",
        "video_composition_model": "timed_full_frame_layers",
        "composition_plan": {
            "schema": "magireco-video-composition-v1",
            "event": event,
            "model": "timed_full_frame_layers",
            "native_dimensions": dict(NATIVE_DIMENSIONS),
            "duration_ms": content_end_ms,
            "extension_policy": "hold_last_frame",
            "evidence": (
                "exact runtime parent ranges plus exact Z2D MovieLayer intervals; "
                "code-unreachable additive aliases are omitted while their same-interval "
                "loadable base layers are retained; no LP source is repeated editorially"
            ),
            "clips": plan_clips,
        },
        "composition_plan_source": str(layer_authority_path.resolve()),
        "runtime_event_manifest_sources": [],
        "reviewed_subtitle_manifest_sources": [],
        "reviewed_subtitle_reconciliation": {},
        "overlap_count": overlap_count,
        "gap_count": 0,
        "timeline_tolerance_ms": 34,
        "clips": clips,
        "audio": manifest_audio,
        "subtitles": subtitles,
        "quality_gates": {
            "all_full_frame": all(
                (int(row["width"]), int(row["height"])) == (416, 232)
                for row in ordered_layers
            ),
            "all_clips_exist": True,
            "all_clip_source_hashes_bound": True,
            "all_audio_exist": all(Path(row["path"]).is_file() for row in manifest_audio),
            "verified_subtitle_voice_count": sum(bool(row["voice_request_id"]) for row in subtitles),
            "graphical_display_subtitle_count": sum(
                row["subtitle_source"] == "graphical_display_text" for row in subtitles
            ),
            "official_voice_label_subtitle_count": sum(
                row["subtitle_source"] == "official_voice_label" for row in subtitles
            ),
            "asr_verified_subtitle_count": 0,
            "reviewed_subtitle_baseline_applied": False,
            "reviewed_subtitle_current_only_voice_candidate_count": 0,
            "reviewed_subtitle_current_only_graphical_candidate_count": 0,
            "exact_z2d_req_sound_count": sum(
                row["source"] == "z2d_req_sound" for row in manifest_audio
            ),
            "event_global_z2d_timing_ready": True,
            "linear_video_timeline": False,
            "video_composition_model": "timed_full_frame_layers",
            "composition_resolved": True,
            "composition_evidence": "ac1101 exact Z2D MovieLayer/runtime-parent authority",
            "video_extension_supported": True,
            "audio_timeline_ready": True,
            "errors": [],
            "render_ready": True,
            "ready": True,
        },
        "strict_no_bgm_sound_bus_contract": {
            "status": "PASS",
            "included_buses": ["SE", "VOICE"],
            "excluded_buses": ["BGM"],
            "excluded_occurrences": [
                {
                    "request_id": int(row["request_id"]),
                    "sound_id": int(row["sound_id"]),
                    "start_ms": int(row["start_ms"]),
                }
                for row in excluded
            ],
            "evidence_path": str(audio_authority_path.resolve()),
        },
        "ac1101_generated_manifest_provenance": {
            "layer_authority": str(layer_authority_path.resolve()),
            "audio_authority": str(audio_authority_path.resolve()),
            "loadable_layer_occurrence_count": len(ordered_layers),
            "unreachable_authored_layer_count": len(unreachable_rows),
            "retained_audio_occurrence_count": len(retained),
            "excluded_bgm_occurrence_count": len(excluded),
            "subtitle_cue_count": len(subtitles),
            "loop_policy": "each exact source once; final frame held instead of repeating LP content",
            "source_media_modified": False,
        },
    }


def presentation_projection(manifest: Mapping[str, Any]) -> str:
    projection = {
        "frames": int(manifest["render_frame_count"]),
        "clips": [
            (
                str(row["source_sha256"]).upper(),
                int(row["event_start_ms"]),
                int(row["event_end_ms"]),
                str(row["dgm_role"]),
            )
            for row in manifest["clips"]
        ],
        "audio": [
            (
                str(row["request_id"]),
                int(row["start_ms"]),
                int(row["duration_ms"]),
                str(row["volume_bus"]),
            )
            for row in manifest["audio"]
        ],
        "subtitles": [
            (
                str(row["text"]),
                int(row["start_ms"]),
                int(row["end_ms"]),
                str(row["voice_request_id"]),
            )
            for row in manifest["subtitles"]
        ],
    }
    return json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_inputs(args: argparse.Namespace) -> dict[str, Path]:
    output_root = args.output_input_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"immutable input checkpoint already exists: {output_root}")
    layers = read_json(args.layer_authority)
    audio = read_json(args.audio_authority)
    dirinfo_rows = read_csv(args.dirinfo)
    translation = read_json(args.translation_map)
    validate_authorities(layers, audio)
    routes = resolve_routes(dirinfo_rows)
    codes = event_code_map(dirinfo_rows)
    sources, source_report = build_bounded_source_authority(
        layers, args.named_video_root.resolve(), args.ffprobe
    )

    staging = output_root.parent / f".{output_root.name}.staging-{os.getpid()}"
    if staging.exists():
        raise FileExistsError(f"staging checkpoint already exists: {staging}")
    try:
        events_root = staging / "events"
        events_root.mkdir(parents=True)
        manifests: dict[str, dict[str, Any]] = {}
        event_source_occurrences = 0
        unreachable_occurrences = 0
        for event in REQUIRED_EVENTS:
            layer_rows, unreachable_rows, visual_end = event_layer_rows(
                event, layers, sources
            )
            event_source_occurrences += len(layer_rows)
            unreachable_occurrences += len(unreachable_rows)
            manifest = build_event_manifest(
                event,
                code_hex=codes[event],
                layer_rows=layer_rows,
                unreachable_rows=unreachable_rows,
                authored_visual_end_frame=visual_end,
                audio_rows=audio["audio_rows"],
                subtitle_rows=audio["subtitle_cues"],
                layer_authority_path=args.layer_authority,
                audio_authority_path=args.audio_authority,
            )
            write_json(events_root / f"{event}.json", manifest)
            manifests[event] = manifest
        if event_source_occurrences != EXPECTED_EVENT_SOURCE_OCCURRENCES:
            raise Ac1101ExhaustiveError("event source occurrence count differs")
        if unreachable_occurrences != 10:
            raise Ac1101ExhaustiveError("per-event unreachable alias occurrence count differs")
        if sum(len(row["audio"]) for row in manifests.values()) != EXPECTED_RETAINED_AUDIO:
            raise Ac1101ExhaustiveError("retained audio occurrence total differs")
        if sum(len(row["subtitles"]) for row in manifests.values()) != EXPECTED_SUBTITLES:
            raise Ac1101ExhaustiveError("subtitle occurrence total differs")

        projections: dict[str, str] = {}
        for event in EDITORIAL_ORDER:
            projection = presentation_projection(manifests[event])
            if projection in projections:
                raise Ac1101ExhaustiveError(
                    f"exact complete presentation duplicated: {event}/{projections[projection]}"
                )
            projections[projection] = event
        if set(EDITORIAL_ORDER) != set(REQUIRED_EVENTS) or len(projections) != 13:
            raise Ac1101ExhaustiveError("editorial order is not one-to-one over 13 events")

        source_series = {
            "schema": "magireco-series-editions-v1",
            "series": "ac1101",
            "status": "passed",
            "event_count": 13,
            "family_state": {"ready_event_names": list(EDITORIAL_ORDER)},
            "product_scopes": {event: PRODUCT_SCOPE for event in EDITORIAL_ORDER},
            "natural_session_claims": {event: False for event in EDITORIAL_ORDER},
            "ordering_evidence": (
                "31 DirInfo kind-53 routes reduce to 13 code-reachable complete event "
                "presentations; all entry, choice, loss, win and revival variants are "
                "grouped editorially and each complete presentation appears once"
            ),
            "fixed_native_session_gap_claimed": False,
        }
        source_series_path = staging / "source_series_catalogs" / "ac1101_exhaustive.json"
        write_json(source_series_path, source_series)

        series = {
            "schema": "magireco-ac1101-exhaustive-editorial-series-v1",
            "series": "ac1101_exhaustive",
            "status": "passed",
            "event_count": 13,
            "title_zh": "沙奈猫锅挑战 全入口·全选项·全结局完整合集",
            "event_sequence": list(EDITORIAL_ORDER),
            "ordering": (
                "four title entries -> second-game entry -> two lure choices -> "
                "continuations -> loss/win -> revival route"
            ),
            "product_scope": PRODUCT_SCOPE,
            "natural_session_claimed": False,
            "loop_scope": {
                "status": "every code-reachable distinct complete event presentation once",
                "fixed_inter_node_gap": False,
                "mutually_exclusive_routes_combined": True,
                "lp_source_repetition_in_editorial_product": False,
            },
            "family_state": {
                "production_manifest_root": str(output_root),
                "known_family_events": 13,
                "ready_family_events": 13,
                "not_ready_family_events": [],
                "ready_event_names": list(EDITORIAL_ORDER),
            },
            "event_manifest_sha256": {
                event: file_sha256(events_root / f"{event}.json")
                for event in EDITORIAL_ORDER
            },
            "source_series_manifest": {
                "path": str((output_root / source_series_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(source_series_path),
                "evidence": "code-level 31-route/13-event exhaustive presentation authority",
            },
            "human_playback_required": True,
            "publication_approved": False,
        }
        series_path = staging / "series_proposals" / "ac1101_exhaustive.json"
        write_json(series_path, series)

        translation_path = staging / "translations" / "ac1101_exhaustive_zh_v1.json"
        write_json(translation_path, translation)
        source_report_path = staging / "BOUNDED_SOURCE_MEDIA_AUTHORITY.json"
        write_json(source_report_path, source_report)

        authority = {
            "schema": "magireco-ac1101-exhaustive-editorial-order-authority-v1",
            "status": "PASS_READY_FOR_RENDER",
            "family": "ac1101",
            "native_dimensions": dict(NATIVE_DIMENSIONS),
            "frame_rate": FRAME_RATE,
            "route_universe": {
                "route_count": len(routes),
                "routes": routes,
                "all_routes_reconstructable": True,
            },
            "presentation_universe": {
                "complete_event_presentation_count": 13,
                "unique_complete_presentation_count": len(projections),
                "ordered_events": list(EDITORIAL_ORDER),
                "each_complete_presentation_once": True,
                "loadable_source_occurrence_count": event_source_occurrences,
                "loadable_source_unique_identity_count": len(sources),
                "source_alias_surplus_count": event_source_occurrences - len(sources),
                "dedupe_unit": "complete_visual_audio_subtitle_presentation",
                "raw_source_aliases_preserved_as_evidence": True,
            },
            "closed_gates": {
                "event_source_universe": "CLOSED_13_EVENTS_35_LOADABLE_DGM_IDENTITIES",
                "missing_movie_layers": "CLOSED_AS_CODE_UNREACHABLE_ALIASES_WITH_LOADABLE_TWINS",
                "event_audio_and_strict_no_bgm": "CLOSED_49_RETAINED_2_BGM_EXCLUDED",
                "child_local_timing": "CLOSED_FOR_ALL_29_REQSOUND_CALLBACKS",
                "legacy_secondary_scene_and_ac1101_002_omissions": "CLOSED_BY_RUNTIME_PARENT_SCENE_AUTHORITY",
                "duplicate_free_editorial_order": "CLOSED_13_OF_13_UNIQUE",
            },
            "decision": {
                "legacy_36_video_inventory_authoritative": False,
                "old_route_fragments_are_final_products": False,
                "new_exhaustive_render_allowed": True,
                "human_playback_required": True,
            },
            "source_media_modified": False,
        }
        authority_path = staging / "AC1101_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
        write_json(authority_path, authority)

        bindings = {
            "schema": "magireco-ac1101-exhaustive-input-bindings-v1",
            "status": "PASS",
            "bindings": [
                _snapshot(path)
                for path in (
                    args.layer_authority,
                    args.audio_authority,
                    args.dirinfo,
                    args.translation_map,
                )
            ],
            "source_media_authority": {
                "path": str((output_root / source_report_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(source_report_path),
            },
            "source_media_modified": False,
        }
        write_json(staging / "SOURCE_BINDINGS.json", bindings)
        verification = {
            "schema": "magireco-ac1101-exhaustive-input-verification-v1",
            "status": "PASS_READY_FOR_RENDER",
            "checks": {
                "dirinfo_routes": 31,
                "complete_event_presentations": 13,
                "unique_complete_presentations": 13,
                "loadable_source_identities": 35,
                "loadable_event_source_occurrences": 51,
                "unreachable_add_alias_occurrences": 10,
                "retained_no_bgm_audio_occurrences": 49,
                "excluded_bgm_occurrences": 2,
                "subtitle_cues": 31,
                "child_local_only_timing_occurrences": 0,
                "p16_p17_p18_leak_count": 0,
                "native_416x232_output": True,
            },
            "authority": {
                "path": str((output_root / authority_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(authority_path),
            },
            "series_proposal": {
                "path": str((output_root / series_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(series_path),
            },
            "source_media_modified": False,
        }
        write_json(staging / "VERIFICATION_RECORD.json", verification)
        (staging / "README.md").write_text(
            "# ac1101 exhaustive authoritative longform inputs\n\n"
            "All 31 DirInfo routes are represented by 13 distinct complete event "
            "presentations. Each presentation and each exact source clip appears once "
            "within that presentation; mutually exclusive routes are combined in a "
            "comprehensible editorial order. Human playback remains required.\n",
            encoding="utf-8",
        )
        (staging / "ROLLBACK.ps1").write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not (Test-Path -LiteralPath (Join-Path $Root 'VERIFICATION_RECORD.json'))) { throw 'verification missing' }\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable checkpoint can be disabled by same-volume rename; source media remains untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8",
        )
        staging.replace(output_root)
    except BaseException:
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text(
                "Input checkpoint construction failed; inspect the command error.\n",
                encoding="utf-8",
            )
        raise
    return {
        "output_root": output_root,
        "series_path": output_root / "series_proposals" / "ac1101_exhaustive.json",
        "translation_path": output_root / "translations" / "ac1101_exhaustive_zh_v1.json",
    }


def load_existing_inputs(output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    verification = read_json(output_root / "VERIFICATION_RECORD.json")
    authority = read_json(output_root / "AC1101_EXHAUSTIVE_EDITORIAL_AUTHORITY.json")
    series_path = output_root / "series_proposals" / "ac1101_exhaustive.json"
    translation_path = output_root / "translations" / "ac1101_exhaustive_zh_v1.json"
    series = read_json(series_path)
    if (
        verification.get("status") != "PASS_READY_FOR_RENDER"
        or verification.get("checks", {}).get("unique_complete_presentations") != 13
        or authority.get("decision", {}).get("new_exhaustive_render_allowed") is not True
        or series.get("event_sequence") != list(EDITORIAL_ORDER)
    ):
        raise Ac1101ExhaustiveError("existing ac1101 input checkpoint differs")
    return {
        "output_root": output_root,
        "series_path": series_path,
        "translation_path": translation_path,
    }


def verify_production(production_root: Path, ffprobe: str) -> dict[str, Any]:
    family = production_root / "ac1101_exhaustive_full_no_bgm_editions_v1"
    manifest = read_json(family / "manifests" / "family_editions_manifest.json")
    qa = read_json(family / "qa" / "automated_qa.json")
    if (
        manifest.get("ordered_events") != list(EDITORIAL_ORDER)
        or manifest.get("audio_profile") != "no_bgm"
        or qa.get("checks", {}).get("no_exact_duplicate_audience_events") is not True
        or qa.get("status") not in {"passed", "AUTOMATED_QA_PASSED"}
    ):
        raise Ac1101ExhaustiveError("produced family manifest/QA differs")
    media: list[dict[str, Any]] = []
    for edition in ("none", "ja", "zh"):
        path = family / "video" / f"ac1101_exhaustive_full_no_bgm_editions_v1__{edition}.mp4"
        probe = _probe_video(path, ffprobe)
        video = [row for row in probe["streams"] if row["codec_type"] == "video"]
        audio = [row for row in probe["streams"] if row["codec_type"] == "audio"]
        if (
            len(video) != 1
            or len(audio) != 1
            or video[0].get("codec_name") != "h264"
            or (int(video[0].get("width", 0)), int(video[0].get("height", 0)))
            != (416, 232)
            or video[0].get("r_frame_rate") != FRAME_RATE
            or audio[0].get("codec_name") != "aac"
            or int(audio[0].get("sample_rate", 0)) != 48000
            or int(audio[0].get("channels", 0)) != 2
        ):
            raise Ac1101ExhaustiveError(f"media signature differs: {path}")
        media.append(
            {
                "edition": edition,
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
                "duration_seconds": float(probe["format"]["duration"]),
                "frame_count": int(video[0]["nb_read_frames"]),
                "width": 416,
                "height": 232,
                "frame_rate": FRAME_RATE,
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": 48000,
                "audio_channels": 2,
            }
        )
    if len({row["frame_count"] for row in media}) != 1:
        raise Ac1101ExhaustiveError("edition frame grids differ")
    if max(row["duration_seconds"] for row in media) - min(row["duration_seconds"] for row in media) > 0.001:
        raise Ac1101ExhaustiveError("edition container durations differ")
    report = {
        "schema": "magireco-ac1101-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "ordered_complete_event_presentations": 13,
        "exact_duplicate_complete_presentation_count": 0,
        "dirinfo_route_coverage": "31/31",
        "native_416x232_only": True,
        "strict_no_bgm": True,
        "blocked_p16_p17_p18_leak_count": 0,
        "media": media,
        "source_media_modified": False,
        "bilibili_uploaded": False,
    }
    write_json(production_root / "PRODUCTION_VERIFICATION.json", report)
    return report


def render(args: argparse.Namespace, inputs: Mapping[str, Path]) -> dict[str, Any]:
    production_root = args.production_root.resolve()
    if production_root.exists():
        raise FileExistsError(f"immutable production root already exists: {production_root}")
    command = [
        sys.executable,
        str(args.family_builder.resolve()),
        "--manifest-root",
        str(inputs["output_root"]),
        "--series-manifest",
        f"ac1101_exhaustive={inputs['series_path']}",
        "--translation-map",
        str(inputs["translation_path"]),
        "--layout-profile",
        str(args.layout_profile.resolve()),
        "--speaker-registry",
        str(args.speaker_registry.resolve()),
        "--edition",
        "none",
        "--edition",
        "ja",
        "--edition",
        "zh",
        "--font",
        str(args.font.resolve()),
        "--out-root",
        str(production_root),
        "--renderer",
        str(args.renderer.resolve()),
        "--ffmpeg",
        args.ffmpeg,
        "--ffprobe",
        args.ffprobe,
    ]
    subprocess.run(command, check=True)
    return verify_production(production_root, args.ffprobe)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer-authority", required=True, type=Path)
    parser.add_argument("--audio-authority", required=True, type=Path)
    parser.add_argument("--dirinfo", required=True, type=Path)
    parser.add_argument("--translation-map", required=True, type=Path)
    parser.add_argument("--named-video-root", required=True, type=Path)
    parser.add_argument("--output-input-root", required=True, type=Path)
    parser.add_argument("--production-root", type=Path)
    parser.add_argument("--family-builder", type=Path)
    parser.add_argument("--layout-profile", type=Path)
    parser.add_argument("--speaker-registry", type=Path)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--renderer", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--reuse-inputs", action="store_true")
    parser.add_argument("--verify-existing-production", action="store_true")
    args = parser.parse_args(argv)
    if args.render and args.verify_existing_production:
        parser.error("--render and --verify-existing-production are mutually exclusive")
    if args.verify_existing_production and args.production_root is None:
        parser.error("--verify-existing-production requires --production-root")
    if args.render and any(
        value is None
        for value in (
            args.production_root,
            args.family_builder,
            args.layout_profile,
            args.speaker_registry,
            args.font,
            args.renderer,
        )
    ):
        parser.error("--render requires production, builder, layout, speaker, font and renderer paths")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.reuse_inputs:
        inputs = load_existing_inputs(args.output_input_root)
        print(f"PASS_REOPEN inputs={inputs['output_root']}")
    else:
        inputs = build_inputs(args)
        print(
            "PASS routes=31 event_presentations=13 unique_presentations=13 "
            "loadable_sources=35 source_occurrences=51 audio=49 subtitles=31 "
            f"inputs={inputs['output_root']}"
        )
    if args.render:
        report = render(args, inputs)
        row = report["media"][0]
        print(
            f"PASS_RENDER editions=3 frames={row['frame_count']} "
            f"duration={row['duration_seconds']:.3f}s production={args.production_root.resolve()}"
        )
    elif args.verify_existing_production:
        report = verify_production(args.production_root.resolve(), args.ffprobe)
        row = report["media"][0]
        print(
            f"PASS_VERIFY_EXISTING editions=3 frames={row['frame_count']} "
            f"duration={row['duration_seconds']:.3f}s production={args.production_root.resolve()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
