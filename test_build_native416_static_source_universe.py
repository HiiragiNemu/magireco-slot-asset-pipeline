from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_native416_static_source_universe import (
    UniverseError,
    align_catalog,
    build_family_rows,
    extract_dgm_names,
    probe_catalog,
    resolve_durable_media_path,
)


class Native416StaticSourceUniverseTests(unittest.TestCase):
    def test_catalog_alignment_is_exact_and_fail_closed(self):
        rows = [
            {"global_index": "1", "official_name": "beta"},
            {"global_index": "0", "official_name": "alpha"},
        ]
        self.assertEqual(["alpha", "beta"], [r["official_name"] for r in align_catalog(rows, ["alpha", "beta"])])
        with self.assertRaisesRegex(UniverseError, "differ"):
            align_catalog(rows, ["alpha", "gamma"])

    def test_collision_disambiguated_named_media_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = {
                "package": "main",
                "group": "ac4904",
                "official_name": "ac4904_name_",
                "global_index": "4188",
            }
            target = root / "main" / "ac4904" / "ac4904_name__idx4188.mp4"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"fixture")
            self.assertEqual(target, resolve_durable_media_path(row, root))

    def test_probe_catalog_preserves_absent_rows_and_native_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            present = {
                "global_index": "0",
                "package": "main",
                "group": "ac0001",
                "official_name": "ac0001_clip",
                "source_exists": "yes",
            }
            absent = {
                "global_index": "1",
                "package": "main",
                "group": "ac0001",
                "official_name": "ac0001_missing",
                "source_exists": "no",
            }
            path = root / "main" / "ac0001" / "ac0001_clip.mp4"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"fixture")
            rows = probe_catalog(
                [present, absent],
                root,
                workers=1,
                probe=lambda _: {
                    "codec_name": "h264",
                    "width": 416,
                    "height": 232,
                    "frame_rate": "30/1",
                    "frame_count": 90,
                    "duration_seconds": 3.0,
                },
            )
            self.assertEqual("PASS", rows[0]["media_open_status"])
            self.assertEqual("SOURCE_ABSENT", rows[1]["media_open_status"])

    def test_dgm_references_are_unique_and_strip_extension(self):
        data = b"[clip_a.dgm]\x00clip_a.dgm\x00clip_b.dgm\x00"
        self.assertEqual(["clip_a", "clip_b"], extract_dgm_names(data))

    def test_family_queue_separates_pending_existing_and_fail_closed(self):
        media = [
            {
                "official_name": "ac0001_clip",
                "group": "ac0001",
                "media_open_status": "PASS",
                "width": 416,
                "height": 232,
                "frame_count": 90,
            },
            {
                "official_name": "ac6003_clip",
                "group": "ac6003",
                "media_open_status": "PASS",
                "width": 416,
                "height": 232,
                "frame_count": 90,
            },
            {
                "official_name": "ac0917_clip",
                "group": "ac0917",
                "media_open_status": "PASS",
                "width": 416,
                "height": 232,
                "frame_count": 90,
            },
        ]
        edges = [
            {
                "family_root": root,
                "dgm_name": f"{root}_clip",
                "compiled_table_present": True,
                "width": 416,
                "height": 232,
            }
            for root in ("ac0001", "ac6003", "ac0917")
        ]
        event_info = [
            {"base_name": root, "scene_name": f"{root}_001"}
            for root in ("ac0001", "ac6003", "ac0917")
        ]
        dirinfo = [
            {"base_names": root, "ordered_events": f"{root}_001"}
            for root in ("ac0001", "ac6003", "ac0917")
        ]
        statuses = {
            "ac6003": {"state": "FAIL_CLOSED", "blocker": "P16 exact offset"},
            "ac0917": {"state": "PRODUCED_CURRENT_REVIEW_READY"},
        }
        rows = {row["family_root"]: row for row in build_family_rows(media, edges, event_info, dirinfo, statuses)}
        self.assertEqual("P1_AUDIENCE_ROUTE_CODE_AUDIT", rows["ac0001"]["priority_lane"])
        self.assertEqual("P0_FAIL_CLOSED_NO_RENDER", rows["ac6003"]["priority_lane"])
        self.assertEqual("P4_EXISTING_OUTPUT_REAUDIT_OR_REVIEW", rows["ac0917"]["priority_lane"])
        self.assertFalse(any(row["production_allowed"] for row in rows.values()))

    def test_explicit_gameplay_effect_route_is_not_promoted_to_story_queue(self):
        media = [
            {
                "official_name": "ac9053_uwa_renda_impact_ef_add",
                "group": "ac9053",
                "media_open_status": "PASS",
                "width": 416,
                "height": 232,
                "frame_count": 90,
            }
        ]
        edges = [
            {
                "family_root": "ac9060",
                "dgm_name": "ac9053_uwa_renda_impact_ef_add",
                "compiled_table_present": True,
                "width": 416,
                "height": 232,
            }
        ]
        event_info = [{"base_name": "ac9060", "scene_name": "ac9060_001"}]
        dirinfo = [
            {
                "kind": "237",
                "base_names": "ac9060",
                "ordered_events": "ac9060_001",
                "disposition": "gameplay_effect_collection",
                "production_state": "planned_unproduced",
            }
        ]
        row = build_family_rows(media, edges, event_info, dirinfo, {})[0]
        self.assertEqual("P3_GAMEPLAY_EFFECT_OR_MATERIAL_CLASSIFICATION", row["priority_lane"])
        self.assertEqual("237", row["dirinfo_kinds"])
        self.assertEqual(237, row["min_dirinfo_kind"])
        self.assertEqual("gameplay_effect_collection", row["dirinfo_dispositions"])
        self.assertFalse(row["production_allowed"])


if __name__ == "__main__":
    unittest.main()
