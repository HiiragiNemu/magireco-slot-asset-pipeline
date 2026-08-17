#!/usr/bin/env python3
"""Close child-local timing for the fourteen ac7101-ac7107 story events.

The seven DirInfo kinds contain repeated single-event occurrences, not a proven
``_001 -> _002`` session.  This builder therefore authors timing authority only
for fourteen independent 416x232 event archives.  It combines the exact-hash
Slot IDA scheduler model with one bounded live scene-graph capture and rejects
any source that does not retain the SOUND_DIVIDE_TBL SE/VOICE-only contract.
"""

from __future__ import annotations

import argparse
import csv
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
RUNTIME_ROOT = (
    RESEARCH_ROOT / "runtime_ac7101_ac7107_story_scene_motion_v76_20260817"
)
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
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT / "ac7101_ac7107_event_global_timing_authority_v1_20260817"
)
DEFAULT_OVERRIDE_ROOT = (
    REPO_ROOT / "tools" / "frida_runtime_probe" / "z2d_event_timing_overrides"
)

BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"
EVENT_CODES = {
    "ac7101_001": "0x514d6c62404e6f53",
    "ac7101_002": "0x4e72634b404e6f53",
    "ac7102_001": "0x63426d544f59427a",
    "ac7102_002": "0x622d346f4f59427a",
    "ac7103_001": "0x2d2d6f485f79616b",
    "ac7103_002": "0x796a44505f79616b",
    "ac7104_001": "0x554749633f647837",
    "ac7104_002": "0x2d3252633f647837",
    "ac7105_001": "0x437674744131643d",
    "ac7105_002": "0x642166364131643d",
    "ac7106_001": "0x3032577654432b24",
    "ac7106_002": "0x4856782454432b24",
    "ac7107_001": "0x625076413532772b",
    "ac7107_002": "0x4c7859523532772b",
}
EVENTS = tuple(EVENT_CODES)
EXPECTED_REQUESTS = {
    "ac7101_001": ("8449", "8450"),
    "ac7101_002": ("8459", "8460", "8461"),
    "ac7102_001": ("8465", "8466", "8467", "8468"),
    "ac7102_002": ("8490", "8491", "8492", "8493"),
    "ac7103_001": ("8518", "8519", "8520", "8521"),
    "ac7103_002": ("8530", "8531", "8532", "8533"),
    "ac7104_001": ("8547", "8548"),
    "ac7104_002": ("8620", "8621", "8622", "8623"),
    "ac7105_001": ("9967", "8635", "9965", "8637", "9966", "9968"),
    "ac7105_002": ("8691", "8692", "8693", "8694", "8695"),
    "ac7106_001": ("8710", "8711", "8712", "8713"),
    "ac7106_002": ("8808", "8809", "8810", "8811"),
    "ac7107_001": ("8960", "8961", "8962", "8963", "8965"),
    "ac7107_002": ("9005", "9006", "9007", "9008"),
}
EXPECTED_GRAPHICAL_Z2D = {
    "ac7101_001": ("cap7101_story1_qb_001", "cap7101_story1_iro_002", "cap7101_story1_iro_003", "cap7101_story1_iro_004"),
    "ac7101_002": ("cap7101_story1_iro_005", "cap7101_story1_iro_006", "cap7101_story1_iro_007", "cap7101_story1_iro_008"),
    "ac7102_001": ("cap7102_story2_mom_001", "cap7102_story2_mom_002", "cap7102_story2_ren_003", "cap7102_story2_mom_004", "cap7102_story2_mom_005"),
    "ac7102_002": ("cap7102_story2_mom_006", "cap7102_story2_mom_008", "cap7102_story2_mom_009", "cap7102_story2_mom_010"),
    "ac7103_001": ("cap7103_story3_tur_001", "cap7103_story3_tur_002", "cap7103_story3_tur_003", "cap7103_story3_tur_004", "cap7103_story3_tur_005"),
    "ac7103_002": ("cap7103_story3_iro_006", "cap7103_story3_iro_007", "cap7103_story3_iro_008", "cap7103_story3_ui_009", "cap7103_story3_ui_010"),
    "ac7104_001": ("cap7104_story4_fer_001", "cap7104_story4_fer_002_01"),
    "ac7104_002": ("cap7104_story4_kyo_003", "cap7104_story4_kyo_004", "cap7104_story4_tks_005", "cap7104_story4_tks_006", "cap7104_story4_tky_007"),
    "ac7105_001": ("cap7105_story5_ai_001", "cap7105_story5_iro_002", "cap7105_story5_ai_003", "cap7105_story5_iro_004", "cap7105_story5_ai_005", "cap7105_story5_ai_006"),
    "ac7105_002": ("cap7105_story5_ai_007", "cap7105_story5_ai_008", "cap7105_story5_ai_009", "cap7105_story5_san_010", "cap7105_story5_san_011_01"),
    "ac7106_001": ("cap7105_story6_iro_000", "cap7106_story6_tou_001", "cap7106_story6_tou_002", "cap7106_story6_tou_003"),
    "ac7106_002": ("cap7106_story6_mam_004", "cap7106_story6_mam_005", "cap7106_story6_mam_006", "cap7106_story6_mam_007"),
    "ac7107_001": ("cap7107_story7_sig_001", "cap7107_story7_yac_002", "cap7107_story7_sig_003", "cap7107_story7_yac_004", "cap7107_story7_sig_005"),
    "ac7107_002": ("cap7107_story7_nem_006", "cap7107_story7_nem_007", "cap7107_story7_nem_008", "cap7107_story7_yac_009", "cap7107_story7_kur_010"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def validate_dirinfo(rows: list[dict[str, str]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for offset, family in enumerate(f"ac710{i}" for i in range(1, 8)):
        kind = str(180 + offset)
        selected = [row for row in rows if row.get("kind") == kind]
        expected = []
        for row_index in range(20):
            expected.append((row_index, "0", f"{family}_{'001' if row_index < 10 else '002'}", "2"))
        expected.append((19, "5", f"{family}_003", "0"))
        observed = [
            (
                int(row["row_index"]),
                row["selector_raw"],
                row["scene_name"],
                row["resolved_source_count"],
            )
            for row in selected
        ]
        if observed != expected:
            raise ValueError(f"{family}: DirInfo occurrence grid differs")
        result[family] = {
            "kind": int(kind),
            "rows_0_9": f"{family}_001 repeated single-event occurrences",
            "rows_10_19": f"{family}_002 repeated single-event occurrences",
            "row_19_selector_5": f"{family}_003 unresolved source",
            "natural_001_to_002_session_proven": False,
        }
    return result


def extract_event_authority(
    event: str,
    runtime_event: dict,
    manifest: dict,
    sound_bus_rows: list[dict[str, str]],
) -> tuple[dict, dict]:
    if (
        runtime_event.get("event_code", "").lower() != EVENT_CODES[event]
        or manifest.get("event_code_hex", "").lower() != EVENT_CODES[event]
        or manifest.get("native_dimensions") != {"width": 416, "height": 232}
        or manifest.get("native_frame_rate") != "30/1"
    ):
        raise ValueError(f"{event}: event identity differs")
    gates = manifest.get("quality_gates", {})
    if (
        gates.get("errors") != [BLOCKER]
        or gates.get("event_global_z2d_timing_ready") is not False
        or gates.get("composition_resolved") is not True
        or gates.get("ready") is not False
    ):
        raise ValueError(f"{event}: source fail-closed state differs")

    audio_rows = [
        row for row in manifest.get("audio", []) if row.get("source") == "z2d_req_sound"
    ]
    observed_requests = tuple(str(row.get("request_id", "")) for row in audio_rows)
    if observed_requests != EXPECTED_REQUESTS[event]:
        raise ValueError(f"{event}: expected request set differs")
    all_audio = {str(row.get("request_id", "")): row for row in manifest.get("audio", [])}
    audit_by_request = {
        row["request_id"]: row for row in sound_bus_rows if row.get("event") == event
    }
    if set(all_audio) != set(audit_by_request):
        raise ValueError(f"{event}: SOUND_DIVIDE_TBL request set differs")
    for request_id, row in all_audio.items():
        audit = audit_by_request[request_id]
        expected_bus = "VOICE" if row.get("source") == "z2d_req_sound" else "SE"
        if (
            audit.get("volume_bus") != expected_bus
            or audit.get("strict_no_bgm_disposition") != "NOT_BGM_BUS"
            or audit.get("code_name") != row.get("code_name")
            or audit.get("ogg_name") != row.get("ogg_name")
        ):
            raise ValueError(f"{event}/{request_id}: sound-bus identity differs")

    scene = one(runtime_event.get("scenes", []), lambda row: row.get("name") == event, f"{event} scene")
    cut = one(scene.get("cuts", []), lambda row: row.get("cut_name") == event, f"{event} cut")
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
            if not name.endswith(".z2d"):
                continue
            key = name[:-4]
            if key in node_context:
                raise ValueError(f"{event}/{key}: duplicate runtime Z2D node")
            node_context[key] = (node, layer, str(top.get("name", "")))

    def exact_key(z2d_name: str) -> tuple[dict, dict, str]:
        if z2d_name not in node_context:
            raise ValueError(f"{event}/{z2d_name}: runtime Z2D node missing")
        node, layer, layer_name = node_context[z2d_name]
        if node.get("time_remap_pointer") is not None:
            raise ValueError(f"{event}/{z2d_name}: time remap is active")
        motion = one(node.get("motions", []), lambda row: row.get("is_z2d_motion") is True, f"{event}/{z2d_name} Z2D motion")
        key = one(motion.get("keys", []), lambda row: row.get("index") == 0, f"{event}/{z2d_name} key zero")
        return key, layer, layer_name

    cues: dict[tuple[str, str], dict] = {}
    evidence: list[dict] = []
    for row in audio_rows:
        request_id = str(row["request_id"])
        z2d_name = str(row["z2d_name"])
        key, layer, layer_name = exact_key(z2d_name)
        start_frame = int(key["floats"][0])
        if (
            row.get("event_global_start_resolved") is not False
            or int(row.get("start_ms", -1)) != round_frame_ms(start_frame)
            or int(float(row.get("absolute_start_frame", -1))) != start_frame
        ):
            raise ValueError(f"{event}/{request_id}: child-local start differs")
        cues[(request_id, z2d_name)] = {
            "request_id": request_id,
            "z2d_name": z2d_name,
            "event_global_start_frame": start_frame,
            "event_global_start_ms": round_frame_ms(start_frame),
        }
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
            }
        )

    graphical = [
        row for row in manifest.get("subtitles", []) if row.get("subtitle_source") == "graphical_display_text"
    ]
    if tuple(str(row.get("z2d_name", "")) for row in graphical) != EXPECTED_GRAPHICAL_Z2D[event]:
        raise ValueError(f"{event}: graphical subtitle Z2D set differs")
    graphical_end_changes = []
    for row in graphical:
        if row.get("event_global_start_resolved") is not False:
            raise ValueError(f"{event}/{row.get('z2d_name')}: graphical row is not child-local")
        request_id = str(row.get("voice_request_id", ""))
        z2d_name = str(row.get("z2d_name", ""))
        key, _, _ = exact_key(z2d_name)
        start_frame = int(key["floats"][0])
        end_frame = int(key["floats"][1]) + 1
        if int(row.get("start_ms", -1)) != round_frame_ms(start_frame):
            raise ValueError(f"{event}/{z2d_name}: graphical start differs")
        cue_key = (request_id, z2d_name)
        if request_id and cue_key not in cues:
            raise ValueError(f"{event}/{z2d_name}: graphical voice cue lacks audio")
        if not request_id:
            cues[cue_key] = {
                "request_id": "",
                "z2d_name": z2d_name,
                "subtitle_only": True,
                "event_global_start_frame": start_frame,
                "event_global_start_ms": round_frame_ms(start_frame),
            }
        cue = cues[cue_key]
        cue["event_global_end_frame_exclusive"] = end_frame
        cue["event_global_end_ms"] = round_frame_ms(end_frame)
        if int(row.get("end_ms", -1)) != cue["event_global_end_ms"]:
            graphical_end_changes.append(
                {
                    "z2d_name": z2d_name,
                    "request_id": request_id,
                    "old_end_ms": int(row["end_ms"]),
                    "new_end_ms": cue["event_global_end_ms"],
                }
            )

    cue_rows = sorted(
        cues.values(),
        key=lambda row: (
            int(row["event_global_start_frame"]),
            str(row["request_id"]),
            str(row["z2d_name"]),
        ),
    )
    return (
        {
            "status": "event_global_parent_scene_motion_exact",
            "event_code_hex": EVENT_CODES[event],
            "parent_cut": {
                "scene": scene["name"],
                "cut": cut["cut_name"],
                "instance_offset_frames": 0,
                "cut_start_frame": 0,
                "cut_end_frame": cut["cut_end_frame"],
            },
            "sound_bus_contract": "SE plus VOICE only; zero BGM-bus rows",
            "caption_motion_evidence": evidence,
            "graphical_end_changes": graphical_end_changes,
        },
        {
            "schema": "magireco-z2d-event-timing-override-v1",
            "event": event,
            "event_code_hex": EVENT_CODES[event],
            "frame_rate": "30/1",
            "expected_z2d_request_ids": list(EXPECTED_REQUESTS[event]),
            "cues": cue_rows,
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
            "ida_parent_child": STATIC_ROOT / "parent_child_timing_authority_v1_20260815" / "IDA_PARENT_CHILD_PSEUDOCODE.json",
            "ida_z2d_motion_fields": STATIC_ROOT / "parent_child_timing_authority_v1_20260815" / "IDA_Z2D_MOTION_FIELDS.json",
            "ida_session_preflight": IDA_PREFLIGHT,
            "runtime_scene_motion": RUNTIME_ROOT / "AC7101_AC7107_RUNTIME_SCENE_MOTION.json",
            "runtime_capture_script": RUNTIME_ROOT / "capture_ac7101_ac7107_scene_motion.py",
            "runtime_probe_script": RUNTIME_ROOT / "inspect_event_scene_motion.js",
            "sound_bus_audit": SOUND_BUS_AUDIT,
            "dirinfo_routes": DIRINFO_ROUTES,
        }
        for event in EVENTS:
            sources[f"source_manifest_{event}"] = SOURCE_MANIFEST_ROOT / f"{event}.json"
        bindings = {name: binding(path) for name, path in sources.items()}
        if bindings["exact_libgameproc"]["sha256"] != "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF":
            raise ValueError("exact Slot libGameProc hash differs")
        validate_ida_preflight(read_json(sources["ida_session_preflight"]))
        runtime = read_json(sources["runtime_scene_motion"])
        if (
            runtime.get("schema") != "magireco-ac7101-ac7107-runtime-scene-motion-v1"
            or runtime.get("host_frida_version") != "17.16.4"
            or runtime.get("protected_processes_unchanged") is not True
            or runtime.get("crash_buffer_empty") is not True
            or tuple(runtime.get("requested_events", {})) != EVENTS
            or set(runtime.get("events", {})) != set(EVENTS)
        ):
            raise ValueError("bounded ac7101-ac7107 runtime capture differs")
        dirinfo = validate_dirinfo(read_csv(sources["dirinfo_routes"]))
        sound_bus_rows = read_csv(sources["sound_bus_audit"])
        authorities = {}
        overrides = {}
        for event in EVENTS:
            authorities[event], overrides[event] = extract_event_authority(
                event,
                runtime["events"][event],
                read_json(sources[f"source_manifest_{event}"]),
                sound_bus_rows,
            )
        authority_path = out_dir / "AC7101_AC7107_EVENT_GLOBAL_TIMING_AUTHORITY.json"
        write_json(
            authority_path,
            {
                "schema": "magireco-ac7101-ac7107-event-global-timing-authority-v1",
                "status": "PASS",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "families": [f"ac710{i}" for i in range(1, 8)],
                "event_count": len(EVENTS),
                "events": authorities,
                "dirinfo_product_boundary": dirinfo,
                "source_bindings": bindings,
                "source_media_modified": False,
                "product_scope": "fourteen independent single-event archives; repeated occurrences are aliases; unresolved _003 selector remains blocked",
                "human_playback_required": True,
                "publication_approved": False,
            },
        )
        authority_binding = binding(authority_path)
        override_bindings = []
        for event in EVENTS:
            payload = overrides[event]
            payload["authority_path"] = str(authority_path)
            payload["source_bindings"] = [
                authority_binding,
                bindings["exact_libgameproc"],
                bindings["ida_parent_child"],
                bindings["ida_z2d_motion_fields"],
                bindings["ida_session_preflight"],
                bindings["runtime_scene_motion"],
                bindings["sound_bus_audit"],
                bindings["dirinfo_routes"],
                bindings[f"source_manifest_{event}"],
            ]
            target = override_dir / f"{event}_parent_scene_motion_key_v1.json"
            if target.exists():
                raise ValueError(f"immutable override already exists: {target}")
            write_json(target, payload)
            override_bindings.append(binding(target))
        write_json(
            out_dir / "SUMMARY.json",
            {
                "schema": "magireco-ac7101-ac7107-timing-authority-summary-v1",
                "status": "PASS",
                "events": list(EVENTS),
                "authority": authority_binding,
                "overrides": override_bindings,
                "audio_start_timing_changed": False,
                "graphical_subtitle_end_change_count": sum(
                    len(row["graphical_end_changes"]) for row in authorities.values()
                ),
                "human_playback_required": True,
                "publication_approved": False,
            },
        )
        (out_dir / "ROLLBACK.ps1").write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: disable ac7101-ac7107 authority/overrides; source manifests and media remain unchanged.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8",
        )
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    print(json.dumps(read_json(out_dir / "SUMMARY.json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
