#!/usr/bin/env python3
"""Summarize metadata-only GL texture upload captures."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


UPLOAD_KINDS = {
    "gl_tex_image_2d",
    "gl_tex_sub_image_2d",
    "gl_compressed_tex_image_2d",
    "gl_compressed_tex_sub_image_2d",
    "gl_egl_image_target_texture_2d_oes",
}

RENDER_METADATA_KINDS = UPLOAD_KINDS | {
    "gl_bind_texture",
    "gl_delete_textures",
    "gl_draw_call",
    "gl_sync_call",
    "egl_swap_buffers",
    "gl_probe_counters",
}


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
        help="event-relative window used for per-texture counts",
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


def texture_key(payload: dict[str, Any]) -> tuple[Any, ...]:
    return (
        payload.get("target_name") or payload.get("target"),
        payload.get("bound_texture"),
        payload.get("width"),
        payload.get("height"),
        payload.get("format"),
        payload.get("type"),
        payload.get("internal_format"),
    )


def event_relative_ms(record: dict[str, Any], start_host_ms: int | None) -> int | None:
    host_unix_ms = record.get("host_unix_ms")
    if start_host_ms is not None and isinstance(host_unix_ms, (int, float)):
        return int(host_unix_ms) - start_host_ms
    return None


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


def kind_time_ranges(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("kind") or "unknown")].append(row)
    result: dict[str, dict[str, Any]] = {}
    for kind, kind_rows in sorted(grouped.items()):
        rels = [
            row.get("event_relative_ms")
            for row in kind_rows
            if isinstance(row.get("event_relative_ms"), (int, float))
        ]
        result[kind] = {
            "count": len(kind_rows),
            "first_event_relative_ms": min(rels) if rels else None,
            "last_event_relative_ms": max(rels) if rels else None,
        }
    return result


def summarize_group(rows: list[dict[str, Any]], windows: list[tuple[str, float, float]]) -> dict[str, Any]:
    event_rel_values = [
        row["event_relative_ms"]
        for row in rows
        if isinstance(row.get("event_relative_ms"), (int, float))
    ]
    hashes = [row.get("hash_fnv1a") for row in rows if row.get("hash_fnv1a")]
    result: dict[str, Any] = {
        "count": len(rows),
        "first_event_relative_ms": min(event_rel_values) if event_rel_values else None,
        "last_event_relative_ms": max(event_rel_values) if event_rel_values else None,
        "distinct_hash_count": len(set(hashes)),
        "hashes_first_last": [hashes[0], hashes[-1]] if hashes else None,
        "has_data_count": sum(1 for row in rows if row.get("has_data")),
        "windows": {},
    }
    for name, start, end in windows:
        in_window = [
            row
            for row in rows
            if isinstance(row.get("event_relative_ms"), (int, float))
            and start <= row["event_relative_ms"] <= end
        ]
        window_hashes = [row.get("hash_fnv1a") for row in in_window if row.get("hash_fnv1a")]
        result["windows"][name] = {
            "count": len(in_window),
            "distinct_hash_count": len(set(window_hashes)),
            "hashes_first_last": [window_hashes[0], window_hashes[-1]] if window_hashes else None,
        }
    return result


def main() -> int:
    args = parse_args()
    runtime_log = Path(args.runtime_log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    windows = [parse_window(value) for value in args.window]
    start_host_ms = forced_event_start_host_ms(args.event_log)

    kind_counts: Counter[str] = Counter()
    parse_errors: list[dict[str, Any]] = []
    uploads: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    counter_rows: list[dict[str, Any]] = []

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
            if kind in RENDER_METADATA_KINDS:
                metadata_rows.append(row)
            if kind == "gl_probe_counters":
                counter_rows.append(row)
            if kind in UPLOAD_KINDS:
                uploads.append(row)

    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in uploads:
        groups[texture_key(row)].append(row)

    group_summaries = []
    for key, rows in groups.items():
        first = rows[0]
        summary = summarize_group(rows, windows)
        summary.update(
            {
                "kind": first.get("kind"),
                "target": key[0],
                "bound_texture": key[1],
                "width": key[2],
                "height": key[3],
                "format": key[4],
                "type": key[5],
                "internal_format": key[6],
            }
        )
        group_summaries.append(summary)
    group_summaries.sort(
        key=lambda item: (
            -(item.get("count") or 0),
            str(item.get("target")),
            str(item.get("bound_texture")),
            str(item.get("width")),
            str(item.get("height")),
        )
    )

    summary_doc = {
        "runtime_log": str(runtime_log),
        "event_log": args.event_log,
        "forced_event_start_host_ms": start_host_ms,
        "kind_counts": dict(kind_counts),
        "parse_errors": parse_errors,
        "metadata_event_count": len(metadata_rows),
        "metadata_kind_time_ranges": kind_time_ranges(metadata_rows),
        "metadata_window_kind_counts": window_kind_counts(metadata_rows, windows),
        "counter_first_last": {
            "first": counter_rows[0] if counter_rows else None,
            "last": counter_rows[-1] if counter_rows else None,
        },
        "upload_count": len(uploads),
        "texture_group_count": len(group_summaries),
        "texture_groups": group_summaries,
    }
    (out_dir / "gl_texture_summary.json").write_text(
        json.dumps(summary_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with (out_dir / "gl_texture_uploads.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "event_relative_ms",
            "kind",
            "target_name",
            "bound_texture",
            "width",
            "height",
            "format",
            "type",
            "internal_format",
            "hash_fnv1a",
            "has_data",
            "bytes_hashed",
            "nonzero_hashed_bytes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in uploads:
            writer.writerow({name: row.get(name) for name in fieldnames})

    with (out_dir / "gl_runtime_events.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "event_relative_ms",
            "kind",
            "draw_kind",
            "call_kind",
            "mode",
            "count",
            "index_type",
            "current_program",
            "current_framebuffer",
            "current_viewport",
            "active_texture_unit",
            "known_binding_count",
            "target_name",
            "bound_texture",
            "texture_ids_first16",
            "width",
            "height",
            "fields",
            "call_counts",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in metadata_rows:
            flat = {name: row.get(name) for name in fieldnames}
            for json_field in ("current_viewport", "texture_ids_first16", "fields", "call_counts"):
                if flat.get(json_field) is not None:
                    flat[json_field] = json.dumps(flat[json_field], ensure_ascii=False, sort_keys=True)
            writer.writerow(flat)

    print(json.dumps({"summary": str(out_dir / "gl_texture_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
