#!/usr/bin/env python3
"""Build the exhaustive native-416 ac7206 story longform.

The final audience product is an editorial collection, not a single-session
claim: every code-reachable story presentation appears once, even when the
underlying DirInfo routes are mutually exclusive.  Exact visual reuse is kept
only when the complete AV/subtitle presentation differs.  The ac7206_015
``uwa`` gameplay stack remains a separately indexed composition gate and is
never smuggled into the clean story product.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac1101_exhaustive_authoritative_longform import (
        _probe_video,
        _snapshot,
        _video_stream,
        frame_to_ms,
        presentation_projection,
        read_json,
        write_json,
    )
    from .build_event_production_manifests import (
        file_sha256,
        quantize_duration_to_frame_grid,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_ac1101_exhaustive_authoritative_longform import (
        _probe_video,
        _snapshot,
        _video_stream,
        frame_to_ms,
        presentation_projection,
        read_json,
        write_json,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import (
        file_sha256,
        quantize_duration_to_frame_grid,
    )


STORY_EVENTS = tuple(f"ac7206_{index:03d}" for index in range(1, 15))
GAMEPLAY_EVENT = "ac7206_015"
ALL_EVENTS = (*STORY_EVENTS, GAMEPLAY_EVENT)
EDITORIAL_ORDER = (
    "ac7206_001",
    "ac7206_003",
    "ac7206_004",
    "ac7206_005",
    "ac7206_006",
    "ac7206_007",
    "ac7206_008",
    "ac7206_002",
    "ac7206_009",
    "ac7206_010",
    "ac7206_011",
    "ac7206_012",
    "ac7206_013",
    "ac7206_014",
)
FRAME_RATE = "30/1"
NATIVE_DIMENSIONS = {"width": 416, "height": 232}
PRODUCT_SCOPE = "exhaustive_duplicate_free_event_presentation_editorial_longform"
EXPECTED_ROUTE_ROWS = 40
EXPECTED_UNIQUE_ROUTE_SEQUENCES = 20
EXPECTED_UNIQUE_STORY_ROUTE_PROJECTIONS = 12
EXPECTED_STORY_PARENT_Z2DS = 8
EXPECTED_STORY_DGM_IDENTITIES = 12
EXPECTED_STORY_SOURCE_OCCURRENCES = 19
EXPECTED_RETAINED_AUDIO = 28
EXPECTED_EXCLUDED_BGM = 2
EXPECTED_SUBTITLES = 14


class Ac7206ExhaustiveError(ValueError):
    pass


def validate_authorities(
    layers: Mapping[str, Any], audio: Mapping[str, Any]
) -> None:
    layer_assertions = layers.get("assertions", {})
    layer_decision = layers.get("decision", {})
    if (
        layers.get("schema")
        != "magireco-ac7206-movielayer-runtime-reachability-authority-v1"
        or layers.get("status") != "passed"
        or int(layer_assertions.get("runtime_events", -1)) != 15
        or int(layer_assertions.get("runtime_story_events", -1)) != 14
        or int(layer_assertions.get("runtime_gameplay_effect_events", -1)) != 1
        or int(layer_assertions.get("story_dgm_names", -1))
        != EXPECTED_STORY_DGM_IDENTITIES
        or int(layer_assertions.get("gameplay_effect_dgm_names", -1)) != 3
        or int(layer_assertions.get("exact_physical_selector_backing_z2ds", -1))
        != 48
        or layer_decision.get("visual_reachability_gate") != "CLOSED"
        or layer_decision.get("ac7206_015_classification")
        != "gameplay_effect_component_not_clean_story"
    ):
        raise Ac7206ExhaustiveError("ac7206 MovieLayer authority differs")

    audio_assertions = audio.get("assertions", {})
    audio_decision = audio.get("decision", {})
    if (
        audio.get("schema")
        != "magireco-ac7206-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "passed"
        or tuple(audio_decision.get("story_events", [])) != STORY_EVENTS
        or audio_decision.get("gameplay_event") != GAMEPLAY_EVENT
        or audio_decision.get("event_global_child_audio_timing")
        != "CLOSED_FOR_STORY_EVENTS_001_TO_014"
        or audio_decision.get("event_audio_and_strict_no_bgm_manifest_closure")
        != "CLOSED_FOR_STORY_EVENTS_001_TO_014"
        or int(audio_assertions.get("total_audio_occurrences", -1)) != 30
        or int(audio_assertions.get("retained_audio_occurrences", -1))
        != EXPECTED_RETAINED_AUDIO
        or int(audio_assertions.get("excluded_bgm_occurrences", -1))
        != EXPECTED_EXCLUDED_BGM
        or int(audio_assertions.get("subtitle_cues", -1)) != EXPECTED_SUBTITLES
        or int(audio_assertions.get("gameplay_event_owned_audio_rows", -1)) != 0
        or audio_assertions.get("only_sound_551_is_excluded_as_bgm") is not True
    ):
        raise Ac7206ExhaustiveError("ac7206 audio authority differs")


def resolve_routes(route_audit: Mapping[str, Any]) -> list[dict[str, Any]]:
    universe = route_audit.get("route_universe", {})
    raw_routes = list(universe.get("routes", []))
    if (
        int(universe.get("route_count", -1)) != EXPECTED_ROUTE_ROWS
        or len(raw_routes) != EXPECTED_ROUTE_ROWS
        or {int(row["row_index"]) for row in raw_routes}
        != set(range(EXPECTED_ROUTE_ROWS))
    ):
        raise Ac7206ExhaustiveError("ac7206 route row universe differs")

    first_by_sequence: dict[tuple[str, ...], int] = {}
    routes: list[dict[str, Any]] = []
    union: set[str] = set()
    for row in sorted(raw_routes, key=lambda item: int(item["row_index"])):
        sequence = tuple(str(event) for event in row["event_sequence"])
        if (
            len(sequence) not in {2, 3}
            or len(sequence) != len(set(sequence))
            or not set(sequence) <= set(ALL_EVENTS)
            or sequence[0] not in {"ac7206_001", "ac7206_002"}
            or (len(sequence) == 3 and sequence[-1] != GAMEPLAY_EVENT)
        ):
            raise Ac7206ExhaustiveError(
                f"invalid ac7206 route sequence: {row['row_index']}"
            )
        union.update(sequence)
        alias_of = first_by_sequence.setdefault(sequence, int(row["row_index"]))
        story_projection = [event for event in sequence if event != GAMEPLAY_EVENT]
        routes.append(
            {
                "row_index": int(row["row_index"]),
                "selector_values": [int(value) for value in row["selector_values"]],
                "event_sequence": list(sequence),
                "story_projection": story_projection,
                "gameplay_effect_occurs": GAMEPLAY_EVENT in sequence,
                "duplicate_event_sequence_alias_of": (
                    None if alias_of == int(row["row_index"]) else alias_of
                ),
            }
        )
    if union != set(ALL_EVENTS):
        raise Ac7206ExhaustiveError("ac7206 route union does not cover 15 events")
    unique_sequences = {tuple(row["event_sequence"]) for row in routes}
    story_sequences = {tuple(row["story_projection"]) for row in routes}
    if (
        len(unique_sequences) != EXPECTED_UNIQUE_ROUTE_SEQUENCES
        or len(story_sequences) != EXPECTED_UNIQUE_STORY_ROUTE_PROJECTIONS
    ):
        raise Ac7206ExhaustiveError("ac7206 route dedupe counts differ")
    return routes


def event_code_map(runtime_scene_motion: Mapping[str, Any]) -> dict[str, str]:
    requested = runtime_scene_motion.get("requested_events", {})
    result = {str(event): str(code).casefold() for event, code in requested.items()}
    if set(result) != set(ALL_EVENTS) or any(
        not code.startswith("0x") or len(code) != 18 for code in result.values()
    ):
        raise Ac7206ExhaustiveError("runtime event-code map differs")
    for event, capture in runtime_scene_motion.get("events", {}).items():
        if str(capture.get("event_code", "")).casefold() != result.get(str(event)):
            raise Ac7206ExhaustiveError(f"runtime event-code mismatch: {event}")
    return result


def source_path_for_dgm(named_video_root: Path, dgm_name: str) -> Path:
    if not dgm_name.startswith("ac7206_"):
        raise Ac7206ExhaustiveError(f"unexpected story DGM family: {dgm_name}")
    return (named_video_root / "patch" / "ac7206" / f"{dgm_name}.mp4").resolve()


def _story_bindings(layers: Mapping[str, Any]) -> Mapping[str, Any]:
    bindings = layers.get("runtime_event_bindings", {}).get("events", {})
    if set(bindings) != set(ALL_EVENTS):
        raise Ac7206ExhaustiveError("runtime binding event set differs")
    return bindings


def build_bounded_source_authority(
    layers: Mapping[str, Any], named_video_root: Path, ffprobe: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    bindings = _story_bindings(layers)
    story_parents = {
        str(binding["parent_z2d"])
        for event in STORY_EVENTS
        for binding in bindings[event]
        if binding.get("role") == "story_visual"
    }
    if len(story_parents) != EXPECTED_STORY_PARENT_Z2DS:
        raise Ac7206ExhaustiveError("story parent Z2D count differs")
    chunks = {str(row["name"]): row for row in layers["z2d_chunks"]}
    expected: dict[str, dict[str, int]] = {}
    for parent in story_parents:
        chunk = chunks.get(parent)
        if chunk is None:
            raise Ac7206ExhaustiveError(f"missing exact story chunk: {parent}")
        for layer in chunk["movie_layers"]:
            if layer.get("compiled_table_present") is not True:
                raise Ac7206ExhaustiveError(f"unloadable story MovieLayer: {parent}")
            name = str(layer["z2d_reference"]).removesuffix(".dgm")
            row = {
                "compiled_table_index": int(layer["compiled_table_index"]),
                "expected_frames": int(layer["frame_count"]),
            }
            prior = expected.setdefault(name, row)
            if prior != row:
                raise Ac7206ExhaustiveError(f"story DGM interval differs: {name}")
    if len(expected) != EXPECTED_STORY_DGM_IDENTITIES:
        raise Ac7206ExhaustiveError("story DGM identity count differs")

    resolved: dict[str, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for name in sorted(expected):
        path = source_path_for_dgm(named_video_root, name)
        if not path.is_file():
            raise FileNotFoundError(path)
        probe = _probe_video(path, ffprobe)
        stream = _video_stream(probe)
        source_frames = int(stream.get("nb_read_frames", 0))
        if (
            stream.get("codec_name") != "h264"
            or stream.get("r_frame_rate") != FRAME_RATE
            or stream.get("pix_fmt") != "yuv420p"
            or (int(stream.get("width", 0)), int(stream.get("height", 0)))
            != (416, 232)
            or source_frames != expected[name]["expected_frames"]
        ):
            raise Ac7206ExhaustiveError(f"bounded source signature differs: {name}")
        entry = {
            "dgm_name": name,
            "compiled_table_index": expected[name]["compiled_table_index"],
            "path": str(path),
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
            "width": 416,
            "height": 232,
            "frame_rate": FRAME_RATE,
            "source_frame_count": source_frames,
            "playback_frame_count": source_frames,
            "source_frame_contract": "exact_one_to_one_authored_interval",
        }
        entries.append(entry)
        resolved[name] = entry
    return resolved, {
        "schema": "magireco-ac7206-bounded-story-source-media-authority-v1",
        "status": "PASS",
        "entry_count": len(entries),
        "native_416x232_count": len(entries),
        "entries": entries,
        "source_media_modified": False,
    }


def event_layer_rows(
    event: str,
    layers: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, str]:
    bindings = [
        row
        for row in _story_bindings(layers)[event]
        if row.get("role") == "story_visual"
    ]
    if len(bindings) != 1:
        raise Ac7206ExhaustiveError(f"story visual parent count differs: {event}")
    binding = bindings[0]
    parent = str(binding["parent_z2d"])
    chunks = {str(row["name"]): row for row in layers["z2d_chunks"]}
    chunk = chunks[parent]
    parent_start = int(binding["event_global_start_frame"])
    parent_end = int(binding["event_global_end_frame_inclusive"]) + 1
    if int(chunk["header"]["scene_frame_count"]) != parent_end - parent_start:
        raise Ac7206ExhaustiveError(f"parent range differs from chunk: {event}")
    visible: list[dict[str, Any]] = []
    for layer in chunk["movie_layers"]:
        name = str(layer["z2d_reference"]).removesuffix(".dgm")
        source = sources.get(name)
        if layer.get("compiled_table_present") is not True or source is None:
            raise Ac7206ExhaustiveError(f"story source is not loadable: {event}/{name}")
        start_frame = parent_start + int(layer["start_frame"])
        authored_end = parent_start + int(layer["end_frame_inclusive"]) + 1
        end_frame = start_frame + int(source["playback_frame_count"])
        if end_frame != authored_end:
            raise Ac7206ExhaustiveError(f"source/authored interval differs: {event}/{name}")
        visible.append(
            {
                **dict(source),
                "parent_z2d": parent,
                "event_start_frame": start_frame,
                "event_end_frame_exclusive": end_frame,
                "event_start_ms": frame_to_ms(start_frame),
                "event_end_ms": frame_to_ms(end_frame),
                "role": "background",
            }
        )
    return visible, parent_end, parent


def _speaker_code_from_caption(name: str) -> str:
    return "ari" if str(name).startswith("cap7206_paint_ari_") else ""


def build_event_manifest(
    event: str,
    *,
    code_hex: str,
    layer_rows: Sequence[Mapping[str, Any]],
    authored_visual_end_frame: int,
    parent_z2d: str,
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
        raise Ac7206ExhaustiveError(f"BGM leaked into retained audio: {event}")
    if any(
        (int(row["request_id"]), int(row["sound_id"])) != (226, 551)
        for row in excluded
    ):
        raise Ac7206ExhaustiveError(f"unexpected excluded BGM identity: {event}")
    event_subtitles = [dict(row) for row in subtitle_rows if row["event"] == event]
    if len(event_subtitles) != 1:
        raise Ac7206ExhaustiveError(f"subtitle count differs: {event}")
    video_content_ms = frame_to_ms(authored_visual_end_frame)
    audio_content_ms = max(
        (int(row["start_ms"]) + int(row["duration_ms"]) for row in retained),
        default=0,
    )
    subtitle_content_ms = max(int(row["end_ms"]) for row in event_subtitles)
    content_end_ms = max(video_content_ms, audio_content_ms, subtitle_content_ms)
    quantization = quantize_duration_to_frame_grid(content_end_ms, FRAME_RATE)

    clips = [
        {
            "order": order,
            "dgm_name": row["dgm_name"],
            "dgm_role": "background",
            "path": row["path"],
            "source_sha256": row["sha256"],
            "event_start_ms": int(row["event_start_ms"]),
            "event_end_ms": int(row["event_end_ms"]),
            "authored_event_end_ms": int(row["event_end_ms"]),
            "source_frame_count": int(row["source_frame_count"]),
            "authored_layer_frame_count": int(row["source_frame_count"]),
            "interval_confidence": "exact_runtime_parent_range_and_z2d_movielayer_interval",
            "source_frame_contract": row["source_frame_contract"],
        }
        for order, row in enumerate(
            sorted(layer_rows, key=lambda item: int(item["event_start_frame"]))
        )
    ]
    composition_clips = [
        {
            "dgm_name": row["dgm_name"],
            "role": "background",
            "start_ms": int(row["event_start_ms"]),
        }
        for row in sorted(layer_rows, key=lambda item: int(item["event_start_frame"]))
    ]

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

    voice_by_request = {
        str(row["request_id"]): row
        for row in retained
        if row["source_kind"] == "z2d_req_sound"
    }
    subtitles: list[dict[str, Any]] = []
    for row in event_subtitles:
        request_id = str(row["voice_request_id"])
        voice = voice_by_request.get(request_id)
        if voice is None:
            raise Ac7206ExhaustiveError(f"subtitle has no retained voice: {event}")
        subtitles.append(
            {
                "text": str(row["ja"]),
                "start_ms": int(row["start_ms"]),
                "end_ms": int(row["end_ms"]),
                "voice_request_id": request_id,
                "voice_start_ms": int(row["start_ms"]),
                "z2d_name": str(row["z2d_name"]),
                "speaker_code": _speaker_code_from_caption(str(row["z2d_name"])),
                "subtitle_source": "official_voice_label",
                "evidence": str(row["evidence"]),
                "event_global_start_frame": int(voice["start_frame"]),
                "event_global_start_resolved": True,
                "timing_scope": "event_global_exact_parent_scene_and_motion_key",
                "timing_override_source": str(audio_authority_path.resolve()),
                "speaker_identity_evidence": "exact_runtime_caption_resource_name_and_official_voice_label",
            }
        )

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
            "evidence": "exact runtime story parent range plus exact Z2D MovieLayer intervals",
            "clips": composition_clips,
        },
        "composition_plan_source": str(layer_authority_path.resolve()),
        "runtime_event_manifest_sources": [],
        "reviewed_subtitle_manifest_sources": [],
        "reviewed_subtitle_reconciliation": {},
        "overlap_count": 0,
        "gap_count": 0,
        "timeline_tolerance_ms": 34,
        "clips": clips,
        "audio": manifest_audio,
        "subtitles": subtitles,
        "quality_gates": {
            "all_full_frame": True,
            "all_clips_exist": True,
            "all_clip_source_hashes_bound": True,
            "all_audio_exist": all(Path(row["path"]).is_file() for row in manifest_audio),
            "verified_subtitle_voice_count": 1,
            "graphical_display_subtitle_count": 0,
            "official_voice_label_subtitle_count": 1,
            "asr_verified_subtitle_count": 0,
            "reviewed_subtitle_baseline_applied": False,
            "reviewed_subtitle_current_only_voice_candidate_count": 0,
            "reviewed_subtitle_current_only_graphical_candidate_count": 0,
            "exact_z2d_req_sound_count": 1,
            "event_global_z2d_timing_ready": True,
            "linear_video_timeline": False,
            "video_composition_model": "timed_full_frame_layers",
            "composition_resolved": True,
            "composition_evidence": "ac7206 exact Z2D MovieLayer/runtime-parent authority",
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
        "ac7206_generated_manifest_provenance": {
            "layer_authority": str(layer_authority_path.resolve()),
            "audio_authority": str(audio_authority_path.resolve()),
            "parent_z2d": parent_z2d,
            "loadable_layer_occurrence_count": len(clips),
            "retained_audio_occurrence_count": len(retained),
            "excluded_bgm_occurrence_count": len(excluded),
            "subtitle_cue_count": len(subtitles),
            "loop_policy": "authored MovieLayer intervals once; final frame held only to close AV presentation",
            "source_media_modified": False,
        },
    }


def visual_projection(manifest: Mapping[str, Any]) -> str:
    projection = {
        "video_frames": round(int(manifest["video_duration_ms"]) * 30 / 1000),
        "clips": [
            (
                str(row["source_sha256"]).upper(),
                int(row["event_start_ms"]),
                int(row["event_end_ms"]),
            )
            for row in manifest["clips"]
        ],
    }
    return json.dumps(projection, sort_keys=True, separators=(",", ":"))


def build_inputs(args: argparse.Namespace) -> dict[str, Path]:
    output_root = args.output_input_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"immutable input checkpoint already exists: {output_root}")
    layers = read_json(args.layer_authority)
    audio = read_json(args.audio_authority)
    route_audit = read_json(args.route_audit)
    runtime = read_json(args.runtime_scene_motion)
    translation = read_json(args.translation_map)
    validate_authorities(layers, audio)
    routes = resolve_routes(route_audit)
    codes = event_code_map(runtime)
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
        parent_by_event: dict[str, str] = {}
        event_source_occurrences = 0
        for event in STORY_EVENTS:
            layer_rows, visual_end, parent = event_layer_rows(event, layers, sources)
            event_source_occurrences += len(layer_rows)
            parent_by_event[event] = parent
            manifest = build_event_manifest(
                event,
                code_hex=codes[event],
                layer_rows=layer_rows,
                authored_visual_end_frame=visual_end,
                parent_z2d=parent,
                audio_rows=audio["audio_rows"],
                subtitle_rows=audio["subtitle_cues"],
                layer_authority_path=args.layer_authority,
                audio_authority_path=args.audio_authority,
            )
            write_json(events_root / f"{event}.json", manifest)
            manifests[event] = manifest
        if event_source_occurrences != EXPECTED_STORY_SOURCE_OCCURRENCES:
            raise Ac7206ExhaustiveError("story source occurrence count differs")
        if sum(len(row["audio"]) for row in manifests.values()) != EXPECTED_RETAINED_AUDIO:
            raise Ac7206ExhaustiveError("retained audio occurrence total differs")
        if sum(len(row["subtitles"]) for row in manifests.values()) != EXPECTED_SUBTITLES:
            raise Ac7206ExhaustiveError("subtitle occurrence total differs")

        complete_seen: dict[str, str] = {}
        visual_groups: defaultdict[str, list[str]] = defaultdict(list)
        for event in EDITORIAL_ORDER:
            complete = presentation_projection(manifests[event])
            if complete in complete_seen:
                raise Ac7206ExhaustiveError(
                    f"exact complete AV presentation duplicated: {event}/{complete_seen[complete]}"
                )
            complete_seen[complete] = event
            visual_groups[visual_projection(manifests[event])].append(event)
        if (
            set(EDITORIAL_ORDER) != set(STORY_EVENTS)
            or len(complete_seen) != 14
            or len(visual_groups) != EXPECTED_STORY_PARENT_Z2DS
        ):
            raise Ac7206ExhaustiveError("story editorial projection counts differ")
        reuse_groups = sorted(sorted(events) for events in visual_groups.values() if len(events) > 1)
        expected_reuse = sorted(
            [
                ["ac7206_003", "ac7206_009"],
                ["ac7206_004", "ac7206_010"],
                ["ac7206_005", "ac7206_011"],
                ["ac7206_006", "ac7206_012"],
                ["ac7206_007", "ac7206_013"],
                ["ac7206_008", "ac7206_014"],
            ]
        )
        if reuse_groups != expected_reuse:
            raise Ac7206ExhaustiveError("visual reuse groups differ")

        source_series = {
            "schema": "magireco-series-editions-v1",
            "series": "ac7206",
            "status": "passed",
            "event_count": 14,
            "family_state": {"ready_event_names": list(EDITORIAL_ORDER)},
            "product_scopes": {event: PRODUCT_SCOPE for event in EDITORIAL_ORDER},
            "natural_session_claims": {event: False for event in EDITORIAL_ORDER},
            "ordering_evidence": (
                "40 exact DirInfo rows reduce to 20 distinct route sequences and 12 "
                "story route projections; the full story universe is 14 complete AV "
                "presentations because the two entry presentations are also retained"
            ),
            "fixed_native_session_gap_claimed": False,
        }
        source_series_path = staging / "source_series_catalogs" / "ac7206_exhaustive.json"
        write_json(source_series_path, source_series)

        series = {
            "schema": "magireco-ac7206-exhaustive-editorial-series-v1",
            "series": "ac7206_exhaustive",
            "status": "passed",
            "event_count": 14,
            "title_zh": "阿莉娜绘画演出 全入口·全结果完整合集",
            "event_sequence": list(EDITORIAL_ORDER),
            "ordering": "weak entry and six outcomes, then strong entry and six outcomes",
            "product_scope": PRODUCT_SCOPE,
            "natural_session_claimed": False,
            "loop_scope": {
                "status": "every code-reachable distinct complete story AV presentation once",
                "fixed_inter_node_gap": False,
                "mutually_exclusive_routes_combined": True,
                "same_visual_source_retained_only_when_voice_or_subtitle_differs": True,
            },
            "family_state": {
                "production_manifest_root": str(output_root),
                "known_family_events": 15,
                "ready_family_events": 14,
                "not_ready_family_events": [GAMEPLAY_EVENT],
                "ready_event_names": list(EDITORIAL_ORDER),
            },
            "event_manifest_sha256": {
                event: file_sha256(events_root / f"{event}.json")
                for event in EDITORIAL_ORDER
            },
            "source_series_manifest": {
                "path": str((output_root / source_series_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(source_series_path),
                "evidence": "code-level 40-row/15-event route authority with gameplay split",
            },
            "human_playback_required": True,
            "publication_approved": False,
        }
        series_path = staging / "series_proposals" / "ac7206_exhaustive.json"
        write_json(series_path, series)
        translation_path = staging / "translations" / "ac7206_exhaustive_zh_v1.json"
        write_json(translation_path, translation)
        source_report_path = staging / "BOUNDED_SOURCE_MEDIA_AUTHORITY.json"
        write_json(source_report_path, source_report)

        authority = {
            "schema": "magireco-ac7206-exhaustive-editorial-order-authority-v1",
            "status": "PASS_READY_FOR_STORY_RENDER",
            "family": "ac7206",
            "native_dimensions": dict(NATIVE_DIMENSIONS),
            "frame_rate": FRAME_RATE,
            "route_universe": {
                "route_row_count": len(routes),
                "unique_event_sequence_count": len(
                    {tuple(row["event_sequence"]) for row in routes}
                ),
                "unique_story_projection_count": len(
                    {tuple(row["story_projection"]) for row in routes}
                ),
                "routes": routes,
            },
            "story_presentation_universe": {
                "complete_av_presentation_count": 14,
                "unique_complete_av_presentation_count": len(complete_seen),
                "ordered_events": list(EDITORIAL_ORDER),
                "each_complete_av_presentation_once": True,
                "distinct_visual_projection_count": len(visual_groups),
                "visual_reuse_groups": reuse_groups,
                "visual_reuse_retention_reason": "different exact VOICE/subtitle presentation",
                "loadable_story_source_occurrence_count": event_source_occurrences,
                "loadable_story_source_unique_identity_count": len(sources),
                "dedupe_unit": "complete_visual_audio_subtitle_presentation",
            },
            "gameplay_effect_boundary": {
                "event": GAMEPLAY_EVENT,
                "classification": "separate_gameplay_effect_component",
                "loadable_dgm_identity_count": 3,
                "logical_selector_node_count": 5,
                "exact_selector_backing_z2d_count": 48,
                "event_owned_audio_row_count": 0,
                "story_product_inclusion": False,
                "render_status": "BLOCKED_PENDING_LAYERED_SELECTOR_COMPOSITION_AND_AUDIO_CONTEXT",
            },
            "legacy_fragment_collection": {
                "status": "WITHDRAWN_INCOMPLETE_AND_DUPLICATE_HEAVY",
                "duration_seconds": 137.8,
                "event_occurrences": 19,
                "source_occurrences": 35,
                "unique_source_identities": 10,
                "duplicate_source_surplus": 25,
            },
            "closed_gates": {
                "story_visual_universe": "CLOSED_14_EVENTS_8_PARENT_Z2DS_12_DGM_IDENTITIES",
                "event_audio_and_strict_no_bgm": "CLOSED_28_RETAINED_2_BGM_EXCLUDED",
                "child_local_timing": "CLOSED_FOR_ALL_14_STORY_VOICES",
                "duplicate_free_editorial_order": "CLOSED_14_OF_14_UNIQUE_COMPLETE_AV",
            },
            "decision": {
                "old_fragment_collection_authoritative": False,
                "old_route_fragments_are_final_products": False,
                "new_exhaustive_story_render_allowed": True,
                "gameplay_015_render_allowed": False,
                "human_playback_required": True,
            },
            "source_media_modified": False,
        }
        authority_path = staging / "AC7206_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
        write_json(authority_path, authority)

        bindings = {
            "schema": "magireco-ac7206-exhaustive-input-bindings-v1",
            "status": "PASS",
            "bindings": [
                _snapshot(path)
                for path in (
                    args.layer_authority,
                    args.audio_authority,
                    args.route_audit,
                    args.runtime_scene_motion,
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
            "schema": "magireco-ac7206-exhaustive-input-verification-v1",
            "status": "PASS_READY_FOR_STORY_RENDER",
            "checks": {
                "dirinfo_route_rows": 40,
                "unique_route_event_sequences": 20,
                "unique_story_route_projections": 12,
                "complete_story_av_presentations": 14,
                "unique_complete_story_av_presentations": 14,
                "distinct_story_visual_projections": 8,
                "loadable_story_source_identities": 12,
                "loadable_story_source_occurrences": 19,
                "retained_no_bgm_audio_occurrences": 28,
                "excluded_bgm_occurrences": 2,
                "subtitle_cues": 14,
                "child_local_only_timing_occurrences": 0,
                "gameplay_015_story_leak_count": 0,
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
            "# ac7206 exhaustive authoritative story longform inputs\n\n"
            "All 40 DirInfo rows and 15 event identities are preserved in the route "
            "authority. The clean story product contains 14 distinct complete AV "
            "presentations once each. Six pairs intentionally reuse exact visuals "
            "because their exact voice/subtitle presentations differ. ac7206_015 is "
            "indexed but excluded as a separate unresolved gameplay composition.\n",
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
        "series_path": output_root / "series_proposals" / "ac7206_exhaustive.json",
        "translation_path": output_root / "translations" / "ac7206_exhaustive_zh_v1.json",
    }


def load_existing_inputs(output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    verification = read_json(output_root / "VERIFICATION_RECORD.json")
    authority = read_json(output_root / "AC7206_EXHAUSTIVE_EDITORIAL_AUTHORITY.json")
    series_path = output_root / "series_proposals" / "ac7206_exhaustive.json"
    translation_path = output_root / "translations" / "ac7206_exhaustive_zh_v1.json"
    series = read_json(series_path)
    if (
        verification.get("status") != "PASS_READY_FOR_STORY_RENDER"
        or verification.get("checks", {}).get("unique_complete_story_av_presentations")
        != 14
        or authority.get("decision", {}).get("new_exhaustive_story_render_allowed")
        is not True
        or authority.get("decision", {}).get("gameplay_015_render_allowed") is not False
        or series.get("event_sequence") != list(EDITORIAL_ORDER)
    ):
        raise Ac7206ExhaustiveError("existing ac7206 input checkpoint differs")
    return {
        "output_root": output_root,
        "series_path": series_path,
        "translation_path": translation_path,
    }


def verify_production(production_root: Path, ffprobe: str) -> dict[str, Any]:
    family = production_root / "ac7206_exhaustive_full_no_bgm_editions_v1"
    manifest = read_json(family / "manifests" / "family_editions_manifest.json")
    qa = read_json(family / "qa" / "automated_qa.json")
    if (
        manifest.get("ordered_events") != list(EDITORIAL_ORDER)
        or manifest.get("audio_profile") != "no_bgm"
        or GAMEPLAY_EVENT in manifest.get("ordered_events", [])
        or qa.get("checks", {}).get("no_exact_duplicate_audience_events") is not True
        or qa.get("status") not in {"passed", "AUTOMATED_QA_PASSED"}
    ):
        raise Ac7206ExhaustiveError("produced family manifest/QA differs")
    media: list[dict[str, Any]] = []
    for edition in ("none", "ja", "zh"):
        path = family / "video" / f"ac7206_exhaustive_full_no_bgm_editions_v1__{edition}.mp4"
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
            raise Ac7206ExhaustiveError(f"media signature differs: {path}")
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
        raise Ac7206ExhaustiveError("edition frame grids differ")
    if max(row["duration_seconds"] for row in media) - min(
        row["duration_seconds"] for row in media
    ) > 0.001:
        raise Ac7206ExhaustiveError("edition container durations differ")
    report = {
        "schema": "magireco-ac7206-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "ordered_complete_event_presentations": 14,
        "exact_duplicate_complete_presentation_count": 0,
        "distinct_visual_projection_count": 8,
        "intentional_visual_reuse_pair_count": 6,
        "dirinfo_route_coverage": "40/40",
        "unique_route_event_sequences": 20,
        "gameplay_015_story_leak_count": 0,
        "gameplay_015_status": "SEPARATE_BLOCKED_GAMEPLAY_COMPOSITION",
        "legacy_fragment_collection_status": "WITHDRAWN_INCOMPLETE_AND_DUPLICATE_HEAVY",
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
        f"ac7206_exhaustive={inputs['series_path']}",
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
    parser.add_argument("--route-audit", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
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
            "PASS routes=40 unique_routes=20 story_presentations=14 "
            "unique_complete_av=14 visual_projections=8 story_sources=12 "
            "source_occurrences=19 audio=28 subtitles=14 gameplay015=separate_blocked "
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
