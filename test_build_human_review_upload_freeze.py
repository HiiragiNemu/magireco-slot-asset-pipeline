import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_human_review_upload_freeze as module  # noqa: E402


class BuildHumanReviewUploadFreezeTest(unittest.TestCase):
    def test_route_parser_accepts_hyphenated_dirinfo_names(self) -> None:
        row = {
            "exact_filename": "ac4903__dirinfo-row-008__zh.mp4",
            "suggested_part_name": "",
            "absolute_folder": "D:/durable/video",
        }
        self.assertEqual(module.route_for(row), "8")

    def test_batch_duration_counts_exact_hash_alias_once(self) -> None:
        aliases = [
            {
                "expected_sha256": "A" * 64,
                "duration_seconds": 1000.0,
            }
            for _ in range(3)
        ]
        distinct = [
            {
                "expected_sha256": "B" * 64,
                "duration_seconds": 1000.0,
            }
        ]
        batches = module.make_batches([aliases, distinct])
        self.assertEqual(len(batches), 2)
        self.assertEqual(
            module.unique_duration_seconds(batches[0], "expected_sha256"),
            1000.0,
        )

    def test_edition_target_is_preserved_for_legal_aliases(self) -> None:
        japanese = {
            "target_bv": "新建：MagiaReco Slot 日文字幕路线合集 BV"
        }
        route_catalog = {"target_bv": "新建：ac4903/P13 互斥路线合集 BV"}
        self.assertEqual(
            module.target_bv_for(japanese, "ja", material=False),
            module.BASELINE_BV["ja"],
        )
        self.assertEqual(
            module.target_bv_for(route_catalog, "none", material=False),
            route_catalog["target_bv"],
        )
        self.assertEqual(
            module.target_bv_for(route_catalog, "zh", material=False),
            route_catalog["target_bv"],
        )


if __name__ == "__main__":
    unittest.main()
