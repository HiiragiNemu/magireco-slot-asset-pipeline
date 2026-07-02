#!/usr/bin/env python3
"""Summarize visual_tail_probe CRI receiver lifecycle and numeric samples."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-log", required=True, help="runtime_probe_host JSONL")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        metavar="NAME:START_MS:END_MS",
        help="optional named range, relative to receiver SetData time",
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


def add_event(receiver: dict[str, Any], payload: dict[str, Any]) -> None:
    event = {
        "kind": payload.get("kind"),
        "unix_ms": payload.get("unix_ms"),
        "return_i32": payload.get("return_i32"),
    }
    set_data_unix_ms = receiver.get("set_data_unix_ms")
    if isinstance(event["unix_ms"], (int, float)) and isinstance(set_data_unix_ms, (int, float)):
        event["relative_ms"] = event["unix_ms"] - set_data_unix_ms
    else:
        event["relative_ms"] = None
    receiver["events"].append(event)


def sample_fields(sample: dict[str, Any]) -> list[dict[str, Any]]:
    probe = sample.get("numeric_probe")
    if not isinstance(probe, dict):
        return []
    fields = probe.get("fields")
    return fields if isinstance(fields, list) else []


def summarize_field_series(
    values: list[tuple[float | None, float]],
    windows: list[tuple[str, float, float]],
) -> dict[str, Any]:
    raw_values = [value for _, value in values]
    result: dict[str, Any] = {
        "n": len(values),
        "distinct": len(set(raw_values)),
        "first": raw_values[0],
        "last": raw_values[-1],
        "min": min(raw_values),
        "max": max(raw_values),
        "inc_steps": sum(1 for (_, a), (_, b) in zip(values, values[1:]) if b >= a),
        "dec_steps": sum(1 for (_, a), (_, b) in zip(values, values[1:]) if b <= a),
        "windows": {},
    }
    for name, start, end in windows:
        in_window = [value for rel_ms, value in values if rel_ms is not None and start <= rel_ms <= end]
        result["windows"][name] = (
            None
            if not in_window
            else {
                "min": min(in_window),
                "max": max(in_window),
            }
        )
    return result


def summarize_receiver(receiver: dict[str, Any], windows: list[tuple[str, float, float]]) -> dict[str, Any]:
    events = receiver["events"]
    event_counts = Counter(str(event["kind"]) for event in events)
    status_counts = Counter(
        str(event.get("return_i32"))
        for event in events
        if event.get("kind") == "cri_get_status"
    )
    update_times = [
        event.get("relative_ms")
        for event in events
        if event.get("kind") == "cri_update" and isinstance(event.get("relative_ms"), (int, float))
    ]
    status_times = [
        event.get("relative_ms")
        for event in events
        if event.get("kind") == "cri_get_status" and isinstance(event.get("relative_ms"), (int, float))
    ]

    field_series: dict[tuple[str, str], list[tuple[float | None, float]]] = defaultdict(list)
    for sample in receiver["samples"]:
        rel_ms = sample.get("relative_ms")
        for item in sample_fields(sample):
            offset = item.get("offset")
            if not isinstance(offset, str):
                continue
            if "u32" in item:
                field_series[(offset, "u32")].append((rel_ms, float(item["u32"])))
            if "f32" in item:
                field_series[(offset, "f32")].append((rel_ms, float(item["f32"])))

    varying_fields = []
    for (offset, value_type), values in field_series.items():
        if len(values) < 2:
            continue
        summary = summarize_field_series(values, windows)
        if summary["distinct"] <= 1:
            continue
        summary.update({"offset": offset, "type": value_type})
        varying_fields.append(summary)
    varying_fields.sort(key=lambda row: (-int(row["distinct"]), str(row["offset"]), str(row["type"])))

    return {
        "receiver": receiver["receiver"],
        "set_data_unix_ms": receiver.get("set_data_unix_ms"),
        "byte_size_u32": receiver.get("byte_size_u32"),
        "data_fnv1a_4k": receiver.get("data_fnv1a_4k"),
        "movie_info": receiver.get("movie_info"),
        "event_counts": dict(event_counts),
        "status_return_counts": dict(status_counts),
        "first_update_relative_ms": min(update_times) if update_times else None,
        "last_update_relative_ms": max(update_times) if update_times else None,
        "first_status_relative_ms": min(status_times) if status_times else None,
        "last_status_relative_ms": max(status_times) if status_times else None,
        "sample_count": len(receiver["samples"]),
        "first_sample_relative_ms": receiver["samples"][0].get("relative_ms") if receiver["samples"] else None,
        "last_sample_relative_ms": receiver["samples"][-1].get("relative_ms") if receiver["samples"] else None,
        "numeric_varying_fields": varying_fields,
    }


def main() -> int:
    args = parse_args()
    runtime_log = Path(args.runtime_log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    windows = [parse_window(value) for value in args.window]

    counts: Counter[str] = Counter()
    receivers: dict[str, dict[str, Any]] = {}
    parse_errors: list[dict[str, Any]] = []

    def receiver_entry(receiver: str) -> dict[str, Any]:
        if receiver not in receivers:
            receivers[receiver] = {"receiver": receiver, "events": [], "samples": []}
        return receivers[receiver]

    with runtime_log.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                parse_errors.append({"line": line_no, "error": str(error)})
                continue
            payload = payload_from_record(record)
            kind = payload.get("kind") or record.get("event") or record.get("type") or "unknown"
            counts[str(kind)] += 1

            if kind == "cri_set_data":
                receiver = payload.get("receiver")
                if isinstance(receiver, str):
                    entry = receiver_entry(receiver)
                    entry["set_data_unix_ms"] = payload.get("unix_ms")
                    entry["byte_size_u32"] = payload.get("byte_size_u32")
                    entry["data_fnv1a_4k"] = payload.get("data_fnv1a_4k")
                    entry["data_head32_hex"] = payload.get("data_head32_hex")
                    add_event(entry, payload)
            elif kind == "cri_movie_info":
                receiver = payload.get("receiver")
                if isinstance(receiver, str):
                    entry = receiver_entry(receiver)
                    entry["movie_info"] = {
                        "width": payload.get("value0"),
                        "height": payload.get("value1"),
                        "frame_rate": payload.get("frame_rate"),
                        "frame_count": payload.get("value3"),
                        "value4": payload.get("value4"),
                        "return_i32": payload.get("return_i32"),
                    }
                    add_event(entry, payload)
            elif kind in {
                "cri_start",
                "cri_update",
                "cri_get_status",
                "cri_stop",
                "cri_destroy_player",
                "cri_set_loop",
            }:
                receiver = payload.get("receiver") or payload.get("arg0_pointer")
                if isinstance(receiver, str):
                    add_event(receiver_entry(receiver), payload)
            elif kind == "cri_receiver_numeric_sample":
                for sample in payload.get("samples", []):
                    if not isinstance(sample, dict):
                        continue
                    receiver = sample.get("receiver")
                    if not isinstance(receiver, str):
                        continue
                    entry = receiver_entry(receiver)
                    set_data_unix_ms = entry.get("set_data_unix_ms")
                    sample_unix_ms = payload.get("unix_ms")
                    if isinstance(sample_unix_ms, (int, float)) and isinstance(set_data_unix_ms, (int, float)):
                        relative_ms = sample_unix_ms - set_data_unix_ms
                    else:
                        relative_ms = None
                    copied = dict(sample)
                    copied["relative_ms"] = relative_ms
                    entry["samples"].append(copied)

    receiver_summaries = [summarize_receiver(receiver, windows) for receiver in receivers.values()]
    receiver_summaries.sort(
        key=lambda item: (
            str(item.get("data_fnv1a_4k") or ""),
            str(item.get("receiver") or ""),
        )
    )

    summary = {
        "runtime_log": str(runtime_log),
        "kind_counts": dict(counts),
        "parse_errors": parse_errors,
        "receiver_count": len(receiver_summaries),
        "receivers": receiver_summaries,
    }
    (out_dir / "cri_receiver_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with (out_dir / "cri_receiver_events.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "receiver",
                "data_fnv1a_4k",
                "byte_size_u32",
                "kind",
                "relative_ms",
                "return_i32",
            ],
        )
        writer.writeheader()
        for receiver in receivers.values():
            for event in receiver["events"]:
                writer.writerow(
                    {
                        "receiver": receiver["receiver"],
                        "data_fnv1a_4k": receiver.get("data_fnv1a_4k"),
                        "byte_size_u32": receiver.get("byte_size_u32"),
                        "kind": event.get("kind"),
                        "relative_ms": event.get("relative_ms"),
                        "return_i32": event.get("return_i32"),
                    }
                )

    print(json.dumps({"summary": str(out_dir / "cri_receiver_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
