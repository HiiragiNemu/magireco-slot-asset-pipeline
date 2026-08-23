import unittest

from tools.frida_runtime_probe import resolve_ac1101_event_audio_authority as m


class Ac1101AudioAuthorityTests(unittest.TestCase):
    def test_event_component_contract_covers_all_events_and_two_bgm_occurrences(self):
        self.assertEqual(set(m.EXPECTED_EVENT_COMPONENTS), set(m.EVENTS))
        self.assertEqual(sum(map(len, m.EXPECTED_EVENT_COMPONENTS.values())), 22)
        bgm = [row for rows in m.EXPECTED_EVENT_COMPONENTS.values() for row in rows if row[0] == 229]
        self.assertEqual(len(bgm), 2)

    def test_label_contract_is_code_label_bound(self):
        self.assertEqual(m.OFFICIAL_LABEL_TEXT["4310"], "さなの")
        self.assertEqual(m.OFFICIAL_LABEL_TEXT["8369"], "ねこ鍋チャレンジ")
        self.assertEqual(m.OFFICIAL_LABEL_TEXT["8373"], "ねこ鍋チャレンジ")
        self.assertEqual(len(m.NO_CALLBACK_CAPTION_NODES), 2)

    def test_caption_name_normalization(self):
        self.assertEqual(m.normalize_caption_name("cap1101_neko_san_009.z2d"), "cap1101_neko_san_009")
        self.assertEqual(m.normalize_caption_name("cap1101_neko_san_009.z2d1"), "cap1101_neko_san_009")

    def test_runtime_caption_extractor_is_fail_closed(self):
        with self.assertRaisesRegex(m.Ac1101AudioAuthorityError, "schema differs"):
            m.extract_runtime_caption_nodes({})


if __name__ == "__main__":
    unittest.main()
