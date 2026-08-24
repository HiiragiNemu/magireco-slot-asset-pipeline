import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac0915_exhaustive_authoritative_longform as m


class Ac0915ExhaustiveLongformTests(unittest.TestCase):
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
            "schema": "magireco-ac0915-dirinfo-route-and-complete-presentation-dedup-authority-v1",
            "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
            "summary": {
                "dirinfo_routes": 42,
                "dirinfo_event_occurrences": 177,
                "source_events": 21,
                "canonical_presentations": 18,
                "identical_complete_presentation_aliases": 3,
                "unique_loadable_cri_sources_covered": 42,
                "duplicate_free_longform_frames": 3933,
                "duplicate_free_longform_seconds": 131.1,
            },
            "editorial_timeline": timeline,
            "dedup_contract": {
                "identical_alias_events": {
                    "ac0915_008": "ac0915_003",
                    "ac0915_019": "ac0915_005",
                    "ac0915_021": "ac0915_007",
                }
            },
        }
        visual = {
            "schema": "magireco-ac0915-output-projection-authority-v1",
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "summary": {"events": 21, "unique_loadable_cri_sources": 42},
        }
        audio = {
            "schema": "magireco-ac0915-native416-event-audio-runtime-and-sound-bus-authority-v1",
            "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
            "summary": {
                "retained_audio_occurrences": 40,
                "excluded_bgm_occurrences": 1,
                "subtitle_cue_occurrences": 18,
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
            visual_frames = m.EXPECTED_VISUAL_FRAMES[event]
            count = 3 if event_index < 10 else 2
            layers = []
            for _ in range(count):
                source_index = layer_serial if layer_serial < 42 else 0
                layers.append(
                    {
                        "event_start_frame": 0,
                        "event_end_frame_inclusive": visual_frames - 1,
                        "effective_renderer_state": 3 if layer_serial >= 44 else 1,
                        "output_rect_xywh": [0, 0, 416, 232],
                        "frame_policy": {
                            "source_frame_count": visual_frames,
                            "consumed_source_frames": visual_frames,
                        },
                        "source": {
                            "official_name": f"source_{source_index:03d}",
                            "path": f"source_{source_index:03d}.usm",
                            "sha256": "0" * 64,
                            "width": 416,
                            "height": 232,
                            "frame_count": visual_frames,
                        },
                    }
                )
                layer_serial += 1
            events.append(
                {
                    "event": event,
                    "presentation_frame_count": frames,
                    "layers_in_render_pass_order_under_to_top": layers,
                    "unreachable_layers_excluded_by_exact_loader": [
                        {"source_name": f"missing_{index}"} for index in range(6)
                    ]
                    if event_index == 0
                    else [],
                    "non_movie_text_z2d_nodes": [],
                    "runtime_symbolic_nodes": [],
                }
            )
        for alias in ("ac0915_008", "ac0915_019", "ac0915_021"):
            events.append({"event": alias})

        retained = []
        for event in order:
            if event == "ac0915_009":
                continue
            retained.append(
                {
                    "event": event,
                    "volume_bus": "SE",
                    "start_ms": 0,
                    "official_source": {"path": "fixture.ogg", "size_bytes": 1},
                }
            )
        for index in range(17):
            retained.append(
                {
                    "event": order[0],
                    "volume_bus": "VOICE",
                    "start_ms": index,
                    "official_source": {"path": "fixture.ogg", "size_bytes": 1},
                }
            )
        subtitles = []
        for event in order[:15]:
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
        with self.assertRaisesRegex(m.Ac0915LongformBuildError, "editorial order differs"):
            m.validate_authorities(route, visual, audio)

    def test_builds_exact_canonical_production_dimensions(self):
        order, visual, audio = self._production_payloads()
        manifests = m.build_event_manifests(order, visual, audio)
        self.assertEqual(len(manifests), 18)
        self.assertEqual(sum(len(row["layers"]) for row in manifests.values()), 46)
        self.assertEqual(sum(len(row["retained_audio"]) for row in manifests.values()), 34)
        self.assertEqual(manifests["ac0915_009"]["retained_audio"], [])
        self.assertEqual(sum(len(row["subtitles"]) for row in manifests.values()), 15)
        self.assertEqual(manifests["ac0915_011"]["visual_frames"], 96)
        self.assertEqual(manifests["ac0915_011"]["presentation_frames"], 100)
        self.assertEqual(len(m.global_subtitle_cues(order, manifests, "zh")), 15)

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
            with self.assertRaisesRegex(m.Ac0915LongformBuildError, "IDA runtime-choice evidence differs"):
                m.validate_ida_choice_evidence(path)


if __name__ == "__main__":
    unittest.main()
