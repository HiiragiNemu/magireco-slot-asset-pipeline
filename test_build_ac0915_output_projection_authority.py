from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac0915_output_projection_authority as MODULE


def identity_transform() -> dict:
    return {
        "enabled": 1,
        "translation": [0.0, 0.0],
        "rotation_degrees": {"mode": "static", "value": 0.0},
        "scale": [1.0, 1.0],
        "opacity": {"mode": "static", "value": 1.0},
        "anchor_offset": [0.0, 0.0],
    }


def node(
    name: str,
    *,
    node_class: str = "exact_apk_z2d",
    layer_index: int = 5,
    viewport: tuple[int, int, int, int] = (128, 0, 1024, 576),
) -> dict:
    left, top, width, height = viewport
    return {
        "z2d_node": name,
        "normalised_z2d_name": name.removesuffix(".z2d"),
        "node_authority_class": node_class,
        "owning_layer": {
            "canonical_name": f"layer-{layer_index}",
            "index": layer_index,
            "hash_words": [layer_index, layer_index + 1],
            "effective_viewport": {
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            },
        },
        "transform": identity_transform(),
        "motion_keys": [
            {
                "event_global_start_frame": 0,
                "event_global_end_frame_inclusive": 5,
            }
        ],
    }


def layer(
    source: str,
    *,
    width: int,
    height: int,
    state: int,
    disposition: str = "LOADABLE_BY_EXACT_NAME",
    tag_index: int = 0,
) -> dict:
    return {
        "movie_layer_tag_value_hex": f"0x{0x50000000 | tag_index:08x}",
        "authored_blend_enum": 0 if state == 1 else 2,
        "effective_renderer_state": state,
        "start_frame": 0,
        "end_frame_inclusive": 5,
        "frame_count": 6,
        "position": [width / 2, height / 2],
        "pivot": [width / 2, height / 2],
        "layer_width": width,
        "layer_height": height,
        "cri_lookup_base_name": source,
        "runtime_load_disposition": disposition,
    }


