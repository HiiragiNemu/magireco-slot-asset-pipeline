#!/usr/bin/env python3
"""Close exact ``ac0915`` MovieLayer projection onto native 416x232.

The runtime GFDirection project renders into a virtual 1280x1024 buffer.  The
physical Slot story surface is the exact GDP viewport ``[128,0,1152,576]`` and
maps to native 416x232.  Normal 1024x576 Z2D scenes fill that viewport, while
caption/button Z2D scenes authored at 1280x1024 and 1280x720 are composed in the
virtual buffer first and are then cropped by the same physical viewport.

This builder never guesses a visual match.  It joins event-global Type-20 node
timing, exact parent Z2D MovieLayers, exact CRI color/alpha sources, GDP layer
geometry, and an exact-hash IDA renderer contract.  Renderer state 3 is native
premultiplied addition (``src.rgb * src.a + dst.rgb``), not screen blend.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_exhaustive_unique_longform import file_sha256, read_json, write_json
    from .resolve_ac4903_exhaustive_authority import validate_renderer_authority
except ImportError:  # pragma: no cover - direct script execution
    from build_exhaustive_unique_longform import file_sha256, read_json, write_json  # type: ignore
    from resolve_ac4903_exhaustive_authority import validate_renderer_authority  # type: ignore


SCHEMA = "magireco-ac0915-output-projection-authority-v1"
VERIFY_SCHEMA = "magireco-ac0915-output-projection-verification-v1"
SLOT_BINARY_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
EVENTS = tuple(f"ac0915_{index:03d}" for index in range(1, 22))
RENDERBUFFER = (1280, 1024)
NORMAL_VIEWPORT = (128, 0, 1024, 576)
NORMAL_CROP_LTRB = (128, 0, 1152, 576)
OUTPUT = (416, 232)
TAIL_TRIM_POLICY = {"ac0915_007_c10": (211, 200)}
EXPECTED_COUNTS = {
    "events": 21,
    "archive_backed_z2d_occurrences": 43,
    "movie_bearing_z2d_occurrences": 26,
    "non_movie_text_z2d_occurrences": 17,
    "runtime_symbolic_node_occurrences": 5,
    "loadable_movie_layer_occurrences": 52,
    "unique_loadable_cri_sources": 42,
    "unreachable_movie_layer_occurrences": 6,
    "unique_unreachable_movie_layer_names": 2,
    "renderer_state_1_occurrences": 50,
    "renderer_state_3_occurrences": 2,
    "authored_tail_trim_occurrences": 2,
}

GFDIRECTION_DRAW_AUTHORITY = (
    (
        "0x42c2f64",
        "zg::CGFDirectionPlayer::Draw",
        "loops i=0..layer-array-size-1 and calls CGFDirectionLayer::Draw for each enabled layer; later GDP indices draw later/topmost",
    ),
    (
        "0x429c018",
        "zg::CGFDirectionLayer::Draw",
        "draws the active playlist for one exact GDP layer and its render-buffer viewport",
    ),
    (
        "0x42c8f0c",
        "zg::CGFDirectionPlaylist::Draw",
        "draws the active Type-3 cut selected by the Type-2 presentation clock",
    ),
    (
        "0x429b004",
        "zg::CGFDirectionCut::Draw",
        "selects a Type-38 node layer by the exact two-word GDP layer hash",
    ),
    (
        "0x42a9984",
        "zg::CGFDirectionNodeLayer::ForEachDrawNodeLayer",
        "iterates the compiled/sorted child node list in order; the runtime capture preserves that order",
    ),
    (
        "0x42a9148",
        "zg::CGFDirectionNodeLayer::Draw",
        "dispatches Type-20 nodes to DrawZ2D on the selected GDP layer",
    ),
)


class ProjectionError(ValueError):
    """An input differs from the bounded code-level projection contract."""


def _binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _normalise_z2d_name(value: str) -> str:
    return value[:-4] if value.casefold().endswith(".z2d") else value


def _identity_transform(node: Mapping[str, Any]) -> None:
    transform = node["transform"]
    rotation = transform["rotation_degrees"]
    opacity = transform["opacity"]
    if (
        [float(value) for value in transform["translation"]] != [0.0, 0.0]
        or [float(value) for value in transform["scale"]] != [1.0, 1.0]
        or [float(value) for value in transform["anchor_offset"]] != [0.0, 0.0]
        or rotation != {"mode": "static", "value": 0.0}
        or opacity != {"mode": "static", "value": 1.0}
        or int(transform["enabled"]) != 1
    ):
        raise ProjectionError(
            f"archive-backed Z2D transform is not identity: {node.get('z2d_node')}"
        )


def _validate_inputs(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    cri: Mapping[str, Any],
    project: Mapping[str, Any],
    renderer: Mapping[str, Any],
    *,
    expected_presentation_schema: str,
    family_label: str,
    expected_event_count: int,
    expected_presentation_node_count: int,
    expected_chunk_count: int,
    expected_unique_source_count: int,
    expected_movie_layer_count: int,
    expected_unique_loadable_layer_count: int,
    expected_unique_unreachable_layer_count: int,
) -> None:
    if (
        presentation.get("schema")
        != expected_presentation_schema
        or presentation.get("status")
        != "passed_code_runtime_cross_bound_projection_pending"
        or presentation.get("summary", {}).get("event_count")
        != expected_event_count
        or presentation.get("summary", {}).get("z2d_node_occurrence_count")
        != expected_presentation_node_count
    ):
        raise ProjectionError(f"{family_label} presentation authority differs")
    if (
        movie.get("schema")
        != "magireco-z2d-movielayer-reachability-authority-v1"
        or movie.get("status") != "passed"
        or movie.get("counts", {}).get("z2d_chunks") != expected_chunk_count
        or movie.get("counts", {}).get("movie_layers")
        != expected_movie_layer_count
        or movie.get("counts", {}).get("loadable_movie_layers")
        != expected_unique_loadable_layer_count
        or movie.get("counts", {}).get("unreachable_movie_layers")
        != expected_unique_unreachable_layer_count
    ):
        raise ProjectionError(f"{family_label} MovieLayer authority differs")
    if (
        cri.get("schema") != "magireco-selected-cri-usm-argb-authority-v1"
        or cri.get("status") != "passed_exact_color_alpha_streams_resolved"
        or cri.get("counts", {}).get("selected_usm_count")
        != expected_unique_source_count
        or cri.get("assertions", {}).get(
            "all_selected_usms_have_exact_color_and_alpha_video_streams"
        )
        is not True
    ):
        raise ProjectionError(f"{family_label} CRI ARGB authority differs")
    render_sets = project.get("project", {}).get("render_buffer_sets", [])
    if (
        project.get("schema")
        != "magireco-gfdirection-project-viewport-authority-v1"
        or project.get("status") != "passed_code_exact"
        or not render_sets
        or (int(render_sets[0]["width"]), int(render_sets[0]["height"]))
        != RENDERBUFFER
    ):
        raise ProjectionError("GFDirection project viewport authority differs")
    expected_renderer = {
        "renderer_state_1": {
            "rgb": "src_rgb*src_alpha + dst_rgb*(1-src_alpha)",
            "gl_blend_func_separate": [770, 771, 1, 771],
            "equation": 32774,
        },
        "renderer_state_3": {
            "rgb": "src_rgb*src_alpha + dst_rgb",
            "gl_blend_func_separate": [770, 1, 1, 1],
            "equation": 32774,
        },
    }
    for key, expected in expected_renderer.items():
        if renderer.get(key) != expected:
            raise ProjectionError(f"exact renderer contract differs: {key}")


def _source_rows(
    cri: Mapping[str, Any], *, expected_count: int
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for artifact in cri["artifacts"]:
        name = str(artifact["official_name"])
        if name in result:
            raise ProjectionError(f"duplicate CRI source identity: {name}")
        path = Path(str(artifact["path"])).resolve()
        if (
            not path.is_file()
            or path.stat().st_size != int(artifact["size"])
            or int(artifact["color_stream_index"]) != 0
            or int(artifact["alpha_stream_index"]) != 1
            or str(artifact["frame_rate"]) != "30/1"
        ):
            raise ProjectionError(f"exact CRI source binding differs: {name}")
        result[name] = {
            "official_name": name,
            "path": str(path),
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
            "global_index": int(artifact["global_index"]),
            "package": str(artifact["package"]),
            "package_index": int(artifact["package_index"]),
            "width": int(artifact["width"]),
            "height": int(artifact["height"]),
            "frame_rate": str(artifact["frame_rate"]),
            "frame_count": int(artifact["frame_count"]),
            "color_stream_index": 0,
            "alpha_stream_index": 1,
            "alpha_reconstruction": "color=video_stream_0 alpha=luma(video_stream_1)",
        }
    if len(result) != expected_count:
        raise ProjectionError("exact CRI source identity count differs")
    return result


def _layer_rect_in_renderbuffer(
    node: Mapping[str, Any],
    chunk: Mapping[str, Any],
    layer: Mapping[str, Any],
) -> tuple[int, int, int, int]:
    _identity_transform(node)
    viewport = node["owning_layer"]["effective_viewport"]
    canvas = (
        int(chunk["header"]["canvas_width"]),
        int(chunk["header"]["canvas_height"]),
    )
    viewport_size = (int(viewport["width"]), int(viewport["height"]))
    if canvas != viewport_size:
        raise ProjectionError(
            f"parent Z2D canvas/GDP viewport differ: {chunk['name']}"
        )
    left_f = (
        float(viewport["left"])
        + float(layer["position"][0])
        - float(layer["pivot"][0])
    )
    top_f = (
        float(viewport["top"])
        + float(layer["position"][1])
        - float(layer["pivot"][1])
    )
    if not left_f.is_integer() or not top_f.is_integer():
        raise ProjectionError(
            f"MovieLayer virtual origin is not integral: {chunk['name']}"
        )
    left = int(left_f)
    top = int(top_f)
    width = int(layer["layer_width"])
    height = int(layer["layer_height"])
    return left, top, left + width, top + height


def _intersection(
    first: Sequence[int], second: Sequence[int]
) -> tuple[int, int, int, int] | None:
    left = max(int(first[0]), int(second[0]))
    top = max(int(first[1]), int(second[1]))
    right = min(int(first[2]), int(second[2]))
    bottom = min(int(first[3]), int(second[3]))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _frame_policy(
    source_name: str, source_frames: int, authored_frames: int
) -> dict[str, Any]:
    if source_frames == authored_frames:
        return {
            "mode": "consume_exact_authored_span",
            "source_frame_count": source_frames,
            "consumed_source_frames": authored_frames,
            "discarded_unreferenced_tail_frames": 0,
        }
    expected = TAIL_TRIM_POLICY.get(source_name)
    if expected == (source_frames, authored_frames):
        return {
            "mode": "trim_exact_official_source_to_authored_z2d_span",
            "source_frame_count": source_frames,
            "consumed_source_frames": authored_frames,
            "discarded_unreferenced_tail_frames": source_frames - authored_frames,
            "reason": "exact Z2D MovieLayer interval ends before the official USM tail",
        }
    raise ProjectionError(
        f"authored/source frame span differs: {source_name}/"
        f"{authored_frames}!={source_frames}"
    )


def _validate_counts(actual: Mapping[str, int], expected: Mapping[str, int]) -> None:
    for key, value in expected.items():
        if actual.get(key) != value:
            raise ProjectionError(
                f"{key} differs: expected={value} actual={actual.get(key)}"
            )


def resolve(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    cri: Mapping[str, Any],
    project: Mapping[str, Any],
    renderer: Mapping[str, Any],
    *,
    expected_events: Sequence[str] = EVENTS,
    expected_presentation_schema: str = (
        "magireco-ac0915-gfdirection-presentation-authority-v1"
    ),
    family_label: str = "ac0915",
    expected_counts: Mapping[str, int] = EXPECTED_COUNTS,
    expected_chunk_count: int = 34,
    expected_movie_layer_count: int = 44,
    expected_unique_loadable_layer_count: int = 42,
    expected_unique_unreachable_layer_count: int = 2,
    expected_state3_names: frozenset[str] = frozenset(
        {"ac8050_uwanose_impact_ef", "ac8050_uwanose_impact_ef_LP"}
    ),
    expected_unreachable_names: frozenset[str] = frozenset(
        {"ac8040_premia_EF_add", "ac8040_premia_EF_add_LP"}
    ),
) -> dict[str, Any]:
    _validate_inputs(
        presentation,
        movie,
        cri,
        project,
        renderer,
        expected_presentation_schema=expected_presentation_schema,
        family_label=family_label,
        expected_event_count=len(expected_events),
        expected_presentation_node_count=int(
            expected_counts["archive_backed_z2d_occurrences"]
        )
        + int(expected_counts["runtime_symbolic_node_occurrences"]),
        expected_chunk_count=expected_chunk_count,
        expected_unique_source_count=int(
            expected_counts["unique_loadable_cri_sources"]
        ),
        expected_movie_layer_count=expected_movie_layer_count,
        expected_unique_loadable_layer_count=expected_unique_loadable_layer_count,
        expected_unique_unreachable_layer_count=expected_unique_unreachable_layer_count,
    )
    chunks = {str(row["name"]): row for row in movie["z2d_chunks"]}
    if len(chunks) != expected_chunk_count:
        raise ProjectionError("bounded parent Z2D identity count differs")
    sources = _source_rows(
        cri, expected_count=int(expected_counts["unique_loadable_cri_sources"])
    )
    events_by_id = {str(row["event_id"]): row for row in presentation["events"]}
    if set(events_by_id) != set(expected_events):
        raise ProjectionError("projection event set differs")

    event_rows: list[dict[str, Any]] = []
    all_loadable: list[dict[str, Any]] = []
    all_unreachable: list[dict[str, Any]] = []
    non_movie_nodes: list[dict[str, Any]] = []
    symbolic_nodes: list[dict[str, Any]] = []
    archive_occurrences = 0
    movie_node_occurrences = 0
    for event_id in expected_events:
        event = events_by_id[event_id]
        event_loadable: list[dict[str, Any]] = []
        event_unreachable: list[dict[str, Any]] = []
        event_non_movie: list[dict[str, Any]] = []
        event_symbolic: list[dict[str, Any]] = []
        parent_order = 0
        for scene in event["scenes"]:
            for cut in scene["cuts"]:
                for node in cut["z2d_nodes"]:
                    node_class = str(node["node_authority_class"])
                    if node_class == "runtime_symbolic_counter_overlay":
                        row = {
                            "event": event_id,
                            "scene": scene["name"],
                            "cut": cut["cut_name"],
                            "node": node["z2d_node"],
                            "disposition": (
                                "runtime_dynamic_counter_component_not_a_missing_cri_video"
                            ),
                        }
                        event_symbolic.append(row)
                        symbolic_nodes.append(row)
                        parent_order += 1
                        continue
                    if node_class != "exact_apk_z2d":
                        raise ProjectionError(
                            f"unknown Type-20 authority class: {node_class}"
                        )
                    archive_occurrences += 1
                    name = _normalise_z2d_name(str(node["z2d_node"]))
                    chunk = chunks.get(name)
                    if chunk is None:
                        raise ProjectionError(f"exact parent Z2D is absent: {name}")
                    motion_keys = node["motion_keys"]
                    if len(motion_keys) != 1:
                        raise ProjectionError(
                            f"{event_id}/{name} motion-key count differs"
                        )
                    parent_start = int(motion_keys[0]["event_global_start_frame"])
                    if not chunk["movie_layers"]:
                        row = {
                            "event": event_id,
                            "scene": scene["name"],
                            "cut": cut["cut_name"],
                            "node": name,
                            "event_global_start_frame": parent_start,
                            "event_global_end_frame_inclusive": int(
                                motion_keys[0]["event_global_end_frame_inclusive"]
                            ),
                            "owning_gdp_layer_index": int(
                                node["owning_layer"]["index"]
                            ),
                            "disposition": (
                                "exact_non_movie_z2d_text_presentation; edition subtitles "
                                "are resolved by the downstream audio/subtitle authority"
                            ),
                        }
                        event_non_movie.append(row)
                        non_movie_nodes.append(row)
                        parent_order += 1
                        continue
                    movie_node_occurrences += 1
                    for layer in chunk["movie_layers"]:
                        tag_index = int(layer["movie_layer_tag_value_hex"], 16) & 0x07FFFFFF
                        authored_frames = int(layer["frame_count"])
                        base = {
                            "event": event_id,
                            "scene": scene["name"],
                            "cut": cut["cut_name"],
                            "parent_z2d": name,
                            "parent_composition_order": parent_order,
                            "owning_gdp_layer_index": int(
                                node["owning_layer"]["index"]
                            ),
                            "owning_gdp_layer_name": str(
                                node["owning_layer"]["canonical_name"]
                            ),
                            "authored_tag_index": tag_index,
                            "authored_blend_enum": int(
                                layer["authored_blend_enum"]
                            ),
                            "effective_renderer_state": int(
                                layer["effective_renderer_state"]
                            ),
                            "source_name": str(layer["cri_lookup_base_name"]),
                            "event_start_frame": parent_start
                            + int(layer["start_frame"]),
                            "event_end_frame_inclusive": parent_start
                            + int(layer["end_frame_inclusive"]),
                            "authored_frame_count": authored_frames,
                        }
                        if (
                            layer["runtime_load_disposition"]
                            != "LOADABLE_BY_EXACT_NAME"
                        ):
                            row = {
                                **base,
                                "runtime_load_disposition": layer[
                                    "runtime_load_disposition"
                                ],
                                "decision": (
                                    "exclude_exactly_as_the_game_does; LoadUSMFileByName "
                                    "returns false and no substitute is inferred"
                                ),
                            }
                            event_unreachable.append(row)
                            all_unreachable.append(row)
                            continue
                        source_name = str(layer["cri_lookup_base_name"])
                        source = sources.get(source_name)
                        if source is None:
                            raise ProjectionError(
                                f"loadable MovieLayer lacks exact CRI: {source_name}"
                            )
                        rect = _layer_rect_in_renderbuffer(node, chunk, layer)
                        clipped = _intersection(rect, NORMAL_CROP_LTRB)
                        if clipped != NORMAL_CROP_LTRB:
                            raise ProjectionError(
                                f"{event_id}/{source_name} does not cover the exact physical viewport: {clipped}"
                            )
                        frame_policy = _frame_policy(
                            source_name,
                            int(source["frame_count"]),
                            authored_frames,
                        )
                        state = int(layer["effective_renderer_state"])
                        if state == 1:
                            blend = dict(renderer["renderer_state_1"])
                            ffmpeg_equivalent = (
                                "alpha_overlay_after_color0_plus_alpha1_reconstruction"
                            )
                        elif state == 3:
                            blend = dict(renderer["renderer_state_3"])
                            ffmpeg_equivalent = (
                                "premultiply_source_rgb_by_reconstructed_alpha_then_addition"
                            )
                        else:
                            raise ProjectionError(
                                f"unsupported exact renderer state: {state}"
                            )
                        output_scale_x = OUTPUT[0] / int(source["width"])
                        output_scale_y = OUTPUT[1] / int(source["height"])
                        row = {
                            **base,
                            "runtime_load_disposition": "LOADABLE_BY_EXACT_NAME",
                            "source": source,
                            "frame_policy": frame_policy,
                            "virtual_layer_rect_ltrb": list(rect),
                            "physical_viewport_crop_ltrb": list(NORMAL_CROP_LTRB),
                            "output_rect_xywh": [0, 0, *OUTPUT],
                            "runtime_authored_source_to_layer_scale": [
                                (rect[2] - rect[0]) / int(source["width"]),
                                (rect[3] - rect[1]) / int(source["height"]),
                            ],
                            "effective_source_to_output_scale": [
                                output_scale_x,
                                output_scale_y,
                            ],
                            "runtime_authored_component_scaling": (
                                int(source["width"]) < OUTPUT[0]
                                or int(source["height"]) < OUTPUT[1]
                            ),
                            "renderer_contract": blend,
                            "ffmpeg_equivalent": ffmpeg_equivalent,
                            "projection_recipe": (
                                "reconstruct CRI ARGB; scale/place on exact parent Z2D "
                                "MovieLayer rect in 1280x1024; draw GDP layers in ascending "
                                "index; crop [128,0,1152,576]; scale to 416x232"
                            ),
                        }
                        event_loadable.append(row)
                        all_loadable.append(row)
                    parent_order += 1
        event_loadable.sort(
            key=lambda row: (
                int(row["owning_gdp_layer_index"]),
                int(row["parent_composition_order"]),
                -int(row["authored_tag_index"]),
            )
        )
        event_rows.append(
            {
                "event": event_id,
                "presentation_frame_count": int(event["presentation_frame_count"]),
                "output_canvas": list(OUTPUT),
                "projection": {
                    "virtual_renderbuffer": list(RENDERBUFFER),
                    "physical_story_crop_ltrb": list(NORMAL_CROP_LTRB),
                    "physical_story_surface": [1024, 576],
                    "native_output": list(OUTPUT),
                    "mode": "COMPOSE_VIRTUAL_THEN_EXACT_NORMAL_VIEWPORT_CROP_TO_NATIVE_416",
                },
                "loadable_movie_layer_occurrences": len(event_loadable),
                "unreachable_movie_layer_occurrences": len(event_unreachable),
                "non_movie_text_z2d_occurrences": len(event_non_movie),
                "runtime_symbolic_node_occurrences": len(event_symbolic),
                "layers_in_render_pass_order_under_to_top": event_loadable,
                "unreachable_layers_excluded_by_exact_loader": event_unreachable,
                "non_movie_text_z2d_nodes": event_non_movie,
                "runtime_symbolic_nodes": event_symbolic,
            }
        )

    used_sources = {row["source_name"] for row in all_loadable}
    if used_sources != set(sources):
        raise ProjectionError(
            "projection does not cover every exact CRI identity: "
            f"missing={sorted(set(sources) - used_sources)}"
        )
    counts = {
        "events": len(event_rows),
        "archive_backed_z2d_occurrences": archive_occurrences,
        "movie_bearing_z2d_occurrences": movie_node_occurrences,
        "non_movie_text_z2d_occurrences": len(non_movie_nodes),
        "runtime_symbolic_node_occurrences": len(symbolic_nodes),
        "loadable_movie_layer_occurrences": len(all_loadable),
        "unique_loadable_cri_sources": len(used_sources),
        "unreachable_movie_layer_occurrences": len(all_unreachable),
        "unique_unreachable_movie_layer_names": len(
            {row["source_name"] for row in all_unreachable}
        ),
        "renderer_state_1_occurrences": sum(
            int(row["effective_renderer_state"]) == 1 for row in all_loadable
        ),
        "renderer_state_3_occurrences": sum(
            int(row["effective_renderer_state"]) == 3 for row in all_loadable
        ),
        "authored_tail_trim_occurrences": sum(
            row["frame_policy"]["discarded_unreferenced_tail_frames"] > 0
            for row in all_loadable
        ),
    }
    _validate_counts(counts, expected_counts)
    state3_names = {
        row["source_name"]
        for row in all_loadable
        if int(row["effective_renderer_state"]) == 3
    }
    if state3_names != set(expected_state3_names):
        raise ProjectionError("renderer-state-3 source set differs")
    unreachable_names = {row["source_name"] for row in all_unreachable}
    if unreachable_names != set(expected_unreachable_names):
        raise ProjectionError("exact unreachable MovieLayer set differs")
    return {
        "events": event_rows,
        "occurrences": all_loadable,
        "unreachable_occurrences": all_unreachable,
        "non_movie_nodes": non_movie_nodes,
        "symbolic_nodes": symbolic_nodes,
        "counts": counts,
        "runtime_authored_component_scale_sources": sorted(
            {
                row["source_name"]
                for row in all_loadable
                if row["runtime_authored_component_scaling"]
            }
        ),
    }


def _flatten_csv_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in result["occurrences"]:
        source = row["source"]
        rows.append(
            {
                "event": row["event"],
                "scene": row["scene"],
                "cut": row["cut"],
                "parent_z2d": row["parent_z2d"],
                "owning_gdp_layer_index": row["owning_gdp_layer_index"],
                "parent_composition_order": row["parent_composition_order"],
                "authored_tag_index": row["authored_tag_index"],
                "source_name": row["source_name"],
                "source_sha256": source["sha256"],
                "source_width": source["width"],
                "source_height": source["height"],
                "source_frame_count": source["frame_count"],
                "consumed_source_frames": row["frame_policy"][
                    "consumed_source_frames"
                ],
                "discarded_tail_frames": row["frame_policy"][
                    "discarded_unreferenced_tail_frames"
                ],
                "event_start_frame": row["event_start_frame"],
                "event_end_frame_inclusive": row["event_end_frame_inclusive"],
                "effective_renderer_state": row["effective_renderer_state"],
                "renderer_rgb_equation": row["renderer_contract"]["rgb"],
                "virtual_layer_rect_ltrb": ",".join(
                    str(value) for value in row["virtual_layer_rect_ltrb"]
                ),
                "physical_viewport_crop_ltrb": "128,0,1152,576",
                "output_rect_xywh": "0,0,416,232",
                "runtime_authored_component_scaling": row[
                    "runtime_authored_component_scaling"
                ],
            }
        )
    return rows


def build(
    *,
    binary_path: Path,
    presentation_path: Path,
    movie_path: Path,
    cri_path: Path,
    project_path: Path,
    renderer_order_path: Path,
    output_dir: Path,
) -> Path:
    binary_path = binary_path.resolve()
    if not binary_path.is_file() or file_sha256(binary_path) != SLOT_BINARY_SHA256:
        raise ProjectionError("exact Slot binary SHA-256 differs")
    renderer_document = read_json(renderer_order_path)
    renderer = validate_renderer_authority(renderer_document, binary_path)
    inputs = [
        presentation_path.resolve(),
        movie_path.resolve(),
        cri_path.resolve(),
        project_path.resolve(),
        renderer_order_path.resolve(),
        binary_path,
    ]
    result = resolve(
        read_json(presentation_path),
        read_json(movie_path),
        read_json(cri_path),
        read_json(project_path),
        renderer,
    )
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    staging = output_dir.with_name(
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    staging.mkdir(parents=True)
    try:
        authority = {
            "schema": SCHEMA,
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "family": "ac0915",
            "product_semantics": (
                "duplicate_free_exhaustive_editorial_collection_not_native_single_session"
            ),
            "output_canvas": list(OUTPUT),
            "frame_rate": "30/1",
            "inputs": [_binding(path) for path in inputs],
            "code_authority": [
                {"address": address, "function": function, "proves": proves}
                for address, function, proves in GFDIRECTION_DRAW_AUTHORITY
            ],
            "exact_renderer_contract": renderer,
            "projection_policy": {
                "virtual_renderbuffer": list(RENDERBUFFER),
                "physical_story_crop_ltrb": list(NORMAL_CROP_LTRB),
                "physical_story_surface": [1024, 576],
                "native_output": list(OUTPUT),
                "all_gdp_layers_draw_in_ascending_compiled_index": True,
                "normal_1024x576_sources_map_to_native_416x232_without_editorial_upscale": True,
                "full_1280x720_or_1280x1024_sources_are_composed_before_the_same_crop": True,
                "runtime_authored_component_scaling_is_not_a_postproduction_upscale": True,
            },
            "events": result["events"],
            "summary": {
                **result["counts"],
                "runtime_authored_component_scale_sources": result[
                    "runtime_authored_component_scale_sources"
                ],
            },
            "assertions": {
                "all_21_events_projected": True,
                "all_42_exact_cri_sources_reachable": True,
                "all_52_loadable_occurrences_have_exact_source_hashes": True,
                "five_symbolic_counter_nodes_are_not_missing_cri_videos": True,
                "seventeen_non_movie_z2d_occurrences_are_not_missing_cri_videos": True,
                "six_unreachable_additive_occurrences_are_excluded_without_substitution": True,
                "renderer_state_1_and_3_are_exact_slot_ida_bound": True,
                "renderer_state_3_is_premultiplied_addition_not_screen": True,
                "all_events_use_exact_normal_story_crop": True,
                "source_media_modified": False,
                "media_rendered": False,
                "P16_P17_P18_reference_count": 0,
            },
        }
        authority_path = staging / "AC0915_OUTPUT_PROJECTION_AUTHORITY.json"
        write_json(authority_path, authority)
        csv_path = staging / "MOVIELAYER_OUTPUT_PROJECTIONS.csv"
        rows = _flatten_csv_rows(result)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        readme_path = staging / "README.md"
        readme_path.write_text(
            "# ac0915 native-416 output projection authority\n\n"
            "全部 21 个事件先在精确 1280×1024 虚拟缓冲区按 GDP 层序合成，再统一裁切 "
            "`[128,0,1152,576]` 并映射为原生 416×232。52 个可加载 MovieLayer "
            "覆盖 42 个官方 CRI 源；两层 `ac8050` 冲击效果使用 IDA 证明的预乘加算 "
            "`src*alpha+dst`，不是 screen。`ac8040` 的两层 add 名称在三个事件中共 "
            "6 次均由精确加载器返回 false，按游戏行为排除且不猜替代物。13 个文字 "
            "Z2D（17 次出现）和 5 个动态计数节点不是缺失视频，由后续字幕/动态 UI "
            "边界处理。本检查点没有渲染或修改媒体。\n",
            encoding="utf-8",
        )
        rollback_path = staging / "ROLLBACK.ps1"
        rollback_path.write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not (Test-Path -LiteralPath (Join-Path $Root 'VERIFICATION_RECORD.json'))) { throw 'verification missing' }\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable projection checkpoint can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8",
        )
        verification = {
            "schema": VERIFY_SCHEMA,
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "literal_result": (
                f"PASS events={result['counts']['events']} "
                f"loadable_occurrences={result['counts']['loadable_movie_layer_occurrences']} "
                f"unique_sources={result['counts']['unique_loadable_cri_sources']} "
                f"state3={result['counts']['renderer_state_3_occurrences']} "
                f"unreachable={result['counts']['unreachable_movie_layer_occurrences']} "
                "output=416x232"
            ),
            "checks": authority["assertions"],
            "outputs": {
                authority_path.name: file_sha256(authority_path),
                csv_path.name: file_sha256(csv_path),
                readme_path.name: file_sha256(readme_path),
                rollback_path.name: file_sha256(rollback_path),
            },
        }
        write_json(staging / "VERIFICATION_RECORD.json", verification)
        staging.replace(output_dir)
    except BaseException:
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text(
                "Projection authority construction failed; inspect the command error.\n",
                encoding="utf-8",
            )
        raise
    return output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--presentation", required=True, type=Path)
    parser.add_argument("--movie", required=True, type=Path)
    parser.add_argument("--cri", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--renderer-order", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = build(
        binary_path=args.binary,
        presentation_path=args.presentation,
        movie_path=args.movie,
        cri_path=args.cri,
        project_path=args.project,
        renderer_order_path=args.renderer_order,
        output_dir=args.output_dir,
    )
    verification = read_json(output / "VERIFICATION_RECORD.json")
    print(verification["literal_result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
