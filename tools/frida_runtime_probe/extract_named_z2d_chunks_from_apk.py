"""Extract exact named Z2D chunks from the Slot APK without unpacking the archive."""

from __future__ import annotations

import argparse
import json
import struct
import zipfile
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

try:
    from .extract_crivideo_filename_table_authority import (
        AuthorityError,
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        extract_z2d_dgm_names,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import (  # type: ignore
        AuthorityError,
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        extract_z2d_dgm_names,
    )


NAME_TABLE_OFFSET = 0x1455934
NAME_COUNT = 12083
Z2D_BIN_ENTRY = "assets/z2d.bin"
Z2D_ADD_ENTRY = "assets/z2d_add.bin"


class ExtractionError(RuntimeError):
    pass


def extract_optional_dgm_references(z2d: Path) -> tuple[list[str], str]:
    """Return authored DGM references without rejecting image-only Z2Ds."""

    try:
        return extract_z2d_dgm_names(z2d), "authored_dgm_references"
    except AuthorityError as exc:
        if str(exc) != "target Z2D contains no .dgm references":
            raise
        return [], "no_authored_dgm_reference"


def read_native_relative_name_table(
    native_lib: Path, table_offset: int, count: int
) -> list[str]:
    data = native_lib.read_bytes()
    table_end = table_offset + count * 4
    if table_offset < 0 or table_end > len(data):
        raise ExtractionError("native Z2D name table is outside the exact binary")
    names: list[str] = []
    for index in range(count):
        relative = struct.unpack_from("<i", data, table_offset + index * 4)[0]
        start = table_offset + relative
        if start < 0 or start >= len(data):
            raise ExtractionError(f"native Z2D name {index} points outside the binary")
        end = data.find(b"\x00", start)
        if end < 0:
            raise ExtractionError(f"native Z2D name {index} is not NUL terminated")
        names.append(data[start:end].decode("utf-8", errors="strict"))
    return names


def parse_offsets(data: bytes, archive_size: int) -> list[int]:
    if len(data) % 4:
        raise ExtractionError("Z2D offset table is not uint32-aligned")
    offsets = list(struct.unpack(f"<{len(data) // 4}I", data))
    if not offsets or offsets[0] != 0:
        raise ExtractionError("Z2D offset table does not begin at zero")
    if offsets[-1] != archive_size:
        offsets.append(archive_size)
    if any(right < left for left, right in zip(offsets, offsets[1:])):
        raise ExtractionError("Z2D offset table is not monotonic")
    return offsets


def target_ranges(
    names: list[str], offsets: list[int], target_names: list[str]
) -> list[dict[str, int | str]]:
    if len(offsets) != len(names) + 1:
        raise ExtractionError("native Z2D name count and physical chunk count differ")
    if len(names) != len(set(names)):
        raise ExtractionError("native Z2D name table contains duplicates")
    if len(target_names) != len(set(target_names)):
        raise ExtractionError("requested Z2D names contain duplicates")
    by_name = {name: index for index, name in enumerate(names)}
    missing = [name for name in target_names if name not in by_name]
    if missing:
        raise ExtractionError(f"requested Z2D names are absent: {missing}")
    return [
        {
            "name": name,
            "chunk_index": by_name[name],
            "offset": offsets[by_name[name]],
            "size": offsets[by_name[name] + 1] - offsets[by_name[name]],
        }
        for name in target_names
    ]


def validate_exact_binary(binary: Path) -> str:
    if binary.stat().st_size != SLOT_BINARY_SIZE:
        raise ExtractionError("exact Slot binary size differs")
    with binary.open("rb") as stream:
        build_id = _gnu_build_id(ELFFile(stream))
    if build_id.casefold() != SLOT_BINARY_BUILD_ID.casefold():
        raise ExtractionError("exact Slot binary GNU build-id differs")
    return build_id


def extract(
    *, apk: Path, binary: Path, target_names: list[str], output_dir: Path
) -> dict[str, Any]:
    build_id = validate_exact_binary(binary)
    names = read_native_relative_name_table(binary, NAME_TABLE_OFFSET, NAME_COUNT)
    with zipfile.ZipFile(apk) as archive:
        z2d_info = archive.getinfo(Z2D_BIN_ENTRY)
        add_info = archive.getinfo(Z2D_ADD_ENTRY)
        offsets = parse_offsets(archive.read(Z2D_ADD_ENTRY), z2d_info.file_size)
        ranges = target_ranges(names, offsets, target_names)
        output_dir.mkdir(parents=True, exist_ok=True)
        with archive.open(Z2D_BIN_ENTRY) as stream:
            for row in ranges:
                stream.seek(int(row["offset"]))
                data = stream.read(int(row["size"]))
                if len(data) != int(row["size"]):
                    raise ExtractionError(f"short Z2D read: {row['name']}")
                target = output_dir / f"{row['name']}.z2d"
                target.write_bytes(data)
                row["output_path"] = str(target.resolve())
                references, reference_status = extract_optional_dgm_references(target)
                row["dgm_references"] = references
                row["dgm_reference_status"] = reference_status
    report = {
        "schema": "magireco-exact-apk-named-z2d-extraction-v1",
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
            "inherited_sha256": "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF",
            "name_table_file_offset_hex": f"0x{NAME_TABLE_OFFSET:x}",
            "name_count": len(names),
        },
        "apk": {
            "path": str(apk.resolve()),
            "z2d_bin_entry": Z2D_BIN_ENTRY,
            "z2d_bin_size": z2d_info.file_size,
            "z2d_bin_zip_crc32": f"{z2d_info.CRC:08X}",
            "z2d_add_entry": Z2D_ADD_ENTRY,
            "z2d_add_size": add_info.file_size,
            "z2d_add_zip_crc32": f"{add_info.CRC:08X}",
            "physical_chunk_count": len(offsets) - 1,
        },
        "chunks": ranges,
        "assertions": {
            "native_name_count_matches_physical_chunks": len(names) == len(offsets) - 1,
            "all_requested_names_resolved_exactly_once": len(ranges)
            == len(target_names),
            "media_reencoded": False,
            "machine_vision_used_as_authority": False,
        },
    }
    (output_dir / "NAMED_Z2D_CHUNKS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--name", action="append", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = extract(
        apk=args.apk,
        binary=args.binary,
        target_names=args.name,
        output_dir=args.output_dir,
    )
    print(
        f"PASS named_z2d={len(report['chunks'])} "
        f"physical_chunks={report['apk']['physical_chunk_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
