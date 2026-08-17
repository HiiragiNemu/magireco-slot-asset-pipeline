#!/usr/bin/env python3
"""Build exact parent-scene timing authority for ac7210 DirInfo rows 0/1.

The old manifests contained numerically correct starts for ac7210_004 and
ac7210_005, but their evidence stopped at a child-local Z2D callback.  This
builder binds the exact Slot binary's IDA mechanism semantics to one bounded
live scene-graph capture.  It proves the parent cut starts at event-global
frame zero, the relevant layer speed is one, no time remap is active, and the
caption Z2D keys begin at frames 65/65 and 15 respectively.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

try:
    from tools.frida_runtime_probe.build_event_production_manifests import (
        file_sha256,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import (
        file_sha256,
    )


RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = RESEARCH_ROOT / "ida_static_scheduler_analysis_v1_20260808"
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_ac7210_rows0_1_scene_motion_v18_20260817"
SOURCE_MANIFEST_ROOT = (
    RESEARCH_ROOT
    / "production_manifests_v68_ac0911_011_audio_repair_20260806"
    / "events"
)
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT / "ac7210_rows0_1_event_global_timing_authority_v1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)

EVENTS = ("ac7210_004", "ac7210_005")
EXPECTED_EVENT_CODES = {
    "ac7210_004": "0x7645363357706153",
    "ac7210_005": "0x6d5a4f5657706153",
}
EXPECTED_CAPTION_NODES = {
    "ac7210_004": {
        "cap7210_hobaku_yac_004": ("3280", 65, 95, False),
        "cap7210_hobaku_tur_005": ("3594", 65, 95, False),
    },
    "ac7210_005": {
        "cap7210_hobaku_tur_002": ("3593", 15, 45, True),
    },
}
EXPECTED_Z2D_REQUESTS = {
    "ac7210_004": ("3280", "3594"),
    "ac7210_005": ("3593",),
}
EXPECTED_SOURCE_TIMES = {
    ("ac7210_004", "3280"): 2167,
    ("ac7210_004", "3594"): 2167,
    ("ac7210_005", "3593"): 500,
}
BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def binding(path: Path) -> dict[str, object]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def one(rows: list[dict], predicate, label: str) -> dict:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise ValueError(f"expected one {label}, got {len(matches)}")
    return matches[0]


def walk(node: dict):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def round_frame_ms(frame: int) -> int:
    return int(Fraction(frame * 1000, 30) + Fraction(1, 2))


def validate_ida_preflight(preflight: dict) -> None:
    expected_functions = {
        ("0x42b0060", "zg::CGFDirectionNodeLayer::AdvanceTime"),
        ("0x42b0140", "zg::CGFDirectionNodeLayer::SetTime"),
        ("0x42b43e0", "zg::CGFDirectionNodeMotionZ2D::Calc"),
    }
    observed_functions = {
        (str(row.get("address", "")).lower(), str(row.get("name", "")))
        for row in preflight.get("functions", [])
    }
    if (
        preflight.get("schema")
        != "magireco-ida-exact-slot-session-preflight-v1"
        or preflight.get("module") != "libGameProc.so"
        or preflight.get("input_sha256")
        != "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
        or preflight.get("imagebase") != 0
        or preflight.get("analysis_complete") is not True
        or observed_functions != expected_functions
    ):
        raise ValueError("exact Slot IDA session preflight differs")


def extract_event_authority(
    event: str, runtime_event: dict, manifest: dict
) -> tuple[dict, dict]:
    event_code = EXPECTED_EVENT_CODES[event]
    if (
        runtime_event.get("event_code", "").lower() != event_code
        or manifest.get("event_code_hex", "").lower() != event_code
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

    node_context: dict[str, tuple[dict, dict, str]] = {}
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

    observed_requests = sorted(
        str(row.get("request_id", ""))
        for row in manifest.get("audio", [])
        if row.get("source") == "z2d_req_sound"
    )
    if observed_requests != sorted(EXPECTED_Z2D_REQUESTS[event]):
        raise ValueError(f"{event}: expected Z2D request set differs")

    cues: list[dict] = []
    evidence: list[dict] = []
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
            or int(audio.get("start_ms", -1)) != EXPECTED_SOURCE_TIMES[(event, request_id)]
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
            "expected_z2d_request_ids": list(EXPECTED_Z2D_REQUESTS[event]),
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
        "ida_session_preflight": RUNTIME_ROOT / "IDA_EXACT_SLOT_SESSION_PREFLIGHT.json",
        "runtime_scene_motion": RUNTIME_ROOT / "AC7210_ROWS0_1_RUNTIME_SCENE_MOTION.json",
        "runtime_capture_script": RUNTIME_ROOT / "capture_ac7210_scene_motion.py",
        "runtime_probe_script": RUNTIME_ROOT / "inspect_event_scene_motion.js",
        "route_plan": (
            REPO_ROOT
            / "tools"
            / "frida_runtime_probe"
            / "series_proposals"
            / "ac7210_approved_route_editions_v1.json"
        ),
        "route_review_plan": (
            REPO_ROOT
            / "tools"
            / "frida_runtime_probe"
            / "series_proposals"
            / "ac7210_dirinfo_route_supplements_v1.json"
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
        runtime.get("schema") != "magireco-ac7210-runtime-scene-motion-v1"
        or runtime.get("host_frida_version") != "17.16.4"
        or runtime.get("protected_processes_unchanged") is not True
        or runtime.get("crash_buffer_empty") is not True
        or tuple(runtime.get("requested_events", {})) != EVENTS
        or set(runtime.get("events", {})) != set(EVENTS)
    ):
        raise ValueError("bounded ac7210 runtime capture differs")

    route_plan = read_json(sources["route_plan"])
    route_rows = {
        int(row.get("dirinfo_row", -1)): tuple(row.get("ordered_events", []))
        for row in route_plan.get("approved_zh", [])
    }
    # The route order is stored in the nested v29 review plan, while this plan
    # binds the exact owner-approved row identities.
    review_plan = read_json(sources["route_review_plan"])
    ordered_routes = {
        int(row["dirinfo_row"]): tuple(row["ordered_events"])
        for row in review_plan.get("routes", [])
    }
    if ordered_routes != {
        0: ("ac7210_001", "ac7210_002", "ac7210_003", "ac7210_004"),
        1: ("ac7210_001", "ac7210_005", "ac7210_003", "ac7210_004"),
    } or set(route_rows) != {0, 1}:
        raise ValueError("ac7210 approved route scope differs")

    events: dict[str, dict] = {}
    overrides: dict[str, dict] = {}
    for event in EVENTS:
        manifest = read_json(SOURCE_MANIFEST_ROOT / f"{event}.json")
        events[event], overrides[event] = extract_event_authority(
            event, runtime["events"][event], manifest
        )

    authority_path = out_dir / "AC7210_ROWS0_1_EVENT_GLOBAL_TIMING_AUTHORITY.json"
    authority = {
        "schema": "magireco-ac7210-rows0-1-event-global-timing-authority-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "route_scope": {
            "family": "ac7210",
            "dirinfo_rows": [0, 1],
            "routes": {str(key): list(value) for key, value in ordered_routes.items()},
        },
        "runtime_safety": {
            "protected_processes_before": runtime["protected_processes_before"],
            "protected_processes_after": runtime["protected_processes_after"],
            "protected_processes_unchanged": True,
            "crash_buffer_empty": True,
            "no_app_restarted_closed_or_switched": True,
        },
        "mechanism": {
            "authority": "exact-hash IDA mechanism semantics plus bounded live scene graph",
            "frame_rule": "event_global_frame = parent_instance_offset_frames + child_motion_key_frame - cut_start_frame",
            "voice_subtitle_end_policy": "preserve official voice-duration end when only the exact start is under repair",
            "graphical_subtitle_end_policy": "use the Z2D motion key exclusive end",
            "numeric_change": False,
            "evidence_change": "child-local-only starts promoted to exact event-global starts",
        },
        "source_bindings": bindings,
        "events": events,
        "status": "PASS",
    }
    write_json(authority_path, authority)
    authority_binding = binding(authority_path)

    override_bindings = []
    for event in EVENTS:
        payload = overrides[event]
        payload["authority_path"] = str(authority_path.resolve())
        payload["source_bindings"] = [authority_binding, *bindings.values()]
        path = override_dir / f"{event}_parent_scene_motion_key_v1.json"
        if path.exists():
            raise ValueError(f"refusing to overwrite timing override: {path}")
        write_json(path, payload)
        override_bindings.append(binding(path))

    summary = {
        "schema": "magireco-ac7210-rows0-1-timing-authority-summary-v1",
        "status": "PASS",
        "events": list(EVENTS),
        "dirinfo_rows": [0, 1],
        "authority": authority_binding,
        "overrides": override_bindings,
        "numeric_timing_changed": False,
        "existing_owner_approved_zh_hashes_remain_valid": True,
        "none_ja_human_playback_required": True,
        "publication_approved": False,
    }
    write_json(out_dir / "SUMMARY.json", summary)
    shutil.copy2(Path(__file__).resolve(), out_dir / Path(__file__).name)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
