import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent
MODULE_PATH = ROOT / "tools" / "frida_runtime_probe" / "verify_audience_longform_policy.py"
POLICY_PATH = ROOT / "tools" / "frida_runtime_probe" / "audience_longform_policy_v1.json"
SPEC = importlib.util.spec_from_file_location("verify_audience_longform_policy", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class AudienceLongformPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.withdrawals = MODULE.withdrawal_map(self.policy)

    def test_resolution_priority_and_longform_defaults(self):
        priorities = {row["resolution"]: row for row in self.policy["resolution_priority"]}
        self.assertGreater(priorities["416x232"]["priority"], priorities["512x288"]["priority"])
        self.assertEqual(
            priorities["512x288"]["action"],
            "record_evidence_then_defer_until_416x232_inventory_is_exhausted"
        )
        self.assertEqual(self.policy["product_contract"]["default_audience_product"], "family_longform")
        self.assertIn("every_reverse_proven_unique_playable_variant_exactly_once", self.policy["product_contract"]["multi_route_longform"])
        self.assertEqual(self.policy["product_contract"]["dynamic_runtime_role"], "targeted_validation_of_static_predictions_not_manual_trigger_enumeration")

    def test_explicit_fragment_is_withdrawn(self):
        item = {
            "inventory_item_id": "I_951B0D81C03C8E85DB08",
            "family": "ac1103_013",
            "content_type": "gameplay_effect",
            "review_disposition": "REVIEW_READY",
            "resolution": "416x232"
        }
        action, reason = MODULE.classify_item(item, self.withdrawals)
        self.assertEqual(action, "WITHDRAW_FROM_LONGFORM_REVIEW")
        self.assertIn("18-second", reason)

    def test_other_single_event_requires_family_audit(self):
        action, _ = MODULE.classify_item(
            {
                "inventory_item_id": "I_TEST",
                "family": "ac7114_001",
                "content_type": "story_route",
                "review_disposition": "REVIEW_READY",
                "resolution": "512x416"
            },
            self.withdrawals
        )
        self.assertEqual(action, "REQUIRES_FAMILY_LONGFORM_AUDIT")

    def test_416_owner_approved_product_is_withdrawn_pending_exhaustive_audit(self):
        action, reason = MODULE.classify_item(
            {
                "inventory_item_id": "I_APPROVED",
                "family": "ac0908",
                "content_type": "story_route",
                "review_disposition": "REVIEW_READY",
                "resolution": "416x232",
            },
            self.withdrawals,
        )
        self.assertEqual(action, "WITHDRAW_PENDING_EXHAUSTIVE_FAMILY_AUDIT")
        self.assertIn("every unique family variant", reason)

    def test_ac0908_known_coverage_is_9_of_17(self):
        row = next(item for item in self.policy["known_family_coverage"] if item["family"] == "ac0908")
        self.assertEqual(len(row["discovered_event_candidates"]), 17)
        self.assertEqual(len(row["included_unique_events"]), 9)
        self.assertEqual(len(row["missing_event_candidates"]), 8)
        self.assertEqual(row["current_authority"], "OWNER_PLAYBACK_APPROVED_PARTIAL_REFERENCE_NOT_EXHAUSTIVE")

    def test_ac1102_comparison_accepts_cross_route_compilation_but_requires_all_candidates(self):
        legacy = ROOT / "_test_ac1102_legacy.json"
        route_root = ROOT / "_test_ac1102_routes"
        try:
            legacy.write_text(
                json.dumps({"media": {"duration_ms": 1000}, "ordered_events": ["ac1102_001"]}),
                encoding="utf-8",
            )
            for index in range(16):
                manifest = (
                    route_root
                    / f"ac1102_route{index:02d}_full_no_bgm_editions_v1"
                    / "manifests"
                    / "family_editions_manifest.json"
                )
                manifest.parent.mkdir(parents=True, exist_ok=True)
                manifest.write_text(
                    json.dumps({
                        "release_id": f"fixture{index}",
                        "ordered_events": ["ac1102_001"],
                        "media": {"duration_ms": 1000},
                        "natural_session_claimed": False,
                    }),
                    encoding="utf-8",
                )
            result = MODULE.compare_ac1102(
                legacy,
                route_root,
                [{"ordered_events": "ac1102_001|ac1102_002"}],
            )
            self.assertEqual(result["longform_decision"]["required_product"], "exhaustive_unique_ac1102_family_compilation")
            self.assertFalse(result["longform_decision"]["native_single_session_is_a_gate"])
            self.assertEqual(result["legacy"]["missing_dirinfo_event_candidates"], ["ac1102_002"])
        finally:
            if legacy.exists():
                legacy.unlink()
            if route_root.exists():
                import shutil
                shutil.rmtree(route_root)

    def test_512x288_is_deferred(self):
        action, _ = MODULE.classify_item(
            {
                "inventory_item_id": "I_TEST",
                "family": "ac5000",
                "content_type": "story_route",
                "review_disposition": "REVIEW_READY",
                "resolution": "512x288"
            },
            self.withdrawals
        )
        self.assertEqual(action, "DEFER_512X288")

    def test_material_is_not_forced_into_story_longform(self):
        action, _ = MODULE.classify_item(
            {
                "inventory_item_id": "I_TEST",
                "family": "ac4906_001",
                "content_type": "component_archive",
                "review_disposition": "REVIEW_READY",
                "resolution": "416x232"
            },
            self.withdrawals
        )
        self.assertEqual(action, "PRESERVE_CURRENT_METADATA_PENDING_AUDIT")


if __name__ == "__main__":
    unittest.main()
