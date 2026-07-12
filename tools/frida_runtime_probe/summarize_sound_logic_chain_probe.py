#!/usr/bin/env python3
"""Summarize the metadata-only sound-logic Frida probe.

The important rule in this module is deliberately narrow: a runtime request may
be associated with ``SoundMng::sndPlayReq`` only when the probe observed that
call nested inside ``PlayerImpl::performRequest`` on the same thread.  Legacy
``same_thread_recent`` / ``global_recent_window`` fields are retained for audit
but are never used as causal evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


TEMPORAL_MARKERS = ("recent", "window", "nearest", "temporal")
EXACT_NESTED_BASIS = "nested_within_perform_request"
OUTPUT_TABLES = {
    "code_mappings": "code_mappings.csv",
    "zg_requests": "zg_requests.csv",
    "get_requests": "get_requests.csv",
    "set_requests": "set_requests.csv",
    "request_data": "request_data.csv",
    "perform_orders": "perform_orders.csv",
    "nested_play_requests": "nested_play_requests.csv",
    "csl_play_starts": "csl_play_starts.csv",
    "chains": "chains.csv",
}
COMMON_FIELDS = ["line", "unix_ms", "rel_s", "thread_id"]
TABLE_FIELDS = {
    "code_mappings": COMMON_FIELDS
    + ["source", "request_id", "code_name", "association_basis", "causal"],
    "zg_requests": COMMON_FIELDS
    + [
        "request_id",
        "code_name",
        "code_association_basis",
        "arg1",
        "arg2",
        "association_basis",
        "causal",
    ],
    "get_requests": COMMON_FIELDS
    + [
        "request_id",
        "derived_own_ids",
        "code_name",
        "code_association_basis",
        "request_pointer",
        "reqdata_count",
        "association_basis",
        "legacy_context_basis",
        "temporal_context_rejected",
        "static_code_name",
        "static_media",
    ],
    "set_requests": COMMON_FIELDS
    + [
        "request_id",
        "derived_own_ids",
        "code_name",
        "code_association_basis",
        "request_pointer",
        "reqdata_count",
        "association_basis",
        "legacy_context_basis",
        "temporal_context_rejected",
        "static_code_name",
        "static_media",
    ],
    "request_data": COMMON_FIELDS
    + [
        "stage",
        "request_id",
        "reqdata_index",
        "own_id",
        "target_id",
        "channel_hex",
        "function_type",
        "media_format",
        "media_name",
        "association_basis",
        "raw_reqdata_json",
    ],
    "perform_orders": COMMON_FIELDS
    + [
        "request_id",
        "code_name",
        "code_association_basis",
        "function_type",
        "player_channel",
        "req_order_pointer",
        "association_basis",
        "legacy_context_basis",
        "temporal_context_rejected",
        "static_code_name",
        "static_media",
    ],
    "nested_play_requests": COMMON_FIELDS
    + [
        "phase",
        "request_id",
        "code_name",
        "code_association_basis",
        "function_type",
        "player_channel",
        "sound_resource_id",
        "play_index_or_bank",
        "return_i32",
        "static_final_sound_ids",
        "static_sound_id_names",
        "association_basis",
        "causal_request_to_resource",
        "legacy_context_request_id_ignored",
        "legacy_context_basis",
        "temporal_context_rejected",
    ],
    "csl_play_starts": COMMON_FIELDS
    + [
        "play_index",
        "final_sound_id",
        "static_sound_resource_ids",
        "static_sound_id_names",
        "association_basis",
        "causal_request_id",
        "causal_request_association_basis",
        "legacy_context_request_id_ignored",
        "legacy_context_basis",
        "temporal_context_rejected",
    ],
    "chains": [
        "request_id",
        "code_name",
        "function_type",
        "player_channel",
        "sound_resource_id",
        "static_final_sound_ids",
        "runtime_observed_final_sound_ids",
        "event_names",
        "request_to_resource_basis",
        "resource_to_final_basis",
        "event_association_basis",
        "association_basis",
        "complete_chain_observed",
        "status",
    ],
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return None


def _id(value: Any) -> str:
    result = _int(value)
    return "" if result is None else str(result)


def _join(values: Iterable[Any]) -> str:
    unique: list[str] = []
    for value in values:
        item = _text(value).strip()
        if item and item not in unique:
            unique.append(item)
    return ";".join(unique)


def _is_temporal_basis(value: Any) -> bool:
    basis = _text(value).strip().lower()
    return bool(basis) and any(marker in basis for marker in TEMPORAL_MARKERS)


def _event_payload(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    message = record.get("message")
    if isinstance(message, dict) and message.get("type") == "send":
        payload = message.get("payload")
        return payload if isinstance(payload, dict) else None
    payload = record.get("payload")
    if isinstance(payload, dict) and (payload.get("kind") or payload.get("event")):
        return payload
    if record.get("kind"):
        return record
    return None


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read host-wrapped or direct Frida JSONL without failing on bad lines."""

    events: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "path": str(path.resolve()),
        "line_count": 0,
        "blank_line_count": 0,
        "invalid_json_line_count": 0,
        "non_event_line_count": 0,
        "invalid_json_line_samples": [],
    }
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw in enumerate(handle, 1):
            stats["line_count"] += 1
            text = raw.strip()
            if not text:
                stats["blank_line_count"] += 1
                continue
            try:
                record = json.loads(text)
            except (json.JSONDecodeError, ValueError) as exc:
                stats["invalid_json_line_count"] += 1
                if len(stats["invalid_json_line_samples"]) < 5:
                    stats["invalid_json_line_samples"].append(
                        {"line": line_number, "error": str(exc), "prefix": text[:160]}
                    )
                continue
            payload = _event_payload(record)
            if payload is None:
                stats["non_event_line_count"] += 1
                continue
            events.append(
                {
                    "line": line_number,
                    "host_unix_ms": _int(record.get("host_unix_ms")),
                    "payload": payload,
                }
            )
    stats["event_count"] = len(events)
    return events, stats


