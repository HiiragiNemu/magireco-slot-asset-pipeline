#!/usr/bin/env python3
"""Join runtime CSL snapshots to the audited Sound Pack gate.

The tool is deliberately read-only with respect to the game.  It consumes
already captured natural-hunt journals, the version-matched static gate audit,
the read-only addon snapshot, and the extracted sound request table.  It never
attaches to a process and never changes entitlement or volume state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "magireco-runtime-sound-pack-audit-v1"
CSV_NAME = "runtime_sound_pack_rows.csv"
PRE_GATE_CSV_NAME = "runtime_sound_pack_pre_gate_volume_rows.csv"
JSON_NAME = "runtime_sound_pack_audit.json"

REFERENCE_GAME_PROC_SHA256 = (
    "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
)
REFERENCE_ARM64_APK_SHA256 = (
    "89ACC81D02FF63697603FCE2E5F4281850C092FA833FD8CF3E636B44AB624E24"
)
REFERENCE_LIB_AMAIN_SHA256 = (
    "58E3F7A9DBCE2E3D79D1A5A30F1DBFEEAC5BB4712BD4D8FF4E6328D2631DCA5D"
)
REFERENCE_GATE_TABLE_SHA256 = (
    "C18955F4CD09F18CBA179AA19D432864026C1591243C9AB7F134FC7347153FDC"
)
REFERENCE_GATE_ID_COUNT = 222
REFERENCE_GATE_KEYS = {
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
REFERENCE_GATE_TABLE_OFFSET = 0x14458DC
REFERENCE_GATE_TABLE_BYTE_LENGTH = 0x378
REFERENCE_CHANGE_VOLUME_OFFSET = "0x425ee68"
REFERENCE_ACCESSOR_OFFSETS = {
    "cslMngSndGetId": "0x1308c0",
    "cslMngSndGetChannel": "0x130888",
    "cslMngSndGetTime": "0x130934",
    "cslMngSndGetLoopNum": "0x1309a8",
    "cslMngSndGetPriority": "0x130d04",
    "cslMngSndGetLoopF": "0x130d60",
    "cslMngSndGetWaitF": "0x130dbc",
    "cslMngSndGetPauseF": "0x130e18",
}
REFERENCE_CALC_OFFSET = "0x12f7c8"
REFERENCE_STATIC_SNAPSHOT = {
    "game_proc_sha256": REFERENCE_GAME_PROC_SHA256,
    "arm64_apk_sha256": REFERENCE_ARM64_APK_SHA256,
    "lib_amain_sha256": REFERENCE_LIB_AMAIN_SHA256,
    "abi": "aarch64-aapcs64",
    "csl_active_slot_layout": {
        "vector_begin_offset": "0xa0",
        "vector_end_offset": "0xa8",
        "stride": "0x38",
        "source_constructor_offset": "0x12f004",
    },
}
DIRECT_REQUEST_CALLER_OFFSETS = {"0x425f160", "0x425f31c"}
VOLUME_CONTROL_CALLER_OFFSET = "0x425f918"
VOLUME_CONTROL_REASONS = {
    "first_observed_volume_control_state",
    "volume_control_state_changed",
}
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")


class AuditError(RuntimeError):
    """Input or provenance failure that must not produce audit outputs."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"expected a JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, 1):
                if not raw.strip():
                    continue
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise AuditError(
                        f"journal row {line_number} is not an object: {path}"
                    )
                rows.append(value)
    except AuditError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read journal {path}: {exc}") from exc
    if not rows:
        raise AuditError(f"journal is empty: {path}")
    return rows


def _as_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise AuditError(f"{field} must be an integer, not bool")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AuditError(f"{field} is not an integer: {value!r}") from exc


def _bounded_int(
    value: Any, *, field: str, minimum: int, maximum: int
) -> int:
    parsed = _as_int(value, field=field)
    if parsed < minimum or parsed > maximum:
        raise AuditError(
            f"{field} is outside [{minimum}, {maximum}]: {parsed}"
        )
    return parsed


def _exact_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise AuditError(f"{field} must be a JSON boolean")
    return value


