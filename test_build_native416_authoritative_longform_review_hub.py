import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.frida_runtime_probe import (
    build_native416_authoritative_longform_review_hub as hub,
)


def media_probe(frame_count=300):
    return {
        "duration_seconds": 10.0,
        "frame_count": frame_count,
        "width": 416,
        "height": 232,
        "frame_rate": "30/1",
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "probe_sha256": "A" * 64,
    }


class Native416ReviewHubTests(unittest.TestCase):
    def make_plan(self, root: Path, *, family="ac1101"):
        media = []
        for edition in hub.EDITIONS:
            source = root / f"{family}__{edition}.mp4"
            source.write_bytes((edition * 20).encode("ascii"))
            media.append(
                {
                    "edition": edition,
                    "path": str(source),
                    "sha256": hub.file_sha256(source),
                    **media_probe(),
                }
            )
        evidence = root / "PRODUCTION_VERIFICATION.json"
        evidence.write_text(
            json.dumps(
                {
                    "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                    "media": media,
                }
            ),
            encoding="utf-8",
        )
        hub_root = root / "hub"
        return {
            "schema": hub.SCHEMA,
            "release_id": "authority_test_v1",
            "hub_root": str(hub_root),
            "expected_previous_current_target": str(root / "previous"),
            "expected_group_count": 1,
            "expected_edition_file_count": 3,
            "groups": [
                {
                    "review_group_id": f"{family}_exhaustive",
                    "family": family,
                    "title": f"测试完整合集_{family}",
                    "content_type": "story",
                    "event_container_count": 5,
                    "unique_complete_presentation_count": 4,
                    "evidence": {
                        "kind": "production_verification_media",
                        "path": str(evidence),
                        "sha256": hub.file_sha256(evidence),
                    },
                    "media": media,
                }
            ],
        }

    def test_safe_filename_and_forbidden_title_characters(self):
        self.assertEqual(hub.safe_filename("完整合集_ac1101", "zh"), "完整合集_ac1101__zh.mp4")
        with self.assertRaises(hub.ReviewHubError):
            hub.safe_filename("bad/name_ac1101", "zh")

    def test_media_contract_rejects_non_native_canvas(self):
        expected = media_probe()
        actual = dict(expected, width=512)
        with self.assertRaisesRegex(hub.ReviewHubError, "width"):
            hub.validate_media_contract(expected, actual, "fixture")

    def test_plan_rejects_quarantined_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.make_plan(Path(tmp), family="ac6003")
            with self.assertRaisesRegex(hub.ReviewHubError, "quarantined"):
                hub.validate_plan(plan)

    @mock.patch.object(hub, "probe_media", side_effect=lambda *_args, **_kwargs: media_probe())
    def test_dry_run_validates_without_creating_hub(self, _probe):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.make_plan(root)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            result = hub.build(plan_path, dry_run=True, publish_current_link=False)
            self.assertEqual(result["status"], "PASS_DRY_RUN")
            self.assertFalse(Path(plan["hub_root"]).exists())

    @mock.patch.object(hub, "probe_media", side_effect=lambda *_args, **_kwargs: media_probe())
    def test_build_publishes_three_hardlinks_and_metadata(self, _probe):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.make_plan(root)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            result = hub.build(plan_path, dry_run=False, publish_current_link=False)
            release = Path(result["release_root"])
            self.assertTrue((release / "READY").is_file())
            index = json.loads((release / "HUMAN_REVIEW_INDEX.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index), 3)
            for row in index:
                self.assertTrue(os.path.samefile(row["source_file"], row["review_file"]))
            record = json.loads((release / "VERIFICATION_RECORD.json").read_text(encoding="utf-8"))
            self.assertEqual(record["source_target_samefile_count"], 3)
            self.assertEqual(record["p16_p17_p18_leak_count"], 0)


if __name__ == "__main__":
    unittest.main()
