#!/usr/bin/env python3
"""State-driven natural SP-story capture with strict runtime evidence gates.

The default mode is a read-only dry run: it verifies foreground/PID identity,
attaches one ARM64 Gadget session, loads the existing probes, and writes only a
small journal.  ADB input is possible only with explicit ``--execute``.

During an executed hunt, no coordinate is trusted by itself.  MAX BET and the
lever advance only when the same Gadget session observes their exact non-zero
``CSlotBody::process`` input bit.  A stop additionally requires the game's
``state+0x64`` progress mask to advance; an input bit alone only proves that the
tap reached ``process`` and can still be rejected by the reel logic.  Heavy
probe messages stay in memory for each attempt.  A non-target attempt writes
only one compact journal row; observer JSONL, hashes, and a manifest are written
only after a real dispatch batch contains both ID19 raw[1] == 8 and a legal
ID24 stage/selector pair.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import queue
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import frida

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.frida_runtime_probe.summarize_lightweight_spin_probe import (
    DispatchBatchTracker,
)


PACKAGE = "com.universal777.magireco"
ACTIVITY = ".SlotMainActivity"
EXPECTED_INPUT_BITS = {
    "max_bet": 1048576,
    "lever": 524288,
    "left_stop": 2,
    "middle_stop": 4,
    "right_stop": 8,
}
STOP_PROGRESS_MASKS = {
    "left_stop": 0x00200000,
    "middle_stop": 0x00600000,
    "right_stop": 0x00E00000,
}
TARGETS_BY_STAGE_SELECTOR = {
    (11, 1): {
        "event": "ac7114_001",
        "event_code_hex": "0x4f71466b3d723041",
        "scene_key": "A0r=kFqO",
    },
    (11, 2): {
        "event": "ac7114_001",
        "event_code_hex": "0x4f71466b3d723041",
        "scene_key": "A0r=kFqO",
    },
    (12, 1): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (12, 2): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (12, 3): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (12, 4): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (13, 1): {
        "event": "ac7116_001",
        "event_code_hex": "0x2476304366614152",
        "scene_key": "RAafC0v$",
    },
    (13, 2): {
        "event": "ac7116_001",
        "event_code_hex": "0x2476304366614152",
        "scene_key": "RAafC0v$",
    },
}
PROBE_FILES = {
    "slot_gate": "slot_state_gate_probe.js",
    "dispatch": "sp_story_dispatch_hunt_probe.js",
    "sound_logic": "sound_logic_chain_probe.js",
}
READY_KINDS = {
    "slot_gate": "slot_gate_probe_ready",
    "dispatch": "sp_story_dispatch_hunt_probe_ready",
    "sound_logic": "sound_logic_probe_ready",
}


class HuntError(RuntimeError):
    """A safety/evidence invariant failed."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_coordinate(value: str) -> tuple[int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("coordinate must be X,Y")
    try:
        x, y = (int(part, 0) for part in parts)
    except ValueError as error:
        raise argparse.ArgumentTypeError("coordinate must contain integers") from error
    if x < 0 or y < 0:
        raise argparse.ArgumentTypeError("coordinate must be non-negative")
    return x, y


def parse_args() -> argparse.Namespace:
    probe_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--device", default="emulator-5554")
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument("--package", default=PACKAGE)
    parser.add_argument("--activity", default=ACTIVITY)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="allow verified ADB taps; without this flag the tool is read-only",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=0,
        help="0 means continue until a target batch; ignored in dry-run mode",
    )
    parser.add_argument("--dry-run-seconds", type=float, default=3.0)
    parser.add_argument("--probe-ready-timeout", type=float, default=15.0)
    # Three simultaneous observers can stretch the game's real 2/2 START
    # phase well past 30 host seconds; the logical snapshot, not elapsed time,
    # still decides when a stop is allowed.
    parser.add_argument("--ready-state-timeout", type=float, default=120.0)
    parser.add_argument(
        "--spin-settle-steps",
        type=int,
        default=17,
        help=(
            "minimum body state steps after entering 3/3 before the first stop; "
            "the stop progress mask remains authoritative"
        ),
    )
    parser.add_argument(
        "--inter-stop-settle-steps",
        type=int,
        default=1,
        help="minimum additional body state steps after each accepted stop",
    )
    # Three simultaneous observers can stretch one logical reel/update frame
    # to several host seconds.  This timeout sends no additional input; it only
    # waits for updateReel/setStopAngle progress after the single gesture.
    parser.add_argument("--stop-progress-timeout", type=float, default=120.0)
    parser.add_argument(
        "--press-duration-ms",
        type=int,
        default=500,
        help=(
            "single stationary swipe duration for every control; this produces "
            "one bounded press that spans multiple render frames under probes"
        ),
    )
    parser.add_argument("--input-confirm-timeout", type=float, default=0.8)
    parser.add_argument("--input-overall-timeout", type=float, default=180.0)
    parser.add_argument("--input-retry-wait", type=float, default=0.12)
    parser.add_argument("--queue-catch-up-timeout", type=float, default=5.0)
    parser.add_argument("--round-timeout", type=float, default=90.0)
    parser.add_argument("--post-hit-seconds", type=float, default=60.0)
    parser.add_argument("--foreground-check-interval", type=float, default=1.0)
    parser.add_argument("--max-buffer-mib", type=float, default=128.0)
    parser.add_argument("--max-bet", type=parse_coordinate, default=(250, 2150))
    parser.add_argument("--lever", type=parse_coordinate, default=(330, 2720))
    parser.add_argument("--left-stop", type=parse_coordinate, default=(820, 2680))
    parser.add_argument("--middle-stop", type=parse_coordinate, default=(1080, 2680))
    parser.add_argument("--right-stop", type=parse_coordinate, default=(1330, 2680))
    parser.add_argument(
        "--slot-gate-script",
        type=Path,
        default=probe_dir / PROBE_FILES["slot_gate"],
    )
    parser.add_argument(
        "--dispatch-script",
        type=Path,
        default=probe_dir / PROBE_FILES["dispatch"],
    )
    parser.add_argument(
        "--sound-logic-script",
        type=Path,
        default=probe_dir / PROBE_FILES["sound_logic"],
    )
    return parser.parse_args()


def run_command(argv: list[str], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )


def adb_command(args: argparse.Namespace, *parts: str) -> list[str]:
    return [args.adb, "-s", args.device, *parts]


def normalized_component(package: str, activity: str) -> str:
    if "/" in activity:
        return activity
    return f"{package}/{activity}"


