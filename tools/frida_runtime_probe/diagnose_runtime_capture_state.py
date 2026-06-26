#!/usr/bin/env python3
"""Diagnose whether the current emulator can produce trusted runtime captures.

The MagiaReco slot app runs as an x86_64 Android process while the game native
code is mapped through an ARM64 native bridge.  A normal x86_64 frida-server can
attach to the Java/process shell but cannot instrument ARM64 `libGameProc.so`.
Trusted event capture therefore requires the ARM64 Frida Gadget endpoint.

This script is intentionally read-only: it checks ADB state, process maps,
Gadget reachability, and the x86_64 fallback attach surface, then emits a
machine-readable diagnosis.
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
    r"GameProc|AMAIN|ARES|openal|ogg|frida|gadget|libnb|split_config|magireco",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--adb-serial", default="127.0.0.1:16384")
    parser.add_argument("--package", default="com.universal777.magireco")
    parser.add_argument("--pid", default="")
    parser.add_argument("--gadget-host", default="127.0.0.1:27043")
    parser.add_argument("--x86-host", default="127.0.0.1:27042")
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def run_command(argv: list[str], timeout: float = 10.0) -> dict[str, Any]:
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


def split_maps(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.strip()]


def summarize_maps(lines: list[str]) -> dict[str, Any]:
    relevant = [line for line in lines if RELEVANT_MODULE_RE.search(line)]
    apk_mappings = [line for line in lines if "/data/app/" in line]
    return {
        "line_count": len(lines),
        "contains_libGameProc": any("libGameProc" in line for line in lines),
        "contains_gadget": any(
            "frida" in line.lower() or "gadget" in line.lower() for line in lines
        ),
        "apk_mapping_count": len(apk_mappings),
        "relevant_mappings": relevant[:120],
    }


def try_gadget(host: str) -> dict[str, Any]:
    try:
        device = frida.get_device_manager().add_remote_device(host)
        processes = device.enumerate_processes()
        return {
            "ok": True,
            "process_count": len(processes),
            "processes": [{"pid": p.pid, "name": p.name} for p in processes[:20]],
        }
    except Exception as error:
        return {"ok": False, "error": repr(error)}


def try_x86_attach(host: str, pid: int) -> dict[str, Any]:
    try:
        device = frida.get_device_manager().add_remote_device(host)
        session = device.attach(pid)
        script = session.create_script(
            """
