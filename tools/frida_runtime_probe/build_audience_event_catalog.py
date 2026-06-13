#!/usr/bin/env python3
"""Build an auditable event catalog and exclude component-only media."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-info", required=True)
    parser.add_argument("--video-timeline", required=True)
    parser.add_argument("--video-probes", required=True)
    parser.add_argument("--voice-catalog", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def media_class(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    aspect = width / height
    if width >= 400 and height >= 220 and 1.55 <= aspect <= 2.05:
        return "full_frame_landscape"
    if height > width and height >= 400:
        return "portrait_component"
    if width == height:
        return "square_component"
    return "other_component"


def main() -> int:
    args = parse_args()
    event_info = read_csv(Path(args.event_info))
    timeline = read_csv(Path(args.video_timeline))
    probes = read_csv(Path(args.video_probes))
    voices = read_csv(Path(args.voice_catalog))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    event_code = {
        row.get("scene_name", "").lower(): row.get("code_hex", "")
        for row in event_info
        if row.get("scene_name")
    }
    probe_by_media = {
        (row.get("package", ""), row.get("package_index", "")): row
        for row in probes
    }
    voice_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in voices:
        if row.get("auto_accepted") == "yes" and row.get("ogg_exists") == "yes":
            voice_by_event[row.get("event_name", "")].append(row)

    clips_by_event: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple] = set()
    for row in timeline:
        event = row.get("event_name", "")
        key = (
            event,
            row.get("z2d_name", ""),
            row.get("dgm_order", ""),
            row.get("dgm_name", ""),
            row.get("package", ""),
            row.get("package_index", ""),
            row.get("event_start_ms", ""),
            row.get("event_end_ms", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        probe = probe_by_media.get(
            (row.get("package", ""), row.get("package_index", "")), {}
        )
        width = int(float(probe.get("width", "0") or 0))
        height = int(float(probe.get("height", "0") or 0))
        source_path = row.get("target_mp4") or row.get("source_mp4", "")
        clips_by_event[event].append(
            {
                "event_name": event,
                "z2d_order": row.get("z2d_order", ""),
                "z2d_name": row.get("z2d_name", ""),
                "dgm_order": row.get("dgm_order", ""),
                "dgm_name": row.get("dgm_name", ""),
                "dgm_role": row.get("dgm_role", ""),
                "event_start_ms": row.get("event_start_ms", ""),
                "event_end_ms": row.get("event_end_ms", ""),
                "media_duration_sec": row.get("media_duration_sec", ""),
                "package": row.get("package", ""),
                "package_index": row.get("package_index", ""),
                "official_name": row.get("official_name", ""),
                "source_mp4": row.get("source_mp4", ""),
                "target_mp4": row.get("target_mp4", ""),
                "source_exists": (
                    "yes" if source_path and Path(source_path).exists() else "no"
                ),
                "width": width,
                "height": height,
                "frame_rate": probe.get("frame_rate", ""),
                "media_class": media_class(width, height),
                "interval_confidence": row.get("interval_confidence", ""),
            }
        )

    clip_fields = [
        "event_name",
        "z2d_order",
        "z2d_name",
        "dgm_order",
        "dgm_name",
        "dgm_role",
        "event_start_ms",
        "event_end_ms",
        "media_duration_sec",
        "package",
        "package_index",
        "official_name",
        "source_mp4",
        "target_mp4",
        "source_exists",
        "width",
        "height",
        "frame_rate",
        "media_class",
        "interval_confidence",
    ]
    clip_rows = [
        row
        for event in sorted(clips_by_event)
        for row in sorted(
            clips_by_event[event],
            key=lambda item: (
                int(float(item["z2d_order"] or 0)),
                int(float(item["event_start_ms"] or 0)),
                int(float(item["dgm_order"] or 0)),
            ),
        )
    ]
    write_csv(out_dir / "audience_event_clips.csv", clip_rows, clip_fields)

    event_rows: list[dict] = []
    for event in sorted(clips_by_event):
        clips = clips_by_event[event]
        classes = {row["media_class"] for row in clips}
        full_count = sum(
            row["media_class"] == "full_frame_landscape" for row in clips
        )
        resolved_count = sum(row["source_exists"] == "yes" for row in clips)
        if full_count == len(clips) and clips:
            classification = "native_full_frame_only"
        elif full_count:
            classification = "mixed_full_frame_and_components"
        elif classes == {"unknown"}:
            classification = "unresolved"
        else:
            classification = "component_only"
        event_voices = voice_by_event.get(event, [])
        total_duration = sum(
            float(row.get("media_duration_sec", "0") or 0) for row in clips
        )
        dimensions = sorted(
            {
                f"{row['width']}x{row['height']}"
                for row in clips
                if row["width"] and row["height"]
            }
        )
        code_hex = event_code.get(event.lower(), "")
        automatic_candidate = (
            classification == "native_full_frame_only"
            and resolved_count == len(clips)
            and bool(code_hex)
        )
        event_rows.append(
            {
                "event_name": event,
                "code_hex": code_hex,
                "clip_count": len(clips),
                "resolved_clip_count": resolved_count,
                "full_frame_clip_count": full_count,
                "dimensions": ";".join(dimensions),
                "total_source_duration_sec": f"{total_duration:.6f}",
                "classification": classification,
                "auto_voice_count": len(event_voices),
                "has_auto_voice": "yes" if event_voices else "no",
                "automatic_candidate": "yes" if automatic_candidate else "no",
            }
        )

    event_fields = [
        "event_name",
        "code_hex",
        "clip_count",
        "resolved_clip_count",
        "full_frame_clip_count",
        "dimensions",
        "total_source_duration_sec",
        "classification",
        "auto_voice_count",
        "has_auto_voice",
        "automatic_candidate",
    ]
    write_csv(out_dir / "audience_event_catalog.csv", event_rows, event_fields)
    write_csv(
        out_dir / "automatic_full_frame_candidates.csv",
        [row for row in event_rows if row["automatic_candidate"] == "yes"],
        event_fields,
    )
    write_csv(
        out_dir / "component_or_mixed_review.csv",
        [row for row in event_rows if row["automatic_candidate"] != "yes"],
        event_fields,
    )

    summary = {
        "events": len(event_rows),
        "clips": len(clip_rows),
        "native_full_frame_only_events": sum(
            row["classification"] == "native_full_frame_only"
            for row in event_rows
        ),
        "mixed_events": sum(
            row["classification"] == "mixed_full_frame_and_components"
            for row in event_rows
        ),
        "component_only_events": sum(
            row["classification"] == "component_only" for row in event_rows
        ),
        "automatic_full_frame_candidates": sum(
            row["automatic_candidate"] == "yes" for row in event_rows
        ),
        "automatic_candidates_with_voice": sum(
            row["automatic_candidate"] == "yes"
            and row["has_auto_voice"] == "yes"
            for row in event_rows
        ),
    }
    with (out_dir / "audience_event_summary.json").open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
