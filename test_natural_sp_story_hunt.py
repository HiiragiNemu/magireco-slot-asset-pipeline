from __future__ import annotations

import argparse
import copy
import hashlib
import struct
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe.natural_sp_story_hunt import (
    EXPECTED_ARM64_SPLIT_BASENAME,
    EXPECTED_ARM64_SPLIT_SHA256,
    EXPECTED_ARM64_SPLIT_SIZE_BYTES,
    EXPECTED_BGM_UPSTREAM_FIELD_SCHEMA,
    EXPECTED_BGM_UPSTREAM_HOOK_KEYS,
    EXPECTED_GAME_PROC_SHA256,
    EXPECTED_GAME_PROC_SIZE_BYTES,
    EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
    EXPECTED_GAME_PROC_APK_CRC32,
    EXPECTED_GAME_PROC_APK_DATA_OFFSET,
    EXPECTED_GAME_PROC_APK_ENTRY,
    EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET,
    EXPECTED_SOUND_CAPTURE_SCOPE,
    EXPECTED_SOUND_HOOKS,
    HuntError,
    LiveCapture,
    SOUND_PACK_REFERENCE_KEYS,
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
    parse_bound_game_proc_local_header,
    probe_source_provenance,
    tap_until_accepted,
    target_for_batch,
    validate_bgm_upstream_window_contract,
    validate_installed_arm64_split_identity,
    validate_probe_ready_contracts,
)


