import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.frida_runtime_probe.build_manual_review_hub import (
    apply_inventory_deltas,
    build,
    file_sha256,
    probe_media,
    quarantine_searchable_identity,
)


class ManualReviewHubBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir()
        self.source = self.source_root / "source.mp4"
        self.source.write_bytes(b"synthetic-mp4-fixture")
        self.sha = file_sha256(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_quarantine_identity_ignores_unrelated_absolute_path_ancestors(self):
        item = {
            "inventory_item_id": "I_READY",
            "family": "ac7002",
            "title_zh": "夜空魔女全视频合集",
            "source_path": str(
                Path("C:/unrelated-p18-workspace/source/ac7002_ready.mp4")
            ),
        }
        self.assertNotIn("p18", quarantine_searchable_identity(item))
        item["source_path"] = str(Path("C:/workspace/source/ac6004_p17.mp4"))
        searchable = quarantine_searchable_identity(item)
        self.assertIn("ac6004", searchable)
        self.assertIn("p17", searchable)

    @staticmethod
    def fake_probe(path: Path, _ffprobe: str):
        return {
            "duration_sec": 1.0,
            "width": 416,
            "height": 232,
            "frame_rate": "30/1",
            "video_codec": "h264",
            "audio_codec": None,
            "audio_sample_rate": None,
            "audio_channels": None,
            "probe_sha256": "A" * 64,
        }

    def item(self, item_id, disposition, **overrides):
        value = {
            "inventory_item_id": item_id,
            "review_group_id": "G1",
            "timeline_order": 1,
            "event_ids": ["ac0001_001"],
            "source_ids": ["ac0001"],
            "family": "ac0001",
            "series": "sample",
            "route_id": "",
            "route_kind": "standalone",
            "content_type": "material",
            "edition": "material",
            "title_zh": "测试素材",
            "source_path": str(self.source),
            "source_root": str(self.source_root),
            "source_root_generation": "fixture",
            "sha256": self.sha,
            "actual_sha256": self.sha,
            "size": self.source.stat().st_size,
            "duration_sec": 1.0,
            "width": 416,
            "height": 232,
            "frame_rate": "30/1",
            "video_codec": "h264",
            "audio_codec": None,
            "audio_sample_rate": 0,
            "audio_channels": 0,
            "language_semantics": {"dialogue_language": None, "subtitle_language": None},
            "audio_profile": "silent",
            "auto_qa_status": "AUTO_QA_PASS",
            "evidence_status": "hash_bound",
            "evidence_paths": [],
            "human_status": "human_playback_required",
            "review_disposition": disposition,
            "not_in_primary_review_reason": "" if disposition == "REVIEW_READY" else "fixture_boundary",
            "quarantine_flags": [],
            "superseded": False,
            "already_uploaded": False,
            "owner_approved": False,
            "owner_approval_source": "",
            "canonical_sha256": self.sha,
            "canonical_review_item_id": item_id,
            "is_alias": False,
            "alias_reason": "",
            "source_identity_alias": False,
            "source_identity_canonical_item_id": "",
            "source_identity_reason": "",
            "target_bv": "",
            "proposed_hub_relative_path": "",
            "proposed_review_filename": "",
            "physical_link_policy": "hardlink",
            "media_open_status": "open_ok",
            "probe_sha256": "B" * 64,
            "source_manifest": "fixture.json",
            "source_manifest_sha256": "C" * 64,
        }
        value.update(overrides)
        return value

    def write_fixture(self, ready_overrides=None, mapping_overrides=None):
        ready = self.item("I_READY", "REVIEW_READY", **(ready_overrides or {}))
        needs = self.item("I_NEEDS", "NEEDS_DECISION")
        excluded = self.item("I_EXCLUDED", "EXCLUDED_REFERENCE")
        alias = self.item(
            "I_ALIAS",
            "EXCLUDED_REFERENCE",
            source_identity_alias=True,
            source_identity_canonical_item_id="I_READY",
            source_identity_reason="review canonical once",
            canonical_review_item_id="I_READY",
        )
        inventory = {
            "schema": "magireco-authoritative-production-inventory-v1",
            "summary": {},
            "items": [ready, needs, excluded, alias],
        }
        inventory_path = self.root / "inventory.json"
        inventory_path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
        mapping = {
            "inventory_item_id": "I_READY",
            "source_path": str(self.source),
            "sha256": self.sha,
            "proposed_hub_relative_path": "REVIEW_READY/material/sample/material/R0001_测试素材_ac0001.mp4",
        }
        mapping.update(mapping_overrides or {})
        mapping_path = self.root / "mapping.csv"
        with mapping_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(mapping))
            writer.writeheader()
            writer.writerow(mapping)
        plan = {
            "schema": "magireco-manual-review-hub-plan-v1",
            "release_id": "fixture_release",
            "output_root": str(self.root / "hub"),
            "allowed_source_root": str(self.root),
            "inputs": {
                "inventory": {"path": str(inventory_path), "sha256": file_sha256(inventory_path)},
                "mapping": {"path": str(mapping_path), "sha256": file_sha256(mapping_path)},
            },
            "expected_counts": {
                "inventory_items": 4,
                "review_ready": 1,
                "needs_decision": 1,
                "excluded_reference": 2,
                "mapping_rows": 1,
            },
        }
        plan_path = self.root / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return plan_path, inventory_path, mapping_path

    def test_builds_single_hardlink_and_full_index(self):
        plan, _, _ = self.write_fixture()
        result = build(plan, probe_func=self.fake_probe)
        self.assertEqual(result["status"], "PASS")
        release = Path(result["release_path"])
        media = release / "REVIEW_READY/material/sample/material/R0001_测试素材_ac0001.mp4"
        self.assertTrue(os.path.samefile(self.source, media))
        index = json.loads((release / "review_index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["summary"]["inventory_items"], 4)
        self.assertEqual(index["summary"]["canonical_review_files"], 1)
        self.assertFalse(index["summary"]["auto_qa_is_human_approval"])
        rows = {row["inventory_item_id"]: row for row in index["items"]}
        self.assertEqual(rows["I_READY"]["human_status"], "human_playback_required")
        self.assertEqual(rows["I_ALIAS"]["canonical_review_absolute_path"], str(media))
        self.assertFalse(rows["I_NEEDS"]["review_absolute_path"])
        self.assertTrue((release / "READY").is_file())
        self.assertTrue((release / "_rollback/ROLLBACK.ps1").is_file())
        current = json.loads((self.root / "hub/CURRENT.json").read_text(encoding="utf-8"))
        self.assertEqual(current["release_id"], "fixture_release")

    def test_dry_run_writes_nothing(self):
        plan, _, _ = self.write_fixture()
        probe = mock.Mock(side_effect=self.fake_probe)
        result = build(plan, dry_run=True, probe_func=probe)
        self.assertEqual(result["status"], "DRY_RUN_PASS")
        self.assertEqual(probe.call_count, 4)
        self.assertFalse((self.root / "hub").exists())

    def test_builds_flat_language_first_material_lane(self):
        plan, _, _ = self.write_fixture()
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["layout_mode"] = "flat_language_v2"
        plan.write_text(json.dumps(payload), encoding="utf-8")
        result = build(plan, probe_func=self.fake_probe)
        release = Path(result["release_path"])
        media = release / "REVIEW_READY_FLAT/MATERIAL/R0001_测试素材_ac0001.mp4"
        self.assertTrue(os.path.samefile(self.source, media))
        self.assertFalse((release / "REVIEW_READY_FLAT/MATERIAL/material").exists())
        self.assertEqual(result["layout_mode"], "flat_language_v2")
        self.assertEqual(result["review_root"], str(release / "REVIEW_READY_FLAT"))
        verification = json.loads(
            (release / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
        )
        self.assertTrue(verification["checks"]["flat_language_first_layout"])
        self.assertTrue(
            verification["checks"]["flat_paths_have_no_family_subdirectories"]
        )

    def test_builds_flat_zh_route_without_family_subdirectory(self):
        plan, _, mapping_path = self.write_fixture(
            ready_overrides={
                "content_type": "story_route",
                "edition": "zh",
                "audio_profile": "no_bgm",
            },
            mapping_overrides={
                "proposed_hub_relative_path": (
                    "REVIEW_READY/routes/ac0001/zh/"
                    "R0001_测试路线_ac0001_001__zh.mp4"
                )
            },
        )
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["layout_mode"] = "flat_language_v2"
        payload["inputs"]["mapping"]["sha256"] = file_sha256(mapping_path)
        plan.write_text(json.dumps(payload), encoding="utf-8")
        result = build(plan, probe_func=self.fake_probe)
        release = Path(result["release_path"])
        media = (
            release
            / "REVIEW_READY_FLAT/ZH/routes/R0001_测试路线_ac0001_001__zh.mp4"
        )
        self.assertTrue(os.path.samefile(self.source, media))
        self.assertEqual(len(media.relative_to(release).parts), 4)

    def test_flat_layout_rejects_filename_without_identity(self):
        plan, _, mapping_path = self.write_fixture(
            mapping_overrides={
                "proposed_hub_relative_path": (
                    "REVIEW_READY/material/sample/material/R0001_测试素材.mp4"
                )
            }
        )
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["layout_mode"] = "flat_language_v2"
        payload["inputs"]["mapping"]["sha256"] = file_sha256(mapping_path)
        plan.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lacks family/event/route identity"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_non_ready_source_hash_drift(self):
        plan, inventory_path, _ = self.write_fixture()
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
        needs = next(
            item for item in payload["items"] if item["inventory_item_id"] == "I_NEEDS"
        )
        separate = self.source_root / "needs.mp4"
        separate.write_bytes(b"needs-decision-fixture")
        needs["source_path"] = str(separate)
        needs["source_root"] = str(self.source_root)
        needs["size"] = separate.stat().st_size
        needs["sha256"] = "D" * 64
        needs["actual_sha256"] = "D" * 64
        needs["canonical_sha256"] = "D" * 64
        inventory_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        plan_payload = json.loads(plan.read_text(encoding="utf-8"))
        plan_payload["inputs"]["inventory"]["sha256"] = file_sha256(inventory_path)
        plan.write_text(json.dumps(plan_payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_non_ready_mapping(self):
        plan, inventory_path, mapping_path = self.write_fixture(
            ready_overrides={"review_disposition": "NEEDS_DECISION"}
        )
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["inputs"]["inventory"]["sha256"] = file_sha256(inventory_path)
        payload["expected_counts"].update(review_ready=0, needs_decision=2)
        plan.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non-ready"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_path_traversal(self):
        plan, _, _ = self.write_fixture(
            mapping_overrides={"proposed_hub_relative_path": "REVIEW_READY/material/../escape.mp4"}
        )
        with self.assertRaisesRegex(ValueError, "unsafe hub path"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_language_suffix_for_material(self):
        plan, _, _ = self.write_fixture(
            mapping_overrides={
                "proposed_hub_relative_path": "REVIEW_READY/material/sample/material/R0001_测试素材__none.mp4"
            }
        )
        with self.assertRaisesRegex(ValueError, "language suffix"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_quarantined_family(self):
        plan, _, _ = self.write_fixture(ready_overrides={"family": "ac6003"})
        with self.assertRaisesRegex(ValueError, "quarantined product"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_source_hash_drift(self):
        plan, _, _ = self.write_fixture()
        self.source.write_bytes(b"X" * self.source.stat().st_size)
        with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_existing_release(self):
        plan, _, _ = self.write_fixture()
        release = self.root / "hub/releases/fixture_release"
        release.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "already exists"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_rejects_unresolved_with_bgm(self):
        plan, _, _ = self.write_fixture(ready_overrides={"audio_profile": "with_bgm"})
        with self.assertRaisesRegex(ValueError, "unclosed audio profile"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_hash_bound_sound_bus_audit_demotes_ready_without_erasing_approval(self):
        plan, _, _ = self.write_fixture(ready_overrides={"owner_approved": True})
        impact = {
            "schema": "magireco-ida-sound-volume-bus-product-impact-delta-v1",
            "counts": {"items": 1, "review_ready_withdrawals": 1},
            "items": [
                {
                    "inventory_item_id": "I_READY",
                    "source_path": str(self.source),
                    "sha256": self.sha,
                    "source_review_disposition": "REVIEW_READY",
                    "effective_review_disposition": "NEEDS_DECISION",
                    "owner_approval_preserved": True,
                    "action": "withdraw_from_strict_no_bgm_review_ready",
                    "reason": "fixture BGM bus request",
                    "bgm_bus_sound_ids": [553],
                    "bgm_bus_requests": ["228"],
                }
            ],
        }
        risk = {
            "schema": "magireco-ready-event-bgm-volume-bus-risk-v1",
            "items": [dict(impact["items"][0])],
        }
        v68 = {
            "schema": "magireco-v68-ac0911-no-bgm-semantic-withdrawal-v1",
            "items": [dict(impact["items"][0])],
        }
        verification = {
            "schema": "magireco-ida-sound-volume-bus-product-impact-verification-v1",
            "status": "PASS",
        }
        bindings = {}
        for name, payload in (
            ("product_impact_delta", impact),
            ("ready_risk", risk),
            ("v68_withdrawal", v68),
            ("verification_record", verification),
        ):
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            bindings[name] = {"path": str(path), "sha256": file_sha256(path)}
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["inputs"]["sound_bus_audit"] = bindings
        payload["expected_counts"] = {
            "inventory_items": 4,
            "review_ready": 0,
            "needs_decision": 2,
            "excluded_reference": 2,
            "mapping_rows": 0,
        }
        plan.write_text(json.dumps(payload), encoding="utf-8")
        result = build(plan, probe_func=self.fake_probe)
        release = Path(result["release_path"])
        index = json.loads((release / "review_index.json").read_text(encoding="utf-8"))
        row = next(item for item in index["items"] if item["inventory_item_id"] == "I_READY")
        self.assertEqual(row["review_disposition"], "NEEDS_DECISION")
        self.assertEqual(row["pre_sound_bus_review_disposition"], "REVIEW_READY")
        self.assertTrue(row["owner_approved"])
        self.assertEqual(row["bgm_bus_sound_ids"], [553])
        self.assertFalse(row["review_absolute_path"])
        verification_output = json.loads(
            (release / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
        )
        self.assertTrue(
            verification_output["checks"]["sound_bus_withdrawals_not_linked"]
        )

    def test_hash_bound_delta_supersedes_reference_and_adds_replacement(self):
        plan, inventory_path, _ = self.write_fixture()
        base_inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        old = next(
            item
            for item in base_inventory["items"]
            if item["inventory_item_id"] == "I_READY"
        )
        old["review_disposition"] = "NEEDS_DECISION"
        old["not_in_primary_review_reason"] = "fixture_pending_before_repair"
        old["route_id"] = "0"
        # Model the production contract where path/hash plus semantic identity
        # selects one row even when this synthetic fixture reuses media bytes.
        for item in base_inventory["items"]:
            if item["inventory_item_id"] != "I_READY":
                item["family"] = "ac0002"
        inventory_path.write_text(
            json.dumps(base_inventory, ensure_ascii=False), encoding="utf-8"
        )
        replacement_source = self.source_root / "replacement.mp4"
        replacement_source.write_bytes(b"replacement-synthetic-mp4-fixture")
        replacement_sha = file_sha256(replacement_source)
        replacement = self.item(
            "I_REPLACEMENT",
            "REVIEW_READY",
            source_path=str(replacement_source),
            sha256=replacement_sha,
            actual_sha256=replacement_sha,
            canonical_sha256=replacement_sha,
            canonical_review_item_id="I_REPLACEMENT",
            size=replacement_source.stat().st_size,
            proposed_hub_relative_path=(
                "REVIEW_READY/material/sample/material/"
                "R0002_替换素材_ac0001.mp4"
            ),
            proposed_review_filename="R0002_替换素材_ac0001.mp4",
            route_id="dirinfo-row-000",
        )
        delta = {
            "schema": "magireco-authoritative-production-inventory-delta-v2",
            "base_inventory": {
                "path": str(inventory_path),
                "sha256": file_sha256(inventory_path),
            },
            "items": [replacement],
        }
        delta_path = self.root / "delta.json"
        delta_path.write_text(json.dumps(delta, ensure_ascii=False), encoding="utf-8")
        supersession = {
            "schema": "magireco-production-inventory-supersession-delta-v1",
            "items": [
                {
                    "family": "ac0001",
                    "route_id": "dirinfo-row-000",
                    "edition": "material",
                    "superseded_source_path": str(self.source),
                    "superseded_sha256": self.sha,
                    "replacement_inventory_item_id": "I_REPLACEMENT",
                    "reason": "fixture replacement",
                }
            ],
        }
        supersession_path = self.root / "supersession.json"
        supersession_path.write_text(
            json.dumps(supersession, ensure_ascii=False), encoding="utf-8"
        )
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["inputs"]["inventory"]["sha256"] = file_sha256(inventory_path)
        payload["inputs"]["deltas"] = [
            {
                "inventory_delta": {
                    "path": str(delta_path),
                    "sha256": file_sha256(delta_path),
                },
                "supersession_delta": {
                    "path": str(supersession_path),
                    "sha256": file_sha256(supersession_path),
                },
            }
        ]
        payload["expected_counts"] = {
            "inventory_items": 5,
            "review_ready": 1,
            "needs_decision": 2,
            "excluded_reference": 2,
            "mapping_rows": 1,
        }
        plan.write_text(json.dumps(payload), encoding="utf-8")
        result = build(plan, probe_func=self.fake_probe)
        release = Path(result["release_path"])
        replacement_path = (
            release
            / "REVIEW_READY/material/sample/material/"
            "R0002_替换素材_ac0001.mp4"
        )
        self.assertTrue(os.path.samefile(replacement_source, replacement_path))
        index = json.loads((release / "review_index.json").read_text(encoding="utf-8"))
        rows = {row["inventory_item_id"]: row for row in index["items"]}
        self.assertEqual(rows["I_READY"]["review_disposition"], "NEEDS_DECISION")
        self.assertTrue(rows["I_READY"]["superseded"])
        self.assertEqual(
            rows["I_READY"]["superseded_by_inventory_item_id"], "I_REPLACEMENT"
        )
        self.assertFalse(rows["I_READY"]["review_absolute_path"])

    def test_v3_bounded_candidate_preserves_owner_approved_full_product(self):
        old = self.item(
            "I_READY",
            "REVIEW_READY",
            owner_approved=True,
            family="ac0001",
            route_id="full",
        )
        inventory = {
            "schema": "magireco-authoritative-production-inventory-v1",
            "items": [old],
        }
        inventory_path = self.root / "inventory-v3-base.json"
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        inventory_sha = file_sha256(inventory_path)
        prior = {
            "schema": "magireco-authoritative-production-inventory-delta-v2",
            "base_inventory": {"path": str(inventory_path), "sha256": inventory_sha},
            "items": [],
        }
        prior_path = self.root / "prior-delta.json"
        prior_path.write_text(json.dumps(prior), encoding="utf-8")
        prior_supersession_path = self.root / "prior-supersession.json"
        prior_supersession_path.write_text(
            json.dumps(
                {
                    "schema": "magireco-production-inventory-supersession-delta-v1",
                    "items": [],
                }
            ),
            encoding="utf-8",
        )

        candidate_source = self.source_root / "bounded-candidate.mp4"
        candidate_source.write_bytes(b"bounded-candidate-media")
        candidate_sha = file_sha256(candidate_source)
        evidence_path = self.root / "bounded-evidence.json"
        evidence_path.write_text('{"result":"PASS"}\n', encoding="utf-8")
        candidate = self.item(
            "I_BOUNDED",
            "REVIEW_READY",
            source_path=str(candidate_source),
            source_root=str(self.source_root),
            sha256=candidate_sha,
            actual_sha256=candidate_sha,
            canonical_sha256=candidate_sha,
            canonical_review_item_id="I_BOUNDED",
            size=candidate_source.stat().st_size,
            family="ac0001_013",
            series="ac0001",
            route_id="013",
            source_manifest=str(evidence_path),
            source_manifest_sha256=file_sha256(evidence_path),
            evidence_paths=[str(evidence_path)],
            proposed_hub_relative_path=(
                "REVIEW_READY/material/sample/material/R0002_单事件候选_ac0001_013.mp4"
            ),
            proposed_review_filename="R0002_单事件候选_ac0001_013.mp4",
        )
        delta = {
            "schema": "magireco-authoritative-production-inventory-delta-v3",
            "base_inventory": {"path": str(inventory_path), "sha256": inventory_sha},
            "prior_delta": {
                "path": str(prior_path),
                "sha256": file_sha256(prior_path),
            },
            "items": [candidate],
        }
        delta_path = self.root / "delta-v3.json"
        delta_path.write_text(json.dumps(delta), encoding="utf-8")
        supersession_path = self.root / "supersession-v2.json"
        supersession_path.write_text(
            json.dumps(
                {
                    "schema": "magireco-production-inventory-supersession-delta-v2",
                    "items": [
                        {
                            "withdrawn_inventory_item_id": "I_READY",
                            "family": "ac0001",
                            "edition": "material",
                            "withdrawn_source_path": str(self.source),
                            "withdrawn_sha256": self.sha,
                            "owner_playback_approval_preserved": True,
                            "strict_no_bgm_review_ready_withdrawn": True,
                            "replacement_scope": (
                                "bounded_event_candidate_only_not_full_chapter_replacement"
                            ),
                            "replacement_inventory_item_id": "I_BOUNDED",
                            "replacement_sha256": candidate_sha,
                            "reason": "bounded fixture only",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        verification_path = self.root / "delta-v3-verification.json"
        verification_path.write_text(
            json.dumps(
                {
                    "schema": (
                        "magireco-authoritative-production-inventory-delta-verification-v3"
                    ),
                    "result": "PASS",
                    "counts": {"items": 1},
                }
            ),
            encoding="utf-8",
        )
        source_bindings_path = self.root / "delta-v3-source-bindings.json"
        source_bindings_path.write_text(
            json.dumps(
                {
                    "schema": "magireco-inventory-delta-source-bindings-v2",
                    "measured_source_hashes": {
                        str(evidence_path): file_sha256(evidence_path)
                    },
                }
            ),
            encoding="utf-8",
        )
        plan = {
            "inputs": {
                "deltas": [
                    {
                        "inventory_delta": {
                            "path": str(prior_path),
                            "sha256": file_sha256(prior_path),
                        },
                        "supersession_delta": {
                            "path": str(prior_supersession_path),
                            "sha256": file_sha256(prior_supersession_path),
                        },
                    },
                    {
                        "inventory_delta": {
                            "path": str(delta_path),
                            "sha256": file_sha256(delta_path),
                        },
                        "supersession_delta": {
                            "path": str(supersession_path),
                            "sha256": file_sha256(supersession_path),
                        },
                        "verification_record": {
                            "path": str(verification_path),
                            "sha256": file_sha256(verification_path),
                        },
                        "source_bindings": {
                            "path": str(source_bindings_path),
                            "sha256": file_sha256(source_bindings_path),
                        },
                    },
                ]
            }
        }
        items, mapping, bindings = apply_inventory_deltas(
            plan=plan,
            inventory_path=inventory_path,
            inventory_sha256=inventory_sha,
            base_items=[old],
            base_mapping=[
                {
                    "inventory_item_id": "I_READY",
                    "source_path": str(self.source),
                    "sha256": self.sha,
                    "proposed_hub_relative_path": (
                        "REVIEW_READY/material/sample/material/R0001_完整成品_ac0001.mp4"
                    ),
                }
            ],
        )
        rows = {item["inventory_item_id"]: item for item in items}
        self.assertTrue(rows["I_READY"]["owner_approved"])
        self.assertFalse(rows["I_READY"]["superseded"])
        self.assertEqual(
            rows["I_READY"]["bounded_replacement_candidate_inventory_item_id"],
            "I_BOUNDED",
        )
        self.assertEqual({row["inventory_item_id"] for row in mapping}, {"I_READY", "I_BOUNDED"})
        self.assertIn("verification_record", bindings[1])
        self.assertIn("source_bindings", bindings[1])

    def test_authority_audit_must_cover_inventory_and_ready_set_exactly(self):
        plan, inventory_path, _ = self.write_fixture()
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        audit_items = []
        for item in inventory["items"]:
            audit_items.append(
                {
                    "inventory_item_id": item["inventory_item_id"],
                    "source_path": item["source_path"],
                    "sha256": item["sha256"],
                    "effective_review_disposition": item["review_disposition"],
                    "ida_accuracy_category": (
                        "NO_CHILD_LOCAL_RISK"
                        if item["review_disposition"] == "REVIEW_READY"
                        else "CHILD_LOCAL_FAIL_CLOSED"
                    ),
                    "audit_action": "fixture",
                    "rationale": "fixture",
                    "ida_authority_report": "fixture.json",
                    "ida_authority_report_sha256": "D" * 64,
                }
            )
        safe = {
            "schema": "magireco.ida_safe_review_index.v1",
            "items": [
                {
                    "inventory_item_id": "I_READY",
                    "sha256": self.sha,
                }
            ],
        }
        audit = {
            "schema": "magireco.ida_past_product_accuracy_audit.v1",
            "items": audit_items,
        }
        verification = {
            "schema": "magireco.ida_past_product_accuracy_verification.v1",
            "status": "PASS",
        }
        paths = {}
        for name, value in (
            ("safe_review_index", safe),
            ("product_accuracy_audit", audit),
            ("verification_record", verification),
        ):
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = {"path": str(path), "sha256": file_sha256(path)}
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["inputs"]["authority_audit"] = paths
        plan.write_text(json.dumps(payload), encoding="utf-8")
        result = build(plan, dry_run=True, probe_func=self.fake_probe)
        self.assertEqual(result["status"], "DRY_RUN_PASS")

        safe["items"] = []
        safe_path = Path(paths["safe_review_index"]["path"])
        safe_path.write_text(json.dumps(safe), encoding="utf-8")
        payload["inputs"]["authority_audit"]["safe_review_index"][
            "sha256"
        ] = file_sha256(safe_path)
        plan.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not equal REVIEW_READY"):
            build(plan, dry_run=True, probe_func=self.fake_probe)

    def test_ffprobe_json_is_decoded_as_utf8_not_windows_locale(self):
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 416,
                    "height": 232,
                    "r_frame_rate": "30/1",
                    "avg_frame_rate": "3671040/122363",
                    "tags": {"title": "黑江"},
                }
            ],
            "format": {"duration": "1.0"},
        }
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            stderr=b"",
        )
        with mock.patch("subprocess.run", return_value=completed):
            actual = probe_media(self.source)
        self.assertEqual(actual["width"], 416)
        self.assertEqual(actual["frame_rate"], "30/1")
        self.assertEqual(actual["audio_codec"], None)


if __name__ == "__main__":
    unittest.main()
