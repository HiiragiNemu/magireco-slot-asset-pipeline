import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parent
    / "tools"
    / "frida_runtime_probe"
    / "build_unified_current_production_checkpoint.py"
)
SPEC = importlib.util.spec_from_file_location("unified_current", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class UnifiedCurrentProductionCheckpointTest(unittest.TestCase):
    def test_human_view_classification(self) -> None:
        self.assertEqual(
            module.edition_folder(
                {
                    "subtitle_track": "material; no audio; no burned-in subtitles",
                    "exact_filename": "component.mp4",
                }
            ),
            "material",
        )
        self.assertEqual(
            module.edition_folder(
                {
                    "subtitle_track": "visual-only; no audio; no burned-in subtitles",
                    "exact_filename": "legacy_component.mp4",
                }
            ),
            "material",
        )
        self.assertEqual(
            module.edition_folder(
                {"subtitle_track": "JA burned-in", "exact_filename": "story__ja.mp4"}
            ),
            "jp",
        )
        self.assertEqual(module.state_folder("ready_to_upload"), "01_已审查可上传")
        self.assertEqual(
            module.material_filename(
                {"suggested_part_name": "小丘比动作素材 ac0906"},
                "catalog__416x232_30-1.mp4",
            ),
            "小丘比动作素材 ac0906 [416x232].mp4",
        )

    def test_guide_verifier_binds_exact_files_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            media = root / "media.mp4"
            media.write_bytes(b"exact-media")
            guide = {
                "items": [
                    {
                        "state": "human_playback_required",
                        "absolute_folder": str(root),
                        "exact_filename": media.name,
                        "sha256": module.file_sha256(media),
                    }
                ],
                "counts": {
                    "already_uploaded": 0,
                    "ready_to_upload": 0,
                    "human_playback_required": 1,
                    "total_exact_files": 1,
                },
            }
            result = module.validate_guide_files(guide)
            self.assertEqual(result["exact_file_count"], 1)
            self.assertEqual(result["unique_declared_folder_count"], 1)

            media.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                module.validate_guide_files(guide)

    def test_v43_requires_all_families_and_false_approval(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            names = ["a", "b", "c", "d"]
            for name in names:
                (root / name).mkdir()
            summary = {
                "families": [str(root / name) for name in names],
                "human_playback_approved": False,
                "publication_approved": False,
                "bilibili_release_ready": False,
            }
            module.validate_v43_summary(summary, names)
            summary["publication_approved"] = True
            with self.assertRaisesRegex(ValueError, "must remain false"):
                module.validate_v43_summary(summary, names)

    def test_bound_json_fails_closed_on_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "source.json"
            path.write_text(json.dumps({"ok": True}), encoding="utf-8")
            binding = {"path": str(path), "sha256": module.file_sha256(path)}
            actual_path, payload = module.validate_bound_json(
                binding,
                label="fixture",
            )
            self.assertEqual(actual_path, path.resolve())
            self.assertTrue(payload["ok"])
            path.write_text(json.dumps({"ok": False}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                module.validate_bound_json(binding, label="fixture")


if __name__ == "__main__":
    unittest.main()
