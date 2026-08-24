import unittest

from tools.frida_runtime_probe.build_ac0911_exhaustive_authoritative_longform import (
    CHAPTER_TITLES,
    EXPECTED_FRAMES,
    validate_authority,
    validate_probe,
)
from tools.frida_runtime_probe.resolve_ac0911_exhaustive_authority import (
    EDITORIAL_ORDER,
    PRESENTATION_FRAMES,
)


class BuildAc0911ExhaustiveAuthoritativeLongformTest(unittest.TestCase):
    def test_chapter_titles_cover_editorial_order(self):
        self.assertEqual(set(CHAPTER_TITLES), set(EDITORIAL_ORDER))
        self.assertEqual(sum(PRESENTATION_FRAMES[event] for event in EDITORIAL_ORDER), EXPECTED_FRAMES)

    def test_validate_authority_rejects_route_shortfall(self):
        authority = {
            "status": "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
            "route_count": 13,
            "event_container_count": 17,
            "canonical_presentation_count": 17,
            "exact_duplicate_surplus_count": 0,
            "total_frames": EXPECTED_FRAMES,
            "chapters": [{}] * 17,
            "strict_no_bgm": {"excluded_sound_ids": [551, 552, 553]},
            "automatic_assertions": {"ok": True},
        }
        with self.assertRaisesRegex(RuntimeError, "route/event"):
            validate_authority(authority)

    def test_validate_authority_accepts_false_machine_vision_flag(self):
        authority = {
            "status": "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
            "route_count": 14,
            "event_container_count": 17,
            "canonical_presentation_count": 17,
            "exact_duplicate_surplus_count": 0,
            "total_frames": EXPECTED_FRAMES,
            "chapters": [{}] * 17,
            "strict_no_bgm": {"excluded_sound_ids": [551, 552, 553]},
            "automatic_assertions": {
                "all_14_dirinfo_routes_covered": True,
                "all_17_event_containers_covered_once": True,
                "runtime_all_events_same_bounded_capture": True,
                "runtime_process_and_map_guards_passed": True,
                "parent_audio_and_runtime_sound_sets_agree": True,
                "exact_cri_argb_sources_resolved_for_007": True,
                "bgm_551_552_553_excluded": True,
                "P16_P17_P18_not_referenced": True,
                "machine_vision_used_as_authority": False,
            },
        }
        validate_authority(authority)

    def test_validate_probe_accepts_exact_media_contract(self):
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 416, "height": 232,
                 "avg_frame_rate": "30/1", "nb_read_frames": str(EXPECTED_FRAMES)},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
            ],
            "chapters": [{}] * 17,
        }
        self.assertTrue(all(validate_probe(probe).values()))


if __name__ == "__main__":
    unittest.main()
