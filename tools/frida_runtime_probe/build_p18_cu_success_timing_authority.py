#!/usr/bin/env python3
"""Build exact P18 CU-success parent-scene timing authority.

The rejected P18 candidate promoted child-local caption callbacks into the
event-global timeline.  A bounded runtime scene-graph capture now proves the
parent cut, layer speed, time-remap state, and exact Z2D motion keys for the
two affected events.  ac6005_013 remains bound to its official resolved
runtime manifest and intentionally receives no override.
"""

from __future__ import annotations

import argparse
import csv
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
SOURCE_MANIFEST_ROOT = (
    RESEARCH_ROOT
    / "production_manifests_v68_ac0911_011_audio_repair_20260806"
    / "events"
)
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_p18_cu_success_scene_motion_v17_20260817"
CATALOG_ROOT = RESEARCH_ROOT / "z2d_audio_timeline_v2"
DGM_TIMELINE = Path(
    r"D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603"
    r"\z2d_dgm_event_map_v4\gdb_event_dgm_video_timeline.csv"
)
DIRINFO_ROUTES = Path(
    r"D:\magia\MyProducts\casino\runtime_recovery_20260703"
    r"\dirinfo_event_table_decode_v3_20260703\dirinfo_event_routes.csv"
)
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT / "p18_ac6005_cu_success_event_global_timing_authority_v1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)
ROUTE_EVENTS = ("ac6005_010", "ac6005_013", "ac6005_014")
OVERRIDE_EVENTS = ("ac6005_010", "ac6005_014")
EXPECTED_EVENT_CODES = {
    "ac6005_010": "0x635337534c444566",
    "ac6005_013": "0x352f6f3d4c444566",
    "ac6005_014": "0x455f642a4c444566",
}
EXPECTED_Z2D_REQUESTS = {
    "ac6005_010": ("5409", "5612"),
    "ac6005_014": ("2793", "2794", "2795"),
}
EXPECTED_CAPTION_NODES = {
    "ac6005_010": {
        "cap6005_mb_nem_011": ("5612", 27, 87),
        "cap6005_mb_tou_012": ("5409", 96, 196),
    },
    "ac6005_014": {
        "cap6005_mb_iro_014": ("2793", 1, 51),
        "cap6005_mb_iro_015": ("2794", 137, 206),
        "cap6005_mb_iro_015_01": ("", 227, 290),
        "cap6005_mb_iro_015_02": ("2795", 295, 331),
        "cap6005_mb_iro_015_03": ("", 335, 434),
    },
}
EXPECTED_GRAPHICAL_TEXT = {
    "cap6005_mb_iro_015_01": "少しでも長く一緒にいてよ…",
    "cap6005_mb_iro_015_03": "大好きなふたりのお姉ちゃんでいさせて",
}


def binding(path: Path) -> dict[str, object]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


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


