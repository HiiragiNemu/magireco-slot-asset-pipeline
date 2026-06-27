#!/usr/bin/env python3
"""Reload the ARM64 Frida Gadget through the x86 Java attach surface.

The MuMu process is an x86_64 Android shell that runs the game ARM64 code
through native bridge.  The reliable recovery path observed in prior captures is:

1. use the x86 frida-server endpoint to attach to the app process;
2. run `inject_gadget.js`, which calls Android's runtime loader on
   `/data/user/0/com.universal777.magireco/files/libmagireco_gadget.so`;
3. verify that the app opens the Gadget listener and that the Gadget sees
   `libGameProc.so`.

This tool does not push files or kill/restart the app.  It assumes the Gadget
SO/config and the x86 frida-server endpoint already exist.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import frida


RELEVANT_MODULE_RE = re.compile(
    r"GameProc|AMAIN|ARES|openal|ogg|frida|gadget|libnb|libart|split_config|magireco",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--adb-serial", default="127.0.0.1:16384")
    parser.add_argument("--package", default="com.universal777.magireco")
    parser.add_argument("--frida", default="frida")
    parser.add_argument("--x86-host", default="127.0.0.1:27042")
    parser.add_argument("--gadget-host", default="127.0.0.1:27043")
    parser.add_argument(
        "--script",
        default=str(Path(__file__).with_name("inject_gadget.js")),
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def run_command(argv: list[str], timeout: float = 20.0) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        return {
            "argv": argv,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as error:  # pragma: no cover - diagnostic path
        return {"argv": argv, "error": repr(error), "stdout": "", "stderr": ""}


def adb_shell(adb: str, serial: str, command: str, timeout: float = 10.0) -> dict[str, Any]:
    return run_command([adb, "-s", serial, "shell", command], timeout=timeout)


def extract_pid(pidof_output: str) -> str:
    for token in pidof_output.split():
        if token.isdigit():
            return token
    return ""


def parse_port(host: str) -> str:
    if ":" not in host:
        raise ValueError(f"gadget host must include a port: {host}")
    return host.rsplit(":", 1)[1]


def inspect_gadget(host: str) -> dict[str, Any]:
    session: frida.core.Session | None = None
    script: frida.core.Script | None = None
    try:
        device = frida.get_device_manager().add_remote_device(host)
        processes = device.enumerate_processes()
        if not processes:
            return {"ok": False, "error": "no_process_exposed"}
        target = processes[0]
        session = device.attach(target.pid)
        script = session.create_script(
            """
setImmediate(function(){
  var all = Process.enumerateModules();
  var gameExport = Module.findGlobalExportByName("_ZN8CScnSlot4CalcEv");
  var gameProc = gameExport === null ?
    Process.findModuleByName("libGameProc.so") :
    Process.findModuleByAddress(gameExport);
  var modules = all.filter(function(m) {
    return /GameProc|AMAIN|ARES|openal|ogg|frida|gadget|libnb|libart|split_config|magireco/i
      .test(m.name + " " + m.path);
  }).map(function(m) {
    return {name:m.name, path:m.path, base:m.base.toString(), size:m.size};
  });
  send({kind:"gadget_probe", arch:Process.arch, platform:Process.platform,
        gameExport: gameExport === null ? null : gameExport.toString(),
        libGameProc: gameProc === null ? null :
          {name:gameProc.name, path:gameProc.path, base:gameProc.base.toString(), size:gameProc.size},
        module_count:all.length, modules:modules});
});
""",
            runtime="v8",
        )
        messages: list[dict[str, Any]] = []
        script.on("message", lambda message, data: messages.append(message))
        script.load()
        time.sleep(1.0)
        payloads = [msg.get("payload", {}) for msg in messages if msg.get("type") == "send"]
        payload = payloads[0] if payloads else {}
        module_texts = [
            f"{row.get('name', '')} {row.get('path', '')}"
            for row in payload.get("modules", [])
        ]
        lib_game_proc = payload.get("libGameProc")
        return {
            "ok": True,
            "target_pid": target.pid,
            "target_name": target.name,
            "arch": payload.get("arch", ""),
            "platform": payload.get("platform", ""),
            "module_count": payload.get("module_count", 0),
            "gameExport": payload.get("gameExport"),
            "libGameProc": lib_game_proc,
            "sees_libGameProc": bool(lib_game_proc)
            or any("libGameProc" in text for text in module_texts),
            "modules": payload.get("modules", []),
            "raw_messages": messages,
        }
    except Exception as error:
        return {"ok": False, "error": repr(error)}
    finally:
        if script is not None:
            try:
                script.unload()
            except Exception:
                pass
        if session is not None:
            try:
                session.detach()
            except Exception:
                pass


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pidof = adb_shell(args.adb, args.adb_serial, f"pidof {args.package}")
    pid = extract_pid(pidof.get("stdout", ""))
    if not pid:
        summary = {
            "ok": False,
            "pidof": pidof,
            "error": "app_process_not_found",
        }
        (out_dir / "gadget_reinject_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False))
        return 1

    log_path = out_dir / "gadget_reinject.log"
    frida_result = run_command(
        [
            args.frida,
            "-H",
            args.x86_host,
            "-p",
            pid,
            "-l",
            str(Path(args.script).resolve()),
            "-q",
            "-t",
            str(max(args.timeout, 1.0)),
            "-o",
            str(log_path),
        ],
        timeout=max(args.timeout + 15.0, 20.0),
    )
    listen = adb_shell(
        args.adb,
        args.adb_serial,
        f"su -c 'ss -lntp 2>/dev/null | grep {parse_port(args.gadget_host)} || true'",
    )
    gadget = inspect_gadget(args.gadget_host)
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    inject_text = "\n".join(
        [
            log_text,
            str(frida_result.get("stdout", "")),
            str(frida_result.get("stderr", "")),
        ]
    )
    inject_loaded = "gadget_loaded" in inject_text
    summary = {
        "ok": (
            frida_result.get("returncode") == 0
            and inject_loaded
            and bool(listen.get("stdout", "").strip())
            and gadget.get("ok")
            and gadget.get("sees_libGameProc")
        ),
        "package": args.package,
        "pid": pid,
        "x86_host": args.x86_host,
        "gadget_host": args.gadget_host,
        "inject_log": str(log_path),
        "inject_output_contains_loaded": inject_loaded,
        "frida_result": frida_result,
        "listen": listen,
        "gadget": gadget,
    }
    summary_path = out_dir / "gadget_reinject_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": summary["ok"],
                "pid": pid,
                "summary": str(summary_path),
                "log": str(log_path),
                "gadget_arch": gadget.get("arch", ""),
                "gadget_sees_libGameProc": gadget.get("sees_libGameProc", False),
            },
            ensure_ascii=False,
        )
    )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
