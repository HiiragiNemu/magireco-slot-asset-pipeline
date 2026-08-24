from __future__ import annotations

import copy
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac4901_route_dedup_authority as MODULE


class Ac4901RouteDedupAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = MODULE.read_route_contract(
            Path(
                "tools/frida_runtime_probe/series_proposals/"
                "ac4901_dirinfo_routes_native416_v1.json"
            )
        )

    def _dirinfo_rows(self) -> list[dict[str, str]]:
        rows = []
        for route in self.contract["routes"]:
            for selector, event in zip(route["selectors"], route["events"]):
                rows.append(
                    {
                        "kind": "112",
                        "base_name": "ac4901",
                        "route_status": "ok",
                        "row_index": str(route["route_index"]),
                        "selector_raw": str(selector),
                        "scene_name": event,
                    }
                )
        return rows

    def test_exact_dirinfo_contract_covers_every_event(self) -> None:
        routes = MODULE.validate_dirinfo(self._dirinfo_rows(), self.contract)
        self.assertEqual(162, len(routes))
        self.assertEqual(720, sum(row["event_count"] for row in routes))
        self.assertEqual(
            set(MODULE.EVENTS),
            {event for route in routes for event in route["event_sequence"]},
        )

    def test_rejects_route_drift(self) -> None:
        rows = self._dirinfo_rows()
        rows[0]["scene_name"] = "ac4901_999"
        with self.assertRaisesRegex(MODULE.Ac4901RouteDedupError, "route differs"):
            MODULE.validate_dirinfo(rows, self.contract)

    def test_only_three_exact_event_ids_share_one_complete_signature(self) -> None:
        payloads = {
            event: {"complete": MODULE.EXPECTED_ALIASES.get(event, event)}
            for event in MODULE.EVENTS
        }
        mapping, groups, _ = MODULE.group_complete_signatures(payloads)
        self.assertEqual(MODULE.EXPECTED_ALIASES, {
            event: canonical
            for event, canonical in mapping.items()
            if event != canonical
        })
        self.assertEqual(203, len(groups))

    def test_editorial_units_preserve_all_prior_frame_variants(self) -> None:
        routes = MODULE.validate_dirinfo(self._dirinfo_rows(), self.contract)
        mapping = {
            event: MODULE.EXPECTED_ALIASES.get(event, event)
            for event in MODULE.EVENTS
        }
        units, route_rows = MODULE.editorial_units(routes, mapping)
        self.assertEqual(220, len(units))
        self.assertEqual(18, sum(bool(row["underlay_event"]) for row in units))
        self.assertEqual(162, len(route_rows))
        self.assertEqual(
            MODULE.PRIOR_UNDERLAY_EVENTS,
            frozenset(row["underlay_event"] for row in units if row["underlay_event"]),
        )

    def test_unexpected_duplicate_fails_closed(self) -> None:
        payloads = {event: {"complete": event} for event in MODULE.EVENTS}
        payloads["ac4901_112"] = copy.deepcopy(payloads["ac4901_105"])
        payloads["ac4901_232"] = copy.deepcopy(payloads["ac4901_105"])
        payloads["ac4901_002"] = copy.deepcopy(payloads["ac4901_001"])
        with self.assertRaisesRegex(
            MODULE.Ac4901RouteDedupError, "equality groups differ"
        ):
            MODULE.group_complete_signatures(payloads)


if __name__ == "__main__":
    unittest.main()
