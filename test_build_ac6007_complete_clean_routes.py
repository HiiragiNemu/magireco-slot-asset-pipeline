import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).resolve().parent
    / "tools"
    / "frida_runtime_probe"
    / "build_ac6007_complete_clean_routes.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_ac6007_complete_clean_routes", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC.loader.exec_module(MODULE)


class Ac6007CompleteCleanRoutesTests(unittest.TestCase):
    def test_route_partition_is_exhaustive(self):
        self.assertEqual(
            set(MODULE.INCLUDED_ROWS) | set(MODULE.EXCLUDED_ROWS), set(range(5))
        )
        self.assertFalse(set(MODULE.INCLUDED_ROWS) & set(MODULE.EXCLUDED_ROWS))

    def test_entry_visible_sequence_is_parent_interval_selection(self):
        self.assertEqual(MODULE.ENTRY_FRAMES, 36 + 77 + 90)
        self.assertNotIn(
            "ac6007_lev_c002", MODULE.ENTRY_VISIBLE_SEQUENCE
        )
        self.assertEqual(len(MODULE.ENTRY_MISSING_EFFECTS), 2)

    def test_route_pcm_preserves_multiple_entry_scene_se(self):
        self.assertEqual(MODULE.ENTRY_EVENT, "ac6007_001")
        self.assertEqual(MODULE.EDITIONS, ("none", "ja", "zh"))


if __name__ == "__main__":
    unittest.main()
