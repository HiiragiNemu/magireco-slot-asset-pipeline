#!/usr/bin/env python3
"""Close ac1104 MovieLayer reachability and the legacy 43-video omission.

This consumer joins three code-level authorities: the exact Slot CRI filename
table, exact named Z2D chunks, and a bounded 17-event runtime scene-motion
capture.  It does not render media or infer reachability from pixels.
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


EVENTS = tuple(f"ac1104_{index:03d}" for index in range(1, 18))
REQUIRED_Z2D_NAMES = (
    "ac1104_lev_c001_c002_title_wht_S",
    "ac1104_1on_c003_c004",
    "ac1104_3on_c005",
    "ac1104_3on_c006",
    "ac1104_lev_c001_c002_title_red_S",
    "ac1104_lev_c001_c002_title_wht_L",
    "ac1104_lev_c001_c002_title_red_L",
    "ac1104_lev_c007",
    "ac1104_1on_c008",
    "ac1104_3on_c011_c012",
    "ac1104_3on_c013",
    "ac1104_3off_c016_c017_c018_lose",
    "ac1104_3off_c014_c015_win",
    "ac8040_shouri_EF_small",
    "ac1104_3off_c014_c015_win_rogo",
    "ac1104_lev_c009",
    "ac1104_1on_c010",
    "ac1104_lev_c019_c020_fukkatu_win",
    "ac1104_1on_c021_c022_c023_c024_c025_c026_fukkatu_win",
)
EXPECTED_PARENT_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "ac1104_001": {"ac1104_lev_c001_c002_title_wht_S": (0, 124)},
    "ac1104_002": {"ac1104_1on_c003_c004": (0, 144)},
    "ac1104_003": {"ac1104_3on_c005": (0, 416)},
    "ac1104_004": {"ac1104_3on_c006": (0, 349)},
    "ac1104_005": {"ac1104_lev_c001_c002_title_red_S": (0, 124)},
    "ac1104_006": {"ac1104_lev_c001_c002_title_wht_L": (0, 124)},
    "ac1104_007": {"ac1104_lev_c001_c002_title_red_L": (0, 124)},
    "ac1104_008": {"ac1104_lev_c007": (0, 89)},
    "ac1104_009": {"ac1104_1on_c008": (0, 39)},
    "ac1104_010": {"ac1104_3on_c011_c012": (0, 202)},
    "ac1104_011": {"ac1104_3on_c013": (0, 75)},
    "ac1104_012": {"ac1104_3off_c016_c017_c018_lose": (0, 191)},
    "ac1104_013": {
        "ac1104_3off_c014_c015_win": (0, 110),
        "ac8040_shouri_EF_small": (0, 259),
        "ac1104_3off_c014_c015_win_rogo": (90, 239),
    },
    "ac1104_014": {
        "ac1104_lev_c007": (0, 89),
        "ac1104_lev_c009": (0, 114),
    },
    "ac1104_015": {"ac1104_1on_c010": (0, 91)},
    "ac1104_016": {
        "ac1104_lev_c019_c020_fukkatu_win": (0, 143),
        "ac8040_shouri_EF_small": (0, 259),
    },
    "ac1104_017": {
        "ac1104_1on_c021_c022_c023_c024_c025_c026_fukkatu_win": (0, 406),
        "ac8040_shouri_EF_small": (0, 259),
        "ac1104_3off_c014_c015_win_rogo": (382, 531),
    },
}
UNREACHABLE_TO_LOADABLE_TWIN = {
    "ac8040_shouri_EF_small_add.dgm": "ac8040_shouri_EF_small.dgm",
    "ac8040_shouri_EF_small_add_LP.dgm": "ac8040_shouri_EF_small_LP.dgm",
    "ac1104_3off_c015_win_rogo_add.dgm": "ac1104_3off_c015_win_rogo.dgm",
    "ac1104_3off_c015_win_rogo_add_LP.dgm": "ac1104_3off_c015_win_rogo_LP.dgm",
}
MISSING_LEGACY_EVENT17_DGMS = {
    f"ac1104_1on_c0{index}_fukkatu_win" for index in range(21, 27)
} | {"ac1104_1on_c026_fukkatu_win_LP"}
EXPECTED_MODULE = (
    "split_config.arm64_v8a.apk",
    "/data/app/~~w196OEQ5FYrNgE6LHA9tnQ==/com.universal777.magireco-"
    "rHM8me-Z6EdQJaFV4cbnQA==/split_config.arm64_v8a.apk",
    80689936,
)


class Ac1104ReachabilityError(ValueError):
    pass


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def extract_runtime_parent_ranges(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if runtime.get("schema") != "magireco-ac1104-runtime-scene-motion-v1":
        raise Ac1104ReachabilityError("runtime scene-motion schema differs")
    if runtime.get("host_frida_version") != "17.16.4":
        raise Ac1104ReachabilityError("runtime Frida version differs")
    if runtime.get("protected_processes_unchanged") is not True:
        raise Ac1104ReachabilityError("protected emulator processes changed")
    if runtime.get("crash_buffer_unchanged") is not True:
        raise Ac1104ReachabilityError("crash buffer changed during capture")
    if runtime.get("process_restart_or_app_switch_performed") is not False:
        raise Ac1104ReachabilityError("capture restarted or switched an application")
    if runtime.get("module_rows") != [list(EXPECTED_MODULE)]:
        raise Ac1104ReachabilityError("runtime ARM64 module identity differs")
    events = runtime.get("events")
    if not isinstance(events, Mapping) or set(events) != set(EVENTS):
        raise Ac1104ReachabilityError("runtime event set differs")

    result: dict[str, Any] = {}
    for event, expected in EXPECTED_PARENT_RANGES.items():
        value = events[event]
        scenes = [row for row in value.get("scenes", []) if row.get("name") == event]
        if len(scenes) != 1:
            raise Ac1104ReachabilityError(f"primary runtime scene differs: {event}")
        cuts = [row for row in scenes[0].get("cuts", []) if row.get("cut_name") == event]
        if len(cuts) != 1:
            raise Ac1104ReachabilityError(f"primary runtime cut differs: {event}")
        cut = cuts[0]
        observed: dict[str, tuple[int, int]] = {}
        for node in _walk_nodes(cut.get("nodes", [])):
            name = str(node.get("name", ""))
            base = name[:-4] if name.endswith(".z2d") else name
            if base not in expected:
                continue
            motions = node.get("motions", [])
            if len(motions) != 1 or motions[0].get("is_z2d_motion") is not True:
                raise Ac1104ReachabilityError(f"Z2D motion binding differs: {event}/{base}")
            keys = motions[0].get("keys", [])
            if len(keys) != 1:
                raise Ac1104ReachabilityError(f"Z2D key count differs: {event}/{base}")
            values = keys[0].get("floats", [])
            if len(values) < 6:
                raise Ac1104ReachabilityError(f"Z2D key payload is short: {event}/{base}")
            starts, ends = values[0::2][:3], values[1::2][:3]
            if len(set(starts)) != 1 or len(set(ends)) != 1:
                raise Ac1104ReachabilityError(f"Z2D key triplets differ: {event}/{base}")
            start, end = starts[0], ends[0]
            if int(start) != start or int(end) != end or base in observed:
                raise Ac1104ReachabilityError(f"Z2D parent range differs: {event}/{base}")
            observed[base] = int(start), int(end)
        if observed != expected:
            raise Ac1104ReachabilityError(
                f"runtime parent ranges differ for {event}: {observed} != {expected}"
            )
        result[event] = {
            "cut_instance_offset_frames": int(cut["instance_offset_frames"]),
            "cut_start_frame": int(cut["cut_start_frame"]),
            "cut_end_frame": int(cut["cut_end_frame"]),
            "z2d_parent_ranges": {
                name: {"start_frame": start, "end_frame_inclusive": end}
                for name, (start, end) in observed.items()
            },
        }
    return result


def classify_unreachable_twins(layers: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_reference = {str(row["z2d_reference"]): row for row in layers}
    if set(UNREACHABLE_TO_LOADABLE_TWIN) - set(by_reference):
        raise Ac1104ReachabilityError("authored unreachable MovieLayer set is incomplete")
    result: list[dict[str, Any]] = []
    comparable = (
        "start_frame",
        "end_frame_inclusive",
        "position",
        "pivot",
        "layer_width",
        "layer_height",
    )
    for unreachable_name, twin_name in UNREACHABLE_TO_LOADABLE_TWIN.items():
        unreachable, twin = by_reference[unreachable_name], by_reference.get(twin_name)
        if twin is None:
            raise Ac1104ReachabilityError(f"loadable twin is absent: {twin_name}")
        if unreachable.get("compiled_table_present") is not False:
            raise Ac1104ReachabilityError(f"_add layer unexpectedly loadable: {unreachable_name}")
        if twin.get("compiled_table_present") is not True:
            raise Ac1104ReachabilityError(f"non-add twin unavailable: {twin_name}")
        if any(unreachable.get(key) != twin.get(key) for key in comparable):
            raise Ac1104ReachabilityError(f"unreachable/twin geometry differs: {unreachable_name}")
        result.append(
            {
                "unreachable_authored_layer": unreachable_name,
                "loadable_same_interval_twin": twin_name,
                "start_frame": unreachable["start_frame"],
                "end_frame_inclusive": unreachable["end_frame_inclusive"],
                "unreachable_blend_enum": unreachable["authored_blend_enum"],
                "loadable_twin_blend_enum": twin["authored_blend_enum"],
            }
        )
    return result


def read_legacy_inventory(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["event_name"].startswith("ac1104_")]
    events = {row["event_name"] for row in rows}
    z2ds = {row["z2d_name"] for row in rows}
    dgms = {row["dgm_name"] for row in rows}
    missing_parent = "ac1104_1on_c021_c022_c023_c024_c025_c026_fukkatu_win"
    if len(rows) != 67 or len(events) != 17 or len(z2ds) != 18 or len(dgms) != 43:
        raise Ac1104ReachabilityError("legacy ac1104 inventory dimensions differ")
    if missing_parent in z2ds or dgms & MISSING_LEGACY_EVENT17_DGMS:
        raise Ac1104ReachabilityError("legacy inventory unexpectedly contains event17 main media")
    return {
        "row_count": len(rows),
        "event_count": len(events),
        "unique_parent_z2d_count": len(z2ds),
        "unique_dgm_name_count": len(dgms),
        "missing_event17_parent_z2d": missing_parent,
        "missing_event17_dgm_names": sorted(MISSING_LEGACY_EVENT17_DGMS),
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
        raise Ac1104ReachabilityError("named Z2D extraction differs")
    chunks = manifest.get("chunks", [])
    if {row.get("name") for row in chunks} != set(REQUIRED_Z2D_NAMES):
        raise Ac1104ReachabilityError("named Z2D set differs")
    runtime_raw = json.loads(runtime_scene_motion_path.read_text(encoding="utf-8"))
    runtime_ranges = extract_runtime_parent_ranges(runtime_raw)
    compiled_names = read_filename_table(filename_table_csv)

    parsed_chunks: list[dict[str, Any]] = []
    all_layers: list[dict[str, Any]] = []
    headers: dict[str, dict[str, Any]] = {}
    for source in chunks:
        data = Path(source["output_path"]).read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{source['name']}.z2d" or header["frame_rate"] != 30.0:
            raise Ac1104ReachabilityError(f"Z2D header differs: {source['name']}")
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

    for mappings in EXPECTED_PARENT_RANGES.values():
        for z2d_name, (start, end) in mappings.items():
            if end - start + 1 != headers[z2d_name]["scene_frame_count"]:
                raise Ac1104ReachabilityError(f"runtime/Z2D frame count differs: {z2d_name}")
    twin_rows = classify_unreachable_twins(all_layers)
    unreachable = [row for row in all_layers if not row["compiled_table_present"]]
    if {row["z2d_reference"] for row in unreachable} != set(UNREACHABLE_TO_LOADABLE_TWIN):
        raise Ac1104ReachabilityError("unloadable authored MovieLayer set differs")
    unique_refs = {row["z2d_reference"] for row in all_layers}
    unique_loadable = {row["z2d_reference"] for row in all_layers if row["compiled_table_present"]}
    event17_refs = {
        row["z2d_reference"][:-4]
        for row in all_layers
        if row["parent_z2d"].startswith("ac1104_1on_c021_")
    }
    if len(all_layers) != 60 or len(unique_refs) != 50 or len(unique_loadable) != 46:
        raise Ac1104ReachabilityError("exact ac1104 MovieLayer dimensions differ")
    if event17_refs != MISSING_LEGACY_EVENT17_DGMS:
        raise Ac1104ReachabilityError("event17 exact DGM set differs")
    legacy = read_legacy_inventory(legacy_timeline_csv)

    return {
        "schema": "magireco-ac1104-movielayer-runtime-reachability-authority-v1",
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
        "runtime_parent_event_ranges": runtime_ranges,
        "z2d_chunks": parsed_chunks,
        "unreachable_authored_layers_and_loadable_twins": twin_rows,
        "legacy_inventory": legacy,
        "decision": {
            "legacy_43_video_inventory": "WITHDRAWN_INCOMPLETE",
            "new_exact_distinct_authored_dgm_names": 50,
            "runtime_loadable_distinct_dgm_names": 46,
            "code_unreachable_alias_names": 4,
            "newly_recovered_runtime_loadable_event17_names": sorted(event17_refs),
            "visual_reachability_gate": "CLOSED",
            "new_longform_render_allowed_by_this_report_alone": False,
            "remaining_independent_gates": [
                "event_global_voice_se_subtitle_timing",
                "strict_no_bgm_sound_bus_partition",
                "duplicate_free_exhaustive_editorial_order",
            ],
        },
        "assertions": {
            "runtime_events": len(runtime_ranges),
            "runtime_parent_bindings": sum(map(len, EXPECTED_PARENT_RANGES.values())),
            "exact_parent_z2ds": len(REQUIRED_Z2D_NAMES),
            "authored_movie_layer_occurrences": len(all_layers),
            "unique_authored_dgm_names": len(unique_refs),
            "unique_runtime_loadable_dgm_names": len(unique_loadable),
            "unreachable_alias_names": len(unreachable),
            "legacy_missing_loadable_event17_names": len(event17_refs),
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac1104ReachabilityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC1104_MOVIELAYER_REACHABILITY_AUTHORITY.json"
    csv_path = output_dir / "AC1104_MOVIELAYERS.csv"
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
                "schema": "magireco-ac1104-movielayer-reachability-verification-v1",
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
        "# ac1104 MovieLayer reachability authority\n\n"
        "The bounded 17-event runtime capture resolves 19 exact parent Z2Ds. The "
        "legacy table omitted the seven loadable ac1104_017 revival movie names. "
        "The exact compiled CRI table resolves 46 distinct movie names; four authored "
        "additive aliases are code-unreachable and each has a same-interval loadable "
        "twin. The old 43-name inventory is withdrawn. Audio/no-BGM and editorial "
        "order remain separate fail-closed gates. No media was changed.\n",
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
    checks = report["assertions"]
    print(
        "PASS "
        f"events={checks['runtime_events']} parent_z2d={checks['exact_parent_z2ds']} "
        f"distinct_authored={checks['unique_authored_dgm_names']} "
        f"loadable={checks['unique_runtime_loadable_dgm_names']} "
        f"legacy_missing_event17={checks['legacy_missing_loadable_event17_names']} "
        "visual_gate=CLOSED audio_order_gates=OPEN"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
