from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

from tools.frida_runtime_probe import extract_gfdirection_scene_group_authority as target


def string255(value: str) -> bytes:
    raw = value.encode("utf-8") + b"\0"
    result = bytes([len(raw)]) + raw
    return result + b"\0" * ((-len(result)) % 4)


def record(record_type: int, body: bytes) -> bytes:
    return b"GDB" + bytes([record_type]) + struct.pack("<I", len(body)) + body


def type3(name: str, frames: int) -> bytes:
    body = (
        struct.pack("<II", 1, 2)
        + struct.pack("<III", frames, 0, frames - 1)
        + string255(name)
        + b"PAYLOAD0"
    )
    return record(3, body)


def type2(name: str, frames: int, references: list[tuple[int, int]]) -> bytes:
    body = (
        struct.pack("<II", 3, 4)
        + struct.pack("<I", frames)
        + string255(name)
        + struct.pack("<I", len(references))
        + b"".join(struct.pack("<II", *reference) for reference in references)
    )
    return record(2, body)


def group_chunk() -> bytes:
    return (
        b"H" * 28
        + record(0, b"HEADER00")
        + type2("fixture", 30, [(0, 0)])
        + type2("fixture_alias", 22, [(1, 10)])
        + type3("fixture_001", 30)
        + type3("subscene_001", 12)
        + record(4, b"")
    )


class GFDirectionSceneGroupAuthorityTests(unittest.TestCase):
    def test_parses_contiguous_type3_records_and_frames(self) -> None:
        result = target.parse_group_chunk(group_chunk())
        self.assertEqual(2, len(result["type3_records"]))
        self.assertEqual("fixture_001", result["type3_records"][0]["name"])
        self.assertEqual(30, result["type3_records"][0]["frame_count"])
        self.assertEqual(1, result["counts_by_record_type"]["4"])
        self.assertEqual(
            "subscene_001",
            result["type2_presentations"][1]["scene_references"][0]["target_name"],
        )

    def test_rejects_missing_final_terminator(self) -> None:
        with self.assertRaisesRegex(target.SceneGroupError, "terminator"):
            target.parse_group_chunk(group_chunk()[:-8])

    @mock.patch.object(target, "read_scene_group_names", return_value=["zero", "fixture", "two"])
    @mock.patch.object(target, "validate_exact_binary", return_value=("build-id", [], 0))
    def test_builds_exact_indexed_group_and_reopens_outputs(
        self, _validate: mock.Mock, _names: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "libGameProc.so"
            binary.write_bytes(b"fixture")
            chunk = group_chunk()
            gdb = b"A" * 10 + chunk + b"B" * 5
            offsets = struct.pack("<4I", 0, 10, 10 + len(chunk), len(gdb))
            apk = root / "pack.apk"
            with ZipFile(apk, "w") as archive:
                archive.writestr(target.OFFSET_ASSET, offsets)
                archive.writestr(target.DATA_ASSET, gdb)
            with mock.patch.object(target, "SCENE_GROUP_COUNT", 3):
                report, exact = target.build_report(
                    binary=binary,
                    apk=apk,
                    group_name="fixture",
                    expected_group_index=1,
                )
            self.assertEqual(1, report["group"]["compiled_index"])
            self.assertEqual(1, len(report["group"]["primary_type3_records"]))
            output = root / "authority"
            target.write_outputs(report, exact, output)
            self.assertTrue((output / "type3_records" / "fixture_001.gdb3.bin").is_file())


if __name__ == "__main__":
    unittest.main()
