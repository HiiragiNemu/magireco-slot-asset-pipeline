from __future__ import annotations

import unittest

from tools.frida_runtime_probe.build_silent_audience_event_manifests import (
    parse_declared_bool,
    validate_bounded_product_contract,
    zero_audio_matches,
)


class SilentAudienceEventManifestTests(unittest.TestCase):
    def test_declared_bool_does_not_treat_no_string_as_true(self) -> None:
        self.assertFalse(parse_declared_bool("no", label="claim"))
        self.assertTrue(parse_declared_bool("yes", label="claim"))

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

    def test_bounded_profile_product_binds_one_complete_source_loop(self) -> None:
        result = validate_bounded_product_contract(
            {
                "product_scope": (
                    "profile_material_intro_plus_one_complete_source_loop_"
                    "not_natural_session"
                ),
                "natural_session_claimed": False,
                "loop_scope": {
                    "policy": "intro_then_exactly_one_complete_source_loop",
                    "loop_clip_official_name": "ac7118_at_ch_profile_iro_LP",
                    "loop_source_frame_count": 600,
                    "runtime_loop_count_claimed": False,
                },
            },
            event="ac7118_001",
            clip_rows=[
                {
                    "official_name": "ac7118_at_ch_profile_iro_IN",
                    "dgm_role": "single_layer_segment",
                },
                {
                    "official_name": "ac7118_at_ch_profile_iro_LP",
                    "dgm_role": "orphan_loop_cycle",
                },
            ],
            frame_counts={
                "ac7118_at_ch_profile_iro_IN": 100,
                "ac7118_at_ch_profile_iro_LP": 600,
            },
        )
        self.assertFalse(result["natural_session_claimed"])
        self.assertEqual(
            result["loop_scope"]["loop_source_frame_count"],
            600,
        )

    def test_bounded_profile_product_rejects_runtime_loop_claim(self) -> None:
        with self.assertRaisesRegex(ValueError, "claims runtime evidence"):
            validate_bounded_product_contract(
                {
                    "product_scope": "bounded_profile_material",
                    "natural_session_claimed": False,
                    "loop_scope": {
                        "policy": "intro_then_exactly_one_complete_source_loop",
                        "loop_clip_official_name": "profile_LP",
                        "loop_source_frame_count": 600,
                        "runtime_loop_count_claimed": True,
                    },
                },
                event="ac7118_001",
                clip_rows=[
                    {
                        "official_name": "profile_IN",
                        "dgm_role": "single_layer_segment",
                    },
                    {
                        "official_name": "profile_LP",
                        "dgm_role": "orphan_loop_cycle",
                    },
                ],
                frame_counts={"profile_IN": 100, "profile_LP": 600},
            )


if __name__ == "__main__":
    unittest.main()
