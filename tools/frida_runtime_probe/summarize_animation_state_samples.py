#!/usr/bin/env python3
"""Summarize event_scene_probe animation_state_sample JSONL captures."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-log", required=True, help="event_scene_host JSONL")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        metavar="NAME:START_MS:END_MS",
        help="optional named range for field min/max summaries",
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


def pointer_of(state: dict[str, Any], key: str) -> str | None:
    value = state.get(key)
    if isinstance(value, dict):
        pointer = value.get("pointer")
        if isinstance(pointer, str):
            return pointer
    return None


def numeric_fields(state: dict[str, Any], object_key: str) -> list[dict[str, Any]]:
    probe = state.get("numeric_probe")
    if not isinstance(probe, dict):
        return []
    object_probe = probe.get(object_key)
    if not isinstance(object_probe, dict):
        return []
    fields = object_probe.get("fields")
    return fields if isinstance(fields, list) else []


def field_ranges(
    values: list[tuple[float | None, float]],
    windows: list[tuple[str, float, float]],
) -> dict[str, dict[str, float] | None]:
    result: dict[str, dict[str, float] | None] = {}
    for name, start, end in windows:
        in_window = [value for rel_ms, value in values if rel_ms is not None and start <= rel_ms <= end]
        result[name] = (
            None
            if not in_window
            else {
                "min": min(in_window),
                "max": max(in_window),
            }
        )
    return result


def summarize_fields(
    samples: list[dict[str, Any]],
    object_key: str,
    windows: list[tuple[str, float, float]],
) -> list[dict[str, Any]]:
    series: dict[tuple[str, str], list[tuple[float | None, float]]] = defaultdict(list)
    for sample in samples:
        rel_ms = sample.get("relative_ms")
        state = sample["state"]
        for item in numeric_fields(state, object_key):
            offset = item.get("offset")
            if not isinstance(offset, str):
                continue
            if "u32" in item:
                series[(offset, "u32")].append((rel_ms, float(item["u32"])))
            if "f32" in item:
                series[(offset, "f32")].append((rel_ms, float(item["f32"])))

    rows: list[dict[str, Any]] = []
    for (offset, value_type), values in series.items():
        raw_values = [value for _, value in values]
        distinct = len(set(raw_values))
        if distinct <= 1:
            continue
        inc_steps = sum(1 for (_, a), (_, b) in zip(values, values[1:]) if b >= a)
        dec_steps = sum(1 for (_, a), (_, b) in zip(values, values[1:]) if b <= a)
        rows.append(
            {
                "object": object_key,
                "offset": offset,
                "type": value_type,
                "n": len(values),
                "distinct": distinct,
                "first": raw_values[0],
                "last": raw_values[-1],
                "min": min(raw_values),
                "max": max(raw_values),
                "inc_steps": inc_steps,
                "dec_steps": dec_steps,
                "windows": field_ranges(values, windows),
            }
        )
    rows.sort(key=lambda row: (-int(row["distinct"]), str(row["object"]), str(row["offset"]), str(row["type"])))
    return rows


def main() -> int:
    args = parse_args()
    event_log = Path(args.event_log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    windows = [parse_window(value) for value in args.window]

    counts: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []

    with event_log.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                parse_errors.append({"line": line_no, "error": str(error)})
                continue
            payload = payload_from_record(record)
            kind = payload.get("kind") or record.get("event") or record.get("type") or "unknown"
            counts[str(kind)] += 1
            if kind != "animation_state_sample":
                continue
            state = payload.get("animation_state")
            if not isinstance(state, dict):
                continue
            rel_ms = payload.get("forced_event_relative_ms")
            samples.append(
                {
                    "relative_ms": float(rel_ms) if isinstance(rel_ms, (int, float)) else None,
                    "reason": payload.get("sample_reason"),
                    "state": state,
                }
            )

    selected_sources = Counter(str(sample["state"].get("selected_source")) for sample in samples)
    selected_pointers = Counter(pointer_of(sample["state"], "selected_object") or "" for sample in samples)
    frame_pointers = Counter(pointer_of(sample["state"], "frame_animation_object") or "" for sample in samples)
    last_ages = []
    for sample in samples:
        last_frame = sample["state"].get("last_animation_frame")
        if isinstance(last_frame, dict) and isinstance(last_frame.get("age_ms"), (int, float)):
            last_ages.append(float(last_frame["age_ms"]))

    summary = {
        "event_log": str(event_log),
        "sample_count": len(samples),
        "first_relative_ms": samples[0]["relative_ms"] if samples else None,
        "last_relative_ms": samples[-1]["relative_ms"] if samples else None,
        "kind_counts": dict(counts),
        "parse_errors": parse_errors,
        "selected_source_counts": dict(selected_sources),
        "selected_object_pointer_counts": dict(selected_pointers),
        "frame_object_pointer_counts": dict(frame_pointers),
        "last_frame_age_ms": None
        if not last_ages
        else {
            "min": min(last_ages),
            "max": max(last_ages),
            "avg": sum(last_ages) / len(last_ages),
        },
        "numeric_varying_fields": {
            "selected_object": summarize_fields(samples, "selected_object", windows),
            "frame_animation_object": summarize_fields(samples, "frame_animation_object", windows),
        },
    }

    (out_dir / "animation_state_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with (out_dir / "animation_state_samples.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "relative_ms",
                "reason",
                "selected_source",
                "selected_object",
                "frame_animation_object",
                "active_animation_child",
                "last_frame_age_ms",
            ],
        )
        writer.writeheader()
        for sample in samples:
            state = sample["state"]
            last_frame = state.get("last_animation_frame")
            writer.writerow(
                {
                    "relative_ms": sample["relative_ms"],
                    "reason": sample["reason"],
                    "selected_source": state.get("selected_source"),
                    "selected_object": pointer_of(state, "selected_object"),
                    "frame_animation_object": pointer_of(state, "frame_animation_object"),
                    "active_animation_child": pointer_of(state, "active_animation_child"),
                    "last_frame_age_ms": last_frame.get("age_ms") if isinstance(last_frame, dict) else None,
                }
            )

    print(json.dumps({"summary": str(out_dir / "animation_state_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
