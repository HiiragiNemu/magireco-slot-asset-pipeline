from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe import composition_contract
from tools.frida_runtime_probe import render_event_manifest
from tools.frida_runtime_probe import render_subtitle_editions


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True)


class CleanVisualPlanValidationTests(unittest.TestCase):
    def test_authored_content_tail_may_precede_quantized_frame_tail(self) -> None:
        manifest = {
            "event": "ac7116_001",
            "native_dimensions": {"width": 512, "height": 288},
            "render_duration_ms": 13033,
            "raw_render_duration_ms": 13027,
            "timeline_content_end_ms": 13027,
            "video_extension_policy": "hold_last_frame",
            "video_composition_model": "linear_full_frame_sequence",
            "composition_plan": {
                "event": "ac7116_001",
                "model": "linear_full_frame_sequence",
                "duration_ms": 13027,
                "extension_policy": "hold_last_frame",
                "native_dimensions": {"width": 512, "height": 288},
                "clips": [
                    {
                        "dgm_name": "ac7116_AT_SP_story5_01",
                        "role": "background",
                        "start_ms": 0,
                    }
                ],
            },
            "clips": [
                {
                    "dgm_name": "ac7116_AT_SP_story5_01",
                    "event_start_ms": 0,
                    "event_end_ms": 13027,
                }
            ],
        }
        validated = render_event_manifest.validate_explicit_composition_plan(manifest)
        self.assertEqual(validated["duration_ms"], 13027)

        manifest["composition_plan"]["duration_ms"] = 13026
        with self.assertRaises(RuntimeError):
            render_event_manifest.validate_explicit_composition_plan(manifest)

    def test_clean_visual_requires_bound_clip_hash_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "clip.mp4"
            source.write_bytes(b"not read by ffprobe")
            manifest = {
                "event": "ac_hash_gate_001",
                "classification": "native_full_frame_only",
                "native_dimensions": {"width": 32, "height": 32},
                "render_duration_ms": 1000,
                "video_extension_policy": "none",
                "video_composition_model": "linear_full_frame_sequence",
                "composition_plan": {
                    "model": "linear_full_frame_sequence",
                    "extension_policy": "none",
                    "clips": [{"dgm_name": "clip", "role": "segment"}],
                },
                "clips": [{"dgm_name": "clip", "path": str(source)}],
                "quality_gates": {"composition_resolved": True},
            }
            manifest_path = root / "event.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            out_root = root / "out"
            argv = [
                "render_event_manifest.py",
                "--manifest",
                str(manifest_path),
                "--out-root",
                str(out_root),
                "--clean-visual-only",
            ]
            with patch.object(sys, "argv", argv), self.assertRaisesRegex(
                SystemExit, "source_sha256"
            ):
                render_event_manifest.main()
            self.assertFalse(out_root.exists())


