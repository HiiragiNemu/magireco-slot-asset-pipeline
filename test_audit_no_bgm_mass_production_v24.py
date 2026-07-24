import csv
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WINGET_LINKS = Path.home() / "AppData/Local/Microsoft/WinGet/Links"
if WINGET_LINKS.is_dir():
    os.environ["PATH"] = str(WINGET_LINKS) + os.pathsep + os.environ.get("PATH", "")
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

from tools.frida_runtime_probe.audit_no_bgm_mass_production_v24 import (
    AuditError,
    REQUIRED_EDITIONS,
    REQUIRED_QA_CHECKS,
    _audit_actual_audio,
    audit_batch_roots,
    canonical_sha256,
    file_sha256,
    write_reports,
)


WIDTH = 416
HEIGHT = 232
FRAMES = 30
SAMPLES = 48000


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fake_probe(path: Path, _ffprobe: str) -> dict:
    video = {
        "codec_type": "video",
        "codec_name": "h264",
        "width": WIDTH,
        "height": HEIGHT,
        "r_frame_rate": "30/1",
        "nb_read_frames": str(FRAMES),
    }
    audio = {
        "codec_type": "audio",
        "codec_name": "aac",
        "sample_rate": "48000",
        "channels": 2,
    }
    if "clean_visual_master" in path.name:
        return {"streams": [video], "format": {}}
    if "no_bgm_audio_master" in path.name:
        return {"streams": [audio], "format": {}}
    return {"streams": [video, audio], "format": {}}


def bad_audio_probe(path: Path, ffprobe: str) -> dict:
    result = fake_probe(path, ffprobe)
    for stream in result["streams"]:
        if stream["codec_type"] == "audio":
            stream["sample_rate"] = "44100"
    return result


