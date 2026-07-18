from __future__ import annotations

import copy
import unittest

from tools.frida_runtime_probe.independent_release_contract import (
    BUILD_READY_SCHEMA,
    BUILD_READY_STATUS,
    RELEASE_CONTRACT_SCHEMA,
    RELEASE_PROFILE,
    build_build_ready_marker,
    canonical_sha256,
    release_contract,
    validate_build_ready_marker,
    validate_release_contract,
)


def valid_artifacts() -> dict[str, dict[str, str]]:
    return {
        "video": {"path": "D:/release/scene.mp4", "sha256": "A" * 64},
        "subtitles": {"path": "D:/release/scene.zh.srt", "sha256": "B" * 64},
        "manifest": {"path": "D:/release/scene_manifest.json", "sha256": "C" * 64},
        "qa_report": {"path": "D:/release/automated_qa.json", "sha256": "D" * 64},
    }


def valid_media() -> dict[str, object]:
    return {
        "duration_ms": 44867,
        "width": 512,
        "height": 288,
        "frame_rate": "30/1",
        "video_codec": "h264",
        "video_bit_rate": 1_200_000,
        "audio_codec": "aac",
        "audio_bit_rate": 128_000,
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "audio_channel_layout": "stereo",
        "upscaled": False,
    }


def valid_marker() -> dict[str, object]:
    return build_build_ready_marker(
        release_id="ac7114_16_sp_story_no_bgm_zh_v1",
        ordered_events=["ac7114_001", "ac7115_001", "ac7116_001"],
        dialogue_cue_count=9,
        media=valid_media(),
        artifacts=valid_artifacts(),
    )


