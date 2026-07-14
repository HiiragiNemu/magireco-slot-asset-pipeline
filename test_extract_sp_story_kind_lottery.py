from __future__ import annotations

import struct
import unittest

from tools.frida_runtime_probe.extract_sp_story_kind_lottery import (
    decode_lottery_table_bytes,
    flatten_table_rows,
)


def table_bytes(*entries: tuple[int, int]) -> bytes:
    return b"".join(struct.pack("<QQ", weight, result) for weight, result in entries)


class DecodeLotteryTableBytesTests(unittest.TestCase):
    def test_decodes_weight_result_kind_and_probability_until_sentinel(self) -> None:
        decoded = decode_lottery_table_bytes(
            table_bytes(
                (0x2AAB, 2),
                (0x2AAB, 3),
                (0x2AAA, 5),
                (0x8000, 0),
                (0x1234, 99),
            )
        )

        self.assertEqual(decoded["entry_count"], 3)
        self.assertEqual(decoded["weight_total"], 0x8000)
        self.assertEqual([row["kind"] for row in decoded["entries"]], [11, 12, 14])
        self.assertAlmostEqual(decoded["entries"][0]["probability"], 0x2AAB / 0x8000)
        self.assertEqual(decoded["sentinel"]["entry_index"], 3)
        self.assertEqual(decoded["sentinel"]["result"], 0)

    def test_result_zero_maps_to_kind_nine(self) -> None:
        decoded = decode_lottery_table_bytes(
            table_bytes((0x6E00, 0), (0x1200, 4), (0x8000, 0))
        )

        self.assertEqual(decoded["entries"][0]["kind"], 9)
        self.assertEqual(decoded["entries"][1]["kind"], 13)
        self.assertEqual(decoded["probability_total"], 1.0)

    def test_rejects_a_table_without_a_sentinel(self) -> None:
        with self.assertRaisesRegex(ValueError, "sentinel 0x8000"):
            decode_lottery_table_bytes(table_bytes((0x400, 2), (0x7400, 4)))

    def test_flattened_rows_keep_table_provenance(self) -> None:
        decoded = decode_lottery_table_bytes(
            table_bytes((0x400, 2), (0x7C00, 4), (0x8000, 0))
        )
        rows = flatten_table_rows(
            [
                {
                    "table_index": 2,
                    "label": "OT_AT_SpStryKnd_02",
                    "descriptor_address": "0x4b28e80",
                    "table_pointer": "0x30c1998",
                    **decoded,
                }
            ]
        )

        self.assertEqual(rows[0]["label"], "OT_AT_SpStryKnd_02")
        self.assertEqual(rows[0]["entry_address"], "0x30c1998")
        self.assertEqual(rows[1]["entry_address"], "0x30c19a8")
        self.assertEqual(rows[1]["kind"], 13)


if __name__ == "__main__":
    unittest.main()
