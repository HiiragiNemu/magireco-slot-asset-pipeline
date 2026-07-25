import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parent
    / "tools"
    / "frida_runtime_probe"
    / "build_ac0908_reference_showcase.py"
)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location(
    "build_ac0908_reference_showcase", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildAc0908ReferenceShowcaseTest(unittest.TestCase):
    def test_samples_and_frame_grid_are_exact(self):
        self.assertEqual(MODULE.SAMPLES_PER_FRAME, 1600)
        self.assertEqual(MODULE.milliseconds_for_samples(1600), 33)
        self.assertEqual(MODULE.milliseconds_for_samples(139 * 1600), 4633)

    def test_sha256_validation_is_fail_closed(self):
        good = "A" * 64
        self.assertEqual(MODULE._valid_sha256(good.lower()), good)
        for bad in ("", "A" * 63, "G" * 64):
            with self.assertRaises(ValueError):
                MODULE._valid_sha256(bad)

    def test_status_never_claims_publication_readiness(self):
        self.assertIn("HUMAN_REVIEW_REQUIRED", MODULE.STATUS)
        self.assertNotIn("BILIBILI_RELEASE_READY", MODULE.STATUS)

    def test_output_manifest_path_is_stable_and_relative(self):
        staging = Path.cwd() / "candidate.staging"
        output = staging / "REVIEW_NOW_1_MP4" / "candidate.mp4"
        self.assertEqual(
            MODULE.relative_output_path(output, staging=staging),
            "REVIEW_NOW_1_MP4/candidate.mp4",
        )
        with self.assertRaises(ValueError):
            MODULE.relative_output_path(Path.cwd() / "outside.mp4", staging=staging)


if __name__ == "__main__":
    unittest.main()
