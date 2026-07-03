#!/usr/bin/env python3
"""Summarize metadata-only Z2D movie-layer probe captures."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-log", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--event-log", help="optional event_scene_host JSONL for forced-event alignment")
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        metavar="NAME:START_MS:END_MS",
        help="event-relative window for per-kind counts",
    )
    return parser.parse_args()


def payload_from_record(record: dict[str, Any]) -> dict[str, Any]:
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("payload"), dict):
        return message["payload"]
    return record


def parse_window(value: str) -> tuple[str, float, float]:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid --window {value!r}; expected NAME:START_MS:END_MS")
    name, start, end = parts
    return name, float(start), float(end)


def forced_event_start_host_ms(path: str | None) -> int | None:
    if not path:
        return None
    event_log = Path(path)
    if not event_log.exists():
        return None
    with event_log.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = payload_from_record(record)
            kind = payload.get("kind") or record.get("event")
            if kind == "forced_event_context_started":
                value = record.get("host_unix_ms")
                return int(value) if isinstance(value, (int, float)) else None
    return None


def event_relative_ms(record: dict[str, Any], start_host_ms: int | None) -> int | None:
    host_unix_ms = record.get("host_unix_ms")
    if start_host_ms is not None and isinstance(host_unix_ms, (int, float)):
        return int(host_unix_ms) - start_host_ms
    return None


def time_range(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rels = [
        row.get("event_relative_ms")
        for row in rows
        if isinstance(row.get("event_relative_ms"), (int, float))
    ]
    return {
        "count": len(rows),
        "first_event_relative_ms": min(rels) if rels else None,
        "last_event_relative_ms": max(rels) if rels else None,
    }


def window_kind_counts(
    rows: list[dict[str, Any]], windows: list[tuple[str, float, float]]
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name, start, end in windows:
        counts: Counter[str] = Counter()
        for row in rows:
            rel = row.get("event_relative_ms")
            if isinstance(rel, (int, float)) and start <= rel <= end:
                counts[str(row.get("kind") or "unknown")] += 1
        result[name] = dict(counts)
    return result


def extract_cstring_text(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("text")
        return text if isinstance(text, str) else ""
    return ""


def first_texture_id(primitive: Any) -> Any:
    if not isinstance(primitive, dict):
        return None
    textures = primitive.get("textures")
    if not isinstance(textures, list) or not textures:
        return None
    first = textures[0]
    if not isinstance(first, dict):
        return None
    return first.get("texture_object_u32_at_base_plus_0x8")


def summarize_by_pointer(rows: list[dict[str, Any]], pointer_fields: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(row.get(field) for field in pointer_fields)
        if any(value in (None, "", "0x0") for value in key):
            continue
        grouped[key].append(row)
    docs: list[dict[str, Any]] = []
    for key, group in grouped.items():
        doc = {field: value for field, value in zip(pointer_fields, key)}
        doc.update(time_range(group))
        texts: Counter[str] = Counter()
        for row in group:
            for field in ("return_cstring", "path"):
                text = extract_cstring_text(row.get(field))
                if text:
                    texts[text] += 1
        if texts:
            doc["texts"] = dict(texts.most_common())
        states: Counter[str] = Counter()
        for row in group:
            for field in ("return_i32", "new_state_i32", "input_frame_i32"):
                value = row.get(field)
                if value is not None:
                    states[f"{field}={value}"] += 1
        if states:
            doc["numeric_values"] = dict(states.most_common(20))
        docs.append(doc)
    docs.sort(
        key=lambda item: (
            -(item.get("count") or 0),
            str(tuple(item.get(field) for field in pointer_fields)),
        )
    )
    return docs


def fields_by_offset(probe: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(probe, dict):
        return {}
    fields = probe.get("fields")
    if not isinstance(fields, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        offset = field.get("offset")
        if isinstance(offset, str):
            result[offset] = field
    return result


def field_value(probe: Any, offset: str, value_type: str = "u32") -> Any:
    return fields_by_offset(probe).get(offset, {}).get(value_type)


def minmax(values: list[Any]) -> dict[str, Any]:
    numeric = [value for value in values if isinstance(value, (int, float))]
    if not numeric:
        return {"count": 0, "min": None, "max": None, "first": None, "last": None, "distinct": 0}
    return {
        "count": len(numeric),
        "min": min(numeric),
        "max": max(numeric),
        "first": numeric[0],
        "last": numeric[-1],
        "distinct": len(set(numeric)),
    }


def summarize_play_movie_numeric(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pointer = row.get("play_movie_pointer")
        if isinstance(pointer, str) and pointer not in ("", "0x0"):
            grouped[pointer].append(row)
    docs: list[dict[str, Any]] = []
    offsets = {
        "state_or_flags_at_0x0": "0x0",
        "current_or_input_frame_at_0x4": "0x4",
        "texture_like_at_0x20": "0x20",
        "decode_or_frame_at_0x28": "0x28",
        "width_at_0x38": "0x38",
        "height_at_0x40": "0x40",
    }
    for pointer, group in grouped.items():
        numeric_rows = [row for row in group if isinstance(row.get("play_movie_numeric"), dict)]
        doc: dict[str, Any] = {"play_movie_pointer": pointer}
        doc.update(time_range(group))
        texts: Counter[str] = Counter()
        for row in group:
            for field in ("return_cstring", "path"):
                text = extract_cstring_text(row.get(field))
                if text:
                    texts[text] += 1
        if texts:
            doc["texts"] = dict(texts.most_common())
        for name, offset in offsets.items():
            doc[name] = minmax([field_value(row.get("play_movie_numeric"), offset) for row in numeric_rows])
        docs.append(doc)
    docs.sort(key=lambda item: (-(item.get("count") or 0), str(item.get("play_movie_pointer"))))
    return docs


def summarize_elem_movie_numeric(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pointer = row.get("elem_movie_pointer")
        if isinstance(pointer, str) and pointer not in ("", "0x0"):
            grouped[pointer].append(row)
    docs: list[dict[str, Any]] = []
    for pointer, group in grouped.items():
        doc: dict[str, Any] = {"elem_movie_pointer": pointer}
        doc.update(time_range(group))
        texts: Counter[str] = Counter()
        for row in group:
            for field in ("return_cstring", "path"):
                text = extract_cstring_text(row.get(field))
                if text:
                    texts[text] += 1
        if texts:
            doc["texts"] = dict(texts.most_common())
        for kind_name in (
            "z2d_elem_movie_get_start_time",
            "z2d_elem_movie_get_end_time",
            "z2d_elem_movie_get_decode_frame",
            "z2d_elem_movie_get_time_remap_frame",
            "z2d_elem_movie_is_draw_time",
        ):
            values = [row.get("return_i32") for row in group if row.get("kind") == kind_name]
            doc[kind_name] = minmax(values)
        doc["input_frame_i32"] = minmax(
            [row.get("input_frame_i32") for row in group if row.get("input_frame_i32") is not None]
        )
        doc["texture_like_at_0x70"] = minmax(
            [field_value(row.get("elem_movie_numeric"), "0x70") for row in group]
        )
        docs.append(doc)
    docs.sort(key=lambda item: (-(item.get("count") or 0), str(item.get("elem_movie_pointer"))))
    return docs


def summarize_renderer_draws(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        primitive = row.get("primitive")
        key = (
            row.get("renderer_pointer"),
            row.get("primitive_pointer"),
            first_texture_id(primitive),
        )
        grouped[key].append(row)
    docs: list[dict[str, Any]] = []
    for key, group in grouped.items():
        doc = {
            "renderer_pointer": key[0],
            "primitive_pointer": key[1],
            "first_texture_id": key[2],
        }
        doc.update(time_range(group))
        docs.append(doc)
    docs.sort(key=lambda item: (-(item.get("count") or 0), str(item.get("primitive_pointer"))))
    return docs


def main() -> int:
    args = parse_args()
    runtime_log = Path(args.runtime_log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    windows = [parse_window(item) for item in args.window]
    start_host_ms = forced_event_start_host_ms(args.event_log)

    rows: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    with runtime_log.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                parse_errors.append({"line": line_no, "error": str(error)})
                continue
            payload = payload_from_record(record)
            kind = payload.get("kind") or record.get("event")
            if not kind:
                continue
            row = dict(payload)
            row["kind"] = kind
            row["host_unix_ms"] = record.get("host_unix_ms")
            row["event_relative_ms"] = event_relative_ms(record, start_host_ms)
            rows.append(row)

    kind_counts = Counter(str(row.get("kind")) for row in rows)
    kind_time_ranges = {
        kind: time_range([row for row in rows if row.get("kind") == kind])
        for kind in sorted(kind_counts)
    }

    cri_rows = [row for row in rows if str(row.get("kind")).startswith("cri_")]
    z2d_rows = [row for row in rows if str(row.get("kind")).startswith("z2d_")]
    gf_rows = [row for row in rows if str(row.get("kind")).startswith("gf_cri_")]
    renderer_rows = [row for row in rows if row.get("kind") == "sprite_renderer_draw_call"]

    summary = {
        "runtime_log": str(runtime_log),
        "event_log": args.event_log,
        "forced_event_start_host_ms": start_host_ms,
        "kind_counts": dict(kind_counts),
        "kind_time_ranges": kind_time_ranges,
        "window_kind_counts": window_kind_counts(rows, windows),
        "parse_errors": parse_errors,
        "cri_set_data": [
            {
                "event_relative_ms": row.get("event_relative_ms"),
                "receiver": row.get("receiver"),
                "byte_size_u32": row.get("byte_size_u32"),
                "hash_fnv1a": row.get("hash_fnv1a"),
                "bytes_hashed": row.get("bytes_hashed"),
                "nonzero_hashed_bytes": row.get("nonzero_hashed_bytes"),
            }
            for row in cri_rows
            if row.get("kind") == "cri_set_data"
        ],
        "z2d_play_movie_groups": summarize_by_pointer(
            z2d_rows,
            ["play_movie_pointer"],
        ),
        "z2d_play_movie_numeric_groups": summarize_play_movie_numeric(z2d_rows),
        "z2d_elem_movie_numeric_groups": summarize_elem_movie_numeric(z2d_rows),
        "z2d_play_prim_groups": summarize_by_pointer(
            z2d_rows,
            ["play_prim_pointer"],
        ),
        "z2d_movie_layer_groups": summarize_by_pointer(
            z2d_rows,
            ["movie_layer_pointer"],
        ),
        "gf_cri_player_groups": summarize_by_pointer(
            gf_rows,
            ["gf_cri_player_pointer"],
        ),
        "renderer_draw_groups": summarize_renderer_draws(renderer_rows),
    }

    summary_path = out_dir / "z2d_movie_layer_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    csv_path = out_dir / "z2d_movie_layer_events.csv"
    fieldnames = [
        "event_relative_ms",
        "host_unix_ms",
        "kind",
        "symbol",
        "active_event_code",
        "active_event_relative_ms",
        "receiver",
        "byte_size_u32",
        "hash_fnv1a",
        "width",
        "height",
        "frame_rate",
        "value3",
        "return_i32",
        "return_u32",
        "return_pointer",
        "return_cstring",
        "path",
        "player_pointer",
        "hard_player_pointer",
        "play_movie_pointer",
        "play_prim_pointer",
        "movie_layer_pointer",
        "rb_info_pointer",
        "gf_cri_player_pointer",
        "gf_renderer_pointer",
        "renderer_pointer",
        "primitive_pointer",
        "primitive",
        "texture_state_numeric",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {field: row.get(field) for field in fieldnames}
            for json_field in ("return_cstring", "path", "primitive", "texture_state_numeric"):
                if flat.get(json_field) is not None:
                    flat[json_field] = json.dumps(flat[json_field], ensure_ascii=False, sort_keys=True)
            writer.writerow(flat)

    print(json.dumps({"summary": str(summary_path), "csv": str(csv_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
