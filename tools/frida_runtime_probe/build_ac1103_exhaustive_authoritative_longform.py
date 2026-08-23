#!/usr/bin/env python3
"""Build the exhaustive, duplicate-free native-416 ac1103 longform.

The audience product is one editorial collection containing every distinct
code-reachable complete event presentation once.  The 31 mutually exclusive
DirInfo rows remain route evidence; they are not promoted to 31 standalone
final products.  In particular, ac1103_013 (the former 18-second revival
fragment) is retained as the final chapter of this collection.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_event_production_manifests import file_sha256
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import file_sha256


EDITORIAL_ORDER = (
    "ac1103_001",  # entry presentation A
    "ac1103_008",  # entry presentation B
    "ac1103_009",  # entry presentation C
    "ac1103_010",  # entry presentation D
    "ac1103_011",  # entry presentation E
    "ac1103_002",  # common road sequence A
    "ac1103_007",  # common road sequence B
    "ac1103_003",  # option/outcome A
    "ac1103_004",  # option setup B/C
    "ac1103_005",  # outcome B
    "ac1103_006",  # outcome C
    "ac1103_012",  # revival entry
    "ac1103_013",  # victory/revival completion
)
REQUIRED_EVENTS = frozenset(EDITORIAL_ORDER)
PRODUCT_SCOPE = "exhaustive_duplicate_free_event_presentation_editorial_longform"
EXPECTED_ROUTE_COUNT = 31
EXPECTED_EVENT_COUNT = 13
EXPECTED_FRAME_COUNT = 3114
EXPECTED_SOURCE_OCCURRENCES = 53
EXPECTED_UNIQUE_SOURCE_IDENTITIES = 35
EXPECTED_RETAINED_AUDIO_OCCURRENCES = 57
EXPECTED_SUBTITLE_OCCURRENCES = 33
EXPECTED_EXCLUDED_BGM_OCCURRENCES = 2


class Ac1103ExhaustiveError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def snapshot(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def presentation_projection(manifest: Mapping[str, Any]) -> str:
    """Canonical complete AV/subtitle presentation identity."""

    return json.dumps(
        {
            "frames": int(manifest["render_frame_count"]),
            "visual": [
                {
                    "dgm_name": str(row["dgm_name"]),
                    "role": str(row.get("dgm_role", "")),
                    "source_sha256": str(row["source_sha256"]).upper(),
                    "start_ms": int(row["event_start_ms"]),
                    "end_ms": int(row["event_end_ms"]),
                }
                for row in manifest["clips"]
            ],
            "audio": [
                {
                    "request_id": str(row["request_id"]),
                    "sound_id": int(row.get("sound_id", -1)),
                    "ogg_name": str(row["ogg_name"]),
                    "start_ms": int(row["start_ms"]),
                    "duration_ms": int(row["duration_ms"]),
                }
                for row in manifest["audio"]
            ],
            "subtitles": [
                {
                    "request_id": str(row.get("voice_request_id", "")),
                    "text": str(row.get("text", "")),
                    "start_ms": int(row["start_ms"]),
                    "end_ms": int(row["end_ms"]),
                }
                for row in manifest.get("subtitles", [])
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def bind_exact_ac1103_013_audio_roles(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Expose the already-bound IDA/runtime role contract to the renderer gate.

    The v69r2 ac1103_013 manifest carries the exact role facts under
    ``ida_volume_*`` plus a hash-bound correction object.  The generic renderer
    deliberately accepts only its normalized full contract.  This function
    performs that lossless schema bridge; it does not infer a role from text or
    from the presence/absence of a subtitle.
    """

    prepared = copy.deepcopy(dict(manifest))
    if prepared.get("event") != "ac1103_013":
        return prepared
    correction = prepared.get("strict_no_bgm_sound_bus_correction", {})
    if correction.get("status") != "hash_bound":
        raise Ac1103ExhaustiveError("ac1103_013 sound-bus correction is not hash-bound")
    retained = {str(value) for value in correction.get("retained_request_ids", [])}
    voice = {str(value) for value in correction.get("voice_request_ids", [])}
    scene_se = {str(value) for value in correction.get("scene_se_request_ids", [])}
    audio_ids = {str(row.get("request_id", "")) for row in prepared.get("audio", [])}
    if retained != audio_ids or voice & scene_se or voice | scene_se != retained:
        raise Ac1103ExhaustiveError("ac1103_013 exact retained role partition differs")
    for row in prepared["audio"]:
        request_id = str(row["request_id"])
        if request_id in voice:
            expected = ("VOICE", 2, "z2d_req_sound")
            disposition = "RETAIN_VERIFIED_VOICE"
            timing = "runtime_parent_scene_z2d_start_plus_exact_child_callback_frame_0"
            row["event_global_start_resolved"] = True
        else:
            expected = ("SE", 1, "event_audio_component")
            disposition = "RETAIN_VERIFIED_SE"
            timing = "official_event_audio_component_event_global_start"
        if (
            row.get("ida_volume_bus"),
            int(row.get("ida_volume_kind_value", -1)),
            row.get("source"),
        ) != expected:
            raise Ac1103ExhaustiveError(
                f"ac1103_013 exact role evidence differs: request {request_id}"
            )
        row["volume_bus"] = expected[0]
        row["volume_kind_value"] = expected[1]
        row["strict_no_bgm_disposition"] = disposition
        row["timing_evidence"] = timing
    prepared["exhaustive_longform_audio_role_binding"] = {
        "status": "hash_bound_schema_normalization",
        "retained_request_ids": sorted(retained, key=int),
        "voice_request_ids": sorted(voice, key=int),
        "scene_se_request_ids": sorted(scene_se, key=int),
        "semantic_change": False,
        "source_media_modified": False,
    }
    return prepared