class Fixture:
    def __init__(self, root: Path) -> None:
        if not FFMPEG or not FFPROBE:
            raise AssertionError(
                "real FFmpeg and FFprobe are required; WinGet Links was added to PATH"
            )
        self.root = root
        self.batch = root / "batch"
        self.manifest_root = root / "production_manifests_v24"
        self.release_roots: dict[str, Path] = {}
        self._make_media_templates()
        self._make_family("ac0911", "ac0911_010")
        self._make_family("ac5303", "ac5303_003")
        write_json(
            self.batch / "BATCH_SUMMARY.json",
            {
                "schema": "magireco-no-bgm-story-family-editions-batch-v1",
                "status": "AUTOMATED_QA_PASSED",
                "selected_editions": list(REQUIRED_EDITIONS),
                "families": [
                    str(path.resolve())
                    for path in sorted(self.release_roots.values())
                ],
                "human_playback_approved": False,
                "bilibili_release_ready": False,
            },
        )
        self._make_event_manifest(
            "ac0911_010",
            "8041",
            "私もチャレンジした方がいいのかな",
            "kuroe",
        )
        self._make_event_manifest(
            "ac5303_003",
            "5172",
            "ふざけるなふざけるなふざけるな",
            "ari",
        )
        self._make_event_manifest(
            "ac5203_2_001",
            "9999",
            "multi-suffix event fixture",
            "fixture",
        )
        write_json(
            self.manifest_root / "event_production_summary.json",
            {
                "events": 3,
                "ready_events": 3,
                "failed_events": 0,
                "audio_timeline_ready_events": 3,
                "composition_resolved_events": 3,
            },
        )

    def _run_media(self, command: list[str]) -> None:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def _make_media_templates(self) -> None:
        template = self.root / "_real_media_templates"
        template.mkdir(parents=True)
        self.clean_template = template / "clean_visual_master.mp4"
        self.audio_template = template / "no_bgm_audio_master.m4a"
        self.edition_template = template / "edition.mp4"
        self._run_media(
            [
                str(FFMPEG),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c=blue:s={WIDTH}x{HEIGHT}:r=30:d=1",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-frames:v",
                str(FRAMES),
                str(self.clean_template),
            ]
        )
        self._run_media(
            [
                str(FFMPEG),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=48000:duration=1",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(self.audio_template),
            ]
        )
        self._run_media(
            [
                str(FFMPEG),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(self.clean_template),
                "-i",
                str(self.audio_template),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(self.edition_template),
            ]
        )
        self.actual_audio_audit = _audit_actual_audio(
            self.audio_template,
            expected_samples=SAMPLES,
            ffmpeg=str(FFMPEG),
            ffprobe=str(FFPROBE),
            label="fixture audio master",
        )
        edition_audit = _audit_actual_audio(
            self.edition_template,
            expected_samples=SAMPLES,
            ffmpeg=str(FFMPEG),
            ffprobe=str(FFPROBE),
            label="fixture edition",
        )
        if edition_audit != self.actual_audio_audit:
            raise AssertionError("real fixture edition audio differs from its master")

    def _make_family(self, family: str, event: str) -> None:
        release_id = f"{family}_full_no_bgm_editions_v1"
        release_root = self.batch / release_id
        self.release_roots[family] = release_root
        timeline = [
            {
                "event": event,
                "start_frame": 0,
                "end_frame": FRAMES,
                "start_sample": 0,
                "end_sample": SAMPLES,
                "inserted_gap_frames": 0,
            }
        ]
        qa = {
            "schema": "magireco-no-bgm-story-family-editions-qa-v1",
            "status": "passed",
            "family": family,
            "selected_editions": list(REQUIRED_EDITIONS),
            "checks": {name: True for name in REQUIRED_QA_CHECKS},
            "events": [event],
            "timeline": timeline,
            "total_frames": FRAMES,
            "total_presentation_samples": SAMPLES,
            "duration_ms": 1000,
            "dialogue_cue_count": 1,
            "audio_layer_count": 1,
            "audio_role_counts": {
                "voice": 1,
                "scene_se": 0,
                "unsubtitled_audio": 0,
            },
            "audio_master_packet_sha256": self.actual_audio_audit[
                "audio_packet_sha256"
            ],
            "audio_master_timeline": self.actual_audio_audit["audio_timeline"],
            "audio_master_decoded_pcm": self.actual_audio_audit["decoded_pcm"],
            "edition_media_audits": {
                edition: {
                    "frame_count": FRAMES,
                    "audio_packet_sha256": self.actual_audio_audit[
                        "audio_packet_sha256"
                    ],
                    "audio_timeline": self.actual_audio_audit["audio_timeline"],
                    "decoded_pcm": self.actual_audio_audit["decoded_pcm"],
                }
                for edition in REQUIRED_EDITIONS
            },
        }
        artifact_relpaths = {
            "qa": "qa/automated_qa.json",
            "review_form": "review/HUMAN_PLAYBACK_REVIEW.md",
            "clean_visual_master": (
                f"masters/{release_id}__clean_visual_master.mp4"
            ),
            "no_bgm_audio_master": (
                f"masters/{release_id}__no_bgm_audio_master.m4a"
            ),
            "video_none": f"video/{release_id}__none.mp4",
            "video_ja": f"video/{release_id}__ja.mp4",
            "video_zh": f"video/{release_id}__zh.mp4",
            "subtitles_ja": f"subtitles/{release_id}__ja.srt",
            "subtitles_zh": f"subtitles/{release_id}__zh.srt",
        }
        write_json(release_root / artifact_relpaths["qa"], qa)
        for name, relative in artifact_relpaths.items():
            if name == "qa":
                continue
            path = release_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == "clean_visual_master":
                shutil.copy2(self.clean_template, path)
            elif name == "no_bgm_audio_master":
                shutil.copy2(self.audio_template, path)
            elif name.startswith("video_"):
                shutil.copy2(self.edition_template, path)
            elif name == "subtitles_ja":
                path.write_text(
                    "1\n00:00:00,200 --> 00:00:00,900\nテスト台詞\n",
                    encoding="utf-8",
                )
            elif name == "subtitles_zh":
                path.write_text(
                    "1\n00:00:00,200 --> 00:00:00,900\n测试台词\n",
                    encoding="utf-8",
                )
            else:
                path.write_text(f"# {family} playback review\n", encoding="utf-8")
        artifacts = {
            name: {
                "path": relative,
                "sha256": file_sha256(release_root / relative),
            }
            for name, relative in artifact_relpaths.items()
        }
        manifest = {
            "schema": "magireco-no-bgm-story-family-editions-v1",
            "status": "AUTOMATED_QA_PASSED",
            "release_id": release_id,
            "family": family,
            "release_scope": "no_bgm_family_expansion_candidates",
            "audio_profile": "no_bgm",
            "selected_editions": list(REQUIRED_EDITIONS),
            "subtitle_profiles": {
                "none": "none",
                "ja": "ja_voice_bound_dialogue",
                "zh": "zh_voice_bound_dialogue",
            },
            "bgm_policy": "intentionally_excluded",
            "voice_se_policy": "preserve_verified_evidence_bound_original",
            "readiness": {"AUTOMATED_QA_PASSED": True},
            "ordered_events": [event],
            "timeline": timeline,
            "media": {
                "duration_ms": 1000,
                "width": WIDTH,
                "height": HEIGHT,
                "frame_rate": "30/1",
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": 48000,
                "audio_channels": 2,
                "upscaled": False,
                "edition_video_bit_rates": {
                    edition: 600000 for edition in REQUIRED_EDITIONS
                },
            },
            "dialogue_cue_count": 1,
            "artifacts": artifacts,
        }
        manifest_relpath = "manifests/family_editions_manifest.json"
        write_json(release_root / manifest_relpath, manifest)
        marker_artifacts = {
            **artifacts,
            "manifest": {
                "path": manifest_relpath,
                "sha256": file_sha256(release_root / manifest_relpath),
            },
        }
        marker = {
            "schema": "magireco-no-bgm-story-family-editions-ready-v1",
            "status": "AUTOMATED_QA_PASSED",
            "release_id": release_id,
            "family": family,
            "selected_editions": list(REQUIRED_EDITIONS),
            "publishable": False,
            "readiness": {"AUTOMATED_QA_PASSED": True},
            "artifacts": marker_artifacts,
            "artifact_set_sha256": canonical_sha256(marker_artifacts),
        }
        write_json(release_root / "BATCH_REVIEW_READY.json", marker)

    def _make_event_manifest(
        self,
        event: str,
        request_id: str,
        text: str,
        speaker: str,
    ) -> None:
        manifest = {
            "event": event,
            "audio": [
                {
                    "source": "z2d_req_sound",
                    "request_id": request_id,
                    "path": f"audio/{request_id}.ogg",
                    "start_ms": 200,
                    "duration_ms": 2000,
                    "evidence": "official_runtime_capture",
                }
            ],
            "subtitles": [
                {
                    "text": text,
                    "start_ms": 200,
                    "end_ms": 2200,
                    "voice_request_id": request_id,
                    "voice_start_ms": 200,
                    "speaker_code": speaker,
                    "subtitle_source": "official_voice_asr_verified",
                    "evidence": "curated_official_prefix_and_large_v3_consensus",
                }
            ],
            "reviewed_subtitle_reconciliation": {
                "accepted_current_voice_override_candidates": [
                    {
                        "voice_request_id": request_id,
                        "text": text,
                        "subtitle_source": "official_voice_asr_verified",
                    }
                ],
                "excluded_current_voice_candidates": [],
            },
            "quality_gates": {
                "all_clips_exist": True,
                "all_clip_source_hashes_bound": True,
                "all_audio_exist": True,
                "composition_resolved": True,
                "audio_timeline_ready": True,
                "errors": [],
                "render_ready": True,
                "ready": True,
            },
        }
        write_json(self.manifest_root / "events" / f"{event}.json", manifest)

    def refresh_release_bindings(self, family: str) -> None:
        release_root = self.release_roots[family]
        marker_path = release_root / "BATCH_REVIEW_READY.json"
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        manifest_path = release_root / marker["artifacts"]["manifest"]["path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, artifact in marker["artifacts"].items():
            if name == "manifest":
                continue
            digest = file_sha256(release_root / artifact["path"])
            artifact["sha256"] = digest
            manifest["artifacts"][name]["sha256"] = digest
        write_json(manifest_path, manifest)
        marker["artifacts"]["manifest"]["sha256"] = file_sha256(manifest_path)
        marker["artifact_set_sha256"] = canonical_sha256(marker["artifacts"])
        write_json(marker_path, marker)

    def audit(self, probe=fake_probe) -> dict:
        kwargs = {}
        if probe is not None:
            kwargs["probe_func"] = probe
        return audit_batch_roots(
            [self.batch],
            manifest_roots=[self.manifest_root],
            ffmpeg=str(FFMPEG),
            ffprobe=str(FFPROBE),
            **kwargs,
        )


class NoBgmMassProductionAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Fixture(Path(self.temporary.name))

    def test_passes_and_writes_json_and_csv(self) -> None:
        report = self.fixture.audit()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["family_count"], 2)
        self.assertEqual(report["edition_video_count"], 6)
        self.assertEqual(report["manifest_root_count"], 1)
        self.assertFalse(
            report["legacy_reviewed_subtitle_reconciliation_qa_used"]
        )
        accepted = report["accepted_current_voice_override_candidates"]
        self.assertEqual(
            {(row["event"], row["voice_request_id"]) for row in accepted},
            {("ac0911_010", "8041"), ("ac5303_003", "5172")},
        )
        self.assertTrue(
            all(
                row["reconciliation_accepted_current_candidate"]
                for row in accepted
            )
        )

        json_path = self.fixture.root / "audit.json"
        csv_path = self.fixture.root / "audit.csv"
        write_reports(report, json_path=json_path, csv_path=csv_path)
        written = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(written["family_count"], 2)
        with csv_path.open(encoding="utf-8", newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["unresolved_audio_layer_count"] for row in rows},
            {"0"},
        )

    def test_real_ffmpeg_and_ffprobe_validate_actual_media(self) -> None:
        report = self.fixture.audit(probe=None)
        self.assertEqual(report["status"], "passed")
        for family in report["families"]:
            self.assertEqual(family["subtitle_audit"]["cue_count"], 1)
            master = family["actual_audio_master_audit"]
            self.assertEqual(
                {
                    row["audio_packet_sha256"]
                    for row in family["actual_edition_audio_audits"].values()
                },
                {master["audio_packet_sha256"]},
            )
            self.assertEqual(
                master["decoded_pcm"]["sample_count_per_channel"],
                SAMPLES,
            )

    def test_fails_if_srt_is_not_strictly_parseable_after_rebinding(self) -> None:
        release = self.fixture.release_roots["ac0911"]
        subtitle = release / "subtitles/ac0911_full_no_bgm_editions_v1__zh.srt"
        subtitle.write_text("this is not an SRT\n", encoding="utf-8")
        self.fixture.refresh_release_bindings("ac0911")
        with self.assertRaisesRegex(AuditError, "cue 1 is incomplete"):
            self.fixture.audit()

    def test_fails_if_actual_edition_audio_differs_after_rebinding(self) -> None:
        alternate_audio = self.fixture.root / "alternate_audio.m4a"
        alternate_edition = self.fixture.root / "alternate_edition.mp4"
        self.fixture._run_media(
            [
                str(FFMPEG),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=880:sample_rate=48000:duration=1",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(alternate_audio),
            ]
        )
        self.fixture._run_media(
            [
                str(FFMPEG),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(self.fixture.clean_template),
                "-i",
                str(alternate_audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(alternate_edition),
            ]
        )
        release = self.fixture.release_roots["ac0911"]
        target = release / "video/ac0911_full_no_bgm_editions_v1__zh.mp4"
        shutil.copy2(alternate_edition, target)
        self.fixture.refresh_release_bindings("ac0911")
        with self.assertRaisesRegex(AuditError, "actual audio differs from the master"):
            self.fixture.audit()

    def test_fails_if_ready_listed_artifact_hash_differs(self) -> None:
        video = (
            self.fixture.release_roots["ac0911"]
            / "video/ac0911_full_no_bgm_editions_v1__zh.mp4"
        )
        video.write_bytes(b"tampered")
        with self.assertRaisesRegex(AuditError, "SHA-256 differs"):
            self.fixture.audit()

    def test_fails_if_unresolved_audio_is_nonzero(self) -> None:
        release = self.fixture.release_roots["ac0911"]
        qa_path = release / "qa/automated_qa.json"
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        qa["audio_role_counts"] = {
            "voice": 0,
            "scene_se": 0,
            "unsubtitled_audio": 1,
        }
        write_json(qa_path, qa)
        self.fixture.refresh_release_bindings("ac0911")
        with self.assertRaisesRegex(AuditError, "unresolved audio layers"):
            self.fixture.audit()

    def test_fails_if_selected_editions_are_not_exact(self) -> None:
        marker_path = (
            self.fixture.release_roots["ac0911"] / "BATCH_REVIEW_READY.json"
        )
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["selected_editions"] = ["none", "zh"]
        write_json(marker_path, marker)
        with self.assertRaisesRegex(AuditError, "must be exactly"):
            self.fixture.audit()

    def test_fails_if_actual_audio_is_not_48khz(self) -> None:
        with self.assertRaisesRegex(AuditError, "not 48 kHz"):
            self.fixture.audit(probe=bad_audio_probe)

    def test_fails_if_required_voice_subtitle_is_missing(self) -> None:
        path = (
            self.fixture.manifest_root / "events" / "ac0911_010.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["subtitles"] = []
        manifest["reviewed_subtitle_reconciliation"][
            "accepted_current_voice_override_candidates"
        ] = []
        write_json(path, manifest)
        with self.assertRaisesRegex(AuditError, "voice-bound subtitle"):
            self.fixture.audit()

    def test_fails_if_batch_summary_omits_a_release_directory(self) -> None:
        extra = self.fixture.batch / "ac9999_full_no_bgm_editions_v1"
        extra.mkdir()
        with self.assertRaisesRegex(AuditError, "summary/discovered family sets"):
            self.fixture.audit()

    def test_accepts_native_dimension_split_family_names(self) -> None:
        self.fixture._make_family(
            "ac7113_main_512x288",
            "ac5203_2_001",
        )
        write_json(
            self.fixture.batch / "BATCH_SUMMARY.json",
            {
                "schema": "magireco-no-bgm-story-family-editions-batch-v1",
                "status": "AUTOMATED_QA_PASSED",
                "selected_editions": list(REQUIRED_EDITIONS),
                "families": [
                    str(path.resolve())
                    for path in sorted(self.fixture.release_roots.values())
                ],
                "human_playback_approved": False,
                "bilibili_release_ready": False,
            },
        )

        report = self.fixture.audit()

        self.assertEqual(report["family_count"], 3)
        self.assertIn(
            "ac7113_main_512x288",
            {row["family"] for row in report["families"]},
        )


if __name__ == "__main__":
    unittest.main()
