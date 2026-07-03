#!/usr/bin/env python3
"""Run an auditable slot force-kind mapping scan.

The scan intentionally records runtime evidence instead of visual guesses:

1. prepare a clean/ready slot state;
2. start an independent CSL/SP Story observer;
3. trigger ``body-force-next-lever`` for one force kind;
4. tap the reel stop buttons through Android input;
5. summarize force calls, event-code requests, SP Story state, and final audio
   queue chunks.

This is a diagnostic mapping tool.  A hit here is evidence for mechanism
research, not by itself approval for final Bilibili publication.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PACKAGE = "com.universal777.magireco"
DEFAULT_TARGET_CODES = {
    "0x4f71466b3d723041",  # ac7114_001
    "0x5773382374447854",  # ac7115_001
    "0x4c792a5a74447854",  # ac7115_013
    "0x2476304366614152",  # ac7116_001
}


def parse_candidates(text: str) -> list[int]:
    result: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            step = 1 if end >= start else -1
            result.extend(range(start, end + step, step))
        else:
            result.append(int(part))
    seen: set[int] = set()
    unique: list[int] = []
    for value in result:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_event_info_csv() -> Path | None:
    candidates = [
        Path(r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manifests\event_info.csv"),
        Path(r"A:\magireco_corrected_research_20260612\manifests\event_info.csv"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def load_event_info(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = (row.get("code_hex") or "").lower()
            scene = row.get("scene_name") or row.get("base_name") or ""
            if code and scene:
                mapping[code] = scene
    return mapping


def run_command(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    timeout: float | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    elapsed = time.time() - started
    log_path.write_text(
        "\n".join(
            [
                "COMMAND:",
                json.dumps(command, ensure_ascii=False),
                f"EXIT_CODE: {proc.returncode}",
                f"ELAPSED_SECONDS: {elapsed:.3f}",
                "OUTPUT:",
                proc.stdout,
            ]
        ),
        encoding="utf-8",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(command)}; see {log_path}")
    return proc


def run_binary_command(
    command: list[str],
    *,
    cwd: Path,
    output_path: Path,
    log_path: Path,
    timeout: float | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed = time.time() - started
    output_path.write_bytes(proc.stdout)
    log_path.write_text(
        "\n".join(
            [
                "COMMAND:",
                json.dumps(command, ensure_ascii=False),
                f"EXIT_CODE: {proc.returncode}",
                f"ELAPSED_SECONDS: {elapsed:.3f}",
                "STDERR:",
                proc.stderr.decode("utf-8", errors="replace"),
            ]
        ),
        encoding="utf-8",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"binary command failed ({proc.returncode}): {' '.join(command)}; see {log_path}")
    return proc


def adb_command(device: str, *args: str) -> list[str]:
    return ["adb", "-s", device, *args]


def run_control(
    action: str,
    *,
    out_file: Path,
    log_file: Path,
    cwd: Path,
    index: int | None = None,
    wait: float = 0.8,
    extra: list[str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "tools/frida_runtime_probe/force_selector_host.py",
        action,
        "--wait",
        str(wait),
        "--out",
        str(out_file),
    ]
    if index is not None:
        command.extend(["--index", str(index)])
    if extra:
        command.extend(extra)
    return run_command(command, cwd=cwd, log_path=log_file, timeout=45, check=check)


def parse_last_final_status(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    final: dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "final_status":
                state = record.get("state")
                if isinstance(state, dict):
                    final = state
    return final


def prepare_ready_state(kind_dir: Path, cwd: Path) -> dict[str, Any] | None:
    steps = [
        ("body-force-main", -1, 0.3),
        ("body-force-sub", 0, 0.3),
        ("body-force-param", 0, 0.3),
        ("body-bet", None, 1.0),
        ("status", None, 1.0),
    ]
    final_state: dict[str, Any] | None = None
    for index, (action, value, wait) in enumerate(steps, start=1):
        out_file = kind_dir / f"ready_{index:02d}_{action}.jsonl"
        log_file = kind_dir / f"ready_{index:02d}_{action}.log"
        run_control(action, out_file=out_file, log_file=log_file, cwd=cwd, index=value, wait=wait)
        final_state = parse_last_final_status(out_file) or final_state
    return final_state


def restart_and_reinject(kind_dir: Path, cwd: Path, device: str, startup_wait: float) -> None:
    run_command(
        adb_command(device, "shell", "am", "force-stop", PACKAGE),
        cwd=cwd,
        log_path=kind_dir / "restart_01_force_stop.log",
        timeout=30,
    )
    time.sleep(1.0)
    run_command(
        adb_command(device, "shell", "monkey", "-p", PACKAGE, "1"),
        cwd=cwd,
        log_path=kind_dir / "restart_02_monkey_start.log",
        timeout=30,
    )
    time.sleep(startup_wait)
    run_command(
        adb_command(device, "shell", "pidof", PACKAGE),
        cwd=cwd,
        log_path=kind_dir / "restart_03_pidof.log",
        timeout=30,
    )
    run_command(
        adb_command(device, "forward", "tcp:27042", "tcp:27042"),
        cwd=cwd,
        log_path=kind_dir / "restart_04_forward_frida_server.log",
        timeout=30,
    )
    run_command(
        [
            sys.executable,
            "tools/frida_runtime_probe/reinject_gadget.py",
            "--out-dir",
            str(kind_dir / "gadget_reinject"),
        ],
        cwd=cwd,
        log_path=kind_dir / "restart_05_reinject_gadget.log",
        timeout=120,
    )
    run_command(
        adb_command(device, "forward", "tcp:27043", "tcp:27043"),
        cwd=cwd,
        log_path=kind_dir / "restart_06_forward_gadget.log",
        timeout=30,
    )


def tap_title_entry_sequence(kind_dir: Path, cwd: Path, args: argparse.Namespace, attempt: int) -> None:
    run_command(
        adb_command(
            args.device,
            "shell",
            "input",
            "tap",
            str(args.simulation_tap_x),
            str(args.simulation_tap_y),
        ),
        cwd=cwd,
        log_path=kind_dir / f"enter_simulation_tap_{attempt:02d}.log",
        timeout=20,
        check=False,
    )
    time.sleep(args.post_simulation_tap_wait)
    run_command(
        adb_command(
            args.device,
            "shell",
            "input",
            "tap",
            str(args.game_start_tap_x),
            str(args.game_start_tap_y),
        ),
        cwd=cwd,
        log_path=kind_dir / f"enter_game_start_tap_{attempt:02d}.log",
        timeout=20,
        check=False,
    )


def wait_for_slot_body(args: argparse.Namespace, kind_dir: Path, cwd: Path) -> dict[str, Any]:
    last_state: dict[str, Any] | None = None
    for attempt in range(1, args.ready_retries + 1):
        status_file = kind_dir / f"slot_wait_status_{attempt:02d}.jsonl"
        run_control(
            "status",
            out_file=status_file,
            log_file=kind_dir / f"slot_wait_status_{attempt:02d}.log",
            cwd=cwd,
            wait=1.0,
            check=False,
        )
        last_state = parse_last_final_status(status_file) or last_state
        if last_state and last_state.get("slot_pointer") and last_state.get("slot_body_pointer"):
            return last_state
        if args.enter_simulation:
            tap_title_entry_sequence(kind_dir, cwd, args, attempt)
        time.sleep(args.ready_retry_wait)
    raise RuntimeError(f"slot/body pointer was not observed after {args.ready_retries} retries: {last_state}")


def tap_reel_stops(kind_dir: Path, cwd: Path, device: str, rounds: int, delay_s: float) -> None:
    coords = [("880", "2860"), ("1160", "2860"), ("1440", "2860")]
    for round_index in range(rounds):
        for x, y in coords:
            run_command(
                adb_command(device, "shell", "input", "tap", x, y),
                cwd=cwd,
                log_path=kind_dir / f"tap_round_{round_index + 1:02d}_{x}_{y}.log",
                timeout=20,
                check=False,
            )
            time.sleep(delay_s)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize_candidate(
    *,
    kind: int,
    kind_dir: Path,
    event_map: dict[str, str],
    target_codes: set[str],
    final_state: dict[str, Any] | None,
) -> dict[str, Any]:
    summary_json = kind_dir / "summary_v1" / "summary.json"
    summary = json.loads(summary_json.read_text(encoding="utf-8")) if summary_json.exists() else {}
    runtime = summary.get("runtime", {})
    csl = summary.get("csl", {})

    event_rows = read_csv_rows(kind_dir / "summary_v1" / "runtime_event_codes.csv")
    force_rows = read_csv_rows(kind_dir / "summary_v1" / "runtime_force_calls.csv")
    sp_story_rows = read_csv_rows(kind_dir / "summary_v1" / "runtime_sp_story_state.csv")
    gr_dir_rows = read_csv_rows(kind_dir / "summary_v1" / "runtime_gr_dir_prm_copy.csv")
    rxcom_rows = read_csv_rows(kind_dir / "summary_v1" / "runtime_rxcom_dir_flow.csv")
    queue_rows = read_csv_rows(kind_dir / "summary_v1" / "csl_queue_chunks.csv")

    event_codes = sorted(
        {
            (row.get("event_code") or "").lower()
            for row in event_rows
            if row.get("event_code")
        }
    )
    sp_base_codes = sorted(
        {
            (row.get("base_event_code_hex_at_0x358") or "").lower()
            for row in sp_story_rows
            if row.get("base_event_code_hex_at_0x358")
        }
    )
    observed_sound_ids = sorted(
        {
            int(row["sound_id_u16_at_0x2"])
            for row in queue_rows
            if (row.get("sound_id_u16_at_0x2") or "").isdigit()
        }
    )
    mapped_event_codes = {
        code: event_map.get(code, "")
        for code in sorted(set(event_codes) | set(sp_base_codes))
    }
    force_set_rows = [
        row
        for row in force_rows
        if row.get("kind") in {"force_flag_set", "force_flag_set_return", "force_flag_get_kind_return"}
    ]
    gr_sdgm_source_story_numbers = sorted(
        {
            row.get("sdgm_source_story_no_u16_at_0x788") or ""
            for row in gr_dir_rows
            if row.get("sdgm_source_story_no_u16_at_0x788")
        }
    )
    gr_mst_source_story_numbers = sorted(
        {
            row.get("mst_source_story_no_u16_at_0x2378") or ""
            for row in gr_dir_rows
            if row.get("mst_source_story_no_u16_at_0x2378")
        }
    )
    rxcom_source_stage_numbers = sorted(
        {
            row.get("sdgm_rx_source_stage_u16_at_0x170") or ""
            for row in rxcom_rows
            if row.get("sdgm_rx_source_stage_u16_at_0x170")
        }
    )
    rxcom_source_selector_numbers = sorted(
        {
            row.get("sdgm_rx_source_selector_u16_at_0x16e") or ""
            for row in rxcom_rows
            if row.get("sdgm_rx_source_selector_u16_at_0x16e")
        }
    )
    rxcom_payload_stage_numbers = sorted(
        {
            row.get("rxcom_dirinfo8_stage_from_payload_u8_at_4") or ""
            for row in rxcom_rows
            if row.get("rxcom_dirinfo8_stage_from_payload_u8_at_4")
        }
    )
    rxcom_payload_selector_numbers = sorted(
        {
            row.get("rxcom_dirinfo8_selector_from_payload_u8_at_5") or ""
            for row in rxcom_rows
            if row.get("rxcom_dirinfo8_selector_from_payload_u8_at_5")
        }
    )
    return {
        "kind": kind,
        "path": str(kind_dir),
        "final_state": final_state or {},
        "event_codes": event_codes,
        "sp_story_base_codes": sp_base_codes,
        "mapped_event_codes": mapped_event_codes,
        "hit_target_event": bool((set(event_codes) | set(sp_base_codes)) & target_codes),
        "sp_story_state_count": runtime.get("sp_story_state_count", 0),
        "gr_dir_prm_copy_count": runtime.get("gr_dir_prm_copy_count", 0),
        "rxcom_dir_flow_count": runtime.get("rxcom_dir_flow_count", 0),
        "gr_copy_sdgm_source_story_numbers": gr_sdgm_source_story_numbers,
        "gr_copy_mst_source_story_numbers": gr_mst_source_story_numbers,
        "rxcom_source_stage_numbers": rxcom_source_stage_numbers,
        "rxcom_source_selector_numbers": rxcom_source_selector_numbers,
        "rxcom_payload_stage_numbers": rxcom_payload_stage_numbers,
        "rxcom_payload_selector_numbers": rxcom_payload_selector_numbers,
        "force_call_count": runtime.get("force_call_count", 0),
        "csl_queue_chunk_count": csl.get("queue_chunk_count", 0),
        "observed_sound_ids": observed_sound_ids,
        "force_set_rows": force_set_rows,
    }


def run_one_candidate(args: argparse.Namespace, cwd: Path, event_map: dict[str, str], kind: int) -> dict[str, Any]:
    kind_dir = args.out_dir / f"force_kind_{kind:02d}_postclear_scan"
    kind_dir.mkdir(parents=True, exist_ok=True)
    if args.restart_each:
        restart_and_reinject(kind_dir, cwd, args.device, args.startup_wait)
    else:
        run_command(
            adb_command(args.device, "forward", "tcp:27043", "tcp:27043"),
            cwd=cwd,
            log_path=kind_dir / "forward_gadget.log",
            timeout=30,
            check=False,
        )

    wait_for_slot_body(args, kind_dir, cwd)
    ready_state = prepare_ready_state(kind_dir, cwd)
    if not ready_state or not ready_state.get("slot_pointer") or not ready_state.get("slot_body_pointer"):
        raise RuntimeError(f"ready preparation did not observe slot/body pointers: {ready_state}")
    if ready_state.get("body_state") != 1 or ready_state.get("body_mode") != 1 or ready_state.get("body_bet") != 3:
        for retry in range(1, args.bet_retries + 1):
            run_control(
                "body-bet",
                out_file=kind_dir / f"ready_retry_bet_{retry:02d}.jsonl",
                log_file=kind_dir / f"ready_retry_bet_{retry:02d}.log",
                cwd=cwd,
                wait=1.0,
                check=False,
            )
            run_control(
                "status",
                out_file=kind_dir / f"ready_retry_status_{retry:02d}.jsonl",
                log_file=kind_dir / f"ready_retry_status_{retry:02d}.log",
                cwd=cwd,
                wait=1.0,
                check=False,
            )
            ready_state = parse_last_final_status(kind_dir / f"ready_retry_status_{retry:02d}.jsonl") or ready_state
            if ready_state.get("body_state") == 1 and ready_state.get("body_mode") == 1 and ready_state.get("body_bet") == 3:
                break
    if ready_state.get("body_state") != 1 or ready_state.get("body_mode") != 1 or ready_state.get("body_bet") != 3:
        raise RuntimeError(f"slot did not reach ready bet state before trigger: {ready_state}")
    (kind_dir / "ready_state.json").write_text(
        json.dumps(ready_state or {}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    observer_jsonl = kind_dir / "observer_csl.jsonl"
    observer_log = (kind_dir / "observer_console.log").open("w", encoding="utf-8", buffering=1)
    observer = subprocess.Popen(
        [
            sys.executable,
            "tools/frida_runtime_probe/runtime_probe_host.py",
            "--script",
            "tools/frida_runtime_probe/csl_audio_queue_probe.js",
            "--out",
            str(observer_jsonl),
            "--duration",
            str(args.duration),
            "--quiet",
        ],
        cwd=str(cwd),
        stdout=observer_log,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        time.sleep(args.observer_warmup)
        run_control(
            "body-force-next-lever",
            out_file=kind_dir / "trigger_body_force_next_lever.jsonl",
            log_file=kind_dir / "trigger_body_force_next_lever.log",
            cwd=cwd,
            index=kind,
            wait=args.trigger_wait,
        )
        time.sleep(args.stop_wait)
        tap_reel_stops(kind_dir, cwd, args.device, args.stop_rounds, args.tap_delay)
        run_binary_command(
            adb_command(args.device, "exec-out", "screencap", "-p"),
            cwd=cwd,
            output_path=kind_dir / "screen_after_trigger.png",
            log_path=kind_dir / "screen_after_trigger.log",
            timeout=30,
            check=False,
        )
        try:
            observer.wait(timeout=args.duration + 20)
        except subprocess.TimeoutExpired:
            observer.terminate()
            observer.wait(timeout=10)
    finally:
        observer_log.close()

    run_command(
        [
            sys.executable,
            "tools/frida_runtime_probe/summarize_runtime_audio_capture.py",
            "--runtime-jsonl",
            str(observer_jsonl),
            "--csl-jsonl",
            str(observer_jsonl),
            "--out-dir",
            str(kind_dir / "summary_v1"),
        ],
        cwd=cwd,
        log_path=kind_dir / "summary_v1.log",
        timeout=120,
    )
    run_control(
        "status",
        out_file=kind_dir / "final_status.jsonl",
        log_file=kind_dir / "final_status.log",
        cwd=cwd,
        wait=1.0,
        check=False,
    )
    final_state = parse_last_final_status(kind_dir / "final_status.jsonl")
    candidate_summary = summarize_candidate(
        kind=kind,
        kind_dir=kind_dir,
        event_map=event_map,
        target_codes={code.lower() for code in args.target_codes},
        final_state=final_state,
    )
    (kind_dir / "candidate_summary.json").write_text(
        json.dumps(candidate_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return candidate_summary


def write_overall(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "force_kind_scan_summary.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_path = out_dir / "force_kind_scan_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "kind",
            "error",
            "hit_target_event",
            "sp_story_state_count",
            "gr_dir_prm_copy_count",
            "gr_copy_sdgm_source_story_numbers",
            "gr_copy_mst_source_story_numbers",
            "event_codes",
            "mapped_event_codes",
            "observed_sound_ids",
            "final_body_state",
            "final_body_mode",
            "final_body_bet",
            "final_body_credit",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            final_state = row.get("final_state") or {}
            writer.writerow(
                {
                    "kind": row.get("kind"),
                    "error": row.get("error", ""),
                    "hit_target_event": row.get("hit_target_event"),
                    "sp_story_state_count": row.get("sp_story_state_count"),
                    "gr_dir_prm_copy_count": row.get("gr_dir_prm_copy_count"),
                    "gr_copy_sdgm_source_story_numbers": ";".join(
                        row.get("gr_copy_sdgm_source_story_numbers") or []
                    ),
                    "gr_copy_mst_source_story_numbers": ";".join(
                        row.get("gr_copy_mst_source_story_numbers") or []
                    ),
                    "event_codes": ";".join(row.get("event_codes") or []),
                    "mapped_event_codes": json.dumps(row.get("mapped_event_codes") or {}, ensure_ascii=False),
                    "observed_sound_ids": ";".join(str(value) for value in row.get("observed_sound_ids") or []),
                    "final_body_state": final_state.get("body_state"),
                    "final_body_mode": final_state.get("body_mode"),
                    "final_body_bet": final_state.get("body_bet"),
                    "final_body_credit": final_state.get("body_credit"),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="comma/range list, e.g. 1,2,10-17")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--device", default="127.0.0.1:16384")
    parser.add_argument("--duration", type=float, default=45.0)
    parser.add_argument("--observer-warmup", type=float, default=3.0)
    parser.add_argument("--trigger-wait", type=float, default=1.2)
    parser.add_argument("--stop-wait", type=float, default=2.0)
    parser.add_argument("--stop-rounds", type=int, default=3)
    parser.add_argument("--tap-delay", type=float, default=0.35)
    parser.add_argument("--startup-wait", type=float, default=20.0)
    parser.add_argument("--ready-retries", type=int, default=8)
    parser.add_argument("--ready-retry-wait", type=float, default=5.0)
    parser.add_argument("--bet-retries", type=int, default=4)
    parser.add_argument("--enter-simulation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--simulation-tap-x", type=int, default=1080)
    parser.add_argument("--simulation-tap-y", type=int, default=3000)
    parser.add_argument("--post-simulation-tap-wait", type=float, default=3.0)
    parser.add_argument("--game-start-tap-x", type=int, default=600)
    parser.add_argument("--game-start-tap-y", type=int, default=2670)
    parser.add_argument("--restart-each", action="store_true")
    parser.add_argument("--event-info-csv", type=Path, default=default_event_info_csv())
    parser.add_argument("--target-code", dest="target_codes", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir = args.out_dir.resolve()
    if not args.target_codes:
        args.target_codes = sorted(DEFAULT_TARGET_CODES)
    candidates = parse_candidates(args.candidates)
    if not candidates:
        raise SystemExit("no candidates")
    cwd = repo_root()
    event_map = load_event_info(args.event_info_csv)

    rows: list[dict[str, Any]] = []
    for kind in candidates:
        try:
            row = run_one_candidate(args, cwd, event_map, kind)
        except Exception as exc:  # keep the scan auditable even on one failed candidate
            row = {
                "kind": kind,
                "path": str(args.out_dir / f"force_kind_{kind:02d}_postclear_scan"),
                "error": str(exc),
                "hit_target_event": False,
            }
            (args.out_dir / f"force_kind_{kind:02d}_postclear_scan").mkdir(parents=True, exist_ok=True)
            (args.out_dir / f"force_kind_{kind:02d}_postclear_scan" / "candidate_summary.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        rows.append(row)
        write_overall(args.out_dir, rows)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if row.get("hit_target_event"):
            break
    write_overall(args.out_dir, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
