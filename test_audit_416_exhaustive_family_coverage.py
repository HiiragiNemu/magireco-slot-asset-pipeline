import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent
MODULE_PATH = ROOT / "tools" / "frida_runtime_probe" / "audit_416_exhaustive_family_coverage.py"
SPEC = importlib.util.spec_from_file_location("audit_416_exhaustive_family_coverage", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class Exhaustive416CoverageTests(unittest.TestCase):
    def policy(self):
        return {
            "known_family_coverage": [
                {
                    "family": "ac0908",
                    "included_unique_events": ["ac0908_001", "ac0908_002"],
                    "discovered_event_candidates": ["ac0908_001", "ac0908_002", "ac0908_003"],
                    "missing_event_candidates": ["ac0908_003"],
                    "current_authority": "OWNER_PLAYBACK_APPROVED_PARTIAL_REFERENCE_NOT_EXHAUSTIVE",
                    "reason": "fixture 2 of 3",
                }
            ]
        }

    @staticmethod
    def inventory(**overrides):
        row = {
            "inventory_item_id": "I1",
            "family": "ac0908",
            "content_type": "story_route",
            "resolution": "416x232",
            "edition": "zh",
            "owner_approved": "True",
            "event_ids": '["ac0908_001","ac0908_002"]',
            "canonical_sha256": "ABC",
            "sha256": "ABC",
            "title": "fixture",
            "source_absolute_path": "D:/fixture.mp4",
            "human_status": "exact_file_owner_playback_approved",
        }
        row.update(overrides)
        return row

    def test_known_incomplete_family_remains_blocked(self):
        families, withdrawals, summary = MODULE.build_ledger(
            [self.inventory()],
            [{"ordered_events": "ac0908_001|ac0908_002|ac0908_003"}],
            self.policy(),
        )
        self.assertEqual(families[0]["status"], "KNOWN_INCOMPLETE")
        self.assertEqual(families[0]["known_included_event_container_count"], 2)
        self.assertEqual(families[0]["known_included_unique_event_count"], 2)
        self.assertEqual(families[0]["missing_event_candidate_count"], 1)
        self.assertEqual(len(withdrawals), 1)
        self.assertEqual(summary["certified_exhaustive_family_labels"], 0)

    def test_material_and_non_416_are_excluded(self):
        rows = [
            self.inventory(content_type="material"),
            self.inventory(inventory_item_id="I2", resolution="512x288"),
        ]
        families, withdrawals, summary = MODULE.build_ledger(rows, [], self.policy())
        self.assertEqual(families, [])
        self.assertEqual(withdrawals, [])
        self.assertEqual(summary["inventory_item_count"], 0)

    def test_mutually_exclusive_candidates_are_counted_in_one_universe(self):
        rows = [self.inventory(owner_approved="False")]
        dirinfo = [
            {"ordered_events": "ac1000_001|ac1000_002"},
            {"ordered_events": "ac1000_001|ac1000_003"},
        ]
        rows[0].update(family="ac1000", event_ids='["ac1000_001","ac1000_002"]')
        families, _, _ = MODULE.build_ledger(rows, dirinfo, {"known_family_coverage": []})
        self.assertEqual(families[0]["discovered_event_candidate_count"], 3)
        self.assertEqual(families[0]["missing_event_candidates"], "ac1000_003")
        self.assertEqual(families[0]["final_family_product_gate"], "BLOCKED_PENDING_EXHAUSTIVE_UNIQUE_VARIANT_CLOSURE")


if __name__ == "__main__":
    unittest.main()
