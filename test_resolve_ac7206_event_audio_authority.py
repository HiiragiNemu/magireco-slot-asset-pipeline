import unittest

from tools.frida_runtime_probe import resolve_ac7206_event_audio_authority as m


class Ac7206AudioAuthorityTests(unittest.TestCase):
    def test_event_component_contract_covers_story_and_empty_gameplay_event(self):
        self.assertEqual(set(m.EXPECTED_EVENT_COMPONENTS), set(m.EVENTS))
        self.assertEqual(sum(map(len, m.EXPECTED_EVENT_COMPONENTS.values())), 16)
        self.assertEqual(m.EXPECTED_EVENT_COMPONENTS[m.GAMEPLAY_EVENT], set())
        bgm = [row for rows in m.EXPECTED_EVENT_COMPONENTS.values() for row in rows if row[0] == 226]
        self.assertEqual(bgm, [(226, 551, 3260), (226, 551, 3260)])

    def test_voice_contract_covers_four_callbacks_and_fourteen_events(self):
        self.assertEqual(set(m.EXPECTED_VOICE_BY_EVENT), set(m.STORY_EVENTS))
        self.assertEqual({row[1] for row in m.EXPECTED_VOICE_BY_EVENT.values()}, set(m.VOICE_TEXT))
        self.assertEqual(m.EXPECTED_VOICE_BY_EVENT["ac7206_001"], ("cap7206_paint_ari_001", 5321, 1))
        self.assertEqual(m.EXPECTED_VOICE_BY_EVENT["ac7206_002"], ("cap7206_paint_ari_003", 5323, 10))

    def test_translation_labels_preserve_existing_p24_text(self):
        self.assertEqual(m.VOICE_TEXT[5322], "それこそが本物のアート")
        self.assertEqual(m.VOICE_TEXT[5324], "アリナが代わりにマスタリングしてあげる")

    def test_visual_runtime_extractor_remains_fail_closed(self):
        with self.assertRaisesRegex(Exception, "schema differs"):
            m.extract_runtime_bindings({})


if __name__ == "__main__":
    unittest.main()
