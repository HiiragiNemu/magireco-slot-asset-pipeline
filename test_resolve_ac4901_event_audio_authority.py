from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import resolve_ac4901_event_audio_authority as MODULE


class Ac4901EventAudioAuthorityTests(unittest.TestCase):
    def test_frozen_dimensions_match_complete_family(self) -> None:
        self.assertEqual(205, len(MODULE.EVENT_IDS))
        self.assertEqual(3, len(MODULE.VOICE_REQUEST_IDS))
        self.assertEqual(9, len(MODULE.COMPONENT_REQUEST_SOUND_COUNTS))
        self.assertEqual(8, len(MODULE.CALLBACK_REQUEST_SOUND_PAIRS))
        self.assertEqual(21, len(MODULE.BGM_EVENTS))
        self.assertEqual(393, MODULE.EXPECTED_RETAINED_AUDIO)
        self.assertEqual(34236, MODULE.EXPECTED_VISUAL_FRAMES)

    def test_translation_map_preserves_iroha_and_ambiguous_mokyu_label(self) -> None:
        path = Path(
            "tools/frida_runtime_probe/translations/"
            "ac4901_exhaustive_native416_zh_dialogue_v1.json"
        )
        rows = MODULE._translation_map(path)
        self.assertEqual(MODULE.VOICE_REQUEST_IDS, frozenset(rows))
        self.assertEqual("环彩羽：按下去！", rows[2439]["render_zh"])
        self.assertEqual("环彩羽：好！", rows[2740]["render_zh"])
        self.assertEqual("", rows[8209]["speaker_zh"])

    def test_translation_map_rejects_wrong_2740_speaker(self) -> None:
        source = Path(
            "tools/frida_runtime_probe/translations/"
            "ac4901_exhaustive_native416_zh_dialogue_v1.json"
        )
        document = json.loads(source.read_text(encoding="utf-8"))
        next(row for row in document["translations"] if row["request_id"] == 2740)[
            "speaker_zh"
        ] = "黑江"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.Ac4901AudioAuthorityError, "translation map dimensions differ"
            ):
                MODULE._translation_map(path)


if __name__ == "__main__":
    unittest.main()
