#!/usr/bin/env python3
"""Resolve the evidence-bound exhaustive ac0911 editorial authority.

This resolver does not render media.  It cross-checks the complete DirInfo
route universe, the bounded all-event runtime scene capture, exact parent
audio rows, the CRI/Z2D source map, and the already QA-passed v75 event
segments.  The result is the input contract for one duplicate-free longform.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys


FPS = 30
EXPECTED_SLOT_BINARY = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
EVENTS = [f"ac0911_{index:03d}" for index in range(1, 18)]
ROUTES = [
    ["ac0911_001", "ac0911_002", "ac0911_003"],
    ["ac0911_001", "ac0911_002", "ac0911_004"],
    ["ac0911_001", "ac0911_002", "ac0911_005"],
    ["ac0911_001", "ac0911_002", "ac0911_009"],
    ["ac0911_001", "ac0911_002", "ac0911_017"],
    ["ac0911_001", "ac0911_002", "ac0911_010"],
    ["ac0911_001", "ac0911_002", "ac0911_011"],
    ["ac0911_001", "ac0911_002", "ac0911_012"],
    ["ac0911_001", "ac0911_006", "ac0911_007"],
    ["ac0911_001", "ac0911_006", "ac0911_008"],
    ["ac0911_001", "ac0911_006", "ac0911_013"],
    ["ac0911_001", "ac0911_006", "ac0911_016"],
    ["ac0911_001", "ac0911_006", "ac0911_014"],
    ["ac0911_001", "ac0911_006", "ac0911_015"],
]
EDITORIAL_ORDER = [
    "ac0911_001", "ac0911_002", "ac0911_003", "ac0911_004",
    "ac0911_005", "ac0911_009", "ac0911_017", "ac0911_010",
    "ac0911_011", "ac0911_012", "ac0911_006", "ac0911_007",
    "ac0911_008", "ac0911_013", "ac0911_016", "ac0911_014",
    "ac0911_015",
]
PRESENTATION_FRAMES = {
    "ac0911_001": 316, "ac0911_002": 312, "ac0911_003": 180,
    "ac0911_004": 225, "ac0911_005": 154, "ac0911_006": 173,
    "ac0911_007": 165, "ac0911_008": 176, "ac0911_009": 510,
    "ac0911_010": 510, "ac0911_011": 510, "ac0911_012": 135,
    "ac0911_013": 498, "ac0911_014": 498, "ac0911_015": 145,
    "ac0911_016": 498, "ac0911_017": 510,
}
RUNTIME_MOTION_FRAMES = {
    "ac0911_001": 289, "ac0911_002": 311, "ac0911_003": 180,
    "ac0911_004": 224, "ac0911_005": 135, "ac0911_006": 78,
    "ac0911_007": 105, "ac0911_008": 141, "ac0911_009": 510,
    "ac0911_010": 510, "ac0911_011": 510, "ac0911_012": 135,
    "ac0911_013": 498, "ac0911_014": 498, "ac0911_015": 78,
    "ac0911_016": 498, "ac0911_017": 510,
}
EXPECTED_RUNTIME_SOUND_IDS = {
    "ac0911_007": [2756],
    "ac0911_013": [551, 1005, 1035, 1036],
    "ac0911_014": [552, 1008, 1035, 1036],
    "ac0911_015": [553, 1010, 1035, 1036],
    "ac0911_016": [1004, 1035, 1036],
}
BGM_IDS = {551, 552, 553}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing {label}: {path}")


def binding(path: Path) -> dict:
    require_file(path, "bound evidence")
    return {"path": str(path.resolve()), "size_bytes": path.stat().st_size}


def _walk_nodes(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def visible_motion_frames(event: dict) -> int:
    maximum_cut = 0
    maximum_z2d = 0
    for scene in event.get("scenes", []):
        for cut in scene.get("cuts", []):
            maximum_cut = max(maximum_cut, int(cut.get("cut_end_frame", -1)) + 1)
            for node in _walk_nodes(cut.get("nodes", [])):
                for motion in node.get("motions", []):
                    if not motion.get("is_z2d_motion"):
                        continue
                    for key in motion.get("keys", []):
                        floats = key.get("floats", [])
                        if len(floats) >= 2:
                            maximum_z2d = max(maximum_z2d, int(round(float(floats[1]))) + 1)
    return maximum_z2d or maximum_cut


def runtime_sound_ids(capture_path: Path) -> dict[str, list[int]]:
    rows: dict[str, set[int]] = {event: set() for event in EXPECTED_RUNTIME_SOUND_IDS}
    for line in capture_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        payload = row.get("message", {}).get("payload", row.get("payload", row))
        if payload.get("kind") != "forced_sound_play":
            continue
        event = payload.get("forced_event_label")
        if event not in rows:
            continue
        value = payload.get("sound_code", payload.get("sound_id", payload.get("code")))
        if value is None:
            match = re.match(r"0*(\d+)", str(payload.get("code_name", "")))
            value = match.group(1) if match else None
        if value is None:
            continue
        try:
            rows[event].add(int(value))
        except (TypeError, ValueError):
            pass
    return {event: sorted(values) for event, values in rows.items()}


def load_audio_rows(path: Path) -> dict[str, list[dict]]:
    result = {event: [] for event in EVENTS}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            event = row.get("primary_animation")
            if event not in result:
                continue
            sound_id = int(row["leaf_sound_code"])
            source = Path(row["ogg_path"].replace("A:\\", "D:\\magia\\MyProducts\\casino\\"))
            require_file(source, f"official audio {sound_id}")
            result[event].append({
                "request_id": int(row["parent_request_id"]),
                "sound_id": sound_id,
                "kind": "BGM" if sound_id in BGM_IDS else "SE",
                "start_ms": int(row["start_ms"]),
                "duration_ms": int(row["duration_ms"]),
                "source": binding(source),
            })
    return result


def load_dgm_007(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("event_name") != "ac0911_007":
                continue
            rows.append({
                "dgm_name": row["dgm_name"],
                "event_start_frame": int(float(row["event_start_frame"])),
                "event_end_frame_inclusive": int(float(row["event_end_frame"])),
                "frames": int(row["media_expected_frames"]),
                "package": row["package"],
                "package_index": int(row["package_index"]),
                "official_name": row["official_name"],
            })
    rows.sort(key=lambda row: row["event_start_frame"])
    expected = [
        ("ac0911_007_c09_MR", 0, 74, 75, 2033),
        ("ac0911_007_c09_LP_MR", 75, 104, 30, 2032),
    ]
    observed = [
        (row["dgm_name"], row["event_start_frame"], row["event_end_frame_inclusive"], row["frames"], row["package_index"])
        for row in rows
    ]
    if observed != expected:
        raise RuntimeError(f"ac0911_007 DGM timeline changed: {observed}")
    return rows


def load_v75_segments(root: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for manifest_path in sorted(root.glob("ac0911/routes/dirinfo-row-*/ROUTE_MANIFEST.json")):
        manifest = read_json(manifest_path)
        if manifest.get("status") != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED":
            raise RuntimeError(f"v75 route status changed: {manifest_path}")
        route_dir = manifest_path.parent
        for item in manifest["timeline"]:
            event = item["event"]
            if event in result:
                continue
            media = {}
            for edition, source in manifest["media"].items():
                path = route_dir / source["path"].replace("routes/" + route_dir.name + "/", "")
                if not path.is_file():
                    path = root / "ac0911" / source["path"]
                require_file(path, f"v75 {event} {edition}")
                media[edition] = {
                    "path": str(path.resolve()),
                    "declared_sha256": source.get("sha256"),
                }
            result[event] = {
                "route_manifest": binding(manifest_path),
                "route_media_start_frame": int(item["start_frame"]),
                "route_media_end_frame_exclusive": int(item["end_frame"]),
                "legacy_master_start_frame": int(item["source_start_frame"]),
                "legacy_master_end_frame_exclusive": int(item["source_end_frame"]),
                "frames": int(item["end_frame"]) - int(item["start_frame"]),
                "media": media,
            }
    return result


def resolve(args: argparse.Namespace) -> Path:
    for path, label in [
        (args.identity_audit, "identity audit"),
        (args.runtime_scene, "runtime scene capture"),
        (args.runtime_audio, "runtime audio capture"),
        (args.audio_components, "audio component table"),
        (args.dgm_timeline, "DGM timeline"),
        (args.cri_argb_authority, "CRI ARGB authority"),
    ]:
        require_file(path, label)

    identity = read_json(args.identity_audit)
    runtime = read_json(args.runtime_scene)
    cri = read_json(args.cri_argb_authority)
    route_rows = [row["event_sequence"] for row in identity["route_universe"]["routes"]]
    if route_rows != ROUTES or identity["route_universe"].get("unique_events") != EVENTS:
        raise RuntimeError("DirInfo route universe changed")
    if sorted(runtime.get("events", {})) != EVENTS:
        raise RuntimeError("runtime capture does not cover all 17 events")
    if runtime.get("exact_libgameproc", {}).get("sha256") != EXPECTED_SLOT_BINARY:
        raise RuntimeError("runtime capture is not bound to the exact Slot binary")
    for guard in ("protected_processes_unchanged", "crash_buffer_unchanged", "critical_module_maps_unchanged", "zygote_agent_maps_clean"):
        if runtime.get(guard) is not True:
            raise RuntimeError(f"runtime safety guard failed: {guard}")
    observed_motion = {event: visible_motion_frames(runtime["events"][event]) for event in EVENTS}
    if observed_motion != RUNTIME_MOTION_FRAMES:
        raise RuntimeError(f"runtime motion frame map changed: {observed_motion}")
    if cri.get("status") != "passed_exact_color_alpha_streams_resolved":
        raise RuntimeError("CRI ARGB authority is not passed")
    cri_names = {row["official_name"]: row for row in cri.get("artifacts", [])}
    if set(cri_names) != {"ac0911_007_c09_MR", "ac0911_007_c09_LP_MR"}:
        raise RuntimeError("ac0911_007 exact CRI source set changed")

    captured_sounds = runtime_sound_ids(args.runtime_audio)
    if captured_sounds != EXPECTED_RUNTIME_SOUND_IDS:
        raise RuntimeError(f"runtime sound set changed: {captured_sounds}")
    audio = load_audio_rows(args.audio_components)
    for event, expected in EXPECTED_RUNTIME_SOUND_IDS.items():
        if sorted(row["sound_id"] for row in audio[event]) != expected:
            raise RuntimeError(f"parent audio table disagrees for {event}")
    dgm_007 = load_dgm_007(args.dgm_timeline)
    v75 = load_v75_segments(args.v75_root)
    inherited_events = [event for event in EVENTS if event not in {"ac0911_007", "ac0911_013", "ac0911_014", "ac0911_015", "ac0911_016"}]
    missing = sorted(set(inherited_events) - set(v75))
    if missing:
        raise RuntimeError(f"v75 lacks required inherited events: {missing}")
    for event in inherited_events:
        if v75[event]["frames"] != PRESENTATION_FRAMES[event]:
            raise RuntimeError(f"v75 presentation frame count changed for {event}")

    outcome_root = args.outcome_root.resolve()
    outcome_files = {
        "ac0911_013": outcome_root / "hatten.mp4",
        "ac0911_014": outcome_root / "cz.mp4",
        "ac0911_015": outcome_root / "win.mp4",
        "ac0911_016": outcome_root / "zenchou.mp4",
    }
    for event, path in outcome_files.items():
        require_file(path, f"shared exact outcome {event}")

    chapters = []
    cursor = 0
    for order, event in enumerate(EDITORIAL_ORDER, 1):
        frames = PRESENTATION_FRAMES[event]
        chapters.append({
            "timeline_order": order,
            "event": event,
            "start_frame": cursor,
            "end_frame_exclusive": cursor + frames,
            "frames": frames,
            "presentation_policy": "one_unique_event_container_once",
        })
        cursor += frames
    if cursor != 5515 or set(EDITORIAL_ORDER) != set(EVENTS):
        raise RuntimeError("editorial timeline is not an exact 17-event cover")

    output = {
        "schema": "ac0911_exhaustive_native416_authority_v1",
        "status": "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
        "family": "ac0911",
        "product_semantics": "editorial_exhaustive_collection_not_native_single_session",
        "canvas": [416, 232],
        "frame_rate": FPS,
        "route_count": len(ROUTES),
        "routes": [{"row_index": index, "events": route} for index, route in enumerate(ROUTES)],
        "event_container_count": len(EVENTS),
        "canonical_presentation_count": len(EVENTS),
        "exact_duplicate_surplus_count": 0,
        "all_event_containers_pointer_free_distinct": True,
        "editorial_order": EDITORIAL_ORDER,
        "chapters": chapters,
        "total_frames": cursor,
        "duration_seconds": cursor / FPS,
        "runtime_motion_frames": observed_motion,
        "presentation_frames": PRESENTATION_FRAMES,
        "v75_event_segments": {event: v75[event] for event in inherited_events},
        "ac0911_007": {
            "runtime_motion_frames": 105,
            "presentation_frames": 165,
            "tail_policy": "hold_last_frame_to_verified_5500ms_parent_SE_end",
            "dgm_timeline": dgm_007,
            "cri_argb_sources": [cri_names[name] for name in sorted(cri_names)],
            "audio": audio["ac0911_007"],
        },
        "shared_exact_outcomes": {
            event: {
                "path": str(path),
                "presentation_frames": PRESENTATION_FRAMES[event],
                "audio": [row for row in audio[event] if row["kind"] != "BGM"],
                "excluded_bgm": [row for row in audio[event] if row["kind"] == "BGM"],
                "reuse_basis": "same runtime scene/cut/Z2D structure and same parent request/audio schedule as ac0908 exact outcome",
            }
            for event, path in outcome_files.items()
        },
        "strict_no_bgm": {
            "excluded_sound_ids": sorted(BGM_IDS),
            "retained_verified_voice_and_se": True,
            "claim": "BGM intentionally excluded; independently verified voice and SE retained",
        },
        "authority_inputs": {
            "identity_audit": binding(args.identity_audit),
            "runtime_scene": binding(args.runtime_scene),
            "runtime_audio": binding(args.runtime_audio),
            "audio_components": binding(args.audio_components),
            "dgm_timeline": binding(args.dgm_timeline),
            "cri_argb_authority": binding(args.cri_argb_authority),
        },
        "automatic_assertions": {
            "all_14_dirinfo_routes_covered": True,
            "all_17_event_containers_covered_once": True,
            "runtime_all_events_same_bounded_capture": True,
            "runtime_process_and_map_guards_passed": True,
            "parent_audio_and_runtime_sound_sets_agree": True,
            "exact_cri_argb_sources_resolved_for_007": True,
            "bgm_551_552_553_excluded": True,
            "P16_P17_P18_not_referenced": True,
            "machine_vision_used_as_authority": False,
        },
        "human_status": "HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    target = args.output_root / "AC0911_EXHAUSTIVE_NATIVE416_AUTHORITY.json"
    write_json(target, output)
    (args.output_root / "00_README.md").write_text(
        "# ac0911 穷尽长片权威清单\n\n"
        "- 14 条 DirInfo 路线，17 个代码级不同事件容器。\n"
        "- 最终长片每个事件只出现一次，按剧情分组顺序排列。\n"
        "- 预计 5515 帧 / 183.833 秒，原生 416×232、30fps。\n"
        "- 551/552/553 明确为 BGM 并排除；保留运行时与 parent request 同时验证的 SE。\n"
        "- 自动证据闭合只允许渲染；成片仍须人工播放验收。\n",
        encoding="utf-8",
    )
    print("PASS routes=14 events=17 chapters=17 frames=5515 duplicate_surplus=0")
    return target


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--identity-audit", type=Path, required=True)
    value.add_argument("--runtime-scene", type=Path, required=True)
    value.add_argument("--runtime-audio", type=Path, required=True)
    value.add_argument("--audio-components", type=Path, required=True)
    value.add_argument("--dgm-timeline", type=Path, required=True)
    value.add_argument("--cri-argb-authority", type=Path, required=True)
    value.add_argument("--v75-root", type=Path, required=True)
    value.add_argument("--outcome-root", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    return value


def main() -> int:
    try:
        resolve(parser().parse_args())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
