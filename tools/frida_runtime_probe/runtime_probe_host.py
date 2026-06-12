#!/usr/bin/env python3
"""Attach to the ARM64 Frida Gadget and record runtime sound/text events."""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import frida


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--script", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--duration", type=float, default=120.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_path = Path(args.script).resolve()
    output_path = Path(args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manager = frida.get_device_manager()
    device = manager.add_remote_device(args.host)
    processes = device.enumerate_processes()
    if not processes:
        raise RuntimeError(f"no process exposed by Gadget at {args.host}")

    target = processes[0]
    session = device.attach(target.pid)
    source = script_path.read_text(encoding="utf-8")
    script = session.create_script(source)

    with output_path.open("a", encoding="utf-8", buffering=1) as output:
        def on_message(message: dict, data: bytes | None) -> None:
            record = {
                "host_unix_ms": int(time.time() * 1000),
                "message": message,
            }
            if data:
                record["data_base64"] = base64.b64encode(data).decode("ascii")
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            payload = message.get("payload", {})
            print(
                json.dumps(
                    {
                        "kind": payload.get("kind", message.get("type")),
                        "text": payload.get("text_utf8", ""),
                        "request_id": payload.get("request_id"),
                        "return_u32": payload.get("return_u32"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

        script.on("message", on_message)
        script.load()
        output.write(
            json.dumps(
                {
                    "host_unix_ms": int(time.time() * 1000),
                    "event": "host_attached",
                    "target_pid": target.pid,
                    "target_name": target.name,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        time.sleep(max(args.duration, 0.0))

    script.unload()
    session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
