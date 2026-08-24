#!/usr/bin/env python3
"""Extract fail-closed Z2D resource-binding evidence from one GFDirection record.

This parser is intentionally narrow.  It decodes the exact packed node and
parameter layout used by the ac0908_016 type-3 GDB record and rejects keyed or
otherwise unsupported parameter payloads instead of guessing their size.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SLOT_BINARY_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
TARGET_NODES = ("ac0908_pre_c10.z2d", "ac8040_premia_EF.z2d")
EXPECTED_PARAMETER_IDS = (9, 11, 14, 16, 19, 21)
RESOURCE_OVERRIDE_PARAMETER_ID = 147

CODE_AUTHORITY = (
    ("0x42b0374", "zg::CGFDirectionNodeLayer::Load", "packed node header, child, parameter, and motion counts"),
    ("0x42ce710", "zg::CGFDirectionUnit::LoadNodeParameter", "parameter id and value-type dispatch"),
    ("0x42ba544", "zg::CGFDirectionNodeSingleParameter<CGFDirectionResourceBase*>::Load", "resource-index payload"),
    ("0x42bc378", "zg::CGFDirectionNodeSingleParameter<CGFDirectionResourceBase*>::LoadReference", "resource-index reference resolution"),
    ("0x42b38d4", "zg::CGFDirectionNodeMotionZ2D::LoadImages", "parameter 147 override lookup and fallback"),
    ("0x42ca6a4", "zg::CGFDirectionResourceSingle::LoadFileZ2DTexture", "per-image direct-load fallback"),
)


class ParseError(ValueError):
    """The record does not match the bounded, code-proven layout."""


@dataclass
class Reader:
    data: bytes
    offset: int

    def need(self, size: int) -> None:
        if size < 0 or self.offset + size > len(self.data):
            raise ParseError(f"record truncated at 0x{self.offset:x}, need {size} bytes")

    def u8(self) -> int:
        self.need(1)
        value = self.data[self.offset]
        self.offset += 1
        return value

    def u16(self) -> int:
        self.need(2)
        value = struct.unpack_from("<H", self.data, self.offset)[0]
        self.offset += 2
        return value

    def i32(self) -> int:
        self.need(4)
        value = struct.unpack_from("<i", self.data, self.offset)[0]
        self.offset += 4
        return value

    def u32(self) -> int:
        self.need(4)
        value = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return value

    def f32(self) -> float:
        self.need(4)
        value = struct.unpack_from("<f", self.data, self.offset)[0]
        self.offset += 4
        return value

    def fixed(self, size: int) -> bytes:
        self.need(size)
        value = self.data[self.offset : self.offset + size]
        self.offset += size
        return value

    def string255(self) -> str:
        length = self.u8()
        raw = self.fixed(length)
        while self.offset % 4:
            self.fixed(1)
        raw = raw[:-1] if raw.endswith(b"\0") else raw
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError(f"invalid UTF-8 String255 at 0x{self.offset:x}") from exc


def _parse_static_single_value(reader: Reader, value_type: int) -> Any:
    if value_type == 1:
        return reader.i32()
    if value_type == 2:
        return reader.f32()
    if value_type == 3:
        return reader.string255()
    if value_type in (10, 12):
        return reader.i32()
    if value_type == 11:
        return [reader.u32(), reader.u32()]
    raise ParseError(f"unsupported single parameter value type {value_type}")


def parse_parameter(
    reader: Reader, *, allow_keyed_float: bool = False
) -> dict[str, Any]:
    start = reader.offset
    version = reader.i32()
    parameter_id = reader.u16()
    value_type = reader.u8()
    reference_flag = reader.u8()
    name = reader.string255()
    hashes = None
    if name:
        hashes = {
            "name_hash": reader.fixed(8).hex(),
            "reference_hash": reader.fixed(8).hex(),
        }

    row: dict[str, Any] = {
        "offset_hex": f"0x{start:x}",
        "version": version,
        "parameter_id": parameter_id,
        "value_type": value_type,
        "reference_flag": reference_flag,
        "name": name,
    }
    if hashes is not None:
        row["hashes"] = hashes

    if 4 <= value_type <= 8:
        component_count = reader.i32()
        if not 0 <= component_count <= 16:
            raise ParseError(
                f"invalid compound component count {component_count} at 0x{start:x}"
            )
        row["components"] = [
            parse_parameter(reader, allow_keyed_float=allow_keyed_float)
            for _ in range(component_count)
        ]
    else:
        row["load_flags"] = [reader.u8(), reader.u8(), reader.u8()]
        reader.fixed(1)  # code-proven one-byte padding
        key_count = reader.i32()
        if key_count < 0 or key_count > 0x100000:
            raise ParseError(
                f"invalid key count {key_count} for parameter {parameter_id} at 0x{start:x}"
            )
        if key_count and (not allow_keyed_float or value_type != 2):
            raise ParseError(
                f"keyed parameter {parameter_id} at 0x{start:x} is outside the bounded parser"
            )
        row["key_count"] = key_count
        if key_count:
            if row["load_flags"][0]:
                raise ParseError(
                    f"spline curve parameter {parameter_id} at 0x{start:x} is outside the bounded parser"
                )
            row["keys"] = [
                {
                    "time": reader.f32(),
                    "curve_type": reader.i32(),
                    "value": reader.f32(),
                }
                for _ in range(key_count)
            ]
        else:
            row["static_value"] = _parse_static_single_value(reader, value_type)

    row["end_offset_hex"] = f"0x{reader.offset:x}"
    return row


def flatten_parameter_ids(parameters: Iterable[dict[str, Any]]) -> list[int]:
    result: list[int] = []
    for row in parameters:
        result.append(int(row["parameter_id"]))
        result.extend(flatten_parameter_ids(row.get("components", [])))
    return result


def find_node_offset(data: bytes, name: str) -> int:
    marker = name.encode("utf-8") + b"\0"
    positions: list[int] = []
    cursor = 0
    while True:
        found = data.find(marker, cursor)
        if found < 0:
            break
        positions.append(found)
        cursor = found + 1
    if len(positions) != 1:
        raise ParseError(f"expected one {name!r} node marker, found {len(positions)}")
    node_offset = positions[0] - 5  # u32 node type + u8 String255 length
    if node_offset < 0 or data[node_offset + 4] != len(marker):
        raise ParseError(f"{name!r} is not preceded by the packed node header")
    return node_offset


def parse_node(
    data: bytes, name: str, *, allow_keyed_float: bool = False
) -> dict[str, Any]:
    start = find_node_offset(data, name)
    reader = Reader(data, start)
    node_type = reader.i32()
    parsed_name = reader.string255()
    if parsed_name != name:
        raise ParseError(f"node name differs: {parsed_name!r} != {name!r}")
    name_hash = reader.fixed(8).hex() if parsed_name else ""
    resource_index = reader.i32()
    secondary_index = reader.i32()
    node_hash = [reader.u32(), reader.u32()]
    secondary_name = reader.string255()
    node_flags = [reader.u8(), reader.u8(), reader.u8()]
    reader.fixed(1)
    child_count = reader.i32()
    parameter_count = reader.i32()
    motion_count = reader.i32()
    if child_count != 0:
        raise ParseError(f"target node {name!r} unexpectedly has {child_count} children")
    if not 0 <= parameter_count <= 256 or not 0 <= motion_count <= 256:
        raise ParseError(f"invalid target node counts at 0x{start:x}")
    parameters = [
        parse_parameter(reader, allow_keyed_float=allow_keyed_float)
        for _ in range(parameter_count)
    ]
    top_level_ids = [int(row["parameter_id"]) for row in parameters]
    all_ids = flatten_parameter_ids(parameters)
    return {
        "name": name,
        "offset_hex": f"0x{start:x}",
        "node_type": node_type,
        "name_hash": name_hash,
        "resource_index": resource_index,
        "secondary_index": secondary_index,
        "node_hash": node_hash,
        "secondary_name": secondary_name,
        "node_flags": node_flags,
        "child_count": child_count,
        "parameter_count": parameter_count,
        "motion_count": motion_count,
        "parameter_payload_end_offset_hex": f"0x{reader.offset:x}",
        "top_level_parameter_ids": top_level_ids,
        "all_parameter_ids_including_compound_children": all_ids,
        "resource_override_parameter_147_present": RESOURCE_OVERRIDE_PARAMETER_ID in all_ids,
        "parameters": parameters,
    }


def extract(record: Path) -> dict[str, Any]:
    data = record.read_bytes()
    if len(data) < 8 or data[:4] != b"GDB\x03":
        raise ParseError("record is not a GDB type-3 artifact")
    body_size = struct.unpack_from("<I", data, 4)[0]
    if body_size + 8 != len(data):
        raise ParseError(f"GDB body-size mismatch: {body_size}+8 != {len(data)}")
    nodes = [parse_node(data, name) for name in TARGET_NODES]
    for node in nodes:
        if tuple(node["top_level_parameter_ids"]) != EXPECTED_PARAMETER_IDS:
            raise ParseError(f"target parameter set differs for {node['name']}")
        if node["resource_index"] != -1 or node["motion_count"] != 1:
            raise ParseError(f"target resource/motion header differs for {node['name']}")
        if node["resource_override_parameter_147_present"]:
            raise ParseError(f"unexpected resource override parameter 147 in {node['name']}")
    return {
        "schema": "magireco-gfdirection-z2d-node-resource-bindings-v1",
        "status": "passed_fail_closed",
        "record": {
            "path": str(record.resolve()),
            "size": len(data),
            "gdb_record_type": 3,
            "body_size": body_size,
            "derived_from_exact_slot_binary_sha256": SLOT_BINARY_SHA256,
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "nodes": nodes,
        "assertions": {
            "both_target_nodes_have_no_direct_resource_index": True,
            "both_target_nodes_lack_parameter_147_resource_override": True,
            "z2d_image_loader_uses_direct_file_fallback_without_parameter_147": True,
            "add_and_add_lp_logical_images_are_not_yet_resolved_to_physical_media": True,
            "ac0908_016_production_disposition": "FAIL_CLOSED_RESOURCE_RESOLUTION_PENDING",
            "machine_vision_used_as_authority": False,
        },
    }


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    bindings = output_dir / "AC0908_016_NODE_RESOURCE_BINDINGS.json"
    evidence = output_dir / "IDA_Z2D_DGM_RESOLUTION_EVIDENCE.json"
    verification = output_dir / "VERIFICATION_RECORD.json"
    integration = output_dir / "INTEGRATION_VERIFICATION.txt"
    bindings.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evidence_payload = {
        "schema": "magireco-ac0908-016-z2d-dgm-resolution-evidence-v1",
        "status": "partial_authority_fail_closed",
        "source_bindings": bindings.name,
        "code_authority": result["code_authority"],
        "findings": result["assertions"],
        "next_boundary": (
            "resolve logical ac8040_premia_EF_add(.dgm) and _add_LP(.dgm) through "
            "CGFDirectionPlayer resource callbacks/extension conversion before rendering"
        ),
    }
    evidence.write_text(
        json.dumps(evidence_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    verification_payload = {
        "schema": "magireco-ac0908-016-static-binding-verification-v1",
        "status": "passed",
        "outputs": [bindings.name, evidence.name],
        "checks": {
            "target_node_count": len(result["nodes"]),
            "target_parameter_sets_exact": True,
            "parameter_147_absent": True,
            "resource_index_negative_one": True,
            "production_remains_fail_closed": True,
        },
    }
    verification.write_text(
        json.dumps(verification_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    integration.write_text(
        "PASS\n"
        "target_nodes=2\n"
        "resource_override_parameter_147_present=0\n"
        "direct_resource_index_present=0\n"
        "ac0908_016=FAIL_CLOSED_RESOURCE_RESOLUTION_PENDING\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = extract(args.record)
    write_outputs(result, args.output_dir)
    print(
        "PASS "
        f"nodes={len(result['nodes'])} "
        "parameter147=absent resource_index=-1 "
        "production=FAIL_CLOSED_RESOURCE_RESOLUTION_PENDING"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
