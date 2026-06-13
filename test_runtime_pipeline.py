from __future__ import annotations

import csv
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
    load_voice_subtitle_overrides,
)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class CompositionPlanTests(unittest.TestCase):
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


class ManifestBuilderTests(unittest.TestCase):
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
