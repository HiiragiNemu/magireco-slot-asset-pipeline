from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.subtitle_edition_contract import (
    AUDIO_MASTER_CONTRACT_SCHEMA,
    build_edition_plan,
    normalize_cues,
    normalize_render_edition_matrix,
    normalize_render_editions,
    normalize_requested_editions,
    subtitle_cue_sha256,
    subtitle_tracks_from_manifest,
    validate_bgm_layer,
    validate_evidence,
    validate_voice_subtitle_bindings,
    validate_voice_se_row,
)


def cues(texts: list[str], timings: list[tuple[int, int]] | None = None) -> list[dict]:
    if timings is None:
        timings = [(index * 1000, index * 1000 + 900) for index in range(len(texts))]
    return [
        {"start_ms": start, "end_ms": end, "text": text}
        for text, (start, end) in zip(texts, timings)
    ]


def fake_inspector(codepoints: set[int]):
    def inspect(_path: Path, face_index: int) -> dict:
        return {
            "family_names": ["Verified Game Font"],
            "codepoints": codepoints,
            "face_index": face_index,
        }

    return inspect


def fake_audio_media(_path: Path) -> dict:
    return {
        "codec_name": "vorbis",
        "sample_rate": 48000,
        "channels": 2,
        "channel_layout": "stereo",
        "duration_ms": 3000,
    }


def bound_tracks(
    event: str,
    voice_rows: list[dict],
    ja_texts: list[str],
    zh_texts: list[str],
) -> dict[str, list[dict]]:
    ja_rows: list[dict] = []
    zh_rows: list[dict] = []
    for index, (voice, ja_text, zh_text) in enumerate(
        zip(voice_rows, ja_texts, zh_texts)
    ):
        start_ms = int(voice["start_ms"])
        end_ms = start_ms + int(voice["duration_ms"])
        binding = {
            "event": event,
            "request_id": str(voice["request_id"]),
            "source_sha256": str(voice["sha256"]),
            "voice_start_ms": start_ms,
            "voice_end_ms": end_ms,
        }
        ja_cue = {
            "cue_index": index,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "text": ja_text,
            "voice_binding": binding,
        }
        ja_rows.append({key: value for key, value in ja_cue.items() if key != "cue_index"})
        zh_rows.append(
            {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": zh_text,
                "voice_binding": binding,
                "translation_provenance": {
                    "source_ja_cue_index": index,
                    "source_ja_cue_sha256": subtitle_cue_sha256(ja_cue),
                    "translator": "unit-test translator",
                    "reviewer": "unit-test human reviewer",
                    "human_approved": True,
                },
            }
        )
    return {"ja": ja_rows, "zh": zh_rows}


def audited_voice_rows() -> list[dict]:
    return [
        {
            "audio_role": "voice",
            "request_id": "1234",
            "sha256": "A" * 64,
            "start_ms": 100,
            "duration_ms": 800,
        }
    ]


def normalized_bound_tracks() -> dict[str, list[dict]]:
    rows = bound_tracks(
        "ac0001_001", audited_voice_rows(), ["日本語"], ["中文"]
    )
    return {
        language: normalize_cues(cue_rows, language=language)
        for language, cue_rows in rows.items()
    }


