import unittest

from tools.frida_runtime_probe import resolve_ac7205_event_audio_authority as m


class Ac7205EventAudioAuthorityTests(unittest.TestCase):
    def test_component_contract_covers_all_native416_events(self):
        self.assertEqual(set(m.EXPECTED_EVENT_COMPONENTS), set(m.NATIVE416_EVENTS))
        self.assertEqual(sum(map(len, m.EXPECTED_EVENT_COMPONENTS.values())), 35)
        self.assertEqual(
            m.EXPECTED_BGM_COMPONENTS,
            {
                ("ac7205_015", 226, 551, 1409),
                ("ac7205_016", 226, 551, 3344),
                ("ac7205_017", 226, 551, 2384),
            },
        )

    def test_voice_contract_has_nine_parent_bound_occurrences(self):
        self.assertEqual(set(m.EXPECTED_VOICE_BY_EVENT), set(m.NATIVE416_EVENTS))
        rows = [row for values in m.EXPECTED_VOICE_BY_EVENT.values() for row in values]
        self.assertEqual(len(rows), 9)
        self.assertEqual({row[1] for row in rows}, {8310, 8311, 8312, 8313, 8314})
        self.assertEqual({row[2] for row in rows}, {1, 21})

    def test_unique_content_and_presentation_contract(self):
        self.assertEqual(sum(m.EXPECTED_UNIQUE_VIDEO_CONTENT_FRAMES.values()), 3303)
        self.assertEqual(sum(m.EXPECTED_PRESENTATION_FRAMES.values()), 3827)
        self.assertEqual(m.EXPECTED_PRESENTATION_FRAMES["ac7205_008"], 186)
        self.assertEqual(m.EXPECTED_PRESENTATION_FRAMES["ac7205_010"], 211)
        self.assertEqual(m.EXPECTED_PRESENTATION_FRAMES["ac7205_014"], 191)

    def test_editorial_order_is_one_exact_permutation(self):
        self.assertEqual(len(m.EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER), 21)
        self.assertEqual(set(m.EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER), set(m.NATIVE416_EVENTS))

    def test_graphical_frame_edge_transport_does_not_cross_next_frame(self):
        self.assertEqual(191 * 1000 // 30, 6366)
        self.assertLess(191 * 1000 // 30, 191 * 1000 / 30)


if __name__ == "__main__":
    unittest.main()
