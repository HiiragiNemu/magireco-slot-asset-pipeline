#!/usr/bin/env python3
"""Attach to the ARM64 Frida Gadget and record runtime sound/text events."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import frida


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--realm", choices=("native", "emulated"))
    parser.add_argument("--script", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--quiet", action="store_true", help="write JSONL only; do not echo every hook event")
    parser.add_argument(
        "--control-script",
        help="optional second script loaded in the same Gadget session for RPC control actions",
    )
    parser.add_argument("--control-action", help="RPC queue action to run from the optional control script")
    parser.add_argument("--control-value", type=int, help="integer value for the optional control action")
    parser.add_argument(
        "--control-sequence",
        help="comma-separated RPC actions for the optional control script, e.g. body_bet=1,body_force_next_lever=8",
    )
    parser.add_argument("--control-pre-wait", type=float, default=1.0)
    parser.add_argument("--control-post-wait", type=float, default=1.0)
    parser.add_argument("--control-step-wait", type=float, default=0.5)
    parser.add_argument(
        "--no-unload",
        action="store_true",
        help="exit without explicit script unload/detach; useful when Gadget cleanup blocks",
    )
    return parser.parse_args()


def parse_control_sequence(args: argparse.Namespace) -> list[tuple[str, int]]:
    actions: list[tuple[str, int]] = []
    if args.control_sequence:
        for raw_item in args.control_sequence.split(","):
            item = raw_item.strip()
            if not item:
                continue
            if "=" in item:
                name, raw_value = item.split("=", 1)
                actions.append((name.strip(), int(raw_value.strip(), 0)))
            else:
                actions.append((item, 0))
    elif args.control_action:
        actions.append((args.control_action, 0 if args.control_value is None else args.control_value))
    return actions


def main() -> int:
    args = parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    script_path = Path(args.script).resolve()
    control_script_path = Path(args.control_script).resolve() if args.control_script else None
    output_path = Path(args.out).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manager = frida.get_device_manager()
    device = manager.add_remote_device(args.host)
    processes = device.enumerate_processes()
    if not processes:
        raise RuntimeError(f"no process exposed by Gadget at {args.host}")

    target = processes[0]
    session = device.attach(target.pid, realm=args.realm)
    source = script_path.read_text(encoding="utf-8")
    script = session.create_script(source)
    control_script = None
    if control_script_path:
        control_script = session.create_script(control_script_path.read_text(encoding="utf-8"))

    with output_path.open("a", encoding="utf-8", buffering=1) as output:
        def write_host_event(event: str, **fields) -> None:
            output.write(
                json.dumps(
                    {
                        "host_unix_ms": int(time.time() * 1000),
                        "event": event,
                        **fields,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        def on_message(message: dict, data: bytes | None) -> None:
            record = {
                "host_unix_ms": int(time.time() * 1000),
                "message": message,
            }
            if data:
                record["data_base64"] = base64.b64encode(data).decode("ascii")
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            payload = message.get("payload", {})
            if not args.quiet:
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
        if control_script is not None:
            control_script.on("message", on_message)
            control_script.load()
        write_host_event(
            "host_attached",
            target_pid=target.pid,
            target_name=target.name,
            script=str(script_path),
            control_script=str(control_script_path) if control_script_path else "",
        )

        end_time = time.monotonic() + max(args.duration, 0.0)
        control_actions = parse_control_sequence(args)
        if control_script is not None and control_actions:
            time.sleep(max(args.control_pre_wait, 0.0))
            try:
                initial = control_script.exports_sync.status()
                write_host_event("control_initial_status", state=initial)
                for index, (action, value) in enumerate(control_actions, start=1):
                    accepted = control_script.exports_sync.queue(action, value)
                    write_host_event(
                        "control_action_queued",
                        action=action,
                        value=value,
                        sequence_index=index,
                        result=accepted,
                    )
                    time.sleep(max(args.control_step_wait, 0.0))
                    step_status = control_script.exports_sync.status()
                    write_host_event(
                        "control_step_status",
                        action=action,
                        value=value,
                        sequence_index=index,
                        state=step_status,
                    )
            except frida.InvalidOperationError as exc:
                write_host_event(
                    "control_action_error",
                    sequence=control_actions,
                    error=repr(exc),
                )
                raise
            time.sleep(max(args.control_post_wait, 0.0))
            try:
                final = control_script.exports_sync.status()
                write_host_event("control_final_status", state=final)
            except frida.InvalidOperationError as exc:
                write_host_event("control_final_status_error", error=repr(exc))
                raise
        time.sleep(max(end_time - time.monotonic(), 0.0))

    if args.no_unload:
        os._exit(0)
    if control_script is not None:
        try:
            control_script.unload()
        except frida.InvalidOperationError:
            pass
    try:
        script.unload()
    except frida.InvalidOperationError:
        pass
    try:
        session.detach()
    except frida.InvalidOperationError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