setImmediate(function(){
  var all = Process.enumerateModules();
  var modules = all.filter(function(m) {
    return /GameProc|AMAIN|ARES|openal|ogg|frida|gadget|libnb|split_config|magireco/i
      .test(m.name + " " + m.path);
  }).map(function(m) {
    return {name:m.name, path:m.path, base:m.base.toString(), size:m.size};
  });
  send({kind:"x86_attach_probe", arch:Process.arch, platform:Process.platform,
        module_count:all.length, modules:modules});
});
"""
        )
        messages: list[dict[str, Any]] = []
        script.on("message", lambda message, data: messages.append(message))
        script.load()
        time.sleep(1.0)
        script.unload()
        session.detach()
        payloads = [msg.get("payload", {}) for msg in messages if msg.get("type") == "send"]
        payload = payloads[0] if payloads else {}
        module_names = [row.get("name", "") for row in payload.get("modules", [])]
        return {
            "ok": True,
            "arch": payload.get("arch", ""),
            "platform": payload.get("platform", ""),
            "module_count": payload.get("module_count", 0),
            "sees_libGameProc": any("libGameProc" in name for name in module_names),
            "modules": payload.get("modules", []),
            "raw_messages": messages,
        }
    except Exception as error:
        return {"ok": False, "error": repr(error)}


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Runtime capture state diagnosis",
        "",
        f"- Package: `{summary['package']}`",
        f"- ADB serial: `{summary['adb_serial']}`",
        f"- PID: `{summary.get('pid') or 'not found'}`",
        f"- Verdict: `{summary['verdict']}`",
        "",
        "## Device",
        "",
        f"- ABI: `{summary['device'].get('abi', '').strip()}`",
        f"- Native bridge: `{summary['device'].get('native_bridge', '').strip()}`",
        f"- Kernel arch: `{summary['device'].get('uname_m', '').strip()}`",
        "",
        "## Frida surfaces",
        "",
        f"- Gadget `{summary['gadget_host']}` ok: `{summary['gadget'].get('ok')}`",
        f"- x86 fallback `{summary['x86_host']}` ok: `{summary['x86_attach'].get('ok')}`",
        f"- x86 arch: `{summary['x86_attach'].get('arch', '')}`",
        f"- x86 sees libGameProc: `{summary['x86_attach'].get('sees_libGameProc', '')}`",
        "",
        "## Process maps",
        "",
        f"- contains libGameProc: `{summary['maps'].get('contains_libGameProc')}`",
        f"- contains Gadget/Frida: `{summary['maps'].get('contains_gadget')}`",
        f"- APK mapping count: `{summary['maps'].get('apk_mapping_count')}`",
        "",
    ]
    if not summary["gadget"].get("ok"):
        lines.extend(
            [
                "## Gadget error",
                "",
                f"`{summary['gadget'].get('error', '')}`",
                "",
            ]
        )
    if not summary["x86_attach"].get("ok"):
        lines.extend(
            [
                "## x86 attach error",
                "",
                f"`{summary['x86_attach'].get('error', '')}`",
                "",
            ]
        )
    lines.extend(["## Relevant mappings", ""])
    for line in summary["maps"].get("relevant_mappings", [])[:80]:
        lines.append(f"- `{line}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pid = args.pid
    pidof = adb_shell(args.adb, args.adb_serial, f"pidof {args.package}")
    if not pid:
        pid = extract_pid(pidof.get("stdout", ""))

    device = {
        "abi": adb_shell(args.adb, args.adb_serial, "getprop ro.product.cpu.abi").get(
            "stdout", ""
        ),
        "native_bridge": adb_shell(
            args.adb, args.adb_serial, "getprop ro.dalvik.vm.native.bridge"
        ).get("stdout", ""),
        "uname_m": adb_shell(args.adb, args.adb_serial, "uname -m").get("stdout", ""),
    }

    maps_lines: list[str] = []
    if pid:
        maps = adb_shell(
            args.adb,
            args.adb_serial,
            f"su -c 'cat /proc/{pid}/maps'",
            timeout=20.0,
        )
        maps_lines = split_maps(maps.get("stdout", ""))

    gadget = try_gadget(args.gadget_host)
    x86_attach = (
        try_x86_attach(args.x86_host, int(pid))
        if pid and pid.isdigit()
        else {"ok": False, "error": "pid_not_found"}
    )
    maps_summary = summarize_maps(maps_lines)

    if gadget.get("ok"):
        verdict = "runtime_capture_ready_via_arm64_gadget"
    elif x86_attach.get("ok") and not x86_attach.get("sees_libGameProc"):
        verdict = "blocked_x86_frida_cannot_see_arm64_game_code"
    elif not pid:
        verdict = "blocked_app_process_not_found"
    else:
        verdict = "blocked_runtime_capture_surface_unavailable"

    summary = {
        "package": args.package,
        "adb_serial": args.adb_serial,
        "pid": pid,
        "device": device,
        "gadget_host": args.gadget_host,
        "x86_host": args.x86_host,
        "pidof": pidof,
        "maps": maps_summary,
        "gadget": gadget,
        "x86_attach": x86_attach,
        "verdict": verdict,
    }
    json_path = out_dir / "runtime_capture_state.json"
    md_path = out_dir / "runtime_capture_state.md"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(md_path, summary)
    print(json.dumps({"verdict": verdict, "json": str(json_path), "report": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
