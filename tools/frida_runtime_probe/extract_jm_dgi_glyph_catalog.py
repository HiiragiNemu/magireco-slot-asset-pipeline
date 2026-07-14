#!/usr/bin/env python3
"""Audit and optionally export the game's ``JM_*`` DGI glyph resources.

The source archives are always opened read-only.  With no output arguments the
command performs a complete audit and prints only a summary.  JSON, CSV, and
standard ASTC containers are written only when their respective output paths
are explicitly supplied.

This tool deliberately does not invent typography metrics.  The DMP resource
header contains an intrinsic texture size but no advance, bearing, baseline,
anchor, or layer transform.  Those authored placement values belong to Z2D
scene data and must be audited separately.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from magireco_asset_pipeline import (  # noqa: E402
    read_native_relative_name_table,
    read_ordered_offsets,
)


DGI_NATIVE_NAME_TABLE_OFFSET = 0x1461600
DGI_NATIVE_NAME_COUNT = 5785
DMP_HEADER = struct.Struct("<4sIIIHHIIHH")
DMP_MAGIC = b"DMP "
DMP_ASTC_4X4_FORMAT_CODE = 0x001D
ASTC_MAGIC = b"\x13\xAB\xA1\x5C"
ASTC_BLOCK = (4, 4, 1)
ASTC_HEADER_SIZE = 16
ASTC_BLOCK_BYTES = 16
MISSING_COVERAGE_EXIT = 3

DEFAULT_NATIVE_LIB = REPO_ROOT / "unpacked_lib" / "lib" / "arm64-v8a" / "libGameProc.so"
DEFAULT_DGI_BIN = REPO_ROOT / "unpacked_assets" / "assets" / "dgi.bin"
DEFAULT_DGI_ADD = REPO_ROOT / "unpacked_assets" / "assets" / "dgi_add.bin"

JM_DGI_NAME_RE = re.compile(
    r"^JM_(?P<codepoint>[0-9A-Fa-f]{4,6})_"
    r"(?P<family>[^_]+)_(?P<variant>[^_]+)$"
)


@dataclass(frozen=True)
class DmpHeader:
    """The 32-byte header used by the audited JM DGI resources."""

    magic: bytes
    data_offset: int
    reserved_u32_0: int
    reserved_u32_1: int
    width: int
    height: int
    reserved_u32_2: int
    data_size: int
    format_code: int
    image_count: int

    @property
    def expected_astc_payload_size(self) -> int:
        block_x, block_y, block_z = ASTC_BLOCK
        return (
            math.ceil(self.width / block_x)
            * math.ceil(self.height / block_y)
            * math.ceil(1 / block_z)
            * ASTC_BLOCK_BYTES
        )


def parse_int(value: str) -> int:
    """Parse a decimal or ``0x``-prefixed command-line integer."""

    return int(value, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(block_size):
            digest.update(block)
    return digest.hexdigest().upper()


def parse_dmp_header(blob: bytes) -> DmpHeader:
    """Parse and strictly validate one JM glyph DMP resource."""

    if len(blob) < DMP_HEADER.size:
        raise ValueError(
            f"DMP resource is shorter than its {DMP_HEADER.size}-byte header: {len(blob)}"
        )
    header = DmpHeader(*DMP_HEADER.unpack_from(blob, 0))
    if header.magic != DMP_MAGIC:
        raise ValueError(f"unexpected DMP magic: {header.magic!r}")
    if header.data_offset < DMP_HEADER.size:
        raise ValueError(f"DMP data offset overlaps its header: {header.data_offset}")
    if header.width <= 0 or header.height <= 0:
        raise ValueError(f"invalid DMP dimensions: {header.width}x{header.height}")
    if header.data_offset + header.data_size != len(blob):
        raise ValueError(
            "DMP payload boundary does not match chunk size: "
            f"offset={header.data_offset}, data_size={header.data_size}, chunk={len(blob)}"
        )
    if header.format_code != DMP_ASTC_4X4_FORMAT_CODE:
        raise ValueError(
            f"unsupported JM DMP format 0x{header.format_code:04X}; expected ASTC 4x4 code 0x001D"
        )
    if header.image_count != 1:
        raise ValueError(f"unsupported JM DMP image count: {header.image_count}")
    if header.data_size != header.expected_astc_payload_size:
        raise ValueError(
            "ASTC 4x4 payload size disagrees with DMP dimensions: "
            f"expected={header.expected_astc_payload_size}, actual={header.data_size}"
        )
    return header


def _u24le(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFF:
        raise ValueError(f"ASTC dimension is outside unsigned 24-bit range: {value}")
    return value.to_bytes(3, "little")


def build_astc_container(header: DmpHeader, payload: bytes) -> bytes:
    """Wrap a validated DMP ASTC payload in the standard 16-byte ASTC header."""

    if header.format_code != DMP_ASTC_4X4_FORMAT_CODE:
        raise ValueError(f"DMP format 0x{header.format_code:04X} is not ASTC 4x4")
    if len(payload) != header.data_size:
        raise ValueError(
            f"ASTC payload length mismatch: expected={header.data_size}, actual={len(payload)}"
        )
    if header.data_size != header.expected_astc_payload_size:
        raise ValueError(
            "ASTC payload size disagrees with dimensions: "
            f"expected={header.expected_astc_payload_size}, actual={header.data_size}"
        )
    block_x, block_y, block_z = ASTC_BLOCK
    astc_header = (
        ASTC_MAGIC
        + bytes((block_x, block_y, block_z))
        + _u24le(header.width)
        + _u24le(header.height)
        + _u24le(1)
    )
    if len(astc_header) != ASTC_HEADER_SIZE:
        raise AssertionError(f"internal ASTC header size error: {len(astc_header)}")
    return astc_header + payload


def _record_from_chunk(
    *,
    archive_index: int,
    resource_name: str,
    archive_offset: int,
    chunk: bytes,
    codepoint: int,
    family: str,
    variant: str,
) -> dict[str, Any]:
    header = parse_dmp_header(chunk)
    payload = chunk[header.data_offset : header.data_offset + header.data_size]
    return {
        "archive_index": archive_index,
        "resource_name": resource_name,
        "codepoint_hex": f"U+{codepoint:04X}",
        "codepoint_int": codepoint,
        "character": chr(codepoint),
        "family": family,
        "variant": variant,
        "archive_offset": archive_offset,
        "chunk_size": len(chunk),
        "chunk_sha256": sha256_bytes(chunk),
        "payload_sha256": sha256_bytes(payload),
        "dmp_magic_ascii": header.magic.decode("ascii"),
        "dmp_data_offset": header.data_offset,
        "dmp_reserved_u32_0": header.reserved_u32_0,
        "dmp_reserved_u32_1": header.reserved_u32_1,
        "dmp_width": header.width,
        "dmp_height": header.height,
        "dmp_reserved_u32_2": header.reserved_u32_2,
        "dmp_data_size": header.data_size,
        "dmp_format_code": header.format_code,
        "dmp_format_hex": f"0x{header.format_code:04X}",
        "dmp_image_count": header.image_count,
        "astc_format": "RGBA_ASTC_4x4",
        "astc_block_x": ASTC_BLOCK[0],
        "astc_block_y": ASTC_BLOCK[1],
        "astc_block_z": ASTC_BLOCK[2],
        "astc_width": header.width,
        "astc_height": header.height,
        "astc_depth": 1,
        "astc_payload_size": len(payload),
        "astc_container_size": ASTC_HEADER_SIZE + len(payload),
        "astc_relative_path": "",
        "typography_metrics_present": False,
    }


def read_dgi_catalog(
    native_lib: Path,
    dgi_bin: Path,
    dgi_add: Path,
    *,
    name_table_offset: int = DGI_NATIVE_NAME_TABLE_OFFSET,
    name_count: int = DGI_NATIVE_NAME_COUNT,
) -> list[dict[str, Any]]:
    """Read every JM glyph through the native name table and ordered offsets."""

    native_lib = Path(native_lib)
    dgi_bin = Path(dgi_bin)
    dgi_add = Path(dgi_add)
    for source in (native_lib, dgi_bin, dgi_add):
        if not source.is_file():
            raise FileNotFoundError(source)

    offsets = read_ordered_offsets(dgi_bin, dgi_add)
    names = read_native_relative_name_table(native_lib, name_table_offset, name_count)
    archive_entry_count = len(offsets) - 1
    if archive_entry_count != len(names):
        raise ValueError(
            "DGI name/offset count mismatch: "
            f"names={len(names)}, archive_entries={archive_entry_count}"
        )
    if len(names) != len(set(names)):
        raise ValueError("DGI native name table contains duplicate resource names")

    records: list[dict[str, Any]] = []
    with dgi_bin.open("rb") as archive:
        for archive_index, resource_name in enumerate(names):
            match = JM_DGI_NAME_RE.fullmatch(resource_name)
            if match is None:
                continue
            start = offsets[archive_index]
            end = offsets[archive_index + 1]
            if end <= start:
                raise ValueError(
                    f"JM DGI chunk {archive_index} has a non-positive span: {start}..{end}"
                )
            archive.seek(start)
            chunk = archive.read(end - start)
            if len(chunk) != end - start:
                raise ValueError(
                    f"short read for JM DGI chunk {archive_index}: "
                    f"expected={end-start}, actual={len(chunk)}"
                )
            codepoint = int(match.group("codepoint"), 16)
            if not 0 <= codepoint <= 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                raise ValueError(
                    f"invalid Unicode scalar in DGI name {resource_name!r}: 0x{codepoint:X}"
                )
            records.append(
                _record_from_chunk(
                    archive_index=archive_index,
                    resource_name=resource_name,
                    archive_offset=start,
                    chunk=chunk,
                    codepoint=codepoint,
                    family=match.group("family"),
                    variant=match.group("variant"),
                )
            )
    return records


def audit_text_coverage(
    records: Sequence[dict[str, Any]],
    texts: Iterable[str],
    *,
    ignore_whitespace: bool = True,
) -> dict[str, Any]:
    """Compare required Unicode scalars with the audited JM glyph catalog."""

    text_list = list(texts)
    required: Counter[int] = Counter()
    for text in text_list:
        for character in text:
            if ignore_whitespace and character.isspace():
                continue
            required[ord(character)] += 1

    available = {int(record["codepoint_int"]) for record in records}
    covered = sorted(required.keys() & available)
    missing = sorted(required.keys() - available)

    def describe(codepoint: int) -> dict[str, Any]:
        character = chr(codepoint)
        return {
            "codepoint_hex": f"U+{codepoint:04X}",
            "codepoint_int": codepoint,
            "character": character,
            "unicode_name": unicodedata.name(character, "UNNAMED"),
            "occurrences": required[codepoint],
        }

    return {
        "requested": bool(text_list),
        "ignore_whitespace": ignore_whitespace,
        "input_count": len(text_list),
        "required_occurrence_count": sum(required.values()),
        "required_unique_count": len(required),
        "covered_unique_count": len(covered),
        "missing_unique_count": len(missing),
        "covered_codepoints": [describe(codepoint) for codepoint in covered],
        "missing_codepoints": [describe(codepoint) for codepoint in missing],
        "passed": not missing,
    }


def _count_by(records: Sequence[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(record[field]) for record in records)
    return dict(sorted(counts.items()))


def _source_identity(path: Path, *, include_sha256: bool) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "path": str(path.resolve()),
        "size": path.stat().st_size,
    }
    if include_sha256:
        identity["sha256"] = sha256_file(path)
    return identity


def build_manifest(
    *,
    records: list[dict[str, Any]],
    native_lib: Path,
    dgi_bin: Path,
    dgi_add: Path,
    name_table_offset: int,
    name_count: int,
    coverage: dict[str, Any],
    include_source_hashes: bool = True,
) -> dict[str, Any]:
    """Build a deterministic, audit-oriented JSON manifest."""

    unique_codepoints = {int(record["codepoint_int"]) for record in records}
    return {
        "schema_version": 1,
        "kind": "magireco_jm_dgi_glyph_catalog",
        "sources": {
            "native_lib": _source_identity(Path(native_lib), include_sha256=include_source_hashes),
            "dgi_bin": _source_identity(Path(dgi_bin), include_sha256=include_source_hashes),
            "dgi_add": _source_identity(Path(dgi_add), include_sha256=include_source_hashes),
        },
        "parameters": {
            "native_name_table_file_offset": name_table_offset,
            "native_name_table_file_offset_hex": f"0x{name_table_offset:X}",
            "native_name_count": name_count,
            "dmp_header_struct": DMP_HEADER.format,
            "jm_name_regex": JM_DGI_NAME_RE.pattern,
        },
        "summary": {
            "glyph_record_count": len(records),
            "unique_codepoint_count": len(unique_codepoints),
            "family_counts": _count_by(records, "family"),
            "variant_counts": _count_by(records, "variant"),
            "intrinsic_size_counts": dict(
                sorted(
                    Counter(
                        f'{record["dmp_width"]}x{record["dmp_height"]}'
                        for record in records
                    ).items()
                )
            ),
            "astc_format": "RGBA_ASTC_4x4",
            "typography_metrics_present": False,
        },
        "coverage": coverage,
        "glyphs": records,
    }


CSV_FIELDS = [
    "archive_index",
    "resource_name",
    "codepoint_hex",
    "codepoint_int",
    "character",
    "family",
    "variant",
    "archive_offset",
    "chunk_size",
    "chunk_sha256",
    "payload_sha256",
    "dmp_magic_ascii",
    "dmp_data_offset",
    "dmp_reserved_u32_0",
    "dmp_reserved_u32_1",
    "dmp_width",
    "dmp_height",
    "dmp_reserved_u32_2",
    "dmp_data_size",
    "dmp_format_code",
    "dmp_format_hex",
    "dmp_image_count",
    "astc_format",
    "astc_block_x",
    "astc_block_y",
    "astc_block_z",
    "astc_width",
    "astc_height",
    "astc_depth",
    "astc_payload_size",
    "astc_container_size",
    "astc_relative_path",
    "typography_metrics_present",
]


def _ensure_output_is_not_source(output: Path, sources: Sequence[Path]) -> None:
    output_resolved = output.resolve()
    for source in sources:
        if output_resolved == source.resolve():
            raise ValueError(f"refusing to overwrite source asset: {output_resolved}")


def _prepare_output_file(path: Path, *, overwrite: bool, sources: Sequence[Path]) -> None:
    _ensure_output_is_not_source(path, sources)
    if path.exists() and not overwrite:
        raise FileExistsError(f"output already exists (use --overwrite-outputs): {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json_manifest(
    path: Path,
    manifest: dict[str, Any],
    *,
    overwrite: bool,
    sources: Sequence[Path],
) -> None:
    _prepare_output_file(path, overwrite=overwrite, sources=sources)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def write_csv_manifest(
    path: Path,
    records: Sequence[dict[str, Any]],
    *,
    overwrite: bool,
    sources: Sequence[Path],
) -> None:
    _prepare_output_file(path, overwrite=overwrite, sources=sources)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def select_astc_records(
    records: Sequence[dict[str, Any]],
    *,
    requested_names: Sequence[str],
    limit: int | None,
) -> list[dict[str, Any]]:
    by_name = {str(record["resource_name"]): record for record in records}
    if requested_names:
        unknown = sorted(set(requested_names) - by_name.keys())
        if unknown:
            raise ValueError(f"requested ASTC glyph names are absent: {', '.join(unknown)}")
        requested = set(requested_names)
        selected = [record for record in records if record["resource_name"] in requested]
    else:
        selected = list(records)
    if limit is not None:
        if limit < 0:
            raise ValueError("--astc-limit must be non-negative")
        selected = selected[:limit]
    return selected


def export_astc_files(
    *,
    records: Sequence[dict[str, Any]],
    dgi_bin: Path,
    output_dir: Path,
    overwrite: bool,
    source_paths: Sequence[Path],
) -> dict[str, str]:
    """Export selected records without decoding or modifying the DGI archive."""

    output_dir = Path(output_dir)
    _ensure_output_is_not_source(output_dir, source_paths)
    relative_paths: dict[str, str] = {}
    with Path(dgi_bin).open("rb") as archive:
        for record in records:
            archive.seek(int(record["archive_offset"]))
            chunk = archive.read(int(record["chunk_size"]))
            if sha256_bytes(chunk) != record["chunk_sha256"]:
                raise ValueError(f"DGI chunk changed during export: {record['resource_name']}")
            header = parse_dmp_header(chunk)
            payload = chunk[header.data_offset : header.data_offset + header.data_size]
            container = build_astc_container(header, payload)
            relative = (
                Path(str(record["family"]))
                / str(record["variant"])
                / f"{record['resource_name']}.astc"
            )
            destination = output_dir / relative
            _prepare_output_file(destination, overwrite=overwrite, sources=source_paths)
            destination.write_bytes(container)
            relative_paths[str(record["resource_name"])] = relative.as_posix()
    return relative_paths


def _read_coverage_inputs(texts: Sequence[str], files: Sequence[Path]) -> list[str]:
    values = list(texts)
    for path in files:
        values.append(Path(path).read_text(encoding="utf-8-sig"))
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-lib", type=Path, default=DEFAULT_NATIVE_LIB)
    parser.add_argument("--dgi-bin", type=Path, default=DEFAULT_DGI_BIN)
    parser.add_argument("--dgi-add", type=Path, default=DEFAULT_DGI_ADD)
    parser.add_argument(
        "--name-table-offset",
        type=parse_int,
        default=DGI_NATIVE_NAME_TABLE_OFFSET,
        help="libGameProc.so file offset of the DGI relative-name table",
    )
    parser.add_argument("--name-count", type=int, default=DGI_NATIVE_NAME_COUNT)
    parser.add_argument("--coverage-text", action="append", default=[])
    parser.add_argument("--coverage-file", action="append", type=Path, default=[])
    parser.add_argument(
        "--include-whitespace",
        action="store_true",
        help="treat whitespace as required glyphs during coverage auditing",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument(
        "--astc-dir",
        type=Path,
        help="explicitly export standard ASTC containers; omitted in default dry-run",
    )
    parser.add_argument(
        "--astc-name",
        action="append",
        default=[],
        help="exact JM resource name to export; repeat for a small audited batch",
    )
    parser.add_argument("--astc-limit", type=int)
    parser.add_argument(
        "--skip-source-hashes",
        action="store_true",
        help="omit whole-file hashes from JSON (per-glyph hashes are always recorded)",
    )
    parser.add_argument(
        "--overwrite-outputs",
        action="store_true",
        help="replace generated outputs only; source assets are always protected",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    sources = [Path(args.native_lib), Path(args.dgi_bin), Path(args.dgi_add)]
    records = read_dgi_catalog(
        sources[0],
        sources[1],
        sources[2],
        name_table_offset=args.name_table_offset,
        name_count=args.name_count,
    )
    coverage_inputs = _read_coverage_inputs(args.coverage_text, args.coverage_file)
    coverage = audit_text_coverage(
        records,
        coverage_inputs,
        ignore_whitespace=not args.include_whitespace,
    )

    exported_paths: dict[str, str] = {}
    if args.astc_dir is not None:
        selected = select_astc_records(
            records,
            requested_names=args.astc_name,
            limit=args.astc_limit,
        )
        exported_paths = export_astc_files(
            records=selected,
            dgi_bin=sources[1],
            output_dir=args.astc_dir,
            overwrite=args.overwrite_outputs,
            source_paths=sources,
        )
        for record in records:
            record["astc_relative_path"] = exported_paths.get(
                str(record["resource_name"]), ""
            )

    manifest = build_manifest(
        records=records,
        native_lib=sources[0],
        dgi_bin=sources[1],
        dgi_add=sources[2],
        name_table_offset=args.name_table_offset,
        name_count=args.name_count,
        coverage=coverage,
        include_source_hashes=not args.skip_source_hashes,
    )
    manifest["summary"]["exported_astc_count"] = len(exported_paths)

    if args.json_out is not None:
        write_json_manifest(
            args.json_out,
            manifest,
            overwrite=args.overwrite_outputs,
            sources=sources,
        )
    if args.csv_out is not None:
        write_csv_manifest(
            args.csv_out,
            records,
            overwrite=args.overwrite_outputs,
            sources=sources,
        )

    print(
        "[jm-dgi] "
        f"glyphs={len(records)} "
        f"unique_codepoints={manifest['summary']['unique_codepoint_count']} "
        f"families={manifest['summary']['family_counts']}"
    )
    if coverage["requested"]:
        print(
            "[coverage] "
            f"required={coverage['required_unique_count']} "
            f"covered={coverage['covered_unique_count']} "
            f"missing={coverage['missing_unique_count']} "
            f"passed={coverage['passed']}"
        )
        if coverage["missing_codepoints"]:
            missing = ", ".join(
                str(row["codepoint_hex"]) for row in coverage["missing_codepoints"]
            )
            print(f"[coverage] missing codepoints: {missing}", file=sys.stderr)
    if args.json_out is None and args.csv_out is None and args.astc_dir is None:
        print("[dry-run] audit complete; no output path was supplied, so no files were written")

    return MISSING_COVERAGE_EXIT if coverage["missing_unique_count"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
