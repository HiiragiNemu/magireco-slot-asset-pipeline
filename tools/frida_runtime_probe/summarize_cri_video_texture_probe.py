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
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})

    print(json.dumps({"summary": str(out_dir / "cri_video_texture_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
