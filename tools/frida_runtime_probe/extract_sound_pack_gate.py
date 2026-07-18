#!/usr/bin/env python3
"""Extract the version-specific static Sound Pack gate table.

The current Android arm64 build keeps a little-endian array of sound resource
IDs in ``libGameProc.so``.  When Sound Pack entitlement index 6 is disabled,
the native sound manager uses this array to reject or zero the volume of those
IDs.  This tool only reads a local library and optional CSV evidence.  It does
not attach to a process and must not be used to modify, spoof, or bypass a
purchase entitlement.

The default file offset, byte length, and CplayData-relative offsets below are
static evidence for the audited versionCode 31 build.  They are deliberately
reported with a version-scope warning and are not write targets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_TABLE_FILE_OFFSET = 0x14458DC
DEFAULT_TABLE_BYTE_LENGTH = 0x378
GATE_ENTRY_SIZE = 4

ENTITLEMENT_INDEX = 6
ACTIVE_ADDON_ARRAY_OFFSET = 0x14BF4
SAVED_ADDON_ARRAY_OFFSET = 0x14A58
ACTIVE_SOUND_PACK_OFFSET = ACTIVE_ADDON_ARRAY_OFFSET + ENTITLEMENT_INDEX * 4
SAVED_SOUND_PACK_OFFSET = SAVED_ADDON_ARRAY_OFFSET + ENTITLEMENT_INDEX * 4

REFERENCE_APPLICATION_ID = "com.universal777.magireco"
REFERENCE_VERSION_NAME = "1.0.0"
REFERENCE_VERSION_CODE = 31
REFERENCE_LIBRARY_SHA256 = (
    "5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf"
)
REFERENCE_TABLE_SHA256 = (
    "c18955f4cd09f18cba179aa19d432864026c1591243c9ab7f134fc7347153fdc"
)
REFERENCE_ID_COUNT = 222
REFERENCE_KEY_VALUES = {
    0: 67,
    1: 171,
    60: 778,
    67: 786,
    119: 863,
    151: 6103,
    169: 9070,
    170: 9071,
    171: 16716,
    181: 38009,
    219: 41030,
    220: 41031,
    221: 41032,
}

# Symbol entries and call sites are kept separate.  The call-site addresses
# below are internal instructions in the audited build, not function entries.
NATIVE_SYMBOL_ENTRIES = {
    "CplayData::SetAddonID(int,int,bool)": 0x421B4D4,
    "SoundMng::changeVolume(int,int)": 0x425EE68,
    "SoundMng::checkEnableSoundID(int)": 0x425EFC0,
    "SoundMng::wrapSndReq(int)": 0x425F09C,
    "SoundMng::wrapSndReqCh(int,int)": 0x425F254,
    "SoundMng::sndPlayReq(int,int,int)": 0x425FBDC,
    "SoundMng::play(int,int)": 0x42601C8,
    "SoundMng::play(unsigned char*,int,int)": 0x4260464,
}
NATIVE_CALL_SITES = (
    {
        "caller": "SoundMng::play(int,int)",
        "caller_entry": 0x42601C8,
        "call_site": 0x4260384,
        "callee": "SoundMng::sndPlayReq(int,int,int)",
    },
    {
        "caller": "SoundMng::sndPlayReq(int,int,int)",
        "caller_entry": 0x425FBDC,
        "call_site": 0x425FDE4,
        "callee": "SoundMng::wrapSndReq(int)",
    },
    {
        "caller": "SoundMng::wrapSndReq(int)",
        "caller_entry": 0x425F09C,
        "call_site": 0x425F15C,
        "callee": "SoundMng::changeVolume(int,int)",
    },
    {
        "caller": "SoundMng::wrapSndReq(int)",
        "caller_entry": 0x425F09C,
        "call_site": 0x425F190,
        "callee": "CSndMng::SndReq(int,int)",
    },
    {
        "caller": "SoundMng::wrapSndReqCh(int,int)",
        "caller_entry": 0x425F254,
        "call_site": 0x425F318,
        "callee": "SoundMng::changeVolume(int,int)",
    },
    {
        "caller": "SoundMng::wrapSndReqCh(int,int)",
        "caller_entry": 0x425F254,
        "call_site": 0x425F340,
        "callee": "CSndMng::SndReqCh(int,int,int)",
    },
)

DURATION_COLUMN_CANDIDATES = (
    "ogg_duration_sec",
    "duration_sec",
    "duration_seconds",
)
BANK_COLUMN_CANDIDATES = ("sound_bank", "bank")


def parse_int(value: str) -> int:
    """Parse a decimal or ``0x``-prefixed command-line integer."""

    return int(value, 0)


def gate_table_bytes(
    blob: bytes,
    *,
    file_offset: int = DEFAULT_TABLE_FILE_OFFSET,
    byte_length: int = DEFAULT_TABLE_BYTE_LENGTH,
) -> bytes:
    """Return a validated gate-table slice from ``blob``."""

    if file_offset < 0:
        raise ValueError("table file offset must be non-negative")
    if byte_length <= 0:
        raise ValueError("table byte length must be positive")
    if byte_length % GATE_ENTRY_SIZE:
        raise ValueError(
            f"table byte length must be divisible by {GATE_ENTRY_SIZE}"
        )
    end = file_offset + byte_length
    if end > len(blob):
        raise ValueError(
            "gate table extends past the library: "
            f"offset=0x{file_offset:x}, length=0x{byte_length:x}, "
            f"library_size=0x{len(blob):x}"
        )
    return blob[file_offset:end]


def parse_gate_ids(table: bytes) -> list[int]:
    """Decode a complete little-endian ``uint32`` gate table."""

    if not table:
        raise ValueError("gate table is empty")
    if len(table) % GATE_ENTRY_SIZE:
        raise ValueError(
            f"gate table length must be divisible by {GATE_ENTRY_SIZE}"
        )
    return [
        struct.unpack_from("<I", table, offset)[0]
        for offset in range(0, len(table), GATE_ENTRY_SIZE)
    ]


def extract_gate_ids(
    blob: bytes,
    *,
    file_offset: int = DEFAULT_TABLE_FILE_OFFSET,
    byte_length: int = DEFAULT_TABLE_BYTE_LENGTH,
) -> list[int]:
    """Read and decode the gate table from a library blob."""

    return parse_gate_ids(
        gate_table_bytes(blob, file_offset=file_offset, byte_length=byte_length)
    )


def ordered_unique(values: Iterable[int]) -> list[int]:
    """Return integers once each while preserving their first table order."""

    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def summarize_gate_ids(ids: Sequence[int]) -> dict[str, Any]:
    """Build deterministic table-order, uniqueness, and sorting metadata."""

    counts = Counter(ids)
    unique_table_order = ordered_unique(ids)
    duplicate_ids = [
        {"sound_resource_id": sound_id, "occurrence_count": counts[sound_id]}
        for sound_id in sorted(counts)
        if counts[sound_id] > 1
    ]
    return {
        "id_count": len(ids),
        "unique_id_count": len(unique_table_order),
        "ids_table_order": list(ids),
        "unique_ids_table_order": unique_table_order,
        "sorted_unique_ids": sorted(unique_table_order),
        "duplicate_ids": duplicate_ids,
    }


def compare_reference_table(table: bytes, ids: Sequence[int]) -> dict[str, Any]:
    """Compare a table with the audited versionCode 31 reference fingerprint."""

    table_sha256 = hashlib.sha256(table).hexdigest()
    key_checks = []
    for index, expected in REFERENCE_KEY_VALUES.items():
        actual = ids[index] if index < len(ids) else None
        key_checks.append(
            {
                "index": index,
                "expected": expected,
                "actual": actual,
                "matches": actual == expected,
            }
        )
    return {
        "reference_application_id": REFERENCE_APPLICATION_ID,
        "reference_version_name": REFERENCE_VERSION_NAME,
        "reference_version_code": REFERENCE_VERSION_CODE,
        "reference_table_sha256": REFERENCE_TABLE_SHA256,
        "actual_table_sha256": table_sha256,
        "reference_id_count": REFERENCE_ID_COUNT,
        "id_count_matches": len(ids) == REFERENCE_ID_COUNT,
        "sha256_matches": table_sha256 == REFERENCE_TABLE_SHA256,
        "key_value_checks": key_checks,
        "key_values_match": all(row["matches"] for row in key_checks),
        "reference_vector_matches": (
            len(ids) == REFERENCE_ID_COUNT
            and table_sha256 == REFERENCE_TABLE_SHA256
            and all(row["matches"] for row in key_checks)
        ),
    }


def native_call_chain_evidence() -> dict[str, Any]:
    """Render audited symbol entries and internal call sites unambiguously."""

    call_sites = []
    for row in NATIVE_CALL_SITES:
        caller_entry = int(row["caller_entry"])
        call_site = int(row["call_site"])
        call_sites.append(
            {
                "caller": row["caller"],
                "caller_symbol_entry": f"0x{caller_entry:x}",
                "call_site": f"0x{call_site:x}",
                "call_site_offset_from_entry": f"0x{call_site - caller_entry:x}",
                "callee": row["callee"],
            }
        )
    return {
        "version_specific": True,
        "symbol_entries": {
            symbol: f"0x{address:x}"
            for symbol, address in NATIVE_SYMBOL_ENTRIES.items()
        },
        "call_sites": call_sites,
        "warning": (
            "call_site values are internal instructions expressed relative to "
            "their caller symbol entry; they are not function entries"
        ),
    }


def make_csv_source(
    rows: Iterable[dict[str, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
    source: str = "<memory>",
    first_source_row_number: int = 2,
) -> dict[str, Any]:
    """Create an in-memory CSV source with explicit source-row provenance."""

    materialized = [dict(row) for row in rows]
    if fieldnames is None:
        discovered: list[str] = []
        for row in materialized:
            for key in row:
                if key not in discovered:
                    discovered.append(key)
        fieldnames = discovered
    normalized_fields = list(fieldnames)
    records = []
    for source_row_number, row in enumerate(
        materialized, start=first_source_row_number
    ):
        records.append(
            {
                "source_row_number": source_row_number,
                "values": {field: row.get(field, "") for field in normalized_fields},
            }
        )
    return {
        "source": source,
        "fieldnames": normalized_fields,
        "records": records,
    }


def read_csv_source(path: Path) -> dict[str, Any]:
    """Read a CSV while retaining its original columns and row numbers."""

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        rows = [dict(row) for row in reader]
        return make_csv_source(
            rows,
            fieldnames=reader.fieldnames,
            source=str(path.resolve()),
        )


def parse_record_id(value: Any) -> int:
    """Parse a CSV resource ID without silently accepting a blank value."""

    text = str(value).strip()
    if not text:
        raise ValueError("blank sound resource ID")
    try:
        return int(text, 0)
    except ValueError:
        return int(text, 10)


def index_csv_records(
    source: dict[str, Any],
    *,
    id_column: str,
) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Index CSV records by sound ID and retain malformed rows for audit."""

    if id_column not in source["fieldnames"]:
        raise ValueError(
            f"CSV {source['source']} has no required column {id_column!r}"
        )
    index: dict[int, list[dict[str, Any]]] = defaultdict(list)
    invalid: list[dict[str, Any]] = []
    for record in source["records"]:
        raw_value = record["values"].get(id_column, "")
        try:
            sound_id = parse_record_id(raw_value)
        except (TypeError, ValueError) as error:
            invalid.append(
                {
                    "source_row_number": record["source_row_number"],
                    "raw_value": raw_value,
                    "error": str(error),
                }
            )
            continue
        index[sound_id].append(record)
    return dict(index), invalid


