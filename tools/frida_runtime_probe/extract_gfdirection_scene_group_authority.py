#!/usr/bin/env python3
"""Extract one code-indexed GFDirection scene group and its type-3 records."""

from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Any, Sequence
from zipfile import ZipFile

from elftools.elf.elffile import ELFFile

try:
    from .extract_crivideo_filename_table_authority import _va_to_file_offset
    from .extract_jm_dgi_glyph_catalog import sha256_bytes
    from .extract_z2d_movie_layer_blend_authority import (
        SLOT_BINARY_SHA256,
        validate_exact_binary,
    )
except ImportError:  # pragma: no cover - direct script execution
    from extract_crivideo_filename_table_authority import _va_to_file_offset  # type: ignore
    from extract_jm_dgi_glyph_catalog import sha256_bytes  # type: ignore
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        SLOT_BINARY_SHA256,
        validate_exact_binary,
    )


SCHEMA = "magireco-gfdirection-scene-group-authority-v1"
SCENE_GROUP_ARRAY_VA = 0x4BB5FA0
SCENE_GROUP_COUNT = 0x122
OFFSET_ASSET = "assets/gdb_add.bin"
DATA_ASSET = "assets/gdb.bin"

CODE_AUTHORITY = (
    (
        "0x437ecd8",
        "zg::C_Scene::fnInitScene",
        "loads exactly 290 GFDirection groups in the AllSceneGroupArray order",
    ),
    (
        "0x437f078",
        "Slot GDB path formatter",
        "constructs each runtime path as %s/%s.gdb",
    ),
    (
        "0x4bb5fa0",
        "AllSceneGroupArray",
        "maps each loop index to its exact compiled scene-group name",
    ),
    (
        "0x42c054c",
        "zg::CGFDirectionPlayer::LoadGDB",
        "loads the selected group bytes through CGFDirectionUnit::Load",
    ),
)


class SceneGroupError(ValueError):
    """The selected group differs from the code-indexed GDB contract."""


def _read_c_string(stream: Any, offset: int, *, maximum: int = 256) -> str:
    stream.seek(offset)
    raw = bytearray()
    for _ in range(maximum):
        value = stream.read(1)
        if not value:
            raise SceneGroupError("compiled scene-group string is truncated")
        if value == b"\0":
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SceneGroupError("compiled scene-group string is not UTF-8") from exc
        raw.extend(value)
    raise SceneGroupError("compiled scene-group string exceeds bounded length")


def read_scene_group_names(binary: Path) -> list[str]:
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        relocations = elf.get_section_by_name(".rela.dyn")
        if relocations is None:
            raise SceneGroupError("exact binary lacks .rela.dyn")
        pointer_by_address: dict[int, int] = {}
        table_end = SCENE_GROUP_ARRAY_VA + SCENE_GROUP_COUNT * 8
        for relocation in relocations.iter_relocations():
            offset = int(relocation["r_offset"])
            if SCENE_GROUP_ARRAY_VA <= offset < table_end:
                if (
                    int(relocation["r_info_type"]) != 1027
                    or int(relocation["r_info_sym"]) != 0
                    or offset in pointer_by_address
                ):
                    raise SceneGroupError(
                        "AllSceneGroupArray relocation is not one R_AARCH64_RELATIVE entry"
                    )
                pointer_by_address[offset] = int(relocation["r_addend"])
        expected_addresses = [
            SCENE_GROUP_ARRAY_VA + index * 8 for index in range(SCENE_GROUP_COUNT)
        ]
        if set(pointer_by_address) != set(expected_addresses):
            raise SceneGroupError("AllSceneGroupArray relocation coverage differs")
        pointers = [pointer_by_address[address] for address in expected_addresses]
        names = [
            _read_c_string(stream, _va_to_file_offset(elf, pointer))
            for pointer in pointers
        ]
    if any(not name for name in names) or len(set(names)) != len(names):
        raise SceneGroupError("AllSceneGroupArray contains empty or duplicate names")
    return names


def _string255_at(data: bytes, offset: int) -> tuple[str, int]:
    if offset >= len(data):
        raise SceneGroupError("type-3 name length is truncated")
    length = data[offset]
    start = offset + 1
    end = start + length
    if end > len(data):
        raise SceneGroupError("type-3 name is truncated")
    raw = data[start:end]
    if raw.endswith(b"\0"):
        raw = raw[:-1]
    try:
        name = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SceneGroupError("type-3 name is not UTF-8") from exc
    return name, (end + 3) & ~3