def validate_source_checkpoint(
    source_root: Path,
    base_translation_map: Path,
) -> dict[str, Any]:
    summary_path = source_root / "SUMMARY.json"
    authority_path = source_root / "AC1103_EVENT_GLOBAL_ROUTE_AUTHORITY.json"
    verification_path = source_root / "VERIFICATION.json"
    summary = read_json(summary_path)
    authority = read_json(authority_path)
    verification = read_json(verification_path)

    if (
        summary.get("schema") != "magireco-ac1103-event-global-route-inputs-v1"
        or summary.get("status") != "PASS"
        or int(summary.get("event_count", -1)) != EXPECTED_EVENT_COUNT
        or int(summary.get("route_count", -1)) != EXPECTED_ROUTE_COUNT
        or int(summary.get("blocked_route_count", -1)) != 0
        or verification.get("result") != "PASS"
        or int(verification.get("blocked_route_count", -1)) != 0
    ):
        raise Ac1103ExhaustiveError("source route checkpoint is not exact-ready")
    if (
        authority.get("schema") != "magireco-ac1103-event-global-route-authority-v1"
        or authority.get("status") != "PASS"
        or authority.get("dirinfo", {}).get("kind") != 55
        or authority.get("dirinfo", {}).get("blocked_routes") != {}
        or authority.get("source_media_modified") is not False
    ):
        raise Ac1103ExhaustiveError("source authority differs")
    bound_authority = summary.get("authority", {})
    if (
        Path(str(bound_authority.get("path", ""))).resolve() != authority_path.resolve()
        or str(bound_authority.get("sha256", "")).upper() != file_sha256(authority_path)
    ):
        raise Ac1103ExhaustiveError("summary authority binding differs")

    routes = summary.get("routes", [])
    if [int(row.get("row_index", -1)) for row in routes] != list(range(31)):
        raise Ac1103ExhaustiveError("DirInfo route index set differs")
    route_sequences = {
        int(row["row_index"]): tuple(str(value) for value in row["event_sequence"])
        for row in routes
    }
    authority_routes = {
        int(key): tuple(str(value) for value in values)
        for key, values in authority["dirinfo"]["source_resolved_routes"].items()
    }
    if route_sequences != authority_routes:
        raise Ac1103ExhaustiveError("summary and authority route sequences differ")
    route_union = {event for sequence in route_sequences.values() for event in sequence}
    if route_union != REQUIRED_EVENTS:
        raise Ac1103ExhaustiveError("31 routes do not cover the 13-event universe")

    summary_events = {str(row["event"]): row for row in summary.get("events", [])}
    if set(summary_events) != REQUIRED_EVENTS or set(authority.get("events", {})) != REQUIRED_EVENTS:
        raise Ac1103ExhaustiveError("event universe differs")

    translations_payload = read_json(base_translation_map)
    translations = {
        str(row["ja"]): str(row["zh"])
        for row in translations_payload.get("translations", [])
    }
    manifests: dict[str, dict[str, Any]] = {}
    projections: dict[str, str] = {}
    source_occurrences = 0
    source_identities: set[str] = set()
    audio_occurrences = 0
    subtitle_occurrences = 0
    frame_count = 0
    excluded_bgm_ids: list[str] = []

    for event in EDITORIAL_ORDER:
        path = source_root / "events" / f"{event}.json"
        manifest = read_json(path)
        event_row = summary_events[event]
        quality = manifest.get("quality_gates", {})
        no_bgm = manifest.get("strict_no_bgm_sound_bus_contract", {})
        if (
            manifest.get("schema") != "magireco-event-production-v3"
            or manifest.get("event") != event
            or manifest.get("native_dimensions") != {"width": 416, "height": 232}
            or manifest.get("native_frame_rate") != "30/1"
            or quality.get("ready") is not True
            or quality.get("render_ready") is not True
            or quality.get("composition_resolved") is not True
            or quality.get("audio_timeline_ready") is not True
            or quality.get("event_global_z2d_timing_ready") is not True
            or quality.get("errors") != []
            or no_bgm.get("status") != "PASS"
            or set(no_bgm.get("included_buses", [])) != {"SE", "VOICE"}
            or no_bgm.get("excluded_buses") != ["BGM"]
        ):
            raise Ac1103ExhaustiveError(f"event readiness differs: {event}")
        if (
            event_row.get("ready") is not True
            or int(event_row.get("frame_count", -1)) != int(manifest["render_frame_count"])
            or str(event_row.get("sha256", "")).upper() != file_sha256(path)
        ):
            raise Ac1103ExhaustiveError(f"summary event binding differs: {event}")
        if event != "ac1103_013" and authority["events"][event].get("status") != "event_global_parent_scene_motion_exact":
            raise Ac1103ExhaustiveError(f"parent scene-motion authority differs: {event}")
        if event == "ac1103_013" and authority["events"][event].get("status") != "official_runtime_event_manifest_exact":
            raise Ac1103ExhaustiveError("ac1103_013 runtime authority differs")

        projection = presentation_projection(manifest)
        if projection in projections:
            raise Ac1103ExhaustiveError(
                f"complete presentation duplicated: {event}/{projections[projection]}"
            )
        projections[projection] = event
        manifests[event] = manifest
        frame_count += int(manifest["render_frame_count"])
        source_occurrences += len(manifest["clips"])
        source_identities.update(
            str(row["source_sha256"]).upper() for row in manifest["clips"]
        )
        audio_occurrences += len(manifest["audio"])
        subtitle_occurrences += len(manifest.get("subtitles", []))
        missing_translation = [
            row["text"]
            for row in manifest.get("subtitles", [])
            if str(row["text"]) not in translations
        ]
        if missing_translation:
            raise Ac1103ExhaustiveError(
                f"ZH translation coverage differs: {event}/{missing_translation!r}"
            )
        excluded_bgm_ids.extend(str(value) for value in no_bgm.get("excluded_bgm_request_ids", []))

    if (
        len(projections) != EXPECTED_EVENT_COUNT
        or frame_count != EXPECTED_FRAME_COUNT
        or source_occurrences != EXPECTED_SOURCE_OCCURRENCES
        or len(source_identities) != EXPECTED_UNIQUE_SOURCE_IDENTITIES
        or audio_occurrences != EXPECTED_RETAINED_AUDIO_OCCURRENCES
        or subtitle_occurrences != EXPECTED_SUBTITLE_OCCURRENCES
        or len(excluded_bgm_ids) != EXPECTED_EXCLUDED_BGM_OCCURRENCES
        or set(excluded_bgm_ids) != {"229"}
    ):
        raise Ac1103ExhaustiveError("bounded presentation/audio/source counts differ")
    if any(blocked in json.dumps(summary) for blocked in ("ac6003", "ac6004", "ac6005")):
        raise Ac1103ExhaustiveError("P16/P17/P18 leakage detected")

    return {
        "summary_path": summary_path,
        "authority_path": authority_path,
        "verification_path": verification_path,
        "summary": summary,
        "authority": authority,
        "routes": route_sequences,
        "manifests": manifests,
        "source_occurrences": source_occurrences,
        "unique_source_identities": len(source_identities),
        "audio_occurrences": audio_occurrences,
        "subtitle_occurrences": subtitle_occurrences,
        "frame_count": frame_count,
    }


