from __future__ import annotations

import struct
import unittest

from tools.frida_runtime_probe.extract_z2d_movie_layer_blend_authority import (
    BlendAuthorityError,
    parse_movie_layer,
    parse_z2d_header,
)


def movie_layer(reference: str, *, flags: int, blend: int, start: int, end: int) -> bytes:
    data = bytearray(struct.pack("<II", 10 << 27, 0))
    data.extend(f"[{reference}]\0".encode("ascii"))
    while len(data) % 4:
        data.append(0)
    data.extend(b"\0\0")
    data.extend(struct.pack("<H", flags))
    if flags & 0x400:
        data.extend(struct.pack("<2H", start, end))
    else:
        data.extend(struct.pack("<I", blend))
        data.extend(struct.pack("<2H", start, end))
    data.extend(struct.pack("<4f2H", 512.0, 288.0, 512.0, 288.0, 1024, 576))
    return bytes(data)


class Z2DMovieLayerBlendAuthorityTests(unittest.TestCase):
    def test_default_blend_uses_renderer_state_one(self) -> None:
        row = parse_movie_layer(
            movie_layer("entry.dgm", flags=0x077E, blend=0, start=0, end=21),
            "entry.dgm",
            [2, 3, 4],
        )
        self.assertEqual(row["authored_blend_enum"], 0)
        self.assertEqual(row["effective_renderer_state"], 1)
        self.assertEqual(row["frame_count"], 22)
        self.assertEqual(row["position"], [512.0, 288.0])
        self.assertEqual(row["pivot"], [512.0, 288.0])
        self.assertEqual((row["layer_width"], row["layer_height"]), (1024, 576))

    def test_explicit_blend_uses_exact_code_table(self) -> None:
        row = parse_movie_layer(
            movie_layer("effect.dgm", flags=0x037E, blend=2, start=60, end=259),
            "effect.dgm",
            [2, 3, 4],
        )
        self.assertEqual(row["authored_blend_enum"], 2)
        self.assertEqual(row["effective_renderer_state"], 3)
        self.assertEqual((row["start_frame"], row["end_frame_inclusive"]), (60, 259))

    def test_missing_or_duplicate_bracketed_reference_fails_closed(self) -> None:
        with self.assertRaisesRegex(BlendAuthorityError, "found 0"):
            parse_movie_layer(b"no layer", "missing.dgm", [2, 3, 4])
        duplicate = movie_layer("same.dgm", flags=0x077E, blend=0, start=0, end=1) * 2
        with self.assertRaisesRegex(BlendAuthorityError, "found 2"):
            parse_movie_layer(duplicate, "same.dgm", [2, 3, 4])

    def test_truncated_geometry_fails_closed(self) -> None:
        data = movie_layer("short.dgm", flags=0x077E, blend=0, start=0, end=1)[:-1]
        with self.assertRaisesRegex(BlendAuthorityError, "geometry is truncated"):
            parse_movie_layer(data, "short.dgm", [2, 3, 4])

    def test_parses_exact_z2d_scene_and_canvas_header(self) -> None:
        data = bytearray(0xA0)
        data[:4] = b"z2d\0"
        struct.pack_into("<4I", data, 4, 15, 0, 86, 22)
        struct.pack_into("<f", data, 0x14, 30.0)
        data[0x78 : 0x78 + len(b"entry.z2d\0")] = b"entry.z2d\0"
        cursor = (0x78 + len(b"entry.z2d\0") + 3) & ~3
        struct.pack_into("<3I", data, cursor, 0, 1024, 576)
        header = parse_z2d_header(bytes(data))
        self.assertEqual(header["scene_frame_count"], 87)
        self.assertEqual(header["scene_loop_frame"], 22)
        self.assertEqual((header["canvas_width"], header["canvas_height"]), (1024, 576))


if __name__ == "__main__":
    unittest.main()
