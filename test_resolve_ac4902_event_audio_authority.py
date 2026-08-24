from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import resolve_ac4902_event_audio_authority as MODULE


class Ac4902EventAudioAuthorityTests(unittest.TestCase):
    def test_frozen_dimensions_match_exhaustive_family(self) -> None:
        self.assertEqual(64, len(MODULE.EVENT_IDS))
        self.assertEqual(20, len(MODULE.VOICE_REQUEST_IDS))
        self.assertEqual(24, len(MODULE.COMPONENT_REQUEST_SOUND_PAIRS))
        self.assertEqual(24, len(MODULE.CALLBACK_REQUEST_SOUND_PAIRS))
        self.assertEqual(6, len(MODULE.EXTENDED_HOLD_EVENTS))
        self.assertEqual(148, MODULE.EXPECTED_RETAINED_AUDIO)
        self.assertEqual(25703, MODULE.EXPECTED_OUTPUT_FRAMES)

    def test_translation_map_has_owner_approved_black_feather_identity(self) -> None:
        path = Path(
            "tools/frida_runtime_probe/translations/"
            "ac4902_exhaustive_native416_zh_dialogue_v2.json"
        )
        rows = MODULE._translation_map(path)
        self.assertEqual(MODULE.VOICE_REQUEST_IDS, frozenset(rows))
        self.assertEqual("黒羽", rows[8340]["speaker_ja"])
        self.assertEqual("黑羽：可恶！", rows[8340]["render_zh"])
        self.assertEqual("", rows[8209]["speaker_zh"])

    def test_translation_map_rejects_wrong_kuro_identity(self) -> None:
        source = Path(
            "tools/frida_runtime_probe/translations/"
            "ac4902_exhaustive_native416_zh_dialogue_v2.json"
        )
        document = json.loads(source.read_text(encoding="utf-8"))
        next(row for row in document["translations"] if row["request_id"] == 8340)[
            "speaker_zh"
        ] = "黑江"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.Ac4902AudioAuthorityError, "translation map dimensions differ"
            ):
                MODULE._translation_map(path)

    def test_speaker_override_scope_is_only_two_owner_approved_events(self) -> None:
        rows = MODULE._speaker_override_map(
            Path("tools/frida_runtime_probe/speaker_identity_overrides_v1.json")
        )
        self.assertEqual({("ac4902_003", 8340), ("ac4902_059", 8340)}, set(rows))
        self.assertTrue(
            all(row["canonical_speaker_code"] == "kuro_black_feather" for row in rows.values())
        )


if __name__ == "__main__":
    unittest.main()
