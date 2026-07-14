#!/usr/bin/env python3
"""Extract the static ``fnLot_OT_AT_SpStryKnd`` lottery tables.

The native routine selects one of five 16-byte descriptors at a fixed virtual
address.  Each descriptor contains relocated pointers to a weighted table and
its audit label.  Weighted table entries are ``(weight u64, result u64)`` and
end at the ``weight == 0x8000`` sentinel.  The routine stores ``result + 9`` as
the resulting SP story kind.

This extractor deliberately reports the table mechanics only.  It does not
infer an ``ac`` event from a numeric suffix or from visual similarity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


# ``decode_dirinfo_event_tables.py`` was originally written as a directly
# executable script and imports a sibling module by its bare name.  Adding the
# tool directory keeps both direct execution and repository-root imports
# working while reusing its audited ELF/RELA helpers unchanged.
TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from decode_dirinfo_event_tables import (  # noqa: E402
    elf_sections,
    load_relocation_values,
    load_symbol_tables,
    read_relocated_u64,
    read_string_at,
    vaddr_to_file_offset,
    write_csv,
)


DEFAULT_TABLE_ARRAY_ADDRESS = 0x4B28E60
DEFAULT_TABLE_COUNT = 5
DEFAULT_DENOMINATOR = 0x8000
DEFAULT_SENTINEL_WEIGHT = 0x8000
DEFAULT_MAX_ENTRIES = 256
ENTRY_SIZE = 16
DESCRIPTOR_SIZE = 16


def parse_int(value: str) -> int:
    """Parse decimal or ``0x``-prefixed command-line integers."""

    return int(value, 0)


def decode_lottery_table_bytes(
    data: bytes,
    *,
    denominator: int = DEFAULT_DENOMINATOR,
    sentinel_weight: int = DEFAULT_SENTINEL_WEIGHT,
    result_kind_offset: int = 9,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> dict[str, Any]:
    """Decode one weighted table from bytes without filesystem dependencies.

    The sentinel is not a weighted outcome.  Its location and result field are
    retained separately so callers can audit that parsing stopped at the
    expected native terminator.  A missing sentinel is rejected instead of
    silently treating unrelated adjacent data as lottery entries.
    """

    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if max_entries <= 0:
        raise ValueError("max_entries must be positive")

    available_entries = min(len(data) // ENTRY_SIZE, max_entries)
    entries: list[dict[str, Any]] = []
    for entry_index in range(available_entries):
        entry_offset = entry_index * ENTRY_SIZE
        weight, result = struct.unpack_from("<QQ", data, entry_offset)
        if weight == sentinel_weight:
            weight_total = sum(int(row["weight"]) for row in entries)
            return {
                "entries": entries,
                "entry_count": len(entries),
                "weight_total": weight_total,
                "probability_total": weight_total / denominator,
                "sentinel": {
                    "entry_index": entry_index,
                    "byte_offset": entry_offset,
                    "weight": weight,
                    "result": result,
                },
            }
        entries.append(
            {
                "entry_index": entry_index,
                "byte_offset": entry_offset,
                "weight": weight,
                "weight_hex": f"0x{weight:x}",
                "result": result,
                "kind": result + result_kind_offset,
                "probability": weight / denominator,
            }
        )

    if len(data) < ENTRY_SIZE:
        detail = f"only {len(data)} byte(s) available"
    elif len(data) // ENTRY_SIZE > max_entries:
        detail = f"not found within max_entries={max_entries}"
    else:
        detail = f"not found in {available_entries} complete entry/entries"
    raise ValueError(f"lottery table sentinel 0x{sentinel_weight:x} {detail}")


def read_table_bytes(
    blob: bytes,
    sections: list[dict[str, Any]],
    table_address: int,
    *,
    max_entries: int,
) -> bytes:
    """Read at most ``max_entries`` complete entries from the mapped section."""

    table_offset = vaddr_to_file_offset(sections, table_address)
    containing_section = next(
        section
        for section in sections
        if int(section["addr"]) <= table_address
        < int(section["addr"]) + int(section["size"])
    )
    section_file_end = int(containing_section["offset"]) + int(containing_section["size"])
    requested_end = table_offset + max_entries * ENTRY_SIZE
    return blob[table_offset : min(section_file_end, requested_end)]


def extract_tables(
    blob: bytes,
    *,
    table_array_address: int = DEFAULT_TABLE_ARRAY_ADDRESS,
    table_count: int = DEFAULT_TABLE_COUNT,
    denominator: int = DEFAULT_DENOMINATOR,
    sentinel_weight: int = DEFAULT_SENTINEL_WEIGHT,
    result_kind_offset: int = 9,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> list[dict[str, Any]]:
    """Resolve descriptors and decode all configured lottery tables."""

    if table_count <= 0:
        raise ValueError("table_count must be positive")

    sections = elf_sections(blob)
    symbol_tables = load_symbol_tables(blob, sections)
    relocations = load_relocation_values(blob, sections, symbol_tables)
    tables: list[dict[str, Any]] = []
    for table_index in range(table_count):
        descriptor_address = table_array_address + table_index * DESCRIPTOR_SIZE
        table_pointer = read_relocated_u64(
            blob, sections, relocations, descriptor_address
        )
        label_pointer = read_relocated_u64(
            blob, sections, relocations, descriptor_address + 8
        )
        if table_pointer == 0:
            raise ValueError(
                f"table {table_index} has a null pointer at 0x{descriptor_address:x}"
            )
        decoded = decode_lottery_table_bytes(
            read_table_bytes(
                blob,
                sections,
                table_pointer,
                max_entries=max_entries,
            ),
            denominator=denominator,
            sentinel_weight=sentinel_weight,
            result_kind_offset=result_kind_offset,
            max_entries=max_entries,
        )
        tables.append(
            {
                "table_index": table_index,
                "descriptor_address": f"0x{descriptor_address:x}",
                "table_pointer": f"0x{table_pointer:x}",
                "label_pointer": f"0x{label_pointer:x}" if label_pointer else "",
                "label": read_string_at(blob, sections, label_pointer),
                **decoded,
            }
        )
    return tables


def flatten_table_rows(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten decoded JSON table objects into auditable CSV rows."""

    rows: list[dict[str, Any]] = []
    for table in tables:
        for entry in table["entries"]:
            rows.append(
                {
                    "table_index": table["table_index"],
                    "label": table["label"],
                    "descriptor_address": table["descriptor_address"],
                    "table_pointer": table["table_pointer"],
                    "entry_index": entry["entry_index"],
                    "entry_address": f"0x{int(table['table_pointer'], 0) + int(entry['byte_offset']):x}",
                    "weight": entry["weight"],
                    "weight_hex": entry["weight_hex"],
                    "result": entry["result"],
                    "kind": entry["kind"],
                    "probability": entry["probability"],
                    "probability_percent": entry["probability"] * 100,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract static fnLot_OT_AT_SpStryKnd weighted tables."
    )
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--table-array-address",
        type=parse_int,
        default=DEFAULT_TABLE_ARRAY_ADDRESS,
    )
    parser.add_argument("--table-count", type=int, default=DEFAULT_TABLE_COUNT)
    parser.add_argument("--denominator", type=parse_int, default=DEFAULT_DENOMINATOR)
    parser.add_argument(
        "--sentinel-weight", type=parse_int, default=DEFAULT_SENTINEL_WEIGHT
    )
    parser.add_argument("--result-kind-offset", type=int, default=9)
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    args = parser.parse_args()

    blob = args.lib.read_bytes()
    tables = extract_tables(
        blob,
        table_array_address=args.table_array_address,
        table_count=args.table_count,
        denominator=args.denominator,
        sentinel_weight=args.sentinel_weight,
        result_kind_offset=args.result_kind_offset,
        max_entries=args.max_entries,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.out_dir / "sp_story_kind_lottery_tables.json"
    csv_path = args.out_dir / "sp_story_kind_lottery_entries.csv"
    document = {
        "schema_version": 1,
        "lib": str(args.lib.resolve()),
        "lib_sha256": hashlib.sha256(blob).hexdigest(),
        "table_array_address": f"0x{args.table_array_address:x}",
        "table_count": args.table_count,
        "descriptor_size": DESCRIPTOR_SIZE,
        "entry_layout": "weight_u64_le,result_u64_le",
        "sentinel_weight": args.sentinel_weight,
        "denominator": args.denominator,
        "result_kind_offset": args.result_kind_offset,
        "tables": tables,
    }
    json_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(
        csv_path,
        flatten_table_rows(tables),
        [
            "table_index",
            "label",
            "descriptor_address",
            "table_pointer",
            "entry_index",
            "entry_address",
            "weight",
            "weight_hex",
            "result",
            "kind",
            "probability",
            "probability_percent",
        ],
    )

    print(
        json.dumps(
            {
                "ok": True,
                "lib_sha256": document["lib_sha256"],
                "table_count": len(tables),
                "entry_count": sum(table["entry_count"] for table in tables),
                "json": str(json_path),
                "csv": str(csv_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
