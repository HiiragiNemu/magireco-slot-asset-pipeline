#!/usr/bin/env python3
"""Build an evidence-only runtime manifest skeleton from capture summary tables.

This tool is deliberately not a production-manifest builder.  It joins runtime
capture facts with static audit tables so that the next production step can be
automated without falling back to visual family classification.

Inputs are the CSV/JSON files emitted by `summarize_runtime_audio_capture.py`
plus the repository/asset `asset_manifests` directory.  Outputs are normalized
CSV tables and one JSON skeleton with explicit `evidence_only_not_render_ready`
status.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


def index_first(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if value and value not in result:
            result[value] = row
    return result


def normalize_int_string(value: str | int | None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return str(int(text, 0))
    except ValueError:
        return text


def event_code_to_key(code: str | None) -> str:
    if not code:
        return ""
    text = str(code).strip()
    if not text:
        return ""
    try:
        value = int(text, 0)
    except ValueError:
        return ""
    try:
        raw = value.to_bytes(8, "little", signed=False)
    except OverflowError:
        return ""
    return raw.decode("ascii", errors="replace")


def enrich_event(
    row: dict[str, str],
    event_by_key: dict[str, dict[str, str]],
    sequence_index: int,
) -> dict[str, Any]:
    code = row.get("event_code", "")
    event_key = event_code_to_key(code)
    static = event_by_key.get(event_key, {})
    return {
        "sequence_index": sequence_index,
        "time_s": row.get("time_s", ""),
        "event_code": code,
        "event_key": event_key,
        "event_index": static.get("event_index", ""),
        "root": static.get("root", ""),
        "primary_animation": static.get("primary_animation", ""),
        "main_animations": static.get("main_animations", ""),
        "overlays": static.get("overlays", ""),
        "sound_count": static.get("sound_count", ""),
        "sound_request_ids": static.get("sound_request_ids", ""),
        "sound_codes": static.get("sound_codes", ""),
        "audio_timeline_duration_ms": static.get("audio_timeline_duration_ms", ""),
        "subtitle_texts": static.get("subtitle_texts", ""),
        "video_default_mp4": static.get("video_default_mp4", ""),
        "video_mapping": static.get("video_mapping", ""),
        "mapping_status": "mapped_static_event" if static else "unmapped_event_code",
    }


def active_event_context(
    active_event_code: str,
    event_by_code: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not active_event_code:
        return {}
    return event_by_code.get(active_event_code, {})


def enrich_sound_code(
    row: dict[str, str],
    request_by_id: dict[str, dict[str, str]],
    request_by_code_name: dict[str, dict[str, str]],
    event_by_code: dict[str, dict[str, Any]],
    sequence_index: int,
) -> dict[str, Any]:
    code_string = row.get("code_string", "")
    request_table_id = normalize_int_string(row.get("request_table_id"))
    static_request = request_by_id.get(request_table_id) or request_by_code_name.get(code_string, {})
    context = active_event_context(row.get("active_event_code", ""), event_by_code)
    return {
        "sequence_index": sequence_index,
        "time_s": row.get("time_s", ""),
        "code_string": code_string,
        "request_table_id": request_table_id,
        "static_request_id": static_request.get("request_id", ""),
        "static_code_name": static_request.get("code_name", ""),
        "first_smz_media": static_request.get("first_smz_media", ""),
        "reqdata_count": static_request.get("reqdata_count", ""),
        "active_event_code": row.get("active_event_code", ""),
        "active_event_key": context.get("event_key", ""),
        "active_root": context.get("root", ""),
        "active_primary_animation": context.get("primary_animation", ""),
        "active_event_relative_ms": row.get("active_event_relative_ms", ""),
        "mapping_status": "mapped_static_request" if static_request else "unmapped_sound_code",
    }


def enrich_play_request(
    row: dict[str, str],
    sound_by_resource: dict[str, dict[str, str]],
    request_by_id: dict[str, dict[str, str]],
    event_by_code: dict[str, dict[str, Any]],
    sequence_index: int,
) -> dict[str, Any]:
    request_id = normalize_int_string(row.get("request_id"))
    sound_record = sound_by_resource.get(request_id, {})
    request_record = request_by_id.get(request_id, {})
    context = active_event_context(row.get("active_event_code", ""), event_by_code)
    return {
        "sequence_index": sequence_index,
        "time_s": row.get("time_s", ""),
        "request_id": request_id,
        "play_index_or_bank": row.get("play_index_or_bank", ""),
        "arg2_i32": row.get("arg2_i32", ""),
        "sound_resource_id": sound_record.get("sound_resource_id", ""),
        "ogg_chunk_index": sound_record.get("ogg_chunk_index", ""),
        "sound_bank": sound_record.get("sound_bank", ""),
        "suggested_name": sound_record.get("suggested_name", ""),
        "static_request_code_name": request_record.get("code_name", ""),
        "static_request_first_smz_media": request_record.get("first_smz_media", ""),
        "active_event_code": row.get("active_event_code", ""),
        "active_event_key": context.get("event_key", ""),
        "active_root": context.get("root", ""),
        "active_primary_animation": context.get("primary_animation", ""),
        "active_event_relative_ms": row.get("active_event_relative_ms", ""),
        "mapping_status": "mapped_sound_resource" if sound_record else "unmapped_play_request",
    }


def enrich_queue_row(
    row: dict[str, str],
    sound_by_ogg_chunk: dict[str, dict[str, str]],
    is_metadata: bool,
) -> dict[str, Any]:
    sound_id = normalize_int_string(row.get("sound_id_u16_at_0x2"))
    sound_record = sound_by_ogg_chunk.get(sound_id, {})
    return {
        "time_s": row.get("time_s", ""),
        "chunk_index": row.get("chunk_index", ""),
        "is_metadata_only": "yes" if is_metadata else "no",
        "sound_id_u16_at_0x2": sound_id,
        "buffer_bytes": row.get("buffer_bytes", ""),
        "play_start_index": row.get("play_start_index", ""),
        "request_id": normalize_int_string(row.get("request_id")),
        "queue_object": row.get("queue_object", ""),
        "mapped_sound_resource_id": sound_record.get("sound_resource_id", ""),
        "mapped_ogg_chunk_index": sound_record.get("ogg_chunk_index", ""),
        "mapped_sound_bank": sound_record.get("sound_bank", ""),
        "mapped_suggested_name": sound_record.get("suggested_name", ""),
        "mapping_status": "mapped_ogg_chunk" if sound_record else "unmapped_queue_sound_id",
    }


def build_static_event_sound_rows(
    event_sequence: list[dict[str, Any]],
    sounds_by_event_key: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in event_sequence:
        event_key = str(event.get("event_key", ""))
        for sound in sounds_by_event_key.get(event_key, []):
            key = (event_key, sound.get("sound_order", ""), sound.get("request_id", ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "event_key": event_key,
                    "event_index": sound.get("event_index", ""),
                    "root": sound.get("root", ""),
                    "primary_animation": sound.get("primary_animation", ""),
                    "sound_order": sound.get("sound_order", ""),
                    "request_id": sound.get("request_id", ""),
                    "sound_code": sound.get("sound_code", ""),
                    "code_name": sound.get("code_name", ""),
                    "label": sound.get("label", ""),
                    "speaker_hint": sound.get("speaker_hint", ""),
                    "subtitle_text": sound.get("subtitle_text", ""),
                    "duration_ms": sound.get("duration_ms", ""),
                    "smz_media": sound.get("smz_media", ""),
                    "smz_chunk_index": sound.get("smz_chunk_index", ""),
                    "ogg_name": sound.get("ogg_name", ""),
                    "ogg_duration_sec": sound.get("ogg_duration_sec", ""),
                    "ogg_duration_match": sound.get("ogg_duration_match", ""),
                }
            )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-dir", required=True, type=Path)
    parser.add_argument("--asset-manifests", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_dir = args.summary_dir.resolve()
    asset_manifests = args.asset_manifests.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runtime_event_codes = read_csv(summary_dir / "runtime_event_codes.csv")
    runtime_dgm_strings = read_csv(summary_dir / "runtime_dgm_strings.csv")
    runtime_sound_codes = read_csv(summary_dir / "runtime_sound_codes.csv")
    runtime_play_requests = read_csv(summary_dir / "runtime_play_requests.csv")
    runtime_bgm_calls = read_csv(summary_dir / "runtime_bgm_calls.csv")
    csl_chunks = read_csv(summary_dir / "csl_queue_chunks.csv")
    csl_metadata = read_csv(summary_dir / "csl_queue_metadata.csv")
    capture_summary = load_json(summary_dir / "summary.json")

    event_rows = read_csv(asset_manifests / "event_timeline_events.csv")
    event_sound_rows = read_csv(asset_manifests / "event_timeline_sounds.csv")
    request_rows = read_csv(asset_manifests / "sound_request_struct_requests.csv")
    sound_rows = read_csv(asset_manifests / "sound_id_records.csv")

    event_by_key = index_first(event_rows, "event_key")
    request_by_id = {
        normalize_int_string(row.get("request_id")): row
        for row in request_rows
        if normalize_int_string(row.get("request_id"))
    }
    request_by_code_name = index_first(request_rows, "code_name")
    sound_by_resource = {
        normalize_int_string(row.get("sound_resource_id")): row
        for row in sound_rows
        if normalize_int_string(row.get("sound_resource_id"))
    }
    sound_by_ogg_chunk = {
        normalize_int_string(row.get("ogg_chunk_index")): row
        for row in sound_rows
        if normalize_int_string(row.get("ogg_chunk_index"))
    }
    sounds_by_event_key: dict[str, list[dict[str, str]]] = {}
    for row in event_sound_rows:
        sounds_by_event_key.setdefault(row.get("event_key", ""), []).append(row)

    event_sequence = [
        enrich_event(row, event_by_key, index)
        for index, row in enumerate(runtime_event_codes)
    ]
    event_by_code = {
        str(row.get("event_code", "")): row
        for row in event_sequence
        if row.get("event_code")
    }

    sound_code_sequence = [
        enrich_sound_code(row, request_by_id, request_by_code_name, event_by_code, index)
        for index, row in enumerate(runtime_sound_codes)
    ]
    play_request_sequence = [
        enrich_play_request(row, sound_by_resource, request_by_id, event_by_code, index)
        for index, row in enumerate(runtime_play_requests)
    ]
    queue_sequence = [
        enrich_queue_row(row, sound_by_ogg_chunk, False)
        for row in csl_chunks
    ] + [
        enrich_queue_row(row, sound_by_ogg_chunk, True)
        for row in csl_metadata
    ]
    static_event_sounds = build_static_event_sound_rows(event_sequence, sounds_by_event_key)

    warnings: list[str] = []
    if any(row.get("mapping_status") == "unmapped_event_code" for row in event_sequence):
        warnings.append("some runtime event codes are not present in event_timeline_events.csv")
    if any(row.get("mapping_status") == "unmapped_sound_code" for row in sound_code_sequence):
        warnings.append("some runtime sound-code lookups are not present in sound_request_struct_requests.csv")
    if any(row.get("mapping_status") == "unmapped_play_request" for row in play_request_sequence):
        warnings.append("some SoundMng play requests are not direct sound_id.dat resource ids")
    if any(row.get("mapping_status") == "unmapped_queue_sound_id" for row in queue_sequence):
        warnings.append("some OpenSL queue sound ids are not present as sound_id.dat ogg_chunk_index values")
    if csl_metadata:
        warnings.append("capture contains metadata-only queue chunks; recapture with larger per-chunk cap before delivery")

    skeleton = {
        "schema": "magireco_runtime_evidence_skeleton.v1",
        "delivery_status": "evidence_only_not_render_ready",
        "source_summary_dir": str(summary_dir),
        "asset_manifests": str(asset_manifests),
        "counts": {
            "runtime_event_codes": len(event_sequence),
            "runtime_dgm_strings": len(runtime_dgm_strings),
            "runtime_sound_codes": len(sound_code_sequence),
            "runtime_play_requests": len(play_request_sequence),
            "runtime_bgm_calls": len(runtime_bgm_calls),
            "csl_queue_rows": len(queue_sequence),
            "static_event_sounds": len(static_event_sounds),
        },
        "warnings": warnings,
        "capture_summary": capture_summary,
        "event_sequence": event_sequence,
        "runtime_dgm_strings": runtime_dgm_strings,
        "sound_code_sequence": sound_code_sequence,
        "play_request_sequence": play_request_sequence,
        "queue_sequence": queue_sequence,
        "static_event_sounds": static_event_sounds,
    }

    write_csv(
        out_dir / "event_sequence.csv",
        event_sequence,
        [
            "sequence_index",
            "time_s",
            "event_code",
            "event_key",
            "event_index",
            "root",
            "primary_animation",
            "main_animations",
            "overlays",
            "sound_count",
            "sound_request_ids",
            "sound_codes",
            "audio_timeline_duration_ms",
            "subtitle_texts",
            "video_default_mp4",
            "video_mapping",
            "mapping_status",
        ],
    )
    write_csv(
        out_dir / "sound_code_sequence.csv",
        sound_code_sequence,
        [
            "sequence_index",
            "time_s",
            "code_string",
            "request_table_id",
            "static_request_id",
            "static_code_name",
            "first_smz_media",
            "reqdata_count",
            "active_event_code",
            "active_event_key",
            "active_root",
            "active_primary_animation",
            "active_event_relative_ms",
            "mapping_status",
        ],
    )
    write_csv(
        out_dir / "play_request_sequence.csv",
        play_request_sequence,
        [
            "sequence_index",
            "time_s",
            "request_id",
            "play_index_or_bank",
            "arg2_i32",
            "sound_resource_id",
            "ogg_chunk_index",
            "sound_bank",
            "suggested_name",
            "static_request_code_name",
            "static_request_first_smz_media",
            "active_event_code",
            "active_event_key",
            "active_root",
            "active_primary_animation",
            "active_event_relative_ms",
            "mapping_status",
        ],
    )
    write_csv(
        out_dir / "queue_sequence.csv",
        queue_sequence,
        [
            "time_s",
            "chunk_index",
            "is_metadata_only",
            "sound_id_u16_at_0x2",
            "buffer_bytes",
            "play_start_index",
            "request_id",
            "queue_object",
            "mapped_sound_resource_id",
            "mapped_ogg_chunk_index",
            "mapped_sound_bank",
            "mapped_suggested_name",
            "mapping_status",
        ],
    )
    write_csv(
        out_dir / "static_event_sounds.csv",
        static_event_sounds,
        [
            "event_key",
            "event_index",
            "root",
            "primary_animation",
            "sound_order",
            "request_id",
            "sound_code",
            "code_name",
            "label",
            "speaker_hint",
            "subtitle_text",
            "duration_ms",
            "smz_media",
            "smz_chunk_index",
            "ogg_name",
            "ogg_duration_sec",
            "ogg_duration_match",
        ],
    )
    write_json(out_dir / "runtime_evidence_skeleton.json", skeleton)
    print(json.dumps({"out_dir": str(out_dir), "counts": skeleton["counts"], "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
