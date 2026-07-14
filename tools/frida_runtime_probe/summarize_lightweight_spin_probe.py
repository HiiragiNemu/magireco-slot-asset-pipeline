#!/usr/bin/env python3
"""Summarize `lightweight_spin_audio_probe.js` JSONL captures.

This is a mechanism-audit parser, not a renderer validator.  It extracts the
runtime facts that matter for the generic slot scheduler route:

- LC701A/ID401 command-buffer packets;
- whether the upstream story-dispatch candidate packet appears;
- RxCom/SdGmData stage/selector/lottery fields;
- BGM helper calls and final OpenSL queue metadata;
- real slot input state transitions.

It intentionally does not infer animation identity from `ac` suffixes, contact
sheets, or codec metadata.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PACKET_CALLBACKS: dict[int, tuple[str, str]] = {
    4: ("fnRxComMedalIN", "fnRxSubMedalIN"),
    5: ("fnRxComGmStart", "fnRxSubGmStart"),
    6: ("fnRxComRlStart", "fnRxSubRlStart"),
    7: ("fnRxComSpeed", "fnRxSubSpeed"),
    17: ("fnRxComDirInfo1", "fnRxSubDirInfo1"),
    18: ("fnRxComDirInfo2", "fnRxSubDirInfo2"),
    19: ("fnRxComDirInfo3", "fnRxSubDirInfo3"),
    20: ("fnRxComDirInfo4", "fnRxSubDirInfo4"),
    21: ("fnRxComDirInfo5", "fnRxSubDirInfo5"),
    22: ("fnRxComDirInfo6", "fnRxSubDirInfo6"),
    23: ("fnRxComDirInfo7", "fnRxSubDirInfo7"),
    24: ("fnRxComDirInfo8", "fnRxSubDirInfo8"),
    25: ("fnRxComDirInfo9", "fnRxSubDirInfo9"),
}

BGM_KINDS = {
    "obj_nml_snd_request_bgm_sequence",
    "obj_nml_snd_request_bgm_dir",
    "obj_nml_snd_request_bgm_stg",
    "obj_nml_snd_request_bgm_end",
    "obj_nml_snd_request_bgm_dir_next",
    "obj_nml_snd_request_bgm_fade_next",
    "obj_nml_snd_request_bgm_fade",
    "direction_macro_snd_bgm_play_leave",
    "direction_macro_snd_bgm_play",
}

SOUND_CODE_KINDS = {
    "ctrl_snd_req_sound_code",
    "ctrl_snd_req_sound_code_timed",
}

SP_STORY_SELECTORS_BY_STAGE = {
    11: {1, 2},
    12: {1, 2, 3, 4, 13, 14},
    13: {1, 2},
}

DIRECTION_MACRO_KINDS = {
    "direction_macro_snd_bgm_play",
    "direction_macro_dispatch",
    "direction_macro_snd_se_play_enter",
    "direction_macro_snd_se_play_leave",
    "direction_macro_snd_bgm_play_enter",
    "direction_macro_snd_bgm_play_leave",
    "direction_macro_snd_fade_play_enter",
    "direction_macro_snd_fade_play_leave",
    "direction_macro_change_anm",
    "direction_macro_event_play_enter",
    "direction_macro_event_play_leave",
    "direction_change_animation_resolved",
    "direction_scene_request",
    "direction_scene_only_request",
}

DIRECTION_MACRO_FIELDS = (
    "symbol",
    "return_symbol",
    "direction_controller",
    "direction_frame_sequence",
    "direction_entry_macro_bits_hex",
    "direction_active_mask_hex",
    "direction_effective_mask_hex",
    "direction_effective_mask_u32_low",
    "direction_table_index_u16",
    "direction_device_data_pointer",
    "direction_device_raw_0x28",
    "direction_device_macro_bits_hex_at_0x00",
    "direction_device_channel_u16_at_0x08",
    "direction_device_value_kind_u16_at_0x0a",
    "direction_device_payload0_hex_at_0x10",
    "direction_device_payload1_hex_at_0x18",
    "direction_device_payload0_pointer",
    "direction_device_payload1_pointer",
    "direction_device_payload0_text_utf8",
    "direction_device_payload0_text_error",
    "direction_device_payload1_text_utf8",
    "direction_device_payload1_text_error",
    "direction_device_selector_u8_at_0x20",
    "direction_device_enabled_u8_at_0x21",
    "direction_device_raw_u32_at_0x22",
    "direction_device_raw_u16_at_0x26",
    "direction_queue_base",
    "direction_queue_slot",
    "direction_queue_entry",
    "direction_queue_code0_pointer",
    "direction_queue_code1_pointer",
    "direction_queue_code0_text_utf8",
    "direction_queue_code0_text_error",
    "direction_queue_code1_text_utf8",
    "direction_queue_code1_text_error",
    "direction_queue_state_before_u16",
    "direction_queue_code0_before_pointer",
    "direction_queue_code1_before_pointer",
    "direction_queue_code0_before_text_utf8",
    "direction_queue_code1_before_text_utf8",
    "direction_queue_state_u16_at_0x10",
    "direction_queue_changed",
    "direction_event_queue_slot",
    "direction_event_queue_entry",
    "direction_event_info_pointer",
    "direction_event_queue_state_before_u16",
    "direction_event_code_before_hex",
    "direction_event_code_hex",
    "direction_event_queue_state_u16_at_0x08",
    "direction_event_queue_changed",
    "direction_animation_number_i32",
    "direction_change_arg2_u8",
    "animation_object",
    "event_code_hex",
    "request_arg2_u8",
    "request_arg3_u16",
    "request_arg4_u16",
)

RXCOM_KINDS = {
    "rxcom_dirinfo8_enter",
    "rxcom_dirinfo8_leave",
    "rxcom_dirinfo3_enter",
    "rxcom_dirinfo3_leave",
    "rxcom_gm_start_enter",
    "rxcom_gm_start_leave",
}

LOTTERY_KINDS = {
    "lot_dir_gm_start_enter",
    "lot_dir_gm_start_leave",
    "kndcal_lot_start_enter",
    "kndcal_lot_start_leave",
    "lot_other_after_get_param_enter",
    "lot_other_after_get_param_leave",
    "kndcal_usr_set_gr_dir_prm_copy_enter",
    "kndcal_usr_set_gr_dir_prm_copy_leave",
    "lot_ot_at_sp_stryknd_enter",
    "lot_ot_at_sp_stryknd_leave",
}

SLOT_STATE_KEYS = (
    "body_state",
    "body_mode",
    "body_credit",
    "body_bet",
    "body_input_mask",
    "body_button_state",
    "body_lever_state",
    "slot_input_enabled",
)

SDGM_KEYS = (
    "sdgm_rx_source_selector_u16_at_0x16e",
    "sdgm_rx_source_stage_u16_at_0x170",
    "sdgm_rx_dirinfo3_payload6_copy_u16_at_0x130",
    "sdgm_rx_dirinfo3_payload6_premdl_copy_u16_at_0x0a8",
    "sdgm_rx_dirinfo3_payload6_premdl_copy_u16_at_0x184",
    "sdgm_rx_pre_selector_u16_at_0x0ee",
    "sdgm_rx_pre_stage_u16_at_0x0ec",
    "sdgm_rx_copy_stage_u16_at_0x318",
    "sdgm_rx_copy_selector_u16_at_0x31a",
    "sdgm_lot_dir_case_u16_at_0x358",
    "sdgm_sp_story_special_case_u16_at_0x35e",
    "sdgm_sp_story_enable_u16_at_0x45a",
    "sdgm_sp_story_probability_selector_u16_at_0x592",
    "sdgm_source_story_no_u16_at_0x788",
    "sdgm_lot_stage_u16_at_0x1354",
    "sdgm_lot_substage_u16_at_0x1358",
    "sdgm_lot_mode_u8_at_0x135e",
    "sdgm_lot_dispatch_u16_at_0x13be",
    "sdgm_lot_start_gate_u16_at_0x14cc",
    "sdgm_lot_stage_gate_u16_at_0x14e2",
    "sdgm_lot_stage_gate_u16_at_0x14e4",
    "sdgm_lot_gate_u16_at_0x15a4",
    "sdgm_lot_gate_u8_at_0x1676",
    "sdgm_sp_story_kind_u16_at_0x1f82",
    "sdgm_sp_story_pool0_u16_at_0x1f84",
    "sdgm_sp_story_pool1_u16_at_0x1f86",
    "sdgm_sp_story_pool2_u16_at_0x1f88",
    "sdgm_sp_story_pool3_u16_at_0x1f8a",
    "sdgm_sp_story_pool4_u16_at_0x1f8c",
    "sdgm_sp_story_pool5_u16_at_0x1f8e",
    "sdgm_sp_story_pool6_u16_at_0x1f90",
    "sdgm_sp_story_pool7_u16_at_0x1f92",
    "sdgm_sp_story_premdl_kind_u16_at_0x2cde",
    "sdgm_sp_story_premdl_pool0_u16_at_0x2ce0",
    "sdgm_sp_story_premdl_pool1_u16_at_0x2ce2",
    "sdgm_sp_story_premdl_pool2_u16_at_0x2ce4",
    "sdgm_sp_story_premdl_pool3_u16_at_0x2ce6",
    "sdgm_sp_story_premdl_pool4_u16_at_0x2ce8",
    "sdgm_sp_story_premdl_pool5_u16_at_0x2cea",
    "sdgm_sp_story_premdl_pool6_u16_at_0x2cec",
    "sdgm_sp_story_premdl_pool7_u16_at_0x2cee",
    "sdgm_sp_story_lottery_result_u16_at_0x2fdc",
)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_number, json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_number, {
                    "event": "json_parse_error",
                    "parse_error": f"{path}:{line_number}: invalid JSON: {exc}",
                }


def payload_for(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("message", {}).get("payload")
    if isinstance(payload, dict):
        return payload
    return record


def kind_for(record: dict[str, Any], payload: dict[str, Any]) -> str:
    return str(
        payload.get("kind")
        or record.get("event")
        or record.get("message", {}).get("type")
        or "unknown"
    )


def rel_s(record: dict[str, Any], payload: dict[str, Any], first_ms: int | None) -> float | None:
    if first_ms is None:
        return None
    value = record.get("host_unix_ms") or payload.get("unix_ms")
    if value is None:
        return None
    return round((int(value) - first_ms) / 1000.0, 3)


def raw_from_packet(packet: dict[str, Any]) -> list[int] | None:
    raw = packet.get("raw")
    if isinstance(raw, list) and len(raw) >= 8:
        try:
            return [int(v) & 0xFF for v in raw[:8]]
        except (TypeError, ValueError):
            return None
    return None


def raw_from_access(payload: dict[str, Any]) -> list[int] | None:
    raw: list[int] = []
    for idx in range(8):
        key = f"id401_raw_packet_u8_at_{idx}"
        if key not in payload or payload[key] is None:
            return None
        try:
            raw.append(int(payload[key]) & 0xFF)
        except (TypeError, ValueError):
            return None
    return raw


def packet_row(
    *,
    line: int,
    rel_time: float | None,
    source_kind: str,
    source_field: str,
    offset: int | None,
    raw: list[int],
    packet: dict[str, Any] | None = None,
    dispatch_batch: int | None = None,
    thread_id: Any = None,
    buffer_pointer: Any = None,
) -> dict[str, Any]:
    packet_id = (raw[0] & 0x7F) if raw else None
    callback0 = ""
    callback1 = ""
    if packet:
        callback0 = str(packet.get("callback0_symbol") or packet.get("callback0") or "")
        callback1 = str(packet.get("callback1_symbol") or packet.get("callback1") or "")
    if not callback0 and packet_id in PACKET_CALLBACKS:
        callback0, callback1 = PACKET_CALLBACKS[int(packet_id)]
    story_dispatch_candidate = packet_id == 19 and len(raw) > 1 and raw[1] == 8
    sp_story_selection_candidate = (
        packet_id == 24
        and len(raw) > 3
        and raw[3] in SP_STORY_SELECTORS_BY_STAGE
        and raw[2] in SP_STORY_SELECTORS_BY_STAGE[raw[3]]
    )
    return {
        "line": line,
        "rel_s": rel_time,
        "source_kind": source_kind,
        "source_field": source_field,
        "observation_type": (
            "access_subprocess_dispatch"
            if source_field == "id401_access_subprocess_raw"
            else "copied_buffer"
            if source_field == "id401_command_buffer_packets"
            or source_field.startswith("copied_buffer.")
            else "buffer_or_state_snapshot"
        ),
        "dispatch_batch": dispatch_batch if dispatch_batch is not None else "",
        "thread_id": thread_id if thread_id is not None else "",
        "buffer_pointer": buffer_pointer if buffer_pointer is not None else "",
        "offset": offset if offset is not None else "",
        "packet_id": packet_id,
        "raw": raw,
        "raw_csv": " ".join(str(v) for v in raw),
        "candidate": story_dispatch_candidate,
        "story_dispatch_candidate": story_dispatch_candidate,
        "sp_story_selection_candidate": sp_story_selection_candidate,
        "callback0": callback0,
        "callback1": callback1,
    }


def collect_packets_from_field(
    rows: list[dict[str, Any]],
    *,
    line: int,
    rel_time: float | None,
    kind: str,
    source_field: str,
    packets: Any,
    dispatch_batch: int | None = None,
    thread_id: Any = None,
    buffer_pointer: Any = None,
) -> None:
    if not isinstance(packets, list):
        return
    for packet in packets:
        if not isinstance(packet, dict):
            continue
        raw = raw_from_packet(packet)
        if raw is None:
            continue
        rows.append(
            packet_row(
                line=line,
                rel_time=rel_time,
                source_kind=kind,
                source_field=source_field,
                offset=packet.get("offset"),
                raw=raw,
                packet=packet,
                dispatch_batch=dispatch_batch,
                thread_id=thread_id,
                buffer_pointer=buffer_pointer,
            )
        )


class DispatchBatchTracker:
    """Correlate real ``accessSubProcess`` calls with their command-buffer batch.

    The offline summarizer and the natural-spin hunt driver must use the same
    packet semantics.  Snapshot/copy observations are deliberately excluded:
    only an actual ``ID401::accessSubProcess`` call can complete a batch.

    ``strict=True`` is intended for new live evidence.  It requires a thread,
    a readable command-buffer base/length, an in-range packet pointer, and
    eight-byte packet alignment.  The default preserves the legacy summarizer's
    ability to describe older captures that lacked some of that metadata.
    """

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict
        self.dispatch_batch_index = 0
        self.metadata: dict[int, dict[str, Any]] = {}
        self.latest_batch_by_thread: dict[str, int] = {}
        self.rows_by_batch: dict[int, list[dict[str, Any]]] = {}

    def register_get_cmd_buf(
        self,
        payload: dict[str, Any],
        *,
        line: int,
        rel_time: float | None,
    ) -> int:
        self.dispatch_batch_index += 1
        batch = self.dispatch_batch_index
        thread_id = payload.get("thread_id")
        thread_key = str(thread_id) if thread_id is not None else ""
        if thread_key:
            self.latest_batch_by_thread[thread_key] = batch
        self.metadata[batch] = {
            "source_line": line,
            "source_rel_s": rel_time,
            "thread_id": thread_id if thread_id is not None else "",
            "get_cmd_buf_call_count": payload.get("high_level_call_count_for_kind", ""),
            "command_buffer_pointer": payload.get("id401_command_buffer_pointer", ""),
            "command_buffer_length": payload.get("id401_command_buffer_length", ""),
        }
        return batch

    def _resolve_access_batch(self, payload: dict[str, Any]) -> int | None:
        thread_id = payload.get("thread_id")
        thread_key = str(thread_id) if thread_id is not None else ""
        packet_address = pointer_int(payload.get("id401_packet_pointer"))

        if thread_key and thread_key in self.latest_batch_by_thread:
            batch = self.latest_batch_by_thread[thread_key]
            metadata = self.metadata.get(batch, {})
            base_address = pointer_int(metadata.get("command_buffer_pointer"))
            try:
                buffer_length = int(metadata.get("command_buffer_length"))
            except (TypeError, ValueError):
                buffer_length = 0

            if self.strict:
                if packet_address is None or base_address is None or buffer_length <= 0:
                    return None
                if not (
                    base_address <= packet_address
                    and packet_address + 8 <= base_address + buffer_length
                ):
                    return None
                if (packet_address - base_address) % 8 != 0:
                    return None
                return batch

            if (
                packet_address is None
                or base_address is None
                or buffer_length <= 0
                or base_address <= packet_address < base_address + buffer_length
            ):
                return batch
            return None

        if not self.strict and not thread_key and self.dispatch_batch_index:
            # Legacy captures did not record thread/pointer metadata.
            return self.dispatch_batch_index
        return None

    def observe_access(
        self,
        payload: dict[str, Any],
        *,
        line: int,
        rel_time: float | None,
        source_kind: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        raw = raw_from_access(payload)
        if raw is None:
            return None, None
        batch = self._resolve_access_batch(payload)
        row = packet_row(
            line=line,
            rel_time=rel_time,
            source_kind=source_kind,
            source_field="id401_access_subprocess_raw",
            offset=None,
            raw=raw,
            dispatch_batch=batch,
            thread_id=payload.get("thread_id"),
            buffer_pointer=payload.get("id401_packet_pointer"),
            packet={
                "callback0_symbol": payload.get("id401_callback0_symbol"),
                "callback1_symbol": payload.get("id401_callback1_symbol"),
            },
        )
        if isinstance(batch, int):
            self.rows_by_batch.setdefault(batch, []).append(row)
            summary = self.batch_summary(batch)
            if summary["complete_sp_story_candidate"]:
                # A real accessSubProcess batch can keep receiving packets after
                # it first becomes complete.  Live consumers need the refreshed
                # selection set (for example stage-12 selectors 1..4 arriving
                # after 13/14), while the offline summarizer ignores this return
                # value and derives one final summary per batch below.
                return row, summary
        return row, None

    def batch_summary(self, batch: int) -> dict[str, Any]:
        rows = self.rows_by_batch.get(batch, [])
        story_rows = [row for row in rows if row.get("story_dispatch_candidate")]
        selection_rows = [row for row in rows if row.get("sp_story_selection_candidate")]
        metadata = self.metadata.get(batch, {})
        story_raws = [list(row.get("raw") or []) for row in story_rows]
        selection_raws = [list(row.get("raw") or []) for row in selection_rows]
        return {
            "dispatch_batch": batch,
            "source_line": metadata.get("source_line", ""),
            "source_rel_s": metadata.get("source_rel_s", ""),
            "thread_id": metadata.get("thread_id", ""),
            "get_cmd_buf_call_count": metadata.get("get_cmd_buf_call_count", ""),
            "command_buffer_pointer": metadata.get("command_buffer_pointer", ""),
            "command_buffer_length": metadata.get("command_buffer_length", ""),
            "packet_count": len(rows),
            "packet_raw_csv": " | ".join(str(row.get("raw_csv") or "") for row in rows),
            "story_dispatch_candidate": bool(story_rows),
            "sp_story_selection_candidate": bool(selection_rows),
            "complete_sp_story_candidate": bool(story_rows and selection_rows),
            "story_dispatch_raw_csv": " | ".join(
                str(row.get("raw_csv") or "") for row in story_rows
            ),
            "sp_story_selection_raw_csv": " | ".join(
                str(row.get("raw_csv") or "") for row in selection_rows
            ),
            "story_dispatch_raws": story_raws,
            "sp_story_selection_raws": selection_raws,
            "sp_story_selection_pairs": [
                {"stage": raw[3], "selector": raw[2]}
                for raw in selection_raws
                if len(raw) == 8
            ],
        }

    def dispatch_batches(self) -> list[dict[str, Any]]:
        return [
            self.batch_summary(batch)
            for batch in sorted(self.rows_by_batch)
        ]


def small_sample(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    return rows[:limit]


def selected_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: payload.get(field) for field in fields if field in payload}


def packet_raw_csv(packet: dict[str, Any] | None) -> str:
    if not isinstance(packet, dict):
        return ""
    raw = raw_from_packet(packet)
    if raw is None:
        return ""
    return " ".join(str(value) for value in raw)


def staging_packets(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    packets = state.get("id401_staging_packets_at_0xf298")
    if not isinstance(packets, list):
        return []
    return [packet for packet in packets if isinstance(packet, dict)]


def flattened_packet_bytes(packets: list[dict[str, Any]]) -> list[int]:
    out: list[int] = []
    for packet in packets:
        raw = raw_from_packet(packet)
        if raw is not None:
            out.extend(raw)
    return out


def packet_at_offset(packets: list[dict[str, Any]], offset: int) -> dict[str, Any] | None:
    for packet in packets:
        if packet.get("offset") == offset:
            return packet
    return None


def packet_by_id(packets: list[dict[str, Any]], packet_id: int) -> dict[str, Any] | None:
    for packet in packets:
        raw = raw_from_packet(packet)
        if raw and (raw[0] & 0x7F) == packet_id:
            return packet
    return None


def changed_byte_summary(before: list[int], after: list[int], limit: int = 32) -> str:
    rows: list[str] = []
    max_len = max(len(before), len(after))
    for index in range(max_len):
        old = before[index] if index < len(before) else None
        new = after[index] if index < len(after) else None
        if old != new:
            rows.append(f"{index}:{'' if old is None else old}->{'' if new is None else new}")
            if len(rows) >= limit:
                remaining = sum(
                    1
                    for idx in range(index + 1, max_len)
                    if (before[idx] if idx < len(before) else None)
                    != (after[idx] if idx < len(after) else None)
                )
                if remaining:
                    rows.append(f"...+{remaining}")
                break
    return ";".join(rows)


def byte_list_csv(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    return " ".join("" if value is None else str(value) for value in values)


def changed_watch_byte_summary(
    before: Any,
    after: Any,
    base_address: Any,
    limit: int = 32,
) -> str:
    if not isinstance(before, list):
        before = []
    if not isinstance(after, list):
        after = []
    try:
        base = int(base_address)
    except (TypeError, ValueError):
        base = 0
    rows: list[str] = []
    max_len = max(len(before), len(after))
    for idx in range(max_len):
        b = before[idx] if idx < len(before) else None
        a = after[idx] if idx < len(after) else None
        if b != a:
            rows.append(f"{hex(base + idx)}:{b}->{a}")
            if len(rows) >= limit:
                remaining = sum(
                    1
                    for tail_idx in range(idx + 1, max_len)
                    if (before[tail_idx] if tail_idx < len(before) else None)
                    != (after[tail_idx] if tail_idx < len(after) else None)
                )
                if remaining:
                    rows.append(f"...+{remaining}")
                break
    return ";".join(rows)


def changed_addressed_byte_summary(
    before: Any,
    before_base_address: Any,
    after: Any,
    after_base_address: Any,
    limit: int = 32,
) -> str:
    """Compare moving byte windows by absolute VM address, not list index."""

    def addressed(values: Any, base_address: Any) -> dict[int, Any]:
        if not isinstance(values, list):
            return {}
        try:
            base = int(base_address)
        except (TypeError, ValueError):
            return {}
        return {base + index: value for index, value in enumerate(values)}

    before_by_address = addressed(before, before_base_address)
    after_by_address = addressed(after, after_base_address)
    rows: list[str] = []
    changed_addresses = [
        address
        for address in sorted(set(before_by_address) | set(after_by_address))
        if before_by_address.get(address) != after_by_address.get(address)
    ]
    for address in changed_addresses[:limit]:
        rows.append(
            f"{hex(address)}:{before_by_address.get(address)}->{after_by_address.get(address)}"
        )
    if len(changed_addresses) > limit:
        rows.append(f"...+{len(changed_addresses) - limit}")
    return ";".join(rows)


def state_field(state: dict[str, Any] | None, key: str) -> Any:
    if not isinstance(state, dict):
        return None
    return state.get(key)


def hex_int(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"0x{int(value):x}"
    except (TypeError, ValueError):
        return ""


def pointer_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return None


def payload_bytes(payload: dict[str, Any], prefix: str) -> list[int] | None:
    values: list[int] = []
    for idx in range(8):
        key = f"{prefix}{idx}"
        if key not in payload or payload[key] is None:
            return None
        try:
            values.append(int(payload[key]) & 0xFF)
        except (TypeError, ValueError):
            return None
    return values


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key, value in tuple(out.items()):
                if isinstance(value, (list, dict)):
                    out[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def summarize(path: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    counts: Counter[str] = Counter()
    first_ms: int | None = None
    parse_errors: list[str] = []
    hook_errors: list[dict[str, Any]] = []
    packet_rows: list[dict[str, Any]] = []
    rxcom_rows: list[dict[str, Any]] = []
    lottery_rows: list[dict[str, Any]] = []
    bgm_rows: list[dict[str, Any]] = []
    sound_code_rows: list[dict[str, Any]] = []
    direction_macro_rows: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []
    event_code_rows: list[dict[str, Any]] = []
    play_start_rows: list[dict[str, Any]] = []
    slot_rows: list[dict[str, Any]] = []
    command_state_change_rows: list[dict[str, Any]] = []
    core_state_change_rows: list[dict[str, Any]] = []
    opcode_staging_write_rows: list[dict[str, Any]] = []
    user_label_enters: dict[int, dict[str, Any]] = {}
    lc701a_transition_rows: list[dict[str, Any]] = []
    lc701a_enter_sequence_rows: list[dict[str, Any]] = []
    previous_user_label_enter: dict[str, Any] | None = None
    dispatch_tracker = DispatchBatchTracker()

    state_values: dict[str, set[Any]] = {key: set() for key in SLOT_STATE_KEYS}
    sdgm_values: dict[str, set[Any]] = {key: set() for key in SDGM_KEYS}

    for line, record in iter_jsonl(path):
        payload = payload_for(record)
        kind = kind_for(record, payload)
        counts[kind] += 1
        if first_ms is None:
            value = record.get("host_unix_ms") or payload.get("unix_ms")
            if value is not None:
                first_ms = int(value)
        t = rel_s(record, payload, first_ms)

        current_record_dispatch_batch: int | None = None
        if kind == "id401_get_cmd_buf_leave":
            current_record_dispatch_batch = dispatch_tracker.register_get_cmd_buf(
                payload,
                line=line,
                rel_time=t,
            )

        if kind != "json_parse_error" and "error" in kind.lower():
            hook_errors.append({"line": line, "kind": kind, "payload": payload})
        if payload.get("parse_error") or payload.get("sdgm_error"):
            err = payload.get("parse_error") or payload.get("sdgm_error")
            if err:
                parse_errors.append(f"{line}:{kind}:{err}")

        # Direct ID401 accessSubProcess packet.
        access_row, _new_complete_batch = dispatch_tracker.observe_access(
            payload,
            line=line,
            rel_time=t,
            source_kind=kind,
        )
        if access_row is not None:
            packet_rows.append(access_row)

        # Command-buffer packet arrays can appear directly, under copied_buffer,
        # and under LC701A before/after state snapshots.
        collect_packets_from_field(
            packet_rows,
            line=line,
            rel_time=t,
            kind=kind,
            source_field="id401_command_buffer_packets",
            packets=payload.get("id401_command_buffer_packets"),
            dispatch_batch=current_record_dispatch_batch,
            thread_id=payload.get("thread_id"),
            buffer_pointer=payload.get("id401_command_buffer_pointer"),
        )
        copied_buffer = payload.get("copied_buffer")
        if isinstance(copied_buffer, dict):
            collect_packets_from_field(
                packet_rows,
                line=line,
                rel_time=t,
                kind=kind,
                source_field="copied_buffer.id401_command_buffer_packets",
                packets=copied_buffer.get("id401_command_buffer_packets"),
                thread_id=payload.get("thread_id"),
                buffer_pointer=copied_buffer.get("id401_command_buffer_pointer"),
            )
        for state_name in ("state_before", "state_after"):
            state = payload.get(state_name)
            if isinstance(state, dict):
                for key in SLOT_STATE_KEYS:
                    value = state.get(key)
                    if value is not None:
                        state_values[key].add(value)
                collect_packets_from_field(
                    packet_rows,
                    line=line,
                    rel_time=t,
                    kind=kind,
                    source_field=f"{state_name}.id401_staging_packets_at_0xf298",
                    packets=state.get("id401_staging_packets_at_0xf298"),
                )
                collect_packets_from_field(
                    packet_rows,
                    line=line,
                    rel_time=t,
                    kind=kind,
                    source_field=f"{state_name}.id401_queue_packets_at_0x200ee",
                    packets=state.get("id401_queue_packets_at_0x200ee"),
                )

        for key in SDGM_KEYS:
            value = payload.get(key)
            if value is not None:
                sdgm_values[key].add(value)

        if kind in RXCOM_KINDS:
            row = {"line": line, "rel_s": t, "kind": kind}
            row.update(selected_fields(payload, SDGM_KEYS))
            rx_payload = payload_bytes(payload, "rxcom_payload_u8_at_")
            if rx_payload is not None:
                row["rxcom_payload"] = rx_payload
                row["rxcom_payload_csv"] = " ".join(str(v) for v in rx_payload)
            rxcom_rows.append(row)

        if kind in LOTTERY_KINDS:
            row = {"line": line, "rel_s": t, "kind": kind}
            row.update(selected_fields(payload, SDGM_KEYS))
            if "arg1" in payload:
                row["arg1"] = payload.get("arg1")
            if "arg2" in payload:
                row["arg2"] = payload.get("arg2")
            lottery_rows.append(row)

        if kind in BGM_KINDS:
            row = {
                "line": line,
                "rel_s": t,
                "kind": kind,
                "symbol": payload.get("symbol"),
                "return_symbol": payload.get("return_symbol"),
                "this_pointer": payload.get("this_pointer"),
            }
            row.update(selected_fields(payload, DIRECTION_MACRO_FIELDS))
            bgm_rows.append(row)

        if kind in SOUND_CODE_KINDS:
            sound_code_rows.append(
                {
                    "line": line,
                    "rel_s": t,
                    "kind": kind,
                    "sound_code_pointer": payload.get("sound_code_pointer"),
                    "sound_code": payload.get("sound_code_text_utf8"),
                    "sound_code_text_error": payload.get("sound_code_text_error"),
                    "arg2": payload.get("arg2_i32"),
                    "arg3": payload.get("arg3_i32"),
                    "return_symbol": payload.get("return_symbol"),
                }
            )

        if kind in DIRECTION_MACRO_KINDS:
            row = {"line": line, "rel_s": t, "kind": kind}
            row.update(selected_fields(payload, DIRECTION_MACRO_FIELDS))
            direction_macro_rows.append(row)

        if kind == "queue_enqueue_metadata":
            last = payload.get("last_play_start") or {}
            queue_rows.append(
                {
                    "line": line,
                    "rel_s": t,
                    "queue_object": payload.get("queue_object"),
                    "buffer_bytes": payload.get("buffer_bytes"),
                    "sound_id": last.get("sound_id_u16_at_0x2"),
                    "play_index": last.get("play_index_i32"),
                    "sound_u32_at_0x0": last.get("sound_u32_at_0x0"),
                    "return_symbol": payload.get("return_symbol"),
                }
            )

        if kind == "ctrl_snd_req_event_code":
            event_code_rows.append(
                {
                    "line": line,
                    "rel_s": t,
                    "event_code_hex": payload.get("event_code_hex"),
                    "event_code_i32_low": payload.get("event_code_i32_low"),
                    "return_symbol": payload.get("return_symbol"),
                }
            )

        if kind == "csl_mng_play_start":
            play_start_rows.append(
                {
                    "line": line,
                    "rel_s": t,
                    "sound_id": payload.get("sound_id_u16_at_0x2"),
                    "play_index": payload.get("play_index_i32"),
                    "sound_u32_at_0x0": payload.get("sound_u32_at_0x0"),
                    "return_symbol": payload.get("return_symbol"),
                }
            )

        if kind.startswith("slot_body_"):
            state = payload.get("state_before") or payload.get("state_after") or {}
            row = {"line": line, "rel_s": t, "kind": kind}
            if isinstance(state, dict):
                row.update({key: state.get(key) for key in SLOT_STATE_KEYS if key in state})
            slot_rows.append(row)

        if kind.endswith("_command_state_change") or kind.endswith("_core_state_change"):
            state_change_output_rows = (
                core_state_change_rows
                if kind.endswith("_core_state_change")
                else command_state_change_rows
            )
            before = payload.get("state_before")
            after = payload.get("state_after")
            before_packets = staging_packets(before)
            after_packets = staging_packets(after)
            before_bytes = flattened_packet_bytes(before_packets)
            after_bytes = flattened_packet_bytes(after_packets)
            source_watch_before = state_field(before, "id401_packet_source_watch_bytes_at_0xffe0")
            source_watch_after = state_field(after, "id401_packet_source_watch_bytes_at_0xffe0")
            source_watch_base = state_field(after, "id401_packet_source_watch_base_vm_addr") or state_field(
                before, "id401_packet_source_watch_base_vm_addr"
            )
            dirinfo3_before = packet_by_id(before_packets, 19)
            dirinfo3_after = packet_by_id(after_packets, 19)
            dirinfo3_after_raw = raw_from_packet(dirinfo3_after) if dirinfo3_after else None
            state_change_output_rows.append(
                {
                    "line": line,
                    "rel_s": t,
                    "kind": kind,
                    "symbol": payload.get("symbol"),
                    "return_symbol": payload.get("return_symbol"),
                    "retval_i32": payload.get("retval_i32"),
                    "lc701a_call_target_u16": payload.get("lc701a_call_target_u16"),
                    "pc_before": state_field(before, "id401_pc_u16_at_0x20"),
                    "pc_after": state_field(after, "id401_pc_u16_at_0x20"),
                    "pending_len_before": state_field(before, "id401_pending_len_u8_at_0xf0fe"),
                    "pending_len_after": state_field(after, "id401_pending_len_u8_at_0xf0fe"),
                    "queue_flag_before": state_field(before, "id401_command_queue_flag_u8_at_0x200ed"),
                    "queue_flag_after": state_field(after, "id401_command_queue_flag_u8_at_0x200ed"),
                    "queue_tail_before": state_field(before, "id401_command_queue_tail_u16_at_0x20cee"),
                    "queue_tail_after": state_field(after, "id401_command_queue_tail_u16_at_0x20cee"),
                    "source_watch_base": source_watch_base,
                    "source_watch_base_hex": hex_int(source_watch_base),
                    "source_watch_before": byte_list_csv(source_watch_before),
                    "source_watch_after": byte_list_csv(source_watch_after),
                    "source_watch_changed_bytes": changed_watch_byte_summary(
                        source_watch_before, source_watch_after, source_watch_base
                    ),
                    "lc701a_sp_before": state_field(before, "lc701a_sp_u16_at_0x0e"),
                    "lc701a_sp_after": state_field(after, "lc701a_sp_u16_at_0x0e"),
                    "lc701a_bank_before": state_field(before, "lc701a_bank_u8_at_0x70"),
                    "lc701a_bank_after": state_field(after, "lc701a_bank_u8_at_0x70"),
                    "lc701a_reg02_u16_before": state_field(before, "lc701a_reg_u16_at_0x02"),
                    "lc701a_reg02_u16_after": state_field(after, "lc701a_reg_u16_at_0x02"),
                    "lc701a_reg04_u16_before": state_field(before, "lc701a_reg_u16_at_0x04"),
                    "lc701a_reg04_u16_after": state_field(after, "lc701a_reg_u16_at_0x04"),
                    "lc701a_reg06_u16_before": state_field(before, "lc701a_reg_u16_at_0x06"),
                    "lc701a_reg06_u16_after": state_field(after, "lc701a_reg_u16_at_0x06"),
                    "lc701a_reg08_u16_before": state_field(before, "lc701a_reg_u16_at_0x08"),
                    "lc701a_reg08_u16_after": state_field(after, "lc701a_reg_u16_at_0x08"),
                    "lc701a_stack_window_valid_before": state_field(
                        before, "lc701a_stack_window_valid"
                    ),
                    "lc701a_stack_window_valid_after": state_field(
                        after, "lc701a_stack_window_valid"
                    ),
                    "lc701a_stack_window_base_before": state_field(
                        before, "lc701a_stack_window_base_vm_addr"
                    ),
                    "lc701a_stack_window_base_after": state_field(
                        after, "lc701a_stack_window_base_vm_addr"
                    ),
                    "lc701a_stack_window_before": byte_list_csv(
                        state_field(before, "lc701a_stack_window_bytes")
                    ),
                    "lc701a_stack_window_after": byte_list_csv(
                        state_field(after, "lc701a_stack_window_bytes")
                    ),
                    "lc701a_stack_window_changed_bytes": changed_addressed_byte_summary(
                        state_field(before, "lc701a_stack_window_bytes"),
                        state_field(before, "lc701a_stack_window_base_vm_addr"),
                        state_field(after, "lc701a_stack_window_bytes"),
                        state_field(after, "lc701a_stack_window_base_vm_addr"),
                    ),
                    "lc701a_reg03_before": state_field(before, "lc701a_reg_u8_at_0x03"),
                    "lc701a_reg03_after": state_field(after, "lc701a_reg_u8_at_0x03"),
                    "lc701a_reg04_before": state_field(before, "lc701a_reg_u8_at_0x04"),
                    "lc701a_reg04_after": state_field(after, "lc701a_reg_u8_at_0x04"),
                    "lc701a_count05_before": state_field(before, "lc701a_reg_u8_at_0x05_count"),
                    "lc701a_count05_after": state_field(after, "lc701a_reg_u8_at_0x05_count"),
                    "lc701a_addr06_before": state_field(before, "lc701a_addr_u16_at_0x06"),
                    "lc701a_addr06_after": state_field(after, "lc701a_addr_u16_at_0x06"),
                    "lc701a_addr08_before": state_field(before, "lc701a_addr_u16_at_0x08"),
                    "lc701a_addr08_after": state_field(after, "lc701a_addr_u16_at_0x08"),
                    "asm7e_dst_addr_before": state_field(before, "lc701a_asm_7e_dst_addr_u16_at_0x06"),
                    "asm7e_dst_addr_after": state_field(after, "lc701a_asm_7e_dst_addr_u16_at_0x06"),
                    "asm7e_src_addr_before": state_field(before, "lc701a_asm_7e_src_addr_u16_at_0x08"),
                    "asm7e_src_addr_after": state_field(after, "lc701a_asm_7e_src_addr_u16_at_0x08"),
                    "asm7e_count_before": state_field(before, "lc701a_asm_7e_count_u8_at_0x05"),
                    "asm7e_count_after": state_field(after, "lc701a_asm_7e_count_u8_at_0x05"),
                    "asm7e_src_byte_before": state_field(before, "lc701a_asm_7e_src_byte"),
                    "asm7e_src_byte_after": state_field(after, "lc701a_asm_7e_src_byte"),
                    "asm7e_dst_byte_before": state_field(before, "lc701a_asm_7e_dst_byte"),
                    "asm7e_dst_byte_after": state_field(after, "lc701a_asm_7e_dst_byte"),
                    "asm77_dst_addr_before": state_field(before, "lc701a_asm_77_dst_addr_u16_at_0x08"),
                    "asm77_dst_addr_after": state_field(after, "lc701a_asm_77_dst_addr_u16_at_0x08"),
                    "asm77_src_reg_before": state_field(before, "lc701a_asm_77_src_reg_u8_at_0x03"),
                    "asm77_src_reg_after": state_field(after, "lc701a_asm_77_src_reg_u8_at_0x03"),
                    "asm77_dst_byte_before": state_field(before, "lc701a_asm_77_dst_byte"),
                    "asm77_dst_byte_after": state_field(after, "lc701a_asm_77_dst_byte"),
                    "staging_raw_before": " | ".join(packet_raw_csv(packet) for packet in before_packets),
                    "staging_raw_after": " | ".join(packet_raw_csv(packet) for packet in after_packets),
                    "changed_bytes": changed_byte_summary(before_bytes, after_bytes),
                    "dirinfo3_raw_before": packet_raw_csv(dirinfo3_before),
                    "dirinfo3_raw_after": packet_raw_csv(dirinfo3_after),
                    "dirinfo3_byte1_after": dirinfo3_after_raw[1] if dirinfo3_after_raw else "",
                    "dirinfo3_byte2_after": dirinfo3_after_raw[2] if dirinfo3_after_raw else "",
                    "candidate_after": bool(
                        dirinfo3_after_raw
                        and len(dirinfo3_after_raw) > 1
                        and (dirinfo3_after_raw[0] & 0x7F) == 19
                        and dirinfo3_after_raw[1] == 8
                    ),
                }
            )

        if kind.endswith("_staging_write"):
            dst_addr = payload.get("lc701a_staging_write_dst_addr")
            src_addr = payload.get("lc701a_staging_write_src_addr")
            opcode_staging_write_rows.append(
                {
                    "line": line,
                    "rel_s": t,
                    "kind": kind,
                    "symbol": payload.get("symbol"),
                    "return_symbol": payload.get("return_symbol"),
                    "retval_i32": payload.get("retval_i32"),
                    "pc_before": payload.get("pc_before"),
                    "pc_after": payload.get("pc_after"),
                    "pending_len_before": payload.get("pending_len_before"),
                    "pending_len_after": payload.get("pending_len_after"),
                    "opcode": payload.get("lc701a_staging_write_opcode"),
                    "dst_addr": dst_addr,
                    "dst_addr_hex": hex_int(dst_addr),
                    "byte_offset": payload.get("lc701a_staging_write_byte_offset"),
                    "packet_offset": payload.get("lc701a_staging_write_packet_offset"),
                    "packet_byte_index": payload.get("lc701a_staging_write_packet_byte_index"),
                    "packet_id_before": payload.get("lc701a_staging_write_packet_id_before"),
                    "packet_id_after": payload.get("lc701a_staging_write_packet_id_after"),
                    "src_addr": src_addr,
                    "src_addr_hex": hex_int(src_addr),
                    "src_byte_before": payload.get("lc701a_staging_write_src_byte_before"),
                    "src_reg_byte_before": payload.get("lc701a_staging_write_src_reg_byte_before"),
                    "dst_byte_before": payload.get("lc701a_staging_write_dst_byte_before"),
                    "dst_byte_after": payload.get("lc701a_staging_write_dst_byte_after"),
                    "count_before": payload.get("lc701a_staging_write_count_before"),
                    "in_dirinfo3_packet_slot": payload.get("lc701a_staging_write_in_dirinfo3_packet_slot"),
                    "in_dirinfo8_packet_slot": payload.get("lc701a_staging_write_in_dirinfo8_packet_slot"),
                    "is_dirinfo3_raw_byte1": payload.get("lc701a_staging_write_is_dirinfo3_raw_byte1"),
                    "is_dirinfo3_raw_byte2": payload.get("lc701a_staging_write_is_dirinfo3_raw_byte2"),
                    "is_dirinfo8_raw_byte2": payload.get("lc701a_staging_write_is_dirinfo8_raw_byte2"),
                    "is_dirinfo8_raw_byte3": payload.get("lc701a_staging_write_is_dirinfo8_raw_byte3"),
                }
            )

        if kind == "id401_user_label_work_enter":
            call_count = payload.get("high_level_call_count_for_kind")
            if isinstance(call_count, int):
                current_enter = {
                    "line": line,
                    "rel_s": t,
                    "payload": payload,
                }
                user_label_enters[call_count] = current_enter
                if previous_user_label_enter is not None:
                    before = previous_user_label_enter["payload"].get("state_before")
                    after = payload.get("state_before")
                    before_packets = staging_packets(before)
                    after_packets = staging_packets(after)
                    before_bytes = flattened_packet_bytes(before_packets)
                    after_bytes = flattened_packet_bytes(after_packets)
                    dirinfo3_before = packet_by_id(before_packets, 19)
                    dirinfo3_after = packet_by_id(after_packets, 19)
                    dirinfo3_after_raw = raw_from_packet(dirinfo3_after) if dirinfo3_after else None
                    prev_call = previous_user_label_enter["payload"].get("high_level_call_count_for_kind")
                    lc701a_enter_sequence_rows.append(
                        {
                            "prev_call_count": prev_call,
                            "call_count": call_count,
                            "line_prev_enter": previous_user_label_enter["line"],
                            "line_enter": line,
                            "rel_s_prev_enter": previous_user_label_enter["rel_s"],
                            "rel_s_enter": t,
                            "pc_prev": state_field(before, "id401_pc_u16_at_0x20"),
                            "pc": state_field(after, "id401_pc_u16_at_0x20"),
                            "pending_len_prev": state_field(before, "id401_pending_len_u8_at_0xf0fe"),
                            "pending_len": state_field(after, "id401_pending_len_u8_at_0xf0fe"),
                            "queue_flag_prev": state_field(before, "id401_command_queue_flag_u8_at_0x200ed"),
                            "queue_flag": state_field(after, "id401_command_queue_flag_u8_at_0x200ed"),
                            "queue_tail_prev": state_field(before, "id401_command_queue_tail_u16_at_0x20cee"),
                            "queue_tail": state_field(after, "id401_command_queue_tail_u16_at_0x20cee"),
                            "staging_raw_prev": " | ".join(packet_raw_csv(packet) for packet in before_packets),
                            "staging_raw": " | ".join(packet_raw_csv(packet) for packet in after_packets),
                            "changed_bytes": changed_byte_summary(before_bytes, after_bytes),
                            "dirinfo3_raw_prev": packet_raw_csv(dirinfo3_before),
                            "dirinfo3_raw": packet_raw_csv(dirinfo3_after),
                            "dirinfo3_byte1": dirinfo3_after_raw[1] if dirinfo3_after_raw else "",
                            "dirinfo3_byte2": dirinfo3_after_raw[2] if dirinfo3_after_raw else "",
                            "candidate": bool(
                                dirinfo3_after_raw
                                and len(dirinfo3_after_raw) > 1
                                and (dirinfo3_after_raw[0] & 0x7F) == 19
                                and dirinfo3_after_raw[1] == 8
                            ),
                        }
                    )
                previous_user_label_enter = current_enter

        if kind == "id401_user_label_work_leave":
            call_count = payload.get("high_level_call_count_for_kind")
            enter = user_label_enters.get(call_count) if isinstance(call_count, int) else None
            if enter is not None:
                before = enter["payload"].get("state_before")
                after = payload.get("state_after")
                before_packets = staging_packets(before)
                after_packets = staging_packets(after)
                before_bytes = flattened_packet_bytes(before_packets)
                after_bytes = flattened_packet_bytes(after_packets)
                dirinfo3_before = packet_by_id(before_packets, 19)
                dirinfo3_after = packet_by_id(after_packets, 19)
                dirinfo3_after_raw = raw_from_packet(dirinfo3_after) if dirinfo3_after else None
                lc701a_transition_rows.append(
                    {
                        "call_count": call_count,
                        "line_enter": enter["line"],
                        "line_leave": line,
                        "rel_s_enter": enter["rel_s"],
                        "rel_s_leave": t,
                        "pc_before": state_field(before, "id401_pc_u16_at_0x20"),
                        "pc_after": state_field(after, "id401_pc_u16_at_0x20"),
                        "pending_len_before": state_field(before, "id401_pending_len_u8_at_0xf0fe"),
                        "pending_len_after": state_field(after, "id401_pending_len_u8_at_0xf0fe"),
                        "queue_flag_before": state_field(before, "id401_command_queue_flag_u8_at_0x200ed"),
                        "queue_flag_after": state_field(after, "id401_command_queue_flag_u8_at_0x200ed"),
                        "queue_tail_before": state_field(before, "id401_command_queue_tail_u16_at_0x20cee"),
                        "queue_tail_after": state_field(after, "id401_command_queue_tail_u16_at_0x20cee"),
                        "staging_packet_count_before": len(before_packets),
                        "staging_packet_count_after": len(after_packets),
                        "staging_raw_before": " | ".join(packet_raw_csv(packet) for packet in before_packets),
                        "staging_raw_after": " | ".join(packet_raw_csv(packet) for packet in after_packets),
                        "changed_bytes": changed_byte_summary(before_bytes, after_bytes),
                        "dirinfo3_raw_before": packet_raw_csv(dirinfo3_before),
                        "dirinfo3_raw_after": packet_raw_csv(dirinfo3_after),
                        "dirinfo3_byte1_after": dirinfo3_after_raw[1] if dirinfo3_after_raw else "",
                        "dirinfo3_byte2_after": dirinfo3_after_raw[2] if dirinfo3_after_raw else "",
                        "candidate_after": bool(
                            dirinfo3_after_raw
                            and len(dirinfo3_after_raw) > 1
                            and (dirinfo3_after_raw[0] & 0x7F) == 19
                            and dirinfo3_after_raw[1] == 8
                        ),
                    }
                )

    unique_packets: dict[tuple[int, ...], dict[str, Any]] = {}
    for row in packet_rows:
        raw_tuple = tuple(row["raw"])
        unique_packets.setdefault(raw_tuple, row)

    dispatch_packet_rows = [
        row for row in packet_rows if row.get("observation_type") == "access_subprocess_dispatch"
    ]
    copied_buffer_packet_rows = [
        row for row in packet_rows if row.get("observation_type") == "copied_buffer"
    ]
    snapshot_packet_rows = [
        row for row in packet_rows if row.get("observation_type") == "buffer_or_state_snapshot"
    ]
    candidate_observations = [row for row in packet_rows if row["candidate"]]
    candidate_packets = [row for row in dispatch_packet_rows if row["candidate"]]
    sp_story_selection_candidate_observations = [
        row for row in packet_rows if row.get("sp_story_selection_candidate")
    ]
    sp_story_selection_candidate_packets = [
        row for row in dispatch_packet_rows if row.get("sp_story_selection_candidate")
    ]
    dirinfo3_packets = [
        row
        for row in packet_rows
        if row.get("packet_id") == 19
        or row.get("callback0") == "fnRxComDirInfo3"
    ]
    dirinfo8_packets = [
        row
        for row in packet_rows
        if row.get("packet_id") == 24
        or row.get("callback0") == "fnRxComDirInfo8"
    ]
    dirinfo3_dispatch_packets = [row for row in dispatch_packet_rows if row.get("packet_id") == 19]
    dirinfo8_dispatch_packets = [row for row in dispatch_packet_rows if row.get("packet_id") == 24]

    dispatch_batches = dispatch_tracker.dispatch_batches()

    bgm_pending_queue_mutations = [
        row
        for row in bgm_rows
        if row.get("kind") == "direction_macro_snd_bgm_play_leave"
        and row.get("direction_queue_changed") is True
        and row.get("direction_queue_state_u16_at_0x10") == 1
        and bool(row.get("direction_queue_code0_text_utf8"))
    ]

    summary = {
        "observer": str(path),
        "observer_bytes": path.stat().st_size,
        "kind_counts": dict(counts.most_common()),
        "parse_errors": parse_errors,
        "hook_error_count": len(hook_errors),
        "hook_errors_first": small_sample(hook_errors, 10),
        "state_values": {
            key: sorted(values)
            for key, values in state_values.items()
            if values
        },
        "sdgm_values": {
            key: sorted(values)
            for key, values in sdgm_values.items()
            if values
        },
        "packet_count": len(packet_rows),
        "packet_observation_count": len(packet_rows),
        "access_subprocess_dispatch_count": len(dispatch_packet_rows),
        "copied_buffer_packet_observation_count": len(copied_buffer_packet_rows),
        "snapshot_packet_observation_count": len(snapshot_packet_rows),
        "unique_packet_count": len(unique_packets),
        "unique_packets": list(unique_packets.values()),
        "dirinfo3_packet_count": len(dirinfo3_packets),
        "dirinfo3_dispatch_count": len(dirinfo3_dispatch_packets),
        "dirinfo3_dispatch_packets": dirinfo3_dispatch_packets,
        "dirinfo3_packets": small_sample(dirinfo3_packets, 20),
        "candidate_count": len(candidate_packets),
        "candidate_packets": candidate_packets,
        "candidate_observation_count": len(candidate_observations),
        "dirinfo8_packet_count": len(dirinfo8_packets),
        "dirinfo8_dispatch_count": len(dirinfo8_dispatch_packets),
        "dirinfo8_dispatch_packets": dirinfo8_dispatch_packets,
        "dirinfo8_packets": small_sample(dirinfo8_packets, 20),
        "sp_story_selection_candidate_count": len(sp_story_selection_candidate_packets),
        "sp_story_selection_candidate_packets": sp_story_selection_candidate_packets,
        "sp_story_selection_candidate_observation_count": len(
            sp_story_selection_candidate_observations
        ),
        "dispatch_batch_count": len(dispatch_batches),
        "complete_sp_story_batch_candidate_count": sum(
            1 for row in dispatch_batches if row["complete_sp_story_candidate"]
        ),
        "dispatch_batches": dispatch_batches,
        "rxcom_rows_count": len(rxcom_rows),
        "rxcom_rows_first": small_sample(rxcom_rows, 20),
        "lottery_rows_count": len(lottery_rows),
        "lottery_rows_first": small_sample(lottery_rows, 20),
        "bgm_event_count": len(bgm_rows),
        "bgm_event_kind_counts": dict(Counter(row["kind"] for row in bgm_rows).most_common()),
        "bgm_rows_first": small_sample(bgm_rows, 20),
        "bgm_pending_queue_mutation_count": len(bgm_pending_queue_mutations),
        "bgm_pending_queue_mutations": bgm_pending_queue_mutations,
        "sound_code_request_count": len(sound_code_rows),
        "sound_code_rows": sound_code_rows,
        "direction_macro_event_count": len(direction_macro_rows),
        "direction_macro_kind_counts": dict(
            Counter(row["kind"] for row in direction_macro_rows).most_common()
        ),
        "direction_macro_rows_first": small_sample(direction_macro_rows, 80),
        "queue_event_count": len(queue_rows),
        "queue_rows": queue_rows,
        "event_code_count": len(event_code_rows),
        "event_code_rows": event_code_rows,
        "play_start_count": len(play_start_rows),
        "play_start_rows": play_start_rows,
        "slot_event_count": len(slot_rows),
        "slot_rows_first": small_sample(slot_rows, 40),
        "slot_rows_last": slot_rows[-40:],
        "command_state_change_count": len(command_state_change_rows),
        "command_state_change_kind_counts": dict(
            Counter(row["kind"] for row in command_state_change_rows).most_common()
        ),
        "command_state_change_candidate_after_count": sum(
            1 for row in command_state_change_rows if row.get("candidate_after")
        ),
        "command_state_change_first": small_sample(command_state_change_rows, 80),
        "core_state_change_count": len(core_state_change_rows),
        "core_state_change_kind_counts": dict(
            Counter(row["kind"] for row in core_state_change_rows).most_common()
        ),
        "core_state_change_first": small_sample(core_state_change_rows, 80),
        "opcode_staging_write_count": len(opcode_staging_write_rows),
        "opcode_staging_write_kind_counts": dict(
            Counter(row["kind"] for row in opcode_staging_write_rows).most_common()
        ),
        "opcode_staging_write_dirinfo3_byte1_count": sum(
            1 for row in opcode_staging_write_rows if row.get("is_dirinfo3_raw_byte1")
        ),
        "opcode_staging_write_dirinfo3_byte2_count": sum(
            1 for row in opcode_staging_write_rows if row.get("is_dirinfo3_raw_byte2")
        ),
        "opcode_staging_write_dirinfo8_byte2_count": sum(
            1 for row in opcode_staging_write_rows if row.get("is_dirinfo8_raw_byte2")
        ),
        "opcode_staging_write_dirinfo8_byte3_count": sum(
            1 for row in opcode_staging_write_rows if row.get("is_dirinfo8_raw_byte3")
        ),
        "opcode_staging_write_first": small_sample(opcode_staging_write_rows, 80),
        "lc701a_transition_count": len(lc701a_transition_rows),
        "lc701a_transition_changed_count": sum(
            1 for row in lc701a_transition_rows if row.get("changed_bytes")
        ),
        "lc701a_transition_candidate_after_count": sum(
            1 for row in lc701a_transition_rows if row.get("candidate_after")
        ),
        "lc701a_transition_changed_first": small_sample(
            [row for row in lc701a_transition_rows if row.get("changed_bytes")],
            40,
        ),
        "lc701a_enter_sequence_count": len(lc701a_enter_sequence_rows),
        "lc701a_enter_sequence_changed_count": sum(
            1 for row in lc701a_enter_sequence_rows if row.get("changed_bytes")
        ),
        "lc701a_enter_sequence_candidate_count": sum(
            1 for row in lc701a_enter_sequence_rows if row.get("candidate")
        ),
        "lc701a_enter_sequence_changed_first": small_sample(
            [row for row in lc701a_enter_sequence_rows if row.get("changed_bytes")],
            80,
        ),
    }

    tables = {
        "packets": packet_rows,
        "dispatch_packets": dispatch_packet_rows,
        "dispatch_batches": dispatch_batches,
        "rxcom": rxcom_rows,
        "lottery": lottery_rows,
        "bgm": bgm_rows,
        "sound_codes": sound_code_rows,
        "direction_macros": direction_macro_rows,
        "queue": queue_rows,
        "event_codes": event_code_rows,
        "play_start": play_start_rows,
        "slot": slot_rows,
        "command_state_changes": command_state_change_rows,
        "core_state_changes": core_state_change_rows,
        "opcode_staging_writes": opcode_staging_write_rows,
        "lc701a_transitions": lc701a_transition_rows,
        "lc701a_enter_sequence": lc701a_enter_sequence_rows,
    }
    return summary, tables


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--prefix", default=None)
    args = parser.parse_args()

    path = args.jsonl
    out_dir = args.out_dir or path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or path.stem.replace("observer_", "summary_")

    summary, tables = summarize(path)

    summary_path = out_dir / f"{prefix}.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    write_csv(
        out_dir / f"{prefix}_packets.csv",
        tables["packets"],
        [
            "line",
            "rel_s",
            "source_kind",
            "source_field",
            "observation_type",
            "dispatch_batch",
            "thread_id",
            "buffer_pointer",
            "offset",
            "packet_id",
            "raw_csv",
            "candidate",
            "story_dispatch_candidate",
            "sp_story_selection_candidate",
            "callback0",
            "callback1",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_dispatch_packets.csv",
        tables["dispatch_packets"],
        [
            "line",
            "rel_s",
            "dispatch_batch",
            "thread_id",
            "buffer_pointer",
            "packet_id",
            "raw_csv",
            "story_dispatch_candidate",
            "sp_story_selection_candidate",
            "callback0",
            "callback1",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_dispatch_batches.csv",
        tables["dispatch_batches"],
        [
            "dispatch_batch",
            "source_line",
            "source_rel_s",
            "thread_id",
            "get_cmd_buf_call_count",
            "command_buffer_pointer",
            "command_buffer_length",
            "packet_count",
            "packet_raw_csv",
            "story_dispatch_candidate",
            "sp_story_selection_candidate",
            "complete_sp_story_candidate",
            "story_dispatch_raw_csv",
            "sp_story_selection_raw_csv",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_rxcom.csv",
        tables["rxcom"],
        ["line", "rel_s", "kind", "rxcom_payload_csv", *SDGM_KEYS],
    )
    write_csv(
        out_dir / f"{prefix}_lottery.csv",
        tables["lottery"],
        ["line", "rel_s", "kind", "arg1", "arg2", *SDGM_KEYS],
    )
    write_csv(
        out_dir / f"{prefix}_bgm.csv",
        tables["bgm"],
        ["line", "rel_s", "kind", "this_pointer", *DIRECTION_MACRO_FIELDS],
    )
    write_csv(
        out_dir / f"{prefix}_sound_codes.csv",
        tables["sound_codes"],
        [
            "line",
            "rel_s",
            "kind",
            "sound_code_pointer",
            "sound_code",
            "sound_code_text_error",
            "arg2",
            "arg3",
            "return_symbol",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_direction_macros.csv",
        tables["direction_macros"],
        ["line", "rel_s", "kind", *DIRECTION_MACRO_FIELDS],
    )
    write_csv(
        out_dir / f"{prefix}_queue.csv",
        tables["queue"],
        [
            "line",
            "rel_s",
            "queue_object",
            "buffer_bytes",
            "sound_id",
            "play_index",
            "sound_u32_at_0x0",
            "return_symbol",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_event_codes.csv",
        tables["event_codes"],
        ["line", "rel_s", "event_code_hex", "event_code_i32_low", "return_symbol"],
    )
    write_csv(
        out_dir / f"{prefix}_play_start.csv",
        tables["play_start"],
        ["line", "rel_s", "sound_id", "play_index", "sound_u32_at_0x0", "return_symbol"],
    )
    write_csv(
        out_dir / f"{prefix}_slot.csv",
        tables["slot"],
        ["line", "rel_s", "kind", *SLOT_STATE_KEYS],
    )
    write_csv(
        out_dir / f"{prefix}_command_state_changes.csv",
        tables["command_state_changes"],
        [
            "line",
            "rel_s",
            "kind",
            "symbol",
            "return_symbol",
            "retval_i32",
            "lc701a_call_target_u16",
            "pc_before",
            "pc_after",
            "pending_len_before",
            "pending_len_after",
            "queue_flag_before",
            "queue_flag_after",
            "queue_tail_before",
            "queue_tail_after",
            "source_watch_base",
            "source_watch_base_hex",
            "source_watch_before",
            "source_watch_after",
            "source_watch_changed_bytes",
            "lc701a_sp_before",
            "lc701a_sp_after",
            "lc701a_bank_before",
            "lc701a_bank_after",
            "lc701a_reg02_u16_before",
            "lc701a_reg02_u16_after",
            "lc701a_reg04_u16_before",
            "lc701a_reg04_u16_after",
            "lc701a_reg06_u16_before",
            "lc701a_reg06_u16_after",
            "lc701a_reg08_u16_before",
            "lc701a_reg08_u16_after",
            "lc701a_stack_window_valid_before",
            "lc701a_stack_window_valid_after",
            "lc701a_stack_window_base_before",
            "lc701a_stack_window_base_after",
            "lc701a_stack_window_before",
            "lc701a_stack_window_after",
            "lc701a_stack_window_changed_bytes",
            "lc701a_reg03_before",
            "lc701a_reg03_after",
            "lc701a_reg04_before",
            "lc701a_reg04_after",
            "lc701a_count05_before",
            "lc701a_count05_after",
            "lc701a_addr06_before",
            "lc701a_addr06_after",
            "lc701a_addr08_before",
            "lc701a_addr08_after",
            "asm7e_dst_addr_before",
            "asm7e_dst_addr_after",
            "asm7e_src_addr_before",
            "asm7e_src_addr_after",
            "asm7e_count_before",
            "asm7e_count_after",
            "asm7e_src_byte_before",
            "asm7e_src_byte_after",
            "asm7e_dst_byte_before",
            "asm7e_dst_byte_after",
            "asm77_dst_addr_before",
            "asm77_dst_addr_after",
            "asm77_src_reg_before",
            "asm77_src_reg_after",
            "asm77_dst_byte_before",
            "asm77_dst_byte_after",
            "staging_raw_before",
            "staging_raw_after",
            "changed_bytes",
            "dirinfo3_raw_before",
            "dirinfo3_raw_after",
            "dirinfo3_byte1_after",
            "dirinfo3_byte2_after",
            "candidate_after",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_core_state_changes.csv",
        tables["core_state_changes"],
        [
            "line",
            "rel_s",
            "kind",
            "symbol",
            "return_symbol",
            "lc701a_call_target_u16",
            "pc_before",
            "pc_after",
            "lc701a_sp_before",
            "lc701a_sp_after",
            "lc701a_bank_before",
            "lc701a_bank_after",
            "lc701a_reg02_u16_before",
            "lc701a_reg02_u16_after",
            "lc701a_reg04_u16_before",
            "lc701a_reg04_u16_after",
            "lc701a_reg06_u16_before",
            "lc701a_reg06_u16_after",
            "lc701a_reg08_u16_before",
            "lc701a_reg08_u16_after",
            "source_watch_base",
            "source_watch_base_hex",
            "source_watch_before",
            "source_watch_after",
            "lc701a_stack_window_valid_before",
            "lc701a_stack_window_valid_after",
            "lc701a_stack_window_base_before",
            "lc701a_stack_window_base_after",
            "lc701a_stack_window_before",
            "lc701a_stack_window_after",
            "lc701a_stack_window_changed_bytes",
            "source_watch_changed_bytes",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_opcode_staging_writes.csv",
        tables["opcode_staging_writes"],
        [
            "line",
            "rel_s",
            "kind",
            "symbol",
            "return_symbol",
            "retval_i32",
            "pc_before",
            "pc_after",
            "pending_len_before",
            "pending_len_after",
            "opcode",
            "dst_addr",
            "dst_addr_hex",
            "byte_offset",
            "packet_offset",
            "packet_byte_index",
            "packet_id_before",
            "packet_id_after",
            "src_addr",
            "src_addr_hex",
            "src_byte_before",
            "src_reg_byte_before",
            "dst_byte_before",
            "dst_byte_after",
            "count_before",
            "in_dirinfo3_packet_slot",
            "in_dirinfo8_packet_slot",
            "is_dirinfo3_raw_byte1",
            "is_dirinfo3_raw_byte2",
            "is_dirinfo8_raw_byte2",
            "is_dirinfo8_raw_byte3",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_lc701a_transitions.csv",
        tables["lc701a_transitions"],
        [
            "call_count",
            "line_enter",
            "line_leave",
            "rel_s_enter",
            "rel_s_leave",
            "pc_before",
            "pc_after",
            "pending_len_before",
            "pending_len_after",
            "queue_flag_before",
            "queue_flag_after",
            "queue_tail_before",
            "queue_tail_after",
            "staging_packet_count_before",
            "staging_packet_count_after",
            "staging_raw_before",
            "staging_raw_after",
            "changed_bytes",
            "dirinfo3_raw_before",
            "dirinfo3_raw_after",
            "dirinfo3_byte1_after",
            "dirinfo3_byte2_after",
            "candidate_after",
        ],
    )
    write_csv(
        out_dir / f"{prefix}_lc701a_enter_sequence.csv",
        tables["lc701a_enter_sequence"],
        [
            "prev_call_count",
            "call_count",
            "line_prev_enter",
            "line_enter",
            "rel_s_prev_enter",
            "rel_s_enter",
            "pc_prev",
            "pc",
            "pending_len_prev",
            "pending_len",
            "queue_flag_prev",
            "queue_flag",
            "queue_tail_prev",
            "queue_tail",
            "staging_raw_prev",
            "staging_raw",
            "changed_bytes",
            "dirinfo3_raw_prev",
            "dirinfo3_raw",
            "dirinfo3_byte1",
            "dirinfo3_byte2",
            "candidate",
        ],
    )

    print(summary_path)


if __name__ == "__main__":
    main()
