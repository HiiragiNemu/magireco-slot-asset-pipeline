import unittest

from tools.frida_runtime_probe import resolve_ac1104_event_audio_authority as m


class Ac1104AudioAuthorityTests(unittest.TestCase):
    def test_caption_name_normalizes_runtime_z2d1_typo(self):
        self.assertEqual(
            m.normalize_caption_name("cap1104_banana_iro_043.z2d1"),
            "cap1104_banana_iro_043",
        )
        self.assertEqual(
            m.normalize_caption_name("cap1104_banana_tks_041.z2d"),
            "cap1104_banana_tks_041",
        )

    def test_event_component_contract_covers_all_events_and_two_bgm_occurrences(self):
        self.assertEqual(set(m.EXPECTED_EVENT_COMPONENTS), set(m.EVENTS))
        self.assertEqual(sum(map(len, m.EXPECTED_EVENT_COMPONENTS.values())), 31)
        bgm = [
            (event, row)
            for event, rows in m.EXPECTED_EVENT_COMPONENTS.items()
            for row in rows
            if row[0] == 229
        ]
        self.assertEqual(len(bgm), 2)

    def test_label_contract_includes_corrected_event17_requests(self):
        self.assertEqual(m.OFFICIAL_LABEL_TEXT["6214"], "きゃっ")
        self.assertEqual(m.OFFICIAL_LABEL_TEXT["2677"], "やりましたね")
        self.assertEqual(len(m.NO_CALLBACK_CAPTION_NODES), 2)

    def test_runtime_caption_extractor_is_fail_closed(self):
        with self.assertRaisesRegex(m.Ac1104AudioAuthorityError, "schema differs"):
            m.extract_runtime_caption_nodes({})


if __name__ == "__main__":
    unittest.main()
