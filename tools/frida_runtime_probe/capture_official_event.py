#!/usr/bin/env python3
"""Capture one official event with separate event and runtime Frida probes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--pre-wait", type=float, default=3.0)
    parser.add_argument("--post-wait", type=float, default=10.0)
    parser.add_argument("--object-wait", type=float, default=10.0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tool_dir = Path(__file__).resolve().parent
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    runtime_log = out_dir / f"{args.label}__runtime.jsonl"
    event_log = out_dir / f"{args.label}__event.jsonl"
    runtime_stdout = out_dir / f"{args.label}__runtime.stdout.txt"
    runtime_stderr = out_dir / f"{args.label}__runtime.stderr.txt"
    event_stdout = out_dir / f"{args.label}__event.stdout.txt"
    event_stderr = out_dir / f"{args.label}__event.stderr.txt"
    paths = (
        runtime_log,
        event_log,
        runtime_stdout,
        runtime_stderr,
        event_stdout,
        event_stderr,
    )
    existing = [path for path in paths if path.exists()]
    if existing and not args.overwrite:
        names = ", ".join(str(path) for path in existing)
        raise SystemExit(f"refusing to overwrite existing capture files: {names}")
    if args.overwrite:
        for path in existing:
            path.unlink()

    runtime_duration = max(args.pre_wait, 0.0) + max(args.post_wait, 0.0) + 5.0
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
        str(runtime_duration),
    ]
    event_command = [
        sys.executable,
        str(tool_dir / "event_scene_host.py"),
        "request-official-code",
        "--host",
        args.host,
        "--code",
        args.code,
        "--label",
        args.label,
        "--pre-wait",
        "1",
        "--object-wait",
        str(max(args.object_wait, 0.0)),
        "--post-wait",
        str(max(args.post_wait, 0.2)),
        "--out",
        str(event_log),
    ]

    with (
        runtime_stdout.open("w", encoding="utf-8") as runtime_out,
        runtime_stderr.open("w", encoding="utf-8") as runtime_err,
    ):
        runtime_process = subprocess.Popen(
            runtime_command,
            stdout=runtime_out,
            stderr=runtime_err,
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
                timeout=max(runtime_duration + 15.0, 30.0)
            )
        except BaseException:
            runtime_process.terminate()
            runtime_process.wait(timeout=10)
            raise

    summary = {
        "event": args.label,
        "code_hex": args.code,
        "event_exit_code": event_result.returncode,
        "runtime_exit_code": runtime_result,
        "event_log": str(event_log),
        "runtime_log": str(runtime_log),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if event_result.returncode != 0 or runtime_result != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
