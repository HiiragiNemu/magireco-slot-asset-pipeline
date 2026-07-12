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
        self.assertIn("inputNonzero || changedWithinCall || signature !== lastSignature", self.source)
        self.assertIn('evidence_rule: "nonzero_process_input_is_accepted_input"', self.source)
        self.assertIn("delete stable.body_initialized_i32_at_0x08", self.source)

    def test_captures_logical_fields_without_media_dump(self) -> None:
        for token in (
            "body_input_mask_i32_at_0x408",
            "body_touch_mask_i32_at_0x40c",
            "body_state_i32_at_0x00",
            "body_mode_i32_at_0x04",
            "body_button_state_i32_at_0x74",
            "body_lever_state_i32_at_0x7c",
        ):
            self.assertIn(token, self.source)
        for forbidden in ("readByteArray", "Thread.backtrace", "screencap", "pcm"):
            self.assertNotIn(forbidden, self.source)

    def test_small_state_neighborhood_is_named_and_bounded(self) -> None:
        self.assertIn("state_u32_at_0x60", self.source)
        self.assertIn("state_u32_at_0x8c", self.source)
        self.assertNotIn("state_u32_at_0x90", self.source)


if __name__ == "__main__":
    unittest.main()