def build_inputs(args: argparse.Namespace) -> dict[str, Path]:
    output_root = args.output_input_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"immutable input checkpoint already exists: {output_root}")
    source_root = args.source_manifest_root.resolve()
    validated = validate_source_checkpoint(source_root, args.base_translation_map.resolve())
    staging = output_root.parent / f".{output_root.name}.staging-{os.getpid()}"
    if staging.exists():
        raise FileExistsError(f"staging checkpoint already exists: {staging}")
    try:
        events_root = staging / "events"
        events_root.mkdir(parents=True)
        for event in EDITORIAL_ORDER:
            source_manifest = validated["manifests"][event]
            prepared_manifest = bind_exact_ac1103_013_audio_roles(source_manifest)
            write_json(events_root / f"{event}.json", prepared_manifest)

        source_series = {
            "schema": "magireco-series-editions-v1",
            "series": "ac1103",
            "status": "passed",
            "event_count": EXPECTED_EVENT_COUNT,
            "family_state": {"ready_event_names": list(EDITORIAL_ORDER)},
            "product_scopes": {event: PRODUCT_SCOPE for event in EDITORIAL_ORDER},
            "natural_session_claims": {event: False for event in EDITORIAL_ORDER},
            "ordering_evidence": (
                "31 exact DirInfo kind-55 rows reduce to 13 distinct complete event "
                "presentations. Entry, road, option, standard outcome and revival "
                "presentations are grouped editorially and each appears once."
            ),
            "fixed_native_session_gap_claimed": False,
        }
        source_series_path = staging / "source_series_catalogs" / "ac1103_exhaustive.json"
        write_json(source_series_path, source_series)

        series = {
            "schema": "magireco-ac1103-exhaustive-editorial-series-v1",
            "series": "ac1103_exhaustive",
            "status": "passed",
            "event_count": EXPECTED_EVENT_COUNT,
            "title_zh": "鹤乃外送修行 全入口·全选项·全结局完整合集",
            "event_sequence": list(EDITORIAL_ORDER),
            "ordering": "entry variants -> road variants -> option variants -> standard outcomes -> revival outcome",
            "product_scope": PRODUCT_SCOPE,
            "natural_session_claimed": False,
            "loop_scope": {
                "status": "every code-reachable distinct complete event presentation once",
                "fixed_inter_node_gap": False,
                "mutually_exclusive_routes_combined": True,
            },
            "family_state": {
                "production_manifest_root": str(output_root),
                "known_family_events": EXPECTED_EVENT_COUNT,
                "ready_family_events": EXPECTED_EVENT_COUNT,
                "not_ready_family_events": [],
                "ready_event_names": list(EDITORIAL_ORDER),
            },
            "event_manifest_sha256": {
                event: file_sha256(events_root / f"{event}.json") for event in EDITORIAL_ORDER
            },
            "source_series_manifest": {
                "path": str((output_root / source_series_path.relative_to(staging)).resolve()),
                "sha256": file_sha256(source_series_path),
                "evidence": "code-level 31-route/13-event exhaustive presentation authority",
            },
            "human_playback_required": True,
            "publication_approved": False,
        }
        series_path = staging / "series_proposals" / "ac1103_exhaustive.json"
        write_json(series_path, series)

        translation_payload = read_json(args.base_translation_map.resolve())
        translation_payload = dict(translation_payload)
        translation_payload["scope"] = "ac1103_exhaustive_event_presentations"
        translation_path = staging / "translations" / "ac1103_exhaustive_zh_v1.json"
        write_json(translation_path, translation_payload)

        authority = {
            "schema": "magireco-ac1103-exhaustive-editorial-order-authority-v1",
            "status": "PASS_READY_FOR_RENDER",
            "family": "ac1103",
            "native_dimensions": {"width": 416, "height": 232},
            "frame_rate": "30/1",
            "route_universe": {
                "route_count": EXPECTED_ROUTE_COUNT,
                "routes": {str(key): list(value) for key, value in validated["routes"].items()},
                "all_routes_reconstructable": True,
            },
            "presentation_universe": {
                "complete_event_presentation_count": EXPECTED_EVENT_COUNT,
                "unique_complete_presentation_count": EXPECTED_EVENT_COUNT,
                "ordered_events": list(EDITORIAL_ORDER),
                "each_complete_presentation_once": True,
                "raw_visual_source_occurrence_count": validated["source_occurrences"],
                "raw_visual_unique_identity_count": validated["unique_source_identities"],
                "raw_visual_alias_surplus_count": validated["source_occurrences"] - validated["unique_source_identities"],
                "dedupe_unit": "complete_visual_audio_subtitle_presentation",
                "raw_source_aliases_preserved_as_evidence": True,
            },
            "closed_gates": {
                "dirinfo_route_universe": "CLOSED_31_OF_31",
                "event_global_parent_child_timing": "CLOSED_13_OF_13",
                "strict_no_bgm_sound_bus": "CLOSED_REQUEST_229_EXCLUDED_IN_012_AND_013",
                "ac1103_013_renderer_audio_role_schema": "CLOSED_BY_HASH_BOUND_NORMALIZATION",
                "duplicate_free_editorial_order": "CLOSED_13_OF_13_UNIQUE",
            },
            "decision": {
                "legacy_short_route_fragments_are_final_products": False,
                "legacy_ac1103_013_18s_is_final_product": False,
                "legacy_ac1103_013_18s_role": "chapter_evidence_only",
                "new_exhaustive_render_allowed": True,
                "human_playback_required": True,
            },
            "source_authority": snapshot(validated["authority_path"]),
            "source_media_modified": False,
        }
        authority_path = staging / "AC1103_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
        write_json(authority_path, authority)

        bindings = {
            "schema": "magireco-ac1103-exhaustive-input-bindings-v1",
            "status": "PASS",
            "bindings": [
                snapshot(validated["summary_path"]),
                snapshot(validated["authority_path"]),
                snapshot(validated["verification_path"]),
                snapshot(args.base_translation_map.resolve()),
            ],
            "source_media_modified": False,
        }
        write_json(staging / "SOURCE_BINDINGS.json", bindings)

        verification_record = {
            "schema": "magireco-ac1103-exhaustive-input-verification-v1",
            "status": "PASS_READY_FOR_RENDER",
            "checks": {
                "dirinfo_routes": EXPECTED_ROUTE_COUNT,
                "complete_event_presentations": EXPECTED_EVENT_COUNT,
                "unique_complete_presentations": EXPECTED_EVENT_COUNT,
                "editorial_frame_count": validated["frame_count"],
                "visual_source_occurrences": validated["source_occurrences"],
                "visual_unique_source_identities": validated["unique_source_identities"],
                "retained_no_bgm_audio_occurrences": validated["audio_occurrences"],
                "subtitle_occurrences": validated["subtitle_occurrences"],
                "excluded_bgm_request_ids": ["229"],
                "excluded_bgm_occurrences": EXPECTED_EXCLUDED_BGM_OCCURRENCES,
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
        write_json(staging / "VERIFICATION_RECORD.json", verification_record)
        (staging / "README.md").write_text(
            "# ac1103 exhaustive authoritative longform inputs\n\n"
            "All 31 DirInfo rows are represented by 13 distinct complete event presentations. "
            "Each appears once in an editorial longform; the former 18-second ac1103_013 "
            "standalone is retained only as chapter evidence. Human playback is required.\n",
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
        "series_path": output_root / "series_proposals" / "ac1103_exhaustive.json",
        "translation_path": output_root / "translations" / "ac1103_exhaustive_zh_v1.json",
    }


def load_existing_inputs(output_root: Path) -> dict[str, Path]:
    output_root = output_root.resolve()
    verification = read_json(output_root / "VERIFICATION_RECORD.json")
    authority = read_json(output_root / "AC1103_EXHAUSTIVE_EDITORIAL_AUTHORITY.json")
    series_path = output_root / "series_proposals" / "ac1103_exhaustive.json"
    translation_path = output_root / "translations" / "ac1103_exhaustive_zh_v1.json"
    series = read_json(series_path)
    if (
        verification.get("status") != "PASS_READY_FOR_RENDER"
        or verification.get("checks", {}).get("unique_complete_presentations") != EXPECTED_EVENT_COUNT
        or authority.get("status") != "PASS_READY_FOR_RENDER"
        or authority.get("decision", {}).get("new_exhaustive_render_allowed") is not True
        or series.get("event_sequence") != list(EDITORIAL_ORDER)
        or not translation_path.is_file()
    ):
        raise Ac1103ExhaustiveError("existing ac1103 input checkpoint differs")
    return {
        "output_root": output_root,
        "series_path": series_path,
        "translation_path": translation_path,
    }


def probe_media(path: Path, ffprobe: str) -> dict[str, Any]:
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
    family = production_root / "ac1103_exhaustive_full_no_bgm_editions_v1"
    manifest = read_json(family / "manifests" / "family_editions_manifest.json")
    qa = read_json(family / "qa" / "automated_qa.json")
    if (
        manifest.get("ordered_events") != list(EDITORIAL_ORDER)
        or manifest.get("audio_profile") != "no_bgm"
        or qa.get("checks", {}).get("no_exact_duplicate_audience_events") is not True
        or qa.get("status") not in {"passed", "AUTOMATED_QA_PASSED"}
    ):
        raise Ac1103ExhaustiveError("produced family manifest/QA differs")
    media_rows: list[dict[str, Any]] = []
    for edition in ("none", "ja", "zh"):
        path = family / "video" / f"ac1103_exhaustive_full_no_bgm_editions_v1__{edition}.mp4"
        probe = probe_media(path, ffprobe)
        video = [row for row in probe["streams"] if row["codec_type"] == "video"]
        audio = [row for row in probe["streams"] if row["codec_type"] == "audio"]
        if (
            len(video) != 1
            or len(audio) != 1
            or video[0].get("codec_name") != "h264"
            or (int(video[0].get("width", 0)), int(video[0].get("height", 0))) != (416, 232)
            or video[0].get("r_frame_rate") != "30/1"
            or int(video[0].get("nb_read_frames", -1)) != EXPECTED_FRAME_COUNT
            or audio[0].get("codec_name") != "aac"
            or int(audio[0].get("sample_rate", 0)) != 48000
            or int(audio[0].get("channels", 0)) != 2
        ):
            raise Ac1103ExhaustiveError(f"media signature differs: {path}")
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
    durations = [row["duration_seconds"] for row in media_rows]
    if max(durations) - min(durations) > 0.001:
        raise Ac1103ExhaustiveError("edition container durations differ")
    report = {
        "schema": "magireco-ac1103-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "ordered_complete_event_presentations": EXPECTED_EVENT_COUNT,
        "exact_duplicate_complete_presentation_count": 0,
        "dirinfo_route_coverage": "31/31",
        "legacy_ac1103_013_18s_standalone_role": "chapter_evidence_only",
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
        f"ac1103_exhaustive={inputs['series_path']}",
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
    parser.add_argument("--source-manifest-root", required=True, type=Path)
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
    parser.add_argument("--verify-existing-production", action="store_true")
    parser.add_argument("--reuse-inputs", action="store_true")
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
            "visual_sources=35 audio_gate=CLOSED timing_gate=CLOSED "
            f"inputs={inputs['output_root']}"
        )
    if args.render:
        report = render(args, inputs)
        media = report["media"]
        print(
            f"PASS_RENDER editions=3 frames={media[0]['frame_count']} "
            f"duration={media[0]['duration_seconds']:.3f}s production={args.production_root.resolve()}"
        )
    elif args.verify_existing_production:
        report = verify_production(args.production_root.resolve(), args.ffprobe)
        media = report["media"]
        print(
            f"PASS_VERIFY_EXISTING editions=3 frames={media[0]['frame_count']} "
            f"duration={media[0]['duration_seconds']:.3f}s production={args.production_root.resolve()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