def read_csv_optional(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [_id(item) for item in value if _id(item)]
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        decoded = None
    if isinstance(decoded, list):
        return [_id(item) for item in decoded if _id(item)]
    return [match for match in re.findall(r"(?<![A-Za-z])\d+", text)]


def _request_description(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("request")
    return value if isinstance(value, dict) else {}


def _reqdata_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _request_description(payload).get("reqdata_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _base(event: dict[str, Any], first_ms: int | None) -> dict[str, Any]:
    payload = event["payload"]
    unix_ms = _int(payload.get("unix_ms"))
    if unix_ms is None:
        unix_ms = event.get("host_unix_ms")
    rel_s = ""
    if unix_ms is not None and first_ms is not None:
        rel_s = f"{(unix_ms - first_ms) / 1000.0:.6f}"
    return {
        "line": event["line"],
        "unix_ms": unix_ms if unix_ms is not None else "",
        "rel_s": rel_s,
        "thread_id": _text(payload.get("thread_id")),
    }


def _static_indexes(
    requests: list[dict[str, str]],
    reqdata: list[dict[str, str]],
    sound_ids: list[dict[str, str]],
    timeline: list[dict[str, str]],
) -> dict[str, Any]:
    request_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    reqdata_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    sound_by_resource: dict[str, list[dict[str, str]]] = defaultdict(list)
    sound_by_final: dict[str, list[dict[str, str]]] = defaultdict(list)
    event_by_request: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in requests:
        if key := _id(row.get("request_id")):
            request_by_id[key].append(row)
    for row in reqdata:
        if key := _id(row.get("request_id")):
            reqdata_by_id[key].append(row)
    for row in sound_ids:
        resource = _id(row.get("sound_resource_id") or row.get("resource_id"))
        final_id = _id(
            row.get("ogg_chunk_index")
            or row.get("final_sound_id")
            or row.get("sound_id")
        )
        if resource:
            sound_by_resource[resource].append(row)
        if final_id:
            sound_by_final[final_id].append(row)
    for row in timeline:
        for request_id in _split_ids(
            row.get("sound_request_ids") or row.get("request_ids") or row.get("request_id")
        ):
            event_by_request[request_id].append(row)
    return {
        "request_by_id": request_by_id,
        "reqdata_by_id": reqdata_by_id,
        "sound_by_resource": sound_by_resource,
        "sound_by_final": sound_by_final,
        "event_by_request": event_by_request,
    }


def _static_request_fields(indexes: dict[str, Any], request_id: str) -> dict[str, str]:
    request_rows = indexes["request_by_id"].get(request_id, [])
    reqdata_rows = indexes["reqdata_by_id"].get(request_id, [])
    return {
        "static_code_name": _join(row.get("code_name") for row in request_rows + reqdata_rows),
        "static_media": _join(
            row.get("first_smz_media") or row.get("smz_media")
            for row in request_rows + reqdata_rows
        ),
    }


def _resolved_code(
    request_id: str,
    runtime_codes: dict[str, set[str]],
    indexes: dict[str, Any],
    payload_code: Any = "",
) -> tuple[str, str]:
    direct = _text(payload_code).strip()
    if direct:
        return direct, "probe_exact_request_id_map"
    values = sorted(runtime_codes.get(request_id, set()))
    if len(values) == 1:
        return values[0], "runtime_code_lookup_request_id_join"
    static_values = {
        _text(row.get("code_name")).strip()
        for row in indexes["request_by_id"].get(request_id, [])
        if _text(row.get("code_name")).strip()
    }
    if len(static_values) == 1:
        return next(iter(static_values)), "static_sound_request_manifest_request_id_join"
    return "", "none"


def summarize(
    jsonl_path: Path,
    *,
    sound_requests_csv: Path | None = None,
    sound_reqdata_csv: Path | None = None,
    sound_id_records_csv: Path | None = None,
    event_timeline_csv: Path | None = None,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    events, parse_stats = read_jsonl(jsonl_path)
    static_rows = {
        "requests": read_csv_optional(sound_requests_csv),
        "reqdata": read_csv_optional(sound_reqdata_csv),
        "sound_ids": read_csv_optional(sound_id_records_csv),
        "timeline": read_csv_optional(event_timeline_csv),
    }
    indexes = _static_indexes(
        static_rows["requests"],
        static_rows["reqdata"],
        static_rows["sound_ids"],
        static_rows["timeline"],
    )
    times = [
        value
        for event in events
        if (value := _int(event["payload"].get("unix_ms"))) is not None
    ]
    first_ms = min(times) if times else None

    runtime_codes: dict[str, set[str]] = defaultdict(set)
    for event in events:
        payload = event["payload"]
        if payload.get("kind") == "sound_logic_code_name_to_request_id":
            request_id = _id(payload.get("request_id_i32"))
            code = _text(payload.get("code_string")).strip()
            if request_id and code:
                runtime_codes[request_id].add(code)

    tables: dict[str, list[dict[str, Any]]] = {key: [] for key in OUTPUT_TABLES}
    get_request_by_pointer: dict[str, str] = {}
    observed_request_ids: set[str] = set()
    csl_final_ids: set[str] = set()
    rejected_temporal_count = 0

    for event in events:
        payload = event["payload"]
        kind = _text(payload.get("kind"))
        base = _base(event, first_ms)
        legacy_basis = _text(
            payload.get("context_association_basis")
            or payload.get("causal_association_basis")
        )
        temporal_rejected = _is_temporal_basis(legacy_basis)
        if temporal_rejected:
            rejected_temporal_count += 1

        if kind == "sound_logic_code_name_to_request_id":
            request_id = _id(payload.get("request_id_i32"))
            if request_id:
                observed_request_ids.add(request_id)
            tables["code_mappings"].append(
                {
                    **base,
                    "source": "runtime_code_lookup",
                    "request_id": request_id,
                    "code_name": _text(payload.get("code_string")),
                    "association_basis": "runtime_code_name_to_request_id_return",
                    "causal": "yes",
                }
            )
            continue

        if kind == "sound_logic_zg_snd_req_id":
            request_id = _id(payload.get("request_id_i32"))
            if request_id:
                observed_request_ids.add(request_id)
            code, code_basis = _resolved_code(
                request_id, runtime_codes, indexes, payload.get("context_code")
            )
            tables["zg_requests"].append(
                {
                    **base,
                    "request_id": request_id,
                    "code_name": code,
                    "code_association_basis": code_basis,
                    "arg1": _text(payload.get("request_arg1_i32")),
                    "arg2": _text(payload.get("request_arg2_i32")),
                    "association_basis": "runtime_zg_snd_req_id_argument",
                    "causal": "yes",
                }
            )
            continue

        if kind in {
            "sound_logic_request_ctrl_get_request",
            "sound_logic_request_ctrl_set_request_list",
        }:
            request = _request_description(payload)
            pointer = _text(request.get("request_pointer"))
            own_ids = sorted(
                {
                    key
                    for row in _reqdata_rows(payload)
                    if (key := _id(row.get("own_id_u32_at_0x48")))
                },
                key=int,
            )
            if kind == "sound_logic_request_ctrl_get_request":
                request_id = _id(payload.get("request_id_i32"))
                association_basis = "runtime_get_request_id_argument"
                if pointer and request_id:
                    get_request_by_pointer[pointer] = request_id
                table_name = "get_requests"
            else:
                explicit_basis = _text(payload.get("request_id_association_basis"))
                if len(own_ids) == 1:
                    request_id = own_ids[0]
                    association_basis = "runtime_reqdata_own_id"
                elif len(own_ids) > 1:
                    request_id = ""
                    association_basis = "runtime_reqdata_multiple_own_ids"
                elif (
                    explicit_basis == "same_request_pointer_previous_get"
                    and pointer in get_request_by_pointer
                ):
                    request_id = get_request_by_pointer[pointer]
                    association_basis = "runtime_same_request_pointer_previous_get"
                elif explicit_basis == "reqdata_own_id":
                    request_id = _id(payload.get("request_id_i32"))
                    association_basis = "runtime_reqdata_own_id"
                else:
                    # In particular, never accept legacy context_request_id here.
                    request_id = ""
                    association_basis = (
                        "legacy_temporal_context_rejected" if temporal_rejected else "none"
                    )
                table_name = "set_requests"
            if request_id:
                observed_request_ids.add(request_id)
            code, code_basis = _resolved_code(
                request_id,
                runtime_codes,
                indexes,
                request.get("request_code_name_utf8"),
            )
            static_fields = _static_request_fields(indexes, request_id)
            tables[table_name].append(
                {
                    **base,
                    "request_id": request_id,
                    "derived_own_ids": _join(own_ids),
                    "code_name": code,
                    "code_association_basis": code_basis,
                    "request_pointer": pointer,
                    "reqdata_count": _text(request.get("reqdata_count")),
                    "association_basis": association_basis,
                    "legacy_context_basis": legacy_basis,
                    "temporal_context_rejected": _text(temporal_rejected),
                    **static_fields,
                }
            )
            for reqdata in _reqdata_rows(payload):
                tables["request_data"].append(
                    {
                        **base,
                        "stage": "get" if table_name == "get_requests" else "set",
                        "request_id": request_id,
                        "reqdata_index": _text(reqdata.get("reqdata_index")),
                        "own_id": _id(reqdata.get("own_id_u32_at_0x48")),
                        "target_id": _id(reqdata.get("target_id_u32_at_0x4c")),
                        "channel_hex": _text(reqdata.get("channel_hex_at_0x00")),
                        "function_type": _text(reqdata.get("function_type_name")),
                        "media_format": _text(reqdata.get("media_format_name")),
                        "media_name": _text(reqdata.get("media_name_utf8")),
                        "association_basis": "runtime_request_struct_reqdata",
                        "raw_reqdata_json": json.dumps(
                            reqdata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                        ),
                    }
                )
            continue

        if kind == "sound_logic_player_perform_request":
            order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
            request_id = _id(
                payload.get("order_request_id_u32") or order.get("raw_u32_at_0x28")
            )
            if request_id:
                observed_request_ids.add(request_id)
            code, code_basis = _resolved_code(
                request_id, runtime_codes, indexes, payload.get("order_code")
            )
            tables["perform_orders"].append(
                {
                    **base,
                    "request_id": request_id,
                    "code_name": code,
                    "code_association_basis": code_basis,
                    "function_type": _text(order.get("function_type_name")),
                    "player_channel": _text(order.get("player_channel_i32")),
                    "req_order_pointer": _text(order.get("req_order_pointer")),
                    "association_basis": "runtime_req_order_u32_at_0x28",
                    "legacy_context_basis": legacy_basis,
                    "temporal_context_rejected": _text(temporal_rejected),
                    **_static_request_fields(indexes, request_id),
                }
            )
            continue

        if kind in {
            "sound_logic_sound_mng_snd_play_req_enter",
            "sound_logic_sound_mng_snd_play_req_leave",
        }:
            phase = "enter" if kind.endswith("_enter") else "leave"
            nested_basis = _text(payload.get("perform_association_basis"))
            exact_nested = (
                nested_basis == EXACT_NESTED_BASIS
                and _id(payload.get("perform_order_request_id_u32")) != ""
            )
            request_id = (
                _id(payload.get("perform_order_request_id_u32")) if exact_nested else ""
            )
            if request_id:
                observed_request_ids.add(request_id)
            resource_id = _id(payload.get("sound_resource_id_i32"))
            sound_rows = indexes["sound_by_resource"].get(resource_id, [])
            final_ids = _join(
                _id(row.get("ogg_chunk_index") or row.get("final_sound_id") or row.get("sound_id"))
                for row in sound_rows
            )
            code, code_basis = _resolved_code(
                request_id, runtime_codes, indexes, payload.get("perform_order_code")
            )
            association_basis = (
                "runtime_same_thread_nested_within_perform_request"
                if exact_nested
                else "legacy_temporal_context_rejected"
                if temporal_rejected
                else "none"
            )
            tables["nested_play_requests"].append(
                {
                    **base,
                    "phase": phase,
                    "request_id": request_id,
                    "code_name": code,
                    "code_association_basis": code_basis,
                    "function_type": _text(payload.get("perform_function_type_name")),
                    "player_channel": _text(payload.get("perform_player_channel_i32")),
                    "sound_resource_id": resource_id,
                    "play_index_or_bank": _text(payload.get("play_index_or_bank_i32")),
                    "return_i32": _text(payload.get("return_i32")),
                    "static_final_sound_ids": final_ids,
                    "static_sound_id_names": _join(row.get("suggested_name") for row in sound_rows),
                    "association_basis": association_basis,
                    "causal_request_to_resource": _text(exact_nested),
                    "legacy_context_request_id_ignored": _id(payload.get("context_request_id")),
                    "legacy_context_basis": legacy_basis,
                    "temporal_context_rejected": _text(temporal_rejected),
                }
            )
            continue

        if kind == "sound_logic_csl_mng_play_start":
            sound = payload.get("sound") if isinstance(payload.get("sound"), dict) else {}
            final_id = _id(sound.get("final_sound_id_u16_at_0x02"))
            if final_id:
                csl_final_ids.add(final_id)
            sound_rows = indexes["sound_by_final"].get(final_id, [])
            resource_ids = _join(
                _id(row.get("sound_resource_id") or row.get("resource_id"))
                for row in sound_rows
            )
            static_basis = (
                "static_sound_id_records_ogg_chunk_index_unique"
                if len(sound_rows) == 1
                else "static_sound_id_records_ogg_chunk_index_multiple"
                if sound_rows
                else "none"
            )
            causal_basis = _text(payload.get("causal_association_basis"))
            if _is_temporal_basis(legacy_basis):
                causal_basis = "legacy_temporal_context_rejected"
            elif not causal_basis:
                causal_basis = "none_static_sound_id_join_required"
            tables["csl_play_starts"].append(
                {
                    **base,
                    "play_index": _text(payload.get("play_index_i32")),
                    "final_sound_id": final_id,
                    "static_sound_resource_ids": resource_ids,
                    "static_sound_id_names": _join(row.get("suggested_name") for row in sound_rows),
                    "association_basis": static_basis,
                    "causal_request_id": "",
                    "causal_request_association_basis": causal_basis,
                    "legacy_context_request_id_ignored": _id(payload.get("context_request_id")),
                    "legacy_context_basis": legacy_basis,
                    "temporal_context_rejected": _text(temporal_rejected),
                }
            )

    # Add relevant static request mappings without copying the full manifest.
    runtime_code_pairs = {
        (row["request_id"], row["code_name"])
        for row in tables["code_mappings"]
    }
    for request_id in sorted(observed_request_ids, key=int):
        for row in indexes["request_by_id"].get(request_id, []):
            pair = (request_id, _text(row.get("code_name")))
            if pair in runtime_code_pairs:
                continue
            tables["code_mappings"].append(
                {
                    "line": "",
                    "unix_ms": "",
                    "rel_s": "",
                    "thread_id": "",
                    "source": "static_sound_request_manifest",
                    "request_id": request_id,
                    "code_name": pair[1],
                    "association_basis": "static_manifest_request_id",
                    "causal": "no",
                }
            )

    # A complete row starts only from a causally accepted nested runtime call.
    seen_chains: set[tuple[str, str, str, str, str]] = set()
    for nested in tables["nested_play_requests"]:
        if nested["phase"] != "enter" or nested["causal_request_to_resource"] != "yes":
            continue
        request_id = nested["request_id"]
        resource_id = nested["sound_resource_id"]
        final_rows = indexes["sound_by_resource"].get(resource_id, [])
        final_ids = [
            _id(row.get("ogg_chunk_index") or row.get("final_sound_id") or row.get("sound_id"))
            for row in final_rows
        ]
        final_ids = [value for value in final_ids if value]
        observed_final_ids = [value for value in final_ids if value in csl_final_ids]
        events_for_request = indexes["event_by_request"].get(request_id, [])
        event_names = _join(
            row.get("primary_animation") or row.get("event_name") or row.get("event")
            for row in events_for_request
        )
        key = (
            request_id,
            resource_id,
            nested["function_type"],
            nested["player_channel"],
            _join(final_ids),
        )
        if key in seen_chains:
            continue
        seen_chains.add(key)
        complete = bool(final_ids and observed_final_ids)
        tables["chains"].append(
            {
                "request_id": request_id,
                "code_name": nested["code_name"],
                "function_type": nested["function_type"],
                "player_channel": nested["player_channel"],
                "sound_resource_id": resource_id,
                "static_final_sound_ids": _join(final_ids),
                "runtime_observed_final_sound_ids": _join(observed_final_ids),
                "event_names": event_names,
                "request_to_resource_basis": nested["association_basis"],
                "resource_to_final_basis": (
                    "static_sound_id_records_sound_resource_id"
                    if final_ids
                    else "none"
                ),
                "event_association_basis": (
                    "static_event_timeline_request_id" if event_names else "none"
                ),
                "association_basis": (
                    "runtime_nested_request_to_resource+static_sound_id_record"
                    if final_ids
                    else "runtime_nested_request_to_resource"
                ),
                "complete_chain_observed": _text(complete),
                "status": (
                    "runtime_nested_static_final_and_csl_id_observed"
                    if complete
                    else "runtime_nested_static_final_not_observed_in_csl"
                    if final_ids
                    else "runtime_nested_resource_only"
                ),
            }
        )

    kind_counts = Counter(_text(event["payload"].get("kind")) for event in events)
    summary = {
        "schema_version": 1,
        "input_jsonl": str(jsonl_path.resolve()),
        "parse": parse_stats,
        "event_kind_counts": dict(sorted(kind_counts.items())),
        "table_counts": {name: len(rows) for name, rows in tables.items()},
        "rejected_temporal_context_event_count": rejected_temporal_count,
        "causal_policy": {
            "request_to_resource": "same-thread nested sndPlayReq inside performRequest only",
            "legacy_recent_or_global_context": "retained for audit, rejected as causal",
            "resource_to_final_sound_id": "optional static sound_id_records exact ID join",
            "csl_to_request": "never inferred by time",
        },
        "static_inputs": {
            "sound_requests_csv": str(sound_requests_csv.resolve()) if sound_requests_csv else "",
            "sound_reqdata_csv": str(sound_reqdata_csv.resolve()) if sound_reqdata_csv else "",
            "sound_id_records_csv": (
                str(sound_id_records_csv.resolve()) if sound_id_records_csv else ""
            ),
            "event_timeline_csv": str(event_timeline_csv.resolve()) if event_timeline_csv else "",
            "row_counts": {name: len(rows) for name, rows in static_rows.items()},
        },
        "complete_chain_count": sum(
            row["complete_chain_observed"] == "yes" for row in tables["chains"]
        ),
        "complete_chains": [
            row for row in tables["chains"] if row["complete_chain_observed"] == "yes"
        ],
    }
    return summary, tables


def write_csv(
    path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None
) -> None:
    fields = list(fields or [])
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    out_dir: Path,
    summary: dict[str, Any],
    tables: dict[str, list[dict[str, Any]]],
    prefix: str = "sound_logic",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for table_name, suffix in OUTPUT_TABLES.items():
        write_csv(
            out_dir / f"{prefix}_{suffix}",
            tables[table_name],
            TABLE_FIELDS[table_name],
        )
    (out_dir / f"{prefix}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _manifest_path(
    explicit: Path | None, manifest_dir: Path | None, filename: str
) -> Path | None:
    if explicit is not None:
        return explicit
    if manifest_dir is None:
        return None
    candidate = manifest_dir / filename
    return candidate if candidate.is_file() else None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--prefix", default="sound_logic")
    parser.add_argument("--asset-manifest-dir", type=Path)
    parser.add_argument(
        "--sound-requests-csv",
        "--sound-request-struct-requests-csv",
        dest="sound_requests_csv",
        type=Path,
    )
    parser.add_argument(
        "--sound-reqdata-csv",
        "--sound-request-struct-reqdata-csv",
        dest="sound_reqdata_csv",
        type=Path,
    )
    parser.add_argument("--sound-id-records-csv", type=Path)
    parser.add_argument("--event-timeline-csv", "--event-timeline-events-csv", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_dir = args.asset_manifest_dir
    sound_requests_csv = _manifest_path(
        args.sound_requests_csv, manifest_dir, "sound_request_struct_requests.csv"
    )
    sound_reqdata_csv = _manifest_path(
        args.sound_reqdata_csv, manifest_dir, "sound_request_struct_reqdata.csv"
    )
    sound_id_records_csv = _manifest_path(
        args.sound_id_records_csv, manifest_dir, "sound_id_records.csv"
    )
    event_timeline_csv = _manifest_path(
        args.event_timeline_csv, manifest_dir, "event_timeline_events.csv"
    )
    summary, tables = summarize(
        args.jsonl,
        sound_requests_csv=sound_requests_csv,
        sound_reqdata_csv=sound_reqdata_csv,
        sound_id_records_csv=sound_id_records_csv,
        event_timeline_csv=event_timeline_csv,
    )
    write_outputs(args.out_dir, summary, tables, args.prefix)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
