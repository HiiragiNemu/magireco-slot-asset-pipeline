import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from tools.frida_runtime_probe.build_ac1103_exhaustive_authoritative_longform import (
    EDITORIAL_ORDER,
    EXPECTED_EVENT_COUNT,
    Ac1103ExhaustiveError,
    bind_exact_ac1103_013_audio_roles,
    build_inputs,
    load_existing_inputs,
    presentation_projection,
    validate_source_checkpoint,
)


SOURCE_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
    r"\ac1103_event_global_route_inputs_v1_20260818"
)
TRANSLATION_MAP = Path(
    "tools/frida_runtime_probe/translations/"
    "mixed_story_ac1102_04_ac5208_zh_dialogue_v1.json"
).resolve()


def projection_manifest() -> dict:
    return {
        "render_frame_count": 30,
        "clips": [
            {
                "dgm_name": "visual",
                "dgm_role": "background",
                "source_sha256": "ab" * 32,
                "event_start_ms": 0,
                "event_end_ms": 1000,
            }
        ],
        "audio": [
            {
                "request_id": "1",
                "sound_id": 2,
                "ogg_name": "voice.ogg",
                "start_ms": 100,
                "duration_ms": 500,
            }
        ],
        "subtitles": [
            {
                "voice_request_id": "1",
                "text": "字幕",
                "start_ms": 100,
                "end_ms": 600,
            }
        ],
    }


class Ac1103ExhaustiveLongformTests(unittest.TestCase):
    def test_editorial_order_is_one_to_one_and_revival_is_final_chapter(self) -> None:
        self.assertEqual(len(EDITORIAL_ORDER), EXPECTED_EVENT_COUNT)
        self.assertEqual(
            set(EDITORIAL_ORDER),
            {f"ac1103_{index:03d}" for index in range(1, 14)},
        )
        self.assertEqual(EDITORIAL_ORDER[-2:], ("ac1103_012", "ac1103_013"))

    def test_projection_uses_complete_av_subtitle_timeline(self) -> None:
        first = projection_manifest()
        second = projection_manifest()
        self.assertEqual(presentation_projection(first), presentation_projection(second))
        second["subtitles"][0]["start_ms"] = 133
        self.assertNotEqual(presentation_projection(first), presentation_projection(second))

    @unittest.skipUnless(SOURCE_ROOT.is_dir(), "durable ac1103 checkpoint unavailable")
    def test_ac1103_013_exact_audio_roles_are_normalized_without_inference(self) -> None:
        source = json.loads(
            (SOURCE_ROOT / "events" / "ac1103_013.json").read_text(encoding="utf-8")
        )
        prepared = bind_exact_ac1103_013_audio_roles(source)
        roles = {str(row["request_id"]): row for row in prepared["audio"]}
        self.assertEqual(roles["4059"]["volume_bus"], "VOICE")
        self.assertTrue(roles["4059"]["event_global_start_resolved"])
        self.assertEqual(roles["1086"]["volume_bus"], "SE")
        self.assertEqual(
            prepared["exhaustive_longform_audio_role_binding"]["semantic_change"],
            False,
        )

    @unittest.skipUnless(SOURCE_ROOT.is_dir(), "durable ac1103 checkpoint unavailable")
    def test_durable_source_checkpoint_closes_all_routes_and_presentations(self) -> None:
        result = validate_source_checkpoint(SOURCE_ROOT, TRANSLATION_MAP)
        self.assertEqual(len(result["routes"]), 31)
        self.assertEqual(len(result["manifests"]), 13)
        self.assertEqual(result["frame_count"], 3114)
        self.assertEqual(result["source_occurrences"], 53)
        self.assertEqual(result["unique_source_identities"], 35)
        self.assertEqual(result["audio_occurrences"], 57)
        self.assertEqual(result["subtitle_occurrences"], 33)

    @unittest.skipUnless(SOURCE_ROOT.is_dir(), "durable ac1103 checkpoint unavailable")
    def test_builds_immutable_checkpoint_and_demotes_short_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "inputs"
            result = build_inputs(
                Namespace(
                    source_manifest_root=SOURCE_ROOT,
                    base_translation_map=TRANSLATION_MAP,
                    output_input_root=output,
                )
            )
            authority = json.loads(
                (output / "AC1103_EXHAUSTIVE_EDITORIAL_AUTHORITY.json").read_text(
                    encoding="utf-8"
                )
            )
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertEqual(authority["status"], "PASS_READY_FOR_RENDER")
            self.assertFalse(
                authority["decision"]["legacy_ac1103_013_18s_is_final_product"]
            )
            self.assertEqual(
                authority["decision"]["legacy_ac1103_013_18s_role"],
                "chapter_evidence_only",
            )
            self.assertEqual(
                verification["checks"]["unique_complete_presentations"], 13
            )
            normalized = json.loads(
                (output / "events" / "ac1103_013.json").read_text(encoding="utf-8")
            )
            self.assertEqual(normalized["audio"][0]["volume_bus"], "SE")
            self.assertTrue((output / "ROLLBACK.ps1").is_file())
            self.assertEqual(result["output_root"], output.resolve())
            reopened = load_existing_inputs(output)
            self.assertEqual(reopened["series_path"], result["series_path"])

    def test_reopen_fails_closed_on_incomplete_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "VERIFICATION_RECORD.json").write_text(
                '{"status":"PASS_READY_FOR_RENDER","checks":{}}', encoding="utf-8"
            )
            (root / "AC1103_EXHAUSTIVE_EDITORIAL_AUTHORITY.json").write_text(
                '{"status":"PASS_READY_FOR_RENDER","decision":{"new_exhaustive_render_allowed":true}}',
                encoding="utf-8",
            )
            (root / "series_proposals").mkdir()
            (root / "series_proposals" / "ac1103_exhaustive.json").write_text(
                '{"event_sequence":[]}', encoding="utf-8"
            )
            (root / "translations").mkdir()
            (root / "translations" / "ac1103_exhaustive_zh_v1.json").write_text(
                "{}", encoding="utf-8"
            )
            with self.assertRaisesRegex(Ac1103ExhaustiveError, "checkpoint differs"):
                load_existing_inputs(root)


if __name__ == "__main__":
    unittest.main()
