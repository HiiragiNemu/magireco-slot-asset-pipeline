from __future__ import annotations

import unittest

from tools.frida_runtime_probe.build_ac0908_016_event_composition_authority import (
    CompositionError,
    derive_center_crop,
    static_transform,
)


def _scalar(parameter_id: int, value: float | int) -> dict:
    return {"parameter_id": parameter_id, "static_value": value}


def _compound(parameter_id: int, x: float, y: float) -> dict:
    return {
        "parameter_id": parameter_id,
        "components": [
            {"parameter_id": 1, "static_value": x},
            {"parameter_id": 2, "static_value": y},
        ],
    }


def _exact_node() -> dict:
    return {
        "name": "cap0908_banbanzai_tur_012.z2d",
        "resource_index": -1,
        "motion_count": 1,
        "node_flags": [0, 1, 0],
        "parameters": [
            _scalar(9, 1),
            _compound(11, 0.0, 0.0),
            _scalar(14, 0.0),
            _compound(16, 1.0, 1.0),
            _scalar(19, 1.0),
            _compound(21, 0.0, 0.0),
        ],
    }


class Ac0908016EventCompositionAuthorityTests(unittest.TestCase):
    def test_exact_center_crop_maps_virtual_render_to_movie_viewport(self) -> None:
        self.assertEqual(
            derive_center_crop(1280, 1024, 1024, 576),
            (128, 224, 1152, 800),
        )

    def test_exact_static_transform_is_accepted(self) -> None:
        self.assertEqual(
            static_transform(_exact_node()),
            {
                "enabled": 1,
                "translation": [0.0, 0.0],
                "rotation_degrees": 0.0,
                "scale": [1.0, 1.0],
                "opacity": 1.0,
                "anchor_offset": [0.0, 0.0],
            },
        )

    def test_nonidentity_scale_fails_closed(self) -> None:
        node = _exact_node()
        node["parameters"][3] = _compound(16, 0.5, 0.5)
        with self.assertRaisesRegex(CompositionError, "static transform differs"):
            static_transform(node)

    def test_nonintegral_crop_origin_fails_closed(self) -> None:
        with self.assertRaisesRegex(CompositionError, "non-integral"):
            derive_center_crop(1281, 1024, 1024, 576)


if __name__ == "__main__":
    unittest.main()
