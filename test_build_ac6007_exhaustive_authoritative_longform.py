import unittest

from tools.frida_runtime_probe import build_ac6007_exhaustive_authoritative_longform as m


class Ac6007ExhaustiveLongformTests(unittest.TestCase):
    def test_layer_filter_uses_exact_projection_and_parent_start(self):
        parts, output = m.layer_filter_parts(
            0,
            0,
            {
                "source": {"frame_count": 60, "width": 320, "height": 256},
                "event_start_frame": 40,
                "event_end_frame_inclusive": 99,
                "effective_renderer_state": 1,
                "output_x": 63,
                "output_y": 0,
                "output_width": 290,
                "output_height": 232,
            },
            "base0",
        )
        value = ";".join(parts)
        self.assertIn("scale=290:232", value)
        self.assertIn("+40/30/TB", value)
        self.assertIn("overlay=63:0", value)
        self.assertEqual(output, "base1")

    def test_native_layer_avoids_unneeded_scale(self):
        parts, _ = m.layer_filter_parts(
            0,
            0,
            {
                "source": {"frame_count": 30, "width": 416, "height": 232},
                "event_start_frame": 0,
                "event_end_frame_inclusive": 29,
                "effective_renderer_state": 1,
                "output_x": 0,
                "output_y": 0,
                "output_width": 416,
                "output_height": 232,
            },
            "base0",
        )
        self.assertNotIn("scale=", ";".join(parts))

    def test_ass_time_rounds_to_centiseconds(self):
        self.assertEqual(m._ass_time(100_533), "0:01:40.53")


if __name__ == "__main__":
    unittest.main()
