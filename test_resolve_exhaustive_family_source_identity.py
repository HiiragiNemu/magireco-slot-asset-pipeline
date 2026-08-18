from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.resolve_ac1102_exhaustive_unique_segments import (
    EXACT_SLOT_SHA256,
)
from tools.frida_runtime_probe.resolve_exhaustive_family_source_identity import (
    derive_routes,
    resolve,
)


FAMILY = "ac9999"
EVENTS = ("ac9999_001", "ac9999_002")


def node(name: str) -> dict:
    return {
        "type": 20,
        "name": name,
        "motions": [{"is_z2d_motion": True, "keys": []}],
        "children": [],
    }


def runtime() -> dict:
    return {
        "schema": "magireco-ac9999-runtime-scene-motion-v1",
        "host_frida_version": "17.16.4",
        "protected_processes_unchanged": True,
        "crash_tail_empty": True,
        "requested_events": {event: "0x1" for event in EVENTS},
        "events": {
            event: {
                "group_name": FAMILY,
                "scenes": [
                    {
                        "name": event,
                        "cuts": [
                            {
                                "cut_name": event,
                                "instance_offset_frames": 0,
                                "cut_start_frame": 0,
                                "cut_end_frame": 29,
                                "nodes": [node(event + ".z2d")],
                            }
                        ],
                    }
                ],
            }
            for event in EVENTS
        },
    }


def lockframes() -> dict:
    return {
        "schema": "magireco-ac9999-runtime-lockframe-v1",
        "host_frida_version": "17.16.4",
        "protected_processes_unchanged": True,
        "crash_tail_empty": True,
        "events": {event: {"lock_frame": 0} for event in EVENTS},
    }


def routes() -> list[dict[str, str]]:
    return [
        {
            "kind": "99",
            "row_index": "0",
            "selector_raw": "0",
            "scene_name": EVENTS[0],
            "resolved_source_count": "2",
        },
        {
            "kind": "99",
            "row_index": "0",
            "selector_raw": "2",
            "scene_name": EVENTS[1],
            "resolved_source_count": "0",
        },
        {
            "kind": "99",
            "row_index": "1",
            "selector_raw": "0",
            "scene_name": EVENTS[1],
            "resolved_source_count": "0",
        },
    ]


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


