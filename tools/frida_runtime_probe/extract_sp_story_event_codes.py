#!/usr/bin/env python3
"""Recover C_ObjStageAT_SP_Story event-code constants from libGameProc.so.

The slot runtime does not choose AT SP story events by an ``ac`` suffix or CRI
index.  ``C_ObjStageAT_SP_Story::fnSetEvCdBase`` and
``C_ObjStageAT_SP_Story::fnSetEvCdNext`` build 64-bit event codes with AArch64
``mov``/``movk`` immediates and store them into the story object.  This script
extracts those constants directly from the native binary and optionally maps
them to already-resolved official event manifests.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Any


DEFAULT_RANGES = {
    "C_ObjStageAT_SP_Story::fnSetEvCdBase": (0x43DC3E8, 0x43DCBBC),
    "C_ObjStageAT_SP_Story::fnSetEvCdNext": (0x43DCBBC, 0x43DCE50),
}

DEFAULT_BASE_JUMP_TABLES = [
    {
        "function": "C_ObjStageAT_SP_Story::fnSetEvCdBase",
        "stage_kind_u16_at_0x318": 9,
        "jump_table_address": 0x1572920,
        "case_base_address": 0x43DC4CC,
        "selector_count": 30,
    },
    {
        "function": "C_ObjStageAT_SP_Story::fnSetEvCdBase",
        "stage_kind_u16_at_0x318": 10,
        "jump_table_address": 0x15728E4,
        "case_base_address": 0x43DC56C,
        "selector_count": 30,
    },
    {
        "function": "C_ObjStageAT_SP_Story::fnSetEvCdBase",
        "stage_kind_u16_at_0x318": 11,
        "jump_table_address": 0x15728A8,
        "case_base_address": 0x43DC434,
        "selector_count": 30,
    },
    {
        "function": "C_ObjStageAT_SP_Story::fnSetEvCdBase",
        "stage_kind_u16_at_0x318": 12,
        "jump_table_address": 0x157286C,
        "case_base_address": 0x43DC508,
        "selector_count": 30,
    },
    {
        "function": "C_ObjStageAT_SP_Story::fnSetEvCdBase",
        "stage_kind_u16_at_0x318": 13,
        "jump_table_address": 0x1572830,
        "case_base_address": 0x43DC5AC,
        "selector_count": 30,
    },
    {
        "function": "C_ObjStageAT_SP_Story::fnSetEvCdBase",
        "stage_kind_u16_at_0x318": 14,
        "jump_table_address": 0x15727F4,
        "case_base_address": 0x43DC48C,
        "selector_count": 30,
    },
]


def parse_int(value: str) -> int:
    return int(value, 0)


def read_cstring(blob: bytes, offset: int) -> str:
    end = blob.find(b"\0", offset)
    if end < 0:
        end = len(blob)
    return blob[offset:end].decode("utf-8", errors="replace")


def elf_sections(blob: bytes) -> list[dict[str, Any]]:
    if blob[:4] != b"\x7fELF" or blob[4] != 2 or blob[5] != 1:
        raise ValueError("expected little-endian ELF64")
    e_shoff = struct.unpack_from("<Q", blob, 0x28)[0]
    e_shentsize = struct.unpack_from("<H", blob, 0x3A)[0]
    e_shnum = struct.unpack_from("<H", blob, 0x3C)[0]
    e_shstrndx = struct.unpack_from("<H", blob, 0x3E)[0]
    raw_sections = []
    for index in range(e_shnum):
        off = e_shoff + index * e_shentsize
        sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(
            "<IIQQQQ", blob, off
        )
        raw_sections.append(
            {
                "index": index,
                "name_offset": sh_name,
                "type": sh_type,
                "flags": sh_flags,
                "addr": sh_addr,
                "offset": sh_offset,
                "size": sh_size,
            }
        )
    shstr = raw_sections[e_shstrndx]
    shstr_blob = blob[shstr["offset"] : shstr["offset"] + shstr["size"]]
    for section in raw_sections:
        section["name"] = read_cstring(shstr_blob, section["name_offset"])
    return raw_sections


def vaddr_to_file_offset(sections: list[dict[str, Any]], vaddr: int) -> int:
    for section in sections:
        start = int(section["addr"])
        end = start + int(section["size"])
        if start <= vaddr < end:
            return int(section["offset"]) + (vaddr - start)
    raise ValueError(f"virtual address 0x{vaddr:x} is not covered by any section")


def decode_move_wide(word: int) -> tuple[str, int, int, int] | None:
    """Return (op, rd, shift, imm16) for 64-bit MOVZ/MOVK, else None."""

    if (word & 0xFF800000) == 0xD2800000:
        op = "movz"
    elif (word & 0xFF800000) == 0xF2800000:
        op = "movk"
    else:
        return None
    rd = word & 0x1F
    shift = ((word >> 21) & 0x3) * 16
    imm16 = (word >> 5) & 0xFFFF
    return op, rd, shift, imm16


def decode_str_x(word: int) -> tuple[int, int, int] | None:
    """Return (rt, rn, byte_offset) for 64-bit STR unsigned immediate."""

    if (word & 0xFFC00000) != 0xF9000000:
        return None
    rt = word & 0x1F
    rn = (word >> 5) & 0x1F
    imm = ((word >> 10) & 0xFFF) * 8
    return rt, rn, imm


def decode_unconditional_branch(word: int, address: int) -> int | None:
    if (word & 0x7C000000) != 0x14000000:
        return None
    imm26 = word & 0x03FFFFFF
    if imm26 & 0x02000000:
        imm26 -= 0x04000000
    return address + imm26 * 4


def code_ascii_le(value: int) -> str:
    raw = value.to_bytes(8, "little", signed=False)
    return "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in raw)


def load_resolved_events(root: Path | None) -> dict[str, str]:
    if root is None:
        return {}
    result: dict[str, str] = {}
    for manifest in root.glob("*/*event_manifest.json"):
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        code = str(doc.get("code_hex") or "").lower()
        event = str(doc.get("event") or "")
        if code and event:
            result[code] = event
    return result


def find_store_after(
    blob: bytes,
    sections: list[dict[str, Any]],
    start_address: int,
    function_end: int,
    max_instructions: int = 8,
) -> tuple[int | None, int | None]:
    """Return (store_address, this_offset) for a nearby store/branch-to-store."""

    for step in range(1, max_instructions + 1):
        address = start_address + step * 4
        if address >= function_end:
            break
        file_offset = vaddr_to_file_offset(sections, address)
        word = struct.unpack_from("<I", blob, file_offset)[0]
        store = decode_str_x(word)
        if store is not None:
            rt, rn, byte_offset = store
            if rt == 8 and rn == 0:
                return address, byte_offset
        branch_target = decode_unconditional_branch(word, address)
        if branch_target is not None and start_address <= branch_target < function_end:
            target_offset = vaddr_to_file_offset(sections, branch_target)
            target_word = struct.unpack_from("<I", blob, target_offset)[0]
            store = decode_str_x(target_word)
            if store is not None:
                rt, rn, byte_offset = store
                if rt == 8 and rn == 0:
                    return branch_target, byte_offset
    return None, None


def extract_range(
    blob: bytes,
    sections: list[dict[str, Any]],
    function_name: str,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_value: int | None = None
    current_start: int | None = None

    for address in range(start, end, 4):
        word = struct.unpack_from("<I", blob, vaddr_to_file_offset(sections, address))[0]
        move = decode_move_wide(word)
        if move is not None:
            op, rd, shift, imm16 = move
            if rd == 8:
                if op == "movz":
                    current_value = imm16 << shift
                    current_start = address
                elif current_value is not None:
                    current_value &= ~(0xFFFF << shift)
                    current_value |= imm16 << shift
                continue

        if current_value is None or current_start is None:
            continue
        store_address, this_offset = find_store_after(blob, sections, address - 4, end)
        if store_address is None:
            continue
        rows.append(
            {
                "function": function_name,
                "constant_address": f"0x{current_start:x}",
                "store_address": f"0x{store_address:x}",
                "target_this_offset": f"0x{this_offset:x}",
                "code_hex": f"0x{current_value:016x}",
                "code_ascii_le": code_ascii_le(current_value),
            }
        )
        current_value = None
        current_start = None
    return rows


def decode_constant_at(
    blob: bytes,
    sections: list[dict[str, Any]],
    target: int,
    function_start: int,
    function_end: int,
    max_instructions: int = 12,
) -> dict[str, Any]:
    current_value: int | None = None
    current_start: int | None = None
    last_move_address: int | None = None
    for step in range(max_instructions):
        address = target + step * 4
        if address >= function_end:
            break
        word = struct.unpack_from("<I", blob, vaddr_to_file_offset(sections, address))[0]
        move = decode_move_wide(word)
        if move is not None:
            op, rd, shift, imm16 = move
            if rd == 8:
                if op == "movz":
                    current_value = imm16 << shift
                    current_start = address
                elif current_value is not None:
                    current_value &= ~(0xFFFF << shift)
                    current_value |= imm16 << shift
                last_move_address = address
                continue

        if current_value is not None and last_move_address is not None:
            store_address, this_offset = find_store_after(
                blob,
                sections,
                last_move_address,
                function_end,
                max_instructions=8,
            )
            if store_address is not None:
                return {
                    "constant_address": f"0x{current_start:x}" if current_start else "",
                    "store_address": f"0x{store_address:x}",
                    "target_this_offset": f"0x{this_offset:x}",
                    "code_hex": f"0x{current_value:016x}",
                    "code_ascii_le": code_ascii_le(current_value),
                    "decode_status": "ok",
                }
        branch_target = decode_unconditional_branch(word, address)
        if (
            branch_target is not None
            and function_start <= branch_target < function_end
            and branch_target != address
        ):
            branch_result = decode_constant_at(
                blob,
                sections,
                branch_target,
                function_start,
                function_end,
                max_instructions=max_instructions,
            )
            if branch_result.get("decode_status") == "ok":
                return branch_result
    return {
        "constant_address": "",
        "store_address": "",
        "target_this_offset": "",
        "code_hex": "",
        "code_ascii_le": "",
        "decode_status": f"no constant decoded at 0x{target:x}",
    }


def extract_base_jump_table_routes(
    blob: bytes,
    sections: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    function_start: int,
    function_end: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in tables:
        table_address = int(table["jump_table_address"])
        case_base = int(table["case_base_address"])
        selector_count = int(table["selector_count"])
        for index in range(selector_count):
            selector = index + 1
            entry_address = table_address + index * 2
            entry_offset = struct.unpack_from(
                "<H",
                blob,
                vaddr_to_file_offset(sections, entry_address),
            )[0]
            target = case_base + entry_offset * 4
            decoded = decode_constant_at(blob, sections, target, function_start, function_end)
            rows.append(
                {
                    "function": table["function"],
                    "stage_kind_u16_at_0x318": int(table["stage_kind_u16_at_0x318"]),
                    "selector_u16_at_0x34a": selector,
                    "jump_table_address": f"0x{table_address:x}",
                    "jump_table_entry_address": f"0x{entry_address:x}",
                    "jump_table_entry_u16": entry_offset,
                    "case_base_address": f"0x{case_base:x}",
                    "jump_target_address": f"0x{target:x}",
                    **decoded,
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--resolved-root",
        type=Path,
        help="Optional root containing resolved/*/event_manifest.json files.",
    )
    parser.add_argument(
        "--range",
        action="append",
        nargs=3,
        metavar=("NAME", "START", "END"),
        help="Virtual-address range to scan. Defaults to C_ObjStageAT_SP_Story base/next.",
    )
    args = parser.parse_args()

    blob = args.lib.read_bytes()
    sections = elf_sections(blob)
    ranges = (
        {name: (parse_int(start), parse_int(end)) for name, start, end in args.range}
        if args.range
        else DEFAULT_RANGES
    )

    resolved = load_resolved_events(args.resolved_root)
    rows: list[dict[str, Any]] = []
    for name, (start, end) in ranges.items():
        rows.extend(extract_range(blob, sections, name, start, end))
    for row in rows:
        row["resolved_event"] = resolved.get(str(row["code_hex"]).lower(), "")

    route_rows = extract_base_jump_table_routes(
        blob,
        sections,
        DEFAULT_BASE_JUMP_TABLES,
        DEFAULT_RANGES["C_ObjStageAT_SP_Story::fnSetEvCdBase"][0],
        DEFAULT_RANGES["C_ObjStageAT_SP_Story::fnSetEvCdBase"][1],
    )
    for row in route_rows:
        row["resolved_event"] = resolved.get(str(row["code_hex"]).lower(), "")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "sp_story_event_codes.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "function",
            "constant_address",
            "store_address",
            "target_this_offset",
            "code_hex",
            "code_ascii_le",
            "resolved_event",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    json_path = args.out_dir / "sp_story_event_codes.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "lib": str(args.lib),
                "ranges": {
                    name: {"start": f"0x{start:x}", "end": f"0x{end:x}"}
                    for name, (start, end) in ranges.items()
                },
                "resolved_root": str(args.resolved_root) if args.resolved_root else None,
                "row_count": len(rows),
                "resolved_count": sum(1 for row in rows if row.get("resolved_event")),
                "rows": rows,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")

    routes_csv_path = args.out_dir / "sp_story_event_code_routes.csv"
    with routes_csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "function",
            "stage_kind_u16_at_0x318",
            "selector_u16_at_0x34a",
            "jump_table_address",
            "jump_table_entry_address",
            "jump_table_entry_u16",
            "case_base_address",
            "jump_target_address",
            "constant_address",
            "store_address",
            "target_this_offset",
            "code_hex",
            "code_ascii_le",
            "decode_status",
            "resolved_event",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(route_rows)

    routes_json_path = args.out_dir / "sp_story_event_code_routes.json"
    with routes_json_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "lib": str(args.lib),
                "resolved_root": str(args.resolved_root) if args.resolved_root else None,
                "jump_tables": [
                    {
                        **table,
                        "jump_table_address": f"0x{int(table['jump_table_address']):x}",
                        "case_base_address": f"0x{int(table['case_base_address']):x}",
                    }
                    for table in DEFAULT_BASE_JUMP_TABLES
                ],
                "row_count": len(route_rows),
                "resolved_count": sum(1 for row in route_rows if row.get("resolved_event")),
                "rows": route_rows,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")

    print(
        json.dumps(
            {
                "csv": str(csv_path),
                "json": str(json_path),
                "routes_csv": str(routes_csv_path),
                "routes_json": str(routes_json_path),
                "row_count": len(rows),
                "resolved_count": sum(1 for row in rows if row.get("resolved_event")),
                "route_row_count": len(route_rows),
                "route_resolved_count": sum(1 for row in route_rows if row.get("resolved_event")),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
