#!/usr/bin/env python3
"""Extract exact GFDirection GDP layer and viewport authority from the Slot APK."""

from __future__ import annotations

import argparse
import csv
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from zipfile import ZipFile

try:
    from .extract_jm_dgi_glyph_catalog import sha256_bytes
    from .extract_z2d_movie_layer_blend_authority import (
        SLOT_BINARY_SHA256,
        validate_exact_binary,
    )
except ImportError:  # pragma: no cover - direct script execution
    from extract_jm_dgi_glyph_catalog import sha256_bytes  # type: ignore
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        SLOT_BINARY_SHA256,
        validate_exact_binary,
    )


SCHEMA = "magireco-gfdirection-project-viewport-authority-v1"
GDP_ASSET = "assets/gdp.bin"
GDP_VERSION = (1, 7, 0)
RB_SET_COUNT = 4

CODE_AUTHORITY = (
    (
        "0x42c218c",
        "zg::CGFDirectionPlayer::LoadGDP",
        "GDP 1.7.0 header, four render-buffer sets, layer records, render buffers, and resources",
    ),
    (
        "0x429cc40",
        "zg::CGFDirectionLayer::GetViewport",
        "stores left/top and derives width/height from right/bottom; invalid rectangles fall back to the target render buffer",
    ),
    (
        "0x42bdd30",
        "zg::CGFDirectionPlayer::CreateRBSet",
        "creates the render-buffer dimensions declared by the GDP project",
    ),
    (
        "0x42a71bc",
        "zg::CGFDirectionNodeLayer::SetParameterZ2D",
        "places a Z2D root relative to the exact layer viewport and render-buffer dimensions",
    ),
    (
        "0x437f4c8",
        "zg::C_Scene::fnSceneRenderBuffer",
        "draws the completed scene texture across the destination render buffer with full UV coordinates",
    ),
)


class GDPAuthorityError(ValueError):
    """The GDP asset does not match the code-proven bounded layout."""


@dataclass
class Reader:
    data: bytes
    offset: int = 0

    def need(self, size: int) -> None:
        if size < 0 or self.offset + size > len(self.data):
            raise GDPAuthorityError(
                f"GDP truncated at 0x{self.offset:x}, need {size} bytes"
            )

    def fixed(self, size: int) -> bytes:
        self.need(size)
        value = self.data[self.offset : self.offset + size]
        self.offset += size
        return value

    def u8(self) -> int:
        return self.fixed(1)[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.fixed(4))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.fixed(4))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.fixed(4))[0]

    def string255(self) -> str:
        start = self.offset
        length = self.u8()
        raw = self.fixed(length)
        padding = (-self.offset) % 4
        if padding and any(self.fixed(padding)):
            raise GDPAuthorityError(f"non-zero String255 padding at 0x{start:x}")
        if raw.endswith(b"\0"):
            raw = raw[:-1]
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GDPAuthorityError(
                f"invalid UTF-8 String255 at 0x{start:x}"
            ) from exc


def _hash_pair(reader: Reader) -> list[int]:
    return [reader.u32(), reader.u32()]


def _bounded_count(reader: Reader, *, label: str, maximum: int) -> int:
    value = reader.i32()
    if not 0 <= value <= maximum:
        raise GDPAuthorityError(f"invalid {label} count {value}")
    return value


