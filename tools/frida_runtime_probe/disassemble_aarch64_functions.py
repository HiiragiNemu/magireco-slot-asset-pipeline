#!/usr/bin/env python3
"""Dump selected AArch64 ELF functions with branch/call annotations.

This helper is intentionally narrow: it gives the next reverse-engineering pass
stable, auditable disassembly for named native functions without depending on
objdump/readelf being installed.  It reuses the small ELF parser from
``survey_aarch64_xrefs.py`` and writes:

* one ``functions_disassembly.txt`` file with function-sized windows;
* one ``branch_targets.csv`` file for direct ``b``/``bl`` targets inside those
  windows;
* one ``summary.json`` file with source library hash and resolved symbol ranges.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

from survey_aarch64_xrefs import (
    containing_symbol,
    decode_direct_branch,
    elf_sections,
    load_symbols,
    parse_int,
    vaddr_to_file_offset,
)


def parse_symbol_arg(value: str) -> tuple[str, int | None]:
    if "=" in value:
        name, size_text = value.split("=", 1)
        return name, parse_int(size_text)
    return value, None


def find_symbol(symbols: list[dict[str, Any]], name: str) -> dict[str, Any]:
    exact = [symbol for symbol in symbols if str(symbol["name"]) == name]
    if exact:
        return max(exact, key=lambda symbol: int(symbol["size"] or 0))
    contains = [symbol for symbol in symbols if name in str(symbol["name"])]
    if len(contains) == 1:
        return contains[0]
    if not contains:
        raise KeyError(f"symbol not found: {name}")
    matches = ", ".join(str(symbol["name"]) for symbol in contains[:20])
    raise KeyError(f"ambiguous symbol {name!r}; matches: {matches}")


def read_function_bytes(
    blob: bytes,
    sections: list[dict[str, Any]],
    symbol: dict[str, Any],
    override_size: int | None,
) -> bytes:
    address = int(symbol["address"])
    size = int(override_size if override_size is not None else symbol["size"] or 0)
    if size <= 0:
        raise ValueError(f"symbol has no size; pass NAME=0xSIZE for {symbol['name']}")
    file_offset = vaddr_to_file_offset(sections, address)
    return blob[file_offset : file_offset + size]


def disassemble_function(
    md: Cs,
    blob: bytes,
    sections: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    symbol: dict[str, Any],
    override_size: int | None,
) -> tuple[list[str], list[dict[str, Any]]]:
    name = str(symbol["name"])
    address = int(symbol["address"])
    code = read_function_bytes(blob, sections, symbol, override_size)
    lines = [f"## {name} @ 0x{address:x} size=0x{len(code):x}"]
    branch_rows: list[dict[str, Any]] = []
    for insn in md.disasm(code, address):
        rel = int(insn.address) - address
        raw_word = struct.unpack_from("<I", code, rel)[0] if rel + 4 <= len(code) else 0
        branch = decode_direct_branch(raw_word, int(insn.address))
        annotation = ""
        if branch is not None:
            op, target_address = branch
            target_symbol = containing_symbol(symbols, target_address)
            target_name = str(target_symbol["name"]) if target_symbol else ""
            annotation = f" ; {op}->0x{target_address:x}"
            if target_name:
                annotation += f" {target_name}"
            branch_rows.append(
                {
                    "function": name,
                    "xref_address": f"0x{int(insn.address):x}",
                    "op": op,
                    "target_address": f"0x{target_address:x}",
                    "target_symbol": target_name,
                    "target_symbol_address": f"0x{int(target_symbol['address']):x}" if target_symbol else "",
                    "target_symbol_size": int(target_symbol["size"]) if target_symbol else "",
                    "word_hex": f"0x{raw_word:08x}",
                }
            )
        lines.append(f"0x{int(insn.address):x}: {insn.mnemonic}\t{insn.op_str}{annotation}")
    return lines, branch_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument(
        "--symbol",
        action="append",
        required=True,
        help="Symbol name, or NAME=0xSIZE when the ELF symbol size is unusable.",
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    blob = args.lib.read_bytes()
    sections = elf_sections(blob)
    symbols = load_symbols(blob, sections)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = False

    args.out_dir.mkdir(parents=True, exist_ok=True)

    function_summaries: list[dict[str, Any]] = []
    all_lines: list[str] = []
    all_branch_rows: list[dict[str, Any]] = []
    for value in args.symbol:
        name, override_size = parse_symbol_arg(value)
        symbol = find_symbol(symbols, name)
        lines, branch_rows = disassemble_function(md, blob, sections, symbols, symbol, override_size)
        if all_lines:
            all_lines.append("")
        all_lines.extend(lines)
        all_branch_rows.extend(branch_rows)
        function_summaries.append(
            {
                "name": str(symbol["name"]),
                "address": f"0x{int(symbol['address']):x}",
                "elf_size": int(symbol["size"] or 0),
                "dumped_size": int(override_size if override_size is not None else symbol["size"] or 0),
                "branch_count": len(branch_rows),
            }
        )

    (args.out_dir / "functions_disassembly.txt").write_text("\n".join(all_lines) + "\n", encoding="utf-8")
    with (args.out_dir / "branch_targets.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "function",
            "xref_address",
            "op",
            "target_address",
            "target_symbol",
            "target_symbol_address",
            "target_symbol_size",
            "word_hex",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_branch_rows)

    summary = {
        "lib": str(args.lib),
        "lib_sha256": hashlib.sha256(blob).hexdigest(),
        "functions": function_summaries,
        "branch_target_count": len(all_branch_rows),
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
