#!/usr/bin/env python3
"""Scan AArch64 code for SdGmData field references.

This is a base-aware companion to ``scan_aarch64_memory_offsets.py``.  A raw
offset scan is too noisy for fields such as ``0x358`` because many unrelated C++
classes have a member at the same displacement.  This helper only records memory
references whose base register can be locally traced back to a call to
``fnGetAddrSdGmData``.

The analysis is intentionally conservative and local.  It is meant to triage
reverse-engineering targets, not to replace manual proof for final conclusions.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from capstone.arm64 import (
    ARM64_OP_IMM,
    ARM64_OP_MEM,
    ARM64_OP_REG,
    ARM64_SFT_LSL,
)

from survey_aarch64_xrefs import (
    SHF_EXECINSTR,
    containing_symbol,
    decode_direct_branch,
    elf_sections,
    load_symbols,
    parse_int,
)


CALLER_SAVED_REGS = {f"x{i}" for i in range(19)}


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
    if name == "sp" or name == "wsp":
        return "sp"
    if name.startswith("w") and name[1:].isdigit():
        return "x" + name[1:]
    return name


def shifted_immediate(operand: Any) -> int:
    value = int(operand.imm)
    shift = getattr(operand, "shift", None)
    if shift is not None and getattr(shift, "type", 0) == ARM64_SFT_LSL:
        value <<= int(getattr(shift, "value", 0))
    return value


def first_written_register(md: Cs, insn: Any) -> str | None:
    if not insn.operands or insn.mnemonic.startswith("st"):
        return None
    first = insn.operands[0]
    if first.type != ARM64_OP_REG:
        return None
    return canonical_register_name(md, int(first.reg))


def update_register_state(
    md: Cs,
    insn: Any,
    sdgm_regs: dict[str, int],
    constants: dict[str, int],
) -> None:
    mnemonic = insn.mnemonic.lower()
    operands = list(insn.operands)
    dst = first_written_register(md, insn)

    if mnemonic == "mov" and len(operands) == 2 and dst is not None:
        src = operands[1]
        if src.type == ARM64_OP_IMM:
            constants[dst] = int(src.imm)
            sdgm_regs.pop(dst, None)
            return
        if src.type == ARM64_OP_REG:
            src_name = canonical_register_name(md, int(src.reg))
            if src_name in sdgm_regs:
                sdgm_regs[dst] = sdgm_regs[src_name]
            else:
                sdgm_regs.pop(dst, None)
            constants.pop(dst, None)
            return

    if mnemonic == "add" and len(operands) == 3 and dst is not None:
        base_operand = operands[1]
        imm_operand = operands[2]
        if base_operand.type == ARM64_OP_REG and imm_operand.type == ARM64_OP_IMM:
            base_name = canonical_register_name(md, int(base_operand.reg))
            if base_name in sdgm_regs:
                sdgm_regs[dst] = sdgm_regs[base_name] + shifted_immediate(imm_operand)
            else:
                sdgm_regs.pop(dst, None)
            constants.pop(dst, None)
            return

    if dst is not None:
        sdgm_regs.pop(dst, None)
        constants.pop(dst, None)


def apply_call_clobber(
    sdgm_regs: dict[str, int],
    constants: dict[str, int],
) -> None:
    for register_name in list(sdgm_regs):
        if register_name in CALLER_SAVED_REGS:
            sdgm_regs.pop(register_name, None)
    for register_name in list(constants):
        if register_name in CALLER_SAVED_REGS:
            constants.pop(register_name, None)


def scan_sdgm_refs(
    blob: bytes,
    sections: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    sdgm_call_address: int,
    offsets: dict[int, str] | None,
) -> list[dict[str, Any]]:
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    rows: list[dict[str, Any]] = []

    for section in sections:
        if not (int(section["flags"]) & SHF_EXECINSTR):
            continue
        code = blob[section["offset"] : section["offset"] + section["size"]]
        start = int(section["addr"])
        sdgm_regs: dict[str, int] = {}
        constants: dict[str, int] = {}

        for insn in md.disasm(code, start):
            for operand_index, operand in enumerate(insn.operands):
                if operand.type != ARM64_OP_MEM:
                    continue
                base_name = canonical_register_name(md, int(operand.mem.base))
                if base_name not in sdgm_regs:
                    continue
                offset = sdgm_regs[base_name] + int(operand.mem.disp)
                index_name = ""
                index_constant = ""
                if operand.mem.index:
                    index_name = canonical_register_name(md, int(operand.mem.index))
                    if index_name not in constants:
                        continue
                    offset += constants[index_name]
                    index_constant = f"0x{constants[index_name]:x}"
                if offsets is not None and offset not in offsets:
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
                        "sdgm_base_register": base_name,
                        "sdgm_base_offset_hex": f"0x{sdgm_regs[base_name]:x}",
                        "index_register": index_name,
                        "index_constant_hex": index_constant,
                        "offset_hex": f"0x{offset:x}",
                        "offset_name": offsets.get(offset, "") if offsets is not None else "",
                        "caller_symbol": symbol["name"] if symbol else "",
                        "caller_symbol_address": f"0x{int(symbol['address']):x}" if symbol else "",
                        "caller_symbol_size": int(symbol["size"]) if symbol else "",
                    }
                )

            raw_word = int.from_bytes(
                blob[
                    section["offset"]
                    + (int(insn.address) - start) : section["offset"]
                    + (int(insn.address) - start)
                    + 4
                ],
                "little",
            )
            branch = decode_direct_branch(raw_word, int(insn.address))
            if branch is not None:
                op, target = branch
                if op == "bl":
                    apply_call_clobber(sdgm_regs, constants)
                    if target == sdgm_call_address:
                        sdgm_regs["x0"] = 0
                    else:
                        sdgm_regs.pop("x0", None)
                    continue
                if insn.mnemonic in {"ret", "br"} or op == "b":
                    sdgm_regs.clear()
                    constants.clear()
                    continue

            update_register_state(md, insn, sdgm_regs, constants)

            if insn.mnemonic in {"ret", "br"}:
                sdgm_regs.clear()
                constants.clear()

    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument(
        "--sdgm-call",
        default="0x4490390",
        help="absolute address of fnGetAddrSdGmData call target/PLT in the ELF",
    )
    parser.add_argument("--offset", action="append", default=[], help="name=0xOFFSET or 0xOFFSET")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    offsets = dict(parse_offset(value) for value in args.offset) if args.offset else None
    blob = args.lib.read_bytes()
    sections = elf_sections(blob)
    symbols = load_symbols(blob, sections)
    rows = scan_sdgm_refs(blob, sections, symbols, parse_int(args.sdgm_call), offsets)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "aarch64_sdgm_refs.csv"
    fieldnames = [
        "address",
        "section",
        "mnemonic",
        "op_str",
        "access",
        "operand_index",
        "sdgm_base_register",
        "sdgm_base_offset_hex",
        "index_register",
        "index_constant_hex",
        "offset_hex",
        "offset_name",
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
    summary = {
        "lib": str(args.lib),
        "sdgm_call": f"0x{parse_int(args.sdgm_call):x}",
        "offsets": {f"0x{offset:x}": name for offset, name in (offsets or {}).items()},
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
    }
    summary_path = args.out_dir / "aarch64_sdgm_refs.summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "csv": str(csv_path),
                "json": str(summary_path),
                "row_count": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

