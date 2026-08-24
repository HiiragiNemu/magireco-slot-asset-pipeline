import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.frida_runtime_probe.build_ac0917_parent_z2d_authority import (
    AuthorityError,
    collect_event_z2d_bindings,
    normalize_z2d_name,
    partition_archive_names,
    rebind_extracted_paths,
    write_rollback,
)


class Ac0917ParentZ2dAuthorityTests(unittest.TestCase):
    def test_normalize_z2d_name(self) -> None:
        self.assertEqual(normalize_z2d_name("abc.z2d"), "abc")
        self.assertEqual(normalize_z2d_name("abc.Z2D"), "abc")
        self.assertEqual(normalize_z2d_name("abc"), "abc")

    def test_rejects_non_ac0917_event_set(self) -> None:
        runtime = {"events": {f"ac0917_{index:03d}": {} for index in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}}
        runtime["events"]["ac9999_014"] = {}
        with self.assertRaisesRegex(AuthorityError, "foreign runtime event"):
            collect_event_z2d_bindings(runtime)

    def test_rejects_wrong_event_count(self) -> None:
        with self.assertRaisesRegex(AuthorityError, "event count differs"):
            collect_event_z2d_bindings({"events": {}})

    def test_rejects_wrong_same_size_event_set(self) -> None:
        events = {
            f"ac0917_{index:03d}": {}
            for index in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13)
        }
        with self.assertRaisesRegex(AuthorityError, "event set differs"):
            collect_event_z2d_bindings({"events": events})

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
        self.assertEqual(
            Path(extracted["chunks"][0]["output_path"]).name,
            "sample.z2d",
        )
        self.assertEqual(
            Path(extracted["chunks"][0]["output_path"]).parent.name,
            "final",
        )


if __name__ == "__main__":
    unittest.main()
