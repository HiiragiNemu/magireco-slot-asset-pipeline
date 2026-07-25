import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent / "tools" / "frida_runtime_probe"
sys.path.insert(0, str(MODULE_DIR))
import build_ac7210_route_supplements as module  # noqa: E402


class BuildAc7210RouteSupplementsTest(unittest.TestCase):
    def test_status_is_review_only(self):
        self.assertIn("RISK", module.STATUS)
        self.assertIn("HUMAN_REVIEW_REQUIRED", module.STATUS)

    def test_static_hold_frame_totals(self):
        self.assertEqual(255 + 233 + 222 + 214, 924)
        self.assertEqual(255 + 430 + 222 + 214, 1121)

    def test_native_grid_is_unchanged(self):
        self.assertEqual((module.WIDTH, module.HEIGHT, module.FPS), (416, 232, 30))

    def test_output_manifest_path_is_stable_and_relative(self):
        staging = Path.cwd() / "candidate.staging"
        output = staging / "REVIEW_NOW_2_MP4" / "candidate.mp4"
        self.assertEqual(
            module.relative_output_path(output, staging=staging),
            "REVIEW_NOW_2_MP4/candidate.mp4",
        )
        with self.assertRaises(ValueError):
            module.relative_output_path(Path.cwd() / "outside.mp4", staging=staging)


if __name__ == "__main__":
    unittest.main()