def verified_audio_contract(root: Path, voice_se_timeline: list[dict]) -> dict:
    bgm = root / "verified_bgm.ogg"
    bgm.write_bytes(b"verified-bgm-source")
    bgm_sha256 = hashlib.sha256(bgm.read_bytes()).hexdigest().upper()
    evidence_artifact = root / "runtime-evidence.jsonl"
    evidence_artifact.write_bytes(b'{"verified":true}\n')
    evidence_sha256 = hashlib.sha256(
        evidence_artifact.read_bytes()
    ).hexdigest().upper()
    evidence_reference = {
        "path": str(evidence_artifact),
        "sha256": evidence_sha256,
        "locator": "unit-test row 1",
    }
    profile_evidence = {
        "kind": "official_runtime",
        "references": [evidence_reference],
        "fields": ["voice_se_preserved", "bgm_policy"],
    }
    return {
        "schema": AUDIO_MASTER_CONTRACT_SCHEMA,
        "voice_se_timeline": voice_se_timeline,
        "profiles": {
            "no_bgm": {
                "evidence": profile_evidence,
                "bgm_layers": [],
            },
            "with_bgm": {
                "evidence": profile_evidence,
                "bgm_layers": [
                    {
                        "source": {
                            "path": str(bgm),
                            "sha256": bgm_sha256,
                            "resource_id": "unit_test_bgm",
                        },
                        "start_ms": 0,
                        "end_ms": 2000,
                        "source_offset_ms": 125,
                        "loop": True,
                        "loop_start_ms": 0,
                        "loop_end_ms": 1500,
                        "volume": 1.0,
                        "volume_unit": "linear",
                        "volume_transitions": [
                            {
                                "at_ms": 0,
                                "volume": 1.0,
                                "volume_unit": "linear",
                                "kind": "initial",
                            }
                        ],
                        "evidence": {
                            "kind": "verified_static_logic",
                            "references": [evidence_reference],
                            "fields": [
                                "source",
                                "timing",
                                "volume",
                                "loop_phase",
                                "transitions",
                            ],
                        },
                    }
                ],
            },
        },
    }


