import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import resolve_ac0915_event_audio_authority as m


class Ac0915EventAudioAuthorityTests(unittest.TestCase):
    def _fixture(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        binary = root / "libGameProc.so"
        binary.write_bytes(b"fixture-slot")
        audio_root = root / "audio"
        audio_root.mkdir()

        events = []
        for event in m.EVENTS:
            non_movie = []
            movie = []
            seen_hosts = set()
            for host, _, _, frame, _ in m.EXPECTED_CALLBACKS_BY_EVENT[event]:
                if host in seen_hosts:
                    continue
                seen_hosts.add(host)
                end = min(frame + 29, m.EXPECTED_PRESENTATION_FRAMES[event] - 1)
                if host.startswith("ac8002_"):
                    movie.append(
                        {
                            "parent_z2d": host,
                            "event_start_frame": frame,
                            "event_end_frame_inclusive": end,
                        }
                    )
                else:
                    non_movie.append(
                        {
                            "node": host,
                            "event_global_start_frame": frame,
                            "event_global_end_frame_inclusive": end,
                        }
                    )
            events.append(
                {
                    "event": event,
                    "presentation_frame_count": m.EXPECTED_PRESENTATION_FRAMES[event],
                    "non_movie_text_z2d_nodes": non_movie,
                    "layers_in_render_pass_order_under_to_top": movie,
                }
            )
        visual = {
            "schema": "magireco-ac0915-output-projection-authority-v1",
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "family": "ac0915",
            "frame_rate": "30/1",
            "output_canvas": [416, 232],
            "events": events,
        }
        visual_path = root / "visual.json"
        visual_path.write_text(json.dumps(visual), encoding="utf-8")

        component_fields = [
            "root",
            "primary_animation",
            "leaf_request_id",
            "leaf_sound_code",
            "start_ms",
            "duration_ms",
            "smz_matches_leaf_request",
            "ogg_duration_match",
            "leaf_code_name",
            "ogg_name",
        ]
        components = []
        for event, specs in m.EXPECTED_EVENT_COMPONENTS.items():
            for request_id, sound_id, start_ms in sorted(specs):
                name = f"s{sound_id}.ogg"
                (audio_root / name).touch(exist_ok=True)
                components.append(
                    {
                        "root": "ac0915",
                        "primary_animation": event,
                        "leaf_request_id": request_id,
                        "leaf_sound_code": sound_id,
                        "start_ms": start_ms,
                        "duration_ms": 100,
                        "smz_matches_leaf_request": "yes",
                        "ogg_duration_match": "yes",
                        "leaf_code_name": f"component_{sound_id}",
                        "ogg_name": name,
                    }
                )
        components_path = root / "components.csv"
        with components_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=component_fields)
            writer.writeheader()
            writer.writerows(components)

        callback_fields = [
            "z2d_name",
            "sound_request_id",
            "sound_resource_id",
            "exec_frame",
            "sound_request_match_count",
            "ogg_exists",
            "sound_duration_ms",
            "sound_code_name",
            "ogg_name",
        ]
        unique_specs = {
            (host, request_id): (sound_id, bus)
            for specs in m.EXPECTED_CALLBACKS_BY_EVENT.values()
            for host, request_id, sound_id, _, bus in specs
        }
        callbacks = []
        buses = {}
        for event_specs in m.EXPECTED_EVENT_COMPONENTS.values():
            for _, sound_id, _ in event_specs:
                buses[sound_id] = 0 if sound_id == 551 else 1
        for (host, request_id), (sound_id, bus) in sorted(unique_specs.items()):
            name = f"s{sound_id}.ogg"
            (audio_root / name).touch(exist_ok=True)
            buses[sound_id] = 2 if bus == "VOICE" else 1
            callbacks.append(
                {
                    "z2d_name": host,
                    "sound_request_id": request_id,
                    "sound_resource_id": sound_id,
                    "exec_frame": 0,
                    "sound_request_match_count": 1,
                    "ogg_exists": "yes",
                    "sound_duration_ms": 100,
                    "sound_code_name": f"callback_{sound_id}",
                    "ogg_name": name,
                }
            )
        callbacks_path = root / "callbacks.csv"
        with callbacks_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=callback_fields)
            writer.writeheader()
            writer.writerows(callbacks)

        translation_path = (
            Path(m.__file__).resolve().parent
            / "translations"
            / "ac0915_exhaustive_native416_zh_dialogue_v1.json"
        )
        return {
            "temp": temp,
            "binary": binary,
            "visual": visual,
            "visual_path": visual_path,
            "components": components,
            "components_path": components_path,
            "callbacks": callbacks,
            "callbacks_path": callbacks_path,
            "translation_path": translation_path,
            "audio_root": audio_root,
            "buses": buses,
        }

    @staticmethod
    def _write_csv(path, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def _build(self, fixture, buses=None):
        selected = dict(fixture["buses"] if buses is None else buses)
        with mock.patch.object(
            m, "read_sound_divide_values", return_value=("fixture-build", selected)
        ):
            return m.build_report(
                binary=fixture["binary"],
                visual_authority_path=fixture["visual_path"],
                event_audio_components_path=fixture["components_path"],
                z2d_sound_callbacks_path=fixture["callbacks_path"],
                translation_path=fixture["translation_path"],
                durable_audio_root=fixture["audio_root"],
            )

    def test_closes_exact_audio_bus_and_event_global_subtitle_contract(self):
        fixture = self._fixture()
        self.addCleanup(fixture["temp"].cleanup)
        report = self._build(fixture)
        self.assertEqual(report["summary"]["retained_audio_occurrences"], 40)
        self.assertEqual(report["summary"]["retained_se_occurrences"], 22)
        self.assertEqual(report["summary"]["retained_voice_occurrences"], 18)
        self.assertEqual(report["summary"]["excluded_bgm_occurrences"], 1)
        self.assertEqual(report["summary"]["subtitle_cue_occurrences"], 18)
        self.assertEqual(report["summary"]["unique_official_ogg_sources"], 30)
        excluded = report["excluded_audio_rows"][0]
        self.assertEqual((excluded["event"], excluded["request_id"], excluded["sound_id"]), ("ac0915_012", 226, 551))
        cue = next(row for row in report["subtitle_cues"] if row["event"] == "ac0915_002")
        self.assertEqual((cue["start_frame"], cue["start_ms"]), (9, 300))
        self.assertFalse(report["assertions"]["child_local_timing_without_parent_offset_used"])

    def test_rejects_visual_parent_start_drift(self):
        fixture = self._fixture()
        self.addCleanup(fixture["temp"].cleanup)
        visual = copy.deepcopy(fixture["visual"])
        event = next(row for row in visual["events"] if row["event"] == "ac0915_002")
        event["non_movie_text_z2d_nodes"][0]["event_global_start_frame"] = 8
        fixture["visual_path"].write_text(json.dumps(visual), encoding="utf-8")
        with self.assertRaisesRegex(m.Ac0915AudioAuthorityError, "exact callback binding differs"):
            self._build(fixture)

    def test_rejects_child_callback_frame_drift(self):
        fixture = self._fixture()
        self.addCleanup(fixture["temp"].cleanup)
        callbacks = copy.deepcopy(fixture["callbacks"])
        row = next(item for item in callbacks if int(item["sound_request_id"]) == 5592)
        row["exec_frame"] = 1
        self._write_csv(fixture["callbacks_path"], callbacks)
        with self.assertRaisesRegex(m.Ac0915AudioAuthorityError, "exact callback binding differs"):
            self._build(fixture)

    def test_rejects_reclassifying_the_only_bgm_row_as_se(self):
        fixture = self._fixture()
        self.addCleanup(fixture["temp"].cleanup)
        buses = dict(fixture["buses"])
        buses[551] = 1
        with self.assertRaisesRegex(m.Ac0915AudioAuthorityError, "audio authority dimensions differ"):
            self._build(fixture, buses=buses)


if __name__ == "__main__":
    unittest.main()
