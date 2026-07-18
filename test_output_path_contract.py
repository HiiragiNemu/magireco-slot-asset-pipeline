from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe import build_material_collection
from tools.frida_runtime_probe import build_event_production_manifests
from tools.frida_runtime_probe import build_scene_editions
from tools.frida_runtime_probe import build_series_editions
from tools.frida_runtime_probe import render_event_manifest
from tools.frida_runtime_probe import render_subtitle_editions
from tools.frida_runtime_probe.output_path_contract import (
    UnsafeOutputIdentifier,
    resolve_output_child,
    validate_output_identifier,
)


class OutputPathContractTests(unittest.TestCase):
    def test_existing_production_identifiers_remain_compatible(self) -> None:
        valid = (
            "ac7114_16_sp_story_clean_audio_gate",
            "ac1102",
            "ac0921_001",
            "named_material",
            "小丘比_素材合集-01",
        )
        for identifier in valid:
            with self.subTest(identifier=identifier):
                self.assertEqual(validate_output_identifier(identifier), identifier)

    def test_path_syntax_ads_reserved_tail_and_controls_are_rejected(self) -> None:
        invalid = (
            "",
            ".",
            "..",
            "../escape",
            "..\\escape",
            "/absolute",
            "C:\\absolute",
            "C:drive-relative",
            "\\\\server\\share",
            "event/child",
            "event\\child",
            "event:stream",
            "CON",
            "con.json",
            "LPT1.release",
            "NUL.txt",
            "event.",
            "event ",
            "event\nname",
            "event\x7fname",
            "event?name",
        )
        for identifier in invalid:
            with self.subTest(identifier=repr(identifier)):
                with self.assertRaises(UnsafeOutputIdentifier):
                    validate_output_identifier(identifier)

    def test_non_string_identifier_is_rejected(self) -> None:
        for value in (None, 7, ["ac0001"]):
            with self.subTest(value=value):
                with self.assertRaises(UnsafeOutputIdentifier):
                    validate_output_identifier(value)

    def test_existing_symlink_escape_is_rejected_after_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = Path(temp_dir)
            root = parent / "root"
            outside = parent / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "ac0001"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink creation is unavailable: {error}")
            with self.assertRaisesRegex(UnsafeOutputIdentifier, "escapes"):
                resolve_output_child(root, "ac0001", label="event")

    def test_contained_nonexistent_child_is_returned_under_resolved_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "out"
            child = resolve_output_child(root, "ac0001_001", label="event")
            self.assertEqual(child, root.resolve() / "ac0001_001")
            self.assertFalse(root.exists())


