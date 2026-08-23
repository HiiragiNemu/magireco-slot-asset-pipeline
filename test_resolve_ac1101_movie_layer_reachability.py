import unittest

from tools.frida_runtime_probe import resolve_ac1101_movie_layer_reachability as m


def node(name, start, end):
    return {
        "name": name + ".z2d",
        "motions": [
            {
                "is_z2d_motion": True,
                "keys": [{"floats": [start, end, start, end, start, end, -1]}],
            }
        ],
        "children": [],
    }


class Ac1101ReachabilityTests(unittest.TestCase):
    def runtime_fixture(self):
        events = {}
        for event, bindings in m.EXPECTED_BINDINGS.items():
            scenes = {}
            for scene_name, cut_name, offset, z2d_name, start, end in bindings:
                key = (scene_name, cut_name, offset)
                scenes.setdefault(key, []).append(node(z2d_name, start, end))
            events[event] = {
                "scenes": [
                    {
                        "name": scene_name,
                        "cuts": [
                            {
                                "cut_name": cut_name,
                                "instance_offset_frames": offset,
                                "cut_start_frame": 0,
                                "cut_end_frame": max(
                                    end
                                    for row in bindings
                                    if row[0] == scene_name and row[1] == cut_name
                                    for end in [row[5]]
                                ),
                                "nodes": nodes,
                            }
                        ],
                    }
                    for (scene_name, cut_name, offset), nodes in scenes.items()
                ]
            }
        return {
            "schema": "magireco-ac1101-runtime-scene-motion-v1",
            "host_frida_version": "17.16.4",
            "protected_processes_unchanged": True,
            "crash_buffer_unchanged": True,
            "process_restart_or_app_switch_performed": False,
            "module_rows": [list(m.EXPECTED_MODULE)],
            "events": events,
        }

    def test_runtime_bindings_cover_secondary_scenes(self):
        result = m.extract_runtime_bindings(self.runtime_fixture())
        self.assertEqual(set(result), set(m.EVENTS))
        self.assertEqual(sum(map(len, result.values())), 20)
        self.assertEqual(
            [row for row in result["ac1101_003"] if row["scene_name"] == "TUDUKU"][0]
            ["event_global_end_frame_inclusive"],
            249,
        )
        self.assertEqual(
            [row for row in result["ac1101_005"] if row["scene_name"] == "ANTEN"][0]
            ["event_global_start_frame"],
            53,
        )

    def test_runtime_capture_fails_closed_on_app_switch(self):
        fixture = self.runtime_fixture()
        fixture["process_restart_or_app_switch_performed"] = True
        with self.assertRaisesRegex(m.Ac1101ReachabilityError, "switched"):
            m.extract_runtime_bindings(fixture)

    def test_secondary_scene_offset_is_hash_bound(self):
        fixture = self.runtime_fixture()
        fixture["events"]["ac1101_003"]["scenes"][1]["cuts"][0]["instance_offset_frames"] = 129
        with self.assertRaisesRegex(m.Ac1101ReachabilityError, "offset differs"):
            m.extract_runtime_bindings(fixture)

    def test_unreachable_alias_requires_loadable_same_interval_twin(self):
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
            rows.append({"z2d_reference": unreachable, "compiled_table_present": False, **common})
            rows.append({"z2d_reference": twin, "compiled_table_present": True, **common})
        self.assertEqual(len(m.classify_unreachable_twins(rows)), 4)

    def test_constants_bind_full_ac1101_set(self):
        self.assertEqual(len(m.EVENTS), 13)
        self.assertEqual(len(m.REQUIRED_Z2D_NAMES), 17)
        self.assertEqual(sum(map(len, m.EXPECTED_BINDINGS.values())), 20)
        self.assertEqual(len(m.LEGACY_MISSING_LOADABLE_DGMS), 3)


if __name__ == "__main__":
    unittest.main()
