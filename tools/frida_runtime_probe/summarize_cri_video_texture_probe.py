#!/usr/bin/env python3
"""Summarize metadata-only CRI video texture probe captures."""

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
        help="event-relative window for per-kind/per-texture counts",
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


def window_counts(rows: list[dict[str, Any]], windows: list[tuple[str, float, float]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for name, start, end in windows:
        counts: Counter[str] = Counter()
        for row in rows:
            rel = row.get("event_relative_ms")
            if isinstance(rel, (int, float)) and start <= rel <= end:
                counts[str(row.get("kind") or "unknown")] += 1
        result[name] = dict(counts)
    return result


def summarize_texture_updates(
    rows: list[dict[str, Any]], windows: list[tuple[str, float, float]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("renderer"),
            row.get("texture_id_u32"),
            row.get("value0"),
            row.get("value1"),
            row.get("value2"),
            row.get("value3"),
        )
        grouped[key].append(row)

    summaries: list[dict[str, Any]] = []
    for key, group in grouped.items():
        hashes = [row.get("hash_fnv1a") for row in group if row.get("hash_fnv1a")]
        doc = {
            "renderer": key[0],
            "texture_id_u32": key[1],
            "value0": key[2],
            "value1": key[3],
            "value2": key[4],
            "value3": key[5],
            "distinct_hash_count": len(set(hashes)),
            "hashes_first_last": [hashes[0], hashes[-1]] if hashes else None,
            "has_data_count": sum(1 for row in group if row.get("has_data")),
            "windows": {},
        }
        doc.update(time_range(group))
        for name, start, end in windows:
            in_window = [
                row
                for row in group
                if isinstance(row.get("event_relative_ms"), (int, float))
                and start <= row["event_relative_ms"] <= end
            ]
            window_hashes = [row.get("hash_fnv1a") for row in in_window if row.get("hash_fnv1a")]
            doc["windows"][name] = {
                "count": len(in_window),
                "distinct_hash_count": len(set(window_hashes)),
                "hashes_first_last": [window_hashes[0], window_hashes[-1]] if window_hashes else None,
            }
        summaries.append(doc)
    summaries.sort(
        key=lambda item: (
            -(item.get("count") or 0),
            str(item.get("renderer")),
            str(item.get("texture_id_u32")),
        )
    )
    return summaries


def numeric_values(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values_by_offset: dict[str, dict[str, list[Any]]] = defaultdict(
        lambda: {"u32": [], "f32": [], "error": []}
    )
    for row in rows:
        numeric = row.get("texture_state_numeric")
        if not isinstance(numeric, dict):
            continue
        fields = numeric.get("fields")
        if not isinstance(fields, list):
            continue
        for field in fields:
            if not isinstance(field, dict):
                continue
            offset = str(field.get("offset") or "")
            if not offset:
                continue
            if "u32" in field:
                values_by_offset[offset]["u32"].append(field.get("u32"))
            if "f32" in field:
                values_by_offset[offset]["f32"].append(field.get("f32"))
            if "error" in field:
                values_by_offset[offset]["error"].append(field.get("error"))

    result: dict[str, dict[str, Any]] = {}
    for offset, typed_values in sorted(
        values_by_offset.items(), key=lambda item: int(item[0], 16)
    ):
        offset_doc: dict[str, Any] = {}
        for value_type in ("u32", "f32", "error"):
            values = typed_values[value_type]
            if not values:
                continue
            distinct = []
            for value in values:
                if value not in distinct:
                    distinct.append(value)
            value_doc: dict[str, Any] = {
                "count": len(values),
                "distinct_count": len(distinct),
                "first": values[0],
                "last": values[-1],
                "distinct_first8": distinct[:8],
            }
            numeric_only = [value for value in values if isinstance(value, (int, float))]
            if numeric_only:
                value_doc["min"] = min(numeric_only)
                value_doc["max"] = max(numeric_only)
            offset_doc[value_type] = value_doc
        result[offset] = offset_doc
    return result


def summarize_renderer_checks(
    rows: list[dict[str, Any]], windows: list[tuple[str, float, float]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("arg0_pointer"),
            row.get("arg1_pointer"),
            row.get("arg2_i32"),
        )
        grouped[key].append(row)

    summaries: list[dict[str, Any]] = []
    for key, group in grouped.items():
        doc: dict[str, Any] = {
            "renderer_arg0": key[0],
            "texture_state_arg1": key[1],
            "arg2_i32": key[2],
            "windows": {},
            "numeric_offsets": numeric_values(group),
        }
        doc.update(time_range(group))
        for name, start, end in windows:
            in_window = [
                row
                for row in group
                if isinstance(row.get("event_relative_ms"), (int, float))
                and start <= row["event_relative_ms"] <= end
            ]
            doc["windows"][name] = {
                "count": len(in_window),
                "numeric_offsets": numeric_values(in_window),
            }
        summaries.append(doc)
    summaries.sort(
        key=lambda item: (
            -(item.get("count") or 0),
            str(item.get("renderer_arg0")),
            str(item.get("texture_state_arg1")),
        )
    )
    return summaries


def primitive_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    primitive = row.get("primitive") if isinstance(row.get("primitive"), dict) else {}
    textures = primitive.get("textures") if isinstance(primitive.get("textures"), list) else []
    texture_sig = tuple(
        (
            item.get("index"),
            item.get("type_u32_at_base"),
            item.get("texture_object_u32_at_base_plus_0x8"),
            item.get("texture_object_u32_at_base_plus_0xc"),
            item.get("texture_object_pointer_at_base_plus_0x18"),
            item.get("filter_u32_at_base_plus_0x20"),
            item.get("address_u32_at_base_plus_0x24"),
        )
        for item in textures
        if isinstance(item, dict)
    )
    return (
        row.get("renderer_pointer"),
        row.get("texture_state_pointer"),
        row.get("primitive_pointer"),
        primitive.get("primitive_mode_u32_at_0x0"),
        primitive.get("vertex_count_u32_at_0x28"),
        primitive.get("index_count_u32_at_0x38"),
        primitive.get("texture_count_u32_at_0xb8"),
        texture_sig,
    )


def summarize_primitive_rows(
    rows: list[dict[str, Any]], windows: list[tuple[str, float, float]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[primitive_signature(row)].append(row)

    summaries: list[dict[str, Any]] = []
    for key, group in grouped.items():
        primitive = group[0].get("primitive") if isinstance(group[0].get("primitive"), dict) else {}
        doc: dict[str, Any] = {
            "renderer_pointer": key[0],
            "texture_state_pointer": key[1],
            "primitive_pointer": key[2],
            "primitive_mode_u32_at_0x0": key[3],
            "vertex_count_u32_at_0x28": key[4],
            "index_count_u32_at_0x38": key[5],
            "texture_count_u32_at_0xb8": key[6],
            "textures": primitive.get("textures") if isinstance(primitive, dict) else [],
            "windows": {},
        }
        doc.update(time_range(group))
        for name, start, end in windows:
            in_window = [
                row
                for row in group
                if isinstance(row.get("event_relative_ms"), (int, float))
                and start <= row["event_relative_ms"] <= end
            ]
            doc["windows"][name] = {"count": len(in_window)}
        summaries.append(doc)
    summaries.sort(
        key=lambda item: (
            -(item.get("count") or 0),
            str(item.get("renderer_pointer")),
            str(item.get("primitive_pointer")),
            str(item.get("texture_state_pointer")),
        )
    )
    return summaries


def main() -> int:
    args = parse_args()
    runtime_log = Path(args.runtime_log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    windows = [parse_window(value) for value in args.window]
    start_host_ms = forced_event_start_host_ms(args.event_log)

    kind_counts: Counter[str] = Counter()
    parse_errors: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    with runtime_log.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                parse_errors.append({"line": line_no, "error": str(error)})
                continue
            payload = payload_from_record(record)
            kind = payload.get("kind") or record.get("event") or record.get("type") or "unknown"
            kind_counts[str(kind)] += 1
            row = dict(payload)
            row["kind"] = kind
            row["host_unix_ms"] = record.get("host_unix_ms")
            row["event_relative_ms"] = event_relative_ms(record, start_host_ms)
            rows.append(row)

    grouped_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_by_kind[str(row.get("kind") or "unknown")].append(row)

    texture_updates = [
        row for row in rows if row.get("kind") == "cri_video_update_texture"
    ]
    renderer_checks = [
        row
        for row in rows
        if row.get("kind") == "sprite_renderer_check_bind_texture_states"
    ]
    renderer_makeup_rows = [
        row for row in rows if row.get("kind") == "sprite_renderer_makeup_textures"
    ]
    renderer_draw_call_rows = [
        row for row in rows if row.get("kind") == "sprite_renderer_draw_call"
    ]
    summary_doc = {
        "runtime_log": str(runtime_log),
        "event_log": args.event_log,
        "forced_event_start_host_ms": start_host_ms,
        "kind_counts": dict(kind_counts),
        "parse_errors": parse_errors,
        "kind_time_ranges": {
            kind: time_range(kind_rows)
            for kind, kind_rows in sorted(grouped_by_kind.items())
        },
        "window_kind_counts": window_counts(rows, windows),
        "texture_update_count": len(texture_updates),
        "texture_update_groups": summarize_texture_updates(texture_updates, windows),
        "renderer_check_count": len(renderer_checks),
        "renderer_check_groups": summarize_renderer_checks(renderer_checks, windows),
        "renderer_makeup_count": len(renderer_makeup_rows),
        "renderer_makeup_groups": summarize_primitive_rows(renderer_makeup_rows, windows),
        "renderer_draw_call_count": len(renderer_draw_call_rows),
        "renderer_draw_call_groups": summarize_primitive_rows(renderer_draw_call_rows, windows),
    }
    (out_dir / "cri_video_texture_summary.json").write_text(
        json.dumps(summary_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with (out_dir / "cri_video_texture_events.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "event_relative_ms",
            "kind",
            "receiver",
            "renderer",
            "arg0_pointer",
            "arg1_pointer",
            "arg2_i32",
            "texture_id_u32",
            "width",
            "height",
            "frame_rate",
            "value0",
            "value1",
            "value2",
            "value3",
            "value4",
            "byte_size_u32",
            "hash_fnv1a",
            "has_data",
            "bytes_hashed",
            "nonzero_hashed_bytes",
            "return_i32",
            "return_u32",
            "texture_state_numeric",
            "renderer_pointer",
            "texture_state_pointer",
            "primitive_pointer",
            "primitive",
            "texture_state_before",
            "texture_state_after",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flat = {name: row.get(name) for name in fieldnames}
            if flat.get("texture_state_numeric") is not None:
                flat["texture_state_numeric"] = json.dumps(
                    flat["texture_state_numeric"],
                    ensure_ascii=False,
                    sort_keys=True,
                )
            for json_field in ("primitive", "texture_state_before", "texture_state_after"):
                if flat.get(json_field) is not None:
                    flat[json_field] = json.dumps(
                        flat[json_field],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
            writer.writerow(flat)

    print(json.dumps({"summary": str(out_dir / "cri_video_texture_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
