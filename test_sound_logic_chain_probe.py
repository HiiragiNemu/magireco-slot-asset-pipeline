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


if __name__ == "__main__":
    unittest.main()
