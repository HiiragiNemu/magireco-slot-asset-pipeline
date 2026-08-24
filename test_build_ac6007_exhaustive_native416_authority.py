import unittest

from tools.frida_runtime_probe import build_ac6007_exhaustive_native416_authority as m


class Ac6007ExhaustiveNative416AuthorityTests(unittest.TestCase):
    def test_editorial_order_covers_each_event_once(self):
        self.assertEqual(set(m.EDITORIAL_ORDER), set(m.EVENTS))
        self.assertEqual(len(m.EDITORIAL_ORDER), len(set(m.EDITORIAL_ORDER)))
        self.assertEqual(sum(m.EXPECTED_PRESENTATION_FRAMES.values()), m.EXPECTED_TOTAL_FRAMES)

    def test_route_union_covers_all_events(self):
        union = {event for route in m.EXPECTED_ROUTES.values() for event in route}
        self.assertEqual(union, set(m.EVENTS))
        self.assertEqual(len(m.EXPECTED_ROUTES), 5)

    def test_event_one_clips_only_generic_common_intro_tail(self):
        frames, policy = m.content_end_frame(
            "ac6007_001",
            code_presentation_frames=227,
            visual_end_frame=203,
            retained_audio=[
                {"request_id": 1034, "sound_id": 4010, "start_ms": 0, "duration_ms": 10000},
                {"request_id": 2192, "sound_id": 10000, "start_ms": 0, "duration_ms": 7566},
            ],
            subtitles=[],
        )
        self.assertEqual(frames, 227)
        self.assertEqual(policy["clipped_request_id"], 1034)

    def test_other_events_hold_until_retained_audio_end(self):
        frames, policy = m.content_end_frame(
            "ac6007_002",
            code_presentation_frames=120,
            visual_end_frame=103,
            retained_audio=[{"start_ms": 0, "duration_ms": 10042}],
            subtitles=[],
        )
        self.assertEqual(frames, 302)
        self.assertEqual(policy["mode"], "hold_final_composited_frame_until_last_retained_se_voice_or_subtitle_end")


if __name__ == "__main__":
    unittest.main()
