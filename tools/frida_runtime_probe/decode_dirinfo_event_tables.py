#!/usr/bin/env python3
"""Decode the generic DirInfoTable -> EventInfo event-dispatch tables.

The slot runtime does not need manual per-``ac`` family routing.  Native code
uses a table-driven path:

    kind,row,selector -> DirInfoTable grid -> EventInfo index -> event code

The table contains relocatable pointers, so this script applies ELF RELA
addends before reading DirInfo grid pointers and EventInfo string pointers.
It writes auditable CSV/JSON outputs that can drive later scene grouping and
runtime validation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any

from survey_aarch64_xrefs import elf_sections, load_symbols, read_cstring, vaddr_to_file_offset


SHT_RELA = 4
SHT_SYMTAB = 2
SHT_DYNSYM = 11
R_AARCH64_RELATIVE = 0x403
DEFAULT_MAX_STRING_BYTES = 512


def parse_int(value: str) -> int:
    return int(value, 0)


def normalize_code(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return f"0x{int(text, 0):016x}"
    except ValueError:
        return text.lower()


def code_ascii_le(value: int) -> str:
    raw = value.to_bytes(8, "little", signed=False)
    return "".join(chr(byte) if 0x20 <= byte < 0x7F else "." for byte in raw)


def load_symbol_tables(blob: bytes, sections: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    tables: dict[int, list[dict[str, Any]]] = {}
    for section in sections:
        if section["type"] not in {SHT_SYMTAB, SHT_DYNSYM}:
            continue
        entsize = int(section["entsize"] or 24)
        if entsize <= 0:
            continue
        strtab = sections[int(section["link"])]
        strings = blob[strtab["offset"] : strtab["offset"] + strtab["size"]]
        rows: list[dict[str, Any]] = []
        for symbol_index, offset in enumerate(
            range(section["offset"], section["offset"] + section["size"], entsize)
        ):
            if offset + 24 > len(blob):
                break
            st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack_from(
                "<IBBHQQ", blob, offset
            )
            rows.append(
                {
                    "index": symbol_index,
                    "name": read_cstring(strings, st_name) if st_name else "",
                    "info": st_info,
                    "other": st_other,
                    "section_index": st_shndx,
                    "address": st_value,
                    "size": st_size,
                }
            )
        tables[int(section["index"])] = rows
    return tables


def load_relocation_values(
    blob: bytes,
    sections: list[dict[str, Any]],
    symbol_tables: dict[int, list[dict[str, Any]]],
) -> dict[int, int]:
    values: dict[int, int] = {}
    for section in sections:
        if section["type"] != SHT_RELA:
            continue
        entsize = int(section["entsize"] or 24)
        if entsize <= 0:
            continue
        linked_symbols = symbol_tables.get(int(section["link"]), [])
        for offset in range(section["offset"], section["offset"] + section["size"], entsize):
            if offset + 24 > len(blob):
                break
            r_offset, r_info, r_addend = struct.unpack_from("<QQq", blob, offset)
            r_type = r_info & 0xFFFFFFFF
            symbol_index = r_info >> 32
            if r_type == R_AARCH64_RELATIVE:
                values[r_offset] = r_addend & 0xFFFFFFFFFFFFFFFF
            elif 0 < symbol_index < len(linked_symbols):
                symbol = linked_symbols[symbol_index]
                values[r_offset] = (int(symbol["address"]) + r_addend) & 0xFFFFFFFFFFFFFFFF
    return values


def symbol_by_name(symbols: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [row for row in symbols if row.get("name") == name]
    if not matches:
        raise ValueError(f"symbol not found: {name}")
    matches.sort(key=lambda row: (int(row.get("size") or 0), int(row.get("address") or 0)), reverse=True)
    return matches[0]


def read_relocated_u64(
    blob: bytes,
    sections: list[dict[str, Any]],
    relocations: dict[int, int],
    vaddr: int,
) -> int:
    if vaddr in relocations:
        return relocations[vaddr]
    return struct.unpack_from("<Q", blob, vaddr_to_file_offset(sections, vaddr))[0]


def read_u16(blob: bytes, sections: list[dict[str, Any]], vaddr: int) -> int:
    return struct.unpack_from("<H", blob, vaddr_to_file_offset(sections, vaddr))[0]


def read_string_at(blob: bytes, sections: list[dict[str, Any]], pointer: int) -> str:
    if pointer == 0:
        return ""
    try:
        offset = vaddr_to_file_offset(sections, pointer)
    except ValueError:
        return ""
    end = blob.find(b"\0", offset, min(len(blob), offset + DEFAULT_MAX_STRING_BYTES))
    if end < 0:
        return ""
    return blob[offset:end].decode("utf-8", errors="replace")


def load_manifest_code_map(roots: list[Path]) -> dict[str, dict[str, Any]]:
    code_map: dict[str, dict[str, Any]] = {}

    def add(code: str, event: str, source: str) -> None:
        normalized = normalize_code(code)
        if not normalized or not event:
            return
        bucket = code_map.setdefault(
            normalized,
            {
                "events": set(),
                "sources": set(),
            },
        )
        bucket["events"].add(event)
        bucket["sources"].add(source)

    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*.json")
        for path in paths:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            code = str(doc.get("event_code_hex") or doc.get("code_hex") or "")
            event = str(doc.get("event") or doc.get("label") or "")
            if not event and path.parent.name == "events":
                event = path.stem
            if not event and path.name == "event_manifest.json":
                event = path.parent.name
            add(code, event, str(path))

    normalized_map: dict[str, dict[str, Any]] = {}
    for code, value in code_map.items():
        events = sorted(str(item) for item in value["events"])
        sources = sorted(str(item) for item in value["sources"])
        normalized_map[code] = {
            "events": events,
            "sources": sources,
            "source_count": len(sources),
        }
    return normalized_map


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sorted_int_join(values: set[str]) -> str:
    return ";".join(sorted(values, key=int))


def first_int(values: set[str]) -> int:
    return min(int(value) for value in values) if values else -1


def first_text(values: set[str]) -> str:
    return sorted(values)[0] if values else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--manifest-root",
        action="append",
        default=[],
        type=Path,
        help="Optional roots/files with event_manifest or production manifest JSON.",
    )
    parser.add_argument("--dirinfo-symbol", default="DirInfoTable")
    parser.add_argument("--eventinfo-symbol", default="EventInfo")
    parser.add_argument(
        "--max-route-cells",
        type=int,
        default=2_000_000,
        help="Safety cap for decoded DirInfo grid cells.",
    )
    parser.add_argument(
        "--include-zero-code-routes",
        action="store_true",
        help="Keep routes whose EventInfo code is 0.",
    )
    args = parser.parse_args()

    blob = args.lib.read_bytes()
    sections = elf_sections(blob)
    symbols = load_symbols(blob, sections)
    symbol_tables = load_symbol_tables(blob, sections)
    relocations = load_relocation_values(blob, sections, symbol_tables)
    dirinfo_symbol = symbol_by_name(symbols, args.dirinfo_symbol)
    eventinfo_symbol = symbol_by_name(symbols, args.eventinfo_symbol)
    dirinfo_address = int(dirinfo_symbol["address"])
    dirinfo_size = int(dirinfo_symbol["size"])
    eventinfo_address = int(eventinfo_symbol["address"])
    eventinfo_size = int(eventinfo_symbol["size"])
    if dirinfo_size % 16:
        raise ValueError(f"DirInfoTable size is not divisible by 16: {dirinfo_size}")
    if eventinfo_size % 24:
        raise ValueError(f"EventInfo size is not divisible by 24: {eventinfo_size}")

    dirinfo_count = dirinfo_size // 16
    eventinfo_count = eventinfo_size // 24
    code_map = load_manifest_code_map(args.manifest_root)

    event_rows: list[dict[str, Any]] = []
    event_index: dict[int, dict[str, Any]] = {}
    for index in range(eventinfo_count):
        record_address = eventinfo_address + index * 24
        code_value = read_relocated_u64(blob, sections, relocations, record_address)
        base_pointer = read_relocated_u64(blob, sections, relocations, record_address + 8)
        scene_pointer = read_relocated_u64(blob, sections, relocations, record_address + 16)
        code_hex = f"0x{code_value:016x}"
        resolved = code_map.get(code_hex, {})
        row = {
            "event_info_index": index,
            "record_address": f"0x{record_address:x}",
            "code_hex": code_hex,
            "code_ascii_le": code_ascii_le(code_value),
            "base_name_pointer": f"0x{base_pointer:x}" if base_pointer else "",
            "base_name": read_string_at(blob, sections, base_pointer),
            "scene_name_pointer": f"0x{scene_pointer:x}" if scene_pointer else "",
            "scene_name": read_string_at(blob, sections, scene_pointer),
            "resolved_events": ";".join(resolved.get("events", [])),
            "resolved_source_count": resolved.get("source_count", 0),
        }
        event_rows.append(row)
        event_index[index] = row

    dirinfo_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    route_cell_total = 0
    invalid_grid_count = 0
    invalid_event_index_count = 0
    event_code_to_routes: dict[str, int] = defaultdict(int)

    for kind in range(dirinfo_count):
        entry_address = dirinfo_address + kind * 16
        grid_pointer = read_relocated_u64(blob, sections, relocations, entry_address)
        row_count = read_u16(blob, sections, entry_address + 8)
        selector_count = read_u16(blob, sections, entry_address + 10)
        extra_0c = read_u16(blob, sections, entry_address + 12)
        extra_0e = read_u16(blob, sections, entry_address + 14)
        cell_count = row_count * selector_count
        valid_grid = bool(grid_pointer and row_count and selector_count)
        grid_status = "ok"
        if valid_grid:
            try:
                vaddr_to_file_offset(sections, grid_pointer + max(0, cell_count - 1) * 2)
            except ValueError:
                valid_grid = False
                grid_status = "grid_pointer_not_mapped"
                invalid_grid_count += 1
        else:
            grid_status = "empty"
        if route_cell_total + cell_count > args.max_route_cells:
            valid_grid = False
            grid_status = "max_route_cells_exceeded"

        dirinfo_rows.append(
            {
                "kind": kind,
                "kind_hex": f"0x{kind:x}",
                "entry_address": f"0x{entry_address:x}",
                "grid_pointer": f"0x{grid_pointer:x}" if grid_pointer else "",
                "row_count": row_count,
                "selector_count": selector_count,
                "cell_count": cell_count,
                "extra_u16_0c": extra_0c,
                "extra_u16_0e": extra_0e,
                "grid_status": grid_status,
            }
        )

        if not valid_grid:
            continue
        route_cell_total += cell_count
        grid_offset = vaddr_to_file_offset(sections, grid_pointer)
        for row_index in range(row_count):
            for selector_raw in range(selector_count):
                cell_offset = grid_offset + (row_index * selector_count + selector_raw) * 2
                event_info_idx = struct.unpack_from("<H", blob, cell_offset)[0]
                event = event_index.get(event_info_idx)
                if event is None:
                    invalid_event_index_count += 1
                    route_rows.append(
                        {
                            "kind": kind,
                            "kind_hex": f"0x{kind:x}",
                            "row_index": row_index,
                            "selector_raw": selector_raw,
                            "selector_1based": selector_raw + 1,
                            "event_info_index": event_info_idx,
                            "code_hex": "",
                            "code_ascii_le": "",
                            "base_name": "",
                            "scene_name": "",
                            "resolved_events": "",
                            "resolved_source_count": 0,
                            "route_status": "invalid_event_info_index",
                        }
                    )
                    continue
                if event["code_hex"] == "0x0000000000000000" and not args.include_zero_code_routes:
                    continue
                event_code_to_routes[str(event["code_hex"])] += 1
                route_rows.append(
                    {
                        "kind": kind,
                        "kind_hex": f"0x{kind:x}",
                        "row_index": row_index,
                        "selector_raw": selector_raw,
                        "selector_1based": selector_raw + 1,
                        "event_info_index": event_info_idx,
                        "code_hex": event["code_hex"],
                        "code_ascii_le": event["code_ascii_le"],
                        "base_name": event["base_name"],
                        "scene_name": event["scene_name"],
                        "resolved_events": event["resolved_events"],
                        "resolved_source_count": event["resolved_source_count"],
                        "route_status": "ok",
                    }
                )

    resolved_route_rows = [row for row in route_rows if row.get("resolved_events")]
    route_groups: dict[str, dict[str, Any]] = {}
    for row in route_rows:
        if row.get("route_status") != "ok" or not row.get("code_hex"):
            continue
        code_hex = str(row["code_hex"])
        group = route_groups.setdefault(
            code_hex,
            {
                "route_count": 0,
                "base_names": set(),
                "scene_names": set(),
                "kinds": set(),
                "row_indices": set(),
                "selector_raws": set(),
                "selector_1based": set(),
                "event_info_indices": set(),
            },
        )
        group["route_count"] += 1
        for key in ("base_name", "scene_name"):
            if row.get(key):
                group[f"{key}s"].add(str(row[key]))
        group["kinds"].add(str(row["kind"]))
        group["row_indices"].add(str(row["row_index"]))
        group["selector_raws"].add(str(row["selector_raw"]))
        group["selector_1based"].add(str(row["selector_1based"]))
        group["event_info_indices"].add(str(row["event_info_index"]))

    unique_event_rows: list[dict[str, Any]] = []
    for code_hex, group in sorted(route_groups.items()):
        event = code_map.get(code_hex, {})
        first_kind = first_int(group["kinds"])
        first_row_index = first_int(group["row_indices"])
        first_selector_raw = first_int(group["selector_raws"])
        unique_event_rows.append(
            {
                "code_hex": code_hex,
                "code_ascii_le": code_ascii_le(int(code_hex, 0)) if code_hex else "",
                "route_count": group["route_count"],
                "first_base_name": first_text(group["base_names"]),
                "first_scene_name": first_text(group["scene_names"]),
                "first_kind": first_kind,
                "first_row_index": first_row_index,
                "first_selector_raw": first_selector_raw,
                "base_names": ";".join(sorted(group["base_names"])),
                "scene_names": ";".join(sorted(group["scene_names"])),
                "kinds": sorted_int_join(group["kinds"]),
                "row_indices": sorted_int_join(group["row_indices"]),
                "selector_raws": sorted_int_join(group["selector_raws"]),
                "selector_1based_values": sorted_int_join(group["selector_1based"]),
                "event_info_indices": sorted_int_join(group["event_info_indices"]),
                "resolved_events": ";".join(event.get("events", [])),
                "resolved_source_count": event.get("source_count", 0),
            }
        )
    unique_event_rows.sort(
        key=lambda row: (
            str(row["first_base_name"]),
            int(row["first_kind"]),
            int(row["first_row_index"]),
            int(row["first_selector_raw"]),
            str(row["first_scene_name"]),
            str(row["code_hex"]),
        )
    )
    resolved_scene_rows = [row for row in unique_event_rows if row.get("resolved_events")]

    base_summary: dict[str, dict[str, Any]] = {}
    for row in unique_event_rows:
        base_names = [item for item in str(row.get("base_names", "")).split(";") if item]
        for base_name in base_names or [""]:
            group = base_summary.setdefault(
                base_name,
                {
                    "base_name": base_name,
                    "unique_event_code_count": 0,
                    "resolved_event_code_count": 0,
                    "route_count": 0,
                    "kinds": set(),
                    "resolved_events": set(),
                },
            )
            group["unique_event_code_count"] += 1
            group["route_count"] += int(row["route_count"])
            for kind in str(row.get("kinds", "")).split(";"):
                if kind:
                    group["kinds"].add(kind)
            for event in str(row.get("resolved_events", "")).split(";"):
                if event:
                    group["resolved_events"].add(event)
            if row.get("resolved_events"):
                group["resolved_event_code_count"] += 1

    base_summary_rows = [
        {
            "base_name": value["base_name"],
            "unique_event_code_count": value["unique_event_code_count"],
            "resolved_event_code_count": value["resolved_event_code_count"],
            "route_count": value["route_count"],
            "kinds": ";".join(sorted(value["kinds"], key=int)),
            "resolved_event_count": len(value["resolved_events"]),
            "resolved_events": ";".join(sorted(value["resolved_events"])),
        }
        for value in base_summary.values()
    ]
    base_summary_rows.sort(
        key=lambda row: (
            -int(row["resolved_event_code_count"]),
            -int(row["unique_event_code_count"]),
            str(row["base_name"]),
        )
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.out_dir / "event_info_records.csv",
        event_rows,
        [
            "event_info_index",
            "record_address",
            "code_hex",
            "code_ascii_le",
            "base_name_pointer",
            "base_name",
            "scene_name_pointer",
            "scene_name",
            "resolved_events",
            "resolved_source_count",
        ],
    )
    write_csv(
        args.out_dir / "dirinfo_entries.csv",
        dirinfo_rows,
        [
            "kind",
            "kind_hex",
            "entry_address",
            "grid_pointer",
            "row_count",
            "selector_count",
            "cell_count",
            "extra_u16_0c",
            "extra_u16_0e",
            "grid_status",
        ],
    )
    route_fields = [
        "kind",
        "kind_hex",
        "row_index",
        "selector_raw",
        "selector_1based",
        "event_info_index",
        "code_hex",
        "code_ascii_le",
        "base_name",
        "scene_name",
        "resolved_events",
        "resolved_source_count",
        "route_status",
    ]
    write_csv(args.out_dir / "dirinfo_event_routes.csv", route_rows, route_fields)
    write_csv(args.out_dir / "resolved_dirinfo_event_routes.csv", resolved_route_rows, route_fields)
    write_csv(
        args.out_dir / "unique_event_codes.csv",
        unique_event_rows,
        [
            "code_hex",
            "code_ascii_le",
            "route_count",
            "first_base_name",
            "first_scene_name",
            "first_kind",
            "first_row_index",
            "first_selector_raw",
            "base_names",
            "scene_names",
            "kinds",
            "row_indices",
            "selector_raws",
            "selector_1based_values",
            "event_info_indices",
            "resolved_events",
            "resolved_source_count",
        ],
    )
    write_csv(
        args.out_dir / "resolved_scene_catalog.csv",
        resolved_scene_rows,
        [
            "code_hex",
            "code_ascii_le",
            "route_count",
            "first_base_name",
            "first_scene_name",
            "first_kind",
            "first_row_index",
            "first_selector_raw",
            "base_names",
            "scene_names",
            "kinds",
            "row_indices",
            "selector_raws",
            "selector_1based_values",
            "event_info_indices",
            "resolved_events",
            "resolved_source_count",
        ],
    )
    write_csv(
        args.out_dir / "base_scene_summary.csv",
        base_summary_rows,
        [
            "base_name",
            "unique_event_code_count",
            "resolved_event_code_count",
            "route_count",
            "kinds",
            "resolved_event_count",
            "resolved_events",
        ],
    )

    summary = {
        "lib": str(args.lib),
        "lib_sha256": hashlib.sha256(blob).hexdigest(),
        "dirinfo_symbol": {
            "name": args.dirinfo_symbol,
            "address": f"0x{dirinfo_address:x}",
            "size": dirinfo_size,
            "entry_count": dirinfo_count,
        },
        "eventinfo_symbol": {
            "name": args.eventinfo_symbol,
            "address": f"0x{eventinfo_address:x}",
            "size": eventinfo_size,
            "record_count": eventinfo_count,
        },
        "manifest_roots": [str(path) for path in args.manifest_root],
        "manifest_code_count": len(code_map),
        "relocation_value_count": len(relocations),
        "dirinfo_valid_entry_count": sum(1 for row in dirinfo_rows if row["grid_status"] == "ok"),
        "dirinfo_invalid_grid_count": invalid_grid_count,
        "route_row_count": len(route_rows),
        "route_cell_total": route_cell_total,
        "invalid_event_index_count": invalid_event_index_count,
        "unique_route_event_code_count": len(event_code_to_routes),
        "resolved_route_row_count": len(resolved_route_rows),
        "resolved_unique_event_code_count": sum(1 for row in unique_event_rows if row["resolved_events"]),
        "outputs": {
            "event_info_records_csv": str(args.out_dir / "event_info_records.csv"),
            "dirinfo_entries_csv": str(args.out_dir / "dirinfo_entries.csv"),
            "dirinfo_event_routes_csv": str(args.out_dir / "dirinfo_event_routes.csv"),
            "resolved_dirinfo_event_routes_csv": str(args.out_dir / "resolved_dirinfo_event_routes.csv"),
            "unique_event_codes_csv": str(args.out_dir / "unique_event_codes.csv"),
            "resolved_scene_catalog_csv": str(args.out_dir / "resolved_scene_catalog.csv"),
            "base_scene_summary_csv": str(args.out_dir / "base_scene_summary.csv"),
        },
    }
    with (args.out_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
