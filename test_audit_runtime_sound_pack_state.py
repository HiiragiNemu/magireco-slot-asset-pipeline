import csv
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

from test_extract_sound_pack_gate import CURRENT_REFERENCE_IDS


ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "tools" / "frida_runtime_probe" / "audit_runtime_sound_pack_state.py"
SPEC = importlib.util.spec_from_file_location("audit_runtime_sound_pack_state", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RuntimeSoundPackAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.gate = self.root / "gate.json"
        self.addon = self.root / "addon.json"
        self.sound_csv = self.root / "sound.csv"
        self.journal = self.root / "hunt.jsonl"
        self.out = self.root / "out"

        table_hash = hashlib.sha256(
            struct.pack(f"<{len(CURRENT_REFERENCE_IDS)}I", *CURRENT_REFERENCE_IDS)
        ).hexdigest()
        key_checks = [
            {
                "index": index,
                "expected": expected,
                "actual": expected,
                "matches": True,
            }
            for index, expected in MODULE.REFERENCE_GATE_KEYS.items()
        ]
        self.gate.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "evidence_kind": "read_only_static_sound_pack_gate",
                    "safety": {"read_only": True},
                    "lib_sha256": MODULE.REFERENCE_GAME_PROC_SHA256,
                    "table": {
                        "file_offset": "0x14458dc",
                        "file_offset_decimal": 0x14458DC,
                        "byte_length": 0x378,
                        "entry_size": 4,
                        "id_count": 222,
                        "unique_id_count": 222,
                        "ids_table_order": CURRENT_REFERENCE_IDS,
                        "table_sha256": table_hash,
                    },
                    "reference_comparison": {
                        "reference_application_id": "com.universal777.magireco",
                        "reference_version_name": "1.0.0",
                        "reference_version_code": 31,
                        "reference_table_sha256": table_hash,
                        "actual_table_sha256": table_hash,
                        "reference_id_count": 222,
                        "id_count_matches": True,
                        "sha256_matches": True,
                        "key_value_checks": key_checks,
                        "key_values_match": True,
                        "reference_vector_matches": True,
                        "library_sha256_matches": True,
                        "audited_v31_library_and_table_match": True,
                    },
                    "reference_policy": {
                        "audit_status": "audited_v31_reference_match",
                        "library_sha256_matches": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        self._write_addon(pid=7, active=0)
        with self.sound_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "sound_resource_id",
                    "sound_bank",
                    "ogg_duration_sec",
                    "request_label",
                    "suggested_name",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "sound_resource_id": "801",
                    "sound_bank": "1",
                    "ogg_duration_sec": "10.2",
                    "request_label": "",
                    "suggested_name": "snd_00801.ogg",
                }
            )
            writer.writerow(
                {
                    "sound_resource_id": "304",
                    "sound_bank": "2",
                    "ogg_duration_sec": "2.0",
                    "request_label": "",
                    "suggested_name": "snd_00304.ogg",
                }
            )
        self._write_journal(pid=7, gate_volume=0)

    def tearDown(self):
        self.temp.cleanup()

    def _write_addon(self, *, pid, active):
        rows = []
        for index in range(7):
            rows.append(
                {
                    "index": index,
                    "active_offset": f"0x{0x14BF4 + index * 4:x}",
                    "active_u32": active if index == 6 else 0,
                    "saved_offset": f"0x{0x14A58 + index * 4:x}",
                    "saved_u32": active if index == 6 else 0,
                    "active_read_error": "",
                    "saved_read_error": "",
                }
            )
        self.addon.write_text(
            json.dumps(
                {
                    "schema": "magireco-addon-entitlement-snapshot-v1",
                    "ok": True,
                    "process": {"id": pid, "arch": "arm64", "pointer_size": 8},
                    "active_addon_base_offset": "0x14bf4",
                    "saved_addon_base_offset": "0x14a58",
                    "sound_pack_candidate_index": 6,
                    "rows": rows,
                }
            ),
            encoding="utf-8",
        )

    def _write_journal(self, *, pid, gate_volume):
        accessor_status = {
            key: {
                "status": "ready",
                "actual_module_offset": offset,
                "expected_module_offset": offset,
                "module_offset_matches_static_reference": True,
            }
            for key, offset in MODULE.REFERENCE_ACCESSOR_OFFSETS.items()
        }
        pre_gate_key_checks = [
            {
                "index": index,
                "expected": expected,
                "actual": expected,
                "matches": True,
            }
            for index, expected in MODULE.REFERENCE_GATE_KEYS.items()
        ]
        sound_ready = {
            "kind": "sound_logic_probe_ready",
            "installed_hook_event_count": 7,
            "unavailable_hook_event_count": 0,
            "attach_error_event_count": 0,
            "outer_bgm_snapshot_accessors_ready": True,
            "outer_bgm_snapshot_accessor_status": accessor_status,
            "outer_bgm_snapshot_calc_entry_status": {
                "status": "ready",
                "actual_module_offset": MODULE.REFERENCE_CALC_OFFSET,
                "expected_module_offset": MODULE.REFERENCE_CALC_OFFSET,
                "module_offset_matches_static_reference": True,
            },
            "sound_pack_pre_gate_status": {
                "status": "ready",
                "symbol": "_ZN8SoundMng12changeVolumeEii",
                "actual_module_offset": MODULE.REFERENCE_CHANGE_VOLUME_OFFSET,
                "expected_module_offset": MODULE.REFERENCE_CHANGE_VOLUME_OFFSET,
                "module_offset_matches_static_reference": True,
                "gate_table_offset": "0x14458dc",
                "gate_table_entry_count": 222,
                "gate_table_strictly_increasing_unique": True,
                "gate_table_key_checks": pre_gate_key_checks,
                "read_only_observer": True,
            },
        }
        session = {
            "schema": "magireco-natural-sp-story-hunt-session-v1",
            "event": "session_ready",
            "runtime": {"pid": pid, "package": "pkg", "device": "dev"},
            "loaded_probe_sources": {
                "sound_logic": {
                    "path": "sound_logic_chain_probe.js",
                    "bytes": 1234,
                    "sha256": "A" * 64,
                }
            },
            "probe_ready_payloads": {"sound_logic": sound_ready},
        }
        snapshot_base = {
            "schema": "magireco-csl-active-sound-snapshot-v1",
            "available": True,
            "truncated": False,
            "declared_slot_count": 65,
            "captured_slot_count": 65,
            "snapshot_execution_source": "cslMngCalc_on_enter",
            "snapshot_runs_on_csl_calc_thread": True,
            "snapshot_hook_detached": True,
            "vector_begin_offset": 0xA0,
            "vector_end_offset": 0xA8,
            "active_slot_stride": 0x38,
            "maximum_captured_slots": 128,
            "capture_cap_is_declared_game_limit": False,
            "classification_rule": (
                "active_transport_state_only_csl_resource_table_channel_zero_is_not_bgm_proof"
            ),
            "static_reference": MODULE.REFERENCE_STATIC_SNAPSHOT,
            "accessor_status": accessor_status,
            "captured_host_unix_ms": 123,
        }
        session["initial_outer_bgm_active_sound_snapshot"] = {
            **snapshot_base,
            "label": "session_ready",
            "active_rows": [],
        }
        snapshot = {
            **snapshot_base,
            "label": "attempt_post",
            "active_rows": [
                {
                    "slot_index": 1,
                    "sound_id_i32": 801,
                    "csl_resource_table_channel_i32": 1,
                    "slot_volume_u32_at_0x10": gate_volume,
                    "transport_state": "playing",
                    "transport_playing_proven": True,
                    "transport_paused": False,
                    "sound_time_seconds": 1.5,
                    "sound_loop_flag_i32": 1,
                },
                {
                    "slot_index": 2,
                    "sound_id_i32": 304,
                    "csl_resource_table_channel_i32": 2,
                    "slot_volume_u32_at_0x10": 50,
                    "transport_state": "playing",
                    "transport_playing_proven": True,
                    "transport_paused": False,
                    "sound_time_seconds": 0.2,
                    "sound_loop_flag_i32": 0,
                },
            ],
        }
        attempt = {
            "schema": "magireco-natural-sp-story-hunt-attempt-v1",
            "attempt": 1,
            "outcome": "non_target",
            "sound_pack_pre_gate_volume_events": [
                {
                    "sequence": 10,
                    "first_sequence": 10,
                    "last_sequence": 10,
                    "observation_count": 1,
                    "sound_resource_id_i32": 801,
                    "volume_index_i32": 1,
                    "sound_pack_active_u32": 0,
                    "volume_class_u8": 0,
                    "class_volume_u16": 50,
                    "indexed_volume_u16": 100,
                    "master_volume_u16": 100,
                    "pre_gate_stage_volume_i32": 50,
                    "authorized_final_volume_i32": 50,
                    "current_gate_will_zero": True,
                    "reconstruction_complete": True,
                    "emission_reason": "direct_sound_request_call",
                    "return_module_offset": "0x425f160",
                    "return_symbol": "lib!_ZN8SoundMng10wrapSndReqEi+0xc4",
                }
            ],
            "outer_bgm_active_sound_snapshots": [snapshot],
        }
        terminal = {
            "schema": "magireco-natural-sp-story-hunt-session-v1",
            "event": "max_attempts_reached",
        }
        self.journal.write_text(
            "\n".join(json.dumps(row) for row in (session, attempt, terminal)) + "\n",
            encoding="utf-8",
        )

    def _args(self):
        return [
            "--journal",
            str(self.journal),
            "--sound-pack-gate-json",
            str(self.gate),
            "--addon-snapshot",
            str(self.addon),
            "--sound-request-audit",
            str(self.sound_csv),
            "--out-dir",
            str(self.out),
        ]

    def _journal_rows(self):
        return [json.loads(line) for line in self.journal.read_text(encoding="utf-8").splitlines()]

    def _replace_journal_rows(self, rows):
        self.journal.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
        )

    def _mutate_pre_gate(self, field, value):
        rows = self._journal_rows()
        rows[1]["sound_pack_pre_gate_volume_events"][0][field] = value
        self._replace_journal_rows(rows)

    def test_zero_volume_gate_row_is_corroborated(self):
        self.assertEqual(MODULE.main(self._args()), 0)
        audit = json.loads((self.out / MODULE.JSON_NAME).read_text(encoding="utf-8"))
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["summary"]["sound_pack_gate_unique_ids"], [801])
        self.assertEqual(
            audit["summary"]["unentitled_gate_corroborating_row_count"], 1
        )
        self.assertEqual(audit["summary"]["pre_gate_unique_sound_ids"], [801])
        self.assertEqual(
            audit["summary"]["pre_gate_authorized_final_volumes_by_sound_id"],
            {"801": [50]},
        )
        self.assertTrue((self.out / MODULE.PRE_GATE_CSV_NAME).is_file())
        gate_row = next(row for row in audit["rows"] if row["sound_id"] == 801)
        self.assertEqual(gate_row["sound_bank"], "1")
        self.assertEqual(
            gate_row["gate_runtime_interpretation"],
            "unentitled_gate_consistent_zero_volume",
        )

    def test_nonzero_unentitled_gate_row_is_fail_closed(self):
        self._write_journal(pid=7, gate_volume=50)
        self.assertEqual(MODULE.main(self._args()), 5)
        audit = json.loads((self.out / MODULE.JSON_NAME).read_text(encoding="utf-8"))
        self.assertFalse(audit["ok"])
        self.assertEqual(audit["summary"]["unentitled_gate_conflict_row_count"], 1)

    def test_reference_mismatch_produces_no_output(self):
        gate = json.loads(self.gate.read_text(encoding="utf-8"))
        gate["reference_comparison"]["reference_vector_matches"] = False
        self.gate.write_text(json.dumps(gate), encoding="utf-8")
        self.assertEqual(MODULE.main(self._args()), 4)
        self.assertFalse(self.out.exists())

    def test_full_library_hash_and_complete_table_are_recomputed(self):
        gate = json.loads(self.gate.read_text(encoding="utf-8"))
        gate["lib_sha256"] = "0" * 64
        self.gate.write_text(json.dumps(gate), encoding="utf-8")
        self.assertEqual(MODULE.main(self._args()), 4)
        self.assertFalse(self.out.exists())

    def test_session_ready_sound_probe_and_static_snapshot_are_required(self):
        rows = self._journal_rows()
        rows[0]["probe_ready_payloads"]["sound_logic"][
            "outer_bgm_snapshot_accessors_ready"
        ] = False
        self._replace_journal_rows(rows)
        self.assertEqual(MODULE.main(self._args()), 3)
        self.assertFalse(self.out.exists())

    def test_snapshot_only_legacy_session_may_lack_pre_gate_capability(self):
        rows = self._journal_rows()
        del rows[0]["probe_ready_payloads"]["sound_logic"][
            "sound_pack_pre_gate_status"
        ]
        rows[1]["sound_pack_pre_gate_volume_events"] = []
        self._replace_journal_rows(rows)

        self.assertEqual(MODULE.main(self._args()), 0)
        audit = json.loads((self.out / MODULE.JSON_NAME).read_text(encoding="utf-8"))
        source = audit["sources"]["journals"][0]
        self.assertFalse(source["sound_pack_pre_gate_events_present"])
        self.assertFalse(source["sound_pack_pre_gate_capability_verified"])

    def test_pre_gate_event_requires_ready_capability_proof(self):
        rows = self._journal_rows()
        del rows[0]["probe_ready_payloads"]["sound_logic"][
            "sound_pack_pre_gate_status"
        ]
        self._replace_journal_rows(rows)

        self.assertEqual(MODULE.main(self._args()), 3)
        self.assertFalse(self.out.exists())

    def test_snapshot_only_ignores_unused_legacy_pre_gate_payload(self):
        rows = self._journal_rows()
        rows[0]["probe_ready_payloads"]["sound_logic"][
            "sound_pack_pre_gate_status"
        ]["gate_table_key_checks"] = []
        rows[1]["sound_pack_pre_gate_volume_events"] = []
        self._replace_journal_rows(rows)

        self.assertEqual(MODULE.main(self._args()), 0)
        audit = json.loads((self.out / MODULE.JSON_NAME).read_text(encoding="utf-8"))
        source = audit["sources"]["journals"][0]
        self.assertFalse(source["sound_pack_pre_gate_events_present"])
        self.assertFalse(source["sound_pack_pre_gate_capability_verified"])

    def test_snapshot_static_reference_tamper_is_rejected(self):
        rows = self._journal_rows()
        rows[1]["outer_bgm_active_sound_snapshots"][0]["static_reference"][
            "game_proc_sha256"
        ] = "0" * 64
        self._replace_journal_rows(rows)
        self.assertEqual(MODULE.main(self._args()), 3)
        self.assertFalse(self.out.exists())

    def test_pre_gate_integer_chain_tamper_is_rejected(self):
        self._mutate_pre_gate("authorized_final_volume_i32", 49)
        self.assertEqual(MODULE.main(self._args()), 3)
        self.assertFalse(self.out.exists())

    def test_pre_gate_ranges_gate_boolean_caller_and_count_fail_closed(self):
        cases = (
            ("volume_index_i32", 64),
            ("current_gate_will_zero", False),
            ("return_module_offset", "0x123"),
            ("observation_count", 2),
        )
        baseline = self.journal.read_text(encoding="utf-8")
        for field, value in cases:
            with self.subTest(field=field):
                self.journal.write_text(baseline, encoding="utf-8")
                self._mutate_pre_gate(field, value)
                self.assertEqual(MODULE.main(self._args()), 3)
                self.assertFalse(self.out.exists())

    def test_pid_mismatch_produces_no_output(self):
        self._write_addon(pid=8, active=0)
        self.assertEqual(MODULE.main(self._args()), 3)
        self.assertFalse(self.out.exists())

    def test_refuses_output_overwrite(self):
        self.assertEqual(MODULE.main(self._args()), 0)
        before = (self.out / MODULE.JSON_NAME).read_bytes()
        self.assertEqual(MODULE.main(self._args()), 3)
        self.assertEqual((self.out / MODULE.JSON_NAME).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