def _first_present_column(
    fieldnames: Sequence[str], candidates: Sequence[str]
) -> str | None:
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    return None


def build_sound_record_report(
    ids: Sequence[int],
    source: dict[str, Any] | None,
    *,
    id_column: str = "sound_resource_id",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Join gate IDs to every exact matching sound-ID CSV record."""

    id_counts = Counter(ids)
    unique_ids = ordered_unique(ids)
    if source is None:
        mappings = [
            {
                "table_index": table_index,
                "sound_resource_id": sound_id,
                "gate_occurrence_count": id_counts[sound_id],
                "mapping_status": "not_requested",
                "record_match_count": 0,
                "records": [],
            }
            for table_index, sound_id in enumerate(ids)
        ]
        return (
            {
                "provided": False,
                "source": None,
                "source_record_count": 0,
                "id_column": id_column,
                "fieldnames": [],
                "matched_id_count": 0,
                "matched_record_count": 0,
                "unmapped_ids_table_order": [],
                "unmapped_ids_sorted": [],
                "unmapped_reason": "--sound-id-records was not provided",
                "invalid_id_records": [],
                "bank_statistics": {
                    "bank_column": None,
                    "record_counts": {},
                    "unique_id_counts": {},
                },
                "mappings": mappings,
            },
            mappings,
        )

    index, invalid_records = index_csv_records(source, id_column=id_column)
    mappings = []
    for table_index, sound_id in enumerate(ids):
        matches = index.get(sound_id, [])
        mappings.append(
            {
                "table_index": table_index,
                "sound_resource_id": sound_id,
                "gate_occurrence_count": id_counts[sound_id],
                "mapping_status": "matched" if matches else "unmapped",
                "record_match_count": len(matches),
                "records": matches,
            }
        )

    matched_ids = [sound_id for sound_id in unique_ids if index.get(sound_id)]
    unmapped = [sound_id for sound_id in unique_ids if not index.get(sound_id)]
    matched_records = [
        record for sound_id in matched_ids for record in index[sound_id]
    ]

    bank_column = _first_present_column(
        source["fieldnames"], BANK_COLUMN_CANDIDATES
    )
    bank_record_counts: Counter[str] = Counter()
    bank_unique_ids: dict[str, set[int]] = defaultdict(set)
    if bank_column is not None:
        for sound_id in matched_ids:
            for record in index[sound_id]:
                bank = str(record["values"].get(bank_column, "")).strip()
                if not bank:
                    bank = "<blank>"
                bank_record_counts[bank] += 1
                bank_unique_ids[bank].add(sound_id)

    report = {
        "provided": True,
        "source": source["source"],
        "id_column": id_column,
        "fieldnames": source["fieldnames"],
        "source_record_count": len(source["records"]),
        "matched_id_count": len(matched_ids),
        "matched_record_count": len(matched_records),
        "unmapped_ids_table_order": unmapped,
        "unmapped_ids_sorted": sorted(unmapped),
        "unmapped_reason": None,
        "invalid_id_records": invalid_records,
        "bank_statistics": {
            "bank_column": bank_column,
            "record_counts": dict(sorted(bank_record_counts.items())),
            "unique_id_counts": {
                bank: len(sound_ids)
                for bank, sound_ids in sorted(bank_unique_ids.items())
            },
        },
        "mappings": mappings,
    }
    return report, mappings


def _duration_columns(
    source: dict[str, Any] | None,
    explicit_columns: Sequence[str] | None,
) -> list[str]:
    if source is None:
        return []
    if explicit_columns:
        missing = [
            column for column in explicit_columns if column not in source["fieldnames"]
        ]
        if missing:
            raise ValueError(
                f"duration CSV {source['source']} is missing column(s): "
                + ", ".join(missing)
            )
        return list(explicit_columns)
    return [
        column
        for column in DURATION_COLUMN_CANDIDATES
        if column in source["fieldnames"]
    ]


def build_duration_report(
    ids: Sequence[int],
    source: dict[str, Any] | None,
    *,
    id_column: str = "sound_resource_id",
    duration_columns: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[int, list[float]]]:
    """Summarize one representative duration per unique gated sound ID.

    Multiple exact observations are retained per ID.  The maximum valid value
    is used as the representative duration, and conflicting values are exposed
    instead of silently hidden.
    """

    columns = _duration_columns(source, duration_columns)
    if source is None:
        return (
            {
                "available": False,
                "source": None,
                "id_column": id_column,
                "duration_columns": [],
                "aggregation": "maximum valid duration per unique sound ID",
                "unavailable_reason": "no duration source was provided",
                "unique_ids_with_duration": 0,
                "duration_observation_count": 0,
                "ge_10_sec": 0,
                "ge_30_sec": 0,
                "ge_60_sec": 0,
                "lt_3_sec": 0,
                "minimum_sec": None,
                "maximum_sec": None,
                "mean_sec": None,
                "median_sec": None,
                "conflicting_duration_ids": [],
                "invalid_duration_values": [],
                "duration_values_by_id": {},
            },
            {},
        )
    if not columns:
        return (
            {
                "available": False,
                "source": source["source"],
                "source_record_count": len(source["records"]),
                "id_column": id_column,
                "duration_columns": [],
                "aggregation": "maximum valid duration per unique sound ID",
                "unavailable_reason": (
                    "no supported duration column; pass --duration-column or "
                    "--duration-records with duration metadata"
                ),
                "unique_ids_with_duration": 0,
                "duration_observation_count": 0,
                "ge_10_sec": 0,
                "ge_30_sec": 0,
                "ge_60_sec": 0,
                "lt_3_sec": 0,
                "minimum_sec": None,
                "maximum_sec": None,
                "mean_sec": None,
                "median_sec": None,
                "conflicting_duration_ids": [],
                "invalid_duration_values": [],
                "duration_values_by_id": {},
            },
            {},
        )

    index, invalid_id_records = index_csv_records(source, id_column=id_column)
    gate_ids = ordered_unique(ids)
    values_by_id: dict[int, list[float]] = {}
    invalid_values: list[dict[str, Any]] = []
    observation_count = 0
    for sound_id in gate_ids:
        observations: list[float] = []
        for record in index.get(sound_id, []):
            for column in columns:
                raw = str(record["values"].get(column, "")).strip()
                if not raw:
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    invalid_values.append(
                        {
                            "sound_resource_id": sound_id,
                            "source_row_number": record["source_row_number"],
                            "column": column,
                            "raw_value": raw,
                            "error": "not a floating-point number",
                        }
                    )
                    continue
                if not math.isfinite(value) or value < 0:
                    invalid_values.append(
                        {
                            "sound_resource_id": sound_id,
                            "source_row_number": record["source_row_number"],
                            "column": column,
                            "raw_value": raw,
                            "error": "duration must be finite and non-negative",
                        }
                    )
                    continue
                observations.append(value)
                observation_count += 1
        if observations:
            values_by_id[sound_id] = sorted(set(observations))

    representative = {
        sound_id: max(values) for sound_id, values in values_by_id.items()
    }
    representatives = list(representative.values())
    conflicts = [
        {"sound_resource_id": sound_id, "values_sec": values}
        for sound_id, values in sorted(values_by_id.items())
        if len(values) > 1
    ]
    report = {
        "available": bool(representatives),
        "source": source["source"],
        "source_record_count": len(source["records"]),
        "id_column": id_column,
        "duration_columns": columns,
        "aggregation": "maximum valid duration per unique sound ID",
        "unavailable_reason": None if representatives else "no valid durations",
        "unique_ids_with_duration": len(representatives),
        "duration_observation_count": observation_count,
        "ge_10_sec": sum(value >= 10 for value in representatives),
        "ge_30_sec": sum(value >= 30 for value in representatives),
        "ge_60_sec": sum(value >= 60 for value in representatives),
        "lt_3_sec": sum(value < 3 for value in representatives),
        "minimum_sec": min(representatives) if representatives else None,
        "maximum_sec": max(representatives) if representatives else None,
        "mean_sec": statistics.fmean(representatives) if representatives else None,
        "median_sec": statistics.median(representatives)
        if representatives
        else None,
        "conflicting_duration_ids": conflicts,
        "invalid_id_records": invalid_id_records,
        "invalid_duration_values": invalid_values,
        "duration_values_by_id": {
            str(sound_id): values
            for sound_id, values in sorted(values_by_id.items())
        },
    }
    return report, values_by_id


def flatten_gate_rows(
    mappings: Sequence[dict[str, Any]],
    *,
    record_fieldnames: Sequence[str],
    duration_values_by_id: dict[int, list[float]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Flatten exact record mappings into a stable audit CSV."""

    base_fields = [
        "gate_table_index",
        "sound_resource_id",
        "sound_resource_id_hex",
        "gate_occurrence_count",
        "mapping_status",
        "record_match_count",
        "record_match_index",
        "record_source_row_number",
        "duration_values_sec",
        "representative_duration_sec",
    ]
    record_fields = [f"record_{field}" for field in record_fieldnames]
    rows: list[dict[str, Any]] = []
    for mapping in mappings:
        sound_id = int(mapping["sound_resource_id"])
        durations = duration_values_by_id.get(sound_id, [])
        common = {
            "gate_table_index": mapping["table_index"],
            "sound_resource_id": sound_id,
            "sound_resource_id_hex": f"0x{sound_id:x}",
            "gate_occurrence_count": mapping["gate_occurrence_count"],
            "mapping_status": mapping["mapping_status"],
            "record_match_count": mapping["record_match_count"],
            "duration_values_sec": ";".join(f"{value:.9g}" for value in durations),
            "representative_duration_sec": max(durations) if durations else "",
        }
        records = mapping["records"]
        if not records:
            rows.append(
                {
                    **common,
                    "record_match_index": "",
                    "record_source_row_number": "",
                    **{field: "" for field in record_fields},
                }
            )
            continue
        for record_match_index, record in enumerate(records):
            rows.append(
                {
                    **common,
                    "record_match_index": record_match_index,
                    "record_source_row_number": record["source_row_number"],
                    **{
                        f"record_{field}": record["values"].get(field, "")
                        for field in record_fieldnames
                    },
                }
            )
    return rows, base_fields + record_fields


def build_gate_report(
    blob: bytes,
    *,
    lib_path: str,
    table_file_offset: int = DEFAULT_TABLE_FILE_OFFSET,
    table_byte_length: int = DEFAULT_TABLE_BYTE_LENGTH,
    sound_source: dict[str, Any] | None = None,
    sound_id_column: str = "sound_resource_id",
    duration_source: dict[str, Any] | None = None,
    duration_id_column: str = "sound_resource_id",
    duration_columns: Sequence[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Build JSON and flattened CSV evidence without filesystem writes."""

    table = gate_table_bytes(
        blob,
        file_offset=table_file_offset,
        byte_length=table_byte_length,
    )
    ids = parse_gate_ids(table)
    vector = summarize_gate_ids(ids)
    sound_report, mappings = build_sound_record_report(
        ids, sound_source, id_column=sound_id_column
    )

    effective_duration_source = duration_source
    duration_source_role = "explicit_duration_records"
    if effective_duration_source is None and sound_source is not None:
        effective_duration_source = sound_source
        duration_source_role = "sound_id_records"
    elif effective_duration_source is None:
        duration_source_role = "none"
    duration_report, duration_values_by_id = build_duration_report(
        ids,
        effective_duration_source,
        id_column=duration_id_column
        if duration_source is not None
        else sound_id_column,
        duration_columns=duration_columns,
    )
    duration_report["source_role"] = duration_source_role

    rows, csv_fieldnames = flatten_gate_rows(
        mappings,
        record_fieldnames=sound_source["fieldnames"] if sound_source else [],
        duration_values_by_id=duration_values_by_id,
    )
    reference = compare_reference_table(table, ids)
    actual_library_sha256 = hashlib.sha256(blob).hexdigest()
    reference.update(
        {
            "reference_library_sha256": REFERENCE_LIBRARY_SHA256,
            "actual_library_sha256": actual_library_sha256,
            "library_sha256_matches": (
                actual_library_sha256 == REFERENCE_LIBRARY_SHA256
            ),
        }
    )
    reference["audited_v31_library_and_table_match"] = bool(
        reference["reference_vector_matches"]
        and reference["library_sha256_matches"]
    )
    document = {
        "schema_version": 1,
        "evidence_kind": "read_only_static_sound_pack_gate",
        "safety": {
            "read_only": True,
            "process_attachment": False,
            "authorization_write_supported": False,
            "warning": (
                "Audit evidence only. Do not write these offsets, spoof an "
                "entitlement, or bypass an in-app purchase."
            ),
        },
        "lib": lib_path,
        "lib_size": len(blob),
        "lib_sha256": actual_library_sha256,
        "table": {
            "file_offset": f"0x{table_file_offset:x}",
            "file_offset_decimal": table_file_offset,
            "byte_length": table_byte_length,
            "byte_length_hex": f"0x{table_byte_length:x}",
            "entry_layout": "uint32_le sound_resource_id",
            "entry_size": GATE_ENTRY_SIZE,
            "table_sha256": hashlib.sha256(table).hexdigest(),
            **vector,
        },
        "entitlement_static_evidence": {
            "entitlement_index": ENTITLEMENT_INDEX,
            "entitlement_label": "Sound Pack",
            "offset_base": "CplayData instance",
            "active_addon_array_offset": f"0x{ACTIVE_ADDON_ARRAY_OFFSET:x}",
            "saved_addon_array_offset": f"0x{SAVED_ADDON_ARRAY_OFFSET:x}",
            "active_sound_pack_offset": f"0x{ACTIVE_SOUND_PACK_OFFSET:x}",
            "saved_sound_pack_offset": f"0x{SAVED_SOUND_PACK_OFFSET:x}",
            "version_specific": True,
            "warning": (
                "These CplayData-relative offsets are version-specific static "
                "evidence. They are not authorization-write targets."
            ),
        },
        "native_call_chain_static_evidence": native_call_chain_evidence(),
        "reference_comparison": reference,
        "sound_id_records": sound_report,
        "duration_statistics": duration_report,
    }
    return document, rows, csv_fieldnames


def is_audited_v31_reference_match(document: dict[str, Any]) -> bool:
    """Return true only for the complete known library and its exact table."""

    comparison = document.get("reference_comparison")
    table = document.get("table")
    if not isinstance(comparison, dict) or not isinstance(table, dict):
        return False
    return bool(
        comparison.get("reference_vector_matches") is True
        and comparison.get("library_sha256_matches") is True
        and comparison.get("actual_library_sha256") == REFERENCE_LIBRARY_SHA256
        and comparison.get("reference_library_sha256") == REFERENCE_LIBRARY_SHA256
        and document.get("lib_sha256") == REFERENCE_LIBRARY_SHA256
        and comparison.get("actual_table_sha256") == REFERENCE_TABLE_SHA256
        and comparison.get("reference_table_sha256") == REFERENCE_TABLE_SHA256
        and table.get("table_sha256") == REFERENCE_TABLE_SHA256
    )


def enforce_reference_policy(
    document: dict[str, Any], *, allow_unmatched_reference: bool = False
) -> None:
    """Fail closed when fixed offsets do not match the audited library table."""

    reference_matches = is_audited_v31_reference_match(document)
    if reference_matches or allow_unmatched_reference:
        return
    comparison = document["reference_comparison"]
    raise ValueError(
        "library and fixed-offset table do not both match the audited "
        "versionCode 31 reference fingerprints: "
        f"actual_library={comparison.get('actual_library_sha256')}, "
        f"expected_library={comparison.get('reference_library_sha256')}, "
        f"actual={comparison['actual_table_sha256']}, "
        f"expected={comparison['reference_table_sha256']}. "
        "Refusing to label arbitrary bytes as the Sound Pack gate. Use "
        "--allow-unmatched-reference only for an explicitly reviewed new build."
    )


def write_gate_outputs(
    out_dir: Path,
    document: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    csv_fieldnames: Sequence[str],
    *,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Write deterministic JSON and CSV audit artifacts."""

    json_path = out_dir / "sound_pack_gate.json"
    csv_path = out_dir / "sound_pack_gate.csv"
    existing = [path for path in (json_path, csv_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "refusing to overwrite existing audit output(s): "
            + ", ".join(str(path) for path in existing)
            + "; pass --overwrite-outputs only after reviewing provenance"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_fieldnames))
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the version-specific Sound Pack sound-ID gate from a local "
            "libGameProc.so and emit auditable JSON/CSV."
        )
    )
    parser.add_argument("--lib", required=True, type=Path)
    parser.add_argument("--sound-id-records", type=Path)
    parser.add_argument("--duration-records", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--table-file-offset",
        type=parse_int,
        default=DEFAULT_TABLE_FILE_OFFSET,
        help="raw library file offset (default: 0x14458dc)",
    )
    parser.add_argument(
        "--table-byte-length",
        type=parse_int,
        default=DEFAULT_TABLE_BYTE_LENGTH,
        help="gate table byte length (default: 0x378)",
    )
    parser.add_argument("--sound-id-column", default="sound_resource_id")
    parser.add_argument("--duration-id-column", default="sound_resource_id")
    parser.add_argument(
        "--overwrite-outputs",
        action="store_true",
        help="replace existing sound_pack_gate.json/csv after provenance review",
    )
    parser.add_argument(
        "--allow-unmatched-reference",
        action="store_true",
        help=(
            "allow an explicitly experimental output when the audited v31 "
            "table fingerprint does not match; default is fail-closed with no output"
        ),
    )
    parser.add_argument(
        "--duration-column",
        action="append",
        dest="duration_columns",
        help=(
            "duration column to use; repeat for multiple columns. Without this "
            "option ogg_duration_sec/duration_sec/duration_seconds are detected."
        ),
    )
    args = parser.parse_args()

    blob = args.lib.read_bytes()
    sound_source = (
        read_csv_source(args.sound_id_records) if args.sound_id_records else None
    )
    duration_source = (
        read_csv_source(args.duration_records) if args.duration_records else None
    )
    document, rows, csv_fieldnames = build_gate_report(
        blob,
        lib_path=str(args.lib.resolve()),
        table_file_offset=args.table_file_offset,
        table_byte_length=args.table_byte_length,
        sound_source=sound_source,
        sound_id_column=args.sound_id_column,
        duration_source=duration_source,
        duration_id_column=args.duration_id_column,
        duration_columns=args.duration_columns,
    )
    if args.sound_id_records:
        document["sound_id_records"]["source_sha256"] = hashlib.sha256(
            args.sound_id_records.read_bytes()
        ).hexdigest()
    if args.duration_records:
        document["duration_statistics"]["source_sha256"] = hashlib.sha256(
            args.duration_records.read_bytes()
        ).hexdigest()

    table_matches = bool(
        document["reference_comparison"]["reference_vector_matches"]
    )
    reference_matches = is_audited_v31_reference_match(document)
    experimental_status = (
        "experimental_table_match_only"
        if table_matches
        else "experimental_unmatched_reference"
    )
    document["reference_policy"] = {
        "audited_reference_required_by_default": True,
        "reference_vector_matches": table_matches,
        "library_sha256_matches": document["reference_comparison"][
            "library_sha256_matches"
        ],
        "audited_v31_library_and_table_match": reference_matches,
        "allow_unmatched_reference_requested": bool(args.allow_unmatched_reference),
        "audit_status": (
            "audited_v31_reference_match"
            if reference_matches
            else experimental_status
        ),
    }
    if not reference_matches and not args.allow_unmatched_reference:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        "audited v31 library/table reference fingerprint mismatch"
                    ),
                    "output_written": False,
                    "hint": (
                        "verify the version-matched library; use "
                        "--allow-unmatched-reference only for explicitly experimental research"
                    ),
                    "reference_comparison": document["reference_comparison"],
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 4

    try:
        json_path, csv_path = write_gate_outputs(
            args.out_dir,
            document,
            rows,
            csv_fieldnames,
            overwrite=args.overwrite_outputs,
        )
    except FileExistsError as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "ok": reference_matches,
                "experimental": not reference_matches,
                "read_only": True,
                "lib_sha256": document["lib_sha256"],
                "table_sha256": document["table"]["table_sha256"],
                "id_count": document["table"]["id_count"],
                "unique_id_count": document["table"]["unique_id_count"],
                "matched_id_count": document["sound_id_records"][
                    "matched_id_count"
                ],
                "unmapped_id_count": len(
                    document["sound_id_records"]["unmapped_ids_sorted"]
                ),
                "reference_vector_matches": document["reference_comparison"][
                    "reference_vector_matches"
                ],
                "library_sha256_matches": document["reference_comparison"][
                    "library_sha256_matches"
                ],
                "unmatched_reference_allowed": args.allow_unmatched_reference,
                "json": str(json_path),
                "csv": str(csv_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
