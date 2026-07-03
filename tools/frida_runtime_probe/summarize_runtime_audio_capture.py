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
    }
    tables = {
        "runtime_event_codes": event_codes,
        "runtime_dgm_strings": dgm_strings,
        "runtime_sound_codes": sound_codes,
        "runtime_play_requests": play_requests,
        "runtime_sound_code_calls": sound_code_calls,
        "runtime_bgm_calls": bgm_calls,
        "runtime_sp_story_state": sp_story_state,
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
