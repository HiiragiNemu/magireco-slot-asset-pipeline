#!/usr/bin/env python3
"""Drive the native title-to-slot scene transition through the ARM64 Gadget."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import frida


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "enter-slot"))
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--attach-timeout", type=float, default=30.0)
    parser.add_argument(
        "--script",
        default=str(Path(__file__).with_name("title_scene_probe.js")),
    )
    parser.add_argument("--pre-wait", type=float, default=2.0)
    parser.add_argument("--post-wait", type=float, default=20.0)
    parser.add_argument("--out")
    return parser.parse_args()


def attach_gadget(host: str, timeout: float) -> tuple[frida.core.Session, object]:
    manager = frida.get_device_manager()
    deadline = time.monotonic() + max(timeout, 0.0)
    last_error: Exception | None = None
    while True:
        try:
            device = manager.add_remote_device(host)
            processes = device.enumerate_processes()
            if not processes:
                raise RuntimeError(f"no process exposed at {host}")
            target = processes[0]
            return device.attach(target.pid), target
        except Exception as error:
            last_error = error
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"failed to attach to Gadget at {host} within {timeout:.1f}s"
                ) from last_error
            time.sleep(1.0)


def main() -> int:
    args = parse_args()
    output_path = Path(args.out).resolve() if args.out else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    session, target = attach_gadget(args.host, args.attach_timeout)
    source = Path(args.script).resolve().read_text(encoding="utf-8")
    script = session.create_script(source)
    records: list[dict] = []

    def record(value: dict) -> None:
        records.append(value)
        print(json.dumps(value, ensure_ascii=False), flush=True)

    def on_message(message: dict, data: bytes | None) -> None:
        record(
            {
                "host_unix_ms": int(time.time() * 1000),
                "message": message,
                "data_length": len(data) if data else 0,
            }
        )

    script.on("message", on_message)
    script.load()
    time.sleep(max(args.pre_wait, 0.2))
    record(
        {
            "event": "attached",
            "target_pid": target.pid,
            "target_name": target.name,
            "status": script.exports_sync.status(),
        }
    )

    if args.action == "enter-slot":
        record(
            {
                "event": "transition_queued",
                "result": script.exports_sync.enterslot(),
            }
        )
        time.sleep(max(args.post_wait, 0.2))

    record({"event": "final_status", "status": script.exports_sync.status()})

    if output_path:
        with output_path.open("w", encoding="utf-8") as output:
            for item in records:
                output.write(json.dumps(item, ensure_ascii=False) + "\n")

    script.unload()
    session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
