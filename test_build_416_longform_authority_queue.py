from __future__ import annotations

import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_416_longform_authority_queue import (
    build_queue,
)


def base(family: str, *, missing: int = 0, direction: int = 0) -> dict[str, str]:
    return {
        "family_root": family,
        "inventory_item_count": "3",
        "owner_playback_approved_item_count": "1",
        "native_eventinfo_container_count": "2",
        "dirinfo_route_count": "4",
        "old_manifest_missing_event_count": "1",
        "missing_layer_event_count": str(missing),
        "direction_scene_decode_required_event_count": str(direction),
    }


class Native416LongformAuditQueueTests(unittest.TestCase):
    def test_editions_collapse_to_family_groups_and_deep_authority_overrides(self):
        ac0908 = {
            "schema": "magireco-ac0908-runtime-unique-scene-authority-v2",
            "counts": {
                "event_container_count": 17,
                "canonical_unique_visible_scene_count": 14,
            },
            "legacy_longform_code_comparison": {
                "missing_canonical_visible_scene_count": 5,
                "guaranteed_exact_duplicate_render_occurrence_surplus_count": 2,
            },
            "production_blockers": ["tail", "layers"],
        }
        ac1102 = {
            "schema": "magireco-ac1102-exhaustive-unique-segment-authority-v1",
            "family": "ac1102",
            "route_universe": {"unique_event_count": 15},
            "native_source_universe": {"unique_sha256_count": 36},
            "legacy_longform": {
                "missing_required_unique_sha256_count": 14,
                "duplicate_surplus_occurrence_count": 13,
            },
            "decision": {"blockers": [{"kind": "missing_layer_media"}]},
        }
        ac1103 = {
            "schema": "magireco-exhaustive-family-source-identity-audit-v1",
            "family": "ac1103",
            "route_universe": {"unique_event_count": 13},
            "native_source_universe": {"unique_source_identity_count": 29},
            "legacy_longform": {
                "missing_required_unique_source_identity_count": 0,
                "duplicate_surplus_occurrence_count": 12,
            },
            "decision": {"blockers": [{"kind": "legacy_repeats"}]},
        }
        queue, summary = build_queue(
            [
                base("ac0908"),
                base("ac1102", missing=1),
                base("ac1103", missing=1),
                base("ac7002"),
            ],
            [
                (ac0908, Path("ac0908.json")),
                (ac1102, Path("ac1102.json")),
                (ac1103, Path("ac1103.json")),
            ],
            4,
        )
        self.assertEqual(4, summary["family_content_group_count"])
        self.assertEqual(12, summary["inventory_edition_item_count"])
        self.assertEqual(3, summary["deep_audited_family_count"])
        self.assertEqual(0, summary["certified_authoritative_longform_count"])
        rows = {row["family_root"]: row for row in queue}
        self.assertEqual(14, rows["ac0908"]["canonical_unique_unit_count"])
        self.assertEqual(5, rows["ac0908"]["old_product_missing_unique_unit_count"])
        self.assertEqual(13, rows["ac1102"]["old_product_exact_duplicate_surplus_count"])
        self.assertEqual(12, rows["ac1103"]["old_product_exact_duplicate_surplus_count"])
        self.assertEqual("PENDING_CODE_AUDIT", rows["ac7002"]["audit_state"])
        self.assertFalse(any(row["render_allowed"] for row in queue))

    def test_family_count_and_unknown_authority_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "family count differs"):
            build_queue([base("ac0908")], [], 2)
        with self.assertRaisesRegex(ValueError, "unsupported deep authority schema"):
            build_queue(
                [base("ac0908")],
                [({"schema": "unknown"}, Path("bad.json"))],
                1,
            )


if __name__ == "__main__":
    unittest.main()
