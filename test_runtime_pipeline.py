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
    apply_z2d_event_timing_override,
    apply_path_prefix_maps,
    apply_runtime_voice_subtitle_overrides,
    composition_plan_uses_authored_timing,
    file_sha256,
    filter_subtitle_rows_for_plan,
    load_z2d_event_timing_overrides,
    load_reviewed_subtitle_manifests,
    load_runtime_event_manifests,
    load_voice_subtitle_overrides,
    merge_runtime_graphical_subtitle_rows,
    parse_path_prefix_maps,
    production_content_end_ms,
    quantize_duration_to_frame_grid,
    reconcile_reviewed_subtitle_rows,
    synthesize_static_event_clips_from_plan,
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
from tools.frida_runtime_probe.build_p16_family_replacement_manifests import (
    BLOCKER as P16_TIMING_BLOCKER,
    ROLLBACK_SCRIPT as P16_ROLLBACK_SCRIPT,
    repair_manifest as repair_p16_manifest,
)
from tools.frida_runtime_probe.build_p16_replacement_review_package import (
    ROLLBACK_SCRIPT as P16_REVIEW_ROLLBACK_SCRIPT,
    safe_relative_path as p16_review_safe_relative_path,
)
from tools.frida_runtime_probe.build_p17_family_replacement_manifests import (
    BLOCKER as P17_TIMING_BLOCKER,
    ROLLBACK_SCRIPT as P17_ROLLBACK_SCRIPT,
    repair_manifest as repair_p17_manifest,
)
from tools.frida_runtime_probe.build_p17_replacement_review_package import (
    ROLLBACK_SCRIPT as P17_REVIEW_ROLLBACK_SCRIPT,
    safe_relative_path as p17_review_safe_relative_path,
)
from tools.frida_runtime_probe.build_no_bgm_story_family_editions import (
    attach_speaker_evidence,
    is_exact_graphical_continuation,
    promote_exact_graphical_continuation_cues,
)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class P16ReplacementManifestTests(unittest.TestCase):
    def p16_source(self) -> dict:
        return {
            "schema": "magireco-event-production-v3",
            "event": "ac6003_006",
            "event_code_hex": "0x2573376b25647163",
            "native_frame_rate": "30/1",
            "video_duration_ms": 5000,
            "composition_plan": {},
            "video_extension_policy": "none",
            "clips": [{"event_start_ms": 0, "event_end_ms": 5000}],
            "audio": [
                {
                    "source": "z2d_req_sound",
                    "request_id": "5842",
                    "z2d_name": "cap6003_mb_mif_006",
                    "start_ms": 0,
                    "duration_ms": 1000,
                    "event_global_start_resolved": False,
                }
            ],
            "subtitles": [
                {
                    "voice_request_id": "5842",
                    "z2d_name": "cap6003_mb_mif_006",
                    "voice_start_ms": 0,
                    "start_ms": 0,
                    "end_ms": 4000,
                    "event_global_start_resolved": False,
                }
            ],
            "quality_gates": {
                "all_audio_exist": True,
                "composition_resolved": True,
                "event_global_z2d_timing_ready": False,
                "audio_timeline_ready": False,
                "errors": [P16_TIMING_BLOCKER],
                "render_ready": False,
                "ready": False,
            },
        }

    def p16_override(self) -> dict:
        return {
            "event": "ac6003_006",
            "event_code_hex": "0x2573376b25647163",
            "frame_rate": "30/1",
            "_source_path": "bound-override.json",
            "_source_sha256": "A" * 64,
            "source_bindings": [],
            "authority_path": "authority.json",
            "cues": [
                {
                    "request_id": "5842",
                    "z2d_name": "cap6003_mb_mif_006",
                    "event_global_start_frame": 88,
                    "event_global_start_ms": 2933,
                    "event_global_end_frame_exclusive": 129,
                    "event_global_end_ms": 4300,
                }
            ],
        }

    def test_p16_repair_promotes_only_exact_matched_timing(self) -> None:
        override = self.p16_override()
        override["frame_rate"] = "30"
        repaired, application = repair_p16_manifest(self.p16_source(), override)
        self.assertTrue(application["applied"])
        self.assertEqual(repaired["audio"][0]["start_ms"], 2933)
        self.assertEqual(repaired["subtitles"][0]["start_ms"], 2933)
        self.assertEqual(repaired["subtitles"][0]["end_ms"], 4300)
        self.assertEqual(repaired["timeline_duration_ms"], 5000)
        self.assertEqual(repaired["render_frame_count"], 150)
        self.assertTrue(repaired["quality_gates"]["ready"])
        self.assertEqual(repaired["quality_gates"]["errors"], [])

    def test_p16_repair_fails_closed_on_unmatched_cue(self) -> None:
        override = self.p16_override()
        override["cues"][0]["request_id"] = "wrong-request"
        with self.assertRaisesRegex(ValueError, "unmatched override cues"):
            repair_p16_manifest(self.p16_source(), override)

    def test_p16_rollback_script_has_no_patch_prefixes(self) -> None:
        self.assertFalse(
            any(line.startswith("+") for line in P16_ROLLBACK_SCRIPT.splitlines())
        )
        self.assertIn("source manifests or media", P16_ROLLBACK_SCRIPT)

    def test_p16_review_path_is_language_first_and_flat(self) -> None:
        path = p16_review_safe_relative_path(
            "ZH/story/P16_八千代与美冬的冲突_ac6003__zh.mp4",
            edition="zh",
        )
        self.assertEqual(len(path.parts), 3)
        with self.assertRaisesRegex(ValueError, "unsafe review path"):
            p16_review_safe_relative_path(
                "ZH/story/../escape__zh.mp4", edition="zh"
            )

    def test_p16_review_rollback_script_has_no_patch_prefixes(self) -> None:
        self.assertFalse(
            any(
                line.startswith("+")
                for line in P16_REVIEW_ROLLBACK_SCRIPT.splitlines()
            )
        )


