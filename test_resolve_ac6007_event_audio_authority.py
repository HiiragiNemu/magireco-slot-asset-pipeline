import unittest

from tools.frida_runtime_probe import resolve_ac6007_event_audio_authority as m


class Ac6007AudioAuthorityTests(unittest.TestCase):
    def test_event_component_contract_is_exhaustive(self):
        self.assertEqual(set(m.EXPECTED_EVENT_COMPONENTS), set(m.EVENTS))
        self.assertEqual(sum(map(len, m.EXPECTED_EVENT_COMPONENTS.values())), 18)
        bgm = [row for rows in m.EXPECTED_EVENT_COMPONENTS.values() for row in rows if row[:2] == (225, 550)]
        self.assertEqual(len(bgm), 3)

    def test_parent_callback_contract_is_exhaustive(self):
        self.assertEqual(sum(map(len, m.EXPECTED_CALLBACK_OCCURRENCES.values())), 24)
        names = {name for rows in m.EXPECTED_CALLBACK_OCCURRENCES.values() for name in rows}
        self.assertEqual(len(names), 17)
        self.assertIn("ac8000_cmn_tx_WIN", names)
        self.assertIn("ac8040_kyo_anten", names)

    def test_z2d_suffix_normalization(self):
        self.assertEqual(m.normalize_z2d_name("cap6007_qkuma_fer_001.z2d"), "cap6007_qkuma_fer_001")
        self.assertEqual(m.normalize_z2d_name("cap6007_qkuma_fer_001.z2d1"), "cap6007_qkuma_fer_001")

    def test_presentation_extractor_fails_closed(self):
        with self.assertRaisesRegex(m.Ac6007AudioAuthorityError, "schema differs"):
            m.extract_callback_occurrences({})


if __name__ == "__main__":
    unittest.main()