class IndependentReleaseContractTests(unittest.TestCase):
    def test_only_named_no_bgm_chinese_profile_is_supported(self) -> None:
        contract = release_contract()
        self.assertEqual(contract["schema"], RELEASE_CONTRACT_SCHEMA)
        self.assertEqual(contract["release_profile"], RELEASE_PROFILE)
        self.assertEqual(contract["audio_profile"], "no_bgm")
        self.assertEqual(contract["subtitle_profile"], "zh_dialogue_only")
        self.assertEqual(contract["release_scope"], "independent_edition")
        self.assertEqual(contract["bgm_policy"], "intentionally_excluded")
        self.assertEqual(contract["voice_se_policy"], "preserve_verified_original")
        self.assertFalse(contract["archive_complete"])
        self.assertFalse(contract["six_edition_complete"])
        with self.assertRaisesRegex(ValueError, "unsupported independent release profile"):
            release_contract("with_bgm_zh")

    def test_release_contract_is_exact_and_returns_fresh_copies(self) -> None:
        first = release_contract()
        second = release_contract()
        first["audio_profile"] = "with_bgm"
        self.assertEqual(second["audio_profile"], "no_bgm")
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_release_contract(first)
        extra = release_contract()
        extra["unexpected"] = True
        with self.assertRaisesRegex(ValueError, r"unknown=\['unexpected'\]"):
            validate_release_contract(extra)

    def test_build_ready_binds_exact_artifacts_and_keeps_human_status_false(self) -> None:
        marker = valid_marker()
        self.assertEqual(marker["schema"], BUILD_READY_SCHEMA)
        self.assertEqual(marker["status"], BUILD_READY_STATUS)
        self.assertTrue(marker["readiness"]["BUILD_READY"])
        self.assertTrue(marker["readiness"]["AUTOMATED_QA_PASSED"])
        self.assertFalse(marker["readiness"]["HUMAN_PLAYBACK_APPROVED"])
        self.assertFalse(marker["readiness"]["BILIBILI_RELEASE_READY"])
        self.assertFalse(marker["publishable"])
        self.assertEqual(marker["translation_status"], "machine_draft_pending_owner")
        self.assertEqual(marker["human_review_status"], "pending")
        self.assertEqual(marker["dialogue_cue_count"], 9)
        self.assertEqual(
            marker["release_contract_sha256"],
            canonical_sha256(marker["release_contract"]),
        )
        self.assertEqual(
            marker["artifact_set_sha256"], canonical_sha256(marker["artifacts"])
        )

    def test_marker_rejects_human_or_bilibili_approval_claims(self) -> None:
        for field in ("HUMAN_PLAYBACK_APPROVED", "BILIBILI_RELEASE_READY"):
            marker = valid_marker()
            marker["readiness"][field] = True
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "cannot claim human or Bilibili approval"
            ):
                validate_build_ready_marker(marker)
        marker = valid_marker()
        marker["publishable"] = True
        with self.assertRaisesRegex(ValueError, "fixed fields mismatch"):
            validate_build_ready_marker(marker)
        marker = valid_marker()
        marker["readiness"]["HUMAN_PLAYBACK_APPROVED"] = 0
        with self.assertRaisesRegex(
            ValueError, "cannot claim human or Bilibili approval"
        ):
            validate_build_ready_marker(marker)

    def test_marker_rejects_artifact_contract_tampering(self) -> None:
        marker = valid_marker()
        del marker["artifacts"]["qa_report"]
        with self.assertRaisesRegex(ValueError, "artifact roles differ"):
            validate_build_ready_marker(marker)

        marker = valid_marker()
        marker["artifacts"]["video"]["sha256"] = "short"
        with self.assertRaisesRegex(ValueError, "full SHA-256"):
            validate_build_ready_marker(marker)

        marker = valid_marker()
        marker["artifacts"]["video"]["sha256"] = "E" * 64
        with self.assertRaisesRegex(ValueError, "artifact set SHA-256 mismatch"):
            validate_build_ready_marker(marker)

    def test_marker_rejects_non_native_media_and_invalid_identity_or_order(self) -> None:
        for field, value in (
            ("video_codec", "hevc"),
            ("audio_sample_rate", 44100),
            ("audio_channels", 1),
            ("upscaled", True),
        ):
            media = valid_media()
            media[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "media contract mismatch"
            ):
                build_build_ready_marker(
                    release_id="release",
                    ordered_events=["ac7114_001"],
                    dialogue_cue_count=1,
                    media=media,
                    artifacts=valid_artifacts(),
                )

        with self.assertRaises(ValueError):
            build_build_ready_marker(
                release_id="../escape",
                ordered_events=["ac7114_001"],
                dialogue_cue_count=1,
                media=valid_media(),
                artifacts=valid_artifacts(),
            )
        with self.assertRaisesRegex(ValueError, "duplicates"):
            build_build_ready_marker(
                release_id="release",
                ordered_events=["ac7114_001", "ac7114_001"],
                dialogue_cue_count=1,
                media=valid_media(),
                artifacts=valid_artifacts(),
            )
        with self.assertRaisesRegex(ValueError, "positive integer"):
            build_build_ready_marker(
                release_id="release",
                ordered_events=["ac7114_001"],
                dialogue_cue_count=1.0,  # type: ignore[arg-type]
                media=valid_media(),
                artifacts=valid_artifacts(),
            )

    def test_marker_rejects_contract_hash_and_fixed_field_tampering(self) -> None:
        marker = valid_marker()
        marker["release_contract_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "release contract SHA-256 mismatch"):
            validate_build_ready_marker(marker)

        for field, value in (
            ("audio_profile", "with_bgm"),
            ("bgm_policy", "unknown"),
            ("archive_complete", True),
            ("six_edition_complete", True),
            ("human_review_status", "approved"),
        ):
            marker = valid_marker()
            marker[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "fixed fields mismatch"
            ):
                validate_build_ready_marker(marker)

    def test_validation_is_side_effect_free(self) -> None:
        marker = valid_marker()
        original = copy.deepcopy(marker)
        validated = validate_build_ready_marker(marker)
        self.assertEqual(marker, original)
        validated["artifacts"]["video"]["path"] = "changed"
        self.assertEqual(marker, original)


if __name__ == "__main__":
    unittest.main()
