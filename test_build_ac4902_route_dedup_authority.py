import copy
import unittest

from tools.frida_runtime_probe import build_ac4902_route_dedup_authority as m
from tools.frida_runtime_probe import resolve_ac4902_event_audio_authority as audio_authority


class Ac4902RouteDedupAuthorityTests(unittest.TestCase):
    @staticmethod
    def _dirinfo_rows():
        rows = []
        for route_index, sequence in m.ROUTES.items():
            selectors = (
                [0, 1, 2]
                if route_index in {13, 43, 57, 69}
                else {3: [0, 1, 4], 4: [0, 1, 4, 6], 5: [0, 1, 4, 5, 7]}[
                    len(sequence)
                ]
            )
            for selector_raw, event in zip(selectors, sequence):
                rows.append(
                    {
                        "kind": "113",
                        "base_name": "ac4902",
                        "route_status": "ok",
                        "row_index": str(route_index),
                        "selector_raw": str(selector_raw),
                        "scene_name": event,
                    }
                )
        return rows

    @staticmethod
    def _complete_presentation_payloads():
        payloads = {}
        for event in m.EVENTS:
            canonical = m.EXPECTED_ALIASES.get(event, event)
            payloads[event] = {
                "visual": {"exact_complete_presentation": canonical},
                "audio_and_subtitles": {"exact_complete_presentation": canonical},
            }
        return payloads

    def test_exact_dirinfo_routes_cover_all_events(self):
        routes = m.validate_dirinfo(self._dirinfo_rows())
        self.assertEqual(len(routes), 70)
        self.assertEqual(sum(row["event_count"] for row in routes), 260)
        self.assertEqual(
            {event for row in routes for event in row["event_sequence"]},
            set(m.EVENTS),
        )

    def test_rejects_dirinfo_route_drift(self):
        rows = self._dirinfo_rows()
        rows[0]["scene_name"] = "ac4902_999"
        with self.assertRaisesRegex(m.Ac4902RouteDedupError, "DirInfo route differs"):
            m.validate_dirinfo(rows)

    def test_exactly_sixteen_complete_presentations_are_aliases(self):
        event_to_canonical, groups, _ = m.group_complete_signatures(
            self._complete_presentation_payloads()
        )
        self.assertEqual(
            {event: canonical for event, canonical in event_to_canonical.items() if event != canonical},
            m.EXPECTED_ALIASES,
        )
        self.assertEqual(len(groups), 48)
        self.assertTrue(
            {f"ac4902_{index:03d}" for index in range(54, 75)}.isdisjoint(
                m.EXPECTED_ALIASES
            )
        )

    def test_rejects_an_unexpected_complete_presentation_duplicate(self):
        payloads = self._complete_presentation_payloads()
        payloads["ac4902_002"] = copy.deepcopy(payloads["ac4902_001"])
        with self.assertRaisesRegex(
            m.Ac4902RouteDedupError, "complete presentation equality groups differ"
        ):
            m.group_complete_signatures(payloads)

    def test_editorial_timeline_is_duplicate_free_and_exact_length(self):
        self.assertEqual(len(m.EDITORIAL_ORDER), 48)
        self.assertEqual(len(set(m.EDITORIAL_ORDER)), 48)
        self.assertTrue(set(m.EDITORIAL_ORDER).isdisjoint(m.EXPECTED_ALIASES))
        self.assertEqual(
            sum(
                m.EXPECTED_EVENT_FRAMES[event]
                + (13 if event in audio_authority.EXTENDED_HOLD_EVENTS else 0)
                for event in m.EDITORIAL_ORDER
            ),
            19079,
        )


if __name__ == "__main__":
    unittest.main()
