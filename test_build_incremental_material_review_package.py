import json
import subprocess
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
    def test_historical_hash_bound_inputs_keep_exact_bytes_in_git(self) -> None:
        disposition = json.loads((ROOT / "docs/research/2026-10-03-backlog-disposition.json").read_text(encoding="utf-8"))
        paths = disposition["exact_byte_git_inputs"]
        self.assertEqual(len(paths), 64)
        result = subprocess.run(
            ["git", "check-attr", "-z", "--stdin", "text"],
            input=("\0".join(paths) + "\0").encode("utf-8"), cwd=ROOT,
            capture_output=True, check=True,
        )
        fields = result.stdout.rstrip(b"\0").split(b"\0")
        self.assertEqual(len(fields), len(paths) * 3)
        self.assertTrue(all(value == b"unset" for value in fields[2::3]))

    def test_ac4906_correction_keeps_both_materials_without_language_aliases(self) -> None:
        plan = module.read_json(
            ROOT
            / "tools"
            / "frida_runtime_probe"
            / "series_proposals"
            / "incremental_material_review_v59r2_ac4906_single_visual_correction_20260802.json"
        )
        self.assertEqual(plan["packaging_mode"], "single_visual_canonical")
        products = {row["title"]: row for row in plan["products"]}
        self.assertEqual(len(products), 2)
        self.assertEqual(
            products["Magius白色阶段玩法组件"]["publication_state"],
            "ready_to_upload",
        )
        self.assertEqual(
            products["Magius暗转叠加组件"]["presentation_role"],
            "layer_component_material",
        )
        self.assertEqual(
            products["Magius暗转叠加组件"]["publication_state"],
            "already_uploaded",
        )
        self.assertNotIn("withdrawn", json.dumps(plan, ensure_ascii=False))

    def test_publication_requires_human_approval(self) -> None:
        for publication in ("ready_to_upload", "already_uploaded"):
            with self.subTest(publication=publication):
                with self.assertRaisesRegex(ValueError, "requires exact human"):
                    module.validate_publication_state("human_playback_required", publication)
                module.validate_publication_state("human_playback_approved", publication)
        module.validate_publication_state("human_playback_required", "human_playback_required")
        module.validate_publication_state("human_playback_approved", "human_playback_required")
        for human, publication in (("AUTO_QA_PASS", "ready_to_upload"), ("human_playback_approved", "unknown")):
            with self.assertRaises(ValueError):
                module.validate_publication_state(human, publication)

    def test_revision_checkpoint_labels_are_supported(self) -> None:
        self.assertRegex("v59r2", r"^v\d+(?:r\d+)?$")

    def test_current_plan_modes_are_single_visual_only(self) -> None:
        self.assertIn("single_visual_canonical", module.PACKAGING_MODES)
        self.assertEqual(module.MATERIAL_EDITION, "material")

    def test_metadata_fix_disposition_is_explicitly_supported(self) -> None:
        source = Path(module.__file__).read_text(encoding="utf-8")
        self.assertIn("superseded_by_review_batch_metadata_fix", source)

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

    def test_single_visual_name_and_target_have_no_language_variant(self) -> None:
        self.assertEqual(
            module._part_name("黑江瞄准玩法素材", "ac2201", "material"),
            "黑江瞄准玩法素材 ac2201（视觉素材）",
        )
        self.assertEqual(
            module._target("material", 208, 120),
            "新建建议：MagiaReco Slot 原生208x120玩法／素材合集 BV",
        )
        self.assertEqual(
            module._packaged_filename(
                "U144",
                "Magius白色阶段玩法组件",
                "ac4906",
                "material",
            ),
            "U144_Magius白色阶段玩法组件_ac4906.mp4",
        )
        self.assertNotIn(
            "__none",
            module._packaged_filename("U144", "素材", "ac4906", "material"),
        )

    def test_legacy_cross_target_names_and_targets_remain_distinct(self) -> None:
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
        self.assertEqual(
            len({module._target(value) for value in module.LEGACY_EDITIONS}),
            3,
        )
        self.assertIn(
            "原生512x288",
            module._target("none", 512, 288),
        )

    def test_review_batches_split_at_ten_products_without_language_aliases(self) -> None:
        products = [
            {
                "collection": f"ac9000_component_{index:02d}",
                "publication_state": "human_playback_required",
                "duration_seconds": 1.0,
            }
            for index in range(11)
        ]
        assignments = module.assign_review_batches(products)
        self.assertEqual(assignments["ac9000_component_09"], "batch_001")
        self.assertEqual(assignments["ac9000_component_10"], "batch_002")
        self.assertEqual(len(assignments), 11)
        self.assertEqual(
            module.review_batch_directories(
                "single_visual_canonical", ("material",), assignments
            ),
            [
                "02_REVIEW_MATERIAL/batch_001",
                "02_REVIEW_MATERIAL/batch_002",
            ],
        )
        self.assertEqual(len(set(assignments.values())), 2)

    def test_review_batches_split_at_duration_limit(self) -> None:
        products = [
            {
                "collection": "ac9000_component_a",
                "publication_state": "human_playback_required",
                "duration_seconds": 1799.0,
            },
            {
                "collection": "ac9000_component_b",
                "publication_state": "human_playback_required",
                "duration_seconds": 2.0,
            },
            {
                "collection": "ac9000_component_uploaded",
                "publication_state": "already_uploaded",
                "duration_seconds": 9999.0,
            },
        ]
        assignments = module.assign_review_batches(products)
        self.assertEqual(assignments["ac9000_component_a"], "batch_001")
        self.assertEqual(assignments["ac9000_component_b"], "batch_002")
        self.assertNotIn("ac9000_component_uploaded", assignments)


if __name__ == "__main__":
    unittest.main()