def parse_gdp(data: bytes) -> dict[str, Any]:
    reader = Reader(data)
    if reader.fixed(3) != b"GDP" or reader.u8() != 0:
        raise GDPAuthorityError("illegal GDP signature or reserved byte")
    version = tuple(reader.u8() for _ in range(3))
    if version != GDP_VERSION:
        raise GDPAuthorityError(f"unsupported GDP version {version!r}")
    project_flags = [reader.u8() for _ in range(5)]
    if any(value not in (0, 1) for value in project_flags):
        raise GDPAuthorityError("GDP project boolean flag is not 0 or 1")

    rb_sets: list[dict[str, Any]] = []
    for index in range(RB_SET_COUNT):
        flags, width, height = reader.u32(), reader.u32(), reader.u32()
        if width <= 0 or height <= 0:
            raise GDPAuthorityError(f"render-buffer set {index} has invalid dimensions")
        rb_sets.append(
            {
                "index": index,
                "flags": flags,
                "enabled": bool(flags & 1),
                "double_buffered": bool(flags & 0x10),
                "width": width,
                "height": height,
            }
        )

    layer_count = _bounded_count(reader, label="layer", maximum=4096)
    layers: list[dict[str, Any]] = []
    names: set[str] = set()
    for index in range(layer_count):
        start = reader.offset
        hash_words = _hash_pair(reader)
        name = reader.string255()
        if not name or name in names:
            raise GDPAuthorityError(f"empty or duplicate GDP layer name {name!r}")
        names.add(name)
        render_buffer_target = reader.u8()
        enabled = reader.u8()
        padding = reader.fixed(2)
        if render_buffer_target >= RB_SET_COUNT or enabled not in (0, 1) or any(padding):
            raise GDPAuthorityError(f"invalid GDP layer header for {name!r}")
        left, top, right, bottom = (
            reader.i32(),
            reader.i32(),
            reader.i32(),
            reader.i32(),
        )
        opacity = reader.f32()
        target = rb_sets[render_buffer_target]
        explicit_width = right - left
        explicit_height = bottom - top
        fallback = explicit_width < 1 or explicit_height < 1
        effective_viewport = None
        if target["enabled"]:
            effective_viewport = {
                "left": 0 if fallback else left,
                "top": 0 if fallback else top,
                "width": target["width"] if fallback else explicit_width,
                "height": target["height"] if fallback else explicit_height,
                "source": (
                    "TARGET_RENDERBUFFER_FALLBACK"
                    if fallback
                    else "EXPLICIT_LEFT_TOP_RIGHT_BOTTOM"
                ),
            }
        layers.append(
            {
                "index": index,
                "offset_hex": f"0x{start:x}",
                "hash_words": hash_words,
                "name": name,
                "render_buffer_target": render_buffer_target,
                "render_buffer_available": bool(target["enabled"]),
                "initial_enabled": bool(enabled),
                "stored_viewport_ltrb": [left, top, right, bottom],
                "stored_opacity": opacity,
                "effective_viewport": effective_viewport,
            }
        )

    render_buffer_count = _bounded_count(
        reader, label="named render buffer", maximum=255
    )
    render_buffers: list[dict[str, Any]] = []
    for index in range(render_buffer_count):
        start = reader.offset
        hash_words = _hash_pair(reader)
        pixel_format = reader.i32()
        name = reader.string255()
        width, height = reader.i32(), reader.i32()
        if not 1 <= pixel_format <= 20 or not name or width <= 0 or height <= 0:
            raise GDPAuthorityError(f"invalid named render buffer at index {index}")
        render_buffers.append(
            {
                "index": index,
                "offset_hex": f"0x{start:x}",
                "hash_words": hash_words,
                "pixel_format": pixel_format,
                "name": name,
                "width": width,
                "height": height,
            }
        )

    resource_count = _bounded_count(reader, label="resource", maximum=4096)
    cache_instance_count = _bounded_count(
        reader, label="cache resource instance", maximum=0xFFFFFF
    )
    resources: list[dict[str, Any]] = []
    parsed_cache_instances = 0
    for index in range(resource_count):
        start = reader.offset
        resource_hash = _hash_pair(reader)
        secondary_hash = _hash_pair(reader)
        resource_type = reader.u8()
        padding = reader.fixed(3)
        instances = reader.i32()
        filename = reader.string255()
        directory = reader.string255()
        if (
            not 1 <= resource_type <= 20
            or any(padding)
            or instances < 0
            or not filename
        ):
            raise GDPAuthorityError(f"invalid GDP resource at index {index}")
        parsed_cache_instances += instances
        resources.append(
            {
                "index": index,
                "offset_hex": f"0x{start:x}",
                "resource_hash_words": resource_hash,
                "secondary_hash_words": secondary_hash,
                "resource_type": resource_type,
                "cache_instances": instances,
                "filename": filename,
                "directory": directory,
            }
        )
    if parsed_cache_instances != cache_instance_count:
        raise GDPAuthorityError(
            "declared cache instance count differs from resource instances"
        )
    if reader.offset != len(data):
        raise GDPAuthorityError(
            f"unparsed GDP tail: 0x{reader.offset:x} of 0x{len(data):x}"
        )

    viewport_counts: dict[str, int] = {}
    for layer in layers:
        viewport = layer["effective_viewport"]
        key = (
            "UNAVAILABLE"
            if viewport is None
            else f"{viewport['left']},{viewport['top']}+{viewport['width']}x{viewport['height']}"
        )
        viewport_counts[key] = viewport_counts.get(key, 0) + 1
    return {
        "version": ".".join(str(value) for value in version),
        "project_flags": project_flags,
        "render_buffer_sets": rb_sets,
        "layers": layers,
        "named_render_buffers": render_buffers,
        "resources": resources,
        "counts": {
            "render_buffer_sets": len(rb_sets),
            "layers": len(layers),
            "named_render_buffers": len(render_buffers),
            "resources": len(resources),
            "cache_resource_instances": cache_instance_count,
            "effective_viewports": viewport_counts,
        },
    }


