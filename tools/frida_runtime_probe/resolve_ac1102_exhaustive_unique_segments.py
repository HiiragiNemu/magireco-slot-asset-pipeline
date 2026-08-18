#!/usr/bin/env python3
"""Resolve the code-level ac1102 exhaustive, duplicate-free video universe.

This audit deliberately does not render media.  It combines all 31 DirInfo
rows, exact runtime scene/cut captures for all 15 events, the audience source
catalog and a bounded SHA-256 authority for the 38 relevant source files.  The
result distinguishes event/cut structure from exact source-media identity so a
future longform can include every unique segment once without pretending that
mutually exclusive routes form one native session.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REQUIRED_EVENTS = tuple(f"ac1102_{index:03d}" for index in range(1, 16))
LEGACY_EVENTS = (
    "ac1102_001",
    "ac1102_002",
    "ac1102_003",
    "ac1102_004",
    "ac1102_005",
    "ac1102_006",
    "ac1102_008",
    "ac1102_009",
    "ac1102_010",
    "ac1102_011",
    "ac1102_012",
)
EXACT_SLOT_SHA256 = (
    "5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf"
)
SOURCE_A_PREFIX = r"A:\magireco_bili_fulltest_20260603"
SOURCE_D_PREFIX = (
    r"D:\magia\MyProducts\casino\magireco_bili_fulltest_20260603"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def structure_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def motion_structure(motion: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "is_z2d_motion": motion.get("is_z2d_motion"),
        "keys": [
            {
                "index": key.get("index"),
                "floats": key.get("floats"),
                "flags": key.get("flags"),
            }
            for key in motion.get("keys", [])
        ],
    }


def node_structure(node: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": node.get("type"),
        "name": node.get("name"),
        "motions": [motion_structure(row) for row in node.get("motions", [])],
        "children": [node_structure(row) for row in node.get("children", [])],
    }


def cut_structure(cut: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "cut_name": cut["cut_name"],
        "instance_offset_frames": int(cut["instance_offset_frames"]),
        "cut_start_frame": int(cut["cut_start_frame"]),
        "cut_end_frame": int(cut["cut_end_frame"]),
        "nodes": [node_structure(row) for row in cut.get("nodes", [])],
    }


def cut_frames(cut: Mapping[str, Any]) -> int:
    offset = int(cut["instance_offset_frames"])
    start = int(cut["cut_start_frame"])
    end = int(cut["cut_end_frame"])
    if offset < 0 or end < start:
        raise ValueError(f"invalid cut interval: {cut}")
    return offset + end - start + 1


def durable_source_path(raw: str) -> Path:
    if raw.casefold().startswith(SOURCE_A_PREFIX.casefold()):
        return Path(SOURCE_D_PREFIX + raw[len(SOURCE_A_PREFIX) :])
    return Path(raw)


def validate_capture(
    payload: Mapping[str, Any], schema: str, expected_events: Iterable[str]
) -> None:
    expected = tuple(expected_events)
    if (
        payload.get("schema") != schema
        or payload.get("host_frida_version") != "17.16.4"
        or payload.get("protected_processes_unchanged") is not True
        or payload.get("crash_tail_empty") is not True
        or tuple(payload.get("requested_events", {})) != expected
        or set(payload.get("events", {})) != set(expected)
    ):
        raise ValueError(f"bounded runtime capture differs: {schema}")


def validate_ida_event_av(evidence: Mapping[str, Any]) -> None:
    assertions = evidence.get("semantic_assertions", {})
    if (
        evidence.get("schema") != "magireco-ida-event-av-parallel-start-evidence-v1"
        or evidence.get("status") != "passed"
        or str(evidence.get("binary", {}).get("sha256", "")).casefold()
        != EXACT_SLOT_SHA256
        or assertions.get("graphics_and_sound_receive_same_event_code") is not True
        or assertions.get("all_scene_names_are_set_at_time_zero") is not True
        or assertions.get("same_event_scene_scheduling")
        != "parallel_shared_event_global_origin"
        or assertions.get("scene_container_duration_rule")
        != "maximum_scene_duration_not_sum"
        or assertions.get("machine_vision_used_as_authority") is not False
    ):
        raise ValueError("exact Slot IDA event scheduling evidence differs")


def normalize_runtime_event(wrapper: Mapping[str, Any], event: str) -> Mapping[str, Any]:
    if "value" in wrapper:
        if wrapper.get("status") != "captured":
            raise ValueError(f"runtime event was not captured: {event}")
        value = wrapper["value"]
    else:
        value = wrapper
    if value.get("group_name") != "ac1102":
        raise ValueError(f"unexpected runtime group for {event}")
    return value


def route_universe(rows: list[dict[str, str]]) -> dict[str, Any]:
    selected = [row for row in rows if int(row["kind"]) == 54]
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[int(row["row_index"])].append(row)
    if set(grouped) != set(range(31)):
        raise ValueError("ac1102 DirInfo must contain rows 0 through 30")

    routes: list[dict[str, Any]] = []
    union: set[str] = set()
    for row_index in range(31):
        values = sorted(grouped[row_index], key=lambda row: int(row["selector_raw"]))
        events = [row["scene_name"] for row in values]
        unknown = sorted(set(events) - set(REQUIRED_EVENTS))
        if unknown:
            raise ValueError(f"unexpected ac1102 event(s) in row {row_index}: {unknown}")
        union.update(events)
        routes.append(
            {
                "row_index": row_index,
                "event_sequence": events,
                "selector_values": [int(row["selector_raw"]) for row in values],
                "legacy_resolved_source_counts": [
                    int(row["resolved_source_count"]) for row in values
                ],
            }
        )
    if union != set(REQUIRED_EVENTS):
        raise ValueError("DirInfo route union does not cover all 15 ac1102 events")
    return {
        "kind": 54,
        "route_count": len(routes),
        "routes": routes,
        "unique_event_count": len(union),
        "unique_events": sorted(union),
        "legacy_resolved_source_count_is_authoritative": False,
    }


def load_hash_authority(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if (
        payload.get("schema")
        != "magireco-ac1102-bounded-source-hash-authority-v1"
        or payload.get("status") != "PASS"
        or payload.get("consumer")
        != "tools/frida_runtime_probe/resolve_ac1102_exhaustive_unique_segments.py"
        or int(payload.get("entry_count", -1)) != 38
        or payload.get("source_media_modified") is not False
    ):
        raise ValueError("bounded ac1102 source hash authority differs")
    result: dict[str, dict[str, Any]] = {}
    for row in payload.get("entries", []):
        path = str(Path(row["path"]).resolve())
        digest = str(row["sha256"]).upper()
        if len(digest) != 64 or path in result:
            raise ValueError("invalid or duplicate hash-authority entry")
        result[path] = {
            "sha256": digest,
            "size_bytes": int(row["size_bytes"]),
        }
    if len(result) != 38:
        raise ValueError("bounded hash-authority path count differs")
    return result


def resolve(
    old_runtime: Mapping[str, Any],
    old_lockframes: Mapping[str, Any],
    new_runtime: Mapping[str, Any],
    new_lockframes: Mapping[str, Any],
    dirinfo_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    legacy_manifest: Mapping[str, Any],
    ida_event_av: Mapping[str, Any],
    hash_authority_payload: Mapping[str, Any],
) -> dict[str, Any]:
    validate_capture(
        old_runtime,
        "magireco-ac1102-runtime-scene-motion-v1",
        LEGACY_EVENTS,
    )
    validate_capture(
        old_lockframes,
        "magireco-ac1102-runtime-lockframe-v1",
        LEGACY_EVENTS,
    )
    missing_events = tuple(event for event in REQUIRED_EVENTS if event not in LEGACY_EVENTS)
    validate_capture(
        new_runtime,
        "magireco-ac1102-missing-runtime-scene-motion-v1",
        missing_events,
    )
    validate_capture(
        new_lockframes,
        "magireco-ac1102-missing-runtime-lockframe-v1",
        missing_events,
    )
    validate_ida_event_av(ida_event_av)
    routes = route_universe(dirinfo_rows)
    hash_authority = load_hash_authority(hash_authority_payload)

    combined_runtime = dict(old_runtime["events"])
    combined_runtime.update(new_runtime["events"])
    combined_lockframes = dict(old_lockframes["events"])
    combined_lockframes.update(new_lockframes["events"])
    if set(combined_runtime) != set(REQUIRED_EVENTS):
        raise ValueError("runtime union does not cover all ac1102 events")

    cuts: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    cut_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in REQUIRED_EVENTS:
        value = normalize_runtime_event(combined_runtime[event], event)
        scene_lengths: list[int] = []
        event_cut_count = 0
        for scene in value.get("scenes", []):
            cut_lengths: list[int] = []
            for cut in scene.get("cuts", []):
                frames = cut_frames(cut)
                key = structure_key(cut_structure(cut))
                row = {
                    "event": event,
                    "scene": scene["name"],
                    "cut": cut["cut_name"],
                    "frames": frames,
                    "seconds": frames / 30,
                    "structure_key": key,
                }
                cuts.append(row)
                cut_groups[key].append(row)
                cut_lengths.append(frames)
                event_cut_count += 1
            if cut_lengths:
                scene_lengths.append(max(cut_lengths))
        if not scene_lengths:
            raise ValueError(f"runtime event has no scene cuts: {event}")
        lock_frame = int(combined_lockframes[event]["lock_frame"])
        event_rows.append(
            {
                "event": event,
                "scene_count": len(value.get("scenes", [])),
                "cut_count": event_cut_count,
                "parallel_scene_frame_lengths": scene_lengths,
                "container_frames": max(scene_lengths),
                "container_seconds": max(scene_lengths) / 30,
                "lock_frame": lock_frame,
            }
        )

    family_source_rows = [
        row for row in source_rows if row.get("event_name") in REQUIRED_EVENTS
    ]
    if {row["event_name"] for row in family_source_rows} != set(REQUIRED_EVENTS):
        raise ValueError("source catalog does not cover all ac1102 events")

    present_rows: list[dict[str, Any]] = []
    missing_components: list[dict[str, Any]] = []
    for row in family_source_rows:
        source_exists = row.get("source_exists", "").casefold() == "yes"
        if not source_exists:
            missing_components.append(
                {
                    "event": row["event_name"],
                    "z2d_name": row["z2d_name"],
                    "dgm_name": row["dgm_name"],
                }
            )
            continue
        path = str(durable_source_path(row["source_mp4"]).resolve())
        authority = hash_authority.get(path)
        if authority is None:
            raise ValueError(f"source is outside bounded hash authority: {path}")
        width = int(row["width"])
        height = int(row["height"])
        present_rows.append(
            {
                "event": row["event_name"],
                "z2d_name": row["z2d_name"],
                "dgm_name": row["dgm_name"],
                "official_name": row["official_name"],
                "path": path,
                "sha256": authority["sha256"],
                "size_bytes": authority["size_bytes"],
                "width": width,
                "height": height,
                "native_416x232": width == 416 and height == 232,
            }
        )

    native_rows = [row for row in present_rows if row["native_416x232"]]
    component_rows = [row for row in present_rows if not row["native_416x232"]]
    if len(native_rows) != 53 or len(component_rows) != 6:
        raise ValueError("ac1102 source occurrence counts differ")

    def group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row["sha256"]].append(row)
        return grouped

    native_groups = group_rows(native_rows)
    component_groups = group_rows(component_rows)
    legacy_set = set(legacy_manifest.get("ordered_events", []))
    if tuple(legacy_manifest.get("ordered_events", [])) != LEGACY_EVENTS:
        raise ValueError("legacy ac1102 longform event order differs")
    legacy_native_rows = [row for row in native_rows if row["event"] in legacy_set]
    legacy_groups = group_rows(legacy_native_rows)
    missing_from_legacy = sorted(set(native_groups) - set(legacy_groups))

    unique_sources: list[dict[str, Any]] = []
    duplicate_groups: list[dict[str, Any]] = []
    for digest, rows in sorted(native_groups.items()):
        canonical = rows[0]
        unique_sources.append(
            {
                "sha256": digest,
                "canonical_path": canonical["path"],
                "official_name": canonical["official_name"],
                "occurrence_count": len(rows),
                "events": sorted({row["event"] for row in rows}),
            }
        )
        if len(rows) > 1:
            duplicate_groups.append(
                {
                    "sha256": digest,
                    "canonical_path": canonical["path"],
                    "official_name": canonical["official_name"],
                    "occurrence_count": len(rows),
                    "events": [row["event"] for row in rows],
                }
            )

    missing_component_identities = sorted(
        {row["dgm_name"] for row in missing_components}
    )
    blockers = [
        {
            "kind": "missing_layer_media",
            "identities": missing_component_identities,
            "occurrence_count": len(missing_components),
        },
        {
            "kind": "missing_event_audio_and_strict_no_bgm_manifest_closure",
            "events": list(missing_events),
        },
        {
            "kind": "exhaustive_editorial_order_not_yet_bound",
            "reason": "all unique segments must be ordered once without claiming a native single-session route",
        },
    ]

    return {
        "schema": "magireco-ac1102-exhaustive-unique-segment-authority-v1",
        "status": "PASS_RENDER_PAUSED",
        "family": "ac1102",
        "native_dimensions": {"width": 416, "height": 232},
        "frame_rate": "30/1",
        "product_standard": {
            "one_exhaustive_longform": True,
            "include_mutually_exclusive_outcomes": True,
            "each_exact_source_identity_once": True,
            "logical_editorial_order_required": True,
            "native_single_session_claimed": False,
            "machine_vision_primary_authority": False,
        },
        "route_universe": routes,
        "runtime_structure": {
            "event_count": len(event_rows),
            "events": event_rows,
            "cut_occurrence_count": len(cuts),
            "unique_cut_structure_count": len(cut_groups),
            "duplicate_cut_structure_surplus": len(cuts) - len(cut_groups),
            "cuts": cuts,
            "parallel_scene_duration_rule": "maximum_not_sum",
        },
        "native_source_universe": {
            "occurrence_count": len(native_rows),
            "unique_sha256_count": len(native_groups),
            "duplicate_surplus_occurrence_count": len(native_rows) - len(native_groups),
            "duplicate_group_count": len(duplicate_groups),
            "unique_sources": unique_sources,
            "duplicate_groups": duplicate_groups,
        },
        "related_component_universe": {
            "present_occurrence_count": len(component_rows),
            "present_unique_sha256_count": len(component_groups),
            "missing_occurrence_count": len(missing_components),
            "missing_unique_identity_count": len(missing_component_identities),
            "missing_identities": missing_component_identities,
            "missing_rows": missing_components,
        },
        "legacy_longform": {
            "duration_ms": int(legacy_manifest["media"]["duration_ms"]),
            "event_count": len(LEGACY_EVENTS),
            "events": list(LEGACY_EVENTS),
            "native_source_occurrence_count": len(legacy_native_rows),
            "unique_native_sha256_count": len(legacy_groups),
            "duplicate_surplus_occurrence_count": len(legacy_native_rows)
            - len(legacy_groups),
            "missing_required_unique_sha256_count": len(missing_from_legacy),
            "missing_required_unique_sha256": missing_from_legacy,
            "exhaustive_authoritative": False,
        },
        "decision": {
            "legacy_91_8s_longform_complete": False,
            "route_fragments_are_final_product": False,
            "new_render_allowed": False,
            "reason": "event/source universe is code-level closed, but required layers, audio bus closure and duplicate-free editorial order are not all closed",
            "blockers": blockers,
        },
        "source_media_modified": False,
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-runtime", type=Path, required=True)
    parser.add_argument("--old-lockframes", type=Path, required=True)
    parser.add_argument("--new-runtime", type=Path, required=True)
    parser.add_argument("--new-lockframes", type=Path, required=True)
    parser.add_argument("--dirinfo", type=Path, required=True)
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--ida-event-av", type=Path, required=True)
    parser.add_argument("--hash-authority", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    result = resolve(
        read_json(args.old_runtime),
        read_json(args.old_lockframes),
        read_json(args.new_runtime),
        read_json(args.new_lockframes),
        read_csv(args.dirinfo),
        read_csv(args.source_catalog),
        read_json(args.legacy_manifest),
        read_json(args.ida_event_av),
        read_json(args.hash_authority),
    )
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "AC1102_EXHAUSTIVE_UNIQUE_SEGMENT_AUTHORITY.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(
        args.output_dir / "AC1102_UNIQUE_NATIVE_SOURCES.csv",
        ["sha256", "canonical_path", "official_name", "occurrence_count", "events"],
        [
            {**row, "events": "|".join(row["events"])}
            for row in result["native_source_universe"]["unique_sources"]
        ],
    )
    write_csv(
        args.output_dir / "AC1102_EXACT_DUPLICATE_GROUPS.csv",
        ["sha256", "canonical_path", "official_name", "occurrence_count", "events"],
        [
            {**row, "events": "|".join(row["events"])}
            for row in result["native_source_universe"]["duplicate_groups"]
        ],
    )
    print(json.dumps({
        "status": result["status"],
        "routes": result["route_universe"]["route_count"],
        "events": result["runtime_structure"]["event_count"],
        "unique_native_sources": result["native_source_universe"]["unique_sha256_count"],
        "legacy_missing_unique_sources": result["legacy_longform"]["missing_required_unique_sha256_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
