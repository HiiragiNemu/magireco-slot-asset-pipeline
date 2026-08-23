#!/usr/bin/env python3
"""Resolve exact ac7206 story and gameplay MovieLayer reachability.

The resolver joins the exact Slot ARM64 code tables, exact APK Z2D chunks,
and the bounded fifteen-event runtime scene capture.  It separates the fourteen
story/caption events from the ac7206_015 ``uwa`` gameplay overlay and records
source reuse instead of counting a reused DGM as a new video identity.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .extract_crivideo_filename_table_authority import CODE_AUTHORITY as CRI_CODE_AUTHORITY
    from .extract_named_z2d_chunks_from_apk import (
        NAME_COUNT,
        NAME_TABLE_OFFSET,
        read_native_relative_name_table,
    )
    from .extract_z2d_movie_layer_blend_authority import (
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import CODE_AUTHORITY as CRI_CODE_AUTHORITY  # type: ignore
    from extract_named_z2d_chunks_from_apk import (  # type: ignore
        NAME_COUNT,
        NAME_TABLE_OFFSET,
        read_native_relative_name_table,
    )
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )


EVENTS = tuple(f"ac7206_{index:03d}" for index in range(1, 16))
STORY_EVENTS = EVENTS[:14]
GAMEPLAY_EVENT = "ac7206_015"
EXPECTED_MODULE = {
    "name": "split_config.arm64_v8a.apk",
    "path": (
        "/data/app/~~w196OEQ5FYrNgE6LHA9tnQ==/com.universal777.magireco-"
        "rHM8me-Z6EdQJaFV4cbnQA==/split_config.arm64_v8a.apk"
    ),
    "size": 80689936,
}

# event -> (scene, cut, instance offset, parent Z2D, local start, local end, role)
EXPECTED_BINDINGS: dict[str, tuple[tuple[str, str, int, str, int, int, str], ...]] = {
    "ac7206_001": (
        ("ac7206_001", "ac7206_001", 0, "ac7206_arina_kaiga_lev_01", 0, 59, "story_visual"),
        ("ac7206_001", "ac7206_001", 0, "cap7206_paint_ari_001", 1, 30, "caption_audio_host"),
    ),
    "ac7206_002": (
        ("ac7206_002", "ac7206_002", 0, "ac7206_arina_kaiga_lev_02", 0, 204, "story_visual"),
        ("ac7206_002", "ac7206_002", 0, "cap7206_paint_ari_003", 10, 39, "caption_audio_host"),
    ),
    "ac7206_003": (
        ("ac7206_003", "ac7206_003", 0, "ac7206_arina_kaiga_3on_kok_S1", 0, 29, "story_visual"),
        ("ac7206_003", "ac7206_003", 0, "cap7206_paint_ari_002", 1, 30, "caption_audio_host"),
    ),
    "ac7206_004": (
        ("ac7206_004", "ac7206_004", 0, "ac7206_arina_kaiga_3on_kok_S2", 0, 29, "story_visual"),
        ("ac7206_004", "ac7206_004", 0, "cap7206_paint_ari_002", 1, 30, "caption_audio_host"),
    ),
    "ac7206_005": (
        ("ac7206_005", "ac7206_005", 0, "ac7206_arina_kaiga_3on_kok_M", 0, 29, "story_visual"),
        ("ac7206_005", "ac7206_005", 0, "cap7206_paint_ari_002", 1, 30, "caption_audio_host"),
    ),
    "ac7206_006": (
        ("ac7206_006", "ac7206_006", 0, "ac7206_arina_kaiga_3on_kok_L", 0, 29, "story_visual"),
        ("ac7206_006", "ac7206_006", 0, "cap7206_paint_ari_002", 1, 30, "caption_audio_host"),
    ),
    "ac7206_007": (
        ("ac7206_007", "ac7206_007", 0, "ac7206_arina_kaiga_3on_kok_kakutei", 0, 59, "story_visual"),
        ("ac7206_007", "ac7206_007", 0, "cap7206_paint_ari_002", 1, 30, "caption_audio_host"),
    ),
    "ac7206_008": (
        ("ac7206_008", "ac7206_008", 0, "ac7206_arina_kaiga_3on_kok_hat", 0, 29, "story_visual"),
        ("ac7206_008", "ac7206_008", 0, "cap7206_paint_ari_002", 1, 30, "caption_audio_host"),
    ),
    "ac7206_009": (
        ("ac7206_009", "ac7206_009", 0, "ac7206_arina_kaiga_3on_kok_S1", 0, 29, "story_visual"),
        ("ac7206_009", "ac7206_009", 0, "cap7206_paint_ari_004", 1, 30, "caption_audio_host"),
    ),
    "ac7206_010": (
        ("ac7206_010", "ac7206_010", 0, "ac7206_arina_kaiga_3on_kok_S2", 0, 29, "story_visual"),
        ("ac7206_010", "ac7206_010", 0, "cap7206_paint_ari_004", 1, 30, "caption_audio_host"),
    ),
    "ac7206_011": (
        ("ac7206_011", "ac7206_011", 0, "ac7206_arina_kaiga_3on_kok_M", 0, 29, "story_visual"),
        ("ac7206_011", "ac7206_011", 0, "cap7206_paint_ari_004", 1, 30, "caption_audio_host"),
    ),
    "ac7206_012": (
        ("ac7206_012", "ac7206_012", 0, "ac7206_arina_kaiga_3on_kok_L", 0, 29, "story_visual"),
        ("ac7206_012", "ac7206_012", 0, "cap7206_paint_ari_004", 1, 30, "caption_audio_host"),
    ),
    "ac7206_013": (
        ("ac7206_013", "ac7206_013", 0, "ac7206_arina_kaiga_3on_kok_kakutei", 0, 59, "story_visual"),
        ("ac7206_013", "ac7206_013", 0, "cap7206_paint_ari_004", 1, 30, "caption_audio_host"),
    ),
    "ac7206_014": (
        ("ac7206_014", "ac7206_014", 0, "ac7206_arina_kaiga_3on_kok_hat", 0, 29, "story_visual"),
        ("ac7206_014", "ac7206_014", 0, "cap7206_paint_ari_004", 1, 30, "caption_audio_host"),
    ),
    "ac7206_015": (
        ("uwa", "ac8050_004", 0, "ac8050_ef_bg_uwa_zen_01", 0, 239, "gameplay_effect"),
        ("uwa", "ac8050_004", 0, "ac8050_uwa_impact_ZEN_ef", 0, 239, "gameplay_effect"),
    ),
}
EXPECTED_CUT_RANGES = {
    **{event: ((event, event, 0, 0, 99),) for event in STORY_EVENTS},
    GAMEPLAY_EVENT: (
        (GAMEPLAY_EVENT, GAMEPLAY_EVENT, 0, 0, 99),
        ("uwa", "ac8050_004", 0, 0, 239),
    ),
}
LOGICAL_SELECTOR_NAMES = (
    "ac8050_null_uwa_suji_keta",
    "ac8050_tx_count_uwa_suji_1000",
    "ac8050_tx_count_uwa_suji_0100",
    "ac8050_tx_count_uwa_suji_0010",
    "ac8050_tx_count_uwa_suji_0001",
)
REQUIRED_Z2D_NAMES = tuple(
    dict.fromkeys(row[3] for bindings in EXPECTED_BINDINGS.values() for row in bindings)
)


class Ac7206ReachabilityError(ValueError):
    pass


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def _z2d_range(node: Mapping[str, Any], event: str, name: str) -> tuple[int, int]:
    motions = [row for row in node.get("motions", []) if row.get("is_z2d_motion") is True]
    if len(motions) != 1 or len(motions[0].get("keys", [])) != 1:
        raise Ac7206ReachabilityError(f"Z2D motion binding differs: {event}/{name}")
    values = motions[0]["keys"][0].get("floats", [])
    if len(values) < 6:
        raise Ac7206ReachabilityError(f"Z2D key payload is short: {event}/{name}")
    starts, ends = values[0::2][:3], values[1::2][:3]
    if len(set(starts)) != 1 or len(set(ends)) != 1:
        raise Ac7206ReachabilityError(f"Z2D key triplets differ: {event}/{name}")
    start, end = starts[0], ends[0]
    if int(start) != start or int(end) != end:
        raise Ac7206ReachabilityError(f"Z2D parent range is fractional: {event}/{name}")
    return int(start), int(end)


def _scene_cut(event: str, value: Mapping[str, Any], scene_name: str, cut_name: str) -> Mapping[str, Any]:
    scenes = [row for row in value.get("scenes", []) if row.get("name") == scene_name]
    if len(scenes) != 1:
        raise Ac7206ReachabilityError(f"runtime scene differs: {event}/{scene_name}")
    cuts = [row for row in scenes[0].get("cuts", []) if row.get("cut_name") == cut_name]
    if len(cuts) != 1:
        raise Ac7206ReachabilityError(f"runtime cut differs: {event}/{cut_name}")
    return cuts[0]


def extract_runtime_bindings(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if runtime.get("schema") != "magireco-ac7206-runtime-scene-motion-v1":
        raise Ac7206ReachabilityError("runtime scene-motion schema differs")
    if runtime.get("host_frida_version") != "17.16.4":
        raise Ac7206ReachabilityError("runtime Frida version differs")
    if runtime.get("protected_processes_unchanged") is not True:
        raise Ac7206ReachabilityError("protected emulator processes changed")
    if runtime.get("crash_tail_empty") is not True:
        raise Ac7206ReachabilityError("runtime crash tail was not empty")
    events = runtime.get("events")
    if not isinstance(events, Mapping) or set(events) != set(EVENTS):
        raise Ac7206ReachabilityError("runtime event set differs")
    if set(runtime.get("requested_events", {})) != set(EVENTS):
        raise Ac7206ReachabilityError("requested runtime event set differs")

    result: dict[str, Any] = {}
    for event in EVENTS:
        value = events[event]
        module = value.get("module", {})
        if any(module.get(key) != expected for key, expected in EXPECTED_MODULE.items()):
            raise Ac7206ReachabilityError(f"runtime ARM64 module differs: {event}")
        if value.get("event_code") != runtime["requested_events"][event]:
            raise Ac7206ReachabilityError(f"runtime event code differs: {event}")
        expected_cuts = EXPECTED_CUT_RANGES[event]
        if {str(row.get("name")) for row in value.get("scenes", [])} != {row[0] for row in expected_cuts}:
            raise Ac7206ReachabilityError(f"runtime scene set differs: {event}")
        for scene_name, cut_name, offset, cut_start, cut_end in expected_cuts:
            cut = _scene_cut(event, value, scene_name, cut_name)
            observed = (
                int(cut.get("instance_offset_frames", -1)),
                int(cut.get("cut_start_frame", -1)),
                int(cut.get("cut_end_frame", -1)),
            )
            if observed != (offset, cut_start, cut_end):
                raise Ac7206ReachabilityError(f"runtime cut interval differs: {event}/{cut_name}")

        event_rows: list[dict[str, Any]] = []
        for scene_name, cut_name, offset, name, expected_start, expected_end, role in EXPECTED_BINDINGS[event]:
            cut = _scene_cut(event, value, scene_name, cut_name)
            matching = []
            for node in _walk_nodes(cut.get("nodes", [])):
                observed_name = str(node.get("name", ""))
                base = observed_name[:-4] if observed_name.endswith(".z2d") else observed_name
                if base == name:
                    matching.append(node)
            if len(matching) != 1:
                raise Ac7206ReachabilityError(f"runtime parent Z2D differs: {event}/{name}")
            start, end = _z2d_range(matching[0], event, name)
            if (start, end) != (expected_start, expected_end):
                raise Ac7206ReachabilityError(f"runtime parent range differs: {event}/{name}")
            event_rows.append(
                {
                    "scene_name": scene_name,
                    "cut_name": cut_name,
                    "cut_instance_offset_frames": offset,
                    "parent_z2d": name,
                    "role": role,
                    "local_start_frame": start,
                    "local_end_frame_inclusive": end,
                    "event_global_start_frame": offset + start,
                    "event_global_end_frame_inclusive": offset + end,
                }
            )
        result[event] = event_rows

    uwa_cut = _scene_cut(GAMEPLAY_EVENT, events[GAMEPLAY_EVENT], "uwa", "ac8050_004")
    logical = []
    for node in _walk_nodes(uwa_cut.get("nodes", [])):
        name = str(node.get("name", ""))
        if name in LOGICAL_SELECTOR_NAMES:
            start, end = _z2d_range(node, GAMEPLAY_EVENT, name)
            logical.append({"runtime_logical_name": name, "start_frame": start, "end_frame_inclusive": end})
    if {row["runtime_logical_name"] for row in logical} != set(LOGICAL_SELECTOR_NAMES):
        raise Ac7206ReachabilityError("runtime logical selector set differs")
    if any((row["start_frame"], row["end_frame_inclusive"]) != (0, 239) for row in logical):
        raise Ac7206ReachabilityError("runtime logical selector interval differs")
    return {"events": result, "logical_selector_nodes": sorted(logical, key=lambda row: row["runtime_logical_name"])}


def resolve_logical_selector_backing(native_names: Iterable[str]) -> list[dict[str, Any]]:
    names = set(native_names)
    expected_null = {
        f"ac8050_null_uwa_suji_keta_{place}{suffix}"
        for place in ("0001", "0010", "0100", "1000")
        for suffix in ("", "_sub")
    }
    result = []
    for logical in LOGICAL_SELECTOR_NAMES:
        if logical == "ac8050_null_uwa_suji_keta":
            backing = expected_null
        else:
            place = logical.rsplit("_", 1)[-1]
            backing = {f"ac8050_tx_count_uwa_{place}_suji_{digit:02d}" for digit in range(10)}
        if not backing <= names:
            raise Ac7206ReachabilityError(f"logical selector physical backing differs: {logical}")
        result.append(
            {
                "runtime_logical_name": logical,
                "classification": "parameterized_runtime_alias_not_a_physical_z2d_name",
                "physical_backing_count": len(backing),
                "physical_backing_names": sorted(backing),
            }
        )
    union = set().union(*(set(row["physical_backing_names"]) for row in result))
    if len(union) != 48:
        raise Ac7206ReachabilityError("logical selector backing union differs")
    return result


def read_legacy_audit(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    route = value.get("route_universe", {})
    native = value.get("native_source_universe", {})
    legacy = value.get("legacy_longform", {})
    decision = value.get("decision", {})
    observed = (
        value.get("schema"), value.get("status"), value.get("family"),
        route.get("kind"), route.get("route_count"), route.get("unique_event_count"),
        native.get("occurrence_count"), native.get("unique_source_identity_count"),
        legacy.get("event_count"), legacy.get("native_source_occurrence_count"),
        legacy.get("unique_native_source_identity_count"), legacy.get("duplicate_surplus_occurrence_count"),
        legacy.get("missing_required_unique_source_identity_count"), decision.get("legacy_longform_final_authority"),
    )
    expected = (
        "magireco-exhaustive-family-source-identity-audit-v1", "PASS_RENDER_PAUSED", "ac7206",
        200, 40, 15, 19, 12, 19, 35, 10, 25, 2, False,
    )
    if observed != expected:
        raise Ac7206ReachabilityError("legacy ac7206 audit dimensions differ")
    return {
        "route_count": 40,
        "unique_event_count": 15,
        "known_native_source_occurrences": 19,
        "known_unique_native_source_identities": 12,
        "legacy_fragment_event_occurrences": 19,
        "legacy_fragment_native_source_occurrences": 35,
        "legacy_fragment_unique_native_source_identities": 10,
        "legacy_fragment_duplicate_surplus_occurrences": 25,
        "legacy_longform_final_authority": False,
        "legacy_missing_events": [
            "ac7206_001", "ac7206_003", "ac7206_004", "ac7206_005",
            "ac7206_006", "ac7206_007", "ac7206_008", "ac7206_015",
        ],
    }


def build_report(
    *, binary: Path, z2d_manifest_path: Path, filename_table_csv: Path,
    runtime_scene_motion_path: Path, legacy_audit_path: Path,
) -> dict[str, Any]:
    build_id, blend_state_table, blend_table_offset = validate_exact_binary(binary)
    manifest = json.loads(z2d_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1" or manifest.get("status") != "passed":
        raise Ac7206ReachabilityError("named Z2D extraction differs")
    chunks = manifest.get("chunks", [])
    if {row.get("name") for row in chunks} != set(REQUIRED_Z2D_NAMES):
        raise Ac7206ReachabilityError("named Z2D set differs")
    if manifest.get("binary", {}).get("gnu_build_id") != build_id:
        raise Ac7206ReachabilityError("named Z2D binary build differs")

    runtime = extract_runtime_bindings(json.loads(runtime_scene_motion_path.read_text(encoding="utf-8")))
    compiled_names = read_filename_table(filename_table_csv)
    native_names = read_native_relative_name_table(binary, NAME_TABLE_OFFSET, NAME_COUNT)
    selector_backing = resolve_logical_selector_backing(native_names)
    parsed_chunks: list[dict[str, Any]] = []
    all_layers: list[dict[str, Any]] = []
    headers: dict[str, dict[str, Any]] = {}
    for source in chunks:
        data = Path(source["output_path"]).read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{source['name']}.z2d" or header["frame_rate"] != 30.0:
            raise Ac7206ReachabilityError(f"Z2D header differs: {source['name']}")
        headers[source["name"]] = header
        layers = []
        for reference in source.get("dgm_references", []):
            layer = parse_movie_layer(data, reference, blend_state_table)
            table_index = compiled_names.get(reference[:-4])
            layer.update({
                "parent_z2d": source["name"],
                "content_class": "gameplay_effect" if source["name"].startswith("ac8050_") else "story_visual",
                "compiled_table_present": table_index is not None,
                "compiled_table_index": table_index,
            })
            layers.append(layer)
            all_layers.append(layer)
        parsed_chunks.append({"name": source["name"], "header": header, "movie_layers": layers})

    for bindings in EXPECTED_BINDINGS.values():
        for _, _, _, name, start, end, _ in bindings:
            if end - start + 1 != headers[name]["scene_frame_count"]:
                raise Ac7206ReachabilityError(f"runtime/Z2D frame count differs: {name}")
    if any(row["compiled_table_present"] is not True for row in all_layers):
        raise Ac7206ReachabilityError("authored ac7206/ac8050 MovieLayer is absent from compiled table")
    story_layers = [row for row in all_layers if row["content_class"] == "story_visual"]
    gameplay_layers = [row for row in all_layers if row["content_class"] == "gameplay_effect"]
    if (len(all_layers), len(story_layers), len(gameplay_layers)) != (15, 12, 3):
        raise Ac7206ReachabilityError("exact ac7206 MovieLayer dimensions differ")
    if len({row["z2d_reference"] for row in all_layers}) != 15:
        raise Ac7206ReachabilityError("exact ac7206 MovieLayer identity count differs")

    visual_groups: dict[str, list[str]] = {}
    for event, rows in runtime["events"].items():
        for row in rows:
            if row["role"] == "story_visual":
                visual_groups.setdefault(row["parent_z2d"], []).append(event)
    if len(visual_groups) != 8 or sum(len(events) for events in visual_groups.values()) != 14:
        raise Ac7206ReachabilityError("story visual source reuse dimensions differ")
    source_reuse = [
        {"parent_z2d": name, "events": events, "event_occurrence_count": len(events),
         "same_visual_source_reused": len(events) > 1}
        for name, events in sorted(visual_groups.items())
    ]
    legacy = read_legacy_audit(legacy_audit_path)
    return {
        "schema": "magireco-ac7206-movielayer-runtime-reachability-authority-v1",
        "status": "passed",
        "family": "ac7206",
        "binary": {"path": str(binary.resolve()), "size": binary.stat().st_size,
                   "gnu_build_id": build_id, "identity_from_named_z2d_manifest": manifest["binary"]},
        "inputs": {
            "named_z2d_manifest": str(z2d_manifest_path.resolve()),
            "compiled_crivideo_filename_table": str(filename_table_csv.resolve()),
            "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
            "legacy_audit": str(legacy_audit_path.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in (*CRI_CODE_AUTHORITY, *Z2D_CODE_AUTHORITY)
        ],
        "blend_state_table": {"file_offset_hex": f"0x{blend_table_offset:x}",
                              "renderer_states_by_blend_enum_1_to_30": blend_state_table},
        "runtime_event_bindings": runtime,
        "z2d_chunks": parsed_chunks,
        "story_visual_source_reuse": source_reuse,
        "logical_gameplay_selector_aliases": selector_backing,
        "legacy_audit": legacy,
        "decision": {
            "legacy_fragment_collection": "WITHDRAWN_INCOMPLETE_AND_DUPLICATE_HEAVY",
            "route_universe_count": 40,
            "event_universe_count": 15,
            "story_event_count": 14,
            "gameplay_effect_event_count": 1,
            "distinct_story_parent_z2ds": 8,
            "distinct_story_authored_dgm_names": 12,
            "distinct_gameplay_effect_dgm_names": 3,
            "runtime_logical_selector_nodes": 5,
            "exact_physical_selector_backing_z2ds": 48,
            "visual_reachability_gate": "CLOSED",
            "ac7206_015_classification": "gameplay_effect_component_not_clean_story",
            "new_longform_render_allowed_by_this_report_alone": False,
            "remaining_independent_gates": [
                "event_global_voice_se_subtitle_timing_for_all_story_events",
                "strict_no_bgm_sound_bus_partition",
                "duplicate_free_exhaustive_editorial_order",
                "ac7206_015_gameplay_effect_composition_and_audio",
            ],
        },
        "assertions": {
            "runtime_events": 15,
            "runtime_story_events": 14,
            "runtime_gameplay_effect_events": 1,
            "runtime_parent_bindings": sum(map(len, EXPECTED_BINDINGS.values())),
            "runtime_logical_selector_nodes": len(LOGICAL_SELECTOR_NAMES),
            "exact_parent_z2ds": len(REQUIRED_Z2D_NAMES),
            "authored_movie_layer_occurrences": len(all_layers),
            "unique_runtime_loadable_dgm_names": len({row["z2d_reference"] for row in all_layers}),
            "story_dgm_names": len(story_layers),
            "gameplay_effect_dgm_names": len(gameplay_layers),
            "exact_physical_selector_backing_z2ds": 48,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac7206ReachabilityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC7206_MOVIELAYER_REACHABILITY_AUTHORITY.json"
    csv_path = output_dir / "AC7206_MOVIELAYERS.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = [{"z2d_name": chunk["name"], **layer}
            for chunk in report["z2d_chunks"] for layer in chunk["movie_layers"]]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification_path.write_text(json.dumps({
        "schema": "magireco-ac7206-movielayer-reachability-verification-v1",
        "status": "passed", "checks": report["assertions"], "decision": report["decision"],
        "outputs": [report_path.name, csv_path.name, readme_path.name],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        "# ac7206 MovieLayer reachability authority\n\n"
        "The bounded runtime capture closes all fifteen event containers. Events "
        "001-014 bind fourteen story presentations to eight distinct visual parent "
        "Z2Ds and twelve loadable DGM names. Event 015 is a separate `uwa` gameplay "
        "overlay with three loadable DGM names and five parameterized logical selector "
        "nodes backed by 48 exact APK Z2Ds. The old fragment collection is incomplete "
        "and duplicate-heavy. Audio/no-BGM and editorial ordering remain separate "
        "fail-closed gates. No source media was changed.\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d-manifest", required=True, type=Path)
    parser.add_argument("--filename-table-csv", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--legacy-audit", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(binary=args.binary, z2d_manifest_path=args.z2d_manifest,
                          filename_table_csv=args.filename_table_csv,
                          runtime_scene_motion_path=args.runtime_scene_motion,
                          legacy_audit_path=args.legacy_audit)
    write_outputs(report, args.output_dir)
    print("PASS "
          f"events={report['assertions']['runtime_events']} "
          f"story_dgm={report['assertions']['story_dgm_names']} "
          f"gameplay_dgm={report['assertions']['gameplay_effect_dgm_names']} "
          f"selector_backing={report['assertions']['exact_physical_selector_backing_z2ds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
