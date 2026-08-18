from __future__ import annotations

import unittest

from tools.frida_runtime_probe.resolve_ac0908_runtime_unique_segments import (
    REQUIRED_EVENTS,
    cut_frames,
    cut_structure,
    resolve,
    structure_key,
)


def node(name: str) -> dict:
    return {
        "type": 20,
        "name": name,
        "motions": [
            {
                "is_z2d_motion": True,
                "keys": [{"index": 0, "floats": [0, 1], "flags": [0, 0, 0]}],
            }
        ],
        "children": [],
    }


def cut(name: str, frames: int, nodes: list[dict]) -> dict:
    return {
        "cut_name": name,
        "instance_offset_frames": 0,
        "cut_start_frame": 0,
        "cut_end_frame": frames - 1,
        "node_count": len(nodes),
        "nodes": nodes,
    }


class RuntimeUniqueSegmentTests(unittest.TestCase):
    def test_cut_duration_is_inclusive_and_includes_instance_offset(self):
        value = cut("x", 30, [node("x.z2d")])
        value["instance_offset_frames"] = 7
        self.assertEqual(cut_frames(value), 37)

    def test_pointer_free_structure_is_stable(self):
        value = cut("x", 30, [node("x.z2d")])
        first = structure_key(cut_structure(value))
        value["cut_pointer"] = "0x1234"
        value["nodes"][0]["pointer"] = "0x5678"
        second = structure_key(cut_structure(value))
        self.assertEqual(first, second)

    def test_real_shape_resolves_aliases_parallel_scenes_and_no_bgm(self):
        shutter = {
            "ac0908_010": ("ac8004_001", 498),
            "ac0908_011": ("ac8004_003", 498),
            "ac0908_012": ("ac8004_004", 78),
            "ac0908_013": ("ac8004_001", 498),
            "ac0908_014": ("ac8004_003", 498),
            "ac0908_015": ("ac8004_004", 78),
            "ac0908_017": ("ac8004_002", 498),
        }
        base = {
            "ac0908_001": 87,
            "ac0908_002": 270,
            "ac0908_003": 270,
            "ac0908_004": 270,
            "ac0908_005": 270,
            "ac0908_006": 270,
            "ac0908_007": 201,
            "ac0908_008": 241,
            "ac0908_009": 120,
            "ac0908_016": 180,
        }
        events = {}
        for event in REQUIRED_EVENTS:
            if event in shutter:
                cut_name, frames = shutter[event]
                scenes = [
                    {"name": event, "cuts": [cut(event, 100, [])]},
                    {
                        "name": "SHUTTER",
                        "cuts": [cut(cut_name, frames, [node(cut_name + ".z2d")])],
                    },
                ]
            else:
                scenes = [
                    {
                        "name": event,
                        "cuts": [cut(event, base[event], [node(event + ".z2d")])],
                    }
                ]
            events[event] = {
                "status": "captured",
                "value": {"group_name": "ac0908", "scenes": scenes},
            }
        runtime = {
            "schema": "magireco-ac0908-runtime-scene-motion-v1",
            "host_frida_version": "17.16.4",
            "protected_processes_unchanged": True,
            "crash_tail_empty": True,
            "events": events,
        }
        audio = {}
        for event in REQUIRED_EVENTS:
            audio[event] = [
                {
                    "primary_animation": event,
                    "parent_request_id": "1",
                    "start_ms": "0",
                    "leaf_request_id": "1",
                    "leaf_sound_code": "2650",
                    "leaf_code_name": "base SE",
                    "duration_ms": "1000",
                }
            ]

        def shutter_audio(
            event: str,
            result_request: int,
            result_sound: int,
            result_duration: int,
            bgm_request: int,
            bgm_sound: int,
            bgm_start: int,
            bgm_duration: int,
        ) -> list[dict[str, str]]:
            return [
                {
                    "primary_animation": event,
                    "parent_request_id": "464",
                    "start_ms": "0",
                    "leaf_request_id": "438",
                    "leaf_sound_code": "1035",
                    "leaf_code_name": "shutter close",
                    "duration_ms": "1463",
                },
                {
                    "primary_animation": event,
                    "parent_request_id": "464",
                    "start_ms": "719",
                    "leaf_request_id": "439",
                    "leaf_sound_code": "1036",
                    "leaf_code_name": "shutter open",
                    "duration_ms": "2231",
                },
                {
                    "primary_animation": event,
                    "parent_request_id": "464",
                    "start_ms": "710",
                    "leaf_request_id": str(result_request),
                    "leaf_sound_code": str(result_sound),
                    "leaf_code_name": "result SE",
                    "duration_ms": str(result_duration),
                },
                {
                    "primary_animation": event,
                    "parent_request_id": "464",
                    "start_ms": str(bgm_start),
                    "leaf_request_id": str(bgm_request),
                    "leaf_sound_code": str(bgm_sound),
                    "leaf_code_name": "result jingle",
                    "duration_ms": str(bgm_duration),
                },
            ]

        for event in ("ac0908_010", "ac0908_013"):
            audio[event] = shutter_audio(event, 419, 1005, 2625, 226, 551, 1348, 6194)
        for event in ("ac0908_011", "ac0908_014"):
            audio[event] = shutter_audio(event, 422, 1008, 2742, 227, 552, 1468, 6905)
        for event in ("ac0908_012", "ac0908_015"):
            audio[event] = shutter_audio(event, 424, 1010, 4114, 228, 553, 1603, 6183)
        audio["ac0908_016"] = [
            {
                "primary_animation": "ac0908_016",
                "parent_request_id": "426",
                "start_ms": "0",
                "leaf_request_id": "426",
                "leaf_sound_code": "1012",
                "leaf_code_name": "premium SE",
                "duration_ms": "3833",
            }
        ]
        audio["ac0908_017"] = [
            {
                "primary_animation": "ac0908_017",
                "parent_request_id": "465",
                "start_ms": "0",
                "leaf_request_id": "418",
                "leaf_sound_code": "1004",
                "leaf_code_name": "portent SE",
                "duration_ms": "3584",
            }
        ]
        prior = {
            "event_containers": [
                {
                    "event": event,
                    "static_audio_component_span_ms": str(
                        max(int(row["start_ms"]) + int(row["duration_ms"]) for row in audio[event])
                    ),
                }
                for event in REQUIRED_EVENTS
            ],
            "current_showcase": {
                "occurrence_count": 13,
                "included_events": list(REQUIRED_EVENTS[:9]),
                "event_occurrence_counts": {
                    event: (3 if event in {"ac0908_001", "ac0908_009"} else 1)
                    for event in REQUIRED_EVENTS[:9]
                },
                "guaranteed_duplicate_occurrence_groups": [
                    {
                        "event": "ac0908_009",
                        "frame_count": 139,
                        "kind": "approved_v27_event",
                        "include_exterior": None,
                        "occurrence_count": 3,
                        "surplus_occurrence_count": 2,
                    }
                ],
            },
        }
        dgm = {
            event: [
                {
                    "z2d_name": event,
                    "dgm_name": event,
                    "source_exists": "True",
                    "expected_frames": str(base[event]),
                }
            ]
            for event in base
        }
        dgm["ac0908_016"].extend(
            [
                {
                    "z2d_name": "ac8040_premia_EF",
                    "dgm_name": "ac8040_premia_EF_add",
                    "source_exists": "False",
                    "expected_frames": "",
                },
                {
                    "z2d_name": "ac8040_premia_EF",
                    "dgm_name": "ac8040_premia_EF_add_LP",
                    "source_exists": "False",
                    "expected_frames": "",
                },
            ]
        )
        ida = {
            "schema": "magireco-ida-playlist-chain-evidence-v1",
            "status": "passed",
            "binary": {
                "sha256": "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
            },
            "labels": [
                "CGFDirectionPlayer_SetScene",
                "CGFDirectionPlaylist_AddCut",
                "CGFDirectionPlaylist_AddBlank",
                "CGFDirectionPlaylist_AdvanceTime",
                "CGFDirectionPlaylist_SetTime",
            ],
        }
        ida_event_av = {
            "schema": "magireco-ida-event-av-parallel-start-evidence-v1",
            "status": "passed",
            "binary": ida["binary"],
            "semantic_assertions": {
                "graphics_and_sound_receive_same_event_code": True,
                "all_scene_names_are_set_at_time_zero": True,
                "same_event_scene_scheduling": "parallel_shared_event_global_origin",
                "scene_container_duration_rule": "maximum_scene_duration_not_sum",
                "ac0908_control_commands_empty": True,
                "machine_vision_used_as_authority": False,
            },
        }
        sound_divide = {
            "schema": "magireco-ac0908-sound-divide-values-v1",
            "status": "passed",
            "binary": ida["binary"],
            "table": {"base_ea": "0x1445C54"},
            "assertions": {
                "all_ac0908_nonzero_duration_leaf_sound_ids_covered": True
            },
            "values": [
                {"sound_id": sound_id, "volume_kind_value": kind}
                for sound_id, kind in {
                    551: 0,
                    552: 0,
                    553: 0,
                    1004: 1,
                    1005: 1,
                    1008: 1,
                    1010: 1,
                    1012: 1,
                    1035: 1,
                    1036: 1,
                    2650: 1,
                }.items()
            ],
        }
        result = resolve(
            runtime, prior, dgm, ida, ida_event_av, audio, sound_divide
        )
        self.assertEqual(result["counts"]["canonical_unique_visible_scene_count"], 14)
        self.assertEqual(result["counts"]["visible_scene_occurrence_count"], 17)
        self.assertEqual(result["counts"]["exact_duplicate_visible_surplus_count"], 3)
        self.assertEqual(result["counts"]["parallel_empty_scene_occurrence_count"], 7)
        self.assertEqual(
            next(
                row
                for row in result["event_containers"]
                if row["event"] == "ac0908_010"
            )["container_frames_parallel_max"],
            498,
        )
        self.assertEqual(
            result["counts"]["strict_no_bgm_excluded_bgm_component_occurrence_count"],
            6,
        )
        win = next(
            row
            for row in result["canonical_strict_no_bgm_envelopes"]
            if row["canonical_cut_name"] == "ac8004_004"
        )
        self.assertEqual(win["excluded_bgm_sound_ids"], [553])
        self.assertAlmostEqual(win["strict_no_bgm_envelope_seconds_candidate"], 4.824)
        self.assertEqual(result["duration_audit"]["canonical_unique_visual_frames"], 3751)
        self.assertFalse(result["duration_audit"]["final_audience_duration_resolved"])
        comparison = result["legacy_longform_code_comparison"]
        self.assertEqual(4, comparison["repeated_event_container_reference_surplus_count"])
        self.assertEqual(2, comparison["guaranteed_exact_duplicate_render_occurrence_surplus_count"])
        self.assertEqual(9, comparison["represented_canonical_visible_scene_count"])
        self.assertEqual(5, comparison["missing_canonical_visible_scene_count"])
        self.assertEqual(
            ["ac0908_001"],
            comparison["same_container_different_trim_overlap_not_quantified"],
        )
        self.assertFalse(comparison["exhaustive_authoritative"])


if __name__ == "__main__":
    unittest.main()
