import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_incremental_route_review_package as module  # noqa: E402


class BuildIncrementalRouteReviewPackageTest(unittest.TestCase):
    def test_safe_filename_fragment(self) -> None:
        self.assertEqual(
            module._safe_fragment("黑羽选项", label="title"),
            "黑羽选项",
        )
        for value in ("", "..", "bad/name", "bad:name", "bad."):
            with self.assertRaises(ValueError):
                module._safe_fragment(value, label="title")

    def test_part_names_keep_target_tracks_distinct(self) -> None:
        self.assertEqual(
            module._part_name("黑羽选项路线06", "ac4902", "none"),
            "黑羽选项路线06 ac4902",
        )
        self.assertEqual(
            module._part_name("黑羽选项路线06", "ac4902", "ja"),
            "黑羽选项路线06 ac4902__ja",
        )
        self.assertEqual(
            module._part_name("黑羽选项路线06", "ac4902", "zh"),
            "黑羽选项路线06 ac4902 中文版",
        )


if __name__ == "__main__":
    unittest.main()
