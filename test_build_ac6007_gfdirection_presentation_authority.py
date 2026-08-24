from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import build_ac6007_gfdirection_presentation_authority as MODULE
from tools.frida_runtime_probe.extract_jm_dgi_glyph_catalog import sha256_bytes


def string255(value: str) -> bytes:
    raw = value.encode("utf-8") + (b"\0" if value else b"")
    result = bytes([len(raw)]) + raw
    return result + b"\0" * ((-len(result)) % 4)


def single_parameter(
    parameter_id: int,
    value_type: int,
    value: int | float,
    *,
    keys: list[tuple[float, int, float]] | None = None,
) -> bytes:
    header = struct.pack("<iHBB", 5, parameter_id, value_type, 0) + string255("")
    keys = keys or []
    load = b"\0\0\0\0" + struct.pack("<i", len(keys))
    if keys:
        payload = b"".join(struct.pack("<fif", *key) for key in keys)
    else:
        payload = struct.pack("<i", value) if value_type == 1 else struct.pack("<f", value)
    return header + load + payload


def compound(parameter_id: int, values: tuple[float, float]) -> bytes:
    children = [single_parameter(1, 2, values[0]), single_parameter(2, 2, values[1])]
    return (
        struct.pack("<iHBB", 4, parameter_id, 4, 0)
        + string255("")
        + struct.pack("<i", 2)
        + b"".join(children)
    )


def z2d_node(name: str, *, keyed_opacity: bool = False) -> bytes:
    parameters = [
        single_parameter(9, 1, 1),
        compound(11, (0.0, 0.0)),
        single_parameter(14, 2, 0.0),
        compound(16, (1.0, 1.0)),
        single_parameter(
            19,
            2,
            1.0,
            keys=[(5.0, 1, 1.0), (8.0, 1, 0.0)] if keyed_opacity else None,
        ),
        compound(21, (0.0, 0.0)),
    ]
    return (
        struct.pack("<i", 20)
        + string255(name)
        + b"12345678"
        + struct.pack("<iiII", -1, -1, 1, 2)
        + string255("")
        + bytes([0, 1, 0, 0])
        + struct.pack("<iii", 0, len(parameters), 1)
        + b"".join(parameters)
    )


def record(name: str, *, keyed_opacity: bool = False) -> bytes:
    body = z2d_node(name, keyed_opacity=keyed_opacity)
    return b"GDB\x03" + struct.pack("<I", len(body)) + body


def layer_node(name: str, child: dict, hash_words: tuple[int, int] = (11, 22)) -> dict:
    return {
        "type": 38,
        "name": name,
        "hash_low": hash_words[0],
        "hash_high": hash_words[1],
        "children": [{"type": 8, "name": "2DLayer", "children": [child]}],
    }


def z2d_runtime(name: str, start: int, end: int) -> dict:
    return {
        "type": 20,
        "name": name,
        "motions": [
            {
                "is_z2d_motion": True,
                "keys": [
                    {"index": 0, "floats": [start, end, start, end, start, end, -1], "flags": [0, 3, 1]}
                ],
            }
        ],
        "children": [],
    }


class Ac6007PresentationAuthorityTests(unittest.TestCase):
    def _build(self, *, bad_layer_hash: bool = False) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = root / "records"
            records.mkdir()
            primary_data = record("base.z2d")
            extension_data = record("win.z2d", keyed_opacity=True)
            (records / "ac6007_007.gdb3.bin").write_bytes(primary_data)
            (records / "ac8000_001.gdb3.bin").write_bytes(extension_data)
            binary = {"inherited_sha256": MODULE.SLOT_BINARY_SHA256}
            scene = {
                "status": "passed_code_exact",
                "binary": binary,
                "group": {
                    "name": "ac6007",
                    "compiled_index": 174,
                    "type2_presentations": [
                        {
                            "name": "ac6007_007",
                            "presentation_frame_count": 260,
                            "sha256": "A" * 64,
                            "scene_references": [
                                {
                                    "target_name": "ac6007_007",
                                    "instance_offset_frames": 0,
                                    "target_frame_count": 260,
                                }
                            ],
                        },
                        {
                            "name": "WIN_tanki",
                            "presentation_frame_count": 415,
                            "sha256": "B" * 64,
                            "scene_references": [
                                {
                                    "target_name": "ac8000_001",
                                    "instance_offset_frames": 155,
                                    "target_frame_count": 260,
                                }
                            ],
                        },
                    ],
                    "type3_records": [
                        {"name": "ac6007_007", "sha256": sha256_bytes(primary_data)},
                        {"name": "ac8000_001", "sha256": sha256_bytes(extension_data)},
                    ],
                },
            }
            gdp = {
                "status": "passed_code_exact",
                "binary": binary,
                "project": {
                    "layers": [
                        {
                            "index": 22,
                            "name": "全画面",
                            "hash_words": [11, 99 if bad_layer_hash else 22],
                            "render_buffer_target": 0,
                            "effective_viewport": {
                                "left": 0,
                                "top": 0,
                                "width": 1280,
                                "height": 1024,
                                "source": "TARGET_RENDERBUFFER_FALLBACK",
                            },
                        }
                    ]
                },
            }
            runtime = {
                "events": {
                    "ac6007_007": {
                        "scenes": [
                            {
                                "name": "ac6007_007",
                                "cuts": [
                                    {
                                        "cut_name": "ac6007_007",
                                        "instance_offset_frames": 0,
                                        "cut_start_frame": 0,
                                        "cut_end_frame": 259,
                                        "nodes": [layer_node("全画面", z2d_runtime("base.z2d", 0, 34))],
                                    }
                                ],
                            },
                            {
                                "name": "WIN_tanki",
                                "cuts": [
                                    {
                                        "cut_name": "ac8000_001",
                                        "instance_offset_frames": 155,
                                        "cut_start_frame": 0,
                                        "cut_end_frame": 259,
                                        "nodes": [layer_node("全画面", z2d_runtime("win.z2d", 0, 259))],
                                    }
                                ],
                            },
                        ]
                    }
                }
            }
            paths = {}
            for name, value in (("scene", scene), ("gdp", gdp), ("runtime", runtime)):
                path = root / f"{name}.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                paths[name] = path
            return MODULE.build_authority(
                scene_group_path=paths["scene"],
                gdp_path=paths["gdp"],
                runtime_scene_path=paths["runtime"],
                type3_records_dir=records,
                expected_event_ids=("ac6007_007",),
            )

    def test_selects_extension_presentation_and_offsets_keyed_values(self) -> None:
        result = self._build()
        event = result["events"][0]
        self.assertEqual("WIN_tanki", event["selected_presentation_name"])
        self.assertEqual(415, event["presentation_frame_count"])
        extension = event["scenes"][1]["cuts"][0]["z2d_nodes"][0]
        self.assertEqual("keyed", extension["transform"]["opacity"]["mode"])
        self.assertEqual(
            [160.0, 163.0],
            [row["event_global_time_frames"] for row in extension["transform"]["opacity"]["keys"]],
        )
        self.assertEqual(155, extension["motion_keys"][0]["event_global_start_frame"])
        self.assertEqual(414, extension["motion_keys"][0]["event_global_end_frame_inclusive"])

    def test_rejects_runtime_gdp_layer_hash_mismatch(self) -> None:
        with self.assertRaisesRegex(MODULE.PresentationAuthorityError, "layer hash differs"):
            self._build(bad_layer_hash=True)


if __name__ == "__main__":
    unittest.main()