def _normalized_hex(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise AuditError(f"{field} must be a hexadecimal string")
    try:
        parsed = int(value, 16)
    except ValueError as exc:
        raise AuditError(f"{field} is not hexadecimal: {value!r}") from exc
    if parsed < 0:
        raise AuditError(f"{field} must be non-negative")
    return f"0x{parsed:x}"


def _require_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise AuditError(f"{field} is not a complete SHA-256")
    return value.upper()


def _require_exact(value: Any, expected: Any, *, field: str) -> None:
    if value != expected:
        raise AuditError(f"{field} mismatch: actual={value!r}, expected={expected!r}")


def _validate_gate_reference_metadata(
    gate: dict[str, Any], ids: list[int], computed_table_sha256: str
) -> None:
    table = gate["table"]
    _require_exact(gate.get("schema_version"), 1, field="gate schema_version")
    _require_exact(
        gate.get("evidence_kind"),
        "read_only_static_sound_pack_gate",
        field="gate evidence_kind",
    )
    safety = gate.get("safety")
    if not isinstance(safety, dict) or safety.get("read_only") is not True:
        raise AuditError("Sound Pack gate is not marked read-only")
    _require_exact(
        _require_sha256(gate.get("lib_sha256"), field="gate lib_sha256"),
        REFERENCE_GAME_PROC_SHA256,
        field="gate complete library SHA-256",
    )
    _require_exact(
        _normalized_hex(table.get("file_offset"), field="gate table file_offset"),
        f"0x{REFERENCE_GATE_TABLE_OFFSET:x}",
        field="gate table file_offset",
    )
    _require_exact(
        _as_int(table.get("file_offset_decimal"), field="gate file_offset_decimal"),
        REFERENCE_GATE_TABLE_OFFSET,
        field="gate file_offset_decimal",
    )
    _require_exact(
        _as_int(table.get("byte_length"), field="gate table byte_length"),
        REFERENCE_GATE_TABLE_BYTE_LENGTH,
        field="gate table byte_length",
    )
    _require_exact(
        _as_int(table.get("entry_size"), field="gate table entry_size"),
        4,
        field="gate table entry_size",
    )
    _require_exact(
        _require_sha256(table.get("table_sha256"), field="gate table_sha256"),
        computed_table_sha256,
        field="gate declared/recomputed table SHA-256",
    )
    _require_exact(
        computed_table_sha256,
        REFERENCE_GATE_TABLE_SHA256,
        field="gate audited v31 table SHA-256",
    )
    for field_name in ("id_count", "unique_id_count"):
        _require_exact(
            _as_int(table.get(field_name), field=f"gate table {field_name}"),
            REFERENCE_GATE_ID_COUNT,
            field=f"gate table {field_name}",
        )
    for index, expected in REFERENCE_GATE_KEYS.items():
        _require_exact(ids[index], expected, field=f"gate ID at index {index}")

    reference = gate.get("reference_comparison")
    policy = gate.get("reference_policy")
    if not isinstance(reference, dict) or not isinstance(policy, dict):
        raise AuditError("Sound Pack gate lacks reference provenance")
    for field_name, expected in (
        ("reference_application_id", "com.universal777.magireco"),
        ("reference_version_name", "1.0.0"),
        ("reference_version_code", 31),
        ("reference_id_count", REFERENCE_GATE_ID_COUNT),
    ):
        _require_exact(
            reference.get(field_name), expected, field=f"gate reference {field_name}"
        )
    _require_exact(
        _require_sha256(
            reference.get("reference_table_sha256"),
            field="reference_table_sha256",
        ),
        REFERENCE_GATE_TABLE_SHA256,
        field="reference_table_sha256",
    )
    _require_exact(
        _require_sha256(
            reference.get("actual_table_sha256"), field="actual_table_sha256"
        ),
        computed_table_sha256,
        field="actual_table_sha256",
    )
    for truth_field in (
        "id_count_matches",
        "sha256_matches",
        "key_values_match",
        "reference_vector_matches",
    ):
        _require_exact(reference.get(truth_field), True, field=truth_field)
    declared_checks = reference.get("key_value_checks")
    expected_checks = [
        {"index": index, "expected": expected, "actual": expected, "matches": True}
        for index, expected in REFERENCE_GATE_KEYS.items()
    ]
    _require_exact(
        declared_checks, expected_checks, field="gate reference key_value_checks"
    )
    _require_exact(
        policy.get("audit_status"),
        "audited_v31_reference_match",
        field="gate reference policy",
    )
    if "library_sha256_matches" in reference:
        _require_exact(
            reference.get("library_sha256_matches"),
            True,
            field="gate reference library_sha256_matches",
        )
    if "audited_v31_library_and_table_match" in reference:
        _require_exact(
            reference.get("audited_v31_library_and_table_match"),
            True,
            field="gate audited library/table match",
        )
    if "library_sha256_matches" in policy:
        _require_exact(
            policy.get("library_sha256_matches"),
            True,
            field="gate policy library_sha256_matches",
        )


def _validate_sound_probe_ready(
    session: dict[str, Any], journal_path: Path, *, require_pre_gate: bool
) -> bool:
    loaded = session.get("loaded_probe_sources")
    if not isinstance(loaded, dict) or not isinstance(loaded.get("sound_logic"), dict):
        raise AuditError(f"session_ready lacks loaded sound_logic probe: {journal_path}")
    sound_source = loaded["sound_logic"]
    _bounded_int(
        sound_source.get("bytes"),
        field="loaded sound_logic bytes",
        minimum=1,
        maximum=16 * 1024 * 1024,
    )
    _require_sha256(sound_source.get("sha256"), field="loaded sound_logic sha256")

    payloads = session.get("probe_ready_payloads")
    if not isinstance(payloads, dict) or not isinstance(payloads.get("sound_logic"), dict):
        raise AuditError(f"session_ready lacks sound_logic ready payload: {journal_path}")
    ready = payloads["sound_logic"]
    _require_exact(ready.get("kind"), "sound_logic_probe_ready", field="sound ready kind")
    _bounded_int(
        ready.get("installed_hook_event_count"),
        field="installed sound hook count",
        minimum=7,
        maximum=128,
    )
    _require_exact(
        _as_int(ready.get("unavailable_hook_event_count"), field="unavailable hook count"),
        0,
        field="unavailable sound hook count",
    )
    _require_exact(
        _as_int(ready.get("attach_error_event_count"), field="attach error hook count"),
        0,
        field="sound attach error count",
    )
    _require_exact(
        ready.get("outer_bgm_snapshot_accessors_ready"),
        True,
        field="outer BGM snapshot accessors ready",
    )

    accessors = ready.get("outer_bgm_snapshot_accessor_status")
    if not isinstance(accessors, dict):
        raise AuditError("sound ready payload lacks accessor status")
    _validate_accessor_status(accessors)
    calc = ready.get("outer_bgm_snapshot_calc_entry_status")
    if not isinstance(calc, dict):
        raise AuditError("sound ready payload lacks CSL Calc status")
    _require_ready_offset(calc, REFERENCE_CALC_OFFSET, field="CSLMng::Calc")

    # Snapshot evidence predates the optional pre-gate observer in some valid
    # journals.  Do not let an unused legacy observer payload contaminate or
    # invalidate the independently versioned CSL snapshot path.  A journal
    # that contributes any pre-gate event takes the strict branch below.
    if not require_pre_gate:
        return False

    pre_gate = ready.get("sound_pack_pre_gate_status")
    if not isinstance(pre_gate, dict):
        if require_pre_gate:
            raise AuditError("sound ready payload lacks Sound Pack pre-gate status")
        return False
    for field_name, expected in (
        ("status", "ready"),
        ("symbol", "_ZN8SoundMng12changeVolumeEii"),
        ("gate_table_offset", f"0x{REFERENCE_GATE_TABLE_OFFSET:x}"),
        ("gate_table_entry_count", REFERENCE_GATE_ID_COUNT),
        ("gate_table_strictly_increasing_unique", True),
        ("read_only_observer", True),
    ):
        _require_exact(
            pre_gate.get(field_name), expected, field=f"pre-gate ready {field_name}"
        )
    _require_ready_offset(pre_gate, REFERENCE_CHANGE_VOLUME_OFFSET, field="changeVolume")
    expected_checks = [
        {"index": index, "expected": expected, "actual": expected, "matches": True}
        for index, expected in REFERENCE_GATE_KEYS.items()
    ]
    _require_exact(
        pre_gate.get("gate_table_key_checks"),
        expected_checks,
        field="runtime pre-gate key parity",
    )
    return True


def _require_ready_offset(row: dict[str, Any], expected: str, *, field: str) -> None:
    _require_exact(row.get("status"), "ready", field=f"{field} status")
    actual_offset = _normalized_hex(
        row.get("actual_module_offset"), field=f"{field} actual offset"
    )
    expected_offset = _normalized_hex(
        row.get("expected_module_offset"), field=f"{field} expected offset"
    )
    _require_exact(actual_offset, expected, field=f"{field} actual offset")
    _require_exact(expected_offset, expected, field=f"{field} expected offset")
    _require_exact(
        row.get("module_offset_matches_static_reference"),
        True,
        field=f"{field} offset match",
    )


def _validate_accessor_status(accessors: dict[str, Any]) -> None:
    _require_exact(
        set(accessors), set(REFERENCE_ACCESSOR_OFFSETS), field="CSL accessor key set"
    )
    for key, expected_offset in REFERENCE_ACCESSOR_OFFSETS.items():
        row = accessors.get(key)
        if not isinstance(row, dict):
            raise AuditError(f"CSL accessor {key} status is not an object")
        _require_ready_offset(row, expected_offset, field=key)


def _validate_snapshot_static_reference(snapshot: dict[str, Any]) -> None:
    _require_exact(
        snapshot.get("static_reference"),
        REFERENCE_STATIC_SNAPSHOT,
        field="active-sound snapshot static_reference",
    )
    for field_name, expected in (
        ("snapshot_execution_source", "cslMngCalc_on_enter"),
        ("snapshot_runs_on_csl_calc_thread", True),
        ("vector_begin_offset", 0xA0),
        ("vector_end_offset", 0xA8),
        ("active_slot_stride", 0x38),
        ("maximum_captured_slots", 128),
        ("capture_cap_is_declared_game_limit", False),
        (
            "classification_rule",
            "active_transport_state_only_csl_resource_table_channel_zero_is_not_bgm_proof",
        ),
    ):
        _require_exact(
            snapshot.get(field_name), expected, field=f"snapshot {field_name}"
        )
    accessors = snapshot.get("accessor_status")
    if not isinstance(accessors, dict):
        raise AuditError("active-sound snapshot lacks accessor_status")
    _validate_accessor_status(accessors)


def _load_gate(path: Path) -> tuple[dict[str, Any], list[int], dict[int, int]]:
    gate = _load_json(path)
    table = gate.get("table")
    if not isinstance(table, dict):
        raise AuditError("Sound Pack gate lacks table data")
    raw_ids = table.get("ids_table_order")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise AuditError("Sound Pack gate has no table IDs")
    ids = [_as_int(item, field="gate table ID") for item in raw_ids]
    if len(ids) != REFERENCE_GATE_ID_COUNT:
        raise AuditError(
            f"Sound Pack gate must contain all {REFERENCE_GATE_ID_COUNT} v31 IDs"
        )
    for index, sound_id in enumerate(ids):
        _bounded_int(
            sound_id,
            field=f"gate table ID[{index}]",
            minimum=0,
            maximum=0xFFFFFFFF,
        )
    if len(ids) != len(set(ids)):
        raise AuditError("Sound Pack gate table contains duplicate IDs")
    if ids != sorted(ids):
        raise AuditError("Sound Pack gate table is not strictly increasing")
    packed = struct.pack(f"<{len(ids)}I", *ids)
    computed_table_sha256 = hashlib.sha256(packed).hexdigest().upper()
    _validate_gate_reference_metadata(gate, ids, computed_table_sha256)
    return gate, ids, {sound_id: index for index, sound_id in enumerate(ids)}


def _load_addon(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    addon = _load_json(path)
    if addon.get("schema") != "magireco-addon-entitlement-snapshot-v1":
        raise AuditError("unexpected addon snapshot schema")
    if addon.get("ok") is not True:
        raise AuditError("addon snapshot is not successful")
    sound_pack_index = _as_int(
        addon.get("sound_pack_candidate_index"), field="sound_pack_candidate_index"
    )
    _require_exact(sound_pack_index, 6, field="Sound Pack entitlement index")
    process = addon.get("process")
    if not isinstance(process, dict):
        raise AuditError("addon snapshot lacks process provenance")
    _require_exact(process.get("arch"), "arm64", field="addon process arch")
    _require_exact(process.get("pointer_size"), 8, field="addon pointer size")
    _require_exact(
        addon.get("active_addon_base_offset"),
        "0x14bf4",
        field="addon active base offset",
    )
    _require_exact(
        addon.get("saved_addon_base_offset"),
        "0x14a58",
        field="addon saved base offset",
    )
    rows = addon.get("rows")
    if not isinstance(rows, list) or len(rows) != 7:
        raise AuditError("addon snapshot must contain all seven addon rows")
    if [row.get("index") for row in rows if isinstance(row, dict)] != list(range(7)):
        raise AuditError("addon snapshot row indices are not exactly 0..6")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AuditError(f"addon row {index} is not an object")
        _require_exact(
            _normalized_hex(row.get("active_offset"), field="addon active offset"),
            f"0x{0x14BF4 + index * 4:x}",
            field=f"addon row {index} active offset",
        )
        _require_exact(
            _normalized_hex(row.get("saved_offset"), field="addon saved offset"),
            f"0x{0x14A58 + index * 4:x}",
            field=f"addon row {index} saved offset",
        )
        _bounded_int(
            row.get("active_u32"),
            field=f"addon row {index} active_u32",
            minimum=0,
            maximum=1,
        )
        _bounded_int(
            row.get("saved_u32"),
            field=f"addon row {index} saved_u32",
            minimum=0,
            maximum=1,
        )
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and _as_int(row.get("index"), field="addon row index") == sound_pack_index
    ]
    if len(matches) != 1:
        raise AuditError("addon snapshot does not contain exactly one Sound Pack row")
    selected = matches[0]
    if selected.get("active_read_error") or selected.get("saved_read_error"):
        raise AuditError("Sound Pack addon fields have read errors")
    _bounded_int(
        selected.get("active_u32"),
        field="Sound Pack active_u32",
        minimum=0,
        maximum=1,
    )
    _bounded_int(
        selected.get("saved_u32"),
        field="Sound Pack saved_u32",
        minimum=0,
        maximum=1,
    )
    return addon, selected


def _load_sound_rows(path: Path) -> dict[int, list[dict[str, str]]]:
    by_id: dict[int, list[dict[str, str]]] = {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "sound_resource_id" not in reader.fieldnames:
                raise AuditError("sound request CSV lacks sound_resource_id")
            for source_row_number, row in enumerate(reader, 2):
                raw_id = (row.get("sound_resource_id") or "").strip()
                if not raw_id:
                    continue
                sound_id = _as_int(raw_id, field="sound_resource_id")
                clean = {str(key): str(value or "") for key, value in row.items()}
                clean["source_row_number"] = str(source_row_number)
                by_id.setdefault(sound_id, []).append(clean)
    except AuditError:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise AuditError(f"cannot read sound request CSV {path}: {exc}") from exc
    return by_id


def _snapshot_valid(snapshot: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if snapshot.get("schema") != "magireco-csl-active-sound-snapshot-v1":
        reasons.append("unexpected_schema")
    if snapshot.get("available") is not True:
        reasons.append("unavailable")
    if snapshot.get("truncated") is True:
        reasons.append("truncated")
    declared = snapshot.get("declared_slot_count")
    captured = snapshot.get("captured_slot_count")
    if declared is not None and captured is not None and declared != captured:
        reasons.append("declared_captured_count_mismatch")
    if snapshot.get("snapshot_runs_on_csl_calc_thread") is not True:
        reasons.append("not_on_csl_calc_thread")
    if snapshot.get("snapshot_hook_detached") is not True:
        reasons.append("snapshot_hook_not_detached")
    if not reasons:
        _validate_snapshot_static_reference(snapshot)
    return not reasons, reasons


def _validate_session_ready(
    session: dict[str, Any], journal_path: Path, *, require_pre_gate: bool
) -> bool:
    _require_exact(
        session.get("schema"),
        "magireco-natural-sp-story-hunt-session-v1",
        field="hunt session schema",
    )
    _require_exact(session.get("event"), "session_ready", field="hunt session event")
    pre_gate_capability_verified = _validate_sound_probe_ready(
        session, journal_path, require_pre_gate=require_pre_gate
    )
    initial_snapshot = session.get("initial_outer_bgm_active_sound_snapshot")
    if not isinstance(initial_snapshot, dict):
        raise AuditError(f"session_ready lacks initial sound snapshot: {journal_path}")
    _require_exact(
        initial_snapshot.get("label"), "session_ready", field="initial snapshot label"
    )
    valid, reasons = _snapshot_valid(initial_snapshot)
    if not valid:
        raise AuditError(
            f"session_ready initial sound snapshot is invalid: {','.join(reasons)}"
        )
    return pre_gate_capability_verified


def _validated_pre_gate_event(
    event: dict[str, Any], *, gate_index: dict[int, int], active_value: int
) -> dict[str, Any]:
    sound_id = _bounded_int(
        event.get("sound_resource_id_i32"),
        field="pre-gate runtime sound ID",
        minimum=0,
        maximum=0x7FFFFFFF,
    )
    if sound_id not in gate_index:
        raise AuditError(f"pre-gate sound ID {sound_id} is not a v31 gate member")
    volume_index = _bounded_int(
        event.get("volume_index_i32"),
        field="pre-gate volume_index_i32",
        minimum=0,
        maximum=63,
    )
    event_active = _bounded_int(
        event.get("sound_pack_active_u32"),
        field="pre-gate sound_pack_active_u32",
        minimum=0,
        maximum=1,
    )
    _require_exact(
        event_active, active_value, field="pre-gate/addon Sound Pack active value"
    )
    volume_class = _bounded_int(
        event.get("volume_class_u8"),
        field="pre-gate volume_class_u8",
        minimum=0,
        maximum=2,
    )
    class_volume = _bounded_int(
        event.get("class_volume_u16"),
        field="pre-gate class_volume_u16",
        minimum=0,
        maximum=100,
    )
    indexed_volume = _bounded_int(
        event.get("indexed_volume_u16"),
        field="pre-gate indexed_volume_u16",
        minimum=0,
        maximum=100,
    )
    master_volume = _bounded_int(
        event.get("master_volume_u16"),
        field="pre-gate master_volume_u16",
        minimum=0,
        maximum=100,
    )
    expected_stage = (class_volume * indexed_volume) // 100
    expected_final = (expected_stage * master_volume) // 100
    _require_exact(
        _bounded_int(
            event.get("pre_gate_stage_volume_i32"),
            field="pre_gate_stage_volume_i32",
            minimum=0,
            maximum=100,
        ),
        expected_stage,
        field="pre-gate integer stage recomputation",
    )
    _require_exact(
        _bounded_int(
            event.get("authorized_final_volume_i32"),
            field="authorized_final_volume_i32",
            minimum=0,
            maximum=100,
        ),
        expected_final,
        field="pre-gate integer final recomputation",
    )
    _require_exact(
        _exact_bool(
            event.get("current_gate_will_zero"), field="current_gate_will_zero"
        ),
        event_active == 0,
        field="current_gate_will_zero",
    )
    _require_exact(
        _exact_bool(
            event.get("reconstruction_complete"), field="reconstruction_complete"
        ),
        True,
        field="reconstruction_complete",
    )

    first_sequence = _bounded_int(
        event.get("first_sequence", event.get("sequence")),
        field="pre-gate first_sequence",
        minimum=1,
        maximum=0x7FFFFFFF,
    )
    last_sequence = _bounded_int(
        event.get("last_sequence", event.get("sequence")),
        field="pre-gate last_sequence",
        minimum=first_sequence,
        maximum=0x7FFFFFFF,
    )
    observation_count = _bounded_int(
        event.get("observation_count"),
        field="pre-gate observation_count",
        minimum=1,
        maximum=last_sequence - first_sequence + 1,
    )
    caller_offset = _normalized_hex(
        event.get("return_module_offset"), field="pre-gate caller offset"
    )
    caller_symbol = event.get("return_symbol")
    if not isinstance(caller_symbol, str) or not caller_symbol:
        raise AuditError("pre-gate caller symbol is missing")
    reason = event.get("emission_reason")
    if caller_offset in DIRECT_REQUEST_CALLER_OFFSETS:
        _require_exact(
            reason,
            "direct_sound_request_call",
            field="direct request emission_reason",
        )
        _require_exact(
            observation_count, 1, field="direct request observation_count"
        )
        _require_exact(
            last_sequence, first_sequence, field="direct request sequence span"
        )
        if "wrapSndReq" not in caller_symbol:
            raise AuditError("direct request caller symbol is not wrapSndReq")
    elif caller_offset == VOLUME_CONTROL_CALLER_OFFSET:
        if reason not in VOLUME_CONTROL_REASONS:
            raise AuditError(
                f"volumeControl emission_reason is invalid: {reason!r}"
            )
        if "volumeControl" not in caller_symbol:
            raise AuditError("volumeControl caller symbol is inconsistent")
    else:
        raise AuditError(f"unknown pre-gate caller offset: {caller_offset}")

    return {
        "sound_id": sound_id,
        "volume_index": volume_index,
        "sound_pack_active_u32": event_active,
        "volume_class_u8": volume_class,
        "class_volume_u16": class_volume,
        "indexed_volume_u16": indexed_volume,
        "master_volume_u16": master_volume,
        "pre_gate_stage_volume_i32": expected_stage,
        "authorized_final_volume_i32": expected_final,
        "current_gate_will_zero": event_active == 0,
        "reconstruction_complete": True,
        "first_sequence": first_sequence,
        "last_sequence": last_sequence,
        "observation_count": observation_count,
        "emission_reason": reason,
        "return_module_offset": caller_offset,
        "return_symbol": caller_symbol,
    }


def _interpret_gate_row(
    *, is_gate_id: bool, active_value: int, transport_proven: bool, volume: Any
) -> str:
    if not is_gate_id:
        return "not_in_sound_pack_gate"
    if volume is None:
        return "gate_row_missing_runtime_volume"
    runtime_volume = _as_int(volume, field="slot_volume_u32_at_0x10")
    if active_value == 0 and transport_proven and runtime_volume == 0:
        return "unentitled_gate_consistent_zero_volume"
    if active_value == 0 and transport_proven and runtime_volume != 0:
        return "unentitled_gate_conflict_nonzero_volume"
    if active_value != 0:
        return "entitled_runtime_row_no_zero_volume_inference"
    return "unentitled_gate_transport_not_proven"


def _flatten_rows(
    journal_paths: Iterable[Path],
    gate_index: dict[int, int],
    sound_rows: dict[int, list[dict[str, str]]],
    addon_pid: int,
    active_value: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    output: list[dict[str, Any]] = []
    pre_gate_output: list[dict[str, Any]] = []
    journal_sources: list[dict[str, Any]] = []
    invalid_snapshots: list[str] = []
    for journal_path in journal_paths:
        journal = _load_jsonl(journal_path)
        session = journal[0]
        has_pre_gate_events = any(
            bool(row.get("sound_pack_pre_gate_volume_events"))
            for row in journal
            if row.get("schema") == "magireco-natural-sp-story-hunt-attempt-v1"
        )
        pre_gate_capability_verified = _validate_session_ready(
            session,
            journal_path,
            require_pre_gate=has_pre_gate_events,
        )
        runtime = session.get("runtime")
        if not isinstance(runtime, dict):
            raise AuditError(f"hunt session lacks runtime provenance: {journal_path}")
        session_pid = _as_int(runtime.get("pid"), field="hunt session PID")
        if session_pid != addon_pid:
            raise AuditError(
                f"PID mismatch: journal {session_pid}, addon snapshot {addon_pid}"
            )
        journal_sources.append(
            {
                "path": str(journal_path.resolve()),
                "sha256": _sha256(journal_path),
                "pid": session_pid,
                "package": runtime.get("package"),
                "device": runtime.get("device"),
                "sound_pack_pre_gate_events_present": has_pre_gate_events,
                "sound_pack_pre_gate_capability_verified": (
                    pre_gate_capability_verified
                ),
            }
        )
        for attempt in journal:
            if attempt.get("schema") != "magireco-natural-sp-story-hunt-attempt-v1":
                continue
            attempt_number = _as_int(attempt.get("attempt"), field="attempt")
            pre_gate_events = attempt.get("sound_pack_pre_gate_volume_events", [])
            if not isinstance(pre_gate_events, list):
                raise AuditError(
                    f"attempt {attempt_number} pre-gate volume events are not a list"
                )
            last_pre_gate_signature: tuple[Any, ...] | None = None
            last_pre_gate_output_index: int | None = None
            for event in pre_gate_events:
                if not isinstance(event, dict):
                    raise AuditError("pre-gate volume event is not an object")
                validated = _validated_pre_gate_event(
                    event,
                    gate_index=gate_index,
                    active_value=active_value,
                )
                sound_id = validated["sound_id"]
                mappings = sound_rows.get(sound_id, [])
                mapping = mappings[0] if mappings else {}
                pre_gate_row = {
                        "journal": str(journal_path.resolve()),
                        "journal_sha256": journal_sources[-1]["sha256"],
                        "session_pid": session_pid,
                        "attempt": attempt_number,
                        "attempt_outcome": attempt.get("outcome"),
                        "first_sequence": validated["first_sequence"],
                        "last_sequence": validated["last_sequence"],
                        "first_host_unix_ms": event.get(
                            "first_host_unix_ms", event.get("host_unix_ms")
                        ),
                        "last_host_unix_ms": event.get(
                            "last_host_unix_ms", event.get("host_unix_ms")
                        ),
                        "observation_count": validated["observation_count"],
                        "sound_id": sound_id,
                        "volume_index": validated["volume_index"],
                        "sound_pack_gate_member": True,
                        "sound_pack_gate_table_index": gate_index.get(sound_id),
                        "sound_pack_active_u32": validated[
                            "sound_pack_active_u32"
                        ],
                        "volume_class_u8": validated["volume_class_u8"],
                        "class_volume_u16": validated["class_volume_u16"],
                        "indexed_volume_u16": validated["indexed_volume_u16"],
                        "master_volume_u16": validated["master_volume_u16"],
                        "pre_gate_stage_volume_i32": validated[
                            "pre_gate_stage_volume_i32"
                        ],
                        "authorized_final_volume_i32": validated[
                            "authorized_final_volume_i32"
                        ],
                        "current_gate_will_zero": validated[
                            "current_gate_will_zero"
                        ],
                        "reconstruction_complete": True,
                        "emission_reason": validated["emission_reason"],
                        "return_module_offset": validated[
                            "return_module_offset"
                        ],
                        "return_symbol": validated["return_symbol"],
                        "sound_mapping_count": len(mappings),
                        "sound_mapping_source_row": mapping.get(
                            "source_row_number", ""
                        ),
                        "sound_bank": mapping.get("sound_bank", ""),
                        "ogg_duration_sec": mapping.get("ogg_duration_sec", ""),
                        "request_label": mapping.get("request_label", ""),
                        "suggested_name": mapping.get("suggested_name", ""),
                    }
                signature = (
                    pre_gate_row["sound_id"],
                    pre_gate_row["volume_index"],
                    pre_gate_row["sound_pack_active_u32"],
                    pre_gate_row["volume_class_u8"],
                    pre_gate_row["class_volume_u16"],
                    pre_gate_row["indexed_volume_u16"],
                    pre_gate_row["master_volume_u16"],
                    pre_gate_row["pre_gate_stage_volume_i32"],
                    pre_gate_row["authorized_final_volume_i32"],
                    pre_gate_row["current_gate_will_zero"],
                    pre_gate_row["reconstruction_complete"],
                    pre_gate_row["emission_reason"],
                    pre_gate_row["return_module_offset"],
                )
                if (
                    pre_gate_row["return_module_offset"]
                    == VOLUME_CONTROL_CALLER_OFFSET
                    and pre_gate_row["emission_reason"] in VOLUME_CONTROL_REASONS
                    and last_pre_gate_signature == signature
                    and last_pre_gate_output_index is not None
                ):
                    aggregate = pre_gate_output[last_pre_gate_output_index]
                    aggregate["last_sequence"] = pre_gate_row["last_sequence"]
                    aggregate["last_host_unix_ms"] = pre_gate_row[
                        "last_host_unix_ms"
                    ]
                    aggregate["observation_count"] = _as_int(
                        aggregate["observation_count"],
                        field="pre-gate aggregate observation_count",
                    ) + _as_int(
                        pre_gate_row["observation_count"],
                        field="pre-gate event observation_count",
                    )
                else:
                    pre_gate_output.append(pre_gate_row)
                    last_pre_gate_output_index = len(pre_gate_output) - 1
                last_pre_gate_signature = signature
            snapshots = attempt.get("outer_bgm_active_sound_snapshots")
            if not isinstance(snapshots, list):
                raise AuditError(
                    f"attempt {attempt_number} has no active sound snapshots"
                )
            for snapshot in snapshots:
                if not isinstance(snapshot, dict):
                    raise AuditError("active sound snapshot is not an object")
                valid, reasons = _snapshot_valid(snapshot)
                snapshot_label = str(snapshot.get("label") or "")
                snapshot_key = (
                    f"{journal_path.name}:attempt={attempt_number}:label={snapshot_label}"
                )
                if not valid:
                    invalid_snapshots.append(snapshot_key + ":" + ",".join(reasons))
                active_rows = snapshot.get("active_rows")
                if not isinstance(active_rows, list):
                    raise AuditError(f"snapshot {snapshot_key} has no active_rows")
                for active_row in active_rows:
                    if not isinstance(active_row, dict):
                        raise AuditError(f"snapshot {snapshot_key} row is not an object")
                    sound_id = _as_int(
                        active_row.get("sound_id_i32"), field="runtime sound ID"
                    )
                    mappings = sound_rows.get(sound_id, [])
                    mapping = mappings[0] if mappings else {}
                    is_gate_id = sound_id in gate_index
                    transport_proven = active_row.get("transport_playing_proven") is True
                    interpretation = _interpret_gate_row(
                        is_gate_id=is_gate_id,
                        active_value=active_value,
                        transport_proven=transport_proven,
                        volume=active_row.get("slot_volume_u32_at_0x10"),
                    )
                    output.append(
                        {
                            "journal": str(journal_path.resolve()),
                            "journal_sha256": journal_sources[-1]["sha256"],
                            "session_pid": session_pid,
                            "attempt": attempt_number,
                            "attempt_outcome": attempt.get("outcome"),
                            "snapshot_label": snapshot_label,
                            "snapshot_captured_host_unix_ms": snapshot.get(
                                "captured_host_unix_ms"
                            ),
                            "snapshot_valid": valid,
                            "snapshot_invalid_reasons": ";".join(reasons),
                            "slot_index": active_row.get("slot_index"),
                            "sound_id": sound_id,
                            "channel": active_row.get(
                                "csl_resource_table_channel_i32"
                            ),
                            "runtime_volume": active_row.get(
                                "slot_volume_u32_at_0x10"
                            ),
                            "transport_state": active_row.get("transport_state"),
                            "transport_playing_proven": transport_proven,
                            "transport_paused": active_row.get("transport_paused"),
                            "sound_time_seconds": active_row.get("sound_time_seconds"),
                            "loop_flag": active_row.get("sound_loop_flag_i32"),
                            "sound_pack_gate_member": is_gate_id,
                            "sound_pack_gate_table_index": gate_index.get(sound_id),
                            "sound_pack_active_u32": active_value,
                            "gate_runtime_interpretation": interpretation,
                            "sound_mapping_count": len(mappings),
                            "sound_mapping_source_row": mapping.get(
                                "source_row_number", ""
                            ),
                            "sound_bank": mapping.get("sound_bank", ""),
                            "ogg_duration_sec": mapping.get("ogg_duration_sec", ""),
                            "request_label": mapping.get("request_label", ""),
                            "suggested_name": mapping.get("suggested_name", ""),
                        }
                    )
    return output, pre_gate_output, journal_sources, invalid_snapshots


def build_audit(
    *,
    journal_paths: list[Path],
    gate_path: Path,
    addon_path: Path,
    sound_csv_path: Path,
) -> dict[str, Any]:
    gate, gate_ids, gate_index = _load_gate(gate_path)
    addon, sound_pack_row = _load_addon(addon_path)
    process = addon.get("process")
    if not isinstance(process, dict):
        raise AuditError("addon snapshot lacks process provenance")
    addon_pid = _as_int(process.get("id"), field="addon snapshot PID")
    active_value = _as_int(
        sound_pack_row.get("active_u32"), field="Sound Pack active_u32"
    )
    saved_value = _as_int(
        sound_pack_row.get("saved_u32"), field="Sound Pack saved_u32"
    )
    sound_rows = _load_sound_rows(sound_csv_path)
    rows, pre_gate_rows, journals, invalid_snapshots = _flatten_rows(
        journal_paths, gate_index, sound_rows, addon_pid, active_value
    )
    gate_rows = [row for row in rows if row["sound_pack_gate_member"]]
    zero_gate_rows = [row for row in gate_rows if row["runtime_volume"] == 0]
    nonzero_gate_rows = [
        row
        for row in gate_rows
        if row["runtime_volume"] is not None and row["runtime_volume"] != 0
    ]
    conflict_rows = [
        row
        for row in gate_rows
        if row["gate_runtime_interpretation"]
        == "unentitled_gate_conflict_nonzero_volume"
    ]
    corroborating_rows = [
        row
        for row in gate_rows
        if row["gate_runtime_interpretation"]
        == "unentitled_gate_consistent_zero_volume"
    ]
    reconstructed_rows = [
        row
        for row in pre_gate_rows
        if row["sound_pack_gate_member"]
        and row["reconstruction_complete"] is True
        and row["authorized_final_volume_i32"] is not None
    ]
    invalid_pre_gate_rows = [
        row
        for row in pre_gate_rows
        if not row["sound_pack_gate_member"]
        or row["sound_pack_active_u32"] != active_value
        or row["reconstruction_complete"] is not True
    ]
    ok = not invalid_snapshots and not conflict_rows and not invalid_pre_gate_rows
    return {
        "schema": SCHEMA,
        "ok": ok,
        "evidence_kind": "read_only_post_capture_runtime_static_join",
        "safety": {
            "process_attachment": False,
            "game_input": False,
            "native_calls": False,
            "memory_writes": False,
            "entitlement_bypass_supported": False,
        },
        "sources": {
            "journals": journals,
            "sound_pack_gate": {
                "path": str(gate_path.resolve()),
                "sha256": _sha256(gate_path),
                "table_sha256": gate.get("table", {}).get("table_sha256"),
                "reference_status": gate.get("reference_policy", {}).get(
                    "audit_status"
                ),
                "id_count": len(gate_ids),
            },
            "addon_snapshot": {
                "path": str(addon_path.resolve()),
                "sha256": _sha256(addon_path),
                "pid": addon_pid,
                "sound_pack_index": addon.get("sound_pack_candidate_index"),
                "active_u32": active_value,
                "saved_u32": saved_value,
            },
            "sound_request_audit": {
                "path": str(sound_csv_path.resolve()),
                "sha256": _sha256(sound_csv_path),
            },
        },
        "summary": {
            "runtime_active_row_count": len(rows),
            "sound_pack_gate_row_count": len(gate_rows),
            "sound_pack_gate_unique_ids": sorted(
                {int(row["sound_id"]) for row in gate_rows}
            ),
            "sound_pack_gate_zero_volume_row_count": len(zero_gate_rows),
            "sound_pack_gate_nonzero_volume_row_count": len(nonzero_gate_rows),
            "unentitled_gate_corroborating_row_count": len(corroborating_rows),
            "unentitled_gate_conflict_row_count": len(conflict_rows),
            "invalid_snapshot_count": len(invalid_snapshots),
            "invalid_snapshots": invalid_snapshots,
            "claim_boundary": (
                "A gate-table member observed as a proven playing transport with "
                "runtime volume zero while addon index 6 is zero corroborates the "
                "native entitlement mute path. It does not prove that every scene "
                "requests BGM or reveal the authorized mix volume."
            ),
            "pre_gate_volume_row_count": len(pre_gate_rows),
            "pre_gate_observation_count": sum(
                _as_int(row["observation_count"], field="pre-gate observation_count")
                for row in pre_gate_rows
            ),
            "pre_gate_reconstructed_row_count": len(reconstructed_rows),
            "pre_gate_invalid_row_count": len(invalid_pre_gate_rows),
            "pre_gate_unique_sound_ids": sorted(
                {int(row["sound_id"]) for row in reconstructed_rows}
            ),
            "pre_gate_authorized_final_volumes_by_sound_id": {
                str(sound_id): sorted(
                    {
                        int(row["authorized_final_volume_i32"])
                        for row in reconstructed_rows
                        if int(row["sound_id"]) == sound_id
                    }
                )
                for sound_id in sorted(
                    {int(row["sound_id"]) for row in reconstructed_rows}
                )
            },
            "pre_gate_claim_boundary": (
                "The reconstructed value is the integer percentage-chain result "
                "immediately before the entitlement branch zeros a matching "
                "Sound Pack ID. It is suitable as an exact volume-control input, "
                "but final scene mixing still requires request time, loop phase, "
                "ducking transitions, and the target scene identity."
            ),
        },
        "rows": rows,
        "pre_gate_volume_rows": pre_gate_rows,
    }


CSV_FIELDS = [
    "journal",
    "journal_sha256",
    "session_pid",
    "attempt",
    "attempt_outcome",
    "snapshot_label",
    "snapshot_captured_host_unix_ms",
    "snapshot_valid",
    "snapshot_invalid_reasons",
    "slot_index",
    "sound_id",
    "channel",
    "runtime_volume",
    "transport_state",
    "transport_playing_proven",
    "transport_paused",
    "sound_time_seconds",
    "loop_flag",
    "sound_pack_gate_member",
    "sound_pack_gate_table_index",
    "sound_pack_active_u32",
    "gate_runtime_interpretation",
    "sound_mapping_count",
    "sound_mapping_source_row",
    "sound_bank",
    "ogg_duration_sec",
    "request_label",
    "suggested_name",
]

PRE_GATE_CSV_FIELDS = [
    "journal",
    "journal_sha256",
    "session_pid",
    "attempt",
    "attempt_outcome",
    "first_sequence",
    "last_sequence",
    "first_host_unix_ms",
    "last_host_unix_ms",
    "observation_count",
    "sound_id",
    "volume_index",
    "sound_pack_gate_member",
    "sound_pack_gate_table_index",
    "sound_pack_active_u32",
    "volume_class_u8",
    "class_volume_u16",
    "indexed_volume_u16",
    "master_volume_u16",
    "pre_gate_stage_volume_i32",
    "authorized_final_volume_i32",
    "current_gate_will_zero",
    "reconstruction_complete",
    "emission_reason",
    "return_module_offset",
    "return_symbol",
    "sound_mapping_count",
    "sound_mapping_source_row",
    "sound_bank",
    "ogg_duration_sec",
    "request_label",
    "suggested_name",
]


def _write_outputs(audit: dict[str, Any], out_dir: Path, overwrite: bool) -> None:
    json_path = out_dir / JSON_NAME
    csv_path = out_dir / CSV_NAME
    pre_gate_csv_path = out_dir / PRE_GATE_CSV_NAME
    existing = [
        str(path)
        for path in (json_path, csv_path, pre_gate_csv_path)
        if path.exists()
    ]
    if existing and not overwrite:
        raise AuditError("refusing to overwrite existing outputs: " + ", ".join(existing))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(audit["rows"])
    with pre_gate_csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=PRE_GATE_CSV_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(audit["pre_gate_volume_rows"])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--journal",
        action="append",
        required=True,
        help="natural_sp_story_hunt JSONL; repeat for multiple captures",
    )
    parser.add_argument("--sound-pack-gate-json", required=True)
    parser.add_argument("--addon-snapshot", required=True)
    parser.add_argument("--sound-request-audit", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--overwrite-outputs", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    try:
        audit = build_audit(
            journal_paths=[Path(path) for path in args.journal],
            gate_path=Path(args.sound_pack_gate_json),
            addon_path=Path(args.addon_snapshot),
            sound_csv_path=Path(args.sound_request_audit),
        )
        _write_outputs(audit, out_dir, args.overwrite_outputs)
    except AuditError as exc:
        message = str(exc)
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
        if message.startswith(("gate ", "Sound Pack gate", "reference_")):
            return 4
        return 3
    print(
        json.dumps(
            {
                "ok": audit["ok"],
                "json": str((out_dir / JSON_NAME).resolve()),
                "csv": str((out_dir / CSV_NAME).resolve()),
                "pre_gate_csv": str((out_dir / PRE_GATE_CSV_NAME).resolve()),
                "summary": audit["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if audit["ok"] else 5


if __name__ == "__main__":
    raise SystemExit(main())
