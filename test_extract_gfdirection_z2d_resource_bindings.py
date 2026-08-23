from __future__ import annotations

import importlib.util
import struct
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parent
    / "tools"
    / "frida_runtime_probe"
    / "extract_gfdirection_z2d_resource_bindings.py"
)
SPEC = importlib.util.spec_from_file_location("extract_gfdirection_z2d_resource_bindings", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def string255(value: str) -> bytes:
    raw = value.encode("utf-8") + (b"\0" if value else b"")
    result = bytes([len(raw)]) + raw
    return result + b"\0" * ((-len(result)) % 4)


def single_parameter(parameter_id: int, value_type: int, value: int | float) -> bytes:
    header = struct.pack("<iHBB", 5, parameter_id, value_type, 0) + string255("")
    load = b"\0\0\0\0" + struct.pack("<i", 0)
    payload = struct.pack("<i", value) if value_type == 1 else struct.pack("<f", value)
    return header + load + payload


def compound_parameter(parameter_id: int, children: list[bytes]) -> bytes:
    return (
        struct.pack("<iHBB", 4, parameter_id, 4, 0)
        + string255("")
        + struct.pack("<i", len(children))
        + b"".join(children)
    )


def node(name: str, *, include_147: bool = False) -> bytes:
    parameters = [
        single_parameter(9, 1, 1),
        compound_parameter(11, [single_parameter(1, 2, 0.0), single_parameter(2, 2, 0.0)]),
        single_parameter(14, 2, 0.0),
        compound_parameter(16, [single_parameter(1, 2, 1.0), single_parameter(2, 2, 1.0)]),
        single_parameter(19, 2, 1.0),
        compound_parameter(21, [single_parameter(1, 2, 0.0), single_parameter(2, 2, 0.0)]),
    ]
    if include_147:
        parameters.append(single_parameter(147, 1, 0))
    return (
        struct.pack("<i", 20)
        + string255(name)
        + b"\x11\x22\x33\x44\x55\x66\x77\x88"
        + struct.pack("<iiII", -1, -1, 0, 0)
        + string255("")
        + bytes([0, 1, 0, 0])
        + struct.pack("<iii", 0, len(parameters), 1)
        + b"".join(parameters)
        + b"MOTION"
    )


class ResourceBindingParserTests(unittest.TestCase):
    def test_parses_target_node_and_nested_parameter_ids(self) -> None:
        data = b"PREFIX00" + node("ac0908_pre_c10.z2d")
        result = MODULE.parse_node(data, "ac0908_pre_c10.z2d")
        self.assertEqual([9, 11, 14, 16, 19, 21], result["top_level_parameter_ids"])
        self.assertEqual(-1, result["resource_index"])
        self.assertEqual(1, result["motion_count"])
        self.assertFalse(result["resource_override_parameter_147_present"])
        self.assertEqual([9, 11, 1, 2, 14, 16, 1, 2, 19, 21, 1, 2], result["all_parameter_ids_including_compound_children"])

    def test_detects_parameter_147(self) -> None:
        data = b"PREFIX00" + node("ac8040_premia_EF.z2d", include_147=True)
        result = MODULE.parse_node(data, "ac8040_premia_EF.z2d")
        self.assertTrue(result["resource_override_parameter_147_present"])

    def test_rejects_ambiguous_node_marker(self) -> None:
        value = node("ac8040_premia_EF.z2d")
        with self.assertRaisesRegex(MODULE.ParseError, "expected one"):
            MODULE.parse_node(value + value, "ac8040_premia_EF.z2d")

    def test_rejects_keyed_parameter(self) -> None:
        value = bytearray(single_parameter(9, 1, 1))
        # Header is 12 bytes for an empty String255; key_count follows four load bytes.
        struct.pack_into("<i", value, 16, 1)
        reader = MODULE.Reader(bytes(value), 0)
        with self.assertRaisesRegex(MODULE.ParseError, "keyed parameter"):
            MODULE.parse_parameter(reader)


if __name__ == "__main__":
    unittest.main()
