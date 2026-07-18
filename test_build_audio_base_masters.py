from __future__ import annotations

import array
import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe import build_audio_base_masters as builder
from tools.frida_runtime_probe import render_subtitle_editions as subtitle_renderer
from tools.frida_runtime_probe.subtitle_edition_contract import (
    AUDIO_PROFILES,
    AUDIO_MASTER_CONTRACT_SCHEMA,
    inspect_audio_asset,
    validate_audio_master_contract,
)


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def run(command: list[str]) -> None:
    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def artifact_reference(path: Path, locator: str) -> dict[str, str]:
    return {
        "path": str(path),
        "sha256": builder.file_sha256(path),
        "locator": locator,
    }


def evidence(reference: dict[str, str], fields: list[str]) -> dict[str, object]:
    return {
        "kind": "official_runtime",
        "references": [reference],
        "fields": fields,
    }


@unittest.skipUnless(FFMPEG and FFPROBE, "FFmpeg and ffprobe are required")
class AudioBaseMasterEndToEndTests(unittest.TestCase):
    def make_tone(self, path: Path, frequency: int, duration: float) -> None:
        run(
            [
                str(FFMPEG),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=48000:duration={duration}",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(path),
            ]
        )

    def decoded_tone_amplitude(
        self,
        path: Path,
        frequency: int,
        *,
        start_ms: int = 0,
        end_ms: int | None = None,
    ) -> float:
        result = subprocess.run(
            [
                str(FFMPEG),
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                "48000",
                "-f",
                "f32le",
                "-",
            ],
            check=True,
            capture_output=True,
        )
        samples = array.array("f")
        samples.frombytes(result.stdout)
        start_sample = start_ms * 48
        end_sample = len(samples) if end_ms is None else end_ms * 48
        samples = samples[start_sample:end_sample]
        self.assertTrue(samples)
        cosine = 0.0
        sine = 0.0
        for index, sample in enumerate(samples):
            phase = 2.0 * math.pi * frequency * index / 48000
            cosine += sample * math.cos(phase)
            sine += sample * math.sin(phase)
        return 2.0 * math.hypot(cosine, sine) / len(samples)

    def make_fixture(self, root: Path) -> tuple[Path, Path]:
        clean_visual = root / "clean_visual.mp4"
        run(
            [
                str(FFMPEG),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=64x64:rate=30:duration=2",
                "-an",
                "-c:v",
                "libx264",
                "-profile:v",
                "high",
                "-level:v",
                "3.0",
                "-pix_fmt",
                "yuv420p",
                "-b:v",
                "200k",
                str(clean_visual),
            ]
        )
        clean_probe = subtitle_renderer.probe(clean_visual, str(FFPROBE))
        clean_video_stream = next(
            row
            for row in clean_probe["streams"]
            if row.get("codec_type") == "video"
        )
        clean_timeline = subtitle_renderer.probe_video_timeline(
            clean_visual,
            str(FFPROBE),
            expected_duration_ms=2000,
            expected_frame_rate="30/1",
            label="synthetic clean visual",
        )
        composition_fields = {
            "event": "ac_unit_001",
            "native_dimensions": {"width": 64, "height": 64},
            "native_frame_rate": "30/1",
            "video_duration_ms": 2000,
            "render_duration_ms": 2000,
            "video_extension_policy": "none",
            "video_composition_model": "linear_full_frame_sequence",
            "composition_plan": {
                "model": "linear_full_frame_sequence",
                "extension_policy": "none",
                "clips": [
                    {
                        "dgm_name": "synthetic_clean_source",
                        "role": "segment",
                        "start_ms": 0,
                        "end_ms": 2000,
                    }
                ],
            },
            "clips": [
                {
                    "order": 0,
                    "dgm_name": "synthetic_clean_source",
                    "path": str(clean_visual),
                    "event_start_ms": 0,
                    "event_end_ms": 2000,
                }
            ],
        }
        source_composition_projection = builder.composition_contract_projection(
            composition_fields
        )
        source_composition_sha256 = builder.composition_contract_sha256(
            composition_fields
        )
        clean_render_manifest = root / "clean_visual.render_manifest.json"
        clean_render_manifest.write_text(
            json.dumps(
                {
                    "schema": builder.CLEAN_VISUAL_RENDER_SCHEMA,
                    "status": "passed",
                    "publishable": True,
                    "event": "ac_unit_001",
                    "output": str(clean_visual),
                    "output_sha256": builder.file_sha256(clean_visual),
                    "output_video_packet_sha256": (
                        subtitle_renderer.video_packet_hash(
                            clean_visual, str(FFMPEG)
                        )
                    ),
                    "output_video_timeline_sha256": clean_timeline[
                        "timeline_sha256"
                    ],
                    "duration_ms": 2000,
                    "video_encoding_signature": list(
                        subtitle_renderer.video_encoding_signature(
                            clean_video_stream
                        )
                    ),
                    "source_composition_contract_sha256": (
                        source_composition_sha256
                    ),
                    "source_composition_contract": (
                        source_composition_projection
                    ),
                    "qa": {"status": "passed", "errors": []},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        voice = root / "voice.wav"
        sound_effect = root / "sound_effect.wav"
        bgm = root / "bgm.wav"
        self.make_tone(voice, 440, 2.0)
        self.make_tone(sound_effect, 660, 0.5)
        self.make_tone(bgm, 880, 2.0)
        runtime_evidence = root / "runtime_evidence.jsonl"
        runtime_evidence.write_text('{"audited":true}\n', encoding="utf-8")
        reference = artifact_reference(runtime_evidence, "synthetic runtime row 1")
        voice_evidence = evidence(
            reference, ["source", "timing", "identity", "volume"]
        )
        profile_evidence = evidence(
            reference, ["voice_se_preserved", "bgm_policy"]
        )
        voice_se = [
            {
                "path": str(voice),
                "sha256": builder.file_sha256(voice),
                "audio_role": "voice",
                "identity": "synthetic_voice_440_hz",
                "request_id": "voice-1",
                "code_name": "unit_voice",
                "start_ms": 0,
                "duration_ms": 2000,
                "source_offset_ms": 0,
                "volume": 1.0,
                "volume_unit": "linear",
                "evidence": voice_evidence,
            },
            {
                "path": str(sound_effect),
                "sha256": builder.file_sha256(sound_effect),
                "audio_role": "se",
                "identity": "synthetic_se_660_hz",
                "request_id": "se-1",
                "code_name": "unit_se",
                "start_ms": 1000,
                "duration_ms": 500,
                "source_offset_ms": 0,
                "volume": -6.020599913279624,
                "volume_unit": "db",
                "evidence": voice_evidence,
            },
        ]
        bgm_layer = {
            "source": {
                "path": str(bgm),
                "sha256": builder.file_sha256(bgm),
                "resource_id": "synthetic_bgm_880_hz",
            },
            "start_ms": 0,
            "end_ms": 2000,
            "source_offset_ms": 0,
            "loop": False,
            "loop_start_ms": None,
            "loop_end_ms": None,
            "volume": 0.5,
            "volume_unit": "linear",
            "volume_transitions": [
                {
                    "at_ms": 0,
                    "volume": 0.5,
                    "volume_unit": "linear",
                    "kind": "initial",
                },
                {
                    "at_ms": 700,
                    "volume": 0.25,
                    "volume_unit": "linear",
                    "kind": "duck",
                },
                {
                    "at_ms": 1200,
                    "volume": 0.5,
                    "volume_unit": "linear",
                    "kind": "restore",
                },
            ],
            "evidence": evidence(
                reference,
                ["source", "timing", "volume", "loop_phase", "transitions"],
            ),
        }
        manifest = {
            **composition_fields,
            "clean_visual_master": {
                "artifact": artifact_reference(
                    clean_visual, "synthetic clean visual bytes"
                ),
                "render_manifest": artifact_reference(
                    clean_render_manifest, "synthetic clean visual QA"
                ),
            },
            "audio": voice_se,
            "audio_master_contract": {
                "schema": AUDIO_MASTER_CONTRACT_SCHEMA,
                "output_encoding": {
                    "codec": "aac",
                    "sample_rate": 48000,
                    "channels": 2,
                    "channel_layout": "stereo",
                    "bit_rate": 128000,
                },
                "voice_se_timeline": voice_se,
                "profiles": {
                    "with_bgm": {
                        "evidence": profile_evidence,
                        "bgm_layers": [bgm_layer],
                    },
                    "no_bgm": {
                        "evidence": profile_evidence,
                        "bgm_layers": [],
                    },
                },
            },
        }
        manifest_path = root / "event_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest_path, clean_visual

    def test_two_masters_exclude_bgm_only_from_no_bgm_and_share_voice_se(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path, clean_visual = self.make_fixture(root)
            out_root = root / "masters"
            substitute = root / "same_shape_substitute.mp4"
            shutil.copy2(clean_visual, substitute)
            with self.assertRaisesRegex(
                RuntimeError, "does not match the evidence-bound artifact"
            ):
                builder.build_audio_base_masters(
                    event_manifest_path=manifest_path,
                    clean_visual_path=substitute,
                    out_root=root / "substitution-must-fail",
                    ffmpeg=str(FFMPEG),
                    ffprobe=str(FFPROBE),
                    aac_bitrate=128_000,
                )
            with self.assertRaisesRegex(RuntimeError, "evidence-bound target"):
                builder.build_audio_base_masters(
                    event_manifest_path=manifest_path,
                    clean_visual_path=clean_visual,
                    out_root=root / "wrong-bitrate-must-fail",
                    ffmpeg=str(FFMPEG),
                    ffprobe=str(FFPROBE),
                    aac_bitrate=192_000,
                )
            result = builder.build_audio_base_masters(
                event_manifest_path=manifest_path,
                clean_visual_path=clean_visual,
                out_root=out_root,
                ffmpeg=str(FFMPEG),
                ffprobe=str(FFPROBE),
                aac_bitrate=128_000,
            )
            self.assertEqual(set(result["profiles"]), set(AUDIO_PROFILES))
            self.assertEqual(len(list(out_root.rglob("*.mp4"))), 2)
            ready_reference = result["transaction_ready_marker"]
            ready_path = Path(ready_reference["path"])
            self.assertTrue(ready_path.is_file())
            self.assertEqual(
                builder.file_sha256(ready_path), ready_reference["sha256"]
            )
            with_bgm_path = Path(result["profiles"]["with_bgm"]["video"])
            no_bgm_path = Path(result["profiles"]["no_bgm"]["video"])
            clean_video_hash = subtitle_renderer.video_packet_hash(
                clean_visual, str(FFMPEG)
            )
            self.assertEqual(
                subtitle_renderer.video_packet_hash(with_bgm_path, str(FFMPEG)),
                clean_video_hash,
            )
            self.assertEqual(
                subtitle_renderer.video_packet_hash(no_bgm_path, str(FFMPEG)),
                clean_video_hash,
            )

            no_voice = self.decoded_tone_amplitude(no_bgm_path, 440)
            with_voice = self.decoded_tone_amplitude(with_bgm_path, 440)
            no_se = self.decoded_tone_amplitude(no_bgm_path, 660)
            with_se = self.decoded_tone_amplitude(with_bgm_path, 660)
            no_bgm = self.decoded_tone_amplitude(no_bgm_path, 880)
            with_bgm = self.decoded_tone_amplitude(with_bgm_path, 880)
            self.assertGreater(no_voice, 0.08)
            self.assertAlmostEqual(with_voice / no_voice, 1.0, delta=0.04)
            self.assertGreater(no_se, 0.01)
            self.assertAlmostEqual(with_se / no_se, 1.0, delta=0.08)
            self.assertLess(no_bgm, 0.001)
            self.assertGreater(with_bgm, no_bgm * 20 + 0.02)
            bgm_initial = self.decoded_tone_amplitude(
                with_bgm_path, 880, start_ms=200, end_ms=600
            )
            bgm_ducked = self.decoded_tone_amplitude(
                with_bgm_path, 880, start_ms=800, end_ms=1100
            )
            bgm_restored = self.decoded_tone_amplitude(
                with_bgm_path, 880, start_ms=1300, end_ms=1800
            )
            self.assertAlmostEqual(bgm_ducked / bgm_initial, 0.5, delta=0.08)
            self.assertAlmostEqual(bgm_restored / bgm_initial, 1.0, delta=0.08)

            payloads = {}
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for profile in AUDIO_PROFILES:
                reference = result["profiles"][profile]["base_master_manifest"]
                manifest["audio_master_contract"]["profiles"][profile][
                    "base_master_manifest"
                ] = reference
                sidecar_path = Path(reference["path"])
                self.assertEqual(builder.file_sha256(sidecar_path), reference["sha256"])
                payloads[profile] = json.loads(sidecar_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    payloads[profile]["transaction_ready_marker"]["sha256"],
                    ready_reference["sha256"],
                )
                timeline = payloads[profile]["audio_presentation_timeline"]
                self.assertEqual(timeline["expected_presentation_samples"], 96000)
                self.assertEqual(timeline["packet_presentation_end_sample"], 96000)
                self.assertEqual(
                    sum(row["duration"] for row in timeline["frames"]), 96000
                )
                self.assertEqual(
                    payloads[profile]["effective_decoded_pcm_audit"][
                        "sample_count_per_channel"
                    ],
                    96000,
                )
                self.assertEqual(
                    payloads[profile][
                        "output_effective_decoded_pcm_sha256"
                    ],
                    payloads[profile]["effective_decoded_pcm_audit"][
                        "pcm_sha256"
                    ],
                )
                self.assertEqual(
                    payloads[profile]["preencode_mix_audit"][
                        "sample_count_per_channel"
                    ],
                    96000,
                )
                self.assertLess(
                    payloads[profile]["preencode_mix_audit"]["peak_absolute"],
                    1.0,
                )
                self.assertLessEqual(
                    abs(
                        payloads[profile]["render_method"][
                            "actual_audio_bit_rate"
                        ]
                        - 128000
                    ),
                    12800,
                )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            validated = validate_audio_master_contract(
                manifest,
                requested_profiles=AUDIO_PROFILES,
                manifest_path=manifest_path,
                media_inspector=lambda path: inspect_audio_asset(
                    path, ffprobe=str(FFPROBE)
                ),
            )
            for profile in AUDIO_PROFILES:
                output = Path(result["profiles"][profile]["video"])
                output_probe = subtitle_renderer.probe(output, str(FFPROBE))
                video_timeline = subtitle_renderer.probe_video_timeline(
                    output,
                    str(FFPROBE),
                    expected_duration_ms=2000,
                    expected_frame_rate="30/1",
                    label=f"unit {profile}",
                )
                subtitle_renderer.validate_base_master_manifest(
                    event="ac_unit_001",
                    profile=profile,
                    base_path=output,
                    profile_contract=validated["profiles"][profile],
                    event_manifest_path=manifest_path,
                    base_probe=output_probe,
                    audio_packet_sha256=subtitle_renderer.audio_hash(
                        output, str(FFMPEG)
                    ),
                    decoded_pcm_sha256=subtitle_renderer.decoded_pcm_hash(
                        output, str(FFMPEG)
                    ),
                    video_packet_sha256=subtitle_renderer.video_packet_hash(
                        output, str(FFMPEG)
                    ),
                    video_timeline_sha256=str(
                        video_timeline["timeline_sha256"]
                    ),
                )
            self.assertEqual(payloads["no_bgm"]["source_layers"]["bgm_layers"], [])
            self.assertTrue(
                payloads["no_bgm"]["qa"]["checks"]["no_bgm_excludes_bgm"]
            )
            self.assertEqual(
                payloads["with_bgm"]["voice_se_timeline_sha256"],
                payloads["no_bgm"]["voice_se_timeline_sha256"],
            )
            self.assertEqual(
                payloads["with_bgm"]["source_layers"]["voice_se"],
                payloads["no_bgm"]["source_layers"]["voice_se"],
            )
            for profile in AUDIO_PROFILES:
                self.assertEqual(
                    payloads[profile]["source_layers_sha256"],
                    subtitle_renderer.canonical_sha256(
                        payloads[profile]["source_layers"]
                    ),
                )
            self.assertNotEqual(
                payloads["with_bgm"]["output_decoded_pcm_sha256"],
                payloads["no_bgm"]["output_decoded_pcm_sha256"],
            )
            self.assertNotEqual(
                payloads["with_bgm"][
                    "output_effective_decoded_pcm_sha256"
                ],
                payloads["no_bgm"][
                    "output_effective_decoded_pcm_sha256"
                ],
            )

    def test_clean_visual_binding_rejects_composition_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path, clean_visual = self.make_fixture(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["composition_plan"]["clips"][0]["end_ms"] = 1999
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError, "source composition contract does not match"
            ):
                builder.build_audio_base_masters(
                    event_manifest_path=manifest_path,
                    clean_visual_path=clean_visual,
                    out_root=root / "tampered-composition-must-fail",
                    ffmpeg=str(FFMPEG),
                    ffprobe=str(FFPROBE),
                    aac_bitrate=128_000,
                )

    def test_overrange_linear_sum_is_not_published_without_mixer_law(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path, clean_visual = self.make_fixture(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["audio"][0]["volume"] = 12.0
            manifest["audio_master_contract"]["voice_se_timeline"][0][
                "volume"
            ] = 12.0
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "would clip"):
                builder.build_audio_base_masters(
                    event_manifest_path=manifest_path,
                    clean_visual_path=clean_visual,
                    out_root=root / "clipping-must-fail",
                    ffmpeg=str(FFMPEG),
                    ffprobe=str(FFPROBE),
                    aac_bitrate=128_000,
                )
            self.assertFalse((root / "clipping-must-fail" / "with_bgm").exists())


class AudioBaseMasterPromotionTests(unittest.TestCase):
    def make_transaction(
        self, root: Path
    ) -> tuple[list[tuple[Path, Path]], Path, Path, Path]:
        staging = root / "staging"
        staging.mkdir()
        destination = root / "published"
        staged_artifacts: list[tuple[Path, Path]] = []
        for index, relative in enumerate(
            (
                Path("with_bgm/event.mp4"),
                Path("no_bgm/event.mp4"),
                Path("with_bgm/event.base_master.json"),
                Path("no_bgm/event.base_master.json"),
            )
        ):
            staged_path = staging / f"artifact-{index}.bin"
            staged_path.write_bytes(f"staged-{index}".encode("ascii"))
            staged_artifacts.append((staged_path, destination / relative))
        staged_ready = staging / "transaction.ready.json"
        staged_ready.write_text(
            json.dumps({"status": "ready", "generation": "this-build"}),
            encoding="utf-8",
        )
        final_ready = destination / "transactions" / "event.ready.json"
        lock_path = destination / "transactions" / ".event.promotion.lock"
        return staged_artifacts, staged_ready, final_ready, lock_path

    def test_post_check_sentinel_race_fails_without_overwrite_or_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts, staged_ready, final_ready, lock_path = self.make_transaction(
                root
            )
            original_link = builder._link_staged_file_no_replace
            sentinel_target = artifacts[1][1]
            sentinel_bytes = b"foreign-process-sentinel"
            call_count = 0

            def inject_after_final_check(staged_path: Path, final_path: Path) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    final_path.write_bytes(sentinel_bytes)
                original_link(staged_path, final_path)

            with patch.object(
                builder,
                "_link_staged_file_no_replace",
                side_effect=inject_after_final_check,
            ):
                with self.assertRaisesRegex(
                    FileExistsError, "concurrent output appeared"
                ):
                    builder._promote_audio_base_master_transaction(
                        staged_artifacts=artifacts,
                        staged_ready=staged_ready,
                        final_ready=final_ready,
                        lock_path=lock_path,
                    )

            self.assertEqual(call_count, 2)
            self.assertEqual(sentinel_target.read_bytes(), sentinel_bytes)
            self.assertFalse(artifacts[0][1].exists())
            for _, final_path in artifacts[2:]:
                self.assertFalse(final_path.exists())
            self.assertFalse(final_ready.exists())
            for staged_path, _ in artifacts:
                self.assertTrue(staged_path.is_file())
            self.assertTrue(staged_ready.is_file())

    def test_concurrent_complete_ready_release_survives_failed_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts, staged_ready, final_ready, lock_path = self.make_transaction(
                root
            )
            original_link = builder._link_staged_file_no_replace
            all_targets = [
                *(final_path for _, final_path in artifacts),
                final_ready,
            ]
            other_release = {
                target: (
                    json.dumps(
                        {"status": "ready", "generation": "other-process"}
                    ).encode("utf-8")
                    if target == final_ready
                    else f"other-release-{index}".encode("ascii")
                )
                for index, target in enumerate(all_targets)
            }
            injected = False

            def inject_complete_release(staged_path: Path, final_path: Path) -> None:
                nonlocal injected
                if not injected:
                    injected = True
                    for target, payload in other_release.items():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(payload)
                original_link(staged_path, final_path)

            with patch.object(
                builder,
                "_link_staged_file_no_replace",
                side_effect=inject_complete_release,
            ):
                with self.assertRaisesRegex(
                    FileExistsError, "concurrent output appeared"
                ):
                    builder._promote_audio_base_master_transaction(
                        staged_artifacts=artifacts,
                        staged_ready=staged_ready,
                        final_ready=final_ready,
                        lock_path=lock_path,
                    )

            self.assertTrue(injected)
            self.assertEqual(
                {target: target.read_bytes() for target in all_targets},
                other_release,
            )
            self.assertEqual(
                json.loads(final_ready.read_text(encoding="utf-8"))["status"],
                "ready",
            )

    def test_rollback_does_not_unlink_a_foreign_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifacts, staged_ready, final_ready, lock_path = self.make_transaction(
                root
            )
            original_link = builder._link_staged_file_no_replace
            first_foreign_bytes = b"foreign-replacement-of-first-link"
            collision_bytes = b"foreign-collision-on-second-target"
            call_count = 0

            def replace_then_collide(staged_path: Path, final_path: Path) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    artifacts[0][1].unlink()
                    artifacts[0][1].write_bytes(first_foreign_bytes)
                    final_path.write_bytes(collision_bytes)
                original_link(staged_path, final_path)

            with patch.object(
                builder,
                "_link_staged_file_no_replace",
                side_effect=replace_then_collide,
            ):
                with self.assertRaisesRegex(
                    FileExistsError, "concurrent output appeared"
                ):
                    builder._promote_audio_base_master_transaction(
                        staged_artifacts=artifacts,
                        staged_ready=staged_ready,
                        final_ready=final_ready,
                        lock_path=lock_path,
                    )

            self.assertEqual(artifacts[0][1].read_bytes(), first_foreign_bytes)
            self.assertEqual(artifacts[1][1].read_bytes(), collision_bytes)
            for _, final_path in artifacts[2:]:
                self.assertFalse(final_path.exists())
            self.assertFalse(final_ready.exists())


class AudioBaseMasterFailClosedTests(unittest.TestCase):
    def test_source_integrity_rehash_detects_post_validation_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.bin"
            source.write_bytes(b"first")
            snapshot = {source: builder.file_sha256(source)}
            source.write_bytes(b"second")
            with self.assertRaisesRegex(RuntimeError, "changed during render"):
                builder._assert_source_integrity(snapshot)

    def test_rejects_loop_fade_and_game_parameter_instead_of_guessing(self) -> None:
        base_layer = {
            "loop": False,
            "start_ms": 0,
            "volume_transitions": [
                {
                    "at_ms": 0,
                    "volume": 1.0,
                    "volume_unit": "linear",
                    "kind": "initial",
                }
            ],
        }
        with self.subTest("loop"):
            with self.assertRaisesRegex(RuntimeError, "loop phase"):
                builder._validate_step_transitions(
                    {**base_layer, "loop": True}, label="test BGM"
                )
        with self.subTest("fade"):
            with self.assertRaisesRegex(RuntimeError, "interpolation curve"):
                builder._validate_step_transitions(
                    {
                        **base_layer,
                        "volume_transitions": [
                            *base_layer["volume_transitions"],
                            {
                                "at_ms": 100,
                                "volume": 0.0,
                                "volume_unit": "linear",
                                "kind": "fade",
                            },
                        ],
                    },
                    label="test BGM",
                )
        with self.subTest("game parameter"):
            with self.assertRaisesRegex(RuntimeError, "ambiguous volume unit"):
                builder._gain(50, "game_parameter", label="test voice")


if __name__ == "__main__":
    unittest.main()
