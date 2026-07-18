from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.frida_runtime_probe.build_independent_scene_release import (
    LAYOUT_SCHEMA,
    PLAN_SCHEMA,
    parse_srt,
    validate_plan,
    write_srt,
)
from tools.frida_runtime_probe.independent_release_contract import release_contract


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


class IndependentScenePlanFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.roots = {
            name: root / name for name in ("research", "audio", "repo")
        }
        for path in self.roots.values():
            path.mkdir(parents=True)

        self.event = "ac0001_001"
        self.composition = {
            "event": self.event,
            "model": "linear_full_frame_sequence",
            "extension_policy": "hold_last_frame",
            "excluded_audio_request_ids": [1681],
            "native_dimensions": {"width": 512, "height": 288},
        }
        self.manifest = {
            "event": self.event,
            "composition_plan": self.composition,
            "quality_gates": {
                "ready": True,
                "render_ready": True,
                "audio_timeline_ready": True,
                "composition_resolved": True,
            },
            "audio": [
                {
                    "request_id": "100",
                    "ogg_name": "scene_se",
                    "start_ms": 0,
                    "duration_ms": 333,
                },
                {
                    "request_id": "200",
                    "ogg_name": "voice_001",
                    "start_ms": 101,
                    "duration_ms": 177,
                },
            ],
            "subtitles": [
                {
                    "text": "テストです",
                    "start_ms": 101,
                    "end_ms": 278,
                    "voice_request_id": "200",
                    "z2d_name": "",
                    "subtitle_source": "official_runtime_capture",
                },
                {
                    "text": "画面だけ",
                    "start_ms": 280,
                    "end_ms": 320,
                    "voice_request_id": "",
                    "z2d_name": "cap_graphical_only",
                    "subtitle_source": "graphical_display_text",
                },
            ],
        }

        clean_payload = b"placeholder-clean-h264"
        clean_locator = self.file_locator(
            "research", "media/clean.mp4", clean_payload
        )
        self.clean_path = self.roots["research"] / "media/clean.mp4"
        clean_report = {
            "event": self.event,
            "output_sha256": sha256(clean_payload),
        }
        layout = {
            "schema": LAYOUT_SCHEMA,
            "profile_id": "project_approved_zh_video_subtitle_layout_v1",
            "approval_status": "pending_owner_review",
            "original_game_layout": False,
            "target_width": 512,
            "target_height": 288,
            "alignment": "bottom_center",
            "font_family": "Noto Sans SC",
            "font_size": 22,
            "primary_colour": "&H00FFFFFF",
            "outline_colour": "&H00000000",
            "border_style": 1,
            "outline": 1.5,
            "shadow": 0,
            "margin_v": 18,
            "margin_lr": 20,
            "max_lines": 2,
            "safe_area": {"left": 20, "right": 20, "top": 12, "bottom": 18},
            "notes": "Candidate layout pending project-owner playback review.",
        }

        self.plan: dict[str, Any] = {
            "schema": PLAN_SCHEMA,
            "release_id": "ac0001_scene_no_bgm_zh_v1",
            "release_contract": release_contract(),
            "expected": {
                "ordered_events": [self.event],
                "width": 512,
                "height": 288,
                "frame_rate": "30/1",
                "total_frames": 10,
                "sample_rate": 48000,
                "audio_channels": 2,
                "total_presentation_samples": 16000,
                "dialogue_cue_count": 1,
            },
            "events": [
                {
                    "event": self.event,
                    "frame_count": 10,
                    "presentation_samples": 16000,
                    "v20_manifest": self.json_locator(
                        "research", "evidence/v20.json", self.manifest
                    ),
                    "runtime_manifest": self.json_locator(
                        "research", "evidence/runtime.json", {"event": self.event}
                    ),
                    "composition_plan": self.json_locator(
                        "research", "evidence/composition.json", self.composition
                    ),
                    "clean_visual": clean_locator,
                    "clean_render_manifest": self.json_locator(
                        "research", "evidence/clean_report.json", clean_report
                    ),
                    "official_ja_srt": self.file_locator(
                        "research",
                        "evidence/official.ja.srt",
                        (
                            "1\n00:00:00,101 --> 00:00:00,278\n"
                            "テストです\n"
                        ).encode("utf-8"),
                    ),
                    "audio_layers": [
                        {
                            "role": "scene_se",
                            "request_id": "100",
                            "ogg_name": "scene_se",
                            "start_ms": 0,
                            "duration_ms": 333,
                            "source": self.file_locator(
                                "audio", "ogg/scene_se.ogg", b"placeholder-scene-se"
                            ),
                        },
                        {
                            "role": "voice",
                            "request_id": "200",
                            "ogg_name": "voice_001",
                            "start_ms": 101,
                            "duration_ms": 177,
                            "source": self.file_locator(
                                "audio", "ogg/voice_001.ogg", b"placeholder-voice"
                            ),
                        },
                    ],
                    "dialogue_cues": [
                        {
                            "request_id": "200",
                            "speaker_code": "test",
                            "start_ms": 101,
                            "end_ms": 278,
                            "ja_text": "テストです",
                            "zh_text": "这是测试。",
                            "translation_status": "machine_draft_pending_owner",
                        }
                    ],
                    "excluded_voice_requests": [],
                    "excluded_source_cues": [
                        {
                            "text": "画面だけ",
                            "start_ms": 280,
                            "end_ms": 320,
                            "voice_request_id": "",
                            "z2d_name": "cap_graphical_only",
                            "subtitle_source": "graphical_display_text",
                            "reason": "Graphical-only text is outside dialogue subtitles.",
                        }
                    ],
                    "oracle": {
                        field: self.file_locator(
                            "research", f"oracle/{field}.bin", field.encode("ascii")
                        )
                        for field in (
                            "user_verified_media",
                            "render_manifest",
                            "qa_summary",
                            "qa_audit",
                        )
                    },
                }
            ],
            "layout_profile": self.json_locator(
                "repo", "profiles/zh_layout.json", layout
            ),
            "font": self.file_locator(
                "repo", "fonts/NotoSansSC-VF.ttf", b"placeholder-font"
            ),
        }
        self.plan_path = root / "plan.json"
        self.write_plan()

    def file_locator(
        self, root_name: str, relative: str, payload: bytes
    ) -> dict[str, str]:
        path = self.roots[root_name] / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {"root": root_name, "path": relative, "sha256": sha256(payload)}

    def json_locator(
        self, root_name: str, relative: str, value: Any
    ) -> dict[str, str]:
        payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
        return self.file_locator(root_name, relative, payload)

    def write_plan(self) -> None:
        self.plan_path.write_text(
            json.dumps(self.plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class IndependentScenePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = IndependentScenePlanFixture(Path(self.temporary.name))

    def validate(self) -> dict[str, Any]:
        self.fixture.write_plan()
        return validate_plan(self.fixture.plan_path, roots=self.fixture.roots)

    def test_valid_plan_resolves_exact_scene_cue_and_pending_layout(self) -> None:
        resolved = self.validate()
        self.assertEqual(resolved["release_contract"], release_contract())
        self.assertEqual(resolved["duration_ms"], 333)
        self.assertEqual(len(resolved["scene_cues"]), 1)
        cue = resolved["scene_cues"][0]
        self.assertEqual((cue["start_ms"], cue["end_ms"]), (101, 278))
        self.assertEqual(cue["event_start_sample"], 0)
        self.assertEqual(cue["zh_text"], "这是测试。")
        self.assertEqual(
            cue["voice_source_sha256"],
            self.fixture.plan["events"][0]["audio_layers"][1]["source"]["sha256"],
        )
        self.assertEqual(resolved["layout"]["approval_status"], "pending_owner_review")
        self.assertIs(resolved["layout"]["original_game_layout"], False)

    def test_source_hash_tampering_fails_closed(self) -> None:
        self.fixture.clean_path.write_bytes(b"tampered-clean-video")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.validate()

    def test_graphical_only_cue_must_be_explicitly_excluded(self) -> None:
        self.fixture.plan["events"][0]["excluded_source_cues"] = []
        with self.assertRaisesRegex(ValueError, "explicitly exclude every graphical-only cue"):
            self.validate()

    def test_graphical_only_cue_cannot_be_promoted_to_dialogue(self) -> None:
        self.fixture.plan["events"][0]["dialogue_cues"].append(
            {
                "request_id": "",
                "speaker_code": "",
                "start_ms": 280,
                "end_ms": 320,
                "ja_text": "画面だけ",
                "zh_text": "只有画面文字",
                "translation_status": "machine_draft_pending_owner",
            }
        )
        self.fixture.plan["expected"]["dialogue_cue_count"] = 2
        with self.assertRaisesRegex(ValueError, "lacks one runtime binding"):
            self.validate()

    def test_every_voice_must_be_included_or_explicitly_excluded(self) -> None:
        extra_audio = {
            "request_id": "201",
            "ogg_name": "voice_002",
            "start_ms": 200,
            "duration_ms": 100,
        }
        self.fixture.manifest["audio"].append(extra_audio)
        self.fixture.plan["events"][0]["v20_manifest"] = self.fixture.json_locator(
            "research", "evidence/v20-extra-voice.json", self.fixture.manifest
        )
        self.fixture.plan["events"][0]["audio_layers"].append(
            {
                "role": "voice",
                **extra_audio,
                "source": self.fixture.file_locator(
                    "audio", "ogg/voice_002.ogg", b"placeholder-extra-voice"
                ),
            }
        )
        with self.assertRaisesRegex(ValueError, "every voice must be included or explicitly excluded"):
            self.validate()

    def test_release_profile_or_contract_tampering_fails_closed(self) -> None:
        for field, value in (
            ("release_profile", "with_bgm_zh"),
            ("bgm_policy", "unknown"),
        ):
            fixture = IndependentScenePlanFixture(Path(self.temporary.name) / field)
            fixture.plan["release_contract"][field] = value
            fixture.write_plan()
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "does not match the named profile"
            ):
                validate_plan(fixture.plan_path, roots=fixture.roots)

    def test_layout_cannot_claim_owner_approval_or_game_identity(self) -> None:
        for field, value in (
            ("approval_status", "approved"),
            ("original_game_layout", True),
        ):
            fixture = IndependentScenePlanFixture(Path(self.temporary.name) / field)
            layout_path = fixture.roots["repo"] / "profiles/zh_layout.json"
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
            layout[field] = value
            fixture.plan["layout_profile"] = fixture.json_locator(
                "repo", f"profiles/zh_layout-{field}.json", layout
            )
            fixture.write_plan()
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "subtitle layout fixed field mismatch"
            ):
                validate_plan(fixture.plan_path, roots=fixture.roots)

    def test_srt_write_parse_roundtrip(self) -> None:
        path = Path(self.temporary.name) / "roundtrip.zh.srt"
        cues = [
            {"start_ms": 101, "end_ms": 278, "text": "这是测试。"},
            {"start_ms": 1001, "end_ms": 2345, "text": "第一行\n第二行"},
        ]
        write_srt(path, cues)
        self.assertEqual(parse_srt(path), cues)


if __name__ == "__main__":
    unittest.main()
