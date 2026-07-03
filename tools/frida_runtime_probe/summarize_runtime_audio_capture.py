#!/usr/bin/env python3
"""Summarize runtime audio capture JSONL into auditable CSV/JSON tables.

This parser is intentionally evidence-first.  It does not infer final delivery
audio from filenames or `ac` suffixes; it only extracts what the runtime probes
actually reported:

- GBoss event-code requests;
- DGM/resource strings observed by the runtime;
- sound-code lookup rows;
- SoundMng / CSndMng request rows;
- final OpenSL queue chunks captured by `csl_audio_queue_probe.js`.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


SOUND_CODE_CALL_KINDS = {
    "ctrl_snd_req_sound_code",
    "ctrl_snd_req_sound_code_timed",
    "ctrl_snd_req_sequence_sc",
    "ctrl_snd_req_sound_code_callback",
    "snd_proc_code_callback",
    "sound_mng_play_by_sound_cd",
    "sound_mng_play_bytes",
    "snd_req_by_sound_cd",
    "zg_snd_req_code",
    "zg_snd_req_fade_code",
    "zg_snd_req_volume_code",
    "zg_snd_req_pause_code",
    "ctrl_snd_req_now",
    "ctrl_snd_call_code_callback",
}


def first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def sound_code_text(payload: dict[str, Any]) -> Any:
    return first_present(
        payload,
        (
            "text_utf8",
            "arg0_text_utf8",
            "arg1_text_utf8",
            "arg2_text_utf8",
        ),
    )


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_number, json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc


def payload_kind(record: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    payload = record.get("message", {}).get("payload", {})
    kind = payload.get("kind") or record.get("event") or record.get("message", {}).get("type")
    return str(kind), payload


def relative_seconds(record: dict[str, Any], first_ms: int | None) -> float | None:
    if first_ms is None:
        return None
    value = record.get("host_unix_ms")
    if value is None:
        payload = record.get("message", {}).get("payload", {})
        value = payload.get("unix_ms")
    if value is None:
        return None
    return round((int(value) - int(first_ms)) / 1000.0, 3)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def summarize_runtime(path: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    counts: Counter[str] = Counter()
    first_ms: int | None = None
    event_codes: list[dict[str, Any]] = []
    dgm_strings: list[dict[str, Any]] = []
    sound_codes: list[dict[str, Any]] = []
    play_requests: list[dict[str, Any]] = []
    sound_code_calls: list[dict[str, Any]] = []
    bgm_calls: list[dict[str, Any]] = []
    sp_story_state: list[dict[str, Any]] = []
    anm_dir_data: list[dict[str, Any]] = []
    gr_dir_prm_copy: list[dict[str, Any]] = []
    rxcom_dir_flow: list[dict[str, Any]] = []
    force_calls: list[dict[str, Any]] = []

    for _, record in iter_jsonl(path):
        if first_ms is None and record.get("host_unix_ms") is not None:
            first_ms = int(record["host_unix_ms"])
        kind, payload = payload_kind(record)
        counts[kind] += 1
        t = relative_seconds(record, first_ms)

        if kind == "ctrl_snd_req_event_code":
            event_codes.append(
                {
                    "time_s": t,
                    "event_code": first_present(
                        payload,
                        (
                            "arg1_u64_hex",
                            "arg1_pointer",
                            "arg0_u64_hex",
                            "arg0_pointer",
                        ),
                    ),
                    "active_event_code": payload.get("active_event_code"),
                    "active_event_relative_ms": payload.get("active_event_relative_ms"),
                }
            )
        elif kind == "z2d_string_set":
            text = payload.get("text_utf8") or ""
            if text.startswith("[ac") or text.startswith("ac") or text == "lp":
                dgm_strings.append(
                    {
                        "time_s": t,
                        "text": text,
                        "active_event_code": payload.get("active_event_code"),
                    }
                )
        elif kind == "sound_code_lookup":
            sound_codes.append(
                {
                    "time_s": t,
                    "code_string": payload.get("text_utf8"),
                    "request_table_id": payload.get("return_u32"),
                    "active_event_code": payload.get("active_event_code"),
                    "active_event_relative_ms": payload.get("active_event_relative_ms"),
                }
            )
        elif kind == "sound_mng_play_request":
            play_requests.append(
                {
                    "time_s": t,
                    "request_id": payload.get("arg0_i32"),
                    "play_index_or_bank": payload.get("arg1_i32"),
                    "arg2_i32": payload.get("arg2_i32"),
                    "active_event_code": payload.get("active_event_code"),
                    "active_event_relative_ms": payload.get("active_event_relative_ms"),
                }
            )
        elif kind in SOUND_CODE_CALL_KINDS:
            sound_code_calls.append(
                {
                    "time_s": t,
                    "kind": kind,
                    "code_string": sound_code_text(payload),
                    "arg2_i32": payload.get("arg2_i32"),
                    "arg3_i32": payload.get("arg3_i32"),
                    "active_event_code": payload.get("active_event_code"),
                    "active_event_relative_ms": payload.get("active_event_relative_ms"),
                }
            )
        elif "bgm" in kind.lower() or kind == "direction_macro_snd_bgm_play":
            bgm_calls.append(
                {
                    "time_s": t,
                    "kind": kind,
                    "active_event_code": payload.get("active_event_code"),
                    "active_event_relative_ms": payload.get("active_event_relative_ms"),
                    "arg0_pointer": payload.get("arg0_pointer"),
                    "arg1_pointer": payload.get("arg1_pointer"),
                }
            )
        elif kind.startswith("sp_story_"):
            sp_story_state.append(
                {
                    "time_s": t,
                    "kind": kind,
                    "sp_story_this": payload.get("sp_story_this"),
                    "stage_kind_u16_at_0x318": payload.get("stage_kind_u16_at_0x318"),
                    "source_story_no_u16_at_0x31a": payload.get("source_story_no_u16_at_0x31a"),
                    "active_story_no_u16_at_0x34a": payload.get("active_story_no_u16_at_0x34a"),
                    "dir_no_u16_at_0x34c": payload.get("dir_no_u16_at_0x34c"),
                    "base_event_code_hex_at_0x358": payload.get("base_event_code_hex_at_0x358"),
                    "previous_base_event_code_hex_at_0x360": payload.get(
                        "previous_base_event_code_hex_at_0x360"
                    ),
                    "next_event_code_hex_at_0x368": payload.get("next_event_code_hex_at_0x368"),
                    "previous_next_event_code_hex_at_0x370": payload.get(
                        "previous_next_event_code_hex_at_0x370"
                    ),
                    "arg1_u16": payload.get("arg1_u16"),
                    "arg1_i32": payload.get("arg1_i32"),
                    "high_level_call_count_for_kind": payload.get("high_level_call_count_for_kind"),
                }
            )
        elif kind.startswith("anm_base_data_set_dir_"):
            anm_dir_data.append(
                {
                    "time_s": t,
                    "kind": kind,
                    "anm_base_this": payload.get("anm_base_this"),
                    "stage_kind_u16_at_0x318": payload.get("stage_kind_u16_at_0x318"),
                    "source_story_no_u16_at_0x31a": payload.get("source_story_no_u16_at_0x31a"),
                    "dir_special_flag_u8_at_0x31c": payload.get("dir_special_flag_u8_at_0x31c"),
                    "dir_extra_u16_at_0x31e": payload.get("dir_extra_u16_at_0x31e"),
                    "dir_scene_u16_at_0x322": payload.get("dir_scene_u16_at_0x322"),
                    "active_story_no_u16_at_0x34a": payload.get("active_story_no_u16_at_0x34a"),
                    "dir_no_u16_at_0x34c": payload.get("dir_no_u16_at_0x34c"),
                    "base_event_code_hex_at_0x358": payload.get("base_event_code_hex_at_0x358"),
                    "previous_base_event_code_hex_at_0x360": payload.get(
                        "previous_base_event_code_hex_at_0x360"
                    ),
                    "next_event_code_hex_at_0x368": payload.get("next_event_code_hex_at_0x368"),
                    "previous_next_event_code_hex_at_0x370": payload.get(
                        "previous_next_event_code_hex_at_0x370"
                    ),
                    "mstcom_pointer": payload.get("mstcom_pointer"),
                    "mst_stage_kind_u16_at_0x2376": payload.get("mst_stage_kind_u16_at_0x2376"),
                    "mst_source_story_no_u16_at_0x2378": payload.get(
                        "mst_source_story_no_u16_at_0x2378"
                    ),
                    "mst_extra_u16_at_0x238a": payload.get("mst_extra_u16_at_0x238a"),
                    "mst_scene_u16_at_0x23be": payload.get("mst_scene_u16_at_0x23be"),
                    "mstcom_error": payload.get("mstcom_error"),
                    "high_level_call_count_for_kind": payload.get("high_level_call_count_for_kind"),
                }
            )
        elif kind.startswith("gr_dir_prm_copy_"):
            gr_dir_prm_copy.append(
                {
                    "time_s": t,
                    "kind": kind,
                    "sdgm_pointer": payload.get("sdgm_pointer"),
                    "sdgm_rx_source_selector_u16_at_0x16e": payload.get(
                        "sdgm_rx_source_selector_u16_at_0x16e"
                    ),
                    "sdgm_rx_source_stage_u16_at_0x170": payload.get(
                        "sdgm_rx_source_stage_u16_at_0x170"
                    ),
                    "sdgm_rx_pre_selector_u16_at_0x0ee": payload.get(
                        "sdgm_rx_pre_selector_u16_at_0x0ee"
                    ),
                    "sdgm_rx_pre_stage_u16_at_0x0ec": payload.get(
                        "sdgm_rx_pre_stage_u16_at_0x0ec"
                    ),
                    "sdgm_rx_copy_stage_u16_at_0x318": payload.get(
                        "sdgm_rx_copy_stage_u16_at_0x318"
                    ),
                    "sdgm_rx_copy_selector_u16_at_0x31a": payload.get(
                        "sdgm_rx_copy_selector_u16_at_0x31a"
                    ),
                    "sdgm_dir_slot_u16_at_0x782": payload.get("sdgm_dir_slot_u16_at_0x782"),
                    "sdgm_dir_slot_u16_at_0x784": payload.get("sdgm_dir_slot_u16_at_0x784"),
                    "sdgm_dir_slot_u16_at_0x786": payload.get("sdgm_dir_slot_u16_at_0x786"),
                    "sdgm_source_story_no_u16_at_0x788": payload.get(
                        "sdgm_source_story_no_u16_at_0x788"
                    ),
                    "sdgm_dir_slot_u16_at_0x78a": payload.get("sdgm_dir_slot_u16_at_0x78a"),
                    "sdgm_dir_slot_u16_at_0x78c": payload.get("sdgm_dir_slot_u16_at_0x78c"),
                    "sdgm_dir_slot_u16_at_0x78e": payload.get("sdgm_dir_slot_u16_at_0x78e"),
                    "sdgm_dir_slot_u16_at_0x790": payload.get("sdgm_dir_slot_u16_at_0x790"),
                    "sdgm_dir_slot_u16_at_0x792": payload.get("sdgm_dir_slot_u16_at_0x792"),
                    "sdgm_dir_slot_u16_at_0x794": payload.get("sdgm_dir_slot_u16_at_0x794"),
                    "sdgm_dir_slot_u16_at_0x796": payload.get("sdgm_dir_slot_u16_at_0x796"),
                    "sdgm_dir_slot_u16_at_0x798": payload.get("sdgm_dir_slot_u16_at_0x798"),
                    "sdgm_dir_slot_u16_at_0x79a": payload.get("sdgm_dir_slot_u16_at_0x79a"),
                    "sdgm_error": payload.get("sdgm_error"),
                    "mstcom_pointer": payload.get("mstcom_pointer"),
                    "mst_stage_kind_u16_at_0x2376": payload.get("mst_stage_kind_u16_at_0x2376"),
                    "mst_source_story_no_u16_at_0x2378": payload.get(
                        "mst_source_story_no_u16_at_0x2378"
                    ),
                    "mst_extra_u16_at_0x238a": payload.get("mst_extra_u16_at_0x238a"),
                    "mst_scene_u16_at_0x23be": payload.get("mst_scene_u16_at_0x23be"),
                    "mstcom_error": payload.get("mstcom_error"),
                    "retval_i32": payload.get("retval_i32"),
                    "high_level_call_count_for_kind": payload.get("high_level_call_count_for_kind"),
                }
            )
        elif (
            kind.startswith("rxcom_dirinfo8_")
            or kind.startswith("rxcom_pre_mdl_")
            or kind.startswith("lot_dir_pre_mdl_")
        ):
            rxcom_dir_flow.append(
                {
                    "time_s": t,
                    "kind": kind,
                    "symbol": payload.get("symbol"),
                    "address": payload.get("address"),
                    "arg0_pointer": payload.get("arg0_pointer"),
                    "rxcom_payload_pointer": payload.get("rxcom_payload_pointer"),
                    "rxcom_payload_u8_at_0": payload.get("rxcom_payload_u8_at_0"),
                    "rxcom_payload_u8_at_1": payload.get("rxcom_payload_u8_at_1"),
                    "rxcom_payload_u8_at_2": payload.get("rxcom_payload_u8_at_2"),
                    "rxcom_payload_u8_at_3": payload.get("rxcom_payload_u8_at_3"),
                    "rxcom_payload_u8_at_4": payload.get("rxcom_payload_u8_at_4"),
                    "rxcom_payload_u8_at_5": payload.get("rxcom_payload_u8_at_5"),
                    "rxcom_payload_u8_at_6": payload.get("rxcom_payload_u8_at_6"),
                    "rxcom_payload_u8_at_7": payload.get("rxcom_payload_u8_at_7"),
                    "rxcom_dirinfo8_stage_from_payload_u8_at_4": payload.get(
                        "rxcom_dirinfo8_stage_from_payload_u8_at_4"
                    ),
                    "rxcom_dirinfo8_selector_from_payload_u8_at_5": payload.get(
                        "rxcom_dirinfo8_selector_from_payload_u8_at_5"
                    ),
                    "sdgm_pointer": payload.get("sdgm_pointer"),
                    "sdgm_rx_source_selector_u16_at_0x16e": payload.get(
                        "sdgm_rx_source_selector_u16_at_0x16e"
                    ),
                    "sdgm_rx_source_stage_u16_at_0x170": payload.get(
                        "sdgm_rx_source_stage_u16_at_0x170"
                    ),
                    "sdgm_rx_pre_selector_u16_at_0x0ee": payload.get(
                        "sdgm_rx_pre_selector_u16_at_0x0ee"
                    ),
                    "sdgm_rx_pre_stage_u16_at_0x0ec": payload.get(
                        "sdgm_rx_pre_stage_u16_at_0x0ec"
                    ),
                    "sdgm_rx_copy_stage_u16_at_0x318": payload.get(
                        "sdgm_rx_copy_stage_u16_at_0x318"
                    ),
                    "sdgm_rx_copy_selector_u16_at_0x31a": payload.get(
                        "sdgm_rx_copy_selector_u16_at_0x31a"
                    ),
                    "sdgm_dir_slot_u16_at_0x786": payload.get("sdgm_dir_slot_u16_at_0x786"),
                    "sdgm_source_story_no_u16_at_0x788": payload.get(
                        "sdgm_source_story_no_u16_at_0x788"
                    ),
                    "sdgm_error": payload.get("sdgm_error"),
                    "retval_i32": payload.get("retval_i32"),
                    "high_level_call_count_for_kind": payload.get("high_level_call_count_for_kind"),
                }
            )
        elif kind.startswith("force_"):
            force_calls.append(
                {
                    "time_s": t,
                    "kind": kind,
                    "arg0_u16": payload.get("arg0_u16"),
                    "arg0_i32": payload.get("arg0_i32"),
                    "arg1_u16": payload.get("arg1_u16"),
                    "arg1_i32": payload.get("arg1_i32"),
                    "retval_i32": payload.get("retval_i32"),
                    "active_event_code": payload.get("active_event_code"),
                    "active_event_relative_ms": payload.get("active_event_relative_ms"),
                    "high_level_call_count_for_kind": payload.get("high_level_call_count_for_kind"),
                }
            )

    summary = {
        "source": str(path),
        "counts": dict(counts),
        "event_code_count": len(event_codes),
        "dgm_string_count": len(dgm_strings),
        "sound_code_lookup_count": len(sound_codes),
        "sound_mng_play_request_count": len(play_requests),
        "sound_code_call_count": len(sound_code_calls),
        "bgm_call_count": len(bgm_calls),
        "sp_story_state_count": len(sp_story_state),
        "anm_dir_data_count": len(anm_dir_data),
        "gr_dir_prm_copy_count": len(gr_dir_prm_copy),
        "rxcom_dir_flow_count": len(rxcom_dir_flow),
        "force_call_count": len(force_calls),
        "unique_event_codes": sorted({str(row["event_code"]) for row in event_codes if row.get("event_code")}),
        "unique_sound_codes": sorted({str(row["code_string"]) for row in sound_codes if row.get("code_string")}),
        "unique_sp_story_base_event_codes": sorted(
            {
                str(row["base_event_code_hex_at_0x358"])
                for row in sp_story_state
                if row.get("base_event_code_hex_at_0x358")
            }
        ),
        "unique_sp_story_next_event_codes": sorted(
            {
                str(row["next_event_code_hex_at_0x368"])
                for row in sp_story_state
                if row.get("next_event_code_hex_at_0x368")
            }
        ),
        "unique_anm_dir_source_story_numbers": sorted(
            {
                str(row["source_story_no_u16_at_0x31a"])
                for row in anm_dir_data
                if row.get("source_story_no_u16_at_0x31a") is not None
            }
        ),
        "unique_mst_source_story_numbers": sorted(
            {
                str(row["mst_source_story_no_u16_at_0x2378"])
                for row in anm_dir_data
                if row.get("mst_source_story_no_u16_at_0x2378") is not None
            }
        ),
        "unique_gr_copy_sdgm_source_story_numbers": sorted(
            {
                str(row["sdgm_source_story_no_u16_at_0x788"])
                for row in gr_dir_prm_copy
                if row.get("sdgm_source_story_no_u16_at_0x788") is not None
            }
        ),
        "unique_gr_copy_mst_source_story_numbers": sorted(
            {
                str(row["mst_source_story_no_u16_at_0x2378"])
                for row in gr_dir_prm_copy
                if row.get("mst_source_story_no_u16_at_0x2378") is not None
            }
        ),
        "unique_rxcom_source_stage_numbers": sorted(
            {
                str(row["sdgm_rx_source_stage_u16_at_0x170"])
                for row in rxcom_dir_flow
                if row.get("sdgm_rx_source_stage_u16_at_0x170") is not None
            }
        ),
        "unique_rxcom_source_selector_numbers": sorted(
            {
                str(row["sdgm_rx_source_selector_u16_at_0x16e"])
                for row in rxcom_dir_flow
                if row.get("sdgm_rx_source_selector_u16_at_0x16e") is not None
            }
        ),
    }
    tables = {
        "runtime_event_codes": event_codes,
        "runtime_dgm_strings": dgm_strings,
        "runtime_sound_codes": sound_codes,
        "runtime_play_requests": play_requests,
        "runtime_sound_code_calls": sound_code_calls,
        "runtime_bgm_calls": bgm_calls,
        "runtime_sp_story_state": sp_story_state,
        "runtime_anm_dir_data": anm_dir_data,
        "runtime_gr_dir_prm_copy": gr_dir_prm_copy,
        "runtime_rxcom_dir_flow": rxcom_dir_flow,
        "runtime_force_calls": force_calls,
    }
    return summary, tables


def summarize_csl(path: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    counts: Counter[str] = Counter()
    first_ms: int | None = None
    requests: list[dict[str, Any]] = []
    play_starts: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []

    for _, record in iter_jsonl(path):
        if first_ms is None and record.get("host_unix_ms") is not None:
            first_ms = int(record["host_unix_ms"])
        kind, payload = payload_kind(record)
        counts[kind] += 1
        t = relative_seconds(record, first_ms)

        if kind == "csnd_mng_snd_req_enter":
            requests.append(
                {
                    "time_s": t,
                    "request_id": payload.get("request_id_i32"),
                    "arg2_i32": payload.get("arg2_i32"),
                    "thread_id": payload.get("thread_id"),
                }
            )
        elif kind == "csl_mng_play_start_enter":
            sound = payload.get("sound") or {}
            play_starts.append(
                {
                    "time_s": t,
                    "play_index": payload.get("play_index_i32"),
                    "sound_id_u16_at_0x2": sound.get("sound_id_u16_at_0x2"),
                    "sound_data": sound.get("sound_data"),
                    "thread_id": payload.get("thread_id"),
                }
            )
        elif kind == "queue_enqueue_chunk":
            chunks.append(
                {
                    "time_s": t,
                    "chunk_index": payload.get("chunk_index"),
                    "sound_id_u16_at_0x2": payload.get("sound_id_u16_at_0x2"),
                    "buffer_bytes": payload.get("buffer_bytes"),
                    "play_start_index": payload.get("play_start_index_i32"),
                    "request_id": payload.get("request_id_i32"),
                    "queue_object": payload.get("queue_object"),
                    "dumped": payload.get("dumped"),
                }
            )
        elif kind == "queue_enqueue_metadata":
            metadata.append(
                {
                    "time_s": t,
                    "sound_id_u16_at_0x2": payload.get("sound_id_u16_at_0x2"),
                    "buffer_bytes": payload.get("buffer_bytes"),
                    "play_start_index": payload.get("play_start_index_i32"),
                    "request_id": payload.get("request_id_i32"),
                    "queue_object": payload.get("queue_object"),
                    "dumped": payload.get("dumped"),
                    "dumped_bytes_so_far": payload.get("dumped_bytes_so_far"),
                }
            )

    total_chunk_bytes = sum(int(row.get("buffer_bytes") or 0) for row in chunks)
    largest_chunk = max((int(row.get("buffer_bytes") or 0) for row in chunks), default=0)
    summary = {
        "source": str(path),
        "counts": dict(counts),
        "request_count": len(requests),
        "play_start_count": len(play_starts),
        "queue_chunk_count": len(chunks),
        "queue_metadata_count": len(metadata),
        "total_dumped_chunk_bytes": total_chunk_bytes,
        "largest_dumped_chunk_bytes": largest_chunk,
        "observed_sound_ids": sorted(
            {
                int(row["sound_id_u16_at_0x2"])
                for row in chunks
                if row.get("sound_id_u16_at_0x2") is not None
            }
        ),
        "metadata_sound_ids": sorted(
            {
                int(row["sound_id_u16_at_0x2"])
                for row in metadata
                if row.get("sound_id_u16_at_0x2") is not None
            }
        ),
    }
    tables = {
        "csl_requests": requests,
        "csl_play_starts": play_starts,
        "csl_queue_chunks": chunks,
        "csl_queue_metadata": metadata,
    }
    return summary, tables


def csl_summary_has_rows(summary: dict[str, Any]) -> bool:
    return any(
        int(summary.get(key) or 0) > 0
        for key in (
            "request_count",
            "play_start_count",
            "queue_chunk_count",
            "queue_metadata_count",
        )
    )


def write_csl_outputs(out_dir: Path, csl_tables: dict[str, list[dict[str, Any]]]) -> None:
    write_csv(
        out_dir / "csl_requests.csv",
        csl_tables["csl_requests"],
        ["time_s", "request_id", "arg2_i32", "thread_id"],
    )
    write_csv(
        out_dir / "csl_play_starts.csv",
        csl_tables["csl_play_starts"],
        ["time_s", "play_index", "sound_id_u16_at_0x2", "sound_data", "thread_id"],
    )
    write_csv(
        out_dir / "csl_queue_chunks.csv",
        csl_tables["csl_queue_chunks"],
        [
            "time_s",
            "chunk_index",
            "sound_id_u16_at_0x2",
            "buffer_bytes",
            "play_start_index",
            "request_id",
            "queue_object",
            "dumped",
        ],
    )
    write_csv(
        out_dir / "csl_queue_metadata.csv",
        csl_tables["csl_queue_metadata"],
        [
            "time_s",
            "sound_id_u16_at_0x2",
            "buffer_bytes",
            "play_start_index",
            "request_id",
            "queue_object",
            "dumped",
            "dumped_bytes_so_far",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-jsonl", type=Path)
    parser.add_argument("--csl-jsonl", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}

    if args.runtime_jsonl:
        runtime_summary, runtime_tables = summarize_runtime(args.runtime_jsonl)
        summary["runtime"] = runtime_summary
        write_csv(
            args.out_dir / "runtime_event_codes.csv",
            runtime_tables["runtime_event_codes"],
            ["time_s", "event_code", "active_event_code", "active_event_relative_ms"],
        )
        write_csv(
            args.out_dir / "runtime_dgm_strings.csv",
            runtime_tables["runtime_dgm_strings"],
            ["time_s", "text", "active_event_code"],
        )
        write_csv(
            args.out_dir / "runtime_sound_codes.csv",
            runtime_tables["runtime_sound_codes"],
            [
                "time_s",
                "code_string",
                "request_table_id",
                "active_event_code",
                "active_event_relative_ms",
            ],
        )
        write_csv(
            args.out_dir / "runtime_play_requests.csv",
            runtime_tables["runtime_play_requests"],
            [
                "time_s",
                "request_id",
                "play_index_or_bank",
                "arg2_i32",
                "active_event_code",
                "active_event_relative_ms",
            ],
        )
        write_csv(
            args.out_dir / "runtime_sound_code_calls.csv",
            runtime_tables["runtime_sound_code_calls"],
            [
                "time_s",
                "kind",
                "code_string",
                "arg2_i32",
                "arg3_i32",
                "active_event_code",
                "active_event_relative_ms",
            ],
        )
        write_csv(
            args.out_dir / "runtime_bgm_calls.csv",
            runtime_tables["runtime_bgm_calls"],
            [
                "time_s",
                "kind",
                "active_event_code",
                "active_event_relative_ms",
                "arg0_pointer",
                "arg1_pointer",
            ],
        )
        write_csv(
            args.out_dir / "runtime_sp_story_state.csv",
            runtime_tables["runtime_sp_story_state"],
            [
                "time_s",
                "kind",
                "sp_story_this",
                "stage_kind_u16_at_0x318",
                "source_story_no_u16_at_0x31a",
                "active_story_no_u16_at_0x34a",
                "dir_no_u16_at_0x34c",
                "base_event_code_hex_at_0x358",
                "previous_base_event_code_hex_at_0x360",
                "next_event_code_hex_at_0x368",
                "previous_next_event_code_hex_at_0x370",
                "arg1_u16",
                "arg1_i32",
                "high_level_call_count_for_kind",
            ],
        )
        write_csv(
            args.out_dir / "runtime_anm_dir_data.csv",
            runtime_tables["runtime_anm_dir_data"],
            [
                "time_s",
                "kind",
                "anm_base_this",
                "stage_kind_u16_at_0x318",
                "source_story_no_u16_at_0x31a",
                "dir_special_flag_u8_at_0x31c",
                "dir_extra_u16_at_0x31e",
                "dir_scene_u16_at_0x322",
                "active_story_no_u16_at_0x34a",
                "dir_no_u16_at_0x34c",
                "base_event_code_hex_at_0x358",
                "previous_base_event_code_hex_at_0x360",
                "next_event_code_hex_at_0x368",
                "previous_next_event_code_hex_at_0x370",
                "mstcom_pointer",
                "mst_stage_kind_u16_at_0x2376",
                "mst_source_story_no_u16_at_0x2378",
                "mst_extra_u16_at_0x238a",
                "mst_scene_u16_at_0x23be",
                "mstcom_error",
                "high_level_call_count_for_kind",
            ],
        )
        write_csv(
            args.out_dir / "runtime_gr_dir_prm_copy.csv",
            runtime_tables["runtime_gr_dir_prm_copy"],
            [
                "time_s",
                "kind",
                "sdgm_pointer",
                "sdgm_rx_source_selector_u16_at_0x16e",
                "sdgm_rx_source_stage_u16_at_0x170",
                "sdgm_rx_pre_selector_u16_at_0x0ee",
                "sdgm_rx_pre_stage_u16_at_0x0ec",
                "sdgm_rx_copy_stage_u16_at_0x318",
                "sdgm_rx_copy_selector_u16_at_0x31a",
                "sdgm_dir_slot_u16_at_0x782",
                "sdgm_dir_slot_u16_at_0x784",
                "sdgm_dir_slot_u16_at_0x786",
                "sdgm_source_story_no_u16_at_0x788",
                "sdgm_dir_slot_u16_at_0x78a",
                "sdgm_dir_slot_u16_at_0x78c",
                "sdgm_dir_slot_u16_at_0x78e",
                "sdgm_dir_slot_u16_at_0x790",
                "sdgm_dir_slot_u16_at_0x792",
                "sdgm_dir_slot_u16_at_0x794",
                "sdgm_dir_slot_u16_at_0x796",
                "sdgm_dir_slot_u16_at_0x798",
                "sdgm_dir_slot_u16_at_0x79a",
                "sdgm_error",
                "mstcom_pointer",
                "mst_stage_kind_u16_at_0x2376",
                "mst_source_story_no_u16_at_0x2378",
                "mst_extra_u16_at_0x238a",
                "mst_scene_u16_at_0x23be",
                "mstcom_error",
                "retval_i32",
                "high_level_call_count_for_kind",
            ],
        )
        write_csv(
            args.out_dir / "runtime_rxcom_dir_flow.csv",
            runtime_tables["runtime_rxcom_dir_flow"],
            [
                "time_s",
                "kind",
                "symbol",
                "address",
                "arg0_pointer",
                "rxcom_payload_pointer",
                "rxcom_payload_u8_at_0",
                "rxcom_payload_u8_at_1",
                "rxcom_payload_u8_at_2",
                "rxcom_payload_u8_at_3",
                "rxcom_payload_u8_at_4",
                "rxcom_payload_u8_at_5",
                "rxcom_payload_u8_at_6",
                "rxcom_payload_u8_at_7",
                "rxcom_dirinfo8_stage_from_payload_u8_at_4",
                "rxcom_dirinfo8_selector_from_payload_u8_at_5",
                "sdgm_pointer",
                "sdgm_rx_source_selector_u16_at_0x16e",
                "sdgm_rx_source_stage_u16_at_0x170",
                "sdgm_rx_pre_selector_u16_at_0x0ee",
                "sdgm_rx_pre_stage_u16_at_0x0ec",
                "sdgm_rx_copy_stage_u16_at_0x318",
                "sdgm_rx_copy_selector_u16_at_0x31a",
                "sdgm_dir_slot_u16_at_0x786",
                "sdgm_source_story_no_u16_at_0x788",
                "sdgm_error",
                "retval_i32",
                "high_level_call_count_for_kind",
            ],
        )
        write_csv(
            args.out_dir / "runtime_force_calls.csv",
            runtime_tables["runtime_force_calls"],
            [
                "time_s",
                "kind",
                "arg0_u16",
                "arg0_i32",
                "arg1_u16",
                "arg1_i32",
                "retval_i32",
                "active_event_code",
                "active_event_relative_ms",
                "high_level_call_count_for_kind",
            ],
        )
        embedded_csl_summary, embedded_csl_tables = summarize_csl(args.runtime_jsonl)
        if csl_summary_has_rows(embedded_csl_summary):
            summary["runtime_embedded_csl"] = embedded_csl_summary
            write_csl_outputs(args.out_dir, embedded_csl_tables)

    if args.csl_jsonl:
        csl_summary, csl_tables = summarize_csl(args.csl_jsonl)
        summary["csl"] = csl_summary
        write_csl_outputs(args.out_dir, csl_tables)

    with (args.out_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
