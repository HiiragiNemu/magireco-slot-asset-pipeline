from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from tools.frida_runtime_probe import build_ac4901_z2d_loop_authority as MODULE


class Ac4901Z2DLoopAuthorityTests(unittest.TestCase):
    def test_intro_then_loop_maps_exact_scene_frames(self) -> None:
        def mapped(frame: int) -> int | None:
            return MODULE.scene_frame_at(
                event_frame=frame,
                key_start_frame=0,
                scene_start_frame=0,
                scene_end_frame_inclusive=74,
                scene_loop_frame=45,
                motion_mode=3,
            )

        self.assertEqual(
            [0, 44, 45, 74, 45, 74, 45, 59],
            [mapped(frame) for frame in (0, 44, 45, 74, 75, 104, 105, 119)],
        )

    def test_whole_scene_loop_respects_nonzero_key_start(self) -> None:
        values = [
            MODULE.scene_frame_at(
                event_frame=frame,
                key_start_frame=30,
                scene_start_frame=0,
                scene_end_frame_inclusive=29,
                scene_loop_frame=0,
                motion_mode=2,
            )
            for frame in (30, 59, 60, 89)
        ]
        self.assertEqual([0, 29, 0, 29], values)

    def test_hold_and_play_once_differ_after_scene_end(self) -> None:
        hold = MODULE.scene_frame_at(
            event_frame=60,
            key_start_frame=0,
            scene_start_frame=0,
            scene_end_frame_inclusive=29,
            scene_loop_frame=0,
            motion_mode=1,
        )
        once = MODULE.scene_frame_at(
            event_frame=60,
            key_start_frame=0,
            scene_start_frame=0,
            scene_end_frame_inclusive=29,
            scene_loop_frame=0,
            motion_mode=0,
        )
        self.assertEqual(29, hold)
        self.assertIsNone(once)

    def test_compression_splits_at_source_and_loop_reset(self) -> None:
        rows = [
            {
                "event_frame": event,
                "scene_frame": scene,
                "source_frame": source,
                "source_name": name,
                "projection_key": f"p|{name}",
            }
            for event, scene, source, name in (
                (0, 0, 0, "intro"),
                (1, 1, 1, "intro"),
                (2, 2, 0, "loop"),
                (3, 3, 1, "loop"),
                (4, 2, 0, "loop"),
                (5, 3, 1, "loop"),
            )
        ]
        segments = MODULE.compress_source_frames(rows)
        self.assertEqual(3, len(segments))
        self.assertEqual([2, 2, 2], [row["frame_count"] for row in segments])
        self.assertEqual(
            ["intro", "loop", "loop"], [row["source_name"] for row in segments]
        )

    def test_frozen_ac4901_dimensions_are_explicit(self) -> None:
        self.assertEqual(205, MODULE.EXPECTED_EVENTS)
        self.assertEqual(335, MODULE.EXPECTED_MOVIE_PARENTS)
        self.assertEqual(108, MODULE.EXPECTED_EXTENDED_LOOP_PARENTS)
        self.assertEqual(4392, MODULE.EXPECTED_LOOP_EXTENSION_FRAMES)
        self.assertEqual(40326, MODULE.EXPECTED_SCHEDULED_MOVIE_FRAME_OCCURRENCES)
        self.assertEqual(771, MODULE.EXPECTED_RENDER_SEGMENTS)

    def test_published_output_binding_uses_final_immutable_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / ".stage"
            stage.mkdir()
            source = stage / "proof.txt"
            source.write_text("proof\n", encoding="utf-8")
            expected_size = source.stat().st_size
            output = root / "published"
            bound = MODULE.bind_published_output(source, output)
        self.assertEqual(str((output / "proof.txt").resolve()), bound["path"])
        self.assertEqual(expected_size, bound["size_bytes"])
        self.assertEqual(64, len(bound["sha256"]))


if __name__ == "__main__":
    unittest.main()
