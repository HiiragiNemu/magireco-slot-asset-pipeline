from __future__ import annotations

import unittest
from pathlib import Path

from tools.frida_runtime_probe.resolve_ac1102_exhaustive_unique_segments import (
    EXACT_SLOT_SHA256,
    LEGACY_EVENTS,
    REQUIRED_EVENTS,
    cut_frames,
    cut_structure,
    resolve,
    route_universe,
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


def cut(event: str, frames: int = 30) -> dict:
    return {
        "cut_name": event,
        "instance_offset_frames": 0,
        "cut_start_frame": 0,
        "cut_end_frame": frames - 1,
        "nodes": [node(event + ".z2d")],
    }


def event_value(event: str) -> dict:
    return {
        "group_name": "ac1102",
        "scenes": [{"name": event, "cuts": [cut(event)]}],
    }


def capture(schema: str, events: tuple[str, ...], wrapped: bool) -> dict:
    return {
        "schema": schema,
        "host_frida_version": "17.16.4",
        "protected_processes_unchanged": True,
        "crash_tail_empty": True,
        "requested_events": {event: "0x1" for event in events},
        "events": {
            event: (
                {"status": "captured", "value": event_value(event)}
                if wrapped
                else event_value(event)
            )
            for event in events
        },
    }


def lock_capture(schema: str, events: tuple[str, ...]) -> dict:
    return {
        "schema": schema,
        "host_frida_version": "17.16.4",
        "protected_processes_unchanged": True,
        "crash_tail_empty": True,
        "requested_events": {event: "0x1" for event in events},
        "events": {event: {"lock_frame": 0} for event in events},
    }


def route_rows() -> list[dict[str, str]]:
    rows = []
    for index in range(31):
        event = REQUIRED_EVENTS[index % len(REQUIRED_EVENTS)]
        rows.append(
            {
                "kind": "54",
                "row_index": str(index),
                "selector_raw": "0",
                "scene_name": event,
                "resolved_source_count": "0" if event.endswith(("007", "013")) else "2",
            }
        )
    return rows


def source_fixture() -> tuple[list[dict[str, str]], dict]:
    native_paths = [str(Path(f"C:/fake/native_{index:02d}.mp4").resolve()) for index in range(36)]
    component_paths = [
        str(Path(f"C:/fake/component_{index:02d}.mp4").resolve()) for index in range(2)
    ]
    entries = [
        {
            "path": path,
            "sha256": f"{index + 1:064X}",
            "size_bytes": 1000 + index,
        }
        for index, path in enumerate(native_paths + component_paths)
    ]
    rows: list[dict[str, str]] = []
    occurrence_paths = native_paths + native_paths[:17]
    for index, path in enumerate(occurrence_paths):
        event = REQUIRED_EVENTS[index % len(REQUIRED_EVENTS)]
        rows.append(
            {
                "event_name": event,
                "z2d_name": f"z{index}",
                "dgm_name": f"d{index}",
                "official_name": Path(path).stem,
                "source_exists": "yes",
                "source_mp4": path,
                "width": "416",
                "height": "232",
            }
        )
    for index in range(6):
        path = component_paths[index % 2]
        rows.append(
            {
                "event_name": REQUIRED_EVENTS[6 + index],
                "z2d_name": "shared_effect",
                "dgm_name": f"component_{index % 2}",
                "official_name": Path(path).stem,
                "source_exists": "yes",
                "source_mp4": path,
                "width": "256",
                "height": "144",
            }
        )
    missing_names = ("add", "add_lp", "logo_add", "logo_add_lp")
    for index in range(10):
        rows.append(
            {
                "event_name": REQUIRED_EVENTS[6 + index % 9],
                "z2d_name": "missing_effect",
                "dgm_name": missing_names[index % len(missing_names)],
                "official_name": "",
                "source_exists": "no",
                "source_mp4": "",
                "width": "0",
                "height": "0",
            }
        )
    authority = {
        "schema": "magireco-ac1102-bounded-source-hash-authority-v1",
        "status": "PASS",
        "consumer": "tools/frida_runtime_probe/resolve_ac1102_exhaustive_unique_segments.py",
        "entry_count": 38,
        "entries": entries,
        "source_media_modified": False,
    }
    return rows, authority


def ida_evidence() -> dict:
    return {
        "schema": "magireco-ida-event-av-parallel-start-evidence-v1",
        "status": "passed",
        "binary": {"sha256": EXACT_SLOT_SHA256.upper()},
        "semantic_assertions": {
            "graphics_and_sound_receive_same_event_code": True,
            "all_scene_names_are_set_at_time_zero": True,
            "same_event_scene_scheduling": "parallel_shared_event_global_origin",
            "scene_container_duration_rule": "maximum_scene_duration_not_sum",
            "machine_vision_used_as_authority": False,
        },
    }


class Ac1102ExhaustiveUniqueSegmentTests(unittest.TestCase):
    def test_cut_structure_ignores_runtime_pointers_and_duration_is_inclusive(self):
        value = cut("x", 30)
        value["instance_offset_frames"] = 5
        self.assertEqual(cut_frames(value), 35)
        first = structure_key(cut_structure(value))
        value["cut_pointer"] = "0x1234"
        value["nodes"][0]["pointer"] = "0x5678"
        self.assertEqual(first, structure_key(cut_structure(value)))

    def test_dirinfo_requires_all_31_rows_and_all_15_events(self):
        result = route_universe(route_rows())
        self.assertEqual(31, result["route_count"])
        self.assertEqual(15, result["unique_event_count"])
        broken = route_rows()[:-1]
        with self.assertRaisesRegex(ValueError, "rows 0 through 30"):
            route_universe(broken)

    def test_resolve_counts_exact_sources_and_rejects_old_longform(self):
        missing = tuple(event for event in REQUIRED_EVENTS if event not in LEGACY_EVENTS)
        sources, hashes = source_fixture()
        result = resolve(
            capture("magireco-ac1102-runtime-scene-motion-v1", LEGACY_EVENTS, False),
            lock_capture("magireco-ac1102-runtime-lockframe-v1", LEGACY_EVENTS),
            capture(
                "magireco-ac1102-missing-runtime-scene-motion-v1", missing, True
            ),
            lock_capture("magireco-ac1102-missing-runtime-lockframe-v1", missing),
            route_rows(),
            sources,
            {
                "ordered_events": list(LEGACY_EVENTS),
                "media": {"duration_ms": 91800},
            },
            ida_evidence(),
            hashes,
        )
        self.assertEqual("PASS_RENDER_PAUSED", result["status"])
        self.assertEqual(31, result["route_universe"]["route_count"])
        self.assertEqual(15, result["runtime_structure"]["event_count"])
        self.assertEqual(53, result["native_source_universe"]["occurrence_count"])
        self.assertEqual(36, result["native_source_universe"]["unique_sha256_count"])
        self.assertEqual(
            17,
            result["native_source_universe"]["duplicate_surplus_occurrence_count"],
        )
        self.assertEqual(6, result["related_component_universe"]["present_occurrence_count"])
        self.assertEqual(2, result["related_component_universe"]["present_unique_sha256_count"])
        self.assertEqual(10, result["related_component_universe"]["missing_occurrence_count"])
        self.assertEqual(4, result["related_component_universe"]["missing_unique_identity_count"])
        self.assertFalse(result["legacy_longform"]["exhaustive_authoritative"])
        self.assertFalse(result["decision"]["new_render_allowed"])


if __name__ == "__main__":
    unittest.main()