class ExhaustiveFamilySourceIdentityTests(unittest.TestCase):
    def test_dirinfo_derives_complete_contiguous_route_universe(self):
        result = derive_routes(routes(), FAMILY, 99, 2)
        self.assertEqual(2, result["route_count"])
        self.assertEqual(list(EVENTS), result["unique_events"])
        with self.assertRaisesRegex(ValueError, "complete zero-based range"):
            derive_routes(routes()[:2], FAMILY, 99, 2)

    def test_source_identical_occurrences_are_counted_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shared = root / "shared.mp4"
            unique = root / "unique.mp4"
            component = root / "component.mp4"
            for path in (shared, unique, component):
                path.write_bytes(path.name.encode("ascii"))
            rows = [
                {
                    "event_name": EVENTS[0],
                    "z2d_name": "z1",
                    "dgm_name": "shared",
                    "package": "main",
                    "package_index": "1",
                    "official_name": "shared",
                    "source_exists": "yes",
                    "source_mp4": str(shared),
                    "width": "416",
                    "height": "232",
                },
                {
                    "event_name": EVENTS[1],
                    "z2d_name": "z2",
                    "dgm_name": "shared",
                    "package": "main",
                    "package_index": "1",
                    "official_name": "shared",
                    "source_exists": "yes",
                    "source_mp4": str(shared),
                    "width": "416",
                    "height": "232",
                },
                {
                    "event_name": EVENTS[1],
                    "z2d_name": "z2",
                    "dgm_name": "unique",
                    "package": "main",
                    "package_index": "2",
                    "official_name": "unique",
                    "source_exists": "yes",
                    "source_mp4": str(unique),
                    "width": "416",
                    "height": "232",
                },
                {
                    "event_name": EVENTS[1],
                    "z2d_name": "effect",
                    "dgm_name": "component",
                    "package": "patch",
                    "package_index": "3",
                    "official_name": "component",
                    "source_exists": "yes",
                    "source_mp4": str(component),
                    "width": "256",
                    "height": "144",
                },
                {
                    "event_name": EVENTS[1],
                    "z2d_name": "effect",
                    "dgm_name": "component_add",
                    "package": "",
                    "package_index": "",
                    "official_name": "",
                    "source_exists": "no",
                    "source_mp4": "",
                    "width": "0",
                    "height": "0",
                },
            ]
            result = resolve(
                family=FAMILY,
                dirinfo_kind=99,
                expected_route_count=2,
                native_width=416,
                native_height=232,
                runtime=runtime(),
                lockframes=lockframes(),
                dirinfo_rows=routes(),
                source_rows=rows,
                legacy_manifest={
                    "ordered_events": list(EVENTS),
                    "media": {"duration_ms": 2000},
                },
                ida_event_av=ida_evidence(),
            )
        self.assertEqual(3, result["native_source_universe"]["occurrence_count"])
        self.assertEqual(
            2, result["native_source_universe"]["unique_source_identity_count"]
        )
        self.assertEqual(
            1,
            result["native_source_universe"]["duplicate_surplus_occurrence_count"],
        )
        self.assertTrue(result["legacy_longform"]["complete_event_set"])
        self.assertFalse(result["legacy_longform"]["duplicate_free"])
        self.assertFalse(result["decision"]["legacy_longform_final_authority"])
        self.assertFalse(result["decision"]["new_render_allowed"])

    def test_missing_lockframe_capture_is_a_render_blocker_not_an_audit_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.mp4"
            source.write_bytes(b"source")
            rows = [
                {
                    "event_name": event,
                    "z2d_name": event,
                    "dgm_name": event,
                    "package": "main",
                    "package_index": str(index),
                    "official_name": event,
                    "source_exists": "yes",
                    "source_mp4": str(source),
                    "width": "416",
                    "height": "232",
                }
                for index, event in enumerate(EVENTS, 1)
            ]
            result = resolve(
                family=FAMILY,
                dirinfo_kind=99,
                expected_route_count=2,
                native_width=416,
                native_height=232,
                runtime=runtime(),
                lockframes=None,
                dirinfo_rows=routes(),
                source_rows=rows,
                legacy_manifest={
                    "ordered_events": list(EVENTS),
                    "media": {"duration_ms": 2000},
                },
                ida_event_av=ida_evidence(),
            )
        blocker_kinds = {row["kind"] for row in result["decision"]["blockers"]}
        self.assertIn("runtime_lockframe_capture_missing", blocker_kinds)
        self.assertFalse(result["decision"]["new_render_allowed"])

    def test_partial_source_catalog_keeps_structure_audit_and_blocks_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.mp4"
            source.write_bytes(b"source")
            rows = [
                {
                    "event_name": EVENTS[0],
                    "z2d_name": EVENTS[0],
                    "dgm_name": EVENTS[0],
                    "package": "main",
                    "package_index": "1",
                    "official_name": EVENTS[0],
                    "source_exists": "yes",
                    "source_mp4": str(source),
                    "width": "416",
                    "height": "232",
                }
            ]
            result = resolve(
                family=FAMILY,
                dirinfo_kind=99,
                expected_route_count=2,
                native_width=416,
                native_height=232,
                runtime=runtime(),
                lockframes=None,
                dirinfo_rows=routes(),
                source_rows=rows,
                legacy_manifest={
                    "ordered_events": list(EVENTS),
                    "media": {"duration_ms": 2000},
                },
                ida_event_av=ida_evidence(),
            )
        self.assertEqual(1, result["source_catalog_coverage"]["covered_event_count"])
        self.assertEqual([EVENTS[1]], result["source_catalog_coverage"]["missing_events"])
        blocker_kinds = {row["kind"] for row in result["decision"]["blockers"]}
        self.assertIn("source_catalog_missing_events", blocker_kinds)
        self.assertFalse(result["decision"]["legacy_longform_final_authority"])


if __name__ == "__main__":
    unittest.main()