class P17ReplacementManifestTests(unittest.TestCase):
    def test_exact_graphical_continuations_are_restored_without_child_local_leak(self) -> None:
        exact = {
            "text": "あなたはいつも呆れるほど元気に頑張ってる",
            "start_ms": 5967,
            "end_ms": 9367,
            "voice_request_id": "",
            "speaker_code": "",
            "subtitle_source": "graphical_display_text",
            "evidence": "runtime_scene_motion",
            "timing_scope": "event_global_exact_parent_scene_and_motion_key",
            "event_global_start_resolved": True,
            "timing_override_source": "bound-override.json",
        }
        child_local = {
            **exact,
            "text": "child-local risk",
            "timing_scope": "child_z2d_local_only",
            "event_global_start_resolved": False,
            "timing_override_source": "",
        }
        resolved = {
            "event": "ac6004_006",
            "dialogue_cues": [],
            "excluded_source_cues": [
                {
                    "text": exact["text"],
                    "start_ms": exact["start_ms"],
                    "end_ms": exact["end_ms"],
                    "reason": "unvoiced graphical text excluded",
                },
                {
                    "text": child_local["text"],
                    "start_ms": child_local["start_ms"],
                    "end_ms": child_local["end_ms"],
                    "reason": "unvoiced graphical text excluded",
                },
            ],
        }
        manifest = {"subtitles": [exact, child_local]}

        promoted = promote_exact_graphical_continuation_cues(
            resolved,
            manifest,
            {exact["text"]: "你不是一直都\n精神十足地努力着吗？"},
        )

        self.assertTrue(is_exact_graphical_continuation(exact))
        self.assertFalse(is_exact_graphical_continuation(child_local))
        self.assertEqual(len(promoted), 1)
        self.assertEqual(resolved["dialogue_cues"][0]["request_id"], "")
        self.assertTrue(
            resolved["dialogue_cues"][0]["event_global_graphical_continuation"]
        )
        self.assertEqual(
            [row["text"] for row in resolved["excluded_source_cues"]],
            ["child-local risk"],
        )
        attach_speaker_evidence(resolved, manifest)

    def test_p17_repair_recovers_request_3260_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            audio_path = Path(temp) / "req3260.ogg"
            existing_path = Path(temp) / "req3735.ogg"
            audio_path.write_bytes(b"req3260")
            existing_path.write_bytes(b"req3735")
            source = {
                "schema": "magireco-event-production-v3",
                "event": "ac6004_006",
                "event_code_hex": "0x446d4e7634596654",
                "native_frame_rate": "30/1",
                "video_duration_ms": 14200,
                "composition_plan": {},
                "video_extension_policy": "none",
                "clips": [{"event_start_ms": 0, "event_end_ms": 14200}],
                "audio": [
                    {
                        "source": "z2d_req_sound",
                        "request_id": "3735",
                        "z2d_name": "cap6004_mb_uwt_004",
                        "path": str(existing_path),
                        "start_ms": 167,
                        "duration_ms": 4150,
                        "event_global_start_resolved": False,
                    }
                ],
                "subtitles": [
                    {
                        "voice_request_id": "3735",
                        "z2d_name": "cap6004_mb_uwt_004",
                        "start_ms": 167,
                        "end_ms": 4317,
                        "voice_start_ms": 167,
                        "subtitle_source": "graphical_display_text",
                        "event_global_start_resolved": False,
                    },
                    {
                        "voice_request_id": "",
                        "z2d_name": "cap6004_mb_yac_005_01",
                        "start_ms": 5967,
                        "end_ms": 9367,
                        "voice_start_ms": 5967,
                        "subtitle_source": "graphical_display_text",
                        "event_global_start_resolved": False,
                    },
                    {
                        "voice_request_id": "",
                        "z2d_name": "cap6004_mb_yac_005_02",
                        "start_ms": 0,
                        "end_ms": 5733,
                        "voice_start_ms": 0,
                        "subtitle_source": "graphical_display_text",
                        "event_global_start_resolved": False,
                    },
                ],
                "quality_gates": {
                    "errors": [P17_TIMING_BLOCKER],
                    "all_audio_exist": True,
                    "composition_resolved": True,
                    "event_global_z2d_timing_ready": False,
                    "audio_timeline_ready": False,
                    "render_ready": False,
                    "ready": False,
                },
            }
            override = {
                "event_code_hex": source["event_code_hex"],
                "frame_rate": "30/1",
                "expected_z2d_request_ids": ["3260", "3735"],
                "cues": [
                    {
                        "request_id": "3735",
                        "z2d_name": "cap6004_mb_uwt_004",
                        "event_global_start_frame": 5,
                        "event_global_start_ms": 167,
                        "event_global_end_frame_exclusive": 121,
                        "event_global_end_ms": 4033,
                    },
                    {
                        "request_id": "3260",
                        "z2d_name": "cap6004_mb_yac_005",
                        "event_global_start_frame": 124,
                        "event_global_start_ms": 4133,
                        "event_global_end_frame_exclusive": 161,
                        "event_global_end_ms": 5367,
                        "recover_missing_audio": {
                            "code_name": "16214_yac_voice",
                            "ogg_name": audio_path.name,
                            "path": str(audio_path),
                            "sha256": "C" * 64,
                            "duration_ms": 7899,
                            "child_local_start_ms": 0,
                            "callback_exec_frame": 0,
                            "child_local_absolute_start_frame": "",
                            "evidence": "official_ogg_and_z2d_callback",
                        },
                        "recover_missing_subtitle": {
                            "text": "何言ってるの！",
                            "speaker_code": "",
                            "subtitle_source": "graphical_display_text",
                            "evidence": "runtime_scene_motion",
                        },
                    },
                    {
                        "request_id": "",
                        "z2d_name": "cap6004_mb_yac_005_01",
                        "subtitle_only": True,
                        "event_global_start_frame": 179,
                        "event_global_start_ms": 5967,
                        "event_global_end_frame_exclusive": 281,
                        "event_global_end_ms": 9367,
                    },
                    {
                        "request_id": "",
                        "z2d_name": "cap6004_mb_yac_005_02",
                        "subtitle_only": True,
                        "event_global_start_frame": 290,
                        "event_global_start_ms": 9667,
                        "event_global_end_frame_exclusive": 356,
                        "event_global_end_ms": 11867,
                    },
                ],
                "source_bindings": [],
                "authority_path": "authority.json",
                "_source_path": "override.json",
                "_source_sha256": "B" * 64,
            }

            repaired, application = repair_p17_manifest(source, override)

            self.assertTrue(repaired["quality_gates"]["ready"])
            self.assertTrue(application["request_set_matches"])
            self.assertEqual(application["recovered_audio_cue_count"], 1)
            self.assertEqual(application["recovered_subtitle_cue_count"], 1)
            recovered = [
                row for row in repaired["audio"] if row["request_id"] == "3260"
            ]
            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0]["start_ms"], 4133)
            self.assertEqual(recovered[0]["duration_ms"], 7899)
            self.assertEqual(
                [row["start_ms"] for row in repaired["subtitles"]],
                [167, 4133, 5967, 9667],
            )

    def test_p17_rollback_script_has_no_patch_prefixes(self) -> None:
        self.assertFalse(
            any(line.startswith("+") for line in P17_ROLLBACK_SCRIPT.splitlines())
        )
        self.assertIn("source manifests or media", P17_ROLLBACK_SCRIPT)

    def test_p17_review_path_is_language_first_and_flat(self) -> None:
        path = p17_review_safe_relative_path(
            "ZH/story/P17_八千代等人拯救谣鹤乃_ac6004__zh.mp4", edition="zh"
        )
        self.assertEqual(len(path.parts), 3)
        with self.assertRaisesRegex(ValueError, "unsafe review path"):
            p17_review_safe_relative_path(
                "ZH/story/../escape__zh.mp4", edition="zh"
            )

    def test_p17_review_rollback_script_has_no_patch_prefixes(self) -> None:
        self.assertFalse(
            any(
                line.startswith("+")
                for line in P17_REVIEW_ROLLBACK_SCRIPT.splitlines()
            )
        )


