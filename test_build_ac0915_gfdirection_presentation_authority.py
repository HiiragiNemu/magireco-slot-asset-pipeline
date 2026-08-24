from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import (
    build_ac0915_gfdirection_presentation_authority as MODULE,
)
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
        payload = (
            struct.pack("<i", value)
            if value_type == 1
            else struct.pack("<f", value)
        )
    return header + load + payload


def compound(parameter_id: int, values: tuple[float, float]) -> bytes:
    children = [
        single_parameter(1, 2, values[0]),
        single_parameter(2, 2, values[1]),
    ]
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
            keys=[(1.0, 1, 1.0), (4.0, 1, 0.0)] if keyed_opacity else None,
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


def record(*names: str, keyed_name: str | None = None) -> bytes:
    body = b"".join(
        z2d_node(name, keyed_opacity=name == keyed_name) for name in names
    )
    return b"GDB\x03" + struct.pack("<I", len(body)) + body


def runtime_z2d(name: str, start: int, end: int) -> dict:
    return {
        "type": 20,
        "name": name,
        "motions": [
            {
                "is_z2d_motion": True,
                "keys": [
                    {
                        "index": 0,
                        "floats": [start, end, start, end, start, end, -1],
                        "flags": [0, 3, 1],
                    }
                ],
            }
        ],
        "children": [],
    }


def runtime_layer(
    *nodes: dict, hash_words: tuple[int, int] = (111, 222)
) -> dict:
    return {
        "type": 38,
        "name": "mojibake-runtime-label",
        "hash_low": hash_words[0],
        "hash_high": hash_words[1],
        "children": [{"type": 8, "name": "2DLayer", "children": list(nodes)}],
    }


