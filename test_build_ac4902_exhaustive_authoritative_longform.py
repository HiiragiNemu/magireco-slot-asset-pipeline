import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac4902_exhaustive_authoritative_longform as m


class Ac4902ExhaustiveLongformTests(unittest.TestCase):
    @staticmethod
    def _authority_headers():
        cursor = 0
        timeline = []
        for event, frames in m.EXPECTED_PRESENTATION_FRAMES.items():
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
            "schema": "magireco-ac4902-dirinfo-route-and-complete-presentation-dedup-authority-v1",
            "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
            "summary": {
                "dirinfo_routes": 70,
                "dirinfo_event_occurrences": 260,
                "source_events": 64,
                "canonical_presentations": 48,
                "identical_complete_presentation_aliases": 16,
                "unique_loadable_cri_sources_covered": 56,
                "duplicate_free_longform_frames": 19079,
                "duplicate_free_longform_seconds": 19079 / 30,
            },
            "editorial_timeline": timeline,
            "dedup_contract": {
                "identical_alias_events": m.EXPECTED_ALIASES
            },
        }
        visual = {
            "schema": "magireco-ac4902-output-projection-authority-v1",
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "summary": {"events": 64, "unique_loadable_cri_sources": 56},
        }
        audio = {
            "schema": "magireco-ac4902-native416-event-audio-runtime-and-sound-bus-authority-v1",
            "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
            "summary": {
                "retained_audio_occurrences": 148,
                "excluded_bgm_occurrences": 1,
                "subtitle_cue_occurrences": 56,
            },
        }
        return route, visual, audio

    @staticmethod
    def _production_payloads():
        order = list(m.EXPECTED_PRESENTATION_FRAMES)
        events = []
        layer_serial = 0
        for event_index, event in enumerate(order):
            frames = m.EXPECTED_PRESENTATION_FRAMES[event]
            event_visual_frames = m.EXPECTED_VISUAL_FRAMES[event]
            movie_frames = m.EXPECTED_MOVIE_LAYER_FRAMES[event]
            count = 3 if event_index < 39 else 2
            layers = []
            for _ in range(count):
                source_index = layer_serial % 56
                layers.append(
                    {
                        "event_start_frame": 0,
                        "event_end_frame_inclusive": movie_frames - 1,
                        "effective_renderer_state": 3 if layer_serial >= 133 else 1,
                        "output_rect_xywh": [0, 0, 416, 232],
                        "frame_policy": {
                            "source_frame_count": movie_frames,
                            "consumed_source_frames": movie_frames,
                        },
                        "source": {
                            "official_name": f"source_{source_index:03d}",
                            "path": f"source_{source_index:03d}.usm",
                            "sha256": "0" * 64,
                            "width": 416,
                            "height": 232,
                            "frame_count": movie_frames,
                        },
                    }
                )
                layer_serial += 1
            events.append(
                {
                    "event": event,
                    "presentation_frame_count": event_visual_frames,
                    "layers_in_render_pass_order_under_to_top": layers,
                    "unreachable_layers_excluded_by_exact_loader": [],
                    "non_movie_text_z2d_nodes": [],
                    "runtime_symbolic_nodes": [],
                }
            )
        for alias in m.EXPECTED_ALIASES:
            events.append({"event": alias})

        retained = []
        for event in order:
            if event == "ac4902_022":
                continue
            retained.append(
                {
                    "event": event,
                    "volume_bus": "SE",
                    "start_ms": 0,
                    "official_source": {"path": "fixture.ogg", "size_bytes": 1},
                }
            )
        for index in range(28):
            retained.append(
                {
                    "event": order[0],
                    "volume_bus": "SE",
                    "start_ms": index,
                    "official_source": {"path": "fixture.ogg", "size_bytes": 1},
                }
            )
        for index in range(40):
            retained.append(
                {
                    "event": order[0],
                    "volume_bus": "VOICE",
                    "start_ms": index,
                    "official_source": {"path": "fixture.ogg", "size_bytes": 1},
                }
            )
        subtitles = []
        subtitle_events = [event for event in order if event != "ac4902_022"][:40]
        for event in subtitle_events:
            subtitles.append(
                {
                    "event": event,
                    "voice_request_id": 1,
                    "start_frame": 0,
                    "end_ms": 100,
                    "ja": "JA",
                    "zh": "ZH",
                    "translation_status": "fixture",
                }
            )
        return order, {"events": events}, {
            "retained_audio_rows": retained,
            "subtitle_cues": subtitles,
            "event_presentations": [
                {
                    "event": event,
                    "final_presentation_frames": m.EXPECTED_PRESENTATION_FRAMES[event],
                }
                for event in order
            ],
        }

    def test_accepts_exact_authority_dimensions_and_order(self):
        route, visual, audio = self._authority_headers()
        self.assertEqual(
            m.validate_authorities(route, visual, audio),
            list(m.EXPECTED_PRESENTATION_FRAMES),
        )

    def test_rejects_editorial_timeline_drift(self):
        route, visual, audio = self._authority_headers()
        route["editorial_timeline"][3]["duration_frames"] -= 1
        with self.assertRaisesRegex(m.Ac4902LongformBuildError, "editorial order differs"):
            m.validate_authorities(route, visual, audio)

    def test_builds_exact_canonical_production_dimensions(self):
        order, visual, audio = self._production_payloads()
        manifests = m.build_event_manifests(order, visual, audio)
        self.assertEqual(len(manifests), 48)
        self.assertEqual(sum(len(row["layers"]) for row in manifests.values()), 135)
        self.assertEqual(sum(len(row["retained_audio"]) for row in manifests.values()), 115)
        self.assertEqual(manifests["ac4902_022"]["retained_audio"], [])
        self.assertEqual(sum(len(row["subtitles"]) for row in manifests.values()), 40)
        self.assertEqual(manifests["ac4902_002"]["visual_frames"], 89)
        self.assertEqual(manifests["ac4902_002"]["event_global_visual_frames"], 321)
        self.assertEqual(manifests["ac4902_004"]["presentation_frames"], 194)
        self.assertEqual(len(m.global_subtitle_cues(order, manifests, "zh")), 40)

    def test_normal_and_additive_filter_contracts_are_distinct(self):
        row = {
            "event_start_frame": 10,
            "event_end_frame_inclusive": 19,
            "effective_renderer_state": 1,
            "output_rect_xywh": [0, 0, 416, 232],
            "frame_policy": {"source_frame_count": 10, "consumed_source_frames": 10},
            "source": {"frame_count": 10, "width": 416, "height": 232},
        }
        normal, _ = m.layer_filter_parts(0, 0, row, "base0", 30)
        self.assertIn("overlay=0:0", ";".join(normal))
        self.assertNotIn("all_mode=addition", ";".join(normal))
        additive_row = copy.deepcopy(row)
        additive_row["effective_renderer_state"] = 3
        additive, _ = m.layer_filter_parts(0, 0, additive_row, "base0", 30)
        text = ";".join(additive)
        self.assertIn("premultiply_dynamic=inplace=1", text)
        self.assertIn("blend=all_mode=addition", text)
        self.assertIn("tpad=start=10:stop=10", text)

    def test_event_output_is_bounded_by_exact_frame_grid_and_duration(self):
        self.assertEqual(
            m.event_output_boundary_args(194),
            ["-frames:v", "194", "-t", "6.466666667"],
        )
        with self.assertRaisesRegex(m.Ac4902LongformBuildError, "not positive"):
            m.event_output_boundary_args(0)

    def test_each_dual_stream_video_input_uses_one_decoder_thread(self):
        self.assertEqual(
            m.video_input_args(Path("fixture.usm")),
            ["-threads", "1", "-i", "fixture.usm"],
        )

    def test_event_filter_and_encoder_thread_pools_are_bounded(self):
        self.assertEqual(m.event_filter_thread_args(), ["-filter_complex_threads", "1"])
        self.assertEqual(m.event_encoder_thread_args(), ["-threads", "4"])

    def test_failed_partial_mp4_is_preserved_outside_media_scans(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            source = root / "intermediate" / "events" / "ac4902_060.failed_deadlock.mp4"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"partial")
            archived = m.archive_failed_attempts(root)
            self.assertFalse(source.exists())
            target = root / archived[0]["archived_relative_path"]
            self.assertEqual(target.name, source.name + ".partial.bin")
            self.assertEqual(target.read_bytes(), b"partial")
            self.assertEqual(archived[0]["media_disposition"], "FAILED_PARTIAL_NOT_REVIEW_MEDIA")

    def test_ida_evidence_binds_runtime_choices_not_video_identities(self):
        code = "C_DirectionControllerMainDir::fnPlayCHO\n"
        code += "g_usMainDirKind == 10012\n"
        code += "ac8050_uwa_impact_ef\nMSTCOMCBK() + 62432\n"
        for node, (offset, variable) in m.SYMBOLIC_COUNTER_NODES.items():
            code += f"MSTCOMCBK() + {offset}\n\"{node}\", {variable}\n"
        with tempfile.TemporaryDirectory() as value:
            path = Path(value) / "ida.json"
            path.write_text(json.dumps({"code": code}), encoding="utf-8")
            result = m.validate_ida_choice_evidence(path)
            self.assertEqual(result["main_direction_kind"], 10012)
            self.assertIn("ac8050_tx_count_uwa_suji_1000", result["choice_nodes"])
            path.write_text(json.dumps({"code": code.replace("g_usMainDirKind == 10012", "")}), encoding="utf-8")
            with self.assertRaisesRegex(m.Ac4902LongformBuildError, "IDA runtime-choice evidence differs"):
                m.validate_ida_choice_evidence(path)


if __name__ == "__main__":
    unittest.main()
