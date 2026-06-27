#!/usr/bin/env python3
"""Write source hashes and cumulative timelines for one rendered event.

This complements render_manifest.json.  The renderer already records output
hashes and stream probes; this audit records the production manifest hash, input
clip/audio hashes, optional event-table index, and a single ordered timeline that
can be checked without re-rendering the media.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-manifest", required=True)
    parser.add_argument(
        "--event-timeline-events",
        default="",
        help="optional asset_manifests/event_timeline_events.csv for event_index",
    )
    parser.add_argument("--out-dir", default="")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_record(path_text: str, *, label: str, order: int) -> dict[str, Any]:
    path = Path(path_text)
    exists = path.is_file()
    return {
        "label": label,
        "order": order,
        "path": str(path),
        "exists": exists,
        "size": path.stat().st_size if exists else "",
        "sha256": sha256(path) if exists else "",
    }


def number(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def find_event_table_row(path: Path, event: str) -> dict[str, str]:
    if not path.is_file():
        return {}
    for row in read_csv(path):
        if row.get("primary_animation") == event:
            return row
    return {}


def main() -> int:
    args = parse_args()
    render_manifest_path = Path(args.render_manifest).resolve()
    render_manifest = read_json(render_manifest_path)
    production_manifest_path = Path(render_manifest["source_manifest"]).resolve()
    production_manifest = read_json(production_manifest_path)
    event = str(production_manifest["event"])

    out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else render_manifest_path.parent
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    event_table_row = find_event_table_row(
        Path(args.event_timeline_events), event
    ) if args.event_timeline_events else {}

    source_files: list[dict[str, Any]] = [
        file_record(str(production_manifest_path), label="production_manifest", order=0),
        file_record(str(render_manifest_path), label="render_manifest", order=1),
    ]
    for index, row in enumerate(production_manifest.get("clips", []), start=1):
        source_files.append(
            file_record(str(row.get("path", "")), label=f"clip:{index}", order=index)
        )
    for index, row in enumerate(production_manifest.get("audio", []), start=1):
        source_files.append(
            file_record(str(row.get("path", "")), label=f"audio:{index}", order=index)
        )
    for label in ("without_subtitles", "with_subtitles", "subtitles"):
        source_files.append(
            file_record(
                str(render_manifest.get(label, "")),
                label=f"output:{label}",
                order=len(source_files),
            )
        )

    timeline_rows: list[dict[str, Any]] = []
    for index, row in enumerate(production_manifest.get("clips", [])):
        start_ms = number(row.get("event_start_ms", 0))
        end_ms = number(row.get("event_end_ms", 0))
        timeline_rows.append(
            {
                "event": event,
                "kind": "video",
                "order": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": max(0, end_ms - start_ms),
                "name": row.get("dgm_name", ""),
                "source": row.get("path", ""),
                "sha256": sha256(Path(row["path"])) if Path(row.get("path", "")).is_file() else "",
                "evidence": row.get("interval_confidence", ""),
            }
        )
    for index, row in enumerate(production_manifest.get("audio", [])):
        start_ms = number(row.get("start_ms", 0))
        duration_ms = number(row.get("duration_ms", 0))
        timeline_rows.append(
            {
                "event": event,
                "kind": "audio",
                "order": index,
                "start_ms": start_ms,
                "end_ms": start_ms + duration_ms,
                "duration_ms": duration_ms,
                "name": row.get("code_name", ""),
                "source": row.get("path", ""),
                "sha256": sha256(Path(row["path"])) if Path(row.get("path", "")).is_file() else "",
                "evidence": row.get("evidence", ""),
            }
        )
    for index, row in enumerate(production_manifest.get("subtitles", [])):
        start_ms = number(row.get("start_ms", 0))
        end_ms = number(row.get("end_ms", 0))
        timeline_rows.append(
            {
                "event": event,
                "kind": "subtitle",
                "order": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": max(0, end_ms - start_ms),
                "name": row.get("text", ""),
                "source": row.get("voice_request_id", ""),
                "sha256": "",
                "evidence": row.get("evidence", ""),
            }
        )
    timeline_rows.sort(
        key=lambda row: (number(row["start_ms"]), row["kind"], number(row["order"]))
    )

    timeline_fields = [
        "event",
        "kind",
        "order",
        "start_ms",
        "end_ms",
        "duration_ms",
        "name",
        "source",
        "sha256",
        "evidence",
    ]
    timeline_path = out_dir / "source_timeline.csv"
    write_csv(timeline_path, timeline_rows, timeline_fields)

    source_files_path = out_dir / "source_hashes.csv"
    write_csv(
        source_files_path,
        source_files,
        ["label", "order", "path", "exists", "size", "sha256"],
    )

    output_hashes = {
        key: sha256(Path(render_manifest[key]))
        for key in ("without_subtitles", "with_subtitles", "subtitles")
        if render_manifest.get(key) and Path(render_manifest[key]).is_file()
    }
    declared_output_hashes = {
        key: str(value).upper()
        for key, value in render_manifest.get("sha256", {}).items()
    }
    output_hash_match = all(
        output_hashes.get(key, "") == declared_output_hashes.get(key, "")
        for key in declared_output_hashes
    )

    audit_manifest = {
        "schema": "magireco-render-source-integrity-v1",
        "event": event,
        "event_code_hex": production_manifest.get("event_code_hex", ""),
        "event_index": event_table_row.get("event_index", ""),
        "event_key": event_table_row.get("event_key", ""),
        "render_manifest": str(render_manifest_path),
        "production_manifest": str(production_manifest_path),
        "production_manifest_sha256": sha256(production_manifest_path),
        "render_manifest_sha256": sha256(render_manifest_path),
        "render_duration_ms": production_manifest.get("render_duration_ms", ""),
        "native_dimensions": production_manifest.get("native_dimensions", {}),
        "native_frame_rate": production_manifest.get("native_frame_rate", ""),
        "clip_count": len(production_manifest.get("clips", [])),
        "audio_count": len(production_manifest.get("audio", [])),
        "subtitle_count": len(production_manifest.get("subtitles", [])),
        "timeline_csv": str(timeline_path),
        "source_hashes_csv": str(source_files_path),
        "output_hashes": output_hashes,
        "declared_output_hashes": declared_output_hashes,
        "output_hash_match": output_hash_match,
        "source_files": source_files,
    }
    audit_path = out_dir / "source_integrity_manifest.json"
    audit_path.write_text(
        json.dumps(audit_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit_manifest, ensure_ascii=False, indent=2))
    return 0 if output_hash_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
