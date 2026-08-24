from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import (
    build_ac4901_gfdirection_presentation_authority as MODULE,
)


def fake_authority(parallel_events: int = 115) -> dict:
    event_presentations = {}
    events = []
    for index, event_id in enumerate(MODULE.EVENT_IDS):
        scene_count = 2 if index < parallel_events else 1
        event_presentations[event_id] = {
            "frames": 120,
            "parallel_scenes": [f"scene_{index}_{n}" for n in range(scene_count)],
        }
        events.append(
            {
                "event_id": event_id,
                "presentation_frame_count": 120,
                "scenes": [
                    {
                        "parallel_scene_order": 0,
                        "name": f"scene_{index}_0",
                        "type2_presentation_frame_count": 120,
                        "cuts": [
                            {
                                "cut_name": f"cut_{index}",
                                "instance_offset_frames": 0,
                                "z2d_nodes": [
                                    {
                                        "event_id": event_id,
                                        "owning_layer": {
                                            "canonical_name": "通常画面",
                                            "hash_words": [1, 2],
                                            "effective_viewport": {
                                                "left": 128,
                                                "top": 0,
                                                "width": 1024,
                                                "height": 576,
                                            },
                                        },
                                        "z2d_node": f"node_{index}",
                                        "node_authority_class": "exact_apk_z2d",
                                        "motion_keys": [],
                                        "transform": {
                                            "opacity": {"mode": "static", "value": 1.0}
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )
    return {
        "schema": "old",
        "status": "passed_code_runtime_cross_bound_projection_pending",
        "events": events,
        "summary": {
            **MODULE.EXPECTED_COUNTS,
            "event_presentations": event_presentations,
        },
        "assertions": {},
    }


class Ac4901PresentationAuthorityTests(unittest.TestCase):
    def test_exact_contract_contains_all_205_events(self) -> None:
        self.assertEqual(205, len(MODULE.EVENT_IDS))
        self.assertEqual("ac4901_001", MODULE.EVENT_IDS[0])
        self.assertEqual("ac4901_256", MODULE.EVENT_IDS[-1])
        self.assertEqual(112, MODULE.EXPECTED_GROUP_INDEX)

    def test_derives_parallel_extent_from_all_static_type2_scenes(self) -> None:
        type2 = [
            {"name": event_id, "presentation_frame_count": 120}
            for event_id in MODULE.EVENT_IDS
        ]
        type2.append({"name": "UWA", "presentation_frame_count": 240})
        runtime_events = {
            event_id: {"scenes": [{"name": event_id}]}
            for event_id in MODULE.EVENT_IDS
        }
        runtime_events[MODULE.EVENT_IDS[0]]["scenes"].append({"name": "UWA"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = root / "scene.json"
            runtime = root / "runtime.json"
            scene.write_text(
                json.dumps(
                    {
                        "group": {
                            "name": "ac4901",
                            "compiled_index": 112,
                            "type2_presentations": type2,
                        }
                    }
                ),
                encoding="utf-8",
            )
            runtime.write_text(
                json.dumps({"events": runtime_events}), encoding="utf-8"
            )
            frames = MODULE.derive_expected_event_frames(scene, runtime)
        self.assertEqual(240, frames[MODULE.EVENT_IDS[0]])
        self.assertEqual(120, frames[MODULE.EVENT_IDS[1]])

    def test_wrapper_binds_exact_ac4901_contract(self) -> None:
        frames = {event_id: 120 for event_id in MODULE.EVENT_IDS}
        with mock.patch.object(
            MODULE, "derive_expected_event_frames", return_value=frames
        ), mock.patch.object(MODULE, "_build_core", return_value=fake_authority()) as core:
            result = MODULE.build_ac4901_authority(
                scene_group_path=Path("scene.json"),
                gdp_path=Path("gdp.json"),
                runtime_scene_path=Path("runtime.json"),
                type3_records_dir=Path("records"),
                parent_z2d_authority_path=Path("parent.json"),
            )
        kwargs = core.call_args.kwargs
        self.assertEqual(MODULE.EVENT_IDS, kwargs["expected_event_ids"])
        self.assertEqual(MODULE.EXPECTED_COUNTS, kwargs["expected_counts"])
        self.assertEqual("ac4901", kwargs["expected_group_name"])
        self.assertEqual(112, kwargs["expected_group_index"])
        self.assertEqual(115, result["summary"]["parallel_event_count"])
        self.assertEqual(90, result["summary"]["single_scene_event_count"])

    def test_wrapper_rejects_parallel_count_drift(self) -> None:
        frames = {event_id: 120 for event_id in MODULE.EVENT_IDS}
        with mock.patch.object(
            MODULE, "derive_expected_event_frames", return_value=frames
        ), mock.patch.object(
            MODULE, "_build_core", return_value=fake_authority(parallel_events=114)
        ):
            with self.assertRaisesRegex(
                MODULE.PresentationAuthorityError, "parallel event count differs"
            ):
                MODULE.build_ac4901_authority(
                    scene_group_path=Path("scene.json"),
                    gdp_path=Path("gdp.json"),
                    runtime_scene_path=Path("runtime.json"),
                    type3_records_dir=Path("records"),
                    parent_z2d_authority_path=Path("parent.json"),
                )

    def test_write_outputs_is_immutable(self) -> None:
        authority = fake_authority()
        authority["summary"]["parallel_event_count"] = 115
        authority["assertions"] = {
            "source_media_untouched": True,
            "final_416x232_projection_resolved": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "v195"
            MODULE.write_outputs(authority, output)
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertEqual("passed", verification["status"])
            self.assertIn("parallel_events=115", verification["literal_result"])
            self.assertEqual(4, len(verification["output_byte_counts"]))
            with self.assertRaisesRegex(
                MODULE.PresentationAuthorityError, "immutable output already exists"
            ):
                MODULE.write_outputs(authority, output)


if __name__ == "__main__":
    unittest.main()
