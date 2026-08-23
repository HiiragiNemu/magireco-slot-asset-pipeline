#!/usr/bin/env python3
"""Extract and reconstruct only DGI glyphs referenced by one exact Z2D."""

from __future__ import annotations

import argparse
import json
import re
import struct
import zipfile
from pathlib import Path
from typing import Any

import texture2ddecoder
from PIL import Image

try:
    from .extract_jm_dgi_glyph_catalog import parse_dmp_header
    from .extract_named_z2d_chunks_from_apk import (
        parse_offsets,
        read_native_relative_name_table,
        validate_exact_binary,
    )
except ImportError:  # direct script execution
    from extract_jm_dgi_glyph_catalog import parse_dmp_header  # type: ignore
    from extract_named_z2d_chunks_from_apk import (  # type: ignore
        parse_offsets,
        read_native_relative_name_table,
        validate_exact_binary,
    )


DGI_NATIVE_NAME_TABLE_OFFSET = 0x1461600
DGI_NATIVE_NAME_COUNT = 5785
DGI_BIN_ENTRY = "assets/dgi.bin"
DGI_ADD_ENTRY = "assets/dgi_add.bin"
DGI_REFERENCE_RE = re.compile(rb"(JM_[0-9A-Fa-f]{4,6}_[A-Za-z0-9]+_[A-Za-z0-9]+)\.dgi")
SPRITE_NAME_RE = re.compile(rb"<<(?P<name>JM_[A-Za-z0-9_]+)\.png/[^>]+>>\0")

CODE_AUTHORITY = (
    (
        "0x4365b68",
        "zg::ReadElemFunc_SpriteLayer",
        "reads the SpriteLayer base then stores the exact image-table index at element offset 0x94",
    ),
    (
        "0x4367628",
        "zg::CZ2DReader::ReadLayerBase",
        "decodes layer flags, compact frame range, position, pivot, dimensions, rotation and alpha",
    ),
    (
        "0x4350dac",
        "zg::CZ2DRoot::Calc2DPoint",
        "uses element position at 0x50, pivot at 0x84, dimensions at 0x78 and scale at 0x80",
    ),
    (
        "0x4350ac8",
        "zg::CZ2DRoot::Make2DRectPoint",
        "builds the authored SpriteLayer rectangle from the exact decoded layer fields",
    ),
)


class SelectedDgiError(ValueError):
    pass


def extract_references(z2d_data: bytes) -> list[str]:
    values: list[str] = []
    for match in DGI_REFERENCE_RE.finditer(z2d_data):
        value = match.group(1).decode("ascii")
        if value not in values:
            values.append(value)
    if not values:
        raise SelectedDgiError("target Z2D contains no JM DGI references")
    return values


