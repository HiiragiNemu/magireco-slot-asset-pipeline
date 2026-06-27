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
    r"GameProc|AMAIN|ARES|openal|ogg|frida|gadget|libnb|libart|split_config|magireco",
    re.IGNORECASE,
)
X86_REALMS: tuple[tuple[str, str | None], ...] = (
    ("default", None),
    ("native", "native"),
    ("emulated", "emulated"),
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


def parse_package_dump(stdout: str) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "primaryCpuAbi": "",
        "secondaryCpuAbi": "",
        "versionCode": "",
        "versionName": "",
        "pkgFlags": "",
        "privateFlags": "",
        "debuggable": False,
    }
    for line in stdout.splitlines():
        stripped = line.strip()
        for key in (
            "primaryCpuAbi",
            "secondaryCpuAbi",
            "versionCode",
            "versionName",
            "pkgFlags",
            "privateFlags",
        ):
            prefix = f"{key}="
            if stripped.startswith(prefix):
                fields[key] = stripped[len(prefix) :]
        if "DEBUGGABLE" in stripped or "debuggable=true" in stripped:
            fields["debuggable"] = True
    return fields


def try_gadget(host: str) -> dict[str, Any]:
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
            "process_count": len(processes),
            "processes": [{"pid": p.pid, "name": p.name} for p in processes[:20]],
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


def try_x86_attach(
    host: str, pid: int, *, realm_label: str, realm: str | None
) -> dict[str, Any]:
    session: frida.core.Session | None = None
    script: frida.core.Script | None = None
    try:
        device = frida.get_device_manager().add_remote_device(host)
        session = device.attach(pid, realm=realm)
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
  var hasJava = (typeof Java !== "undefined");
  var javaAvailable = false;
  var javaError = "";
  if (hasJava) {
    try {
      javaAvailable = Java.available;
    } catch (e) {
      javaError = e.toString();
    }
  }
  send({kind:"x86_attach_probe", arch:Process.arch, platform:Process.platform,
        gameExport: gameExport === null ? null : gameExport.toString(),
        libGameProc: gameProc === null ? null :
          {name:gameProc.name, path:gameProc.path, base:gameProc.base.toString(), size:gameProc.size},
        hasJava:hasJava, javaAvailable:javaAvailable, javaError:javaError,
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
            "realm": realm_label,
            "arch": payload.get("arch", ""),
            "platform": payload.get("platform", ""),
            "hasJava": payload.get("hasJava", False),
            "javaAvailable": payload.get("javaAvailable", False),
            "javaError": payload.get("javaError", ""),
            "module_count": payload.get("module_count", 0),
            "gameExport": payload.get("gameExport"),
            "libGameProc": lib_game_proc,
            "sees_libGameProc": bool(lib_game_proc)
            or any("libGameProc" in text for text in module_texts),
            "modules": payload.get("modules", []),
            "raw_messages": messages,
        }
    except Exception as error:
        return {"ok": False, "realm": realm_label, "error": repr(error)}
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


def try_x86_realms(host: str, pid: int) -> list[dict[str, Any]]:
    return [
        try_x86_attach(host, pid, realm_label=label, realm=realm)
        for label, realm in X86_REALMS
    ]


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
        f"- ro.debuggable: `{summary['device'].get('ro_debuggable', '').strip()}`",
        "",
        "## Package",
        "",
        f"- Version: `{summary['package_info'].get('versionName', '')}` (`{summary['package_info'].get('versionCode', '')}`)",
        f"- Primary ABI: `{summary['package_info'].get('primaryCpuAbi', '')}`",
        f"- Secondary ABI: `{summary['package_info'].get('secondaryCpuAbi', '')}`",
        f"- Debuggable: `{summary['package_info'].get('debuggable')}`",
        "",
        "## Frida surfaces",
        "",
        f"- Gadget `{summary['gadget_host']}` ok: `{summary['gadget'].get('ok')}`",
        f"- Gadget arch: `{summary['gadget'].get('arch', '')}`",
        f"- Gadget sees libGameProc: `{summary['gadget'].get('sees_libGameProc', '')}`",
        f"- x86 fallback `{summary['x86_host']}` default ok: `{summary['x86_attach'].get('ok')}`",
        f"- any x86 realm sees libGameProc: `{summary.get('x86_any_sees_libGameProc')}`",
        f"- any x86 realm exposes Java bridge: `{summary.get('x86_any_java_bridge')}`",
        "",
        "### x86 realm probes",
        "",
        "| realm | ok | arch | Java global | Java.available | sees libGameProc | error |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in summary.get("x86_attach_realms", []):
        error = str(result.get("error", "")).replace("|", "\\|")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{result.get('realm', '')}`",
                    f"`{result.get('ok')}`",
                    f"`{result.get('arch', '')}`",
                    f"`{result.get('hasJava', '')}`",
                    f"`{result.get('javaAvailable', '')}`",
                    f"`{result.get('sees_libGameProc', '')}`",
                    f"`{error}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
        "",
        "## Process maps",
        "",
        f"- contains libGameProc: `{summary['maps'].get('contains_libGameProc')}`",
        f"- contains Gadget/Frida: `{summary['maps'].get('contains_gadget')}`",
        f"- APK mapping count: `{summary['maps'].get('apk_mapping_count')}`",
        "",
        ]
    )
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
        "ro_debuggable": adb_shell(
            args.adb, args.adb_serial, "getprop ro.debuggable"
        ).get("stdout", ""),
    }
    package_dump = adb_shell(
        args.adb,
        args.adb_serial,
        f"dumpsys package {args.package}",
        timeout=20.0,
    )
    package_info = parse_package_dump(package_dump.get("stdout", ""))

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
    x86_attach_realms = (
        try_x86_realms(args.x86_host, int(pid))
        if pid and pid.isdigit()
        else [{"ok": False, "realm": label, "error": "pid_not_found"} for label, _ in X86_REALMS]
    )
    x86_attach = x86_attach_realms[0]
    maps_summary = summarize_maps(maps_lines)
    x86_any_sees_libGameProc = any(
        result.get("ok") and result.get("sees_libGameProc")
        for result in x86_attach_realms
    )
    x86_any_java_bridge = any(
        result.get("ok") and result.get("hasJava")
        for result in x86_attach_realms
    )

    if gadget.get("ok") and gadget.get("sees_libGameProc"):
        verdict = "runtime_capture_ready_via_arm64_gadget"
    elif gadget.get("ok"):
        verdict = "blocked_gadget_does_not_expose_game_code"
    elif x86_any_sees_libGameProc:
        verdict = "runtime_capture_possible_via_x86_realm"
    elif any(result.get("ok") for result in x86_attach_realms):
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
        "package_dump": package_dump,
        "package_info": package_info,
        "gadget_host": args.gadget_host,
        "x86_host": args.x86_host,
        "pidof": pidof,
        "maps": maps_summary,
        "gadget": gadget,
        "x86_attach": x86_attach,
        "x86_attach_realms": x86_attach_realms,
        "x86_any_sees_libGameProc": x86_any_sees_libGameProc,
        "x86_any_java_bridge": x86_any_java_bridge,
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
