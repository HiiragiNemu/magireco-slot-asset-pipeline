import json
import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_ac1103_event_global_route_inputs import (
    CHILD_TIMING_EVENTS,
    EVENTS,
    LOCK_FRAMES,
    ROUTES,
    exact_key,
    validate_dirinfo,
    validate_runtime,
)


class Ac1103EventGlobalRouteInputsTests(unittest.TestCase):
    def test_all_31_source_resolved_dirinfo_rows_are_preserved(self) -> None:
        rows = []
        for row_index, events in ROUTES.items():
            rows.extend(
                {
                    "kind": "55",
                    "row_index": str(row_index),
                    "selector_raw": str(selector),
                    "scene_name": event,
                    "resolved_source_count": "1",
                }
                for selector, event in enumerate(events)
            )
        result = validate_dirinfo(rows)
        self.assertEqual(len(result["source_resolved_routes"]), 31)
        self.assertEqual(result["blocked_routes"], {})
        self.assertEqual(result["source_resolved_routes"]["30"], list(ROUTES[30]))

    def test_runtime_and_lockframe_contract_requires_every_event(self) -> None:
        runtime = {
            "schema": "magireco-ac1103-runtime-scene-motion-v1",
            "host_frida_version": "17.16.4",
            "protected_processes_unchanged": True,
            "crash_tail_empty": True,
            "requested_events": {event: event for event in EVENTS},
            "events": {event: {} for event in EVENTS},
        }
        lockframes = {
            "schema": "magireco-ac1103-runtime-lockframe-v1",
            "host_frida_version": "17.16.4",
            "protected_processes_unchanged": True,
            "crash_tail_empty": True,
            "events": {
                event: {"lock_frame": frame}
                for event, frame in LOCK_FRAMES.items()
            },
        }
        validate_runtime(runtime, lockframes)
        runtime["events"].pop("ac1103_013")
        with self.assertRaisesRegex(ValueError, "bounded ac1103 scene capture differs"):
            validate_runtime(runtime, lockframes)

    def test_exact_key_rejects_active_time_remap(self) -> None:
        node = {
            "time_remap_pointer": None,
            "motions": [
                {"is_z2d_motion": True, "keys": [{"index": 0, "floats": [29.0]}]}
            ],
        }
        layer = {"speed": 1.0}
        key, actual_layer, layer_name = exact_key(
            {"cap1103_test": (node, layer, "layer")},
            "ac1103_001",
            "cap1103_test",
        )
        self.assertEqual(key["floats"][0], 29.0)
        self.assertIs(actual_layer, layer)
        self.assertEqual(layer_name, "layer")
        node["time_remap_pointer"] = "0x1"
        with self.assertRaisesRegex(ValueError, "time remap is active"):
            exact_key(
                {"cap1103_test": (node, layer, "layer")},
                "ac1103_001",
                "cap1103_test",
            )

    def test_repository_overrides_cover_only_child_timing_events(self) -> None:
        root = (
            Path(__file__).resolve().parent
            / "tools"
            / "frida_runtime_probe"
            / "z2d_event_timing_overrides"
        )
        files = sorted(root.glob("ac1103_*_parent_scene_motion_key_v1.json"))
        payloads = [json.loads(path.read_text(encoding="utf-8")) for path in files]
        self.assertEqual({row["event"] for row in payloads}, set(CHILD_TIMING_EVENTS))
        self.assertEqual(len(payloads), 12)
        self.assertTrue(
            all(row["schema"] == "magireco-z2d-event-timing-override-v1" for row in payloads)
        )


if __name__ == "__main__":
    unittest.main()