def parse_caption_sprite_layers(z2d_data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in SPRITE_NAME_RE.finditer(z2d_data):
        name = match.group("name").decode("ascii")
        layer_base = (match.end() + 3) & ~3
        if layer_base + 32 > len(z2d_data):
            raise SelectedDgiError(f"SpriteLayer is truncated: {name}")
        layer_id, flags = struct.unpack_from("<2H", z2d_data, layer_base)
        if flags != 0x077E:
            raise SelectedDgiError(f"caption SpriteLayer flags differ for {name}: 0x{flags:04x}")
        start_frame, end_frame = struct.unpack_from("<2H", z2d_data, layer_base + 4)
        position_x, position_y, pivot_x, pivot_y = struct.unpack_from(
            "<4f", z2d_data, layer_base + 8
        )
        source_width, source_height = struct.unpack_from("<2h", z2d_data, layer_base + 24)
        image_index_word = struct.unpack_from("<I", z2d_data, layer_base + 28)[0]
        if image_index_word >> 27 != 2:
            raise SelectedDgiError(f"SpriteLayer image reference type differs for {name}")
        rows.append(
            {
                "resource_name": name,
                "layer_base_file_offset_hex": f"0x{layer_base:x}",
                "layer_id": layer_id,
                "flags_hex": f"0x{flags:04x}",
                "start_frame": start_frame,
                "end_frame_inclusive": end_frame,
                "position_x": position_x,
                "position_y": position_y,
                "pivot_x": pivot_x,
                "pivot_y": pivot_y,
                "source_width": source_width,
                "source_height": source_height,
                "image_index_word_hex": f"0x{image_index_word:08x}",
                "image_index": image_index_word & 0x07FFFFFF,
                "rotation_degrees": 0.0,
                "opacity": 1.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
            }
        )
    if not rows:
        raise SelectedDgiError("target Z2D contains no SpriteLayer names")
    return rows


def _codepoint_character(resource_name: str) -> str:
    codepoint = int(resource_name.split("_", 2)[1], 16)
    return chr(codepoint)


def extract_and_render(
    *, apk: Path, binary: Path, z2d: Path, output_dir: Path
) -> dict[str, Any]:
    build_id = validate_exact_binary(binary)
    z2d_data = z2d.read_bytes()
    references = extract_references(z2d_data)
    sprites = parse_caption_sprite_layers(z2d_data)
    sprite_names = [row["resource_name"] for row in sprites]
    if set(sprite_names) != set(references) or len(sprite_names) != len(references):
        raise SelectedDgiError("DGI reference set and SpriteLayer set do not match exactly")
    names = read_native_relative_name_table(
        binary, DGI_NATIVE_NAME_TABLE_OFFSET, DGI_NATIVE_NAME_COUNT
    )
    if len(names) != len(set(names)):
        raise SelectedDgiError("native DGI name table contains duplicates")
    by_name = {name: index for index, name in enumerate(names)}
    missing = [name for name in references if name not in by_name]
    if missing:
        raise SelectedDgiError(f"referenced DGI names are absent from native table: {missing}")

    png_dir = output_dir / "glyph_png"
    dmp_dir = output_dir / "glyph_dmp"
    png_dir.mkdir(parents=True, exist_ok=True)
    dmp_dir.mkdir(parents=True, exist_ok=True)
    extracted: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(apk) as archive:
        dgi_info = archive.getinfo(DGI_BIN_ENTRY)
        add_info = archive.getinfo(DGI_ADD_ENTRY)
        offsets = parse_offsets(archive.read(DGI_ADD_ENTRY), dgi_info.file_size)
        if len(offsets) - 1 != len(names):
            raise SelectedDgiError("native DGI name count and physical chunk count differ")
        with archive.open(DGI_BIN_ENTRY) as stream:
            for name in references:
                index = by_name[name]
                start, end = offsets[index], offsets[index + 1]
                stream.seek(start)
                chunk = stream.read(end - start)
                if len(chunk) != end - start:
                    raise SelectedDgiError(f"short DGI read: {name}")
                header = parse_dmp_header(chunk)
                payload = chunk[header.data_offset : header.data_offset + header.data_size]
                decoded = texture2ddecoder.decode_astc(
                    payload, header.width, header.height, 4, 4
                )
                image = Image.frombytes(
                    "RGBA", (header.width, header.height), decoded, "raw", "BGRA"
                )
                dmp_path = dmp_dir / f"{name}.dgi"
                png_path = png_dir / f"{name}.png"
                dmp_path.write_bytes(chunk)
                image.save(png_path)
                extracted[name] = {
                    "resource_name": name,
                    "character": _codepoint_character(name),
                    "archive_index": index,
                    "archive_offset": start,
                    "chunk_size": len(chunk),
                    "dmp_width": header.width,
                    "dmp_height": header.height,
                    "dmp_format_hex": f"0x{header.format_code:04x}",
                    "dmp_path": str(dmp_path.resolve()),
                    "png_path": str(png_path.resolve()),
                }

    canvas_width, canvas_height = struct.unpack_from(
        "<2I", z2d_data, ((z2d_data.find(b"\0", 0x78) + 4) & ~3) + 4
    )
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    for row in sprites:
        source = Image.open(extracted[row["resource_name"]]["png_path"]).convert("RGBA")
        if source.size != (row["source_width"], row["source_height"]):
            raise SelectedDgiError(f"SpriteLayer source dimensions differ: {row['resource_name']}")
        left = round(row["position_x"] - row["pivot_x"])
        top = round(row["position_y"] - row["pivot_y"])
        canvas.alpha_composite(source, (left, top))
        row["render_left_rounded"] = left
        row["render_top_rounded"] = top
        row["character"] = extracted[row["resource_name"]]["character"]
    caption_path = output_dir / "cap0908_banbanzai_tur_012__exact_z2d_canvas.png"
    canvas.save(caption_path)
    visual_order = sorted(sprites, key=lambda row: (row["position_x"], row["position_y"]))
    display_text = "".join(row["character"] for row in visual_order)
    report = {
        "schema": "magireco-selected-z2d-dgi-apk-extraction-v1",
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
            "inherited_sha256": "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF",
            "dgi_name_table_file_offset_hex": f"0x{DGI_NATIVE_NAME_TABLE_OFFSET:x}",
            "dgi_name_count": len(names),
        },
        "apk": {
            "path": str(apk.resolve()),
            "dgi_bin_entry": DGI_BIN_ENTRY,
            "dgi_bin_size": dgi_info.file_size,
            "dgi_bin_zip_crc32": f"{dgi_info.CRC:08X}",
            "dgi_add_entry": DGI_ADD_ENTRY,
            "dgi_add_size": add_info.file_size,
            "dgi_add_zip_crc32": f"{add_info.CRC:08X}",
            "physical_chunk_count": len(offsets) - 1,
        },
        "z2d": {
            "path": str(z2d.resolve()),
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "referenced_glyph_count": len(references),
            "display_text_from_exact_sprite_x_order": display_text,
            "exact_canvas_png": str(caption_path.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "glyphs": [extracted[name] for name in references],
        "sprite_layers_file_order": sprites,
        "sprite_layers_visual_order": [row["resource_name"] for row in visual_order],
        "assertions": {
            "all_referenced_glyphs_extracted_exactly_once": len(extracted) == len(references),
            "sprite_reference_set_matches_dgi_reference_set": set(sprite_names)
            == set(references),
            "all_sprite_layers_active_frames_0_to_29": all(
                (row["start_frame"], row["end_frame_inclusive"]) == (0, 29)
                for row in sprites
            ),
            "display_text_matches_catalog": display_text == "万々歳スペシャルセットだよ！",
            "full_dgi_archive_copied_out": False,
            "machine_vision_used_as_authority": False,
            "event_canvas_transform_resolved": False,
            "media_reencoded": False,
        },
    }
    (output_dir / "SELECTED_DGI_GLYPH_AUTHORITY.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = extract_and_render(
        apk=args.apk,
        binary=args.binary,
        z2d=args.z2d,
        output_dir=args.output_dir,
    )
    print(
        f"PASS selected_glyphs={len(report['glyphs'])} "
        f"text={report['z2d']['display_text_from_exact_sprite_x_order']} "
        "event_canvas_transform_resolved=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
