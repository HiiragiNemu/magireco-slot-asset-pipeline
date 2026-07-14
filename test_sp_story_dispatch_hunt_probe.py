from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROBE = (
    ROOT
    / "tools"
    / "frida_runtime_probe"
    / "sp_story_dispatch_hunt_probe.js"
)


class SpStoryDispatchHuntProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PROBE.read_text(encoding="utf-8")

    def test_required_dispatch_and_event_symbols_are_hooked(self) -> None:
        for token in (
            'getCmdBuf: "_ZN5ID4019getCmdBufEPhi"',
            'accessSubProcess: "_ZN5ID40116accessSubProcessEPh"',
            'requestScene: "_ZN9C_AnmBase10fnReqSceneEyhtt"',
            'requestSoundEventCode: "_ZN12C_CtrlSndLib17fnReqSndEventCodeEy"',
            'lotSpStoryKind: "fnLot_OT_AT_SpStryKnd"',
        ):
            self.assertIn(token, self.source)

    def test_houdini_split_apk_module_name_uses_export_owner_fallback(self) -> None:
        for token in (
            "function findGameModule()",
            "Process.findModuleByName(MODULE_NAME)",
            "Process.findModuleByAddress(address)",
            "logical_module_name: MODULE_NAME",
            "module_path: moduleValue.path",
        ):
            self.assertIn(token, self.source)

    def test_payload_kinds_remain_compatible_with_live_hunter(self) -> None:
        for token in (
            '"id401_get_cmd_buf_enter"',
            '"id401_get_cmd_buf_leave"',
            '"id401_access_subprocess"',
            '"direction_scene_request"',
            '"ctrl_snd_req_event_code"',
            '"lot_sp_story_kind_enter"',
            '"lot_sp_story_kind_leave"',
            '"sp_story_dispatch_hunt_probe_ready"',
        ):
            self.assertIn(token, self.source)

    def test_dispatch_metadata_is_strict_and_packet_read_is_exactly_eight_bytes(self) -> None:
        for token in (
            "id401_get_cmd_buf_call_count",
            "id401_get_cmd_buf_enter_thread_id",
            "id401_get_cmd_buf_leave_thread_id",
            "id401_command_buffer_pointer",
            "id401_command_buffer_length",
            "id401_packet_pointer",
            "high_level_call_count_for_kind",
            "for (let index = 0; index < 8; index += 1)",
            'fields["id401_raw_packet_u8_at_" + index]',
            "id401_raw_packet_complete",
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("index <= 8", self.source)

    def test_event_code_abi_fields_are_preserved(self) -> None:
        for token in (
            "event_code_hex: args[1].toString()",
            "request_arg2_u8: toU32(args[2]) & 0xff",
            "request_arg3_u16: toU32(args[3]) & 0xffff",
            "request_arg4_u16: toU32(args[4]) & 0xffff",
            "event_code_i32_low: toI32(args[1])",
        ):
            self.assertIn(token, self.source)

    def test_lottery_state_capture_is_named_and_bounded(self) -> None:
        expected_fields = {
            "sdgm_sp_story_special_case_u16_at_0x35e",
            "sdgm_sp_story_enable_u16_at_0x45a",
            "sdgm_sp_story_probability_selector_u16_at_0x592",
            "sdgm_lot_dispatch_u16_at_0x13be",
            "sdgm_lot_dispatch_prev2_u16_at_0x13c4",
            "sdgm_lot_start_gate_u16_at_0x14cc",
            "sdgm_sp_story_kind_u16_at_0x1f82",
            "sdgm_sp_story_lottery_result_u16_at_0x2fdc",
        }
        for field in expected_fields:
            self.assertIn(field, self.source)
        self.assertEqual(self.source.count("readU16Safe(data,"), len(expected_fields))

    def test_every_hook_reports_installed_unavailable_or_error(self) -> None:
        for token in (
            'emit("hook_installed", row)',
            'emit("hook_unavailable", row)',
            'emit("hook_attach_error", row)',
            "hook_status: hookStatusByKind",
            "required_hooks_installed: requiredInstalled",
        ):
            self.assertIn(token, self.source)

    def test_probe_has_no_heavy_or_high_frequency_capture_surface(self) -> None:
        for forbidden in (
            "Thread.backtrace",
            "readByteArray",
            "Memory.scan",
            "Interceptor.replace",
            "ASM_0x",
            "LC701A_SLOT12mn_getCmdBuf",
            "fnLotDirGmStart",
            "fnKndCalLot_Start",
            "fnRxComDirInfo3",
            "fnRxComDirInfo8",
            "CScnSlot4Calc",
            "queue_enqueue",
            "PlayStart",
            "pcm",
        ):
            self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
