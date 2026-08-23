#!/usr/bin/env python3
"""Build code-bound ac0908_016 event-canvas composition evidence.

The builder is deliberately limited to the exact Slot GDB record and the
already extracted Z2D/DGI authority artifacts.  It resolves the remaining
caption transform and Android GL texture orientation without using visual
matching as evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

from tools.frida_runtime_probe.extract_gfdirection_z2d_resource_bindings import (
    ParseError,
    parse_node,
)


SLOT_BINARY_SHA256 = (
    "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
)
TARGET_NODE_NAMES = (
    "ac0908_pre_c10.z2d",
    "ac8040_premia_EF.z2d",
    "cap0908_banbanzai_tur_012.z2d",
)
EXPECTED_STATIC_TRANSFORM = {
    "enabled": 1,
    "translation": [0.0, 0.0],
    "rotation_degrees": 0.0,
    "scale": [1.0, 1.0],
    "opacity": 1.0,
    "anchor_offset": [0.0, 0.0],
}

CODE_AUTHORITY = (
    (
        "0x437ecd8",
        "zg::C_Scene::fnInitScene",
        "writes 1280x1024 into GFDIRECTION_INITPARAM before CGFDirectionPlayer::Initialize",
    ),
    (
        "0x42a71bc",
        "zg::CGFDirectionNodeLayer::SetParameterZ2D",
        "sets root anchor to half the Z2D display size and root position to half the renderbuffer plus node translation minus viewport origin",
    ),
    (
        "0x435ca40",
        "zg::CZ2DPlayer::GetDisplaySize",
        "returns the authored Z2D root display width and height",
    ),
    (
        "0x434b114",
        "zg::RendererImplGL::isTextureYUp",
        "returns true on the Android GL renderer path",
    ),
    (
        "0x4358f4c",
        "zg::CZ2DHardPlayer movie/sprite renderer path",
        "uses 1.0-v texture coordinates when the renderer reports texture-Y-up",
    ),
)

VIRTUAL_RENDER_SIZE = (1280, 1024)
MOVIE_VIEWPORT_SIZE = (1024, 576)
NATIVE_OUTPUT_SIZE = (416, 232)


class CompositionError(ValueError):
    """An input differs from the exact, bounded composition contract."""


def _compound_values(parameter: dict[str, Any]) -> list[float]:
    children = parameter.get("components", [])
    if [int(child["parameter_id"]) for child in children] != [1, 2]:
        raise CompositionError(
            f"parameter {parameter['parameter_id']} compound components differ"
        )
    return [float(child["static_value"]) for child in children]


def static_transform(node: dict[str, Any]) -> dict[str, Any]:
    rows = {int(row["parameter_id"]): row for row in node["parameters"]}
    if tuple(rows) != (9, 11, 14, 16, 19, 21):
        raise CompositionError(f"{node['name']} parameter ids differ")
    result = {
        "enabled": int(rows[9]["static_value"]),
        "translation": _compound_values(rows[11]),
        "rotation_degrees": float(rows[14]["static_value"]),
        "scale": _compound_values(rows[16]),
        "opacity": float(rows[19]["static_value"]),
        "anchor_offset": _compound_values(rows[21]),
    }
    if result != EXPECTED_STATIC_TRANSFORM:
        raise CompositionError(f"{node['name']} static transform differs: {result}")
    if node["resource_index"] != -1 or node["motion_count"] != 1:
        raise CompositionError(f"{node['name']} resource/motion header differs")
    if node["node_flags"] != [0, 1, 0]:
        raise CompositionError(f"{node['name']} flags differ")
    return result


def derive_center_crop(
    canvas_width: int,
    canvas_height: int,
    event_width: int,
    event_height: int,
    *,
    translation: tuple[float, float] = (0.0, 0.0),
    viewport_origin: tuple[float, float] = (0.0, 0.0),
) -> tuple[int, int, int, int]:
    """Resolve a centered child display inside the Slot virtual render canvas."""
    anchor_x = canvas_width / 2.0
    anchor_y = canvas_height / 2.0
    root_x = event_width / 2.0 + translation[0] - viewport_origin[0]
    root_y = event_height / 2.0 + translation[1] - viewport_origin[1]
    values = (anchor_x - root_x, anchor_y - root_y)
    if any(value != int(value) for value in values):
        raise CompositionError(f"non-integral exact crop origin: {values}")
    left, top = (int(value) for value in values)
    return left, top, left + event_width, top + event_height


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_movie_layers(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("status") != "passed":
        raise CompositionError("MovieLayer authority is not passed")
    if report.get("binary", {}).get("inherited_sha256") != SLOT_BINARY_SHA256:
        raise CompositionError("MovieLayer authority binary differs")
    chunks = {row["name"]: row for row in report["z2d_chunks"]}
    for name in ("ac0908_pre_c10", "ac8040_premia_EF", "cap0908_banbanzai_tur_012"):
        if name not in chunks:
            raise CompositionError(f"MovieLayer authority lacks {name}")

    pre = chunks["ac0908_pre_c10"]
    if [row["z2d_reference"] for row in pre["movie_layers"]] != [
        "ac0908_pre_c10.dgm",
        "ac0908_pre_c10_LP.dgm",
    ]:
        raise CompositionError("pre-c10 MovieLayer schedule differs")
    if [(row["start_frame"], row["end_frame_inclusive"]) for row in pre["movie_layers"]] != [
        (0, 89),
        (90, 179),
    ]:
        raise CompositionError("pre-c10 frame schedule differs")

    premia = chunks["ac8040_premia_EF"]
    layers = {row["z2d_reference"]: row for row in premia["movie_layers"]}
    expected = {
        "ac8040_premia_EF_add.dgm": (0, 59, 2, 3, False),
        "ac8040_premia_EF_add_LP.dgm": (60, 259, 2, 3, False),
        "ac8040_premia_EF.dgm": (0, 59, 0, 1, True),
        "ac8040_premia_EF_LP.dgm": (60, 259, 0, 1, True),
    }
    if set(layers) != set(expected):
        raise CompositionError("premia MovieLayer set differs")
    for reference, (start, end, blend, state, loadable) in expected.items():
        row = layers[reference]
        actual_loadable = row["runtime_load_disposition"] == "LOADABLE_BY_EXACT_NAME"
        actual = (
            row["start_frame"],
            row["end_frame_inclusive"],
            row["authored_blend_enum"],
            row["effective_renderer_state"],
            actual_loadable,
        )
        if actual != (start, end, blend, state, loadable):
            raise CompositionError(f"premia layer differs for {reference}: {actual}")
    all_movie_layers = [
        row for chunk in chunks.values() for row in chunk.get("movie_layers", [])
    ]
    if not all(
        row.get("position") == [512.0, 288.0]
        and row.get("pivot") == [512.0, 288.0]
        and row.get("layer_width") == 1024
        and row.get("layer_height") == 576
        for row in all_movie_layers
    ):
        raise CompositionError("MovieLayer centered 1024x576 geometry differs")
    if chunks["cap0908_banbanzai_tur_012"]["movie_layer_count"] != 0:
        raise CompositionError("caption unexpectedly contains MovieLayers")
    return chunks


def _validate_event_scene(report: dict[str, Any]) -> dict[str, Any]:
    scenes = {
        row["canonical_cut_name"]: row for row in report["canonical_visible_scenes"]
    }
    scene = scenes.get("ac0908_016")
    if scene is None or scene["frames"] != 180:
        raise CompositionError("ac0908_016 exact 180-frame scene is absent")
    if scene["z2d_names"] != list(TARGET_NODE_NAMES):
        raise CompositionError("ac0908_016 Z2D node order differs")
    caption_keys = []
    for node in scene["structure"]["nodes"]:
        for layer in node.get("children", []):
            for child in layer.get("children", []):
                if child.get("name") == "cap0908_banbanzai_tur_012.z2d":
                    caption_keys.extend(child["motions"][0]["keys"])
    if len(caption_keys) != 1 or caption_keys[0]["floats"][:2] != [6, 35]:
        raise CompositionError("caption event-global key differs from frames 6..35")
    return scene


def render_caption(
    glyph_report: dict[str, Any],
    output_dir: Path,
    native_width: int,
    native_height: int,
) -> dict[str, Any]:
    z2d = glyph_report["z2d"]
    canvas_width = int(z2d["canvas_width"])
    canvas_height = int(z2d["canvas_height"])
    if (canvas_width, canvas_height) != (1280, 1024):
        raise CompositionError("caption Z2D canvas differs from 1280x1024")
    glyph_rows = {row["resource_name"]: row for row in glyph_report["glyphs"]}
    layers = glyph_report["sprite_layers_file_order"]
    if len(glyph_rows) != 14 or len(layers) != 14:
        raise CompositionError("caption exact glyph/layer count differs from 14")
    if any((row["start_frame"], row["end_frame_inclusive"]) != (0, 29) for row in layers):
        raise CompositionError("caption glyph local active range differs")

    corrected_dir = output_dir / "corrected_gl_glyph_png"
    corrected_dir.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    corrected_paths: list[str] = []
    for layer in layers:
        name = layer["resource_name"]
        if name not in glyph_rows:
            raise CompositionError(f"glyph layer lacks extracted resource {name}")
        source = Path(glyph_rows[name]["png_path"])
        with Image.open(source) as image:
            corrected = image.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        corrected_path = corrected_dir / f"{name}.png"
        corrected.save(corrected_path)
        corrected_paths.append(str(corrected_path.resolve()))
        canvas.alpha_composite(
            corrected,
            (int(layer["render_left_rounded"]), int(layer["render_top_rounded"])),
        )

    canvas_path = output_dir / "cap0908_banbanzai_tur_012__gl_corrected_canvas.png"
    canvas.save(canvas_path)
    if (canvas_width, canvas_height) != VIRTUAL_RENDER_SIZE:
        raise CompositionError("caption does not match the exact Slot virtual render size")
    viewport_width, viewport_height = MOVIE_VIEWPORT_SIZE
    crop_box = derive_center_crop(
        canvas_width, canvas_height, viewport_width, viewport_height
    )
    viewport_overlay = canvas.crop(crop_box)
    viewport_path = (
        output_dir
        / "cap0908_banbanzai_tur_012__virtual_1024x576_viewport_overlay.png"
    )
    viewport_overlay.save(viewport_path)
    event_overlay = viewport_overlay.resize(
        (native_width, native_height), Image.Resampling.LANCZOS
    )
    event_path = output_dir / "cap0908_banbanzai_tur_012__native_416x232_overlay.png"
    event_overlay.save(event_path)
    canvas_bbox = canvas.getchannel("A").getbbox()
    event_bbox = event_overlay.getchannel("A").getbbox()
    if canvas_bbox is None or event_bbox is None:
        raise CompositionError("corrected caption render is empty")
    return {
        "android_gl_texture_y_up": True,
        "software_reproduction_operation": "vertical_flip_each_raw_astc_decoded_glyph_exactly_once",
        "canvas_size": [canvas_width, canvas_height],
        "virtual_render_size": [canvas_width, canvas_height],
        "movie_viewport_size": [viewport_width, viewport_height],
        "native_output_size": [native_width, native_height],
        "root_anchor": [canvas_width / 2.0, canvas_height / 2.0],
        "root_position_in_virtual_render": [canvas_width / 2.0, canvas_height / 2.0],
        "movie_viewport_box_left_top_right_bottom": list(crop_box),
        "native_scale_from_movie_viewport": [
            native_width / viewport_width,
            native_height / viewport_height,
        ],
        "canvas_alpha_bbox": list(canvas_bbox),
        "event_alpha_bbox": list(event_bbox),
        "caption_canvas_path": str(canvas_path.resolve()),
        "viewport_overlay_path": str(viewport_path.resolve()),
        "event_overlay_path": str(event_path.resolve()),
        "corrected_glyph_paths": corrected_paths,
    }


def build(
    record_path: Path,
    glyph_authority_path: Path,
    movie_layer_authority_path: Path,
    event_authority_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    data = record_path.read_bytes()
    if data[:4] != b"GDB\x03":
        raise CompositionError("input record is not GDB type 3")
    nodes: list[dict[str, Any]] = []
    for name in TARGET_NODE_NAMES:
        try:
            node = parse_node(data, name)
        except ParseError as exc:
            raise CompositionError(str(exc)) from exc
        transform = static_transform(node)
        nodes.append(
            {
                "name": name,
                "record_offset_hex": node["offset_hex"],
                "resource_index": node["resource_index"],
                "node_flags": node["node_flags"],
                "motion_count": node["motion_count"],
                "static_transform": transform,
            }
        )

    movie_report = _load_json(movie_layer_authority_path)
    movie_chunks = _validate_movie_layers(movie_report)
    scene = _validate_event_scene(_load_json(event_authority_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    caption = render_caption(
        _load_json(glyph_authority_path),
        output_dir,
        native_width=NATIVE_OUTPUT_SIZE[0],
        native_height=NATIVE_OUTPUT_SIZE[1],
    )
    result = {
        "schema": "magireco-ac0908-016-event-composition-authority-v1",
        "status": "passed_code_bound_event_canvas_resolved",
        "exact_slot_binary": {
            "inherited_sha256": SLOT_BINARY_SHA256,
            "gnu_build_id": "a1aceffc5be1f2380cdcd9af4d8f9764ac2bf40b",
        },
        "inputs": {
            "gdb_record": str(record_path.resolve()),
            "glyph_authority": str(glyph_authority_path.resolve()),
            "movie_layer_authority": str(movie_layer_authority_path.resolve()),
            "event_authority": str(event_authority_path.resolve()),
        },
        "code_authority": [
            {"address": a, "function": f, "proves": p}
            for a, f, p in CODE_AUTHORITY
        ],
        "event": {
            "event_id": "ac0908_016",
            "virtual_render_canvas": list(VIRTUAL_RENDER_SIZE),
            "movie_viewport": list(MOVIE_VIEWPORT_SIZE),
            "native_output_canvas": list(NATIVE_OUTPUT_SIZE),
            "frame_rate": 30,
            "event_frames": 180,
            "event_seconds": 6.0,
            "node_order": list(TARGET_NODE_NAMES),
            "nodes": nodes,
            "caption_event_global_range_inclusive": [6, 35],
            "caption_local_range_inclusive": [0, 29],
            "verified_retained_audio": {
                "request_id": 426,
                "sound_code": 1012,
                "role": "SE",
                "start_ms": 0,
                "duration_ms": 3833,
            },
        },
        "movie_layer_schedule": {
            "pre_c10": movie_chunks["ac0908_pre_c10"]["movie_layers"],
            "premia": movie_chunks["ac8040_premia_EF"]["movie_layers"],
            "unloadable_layers_excluded": [
                "ac8040_premia_EF_add.dgm",
                "ac8040_premia_EF_add_LP.dgm",
            ],
        },
        "caption_composition": caption,
        "assertions": {
            "event_canvas_transform_resolved": True,
            "slot_virtual_render_1280x1024_code_bound": True,
            "movie_viewport_1024x576_z2d_bound": True,
            "native_output_is_downsampled_from_movie_viewport": True,
            "android_gl_texture_orientation_resolved": True,
            "all_three_node_static_transforms_exact": True,
            "caption_event_global_timing_exact": True,
            "premia_add_layers_unloadable_in_exact_binary": True,
            "machine_vision_used_as_authority": False,
            "visual_inspection_role": "corroboration_only",
            "production_disposition": "READY_FOR_EXACT_AC0908_016_RENDER",
        },
        "source_scene_key_id": scene["scene_key_id"],
    }
    return result


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    authority = output_dir / "AC0908_016_EVENT_COMPOSITION_AUTHORITY.json"
    verification = output_dir / "VERIFICATION_RECORD.json"
    readme = output_dir / "README.md"
    rollback = output_dir / "ROLLBACK.md"
    authority.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verification.write_text(
        json.dumps(
            {
                "schema": "magireco-ac0908-016-event-composition-verification-v1",
                "status": "passed",
                "checks": result["assertions"],
                "literal_result": "PASS event=ac0908_016 canvas=416x232 frames=180 caption=6..35 transform=resolved texture_y=resolved",
                "outputs": [
                    authority.name,
                    Path(result["caption_composition"]["caption_canvas_path"]).name,
                    Path(result["caption_composition"]["viewport_overlay_path"]).name,
                    Path(result["caption_composition"]["event_overlay_path"]).name,
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readme.write_text(
        "# ac0908_016 code-bound event composition authority\n\n"
        "This immutable checkpoint resolves the 1280x1024 caption Z2D in the "
        "exact 1280x1024 Slot virtual render canvas, crops the centered "
        "1024x576 movie viewport, and downsamples that viewport to the native "
        "416x232 source-media output. The transform comes from exact Slot code "
        "and the type-3 GDB/Z2D values; Android GL texture orientation comes "
        "from the exact renderer implementation. Visual inspection is only "
        "corroboration. The authored premia add/addLP layers remain excluded "
        "because the exact compiled CRI filename table makes them unloadable.\n",
        encoding="utf-8",
    )
    rollback.write_text(
        "# Rollback\n\n"
        "This checkpoint is additive and does not modify source media. To roll "
        "back its use, remove its path from the downstream production manifest "
        "and retain this directory as withdrawn evidence.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--glyph-authority", required=True, type=Path)
    parser.add_argument("--movie-layer-authority", required=True, type=Path)
    parser.add_argument("--event-authority", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = build(
        args.record,
        args.glyph_authority,
        args.movie_layer_authority,
        args.event_authority,
        args.output_dir,
    )
    write_outputs(result, args.output_dir)
    print(
        "PASS event=ac0908_016 canvas=416x232 frames=180 "
        "caption=6..35 transform=resolved texture_y=resolved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
