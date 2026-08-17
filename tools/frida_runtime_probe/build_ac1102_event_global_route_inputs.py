#!/usr/bin/env python3
"""Build event-global ac1102 manifests and sixteen bounded route inputs.

The Slot scheduler stores one DirInfo event per target stage.  It does not
define a fixed wall-clock gap between stages.  These outputs therefore preserve
each selected event occurrence through its complete verified visual/VOICE/SE
tail and order the occurrences by one exact DirInfo row.  They are review route
archives, not claims of a captured single native session.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

try:
    from tools.frida_runtime_probe.build_ac7101_ac7107_timing_authority import (
        binding,
        one,
        read_json,
        round_frame_ms,
        walk,
        write_json,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_ac7101_ac7107_timing_authority import (
        binding,
        one,
        read_json,
        round_frame_ms,
        walk,
        write_json,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
STATIC_ROOT = RESEARCH_ROOT / "ida_static_scheduler_analysis_v1_20260808"
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_ac1102_story_scene_motion_v77_20260818"
SOURCE_MANIFEST_ROOT = (
    RESEARCH_ROOT
    / "production_manifests_v68_ac0911_011_audio_repair_20260806"
    / "events"
)
SOUND_BUS_AUDIT = (
    STATIC_ROOT
    / "sound_divide_manifest_audit_v1b_20260810"
    / "final"
    / "EVENT_SOUND_BUS_AUDIT.csv"
)
DIRINFO_ROUTES = Path(
    r"D:\magia\MyProducts\casino\runtime_recovery_20260703"
    r"\dirinfo_event_table_decode_v3_20260703\dirinfo_event_routes.csv"
)
DEFAULT_OUTPUT_ROOT = RESEARCH_ROOT / "ac1102_event_global_route_inputs_v1_20260818"
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)

BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"
EVENT_CODES = {
    "ac1102_001": "0x2f477450382b2f63",
    "ac1102_002": "0x4d35373f382b2f63",
    "ac1102_003": "0x59324b6f382b2f63",
    "ac1102_004": "0x56633371382b2f63",
    "ac1102_005": "0x72616c68382b2f63",
    "ac1102_006": "0x2b306f49382b2f63",
    "ac1102_008": "0x3025622f382b2f63",
    "ac1102_009": "0x59654d6e382b2f63",
    "ac1102_010": "0x3437696f382b2f63",
    "ac1102_011": "0x5023704a382b2f63",
    "ac1102_012": "0x48246643382b2f63",
}
EVENTS = tuple(EVENT_CODES)
EXPECTED_REQUESTS = {
    "ac1102_001": ("4021", "8370", "4024"),
    "ac1102_002": ("2667", "4026"),
    "ac1102_003": ("4027", "4028"),
    "ac1102_004": ("4030", "4027", "4028"),
    "ac1102_005": ("4034", "4035"),
    "ac1102_006": ("4039", "4040"),
    "ac1102_008": ("4031", "4035"),
    "ac1102_009": ("4021", "8370", "4024"),
    "ac1102_010": ("4021", "8374", "4024"),
    "ac1102_011": ("4021", "8374", "4024"),
    "ac1102_012": ("4032",),
}
EXPECTED_EFFECT_SCENES = {
    "ac1102_003": ("TUDUKU",),
    "ac1102_004": ("TUDUKU_CU",),
    "ac1102_006": ("ANTEN",),
}
ROUTES = {
    0: ("ac1102_001", "ac1102_002", "ac1102_003"),
    1: ("ac1102_001", "ac1102_002", "ac1102_004"),
    2: ("ac1102_001", "ac1102_002", "ac1102_005", "ac1102_006"),
    4: ("ac1102_001", "ac1102_002", "ac1102_008", "ac1102_006"),
    6: ("ac1102_009", "ac1102_002", "ac1102_003"),
    7: ("ac1102_009", "ac1102_002", "ac1102_004"),
    8: ("ac1102_009", "ac1102_002", "ac1102_005", "ac1102_006"),
    10: ("ac1102_009", "ac1102_002", "ac1102_008", "ac1102_006"),
    12: ("ac1102_010", "ac1102_002", "ac1102_003"),
    13: ("ac1102_010", "ac1102_002", "ac1102_004"),
    14: ("ac1102_010", "ac1102_002", "ac1102_005", "ac1102_006"),
    16: ("ac1102_010", "ac1102_002", "ac1102_008", "ac1102_006"),
    18: ("ac1102_011", "ac1102_002", "ac1102_003"),
    19: ("ac1102_011", "ac1102_002", "ac1102_004"),
    20: ("ac1102_011", "ac1102_002", "ac1102_005", "ac1102_006"),
    22: ("ac1102_011", "ac1102_002", "ac1102_008", "ac1102_006"),
}
ROUTE_TITLES = {
    0: "菲利希亚牧场 白标题·回避路线",
    1: "菲利希亚牧场 白标题·回避CU路线",
    2: "菲利希亚牧场 白标题·压制失败路线",
    4: "菲利希亚牧场 白标题·压制CU失败路线",
    6: "菲利希亚牧场 红标题·回避路线",
    7: "菲利希亚牧场 红标题·回避CU路线",
    8: "菲利希亚牧场 红标题·压制失败路线",
    10: "菲利希亚牧场 红标题·压制CU失败路线",
    12: "菲利希亚牧场 黑江加入白标题·回避路线",
    13: "菲利希亚牧场 黑江加入白标题·回避CU路线",
    14: "菲利希亚牧场 黑江加入白标题·压制失败路线",
    16: "菲利希亚牧场 黑江加入白标题·压制CU失败路线",
    18: "菲利希亚牧场 黑江加入红标题·回避路线",
    19: "菲利希亚牧场 黑江加入红标题·回避CU路线",
    20: "菲利希亚牧场 黑江加入红标题·压制失败路线",
    22: "菲利希亚牧场 黑江加入红标题·压制CU失败路线",
}
LOCK_FRAMES = {
    "ac1102_001": 0,
    "ac1102_002": 0,
    "ac1102_003": 0,
    "ac1102_004": 0,
    "ac1102_005": 80,
    "ac1102_006": 0,
    "ac1102_008": 85,
    "ac1102_009": 0,
    "ac1102_010": 0,
    "ac1102_011": 0,
    "ac1102_012": 0,
}
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Summary = Join-Path $Root 'SUMMARY.json'
if (-not (Test-Path -LiteralPath $Summary)) { throw 'ac1102 route input summary missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable ac1102 route inputs can be disabled by same-volume rename; source manifests and media remain untouched.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def final_binding(staged: Path, final: Path) -> dict[str, Any]:
    row = binding(staged)
    row["path"] = str(final.resolve())
    return row


def validate_dirinfo(rows: list[dict[str, str]]) -> dict[str, Any]:
    selected = [row for row in rows if int(row["kind"]) == 54]
    grouped: dict[int, list[dict[str, str]]] = {}
    for row in selected:
        grouped.setdefault(int(row["row_index"]), []).append(row)
    if set(grouped) != set(range(31)):
        raise ValueError("ac1102 DirInfo row set differs")
    resolved: dict[int, tuple[str, ...]] = {}
    blocked: dict[int, dict[str, Any]] = {}
    for row_index, values in grouped.items():
        values.sort(key=lambda row: int(row["selector_raw"]))
        scene_names = tuple(row["scene_name"] for row in values)
        missing = tuple(
            row["scene_name"]
            for row in values
            if int(row["resolved_source_count"]) == 0
        )
        if missing:
            blocked[row_index] = {
                "events": list(scene_names),
                "missing_sources": list(missing),
                "reason": "one_or_more_dirinfo_events_have_no_resolved_source",
            }
        else:
            resolved[row_index] = scene_names
    if resolved != ROUTES:
        raise ValueError(f"ac1102 source-resolved route set differs: {resolved}")
    if set(blocked) != set(range(31)) - set(ROUTES):
        raise ValueError("ac1102 blocked route set differs")
    return {
        "kind": 54,
        "source_resolved_routes": {str(key): list(value) for key, value in ROUTES.items()},
        "blocked_routes": {str(key): value for key, value in blocked.items()},
    }


def validate_runtime(runtime: Mapping[str, Any], lockframes: Mapping[str, Any]) -> None:
    if (
        runtime.get("schema") != "magireco-ac1102-runtime-scene-motion-v1"
        or runtime.get("host_frida_version") != "17.16.4"
        or runtime.get("protected_processes_unchanged") is not True
        or runtime.get("crash_tail_empty") is not True
        or tuple(runtime.get("requested_events", {})) != EVENTS
        or set(runtime.get("events", {})) != set(EVENTS)
    ):
        raise ValueError("bounded ac1102 scene capture differs")
    if (
        lockframes.get("schema") != "magireco-ac1102-runtime-lockframe-v1"
        or lockframes.get("host_frida_version") != "17.16.4"
        or lockframes.get("protected_processes_unchanged") is not True
        or lockframes.get("crash_tail_empty") is not True
        or set(lockframes.get("events", {})) != set(EVENTS)
        or {
            event: int(row["lock_frame"])
            for event, row in lockframes["events"].items()
        }
        != LOCK_FRAMES
    ):
        raise ValueError("bounded ac1102 LockFrame capture differs")


def find_motion_context(runtime_event: Mapping[str, Any], event: str) -> tuple[dict[str, tuple[dict, dict, str]], dict, list[dict]]:
    scene = one(
        runtime_event.get("scenes", []),
        lambda row: row.get("name") == event,
        f"{event} main scene",
    )
    cut = one(
        scene.get("cuts", []),
        lambda row: row.get("cut_name") == event,
        f"{event} main cut",
    )
    if cut.get("instance_offset_frames") != 0 or cut.get("cut_start_frame") != 0:
        raise ValueError(f"{event}: main cut is not event-global frame zero")
    effects = [row for row in runtime_event.get("scenes", []) if row is not scene]
    if tuple(row.get("name") for row in effects) != EXPECTED_EFFECT_SCENES.get(event, ()):
        raise ValueError(f"{event}: effect-scene set differs")
    context: dict[str, tuple[dict, dict, str]] = {}
    for top in cut.get("nodes", []):
        layer = one(
            runtime_event.get("layers", []),
            lambda row, top=top: (row.get("hash_low"), row.get("hash_high"))
            == (top.get("hash_low"), top.get("hash_high")),
            f"{event}/{top.get('name')} layer",
        )
        if float(layer.get("speed", 0)) != 1.0:
            raise ValueError(f"{event}/{top.get('name')}: layer speed differs")
        for node in walk(top):
            name = str(node.get("name", ""))
            if not name.endswith(".z2d"):
                continue
            key = name[:-4]
            if key in context:
                raise ValueError(f"{event}/{key}: duplicate runtime Z2D node")
            context[key] = (node, layer, str(top.get("name", "")))
    return context, cut, effects


def exact_key(context: Mapping[str, tuple[dict, dict, str]], event: str, z2d_name: str) -> tuple[dict, dict, str]:
    if z2d_name not in context:
        raise ValueError(f"{event}/{z2d_name}: runtime Z2D node missing")
    node, layer, layer_name = context[z2d_name]
    if node.get("time_remap_pointer") is not None:
        raise ValueError(f"{event}/{z2d_name}: time remap is active")
    motion = one(
        node.get("motions", []),
        lambda row: row.get("is_z2d_motion") is True,
        f"{event}/{z2d_name} Z2D motion",
    )
    key = one(
        motion.get("keys", []),
        lambda row: row.get("index") == 0,
        f"{event}/{z2d_name} motion key zero",
    )
    return key, layer, layer_name


def extract_event_authority(
    event: str,
    runtime_event: Mapping[str, Any],
    manifest: Mapping[str, Any],
    sound_rows: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        str(runtime_event.get("event_code", "")).lower() != EVENT_CODES[event]
        or str(manifest.get("event_code_hex", "")).lower() != EVENT_CODES[event]
        or manifest.get("native_dimensions") != {"width": 416, "height": 232}
        or manifest.get("native_frame_rate") != "30/1"
    ):
        raise ValueError(f"{event}: identity or native media contract differs")
    gates = manifest.get("quality_gates", {})
    if (
        gates.get("errors") != [BLOCKER]
        or gates.get("event_global_z2d_timing_ready") is not False
        or gates.get("composition_resolved") is not True
        or gates.get("ready") is not False
    ):
        raise ValueError(f"{event}: source fail-closed state differs")

    audio = list(manifest.get("audio", []))
    voice_rows = [row for row in audio if row.get("source") == "z2d_req_sound"]
    if tuple(str(row.get("request_id", "")) for row in voice_rows) != EXPECTED_REQUESTS[event]:
        raise ValueError(f"{event}: expected VOICE request set differs")
    audit = {
        row["request_id"]: row for row in sound_rows if row.get("event") == event
    }
    if set(audit) != {str(row.get("request_id", "")) for row in audio}:
        raise ValueError(f"{event}: SOUND_DIVIDE_TBL request coverage differs")
    for row in audio:
        request_id = str(row["request_id"])
        expected_bus = "VOICE" if row.get("source") == "z2d_req_sound" else "SE"
        if (
            audit[request_id].get("volume_bus") != expected_bus
            or audit[request_id].get("strict_no_bgm_disposition") != "NOT_BGM_BUS"
            or audit[request_id].get("code_name") != row.get("code_name")
            or audit[request_id].get("ogg_name") != row.get("ogg_name")
        ):
            raise ValueError(f"{event}/{request_id}: sound-bus identity differs")

    context, cut, effects = find_motion_context(runtime_event, event)
    subtitle_by_key = {
        (str(row.get("voice_request_id", "")), str(row.get("z2d_name", ""))): row
        for row in manifest.get("subtitles", [])
    }
    if len(subtitle_by_key) != len(manifest.get("subtitles", [])):
        raise ValueError(f"{event}: duplicate subtitle request/Z2D key")
    cues: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for row in voice_rows:
        request_id = str(row["request_id"])
        z2d_name = str(row["z2d_name"])
        key, layer, layer_name = exact_key(context, event, z2d_name)
        start_frame = int(key["floats"][0])
        if (
            row.get("event_global_start_resolved") is not False
            or int(row.get("start_ms", -1)) != round_frame_ms(start_frame)
            or int(float(row.get("absolute_start_frame", -1))) != start_frame
        ):
            raise ValueError(f"{event}/{request_id}: child-local start differs")
        subtitle = subtitle_by_key.get((request_id, z2d_name))
        if subtitle is None:
            raise ValueError(f"{event}/{request_id}: subtitle request is missing")
        cue = {
            "request_id": request_id,
            "z2d_name": z2d_name,
            "event_global_start_frame": start_frame,
            "event_global_start_ms": round_frame_ms(start_frame),
        }
        if subtitle.get("subtitle_source") == "graphical_display_text":
            end_frame = int(key["floats"][1]) + 1
            cue["event_global_end_frame_exclusive"] = end_frame
            cue["event_global_end_ms"] = round_frame_ms(end_frame)
            if int(subtitle.get("end_ms", -1)) != cue["event_global_end_ms"]:
                raise ValueError(f"{event}/{request_id}: graphical end differs")
        cues.append(cue)
        evidence.append(
            {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "motion_fields": key["floats"],
                "motion_flags": key["flags"],
                "layer_name": layer_name,
                "layer_speed": layer["speed"],
                "event_global_start_frame": start_frame,
            }
        )

    content_end_ms = max(
        [int(manifest.get("video_duration_ms", 0))]
        + [int(row.get("start_ms", 0)) + int(row.get("duration_ms", 0)) for row in audio]
    )
    expected_frames = (content_end_ms * 30 + 999) // 1000
    if (
        int(manifest.get("render_frame_count", -1)) != expected_frames
        or int(manifest.get("render_duration_quantization", {}).get("frame_count", -1))
        != expected_frames
    ):
        raise ValueError(f"{event}: complete occurrence frame boundary differs")

    return (
        {
            "status": "event_global_parent_scene_motion_exact",
            "event_code_hex": EVENT_CODES[event],
            "parent_cut": {
                "scene": event,
                "cut": event,
                "instance_offset_frames": 0,
                "cut_start_frame": 0,
                "cut_end_frame": cut.get("cut_end_frame"),
            },
            "lock_frame": LOCK_FRAMES[event],
            "lock_frame_role": "target_replacement_guard_not_universal_event_duration",
            "archive_content_end_ms": content_end_ms,
            "archive_frame_count": expected_frames,
            "archive_boundary": "ceil(max(verified visual timeline end, retained VOICE/SE tail) to complete 30 fps frame)",
            "excluded_effect_scenes": [
                {
                    "name": row["name"],
                    "reason": "separate gameplay/effect layer; excluded from clean story route",
                }
                for row in effects
            ],
            "caption_motion_evidence": evidence,
            "sound_bus_contract": "SE plus VOICE only; zero BGM-bus rows",
        },
        {
            "schema": "magireco-z2d-event-timing-override-v1",
            "event": event,
            "event_code_hex": EVENT_CODES[event],
            "frame_rate": "30/1",
            "expected_z2d_request_ids": list(EXPECTED_REQUESTS[event]),
            "cues": cues,
        },
    )


def timing_snapshot(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "audio": [
            {
                "request_id": str(row.get("request_id", "")),
                "start_ms": int(row.get("start_ms", -1)),
            }
            for row in manifest.get("audio", [])
            if row.get("source") == "z2d_req_sound"
        ],
        "subtitles": [
            {
                "request_id": str(row.get("voice_request_id", "")),
                "start_ms": int(row.get("start_ms", -1)),
                "end_ms": int(row.get("end_ms", -1)),
                "subtitle_source": str(row.get("subtitle_source", "")),
            }
            for row in manifest.get("subtitles", [])
        ],
    }


def annotate_speakers(manifest: dict[str, Any]) -> list[dict[str, str]]:
    event = str(manifest["event"])
    audio = {
        str(row["request_id"]): row
        for row in manifest.get("audio", [])
        if row.get("source") == "z2d_req_sound"
    }
    applied: list[dict[str, str]] = []
    for row in manifest.get("subtitles", []):
        request_id = str(row.get("voice_request_id", ""))
        voice = audio.get(request_id)
        if voice is None:
            raise ValueError(f"{event}/{request_id}: subtitle lacks VOICE row")
        parts = str(voice.get("code_name", "")).split("_", 3)
        if len(parts) != 4 or not parts[1]:
            raise ValueError(f"{event}/{request_id}: official speaker token missing")
        token = "multiple" if parts[1] == "mix" else parts[1]
        existing = str(row.get("speaker_code", ""))
        if existing and existing != token:
            raise ValueError(f"{event}/{request_id}: speaker token conflicts")
        row["speaker_code"] = token
        row["speaker_identity_evidence"] = "exact_official_voice_request_code_name_speaker_token"
        applied.append(
            {
                "event": event,
                "request_id": request_id,
                "speaker_code": token,
                "code_name": str(voice["code_name"]),
            }
        )
    return applied


def repair_manifest(source: Mapping[str, Any], override: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = copy.deepcopy(source)
    event = str(manifest.get("event", ""))
    if event not in EVENTS:
        raise ValueError(f"unexpected ac1102 event: {event}")
    gates = manifest.get("quality_gates", {})
    if (
        gates.get("errors") != [BLOCKER]
        or gates.get("ready") is not False
        or gates.get("event_global_z2d_timing_ready") is not False
        or gates.get("composition_resolved") is not True
        or gates.get("video_composition_model")
        not in {"linear_full_frame_sequence", "timed_full_frame_layers"}
        or Fraction(str(manifest.get("native_frame_rate"))) != Fraction(30, 1)
    ):
        raise ValueError(f"{event}: replacement source contract differs")
    before = timing_snapshot(manifest)
    application = apply_z2d_event_timing_override(
        manifest.get("audio", []), manifest.get("subtitles", []), override
    )
    if (
        application["unmatched_cues"]
        or application["recovery_conflicts"]
        or not application["request_set_matches"]
        or application["matched_audio_cue_count"] != len(EXPECTED_REQUESTS[event])
        or application["matched_subtitle_cue_count"] != len(manifest.get("subtitles", []))
    ):
        raise ValueError(f"{event}: timing override application differs")
    after = timing_snapshot(manifest)
    if [row["start_ms"] for row in before["audio"]] != [row["start_ms"] for row in after["audio"]]:
        raise ValueError(f"{event}: audio start unexpectedly changed")
    if [row["start_ms"] for row in before["subtitles"]] != [row["start_ms"] for row in after["subtitles"]]:
        raise ValueError(f"{event}: subtitle start unexpectedly changed")
    speaker_rows = annotate_speakers(manifest)
    unresolved = [
        row
        for row in [*manifest.get("audio", []), *manifest.get("subtitles", [])]
        if (
            row.get("source") == "z2d_req_sound"
            or row.get("subtitle_source")
            in {"graphical_display_text", "official_voice_label", "official_voice_asr_verified"}
        )
        and row.get("event_global_start_resolved") is not True
    ]
    if unresolved:
        raise ValueError(f"{event}: child-local timing remains")
    gates["errors"] = []
    gates["all_audio_exist"] = True
    gates["event_global_z2d_timing_ready"] = True
    gates["audio_timeline_ready"] = True
    gates["render_ready"] = True
    gates["ready"] = True
    manifest["z2d_event_timing_override_application"] = application
    manifest["strict_no_bgm_sound_bus_contract"] = {
        "status": "PASS",
        "included_buses": ["SE", "VOICE"],
        "excluded_buses": ["BGM"],
        "bgm_bus_row_count": 0,
        "evidence": "bound SOUND_DIVIDE_TBL audit in ac1102 route authority",
    }
    return manifest, {"application": application, "speaker_rows": speaker_rows}


def verify_output(output_dir: Path) -> dict[str, Any]:
    summary = read_json(output_dir / "SUMMARY.json")
    if (
        summary.get("schema") != "magireco-ac1102-event-global-route-inputs-v1"
        or summary.get("status") != "PASS"
        or summary.get("event_count") != len(EVENTS)
        or summary.get("route_count") != len(ROUTES)
        or summary.get("human_playback_required") is not True
        or summary.get("publication_approved") is not False
    ):
        raise ValueError("ac1102 route input summary differs")
    for row in summary["events"]:
        path = output_dir / row["relative_path"]
        if file_sha256(path) != row["sha256"]:
            raise ValueError(f"{row['event']}: replacement manifest binding differs")
        manifest = read_json(path)
        if manifest.get("quality_gates", {}).get("ready") is not True:
            raise ValueError(f"{row['event']}: replacement manifest is not READY")
    for row in summary["routes"]:
        for key in ("source_series", "series_proposal"):
            path = output_dir / row[f"{key}_relative_path"]
            if file_sha256(path) != row[f"{key}_sha256"]:
                raise ValueError(f"route {row['row_index']}: {key} binding differs")
    override_paths = [
        output_dir / "timing_overrides" / f"{event}_parent_scene_motion_key_v1.json"
        for event in EVENTS
    ]
    loaded_overrides = load_z2d_event_timing_overrides(override_paths)
    if set(loaded_overrides) != set(EVENTS):
        raise ValueError("published ac1102 timing override set differs")
    return {
        "schema": "magireco-ac1102-event-global-route-inputs-verification-v1",
        "result": "PASS",
        "event_count": len(EVENTS),
        "route_count": len(ROUTES),
        "blocked_route_count": 31 - len(ROUTES),
        "native_dimensions": "416x232",
        "native_frame_rate": "30/1",
        "audio_profile": "strict_no_bgm",
        "fixed_native_session_gap_claimed": False,
        "human_playback_required": True,
        "publication_approved": False,
        "source_media_modified": False,
    }


def build(output_dir: Path, override_dir: Path) -> None:
    if output_dir.exists():
        raise ValueError(f"immutable ac1102 route input root exists: {output_dir}")
    override_dir.mkdir(parents=True, exist_ok=True)
    override_targets = {
        event: override_dir / f"{event}_parent_scene_motion_key_v1.json"
        for event in EVENTS
    }
    if any(path.exists() for path in override_targets.values()):
        raise ValueError("one or more ac1102 timing override targets already exist")

    staging = output_dir.with_name(f".{output_dir.name}.staging-{uuid.uuid4().hex}")
    staging.mkdir(parents=True)
    try:
        sources = {
            "exact_libgameproc": STATIC_ROOT / "sample" / "libGameProc.so",
            "ida_parent_child": STATIC_ROOT / "parent_child_timing_authority_v1_20260815" / "IDA_PARENT_CHILD_PSEUDOCODE.json",
            "ida_z2d_motion_fields": STATIC_ROOT / "parent_child_timing_authority_v1_20260815" / "IDA_Z2D_MOTION_FIELDS.json",
            "ida_ac1102_scheduler": RUNTIME_ROOT / "IDA_AC1102_DIRINFO_PLAYBACK_MECHANISM.json",
            "runtime_scene_motion": RUNTIME_ROOT / "AC1102_RUNTIME_SCENE_MOTION.json",
            "runtime_lockframes": RUNTIME_ROOT / "AC1102_RUNTIME_LOCKFRAME.json",
            "runtime_scene_script": RUNTIME_ROOT / "inspect_event_scene_motion.js",
            "runtime_lockframe_script": RUNTIME_ROOT / "inspect_event_lockframe.js",
            "sound_bus_audit": SOUND_BUS_AUDIT,
            "dirinfo_routes": DIRINFO_ROUTES,
        }
        for event in EVENTS:
            sources[f"source_manifest_{event}"] = SOURCE_MANIFEST_ROOT / f"{event}.json"
        bindings = {name: binding(path) for name, path in sources.items()}
        if bindings["exact_libgameproc"]["sha256"] != "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF":
            raise ValueError("exact Slot libGameProc binding differs")

        runtime = read_json(sources["runtime_scene_motion"])
        lockframes = read_json(sources["runtime_lockframes"])
        validate_runtime(runtime, lockframes)
        dirinfo = validate_dirinfo(read_csv(sources["dirinfo_routes"]))
        sound_rows = read_csv(sources["sound_bus_audit"])

        authorities: dict[str, Any] = {}
        override_payloads: dict[str, Any] = {}
        for event in EVENTS:
            authorities[event], override_payloads[event] = extract_event_authority(
                event,
                runtime["events"][event],
                read_json(sources[f"source_manifest_{event}"]),
                sound_rows,
            )

        authority_path = staging / "AC1102_EVENT_GLOBAL_ROUTE_AUTHORITY.json"
        write_json(
            authority_path,
            {
                "schema": "magireco-ac1102-event-global-route-authority-v1",
                "status": "PASS",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "events": authorities,
                "dirinfo": dirinfo,
                "scheduler_conclusion": "DirInfo entries are target-stage progression nodes; no universal fixed inter-node wall-clock gap exists.",
                "product_scope": "sixteen edited full-occurrence clean-story route archives ordered by exact DirInfo rows",
                "source_bindings": bindings,
                "human_playback_required": True,
                "publication_approved": False,
                "source_media_modified": False,
            },
        )
        authority_binding = final_binding(
            authority_path, output_dir / authority_path.name
        )

        staged_overrides = staging / "timing_overrides"
        staged_overrides.mkdir()
        validation_overrides = staging / ".validation_overrides"
        validation_overrides.mkdir()
        for event, payload in override_payloads.items():
            payload["authority_path"] = authority_binding["path"]
            payload["source_bindings"] = [
                authority_binding,
                bindings["exact_libgameproc"],
                bindings["ida_parent_child"],
                bindings["ida_z2d_motion_fields"],
                bindings["ida_ac1102_scheduler"],
                bindings["runtime_scene_motion"],
                bindings["runtime_lockframes"],
                bindings["sound_bus_audit"],
                bindings["dirinfo_routes"],
                bindings[f"source_manifest_{event}"],
            ]
            write_json(staged_overrides / override_targets[event].name, payload)

            validation_payload = copy.deepcopy(payload)
            staging_authority_binding = binding(authority_path)
            validation_payload["authority_path"] = staging_authority_binding["path"]
            validation_payload["source_bindings"][0] = staging_authority_binding
            write_json(
                validation_overrides / override_targets[event].name,
                validation_payload,
            )

        loaded_overrides = load_z2d_event_timing_overrides(
            [validation_overrides / override_targets[event].name for event in EVENTS]
        )
        for event in EVENTS:
            final_override_path = override_targets[event].resolve()
            published_payload = read_json(
                staged_overrides / override_targets[event].name
            )
            loaded_overrides[event]["_source_path"] = str(final_override_path)
            loaded_overrides[event]["_source_sha256"] = file_sha256(
                staged_overrides / override_targets[event].name
            )
            loaded_overrides[event]["authority_path"] = published_payload[
                "authority_path"
            ]
            loaded_overrides[event]["source_bindings"] = published_payload[
                "source_bindings"
            ]
        shutil.rmtree(validation_overrides)
        event_dir = staging / "events"
        event_dir.mkdir()
        event_rows = []
        for event in EVENTS:
            source_path = sources[f"source_manifest_{event}"]
            repaired, repair = repair_manifest(
                read_json(source_path), loaded_overrides[event]
            )
            repaired["timing_repair_provenance"] = {
                "source_manifest": bindings[f"source_manifest_{event}"],
                "timing_authority": authority_binding,
                "audio_start_timing_changed": False,
                "request_bound_speaker_identity_ready": True,
                "source_media_modified": False,
                **repair,
            }
            path = event_dir / f"{event}.json"
            write_json(path, repaired)
            event_rows.append(
                {
                    "event": event,
                    "relative_path": f"events/{event}.json",
                    "sha256": file_sha256(path),
                    "frame_count": int(repaired["render_frame_count"]),
                    "ready": True,
                }
            )

        catalogs = staging / "source_series_catalogs"
        proposals = staging / "route_series_proposals"
        catalogs.mkdir()
        proposals.mkdir()
        event_sha = {row["event"]: row["sha256"] for row in event_rows}
        route_rows = []
        for row_index, event_sequence in ROUTES.items():
            family = f"ac1102_route{row_index:02d}"
            catalog_path = catalogs / f"{family}.json"
            product_scope = "edited_full_occurrence_target_progression_route_archive"
            write_json(
                catalog_path,
                {
                    "schema": "magireco-series-editions-v1",
                    "series": "ac1102",
                    "status": "passed",
                    "event_count": len(event_sequence),
                    "family_state": {"ready_event_names": list(event_sequence)},
                    "product_scopes": {event: product_scope for event in event_sequence},
                    "natural_session_claims": {event: False for event in event_sequence},
                    "ordering_evidence": f"DirInfo kind 54 row {row_index}; target-stage order only",
                    "fixed_native_session_gap_claimed": False,
                },
            )
            catalog_binding = final_binding(
                catalog_path, output_dir / "source_series_catalogs" / catalog_path.name
            )
            proposal_path = proposals / f"{family}.json"
            write_json(
                proposal_path,
                {
                    "schema": "magireco-ac1102-dirinfo-route-series-v1",
                    "series": family,
                    "status": "passed",
                    "event_count": len(event_sequence),
                    "title_zh": ROUTE_TITLES[row_index],
                    "dirinfo_kind": 54,
                    "dirinfo_row": row_index,
                    "event_sequence": list(event_sequence),
                    "ordering": "exact DirInfo target-stage order; each event is retained as a complete occurrence archive",
                    "product_scope": product_scope,
                    "natural_session_claimed": False,
                    "loop_scope": {
                        "status": "complete verified occurrence per target-stage node",
                        "fixed_inter_node_gap": False,
                    },
                    "family_state": {
                        "production_manifest_root": str(output_dir.resolve()),
                        "known_family_events": len(event_sequence),
                        "ready_family_events": len(event_sequence),
                        "not_ready_family_events": [],
                        "ready_event_names": list(event_sequence),
                    },
                    "event_manifest_sha256": {
                        event: event_sha[event] for event in event_sequence
                    },
                    "source_series_manifest": {
                        "path": catalog_binding["path"],
                        "sha256": catalog_binding["sha256"],
                        "evidence": "bound ac1102 DirInfo row and event-global timing authority",
                    },
                    "human_playback_required": True,
                    "publication_approved": False,
                },
            )
            route_rows.append(
                {
                    "row_index": row_index,
                    "family": family,
                    "title_zh": ROUTE_TITLES[row_index],
                    "event_sequence": list(event_sequence),
                    "source_series_relative_path": f"source_series_catalogs/{catalog_path.name}",
                    "source_series_sha256": file_sha256(catalog_path),
                    "series_proposal_relative_path": f"route_series_proposals/{proposal_path.name}",
                    "series_proposal_sha256": file_sha256(proposal_path),
                }
            )

        write_json(
            staging / "SUMMARY.json",
            {
                "schema": "magireco-ac1102-event-global-route-inputs-v1",
                "status": "PASS",
                "event_count": len(EVENTS),
                "route_count": len(ROUTES),
                "blocked_route_count": 31 - len(ROUTES),
                "events": event_rows,
                "routes": route_rows,
                "authority": authority_binding,
                "source_bindings": bindings,
                "fixed_native_session_gap_claimed": False,
                "human_playback_required": True,
                "publication_approved": False,
                "source_media_modified": False,
            },
        )
        (staging / "ROLLBACK.ps1").write_text(ROLLBACK_SCRIPT, encoding="utf-8")
        os.replace(staging, output_dir)
        for event, target in override_targets.items():
            shutil.copy2(output_dir / "timing_overrides" / target.name, target)
        write_json(output_dir / "VERIFICATION.json", verify_output(output_dir))
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--override-out-dir", type=Path, default=DEFAULT_OVERRIDE_ROOT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if args.verify_only:
        result = verify_output(output_dir)
    else:
        build(output_dir, args.override_out_dir.resolve())
        result = read_json(output_dir / "VERIFICATION.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
