import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.frida_runtime_probe.build_ac4901_parent_z2d_authority import (
    AuthorityError,
    EXPECTED_EVENT_IDS,
    collect_event_z2d_bindings,
    normalize_z2d_name,
    partition_archive_names,
    rebind_extracted_paths,
    validate_runtime_capture,
    write_rollback,
)


def runtime_node(name: str) -> dict:
    return {
        "type": 20,
        "name": name,
        "motions": [{"keys": [{"floats": [0.0], "flags": 0}]}],
        "children": [],
    }


class Ac4901ParentZ2dAuthorityTests(unittest.TestCase):
    def test_accepts_exact_safe_runtime_capture_contract(self) -> None:
        validate_runtime_capture(
            {
                "status": "PASSED",
                "transport": "known_pid_single_session_127.0.0.1_27043",
                "target_pid": 123,
                "protected_processes_unchanged": True,
                "crash_buffer_unchanged": True,
            }
        )

    def test_rejects_runtime_capture_with_changed_crash_buffer(self) -> None:
        with self.assertRaisesRegex(AuthorityError, "changed the crash buffer"):
            validate_runtime_capture(
                {
                    "status": "PASSED",
                    "transport": "known_pid_single_session_127.0.0.1_27043",
                    "target_pid": 123,
                    "protected_processes_unchanged": True,
                    "crash_buffer_unchanged": False,
                }
            )

    def test_accepts_exact_family_dimensions(self) -> None:
        events = {}
        unique_names = [f"z2d_{index:03d}" for index in range(108)]
        for index, event_id in enumerate(EXPECTED_EVENT_IDS):
            names = [unique_names[index % len(unique_names)]]
            if index == 0:
                names.extend([unique_names[0]] * 263)
            events[event_id] = {
                "scenes": [
                    {
                        "name": "scene",
                        "cuts": [
                            {
                                "cut_name": "cut",
                                "cut_start_frame": 0,
                                "cut_end_frame": 1,
                                "nodes": [runtime_node(name) for name in names],
                            }
                        ],
                    }
                ]
            }
        bindings, names = collect_event_z2d_bindings({"events": events})
        self.assertEqual(len(bindings), 205)
        self.assertEqual(sum(row["z2d_occurrence_count"] for row in bindings), 468)
        self.assertEqual(len(names), 108)

    def test_rejects_same_size_but_wrong_event_set(self) -> None:
        events = {event_id: {} for event_id in EXPECTED_EVENT_IDS}
        events.pop(EXPECTED_EVENT_IDS[-1])
        events["ac4901_999"] = {}
        with self.assertRaisesRegex(AuthorityError, "exact event set differs"):
            collect_event_z2d_bindings({"events": events})

    def test_rejects_foreign_event(self) -> None:
        events = {event_id: {} for event_id in EXPECTED_EVENT_IDS}
        events.pop(EXPECTED_EVENT_IDS[-1])
        events["ac9999_256"] = {}
        with self.assertRaisesRegex(AuthorityError, "foreign runtime event"):
            collect_event_z2d_bindings({"events": events})

    def test_rejects_wrong_event_count(self) -> None:
        with self.assertRaisesRegex(AuthorityError, "event count differs"):
            collect_event_z2d_bindings({"events": {}})

    def test_normalize_z2d_name(self) -> None:
        self.assertEqual(normalize_z2d_name("abc.z2d"), "abc")
        self.assertEqual(normalize_z2d_name("abc.Z2D"), "abc")
        self.assertEqual(normalize_z2d_name("abc"), "abc")

    def test_partitions_runtime_only_type20_names(self) -> None:
        extractable, runtime_only = partition_archive_names(
            ["present", "dynamic"], {"present", "unrelated"}
        )
        self.assertEqual(extractable, ["present"])
        self.assertEqual(runtime_only, ["dynamic"])

    def test_rollback_names_final_root_not_staging_root(self) -> None:
        with TemporaryDirectory() as temporary:
            stage = Path(temporary) / "stage"
            stage.mkdir()
            final = Path(temporary) / "final"
            write_rollback(stage, final)
            text = (stage / "ROLLBACK.ps1").read_text(encoding="utf-8")
            self.assertIn(str(final), text)
            self.assertNotIn("$root = '" + str(stage) + "'", text)

    def test_rebinds_extracted_paths_to_final_root(self) -> None:
        extracted = {"chunks": [{"name": "sample", "output_path": "stage"}]}
        rebind_extracted_paths(extracted, Path("final"))
        output = Path(extracted["chunks"][0]["output_path"])
        self.assertEqual(output.name, "sample.z2d")
        self.assertEqual(output.parent.name, "final")


if __name__ == "__main__":
    unittest.main()