def parse_group_chunk(chunk: bytes) -> dict[str, Any]:
    first_record = chunk.find(b"GDB")
    if first_record != 28:
        raise SceneGroupError(
            f"scene-group header differs: first GDB record at {first_record}"
        )
    records: list[dict[str, Any]] = []
    cursor = first_record
    terminator_seen = False
    while cursor < len(chunk):
        if cursor + 8 > len(chunk) or chunk[cursor : cursor + 3] != b"GDB":
            raise SceneGroupError(f"non-contiguous GDB record at 0x{cursor:x}")
        record_type = chunk[cursor + 3]
        body_size = struct.unpack_from("<I", chunk, cursor + 4)[0]
        end = cursor + 8 + body_size
        if end > len(chunk):
            raise SceneGroupError(f"GDB record at 0x{cursor:x} is truncated")
        record: dict[str, Any] = {
            "index": len(records),
            "offset": cursor,
            "offset_hex": f"0x{cursor:x}",
            "record_type": record_type,
            "body_size": body_size,
            "total_size": end - cursor,
            "sha256": sha256_bytes(chunk[cursor:end]),
        }
        if record_type == 3:
            if body_size < 24:
                raise SceneGroupError("type-3 GDB record is shorter than its header")
            frame_count, scene_start, scene_end = struct.unpack_from(
                "<III", chunk, cursor + 16
            )
            name, _ = _string255_at(chunk, cursor + 28)
            if not name or scene_end < scene_start or frame_count != scene_end - scene_start + 1:
                raise SceneGroupError(f"type-3 event header differs at 0x{cursor:x}")
            record.update(
                {
                    "name": name,
                    "frame_count": frame_count,
                    "scene_start_frame": scene_start,
                    "scene_end_frame_inclusive": scene_end,
                }
            )
        records.append(record)
        cursor = end
        if record_type == 4:
            if body_size != 0 or cursor != len(chunk):
                raise SceneGroupError("GDB terminator differs or is not final")
            terminator_seen = True
            break
    if not terminator_seen:
        raise SceneGroupError("scene group lacks final GDB type-4 terminator")
    type3 = [row for row in records if row["record_type"] == 3]
    names = [str(row["name"]) for row in type3]
    if len(names) != len(set(names)):
        raise SceneGroupError("scene group contains duplicate type-3 names")
    counts: dict[str, int] = {}
    for row in records:
        key = str(row["record_type"])
        counts[key] = counts.get(key, 0) + 1
    return {
        "header_size": first_record,
        "header_hex": chunk[:first_record].hex(),
        "records": records,
        "type3_records": type3,
        "counts_by_record_type": counts,
    }


