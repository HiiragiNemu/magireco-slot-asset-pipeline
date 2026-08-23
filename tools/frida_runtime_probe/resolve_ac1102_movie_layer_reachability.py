#!/usr/bin/env python3
"""Close ac1102 authored MovieLayer reachability against the exact Slot binary.

This is intentionally narrower than a renderer. It proves whether the four
historically "missing" ``*_add`` movie names can be loaded by the current
binary and binds the loadable twins to their parent event-global intervals.
Audio and editorial-order gates remain independent.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .extract_crivideo_filename_table_authority import (
        CODE_AUTHORITY as CRI_CODE_AUTHORITY,
        SLOT_BINARY_SHA256,
    )
    from .extract_z2d_movie_layer_blend_authority import (
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import (  # type: ignore
        CODE_AUTHORITY as CRI_CODE_AUTHORITY,
        SLOT_BINARY_SHA256,
    )
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )


REQUIRED_Z2D_NAMES = (
    "ac1102_3off_c012_c013_c014_c015_win",
    "ac8040_shouri_EF_small",
    "ac1102_3off_c015_win_rogo",
    "ac1102_1on_c004",
    "ac1102_lev_c017_c018_c019_fukkatu_win",
    "ac1102_1on_c020_c021_fukkatu_win",
)

EXPECTED_PARENT_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "ac1102_007": {
        "ac1102_3off_c012_c013_c014_c015_win": (0, 277),
        "ac8040_shouri_EF_small": (0, 259),
        "ac1102_3off_c015_win_rogo": (232, 381),
    },
    "ac1102_013": {"ac1102_1on_c004": (0, 89)},
    "ac1102_014": {
        "ac1102_lev_c017_c018_c019_fukkatu_win": (0, 167),
        "ac8040_shouri_EF_small": (0, 259),
    },
    "ac1102_015": {
        "ac1102_1on_c020_c021_fukkatu_win": (0, 408),
        "ac8040_shouri_EF_small": (0, 259),
        "ac1102_3off_c015_win_rogo": (343, 492),
    },
}

UNREACHABLE_TO_LOADABLE_TWIN = {
    "ac8040_shouri_EF_small_add.dgm": "ac8040_shouri_EF_small.dgm",
    "ac8040_shouri_EF_small_add_LP.dgm": "ac8040_shouri_EF_small_LP.dgm",
    "ac1102_3off_c015_win_rogo_add.dgm": "ac1102_3off_c015_win_rogo.dgm",
    "ac1102_3off_c015_win_rogo_LP_add.dgm": "ac1102_3off_c015_win_rogo_LP.dgm",
}


class Ac1102ReachabilityError(ValueError):
    pass


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def extract_runtime_parent_ranges(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if runtime.get("schema") != "magireco-ac1102-missing-runtime-scene-motion-v1":
        raise Ac1102ReachabilityError("runtime scene-motion schema differs")
    if runtime.get("protected_processes_unchanged") is not True:
        raise Ac1102ReachabilityError("protected emulator processes changed during capture")
    if runtime.get("crash_tail_empty") is not True:
        raise Ac1102ReachabilityError("runtime capture has a non-empty crash tail")
    events = runtime.get("events")
    if not isinstance(events, Mapping) or set(events) != set(EXPECTED_PARENT_RANGES):
        raise Ac1102ReachabilityError("runtime event set differs")

    result: dict[str, Any] = {}
    for event, expected in EXPECTED_PARENT_RANGES.items():
        envelope = events[event]
        if envelope.get("status") != "captured":
            raise Ac1102ReachabilityError(f"runtime event was not captured: {event}")
        value = envelope.get("value")
        if not isinstance(value, Mapping):
            raise Ac1102ReachabilityError(f"runtime event payload differs: {event}")
        scenes = value.get("scenes", [])
        if len(scenes) != 1 or scenes[0].get("name") != event:
            raise Ac1102ReachabilityError(f"runtime scene binding differs: {event}")
        cuts = scenes[0].get("cuts", [])
        if len(cuts) != 1 or cuts[0].get("cut_name") != event:
            raise Ac1102ReachabilityError(f"runtime cut binding differs: {event}")
        cut = cuts[0]
        observed: dict[str, tuple[int, int]] = {}
        for node in _walk_nodes(cut.get("nodes", [])):
            name = str(node.get("name", ""))
            if not name.endswith(".z2d"):
                continue
            base = name[:-4]
            if base not in expected:
                continue
            motions = node.get("motions", [])
            if len(motions) != 1 or motions[0].get("is_z2d_motion") is not True:
                raise Ac1102ReachabilityError(f"Z2D motion binding differs: {event}/{base}")
            keys = motions[0].get("keys", [])
            if len(keys) != 1:
                raise Ac1102ReachabilityError(f"Z2D key count differs: {event}/{base}")
            values = keys[0].get("floats", [])
            if len(values) < 6:
                raise Ac1102ReachabilityError(f"Z2D key payload is short: {event}/{base}")
            starts = values[0], values[2], values[4]
            ends = values[1], values[3], values[5]
            if len(set(starts)) != 1 or len(set(ends)) != 1:
                raise Ac1102ReachabilityError(f"Z2D key triplets differ: {event}/{base}")
            start, end = starts[0], ends[0]
            if int(start) != start or int(end) != end:
                raise Ac1102ReachabilityError(f"Z2D parent range is non-integral: {event}/{base}")
            if base in observed:
                raise Ac1102ReachabilityError(f"duplicate Z2D parent binding: {event}/{base}")
            observed[base] = int(start), int(end)
        if observed != expected:
            raise Ac1102ReachabilityError(
                f"runtime parent ranges differ for {event}: {observed} != {expected}"
            )
        result[event] = {
            "cut_start_frame": int(cut["cut_start_frame"]),
            "cut_end_frame_inclusive": int(cut["cut_end_frame"]),
            "z2d_parent_ranges": {
                name: {"start_frame": start, "end_frame_inclusive": end}
                for name, (start, end) in observed.items()
            },
        }
    return result


def classify_unreachable_twins(layers: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_reference: dict[str, Mapping[str, Any]] = {}
    for layer in layers:
        reference = str(layer["z2d_reference"])
        if reference in by_reference:
            raise Ac1102ReachabilityError(f"duplicate MovieLayer reference: {reference}")
        by_reference[reference] = layer
    if set(UNREACHABLE_TO_LOADABLE_TWIN) - set(by_reference):
        raise Ac1102ReachabilityError("one or more authored _add MovieLayers are absent")

    result: list[dict[str, Any]] = []
    for unreachable_name, twin_name in UNREACHABLE_TO_LOADABLE_TWIN.items():
        unreachable = by_reference[unreachable_name]
        twin = by_reference.get(twin_name)
        if twin is None:
            raise Ac1102ReachabilityError(f"loadable twin is absent: {twin_name}")
        if unreachable.get("compiled_table_present") is not False:
            raise Ac1102ReachabilityError(f"_add layer unexpectedly loadable: {unreachable_name}")
        if twin.get("compiled_table_present") is not True:
            raise Ac1102ReachabilityError(f"non-add twin unexpectedly unavailable: {twin_name}")
        comparable = (
            "start_frame",
            "end_frame_inclusive",
            "position",
            "pivot",
            "layer_width",
            "layer_height",
        )
        if any(unreachable.get(key) != twin.get(key) for key in comparable):
            raise Ac1102ReachabilityError(
                f"unreachable layer and loadable twin geometry/timing differ: {unreachable_name}"
            )
        result.append(
            {
                "unreachable_authored_layer": unreachable_name,
                "runtime_disposition": "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE",
                "loadable_same_interval_twin": twin_name,
                "start_frame": unreachable["start_frame"],
                "end_frame_inclusive": unreachable["end_frame_inclusive"],
                "unreachable_blend_enum": unreachable["authored_blend_enum"],
                "loadable_twin_blend_enum": twin["authored_blend_enum"],
            }
        )
    return result


def build_report(
    *,
    binary: Path,
    z2d_manifest_path: Path,
    filename_table_csv: Path,
    runtime_scene_motion_path: Path,
) -> dict[str, Any]:
    build_id, blend_state_table, blend_table_offset = validate_exact_binary(binary)
    manifest = json.loads(z2d_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1":
        raise Ac1102ReachabilityError("named Z2D manifest schema differs")
    if manifest.get("status") != "passed":
        raise Ac1102ReachabilityError("named Z2D extraction did not pass")
    chunks = manifest.get("chunks", [])
    if {row.get("name") for row in chunks} != set(REQUIRED_Z2D_NAMES):
        raise Ac1102ReachabilityError("named Z2D set differs")

    compiled_names = read_filename_table(filename_table_csv)
    runtime_raw = json.loads(runtime_scene_motion_path.read_text(encoding="utf-8"))
    runtime_ranges = extract_runtime_parent_ranges(runtime_raw)
    parsed_chunks: list[dict[str, Any]] = []
    all_layers: list[dict[str, Any]] = []
    headers: dict[str, dict[str, Any]] = {}
    for source in chunks:
        path = Path(source["output_path"])
        data = path.read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{source['name']}.z2d":
            raise Ac1102ReachabilityError(f"Z2D filename differs: {source['name']}")
        if header["frame_rate"] != 30.0 or (
            header["canvas_width"], header["canvas_height"]
        ) != (1024, 576):
            raise Ac1102ReachabilityError(f"Z2D native geometry differs: {source['name']}")
        headers[source["name"]] = header
        layers: list[dict[str, Any]] = []
        for reference in source.get("dgm_references", []):
            layer = parse_movie_layer(data, reference, blend_state_table)
            base_name = reference[:-4]
            table_index = compiled_names.get(base_name)
            layer.update(
                {
                    "parent_z2d": source["name"],
                    "cri_lookup_base_name": base_name,
                    "compiled_table_present": table_index is not None,
                    "compiled_table_index": table_index,
                    "runtime_load_disposition": (
                        "LOADABLE_BY_EXACT_NAME"
                        if table_index is not None
                        else "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"
                    ),
                }
            )
            layers.append(layer)
            all_layers.append(layer)
        parsed_chunks.append(
            {
                "name": source["name"],
                "path": str(path.resolve()),
                "chunk_index": source["chunk_index"],
                "chunk_offset": source["offset"],
                "chunk_size": source["size"],
                "header": header,
                "movie_layers": layers,
            }
        )

    parent_lengths_match = True
    for mappings in EXPECTED_PARENT_RANGES.values():
        for z2d_name, (start, end) in mappings.items():
            parent_lengths_match &= end - start + 1 == headers[z2d_name]["scene_frame_count"]
    if not parent_lengths_match:
        raise Ac1102ReachabilityError("parent event ranges do not match exact Z2D frame counts")
    twin_rows = classify_unreachable_twins(all_layers)
    unreachable = [row for row in all_layers if not row["compiled_table_present"]]
    if {row["z2d_reference"] for row in unreachable} != set(UNREACHABLE_TO_LOADABLE_TWIN):
        raise Ac1102ReachabilityError("unloadable authored MovieLayer set differs")

    return {
        "schema": "magireco-ac1102-movielayer-runtime-reachability-authority-v1",
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
            "inherited_sha256": SLOT_BINARY_SHA256,
        },
        "inputs": {
            "named_z2d_manifest": str(z2d_manifest_path.resolve()),
            "compiled_crivideo_filename_table": str(filename_table_csv.resolve()),
            "compiled_crivideo_filename_entry_count": len(compiled_names),
            "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
            "runtime_transport": runtime_raw.get("transport"),
            "runtime_target_pid": runtime_raw.get("target_pid"),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in (*CRI_CODE_AUTHORITY, *Z2D_CODE_AUTHORITY)
        ],
        "blend_state_table": {
            "file_offset_hex": f"0x{blend_table_offset:x}",
            "renderer_states_by_blend_enum_1_to_30": blend_state_table,
        },
        "runtime_parent_event_ranges": runtime_ranges,
        "z2d_chunks": parsed_chunks,
        "unreachable_authored_layers_and_loadable_twins": twin_rows,
        "decision": {
            "old_missing_layer_media_blocker": "CLOSED_AS_CODE_UNREACHABLE_AUTHORED_LAYERS",
            "required_visible_media_missing": False,
            "new_longform_render_allowed_by_this_report_alone": False,
            "remaining_independent_gates": [
                "event_audio_and_strict_no_bgm_manifest_closure",
                "duplicate_free_exhaustive_editorial_order",
            ],
        },
        "assertions": {
            "compiled_filename_entries": len(compiled_names),
            "parent_event_bindings": sum(len(row) for row in EXPECTED_PARENT_RANGES.values()),
            "parent_event_ranges_match_exact_z2d_frame_counts": parent_lengths_match,
            "authored_movie_layers": len(all_layers),
            "loadable_movie_layers": sum(row["compiled_table_present"] for row in all_layers),
            "unreachable_add_movie_layers": len(unreachable),
            "all_four_unreachable_layers_have_same_interval_loadable_twins": len(twin_rows) == 4,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "AC1102_MOVIELAYER_REACHABILITY_AUTHORITY.json"
    csv_path = output_dir / "AC1102_MOVIELAYERS.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = [
        {"z2d_name": chunk["name"], **layer}
        for chunk in report["z2d_chunks"]
        for layer in chunk["movie_layers"]
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification = {
        "schema": "magireco-ac1102-movielayer-reachability-verification-v1",
        "status": "passed",
        "checks": report["assertions"],
        "decision": report["decision"],
        "outputs": [report_path.name, csv_path.name, readme_path.name],
    }
    verification_path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    readme_path.write_text(
        "# ac1102 MovieLayer runtime reachability authority\n\n"
        "The exact Slot binary loads CRI movies by exact compiled name. The four authored "
        "`*_add` layers are absent from that table and therefore return false. Each has a "
        "loadable non-add twin with the same authored interval and geometry. Runtime capture "
        "binds the containing Z2Ds to exact event-global ranges. The historical missing-layer "
        "blocker is closed; audio/no-BGM and duplicate-free editorial order remain separate "
        "fail-closed gates. No media was changed.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d-manifest", required=True, type=Path)
    parser.add_argument("--filename-table-csv", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary,
        z2d_manifest_path=args.z2d_manifest,
        filename_table_csv=args.filename_table_csv,
        runtime_scene_motion_path=args.runtime_scene_motion,
    )
    write_outputs(report, args.output_dir)
    checks = report["assertions"]
    print(
        "PASS "
        f"parent_bindings={checks['parent_event_bindings']} "
        f"movie_layers={checks['authored_movie_layers']} "
        f"loadable={checks['loadable_movie_layers']} "
        f"unreachable_add={checks['unreachable_add_movie_layers']} "
        "missing_layer_blocker=CLOSED audio_order_gates=OPEN"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
