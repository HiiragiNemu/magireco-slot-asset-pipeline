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