class CompositionPlanTests(unittest.TestCase):
    def test_reviewed_subtitles_keep_current_timing_and_restore_missing_voice(self) -> None:
        current = [
            {
                "text": "アリナが代わりにマ",
                "start_ms": 100,
                "end_ms": 900,
                "voice_request_id": "5324",
                "voice_start_ms": 100,
                "subtitle_source": "official_voice_label",
            },
            {
                "text": "ヌル\n3",
                "start_ms": 1200,
                "end_ms": 1700,
                "voice_request_id": "451",
                "voice_start_ms": 1200,
                "subtitle_source": "graphical_display_text",
            },
            {
                "text": "graphical-only",
                "start_ms": 0,
                "end_ms": 500,
                "voice_request_id": "",
                "subtitle_source": "graphical_display_text",
            },
        ]
        audio = [
            {
                "request_id": "5324",
                "start_ms": 100,
                "duration_ms": 860,
                "z2d_name": "cap7206_ari_say",
            },
            {
                "request_id": "7856",
                "start_ms": 833,
                "duration_ms": 6220,
                "z2d_name": "cap5203_mam_attack_say_005",
            },
            {
                "request_id": "451",
                "start_ms": 1200,
                "duration_ms": 500,
                "z2d_name": "chance_button",
            },
        ]
        reviewed = {
            "subtitles": [
                {
                    "text": "アリナが代わりにマギウスを…",
                    "start_ms": 100,
                    "end_ms": 960,
                    "voice_request_id": "5324",
                    "voice_start_ms": 100,
                    "speaker_code": "ari",
                    "subtitle_source": "official_voice_asr_verified",
                    "evidence": "reviewed-full-text",
                },
                {
                    "text": "負けるもんか！",
                    "start_ms": 833,
                    "end_ms": 7053,
                    "voice_request_id": "7856",
                    "voice_start_ms": 833,
                    "speaker_code": "mam",
                    "subtitle_source": "official_voice_asr_verified",
                    "evidence": "reviewed-asr",
                },
            ],
            "_source_provenance": [
                {"path": "D:/reviewed/ac.json", "sha256": "A" * 64}
            ],
        }

        rows, audit = reconcile_reviewed_subtitle_rows(
            "ac_test",
            current,
            audio,
            reviewed,
        )

        self.assertEqual([row["voice_request_id"] for row in rows], ["5324", "7856"])
        self.assertEqual(rows[0]["text"], "アリナが代わりにマギウスを…")
        self.assertEqual((rows[0]["start_ms"], rows[0]["end_ms"]), (100, 900))
        self.assertEqual(rows[1]["text"], "負けるもんか！")
        self.assertEqual((rows[1]["start_ms"], rows[1]["end_ms"]), (833, 7053))
        self.assertEqual(audit["matched_voice_cue_count"], 1)
        self.assertEqual(audit["carried_voice_cue_count"], 1)
        self.assertEqual(
            audit["excluded_current_voice_candidates"][0]["voice_request_id"],
            "451",
        )
        self.assertEqual(
            audit["excluded_current_graphical_candidates"][0]["text"],
            "graphical-only",
        )

    def test_reviewed_subtitle_without_current_audio_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "has no current verified audio row"):
            reconcile_reviewed_subtitle_rows(
                "ac_test",
                [],
                [],
                {
                    "subtitles": [
                        {
                            "text": "missing",
                            "start_ms": 0,
                            "end_ms": 500,
                            "voice_request_id": "999",
                        }
                    ]
                },
            )

    def test_reviewed_subtitles_accept_exact_curated_current_only_voice(self) -> None:
        current = [
            {
                "text": "私もチャレンジした方がいいのかな",
                "start_ms": 333,
                "end_ms": 2786,
                "voice_request_id": "8041",
                "voice_start_ms": 333,
                "speaker_code": "kur",
                "subtitle_source": "official_voice_asr_verified",
                "evidence": "curated_official_prefix_and_asr",
            },
            {
                "text": "unreviewed",
                "start_ms": 500,
                "end_ms": 1000,
                "voice_request_id": "9999",
                "voice_start_ms": 500,
                "subtitle_source": "official_voice_label",
            },
        ]
        audio = [
            {"request_id": "8041", "start_ms": 333, "duration_ms": 2453},
            {"request_id": "9999", "start_ms": 500, "duration_ms": 500},
        ]
        rows, audit = reconcile_reviewed_subtitle_rows(
            "ac0911_010",
            current,
            audio,
            {"subtitles": []},
            {
                "8041": {
                    "text": "私もチャレンジした方がいいのかな",
                    "source": "curated_official_prefix_and_asr",
                }
            },
        )
        self.assertEqual(
            [row["voice_request_id"] for row in rows],
            ["8041"],
        )
        self.assertEqual(
            audit["accepted_current_voice_override_candidates"][0][
                "voice_request_id"
            ],
            "8041",
        )
        self.assertEqual(
            audit["excluded_current_voice_candidates"][0]["voice_request_id"],
            "9999",
        )

    def test_reviewed_subtitles_reject_changed_curated_current_only_voice(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "differs from its accepted voice override",
        ):
            reconcile_reviewed_subtitle_rows(
                "ac0911_010",
                [
                    {
                        "text": "truncated",
                        "start_ms": 0,
                        "end_ms": 500,
                        "voice_request_id": "8041",
                    }
                ],
                [{"request_id": "8041", "start_ms": 0, "duration_ms": 500}],
                {"subtitles": []},
                {"8041": {"text": "full dialogue"}},
            )

    def test_reviewed_subtitle_loader_hashes_and_rejects_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "one" / "events" / "ac_test.json"
            second = root / "two" / "events" / "ac_test.json"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            payload = {
                "event": "ac_test",
                "subtitles": [{"text": "approved"}],
                "quality_gates": {"ready": True},
            }
            first.write_text(json.dumps(payload), encoding="utf-8")
            second.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_reviewed_subtitle_manifests(
                [first.parent.parent, second.parent.parent]
            )
            self.assertEqual(
                len(loaded["ac_test"]["_source_provenance"]),
                2,
            )
            self.assertEqual(
                loaded["ac_test"]["_source_provenance"][0]["sha256"],
                file_sha256(first),
            )
            payload["subtitles"][0]["text"] = "conflict"
            second.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "conflicting reviewed subtitle manifests for ac_test",
            ):
                load_reviewed_subtitle_manifests(
                    [first.parent.parent, second.parent.parent]
                )

    def test_timed_plan_duration_bounds_static_loop_and_overlay_sources(self) -> None:
        sources = [
            {
                "dgm_name": "scene_intro",
                "media_duration_sec": "8.0",
                "event_start_ms": "0",
                "event_end_ms": "8000",
            },
            {
                "dgm_name": "scene_loop",
                "media_duration_sec": "8.0",
                "event_start_ms": "8000",
                "event_end_ms": "16000",
            },
            {
                "dgm_name": "scene_overlay",
                "media_duration_sec": "16.0",
                "event_start_ms": "0",
                "event_end_ms": "16000",
            },
        ]
        for duration_ms in (8654, 8958, 9661, 9381, 11610):
            with self.subTest(duration_ms=duration_ms):
                plan = {
                    "event": "sample_event",
                    "model": "timed_full_frame_layers",
                    "duration_ms": duration_ms,
                    "evidence": "reviewed runtime timing evidence",
                    "clips": [
                        {
                            "dgm_name": "scene_intro",
                            "role": "background",
                            "start_ms": 0,
                        },
                        {
                            "dgm_name": "scene_loop",
                            "role": "loop_background",
                            "start_ms": 8000,
                        },
                        {
                            "dgm_name": "scene_overlay",
                            "role": "screen_overlay",
                            "start_ms": 0,
                        },
                    ],
                }

                self.assertTrue(composition_plan_uses_authored_timing(plan))
                clips = synthesize_static_event_clips_from_plan(sources, plan)

                self.assertEqual(clips[0]["event_end_ms"], "8000")
                self.assertEqual(clips[1]["event_end_ms"], str(duration_ms))
                self.assertEqual(clips[2]["event_end_ms"], str(duration_ms))
                self.assertEqual(
                    max(int(row["event_end_ms"]) for row in clips), duration_ms
                )

    def test_timed_plan_authored_timing_fails_closed_without_evidence(self) -> None:
        plan = {
            "event": "sample_event",
            "model": "timed_full_frame_layers",
            "duration_ms": 8654,
            "evidence": "",
            "clips": [
                {"dgm_name": "scene", "role": "background", "start_ms": 0}
            ],
        }
        with self.assertRaisesRegex(ValueError, "no evidence statement"):
            composition_plan_uses_authored_timing(plan)

    def test_plan_duration_is_a_floor_without_truncating_proven_av_tails(self) -> None:
        def plan(duration_ms: int, extension_policy: str = "") -> dict:
            return {
                "event": "sample_event",
                "model": "linear_full_frame_sequence",
                "duration_ms": duration_ms,
                "extension_policy": extension_policy,
                "evidence": "reviewed runtime timing evidence",
                "clips": [
                    {"dgm_name": "scene", "role": "background", "start_ms": 0}
                ],
            }

        # A short visual is extended through the complete authored black tail.
        self.assertEqual(
            production_content_end_ms(2000, 7053, plan(7118, "black_tail")),
            7118,
        )
        # A proven subtitle tail remains authoritative when it exceeds the plan.
        self.assertEqual(production_content_end_ms(6160, 6200, plan(6160)), 6200)
        # A plan remains the floor when indexed AV ends slightly earlier.
        self.assertEqual(production_content_end_ms(9565, 9538, plan(9565)), 9565)

    def test_legacy_plan_without_duration_uses_proven_av_tail(self) -> None:
        plan = {
            "event": "ac0908_009",
            "model": "linear_full_frame_sequence",
            "extension_policy": "hold_last_frame",
            "evidence": "verified visual order without an authored duration",
        }
        self.assertEqual(production_content_end_ms(4000, 4624, plan), 4624)

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
            "kuroe",
        )
        self.assertEqual(
            request_speaker("8340_kuro_くそっ！"),
            "kuro",
        )
        self.assertEqual(
            speaker_hint("ac7117_001_kuro_走る"),
            "kuro",
        )
        self.assertEqual(
            speaker_hint("ac7117_003_kuroe_振り返る"),
            "kuroe",
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
            self.assertEqual(
                manifest["audio"][1]["timing_scope"],
                "child_z2d_local_only",
            )
            self.assertFalse(
                manifest["audio"][1]["event_global_start_resolved"]
            )
            self.assertFalse(
                manifest["quality_gates"]["event_global_z2d_timing_ready"]
            )
            self.assertFalse(
                manifest["quality_gates"]["audio_timeline_ready"]
            )
            self.assertFalse(manifest["quality_gates"]["render_ready"])
            self.assertIn(
                "unresolved_parent_dgm_to_child_z2d_instantiation_offset",
                manifest["quality_gates"]["errors"],
            )

            authority = root / "timing_authority.json"
            authority.write_text("bound P16-style evidence\n", encoding="utf-8")
            timing_override = root / "timing_override.json"
            timing_override.write_text(
                json.dumps(
                    {
                        "schema": "magireco-z2d-event-timing-override-v1",
                        "event": "ac_test_001",
                        "event_code_hex": "0x1",
                        "frame_rate": "30/1",
                        "authority_path": str(authority),
                        "source_bindings": [
                            {
                                "path": str(authority),
                                "sha256": file_sha256(authority),
                            }
                        ],
                        "cues": [
                            {
                                "request_id": "20",
                                "z2d_name": "cap_test",
                                "event_global_start_frame": 6,
                                "event_global_start_ms": 200,
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            resolved_out_dir = root / "resolved_out"
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
                    "--z2d-event-timing-overrides",
                    str(timing_override),
                    "--out-dir",
                    str(resolved_out_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            resolved = json.loads(
                (resolved_out_dir / "events" / "ac_test_001.json").read_text(
                    encoding="utf-8"
                )
            )
            resolved_voice = resolved["audio"][1]
            self.assertEqual(resolved_voice["child_local_start_ms"], 100)
            self.assertEqual(resolved_voice["start_ms"], 200)
            self.assertEqual(resolved_voice["event_global_start_frame"], 6)
            self.assertTrue(resolved_voice["event_global_start_resolved"])
            self.assertEqual(
                resolved_voice["timing_scope"],
                "event_global_exact_parent_scene_and_motion_key",
            )
            self.assertTrue(
                resolved["quality_gates"]["event_global_z2d_timing_ready"]
            )
            self.assertTrue(resolved["quality_gates"]["render_ready"])
            self.assertNotIn(
                "unresolved_parent_dgm_to_child_z2d_instantiation_offset",
                resolved["quality_gates"]["errors"],
            )
            application = resolved["z2d_event_timing_override_application"]
            self.assertTrue(application["applied"])
            self.assertEqual(application["matched_audio_cue_count"], 1)
            self.assertEqual(application["matched_subtitle_cue_count"], 0)
            self.assertEqual(application["unmatched_cues"], [])

            authority.write_text("tampered evidence\n", encoding="utf-8")
            stale = subprocess.run(
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
                    "--z2d-event-timing-overrides",
                    str(timing_override),
                    "--out-dir",
                    str(root / "stale_out"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("Z2D timing source SHA-256 mismatch", stale.stderr)

    def test_z2d_timing_override_keeps_unmatched_child_local_rows_blocked(self) -> None:
        override = {
            "cues": [
                {
                    "request_id": "99",
                    "z2d_name": "cap_other",
                    "event_global_start_frame": 29,
                    "event_global_start_ms": 967,
                }
            ],
            "source_bindings": [],
            "authority_path": "authority.json",
            "_source_path": "override.json",
            "_source_sha256": "A" * 64,
        }
        audio_rows = [
            {
                "source": "z2d_req_sound",
                "request_id": "20",
                "z2d_name": "cap_test",
                "start_ms": 100,
                "event_global_start_resolved": False,
            }
        ]
        result = apply_z2d_event_timing_override(audio_rows, [], override)
        self.assertFalse(result["applied"])
        self.assertEqual(
            result["unmatched_cues"],
            [{"request_id": "99", "z2d_name": "cap_other"}],
        )
        self.assertEqual(audio_rows[0]["start_ms"], 100)
        self.assertFalse(audio_rows[0]["event_global_start_resolved"])

    def test_z2d_timing_override_shifts_matching_voice_and_subtitle(self) -> None:
        override = {
            "cues": [
                {
                    "request_id": "5843",
                    "z2d_name": "cap6003_mb_mif_007",
                    "event_global_start_frame": 29,
                    "event_global_start_ms": 967,
                    "event_global_end_frame_exclusive": 138,
                    "event_global_end_ms": 4600,
                },
                {
                    "request_id": "",
                    "z2d_name": "cap6003_mb_mif_007_01",
                    "subtitle_only": True,
                    "event_global_start_frame": 139,
                    "event_global_start_ms": 4633,
                    "event_global_end_frame_exclusive": 221,
                    "event_global_end_ms": 7367,
                }
            ],
            "source_bindings": [{"path": "authority.json", "sha256": "A" * 64}],
            "authority_path": "authority.json",
            "_source_path": "override.json",
            "_source_sha256": "B" * 64,
        }
        audio_rows = [
            {
                "source": "z2d_req_sound",
                "request_id": "5843",
                "z2d_name": "cap6003_mb_mif_007",
                "start_ms": 0,
                "absolute_start_frame": "0.0",
                "event_global_start_resolved": False,
            }
        ]
        subtitle_rows = [
            {
                "voice_request_id": "5843",
                "z2d_name": "cap6003_mb_mif_007",
                "start_ms": 0,
                "end_ms": 5733,
                "voice_start_ms": 0,
                "event_global_start_resolved": False,
            },
            {
                "voice_request_id": "",
                "z2d_name": "cap6003_mb_mif_007_01",
                "start_ms": 0,
                "end_ms": 5733,
                "voice_start_ms": 0,
                "event_global_start_resolved": False,
            }
        ]
        result = apply_z2d_event_timing_override(
            audio_rows, subtitle_rows, override
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["matched_audio_cue_count"], 1)
        self.assertEqual(result["matched_subtitle_cue_count"], 2)
        self.assertEqual(result["unmatched_cues"], [])
        self.assertEqual(audio_rows[0]["start_ms"], 967)
        self.assertEqual(audio_rows[0]["child_local_start_ms"], 0)
        self.assertEqual(audio_rows[0]["event_global_start_frame"], 29)
        self.assertTrue(audio_rows[0]["event_global_start_resolved"])
        self.assertEqual(subtitle_rows[0]["start_ms"], 967)
        self.assertEqual(subtitle_rows[0]["end_ms"], 4600)
        self.assertEqual(subtitle_rows[0]["voice_start_ms"], 967)
        self.assertEqual(subtitle_rows[0]["child_local_end_ms"], 5733)
        self.assertTrue(subtitle_rows[0]["event_global_start_resolved"])
        self.assertEqual(subtitle_rows[1]["start_ms"], 4633)
        self.assertEqual(subtitle_rows[1]["end_ms"], 7367)
        self.assertEqual(
            subtitle_rows[1]["event_global_end_frame_exclusive"], 221
        )
        self.assertTrue(subtitle_rows[1]["event_global_start_resolved"])

    def test_z2d_timing_override_recovers_exact_missing_rows(self) -> None:
        override = {
            "cues": [
                {
                    "request_id": "3260",
                    "z2d_name": "cap6004_mb_yac_005",
                    "event_global_start_frame": 124,
                    "event_global_start_ms": 4133,
                    "event_global_end_frame_exclusive": 161,
                    "event_global_end_ms": 5367,
                    "recover_missing_audio": {
                        "code_name": "16214_yac_voice",
                        "ogg_name": "req3260.ogg",
                        "path": "D:/evidence/req3260.ogg",
                        "sha256": "C" * 64,
                        "duration_ms": 7899,
                        "child_local_start_ms": 0,
                        "callback_exec_frame": 0,
                        "child_local_absolute_start_frame": "0.0",
                        "evidence": "official_ogg_and_z2d_callback",
                    },
                    "recover_missing_subtitle": {
                        "text": "何言ってるの！",
                        "speaker_code": "",
                        "subtitle_source": "graphical_display_text",
                        "evidence": "runtime_scene_motion_and_graphical_text",
                    },
                }
            ],
            "expected_z2d_request_ids": ["3260", "3735"],
            "source_bindings": [],
            "authority_path": "authority.json",
            "_source_path": "override.json",
            "_source_sha256": "B" * 64,
        }
        audio_rows = [
            {
                "source": "z2d_req_sound",
                "request_id": "3735",
                "z2d_name": "cap6004_mb_uwt_004",
                "start_ms": 167,
                "event_global_start_resolved": True,
            }
        ]
        subtitle_rows: list[dict] = []

        result = apply_z2d_event_timing_override(
            audio_rows, subtitle_rows, override
        )

        self.assertTrue(result["applied"])
        self.assertEqual(result["recovered_audio_cue_count"], 1)
        self.assertEqual(result["recovered_subtitle_cue_count"], 1)
        self.assertEqual(result["recovery_conflicts"], [])
        self.assertTrue(result["request_set_matches"])
        self.assertEqual(result["observed_z2d_request_ids"], ["3260", "3735"])
        recovered_audio = next(
            row for row in audio_rows if row.get("request_id") == "3260"
        )
        self.assertEqual(recovered_audio["start_ms"], 4133)
        self.assertEqual(recovered_audio["duration_ms"], 7899)
        self.assertEqual(recovered_audio["event_global_shift_ms"], 4133)
        self.assertTrue(recovered_audio["event_global_start_resolved"])
        self.assertTrue(recovered_audio["recovered_missing_source_row"])
        self.assertEqual(subtitle_rows[0]["start_ms"], 4133)
        self.assertEqual(subtitle_rows[0]["end_ms"], 5367)
        self.assertEqual(subtitle_rows[0]["text"], "何言ってるの！")

    def test_z2d_timing_override_expected_request_set_fails_closed(self) -> None:
        override = {
            "cues": [
                {
                    "request_id": "3260",
                    "z2d_name": "cap6004_mb_yac_005",
                    "event_global_start_frame": 124,
                    "event_global_start_ms": 4133,
                }
            ],
            "expected_z2d_request_ids": ["3260", "3735"],
            "source_bindings": [],
            "authority_path": "authority.json",
            "_source_path": "override.json",
            "_source_sha256": "B" * 64,
        }
        audio_rows = [
            {
                "source": "z2d_req_sound",
                "request_id": "3260",
                "z2d_name": "cap6004_mb_yac_005",
                "start_ms": 0,
                "event_global_start_resolved": False,
            }
        ]

        result = apply_z2d_event_timing_override(audio_rows, [], override)

        self.assertFalse(result["request_set_matches"])
        self.assertEqual(result["expected_z2d_request_ids"], ["3260", "3735"])
        self.assertEqual(result["observed_z2d_request_ids"], ["3260"])

    def test_z2d_timing_override_recovered_audio_is_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            authority = root / "authority.json"
            audio = root / "req3260.ogg"
            authority.write_text("exact authority\n", encoding="utf-8")
            audio.write_bytes(b"official ogg fixture")
            override_path = root / "override.json"
            override_path.write_text(
                json.dumps(
                    {
                        "schema": "magireco-z2d-event-timing-override-v1",
                        "event": "ac6004_006",
                        "event_code_hex": "0x1",
                        "frame_rate": "30/1",
                        "authority_path": str(authority),
                        "expected_z2d_request_ids": ["3260"],
                        "source_bindings": [
                            {
                                "path": str(authority),
                                "sha256": file_sha256(authority),
                            },
                            {
                                "path": str(audio),
                                "sha256": file_sha256(audio),
                            },
                        ],
                        "cues": [
                            {
                                "request_id": "3260",
                                "z2d_name": "cap6004_mb_yac_005",
                                "event_global_start_frame": 124,
                                "event_global_start_ms": 4133,
                                "event_global_end_frame_exclusive": 161,
                                "event_global_end_ms": 5367,
                                "recover_missing_audio": {
                                    "code_name": "16214_yac_voice",
                                    "ogg_name": audio.name,
                                    "path": str(audio),
                                    "sha256": file_sha256(audio),
                                    "duration_ms": 7899,
                                    "child_local_start_ms": 0,
                                    "callback_exec_frame": 0,
                                    "child_local_absolute_start_frame": "0.0",
                                    "evidence": "official_ogg_and_z2d_callback",
                                },
                                "recover_missing_subtitle": {
                                    "text": "何言ってるの！",
                                    "speaker_code": "",
                                    "subtitle_source": "graphical_display_text",
                                    "evidence": "runtime_scene_motion",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_z2d_event_timing_overrides([override_path])
            self.assertEqual(
                loaded["ac6004_006"]["expected_z2d_request_ids"], ["3260"]
            )

            audio.write_bytes(b"tampered")
            with self.assertRaisesRegex(
                ValueError, "Z2D timing source SHA-256 mismatch"
            ):
                load_z2d_event_timing_overrides([override_path])

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