class Ac0915PresentationAuthorityTests(unittest.TestCase):
    def _build(self, *, bad_layer_hash: bool = False) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = root / "records"
            records.mkdir()
            primary = record("main.z2d")
            overlay = record(
                "effect.z2d", "counter_symbol", keyed_name="effect.z2d"
            )
            (records / "main_cut.gdb3.bin").write_bytes(primary)
            (records / "overlay_cut.gdb3.bin").write_bytes(overlay)
            binary = {"inherited_sha256": MODULE.SLOT_BINARY_SHA256}
            scene = {
                "status": "passed_code_exact",
                "binary": binary,
                "group": {
                    "name": "ac0915",
                    "compiled_index": 40,
                    "type2_presentations": [
                        {
                            "name": "main_scene",
                            "presentation_frame_count": 4,
                            "sha256": "A" * 64,
                            "scene_references": [
                                {
                                    "target_name": "main_cut",
                                    "instance_offset_frames": 0,
                                    "target_frame_count": 4,
                                }
                            ],
                        },
                        {
                            "name": "overlay_scene",
                            "presentation_frame_count": 6,
                            "sha256": "B" * 64,
                            "scene_references": [
                                {
                                    "target_name": "overlay_cut",
                                    "instance_offset_frames": 0,
                                    "target_frame_count": 6,
                                }
                            ],
                        },
                    ],
                    "type3_records": [
                        {"name": "main_cut", "sha256": sha256_bytes(primary)},
                        {
                            "name": "overlay_cut",
                            "sha256": sha256_bytes(overlay),
                        },
                    ],
                },
            }
            gdp = {
                "status": "passed_code_exact",
                "binary": binary,
                "project": {
                    "layers": [
                        {
                            "index": 5,
                            "name": "通常画面",
                            "hash_words": [111, 999 if bad_layer_hash else 222],
                            "render_buffer_target": 0,
                            "effective_viewport": {
                                "left": 128,
                                "top": 0,
                                "width": 1024,
                                "height": 576,
                                "source": "EXPLICIT_LEFT_TOP_RIGHT_BOTTOM",
                            },
                        }
                    ]
                },
            }
            runtime = {
                "events": {
                    "ac0915_001": {
                        "scenes": [
                            {
                                "name": "main_scene",
                                "cuts": [
                                    {
                                        "cut_name": "main_cut",
                                        "instance_offset_frames": 0,
                                        "cut_start_frame": 0,
                                        "cut_end_frame": 3,
                                        "nodes": [
                                            runtime_layer(runtime_z2d("main.z2d", 0, 3))
                                        ],
                                    }
                                ],
                            },
                            {
                                "name": "overlay_scene",
                                "cuts": [
                                    {
                                        "cut_name": "overlay_cut",
                                        "instance_offset_frames": 0,
                                        "cut_start_frame": 0,
                                        "cut_end_frame": 5,
                                        "nodes": [
                                            runtime_layer(
                                                runtime_z2d("effect.z2d", 1, 5),
                                                runtime_z2d("counter_symbol", 0, 5),
                                            )
                                        ],
                                    }
                                ],
                            },
                        ]
                    }
                }
            }
            parent = {
                "status": "PASSED",
                "exact_binary": binary,
                "exact_archive_z2d_names": ["main", "effect"],
                "runtime_only_type20_names": ["counter_symbol"],
            }
            paths = {}
            for name, value in (
                ("scene", scene),
                ("gdp", gdp),
                ("runtime", runtime),
                ("parent", parent),
            ):
                path = root / f"{name}.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                paths[name] = path
            return MODULE.build_authority(
                scene_group_path=paths["scene"],
                gdp_path=paths["gdp"],
                runtime_scene_path=paths["runtime"],
                type3_records_dir=records,
                parent_z2d_authority_path=paths["parent"],
                expected_event_ids=("ac0915_001",),
                expected_event_frames={"ac0915_001": 6},
                expected_counts={
                    "event_count": 1,
                    "scene_instance_count": 2,
                    "cut_count": 2,
                    "z2d_node_occurrence_count": 3,
                    "unique_z2d_node_count": 3,
                    "archive_backed_z2d_occurrence_count": 2,
                    "unique_archive_backed_z2d_count": 2,
                    "runtime_symbolic_z2d_occurrence_count": 1,
                    "unique_runtime_symbolic_z2d_count": 1,
                },
            )

    def test_preserves_parallel_presentations_and_resolves_layer_by_hash(self) -> None:
        result = self._build()
        event = result["events"][0]
        self.assertEqual(6, event["presentation_frame_count"])
        self.assertEqual(2, event["parallel_scene_count"])
        self.assertEqual([0, 0], [row["event_global_start_frame"] for row in event["scenes"]])
        nodes = [
            node
            for scene in event["scenes"]
            for cut in scene["cuts"]
            for node in cut["z2d_nodes"]
        ]
        self.assertEqual({"通常画面"}, {row["owning_layer"]["canonical_name"] for row in nodes})
        self.assertEqual(
            "runtime_symbolic_counter_overlay", nodes[-1]["node_authority_class"]
        )
        self.assertEqual("keyed", nodes[1]["transform"]["opacity"]["mode"])
        self.assertEqual(1, result["summary"]["keyed_parameter_occurrence_count"])

    def test_rejects_runtime_layer_hash_absent_from_gdp(self) -> None:
        with self.assertRaisesRegex(
            MODULE.PresentationAuthorityError, "GDP lacks owning layer hash"
        ):
            self._build(bad_layer_hash=True)

    def test_write_outputs_is_immutable_and_hash_binds_all_roles(self) -> None:
        authority = self._build()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "v178"
            MODULE.write_outputs(authority, output)
            verification = json.loads(
                (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
            )
            self.assertEqual("passed", verification["status"])
            self.assertEqual(
                {
                    "AC0915_GFDIRECTION_PRESENTATION_AUTHORITY.json",
                    "PRESENTATION_Z2D_NODES.csv",
                    "README.md",
                    "ROLLBACK.ps1",
                },
                set(verification["outputs"]),
            )
            with self.assertRaisesRegex(
                MODULE.PresentationAuthorityError, "immutable output already exists"
            ):
                MODULE.write_outputs(authority, output)


if __name__ == "__main__":
    unittest.main()
