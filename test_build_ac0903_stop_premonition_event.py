from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import build_ac0903_stop_premonition_event as module  # noqa: E402


def visual_rows() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    audience: list[dict[str, str]] = []
    timeline: list[dict[str, str]] = []
    for expected in module.EXPECTED_VISUALS:
        audience.append(
            {
                "event_name": module.EVENT,
                "dgm_order": str(expected["dgm_order"]),
                "official_name": str(expected["official_name"]),
                "dgm_role": str(expected["dgm_role"]),
                "event_start_ms": str(expected["start_ms"]),
                "event_end_ms": str(expected["end_ms"]),
                "width": "416",
                "height": "232",
                "frame_rate": module.FRAME_RATE,
                "interval_confidence": "exact_duration_unique",
                "target_mp4": f"A:\\source\\{expected['official_name']}.mp4",
            }
        )
        timeline.append(
            {
                "event_name": module.EVENT,
                "z2d_name": "ac0903_cmn_stop_zen_SU1_S",
                "z2d_loop_point": "30",
                "relation_start_ms": "0",
                "relation_end_ms": "2000",
                "dgm_order": str(expected["dgm_order"]),
                "official_name": str(expected["official_name"]),
                "dgm_role": str(expected["dgm_role"]),
                "event_start_frame": str(expected["start_frame"]),
                "event_end_frame": str(
                    int(expected["end_frame_exclusive"]) - 1
                ),
                "media_expected_frames": str(expected["frame_count"]),
                "interval_confidence": "exact_duration_unique",
                "cri_match": "yes",
                "layer_flags_hex": str(expected["layer_flags_hex"]),
            }
        )
    return audience, timeline


def direct_audio_row() -> dict[str, str]:
    expected = module.EXPECTED_AUDIO
    return {
        "primary_animation": module.EVENT,
        "parent_request_id": str(expected["parent_request_id"]),
        "parent_code_name": str(expected["parent_code_name"]),
        "leaf_request_id": str(expected["leaf_request_id"]),
        "leaf_sound_code": str(expected["leaf_sound_code"]),
        "leaf_label": str(expected["leaf_label"]),
        "start_ms": str(expected["start_ms"]),
        "duration_ms": str(expected["catalog_duration_ms"]),
        "ogg_name": str(expected["ogg_name"]),
        "reqdata_type": str(expected["reqdata_type"]),
        "reqdata_group_or_channel": str(
            expected["reqdata_group_or_channel"]
        ),
        "reqdata_flag": str(expected["reqdata_flag"]),
        "speaker_hint": "",
        "subtitle_text": "",
        "smz_matches_leaf_request": "yes",
        "ogg_duration_match": "yes",
        "ogg_path": "A:\\source\\request680.ogg",
    }


class BuildAc0903StopPremonitionEventTests(unittest.TestCase):
    def test_parent_z2d_schedule_is_parallel_not_linear(self) -> None:
        audience, timeline = visual_rows()
        rows = module.validate_visual_schedule(audience, timeline)
        self.assertEqual(
            [row["start_frame"] for row in rows],
            [0, 0, 0, 30],
        )
        self.assertEqual(
            rows[0]["blend_operator"],
            "candidate_from_dgm_suffix_unproven",
        )
        self.assertEqual(
            rows[1]["blend_operator"],
            "candidate_from_dgm_suffix_unproven",
        )

    def test_linearized_overlay_fails_closed(self) -> None:
        audience, timeline = visual_rows()
        audience[1]["event_start_ms"] = "333"
        timeline[1]["event_start_frame"] = "10"
        timeline[1]["event_end_frame"] = "19"
        with self.assertRaisesRegex(ValueError, "interval differs"):
            module.validate_visual_schedule(audience, timeline)

    def test_direct_parent_req680_is_scene_se_at_event_zero(self) -> None:
        audio = module.validate_direct_parent_audio([direct_audio_row()])
        self.assertEqual(audio["classification"], "scene_se")
        self.assertTrue(audio["retain_in_no_bgm"])
        self.assertEqual(audio["start_ms"], 0)

    def test_child_local_or_subtitle_match_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "zero child-audio"):
            module.validate_zero_child_and_subtitle_rows(
                [{"event_name": module.EVENT}],
                [],
            )
        with self.assertRaisesRegex(ValueError, "zero child-audio"):
            module.validate_zero_child_and_subtitle_rows(
                [],
                [{"event_name": module.EVENT}],
            )

    def test_editions_are_identical_review_only_alias_targets(self) -> None:
        aliases = module.edition_aliases()
        self.assertEqual(
            [row["edition"] for row in aliases],
            ["none", "ja", "zh"],
        )
        self.assertTrue(
            all(
                row["expected_media_sha256_relation"]
                == "identical_to_canonical"
                for row in aliases
            )
        )
        self.assertTrue(all(row["publishable"] is False for row in aliases))
        self.assertTrue(
            all(row["status"] == "blocked_no_media_authorized" for row in aliases)
        )

    def test_manifest_uses_exact_frame_and_sample_grid(self) -> None:
        visuals = []
        for row in module.EXPECTED_VISUALS:
            visuals.append(
                {
                    **copy.deepcopy(row),
                    "source_path": f"C:\\source\\{row['official_name']}.mp4",
                }
            )
        audio = {
            **copy.deepcopy(module.EXPECTED_AUDIO),
            "source_path": "C:\\source\\request680.ogg",
            "classification": "scene_se",
            "retain_in_no_bgm": True,
        }
        validated = {
            "route": copy.deepcopy(module.EXPECTED_ROUTE),
            "visuals": visuals,
            "audio": audio,
            "source_snapshots": [],
        }
        plan_path = MODULE_DIR / "series_proposals" / "placeholder.json"
        original_hash = module.file_sha256
        try:
            module.file_sha256 = lambda _path: "0" * 64
            manifest = module.build_event_manifest(
                validated,
                plan_path=plan_path,
            )
        finally:
            module.file_sha256 = original_hash
        self.assertEqual(manifest["render_frame_count"], 60)
        self.assertEqual(
            manifest["audio_mix"]["presentation_sample_count"],
            96000,
        )
        self.assertEqual(
            manifest["audio_mix"]["tail_silence_samples"],
            4189,
        )
        self.assertEqual(
            manifest["composition_plan"]["forbidden_model"],
            "linear_concatenation_of_four_components",
        )
        self.assertFalse(manifest["render_authorized"])
        self.assertEqual(
            manifest["composition_plan"]["render_layer_order"],
            "unresolved",
        )

    def test_plan_status_never_authorizes_render(self) -> None:
        plan = module.read_json(
            MODULE_DIR
            / "series_proposals"
            / "ac0903_stop_premonition_event_v1.json"
        )
        self.assertEqual(
            plan["status"],
            "blocked_exact_compositor_contract_missing",
        )
        self.assertFalse(plan["render_authorized"])
        self.assertEqual(plan["media_outputs_written"], 0)


if __name__ == "__main__":
    unittest.main()
