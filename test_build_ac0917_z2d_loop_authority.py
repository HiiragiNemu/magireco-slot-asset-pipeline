from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac0917_z2d_loop_authority as MODULE


class Ac0917Z2DLoopAuthorityTests(unittest.TestCase):
    def test_frozen_dimensions_are_explicit(self) -> None:
        self.assertEqual(12, MODULE.EXPECTED["events"])
        self.assertEqual(13, MODULE.EXPECTED["movie_parents"])
        self.assertEqual(3, MODULE.EXPECTED["extended_loop_parents"])
        self.assertEqual(207, MODULE.EXPECTED["loop_extension_frames"])
        self.assertEqual(2711, MODULE.EXPECTED["scheduled_movie_frame_occurrences"])
        self.assertEqual(31, MODULE.EXPECTED["render_segments"])

    def test_shared_code_mapping_repeats_only_exact_loop_interval(self) -> None:
        mapped = [
            MODULE.scene_frame_at(
                event_frame=frame,
                key_start_frame=0,
                scene_start_frame=0,
                scene_end_frame_inclusive=179,
                scene_loop_frame=150,
                motion_mode=3,
            )
            for frame in (149, 150, 179, 180, 209, 210, 279)
        ]
        self.assertEqual([149, 150, 179, 150, 179, 150, 159], mapped)

    def test_output_binding_names_final_immutable_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / ".stage"
            stage.mkdir()
            source = stage / "proof.txt"
            source.write_text("proof\n", encoding="utf-8")
            bound = MODULE._bind_output(source, root / "published")
        self.assertEqual(str((root / "published" / "proof.txt").resolve()), bound["path"])
        self.assertEqual(64, len(bound["sha256"]))

    def test_all_events_are_frozen_without_p16_p17_p18(self) -> None:
        self.assertEqual(12, len(MODULE.EVENT_IDS))
        self.assertTrue(all(event.startswith("ac0917_") for event in MODULE.EVENT_IDS))


if __name__ == "__main__":
    unittest.main()
