import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_exhaustive_unique_longform import (
    PLAN_SCHEMA,
    decoded_pcm_is_zero,
    ffconcat_quote,
    output_materialization_strategy,
    video_copy_needs_exact_cfr_normalization,
    validate_plan_structure,
    validate_probe,
)

SHA_A = "A" * 64
SHA_B = "B" * 64


def make_plan():
    return {
        "schema": PLAN_SCHEMA,
        "release_id": "ac7002_exhaustive_v1",
        "family": "ac7002",
        "title": "test",
        "content_type": "story",
        "native": {
            "width": 416,
            "height": 232,
            "frame_rate": "30/1",
            "video_codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
        },
        "audio_profile": "no_bgm",
        "authority": [
            {"role": "audit", "path": "C:/audit.json", "sha256": SHA_A}
        ],
        "editions": [{
            "edition": "none",
            "output_filename": "ac7002__none.mp4",
            "sources": [
                {
                    "order": 0,
                    "event": "ac7002_001",
                    "source_identities": ["patch:1"],
                    "chapter_title": "one",
                    "path": "C:/one.mp4",
                    "sha256": SHA_A,
                    "video_frames": 30,
                },
                {
                    "order": 1,
                    "event": "ac7002_002",
                    "source_identities": ["patch:2"],
                    "chapter_title": "two",
                    "path": "C:/two.mp4",
                    "sha256": SHA_B,
                    "video_frames": 60,
                },
            ],
        }],
        "expected_chapter_count": 2,
        "expected_unique_source_count": 2,
        "expected_total_video_frames": 90,
        "human_status": "HUMAN_PLAYBACK_REQUIRED",
        "production_scope": {
            "native_416_only": True,
            "include_mutually_exclusive_outcomes": True,
            "each_unique_source_once": True,
            "single_exhaustive_longform": True,
            "source_media_modified": False,
        },
    }


