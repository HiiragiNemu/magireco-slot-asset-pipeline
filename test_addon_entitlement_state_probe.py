from __future__ import annotations

import unittest
from pathlib import Path

from tools.frida_runtime_probe.capture_addon_entitlement_state import (
    parse_single_pid,
    validate_snapshot,
)


class AddonEntitlementStateProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (
            Path(__file__).resolve().parent
            / "tools"
            / "frida_runtime_probe"
            / "addon_entitlement_state_probe.js"
        ).read_text(encoding="utf-8")

    def snapshot(self) -> dict:
        return {
            "schema": "magireco-addon-entitlement-snapshot-v1",
            "ok": True,
            "process": {"id": 3125, "arch": "arm64", "pointer_size": 8},
            "read_policy": "seven_named_u32_active_and_saved_fields_no_calls_no_writes",
            "rows": [
                {
                    "index": index,
                    "active_offset": hex(0x14BF4 + index * 4),
                    "active_u32": 0,
                    "active_read_error": "",
                    "saved_offset": hex(0x14A58 + index * 4),
                    "saved_u32": 0,
                    "saved_read_error": "",
                }
                for index in range(7)
            ],
        }

    def test_validates_exact_fixed_field_layout(self) -> None:
        validate_snapshot(self.snapshot(), 3125)

    def test_rejects_pid_arch_offset_and_read_failures(self) -> None:
        cases = []
        wrong_pid = self.snapshot()
        wrong_pid["process"]["id"] = 99
        cases.append(wrong_pid)
        wrong_arch = self.snapshot()
        wrong_arch["process"]["arch"] = "x64"
        cases.append(wrong_arch)
        wrong_offset = self.snapshot()
        wrong_offset["rows"][6]["active_offset"] = "0x0"
        cases.append(wrong_offset)
        read_error = self.snapshot()
        read_error["rows"][2]["saved_read_error"] = "unreadable"
        cases.append(read_error)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_snapshot(value, 3125)

    def test_pid_parser_fails_closed_on_zero_or_multiple(self) -> None:
        self.assertEqual(parse_single_pid("3125\n"), 3125)
        for value in ("", "3125 4000"):
            with self.assertRaises(ValueError):
                parse_single_pid(value)

    def test_probe_has_no_calls_writes_or_arbitrary_dumps(self) -> None:
        self.assertIn("CplayData11getInstanceEvE18mcplayDataInstance", self.source)
        self.assertIn("seven_named_u32_active_and_saved_fields_no_calls_no_writes", self.source)
        for forbidden in (
            "NativeFunction",
            "writeU32",
            "writeS32",
            "writePointer",
            "readByteArray",
            "Memory.scan",
            "Interceptor",
        ):
            self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
