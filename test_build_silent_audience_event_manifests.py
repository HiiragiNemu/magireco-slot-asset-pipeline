from __future__ import annotations

import unittest

from tools.frida_runtime_probe.build_silent_audience_event_manifests import (
    zero_audio_matches,
)


class SilentAudienceEventManifestTests(unittest.TestCase):
    def test_zero_audio_evidence_uses_exact_event_fields(self) -> None:
        counts = zero_audio_matches(
            event="ac4002_001",
            direct_rows=[
                {
                    "root": "ac4002",
                    "primary_animation": "ac4002_099",
                }
            ],
            child_rows=[{"event_name": "ac4002_099"}],
            subtitle_rows=[{"event_name": "ac4002_099"}],
        )
        self.assertEqual(
            counts,
            {
                "direct_parent_audio_matches": 0,
                "child_audio_matches": 0,
                "subtitle_matches": 0,
            },
        )

    def test_any_exact_audio_or_subtitle_match_fails_closed(self) -> None:
        for source in ("direct", "child", "subtitle"):
            with self.subTest(source=source):
                direct = []
                child = []
                subtitles = []
                if source == "direct":
                    direct.append({"primary_animation": "ac4002_001"})
                elif source == "child":
                    child.append({"event_name": "ac4002_001"})
                else:
                    subtitles.append({"event_name": "ac4002_001"})
                with self.assertRaisesRegex(ValueError, "has matches"):
                    zero_audio_matches(
                        event="ac4002_001",
                        direct_rows=direct,
                        child_rows=child,
                        subtitle_rows=subtitles,
                    )


if __name__ == "__main__":
    unittest.main()
