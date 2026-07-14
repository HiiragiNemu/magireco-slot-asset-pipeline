from __future__ import annotations

import hashlib
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.extract_jm_dgi_glyph_catalog import (
    ASTC_MAGIC,
    DGI_NATIVE_NAME_COUNT,
    DGI_NATIVE_NAME_TABLE_OFFSET,
    DMP_HEADER,
    MISSING_COVERAGE_EXIT,
    audit_text_coverage,
    build_astc_container,
    build_parser,
    parse_dmp_header,
    read_dgi_catalog,
    run,
)


def make_dmp(width: int, height: int, payload: bytes) -> bytes:
    return DMP_HEADER.pack(
        b"DMP ",
        DMP_HEADER.size,
        0,
        0,
        width,
        height,
        0,
        len(payload),
        0x001D,
        1,
    ) + payload


class DgiGlyphCatalogUnitTests(unittest.TestCase):
    def test_parse_and_wrap_synthetic_four_by_four_astc_block(self) -> None:
        payload = bytes(range(16))
        chunk = make_dmp(4, 4, payload)
        header = parse_dmp_header(chunk)
        self.assertEqual(header.width, 4)
        self.assertEqual(header.height, 4)
        self.assertEqual(header.expected_astc_payload_size, 16)

        astc = build_astc_container(header, payload)
        self.assertEqual(astc[:4], ASTC_MAGIC)
        self.assertEqual(astc[4:7], bytes((4, 4, 1)))
        self.assertEqual(astc[7:10], (4).to_bytes(3, "little"))
        self.assertEqual(astc[10:13], (4).to_bytes(3, "little"))
        self.assertEqual(astc[13:16], (1).to_bytes(3, "little"))
        self.assertEqual(astc[16:], payload)

    def test_parse_rejects_truncated_or_non_astc_dmp(self) -> None:
        with self.assertRaisesRegex(ValueError, "shorter"):
            parse_dmp_header(b"DMP ")
        wrong_format = bytearray(make_dmp(4, 4, bytes(16)))
        struct.pack_into("<H", wrong_format, 28, 0x001C)
        with self.assertRaisesRegex(ValueError, "unsupported JM DMP format"):
            parse_dmp_header(bytes(wrong_format))

    def test_synthetic_name_offset_catalog_is_end_to_end(self) -> None:
        payload = b"\xA5" * 16
        chunk = make_dmp(4, 4, payload)
        name = b"JM_0041_TEST_MR000\x00"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native_lib = root / "libGameProc.so"
            dgi_bin = root / "dgi.bin"
            dgi_add = root / "dgi_add.bin"
            name_table_offset = 64
            native_lib.write_bytes(
                bytes(name_table_offset)
                + struct.pack("<i", 4)
                + name
            )
            dgi_bin.write_bytes(chunk)
            dgi_add.write_bytes(struct.pack("<2I", 0, len(chunk)))

            records = read_dgi_catalog(
                native_lib,
                dgi_bin,
                dgi_add,
                name_table_offset=name_table_offset,
                name_count=1,
            )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["resource_name"], "JM_0041_TEST_MR000")
        self.assertEqual(record["codepoint_hex"], "U+0041")
        self.assertEqual(record["character"], "A")
        self.assertEqual(record["family"], "TEST")
        self.assertEqual(record["variant"], "MR000")
        self.assertEqual(record["chunk_sha256"], hashlib.sha256(chunk).hexdigest().upper())
        self.assertEqual(record["payload_sha256"], hashlib.sha256(payload).hexdigest().upper())
        self.assertFalse(record["typography_metrics_present"])

    def test_coverage_is_fail_closed_and_ignores_whitespace_by_default(self) -> None:
        records = [{"codepoint_int": ord("A")}, {"codepoint_int": ord("日")}]
        coverage = audit_text_coverage(records, ["A 日中\n"])
        self.assertEqual(coverage["required_unique_count"], 3)
        self.assertEqual(coverage["covered_unique_count"], 2)
        self.assertEqual(coverage["missing_unique_count"], 1)
        self.assertEqual(coverage["missing_codepoints"][0]["codepoint_hex"], "U+4E2D")
        self.assertFalse(coverage["passed"])

    def test_run_returns_distinct_nonzero_status_for_missing_coverage(self) -> None:
        payload = bytes(16)
        chunk = make_dmp(4, 4, payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native_lib = root / "libGameProc.so"
            dgi_bin = root / "dgi.bin"
            dgi_add = root / "dgi_add.bin"
            table_offset = 64
            native_lib.write_bytes(
                bytes(table_offset)
                + struct.pack("<i", 4)
                + b"JM_0041_TEST_MR000\x00"
            )
            dgi_bin.write_bytes(chunk)
            dgi_add.write_bytes(struct.pack("<2I", 0, len(chunk)))
            args = build_parser().parse_args(
                [
                    "--native-lib",
                    str(native_lib),
                    "--dgi-bin",
                    str(dgi_bin),
                    "--dgi-add",
                    str(dgi_add),
                    "--name-table-offset",
                    str(table_offset),
                    "--name-count",
                    "1",
                    "--coverage-text",
                    "AB",
                    "--skip-source-hashes",
                ]
            )
            self.assertEqual(run(args), MISSING_COVERAGE_EXIT)

    def test_explicit_outputs_write_manifest_and_small_astc_batch_only(self) -> None:
        payload = bytes(range(16))
        chunk = make_dmp(4, 4, payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native_lib = root / "libGameProc.so"
            dgi_bin = root / "dgi.bin"
            dgi_add = root / "dgi_add.bin"
            table_offset = 64
            native_lib.write_bytes(
                bytes(table_offset)
                + struct.pack("<i", 4)
                + b"JM_0041_TEST_MR000\x00"
            )
            dgi_bin.write_bytes(chunk)
            dgi_add.write_bytes(struct.pack("<2I", 0, len(chunk)))
            source_hashes_before = {
                path: hashlib.sha256(path.read_bytes()).digest()
                for path in (native_lib, dgi_bin, dgi_add)
            }
            json_out = root / "audit" / "catalog.json"
            csv_out = root / "audit" / "catalog.csv"
            astc_dir = root / "audit" / "astc"
            args = build_parser().parse_args(
                [
                    "--native-lib",
                    str(native_lib),
                    "--dgi-bin",
                    str(dgi_bin),
                    "--dgi-add",
                    str(dgi_add),
                    "--name-table-offset",
                    str(table_offset),
                    "--name-count",
                    "1",
                    "--coverage-text",
                    "A",
                    "--json-out",
                    str(json_out),
                    "--csv-out",
                    str(csv_out),
                    "--astc-dir",
                    str(astc_dir),
                    "--astc-name",
                    "JM_0041_TEST_MR000",
                    "--skip-source-hashes",
                ]
            )
            self.assertEqual(run(args), 0)

            manifest = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(manifest["summary"]["exported_astc_count"], 1)
            self.assertFalse(manifest["summary"]["typography_metrics_present"])
            self.assertTrue(manifest["coverage"]["passed"])
            self.assertTrue(csv_out.is_file())
            relative = manifest["glyphs"][0]["astc_relative_path"]
            exported = astc_dir / Path(relative)
            self.assertEqual(
                exported.read_bytes(),
                build_astc_container(parse_dmp_header(chunk), payload),
            )
            for path, expected_hash in source_hashes_before.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), expected_hash)


