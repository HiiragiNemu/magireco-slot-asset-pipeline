import unittest

from tools.frida_runtime_probe import resolve_ac7210_event_audio_authority as m


class Ac7210EventAudioAuthorityTests(unittest.TestCase):
    def test_component_contract_covers_five_native416_events(self):
        self.assertEqual(set(m.EXPECTED_EVENT_COMPONENTS), set(m.NATIVE416_STORY_EVENTS))
        self.assertEqual(sum(map(len, m.EXPECTED_EVENT_COMPONENTS.values())), 6)
        self.assertEqual(m.EXPECTED_EVENT_COMPONENTS["ac7210_005"], {(2258, 11201, 0), (2261, 11204, 510)})

    def test_voice_contract_has_four_exact_parent_bound_callbacks(self):
        self.assertEqual(set(m.EXPECTED_VOICE_BY_EVENT), set(m.NATIVE416_STORY_EVENTS))
        rows = [row for values in m.EXPECTED_VOICE_BY_EVENT.values() for row in values]
        self.assertEqual(len(rows), 4)
        self.assertEqual({row[1] for row in rows}, {3279, 3280, 3593, 3594})

    def test_deduplicated_presentation_contract_totals_1354_frames(self):
        self.assertEqual(sum(m.EXPECTED_VIDEO_CONTENT_FRAMES.values()), 1174)
        self.assertEqual(sum(m.EXPECTED_PRESENTATION_FRAMES.values()), 1354)
        self.assertEqual(m.EXPECTED_PRESENTATION_FRAMES["ac7210_002"] - m.EXPECTED_VIDEO_CONTENT_FRAMES["ac7210_002"], 83)
        self.assertEqual(m.EXPECTED_PRESENTATION_FRAMES["ac7210_003"] - m.EXPECTED_VIDEO_CONTENT_FRAMES["ac7210_003"], 97)


if __name__ == "__main__":
    unittest.main()
