from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parent
    / "tools"
    / "frida_runtime_probe"
    / "extract_crivideo_filename_table_authority.py"
)
SPEC = importlib.util.spec_from_file_location("extract_crivideo_filename_table_authority", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CriVideoFilenameAuthorityTests(unittest.TestCase):
    def test_classifies_exact_presence_without_alias_guessing(self) -> None:
        names = ["ac8040_premia_EF", "ac8040_premia_EF_LP", "ac8040_premia_EF_zen"]
        rows = MODULE.classify_references(
            names,
            [
                "ac8040_premia_EF_add.dgm",
                "ac8040_premia_EF_add_LP.dgm",
                "ac8040_premia_EF.dgm",
                "ac8040_premia_EF_LP.dgm",
            ],
        )
        self.assertEqual([False, False, True, True], [row["compiled_table_present"] for row in rows])
        self.assertEqual([None, None, 0, 1], [row["compiled_table_index"] for row in rows])

    def test_zen_is_not_promoted_when_not_authored(self) -> None:
        rows = MODULE.classify_references(
            ["ac8040_premia_EF_zen"], ["ac8040_premia_EF_add.dgm"]
        )
        self.assertFalse(rows[0]["compiled_table_present"])

    def test_rejects_non_dgm_reference(self) -> None:
        with self.assertRaisesRegex(MODULE.AuthorityError, "not a .dgm"):
            MODULE.classify_references(["name"], ["name.usm"])

    def test_extracts_bracketed_and_nul_terminated_z2d_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.z2d"
            path.write_bytes(b"[first.dgm]\0\x0asecond.dgm\0[first.dgm]")
            self.assertEqual(["first.dgm", "second.dgm"], MODULE.extract_z2d_dgm_names(path))


if __name__ == "__main__":
    unittest.main()
