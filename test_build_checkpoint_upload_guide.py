import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_checkpoint_upload_guide as module  # noqa: E402


class BuildCheckpointUploadGuideTest(unittest.TestCase):
    def test_media_extraction_ignores_excluded_rows(self) -> None:
        value = {
            "routes": [
                {
                    "title": "ready",
                    "media": {
                        "zh": {"path": "video/ready.mp4", "sha256": "A" * 64}
                    },
                }
            ],
            "excluded_dirinfo_rows": [
                {
                    "media": {
                        "zh": {
                            "path": "superseded/bad.mp4",
                            "sha256": "B" * 64,
                        }
                    }
                }
            ],
        }
        rows = module._manifest_media(
            value,
            family_root=Path("D:/durable/current"),
            family="ac0001",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(Path(rows[0]["path"]).name, "ready.mp4")

    def test_family_targets_are_explicit(self) -> None:
        plan = {
            "target_bvs": {
                "ac0911_route_catalog": "new ac0911 BV",
                "ac4903_route_catalog": "new ac4903 BV",
                "ac6007_route_catalog": "new ac6007 BV",
                "future_catalog": "future BV",
            }
        }
        self.assertEqual(
            module._batch_target(plan, "ac4903", "route"),
            "new ac4903 BV",
        )
        self.assertEqual(
            module._batch_target(plan, "ac9999", "route"),
            "future BV",
        )
        self.assertEqual(
            module._batch_target(plan, "ac6007", "route"),
            "new ac6007 BV",
        )
        self.assertEqual(
            module._batch_target(plan, "ac0911", "route"),
            "new ac0911 BV",
        )


if __name__ == "__main__":
    unittest.main()
