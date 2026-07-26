import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac0908_approved_production as ac0908


class Ac0908ApprovedProductionTests(unittest.TestCase):
    def test_plan_declares_exact_21_mp4_matrix(self) -> None:
        plan_path = (
            Path(__file__).parent
            / "tools"
            / "frida_runtime_probe"
            / "series_proposals"
            / "ac0908_approved_full_production_v1.json"
        )
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["schema"], ac0908.PLAN_SCHEMA)
        self.assertEqual(plan["expected_mp4_count"], 21)
        self.assertEqual(plan["editions"], list(ac0908.EDITIONS))
        self.assertEqual(len(plan["routes"]), 6)
        self.assertEqual(
            sum(len(route["outputs"]) for route in plan["routes"]),
            18,
        )
        self.assertEqual(
            sum(
                int(row["expected_cues"])
                for row in plan["showcase_ja_subtitle_occurrences"]
            ),
            15,
        )

    def test_extract_event_local_cues_uses_route_presentation_window(self) -> None:
        cues = [
            {"start_ms": 900, "end_ms": 950, "text": "before"},
            {"start_ms": 1100, "end_ms": 1400, "text": "first"},
            {"start_ms": 2100, "end_ms": 2500, "text": "second"},
            {"start_ms": 3100, "end_ms": 3200, "text": "after"},
        ]
        local = ac0908.extract_event_local_cues(
            cues,
            timeline_row={
                "event": "ac0908_009",
                "start_sample": 48000,
                "end_sample": 144000,
            },
            event="ac0908_009",
        )
        self.assertEqual(
            local,
            [
                {"start_ms": 100, "end_ms": 400, "text": "first"},
                {"start_ms": 1100, "end_ms": 1500, "text": "second"},
            ],
        )

    def test_extract_event_local_cues_fails_closed_on_crossing_end(self) -> None:
        with self.assertRaisesRegex(ValueError, "crosses its event interval"):
            ac0908.extract_event_local_cues(
                [{"start_ms": 2500, "end_ms": 3100, "text": "cross"}],
                timeline_row={
                    "event": "ac0908_008",
                    "start_sample": 48000,
                    "end_sample": 144000,
                },
                event="ac0908_008",
            )

    def test_hardlink_exact_preserves_identity_and_relative_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary)
            source = staging / "source.bin"
            destination = staging / "video" / "promoted.bin"
            source.write_bytes(b"ac0908-approved-hardlink")
            digest = ac0908.file_sha256(source)
            audit = ac0908.hardlink_exact(
                source,
                destination,
                expected_sha256=digest,
                expected_bytes=source.stat().st_size,
                staging=staging,
            )
            self.assertTrue(os.path.samefile(source, destination))
            self.assertEqual(audit["path"], "video/promoted.bin")
            self.assertEqual(audit["sha256"], digest)
            self.assertTrue(audit["same_file_identity_verified"])

    def test_output_path_contract_rejects_escape(self) -> None:
        self.assertEqual(ac0908.assert_relative_output("video/ac0908.mp4"), "video/ac0908.mp4")
        with self.assertRaises(ValueError):
            ac0908.assert_relative_output("../outside.mp4")
        with self.assertRaises(ValueError):
            ac0908.assert_relative_output(str(Path.cwd() / "absolute.mp4"))


if __name__ == "__main__":
    unittest.main()
