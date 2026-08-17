#!/usr/bin/env python3
"""Bind ac6007 rows 0/1 caption timing to parent event time.

The source manifests knew the child Z2D callback frames but did not prove
where those children were instantiated by the parent DGM.  This bounded
builder combines the exact Slot IDA timing mechanism with one single-session
scene-graph capture.  It emits per-event overrides only after confirming that
the parent cut begins at event-global frame zero, the caption layer runs at
speed one, and no time remap is active.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    from tools.frida_runtime_probe.build_ac7210_rows0_1_timing_authority import (
        binding,
        one,
        read_json,
        round_frame_ms,
        validate_ida_preflight,
        walk,
        write_json,
    )
except ModuleNotFoundError:
    from build_ac7210_rows0_1_timing_authority import (  # type: ignore
        binding,
        one,
        read_json,
        round_frame_ms,
        validate_ida_preflight,
        walk,
        write_json,
    )


RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = RESEARCH_ROOT / "ida_static_scheduler_analysis_v1_20260808"
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_ac6007_rows0_1_scene_motion_v19_20260817"
IDA_PREFLIGHT = (
    RESEARCH_ROOT
    / "runtime_ac7210_rows0_1_scene_motion_v18_20260817"
    / "IDA_EXACT_SLOT_SESSION_PREFLIGHT.json"
)
SOURCE_MANIFEST_ROOT = (
    RESEARCH_ROOT
    / "production_manifests_v68_ac0911_011_audio_repair_20260806"
    / "events"
)
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT / "ac6007_rows0_1_event_global_timing_authority_v1r1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)

EVENTS = ("ac6007_002", "ac6007_003", "ac6007_005", "ac6007_006")
EXPECTED_EVENT_CODES = {
    "ac6007_002": "0x6d34576656306f6e",
    "ac6007_003": "0x6648437a56306f6e",
    "ac6007_005": "0x6e6f543356306f6e",
    "ac6007_006": "0x48574c7456306f6e",
}
# z2d -> (request, start frame, end frame exclusive, graphical end authoritative)
EXPECTED_CAPTION_NODES = {
    "ac6007_002": {
        "cap6007_qkuma_fer_001": ("4093", 1, 31, True),
        "cap6007_qkuma_san_002": ("4356", 19, 49, False),
    },
    "ac6007_003": {"cap6007_qkuma_fer_003": ("4090", 1, 31, False)},
    "ac6007_005": {"cap6007_qkuma_fer_005": ("4091", 1, 86, True)},
    "ac6007_006": {"cap6007_qkuma_fer_006": ("4096", 1, 46, True)},
}
EXPECTED_SOURCE_TIMES = {
    ("ac6007_002", "4093"): 33,
    ("ac6007_002", "4356"): 633,
    ("ac6007_003", "4090"): 33,
    ("ac6007_005", "4091"): 33,
    ("ac6007_006", "4096"): 33,
}
BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"


def extract_event_authority(event: str, runtime_event: dict, manifest: dict):
    event_code = EXPECTED_EVENT_CODES[event]
    if (
        str(runtime_event.get("event_code", "")).lower() != event_code
        or str(manifest.get("event_code_hex", "")).lower() != event_code
        or manifest.get("native_frame_rate") != "30/1"
    ):
        raise ValueError(f"{event}: event identity differs")
    gates = manifest.get("quality_gates", {})
    if (
        gates.get("errors") != [BLOCKER]
        or gates.get("event_global_z2d_timing_ready") is not False
        or gates.get("ready") is not False
        or gates.get("composition_resolved") is not True
    ):
        raise ValueError(f"{event}: source fail-closed state differs")

    scene = one(
        runtime_event.get("scenes", []),
        lambda row: row.get("name") == event,
        f"{event} primary scene",
    )
    cut = one(
        scene.get("cuts", []),
        lambda row: row.get("cut_name") == event,
        f"{event} primary cut",
    )
    if cut.get("instance_offset_frames") != 0 or cut.get("cut_start_frame") != 0:
        raise ValueError(f"{event}: parent cut is not event-global frame zero")

    node_context = {}
    for top in cut.get("nodes", []):
        layer = one(
            runtime_event.get("layers", []),
            lambda row, top=top: (row.get("hash_low"), row.get("hash_high"))
            == (top.get("hash_low"), top.get("hash_high")),
            f"{event}/{top.get('name')} player layer",
        )
        if layer.get("speed") != 1:
            raise ValueError(f"{event}/{top.get('name')}: layer speed differs")
        for node in walk(top):
            name = str(node.get("name", ""))
            if name.endswith(".z2d"):
                node_context[name[:-4]] = (node, layer, str(top.get("name", "")))

    expected_requests = tuple(
        value[0] for value in EXPECTED_CAPTION_NODES[event].values()
    )
    observed_requests = sorted(
        str(row.get("request_id", ""))
        for row in manifest.get("audio", [])
        if row.get("source") == "z2d_req_sound"
    )
    if observed_requests != sorted(expected_requests):
        raise ValueError(f"{event}: expected Z2D request set differs")

    cues = []
    evidence = []
    for z2d_name, (request_id, expected_start, expected_end, graphical_end) in (
        EXPECTED_CAPTION_NODES[event].items()
    ):
        if z2d_name not in node_context:
            raise ValueError(f"{event}/{z2d_name}: runtime Z2D node missing")
        node, layer, layer_name = node_context[z2d_name]
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
        start_frame = int(key["floats"][0])
        end_frame = int(key["floats"][1]) + 1
        if (start_frame, end_frame) != (expected_start, expected_end):
            raise ValueError(f"{event}/{z2d_name}: runtime motion interval differs")
        audio = one(
            manifest.get("audio", []),
            lambda row, request_id=request_id, z2d_name=z2d_name: str(
                row.get("request_id", "")
            )
            == request_id
            and row.get("z2d_name") == z2d_name,
            f"{event}/{request_id} source audio",
        )
        if (
            audio.get("event_global_start_resolved") is not False
            or int(audio.get("start_ms", -1))
            != EXPECTED_SOURCE_TIMES[(event, request_id)]
        ):
            raise ValueError(f"{event}/{request_id}: source child-local state differs")

        cue = {
            "request_id": request_id,
            "z2d_name": z2d_name,
            "event_global_start_frame": start_frame,
            "event_global_start_ms": round_frame_ms(start_frame),
        }
        if graphical_end:
            cue.update(
                {
                    "event_global_end_frame_exclusive": end_frame,
                    "event_global_end_ms": round_frame_ms(end_frame),
                }
            )
        cues.append(cue)
        evidence.append(
            {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "runtime_motion_fields": key["floats"],
                "runtime_motion_flags": key["flags"],
                "layer_name": layer_name,
                "layer_speed": layer["speed"],
                "time_remap_pointer": None,
                "event_global_start_frame": start_frame,
                "event_global_end_frame_exclusive": end_frame,
                "subtitle_end_policy": (
                    "graphical_motion_key_end"
                    if graphical_end
                    else "official_voice_duration_preserved"
                ),
            }
        )
    return (
        {
            "status": "event_global_parent_scene_motion_exact",
            "event_code_hex": event_code,
            "parent_cut": {
                "scene": scene["name"],
                "cut": cut["cut_name"],
                "instance_offset_frames": cut["instance_offset_frames"],
                "cut_start_frame": cut["cut_start_frame"],
                "cut_end_frame": cut["cut_end_frame"],
            },
            "caption_motion_evidence": evidence,
        },
        {
            "schema": "magireco-z2d-event-timing-override-v1",
            "event": event,
            "event_code_hex": event_code,
            "frame_rate": "30/1",
            "expected_z2d_request_ids": list(expected_requests),
            "cues": cues,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--override-out-dir", default=str(DEFAULT_OVERRIDE_ROOT))
    args = parser.parse_args()
    out_dir = Path(args.out_dir).resolve()
    override_dir = Path(args.override_out_dir).resolve()
    if out_dir.exists():
        raise ValueError(f"immutable authority output already exists: {out_dir}")
    out_dir.mkdir(parents=True)
    override_dir.mkdir(parents=True, exist_ok=True)
    try:
        sources = {
            "exact_libgameproc": STATIC_ROOT / "sample" / "libGameProc.so",
            "ida_parent_child": (
                STATIC_ROOT
                / "parent_child_timing_authority_v1_20260815"
                / "IDA_PARENT_CHILD_PSEUDOCODE.json"
            ),
            "ida_z2d_motion_fields": (
                STATIC_ROOT
                / "parent_child_timing_authority_v1_20260815"
                / "IDA_Z2D_MOTION_FIELDS.json"
            ),
            "ida_session_preflight": IDA_PREFLIGHT,
            "runtime_scene_motion": (
                RUNTIME_ROOT / "AC6007_ROWS0_1_RUNTIME_SCENE_MOTION.json"
            ),
            "runtime_capture_script": RUNTIME_ROOT / "capture_ac6007_scene_motion.py",
            "runtime_probe_script": RUNTIME_ROOT / "inspect_event_scene_motion.js",
            "route_plan": (
                REPO_ROOT
                / "tools"
                / "frida_runtime_probe"
                / "series_proposals"
                / "ac6007_complete_clean_routes_v1.json"
            ),
        }
        for event in EVENTS:
            sources[f"source_manifest_{event}"] = SOURCE_MANIFEST_ROOT / f"{event}.json"
        bindings = {name: binding(path) for name, path in sources.items()}
        if (
            bindings["exact_libgameproc"]["sha256"]
            != "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
        ):
            raise ValueError("exact Slot libGameProc hash differs")
        preflight = read_json(sources["ida_session_preflight"])
        validate_ida_preflight(preflight)
        runtime = read_json(sources["runtime_scene_motion"])
        if (
            runtime.get("schema") != "magireco-ac6007-runtime-scene-motion-v1"
            or runtime.get("host_frida_version") != "17.16.4"
            or runtime.get("protected_processes_unchanged") is not True
            or runtime.get("crash_buffer_empty") is not True
            or tuple(runtime.get("requested_events", {})) != EVENTS
            or set(runtime.get("events", {})) != set(EVENTS)
        ):
            raise ValueError("bounded ac6007 runtime capture differs")
        plan = read_json(sources["route_plan"])
        if (
            plan.get("schema") != "magireco-ac6007-complete-clean-routes-plan-v1"
            or tuple(plan.get("included_dirinfo_rows", [])) != (0, 1)
            or tuple(int(row["row"]) for row in plan.get("excluded_dirinfo_rows", []))
            != (2, 3, 4)
        ):
            raise ValueError("ac6007 route plan boundary differs")

        event_authority = {}
        overrides = {}
        for event in EVENTS:
            authority, override = extract_event_authority(
                event,
                runtime["events"][event],
                read_json(sources[f"source_manifest_{event}"]),
            )
            event_authority[event] = authority
            overrides[event] = override
        authority_path = out_dir / "AC6007_ROWS0_1_EVENT_GLOBAL_TIMING_AUTHORITY.json"
        authority_payload = {
            "schema": "magireco-ac6007-rows0-1-event-global-timing-authority-v1",
            "status": "PASS",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "family": "ac6007",
            "dirinfo_rows": [0, 1],
            "events": event_authority,
            "source_bindings": bindings,
            "source_media_modified": False,
            "review_boundary": (
                "rows 0/1 only; rows 2/3/4 remain gameplay/effect routes; "
                "new route editions still require human playback"
            ),
        }
        write_json(authority_path, authority_payload)
        authority_binding = binding(authority_path)
        override_bindings = []
        for event in EVENTS:
            payload = overrides[event]
            payload["authority_path"] = str(authority_path.resolve())
            payload["source_bindings"] = [authority_binding, *bindings.values()]
            override_path = (
                override_dir / f"{event}_parent_scene_motion_key_v1r1.json"
            )
            if override_path.exists():
                raise ValueError(f"immutable override already exists: {override_path}")
            write_json(override_path, payload)
            override_bindings.append(binding(override_path))
        write_json(
            out_dir / "VERIFICATION.json",
            {
                "schema": "magireco-ac6007-rows0-1-timing-verification-v1",
                "result": "PASS",
                "event_count": len(EVENTS),
                "event_global_start_frames": {
                    "ac6007_002": {"4093": 1, "4356": 19},
                    "ac6007_003": {"4090": 1},
                    "ac6007_005": {"4091": 1},
                    "ac6007_006": {"4096": 1},
                },
                "graphical_end_correction": {
                    "event": "ac6007_005",
                    "request_id": "4091",
                    "old_end_ms": 3030,
                    "event_global_end_frame_exclusive": 86,
                    "new_end_ms": 2867,
                },
                "protected_processes_unchanged": True,
                "source_media_modified": False,
                "publication_approved": False,
            },
        )
        write_json(
            out_dir / "SUMMARY.json",
            {
                "schema": "magireco-ac6007-rows0-1-timing-authority-summary-v1",
                "status": "PASS",
                "events": list(EVENTS),
                "dirinfo_rows": [0, 1],
                "authority": authority_binding,
                "overrides": override_bindings,
                "audio_start_timing_changed": False,
                "graphical_subtitle_end_changed": True,
                "human_playback_required": True,
                "publication_approved": False,
            },
        )
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    print(str(out_dir / "VERIFICATION.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