class NaturalSpStoryHuntTests(unittest.TestCase):
    @staticmethod
    def complete_installed_split_identity() -> dict[str, object]:
        device_path = f"/data/app/test/{EXPECTED_ARM64_SPLIT_BASENAME}"
        return {
            "schema": "magireco-installed-arm64-split-identity-v1",
            "device": "emulator-5554",
            "package": "com.universal777.magireco",
            "device_apk_path": device_path,
            "split_basename": EXPECTED_ARM64_SPLIT_BASENAME,
            "verification_method": (
                "host_sha256_over_adb_exec_out_cat_with_fixed_uncompressed_entry_range"
            ),
            "actual_apk_size_bytes": EXPECTED_ARM64_SPLIT_SIZE_BYTES,
            "expected_apk_size_bytes": EXPECTED_ARM64_SPLIT_SIZE_BYTES,
            "actual_apk_sha256": EXPECTED_ARM64_SPLIT_SHA256,
            "expected_apk_sha256": EXPECTED_ARM64_SPLIT_SHA256,
            "apk_size_matches": True,
            "apk_sha256_matches": True,
            "entry_path": EXPECTED_GAME_PROC_APK_ENTRY,
            "entry_compression_method": EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
            "entry_crc32": EXPECTED_GAME_PROC_APK_CRC32,
            "entry_local_header": {
                "signature_u32_le": "0x04034B50",
                "version_needed_u16": 0,
                "flag_bits_u16": 0,
                "compression_method_u16": EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
                "mod_time_u16": 2081,
                "mod_date_u16": 545,
                "crc32": EXPECTED_GAME_PROC_APK_CRC32,
                "compressed_size_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
                "uncompressed_size_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
                "filename_length": len(EXPECTED_GAME_PROC_APK_ENTRY.encode("utf-8")),
                "extra_length": 4054,
                "filename": EXPECTED_GAME_PROC_APK_ENTRY,
                "local_header_offset": EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET,
                "data_offset": EXPECTED_GAME_PROC_APK_DATA_OFFSET,
            },
            "entry_data_offset": EXPECTED_GAME_PROC_APK_DATA_OFFSET,
            "actual_entry_bytes_hashed": EXPECTED_GAME_PROC_SIZE_BYTES,
            "expected_entry_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
            "actual_entry_sha256": EXPECTED_GAME_PROC_SHA256,
            "expected_entry_sha256": EXPECTED_GAME_PROC_SHA256,
            "entry_sha256_matches": True,
            "entry_elf_prefix_hex": "7F454C460201010000000000000000000300B7",
            "entry_elf_header_matches_aarch64": True,
            "outer_digest_binds_local_header_layout": True,
            "read_only_adb_stream": True,
            "gameplay_input_sent": False,
            "device_state_modified": False,
        }

    @staticmethod
    def complete_ready_payloads() -> dict[str, dict[str, object]]:
        split_identity = NaturalSpStoryHuntTests.complete_installed_split_identity()
        device_path = str(split_identity["device_apk_path"])
        accessor_status = {
            f"accessor_{index}": {
                "status": "ready",
                "module_offset_matches_static_reference": True,
            }
            for index in range(8)
        }
        hook_status = {
            key: {
                "status": "installed",
                "hook_key": key,
                "symbol": symbol,
                "module": (
                    EXPECTED_ARM64_SPLIT_BASENAME
                    if key in EXPECTED_BGM_UPSTREAM_HOOK_KEYS
                    else "versioned-module"
                ),
                "module_path": (
                    device_path
                    if key in EXPECTED_BGM_UPSTREAM_HOOK_KEYS
                    else "/versioned/module"
                ),
                "derived_elf_base": (
                    "0x10000000" if key in EXPECTED_BGM_UPSTREAM_HOOK_KEYS else None
                ),
                "offset_basis": (
                    "known_export_minus_derived_game_proc_elf_base"
                    if key in EXPECTED_BGM_UPSTREAM_HOOK_KEYS
                    else "frida_reported_module_base"
                ),
                "actual_module_offset": offset,
                "expected_module_offset": offset,
                "module_offset_matches_static_reference": True,
                "module_identity_matches_static_reference": True,
            }
            for key, (symbol, offset) in EXPECTED_SOUND_HOOKS.items()
        }
        return {
            "slot_gate": {
                "installed": True,
                "process_hook_installed": True,
                "reel_stop_hook_installed": True,
            },
            "dispatch": {
                "installed": True,
                "required_hooks_installed": True,
                "optional_sound_event_hook_installed": True,
                "optional_lottery_hook_installed": True,
            },
            "sound_logic": {
                "installed_hook_event_count": len(EXPECTED_SOUND_HOOKS),
                "unavailable_hook_event_count": 0,
                "attach_error_event_count": 0,
                "hook_status": hook_status,
                "outer_bgm_snapshot_accessors_ready": True,
                "outer_bgm_snapshot_accessor_status": accessor_status,
                "outer_bgm_snapshot_calc_entry_status": {
                    "status": "ready",
                    "module_offset_matches_static_reference": True,
                },
                "capture_scope": dict(EXPECTED_SOUND_CAPTURE_SCOPE),
                "game_proc_identity_status": {
                    "status": "ready",
                    "mapping_kind": "apk_backed_uncompressed_elf",
                    "logical_library_name": "libGameProc.so",
                    "container_module": EXPECTED_ARM64_SPLIT_BASENAME,
                    "container_path": device_path,
                    "expected_container_module": EXPECTED_ARM64_SPLIT_BASENAME,
                    "container_name_matches": True,
                    "container_path_matches": True,
                    "reported_container_base": "0x10000000",
                    "derived_elf_base": "0x10000000",
                    "reported_base_matches_derived": True,
                    "anchor_symbol": "fnGetAddrSdGmData",
                    "anchor_address": "0x1424d474",
                    "actual_anchor_derived_elf_offset": "0x424d474",
                    "expected_anchor_offset": "0x424d474",
                    "reported_anchor_module_offset": "0x424d474",
                    "anchor_offset_matches": True,
                    "elf_header": {
                        "magic_u32_le_at_0x00": 0x464C457F,
                        "class_u8_at_0x04": 2,
                        "data_encoding_u8_at_0x05": 1,
                        "machine_u16_at_0x12": 183,
                    },
                    "elf_header_matches_aarch64": True,
                    "export_checks": [
                        {
                            "hook_key": key,
                            "symbol": EXPECTED_SOUND_HOOKS[key][0],
                            "address": "0x1",
                            "container_module": EXPECTED_ARM64_SPLIT_BASENAME,
                            "container_path": device_path,
                            "actual_derived_elf_offset": EXPECTED_SOUND_HOOKS[key][1],
                            "expected_elf_offset": EXPECTED_SOUND_HOOKS[key][1],
                            "offset_matches": True,
                            "same_apk_container": True,
                        }
                        for key in sorted(EXPECTED_BGM_UPSTREAM_HOOK_KEYS)
                    ],
                    "all_export_checks_match": True,
                    "installed_container_identity_required_from_host": True,
                    "expected_container_sha256": EXPECTED_ARM64_SPLIT_SHA256,
                    "expected_container_size_bytes": EXPECTED_ARM64_SPLIT_SIZE_BYTES,
                    "bound_apk_entry": {
                        "path": EXPECTED_GAME_PROC_APK_ENTRY,
                        "compression_method": EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
                        "crc32": EXPECTED_GAME_PROC_APK_CRC32,
                        "local_header_offset": EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET,
                        "data_offset": EXPECTED_GAME_PROC_APK_DATA_OFFSET,
                        "compressed_size_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
                        "uncompressed_size_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
                        "expected_uncompressed_sha256": EXPECTED_GAME_PROC_SHA256,
                    },
                    "read_only_verification": True,
                },
                "bgm_upstream_sdgm_accessor_status": {
                    "status": "ready",
                    "symbol": "fnGetAddrSdGmData",
                    "module": EXPECTED_ARM64_SPLIT_BASENAME,
                    "module_path": device_path,
                    "derived_elf_base": "0x10000000",
                    "actual_module_offset": "0x424d474",
                    "expected_module_offset": "0x424d474",
                    "module_offset_matches_static_reference": True,
                    "read_only_accessor": True,
                },
                "bgm_upstream_field_schema": copy.deepcopy(
                    EXPECTED_BGM_UPSTREAM_FIELD_SCHEMA
                ),
                "bgm_upstream_window_rpc": {
                    "schema": "magireco-target-bgm-upstream-window-v1",
                    "begin_export": "beginbgmupstreamattempt",
                    "end_export": "endbgmupstreamattempt",
                    "status_export": "bgmupstreamstatus",
                    "read_only_observer": True,
                },
                "sound_pack_pre_gate_status": {
                    "status": "ready",
                    "module_offset_matches_static_reference": True,
                    "gate_table_entry_count": 222,
                    "gate_table_strictly_increasing_unique": True,
                    "read_only_observer": True,
                    "repeated_unchanged_volume_control_calls_suppressed": True,
                    "gate_table_key_checks": [
                        {
                            "index": index,
                            "expected": value,
                            "actual": value,
                            "matches": True,
                        }
                        for index, value in SOUND_PACK_REFERENCE_KEYS.items()
                    ],
                },
            },
        }

    def test_execute_preflight_accepts_only_the_full_sound_contract(self) -> None:
        split_identity = self.complete_installed_split_identity()
        ready = self.complete_ready_payloads()
        validate_probe_ready_contracts(
            ready,
            installed_split_identity=split_identity,
        )

        weakened = self.complete_ready_payloads()
        weakened_checks = weakened["sound_logic"]["sound_pack_pre_gate_status"][
            "gate_table_key_checks"
        ]
        weakened_checks.pop()
        with self.assertRaisesRegex(HuntError, "full static extractor parity"):
            validate_probe_ready_contracts(
                weakened,
                installed_split_identity=split_identity,
            )

        no_sync_ids = self.complete_ready_payloads()
        no_sync_ids["sound_logic"]["capture_scope"].pop(
            "synchronous_nested_invocation_ids_are_causal"
        )
        with self.assertRaisesRegex(HuntError, "exact synchronous metadata"):
            validate_probe_ready_contracts(
                no_sync_ids,
                installed_split_identity=split_identity,
            )

        wrong_hook = self.complete_ready_payloads()
        wrong_hook["sound_logic"]["hook_status"]["performRequest"][
            "actual_module_offset"
        ] = "0xdeadbeef"
        with self.assertRaisesRegex(HuntError, "performRequest"):
            validate_probe_ready_contracts(
                wrong_hook,
                installed_split_identity=split_identity,
            )

        wrong_split_hash = self.complete_installed_split_identity()
        wrong_split_hash["actual_apk_sha256"] = "00"
        with self.assertRaisesRegex(HuntError, "actual_apk_sha256"):
            validate_probe_ready_contracts(
                ready,
                installed_split_identity=wrong_split_hash,
            )

        wrong_mapping = self.complete_ready_payloads()
        wrong_mapping["sound_logic"]["game_proc_identity_status"][
            "expected_container_sha256"
        ] = "00"
        with self.assertRaisesRegex(HuntError, "mapping identity"):
            validate_probe_ready_contracts(
                wrong_mapping,
                installed_split_identity=split_identity,
            )

        wrong_field = self.complete_ready_payloads()
        wrong_field["sound_logic"]["bgm_upstream_field_schema"][
            "sdgm_snapshot_fields"
        ].pop("saved_no_u16_at_0x149a")
        with self.assertRaisesRegex(HuntError, "field schema"):
            validate_probe_ready_contracts(
                wrong_field,
                installed_split_identity=split_identity,
            )

        wrong_binding = self.complete_ready_payloads()
        wrong_binding["sound_logic"]["hook_status"]["kndCalLotRlStart"][
            "module_path"
        ] = "/wrong/libGameProc.so"
        with self.assertRaisesRegex(HuntError, "verified split/ELF"):
            validate_probe_ready_contracts(
                wrong_binding,
                installed_split_identity=split_identity,
            )

    def test_bgm_upstream_window_contract_is_exact_and_bounded(self) -> None:
        payload = {
            "schema": "magireco-target-bgm-upstream-window-v1",
            "active": True,
            "label": "hunt_attempt_000001",
            "epoch": 1,
            "emitted_event_count": 0,
            "dropped_event_count": 0,
            "maximum_emitted_events": 1024,
            "read_only_observer": True,
        }
        self.assertEqual(
            validate_bgm_upstream_window_contract(payload, expected_active=True),
            payload,
        )
        overflow = dict(payload, dropped_event_count=1)
        with self.assertRaisesRegex(HuntError, "dropped events"):
            validate_bgm_upstream_window_contract(overflow, expected_active=True)
        wrong_epoch = dict(payload, epoch=2)
        with self.assertRaisesRegex(HuntError, "epoch changed"):
            validate_bgm_upstream_window_contract(
                wrong_epoch,
                expected_active=True,
                expected_epoch=1,
            )

    def test_installed_split_identity_binds_outer_and_uncompressed_inner(self) -> None:
        identity = self.complete_installed_split_identity()
        self.assertEqual(
            validate_installed_arm64_split_identity(identity),
            identity,
        )
        wrong_inner = copy.deepcopy(identity)
        wrong_inner["actual_entry_sha256"] = "00"
        with self.assertRaisesRegex(HuntError, "actual_entry_sha256"):
            validate_installed_arm64_split_identity(wrong_inner)
        wrong_layout = copy.deepcopy(identity)
        wrong_layout["entry_local_header"]["flag_bits_u16"] = 8
        with self.assertRaisesRegex(HuntError, "parsed GameProc header"):
            validate_installed_arm64_split_identity(wrong_layout)

        filename = EXPECTED_GAME_PROC_APK_ENTRY.encode("utf-8")
        extra_length = (
            EXPECTED_GAME_PROC_APK_DATA_OFFSET
            - EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET
            - 30
            - len(filename)
        )
        header = struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            0,
            0,
            EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
            2081,
            545,
            int(EXPECTED_GAME_PROC_APK_CRC32, 16),
            EXPECTED_GAME_PROC_SIZE_BYTES,
            EXPECTED_GAME_PROC_SIZE_BYTES,
            len(filename),
            extra_length,
        ) + filename + bytes(extra_length)
        parsed = parse_bound_game_proc_local_header(header)
        self.assertEqual(parsed["filename"], EXPECTED_GAME_PROC_APK_ENTRY)
        self.assertEqual(parsed["data_offset"], EXPECTED_GAME_PROC_APK_DATA_OFFSET)
        compressed = bytearray(header)
        struct.pack_into("<H", compressed, 8, 8)
        with self.assertRaisesRegex(HuntError, "ZIP entry contract"):
            parse_bound_game_proc_local_header(bytes(compressed))

    def test_finished_bgm_window_retains_final_overflow_counters(self) -> None:
        class Exports:
            @staticmethod
            def beginbgmupstreamattempt(label: str) -> dict[str, object]:
                return {
                    "schema": "magireco-target-bgm-upstream-window-v1",
                    "active": True,
                    "label": label,
                    "epoch": 3,
                    "emitted_event_count": 0,
                    "dropped_event_count": 0,
                    "maximum_emitted_events": 1024,
                    "read_only_observer": True,
                }

            @staticmethod
            def endbgmupstreamattempt() -> dict[str, object]:
                return {
                    "schema": "magireco-target-bgm-upstream-window-v1",
                    "active": False,
                    "label": "hunt_attempt_000001",
                    "epoch": 3,
                    "emitted_event_count": 1024,
                    "dropped_event_count": 7,
                    "maximum_emitted_events": 1024,
                    "read_only_observer": True,
                }

        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024,
        )
        capture.scripts["sound_logic"] = SimpleNamespace(exports_sync=Exports())
        capture.begin_attempt()
        with self.assertRaisesRegex(HuntError, "dropped events"):
            capture.finish_bgm_upstream_window()
        self.assertIsNotNone(capture.bgm_upstream_window)
        self.assertFalse(capture.bgm_upstream_window["active"])
        self.assertEqual(capture.bgm_upstream_window["emitted_event_count"], 1024)
        self.assertEqual(capture.bgm_upstream_window["dropped_event_count"], 7)
        capture.end_attempt()

    def test_attempt_trace_retains_bgm_upstream_entry_leave_and_window(self) -> None:
        class Exports:
            @staticmethod
            def beginbgmupstreamattempt(label: str) -> dict[str, object]:
                return {
                    "schema": "magireco-target-bgm-upstream-window-v1",
                    "active": True,
                    "label": label,
                    "epoch": 7,
                    "emitted_event_count": 0,
                    "dropped_event_count": 0,
                    "maximum_emitted_events": 1024,
                    "read_only_observer": True,
                }

            @staticmethod
            def endbgmupstreamattempt() -> dict[str, object]:
                return {
                    "schema": "magireco-target-bgm-upstream-window-v1",
                    "active": False,
                    "label": "hunt_attempt_000001",
                    "epoch": 7,
                    "emitted_event_count": 1,
                    "dropped_event_count": 0,
                    "maximum_emitted_events": 1024,
                    "read_only_observer": True,
                }

        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024 * 1024,
        )
        capture.scripts["sound_logic"] = SimpleNamespace(exports_sync=Exports())
        capture.ready_payloads["sound_logic"] = self.complete_ready_payloads()[
            "sound_logic"
        ]
        capture.installed_split_identity = self.complete_installed_split_identity()
        capture.begin_attempt()
        callback = capture._callback("sound_logic")
        callback(
            {
                "type": "send",
                "payload": {
                    "kind": "sound_logic_bgm_upstream_bgm_dir_request",
                    "unix_ms": 100,
                    "thread_id": 9,
                    "bgm_upstream_hook": "objNmlSndRequestBgmDir",
                    "bgm_upstream_call_id": 33,
                    "bgm_upstream_window_label": "hunt_attempt_000001",
                    "bgm_upstream_window_epoch": 7,
                    "bgm_upstream_window_event_index": 1,
                    "bgm_upstream_state_partition": "objNmlSndRequestBgmDir@0x1234",
                    "emission_reason": "first_observation_in_window",
                    "obj_nml_pointer": "0x1234",
                    "entry": {
                        "direction_kind_u16_at_0x00ca": 47,
                        "direction_no_u16_at_0x011a": 12,
                        "cached_code_pointer_at_0x0800": "0x2000",
                        "cached_code_string_at_0x0800": "835",
                    },
                    "leave": {
                        "direction_kind_u16_at_0x00ca": 47,
                        "direction_no_u16_at_0x011a": 25,
                        "cached_code_pointer_at_0x0800": "0x3000",
                        "cached_code_string_at_0x0800": "836",
                    },
                    "changed_fields": [
                        "direction_no_u16_at_0x011a",
                        "cached_code_pointer_at_0x0800",
                        "cached_code_string_at_0x0800",
                    ],
                },
            },
            None,
        )
        capture.pump(0.1)
        final_window = capture.finish_bgm_upstream_window()
        self.assertIsNotNone(final_window)
        self.assertFalse(final_window["active"])
        self.assertEqual(final_window["emitted_event_count"], 1)
        trace = compact_attempt_summary(
            attempt=1,
            started_unix_ms=1,
            outcome="test",
            actions=[],
            capture=capture,
        )["sound_logic_request_trace"]
        self.assertEqual(trace["bgm_upstream_window"]["epoch"], 7)
        self.assertFalse(trace["bgm_upstream_window"]["active"])
        self.assertEqual(trace["events"][0]["bgm_upstream_state_partition"], "objNmlSndRequestBgmDir@0x1234")
        self.assertEqual(
            trace["bgm_upstream_field_schema"], EXPECTED_BGM_UPSTREAM_FIELD_SCHEMA
        )
        self.assertEqual(
            trace["bgm_upstream_provenance"]["installed_split_identity"][
                "actual_entry_sha256"
            ],
            EXPECTED_GAME_PROC_SHA256,
        )
        self.assertEqual(
            trace["bgm_upstream_provenance"]["game_proc_identity_status"][
                "expected_container_sha256"
            ],
            EXPECTED_ARM64_SPLIT_SHA256,
        )
        self.assertEqual(
            set(trace["bgm_upstream_provenance"]["upstream_hook_status"]),
            set(EXPECTED_BGM_UPSTREAM_HOOK_KEYS),
        )
        self.assertEqual(trace["events"][0]["entry"]["cached_code_string_at_0x0800"], "835")
        self.assertEqual(trace["events"][0]["leave"]["cached_code_string_at_0x0800"], "836")
        capture.end_attempt()

    def test_bgm_upstream_overflow_fails_attempt(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024 * 1024,
        )
        capture.begin_attempt()
        callback = capture._callback("sound_logic")
        callback(
            {
                "type": "send",
                "payload": {
                    "kind": "sound_logic_bgm_upstream_trace_overflow",
                    "unix_ms": 1,
                    "maximum_emitted_events": 1024,
                    "dropped_event_count": 1,
                    "overflow_policy": "fail_attempt",
                },
            },
            None,
        )
        with self.assertRaisesRegex(HuntError, "trace overflowed"):
            capture.pump(0.1)

    def test_sound_request_trace_retains_exact_nested_join_ids_and_fails_bounded(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024 * 1024,
        )
        capture.max_sound_request_trace_events = 4
        capture.begin_attempt()
        callback = capture._callback("sound_logic")
        payloads = [
            {
                "kind": "sound_logic_player_perform_request",
                "unix_ms": 100,
                "thread_id": 7,
                "perform_invocation_id": 91,
                "order_request_id_u32": 3094,
                "order_code": "16048",
                "order": {"function_type_name": "PLAY"},
                "return_module_offset": "0x1234",
            },
            {
                "kind": "sound_logic_sound_mng_snd_play_req_enter",
                "unix_ms": 101,
                "thread_id": 7,
                "play_request_call_id": 44,
                "perform_invocation_id": 91,
                "perform_order_request_id_u32": 3094,
                "perform_order_code": "16048",
                "perform_association_basis": "nested_within_perform_request",
                "sound_resource_id_i32": 835,
            },
            {
                "kind": "sound_logic_csl_mng_snd_req_enqueue",
                "unix_ms": 102,
                "thread_id": 7,
                "csl_enqueue_id": 72,
                "play_request_call_id": 44,
                "perform_invocation_id": 91,
                "perform_order_request_id_u32": 3094,
                "perform_order_code": "16048",
                "requested_sound_resource_id_i32": 835,
                "request_table_entry_slot_index_u16": 1,
                "sound_data_pointer": "0x1234",
                "pending_sound_data_pointer_after_request": "0x1234",
                "enqueue_committed": True,
                "causal_association_basis": "nested_within_sound_mng_snd_play_req",
            },
            {
                "kind": "sound_logic_csl_mng_play_start",
                "unix_ms": 103,
                "thread_id": 8,
                "causal_csl_enqueue_id": 72,
                "causal_play_request_call_id": 44,
                "causal_sound_resource_id_i32": 835,
                "causal_perform_invocation_id": 91,
                "causal_perform_order_request_id_u32": 3094,
                "causal_perform_order_code": "16048",
                "causal_association_basis": (
                    "same_csl_slot_and_pending_sound_data_pointer_written_by_snd_req_"
                    "then_consumed_by_calc"
                ),
                "sound": {"final_sound_id_u16_at_0x02": 305},
            },
            {
                "kind": "sound_logic_sound_mng_snd_play_req_leave",
                "unix_ms": 104,
                "thread_id": 7,
                "play_request_call_id": 44,
                "perform_invocation_id": 91,
                "sound_resource_id_i32": 835,
                "return_i32": 0,
            },
        ]
        for payload in payloads:
            callback({"type": "send", "payload": payload}, None)
            capture.pump(0.1)
        trace = compact_attempt_summary(
            attempt=1,
            started_unix_ms=1,
            outcome="test",
            actions=[],
            capture=capture,
        )["sound_logic_request_trace"]
        self.assertFalse(trace["complete"])
        self.assertEqual(trace["retained_event_count"], 4)
        self.assertEqual(trace["dropped_event_count"], 1)
        perform, play, enqueue, csl = trace["events"]
        self.assertEqual(perform["perform_invocation_id"], play["perform_invocation_id"])
        self.assertEqual(play["perform_invocation_id"], enqueue["perform_invocation_id"])
        self.assertEqual(enqueue["csl_enqueue_id"], csl["causal_csl_enqueue_id"])
        self.assertEqual(enqueue["perform_invocation_id"], csl["causal_perform_invocation_id"])
        self.assertEqual(play["play_request_call_id"], csl["causal_play_request_call_id"])
        self.assertEqual(play["sound_resource_id_i32"], 835)
        self.assertEqual(csl["causal_sound_resource_id_i32"], 835)
        self.assertEqual(csl["sound"]["final_sound_id_u16_at_0x02"], 305)

    def test_frida_script_error_fails_attempt_and_marks_trace_incomplete(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024 * 1024,
        )
        capture.begin_attempt()
        callback = capture._callback("sound_logic")
        callback(
            {
                "type": "error",
                "description": "TypeError: test failure",
                "stack": "at probe.js:12",
                "fileName": "probe.js",
                "lineNumber": 12,
                "columnNumber": 3,
            },
            None,
        )
        with self.assertRaisesRegex(HuntError, "Frida script error"):
            capture.pump(0.1)
        trace = compact_attempt_summary(
            attempt=1,
            started_unix_ms=1,
            outcome="attempt_error",
            actions=[],
            capture=capture,
        )["sound_logic_request_trace"]
        self.assertFalse(trace["complete"])
        self.assertEqual(trace["dropped_event_count"], 0)
        self.assertEqual(trace["probe_errors"][0]["line_number"], 12)

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
            def beginbgmupstreamattempt(label: str) -> dict[str, object]:
                return {
                    "schema": "magireco-target-bgm-upstream-window-v1",
                    "active": True,
                    "label": label,
                    "epoch": 1,
                    "emitted_event_count": 0,
                    "dropped_event_count": 0,
                    "maximum_emitted_events": 1024,
                    "read_only_observer": True,
                }

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

    def test_attach_hashes_exact_injected_probe_bytes_before_path_can_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "probe.js"
            original = b"send({kind:'ready'});\n"
            probe.write_bytes(original)

            class Script:
                @staticmethod
                def on(_event: str, _callback: object) -> None:
                    return None

                @staticmethod
                def load() -> None:
                    return None

            class Session:
                @staticmethod
                def on(_event: str, _callback: object) -> None:
                    return None

                @staticmethod
                def create_script(source: str) -> Script:
                    self.assertEqual(source.encode("utf-8"), original)
                    probe.write_bytes(b"changed-after-create-script\n")
                    return Script()

            class Device:
                @staticmethod
                def enumerate_processes() -> list[SimpleNamespace]:
                    return [SimpleNamespace(pid=1, name="Gadget")]

                @staticmethod
                def attach(_pid: int) -> Session:
                    return Session()

            manager = SimpleNamespace(add_remote_device=lambda _host: Device())
            capture = LiveCapture(
                host="127.0.0.1:27043",
                expected_pid=1,
                script_paths={"sound_logic": probe},
                max_buffer_bytes=1024,
            )
            with patch(
                "tools.frida_runtime_probe.natural_sp_story_hunt.frida.get_device_manager",
                return_value=manager,
            ):
                capture.attach()
            loaded = capture.loaded_probe_sources["sound_logic"]
            self.assertEqual(loaded["bytes"], len(original))
            self.assertEqual(
                loaded["sha256"],
                hashlib.sha256(original).hexdigest().upper(),
            )
            self.assertEqual(
                capture.loaded_probe_source_bytes["sound_logic"],
                original,
            )
            self.assertNotEqual(probe.read_bytes(), original)

    def test_pre_gate_direct_sound_requests_are_retained_individually(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024 * 1024,
        )
        capture.begin_attempt()
        callback = capture._callback("sound_logic")
        callback(
            {
                "type": "send",
                "payload": {
                    "kind": "sound_logic_sound_pack_pre_gate_volume",
                    "unix_ms": 10,
                    "sound_resource_id_i32": 801,
                    "volume_index_i32": 0,
                    "sound_pack_active_u32": 0,
                    "volume_class_u8": 0,
                    "class_volume_u16": 50,
                    "indexed_volume_u16": 50,
                    "master_volume_u16": 100,
                    "pre_gate_stage_volume_i32": 25,
                    "authorized_final_volume_i32": 25,
                    "current_gate_will_zero": True,
                    "reconstruction_complete": True,
                    "emission_reason": "direct_sound_request_call",
                    "return_module_offset": "0x425f160",
                },
            },
            None,
        )
        capture.pump(0.1)
        callback(
            {
                "type": "send",
                "payload": {
                    "kind": "sound_logic_sound_pack_pre_gate_volume",
                    "unix_ms": 11,
                    "sound_resource_id_i32": 801,
                    "volume_index_i32": 0,
                    "sound_pack_active_u32": 0,
                    "volume_class_u8": 0,
                    "class_volume_u16": 50,
                    "indexed_volume_u16": 50,
                    "master_volume_u16": 100,
                    "pre_gate_stage_volume_i32": 25,
                    "authorized_final_volume_i32": 25,
                    "current_gate_will_zero": True,
                    "reconstruction_complete": True,
                    "emission_reason": "direct_sound_request_call",
                    "return_module_offset": "0x425f160",
                },
            },
            None,
        )
        capture.pump(0.1)
        row = compact_attempt_summary(
            attempt=1,
            started_unix_ms=1,
            outcome="test",
            actions=[],
            capture=capture,
        )
        events = row["sound_pack_pre_gate_volume_events"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["sound_resource_id_i32"], 801)
        self.assertEqual(events[0]["authorized_final_volume_i32"], 25)
        self.assertTrue(events[0]["current_gate_will_zero"])
        self.assertEqual([event["observation_count"] for event in events], [1, 1])
        self.assertEqual(events[0]["last_sequence"], events[0]["first_sequence"])

    def test_pre_gate_volume_control_repeats_are_aggregated(self) -> None:
        capture = LiveCapture(
            host="127.0.0.1:27043",
            expected_pid=1,
            script_paths={"sound_logic": Path("probe.js")},
            max_buffer_bytes=1024 * 1024,
        )
        capture.begin_attempt()
        callback = capture._callback("sound_logic")
        payload = {
            "kind": "sound_logic_sound_pack_pre_gate_volume",
            "unix_ms": 10,
            "sound_resource_id_i32": 801,
            "volume_index_i32": 0,
            "sound_pack_active_u32": 0,
            "volume_class_u8": 0,
            "class_volume_u16": 50,
            "indexed_volume_u16": 50,
            "master_volume_u16": 100,
            "pre_gate_stage_volume_i32": 25,
            "authorized_final_volume_i32": 25,
            "current_gate_will_zero": True,
            "reconstruction_complete": True,
            "emission_reason": "first_observed_volume_control_state",
            "return_module_offset": "0x425f918",
        }
        for unix_ms in (10, 11):
            payload["unix_ms"] = unix_ms
            callback({"type": "send", "payload": dict(payload)}, None)
            capture.pump(0.1)
        events = compact_attempt_summary(
            attempt=1,
            started_unix_ms=1,
            outcome="test",
            actions=[],
            capture=capture,
        )["sound_pack_pre_gate_volume_events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["observation_count"], 2)
        self.assertGreater(events[0]["last_sequence"], events[0]["first_sequence"])

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
            'outcome="read_only_dry_run"',
            'outcome="read_only_dry_run_error"',
            '"sound_logic_request_trace": dry_run_trace',
            '"event": "dry_run_error"',
            '"adb_input_sent": False',
            '"--expected-pid"',
            'expected game PID {args.expected_pid}',
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
