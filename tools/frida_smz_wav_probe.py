#!/usr/bin/env python3
"""Probe the game's native WAV conversion exports through Frida.

This tool does not decode SMZ locally. It attaches to a running game process and
calls exported functions from libGameProc.so after the game's sound runtime has
initialized them.

Prerequisites:
- The game is running in the emulator.
- A matching frida-server is running on the Android side.
- The output directory is writable by the game process.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_PACKAGE = "com.universal777.magireco"
DEFAULT_OUTPUT_DIR = "/sdcard/Download/magireco_wav_probe"


FRIDA_SCRIPT = r"""
'use strict';

const LIB_NAME = 'libGameProc.so';

function ptrToString(p) {
  return p === null ? null : p.toString();
}

function findExport(name) {
  const module = Process.findModuleByName(LIB_NAME);
  if (module === null) {
    return null;
  }
  const exports = module.enumerateExports();
  for (const item of exports) {
    if (item.name === name) {
      return item.address;
    }
  }
  return null;
}

function ensureDir(path) {
  if (!Java.available) {
    return false;
  }
  let ok = false;
  Java.perform(function () {
    const File = Java.use('java.io.File');
    const f = File.$new(path);
    ok = f.exists() || f.mkdirs();
  });
  return ok;
}

function requireExport(name) {
  const p = findExport(name);
  if (p === null) {
    throw new Error('missing export: ' + name);
  }
  return p;
}

rpc.exports = {
  status: function () {
    const module = Process.findModuleByName(LIB_NAME);
    const byHash = findExport('zgSndCaptureConvertWavByHashCode');
    const raw = findExport('zgSndCaptureConvertWav');
    return {
      pid: Process.id,
      libGameProcBase: module === null ? null : ptrToString(module.base),
      convertByHashExport: ptrToString(byHash),
      convertRawExport: ptrToString(raw)
    };
  },

  convert_by_code: function (code, outputDir) {
    outputDir = outputDir || '/sdcard/Download/magireco_wav_probe';
    ensureDir(outputDir);
    const fn = new NativeFunction(
      requireExport('zgSndCaptureConvertWavByHashCode'),
      'int',
      ['pointer', 'pointer']
    );
    const codePtr = Memory.allocUtf8String(String(code));
    const outputDirPtr = Memory.allocUtf8String(String(outputDir));
    const ret = fn(codePtr, outputDirPtr);
    return {
      code: String(code),
      outputDir: String(outputDir),
      ret: ret,
      ok: (ret & 1) === 1
    };
  },

  convert_raw: function (mediaName, outputDir, outputStem) {
    outputDir = outputDir || '/sdcard/Download/magireco_wav_probe';
    outputStem = outputStem || mediaName;
    ensureDir(outputDir);
    const fn = new NativeFunction(
      requireExport('zgSndCaptureConvertWav'),
      'int',
      ['pointer', 'pointer', 'pointer']
    );
    const mediaPtr = Memory.allocUtf8String(String(mediaName));
    const outputDirPtr = Memory.allocUtf8String(String(outputDir));
    const stemPtr = Memory.allocUtf8String(String(outputStem));
    const ret = fn(mediaPtr, outputDirPtr, stemPtr);
    return {
      mediaName: String(mediaName),
      outputDir: String(outputDir),
      outputStem: String(outputStem),
      ret: ret,
      ok: (ret & 1) === 1
    };
  }
};
"""


def load_codes(args: argparse.Namespace) -> list[str]:
    codes: list[str] = []
    codes.extend(args.code or [])
    for path_text in args.codes_file or []:
        path = Path(path_text)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                codes.append(line)
    return codes


def get_device(args: argparse.Namespace):
    import frida

    if args.remote:
        return frida.get_device_manager().add_remote_device(args.remote)
    if args.usb:
        return frida.get_usb_device(timeout=args.timeout)
    return frida.get_local_device()


def attach_or_spawn(device, args: argparse.Namespace) -> tuple[int, bool]:
    if args.pid:
        return int(args.pid), False
    if args.spawn:
        pid = device.spawn([args.package])
        return pid, True
    try:
        applications = device.enumerate_applications()
    except Exception:
        applications = []
    for app in applications:
        identifier = getattr(app, "identifier", "")
        pid = int(getattr(app, "pid", 0) or 0)
        if identifier == args.package and pid:
            return pid, False
    processes = device.enumerate_processes()
    for process in processes:
        identifier = getattr(process, "identifier", "")
        if process.name == args.package or identifier == args.package:
            return process.pid, False
    raise SystemExit(f"process not found: {args.package}; start the game or pass --spawn")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe libGameProc SMZ/PCM WAV conversion exports through Frida.")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--spawn", action="store_true", help="spawn the package before attaching")
    parser.add_argument("--usb", action="store_true", help="use a USB/ADB Frida device")
    parser.add_argument("--remote", default="", help="connect to a Frida remote device, for example 127.0.0.1:27042")
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="device-side output directory")
    parser.add_argument("--code", action="append", help="sound code/hash to convert through zgSndCaptureConvertWavByHashCode")
    parser.add_argument("--codes-file", action="append", help="text file containing one sound code/hash per line")
    parser.add_argument("--raw-media", action="append", help="SMZ/PCM media name to pass to zgSndCaptureConvertWav")
    args = parser.parse_args()

    try:
        import frida  # noqa: F401
    except ImportError as exc:
        raise SystemExit("frida Python package is required: python -m pip install frida-tools") from exc

    device = get_device(args)
    pid, spawned = attach_or_spawn(device, args)
    session = device.attach(pid)
    script = session.create_script(FRIDA_SCRIPT)
    script.load()
    if spawned:
        device.resume(pid)

    status = script.exports_sync.status()
    print(json.dumps({"status": status}, ensure_ascii=False, indent=2))

    results = []
    for code in load_codes(args):
        results.append(script.exports_sync.convert_by_code(code, args.output_dir))
    for media_name in args.raw_media or []:
        stem = Path(media_name).stem
        results.append(script.exports_sync.convert_raw(media_name, args.output_dir, stem))

    if results:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    else:
        print("No --code/--codes-file/--raw-media supplied; status probe only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
