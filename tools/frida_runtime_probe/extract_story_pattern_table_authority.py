#!/usr/bin/env python3
"""Extract exported StageAT story pattern tables from the exact Slot ELF.

This is intentionally narrower than ``decode_dirinfo_event_tables.py``.  The
StageAT story dispatcher uses exported ``ptnTbl_acXXXX`` grids whose cells are
event-code qwords rather than EventInfo indices.  Some exported grids are not
referenced by the current dispatcher; those must remain distinct from
statically reachable story families.

The extractor records both facts:

* which unique event codes exist in each 9-selector grid; and
* whether executable code has a PC-relative reference to the table or its
  exported ``*_ptr`` relocation slot.

An exported table with no executable reference is evidence that media/event
codes exist, but it is not evidence that the current build can dispatch it.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import struct
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .survey_aarch64_xrefs import (
        elf_sections,
        load_symbols,
        read_cstring,
        scan_absolute_data_refs,
        scan_pc_relative_refs,
        vaddr_to_file_offset,
    )
except ImportError:  # Direct script execution from tools/frida_runtime_probe.
    from survey_aarch64_xrefs import (
        elf_sections,
        load_symbols,
        read_cstring,
        scan_absolute_data_refs,
        scan_pc_relative_refs,
        vaddr_to_file_offset,
    )


SELECTOR_COUNT = 9
CELL_SIZE = 8
ROW_SIZE = SELECTOR_COUNT * CELL_SIZE
DEFAULT_DISPATCHER_SYMBOL = "_ZN18C_ObjStageAT_Story14fnSetEventCodeEv"
SHT_RELA = 4
SHT_SYMTAB = 2
SHT_DYNSYM = 11
R_AARCH64_RELATIVE = 0x403


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return f"0x{int(text, 0):016x}"
    except ValueError:
        return text.lower()


def symbol_by_name(symbols: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [row for row in symbols if row.get("name") == name]
    if not matches:
        raise ValueError(f"symbol not found: {name}")
    return max(
        matches,
        key=lambda row: (int(row.get("size") or 0), int(row.get("address") or 0)),
    )


def load_manifest_code_map(roots: list[Path]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, set[str]]] = {}
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.json")
        for path in paths:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            code = normalize_code(doc.get("event_code_hex") or doc.get("code_hex"))
            event = str(doc.get("event") or doc.get("label") or "").strip()
            if not event and path.parent.name == "events":
                event = path.stem
            if not code or not event:
                continue
            bucket = buckets.setdefault(code, {"events": set(), "sources": set()})
            bucket["events"].add(event)
            bucket["sources"].add(str(path))
    return {
        code: {
            "events": sorted(value["events"]),
            "sources": sorted(value["sources"]),
            "source_count": len(value["sources"]),
        }
        for code, value in buckets.items()
    }


def load_symbol_tables(
    blob: bytes, sections: list[dict[str, Any]]
) -> dict[int, list[dict[str, Any]]]:
    tables: dict[int, list[dict[str, Any]]] = {}
    for section in sections:
        if int(section["type"]) not in {SHT_SYMTAB, SHT_DYNSYM}:
            continue
        entsize = int(section.get("entsize") or 24)
        if entsize < 24:
            continue
        strtab = sections[int(section["link"])]
        strings = blob[
            int(strtab["offset"]) : int(strtab["offset"]) + int(strtab["size"])
        ]
        rows: list[dict[str, Any]] = []
        for symbol_index, offset in enumerate(
            range(
                int(section["offset"]),
                int(section["offset"]) + int(section["size"]),
                entsize,
            )
        ):
            if offset + 24 > len(blob):
                break
            st_name, _st_info, _st_other, _st_shndx, st_value, _st_size = struct.unpack_from(
                "<IBBHQQ", blob, offset
            )
            rows.append(
                {
                    "index": symbol_index,
                    "name": read_cstring(strings, st_name) if st_name else "",
                    "address": st_value,
                }
            )
        tables[int(section["index"])] = rows
    return tables


def load_relocation_values(
    blob: bytes,
    sections: list[dict[str, Any]],
    symbol_tables: dict[int, list[dict[str, Any]]],
) -> dict[int, int]:
    """Return ELF relocation slot -> resolved target mappings."""
    values: dict[int, int] = {}
    for section in sections:
        if int(section["type"]) != SHT_RELA:
            continue
        entsize = int(section.get("entsize") or 24)
        if entsize < 24:
            continue
        for offset in range(
            int(section["offset"]),
            int(section["offset"]) + int(section["size"]),
            entsize,
        ):
            if offset + 24 > len(blob):
                break
            r_offset, r_info, r_addend = struct.unpack_from("<QQq", blob, offset)
            r_type = r_info & 0xFFFFFFFF
            symbol_index = r_info >> 32
            if r_type == R_AARCH64_RELATIVE:
                values[r_offset] = r_addend & 0xFFFFFFFFFFFFFFFF
            else:
                linked_symbols = symbol_tables.get(int(section["link"]), [])
                if 0 < symbol_index < len(linked_symbols):
                    values[r_offset] = (
                        int(linked_symbols[symbol_index]["address"]) + r_addend
                    ) & 0xFFFFFFFFFFFFFFFF
    return values


def code_ascii_le(value: int) -> str:
    raw = value.to_bytes(8, "little", signed=False)
    return "".join(chr(byte) if 0x20 <= byte < 0x7F else "." for byte in raw)


def decode_pattern_table(
    blob: bytes,
    *,
    table_offset: int,
    table_size: int,
    selector_count: int = SELECTOR_COUNT,
) -> list[dict[str, Any]]:
    row_size = selector_count * CELL_SIZE
    if table_size <= 0 or table_size % row_size:
        raise ValueError(
            f"pattern table size {table_size} is not divisible by row size {row_size}"
        )
    if table_offset < 0 or table_offset + table_size > len(blob):
        raise ValueError("pattern table is outside the ELF file")

    rows: list[dict[str, Any]] = []
    row_count = table_size // row_size
    for row_index in range(row_count):
        for selector_raw in range(selector_count):
            relative_offset = row_index * row_size + selector_raw * CELL_SIZE
            value = struct.unpack_from("<Q", blob, table_offset + relative_offset)[0]
            rows.append(
                {
                    "row_index": row_index,
                    "selector_raw": selector_raw,
                    "selector_1based": selector_raw + 1,
                    "relative_offset": relative_offset,
                    "code_hex": f"0x{value:016x}",
                    "code_ascii_le": code_ascii_le(value) if value else "",
                    "is_zero": value == 0,
                }
            )
    return rows


def classify_static_reachability(
    *, pointer_symbol_present: bool, executable_reference_count: int
) -> str:
    if executable_reference_count > 0:
        return "active_dispatcher_static_reference"
    if pointer_symbol_present:
        return "pointer_export_present_but_no_executable_reference"
    return "orphan_exported_pattern_table_no_executable_reference"


def standard_three_event_bindings(
    rows: list[dict[str, Any]], family: str
) -> dict[str, str]:
    """Bind the canonical 20x9 StageAT layout to _001/_002/_003 events."""
    nonzero_by_code: dict[str, set[tuple[int, int]]] = {}
    for row in rows:
        if row["is_zero"]:
            continue
        nonzero_by_code.setdefault(str(row["code_hex"]), set()).add(
            (int(row["row_index"]), int(row["selector_raw"]))
        )
    expected_cells = [
        ({(row, 0) for row in range(0, 10)}, f"{family}_001"),
        ({(row, 0) for row in range(10, 20)}, f"{family}_002"),
        ({(19, 5)}, f"{family}_003"),
    ]
    bindings: dict[str, str] = {}
    for expected, event in expected_cells:
        matches = [code for code, cells in nonzero_by_code.items() if cells == expected]
        if len(matches) != 1:
            return {}
        bindings[matches[0]] = event
    return bindings if len(bindings) == 3 else {}


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--family", action="append", required=True)
    parser.add_argument("--manifest-root", action="append", default=[], type=Path)
    parser.add_argument(
        "--authority-sha256",
        default="",
        help="Previously verified exact-binary SHA-256 provenance; not recomputed here.",
    )
    parser.add_argument(
        "--authority-source",
        default="",
        help="Path/name of the existing record that verified authority-sha256.",
    )
    parser.add_argument("--dispatcher-symbol", default=DEFAULT_DISPATCHER_SYMBOL)
    args = parser.parse_args()

    blob = args.lib.read_bytes()
    sections = elf_sections(blob)
    symbols = load_symbols(blob, sections)
    symbol_tables = load_symbol_tables(blob, sections)
    relocation_values = load_relocation_values(blob, sections, symbol_tables)
    relocation_slots_by_target: dict[int, list[int]] = {}
    for slot, target in relocation_values.items():
        relocation_slots_by_target.setdefault(target, []).append(slot)
    manifest_map = load_manifest_code_map(args.manifest_root)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_cell_rows: list[dict[str, Any]] = []
    all_unique_rows: list[dict[str, Any]] = []
    family_summaries: list[dict[str, Any]] = []

    selected: list[dict[str, Any]] = []
    scan_targets: dict[int, str] = {}
    for requested_family in args.family:
        family = requested_family.strip().lower()
        table_name = f"ptnTbl_{family}"
        pointer_name = f"{table_name}_ptr"
        table_symbol = symbol_by_name(symbols, table_name)
        pointer_matches = [row for row in symbols if row.get("name") == pointer_name]
        pointer_slots = sorted(
            relocation_slots_by_target.get(int(table_symbol["address"]), [])
        )
        selected.append(
            {
                "family": family,
                "table_name": table_name,
                "pointer_name": pointer_name,
                "table_symbol": table_symbol,
                "pointer_matches": pointer_matches,
                "pointer_slots": pointer_slots,
            }
        )
        scan_targets[int(table_symbol["address"])] = table_name
        if pointer_matches:
            scan_targets[int(pointer_matches[0]["address"])] = pointer_name
        for pointer_slot in pointer_slots:
            scan_targets[pointer_slot] = pointer_name

    # Also scan every exported story-pattern pointer once so the dispatcher
    # family set is derived from code rather than copied from a prior report.
    all_story_tables: dict[int, str] = {}
    for symbol in symbols:
        name = str(symbol.get("name") or "")
        if re.fullmatch(r"ptnTbl_ac\d{4}_ptr", name):
            scan_targets[int(symbol["address"])] = name
        match = re.fullmatch(r"ptnTbl_(ac\d{4})", name)
        if match:
            all_story_tables[int(symbol["address"])] = match.group(1)
    for table_address, family in all_story_tables.items():
        for pointer_slot in relocation_slots_by_target.get(table_address, []):
            scan_targets[pointer_slot] = f"ptnTbl_{family}_ptr"
    executable_refs_all = scan_pc_relative_refs(blob, sections, symbols, scan_targets)
    table_targets = {
        int(item["table_symbol"]["address"]): str(item["table_name"])
        for item in selected
    }
    absolute_refs_all = scan_absolute_data_refs(blob, sections, table_targets)
    dispatcher = symbol_by_name(symbols, args.dispatcher_symbol)
    dispatcher_supported_families = sorted(
        {
            match.group(1)
            for row in executable_refs_all
            if row.get("caller_symbol") == args.dispatcher_symbol
            for match in [re.fullmatch(r"ptnTbl_(ac\d{4})_ptr", str(row.get("target_name") or ""))]
            if match
        }
    )

    for item in selected:
        family = str(item["family"])
        table_name = str(item["table_name"])
        pointer_name = str(item["pointer_name"])
        table_symbol = item["table_symbol"]
        pointer_matches = item["pointer_matches"]
        pointer_slots = item["pointer_slots"]
        table_address = int(table_symbol["address"])
        table_size = int(table_symbol["size"])
        table_offset = vaddr_to_file_offset(sections, table_address)
        decoded = decode_pattern_table(
            blob,
            table_offset=table_offset,
            table_size=table_size,
        )

        own_target_names = {table_name, pointer_name}
        executable_refs = [
            row for row in executable_refs_all if row.get("target_name") in own_target_names
        ]
        absolute_refs = [
            row for row in absolute_refs_all if row.get("target_name") == table_name
        ]
        nonzero = [row for row in decoded if not row["is_zero"]]
        counts = Counter(str(row["code_hex"]) for row in nonzero)
        structural_bindings = standard_three_event_bindings(decoded, family)

        for row in decoded:
            resolved = manifest_map.get(normalize_code(row["code_hex"]), {})
            all_cell_rows.append(
                {
                    "family": family,
                    "table_symbol": table_name,
                    "table_address": f"0x{table_address:x}",
                    "table_file_offset": f"0x{table_offset:x}",
                    **row,
                    "resolved_events": ";".join(resolved.get("events", [])),
                    "resolved_source_count": resolved.get("source_count", 0),
                }
            )

        for code_hex, occurrence_count in sorted(counts.items()):
            exemplar = next(row for row in nonzero if row["code_hex"] == code_hex)
            cells = [
                f"{row['row_index']}:{row['selector_raw']}"
                for row in nonzero
                if row["code_hex"] == code_hex
            ]
            resolved = manifest_map.get(normalize_code(code_hex), {})
            all_unique_rows.append(
                {
                    "family": family,
                    "code_hex": code_hex,
                    "code_ascii_le": exemplar["code_ascii_le"],
                    "structural_event": structural_bindings.get(code_hex, ""),
                    "structural_binding_evidence": (
                        "exact_20x9_stageat_layout_isomorphic_to_active_ac7101_ac7108"
                        if code_hex in structural_bindings
                        else ""
                    ),
                    "occurrence_count": occurrence_count,
                    "cells_row_selector_raw": ";".join(cells),
                    "resolved_events": ";".join(resolved.get("events", [])),
                    "resolved_source_count": resolved.get("source_count", 0),
                }
            )

        reachability = classify_static_reachability(
            pointer_symbol_present=bool(pointer_matches or pointer_slots),
            executable_reference_count=len(executable_refs),
        )
        family_summaries.append(
            {
                "family": family,
                "table_symbol": table_name,
                "table_address": f"0x{table_address:x}",
                "table_file_offset": f"0x{table_offset:x}",
                "table_size": table_size,
                "row_count": table_size // ROW_SIZE,
                "selector_count": SELECTOR_COUNT,
                "nonzero_cell_count": len(nonzero),
                "unique_event_code_count": len(counts),
                "standard_three_event_layout": bool(structural_bindings),
                "structural_event_bindings": structural_bindings,
                "pointer_symbol": pointer_name if (pointer_matches or pointer_slots) else "",
                "pointer_slot_addresses": [f"0x{value:x}" for value in pointer_slots],
                "executable_reference_count": len(executable_refs),
                "executable_references": executable_refs,
                "absolute_data_references": absolute_refs,
                "static_dispatch_reachability": reachability,
                "production_gate": (
                    "event_inventory_only_runtime_reachability_not_established"
                    if reachability != "active_dispatcher_static_reference"
                    else "static_dispatch_reference_established_timing_still_independent"
                ),
            }
        )

    cell_fields = [
        "family",
        "table_symbol",
        "table_address",
        "table_file_offset",
        "row_index",
        "selector_raw",
        "selector_1based",
        "relative_offset",
        "code_hex",
        "code_ascii_le",
        "is_zero",
        "resolved_events",
        "resolved_source_count",
    ]
    unique_fields = [
        "family",
        "code_hex",
        "code_ascii_le",
        "structural_event",
        "structural_binding_evidence",
        "occurrence_count",
        "cells_row_selector_raw",
        "resolved_events",
        "resolved_source_count",
    ]
    write_csv(args.out_dir / "PATTERN_TABLE_CELLS.csv", all_cell_rows, cell_fields)
    write_csv(args.out_dir / "UNIQUE_EVENT_CODES.csv", all_unique_rows, unique_fields)

    report = {
        "schema": "magireco_slot_story_pattern_table_authority_v1",
        "lib": str(args.lib),
        "binary_authority": {
            "sha256": args.authority_sha256.lower(),
            "verification_mode": "inherited_exact_binary_identity_not_recomputed",
            "source": args.authority_source,
        },
        "dispatcher": {
            "symbol": args.dispatcher_symbol,
            "address": f"0x{int(dispatcher['address']):x}",
            "size": int(dispatcher["size"]),
            "supported_families_from_pc_relative_pointer_references": dispatcher_supported_families,
        },
        "families": family_summaries,
        "manifest_roots": [str(path) for path in args.manifest_root],
        "interpretation": {
            "collection_semantics": (
                "nonzero table cells enumerate stored event-code outcomes; repeated cells do not "
                "create duplicate collection chapters"
            ),
            "reachability_semantics": (
                "table existence alone does not establish dispatch reachability in this build"
            ),
            "timing_semantics": (
                "pattern-table reachability does not establish parent DGM to child Z2D offsets"
            ),
        },
        "outputs": {
            "cells_csv": str(args.out_dir / "PATTERN_TABLE_CELLS.csv"),
            "unique_codes_csv": str(args.out_dir / "UNIQUE_EVENT_CODES.csv"),
        },
    }
    (args.out_dir / "PATTERN_TABLE_AUTHORITY.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
