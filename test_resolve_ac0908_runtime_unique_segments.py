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

    def test_real_shape_resolves_aliases_and_blank_holds(self):
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
        prior = {
            "event_containers": [
                {"event": event, "static_audio_component_span_ms": "1000"}
                for event in REQUIRED_EVENTS
            ]
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
        result = resolve(runtime, prior, dgm, ida)
        self.assertEqual(result["counts"]["canonical_unique_visible_scene_count"], 14)
        self.assertEqual(result["counts"]["visible_scene_occurrence_count"], 17)
        self.assertEqual(result["counts"]["exact_duplicate_visible_surplus_count"], 3)
        self.assertEqual(result["counts"]["blank_hold_occurrence_count"], 7)
        self.assertEqual(result["duration_audit"]["canonical_unique_visual_frames"], 3751)
        self.assertFalse(result["duration_audit"]["final_audience_duration_resolved"])


if __name__ == "__main__":
    unittest.main()