class SubtitleEditionContractTests(unittest.TestCase):
    def test_evidence_rejects_unhashed_string_references(self) -> None:
        with self.assertRaisesRegex(ValueError, "bind path, sha256, and locator"):
            validate_evidence(
                {
                    "kind": "official_runtime",
                    "references": ["self-declared trace"],
                    "fields": ["source"],
                },
                label="test",
                fields={"source"},
                manifest_path=None,
            )

    def test_voice_se_row_requires_source_hash_and_mix_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "voice.ogg"
            source.write_bytes(b"voice")
            with self.assertRaisesRegex(ValueError, "full source SHA-256"):
                validate_voice_se_row(
                    {
                        "path": str(source),
                        "start_ms": 0,
                        "duration_ms": 100,
                        "source_offset_ms": 0,
                    },
                    index=0,
                    manifest_path=None,
                    render_duration_ms=1000,
                )

    def test_opaque_base_scene_audio_is_forbidden_from_no_bgm_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "mixed.ogg"
            source.write_bytes(b"opaque-mix")
            digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            with self.assertRaisesRegex(ValueError, "could hide BGM"):
                validate_voice_se_row(
                    {
                        "path": str(source),
                        "sha256": digest,
                        "audio_role": "base_scene_audio",
                    },
                    index=0,
                    manifest_path=None,
                    render_duration_ms=1000,
                )

    def test_audio_source_timing_must_fit_probed_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "voice.ogg"
            source.write_bytes(b"voice")
            digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            with self.assertRaisesRegex(ValueError, "source duration"):
                validate_voice_se_row(
                    {
                        "path": str(source),
                        "sha256": digest,
                        "audio_role": "voice",
                        "identity": "request:test",
                        "request_id": "1",
                        "start_ms": 0,
                        "duration_ms": 100,
                        "source_offset_ms": 0,
                        "volume": 1.0,
                        "volume_unit": "linear",
                    },
                    index=0,
                    manifest_path=None,
                    render_duration_ms=1000,
                    media_inspector=lambda _path: {"duration_ms": 50},
                )

    def test_bgm_layer_requires_end_phase_loop_and_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "bgm.ogg"
            source.write_bytes(b"bgm")
            digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            with self.assertRaisesRegex(ValueError, "end_ms/source_offset_ms"):
                validate_bgm_layer(
                    {
                        "source": {"path": str(source), "sha256": digest},
                        "start_ms": 0,
                        "volume": 50,
                        "volume_unit": "game_parameter",
                    },
                    index=0,
                    manifest_path=None,
                )

    def test_legacy_subtitles_are_japanese_and_compatibility_remains_two_editions(self) -> None:
        manifest = {"event": "ac0001_001", "subtitles": cues(["日本語"]), "audio": []}
        tracks = subtitle_tracks_from_manifest(manifest)

        self.assertEqual(list(tracks), ["ja"])
        self.assertEqual(
            normalize_requested_editions(None, legacy_compat=True),
            ["none", "ja"],
        )
        self.assertEqual(normalize_requested_editions(None), ["none", "ja", "zh"])

    def test_legacy_and_new_japanese_tracks_must_agree(self) -> None:
        manifest = {
            "subtitles": cues(["旧"]),
            "subtitle_tracks": {"ja": cues(["新"])},
        }

        with self.assertRaisesRegex(ValueError, "disagree"):
            subtitle_tracks_from_manifest(manifest)

    def test_three_editions_share_timing_and_audio_without_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ja_font = root / "verified-ja.ttf"
            zh_font = root / "verified-zh.ttf"
            ja_font.write_bytes(b"verified-game-font-evidence")
            zh_font.write_bytes(b"audited-complete-chinese-font-evidence")
            ja_digest = hashlib.sha256(ja_font.read_bytes()).hexdigest().upper()
            zh_digest = hashlib.sha256(zh_font.read_bytes()).hexdigest().upper()
            layout_evidence = root / "layout-evidence.json"
            layout_evidence.write_bytes(b'{"layout":"verified"}\n')
            layout_evidence_sha256 = hashlib.sha256(
                layout_evidence.read_bytes()
            ).hexdigest().upper()
            font_config = {
                "schema": "magireco-subtitle-fonts-v1",
                "_config_path": str(root / "fonts.json"),
                "fonts": {
                    "ja": {
                        "path": str(ja_font),
                        "family": "Verified Game Font",
                        "sha256": ja_digest,
                        "source": {
                            "kind": "verified_game_asset",
                            "evidence": "unit-test provenance",
                            "license": "unit-test game asset render scope",
                        },
                    },
                    "zh": {
                        "path": str(zh_font),
                        "family": "Verified Game Font",
                        "sha256": zh_digest,
                        "source": {
                            "kind": "audited_chinese_fallback",
                            "evidence": "unit-test provenance",
                            "license": "unit-test permissive font license",
                        },
                    },
                },
                "layout_profile": {
                    "id": "verified-game-layout",
                    "style": {
                        "font_size": 16,
                        "primary_colour": "&H00FFFFFF",
                        "outline_colour": "&H00000000",
                        "border_style": 1,
                        "outline": 1,
                        "shadow": 0,
                        "margin_v": 12,
                        "alignment": 2,
                    },
                    "evidence": {
                        "kind": "official_runtime",
                        "references": [
                            {
                                "path": str(layout_evidence),
                                "sha256": layout_evidence_sha256,
                                "locator": "unit-test verified layout",
                            }
                        ],
                        "fields": [
                            "font_size",
                            "colours",
                            "outline",
                            "position",
                        ],
                    },
                },
            }
            voice = root / "voice.ogg"
            voice.write_bytes(b"verified-voice-source")
            voice_sha256 = hashlib.sha256(voice.read_bytes()).hexdigest().upper()
            audio_evidence = root / "voice-evidence.jsonl"
            audio_evidence.write_bytes(b'{"voice":true}\n')
            audio_evidence_sha256 = hashlib.sha256(
                audio_evidence.read_bytes()
            ).hexdigest().upper()
            voice_se_timeline = [
                {
                    "path": str(voice),
                    "sha256": voice_sha256,
                    "audio_role": "voice",
                    "identity": "request:unit-test-voice",
                    "request_id": "1234",
                    "code_name": "unit_test_voice",
                    "start_ms": 0,
                    "duration_ms": 900,
                    "source_offset_ms": 0,
                    "volume": 50,
                    "volume_unit": "game_parameter",
                    "evidence": {
                        "kind": "official_runtime",
                        "references": [
                            {
                                "path": str(audio_evidence),
                                "sha256": audio_evidence_sha256,
                                "locator": "unit-test voice request",
                            }
                        ],
                        "fields": ["source", "timing", "identity", "volume"],
                    },
                }
            ]
            voice_se_timeline.append(
                {
                    **voice_se_timeline[0],
                    "identity": "request:unit-test-voice-2",
                    "request_id": "1235",
                    "code_name": "unit_test_voice_2",
                    "start_ms": 1000,
                }
            )
            tracks = bound_tracks(
                "ac0001_001",
                voice_se_timeline,
                ["いろは", "まどか"],
                ["环彩羽", "鹿目圆"],
            )
            visible = {
                ord(char)
                for rows in tracks.values()
                for row in rows
                for char in row["text"]
            }
            plan = build_edition_plan(
                {
                    "event": "ac0001_001",
                    "subtitle_tracks": tracks,
                    "audio": voice_se_timeline,
                    "audio_master_contract": verified_audio_contract(
                        root, voice_se_timeline
                    ),
                    "render_duration_ms": 2000,
                    "native_dimensions": {"width": 416, "height": 232},
                },
                editions=["none", "ja", "zh"],
                font_config=font_config,
                font_inspector=fake_inspector(visible),
                audio_media_inspector=fake_audio_media,
                manifest_path=root / "manifest.json",
            )

        self.assertEqual(plan["requested_editions"], ["none", "ja", "zh"])
        self.assertFalse(plan["translation_performed"])
        self.assertEqual(plan["edition_count"], 6)
        self.assertEqual(
            plan["requested_audio_profiles"], ["with_bgm", "no_bgm"]
        )
        self.assertEqual(
            plan["tracks"]["ja"]["timeline_sha256"],
            plan["tracks"]["zh"]["timeline_sha256"],
        )
        self.assertTrue(plan["tracks"]["ja"]["font"]["coverage_complete"])
        self.assertEqual(
            plan["subtitle_layout"]["id"], "verified-game-layout"
        )
        self.assertNotEqual(
            plan["tracks"]["ja"]["font"]["sha256"],
            plan["tracks"]["zh"]["font"]["sha256"],
        )
        self.assertEqual(
            plan["tracks"]["zh"]["font"]["source"]["kind"],
            "audited_chinese_fallback",
        )
        self.assertEqual(
            plan["subtitle_voice_binding"]["mode"],
            "one_voice_to_one_cue_per_language",
        )
        self.assertEqual(plan["subtitle_voice_binding"]["voice_row_count"], 2)

    def test_missing_translation_track_fails_instead_of_translating(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not translate"):
            build_edition_plan(
                {"subtitles": cues(["日本語"])},
                editions=["none", "ja", "zh"],
            )

    def test_mismatched_ja_zh_timeline_fails_closed(self) -> None:
        manifest = {
            "subtitle_tracks": {
                "ja": cues(["日本語"], [(0, 900)]),
                "zh": cues(["中文"], [(100, 1000)]),
            }
        }
        with self.assertRaisesRegex(ValueError, "timing mismatch"):
            build_edition_plan(
                manifest,
                editions=["none", "ja", "zh"],
            )

    def test_voice_rows_require_non_empty_japanese_and_chinese_tracks(self) -> None:
        tracks = normalized_bound_tracks()
        tracks["zh"] = []
        with self.assertRaisesRegex(ValueError, "non-empty zh subtitle track"):
            validate_voice_subtitle_bindings(
                event="ac0001_001",
                tracks=tracks,
                voice_se_timeline=audited_voice_rows(),
            )

    def test_voice_cue_binding_rejects_request_hash_and_timing_mismatch(self) -> None:
        mismatch_cases = {
            "request": ("request_id", "9999", "does not match"),
            "source hash": ("source_sha256", "B" * 64, "does not match"),
        }
        for name, (field, value, message) in mismatch_cases.items():
            with self.subTest(name=name):
                tracks = normalized_bound_tracks()
                tracks["ja"][0]["voice_binding"][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    validate_voice_subtitle_bindings(
                        event="ac0001_001",
                        tracks=tracks,
                        voice_se_timeline=audited_voice_rows(),
                    )

        tracks = normalized_bound_tracks()
        tracks["ja"][0]["end_ms"] = 899
        with self.assertRaisesRegex(ValueError, "does not cover"):
            validate_voice_subtitle_bindings(
                event="ac0001_001",
                tracks=tracks,
                voice_se_timeline=audited_voice_rows(),
            )

    def test_unbound_or_duplicate_cues_fail_closed(self) -> None:
        tracks = normalized_bound_tracks()
        tracks["ja"].append(copy.deepcopy(tracks["ja"][0]))
        tracks["ja"][1]["cue_index"] = 1
        with self.assertRaisesRegex(ValueError, "duplicate cues"):
            validate_voice_subtitle_bindings(
                event="ac0001_001",
                tracks=tracks,
                voice_se_timeline=audited_voice_rows(),
            )

        with self.assertRaisesRegex(ValueError, "therefore unbound"):
            validate_voice_subtitle_bindings(
                event="ac0001_001",
                tracks=normalized_bound_tracks(),
                voice_se_timeline=[],
            )

    def test_chinese_translation_provenance_is_bound_and_human_approved(self) -> None:
        cases = [
            (
                "missing provenance",
                lambda provenance: None,
                "translation_provenance must be an object",
            ),
            (
                "wrong Japanese hash",
                lambda provenance: provenance.update(
                    {"source_ja_cue_sha256": "B" * 64}
                ),
                "source Japanese cue SHA256 mismatch",
            ),
            (
                "no translator or model",
                lambda provenance: provenance.update({"translator": ""}),
                "requires translator or translation_method",
            ),
            (
                "no reviewer",
                lambda provenance: provenance.update({"reviewer": ""}),
                "reviewer is required",
            ),
            (
                "not human approved",
                lambda provenance: provenance.update({"human_approved": False}),
                "human_approved must be true",
            ),
        ]
        for name, (mutate, message) in {
            case_name: (mutation, expected)
            for case_name, mutation, expected in cases
        }.items():
            with self.subTest(name=name):
                tracks = normalized_bound_tracks()
                provenance = tracks["zh"][0].get("translation_provenance")
                result = mutate(provenance)
                if name == "missing provenance":
                    tracks["zh"][0]["translation_provenance"] = result
                with self.assertRaisesRegex(ValueError, message):
                    validate_voice_subtitle_bindings(
                        event="ac0001_001",
                        tracks=tracks,
                        voice_se_timeline=audited_voice_rows(),
                    )

    def test_chinese_translation_method_and_model_can_replace_named_translator(self) -> None:
        tracks = normalized_bound_tracks()
        provenance = tracks["zh"][0]["translation_provenance"]
        provenance["translator"] = ""
        provenance["translation_method"] = {
            "method": "machine_translation",
            "model": "audited-test-model",
        }

        result = validate_voice_subtitle_bindings(
            event="ac0001_001",
            tracks=tracks,
            voice_se_timeline=audited_voice_rows(),
        )

        self.assertEqual(result["voice_row_count"], 1)
        self.assertEqual(result["bound_cue_count"], {"ja": 1, "zh": 1})

    def test_subtitles_require_explicit_font_no_yu_gothic_fallback(self) -> None:
        with self.assertRaisesRegex(ValueError, "implicit system font fallback"):
            build_edition_plan(
                {"subtitles": cues(["日本語"])},
                editions=["none", "ja"],
            )

    def test_font_coverage_and_source_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            font = Path(temp_dir) / "font.ttf"
            font.write_bytes(b"font-evidence")
            config = {
                "fonts": {
                    "ja": {
                        "path": str(font),
                        "family": "Verified Game Font",
                        "source": {
                            "kind": "verified_game_asset",
                            "evidence": "unit-test provenance",
                            "license": "unit-test game asset render scope",
                        },
                    }
                }
            }
            with self.assertRaisesRegex(ValueError, "coverage missing"):
                build_edition_plan(
                    {"subtitles": cues(["日本語"])},
                    editions=["none", "ja"],
                    font_config=config,
                    font_inspector=fake_inspector({ord("日"), ord("本")}),
                )
            del config["fonts"]["ja"]["source"]
            with self.assertRaisesRegex(ValueError, "source.kind"):
                build_edition_plan(
                    {"subtitles": cues(["日本語"])},
                    editions=["none", "ja"],
                    font_config=config,
                    font_inspector=fake_inspector({ord(c) for c in "日本語"}),
                )

    def test_font_binding_requires_explicit_license(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            font = Path(temp_dir) / "font.ttf"
            font.write_bytes(b"font-evidence")
            config = {
                "fonts": {
                    "ja": {
                        "path": str(font),
                        "family": "Verified Game Font",
                        "source": {
                            "kind": "verified_game_asset",
                            "evidence": "unit-test provenance",
                        },
                    }
                }
            }
            with self.assertRaisesRegex(ValueError, "source.license"):
                build_edition_plan(
                    {"subtitles": cues(["日本語"])},
                    editions=["none", "ja"],
                    font_config=config,
                    font_inspector=fake_inspector({ord(c) for c in "日本語"}),
                )

    def test_new_and_legacy_render_manifests_normalize(self) -> None:
        legacy = normalize_render_editions(
            {
                "without_subtitles": "none.mp4",
                "with_subtitles": "ja.mp4",
                "subtitles": "ja.srt",
            }
        )
        modern = normalize_render_editions(
            {
                "editions": {
                    "none": {"video": "none.mp4"},
                    "ja": {"video": "ja.mp4", "subtitles": "ja.srt"},
                    "zh": {"video": "zh.mp4", "subtitles": "zh.srt"},
                }
            }
        )

        self.assertEqual(set(legacy), {"none", "ja"})
        self.assertEqual(set(modern), {"none", "ja", "zh"})
        self.assertEqual(modern["zh"]["video"], "zh.mp4")

    def test_render_edition_language_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "declares language"):
            normalize_render_editions(
                {
                    "editions": {
                        "none": {"video": "none.mp4"},
                        "zh": {
                            "language": "ja",
                            "video": "wrong.mp4",
                            "subtitles": "wrong.srt",
                        },
                    }
                }
            )

    def test_default_matrix_refuses_missing_audio_master_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "audio_master_contract"):
            build_edition_plan(
                {
                    "subtitle_tracks": {"ja": [], "zh": []},
                    "audio": [],
                }
            )

    def test_render_matrix_requires_shared_audio_per_profile(self) -> None:
        good_hash = "A" * 64
        bad_hash = "B" * 64
        matrix = {
            profile: {
                "audio_profile": profile,
                "editions": {
                    "none": {
                        "video": f"{profile}-none.mp4",
                        "audio_sha256": good_hash,
                    },
                    "ja": {
                        "video": f"{profile}-ja.mp4",
                        "subtitles": f"{profile}-ja.srt",
                        "audio_sha256": (
                            bad_hash if profile == "with_bgm" else good_hash
                        ),
                    },
                    "zh": {
                        "video": f"{profile}-zh.mp4",
                        "subtitles": f"{profile}-zh.srt",
                        "audio_sha256": good_hash,
                    },
                },
            }
            for profile in ("with_bgm", "no_bgm")
        }
        with self.assertRaisesRegex(ValueError, "share one audio hash"):
            normalize_render_edition_matrix({"edition_matrix": matrix})

    def test_render_matrix_requires_distinct_audio_masters(self) -> None:
        shared_hash = "A" * 64
        matrix = {
            profile: {
                "audio_profile": profile,
                "editions": {
                    edition: {
                        "video": f"{profile}-{edition}.mp4",
                        "subtitles": "" if edition == "none" else f"{edition}.srt",
                        "audio_sha256": shared_hash,
                    }
                    for edition in ("none", "ja", "zh")
                },
            }
            for profile in ("with_bgm", "no_bgm")
        }
        with self.assertRaisesRegex(ValueError, "different audio hashes"):
            normalize_render_edition_matrix({"edition_matrix": matrix})


if __name__ == "__main__":
    unittest.main()
