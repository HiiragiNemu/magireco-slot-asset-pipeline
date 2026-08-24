from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import build_ac4902_output_projection_authority as MODULE


def fake_result() -> dict:
    source = {
        "sha256": "A" * 64,
        "width": 416,
        "height": 232,
        "frame_count": 6,
    }
    occurrence = {
        "event": "ac4902_001",
        "scene": "scene",
        "cut": "cut",
        "parent_z2d": "parent",
        "owning_gdp_layer_index": 5,
        "parent_composition_order": 0,
        "authored_tag_index": 0,
        "source_name": "movie",
        "source": source,
        "frame_policy": {
            "consumed_source_frames": 6,
            "discarded_unreferenced_tail_frames": 0,
        },
        "event_start_frame": 0,
        "event_end_frame_inclusive": 5,
        "effective_renderer_state": 1,
        "renderer_contract": {"rgb": "src_rgb*src_alpha + dst_rgb*(1-src_alpha)"},
        "virtual_layer_rect_ltrb": [128, 0, 1152, 576],
        "runtime_authored_component_scaling": False,
    }
    return {
        "events": [{"event": "ac4902_001"}],
        "occurrences": [occurrence],
        "counts": dict(MODULE.EXPECTED_COUNTS),
        "runtime_authored_component_scale_sources": [],
    }


class Ac4902OutputProjectionTests(unittest.TestCase):
    def test_exact_contract_counts_and_event_set(self) -> None:
        self.assertEqual(64, len(MODULE.EVENT_IDS))
        self.assertEqual(171, MODULE.EXPECTED_COUNTS["loadable_movie_layer_occurrences"])
        self.assertEqual(56, MODULE.EXPECTED_COUNTS["unique_loadable_cri_sources"])
        self.assertEqual(0, MODULE.EXPECTED_COUNTS["unreachable_movie_layer_occurrences"])

    def test_resolver_passes_ac4902_schema_and_cardinalities(self) -> None:
        with mock.patch.object(MODULE, "resolve", return_value=fake_result()) as resolver:
            result = MODULE.resolve_ac4902({}, {}, {}, {}, {})
        kwargs = resolver.call_args.kwargs
        self.assertEqual(MODULE.EVENT_IDS, kwargs["expected_events"])
        self.assertEqual(MODULE.PRESENTATION_SCHEMA, kwargs["expected_presentation_schema"])
        self.assertEqual(MODULE.EXPECTED_COUNTS, kwargs["expected_counts"])
        self.assertEqual(50, kwargs["expected_chunk_count"])
        self.assertEqual(60, kwargs["expected_movie_layer_count"])
        self.assertEqual(frozenset(), kwargs["expected_unreachable_names"])
        self.assertEqual(64, result["counts"]["events"])

    def test_document_and_writer_are_immutable_and_hash_bound(self) -> None:
        result = fake_result()
        renderer = {"renderer_state_1": {}, "renderer_state_3": {}}
        authority = MODULE._authority_document(result, renderer, [])
        self.assertEqual(MODULE.SCHEMA, authority["schema"])
        self.assertTrue(authority["assertions"]["no_authored_movie_layer_is_unreachable"])
        self.assertFalse(authority["assertions"]["source_media_modified"])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "v188"
            MODULE._write_checkpoint(authority, result, output)
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                {
                    "AC4902_OUTPUT_PROJECTION_AUTHORITY.json",
                    "MOVIELAYER_OUTPUT_PROJECTIONS.csv",
                    "README.md",
                    "ROLLBACK.ps1",
                },
                set(verification["outputs"]),
            )
            self.assertIn("events=64", verification["literal_result"])
            with self.assertRaisesRegex(FileExistsError, "immutable output already exists"):
                MODULE._write_checkpoint(authority, result, output)


if __name__ == "__main__":
    unittest.main()
