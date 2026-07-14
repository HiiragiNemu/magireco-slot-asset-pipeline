from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.summarize_lightweight_spin_probe import (
    DispatchBatchTracker,
    changed_addressed_byte_summary,
    packet_row,
    payload_bytes,
    summarize,
    write_csv,
)
from tools.frida_runtime_probe.resolve_official_event_capture import BGM_CONTROL_KINDS


def access_record(raw: list[int], unix_ms: int, **fields: object) -> dict:
    payload = {"kind": "id401_access_subprocess", "unix_ms": unix_ms, **fields}
    for index, value in enumerate(raw):
        payload[f"id401_raw_packet_u8_at_{index}"] = value
    return {"host_unix_ms": unix_ms, "message": {"payload": payload}}


def event_record(kind: str, unix_ms: int, **fields: object) -> dict:
    payload = {"kind": kind, "unix_ms": unix_ms, **fields}
    return {"host_unix_ms": unix_ms, "message": {"payload": payload}}


class PacketCandidateTests(unittest.TestCase):
    def test_packet_id_masks_dispatch_flag(self) -> None:
        story = packet_row(
            line=1,
            rel_time=0.0,
            source_kind="id401_access_subprocess",
            source_field="id401_access_subprocess_raw",
            offset=None,
            raw=[0x93, 8, 0, 0, 0, 0, 0, 0],
        )
        selection = packet_row(
            line=2,
            rel_time=0.1,
            source_kind="id401_access_subprocess",
            source_field="id401_access_subprocess_raw",
            offset=None,
            raw=[0x98, 0, 2, 11, 0, 0, 0, 0],
        )
        self.assertEqual(story["packet_id"], 19)
        self.assertTrue(story["story_dispatch_candidate"])
        self.assertEqual(selection["packet_id"], 24)
        self.assertTrue(selection["sp_story_selection_candidate"])

    def test_stage_selector_pairs_are_not_cartesian_product(self) -> None:
        valid = {
            11: {1, 2},
            12: {1, 2, 3, 4, 13, 14},
            13: {1, 2},
        }
        for stage in (11, 12, 13):
            for selector in (1, 2, 3, 4, 13, 14):
                row = packet_row(
                    line=1,
                    rel_time=0.0,
                    source_kind="test",
                    source_field="test",
                    offset=None,
                    raw=[24, 0, selector, stage, 0, 0, 0, 0],
                )
                self.assertEqual(
                    row["sp_story_selection_candidate"],
                    selector in valid[stage],
                    (stage, selector),
                )


