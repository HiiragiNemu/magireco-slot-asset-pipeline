from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe import build_scene_editions


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class BuildSceneReleaseGateTests(unittest.TestCase):
    maxDiff = None

    def make_fixture(self, root: Path) -> dict:
        input_root = root / "input"
        input_root.mkdir()
        events = ("ac7114_001", "ac7115_001")
        (input_root / "full_qa_audit.csv").write_text(
            "event,status\n" + "".join(f"{event},passed\n" for event in events),
            encoding="utf-8",
        )
        packet_by_edition = {
            "none": "1" * 64,
            "ja": "2" * 64,
            "zh": "3" * 64,
        }
        audio_by_profile = {"with_bgm": "A" * 64, "no_bgm": "B" * 64}
        for event in events:
            event_dir = input_root / event
            event_dir.mkdir()
            source_manifest = event_dir / "event_manifest.json"
            source_manifest.write_text(
                json.dumps(
                    {
                        "event": event,
                        "native_frame_rate": "30/1",
                        "render_frame_count": 30,
                        "render_duration_ms": 1000,
                        "render_duration_quantization": {
                            "frame_rate": "30/1",
                            "frame_count": 30,
                            "content_end_ms": 1000,
                            "duration_ms": 1000,
                            "exact_duration_ms_numerator": 1000,
                            "exact_duration_ms_denominator": 1,
                            "audio_sample_rate": 48000,
                            "audio_sample_count": 48000,
                        },
                    }
                ),
                encoding="utf-8",
            )
            subtitles = {}
            for edition, text in (("ja", "日本語"), ("zh", "中文")):
                subtitle = event_dir / f"{edition}.srt"
                subtitle.write_text(
                    f"1\n00:00:00,100 --> 00:00:00,800\n{text}\n",
                    encoding="utf-8",
                )
                subtitles[edition] = subtitle
            matrix = {}
            for profile in ("with_bgm", "no_bgm"):
                editions = {}
                for edition in ("none", "ja", "zh"):
                    video = event_dir / f"{profile}-{edition}.mp4"
                    video.write_bytes(f"{event}:{profile}:{edition}".encode())
                    subtitle = subtitles.get(edition)
                    editions[edition] = {
                        "language": edition,
                        "video": str(video),
                        "subtitles": str(subtitle) if subtitle else "",
                        "video_sha256": sha256(video),
                        "video_packet_sha256": packet_by_edition[edition],
                        "audio_sha256": audio_by_profile[profile],
                        "subtitle_sha256": sha256(subtitle) if subtitle else "",
                    }
                matrix[profile] = {
                    "audio_profile": profile,
                    "audio_sha256": audio_by_profile[profile],
                    "editions": editions,
                }
            (event_dir / "render_manifest.json").write_text(
                json.dumps(
                    {
                        "event": event,
                        "source_manifest": str(source_manifest),
                        "source_manifest_sha256": sha256(source_manifest),
                        "edition_matrix": matrix,
                        "edition_plan": {
                            "event": event,
                            "tracks": {
                                "ja": {
                                    "cue_count": 1,
                                    "cues": [
                                        {
                                            "start_ms": 100,
                                            "end_ms": 800,
                                            "text": "日本語",
                                        }
                                    ],
                                },
                                "zh": {
                                    "cue_count": 1,
                                    "cues": [
                                        {
                                            "start_ms": 100,
                                            "end_ms": 800,
                                            "text": "中文",
                                        }
                                    ],
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
        return {"input_root": input_root, "events": events}

    @staticmethod
    def fake_probe(path: Path, _ffprobe: str) -> dict:
        duration = "2.0" if "__scene" in path.name else "1.0"
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "profile": "High",
                    "level": 31,
                    "width": 416,
                    "height": 232,
                    "pix_fmt": "yuv420p",
                    "r_frame_rate": "30/1",
                    "time_base": "1/15360",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                    "channel_layout": "stereo",
                    "time_base": "1/48000",
                },
            ],
            "format": {"duration": duration},
        }

    @staticmethod
    def fake_concat(
        sources: list[Path],
        list_path: Path,
        output_path: Path,
        _ffmpeg: str,
        _overwrite: bool,
    ) -> None:
        list_path.parent.mkdir(parents=True, exist_ok=True)
        list_path.write_text(
            "ffconcat version 1.0\n"
            + "\n".join(build_scene_editions.ffconcat_line(path) for path in sources)
            + "\n",
            encoding="utf-8",
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"ordered-stream-copy")

    @staticmethod
    def fake_audio_hash(path: Path, _ffmpeg: str) -> str:
        return "A" * 64 if "with_bgm" in str(path) else "B" * 64

    @staticmethod
    def fake_decoded_pcm(path: Path, _ffmpeg: str) -> str:
        return "C" * 64 if "with_bgm" in str(path) else "D" * 64

    @staticmethod
    def fake_video_packet(path: Path, _ffmpeg: str) -> str:
        value = str(path)
        if (
            "without_subtitles" in value
            or value.endswith("-none.mp4")
            or "__none__video_only" in value
        ):
            return "1" * 64
        if (
            "with_subtitles_zh" in value
            or value.endswith("-zh.mp4")
            or "__zh__video_only" in value
        ):
            return "3" * 64
        return "2" * 64

    @classmethod
    def fake_decoded_video(cls, path: Path, ffmpeg: str) -> str:
        return cls.fake_video_packet(path, ffmpeg)

    @staticmethod
    def fake_timeline(
        _path: Path,
        _ffprobe: str,
        *,
        expected_duration_ms: int,
        expected_frame_rate: str,
        label: str,
    ) -> dict:
        return {
            "schema": "test-timeline",
            "status": "passed",
            "timeline_sha256": "9" * 64,
            "frame_rate": expected_frame_rate,
            "frame_count": expected_duration_ms * 30 // 1000,
            "packet_count": expected_duration_ms * 30 // 1000,
            "label": label,
        }

    @classmethod
    def fake_concat_decoded_hash(
        cls, list_path: Path, media_type: str, _ffmpeg: str
    ) -> str:
        if media_type == "audio":
            return "C" * 64 if "with_bgm" in list_path.name else "D" * 64
        edition = list_path.stem.rsplit("__", 1)[-1]
        return {"none": "1" * 64, "ja": "2" * 64, "zh": "3" * 64}[edition]

    def build(self, fixture: dict, root: Path, **kwargs: object) -> dict:
        candidates = build_scene_editions.discover_events(
            [fixture["input_root"]], allow_legacy=False
        )
        selected = [candidates[event] for event in kwargs.pop("events", fixture["events"])]
        decoded_side_effect = kwargs.pop("decoded_pcm", self.fake_decoded_pcm)
        concat_side_effect = kwargs.pop("concat", self.fake_concat)
        write_srt_side_effect = kwargs.pop("write_srt", build_scene_editions.write_srt)
        mux_side_effect = kwargs.pop("mux", None)
        overwrite = bool(kwargs.pop("overwrite", True))
        scene = str(kwargs.pop("scene", "sp_story_clean"))
        if kwargs:
            raise AssertionError(f"unexpected build test options: {sorted(kwargs)}")

        def fake_audio_presentation(
            path: Path,
            _media_probe: dict,
            video_timeline: dict,
            _ffprobe: str,
            ffmpeg: str,
            *,
            expected_samples: int | None = None,
        ) -> dict:
            return {
                "expected_presentation_samples": (
                    expected_samples
                    if expected_samples is not None
                    else int(video_timeline["frame_count"]) * 1600
                ),
                "packet_frame_timeline": {
                    "schema": "test-audio-timeline",
                    "timeline_sha256": "8" * 64,
                },
                "effective_decoded_pcm": {
                    "pcm_sha256": decoded_side_effect(path, ffmpeg),
                },
            }

        def fake_sidecar(row: dict, profile: str) -> dict:
            path = Path(row["render_manifest_path"])
            digest = sha256(path)
            return {
                "path": str(path),
                "sha256": digest,
                "locator": f"fake {profile} sidecar",
                "presentation_sample_count": 48000,
                "encoding": {
                    "codec": "aac",
                    "sample_rate": 48000,
                    "channels": 2,
                    "channel_layout": "stereo",
                    "bit_rate": 128000,
                },
                "effective_pcm_sha256": (
                    "C" * 64 if profile == "with_bgm" else "D" * 64
                ),
                "audio_packet_sha256": (
                    "A" * 64 if profile == "with_bgm" else "B" * 64
                ),
                "ready_marker": {
                    "path": str(path),
                    "sha256": digest,
                    "locator": "fake ready marker",
                },
            }

        def fake_build_audio_master(
            segments: list[dict],
            output_path: Path,
            target_bit_rate: int,
            _ffmpeg: str,
            _overwrite: bool,
        ) -> dict:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"single-scene-aac")
            return {
                "method": "effective_pcm_concat_then_single_aac_encode",
                "codec": "aac",
                "sample_rate": 48000,
                "channels": 2,
                "channel_layout": "stereo",
                "target_bit_rate": target_bit_rate,
                "presentation_sample_count": sum(
                    int(row["presentation_sample_count"]) for row in segments
                ),
                "segments": [
                    {
                        **row,
                        "path": str(row["path"]),
                    }
                    for row in segments
                ],
            }

        def fake_audio_master_audit(
            path: Path,
            expected_samples: int,
            target_bit_rate: int,
            _ffprobe: str,
            ffmpeg: str,
        ) -> dict:
            return {
                "expected_presentation_samples": expected_samples,
                "target_bit_rate": target_bit_rate,
                "actual_bit_rate": target_bit_rate,
                "audio_packet_sha256": self.fake_audio_hash(path, ffmpeg),
                "packet_frame_timeline": {"timeline_sha256": "8" * 64},
                "effective_decoded_pcm": {
                    "pcm_sha256": self.fake_decoded_pcm(path, ffmpeg)
                },
            }

        def fake_mux(
            _video_path: Path,
            _audio_path: Path,
            output_path: Path,
            _ffmpeg: str,
            _overwrite: bool,
        ) -> None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"muxed-scene")

        if mux_side_effect is None:
            mux_side_effect = fake_mux

        with patch.object(
            build_scene_editions, "probe", side_effect=self.fake_probe
        ), patch.object(
            build_scene_editions,
            "concat_video_copy",
            side_effect=concat_side_effect,
        ), patch.object(
            build_scene_editions,
            "build_scene_audio_master",
            side_effect=fake_build_audio_master,
        ), patch.object(
            build_scene_editions,
            "audit_audio_only_master",
            side_effect=fake_audio_master_audit,
        ), patch.object(
            build_scene_editions,
            "mux_scene_av_copy",
            side_effect=mux_side_effect,
        ), patch.object(
            build_scene_editions,
            "load_scene_audio_sidecar",
            side_effect=fake_sidecar,
        ), patch.object(
            build_scene_editions, "audio_hash", side_effect=self.fake_audio_hash
        ), patch.object(
            build_scene_editions,
            "audio_presentation_audit",
            side_effect=fake_audio_presentation,
        ), patch.object(
            build_scene_editions,
            "probe_video_timeline",
            side_effect=self.fake_timeline,
        ), patch.object(
            build_scene_editions,
            "concat_decoded_hash",
            side_effect=self.fake_concat_decoded_hash,
        ), patch.object(
            build_scene_editions,
            "concat_stream_hash",
            side_effect=lambda path, media_type, ffmpeg: (
                self.fake_audio_hash(path, ffmpeg)
                if media_type == "audio"
                else self.fake_video_packet(path, ffmpeg)
            ),
        ), patch.object(
            build_scene_editions,
            "decoded_video_hash",
            side_effect=self.fake_decoded_video,
        ), patch.object(
            build_scene_editions,
            "write_srt",
            side_effect=write_srt_side_effect,
        ), patch.object(
            build_scene_editions.series_gate,
            "audio_hash",
            side_effect=self.fake_audio_hash,
        ), patch.object(
            build_scene_editions.series_gate,
            "video_packet_hash",
            side_effect=self.fake_video_packet,
        ):
            return build_scene_editions.build_verified_scene(
                scene,
                selected,
                root / "out",
                None,
                "ffmpeg",
                "ffprobe",
                overwrite,
            )

    def test_complete_six_route_build_preserves_explicit_event_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            requested_order = tuple(reversed(fixture["events"]))
            result = self.build(fixture, root, events=requested_order)

            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["release_eligible"])
            self.assertEqual(
                [row["event"] for row in manifest["sources"]],
                list(requested_order),
            )
            self.assertEqual(
                set(manifest["outputs"]["edition_matrix"]),
                {"with_bgm", "no_bgm"},
            )
            for profile in ("with_bgm", "no_bgm"):
                self.assertEqual(
                    set(manifest["outputs"]["edition_matrix"][profile]["editions"]),
                    {"none", "ja", "zh"},
                )
            ready = root / "out" / "sp_story_clean" / "READY.json"
            self.assertTrue(ready.is_file())
            self.assertEqual(json.loads(ready.read_text())["status"], "READY")
            scene_dir = ready.parent
            for path in scene_dir.rglob("*"):
                if path.suffix in {".json", ".csv", ".srt", ".ffconcat"}:
                    self.assertNotIn(
                        ".scene-staging-",
                        path.read_text(encoding="utf-8-sig"),
                    )

    def test_existing_ready_without_overwrite_fails_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            self.build(fixture, root)
            scene_dir = root / "out" / "sp_story_clean"
            before = {
                path.relative_to(scene_dir).as_posix(): (
                    sha256(path),
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                )
                for path in scene_dir.rglob("*")
                if path.is_file()
            }

            with patch.object(
                build_scene_editions.tempfile, "mkdtemp"
            ) as staging_factory:
                with self.assertRaisesRegex(FileExistsError, "READY"):
                    self.build(fixture, root, overwrite=False)
                staging_factory.assert_not_called()

            after = {
                path.relative_to(scene_dir).as_posix(): (
                    sha256(path),
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                )
                for path in scene_dir.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_failed_rerun_preserves_previous_ready_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            result = self.build(fixture, root)
            scene_dir = root / "out" / "sp_story_clean"
            manifest_path = Path(result["manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            six_videos = [
                Path(edition["video"])
                for profile in manifest["outputs"]["edition_matrix"].values()
                for edition in profile["editions"].values()
            ]
            self.assertEqual(len(six_videos), 6)
            ready_path = scene_dir / "READY.json"
            tracked = [*six_videos, manifest_path, ready_path]
            before = {str(path): sha256(path) for path in tracked}
            before_release_tree = {
                path.relative_to(scene_dir).as_posix(): sha256(path)
                for path in scene_dir.rglob("*")
                if path.is_file()
            }
            mux_calls = 0

            def fail_during_fourth_mux(
                _video_path: Path,
                _audio_path: Path,
                output_path: Path,
                _ffmpeg: str,
                _overwrite: bool,
            ) -> None:
                nonlocal mux_calls
                mux_calls += 1
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(f"rerun-{mux_calls}".encode())
                if mux_calls == 4:
                    raise RuntimeError("injected mux failure")

            with self.assertRaisesRegex(RuntimeError, "injected mux failure"):
                self.build(
                    fixture,
                    root,
                    overwrite=True,
                    mux=fail_during_fourth_mux,
                )

            self.assertEqual(mux_calls, 4)
            self.assertEqual({str(path): sha256(path) for path in tracked}, before)
            self.assertEqual(
                {
                    path.relative_to(scene_dir).as_posix(): sha256(path)
                    for path in scene_dir.rglob("*")
                    if path.is_file()
                },
                before_release_tree,
            )
            self.assertEqual(
                json.loads(ready_path.read_text(encoding="utf-8"))["status"],
                "READY",
            )
            self.assertFalse(list((root / "out").glob(".scene-staging-*")))
            self.assertFalse(
                list((root / "out").glob(".sp_story_clean.previous-*"))
            )

    def test_scene_ready_summary_hash_survives_another_scene_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            self.build(fixture, root, scene="scene_one")
            first_ready_path = root / "out" / "scene_one" / "READY.json"
            first_ready = json.loads(first_ready_path.read_text(encoding="utf-8"))
            first_summary = Path(first_ready["summary"])
            first_summary_sha256 = sha256(first_summary)

            self.build(fixture, root, scene="scene_two")
            second_ready = json.loads(
                (root / "out" / "scene_two" / "READY.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(first_summary.parent.name, "scene_one")
            self.assertNotEqual(first_ready["summary"], second_ready["summary"])
            self.assertEqual(first_summary_sha256, first_ready["summary_sha256"])
            self.assertEqual(sha256(first_summary), first_ready["summary_sha256"])

    def test_synchronized_missing_srt_cues_fail_against_edition_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            event = fixture["events"][0]
            event_dir = fixture["input_root"] / event
            render_path = event_dir / "render_manifest.json"
            render_manifest = json.loads(render_path.read_text(encoding="utf-8"))
            for language in ("ja", "zh"):
                subtitle = event_dir / f"{language}.srt"
                subtitle.write_text("", encoding="utf-8")
                for profile in ("with_bgm", "no_bgm"):
                    render_manifest["edition_matrix"][profile]["editions"][language][
                        "subtitle_sha256"
                    ] = sha256(subtitle)
            render_path.write_text(json.dumps(render_manifest), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError, "parsed SRT does not match audited edition_plan cues"
            ):
                self.build(fixture, root)
            self.assertFalse(
                (root / "out" / "sp_story_clean" / "READY.json").exists()
            )

    def test_written_scene_srt_is_round_trip_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            original_write_srt = build_scene_editions.write_srt

            def dropping_writer(path: Path, cues: list[dict]) -> None:
                original_write_srt(path, cues[:-1])

            with self.assertRaisesRegex(
                RuntimeError, "written SRT round-trip mismatch"
            ):
                self.build(fixture, root, write_srt=dropping_writer)
            self.assertFalse(
                (root / "out" / "sp_story_clean" / "READY.json").exists()
            )

    def test_video_presentation_samples_support_fractional_frame_rates(self) -> None:
        self.assertEqual(
            build_scene_editions.video_presentation_sample_count(
                frame_count=24,
                frame_rate="24000/1001",
            ),
            48048,
        )

    def test_missing_matrix_route_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            candidates = build_scene_editions.discover_events(
                [fixture["input_root"]], allow_legacy=False
            )
            del candidates[fixture["events"][0]]["edition_matrix"]["no_bgm"][
                "editions"
            ]["zh"]
            with self.assertRaisesRegex(ValueError, "missing profiles=.*editions"):
                build_scene_editions.build_verified_scene(
                    "sp_story_clean",
                    [candidates[event] for event in fixture["events"]],
                    root / "out",
                    None,
                    "ffmpeg",
                    "ffprobe",
                    True,
                )
            self.assertFalse(
                (root / "out" / "sp_story_clean" / "READY.json").exists()
            )

    def test_sidecar_sample_count_and_encoding_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "base.mp4"
            output.write_bytes(b"base")
            sidecar = root / "base.manifest.json"
            payload = {
                "schema": "magireco-audio-base-master-render-v1",
                "status": "passed",
                "publishable": True,
                "event": "ac7114_001",
                "audio_profile": "with_bgm",
                "source_event_contract_sha256": "1" * 64,
                "output": str(output),
                "output_audio_packet_sha256": "A" * 64,
                "output_effective_decoded_pcm_sha256": "C" * 64,
                "presentation_sample_count": 48000,
                "render_method": {
                    "output_encoding_contract": {
                        "codec": "aac",
                        "sample_rate": 48000,
                        "channels": 2,
                        "channel_layout": "stereo",
                        "bit_rate": 128000,
                    }
                },
            }
            sidecar.write_text(json.dumps(payload), encoding="utf-8")
            row = {
                "event": "ac7114_001",
                "render_manifest_path": str(root / "render_manifest.json"),
                "render_manifest": {
                    "base_master_manifests": {
                        "with_bgm": {
                            "path": str(sidecar),
                            "sha256": sha256(sidecar),
                            "locator": "verified base master",
                            "manifest": payload,
                        }
                    }
                },
            }
            with patch.object(
                build_scene_editions,
                "validate_transaction_ready_marker",
                return_value={
                    "path": str(sidecar),
                    "sha256": sha256(sidecar),
                    "locator": "ready",
                },
            ):
                result = build_scene_editions.load_scene_audio_sidecar(
                    row, "with_bgm"
                )
            self.assertEqual(result["presentation_sample_count"], 48000)
            self.assertEqual(result["encoding"]["bit_rate"], 128000)
            payload["presentation_sample_count"] = 0
            sidecar.write_text(json.dumps(payload), encoding="utf-8")
            row["render_manifest"]["base_master_manifests"]["with_bgm"][
                "sha256"
            ] = sha256(sidecar)
            row["render_manifest"]["base_master_manifests"]["with_bgm"][
                "manifest"
            ] = payload
            with self.assertRaisesRegex(ValueError, "sample_count is invalid"):
                build_scene_editions.load_scene_audio_sidecar(row, "with_bgm")

    def test_altered_ffconcat_order_and_audio_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)

            def reversed_concat(
                sources: list[Path],
                list_path: Path,
                output_path: Path,
                ffmpeg: str,
                overwrite: bool,
            ) -> None:
                self.fake_concat(
                    list(reversed(sources)),
                    list_path,
                    output_path,
                    ffmpeg,
                    overwrite,
                )

            with self.assertRaisesRegex(ValueError, "explicit event order was altered"):
                self.build(fixture, root, concat=reversed_concat)
            self.assertFalse(
                (root / "out" / "sp_story_clean" / "READY.json").exists()
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)

            def output_pcm_tamper(path: Path, ffmpeg: str) -> str:
                if "__scene" in path.name:
                    return "E" * 64
                return self.fake_decoded_pcm(path, ffmpeg)

            with self.assertRaisesRegex(
                RuntimeError, "audio_master_profiles_decoded_pcm_identical"
            ):
                self.build(fixture, root, decoded_pcm=output_pcm_tamper)
            self.assertFalse(
                (root / "out" / "sp_story_clean").exists()
            )
            self.assertFalse(list((root / "out").glob(".scene-staging-*")))

    @unittest.skipUnless(
        shutil.which("ffmpeg"),
        "ffmpeg is required for the real stream-copy hash audit",
    )
    def test_real_concat_copy_hashes_and_rejects_aac_padding_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sources = []
            for index, colour in enumerate(("red", "blue"), start=1):
                source = root / f"segment-{index}.mp4"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c={colour}:size=160x90:rate=30:duration=0.5",
                        "-f",
                        "lavfi",
                        "-i",
                        f"sine=frequency={400 + index * 100}:sample_rate=48000:duration=0.5",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-g",
                        "15",
                        "-c:a",
                        "aac",
                        "-ar",
                        "48000",
                        "-ac",
                        "2",
                        "-shortest",
                        str(source),
                    ],
                    check=True,
                )
                sources.append(source)
            concat_list = root / "ordered.ffconcat"
            output = root / "joined.mp4"
            build_scene_editions.concat_copy(
                sources, concat_list, output, "ffmpeg", True
            )
            build_scene_editions.verify_ffconcat_order(concat_list, sources)
            self.assertEqual(
                build_scene_editions.concat_decoded_hash(
                    concat_list, "video", "ffmpeg"
                ),
                build_scene_editions.decoded_video_hash(output, "ffmpeg"),
            )
            self.assertEqual(
                build_scene_editions.concat_stream_hash(
                    concat_list, "audio", "ffmpeg"
                ),
                build_scene_editions.audio_hash(output, "ffmpeg"),
            )
            video_timeline = build_scene_editions.probe_video_timeline(
                output,
                "ffprobe",
                expected_duration_ms=1000,
                expected_frame_rate="30/1",
                label="real joined scene",
            )
            with self.assertRaisesRegex(
                RuntimeError, "presentation endpoint|decoded-frame"
            ):
                build_scene_editions.audio_presentation_audit(
                    output,
                    build_scene_editions.probe(output, "ffprobe"),
                    video_timeline,
                    "ffprobe",
                    "ffmpeg",
                )

            video_list = root / "video-only.ffconcat"
            video_only = root / "video-only.mp4"
            build_scene_editions.concat_video_copy(
                sources, video_list, video_only, "ffmpeg", True
            )
            audio_master = root / "scene-audio.m4a"
            provenance = build_scene_editions.build_scene_audio_master(
                [
                    {
                        "event": f"event-{index}",
                        "path": source,
                        "presentation_sample_count": 24000,
                        "sidecar": str(source),
                        "sidecar_sha256": sha256(source),
                    }
                    for index, source in enumerate(sources, start=1)
                ],
                audio_master,
                128000,
                "ffmpeg",
                True,
            )
            self.assertEqual(provenance["presentation_sample_count"], 48000)
            master_audit = build_scene_editions.audit_audio_only_master(
                audio_master, 48000, 128000, "ffprobe", "ffmpeg"
            )
            final = root / "scene-final.mp4"
            build_scene_editions.mux_scene_av_copy(
                video_only, audio_master, final, "ffmpeg", True
            )
            final_video_timeline = build_scene_editions.probe_video_timeline(
                final,
                "ffprobe",
                expected_duration_ms=1000,
                expected_frame_rate="30/1",
                label="single-encode scene",
            )
            self.assertEqual(
                final_video_timeline["timeline_sha256"],
                video_timeline["timeline_sha256"],
            )
            final_audio_audit = build_scene_editions.audio_presentation_audit(
                final,
                build_scene_editions.probe(final, "ffprobe"),
                final_video_timeline,
                "ffprobe",
                "ffmpeg",
            )
            self.assertEqual(
                final_audio_audit["effective_decoded_pcm"]["pcm_sha256"],
                master_audit["effective_decoded_pcm"]["pcm_sha256"],
            )
            self.assertEqual(
                build_scene_editions.series_gate.video_packet_hash(
                    final, "ffmpeg"
                ),
                build_scene_editions.series_gate.video_packet_hash(
                    video_only, "ffmpeg"
                ),
            )


if __name__ == "__main__":
    unittest.main()