class ExhaustiveLongformPlanTests(unittest.TestCase):
    def test_accepts_exact_contract(self):
        self.assertEqual(validate_plan_structure(make_plan())["family"], "ac7002")

    def test_rejects_duplicate_semantic_source(self):
        value = make_plan()
        value["editions"][0]["sources"][1]["source_identities"] = ["patch:1"]
        with self.assertRaisesRegex(ValueError, "duplicate semantic"):
            validate_plan_structure(value)

    def test_rejects_duplicate_binary(self):
        value = make_plan()
        value["editions"][0]["sources"][1]["sha256"] = SHA_A
        with self.assertRaisesRegex(ValueError, "duplicate exact"):
            validate_plan_structure(value)

    def test_rejects_count_mismatch(self):
        value = make_plan()
        value["expected_chapter_count"] = 3
        with self.assertRaisesRegex(ValueError, "exactly 3 chapters"):
            validate_plan_structure(value)

    def test_rejects_unsafe_output_filename(self):
        value = make_plan()
        value["editions"][0]["output_filename"] = "../bad.mp4"
        with self.assertRaisesRegex(ValueError, "without directories"):
            validate_plan_structure(value)

    def test_rejects_edition_timeline_drift(self):
        value = make_plan()
        second = {
            **value["editions"][0],
            "edition": "zh",
            "output_filename": "ac7002__zh.mp4",
            "sources": [dict(row) for row in value["editions"][0]["sources"]],
        }
        second["sources"][1]["source_identities"] = ["patch:3"]
        value["editions"].append(second)
        with self.assertRaisesRegex(ValueError, "semantic timeline"):
            validate_plan_structure(value)

    def test_accepts_parent_cut_trim_contract(self):
        value = make_plan()
        value["editions"][0]["sources"][0]["input_video_frames"] = 31
        self.assertEqual(
            validate_plan_structure(value)["editions"][0]["sources"][0]["video_frames"],
            30,
        )

    def test_rejects_trim_that_extends_input(self):
        value = make_plan()
        value["editions"][0]["sources"][0]["input_video_frames"] = 29
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            validate_plan_structure(value)

    def test_validate_probe_accepts_exact_media(self):
        native = make_plan()["native"]
        probe = {"streams": [
            {
                "codec_type": "video", "codec_name": "h264", "width": 416,
                "height": 232, "r_frame_rate": "30/1", "nb_read_frames": "90",
            },
            {
                "codec_type": "audio", "codec_name": "aac",
                "sample_rate": "48000", "channels": 2,
            },
        ]}
        result = validate_probe(probe, native, 90, "test")
        self.assertTrue(result["checks"]["video_frames"])

    def test_decoded_pcm_zero_guard(self):
        self.assertTrue(decoded_pcm_is_zero(b"\x00" * 32))
        self.assertFalse(decoded_pcm_is_zero(b""))
        self.assertFalse(decoded_pcm_is_zero(b"\x00\x01\x00"))

    def test_ffconcat_quote_normalizes_windows_path(self):
        self.assertEqual(ffconcat_quote(Path("C:/a b.mp4")), "'C:/a b.mp4'")

    def test_single_chapter_uses_exact_copy(self):
        self.assertEqual(
            output_materialization_strategy([Path("C:/one.mp4")]),
            "exact_single_chapter_copy",
        )

    def test_multiple_chapters_use_concat(self):
        self.assertEqual(
            output_materialization_strategy([
                Path("C:/one.mp4"), Path("C:/two.mp4")
            ]),
            "split_video_copy_audio_once_bounded",
        )

    def test_complete_copy_one_frame_short_requires_exact_cfr_normalization(self):
        probe = {"streams": [{
            "codec_type": "video", "codec_name": "h264",
            "r_frame_rate": "30/1", "nb_read_frames": "5130",
            "start_time": "0.000000", "duration": "170.966667",
        }]}
        self.assertTrue(video_copy_needs_exact_cfr_normalization(probe, 5130))

    def test_exact_copy_does_not_require_exact_cfr_normalization(self):
        probe = {"streams": [{
            "codec_type": "video", "codec_name": "h264",
            "r_frame_rate": "30/1", "nb_read_frames": "5130",
            "start_time": "0.000000", "duration": "171.000000",
        }]}
        self.assertFalse(video_copy_needs_exact_cfr_normalization(probe, 5130))

    def test_incomplete_copy_is_not_silently_normalized(self):
        probe = {"streams": [{
            "codec_type": "video", "codec_name": "h264",
            "r_frame_rate": "30/1", "nb_read_frames": "5129",
            "start_time": "0.000000", "duration": "170.966667",
        }]}
        self.assertFalse(video_copy_needs_exact_cfr_normalization(probe, 5130))

    def test_silent_single_chapter_requires_synthetic_audio(self):
        self.assertEqual(
            output_materialization_strategy(
                [Path("C:/one.mp4")], "synthesize_silence"
            ),
            "split_video_copy_synthetic_silence_bounded",
        )

    def test_accepts_silent_edition_contract(self):
        value = make_plan()
        value["editions"][0]["audio_assembly"] = "synthesize_silence"
        normalized = validate_plan_structure(value)
        self.assertEqual(
            normalized["editions"][0]["audio_assembly"],
            "synthesize_silence",
        )

    def test_accepts_one_suffix_free_material_edition(self):
        value = make_plan()
        value["content_type"] = "material"
        value["audio_profile"] = "silent"
        value["editions"][0].update({
            "edition": "material",
            "output_filename": "ac7002_material.mp4",
            "audio_assembly": "synthesize_silence",
        })
        self.assertEqual(
            validate_plan_structure(value)["editions"][0]["edition"],
            "material",
        )

    def test_rejects_language_suffix_on_material(self):
        value = make_plan()
        value["content_type"] = "material"
        value["audio_profile"] = "silent"
        value["editions"][0].update({
            "edition": "material",
            "audio_assembly": "synthesize_silence",
        })
        with self.assertRaisesRegex(ValueError, "language suffix"):
            validate_plan_structure(value)

    def test_empty_chapter_list_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            output_materialization_strategy([])

    def test_exact_timeline_accepts_bounded_audio(self):
        native = make_plan()["native"]
        probe = {"streams": [
            {
                "codec_type": "video", "codec_name": "h264", "width": 416,
                "height": 232, "r_frame_rate": "30/1", "nb_read_frames": "90",
                "start_time": "0.000000", "duration": "3.000000",
            },
            {
                "codec_type": "audio", "codec_name": "aac",
                "sample_rate": "48000", "channels": 2,
                "start_time": "0.000000", "duration": "2.999667",
            },
        ], "format": {"duration": "3.000000"}}
        result = validate_probe(probe, native, 90, "test", exact_timeline=True)
        self.assertTrue(result["checks"]["format_duration_within_0_01_frame"])
        self.assertTrue(result["checks"]["video_duration_within_0_01_frame"])

    def test_exact_timeline_rejects_aac_priming_shift(self):
        native = make_plan()["native"]
        probe = {"streams": [
            {
                "codec_type": "video", "codec_name": "h264", "width": 416,
                "height": 232, "r_frame_rate": "30/1", "nb_read_frames": "90",
                "start_time": "0.021029", "duration": "3.000000",
            },
            {
                "codec_type": "audio", "codec_name": "aac",
                "sample_rate": "48000", "channels": 2,
                "start_time": "0.000000", "duration": "3.021333",
            },
        ], "format": {"duration": "3.021333"}}
        with self.assertRaisesRegex(ValueError, "media contract failed"):
            validate_probe(probe, native, 90, "shifted", exact_timeline=True)


if __name__ == "__main__":
    unittest.main()
