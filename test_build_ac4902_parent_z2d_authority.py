import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.frida_runtime_probe.build_ac4902_parent_z2d_authority import (
    AuthorityError,
    collect_event_z2d_bindings,
    normalize_z2d_name,
    partition_archive_names,
    rebind_extracted_paths,
    write_rollback,
)


def runtime_node(name: str) -> dict:
    return {
        "type": 20,
        "name": name,
        "motions": [{"keys": [{"floats": [0.0], "flags": 0}]}],
        "children": [],
    }


class Ac4902ParentZ2dAuthorityTests(unittest.TestCase):
    def test_accepts_exact_family_dimensions(self) -> None:
        events = {}
        unique_names = [f"z2d_{index:03d}" for index in range(55)]
        for index in range(64):
            names = [unique_names[index % len(unique_names)]]
            if index == 0:
                names.extend([unique_names[0]] * 100)
            events[f"ac4902_{index + 1:03d}"] = {
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
        self.assertEqual(len(bindings), 64)
        self.assertEqual(sum(row["z2d_occurrence_count"] for row in bindings), 164)
        self.assertEqual(len(names), 55)

    def test_normalize_z2d_name(self) -> None:
        self.assertEqual(normalize_z2d_name("abc.z2d"), "abc")
        self.assertEqual(normalize_z2d_name("abc.Z2D"), "abc")
        self.assertEqual(normalize_z2d_name("abc"), "abc")

    def test_rejects_non_ac4902_event_set(self) -> None:
        runtime = {"events": {f"ac4902_{index:03d}": {} for index in range(1, 64)}}
        runtime["events"]["ac9999_064"] = {}
        with self.assertRaisesRegex(AuthorityError, "foreign runtime event"):
            collect_event_z2d_bindings(runtime)

    def test_rejects_wrong_event_count(self) -> None:
        with self.assertRaisesRegex(AuthorityError, "event count differs"):
            collect_event_z2d_bindings({"events": {}})

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
