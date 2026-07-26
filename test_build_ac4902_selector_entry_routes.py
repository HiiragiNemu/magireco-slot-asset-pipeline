import sys
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent / "tools" / "frida_runtime_probe"
sys.path.insert(0, str(MODULE_DIR))
import build_ac4902_selector_entry_routes as module  # noqa: E402


class BuildAc4902SelectorEntryRoutesTest(unittest.TestCase):
    def test_contract_is_native_independent_and_has_no_showcase(self):
        self.assertEqual((module.WIDTH, module.HEIGHT, module.FPS), (416, 232, 30))
        self.assertEqual(module.EDITIONS, ("none", "ja", "zh"))
        self.assertEqual(
            module.COMPOSITION_CLAIM,
            "independent_native_dirinfo_routes_no_showcase",
        )

    def test_fixed_route_partition_is_seventeen_plus_nine(self):
        self.assertEqual(len(module.EXPECTED_CANONICAL_ROUTES), 17)
        self.assertEqual(len(module.EXPECTED_DUPLICATE_ROWS), 9)
        self.assertEqual(
            set(module.EXPECTED_CANONICAL_ROUTES),
            {14, 15, 16, 17, 24, 25, 26, 27, 34, 35, 37, 44, 45, 46, 55, 58, 59},
        )
        self.assertEqual(
            set(module.EXPECTED_DUPLICATE_ROWS),
            {36, 38, 39, 40, 41, 53, 54, 66, 67},
        )

    def test_entry_contracts_are_on_frame_sample_grid(self):
        self.assertEqual(
            {
                event: (
                    row["alias"],
                    row["frames"],
                    row["frames"] * module.SAMPLES_PER_FRAME,
                )
                for event, row in module.ENTRY_CONTRACTS.items()
            },
            {
                "ac4902_005": ("ac4902_056", 603, 964800),
                "ac4902_014": ("ac4902_057", 100, 160000),
                "ac4902_017": ("ac4902_058", 189, 302400),
            },
        )
        for row in module.ENTRY_CONTRACTS.values():
            self.assertEqual(row["main_frames"] + row["loop_frames"], row["frames"])
            self.assertEqual(row["request_id"] > 0, True)
            self.assertEqual(row["sound_code"] > 0, True)

    def _aliases(self):
        aliases = {
            "ac4902_054": "ac4902_001",
            "ac4902_064": "ac4902_008",
            "ac4902_066": "ac4902_010",
            "ac4902_067": "ac4902_011",
            "ac4902_068": "ac4902_012",
            "ac4902_069": "ac4902_013",
            "ac4902_070": "ac4902_015",
            "ac4902_071": "ac4902_029",
            "ac4902_073": "ac4902_018",
            "ac4902_074": "ac4902_019",
        }
        aliases.update(
            {row["alias"]: event for event, row in module.ENTRY_CONTRACTS.items()}
        )
        return aliases

    def _route_plan(self):
        routes = []
        row_to_id = {}
        for row_index, (raw, render) in module.EXPECTED_CANONICAL_ROUTES.items():
            route_id = f"row{row_index:03d}"
            row_to_id[row_index] = route_id
            routes.append(
                {
                    "route_id": route_id,
                    "title": f"route {row_index}",
                    "source_row": {
                        "row_index": row_index,
                        "raw_event_sequence": list(raw),
                    },
                    "render_event_sequence": list(render),
                }
            )
        duplicates = [
            {
                "row_index": row_index,
                "canonical_route_id": row_to_id[canonical_row],
                "raw_event_sequence": list(raw),
            }
            for row_index, (canonical_row, raw) in module.EXPECTED_DUPLICATE_ROWS.items()
        ]
        source_routes = {
            row_index: list(raw)
            for row_index, (raw, _) in module.EXPECTED_CANONICAL_ROUTES.items()
        }
        source_routes.update(
            {
                row_index: list(raw)
                for row_index, (_, raw) in module.EXPECTED_DUPLICATE_ROWS.items()
            }
        )
        return routes, duplicates, source_routes

    def test_route_declarations_validate_exact_aliases(self):
        routes, duplicates, source_routes = self._route_plan()
        validated, removed = module.validate_route_declarations(
            routes_raw=routes,
            duplicate_rows_raw=duplicates,
            source_routes=source_routes,
            aliases=self._aliases(),
        )
        self.assertEqual(len(validated), 17)
        self.assertEqual(len(removed), 9)
        self.assertEqual(validated[8]["render_event_sequence"][1], "ac4902_005")
        self.assertEqual(removed[0]["canonical_source_row"], 16)

    def test_route_alias_or_dirinfo_drift_fails_closed(self):
        routes, duplicates, source_routes = self._route_plan()
        source_routes[36] = ["ac4902_054", "ac4902_056", "ac4902_008"]
        with self.assertRaises(ValueError):
            module.validate_route_declarations(
                routes_raw=routes,
                duplicate_rows_raw=duplicates,
                source_routes=source_routes,
                aliases=self._aliases(),
            )

    def test_mixed_timeline_inserts_entry_on_exact_grid(self):
        family = {
            "ac4902_001": {
                "start_frame": 0,
                "end_frame": 120,
                "start_sample": 0,
                "end_sample": 192000,
            },
            "ac4902_006": {
                "start_frame": 567,
                "end_frame": 927,
                "start_sample": 907200,
                "end_sample": 1483200,
            },
        }
        entries = {
            "ac4902_005": {
                "frames": 603,
                "samples": 964800,
            }
        }
        timeline, frames, samples = module.mixed_route_timeline(
            ["ac4902_001", "ac4902_005", "ac4902_006"],
            family_timeline=family,
            entry_events=entries,
        )
        self.assertEqual((frames, samples), (1083, 1732800))
        self.assertEqual(timeline[1]["source_kind"], "hash_bound_entry_event")
        self.assertEqual(timeline[2]["start_frame"], 723)
        self.assertEqual(samples, frames * module.SAMPLES_PER_FRAME)

    def test_entry_event_cannot_inherit_family_subtitles(self):
        family = {
            "ac4902_001": {
                "start_sample": 0,
                "end_sample": 192000,
            },
            "ac4902_006": {
                "start_sample": 907200,
                "end_sample": 1483200,
            },
        }
        entries = {"ac4902_005": {"samples": 964800}}
        cues = [
            {"start_ms": 10, "end_ms": 100, "text": "黑羽：可恶！"},
            {"start_ms": 19000, "end_ms": 19500, "text": "outcome"},
        ]
        output = module.mixed_route_subtitle_cues(
            ["ac4902_001", "ac4902_005", "ac4902_006"],
            family_timeline=family,
            source_cues=cues,
            entry_events=entries,
        )
        self.assertEqual([row["text"] for row in output], ["黑羽：可恶！", "outcome"])
        self.assertGreater(output[1]["start_ms"], 24000)

    def test_kuroba_correction_is_exact_and_fail_closed(self):
        valid = [
            {"text": "黑羽：可恶！"},
            {"text": "unrelated"},
            {"text": "黑羽：可恶！"},
        ]
        module.validate_kuroba_subtitles(valid)
        valid[0] = {"text": "黑江：可恶！"}
        with self.assertRaises(ValueError):
            module.validate_kuroba_subtitles(valid)


if __name__ == "__main__":
    unittest.main()
