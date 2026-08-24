import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.frida_runtime_probe import build_ac4903_exhaustive_authoritative_longform as target
from tools.frida_runtime_probe import resolve_ac4903_exhaustive_authority as resolver


def authority_fixture() -> dict:
    frames = {
        "ac4903_001": 90, "ac4903_002": 120, "ac4903_003": 165,
        "ac4903_004": 224, "ac4903_005": 120, "ac4903_006": 150,
        "ac4903_007": 165, "ac4903_008": 180, "ac4903_009": 480,
        "ac4903_010": 480, "ac4903_011": 480, "ac4903_012": 480,
        "ac4903_013": 480, "ac4903_015": 260, "ac4903_016": 165,
        "ac4903_018": 165,
    }
    cue_events = set(resolver.EDITORIAL_ORDER[:12])
    manifests = {}
    for event in resolver.EDITORIAL_ORDER:
        manifests[event] = {
            "presentation_frames": frames[event],
            "subtitles": ([{
                "start_frame": 1,
                "end_ms": 1000,
                "voice_request_id": 1,
                "ja": "日本語",
                "zh": "中文",
            }] if event in cue_events else []),
        }
    return {
        "schema": "magireco-ac4903-exhaustive-native416-authority-v1",
        "status": "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
        "editorial_order": list(resolver.EDITORIAL_ORDER),
        "event_manifests": manifests,
        "summary": {
            "dirinfo_routes": 22,
            "unique_complete_event_presentations": 16,
            "authored_movie_layer_occurrences": 41,
            "loadable_movie_layer_occurrences": 39,
            "unique_loadable_cri_identities": 35,
            "code_unreachable_alias_occurrences": 2,
            "retained_no_bgm_audio_occurrences": 28,
            "excluded_bgm_occurrences": 7,
            "subtitle_cues": 12,
            "total_frames": 4204,
        },
        "assertions": {
            "all_22_dirinfo_routes_covered": True,
            "all_16_complete_event_presentations_once": True,
            "no_exact_duplicate_complete_presentations": True,
            "all_35_loadable_cri_sources_bound": True,
            "all_cri_sources_have_exact_color_alpha_streams": True,
            "renderer_state_1_and_3_code_closed": True,
            "child_local_only_timing_occurrences": 0,
            "P16_P17_P18_references": 0,
            "machine_vision_used_as_authority": False,
        },
    }


class BuildAc4903ExhaustiveLongformTests(unittest.TestCase):
    def test_validate_authority_accepts_exact_contract(self) -> None:
        value = authority_fixture()
        target.validate_authority(value)
        value["summary"]["loadable_movie_layer_occurrences"] = 38
        with self.assertRaises(target.Ac4903BuildError):
            target.validate_authority(value)

    def test_additive_filter_uses_alpha_composite_over_black_then_addition(self) -> None:
        row = {
            "source": {"frame_count": 60, "width": 416, "height": 232},
            "event_start_frame": 0,
            "effective_renderer_state": 3,
        }
        parts, label = target._layer_filters(0, 0, row, 480, "base0")
        text = ";".join(parts)
        self.assertIn("alphamerge", text)
        self.assertIn("overlay=0:0", text)
        self.assertIn("blend=all_mode=addition", text)
        self.assertEqual(label, "base1")

    def test_component_layer_scales_only_inside_native_scene_canvas(self) -> None:
        row = {
            "source": {"frame_count": 60, "width": 256, "height": 144},
            "event_start_frame": 0,
            "effective_renderer_state": 1,
        }
        parts, _ = target._layer_filters(0, 0, row, 260, "base0")
        self.assertIn("scale=416:232:flags=lanczos", ";".join(parts))

    def test_global_subtitles_share_the_exact_4204_frame_timeline(self) -> None:
        rows = target.global_subtitle_cues(authority_fixture(), "zh")
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0]["start_ms"], 33)
        self.assertGreater(rows[-1]["start_ms"], rows[0]["start_ms"])

    def test_validate_probe_requires_native_av_and_sixteen_chapters(self) -> None:
        value = {
            "streams": [
                {
                    "codec_type": "video", "codec_name": "h264", "width": 416,
                    "height": 232, "avg_frame_rate": "30/1", "nb_read_frames": "4204",
                },
                {
                    "codec_type": "audio", "codec_name": "aac",
                    "sample_rate": "48000", "channels": 2,
                },
            ],
            "chapters": [{} for _ in range(16)],
        }
        self.assertTrue(all(target.validate_probe(value, chapters=16).values()))
        value["streams"][0]["width"] = 512
        with self.assertRaises(target.Ac4903BuildError):
            target.validate_probe(value, chapters=16)

    def test_production_verification_binds_each_edition_sha256(self) -> None:
        probe_value = {
            "format": {"duration": "140.133333"},
            "streams": [
                {
                    "codec_type": "video", "codec_name": "h264", "width": 416,
                    "height": 232, "avg_frame_rate": "30/1", "nb_read_frames": "4204",
                },
                {
                    "codec_type": "audio", "codec_name": "aac",
                    "sample_rate": "48000", "channels": 2,
                },
            ],
            "chapters": [{} for _ in range(16)],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_dir = root / "manifests"
            manifest_dir.mkdir()
            (manifest_dir / "PRODUCTION_MANIFEST.json").write_text(
                json.dumps({
                    "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                    "content_group_count": 1,
                    "edition_file_count": 3,
                    "ordered_events": [
                        "ac4903_001", "ac4903_016", "ac4903_018", "ac4903_015"
                    ],
                }),
                encoding="utf-8",
            )
            expected = {}
            for edition, folder in target.EDITIONS.items():
                media_dir = root / "HUMAN_REVIEW" / folder / "story"
                media_dir.mkdir(parents=True, exist_ok=True)
                path = media_dir / f"ac4903_{target.TITLE}_严格无BGM__{edition}.mp4"
                path.write_bytes((edition * 32).encode("ascii"))
                expected[edition] = target.file_sha256(path)
            with mock.patch.object(target, "probe", return_value=probe_value):
                report = target.verify_production(root, "ffprobe", write_report=False)
            self.assertEqual(
                {row["edition"]: row["sha256"] for row in report["media"]}, expected
            )


if __name__ == "__main__":
    unittest.main()
