#!/usr/bin/env python3
"""Capture one provenance-complete, read-only addon entitlement snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

import frida


PACKAGE = "com.universal777.magireco"
EXPECTED_SCHEMA = "magireco-addon-entitlement-snapshot-v1"
EXPECTED_ACTIVE_OFFSETS = [0x14BF4 + index * 4 for index in range(7)]
EXPECTED_SAVED_OFFSETS = [0x14A58 + index * 4 for index in range(7)]
EXPECTED_ADDON_METADATA = [
    ("magireco_addon_01", "save_data", "operational_only"),
    ("magireco_addon_02", "wait_cut", "operational_only"),
    ("magireco_addon_03", "settings_change", "route_probability_control"),
    ("magireco_addon_04", "auto_play", "operational_only"),
    ("magireco_addon_05", "forced_role", "forced_route_control"),
    ("magireco_addon_06", "value_pack", "bundle_indices_0_through_4"),
    ("magireco_addon_07", "sound_pack", "audio_playback_gate"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def run_command(argv: Sequence[str], *, timeout: float = 30.0) -> str:
    completed = subprocess.run(
        list(argv),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return completed.stdout.strip()


def parse_single_pid(value: str) -> int:
    values = [int(token) for token in re.findall(r"\b\d+\b", value)]
    if len(values) != 1:
        raise ValueError(f"expected exactly one PID, got {values!r}")
    return values[0]


def parse_hex(value: Any) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError(f"expected hexadecimal string, got {value!r}")
    return int(value, 16)


def validate_snapshot(snapshot: dict[str, Any], expected_pid: int) -> None:
    if snapshot.get("schema") != EXPECTED_SCHEMA:
        raise ValueError(f"unexpected snapshot schema: {snapshot.get('schema')!r}")
    if snapshot.get("ok") is not True:
        raise ValueError(f"probe did not complete every fixed read: {snapshot!r}")
    process = snapshot.get("process")
    if not isinstance(process, dict) or int(process.get("id", -1)) != expected_pid:
        raise ValueError(f"snapshot PID does not match expected PID {expected_pid}: {process!r}")
    if process.get("arch") != "arm64":
        raise ValueError(f"snapshot did not run in ARM64 game realm: {process!r}")
    rows = snapshot.get("rows")
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError(f"snapshot must contain exactly seven addon rows: {rows!r}")
    if [int(row.get("index", -1)) for row in rows] != list(range(7)):
        raise ValueError("addon row indices are incomplete or out of order")
    metadata = [
        (
            str(row.get("sku", "")),
            str(row.get("label", "")),
            str(row.get("archive_impact", "")),
        )
        for row in rows
    ]
    if metadata != EXPECTED_ADDON_METADATA:
        raise ValueError("addon row SKU/label/archive-impact mapping is not version-audited")
    active_offsets = [parse_hex(row.get("active_offset")) for row in rows]
    saved_offsets = [parse_hex(row.get("saved_offset")) for row in rows]
    if active_offsets != EXPECTED_ACTIVE_OFFSETS or saved_offsets != EXPECTED_SAVED_OFFSETS:
        raise ValueError("addon offsets do not match the version-specific fixed-field layout")
    for row in rows:
        if row.get("active_read_error") or row.get("saved_read_error"):
            raise ValueError(f"addon row contains a read error: {row!r}")
        if not isinstance(row.get("active_u32"), int) or not isinstance(row.get("saved_u32"), int):
            raise ValueError(f"addon row value is not an integer: {row!r}")
    if snapshot.get("read_policy") != "seven_named_u32_active_and_saved_fields_no_calls_no_writes":
        raise ValueError("probe did not declare the required read-only policy")
    if snapshot.get("addon_index_map_basis") != (
        "java_sku_order_plus_CplayData_SetAddonID_and_native_xrefs"
    ):
        raise ValueError("addon index map lacks the required static provenance")
    if snapshot.get("value_pack_policy") != (
        "index_5_sets_indices_0_through_5_but_not_index_6"
    ):
        raise ValueError("Value Pack policy mismatch")


def adb_state(adb: str, device: str, package: str) -> dict[str, Any]:
    prefix = [adb, "-s", device]
    device_state = run_command([*prefix, "get-state"])
    pid = parse_single_pid(run_command([*prefix, "shell", "pidof", package]))
    activities = run_command([*prefix, "shell", "dumpsys", "activity", "activities"])
    foreground_lines = [
        line.strip()
        for line in activities.splitlines()
        if package in line and ("mResumedActivity" in line or "topResumedActivity" in line)
    ]
    package_dump = run_command([*prefix, "shell", "dumpsys", "package", package])
    version_lines = [
        line.strip()
        for line in package_dump.splitlines()
        if "versionCode=" in line or "versionName=" in line
    ][:4]
    return {
        "device_state": device_state,
        "pid": pid,
        "foreground_lines": foreground_lines,
        "version_lines": version_lines,
    }


def parse_args() -> argparse.Namespace:
    probe = Path(__file__).with_name("addon_entitlement_state_probe.js")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--expected-pid", required=True, type=int)
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--device", default="emulator-5554")
    parser.add_argument("--package", default=PACKAGE)
    parser.add_argument("--probe", type=Path, default=probe)
    parser.add_argument("--native-lib", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    if out_dir.exists():
        raise FileExistsError(f"refusing to reuse evidence directory: {out_dir}")
    probe_path = args.probe.resolve()
    if not probe_path.is_file():
        raise FileNotFoundError(probe_path)
    if args.native_lib is not None and not args.native_lib.resolve().is_file():
        raise FileNotFoundError(args.native_lib.resolve())

    before = adb_state(args.adb, args.device, args.package)
    if before["pid"] != args.expected_pid:
        raise RuntimeError(
            f"ADB PID changed before attach: expected {args.expected_pid}, got {before['pid']}"
        )
    if not before["foreground_lines"]:
        raise RuntimeError(f"package {args.package} is not the resumed foreground activity")

    source = probe_path.read_text(encoding="utf-8")
    manager = frida.get_device_manager()
    device = manager.add_remote_device(args.host)
    processes = device.enumerate_processes()
    targets = [process for process in processes if int(process.pid) == args.expected_pid]
    if len(targets) != 1:
        visible = [(int(process.pid), process.name) for process in processes]
        raise RuntimeError(
            f"Gadget did not expose expected PID {args.expected_pid}; visible={visible!r}"
        )
    target = targets[0]
    messages: list[dict[str, Any]] = []
    session = device.attach(args.expected_pid)
    script = session.create_script(source)

    def on_message(message: dict[str, Any], data: bytes | None) -> None:
        messages.append(
            {
                "host_unix_ms": int(time.time() * 1000),
                "message": message,
                "data_length": len(data) if data else 0,
            }
        )

    script.on("message", on_message)
    try:
        script.load()
        snapshot = script.exports_sync.snapshot()
        if not isinstance(snapshot, dict):
            raise TypeError(f"probe RPC did not return an object: {snapshot!r}")
        validate_snapshot(snapshot, args.expected_pid)
    finally:
        try:
            script.unload()
        except Exception:
            pass
        try:
            session.detach()
        except Exception:
            pass

    after = adb_state(args.adb, args.device, args.package)
    if after["pid"] != args.expected_pid:
        raise RuntimeError(
            f"ADB PID changed during snapshot: expected {args.expected_pid}, got {after['pid']}"
        )

    out_dir.mkdir(parents=True, exist_ok=False)
    snapshot_path = out_dir / "addon_entitlement_snapshot.json"
    raw_path = out_dir / "probe_messages.jsonl"
    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    raw_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in messages),
        encoding="utf-8",
    )
    sources: dict[str, Any] = {
        "capture_driver": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "probe": {"path": str(probe_path), "sha256": sha256_file(probe_path)},
    }
    if args.native_lib is not None:
        native_lib = args.native_lib.resolve()
        sources["version_matched_native_lib"] = {
            "path": str(native_lib),
            "bytes": native_lib.stat().st_size,
            "sha256": sha256_file(native_lib),
        }
    manifest = {
        "schema": "magireco-addon-entitlement-capture-v1",
        "created_host_unix_ms": int(time.time() * 1000),
        "package": args.package,
        "device": args.device,
        "gadget_host": args.host,
        "expected_pid": args.expected_pid,
        "frida_target": {"pid": int(target.pid), "name": target.name},
        "adb_before": before,
        "adb_after": after,
        "gameplay_input_sent": False,
        "memory_write_performed": False,
        "native_function_called": False,
        "entitlement_modified": False,
        "snapshot": snapshot,
        "source_hashes": sources,
        "output_hashes": {
            "addon_entitlement_snapshot.json": sha256_file(snapshot_path),
            "probe_messages.jsonl": sha256_file(raw_path),
        },
    }
    manifest_path = out_dir / "capture_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checksums = {
        "capture_manifest.json": sha256_file(manifest_path),
        **manifest["output_hashes"],
    }
    (out_dir / "sha256sums.json").write_text(
        json.dumps(checksums, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"out_dir": str(out_dir), "snapshot": snapshot, "sha256": checksums}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
