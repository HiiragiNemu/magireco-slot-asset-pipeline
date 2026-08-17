#!/usr/bin/env python3
"""Bind ac7206 route events 002/013 to event-global parent time."""

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
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_ac7206_rows20_39_scene_motion_v20_20260817"
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
    RESEARCH_ROOT / "ac7206_routes_event_global_timing_authority_v1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)

EVENTS = ("ac7206_002", "ac7206_013")
EVENT_CODES = {
    "ac7206_002": "0x253f336a4e516467",
    "ac7206_013": "0x464d434f4e516467",
}
# event -> z2d -> (request, start, end-exclusive)
CAPTIONS = {
    "ac7206_002": {"cap7206_paint_ari_003": ("5323", 10, 40)},
    "ac7206_013": {"cap7206_paint_ari_004": ("5324", 1, 31)},
}
SOURCE_STARTS = {
    ("ac7206_002", "5323"): 333,
    ("ac7206_013", "5324"): 33,
}
BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"


def extract_event_authority(event: str, runtime_event: dict, manifest: dict):
    event_code = EVENT_CODES[event]
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

    nodes = {}
    for top in cut.get("nodes", []):
        layer = one(
            runtime_event.get("layers", []),
            lambda row, top=top: (row.get("hash_low"), row.get("hash_high"))
            == (top.get("hash_low"), top.get("hash_high")),
            f"{event}/{top.get('name')} player layer",
        )
        if layer.get("speed") != 1:
            raise ValueError(f"{event}: caption layer speed differs")
        for node in walk(top):
            name = str(node.get("name", ""))
            if name.endswith(".z2d"):
                nodes[name[:-4]] = (node, layer, str(top.get("name", "")))
    expected_requests = tuple(value[0] for value in CAPTIONS[event].values())
    observed_requests = sorted(
        str(row.get("request_id", ""))
        for row in manifest.get("audio", [])
        if row.get("source") == "z2d_req_sound"
    )
    if observed_requests != sorted(expected_requests):
        raise ValueError(f"{event}: expected Z2D request set differs")

    cues = []
    evidence = []
    for z2d_name, (request_id, expected_start, expected_end) in CAPTIONS[event].items():
        if z2d_name not in nodes:
            raise ValueError(f"{event}/{z2d_name}: runtime Z2D node missing")
        node, layer, layer_name = nodes[z2d_name]
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
            lambda row: str(row.get("request_id", "")) == request_id
            and row.get("z2d_name") == z2d_name,
            f"{event}/{request_id} source audio",
        )
        if (
            audio.get("event_global_start_resolved") is not False
            or int(audio.get("start_ms", -1)) != SOURCE_STARTS[(event, request_id)]
            or round_frame_ms(start_frame) != SOURCE_STARTS[(event, request_id)]
        ):
            raise ValueError(f"{event}/{request_id}: source child-local start differs")
        cues.append(
            {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "event_global_start_frame": start_frame,
                "event_global_start_ms": round_frame_ms(start_frame),
            }
        )
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
                "subtitle_end_policy": "official_voice_or_reviewed_asr_duration_preserved",
            }
        )
    return (
        {
            "status": "event_global_parent_scene_motion_exact",
            "event_code_hex": event_code,
            "parent_cut": {
                "scene": scene["name"],
                "cut": cut["cut_name"],
                "instance_offset_frames": 0,
                "cut_start_frame": 0,
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
            "runtime_scene_motion": RUNTIME_ROOT / "AC7206_RUNTIME_SCENE_MOTION.json",
            "runtime_capture_script": RUNTIME_ROOT / "capture_ac7206_scene_motion.py",
            "runtime_probe_script": RUNTIME_ROOT / "inspect_event_scene_motion.js",
            "route_plan": (
                REPO_ROOT
                / "tools"
                / "frida_runtime_probe"
                / "series_proposals"
                / "ac7206_mature_dirinfo_routes_v1.json"
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
        validate_ida_preflight(read_json(sources["ida_session_preflight"]))
        runtime = read_json(sources["runtime_scene_motion"])
        if (
            runtime.get("schema") != "magireco-ac7206-runtime-scene-motion-v1"
            or runtime.get("host_frida_version") != "17.16.4"
            or runtime.get("protected_processes_unchanged") is not True
            or runtime.get("crash_buffer_empty") is not True
            or tuple(runtime.get("requested_events", {})) != EVENTS
            or set(runtime.get("events", {})) != set(EVENTS)
        ):
            raise ValueError("bounded ac7206 runtime capture differs")
        plan = read_json(sources["route_plan"])
        routes = [tuple(row.get("render_event_sequence", [])) for row in plan.get("routes", [])]
        if (
            plan.get("family") != "ac7206"
            or len(routes) != 6
            or any(route[0] != "ac7206_002" for route in routes)
            or routes[-2:] != [
                ("ac7206_002", "ac7206_013"),
                ("ac7206_002", "ac7206_014"),
            ]
        ):
            raise ValueError("ac7206 mature route boundary differs")

        authorities = {}
        overrides = {}
        for event in EVENTS:
            authorities[event], overrides[event] = extract_event_authority(
                event,
                runtime["events"][event],
                read_json(sources[f"source_manifest_{event}"]),
            )
        authority_path = out_dir / "AC7206_ROUTE_EVENT_GLOBAL_TIMING_AUTHORITY.json"
        write_json(
            authority_path,
            {
                "schema": "magireco-ac7206-route-event-global-timing-authority-v1",
                "status": "PASS",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "family": "ac7206",
                "route_count": 6,
                "events": authorities,
                "source_bindings": bindings,
                "numeric_timing_changed": False,
                "source_media_modified": False,
                "publication_approved": False,
            },
        )
        authority_binding = binding(authority_path)
        override_bindings = []
        for event in EVENTS:
            payload = overrides[event]
            payload["authority_path"] = str(authority_path.resolve())
            payload["source_bindings"] = [authority_binding, *bindings.values()]
            path = override_dir / f"{event}_parent_scene_motion_key_v1.json"
            if path.exists():
                raise ValueError(f"immutable override already exists: {path}")
            write_json(path, payload)
            override_bindings.append(binding(path))
        write_json(
            out_dir / "SUMMARY.json",
            {
                "schema": "magireco-ac7206-route-timing-authority-summary-v1",
                "status": "PASS",
                "events": list(EVENTS),
                "route_count": 6,
                "authority": authority_binding,
                "overrides": override_bindings,
                "numeric_timing_changed": False,
                "existing_route_media_reencode_required": False,
                "human_playback_required": True,
                "publication_approved": False,
            },
        )
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    print(json.dumps(read_json(out_dir / "SUMMARY.json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
