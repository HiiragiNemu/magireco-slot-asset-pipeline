import unittest

from tools.frida_runtime_probe.build_ac1104_exhaustive_authoritative_longform import (
    EDITORIAL_ORDER,
    REQUIRED_EVENTS,
    Ac1104ExhaustiveError,
    event_code_map,
    frame_to_ms,
    layer_role,
    presentation_projection,
    resolve_routes,
)


def dirinfo_rows():
    routes = (
        ("ac1104_001", "ac1104_002", "ac1104_003"),
        ("ac1104_001", "ac1104_002", "ac1104_004"),
        ("ac1104_005", "ac1104_002", "ac1104_003"),
        ("ac1104_005", "ac1104_002", "ac1104_004"),
        ("ac1104_006", "ac1104_002", "ac1104_003"),
        ("ac1104_006", "ac1104_002", "ac1104_004"),
        ("ac1104_007", "ac1104_002", "ac1104_003"),
        ("ac1104_007", "ac1104_002", "ac1104_004"),
        ("ac1104_008", "ac1104_009", "ac1104_010"),
        ("ac1104_008", "ac1104_009", "ac1104_011", "ac1104_012"),
        ("ac1104_008", "ac1104_009", "ac1104_011", "ac1104_013"),
        ("ac1104_014", "ac1104_015", "ac1104_010"),
        ("ac1104_014", "ac1104_015", "ac1104_011", "ac1104_012"),
        ("ac1104_014", "ac1104_015", "ac1104_011", "ac1104_013"),
        ("ac1104_016", "ac1104_017"),
    )
    rows = []
    codes = {event: f"0x{index:016x}" for index, event in enumerate(REQUIRED_EVENTS, 1)}
    for row_index, route in enumerate(routes):
        for selector, event in enumerate(route):
            rows.append(
                {
                    "kind": "56",
                    "row_index": str(row_index),
                    "selector_raw": str(selector * 2),
                    "scene_name": event,
                    "code_hex": codes[event],
                    "resolved_source_count": "0" if event in {"ac1104_002", "ac1104_013", "ac1104_016", "ac1104_017"} else "2",
                }
            )
    return rows


class Ac1104ExhaustiveTests(unittest.TestCase):
    def test_editorial_order_is_exact_event_bijection(self):
        self.assertEqual(len(EDITORIAL_ORDER), 17)
        self.assertEqual(set(EDITORIAL_ORDER), set(REQUIRED_EVENTS))

    def test_routes_cover_all_fifteen_rows_and_seventeen_events(self):
        routes = resolve_routes(dirinfo_rows())
        self.assertEqual(len(routes), 15)
        self.assertEqual(
            {event for route in routes for event in route["events"]},
            set(REQUIRED_EVENTS),
        )
        self.assertEqual(routes[-1]["events"], ["ac1104_016", "ac1104_017"])

    def test_event_code_map_rejects_conflict(self):
        rows = dirinfo_rows()
        result = event_code_map(rows)
        self.assertEqual(set(result), set(REQUIRED_EVENTS))
        duplicate = dict(rows[0])
        duplicate["code_hex"] = "0xffffffffffffffff"
        with self.assertRaises(Ac1104ExhaustiveError):
            event_code_map([*rows, duplicate])

    def test_frame_quantization_matches_runtime_convention(self):
        self.assertEqual(frame_to_ms(1), 33)
        self.assertEqual(frame_to_ms(30), 1000)
        self.assertEqual(frame_to_ms(74), 2467)
        self.assertEqual(frame_to_ms(532), 17733)

    def test_layer_roles_preserve_verified_overlay_families(self):
        self.assertEqual(
            layer_role("ac1104_lev_c001_c002_title_wht_S", "ac1104_lev_title_wht"),
            "screen_overlay",
        )
        self.assertEqual(
            layer_role("ac1104_lev_c009", "ac1104_lev_c009"),
            "screen_overlay",
        )
        self.assertEqual(
            layer_role("ac8040_shouri_EF_small", "ac8040_shouri_EF_small"),
            "screen_overlay",
        )
        self.assertEqual(
            layer_role("ac1104_1on_c003_c004", "ac1104_1on_c003"),
            "background",
        )

    def test_projection_distinguishes_complete_presentations(self):
        base = {
            "render_frame_count": 30,
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
                    "request_id": "1",
                    "start_ms": 0,
                    "duration_ms": 500,
                    "volume_bus": "VOICE",
                }
            ],
            "subtitles": [
                {
                    "text": "A",
                    "start_ms": 0,
                    "end_ms": 500,
                    "voice_request_id": "1",
                }
            ],
        }
        changed = {**base, "render_frame_count": 31}
        self.assertNotEqual(presentation_projection(base), presentation_projection(changed))


if __name__ == "__main__":
    unittest.main()
