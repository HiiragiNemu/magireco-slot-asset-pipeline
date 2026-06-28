#!/usr/bin/env python3
"""Audit runtime evidence packages under a repair/research root."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


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


def failed_checks(qa: dict[str, Any]) -> list[str]:
    return [
        str(check.get("name", ""))
        for check in qa.get("checks", [])
        if isinstance(check, dict) and not check.get("passed")
    ]


def package_row(root: Path, qa_path: Path) -> dict[str, Any]:
    qa = read_json(qa_path)
    package_dir = qa_path.parent
    manifest_path = package_dir / "package_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    summary = qa.get("summary", {}) if isinstance(qa.get("summary"), dict) else {}
    failures = failed_checks(qa)
    capture_dir = Path(str(qa.get("capture_dir") or package_dir.parent))
    return {
        "capture_name": capture_dir.name,
        "capture_dir": str(capture_dir),
        "package_dir": str(package_dir),
        "package_relative": str(package_dir.relative_to(root)) if package_dir.is_relative_to(root) else str(package_dir),
        "label": manifest.get("label", ""),
        "status": qa.get("status", ""),
        "failed_checks": ";".join(failures),
        "failed_check_count": len(failures),
        "event_code_count": summary.get("event_code_count", ""),
        "sound_code_lookup_count": summary.get("sound_code_lookup_count", ""),
        "bgm_call_count": summary.get("bgm_call_count", ""),
        "queue_chunk_count": summary.get("queue_chunk_count", ""),
        "queue_metadata_count": summary.get("queue_metadata_count", ""),
        "duration_seconds": summary.get("duration_seconds", ""),
        "rendered_rms_dbfs": summary.get("rendered_rms_dbfs", ""),
        "observed_sound_ids": ";".join(str(value) for value in summary.get("observed_sound_ids", []) or []),
        "qa_report": str(qa_path),
        "package_manifest": str(manifest_path) if manifest_path.exists() else "",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    out_dir = args.out_dir.resolve()
    qa_paths = sorted(root.rglob("evidence_package_v*/qa_report.json"))
    rows = [package_row(root, path) for path in qa_paths]
    status_counts = Counter(row["status"] for row in rows)
    failed_check_counts = Counter()
    for row in rows:
        for name in str(row.get("failed_checks") or "").split(";"):
            if name:
                failed_check_counts[name] += 1

    fieldnames = [
        "capture_name",
        "status",
        "failed_checks",
        "failed_check_count",
        "event_code_count",
        "sound_code_lookup_count",
        "bgm_call_count",
        "queue_chunk_count",
        "queue_metadata_count",
        "duration_seconds",
        "rendered_rms_dbfs",
        "observed_sound_ids",
        "capture_dir",
        "package_dir",
        "package_relative",
        "label",
        "qa_report",
        "package_manifest",
    ]
    write_csv(out_dir / "runtime_evidence_package_index.csv", rows, fieldnames)
    summary = {
        "schema": "magireco_runtime_evidence_package_index.v1",
        "root": str(root),
        "package_count": len(rows),
        "status_counts": dict(status_counts),
        "failed_check_counts": dict(failed_check_counts),
        "packages": rows,
    }
    write_json(out_dir / "runtime_evidence_package_index.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "packages"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
