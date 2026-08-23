import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
import json


MODULE_PATH = Path(__file__).resolve().parent / "tools" / "frida_runtime_probe" / "build_native416_exhaustive_review_checkpoint.py"
SPEC = importlib.util.spec_from_file_location("native416_review", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Native416ReviewCheckpointTests(unittest.TestCase):
    def test_current_checkpoint_cardinality(self):
        self.assertEqual(MODULE.EXPECTED_CONTENT_GROUP_COUNT, 19)
        self.assertEqual(MODULE.EXPECTED_EDITION_FILE_COUNT, 45)

    def test_safe_title(self):
        self.assertEqual(MODULE.safe_title('a:b/c* d'), "a_b_c_ d")

    def test_v99_title_contract(self):
        path = Path("ac7101_示例全视频合集_严格无BGM__zh.mp4")
        self.assertEqual(MODULE.title_from_v99_path(path, "ac7101", "zh"), "示例全视频合集")

    def test_material_has_no_language_suffix(self):
        row = {"group_number": 12, "family": "ac7118", "title": "全角色资料动画穷尽合集", "edition": "material", "content_type": "material"}
        self.assertEqual(str(MODULE.relative_target(row)), str(Path("MATERIAL") / "G012_ac7118_全角色资料动画穷尽合集.mp4"))

    def test_hardlink_samefile(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bin"
            target = Path(directory) / "target.bin"
            source.write_bytes(b"content")
            os.link(source, target)
            self.assertTrue(os.path.samefile(source, target))

    def test_ac0908_manifest_becomes_one_three_edition_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = []
            for edition in ("none", "ja", "zh"):
                outputs.append(
                    {
                        "edition": edition,
                        "path": str(root / f"sample__{edition}.mp4"),
                        "human_status": "HUMAN_PLAYBACK_REQUIRED",
                        "automatic_qa": {"media": True},
                    }
                )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "ac0908_exhaustive_authoritative_longform_v2",
                        "status": "AUTOMATED_QA_PASS_HUMAN_PLAYBACK_REQUIRED",
                        "canonical_presentation_count": 14,
                        "event_container_count": 17,
                        "frames": 3915,
                        "outputs": outputs,
                    }
                ),
                encoding="utf-8",
            )
            rows = MODULE.rows_from_ac0908_manifest(manifest, 14)
        self.assertEqual({row["edition"] for row in rows}, {"none", "ja", "zh"})
        self.assertEqual({row["group_number"] for row in rows}, {14})
        self.assertEqual(sum(row["primary"] for row in rows), 1)

    def test_ac1102_verification_becomes_one_three_edition_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = []
            for edition in ("none", "ja", "zh"):
                media.append(
                    {
                        "edition": edition,
                        "path": str(root / f"sample__{edition}.mp4"),
                        "sha256": edition.upper().ljust(64, "A")[:64],
                        "frame_count": 4091,
                    }
                )
            verification = root / "verification.json"
            verification.write_text(
                json.dumps(
                    {
                        "schema": (
                            "magireco-ac1102-exhaustive-production-verification-v1"
                        ),
                        "status": (
                            "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
                        ),
                        "content_group_count": 1,
                        "edition_file_count": 3,
                        "ordered_complete_event_presentations": 15,
                        "exact_duplicate_complete_presentation_count": 0,
                        "dirinfo_route_coverage": "31/31",
                        "native_416x232_only": True,
                        "strict_no_bgm": True,
                        "blocked_p16_p17_p18_leak_count": 0,
                        "media": media,
                    }
                ),
                encoding="utf-8",
            )
            rows = MODULE.rows_from_ac1102_verification(verification, 15)
        self.assertEqual({row["edition"] for row in rows}, {"none", "ja", "zh"})
        self.assertEqual({row["group_number"] for row in rows}, {15})
        self.assertEqual(sum(row["primary"] for row in rows), 1)
        self.assertTrue(all(row["expected_frames"] == 4091 for row in rows))

    def test_ac1103_verification_becomes_one_group_and_short_clip_is_chapter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = [
                {
                    "edition": edition,
                    "path": str(root / f"sample__{edition}.mp4"),
                    "sha256": edition.upper().ljust(64, "B")[:64],
                    "frame_count": 3114,
                }
                for edition in ("none", "ja", "zh")
            ]
            verification = root / "verification.json"
            verification.write_text(
                json.dumps(
                    {
                        "schema": "magireco-ac1103-exhaustive-production-verification-v1",
                        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                        "content_group_count": 1,
                        "edition_file_count": 3,
                        "ordered_complete_event_presentations": 13,
                        "exact_duplicate_complete_presentation_count": 0,
                        "dirinfo_route_coverage": "31/31",
                        "legacy_ac1103_013_18s_standalone_role": "chapter_evidence_only",
                        "native_416x232_only": True,
                        "strict_no_bgm": True,
                        "blocked_p16_p17_p18_leak_count": 0,
                        "media": media,
                    }
                ),
                encoding="utf-8",
            )
            rows = MODULE.rows_from_ac1103_verification(verification, 16)
        self.assertEqual({row["edition"] for row in rows}, {"none", "ja", "zh"})
        self.assertEqual({row["group_number"] for row in rows}, {16})
        self.assertEqual(sum(row["primary"] for row in rows), 1)
        self.assertTrue(all(row["expected_frames"] == 3114 for row in rows))

    def test_ac1104_verification_becomes_one_complete_longform_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = [
                {
                    "edition": edition,
                    "path": str(root / f"sample__{edition}.mp4"),
                    "sha256": edition.upper().ljust(64, "C")[:64],
                    "frame_count": 4221,
                }
                for edition in ("none", "ja", "zh")
            ]
            verification = root / "verification.json"
            verification.write_text(
                json.dumps(
                    {
                        "schema": "magireco-ac1104-exhaustive-production-verification-v1",
                        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                        "content_group_count": 1,
                        "edition_file_count": 3,
                        "ordered_complete_event_presentations": 17,
                        "exact_duplicate_complete_presentation_count": 0,
                        "dirinfo_route_coverage": "15/15",
                        "native_416x232_only": True,
                        "strict_no_bgm": True,
                        "blocked_p16_p17_p18_leak_count": 0,
                        "media": media,
                    }
                ),
                encoding="utf-8",
            )
            rows = MODULE.rows_from_ac1104_verification(verification, 17)
        self.assertEqual({row["edition"] for row in rows}, {"none", "ja", "zh"})
        self.assertEqual({row["group_number"] for row in rows}, {17})
        self.assertEqual(sum(row["primary"] for row in rows), 1)
        self.assertTrue(all(row["expected_frames"] == 4221 for row in rows))

    def test_ac1101_verification_becomes_one_complete_longform_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = [
                {
                    "edition": edition,
                    "path": str(root / f"sample__{edition}.mp4"),
                    "sha256": edition.upper().ljust(64, "D")[:64],
                    "frame_count": 2851,
                }
                for edition in ("none", "ja", "zh")
            ]
            verification = root / "verification.json"
            verification.write_text(
                json.dumps(
                    {
                        "schema": "magireco-ac1101-exhaustive-production-verification-v1",
                        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                        "content_group_count": 1,
                        "edition_file_count": 3,
                        "ordered_complete_event_presentations": 13,
                        "exact_duplicate_complete_presentation_count": 0,
                        "dirinfo_route_coverage": "31/31",
                        "native_416x232_only": True,
                        "strict_no_bgm": True,
                        "blocked_p16_p17_p18_leak_count": 0,
                        "media": media,
                    }
                ),
                encoding="utf-8",
            )
            rows = MODULE.rows_from_ac1101_verification(verification, 18)
        self.assertEqual({row["edition"] for row in rows}, {"none", "ja", "zh"})
        self.assertEqual({row["group_number"] for row in rows}, {18})
        self.assertEqual(sum(row["primary"] for row in rows), 1)
        self.assertTrue(all(row["expected_frames"] == 2851 for row in rows))

    def test_ac7206_verification_becomes_one_complete_story_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = [
                {
                    "edition": edition,
                    "path": str(root / f"sample__{edition}.mp4"),
                    "sha256": edition.upper().ljust(64, "E")[:64],
                    "frame_count": 1620,
                }
                for edition in ("none", "ja", "zh")
            ]
            verification = root / "verification.json"
            verification.write_text(
                json.dumps(
                    {
                        "schema": "magireco-ac7206-exhaustive-production-verification-v1",
                        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                        "content_group_count": 1,
                        "edition_file_count": 3,
                        "ordered_complete_event_presentations": 14,
                        "exact_duplicate_complete_presentation_count": 0,
                        "distinct_visual_projection_count": 8,
                        "intentional_visual_reuse_pair_count": 6,
                        "dirinfo_route_coverage": "40/40",
                        "unique_route_event_sequences": 20,
                        "gameplay_015_story_leak_count": 0,
                        "gameplay_015_status": "SEPARATE_BLOCKED_GAMEPLAY_COMPOSITION",
                        "native_416x232_only": True,
                        "strict_no_bgm": True,
                        "blocked_p16_p17_p18_leak_count": 0,
                        "media": media,
                    }
                ),
                encoding="utf-8",
            )
            rows = MODULE.rows_from_ac7206_verification(verification, 19)
        self.assertEqual({row["edition"] for row in rows}, {"none", "ja", "zh"})
        self.assertEqual({row["group_number"] for row in rows}, {19})
        self.assertEqual(sum(row["primary"] for row in rows), 1)
        self.assertTrue(all(row["expected_frames"] == 1620 for row in rows))


if __name__ == "__main__":
    unittest.main()
