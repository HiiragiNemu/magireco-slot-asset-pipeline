#!/usr/bin/env python3
"""Audit ac0908 uniqueness and duration from native dispatch/composition evidence.

EventInfo identity, Direction scene identity, and DGM/CRI media identity are
kept separate.  This prevents a distinct event container from being counted as
a distinct visible movie when it reuses a common shutter scene.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


EVENT_RE = re.compile(r"ac0908_\d{3}")
EXPECTED_EVENTS = [f"ac0908_{index:03d}" for index in range(1, 18)]
IDA_FUNCTIONS = [
    ("0x42c428c", "zg::CGFDirectionPlayer::SetScene"),
    ("0x42c8424", "zg::CGFDirectionPlaylist::AddCut"),
    ("0x42c84d0", "zg::CGFDirectionPlaylist::AddBlank"),
    ("0x42c907c", "zg::CGFDirectionPlaylist::AdvanceTime"),
    ("0x42c91fc", "zg::CGFDirectionPlaylist::SetTime"),
    ("0x43c21cc", "C_DirectionControllerBase::Macro_EVENT_PLAY"),
    ("0x42b0060", "zg::CGFDirectionNodeLayer::AdvanceTime"),
    ("0x42b0140", "zg::CGFDirectionNodeLayer::SetTime"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    values = list(rows)
    fields: list[str] = []
    for row in values:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_runtime_result(path: Path) -> dict[str, Any]:
    result = None
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("event") == "result":
            result = row.get("result")
    if not isinstance(result, dict):
        raise ValueError(f"runtime result missing: {path}")
    return result


def durable_media_path(source: str, durable_root: Path) -> Path:
    normalized = source.replace("/", "\\")
    marker = "\\magireco_bili_fulltest_20260603\\"
    folded = normalized.casefold()
    if marker.casefold() in folded:
        tail = normalized[folded.index(marker.casefold()) + len(marker) :]
        return durable_root / Path(tail)
    return Path(source)


def probe_media(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        return {"status": "ERROR", "exit_code": result.returncode}
    data = json.loads(result.stdout)
    video = next((row for row in data.get("streams", []) if row.get("codec_type") == "video"), {})
    return {
        "status": "OPENED",
        "duration_sec": data.get("format", {}).get("duration", ""),
        "codec": video.get("codec_name", ""),
        "width": video.get("width", ""),
        "height": video.get("height", ""),
        "frame_rate": video.get("r_frame_rate", ""),
        "frame_count": video.get("nb_frames", ""),
    }


def group_routes(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("base_name") == "ac0908":
            grouped[(int(row["kind"]), int(row["row_index"]))].append(row)
    result = []
    for (kind, row_index), items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda item: int(item["selector_raw"]))
        result.append(
            {
                "kind": kind,
                "row_index": row_index,
                "ordered_events": "|".join(item["scene_name"] for item in ordered),
                "selector_values": "|".join(item["selector_raw"] for item in ordered),
            }
        )
    return result


def build_report(
    event_info_rows: list[dict[str, str]],
    dirinfo_rows: list[dict[str, str]],
    runtime_results: Mapping[str, Mapping[str, Any]],
    timeline_rows: list[dict[str, str]],
    dgm_rows: list[dict[str, str]],
    showcase: Mapping[str, Any],
    media_probes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    native = {row["scene_name"]: row for row in event_info_rows if row.get("base_name") == "ac0908"}
    event_timeline = {
        row["primary_animation"]: row for row in timeline_rows if row.get("root") == "ac0908"
    }
    by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in dgm_rows:
        if EVENT_RE.fullmatch(row.get("event_name", "")):
            by_event[row["event_name"]].append(row)
    if sorted(native) != EXPECTED_EVENTS or sorted(runtime_results) != EXPECTED_EVENTS:
        raise ValueError("ac0908 native/runtime universe differs from 001..017")

    containers = []
    scene_uses: dict[str, list[str]] = defaultdict(list)
    container_signatures = []
    for event in EXPECTED_EVENTS:
        native_row = native[event]
        runtime = runtime_results[event]
        if str(runtime.get("code_hex", "")).casefold() != str(native_row["code_hex"]).casefold():
            raise ValueError(f"native/runtime event code mismatch: {event}")
        scenes = [str(scene) for animation in runtime.get("animations", []) for scene in animation.get("scenes", [])]
        for scene in scenes:
            scene_uses[scene].append(event)
        event_dgms = by_event.get(event, [])
        exact = [row for row in event_dgms if row.get("cri_match") == "yes"]
        missing = [row for row in event_dgms if row.get("cri_match") != "yes"]
        span = max(
            (int(float(row["event_end_ms"])) for row in event_dgms if row.get("event_end_ms")),
            default=None,
        )
        static_audio = event_timeline.get(event, {}).get("audio_timeline_duration_ms", "")
        container_signatures.append((native_row["code_hex"], tuple(scenes)))
        containers.append(
            {
                "event": event,
                "event_info_index": native_row["event_info_index"],
                "event_code": native_row["code_hex"],
                "referenced_scenes": "|".join(scenes),
                "static_audio_component_span_ms": static_audio,
                "exact_dgm_media_count": len(exact),
                "missing_dgm_layer_count": len(missing),
                "known_parent_z2d_span_ms": "" if span is None else span,
                "timing_status": (
                    "PARENT_Z2D_INTERVALS_AVAILABLE"
                    if event_dgms and not missing
                    else "PARENT_Z2D_INTERVALS_PARTIAL_MISSING_LAYERS"
                    if event_dgms
                    else "NEEDS_DIRECTION_SCENE_CUT_BLANK_LAYER_DECODE"
                ),
            }
        )

    scenes = [
        {
            "scene": name,
            "kind": "shared_component" if name.startswith("SHUTTER_") else "family_primary_scene",
            "referenced_by_events": "|".join(events),
            "reference_count": len(events),
            "deduplicated_scene_count": 1,
        }
        for name, events in sorted(scene_uses.items())
    ]
    shared_scenes = [row for row in scenes if row["reference_count"] > 1]

    bindings = []
    for event in EXPECTED_EVENTS:
        for row in sorted(by_event.get(event, []), key=lambda item: (int(item["z2d_order"]), int(item["dgm_order"]))):
            identity = f"{row.get('package','')}:{row.get('package_index','')}:{row.get('official_name','')}"
            probe = dict(media_probes.get(identity, {}))
            bindings.append(
                {
                    "event": event,
                    "z2d_name": row.get("z2d_name", ""),
                    "dgm_name": row.get("dgm_name", ""),
                    "dgm_role": row.get("dgm_role", ""),
                    "source_identity": identity,
                    "event_start_ms": row.get("event_start_ms", ""),
                    "event_end_ms": row.get("event_end_ms", ""),
                    "expected_frames": row.get("media_expected_frames", ""),
                    "interval_confidence": row.get("interval_confidence", ""),
                    "source_exists": probe.get("source_exists", False),
                    "source_path": probe.get("source_path", ""),
                    "probe_status": probe.get("status", ""),
                    "probe_duration_sec": probe.get("duration_sec", ""),
                    "probe_frame_count": probe.get("frame_count", ""),
                }
            )

    occurrences = list(showcase.get("timeline", []))
    occurrence_counts = Counter(str(row.get("event", "")) for row in occurrences)
    signatures = Counter(
        (
            str(row.get("event", "")),
            int(row.get("end_frame", 0)) - int(row.get("start_frame", 0)),
            str(row.get("kind", "")),
            row.get("include_exterior"),
        )
        for row in occurrences
    )
    duplicate_occurrences = [
        {
            "event": event,
            "frame_count": frames,
            "kind": kind,
            "include_exterior": include_exterior,
            "occurrence_count": count,
            "surplus_occurrence_count": count - 1,
        }
        for (event, frames, kind, include_exterior), count in sorted(signatures.items())
        if count > 1
    ]
    included = sorted(event for event in occurrence_counts if EVENT_RE.fullmatch(event))
    routes = group_routes(dirinfo_rows)
    source_identities = [row["source_identity"] for row in bindings if row["source_exists"]]
    repeated_sources = [name for name, count in Counter(source_identities).items() if count > 1]
    return {
        "schema": "magireco-ac0908-reverse-unique-segment-audit-v1",
        "result": "PASS_FAIL_CLOSED",
        "production_paused": True,
        "authority": {
            "ida_functions": [{"address": address, "name": name} for address, name in IDA_FUNCTIONS],
            "code_model": "DirInfo selectors -> EventInfo -> SetScene -> AddBlank/AddCut -> AdvanceTime/SetTime -> layers/DGM/Z2D",
            "machine_vision_used_as_authority": False,
        },
        "proven_counts": {
            "dirinfo_route_count": len(routes),
            "event_info_container_count": len(containers),
            "unique_event_code_count": len({row["event_code"] for row in containers}),
            "unique_runtime_container_signature_count": len(set(container_signatures)),
            "unique_referenced_scene_node_count": len(scenes),
            "shared_scene_node_count": len(shared_scenes),
            "dgm_binding_row_count": len(bindings),
            "existing_dgm_media_count": sum(bool(row["source_exists"]) for row in bindings),
            "unique_existing_dgm_source_identity_count": len(set(source_identities)),
            "repeated_dgm_source_identity_count": len(repeated_sources),
        },
        "not_yet_proven": {
            "final_unique_human_visible_segment_count": "UNRESOLVED",
            "reason": "010-015/017 need Direction cut/blank/layer timing; 016 has two missing overlay media layers",
        },
        "current_showcase": {
            "occurrence_count": len(occurrences),
            "unique_event_count": len(included),
            "included_events": included,
            "missing_event_containers": sorted(set(EXPECTED_EVENTS) - set(included)),
            "event_occurrence_counts": dict(sorted(occurrence_counts.items())),
            "guaranteed_duplicate_occurrence_groups": duplicate_occurrences,
            "authority_decision": "PLAYBACK_APPROVAL_RETAINED_COMPLETE_CLAIM_WITHDRAWN",
        },
        "event_containers": containers,
        "dirinfo_routes": routes,
        "unique_scene_nodes": scenes,
        "shared_scene_nodes": shared_scenes,
        "dgm_media_bindings": bindings,
        "repeated_dgm_source_identities": repeated_sources,
        "final_product_gate": "BLOCKED_PENDING_CODE_LEVEL_VISIBLE_SEGMENT_AND_DURATION_CLOSURE",
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    runtime = {
        event: read_runtime_result(args.runtime_event_root / f"{event}.jsonl")
        for event in EXPECTED_EVENTS
    }
    dgm_rows = [row for row in read_csv(args.dgm_timeline) if EVENT_RE.fullmatch(row.get("event_name", ""))]
    probes: dict[str, dict[str, Any]] = {}
    for row in dgm_rows:
        identity = f"{row.get('package','')}:{row.get('package_index','')}:{row.get('official_name','')}"
        if identity in probes:
            continue
        source = durable_media_path(row.get("target_mp4") or row.get("source_mp4", ""), args.durable_fulltest_root)
        probes[identity] = {"source_exists": source.is_file(), "source_path": str(source)}
        if source.is_file():
            probes[identity].update(probe_media(source, args.ffprobe))
    report = build_report(
        read_csv(args.event_info_csv),
        read_csv(args.dirinfo_routes_csv),
        runtime,
        read_csv(args.event_timeline_csv),
        dgm_rows,
        json.loads(args.showcase_manifest.read_text(encoding="utf-8")),
        probes,
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    write_json(args.output_root / "AC0908_REVERSE_UNIQUENESS.json", report)
    write_json(args.output_root / "AC0908_REVERSE_VERIFICATION.json", {
        "result": report["result"],
        "proven_counts": report["proven_counts"],
        "current_showcase": report["current_showcase"],
        "not_yet_proven": report["not_yet_proven"],
        "final_product_gate": report["final_product_gate"],
    })
    write_csv(args.output_root / "AC0908_EVENT_CONTAINERS.csv", report["event_containers"])
    write_csv(args.output_root / "AC0908_DIRINFO_ROUTES.csv", report["dirinfo_routes"])
    write_csv(args.output_root / "AC0908_UNIQUE_SCENE_NODES.csv", report["unique_scene_nodes"])
    write_csv(args.output_root / "AC0908_DGM_MEDIA_BINDINGS.csv", report["dgm_media_bindings"])
    (args.output_root / "AC0908_README.md").write_text(
        "# ac0908 代码级唯一性与时长复核\n\n"
        "- 17 个 EventInfo 容器由原生表与 runtime object 双重绑定。\n"
        "- 容器数量不等于最终独一无二可见视频数量；共享 shutter 必须去重。\n"
        "- 旧 91.5 秒合集仅包含 001-009，009 以同样 139 帧出现三次。\n"
        "- 010-015/017 的 Direction 时间线未闭合；016 仍有两层媒体缺失。\n"
        "- 保留人工播放记录，但撤回穷尽完整声明；没有重编码媒体。\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-info-csv", type=Path, required=True)
    parser.add_argument("--dirinfo-routes-csv", type=Path, required=True)
    parser.add_argument("--runtime-event-root", type=Path, required=True)
    parser.add_argument("--event-timeline-csv", type=Path, required=True)
    parser.add_argument("--dgm-timeline", type=Path, required=True)
    parser.add_argument("--showcase-manifest", type=Path, required=True)
    parser.add_argument("--durable-fulltest-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    report = run(parse_args())
    print(json.dumps({
        "result": report["result"],
        "proven_counts": report["proven_counts"],
        "current_showcase": report["current_showcase"],
        "final_product_gate": report["final_product_gate"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
