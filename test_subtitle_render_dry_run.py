from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe import build_scene_editions
from tools.frida_runtime_probe import build_series_editions
from tools.frida_runtime_probe import render_event_manifest
from tools.frida_runtime_probe import render_subtitle_editions


def synthetic_video_timeline_payload(
    frame_ticks: list[int], *, time_base: str = "1/30"
) -> dict:
    frames = [
        {"best_effort_timestamp": tick} for tick in frame_ticks
    ]
    packets = [
        {"pts": tick, "dts": tick, "duration": 1}
        for tick in frame_ticks
    ]
    return {
        "frames": frames,
        "packets": packets,
        "streams": [
            {
                "index": 0,
                "time_base": time_base,
                "r_frame_rate": "30/1",
                "avg_frame_rate": "30/1",
                "duration": f"{len(frame_ticks) / 30:.6f}",
                "nb_frames": str(len(frame_ticks)),
                "nb_read_frames": str(len(frame_ticks)),
            }
        ],
    }


class SubtitleRenderDryRunTests(unittest.TestCase):
    def test_srt_round_trip_rejects_dropped_cue_text_and_one_ms_drift(self) -> None:
        cues = [
            {"start_ms": 100, "end_ms": 900, "text": "一行目"},
            {"start_ms": 1000, "end_ms": 1900, "text": "第二行\n続き"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "track.srt"
            render_subtitle_editions.write_srt(path, cues)
            passed = render_subtitle_editions.validate_srt_against_edition_plan(
                path,
                cues,
                event="ac0001_001",
                language="ja",
            )
            self.assertEqual(passed["cue_count"], 2)

            render_subtitle_editions.write_srt(path, cues[:1])
            with self.assertRaisesRegex(RuntimeError, "cue count"):
                render_subtitle_editions.validate_srt_against_edition_plan(
                    path, cues, event="ac0001_001", language="ja"
                )

            render_subtitle_editions.write_srt(path, cues)
            path.write_text(
                path.read_text(encoding="utf-8").replace("第二行", "改変"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "text mismatch"):
                render_subtitle_editions.validate_srt_against_edition_plan(
                    path, cues, event="ac0001_001", language="ja"
                )

            render_subtitle_editions.write_srt(path, cues)
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "00:00:01,000 -->", "00:00:01,001 -->"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "start_ms mismatch"):
                render_subtitle_editions.validate_srt_against_edition_plan(
                    path, cues, event="ac0001_001", language="ja"
                )

    def test_source_snapshot_covers_manifest_masters_sidecars_ready_and_font(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_root = root / "manifests"
            manifest_root.mkdir()
            manifest = manifest_root / "ac0001_001.json"
            manifest.write_text(
                json.dumps({"event": "ac0001_001"}), encoding="utf-8"
            )
            font = root / "font.ttf"
            font.write_bytes(b"font")
            base_dirs = {}
            sidecars = {}
            for profile in ("with_bgm", "no_bgm"):
                base_dir = root / profile
                base_dir.mkdir()
                (base_dir / "ac0001_001.mp4").write_bytes(profile.encode())
                base_dirs[profile] = base_dir
                sidecars[profile] = root / f"{profile}.json"
            ready = root / "audio.READY.json"
            ready.write_text(
                json.dumps(
                    {
                        "profiles": {
                            profile: {
                                "video": str(
                                    base_dirs[profile] / "ac0001_001.mp4"
                                ),
                                "base_master_manifest": str(sidecars[profile]),
                            }
                            for profile in ("with_bgm", "no_bgm")
                        }
                    }
                ),
                encoding="utf-8",
            )
            for sidecar in sidecars.values():
                sidecar.write_text(
                    json.dumps(
                        {
                            "transaction_ready_marker": {
                                "path": str(ready),
                            }
                        }
                    ),
                    encoding="utf-8",
                )
            plan = {
                "requested_audio_profiles": ["with_bgm", "no_bgm"],
                "tracks": {
                    "ja": {
                        "cues": [{"start_ms": 0, "end_ms": 1, "text": "字"}],
                        "font": {"path": str(font)},
                    },
                    "zh": {"cues": [], "font": None},
                },
                "audio_master_contract": {
                    "profiles": {
                        profile: {
                            "base_master_manifest": {
                                "path": str(sidecars[profile])
                            }
                        }
                        for profile in ("with_bgm", "no_bgm")
                    }
                },
            }
            planned = [(manifest, plan)]
            start = render_subtitle_editions.capture_render_source_snapshot(
                planned, base_dirs
            )
            roles = {
                role
                for row in start["sources"]
                for role in row["roles"]
            }
            self.assertIn("ac0001_001:source_manifest", roles)
            self.assertIn("ac0001_001:with_bgm:base_video", roles)
            self.assertIn("ac0001_001:no_bgm:base_master_sidecar", roles)
            self.assertIn("ac0001_001:audio_transaction_READY", roles)
            self.assertIn("ac0001_001:ja:font", roles)

            original = font.read_bytes()
            font.write_bytes(original + b"-changed-during-render")
            end = render_subtitle_editions.capture_render_source_snapshot(
                planned, base_dirs
            )
            with self.assertRaisesRegex(RuntimeError, "TOCTOU"):
                render_subtitle_editions.assert_render_source_snapshot_unchanged(
                    start, end
                )

    def test_mid_render_source_tamper_and_worker_failure_preserve_old_batch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_root = root / "manifests"
            manifest_root.mkdir()
            manifest = manifest_root / "ac0001_001.json"
            manifest.write_text(
                json.dumps({"event": "ac0001_001"}), encoding="utf-8"
            )
            base_dir = root / "base"
            base_dir.mkdir()
            base = base_dir / "ac0001_001.mp4"
            base.write_bytes(b"stable-source")
            out_root = root / "published"
            out_root.mkdir()
            sentinel = out_root / "old-batch.txt"
            sentinel.write_bytes(b"previous verified batch")
            plan = {
                "requested_editions": ["none", "ja"],
                "requested_audio_profiles": [
                    render_subtitle_editions.LEGACY_AUDIO_PROFILE
                ],
                "tracks": {"ja": {"cues": [], "font": None}},
            }
            kwargs = {
                "planned": [(manifest, plan)],
                "base_video_dirs": {
                    render_subtitle_editions.LEGACY_AUDIO_PROFILE: base_dir
                },
                "out_root": out_root,
                "workers": 1,
                "ffmpeg": "ffmpeg",
                "ffprobe": "ffprobe",
                "manifest_root": manifest_root,
                "expected_event_index": None,
                "legacy_two_edition": True,
                "overwrite": True,
            }

            def tamper(*args, **_kwargs):
                staging = args[3]
                (staging / "partial").mkdir()
                base.write_bytes(b"changed while worker was rendering")
                return {"event": "ac0001_001"}

            with patch.object(
                render_subtitle_editions, "render_one", side_effect=tamper
            ), self.assertRaisesRegex(RuntimeError, "changed during batch"):
                render_subtitle_editions.execute_render_batch(**kwargs)
            self.assertEqual(sentinel.read_bytes(), b"previous verified batch")
            self.assertFalse(
                list(root.glob(".published.staging-*")),
                "failed TOCTOU batch left a staging directory",
            )

            base.write_bytes(b"stable-source")

            def fail_worker(*args, **_kwargs):
                staging = args[3]
                (staging / "partial-worker-output").mkdir()
                raise RuntimeError("injected worker failure")

            with patch.object(
                render_subtitle_editions,
                "render_one",
                side_effect=fail_worker,
            ), self.assertRaisesRegex(RuntimeError, "injected worker failure"):
                render_subtitle_editions.execute_render_batch(**kwargs)
            self.assertEqual(sentinel.read_bytes(), b"previous verified batch")
            self.assertEqual([path.name for path in out_root.iterdir()], [sentinel.name])
            self.assertFalse(
                list(root.glob(".published.staging-*")),
                "worker failure left a staging directory",
            )

    def test_complete_ready_batch_replaces_old_root_only_after_verification(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_root = root / "published"
            out_root.mkdir()
            (out_root / "old.txt").write_text("old", encoding="utf-8")
            staging = root / ".published.staging-unit"
            event_dir = staging / "ac0001_001"
            event_dir.mkdir(parents=True)
            video = staging / "without_subtitles" / "ac0001_001.mp4"
            video.parent.mkdir()
            video.write_bytes(b"verified-video")
            published_video = out_root / video.relative_to(staging)
            (event_dir / "render_manifest.json").write_text(
                json.dumps(
                    {
                        "event": "ac0001_001",
                        "edition_plan": {"tracks": {"ja": {"cues": []}}},
                        "editions": {
                            "none": {
                                "video": str(published_video),
                                "video_sha256": hashlib.sha256(
                                    video.read_bytes()
                                ).hexdigest().upper(),
                                "subtitles": "",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            snapshot_hash = render_subtitle_editions.canonical_sha256([])
            snapshot = {
                "schema": render_subtitle_editions.SOURCE_SNAPSHOT_SCHEMA,
                "sources": [],
                "snapshot_sha256": snapshot_hash,
            }
            summary = {
                "publication_eligible": True,
                "expected_event_index": None,
                "source_snapshot": snapshot,
                "events_detail": [{"event": "ac0001_001"}],
            }
            (staging / "subtitle_editions_summary.json").write_text(
                json.dumps(summary), encoding="utf-8"
            )
            render_subtitle_editions._write_batch_ready_marker(
                staging_root=staging,
                publication_root=out_root,
                summary=summary,
                source_snapshot_start=snapshot,
                source_snapshot_end=snapshot,
            )

            marker = render_subtitle_editions.promote_staged_subtitle_batch(
                staging, out_root, overwrite=True
            )

            self.assertEqual(marker["status"], "ready")
            self.assertTrue(marker["publishable"])
            self.assertFalse((out_root / "old.txt").exists())
            self.assertTrue(
                (out_root / render_subtitle_editions.SUBTITLE_BATCH_READY_FILENAME).is_file()
            )
            self.assertFalse(list(root.glob(".published.previous-*")))

    def test_existing_batch_requires_explicit_overwrite_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_root = root / "manifests"
            manifest_root.mkdir()
            manifest = manifest_root / "ac0001_001.json"
            manifest.write_text(
                json.dumps({"event": "ac0001_001"}), encoding="utf-8"
            )
            base_dir = root / "base"
            base_dir.mkdir()
            (base_dir / "ac0001_001.mp4").write_bytes(b"stable-source")
            out_root = root / "published"
            out_root.mkdir()
            sentinel = out_root / "old.txt"
            sentinel.write_bytes(b"old-ready-tree")
            plan = {
                "requested_editions": ["none", "ja"],
                "requested_audio_profiles": [
                    render_subtitle_editions.LEGACY_AUDIO_PROFILE
                ],
                "tracks": {"ja": {"cues": [], "font": None}},
            }
            with self.assertRaisesRegex(FileExistsError, "--overwrite"):
                render_subtitle_editions.execute_render_batch(
                    planned=[(manifest, plan)],
                    base_video_dirs={
                        render_subtitle_editions.LEGACY_AUDIO_PROFILE: base_dir
                    },
                    out_root=out_root,
                    workers=1,
                    ffmpeg="ffmpeg",
                    ffprobe="ffprobe",
                    manifest_root=manifest_root,
                    expected_event_index=None,
                    legacy_two_edition=True,
                )
            self.assertEqual(sentinel.read_bytes(), b"old-ready-tree")
            self.assertFalse(list(root.glob(".published.staging-*")))

    def test_output_root_cannot_overlap_manifest_or_media_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_root = root / "manifests"
            manifest_root.mkdir()
            manifest = manifest_root / "ac0001_001.json"
            manifest.write_text(
                json.dumps({"event": "ac0001_001"}), encoding="utf-8"
            )
            base_dir = root / "base"
            base_dir.mkdir()
            base = base_dir / "ac0001_001.mp4"
            base.write_bytes(b"stable-source")
            plan = {
                "requested_editions": ["none", "ja"],
                "requested_audio_profiles": [
                    render_subtitle_editions.LEGACY_AUDIO_PROFILE
                ],
                "tracks": {"ja": {"cues": [], "font": None}},
            }
            for out_root in (manifest_root / "published", base_dir / "published"):
                with self.subTest(out_root=out_root), self.assertRaisesRegex(
                    RuntimeError, "overlaps a protected input root"
                ):
                    render_subtitle_editions.execute_render_batch(
                        planned=[(manifest, plan)],
                        base_video_dirs={
                            render_subtitle_editions.LEGACY_AUDIO_PROFILE: base_dir
                        },
                        out_root=out_root,
                        workers=1,
                        ffmpeg="ffmpeg",
                        ffprobe="ffprobe",
                        manifest_root=manifest_root,
                        expected_event_index=None,
                        legacy_two_edition=True,
                    )
                self.assertFalse(out_root.exists())
                self.assertEqual(manifest.read_text(encoding="utf-8"), '{"event": "ac0001_001"}')
                self.assertEqual(base.read_bytes(), b"stable-source")

    def test_video_timeline_audit_hashes_exact_frame_and_packet_pts(self) -> None:
        first = render_subtitle_editions.validate_video_timeline_payload(
            synthetic_video_timeline_payload([0, 1, 2]),
            expected_duration_ms=100,
            expected_frame_rate="30/1",
            label="synthetic CFR",
        )
        second_payload = synthetic_video_timeline_payload(
            [0, 1000, 2000], time_base="1/30000"
        )
        for packet in second_payload["packets"]:
            packet["duration"] = 1000
        second = render_subtitle_editions.validate_video_timeline_payload(
            second_payload,
            expected_duration_ms=100,
            expected_frame_rate="30/1",
            label="synthetic CFR alternate time base",
        )

        self.assertEqual(first["status"], "passed")
        self.assertEqual(first["frame_count"], 3)
        self.assertEqual(first["packet_count"], 3)
        self.assertEqual(first["timeline_sha256"], second["timeline_sha256"])

    def test_video_timeline_audit_rejects_vfr_gap_and_nonzero_start(self) -> None:
        gap = synthetic_video_timeline_payload([0, 1, 3])
        with self.assertRaisesRegex(RuntimeError, "VFR/discontinuous"):
            render_subtitle_editions.validate_video_timeline_payload(
                gap,
                expected_duration_ms=100,
                expected_frame_rate="30/1",
                label="synthetic gap",
            )

        shifted = synthetic_video_timeline_payload([2, 3, 4])
        with self.assertRaisesRegex(RuntimeError, "more than one frame from zero"):
            render_subtitle_editions.validate_video_timeline_payload(
                shifted,
                expected_duration_ms=100,
                expected_frame_rate="30/1",
                label="synthetic shifted",
            )

    def test_video_identity_gate_rejects_cross_master_timeline_or_packet_drift(
        self,
    ) -> None:
        profiles = ["with_bgm", "no_bgm"]
        editions = ["none", "ja", "zh"]
        packets = {
            profile: {edition: "A" * 64 for edition in editions}
            for profile in profiles
        }
        timelines = {
            profile: {edition: "B" * 64 for edition in editions}
            for profile in profiles
        }
        with self.assertRaisesRegex(RuntimeError, "ja video timelines differ"):
            drifted = json.loads(json.dumps(timelines))
            drifted["no_bgm"]["ja"] = "C" * 64
            render_subtitle_editions.validate_video_identity_across_audio_masters(
                event="ac0001_001",
                profiles=profiles,
                editions=editions,
                source_packet_sha256_by_profile={
                    profile: "D" * 64 for profile in profiles
                },
                source_timeline_sha256_by_profile={
                    profile: "E" * 64 for profile in profiles
                },
                packet_sha256_by_profile_and_edition=packets,
                timeline_sha256_by_profile_and_edition=drifted,
            )

        with self.assertRaisesRegex(RuntimeError, "same encoded video stream"):
            render_subtitle_editions.validate_video_identity_across_audio_masters(
                event="ac0001_001",
                profiles=profiles,
                editions=editions,
                source_packet_sha256_by_profile={
                    "with_bgm": "D" * 64,
                    "no_bgm": "F" * 64,
                },
                source_timeline_sha256_by_profile={
                    profile: "E" * 64 for profile in profiles
                },
                packet_sha256_by_profile_and_edition=packets,
                timeline_sha256_by_profile_and_edition=timelines,
            )

        with self.assertRaisesRegex(RuntimeError, "zh video packets differ"):
            drifted_packets = json.loads(json.dumps(packets))
            drifted_packets["no_bgm"]["zh"] = "F" * 64
            render_subtitle_editions.validate_video_identity_across_audio_masters(
                event="ac0001_001",
                profiles=profiles,
                editions=editions,
                source_packet_sha256_by_profile={
                    profile: "D" * 64 for profile in profiles
                },
                source_timeline_sha256_by_profile={
                    profile: "E" * 64 for profile in profiles
                },
                packet_sha256_by_profile_and_edition=drifted_packets,
                timeline_sha256_by_profile_and_edition=timelines,
            )

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "ffmpeg/ffprobe are required for the real timestamp audit",
    )
    def test_real_ffprobe_timeline_accepts_cfr_and_rejects_dropped_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cfr = root / "cfr.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=160x90:rate=30:duration=1",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(cfr),
                ],
                check=True,
            )
            audit = render_subtitle_editions.probe_video_timeline(
                cfr,
                "ffprobe",
                expected_duration_ms=1000,
                expected_frame_rate="30/1",
                label="real CFR",
            )
            self.assertEqual(audit["frame_count"], 30)

            vfr = root / "dropped-frame.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=160x90:rate=30:duration=1",
                    "-vf",
                    "select=not(eq(n\\,15))",
                    "-fps_mode",
                    "vfr",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(vfr),
                ],
                check=True,
            )
            with self.assertRaisesRegex(
                RuntimeError, "avg_frame_rate|VFR/discontinuous"
            ):
                render_subtitle_editions.probe_video_timeline(
                    vfr,
                    "ffprobe",
                    expected_duration_ms=1000,
                    expected_frame_rate="30/1",
                    label="real dropped frame",
                )

    def test_event_contract_projection_breaks_sidecar_hash_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "event.json"
            payload = {
                "event": "ac0001_001",
                "audio_master_contract": {
                    "profiles": {"with_bgm": {"bgm_layers": []}}
                },
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            before = render_subtitle_editions.event_contract_projection_sha256(path)
            payload["audio_master_contract"]["profiles"]["with_bgm"][
                "base_master_manifest"
            ] = {"path": "sidecar.json", "sha256": "A" * 64}
            path.write_text(json.dumps(payload), encoding="utf-8")

            self.assertEqual(
                before,
                render_subtitle_editions.event_contract_projection_sha256(path),
            )

    def test_short_audio_stream_and_low_spec_audio_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "duration"):
            render_subtitle_editions.validate_stream_coverage(
                {"start_time": "0", "duration": "1.0"},
                expected_duration_ms=2000,
                label="audio",
            )
        with self.assertRaisesRegex(RuntimeError, "audio signature"):
            render_subtitle_editions.validate_native_audio_signature(
                {
                    "codec_name": "aac",
                    "sample_rate": "44100",
                    "channels": 1,
                    "channel_layout": "mono",
                },
                label="audio",
            )

    def test_verified_audio_masters_must_differ_as_decoded_pcm(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "identical PCM"):
            render_subtitle_editions.validate_audio_master_distinction(
                {"with_bgm": "A" * 64, "no_bgm": "B" * 64},
                {"with_bgm": "C" * 64, "no_bgm": "C" * 64},
            )

    def test_verified_render_requires_base_master_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event_manifest = root / "event.json"
            base = root / "base.mp4"
            event_manifest.write_text(
                json.dumps({"render_duration_ms": 1000}), encoding="utf-8"
            )
            base.write_bytes(b"not-used-before-binding-check")
            with self.assertRaisesRegex(RuntimeError, "base_master_manifest"):
                render_subtitle_editions.validate_base_master_manifest(
                    event="ac0001_001",
                    profile="with_bgm",
                    base_path=base,
                    profile_contract={},
                    event_manifest_path=event_manifest,
                    base_probe={},
                    audio_packet_sha256="A" * 64,
                    decoded_pcm_sha256="B" * 64,
                    video_packet_sha256="C" * 64,
                    video_timeline_sha256="D" * 64,
                )

    def test_event_dry_run_accepts_legacy_two_edition_manifest_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "ac0001_001.json"
            out_root = root / "must_not_exist"
            manifest_path.write_text(
                json.dumps(
                    {
                        "event": "ac0001_001",
                        "classification": "native_full_frame_only",
                        "quality_gates": {"ready": True, "errors": []},
                        "subtitles": [],
                        "audio": [],
                    }
                ),
                encoding="utf-8",
            )
            argv = [
                "render_event_manifest.py",
                "--manifest",
                str(manifest_path),
                "--out-root",
                str(out_root),
                "--dry-run",
                "--legacy-two-edition",
            ]
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(
                io.StringIO()
            ) as output:
                result = render_event_manifest.main()

            self.assertEqual(result, 0)
            self.assertFalse(out_root.exists())
            payload = json.loads(output.getvalue())
            self.assertEqual(
                payload["edition_plan"]["requested_editions"], ["none", "ja"]
            )

    def test_bulk_dry_run_plans_three_editions_without_writes_or_media_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_root = root / "manifests"
            event_dir = manifest_root / "events"
            with_bgm_dir = root / "with_bgm"
            no_bgm_dir = root / "no_bgm"
            out_root = root / "must_not_exist"
            event_dir.mkdir(parents=True)
            with_bgm_dir.mkdir()
            no_bgm_dir.mkdir()
            for base_dir in (with_bgm_dir, no_bgm_dir):
                (base_dir / "ac0001_001.mp4").write_bytes(
                    b"dry-run-placeholder"
                )
            bgm = root / "bgm.wav"
            with wave.open(str(bgm), "wb") as writer:
                writer.setnchannels(2)
                writer.setsampwidth(2)
                writer.setframerate(48000)
                writer.writeframes(b"\0\0\0\0" * 48000)
            bgm_hash = hashlib.sha256(bgm.read_bytes()).hexdigest().upper()
            runtime_evidence = root / "runtime-evidence.jsonl"
            runtime_evidence.write_bytes(b'{"verified":true}\n')
            runtime_evidence_hash = hashlib.sha256(
                runtime_evidence.read_bytes()
            ).hexdigest().upper()
            evidence_reference = {
                "path": str(runtime_evidence),
                "sha256": runtime_evidence_hash,
                "locator": "dry-run evidence row 1",
            }
            profile_evidence = {
                "kind": "official_runtime",
                "references": [evidence_reference],
                "fields": ["voice_se_preserved", "bgm_policy"],
            }
            (event_dir / "ac0001_001.json").write_text(
                json.dumps(
                    {
                        "event": "ac0001_001",
                        "quality_gates": {"ready": True},
                        "render_duration_ms": 1000,
                        "subtitle_tracks": {"ja": [], "zh": []},
                        "audio": [],
                        "audio_master_contract": {
                            "schema": "magireco-audio-master-contract-v1",
                            "voice_se_timeline": [],
                            "profiles": {
                                "no_bgm": {
                                    "evidence": profile_evidence,
                                    "bgm_layers": [],
                                },
                                "with_bgm": {
                                    "evidence": profile_evidence,
                                    "bgm_layers": [
                                        {
                                            "source": {
                                                "path": str(bgm),
                                                "sha256": bgm_hash,
                                            },
                                            "start_ms": 0,
                                            "end_ms": 1000,
                                            "source_offset_ms": 0,
                                            "loop": False,
                                            "loop_start_ms": None,
                                            "loop_end_ms": None,
                                            "volume": 1.0,
                                            "volume_unit": "linear",
                                            "volume_transitions": [
                                                {
                                                    "at_ms": 0,
                                                    "volume": 1.0,
                                                    "volume_unit": "linear",
                                                    "kind": "initial",
                                                }
                                            ],
                                            "evidence": {
                                                "kind": "verified_static_logic",
                                                "references": [evidence_reference],
                                                "fields": [
                                                    "source",
                                                    "timing",
                                                    "volume",
                                                    "loop_phase",
                                                    "transitions",
                                                ],
                                            },
                                        }
                                    ],
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            argv = [
                "render_subtitle_editions.py",
                "--manifest-root",
                str(manifest_root),
                "--with-bgm-base-video-dir",
                str(with_bgm_dir),
                "--no-bgm-base-video-dir",
                str(no_bgm_dir),
                "--out-root",
                str(out_root),
                "--dry-run",
            ]
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(
                io.StringIO()
            ) as output:
                result = render_subtitle_editions.main()

            self.assertEqual(result, 0)
            self.assertFalse(out_root.exists())
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["requested_editions"], ["none", "ja", "zh"])
            self.assertEqual(
                payload["requested_audio_profiles"], ["with_bgm", "no_bgm"]
            )
            self.assertEqual(payload["edition_count_per_event"], 6)
            self.assertFalse(payload["plans"][0]["translation_performed"])

            publication_argv = [value for value in argv if value != "--dry-run"]
            with patch.object(sys, "argv", publication_argv), self.assertRaisesRegex(
                SystemExit, "expected-event-index"
            ):
                render_subtitle_editions.main()

    def test_bulk_renderer_writes_per_event_modern_and_legacy_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "ac0001_001.json"
            base_dir = root / "base"
            out_root = root / "out"
            base_dir.mkdir()
            (base_dir / "ac0001_001.mp4").write_bytes(b"base-media")
            manifest_path.write_text(
                json.dumps(
                    {
                        "event": "ac0001_001",
                        "native_dimensions": {"width": 416, "height": 232},
                        "native_frame_rate": "30/1",
                        "render_duration_ms": 2000,
                    }
                ),
                encoding="utf-8",
            )
            plan = {
                "schema": "magireco-subtitle-edition-plan-v2",
                "requested_editions": ["none", "ja"],
                "requested_audio_profiles": ["legacy_unclassified"],
                "audio_master_contract": None,
                "tracks": {
                    "ja": {"cue_count": 0, "cues": [], "font": None}
                },
            }
            fake_probe = {
                "streams": [
                    {
                        "codec_name": "h264",
                        "codec_type": "video",
                        "profile": "High",
                        "level": 31,
                        "width": 416,
                        "height": 232,
                        "r_frame_rate": "30/1",
                        "pix_fmt": "yuv420p",
                        "bit_rate": "1500000",
                    },
                    {
                        "codec_name": "aac",
                        "codec_type": "audio",
                        "sample_rate": "48000",
                        "channels": 2,
                        "channel_layout": "stereo",
                        "time_base": "1/48000",
                    },
                ]
            }
            with patch.object(
                render_subtitle_editions, "probe", return_value=fake_probe
            ), patch.object(
                render_subtitle_editions, "audio_hash", return_value="AUDIO"
            ), patch.object(
                render_subtitle_editions,
                "video_packet_hash",
                return_value="VIDEO",
            ):
                row = render_subtitle_editions.render_one(
                    manifest_path,
                    plan,
                    {"legacy_unclassified": base_dir},
                    out_root,
                    "ffmpeg",
                    "ffprobe",
                )

            render_manifest = Path(row["render_manifest"])
            payload = json.loads(render_manifest.read_text(encoding="utf-8"))
            self.assertEqual(set(payload["editions"]), {"none", "ja"})
            self.assertEqual(
                payload["with_subtitles"], payload["editions"]["ja"]["video"]
            )
            self.assertEqual(payload["shared_audio_sha256"], "AUDIO")

    def test_bulk_renderer_materializes_six_entry_matrix_from_two_masters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "ac0001_001.json"
            with_bgm_dir = root / "with_bgm"
            no_bgm_dir = root / "no_bgm"
            out_root = root / "out"
            with_bgm_dir.mkdir()
            no_bgm_dir.mkdir()
            (with_bgm_dir / "ac0001_001.mp4").write_bytes(b"with-bgm")
            (no_bgm_dir / "ac0001_001.mp4").write_bytes(b"no-bgm")
            manifest_path.write_text(
                json.dumps(
                    {
                        "event": "ac0001_001",
                        "native_dimensions": {"width": 416, "height": 232},
                        "native_frame_rate": "30/1",
                        "render_duration_ms": 2000,
                    }
                ),
                encoding="utf-8",
            )
            event_contract_sha256 = (
                render_subtitle_editions.event_contract_projection_sha256(
                    manifest_path
                )
            )
            profile_rows = {}
            for profile, audio_packet_sha256, decoded_sha256 in (
                ("with_bgm", "A" * 64, "D" * 64),
                ("no_bgm", "B" * 64, "E" * 64),
            ):
                base_path = (
                    with_bgm_dir if profile == "with_bgm" else no_bgm_dir
                ) / "ac0001_001.mp4"
                source_layers = {
                    "voice_se": [],
                    "bgm_layers": (
                        [{"source": "unit-test-bgm"}]
                        if profile == "with_bgm"
                        else []
                    ),
                }
                audio_timeline_sha256 = (
                    render_subtitle_editions.canonical_sha256(source_layers)
                )
                sidecar = root / f"{profile}-base-master.json"
                profile_rows[profile] = {
                    "audio_packet_sha256": audio_packet_sha256,
                    "decoded_sha256": decoded_sha256,
                    "base_path": base_path,
                    "source_layers": source_layers,
                    "audio_timeline_sha256": audio_timeline_sha256,
                    "sidecar": sidecar,
                }
            ready_path = root / "ac0001_001.audio-base-masters.ready.json"
            ready_path.write_text(
                json.dumps(
                    {
                        "schema": (
                            render_subtitle_editions.BASE_MASTER_READY_SCHEMA
                        ),
                        "status": "ready",
                        "publishable": True,
                        "event": "ac0001_001",
                        "source_event_contract_sha256": event_contract_sha256,
                        "profiles": {
                            profile: {
                                "video": str(row["base_path"]),
                                "video_sha256": hashlib.sha256(
                                    row["base_path"].read_bytes()
                                ).hexdigest().upper(),
                                "base_master_manifest": str(row["sidecar"]),
                                "audio_timeline_sha256": row[
                                    "audio_timeline_sha256"
                                ],
                            }
                            for profile, row in profile_rows.items()
                        },
                        "publication_rule": (
                            render_subtitle_editions.BASE_MASTER_READY_PUBLICATION_RULE
                        ),
                    }
                ),
                encoding="utf-8",
            )
            ready_reference = {
                "path": str(ready_path),
                "sha256": hashlib.sha256(
                    ready_path.read_bytes()
                ).hexdigest().upper(),
                "locator": "unit-test complete two-profile transaction",
            }
            profile_contracts = {}
            for profile, row in profile_rows.items():
                base_path = row["base_path"]
                source_layers = row["source_layers"]
                audio_timeline_sha256 = row["audio_timeline_sha256"]
                sidecar = row["sidecar"]
                sidecar.write_text(
                    json.dumps(
                        {
                            "schema": "magireco-audio-base-master-render-v1",
                            "status": "passed",
                            "publishable": True,
                            "event": "ac0001_001",
                            "audio_profile": profile,
                            "source_event_contract_sha256": event_contract_sha256,
                            "voice_se_timeline_sha256": "F" * 64,
                            "audio_timeline_sha256": audio_timeline_sha256,
                            "output": str(base_path.resolve()),
                            "output_sha256": hashlib.sha256(
                                base_path.read_bytes()
                            ).hexdigest().upper(),
                            "output_audio_packet_sha256": row[
                                "audio_packet_sha256"
                            ],
                            "output_decoded_pcm_sha256": row["decoded_sha256"],
                            "output_video_packet_sha256": "C" * 64,
                            "output_video_timeline_sha256": "9" * 64,
                            "duration_ms": 2000,
                            "presentation_sample_count": 96000,
                            "audio_encoding_signature": [
                                "aac",
                                "48000",
                                "2",
                                "stereo",
                                "1/48000",
                            ],
                            "video_encoding_signature": [
                                "h264",
                                "High",
                                "31",
                                416,
                                232,
                                "yuv420p",
                                "30/1",
                            ],
                            "source_layers": source_layers,
                            "qa": {"status": "passed", "errors": []},
                            "transaction_ready_marker": ready_reference,
                        }
                    ),
                    encoding="utf-8",
                )
                profile_contracts[profile] = {
                    "voice_se_timeline_sha256": "F" * 64,
                    "audio_timeline_sha256": audio_timeline_sha256,
                    "base_master_manifest": {
                        "path": str(sidecar),
                        "sha256": hashlib.sha256(
                            sidecar.read_bytes()
                        ).hexdigest().upper(),
                        "locator": "unit-test complete base master",
                    },
                }
            plan = {
                "schema": "magireco-subtitle-edition-plan-v2",
                "requested_editions": ["none", "ja", "zh"],
                "requested_audio_profiles": ["with_bgm", "no_bgm"],
                "audio_master_contract": {
                    "profiles": profile_contracts
                },
                "tracks": {
                    language: {"cue_count": 0, "cues": [], "font": None}
                    for language in ("ja", "zh")
                },
            }
            fake_probe = {
                "streams": [
                    {
                        "codec_name": "h264",
                        "codec_type": "video",
                        "profile": "High",
                        "level": 31,
                        "width": 416,
                        "height": 232,
                        "r_frame_rate": "30/1",
                        "pix_fmt": "yuv420p",
                        "bit_rate": "1500000",
                        "duration": "2.000000",
                        "start_time": "0.000000",
                        "nb_frames": "60",
                        "nb_read_frames": "60",
                    },
                    {
                        "codec_name": "aac",
                        "codec_type": "audio",
                        "sample_rate": "48000",
                        "channels": 2,
                        "channel_layout": "stereo",
                        "time_base": "1/48000",
                        "duration": "2.000000",
                        "start_time": "0.000000",
                    },
                ],
                "format": {"duration": "2.000000"},
            }

            def fake_audio_hash(path: Path, _ffmpeg: str) -> str:
                return "A" * 64 if "with_bgm" in str(path) else "B" * 64

            with patch.object(
                render_subtitle_editions, "probe", return_value=fake_probe
            ), patch.object(
                render_subtitle_editions,
                "audio_hash",
                side_effect=fake_audio_hash,
            ), patch.object(
                render_subtitle_editions,
                "video_packet_hash",
                return_value="C" * 64,
            ), patch.object(
                render_subtitle_editions,
                "decoded_pcm_hash",
                side_effect=lambda path, _ffmpeg: (
                    "D" * 64 if "with_bgm" in str(path) else "E" * 64
                ),
            ), patch.object(
                render_subtitle_editions,
                "probe_video_timeline",
                return_value={
                    "schema": "magireco-video-presentation-timeline-v1",
                    "status": "passed",
                    "timeline_sha256": "9" * 64,
                    "frame_rate": "30/1",
                    "frame_count": 60,
                    "packet_count": 60,
                },
            ):
                row = render_subtitle_editions.render_one(
                    manifest_path,
                    plan,
                    {"with_bgm": with_bgm_dir, "no_bgm": no_bgm_dir},
                    out_root,
                    "ffmpeg",
                    "ffprobe",
                )

            payload = json.loads(
                Path(row["render_manifest"]).read_text(encoding="utf-8")
            )
            self.assertEqual(set(payload["edition_matrix"]), {"with_bgm", "no_bgm"})
            self.assertEqual(
                set(payload["edition_matrix"]["with_bgm"]["editions"]),
                {"none", "ja", "zh"},
            )
            self.assertFalse(payload["legacy_schema_compatible"])
            self.assertEqual(
                payload["source_video_timeline_sha256_by_profile"],
                {"with_bgm": "9" * 64, "no_bgm": "9" * 64},
            )
            self.assertEqual(
                payload["edition_matrix"]["with_bgm"]["editions"]["none"][
                    "video_timeline_sha256"
                ],
                "9" * 64,
            )
            for profile in ("with_bgm", "no_bgm"):
                self.assertEqual(
                    payload["base_master_manifests"][profile][
                        "transaction_ready_marker"
                    ]["sha256"],
                    ready_reference["sha256"],
                )

            current_row = profile_rows["with_bgm"]
            current_sidecar = json.loads(
                current_row["sidecar"].read_text(encoding="utf-8")
            )
            missing_reference = dict(current_sidecar)
            missing_reference.pop("transaction_ready_marker")
            with self.assertRaisesRegex(
                RuntimeError, "transaction_ready_marker"
            ):
                render_subtitle_editions.validate_transaction_ready_marker(
                    event="ac0001_001",
                    profile="with_bgm",
                    base_path=current_row["base_path"],
                    base_manifest_path=current_row["sidecar"],
                    base_manifest=missing_reference,
                    expected_event_contract_sha256=event_contract_sha256,
                )

            sibling_sidecar = profile_rows["no_bgm"]["sidecar"]
            sibling_bytes = sibling_sidecar.read_bytes()
            sibling_sidecar.unlink()
            with self.assertRaises(FileNotFoundError):
                render_subtitle_editions.validate_transaction_ready_marker(
                    event="ac0001_001",
                    profile="with_bgm",
                    base_path=current_row["base_path"],
                    base_manifest_path=current_row["sidecar"],
                    base_manifest=current_sidecar,
                    expected_event_contract_sha256=event_contract_sha256,
                )
            sibling_sidecar.write_bytes(sibling_bytes)

            ready_path.write_bytes(ready_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                render_subtitle_editions.validate_transaction_ready_marker(
                    event="ac0001_001",
                    profile="with_bgm",
                    base_path=current_row["base_path"],
                    base_manifest_path=current_row["sidecar"],
                    base_manifest=current_sidecar,
                    expected_event_contract_sha256=event_contract_sha256,
                )

    def test_language_paths_keep_legacy_japanese_names(self) -> None:
        root = Path("output")
        ja_video, ja_srt = render_subtitle_editions.subtitle_edition_paths(
            root, "ac0001_001", "ja"
        )
        zh_video, zh_srt = render_subtitle_editions.subtitle_edition_paths(
            root, "ac0001_001", "zh"
        )

        self.assertEqual(ja_video, root / "with_subtitles/ac0001_001__subtitles.mp4")
        self.assertEqual(ja_srt, root / "subtitles/ac0001_001.srt")
        self.assertEqual(
            zh_video,
            root / "with_subtitles_zh/ac0001_001__zh_subtitles.mp4",
        )
        self.assertEqual(zh_srt, root / "subtitles_zh/ac0001_001.zh.srt")

    def test_long_edition_discovery_accepts_modern_three_edition_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event_dir = root / "ac0001_001"
            event_dir.mkdir()
            (root / "full_qa_audit.csv").write_text(
                "event,status\nac0001_001,passed\n", encoding="utf-8"
            )
            editions = {}
            for edition in ("none", "ja", "zh"):
                video = event_dir / f"{edition}.mp4"
                video.write_bytes(edition.encode("ascii"))
                subtitle = ""
                if edition != "none":
                    subtitle_path = event_dir / f"{edition}.srt"
                    subtitle_path.write_text("", encoding="utf-8")
                    subtitle = str(subtitle_path)
                editions[edition] = {
                    "language": edition,
                    "video": str(video),
                    "subtitles": subtitle,
                }
            (event_dir / "render_manifest.json").write_text(
                json.dumps({"event": "ac0001_001", "editions": editions}),
                encoding="utf-8",
            )

            series = build_series_editions.discover_events(
                [root], allow_legacy=True
            )
            scene = build_scene_editions.discover_events([root])

            self.assertEqual(set(series["ac0001_001"]["editions"]), {"none", "ja", "zh"})
            self.assertEqual(set(scene["ac0001_001"]["editions"]), {"none", "ja", "zh"})
            self.assertEqual(
                series["ac0001_001"]["with_path"],
                (event_dir / "ja.mp4").resolve(),
            )

    def test_series_discovery_requires_and_accepts_verified_six_entry_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event_dir = root / "ac0001_001"
            event_dir.mkdir()
            (root / "full_qa_audit.csv").write_text(
                "event,status\nac0001_001,passed\n", encoding="utf-8"
            )
            matrix = {}
            for profile, audio_hash in (
                ("with_bgm", "A" * 64),
                ("no_bgm", "B" * 64),
            ):
                editions = {}
                for edition in ("none", "ja", "zh"):
                    video = event_dir / f"{profile}-{edition}.mp4"
                    video.write_bytes(f"{profile}-{edition}".encode("ascii"))
                    subtitle = ""
                    if edition != "none":
                        subtitle_path = event_dir / f"{edition}.srt"
                        subtitle_path.write_text("", encoding="utf-8")
                        subtitle = str(subtitle_path)
                    editions[edition] = {
                        "language": edition,
                        "video": str(video),
                        "subtitles": subtitle,
                        "audio_sha256": audio_hash,
                    }
                matrix[profile] = {
                    "audio_profile": profile,
                    "audio_sha256": audio_hash,
                    "editions": editions,
                }
            (event_dir / "render_manifest.json").write_text(
                json.dumps(
                    {"event": "ac0001_001", "edition_matrix": matrix}
                ),
                encoding="utf-8",
            )

            events = build_series_editions.discover_events([root])

            self.assertEqual(
                set(events["ac0001_001"]["edition_matrix"]),
                {"with_bgm", "no_bgm"},
            )
            self.assertEqual(
                set(
                    events["ac0001_001"]["edition_matrix"]["with_bgm"][
                        "editions"
                    ]
                ),
                {"none", "ja", "zh"},
            )

    def test_long_edition_output_paths_preserve_legacy_aliases(self) -> None:
        root = Path("out")
        self.assertEqual(
            build_series_editions.series_edition_paths(root, "ac0001", "ja"),
            (
                root / "with_subtitles/ac0001__series__subtitles.mp4",
                root / "subtitles/ac0001__series.srt",
            ),
        )
        self.assertEqual(
            build_scene_editions.scene_edition_paths(root, "story", "zh"),
            (
                root / "with_subtitles_zh/story__scene__zh_subtitles.mp4",
                root / "subtitles_zh/story__scene.zh.srt",
            ),
        )


if __name__ == "__main__":
    unittest.main()
