#!/usr/bin/env python3
"""Resolve exact ac1101 parent/secondary Z2D and MovieLayer reachability.

The resolver joins the exact Slot CRI filename table, exact named Z2D chunks,
the bounded thirteen-event runtime scene capture, and the legacy timeline.  It
uses code/runtime structure rather than rendered pixels and explicitly retains
the TUDUKU and ANTEN secondary scenes that the legacy inventory omitted.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .extract_crivideo_filename_table_authority import CODE_AUTHORITY as CRI_CODE_AUTHORITY
    from .extract_z2d_movie_layer_blend_authority import (
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import CODE_AUTHORITY as CRI_CODE_AUTHORITY  # type: ignore
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )


EVENTS = tuple(f"ac1101_{index:03d}" for index in range(1, 14))
EXPECTED_MODULE = (
    "split_config.arm64_v8a.apk",
    "/data/app/~~w196OEQ5FYrNgE6LHA9tnQ==/com.universal777.magireco-"
    "rHM8me-Z6EdQJaFV4cbnQA==/split_config.arm64_v8a.apk",
    80689936,
)

# event -> (scene, cut, instance offset, parent Z2D, local start, local end)
EXPECTED_BINDINGS: dict[str, tuple[tuple[str, str, int, str, int, int], ...]] = {
    "ac1101_001": (("ac1101_001", "ac1101_001", 0, "ac1101_lev_c001_c002_title_wht_S", 0, 172),),
    "ac1101_002": (("ac1101_002", "ac1101_002", 0, "ac1101_1on_c003", 0, 100),),
    "ac1101_003": (
        ("ac1101_003", "ac1101_003", 0, "ac1101_3on_c005_c006", 0, 169),
        ("TUDUKU", "ac8000_003", 130, "ac8000_cmn_tx_tuduku", 0, 119),
    ),
    "ac1101_004": (("ac1101_004", "ac1101_004", 0, "ac1101_3on_c008", 0, 109),),
    "ac1101_005": (
        ("ac1101_005", "ac1101_005", 0, "ac1101_3off_c011_lose", 0, 119),
        ("ANTEN", "ac8040_001", 53, "ac8040_kyo_anten", 0, 29),
    ),
    "ac1101_006": (
        ("ac1101_006", "ac1101_006", 0, "ac1101_3off_c009_c010_win", 0, 169),
        ("ac1101_006", "ac1101_006", 0, "ac8040_shouri_EF_small", 0, 259),
        ("ac1101_006", "ac1101_006", 0, "ac1101_3off_win_rogo", 103, 252),
    ),
    "ac1101_007": (("ac1101_007", "ac1101_007", 0, "ac1101_1on_c004_L", 0, 135),),
    "ac1101_008": (("ac1101_008", "ac1101_008", 0, "ac1101_lev_c001_c002_title_red_S", 0, 172),),
    "ac1101_009": (("ac1101_009", "ac1101_009", 0, "ac1101_lev_c001_c002_title_wht_L", 0, 172),),
    "ac1101_010": (("ac1101_010", "ac1101_010", 0, "ac1101_lev_c001_c002_title_red_L", 0, 172),),
    "ac1101_011": (("ac1101_011", "ac1101_011", 0, "ac1101_lev_c007", 0, 104),),
    "ac1101_012": (
        ("ac1101_012", "ac1101_012", 0, "ac1101_lev_c012_c013_fukkatu_win", 0, 290),
        ("ac1101_012", "ac1101_012", 0, "ac8040_shouri_EF_small", 0, 259),
    ),
    "ac1101_013": (
        ("ac1101_013", "ac1101_013", 0, "ac1101_1on_c014_c015_c016_fukkatu_win", 0, 473),
        ("ac1101_013", "ac1101_013", 0, "ac8040_shouri_EF_small", 0, 259),
        ("ac1101_013", "ac1101_013", 0, "ac1101_3off_win_rogo", 398, 547),
    ),
}
REQUIRED_Z2D_NAMES = tuple(
    dict.fromkeys(binding[3] for rows in EXPECTED_BINDINGS.values() for binding in rows)
)
UNREACHABLE_TO_LOADABLE_TWIN = {
    "ac8040_shouri_EF_small_add.dgm": "ac8040_shouri_EF_small.dgm",
    "ac8040_shouri_EF_small_add_LP.dgm": "ac8040_shouri_EF_small_LP.dgm",
    "ac1101_3off_c010_win_rogo_add.dgm": "ac1101_3off_c010_win_rogo.dgm",
    "ac1101_3off_c010_win_rogo_add_LP.dgm": "ac1101_3off_c010_win_rogo_LP.dgm",
}
LEGACY_MISSING_LOADABLE_DGMS = {
    "ac8000_cmn_tx_tuduku",
    "ac8000_cmn_tx_tuduku_LP",
    "ac8040_kyo_anten",
}


class Ac1101ReachabilityError(ValueError):
    pass


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def _z2d_range(node: Mapping[str, Any], event: str, name: str) -> tuple[int, int]:
    motions = node.get("motions", [])
    if len(motions) != 1 or motions[0].get("is_z2d_motion") is not True:
        raise Ac1101ReachabilityError(f"Z2D motion binding differs: {event}/{name}")
    keys = motions[0].get("keys", [])
    if len(keys) != 1:
        raise Ac1101ReachabilityError(f"Z2D key count differs: {event}/{name}")
    values = keys[0].get("floats", [])
    if len(values) < 6:
        raise Ac1101ReachabilityError(f"Z2D key payload is short: {event}/{name}")
    starts, ends = values[0::2][:3], values[1::2][:3]
    if len(set(starts)) != 1 or len(set(ends)) != 1:
        raise Ac1101ReachabilityError(f"Z2D key triplets differ: {event}/{name}")
    start, end = starts[0], ends[0]
    if int(start) != start or int(end) != end:
        raise Ac1101ReachabilityError(f"Z2D parent range is fractional: {event}/{name}")
    return int(start), int(end)


def extract_runtime_bindings(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if runtime.get("schema") != "magireco-ac1101-runtime-scene-motion-v1":
        raise Ac1101ReachabilityError("runtime scene-motion schema differs")
    if runtime.get("host_frida_version") != "17.16.4":
        raise Ac1101ReachabilityError("runtime Frida version differs")
    if runtime.get("protected_processes_unchanged") is not True:
        raise Ac1101ReachabilityError("protected emulator processes changed")
    if runtime.get("crash_buffer_unchanged") is not True:
        raise Ac1101ReachabilityError("crash buffer changed during capture")
    if runtime.get("process_restart_or_app_switch_performed") is not False:
        raise Ac1101ReachabilityError("capture restarted or switched an application")
    if runtime.get("module_rows") != [list(EXPECTED_MODULE)]:
        raise Ac1101ReachabilityError("runtime ARM64 module identity differs")
    events = runtime.get("events")
    if not isinstance(events, Mapping) or set(events) != set(EVENTS):
        raise Ac1101ReachabilityError("runtime event set differs")

    result: dict[str, Any] = {}
    for event, expected_rows in EXPECTED_BINDINGS.items():
        value = events[event]
        expected_scene_names = {row[0] for row in expected_rows}
        observed_scene_names = {str(row.get("name")) for row in value.get("scenes", [])}
        if observed_scene_names != expected_scene_names:
            raise Ac1101ReachabilityError(f"runtime scene set differs: {event}")
        event_rows: list[dict[str, Any]] = []
        for scene_name, cut_name, offset, z2d_name, expected_start, expected_end in expected_rows:
            scenes = [row for row in value.get("scenes", []) if row.get("name") == scene_name]
            if len(scenes) != 1:
                raise Ac1101ReachabilityError(f"runtime scene differs: {event}/{scene_name}")
            cuts = [row for row in scenes[0].get("cuts", []) if row.get("cut_name") == cut_name]
            if len(cuts) != 1:
                raise Ac1101ReachabilityError(f"runtime cut differs: {event}/{cut_name}")
            cut = cuts[0]
            if int(cut.get("instance_offset_frames", -1)) != offset:
                raise Ac1101ReachabilityError(f"runtime scene offset differs: {event}/{scene_name}")
            matching = []
            for node in _walk_nodes(cut.get("nodes", [])):
                name = str(node.get("name", ""))
                base = name[:-4] if name.endswith(".z2d") else name
                if base == z2d_name:
                    matching.append(node)
            if len(matching) != 1:
                raise Ac1101ReachabilityError(f"runtime parent Z2D differs: {event}/{z2d_name}")
            start, end = _z2d_range(matching[0], event, z2d_name)
            if (start, end) != (expected_start, expected_end):
                raise Ac1101ReachabilityError(f"runtime parent range differs: {event}/{z2d_name}")
            event_rows.append(
                {
                    "scene_name": scene_name,
                    "cut_name": cut_name,
                    "cut_instance_offset_frames": offset,
                    "cut_start_frame": int(cut["cut_start_frame"]),
                    "cut_end_frame": int(cut["cut_end_frame"]),
                    "parent_z2d": z2d_name,
                    "local_start_frame": start,
                    "local_end_frame_inclusive": end,
                    "event_global_start_frame": offset + start,
                    "event_global_end_frame_inclusive": offset + end,
                }
            )
        result[event] = event_rows
    return result


def classify_unreachable_twins(layers: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_reference = {str(row["z2d_reference"]): row for row in layers}
    comparable = ("start_frame", "end_frame_inclusive", "position", "pivot", "layer_width", "layer_height")
    result: list[dict[str, Any]] = []
    for unreachable_name, twin_name in UNREACHABLE_TO_LOADABLE_TWIN.items():
        unreachable, twin = by_reference.get(unreachable_name), by_reference.get(twin_name)
        if unreachable is None or twin is None:
            raise Ac1101ReachabilityError(f"unreachable/twin pair absent: {unreachable_name}")
        if unreachable.get("compiled_table_present") is not False or twin.get("compiled_table_present") is not True:
            raise Ac1101ReachabilityError(f"unreachable/twin loadability differs: {unreachable_name}")
        if any(unreachable.get(key) != twin.get(key) for key in comparable):
            raise Ac1101ReachabilityError(f"unreachable/twin geometry differs: {unreachable_name}")
        result.append(
            {
                "unreachable_authored_layer": unreachable_name,
                "loadable_same_interval_twin": twin_name,
                "start_frame": unreachable["start_frame"],
                "end_frame_inclusive": unreachable["end_frame_inclusive"],
            }
        )
    return result


def read_legacy_inventory(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["event_name"].startswith("ac1101_")]
    events = {row["event_name"] for row in rows}
    z2ds = {row["z2d_name"] for row in rows}
    dgms = {row["dgm_name"] for row in rows}
    if (len(rows), len(events), len(z2ds), len(dgms)) != (58, 13, 15, 36):
        raise Ac1101ReachabilityError("legacy ac1101 inventory dimensions differ")
    if {"ac8000_cmn_tx_tuduku", "ac8040_kyo_anten"} & z2ds:
        raise Ac1101ReachabilityError("legacy inventory unexpectedly contains secondary scenes")
    if LEGACY_MISSING_LOADABLE_DGMS & dgms:
        raise Ac1101ReachabilityError("legacy inventory unexpectedly contains recovered secondary media")
    return {
        "row_count": len(rows),
        "event_count": len(events),
        "unique_parent_z2d_count": len(z2ds),
        "unique_dgm_name_count": len(dgms),
        "missing_secondary_parent_z2ds": ["ac8000_cmn_tx_tuduku", "ac8040_kyo_anten"],
        "missing_loadable_dgm_names": sorted(LEGACY_MISSING_LOADABLE_DGMS),
    }


def build_report(
    *,
    binary: Path,
    z2d_manifest_path: Path,
    filename_table_csv: Path,
    runtime_scene_motion_path: Path,
    legacy_timeline_csv: Path,
) -> dict[str, Any]:
    build_id, blend_state_table, blend_table_offset = validate_exact_binary(binary)
    manifest = json.loads(z2d_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1" or manifest.get("status") != "passed":
        raise Ac1101ReachabilityError("named Z2D extraction differs")
    chunks = manifest.get("chunks", [])
    if {row.get("name") for row in chunks} != set(REQUIRED_Z2D_NAMES):
        raise Ac1101ReachabilityError("named Z2D set differs")
    runtime = extract_runtime_bindings(json.loads(runtime_scene_motion_path.read_text(encoding="utf-8")))
    compiled_names = read_filename_table(filename_table_csv)

    parsed_chunks: list[dict[str, Any]] = []
    all_layers: list[dict[str, Any]] = []
    headers: dict[str, dict[str, Any]] = {}
    for source in chunks:
        data = Path(source["output_path"]).read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{source['name']}.z2d" or header["frame_rate"] != 30.0:
            raise Ac1101ReachabilityError(f"Z2D header differs: {source['name']}")
        headers[source["name"]] = header
        layers: list[dict[str, Any]] = []
        for reference in source.get("dgm_references", []):
            layer = parse_movie_layer(data, reference, blend_state_table)
            table_index = compiled_names.get(reference[:-4])
            layer.update(
                {
                    "parent_z2d": source["name"],
                    "compiled_table_present": table_index is not None,
                    "compiled_table_index": table_index,
                }
            )
            layers.append(layer)
            all_layers.append(layer)
        parsed_chunks.append({"name": source["name"], "header": header, "movie_layers": layers})

    for bindings in EXPECTED_BINDINGS.values():
        for _, _, _, name, start, end in bindings:
            if end - start + 1 != headers[name]["scene_frame_count"]:
                raise Ac1101ReachabilityError(f"runtime/Z2D frame count differs: {name}")
    twin_rows = classify_unreachable_twins(all_layers)
    unreachable = [row for row in all_layers if not row["compiled_table_present"]]
    if {row["z2d_reference"] for row in unreachable} != set(UNREACHABLE_TO_LOADABLE_TWIN):
        raise Ac1101ReachabilityError("unloadable authored MovieLayer set differs")
    unique_refs = {row["z2d_reference"] for row in all_layers}
    unique_loadable = {row["z2d_reference"] for row in all_layers if row["compiled_table_present"]}
    if (len(all_layers), len(unique_refs), len(unique_loadable)) != (49, 39, 35):
        raise Ac1101ReachabilityError("exact ac1101 MovieLayer dimensions differ")
    if not LEGACY_MISSING_LOADABLE_DGMS <= {name[:-4] for name in unique_loadable}:
        raise Ac1101ReachabilityError("recovered secondary DGM set differs")
    legacy = read_legacy_inventory(legacy_timeline_csv)

    return {
        "schema": "magireco-ac1101-movielayer-runtime-reachability-authority-v1",
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
            "identity_from_named_z2d_manifest": manifest["binary"],
        },
        "inputs": {
            "named_z2d_manifest": str(z2d_manifest_path.resolve()),
            "compiled_crivideo_filename_table": str(filename_table_csv.resolve()),
            "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
            "legacy_timeline": str(legacy_timeline_csv.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in (*CRI_CODE_AUTHORITY, *Z2D_CODE_AUTHORITY)
        ],
        "blend_state_table": {
            "file_offset_hex": f"0x{blend_table_offset:x}",
            "renderer_states_by_blend_enum_1_to_30": blend_state_table,
        },
        "runtime_event_bindings": runtime,
        "z2d_chunks": parsed_chunks,
        "unreachable_authored_layers_and_loadable_twins": twin_rows,
        "legacy_inventory": legacy,
        "decision": {
            "legacy_36_video_inventory": "WITHDRAWN_INCOMPLETE",
            "new_exact_distinct_authored_dgm_names": 39,
            "runtime_loadable_distinct_dgm_names": 35,
            "code_unreachable_alias_names": 4,
            "newly_recovered_secondary_scene_names": ["TUDUKU", "ANTEN"],
            "newly_recovered_runtime_loadable_dgm_names": sorted(LEGACY_MISSING_LOADABLE_DGMS),
            "visual_reachability_gate": "CLOSED",
            "new_longform_render_allowed_by_this_report_alone": False,
            "remaining_independent_gates": [
                "event_global_voice_se_subtitle_timing",
                "strict_no_bgm_sound_bus_partition",
                "duplicate_free_exhaustive_editorial_order",
            ],
        },
        "assertions": {
            "runtime_events": len(runtime),
            "runtime_parent_and_secondary_bindings": sum(map(len, EXPECTED_BINDINGS.values())),
            "exact_parent_z2ds": len(REQUIRED_Z2D_NAMES),
            "authored_movie_layer_occurrences": len(all_layers),
            "unique_authored_dgm_names": len(unique_refs),
            "unique_runtime_loadable_dgm_names": len(unique_loadable),
            "unreachable_alias_names": len(unreachable),
            "legacy_missing_loadable_secondary_names": len(LEGACY_MISSING_LOADABLE_DGMS),
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac1101ReachabilityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC1101_MOVIELAYER_REACHABILITY_AUTHORITY.json"
    csv_path = output_dir / "AC1101_MOVIELAYERS.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = [
        {"z2d_name": chunk["name"], **layer}
        for chunk in report["z2d_chunks"]
        for layer in chunk["movie_layers"]
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification_path.write_text(
        json.dumps(
            {
                "schema": "magireco-ac1101-movielayer-reachability-verification-v1",
                "status": "passed",
                "checks": report["assertions"],
                "decision": report["decision"],
                "outputs": [report_path.name, csv_path.name, readme_path.name],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        "# ac1101 MovieLayer reachability authority\n\n"
        "The bounded thirteen-event runtime capture closes seventeen exact parent "
        "Z2Ds and twenty event bindings. The legacy inventory omitted the TUDUKU "
        "and ANTEN secondary scenes and their three loadable DGM names. The exact "
        "compiled CRI table resolves 35 distinct loadable movie names; four authored "
        "additive aliases are code-unreachable same-interval twins. Audio/no-BGM and "
        "editorial ordering remain separate fail-closed gates. No media was changed.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d-manifest", required=True, type=Path)
    parser.add_argument("--filename-table-csv", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--legacy-timeline-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary,
        z2d_manifest_path=args.z2d_manifest,
        filename_table_csv=args.filename_table_csv,
        runtime_scene_motion_path=args.runtime_scene_motion,
        legacy_timeline_csv=args.legacy_timeline_csv,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS "
        f"events={report['assertions']['runtime_events']} "
        f"bindings={report['assertions']['runtime_parent_and_secondary_bindings']} "
        f"loadable_dgm={report['assertions']['unique_runtime_loadable_dgm_names']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
