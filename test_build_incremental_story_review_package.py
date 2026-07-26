import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_incremental_story_review_package as module  # noqa: E402


class BuildIncrementalStoryReviewPackageTest(unittest.TestCase):
    def test_part_names_are_track_specific(self) -> None:
        self.assertEqual(
            module._part_name("枫的魔女化身", "ac7115_001", "none"),
            "枫的魔女化身 ac7115_001",
        )
        self.assertEqual(
            module._part_name("枫的魔女化身", "ac7115_001", "ja"),
            "枫的魔女化身 ac7115_001__ja",
        )
        self.assertEqual(
            module._part_name("枫的魔女化身", "ac7115_001", "zh"),
            "枫的魔女化身 ac7115_001 中文版",
        )

    def test_guide_path_index_rejects_duplicate_exact_files(self) -> None:
        row = {
            "absolute_folder": "D:/durable/review",
            "exact_filename": "same.mp4",
        }
        with self.assertRaisesRegex(ValueError, "duplicate upload-guide path"):
            module._guide_item_by_path({"items": [row, dict(row)]})


if __name__ == "__main__":
    unittest.main()
