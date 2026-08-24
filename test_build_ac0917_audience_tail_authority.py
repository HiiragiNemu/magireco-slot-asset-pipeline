import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_ac0917_audience_tail_authority import (
    Ac0917AudienceTailError,
    EVENTS,
    EXPECTED_ALPHA_LOGS,
    EXPECTED_ARCHIVE_FRAMES,
    EXPECTED_AUDIENCE_FRAMES,
    EXPECTED_FUNCTIONS,
    build_report,
    write_outputs,
)


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class Ac0917AudienceTailAuthorityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        binary = self.root / "libGameProc.so"
        binary.write_bytes(b"slot-fixture")
        sample = self.root / "SAMPLE_IDENTITY.json"
        dump(
            sample,
            {
                "schema": "magireco-ida-sample-identity-v1",
                "analysis_copy": str(binary),
                "source_size": binary.stat().st_size,
                "copy_verified": True,
            },
        )
        self.ida = self.root / "ida.json"
        dump(
            self.ida,
            {
                "schema": "magireco-ac0917-gfdirection-clear-and-idle-tail-ida-evidence-v1",
                "status": "PROVEN_FOR_HASH_BOUND_BINARY",
                "binary": {
                    "path": str(binary),
                    "size_bytes": binary.stat().st_size,
                    "sample_identity": str(sample),
                },
                "function_chain": [
                    {"address": address, "name": name}
                    for address, name in EXPECTED_FUNCTIONS.items()
                ],
                "binary_constants": {
                    "xmmword_143F300_float_rgba": [0.0, 0.0, 0.0, 1.0]
                },
                "mechanism_decision": {
                    "previous_frame_carry": False,
                    "implicit_last_movie_frame_hold": False,
                    "inactive_cut_player_buffer": "transparent_black_after_per_frame_clear",
                    "final_scene_output_when_no_cut_draws": "opaque_black_after_final_target_clear",
                },
            },
        )
        self.route = self.root / "route.json"
        dump(
            self.route,
            {
                "schema": "magireco-ac0917-dirinfo-route-and-complete-presentation-dedup-authority-v2",
                "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
                "summary": {
                    "dirinfo_routes": 22,
                    "dirinfo_event_occurrences": 75,
                    "canonical_presentations": 12,
                    "identical_complete_presentation_aliases": 0,
                },
                "editorial_timeline": [{"event": event} for event in EVENTS],
            },
        )
        self.visual = self.root / "visual.json"
        dump(
            self.visual,
            {
                "schema": "magireco-ac0917-output-projection-authority-v1",
                "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
                "events": [
                    {"event": event, "non_movie_text_z2d_nodes": []}
                    for event in EVENTS
                ],
            },
        )
        movie_ends = {
            "ac0917_014": 84,
            "ac0917_006": 84,
            "ac0917_010": 96,
        }
        self.loop = self.root / "loop.json"
        dump(
            self.loop,
            {
                "schema": "magireco-ac0917-parent-clock-z2d-loop-authority-v1",
                "status": "PASS_READY_FOR_LOOP_AWARE_ROUTE_DEDUP_AND_LONGFORM_RENDER",
                "events": [
                    {
                        "event": event,
                        "parent_z2d_schedules_in_gfdirection_order": [
                            {
                                "render_segments": [
                                    {
                                        "event_end_frame_inclusive": movie_ends.get(
                                            event, EXPECTED_AUDIENCE_FRAMES[event]
                                        )
                                        - 1
                                    }
                                ]
                            }
                        ],
                    }
                    for event in EVENTS
                ],
            },
        )
        retained = [
            {
                "event": "ac0917_006",
                "end_ms": EXPECTED_AUDIENCE_FRAMES["ac0917_006"] * 1000 / 30,
            }
        ]
        self.audio = self.root / "audio.json"
        dump(
            self.audio,
            {
                "schema": "magireco-ac0917-native416-event-audio-runtime-and-sound-bus-authority-v1",
                "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
                "event_presentations": [
                    {
                        "event": event,
                        "rendered_presentation_frames": EXPECTED_ARCHIVE_FRAMES[event],
                    }
                    for event in EVENTS
                ],
                "retained_audio_rows": retained,
                "subtitle_page_cues": [],
            },
        )
        self.alpha = self.root / "alpha"
        self.alpha.mkdir()
        for name, frames in EXPECTED_ALPHA_LOGS.items():
            lines = []
            for frame in range(frames):
                lines += [
                    f"frame:{frame}",
                    "lavfi.signalstats.YMIN=0",
                    "lavfi.signalstats.YAVG=12.5",
                    "lavfi.signalstats.YMAX=255",
                ]
            (self.alpha / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self):
        return build_report(
            route_path=self.route,
            visual_path=self.visual,
            loop_path=self.loop,
            audio_path=self.audio,
            ida_evidence_path=self.ida,
            alpha_log_root=self.alpha,
        )

    def test_exact_audience_extents_and_trim(self) -> None:
        report = self.build()
        rows = {row["event"]: row for row in report["event_rows"]}
        self.assertEqual(report["summary"]["audience_content_frames"], 2734)
        self.assertEqual(report["summary"]["terminal_idle_frames_omitted"], 402)
        self.assertEqual(rows["ac0917_014"]["audience_content_frames"], 84)
        self.assertEqual(rows["ac0917_006"]["audience_content_frames"], 118)
        self.assertEqual(rows["ac0917_010"]["audience_content_frames"], 96)
        self.assertTrue(report["assertions"]["no_predecessor_underlay_invented"])

    def test_audio_extent_is_not_cut_to_movie_end(self) -> None:
        row = next(
            row for row in self.build()["event_rows"] if row["event"] == "ac0917_006"
        )
        self.assertEqual(row["last_movie_frame_exclusive"], 84)
        self.assertEqual(row["last_audio_frame_exclusive"], 118)
        self.assertEqual(row["audience_content_frames"], 118)

    def test_previous_frame_carry_claim_fails_closed(self) -> None:
        evidence = json.loads(self.ida.read_text(encoding="utf-8"))
        evidence["mechanism_decision"]["previous_frame_carry"] = True
        dump(self.ida, evidence)
        with self.assertRaisesRegex(Ac0917AudienceTailError, "mechanism differs"):
            self.build()

    def test_immutable_output_and_reopen_record(self) -> None:
        output = self.root / "authority"
        write_outputs(self.build(), output)
        verification = json.loads(
            (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
        )
        self.assertIn("audience_frames=2734", verification["literal_result"])
        with self.assertRaisesRegex(Ac0917AudienceTailError, "immutable output"):
            write_outputs(self.build(), output)


if __name__ == "__main__":
    unittest.main()
