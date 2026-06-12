#!/usr/bin/env python3
"""Inspect and request GBoss events through the ARM64 Frida Gadget."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import frida


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "status",
            "hash",
            "inspect",
            "inspect-code",
            "enumerate",
            "event-info",
            "request",
            "request-code",
            "request-official-code",
            "dump",
            "symbols",
        ),
    )
    parser.add_argument("--name")
    parser.add_argument("--code")
    parser.add_argument("--label")
    parser.add_argument("--offset", type=lambda value: int(value, 0))
    parser.add_argument("--size", type=lambda value: int(value, 0), default=0x100)
    parser.add_argument("--pattern")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--immediate", action="store_true")
    parser.add_argument("--with-sound", action="store_true")
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--attach-timeout", type=float, default=60.0)
    parser.add_argument(
        "--script",
        default=str(Path(__file__).with_name("event_scene_probe.js")),
    )
    parser.add_argument("--pre-wait", type=float, default=1.0)
    parser.add_argument("--object-wait", type=float, default=30.0)
    parser.add_argument("--post-wait", type=float, default=10.0)
    parser.add_argument("--out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action in {"hash", "inspect", "request"} and not args.name:
        raise SystemExit(f"--name is required for {args.action}")
    if args.action in {"inspect-code", "request-code", "request-official-code"} and not args.code:
        raise SystemExit(f"--code is required for {args.action}")
    if args.action == "dump" and args.offset is None:
        raise SystemExit("--offset is required for dump")
    if args.action == "symbols" and not args.pattern:
        raise SystemExit("--pattern is required for symbols")
    if args.limit < 0:
        raise SystemExit("--limit must be non-negative")

    output_path = Path(args.out).resolve() if args.out else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    manager = frida.get_device_manager()
    deadline = time.monotonic() + max(args.attach_timeout, 0.0)
    last_attach_error: Exception | None = None
    while True:
        try:
            device = manager.add_remote_device(args.host)
            processes = device.enumerate_processes()
            if not processes:
                raise RuntimeError(f"no process exposed by Gadget at {args.host}")
            target = processes[0]
            session = device.attach(target.pid)
            break
        except Exception as error:
            last_attach_error = error
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"failed to attach to Gadget at {args.host} within "
                    f"{args.attach_timeout:.1f}s"
                ) from last_attach_error
            time.sleep(1.0)
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

    status = script.exports_sync.status()
    record({"event": "initial_status", "state": status})

    if args.action == "request-official-code":
        object_deadline = time.monotonic() + max(args.object_wait, 0.0)
        valid_sources = {"last_animation_request", "C_AnmMain+0x350"}
        while (
            status.get("animation_state", {}).get("selected_source")
            not in valid_sources
        ):
            if time.monotonic() >= object_deadline:
                raise RuntimeError(
                    "no active C_AnmBase-derived scene object was found within "
                    f"{args.object_wait:.1f}s"
                )
            time.sleep(0.5)
            status = script.exports_sync.status()
        record(
            {
                "event": "animation_object_ready",
                "last_animation_request": status.get("last_animation_request"),
                "animation_state": status.get("animation_state"),
            }
        )

    if args.action == "status":
        result = status
    elif args.action == "hash":
        result = script.exports_sync.hash(args.name)
    elif args.action == "inspect":
        result = script.exports_sync.inspect(args.name)
    elif args.action == "inspect-code":
        result = script.exports_sync.inspectcode(args.code)
    elif args.action == "enumerate":
        result = script.exports_sync.enumerate(args.limit)
    elif args.action == "event-info":
        result = script.exports_sync.eventinfo(args.limit)
    elif args.action == "request":
        result = script.exports_sync.queuerequest(args.name, args.immediate)
        record({"event": "request_queued", "result": result})
        time.sleep(max(args.post_wait, 0.2))
        result = {
            "queued": result,
            "final_status": script.exports_sync.status(),
        }
    elif args.action in {"request-code", "request-official-code"}:
        result = script.exports_sync.queuecode(
            args.code,
            args.label or args.code,
            args.immediate,
            args.with_sound,
            args.action == "request-official-code",
        )
        record({"event": "request_queued", "result": result})
        time.sleep(max(args.post_wait, 0.2))
        result = {
            "queued": result,
            "final_status": script.exports_sync.status(),
        }
    elif args.action == "dump":
        result = script.exports_sync.dump(args.offset, args.size)
    else:
        result = script.exports_sync.symbols(args.pattern)

    record({"event": "result", "result": result})

    if output_path:
        with output_path.open("w", encoding="utf-8") as output:
            for item in records:
                output.write(json.dumps(item, ensure_ascii=False) + "\n")

    script.unload()
    session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
