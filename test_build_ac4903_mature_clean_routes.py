import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).resolve().parent
    / "tools"
    / "frida_runtime_probe"
    / "build_ac4903_mature_clean_routes.py"
)
SPEC = importlib.util.spec_from_file_location("build_ac4903_mature_clean_routes", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC.loader.exec_module(MODULE)


class Ac4903MatureCleanRoutesTests(unittest.TestCase):
    def test_route_partition_is_exhaustive(self):
        self.assertEqual(
            set(MODULE.INCLUDED_ROWS) | set(MODULE.EXCLUDED_ROWS),
            set(range(22)),
        )
        self.assertFalse(set(MODULE.INCLUDED_ROWS) & set(MODULE.EXCLUDED_ROWS))
        self.assertEqual(MODULE.EXCLUDED_ROWS, (14, 18, 21))

    def test_route_timeline_is_exact_frame_sample_grid(self):
        assets = {
            "ac4903_001": {
                "frames": 90,
                "samples": 144000,
                "source_policy": "simple",
            },
            "ac4903_002": {
                "frames": 120,
                "samples": 192000,
                "source_policy": "family",
            },
        }
        timeline = MODULE._route_timeline(
            ["ac4903_001", "ac4903_002"], assets
        )
        self.assertEqual(timeline[-1]["end_frame"], 210)
        self.assertEqual(timeline[-1]["end_sample"], 336000)
        self.assertEqual(timeline[1]["start_sample"], 144000)

    def test_route_cues_shift_by_exact_event_samples(self):
        assets = {
            "ac4903_001": {
                "samples": 144000,
                "cues": {"ja": [], "zh": []},
            },
            "ac4903_002": {
                "samples": 192000,
                "cues": {
                    "ja": [{"start_ms": 100, "end_ms": 300, "text": "ja"}],
                    "zh": [{"start_ms": 100, "end_ms": 300, "text": "zh"}],
                },
            },
        }
        cues = MODULE._route_cues(
            events=["ac4903_001", "ac4903_002"], assets=assets
        )
        self.assertEqual(cues["ja"][0]["start_ms"], 3100)
        self.assertEqual(cues["zh"][0]["end_ms"], 3300)

    def test_simple_and_source_event_sets_do_not_overlap(self):
        self.assertFalse(set(MODULE.SIMPLE_EVENTS) & set(MODULE.SOURCE_EVENTS))


if __name__ == "__main__":
    unittest.main()
