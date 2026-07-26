import csv
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_ac0908_complete_entry_routes as module  # noqa: E402


class BuildAc0908CompleteEntryRoutesTest(unittest.TestCase):
    def test_route_matrix_is_exact(self) -> None:
        self.assertEqual(tuple(module.EXPECTED_ROUTES), tuple(range(6, 12)))
        self.assertEqual(
            module.EXPECTED_ROUTES[6], ("ac0908_002", 52)
        )
        self.assertEqual(
            module.EXPECTED_ROUTES[11], ("ac0908_007", 57)
        )
        self.assertEqual(module.ENTRY_FRAMES, 187)
        self.assertEqual(module.ENTRY_SAMPLES, 299200)

    def test_owner_attestation_is_fail_closed(self) -> None:
        path = (
            MODULE_DIR
            / "owner_attestations"
            / "owner_approved_ac0908_complete_entry_routes_20260726.json"
        )
        module._validate_owner_attestation(path)

    def test_dirinfo_rows_must_contain_exact_selectors(self) -> None:
        fields = [
            "kind",
            "row_index",
            "selector_raw",
            "scene_name",
            "route_status",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "routes.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for row, (outcome, _) in module.EXPECTED_ROUTES.items():
                    for selector, event in (
                        (1, "ac0908_001"),
                        (2, outcome),
                        (4, "ac0908_008"),
                    ):
                        writer.writerow(
                            {
                                "kind": 33,
                                "row_index": row,
                                "selector_raw": selector,
                                "scene_name": event,
                                "route_status": "ok",
                            }
                        )
            self.assertEqual(
                set(module._validate_dirinfo(path)),
                set(module.EXPECTED_ROUTES),
            )
            with path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["selector_raw"] = "3"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                module._validate_dirinfo(path)

    def test_complete_entry_timeline_is_frame_sample_exact(self) -> None:
        route = {
            "outcome": "ac0908_002",
            "outcome_frames": 270,
            "total_frames": 698,
            "total_samples": 1116800,
        }
        timeline = module._timeline(route)
        self.assertEqual(
            [row["event"] for row in timeline],
            ["ac0908_001", "ac0908_002", "ac0908_008"],
        )
        self.assertEqual(timeline[-1]["end_frame"], 698)
        self.assertEqual(timeline[-1]["end_sample"], 1116800)


if __name__ == "__main__":
    unittest.main()