def build_report(*, binary: Path, apk: Path, asset_name: str = GDP_ASSET) -> tuple[dict[str, Any], bytes]:
    build_id, _, _ = validate_exact_binary(binary)
    with ZipFile(apk) as archive:
        try:
            info = archive.getinfo(asset_name)
        except KeyError as exc:
            raise GDPAuthorityError(f"APK lacks {asset_name}") from exc
        data = archive.read(info)
    parsed = parse_gdp(data)
    report = {
        "schema": SCHEMA,
        "status": "passed_code_exact",
        "binary": {
            "path": str(binary.resolve()),
            "gnu_build_id": build_id,
            "inherited_sha256": SLOT_BINARY_SHA256,
        },
        "source": {
            "apk_path": str(apk.resolve()),
            "asset_name": asset_name,
            "asset_size": len(data),
            "asset_zip_crc32": f"{info.CRC:08X}",
            "asset_sha256": sha256_bytes(data),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "project": parsed,
        "assertions": {
            "gdp_parser_matches_loadgdp_1_7_0_layout": True,
            "viewport_fallback_matches_getviewport": True,
            "stored_coordinates_are_left_top_right_bottom": True,
            "z2d_placement_must_use_layer_viewport_not_generic_center_crop": True,
            "machine_vision_used_as_authority": False,
            "media_modified": False,
        },
    }
    return report, data


def write_outputs(report: dict[str, Any], data: bytes, output_dir: Path) -> None:
    if output_dir.exists():
        raise GDPAuthorityError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    asset_path = output_dir / "EXACT_GDP_1_7_0.bin"
    asset_path.write_bytes(data)
    if sha256_bytes(asset_path.read_bytes()) != report["source"]["asset_sha256"]:
        raise GDPAuthorityError("written GDP artifact differs from APK asset")
    report_path = output_dir / "GFDIRECTION_PROJECT_VIEWPORT_AUTHORITY.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = []
    for layer in report["project"]["layers"]:
        viewport = layer["effective_viewport"] or {}
        rows.append(
            {
                "index": layer["index"],
                "name": layer["name"],
                "render_buffer_target": layer["render_buffer_target"],
                "render_buffer_available": layer["render_buffer_available"],
                "initial_enabled": layer["initial_enabled"],
                "stored_viewport_ltrb": json.dumps(layer["stored_viewport_ltrb"]),
                "effective_left": viewport.get("left"),
                "effective_top": viewport.get("top"),
                "effective_width": viewport.get("width"),
                "effective_height": viewport.get("height"),
                "effective_source": viewport.get("source", "UNAVAILABLE"),
                "stored_opacity": layer["stored_opacity"],
            }
        )
    with (output_dir / "GDP_LAYERS.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = report["project"]["counts"]
    literal = (
        f"PASS gdp=1.7.0 rbsets={counts['render_buffer_sets']} "
        f"layers={counts['layers']} renderbuffers={counts['named_render_buffers']} "
        f"resources={counts['resources']}"
    )
    (output_dir / "VERIFICATION_RECORD.json").write_text(
        json.dumps(
            {
                "schema": "magireco-gfdirection-project-viewport-verification-v1",
                "status": "passed",
                "source_asset_sha256": report["source"]["asset_sha256"],
                "outputs": [
                    asset_path.name,
                    report_path.name,
                    "GDP_LAYERS.csv",
                ],
                "literal_result": literal,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--asset-name", default=GDP_ASSET)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report, data = build_report(
        binary=args.binary, apk=args.apk, asset_name=args.asset_name
    )
    write_outputs(report, data, args.output_dir)
    counts = report["project"]["counts"]
    print(
        f"PASS gdp=1.7.0 rbsets={counts['render_buffer_sets']} "
        f"layers={counts['layers']} renderbuffers={counts['named_render_buffers']} "
        f"resources={counts['resources']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