class CleanVisualPromotionRollbackTests(unittest.TestCase):
    @staticmethod
    def write_release(
        release_root: Path,
        published_root: Path,
        event: str,
        marker: bytes,
    ) -> None:
        video = release_root / "clean_visual" / f"{event}__clean_visual.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(marker)
        report_path = release_root / "render_manifest.json"
        report = {
            "schema": "magireco-clean-visual-render-v1",
            "status": "passed",
            "publishable": True,
            "event": event,
            "output": str(
                published_root / "clean_visual" / f"{event}__clean_visual.mp4"
            ),
            "output_sha256": render_subtitle_editions.file_sha256(video),
        }
        report_path.write_text(json.dumps(report), encoding="utf-8")
        bound_path = release_root / f"{event}.clean_visual.bound.json"
        bound_path.write_text(
            json.dumps(
                {
                    "event": event,
                    "clean_visual_master": {
                        "artifact": {
                            "path": report["output"],
                            "sha256": report["output_sha256"],
                        },
                        "render_manifest": {
                            "path": str(published_root / "render_manifest.json"),
                            "sha256": render_subtitle_editions.file_sha256(
                                report_path
                            ),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        ready = {
            "schema": render_event_manifest.CLEAN_VISUAL_READY_SCHEMA,
            "status": "READY",
            "event": event,
            "artifacts": [
                {
                    "role": "clean_visual",
                    "relative_path": video.relative_to(release_root).as_posix(),
                    "sha256": render_subtitle_editions.file_sha256(video),
                },
                {
                    "role": "render_manifest",
                    "relative_path": report_path.relative_to(
                        release_root
                    ).as_posix(),
                    "sha256": render_subtitle_editions.file_sha256(report_path),
                },
                {
                    "role": "bound_event_manifest",
                    "relative_path": bound_path.relative_to(
                        release_root
                    ).as_posix(),
                    "sha256": render_subtitle_editions.file_sha256(bound_path),
                },
            ],
        }
        (release_root / "READY.json").write_text(
            json.dumps(ready), encoding="utf-8"
        )

    @staticmethod
    def snapshot_tree(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def test_post_promotion_validation_failure_restores_old_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory)
            event = "ac_transaction_rollback_001"
            published = parent / event
            staging = parent / ".staging" / "release"
            self.write_release(published, published, event, b"old-release")
            self.write_release(staging, published, event, b"new-release")
            old_bytes = self.snapshot_tree(published)
            original_validate = render_event_manifest._validate_clean_visual_release

            def fail_after_promotion(
                release_root: Path, *, event: str, published_root: Path
            ) -> dict:
                result = original_validate(
                    release_root,
                    event=event,
                    published_root=published_root,
                )
                if release_root.resolve() == published_root.resolve():
                    raise RuntimeError("injected post-promotion failure")
                return result

            with patch.object(
                render_event_manifest,
                "_validate_clean_visual_release",
                side_effect=fail_after_promotion,
            ), self.assertRaisesRegex(RuntimeError, "injected"):
                render_event_manifest._promote_clean_visual_release(
                    staging_root=staging,
                    published_root=published,
                    event=event,
                    overwrite=True,
                )
            self.assertEqual(self.snapshot_tree(published), old_bytes)
            self.assertFalse(
                any(
                    ".previous-" in path.name or ".failed-" in path.name
                    for path in parent.iterdir()
                )
            )


@unittest.skipUnless(FFMPEG and FFPROBE, "FFmpeg and ffprobe are required")
class CleanVisualRenderEndToEndTests(unittest.TestCase):
    def test_real_tiny_render_is_video_only_and_emits_bound_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.mp4"
            run(
                [
                    str(FFMPEG),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=64x64:rate=30:duration=1",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(source),
                ]
            )
            manifest = {
                "schema": "magireco-event-production-v3",
                "event": "ac_clean_unit_001",
                "classification": "native_full_frame_only",
                "native_dimensions": {"width": 64, "height": 64},
                "native_frame_rate": "30/1",
                "video_duration_ms": 1000,
                "render_duration_ms": 1000,
                "video_extension_policy": "none",
                "video_composition_model": "linear_full_frame_sequence",
                "composition_plan": {
                    "model": "linear_full_frame_sequence",
                    "extension_policy": "none",
                    "clips": [
                        {
                            "dgm_name": "unit_source",
                            "role": "segment",
                            "start_ms": 0,
                            "end_ms": 1000,
                        }
                    ],
                },
                "composition_plan_source": "synthetic verified unit plan",
                "clips": [
                    {
                        "order": 0,
                        "dgm_name": "unit_source",
                        "dgm_role": "single_layer_segment",
                        "path": str(source),
                        "source_sha256": (
                            render_subtitle_editions.file_sha256(source)
                        ),
                        "event_start_ms": 0,
                        "event_end_ms": 1000,
                        "interval_confidence": "exact_unit_fixture",
                    }
                ],
                # Deliberately present: clean mode must not map this audio.
                "audio": [{"path": str(root / "must_not_be_read.wav")}],
                "subtitles": [{"text": "must not be rendered"}],
                "quality_gates": {
                    # Audio readiness is intentionally false: the visual stage
                    # must depend only on the resolved composition contract.
                    "ready": False,
                    "composition_resolved": True,
                    "errors": ["audio_master_contract_unresolved"],
                },
            }
            manifest_path = root / "event.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            source_manifest_before = manifest_path.read_bytes()
            out_root = root / "out"
            argv = [
                "render_event_manifest.py",
                "--manifest",
                str(manifest_path),
                "--out-root",
                str(out_root),
                "--ffmpeg",
                str(FFMPEG),
                "--ffprobe",
                str(FFPROBE),
                "--clean-visual-only",
            ]
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(
                io.StringIO()
            ) as stdout:
                self.assertEqual(render_event_manifest.main(), 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["schema"], "magireco-clean-visual-render-v1")
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["publishable"])
            output = Path(result["output"])
            self.assertTrue(output.is_file())
            output_probe = render_subtitle_editions.probe(output, str(FFPROBE))
            self.assertEqual(
                [
                    row["codec_type"]
                    for row in output_probe["streams"]
                    if row.get("codec_type") == "audio"
                ],
                [],
            )
            video = next(
                row
                for row in output_probe["streams"]
                if row.get("codec_type") == "video"
            )
            self.assertEqual(video["codec_name"], "h264")
            self.assertEqual((video["width"], video["height"]), (64, 64))
            self.assertEqual(video["r_frame_rate"], "30/1")
            self.assertTrue(result["qa"]["checks"]["no_audio_stream"])

            report_path = Path(result["render_manifest"]["path"])
            bound_path = Path(result["bound_event_manifest"]["path"])
            self.assertTrue(report_path.is_file())
            self.assertTrue(bound_path.is_file())
            ready_path = Path(result["ready_marker"]["path"])
            self.assertTrue(ready_path.is_file())
            self.assertEqual(
                json.loads(ready_path.read_text(encoding="utf-8"))["schema"],
                render_event_manifest.CLEAN_VISUAL_READY_SCHEMA,
            )
            bound = json.loads(bound_path.read_text(encoding="utf-8"))
            self.assertIn("clean_visual_master", bound)
            self.assertNotIn(
                "clean_visual_master",
                json.loads(manifest_path.read_text(encoding="utf-8")),
            )
            self.assertEqual(manifest_path.read_bytes(), source_manifest_before)
            self.assertEqual(
                result["source_composition_contract_sha256"],
                composition_contract.composition_contract_sha256(bound),
            )

    def test_source_change_after_render_start_preserves_old_ready_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.mp4"
            run(
                [
                    str(FFMPEG),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=blue:size=32x32:rate=30:duration=1",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(source),
                ]
            )
            event = "ac_clean_transaction_001"
            manifest = {
                "schema": "magireco-event-production-v3",
                "event": event,
                "classification": "native_full_frame_only",
                "native_dimensions": {"width": 32, "height": 32},
                "native_frame_rate": "30/1",
                "video_duration_ms": 1000,
                "render_duration_ms": 1000,
                "video_extension_policy": "none",
                "video_composition_model": "linear_full_frame_sequence",
                "composition_plan": {
                    "model": "linear_full_frame_sequence",
                    "extension_policy": "none",
                    "clips": [
                        {
                            "dgm_name": "unit_source",
                            "role": "segment",
                            "start_ms": 0,
                            "end_ms": 1000,
                        }
                    ],
                },
                "clips": [
                    {
                        "order": 0,
                        "dgm_name": "unit_source",
                        "path": str(source),
                        "source_sha256": (
                            render_subtitle_editions.file_sha256(source)
                        ),
                        "event_start_ms": 0,
                        "event_end_ms": 1000,
                    }
                ],
                "audio": [],
                "subtitles": [],
                "quality_gates": {"composition_resolved": True},
            }
            manifest_path = root / "event.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            out_parent = root / "out"

            def invoke(*, overwrite: bool = False) -> int:
                argv = [
                    "render_event_manifest.py",
                    "--manifest",
                    str(manifest_path),
                    "--out-root",
                    str(out_parent),
                    "--ffmpeg",
                    str(FFMPEG),
                    "--ffprobe",
                    str(FFPROBE),
                    "--clean-visual-only",
                ]
                if overwrite:
                    argv.append("--overwrite")
                with patch.object(sys, "argv", argv), contextlib.redirect_stdout(
                    io.StringIO()
                ):
                    return render_event_manifest.main()

            self.assertEqual(invoke(), 0)
            published = out_parent / event

            def snapshot_tree(path: Path) -> dict[str, bytes]:
                return {
                    item.relative_to(path).as_posix(): item.read_bytes()
                    for item in sorted(path.rglob("*"))
                    if item.is_file()
                }

            old_release = snapshot_tree(published)
            original_probe = render_event_manifest.production_probe
            changed = False

            def mutate_source_after_render(path: Path, ffprobe: str) -> dict:
                nonlocal changed
                payload = original_probe(path, ffprobe)
                if not changed:
                    source.write_bytes(source.read_bytes() + b"source-mutated")
                    changed = True
                return payload

            with patch.object(
                render_event_manifest,
                "production_probe",
                side_effect=mutate_source_after_render,
            ), self.assertRaisesRegex(SystemExit, "source changed during render"):
                invoke(overwrite=True)
            self.assertEqual(snapshot_tree(published), old_release)
            self.assertFalse(
                any("clean-visual-staging" in item.name for item in out_parent.iterdir())
            )


if __name__ == "__main__":
    unittest.main()
