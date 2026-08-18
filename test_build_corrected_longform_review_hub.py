import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.frida_runtime_probe.build_corrected_longform_review_hub import build


class CorrectedLongformReviewHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"fixture")

    def tearDown(self):
        self.temp.cleanup()

    def row(self, item_id, **overrides):
        row = {
            "inventory_item_id": item_id,
            "title": "测试长片",
            "family": "ac0001",
            "content_type": "clean_story",
            "edition": "zh",
            "duration_sec": "1.0",
            "resolution": "416x232",
            "frame_rate": "30/1",
            "source_absolute_path": str(self.source),
            "review_disposition": "REVIEW_READY",
            "owner_approved": "False",
            "quarantine_flags": "[]",
            "superseded": "False",
            "exclusion_reason": "",
            "sound_bus_audit_action": "",
        }
        row.update(overrides)
        return row

    @staticmethod
    def audit(item_id, action="PRESERVE_CURRENT_METADATA_PENDING_AUDIT"):
        return {"inventory_item_id": item_id, "new_longform_action": action, "reason": "fixture"}

    def write_inputs(self, rows, audits):
        paths = []
        for name, values in (("index.csv", rows), ("audit.csv", audits)):
            path = self.root / name
            fields = []
            for row in values:
                for key in row:
                    if key not in fields:
                        fields.append(key)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(values)
            paths.append(path)
        return paths

    @staticmethod
    def fake_probe(_path, _ffprobe):
        return {
            "duration_sec": 1.0,
            "width": 416,
            "height": 232,
            "frame_rate": "30/1",
            "video_codec": "h264",
            "audio_codec": None,
            "audio_sample_rate": None,
            "audio_channels": None,
        }

    def run_build(self, rows, audits, dry_run=False):
        index, reassessment = self.write_inputs(rows, audits)
        with mock.patch(
            "tools.frida_runtime_probe.build_corrected_longform_review_hub.probe",
            side_effect=self.fake_probe,
        ):
            return build(
                source_index=index,
                reassessment=reassessment,
                output_root=self.root / "hub",
                release_id="fixture_release",
                dry_run=dry_run,
            )

    def test_owner_approved_longfilm_is_hardlinked(self):
        result = self.run_build(
            [self.row("I_APPROVED", owner_approved="True")],
            [self.audit("I_APPROVED")],
        )
        release = Path(result["release_path"])
        media = next((release / "00_APPROVED_CURRENT/ZH/story").glob("*.mp4"))
        self.assertTrue(os.path.samefile(self.source, media))

    def test_unapproved_short_story_is_index_only(self):
        result = self.run_build([self.row("I_SHORT")], [self.audit("I_SHORT")])
        self.assertEqual(result["canonical_hardlinks"], 0)

    def test_material_has_no_none_suffix(self):
        row = self.row(
            "I_MATERIAL", title="白色阶段组件", content_type="material", edition="none"
        )
        result = self.run_build([row], [self.audit("I_MATERIAL")])
        release = Path(result["release_path"])
        media = next((release / "01_TO_REVIEW/MATERIAL").glob("*.mp4"))
        self.assertNotIn("__none", media.name)
        self.assertTrue(os.path.samefile(self.source, media))

    def test_withdrawn_owner_approval_is_index_only(self):
        row = self.row("I_WITHDRAWN", owner_approved="True")
        audit = self.audit("I_WITHDRAWN", "WITHDRAW_FROM_LONGFORM_REVIEW")
        result = self.run_build([row], [audit])
        self.assertEqual(result["approved_current_files"], 0)

    def test_sound_bus_withdrawal_is_index_only(self):
        row = self.row(
            "I_BGM",
            owner_approved="True",
            sound_bus_audit_action="withdraw_from_strict_no_bgm_review_ready",
        )
        result = self.run_build([row], [self.audit("I_BGM")])
        self.assertEqual(result["canonical_hardlinks"], 0)

    def test_dry_run_writes_nothing(self):
        result = self.run_build(
            [self.row("I_APPROVED", owner_approved="True")],
            [self.audit("I_APPROVED")],
            dry_run=True,
        )
        self.assertEqual(result["status"], "DRY_RUN_PASS")
        self.assertFalse((self.root / "hub").exists())
