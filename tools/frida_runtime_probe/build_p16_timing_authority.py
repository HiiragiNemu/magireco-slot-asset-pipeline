from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from tools.frida_runtime_probe.build_event_production_manifests import file_sha256


RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
STATIC_ROOT = RESEARCH_ROOT / "ida_static_scheduler_analysis_v1_20260808"
STATIC_AUTHORITY_ROOT = (
    STATIC_ROOT / "parent_child_timing_authority_v1_20260815"
)
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT / "p16_ac6003_009_event_global_timing_authority_v1r1_20260817"
)
EVENT = "ac6003_009"
EVENT_CODE = "0x4867764e25647163"
REQUEST_ID = "5843"
Z2D_NAME = "cap6003_mb_mif_007"
EXPECTED_FIELDS = [29, 137, 29, 58, 29, 58, -1]
EXPECTED_FLAGS = [0, 2, 0]


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


def descendants(node: dict):
    yield node
    for child in node.get("children", []):
        yield from descendants(child)


def target_by_label(payload: dict, label: str) -> dict:
    return one(payload.get("targets", []), lambda row: row.get("label") == label, label)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "exact_libgameproc": STATIC_ROOT / "sample" / "libGameProc.so",
        "event_gdb": STATIC_AUTHORITY_ROOT / "ac6003_009.gdb",
        "event_z2d": STATIC_AUTHORITY_ROOT / "ac6003_009.z2d",
        "runtime_scene_motion": (
            RESEARCH_ROOT
            / "runtime_p16_scene_motion_v14_20260817"
            / "P16_AC6003_009_RUNTIME_SCENE_MOTION.json"
        ),
        "ida_motion_fields": STATIC_AUTHORITY_ROOT / "IDA_Z2D_MOTION_FIELDS.json",
        "ida_parent_child": STATIC_AUTHORITY_ROOT / "IDA_PARENT_CHILD_PSEUDOCODE.json",
        "ida_timing_core": (
            STATIC_ROOT
            / "scheduler_contract_v2_20260817"
            / "IDA_PARENT_CHILD_TIMING_CORE_RAW.json"
        ),
        "prior_fail_closed_manifest": (
            RESEARCH_ROOT
            / "_repro_audit_v67r2_inputs_r3_20260806"
            / "events"
            / "ac6003_009.json"
        ),
    }
    source_bindings = {name: binding(path) for name, path in paths.items()}

    runtime = json.loads(paths["runtime_scene_motion"].read_text(encoding="utf-8"))
    if not runtime["protected_processes_unchanged"] or not runtime["crash_buffer_empty"]:
        raise ValueError("bounded runtime capture did not preserve all foreground games")
    value = runtime["value"]
    if value["event_code"].lower() != EVENT_CODE.lower() or value["group_name"] != "ac6003":
        raise ValueError("runtime event identity mismatch")
    scene = one(value["scenes"], lambda row: row["name"] == EVENT, "P16 scene")
    cut = one(scene["cuts"], lambda row: row["cut_name"] == EVENT, "P16 cut")
    if cut["instance_offset_frames"] != 0 or cut["cut_start_frame"] != 0:
        raise ValueError("P16 parent cut is not the exact zero-offset cut")
    subtitle_layer = one(
        cut["nodes"], lambda row: row["name"] == "字幕", "subtitle layer"
    )
    player_layer = one(
        value["layers"],
        lambda row: (
            row["hash_low"], row["hash_high"]
        ) == (subtitle_layer["hash_low"], subtitle_layer["hash_high"]),
        "matching player subtitle layer",
    )
    if player_layer["speed"] != 1:
        raise ValueError("P16 subtitle layer speed is not exactly 1")
    child = one(
        list(descendants(subtitle_layer)),
        lambda row: row.get("name") == f"{Z2D_NAME}.z2d",
        "runtime child Z2D node",
    )
    if child["time_remap_pointer"] is not None:
        raise ValueError("P16 child Z2D unexpectedly has a time-remap node")
    motion = one(
        child["motions"], lambda row: row.get("is_z2d_motion") is True, "Z2D motion"
    )
    key = one(motion["keys"], lambda row: row["index"] == 0, "first motion key")
    if key["floats"] != EXPECTED_FIELDS or key["flags"] != EXPECTED_FLAGS:
        raise ValueError("runtime motion key fields differ from the static extraction")

    motion_report = json.loads(paths["ida_motion_fields"].read_text(encoding="utf-8"))
    get_key = target_by_label(motion_report, "NodeMotionBase_GetKey")["pseudocode"]
    set_key_time = target_by_label(
        motion_report, "NodeMotionZ2D_SetKeyTime"
    )["pseudocode"]
    if "**(float **)" not in get_key or "v12 <= a2" not in get_key:
        raise ValueError("IDA GetKey evidence no longer binds the first float")
    if "a3 - *v8" not in set_key_time:
        raise ValueError("IDA SetKeyTime evidence no longer consumes key start time")
    parent_report = json.loads(paths["ida_parent_child"].read_text(encoding="utf-8"))
    set_scene = target_by_label(
        parent_report, "CGFDirectionPlayer_SetScene"
    )["pseudocode"]
    for token in (
        "CGFDirectionPlaylist::AddBlank",
        "CGFDirectionPlaylist::AddCut",
        "*((_DWORD *)v23 + 2)",
    ):
        if token not in set_scene:
            raise ValueError(f"IDA SetScene evidence lacks {token}")

    prior = json.loads(paths["prior_fail_closed_manifest"].read_text(encoding="utf-8"))
    if prior["event"] != EVENT or prior["event_code_hex"].lower() != EVENT_CODE.lower():
        raise ValueError("prior manifest identity mismatch")
    old_audio = one(
        prior["audio"],
        lambda row: str(row.get("request_id")) == REQUEST_ID
        and row.get("z2d_name") == Z2D_NAME,
        "old req5843 audio",
    )
    old_subtitle = one(
        prior["subtitles"],
        lambda row: str(row.get("voice_request_id")) == REQUEST_ID
        and row.get("z2d_name") == Z2D_NAME,
        "old req5843 subtitle",
    )
    if old_audio.get("event_global_start_resolved") is not False:
        raise ValueError("old audio is not the expected fail-closed baseline")
    if old_subtitle.get("event_global_start_resolved") is not False:
        raise ValueError("old subtitle is not the expected fail-closed baseline")

    global_frame = cut["instance_offset_frames"] + key["floats"][0] - cut["cut_start_frame"]
    exact_ms = Decimal(global_frame) * Decimal(1000) / Decimal(30)
    global_ms = int(exact_ms.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    global_end_frame_exclusive = int(key["floats"][1]) + 1
    exact_end_ms = Decimal(global_end_frame_exclusive) * Decimal(1000) / Decimal(30)
    global_end_ms = int(
        exact_end_ms.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if (
        global_frame != 29
        or global_ms != 967
        or global_end_frame_exclusive != 138
        or global_end_ms != 4600
    ):
        raise ValueError("P16 timing derivation changed unexpectedly")

    authority = {
        "schema": "magireco-z2d-event-global-timing-authority-v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "event": EVENT,
        "event_code_hex": EVENT_CODE,
        "status": "EVENT_GLOBAL_TIMING_RESOLVED_FOR_EXACT_CUE",
        "scope": {
            "request_id": REQUEST_ID,
            "z2d_name": Z2D_NAME,
            "does_not_authorize_other_child_local_cues": True,
        },
        "source_bindings": source_bindings,
        "runtime_evidence": {
            "target_pid": runtime["target_pid"],
            "protected_processes_before": runtime["protected_processes_before"],
            "protected_processes_after": runtime["protected_processes_after"],
            "protected_processes_unchanged": True,
            "crash_buffer_empty": True,
            "scene_name": scene["name"],
            "cut_name": cut["cut_name"],
            "parent_instance_offset_frames": cut["instance_offset_frames"],
            "cut_start_frame": cut["cut_start_frame"],
            "layer_name": subtitle_layer["name"],
            "layer_speed": player_layer["speed"],
            "child_node_name": child["name"],
            "child_time_remap_pointer": child["time_remap_pointer"],
            "motion_fields": key["floats"],
            "motion_flags": key["flags"],
        },
        "derivation": {
            "formula": "parent_instance_offset_frames + child_motion_key_frame - cut_start_frame",
            "parent_instance_offset_frames": cut["instance_offset_frames"],
            "child_motion_key_frame": key["floats"][0],
            "cut_start_frame": cut["cut_start_frame"],
            "event_global_start_frame": global_frame,
            "frame_rate": "30/1",
            "event_global_start_ms_exact": str(exact_ms),
            "event_global_start_ms": global_ms,
            "millisecond_rounding": "nearest_integer_half_up",
            "event_global_end_frame_exclusive": global_end_frame_exclusive,
            "event_global_end_ms_exact": str(exact_end_ms),
            "event_global_end_ms": global_end_ms,
        },
        "authorized_manifest_delta": {
            "audio_start_ms": global_ms,
            "subtitle_start_ms": global_ms,
            "subtitle_end_ms": global_end_ms,
            "voice_start_ms": global_ms,
            "timing_scope": "event_global_exact_parent_scene_and_motion_key",
        },
        "human_gate": "replacement media remains HUMAN_PLAYBACK_REQUIRED",
    }
    authority_path = out_dir / "P16_AC6003_009_EVENT_GLOBAL_TIMING_AUTHORITY.json"
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "README.md").write_text(
        "# P16 ac6003_009 event-global timing authority\n\n"
        "Only request `5843` / child `cap6003_mb_mif_007` is resolved. The exact "
        "runtime scene has parent cut offset 0 and start 0; the matching subtitle "
        "layer has speed 1; the exact child has no time remap; its loaded Z2D motion "
        "key starts at frame 29. Therefore the event-global start is 29 frames at "
        "30 fps, rounded half-up to 967 ms; the key is active through frame 137, "
        "so the subtitle end boundary is frame 138 / 4600 ms. Other child-local cues remain fail-closed. "
        "Replacement media remains HUMAN_PLAYBACK_REQUIRED and old P16 stays quarantined.\n",
        encoding="utf-8",
    )
    (out_dir / "VERIFICATION_RECORD.txt").write_text(
        "command=python tools/frida_runtime_probe/build_p16_timing_authority.py\n"
        "exit_status=0\n"
        "event=ac6003_009\nrequest_id=5843\nz2d_name=cap6003_mb_mif_007\n"
        "parent_instance_offset_frames=0\ncut_start_frame=0\nlayer_speed=1\n"
        "time_remap_pointer=null\nchild_motion_key_frame=29\n"
        "event_global_start_frame=29\nevent_global_start_ms=967\n"
        "event_global_end_frame_exclusive=138\nevent_global_end_ms=4600\n"
        "old_media_status=QUARANTINED\n"
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
    json.loads(authority_path.read_text(encoding="utf-8"))
    for path in [*generated, out_dir / "SHA256SUMS.txt"]:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"generated role is missing or empty: {path}")
    print(
        json.dumps(
            {
                "status": "OK",
                "output_root": str(out_dir),
                "event_global_start_frame": global_frame,
                "event_global_start_ms": global_ms,
                "event_global_end_frame_exclusive": global_end_frame_exclusive,
                "event_global_end_ms": global_end_ms,
                "source_binding_count": len(source_bindings),
                "generated_role_count": len(generated) + 1,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
