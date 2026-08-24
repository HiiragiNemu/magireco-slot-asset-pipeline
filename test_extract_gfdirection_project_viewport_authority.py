from __future__ import annotations

import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

from tools.frida_runtime_probe import extract_gfdirection_project_viewport_authority as target


def string255(value: str) -> bytes:
    raw = value.encode("utf-8") + (b"\0" if value else b"")
    result = bytes([len(raw)]) + raw
    return result + b"\0" * ((-len(result)) % 4)


def gdp_fixture(*, trailing: bytes = b"") -> bytes:
    data = bytearray(b"GDP\0" + bytes([1, 7, 0]) + b"\1\1\1\1\1")
    for flags, width, height in (
        (1, 1280, 1024),
        (1, 480, 800),
        (0, 1280, 720),
        (0, 1280, 720),
    ):
        data.extend(struct.pack("<III", flags, width, height))
    layers = (
        ("normal", 0, (128, 0, 1152, 576)),
        ("full", 0, (0, 0, 0, 0)),
        ("sub", 1, (0, 0, 480, 800)),
    )
    data.extend(struct.pack("<i", len(layers)))
    for index, (name, target_index, viewport) in enumerate(layers):
        data.extend(struct.pack("<II", index + 1, index + 2))
        data.extend(string255(name))
        data.extend(bytes([target_index, 0, 0, 0]))
        data.extend(struct.pack("<4if", *viewport, 1.0))
    data.extend(struct.pack("<i", 1))
    data.extend(struct.pack("<IIi", 10, 11, 14))
    data.extend(string255("CaptureBuffer"))
    data.extend(struct.pack("<ii", 1280, 1024))
    data.extend(struct.pack("<ii", 0, 0))
    data.extend(trailing)
    return bytes(data)


class GFDirectionProjectViewportAuthorityTests(unittest.TestCase):
    def test_parses_explicit_and_renderbuffer_fallback_viewports(self) -> None:
        result = target.parse_gdp(gdp_fixture())
        self.assertEqual("1.7.0", result["version"])
        self.assertEqual(3, result["counts"]["layers"])
        normal, full, sub = result["layers"]
        self.assertEqual(
            {"left": 128, "top": 0, "width": 1024, "height": 576,
             "source": "EXPLICIT_LEFT_TOP_RIGHT_BOTTOM"},
            normal["effective_viewport"],
        )
        self.assertEqual(
            {"left": 0, "top": 0, "width": 1280, "height": 1024,
             "source": "TARGET_RENDERBUFFER_FALLBACK"},
            full["effective_viewport"],
        )
        self.assertEqual(480, sub["effective_viewport"]["width"])

    def test_rejects_unparsed_tail(self) -> None:
        with self.assertRaisesRegex(target.GDPAuthorityError, "unparsed GDP tail"):
            target.parse_gdp(gdp_fixture(trailing=b"TAIL"))

    def test_rejects_invalid_version(self) -> None:
        data = bytearray(gdp_fixture())
        data[5] = 8
        with self.assertRaisesRegex(target.GDPAuthorityError, "unsupported GDP version"):
            target.parse_gdp(bytes(data))

    @mock.patch.object(target, "validate_exact_binary", return_value=("build-id", [], 0))
    def test_builds_and_reopens_verified_artifacts(self, _validate: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            apk = root / "pack.apk"
            with ZipFile(apk, "w") as archive:
                archive.writestr(target.GDP_ASSET, gdp_fixture())
            binary = root / "libGameProc.so"
            binary.write_bytes(b"fixture")
            report, data = target.build_report(binary=binary, apk=apk)
            output = root / "authority"
            target.write_outputs(report, data, output)
            reopened = json.loads(
                (output / "GFDIRECTION_PROJECT_VIEWPORT_AUTHORITY.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("passed_code_exact", reopened["status"])
            self.assertEqual(
                reopened["source"]["asset_sha256"],
                json.loads(
                    (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
                )["source_asset_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
