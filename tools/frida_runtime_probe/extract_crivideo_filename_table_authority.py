#!/usr/bin/env python3
"""Extract the exact Slot CRI movie-name table and classify Z2D .dgm references."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection


SLOT_BINARY_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
SLOT_BINARY_BUILD_ID = "a1aceffc5be1f2380cdcd9af4d8f9764ac2bf40b"
SLOT_BINARY_SIZE = 79_683_640
TABLE_VA = 0x44A7088
TABLE_COUNT = 7_801
AARCH64_RELATIVE = 1027

TARGET_BASE_NAMES = (
    "ac8040_premia_EF_add",
    "ac8040_premia_EF_add_LP",
    "ac8040_premia_EF",
    "ac8040_premia_EF_LP",
)
NON_SUBSTITUTE_NAME = "ac8040_premia_EF_zen"

CODE_AUTHORITY = (
    (
        "0x425a714",
        "CriVideo::CriResourceManager::BuildFileNameTable",
        "copies exactly 7801 names from p_s at 0x44a7088 into the lookup vector",
    ),
    (
        "0x4359ba4",
        "zg::CZ2DHardPlayer::OpenMovie",
        "removes the .dgm extension and calls GFDirectionCriPlayer::LoadUSM by base name",
    ),
    (
        "0x425d004",
        "CriVideo::GFDirectionCriPlayer::LoadUSM(char const*)",
        "delegates the base name to CriResourceManager::LoadUSMFileByName",
    ),
    (
        "0x425afa4",
        "CriVideo::CriResourceManager::LoadUSMFileByName",
        "performs exact name comparison against the compiled vector and returns false when absent",
    ),
)


class AuthorityError(ValueError):
    pass


def _va_to_file_offset(elf: ELFFile, address: int) -> int:
    for segment in elf.iter_segments():
        header = segment.header
        if (
            header["p_type"] == "PT_LOAD"
            and header["p_vaddr"] <= address < header["p_vaddr"] + header["p_filesz"]
        ):
            return int(header["p_offset"] + address - header["p_vaddr"])
    raise AuthorityError(f"virtual address is not file-backed: 0x{address:x}")


def _gnu_build_id(elf: ELFFile) -> str:
    section = elf.get_section_by_name(".note.gnu.build-id")
    if section is None:
        raise AuthorityError("GNU build-id note is missing")
    notes = list(section.iter_notes())
    if len(notes) != 1:
        raise AuthorityError("expected one GNU build-id note")
    value = notes[0]["n_desc"]
    return value if isinstance(value, str) else bytes(value).hex()


def extract_filename_table(binary: Path) -> tuple[list[str], dict[str, Any]]:
    if binary.stat().st_size != SLOT_BINARY_SIZE:
        raise AuthorityError(f"exact binary size differs: {binary.stat().st_size}")
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        build_id = _gnu_build_id(elf)
        if build_id.casefold() != SLOT_BINARY_BUILD_ID.casefold():
            raise AuthorityError(f"exact binary build-id differs: {build_id}")
        relocation_section = elf.get_section_by_name(".rela.dyn")
        if not isinstance(relocation_section, RelocationSection):
            raise AuthorityError(".rela.dyn relocation section is missing")
        table_end = TABLE_VA + TABLE_COUNT * 8
        relocations: dict[int, int] = {}
        for relocation in relocation_section.iter_relocations():
            offset = int(relocation["r_offset"])
            if TABLE_VA <= offset < table_end:
                if int(relocation["r_info_type"]) != AARCH64_RELATIVE:
                    raise AuthorityError(f"non-relative filename relocation at 0x{offset:x}")
                relocations[offset] = int(relocation["r_addend"])
        expected_offsets = [TABLE_VA + index * 8 for index in range(TABLE_COUNT)]
        if sorted(relocations) != expected_offsets:
            raise AuthorityError(
                f"filename relocation coverage differs: {len(relocations)} != {TABLE_COUNT}"
            )

        names: list[str] = []
        string_vas: list[int] = []
        for table_offset in expected_offsets:
            string_va = relocations[table_offset]
            string_vas.append(string_va)
            stream.seek(_va_to_file_offset(elf, string_va))
            raw = stream.read(512).split(b"\0", 1)[0]
            if not raw:
                raise AuthorityError(f"empty filename at table offset 0x{table_offset:x}")
            try:
                names.append(raw.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise AuthorityError(f"invalid filename UTF-8 at VA 0x{string_va:x}") from exc
    if len(set(names)) != TABLE_COUNT:
        raise AuthorityError("compiled CRI filename table contains duplicate names")
    metadata = {
        "table_va_hex": f"0x{TABLE_VA:x}",
        "entry_count": TABLE_COUNT,
        "entry_width": 8,
        "relocation_type": AARCH64_RELATIVE,
        "first_string_va_hex": f"0x{string_vas[0]:x}",
        "last_string_va_hex": f"0x{string_vas[-1]:x}",
        "unique_name_count": len(set(names)),
    }
    return names, metadata


def extract_z2d_dgm_names(z2d: Path) -> list[str]:
    data = z2d.read_bytes()
    values: list[str] = []
    patterns = (
        rb"\[([A-Za-z0-9_]+\.dgm)\]",
        rb"([A-Za-z0-9_]+\.dgm)\x00",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, data):
            value = match.group(1).decode("ascii")
            if value not in values:
                values.append(value)
    if not values:
        raise AuthorityError("target Z2D contains no .dgm references")
    return values


def classify_references(names: list[str], references: Iterable[str]) -> list[dict[str, Any]]:
    index = {name: position for position, name in enumerate(names)}
    result: list[dict[str, Any]] = []
    for reference in references:
        if not reference.endswith(".dgm"):
            raise AuthorityError(f"not a .dgm reference: {reference}")
        base_name = reference[:-4]
        table_index = index.get(base_name)
        result.append(
            {
                "z2d_reference": reference,
                "cri_lookup_base_name": base_name,
                "compiled_table_present": table_index is not None,
                "compiled_table_index": table_index,
                "runtime_load_disposition": (
                    "LOADABLE_BY_EXACT_NAME"
                    if table_index is not None
                    else "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"
                ),
            }
        )
    return result


def build_report(binary: Path, z2d: Path) -> tuple[dict[str, Any], list[str]]:
    names, table = extract_filename_table(binary)
    references = extract_z2d_dgm_names(z2d)
    rows = classify_references(names, references)
    by_base = {row["cri_lookup_base_name"]: row for row in rows}
    if set(by_base) != set(TARGET_BASE_NAMES):
        raise AuthorityError(f"target Z2D DGM set differs: {sorted(by_base)}")
    if any(by_base[name]["compiled_table_present"] for name in TARGET_BASE_NAMES[:2]):
        raise AuthorityError("add/add_LP unexpectedly became loadable")
    if not all(by_base[name]["compiled_table_present"] for name in TARGET_BASE_NAMES[2:]):
        raise AuthorityError("base/base_LP unexpectedly became unavailable")
    name_index = {name: position for position, name in enumerate(names)}
    if NON_SUBSTITUTE_NAME not in name_index:
        raise AuthorityError("expected _zen table entry is missing")
    return (
        {
            "schema": "magireco-ac0908-016-crivideo-name-reachability-v1",
            "status": "passed",
            "binary": {
                "path": str(binary.resolve()),
                "size": binary.stat().st_size,
                "gnu_build_id": SLOT_BINARY_BUILD_ID,
                "inherited_sha256": SLOT_BINARY_SHA256,
            },
            "z2d": {"path": str(z2d.resolve()), "dgm_reference_count": len(references)},
            "compiled_filename_table": table,
            "code_authority": [
                {"address": address, "function": function, "proves": proves}
                for address, function, proves in CODE_AUTHORITY
            ],
            "z2d_dgm_reachability": rows,
            "non_substitute": {
                "name": NON_SUBSTITUTE_NAME,
                "compiled_table_index": name_index[NON_SUBSTITUTE_NAME],
                "reason": "present in CRI table but absent from the target Z2D authored DGM set",
            },
            "assertions": {
                "add_and_add_lp_are_authored_but_unloadable_in_exact_current_binary": True,
                "base_and_base_lp_are_loadable": True,
                "zen_is_not_an_authored_substitute_for_this_z2d": True,
                "ac0908_016_visible_media_set": [
                    "ac0908_pre_c10",
                    "ac0908_pre_c10_LP",
                    "ac8040_premia_EF",
                    "ac8040_premia_EF_LP",
                ],
                "ac0908_016_resource_resolution_status": "CLOSED",
                "machine_vision_used_as_authority": False,
            },
        },
        names,
    )


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    values = list(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def write_outputs(report: dict[str, Any], names: list[str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    table_csv = output_dir / "CRIVIDEO_FILENAME_TABLE.csv"
    report_json = output_dir / "AC0908_016_DGM_REACHABILITY.json"
    authority_json = output_dir / "CRIVIDEO_FILENAME_TABLE_AUTHORITY.json"
    verification_json = output_dir / "VERIFICATION_RECORD.json"
    integration_txt = output_dir / "INTEGRATION_VERIFICATION.txt"
    write_csv(table_csv, ({"table_index": index, "name": name} for index, name in enumerate(names)))
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    authority_json.write_text(
        json.dumps(
            {
                "schema": "magireco-crivideo-compiled-filename-table-authority-v1",
                "status": "passed",
                "binary": report["binary"],
                "table": report["compiled_filename_table"],
                "table_csv": table_csv.name,
                "code_authority": report["code_authority"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    verification_json.write_text(
        json.dumps(
            {
                "schema": "magireco-ac0908-016-crivideo-verification-v1",
                "status": "passed",
                "checks": {
                    "compiled_filename_entries": len(names),
                    "compiled_filename_unique": len(set(names)),
                    "z2d_dgm_references": len(report["z2d_dgm_reachability"]),
                    "loadable_references": sum(
                        row["compiled_table_present"] for row in report["z2d_dgm_reachability"]
                    ),
                    "unloadable_references": sum(
                        not row["compiled_table_present"] for row in report["z2d_dgm_reachability"]
                    ),
                    "resource_resolution_closed": True,
                },
                "outputs": [table_csv.name, report_json.name, authority_json.name],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    integration_txt.write_text(
        "PASS\n"
        "compiled_filename_entries=7801\n"
        "z2d_dgm_references=4\n"
        "loadable=2\n"
        "unloadable_add_layers=2\n"
        "ac0908_016_resource_resolution=CLOSED\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report, names = build_report(args.binary, args.z2d)
    write_outputs(report, names, args.output_dir)
    print(
        "PASS compiled_filename_entries=7801 z2d_dgm_references=4 "
        "loadable=2 unloadable_add_layers=2 resource_resolution=CLOSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
