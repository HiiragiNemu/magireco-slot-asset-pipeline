from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_PATH = (
    ROOT / "tools" / "frida_runtime_probe" / "summarize_sound_logic_chain_probe.py"
)
SPEC = importlib.util.spec_from_file_location("summarize_sound_logic_chain_probe", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def wrapped(payload: dict, host_ms: int | None = None) -> dict:
    return {
        "host_unix_ms": host_ms or payload.get("unix_ms", 0),
        "message": {"type": "send", "payload": payload},
    }


def write_jsonl(path: Path, records: list[dict | str]) -> None:
    lines = [item if isinstance(item, str) else json.dumps(item) for item in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class SoundLogicSummaryTests(unittest.TestCase):
    def make_manifests(self, root: Path) -> dict[str, Path]:
        requests = root / "sound_request_struct_requests.csv"
        reqdata = root / "sound_request_struct_reqdata.csv"
        sound_ids = root / "sound_id_records.csv"
        timeline = root / "event_timeline_events.csv"
        write_csv(
            requests,
            [
                {"request_id": "344", "code_name": "814", "first_smz_media": "bgm.smz"},
                {
                    "request_id": "774",
                    "code_name": "2701_やちよﾓﾃﾞﾙ導入_001",
                    "first_smz_media": "voice.smz",
                },
            ],
        )
        write_csv(
            reqdata,
            [
                {
                    "request_id": "344",
                    "code_name": "814",
                    "smz_media": "bgm.smz",
                    "reqdata_group_or_channel": "1",
                },
                {
                    "request_id": "774",
                    "code_name": "2701_やちよﾓﾃﾞﾙ導入_001",
                    "smz_media": "voice.smz",
                    "reqdata_group_or_channel": "1",
                },
            ],
        )
        write_csv(
            sound_ids,
            [
                {
                    "sound_resource_id": "814",
                    "ogg_chunk_index": "287",
                    "suggested_name": "snd_00814_bank01_ogg_00287.ogg",
                },
                {
                    "sound_resource_id": "2701",
                    "ogg_chunk_index": "6758",
                    "suggested_name": "snd_02701_bank03_ogg_06758.ogg",
                },
            ],
        )
        write_csv(
            timeline,
            [
                {
                    "primary_animation": "ac0910_001",
                    "sound_request_ids": "774",
                    "sound_codes": "2701",
                }
            ],
        )
        return {
            "sound_requests_csv": requests,
            "sound_reqdata_csv": reqdata,
            "sound_id_records_csv": sound_ids,
            "event_timeline_csv": timeline,
        }

    def test_exact_nested_chains_validate_bgm_and_event_sound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.make_manifests(root)
            log = root / "probe.jsonl"
            records: list[dict | str] = []
            for index, (request_id, code, channel, resource_id, final_id) in enumerate(
                [
                    (344, "814", 0, 814, 287),
                    (774, "2701_やちよﾓﾃﾞﾙ導入_001", 2, 2701, 6758),
                ]
            ):
                timestamp = 1000 + index * 100
                records.extend(
                    [
                        wrapped(
                            {
                                "kind": "sound_logic_player_perform_request",
                                "unix_ms": timestamp,
                                "thread_id": 7,
                                "order_request_id_u32": request_id,
                                "order_code": code,
                                "order_association_basis": "req_order_u32_at_0x28_static_join_key",
                                "order": {
                                    "raw_u32_at_0x28": request_id,
                                    "function_type_name": "PLAY",
                                    "player_channel_i32": channel,
                                    "req_order_pointer": f"0x{request_id:x}",
                                },
                            }
                        ),
                        wrapped(
                            {
                                "kind": "sound_logic_sound_mng_snd_play_req_enter",
                                "unix_ms": timestamp + 1,
                                "thread_id": 7,
                                "sound_resource_id_i32": resource_id,
                                "play_index_or_bank_i32": channel + 1,
                                "perform_order_request_id_u32": request_id,
                                "perform_order_code": code,
                                "perform_function_type_name": "PLAY",
                                "perform_player_channel_i32": channel,
                                "perform_association_basis": "nested_within_perform_request",
                            }
                        ),
                        wrapped(
                            {
                                "kind": "sound_logic_csl_mng_play_start",
                                "unix_ms": timestamp + 20,
                                "thread_id": 8,
                                "play_index_i32": channel + 1,
                                "sound": {"final_sound_id_u16_at_0x02": final_id},
                                "causal_association_basis": "none_static_sound_id_join_required",
                            }
                        ),
                    ]
                )
            write_jsonl(log, records)

            summary, tables = MODULE.summarize(log, **paths)

            self.assertEqual(summary["complete_chain_count"], 2)
            by_request = {row["request_id"]: row for row in tables["chains"]}
            self.assertEqual(by_request["344"]["code_name"], "814")
            self.assertEqual(by_request["344"]["player_channel"], "0")
            self.assertEqual(by_request["344"]["sound_resource_id"], "814")
            self.assertEqual(by_request["344"]["runtime_observed_final_sound_ids"], "287")
            self.assertEqual(by_request["774"]["sound_resource_id"], "2701")
            self.assertEqual(by_request["774"]["runtime_observed_final_sound_ids"], "6758")
            self.assertEqual(by_request["774"]["event_names"], "ac0910_001")
            self.assertTrue(
                all(
                    row["request_to_resource_basis"]
                    == "runtime_same_thread_nested_within_perform_request"
                    for row in tables["chains"]
                )
            )

    def test_legacy_recent_context_is_rejected_and_not_chained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.make_manifests(root)
            log = root / "legacy.jsonl"
            write_jsonl(
                log,
                [
                    wrapped(
                        {
                            "kind": "sound_logic_player_perform_request",
                            "unix_ms": 1,
                            "thread_id": 7,
                            "order": {
                                "raw_u32_at_0x28": 344,
                                "function_type_name": "PLAY",
                                "player_channel_i32": 0,
                            },
                            "context_request_id": 100,
                            "context_code": "295",
                            "context_association_basis": "same_thread_recent",
                        }
                    ),
                    wrapped(
                        {
                            "kind": "sound_logic_sound_mng_snd_play_req_enter",
                            "unix_ms": 2,
                            "thread_id": 7,
                            "sound_resource_id_i32": 814,
                            "context_request_id": 100,
                            "context_code": "295",
                            "context_association_basis": "same_thread_recent",
                        }
                    ),
                    wrapped(
                        {
                            "kind": "sound_logic_csl_mng_play_start",
                            "unix_ms": 3,
                            "thread_id": 8,
                            "sound": {"final_sound_id_u16_at_0x02": 287},
                            "context_request_id": 100,
                            "context_code": "295",
                            "context_association_basis": "global_recent_window",
                        }
                    ),
                ],
            )

            summary, tables = MODULE.summarize(log, **paths)

            self.assertEqual(summary["complete_chain_count"], 0)
            self.assertEqual(tables["chains"], [])
            play = tables["nested_play_requests"][0]
            self.assertEqual(play["request_id"], "")
            self.assertEqual(play["association_basis"], "legacy_temporal_context_rejected")
            self.assertEqual(play["legacy_context_request_id_ignored"], "100")
            csl = tables["csl_play_starts"][0]
            self.assertEqual(csl["causal_request_id"], "")
            self.assertEqual(
                csl["causal_request_association_basis"], "legacy_temporal_context_rejected"
            )
            self.assertEqual(csl["static_sound_resource_ids"], "814")

    def test_set_request_uses_reqdata_own_id_not_legacy_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.make_manifests(root)
            log = root / "set.jsonl"
            write_jsonl(
                log,
                [
                    wrapped(
                        {
                            "kind": "sound_logic_request_ctrl_set_request_list",
                            "unix_ms": 1,
                            "thread_id": 7,
                            "request_id_i32": 100,
                            "context_request_id": 100,
                            "context_code": "295",
                            "context_association_basis": "same_thread_recent",
                            "request": {
                                "request_pointer": "0x1234",
                                "request_code_name_utf8": "",
                                "reqdata_count": 1,
                                "reqdata_rows": [
                                    {
                                        "reqdata_index": 0,
                                        "own_id_u32_at_0x48": 774,
                                        "function_type_name": "PLAY",
                                        "channel_hex_at_0x00": "0x2",
                                    }
                                ],
                            },
                        }
                    )
                ],
            )

            _, tables = MODULE.summarize(log, **paths)

            row = tables["set_requests"][0]
            self.assertEqual(row["request_id"], "774")
            self.assertEqual(row["association_basis"], "runtime_reqdata_own_id")
            self.assertNotEqual(row["request_id"], "100")

    def test_malformed_and_non_event_lines_do_not_abort_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = root / "mixed.jsonl"
            write_jsonl(
                log,
                [
                    "{truncated",
                    {"host_unix_ms": 1, "event": "host_attached"},
                    {
                        "kind": "sound_logic_code_name_to_request_id",
                        "unix_ms": 2,
                        "request_id_i32": 344,
                        "code_string": "814",
                    },
                    "",
                ],
            )

            summary, tables = MODULE.summarize(log)

            self.assertEqual(summary["parse"]["invalid_json_line_count"], 1)
            self.assertEqual(summary["parse"]["non_event_line_count"], 1)
            self.assertEqual(len(tables["code_mappings"]), 1)

    def test_write_outputs_contains_all_audit_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log = root / "empty.jsonl"
            log.write_text("", encoding="utf-8")
            summary, tables = MODULE.summarize(log)
            out = root / "out"

            MODULE.write_outputs(out, summary, tables, "test")

            self.assertTrue((out / "test_summary.json").is_file())
            for table_name, suffix in MODULE.OUTPUT_TABLES.items():
                path = out / f"test_{suffix}"
                self.assertTrue(path.is_file())
                self.assertIn(
                    "association_basis",
                    path.read_text(encoding="utf-8-sig").splitlines()[0],
                    table_name,
                )


if __name__ == "__main__":
    unittest.main()