class OutputEntryTraversalTests(unittest.TestCase):
    def test_production_manifest_builder_rejects_catalog_and_plan_traversal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            catalog = root / "catalog.csv"
            catalog.write_text(
                "event_name,automatic_candidate,classification\n"
                "../escaped,yes,native_full_frame_only\n",
                encoding="utf-8",
            )
            out_root = root / "production-out"
            argv = [
                "build_event_production_manifests.py",
                "--event-catalog",
                str(catalog),
                "--event-clips",
                str(root / "not-read-clips.csv"),
                "--audio-components",
                str(root / "not-read-audio.csv"),
                "--event-sounds",
                str(root / "not-read-sounds.csv"),
                "--subtitle-timeline",
                str(root / "not-read-subtitles.csv"),
                "--out-dir",
                str(out_root),
            ]
            sentinel = root / "escaped.json"
            sentinel.write_bytes(b"unchanged")
            with patch.object(sys, "argv", argv), self.assertRaises(
                UnsafeOutputIdentifier
            ):
                build_event_production_manifests.main()
            self.assertEqual(sentinel.read_bytes(), b"unchanged")
            self.assertFalse(out_root.exists())

            plans = root / "plans"
            plans.mkdir()
            (plans / "hostile.json").write_text(
                json.dumps({"event": "..\\escaped"}), encoding="utf-8"
            )
            with self.assertRaises(UnsafeOutputIdentifier):
                build_event_production_manifests.load_composition_plans(plans)

    def test_scene_entry_rejects_traversal_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_root = Path(temp_dir) / "scene-out"
            with self.assertRaises(UnsafeOutputIdentifier):
                build_scene_editions.build_verified_scene(
                    "../escaped",
                    [],
                    out_root,
                    None,
                    "ffmpeg",
                    "ffprobe",
                    False,
                )
            self.assertFalse(out_root.exists())

    def test_series_entry_rejects_traversal_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_root = Path(temp_dir) / "series-out"
            with self.assertRaises(UnsafeOutputIdentifier):
                build_series_editions.build_series(
                    "../escaped",
                    {},
                    set(),
                    out_root,
                    None,
                    True,
                    "ffmpeg",
                    "ffprobe",
                    False,
                )
            self.assertFalse(out_root.exists())

    def test_material_entries_reject_series_and_plan_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_dir = root / "manifests"
            manifest_dir.mkdir()
            direct_out = root / "direct-out"
            with self.assertRaises(UnsafeOutputIdentifier):
                build_material_collection.build_collection(
                    "../escaped",
                    manifest_dir,
                    direct_out,
                    "ffmpeg",
                    "ffprobe",
                    False,
                )
            self.assertFalse(direct_out.exists())

            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps({"collection": "..\\escaped", "clips": []}),
                encoding="utf-8",
            )
            named_out = root / "named-out"
            with self.assertRaises(UnsafeOutputIdentifier):
                build_material_collection.build_named_collection(
                    plan_path,
                    {},
                    named_out,
                    "ffmpeg",
                    "ffprobe",
                    False,
                )
            self.assertFalse(named_out.exists())

    def test_material_manifest_event_rejects_traversal_before_media_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifests = root / "manifests"
            manifests.mkdir()
            # Five parent components would escape
            # out/.material-staging-*/ac9000/audit/audible_event_visuals.
            hostile_event = "../../../../../outside"
            (manifests / "ac9000_001.json").write_text(
                json.dumps(
                    {
                        "event": hostile_event,
                        "audience_exclusion_reason": "reviewed component route",
                        "quality_gates": {
                            "errors": ["audience_component_only"]
                        },
                        "clips": [
                            {
                                "path": str(root / "would-not-be-read.mp4"),
                                "dgm_name": "hostile",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            sentinel = root / "outside.ffconcat"
            sentinel.write_bytes(b"must remain unchanged")
            out_root = root / "out"
            with patch.object(
                build_material_collection.subprocess,
                "run",
                side_effect=AssertionError("ffmpeg must not run"),
            ), self.assertRaises(UnsafeOutputIdentifier):
                build_material_collection.build_collection(
                    "ac9000",
                    manifests,
                    out_root,
                    "ffmpeg",
                    "ffprobe",
                    False,
                )
            self.assertEqual(sentinel.read_bytes(), b"must remain unchanged")
            self.assertFalse((root / "outside.mp4").exists())
            self.assertTrue(out_root.is_dir())
            self.assertEqual(list(out_root.iterdir()), [])

    def test_subtitle_batch_entry_rejects_manifest_event_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "event.json"
            manifest_path.write_text(
                json.dumps({"event": "../escaped"}), encoding="utf-8"
            )
            out_root = root / "subtitle-out"
            with self.assertRaises(UnsafeOutputIdentifier):
                render_subtitle_editions.execute_render_batch(
                    planned=[
                        (
                            manifest_path,
                            {"event": "../escaped"},
                        )
                    ],
                    base_video_dirs={},
                    out_root=out_root,
                    workers=1,
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    manifest_root=root,
                    expected_event_index=None,
                    legacy_two_edition=True,
                )
            self.assertFalse(out_root.exists())

    def test_event_renderer_rejects_manifest_event_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "event.json"
            manifest_path.write_text(
                json.dumps({"event": "../escaped"}), encoding="utf-8"
            )
            out_root = root / "event-out"
            argv = [
                "render_event_manifest.py",
                "--manifest",
                str(manifest_path),
                "--out-root",
                str(out_root),
            ]
            with patch.object(sys, "argv", argv), self.assertRaises(
                UnsafeOutputIdentifier
            ):
                render_event_manifest.main()
            self.assertFalse(out_root.exists())


if __name__ == "__main__":
    unittest.main()
