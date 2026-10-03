from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parent / "tools" / "frida_runtime_probe" / "event_scene_host.py"


class EventSceneHostSafeAttachTests(unittest.TestCase):
    def test_help_exposes_direct_pid_and_no_unload_policy(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--pid PID", result.stdout)
        self.assertIn("--no-unload", result.stdout)

    def test_missing_pid_fails_without_enumeration(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "status"], text=True,
            capture_output=True, check=False, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--pid is required", result.stderr)
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        calls = [node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertNotIn("enumerate_processes", calls)

    def test_nonpositive_pid_fails_before_any_attachment(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "status", "--pid", "0"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--pid must be a positive numeric PID", result.stderr)

    def test_nonnumeric_official_code_fails_before_any_attachment(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "request-official-code",
                "--pid",
                "123",
                "--code",
                "ac0908_016",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--code must be a numeric GBoss uint64 code", result.stderr)


if __name__ == "__main__":
    unittest.main()
