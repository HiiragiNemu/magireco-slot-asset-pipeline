from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_ac1102_exhaustive_authoritative_longform import (
    EDITORIAL_ORDER,
    Ac1102ExhaustiveError,
    _augment_translation_map,
    _presentation_projection,
    build_missing_manifest,
    load_existing_inputs,
)


class Ac1102ExhaustiveLongformTests(unittest.TestCase):
    def test_editorial_order_covers_all_fifteen_events_once(self) -> None:
        self.assertEqual(len(EDITORIAL_ORDER), 15)
        self.assertEqual(
            set(EDITORIAL_ORDER),
            {f"ac1102_{index:03d}" for index in range(1, 16)},
        )

    def test_translation_map_adds_only_authority_subtitles(self) -> None:
        base = {
            "translations": [
                {"ja": "既存", "zh": "现有", "status": "machine_draft_pending_owner"}
            ]
        }
        audio = {
            "audio_rows": [
                {"subtitle_ja": "奥の手だ！", "subtitle_zh": "这是我的绝招！"},
                {"subtitle_ja": None, "subtitle_zh": None},
            ]
        }
        result = _augment_translation_map(base, audio)
        self.assertEqual(len(result["translations"]), 2)
        self.assertEqual(result["translations"][1]["ja"], "奥の手だ！")

    def test_generated_event_retains_voice_without_invented_subtitle(self) -> None:
        sources = [
            {
                "source_exists": True,
                "z2d_name": "ac1102_1on_c004",
                "dgm_name": "ac1102_1on_c004",
                "path": "D:/fixture.mp4",
                "source_sha256": "A" * 64,
                "width": 416,
                "height": 232,
                "event_start_ms": 0,
                "event_end_ms": 2000,
            }
        ]
        audio = [
            {
                "event": "ac1102_013",
                "source_kind": "event_audio_component",
                "request_id": 1067,
                "sound_id": 4212,
                "code_name": "SE",
                "start_ms": 0,
                "duration_ms": 4384,
                "ogg_name": "se.ogg",
                "ogg_path": "D:/se.ogg",
                "volume_kind_value": 1,
                "volume_bus": "SE",
                "strict_no_bgm_disposition": "RETAIN_VERIFIED_SE",
                "timing_evidence": "official_event_audio_component_event_global_start",
                "subtitle_ja": None,
                "subtitle_zh": None,
            }
        ]
        manifest = build_missing_manifest(
            "ac1102_013",
            code_hex="0x1",
            source_rows=sources,
            audio_rows=audio,
            runtime_frames=90,
            layer_authority_path=__import__("pathlib").Path("D:/layer.json"),
            audio_authority_path=__import__("pathlib").Path("D:/audio.json"),
        )
        self.assertEqual(manifest["subtitles"], [])
        self.assertEqual(manifest["audio"][0]["volume_bus"], "SE")
        self.assertEqual(manifest["render_frame_count"], 132)

    def test_complete_presentation_projection_changes_with_audio(self) -> None:
        base = {
            "render_frame_count": 30,
            "clips": [
                {
                    "dgm_name": "clip",
                    "dgm_role": "background",
                    "source_sha256": "A" * 64,
                    "event_start_ms": 0,
                    "event_end_ms": 1000,
                }
            ],
            "audio": [
                {
                    "request_id": "1",
                    "sound_id": 2,
                    "ogg_name": "a.ogg",
                    "start_ms": 0,
                    "duration_ms": 1000,
                }
            ],
            "subtitles": [],
        }
        changed = copy.deepcopy(base)
        changed["audio"][0]["start_ms"] = 1
        self.assertNotEqual(
            _presentation_projection(base), _presentation_projection(changed)
        )

    def test_generated_manifest_rejects_retained_bgm(self) -> None:
        with self.assertRaisesRegex(Ac1102ExhaustiveError, "retained no-BGM"):
            build_missing_manifest(
                "ac1102_013",
                code_hex="0x1",
                source_rows=[
                    {
                        "source_exists": True,
                        "z2d_name": "ac1102_1on_c004",
                        "dgm_name": "clip",
                        "path": "D:/fixture.mp4",
                        "source_sha256": "A" * 64,
                        "width": 416,
                        "height": 232,
                        "event_start_ms": 0,
                        "event_end_ms": 3000,
                    }
                ],
                audio_rows=[
                    {
                        "event": "ac1102_013",
                        "source_kind": "event_audio_component",
                        "request_id": 1,
                        "sound_id": 1,
                        "code_name": "bad",
                        "start_ms": 0,
                        "duration_ms": 1000,
                        "ogg_name": "bad.ogg",
                        "ogg_path": "D:/bad.ogg",
                        "volume_kind_value": 0,
                        "volume_bus": "BGM",
                        "strict_no_bgm_disposition": "RETAIN_VERIFIED_SE",
                        "timing_evidence": "official_event_audio_component_event_global_start",
                        "subtitle_ja": None,
                        "subtitle_zh": None,
                    }
                ],
                runtime_frames=90,
                layer_authority_path=__import__("pathlib").Path("D:/layer.json"),
                audio_authority_path=__import__("pathlib").Path("D:/audio.json"),
            )

    def test_reopen_requires_passed_immutable_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "series_proposals").mkdir()
            (root / "translations").mkdir()
            (root / "VERIFICATION_RECORD.json").write_text(
                json.dumps(
                    {
                        "status": "PASS_READY_FOR_RENDER",
                        "checks": {
                            "complete_event_presentations": 15,
                            "unique_complete_presentations": 15,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "AC1102_EXHAUSTIVE_EDITORIAL_AUTHORITY.json").write_text(
                json.dumps(
                    {
                        "status": "PASS_READY_FOR_RENDER",
                        "decision": {"new_exhaustive_render_allowed": True},
                    }
                ),
                encoding="utf-8",
            )
            (root / "series_proposals" / "ac1102_exhaustive.json").write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "event_sequence": list(EDITORIAL_ORDER),
                    }
                ),
                encoding="utf-8",
            )
            (root / "translations" / "ac1102_exhaustive_zh_v2.json").write_text(
                "{}", encoding="utf-8"
            )
            reopened = load_existing_inputs(root)
            self.assertEqual(reopened["output_root"], root.resolve())

    def test_v152_checkpoint_supersedes_fragmented_products(self) -> None:
        checkpoint = json.loads(
            (
                Path(__file__).resolve().parent
                / "tools"
                / "frida_runtime_probe"
                / "series_proposals"
                / "ac1102_exhaustive_authoritative_longform_v152_20260824.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(checkpoint["status"], "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED")
        self.assertEqual(checkpoint["review_group_count"], 1)
        self.assertEqual(checkpoint["dirinfo_route_coverage"], "31/31")
        self.assertEqual(checkpoint["complete_event_presentation_count"], 15)
        self.assertEqual(checkpoint["exact_duplicate_complete_presentation_count"], 0)
        self.assertFalse(
            checkpoint["legacy_disposition"]["legacy_91_8s_longform_authoritative"]
        )
        self.assertFalse(
            checkpoint["legacy_disposition"]["v77_route_fragments_are_final_products"]
        )
        self.assertEqual(checkpoint["presentation_frames"], 4091)
        self.assertTrue(checkpoint["human_playback_required"])
        self.assertFalse(checkpoint["publication_approved"])


if __name__ == "__main__":
    unittest.main()
