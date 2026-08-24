from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.frida_runtime_probe import build_ac4901_output_projection_authority as MODULE


def fake_result() -> dict:
    source = {
        "sha256": "A" * 64,
        "width": 416,
        "height": 232,
        "frame_count": 6,
    }
    occurrence = {
        "event": "ac4901_001",
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
        "renderer_contract": {"rgb": "source-over"},
        "virtual_layer_rect_ltrb": [128, 0, 1152, 576],
        "runtime_authored_component_scaling": False,
    }
    return {
        "events": [{"event": "ac4901_001"}],
        "occurrences": [occurrence],
        "counts": dict(MODULE.EXPECTED_COUNTS),
        "runtime_authored_component_scale_sources": [],
    }


class Ac4901OutputProjectionTests(unittest.TestCase):
    def test_exact_contract_counts_and_event_set(self) -> None:
        self.assertEqual(205, len(MODULE.EVENT_IDS))
        self.assertEqual(591, MODULE.EXPECTED_COUNTS["loadable_movie_layer_occurrences"])
        self.assertEqual(194, MODULE.EXPECTED_COUNTS["unique_loadable_cri_sources"])
        self.assertEqual(frozenset({"ac4901_091"}), MODULE.PRIOR_UNDERLAY_EVENTS)

    def test_resolver_passes_component_aware_contract(self) -> None:
        with mock.patch.object(MODULE, "resolve", return_value=fake_result()) as resolver:
            result = MODULE.resolve_ac4901({}, {}, {}, {}, {})
        kwargs = resolver.call_args.kwargs
        self.assertEqual(MODULE.EVENT_IDS, kwargs["expected_events"])
        self.assertEqual(MODULE.EXPECTED_COUNTS, kwargs["expected_counts"])
        self.assertEqual(103, kwargs["expected_chunk_count"])
        self.assertEqual(194, kwargs["expected_movie_layer_count"])
        self.assertEqual(
            frozenset({"ac4901_091"}), kwargs["allowed_partial_viewport_events"]
        )
        self.assertEqual(205, result["counts"]["events"])

    def test_document_and_writer_preserve_route_underlay_gate(self) -> None:
        result = fake_result()
        renderer = {"renderer_state_1": {}, "renderer_state_3": {}}
        authority = MODULE._authority_document(result, renderer, [])
        self.assertTrue(
            authority["assertions"]["only_ac4901_091_requires_prior_frame_underlay"]
        )
        self.assertTrue(
            authority["projection_policy"][
                "ac4901_091_partial_button_layers_require_route_prior_frame_underlay"
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "v198"
            MODULE._write_checkpoint(authority, result, output)
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertIn("prior_underlay_events=1", verification["literal_result"])
            self.assertEqual(4, len(verification["output_byte_counts"]))
            with self.assertRaisesRegex(FileExistsError, "immutable output already exists"):
                MODULE._write_checkpoint(authority, result, output)


if __name__ == "__main__":
    unittest.main()
