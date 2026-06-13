#!/usr/bin/env python3
"""Flag visually component-like audience videos without auto-rejecting them."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dark-threshold", type=int, default=16)
    return parser.parse_args()


def sample_frames(path: Path) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {path}")
    frame_count = max(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
    frames: list[np.ndarray] = []
    for fraction in (0.10, 0.50, 0.90):
        capture.set(cv2.CAP_PROP_POS_FRAMES, round((frame_count - 1) * fraction))
        ok, frame = capture.read()
        if ok:
            frames.append(frame)
    capture.release()
    if not frames:
        raise RuntimeError(f"cannot decode sample frames: {path}")
    return frames


def frame_metrics(frame: np.ndarray, dark_threshold: int) -> dict[str, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    active = gray > dark_threshold
    dark_fraction = 1.0 - float(np.count_nonzero(active)) / active.size
    if np.any(active):
        y_values, x_values = np.where(active)
        width = int(x_values.max() - x_values.min() + 1)
        height = int(y_values.max() - y_values.min() + 1)
        bbox_fraction = (width * height) / active.size
    else:
        bbox_fraction = 0.0
    return {
        "dark_fraction": dark_fraction,
        "active_bbox_fraction": bbox_fraction,
        "mean_luma": float(np.mean(gray)),
        "luma_stddev": float(np.std(gray)),
    }


def write_contact_sheet(path: Path, frames: list[np.ndarray]) -> None:
    height = min(frame.shape[0] for frame in frames)
    resized = [
        cv2.resize(
            frame,
            (
                round(frame.shape[1] * height / frame.shape[0]),
                height,
            ),
            interpolation=cv2.INTER_AREA,
        )
        for frame in frames
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.hconcat(resized))


def main() -> int:
    args = parse_args()
    video_dir = Path(args.video_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    contact_dir = out_dir / "review_contact_sheets"
    rows: list[dict[str, object]] = []
    for path in sorted(video_dir.glob("*.mp4")):
        frames = sample_frames(path)
        metrics = [
            frame_metrics(frame, args.dark_threshold) for frame in frames
        ]
        median_dark = statistics.median(
            metric["dark_fraction"] for metric in metrics
        )
        median_bbox = statistics.median(
            metric["active_bbox_fraction"] for metric in metrics
        )
        median_stddev = statistics.median(
            metric["luma_stddev"] for metric in metrics
        )
        reasons: list[str] = []
        if median_dark >= 0.80 and median_bbox <= 0.35:
            reasons.append("dark_small_active_region")
        if median_dark >= 0.95 and median_stddev <= 8.0:
            reasons.append("near_blank")
        status = "review" if reasons else "accepted_by_frame_screen"
        if reasons:
            write_contact_sheet(contact_dir / f"{path.stem}.jpg", frames)
        rows.append(
            {
                "event": path.stem,
                "status": status,
                "reasons": ";".join(reasons),
                "median_dark_fraction": f"{median_dark:.6f}",
                "median_active_bbox_fraction": f"{median_bbox:.6f}",
                "median_luma_stddev": f"{median_stddev:.3f}",
                "video_path": str(path),
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "event",
        "status",
        "reasons",
        "median_dark_fraction",
        "median_active_bbox_fraction",
        "median_luma_stddev",
        "video_path",
    ]
    csv_path = out_dir / "audience_frame_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "videos": len(rows),
        "accepted_by_frame_screen": sum(
            row["status"] == "accepted_by_frame_screen" for row in rows
        ),
        "review": sum(row["status"] == "review" for row in rows),
        "audit_csv": str(csv_path),
        "contact_sheet_dir": str(contact_dir),
        "note": "Review flags are not automatic audience exclusions.",
    }
    (out_dir / "audience_frame_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
