#!/usr/bin/env python3
"""Audit one Slot family as an exhaustive, source-identity-unique longform.

The audit is deliberately render-free.  It derives the event universe from
DirInfo, requires runtime scene/cut coverage for that complete universe, and
uses CRI package/index plus the durable source path as the exact source asset
identity.  Repeated use of one source asset is therefore counted once for the
future exhaustive editorial longform even when it appears in mutually
exclusive event containers.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

try:
    from tools.frida_runtime_probe.resolve_ac1102_exhaustive_unique_segments import (
        cut_frames,
        cut_structure,
        durable_source_path,
        structure_key,
        validate_ida_event_av,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.resolve_ac1102_exhaustive_unique_segments import (
        cut_frames,
        cut_structure,
        durable_source_path,
        structure_key,
        validate_ida_event_av,
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def derive_routes(
    rows: list[dict[str, str]],
    family: str,
    dirinfo_kind: int,
    expected_route_count: int,
) -> dict[str, Any]:
    selected = [row for row in rows if int(row["kind"]) == dirinfo_kind]
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[int(row["row_index"])].append(row)
    if expected_route_count <= 0 or set(grouped) != set(range(expected_route_count)):
        raise ValueError(f"{family} DirInfo rows are not a complete zero-based range")

    routes: list[dict[str, Any]] = []
    event_union: set[str] = set()
    for row_index in range(expected_route_count):
        values = sorted(grouped[row_index], key=lambda row: int(row["selector_raw"]))
        events = [row["scene_name"] for row in values]
        if not events or any(not event.startswith(family + "_") for event in events):
            raise ValueError(f"DirInfo row {row_index} contains a foreign event")
        event_union.update(events)
        routes.append(
            {
                "row_index": row_index,
                "selector_values": [int(row["selector_raw"]) for row in values],
                "event_sequence": events,
                "legacy_resolved_source_counts": [
                    int(row["resolved_source_count"]) for row in values
                ],
            }
        )
    return {
        "kind": dirinfo_kind,
        "route_count": len(routes),
        "routes": routes,
        "unique_event_count": len(event_union),
        "unique_events": sorted(event_union),
        "legacy_resolved_source_count_is_authoritative": False,
    }


def validate_runtime(
    runtime: Mapping[str, Any],
    lockframes: Mapping[str, Any],
    family: str,
    required_events: tuple[str, ...],
) -> None:
    if (
        runtime.get("schema") != f"magireco-{family}-runtime-scene-motion-v1"
        or runtime.get("host_frida_version") != "17.16.4"
        or runtime.get("protected_processes_unchanged") is not True
        or runtime.get("crash_tail_empty") is not True
        or tuple(runtime.get("requested_events", {})) != required_events
        or set(runtime.get("events", {})) != set(required_events)
    ):
        raise ValueError(f"bounded {family} runtime scene capture differs")
    if (
        lockframes.get("schema") != f"magireco-{family}-runtime-lockframe-v1"
        or lockframes.get("host_frida_version") != "17.16.4"
        or lockframes.get("protected_processes_unchanged") is not True
        or lockframes.get("crash_tail_empty") is not True
        or set(lockframes.get("events", {})) != set(required_events)
    ):
        raise ValueError(f"bounded {family} LockFrame capture differs")


def source_identity(row: Mapping[str, str]) -> str:
    package = row.get("package", "")
    index = row.get("package_index", "")
    if not package or not index:
        raise ValueError("source catalog row lacks CRI package/index identity")
    return f"{package}:{index}"


def resolve(
    *,
    family: str,
    dirinfo_kind: int,
    expected_route_count: int,
    native_width: int,
    native_height: int,
    runtime: Mapping[str, Any],
    lockframes: Mapping[str, Any],
    dirinfo_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    legacy_manifest: Mapping[str, Any],
    ida_event_av: Mapping[str, Any],
) -> dict[str, Any]:
    validate_ida_event_av(ida_event_av)
    routes = derive_routes(
        dirinfo_rows, family, dirinfo_kind, expected_route_count
    )
    required_events = tuple(routes["unique_events"])
    validate_runtime(runtime, lockframes, family, required_events)

    cut_rows: list[dict[str, Any]] = []
    cut_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_rows: list[dict[str, Any]] = []
    for event in required_events:
        value = runtime["events"][event]
        if "value" in value:
            if value.get("status") != "captured":
                raise ValueError(f"runtime event was not captured: {event}")
            value = value["value"]
        if value.get("group_name") != family:
            raise ValueError(f"runtime event group differs: {event}")
        scene_lengths: list[int] = []
        event_cut_count = 0
        for scene in value.get("scenes", []):
            scene_cut_lengths: list[int] = []
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
                cut_rows.append(row)
                cut_groups[key].append(row)
                scene_cut_lengths.append(frames)
                event_cut_count += 1
            if scene_cut_lengths:
                scene_lengths.append(max(scene_cut_lengths))
        if not scene_lengths:
            raise ValueError(f"runtime event has no scene cut: {event}")
        event_rows.append(
            {
                "event": event,
                "scene_count": len(value.get("scenes", [])),
                "cut_count": event_cut_count,
                "parallel_scene_frame_lengths": scene_lengths,
                "container_frames": max(scene_lengths),
                "container_seconds": max(scene_lengths) / 30,
                "lock_frame": int(lockframes["events"][event]["lock_frame"]),
            }
        )

    family_catalog = [
        row for row in source_rows if row.get("event_name") in required_events
    ]
    if {row["event_name"] for row in family_catalog} != set(required_events):
        raise ValueError(f"source catalog does not cover every {family} event")

    present: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    identity_metadata: dict[str, tuple[str, str, int, int]] = {}
    for row in family_catalog:
        if row.get("source_exists", "").casefold() != "yes":
            missing.append(
                {
                    "event": row["event_name"],
                    "z2d_name": row["z2d_name"],
                    "dgm_name": row["dgm_name"],
                }
            )
            continue
        identity = source_identity(row)
        path = durable_source_path(row["source_mp4"]).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        width = int(row["width"])
        height = int(row["height"])
        metadata = (str(path), row["official_name"], width, height)
        prior = identity_metadata.setdefault(identity, metadata)
        if prior != metadata:
            raise ValueError(f"CRI source identity metadata differs: {identity}")
        present.append(
            {
                "event": row["event_name"],
                "z2d_name": row["z2d_name"],
                "dgm_name": row["dgm_name"],
                "source_identity": identity,
                "official_name": row["official_name"],
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "width": width,
                "height": height,
                "native": width == native_width and height == native_height,
            }
        )

    native = [row for row in present if row["native"]]
    components = [row for row in present if not row["native"]]

    def grouped(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            result[row["source_identity"]].append(row)
        return result

    native_groups = grouped(native)
    component_groups = grouped(components)
    unique_sources: list[dict[str, Any]] = []
    duplicate_groups: list[dict[str, Any]] = []
    for identity, rows in sorted(native_groups.items()):
        canonical = rows[0]
        summary = {
            "source_identity": identity,
            "official_name": canonical["official_name"],
            "canonical_path": canonical["path"],
            "size_bytes": canonical["size_bytes"],
            "occurrence_count": len(rows),
            "events": [row["event"] for row in rows],
        }
        unique_sources.append(summary)
        if len(rows) > 1:
            duplicate_groups.append(summary)

    legacy_events = tuple(legacy_manifest.get("ordered_events", []))
    legacy_event_set = set(legacy_events)
    foreign_legacy = sorted(legacy_event_set - set(required_events))
    if foreign_legacy:
        raise ValueError(f"legacy manifest contains foreign events: {foreign_legacy}")
    legacy_native = [row for row in native if row["event"] in legacy_event_set]
    legacy_groups = grouped(legacy_native)
    missing_unique = sorted(set(native_groups) - set(legacy_groups))
    missing_identities = sorted({row["dgm_name"] for row in missing})

    complete_event_set = legacy_event_set == set(required_events)
    duplicate_free = len(legacy_native) == len(legacy_groups)
    final_authoritative = complete_event_set and duplicate_free and not missing
    blockers: list[dict[str, Any]] = []
    if not complete_event_set:
        blockers.append(
            {
                "kind": "legacy_missing_events",
                "events": sorted(set(required_events) - legacy_event_set),
            }
        )
    if not duplicate_free:
        blockers.append(
            {
                "kind": "legacy_repeats_exact_cri_source_assets",
                "surplus_occurrence_count": len(legacy_native) - len(legacy_groups),
                "duplicate_group_count": sum(
                    len(rows) > 1 for rows in legacy_groups.values()
                ),
            }
        )
    if missing:
        blockers.append(
            {
                "kind": "missing_layer_media",
                "occurrence_count": len(missing),
                "identities": missing_identities,
            }
        )
    blockers.append(
        {
            "kind": "duplicate_free_editorial_timeline_not_yet_bound",
            "reason": "retain every unique source asset once in logical order while preserving verified event-global layer timing and audio",
        }
    )

    return {
        "schema": "magireco-exhaustive-family-source-identity-audit-v1",
        "status": "PASS_RENDER_PAUSED",
        "family": family,
        "native_dimensions": {"width": native_width, "height": native_height},
        "frame_rate": "30/1",
        "identity_rule": {
            "exact_identity": "CRI package plus package_index plus identical durable source path",
            "cross_path_binary_identity_claimed": False,
            "machine_vision_used": False,
        },
        "product_standard": {
            "one_exhaustive_longform": True,
            "include_mutually_exclusive_outcomes": True,
            "each_exact_source_identity_once": True,
            "logical_editorial_order_required": True,
            "native_single_session_claimed": False,
        },
        "route_universe": routes,
        "runtime_structure": {
            "event_count": len(event_rows),
            "events": event_rows,
            "cut_occurrence_count": len(cut_rows),
            "unique_cut_structure_count": len(cut_groups),
            "duplicate_cut_structure_surplus": len(cut_rows) - len(cut_groups),
            "cuts": cut_rows,
            "parallel_scene_duration_rule": "maximum_not_sum",
        },
        "native_source_universe": {
            "occurrence_count": len(native),
            "unique_source_identity_count": len(native_groups),
            "duplicate_surplus_occurrence_count": len(native) - len(native_groups),
            "duplicate_group_count": len(duplicate_groups),
            "unique_sources": unique_sources,
            "duplicate_groups": duplicate_groups,
        },
        "component_universe": {
            "present_occurrence_count": len(components),
            "present_unique_source_identity_count": len(component_groups),
            "missing_occurrence_count": len(missing),
            "missing_unique_identity_count": len(missing_identities),
            "missing_identities": missing_identities,
            "missing_rows": missing,
        },
        "legacy_longform": {
            "duration_ms": int(legacy_manifest["media"]["duration_ms"]),
            "event_count": len(legacy_events),
            "events": list(legacy_events),
            "complete_event_set": complete_event_set,
            "native_source_occurrence_count": len(legacy_native),
            "unique_native_source_identity_count": len(legacy_groups),
            "duplicate_surplus_occurrence_count": len(legacy_native)
            - len(legacy_groups),
            "missing_required_unique_source_identity_count": len(missing_unique),
            "missing_required_unique_source_identities": missing_unique,
            "duplicate_free": duplicate_free,
            "exhaustive_authoritative": final_authoritative,
        },
        "decision": {
            "legacy_longform_final_authority": final_authoritative,
            "route_fragments_are_final_product": False,
            "new_render_allowed": False,
            "blockers": blockers,
        },
        "source_media_modified": False,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "source_identity",
        "official_name",
        "canonical_path",
        "size_bytes",
        "occurrence_count",
        "events",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "events": "|".join(row["events"])})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True)
    parser.add_argument("--dirinfo-kind", type=int, required=True)
    parser.add_argument("--expected-route-count", type=int, required=True)
    parser.add_argument("--native-width", type=int, required=True)
    parser.add_argument("--native-height", type=int, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--lockframes", type=Path, required=True)
    parser.add_argument("--dirinfo", type=Path, required=True)
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--ida-event-av", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    result = resolve(
        family=args.family,
        dirinfo_kind=args.dirinfo_kind,
        expected_route_count=args.expected_route_count,
        native_width=args.native_width,
        native_height=args.native_height,
        runtime=read_json(args.runtime),
        lockframes=read_json(args.lockframes),
        dirinfo_rows=read_csv(args.dirinfo),
        source_rows=read_csv(args.source_catalog),
        legacy_manifest=read_json(args.legacy_manifest),
        ida_event_av=read_json(args.ida_event_av),
    )
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "EXHAUSTIVE_FAMILY_SOURCE_IDENTITY_AUDIT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(
        args.output_dir / "UNIQUE_NATIVE_SOURCE_IDENTITIES.csv",
        result["native_source_universe"]["unique_sources"],
    )
    write_csv(
        args.output_dir / "DUPLICATE_NATIVE_SOURCE_IDENTITY_GROUPS.csv",
        result["native_source_universe"]["duplicate_groups"],
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "family": result["family"],
                "routes": result["route_universe"]["route_count"],
                "events": result["runtime_structure"]["event_count"],
                "native_occurrences": result["native_source_universe"][
                    "occurrence_count"
                ],
                "unique_native_sources": result["native_source_universe"][
                    "unique_source_identity_count"
                ],
                "legacy_final_authority": result["decision"][
                    "legacy_longform_final_authority"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
