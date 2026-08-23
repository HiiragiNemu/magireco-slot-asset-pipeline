import json
import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_ac7205_exhaustive_authoritative_longform import (
    EDITORIAL_ORDER,
    EXPECTED_FRAMES,
    EXPECTED_OVERLAY_OCCURRENCES,
    EXPECTED_PRIMARY_OCCURRENCES,
    NATIVE416_EVENTS,
    Ac7205ExhaustiveError,
    event_code_map,
    event_layer_rows,
    renderer_translation_map,
    translation_rows_by_request,
)


def translations():
    return {
        "schema": "magireco-reviewed-story-zh-dialogue-map-v1",
        "scope": "ac7205_exhaustive_native416_runtime_bound_dialogue",
        "translations": [
            {"request_id": request, "ja": f"ja-{request}", "zh": f"zh-{request}"}
            for request in (8310, 8311, 8312, 8313, 8314)
        ],
    }


class Ac7205ExhaustiveTests(unittest.TestCase):
    def test_editorial_order_is_native416_bijection(self):
        self.assertEqual(len(EDITORIAL_ORDER), 21)
        self.assertEqual(set(EDITORIAL_ORDER), set(NATIVE416_EVENTS))
        self.assertNotIn("ac7205_018", EDITORIAL_ORDER)
        self.assertEqual(EXPECTED_FRAMES, 3827)
        self.assertEqual(EXPECTED_PRIMARY_OCCURRENCES, 42)
        self.assertEqual(EXPECTED_OVERLAY_OCCURRENCES, 10)

    def test_runtime_event_code_map_requires_all_22_events(self):
        events = [*NATIVE416_EVENTS, "ac7205_018"]
        runtime = {
            "requested_events": {
                event: f"0x{index:016x}" for index, event in enumerate(events, 1)
            }
        }
        self.assertEqual(set(event_code_map(runtime)), set(events))
        runtime["requested_events"].pop("ac7205_018")
        with self.assertRaises(Ac7205ExhaustiveError):
            event_code_map(runtime)

    def test_primary_and_overlay_rows_keep_separate_roles(self):
        plans = [
            {
                "event": "ac7205_001", "normalized_start_frame": 0,
                "visual_role": "primary_unique_visual_content",
                "canonical_media_paths": ["C:/a.mp4", "C:/b.mp4"],
            },
            {
                "event": "ac7205_001", "normalized_start_frame": 0,
                "visual_role": "runtime_looping_frame_overlay",
                "canonical_media_paths": ["C:/overlay.mp4"],
            },
        ]
        sources = {
            "c:\\a.mp4": {"path": "C:/a.mp4", "dgm_name": "a", "sha256": "A", "source_frame_count": 28, "source_identity_disposition": "CANONICAL_SOURCE_IDENTITY"},
            "c:\\b.mp4": {"path": "C:/b.mp4", "dgm_name": "b", "sha256": "B", "source_frame_count": 30, "source_identity_disposition": "CANONICAL_SOURCE_IDENTITY"},
            "c:\\overlay.mp4": {"path": "C:/overlay.mp4", "dgm_name": "overlay", "sha256": "C", "source_frame_count": 625, "source_identity_disposition": "CANONICAL_SOURCE_IDENTITY"},
        }
        primary, overlays, frames = event_layer_rows("ac7205_001", plans, sources)
        self.assertEqual(frames, 58)
        self.assertEqual([(row["event_start_frame"], row["event_end_frame_exclusive"]) for row in primary], [(0, 28), (28, 58)])
        self.assertEqual(overlays[0]["dgm_role"], "loop_screen_overlay")
        self.assertEqual(overlays[0]["blend_mode"], "screen")

    def test_renderer_translation_projection_has_five_exact_keys(self):
        resolved = translation_rows_by_request(translations())
        projected = renderer_translation_map(resolved)
        self.assertEqual(len(projected["translations"]), 5)
        self.assertTrue(all(set(row) == {"ja", "zh", "status"} for row in projected["translations"]))
        self.assertTrue(all(row["status"] == "machine_draft_pending_owner" for row in projected["translations"]))

    def test_v150_checkpoint_keeps_one_longform_group_and_defers_native512(self):
        checkpoint = json.loads(
            (
                Path(__file__).resolve().parent
                / "tools"
                / "frida_runtime_probe"
                / "series_proposals"
                / "ac7205_exhaustive_authoritative_longform_v150_20260824.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(checkpoint["status"], "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED")
        self.assertEqual(checkpoint["review_group_count"], 1)
        self.assertEqual(checkpoint["edition_file_count"], 3)
        self.assertEqual(checkpoint["included_native416_event_count"], 21)
        self.assertEqual(checkpoint["deferred_native512_events"], ["ac7205_018"])
        self.assertEqual(checkpoint["complete_presentation_exact_duplicate_count"], 0)
        self.assertEqual(checkpoint["presentation_frames"], EXPECTED_FRAMES)
        self.assertEqual(checkpoint["excluded_bgm_occurrences"], 3)
        self.assertTrue(checkpoint["human_playback_required"])
        self.assertFalse(checkpoint["publication_approved"])


if __name__ == "__main__":
    unittest.main()
