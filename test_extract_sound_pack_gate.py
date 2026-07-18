from __future__ import annotations

import csv
import contextlib
import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe.extract_sound_pack_gate import (
    ACTIVE_SOUND_PACK_OFFSET,
    DEFAULT_TABLE_BYTE_LENGTH,
    ENTITLEMENT_INDEX,
    REFERENCE_LIBRARY_SHA256,
    REFERENCE_TABLE_SHA256,
    SAVED_SOUND_PACK_OFFSET,
    build_gate_report,
    enforce_reference_policy,
    extract_gate_ids,
    gate_table_bytes,
    make_csv_source,
    main,
    native_call_chain_evidence,
    parse_gate_ids,
    write_gate_outputs,
)


# Embedded read-only reference vector from the audited versionCode 31 arm64
# library.  Keeping it in the test removes any dependency on a D: snapshot.
CURRENT_REFERENCE_IDS = [
    67, 171, 603, 604, 611, 612, 615, 616, 622, 623, 630, 631, 632, 635,
    636, 637, 638, 639, 640, 644, 645, 646, 661, 662, 663, 664, 665, 666,
    670, 677, 678, 679, 680, 681, 682, 751, 752, 753, 754, 755, 756, 757,
    758, 759, 760, 761, 762, 763, 764, 765, 766, 767, 768, 769, 770, 771,
    772, 773, 774, 775, 778, 779, 780, 781, 782, 784, 785, 786, 787, 788,
    789, 790, 791, 792, 793, 795, 796, 797, 800, 801, 802, 805, 806, 807,
    813, 814, 815, 816, 817, 820, 821, 822, 823, 824, 826, 827, 828, 829,
    830, 831, 832, 833, 834, 843, 844, 845, 850, 851, 852, 853, 854, 855,
    856, 857, 858, 859, 860, 861, 862, 863, 865, 880, 881, 882, 883, 884,
    885, 886, 887, 889, 890, 891, 892, 893, 894, 895, 896, 897, 900, 901,
    903, 904, 910, 911, 912, 913, 914, 915, 2995, 3001, 3002, 6103, 6152,
    6153, 6154, 6155, 6700, 6702, 6704, 6706, 6708, 6710, 6750, 6751,
    6752, 6753, 6754, 6755, 6756, 9070, 9071, 16716, 38000, 38001, 38002,
    38003, 38004, 38005, 38006, 38007, 38008, 38009, 38010, 39000, 39001,
    39002, 39003, 39004, 39005, 39006, 39007, 39008, 39050, 39051, 39052,
    39053, 39054, 39055, 39056, 39057, 39100, 39101, 39102, 39104, 39105,
    39150, 39151, 39152, 39155, 39156, 39157, 39158, 39159, 39160, 39161,
    39200, 39201, 39203, 39204, 41030, 41031, 41032,
]


def pack_ids(ids: list[int]) -> bytes:
    return struct.pack(f"<{len(ids)}I", *ids)


class GateTableParsingTests(unittest.TestCase):
    def test_extracts_little_endian_ids_from_explicit_file_slice(self) -> None:
        table = pack_ids([7, 0x12345678, 9])
        blob = b"prefix" + table + b"suffix"

        self.assertEqual(
            extract_gate_ids(blob, file_offset=6, byte_length=len(table)),
            [7, 0x12345678, 9],
        )

    def test_rejects_invalid_length_and_out_of_bounds_slice(self) -> None:
        with self.assertRaisesRegex(ValueError, "divisible by 4"):
            parse_gate_ids(b"abc")
        with self.assertRaisesRegex(ValueError, "extends past"):
            gate_table_bytes(b"short", file_offset=3, byte_length=4)

    def test_current_reference_vector_key_values_and_fingerprint(self) -> None:
        table = pack_ids(CURRENT_REFERENCE_IDS)

        self.assertEqual(len(table), DEFAULT_TABLE_BYTE_LENGTH)
        self.assertEqual(hashlib.sha256(table).hexdigest(), REFERENCE_TABLE_SHA256)
        parsed = parse_gate_ids(table)
        self.assertEqual(len(parsed), 222)
        self.assertEqual(len(set(parsed)), 222)
        self.assertEqual(parsed[0:3], [67, 171, 603])
        self.assertEqual(parsed[119], 863)
        self.assertEqual(parsed[169:172], [9070, 9071, 16716])
        self.assertEqual(parsed[-3:], [41030, 41031, 41032])


class SoundRecordJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sound_source = make_csv_source(
            [
                {
                    "record_index": "10",
                    "sound_resource_id": "7",
                    "sound_bank": "1",
                    "suggested_name": "alpha.ogg",
                    "ogg_duration_sec": "12.5",
                },
                {
                    "record_index": "11",
                    "sound_resource_id": "7",
                    "sound_bank": "1",
                    "suggested_name": "beta.ogg",
                    "ogg_duration_sec": "20",
                },
                {
                    "record_index": "12",
                    "sound_resource_id": "9",
                    "sound_bank": "8",
                    "suggested_name": "gamma.ogg",
                    "ogg_duration_sec": "65",
                },
                {
                    "record_index": "13",
                    "sound_resource_id": "100",
                    "sound_bank": "3",
                    "suggested_name": "outside_gate.ogg",
                    "ogg_duration_sec": "5",
                },
            ],
            fieldnames=[
                "record_index",
                "sound_resource_id",
                "sound_bank",
                "suggested_name",
                "ogg_duration_sec",
            ],
            source="synthetic_sound_id_records.csv",
        )

    def test_exact_join_unmapped_bank_and_duration_statistics(self) -> None:
        table = pack_ids([7, 7, 8, 9])
        document, rows, fieldnames = build_gate_report(
            b"XX" + table,
            lib_path="synthetic.so",
            table_file_offset=2,
            table_byte_length=len(table),
            sound_source=self.sound_source,
        )

        sound = document["sound_id_records"]
        self.assertEqual(sound["matched_id_count"], 2)
        self.assertEqual(sound["matched_record_count"], 3)
        self.assertEqual(sound["unmapped_ids_table_order"], [8])
        self.assertEqual(sound["bank_statistics"]["record_counts"], {"1": 2, "8": 1})
        first = sound["mappings"][0]
        self.assertEqual(first["record_match_count"], 2)
        self.assertEqual(
            [record["values"]["suggested_name"] for record in first["records"]],
            ["alpha.ogg", "beta.ogg"],
        )
        self.assertEqual(first["records"][0]["source_row_number"], 2)

        duration = document["duration_statistics"]
        self.assertTrue(duration["available"])
        self.assertEqual(duration["source_role"], "sound_id_records")
        self.assertEqual(duration["unique_ids_with_duration"], 2)
        self.assertEqual(duration["ge_10_sec"], 2)
        self.assertEqual(duration["ge_30_sec"], 1)
        self.assertEqual(duration["ge_60_sec"], 1)
        self.assertEqual(duration["maximum_sec"], 65.0)
        self.assertEqual(
            duration["conflicting_duration_ids"],
            [{"sound_resource_id": 7, "values_sec": [12.5, 20.0]}],
        )

        # Duplicate gate entries repeat their exact mapping in the audit CSV,
        # but unique-ID statistics above are not double-counted.
        self.assertEqual(len(rows), 6)
        self.assertIn("record_suggested_name", fieldnames)
        unmapped_rows = [row for row in rows if row["sound_resource_id"] == 8]
        self.assertEqual(len(unmapped_rows), 1)
        self.assertEqual(unmapped_rows[0]["mapping_status"], "unmapped")

    def test_entitlement_offsets_are_labeled_static_read_only_evidence(self) -> None:
        table = pack_ids([7])
        document, _, _ = build_gate_report(
            table,
            lib_path="synthetic.so",
            table_file_offset=0,
            table_byte_length=4,
        )

        evidence = document["entitlement_static_evidence"]
        self.assertEqual(ENTITLEMENT_INDEX, 6)
        self.assertEqual(ACTIVE_SOUND_PACK_OFFSET, 0x14C0C)
        self.assertEqual(SAVED_SOUND_PACK_OFFSET, 0x14A70)
        self.assertTrue(evidence["version_specific"])
        self.assertFalse(document["safety"]["authorization_write_supported"])
        self.assertIn("not authorization-write targets", evidence["warning"])

    def test_explicit_duration_source_enriches_plain_sound_id_records(self) -> None:
        plain_sound_source = make_csv_source(
            [
                {"sound_resource_id": "7", "sound_bank": "1"},
                {"sound_resource_id": "8", "sound_bank": "1"},
            ],
            fieldnames=["sound_resource_id", "sound_bank"],
            source="plain_sound_id_records.csv",
        )
        duration_source = make_csv_source(
            [
                {"sound_resource_id": "7", "ogg_duration_sec": "75"},
                {"sound_resource_id": "8", "ogg_duration_sec": "2.5"},
            ],
            fieldnames=["sound_resource_id", "ogg_duration_sec"],
            source="sound_request_audit.csv",
        )
        table = pack_ids([7, 8])

        document, rows, _ = build_gate_report(
            table,
            lib_path="synthetic.so",
            table_file_offset=0,
            table_byte_length=len(table),
            sound_source=plain_sound_source,
            duration_source=duration_source,
        )

        duration = document["duration_statistics"]
        self.assertEqual(duration["source_role"], "explicit_duration_records")
        self.assertEqual(duration["source_record_count"], 2)
        self.assertEqual(duration["ge_60_sec"], 1)
        self.assertEqual(duration["lt_3_sec"], 1)
        self.assertEqual(rows[0]["representative_duration_sec"], 75.0)
        self.assertEqual(rows[1]["representative_duration_sec"], 2.5)

    def test_native_symbol_entries_are_not_confused_with_call_sites(self) -> None:
        evidence = native_call_chain_evidence()

        self.assertEqual(
            evidence["symbol_entries"]["SoundMng::play(int,int)"], "0x42601c8"
        )
        self.assertEqual(
            evidence["symbol_entries"]["SoundMng::play(unsigned char*,int,int)"],
            "0x4260464",
        )
        self.assertEqual(
            evidence["symbol_entries"]["SoundMng::sndPlayReq(int,int,int)"],
            "0x425fbdc",
        )
        play_call = evidence["call_sites"][0]
        self.assertEqual(play_call["call_site"], "0x4260384")
        self.assertEqual(play_call["call_site_offset_from_entry"], "0x1bc")
        self.assertNotEqual(play_call["caller_symbol_entry"], play_call["call_site"])

    def test_reference_policy_fails_closed_without_explicit_override(self) -> None:
        table = pack_ids([7, 8, 9])
        document, _, _ = build_gate_report(
            table,
            lib_path="unreviewed.so",
            table_file_offset=0,
            table_byte_length=len(table),
        )

        with self.assertRaisesRegex(ValueError, "Refusing to label arbitrary bytes"):
            enforce_reference_policy(document)
        enforce_reference_policy(document, allow_unmatched_reference=True)

    def test_matching_table_in_unknown_library_is_only_experimental(self) -> None:
        table = pack_ids(CURRENT_REFERENCE_IDS)
        document, _, _ = build_gate_report(
            table,
            lib_path="table-only-not-known-library.so",
            table_file_offset=0,
            table_byte_length=len(table),
        )
        self.assertTrue(document["reference_comparison"]["reference_vector_matches"])
        self.assertFalse(document["reference_comparison"]["library_sha256_matches"])
        self.assertNotEqual(document["lib_sha256"], REFERENCE_LIBRARY_SHA256)
        with self.assertRaisesRegex(ValueError, "library and fixed-offset table"):
            enforce_reference_policy(document)

    def test_cli_table_match_only_override_is_not_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            table = pack_ids(CURRENT_REFERENCE_IDS)
            lib = root / "table-only-not-known-library.so"
            lib.write_bytes(table)
            out_dir = root / "audit"
            argv = [
                "extract_sound_pack_gate.py",
                "--lib",
                str(lib),
                "--out-dir",
                str(out_dir),
                "--table-file-offset",
                "0",
                "--table-byte-length",
                str(len(table)),
                "--allow-unmatched-reference",
            ]
            stdout = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                self.assertEqual(main(), 0)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["ok"])
            self.assertTrue(result["experimental"])
            self.assertTrue(result["reference_vector_matches"])
            self.assertFalse(result["library_sha256_matches"])
            manifest = json.loads(
                (out_dir / "sound_pack_gate.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["reference_policy"]["audit_status"],
                "experimental_table_match_only",
            )

    def test_writes_json_and_csv_with_full_library_hash(self) -> None:
        table = pack_ids([7, 8, 9])
        blob = b"prefix" + table
        document, rows, fieldnames = build_gate_report(
            blob,
            lib_path="synthetic.so",
            table_file_offset=6,
            table_byte_length=len(table),
            sound_source=self.sound_source,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path, csv_path = write_gate_outputs(
                Path(temp_dir), document, rows, fieldnames
            )
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))

        self.assertEqual(loaded["lib_sha256"], hashlib.sha256(blob).hexdigest())
        self.assertEqual(loaded["table"]["ids_table_order"], [7, 8, 9])
        self.assertGreaterEqual(len(csv_rows), 4)

    def test_refuses_to_overwrite_existing_audit_outputs(self) -> None:
        table = pack_ids([7])
        document, rows, fieldnames = build_gate_report(
            table,
            lib_path="synthetic.so",
            table_file_offset=0,
            table_byte_length=len(table),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            write_gate_outputs(out_dir, document, rows, fieldnames)
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                write_gate_outputs(out_dir, document, rows, fieldnames)
            write_gate_outputs(
                out_dir, document, rows, fieldnames, overwrite=True
            )

    def test_cli_fails_closed_before_output_on_reference_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lib = root / "wrong-version.so"
            lib.write_bytes(pack_ids([7]))
            out_dir = root / "audit"
            argv = [
                "extract_sound_pack_gate.py",
                "--lib",
                str(lib),
                "--out-dir",
                str(out_dir),
                "--table-file-offset",
                "0",
                "--table-byte-length",
                "4",
            ]
            stderr = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stderr(stderr):
                self.assertEqual(main(), 4)
            self.assertFalse(out_dir.exists())
            failure = json.loads(stderr.getvalue())
            self.assertFalse(failure["ok"])
            self.assertFalse(failure["output_written"])

    def test_cli_unmatched_override_is_explicitly_experimental(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lib = root / "research-version.so"
            lib.write_bytes(pack_ids([7]))
            out_dir = root / "audit"
            argv = [
                "extract_sound_pack_gate.py",
                "--lib",
                str(lib),
                "--out-dir",
                str(out_dir),
                "--table-file-offset",
                "0",
                "--table-byte-length",
                "4",
                "--allow-unmatched-reference",
            ]
            stdout = io.StringIO()
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                self.assertEqual(main(), 0)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["ok"])
            self.assertTrue(result["experimental"])
            manifest = json.loads(
                (out_dir / "sound_pack_gate.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["reference_policy"]["audit_status"],
                "experimental_unmatched_reference",
            )


if __name__ == "__main__":
    unittest.main()
