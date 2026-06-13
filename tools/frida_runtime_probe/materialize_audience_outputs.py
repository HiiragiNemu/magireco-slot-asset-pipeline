#!/usr/bin/env python3
"""Create a clean audience tree from already rendered, approved events."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--out-root", required=True)
    return parser.parse_args()


def link_or_copy(source: Path, target: Path) -> str:
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def main() -> int:
    args = parse_args()
    manifest_root = Path(args.manifest_root).resolve()
    manifest_dir = manifest_root / "events"
    if not manifest_dir.is_dir():
        manifest_dir = manifest_root
    source_root = Path(args.source_root).resolve()
    out_root = Path(args.out_root).resolve()
    if out_root.exists() and any(out_root.iterdir()):
        raise SystemExit(f"refusing to use non-empty output root: {out_root}")

    rows: list[dict[str, object]] = []
    methods = {"hardlink": 0, "copy": 0}
    for manifest_path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("quality_gates", {}).get("ready"):
            continue
        event = str(manifest["event"])
        source_event = source_root / event
        source_files = {
            "without_subtitles": (
                source_event / "without_subtitles" / f"{event}.mp4"
            ),
            "with_subtitles": (
                source_event
                / "with_subtitles"
                / f"{event}__subtitles.mp4"
            ),
            "subtitle": source_event / "subtitles" / f"{event}.srt",
        }
        missing = [
            f"{label}:{path}"
            for label, path in source_files.items()
            if not path.is_file()
        ]
        if missing:
            raise SystemExit(
                f"missing rendered files for {event}: " + ", ".join(missing)
            )

        targets = {
            "without_subtitles": (
                out_root / "without_subtitles" / f"{event}.mp4"
            ),
            "with_subtitles": (
                out_root / "with_subtitles" / f"{event}__subtitles.mp4"
            ),
            "subtitle": out_root / "subtitles" / f"{event}.srt",
            "manifest": out_root / "manifests" / f"{event}.json",
        }
        event_methods = {}
        for label in ("without_subtitles", "with_subtitles", "subtitle"):
            method = link_or_copy(source_files[label], targets[label])
            methods[method] += 1
            event_methods[label] = method
        method = link_or_copy(manifest_path, targets["manifest"])
        methods[method] += 1
        event_methods["manifest"] = method

        rows.append(
            {
                "event": event,
                "width": manifest["native_dimensions"]["width"],
                "height": manifest["native_dimensions"]["height"],
                "frame_rate": manifest["native_frame_rate"],
                "subtitle_count": len(manifest["subtitles"]),
                "audio_tracks": len(manifest["audio"]),
                "methods": event_methods,
            }
        )

    out_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema": "magireco-audience-output-v1",
        "events": len(rows),
        "editions": {
            "without_subtitles": str(out_root / "without_subtitles"),
            "with_subtitles": str(out_root / "with_subtitles"),
            "subtitle_files": str(out_root / "subtitles"),
            "manifests": str(out_root / "manifests"),
        },
        "file_materialization": methods,
        "source_root": str(source_root),
        "manifest_root": str(manifest_root),
        "events_detail": rows,
    }
    (out_root / "audience_output_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "events_detail"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
