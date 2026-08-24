from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from tools.frida_runtime_probe import extract_z2d_movie_layer_reachability_authority as target


def layer(
    reference: str, *, width: int, height: int, start: int, end: int,
    layer_index: int, movie_index: int,
) -> bytes:
    data = bytearray(struct.pack("<II", (10 << 27) | layer_index, 0))
    data.extend(f"[{reference}]\0".encode("ascii"))
    while len(data) % 4:
        data.append(0)
    data.extend(b"\0\0")
    data.extend(struct.pack("<H", 0x037E))
    data.extend(struct.pack("<I2H", 2, start, end))
    data.extend(
        struct.pack(
            "<4f2H", width / 2, height / 2, width / 2, height / 2, width, height
        )
    )
    data.extend(struct.pack("<I", (14 << 27) | movie_index))
    return bytes(data)


def movie_pubroot(names: list[str], *, second_end: int) -> bytes:
    count = len(names)
    payload = b"".join(bytes([len(name)]) + name.encode("ascii") for name in names)
    data = bytearray(struct.pack("<I", (13 << 27) | 1))
    data.extend(struct.pack("<BBh", 0, 0, count))
    data.extend(struct.pack("<4I", 2, count, 14 << 27, len(payload)))
    data.extend(struct.pack(f"<{count}I", *([1] * count)))
    data.extend(struct.pack(f"<{count}I", *([2] * count)))
    data.extend(struct.pack(f"<{count}i", *([0] * count)))
    data.extend(struct.pack("<2i", 29, second_end))
    data.extend(struct.pack(f"<{count}i", *([0x07FFFFFF] * count)))
    data.extend(payload)
    data.extend(bytes(count))
    while len(data) % 4:
        data.append(0)
    return bytes(data)


def z2d_fixture(path: Path, *, second_end: int = 29) -> None:
    data = bytearray(0x100)
    data[:4] = b"z2d\0"
    struct.pack_into("<4I", data, 4, 15, 0, 29, 0)
    struct.pack_into("<f", data, 0x14, 30.0)
    name = b"fixture.z2d\0"
    data[0x78 : 0x78 + len(name)] = name
    cursor = (0x78 + len(name) + 3) & ~3
    struct.pack_into("<3I", data, cursor, 0, 1024, 576)
    data.extend(layer(
        "component.dgm", width=320, height=256, start=0, end=29,
        layer_index=0, movie_index=0,
    ))
    data.extend(layer(
        "missing_add_MF.dgm", width=512, height=416, start=0, end=second_end,
        layer_index=1, movie_index=1,
    ))
    data.extend(movie_pubroot(["component.dgm", "missing_add.dgm"], second_end=second_end))
    path.write_bytes(data)


class Z2DMovieLayerReachabilityAuthorityTests(unittest.TestCase):
    @mock.patch.object(target, "validate_exact_binary", return_value=("build", [2, 3, 4], 123))
    def test_accepts_component_geometry_and_marks_unreachable_name(self, _validate) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "libGameProc.so"
            binary.write_bytes(b"binary")
            chunk = root / "fixture.z2d"
            z2d_fixture(chunk)
            manifest = root / "named.json"
            manifest.write_text(json.dumps({
                "schema": "magireco-exact-apk-named-z2d-extraction-v1",
                "status": "passed",
                "chunks": [{
                    "name": "fixture", "output_path": str(chunk), "chunk_index": 1,
                    "offset": 10, "size": chunk.stat().st_size,
                    "dgm_references": [
                        "component.dgm", "missing_add_MF.dgm", "missing_add.dgm"
                    ],
                }],
            }), encoding="utf-8")
            table = root / "table.csv"
            table.write_text("table_index,name\n7,component\n", encoding="utf-8")
            report = target.build_report(
                binary=binary, z2d_manifest=manifest, filename_table_csv=table
            )
            self.assertEqual(report["counts"]["loadable_movie_layers"], 1)
            self.assertEqual(report["counts"]["unreachable_movie_layers"], 1)
            self.assertEqual(report["counts"]["layer_names_differing_from_media_names"], 1)
            self.assertEqual(
                report["z2d_chunks"][0]["movie_layers"][1]["z2d_reference"],
                "missing_add.dgm",
            )
            self.assertIn("320x256", next(iter(report["counts"]["geometry_contracts"])))

    @mock.patch.object(target, "validate_exact_binary", return_value=("build", [2, 3, 4], 123))
    def test_rejects_movie_layer_beyond_parent_frame_range(self, _validate) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "libGameProc.so"
            binary.write_bytes(b"binary")
            chunk = root / "fixture.z2d"
            z2d_fixture(chunk, second_end=30)
            manifest = root / "named.json"
            manifest.write_text(json.dumps({
                "schema": "magireco-exact-apk-named-z2d-extraction-v1",
                "status": "passed",
                "chunks": [{
                    "name": "fixture", "output_path": str(chunk), "chunk_index": 1,
                    "offset": 10, "size": chunk.stat().st_size,
                    "dgm_references": [
                        "component.dgm", "missing_add_MF.dgm", "missing_add.dgm"
                    ],
                }],
            }), encoding="utf-8")
            table = root / "table.csv"
            table.write_text("table_index,name\n7,component\n", encoding="utf-8")
            with self.assertRaisesRegex(target.BlendAuthorityError, "exceeds parent"):
                target.build_report(
                    binary=binary, z2d_manifest=manifest, filename_table_csv=table
                )


if __name__ == "__main__":
    unittest.main()
