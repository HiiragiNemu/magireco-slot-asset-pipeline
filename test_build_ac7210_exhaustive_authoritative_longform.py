import unittest

from tools.frida_runtime_probe.build_ac7210_exhaustive_authoritative_longform import (
    ALL_EVENTS,
    DEFERRED_EVENTS,
    EDITORIAL_ORDER,
    STORY_EVENTS,
    Ac7210ExhaustiveError,
    _speaker_code_from_caption,
    event_code_map,
    event_layer_rows,
    renderer_translation_map,
    resolve_routes,
    translation_rows_by_request,
)


def route_authority():
    sequences = [
        ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_004"],
        ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_004"],
        ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_006"],
        ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_006"],
        ["ac7210_007", "ac7210_008"],
    ]
    rows = []
    for index, sequence in enumerate(sequences):
        story = [event for event in sequence if event in STORY_EVENTS]
        deferred = [event for event in sequence if event in DEFERRED_EVENTS]
        rows.append(
            {
                "dirinfo_row": index,
                "ordered_events": sequence,
                "native416_story_events": story,
                "lower_priority_component_events": deferred,
                "native416_story_projection_status": "CLOSED",
                "full_route_single_canvas_status": (
                    "NATIVE416_ONLY" if not deferred else "MIXED"
                ),
            }
        )
    return {"dirinfo_routes": rows}


def translations():
    values = {
        3279: ("私達で足止めするわよ！", "我们来拖住它！"),
        3280: ("きゃぁぁっ", "呀啊啊！"),
        3593: ("今だよ！", "就是现在！"),
        3594: ("きゃぁぁっ", "呀啊啊！"),
    }
    return {
        "translations": [
            {"request_id": request, "ja": values[request][0], "zh": values[request][1]}
            for request in values
        ]
    }


class Ac7210ExhaustiveTests(unittest.TestCase):
    def test_editorial_order_is_story_bijection_and_defers_512(self):
        self.assertEqual(set(EDITORIAL_ORDER), set(STORY_EVENTS))
        self.assertEqual(set(ALL_EVENTS), set(STORY_EVENTS) | set(DEFERRED_EVENTS))
        self.assertTrue(set(EDITORIAL_ORDER).isdisjoint(DEFERRED_EVENTS))

    def test_routes_cover_all_eight_events_and_keep_component_boundary(self):
        rows = resolve_routes(route_authority())
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            {event for row in rows for event in row["ordered_events"]},
            set(ALL_EVENTS),
        )
        self.assertEqual(rows[4]["native416_story_projection"], [])
        self.assertEqual(rows[4]["deferred_component_terminal"], list(DEFERRED_EVENTS[1:]))

    def test_route_validation_fails_on_projection_mismatch(self):
        value = route_authority()
        value["dirinfo_routes"][0]["native416_story_events"] = ["ac7210_001"]
        with self.assertRaises(Ac7210ExhaustiveError):
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
        runtime["events"]["ac7210_001"]["event_code"] = "0xffffffffffffffff"
        with self.assertRaises(Ac7210ExhaustiveError):
            event_code_map(runtime)

    def test_alias_omission_retimes_canonical_sources_contiguously(self):
        visual = {
            "z2d_chunks": [
                {
                    "name": "ac7210_002",
                    "movie_layers": [
                        {
                            "z2d_reference": "a.dgm",
                            "content_class": "native416_story_visual",
                            "audience_dedup_disposition": "CANONICAL_RETAIN_ONCE",
                            "start_frame": 0,
                        },
                        {
                            "z2d_reference": "alias.dgm",
                            "content_class": "native416_story_visual",
                            "audience_dedup_disposition": "ALIAS_SKIP_USE_a.dgm",
                            "start_frame": 30,
                        },
                        {
                            "z2d_reference": "b.dgm",
                            "content_class": "native416_story_visual",
                            "audience_dedup_disposition": "CANONICAL_RETAIN_ONCE",
                            "start_frame": 60,
                        },
                    ],
                },
                *[
                    {"name": event, "movie_layers": []}
                    for event in STORY_EVENTS
                    if event != "ac7210_002"
                ],
            ]
        }
        sources = {
            "a": {
                "dgm_name": "a",
                "playback_frame_count": 30,
                "source_frame_count": 30,
                "path": "a.mp4",
                "sha256": "A" * 64,
                "source_frame_contract": "exact",
            },
            "b": {
                "dgm_name": "b",
                "playback_frame_count": 20,
                "source_frame_count": 20,
                "path": "b.mp4",
                "sha256": "B" * 64,
                "source_frame_contract": "exact",
            },
        }
        rows, frames = event_layer_rows("ac7210_002", visual, sources)
        self.assertEqual(frames, 50)
        self.assertEqual(
            [(row["event_start_frame"], row["event_end_frame_exclusive"]) for row in rows],
            [(0, 30), (30, 50)],
        )

    def test_speaker_codes_use_existing_registry_identities(self):
        self.assertEqual(_speaker_code_from_caption("cap7210_hobaku_yac_001"), "yac")
        self.assertEqual(_speaker_code_from_caption("cap7210_hobaku_tur_002"), "tur")
        self.assertEqual(_speaker_code_from_caption("unknown"), "")

    def test_renderer_translation_projection_has_strict_loader_fields(self):
        resolved = translation_rows_by_request(translations())
        projected = renderer_translation_map(resolved)
        self.assertEqual(len(projected["translations"]), 3)
        self.assertTrue(
            all(set(row) == {"ja", "zh", "status"} for row in projected["translations"])
        )
        self.assertTrue(
            all(row["status"] == "machine_draft_pending_owner" for row in projected["translations"])
        )


if __name__ == "__main__":
    unittest.main()
