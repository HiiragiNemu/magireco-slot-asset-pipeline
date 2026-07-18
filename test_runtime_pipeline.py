from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.generate_verified_family_composition_plans import (
    ac0912_plan,
    lev_plan,
)
from tools.frida_runtime_probe.build_event_production_manifests import (
    apply_path_prefix_maps,
    apply_runtime_voice_subtitle_overrides,
    file_sha256,
    filter_subtitle_rows_for_plan,
    load_runtime_event_manifests,
    load_voice_subtitle_overrides,
    merge_runtime_graphical_subtitle_rows,
    parse_path_prefix_maps,
    quantize_duration_to_frame_grid,
)
from tools.frida_runtime_probe.composition_contract import (
    presentation_sample_count,
)
from tools.frida_runtime_probe.resolve_subtitle_voice_catalog import (
    request_speaker,
    speaker_hint,
)
from tools.frida_runtime_probe.resolve_official_event_capture import (
    is_dialogue_sound,
    sound_resource_id,
    voice_label_text,
)
from tools.frida_runtime_probe.build_series_editions import (
    event_sort_key,
    shifted_srt_cues,
)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class CompositionPlanTests(unittest.TestCase):
    def test_runtime_manifest_equivalent_duplicates_preserve_all_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first" / "event_manifest.json"
            second = root / "second" / "event_manifest.json"
            first.parent.mkdir()
            second.parent.mkdir()
            payload = {
                "event": "ac7114_001",
                "video_assets": [{"target_mp4": "D:/verified/ac7114.mp4"}],
                "sound_assets": [{"request_id": "9001", "relative_ms": 120}],
                "subtitles": [{"text": "test", "relative_ms": 120}],
                "_source_path": "stale-loader-value-one",
            }
            first.write_text(json.dumps(payload), encoding="utf-8")
            second_payload = json.loads(json.dumps(payload))
            second_payload["_source_path"] = "stale-loader-value-two"
            second_payload["_source_paths"] = ["stale-loader-value-two"]
            second.write_text(
                json.dumps(second_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            loaded = load_runtime_event_manifests([first.parent, second.parent])

            self.assertEqual(list(loaded), ["ac7114_001"])
            manifest = loaded["ac7114_001"]
            expected_paths = [str(first.resolve()), str(second.resolve())]
            self.assertEqual(manifest["_source_path"], expected_paths[0])
            self.assertEqual(manifest["_source_paths"], expected_paths)
            self.assertEqual(
                [row["path"] for row in manifest["_source_provenance"]],
                expected_paths,
            )
            self.assertEqual(
                [row["sha256"] for row in manifest["_source_provenance"]],
                [file_sha256(first), file_sha256(second)],
            )
            self.assertEqual(manifest["video_assets"], payload["video_assets"])

    def test_runtime_manifest_conflicting_duplicate_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first" / "event_manifest.json"
            second = root / "second" / "event_manifest.json"
            first.parent.mkdir()
            second.parent.mkdir()
            payload = {
                "event": "ac7114_001",
                "video_assets": [{"target_mp4": "D:/verified/ac7114.mp4"}],
                "sound_assets": [{"request_id": "9001", "relative_ms": 120}],
            }
            first.write_text(json.dumps(payload), encoding="utf-8")
            conflicting = json.loads(json.dumps(payload))
            conflicting["sound_assets"][0]["request_id"] = "9002"
            second.write_text(json.dumps(conflicting), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                r"conflicting runtime event manifests for ac7114_001",
            ) as raised:
                load_runtime_event_manifests([first.parent, second.parent])

            message = str(raised.exception)
            self.assertIn(str(first.resolve()), message)
            self.assertIn(str(second.resolve()), message)

    def test_explicit_path_prefix_map_relocates_nested_backup_paths(self) -> None:
        mappings = parse_path_prefix_maps(
            [
                "A:\\magireco_bili_fulltest_20260603="
                "D:\\magia\\MyProducts\\casino\\magireco_bili_fulltest_20260603"
            ]
        )
        payload = {
            "video_assets": [
                {
                    "target_mp4": (
                        "a:/MAGIRECO_BILI_FULLTEST_20260603/"
                        "cri_official_video_map/ac7116.mp4"
                    )
                }
            ],
            "unrelated": "A:\\magireco_bili_fulltest_202606030\\keep.txt",
        }
        relocated = apply_path_prefix_maps(payload, mappings)
        self.assertEqual(
            relocated["video_assets"][0]["target_mp4"],
            "D:\\magia\\MyProducts\\casino\\magireco_bili_fulltest_20260603\\"
            "cri_official_video_map\\ac7116.mp4",
        )
        self.assertEqual(relocated["unrelated"], payload["unrelated"])
        self.assertEqual(
            payload["video_assets"][0]["target_mp4"],
            "a:/MAGIRECO_BILI_FULLTEST_20260603/"
            "cri_official_video_map/ac7116.mp4",
        )

    def test_path_prefix_map_rejects_implicit_or_blank_relocation(self) -> None:
        for value in ("A:\\old", "=D:\\new", "A:\\old="):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_path_prefix_maps([value])

    def test_render_duration_is_extended_to_complete_cfr_frame(self) -> None:
        ac7116 = quantize_duration_to_frame_grid(13027, "30/1")
        self.assertEqual(ac7116["frame_count"], 391)
        self.assertEqual(ac7116["duration_ms"], 13033)
        self.assertEqual(ac7116["padding_ms"], 6)
        self.assertEqual(ac7116["exact_duration_ms_numerator"], 39100)
        self.assertEqual(ac7116["exact_duration_ms_denominator"], 3)
        self.assertEqual(ac7116["audio_sample_count"], 625600)

        aligned = quantize_duration_to_frame_grid(1000, "30/1")
        self.assertEqual(aligned["frame_count"], 30)
        self.assertEqual(aligned["duration_ms"], 1000)
        self.assertEqual(aligned["padding_ms"], 0)

        ntsc = quantize_duration_to_frame_grid(1000, "30000/1001")
        self.assertEqual(ntsc["frame_count"], 30)
        self.assertEqual(ntsc["duration_ms"], 1001)
        self.assertGreaterEqual(ntsc["duration_ms"], ntsc["content_end_ms"])

    def test_render_duration_rejects_invalid_frame_grid(self) -> None:
        for value in ("", "30", "0/1", "30/0", "bad/1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    quantize_duration_to_frame_grid(13027, value)
        with self.assertRaises(ValueError):
            quantize_duration_to_frame_grid(0, "30/1")

    def test_presentation_samples_follow_exact_frame_grid(self) -> None:
        quantization = quantize_duration_to_frame_grid(13027, "30/1")
        manifest = {
            "native_frame_rate": "30/1",
            "render_frame_count": quantization["frame_count"],
            "render_duration_ms": quantization["duration_ms"],
            "render_duration_quantization": quantization,
        }
        self.assertEqual(presentation_sample_count(manifest), 625600)

        for field, value in (
            ("frame_count", 390),
            ("duration_ms", 13034),
            ("audio_sample_count", 625599),
            ("exact_duration_ms_numerator", 39000),
        ):
            with self.subTest(field=field):
                tampered = json.loads(json.dumps(manifest))
                tampered["render_duration_quantization"][field] = value
                with self.assertRaises(RuntimeError):
                    presentation_sample_count(tampered)

    def test_legacy_presentation_samples_are_exact_at_48_khz(self) -> None:
        self.assertEqual(
            presentation_sample_count({"render_duration_ms": 13033}),
            625584,
        )

    def test_graphical_only_subtitle_keeps_text_without_false_voice_binding(self) -> None:
        rows = [
            {
                "text": "ごめんね…",
                "start_ms": 100,
                "end_ms": 900,
                "voice_request_id": "8894",
                "voice_start_ms": 100,
                "z2d_name": "cap7115_sp4_kdpl_kae_006",
                "speaker_code": "mad",
                "subtitle_source": "runtime_voice_and_graphical_text",
                "evidence": "legacy_text_similarity",
            }
        ]
        filtered = filter_subtitle_rows_for_plan(
            rows,
            {
                "graphical_only_subtitle_z2d_names": [
                    "cap7115_sp4_kdpl_kae_006"
                ]
            },
        )
        self.assertEqual(filtered[0]["text"], "ごめんね…")
        self.assertEqual(filtered[0]["voice_request_id"], "")
        self.assertEqual(filtered[0]["voice_start_ms"], 0)
        self.assertEqual(filtered[0]["speaker_code"], "")
        self.assertEqual(filtered[0]["subtitle_source"], "graphical_display_text")

    def test_lev_plan_separates_title_overlay_from_backgrounds(self) -> None:
        plan = lev_plan(
            {
                "event": "ac1102_001",
                "render_duration_ms": 7000,
                "clips": [
                    {
                        "dgm_name": "ac1102_lev_title_wht",
                        "event_start_ms": 0,
                    },
                    {
                        "dgm_name": "ac1102_lev_c001_S",
                        "event_start_ms": 0,
                    },
                    {
                        "dgm_name": "ac1102_lev_c002",
                        "event_start_ms": 1667,
                    },
                    {
                        "dgm_name": "ac1102_lev_c002_LP",
                        "event_start_ms": 5500,
                    },
                ],
            }
        )
        self.assertIsNotNone(plan)
        roles = {row["dgm_name"]: row["role"] for row in plan["clips"]}
        self.assertEqual(roles["ac1102_lev_title_wht"], "screen_overlay")
        self.assertEqual(roles["ac1102_lev_c002_LP"], "loop_background")

    def test_ac0912_plan_keeps_qb_loop_as_screen_overlay(self) -> None:
        plan = ac0912_plan(
            {
                "event": "ac0912_104",
                "render_duration_ms": 8500,
                "clips": [
                    {
                        "dgm_name": "ac0912_cmn_sQB_guide_3on_S_ef_flash",
                        "event_start_ms": 0,
                    },
                    {
                        "dgm_name": "ac0912_cmn_sQB_guide_3on_S_chance",
                        "event_start_ms": 500,
                    },
                    {
                        "dgm_name": "ac0912_cmn_sQB_guide_3on_S_chance_LP",
                        "event_start_ms": 4500,
                    },
                    {
                        "dgm_name": "ac0912_cmn_sQB_guide_3on_QB",
                        "event_start_ms": 500,
                    },
                    {
                        "dgm_name": "ac0912_cmn_sQB_guide_3on_QB_LP",
                        "event_start_ms": 3133,
                    },
                ],
            }
        )
        self.assertIsNotNone(plan)
        roles = {row["dgm_name"]: row["role"] for row in plan["clips"]}
        self.assertEqual(
            roles["ac0912_cmn_sQB_guide_3on_QB_LP"],
            "loop_screen_overlay",
        )


class SubtitleVoiceCatalogTests(unittest.TestCase):
    def test_event_sound_labels_are_not_dialogue(self) -> None:
        self.assertFalse(
            is_dialogue_sound("42020_SPストーリー2_00_突入", "突入")
        )
        self.assertFalse(
            is_dialogue_sound(
                "35615_ac5203_2_特化ﾏﾐ_ﾏﾐ攻撃_1確SE",
                "特化ﾏﾐ_ﾏﾐ攻撃_1確SE",
            )
        )
        self.assertTrue(
            is_dialogue_sound(
                "30995_303_say_マミさんは、私達を",
                "マミさんは、私達を",
            )
        )
        self.assertTrue(
            is_dialogue_sound(
                "26427_sqb_小さいキュゥべえ_ッキュ",
                "ッキュ",
            )
        )

    def test_voice_label_strips_scene_context(self) -> None:
        self.assertEqual(
            voice_label_text("17797_fer_AT_女王グマ_あああああ"),
            "あああああ",
        )
        self.assertEqual(
            voice_label_text("20050_ari_AT_AMセリフ_それならアリナがパーフ-"),
            "それならアリナがパーフ-",
        )

    def test_numeric_only_sound_code_resolves_short_resource_id(self) -> None:
        self.assertEqual(sound_resource_id("551"), "551")
        self.assertEqual(
            sound_resource_id("26032_kuroe_宝崎線_環さんはこんな話聞いたこ-"),
            "26032",
        )
        self.assertEqual(sound_resource_id("not_a_sound_code"), "")

    def test_numeric_tokens_do_not_hide_z2d_speaker_alias(self) -> None:
        self.assertEqual(
            speaker_hint("31209_315_mita_心の闇を背負った"),
            "mit",
        )

    def test_long_request_speaker_aliases_are_normalized(self) -> None:
        self.assertEqual(
            request_speaker("31209_315_mita_心の闇を背負った"),
            "mit",
        )
        self.assertEqual(
            request_speaker("30757_343_kuroe_このままじゃ"),
            "kuro",
        )


class SeriesEditionTests(unittest.TestCase):
    def test_event_order_is_natural(self) -> None:
        events = ["ac1102_010", "ac1102_002", "ac1102_001"]
        self.assertEqual(
            sorted(events, key=event_sort_key),
            ["ac1102_001", "ac1102_002", "ac1102_010"],
        )

    def test_srt_cues_are_shifted_by_event_offset(self) -> None:
        cues = shifted_srt_cues(
            "1\n00:00:00,100 --> 00:00:00,900\n台詞\n",
            2000,
        )
        self.assertEqual(
            cues,
            [{"start_ms": 2100, "end_ms": 2900, "text": "台詞"}],
        )


class ManifestBuilderTests(unittest.TestCase):
    def test_runtime_voice_override_replaces_truncated_label(self) -> None:
        rows = apply_runtime_voice_subtitle_overrides(
            [
                {
                    "text": "負けるもんか-",
                    "start_ms": 798,
                    "end_ms": 7118,
                    "voice_request_id": "7856",
                    "voice_start_ms": 898,
                    "speaker_code": "say",
                    "subtitle_source": "official_runtime_capture",
                }
            ],
            {
                "7856": {
                    "text": "負けるもんか！",
                    "source": "curated_official_prefix_and_large_v3_consensus",
                }
            },
        )
        self.assertEqual(rows[0]["text"], "負けるもんか！")
        self.assertEqual(
            rows[0]["subtitle_source"], "official_voice_asr_verified"
        )

    def test_runtime_subtitles_keep_unmatched_graphical_text(self) -> None:
        merged = merge_runtime_graphical_subtitle_rows(
            [
                {
                    "text": "かえで！ しっかりして！",
                    "start_ms": 100,
                    "end_ms": 900,
                }
            ],
            [
                {
                    "display_text": "かえで！\\nしっかりして！",
                    "subtitle_start_ms": "90",
                    "subtitle_end_ms": "910",
                    "timeline_confidence": "exact_gdb_frame_and_official_ogg",
                },
                {
                    "display_text": "ごめんね…",
                    "subtitle_start_ms": "1000",
                    "subtitle_end_ms": "1800",
                    "timeline_confidence": "exact_gdb_frame_only",
                },
                {
                    "display_text": "かえで！",
                    "subtitle_start_ms": "120",
                    "subtitle_end_ms": "500",
                    "timeline_confidence": "exact_gdb_frame_only",
                },
                {
                    "display_text": "空白のテキストレイヤー",
                    "subtitle_start_ms": "1900",
                    "subtitle_end_ms": "2200",
                    "timeline_confidence": "exact_gdb_frame_only",
                },
            ],
        )
        self.assertEqual([row["text"] for row in merged], ["かえで！ しっかりして！", "ごめんね…"])

    def test_req_sound_is_kept_when_event_has_no_subtitle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clip = root / "clip.mp4"
            base_audio = root / "base.ogg"
            voice_audio = root / "voice.ogg"
            for path in (clip, base_audio, voice_audio):
                path.touch()

            catalog = root / "catalog.csv"
            clips = root / "clips.csv"
            audio = root / "audio.csv"
            sounds = root / "sounds.csv"
            subtitles = root / "subtitles.csv"
            out_dir = root / "out"
            write_csv(
                catalog,
                [
                    "event_name",
                    "automatic_candidate",
                    "classification",
                    "code_hex",
                ],
                [
                    {
                        "event_name": "ac_test_001",
                        "automatic_candidate": "yes",
                        "classification": "native_full_frame_only",
                        "code_hex": "0x1",
                    }
                ],
            )
            write_csv(
                clips,
                [
                    "event_name",
                    "z2d_order",
                    "dgm_order",
                    "dgm_name",
                    "dgm_role",
                    "event_start_ms",
                    "event_end_ms",
                    "width",
                    "height",
                    "frame_rate",
                    "media_class",
                    "target_mp4",
                    "source_mp4",
                    "interval_confidence",
                ],
                [
                    {
                        "event_name": "ac_test_001",
                        "z2d_order": 0,
                        "dgm_order": 0,
                        "dgm_name": "clip",
                        "dgm_role": "single_layer_segment",
                        "event_start_ms": 0,
                        "event_end_ms": 1000,
                        "width": 416,
                        "height": 232,
                        "frame_rate": "30/1",
                        "media_class": "full_frame_landscape",
                        "target_mp4": clip,
                        "source_mp4": clip,
                        "interval_confidence": "exact_duration_unique",
                    }
                ],
            )
            write_csv(
                audio,
                [
                    "primary_animation",
                    "start_ms",
                    "parent_sound_order",
                    "reqdata_index",
                    "leaf_request_id",
                    "leaf_code_name",
                    "ogg_name",
                    "ogg_path",
                    "duration_ms",
                ],
                [
                    {
                        "primary_animation": "ac_test_001",
                        "start_ms": 0,
                        "parent_sound_order": 0,
                        "reqdata_index": 0,
                        "leaf_request_id": "10",
                        "leaf_code_name": "base",
                        "ogg_name": base_audio.name,
                        "ogg_path": base_audio,
                        "duration_ms": 1000,
                    }
                ],
            )
            write_csv(
                sounds,
                [
                    "event_name",
                    "ogg_exists",
                    "timeline_confidence",
                    "audio_start_ms",
                    "z2d_order",
                    "callback_index",
                    "sound_request_id",
                    "sound_code_name",
                    "ogg_name",
                    "ogg_path",
                    "sound_duration_ms",
                    "z2d_name",
                    "callback_exec_frame",
                    "absolute_start_frame",
                ],
                [
                    {
                        "event_name": "ac_test_001",
                        "ogg_exists": "yes",
                        "timeline_confidence": (
                            "exact_gdb_child_frame_callback_frame_and_official_ogg"
                        ),
                        "audio_start_ms": 100,
                        "z2d_order": 0,
                        "callback_index": 0,
                        "sound_request_id": "20",
                        "sound_code_name": "voice_without_subtitle",
                        "ogg_name": voice_audio.name,
                        "ogg_path": voice_audio,
                        "sound_duration_ms": 500,
                        "z2d_name": "cap_test",
                        "callback_exec_frame": 3,
                        "absolute_start_frame": 3,
                    }
                ],
            )
            write_csv(
                subtitles,
                [
                    "event_name",
                    "display_text",
                    "timeline_confidence",
                    "start_ms",
                    "effective_end_ms",
                    "audio_start_ms",
                    "sound_request_id",
                    "z2d_name",
                    "z2d_order",
                    "srt_text",
                ],
                [],
            )

            script = (
                Path(__file__).resolve().parent
                / "tools"
                / "frida_runtime_probe"
                / "build_event_production_manifests.py"
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--event-catalog",
                    str(catalog),
                    "--event-clips",
                    str(clips),
                    "--audio-components",
                    str(audio),
                    "--event-sounds",
                    str(sounds),
                    "--subtitle-timeline",
                    str(subtitles),
                    "--composition-plans",
                    str(root / "no_plans"),
                    "--out-dir",
                    str(out_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(
                (out_dir / "events" / "ac_test_001.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(manifest["subtitles"]), 0)
            self.assertEqual(
                manifest["clips"][0]["source_sha256"],
                hashlib.sha256(clip.read_bytes()).hexdigest().upper(),
            )
            self.assertTrue(
                manifest["quality_gates"]["all_clip_source_hashes_bound"]
            )
            self.assertEqual(
                [row["source"] for row in manifest["audio"]],
                ["event_audio_component", "z2d_req_sound"],
            )
            self.assertTrue(manifest["quality_gates"]["audio_timeline_ready"])
            self.assertTrue(manifest["quality_gates"]["render_ready"])

    def test_explicit_audience_component_is_not_render_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clip = root / "clip.mp4"
            voice_audio = root / "voice.ogg"
            clip.touch()
            voice_audio.touch()

            catalog = root / "catalog.csv"
            clips = root / "clips.csv"
            audio = root / "audio.csv"
            sounds = root / "sounds.csv"
            subtitles = root / "subtitles.csv"
            exclusions = root / "exclusions.json"
            out_dir = root / "out"
            write_csv(
                catalog,
                [
                    "event_name",
                    "automatic_candidate",
                    "classification",
                    "code_hex",
                ],
                [
                    {
                        "event_name": "ac_component_001",
                        "automatic_candidate": "yes",
                        "classification": "native_full_frame_only",
                        "code_hex": "0x2",
                    }
                ],
            )
            write_csv(
                clips,
                [
                    "event_name",
                    "z2d_order",
                    "dgm_order",
                    "dgm_name",
                    "dgm_role",
                    "event_start_ms",
                    "event_end_ms",
                    "width",
                    "height",
                    "frame_rate",
                    "media_class",
                    "target_mp4",
                    "source_mp4",
                    "interval_confidence",
                ],
                [
                    {
                        "event_name": "ac_component_001",
                        "z2d_order": 0,
                        "dgm_order": 0,
                        "dgm_name": "next_overlay",
                        "dgm_role": "single_layer_segment",
                        "event_start_ms": 0,
                        "event_end_ms": 1000,
                        "width": 512,
                        "height": 288,
                        "frame_rate": "30/1",
                        "media_class": "full_frame_landscape",
                        "target_mp4": clip,
                        "source_mp4": clip,
                        "interval_confidence": "exact_duration_unique",
                    }
                ],
            )
            write_csv(
                audio,
                [
                    "primary_animation",
                    "start_ms",
                    "parent_sound_order",
                    "reqdata_index",
                    "leaf_request_id",
                    "leaf_code_name",
                    "ogg_name",
                    "ogg_path",
                    "duration_ms",
                ],
                [],
            )
            write_csv(
                sounds,
                [
                    "event_name",
                    "ogg_exists",
                    "timeline_confidence",
                    "audio_start_ms",
                    "z2d_order",
                    "callback_index",
                    "sound_request_id",
                    "sound_code_name",
                    "ogg_name",
                    "ogg_path",
                    "sound_duration_ms",
                    "z2d_name",
                    "callback_exec_frame",
                    "absolute_start_frame",
                ],
                [
                    {
                        "event_name": "ac_component_001",
                        "ogg_exists": "yes",
                        "timeline_confidence": (
                            "exact_gdb_child_frame_callback_frame_and_official_ogg"
                        ),
                        "audio_start_ms": 0,
                        "z2d_order": 0,
                        "callback_index": 0,
                        "sound_request_id": "30",
                        "sound_code_name": "silent_control",
                        "ogg_name": voice_audio.name,
                        "ogg_path": voice_audio,
                        "sound_duration_ms": 1000,
                        "z2d_name": "next",
                        "callback_exec_frame": 0,
                        "absolute_start_frame": 0,
                    }
                ],
            )
            write_csv(
                subtitles,
                [
                    "event_name",
                    "display_text",
                    "timeline_confidence",
                    "start_ms",
                    "effective_end_ms",
                    "audio_start_ms",
                    "sound_request_id",
                    "z2d_name",
                    "z2d_order",
                    "srt_text",
                ],
                [],
            )
            exclusions.write_text(
                json.dumps(
                    {
                        "events": {
                            "ac_component_001": "reviewed standalone UI component"
                        }
                    }
                ),
                encoding="utf-8",
            )

            script = (
                Path(__file__).resolve().parent
                / "tools"
                / "frida_runtime_probe"
                / "build_event_production_manifests.py"
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--event-catalog",
                    str(catalog),
                    "--event-clips",
                    str(clips),
                    "--audio-components",
                    str(audio),
                    "--event-sounds",
                    str(sounds),
                    "--subtitle-timeline",
                    str(subtitles),
                    "--composition-plans",
                    str(root / "no_plans"),
                    "--audience-exclusions",
                    str(exclusions),
                    "--out-dir",
                    str(out_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(
                (out_dir / "events" / "ac_component_001.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                manifest["audience_exclusion_reason"],
                "reviewed standalone UI component",
            )
            self.assertIn(
                "audience_component_only",
                manifest["quality_gates"]["errors"],
            )
            self.assertFalse(manifest["quality_gates"]["render_ready"])

    def test_voice_label_creates_subtitle_when_graphical_text_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clip = root / "clip.mp4"
            voice_audio = root / "voice.ogg"
            clip.touch()
            voice_audio.touch()

            catalog = root / "catalog.csv"
            clips = root / "clips.csv"
            audio = root / "audio.csv"
            sounds = root / "sounds.csv"
            subtitles = root / "subtitles.csv"
            out_dir = root / "out"
            write_csv(
                catalog,
                [
                    "event_name",
                    "automatic_candidate",
                    "classification",
                    "code_hex",
                ],
                [
                    {
                        "event_name": "ac_voice_001",
                        "automatic_candidate": "yes",
                        "classification": "native_full_frame_only",
                        "code_hex": "0x3",
                    }
                ],
            )
            write_csv(
                clips,
                [
                    "event_name",
                    "z2d_order",
                    "dgm_order",
                    "dgm_name",
                    "dgm_role",
                    "event_start_ms",
                    "event_end_ms",
                    "width",
                    "height",
                    "frame_rate",
                    "media_class",
                    "target_mp4",
                    "source_mp4",
                    "interval_confidence",
                ],
                [
                    {
                        "event_name": "ac_voice_001",
                        "z2d_order": 0,
                        "dgm_order": 0,
                        "dgm_name": "clip",
                        "dgm_role": "single_layer_segment",
                        "event_start_ms": 0,
                        "event_end_ms": 2000,
                        "width": 416,
                        "height": 232,
                        "frame_rate": "30/1",
                        "media_class": "full_frame_landscape",
                        "target_mp4": clip,
                        "source_mp4": clip,
                        "interval_confidence": "exact_duration_unique",
                    }
                ],
            )
            write_csv(
                audio,
                [
                    "primary_animation",
                    "start_ms",
                    "parent_sound_order",
                    "reqdata_index",
                    "leaf_request_id",
                    "leaf_code_name",
                    "ogg_name",
                    "ogg_path",
                    "duration_ms",
                ],
                [],
            )
            write_csv(
                sounds,
                [
                    "event_name",
                    "ogg_exists",
                    "timeline_confidence",
                    "audio_start_ms",
                    "z2d_order",
                    "callback_index",
                    "sound_request_id",
                    "sound_code_name",
                    "ogg_name",
                    "ogg_path",
                    "sound_duration_ms",
                    "z2d_name",
                    "callback_exec_frame",
                    "absolute_start_frame",
                ],
                [
                    {
                        "event_name": "ac_voice_001",
                        "ogg_exists": "yes",
                        "timeline_confidence": (
                            "exact_gdb_child_frame_callback_frame_and_official_ogg"
                        ),
                        "audio_start_ms": 200,
                        "z2d_order": 0,
                        "callback_index": 0,
                        "sound_request_id": "40",
                        "sound_code_name": (
                            "16774_tur_万々歳_桃まんになりますっ"
                        ),
                        "ogg_name": voice_audio.name,
                        "ogg_path": voice_audio,
                        "sound_duration_ms": 1095,
                        "z2d_name": "cap_voice_tur_001",
                        "callback_exec_frame": 6,
                        "absolute_start_frame": 6,
                    }
                ],
            )
            write_csv(
                subtitles,
                [
                    "event_name",
                    "display_text",
                    "timeline_confidence",
                    "start_ms",
                    "effective_end_ms",
                    "audio_start_ms",
                    "sound_request_id",
                    "z2d_name",
                    "z2d_order",
                    "srt_text",
                ],
                [],
            )

            script = (
                Path(__file__).resolve().parent
                / "tools"
                / "frida_runtime_probe"
                / "build_event_production_manifests.py"
            )
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--event-catalog",
                    str(catalog),
                    "--event-clips",
                    str(clips),
                    "--audio-components",
                    str(audio),
                    "--event-sounds",
                    str(sounds),
                    "--subtitle-timeline",
                    str(subtitles),
                    "--composition-plans",
                    str(root / "no_plans"),
                    "--audience-exclusions",
                    str(root / "no_exclusions.json"),
                    "--out-dir",
                    str(out_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads(
                (out_dir / "events" / "ac_voice_001.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(manifest["subtitles"]), 1)
            self.assertEqual(
                manifest["subtitles"][0]["text"],
                "桃まんになりますっ",
            )
            self.assertEqual(
                manifest["subtitles"][0]["subtitle_source"],
                "official_voice_label",
            )

    def test_voice_subtitle_override_files_merge_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            automatic = root / "automatic.json"
            curated = root / "curated.json"
            automatic.write_text(
                json.dumps(
                    {
                        "accepted": {
                            "5176": {
                                "text": "incorrect automatic text",
                                "source": "automatic",
                            },
                            "7634": {
                                "text": "automatic retained text",
                                "source": "automatic",
                            },
                            "8355": {
                                "cues": [
                                    {
                                        "start_ms": 0,
                                        "end_ms": 1000,
                                        "text": "first cue",
                                    }
                                ],
                                "source": "segmented",
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            curated.write_text(
                json.dumps(
                    {
                        "accepted": {
                            "5176": {
                                "text": "世界を狂わせるビューティフルな力！",
                                "source": "curated",
                            }
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            merged = load_voice_subtitle_overrides([automatic, curated])

            self.assertEqual(
                merged["5176"]["text"],
                "世界を狂わせるビューティフルな力！",
            )
            self.assertEqual(
                merged["7634"]["text"],
                "automatic retained text",
            )
            self.assertEqual(
                merged["8355"]["cues"][0]["text"],
                "first cue",
            )


if __name__ == "__main__":
    unittest.main()
