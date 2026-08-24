from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac0917_route_dedup_authority as MODULE


SELECTORS = {
    0: [1, 4],
    1: [1, 4],
    2: [1, 4, 6],
    3: [1, 4, 5, 7],
    4: [1, 4, 5, 7],
    5: [1, 4, 6],
    6: [1, 4, 5, 7],
    7: [1, 4, 5, 7],
    8: [1, 4],
    9: [1, 4],
    10: [1, 4],
    11: [0, 2, 4],
    12: [0, 2, 4],
    13: [0, 2, 4, 6],
    14: [0, 2, 4, 5, 7],
    15: [0, 2, 4, 5, 7],
    16: [0, 2, 4, 6],
    17: [0, 2, 4, 5, 7],
    18: [0, 2, 4, 5, 7],
    19: [0, 2, 4],
    20: [0, 2, 4],
    21: [0, 2, 4],
}
RENDERED_FRAMES = {
    "ac0917_001": 252,
    "ac0917_002": 269,
    "ac0917_003": 300,
    "ac0917_004": 300,
    "ac0917_005": 240,
    "ac0917_006": 300,
    "ac0917_007": 287,
    "ac0917_008": 280,
    "ac0917_009": 280,
    "ac0917_010": 300,
    "ac0917_011": 228,
    "ac0917_014": 100,
}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Ac0917RouteDedupAuthorityTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        dirinfo_rows = []
        for route_index, sequence in MODULE.ROUTES.items():
            for selector, event in zip(SELECTORS[route_index], sequence, strict=True):
                dirinfo_rows.append(
                    {
                        "kind": 42,
                        "base_name": "ac0917",
                        "row_index": route_index,
                        "selector_raw": selector,
                        "scene_name": event,
                        "route_status": "ok",
                    }
                )
        dirinfo = root / "dirinfo.csv"
        write_csv(dirinfo, dirinfo_rows)

        visual = {
            "schema": "magireco-ac0917-output-projection-authority-v1",
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "summary": {
                "events": 12,
                "unique_loadable_cri_sources": 20,
                "exact_cri_source_identity_count": 21,
            },
            "events": [],
        }
        for index, event in enumerate(MODULE.EVENTS):
            visual["events"].append(
                {
                    "event": event,
                    "presentation_frame_count": 100 + index,
                    "output_canvas": [416, 232],
                    "projection": {"mode": "exact"},
                    "layers_in_render_pass_order_under_to_top": [
                        {
                            "scene": event,
                            "cut": event,
                            "parent_z2d": event,
                            "parent_composition_order": 0,
                            "owning_gdp_layer_index": 1,
                            "source_name": f"{event}_source",
                            "event_start_frame": 0,
                            "event_end_frame_inclusive": 99 + index,
                        }
                    ],
                    "non_movie_text_z2d_nodes": [],
                    "runtime_symbolic_nodes": [],
                }
            )
        visual_path = root / "visual.json"
        visual_path.write_text(json.dumps(visual), encoding="utf-8")

        source_catalog = {
            f"{event}_source": {
                "sha256": f"{index + 1:064x}",
                "frame_count": 100 + index,
            }
            for index, event in enumerate(MODULE.EVENTS)
        }
        source_catalog.update(
            {
                f"unused_{index}": {
                    "sha256": f"{100 + index:064x}",
                    "frame_count": 1,
                }
                for index in range(8)
            }
        )
        loop = {
            "schema": "magireco-ac0917-parent-clock-z2d-loop-authority-v1",
            "status": "PASS_READY_FOR_LOOP_AWARE_ROUTE_DEDUP_AND_LONGFORM_RENDER",
            "summary": dict(MODULE.LOOP_EXPECTED),
            "source_catalog": source_catalog,
            "parent_clock_excluded_occurrences": [{}, {}, {}],
            "events": [],
        }
        for index, event in enumerate(MODULE.EVENTS):
            end = 99 + index
            loop["events"].append(
                {
                    "event": event,
                    "presentation_frame_count": 100 + index,
                    "parent_z2d_schedules_in_gfdirection_order": [
                        {
                            "owning_gdp_layer_index": 1,
                            "active_event_start_frame": 0,
                            "active_event_end_frame_inclusive": end,
                            "motion_key_raw_floats": [0, end, 0, end, 0, end, -1],
                            "motion_key_raw_flags": [0, 0, 1],
                            "mapping_policy": "play_once",
                            "scene_start_frame": 0,
                            "scene_end_frame_inclusive": end,
                            "scene_loop_frame": 0,
                            "render_segments": [
                                {
                                    "projection_key": (
                                        f"{event}|{event}|{event}|{event}_source"
                                    ),
                                    "source_name": f"{event}_source",
                                    "event_start_frame": 0,
                                    "event_end_frame_inclusive": end,
                                    "source_start_frame": 0,
                                    "source_end_frame_inclusive": end,
                                    "source_progression": "increment_1",
                                }
                            ],
                        }
                    ],
                }
            )
        loop_path = root / "loop.json"
        loop_path.write_text(json.dumps(loop), encoding="utf-8")

        retained = []
        for index in range(25):
            event = MODULE.EVENTS[index % len(MODULE.EVENTS)]
            retained.append(
                {
                    "event": event,
                    "source_kind": "fixture",
                    "z2d_name": event,
                    "request_id": 1000 + index,
                    "sound_id": 2000 + index,
                    "start_ms": index,
                    "duration_ms": 1,
                    "end_ms": index + 1,
                    "ogg_name": f"{index}.ogg",
                    "official_source": {"sha256": f"{index:064x}"},
                    "volume_kind_value": 1,
                    "volume_bus": "SE",
                    "strict_no_bgm_disposition": "RETAIN_VERIFIED_SE",
                    "timing_evidence": "fixture",
                }
            )
        subtitles = []
        for index in range(18):
            event = MODULE.EVENTS[index % len(MODULE.EVENTS)]
            subtitles.append(
                {
                    "event": event,
                    "voice_request_id": 3000 + index,
                    "page_index": 1,
                    "page_count": 1,
                    "z2d_name": event,
                    "start_frame": 0,
                    "start_ms": 0,
                    "end_ms": 1,
                    "ja": f"JA-{index}",
                    "zh": f"ZH-{index}",
                }
            )
        audio = {
            "schema": "magireco-ac0917-native416-event-audio-runtime-and-sound-bus-authority-v1",
            "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
            "summary": {
                "retained_audio_occurrences": 25,
                "excluded_bgm_occurrences": 3,
                "subtitle_page_cue_occurrences": 18,
                "rendered_presentation_frames_before_dedup": 3136,
            },
            "retained_audio_rows": retained,
            "excluded_audio_rows": [
                {"event": "ac0917_007"},
                {"event": "ac0917_008"},
                {"event": "ac0917_009"},
            ],
            "subtitle_page_cues": subtitles,
            "event_presentations": [
                {
                    "event": event,
                    "rendered_presentation_frames": RENDERED_FRAMES[event],
                    "final_frame_hold_frames": 0,
                }
                for event in MODULE.EVENTS
            ],
        }
        audio_path = root / "audio.json"
        audio_path.write_text(json.dumps(audio), encoding="utf-8")
        return dirinfo, visual_path, loop_path, audio_path

    def test_validates_all_22_routes_and_75_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dirinfo, _, _, _ = self._fixture(Path(temp))
            routes = MODULE.validate_dirinfo(MODULE.read_csv(dirinfo))
        self.assertEqual(22, len(routes))
        self.assertEqual(75, sum(row["event_count"] for row in routes))

    def test_builds_no_alias_editorial_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._fixture(Path(temp))
            report = MODULE.build_report(
                dirinfo_path=paths[0],
                visual_path=paths[1],
                loop_path=paths[2],
                audio_path=paths[3],
            )
        self.assertEqual(12, report["summary"]["canonical_presentations"])
        self.assertEqual(0, report["summary"]["identical_complete_presentation_aliases"])
        self.assertEqual(3136, report["summary"]["duplicate_free_longform_frames"])
        self.assertEqual(
            list(MODULE.EDITORIAL_ORDER),
            [row["event"] for row in report["editorial_timeline"]],
        )

    def test_rejects_any_complete_presentation_alias(self) -> None:
        payloads = {event: {"identity": event} for event in MODULE.EVENTS}
        payloads["ac0917_002"] = payloads["ac0917_001"]
        with self.assertRaisesRegex(
            MODULE.Ac0917RouteDedupError, "equality groups differ"
        ):
            MODULE.group_complete_signatures(payloads)

    def test_audio_equality_uses_content_not_request_labels(self) -> None:
        audio = {
            "retained_audio_rows": [],
            "subtitle_page_cues": [],
            "event_presentations": [],
        }
        for event, request, name in (
            ("ac0917_001", 1, "first.ogg"),
            ("ac0917_002", 999, "alias-name.ogg"),
        ):
            audio["retained_audio_rows"].append(
                {
                    "event": event,
                    "request_id": request,
                    "sound_id": request,
                    "code_name": name,
                    "ogg_name": name,
                    "start_frame": 0,
                    "start_ms": 0,
                    "duration_ms": 1000,
                    "end_ms": 1000,
                    "official_source": {"sha256": "A" * 64},
                    "volume_kind_value": 1,
                    "volume_bus": "VOICE",
                    "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE",
                }
            )
            audio["event_presentations"].append(
                {
                    "event": event,
                    "rendered_presentation_frames": 30,
                    "final_frame_hold_frames": 0,
                }
            )
        self.assertEqual(
            MODULE._audio_signature(audio, "ac0917_001"),
            MODULE._audio_signature(audio, "ac0917_002"),
        )

    def test_write_outputs_is_immutable_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self._fixture(root)
            report = MODULE.build_report(
                dirinfo_path=paths[0],
                visual_path=paths[1],
                loop_path=paths[2],
                audio_path=paths[3],
            )
            output = root / "authority"
            MODULE.write_outputs(report, output)
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertIn("routes=22", verification["literal_result"])
            self.assertIn("sha256", verification["outputs"]["AC0917_ROUTE_DEDUP_AUTHORITY.json"])
            self.assertTrue(
                Path(
                    verification["outputs"]["AC0917_ROUTE_DEDUP_AUTHORITY.json"][
                        "path"
                    ]
                ).is_file()
            )
            with self.assertRaises(MODULE.Ac0917RouteDedupError):
                MODULE.write_outputs(report, output)


if __name__ == "__main__":
    unittest.main()
