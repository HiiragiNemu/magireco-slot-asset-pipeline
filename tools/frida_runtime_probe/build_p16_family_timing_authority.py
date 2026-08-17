from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from tools.frida_runtime_probe.build_event_production_manifests import file_sha256


RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = RESEARCH_ROOT / "ida_static_scheduler_analysis_v1_20260808"
SOURCE_MANIFEST_ROOT = (
    RESEARCH_ROOT / "_repro_audit_v67r2_inputs_r3_20260806" / "events"
)
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_p16_family_scene_motion_v15_20260817"
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT / "p16_ac6003_family_event_global_timing_authority_v1r1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)
EVENTS = (
    "ac6003_006",
    "ac6003_007",
    "ac6003_009",
    "ac6003_010",
    "ac6003_014",
    "ac6003_015",
)
EXISTING_009_OVERRIDE = (
    DEFAULT_OVERRIDE_ROOT / "ac6003_009_parent_scene_motion_key_v1.json"
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


def round_frame_ms(frame: int, frame_rate: Fraction = Fraction(30, 1)) -> int:
    return int(Fraction(frame * 1000, 1) / frame_rate + Fraction(1, 2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--override-out-dir", default=str(DEFAULT_OVERRIDE_ROOT))
    args = parser.parse_args()
    out_dir = Path(args.out_dir).resolve()
    override_dir = Path(args.override_out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    override_dir.mkdir(parents=True, exist_ok=True)

    sources = {
        "exact_libgameproc": STATIC_ROOT / "sample" / "libGameProc.so",
        "runtime_family_scene_motion": (
            RUNTIME_ROOT / "P16_AC6003_FAMILY_RUNTIME_SCENE_MOTION.json"
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
    }
    for event in EVENTS:
        sources[f"source_manifest_{event}"] = SOURCE_MANIFEST_ROOT / f"{event}.json"
    bindings = {name: binding(path) for name, path in sources.items()}

    runtime = json.loads(
        sources["runtime_family_scene_motion"].read_text(encoding="utf-8")
    )
    if not runtime["protected_processes_unchanged"] or not runtime["crash_buffer_empty"]:
        raise ValueError("family capture did not preserve all foreground games")
    if set(runtime["events"]) != {
        "ac6003_005",
        "ac6003_006",
        "ac6003_007",
        "ac6003_009",
        "ac6003_010",
        "ac6003_014",
        "ac6003_015",
    }:
        raise ValueError("family capture event set mismatch")

    event_results: dict[str, dict] = {}
    override_cues: dict[str, list[dict]] = {}
    for event in EVENTS:
        value = runtime["events"][event]
        manifest = json.loads(
            (SOURCE_MANIFEST_ROOT / f"{event}.json").read_text(encoding="utf-8")
        )
        if value["event_code"].lower() != manifest["event_code_hex"].lower():
            raise ValueError(f"runtime/manifest event-code mismatch for {event}")
        scene = one(value["scenes"], lambda row: row["name"] == event, f"{event} scene")
        cut = one(scene["cuts"], lambda row: row["cut_name"] == event, f"{event} cut")
        if cut["instance_offset_frames"] != 0 or cut["cut_start_frame"] != 0:
            raise ValueError(f"{event} main cut is not at exact zero offset/start")
        layers = {
            (row["hash_low"], row["hash_high"]): row for row in value["layers"]
        }
        node_context: dict[str, tuple[dict, dict]] = {}
        for top in cut["nodes"]:
            player_layer = one(
                value["layers"],
                lambda row, top=top: (
                    row["hash_low"], row["hash_high"]
                ) == (top["hash_low"], top["hash_high"]),
                f"{event} player layer {top['name']}",
            )
            if player_layer["speed"] != 1:
                raise ValueError(f"{event} layer {top['name']} speed is not 1")
            for node in walk(top):
                if str(node.get("name", "")).endswith(".z2d"):
                    node_context[node["name"][:-4]] = (node, player_layer)

        cues: list[dict] = []
        audio_keys: set[tuple[str, str]] = set()
        audio_evidence: list[dict] = []
        for row in manifest["audio"]:
            if row.get("event_global_start_resolved") is not False:
                continue
            request_id = str(row.get("request_id", ""))
            z2d_name = str(row.get("z2d_name", ""))
            node, layer = node_context[z2d_name]
            if node["time_remap_pointer"] is not None:
                raise ValueError(f"{event}/{z2d_name} has a time remap")
            motion = one(
                node["motions"],
                lambda item: item.get("is_z2d_motion") is True,
                f"{event}/{z2d_name} Z2D motion",
            )
            key = one(motion["keys"], lambda item: item["index"] == 0, "first key")
            global_frame = int(
                cut["instance_offset_frames"]
                + key["floats"][0]
                - cut["cut_start_frame"]
            )
            global_end_exclusive = int(key["floats"][1]) + 1
            cue = {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "event_global_start_frame": global_frame,
                "event_global_start_ms": round_frame_ms(global_frame),
                "event_global_end_frame_exclusive": global_end_exclusive,
                "event_global_end_ms": round_frame_ms(global_end_exclusive),
            }
            cues.append(cue)
            audio_keys.add((request_id, z2d_name))
            audio_evidence.append(
                {
                    "request_id": request_id,
                    "z2d_name": z2d_name,
                    "old_child_local_start_ms": row["start_ms"],
                    "runtime_motion_fields": key["floats"],
                    "runtime_motion_flags": key["flags"],
                    "layer_name": next(
                        top["name"]
                        for top in cut["nodes"]
                        if any(candidate is node for candidate in walk(top))
                    ),
                    "layer_speed": layer["speed"],
                    "time_remap_pointer": node["time_remap_pointer"],
                    "event_global_start_frame": global_frame,
                    "event_global_start_ms": cue["event_global_start_ms"],
                    "event_global_end_frame_exclusive": global_end_exclusive,
                    "event_global_end_ms": cue["event_global_end_ms"],
                }
            )

        subtitle_evidence: list[dict] = []
        for row in manifest["subtitles"]:
            if row.get("event_global_start_resolved") is not False:
                continue
            request_id = str(row.get("voice_request_id", ""))
            z2d_name = str(row.get("z2d_name", ""))
            node, layer = node_context[z2d_name]
            if node["time_remap_pointer"] is not None:
                raise ValueError(f"{event}/{z2d_name} has a time remap")
            motion = one(
                node["motions"],
                lambda item: item.get("is_z2d_motion") is True,
                f"{event}/{z2d_name} subtitle motion",
            )
            key = one(motion["keys"], lambda item: item["index"] == 0, "first key")
            global_start_frame = int(key["floats"][0])
            evidence = {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "old_child_local_start_ms": row["start_ms"],
                "old_child_local_end_ms": row["end_ms"],
                "runtime_motion_fields": key["floats"],
                "runtime_motion_flags": key["flags"],
                "layer_speed": layer["speed"],
                "time_remap_pointer": node["time_remap_pointer"],
                "event_global_start_frame": global_start_frame,
                "event_global_start_ms": round_frame_ms(global_start_frame),
            }
            if not request_id:
                global_end_exclusive = int(key["floats"][1]) + 1
                cue = {
                    "request_id": "",
                    "z2d_name": z2d_name,
                    "subtitle_only": True,
                    "event_global_start_frame": global_start_frame,
                    "event_global_start_ms": round_frame_ms(global_start_frame),
                    "event_global_end_frame_exclusive": global_end_exclusive,
                    "event_global_end_ms": round_frame_ms(global_end_exclusive),
                }
                cues.append(cue)
                evidence.update(
                    {
                        "event_global_end_frame_exclusive": global_end_exclusive,
                        "event_global_end_ms": cue["event_global_end_ms"],
                    }
                )
            elif (request_id, z2d_name) not in audio_keys:
                raise ValueError(
                    f"{event}/{request_id}/{z2d_name} subtitle lacks audio cue"
                )
            subtitle_evidence.append(evidence)

        if not cues:
            raise ValueError(f"{event} produced no exact timing cues")
        override_cues[event] = cues
        event_results[event] = {
            "event_code_hex": manifest["event_code_hex"],
            "parent_scene": scene["name"],
            "parent_cut": cut["cut_name"],
            "parent_instance_offset_frames": cut["instance_offset_frames"],
            "cut_start_frame": cut["cut_start_frame"],
            "audio_cues": audio_evidence,
            "subtitle_cues": subtitle_evidence,
            "override_cues": cues,
            "all_child_local_rows_covered": True,
        }

    authority = {
        "schema": "magireco-p16-family-event-global-timing-authority-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ALL_AC6003_P16_CHILD_LOCAL_ROWS_RESOLVED",
        "source_bindings": bindings,
        "protected_processes_before": runtime["protected_processes_before"],
        "protected_processes_after": runtime["protected_processes_after"],
        "protected_processes_unchanged": True,
        "crash_buffer_empty": True,
        "derivation": (
            "event_global_frame = parent cut instance offset + runtime-loaded child "
            "Z2D motion-key start - cut start; every covered main cut is offset 0, "
            "cut start 0, layer speed 1, with no child time-remap"
        ),
        "events": event_results,
        "old_media_status": "QUARANTINED",
        "replacement_media_status": "HUMAN_PLAYBACK_REQUIRED",
    }
    authority_path = out_dir / "P16_AC6003_FAMILY_EVENT_GLOBAL_TIMING_AUTHORITY.json"
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    authority_binding = binding(authority_path)

    override_paths: dict[str, str] = {"ac6003_009": str(EXISTING_009_OVERRIDE)}
    common_binding_names = (
        "exact_libgameproc",
        "runtime_family_scene_motion",
        "ida_motion_fields",
        "ida_parent_child",
    )
    for event in EVENTS:
        if event == "ac6003_009":
            continue
        payload = {
            "schema": "magireco-z2d-event-timing-override-v1",
            "event": event,
            "event_code_hex": event_results[event]["event_code_hex"],
            "frame_rate": "30/1",
            "authority_path": str(authority_path),
            "source_bindings": [
                authority_binding,
                *(bindings[name] for name in common_binding_names),
                bindings[f"source_manifest_{event}"],
            ],
            "cues": override_cues[event],
        }
        target = override_dir / f"{event}_parent_scene_motion_key_v1.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        override_paths[event] = str(target)

    (out_dir / "README.md").write_text(
        "# P16 ac6003 family event-global timing authority\n\n"
        "The bounded runtime capture directly reopened all seven P16 event objects. "
        "Six events contained child-local rows; every corresponding main cut had "
        "offset/start 0, every matching layer had speed 1, and every exact child "
        "node had no time remap. Runtime-loaded motion keys provide per-child starts, "
        "including separate graphical-only continuation text. No uniform shift is used. "
        "Old P16 remains quarantined; replacements require human playback.\n",
        encoding="utf-8",
    )
    (out_dir / "VERIFICATION_RECORD.txt").write_text(
        "command=python -m tools.frida_runtime_probe.build_p16_family_timing_authority\n"
        "exit_status=0\nevent_count=6\nprotected_processes_unchanged=true\n"
        "crash_buffer_empty=true\nall_child_local_rows_covered=true\n"
        "uniform_shift_used=false\nold_media_status=QUARANTINED\n"
        "replacement_media_status=HUMAN_PLAYBACK_REQUIRED\n",
        encoding="utf-8",
    )
    shutil.copy2(Path(__file__).resolve(), out_dir / Path(__file__).name)
    generated = [
        authority_path,
        out_dir / "README.md",
        out_dir / "VERIFICATION_RECORD.txt",
        out_dir / Path(__file__).name,
    ]
    (out_dir / "SHA256SUMS.txt").write_text(
        "".join(f"{file_sha256(path)} *{path.name}\n" for path in generated),
        encoding="ascii",
    )
    for path in [*generated, out_dir / "SHA256SUMS.txt", *map(Path, override_paths.values())]:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"generated role missing or empty: {path}")
    print(
        json.dumps(
            {
                "status": "OK",
                "authority": str(authority_path),
                "events": list(EVENTS),
                "override_paths": override_paths,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
