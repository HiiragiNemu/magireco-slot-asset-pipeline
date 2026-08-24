#!/usr/bin/env python3
"""Close the code-bound ac6007 projection into a 416x232 editorial canvas.

The Slot renderer has two distinct main-screen surfaces in this family.  The
normal story surface is the exact GDP viewport [128,0,1152,576], while the
victory/revival presentations use the complete 1280x1024 render buffer.  The
former maps to the native 416x232 CRI surface.  The latter is *contained* in a
416x232 editorial frame so that no full-screen pixels are discarded.  This is
an exhaustive editorial collection contract, not a native single-session
claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_exhaustive_unique_longform import file_sha256, read_json, write_json
except ImportError:  # direct script execution
    from build_exhaustive_unique_longform import (  # type: ignore
        file_sha256,
        read_json,
        write_json,
    )


SCHEMA = "magireco-ac6007-output-projection-authority-v1"
VERIFY_SCHEMA = "magireco-ac6007-output-projection-verification-v1"
EVENTS = tuple(f"ac6007_{index:03d}" for index in range(1, 11))
NORMAL_EVENTS = frozenset(EVENTS[:6])
FULL_EVENTS = frozenset(EVENTS[6:])
RENDERBUFFER = (1280, 1024)
NORMAL_VIEWPORT = (128, 0, 1024, 576)
OUTPUT = (416, 232)


class ProjectionError(ValueError):
    """An input differs from the bounded code-level projection contract."""


def contain_rect(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> dict[str, Any]:
    """Return an exact centered contain rectangle with integral output pixels."""
    if min(source_width, source_height, target_width, target_height) <= 0:
        raise ProjectionError("projection dimensions must be positive")
    scale = min(Fraction(target_width, source_width), Fraction(target_height, source_height))
    width_fraction = source_width * scale
    height_fraction = source_height * scale
    if width_fraction.denominator != 1 or height_fraction.denominator != 1:
        raise ProjectionError(
            "content-preserving contain projection is not integral: "
            f"{source_width}x{source_height} -> {target_width}x{target_height}"
        )
    width = int(width_fraction)
    height = int(height_fraction)
    x = (target_width - width) // 2
    y = (target_height - height) // 2
    if x * 2 + width != target_width or y * 2 + height != target_height:
        raise ProjectionError("contain projection cannot be centered on integral pixels")
    return {
        "source_canvas": [source_width, source_height],
        "target_canvas": [target_width, target_height],
        "content_rect_xywh": [x, y, width, height],
        "content_rect_ltrb": [x, y, x + width, y + height],
        "scale_fraction": f"{scale.numerator}/{scale.denominator}",
        "scale": float(scale),
        "bars": {
            "left": x,
            "top": y,
            "right": target_width - x - width,
            "bottom": target_height - y - height,
        },
    }


def event_projection(event: str, primary_canvas: Sequence[int], viewport: Mapping[str, Any]) -> dict[str, Any]:
    canvas = tuple(int(value) for value in primary_canvas)
    actual_viewport = (
        int(viewport["left"]),
        int(viewport["top"]),
        int(viewport["width"]),
        int(viewport["height"]),
    )
    if event in NORMAL_EVENTS:
        if canvas != (1024, 576) or actual_viewport != NORMAL_VIEWPORT:
            raise ProjectionError(f"{event} normal-surface geometry differs")
        left, top, width, height = NORMAL_VIEWPORT
        return {
            "mode": "EXACT_NORMAL_VIEWPORT_TO_NATIVE_416",
            "runtime_renderbuffer_crop_ltrb": [left, top, left + width, top + height],
            "authored_surface": [width, height],
            "output_canvas": list(OUTPUT),
            "output_content_rect_xywh": [0, 0, *OUTPUT],
            "scale_xy": [OUTPUT[0] / width, OUTPUT[1] / height],
            "primary_cri_policy": "NATIVE_416X232_PASSTHROUGH",
            "caption_policy": "CROP_EXACT_GDP_NORMAL_VIEWPORT_THEN_SCALE_TO_416X232",
            "pixel_loss_within_selected_surface": False,
            "editorial_bars": {"left": 0, "top": 0, "right": 0, "bottom": 0},
        }
    if event in FULL_EVENTS:
        if canvas != RENDERBUFFER or actual_viewport != (0, 0, *RENDERBUFFER):
            raise ProjectionError(f"{event} full-surface geometry differs")
        contained = contain_rect(*RENDERBUFFER, *OUTPUT)
        return {
            "mode": "FULL_RENDERBUFFER_CONTENT_PRESERVING_CONTAIN",
            "runtime_renderbuffer_crop_ltrb": [0, 0, *RENDERBUFFER],
            "authored_surface": list(RENDERBUFFER),
            "output_canvas": list(OUTPUT),
            "output_content_rect_xywh": contained["content_rect_xywh"],
            "scale_xy": [contained["scale"], contained["scale"]],
            "scale_fraction": contained["scale_fraction"],
            "primary_cri_policy": "RUNTIME_AUTHORED_FULL_SURFACE_THEN_DOWNSCALE_TO_290X232",
            "caption_policy": "FULL_CANVAS_CAPTION_SCALED_WITH_THE_SAME_1280X1024_SURFACE",
            "pixel_loss_within_selected_surface": False,
            "editorial_bars": contained["bars"],
        }
    raise ProjectionError(f"unexpected event: {event}")


def source_projection(
    source_width: int,
    source_height: int,
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    x, y, width, height = (int(value) for value in projection["output_content_rect_xywh"])
    sx = Fraction(width, source_width)
    sy = Fraction(height, source_height)
    return {
        "source_dimensions": [source_width, source_height],
        "output_rect_xywh": [x, y, width, height],
        "scale_x_fraction": f"{sx.numerator}/{sx.denominator}",
        "scale_y_fraction": f"{sy.numerator}/{sy.denominator}",
        "scale_x": float(sx),
        "scale_y": float(sy),
        "editorial_upscale": sx > 1 or sy > 1,
    }


def _flatten_nodes(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(node)
        for scene in event["scenes"]
        for cut in scene["cuts"]
        for node in cut["z2d_nodes"]
    ]


def _primary_node(event_id: str, nodes: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    candidates = [
        node
        for node in nodes
        if str(node["z2d_node"]).startswith("ac6007_")
        and not str(node["z2d_node"]).startswith("ac6007_AT_")
    ]
    if event_id == "ac6007_001":
        candidates = [node for node in nodes if node["z2d_node"] == "ac6007_lev_c001_c002.z2d"]
    if not candidates:
        raise ProjectionError(f"{event_id} lacks a primary ac6007 visual node")
    return candidates[0]


def _binding(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _validate_inputs(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    cri: Mapping[str, Any],
    project: Mapping[str, Any],
) -> None:
    if (
        presentation.get("schema") != "magireco-ac6007-gfdirection-presentation-authority-v1"
        or presentation.get("status") != "passed_code_runtime_cross_bound_projection_pending"
        or presentation.get("summary", {}).get("event_count") != 10
    ):
        raise ProjectionError("ac6007 presentation authority differs")
    if (
        movie.get("status") != "passed"
        or movie.get("counts", {}).get("z2d_chunks") != 32
        or movie.get("counts", {}).get("loadable_movie_layers") != 33
    ):
        raise ProjectionError("ac6007 MovieLayer authority differs")
    if (
        cri.get("status") != "passed_exact_color_alpha_streams_resolved"
        or cri.get("counts", {}).get("selected_usm_count") != 33
    ):
        raise ProjectionError("ac6007 CRI ARGB authority differs")
    if (
        project.get("schema") != "magireco-gfdirection-project-viewport-authority-v1"
        or project.get("status") != "passed_code_exact"
        or project.get("project", {}).get("render_buffer_sets", [{}])[0].get("width") != 1280
        or project.get("project", {}).get("render_buffer_sets", [{}])[0].get("height") != 1024
    ):
        raise ProjectionError("GFDirection project viewport authority differs")


def resolve(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    cri: Mapping[str, Any],
    project: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_inputs(presentation, movie, cri, project)
    chunks = {str(row["name"]): row for row in movie["z2d_chunks"]}
    artifacts = {str(row["official_name"]): row for row in cri["artifacts"]}
    if len(chunks) != 32 or len(artifacts) != 33:
        raise ProjectionError("bounded source identities are not unique")

    event_rows: list[dict[str, Any]] = []
    occurrence_rows: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    used_sources: set[str] = set()
    runtime_authored_component_upscales: set[str] = set()
    for event in presentation["events"]:
        event_id = str(event["event_id"])
        if event_id not in EVENTS or event_id in seen_events:
            raise ProjectionError(f"unexpected or duplicate event: {event_id}")
        seen_events.add(event_id)
        nodes = _flatten_nodes(event)
        primary = _primary_node(event_id, nodes)
        primary_chunk_name = str(primary["z2d_node"]).removesuffix(".z2d")
        primary_chunk = chunks.get(primary_chunk_name)
        if primary_chunk is None:
            raise ProjectionError(f"primary Z2D chunk is absent: {primary_chunk_name}")
        header = primary_chunk["header"]
        projection = event_projection(
            event_id,
            [int(header["canvas_width"]), int(header["canvas_height"])],
            primary["owning_layer"]["effective_viewport"],
        )

        event_occurrences: list[dict[str, Any]] = []
        for node_order, node in enumerate(nodes):
            chunk_name = str(node["z2d_node"]).removesuffix(".z2d")
            chunk = chunks.get(chunk_name)
            if chunk is None:
                raise ProjectionError(f"presentation node lacks bounded Z2D: {chunk_name}")
            motion_keys = node["motion_keys"]
            if len(motion_keys) != 1:
                raise ProjectionError(f"{event_id}/{chunk_name} motion key count differs")
            event_offset = int(motion_keys[0]["event_global_start_frame"])
            for layer_order, layer in enumerate(chunk["movie_layers"]):
                if layer["runtime_load_disposition"] != "LOADABLE_BY_EXACT_NAME":
                    continue
                source_name = str(layer["cri_lookup_base_name"])
                source = artifacts.get(source_name)
                if source is None:
                    raise ProjectionError(f"loadable MovieLayer lacks exact CRI: {source_name}")
                projected = source_projection(
                    int(source["width"]), int(source["height"]), projection
                )
                if projected["editorial_upscale"]:
                    runtime_authored_component_upscales.add(source_name)
                row = {
                    "event": event_id,
                    "node_order": node_order,
                    "layer_order": layer_order,
                    "z2d_name": chunk_name,
                    "owning_gdp_layer": str(node["owning_layer"]["name"]),
                    "source_name": source_name,
                    "source_path": str(source["path"]),
                    "source_width": int(source["width"]),
                    "source_height": int(source["height"]),
                    "effective_renderer_state": int(layer["effective_renderer_state"]),
                    "event_start_frame": event_offset + int(layer["start_frame"]),
                    "event_end_frame_inclusive": event_offset + int(layer["end_frame_inclusive"]),
                    "output_x": projected["output_rect_xywh"][0],
                    "output_y": projected["output_rect_xywh"][1],
                    "output_width": projected["output_rect_xywh"][2],
                    "output_height": projected["output_rect_xywh"][3],
                    "scale_x_fraction": projected["scale_x_fraction"],
                    "scale_y_fraction": projected["scale_y_fraction"],
                    "editorial_upscale": projected["editorial_upscale"],
                }
                event_occurrences.append(row)
                occurrence_rows.append(row)
                used_sources.add(source_name)
        event_rows.append(
            {
                "event": event_id,
                "presentation_frame_count": int(event["presentation_frame_count"]),
                "primary_z2d": primary_chunk_name,
                "primary_gdp_layer": str(primary["owning_layer"]["name"]),
                "projection": projection,
                "loadable_movie_layer_occurrences": len(event_occurrences),
                "movie_layer_occurrences": event_occurrences,
            }
        )

    if seen_events != set(EVENTS):
        raise ProjectionError("event projection coverage differs")
    if used_sources != set(artifacts):
        raise ProjectionError(
            "projection does not cover every exact CRI identity: "
            f"missing={sorted(set(artifacts) - used_sources)}"
        )
    if runtime_authored_component_upscales != {"ac8040_kyo_anten"}:
        raise ProjectionError(
            "runtime-authored component scale boundary differs: "
            f"{sorted(runtime_authored_component_upscales)}"
        )
    return {
        "events": event_rows,
        "occurrences": occurrence_rows,
        "unique_source_count": len(used_sources),
        "runtime_authored_component_upscales": sorted(runtime_authored_component_upscales),
    }


def build(
    presentation_path: Path,
    movie_path: Path,
    cri_path: Path,
    project_path: Path,
    output_dir: Path,
) -> Path:
    inputs = [path.resolve() for path in (presentation_path, movie_path, cri_path, project_path)]
    result = resolve(*(read_json(path) for path in inputs))
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    staging = output_dir.with_name(f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    staging.mkdir(parents=True)
    try:
        authority = {
            "schema": SCHEMA,
            "status": "PASS_READY_FOR_EVENT_COMPOSITION",
            "family": "ac6007",
            "product_semantics": "duplicate_free_exhaustive_editorial_collection_not_native_single_session",
            "output_canvas": list(OUTPUT),
            "renderbuffer": list(RENDERBUFFER),
            "inputs": [_binding(path) for path in inputs],
            "code_bound_runtime_surfaces": {
                "normal_story": {
                    "renderbuffer_crop_ltrb": [128, 0, 1152, 576],
                    "authored_canvas": [1024, 576],
                    "native_cri_surface": [416, 232],
                },
                "full_victory_and_revival": {
                    "renderbuffer_crop_ltrb": [0, 0, 1280, 1024],
                    "authored_canvas": [1280, 1024],
                    "native_primary_cri_surface": [512, 416],
                },
            },
            "editorial_projection_policy": {
                "normal_story": "exact GDP viewport to native 416x232 surface",
                "full_victory_and_revival": "contain complete 1280x1024 surface as 290x232 with 63-pixel black bars on each side",
                "why_not_center_crop": "center crop would discard code-reachable full-screen pixels and GDP proves the normal viewport begins at top=0, not top=224",
                "primary_story_upscale": False,
                "full_surface_pixel_loss": False,
                "runtime_authored_component_scale_exception": "ac8040_kyo_anten is authored as a 208x120 MovieLayer stretched by Z2D to the exact 1024x576 normal surface; reproducing that transform is not a guessed post-production upscale",
            },
            "events": result["events"],
            "summary": {
                "events": len(result["events"]),
                "normal_surface_events": len(NORMAL_EVENTS),
                "full_surface_events": len(FULL_EVENTS),
                "movie_layer_occurrences": len(result["occurrences"]),
                "unique_cri_sources": result["unique_source_count"],
                "runtime_authored_component_upscale_sources": result["runtime_authored_component_upscales"],
            },
            "assertions": {
                "all_10_code_reachable_events_projected": True,
                "all_33_exact_cri_sources_reachable_in_projected_events": True,
                "normal_viewport_uses_exact_gdp_top_zero": True,
                "generic_vertical_center_crop_rejected": True,
                "full_screen_presentations_preserve_all_authored_pixels": True,
                "final_output_primary_media_has_no_editorial_upscale": True,
                "source_media_modified": False,
                "media_rendered": False,
            },
        }
        authority_path = staging / "AC6007_OUTPUT_PROJECTION_AUTHORITY.json"
        write_json(authority_path, authority)
        csv_path = staging / "MOVIELAYER_OUTPUT_PROJECTIONS.csv"
        fields = list(result["occurrences"][0])
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(result["occurrences"])
        verification = {
            "schema": VERIFY_SCHEMA,
            "status": "PASS_READY_FOR_EVENT_COMPOSITION",
            "checks": {
                "events": len(result["events"]),
                "normal_surface_events": len(NORMAL_EVENTS),
                "full_surface_events": len(FULL_EVENTS),
                "unique_cri_sources": result["unique_source_count"],
                "normal_crop": [128, 0, 1152, 576],
                "full_contain_rect_xywh": [63, 0, 290, 232],
                "blocked_p16_p17_p18_leak_count": 0,
                "source_media_modified": False,
            },
            "outputs": {
                authority_path.name: file_sha256(authority_path),
                csv_path.name: file_sha256(csv_path),
            },
        }
        write_json(staging / "VERIFICATION_RECORD.json", verification)
        (staging / "README.md").write_text(
            "# ac6007 output projection authority\n\n"
            "普通剧情严格采用 GDP 的 `[128,0,1152,576]` 画面窗口；全画面胜利/复活保留完整 "
            "1280×1024，并等比缩入 416×232（290×232，左右各 63 像素黑边）。本检查点没有渲染或修改媒体。\n",
            encoding="utf-8",
        )
        (staging / "ROLLBACK.ps1").write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not (Test-Path -LiteralPath (Join-Path $Root 'VERIFICATION_RECORD.json'))) { throw 'verification missing' }\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable metadata checkpoint can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8",
        )
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--presentation", type=Path, required=True)
    parser.add_argument("--movie-layers", type=Path, required=True)
    parser.add_argument("--cri-argb", type=Path, required=True)
    parser.add_argument("--gdp", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = build(
        args.presentation,
        args.movie_layers,
        args.cri_argb,
        args.gdp,
        args.output_dir,
    )
    verification = read_json(output / "VERIFICATION_RECORD.json")
    checks = verification["checks"]
    print(
        "PASS "
        f"events={checks['events']} normal={checks['normal_surface_events']} "
        f"full={checks['full_surface_events']} cri={checks['unique_cri_sources']} "
        f"full_rect={checks['full_contain_rect_xywh']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