def build_report(
    *,
    binary: Path,
    apk: Path,
    group_name: str,
    expected_group_index: int | None = None,
) -> tuple[dict[str, Any], bytes]:
    build_id, _, _ = validate_exact_binary(binary)
    names = read_scene_group_names(binary)
    matches = [index for index, name in enumerate(names) if name == group_name]
    if len(matches) != 1:
        raise SceneGroupError(f"expected one compiled group {group_name!r}, found {matches}")
    group_index = matches[0]
    if expected_group_index is not None and group_index != expected_group_index:
        raise SceneGroupError(
            f"compiled group index differs: {group_index} != {expected_group_index}"
        )
    with ZipFile(apk) as archive:
        try:
            offset_info = archive.getinfo(OFFSET_ASSET)
            data_info = archive.getinfo(DATA_ASSET)
        except KeyError as exc:
            raise SceneGroupError("APK lacks GDB data or offset asset") from exc
        offset_data = archive.read(offset_info)
        gdb_data = archive.read(data_info)
    if len(offset_data) % 4:
        raise SceneGroupError("gdb_add.bin offset table is not uint32 aligned")
    offsets = struct.unpack(f"<{len(offset_data) // 4}I", offset_data)
    if len(offsets) < SCENE_GROUP_COUNT + 1:
        raise SceneGroupError("gdb_add.bin lacks a closing offset for every compiled group")
    start, end = offsets[group_index], offsets[group_index + 1]
    if not 0 <= start < end <= len(gdb_data):
        raise SceneGroupError("selected GDB group offset range is invalid")
    chunk = gdb_data[start:end]
    parsed = parse_group_chunk(chunk)
    primary = [
        row
        for row in parsed["type3_records"]
        if str(row["name"]).startswith(f"{group_name}_")
    ]
    if not primary:
        raise SceneGroupError("selected group has no matching primary type-3 events")
    report = {
        "schema": SCHEMA,
        "status": "passed_code_exact",
        "binary": {
            "path": str(binary.resolve()),
            "gnu_build_id": build_id,
            "inherited_sha256": SLOT_BINARY_SHA256,
            "all_scene_group_array_va_hex": f"0x{SCENE_GROUP_ARRAY_VA:x}",
            "compiled_scene_group_count": len(names),
        },
        "source": {
            "apk_path": str(apk.resolve()),
            "offset_asset": OFFSET_ASSET,
            "offset_asset_size": len(offset_data),
            "offset_asset_sha256": sha256_bytes(offset_data),
            "data_asset": DATA_ASSET,
            "data_asset_size": len(gdb_data),
            "data_asset_sha256": sha256_bytes(gdb_data),
        },
        "group": {
            "name": group_name,
            "compiled_index": group_index,
            "offset": start,
            "end_offset_exclusive": end,
            "size": len(chunk),
            "sha256": sha256_bytes(chunk),
            "neighbor_names": {
                str(index): names[index]
                for index in range(max(0, group_index - 2), min(len(names), group_index + 3))
            },
            **parsed,
            "primary_type3_records": primary,
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "assertions": {
            "group_name_resolved_from_exact_compiled_array": True,
            "group_offsets_resolved_from_apk_offset_table": True,
            "gdb_records_are_contiguous_and_terminated": True,
            "type3_records_exported_without_transformation": True,
            "runtime_triggering_used_as_authority": False,
            "media_modified": False,
        },
    }
    return report, chunk


def write_outputs(report: dict[str, Any], chunk: bytes, output_dir: Path) -> None:
    if output_dir.exists():
        raise SceneGroupError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    chunk_path = output_dir / "EXACT_SCENE_GROUP_CHUNK.bin"
    chunk_path.write_bytes(chunk)
    if sha256_bytes(chunk_path.read_bytes()) != report["group"]["sha256"]:
        raise SceneGroupError("written scene-group chunk differs")
    records_dir = output_dir / "type3_records"
    records_dir.mkdir()
    rows = []
    for record in report["group"]["type3_records"]:
        start = int(record["offset"])
        end = start + int(record["total_size"])
        path = records_dir / f"{record['name']}.gdb3.bin"
        path.write_bytes(chunk[start:end])
        if sha256_bytes(path.read_bytes()) != record["sha256"]:
            raise SceneGroupError(f"written type-3 record differs: {record['name']}")
        rows.append(
            {
                "name": record["name"],
                "primary_group_event": str(record["name"]).startswith(
                    f"{report['group']['name']}_"
                ),
                "offset": start,
                "total_size": record["total_size"],
                "frame_count": record["frame_count"],
                "scene_start_frame": record["scene_start_frame"],
                "scene_end_frame_inclusive": record["scene_end_frame_inclusive"],
                "sha256": record["sha256"],
                "output_path": str(path.resolve()),
            }
        )
    report_path = output_dir / "GFDIRECTION_SCENE_GROUP_AUTHORITY.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "TYPE3_RECORDS.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    primary_count = len(report["group"]["primary_type3_records"])
    literal = (
        f"PASS group={report['group']['name']} index={report['group']['compiled_index']} "
        f"size={report['group']['size']} type3={len(rows)} primary={primary_count}"
    )
    (output_dir / "VERIFICATION_RECORD.json").write_text(
        json.dumps(
            {
                "schema": "magireco-gfdirection-scene-group-verification-v1",
                "status": "passed",
                "group_sha256": report["group"]["sha256"],
                "record_sha256s": {row["name"]: row["sha256"] for row in rows},
                "literal_result": literal,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--group-name", required=True)
    parser.add_argument("--expected-group-index", type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report, chunk = build_report(
        binary=args.binary,
        apk=args.apk,
        group_name=args.group_name,
        expected_group_index=args.expected_group_index,
    )
    write_outputs(report, chunk, args.output_dir)
    print(
        f"PASS group={report['group']['name']} index={report['group']['compiled_index']} "
        f"size={report['group']['size']} "
        f"type3={len(report['group']['type3_records'])} "
        f"primary={len(report['group']['primary_type3_records'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
