import sys
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_exhaustive_video_production_ledger as module  # noqa: E402


class BuildExhaustiveVideoProductionLedgerTest(unittest.TestCase):
    def test_nested_hash_bound_ledger_overlays_merge(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            base = root / "base.json"
            middle = root / "middle.json"
            top = root / "top.json"
            base.write_text('{"schema":"x","a":1}\n', encoding="utf-8")
            middle.write_text(
                json.dumps(
                    {
                        "base_plan": {
                            "path": "base.json",
                            "sha256": module.file_sha256(base),
                        },
                        "b": 2,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            top.write_text(
                json.dumps(
                    {
                        "base_plan": {
                            "path": "middle.json",
                            "sha256": module.file_sha256(middle),
                        },
                        "c": 3,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            plan, snapshots = module._load_plan_with_bases(top)
            self.assertEqual((plan["a"], plan["b"], plan["c"]), (1, 2, 3))
            self.assertEqual(len(snapshots), 2)

    def test_hash_bound_ledger_overlay_can_append_versioned_roots(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            base = root / "base.json"
            top = root / "top.json"
            base.write_text(
                json.dumps(
                    {
                        "schema": "x",
                        "current_material_roots": [{"label": "old"}],
                        "material_component_coverage_bundles": [
                            {"path": "old"}
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            top.write_text(
                json.dumps(
                    {
                        "base_plan": {
                            "path": "base.json",
                            "sha256": module.file_sha256(base),
                        },
                        "append_current_material_roots": [
                            {"label": "new"}
                        ],
                        "append_material_component_coverage_bundles": [
                            {"path": "new"}
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            plan, _snapshots = module._load_plan_with_bases(top)
            self.assertEqual(
                [row["label"] for row in plan["current_material_roots"]],
                ["old", "new"],
            )
            self.assertEqual(
                [
                    row["path"]
                    for row in plan["material_component_coverage_bundles"]
                ],
                ["old", "new"],
            )

    def test_owner_approved_legacy_product_does_not_clear_event_risk(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            release_id = "ac1103_test"
            release_root = root / "products" / release_id
            video = release_root / "video" / f"{release_id}.mp4"
            subtitle = (
                release_root / "subtitles" / f"{release_id}__zh_dialogue.srt"
            )
            manifest = (
                release_root / "manifests" / "chapter_review_manifest.json"
            )
            qa = release_root / "qa" / "automated_qa.json"
            ready = release_root / "BATCH_REVIEW_READY.json"
            for path in (video, subtitle, manifest, qa, ready):
                path.parent.mkdir(parents=True, exist_ok=True)
            video.write_text("video\n", encoding="utf-8")
            subtitle.write_text("subtitle\n", encoding="utf-8")
            manifest.write_text(
                json.dumps(
                    {
                        "release_id": release_id,
                        "ordered_events": ["ac1103_013"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            qa.write_text("{}\n", encoding="utf-8")
            ready.write_text("{}\n", encoding="utf-8")
            attestation = root / "attestation.json"
            attestation.write_text(
                json.dumps(
                    {
                        "schema": "magireco-owner-playback-attestation-v1",
                        "attestation_id": (
                            "mixed_composition_4_chapters_owner_playback_20260718"
                        ),
                        "decisions": {"HUMAN_PLAYBACK_APPROVED": True},
                        "releases": [
                            {
                                "release_id": release_id,
                                "video_sha256": module.file_sha256(video),
                                "subtitle_sha256": module.file_sha256(subtitle),
                                "manifest_sha256": module.file_sha256(manifest),
                                "qa_sha256": module.file_sha256(qa),
                                "ready_sha256": module.file_sha256(ready),
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            index, events, snapshots = module._owner_approved_legacy_products(
                raw={
                    "attestation": {
                        "path": str(attestation),
                        "sha256": module.file_sha256(attestation),
                    },
                    "root": str(root / "products"),
                    "release_ids": [release_id],
                },
                plan_dir=root,
            )
            self.assertEqual(events, {"ac1103_013"})
            self.assertEqual(index[0]["human_playback_status"], (
                "exact_file_owner_playback_approved"
            ))
            self.assertIn("not generalized", index[0]["ledger_effect"])
            self.assertEqual(len(snapshots), 6)

    def test_manifest_event_extraction_ignores_source_snapshots(self) -> None:
        value = {
            "ordered_events": ["ac0908_001", "ac0908_002"],
            "routes": [
                {
                    "render_event_sequence": ["ac0908_008"],
                    "timeline": [{"event": "ac0908_009"}],
                }
            ],
            "source_snapshots": [{"label": "ac9999_999"}],
        }
        self.assertEqual(
            module._events_from_manifest(value),
            {"ac0908_001", "ac0908_002", "ac0908_008", "ac0908_009"},
        )

    def test_manifest_semantics_ignore_excluded_routes(self) -> None:
        value = {
            "routes": [
                {
                    "dirinfo_kind": 201,
                    "dirinfo_row": 0,
                    "ordered_events": ["ac7210_001", "ac7210_004"],
                }
            ],
            "excluded_dirinfo_rows": [
                {
                    "dirinfo_kind": 201,
                    "dirinfo_row": 4,
                    "ordered_events": ["ac7210_007", "ac7210_008"],
                }
            ],
        }
        self.assertEqual(
            module._events_from_manifest(value),
            {"ac7210_001", "ac7210_004"},
        )
        self.assertEqual(
            module._produced_dirinfo_rows(value, default_kind=201),
            {(201, 0)},
        )

    def test_produced_dirinfo_rows_accepts_singular_source_row(self) -> None:
        value = {
            "family": "ac4902",
            "routes": [
                {
                    "dirinfo_source_row": {
                        "row_index": 14,
                        "normalized_event_sequence": [
                            "ac4902_001",
                            "ac4902_005",
                            "ac4902_006",
                        ],
                    }
                }
            ],
        }
        self.assertEqual(
            module._produced_dirinfo_rows(value, default_kind=113),
            {(113, 14)},
        )

    def test_child_local_timing_requires_runtime_source(self) -> None:
        manifest = {
            "audio": [
                {
                    "source": "z2d_req_sound",
                    "evidence": module.UNSAFE_CHILD_CONFIDENCE,
                }
            ],
            "runtime_event_manifest_sources": None,
        }
        self.assertTrue(module._child_local_timing_risk(manifest))
        manifest["runtime_event_manifest_sources"] = [{"path": "event_manifest.json"}]
        self.assertFalse(module._child_local_timing_risk(manifest))

    def test_hard_quarantine_overrides_produced_event(self) -> None:
        disposition = module._classify_production_event(
            event="ac6004_006",
            row={"ready": "yes", "errors": ""},
            audience_classification="native_full_frame_only",
            produced_events={"ac6004_006"},
            material_events=set(),
            timing_risk=False,
            quarantines={
                "ac6004": {
                    "part": "P17",
                    "blocker": "human_playback_failed",
                }
            },
        )
        self.assertEqual(
            disposition,
            ("blocked", "quarantined", "human_playback_failed"),
        )

    def test_component_event_is_routed_to_effect_collection(self) -> None:
        disposition = module._classify_audience_event(
            row={
                "event_name": "ac8040_001",
                "classification": "component_only",
            },
            production={},
            produced_events=set(),
            material_events=set(),
            quarantines={},
        )
        self.assertEqual(
            disposition,
            ("gameplay_effect_collection", "planned_unproduced", ""),
        )

    def test_material_event_is_not_left_as_planned_unproduced(self) -> None:
        disposition = module._classify_audience_event(
            row={
                "event_name": "ac0906_001",
                "classification": "component_only",
            },
            production={},
            produced_events=set(),
            material_events={"ac0906_001"},
            quarantines={},
        )
        self.assertEqual(
            disposition,
            (
                "material_collection",
                "produced_review_only_material_collection",
                "",
            ),
        )

    def test_split_component_bundle_requires_current_catalog_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            catalog416 = root / "catalog416.json"
            catalog512 = root / "catalog512.json"
            catalog416.write_text('{"catalog":"416"}\n', encoding="utf-8")
            catalog512.write_text('{"catalog":"512"}\n', encoding="utf-8")
            bundle = root / "bundle.json"
            bundle.write_text(
                json.dumps(
                    {
                        "schema": (
                            "magireco-material-component-coverage-audit-v1"
                        ),
                        "status": "PASSED",
                        "coverage_id": "fixture",
                        "family": "ac5102",
                        "coverage_claim": "visual components only",
                        "covered_events": ["ac5102_001"],
                        "covered_event_count": 1,
                        "component_catalogs": [
                            {
                                "name": "c416",
                                "manifest_path": str(catalog416),
                                "manifest_sha256": module.file_sha256(catalog416),
                            },
                            {
                                "name": "c512",
                                "manifest_path": str(catalog512),
                                "manifest_sha256": module.file_sha256(catalog512),
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            index, events, snapshots = (
                module._material_component_coverage_bundles(
                    raw_bundles=[
                        {
                            "path": str(bundle),
                            "sha256": module.file_sha256(bundle),
                        }
                    ],
                    plan_dir=root,
                    current_material_manifests={
                        str(catalog416.resolve()).casefold(): (
                            module.file_sha256(catalog416)
                        ),
                        str(catalog512.resolve()).casefold(): (
                            module.file_sha256(catalog512)
                        ),
                    },
                    quarantines={},
                )
            )
            self.assertEqual(events, {"ac5102_001"})
            self.assertEqual(
                index[0]["coverage_status"],
                "split_native_component_coverage_passed",
            )
            self.assertEqual(len(snapshots), 1)

    def test_dirinfo_row_collection_supports_source_alias_rows(self) -> None:
        value = {
            "dirinfo_kind": 113,
            "routes": [
                {
                    "dirinfo_source_rows": [
                        {"row_index": 2},
                        {"row_index": 11},
                    ]
                }
            ],
        }
        self.assertEqual(
            module._produced_dirinfo_rows(value, default_kind=None),
            {(113, 2), (113, 11)},
        )

    def test_explicit_excluded_rows_are_not_produced(self) -> None:
        value = {
            "dirinfo_kind": 201,
            "routes": [{"dirinfo_row": 0}],
            "excluded_dirinfo_rows": [
                {
                    "dirinfo_row": 2,
                    "production_disposition": (
                        "excluded_until_layered_composition_and_parent_child_timing_are_closed"
                    ),
                }
            ],
        }
        self.assertEqual(
            module._produced_dirinfo_rows(value, default_kind=None),
            {(201, 0)},
        )
        self.assertEqual(
            module._excluded_dirinfo_rows(value, default_kind=None),
            {
                (201, 2): {
                    "disposition": "blocked",
                    "production_state": (
                        "explicitly_excluded_by_current_production_manifest"
                    ),
                    "blocker": (
                        "excluded_until_layered_composition_and_parent_child_timing_are_closed"
                    ),
                }
            },
        )

    def test_superseded_path_is_explicitly_excluded(self) -> None:
        root = Path("D:/durable/v30")
        self.assertTrue(
            module._path_matches_exclusion(
                root=root,
                path=root / "ac7210_superseded_verbose_audit" / "manifest.json",
                fragments=["superseded"],
            )
        )
        self.assertFalse(
            module._path_matches_exclusion(
                root=root,
                path=root / "ac7210" / "manifest.json",
                fragments=["superseded"],
            )
        )


if __name__ == "__main__":
    unittest.main()
