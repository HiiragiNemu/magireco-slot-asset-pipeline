from __future__ import annotations

import re
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "tools" / "frida_runtime_probe" / "sound_logic_chain_probe.js"
DEDUP_REGRESSION = (
    ROOT / "tools" / "frida_runtime_probe" / "test_bgm_upstream_dedup.js"
)


class SoundLogicChainProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PROBE.read_text(encoding="utf-8")

    def test_required_logical_chain_symbols_are_hooked(self) -> None:
        required = {
            "_ZN2zg3snd11RequestCtrl14codeName2ReqIdEPKc",
            "zgSndReqId",
            "_ZN2zg3snd11RequestCtrl10getRequestEjRNS0_7RequestE",
            "_ZN2zg3snd11RequestCtrl14setRequestListERKNS0_7RequestE",
            "_ZN2zg3snd10PlayerImpl14performRequestERNS0_11RequestCtrlERNS0_8ReqOrderEb",
            "_ZN8SoundMng10sndPlayReqEiii",
            "_ZN8SoundMng12changeVolumeEii",
            "_ZN6CSLMng6SndReqEii",
            "_ZN6CSLMng9PlayStartEP11SSound_Datai",
            "fnKndCalLot_CcDirEnd",
            "fnKndCalLot_RlStart",
            "_ZN11C_MstComCbk14fnUpDateGmDataEv",
            "_ZN9C_AnmBase16fnDataSetDir_DIREv",
            "_ZN8C_ObjNml20fnSndRequest_BGM_DIREv",
        }
        self.assertTrue(required.issubset(set(re.findall(r'"([_A-Za-z][^"]+)"', self.source))))

    def test_primary_hooks_fail_closed_on_static_offset_mismatch(self) -> None:
        for token in (
            "let hookStatusByKey = {}",
            "if (actualOffset !== expectedOffset || !identityModuleMatches)",
            'status: "static_reference_mismatch"',
            'emit("sound_logic_hook_unavailable", hookStatusByKey[key])',
            "hook_status: hookStatusByKey",
        ):
            self.assertIn(token, self.source)
        mismatch_block = re.search(
            r"if \(actualOffset !== expectedOffset \|\| !identityModuleMatches\) "
            r"\{(?P<body>.*?)\n  \}",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(mismatch_block)
        self.assertIn("return null", mismatch_block.group("body"))

    def test_capture_is_generic_and_keeps_known_static_reference_ids(self) -> None:
        for token in (
            'const REQUEST_CODE_BY_ID = { 96: "291", 100: "295", 3094: "16048" }',
            'code_lookups: "all"',
            'request_ids: "all"',
            'perform_orders: "all"',
            'csl_play_start: "all_metadata_only"',
            '1: "PLAY"',
            '2: "STOP"',
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("const TARGET_", self.source)

    def test_probe_has_no_payload_dump_or_full_backtrace(self) -> None:
        forbidden = (
            "Thread.backtrace",
            "readByteArray",
            "readVolatile",
            "data_base64",
            "pcm_data",
            "compressed_data",
        )
        for token in forbidden:
            self.assertNotIn(token, self.source)

    def test_request_identity_is_not_inferred_from_channel_or_time(self) -> None:
        self.assertNotIn("function inferredCodeFromRequest", self.source)
        self.assertNotIn("function nearestContext", self.source)
        self.assertNotIn('basis: "global_recent_window"', self.source)
        self.assertNotIn('basis: "same_thread_recent"', self.source)
        self.assertIn("requestIdsFromDescription(description)", self.source)
        self.assertIn("knownCodeForRequestId(requestId)", self.source)
        self.assertIn('"reqdata_own_id"', self.source)

    def test_synchronous_nested_ids_bind_perform_play_request_and_csl(self) -> None:
        self.assertIn('"nested_within_perform_request"', self.source)
        self.assertIn('"nested_within_sound_mng_snd_play_req"', self.source)
        self.assertIn('"none_static_sound_id_join_required"', self.source)
        self.assertIn("activePerformStackByThread", self.source)
        self.assertIn("activeSoundPlayStackByThread", self.source)
        self.assertIn("perform_invocation_id: performInvocationId", self.source)
        self.assertIn("play_request_call_id: playRequestCallId", self.source)
        self.assertIn("causal_play_request_call_id: pendingEnqueue", self.source)
        self.assertIn("causal_perform_invocation_id: pendingEnqueue", self.source)
        self.assertIn("synchronous_nested_invocation_ids_are_causal: true", self.source)
        self.assertNotIn("contextFields(contextResult)", self.source)

    def test_csl_cross_thread_join_uses_exact_pending_pointer_and_slot(self) -> None:
        for token in (
            "const CSL_SOUND_DATA_ENTRY_STRIDE = 0x0c",
            "const CSL_PENDING_SOUND_DATA_SLOT_OFFSET = 0x20",
            "const MAX_CSL_SOUND_DATA_TABLE_ROWS = 65536",
            'installHook("cslMngSndReq"',
            '"sound_logic_csl_mng_snd_req_enqueue"',
            "pendingPointer.equals(entry.sound_data_pointer)",
            "pendingCslEnqueueKeyBySlot",
            "delete pendingCslEnqueueByKey[previousEnqueueKey]",
            "cslPendingEnqueueKey(args[0], playIndex, args[1])",
            "causal_csl_enqueue_id: pendingEnqueue",
            '"same_csl_slot_and_pending_sound_data_pointer_written_by_snd_req_then_consumed_by_calc"',
            'csl_request_enqueue: "bounded_named_table_and_pending_slot_fields_only"',
        ):
            self.assertIn(token, self.source)

    def test_c_string_reader_stops_at_nul_within_readable_range(self) -> None:
        self.assertIn("range.size - offsetInRange", self.source)
        self.assertIn("readU8() === 0", self.source)
        self.assertIn("unterminated_within_readable_limit", self.source)
        self.assertNotIn("pointerValue.readUtf8String(limit || 512)", self.source)

    def test_runtime_structure_offsets_are_guarded_by_arm64_abi_check(self) -> None:
        self.assertIn('Process.arch !== "arm64"', self.source)
        self.assertIn("Process.pointerSize !== 8", self.source)
        self.assertIn("byteLength % 0x90 !== 0", self.source)
        self.assertIn("readU16Safe(reqData, 0x08)", self.source)
        self.assertIn("readU32Safe(reqOrderPointer, 0x50)", self.source)
        self.assertIn("readS32Safe(playerPointer, 0x42a4)", self.source)

    def test_probe_does_not_overwrite_frida_read_only_cpu_context(self) -> None:
        self.assertNotIn("this.context =", self.source)
        self.assertIn("this.soundLogicContext =", self.source)

    def test_active_sound_snapshot_uses_versioned_csl_layout_and_getters(self) -> None:
        for token in (
            'lib_amain_sha256: "58E3F7A9DBCE2E3D79D1A5A30F1DBFEEAC5BB4712BD4D8FF4E6328D2631DCA5D"',
            'name: "_ZN6CSLMng4CalcEv"',
            'name: "_ZN6CSLMng8SndGetIDEi"',
            'name: "_ZN6CSLMng13SndGetChannelEi"',
            'name: "_ZN6CSLMng10SndGetTimeEi"',
            'name: "_ZN6CSLMng13SndGetLoopNumEi"',
            'name: "_ZN6CSLMng14SndGetPriorityEi"',
            'name: "_ZN6CSLMng11SndGetLoopFEi"',
            'name: "_ZN6CSLMng11SndGetWaitFEi"',
            'name: "_ZN6CSLMng12SndGetPauseFEi"',
            "const CSL_ACTIVE_VECTOR_BEGIN_OFFSET = 0xa0",
            "const CSL_ACTIVE_VECTOR_END_OFFSET = 0xa8",
            "const CSL_ACTIVE_SLOT_STRIDE = 0x38",
        ):
            self.assertIn(token, self.source)

    def test_active_sound_snapshot_is_bounded_and_does_not_claim_bgm_semantics(self) -> None:
        for token in (
            "const MAX_ACTIVE_SOUND_SLOTS = 128",
            "Math.min(declaredCount, MAX_ACTIVE_SOUND_SLOTS)",
            "capture_cap_is_declared_game_limit: false",
            "byteLength % CSL_ACTIVE_SLOT_STRIDE !== 0",
            "readableSpan(begin, byteLength)",
            'classification_rule: "active_transport_state_only_csl_resource_table_channel_zero_is_not_bgm_proof"',
            "csl_resource_table_channel_zero_candidate_only:",
            "transportPlaying && channel === 0",
            "bgm_semantics_proven: false",
            "outerbgmsnapshot(label)",
            'snapshot_runs_on_csl_calc_thread: executionSource === "cslMngCalc_on_enter"',
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("confirmed_outer_bgm", self.source)

    def test_defensive_cap_does_not_truncate_observed_65_slot_vector(self) -> None:
        match = re.search(
            r"const MAX_ACTIVE_SOUND_SLOTS = (\d+);",
            self.source,
        )
        self.assertIsNotNone(match)
        capture_cap = int(match.group(1))
        self.assertEqual(capture_cap, 128)
        self.assertEqual(min(65, capture_cap), 65)
        self.assertFalse(65 > capture_cap)
        self.assertIn("capture_cap_is_declared_game_limit: false", self.source)

    def test_calc_hook_exists_only_during_one_snapshot_rpc(self) -> None:
        self.assertIn("prepareCslCalcSnapshotEntry()", self.source)
        self.assertIn("Interceptor.attach(cslCalcSnapshotAddress", self.source)
        self.assertIn("listener.detach()", self.source)
        self.assertIn(
            'execution_policy: "attach_for_one_rpc_then_snapshot_on_calc_thread_and_detach"',
            self.source,
        )
        self.assertNotIn('installHook("cslMngCalc"', self.source)

    def test_active_snapshot_reads_only_named_fixed_fields(self) -> None:
        for token in (
            "sound_object_pointer_at_0x00",
            "slot_mute_u8_at_0x0c",
            "slot_volume_u32_at_0x10",
            "slot_time_or_sample_u32_at_0x14",
            "slot_loop_state_u32_at_0x18",
            "pending_sound_data_pointer_at_0x20",
            "chain_data_pointer_at_0x28",
            "transport_playing_proven",
            "transport_state",
            "sound_time_seconds",
            "sound_pause_flag_i32",
        ):
            self.assertIn(token, self.source)
        for forbidden in ("Memory.scan", "readByteArray", "Thread.backtrace"):
            self.assertNotIn(forbidden, self.source)

    def test_paused_transport_is_not_reported_as_proven_playing(self) -> None:
        self.assertIn(
            'transport_playing_proven: transportState === "playing"',
            self.source,
        )

    def test_sound_pack_pre_gate_volume_is_reconstructed_read_only(self) -> None:
        for token in (
            "const SOUND_PACK_GATE_TABLE_OFFSET = 0x14458dc",
            "const SOUND_PACK_GATE_ENTRY_COUNT = 222",
            "const SOUND_PACK_ACTIVE_ADDON_OFFSET = 0x14c0c",
            "const SOUND_MNG_INDEXED_VOLUME_BASE_OFFSET = 0x82c",
            "const SOUND_MNG_MASTER_VOLUME_OFFSET = 0x8ac",
            '"sound_logic_sound_pack_pre_gate_volume"',
            "authorized_final_volume_i32: authorizedFinalVolume",
            "current_gate_will_zero: activeAddon === 0",
            '"changeVolume_arm64_integer_percent_chain_before_entitlement_zero"',
            "gate_table_strictly_increasing_unique: strictlyIncreasing",
            'gate_table_offset: "0x" + SOUND_PACK_GATE_TABLE_OFFSET.toString(16)',
            "read_only_observer: true",
            "repeated_unchanged_volume_control_calls_suppressed: true",
            'callerOffset === "0x425f160"',
            'callerOffset === "0x425f31c"',
            '"volume_control_state_changed"',
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("Memory.write", self.source)
        self.assertNotIn("retval.replace", self.source)

    def test_target_bgm_upstream_capture_is_hashed_named_and_bounded(self) -> None:
        for token in (
            'game_proc_logical_name: "libGameProc.so"',
            'game_proc_apk_entry: "lib/arm64-v8a/libGameProc.so"',
            'game_proc_apk_entry_compression_method: 0',
            'game_proc_apk_entry_crc32: "BBB59DED"',
            'game_proc_apk_entry_header_offset: 2469872',
            'game_proc_apk_entry_data_offset: 2473984',
            'game_proc_size_bytes: 79683640',
            'game_proc_sha256: "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"',
            'arm64_apk_module: "split_config.arm64_v8a.apk"',
            'arm64_apk_size_bytes: 83710748',
            'arm64_apk_sha256: "89ACC81D02FF63697603FCE2E5F4281850C092FA833FD8CF3E636B44AB624E24"',
            'const SDGM_ACCESSOR_SYMBOL = "fnGetAddrSdGmData"',
            'const SDGM_ACCESSOR_EXPECTED_OFFSET = "0x424d474"',
            "const derivedBase = anchorAddress.sub(expectedAnchorOffset)",
            "Process.findModuleByAddress(anchorAddress)",
            "readU32Safe(derivedBase, 0x00)",
            "readU8Safe(derivedBase, 0x04)",
            "readU8Safe(derivedBase, 0x05)",
            "readU16Safe(derivedBase, 0x12)",
            'mapping_kind: "apk_backed_uncompressed_elf"',
            "installed_container_identity_required_from_host: true",
            'offset_basis: spec.requiresGameProcIdentity',
            '"known_export_minus_derived_game_proc_elf_base"',
            "const MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW = 1024",
            'target_bgm_upstream: "named_fields_only_explicit_attempt_window"',
            'window_control: "explicit_rpc_begin_end"',
            'high_frequency_hooks: "first_observation_or_state_change_within_window"',
            'overflow_policy: "emit_overflow_once_and_fail_attempt"',
            'hookKey + "@" + String(statePartition)',
            'bgm_upstream_state_partition: signatureKey',
            'JSON.stringify({ entry: this.entry, leave })',
            "beginbgmupstreamattempt(label)",
            "endbgmupstreamattempt()",
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("File.readAllBytes", self.source)
        self.assertNotIn("Checksum.compute", self.source)

    def test_target_bgm_upstream_hooks_capture_only_named_fields(self) -> None:
        for token in (
            'expectedOffset: "0x4445e3c"',
            'expectedOffset: "0x444466c"',
            'expectedOffset: "0x4399a4c"',
            'expectedOffset: "0x4387f90"',
            'expectedOffset: "0x43a86b0"',
            "readU16Safe(pointerValue, 0x13da)",
            "readU16Safe(pointerValue, 0x13dc)",
            "readU16Safe(pointerValue, 0x13de)",
            "readU16Safe(pointerValue, 0x13e0)",
            "readU16Safe(pointerValue, 0x1472)",
            "readU16Safe(pointerValue, 0x1474)",
            "readU16Safe(pointerValue, 0x149a)",
            "readU16Safe(pointerValue, 0xa72)",
            "readU16Safe(pointerValue, 0xa76)",
            "readU16Safe(pointerValue, 0xca)",
            "readU16Safe(pointerValue, 0x11a)",
            "readPointerSafe(pointerValue, 0x800)",
            "readCStringSafe(cachedCodePointer, 64)",
            '"sound_logic_bgm_upstream_bgm_dir_request"',
            "changedSnapshotFields(this.entry, leave)",
        ):
            self.assertIn(token, self.source)
        for forbidden in ("Memory.write", "retval.replace", "Thread.backtrace"):
            self.assertNotIn(forbidden, self.source)

    def test_bgm_upstream_partition_suppresses_repeats_and_bounds_overflow(self) -> None:
        block = re.search(
            r"function beginBgmUpstreamWindow\(label\) \{.*?\n\}\n\n"
            r"function installBgmUpstreamHooks\(\)",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(block)
        helper_source = block.group(0).rsplit(
            "\n\nfunction installBgmUpstreamHooks()", 1
        )[0]
        harness = f"""
const MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW = 1024;
let bgmUpstreamWindowActive = false;
let bgmUpstreamWindowLabel = "";
let bgmUpstreamWindowEpoch = 0;
let bgmUpstreamWindowEventCount = 0;
let bgmUpstreamWindowDroppedCount = 0;
let bgmUpstreamWindowOverflowEmitted = false;
let bgmUpstreamSignatureByHook = {{}};
const sent = [];
function emit(kind, fields) {{ sent.push(Object.assign({{kind}}, fields || {{}})); }}
{helper_source}
beginBgmUpstreamWindow("repeat-test");
for (let index = 0; index < 1000; index += 1) {{
  emitBgmUpstream("anmBaseDataSetDir", "data", {{index}}, "same", false, "0xA");
}}
emitBgmUpstream("anmBaseDataSetDir", "data", {{}}, "same", false, "0xB");
emitBgmUpstream("anmBaseDataSetDir", "data", {{}}, "changed", false, "0xA");
for (let index = 0; index < 3; index += 1) {{
  emitBgmUpstream("kndCalLotRlStart", "lottery", {{index}}, "ignored", true);
}}
const repeatWindow = endBgmUpstreamWindow();
beginBgmUpstreamWindow("overflow-test");
for (let index = 0; index < 1025; index += 1) {{
  emitBgmUpstream("anmBaseDataSetDir", "data", {{index}}, String(index), false, String(index));
}}
const overflowWindow = endBgmUpstreamWindow();
console.log(JSON.stringify({{repeatWindow, overflowWindow, sent}}));
"""
        completed = subprocess.run(
            ["node", "-e", harness],
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["repeatWindow"]["emitted_event_count"], 6)
        self.assertEqual(result["repeatWindow"]["dropped_event_count"], 0)
        self.assertFalse(result["repeatWindow"]["active"])
        self.assertEqual(result["overflowWindow"]["emitted_event_count"], 1024)
        self.assertEqual(result["overflowWindow"]["dropped_event_count"], 1)
        self.assertFalse(result["overflowWindow"]["active"])
        overflow_rows = [
            row
            for row in result["sent"]
            if row["kind"] == "sound_logic_bgm_upstream_trace_overflow"
        ]
        self.assertEqual(len(overflow_rows), 1)
        self.assertEqual(overflow_rows[0]["dropped_event_count"], 1)

    def test_bgm_upstream_measured_cardinality_node_regression(self) -> None:
        completed = subprocess.run(
            ["node", str(DEDUP_REGRESSION)],
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        result = json.loads(completed.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual(result["same_object_repeated_calls"], 1000)
        self.assertEqual(result["same_object_emitted_events"], 1)
        self.assertEqual(result["measured_replay"], {
            "data_set": 31,
            "bgm_dir": 2,
            "lottery": 34,
            "total": 67,
        })
        self.assertEqual(result["overflow"], {"emitted": 1024, "dropped": 11})

    def test_runtime_gate_key_checks_have_full_static_extractor_parity(self) -> None:
        block = re.search(
            r"const SOUND_PACK_REFERENCE_KEYS = \{(?P<body>.*?)\n\};",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(block)
        parsed = {
            int(index): int(value)
            for index, value in re.findall(r"(\d+):\s*(\d+)", block.group("body"))
        }
        self.assertEqual(
            parsed,
            {
                0: 67,
                1: 171,
                60: 778,
                67: 786,
                119: 863,
                151: 6103,
                169: 9070,
                170: 9071,
                171: 16716,
                181: 38009,
                219: 41030,
                220: 41031,
                221: 41032,
            },
        )


if __name__ == "__main__":
    unittest.main()