def inspect_foreground(args: argparse.Namespace) -> dict[str, Any]:
    state = run_command(adb_command(args, "get-state"))
    if state.returncode != 0 or state.stdout.strip() != "device":
        raise HuntError(
            f"ADB device is not online: rc={state.returncode} stdout={state.stdout!r} "
            f"stderr={state.stderr!r}"
        )
    pidof = run_command(adb_command(args, "shell", "pidof", args.package))
    pids = [token for token in pidof.stdout.split() if token.isdigit()]
    if pidof.returncode != 0 or len(pids) != 1:
        raise HuntError(f"expected one {args.package} PID, observed {pids!r}")
    activities = run_command(
        adb_command(args, "shell", "dumpsys", "activity", "activities"),
        timeout=30.0,
    )
    if activities.returncode != 0:
        raise HuntError(f"dumpsys activity failed: {activities.stderr!r}")
    focus_lines = [
        line.strip()
        for line in activities.stdout.splitlines()
        if "mResumedActivity" in line or "topResumedActivity" in line
    ]
    component = normalized_component(args.package, args.activity)
    focused = any(component in line for line in focus_lines)
    if not focused:
        raise HuntError(
            f"game activity is not foreground; expected {component!r}, observed {focus_lines!r}"
        )
    return {
        "device": args.device,
        "package": args.package,
        "activity_component": component,
        "pid": int(pids[0]),
        "focus_lines": focus_lines,
    }


