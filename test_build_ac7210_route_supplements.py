import sys
import tempfile
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent / "tools" / "frida_runtime_probe"
sys.path.insert(0, str(MODULE_DIR))
import build_ac7210_route_supplements as module  # noqa: E402


class BuildAc7210RouteSupplementsTest(unittest.TestCase):
    def test_status_is_review_only(self):
        self.assertIn("RISK", module.STATUS)
        self.assertIn("HUMAN_REVIEW_REQUIRED", module.STATUS)

    def test_static_hold_frame_totals(self):
        self.assertEqual(255 + 233 + 222 + 214, 924)
        self.assertEqual(255 + 430 + 222 + 214, 1121)

    def test_native_grid_is_unchanged(self):
        self.assertEqual((module.WIDTH, module.HEIGHT, module.FPS), (416, 232, 30))

    def test_output_manifest_path_is_stable_and_relative(self):
        staging = Path.cwd() / "candidate.staging"
        output = staging / "REVIEW_NOW_2_MP4" / "candidate.mp4"
        self.assertEqual(
            module.relative_output_path(output, staging=staging),
            "REVIEW_NOW_2_MP4/candidate.mp4",
        )
        with self.assertRaises(ValueError):
            module.relative_output_path(Path.cwd() / "outside.mp4", staging=staging)

    def test_approved_production_matrix_is_exact(self):
        self.assertEqual(module.PRODUCTION_EDITIONS, ("none", "ja", "zh"))
        self.assertEqual(
            module.EXPECTED_ROUTES,
            {
                0: ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_004"],
                1: ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_004"],
            },
        )
        self.assertEqual(set(module.EXCLUDED_ROUTES), {2, 3, 4})
        self.assertIn("FULL_PRODUCTION_COMPLETE", module.PRODUCTION_STATUS)

    def test_exact_owner_approved_zh_hashes_are_stable(self):
        self.assertEqual(
            module.APPROVED_ZH_SHA256,
            {
                0: "8927CFDF7497B63B4FA47D7D9DB0C340FC837596547F3B9F4E8E15C764079088",
                1: "990407DD95ABC18911782AFA9F2EC7AA3E2F17997BA9F716892D1AFFB1A06849",
            },
        )

    def test_event_presentation_timeline_extracts_local_cues(self):
        timeline = [
            {
                "event": "ac7210_001",
                "start_sample": 0,
                "end_sample": 408000,
            },
            {
                "event": "ac7210_004",
                "start_sample": 408000,
                "end_sample": 750400,
            },
        ]
        cues = [
            {"start_ms": 1035, "end_ms": 2840, "text": "first"},
            {"start_ms": 10667, "end_ms": 11439, "text": "second"},
        ]
        self.assertEqual(
            module.extract_event_local_cues(cues, timeline),
            {
                "ac7210_001": [
                    {"start_ms": 1035, "end_ms": 2840, "text": "first"}
                ],
                "ac7210_004": [
                    {"start_ms": 2167, "end_ms": 2939, "text": "second"}
                ],
            },
        )

    def test_subtitle_crossing_event_boundary_fails_closed(self):
        timeline = [
            {
                "event": "ac7210_001",
                "start_sample": 0,
                "end_sample": 48000,
            }
        ]
        with self.assertRaises(ValueError):
            module.extract_event_local_cues(
                [{"start_ms": 900, "end_ms": 1100, "text": "crosses"}],
                timeline,
            )

    def test_excluded_rows_must_be_exact(self):
        rows = [
            {
                "dirinfo_row": row_number,
                "ordered_events": events,
                "excluded_component_events": (
                    ["ac7210_006"]
                    if row_number in {2, 3}
                    else ["ac7210_007", "ac7210_008"]
                ),
                "production_disposition": (
                    "excluded_until_layered_composition_and_parent_child_timing_are_closed"
                ),
            }
            for row_number, events in module.EXCLUDED_ROUTES.items()
        ]
        self.assertEqual(
            [row["dirinfo_row"] for row in module.validate_excluded_route_declarations(rows)],
            [2, 3, 4],
        )
        rows[0]["ordered_events"] = ["ac7210_001", "ac7210_006"]
        with self.assertRaises(ValueError):
            module.validate_excluded_route_declarations(rows)

    def test_hardlink_preserves_exact_file_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "approved.mp4"
            target = root / "output" / "approved.mp4"
            source.write_bytes(b"approved exact bytes")
            audit = module.hardlink_exact(source, target)
            self.assertTrue(audit["same_file_identity"])
            self.assertTrue(target.samefile(source))
            self.assertEqual(source.read_bytes(), target.read_bytes())

    def test_source_rehash_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.bin"
            source.write_bytes(b"one")
            snapshots = [
                {
                    "label": "test",
                    "path": str(source),
                    "sha256": module.file_sha256(source),
                }
            ]
            module.assert_source_snapshots_unchanged(snapshots)
            source.write_bytes(b"two")
            with self.assertRaises(RuntimeError):
                module.assert_source_snapshots_unchanged(snapshots)


if __name__ == "__main__":
    unittest.main()
