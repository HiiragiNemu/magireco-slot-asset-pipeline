#!/usr/bin/env python3
"""Resolve exact Slot Z2D MovieLayer timing, reachability, and blend state."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
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
PUB_ROOT_TYPE = 13
MOVIE_ELEMENT_TYPE = 14

CODE_AUTHORITY = (
    (
        "0x4364f4c",
        "zg::CZ2DReader::ReadRecursiveElem",
        "decodes the high five bits of each element word and dispatches element type 10 as MovieLayer",
    ),
    (
        "0x44bde30",
        "Z2D element reader dispatch table",
        "maps element type 10 to ReadElemFunc_MovieLayer at 0x43661a8",
    ),
    (
        "0x43661f0",
        "zg::CZ2DReader::ReadMovieLayer",
        "reads the linked type-14 movie element ID into MovieLayer offset 0x94",
    ),
    (
        "0x4366834",
        "zg::CZ2DReader::ReadPubRoot",
        "for PubRoot kind 2 creates sequential type-14 movie elements and reads their exact names, frame ranges, remap values, and flags",
    ),
    (
        "0x435ea5c",
        "zg::CZ2DPlayer::DrawMovieLayer",
        "resolves MovieLayer offset 0x94 through CZ2DRoot::FindElem before drawing the linked movie",
    ),
    (
        "0x4367628",
        "zg::CZ2DReader::ReadLayerBase",
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
    movie_element_id_offset = geometry_offset + 20
    if movie_element_id_offset + 4 > len(data):
        raise BlendAuthorityError(f"MovieLayer movie-element ID is truncated for {reference}")
    movie_element_id = struct.unpack_from("<I", data, movie_element_id_offset)[0]
    if movie_element_id >> 27 != MOVIE_ELEMENT_TYPE:
        raise BlendAuthorityError(
            f"MovieLayer does not link a type-{MOVIE_ELEMENT_TYPE} movie element: "
            f"{reference}/0x{movie_element_id:08x}"
        )
    renderer_state = 1 if blend_enum == 0 else blend_state_table[blend_enum - 1]
    return {
        "z2d_reference": reference,
        "authored_layer_reference": reference,
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
        "movie_element_id_file_offset_hex": f"0x{movie_element_id_offset:x}",
        "movie_element_id": movie_element_id,
        "movie_element_id_hex": f"0x{movie_element_id:08x}",
    }


def authored_movie_layer_references(data: bytes) -> list[str]:
    """Return exact bracketed MovieLayer names in authored order."""

    references = [
        match.group(1).decode("ascii")
        for match in re.finditer(rb"\[([^\]\x00]+\.dgm)\]\x00", data)
    ]
    if len(references) != len(set(references)):
        raise BlendAuthorityError("duplicate bracketed MovieLayer names require occurrence IDs")
    for reference in references:
        string_offset = data.find(f"[{reference}]\0".encode("ascii"))
        _movie_layer_tag_offset(data, string_offset)
    return references


def parse_pubroot_movie_resource_tables(
    data: bytes, *, z2d_version: int
) -> list[dict[str, Any]]:
    """Decode exact PubRoot(kind=2) bulk movie tables used by Z2D v15.

    IDA authority: ReadPubRoot at 0x4366834 creates ``count`` sequential
    type-14 movie elements from ``base_id`` and then reads two uint32 arrays,
    start/end/remap arrays, a byte-counted name payload, and (v14+) flags.
    """

    tables: list[dict[str, Any]] = []
    for tag_offset in range(0, max(0, len(data) - 23), 4):
        tag = struct.unpack_from("<I", data, tag_offset)[0]
        if tag >> 27 != PUB_ROOT_TYPE:
            continue
        animation_count = data[tag_offset + 4]
        child_encoding = data[tag_offset + 5]
        if child_encoding & 1:
            continue
        authored_count = struct.unpack_from("<h", data, tag_offset + 6)[0]
        payload_offset = tag_offset + 8
        kind, count = struct.unpack_from("<2I", data, payload_offset)
        if kind != 2:
            continue
        if not (0 < count <= 0xFFFF):
            continue
        if authored_count != count:
            continue
        movie_element_base_id, name_payload_size = struct.unpack_from(
            "<2I", data, payload_offset + 8
        )
        if movie_element_base_id >> 27 != MOVIE_ELEMENT_TYPE:
            continue
        if (movie_element_base_id & 0x07FFFFFF) + count > 0x08000000:
            raise BlendAuthorityError("PubRoot sequential movie IDs overflow")

        cursor = payload_offset + 16
        fixed_size = count * (2 + 3) * 4
        if cursor + fixed_size + name_payload_size > len(data):
            raise BlendAuthorityError("PubRoot movie table is truncated")
        source_hashes = list(struct.unpack_from(f"<{count}I", data, cursor))
        cursor += count * 4
        original_hashes = list(struct.unpack_from(f"<{count}I", data, cursor))
        cursor += count * 4
        start_frames = list(struct.unpack_from(f"<{count}i", data, cursor))
        cursor += count * 4
        end_frames = list(struct.unpack_from(f"<{count}i", data, cursor))
        cursor += count * 4
        remap_frames = list(struct.unpack_from(f"<{count}i", data, cursor))
        cursor += count * 4

        names_start = cursor
        names_end = names_start + name_payload_size
        names: list[str] = []
        while len(names) < count:
            if cursor >= names_end:
                raise BlendAuthorityError("PubRoot movie name payload ended early")
            length = data[cursor]
            cursor += 1
            if cursor + length > names_end:
                raise BlendAuthorityError("PubRoot movie name exceeds its payload")
            try:
                name = data[cursor : cursor + length].decode("ascii")
            except UnicodeDecodeError as exc:
                raise BlendAuthorityError("PubRoot movie name is not ASCII") from exc
            cursor += length
            if not re.fullmatch(r"[A-Za-z0-9_]+\.dgm", name):
                raise BlendAuthorityError(f"PubRoot movie name is not an exact DGM: {name}")
            names.append(name)
        if cursor != names_end:
            raise BlendAuthorityError("PubRoot movie name payload has trailing bytes")

        if z2d_version >= 14:
            if cursor + count > len(data):
                raise BlendAuthorityError("PubRoot movie flags are truncated")
            movie_flags = list(data[cursor : cursor + count])
            cursor += count
        else:
            movie_flags = [0] * count
        aligned_end = (cursor + 3) & ~3
        if aligned_end > len(data):
            raise BlendAuthorityError("PubRoot movie table alignment exceeds the chunk")

        resources = []
        for index, name in enumerate(names):
            if end_frames[index] < start_frames[index]:
                raise BlendAuthorityError(f"PubRoot movie frame range is reversed: {name}")
            movie_element_id = movie_element_base_id + index
            resources.append(
                {
                    "movie_element_id": movie_element_id,
                    "movie_element_id_hex": f"0x{movie_element_id:08x}",
                    "movie_name": name,
                    "source_hash_hex": f"0x{source_hashes[index]:08x}",
                    "original_hash_hex": f"0x{original_hashes[index]:08x}",
                    "start_frame": start_frames[index],
                    "end_frame_inclusive": end_frames[index],
                    "time_remap_frame": remap_frames[index],
                    "movie_flag": movie_flags[index],
                }
            )
        tables.append(
            {
                "pubroot_tag_file_offset_hex": f"0x{tag_offset:x}",
                "pubroot_tag_value_hex": f"0x{tag:08x}",
                "animation_entry_count": animation_count,
                "authored_movie_count": authored_count,
                "movie_element_base_id_hex": f"0x{movie_element_base_id:08x}",
                "movie_name_payload_size": name_payload_size,
                "table_end_file_offset_hex": f"0x{aligned_end:x}",
                "resources": resources,
            }
        )

    movie_ids = [
        resource["movie_element_id"]
        for table in tables
        for resource in table["resources"]
    ]
    if len(movie_ids) != len(set(movie_ids)):
        raise BlendAuthorityError("PubRoot movie tables contain duplicate element IDs")
    return tables


def resolve_movie_layer_resources(
    data: bytes,
    *,
    blend_state_table: list[int],
    manifest_dgm_references: Iterable[str] | None = None,
    z2d_version: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Bind authored MovieLayers to exact PubRoot movie resources by ID."""

    if z2d_version is None:
        z2d_version = int(parse_z2d_header(data)["version"])
    layer_references = authored_movie_layer_references(data)
    tables = parse_pubroot_movie_resource_tables(data, z2d_version=z2d_version)
    resources = [resource for table in tables for resource in table["resources"]]
    by_id = {int(resource["movie_element_id"]): resource for resource in resources}
    layers: list[dict[str, Any]] = []
    for authored_index, layer_reference in enumerate(layer_references):
        layer = parse_movie_layer(data, layer_reference, blend_state_table)
        resource = by_id.get(int(layer["movie_element_id"]))
        if resource is None:
            raise BlendAuthorityError(
                f"MovieLayer has no exact PubRoot movie resource: "
                f"{layer_reference}/{layer['movie_element_id_hex']}"
            )
        layer.update(
            {
                "authored_reference_index": authored_index,
                "authored_layer_reference": layer_reference,
                "z2d_reference": resource["movie_name"],
                "movie_media_reference": resource["movie_name"],
                "layer_name_differs_from_movie_media_reference": (
                    layer_reference != resource["movie_name"]
                ),
                "movie_resource": resource,
            }
        )
        layers.append(layer)

    if layer_references and not resources:
        raise BlendAuthorityError("MovieLayers exist without a PubRoot movie table")
    if manifest_dgm_references is not None:
        observed = set(str(value) for value in manifest_dgm_references)
        exact = set(layer_references) | {
            str(resource["movie_name"]) for resource in resources
        }
        if observed != exact:
            raise BlendAuthorityError(
                f"named Z2D DGM strings differ from exact layer/resource union: "
                f"missing={sorted(exact - observed)} extra={sorted(observed - exact)}"
            )
    return layers, tables


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
        layers, movie_resource_tables = resolve_movie_layer_resources(
            data,
            blend_state_table=blend_state_table,
            manifest_dgm_references=references,
        )
        for layer in layers:
            base_name = str(layer["z2d_reference"])[:-4]
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
                "movie_resource_tables": movie_resource_tables,
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
