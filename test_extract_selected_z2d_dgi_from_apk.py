from __future__ import annotations

import struct
import unittest

from tools.frida_runtime_probe.extract_selected_z2d_dgi_from_apk import (
    SelectedDgiError,
    extract_references,
    parse_caption_sprite_layers,
)


class SelectedZ2DDgiTests(unittest.TestCase):
    def test_extracts_unique_jm_dgi_references_in_file_order(self) -> None:
        data = (
            b"JM_4E07_00009N7X_MR100.dgi\0"
            b"JM_FF01_00009N7X_MR100.dgi\0"
            b"JM_4E07_00009N7X_MR100.dgi\0"
        )
        self.assertEqual(
            extract_references(data),
            ["JM_4E07_00009N7X_MR100", "JM_FF01_00009N7X_MR100"],
        )

    def test_parses_exact_caption_sprite_layout(self) -> None:
        name = "JM_4E07_00009N7X_MR100"
        data = bytearray(f"<<{name}.png/418.52>>\0".encode("ascii"))
        while len(data) % 4:
            data.append(0)
        data.extend(struct.pack("<2H", 0, 0x077E))
        data.extend(struct.pack("<2H", 0, 29))
        data.extend(struct.pack("<4f", 432.52, 516.0, 32.2, 32.2))
        data.extend(struct.pack("<2hI", 56, 56, (2 << 27) | 11))
        rows = parse_caption_sprite_layers(bytes(data))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["resource_name"], name)
        self.assertEqual((rows[0]["start_frame"], rows[0]["end_frame_inclusive"]), (0, 29))
        self.assertAlmostEqual(rows[0]["position_x"], 432.52, places=2)
        self.assertEqual((rows[0]["source_width"], rows[0]["source_height"]), (56, 56))
        self.assertEqual(rows[0]["image_index"], 11)

    def test_caption_flags_fail_closed(self) -> None:
        name = "JM_4E07_00009N7X_MR100"
        data = bytearray(f"<<{name}.png/x>>\0".encode("ascii"))
        while len(data) % 4:
            data.append(0)
        data.extend(struct.pack("<2H", 0, 0x0000))
        data.extend(bytes(40))
        with self.assertRaisesRegex(SelectedDgiError, "flags differ"):
            parse_caption_sprite_layers(bytes(data))


if __name__ == "__main__":
    unittest.main()
