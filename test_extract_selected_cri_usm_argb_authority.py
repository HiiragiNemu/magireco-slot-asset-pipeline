from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.extract_selected_cri_usm_argb_authority import (
    CriArgbError,
    read_offsets,
    slice_bounds,
    validate_argb_streams,
)


class SelectedCriUsmArgbAuthorityTests(unittest.TestCase):
    def test_reads_monotonic_offsets_and_appends_package_end(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            binary = root / "cri.bin"
            table = root / "cri_add.bin"
            binary.write_bytes(bytes(30))
            table.write_bytes(struct.pack("<3I", 0, 10, 20))
            self.assertEqual(read_offsets(binary, table), [0, 10, 20, 30])

    def test_slice_bounds_fail_closed_for_empty_slice(self) -> None:
        with self.assertRaisesRegex(CriArgbError, "empty"):
            slice_bounds([0, 10, 10, 20], 1)

    def test_two_matching_video_streams_are_argb_inputs(self) -> None:
        probe = {
            "format": {"format_name": "usm"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "mpeg1video",
                    "width": 416,
                    "height": 232,
                    "r_frame_rate": "30/1",
                    "nb_frames": "30",
                },
                {
                    "index": 1,
                    "codec_type": "video",
                    "codec_name": "mpeg1video",
                    "width": 416,
                    "height": 232,
                    "r_frame_rate": "30/1",
                    "nb_frames": "30",
                },
            ],
        }
        result = validate_argb_streams(probe, "sample")
        self.assertEqual(result["alpha_stream_index"], 1)
        self.assertEqual(result["frame_count"], 30)

    def test_single_video_stream_fails_closed(self) -> None:
        probe = {
            "format": {"format_name": "usm"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "mpeg1video",
                    "width": 416,
                    "height": 232,
                    "r_frame_rate": "30/1",
                    "nb_frames": "30",
                }
            ],
        }
        with self.assertRaisesRegex(CriArgbError, "expected two"):
            validate_argb_streams(probe, "sample")


if __name__ == "__main__":
    unittest.main()
