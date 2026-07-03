#!/usr/bin/env python3
"""Scan ELF64/AArch64 code for load/store references to structure offsets.

This is a narrow static-analysis helper for reverse-engineering runtime state
fields such as ``C_AnmBase+0x318`` or ``MSTCOMCBK()+0x2376``.  It disassembles
executable sections with Capstone, records instructions whose memory operand
uses one of the requested immediate displacements, and annotates each match with
the containing symbol when available.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_MEM, ARM64_OP_REG

from survey_aarch64_xrefs import (
    SHF_EXECINSTR,
    containing_symbol,
    elf_sections,
    load_symbols,
    parse_int,
)


def parse_offset(value: str) -> tuple[int, str]:
    if "=" in value:
        name, address_text = value.split("=", 1)
        return parse_int(address_text), name
    offset = parse_int(value)
    return offset, value


def classify_access(mnemonic: str) -> str:
    lowered = mnemonic.lower()
    if lowered.startswith("st"):
        return "write"
    if lowered.startswith("ld"):
        return "read"
    if lowered.startswith("prfm"):
        return "prefetch"
    return "unknown"


def canonical_register_name(md: Cs, reg_id: int) -> str:
    name = md.reg_name(reg_id)
    if name.startswith("w") and name[1:].isdigit():
        return "x" + name[1:]
    return name


def mov_immediate_destination(md: Cs, insn: Any) -> tuple[str, int] | None:
    if insn.mnemonic != "mov" or len(insn.operands) != 2:
        return None
    dst, src = insn.operands
    if dst.type != ARM64_OP_REG or src.type != ARM64_OP_IMM:
        return None
    return canonical_register_name(md, int(dst.reg)), int(src.imm)


def maybe_written_registers(md: Cs, insn: Any) -> set[str]:
    if not insn.operands:
        return set()
    if insn.mnemonic.startswith("st"):
        return set()
    first = insn.operands[0]
    if first.type == ARM64_OP_REG:
        return {canonical_register_name(md, int(first.reg))}
    return set()


def scan_offsets(
    blob: bytes,
    sections: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    offsets: dict[int, str],
) -> list[dict[str, Any]]:
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    rows: list[dict[str, Any]] = []
    for section in sections:
        if not (int(section["flags"]) & SHF_EXECINSTR):
            continue
        code = blob[section["offset"] : section["offset"] + section["size"]]
        start = int(section["addr"])
        register_constants: dict[str, tuple[int, int]] = {}
        for insn in md.disasm(code, start):
            mov_constant = mov_immediate_destination(md, insn)
            for operand_index, operand in enumerate(insn.operands):
                if operand.type != ARM64_OP_MEM:
                    continue
                displacement = int(operand.mem.disp)
                match_offset: int | None = None
                match_mode = ""
                index_constant_address = ""
                if displacement in offsets:
                    match_offset = displacement
                    match_mode = "direct_displacement"
                elif operand.mem.index:
                    index_name = canonical_register_name(md, int(operand.mem.index))
                    index_constant = register_constants.get(index_name)
                    if index_constant is not None:
                        index_value, constant_address = index_constant
                        candidate = displacement + index_value
                        if candidate in offsets:
                            match_offset = candidate
                            match_mode = "register_index_constant"
                            index_constant_address = f"0x{constant_address:x}"
                if match_offset is None:
                    continue
                symbol = containing_symbol(symbols, int(insn.address))
                rows.append(
                    {
                        "address": f"0x{int(insn.address):x}",
                        "section": section["name"],
                        "mnemonic": insn.mnemonic,
                        "op_str": insn.op_str,
                        "access": classify_access(insn.mnemonic),
                        "operand_index": operand_index,
                        "match_mode": match_mode,
                        "offset_hex": f"0x{match_offset:x}",
                        "offset_name": offsets[match_offset],
                        "index_constant_address": index_constant_address,
                        "mem_base_register_id": int(operand.mem.base),
                        "mem_index_register_id": int(operand.mem.index),
                        "caller_symbol": symbol["name"] if symbol else "",
                        "caller_symbol_address": f"0x{int(symbol['address']):x}" if symbol else "",
                        "caller_symbol_size": int(symbol["size"]) if symbol else "",
                    }
                )
            if mov_constant is not None:
                register_name, immediate = mov_constant
                register_constants[register_name] = (immediate, int(insn.address))
            else:
                for register_name in maybe_written_registers(md, insn):
                    register_constants.pop(register_name, None)
            if insn.mnemonic in {"ret", "br"} or insn.mnemonic.startswith("b."):
                register_constants.clear()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument("--offset", action="append", default=[], help="name=0xOFFSET or 0xOFFSET")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    if not args.offset:
        raise SystemExit("at least one --offset is required")

    offsets = dict(parse_offset(value) for value in args.offset)
    blob = args.lib.read_bytes()
    sections = elf_sections(blob)
    symbols = load_symbols(blob, sections)
    rows = scan_offsets(blob, sections, symbols, offsets)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "aarch64_memory_offset_refs.csv"
    fieldnames = [
        "address",
        "section",
        "mnemonic",
        "op_str",
        "access",
        "operand_index",
        "match_mode",
        "offset_hex",
        "offset_name",
        "index_constant_address",
        "mem_base_register_id",
        "mem_index_register_id",
        "caller_symbol",
        "caller_symbol_address",
        "caller_symbol_size",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    offset_counts = Counter((row["offset_hex"], row["offset_name"], row["access"]) for row in rows)
    symbol_counts = Counter(
        (row["offset_hex"], row["offset_name"], row["access"], row["caller_symbol"]) for row in rows
    )
    json_path = args.out_dir / "aarch64_memory_offset_refs.summary.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "lib": str(args.lib),
                "offsets": {f"0x{offset:x}": name for offset, name in offsets.items()},
                "row_count": len(rows),
                "counts_by_offset_access": [
                    {
                        "offset_hex": offset_hex,
                        "offset_name": offset_name,
                        "access": access,
                        "count": count,
                    }
                    for (offset_hex, offset_name, access), count in offset_counts.most_common()
                ],
                "counts_by_offset_access_symbol": [
                    {
                        "offset_hex": offset_hex,
                        "offset_name": offset_name,
                        "access": access,
                        "caller_symbol": caller_symbol,
                        "count": count,
                    }
                    for (offset_hex, offset_name, access, caller_symbol), count in symbol_counts.most_common()
                ],
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
                "row_count": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
