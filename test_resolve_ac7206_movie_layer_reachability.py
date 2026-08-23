import unittest

from tools.frida_runtime_probe import resolve_ac7206_movie_layer_reachability as m


def node(name, start, end, *, suffix=True):
    return {"name": name + (".z2d" if suffix else ""), "motions": [{
        "is_z2d_motion": True,
        "keys": [{"floats": [start, end, start, end, start, end, -1]}],
    }], "children": []}


class Ac7206ReachabilityTests(unittest.TestCase):
    def runtime_fixture(self):
        events = {}
        for event in m.EVENTS:
            cuts = {}
            for scene, cut, offset, cut_start, cut_end in m.EXPECTED_CUT_RANGES[event]:
                cuts[(scene, cut)] = {"cut_name": cut, "instance_offset_frames": offset,
                                      "cut_start_frame": cut_start, "cut_end_frame": cut_end, "nodes": []}
            for scene, cut, _, name, start, end, _ in m.EXPECTED_BINDINGS[event]:
                cuts[(scene, cut)]["nodes"].append(node(name, start, end))
            if event == m.GAMEPLAY_EVENT:
                for name in m.LOGICAL_SELECTOR_NAMES:
                    cuts[("uwa", "ac8050_004")]["nodes"].append(node(name, 0, 239, suffix=False))
            scenes = {}
            for (scene, _), cut_value in cuts.items():
                scenes.setdefault(scene, []).append(cut_value)
            events[event] = {
                "module": {**m.EXPECTED_MODULE, "base": "0x1234"},
                "event_code": f"code-{event}",
                "scenes": [{"name": scene, "cuts": values} for scene, values in scenes.items()],
            }
        return {
            "schema": "magireco-ac7206-runtime-scene-motion-v1",
            "host_frida_version": "17.16.4",
            "protected_processes_unchanged": True,
            "crash_tail_empty": True,
            "requested_events": {event: f"code-{event}" for event in m.EVENTS},
            "events": events,
        }

    def test_runtime_bindings_cover_story_and_gameplay(self):
        result = m.extract_runtime_bindings(self.runtime_fixture())
        self.assertEqual(set(result["events"]), set(m.EVENTS))
        self.assertEqual(sum(map(len, result["events"].values())), 30)
        self.assertEqual(len(result["logical_selector_nodes"]), 5)
        self.assertEqual(result["events"]["ac7206_002"][0]["event_global_end_frame_inclusive"], 204)
        self.assertEqual(result["events"]["ac7206_015"][0]["role"], "gameplay_effect")

    def test_runtime_fails_closed_on_protected_process_change(self):
        fixture = self.runtime_fixture()
        fixture["protected_processes_unchanged"] = False
        with self.assertRaisesRegex(m.Ac7206ReachabilityError, "protected"):
            m.extract_runtime_bindings(fixture)

    def test_runtime_fails_closed_on_logical_selector_loss(self):
        fixture = self.runtime_fixture()
        uwa = [row for row in fixture["events"][m.GAMEPLAY_EVENT]["scenes"] if row["name"] == "uwa"][0]
        uwa["cuts"][0]["nodes"].pop()
        with self.assertRaisesRegex(m.Ac7206ReachabilityError, "logical selector set"):
            m.extract_runtime_bindings(fixture)

    def test_runtime_fails_closed_on_parent_range_change(self):
        fixture = self.runtime_fixture()
        fixture["events"]["ac7206_001"]["scenes"][0]["cuts"][0]["nodes"][0]["motions"][0]["keys"][0]["floats"][1] = 58
        with self.assertRaisesRegex(m.Ac7206ReachabilityError, "triplets differ|range differs"):
            m.extract_runtime_bindings(fixture)

    def test_logical_selector_backing_is_exact(self):
        names = set()
        for place in ("0001", "0010", "0100", "1000"):
            names.add(f"ac8050_null_uwa_suji_keta_{place}")
            names.add(f"ac8050_null_uwa_suji_keta_{place}_sub")
            names.update(f"ac8050_tx_count_uwa_{place}_suji_{digit:02d}" for digit in range(10))
        result = m.resolve_logical_selector_backing(names)
        self.assertEqual([row["physical_backing_count"] for row in result], [8, 10, 10, 10, 10])
        names.remove("ac8050_tx_count_uwa_1000_suji_09")
        with self.assertRaisesRegex(m.Ac7206ReachabilityError, "physical backing differs"):
            m.resolve_logical_selector_backing(names)

    def test_constants_bind_full_ac7206_set(self):
        self.assertEqual(len(m.EVENTS), 15)
        self.assertEqual(len(m.STORY_EVENTS), 14)
        self.assertEqual(len(m.REQUIRED_Z2D_NAMES), 14)
        self.assertEqual(sum(map(len, m.EXPECTED_BINDINGS.values())), 30)
        self.assertEqual(len(m.LOGICAL_SELECTOR_NAMES), 5)


if __name__ == "__main__":
    unittest.main()
