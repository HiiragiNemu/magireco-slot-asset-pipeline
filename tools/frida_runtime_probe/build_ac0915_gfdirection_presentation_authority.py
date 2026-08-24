#!/usr/bin/env python3
"""Build event-global GFDirection presentation authority for ``ac0915``.

This builder joins four bounded evidence classes without visual inference:

* the byte-exact ``ac0915`` GFDirection scene group (Type-2/Type-3 records),
* the byte-exact GDP layer table,
* a single-session runtime scene graph for all 21 events, and
* the exact APK-backed parent-Z2D inventory.

Unlike a serial playlist renderer, ``ac0915`` has five events whose secondary
GFDirection presentations start at event-global frame zero and run in parallel
with the event's primary scene.  The event extent is therefore the maximum of
the parallel Type-2 presentation extents.  This module preserves that fact and
resolves owning GDP layers by their exact two-word hash, because the runtime
capture's Japanese layer labels are mojibake.

The resulting checkpoint is deliberately projection-pending.  It proves the
event-global scene/node graph; a downstream authority decides how the virtual
1280x1024 render buffer is cropped and scaled to native 416x232.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .extract_gfdirection_z2d_resource_bindings import ParseError, parse_node
    from .extract_jm_dgi_glyph_catalog import sha256_bytes
except ImportError:  # pragma: no cover - direct script execution
    from extract_gfdirection_z2d_resource_bindings import ParseError, parse_node  # type: ignore
    from extract_jm_dgi_glyph_catalog import sha256_bytes  # type: ignore


SLOT_BINARY_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
SLOT_BINARY_BUILD_ID = "a1aceffc5be1f2380cdcd9af4d8f9764ac2bf40b"
EVENT_IDS = tuple(f"ac0915_{index:03d}" for index in range(1, 22))
EXPECTED_EVENT_FRAMES = {
    "ac0915_001": 232,
    "ac0915_002": 179,
    "ac0915_003": 299,
    "ac0915_004": 180,
    "ac0915_005": 150,
    "ac0915_006": 178,
    "ac0915_007": 240,
    "ac0915_008": 299,
    "ac0915_009": 240,
    "ac0915_010": 84,
    "ac0915_011": 100,
    "ac0915_012": 498,
    "ac0915_013": 299,
    "ac0915_014": 260,
    "ac0915_015": 150,
    "ac0915_016": 240,
    "ac0915_017": 84,
    "ac0915_018": 260,
    "ac0915_019": 150,
    "ac0915_020": 260,
    "ac0915_021": 240,
}
EXPECTED_COUNTS = {
    "event_count": 21,
    "scene_instance_count": 26,
    "cut_count": 26,
    "z2d_node_occurrence_count": 48,
    "unique_z2d_node_count": 39,
    "archive_backed_z2d_occurrence_count": 43,
    "unique_archive_backed_z2d_count": 34,
    "runtime_symbolic_z2d_occurrence_count": 5,
    "unique_runtime_symbolic_z2d_count": 5,
}
EXPECTED_PARAMETER_IDS = (9, 11, 14, 16, 19, 21)

CODE_AUTHORITY = (
    (
        "0x437ecd8",
        "zg::C_Scene::fnInitScene",
        "loads the exact GDP and requested GFDirection GDB scene group",
    ),
    (
        "0x42c054c",
        "zg::CGFDirectionPlayer::LoadGDB",
        "loads the Type-2 presentation and Type-3 cut records parsed here",
    ),
    (
        "0x42c428c",
        "zg::CGFDirectionPlayer::SetScene",
        "selects the named Type-2 presentation used by each runtime scene instance",
    ),
    (
        "0x42c8424",
        "zg::CGFDirectionPlayer::AddCut",
        "adds a referenced Type-3 cut at its authored presentation time",
    ),
    (
        "0x42c84d0",
        "zg::CGFDirectionPlayer::AddBlank",
        "advances a presentation through authored blank time without inventing media",
    ),
    (
        "0x42c907c",
        "zg::CGFDirectionPlayer::AdvanceTime",
        "advances every active presentation from the shared event clock",
    ),
    (
        "0x42c91fc",
        "zg::CGFDirectionPlayer::SetTime",
        "sets presentation time used for event-global seek and deterministic replay",
    ),
    (
        "0x42b0374",
        "zg::CGFDirectionNodeLayer::Load",
        "defines the packed node hierarchy and parameter/motion counts",
    ),
    (
        "0x42b0060",
        "zg::CGFDirectionNode::AdvanceTime",
        "updates node parameters and Z2D motion on the owning presentation clock",
    ),
    (
        "0x42b0140",
        "zg::CGFDirectionNode::SetTime",
        "seeks node parameters and Z2D motion on the owning presentation clock",
    ),
    (
        "0x42b7824",
        "zg::CGFDirectionNodeSingleParameter<float>::Load",
        "loads keyed floats as time(float), curve type(int), value(float)",
    ),
    (
        "0x42b74b4",
        "zg::CGFDirectionNodeSingleParameter<float>::Calc",
        "uses key time, curve type, and value for exact runtime interpolation",
    ),
    (
        "0x429cc40",
        "zg::CGFDirectionLayer::GetViewport",
        "resolves the owning layer viewport from the exact GDP",
    ),
    (
        "0x42a71bc",
        "zg::CGFDirectionNodeLayer::SetParameterZ2D",
        "applies the parsed transform and opacity relative to the owning GDP layer",
    ),
)


class PresentationAuthorityError(ValueError):
    """An input differs from the bounded ``ac0915`` authority contract."""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_binary(report: dict[str, Any], label: str) -> None:
    candidates = (
        report.get("binary", {}).get("inherited_sha256"),
        report.get("exact_binary", {}).get("inherited_sha256"),
    )
    inherited = next((value for value in candidates if value is not None), None)
    if inherited != SLOT_BINARY_SHA256:
        raise PresentationAuthorityError(
            f"{label} exact Slot binary differs: {inherited!r}"
        )


def _normalise_z2d_name(name: str) -> str:
    return name[:-4] if name.casefold().endswith(".z2d") else name


def _compound_values(parameter: dict[str, Any]) -> list[float]:
    children = parameter.get("components", [])
    if [int(child["parameter_id"]) for child in children] != [1, 2]:
        raise PresentationAuthorityError(
            f"parameter {parameter['parameter_id']} compound components differ"
        )
    if any(child.get("key_count") for child in children):
        raise PresentationAuthorityError(
            f"parameter {parameter['parameter_id']} has unsupported keyed components"
        )
    return [float(child["static_value"]) for child in children]


def _float_parameter(
    parameter: dict[str, Any], *, instance_offset_frames: int
) -> dict[str, Any]:
    key_count = int(parameter.get("key_count", 0))
    if not key_count:
        return {"mode": "static", "value": float(parameter["static_value"])}
    keys = []
    for key in parameter["keys"]:
        curve_type = int(key["curve_type"])
        if curve_type not in (0, 1, 2):
            raise PresentationAuthorityError(
                f"unknown keyed-float curve type {curve_type}"
            )
        local_time = float(key["time"])
        keys.append(
            {
                "local_time_frames": local_time,
                "event_global_time_frames": instance_offset_frames + local_time,
                "curve_type": curve_type,
                "value": float(key["value"]),
            }
        )
    if [row["local_time_frames"] for row in keys] != sorted(
        row["local_time_frames"] for row in keys
    ):
        raise PresentationAuthorityError("keyed-float times are not monotonic")
    return {"mode": "keyed", "keys": keys}


def _node_transform(
    node: dict[str, Any], *, instance_offset_frames: int
) -> dict[str, Any]:
    rows = {int(row["parameter_id"]): row for row in node["parameters"]}
    if tuple(rows) != EXPECTED_PARAMETER_IDS:
        raise PresentationAuthorityError(
            f"{node['name']} parameter ids differ: {tuple(rows)}"
        )
    if int(node["node_type"]) != 20 or int(node["motion_count"]) != 1:
        raise PresentationAuthorityError(
            f"{node['name']} is not one exact single-motion Z2D node"
        )
    if int(node["resource_index"]) != -1:
        raise PresentationAuthorityError(
            f"{node['name']} has unexpected direct resource index"
        )
    enabled = rows[9]
    if enabled.get("key_count"):
        raise PresentationAuthorityError(f"{node['name']} has keyed enabled state")
    return {
        "enabled": int(enabled["static_value"]),
        "translation": _compound_values(rows[11]),
        "rotation_degrees": _float_parameter(
            rows[14], instance_offset_frames=instance_offset_frames
        ),
        "scale": _compound_values(rows[16]),
        "opacity": _float_parameter(
            rows[19], instance_offset_frames=instance_offset_frames
        ),
        "anchor_offset": _compound_values(rows[21]),
    }


def _walk_nodes(
    node: dict[str, Any], *, owning_layer: dict[str, Any] | None = None
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    if int(node.get("type", -1)) == 38:
        owning_layer = node
    if int(node.get("type", -1)) == 20:
        if owning_layer is None:
            raise PresentationAuthorityError(
                f"Z2D node {node.get('name')!r} has no owning Type-38 layer"
            )
        yield owning_layer, node
    for child in node.get("children", []):
        yield from _walk_nodes(child, owning_layer=owning_layer)


def _runtime_event_extent(event: dict[str, Any]) -> int:
    ends: list[int] = []
    for scene in event.get("scenes", []):
        for cut in scene.get("cuts", []):
            ends.append(
                int(cut["instance_offset_frames"])
                + int(cut["cut_end_frame"])
                + 1
            )
    if not ends:
        raise PresentationAuthorityError("runtime event has no cuts")
    return max(ends)


def _motion_rows(
    *,
    runtime_node: dict[str, Any],
    cut_name: str,
    instance_offset: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    motions = runtime_node.get("motions", [])
    if len(motions) != 1 or not motions[0].get("is_z2d_motion"):
        raise PresentationAuthorityError(
            f"{cut_name}/{runtime_node.get('name')} runtime motion is not one Z2D motion"
        )
    for key in motions[0].get("keys", []):
        floats = list(key.get("floats", []))
        if len(floats) < 2:
            raise PresentationAuthorityError(
                f"{cut_name}/{runtime_node.get('name')} runtime motion key is short"
            )
        local_start = int(floats[0])
        local_end = int(floats[1])
        if local_start < 0 or local_end < local_start:
            raise PresentationAuthorityError(
                f"{cut_name}/{runtime_node.get('name')} invalid motion range"
            )
        rows.append(
            {
                "key_index": int(key["index"]),
                "raw_floats": floats,
                "raw_flags": list(key.get("flags", [])),
                "local_start_frame": local_start,
                "local_end_frame_inclusive": local_end,
                "event_global_start_frame": instance_offset + local_start,
                "event_global_end_frame_inclusive": instance_offset + local_end,
            }
        )
    if not rows:
        raise PresentationAuthorityError(
            f"{cut_name}/{runtime_node.get('name')} runtime Z2D motion has no keys"
        )
    return rows


def _validate_expected_counts(
    actual: Mapping[str, int], expected: Mapping[str, int]
) -> None:
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            raise PresentationAuthorityError(
                f"{key} differs: expected={expected_value} actual={actual_value}"
            )


def build_authority(
    *,
    scene_group_path: Path,
    gdp_path: Path,
    runtime_scene_path: Path,
    type3_records_dir: Path,
    parent_z2d_authority_path: Path,
    expected_event_ids: Sequence[str] = EVENT_IDS,
    expected_event_frames: Mapping[str, int] = EXPECTED_EVENT_FRAMES,
    expected_counts: Mapping[str, int] = EXPECTED_COUNTS,
    expected_group_name: str = "ac0915",
    expected_group_index: int = 40,
) -> dict[str, Any]:
    scene_report = _load_json(scene_group_path)
    gdp_report = _load_json(gdp_path)
    runtime_report = _load_json(runtime_scene_path)
    parent_report = _load_json(parent_z2d_authority_path)
    _validate_binary(scene_report, "scene-group authority")
    _validate_binary(gdp_report, "GDP authority")
    _validate_binary(parent_report, "parent-Z2D authority")
    if scene_report.get("status") != "passed_code_exact":
        raise PresentationAuthorityError(
            "scene-group authority is not passed_code_exact"
        )
    if gdp_report.get("status") != "passed_code_exact":
        raise PresentationAuthorityError("GDP authority is not passed_code_exact")
    if parent_report.get("status") != "PASSED":
        raise PresentationAuthorityError("parent-Z2D authority is not PASSED")

    group = scene_report["group"]
    if (
        group.get("name") != expected_group_name
        or int(group.get("compiled_index", -1)) != expected_group_index
    ):
        raise PresentationAuthorityError(
            f"scene-group is not exact {expected_group_name} index {expected_group_index}"
        )
    type2_by_name = {row["name"]: row for row in group["type2_presentations"]}
    type3_by_name = {row["name"]: row for row in group["type3_records"]}
    layers_by_hash: dict[tuple[int, int], dict[str, Any]] = {}
    for layer in gdp_report["project"]["layers"]:
        key = tuple(int(value) for value in layer["hash_words"])
        if key in layers_by_hash:
            raise PresentationAuthorityError(f"duplicate GDP layer hash {key}")
        layers_by_hash[key] = layer

    runtime_events = runtime_report.get("events", {})
    if tuple(sorted(runtime_events)) != tuple(sorted(expected_event_ids)):
        raise PresentationAuthorityError(
            f"runtime event set differs: {sorted(runtime_events)}"
        )
    if set(expected_event_frames) != set(expected_event_ids):
        raise PresentationAuthorityError("expected event-frame map differs from event set")

    archive_names = set(parent_report.get("exact_archive_z2d_names", []))
    symbolic_names = set(parent_report.get("runtime_only_type20_names", []))
    if archive_names & symbolic_names:
        raise PresentationAuthorityError("archive and symbolic Z2D sets overlap")

    events: list[dict[str, Any]] = []
    flattened: list[dict[str, Any]] = []
    keyed_parameter_occurrences = 0
    scene_count = 0
    cut_count = 0
    for event_id in expected_event_ids:
        event = runtime_events[event_id]
        runtime_extent = _runtime_event_extent(event)
        if runtime_extent != int(expected_event_frames[event_id]):
            raise PresentationAuthorityError(
                f"{event_id} runtime extent differs: {runtime_extent}"
            )
        event_scenes: list[dict[str, Any]] = []
        for scene_order, scene in enumerate(event.get("scenes", [])):
            scene_count += 1
            scene_name = str(scene["name"])
            type2 = type2_by_name.get(scene_name)
            if type2 is None:
                raise PresentationAuthorityError(
                    f"{event_id} runtime scene {scene_name} lacks Type-2 record"
                )
            expected_refs = {
                (
                    row["target_name"],
                    int(row["instance_offset_frames"]),
                    int(row["target_frame_count"]),
                )
                for row in type2["scene_references"]
            }
            actual_refs: set[tuple[str, int, int]] = set()
            scene_cuts: list[dict[str, Any]] = []
            for cut in scene.get("cuts", []):
                cut_count += 1
                cut_name = str(cut["cut_name"])
                instance_offset = int(cut["instance_offset_frames"])
                cut_frames = (
                    int(cut["cut_end_frame"])
                    - int(cut["cut_start_frame"])
                    + 1
                )
                actual_refs.add((cut_name, instance_offset, cut_frames))
                type3 = type3_by_name.get(cut_name)
                if type3 is None:
                    raise PresentationAuthorityError(
                        f"{event_id}/{scene_name} cut {cut_name} lacks Type-3 record"
                    )
                record_path = type3_records_dir / f"{cut_name}.gdb3.bin"
                if not record_path.is_file():
                    raise PresentationAuthorityError(
                        f"missing exact Type-3 record {record_path}"
                    )
                record_data = record_path.read_bytes()
                if sha256_bytes(record_data) != type3["sha256"]:
                    raise PresentationAuthorityError(
                        f"Type-3 hash differs for {cut_name}"
                    )

                nodes: list[dict[str, Any]] = []
                for root_node in cut.get("nodes", []):
                    for runtime_layer, runtime_node in _walk_nodes(root_node):
                        runtime_hash = (
                            int(runtime_layer["hash_low"]),
                            int(runtime_layer["hash_high"]),
                        )
                        layer = layers_by_hash.get(runtime_hash)
                        if layer is None:
                            raise PresentationAuthorityError(
                                f"GDP lacks owning layer hash {runtime_hash}"
                            )
                        node_name = str(runtime_node["name"])
                        normalised_name = _normalise_z2d_name(node_name)
                        if normalised_name in archive_names:
                            node_class = "exact_apk_z2d"
                        elif normalised_name in symbolic_names:
                            node_class = "runtime_symbolic_counter_overlay"
                        else:
                            raise PresentationAuthorityError(
                                f"{cut_name}/{node_name} is absent from exact parent-Z2D partition"
                            )
                        try:
                            parsed = parse_node(
                                record_data, node_name, allow_keyed_float=True
                            )
                        except ParseError as exc:
                            raise PresentationAuthorityError(
                                f"{cut_name}/{node_name}: {exc}"
                            ) from exc
                        transform = _node_transform(
                            parsed, instance_offset_frames=instance_offset
                        )
                        if transform["opacity"]["mode"] == "keyed":
                            keyed_parameter_occurrences += 1
                        motion_rows = _motion_rows(
                            runtime_node=runtime_node,
                            cut_name=cut_name,
                            instance_offset=instance_offset,
                        )
                        node_row = {
                            "event_id": event_id,
                            "event_parallel_scene_order": scene_order,
                            "scene_name": scene_name,
                            "scene_type2_frame_count": int(
                                type2["presentation_frame_count"]
                            ),
                            "cut_name": cut_name,
                            "cut_instance_offset_frames": instance_offset,
                            "owning_layer": {
                                "runtime_label_raw": str(runtime_layer.get("name", "")),
                                "canonical_name": str(layer["name"]),
                                "index": int(layer["index"]),
                                "hash_words": list(runtime_hash),
                                "render_buffer_target": int(
                                    layer["render_buffer_target"]
                                ),
                                "effective_viewport": layer["effective_viewport"],
                            },
                            "z2d_node": node_name,
                            "normalised_z2d_name": normalised_name,
                            "node_authority_class": node_class,
                            "node_flags": parsed["node_flags"],
                            "record_offset_hex": parsed["offset_hex"],
                            "transform": transform,
                            "motion_keys": motion_rows,
                        }
                        nodes.append(node_row)
                        flattened.append(node_row)
                scene_cuts.append(
                    {
                        "cut_name": cut_name,
                        "instance_offset_frames": instance_offset,
                        "cut_start_frame": int(cut["cut_start_frame"]),
                        "cut_end_frame_inclusive": int(cut["cut_end_frame"]),
                        "type3_sha256": type3["sha256"],
                        "z2d_nodes": nodes,
                    }
                )
            if actual_refs != expected_refs:
                raise PresentationAuthorityError(
                    f"{event_id}/{scene_name} Type-2/runtime references differ: "
                    f"expected={sorted(expected_refs)} actual={sorted(actual_refs)}"
                )
            event_scenes.append(
                {
                    "parallel_scene_order": scene_order,
                    "name": scene_name,
                    "event_global_start_frame": 0,
                    "type2_presentation_frame_count": int(
                        type2["presentation_frame_count"]
                    ),
                    "type2_sha256": type2["sha256"],
                    "cuts": scene_cuts,
                }
            )
        if not event_scenes:
            raise PresentationAuthorityError(f"{event_id} has no runtime scenes")
        if max(
            int(row["type2_presentation_frame_count"]) for row in event_scenes
        ) != runtime_extent:
            raise PresentationAuthorityError(
                f"{event_id} parallel Type-2 maximum differs from runtime extent"
            )
        events.append(
            {
                "event_id": event_id,
                "presentation_frame_count": runtime_extent,
                "presentation_seconds_at_30fps": runtime_extent / 30.0,
                "parallel_scene_count": len(event_scenes),
                "parallel_start_policy": "all_type2_scenes_start_at_event_global_frame_0",
                "event_extent_policy": "maximum_parallel_type2_presentation_frame_count",
                "scenes": event_scenes,
            }
        )

    archive_rows = [
        row for row in flattened if row["node_authority_class"] == "exact_apk_z2d"
    ]
    symbolic_rows = [
        row
        for row in flattened
        if row["node_authority_class"] == "runtime_symbolic_counter_overlay"
    ]
    counts = {
        "event_count": len(events),
        "scene_instance_count": scene_count,
        "cut_count": cut_count,
        "z2d_node_occurrence_count": len(flattened),
        "unique_z2d_node_count": len(
            {row["normalised_z2d_name"] for row in flattened}
        ),
        "archive_backed_z2d_occurrence_count": len(archive_rows),
        "unique_archive_backed_z2d_count": len(
            {row["normalised_z2d_name"] for row in archive_rows}
        ),
        "runtime_symbolic_z2d_occurrence_count": len(symbolic_rows),
        "unique_runtime_symbolic_z2d_count": len(
            {row["normalised_z2d_name"] for row in symbolic_rows}
        ),
        "keyed_parameter_occurrence_count": keyed_parameter_occurrences,
    }
    _validate_expected_counts(counts, expected_counts)

    return {
        "schema": "magireco-ac0915-gfdirection-presentation-authority-v1",
        "status": "passed_code_runtime_cross_bound_projection_pending",
        "exact_slot_binary": {
            "inherited_sha256": SLOT_BINARY_SHA256,
            "gnu_build_id": SLOT_BINARY_BUILD_ID,
        },
        "inputs": {
            "scene_group_authority": str(scene_group_path.resolve()),
            "gdp_authority": str(gdp_path.resolve()),
            "runtime_scene_motion": str(runtime_scene_path.resolve()),
            "type3_records_dir": str(type3_records_dir.resolve()),
            "parent_z2d_authority": str(parent_z2d_authority_path.resolve()),
            "scene_group_sha256": sha256_bytes(scene_group_path.read_bytes()),
            "gdp_authority_sha256": sha256_bytes(gdp_path.read_bytes()),
            "runtime_scene_motion_sha256": sha256_bytes(
                runtime_scene_path.read_bytes()
            ),
            "parent_z2d_authority_sha256": sha256_bytes(
                parent_z2d_authority_path.read_bytes()
            ),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "events": events,
        "summary": {
            **counts,
            "owning_layer_hashes": sorted(
                {
                    tuple(row["owning_layer"]["hash_words"])
                    for row in flattened
                }
            ),
            "owning_layer_names": sorted(
                {row["owning_layer"]["canonical_name"] for row in flattened}
            ),
            "runtime_symbolic_node_names": sorted(
                {row["normalised_z2d_name"] for row in symbolic_rows}
            ),
            "event_presentations": {
                row["event_id"]: {
                    "frames": row["presentation_frame_count"],
                    "parallel_scenes": [scene["name"] for scene in row["scenes"]],
                }
                for row in events
            },
        },
        "assertions": {
            "all_21_runtime_events_are_present": True,
            "all_26_runtime_scenes_bind_exact_type2_presentations": True,
            "all_runtime_cuts_match_type2_scene_references": True,
            "all_runtime_cuts_bind_exact_hashed_type3_records": True,
            "owning_gdp_layers_resolved_by_exact_two_word_hash_not_label": True,
            "five_secondary_presentations_share_event_global_frame_zero": True,
            "event_extent_is_maximum_of_parallel_type2_presentations": True,
            "all_48_type20_nodes_partition_into_archive_or_symbolic": True,
            "symbolic_counter_nodes_are_not_claimed_as_missing_cri_movies": True,
            "keyed_float_layout_is_code_exact_time_curve_value": True,
            "event_global_motion_ranges_include_cut_instance_offsets": True,
            "machine_vision_used_as_authority": False,
            "media_modified": False,
            "final_416x232_projection_resolved": False,
            "production_disposition": "FAIL_CLOSED_UNTIL_FINAL_OUTPUT_PROJECTION_IS_CODE_BOUND",
        },
    }


def _flatten_rows(authority: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in authority["events"]:
        for scene in event["scenes"]:
            for cut in scene["cuts"]:
                for node in cut["z2d_nodes"]:
                    motion_ranges = [
                        f"{row['event_global_start_frame']}..{row['event_global_end_frame_inclusive']}"
                        for row in node["motion_keys"]
                    ]
                    opacity = node["transform"]["opacity"]
                    keyed = opacity.get("keys", [])
                    viewport = node["owning_layer"]["effective_viewport"]
                    rows.append(
                        {
                            "event_id": event["event_id"],
                            "presentation_frames": event["presentation_frame_count"],
                            "parallel_scene_order": scene["parallel_scene_order"],
                            "scene_name": scene["name"],
                            "scene_frames": scene["type2_presentation_frame_count"],
                            "cut_name": cut["cut_name"],
                            "cut_instance_offset_frames": cut[
                                "instance_offset_frames"
                            ],
                            "owning_layer": node["owning_layer"]["canonical_name"],
                            "owning_layer_hash_low": node["owning_layer"][
                                "hash_words"
                            ][0],
                            "owning_layer_hash_high": node["owning_layer"][
                                "hash_words"
                            ][1],
                            "viewport_left": viewport["left"],
                            "viewport_top": viewport["top"],
                            "viewport_width": viewport["width"],
                            "viewport_height": viewport["height"],
                            "z2d_node": node["z2d_node"],
                            "node_authority_class": node["node_authority_class"],
                            "motion_event_global_ranges": ";".join(motion_ranges),
                            "opacity_mode": opacity["mode"],
                            "opacity_event_global_keys": ";".join(
                                f"{row['event_global_time_frames']}:{row['curve_type']}:{row['value']}"
                                for row in keyed
                            ),
                        }
                    )
    return rows


def _write_rollback(path: Path, final_root: Path) -> None:
    escaped_root = str(final_root.resolve()).replace("'", "''")
    path.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$root = '{escaped_root}'",
                "if (-not (Test-Path -LiteralPath $root)) { throw 'authority root is absent' }",
                "Write-Output 'ROLLBACK_VALIDATED: disable this immutable authority root by same-volume rename; exact GDB/GDP/runtime/APK evidence and media remain untouched.'",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_outputs(authority: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise PresentationAuthorityError(
            f"immutable output already exists: {output_dir}"
        )
    stage = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
    if stage.exists():
        raise PresentationAuthorityError(f"staging output already exists: {stage}")
    stage.mkdir(parents=True)
    try:
        authority_path = stage / "AC0915_GFDIRECTION_PRESENTATION_AUTHORITY.json"
        csv_path = stage / "PRESENTATION_Z2D_NODES.csv"
        verification_path = stage / "VERIFICATION_RECORD.json"
        readme_path = stage / "README.md"
        rollback_path = stage / "ROLLBACK.ps1"

        authority_path.write_text(
            json.dumps(authority, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rows = _flatten_rows(authority)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        _write_rollback(rollback_path, output_dir)
        readme_path.write_text(
            "# ac0915 GFDirection event-global presentation authority\n\n"
            "This immutable checkpoint binds all 21 events, 26 parallel scene "
            "instances, 26 exact Type-3 cuts, and 48 Type-20 nodes to the exact "
            "Slot binary, GDB/GDP bytes, runtime scene graph, and parent-Z2D "
            "partition. Five events contain a secondary presentation at the same "
            "event-global origin; those scenes are parallel, never serially "
            "concatenated. Five AT_UWANOSE numeric nodes are symbolic runtime "
            "counter overlays rather than missing CRI videos. Final 416x232 "
            "projection remains fail-closed, and no media was rendered or changed.\n",
            encoding="utf-8",
        )
        verification = {
            "schema": "magireco-ac0915-gfdirection-presentation-verification-v1",
            "status": "passed",
            "literal_result": (
                f"PASS events={authority['summary']['event_count']} "
                f"scenes={authority['summary']['scene_instance_count']} "
                f"cuts={authority['summary']['cut_count']} "
                f"z2d_occurrences={authority['summary']['z2d_node_occurrence_count']} "
                f"archive_occurrences={authority['summary']['archive_backed_z2d_occurrence_count']} "
                f"symbolic_occurrences={authority['summary']['runtime_symbolic_z2d_occurrence_count']} "
                "projection=FAIL_CLOSED_PENDING"
            ),
            "outputs": {
                authority_path.name: sha256_bytes(authority_path.read_bytes()),
                csv_path.name: sha256_bytes(csv_path.read_bytes()),
                readme_path.name: sha256_bytes(readme_path.read_bytes()),
                rollback_path.name: sha256_bytes(rollback_path.read_bytes()),
            },
            "checks": authority["assertions"],
        }
        verification_path.write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stage.rename(output_dir)
    except Exception:
        if stage.exists():
            (stage / "FAILED_DO_NOT_USE.txt").write_text(
                "The staged authority is incomplete and must not be used.\n",
                encoding="utf-8",
            )
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-group", required=True, type=Path)
    parser.add_argument("--gdp", required=True, type=Path)
    parser.add_argument("--runtime-scene", required=True, type=Path)
    parser.add_argument("--type3-records-dir", required=True, type=Path)
    parser.add_argument("--parent-z2d-authority", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    authority = build_authority(
        scene_group_path=args.scene_group,
        gdp_path=args.gdp,
        runtime_scene_path=args.runtime_scene,
        type3_records_dir=args.type3_records_dir,
        parent_z2d_authority_path=args.parent_z2d_authority,
    )
    write_outputs(authority, args.output_dir)
    print(
        f"PASS events={authority['summary']['event_count']} "
        f"scenes={authority['summary']['scene_instance_count']} "
        f"cuts={authority['summary']['cut_count']} "
        f"z2d_occurrences={authority['summary']['z2d_node_occurrence_count']} "
        f"archive_occurrences={authority['summary']['archive_backed_z2d_occurrence_count']} "
        f"symbolic_occurrences={authority['summary']['runtime_symbolic_z2d_occurrence_count']} "
        "projection=FAIL_CLOSED_PENDING"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
