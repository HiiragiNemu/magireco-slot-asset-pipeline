import unittest

from tools.frida_runtime_probe import resolve_ac1104_movie_layer_reachability as m


def node(name, start, end):
    return {
        "name": name + ".z2d",
        "motions": [
            {
                "is_z2d_motion": True,
                "keys": [{"floats": [start, end, start, end, start, end]}],
            }
        ],
        "children": [],
    }


class Ac1104ReachabilityTests(unittest.TestCase):
    def runtime_fixture(self):
        events = {}
        for event, ranges in m.EXPECTED_PARENT_RANGES.items():
            events[event] = {
                "scenes": [
                    {
                        "name": event,
                        "cuts": [
                            {
                                "cut_name": event,
                                "instance_offset_frames": 0,
                                "cut_start_frame": 0,
                                "cut_end_frame": max(end for _, end in ranges.values()),
                                "nodes": [node(name, start, end) for name, (start, end) in ranges.items()],
                            }
                        ],
                    }
                ]
            }
        return {
            "schema": "magireco-ac1104-runtime-scene-motion-v1",
            "host_frida_version": "17.16.4",
            "protected_processes_unchanged": True,
            "crash_buffer_unchanged": True,
            "process_restart_or_app_switch_performed": False,
            "module_rows": [list(m.EXPECTED_MODULE)],
            "events": events,
        }

    def test_runtime_parent_ranges_cover_all_seventeen_events(self):
        result = m.extract_runtime_parent_ranges(self.runtime_fixture())
        self.assertEqual(set(result), set(m.EVENTS))
        self.assertEqual(sum(len(row["z2d_parent_ranges"]) for row in result.values()), 23)
        self.assertEqual(
            result["ac1104_017"]["z2d_parent_ranges"]
            ["ac1104_1on_c021_c022_c023_c024_c025_c026_fukkatu_win"],
            {"start_frame": 0, "end_frame_inclusive": 406},
        )

    def test_runtime_capture_is_fail_closed_on_process_change(self):
        fixture = self.runtime_fixture()
        fixture["protected_processes_unchanged"] = False
        with self.assertRaisesRegex(m.Ac1104ReachabilityError, "processes changed"):
            m.extract_runtime_parent_ranges(fixture)

    def test_unreachable_alias_requires_same_interval_loadable_twin(self):
        rows = []
        for unreachable, twin in m.UNREACHABLE_TO_LOADABLE_TWIN.items():
            common = {
                "start_frame": 0,
                "end_frame_inclusive": 29,
                "position": [512.0, 288.0],
                "pivot": [0.0, 0.0],
                "layer_width": 1024,
                "layer_height": 576,
            }
            rows.append(
                {"z2d_reference": unreachable, "compiled_table_present": False, "authored_blend_enum": 2, **common}
            )
            rows.append(
                {"z2d_reference": twin, "compiled_table_present": True, "authored_blend_enum": 0, **common}
            )
        result = m.classify_unreachable_twins(rows)
        self.assertEqual(len(result), 4)

    def test_constants_bind_full_event17_revival(self):
        self.assertEqual(len(m.REQUIRED_Z2D_NAMES), 19)
        self.assertEqual(len(m.MISSING_LEGACY_EVENT17_DGMS), 7)
        self.assertEqual(sum(map(len, m.EXPECTED_PARENT_RANGES.values())), 23)


if __name__ == "__main__":
    unittest.main()
