import unittest

from tools.frida_runtime_probe.build_ac1101_exhaustive_authoritative_longform import (
    EDITORIAL_ORDER,
    REQUIRED_EVENTS,
    Ac1101ExhaustiveError,
    _speaker_code_from_caption,
    event_code_map,
    frame_to_ms,
    layer_role,
    presentation_projection,
    resolve_routes,
)


def dirinfo_rows():
    entries = ("ac1101_001", "ac1101_008", "ac1101_009", "ac1101_010", "ac1101_011")
    choices = ("ac1101_002", "ac1101_007")
    tails = (
        ("ac1101_003",),
        ("ac1101_004", "ac1101_005"),
        ("ac1101_004", "ac1101_006"),
    )
    routes = [
        (entry, choice, *tail)
        for entry in entries
        for choice in choices
        for tail in tails
    ]
    routes.append(("ac1101_012", "ac1101_013"))
    rows = []
    codes = {event: f"0x{index:016x}" for index, event in enumerate(REQUIRED_EVENTS, 1)}
    for row_index, route in enumerate(routes):
        for selector, event in enumerate(route):
            rows.append(
                {
                    "kind": "53",
                    "row_index": str(row_index),
                    "selector_raw": str(selector * 2),
                    "scene_name": event,
                    "code_hex": codes[event],
                    "resolved_source_count": "0" if event in {"ac1101_002", "ac1101_006", "ac1101_012", "ac1101_013"} else "2",
                }
            )
    return rows


class Ac1101ExhaustiveTests(unittest.TestCase):
    def test_editorial_order_is_exact_event_bijection(self):
        self.assertEqual(len(EDITORIAL_ORDER), 13)
        self.assertEqual(set(EDITORIAL_ORDER), set(REQUIRED_EVENTS))

    def test_routes_cover_all_thirty_one_rows_and_thirteen_events(self):
        routes = resolve_routes(dirinfo_rows())
        self.assertEqual(len(routes), 31)
        self.assertEqual({event for route in routes for event in route["events"]}, set(REQUIRED_EVENTS))
        self.assertEqual(routes[-1]["events"], ["ac1101_012", "ac1101_013"])

    def test_event_code_map_rejects_conflict(self):
        rows = dirinfo_rows()
        self.assertEqual(set(event_code_map(rows)), set(REQUIRED_EVENTS))
        duplicate = dict(rows[0])
        duplicate["code_hex"] = "0xffffffffffffffff"
        with self.assertRaises(Ac1101ExhaustiveError):
            event_code_map([*rows, duplicate])

    def test_frame_quantization_matches_runtime_convention(self):
        self.assertEqual(frame_to_ms(1), 33)
        self.assertEqual(frame_to_ms(30), 1000)
        self.assertEqual(frame_to_ms(249), 8300)

    def test_layer_roles_include_recovered_secondary_scenes(self):
        self.assertEqual(layer_role("ac1101_lev_c001_c002_title_wht_S", "ac1101_lev_title_wht"), "screen_overlay")
        self.assertEqual(layer_role("ac8000_cmn_tx_tuduku", "ac8000_cmn_tx_tuduku"), "screen_overlay")
        self.assertEqual(layer_role("ac8040_kyo_anten", "ac8040_kyo_anten"), "screen_overlay")
        self.assertEqual(layer_role("ac8040_shouri_EF_small", "ac8040_shouri_EF_small"), "screen_overlay")
        self.assertEqual(layer_role("ac1101_1on_c003", "ac1101_1on_c003"), "background")

    def test_speaker_tokens_use_registry_codes_and_leave_universal_title_unprefixed(self):
        self.assertEqual(_speaker_code_from_caption("cap1101_neko_san_011_01"), "sana")
        self.assertEqual(_speaker_code_from_caption("cap1101_neko_iro_022"), "iro")
        self.assertEqual(_speaker_code_from_caption("cap1101_neko_uni_028"), "")

    def test_projection_distinguishes_complete_presentations(self):
        base = {
            "render_frame_count": 30,
            "clips": [{"source_sha256": "A" * 64, "event_start_ms": 0, "event_end_ms": 1000, "dgm_role": "background"}],
            "audio": [{"request_id": "1", "start_ms": 0, "duration_ms": 500, "volume_bus": "VOICE"}],
            "subtitles": [{"text": "A", "start_ms": 0, "end_ms": 500, "voice_request_id": "1"}],
        }
        changed = {**base, "render_frame_count": 31}
        self.assertNotEqual(presentation_projection(base), presentation_projection(changed))


if __name__ == "__main__":
    unittest.main()
