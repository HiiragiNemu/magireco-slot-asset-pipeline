import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
sys.path.insert(0, str(MODULE_DIR))
import build_mature_416_route_batch as module  # noqa: E402


class BuildMature416RouteBatchTest(unittest.TestCase):
    def test_contract_is_native_and_showcase_is_not_a_session(self):
        self.assertEqual((module.WIDTH, module.HEIGHT, module.FPS), (416, 232, 30))
        self.assertIn("not_single_native_session", module.SHOWCASE_CLAIM)
        self.assertEqual(module.EDITIONS, ("none", "ja", "zh"))

    def test_exact_duplicate_normalization(self):
        proposal = {
            "deduplication": {
                "groups": [
                    {"kept": "ac4902_001", "removed": ["ac4902_054"]},
                    {"kept": "ac4902_002", "removed": ["ac4902_055"]},
                    {
                        "kept": "ac4902_004",
                        "removed": ["ac4902_026", "ac4902_061"],
                    },
                ]
            }
        }
        aliases = module.duplicate_alias_map(proposal)
        self.assertEqual(
            module.normalize_sequence(
                ["ac4902_054", "ac4902_055", "ac4902_061"], aliases
            ),
            ["ac4902_001", "ac4902_002", "ac4902_004"],
        )

    def test_route_timeline_is_cumulative_on_frame_sample_grid(self):
        source = {
            "a": {
                "start_frame": 10,
                "end_frame": 12,
                "start_sample": 16000,
                "end_sample": 19200,
            },
            "b": {
                "start_frame": 30,
                "end_frame": 33,
                "start_sample": 48000,
                "end_sample": 52800,
            },
        }
        rows, frames, samples = module.route_timeline(["a", "b"], source)
        self.assertEqual((frames, samples), (5, 8000))
        self.assertEqual(rows[1]["start_frame"], 2)
        self.assertEqual(rows[1]["start_sample"], 3200)

    def test_plan_route_counts_and_alias_rows_are_finite(self):
        plan_root = MODULE_DIR / "series_proposals"
        ac7206 = json.loads(
            (plan_root / "ac7206_mature_dirinfo_routes_v1.json").read_text(
                encoding="utf-8"
            )
        )
        ac4902 = json.loads(
            (plan_root / "ac4902_mature_dirinfo_routes_v1.json").read_text(
                encoding="utf-8"
            )
        )
        ac0911 = json.loads(
            (plan_root / "ac0911_mature_dirinfo_routes_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(ac7206["routes"]), 6)
        self.assertEqual(len(ac4902["routes"]), 5)
        self.assertEqual(
            [row["row_index"] for row in ac7206["routes"][0]["source_rows"]],
            [20, 30],
        )
        self.assertEqual(
            [row["row_index"] for row in ac4902["routes"][2]["source_rows"]],
            [2, 11],
        )
        self.assertEqual(len(ac0911["routes"]), 9)
        self.assertEqual(
            {row["row_index"] for row in ac0911["excluded_dirinfo_rows"]},
            {8, 10, 11, 12, 13},
        )
        for plan in (ac7206, ac4902, ac0911):
            signatures = {
                tuple(route["render_event_sequence"]) for route in plan["routes"]
            }
            self.assertEqual(len(signatures), len(plan["routes"]))

    def test_route_subtitle_cues_keep_event_local_timing(self):
        timeline = {
            "a": {
                "start_sample": 0,
                "end_sample": 3200,
            },
            "b": {
                "start_sample": 3200,
                "end_sample": 8000,
            },
        }
        cues = [
            {"start_ms": 10, "end_ms": 30, "text": "A"},
            {"start_ms": 80, "end_ms": 120, "text": "B"},
        ]
        output = module.route_subtitle_cues(["b", "a"], timeline, cues)
        self.assertEqual([row["text"] for row in output], ["B", "A"])
        self.assertEqual(output[0]["start_ms"], 13)
        self.assertEqual(output[1]["start_ms"], 110)


if __name__ == "__main__":
    unittest.main()
