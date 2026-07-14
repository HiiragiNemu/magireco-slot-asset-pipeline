from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROBE = ROOT / "tools" / "frida_runtime_probe" / "slot_state_gate_probe.js"


class SlotStateGateProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PROBE.read_text(encoding="utf-8")

    def test_hooks_shared_process_and_emits_only_changes_or_input(self) -> None:
        self.assertIn('_ZN9CSlotBody7processEiiNS_10eStateModeE', self.source)
        self.assertIn('_ZN5CReel12setStopAngleEii', self.source)
        self.assertIn("inputNonzero || changedWithinCall || signature !== lastSignature", self.source)
        self.assertIn('evidence_rule: "process_input_plus_set_stop_angle_and_progress"', self.source)
        self.assertIn("delete stable.body_initialized_i32_at_0x08", self.source)

    def test_captures_logical_fields_without_media_dump(self) -> None:
        for token in (
            "body_input_mask_i32_at_0x408",
            "body_touch_mask_i32_at_0x40c",
            "body_state_i32_at_0x00",
            "body_mode_i32_at_0x04",
            "body_button_state_i32_at_0x74",
            "body_lever_state_i32_at_0x7c",
            "body_stop_wait16_i32_at_0x538",
            "body_interstop_i32_at_0x53c",
            "body_selected_axis_i32_at_0x540",
        ):
            self.assertIn(token, self.source)
        for forbidden in ("readByteArray", "Thread.backtrace", "screencap", "pcm"):
            self.assertNotIn(forbidden, self.source)

    def test_small_state_neighborhood_is_named_and_bounded(self) -> None:
        self.assertIn("state_u32_at_0x60", self.source)
        self.assertIn("state_u32_at_0x8c", self.source)
        self.assertNotIn("state_u32_at_0x90", self.source)

    def test_exposes_bounded_logical_snapshot_rpc(self) -> None:
        self.assertIn("let lastBody = null", self.source)
        self.assertIn("lastBody = args[0]", self.source)
        self.assertIn("snapshot()", self.source)
        self.assertIn("state: describeState(lastBody)", self.source)

    def test_emits_authoritative_reel_stop_axis(self) -> None:
        self.assertIn('emit("reel_stop_angle_enter"', self.source)
        self.assertIn("axis_i32: toI32(args[1])", self.source)


if __name__ == "__main__":
    unittest.main()
