from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import (
    build_ac0917_exhaustive_authoritative_longform as MODULE,
)


class Ac0917ExhaustiveLongformTests(unittest.TestCase):
    def _authority_headers(self):
        cursor = 0
        timeline = []
        for event, frames in MODULE.EXPECTED_PRESENTATION_FRAMES.items():
            timeline.append(
                {
                    "event": event,
                    "start_frame": cursor,
                    "end_frame_exclusive": cursor + frames,
                    "duration_frames": frames,
                }
            )
            cursor += frames
        route = {
            "schema": "magireco-ac0917-dirinfo-route-and-complete-presentation-dedup-authority-v2",
            "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
            "summary": {
                "dirinfo_routes": 22,
                "dirinfo_event_occurrences": 75,
                "source_events": 12,
                "canonical_presentations": 12,
                "identical_complete_presentation_aliases": 0,
                "visible_unique_cri_sources_covered": 20,
                "duplicate_free_longform_frames": 3136,
                "duplicate_free_longform_seconds": 3136 / 30,
            },
            "editorial_timeline": timeline,
            "dedup_contract": {"identical_alias_events": {}},
        }
        visual = {
            "schema": "magireco-ac0917-output-projection-authority-v1",
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "summary": {"events": 12, "unique_loadable_cri_sources": 20},
        }
        loop = {
            "schema": "magireco-ac0917-parent-clock-z2d-loop-authority-v1",
            "status": "PASS_READY_FOR_LOOP_AWARE_ROUTE_DEDUP_AND_LONGFORM_RENDER",
            "inputs": {"output_projection": {"sha256": "V"}},
            "summary": {
                "events": 12,
                "movie_parents": 13,
                "loop_extension_frames": 207,
                "scheduled_movie_frame_occurrences": 2711,
                "render_segments": 31,
                "unique_sources": 20,
                "parent_clock_excluded_occurrences": 3,
            },
        }
        audio = {
            "schema": "magireco-ac0917-native416-event-audio-runtime-and-sound-bus-authority-v1",
            "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
            "summary": {
                "retained_audio_occurrences": 25,
                "retained_se_occurrences": 13,
                "retained_voice_occurrences": 12,
                "excluded_bgm_occurrences": 3,
                "subtitle_page_cue_occurrences": 18,
                "rendered_presentation_frames_before_dedup": 3136,
                "final_frame_hold_frames": 229,
            },
        }
        return route, visual, loop, audio

    def test_frozen_product_dimensions(self) -> None:
        self.assertEqual(3136, MODULE.EXPECTED_FRAMES)
        self.assertEqual(12, MODULE.EXPECTED_EVENTS)
        self.assertEqual(22, MODULE.EXPECTED_LAYER_OCCURRENCES)
        self.assertEqual(31, MODULE.EXPECTED_RENDER_SEGMENTS)
        self.assertEqual(2711, MODULE.EXPECTED_SCHEDULED_MOVIE_FRAMES)
        self.assertEqual(25, MODULE.EXPECTED_RETAINED_AUDIO)
        self.assertEqual(18, MODULE.EXPECTED_SUBTITLES)

    def test_accepts_exact_authority_dimensions_and_order(self) -> None:
        values = self._authority_headers()
        with tempfile.TemporaryDirectory() as temporary:
            visual_path = Path(temporary) / "visual.json"
            visual_path.write_text("fixture", encoding="utf-8")
            with mock.patch.object(MODULE, "file_sha256", return_value="V"):
                order = MODULE.validate_authorities(
                    *values, visual_path=visual_path
                )
        self.assertEqual(list(MODULE.EXPECTED_PRESENTATION_FRAMES), order)

    def test_rejects_route_timeline_drift(self) -> None:
        values = self._authority_headers()
        values[0]["editorial_timeline"][2]["duration_frames"] -= 1
        with tempfile.TemporaryDirectory() as temporary:
            visual_path = Path(temporary) / "visual.json"
            visual_path.write_text("fixture", encoding="utf-8")
            with mock.patch.object(MODULE, "file_sha256", return_value="V"):
                with self.assertRaisesRegex(
                    MODULE.Ac0917LongformBuildError, "editorial order differs"
                ):
                    MODULE.validate_authorities(*values, visual_path=visual_path)

    def test_loop_source_branch_resets_to_authored_source_frame(self) -> None:
        segment = {
            "source_start_frame": 0,
            "source_end_frame_inclusive": 6,
            "event_start_frame": 180,
            "event_end_frame_inclusive": 186,
            "frame_count": 7,
            "source_progression": "increment_1",
        }
        result = MODULE._source_branch_filter(
            "branch", segment, shift_to_event=True
        )
        self.assertIn("trim=start_frame=0:end_frame=7", result)
        self.assertIn("+180/30/TB", result)

    def test_normal_and_additive_loop_filters_are_distinct(self) -> None:
        row = {
            "effective_renderer_state": 1,
            "output_rect_xywh": [0, 0, 416, 232],
            "source": {"width": 416, "height": 232},
            "loop_aware_render_segments": [
                {
                    "source_start_frame": 0,
                    "source_end_frame_inclusive": 9,
                    "event_start_frame": 0,
                    "event_end_frame_inclusive": 9,
                    "frame_count": 10,
                    "source_progression": "increment_1",
                },
                {
                    "source_start_frame": 0,
                    "source_end_frame_inclusive": 4,
                    "event_start_frame": 10,
                    "event_end_frame_inclusive": 14,
                    "frame_count": 5,
                    "source_progression": "increment_1",
                },
            ],
        }
        normal, _ = MODULE.layer_filter_parts(0, 0, row, "base0", 20)
        self.assertIn("split=2", ";".join(normal))
        self.assertIn("overlay=0:0", ";".join(normal))
        additive_row = copy.deepcopy(row)
        additive_row["effective_renderer_state"] = 3
        additive, _ = MODULE.layer_filter_parts(
            0, 0, additive_row, "base0", 20
        )
        self.assertIn("blend=all_mode=addition", ";".join(additive))


if __name__ == "__main__":
    unittest.main()
