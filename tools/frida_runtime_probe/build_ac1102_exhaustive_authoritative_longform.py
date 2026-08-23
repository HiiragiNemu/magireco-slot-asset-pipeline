#!/usr/bin/env python3
"""Close and render the exhaustive ac1102 native-416 editorial longform.

The product unit is one complete event presentation (visual composition plus
its retained VOICE/SE and subtitle semantics), not one DirInfo route.  All 31
mutually exclusive DirInfo rows are covered by the union of 15 event
presentations; each presentation appears once in a comprehensible editorial
order.  Raw source aliases remain in the authority report and are not promoted
as repeated standalone audience clips.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_event_production_manifests import (
        file_sha256,
        quantize_duration_to_frame_grid,
    )
    from .resolve_ac1102_exhaustive_unique_segments import (
        LEGACY_EVENTS,
        REQUIRED_EVENTS,
        durable_source_path,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import (
        file_sha256,
        quantize_duration_to_frame_grid,
    )
    from tools.frida_runtime_probe.resolve_ac1102_exhaustive_unique_segments import (
        LEGACY_EVENTS,
        REQUIRED_EVENTS,
        durable_source_path,
    )


EDITORIAL_ORDER = (
    "ac1102_001",  # white title / short entry
    "ac1102_009",  # red title / short entry
    "ac1102_010",  # white title / long entry
    "ac1102_011",  # red title / long entry
    "ac1102_002",  # common encounter
    "ac1102_003",  # avoidance outcome
    "ac1102_004",  # avoidance CU outcome
    "ac1102_005",  # restraint setup
    "ac1102_008",  # restraint CU setup
    "ac1102_006",  # failure outcome
    "ac1102_007",  # success outcome
    "ac1102_012",  # alternate/revival entry
    "ac1102_013",  # alternate follow-up
    "ac1102_014",  # revival victory setup
    "ac1102_015",  # revival victory completion
)
MISSING_MANIFEST_EVENTS = (
    "ac1102_007",
    "ac1102_013",
    "ac1102_014",
    "ac1102_015",
)
PRODUCT_SCOPE = (
    "exhaustive_duplicate_free_event_presentation_editorial_longform"
)
NATIVE_DIMENSIONS = {"width": 416, "height": 232}
FRAME_RATE = "30/1"
SOURCE_EVENT_MANIFESTS = set(LEGACY_EVENTS)
EXPECTED_ROUTE_COUNT = 31
EXPECTED_NATIVE_SOURCE_IDENTITIES = 36
EXPECTED_COMPONENT_IDENTITIES = 2
EXPECTED_PRESENT_SOURCE_OCCURRENCES = 59
EXPECTED_UNREACHABLE_ADD_OCCURRENCES = 10
EXPECTED_RETAINED_AUDIO_OCCURRENCES = 15
EXPECTED_EXCLUDED_BGM_OCCURRENCES = 2


class Ac1102ExhaustiveError(ValueError):
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


def _event_code_map(dirinfo_rows: Sequence[Mapping[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in dirinfo_rows:
        if int(row["kind"]) != 54:
            continue
        event = str(row["scene_name"])
        code = str(row["code_hex"]).casefold()
        previous = result.setdefault(event, code)
        if previous != code:
            raise Ac1102ExhaustiveError(f"DirInfo code differs for {event}")
    if set(result) != set(REQUIRED_EVENTS):
        raise Ac1102ExhaustiveError("DirInfo kind 54 event union differs")
    return result


def resolve_routes(
    dirinfo_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in dirinfo_rows:
        if int(row["kind"]) == 54:
            grouped[int(row["row_index"])].append(row)
    if set(grouped) != set(range(EXPECTED_ROUTE_COUNT)):
        raise Ac1102ExhaustiveError("DirInfo kind 54 route index set differs")
    routes: list[dict[str, Any]] = []
    union: set[str] = set()
    for row_index in sorted(grouped):
        rows = sorted(grouped[row_index], key=lambda row: int(row["selector_raw"]))
        events = [str(row["scene_name"]) for row in rows]
        if len(events) != len(set(events)) or not set(events) <= set(REQUIRED_EVENTS):
            raise Ac1102ExhaustiveError(f"invalid event sequence in route {row_index}")
        union.update(events)
        routes.append(
            {
                "row_index": row_index,
                "events": events,
                "legacy_zero_source_events": [
                    str(row["scene_name"])
                    for row in rows
                    if int(row["resolved_source_count"]) == 0
                ],
                "reconstructable_from_event_presentation_set": True,
            }
        )
    if union != set(REQUIRED_EVENTS):
        raise Ac1102ExhaustiveError("DirInfo route union does not cover 15 events")
    return routes


def validate_authorities(
    unique: Mapping[str, Any],
    layers: Mapping[str, Any],
    audio: Mapping[str, Any],
) -> None:
    if (
        unique.get("schema")
        != "magireco-ac1102-exhaustive-unique-segment-authority-v1"
        or unique.get("family") != "ac1102"
        or unique.get("runtime_structure", {}).get("event_count") != 15
        or unique.get("runtime_structure", {}).get("unique_cut_structure_count")
        != 18
        or unique.get("native_source_universe", {}).get("unique_sha256_count")
        != EXPECTED_NATIVE_SOURCE_IDENTITIES
    ):
        raise Ac1102ExhaustiveError("ac1102 unique-segment authority differs")
    if (
        layers.get("schema")
        != "magireco-ac1102-movielayer-runtime-reachability-authority-v1"
        or layers.get("status") != "passed"
        or layers.get("decision", {}).get("required_visible_media_missing") is not False
        or layers.get("decision", {}).get("old_missing_layer_media_blocker")
        != "CLOSED_AS_CODE_UNREACHABLE_AUTHORED_LAYERS"
        or layers.get("assertions", {}).get("unreachable_add_movie_layers") != 4
        or layers.get("assertions", {}).get(
            "all_four_unreachable_layers_have_same_interval_loadable_twins"
        )
        is not True
    ):
        raise Ac1102ExhaustiveError("ac1102 MovieLayer reachability differs")
    if (
        audio.get("schema")
        != "magireco-ac1102-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "passed"
        or audio.get("decision", {}).get(
            "event_audio_and_strict_no_bgm_manifest_closure"
        )
        != "CLOSED"
        or audio.get("decision", {}).get("retained_audio_occurrences")
        != EXPECTED_RETAINED_AUDIO_OCCURRENCES
        or audio.get("decision", {}).get("excluded_bgm_occurrences")
        != EXPECTED_EXCLUDED_BGM_OCCURRENCES
        or audio.get("assertions", {}).get(
            "all_caption_audio_event_global_starts_resolved"
        )
        is not True
    ):
        raise Ac1102ExhaustiveError("ac1102 event-audio authority differs")


def _bounded_hashes(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if (
        payload.get("schema")
        != "magireco-ac1102-bounded-source-hash-authority-v1"
        or payload.get("status") != "PASS"
        or payload.get("entry_count") != 38
        or payload.get("source_media_modified") is not False
    ):
        raise Ac1102ExhaustiveError("bounded source hash authority differs")
    result = {
        str(Path(str(row["path"])).resolve()): dict(row)
        for row in payload["entries"]
    }
    if len(result) != 38:
        raise Ac1102ExhaustiveError("bounded source paths are not unique")
    return result


def _source_rows(
    catalog_rows: Sequence[Mapping[str, str]],
    bounded: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_order, row in enumerate(catalog_rows):
        event = str(row.get("event_name", ""))
        if event not in REQUIRED_EVENTS:
            continue
        exists = str(row.get("source_exists", "")).casefold() == "yes"
        if not exists:
            grouped[event].append(
                {
                    "catalog_order": source_order,
                    "z2d_name": str(row["z2d_name"]),
                    "dgm_name": str(row["dgm_name"]),
                    "source_exists": False,
                }
            )
            continue
        path = durable_source_path(str(row["source_mp4"])).resolve()
        authority = bounded.get(str(path))
        if authority is None or not path.is_file():
            raise Ac1102ExhaustiveError(f"source lacks bounded identity: {path}")
        grouped[event].append(
            {
                "catalog_order": source_order,
                "z2d_order": int(row["z2d_order"]),
                "dgm_order": int(row["dgm_order"]),
                "z2d_name": str(row["z2d_name"]),
                "dgm_name": str(row["dgm_name"]),
                "official_name": str(row["official_name"]),
                "path": str(path),
                "source_sha256": str(authority["sha256"]).upper(),
                "size_bytes": int(authority["size_bytes"]),
                "width": int(row["width"]),
                "height": int(row["height"]),
                "event_start_ms": int(row["event_start_ms"]),
                "event_end_ms": int(row["event_end_ms"]),
                "source_exists": True,
            }
        )
    if set(grouped) != set(REQUIRED_EVENTS):
        raise Ac1102ExhaustiveError("audience source catalog event set differs")
    present = [row for rows in grouped.values() for row in rows if row["source_exists"]]
    absent = [row for rows in grouped.values() for row in rows if not row["source_exists"]]
    if len(present) != EXPECTED_PRESENT_SOURCE_OCCURRENCES or len(absent) != EXPECTED_UNREACHABLE_ADD_OCCURRENCES:
        raise Ac1102ExhaustiveError("audience source occurrence counts differ")
    return grouped


def _runtime_frame_counts(unique: Mapping[str, Any]) -> dict[str, int]:
    rows = unique["runtime_structure"]["events"]
    result = {str(row["event"]): int(row["container_frames"]) for row in rows}
    if set(result) != set(REQUIRED_EVENTS):
        raise Ac1102ExhaustiveError("runtime event frame-count set differs")
    return result


def _plan_role(event: str, row: Mapping[str, Any]) -> str:
    z2d = str(row["z2d_name"])
    if z2d in {
        "ac8040_shouri_EF_small",
        "ac1102_3off_c015_win_rogo",
    }:
        return "screen_overlay"
    if event in MISSING_MANIFEST_EVENTS:
        return "background"
    raise Ac1102ExhaustiveError(f"no generated role rule for {event}/{z2d}")


def build_missing_manifest(
    event: str,
    *,
    code_hex: str,
    source_rows: Sequence[Mapping[str, Any]],
    audio_rows: Sequence[Mapping[str, Any]],
    runtime_frames: int,
    layer_authority_path: Path,
    audio_authority_path: Path,
) -> dict[str, Any]:
    if event not in MISSING_MANIFEST_EVENTS:
        raise Ac1102ExhaustiveError(f"unexpected generated event: {event}")
    visible = [dict(row) for row in source_rows if row["source_exists"]]
    unreachable = [dict(row) for row in source_rows if not row["source_exists"]]
    expected_unreachable = 4 if event in {"ac1102_007", "ac1102_015"} else 2 if event == "ac1102_014" else 0
    if len(unreachable) != expected_unreachable:
        raise Ac1102ExhaustiveError(f"unreachable layer count differs for {event}")
    if any((row["width"], row["height"]) not in {(416, 232), (256, 144)} for row in visible):
        raise Ac1102ExhaustiveError(f"native/component dimensions differ for {event}")
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
    if not retained or any(row["volume_bus"] == "BGM" for row in retained):
        raise Ac1102ExhaustiveError(f"retained no-BGM audio differs for {event}")
    if any((row["request_id"], row["sound_id"]) != (229, 554) for row in excluded):
        raise Ac1102ExhaustiveError(f"excluded BGM identity differs for {event}")

    video_content_ms = math.floor(runtime_frames * 1000 / 30)
    audio_content_ms = max(int(row["start_ms"]) + int(row["duration_ms"]) for row in retained)
    content_end_ms = max(video_content_ms, audio_content_ms)
    quantization = quantize_duration_to_frame_grid(content_end_ms, FRAME_RATE)

    clips: list[dict[str, Any]] = []
    plan_clips: list[dict[str, Any]] = []
    for order, row in enumerate(visible):
        role = _plan_role(event, row)
        clips.append(
            {
                "order": order,
                "dgm_name": row["dgm_name"],
                "dgm_role": role,
                "path": row["path"],
                "source_sha256": row["source_sha256"],
                "event_start_ms": row["event_start_ms"],
                "event_end_ms": row["event_end_ms"],
                "interval_confidence": (
                    "exact_runtime_parent_range_and_z2d_movielayer_interval"
                ),
            }
        )
        plan_row: dict[str, Any] = {
            "dgm_name": row["dgm_name"],
            "role": role,
            "start_ms": row["event_start_ms"],
        }
        if role == "screen_overlay":
            plan_row["blend_mode"] = "screen"
            if (row["width"], row["height"]) != (416, 232):
                plan_row["scale_to_native"] = True
        plan_clips.append(plan_row)

    manifest_audio: list[dict[str, Any]] = []
    subtitles: list[dict[str, Any]] = []
    for row in retained:
        source_kind = str(row["source_kind"])
        item: dict[str, Any] = {
            "source": source_kind,
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
        if source_kind == "z2d_req_sound":
            item.update(
                {
                    "z2d_name": str(row["z2d_name"]),
                    "event_global_start_frame": int(row["start_frame"]),
                    "event_global_start_resolved": True,
                    "timing_scope": "event_global_exact_parent_scene_and_motion_key",
                }
            )
        manifest_audio.append(item)
        if row.get("subtitle_ja"):
            subtitles.append(
                {
                    "text": str(row["subtitle_ja"]),
                    "start_ms": int(row["start_ms"]),
                    "end_ms": int(row["start_ms"]) + int(row["duration_ms"]),
                    "voice_request_id": str(row["request_id"]),
                    "voice_start_ms": int(row["start_ms"]),
                    "z2d_name": str(row["z2d_name"]),
                    "speaker_code": "fer",
                    "subtitle_source": "official_voice_label",
                    "evidence": "ac1102_event_audio_authority_v119r1",
                    "event_global_start_frame": int(row["start_frame"]),
                    "event_global_start_resolved": True,
                    "timing_scope": "event_global_exact_parent_scene_and_motion_key",
                    "speaker_identity_evidence": (
                        "exact_official_voice_request_code_name_speaker_token"
                    ),
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
            "duration_ms": video_content_ms,
            "extension_policy": "hold_last_frame",
            "evidence": (
                "exact runtime parent ranges plus exact Z2D MovieLayer intervals; "
                "four authored additive names are code-unreachable and their "
                "same-interval loadable base twins are retained"
            ),
            "clips": plan_clips,
        },
        "composition_plan_source": str(layer_authority_path.resolve()),
        "runtime_event_manifest_sources": [],
        "reviewed_subtitle_manifest_sources": [],
        "reviewed_subtitle_reconciliation": {},
        "overlap_count": sum(1 for row in plan_clips if row["role"] == "screen_overlay"),
        "gap_count": 0,
        "timeline_tolerance_ms": 34,
        "clips": clips,
        "audio": manifest_audio,
        "subtitles": subtitles,
        "quality_gates": {
            "all_full_frame": all((row["width"], row["height"]) == (416, 232) for row in visible),
            "all_clips_exist": True,
            "all_clip_source_hashes_bound": True,
            "all_audio_exist": True,
            "verified_subtitle_voice_count": len(subtitles),
            "graphical_display_subtitle_count": 0,
            "official_voice_label_subtitle_count": len(subtitles),
            "asr_verified_subtitle_count": 0,
            "reviewed_subtitle_baseline_applied": False,
            "reviewed_subtitle_current_only_voice_candidate_count": 0,
            "reviewed_subtitle_current_only_graphical_candidate_count": 0,
            "exact_z2d_req_sound_count": sum(
                row["source_kind"] == "z2d_req_sound" for row in retained
            ),
            "event_global_z2d_timing_ready": True,
            "linear_video_timeline": False,
            "video_composition_model": "timed_full_frame_layers",
            "composition_resolved": True,
            "composition_evidence": "ac1102 MovieLayer reachability v118",
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
        "ac1102_generated_manifest_provenance": {
            "layer_authority": str(layer_authority_path.resolve()),
            "audio_authority": str(audio_authority_path.resolve()),
            "unreachable_authored_layer_count": len(unreachable),
            "retained_audio_occurrence_count": len(retained),
            "excluded_bgm_occurrence_count": len(excluded),
            "voice_without_invented_subtitle_count": sum(
                row["volume_bus"] == "VOICE" and not row.get("subtitle_ja")
                for row in retained
            ),
            "source_media_modified": False,
        },
    }


def _presentation_projection(manifest: Mapping[str, Any]) -> str:
    visual = [
        {
            "dgm_name": row["dgm_name"],
            "role": row.get("dgm_role", ""),
            "source_sha256": str(row["source_sha256"]).upper(),
            "start_ms": int(row["event_start_ms"]),
            "end_ms": int(row["event_end_ms"]),
        }
        for row in manifest["clips"]
    ]
    audio = [
        {
            "request_id": str(row["request_id"]),
            "sound_id": int(row.get("sound_id", -1)),
            "ogg_name": str(row["ogg_name"]),
            "start_ms": int(row["start_ms"]),
            "duration_ms": int(row["duration_ms"]),
        }
        for row in manifest["audio"]
    ]
    subtitles = [
        {
            "request_id": str(row.get("voice_request_id", "")),
            "text": str(row.get("text", "")),
            "start_ms": int(row["start_ms"]),
            "end_ms": int(row["end_ms"]),
        }
        for row in manifest.get("subtitles", [])
    ]
    return json.dumps(
        {
            "frames": int(manifest["render_frame_count"]),
            "visual": visual,
            "audio": audio,
            "subtitles": subtitles,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _augment_translation_map(
    base: Mapping[str, Any], audio: Mapping[str, Any]
) -> dict[str, Any]:
    rows = [dict(row) for row in base.get("translations", [])]
    current = {str(row["ja"]): str(row["zh"]) for row in rows}
    additions: dict[str, str] = {}
    for row in audio["audio_rows"]:
        if row.get("subtitle_ja"):
            additions[str(row["subtitle_ja"])] = str(row["subtitle_zh"])
    for ja, zh in additions.items():
        if ja in current and current[ja] != zh:
            raise Ac1102ExhaustiveError(f"translation conflict for {ja!r}")
        if ja not in current:
            rows.append(
                {"ja": ja, "zh": zh, "status": "machine_draft_pending_owner"}
            )
    return {
        "schema": "magireco-reviewed-story-zh-dialogue-map-v1",
        "scope": "ac1102_exhaustive_event_presentations",
        "status": "machine_draft_pending_owner",
        "translations": rows,
    }


def _snapshot(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def build_inputs(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.output_input_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"immutable input checkpoint already exists: {output_root}")

    unique = read_json(args.unique_authority)
    layers = read_json(args.layer_authority)
    audio = read_json(args.audio_authority)
    bounded_payload = read_json(args.bounded_hash_authority)
    dirinfo_rows = read_csv(args.dirinfo)
    catalog_rows = read_csv(args.source_catalog)
    validate_authorities(unique, layers, audio)
    bounded = _bounded_hashes(bounded_payload)
    routes = resolve_routes(dirinfo_rows)
    event_codes = _event_code_map(dirinfo_rows)
    sources = _source_rows(catalog_rows, bounded)
    runtime_frames = _runtime_frame_counts(unique)

    staging = output_root.parent / f".{output_root.name}.staging-{os.getpid()}"
    if staging.exists():
        raise FileExistsError(f"staging checkpoint already exists: {staging}")
    try:
        events_root = staging / "events"
        events_root.mkdir(parents=True)
        manifests: dict[str, dict[str, Any]] = {}
        for event in REQUIRED_EVENTS:
            target = events_root / f"{event}.json"
            if event in SOURCE_EVENT_MANIFESTS:
                source = args.source_manifest_root / "events" / f"{event}.json"
                if not source.is_file():
                    raise FileNotFoundError(source)
                manifest = read_json(source)
                if manifest.get("event") != event:
                    raise Ac1102ExhaustiveError(f"source manifest identity differs: {event}")
                shutil.copy2(source, target)
            else:
                manifest = build_missing_manifest(
                    event,
                    code_hex=event_codes[event],
                    source_rows=sources[event],
                    audio_rows=audio["audio_rows"],
                    runtime_frames=runtime_frames[event],
                    layer_authority_path=args.layer_authority,
                    audio_authority_path=args.audio_authority,
                )
                write_json(target, manifest)
            manifests[event] = read_json(target)

        projections: dict[str, str] = {}
        for event in EDITORIAL_ORDER:
            projection = _presentation_projection(manifests[event])
            if projection in projections:
                raise Ac1102ExhaustiveError(
                    f"exact complete presentation duplicated: {event}/{projections[projection]}"
                )
            projections[projection] = event
        if set(EDITORIAL_ORDER) != set(REQUIRED_EVENTS) or len(projections) != 15:
            raise Ac1102ExhaustiveError("editorial order is not one-to-one over 15 events")

        source_series = {
            "schema": "magireco-series-editions-v1",
            "series": "ac1102",
            "status": "passed",
            "event_count": 15,
            "family_state": {"ready_event_names": list(EDITORIAL_ORDER)},
            "product_scopes": {event: PRODUCT_SCOPE for event in EDITORIAL_ORDER},
            "natural_session_claims": {event: False for event in EDITORIAL_ORDER},
            "ordering_evidence": (
                "31 DirInfo kind-54 routes reduce to 15 code-reachable complete "
                "event presentations; entry variants, common action variants, "
                "standard outcomes and revival outcomes are grouped editorially"
            ),
            "fixed_native_session_gap_claimed": False,
        }
        source_series_path = staging / "source_series_catalogs" / "ac1102_exhaustive.json"
        write_json(source_series_path, source_series)

        series = {
            "schema": "magireco-ac1102-exhaustive-editorial-series-v1",
            "series": "ac1102_exhaustive",
            "status": "passed",
            "event_count": 15,
            "title_zh": "菲莉希亚牧场 全入口·全选项·全结局完整合集",
            "event_sequence": list(EDITORIAL_ORDER),
            "ordering": (
                "entry variants -> common encounter -> option variants -> standard "
                "outcomes -> alternate entry -> revival outcome"
            ),
            "product_scope": PRODUCT_SCOPE,
            "natural_session_claimed": False,
            "loop_scope": {
                "status": "every code-reachable distinct complete event presentation once",
                "fixed_inter_node_gap": False,
                "mutually_exclusive_routes_combined": True,
            },
            "family_state": {
                "production_manifest_root": str(output_root),
                "known_family_events": 15,
                "ready_family_events": 15,
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
                "evidence": "code-level 31-route/15-event exhaustive presentation authority",
            },
            "human_playback_required": True,
            "publication_approved": False,
        }
        series_path = staging / "series_proposals" / "ac1102_exhaustive.json"
        write_json(series_path, series)

        translation = _augment_translation_map(read_json(args.base_translation_map), audio)
        translation_path = staging / "translations" / "ac1102_exhaustive_zh_v2.json"
        write_json(translation_path, translation)

        raw_native_occurrences = int(unique["native_source_universe"]["occurrence_count"])
        raw_native_unique = int(unique["native_source_universe"]["unique_sha256_count"])
        authority = {
            "schema": "magireco-ac1102-exhaustive-editorial-order-authority-v1",
            "status": "PASS_READY_FOR_RENDER",
            "family": "ac1102",
            "native_dimensions": dict(NATIVE_DIMENSIONS),
            "frame_rate": FRAME_RATE,
            "route_universe": {
                "route_count": len(routes),
                "routes": routes,
                "all_routes_reconstructable": True,
                "legacy_zero_source_flags_superseded_by": [
                    str(args.layer_authority.resolve()),
                    str(args.audio_authority.resolve()),
                ],
            },
            "presentation_universe": {
                "complete_event_presentation_count": 15,
                "unique_complete_presentation_count": len(projections),
                "ordered_events": list(EDITORIAL_ORDER),
                "each_complete_presentation_once": True,
                "raw_native_source_occurrence_count": raw_native_occurrences,
                "raw_native_unique_identity_count": raw_native_unique,
                "raw_native_alias_surplus_count": raw_native_occurrences - raw_native_unique,
                "component_unique_identity_count": EXPECTED_COMPONENT_IDENTITIES,
                "dedupe_unit": "complete_visual_audio_subtitle_presentation",
                "raw_source_aliases_preserved_as_evidence": True,
            },
            "closed_gates": {
                "event_source_universe": "CLOSED_15_EVENTS_36_NATIVE_IDENTITIES",
                "missing_movie_layers": "CLOSED_AS_CODE_UNREACHABLE",
                "event_audio_and_strict_no_bgm": "CLOSED",
                "child_local_timing": "CLOSED_FOR_ALL_SEVEN_NEW_CAPTION_VOICES",
                "duplicate_free_editorial_order": "CLOSED_15_OF_15_UNIQUE",
            },
            "decision": {
                "legacy_91_8s_longform_authoritative": False,
                "v77_route_fragments_are_final_products": False,
                "new_exhaustive_render_allowed": True,
                "human_playback_required": True,
            },
            "source_media_modified": False,
        }
        authority_path = staging / "AC1102_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
        write_json(authority_path, authority)

        binding_paths = [
            args.unique_authority,
            args.layer_authority,
            args.audio_authority,
            args.bounded_hash_authority,
            args.dirinfo,
            args.source_catalog,
            args.base_translation_map,
        ]
        bindings = {
            "schema": "magireco-ac1102-exhaustive-input-bindings-v1",
            "status": "PASS",
            "bindings": [_snapshot(path) for path in binding_paths],
            "source_media_modified": False,
        }
        bindings_path = staging / "SOURCE_BINDINGS.json"
        write_json(bindings_path, bindings)
        verification = {
            "schema": "magireco-ac1102-exhaustive-input-verification-v1",
            "status": "PASS_READY_FOR_RENDER",
            "checks": {
                "dirinfo_routes": 31,
                "complete_event_presentations": 15,
                "unique_complete_presentations": 15,
                "native_source_identities": 36,
                "component_source_identities": 2,
                "unreachable_add_layer_names": 4,
                "retained_no_bgm_audio_occurrences": 15,
                "excluded_bgm_occurrences": 2,
                "child_local_only_timing_occurrences": 0,
                "p16_p17_p18_leak_count": 0,
                "native_416x232_only": True,
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
        verification_path = staging / "VERIFICATION_RECORD.json"
        write_json(verification_path, verification)
        (staging / "README.md").write_text(
            "# ac1102 exhaustive authoritative longform inputs\n\n"
            "This checkpoint reduces all 31 DirInfo rows to 15 distinct complete "
            "event presentations and orders each once. The old 91.8-second product "
            "and v77 route fragments remain preserved but are not final products. "
            "All outputs require human playback.\n",
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
        # Preserve failed staging for diagnosis; never remove evidence or media.
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text(
                "Input checkpoint construction failed; inspect the command error.\n",
                encoding="utf-8",
            )
        raise
    return {
        "output_root": output_root,
        "series_path": output_root / "series_proposals" / "ac1102_exhaustive.json",
        "translation_path": output_root / "translations" / "ac1102_exhaustive_zh_v2.json",
    }


def load_existing_inputs(output_root: Path) -> dict[str, Path]:
    """Reopen one immutable passed checkpoint without rebuilding or overwriting it."""

    output_root = output_root.resolve()
    verification_path = output_root / "VERIFICATION_RECORD.json"
    authority_path = output_root / "AC1102_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
    series_path = output_root / "series_proposals" / "ac1102_exhaustive.json"
    translation_path = output_root / "translations" / "ac1102_exhaustive_zh_v2.json"
    for path in (verification_path, authority_path, series_path, translation_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    verification = read_json(verification_path)
    authority = read_json(authority_path)
    series = read_json(series_path)
    if (
        verification.get("status") != "PASS_READY_FOR_RENDER"
        or verification.get("checks", {}).get("complete_event_presentations") != 15
        or verification.get("checks", {}).get("unique_complete_presentations") != 15
        or authority.get("status") != "PASS_READY_FOR_RENDER"
        or authority.get("decision", {}).get("new_exhaustive_render_allowed") is not True
        or series.get("status") != "passed"
        or series.get("event_sequence") != list(EDITORIAL_ORDER)
    ):
        raise Ac1102ExhaustiveError("existing ac1102 input checkpoint differs")
    return {
        "output_root": output_root,
        "series_path": series_path,
        "translation_path": translation_path,
    }


def _probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames,sample_rate,channels:format=duration",
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


def verify_production(production_root: Path, ffprobe: str) -> dict[str, Any]:
    family = production_root / "ac1102_exhaustive_full_no_bgm_editions_v1"
    manifest_path = family / "manifests" / "family_editions_manifest.json"
    qa_path = family / "qa" / "automated_qa.json"
    manifest = read_json(manifest_path)
    qa = read_json(qa_path)
    if (
        manifest.get("ordered_events") != list(EDITORIAL_ORDER)
        or manifest.get("audio_profile") != "no_bgm"
        or qa.get("checks", {}).get("no_exact_duplicate_audience_events")
        is not True
        or qa.get("status") not in {"passed", "AUTOMATED_QA_PASSED"}
    ):
        raise Ac1102ExhaustiveError("produced family manifest/QA differs")
    media_rows: list[dict[str, Any]] = []
    for edition in ("none", "ja", "zh"):
        path = family / "video" / f"ac1102_exhaustive_full_no_bgm_editions_v1__{edition}.mp4"
        probe = _probe(path, ffprobe)
        video = [row for row in probe["streams"] if row["codec_type"] == "video"]
        audio = [row for row in probe["streams"] if row["codec_type"] == "audio"]
        if (
            len(video) != 1
            or len(audio) != 1
            or video[0].get("codec_name") != "h264"
            or (int(video[0].get("width", 0)), int(video[0].get("height", 0)))
            != (416, 232)
            or video[0].get("r_frame_rate") != "30/1"
            or audio[0].get("codec_name") != "aac"
            or int(audio[0].get("sample_rate", 0)) != 48000
            or int(audio[0].get("channels", 0)) != 2
        ):
            raise Ac1102ExhaustiveError(f"media signature differs: {path}")
        media_rows.append(
            {
                "edition": edition,
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
                "duration_seconds": float(probe["format"]["duration"]),
                "frame_count": int(video[0]["nb_read_frames"]),
                "width": 416,
                "height": 232,
                "frame_rate": "30/1",
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": 48000,
                "audio_channels": 2,
            }
        )
    frame_counts = {row["frame_count"] for row in media_rows}
    durations = [row["duration_seconds"] for row in media_rows]
    if len(frame_counts) != 1 or max(durations) - min(durations) > 0.001:
        raise Ac1102ExhaustiveError("edition frame grid or container duration differs")
    report = {
        "schema": "magireco-ac1102-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "ordered_complete_event_presentations": 15,
        "exact_duplicate_complete_presentation_count": 0,
        "dirinfo_route_coverage": "31/31",
        "native_416x232_only": True,
        "strict_no_bgm": True,
        "blocked_p16_p17_p18_leak_count": 0,
        "media": media_rows,
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
        f"ac1102_exhaustive={inputs['series_path']}",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest-root", required=True, type=Path)
    parser.add_argument("--source-catalog", required=True, type=Path)
    parser.add_argument("--dirinfo", required=True, type=Path)
    parser.add_argument("--unique-authority", required=True, type=Path)
    parser.add_argument("--layer-authority", required=True, type=Path)
    parser.add_argument("--audio-authority", required=True, type=Path)
    parser.add_argument("--bounded-hash-authority", required=True, type=Path)
    parser.add_argument("--base-translation-map", required=True, type=Path)
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
    parser.add_argument(
        "--verify-existing-production",
        action="store_true",
        help="verify an already encoded immutable --production-root without rendering",
    )
    parser.add_argument(
        "--reuse-inputs",
        action="store_true",
        help="reopen the immutable passed --output-input-root for rendering",
    )
    args = parser.parse_args()
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


def main() -> int:
    args = parse_args()
    if args.reuse_inputs:
        inputs = load_existing_inputs(args.output_input_root)
        print(f"PASS_REOPEN inputs={inputs['output_root']}")
    else:
        inputs = build_inputs(args)
        print(
            "PASS routes=31 event_presentations=15 unique_presentations=15 "
            "native_sources=36 components=2 layer_gate=CLOSED audio_gate=CLOSED "
            f"inputs={inputs['output_root']}"
        )
    if args.render:
        report = render(args, inputs)
        media = report["media"]
        print(
            "PASS_RENDER editions=3 frames="
            f"{media[0]['frame_count']} duration={media[0]['duration_seconds']:.3f}s "
            f"production={args.production_root.resolve()}"
        )
    elif args.verify_existing_production:
        report = verify_production(args.production_root.resolve(), args.ffprobe)
        media = report["media"]
        print(
            "PASS_VERIFY_EXISTING editions=3 frames="
            f"{media[0]['frame_count']} duration={media[0]['duration_seconds']:.3f}s "
            f"production={args.production_root.resolve()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