def _dirinfo_route(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    selected = sorted(
        (
            row
            for row in rows
            if row.get("kind") == "173" and row.get("row_index") == "10"
        ),
        key=lambda row: int(row["selector_raw"]),
    )
    if [row["selector_raw"] for row in selected] != ["0", "4", "5"]:
        raise ValueError("DirInfo kind 173 row 10 selector sequence differs")
    route = []
    for event, row in zip(ROUTE_EVENTS, selected):
        if (
            row["scene_name"] != event
            or row["code_hex"].lower() != EXPECTED_EVENT_CODES[event]
            or row["route_status"] != "ok"
        ):
            raise ValueError(f"DirInfo route identity differs for {event}")
        route.append(
            {
                "event": event,
                "selector_raw": int(row["selector_raw"]),
                "event_info_index": int(row["event_info_index"]),
                "event_code_hex": row["code_hex"],
            }
        )
    return route


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
        "runtime_scene_motion": (
            RUNTIME_ROOT / "P18_AC6005_CU_SUCCESS_RUNTIME_SCENE_MOTION.json"
        ),
        "runtime_capture_script": RUNTIME_ROOT / "capture_family_scene_motion.py",
        "runtime_probe_script": RUNTIME_ROOT / "inspect_event_scene_motion.js",
        "ida_motion_fields": (
            STATIC_ROOT
            / "parent_child_timing_authority_v1_20260815"
            / "IDA_Z2D_MOTION_FIELDS.json"
        ),
        "ida_parent_child": (
            STATIC_ROOT
            / "parent_child_timing_authority_v1_20260815"
            / "IDA_PARENT_CHILD_PSEUDOCODE.json"
        ),
        "event_sound_catalog": CATALOG_ROOT / "event_sound_timeline.csv",
        "subtitle_catalog": CATALOG_ROOT / "subtitle_event_timeline.csv",
        "gdb_dgm_timeline": DGM_TIMELINE,
        "dirinfo_routes": DIRINFO_ROUTES,
    }
    for event in ROUTE_EVENTS:
        sources[f"source_manifest_{event}"] = SOURCE_MANIFEST_ROOT / f"{event}.json"
    bindings = {name: binding(path) for name, path in sources.items()}

    runtime = json.loads(sources["runtime_scene_motion"].read_text(encoding="utf-8"))
    if not runtime["protected_processes_unchanged"] or not runtime["crash_buffer_empty"]:
        raise ValueError("P18 capture did not preserve foreground games")
    if tuple(runtime["requested_events"]) != ROUTE_EVENTS or set(runtime["events"]) != set(
        ROUTE_EVENTS
    ):
        raise ValueError("P18 runtime event set differs")
    dirinfo_route = _dirinfo_route(read_csv(DIRINFO_ROUTES))
    sound_rows = read_csv(sources["event_sound_catalog"])
    subtitle_rows = read_csv(sources["subtitle_catalog"])
    dgm_rows = read_csv(DGM_TIMELINE)

    event_results: dict[str, dict] = {}
    override_payloads: dict[str, dict] = {}
    for event in ROUTE_EVENTS:
        manifest = json.loads(
            (SOURCE_MANIFEST_ROOT / f"{event}.json").read_text(encoding="utf-8")
        )
        value = runtime["events"][event]
        if (
            value["event_code"].lower() != EXPECTED_EVENT_CODES[event]
            or manifest["event_code_hex"].lower() != EXPECTED_EVENT_CODES[event]
        ):
            raise ValueError(f"runtime/manifest event code differs for {event}")
        scene = one(value["scenes"], lambda row: row["name"] == event, f"{event} scene")
        cut = one(scene["cuts"], lambda row: row["cut_name"] == event, f"{event} cut")
        if cut["instance_offset_frames"] != 0 or cut["cut_start_frame"] != 0:
            raise ValueError(f"{event} parent cut is not event-global frame zero")

        if event == "ac6005_013":
            runtime_sources = manifest.get("runtime_event_manifest_sources", [])
            if (
                manifest["quality_gates"].get("event_global_z2d_timing_ready") is not True
                or manifest["quality_gates"].get("ready") is not True
                or len(runtime_sources) != 1
            ):
                raise ValueError("ac6005_013 is no longer resolved runtime-exact READY")
            runtime_source = Path(runtime_sources[0]["path"])
            if file_sha256(runtime_source) != runtime_sources[0]["sha256"]:
                raise ValueError("ac6005_013 resolved runtime source differs")
            event_results[event] = {
                "status": "runtime_exact_source_retained",
                "event_code_hex": EXPECTED_EVENT_CODES[event],
                "runtime_event_manifest": runtime_sources[0],
                "override_required": False,
            }
            continue

        node_context: dict[str, tuple[dict, dict, str]] = {}
        for top in cut["nodes"]:
            layer = one(
                value["layers"],
                lambda row, top=top: (row["hash_low"], row["hash_high"])
                == (top["hash_low"], top["hash_high"]),
                f"{event} player layer {top['name']}",
            )
            if layer["speed"] != 1:
                raise ValueError(f"{event}/{top['name']} layer speed differs")
            for node in walk(top):
                name = str(node.get("name", ""))
                if name.endswith(".z2d"):
                    node_context[name[:-4]] = (node, layer, top["name"])

        def exact_key(z2d_name: str) -> tuple[dict, dict, str]:
            node, layer, layer_name = node_context[z2d_name]
            if node["time_remap_pointer"] is not None:
                raise ValueError(f"{event}/{z2d_name} has time remap")
            motion = one(
                node["motions"],
                lambda row: row.get("is_z2d_motion") is True,
                f"{event}/{z2d_name} Z2D motion",
            )
            key = one(motion["keys"], lambda row: row["index"] == 0, "motion key 0")
            return key, layer, layer_name

        cues = []
        evidence_rows = []
        for z2d_name, (request_id, expected_start, expected_end) in (
            EXPECTED_CAPTION_NODES[event].items()
        ):
            key, layer, layer_name = exact_key(z2d_name)
            start_frame = int(key["floats"][0])
            end_frame = int(key["floats"][1]) + 1
            if (start_frame, end_frame) != (expected_start, expected_end):
                raise ValueError(f"{event}/{z2d_name} motion interval differs")
            cue = {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "event_global_start_frame": start_frame,
                "event_global_start_ms": round_frame_ms(start_frame),
                "event_global_end_frame_exclusive": end_frame,
                "event_global_end_ms": round_frame_ms(end_frame),
            }
            if not request_id:
                cue["subtitle_only"] = True
                catalog = one(
                    subtitle_rows,
                    lambda row, z2d_name=z2d_name: row.get("event_name") == event
                    and row.get("z2d_name") == z2d_name
                    and not row.get("sound_request_id"),
                    f"{event}/{z2d_name} graphical subtitle row",
                )
                if catalog["display_text"] != EXPECTED_GRAPHICAL_TEXT[z2d_name]:
                    raise ValueError(f"{event}/{z2d_name} graphical text differs")
                existing = any(
                    row.get("z2d_name") == z2d_name
                    for row in manifest.get("subtitles", [])
                )
                if not existing:
                    cue["recover_missing_subtitle"] = {
                        "text": catalog["display_text"],
                        "speaker_code": "",
                        "subtitle_source": "graphical_display_text",
                        "evidence": "subtitle_catalog_and_runtime_scene_motion_key",
                    }
            else:
                sound = one(
                    sound_rows,
                    lambda row, request_id=request_id, z2d_name=z2d_name: row.get(
                        "event_name"
                    )
                    == event
                    and row.get("sound_request_id") == request_id
                    and row.get("z2d_name") == z2d_name,
                    f"{event}/{request_id} sound row",
                )
                manifest_audio = one(
                    manifest["audio"],
                    lambda row, request_id=request_id, z2d_name=z2d_name: str(
                        row.get("request_id", "")
                    )
                    == request_id
                    and row.get("z2d_name") == z2d_name,
                    f"{event}/{request_id} manifest audio",
                )
                if (
                    sound["ogg_name"] != manifest_audio["ogg_name"]
                    or manifest_audio.get("event_global_start_resolved") is not False
                ):
                    raise ValueError(f"{event}/{request_id} child-local source differs")
            cues.append(cue)
            evidence_rows.append(
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
                }
            )

        observed_requests = sorted(
            str(row["request_id"])
            for row in manifest["audio"]
            if row.get("source") == "z2d_req_sound"
        )
        if observed_requests != sorted(EXPECTED_Z2D_REQUESTS[event]):
            raise ValueError(f"{event} expected request set differs")
        event_dgm_names = {
            row["dgm_name"] for row in dgm_rows if row.get("event_name") == event
        }
        if event == "ac6005_014":
            expected_story = {
                "ac6005_014_c01",
                "ac6005_014_c03",
                "ac6005_014_c04",
                "ac6005_014_c05",
                "ac6005_014_c06",
                "ac6005_014_c06_LP",
            }
            if not expected_story <= event_dgm_names:
                raise ValueError("ac6005_014 clean-story DGM sequence differs")
        event_results[event] = {
            "status": "event_global_parent_scene_motion_exact",
            "event_code_hex": EXPECTED_EVENT_CODES[event],
            "parent_cut": {
                "scene": scene["name"],
                "cut": cut["cut_name"],
                "instance_offset_frames": cut["instance_offset_frames"],
                "cut_start_frame": cut["cut_start_frame"],
                "cut_end_frame": cut["cut_end_frame"],
            },
            "caption_motion_evidence": evidence_rows,
            "override_required": True,
        }
        override_payloads[event] = {
            "schema": "magireco-z2d-event-timing-override-v1",
            "event": event,
            "event_code_hex": EXPECTED_EVENT_CODES[event],
            "frame_rate": "30/1",
            "expected_z2d_request_ids": list(EXPECTED_Z2D_REQUESTS[event]),
            "cues": cues,
        }

    authority_path = out_dir / "P18_AC6005_CU_SUCCESS_EVENT_GLOBAL_TIMING_AUTHORITY.json"
    authority = {
        "schema": "magireco-p18-cu-success-event-global-timing-authority-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "route": {
            "kind": 173,
            "row_index": 10,
            "meaning": "CU success",
            "events": list(ROUTE_EVENTS),
            "rows": dirinfo_route,
        },
        "runtime_safety": {
            "protected_processes_unchanged": True,
            "crash_buffer_empty": True,
            "no_app_restarted_closed_or_switched": True,
        },
        "mechanism": {
            "authority": "IDA field semantics plus bounded live scene graph",
            "frame_rule": "event_global_frame = parent cut frame plus first Z2D motion key start; speed=1 and no time remap",
            "ac6005_013_policy": "retain official resolved runtime event manifest",
            "old_candidate_defects": [
                "ac6005_010 request 5409 used child-local frame 0 instead of event-global frame 96",
                "ac6005_014 request 2795 merged cap6005_mb_iro_015_03 forty frames early instead of preserving its separate frame-335 continuation",
            ],
        },
        "source_bindings": bindings,
        "events": event_results,
        "status": "PASS",
    }
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    authority_binding = binding(authority_path)

    override_paths = []
    for event in OVERRIDE_EVENTS:
        payload = override_payloads[event]
        payload["authority_path"] = str(authority_path.resolve())
        payload["source_bindings"] = [authority_binding, *bindings.values()]
        path = override_dir / f"{event}_parent_scene_motion_key_v1.json"
        if path.exists():
            raise ValueError(f"refusing to overwrite timing override: {path}")
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        override_paths.append(binding(path))

    summary = {
        "schema": "magireco-p18-cu-success-timing-authority-summary-v1",
        "status": "PASS",
        "route_events": list(ROUTE_EVENTS),
        "override_events": list(OVERRIDE_EVENTS),
        "authority": authority_binding,
        "overrides": override_paths,
        "human_playback_required": True,
        "publishable": False,
    }
    (out_dir / "SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(Path(__file__).resolve(), out_dir / Path(__file__).name)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
