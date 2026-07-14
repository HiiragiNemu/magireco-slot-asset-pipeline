from __future__ import annotations

import argparse
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe.natural_sp_story_hunt import (
    HuntError,
    LiveCapture,
    capture_stop_progress_evidence,
    compact_attempt_summary,
    ensure_message_queue_caught_up,
    find_input_after,
    has_stop_progress,
    has_reel_stop_after,
    is_bettable_state,
    is_idle_armed_state,
    is_input_released,
    is_post_lever_state,
    is_spin_ready_state,
    is_stop_engine_ready,
    needs_max_bet,
    parse_coordinate,
    probe_source_provenance,
    tap_until_accepted,
    target_for_batch,
)


class NaturalSpStoryHuntTests(unittest.TestCase):
    def test_refresh_gate_snapshot_updates_passive_logical_state(self) -> None:
        class Exports:
            @staticmethod
            def snapshot() -> dict[str, object]:
                return {
                    "installed": True,
                    "event_count": 7,
                    "state": {
                        "slot_body_pointer": "0x1000",
                        "body_state_i32_at_0x00": 3,
                        "body_mode_i32_at_0x04": 3,
                    },
                }

        class Script:
            exports_sync = Exports()

        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.scripts["slot_gate"] = Script()
        state = capture.refresh_gate_snapshot()
        self.assertEqual(state["body_state_i32_at_0x00"], 3)
        self.assertEqual(state["body_mode_i32_at_0x04"], 3)

    def test_outer_bgm_snapshots_are_bounded_rpc_results_retained_by_attempt(self) -> None:
        class Exports:
            @staticmethod
            def outerbgmsnapshot(label: str) -> dict[str, object]:
                return {
                    "schema": "magireco-csl-active-sound-snapshot-v1",
                    "label": label,
                    "available": True,
                    "maximum_captured_slots": 128,
                    "active_rows": [
                        {
                            "sound_id_i32": 287,
                            "csl_resource_table_channel_i32": 0,
                            "csl_resource_table_channel_zero_candidate_only": True,
                            "bgm_semantics_proven": False,
                        }
                    ],
                }

        class Script:
            exports_sync = Exports()

        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.scripts["sound_logic"] = Script()
        capture.begin_attempt()
        for label in ("attempt_pre", "target_window", "attempt_post"):
            snapshot = capture.record_outer_bgm_snapshot(label)
            self.assertTrue(snapshot["available"])
            self.assertIn("captured_host_unix_ms", snapshot)
        row = compact_attempt_summary(
            attempt=1,
            started_unix_ms=1,
            outcome="test",
            actions=[],
            capture=capture,
        )
        snapshots = row["outer_bgm_active_sound_snapshots"]
        self.assertEqual([item["label"] for item in snapshots], [
            "attempt_pre", "target_window", "attempt_post"
        ])
        self.assertFalse(snapshots[1]["active_rows"][0]["bgm_semantics_proven"])

    def test_probe_ready_payload_and_exact_source_hashes_are_retained(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"dispatch": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        callback = capture._callback("dispatch")
        callback(
            {
                "type": "send",
                "payload": {
                    "kind": "sp_story_dispatch_hunt_probe_ready",
                    "installed": True,
                    "hook_status": {"id401_get_cmd_buf": {"status": "installed"}},
                },
            },
            None,
        )
        capture.pump(0.1)
        self.assertEqual(
            capture.ready_payloads["dispatch"]["hook_status"]["id401_get_cmd_buf"]["status"],
            "installed",
        )

        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "probe.js"
            probe.write_bytes(b"probe-source\n")
            provenance = probe_source_provenance({"dispatch": probe})
        self.assertEqual(provenance["dispatch"]["bytes"], 13)
        self.assertEqual(len(provenance["dispatch"]["sha256"]), 64)

    def test_stop_progress_witness_freezes_first_gate_snapshot(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.sequence = 42
        capture.latest_gate_state = {
            "state_u32_at_0x64": 0x00600000,
            "body_initialized_i32_at_0x08": 23,
        }
        capture.reel_stop_events = [
            {"sequence": 41, "host_unix_ms": 201, "axis_i32": 1}
        ]
        stop_action = {
            "issued_after_sequence": 20,
            "issued_host_unix_ms": 200,
        }
        evidence = capture_stop_progress_evidence(
            capture,
            action="middle_stop",
            stop_action=stop_action,
            expected_axis=1,
        )
        self.assertEqual(evidence["progress_observed_mask"], 0x00600000)
        self.assertEqual(evidence["progress_observed_sequence"], 42)
        self.assertEqual(evidence["progress_observed_state_age"], 23)
        self.assertEqual(evidence["progress_reel_stop_sequence"], 41)
        capture.latest_gate_state["state_u32_at_0x64"] = 0x00E00000
        self.assertEqual(
            evidence["progress_observed_gate_snapshot"]["state_u32_at_0x64"],
            0x00600000,
        )

    def test_hunt_source_records_all_outer_bgm_windows_and_session_provenance(self) -> None:
        source = (
            Path(__file__).resolve().parent
            / "tools"
            / "frida_runtime_probe"
            / "natural_sp_story_hunt.py"
        ).read_text(encoding="utf-8")
        for token in (
            'record_outer_bgm_snapshot("attempt_pre")',
            'record_outer_bgm_snapshot("target_window")',
            'record_outer_bgm_snapshot("attempt_post")',
            '"loaded_probe_sources": loaded_probe_sources',
            '"probe_ready_payloads": copy.deepcopy(capture.ready_payloads)',
            '"progress_observed_gate_snapshot"',
        ):
            self.assertIn(token, source)

    def test_target_matrix_excludes_ac7115_013_selectors(self) -> None:
        target = target_for_batch(
            {"sp_story_selection_pairs": [{"stage": 12, "selector": 4}]}
        )
        self.assertEqual(target["event"], "ac7115_001")
        self.assertEqual(target["event_code_hex"], "0x5773382374447854")
        self.assertIsNone(
            target_for_batch(
                {"sp_story_selection_pairs": [{"stage": 12, "selector": 13}]}
            )
        )
        self.assertIsNone(
            target_for_batch(
                {"sp_story_selection_pairs": [{"stage": 12, "selector": 14}]}
            )
        )

    def test_exact_event_code_is_required_after_selection_batch(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"dispatch": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.lever_eligible_after_sequence = 10
        capture.lever_eligible_after_host_unix_ms = 100
        capture.complete_candidates = [
            {
                "completion_sequence": 20,
                "completion_host_unix_ms": 200,
                "sp_story_selection_pairs": [{"stage": 13, "selector": 1}],
            }
        ]
        capture.observed_event_codes = [
            {
                "sequence": 15,
                "host_unix_ms": 150,
                "event_code_hex": "0x2476304366614152",
            },
            {
                "sequence": 30,
                "host_unix_ms": 300,
                "event_code_hex": "0x4f71466b3d723041",
            }
        ]
        capture._refresh_target()
        self.assertIsNotNone(capture.selection_candidate)
        # The matching code at sequence 15 is after the lever but before the
        # candidate completed at sequence 20, so it cannot prove this batch.
        self.assertIsNone(capture.target_batch)

        capture.observed_event_codes.append(
            {
                "sequence": 31,
                "host_unix_ms": 99,
                "event_code_hex": "0x2476304366614152",
            }
        )
        capture._refresh_target()
        self.assertIsNone(capture.target_batch)

        capture.observed_event_codes.append(
            {
                "sequence": 32,
                "host_unix_ms": 301,
                "event_code_hex": "0x2476304366614152",
            }
        )
        capture._refresh_target()
        self.assertEqual(
            capture.target_batch["resolved_event"]["event"],
            "ac7116_001",
        )

    def test_state_zero_and_idle_one_are_bettable(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        for state, mode, expected in ((0, 0, True), (1, 1, True), (3, 3, False)):
            capture.latest_gate_state = {
                "body_state_i32_at_0x00": state,
                "body_mode_i32_at_0x04": mode,
            }
            self.assertEqual(is_bettable_state(capture), expected)

    def test_fresh_zero_state_always_requires_max_bet_rearm(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        for state, mode, bet, age, input_mask, expected in (
            (0, 0, 3, 100, 0, True),
            (0, 0, 0, 100, 0, True),
            (1, 1, 2, 10, 0, True),
            (1, 1, 3, 0, 0, True),
            (1, 1, 3, 1, 1048576, True),
            (1, 1, 3, 1, 0, False),
        ):
            capture.latest_gate_state = {
                "body_state_i32_at_0x00": state,
                "body_mode_i32_at_0x04": mode,
                "body_bet_i32_at_0x58": bet,
                "body_initialized_i32_at_0x08": age,
                "body_input_mask_i32_at_0x408": input_mask,
                "body_button_state_i32_at_0x74": 0,
            }
            self.assertEqual(needs_max_bet(capture), expected)

    def test_logical_ready_states_require_release_and_one_state_step(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.latest_gate_state = {
            "body_state_i32_at_0x00": 1,
            "body_mode_i32_at_0x04": 1,
            "body_bet_i32_at_0x58": 3,
            "body_initialized_i32_at_0x08": 0,
            "body_input_mask_i32_at_0x408": 0,
            "body_button_state_i32_at_0x74": 0,
        }
        self.assertTrue(is_input_released(capture))
        self.assertFalse(is_idle_armed_state(capture))
        capture.latest_gate_state["body_initialized_i32_at_0x08"] = 1
        self.assertTrue(is_idle_armed_state(capture))

        capture.latest_gate_state.update(
            {
                "body_state_i32_at_0x00": 3,
                "body_mode_i32_at_0x04": 3,
                "body_input_mask_i32_at_0x408": 2,
            }
        )
        self.assertFalse(is_spin_ready_state(capture))
        capture.latest_gate_state["body_input_mask_i32_at_0x408"] = 0
        self.assertTrue(is_spin_ready_state(capture))
        self.assertFalse(is_spin_ready_state(capture, minimum_steps=2))
        capture.latest_gate_state["body_initialized_i32_at_0x08"] = 2
        self.assertTrue(is_spin_ready_state(capture, minimum_steps=2))

    def test_stop_input_requires_authoritative_progress_mask(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.latest_gate_state = {"state_u32_at_0x64": 0}
        self.assertFalse(has_stop_progress(capture, "left_stop"))
        capture.latest_gate_state["state_u32_at_0x64"] = 0x00200000
        self.assertTrue(has_stop_progress(capture, "left_stop"))
        self.assertFalse(has_stop_progress(capture, "middle_stop"))
        capture.latest_gate_state["state_u32_at_0x64"] = 0x00600000
        self.assertTrue(has_stop_progress(capture, "left_stop"))
        self.assertTrue(has_stop_progress(capture, "middle_stop"))
        self.assertFalse(has_stop_progress(capture, "right_stop"))
        capture.latest_gate_state["state_u32_at_0x64"] = 0x00E00000
        self.assertTrue(has_stop_progress(capture, "right_stop"))

    def test_stop_engine_uses_internal_wait_and_selected_axis_fields(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.latest_gate_state = {
            "body_state_i32_at_0x00": 3,
            "body_mode_i32_at_0x04": 3,
            "body_initialized_i32_at_0x08": 17,
            "body_input_mask_i32_at_0x408": 0,
            "body_button_state_i32_at_0x74": 0,
            "body_stop_wait16_i32_at_0x538": 16,
            "body_interstop_i32_at_0x53c": 5,
            "body_selected_axis_i32_at_0x540": -1,
        }
        self.assertTrue(is_stop_engine_ready(capture))
        capture.latest_gate_state["body_selected_axis_i32_at_0x540"] = 0
        self.assertFalse(is_stop_engine_ready(capture))
        capture.latest_gate_state["body_selected_axis_i32_at_0x540"] = -1
        capture.latest_gate_state["body_interstop_i32_at_0x53c"] = 4
        self.assertFalse(is_stop_engine_ready(capture))

    def test_reel_stop_axis_requires_post_input_waterline(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.reel_stop_events = [
            {"sequence": 10, "host_unix_ms": 200, "axis_i32": 0},
            {"sequence": 12, "host_unix_ms": 99, "axis_i32": 1},
            {"sequence": 13, "host_unix_ms": 201, "axis_i32": 1},
        ]
        self.assertTrue(
            has_reel_stop_after(
                capture,
                baseline_sequence=10,
                issued_host_unix_ms=100,
                expected_axis=1,
            )
        )
        self.assertFalse(
            has_reel_stop_after(
                capture,
                baseline_sequence=10,
                issued_host_unix_ms=100,
                expected_axis=2,
            )
        )

    def test_queue_catch_up_consumes_pre_input_callbacks(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        callback = capture._callback("slot_gate")
        callback(
            {
                "type": "send",
                "payload": {"kind": "slot_gate_probe_ready", "unix_ms": 10},
            },
            None,
        )
        self.assertEqual(capture.messages_enqueued, 1)
        self.assertEqual(capture.messages_processed, 0)
        waterline = ensure_message_queue_caught_up(capture, timeout=0.1)
        self.assertEqual(capture.messages_processed, 1)
        self.assertTrue(capture.events.empty())
        self.assertEqual(waterline["sequence"], 1)

    def test_latest_sdgm_state_is_retained_in_compact_summary(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"dispatch": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        callback = capture._callback("dispatch")
        callback(
            {
                "type": "send",
                "payload": {
                    "kind": "lot_sp_story_kind_enter",
                    "unix_ms": 10,
                    "sdgm_main_state_u16_at_0x13be": 16,
                },
            },
            None,
        )
        callback(
            {
                "type": "send",
                "payload": {
                    "kind": "lot_sp_story_kind_leave",
                    "unix_ms": 11,
                    "sdgm_sp_story_flag_u8_at_0x45a": 1,
                },
            },
            None,
        )
        ensure_message_queue_caught_up(capture, timeout=0.1)
        row = compact_attempt_summary(
            attempt=1,
            started_unix_ms=1,
            outcome="test",
            actions=[],
            capture=capture,
        )
        self.assertEqual(
            row["latest_sdgm_state"]["sdgm_main_state_u16_at_0x13be"],
            16,
        )
        self.assertEqual(
            row["latest_sdgm_state"]["sdgm_sp_story_flag_u8_at_0x45a"],
            1,
        )
        self.assertEqual(row["latest_sdgm_state"]["observed_sequence"], 2)

    def test_input_evidence_requires_tap_host_time_waterline(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.input_events = [
            {
                "sequence": 20,
                "host_unix_ms": 99,
                "payload": {"process_input_a_i32": 524288},
            },
            {
                "sequence": 21,
                "host_unix_ms": 101,
                "payload": {"process_input_a_i32": 524288},
            },
        ]
        expected, unexpected = find_input_after(
            capture,
            baseline_sequence=10,
            issued_host_unix_ms=100,
            expected_bit=524288,
        )
        self.assertIsNone(unexpected)
        self.assertEqual(expected["sequence"], 21)

    def test_missing_confirmation_never_repeats_tap(self) -> None:
        args = argparse.Namespace(
            execute=True,
            input_overall_timeout=1.0,
            input_confirm_timeout=0.0,
            queue_catch_up_timeout=0.1,
            press_duration_ms=500,
            adb="adb",
            device="emulator-5554",
        )
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch(
                "tools.frida_runtime_probe.natural_sp_story_hunt.require_same_runtime"
            ),
            patch(
                "tools.frida_runtime_probe.natural_sp_story_hunt.run_command",
                return_value=completed,
            ) as run,
        ):
            with self.assertRaisesRegex(HuntError, "input was not repeated"):
                tap_until_accepted(
                    args,
                    capture,
                    expected_pid=1,
                    action="lever",
                    coordinate=(330, 2720),
                )
        self.assertEqual(run.call_count, 1)

    def test_control_uses_one_bounded_stationary_swipe(self) -> None:
        args = argparse.Namespace(
            execute=True,
            input_overall_timeout=1.0,
            input_confirm_timeout=0.0,
            queue_catch_up_timeout=0.1,
            press_duration_ms=500,
            adb="adb",
            device="emulator-5554",
        )
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch(
                "tools.frida_runtime_probe.natural_sp_story_hunt.require_same_runtime"
            ),
            patch(
                "tools.frida_runtime_probe.natural_sp_story_hunt.run_command",
                return_value=completed,
            ) as run,
        ):
            with self.assertRaisesRegex(HuntError, "input was not repeated"):
                tap_until_accepted(
                    args,
                    capture,
                    expected_pid=1,
                    action="left_stop",
                    coordinate=(820, 2680),
                    expected_reel_axis=0,
                )
        self.assertEqual(run.call_count, 1)
        argv = run.call_args.args[0]
        self.assertEqual(argv[-8:], [
            "shell", "input", "swipe", "820", "2680", "820", "2680", "500"
        ])

    def test_stop_accepts_authoritative_reel_hook_when_process_callback_is_absent(self) -> None:
        args = argparse.Namespace(
            execute=True,
            input_overall_timeout=1.0,
            input_confirm_timeout=0.0,
            queue_catch_up_timeout=0.1,
            press_duration_ms=500,
            adb="adb",
            device="emulator-5554",
        )
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )

        def issue_gesture(_argv: list[str]) -> subprocess.CompletedProcess[str]:
            capture.reel_stop_events.append(
                {
                    "sequence": 1,
                    "host_unix_ms": 2**62,
                    "axis_i32": 0,
                }
            )
            return subprocess.CompletedProcess([], 0, "", "")

        with (
            patch(
                "tools.frida_runtime_probe.natural_sp_story_hunt.require_same_runtime"
            ),
            patch(
                "tools.frida_runtime_probe.natural_sp_story_hunt.run_command",
                side_effect=issue_gesture,
            ),
        ):
            row = tap_until_accepted(
                args,
                capture,
                expected_pid=1,
                action="left_stop",
                coordinate=(820, 2680),
                expected_reel_axis=0,
            )
        self.assertFalse(row["process_input_confirmed"])
        self.assertTrue(row["reel_stop_confirmed"])
        self.assertEqual(row["reel_stop_axis"], 0)

    def test_post_lever_gate_accepts_observed_transition_and_spin_samples(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"slot_gate": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        for state, mode, expected in (
            (1, 2, True),
            (3, 3, True),
            (1, 1, False),
            (0, 0, False),
        ):
            capture.latest_gate_state = {
                "body_state_i32_at_0x00": state,
                "body_mode_i32_at_0x04": mode,
            }
            self.assertEqual(is_post_lever_state(capture), expected)

    def test_default_mode_cannot_issue_adb_input(self) -> None:
        args = argparse.Namespace(execute=False)
        with self.assertRaises(HuntError):
            tap_until_accepted(
                args,
                LiveCapture(
                    host="127.0.0.1:27043",
                    expected_pid=1,
                    script_paths={"slot_gate": Path("probe.js")},
                    max_buffer_bytes=1024,
                ),
                expected_pid=1,
                action="lever",
                coordinate=(330, 2720),
            )

    def test_coordinate_parser_is_strict(self) -> None:
        self.assertEqual(parse_coordinate("0x14a,2720"), (330, 2720))
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_coordinate("-1,2")


if __name__ == "__main__":
    unittest.main()