class Ac0915OutputProjectionTests(unittest.TestCase):
    def _fixture(self) -> tuple[dict, dict, dict, dict, dict, dict]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        base_path = root / "base.usm"
        effect_path = root / "effect.usm"
        base_path.write_bytes(b"base-source")
        effect_path.write_bytes(b"effect-source")
        presentation = {
            "schema": "magireco-ac0915-gfdirection-presentation-authority-v1",
            "status": "passed_code_runtime_cross_bound_projection_pending",
            "summary": {"event_count": 1, "z2d_node_occurrence_count": 4},
            "events": [
                {
                    "event_id": "ac0915_001",
                    "presentation_frame_count": 6,
                    "scenes": [
                        {
                            "name": "scene",
                            "cuts": [
                                {
                                    "cut_name": "cut",
                                    "z2d_nodes": [
                                        node("base.z2d"),
                                        node(
                                            "caption.z2d",
                                            layer_index=35,
                                            viewport=(0, 0, 1280, 1024),
                                        ),
                                        node(
                                            "effect.z2d",
                                            layer_index=47,
                                            viewport=(0, 0, 1280, 1024),
                                        ),
                                        node(
                                            "counter_symbol",
                                            node_class="runtime_symbolic_counter_overlay",
                                        ),
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        movie = {
            "schema": "magireco-z2d-movielayer-reachability-authority-v1",
            "status": "passed",
            "counts": {
                "z2d_chunks": 3,
                "movie_layers": 3,
                "loadable_movie_layers": 2,
                "unreachable_movie_layers": 1,
            },
            "z2d_chunks": [
                {
                    "name": "base",
                    "header": {"canvas_width": 1024, "canvas_height": 576},
                    "movie_layers": [
                        layer("base_source", width=1024, height=576, state=1)
                    ],
                },
                {
                    "name": "caption",
                    "header": {"canvas_width": 1280, "canvas_height": 1024},
                    "movie_layers": [],
                },
                {
                    "name": "effect",
                    "header": {"canvas_width": 1280, "canvas_height": 1024},
                    "movie_layers": [
                        layer("effect_source", width=1280, height=1024, state=3),
                        layer(
                            "missing_add",
                            width=1280,
                            height=1024,
                            state=3,
                            disposition="UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE",
                            tag_index=1,
                        ),
                    ],
                },
            ],
        }
        artifacts = []
        for index, (name, path, width, height) in enumerate(
            (
                ("base_source", base_path, 416, 232),
                ("effect_source", effect_path, 512, 416),
            )
        ):
            artifacts.append(
                {
                    "official_name": name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "global_index": 100 + index,
                    "package": "main",
                    "package_index": 100 + index,
                    "width": width,
                    "height": height,
                    "frame_rate": "30/1",
                    "frame_count": 6,
                    "color_stream_index": 0,
                    "alpha_stream_index": 1,
                }
            )
        cri = {
            "schema": "magireco-selected-cri-usm-argb-authority-v1",
            "status": "passed_exact_color_alpha_streams_resolved",
            "counts": {"selected_usm_count": 2},
            "assertions": {
                "all_selected_usms_have_exact_color_and_alpha_video_streams": True
            },
            "artifacts": artifacts,
        }
        project = {
            "schema": "magireco-gfdirection-project-viewport-authority-v1",
            "status": "passed_code_exact",
            "project": {"render_buffer_sets": [{"width": 1280, "height": 1024}]},
        }
        renderer = {
            "renderer_state_1": {
                "rgb": "src_rgb*src_alpha + dst_rgb*(1-src_alpha)",
                "gl_blend_func_separate": [770, 771, 1, 771],
                "equation": 32774,
            },
            "renderer_state_3": {
                "rgb": "src_rgb*src_alpha + dst_rgb",
                "gl_blend_func_separate": [770, 1, 1, 1],
                "equation": 32774,
            },
        }
        expected = {
            "events": 1,
            "archive_backed_z2d_occurrences": 3,
            "movie_bearing_z2d_occurrences": 2,
            "non_movie_text_z2d_occurrences": 1,
            "runtime_symbolic_node_occurrences": 1,
            "loadable_movie_layer_occurrences": 2,
            "unique_loadable_cri_sources": 2,
            "unreachable_movie_layer_occurrences": 1,
            "unique_unreachable_movie_layer_names": 1,
            "renderer_state_1_occurrences": 1,
            "renderer_state_3_occurrences": 1,
            "authored_tail_trim_occurrences": 0,
        }
        return presentation, movie, cri, project, renderer, expected

    def _resolve(self, fixture: tuple[dict, dict, dict, dict, dict, dict]) -> dict:
        presentation, movie, cri, project, renderer, expected = fixture
        return MODULE.resolve(
            presentation,
            movie,
            cri,
            project,
            renderer,
            expected_events=("ac0915_001",),
            expected_counts=expected,
            expected_chunk_count=3,
            expected_movie_layer_count=3,
            expected_unique_loadable_layer_count=2,
            expected_unique_unreachable_layer_count=1,
            expected_state3_names=frozenset({"effect_source"}),
            expected_unreachable_names=frozenset({"missing_add"}),
        )

    def test_composes_full_overlay_before_normal_crop_and_uses_addition(self) -> None:
        result = self._resolve(self._fixture())
        event = result["events"][0]
        layers = event["layers_in_render_pass_order_under_to_top"]
        self.assertEqual(["base_source", "effect_source"], [row["source_name"] for row in layers])
        self.assertEqual([0, 0, 416, 232], layers[1]["output_rect_xywh"])
        self.assertEqual([0, 0, 1280, 1024], layers[1]["virtual_layer_rect_ltrb"])
        self.assertEqual(
            "src_rgb*src_alpha + dst_rgb", layers[1]["renderer_contract"]["rgb"]
        )
        self.assertEqual(1, event["non_movie_text_z2d_occurrences"])
        self.assertEqual(1, event["runtime_symbolic_node_occurrences"])

    def test_rejects_nonidentity_archive_z2d_transform(self) -> None:
        fixture = self._fixture()
        fixture[0]["events"][0]["scenes"][0]["cuts"][0]["z2d_nodes"][0][
            "transform"
        ]["scale"] = [2.0, 1.0]
        with self.assertRaisesRegex(MODULE.ProjectionError, "transform is not identity"):
            self._resolve(fixture)

    def test_tail_trim_is_exactly_bounded(self) -> None:
        self.assertEqual(
            11,
            MODULE._frame_policy("ac0915_007_c10", 211, 200)[
                "discarded_unreferenced_tail_frames"
            ],
        )
        with self.assertRaisesRegex(MODULE.ProjectionError, "frame span differs"):
            MODULE._frame_policy("unknown", 7, 6)

    def test_accepts_explicit_family_presentation_schema(self) -> None:
        fixture = self._fixture()
        fixture[0]["schema"] = "magireco-ac4902-gfdirection-presentation-authority-v1"
        presentation, movie, cri, project, renderer, expected = fixture
        result = MODULE.resolve(
            presentation,
            movie,
            cri,
            project,
            renderer,
            expected_events=("ac0915_001",),
            expected_presentation_schema=(
                "magireco-ac4902-gfdirection-presentation-authority-v1"
            ),
            family_label="ac4902",
            expected_counts=expected,
            expected_chunk_count=3,
            expected_movie_layer_count=3,
            expected_unique_loadable_layer_count=2,
            expected_unique_unreachable_layer_count=1,
            expected_state3_names=frozenset({"effect_source"}),
            expected_unreachable_names=frozenset({"missing_add"}),
        )
        self.assertEqual(1, result["counts"]["events"])

    def test_partial_only_event_requires_exact_route_underlay_allowance(self) -> None:
        fixture = self._fixture()
        presentation, movie, cri, project, renderer, expected = fixture
        base_layer = movie["z2d_chunks"][0]["movie_layers"][0]
        base_layer.update(
            {
                "position": [640.0, 467.0],
                "pivot": [640.0, 360.0],
                "layer_width": 1280,
                "layer_height": 720,
            }
        )
        movie["z2d_chunks"][0]["header"] = {
            "canvas_width": 1280,
            "canvas_height": 1024,
        }
        presentation["events"][0]["scenes"][0]["cuts"][0]["z2d_nodes"][0][
            "owning_layer"
        ]["effective_viewport"] = {
            "left": 0,
            "top": 0,
            "width": 1280,
            "height": 1024,
        }
        movie["z2d_chunks"][2]["movie_layers"][0][
            "runtime_load_disposition"
        ] = "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"
        movie["counts"]["loadable_movie_layers"] = 1
        movie["counts"]["unreachable_movie_layers"] = 2
        cri["artifacts"] = [cri["artifacts"][0]]
        cri["counts"]["selected_usm_count"] = 1
        expected.update(
            {
                "loadable_movie_layer_occurrences": 1,
                "unique_loadable_cri_sources": 1,
                "unreachable_movie_layer_occurrences": 2,
                "unique_unreachable_movie_layer_names": 2,
                "renderer_state_3_occurrences": 0,
                "partial_viewport_movie_layer_occurrences": 1,
                "prior_underlay_required_events": 1,
            }
        )
        with self.assertRaisesRegex(
            MODULE.ProjectionError, "does not cover the exact physical viewport"
        ):
            MODULE.resolve(
                presentation,
                movie,
                cri,
                project,
                renderer,
                expected_events=("ac0915_001",),
                expected_counts=expected,
                expected_chunk_count=3,
                expected_movie_layer_count=3,
                expected_unique_loadable_layer_count=1,
                expected_unique_unreachable_layer_count=2,
                expected_state3_names=frozenset(),
                expected_unreachable_names=frozenset(
                    {"effect_source", "missing_add"}
                ),
            )
        result = MODULE.resolve(
            presentation,
            movie,
            cri,
            project,
            renderer,
            expected_events=("ac0915_001",),
            expected_counts=expected,
            expected_chunk_count=3,
            expected_movie_layer_count=3,
            expected_unique_loadable_layer_count=1,
            expected_unique_unreachable_layer_count=2,
            expected_state3_names=frozenset(),
            expected_unreachable_names=frozenset(
                {"effect_source", "missing_add"}
            ),
            allowed_partial_viewport_events=frozenset({"ac0915_001"}),
        )
        event = result["events"][0]
        self.assertTrue(event["requires_prior_frame_underlay"])
        self.assertFalse(event["has_full_viewport_movie_layer"])
        self.assertEqual(1, result["counts"]["prior_underlay_required_events"])


if __name__ == "__main__":
    unittest.main()
