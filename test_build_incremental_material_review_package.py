import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_incremental_material_review_package as module  # noqa: E402


class BuildIncrementalMaterialReviewPackageTest(unittest.TestCase):
    def test_bound_file_rejects_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            source = root / "source.json"
            source.write_text("{}\n", encoding="utf-8")
            binding = {
                "path": "source.json",
                "sha256": module.file_sha256(source),
            }
            self.assertEqual(
                module.validate_bound_file(
                    binding,
                    label="source",
                    base=root,
                ),
                source.resolve(),
            )
            source.write_text('{"changed":true}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                module.validate_bound_file(
                    binding,
                    label="source",
                    base=root,
                )

    def test_cross_target_names_and_targets_remain_distinct(self) -> None:
        self.assertEqual(
            module._part_name("黑江瞄准玩法素材", "ac2201", "none"),
            "黑江瞄准玩法素材 ac2201",
        )
        self.assertEqual(
            module._part_name("黑江瞄准玩法素材", "ac2201", "ja"),
            "黑江瞄准玩法素材 ac2201__ja",
        )
        self.assertEqual(
            module._part_name("黑江瞄准玩法素材", "ac2201", "zh"),
            "黑江瞄准玩法素材 ac2201 中文版",
        )
        self.assertEqual(len({module._target(value) for value in module.EDITIONS}), 3)


if __name__ == "__main__":
    unittest.main()
