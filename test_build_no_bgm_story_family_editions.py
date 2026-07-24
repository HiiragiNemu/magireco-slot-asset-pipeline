from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_no_bgm_story_family_editions import (
    AUDIO_OVERRIDE_SCHEMAS,
    DEFAULT_EDITIONS,
    EXPLICITLY_EXCLUDABLE_SLOT_EFFECT_REQUESTS,
    SPEAKER_SCHEMA,
    SUPPORTED_EDITIONS,
    apply_audio_role_overrides,
    apply_missing_voice_subtitle_overrides,
    attach_speaker_evidence,
    build_family_editions,
    display_text,
    edition_cues,
    load_audio_role_overrides,
    load_dialogue_relationship_rules,
    load_speaker_registry,
    normalize_editions,
    snapshot,
    validate_series_proposal_bindings,
    validate_translation_relationship_rules,
)
from tools.frida_runtime_probe.build_sp_story_chapter_reviews import (
    SUPPORTED_DIMENSIONS,
    load_layout_profiles,
    resolve_event,
)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class NoBgmStoryFamilyEditionTests(unittest.TestCase):
    def test_translation_relationship_rules_fail_closed(self) -> None:
        rules_path = (
            Path(__file__).resolve().parent
            / "tools"
            / "frida_runtime_probe"
            / "dialogue_relationship_rules_v1.json"
        )
        rules, source = load_dialogue_relationship_rules(rules_path)
        audit = validate_translation_relationship_rules(
            {
                "環さんはどう思う？": "环同学，你怎么看？",
                "黒江さん！": "黑江同学！",
            },
            rules,
        )
        self.assertEqual(len(audit), 2)
        self.assertEqual(len(source["sha256"]), 64)
        with self.assertRaisesRegex(ValueError, "relationship rule"):
            validate_translation_relationship_rules(
                {"環さんはどう思う？": "环小姐，你怎么看？"},
                rules,
            )

    def test_series_proposal_binds_current_event_and_source_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_root = root / "manifests"
            events = manifest_root / "events"
            events.mkdir(parents=True)
            event_path = events / "ac0001_001.json"
            event_path.write_text('{"event": "ac0001_001"}\n', encoding="utf-8")
            original_event_bytes = event_path.read_bytes()
            source_path = root / "source_series.json"
            write_json(
                source_path,
                {
                    "schema": "magireco-series-editions-v1",
                    "series": "ac0001",
                    "status": "passed",
                    "family_state": {
                        "ready_event_names": ["ac0001_001", "ac0001_002"]
                    },
                },
            )
            proposal_path = root / "proposal.json"
            proposal = {
                "family_state": {
                    "production_manifest_root": str(manifest_root.resolve()),
                    "ready_event_names": ["ac0001_001"],
                },
                "event_manifest_sha256": {
                    "ac0001_001": hashlib.sha256(event_path.read_bytes())
                    .hexdigest()
                    .upper()
                },
                "source_series_manifest": {
                    "path": str(source_path.resolve()),
                    "sha256": hashlib.sha256(source_path.read_bytes())
                    .hexdigest()
                    .upper(),
                    "evidence": "synthetic ordered source series",
                },
            }
            write_json(proposal_path, proposal)
            binding, sources = validate_series_proposal_bindings(
                family="ac0001_split",
                series=proposal,
                series_path=proposal_path,
                manifest_root=manifest_root,
                ordered_events=["ac0001_001"],
            )
            self.assertEqual(binding["status"], "current_identity_bound")
            self.assertEqual(len(sources), 1)

            event_path.write_text('{"event": "changed"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                validate_series_proposal_bindings(
                    family="ac0001_split",
                    series=proposal,
                    series_path=proposal_path,
                    manifest_root=manifest_root,
                    ordered_events=["ac0001_001"],
                )

            event_path.write_bytes(original_event_bytes)
            source_payload = json.loads(source_path.read_text(encoding="utf-8"))
            source_payload["series"] = "ac9999"
            write_json(source_path, source_payload)
            with self.assertRaisesRegex(ValueError, "source series manifest SHA-256"):
                validate_series_proposal_bindings(
                    family="ac0001_split",
                    series=proposal,
                    series_path=proposal_path,
                    manifest_root=manifest_root,
                    ordered_events=["ac0001_001"],
                )

            proposal["source_series_manifest"]["sha256"] = hashlib.sha256(
                source_path.read_bytes()
            ).hexdigest().upper()
            with self.assertRaisesRegex(ValueError, "source series manifest identity"):
                validate_series_proposal_bindings(
                    family="ac0001_split",
                    series=proposal,
                    series_path=proposal_path,
                    manifest_root=manifest_root,
                    ordered_events=["ac0001_001"],
                )

    def test_native_512x416_opening_layout_is_supported_without_resizing(
        self,
    ) -> None:
        repo = Path(__file__).resolve().parent
        layout_path = (
            repo
            / "tools"
            / "frida_runtime_probe"
            / "subtitle_layout_profiles"
            / "project_approved_zh_video_subtitle_layout_512x416_v1.json"
        )
        layouts, sources = load_layout_profiles([str(layout_path)])
        self.assertIn((512, 416), SUPPORTED_DIMENSIONS)
        self.assertEqual(set(layouts), {(512, 416)})
        self.assertEqual(layouts[(512, 416)]["font_size"], 18)
        self.assertEqual(layouts[(512, 416)]["safe_area"]["bottom_px"], 14)
        self.assertEqual(len(sources), 1)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clean = root / "clean.mp4"
            clean.write_bytes(b"native 512x416 clean visual")
            report = root / "render_manifest.json"
            voice = root / "voice.ogg"
            voice.write_bytes(b"voice")
            write_json(
                report,
                {
                    "event": "ac7113_001",
                    "status": "passed",
                    "output_sha256": hashlib.sha256(
                        clean.read_bytes()
                    ).hexdigest().upper(),
                },
            )
            resolved, _ = resolve_event(
                {
                    "event": "ac7113_001",
                    "audio": [
                        {
                            "request_id": "123",
                            "code_name": "voice",
                            "ogg_name": "voice.ogg",
                            "path": str(voice),
                            "source": "z2d_req_sound",
                            "start_ms": 0,
                            "duration_ms": 1000,
                        }
                    ],
                    "subtitles": [
                        {
                            "voice_request_id": "123",
                            "text": "はい",
                            "start_ms": 0,
                            "end_ms": 1000,
                            "subtitle_source": "official_voice_label",
                        }
                    ],
                    "render_frame_count": 342,
                    "render_duration_quantization": {
                        "audio_sample_count": 547200
                    },
                    "native_dimensions": {"width": 512, "height": 416},
                    "video_composition_model": "linear_full_frame_sequence",
                },
                clean_visual=clean,
                clean_report=report,
                translations={"はい": "是。"},
                require_scene_se=False,
                reject_unsubtitled_audio=True,
            )
            self.assertEqual((resolved["width"], resolved["height"]), (512, 416))

    def test_generic_resolver_accepts_voice_only_and_rejects_unknown_audio(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clean = root / "clean.mp4"
            clean.write_bytes(b"clean visual")
            report = root / "render_manifest.json"
            write_json(
                report,
                {
                    "event": "ac_test",
                    "status": "passed",
                    "output_sha256": hashlib.sha256(
                        clean.read_bytes()
                    ).hexdigest().upper(),
                },
            )
            voice = root / "voice.ogg"
            voice.write_bytes(b"voice")
            manifest = {
                "event": "ac_test",
                "audio": [
                    {
                        "request_id": "123",
                        "code_name": "voice",
                        "ogg_name": "voice.ogg",
                        "path": str(voice),
                        "source": "z2d_req_sound",
                        "start_ms": 0,
                        "duration_ms": 1000,
                    }
                ],
                "subtitles": [
                    {
                        "voice_request_id": "123",
                        "text": "はい",
                        "start_ms": 0,
                        "end_ms": 1000,
                        "subtitle_source": "official_voice_label",
                    }
                ],
                "render_frame_count": 30,
                "render_duration_quantization": {"audio_sample_count": 48000},
                "native_dimensions": {"width": 512, "height": 288},
                "video_composition_model": "linear_full_frame_sequence",
            }
            resolved, _ = resolve_event(
                manifest,
                clean_visual=clean,
                clean_report=report,
                translations={"はい": "好的。"},
                require_scene_se=False,
                reject_unsubtitled_audio=True,
            )
            self.assertEqual(resolved["audio_layers"][0]["role"], "voice")

            manifest["subtitles"] = []
            with self.assertRaisesRegex(
                ValueError,
                "unresolved unsubtitled audio layers",
            ):
                resolve_event(
                    manifest,
                    clean_visual=clean,
                    clean_report=report,
                    translations={},
                    require_scene_se=False,
                    reject_unsubtitled_audio=True,
                )

            manifest["audio"] = [
                {
                    "request_id": "123",
                    "code_name": "voice",
                    "ogg_name": "voice.ogg",
                    "path": str(voice),
                    "source": "z2d_req_sound",
                    "start_ms": 0,
                    "duration_ms": 1000,
                }
            ]
            manifest["subtitles"] = [
                {
                    "voice_request_id": "999",
                    "text": "画面文字",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "subtitle_source": "graphical_display_text",
                },
                {
                    "voice_request_id": "123",
                    "text": "はい",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "subtitle_source": "official_voice_label",
                },
            ]
            resolved, _ = resolve_event(
                manifest,
                clean_visual=clean,
                clean_report=report,
                translations={"はい": "好的。"},
                require_scene_se=False,
                reject_unsubtitled_audio=True,
            )
            self.assertEqual(len(resolved["dialogue_cues"]), 1)
            self.assertEqual(len(resolved["excluded_source_cues"]), 1)

            invalid = copy.deepcopy(manifest)
            invalid["subtitles"][0]["subtitle_source"] = "official_voice_label"
            with self.assertRaisesRegex(ValueError, "lacks one voice layer"):
                resolve_event(
                    invalid,
                    clean_visual=clean,
                    clean_report=report,
                    translations={"はい": "好的。"},
                    require_scene_se=False,
                    reject_unsubtitled_audio=True,
                )

            manifest["audio"] = []
            with self.assertRaisesRegex(
                ValueError,
                "no retained evidence-bound audio layers",
            ):
                resolve_event(
                    manifest,
                    clean_visual=clean,
                    clean_report=report,
                    translations={},
                    require_scene_se=False,
                    reject_unsubtitled_audio=True,
                )

    def test_family_builder_rejects_unknown_audio_role_before_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(
                RuntimeError,
                "contains unresolved audio roles",
            ):
                build_family_editions(
                    "ac_test",
                    [
                        {
                            "event": "ac_test_001",
                            "audio_layers": [
                                {"role": "unsubtitled_audio"}
                            ],
                        }
                    ],
                    editions=("none",),
                    out_root=root,
                    layout={},
                    bilingual_layout=None,
                    font_path=root / "missing.ttf",
                    speakers={},
                    source_snapshots=[],
                    audio_role_overrides=[],
                    series_binding={"status": "test_fixture"},
                    relationship_rule_audit=[],
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    overwrite=False,
                )
    def test_default_editions_defer_bilingual_encoding(self) -> None:
        self.assertEqual(normalize_editions(None), DEFAULT_EDITIONS)
        self.assertEqual(
            normalize_editions(["zh", "none", "zh", "ja_zh"]),
            ("none", "zh", "ja_zh"),
        )
        with self.assertRaisesRegex(ValueError, "unsupported editions"):
            normalize_editions(["with_bgm"])

    def test_speaker_prefix_requires_registry_and_cue_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "speakers.json"
            write_json(
                path,
                {
                    "schema": SPEAKER_SCHEMA,
                    "policy": {
                        "prefix_only_when_speaker_identity_is_evidence_bound": True
                    },
                    "speakers": {
                        "iro": {"ja": "環いろは", "zh": "环彩羽"},
                        "mad": {"ja": "鹿目まどか", "zh": "鹿目圆"},
                    },
                },
            )
            registry, source = load_speaker_registry(path)
            self.assertIsNotNone(source)
            cue = {
                "ja_text": "行くよ！",
                "zh_text": "要上了！",
                "speaker_code": "iro",
                "subtitle_source": "official_runtime_capture",
                "evidence": "runtime_text_before_voice",
            }
            self.assertEqual(display_text(cue, "ja", registry), "環いろは：行くよ！")
            self.assertEqual(display_text(cue, "zh", registry), "环彩羽：要上了！")

            no_evidence = dict(cue, evidence="")
            self.assertEqual(display_text(no_evidence, "zh", registry), "要上了！")
            multiple = dict(cue, speaker_code="multiple")
            self.assertEqual(display_text(multiple, "zh", registry), "要上了！")
            unmapped = dict(cue, speaker_code="other")
            self.assertEqual(display_text(unmapped, "zh", registry), "要上了！")

    def test_bilingual_cue_is_japanese_above_chinese(self) -> None:
        registry = {"iro": {"ja": "環いろは", "zh": "环彩羽"}}
        base = [
            {
                "start_ms": 100,
                "end_ms": 900,
                "event": "ac0001_001",
                "request_id": "1",
                "ja_text": "黒江さん！",
                "zh_text": "黑江同学！",
                "speaker_code": "iro",
                "subtitle_source": "official_runtime_capture",
                "evidence": "runtime_text_before_voice",
            }
        ]
        rows = edition_cues(base, "ja_zh", registry)
        self.assertEqual(
            rows[0]["text"],
            "環いろは：黒江さん！\n环彩羽：黑江同学！",
        )

    def test_attach_speaker_evidence_matches_voice_request(self) -> None:
        resolved = {
            "event": "ac0001_001",
            "dialogue_cues": [{"request_id": "123", "ja_text": "はい"}],
        }
        manifest = {
            "subtitles": [
                {
                    "voice_request_id": "123",
                    "speaker_code": "iro",
                    "subtitle_source": "official_voice_label",
                    "evidence": "official_sound_request_code_name",
                }
            ]
        }
        attach_speaker_evidence(resolved, manifest)
        self.assertEqual(resolved["dialogue_cues"][0]["speaker_code"], "iro")
        self.assertEqual(
            resolved["dialogue_cues"][0]["evidence"],
            "official_sound_request_code_name",
        )

    def test_audio_role_override_requires_exact_event_code_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "scene.ogg"
            audio.write_bytes(b"official scene SE")
            digest = hashlib.sha256(audio.read_bytes()).hexdigest().upper()
            path = root / "overrides.json"
            write_json(
                path,
                {
                    "schema": sorted(AUDIO_OVERRIDE_SCHEMAS)[0],
                    "overrides": [
                        {
                            "event": "ac6005_013",
                            "request_id": "2183",
                            "code_name": "9808_いろはCI【CU】_013",
                            "source_sha256": digest,
                            "role": "scene_se",
                            "evidence": "official_runtime_capture_non_dialogue_base_scene_se",
                        }
                    ],
                },
            )
            overrides, source = load_audio_role_overrides(path)
            self.assertIsNotNone(source)
            manifest = {
                "event": "ac6005_013",
                "audio": [
                    {
                        "request_id": "2183",
                        "code_name": "9808_いろはCI【CU】_013",
                        "path": str(audio),
                        "source": "z2d_req_sound",
                    }
                ],
            }
            projected, applied = apply_audio_role_overrides(manifest, overrides)
            self.assertEqual(projected["audio"][0]["source"], "event_audio_component")
            self.assertEqual(len(applied), 1)
            self.assertEqual(manifest["audio"][0]["source"], "z2d_req_sound")

            changed = dict(manifest)
            changed["audio"] = [dict(manifest["audio"][0], code_name="wrong")]
            with self.assertRaisesRegex(ValueError, "evidence mismatch"):
                apply_audio_role_overrides(changed, overrides)

            subtitle_conflict = dict(manifest)
            subtitle_conflict["subtitles"] = [
                {
                    "voice_request_id": "2183",
                    "text": "must remain dialogue",
                }
            ]
            with self.assertRaisesRegex(
                ValueError,
                "scene-SE override conflicts",
            ):
                apply_audio_role_overrides(subtitle_conflict, overrides)

    def test_slot_effect_override_removes_audio_and_only_graphical_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "button.ogg"
            audio.write_bytes(b"official button effect")
            digest = hashlib.sha256(audio.read_bytes()).hexdigest().upper()
            path = root / "overrides.json"
            write_json(
                path,
                {
                    "schema": sorted(AUDIO_OVERRIDE_SCHEMAS)[0],
                    "overrides": [
                        {
                            "event": "ac5203_005",
                            "request_id": "451",
                            "code_name": "1070_ボタンPUSH表示音",
                            "source_sha256": digest,
                            "role": "exclude_slot_effect",
                            "evidence": "official chance-button business identity",
                        }
                    ],
                },
            )
            overrides, _ = load_audio_role_overrides(path)
            manifest = {
                "event": "ac5203_005",
                "audio": [
                    {
                        "request_id": "100",
                        "code_name": "base",
                        "path": str(audio),
                        "source": "event_audio_component",
                    },
                    {
                        "request_id": "451",
                        "code_name": "1070_ボタンPUSH表示音",
                        "path": str(audio),
                        "source": "z2d_req_sound",
                    },
                ],
                "subtitles": [
                    {
                        "voice_request_id": "451",
                        "text": "ヌル\n3",
                        "subtitle_source": "graphical_display_text",
                    }
                ],
            }
            projected, applied = apply_audio_role_overrides(manifest, overrides)
            self.assertEqual([row["request_id"] for row in projected["audio"]], ["100"])
            self.assertEqual(projected["subtitles"], [])
            self.assertEqual(applied[0]["role"], "exclude_slot_effect")

            dialogue = dict(manifest)
            dialogue["subtitles"] = [
                {
                    "voice_request_id": "451",
                    "text": "real dialogue",
                    "subtitle_source": "official_runtime_capture",
                }
            ]
            with self.assertRaisesRegex(ValueError, "non-graphical dialogue"):
                apply_audio_role_overrides(dialogue, overrides)

    def test_hash_bound_gold_frame_request_can_only_be_excluded(self) -> None:
        self.assertEqual(EXPLICITLY_EXCLUDABLE_SLOT_EFFECT_REQUESTS, {"1681"})
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "gold.ogg"
            audio.write_bytes(b"official gold-frame transition")
            digest = hashlib.sha256(audio.read_bytes()).hexdigest().upper()
            base_override = {
                "event": "ac7112_001",
                "request_id": "1681",
                "code_name": "8040_シネスコ変化音_金帯",
                "source_sha256": digest,
                "role": "exclude_slot_effect",
                "evidence": "official gold-frame presentation sound",
            }
            manifest = {
                "event": "ac7112_001",
                "audio": [
                    {
                        "request_id": "1681",
                        "code_name": "8040_シネスコ変化音_金帯",
                        "path": str(audio),
                        "source": "z2d_req_sound",
                    }
                ],
                "subtitles": [],
            }
            projected, applied = apply_audio_role_overrides(
                manifest,
                {("ac7112_001", "1681"): base_override},
            )
            self.assertEqual(projected["audio"], [])
            self.assertEqual(applied[0]["role"], "exclude_slot_effect")

            retained = dict(base_override, role="scene_se")
            with self.assertRaisesRegex(ValueError, "evidence mismatch"):
                apply_audio_role_overrides(
                    manifest,
                    {("ac7112_001", "1681"): retained},
                )

    def test_missing_official_label_voice_override_requires_exact_audio_hash(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "voice.ogg"
            audio.write_bytes(b"official voice")
            digest = hashlib.sha256(audio.read_bytes()).hexdigest().upper()
            manifest = {
                "event": "ac7112_001",
                "audio": [
                    {
                        "request_id": "8906",
                        "code_name": "30555_378_say_っ…！",
                        "ogg_name": "snd_30555_bank08_ogg_07376.ogg",
                        "path": str(audio),
                        "start_ms": 12716,
                        "duration_ms": 932,
                    }
                ],
                "subtitles": [],
            }
            override = {
                "text": "っ…！",
                "speaker_code": "say",
                "source": "curated_official_sound_request_code_name",
                "official_prefix": "っ…！",
                "ogg_name": "snd_30555_bank08_ogg_07376.ogg",
                "audio_sha256": digest,
            }
            projected, applied = apply_missing_voice_subtitle_overrides(
                manifest,
                {"8906": override},
            )
            self.assertEqual(projected["subtitles"][0]["voice_request_id"], "8906")
            self.assertEqual(projected["subtitles"][0]["start_ms"], 12716)
            self.assertEqual(projected["subtitles"][0]["end_ms"], 13648)
            self.assertEqual(projected["subtitles"][0]["speaker_code"], "say")
            self.assertEqual(len(applied), 1)
            self.assertEqual(manifest["subtitles"], [])

            changed = dict(override, audio_sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "evidence mismatch"):
                apply_missing_voice_subtitle_overrides(
                    manifest,
                    {"8906": changed},
                )

            already_bound = dict(manifest)
            already_bound["subtitles"] = [
                {"voice_request_id": "8906", "text": "existing"}
            ]
            unchanged, existing_applied = apply_missing_voice_subtitle_overrides(
                already_bound,
                {"8906": changed},
            )
            self.assertEqual(unchanged["subtitles"], already_bound["subtitles"])
            self.assertEqual(existing_applied, [])

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg integration tools are required",
    )
    def test_all_selected_editions_share_one_aac_master(self) -> None:
        repo = Path(__file__).resolve().parent
        font = (
            repo
            / "reproducibility"
            / "local_inputs"
            / "fonts"
            / "noto-sans-cjk-sc-2.004"
            / "NotoSansSC-VF.ttf"
        )
        if not font.is_file():
            self.skipTest("audited local font dependency is absent")
        layout = json.loads(
            (
                repo
                / "tools"
                / "frida_runtime_probe"
                / "subtitle_layout_profiles"
                / "project_approved_zh_video_subtitle_layout_416x232_v1.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            visual = root / "visual.mp4"
            audio = root / "scene.ogg"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=blue:s=416x232:r=30:d=1",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-frames:v",
                    "30",
                    str(visual),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:sample_rate=48000:duration=1",
                    "-c:a",
                    "libvorbis",
                    str(audio),
                ],
                check=True,
            )
            event = {
                "event": "ac0001_001",
                "width": 416,
                "height": 232,
                "frame_count": 30,
                "presentation_samples": 48000,
                "clean_visual": visual,
                "audio_layers": [
                    {
                        "role": "scene_se",
                        "request_id": "100",
                        "start_ms": 0,
                        "path": audio,
                    }
                ],
                "dialogue_cues": [
                    {
                        "request_id": "100",
                        "start_ms": 100,
                        "end_ms": 900,
                        "ja_text": "はい",
                        "zh_text": "好的",
                        "speaker_code": "iro",
                        "subtitle_source": "official_runtime_capture",
                        "evidence": "runtime_text_before_voice",
                    }
                ],
                "excluded_voice_requests": [],
                "excluded_source_cues": [],
            }
            destination = build_family_editions(
                "ac0001",
                [event],
                editions=SUPPORTED_EDITIONS,
                out_root=root / "out",
                layout=layout,
                bilingual_layout=layout,
                font_path=font,
                speakers={"iro": {"ja": "環いろは", "zh": "环彩羽"}},
                source_snapshots=[
                    snapshot(visual, label="synthetic visual"),
                    snapshot(audio, label="synthetic audio"),
                    snapshot(font, label="audited font"),
                ],
                audio_role_overrides=[],
                series_binding={"status": "test_fixture"},
                relationship_rule_audit=[],
                ffmpeg="ffmpeg",
                ffprobe="ffprobe",
                overwrite=False,
            )
            marker = json.loads(
                (destination / "BATCH_REVIEW_READY.json").read_text(encoding="utf-8")
            )
            self.assertEqual(marker["selected_editions"], list(SUPPORTED_EDITIONS))
            self.assertFalse(marker["publishable"])
            for edition in SUPPORTED_EDITIONS:
                self.assertTrue(
                    (destination / marker["artifacts"][f"video_{edition}"]["path"]).is_file()
                )


if __name__ == "__main__":
    unittest.main()
