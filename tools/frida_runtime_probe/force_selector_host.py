#!/usr/bin/env python3
"""Query and control the in-game force selector through the ARM64 Gadget."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import frida


ACTIONS = {
    "status": None,
    "debug-on": ("set_debug", True),
    "debug-off": ("set_debug", False),
    "java-debug-show": ("show_java_debug", True),
    "java-debug-hide": ("show_java_debug", False),
    "gate-on": ("set_manager_gate", True),
    "gate-off": ("set_manager_gate", False),
    "force-toggle": ("toggle_force", 2),
    "menu-toggle": ("toggle_menu", 2),
    "force-show": ("set_force_image", True),
    "force-hide": ("set_force_image", False),
    "force-visible": ("set_force_visible", True),
    "force-invisible": ("set_force_visible", False),
    "force-reset": ("reset_force_selection", 0),
    "force-select": ("select_force_index", None),
    "force-confirm": ("confirm_force_index", None),
    "body-bet": ("body_bet", 1),
    "body-lever": ("body_lever", 1),
    "body-left-reel": ("body_left_reel", 1),
    "body-center-reel": ("body_center_reel", 1),
    "body-right-reel": ("body_right_reel", 1),
    "gat-tick": ("gat_tick", 1),
    "gat-run": ("gat_drive", None),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=sorted(ACTIONS))
    parser.add_argument("--index", type=int)
    parser.add_argument("--frames", type=int)
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument(
        "--script",
        default=str(Path(__file__).with_name("force_selector_probe.js")),
    )
    parser.add_argument("--wait", type=float, default=1.5)
    parser.add_argument("--pre-wait", type=float)
    parser.add_argument("--post-wait", type=float)
    parser.add_argument("--out")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action in {"force-select", "force-confirm"} and args.index is None:
        raise SystemExit(f"--index is required for {args.action}")
    if args.action == "gat-run" and args.frames is None:
        raise SystemExit("--frames is required for gat-run")

    output_path = Path(args.out).resolve() if args.out else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    manager = frida.get_device_manager()
    device = manager.add_remote_device(args.host)
    processes = device.enumerate_processes()
    if not processes:
        raise RuntimeError(f"no process exposed by Gadget at {args.host}")

    target = processes[0]
    session = device.attach(target.pid)
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
    pre_wait = args.wait if args.pre_wait is None else args.pre_wait
    post_wait = args.wait if args.post_wait is None else args.post_wait
    time.sleep(max(pre_wait, 0.2))

    initial = script.exports_sync.status()
    record({"event": "initial_status", "state": initial})

    action_spec = ACTIONS[args.action]
    if action_spec is not None:
        action_name, action_value = action_spec
        if args.action in {"force-select", "force-confirm"}:
            action_value = args.index
        elif args.action == "gat-run":
            action_value = args.frames
        accepted = script.exports_sync.queue(action_name, action_value)
        record({"event": "action_queued", "result": accepted})
        time.sleep(max(post_wait, 0.2))

    final = script.exports_sync.status()
    record({"event": "final_status", "state": final})

    if output_path:
        with output_path.open("w", encoding="utf-8") as output:
            for item in records:
                output.write(json.dumps(item, ensure_ascii=False) + "\n")

    script.unload()
    session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
