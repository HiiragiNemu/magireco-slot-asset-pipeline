import struct
import unittest

from tools.frida_runtime_probe.extract_story_pattern_table_authority import (
    ROW_SIZE,
    classify_static_reachability,
    decode_pattern_table,
    standard_three_event_bindings,
)


class StoryPatternTableAuthorityTests(unittest.TestCase):
    def test_decodes_twenty_by_nine_grid_without_old_eighty_byte_stride(self):
        values = [0] * (20 * 9)
        code_a = int.from_bytes(b"nf8cf@bI", "little")
        code_b = int.from_bytes(b"nf8cYvrw", "little")
        code_c = int.from_bytes(b"nf8cx-$j", "little")
        for row in range(10):
            values[row * 9] = code_a
        for row in range(10, 20):
            values[row * 9] = code_b
        values[19 * 9 + 5] = code_c
        blob = b"prefix" + b"".join(struct.pack("<Q", value) for value in values) + b"suffix"

        rows = decode_pattern_table(blob, table_offset=6, table_size=20 * ROW_SIZE)
        nonzero = [row for row in rows if not row["is_zero"]]

        self.assertEqual(180, len(rows))
        self.assertEqual(21, len(nonzero))
        self.assertEqual("nf8cf@bI", nonzero[0]["code_ascii_le"])
        self.assertEqual((19, 5, "nf8cx-$j"), (
            nonzero[-1]["row_index"],
            nonzero[-1]["selector_raw"],
            nonzero[-1]["code_ascii_le"],
        ))
        self.assertEqual(
            {
                f"0x{code_a:016x}": "ac7109_001",
                f"0x{code_b:016x}": "ac7109_002",
                f"0x{code_c:016x}": "ac7109_003",
            },
            standard_three_event_bindings(rows, "ac7109"),
        )

    def test_rejects_non_integral_grid(self):
        with self.assertRaisesRegex(ValueError, "not divisible"):
            decode_pattern_table(b"\0" * (ROW_SIZE + 1), table_offset=0, table_size=ROW_SIZE + 1)

    def test_reachability_requires_executable_reference(self):
        self.assertEqual(
            "active_dispatcher_static_reference",
            classify_static_reachability(pointer_symbol_present=True, executable_reference_count=2),
        )
        self.assertEqual(
            "pointer_export_present_but_no_executable_reference",
            classify_static_reachability(pointer_symbol_present=True, executable_reference_count=0),
        )
        self.assertEqual(
            "orphan_exported_pattern_table_no_executable_reference",
            classify_static_reachability(pointer_symbol_present=False, executable_reference_count=0),
        )


if __name__ == "__main__":
    unittest.main()
