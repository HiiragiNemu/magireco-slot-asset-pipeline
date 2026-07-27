import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_checkpoint_upload_guide as module  # noqa: E402


class BuildCheckpointUploadGuideTest(unittest.TestCase):
    def test_nested_hash_bound_plan_overlays_merge(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            base = root / "base.json"
            middle = root / "middle.json"
            top = root / "top.json"
            base.write_text(
                '{"schema":"x","target_bvs":{"a":"A"},'
                '"directories":{"d":"D"},"sources":{"s":{"path":"x"}},'
                '"incremental_story_products":{"ac0001":{"title":"one"}}}\n',
                encoding="utf-8",
            )
            middle.write_text(
                (
                    '{"base_plan":{"path":"base.json","sha256":"'
                    + module.file_sha256(base)
                    + '"},"target_bvs":{"b":"B"},'
                    '"incremental_story_products":{"ac0002":{"title":"two"}}}\n'
                ),
                encoding="utf-8",
            )
            top.write_text(
                (
                    '{"base_plan":{"path":"middle.json","sha256":"'
                    + module.file_sha256(middle)
                    + '"},"directories":{"e":"E"}}\n'
                ),
                encoding="utf-8",
            )
            plan, snapshots = module._load_plan_with_bases(top)
            self.assertEqual(plan["target_bvs"], {"a": "A", "b": "B"})
            self.assertEqual(plan["directories"], {"d": "D", "e": "E"})
            self.assertEqual(
                plan["incremental_story_products"],
                {
                    "ac0001": {"title": "one"},
                    "ac0002": {"title": "two"},
                },
            )
            self.assertEqual(len(snapshots), 2)

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

    def test_media_extraction_reads_standard_family_video_artifacts(self) -> None:
        value = {
            "release_id": "ac7115_001_full_no_bgm_editions_v1",
            "artifacts": {
                "video_none": {
                    "path": "video/release__none.mp4",
                    "sha256": "A" * 64,
                },
                "video_ja": {
                    "path": "video/release__ja.mp4",
                    "sha256": "B" * 64,
                },
                "video_zh": {
                    "path": "video/release__zh.mp4",
                    "sha256": "C" * 64,
                },
                "subtitles_zh": {
                    "path": "subtitles/release__zh.srt",
                    "sha256": "D" * 64,
                },
            },
        }
        rows = module._manifest_media(
            value,
            family_root=Path("D:/durable/current"),
            family="ac7115_001",
        )
        self.assertEqual(
            {row["edition"] for row in rows},
            {"none", "ja", "zh"},
        )
        self.assertEqual(
            {Path(row["path"]).suffix for row in rows},
            {".mp4"},
        )

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

    def test_material_part_names_are_human_facing_with_safe_fallback(self) -> None:
        self.assertEqual(
            module.material_part_name(
                "ac2201_kuroe_nerae_gameplay_layers_v1"
            ),
            "黑江瞄准玩法素材 ac2201",
        )
        self.assertEqual(
            module.material_part_name("future_collection_v1"),
            "future_collection_v1",
        )
        self.assertEqual(
            module.material_part_name(
                "ac0905_su_gameplay_components_416_v1"
            ),
            "SU玩法组件素材 ac0905",
        )
        self.assertEqual(
            module.material_part_name(
                "ac0916_text_effect_components_160x120_v1"
            ),
            "玩法文字循环效果素材 ac0916",
        )
        self.assertEqual(
            module.material_part_name(
                "ac7211_portrait_standby_component_192x320_v1"
            ),
            "角色立绘待机素材 ac7211",
        )

    def test_current_selector_route_source_is_indexed(self) -> None:
        self.assertIn(
            "v51_ac4902_selector_routes_manifest",
            module.ROUTE_BATCH_SOURCE_NAMES,
        )

    def test_owner_approved_mixed_chapters_bind_all_exact_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            releases = []
            specs = []
            for release_id in ("ac1102_test", "ac1103_test"):
                release_root = root / release_id
                paths = {
                    "video_sha256": release_root / "video" / f"{release_id}.mp4",
                    "subtitle_sha256": (
                        release_root
                        / "subtitles"
                        / f"{release_id}__zh_dialogue.srt"
                    ),
                    "manifest_sha256": (
                        release_root / "manifests" / "chapter_review_manifest.json"
                    ),
                    "qa_sha256": release_root / "qa" / "automated_qa.json",
                    "ready_sha256": release_root / "BATCH_REVIEW_READY.json",
                }
                release = {"release_id": release_id}
                for key, path in paths.items():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"{release_id}:{key}\n", encoding="utf-8")
                    release[key] = module.file_sha256(path)
                releases.append(release)
                specs.append(
                    {
                        "release_id": release_id,
                        "target_bv_key": "mixed",
                        "suggested_part_name": f"part {release_id}",
                        "action": "append",
                    }
                )
            attestation = {
                "schema": "magireco-owner-playback-attestation-v1",
                "attestation_id": (
                    "mixed_composition_4_chapters_owner_playback_20260718"
                ),
                "decisions": {"HUMAN_PLAYBACK_APPROVED": True},
                "releases": releases,
            }
            items = module._owner_approved_mixed_chapter_items(
                attestation=attestation,
                root=root,
                specs=specs,
                plan={"target_bvs": {"mixed": "mixed BV"}},
            )
            self.assertEqual(len(items), 2)
            self.assertTrue(all(row["state"] == "ready_to_upload" for row in items))
            self.assertTrue(
                all(
                    row["human_approval_status"]
                    == "exact_file_owner_playback_approved"
                    for row in items
                )
            )


if __name__ == "__main__":
    unittest.main()
