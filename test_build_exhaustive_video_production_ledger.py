import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_exhaustive_video_production_ledger as module  # noqa: E402


class BuildExhaustiveVideoProductionLedgerTest(unittest.TestCase):
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
            quarantines={},
        )
        self.assertEqual(
            disposition,
            ("gameplay_effect_collection", "planned_unproduced", ""),
        )

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
