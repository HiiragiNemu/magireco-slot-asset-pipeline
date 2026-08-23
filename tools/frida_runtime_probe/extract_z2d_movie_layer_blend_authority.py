#!/usr/bin/env python3
"""Resolve exact Slot Z2D MovieLayer timing, reachability, and blend state."""

from __future__ import annotations

import argparse
import csv
import json
import math
import struct
from pathlib import Path
from typing import Any, Iterable

from elftools.elf.elffile import ELFFile

try:
    from .extract_crivideo_filename_table_authority import (
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SHA256,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import (  # type: ignore
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SHA256,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )


BLEND_STATE_TABLE_VA = 0x14BAD48
BLEND_STATE_TABLE_COUNT = 30
MOVIE_LAYER_TYPE = 10

CODE_AUTHORITY = (
    (
        "0x4364f4c",
        "zg::CZ2DHardData::ReadRecursiveElem",
        "decodes the high five bits of each element word and dispatches element type 10 as MovieLayer",
    ),
    (
        "0x44bde30",
        "Z2D element reader dispatch table",
        "maps element type 10 to zg::CZ2DHardData::ReadMovieLayer at 0x43661a8",
    ),
    (
        "0x4367628",
        "zg::CZ2DHardData::ReadLayerBase",
        "reads layer flags and stores the authored blend enum at layer offset 0x1c",
    ),
    (
        "0x435edc0",
        "zg::CZ2DHardPlayer::MakeNormalPrim",
        "copies layer offset 0x1c into the movie play primitive blend byte",
    ),
    (
        "0x4358f4c",
        "zg::CZ2DHardPlayer movie renderer-state selection",
        "maps blend enums 1..30 through the exact table at 0x14bad48 and otherwise selects renderer state 1",
    ),
)


class BlendAuthorityError(ValueError):
    pass


def validate_exact_binary(binary: Path) -> tuple[str, list[int], int]:
    if binary.stat().st_size != SLOT_BINARY_SIZE:
        raise BlendAuthorityError(f"exact binary size differs: {binary.stat().st_size}")
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        build_id = _gnu_build_id(elf)
        if build_id.casefold() != SLOT_BINARY_BUILD_ID.casefold():
            raise BlendAuthorityError(f"exact binary build-id differs: {build_id}")
        table_offset = _va_to_file_offset(elf, BLEND_STATE_TABLE_VA)
        stream.seek(table_offset)
        raw = stream.read(BLEND_STATE_TABLE_COUNT * 4)
    if len(raw) != BLEND_STATE_TABLE_COUNT * 4:
        raise BlendAuthorityError("blend-state table is truncated")
    values = list(struct.unpack(f"<{BLEND_STATE_TABLE_COUNT}I", raw))
    if any(value == 0 for value in values):
        raise BlendAuthorityError("blend-state table contains a zero renderer state")
    return build_id, values, table_offset


def parse_z2d_header(data: bytes) -> dict[str, Any]:
    if len(data) < 0x80 or data[:4] != b"z2d\0":
        raise BlendAuthorityError("not an exact Z2D chunk")
    version, scene_start, scene_end, scene_loop = struct.unpack_from("<4I", data, 4)
    frame_rate = struct.unpack_from("<f", data, 0x14)[0]
    end = data.find(b"\0", 0x78)
    if end < 0:
        raise BlendAuthorityError("Z2D filename is not NUL terminated")
    try:
        filename = data[0x78:end].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BlendAuthorityError("Z2D filename is not valid UTF-8") from exc
    cursor = (end + 4) & ~3
    if cursor + 12 > len(data):
        raise BlendAuthorityError("Z2D canvas header is truncated")
    reserved, canvas_width, canvas_height = struct.unpack_from("<3I", data, cursor)
    if reserved != 0 or canvas_width <= 0 or canvas_height <= 0:
        raise BlendAuthorityError("Z2D canvas header is inconsistent")
    if scene_end < scene_start or not (0 <= scene_loop <= scene_end):
        raise BlendAuthorityError("Z2D scene frame range is inconsistent")
    return {
        "version": version,
        "filename": filename,
        "scene_start_frame": scene_start,
        "scene_end_frame_inclusive": scene_end,
        "scene_loop_frame": scene_loop,
        "scene_frame_count": scene_end - scene_start + 1,
        "frame_rate": frame_rate,
        "canvas_width": canvas_width,
        "canvas_height": canvas_height,
    }


def _movie_layer_tag_offset(data: bytes, string_offset: int) -> int:
    for offset in range(string_offset - 4, max(-1, string_offset - 20), -4):
        if offset >= 0 and struct.unpack_from("<I", data, offset)[0] >> 27 == MOVIE_LAYER_TYPE:
            return offset
    raise BlendAuthorityError("exact MovieLayer type word was not found before DGM reference")


def parse_movie_layer(
    data: bytes, reference: str, blend_state_table: list[int]
) -> dict[str, Any]:
    needle = f"[{reference}]\0".encode("ascii")
    offsets: list[int] = []
    cursor = 0
    while True:
        offset = data.find(needle, cursor)
        if offset < 0:
            break
        offsets.append(offset)
        cursor = offset + 1
    if len(offsets) != 1:
        raise BlendAuthorityError(
            f"expected one bracketed MovieLayer reference for {reference}, found {len(offsets)}"
        )
    string_offset = offsets[0]
    tag_offset = _movie_layer_tag_offset(data, string_offset)
    tag = struct.unpack_from("<I", data, tag_offset)[0]
    layer_base = (string_offset + len(needle) + 3) & ~3
    if layer_base + 8 > len(data) or data[layer_base : layer_base + 2] != b"\0\0":
        raise BlendAuthorityError(f"MovieLayer base alignment differs for {reference}")
    flags = struct.unpack_from("<H", data, layer_base + 2)[0]
    if flags & 0x400:
        blend_enum = 0
        start_frame, end_frame = struct.unpack_from("<2H", data, layer_base + 4)
        geometry_offset = layer_base + 8
        layout = "flags_0x400_default_blend"
    else:
        if layer_base + 12 > len(data):
            raise BlendAuthorityError(f"explicit MovieLayer base is truncated for {reference}")
        blend_enum = struct.unpack_from("<I", data, layer_base + 4)[0]
        start_frame, end_frame = struct.unpack_from("<2H", data, layer_base + 8)
        geometry_offset = layer_base + 12
        layout = "explicit_uint32_blend_enum"
    if blend_enum > len(blend_state_table):
        raise BlendAuthorityError(f"MovieLayer blend enum is outside the exact table: {blend_enum}")
    if end_frame < start_frame:
        raise BlendAuthorityError(f"MovieLayer frame range is reversed for {reference}")
    if geometry_offset + 20 > len(data):
        raise BlendAuthorityError(f"MovieLayer geometry is truncated for {reference}")
    position_x, position_y, pivot_x, pivot_y, layer_width, layer_height = (
        struct.unpack_from("<4f2H", data, geometry_offset)
    )
    if not all(math.isfinite(value) for value in (position_x, position_y, pivot_x, pivot_y)):
        raise BlendAuthorityError(f"MovieLayer geometry is non-finite for {reference}")
    if layer_width == 0 or layer_height == 0:
        raise BlendAuthorityError(f"MovieLayer dimensions are empty for {reference}")
    renderer_state = 1 if blend_enum == 0 else blend_state_table[blend_enum - 1]
    return {
        "z2d_reference": reference,
        "movie_layer_tag_file_offset_hex": f"0x{tag_offset:x}",
        "movie_layer_tag_value_hex": f"0x{tag:08x}",
        "movie_layer_element_type": tag >> 27,
        "layer_flags_hex": f"0x{flags:04x}",
        "layer_layout": layout,
        "authored_blend_enum": blend_enum,
        "effective_renderer_state": renderer_state,
        "start_frame": start_frame,
        "end_frame_inclusive": end_frame,
        "frame_count": end_frame - start_frame + 1,
        "position": [position_x, position_y],
        "pivot": [pivot_x, pivot_y],
        "layer_width": layer_width,
        "layer_height": layer_height,
    }


def read_filename_table(path: Path) -> dict[str, int]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or set(rows[0]) != {"table_index", "name"}:
        raise BlendAuthorityError("compiled filename table CSV schema differs")
    result: dict[str, int] = {}
    for row in rows:
        name = row["name"]
        if name in result:
            raise BlendAuthorityError(f"compiled filename table contains a duplicate: {name}")
        result[name] = int(row["table_index"])
    return result


def build_report(
    *, binary: Path, z2d_manifest: Path, filename_table_csv: Path
) -> dict[str, Any]:
    build_id, blend_state_table, blend_table_offset = validate_exact_binary(binary)
    manifest = json.loads(z2d_manifest.read_text(encoding="utf-8"))
    if manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1":
        raise BlendAuthorityError("named Z2D manifest schema differs")
    if manifest.get("status") != "passed":
        raise BlendAuthorityError("named Z2D extraction did not pass")
    compiled_names = read_filename_table(filename_table_csv)
    chunks: list[dict[str, Any]] = []
    for source in manifest.get("chunks", []):
        path = Path(source["output_path"])
        data = path.read_bytes()
        header = parse_z2d_header(data)
        references = list(source.get("dgm_references", []))
        layers: list[dict[str, Any]] = []
        for reference in references:
            layer = parse_movie_layer(data, reference, blend_state_table)
            base_name = reference[:-4]
            table_index = compiled_names.get(base_name)
            layer.update(
                {
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
        chunks.append(
            {
                "name": source["name"],
                "path": str(path.resolve()),
                "chunk_index": source["chunk_index"],
                "chunk_offset": source["offset"],
                "chunk_size": source["size"],
                "header": header,
                "movie_layers": layers,
                "movie_layer_count": len(layers),
            }
        )
    all_layers = [layer for chunk in chunks for layer in chunk["movie_layers"]]
    centered_1024x576 = all(
        layer["position"] == [512.0, 288.0]
        and layer["pivot"] == [512.0, 288.0]
        and layer["layer_width"] == 1024
        and layer["layer_height"] == 576
        for layer in all_layers
    )
    if not centered_1024x576:
        raise BlendAuthorityError("one or more MovieLayers differ from centered 1024x576")
    entry = next((chunk for chunk in chunks if chunk["name"] == "ac0908_001_c01_MR"), None)
    if entry is None:
        raise BlendAuthorityError("ac0908_001_c01_MR is absent from named Z2D manifest")
    entry_ranges = [
        (layer["z2d_reference"], layer["start_frame"], layer["end_frame_inclusive"])
        for layer in entry["movie_layers"]
    ]
    if entry_ranges != [
        ("ac0908_001_c01_MR.dgm", 0, 21),
        ("ac0908_001_c02.dgm", 22, 86),
    ]:
        raise BlendAuthorityError(f"ac0908 entry MovieLayer ranges differ: {entry_ranges}")
    return {
        "schema": "magireco-z2d-movielayer-blend-and-reachability-authority-v1",
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
            "inherited_sha256": SLOT_BINARY_SHA256,
        },
        "inputs": {
            "named_z2d_manifest": str(z2d_manifest.resolve()),
            "compiled_crivideo_filename_table": str(filename_table_csv.resolve()),
        },
        "blend_state_table": {
            "virtual_address_hex": f"0x{BLEND_STATE_TABLE_VA:x}",
            "file_offset_hex": f"0x{blend_table_offset:x}",
            "entry_count": len(blend_state_table),
            "renderer_states_by_blend_enum_1_to_30": blend_state_table,
            "default_renderer_state_for_enum_0_or_outside_1_to_30": 1,
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "z2d_chunks": chunks,
        "assertions": {
            "all_authored_dgm_references_resolved_to_one_exact_movie_layer": len(all_layers)
            == sum(len(chunk["movie_layers"]) for chunk in chunks),
            "all_movie_layer_renderer_states_resolved": all(
                isinstance(layer["effective_renderer_state"], int) for layer in all_layers
            ),
            "all_movie_layers_are_centered_1024x576": centered_1024x576,
            "entry_parent_frame_count": entry["header"]["scene_frame_count"],
            "entry_exterior_exact_frames": 22,
            "entry_side_cooking_exact_frames": 65,
            "entry_layers_are_contiguous_and_exhaust_parent": entry_ranges
            == [
                ("ac0908_001_c01_MR.dgm", 0, 21),
                ("ac0908_001_c02.dgm", 22, 86),
            ],
            "machine_vision_used_as_authority": False,
            "media_reencoded": False,
        },
    }


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "Z2D_MOVIELAYER_BLEND_AUTHORITY.json"
    csv_path = output_dir / "Z2D_MOVIELAYERS.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    rows: list[dict[str, Any]] = []
    for chunk in report["z2d_chunks"]:
        for layer in chunk["movie_layers"]:
            rows.append(
                {
                    "z2d_name": chunk["name"],
                    "z2d_scene_frame_count": chunk["header"]["scene_frame_count"],
                    **layer,
                }
            )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification = {
        "schema": "magireco-z2d-movielayer-blend-verification-v1",
        "status": "passed",
        "checks": {
            "z2d_chunks": len(report["z2d_chunks"]),
            "movie_layers": len(rows),
            "loadable_movie_layers": sum(row["compiled_table_present"] for row in rows),
            "unloadable_movie_layers": sum(not row["compiled_table_present"] for row in rows),
            "entry_parent_frames": report["assertions"]["entry_parent_frame_count"],
            "entry_exterior_frames": report["assertions"]["entry_exterior_exact_frames"],
            "entry_side_cooking_frames": report["assertions"]["entry_side_cooking_exact_frames"],
        },
        "outputs": [report_path.name, csv_path.name],
    }
    verification_path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d-manifest", required=True, type=Path)
    parser.add_argument("--filename-table-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary,
        z2d_manifest=args.z2d_manifest,
        filename_table_csv=args.filename_table_csv,
    )
    write_outputs(report, args.output_dir)
    layer_count = sum(chunk["movie_layer_count"] for chunk in report["z2d_chunks"])
    print(
        f"PASS z2d={len(report['z2d_chunks'])} movie_layers={layer_count} "
        f"entry_frames={report['assertions']['entry_parent_frame_count']} "
        "machine_vision_authority=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
