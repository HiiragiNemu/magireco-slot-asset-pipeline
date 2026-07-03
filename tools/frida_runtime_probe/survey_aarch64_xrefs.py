#!/usr/bin/env python3
"""Survey direct AArch64 branch/call xrefs in an ELF64 binary.

This is intentionally small and self-contained because the recovery environment
does not always have objdump/readelf.  It finds direct ``B``/``BL`` references
to named virtual addresses and writes both CSV rows and local disassembly
windows for audit.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Any

try:
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
except ImportError:  # pragma: no cover - environment dependent
    Cs = None  # type: ignore[assignment]
    CS_ARCH_ARM64 = 0  # type: ignore[assignment]
    CS_MODE_ARM = 0  # type: ignore[assignment]


SHF_EXECINSTR = 0x4
SHT_SYMTAB = 2
SHT_DYNSYM = 11
STT_FUNC = 2


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
        (
            sh_name,
            sh_type,
            sh_flags,
            sh_addr,
            sh_offset,
            sh_size,
            sh_link,
            sh_info,
            sh_addralign,
            sh_entsize,
        ) = struct.unpack_from("<IIQQQQIIQQ", blob, off)
        raw_sections.append(
            {
                "index": index,
                "name_offset": sh_name,
                "type": sh_type,
                "flags": sh_flags,
                "addr": sh_addr,
                "offset": sh_offset,
                "size": sh_size,
                "link": sh_link,
                "info": sh_info,
                "addralign": sh_addralign,
                "entsize": sh_entsize,
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


def load_symbols(blob: bytes, sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    for section in sections:
        if section["type"] not in {SHT_SYMTAB, SHT_DYNSYM}:
            continue
        entsize = int(section["entsize"] or 24)
        if entsize <= 0:
            continue
        strtab = sections[int(section["link"])]
        strings = blob[strtab["offset"] : strtab["offset"] + strtab["size"]]
        for offset in range(section["offset"], section["offset"] + section["size"], entsize):
            if offset + 24 > len(blob):
                break
            st_name, st_info, _st_other, st_shndx, st_value, st_size = struct.unpack_from(
                "<IBBHQQ", blob, offset
            )
            if st_value == 0 or st_name == 0:
                continue
            name = read_cstring(strings, st_name)
            symbols.append(
                {
                    "table": section["name"],
                    "name": name,
                    "type": st_info & 0xF,
                    "bind": st_info >> 4,
                    "section_index": st_shndx,
                    "address": st_value,
                    "size": st_size,
                }
            )
    return sorted(symbols, key=lambda row: (int(row["address"]), int(row["size"])))


def containing_symbol(symbols: list[dict[str, Any]], address: int) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for symbol in symbols:
        start = int(symbol["address"])
        size = int(symbol["size"] or 0)
        if size > 0 and start <= address < start + size:
            if best is None or start >= int(best["address"]):
                best = symbol
    if best is not None:
        return best
    for symbol in symbols:
        start = int(symbol["address"])
        if start <= address and (best is None or start >= int(best["address"])):
            best = symbol
    return best


def decode_direct_branch(word: int, address: int) -> tuple[str, int] | None:
    if (word & 0xFC000000) == 0x94000000:
        op = "bl"
    elif (word & 0xFC000000) == 0x14000000:
        op = "b"
    else:
        return None
    imm26 = word & 0x03FFFFFF
    if imm26 & 0x02000000:
        imm26 -= 0x04000000
    return op, address + imm26 * 4


def scan_direct_branches(
    blob: bytes,
    sections: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    targets: dict[int, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in sections:
        if not (int(section["flags"]) & SHF_EXECINSTR):
            continue
        start = int(section["addr"])
        data = blob[section["offset"] : section["offset"] + section["size"]]
        for rel in range(0, len(data) - 3, 4):
            address = start + rel
            word = struct.unpack_from("<I", data, rel)[0]
            branch = decode_direct_branch(word, address)
            if branch is None:
                continue
            op, target = branch
            if target not in targets:
                continue
            symbol = containing_symbol(symbols, address)
            rows.append(
                {
                    "xref_address": f"0x{address:x}",
                    "op": op,
                    "target_address": f"0x{target:x}",
                    "target_name": targets[target],
                    "caller_symbol": symbol["name"] if symbol else "",
                    "caller_symbol_address": f"0x{int(symbol['address']):x}" if symbol else "",
                    "caller_symbol_size": int(symbol["size"]) if symbol else "",
                    "section": section["name"],
                    "word_hex": f"0x{word:08x}",
                }
            )
    return rows


def scan_absolute_data_refs(
    blob: bytes,
    sections: list[dict[str, Any]],
    targets: dict[int, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    needles = {target.to_bytes(8, "little"): (target, name) for target, name in targets.items()}
    for section in sections:
        if int(section["flags"]) & SHF_EXECINSTR:
            continue
        data = blob[section["offset"] : section["offset"] + section["size"]]
        for needle, (target, name) in needles.items():
            start = 0
            while True:
                found = data.find(needle, start)
                if found < 0:
                    break
                rows.append(
                    {
                        "ref_address": f"0x{int(section['addr']) + found:x}",
                        "target_address": f"0x{target:x}",
                        "target_name": name,
                        "section": section["name"],
                    }
                )
                start = found + 1
    return rows


def disassemble_window(
    blob: bytes,
    sections: list[dict[str, Any]],
    address: int,
    before: int,
    after: int,
) -> list[str]:
    if Cs is None:
        return ["capstone is not installed"]
    start = max(address - before * 4, 0)
    size = (before + after + 1) * 4
    try:
        file_offset = vaddr_to_file_offset(sections, start)
    except ValueError as exc:
        return [str(exc)]
    code = blob[file_offset : file_offset + size]
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    lines: list[str] = []
    for insn in md.disasm(code, start):
        marker = "=>" if insn.address == address else "  "
        lines.append(f"{marker} 0x{insn.address:x}: {insn.mnemonic}\t{insn.op_str}")
    return lines


def parse_targets(values: list[str]) -> dict[int, str]:
    targets: dict[int, str] = {}
    for value in values:
        if "=" in value:
            name, address_text = value.split("=", 1)
        else:
            address_text = value
            name = value
        address = parse_int(address_text)
        targets[address] = name
    return targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument("--target", action="append", required=True, help="NAME=0xADDR or 0xADDR")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--window-before", type=int, default=24)
    parser.add_argument("--window-after", type=int, default=24)
    args = parser.parse_args()

    blob = args.lib.read_bytes()
    sections = elf_sections(blob)
    symbols = load_symbols(blob, sections)
    targets = parse_targets(args.target)
    branch_rows = scan_direct_branches(blob, sections, symbols, targets)
    data_rows = scan_absolute_data_refs(blob, sections, targets)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "direct_branch_xrefs.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "xref_address",
            "op",
            "target_address",
            "target_name",
            "caller_symbol",
            "caller_symbol_address",
            "caller_symbol_size",
            "section",
            "word_hex",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(branch_rows)
    with (args.out_dir / "absolute_data_refs.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["ref_address", "target_address", "target_name", "section"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_rows)

    windows: dict[str, list[str]] = {}
    for row in branch_rows:
        address = parse_int(str(row["xref_address"]))
        key = f"{row['target_name']}@0x{address:x}"
        windows[key] = disassemble_window(
            blob,
            sections,
            address,
            args.window_before,
            args.window_after,
        )
    (args.out_dir / "xref_disassembly_windows.txt").write_text(
        "\n\n".join(
            [f"## {key}\n" + "\n".join(lines) for key, lines in windows.items()]
        )
        + ("\n" if windows else ""),
        encoding="utf-8",
    )
    (args.out_dir / "summary.json").write_text(
        json.dumps(
            {
                "lib": str(args.lib),
                "targets": {f"0x{address:x}": name for address, name in targets.items()},
                "direct_branch_xref_count": len(branch_rows),
                "absolute_data_ref_count": len(data_rows),
                "symbol_count": len(symbols),
                "capstone_available": Cs is not None,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print((args.out_dir / "summary.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
