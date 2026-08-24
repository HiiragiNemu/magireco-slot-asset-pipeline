from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import build_ac0917_output_projection_authority as MODULE


class Ac0917OutputProjectionAuthorityTests(unittest.TestCase):
    def test_contract_keeps_three_exact_clock_exclusions(self) -> None:
        self.assertEqual(12, len(MODULE.EVENTS))
        self.assertEqual(3, len(MODULE.PARENT_CLOCK_EXCLUDED))
        self.assertIn(
            (
                "ac0917_007",
                "ac0917_3on_hat_c03_MR",
                "ac0917_3on_hat_lp_c03_MR",
            ),
            MODULE.PARENT_CLOCK_EXCLUDED,
        )
        self.assertEqual(
            220, MODULE.EXPECTED_COUNTS["parent_clock_clipped_frames"]
        )

    def test_resolve_delegates_every_fail_closed_boundary(self) -> None:
        with mock.patch.object(MODULE.generic, "resolve", return_value={"ok": True}) as call:
            result = MODULE.resolve_ac0917({}, {}, {}, {}, {})
        self.assertEqual({"ok": True}, result)
        kwargs = call.call_args.kwargs
        self.assertEqual(MODULE.EVENTS, kwargs["expected_events"])
        self.assertEqual(
            MODULE.PARENT_CLOCK_EXCLUDED,
            kwargs["expected_parent_clock_excluded_occurrences"],
        )
        self.assertEqual(21, kwargs["expected_cri_source_identity_count"])
        self.assertEqual(0, kwargs["expected_unique_unreachable_layer_count"])

    def test_write_outputs_is_immutable_and_hash_binds_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = []
            for index in range(2):
                path = root / f"input-{index}.json"
                path.write_text(f"{{\"index\":{index}}}\n", encoding="utf-8")
                inputs.append(path)
            source = root / "source.usm"
            source.write_bytes(b"source")
            result = {
                "counts": dict(MODULE.EXPECTED_COUNTS),
                "events": [{"event": "ac0917_001"}],
                "occurrences": [{"event": "ac0917_001"}],
                "runtime_authored_component_scale_sources": [],
                "parent_clock_excluded_occurrences": [
                    {
                        "event": "ac0917_007",
                        "scene": "scene",
                        "cut": "cut",
                        "parent_z2d": "ac0917_3on_hat_c03_MR",
                        "source_name": "ac0917_3on_hat_lp_c03_MR",
                        "source": {"sha256": "A" * 64, "path": str(source)},
                        "authored_event_start_frame": 300,
                        "authored_event_end_frame_inclusive": 329,
                        "active_parent_start_frame": 0,
                        "active_parent_end_frame_inclusive": 279,
                        "schedule_disposition": (
                            "EXCLUDED_BY_EXACT_PARENT_EVENT_CLOCK_BEFORE_FIRST_FRAME"
                        ),
                    }
                ],
            }
            output = root / "authority"
            with mock.patch.object(
                MODULE.generic,
                "_flatten_csv_rows",
                return_value=[{"event": "ac0917_001", "source_name": "source"}],
            ):
                MODULE.write_outputs(
                    result=result,
                    renderer={"renderer_state_1": {}, "renderer_state_3": {}},
                    input_paths=inputs,
                    output_dir=output,
                )
            authority = json.loads(
                (output / "AC0917_OUTPUT_PROJECTION_AUTHORITY.json").read_text(
                    encoding="utf-8"
                )
            )
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            with (output / "PARENT_CLOCK_EXCLUDED_MOVIELAYERS.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                excluded = list(csv.DictReader(handle))
            self.assertEqual(MODULE.SCHEMA, authority["schema"])
            self.assertEqual(1, len(excluded))
            self.assertEqual(
                "ac0917_3on_hat_lp_c03_MR", excluded[0]["source_name"]
            )
            self.assertIn(
                "PARENT_CLOCK_EXCLUDED_MOVIELAYERS.csv",
                verification["outputs"],
            )
            with self.assertRaises(FileExistsError):
                MODULE.write_outputs(
                    result=result,
                    renderer={},
                    input_paths=inputs,
                    output_dir=output,
                )


if __name__ == "__main__":
    unittest.main()
