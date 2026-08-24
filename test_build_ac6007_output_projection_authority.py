import unittest

from tools.frida_runtime_probe.build_ac6007_output_projection_authority import (
    ProjectionError,
    contain_rect,
    event_projection,
    source_projection,
)


class Ac6007OutputProjectionAuthorityTests(unittest.TestCase):
    def test_full_renderbuffer_contains_without_pixel_loss(self):
        self.assertEqual(
            contain_rect(1280, 1024, 416, 232),
            {
                "source_canvas": [1280, 1024],
                "target_canvas": [416, 232],
                "content_rect_xywh": [63, 0, 290, 232],
                "content_rect_ltrb": [63, 0, 353, 232],
                "scale_fraction": "29/128",
                "scale": 29 / 128,
                "bars": {"left": 63, "top": 0, "right": 63, "bottom": 0},
            },
        )

    def test_normal_surface_uses_gdp_top_zero_not_generic_center_crop(self):
        projection = event_projection(
            "ac6007_002",
            [1024, 576],
            {"left": 128, "top": 0, "width": 1024, "height": 576},
        )
        self.assertEqual(projection["runtime_renderbuffer_crop_ltrb"], [128, 0, 1152, 576])
        self.assertEqual(projection["output_content_rect_xywh"], [0, 0, 416, 232])
        self.assertEqual(projection["primary_cri_policy"], "NATIVE_416X232_PASSTHROUGH")

    def test_full_surface_uses_bounded_contain_projection(self):
        projection = event_projection(
            "ac6007_009",
            [1280, 1024],
            {"left": 0, "top": 0, "width": 1280, "height": 1024},
        )
        self.assertEqual(projection["output_content_rect_xywh"], [63, 0, 290, 232])
        self.assertFalse(projection["pixel_loss_within_selected_surface"])
        source = source_projection(512, 416, projection)
        self.assertEqual(source["scale_x_fraction"], "145/256")
        self.assertEqual(source["scale_y_fraction"], "29/52")
        self.assertFalse(source["editorial_upscale"])

    def test_runtime_authored_208_component_scale_is_explicit(self):
        projection = event_projection(
            "ac6007_004",
            [1024, 576],
            {"left": 128, "top": 0, "width": 1024, "height": 576},
        )
        source = source_projection(208, 120, projection)
        self.assertEqual(source["scale_x_fraction"], "2/1")
        self.assertEqual(source["scale_y_fraction"], "29/15")
        self.assertTrue(source["editorial_upscale"])

    def test_wrong_normal_viewport_fails_closed(self):
        with self.assertRaisesRegex(ProjectionError, "normal-surface geometry differs"):
            event_projection(
                "ac6007_001",
                [1024, 576],
                {"left": 128, "top": 224, "width": 1024, "height": 576},
            )


if __name__ == "__main__":
    unittest.main()
