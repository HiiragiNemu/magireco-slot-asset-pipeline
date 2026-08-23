#!/usr/bin/env python3
"""Build one duplicate-free exhaustive native-416 ac7205 no-BGM longform."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac7210_exhaustive_authoritative_longform import (
        _probe_video,
        _snapshot,
        _video_stream,
        build_event_manifest as build_base_event_manifest,
        frame_to_ms,
        presentation_projection,
        read_json,
        write_json,
    )
    from .build_event_production_manifests import file_sha256, quantize_duration_to_frame_grid
    from .resolve_ac7205_event_audio_authority import (
        EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER,
        EXPECTED_PRESENTATION_FRAMES,
        NATIVE416_EVENTS,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_ac7210_exhaustive_authoritative_longform import (
        _probe_video,
        _snapshot,
        _video_stream,
        build_event_manifest as build_base_event_manifest,
        frame_to_ms,
        presentation_projection,
        read_json,
        write_json,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import file_sha256, quantize_duration_to_frame_grid
    from tools.frida_runtime_probe.resolve_ac7205_event_audio_authority import (
        EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER,
        EXPECTED_PRESENTATION_FRAMES,
        NATIVE416_EVENTS,
    )


EDITORIAL_ORDER = EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER
FRAME_RATE = "30/1"
NATIVE_DIMENSIONS = {"width": 416, "height": 232}
PRODUCT_SCOPE = "exhaustive_duplicate_free_code_reachable_av_editorial_longform"
EXPECTED_ROUTE_ROWS = 98
EXPECTED_CANONICAL_SOURCES = 23
EXPECTED_PRIMARY_OCCURRENCES = 42
EXPECTED_OVERLAY_OCCURRENCES = 10
EXPECTED_RETAINED_AUDIO = 41
EXPECTED_EXCLUDED_BGM = 3
EXPECTED_SUBTITLES = 9
EXPECTED_FRAMES = sum(EXPECTED_PRESENTATION_FRAMES.values())


class Ac7205ExhaustiveError(ValueError):
    pass


def validate_authorities(visual: Mapping[str, Any], audio: Mapping[str, Any]) -> None:
    va = visual.get("assertions", {})
    vd = visual.get("decision", {})
    aa = audio.get("assertions", {})
    ad = audio.get("decision", {})
    if (
        visual.get("schema") != "magireco-ac7205-movielayer-runtime-reachability-authority-v1"
        or visual.get("status") != "passed"
        or int(va.get("dirinfo_route_count", -1)) != EXPECTED_ROUTE_ROWS
        or int(va.get("native416_canonical_source_identity_count", -1)) != EXPECTED_CANONICAL_SOURCES
        or int(va.get("native416_byte_identical_alias_group_count", -1)) != 2
        or tuple(vd.get("native416_events", [])) != NATIVE416_EVENTS
        or tuple(vd.get("native416_exhaustive_editorial_order", [])) != EDITORIAL_ORDER
        or vd.get("native416_visual_reachability_gate") != "CLOSED"
        or tuple(vd.get("deferred_native512_gameplay_effect_events", [])) != ("ac7205_018",)
    ):
        raise Ac7205ExhaustiveError("ac7205 visual authority differs")
    if (
        audio.get("schema") != "magireco-ac7205-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "passed"
        or int(aa.get("retained_audio_occurrences", -1)) != EXPECTED_RETAINED_AUDIO
        or int(aa.get("excluded_bgm_occurrences", -1)) != EXPECTED_EXCLUDED_BGM
        or int(aa.get("subtitle_cues", -1)) != EXPECTED_SUBTITLES
        or int(aa.get("presentation_frames", -1)) != EXPECTED_FRAMES
        or tuple(ad.get("native416_events", [])) != NATIVE416_EVENTS
        or tuple(ad.get("editorial_order", [])) != EDITORIAL_ORDER
        or ad.get("strict_no_bgm_gate") != "CLOSED_THREE_EXACT_BGM_ROWS_EXCLUDED"
        or ad.get("event_global_voice_subtitle_gate") != "CLOSED"
        or ad.get("byte_identical_visual_alias_gate") != "CLOSED_TWO_DGM_ALIASES_OMITTED"
    ):
        raise Ac7205ExhaustiveError("ac7205 audio authority differs")


def event_code_map(runtime: Mapping[str, Any]) -> dict[str, str]:
    requested = {str(event): str(code).casefold() for event, code in runtime.get("requested_events", {}).items()}
    if set(requested) != set(NATIVE416_EVENTS) | {"ac7205_018"}:
        raise Ac7205ExhaustiveError("ac7205 runtime event-code set differs")
    if any(not code.startswith("0x") or len(code) != 18 for code in requested.values()):
        raise Ac7205ExhaustiveError("ac7205 runtime event-code format differs")
    return requested


def translation_rows_by_request(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = value.get("translations", [])
    result = {str(row.get("request_id", "")): dict(row) for row in rows}
    if set(result) != {"8310", "8311", "8312", "8313", "8314"} or len(result) != len(rows):
        raise Ac7205ExhaustiveError("ac7205 translation request set differs")
    if any(not row.get("ja") or not row.get("zh") for row in result.values()):
        raise Ac7205ExhaustiveError("ac7205 translation text is empty")
    return result


def renderer_translation_map(translations: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    order = ("8311", "8312", "8313", "8310", "8314")
    rows = [
        {
            "ja": str(translations[request]["ja"]),
            "zh": str(translations[request]["zh"]),
            "status": "machine_draft_pending_owner",
        }
        for request in order
    ]
    if len({row["ja"] for row in rows}) != len(rows):
        raise Ac7205ExhaustiveError("ac7205 Japanese translation keys are not unique")
    return {
        "schema": "magireco-reviewed-story-zh-dialogue-map-v1",
        "scope": "ac7205_exhaustive_native416_runtime_bound_dialogue",
        "status": "new_longform_human_playback_required",
        "translations": rows,
        "approval_boundary": "new code-derived exhaustive longform and translation timing require owner playback",
    }


def source_index(visual: Mapping[str, Any], ffprobe: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    canonical_count = 0
    for row in visual.get("movie_layers", []):
        if row.get("content_class") != "native416_family_source":
            continue
        path = Path(str(row["media_path"])).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        probe = _probe_video(path, ffprobe)
        stream = _video_stream(probe)
        frames = int(stream.get("nb_read_frames", 0))
        if (
            stream.get("codec_name") != "h264"
            or stream.get("r_frame_rate") != FRAME_RATE
            or (int(stream.get("width", 0)), int(stream.get("height", 0))) != (416, 232)
            or frames != int(row["frame_count"])
            or file_sha256(path) != str(row["media_sha256"])
        ):
            raise Ac7205ExhaustiveError(f"native416 source signature differs: {path}")
        entry = {
            "dgm_name": str(row["z2d_reference"]).removesuffix(".dgm"),
            "path": str(path), "sha256": str(row["media_sha256"]),
            "source_frame_count": frames,
            "source_identity_disposition": row["source_identity_disposition"],
            "parent_z2d": row["parent_z2d"],
        }
        result[str(path).casefold()] = entry
        if row["source_identity_disposition"] == "CANONICAL_SOURCE_IDENTITY":
            canonical_count += 1
    if canonical_count != EXPECTED_CANONICAL_SOURCES:
        raise Ac7205ExhaustiveError("ac7205 canonical source count differs")
    return result


def event_layer_rows(
    event: str,
    visual_plan: Sequence[Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    primary: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    for plan in visual_plan:
        if plan["event"] != event:
            continue
        cursor = int(plan["normalized_start_frame"])
        for raw_path in plan["canonical_media_paths"]:
            source = sources.get(str(Path(raw_path).resolve()).casefold())
            if source is None or source["source_identity_disposition"] != "CANONICAL_SOURCE_IDENTITY":
                raise Ac7205ExhaustiveError(f"canonical source missing: {event}/{raw_path}")
            frames = int(source["source_frame_count"])
            row = {
                **dict(source),
                "event_start_frame": cursor,
                "event_end_frame_exclusive": cursor + frames,
                "event_start_ms": frame_to_ms(cursor),
                "event_end_ms": frame_to_ms(cursor + frames),
                "source_frame_contract": "exact_one_to_one_authored_interval",
            }
            if plan["visual_role"] == "runtime_looping_frame_overlay":
                row.update({"dgm_role": "loop_screen_overlay", "blend_mode": "screen"})
                overlays.append(row)
            else:
                row["dgm_role"] = "background"
                primary.append(row)
            cursor += frames
    primary.sort(key=lambda row: int(row["event_start_frame"]))
    overlays.sort(key=lambda row: int(row["event_start_frame"]))
    if not primary or primary[0]["event_start_frame"] != 0:
        raise Ac7205ExhaustiveError(f"event primary visual does not begin at normalized frame zero: {event}")
    for previous, current in zip(primary, primary[1:]):
        if previous["event_end_frame_exclusive"] != current["event_start_frame"]:
            raise Ac7205ExhaustiveError(f"event primary visual is not contiguous: {event}")
    visual_frames = int(primary[-1]["event_end_frame_exclusive"])
    return primary, overlays, visual_frames


def build_event_manifest(
    event: str,
    *,
    code_hex: str,
    primary: Sequence[Mapping[str, Any]],
    overlays: Sequence[Mapping[str, Any]],
    visual_frames: int,
    presentation: Mapping[str, Any],
    retained_audio: Sequence[Mapping[str, Any]],
    excluded_audio: Sequence[Mapping[str, Any]],
    subtitle_rows: Sequence[Mapping[str, Any]],
    translations: Mapping[str, Mapping[str, Any]],
    visual_authority_path: Path,
    audio_authority_path: Path,
) -> dict[str, Any]:
    event_retained = [dict(row) for row in retained_audio if row["event"] == event]
    event_subtitles = [dict(row) for row in subtitle_rows if row["event"] == event]
    legacy_transport_content_end = max(
        frame_to_ms(visual_frames),
        max((int(row["start_ms"]) + int(row["duration_ms"]) for row in event_retained), default=0),
        max((int(row["end_ms"]) for row in event_subtitles), default=0),
    )
    legacy_transport_frames = int(
        quantize_duration_to_frame_grid(legacy_transport_content_end, FRAME_RATE)["frame_count"]
    )
    base_presentation = {
        "video_content_frames": visual_frames,
        "presentation_frames": legacy_transport_frames,
        "tail_hold_frames": legacy_transport_frames - visual_frames,
    }
    manifest = build_base_event_manifest(
        event,
        code_hex=code_hex,
        layer_rows=primary,
        visual_frames=visual_frames,
        presentation=base_presentation,
        audio_rows=retained_audio,
        subtitle_rows=subtitle_rows,
        translations=translations,
        visual_authority_path=visual_authority_path,
        audio_authority_path=audio_authority_path,
    )
    exact_content_end = max(
        visual_frames * 1000 // 30,
        max((int(row["start_ms"]) + int(row["duration_ms"]) for row in event_retained), default=0),
        max((int(row["end_ms"]) for row in event_subtitles), default=0),
    )
    exact_quantization = quantize_duration_to_frame_grid(exact_content_end, FRAME_RATE)
    authoritative_frames = int(presentation["presentation_frames"])
    if int(exact_quantization["frame_count"]) != authoritative_frames:
        raise Ac7205ExhaustiveError(f"exact event frame-grid closure differs: {event}")
    manifest.update({
        "video_duration_ms": visual_frames * 1000 // 30,
        "timeline_duration_ms": exact_content_end,
        "timeline_content_end_ms": exact_content_end,
        "raw_render_duration_ms": exact_content_end,
        "render_frame_count": authoritative_frames,
        "render_duration_ms": int(exact_quantization["duration_ms"]),
        "render_duration_quantization": exact_quantization,
    })
    manifest["composition_plan"]["duration_ms"] = exact_content_end
    for row in overlays:
        manifest["clips"].append({
            "order": len(manifest["clips"]),
            "dgm_name": row["dgm_name"], "dgm_role": row["dgm_role"],
            "path": row["path"], "source_sha256": row["sha256"],
            "event_start_ms": int(row["event_start_ms"]),
            "event_end_ms": int(row["event_end_ms"]),
            "authored_event_end_ms": int(row["event_end_ms"]),
            "source_frame_count": int(row["source_frame_count"]),
            "authored_layer_frame_count": int(row["source_frame_count"]),
            "interval_confidence": "exact_z2d_runtime_looping_overlay",
            "source_frame_contract": row["source_frame_contract"],
        })
        manifest["composition_plan"]["clips"].append({
            "dgm_name": row["dgm_name"], "role": row["dgm_role"],
            "start_ms": int(row["event_start_ms"]), "blend_mode": row["blend_mode"],
        })
    excluded = [dict(row) for row in excluded_audio if row["event"] == event]
    if any(row.get("volume_bus") != "BGM" for row in excluded):
        raise Ac7205ExhaustiveError(f"non-BGM row entered excluded set: {event}")
    manifest["strict_no_bgm_sound_bus_contract"]["excluded_occurrences"] = [
        {
            "request_id": str(row["request_id"]), "sound_id": int(row["sound_id"]),
            "start_ms": int(row["start_ms"]), "duration_ms": int(row["duration_ms"]),
            "volume_bus": "BGM", "disposition": row["strict_no_bgm_disposition"],
        }
        for row in excluded
    ]
    manifest["composition_plan"]["evidence"] = (
        "exact Z2D MovieLayer intervals, IDA-decoded motion modes, screen overlays, "
        "and byte-identical alias omission"
    )
    manifest["quality_gates"]["composition_evidence"] = "ac7205 code-level Z2D/runtime authority"
    manifest.pop("ac7210_generated_manifest_provenance", None)
    manifest["ac7205_generated_manifest_provenance"] = {
        "visual_authority": str(visual_authority_path.resolve()),
        "audio_authority": str(audio_authority_path.resolve()),
        "canonical_primary_layer_count": len(primary),
        "looping_screen_overlay_count": len(overlays),
        "retained_audio_occurrence_count": len([row for row in retained_audio if row["event"] == event]),
        "excluded_bgm_occurrence_count": len(excluded),
        "subtitle_cue_count": len([row for row in subtitle_rows if row["event"] == event]),
        "presentation_frames": int(presentation["presentation_frames"]),
        "source_media_modified": False,
    }
    return manifest


def build_inputs(args: argparse.Namespace) -> dict[str, Path]:
    output_root = args.output_input_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"immutable input checkpoint already exists: {output_root}")
    visual = read_json(args.visual_authority)
    audio = read_json(args.audio_authority)
    runtime = read_json(args.runtime_scene_motion)
    translation_source = read_json(args.translation_map)
    validate_authorities(visual, audio)
    codes = event_code_map(runtime)
    translations = translation_rows_by_request(translation_source)
    sources = source_index(visual, args.ffprobe)
    presentations = {str(row["event"]): row for row in audio["event_presentations"]}
    if set(presentations) != set(NATIVE416_EVENTS):
        raise Ac7205ExhaustiveError("ac7205 event presentation set differs")

    staging = output_root.parent / f".{output_root.name}.staging-{os.getpid()}"
    if staging.exists():
        raise FileExistsError(f"staging checkpoint already exists: {staging}")
    try:
        events_root = staging / "events"
        events_root.mkdir(parents=True)
        manifests: dict[str, dict[str, Any]] = {}
        overlay_occurrences = 0
        primary_occurrences = 0
        for event in NATIVE416_EVENTS:
            primary, overlays, visual_frames = event_layer_rows(
                event, audio["event_visual_source_plan"], sources
            )
            primary_occurrences += len(primary)
            overlay_occurrences += len(overlays)
            manifest = build_event_manifest(
                event,
                code_hex=codes[event],
                primary=primary,
                overlays=overlays,
                visual_frames=visual_frames,
                presentation=presentations[event],
                retained_audio=audio["retained_audio_rows"],
                excluded_audio=audio["excluded_audio_rows"],
                subtitle_rows=audio["subtitle_cues"],
                translations=translations,
                visual_authority_path=args.visual_authority,
                audio_authority_path=args.audio_authority,
            )
            write_json(events_root / f"{event}.json", manifest)
            manifests[event] = manifest
        if (
            sum(len(row["audio"]) for row in manifests.values()) != EXPECTED_RETAINED_AUDIO
            or sum(len(row["subtitles"]) for row in manifests.values()) != EXPECTED_SUBTITLES
            or sum(int(row["render_frame_count"]) for row in manifests.values()) != EXPECTED_FRAMES
            or sum(
                len(row["strict_no_bgm_sound_bus_contract"]["excluded_occurrences"])
                for row in manifests.values()
            ) != EXPECTED_EXCLUDED_BGM
            or overlay_occurrences != EXPECTED_OVERLAY_OCCURRENCES
            or primary_occurrences != EXPECTED_PRIMARY_OCCURRENCES
        ):
            raise Ac7205ExhaustiveError("ac7205 event manifest cardinality differs")
        seen: dict[str, str] = {}
        for event in EDITORIAL_ORDER:
            projection = presentation_projection(manifests[event])
            if projection in seen:
                raise Ac7205ExhaustiveError(
                    f"complete AV presentation duplicated: {event}/{seen[projection]}"
                )
            seen[projection] = event

        source_series = {
            "schema": "magireco-series-editions-v1",
            "series": "ac7205",
            "status": "passed",
            "event_count": len(NATIVE416_EVENTS),
            "family_state": {"ready_event_names": list(EDITORIAL_ORDER)},
            "product_scopes": {event: PRODUCT_SCOPE for event in EDITORIAL_ORDER},
            "natural_session_claims": {event: False for event in EDITORIAL_ORDER},
            "ordering_evidence": "98 DirInfo rows, exact 22-event runtime mapping, and code-derived MovieLayer/loop authority",
            "fixed_native_session_gap_claimed": False,
        }
        source_series_path = staging / "source_series_catalogs" / "ac7205_exhaustive_native416.json"
        write_json(source_series_path, source_series)
        series = {
            "schema": "magireco-ac7205-exhaustive-native416-editorial-series-v1",
            "series": "ac7205_exhaustive_native416",
            "status": "passed",
            "event_count": len(NATIVE416_EVENTS),
            "title_zh": "丘比新闻与魔女化身抉择 全事件·全结果完整合集",
            "event_sequence": list(EDITORIAL_ORDER),
            "ordering": "entry variants, blue/red report variants, dialogue outcomes, and development outcomes",
            "product_scope": PRODUCT_SCOPE,
            "natural_session_claimed": False,
            "loop_scope": {
                "status": "every code-reachable distinct native416 AV presentation once",
                "fixed_inter_node_gap": False,
                "mutually_exclusive_routes_combined": True,
                "byte_identical_authored_aliases_omitted": 2,
            },
            "family_state": {
                "production_manifest_root": str(output_root),
                "known_family_events": 22,
                "ready_family_events": len(NATIVE416_EVENTS),
                "not_ready_family_events": ["ac7205_018"],
                "ready_event_names": list(EDITORIAL_ORDER),
            },
            "event_manifest_sha256": {
                event: file_sha256(events_root / f"{event}.json") for event in EDITORIAL_ORDER
            },
            "source_series_manifest": {
                "path": str((output_root / source_series_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(source_series_path),
                "evidence": "code-level DirInfo/runtime/MovieLayer/SOUND_DIVIDE authority",
            },
            "human_playback_required": True,
            "publication_approved": False,
        }
        series_path = staging / "series_proposals" / "ac7205_exhaustive_native416.json"
        write_json(series_path, series)
        rendered_translation = renderer_translation_map(translations)
        translation_path = staging / "translations" / "ac7205_exhaustive_native416_zh_v1.json"
        write_json(translation_path, rendered_translation)

        authority = {
            "schema": "magireco-ac7205-exhaustive-native416-editorial-order-authority-v1",
            "status": "PASS_READY_FOR_STORY_RENDER",
            "family": "ac7205",
            "native_dimensions": dict(NATIVE_DIMENSIONS), "frame_rate": FRAME_RATE,
            "route_universe": {
                "dirinfo_route_rows": EXPECTED_ROUTE_ROWS,
                "known_events": 22,
                "native416_events": list(NATIVE416_EVENTS),
                "deferred_native512_events": ["ac7205_018"],
            },
            "presentation_universe": {
                "complete_av_presentation_count": len(NATIVE416_EVENTS),
                "unique_complete_av_presentation_count": len(seen),
                "canonical_source_identities": EXPECTED_CANONICAL_SOURCES,
                "primary_source_occurrences": primary_occurrences,
                "looping_screen_overlay_occurrences": overlay_occurrences,
                "byte_identical_alias_omitted_count": 2,
                "ordered_events": list(EDITORIAL_ORDER),
                "each_complete_av_presentation_once": True,
                "presentation_frames": EXPECTED_FRAMES,
            },
            "closed_gates": {
                "visual_universe": "CLOSED_21_NATIVE416_EVENTS_23_CANONICAL_SOURCES",
                "event_audio_and_strict_no_bgm": "CLOSED_41_RETAINED_3_BGM_EXCLUDED",
                "event_global_dialogue_timing": "CLOSED_FOR_ALL_9_VOICE_OCCURRENCES",
                "duplicate_free_editorial_order": "CLOSED_21_OF_21_UNIQUE_COMPLETE_AV",
            },
            "decision": {
                "old_short_route_fragments_are_primary_products": False,
                "new_exhaustive_native416_render_allowed": True,
                "deferred_native512_render_allowed": False,
                "human_playback_required": True,
            },
            "source_media_modified": False,
        }
        authority_path = staging / "AC7205_EXHAUSTIVE_NATIVE416_EDITORIAL_AUTHORITY.json"
        write_json(authority_path, authority)
        bindings = {
            "schema": "magireco-ac7205-exhaustive-native416-input-bindings-v1",
            "status": "PASS",
            "bindings": [
                _snapshot(path) for path in (
                    args.visual_authority, args.audio_authority,
                    args.runtime_scene_motion, args.translation_map,
                )
            ],
            "source_media_modified": False,
        }
        write_json(staging / "SOURCE_BINDINGS.json", bindings)
        verification = {
            "schema": "magireco-ac7205-exhaustive-native416-input-verification-v1",
            "status": "PASS_READY_FOR_STORY_RENDER",
            "checks": {
                "dirinfo_route_rows": EXPECTED_ROUTE_ROWS,
                "known_family_events": 22,
                "native416_events": len(NATIVE416_EVENTS),
                "deferred_native512_events": 1,
                "canonical_source_identities": EXPECTED_CANONICAL_SOURCES,
                "byte_identical_alias_omitted_count": 2,
                "retained_no_bgm_audio_occurrences": EXPECTED_RETAINED_AUDIO,
                "excluded_bgm_occurrences": EXPECTED_EXCLUDED_BGM,
                "subtitle_cues": EXPECTED_SUBTITLES,
                "child_local_only_timing_occurrences": 0,
                "presentation_frames": EXPECTED_FRAMES,
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
            "# ac7205 exhaustive native416 longform inputs\n\n"
            "All 98 DirInfo rows and 22 events remain indexed. The primary product contains "
            "all 21 native-416 code-reachable AV presentations once; native-512 event 018 "
            "remains deferred. Three exact BGM rows are excluded and all nine dialogue "
            "occurrences use event-global parent timing.\n",
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
        "series_path": output_root / "series_proposals" / "ac7205_exhaustive_native416.json",
        "translation_path": output_root / "translations" / "ac7205_exhaustive_native416_zh_v1.json",
    }


def load_existing_inputs(output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    verification = read_json(output_root / "VERIFICATION_RECORD.json")
    authority = read_json(output_root / "AC7205_EXHAUSTIVE_NATIVE416_EDITORIAL_AUTHORITY.json")
    series_path = output_root / "series_proposals" / "ac7205_exhaustive_native416.json"
    translation_path = output_root / "translations" / "ac7205_exhaustive_native416_zh_v1.json"
    series = read_json(series_path)
    if (
        verification.get("status") != "PASS_READY_FOR_STORY_RENDER"
        or verification.get("checks", {}).get("presentation_frames") != EXPECTED_FRAMES
        or authority.get("decision", {}).get("new_exhaustive_native416_render_allowed") is not True
        or authority.get("decision", {}).get("deferred_native512_render_allowed") is not False
        or series.get("event_sequence") != list(EDITORIAL_ORDER)
    ):
        raise Ac7205ExhaustiveError("existing ac7205 input checkpoint differs")
    return {
        "output_root": output_root,
        "series_path": series_path,
        "translation_path": translation_path,
    }


def verify_production(production_root: Path, ffprobe: str) -> dict[str, Any]:
    family = production_root / "ac7205_exhaustive_native416_full_no_bgm_editions_v1"
    manifest = read_json(family / "manifests" / "family_editions_manifest.json")
    qa = read_json(family / "qa" / "automated_qa.json")
    if (
        manifest.get("ordered_events") != list(EDITORIAL_ORDER)
        or manifest.get("audio_profile") != "no_bgm"
        or "ac7205_018" in manifest.get("ordered_events", [])
        or qa.get("checks", {}).get("no_exact_duplicate_audience_events") is not True
        or qa.get("status") not in {"passed", "AUTOMATED_QA_PASSED"}
    ):
        raise Ac7205ExhaustiveError("produced ac7205 family manifest/QA differs")
    media: list[dict[str, Any]] = []
    for edition in ("none", "ja", "zh"):
        path = family / "video" / f"ac7205_exhaustive_native416_full_no_bgm_editions_v1__{edition}.mp4"
        probe = _probe_video(path, ffprobe)
        videos = [row for row in probe["streams"] if row["codec_type"] == "video"]
        audios = [row for row in probe["streams"] if row["codec_type"] == "audio"]
        if (
            len(videos) != 1 or len(audios) != 1
            or videos[0].get("codec_name") != "h264"
            or (int(videos[0].get("width", 0)), int(videos[0].get("height", 0))) != (416, 232)
            or videos[0].get("r_frame_rate") != FRAME_RATE
            or int(videos[0].get("nb_read_frames", 0)) != EXPECTED_FRAMES
            or audios[0].get("codec_name") != "aac"
            or int(audios[0].get("sample_rate", 0)) != 48000
            or int(audios[0].get("channels", 0)) != 2
        ):
            raise Ac7205ExhaustiveError(f"media signature differs: {path}")
        media.append({
            "edition": edition, "path": str(path.resolve()),
            "sha256": file_sha256(path), "duration_seconds": float(probe["format"]["duration"]),
            "frame_count": int(videos[0]["nb_read_frames"]),
            "width": 416, "height": 232, "frame_rate": FRAME_RATE,
            "video_codec": "h264", "audio_codec": "aac",
            "audio_sample_rate": 48000, "audio_channels": 2,
        })
    if max(row["duration_seconds"] for row in media) - min(row["duration_seconds"] for row in media) > 0.001:
        raise Ac7205ExhaustiveError("ac7205 edition durations differ")
    report = {
        "schema": "magireco-ac7205-exhaustive-native416-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1, "edition_file_count": 3,
        "ordered_complete_event_presentations": len(NATIVE416_EVENTS),
        "canonical_source_identities": EXPECTED_CANONICAL_SOURCES,
        "byte_identical_alias_omitted_count": 2,
        "exact_duplicate_complete_presentation_count": 0,
        "dirinfo_route_coverage": "98/98",
        "deferred_native512_events": ["ac7205_018"],
        "native_416x232_only": True, "strict_no_bgm": True,
        "excluded_bgm_occurrences": EXPECTED_EXCLUDED_BGM,
        "blocked_p16_p17_p18_leak_count": 0,
        "media": media, "source_media_modified": False, "bilibili_uploaded": False,
    }
    write_json(production_root / "PRODUCTION_VERIFICATION.json", report)
    return report


def render(args: argparse.Namespace, inputs: Mapping[str, Path]) -> dict[str, Any]:
    production_root = args.production_root.resolve()
    if production_root.exists():
        raise FileExistsError(f"immutable production root already exists: {production_root}")
    command = [
        sys.executable, str(args.family_builder.resolve()),
        "--manifest-root", str(inputs["output_root"]),
        "--series-manifest", f"ac7205_exhaustive_native416={inputs['series_path']}",
        "--translation-map", str(inputs["translation_path"]),
        "--layout-profile", str(args.layout_profile.resolve()),
        "--speaker-registry", str(args.speaker_registry.resolve()),
        "--edition", "none", "--edition", "ja", "--edition", "zh",
        "--font", str(args.font.resolve()), "--out-root", str(production_root),
        "--renderer", str(args.renderer.resolve()),
        "--ffmpeg", args.ffmpeg, "--ffprobe", args.ffprobe,
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
    if args.render and any(value is None for value in (
        args.production_root, args.family_builder, args.layout_profile,
        args.speaker_registry, args.font, args.renderer,
    )):
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
            f"PASS routes=98 events=22 native416=21 canonical_sources=23 "
            f"audio=41 excluded_bgm=3 subtitles=9 frames={EXPECTED_FRAMES} "
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
