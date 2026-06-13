#!/usr/bin/env python3
"""Generate plans only for composition families verified against the game."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def write_plan(path: Path, plan: dict, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def lev_plan(manifest: dict) -> dict | None:
    event = manifest["event"]
    if not event.startswith(("ac1101_", "ac1102_", "ac1103_", "ac1104_")):
        return None
    clips = manifest["clips"]
    title = [row for row in clips if "_title_" in row["dgm_name"]]
    c001 = [row for row in clips if "_c001_" in row["dgm_name"]]
    c002 = [
        row
        for row in clips
        if "_c002" in row["dgm_name"] and not row["dgm_name"].lower().endswith("_lp")
    ]
    c002_loop = [
        row
        for row in clips
        if "_c002" in row["dgm_name"] and row["dgm_name"].lower().endswith("_lp")
    ]
    if not all(len(group) == 1 for group in (title, c001, c002, c002_loop)):
        return None
    return {
        "schema": "magireco-video-composition-v1",
        "event": event,
        "model": "timed_full_frame_layers",
        "duration_ms": manifest["render_duration_ms"],
        "evidence": "family_runtime_ac1101_and_static_black_matte_validation_2026-06-13",
        "clips": [
            {
                "dgm_name": c001[0]["dgm_name"],
                "role": "background",
                "start_ms": c001[0]["event_start_ms"],
            },
            {
                "dgm_name": c002[0]["dgm_name"],
                "role": "background",
                "start_ms": c002[0]["event_start_ms"],
            },
            {
                "dgm_name": c002_loop[0]["dgm_name"],
                "role": "loop_background",
                "start_ms": c002_loop[0]["event_start_ms"],
            },
            {
                "dgm_name": title[0]["dgm_name"],
                "role": "screen_overlay",
                "start_ms": title[0]["event_start_ms"],
            },
        ],
    }


def ac0912_plan(manifest: dict) -> dict | None:
    event = manifest["event"]
    if not event.startswith("ac0912_"):
        return None
    clips = manifest["clips"]
    flash = [row for row in clips if "_ef_flash" in row["dgm_name"]]
    qb = [
        row
        for row in clips
        if "_QB" in row["dgm_name"] and not row["dgm_name"].lower().endswith("_lp")
    ]
    qb_loop = [
        row
        for row in clips
        if "_QB" in row["dgm_name"] and row["dgm_name"].lower().endswith("_lp")
    ]
    backgrounds = [
        row
        for row in clips
        if row not in flash
        and row not in qb
        and row not in qb_loop
        and not row["dgm_name"].lower().endswith("_lp")
    ]
    background_loops = [
        row
        for row in clips
        if row not in qb_loop
        and row["dgm_name"].lower().endswith("_lp")
    ]
    groups = (flash, qb, qb_loop, backgrounds, background_loops)
    if not all(len(group) == 1 for group in groups):
        return None
    return {
        "schema": "magireco-video-composition-v1",
        "event": event,
        "model": "timed_full_frame_layers",
        "duration_ms": manifest["render_duration_ms"],
        "evidence": "runtime_screens_ac0912_104_and_black_matte_validation_2026-06-13",
        "clips": [
            {
                "dgm_name": backgrounds[0]["dgm_name"],
                "role": "background",
                "start_ms": backgrounds[0]["event_start_ms"],
            },
            {
                "dgm_name": background_loops[0]["dgm_name"],
                "role": "loop_background",
                "start_ms": background_loops[0]["event_start_ms"],
            },
            {
                "dgm_name": flash[0]["dgm_name"],
                "role": "screen_overlay",
                "start_ms": flash[0]["event_start_ms"],
            },
            {
                "dgm_name": qb[0]["dgm_name"],
                "role": "screen_overlay",
                "start_ms": qb[0]["event_start_ms"],
            },
            {
                "dgm_name": qb_loop[0]["dgm_name"],
                "role": "loop_screen_overlay",
                "start_ms": qb_loop[0]["event_start_ms"],
            },
        ],
    }


def main() -> int:
    args = parse_args()
    manifest_dir = Path(args.manifest_root) / "events"
    if not manifest_dir.is_dir():
        manifest_dir = Path(args.manifest_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    skipped_existing = 0
    for manifest_path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plan = lev_plan(manifest) or ac0912_plan(manifest)
        if not plan:
            continue
        if write_plan(out_dir / f"{manifest['event']}.json", plan, args.overwrite):
            generated += 1
        else:
            skipped_existing += 1
    print(
        json.dumps(
            {
                "generated": generated,
                "skipped_existing": skipped_existing,
                "out_dir": str(out_dir.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
