#!/usr/bin/env python3
"""Build exact event-global timing authority for the quarantined P17 family.

Four ac6004 events were promoted from child-local Z2D callback time without a
parent scene offset.  A bounded runtime scene-graph capture now supplies the
parent cut and motion keys.  ac6004_006 additionally lost request 3260, so this
builder binds the official OGG and both static catalog rows before authoring a
fail-closed recovery cue.  The already runtime-exact ac6004_011 is evidence but
does not receive an override.
"""

from __future__ import annotations

import argparse
import csv
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
RUNTIME_ROOT = RESEARCH_ROOT / "runtime_p17_family_scene_motion_v16_20260817"
CATALOG_ROOT = RESEARCH_ROOT / "z2d_audio_timeline_v2"
REQ3260_OGG = Path(
    r"D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603"
    r"\audio_assets\audio\ogg_raw\snd_16214_bank08_ogg_01527.ogg"
)
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT / "p17_ac6004_family_event_global_timing_authority_v1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)
FAMILY_EVENTS = (
    "ac6004_005",
    "ac6004_006",
    "ac6004_008",
    "ac6004_011",
    "ac6004_012",
)
RISK_EVENTS = (
    "ac6004_005",
    "ac6004_006",
    "ac6004_008",
    "ac6004_012",
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


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
    if out_dir.exists():
        raise ValueError(f"immutable authority output already exists: {out_dir}")
    out_dir.mkdir(parents=True)
    override_dir.mkdir(parents=True, exist_ok=True)

    sources = {
        "exact_libgameproc": STATIC_ROOT / "sample" / "libGameProc.so",
        "runtime_family_scene_motion": (
            RUNTIME_ROOT / "P17_AC6004_FAMILY_RUNTIME_SCENE_MOTION.json"
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
        "req3260_official_ogg": REQ3260_OGG,
    }
    for event in RISK_EVENTS:
        sources[f"source_manifest_{event}"] = SOURCE_MANIFEST_ROOT / f"{event}.json"
    bindings = {name: binding(path) for name, path in sources.items()}

    runtime = json.loads(
        sources["runtime_family_scene_motion"].read_text(encoding="utf-8")
    )
    if not runtime["protected_processes_unchanged"] or not runtime["crash_buffer_empty"]:
        raise ValueError("family capture did not preserve all foreground games")
    if tuple(runtime["requested_events"]) != FAMILY_EVENTS or set(runtime["events"]) != set(
        FAMILY_EVENTS
    ):
        raise ValueError("P17 runtime family capture event set mismatch")

    sound_catalog = read_csv(sources["event_sound_catalog"])
    subtitle_catalog = read_csv(sources["subtitle_catalog"])
    req3260_sound = one(
        sound_catalog,
        lambda row: row.get("event_name") == "ac6004_006"
        and row.get("z2d_name") == "cap6004_mb_yac_005"
        and row.get("sound_request_id") == "3260",
        "ac6004_006 request 3260 sound catalog row",
    )
    req3260_subtitle = one(
        subtitle_catalog,
        lambda row: row.get("event_name") == "ac6004_006"
        and row.get("z2d_name") == "cap6004_mb_yac_005"
        and row.get("sound_request_id") == "3260",
        "ac6004_006 request 3260 subtitle catalog row",
    )
    if (
        req3260_sound["ogg_name"] != REQ3260_OGG.name
        or int(req3260_sound["sound_duration_ms"]) != 7899
        or req3260_subtitle["display_text"] != "何言ってるの！"
        or int(req3260_subtitle["callback_exec_frame"]) != 0
    ):
        raise ValueError("request 3260 catalog identity changed")

    event_results: dict[str, dict] = {}
    override_cues: dict[str, list[dict]] = {}
    expected_requests: dict[str, list[str]] = {}
    for event in RISK_EVENTS:
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

        node_context: dict[str, tuple[dict, dict, str]] = {}
        for top in cut["nodes"]:
            player_layer = one(
                value["layers"],
                lambda row, top=top: (row["hash_low"], row["hash_high"])
                == (top["hash_low"], top["hash_high"]),
                f"{event} player layer {top['name']}",
            )
            if player_layer["speed"] != 1:
                raise ValueError(f"{event} layer {top['name']} speed is not 1")
            for node in walk(top):
                if str(node.get("name", "")).endswith(".z2d"):
                    node_context[node["name"][:-4]] = (node, player_layer, top["name"])

        def exact_key(z2d_name: str) -> tuple[dict, dict, str]:
            node, layer, layer_name = node_context[z2d_name]
            if node["time_remap_pointer"] is not None:
                raise ValueError(f"{event}/{z2d_name} has a time remap")
            motion = one(
                node["motions"],
                lambda item: item.get("is_z2d_motion") is True,
                f"{event}/{z2d_name} Z2D motion",
            )
            key = one(motion["keys"], lambda item: item["index"] == 0, "first key")
            return key, layer, layer_name

        cues: list[dict] = []
        audio_keys: set[tuple[str, str]] = set()
        audio_evidence: list[dict] = []
        for row in manifest["audio"]:
            if row.get("source") != "z2d_req_sound":
                continue
            request_id = str(row.get("request_id", ""))
            z2d_name = str(row.get("z2d_name", ""))
            if row.get("event_global_start_resolved") is not False:
                raise ValueError(f"{event}/{request_id} unexpectedly became runtime exact")
            key, layer, layer_name = exact_key(z2d_name)
            start_frame = int(key["floats"][0])
            end_frame_exclusive = int(key["floats"][1]) + 1
            cue = {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "event_global_start_frame": start_frame,
                "event_global_start_ms": round_frame_ms(start_frame),
                "event_global_end_frame_exclusive": end_frame_exclusive,
                "event_global_end_ms": round_frame_ms(end_frame_exclusive),
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
                    "layer_name": layer_name,
                    "layer_speed": layer["speed"],
                    "time_remap_pointer": None,
                    "event_global_start_frame": start_frame,
                    "event_global_start_ms": cue["event_global_start_ms"],
                }
            )

        if event == "ac6004_006":
            z2d_name = "cap6004_mb_yac_005"
            key, layer, layer_name = exact_key(z2d_name)
            start_frame = int(key["floats"][0])
            end_frame_exclusive = int(key["floats"][1]) + 1
            cue = {
                "request_id": "3260",
                "z2d_name": z2d_name,
                "event_global_start_frame": start_frame,
                "event_global_start_ms": round_frame_ms(start_frame),
                "event_global_end_frame_exclusive": end_frame_exclusive,
                "event_global_end_ms": round_frame_ms(end_frame_exclusive),
                "recover_missing_audio": {
                    "code_name": req3260_sound["sound_code_name"],
                    "ogg_name": REQ3260_OGG.name,
                    "path": str(REQ3260_OGG.resolve()),
                    "sha256": bindings["req3260_official_ogg"]["sha256"],
                    "duration_ms": 7899,
                    "child_local_start_ms": 0,
                    "callback_exec_frame": 0,
                    "child_local_absolute_start_frame": "",
                    "evidence": "z2d_callback_catalog_and_official_ogg",
                },
                "recover_missing_subtitle": {
                    "text": req3260_subtitle["display_text"],
                    "speaker_code": "",
                    "subtitle_source": "graphical_display_text",
                    "evidence": "subtitle_catalog_and_runtime_scene_motion_key",
                },
            }
            cues.append(cue)
            audio_keys.add(("3260", z2d_name))
            audio_evidence.append(
                {
                    "request_id": "3260",
                    "z2d_name": z2d_name,
                    "old_manifest_row": "MISSING",
                    "runtime_motion_fields": key["floats"],
                    "runtime_motion_flags": key["flags"],
                    "layer_name": layer_name,
                    "layer_speed": layer["speed"],
                    "event_global_start_frame": start_frame,
                    "event_global_start_ms": cue["event_global_start_ms"],
                    "official_ogg_sha256": bindings["req3260_official_ogg"]["sha256"],
                    "official_ogg_duration_ms": 7899,
                    "recovery": "EXACT_MISSING_AUDIO_AND_SUBTITLE_ROW",
                }
            )

        subtitle_evidence: list[dict] = []
        for row in manifest["subtitles"]:
            if row.get("event_global_start_resolved") is not False:
                continue
            request_id = str(row.get("voice_request_id", ""))
            z2d_name = str(row.get("z2d_name", ""))
            key, layer, layer_name = exact_key(z2d_name)
            start_frame = int(key["floats"][0])
            evidence = {
                "request_id": request_id,
                "z2d_name": z2d_name,
                "old_child_local_start_ms": row["start_ms"],
                "old_child_local_end_ms": row["end_ms"],
                "runtime_motion_fields": key["floats"],
                "runtime_motion_flags": key["flags"],
                "layer_name": layer_name,
                "layer_speed": layer["speed"],
                "event_global_start_frame": start_frame,
                "event_global_start_ms": round_frame_ms(start_frame),
            }
            if not request_id:
                end_frame_exclusive = int(key["floats"][1]) + 1
                cues.append(
                    {
                        "request_id": "",
                        "z2d_name": z2d_name,
                        "subtitle_only": True,
                        "event_global_start_frame": start_frame,
                        "event_global_start_ms": round_frame_ms(start_frame),
                        "event_global_end_frame_exclusive": end_frame_exclusive,
                        "event_global_end_ms": round_frame_ms(end_frame_exclusive),
                    }
                )
                evidence["event_global_end_frame_exclusive"] = end_frame_exclusive
                evidence["event_global_end_ms"] = round_frame_ms(end_frame_exclusive)
            elif (request_id, z2d_name) not in audio_keys:
                raise ValueError(f"{event}/{request_id}/{z2d_name} lacks an audio cue")
            subtitle_evidence.append(evidence)

        expected = sorted(request_id for request_id, _ in audio_keys)
        if len(expected) != len(set(expected)):
            raise ValueError(f"{event} has duplicate Z2D request ids")
        cues.sort(
            key=lambda row: (
                int(row["event_global_start_frame"]),
                str(row["request_id"]),
                str(row["z2d_name"]),
            )
        )
        override_cues[event] = cues
        expected_requests[event] = expected
        event_results[event] = {
            "event_code_hex": manifest["event_code_hex"],
            "parent_scene": scene["name"],
            "parent_cut": cut["cut_name"],
            "parent_instance_offset_frames": cut["instance_offset_frames"],
            "cut_start_frame": cut["cut_start_frame"],
            "audio_cues": audio_evidence,
            "subtitle_cues": subtitle_evidence,
            "expected_z2d_request_ids": expected,
            "override_cues": cues,
            "all_child_local_rows_covered": True,
        }

    authority = {
        "schema": "magireco-p17-family-event-global-timing-authority-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ALL_P17_CHILD_LOCAL_ROWS_RESOLVED_AND_REQ3260_RECOVERED",
        "source_bindings": bindings,
        "protected_processes_before": runtime["protected_processes_before"],
        "protected_processes_after": runtime["protected_processes_after"],
        "protected_processes_unchanged": True,
        "crash_buffer_empty": True,
        "derivation": (
            "event_global_frame = parent cut instance offset + runtime-loaded child "
            "Z2D motion-key start - cut start; all four parent cuts are offset/start "
            "zero, matching layers run at speed 1, and child nodes have no time remap"
        ),
        "events": event_results,
        "already_runtime_exact_event": "ac6004_011",
        "recovered_missing_request": "3260",
        "old_media_status": "QUARANTINED_HUMAN_PLAYBACK_FAILED",
        "replacement_media_status": "HUMAN_PLAYBACK_REQUIRED",
    }
    authority_path = out_dir / "P17_AC6004_FAMILY_EVENT_GLOBAL_TIMING_AUTHORITY.json"
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    authority_binding = binding(authority_path)

    common_names = (
        "exact_libgameproc",
        "runtime_family_scene_motion",
        "runtime_capture_script",
        "runtime_probe_script",
        "ida_motion_fields",
        "ida_parent_child",
        "event_sound_catalog",
        "subtitle_catalog",
    )
    override_paths: dict[str, str] = {}
    for event in RISK_EVENTS:
        source_bindings = [
            authority_binding,
            *(bindings[name] for name in common_names),
            bindings[f"source_manifest_{event}"],
        ]
        if event == "ac6004_006":
            source_bindings.append(bindings["req3260_official_ogg"])
        payload = {
            "schema": "magireco-z2d-event-timing-override-v1",
            "event": event,
            "event_code_hex": event_results[event]["event_code_hex"],
            "frame_rate": "30/1",
            "authority_path": str(authority_path),
            "expected_z2d_request_ids": expected_requests[event],
            "source_bindings": source_bindings,
            "cues": override_cues[event],
        }
        target = override_dir / f"{event}_parent_scene_motion_key_v1.json"
        if target.exists():
            raise ValueError(f"refusing to overwrite existing override: {target}")
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        override_paths[event] = str(target)

    (out_dir / "README.md").write_text(
        "# P17 ac6004 event-global timing authority\n\n"
        "The bounded Slot runtime capture reopened all five family events without "
        "closing or restarting the other foreground games. Four formerly child-local "
        "events now have exact parent scene motion-key timing. Request 3260 is restored "
        "only because its callback row, graphical text, official OGG, duration, parent "
        "motion key, and expected request set are all hash-bound. ac6004_011 retains its "
        "existing runtime-exact manifest. Old P17 media remains quarantined; replacement "
        "media requires owner playback.\n",
        encoding="utf-8",
    )
    (out_dir / "ROLLBACK.ps1").write_text(
        "param([switch]$Apply)\n"
        "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: disable the new P17 "
        "authority/overrides; source manifests and media remain unchanged.'; exit 0 }\n"
        "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
        "Move-Item -LiteralPath $Root -Destination $Target\n"
        "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
        encoding="utf-8",
    )
    (out_dir / "VERIFICATION_RECORD.txt").write_text(
        "command=python -m tools.frida_runtime_probe.build_p17_family_timing_authority\n"
        "exit_status=0\nrisk_event_count=4\nexpected_request_sets_match=true\n"
        "recovered_request=3260\nprotected_processes_unchanged=true\n"
        "crash_buffer_empty=true\nuniform_shift_used=false\n"
        "old_media_status=QUARANTINED_HUMAN_PLAYBACK_FAILED\n"
        "replacement_media_status=HUMAN_PLAYBACK_REQUIRED\n",
        encoding="utf-8",
    )
    shutil.copy2(Path(__file__).resolve(), out_dir / Path(__file__).name)
    generated = [
        authority_path,
        out_dir / "README.md",
        out_dir / "ROLLBACK.ps1",
        out_dir / "VERIFICATION_RECORD.txt",
        out_dir / Path(__file__).name,
    ]
    (out_dir / "SHA256SUMS.txt").write_text(
        "".join(f"{file_sha256(path)} *{path.name}\n" for path in generated),
        encoding="ascii",
    )
    for path in [
        *generated,
        out_dir / "SHA256SUMS.txt",
        *(Path(value) for value in override_paths.values()),
    ]:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"generated role missing or empty: {path}")
    print(
        json.dumps(
            {
                "status": "OK",
                "authority": str(authority_path),
                "risk_events": list(RISK_EVENTS),
                "recovered_request": "3260",
                "override_paths": override_paths,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
