#!/usr/bin/env python3
"""Capture an official event sequence with runtime logs and an ADB recording."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence-json", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--serial", default="127.0.0.1:16384")
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--pre-wait", type=float, default=3.0)
    parser.add_argument("--post-wait", type=float, default=5.0)
    parser.add_argument("--object-wait", type=float, default=10.0)
    parser.add_argument("--bit-rate", type=int, default=12_000_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tool_dir = Path(__file__).resolve().parent
    sequence_path = Path(args.sequence_json).resolve()
    sequence = json.loads(sequence_path.read_text(encoding="utf-8"))
    if not isinstance(sequence, list) or not sequence:
        raise SystemExit("sequence JSON must be a non-empty list")
    sequence_duration = sum(
        max(float(item.get("delay_after", 0.0)), 0.0) for item in sequence
    )

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    runtime_log = out_dir / f"{args.label}__runtime.jsonl"
    event_log = out_dir / f"{args.label}__event.jsonl"
    recording = out_dir / f"{args.label}__screen.mp4"
    runtime_stdout = out_dir / f"{args.label}__runtime.stdout.txt"
    runtime_stderr = out_dir / f"{args.label}__runtime.stderr.txt"
    event_stdout = out_dir / f"{args.label}__event.stdout.txt"
    event_stderr = out_dir / f"{args.label}__event.stderr.txt"
    screen_stdout = out_dir / f"{args.label}__screen.stdout.txt"
    screen_stderr = out_dir / f"{args.label}__screen.stderr.txt"
    paths = (
        runtime_log,
        event_log,
        recording,
        runtime_stdout,
        runtime_stderr,
        event_stdout,
        event_stderr,
        screen_stdout,
        screen_stderr,
    )
    existing = [path for path in paths if path.exists()]
    if existing:
        raise SystemExit(
            "refusing to overwrite existing capture files: "
            + ", ".join(str(path) for path in existing)
        )

    total_duration = (
        max(args.pre_wait, 0.0)
        + sequence_duration
        + max(args.post_wait, 0.0)
        + 5.0
    )
    remote_recording = f"/sdcard/{args.label}__screen.mp4"
    runtime_command = [
        sys.executable,
        str(tool_dir / "runtime_probe_host.py"),
        "--host",
        args.host,
        "--script",
        str(tool_dir / "runtime_probe.js"),
        "--out",
        str(runtime_log),
        "--duration",
        str(total_duration),
    ]
    event_command = [
        sys.executable,
        str(tool_dir / "event_scene_host.py"),
        "request-official-sequence",
        "--host",
        args.host,
        "--sequence-json",
        str(sequence_path),
        "--pre-wait",
        "1",
        "--object-wait",
        str(max(args.object_wait, 0.0)),
        "--post-wait",
        str(max(args.post_wait, 0.2)),
        "--out",
        str(event_log),
    ]
    screen_command = [
        "adb",
        "-s",
        args.serial,
        "shell",
        "screenrecord",
        "--bit-rate",
        str(max(args.bit_rate, 1)),
        "--time-limit",
        str(max(1, min(math.ceil(total_duration), 180))),
        remote_recording,
    ]

    with (
        runtime_stdout.open("w", encoding="utf-8") as runtime_out,
        runtime_stderr.open("w", encoding="utf-8") as runtime_err,
        screen_stdout.open("w", encoding="utf-8") as screen_out,
        screen_stderr.open("w", encoding="utf-8") as screen_err,
    ):
        runtime_process = subprocess.Popen(
            runtime_command,
            stdout=runtime_out,
            stderr=runtime_err,
            text=True,
        )
        screen_process = subprocess.Popen(
            screen_command,
            stdout=screen_out,
            stderr=screen_err,
            text=True,
        )
        try:
            time.sleep(max(args.pre_wait, 0.2))
            with (
                event_stdout.open("w", encoding="utf-8") as event_out,
                event_stderr.open("w", encoding="utf-8") as event_err,
            ):
                event_result = subprocess.run(
                    event_command,
                    stdout=event_out,
                    stderr=event_err,
                    text=True,
                    check=False,
                )
            runtime_result = runtime_process.wait(
                timeout=max(total_duration + 15.0, 30.0)
            )
            screen_result = screen_process.wait(
                timeout=max(total_duration + 15.0, 30.0)
            )
        except BaseException:
            for process in (runtime_process, screen_process):
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
            raise

    pull_result = subprocess.run(
        ["adb", "-s", args.serial, "pull", remote_recording, str(recording)],
        capture_output=True,
        text=True,
        check=False,
    )
    summary = {
        "label": args.label,
        "sequence_json": str(sequence_path),
        "event_exit_code": event_result.returncode,
        "runtime_exit_code": runtime_result,
        "screen_exit_code": screen_result,
        "pull_exit_code": pull_result.returncode,
        "event_log": str(event_log),
        "runtime_log": str(runtime_log),
        "recording": str(recording),
        "recording_bytes": recording.stat().st_size if recording.is_file() else 0,
        "pull_stdout": pull_result.stdout.strip(),
        "pull_stderr": pull_result.stderr.strip(),
    }
    summary_path = out_dir / f"{args.label}__summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(
        code == 0
        for code in (
            event_result.returncode,
            runtime_result,
            screen_result,
            pull_result.returncode,
        )
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
