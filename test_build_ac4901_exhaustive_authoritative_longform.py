from __future__ import annotations

import unittest
from unittest import mock
from pathlib import Path

from tools.frida_runtime_probe import (
    build_ac4901_exhaustive_authoritative_longform as MODULE,
)


class Ac4901ExhaustiveAuthoritativeLongformTests(unittest.TestCase):
    def test_frozen_content_group_dimensions(self) -> None:
        self.assertEqual(1, 1)
        self.assertEqual(205, MODULE.EXPECTED_SOURCE_EVENTS)
        self.assertEqual(162, MODULE.EXPECTED_ROUTES)
        self.assertEqual(720, MODULE.EXPECTED_ROUTE_OCCURRENCES)
        self.assertEqual(220, MODULE.EXPECTED_UNITS)
        self.assertEqual(194, MODULE.EXPECTED_UNIQUE_CRI_SOURCES)
        self.assertEqual(35654, MODULE.EXPECTED_FRAMES)

    def test_projection_key_is_exact_parent_identity(self) -> None:
        row = {
            "scene": "scene",
            "cut": "cut",
            "parent_z2d": "parent",
            "source_name": "movie",
        }
        self.assertEqual("scene|cut|parent|movie", MODULE._projection_key(row))

    def test_incrementing_segment_filter_uses_exact_source_and_event_frames(self) -> None:
        text = MODULE._source_branch_filter(
            "s",
            {
                "source_start_frame": 3,
                "source_end_frame_inclusive": 7,
                "frame_count": 5,
                "event_start_frame": 45,
                "source_progression": "increment_1",
            },
            shift_to_event=True,
        )
        self.assertIn("trim=start_frame=3:end_frame=8", text)
        self.assertIn("setpts=PTS-STARTPTS+45/30/TB", text)

    def test_held_segment_repeats_one_source_frame_only(self) -> None:
        text = MODULE._source_branch_filter(
            "s",
            {
                "source_start_frame": 9,
                "source_end_frame_inclusive": 9,
                "frame_count": 4,
                "event_start_frame": 12,
                "source_progression": "hold",
            },
            shift_to_event=False,
        )
        self.assertIn("trim=start_frame=9:end_frame=10", text)
        self.assertIn("tpad=stop_mode=clone:stop=3", text)
        self.assertNotIn("+12/30/TB", text)

    def test_media_probe_contract_requires_one_416x232_h264_aac_product(self) -> None:
        value = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 416,
                    "height": 232,
                    "avg_frame_rate": "30/1",
                    "nb_read_frames": "35654",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
            "chapters": [{} for _ in range(220)],
        }
        checks = MODULE.validate_probe(value)
        self.assertTrue(all(checks.values()))
        value["streams"][0]["nb_read_frames"] = "35653"
        with self.assertRaisesRegex(MODULE.Ac4901LongformBuildError, "media QA"):
            MODULE.validate_probe(value)

    def test_underlay_unit_filename_is_windows_safe(self) -> None:
        self.assertEqual(
            "ac4901_091__on__ac4901_025.nut",
            MODULE._unit_filename("ac4901_091@ac4901_025"),
        )

    def test_longform_audio_filter_uses_audio_timestamp_operator(self) -> None:
        captured = {}

        def fake_run(command, _log):
            captured["command"] = list(command)

        with mock.patch.object(MODULE, "run", side_effect=fake_run):
            MODULE.render_none_longform(
                "ffmpeg",
                Path("units.ffconcat"),
                Path("chapters.ffmeta"),
                Path("output.mp4"),
                Path("render.log"),
            )
        graph = captured["command"][captured["command"].index("-filter_complex") + 1]
        self.assertIn("atrim=end_sample=57046400,asetpts=PTS-STARTPTS[a]", graph)
        self.assertNotIn("atrim=end_sample=57046400,setpts=", graph)


if __name__ == "__main__":
    unittest.main()