def require_same_runtime(args: argparse.Namespace, expected_pid: int) -> dict[str, Any]:
    current = inspect_foreground(args)
    if current["pid"] != expected_pid:
        raise HuntError(
            f"game PID changed during the single-session capture: "
            f"{expected_pid} -> {current['pid']}"
        )
    return current


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def probe_source_provenance(script_paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Hash the exact observer sources loaded into the shared Gadget session."""

    result: dict[str, dict[str, Any]] = {}
    for name, raw_path in script_paths.items():
        path = raw_path.resolve()
        result[name] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def payload_for(record: dict[str, Any]) -> dict[str, Any]:
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("payload"), dict):
        return message["payload"]
    return {}


class LiveCapture:
    """Own one Gadget session and route three existing probes in memory."""

    def __init__(
        self,
        *,
        host: str,
        expected_pid: int,
        script_paths: dict[str, Path],
        max_buffer_bytes: int,
    ) -> None:
        self.host = host
        self.expected_pid = expected_pid
        self.script_paths = {name: path.resolve() for name, path in script_paths.items()}
        self.max_buffer_bytes = max_buffer_bytes
        self.events: queue.Queue[tuple[str, dict[str, Any], str]] = queue.Queue()
        self.messages_enqueued = 0
        self.messages_processed = 0
        self.device: Any = None
        self.session: Any = None
        self.scripts: dict[str, Any] = {}
        self.detached_reason = ""
        self.ready: set[str] = set()
        self.ready_payloads: dict[str, dict[str, Any]] = {}
        self.sequence = 0
        self.latest_gate_state: dict[str, Any] | None = None
        self.latest_gate_event_count = 0
        self.latest_sdgm_state: dict[str, Any] = {}
        self.input_events: list[dict[str, Any]] = []
        self.reel_stop_events: list[dict[str, Any]] = []
        self.session_records: dict[str, list[str]] = {name: [] for name in script_paths}
        self.capture_session_headers = True
        self.attempt_active = False
        self.attempt_records: dict[str, list[str]] = {name: [] for name in script_paths}
        self.attempt_bytes = 0
        self.buffer_overflow = False
        self.dispatch_tracker = DispatchBatchTracker(strict=True)
        self.complete_candidates: list[dict[str, Any]] = []
        self.lever_eligible_after_sequence: int | None = None
        self.lever_eligible_after_host_unix_ms: int | None = None
        self.selection_candidate: dict[str, Any] | None = None
        self.observed_event_codes: list[dict[str, Any]] = []
        self.target_batch: dict[str, Any] | None = None
        self.outer_bgm_snapshots: list[dict[str, Any]] = []

    def _callback(self, probe_name: str) -> Callable[[dict[str, Any], bytes | None], None]:
        def on_message(message: dict[str, Any], data: bytes | None) -> None:
            self.messages_enqueued += 1
            record: dict[str, Any] = {
                "host_unix_ms": int(time.time() * 1000),
                "callback_message_index": self.messages_enqueued,
                "probe": probe_name,
                "message": message,
            }
            if data:
                record["data_base64"] = base64.b64encode(data).decode("ascii")
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            self.events.put((probe_name, record, line))

        return on_message

    def attach(self) -> None:
        manager = frida.get_device_manager()
        self.device = manager.add_remote_device(self.host)
        processes = self.device.enumerate_processes()
        targets = [process for process in processes if int(process.pid) == self.expected_pid]
        if len(targets) != 1:
            visible = [(int(process.pid), process.name) for process in processes]
            raise HuntError(
                f"Gadget did not expose expected PID {self.expected_pid}; visible={visible!r}"
            )
        self.session = self.device.attach(self.expected_pid)
        try:
            self.session.on("detached", self._on_detached)
        except Exception:
            pass
        for name, path in self.script_paths.items():
            source = path.read_text(encoding="utf-8")
            script = self.session.create_script(source)
            script.on("message", self._callback(name))
            self.scripts[name] = script
            script.load()

    def _on_detached(self, reason: str, _crash: Any = None) -> None:
        self.detached_reason = str(reason)

    def close(self) -> None:
        for script in reversed(list(self.scripts.values())):
            try:
                script.unload()
            except Exception:
                pass
        if self.session is not None:
            try:
                self.session.detach()
            except Exception:
                pass

    def refresh_gate_snapshot(self) -> dict[str, Any] | None:
        """Read the bounded logical slot state without waiting for an event.

        The gate's change-only messages prove accepted inputs, but a passive
        transition can occur between calls that emit a message.  Its RPC reads
        the same named fields from the last observed CSlotBody pointer; it does
        not capture media or arbitrary memory.
        """

        script = self.scripts.get("slot_gate")
        if script is None:
            return self.latest_gate_state
        try:
            snapshot = script.exports_sync.snapshot()
        except Exception as error:
            raise HuntError(f"slot-gate logical snapshot failed: {error}") from error
        if not isinstance(snapshot, dict):
            raise HuntError(f"slot-gate logical snapshot is not an object: {snapshot!r}")
        if snapshot.get("installed") is False:
            raise HuntError("slot-gate logical snapshot reports hook not installed")
        state = snapshot.get("state")
        if isinstance(state, dict) and state.get("slot_body_pointer") not in {None, "0x0"}:
            self.latest_gate_state = state
        return self.latest_gate_state

    def record_outer_bgm_snapshot(self, label: str) -> dict[str, Any]:
        """Record one bounded CSL active-sound RPC result.

        The probe deliberately labels channel-zero rows as candidates only;
        this method preserves that native metadata and never upgrades it to a
        semantic BGM classification.  RPC failure is retained as evidence and
        does not hide an otherwise valid natural-spin attempt.
        """

        host_unix_ms = int(time.time() * 1000)
        script = self.scripts.get("sound_logic")
        if script is None:
            snapshot: dict[str, Any] = {
                "schema": "magireco-csl-active-sound-snapshot-v1",
                "label": label,
                "captured_host_unix_ms": host_unix_ms,
                "available": False,
                "error": "sound_logic probe is not loaded",
            }
        else:
            try:
                raw = script.exports_sync.outerbgmsnapshot(label)
                if not isinstance(raw, dict):
                    raise TypeError(f"outer BGM snapshot is not an object: {raw!r}")
                snapshot = copy.deepcopy(raw)
                snapshot.setdefault("label", label)
                snapshot["captured_host_unix_ms"] = host_unix_ms
            except Exception as error:
                snapshot = {
                    "schema": "magireco-csl-active-sound-snapshot-v1",
                    "label": label,
                    "captured_host_unix_ms": host_unix_ms,
                    "available": False,
                    "error": f"outer BGM snapshot RPC failed: {error}",
                }
        self.outer_bgm_snapshots.append(snapshot)
        return snapshot

    def begin_attempt(self) -> None:
        self.capture_session_headers = False
        self.attempt_active = True
        self.attempt_records = {name: [] for name in self.script_paths}
        self.attempt_bytes = 0
        self.buffer_overflow = False
        self.dispatch_tracker = DispatchBatchTracker(strict=True)
        self.complete_candidates = []
        self.lever_eligible_after_sequence = None
        self.lever_eligible_after_host_unix_ms = None
        self.selection_candidate = None
        self.observed_event_codes = []
        self.target_batch = None
        self.input_events = []
        self.reel_stop_events = []
        self.outer_bgm_snapshots = []

    def end_attempt(self) -> None:
        self.attempt_active = False
        self.attempt_records = {name: [] for name in self.script_paths}
        self.attempt_bytes = 0
        self.input_events = []
        self.reel_stop_events = []
        self.outer_bgm_snapshots = []

    def mark_lever_issued(self, sequence: int, host_unix_ms: int) -> None:
        self.lever_eligible_after_sequence = sequence
        self.lever_eligible_after_host_unix_ms = host_unix_ms
        self._refresh_target()

    def _refresh_target(self) -> None:
        if (
            self.target_batch is not None
            or self.lever_eligible_after_sequence is None
            or self.lever_eligible_after_host_unix_ms is None
        ):
            return
        for candidate in self.complete_candidates:
            candidate_sequence = int(candidate.get("completion_sequence", 0))
            candidate_host_unix_ms = int(candidate.get("completion_host_unix_ms", 0))
            if candidate_sequence <= self.lever_eligible_after_sequence:
                continue
            if candidate_host_unix_ms <= self.lever_eligible_after_host_unix_ms:
                continue
            target = target_for_batch(candidate)
            if target is None:
                continue
            self.selection_candidate = {
                **candidate,
                "expected_target": target,
            }
            expected_code = target["event_code_hex"].lower()
            for event_row in self.observed_event_codes:
                # The exact event code must be emitted after this completed
                # ID19+ID24 selection batch, not merely after the lever.  A
                # matching code from an earlier dispatch in the same attempt
                # is unrelated evidence and must fail closed.
                if int(event_row.get("sequence", 0)) <= candidate_sequence:
                    continue
                if (
                    int(event_row.get("host_unix_ms", 0))
                    <= candidate_host_unix_ms
                ):
                    continue
                if str(event_row.get("event_code_hex", "")).lower() == expected_code:
                    self.target_batch = {
                        **self.selection_candidate,
                        "resolved_event": target,
                        "event_code_observation": event_row,
                    }
                    return

    def _retain_line(self, probe_name: str, line: str) -> None:
        if self.attempt_active:
            encoded_size = len(line.encode("utf-8")) + 1
            if self.max_buffer_bytes > 0 and self.attempt_bytes + encoded_size > self.max_buffer_bytes:
                self.buffer_overflow = True
                return
            self.attempt_records[probe_name].append(line)
            self.attempt_bytes += encoded_size
        elif self.capture_session_headers:
            self.session_records[probe_name].append(line)

    def pump(self, timeout: float) -> dict[str, Any] | None:
        if self.detached_reason:
            raise HuntError(f"Gadget session detached: {self.detached_reason}")
        try:
            probe_name, record, line = self.events.get(timeout=max(timeout, 0.0))
        except queue.Empty:
            return None
        self.sequence += 1
        self.messages_processed += 1
        self._retain_line(probe_name, line)
        payload = payload_for(record)
        kind = str(payload.get("kind") or "")
        if kind == READY_KINDS.get(probe_name):
            if payload.get("installed") is False:
                raise HuntError(f"probe {probe_name} reported not installed: {payload!r}")
            self.ready.add(probe_name)
            self.ready_payloads[probe_name] = copy.deepcopy(payload)

        if probe_name == "slot_gate" and kind == "slot_gate_state":
            state_after = payload.get("state_after")
            if isinstance(state_after, dict):
                self.latest_gate_state = state_after
            try:
                self.latest_gate_event_count = max(
                    self.latest_gate_event_count,
                    int(payload.get("event_count") or 0),
                )
            except (TypeError, ValueError):
                pass
            if payload.get("input_nonzero"):
                self.input_events.append(
                    {
                        "sequence": self.sequence,
                        "host_unix_ms": record.get("host_unix_ms"),
                        "source_unix_ms": payload.get("unix_ms"),
                        "payload": payload,
                    }
                )

        if probe_name == "slot_gate" and kind == "reel_stop_angle_enter":
            self.reel_stop_events.append(
                {
                    "sequence": self.sequence,
                    "host_unix_ms": record.get("host_unix_ms"),
                    "source_unix_ms": payload.get("unix_ms"),
                    "axis_i32": payload.get("axis_i32"),
                    "angle_i32": payload.get("angle_i32"),
                    "slot_body_pointer": payload.get("slot_body_pointer"),
                }
            )

        if probe_name == "dispatch":
            sdgm_fields = {
                key: value
                for key, value in payload.items()
                if key.startswith("sdgm_")
            }
            if sdgm_fields:
                self.latest_sdgm_state.update(sdgm_fields)
                self.latest_sdgm_state.update(
                    {
                        "observed_sequence": self.sequence,
                        "observed_host_unix_ms": record.get("host_unix_ms"),
                        "observed_kind": kind,
                    }
                )
            if kind == "id401_get_cmd_buf_leave":
                self.dispatch_tracker.register_get_cmd_buf(
                    payload,
                    line=self.sequence,
                    rel_time=None,
                )
            _row, complete = self.dispatch_tracker.observe_access(
                payload,
                line=self.sequence,
                rel_time=None,
                source_kind=kind,
            )
            if complete is not None:
                complete = dict(complete)
                complete["completion_sequence"] = self.sequence
                complete["completion_host_unix_ms"] = record.get("host_unix_ms")
                complete["completion_source_unix_ms"] = payload.get("unix_ms")
                self.complete_candidates.append(complete)
                self._refresh_target()
            if kind in {"direction_scene_request", "ctrl_snd_req_event_code"}:
                event_code = str(payload.get("event_code_hex") or "").lower()
                if event_code:
                    self.observed_event_codes.append(
                        {
                            "sequence": self.sequence,
                            "host_unix_ms": record.get("host_unix_ms"),
                            "source_unix_ms": payload.get("unix_ms"),
                            "kind": kind,
                            "event_code_hex": event_code,
                            "return_symbol": payload.get("return_symbol", ""),
                        }
                    )
                    self._refresh_target()
        return {"probe": probe_name, "record": record, "payload": payload, "kind": kind}

    def pump_for(self, seconds: float) -> None:
        deadline = time.monotonic() + max(seconds, 0.0)
        while time.monotonic() < deadline:
            self.pump(min(0.1, max(deadline - time.monotonic(), 0.0)))

    def wait_until(self, predicate: Callable[[], bool], timeout: float, description: str) -> None:
        deadline = time.monotonic() + max(timeout, 0.0)
        while not predicate():
            if time.monotonic() >= deadline:
                raise HuntError(f"timed out waiting for {description}")
            self.pump(min(0.1, max(deadline - time.monotonic(), 0.0)))


def state_value(capture: LiveCapture, key: str) -> Any:
    return (capture.latest_gate_state or {}).get(key)


def is_idle_state(capture: LiveCapture) -> bool:
    return (
        state_value(capture, "body_state_i32_at_0x00") == 1
        and state_value(capture, "body_mode_i32_at_0x04") == 1
    )


def is_bettable_state(capture: LiveCapture) -> bool:
    state = state_value(capture, "body_state_i32_at_0x00")
    mode = state_value(capture, "body_mode_i32_at_0x04")
    return (state, mode) in {(0, 0), (1, 1)}


def is_input_released(capture: LiveCapture) -> bool:
    return (
        state_value(capture, "body_input_mask_i32_at_0x408") == 0
        and state_value(capture, "body_button_state_i32_at_0x74") == 0
    )


def state_age(capture: LiveCapture) -> int | None:
    try:
        return int(state_value(capture, "body_initialized_i32_at_0x08"))
    except (TypeError, ValueError):
        return None


def state_has_advanced(capture: LiveCapture, minimum_steps: int = 1) -> bool:
    age = state_age(capture)
    return age is not None and age >= max(int(minimum_steps), 1)


def is_idle_armed_state(capture: LiveCapture) -> bool:
    return (
        is_idle_state(capture)
        and state_value(capture, "body_bet_i32_at_0x58") == 3
        and is_input_released(capture)
        and state_has_advanced(capture)
    )


def needs_max_bet(capture: LiveCapture) -> bool:
    """Only a confirmed idle 1/1 state with bet 3 is already armed.

    A fresh 0/0 sample can retain a stale bet field, so it must always pass
    through an accepted MAX BET input before the lever is allowed.
    """

    return not is_idle_armed_state(capture)


def ensure_message_queue_caught_up(
    capture: LiveCapture,
    *,
    timeout: float,
) -> dict[str, int]:
    """Consume every callback already enqueued before an input boundary.

    Frida callbacks timestamp records before enqueueing them.  Reaching equal
    enqueue/processed counters with an empty queue establishes a local live
    edge.  If the observer stream cannot be caught up within the bound, input
    is forbidden instead of being repeated against stale evidence.
    """

    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        while capture.messages_processed < capture.messages_enqueued:
            if time.monotonic() >= deadline:
                raise HuntError(
                    "observer message queue did not catch up before input: "
                    f"processed={capture.messages_processed} "
                    f"enqueued={capture.messages_enqueued} "
                    f"queued={capture.events.qsize()}"
                )
            if capture.pump(0.0) is None:
                break
        if (
            capture.messages_processed == capture.messages_enqueued
            and capture.events.empty()
        ):
            return {
                "sequence": capture.sequence,
                "host_unix_ms": int(time.time() * 1000),
                "messages_processed": capture.messages_processed,
            }
        if time.monotonic() >= deadline:
            raise HuntError(
                "observer message queue did not catch up before input: "
                f"processed={capture.messages_processed} "
                f"enqueued={capture.messages_enqueued} "
                f"queued={capture.events.qsize()}"
            )
        capture.pump(min(0.01, max(deadline - time.monotonic(), 0.0)))


def target_for_batch(batch: dict[str, Any]) -> dict[str, Any] | None:
    pairs = batch.get("sp_story_selection_pairs")
    if not isinstance(pairs, list):
        return None
    resolved: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        try:
            key = (int(pair.get("stage")), int(pair.get("selector")))
        except (TypeError, ValueError):
            continue
        target = TARGETS_BY_STAGE_SELECTOR.get(key)
        if target is not None:
            resolved.append({**target, "stage": key[0], "selector": key[1]})
    if not resolved:
        return None
    first = resolved[0]
    if any(row["event"] != first["event"] for row in resolved[1:]):
        return None
    return first


def is_spin_state(capture: LiveCapture) -> bool:
    return (
        state_value(capture, "body_state_i32_at_0x00") == 3
        and state_value(capture, "body_mode_i32_at_0x04") == 3
    )


def is_spin_ready_state(capture: LiveCapture, minimum_steps: int = 1) -> bool:
    return (
        is_spin_state(capture)
        and is_input_released(capture)
        and state_has_advanced(capture, minimum_steps)
    )


def is_stop_engine_ready(capture: LiveCapture, minimum_steps: int = 17) -> bool:
    """Gate a stop on the counters used by CSlotBody::STOP/calcStop.

    In the normal non-FastAuto path, body+0x538 reaches 16 before calcStop is
    entered.  calcStop then requires the inter-stop counter at +0x53c to reach
    5 and +0x540 to be -1 (no axis waiting for updateReel).  These are bounded
    named fields from the same CSlotBody pointer, not visual readiness guesses.
    """

    try:
        wait16 = int(state_value(capture, "body_stop_wait16_i32_at_0x538"))
        interstop = int(state_value(capture, "body_interstop_i32_at_0x53c"))
        selected_axis = int(state_value(capture, "body_selected_axis_i32_at_0x540"))
    except (TypeError, ValueError):
        return False
    return (
        is_spin_ready_state(capture, minimum_steps)
        and wait16 >= 16
        and interstop >= 5
        and selected_axis == -1
    )


def has_stop_progress(capture: LiveCapture, action: str) -> bool:
    """Confirm that the reel state machine, not merely input routing, advanced."""

    expected = STOP_PROGRESS_MASKS[action]
    try:
        observed = int(state_value(capture, "state_u32_at_0x64"))
    except (TypeError, ValueError):
        return False
    return observed & expected == expected


def find_reel_stop_after(
    capture: LiveCapture,
    *,
    baseline_sequence: int,
    issued_host_unix_ms: int,
    expected_axis: int,
) -> dict[str, Any] | None:
    """Return the exact post-input CReel::setStopAngle(axis, ...) call."""

    for event in capture.reel_stop_events:
        if int(event.get("sequence", 0)) <= baseline_sequence:
            continue
        if int(event.get("host_unix_ms", 0)) <= issued_host_unix_ms:
            continue
        try:
            axis = int(event.get("axis_i32"))
        except (TypeError, ValueError):
            continue
        if axis == expected_axis:
            return event
    return None


def has_reel_stop_after(
    capture: LiveCapture,
    *,
    baseline_sequence: int,
    issued_host_unix_ms: int,
    expected_axis: int,
) -> bool:
    return find_reel_stop_after(
        capture,
        baseline_sequence=baseline_sequence,
        issued_host_unix_ms=issued_host_unix_ms,
        expected_axis=expected_axis,
    ) is not None


def capture_stop_progress_evidence(
    capture: LiveCapture,
    *,
    action: str,
    stop_action: dict[str, Any],
    expected_axis: int,
) -> dict[str, Any] | None:
    """Freeze the first state snapshot proving an accepted stop advanced.

    The returned row binds the authoritative CReel callback and cumulative
    state+0x64 mask to the same post-input waterline.  Callers retain the first
    non-null result rather than later, more advanced masks.
    """

    if not has_stop_progress(capture, action):
        return None
    reel_stop = find_reel_stop_after(
        capture,
        baseline_sequence=int(stop_action["issued_after_sequence"]),
        issued_host_unix_ms=int(stop_action["issued_host_unix_ms"]),
        expected_axis=expected_axis,
    )
    if reel_stop is None:
        return None
    try:
        observed_mask = int(state_value(capture, "state_u32_at_0x64"))
    except (TypeError, ValueError):
        return None
    return {
        "progress_expected_mask": STOP_PROGRESS_MASKS[action],
        "progress_observed_mask": observed_mask,
        "progress_observed_sequence": capture.sequence,
        "progress_observed_host_unix_ms": int(time.time() * 1000),
        "progress_observed_state_age": state_age(capture),
        "progress_observed_gate_snapshot": copy.deepcopy(capture.latest_gate_state),
        "progress_reel_stop_sequence": reel_stop.get("sequence"),
        "progress_reel_stop_host_unix_ms": reel_stop.get("host_unix_ms"),
        "progress_reel_stop_axis_i32": reel_stop.get("axis_i32"),
    }


def is_post_lever_state(capture: LiveCapture) -> bool:
    """Recognize the sampled transition after an accepted lever.

    The change-only gate observes ``CSlotBody::process`` calls, not a periodic
    state poll.  A lever call can therefore leave the latest sample at 1/2;
    the historical 3/3 sample is first seen only when a stop candidate enters
    ``process``.  Requiring 3/3 before trying that stop is a circular gate.
    Stop acceptance remains authoritative only when process reports bit 2/4/8.
    """

    state = state_value(capture, "body_state_i32_at_0x00")
    mode = state_value(capture, "body_mode_i32_at_0x04")
    return (state, mode) in {(1, 2), (3, 3)}


def find_input_after(
    capture: LiveCapture,
    *,
    baseline_sequence: int,
    issued_host_unix_ms: int,
    expected_bit: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    expected: dict[str, Any] | None = None
    unexpected: dict[str, Any] | None = None
    for event in capture.input_events:
        if int(event.get("sequence", 0)) <= baseline_sequence:
            continue
        if int(event.get("host_unix_ms", 0)) <= issued_host_unix_ms:
            continue
        payload = event.get("payload") or {}
        if payload.get("process_input_a_i32") == expected_bit:
            expected = event
            break
        unexpected = event
        break
    return expected, unexpected


def tap_until_accepted(
    args: argparse.Namespace,
    capture: LiveCapture,
    *,
    expected_pid: int,
    action: str,
    coordinate: tuple[int, int],
    expected_reel_axis: int | None = None,
) -> dict[str, Any]:
    if not args.execute:
        raise HuntError("internal safety error: attempted input without --execute")
    expected_bit = EXPECTED_INPUT_BITS[action]
    if action in STOP_PROGRESS_MASKS and expected_reel_axis is None:
        raise HuntError(f"internal safety error: no expected reel axis for {action}")
    overall_deadline = time.monotonic() + max(args.input_overall_timeout, 0.0)
    require_same_runtime(args, expected_pid)
    queue_waterline = ensure_message_queue_caught_up(
        capture,
        timeout=min(
            max(args.queue_catch_up_timeout, 0.0),
            max(overall_deadline - time.monotonic(), 0.0),
        ),
    )
    baseline_sequence = capture.sequence
    issued_host_unix_ms = int(time.time() * 1000)
    press_duration_ms = max(int(args.press_duration_ms), 1)
    input_argv = adb_command(
        args,
        "shell",
        "input",
        "swipe",
        str(coordinate[0]),
        str(coordinate[1]),
        str(coordinate[0]),
        str(coordinate[1]),
        str(press_duration_ms),
    )
    input_method = "single_stationary_swipe"
    result = run_command(input_argv)
    if result.returncode != 0:
        raise HuntError(f"ADB tap failed for {action}: {result.stderr!r}")

    def accepted_input() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        return find_input_after(
            capture,
            baseline_sequence=baseline_sequence,
            issued_host_unix_ms=issued_host_unix_ms,
            expected_bit=expected_bit,
        )

    def accepted_reel_stop() -> dict[str, Any] | None:
        if expected_reel_axis is None:
            return None
        return find_reel_stop_after(
            capture,
            baseline_sequence=baseline_sequence,
            issued_host_unix_ms=issued_host_unix_ms,
            expected_axis=expected_reel_axis,
        )

    confirm_deadline = min(
        overall_deadline,
        time.monotonic() + max(args.input_confirm_timeout, 0.0),
    )
    while time.monotonic() < confirm_deadline:
        capture.pump(min(0.05, max(confirm_deadline - time.monotonic(), 0.0)))
        expected, unexpected = accepted_input()
        reel_stop = accepted_reel_stop()
        if unexpected is not None:
            payload = unexpected.get("payload") or {}
            raise HuntError(
                f"{action} produced unexpected nonzero process input: "
                f"A={payload.get('process_input_a_i32')} "
                f"B={payload.get('process_input_b_i32')}"
            )
        if expected is not None or reel_stop is not None:
            break
    else:
        expected, unexpected = accepted_input()
        reel_stop = accepted_reel_stop()

    if expected is None and unexpected is None:
        ensure_message_queue_caught_up(
            capture,
            timeout=min(
                max(args.queue_catch_up_timeout, 0.0),
                max(overall_deadline - time.monotonic(), 0.0),
            ),
        )
        expected, unexpected = accepted_input()
        reel_stop = accepted_reel_stop()
    if unexpected is not None:
        payload = unexpected.get("payload") or {}
        raise HuntError(
            f"{action} produced unexpected nonzero process input: "
            f"A={payload.get('process_input_a_i32')} "
            f"B={payload.get('process_input_b_i32')}"
        )
    if expected is None and reel_stop is None:
        raise HuntError(
            f"single {action} gesture was confirmed by neither process input bit "
            f"{expected_bit} nor the expected setStopAngle axis; input was not repeated"
        )
    authoritative = reel_stop if reel_stop is not None else expected
    return {
        "action": action,
        "expected_process_input_a_i32": expected_bit,
        "coordinate": list(coordinate),
        "input_method": input_method,
        "press_duration_ms": press_duration_ms,
        "tap_attempt": 1,
        "issued_host_unix_ms": issued_host_unix_ms,
        "issued_after_sequence": baseline_sequence,
        "queue_waterline": queue_waterline,
        "accepted_sequence": authoritative.get("sequence"),
        "accepted_host_unix_ms": authoritative.get("host_unix_ms"),
        "process_input_confirmed": expected is not None,
        "process_input_sequence": expected.get("sequence") if expected is not None else None,
        "process_input_host_unix_ms": (
            expected.get("host_unix_ms") if expected is not None else None
        ),
        "reel_stop_confirmed": reel_stop is not None,
        "reel_stop_axis": reel_stop.get("axis_i32") if reel_stop is not None else None,
        "reel_stop_sequence": reel_stop.get("sequence") if reel_stop is not None else None,
        "reel_stop_host_unix_ms": (
            reel_stop.get("host_unix_ms") if reel_stop is not None else None
        ),
        "accepted_payload": expected.get("payload") if expected is not None else None,
    }


def wait_for_state_with_runtime_checks(
    args: argparse.Namespace,
    capture: LiveCapture,
    *,
    expected_pid: int,
    predicate: Callable[[], bool],
    timeout: float,
    description: str,
) -> None:
    deadline = time.monotonic() + max(timeout, 0.0)
    next_runtime_check = 0.0
    while True:
        capture.refresh_gate_snapshot()
        if predicate():
            return
        now = time.monotonic()
        if now >= deadline:
            raise HuntError(f"timed out waiting for {description}")
        if now >= next_runtime_check:
            require_same_runtime(args, expected_pid)
            next_runtime_check = now + max(args.foreground_check_interval, 0.1)
        capture.pump(min(0.1, max(deadline - now, 0.0)))


def append_journal(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", buffering=1) as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def compact_attempt_summary(
    *,
    attempt: int,
    started_unix_ms: int,
    outcome: str,
    actions: list[dict[str, Any]],
    capture: LiveCapture,
    error: str = "",
) -> dict[str, Any]:
    return {
        "schema": "magireco-natural-sp-story-hunt-attempt-v1",
        "host_unix_ms": int(time.time() * 1000),
        "attempt": attempt,
        "started_unix_ms": started_unix_ms,
        "outcome": outcome,
        "error": error,
        "accepted_actions": [
            {
                "action": row.get("action"),
                "expected_process_input_a_i32": row.get("expected_process_input_a_i32"),
                "coordinate": row.get("coordinate"),
                "input_method": row.get("input_method"),
                "press_duration_ms": row.get("press_duration_ms"),
                "tap_attempt": row.get("tap_attempt"),
                "issued_host_unix_ms": row.get("issued_host_unix_ms"),
                "issued_after_sequence": row.get("issued_after_sequence"),
                "queue_waterline": row.get("queue_waterline"),
                "accepted_sequence": row.get("accepted_sequence"),
                "accepted_host_unix_ms": row.get("accepted_host_unix_ms"),
                "process_input_confirmed": row.get("process_input_confirmed"),
                "process_input_sequence": row.get("process_input_sequence"),
                "reel_stop_confirmed": row.get("reel_stop_confirmed"),
                "reel_stop_axis": row.get("reel_stop_axis"),
                "reel_stop_sequence": row.get("reel_stop_sequence"),
                "progress_expected_mask": row.get("progress_expected_mask"),
                "progress_observed_mask": row.get("progress_observed_mask"),
                "progress_observed_sequence": row.get("progress_observed_sequence"),
                "progress_observed_host_unix_ms": row.get(
                    "progress_observed_host_unix_ms"
                ),
                "progress_observed_state_age": row.get("progress_observed_state_age"),
                "progress_observed_gate_snapshot": row.get(
                    "progress_observed_gate_snapshot"
                ),
                "progress_reel_stop_sequence": row.get("progress_reel_stop_sequence"),
                "progress_reel_stop_host_unix_ms": row.get(
                    "progress_reel_stop_host_unix_ms"
                ),
                "progress_reel_stop_axis_i32": row.get("progress_reel_stop_axis_i32"),
            }
            for row in actions
        ],
        "dispatch_batches": capture.dispatch_tracker.dispatch_batches(),
        "complete_candidate_count": len(capture.complete_candidates),
        "selection_candidate": capture.selection_candidate,
        "observed_event_codes": capture.observed_event_codes,
        "target_batch": capture.target_batch,
        "buffer_overflow": capture.buffer_overflow,
        "buffered_observer_bytes": capture.attempt_bytes,
        "final_gate_state": capture.latest_gate_state,
        "latest_sdgm_state": dict(capture.latest_sdgm_state),
        "reel_stop_events": list(capture.reel_stop_events),
        "outer_bgm_active_sound_snapshots": copy.deepcopy(capture.outer_bgm_snapshots),
    }


def unique_target_dir(out_dir: Path, attempt: int) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    base = out_dir / f"target_hit_{stamp}_attempt_{attempt:06d}"
    if not base.exists():
        return base
    for suffix in range(1, 1000):
        candidate = out_dir / f"{base.name}_{suffix:03d}"
        if not candidate.exists():
            return candidate
    raise HuntError("could not allocate a unique target output directory")


def write_target_package(
    args: argparse.Namespace,
    capture: LiveCapture,
    *,
    attempt: int,
    runtime_state: dict[str, Any],
    actions: list[dict[str, Any]],
    journal_path: Path,
) -> Path:
    if capture.target_batch is None:
        raise HuntError("cannot write target package without a complete target batch")
    target_dir = unique_target_dir(args.out_dir, attempt)
    target_dir.mkdir(parents=True, exist_ok=False)
    observer_paths: dict[str, Path] = {}
    for name in capture.script_paths:
        path = target_dir / f"observer_{name}.jsonl"
        lines = capture.session_records[name] + capture.attempt_records[name]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        observer_paths[name] = path

    provenance_paths = {
        "hunt_driver": Path(__file__).resolve(),
        "shared_batch_logic": (
            repo_root() / "tools" / "frida_runtime_probe" / "summarize_lightweight_spin_probe.py"
        ).resolve(),
        **{f"probe_{name}": path for name, path in capture.script_paths.items()},
    }
    hashes: dict[str, dict[str, Any]] = {}
    for name, path in {**observer_paths, **provenance_paths, "hunt_journal": journal_path}.items():
        hashes[name] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    manifest = {
        "schema": "magireco-natural-sp-story-target-capture-v1",
        "created_unix_ms": int(time.time() * 1000),
        "evidence_gate": (
            "same strict ID401 getCmdBuf/accessSubProcess batch contains "
            "ID19 raw[1]=8 and legal ID24 stage/selector"
        ),
        "visual_matching_used": False,
        "adb_input_enabled": bool(args.execute),
        "single_gadget_session": True,
        "runtime": runtime_state,
        "attempt": attempt,
        "expected_process_input_a_i32": EXPECTED_INPUT_BITS,
        "accepted_actions": actions,
        "target_batch": capture.target_batch,
        "resolved_target_event": capture.target_batch.get("resolved_event"),
        "all_dispatch_batches": capture.dispatch_tracker.dispatch_batches(),
        "probe_ready_payloads": copy.deepcopy(capture.ready_payloads),
        "outer_bgm_active_sound_snapshots": copy.deepcopy(capture.outer_bgm_snapshots),
        "buffer_overflow": capture.buffer_overflow,
        "observer_and_source_hashes": hashes,
    }
    manifest_path = target_dir / "capture_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    hashes["capture_manifest"] = {
        "path": str(manifest_path),
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    }
    (target_dir / "sha256sums.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target_dir


def script_paths_from_args(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "slot_gate": args.slot_gate_script,
        "dispatch": args.dispatch_script,
        "sound_logic": args.sound_logic_script,
    }


def validate_args(args: argparse.Namespace) -> None:
    if args.max_attempts < 0:
        raise HuntError("--max-attempts must be >= 0")
    if args.max_buffer_mib < 0:
        raise HuntError("--max-buffer-mib must be >= 0")
    if args.queue_catch_up_timeout < 0:
        raise HuntError("--queue-catch-up-timeout must be >= 0")
    missing = [str(path) for path in script_paths_from_args(args).values() if not path.is_file()]
    if missing:
        raise HuntError(f"probe script(s) missing: {missing!r}")


def main() -> int:
    args = parse_args()
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    journal_path = args.out_dir / "hunt_journal.jsonl"
    capture: LiveCapture | None = None
    try:
        validate_args(args)
        initial_runtime = inspect_foreground(args)
        capture = LiveCapture(
            host=args.host,
            expected_pid=initial_runtime["pid"],
            script_paths=script_paths_from_args(args),
            max_buffer_bytes=int(args.max_buffer_mib * 1024 * 1024),
        )
        capture.attach()
        capture.wait_until(
            lambda: capture.ready == set(PROBE_FILES),
            args.probe_ready_timeout,
            "all three probes to report ready",
        )
        capture.wait_until(
            lambda: capture.latest_gate_state is not None,
            args.ready_state_timeout,
            "initial CSlotBody::process state",
        )
        require_same_runtime(args, initial_runtime["pid"])
        loaded_probe_sources = probe_source_provenance(capture.script_paths)
        initial_outer_bgm_snapshot = capture.record_outer_bgm_snapshot("session_ready")
        append_journal(
            journal_path,
            {
                "schema": "magireco-natural-sp-story-hunt-session-v1",
                "host_unix_ms": int(time.time() * 1000),
                "event": "session_ready",
                "execute": bool(args.execute),
                "runtime": initial_runtime,
                "gadget_host": args.host,
                "expected_process_input_a_i32": EXPECTED_INPUT_BITS,
                "initial_gate_state": capture.latest_gate_state,
                "loaded_probe_sources": loaded_probe_sources,
                "probe_ready_payloads": copy.deepcopy(capture.ready_payloads),
                "initial_outer_bgm_active_sound_snapshot": initial_outer_bgm_snapshot,
            },
        )

        if not args.execute:
            capture.capture_session_headers = False
            capture.pump_for(args.dry_run_seconds)
            require_same_runtime(args, initial_runtime["pid"])
            final_outer_bgm_snapshot = capture.record_outer_bgm_snapshot(
                "dry_run_complete"
            )
            append_journal(
                journal_path,
                {
                    "schema": "magireco-natural-sp-story-hunt-session-v1",
                    "host_unix_ms": int(time.time() * 1000),
                    "event": "dry_run_complete",
                    "adb_input_sent": False,
                    "runtime": initial_runtime,
                    "final_gate_state": capture.latest_gate_state,
                    "final_outer_bgm_active_sound_snapshot": final_outer_bgm_snapshot,
                },
            )
            print(json.dumps({"ok": True, "dry_run": True, "journal": str(journal_path)}))
            return 0

        attempt = 0
        while args.max_attempts == 0 or attempt < args.max_attempts:
            attempt += 1
            require_same_runtime(args, initial_runtime["pid"])
            wait_for_state_with_runtime_checks(
                args,
                capture,
                expected_pid=initial_runtime["pid"],
                predicate=lambda: is_bettable_state(capture),
                timeout=args.ready_state_timeout,
                description="bettable state 0/0 or idle state 1/1 before the next attempt",
            )
            ensure_message_queue_caught_up(
                capture,
                timeout=args.queue_catch_up_timeout,
            )
            if not is_bettable_state(capture):
                raise HuntError(
                    "slot left bettable state while the observer queue was catching up"
                )
            capture.begin_attempt()
            started_unix_ms = int(time.time() * 1000)
            actions: list[dict[str, Any]] = []
            try:
                capture.record_outer_bgm_snapshot("attempt_pre")
                if needs_max_bet(capture):
                    actions.append(
                        tap_until_accepted(
                            args,
                            capture,
                            expected_pid=initial_runtime["pid"],
                            action="max_bet",
                            coordinate=args.max_bet,
                        )
                    )
                    wait_for_state_with_runtime_checks(
                        args,
                        capture,
                        expected_pid=initial_runtime["pid"],
                        predicate=lambda: is_idle_armed_state(capture),
                        timeout=args.ready_state_timeout,
                        description=(
                            "released and advanced idle state 1/1 with bet 3 "
                            "after accepted max bet"
                        ),
                    )
                lever = tap_until_accepted(
                    args,
                    capture,
                    expected_pid=initial_runtime["pid"],
                    action="lever",
                    coordinate=args.lever,
                )
                actions.append(lever)
                capture.mark_lever_issued(
                    int(lever["issued_after_sequence"]),
                    int(lever["issued_host_unix_ms"]),
                )

                wait_for_state_with_runtime_checks(
                    args,
                    capture,
                    expected_pid=initial_runtime["pid"],
                    predicate=lambda: capture.target_batch is not None
                    or is_stop_engine_ready(capture, args.spin_settle_steps),
                    timeout=args.ready_state_timeout,
                    description="released and advanced spin state 3/3",
                )
                stop_actions = (
                    ("left_stop", args.left_stop, 0),
                    ("middle_stop", args.middle_stop, 1),
                    ("right_stop", args.right_stop, 2),
                )
                for stop_index, (action, coordinate, expected_axis) in enumerate(stop_actions):
                    if capture.target_batch is not None:
                        break
                    stop_action = tap_until_accepted(
                        args,
                        capture,
                        expected_pid=initial_runtime["pid"],
                        action=action,
                        coordinate=coordinate,
                        expected_reel_axis=expected_axis,
                    )
                    stop_action.update(
                        {
                            "progress_expected_mask": STOP_PROGRESS_MASKS[action],
                            "progress_observed_mask": None,
                            "progress_observed_sequence": None,
                            "progress_observed_host_unix_ms": None,
                            "progress_observed_state_age": None,
                            "progress_observed_gate_snapshot": None,
                            "progress_reel_stop_sequence": None,
                            "progress_reel_stop_host_unix_ms": None,
                            "progress_reel_stop_axis_i32": None,
                        }
                    )
                    actions.append(stop_action)
                    progress_evidence: dict[str, Any] | None = None

                    def stop_progress_reached() -> bool:
                        nonlocal progress_evidence
                        if capture.target_batch is not None:
                            return True
                        if progress_evidence is None:
                            progress_evidence = capture_stop_progress_evidence(
                                capture,
                                action=action,
                                stop_action=stop_action,
                                expected_axis=expected_axis,
                            )
                        return progress_evidence is not None

                    wait_for_state_with_runtime_checks(
                        args,
                        capture,
                        expected_pid=initial_runtime["pid"],
                        predicate=stop_progress_reached,
                        timeout=args.stop_progress_timeout,
                        description=(
                            f"{action} CReel::setStopAngle axis {expected_axis} and "
                            f"state+0x64 progress mask 0x{STOP_PROGRESS_MASKS[action]:08x}"
                        ),
                    )
                    if progress_evidence is not None:
                        stop_action.update(progress_evidence)
                    if capture.target_batch is not None:
                        break
                    if stop_index < len(stop_actions) - 1:
                        progress_age = state_age(capture)
                        if progress_age is None:
                            raise HuntError(
                                f"{action} progress was observed without a state age"
                            )
                        wait_for_state_with_runtime_checks(
                            args,
                            capture,
                            expected_pid=initial_runtime["pid"],
                            predicate=lambda: capture.target_batch is not None
                            or (
                                is_stop_engine_ready(
                                    capture,
                                    progress_age + args.inter_stop_settle_steps,
                                )
                            ),
                            timeout=args.ready_state_timeout,
                            description=(
                                "released spin state 3/3 and post-stop settle steps "
                                "before the next stop input"
                            ),
                        )

                wait_for_state_with_runtime_checks(
                    args,
                    capture,
                    expected_pid=initial_runtime["pid"],
                    predicate=lambda: capture.target_batch is not None
                    or is_bettable_state(capture),
                    timeout=args.round_timeout,
                    description="target dispatch batch or natural return to bettable 0/0 or 1/1",
                )
                if capture.target_batch is not None:
                    capture.record_outer_bgm_snapshot("target_window")
                    capture.pump_for(args.post_hit_seconds)
                    require_same_runtime(args, initial_runtime["pid"])
                    capture.record_outer_bgm_snapshot("attempt_post")
                    outcome = "target_hit" if not capture.buffer_overflow else "target_hit_buffer_overflow"
                    row = compact_attempt_summary(
                        attempt=attempt,
                        started_unix_ms=started_unix_ms,
                        outcome=outcome,
                        actions=actions,
                        capture=capture,
                    )
                    append_journal(journal_path, row)
                    target_dir = write_target_package(
                        args,
                        capture,
                        attempt=attempt,
                        runtime_state=initial_runtime,
                        actions=actions,
                        journal_path=journal_path,
                    )
                    print(
                        json.dumps(
                            {
                                "ok": not capture.buffer_overflow,
                                "target_hit": True,
                                "attempt": attempt,
                                "target_dir": str(target_dir),
                                "journal": str(journal_path),
                            },
                            ensure_ascii=False,
                        )
                    )
                    return 0 if not capture.buffer_overflow else 2

                capture.record_outer_bgm_snapshot("attempt_post")
                append_journal(
                    journal_path,
                    compact_attempt_summary(
                        attempt=attempt,
                        started_unix_ms=started_unix_ms,
                        outcome="non_target",
                        actions=actions,
                        capture=capture,
                    ),
                )
            except Exception as error:
                capture.record_outer_bgm_snapshot("attempt_post_error")
                append_journal(
                    journal_path,
                    compact_attempt_summary(
                        attempt=attempt,
                        started_unix_ms=started_unix_ms,
                        outcome="attempt_error",
                        actions=actions,
                        capture=capture,
                        error=repr(error),
                    ),
                )
                raise
            finally:
                if capture.target_batch is None:
                    capture.end_attempt()

        append_journal(
            journal_path,
            {
                "schema": "magireco-natural-sp-story-hunt-session-v1",
                "host_unix_ms": int(time.time() * 1000),
                "event": "max_attempts_reached",
                "attempts": attempt,
                "target_hit": False,
            },
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "target_hit": False,
                    "attempts": attempt,
                    "journal": str(journal_path),
                }
            )
        )
        return 0
    except Exception as error:
        append_journal(
            journal_path,
            {
                "schema": "magireco-natural-sp-story-hunt-session-v1",
                "host_unix_ms": int(time.time() * 1000),
                "event": "fatal_error",
                "error": repr(error),
            },
        )
        print(json.dumps({"ok": False, "error": repr(error), "journal": str(journal_path)}))
        return 1
    finally:
        if capture is not None:
            capture.close()


if __name__ == "__main__":
    raise SystemExit(main())
