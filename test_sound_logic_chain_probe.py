from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "tools" / "frida_runtime_probe" / "sound_logic_chain_probe.js"


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
            "_ZN6CSLMng9PlayStartEP11SSound_Datai",
        }
        self.assertTrue(required.issubset(set(re.findall(r'"([_A-Za-z][^"]+)"', self.source))))

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

    def test_play_request_uses_nested_perform_context_but_csl_does_not(self) -> None:
        self.assertIn('"nested_within_perform_request"', self.source)
        self.assertIn('"none_static_sound_id_join_required"', self.source)
        self.assertIn("activePerformStackByThread", self.source)
        self.assertNotIn("contextFields(contextResult)", self.source)

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


if __name__ == "__main__":
    unittest.main()
