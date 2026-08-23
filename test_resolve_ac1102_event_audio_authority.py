from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.frida_runtime_probe.resolve_ac1102_event_audio_authority import (
    Ac1102AudioAuthorityError,
    EXPECTED_CAPTION_AUDIO,
    extract_caption_parent_starts,
    write_outputs,
)


def runtime_fixture() -> dict:
    events = {}
    for event in ("ac1102_007", "ac1102_013", "ac1102_014", "ac1102_015"):
        nodes = []
        for name, (_, _, start) in EXPECTED_CAPTION_AUDIO.get(event, {}).items():
            nodes.append(
                {
                    "name": f"{name}.z2d",
                    "motions": [
                        {
                            "is_z2d_motion": True,
                            "keys": [
                                {"floats": [start, start + 29, start, start + 29, start, start + 29]}
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


class Ac1102EventAudioAuthorityTests(unittest.TestCase):
    def test_extracts_all_event_global_caption_starts(self) -> None:
        result = extract_caption_parent_starts(runtime_fixture())
        self.assertEqual(result["ac1102_007"]["cap1102_rakuno_fer_019"], 152)
        self.assertEqual(result["ac1102_014"]["cap1102_rakuno_fer_022"], 10)
        self.assertEqual(result["ac1102_015"]["cap1102_rakuno_fer_026"], 260)
        self.assertEqual(result["ac1102_013"], {})

    def test_parent_start_triplet_mismatch_fails_closed(self) -> None:
        value = runtime_fixture()
        key = value["events"]["ac1102_014"]["value"]["scenes"][0]["cuts"][0][
            "nodes"
        ][0]["children"][0]["motions"][0]["keys"][0]
        key["floats"][4] += 1
        with self.assertRaisesRegex(Ac1102AudioAuthorityError, "parent starts differ"):
            extract_caption_parent_starts(value)

    def test_unexpected_caption_in_audio_free_event_fails_closed(self) -> None:
        value = runtime_fixture()
        value["events"]["ac1102_013"]["value"]["scenes"][0]["cuts"][0]["nodes"].append(
            {"name": "cap1102_unexpected.z2d", "motions": [], "children": []}
        )
        with self.assertRaisesRegex(Ac1102AudioAuthorityError, "unexpectedly contains"):
            extract_caption_parent_starts(value)

    def test_mixed_event_and_z2d_rows_export_with_union_schema(self) -> None:
        report = {
            "audio_rows": [
                {"event": "ac1102_013", "request_id": 1067},
                {"event": "ac1102_014", "request_id": 4041, "z2d_name": "cap022"},
            ],
            "assertions": {},
            "decision": {},
        }
        with TemporaryDirectory() as directory:
            output = Path(directory)
            write_outputs(report, output)
            text = (output / "AC1102_EVENT_AUDIO_ROWS.csv").read_text(encoding="utf-8-sig")
            self.assertIn("z2d_name", text.splitlines()[0])
            self.assertIn("cap022", text)


if __name__ == "__main__":
    unittest.main()