class SummarySemanticsTests(unittest.TestCase):
    def test_strict_live_tracker_requires_one_real_buffer_batch(self) -> None:
        tracker = DispatchBatchTracker(strict=True)
        tracker.register_get_cmd_buf(
            {
                "thread_id": 7,
                "id401_command_buffer_pointer": "0x1000",
                "id401_command_buffer_length": 16,
            },
            line=1,
            rel_time=None,
        )
        story = {
            "thread_id": 7,
            "id401_packet_pointer": "0x1000",
            **{f"id401_raw_packet_u8_at_{i}": value for i, value in enumerate(
                [19, 8, 0, 0, 0, 0, 0, 19]
            )},
        }
        selection = {
            "thread_id": 7,
            "id401_packet_pointer": "0x1008",
            **{f"id401_raw_packet_u8_at_{i}": value for i, value in enumerate(
                [24, 0, 2, 11, 0, 0, 0, 24]
            )},
        }
        _row, complete = tracker.observe_access(
            story,
            line=2,
            rel_time=None,
            source_kind="id401_access_subprocess",
        )
        self.assertIsNone(complete)
        _row, complete = tracker.observe_access(
            selection,
            line=3,
            rel_time=None,
            source_kind="id401_access_subprocess",
        )
        self.assertIsNotNone(complete)
        self.assertEqual(
            complete["sp_story_selection_pairs"],
            [{"stage": 11, "selector": 2}],
        )

    def test_strict_live_tracker_refreshes_complete_batch_with_late_selectors(self) -> None:
        tracker = DispatchBatchTracker(strict=True)
        tracker.register_get_cmd_buf(
            {
                "thread_id": 12,
                "id401_command_buffer_pointer": "0x2000",
                "id401_command_buffer_length": 56,
            },
            line=1,
            rel_time=None,
        )

        packets = [
            [19, 8, 0, 0, 0, 0, 0, 19],
            [24, 0, 13, 12, 0, 0, 0, 24],
            [24, 0, 14, 12, 0, 0, 0, 24],
            [24, 0, 1, 12, 0, 0, 0, 24],
            [24, 0, 2, 12, 0, 0, 0, 24],
            [24, 0, 3, 12, 0, 0, 0, 24],
            [24, 0, 4, 12, 0, 0, 0, 24],
        ]
        complete = None
        for index, raw in enumerate(packets):
            payload = {
                "thread_id": 12,
                "id401_packet_pointer": hex(0x2000 + index * 8),
                **{
                    f"id401_raw_packet_u8_at_{offset}": value
                    for offset, value in enumerate(raw)
                },
            }
            _row, observed_complete = tracker.observe_access(
                payload,
                line=index + 2,
                rel_time=None,
                source_kind="id401_access_subprocess",
            )
            if index == 0:
                self.assertIsNone(observed_complete)
            else:
                self.assertIsNotNone(observed_complete)
                complete = observed_complete

        self.assertIsNotNone(complete)
        self.assertEqual(
            complete["sp_story_selection_pairs"],
            [
                {"stage": 12, "selector": 13},
                {"stage": 12, "selector": 14},
                {"stage": 12, "selector": 1},
                {"stage": 12, "selector": 2},
                {"stage": 12, "selector": 3},
                {"stage": 12, "selector": 4},
            ],
        )

    def test_strict_live_tracker_rejects_packet_past_buffer_tail(self) -> None:
        tracker = DispatchBatchTracker(strict=True)
        tracker.register_get_cmd_buf(
            {
                "thread_id": 7,
                "id401_command_buffer_pointer": "0x3000",
                "id401_command_buffer_length": 12,
            },
            line=1,
            rel_time=None,
        )
        story = {
            "thread_id": 7,
            "id401_packet_pointer": "0x3000",
            **{
                f"id401_raw_packet_u8_at_{index}": value
                for index, value in enumerate([19, 8, 0, 0, 0, 0, 0, 19])
            },
        }
        selection_past_tail = {
            "thread_id": 7,
            "id401_packet_pointer": "0x3008",
            **{
                f"id401_raw_packet_u8_at_{index}": value
                for index, value in enumerate([24, 0, 1, 11, 0, 0, 0, 24])
            },
        }

        _row, complete = tracker.observe_access(
            story,
            line=2,
            rel_time=None,
            source_kind="id401_access_subprocess",
        )
        self.assertIsNone(complete)
        row, complete = tracker.observe_access(
            selection_past_tail,
            line=3,
            rel_time=None,
            source_kind="id401_access_subprocess",
        )
        self.assertIsNone(complete)
        self.assertEqual(row["dispatch_batch"], "")
        self.assertFalse(tracker.batch_summary(1)["complete_sp_story_candidate"])

    def test_dispatch_batches_ignore_repeated_snapshots(self) -> None:
        records = [
            event_record("id401_get_cmd_buf_leave", 1000),
            access_record([0x93, 8, 0, 0, 0, 0, 0, 19], 1001),
            access_record([0x98, 0, 1, 11, 0, 0, 0, 24], 1002),
            event_record(
                "lc701a_opcode_0x7e_command_state_change",
                1003,
                state_after={
                    "id401_staging_packets_at_0xf298": [
                        {"offset": 0, "raw": [0x93, 8, 0, 0, 0, 0, 0, 19]},
                        {"offset": 8, "raw": [0x98, 0, 1, 11, 0, 0, 0, 24]},
                    ]
                },
            ),
            event_record("id401_get_cmd_buf_leave", 1010),
            access_record([24, 0, 13, 11, 0, 0, 0, 24], 1011),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "observer.jsonl"
            path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n{",
                encoding="utf-8",
            )
            summary, tables = summarize(path)

        self.assertGreater(summary["packet_observation_count"], 3)
        self.assertEqual(summary["access_subprocess_dispatch_count"], 3)
        self.assertEqual(summary["dirinfo3_dispatch_count"], 1)
        self.assertEqual(summary["dirinfo8_dispatch_count"], 2)
        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["sp_story_selection_candidate_count"], 1)
        self.assertEqual(summary["complete_sp_story_batch_candidate_count"], 1)
        self.assertEqual(len(tables["dispatch_batches"]), 2)
        self.assertEqual(len(summary["parse_errors"]), 1)

    def test_legacy_bgm_kind_and_strict_pending_mutation(self) -> None:
        records = [
            event_record("direction_macro_snd_bgm_play", 1000),
            event_record(
                "direction_macro_snd_bgm_play_leave",
                1001,
                direction_queue_changed=False,
                direction_queue_state_u16_at_0x10=1,
                direction_queue_code0_text_utf8="814",
            ),
            event_record(
                "direction_macro_snd_bgm_play_leave",
                1002,
                direction_queue_changed=True,
                direction_queue_state_u16_at_0x10=1,
                direction_queue_code0_text_utf8="295",
            ),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "observer.jsonl"
            path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            summary, _tables = summarize(path)

        self.assertEqual(summary["bgm_event_count"], 3)
        self.assertEqual(summary["bgm_pending_queue_mutation_count"], 1)

    def test_direct_buffer_and_thread_scoped_dispatch_batches(self) -> None:
        records = [
            event_record(
                "id401_get_cmd_buf_leave",
                1000,
                thread_id=7,
                high_level_call_count_for_kind=4,
                id401_command_buffer_pointer="0x1000",
                id401_command_buffer_length=16,
                id401_command_buffer_packets=[
                    {"offset": 0, "raw": [19, 8, 0, 0, 0, 0, 0, 19]},
                    {"offset": 8, "raw": [24, 0, 1, 11, 0, 0, 0, 24]},
                ],
            ),
            event_record(
                "id401_get_cmd_buf_leave",
                1001,
                thread_id=8,
                high_level_call_count_for_kind=9,
                id401_command_buffer_pointer="0x2000",
                id401_command_buffer_length=8,
                id401_command_buffer_packets=[
                    {"offset": 0, "raw": [4, 0, 0, 0, 0, 0, 0, 4]},
                ],
            ),
            access_record(
                [19, 8, 0, 0, 0, 0, 0, 19],
                1002,
                thread_id=7,
                id401_packet_pointer="0x1000",
            ),
            access_record(
                [24, 0, 1, 11, 0, 0, 0, 24],
                1003,
                thread_id=7,
                id401_packet_pointer="0x1008",
            ),
            access_record(
                [4, 0, 0, 0, 0, 0, 0, 4],
                1004,
                thread_id=8,
                id401_packet_pointer="0x2000",
            ),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "observer.jsonl"
            path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            summary, tables = summarize(path)

        self.assertEqual(summary["copied_buffer_packet_observation_count"], 3)
        self.assertEqual(summary["snapshot_packet_observation_count"], 0)
        self.assertEqual(summary["access_subprocess_dispatch_count"], 3)
        self.assertEqual(summary["complete_sp_story_batch_candidate_count"], 1)
        self.assertEqual(tables["dispatch_packets"][0]["dispatch_batch"], 1)
        self.assertEqual(tables["dispatch_packets"][2]["dispatch_batch"], 2)
        self.assertEqual(tables["dispatch_batches"][0]["thread_id"], 7)
        self.assertEqual(tables["dispatch_batches"][0]["command_buffer_pointer"], "0x1000")

    def test_unattributed_thread_does_not_create_complete_batch(self) -> None:
        records = [
            access_record(
                [19, 8, 0, 0, 0, 0, 0, 19],
                1000,
                thread_id=99,
                id401_packet_pointer="0x9000",
            ),
            access_record(
                [24, 0, 1, 11, 0, 0, 0, 24],
                1001,
                thread_id=99,
                id401_packet_pointer="0x9008",
            ),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "observer.jsonl"
            path.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            summary, tables = summarize(path)

        self.assertEqual(summary["access_subprocess_dispatch_count"], 2)
        self.assertEqual(summary["complete_sp_story_batch_candidate_count"], 0)
        self.assertEqual(tables["dispatch_batches"], [])

    def test_null_rxcom_payload_byte_is_ignored(self) -> None:
        payload = {f"rxcom_payload_u8_at_{index}": index for index in range(8)}
        payload["rxcom_payload_u8_at_3"] = None
        self.assertIsNone(payload_bytes(payload, "rxcom_payload_u8_at_"))

    def test_moving_stack_window_diff_uses_absolute_addresses(self) -> None:
        summary = changed_addressed_byte_summary(
            [1, 2, 3], 0xFFDC, [3, 4, 5], 0xFFDE
        )
        self.assertEqual(
            summary,
            "0xffdc:1->None;0xffdd:2->None;0xffdf:None->4;0xffe0:None->5",
        )

    def test_csv_serializes_all_structured_values_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rows.csv"
            write_csv(path, [{"value": [1, 2], "meta": {"a": 3}}], ["value", "meta"])
            with path.open("r", encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
        self.assertEqual(row["value"], "[1,2]")
        self.assertEqual(row["meta"], '{"a":3}')

    def test_resolver_deduplicates_new_bgm_enter_leave_pair(self) -> None:
        self.assertNotIn("direction_macro_snd_bgm_play_enter", BGM_CONTROL_KINDS)
        self.assertIn("direction_macro_snd_bgm_play_leave", BGM_CONTROL_KINDS)
        self.assertIn("direction_macro_snd_bgm_play", BGM_CONTROL_KINDS)


class ProbeSourceRegressionTests(unittest.TestCase):
    def test_call_target_and_stack_bounds_are_emitted(self) -> None:
        probe = (
            Path(__file__).parent
            / "tools"
            / "frida_runtime_probe"
            / "lightweight_spin_audio_probe.js"
        ).read_text(encoding="utf-8")
        self.assertIn("spValue >= 0x4000 && spValue <= 0xffff", probe)
        self.assertIn("(state.lc701a_stack_window_bytes || []).join", probe)
        self.assertIn("lc701a_call_target_u16: this.callTargetU16", probe)
        self.assertIn('attachLC701ACoreStateChange(entry[0], entry[1])', probe)


if __name__ == "__main__":
    unittest.main()
