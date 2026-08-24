from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import (
    build_ac4902_gfdirection_presentation_authority as MODULE,
)


def fake_authority(*, parallel_events: int = 33) -> dict:
    event_presentations = {}
    events = []
    for index, event_id in enumerate(MODULE.EVENT_IDS):
        scene_count = 2 if index < parallel_events else 1
        event_presentations[event_id] = {
            "frames": MODULE.EXPECTED_EVENT_FRAMES[event_id],
            "parallel_scenes": [f"scene_{index}_{n}" for n in range(scene_count)],
        }
        events.append(
            {
                "event_id": event_id,
                "presentation_frame_count": MODULE.EXPECTED_EVENT_FRAMES[event_id],
                "scenes": [
                    {
                        "parallel_scene_order": 0,
                        "name": f"scene_{index}_0",
                        "type2_presentation_frame_count": MODULE.EXPECTED_EVENT_FRAMES[event_id],
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


class Ac4902PresentationAuthorityTests(unittest.TestCase):
    def test_exact_contract_contains_all_64_events(self) -> None:
        self.assertEqual(64, len(MODULE.EVENT_IDS))
        self.assertEqual(set(MODULE.EVENT_IDS), set(MODULE.EXPECTED_EVENT_FRAMES))
        self.assertEqual("ac4902_001", MODULE.EVENT_IDS[0])
        self.assertEqual("ac4902_074", MODULE.EVENT_IDS[-1])
        self.assertEqual(113, MODULE.EXPECTED_GROUP_INDEX)

    def test_wrapper_binds_exact_ac4902_contract(self) -> None:
        with mock.patch.object(MODULE, "_build_core", return_value=fake_authority()) as core:
            result = MODULE.build_ac4902_authority(
                scene_group_path=Path("scene.json"),
                gdp_path=Path("gdp.json"),
                runtime_scene_path=Path("runtime.json"),
                type3_records_dir=Path("records"),
                parent_z2d_authority_path=Path("parent.json"),
            )
        kwargs = core.call_args.kwargs
        self.assertEqual(MODULE.EVENT_IDS, kwargs["expected_event_ids"])
        self.assertEqual(MODULE.EXPECTED_COUNTS, kwargs["expected_counts"])
        self.assertEqual("ac4902", kwargs["expected_group_name"])
        self.assertEqual(113, kwargs["expected_group_index"])
        self.assertEqual(
            "magireco-ac4902-gfdirection-presentation-authority-v1",
            result["schema"],
        )
        self.assertEqual(33, result["summary"]["parallel_event_count"])
        self.assertEqual(31, result["summary"]["single_scene_event_count"])
        self.assertFalse(result["assertions"]["final_416x232_projection_resolved"])

    def test_wrapper_rejects_parallel_count_drift(self) -> None:
        with mock.patch.object(
            MODULE, "_build_core", return_value=fake_authority(parallel_events=32)
        ):
            with self.assertRaisesRegex(
                MODULE.PresentationAuthorityError, "parallel event count differs"
            ):
                MODULE.build_ac4902_authority(
                    scene_group_path=Path("scene.json"),
                    gdp_path=Path("gdp.json"),
                    runtime_scene_path=Path("runtime.json"),
                    type3_records_dir=Path("records"),
                    parent_z2d_authority_path=Path("parent.json"),
                )

    def test_write_outputs_is_immutable_and_hash_binds_all_roles(self) -> None:
        authority = fake_authority()
        authority["summary"]["parallel_event_count"] = 33
        authority["assertions"] = {
            "final_416x232_projection_resolved": False,
            "media_modified": False,
        }
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "v187"
            MODULE.write_outputs(authority, output)
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertEqual("passed", verification["status"])
            self.assertEqual(
                {
                    "AC4902_GFDIRECTION_PRESENTATION_AUTHORITY.json",
                    "PRESENTATION_Z2D_NODES.csv",
                    "README.md",
                    "ROLLBACK.ps1",
                },
                set(verification["outputs"]),
            )
            self.assertIn("parallel_events=33", verification["literal_result"])
            with self.assertRaisesRegex(
                MODULE.PresentationAuthorityError, "immutable output already exists"
            ):
                MODULE.write_outputs(authority, output)


if __name__ == "__main__":
    unittest.main()
