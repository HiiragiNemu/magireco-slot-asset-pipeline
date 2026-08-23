from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parent / "tools" / "frida_runtime_probe" / "extract_cri_movie_runtime_render_authority.py"
SPEC = importlib.util.spec_from_file_location("extract_cri_movie_runtime_render_authority", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CriMovieRuntimeRenderAuthorityTests(unittest.TestCase):
    def test_exact_instruction_requirement_is_fail_closed(self) -> None:
        row = {"address": "0x1", "mnemonic": "mov", "operands": "w1, #-1"}
        MODULE._require_instruction(row, "mov", ("w1", "#-1"))
        with self.assertRaisesRegex(MODULE.CriMovieRuntimeAuthorityError, "operands changed"):
            MODULE._require_instruction(row, "mov", ("w1", "#1"))

    def test_premia_probe_records_runtime_audio_suppression(self) -> None:
        probe = {
            "streams": [
                {"index": 0, "codec_type": "video"},
                {"index": 1, "codec_type": "video"},
                {"index": 2, "codec_type": "audio", "codec_name": "adpcm_adx", "sample_rate": "48000", "channels": 2, "duration": "2.0"},
            ]
        }
        row = MODULE.validate_premia_probe("ac8040_premia_EF", Path("sample.usm"), probe)
        self.assertEqual(row["runtime_playback"], "DISABLED_BY_CRIMANA_AUDIO_TRACK_OFF")
        self.assertEqual(row["embedded_audio_stream_index"], 2)

    def test_premia_probe_rejects_missing_embedded_audio(self) -> None:
        probe = {"streams": [{"index": 0, "codec_type": "video"}, {"index": 1, "codec_type": "video"}]}
        with self.assertRaisesRegex(MODULE.CriMovieRuntimeAuthorityError, "expected two video"):
            MODULE.validate_premia_probe("ac8040_premia_EF", Path("sample.usm"), probe)

    def test_movie_layers_require_exact_default_geometry(self) -> None:
        layer = {
            "layer_flags_hex": "0x077e",
            "layer_layout": "flags_0x400_default_blend",
            "position": [512.0, 288.0],
            "pivot": [512.0, 288.0],
            "layer_width": 1024,
            "layer_height": 576,
        }
        authority = {"status": "passed", "z2d_chunks": [{"movie_layers": [dict(layer)]} for _ in range(13)]}
        authority["z2d_chunks"][0]["movie_layers"][0].update(
            {"layer_flags_hex": "0x037e", "layer_layout": "explicit_uint32_blend_enum"}
        )
        result = MODULE.validate_movie_layers(authority)
        self.assertEqual(result["selected_movie_layer_count"], 13)
        self.assertFalse(result["authored_horizontal_flip"])
        authority["z2d_chunks"][0]["movie_layers"][0]["position"] = [0.0, 0.0]
        with self.assertRaisesRegex(MODULE.CriMovieRuntimeAuthorityError, "transform changed"):
            MODULE.validate_movie_layers(authority)

    def test_contract_constants_are_precise(self) -> None:
        self.assertEqual(MODULE.PREMIA_USMS, ("ac8040_premia_EF", "ac8040_premia_EF_LP"))
        self.assertIn("group__MDL__MANALIB__PLAYER", MODULE.OFFICIAL_CRI_API_URL)


if __name__ == "__main__":
    unittest.main()
