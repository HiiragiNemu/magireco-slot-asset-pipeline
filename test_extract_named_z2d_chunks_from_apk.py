from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.extract_named_z2d_chunks_from_apk import (
    ExtractionError,
    extract_optional_dgm_references,
    parse_offsets,
    target_ranges,
)


class NamedZ2DChunkTests(unittest.TestCase):
    def test_offsets_accept_explicit_terminal(self):
        offsets = parse_offsets(struct.pack("<4I", 0, 3, 8, 12), 12)
        self.assertEqual(offsets, [0, 3, 8, 12])

    def test_offsets_append_missing_terminal(self):
        offsets = parse_offsets(struct.pack("<3I", 0, 3, 8), 12)
        self.assertEqual(offsets, [0, 3, 8, 12])

    def test_exact_name_ranges_are_stable(self):
        rows = target_ranges(["a", "b", "c"], [0, 3, 8, 12], ["c", "a"])
        self.assertEqual(
            rows,
            [
                {"name": "c", "chunk_index": 2, "offset": 8, "size": 4},
                {"name": "a", "chunk_index": 0, "offset": 0, "size": 3},
            ],
        )

    def test_missing_or_duplicate_names_fail_closed(self):
        with self.assertRaises(ExtractionError):
            target_ranges(["a", "b"], [0, 2, 4], ["c"])
        with self.assertRaises(ExtractionError):
            target_ranges(["a", "b"], [0, 2, 4], ["a", "a"])

    def test_image_only_z2d_is_valid_without_dgm_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "caption.z2d"
            target.write_bytes(b"z2d\x00image-only-caption")
            references, status = extract_optional_dgm_references(target)
        self.assertEqual(references, [])
        self.assertEqual(status, "no_authored_dgm_reference")

    def test_dgm_reference_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "movie.z2d"
            target.write_bytes(b"z2d\x00[scene_movie.dgm]\x00")
            references, status = extract_optional_dgm_references(target)
        self.assertEqual(references, ["scene_movie.dgm"])
        self.assertEqual(status, "authored_dgm_references")


if __name__ == "__main__":
    unittest.main()
