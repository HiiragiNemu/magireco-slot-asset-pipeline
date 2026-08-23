#!/usr/bin/env python3
"""Build the duplicate-free native-416 ac7210 exhaustive story longform.

The product is an editorial collection, not a native single-session claim.  It
keeps every code-reachable native-416 story presentation once, combines the two
mutually exclusive approach branches in a comprehensible order, and omits one
byte-identical authored MovieLayer alias.  The native-512/component terminals
remain indexed but outside this higher-priority clean-story product.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import subprocess
import sys
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


STORY_EVENTS = tuple(f"ac7210_{index:03d}" for index in range(1, 6))
DEFERRED_EVENTS = tuple(f"ac7210_{index:03d}" for index in range(6, 9))
ALL_EVENTS = (*STORY_EVENTS, *DEFERRED_EVENTS)
EDITORIAL_ORDER = (
    "ac7210_001",
    "ac7210_002",
    "ac7210_005",
    "ac7210_003",
    "ac7210_004",
)
FRAME_RATE = "30/1"
NATIVE_DIMENSIONS = {"width": 416, "height": 232}
PRODUCT_SCOPE = "exhaustive_duplicate_free_source_presentation_editorial_longform"
EXPECTED_ROUTE_ROWS = 5
EXPECTED_STORY_SOURCE_OCCURRENCES = 14
EXPECTED_CANONICAL_STORY_SOURCES = 13
EXPECTED_AUDIO = 10
EXPECTED_SUBTITLES = 4
EXPECTED_PRESENTATION_FRAMES = 1354


class Ac7210ExhaustiveError(ValueError):
    pass


def validate_authorities(
    visual: Mapping[str, Any], audio: Mapping[str, Any]
) -> None:
    visual_assertions = visual.get("assertions", {})
    visual_decision = visual.get("decision", {})
    if (
        visual.get("schema")
        != "magireco-ac7210-movielayer-runtime-reachability-authority-v1"
        or visual.get("status") != "passed"
        or int(visual_assertions.get("dirinfo_route_count", -1)) != EXPECTED_ROUTE_ROWS
        or int(visual_assertions.get("runtime_event_count", -1)) != len(ALL_EVENTS)
        or int(visual_assertions.get("native416_story_layer_occurrence_count", -1))
        != EXPECTED_STORY_SOURCE_OCCURRENCES
        or int(visual_assertions.get("native416_canonical_story_identity_count", -1))
        != EXPECTED_CANONICAL_STORY_SOURCES
        or int(visual_assertions.get("native416_byte_identical_pair_count", -1)) != 1
        or visual_assertions.get("all_native416_story_sources_are_416x232") is not True
        or visual_assertions.get("all_story_sources_unique_after_alias_dedup") is not True
        or tuple(visual_decision.get("native416_story_events", [])) != STORY_EVENTS
        or tuple(visual_decision.get("lower_priority_512_component_events", []))
        != DEFERRED_EVENTS
        or tuple(visual_decision.get("native416_exhaustive_editorial_order", []))
        != EDITORIAL_ORDER
        or visual_decision.get("native416_visual_reachability_gate") != "CLOSED"
        or visual_decision.get("native416_title_overlay_policy")
        != "separate_gameplay_effect_not_clean_story"
    ):
        raise Ac7210ExhaustiveError("ac7210 visual authority differs")

    audio_assertions = audio.get("assertions", {})
    audio_decision = audio.get("decision", {})
    if (
        audio.get("schema")
        != "magireco-ac7210-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "passed"
        or int(audio_assertions.get("total_audio_occurrences", -1)) != EXPECTED_AUDIO
        or int(audio_assertions.get("excluded_bgm_occurrences", -1)) != 0
        or int(audio_assertions.get("subtitle_cues", -1)) != EXPECTED_SUBTITLES
        or int(audio_assertions.get("presentation_frames", -1))
        != EXPECTED_PRESENTATION_FRAMES
        or audio_assertions.get("all_durable_ogg_files_exist") is not True
        or audio_assertions.get("all_components_are_se_bus") is not True
        or audio_assertions.get("all_callbacks_are_voice_bus") is not True
        or tuple(audio_decision.get("native416_story_events", [])) != STORY_EVENTS
        or tuple(audio_decision.get("editorial_order", [])) != EDITORIAL_ORDER
        or audio_decision.get("strict_no_bgm_gate") != "CLOSED_ZERO_BGM_ROWS"
        or audio_decision.get("event_global_voice_subtitle_gate") != "CLOSED"
        or audio_decision.get("event_presentation_tail_gate") != "CLOSED"
    ):
        raise Ac7210ExhaustiveError("ac7210 audio authority differs")


def resolve_routes(visual: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = list(visual.get("dirinfo_routes", []))
    if len(raw) != EXPECTED_ROUTE_ROWS:
        raise Ac7210ExhaustiveError("ac7210 route row count differs")
    routes: list[dict[str, Any]] = []
    union: set[str] = set()
    for expected_index, row in enumerate(raw):
        index = int(row.get("dirinfo_row", -1))
        ordered = tuple(str(value) for value in row.get("ordered_events", []))
        story = tuple(str(value) for value in row.get("native416_story_events", []))
        deferred = tuple(str(value) for value in row.get("lower_priority_component_events", []))
        if (
            index != expected_index
            or not ordered
            or any(event not in ALL_EVENTS for event in ordered)
            or story != tuple(event for event in ordered if event in STORY_EVENTS)
            or deferred != tuple(event for event in ordered if event in DEFERRED_EVENTS)
            or row.get("native416_story_projection_status") != "CLOSED"
        ):
            raise Ac7210ExhaustiveError(f"invalid ac7210 route row: {index}")
        union.update(ordered)
        routes.append(
            {
                "dirinfo_row": index,
                "ordered_events": list(ordered),
                "native416_story_projection": list(story),
                "deferred_component_terminal": list(deferred),
                "full_route_single_canvas_status": row["full_route_single_canvas_status"],
            }
        )
    if union != set(ALL_EVENTS):
        raise Ac7210ExhaustiveError("ac7210 route union does not cover eight events")
    return routes


def event_code_map(runtime: Mapping[str, Any]) -> dict[str, str]:
    requested = {
        str(event): str(code).casefold()
        for event, code in runtime.get("requested_events", {}).items()
    }
    if set(requested) != set(ALL_EVENTS) or any(
        not code.startswith("0x") or len(code) != 18 for code in requested.values()
    ):
        raise Ac7210ExhaustiveError("ac7210 runtime event-code set differs")
    for event, capture in runtime.get("events", {}).items():
        if str(capture.get("event_code", "")).casefold() != requested.get(str(event)):
            raise Ac7210ExhaustiveError(f"runtime event-code mismatch: {event}")
    return requested


def _story_chunks(visual: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    chunks = {str(row["name"]): row for row in visual.get("z2d_chunks", [])}
    if any(event not in chunks for event in STORY_EVENTS):
        raise Ac7210ExhaustiveError("native416 story parent chunk is missing")
    return {event: chunks[event] for event in STORY_EVENTS}


def validate_duplicate_alias(visual: Mapping[str, Any]) -> dict[str, str]:
    duplicate = visual.get("exact_story_duplicate_alias", {})
    canonical = str(duplicate.get("canonical", ""))
    alias = str(duplicate.get("alias", ""))
    if (
        canonical != "ac7210_002_c03_LP_MR.dgm"
        or alias != "ac7210_002_c03_MR.dgm"
        or duplicate.get("audience_policy")
        != "retain the canonical complete presentation once"
    ):
        raise Ac7210ExhaustiveError("ac7210 exact duplicate alias contract differs")
    layers = {
        str(row["z2d_reference"]): row
        for row in visual.get("movie_layers", [])
        if row.get("content_class") == "native416_story_visual"
    }
    left, right = Path(layers[canonical]["media_path"]), Path(layers[alias]["media_path"])
    if (
        not left.is_file()
        or not right.is_file()
        or left.stat().st_size != right.stat().st_size
        or not filecmp.cmp(left, right, shallow=False)
    ):
        raise Ac7210ExhaustiveError("ac7210 authored alias is not byte-identical")
    return {"canonical": canonical, "alias": alias}


def build_source_authority(
    visual: Mapping[str, Any], ffprobe: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    duplicate = validate_duplicate_alias(visual)
    sources: dict[str, dict[str, Any]] = {}
    authored_occurrences = 0
    for event, chunk in _story_chunks(visual).items():
        for layer in chunk.get("movie_layers", []):
            if layer.get("content_class") != "native416_story_visual":
                continue
            authored_occurrences += 1
            name = str(layer["z2d_reference"]).removesuffix(".dgm")
            if str(layer["z2d_reference"]) == duplicate["alias"]:
                continue
            if (
                layer.get("compiled_table_present") is not True
                or layer.get("runtime_load_disposition") != "LOADABLE_BY_EXACT_NAME"
                or layer.get("audience_dedup_disposition") != "CANONICAL_RETAIN_ONCE"
            ):
                raise Ac7210ExhaustiveError(f"non-canonical story layer: {event}/{name}")
            path = Path(str(layer["media_path"])).resolve()
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
                or source_frames != int(layer["frame_count"])
            ):
                raise Ac7210ExhaustiveError(f"bounded source signature differs: {name}")
            if name in sources:
                raise Ac7210ExhaustiveError(f"canonical source identity repeated: {name}")
            sources[name] = {
                "dgm_name": name,
                "event": event,
                "compiled_table_index": int(layer["compiled_table_index"]),
                "path": str(path),
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
                "width": 416,
                "height": 232,
                "frame_rate": FRAME_RATE,
                "source_frame_count": source_frames,
                "playback_frame_count": source_frames,
                "authored_start_frame": int(layer["start_frame"]),
                "authored_end_frame_inclusive": int(layer["end_frame_inclusive"]),
                "source_frame_contract": "exact_one_to_one_authored_interval",
            }
    if (
        authored_occurrences != EXPECTED_STORY_SOURCE_OCCURRENCES
        or len(sources) != EXPECTED_CANONICAL_STORY_SOURCES
    ):
        raise Ac7210ExhaustiveError("ac7210 bounded source cardinality differs")
    entries = [sources[name] for name in sorted(sources)]
    return sources, {
        "schema": "magireco-ac7210-bounded-native416-story-source-media-authority-v1",
        "status": "PASS",
        "authored_story_source_occurrences": authored_occurrences,
        "canonical_unique_story_sources": len(entries),
        "byte_identical_alias_omitted": duplicate,
        "entries": entries,
        "source_media_modified": False,
    }


def event_layer_rows(
    event: str,
    visual: Mapping[str, Any],
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    chunk = _story_chunks(visual)[event]
    layers = sorted(
        [
            row
            for row in chunk.get("movie_layers", [])
            if row.get("content_class") == "native416_story_visual"
            and row.get("audience_dedup_disposition") == "CANONICAL_RETAIN_ONCE"
        ],
        key=lambda row: int(row["start_frame"]),
    )
    rows: list[dict[str, Any]] = []
    cursor = 0
    for layer in layers:
        name = str(layer["z2d_reference"]).removesuffix(".dgm")
        source = sources.get(name)
        if source is None:
            raise Ac7210ExhaustiveError(f"canonical story source missing: {event}/{name}")
        frames = int(source["playback_frame_count"])
        rows.append(
            {
                **dict(source),
                "parent_z2d": event,
                "event_start_frame": cursor,
                "event_end_frame_exclusive": cursor + frames,
                "event_start_ms": frame_to_ms(cursor),
                "event_end_ms": frame_to_ms(cursor + frames),
                "role": "background",
            }
        )
        cursor += frames
    if not rows:
        raise Ac7210ExhaustiveError(f"event has no canonical layers: {event}")
    return rows, cursor


def _speaker_code_from_caption(name: str) -> str:
    if "_yac_" in name:
        return "yac"
    if "_tur_" in name:
        return "tur"
    return ""


def translation_rows_by_request(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = value.get("translations", [])
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        request = str(row.get("request_id", ""))
        if (
            not request
            or request in result
            or not str(row.get("ja", "")).strip()
            or not str(row.get("zh", "")).strip()
        ):
            raise Ac7210ExhaustiveError("ac7210 translation request map differs")
        result[request] = dict(row)
    if set(result) != {"3279", "3280", "3593", "3594"}:
        raise Ac7210ExhaustiveError("ac7210 translation request set differs")
    return result


def build_event_manifest(
    event: str,
    *,
    code_hex: str,
    layer_rows: Sequence[Mapping[str, Any]],
    visual_frames: int,
    presentation: Mapping[str, Any],
    audio_rows: Sequence[Mapping[str, Any]],
    subtitle_rows: Sequence[Mapping[str, Any]],
    translations: Mapping[str, Mapping[str, Any]],
    visual_authority_path: Path,
    audio_authority_path: Path,
) -> dict[str, Any]:
    retained = [dict(row) for row in audio_rows if row["event"] == event]
    if any(
        row.get("volume_bus") == "BGM"
        or row.get("strict_no_bgm_disposition") == "EXCLUDE_AS_BGM_BUS"
        for row in retained
    ):
        raise Ac7210ExhaustiveError(f"BGM leaked into retained audio: {event}")
    event_subtitles = [dict(row) for row in subtitle_rows if row["event"] == event]
    presentation_frames = int(presentation["presentation_frames"])
    if (
        int(presentation["video_content_frames"]) != visual_frames
        or presentation_frames < visual_frames
        or int(presentation["tail_hold_frames"]) != presentation_frames - visual_frames
    ):
        raise Ac7210ExhaustiveError(f"event presentation contract differs: {event}")
    video_content_ms = frame_to_ms(visual_frames)
    content_end_ms = max(
        video_content_ms,
        max(
            (int(row["start_ms"]) + int(row["duration_ms"]) for row in retained),
            default=0,
        ),
        max((int(row["end_ms"]) for row in event_subtitles), default=0),
    )
    quantization = quantize_duration_to_frame_grid(content_end_ms, FRAME_RATE)
    if int(quantization["frame_count"]) != presentation_frames:
        raise Ac7210ExhaustiveError(f"event frame-grid closure differs: {event}")

    ordered_layers = sorted(layer_rows, key=lambda row: int(row["event_start_frame"]))
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
            "interval_confidence": "exact_z2d_movielayer_interval_canonical_alias_dedup",
            "source_frame_contract": row["source_frame_contract"],
        }
        for order, row in enumerate(ordered_layers)
    ]
    composition_clips = [
        {
            "dgm_name": row["dgm_name"],
            "role": "background",
            "start_ms": int(row["event_start_ms"]),
        }
        for row in ordered_layers
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
                    "timing_scope": "event_global_exact_parent_scene_and_child_callback",
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
        translation = translations.get(request_id)
        if voice is None or translation is None:
            raise Ac7210ExhaustiveError(f"subtitle has no voice/translation: {event}")
        subtitles.append(
            {
                "text": str(translation["ja"]),
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
                "timing_scope": "event_global_exact_parent_scene_and_child_callback",
                "timing_override_source": str(audio_authority_path.resolve()),
                "speaker_identity_evidence": "official_caption_resource_and_speaker_registry",
            }
        )

    voice_count = len(voice_by_request)
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
        "render_frame_count": presentation_frames,
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
            "evidence": "exact Z2D MovieLayer intervals with canonical alias dedup",
            "clips": composition_clips,
        },
        "composition_plan_source": str(visual_authority_path.resolve()),
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
            "verified_subtitle_voice_count": len(subtitles),
            "graphical_display_subtitle_count": 0,
            "official_voice_label_subtitle_count": len(subtitles),
            "asr_verified_subtitle_count": 0,
            "reviewed_subtitle_baseline_applied": False,
            "reviewed_subtitle_current_only_voice_candidate_count": 0,
            "reviewed_subtitle_current_only_graphical_candidate_count": 0,
            "exact_z2d_req_sound_count": voice_count,
            "event_global_z2d_timing_ready": True,
            "linear_video_timeline": False,
            "video_composition_model": "timed_full_frame_layers",
            "composition_resolved": True,
            "composition_evidence": "ac7210 exact Z2D/runtime parent authority",
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
            "excluded_occurrences": [],
            "evidence_path": str(audio_authority_path.resolve()),
        },
        "ac7210_generated_manifest_provenance": {
            "visual_authority": str(visual_authority_path.resolve()),
            "audio_authority": str(audio_authority_path.resolve()),
            "parent_z2d": event,
            "canonical_layer_count": len(clips),
            "retained_audio_occurrence_count": len(retained),
            "subtitle_cue_count": len(subtitles),
            "presentation_frames": presentation_frames,
            "tail_hold_frames": presentation_frames - visual_frames,
            "source_media_modified": False,
        },
    }


def renderer_translation_map(
    translations: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    unique: list[dict[str, str]] = []
    by_ja: dict[str, str] = {}
    for request in ("3279", "3280", "3594", "3593"):
        ja = str(translations[request]["ja"])
        zh = str(translations[request]["zh"])
        prior = by_ja.setdefault(ja, zh)
        if prior != zh:
            raise Ac7210ExhaustiveError(
                f"one Japanese cue has conflicting Chinese translations: {ja!r}"
            )
        if prior == zh and any(row["ja"] == ja for row in unique):
            continue
        unique.append(
            {"ja": ja, "zh": zh, "status": "machine_draft_pending_owner"}
        )
    return {
        "schema": "magireco-reviewed-story-zh-dialogue-map-v1",
        "scope": "ac7210_exhaustive_native416_runtime_bound_dialogue",
        "status": "new_longform_human_playback_required",
        "translations": unique,
        "approval_boundary": (
            "text is reused from exact owner-reviewed routes; the new deduplicated "
            "longform and timing remain HUMAN_PLAYBACK_REQUIRED"
        ),
    }


def build_inputs(args: argparse.Namespace) -> dict[str, Path]:
    output_root = args.output_input_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"immutable input checkpoint already exists: {output_root}")
    visual = read_json(args.visual_authority)
    audio = read_json(args.audio_authority)
    runtime = read_json(args.runtime_scene_motion)
    translation_source = read_json(args.translation_map)
    validate_authorities(visual, audio)
    routes = resolve_routes(visual)
    codes = event_code_map(runtime)
    translations = translation_rows_by_request(translation_source)
    sources, source_report = build_source_authority(visual, args.ffprobe)
    presentations = {
        str(row["event"]): row for row in audio.get("event_presentations", [])
    }
    if set(presentations) != set(STORY_EVENTS):
        raise Ac7210ExhaustiveError("ac7210 event presentation set differs")

    staging = output_root.parent / f".{output_root.name}.staging-{os.getpid()}"
    if staging.exists():
        raise FileExistsError(f"staging checkpoint already exists: {staging}")
    try:
        events_root = staging / "events"
        events_root.mkdir(parents=True)
        manifests: dict[str, dict[str, Any]] = {}
        canonical_occurrences = 0
        for event in STORY_EVENTS:
            layer_rows, visual_frames = event_layer_rows(event, visual, sources)
            canonical_occurrences += len(layer_rows)
            manifest = build_event_manifest(
                event,
                code_hex=codes[event],
                layer_rows=layer_rows,
                visual_frames=visual_frames,
                presentation=presentations[event],
                audio_rows=audio["audio_rows"],
                subtitle_rows=audio["subtitle_cues"],
                translations=translations,
                visual_authority_path=args.visual_authority,
                audio_authority_path=args.audio_authority,
            )
            write_json(events_root / f"{event}.json", manifest)
            manifests[event] = manifest
        if (
            canonical_occurrences != EXPECTED_CANONICAL_STORY_SOURCES
            or sum(len(row["audio"]) for row in manifests.values()) != EXPECTED_AUDIO
            or sum(len(row["subtitles"]) for row in manifests.values())
            != EXPECTED_SUBTITLES
            or sum(int(row["render_frame_count"]) for row in manifests.values())
            != EXPECTED_PRESENTATION_FRAMES
        ):
            raise Ac7210ExhaustiveError("ac7210 event manifest cardinality differs")
        seen: dict[str, str] = {}
        for event in EDITORIAL_ORDER:
            projection = presentation_projection(manifests[event])
            if projection in seen:
                raise Ac7210ExhaustiveError(
                    f"complete AV presentation duplicated: {event}/{seen[projection]}"
                )
            seen[projection] = event

        source_series = {
            "schema": "magireco-series-editions-v1",
            "series": "ac7210",
            "status": "passed",
            "event_count": len(STORY_EVENTS),
            "family_state": {"ready_event_names": list(EDITORIAL_ORDER)},
            "product_scopes": {event: PRODUCT_SCOPE for event in EDITORIAL_ORDER},
            "natural_session_claims": {event: False for event in EDITORIAL_ORDER},
            "ordering_evidence": (
                "five exact DirInfo rows; native416 story union 001..005; native512 "
                "component terminals 006..008 remain separately indexed"
            ),
            "fixed_native_session_gap_claimed": False,
        }
        source_series_path = staging / "source_series_catalogs" / "ac7210_exhaustive_native416.json"
        write_json(source_series_path, source_series)

        series = {
            "schema": "magireco-ac7210-exhaustive-native416-editorial-series-v1",
            "series": "ac7210_exhaustive_native416",
            "status": "passed",
            "event_count": len(STORY_EVENTS),
            "title_zh": "八千代与鹤乃火箭突击 全分支·全结果完整合集",
            "event_sequence": list(EDITORIAL_ORDER),
            "ordering": "shared entry, normal approach, CU approach, shared attack, failure",
            "product_scope": PRODUCT_SCOPE,
            "natural_session_claimed": False,
            "loop_scope": {
                "status": "every code-reachable distinct native416 story source presentation once",
                "fixed_inter_node_gap": False,
                "mutually_exclusive_routes_combined": True,
                "byte_identical_authored_alias_omitted": True,
            },
            "family_state": {
                "production_manifest_root": str(output_root),
                "known_family_events": len(ALL_EVENTS),
                "ready_family_events": len(STORY_EVENTS),
                "not_ready_family_events": list(DEFERRED_EVENTS),
                "ready_event_names": list(EDITORIAL_ORDER),
            },
            "event_manifest_sha256": {
                event: file_sha256(events_root / f"{event}.json")
                for event in EDITORIAL_ORDER
            },
            "source_series_manifest": {
                "path": str((output_root / source_series_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(source_series_path),
                "evidence": "code-level five-row/eight-event route and MovieLayer authority",
            },
            "human_playback_required": True,
            "publication_approved": False,
        }
        series_path = staging / "series_proposals" / "ac7210_exhaustive_native416.json"
        write_json(series_path, series)
        rendered_translation = renderer_translation_map(translations)
        translation_path = staging / "translations" / "ac7210_exhaustive_native416_zh_v1.json"
        write_json(translation_path, rendered_translation)
        source_report_path = staging / "BOUNDED_SOURCE_MEDIA_AUTHORITY.json"
        write_json(source_report_path, source_report)

        authority = {
            "schema": "magireco-ac7210-exhaustive-native416-editorial-order-authority-v1",
            "status": "PASS_READY_FOR_STORY_RENDER",
            "family": "ac7210",
            "native_dimensions": dict(NATIVE_DIMENSIONS),
            "frame_rate": FRAME_RATE,
            "route_universe": {
                "route_row_count": len(routes),
                "routes": routes,
                "native416_story_event_union": list(STORY_EVENTS),
                "deferred_512_component_event_union": list(DEFERRED_EVENTS),
            },
            "story_presentation_universe": {
                "authored_story_source_occurrences": EXPECTED_STORY_SOURCE_OCCURRENCES,
                "canonical_unique_story_sources": EXPECTED_CANONICAL_STORY_SOURCES,
                "byte_identical_alias_omitted_count": 1,
                "complete_av_presentation_count": len(STORY_EVENTS),
                "unique_complete_av_presentation_count": len(seen),
                "ordered_events": list(EDITORIAL_ORDER),
                "each_complete_av_presentation_once": True,
                "presentation_frames": EXPECTED_PRESENTATION_FRAMES,
                "dedupe_unit": "official source presentation plus exact audio and subtitle timing",
            },
            "separated_boundaries": {
                "presentation_title_overlay": "separate_gameplay_effect_not_clean_story",
                "native208_dark_overlay": "separate_material_or_effect_not_clean_story",
                "native512_component_events": list(DEFERRED_EVENTS),
                "native512_status": "RECORDED_DEFERRED_BELOW_NATIVE416_PRIORITY",
            },
            "closed_gates": {
                "story_visual_universe": "CLOSED_5_EVENTS_14_AUTHORED_13_CANONICAL",
                "event_audio_and_strict_no_bgm": "CLOSED_10_RETAINED_ZERO_BGM",
                "child_local_timing": "CLOSED_FOR_ALL_4_STORY_VOICES",
                "duplicate_free_editorial_order": "CLOSED_5_OF_5_UNIQUE_COMPLETE_AV",
            },
            "decision": {
                "old_two_route_fragments_are_final_products": False,
                "new_exhaustive_native416_story_render_allowed": True,
                "deferred_512_component_render_allowed": False,
                "human_playback_required": True,
            },
            "source_media_modified": False,
        }
        authority_path = staging / "AC7210_EXHAUSTIVE_NATIVE416_EDITORIAL_AUTHORITY.json"
        write_json(authority_path, authority)
        bindings = {
            "schema": "magireco-ac7210-exhaustive-native416-input-bindings-v1",
            "status": "PASS",
            "bindings": [
                _snapshot(path)
                for path in (
                    args.visual_authority,
                    args.audio_authority,
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
            "schema": "magireco-ac7210-exhaustive-native416-input-verification-v1",
            "status": "PASS_READY_FOR_STORY_RENDER",
            "checks": {
                "dirinfo_route_rows": EXPECTED_ROUTE_ROWS,
                "known_family_events": len(ALL_EVENTS),
                "native416_story_events": len(STORY_EVENTS),
                "deferred_512_component_events": len(DEFERRED_EVENTS),
                "authored_story_source_occurrences": EXPECTED_STORY_SOURCE_OCCURRENCES,
                "canonical_unique_story_sources": EXPECTED_CANONICAL_STORY_SOURCES,
                "byte_identical_alias_omitted_count": 1,
                "retained_no_bgm_audio_occurrences": EXPECTED_AUDIO,
                "excluded_bgm_occurrences": 0,
                "subtitle_cues": EXPECTED_SUBTITLES,
                "child_local_only_timing_occurrences": 0,
                "presentation_frames": EXPECTED_PRESENTATION_FRAMES,
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
            "# ac7210 exhaustive native416 story longform inputs\n\n"
            "Five DirInfo rows and all eight event identities remain indexed. The clean "
            "story product contains events 001..005 in duplicate-free editorial order. "
            "Events 006..008 and presentation/effect overlays remain separated and deferred.\n",
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
        "series_path": output_root / "series_proposals" / "ac7210_exhaustive_native416.json",
        "translation_path": output_root / "translations" / "ac7210_exhaustive_native416_zh_v1.json",
    }


def load_existing_inputs(output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    verification = read_json(output_root / "VERIFICATION_RECORD.json")
    authority = read_json(output_root / "AC7210_EXHAUSTIVE_NATIVE416_EDITORIAL_AUTHORITY.json")
    series_path = output_root / "series_proposals" / "ac7210_exhaustive_native416.json"
    translation_path = output_root / "translations" / "ac7210_exhaustive_native416_zh_v1.json"
    series = read_json(series_path)
    if (
        verification.get("status") != "PASS_READY_FOR_STORY_RENDER"
        or verification.get("checks", {}).get("presentation_frames")
        != EXPECTED_PRESENTATION_FRAMES
        or authority.get("decision", {}).get("new_exhaustive_native416_story_render_allowed")
        is not True
        or authority.get("decision", {}).get("deferred_512_component_render_allowed")
        is not False
        or series.get("event_sequence") != list(EDITORIAL_ORDER)
    ):
        raise Ac7210ExhaustiveError("existing ac7210 input checkpoint differs")
    return {
        "output_root": output_root,
        "series_path": series_path,
        "translation_path": translation_path,
    }


def verify_production(production_root: Path, ffprobe: str) -> dict[str, Any]:
    family = production_root / "ac7210_exhaustive_native416_full_no_bgm_editions_v1"
    manifest = read_json(family / "manifests" / "family_editions_manifest.json")
    qa = read_json(family / "qa" / "automated_qa.json")
    if (
        manifest.get("ordered_events") != list(EDITORIAL_ORDER)
        or manifest.get("audio_profile") != "no_bgm"
        or any(event in manifest.get("ordered_events", []) for event in DEFERRED_EVENTS)
        or qa.get("checks", {}).get("no_exact_duplicate_audience_events") is not True
        or qa.get("status") not in {"passed", "AUTOMATED_QA_PASSED"}
    ):
        raise Ac7210ExhaustiveError("produced ac7210 family manifest/QA differs")
    media: list[dict[str, Any]] = []
    for edition in ("none", "ja", "zh"):
        path = family / "video" / f"ac7210_exhaustive_native416_full_no_bgm_editions_v1__{edition}.mp4"
        probe = _probe_video(path, ffprobe)
        videos = [row for row in probe["streams"] if row["codec_type"] == "video"]
        audios = [row for row in probe["streams"] if row["codec_type"] == "audio"]
        if (
            len(videos) != 1
            or len(audios) != 1
            or videos[0].get("codec_name") != "h264"
            or (int(videos[0].get("width", 0)), int(videos[0].get("height", 0)))
            != (416, 232)
            or videos[0].get("r_frame_rate") != FRAME_RATE
            or int(videos[0].get("nb_read_frames", 0)) != EXPECTED_PRESENTATION_FRAMES
            or audios[0].get("codec_name") != "aac"
            or int(audios[0].get("sample_rate", 0)) != 48000
            or int(audios[0].get("channels", 0)) != 2
        ):
            raise Ac7210ExhaustiveError(f"media signature differs: {path}")
        media.append(
            {
                "edition": edition,
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
                "duration_seconds": float(probe["format"]["duration"]),
                "frame_count": int(videos[0]["nb_read_frames"]),
                "width": 416,
                "height": 232,
                "frame_rate": FRAME_RATE,
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": 48000,
                "audio_channels": 2,
            }
        )
    if max(row["duration_seconds"] for row in media) - min(
        row["duration_seconds"] for row in media
    ) > 0.001:
        raise Ac7210ExhaustiveError("ac7210 edition durations differ")
    report = {
        "schema": "magireco-ac7210-exhaustive-native416-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "ordered_complete_event_presentations": len(STORY_EVENTS),
        "authored_story_source_occurrences": EXPECTED_STORY_SOURCE_OCCURRENCES,
        "canonical_unique_story_sources": EXPECTED_CANONICAL_STORY_SOURCES,
        "byte_identical_alias_omitted_count": 1,
        "exact_duplicate_complete_presentation_count": 0,
        "dirinfo_route_coverage": "5/5",
        "deferred_512_component_events": list(DEFERRED_EVENTS),
        "deferred_512_story_leak_count": 0,
        "presentation_overlay_story_leak_count": 0,
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
        f"ac7210_exhaustive_native416={inputs['series_path']}",
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
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--audio-authority", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--translation-map", required=True, type=Path)
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
            "PASS routes=5 events=8 native416_story=5 authored_sources=14 "
            "canonical_sources=13 alias_omitted=1 audio=10 subtitles=4 "
            f"frames=1354 inputs={inputs['output_root']}"
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
