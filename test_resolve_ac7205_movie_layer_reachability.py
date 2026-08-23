import unittest

from tools.frida_runtime_probe import resolve_ac7205_movie_layer_reachability as m


class Ac7205MovieLayerReachabilityTests(unittest.TestCase):
    def test_event_and_editorial_universes_are_exhaustive(self):
        self.assertEqual(len(m.EVENTS), 22)
        self.assertEqual(m.DEFERRED_NATIVE512_EVENTS, ("ac7205_018",))
        self.assertEqual(len(m.NATIVE416_EVENTS), 21)
        self.assertEqual(set(m.EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER), set(m.NATIVE416_EVENTS))
        self.assertEqual(len(set(m.EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER)), 21)

    def test_route_contract_covers_every_event(self):
        self.assertEqual(sum(m.EXPECTED_ROUTE_LENGTHS.values()), 98)
        self.assertEqual(set(m.EXPECTED_ROUTE_EVENT_FREQUENCIES), set(m.EVENTS))
        self.assertEqual(m.EXPECTED_ROUTE_EVENT_FREQUENCIES["ac7205_018"], 40)

    def test_runtime_resource_partition_is_exact(self):
        self.assertEqual(len(m.COMPILED_RESOURCE_NAMES), 22)
        self.assertEqual(len(m.RUNTIME_ONLY_NONRESOURCE_NODES), 5)
        self.assertFalse(m.COMPILED_RESOURCE_NAMES & m.RUNTIME_ONLY_NONRESOURCE_NODES)
        self.assertTrue({"cap7205_news_qb_001", "cap7205_news_qb_005"} <= m.COMPILED_RESOURCE_NAMES)
        self.assertIn("ac8050_tx_count_uwa_suji_1000", m.RUNTIME_ONLY_NONRESOURCE_NODES)

    def test_exact_duplicate_contract_is_narrow(self):
        self.assertEqual(len(m.EXPECTED_EXACT_DUPLICATE_DGM_GROUPS), 2)
        self.assertIn(
            frozenset({"ac7205_news_3on_kok_L_01.dgm", "ac7205_news_3on_kok_L_01_lp.dgm"}),
            m.EXPECTED_EXACT_DUPLICATE_DGM_GROUPS,
        )
        self.assertIn(
            frozenset({"ac7205_news_3on_kok_L_03.dgm", "ac7205_news_3on_kok_L_03_lp.dgm"}),
            m.EXPECTED_EXACT_DUPLICATE_DGM_GROUPS,
        )

    def test_native_dimensions_remain_separate(self):
        self.assertEqual(m.EXPECTED_DIMENSIONS["native416_family_source"], (416, 232))
        self.assertEqual(m.EXPECTED_DIMENSIONS["native512_gameplay_effect_source"], (512, 416))

    def test_runtime_motion_modes_are_code_decoded_not_name_inferred(self):
        full_loop = m.decode_motion_key_flags([0, 2, 1])
        scene_loop = m.decode_motion_key_flags([0, 3, 1])
        finite = m.decode_motion_key_flags([0, 2, 0])
        self.assertEqual(full_loop["motion_playback_mode"], "loop_full_z2d_scene")
        self.assertEqual(scene_loop["motion_playback_mode"], "loop_from_z2d_scene_loop_frame")
        self.assertTrue(full_loop["motion_key_persists_after_nominal_end"])
        self.assertFalse(finite["motion_key_persists_after_nominal_end"])

    def test_unknown_runtime_motion_mode_fails_closed(self):
        with self.assertRaisesRegex(m.Ac7205ReachabilityError, "unknown runtime Z2D playback mode"):
            m.decode_motion_key_flags([0, 9, 1])

    def test_runtime_extractor_is_fail_closed(self):
        with self.assertRaisesRegex(m.Ac7205ReachabilityError, "schema differs"):
            m.extract_runtime_bindings({})


if __name__ == "__main__":
    unittest.main()
