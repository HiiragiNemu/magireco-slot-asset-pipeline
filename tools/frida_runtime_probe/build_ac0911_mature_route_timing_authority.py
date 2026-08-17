#!/usr/bin/env python3
"""Bind the nine mature ac0911 route dialogue events to parent event time.

The legacy manifests contained exact child-Z2D callback frames but did not
prove the parent DGM instantiation point.  This builder combines the exact
Slot libGameProc IDA timing mechanism with one bounded live scene-graph
capture.  It fails closed unless the parent cut begins at event-global frame
zero, the owning layer speed is one, no time remap is active, and the complete
caption motion key matches the expected capture.
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
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_ac0911_mature_routes_scene_motion_v21_20260817"
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
    RESEARCH_ROOT / "ac0911_mature_routes_event_global_timing_authority_v1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)

BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"
EVENTS = (
    "ac0911_002",
    "ac0911_003",
    "ac0911_004",
    "ac0911_006",
    "ac0911_008",
    "ac0911_009",
    "ac0911_010",
    "ac0911_012",
    "ac0911_017",
)

# event -> exact captured identity and the one expected child-Z2D request.
# key_floats are the seven DirectionNodeMotionZ2D fields consumed by the
# exact-hash IDA mechanism; key_flags are preserved as additional capture
# identity.  Graphical subtitles use the motion-key end; voice/ASR subtitles
# preserve their independently evidenced duration.
EVENT_SPEC = {
    "ac0911_002": {
        "code": "0x2f6f356273354a53",
        "z2d": "cap0911_takara_kur_002",
        "request": "8031",
        "key_floats": [2, 132, 2, 31, 2, 31, -1],
        "key_flags": [0, 1, 0],
        "source_start_ms": 67,
        "source_end_ms": 4433,
        "graphical_end": True,
    },
    "ac0911_003": {
        "code": "0x6e55743273354a53",
        "z2d": "cap0911_takara_kur_003",
        "request": "8032",
        "key_floats": [3, 60, 3, 32, 3, 32, -1],
        "key_flags": [0, 1, 1],
        "source_start_ms": 100,
        "source_end_ms": 2033,
        "graphical_end": True,
    },
    "ac0911_004": {
        "code": "0x3731334673354a53",
        "z2d": "cap0911_takara_kur_004",
        "request": "8033",
        "key_floats": [10, 39, 10, 39, 10, 39, -1],
        "key_flags": [0, 2, 1],
        "source_start_ms": 333,
        "source_end_ms": 1871,
        "graphical_end": True,
    },
    "ac0911_006": {
        "code": "0x74746a3473354a53",
        "z2d": "cap0911_takara_wom_001",
        "request": "8454",
        "key_floats": [10, 39, 10, 39, 10, 39, -1],
        "key_flags": [0, 1, 1],
        "source_start_ms": 333,
        "source_end_ms": 5681,
        "graphical_end": True,
    },
    "ac0911_008": {
        "code": "0x5666322d73354a53",
        "z2d": "cap0911_takara_wom_003",
        "request": "9963",
        "key_floats": [8, 37, 8, 37, 8, 37, -1],
        "key_flags": [0, 2, 1],
        "source_start_ms": 267,
        "source_end_ms": 5803,
        "graphical_end": True,
    },
    "ac0911_009": {
        "code": "0x30554e4b73354a53",
        "z2d": "cap0911_takara_kur_006",
        "request": "8040",
        "key_floats": [10, 39, 10, 39, 10, 39, -1],
        "key_flags": [0, 2, 1],
        "source_start_ms": 333,
        "source_end_ms": 2173,
        "graphical_end": False,
    },
    "ac0911_010": {
        "code": "0x597a384173354a53",
        "z2d": "cap0911_takara_kur_008",
        "request": "8041",
        "key_floats": [10, 39, 10, 39, 10, 39, -1],
        "key_flags": [0, 2, 1],
        "source_start_ms": 333,
        "source_end_ms": 2786,
        "graphical_end": False,
    },
    "ac0911_012": {
        "code": "0x766e254673354a53",
        "z2d": "cap0911_takara_kur_010",
        "request": "8038",
        "key_floats": [10, 39, 10, 39, 10, 39, -1],
        "key_flags": [0, 2, 1],
        "source_start_ms": 333,
        "source_end_ms": 3293,
        "graphical_end": True,
    },
    "ac0911_017": {
        "code": "0x4b2a777273354a53",
        "z2d": "cap0911_takara_kur_007",
        "request": "8039",
        "key_floats": [6, 35, 6, 35, 6, 35, -1],
        "key_flags": [0, 2, 1],
        "source_start_ms": 200,
        "source_end_ms": 1010,
        "graphical_end": False,
    },
}


def extract_event_authority(event: str, runtime_event: dict, manifest: dict):
    spec = EVENT_SPEC[event]
    if (
        str(runtime_event.get("event_code", "")).lower() != spec["code"]
        or str(manifest.get("event_code_hex", "")).lower() != spec["code"]
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

    expected_requests = [str(spec["request"])]
    observed_requests = sorted(
        str(row.get("request_id", ""))
        for row in manifest.get("audio", [])
        if row.get("source") == "z2d_req_sound"
    )
    if observed_requests != expected_requests:
        raise ValueError(f"{event}: expected Z2D request set differs")
    if spec["z2d"] not in node_context:
        raise ValueError(f"{event}/{spec['z2d']}: runtime Z2D node missing")

    node, layer, layer_name = node_context[str(spec["z2d"])]
    if node.get("time_remap_pointer") is not None:
        raise ValueError(f"{event}/{spec['z2d']}: time remap is active")
    motion = one(
        node.get("motions", []),
        lambda row: row.get("is_z2d_motion") is True,
        f"{event}/{spec['z2d']} Z2D motion",
    )
    key = one(
        motion.get("keys", []),
        lambda row: row.get("index") == 0,
        f"{event}/{spec['z2d']} motion key zero",
    )
    if key.get("floats") != spec["key_floats"] or key.get("flags") != spec["key_flags"]:
        raise ValueError(f"{event}/{spec['z2d']}: runtime motion key differs")
    start_frame = int(key["floats"][0])
    end_frame = int(key["floats"][1]) + 1
    if round_frame_ms(start_frame) != spec["source_start_ms"]:
        raise ValueError(f"{event}/{spec['request']}: captured start differs")

    audio = one(
        manifest.get("audio", []),
        lambda row: str(row.get("request_id", "")) == spec["request"]
        and row.get("z2d_name") == spec["z2d"],
        f"{event}/{spec['request']} source audio",
    )
    subtitle = one(
        manifest.get("subtitles", []),
        lambda row: row.get("z2d_name") == spec["z2d"],
        f"{event}/{spec['z2d']} source subtitle",
    )
    if (
        audio.get("event_global_start_resolved") is not False
        or int(audio.get("start_ms", -1)) != spec["source_start_ms"]
        or (int(subtitle.get("start_ms", -1)), int(subtitle.get("end_ms", -1)))
        != (spec["source_start_ms"], spec["source_end_ms"])
    ):
        raise ValueError(f"{event}: source child-local timing differs")

    cue = {
        "request_id": spec["request"],
        "z2d_name": spec["z2d"],
        "event_global_start_frame": start_frame,
        "event_global_start_ms": round_frame_ms(start_frame),
    }
    if spec["graphical_end"]:
        cue.update(
            {
                "event_global_end_frame_exclusive": end_frame,
                "event_global_end_ms": round_frame_ms(end_frame),
            }
        )

    evidence = {
        "request_id": spec["request"],
        "z2d_name": spec["z2d"],
        "runtime_motion_fields": key["floats"],
        "runtime_motion_flags": key["flags"],
        "layer_name": layer_name,
        "layer_speed": layer["speed"],
        "time_remap_pointer": None,
        "event_global_start_frame": start_frame,
        "event_global_end_frame_exclusive": end_frame,
        "subtitle_end_policy": (
            "graphical_motion_key_end"
            if spec["graphical_end"]
            else "official_voice_or_reviewed_asr_duration_preserved"
        ),
    }
    return (
        {
            "status": "event_global_parent_scene_motion_exact",
            "event_code_hex": spec["code"],
            "parent_cut": {
                "scene": scene["name"],
                "cut": cut["cut_name"],
                "instance_offset_frames": 0,
                "cut_start_frame": 0,
                "cut_end_frame": cut["cut_end_frame"],
            },
            "caption_motion_evidence": [evidence],
        },
        {
            "schema": "magireco-z2d-event-timing-override-v1",
            "event": event,
            "event_code_hex": spec["code"],
            "frame_rate": "30/1",
            "expected_z2d_request_ids": expected_requests,
            "cues": [cue],
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
                RUNTIME_ROOT / "AC0911_MATURE_ROUTES_RUNTIME_SCENE_MOTION.json"
            ),
            "runtime_capture_script": RUNTIME_ROOT / "capture_ac0911_scene_motion.py",
            "runtime_probe_script": RUNTIME_ROOT / "inspect_event_scene_motion.js",
            "route_plan": (
                REPO_ROOT
                / "tools"
                / "frida_runtime_probe"
                / "series_proposals"
                / "ac0911_mature_dirinfo_routes_v1.json"
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
            runtime.get("schema")
            != "magireco-ac0911-mature-routes-runtime-scene-motion-v1"
            or runtime.get("host_frida_version") != "17.16.4"
            or runtime.get("protected_processes_unchanged") is not True
            or runtime.get("crash_buffer_empty") is not True
            or tuple(runtime.get("requested_events", {})) != EVENTS
            or set(runtime.get("events", {})) != set(EVENTS)
        ):
            raise ValueError("bounded ac0911 runtime capture differs")
        plan = read_json(sources["route_plan"])
        routes = [tuple(row.get("render_event_sequence", [])) for row in plan.get("routes", [])]
        excluded = [int(row.get("row_index", -1)) for row in plan.get("excluded_dirinfo_rows", [])]
        if (
            plan.get("family") != "ac0911"
            or len(routes) != 9
            or excluded != [8, 10, 11, 12, 13]
            or any(event not in {value for route in routes for value in route} for event in EVENTS)
        ):
            raise ValueError("ac0911 mature route boundary differs")

        authorities = {}
        overrides = {}
        for event in EVENTS:
            authorities[event], overrides[event] = extract_event_authority(
                event,
                runtime["events"][event],
                read_json(sources[f"source_manifest_{event}"]),
            )
        authority_path = out_dir / "AC0911_MATURE_ROUTES_EVENT_GLOBAL_TIMING_AUTHORITY.json"
        corrections = {
            event: {
                "request_id": EVENT_SPEC[event]["request"],
                "old_end_ms": EVENT_SPEC[event]["source_end_ms"],
                "new_end_ms": round_frame_ms(int(EVENT_SPEC[event]["key_floats"][1]) + 1),
            }
            for event in EVENTS
            if EVENT_SPEC[event]["graphical_end"]
            and round_frame_ms(int(EVENT_SPEC[event]["key_floats"][1]) + 1)
            != EVENT_SPEC[event]["source_end_ms"]
        }
        write_json(
            authority_path,
            {
                "schema": "magireco-ac0911-mature-routes-event-global-timing-authority-v1",
                "status": "PASS",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "family": "ac0911",
                "mature_route_count": 9,
                "events": authorities,
                "source_bindings": bindings,
                "graphical_end_corrections": corrections,
                "source_media_modified": False,
                "review_boundary": (
                    "nine mature routes only; DirInfo rows 8/10/11/12/13 remain blocked; "
                    "new route products require human playback"
                ),
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
                "schema": "magireco-ac0911-mature-routes-timing-authority-summary-v1",
                "status": "PASS",
                "events": list(EVENTS),
                "mature_route_count": 9,
                "authority": authority_binding,
                "overrides": override_bindings,
                "audio_start_timing_changed": False,
                "graphical_subtitle_end_changed_events": sorted(corrections),
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
