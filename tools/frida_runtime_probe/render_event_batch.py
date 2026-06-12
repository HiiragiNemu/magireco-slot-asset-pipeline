#!/usr/bin/env python3
"""Render verified event manifests with bounded concurrency and an audit log."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def output_is_complete(out_root: Path, event: str) -> bool:
    event_root = out_root / event
    required = (
        event_root / "without_subtitles" / f"{event}.mp4",
        event_root / "with_subtitles" / f"{event}__subtitles.mp4",
        event_root / "subtitles" / f"{event}.srt",
        event_root / "render_manifest.json",
    )
    return all(path.is_file() and path.stat().st_size > 0 for path in required)


def render_one(
    renderer: Path,
    manifest_path: Path,
    out_root: Path,
    overwrite: bool,
) -> dict[str, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    event = str(manifest["event"])
    started = datetime.now(timezone.utc)
    if not manifest.get("quality_gates", {}).get("ready"):
        errors = manifest.get("quality_gates", {}).get("errors", [])
        return {
            "event": event,
            "status": "skipped_not_ready",
            "manifest": str(manifest_path),
            "elapsed_seconds": "0.000",
            "message": ";".join(errors),
        }
    if not overwrite and output_is_complete(out_root, event):
        return {
            "event": event,
            "status": "skipped_complete",
            "manifest": str(manifest_path),
            "elapsed_seconds": "0.000",
            "message": "",
        }

    command = [
        sys.executable,
        str(renderer),
        "--manifest",
        str(manifest_path),
        "--out-root",
        str(out_root),
    ]
    if overwrite:
        command.append("--overwrite")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    message = (result.stderr or result.stdout).strip().replace("\r", " ").replace(
        "\n", " | "
    )
    return {
        "event": event,
        "status": "rendered" if result.returncode == 0 else "failed",
        "manifest": str(manifest_path),
        "elapsed_seconds": f"{elapsed:.3f}",
        "message": message,
    }


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 4:
        raise SystemExit("--workers must be between 1 and 4")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be positive")

    manifest_root = Path(args.manifest_root).resolve()
    event_dir = manifest_root / "events"
    if not event_dir.is_dir():
        event_dir = manifest_root
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    renderer = Path(__file__).resolve().with_name("render_event_manifest.py")

    manifests = sorted(event_dir.glob("*.json"))
    if args.only:
        selected = set(args.only)
        manifests = [
            path for path in manifests if path.stem in selected
        ]
        missing = sorted(selected - {path.stem for path in manifests})
        if missing:
            raise SystemExit("missing manifests: " + ", ".join(missing))
    if args.limit is not None:
        manifests = manifests[: args.limit]
    if not manifests:
        raise SystemExit("no event manifests selected")

    rows: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                render_one,
                renderer,
                path,
                out_root,
                args.overwrite,
            ): path
            for path in manifests
        }
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"[{row['status']}] {row['event']}", flush=True)

    rows.sort(key=lambda row: row["event"])
    audit_path = out_root / "batch_render_audit.csv"
    with audit_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=[
                "event",
                "status",
                "manifest",
                "elapsed_seconds",
                "message",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    failed = [row for row in rows if row["status"] == "failed"]
    summary = {
        "selected": len(rows),
        "rendered": sum(row["status"] == "rendered" for row in rows),
        "skipped_complete": sum(
            row["status"] == "skipped_complete" for row in rows
        ),
        "skipped_not_ready": sum(
            row["status"] == "skipped_not_ready" for row in rows
        ),
        "failed": len(failed),
        "audit_csv": str(audit_path),
    }
    (out_root / "batch_render_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
