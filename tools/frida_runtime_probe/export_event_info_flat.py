#!/usr/bin/env python3
"""Flatten the nested event-info Frida result into ordinary CSV and JSONL."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = ("index", "code_hex", "base_name", "scene_name")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--jsonl", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log_path = Path(args.log)
    csv_path = Path(args.csv)
    jsonl_path = Path(args.jsonl)
    rows: list[dict] | None = None

    with log_path.open("r", encoding="utf-8") as source:
        for line in source:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            result = record.get("result")
            if isinstance(result, dict) and isinstance(result.get("rows"), list):
                rows = result["rows"]

    if rows is None:
        raise SystemExit(f"no event-info result rows found in {log_path}")

    cleaned = [
        {field: row.get(field, "") for field in FIELDS}
        for row in rows
        if row.get("scene_name") or row.get("base_name") or row.get("code_hex")
    ]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(cleaned)
    with jsonl_path.open("w", encoding="utf-8") as output:
        for row in cleaned:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[event-info] rows: {len(cleaned)}")
    print(f"[event-info] csv: {csv_path}")
    print(f"[event-info] jsonl: {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
