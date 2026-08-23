import unittest

from tools.frida_runtime_probe import resolve_ac7210_movie_layer_reachability as m


class Ac7210MovieLayerReachabilityTests(unittest.TestCase):
    def test_route_universe_and_native416_projection_are_exhaustive(self):
        self.assertEqual(set(m.DIRINFO_ROUTES), set(range(5)))
        self.assertEqual(set().union(*map(set, m.DIRINFO_ROUTES.values())), set(m.EVENTS))
        self.assertEqual(m.EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER,
                         ("ac7210_001", "ac7210_002", "ac7210_005", "ac7210_003", "ac7210_004"))
        self.assertEqual(set(m.NATIVE416_STORY_EVENTS), set(m.EVENTS[:5]))
        self.assertEqual(set(m.LOWER_PRIORITY_COMPONENT_EVENTS), set(m.EVENTS[5:]))

    def test_runtime_binding_contract_covers_required_z2d_names(self):
        self.assertEqual(set(m.EXPECTED_BINDINGS), set(m.EVENTS))
        names = {row[2] for values in m.EXPECTED_BINDINGS.values() for row in values}
        self.assertEqual(names, set(m.REQUIRED_Z2D_NAMES))
        self.assertTrue({"ac7210_AT_ibu_cap_title", "ac8040_kyo_anten", "ac8000_cmn_tx_WIN"} <= names)

    def test_story_duplicate_alias_contract_is_narrow(self):
        self.assertEqual(m.EXPECTED_STORY_DUPLICATE_ALIAS,
                         {"canonical": "ac7210_002_c03_LP_MR.dgm", "alias": "ac7210_002_c03_MR.dgm"})

    def test_component_dimensions_remain_separate(self):
        self.assertEqual(m.EXPECTED_DIMENSIONS["native416_story_visual"], (416, 232))
        self.assertEqual(m.EXPECTED_DIMENSIONS["native512x416_component_or_gameplay_visual"], (512, 416))
        self.assertEqual(m.EXPECTED_DIMENSIONS["native320x256_gameplay_effect_component"], (320, 256))

    def test_runtime_extractor_is_fail_closed(self):
        with self.assertRaisesRegex(m.Ac7210ReachabilityError, "schema differs"):
            m.extract_runtime_bindings({})


if __name__ == "__main__":
    unittest.main()