def installed_asset_root() -> Path | None:
    value = os.environ.get("MAGIRECO_SLOT_ASSET_ROOT")
    if not value:
        return None
    root = Path(value)
    required = (
        root / "unpacked_lib" / "lib" / "arm64-v8a" / "libGameProc.so",
        root / "unpacked_assets" / "assets" / "dgi.bin",
        root / "unpacked_assets" / "assets" / "dgi_add.bin",
    )
    return root if all(path.is_file() for path in required) else None


@unittest.skipUnless(
    installed_asset_root() is not None,
    "set MAGIRECO_SLOT_ASSET_ROOT to run immutable installed-asset vectors",
)
class DgiGlyphCatalogInstalledAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = installed_asset_root()
        assert root is not None
        cls.records = read_dgi_catalog(
            root / "unpacked_lib" / "lib" / "arm64-v8a" / "libGameProc.so",
            root / "unpacked_assets" / "assets" / "dgi.bin",
            root / "unpacked_assets" / "assets" / "dgi_add.bin",
            name_table_offset=DGI_NATIVE_NAME_TABLE_OFFSET,
            name_count=DGI_NATIVE_NAME_COUNT,
        )
        cls.by_index = {record["archive_index"]: record for record in cls.records}

    def test_full_catalog_static_closure_counts(self) -> None:
        self.assertEqual(len(self.records), 4124)
        self.assertEqual(len({record["codepoint_int"] for record in self.records}), 1056)

    def test_known_index_953_space_vector(self) -> None:
        record = self.by_index[953]
        self.assertEqual(record["resource_name"], "JM_0020_00009N7X_MR060")
        self.assertEqual(record["archive_offset"], 0x69EDF90)
        self.assertEqual(record["chunk_size"], 3168)
        self.assertEqual(record["dmp_width"], 56)
        self.assertEqual(record["dmp_height"], 56)
        self.assertEqual(record["dmp_data_size"], 3136)
        self.assertEqual(
            record["chunk_sha256"],
            "45C9A28E115C2E253E81BF443B950474A6D257AC1AC4F424806A3AEF05560747",
        )
        self.assertEqual(
            record["payload_sha256"],
            "B00CAF266CB058CBE5FC69C8276A2DC28DA8E38D3341978845208744DEC68220",
        )

    def test_known_index_4004_tamaki_large_family_vector(self) -> None:
        record = self.by_index[4004]
        self.assertEqual(record["resource_name"], "JM_74B0_00009N7X_MR060")
        self.assertEqual(record["archive_offset"], 0x724D190)
        self.assertEqual(record["chunk_size"], 3168)
        self.assertEqual(
            record["chunk_sha256"],
            "D188D82E5B91584944542ABDCAE50E7467B768EA6ED8391B19E609CCDA9A0FD7",
        )
        self.assertEqual(
            record["payload_sha256"],
            "22214CFB8B07AEDC314F4BFFD6B36636E494860F3D0EE55EB6C02E77F6526F7C",
        )

    def test_known_index_4006_tamaki_small_family_vector(self) -> None:
        record = self.by_index[4006]
        self.assertEqual(record["resource_name"], "JM_74B0_0000GAMW_MR010")
        self.assertEqual(record["archive_offset"], 0x724EA50)
        self.assertEqual(record["chunk_size"], 2736)
        self.assertEqual(record["dmp_width"], 52)
        self.assertEqual(record["dmp_height"], 52)
        self.assertEqual(record["dmp_data_size"], 2704)
        self.assertEqual(
            record["chunk_sha256"],
            "ECC07E4EC34622C8E20C76EF62A23E60B417FC4AF1717C7A030702AEB85F66FB",
        )
        self.assertEqual(
            record["payload_sha256"],
            "C4A25C46139E01C69BFD6EBEBE3700957CA438694DDF1C2016B0F6ADF27E4759",
        )


if __name__ == "__main__":
    unittest.main()
