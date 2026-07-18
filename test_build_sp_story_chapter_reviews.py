from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_sp_story_chapter_reviews import (
    FORBIDDEN_AUDIO_REQUESTS,
    GENERIC_TRANSLATION_SCHEMA,
    TRANSLATION_SCHEMA,
    generated_linear_plan,
    load_translation_map,
    prepare_manifest,
    scene_audio_role,
    validate_reusable_clean_visual,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class SpStoryChapterReviewTests(unittest.TestCase):
    def minimal_manifest(self, root: Path) -> dict[str, object]:
        clip = root / "clip.mp4"
        audio = root / "scene.ogg"
        clip.write_bytes(b"clip")
        audio.write_bytes(b"audio")
        return {
            "event": "ac7114_003",
            "classification": "native_full_frame_only",
            "native_dimensions": {"width": 512, "height": 288},
            "native_frame_rate": "30/1",
            "timeline_content_end_ms": 12566,
            "video_extension_policy": "hold_last_frame",
            "video_composition_model": "linear_full_frame_sequence",
            "composition_plan": {},
            "composition_plan_source": "",
            "clips": [
                {
                    "order": 0,
                    "dgm_name": "ac7114_AT_SP_story3_02",
                    "dgm_role": "single_layer_segment",
                    "path": str(clip),
                    "event_start_ms": 0,
                    "event_end_ms": 12500,
                    "interval_confidence": "exact_duration_unique",
                }
            ],
            "audio": [
                {
                    "source": "event_audio_component",
                    "request_id": "10330",
                    "code_name": "42041_SPストーリー3_02_2G",
                    "ogg_name": "scene.ogg",
                    "path": str(audio),
                    "start_ms": 0,
                    "duration_ms": 12566,
                }
            ],
            "quality_gates": {
                "ready": True,
                "render_ready": True,
                "audio_timeline_ready": True,
                "composition_resolved": True,
            },
        }

    def test_translation_map_requires_unique_pending_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "translations.json"
            write_json(
                path,
                {
                    "schema": TRANSLATION_SCHEMA,
                    "translations": [
                        {
                            "ja": "鶴乃",
                            "zh": "鹤乃",
                            "status": "machine_draft_pending_owner",
                        }
                    ],
                },
            )
            translations, source = load_translation_map(path)
            self.assertEqual(translations, {"鶴乃": "鹤乃"})
            self.assertEqual(len(source["sha256"]), 64)

            value = json.loads(path.read_text(encoding="utf-8"))
            value["translations"].append(dict(value["translations"][0]))
            write_json(path, value)
            with self.assertRaisesRegex(ValueError, "duplicate Japanese"):
                load_translation_map(path)

    def test_generic_story_translation_schema_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "translations.json"
            write_json(
                path,
                {
                    "schema": GENERIC_TRANSLATION_SCHEMA,
                    "translations": [
                        {
                            "ja": "行くよ！",
                            "zh": "要上了！",
                            "status": "machine_draft_pending_owner",
                        }
                    ],
                },
            )
            translations, _ = load_translation_map(path)
            self.assertEqual(translations, {"行くよ！": "要上了！"})

    def test_generated_plan_is_exact_single_full_frame_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = self.minimal_manifest(Path(temp_dir))
            plan = generated_linear_plan(manifest)
            self.assertEqual(plan["event"], "ac7114_003")
            self.assertEqual(plan["duration_ms"], 12566)
            self.assertEqual(plan["extension_policy"], "hold_last_frame")
            self.assertEqual(
                plan["clips"],
                [
                    {
                        "dgm_name": "ac7114_AT_SP_story3_02",
                        "role": "background",
                        "start_ms": 0,
                    }
                ],
            )
            manifest["clips"].append(dict(manifest["clips"][0]))
            with self.assertRaisesRegex(ValueError, "duplicated|order is invalid"):
                generated_linear_plan(manifest)

    def test_generated_plan_projects_multiple_ordered_full_frame_clips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = self.minimal_manifest(Path(temp_dir))
            second = dict(manifest["clips"][0])
            second.update(
                {
                    "order": 1,
                    "dgm_name": "ac7114_AT_SP_story3_03",
                    "event_start_ms": 5000,
                    "event_end_ms": 12500,
                }
            )
            manifest["clips"].append(second)
            self.assertEqual(
                generated_linear_plan(manifest)["clips"],
                [
                    {
                        "dgm_name": "ac7114_AT_SP_story3_02",
                        "role": "background",
                        "start_ms": 0,
                    },
                    {
                        "dgm_name": "ac7114_AT_SP_story3_03",
                        "role": "background",
                        "start_ms": 5000,
                    },
                ],
            )

    def test_prepare_manifest_binds_sources_and_writes_explicit_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.json"
            write_json(source_path, self.minimal_manifest(root))
            prepared, prepared_path, sources = prepare_manifest(
                source_path,
                plan_dir=root / "plans",
                manifest_dir=root / "prepared",
            )
            self.assertTrue(prepared_path.is_file())
            self.assertEqual(
                prepared["composition_plan"]["model"], "linear_full_frame_sequence"
            )
            self.assertEqual(len(prepared["clips"][0]["source_sha256"]), 64)
            self.assertEqual(len(sources), 3)

    def test_prepare_manifest_replaces_incomplete_authored_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = self.minimal_manifest(root)
            manifest["composition_plan"] = {
                "schema": "magireco-video-composition-v1",
                "event": "ac7114_003",
                "model": "linear_full_frame_sequence",
                "extension_policy": "hold_last_frame",
                "evidence": "legacy plan header without clip rows",
            }
            source_path = root / "source.json"
            write_json(source_path, manifest)

            prepared, _, _ = prepare_manifest(
                source_path,
                plan_dir=root / "plans",
                manifest_dir=root / "prepared",
            )

            self.assertEqual(
                prepared["composition_plan"]["clips"],
                [
                    {
                        "dgm_name": "ac7114_AT_SP_story3_02",
                        "role": "background",
                        "start_ms": 0,
                    }
                ],
            )

    def test_prepare_manifest_rejects_bgm_or_gold_request(self) -> None:
        for request_id in sorted(FORBIDDEN_AUDIO_REQUESTS):
            with self.subTest(request_id=request_id), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                manifest = self.minimal_manifest(root)
                manifest["audio"][0]["request_id"] = request_id
                source_path = root / "source.json"
                write_json(source_path, manifest)
                with self.assertRaisesRegex(ValueError, "forbidden BGM/effect"):
                    prepare_manifest(
                        source_path,
                        plan_dir=root / "plans",
                        manifest_dir=root / "prepared",
                    )

    def test_reused_clean_visual_must_bind_current_prepared_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepared = root / "prepared.json"
            visual = root / "clean.mp4"
            report = root / "report.json"
            prepared.write_text("{}\n", encoding="utf-8")
            visual.write_bytes(b"clean visual")

            def digest(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest().upper()

            write_json(
                report,
                {
                    "event": "ac0001_001",
                    "status": "passed",
                    "source_manifest": {
                        "path": str(prepared.resolve()),
                        "sha256": digest(prepared),
                    },
                    "output": str(visual.resolve()),
                    "output_sha256": digest(visual),
                },
            )
            validate_reusable_clean_visual(
                event="ac0001_001",
                prepared_path=prepared,
                clean_visual=visual,
                clean_report=report,
            )

            prepared.write_text('{"changed": true}\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "stale"):
                validate_reusable_clean_visual(
                    event="ac0001_001",
                    prepared_path=prepared,
                    clean_visual=visual,
                    clean_report=report,
                )

    def test_scene_audio_role_uses_business_identity(self) -> None:
        self.assertEqual(
            scene_audio_role(
                {
                    "source": "z2d_req_sound",
                    "code_name": "42040_SPストーリー3_01_2G",
                }
            ),
            "scene_se",
        )
        self.assertEqual(
            scene_audio_role(
                {"source": "event_audio_component", "code_name": "other"}
            ),
            "scene_se",
        )
        self.assertEqual(
            scene_audio_role(
                {"source": "z2d_req_sound", "code_name": "30952_231_tur"}
            ),
            "voice",
        )

    def test_scene_audio_role_uses_subtitle_bound_request_ids(self) -> None:
        voice_ids = {"30952"}
        self.assertEqual(
            scene_audio_role(
                {"source": "z2d_req_sound", "request_id": "30952"}, voice_ids
            ),
            "voice",
        )
        self.assertEqual(
            scene_audio_role(
                {"source": "event_audio_component", "request_id": "42040"},
                voice_ids,
            ),
            "scene_se",
        )
        self.assertEqual(
            scene_audio_role(
                {"source": "z2d_req_sound", "request_id": "99999"}, voice_ids
            ),
            "unsubtitled_audio",
        )


if __name__ == "__main__":
    unittest.main()
