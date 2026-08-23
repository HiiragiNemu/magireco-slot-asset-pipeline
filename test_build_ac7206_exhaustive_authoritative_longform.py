import unittest
from pathlib import Path

from tools.frida_runtime_probe.build_ac7206_exhaustive_authoritative_longform import (
    ALL_EVENTS,
    EDITORIAL_ORDER,
    GAMEPLAY_EVENT,
    STORY_EVENTS,
    Ac7206ExhaustiveError,
    _speaker_code_from_caption,
    event_code_map,
    resolve_routes,
    source_path_for_dgm,
    visual_projection,
)
from tools.frida_runtime_probe.build_ac1101_exhaustive_authoritative_longform import (
    presentation_projection,
)
from tools.frida_runtime_probe.build_sp_story_chapter_reviews import (
    load_translation_map,
)


def route_audit():
    routes = []
    row = 0
    for entry, outcomes in (
        ("ac7206_001", STORY_EVENTS[2:8]),
        ("ac7206_002", STORY_EVENTS[8:14]),
    ):
        base = []
        for outcome in outcomes[:4]:
            base.append([entry, outcome])
        for outcome in outcomes[:4]:
            base.append([entry, outcome, GAMEPLAY_EVENT])
        for outcome in outcomes[4:]:
            base.append([entry, outcome])
        for _ in range(2):
            for sequence in base:
                routes.append(
                    {
                        "row_index": row,
                        "selector_values": list(range(1, len(sequence) + 1)),
                        "event_sequence": sequence,
                    }
                )
                row += 1
    return {"route_universe": {"route_count": 40, "routes": routes}}


class Ac7206ExhaustiveTests(unittest.TestCase):
    def test_editorial_order_is_exact_story_event_bijection(self):
        self.assertEqual(len(EDITORIAL_ORDER), 14)
        self.assertEqual(set(EDITORIAL_ORDER), set(STORY_EVENTS))
        self.assertNotIn(GAMEPLAY_EVENT, EDITORIAL_ORDER)

    def test_routes_preserve_forty_rows_and_dedupe_twenty_sequences(self):
        routes = resolve_routes(route_audit())
        self.assertEqual(len(routes), 40)
        self.assertEqual(
            {event for route in routes for event in route["event_sequence"]},
            set(ALL_EVENTS),
        )
        self.assertEqual(len({tuple(row["event_sequence"]) for row in routes}), 20)
        self.assertEqual(len({tuple(row["story_projection"]) for row in routes}), 12)
        self.assertEqual(sum(row["duplicate_event_sequence_alias_of"] is not None for row in routes), 20)

    def test_route_validation_rejects_gameplay_in_the_middle(self):
        value = route_audit()
        value["route_universe"]["routes"][0]["event_sequence"] = [
            "ac7206_001",
            GAMEPLAY_EVENT,
            "ac7206_003",
        ]
        with self.assertRaises(Ac7206ExhaustiveError):
            resolve_routes(value)

    def test_runtime_event_code_map_binds_all_events(self):
        requested = {
            event: f"0x{index:016x}" for index, event in enumerate(ALL_EVENTS, 1)
        }
        runtime = {
            "requested_events": requested,
            "events": {
                event: {"event_code": code} for event, code in requested.items()
            },
        }
        self.assertEqual(event_code_map(runtime), requested)
        runtime["events"]["ac7206_001"]["event_code"] = "0xffffffffffffffff"
        with self.assertRaises(Ac7206ExhaustiveError):
            event_code_map(runtime)

    def test_story_source_path_is_native_family_only(self):
        root = __import__("pathlib").Path("D:/named")
        self.assertEqual(
            source_path_for_dgm(root, "ac7206_arina_kaiga_lev_01"),
            (root / "patch" / "ac7206" / "ac7206_arina_kaiga_lev_01.mp4").resolve(),
        )
        with self.assertRaises(Ac7206ExhaustiveError):
            source_path_for_dgm(root, "ac8050_uwanose_base_ZEN_bg_LP")

    def test_caption_speaker_uses_existing_registry_code(self):
        self.assertEqual(_speaker_code_from_caption("cap7206_paint_ari_004"), "ari")
        self.assertEqual(_speaker_code_from_caption("unknown"), "")

    def test_same_visual_can_be_distinct_complete_av_presentation(self):
        base = {
            "video_duration_ms": 1000,
            "render_frame_count": 105,
            "clips": [
                {
                    "source_sha256": "A" * 64,
                    "event_start_ms": 0,
                    "event_end_ms": 1000,
                    "dgm_role": "background",
                }
            ],
            "audio": [
                {
                    "request_id": "5322",
                    "start_ms": 33,
                    "duration_ms": 3482,
                    "volume_bus": "VOICE",
                }
            ],
            "subtitles": [
                {
                    "text": "A",
                    "start_ms": 33,
                    "end_ms": 3515,
                    "voice_request_id": "5322",
                }
            ],
        }
        changed = {
            **base,
            "audio": [{**base["audio"][0], "request_id": "5324"}],
            "subtitles": [
                {
                    **base["subtitles"][0],
                    "text": "B",
                    "voice_request_id": "5324",
                }
            ],
        }
        self.assertEqual(visual_projection(base), visual_projection(changed))
        self.assertNotEqual(
            presentation_projection(base), presentation_projection(changed)
        )

    def test_translation_map_obeys_renderer_contract(self):
        path = (
            Path(__file__).resolve().parent
            / "tools"
            / "frida_runtime_probe"
            / "translations"
            / "ac7206_exhaustive_zh_dialogue_v1.json"
        )
        translations, source = load_translation_map(path)
        self.assertEqual(len(translations), 4)
        self.assertEqual(translations["それこそが本物のアート"], "那才是真正的艺术。")
        self.assertEqual(source["path"], str(path.resolve()))


if __name__ == "__main__":
    unittest.main()
