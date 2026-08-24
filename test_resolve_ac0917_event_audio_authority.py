from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import resolve_ac0917_event_audio_authority as MODULE


HOST_INTERVALS = {
    "ac0917_001": {
        "cap0917_enzetu_tou_001": (20, 67),
        "cap0917_enzetu_tou_002": (92, 155),
        "cap0917_enzetu_tou_003": (158, 186),
    },
    "ac0917_002": {
        "cap0917_enzetu_tou_004": (3, 126),
        "cap0917_enzetu_tou_005": (130, 159),
    },
    "ac0917_003": {
        "cap0917_enzetu_tou_006": (3, 84),
        "cap0917_enzetu_tou_007": (88, 117),
    },
    "ac0917_004": {
        "cap0917_enzetu_tou_004": (3, 126),
        "cap0917_enzetu_tou_005": (130, 159),
    },
    "ac0917_005": {},
    "ac0917_006": {
        "cap5102_iro_oshite_001": (0, 29),
        "ac8002_chance_btn_deka": (0, 83),
    },
    "ac0917_007": {
        "cap0917_enzetu_tou_008": (3, 133),
        "cap0917_enzetu_tou_009": (165, 194),
    },
    "ac0917_008": {"cap0917_enzetu_tou_010": (3, 32)},
    "ac0917_009": {"cap0917_enzetu_tou_011": (3, 32)},
    "ac0917_010": {"ac8002_chance_btn_mokyu": (0, 95)},
    "ac0917_011": {
        "cap0917_enzetu_tou_006": (3, 84),
        "cap0917_enzetu_tou_007": (88, 99),
    },
    "ac0917_014": {
        "cap5102_iro_oshite_001": (0, 29),
        "ac8002_chance_btn_lev": (0, 83),
    },
}
COMPONENT_DURATIONS = {
    2950: 4834,
    2951: 2668,
    2952: 3918,
    1005: 2625,
    551: 6194,
    1008: 2742,
    552: 6905,
    1010: 4114,
    553: 6183,
}
CALLBACK_DURATIONS = {
    5368: 1490,
    5369: 5310,
    5370: 8862,
    5371: 7477,
    5372: 9464,
    5373: 4124,
    5374: 3903,
    2439: 669,
    453: 2191,
    8209: 1382,
    450: 694,
    451: 1986,
}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Ac0917EventAudioAuthorityTests(unittest.TestCase):
    def _fixture(self, root: Path) -> dict[str, Path]:
        visual = {
            "schema": "magireco-ac0917-output-projection-authority-v1",
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "family": "ac0917",
            "frame_rate": "30/1",
            "output_canvas": [416, 232],
            "events": [],
        }
        for event in MODULE.EVENTS:
            nodes = [
                {
                    "node": host,
                    "event_global_start_frame": start,
                    "event_global_end_frame_inclusive": end,
                }
                for host, (start, end) in HOST_INTERVALS[event].items()
            ]
            visual["events"].append(
                {
                    "event": event,
                    "presentation_frame_count": MODULE.EXPECTED_PRESENTATION_FRAMES[event],
                    "non_movie_text_z2d_nodes": nodes,
                    "layers_in_render_pass_order_under_to_top": [],
                }
            )
        visual_path = root / "visual.json"
        visual_path.write_text(json.dumps(visual), encoding="utf-8")

        component_rows = []
        for event in MODULE.EVENTS:
            for request_id, sound_id, start_ms in sorted(
                MODULE.EXPECTED_EVENT_COMPONENTS[event]
            ):
                component_rows.append(
                    {
                        "root": "ac0917",
                        "primary_animation": event,
                        "leaf_request_id": request_id,
                        "leaf_sound_code": sound_id,
                        "start_ms": start_ms,
                        "duration_ms": COMPONENT_DURATIONS[sound_id],
                        "leaf_code_name": f"component-{sound_id}",
                        "ogg_name": f"component-{sound_id}.ogg",
                        "smz_matches_leaf_request": "yes",
                        "ogg_duration_match": "yes",
                    }
                )
        component_path = root / "components.csv"
        write_csv(component_path, component_rows)

        callback_by_pair = {}
        for specs in MODULE.EXPECTED_CALLBACKS_BY_EVENT.values():
            for host, request_id, sound_id, _, _ in specs:
                callback_by_pair[(host, request_id)] = {
                    "z2d_name": host,
                    "sound_request_id": request_id,
                    "sound_resource_id": sound_id,
                    "exec_frame": 0,
                    "sound_code_name": f"callback-{sound_id}",
                    "ogg_name": f"callback-{request_id}.ogg",
                    "sound_duration_ms": CALLBACK_DURATIONS[request_id],
                    "sound_request_match_count": "1",
                    "ogg_exists": "yes",
                }
        callback_path = root / "callbacks.csv"
        write_csv(callback_path, list(callback_by_pair.values()))

        durable = root / "ogg"
        durable.mkdir()
        for row in component_rows:
            (durable / str(row["ogg_name"])).write_bytes(
                str(row["ogg_name"]).encode("utf-8")
            )
        for row in callback_by_pair.values():
            (durable / str(row["ogg_name"])).write_bytes(
                str(row["ogg_name"]).encode("utf-8")
            )
        binary = root / "libGameProc.so"
        binary.write_bytes(b"binary")
        translation = (
            Path(__file__).resolve().parent
            / "tools"
            / "frida_runtime_probe"
            / "translations"
            / "ac0917_exhaustive_native416_zh_dialogue_pages_v1.json"
        )
        return {
            "binary": binary,
            "visual": visual_path,
            "components": component_path,
            "callbacks": callback_path,
            "translation": translation,
            "durable": durable,
        }

    def _build(self, paths: dict[str, Path]) -> dict:
        sound_ids = {
            sound_id
            for rows in MODULE.EXPECTED_EVENT_COMPONENTS.values()
            for _, sound_id, _ in rows
        }
        sound_ids.update(
            sound_id
            for specs in MODULE.EXPECTED_CALLBACKS_BY_EVENT.values()
            for _, _, sound_id, _, _ in specs
        )
        buses = {
            sound_id: (
                0
                if sound_id in {551, 552, 553}
                else 2
                if sound_id >= 15000
                else 1
            )
            for sound_id in sound_ids
        }
        with mock.patch.object(
            MODULE, "read_sound_divide_values", return_value=("build-id", buses)
        ):
            return MODULE.build_report(
                binary=paths["binary"],
                visual_authority_path=paths["visual"],
                event_audio_components_path=paths["components"],
                z2d_sound_callbacks_path=paths["callbacks"],
                translation_path=paths["translation"],
                durable_audio_root=paths["durable"],
            )

    def test_builds_exact_buses_page_cues_and_final_holds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = self._build(self._fixture(Path(temp)))
        self.assertEqual(25, report["summary"]["retained_audio_occurrences"])
        self.assertEqual(3, report["summary"]["excluded_bgm_occurrences"])
        self.assertEqual(18, report["summary"]["subtitle_page_cue_occurrences"])
        self.assertEqual(3136, report["summary"]["rendered_presentation_frames_before_dedup"])
        holds = {
            row["event"]: row["final_frame_hold_frames"]
            for row in report["event_presentations"]
            if row["final_frame_hold_frames"]
        }
        self.assertEqual(MODULE.EXPECTED_FINAL_HOLDS, holds)
        request_5369 = [
            row for row in report["subtitle_page_cues"] if row["voice_request_id"] == 5369
        ]
        self.assertEqual([1, 2], [row["page_index"] for row in request_5369])
        self.assertEqual(request_5369[0]["end_ms"], request_5369[1]["start_ms"])

    def test_rejects_component_and_parent_timing_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = self._fixture(Path(temp))
            rows = MODULE.read_csv(paths["components"])
            rows[0]["start_ms"] = "1"
            write_csv(paths["components"], rows)
            with self.assertRaisesRegex(
                MODULE.Ac0917AudioAuthorityError, "component set differs"
            ):
                self._build(paths)

    def test_write_outputs_is_immutable_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = self._build(self._fixture(root))
            output = root / "authority"
            MODULE.write_outputs(report, output)
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertIn("holds=4/229", verification["literal_result"])
            self.assertEqual(
                18,
                verification["summary"]["subtitle_page_cue_occurrences"],
            )
            self.assertIn("sha256", verification["outputs"]["AC0917_EVENT_AUDIO_AUTHORITY.json"])
            with self.assertRaises(MODULE.Ac0917AudioAuthorityError):
                MODULE.write_outputs(report, output)


if __name__ == "__main__":
    unittest.main()
