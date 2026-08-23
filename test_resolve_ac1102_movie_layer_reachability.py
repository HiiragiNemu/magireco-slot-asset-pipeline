from __future__ import annotations

import copy
import unittest

from tools.frida_runtime_probe.resolve_ac1102_movie_layer_reachability import (
    Ac1102ReachabilityError,
    EXPECTED_PARENT_RANGES,
    UNREACHABLE_TO_LOADABLE_TWIN,
    classify_unreachable_twins,
    extract_runtime_parent_ranges,
)


def runtime_fixture() -> dict:
    events = {}
    for event, mappings in EXPECTED_PARENT_RANGES.items():
        nodes = []
        for name, (start, end) in mappings.items():
            nodes.append(
                {
                    "name": f"{name}.z2d",
                    "motions": [
                        {
                            "is_z2d_motion": True,
                            "keys": [
                                {
                                    "floats": [
                                        start,
                                        end,
                                        start,
                                        end,
                                        start,
                                        end,
                                        -1,
                                    ]
                                }
                            ],
                        }
                    ],
                    "children": [],
                }
            )
        events[event] = {
            "status": "captured",
            "value": {
                "scenes": [
                    {
                        "name": event,
                        "cuts": [
                            {
                                "cut_name": event,
                                "cut_start_frame": 0,
                                "cut_end_frame": max(end for _, end in mappings.values()),
                                "nodes": [{"name": "root", "motions": [], "children": nodes}],
                            }
                        ],
                    }
                ]
            },
        }
    return {
        "schema": "magireco-ac1102-missing-runtime-scene-motion-v1",
        "protected_processes_unchanged": True,
        "crash_tail_empty": True,
        "events": events,
    }


def layer(reference: str, *, present: bool, start: int, end: int) -> dict:
    return {
        "z2d_reference": reference,
        "compiled_table_present": present,
        "start_frame": start,
        "end_frame_inclusive": end,
        "position": [512.0, 288.0],
        "pivot": [512.0, 288.0],
        "layer_width": 1024,
        "layer_height": 576,
        "authored_blend_enum": 2 if not present else 0,
    }


class Ac1102MovieLayerReachabilityTests(unittest.TestCase):
    def test_extracts_exact_parent_event_ranges(self) -> None:
        result = extract_runtime_parent_ranges(runtime_fixture())
        self.assertEqual(set(result), set(EXPECTED_PARENT_RANGES))
        self.assertEqual(
            result["ac1102_007"]["z2d_parent_ranges"]["ac1102_3off_c015_win_rogo"],
            {"start_frame": 232, "end_frame_inclusive": 381},
        )
        self.assertEqual(
            result["ac1102_015"]["z2d_parent_ranges"]["ac1102_3off_c015_win_rogo"],
            {"start_frame": 343, "end_frame_inclusive": 492},
        )

    def test_parent_triplet_mismatch_fails_closed(self) -> None:
        value = runtime_fixture()
        key = value["events"]["ac1102_007"]["value"]["scenes"][0]["cuts"][0][
            "nodes"
        ][0]["children"][0]["motions"][0]["keys"][0]
        key["floats"][2] += 1
        with self.assertRaisesRegex(Ac1102ReachabilityError, "triplets differ"):
            extract_runtime_parent_ranges(value)

    def test_classifies_all_four_unreachable_layers_with_exact_twins(self) -> None:
        rows = []
        for index, (unreachable, twin) in enumerate(UNREACHABLE_TO_LOADABLE_TWIN.items()):
            start, end = index * 30, index * 30 + 29
            rows.extend(
                [
                    layer(unreachable, present=False, start=start, end=end),
                    layer(twin, present=True, start=start, end=end),
                ]
            )
        result = classify_unreachable_twins(rows)
        self.assertEqual(len(result), 4)
        self.assertTrue(
            all(
                row["runtime_disposition"]
                == "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"
                for row in result
            )
        )

    def test_missing_or_timing_different_twin_fails_closed(self) -> None:
        rows = []
        for index, (unreachable, twin) in enumerate(UNREACHABLE_TO_LOADABLE_TWIN.items()):
            rows.extend(
                [
                    layer(unreachable, present=False, start=index, end=index + 1),
                    layer(twin, present=True, start=index, end=index + 1),
                ]
            )
        broken = copy.deepcopy(rows)
        broken[1]["end_frame_inclusive"] += 1
        with self.assertRaisesRegex(Ac1102ReachabilityError, "geometry/timing differ"):
            classify_unreachable_twins(broken)


if __name__ == "__main__":
    unittest.main()
