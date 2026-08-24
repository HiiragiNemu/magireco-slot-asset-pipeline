#!/usr/bin/env python3
"""Build code/runtime-bound GFDirection presentation authority for ac6007.

The builder joins four already bounded evidence classes without using visual
matching: the exact ac6007 GDB scene group, the exact GDP layer/viewports, a
single-session runtime scene graph, and the byte-exact type-3 records exported
from the GDB group.  It resolves Type-2 presentation extensions, owning GDP
layers, event-global Z2D motion ranges, and static/keyed node parameters.  It
does not decide the final 416x232 projection and does not render media.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .extract_gfdirection_z2d_resource_bindings import ParseError, parse_node
    from .extract_jm_dgi_glyph_catalog import sha256_bytes
except ImportError:  # pragma: no cover - direct script execution
    from extract_gfdirection_z2d_resource_bindings import ParseError, parse_node  # type: ignore
    from extract_jm_dgi_glyph_catalog import sha256_bytes  # type: ignore


SLOT_BINARY_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
EVENT_IDS = tuple(f"ac6007_{index:03d}" for index in range(1, 11))
EXPECTED_PARAMETER_IDS = (9, 11, 14, 16, 19, 21)

CODE_AUTHORITY = (
    (
        "0x437ecd8",
        "zg::C_Scene::fnInitScene",
        "loads the exact GDP and the ac6007 GDB scene group used by the runtime player",
    ),
    (
        "0x42c054c",
        "zg::CGFDirectionPlayer::LoadGDB",
        "loads the Type-2 presentation and Type-3 cut records parsed here",
    ),
    (
        "0x42b0374",
        "zg::CGFDirectionNodeLayer::Load",
        "defines the packed node hierarchy and parameter/motion counts",
    ),
    (
        "0x42b7824",
        "zg::CGFDirectionNodeSingleParameter<float>::Load",
        "loads each keyed float as time(float), curve type(int), value(float)",
    ),
    (
        "0x42b74b4",
        "zg::CGFDirectionNodeSingleParameter<float>::Calc",
        "uses key time for lookup, curve type for interpolation, and the third float as value",
    ),
    (
        "0x429cc40",
        "zg::CGFDirectionLayer::GetViewport",
        "resolves each owning layer viewport from the exact GDP",
    ),
    (
        "0x42a71bc",
        "zg::CGFDirectionNodeLayer::SetParameterZ2D",
        "applies the parsed transform and opacity relative to the owning GDP layer",
    ),
)


class PresentationAuthorityError(ValueError):
    """An input differs from the bounded ac6007 authority contract."""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_binary(report: dict[str, Any], label: str) -> None:
    inherited = report.get("binary", {}).get("inherited_sha256")
    if inherited != SLOT_BINARY_SHA256:
        raise PresentationAuthorityError(
            f"{label} exact Slot binary differs: {inherited!r}"
        )


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
            raise PresentationAuthorityError(f"unknown keyed-float curve type {curve_type}")
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
    if node["node_type"] != 20 or node["motion_count"] != 1:
        raise PresentationAuthorityError(
            f"{node['name']} is not one exact single-motion Z2D node"
        )
    if node["resource_index"] != -1:
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


def _runtime_presentation_extent(event: dict[str, Any]) -> int:
    ends: list[int] = []
    for scene in event.get("scenes", []):
        for cut in scene.get("cuts", []):
            ends.append(
                int(cut["instance_offset_frames"]) + int(cut["cut_end_frame"]) + 1
            )
    if not ends:
        raise PresentationAuthorityError("runtime event has no cuts")
    return max(ends)


def _select_presentation(
    event_id: str,
    event: dict[str, Any],
    type2_by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    extent = _runtime_presentation_extent(event)
    scene_names = {str(scene["name"]) for scene in event["scenes"]}
    candidates = [
        row
        for name, row in type2_by_name.items()
        if name in scene_names and int(row["presentation_frame_count"]) == extent
    ]
    if len(candidates) != 1:
        raise PresentationAuthorityError(
            f"{event_id} presentation selection differs: extent={extent} "
            f"scene_names={sorted(scene_names)} candidates={[row['name'] for row in candidates]}"
        )
    return candidates[0]


def build_authority(
    *,
    scene_group_path: Path,
    gdp_path: Path,
    runtime_scene_path: Path,
    type3_records_dir: Path,
    expected_event_ids: Sequence[str] = EVENT_IDS,
) -> dict[str, Any]:
    scene_report = _load_json(scene_group_path)
    gdp_report = _load_json(gdp_path)
    runtime_report = _load_json(runtime_scene_path)
    _validate_binary(scene_report, "scene-group authority")
    _validate_binary(gdp_report, "GDP authority")
    if scene_report.get("status") != "passed_code_exact":
        raise PresentationAuthorityError("scene-group authority is not passed_code_exact")
    if gdp_report.get("status") != "passed_code_exact":
        raise PresentationAuthorityError("GDP authority is not passed_code_exact")

    group = scene_report["group"]
    if group.get("name") != "ac6007" or int(group.get("compiled_index", -1)) != 174:
        raise PresentationAuthorityError("scene-group is not exact ac6007 index 174")
    type2_by_name = {row["name"]: row for row in group["type2_presentations"]}
    type3_by_name = {row["name"]: row for row in group["type3_records"]}
    layers_by_name = {row["name"]: row for row in gdp_report["project"]["layers"]}
    runtime_events = runtime_report.get("events", {})
    if tuple(sorted(runtime_events)) != tuple(sorted(expected_event_ids)):
        raise PresentationAuthorityError(
            f"runtime event set differs: {sorted(runtime_events)}"
        )

    events: list[dict[str, Any]] = []
    flattened: list[dict[str, Any]] = []
    keyed_parameter_occurrences = 0
    for event_id in expected_event_ids:
        event = runtime_events[event_id]
        presentation = _select_presentation(event_id, event, type2_by_name)
        runtime_extent = _runtime_presentation_extent(event)
        event_scenes: list[dict[str, Any]] = []
        for scene in event["scenes"]:
            type2 = type2_by_name.get(scene["name"])
            if type2 is None:
                raise PresentationAuthorityError(
                    f"{event_id} runtime scene {scene['name']} lacks Type-2 record"
                )
            scene_cuts: list[dict[str, Any]] = []
            expected_refs = {
                (
                    row["target_name"],
                    int(row["instance_offset_frames"]),
                    int(row["target_frame_count"]),
                )
                for row in type2["scene_references"]
            }
            actual_refs: set[tuple[str, int, int]] = set()
            for cut in scene["cuts"]:
                cut_name = str(cut["cut_name"])
                instance_offset = int(cut["instance_offset_frames"])
                cut_frames = int(cut["cut_end_frame"]) - int(cut["cut_start_frame"]) + 1
                actual_refs.add((cut_name, instance_offset, cut_frames))
                type3 = type3_by_name.get(cut_name)
                if type3 is None:
                    raise PresentationAuthorityError(
                        f"{event_id}/{scene['name']} cut {cut_name} lacks Type-3 record"
                    )
                record_path = type3_records_dir / f"{cut_name}.gdb3.bin"
                if not record_path.is_file():
                    raise PresentationAuthorityError(f"missing exact record {record_path}")
                record_data = record_path.read_bytes()
                if sha256_bytes(record_data) != type3["sha256"]:
                    raise PresentationAuthorityError(f"Type-3 hash differs for {cut_name}")
                nodes: list[dict[str, Any]] = []
                for root_node in cut.get("nodes", []):
                    for runtime_layer, runtime_node in _walk_nodes(root_node):
                        layer_name = str(runtime_layer["name"])
                        layer = layers_by_name.get(layer_name)
                        if layer is None:
                            raise PresentationAuthorityError(
                                f"GDP lacks owning layer {layer_name!r}"
                            )
                        runtime_hash = [
                            int(runtime_layer["hash_low"]),
                            int(runtime_layer["hash_high"]),
                        ]
                        if runtime_hash != [int(x) for x in layer["hash_words"]]:
                            raise PresentationAuthorityError(
                                f"GDP/runtime layer hash differs for {layer_name}"
                            )
                        node_name = str(runtime_node["name"])
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
                        motion_rows = []
                        for motion in runtime_node.get("motions", []):
                            if not motion.get("is_z2d_motion"):
                                raise PresentationAuthorityError(
                                    f"{cut_name}/{node_name} runtime motion is not Z2D"
                                )
                            for key in motion.get("keys", []):
                                floats = list(key.get("floats", []))
                                if len(floats) < 2:
                                    raise PresentationAuthorityError(
                                        f"{cut_name}/{node_name} runtime motion key is short"
                                    )
                                motion_rows.append(
                                    {
                                        "key_index": int(key["index"]),
                                        "raw_floats": floats,
                                        "raw_flags": list(key.get("flags", [])),
                                        "local_start_frame": int(floats[0]),
                                        "local_end_frame_inclusive": int(floats[1]),
                                        "event_global_start_frame": instance_offset
                                        + int(floats[0]),
                                        "event_global_end_frame_inclusive": instance_offset
                                        + int(floats[1]),
                                    }
                                )
                        node_row = {
                            "event_id": event_id,
                            "presentation_name": presentation["name"],
                            "scene_name": scene["name"],
                            "cut_name": cut_name,
                            "cut_instance_offset_frames": instance_offset,
                            "owning_layer": {
                                "name": layer_name,
                                "index": int(layer["index"]),
                                "hash_words": layer["hash_words"],
                                "render_buffer_target": int(layer["render_buffer_target"]),
                                "effective_viewport": layer["effective_viewport"],
                            },
                            "z2d_node": node_name,
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
                    f"{event_id}/{scene['name']} Type-2/runtime references differ: "
                    f"expected={sorted(expected_refs)} actual={sorted(actual_refs)}"
                )
            event_scenes.append(
                {
                    "name": scene["name"],
                    "type2_presentation_frame_count": int(
                        type2["presentation_frame_count"]
                    ),
                    "type2_sha256": type2["sha256"],
                    "cuts": scene_cuts,
                }
            )
        events.append(
            {
                "event_id": event_id,
                "selected_presentation_name": presentation["name"],
                "presentation_frame_count": runtime_extent,
                "presentation_seconds_at_30fps": runtime_extent / 30.0,
                "type2_sha256": presentation["sha256"],
                "scenes": event_scenes,
            }
        )

    return {
        "schema": "magireco-ac6007-gfdirection-presentation-authority-v1",
        "status": "passed_code_runtime_cross_bound_projection_pending",
        "exact_slot_binary": {
            "inherited_sha256": SLOT_BINARY_SHA256,
            "gnu_build_id": "a1aceffc5be1f2380cdcd9af4d8f9764ac2bf40b",
        },
        "inputs": {
            "scene_group_authority": str(scene_group_path.resolve()),
            "gdp_authority": str(gdp_path.resolve()),
            "runtime_scene_motion": str(runtime_scene_path.resolve()),
            "type3_records_dir": str(type3_records_dir.resolve()),
            "scene_group_sha256": sha256_bytes(scene_group_path.read_bytes()),
            "gdp_authority_sha256": sha256_bytes(gdp_path.read_bytes()),
            "runtime_scene_motion_sha256": sha256_bytes(runtime_scene_path.read_bytes()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "events": events,
        "summary": {
            "event_count": len(events),
            "z2d_node_occurrence_count": len(flattened),
            "unique_z2d_node_count": len({row["z2d_node"] for row in flattened}),
            "owning_layer_names": sorted(
                {row["owning_layer"]["name"] for row in flattened}
            ),
            "keyed_parameter_occurrence_count": keyed_parameter_occurrences,
            "selected_presentations": {
                row["event_id"]: {
                    "name": row["selected_presentation_name"],
                    "frames": row["presentation_frame_count"],
                }
                for row in events
            },
        },
        "assertions": {
            "all_runtime_events_have_one_exact_type2_presentation_extent": True,
            "all_runtime_cuts_match_type2_scene_references": True,
            "all_runtime_cuts_bind_exact_hashed_type3_records": True,
            "all_z2d_nodes_bind_exact_gdp_layers_by_name_and_hash": True,
            "keyed_float_layout_is_code_exact_time_curve_value": True,
            "event_global_motion_ranges_include_scene_instance_offsets": True,
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
                    rows.append(
                        {
                            "event_id": event["event_id"],
                            "presentation_name": event["selected_presentation_name"],
                            "presentation_frames": event["presentation_frame_count"],
                            "scene_name": scene["name"],
                            "cut_name": cut["cut_name"],
                            "cut_instance_offset_frames": cut["instance_offset_frames"],
                            "owning_layer": node["owning_layer"]["name"],
                            "viewport_left": node["owning_layer"]["effective_viewport"]["left"],
                            "viewport_top": node["owning_layer"]["effective_viewport"]["top"],
                            "viewport_width": node["owning_layer"]["effective_viewport"]["width"],
                            "viewport_height": node["owning_layer"]["effective_viewport"]["height"],
                            "z2d_node": node["z2d_node"],
                            "motion_event_global_ranges": ";".join(motion_ranges),
                            "opacity_mode": opacity["mode"],
                            "opacity_event_global_keys": ";".join(
                                f"{row['event_global_time_frames']}:{row['curve_type']}:{row['value']}"
                                for row in keyed
                            ),
                        }
                    )
    return rows


def write_outputs(authority: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    authority_path = output_dir / "AC6007_GFDIRECTION_PRESENTATION_AUTHORITY.json"
    csv_path = output_dir / "PRESENTATION_Z2D_NODES.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    rollback_path = output_dir / "ROLLBACK.md"

    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = _flatten_rows(authority)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification = {
        "schema": "magireco-ac6007-gfdirection-presentation-verification-v1",
        "status": "passed",
        "literal_result": (
            f"PASS events={authority['summary']['event_count']} "
            f"z2d_occurrences={authority['summary']['z2d_node_occurrence_count']} "
            f"unique_z2d={authority['summary']['unique_z2d_node_count']} "
            f"keyed={authority['summary']['keyed_parameter_occurrence_count']} "
            "projection=FAIL_CLOSED_PENDING"
        ),
        "outputs": {
            authority_path.name: sha256_bytes(authority_path.read_bytes()),
            csv_path.name: sha256_bytes(csv_path.read_bytes()),
        },
        "checks": authority["assertions"],
    }
    verification_path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    readme_path.write_text(
        "# ac6007 GFDirection presentation authority\n\n"
        "This immutable checkpoint binds all ten DirInfo events to exact Type-2/Type-3 "
        "GFDirection records, runtime instance offsets, GDP layers/viewports, and static or "
        "keyed Z2D parameters. It intentionally leaves the final 1280x1024 render-buffer to "
        "416x232 output projection fail-closed; no media was rendered or changed.\n",
        encoding="utf-8",
    )
    rollback_path.write_text(
        "# Rollback\n\nThis checkpoint is additive. Remove only this versioned output directory "
        "to roll it back; all source GDB/GDP/runtime evidence and media remain unchanged.\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-group", required=True, type=Path)
    parser.add_argument("--gdp", required=True, type=Path)
    parser.add_argument("--runtime-scene", required=True, type=Path)
    parser.add_argument("--type3-records-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    authority = build_authority(
        scene_group_path=args.scene_group,
        gdp_path=args.gdp,
        runtime_scene_path=args.runtime_scene,
        type3_records_dir=args.type3_records_dir,
    )
    write_outputs(authority, args.output_dir)
    print(
        f"PASS events={authority['summary']['event_count']} "
        f"z2d_occurrences={authority['summary']['z2d_node_occurrence_count']} "
        f"unique_z2d={authority['summary']['unique_z2d_node_count']} "
        f"keyed={authority['summary']['keyed_parameter_occurrence_count']} "
        "projection=FAIL_CLOSED_PENDING"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
