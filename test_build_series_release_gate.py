from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.frida_runtime_probe import (
    build_scene_editions,
    build_series_editions,
    render_subtitle_editions,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class BuildSeriesReleaseGateTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def release_tree_bytes(path: Path) -> dict[str, bytes]:
        return {
            file.relative_to(path).as_posix(): file.read_bytes()
            for file in sorted(path.rglob("*"))
            if file.is_file()
        }

    def make_fixture(
        self,
        root: Path,
        *,
        events: tuple[str, ...] = ("ac0001_001", "ac0001_002"),
        ordered_events: tuple[str, ...] | None = None,
    ) -> dict:
        input_root = root / "input"
        production_root = root / "production"
        production_events = production_root / "events"
        input_root.mkdir()
        production_events.mkdir(parents=True)
        (input_root / "full_qa_audit.csv").write_text(
            "event,status\n"
            + "".join(f"{event},passed\n" for event in events),
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
                path = event_dir / f"{edition}.srt"
                path.write_text(
                    f"1\n00:00:00,100 --> 00:00:00,800\n{text}\n",
                    encoding="utf-8",
                )
                subtitles[edition] = path
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
                        "audio_sha256": audio_by_profile[profile],
                        "video_sha256": sha256(video),
                        "video_packet_sha256": packet_by_edition[edition],
                        "subtitle_sha256": sha256(subtitle) if subtitle else "",
                    }
                matrix[profile] = {
                    "audio_profile": profile,
                    "audio_sha256": audio_by_profile[profile],
                    "editions": editions,
                }
            render_manifest = event_dir / "render_manifest.json"
            render_manifest.write_text(
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
            (production_events / f"{event}.json").write_text(
                json.dumps(
                    {
                        "event": event,
                        "quality_gates": {"ready": True, "errors": []},
                    }
                ),
                encoding="utf-8",
            )

        runtime_evidence = root / "runtime-order.jsonl"
        runtime_evidence.write_text('{"event":"runtime-order"}\n', encoding="utf-8")
        order_manifest = root / "series-order.json"
        order_manifest.write_text(
            json.dumps(
                {
                    "schema": build_series_editions.SERIES_ORDER_SCHEMA,
                    "series": "ac0001",
                    "complete": True,
                    "ordered_events": list(ordered_events or tuple(reversed(events))),
                    "evidence": {
                        "kind": "official_runtime",
                        "fields": ["ordered_events", "family_completeness"],
                        "references": [
                            {
                                "path": str(runtime_evidence),
                                "sha256": sha256(runtime_evidence),
                                "locator": "runtime order rows 1-2",
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        return {
            "input_root": input_root,
            "production_root": production_root,
            "order_manifest": order_manifest,
            "events": events,
            "packet_by_edition": packet_by_edition,
            "audio_by_profile": audio_by_profile,
        }

    def make_real_fixture(self, root: Path) -> dict:
        input_root = root / "input"
        production_root = root / "production"
        production_events = production_root / "events"
        input_root.mkdir()
        production_events.mkdir(parents=True)
        events = ("ac0001_001", "ac0001_002")
        (input_root / "full_qa_audit.csv").write_text(
            "event,status\n" + "".join(f"{event},passed\n" for event in events),
            encoding="utf-8",
        )
        ready_markers: dict[str, Path] = {}
        sidecars: dict[tuple[str, str], Path] = {}

        for event_index, event in enumerate(events):
            event_dir = input_root / event
            event_dir.mkdir()
            source_manifest = event_dir / "event_manifest.json"
            source_manifest.write_text(
                json.dumps(
                    {
                        "event": event,
                        "native_frame_rate": "30/1",
                        "render_frame_count": 15,
                        "render_duration_ms": 500,
                        "render_duration_quantization": {
                            "frame_rate": "30/1",
                            "frame_count": 15,
                            "content_end_ms": 500,
                            "duration_ms": 500,
                            "exact_duration_ms_numerator": 500,
                            "exact_duration_ms_denominator": 1,
                            "audio_sample_rate": 48000,
                            "audio_sample_count": 24000,
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            source_contract_sha256 = (
                render_subtitle_editions.event_contract_projection_sha256(
                    source_manifest
                )
            )
            subtitles: dict[str, Path] = {}
            cue_text = {"ja": f"日本語{event_index}", "zh": f"中文{event_index}"}
            for language, text in cue_text.items():
                subtitle = event_dir / f"{language}.srt"
                subtitle.write_text(
                    f"1\n00:00:00,050 --> 00:00:00,450\n{text}\n",
                    encoding="utf-8",
                )
                subtitles[language] = subtitle

            profile_records: dict[str, dict] = {}
            for profile_index, profile in enumerate(("with_bgm", "no_bgm")):
                base_video = event_dir / f"{profile}-none.mp4"
                colour = "red" if event_index == 0 else "blue"
                frequency = 440 + event_index * 40 + profile_index * 440
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
                        f"sine=frequency={frequency}:sample_rate=48000:duration=0.5",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-g",
                        "15",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-ar",
                        "48000",
                        "-ac",
                        "2",
                        "-shortest",
                        "-map_metadata",
                        "-1",
                        str(base_video),
                    ],
                    check=True,
                )
                for language in ("ja", "zh"):
                    shutil.copy2(base_video, event_dir / f"{profile}-{language}.mp4")
                media_probe = build_scene_editions.probe(base_video, "ffprobe")
                video_timeline = build_scene_editions.probe_video_timeline(
                    base_video,
                    "ffprobe",
                    expected_duration_ms=500,
                    expected_frame_rate="30/1",
                    label=f"{event} {profile}",
                )
                audio_audit = build_scene_editions.audio_presentation_audit(
                    base_video,
                    media_probe,
                    video_timeline,
                    "ffprobe",
                    "ffmpeg",
                    expected_samples=24000,
                )
                profile_records[profile] = {
                    "base_video": base_video,
                    "video_sha256": sha256(base_video),
                    "audio_packet_sha256": build_scene_editions.audio_hash(
                        base_video, "ffmpeg"
                    ),
                    "decoded_pcm_sha256": audio_audit[
                        "effective_decoded_pcm"
                    ]["pcm_sha256"],
                    "audio_timeline_sha256": audio_audit[
                        "packet_frame_timeline"
                    ]["timeline_sha256"],
                    "video_timeline_sha256": video_timeline["timeline_sha256"],
                    "sidecar": event_dir / f"{profile}.base_master.json",
                }

            ready_path = event_dir / "audio_base_masters.ready.json"
            ready_locator = f"complete two-profile audio transaction for {event}"
            ready_payload = {
                "schema": render_subtitle_editions.BASE_MASTER_READY_SCHEMA,
                "status": "ready",
                "publishable": True,
                "event": event,
                "source_event_contract_sha256": source_contract_sha256,
                "profiles": {
                    profile: {
                        "video": str(record["base_video"]),
                        "video_sha256": record["video_sha256"],
                        "base_master_manifest": str(record["sidecar"]),
                        "audio_timeline_sha256": record[
                            "audio_timeline_sha256"
                        ],
                    }
                    for profile, record in profile_records.items()
                },
                "publication_rule": (
                    render_subtitle_editions.BASE_MASTER_READY_PUBLICATION_RULE
                ),
            }
            ready_path.write_text(
                json.dumps(ready_payload, sort_keys=True), encoding="utf-8"
            )
            ready_reference = {
                "path": str(ready_path),
                "sha256": sha256(ready_path),
                "locator": ready_locator,
            }
            for profile, record in profile_records.items():
                sidecar_payload = {
                    "schema": render_subtitle_editions.BASE_MASTER_SCHEMA,
                    "status": "passed",
                    "publishable": True,
                    "event": event,
                    "audio_profile": profile,
                    "source_event_contract_sha256": source_contract_sha256,
                    "audio_timeline_sha256": record["audio_timeline_sha256"],
                    "output": str(record["base_video"]),
                    "output_sha256": record["video_sha256"],
                    "output_audio_packet_sha256": record[
                        "audio_packet_sha256"
                    ],
                    "output_effective_decoded_pcm_sha256": record[
                        "decoded_pcm_sha256"
                    ],
                    "presentation_sample_count": 24000,
                    "render_method": {
                        "output_encoding_contract": {
                            "codec": "aac",
                            "sample_rate": 48000,
                            "channels": 2,
                            "channel_layout": "stereo",
                            "bit_rate": 128000,
                        }
                    },
                    "transaction_ready_marker": ready_reference,
                }
                record["sidecar"].write_text(
                    json.dumps(sidecar_payload, sort_keys=True), encoding="utf-8"
                )
                sidecars[(event, profile)] = record["sidecar"]

            matrix = {}
            for profile, record in profile_records.items():
                editions = {}
                for edition in ("none", "ja", "zh"):
                    video = event_dir / f"{profile}-{edition}.mp4"
                    subtitle = subtitles.get(edition)
                    editions[edition] = {
                        "language": edition,
                        "video": str(video),
                        "subtitles": str(subtitle) if subtitle else "",
                        "audio_sha256": build_scene_editions.audio_hash(
                            video, "ffmpeg"
                        ),
                        "decoded_pcm_sha256": record["decoded_pcm_sha256"],
                        "video_sha256": sha256(video),
                        "video_packet_sha256": (
                            build_series_editions.video_packet_hash(video, "ffmpeg")
                        ),
                        "video_timeline_sha256": record[
                            "video_timeline_sha256"
                        ],
                        "subtitle_sha256": sha256(subtitle) if subtitle else "",
                    }
                matrix[profile] = {
                    "audio_profile": profile,
                    "audio_sha256": record["audio_packet_sha256"],
                    "editions": editions,
                }
            render_manifest = {
                "schema": "magireco-native-subtitle-event-editions-v3",
                "event": event,
                "source_manifest": str(source_manifest),
                "source_manifest_sha256": sha256(source_manifest),
                "edition_matrix": matrix,
                "base_master_manifests": {
                    profile: {
                        "path": str(record["sidecar"]),
                        "sha256": sha256(record["sidecar"]),
                        "locator": f"verified {profile} base master for {event}",
                    }
                    for profile, record in profile_records.items()
                },
                "edition_plan": {
                    "event": event,
                    "tracks": {
                        language: {
                            "cue_count": 1,
                            "cues": [
                                {
                                    "start_ms": 50,
                                    "end_ms": 450,
                                    "text": text,
                                }
                            ],
                        }
                        for language, text in cue_text.items()
                    },
                },
            }
            (event_dir / "render_manifest.json").write_text(
                json.dumps(render_manifest, sort_keys=True), encoding="utf-8"
            )
            (production_events / f"{event}.json").write_text(
                json.dumps(
                    {
                        "event": event,
                        "quality_gates": {"ready": True, "errors": []},
                    }
                ),
                encoding="utf-8",
            )
            ready_markers[event] = ready_path

        runtime_evidence = root / "runtime-order.jsonl"
        runtime_evidence.write_text('{"event":"runtime-order"}\n', encoding="utf-8")
        order_manifest = root / "series-order.json"
        order_manifest.write_text(
            json.dumps(
                {
                    "schema": build_series_editions.SERIES_ORDER_SCHEMA,
                    "series": "ac0001",
                    "complete": True,
                    "ordered_events": list(reversed(events)),
                    "evidence": {
                        "kind": "official_runtime",
                        "fields": ["ordered_events", "family_completeness"],
                        "references": [
                            {
                                "path": str(runtime_evidence),
                                "sha256": sha256(runtime_evidence),
                                "locator": "runtime order rows 1-2",
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        return {
            "input_root": input_root,
            "production_root": production_root,
            "order_manifest": order_manifest,
            "events": events,
            "ready_markers": ready_markers,
            "sidecars": sidecars,
        }

    @staticmethod
    def fake_probe(path: Path, _ffprobe: str) -> dict:
        duration = (
            "2.0"
            if "__series" in path.name or "__scene" in path.name
            else "1.0"
        )
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
        output_path.write_bytes(b"joined-series")

    @staticmethod
    def fake_audio_hash(path: Path, _ffmpeg: str) -> str:
        return "A" * 64 if "with_bgm" in str(path) else "B" * 64

    @staticmethod
    def fake_decoded_pcm(path: Path, _ffmpeg: str) -> str:
        return "C" * 64 if "with_bgm" in str(path) else "D" * 64

    @staticmethod
    def fake_packet_hash(path: Path, _ffmpeg: str) -> str:
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

    def build(self, fixture: dict, root: Path, **kwargs: object) -> dict:
        candidates = build_series_editions.discover_events(
            [fixture["input_root"]]
        )
        packet_side_effect = kwargs.pop("packet_hash", self.fake_packet_hash)

        def fixture_probe(path: Path, ffprobe: str) -> dict:
            result = self.fake_probe(path, ffprobe)
            if "__series" in path.name or "__scene" in path.name:
                result["format"]["duration"] = str(len(fixture["events"]))
            return result

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
                    "pcm_sha256": self.fake_decoded_pcm(path, ffmpeg),
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
            output_path.write_bytes(b"single-series-aac")
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
                    {**row, "path": str(row["path"])} for row in segments
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
            output_path.write_bytes(b"muxed-series")

        def fake_concat_decoded_hash(
            list_path: Path, media_type: str, _ffmpeg: str
        ) -> str:
            if media_type == "audio":
                return (
                    "C" * 64 if "with_bgm" in list_path.name else "D" * 64
                )
            edition = list_path.stem.rsplit("__", 1)[-1]
            return {"none": "1" * 64, "ja": "2" * 64, "zh": "3" * 64}[
                edition
            ]

        with patch.object(
            build_series_editions, "probe", side_effect=fixture_probe
        ), patch.object(
            build_series_editions, "concat_copy", side_effect=self.fake_concat
        ), patch.object(
            build_series_editions, "audio_hash", side_effect=self.fake_audio_hash
        ), patch.object(
            build_series_editions,
            "video_packet_hash",
            side_effect=packet_side_effect,
        ), patch.object(
            build_scene_editions, "probe", side_effect=fixture_probe
        ), patch.object(
            build_scene_editions,
            "concat_video_copy",
            side_effect=self.fake_concat,
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
            side_effect=fake_mux,
        ), patch.object(
            build_scene_editions,
            "load_scene_audio_sidecar",
            side_effect=fake_sidecar,
        ), patch.object(
            build_scene_editions,
            "audio_hash",
            side_effect=self.fake_audio_hash,
        ), patch.object(
            build_scene_editions,
            "audio_presentation_audit",
            side_effect=fake_audio_presentation,
        ), patch.object(
            build_scene_editions,
            "probe_video_timeline",
            side_effect=fake_timeline,
        ), patch.object(
            build_scene_editions,
            "concat_decoded_hash",
            side_effect=fake_concat_decoded_hash,
        ), patch.object(
            build_scene_editions,
            "decoded_video_hash",
            side_effect=packet_side_effect,
        ), patch.object(
            build_scene_editions.series_gate,
            "audio_hash",
            side_effect=self.fake_audio_hash,
        ), patch.object(
            build_scene_editions.series_gate,
            "video_packet_hash",
            side_effect=packet_side_effect,
        ):
            return build_series_editions.build_series(
                "ac0001",
                candidates,
                set(),
                root / "out",
                kwargs.pop("manifest_root", fixture["production_root"]),
                bool(kwargs.pop("require_complete", True)),
                "ffmpeg",
                "ffprobe",
                True,
                ["none", "ja", "zh"],
                ["with_bgm", "no_bgm"],
                False,
                kwargs.pop("order_manifest", fixture["order_manifest"]),
                bool(kwargs.pop("review_only", False)),
            )

    def test_publication_requires_order_manifest_and_fails_zero_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            candidates = build_series_editions.discover_events(
                [fixture["input_root"]]
            )
            with self.assertRaisesRegex(ValueError, "evidence-bound order manifest"):
                build_series_editions.build_series(
                    "ac0001",
                    candidates,
                    set(),
                    root / "out",
                    fixture["production_root"],
                    True,
                    "ffmpeg",
                    "ffprobe",
                    True,
                    order_manifest_path=None,
                )
            with self.assertRaisesRegex(ValueError, "zero QA-passed events"):
                build_series_editions.build_series(
                    "ac9999",
                    {},
                    set(),
                    root / "out",
                    None,
                    True,
                    "ffmpeg",
                    "ffprobe",
                    True,
                    review_only=True,
                )

    def test_partial_edition_matrix_cannot_be_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            candidates = build_series_editions.discover_events(
                [fixture["input_root"]]
            )
            with self.assertRaisesRegex(ValueError, "partial edition/audio matrix"):
                build_series_editions.build_series(
                    "ac0001",
                    candidates,
                    set(),
                    root / "out",
                    fixture["production_root"],
                    True,
                    "ffmpeg",
                    "ffprobe",
                    True,
                    ["none", "ja"],
                    ["with_bgm", "no_bgm"],
                    False,
                    fixture["order_manifest"],
                    False,
                )
    def test_publication_rejects_incomplete_order_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(
                root, ordered_events=("ac0001_001",)
            )
            with self.assertRaisesRegex(ValueError, "exact complete input list"):
                self.build(fixture, root)

    def test_order_evidence_requires_real_hash_and_locator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            payload = json.loads(fixture["order_manifest"].read_text(encoding="utf-8"))
            payload["evidence"]["references"][0]["sha256"] = "0" * 64
            fixture["order_manifest"].write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reference SHA-256 mismatch"):
                build_series_editions.load_series_order_manifest(
                    fixture["order_manifest"], expected_series="ac0001"
                )

    def test_publication_uses_evidenced_order_and_binds_qa(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            result = self.build(fixture, root)
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

            self.assertEqual(result["status"], "passed")
            self.assertTrue(result["publishable"])
            self.assertEqual(
                [row["event"] for row in manifest["sources"]],
                ["ac0001_002", "ac0001_001"],
            )
            self.assertEqual(
                manifest["ordering"], "evidence-bound narrative/runtime order"
            )
            self.assertTrue(manifest["order_contract"]["complete"])
            for row in manifest["sources"]:
                self.assertTrue(Path(row["qa_report"]).is_file())
                self.assertEqual(row["qa_report_sha256"], sha256(Path(row["qa_report"])))
                self.assertEqual(row["qa_locator"], "CSV row 3" if row["event"].endswith("002") else "CSV row 2")

    def test_all_series_post_scene_failures_preserve_previous_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            first = self.build(fixture, root)
            series_dir = root / "out" / "ac0001"
            old_tree = self.release_tree_bytes(series_dir)
            old_manifest = Path(first["manifest"]).read_bytes()
            old_ready = Path(first["ready_marker"]).read_bytes()
            manifest = json.loads(old_manifest.decode("utf-8"))
            six_outputs = [
                Path(row["video"])
                for profile in ("with_bgm", "no_bgm")
                for row in manifest["outputs"]["edition_matrix"][profile][
                    "editions"
                ].values()
            ]
            self.assertEqual(len(six_outputs), 6)
            self.assertTrue(all(path.is_file() for path in six_outputs))
            old_output_bytes = {str(path): path.read_bytes() for path in six_outputs}

            stages = (
                "order_family_refresh",
                "component_ready_archive_write",
                "series_manifest_write",
                "series_ready_switch",
                "postwrite_hash_validation",
            )
            for failed_stage in stages:
                with self.subTest(stage=failed_stage):
                    def fail_at_stage(stage: str) -> None:
                        if stage == failed_stage:
                            raise RuntimeError(f"injected {stage} failure")

                    with patch.object(
                        build_series_editions,
                        "_series_release_checkpoint",
                        side_effect=fail_at_stage,
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError, f"injected {failed_stage} failure"
                        ):
                            self.build(fixture, root)

                    self.assertEqual(
                        self.release_tree_bytes(series_dir),
                        old_tree,
                        f"published tree changed after {failed_stage}",
                    )
                    self.assertEqual(Path(first["manifest"]).read_bytes(), old_manifest)
                    self.assertEqual(Path(first["ready_marker"]).read_bytes(), old_ready)
                    self.assertEqual(
                        {str(path): path.read_bytes() for path in six_outputs},
                        old_output_bytes,
                    )
                    self.assertFalse(list((root / "out").glob(".series-staging-*")))
                    self.assertFalse(
                        list((root / "out").glob(".ac0001.previous-*"))
                    )

    def test_tampered_render_declaration_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            render_path = (
                fixture["input_root"] / "ac0001_001" / "render_manifest.json"
            )
            payload = json.loads(render_path.read_text(encoding="utf-8"))
            payload["edition_matrix"]["with_bgm"]["editions"]["ja"][
                "video_sha256"
            ] = "F" * 64
            render_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, "video SHA-256 declaration mismatch"
            ):
                self.build(fixture, root)

    def test_output_video_packets_must_match_across_audio_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)

            def mismatch_output(path: Path, ffmpeg: str) -> str:
                if (
                    ("__series" in path.name or "__scene" in path.name)
                    and "no_bgm" in str(path)
                    and "with_subtitles" in str(path)
                ):
                    return "F" * 64
                return self.fake_packet_hash(path, ffmpeg)

            with self.assertRaisesRegex(RuntimeError, "video_packet_mismatch"):
                self.build(fixture, root, packet_hash=mismatch_output)

    def test_publication_rejects_srt_that_differs_from_edition_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(root)
            event_dir = fixture["input_root"] / "ac0001_001"
            subtitle = event_dir / "ja.srt"
            subtitle.write_text(
                "1\n00:00:00,100 --> 00:00:00,800\n改ざん\n",
                encoding="utf-8",
            )
            render_path = event_dir / "render_manifest.json"
            render_manifest = json.loads(render_path.read_text(encoding="utf-8"))
            for profile in ("with_bgm", "no_bgm"):
                render_manifest["edition_matrix"][profile]["editions"]["ja"][
                    "subtitle_sha256"
                ] = sha256(subtitle)
            render_path.write_text(json.dumps(render_manifest), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError, "parsed SRT does not match audited edition_plan cues"
            ):
                self.build(fixture, root)

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "ffmpeg and ffprobe are required for exact publication media tests",
    )
    def test_real_publication_uses_single_aac_encode_and_exact_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_real_fixture(root)
            candidates = build_series_editions.discover_events(
                [fixture["input_root"]], allow_legacy=False
            )
            result = build_series_editions.build_series(
                "ac0001",
                candidates,
                set(),
                root / "out",
                fixture["production_root"],
                True,
                "ffmpeg",
                "ffprobe",
                True,
                ["none", "ja", "zh"],
                ["with_bgm", "no_bgm"],
                False,
                fixture["order_manifest"],
                False,
            )
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], "magireco-series-editions-v4")
            self.assertEqual(
                manifest["media_processing"]["audio"],
                "sidecar_trimmed_effective_pcm_concat_single_aac_encode",
            )
            ready = json.loads(Path(result["ready_marker"]).read_text(encoding="utf-8"))
            self.assertEqual(ready["schema"], "magireco-series-editions-ready-v1")
            self.assertEqual(ready["ordered_events"], ["ac0001_002", "ac0001_001"])

            profile_pcm_hashes = set()
            for profile in ("with_bgm", "no_bgm"):
                output = Path(
                    manifest["outputs"]["edition_matrix"][profile]["editions"][
                        "none"
                    ]["video"]
                )
                video_timeline = build_scene_editions.probe_video_timeline(
                    output,
                    "ffprobe",
                    expected_duration_ms=1000,
                    expected_frame_rate="30/1",
                    label=f"real series {profile}",
                )
                audio_audit = build_scene_editions.audio_presentation_audit(
                    output,
                    build_scene_editions.probe(output, "ffprobe"),
                    video_timeline,
                    "ffprobe",
                    "ffmpeg",
                    expected_samples=48000,
                )
                self.assertEqual(
                    audio_audit["expected_presentation_samples"], 48000
                )
                profile_pcm_hashes.add(
                    audio_audit["effective_decoded_pcm"]["pcm_sha256"]
                )
            self.assertEqual(len(profile_pcm_hashes), 2)

            direct_sources = [
                candidates[event]["edition_matrix"]["with_bgm"]["editions"][
                    "none"
                ]["video_path"]
                for event in ("ac0001_002", "ac0001_001")
            ]
            direct_list = root / "direct.ffconcat"
            direct_output = root / "direct-stream-copy.mp4"
            build_scene_editions.concat_copy(
                direct_sources, direct_list, direct_output, "ffmpeg", True
            )
            direct_video_timeline = build_scene_editions.probe_video_timeline(
                direct_output,
                "ffprobe",
                expected_duration_ms=1000,
                expected_frame_rate="30/1",
                label="invalid direct series concat",
            )
            with self.assertRaisesRegex(
                RuntimeError, "presentation endpoint|decoded-frame"
            ):
                build_scene_editions.audio_presentation_audit(
                    direct_output,
                    build_scene_editions.probe(direct_output, "ffprobe"),
                    direct_video_timeline,
                    "ffprobe",
                    "ffmpeg",
                    expected_samples=48000,
                )

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "ffmpeg and ffprobe are required for transaction evidence tests",
    )
    def test_real_publication_rejects_missing_ready_and_tampered_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_real_fixture(root)
            candidates = build_series_editions.discover_events(
                [fixture["input_root"]], allow_legacy=False
            )
            ready_path = fixture["ready_markers"]["ac0001_002"]
            ready_bytes = ready_path.read_bytes()
            ready_path.unlink()
            with self.assertRaises(FileNotFoundError):
                build_series_editions.build_series(
                    "ac0001",
                    candidates,
                    set(),
                    root / "out-missing-ready",
                    fixture["production_root"],
                    True,
                    "ffmpeg",
                    "ffprobe",
                    True,
                    ["none", "ja", "zh"],
                    ["with_bgm", "no_bgm"],
                    False,
                    fixture["order_manifest"],
                    False,
                )
            ready_path.write_bytes(ready_bytes)

            sidecar = fixture["sidecars"][("ac0001_002", "with_bgm")]
            sidecar.write_bytes(sidecar.read_bytes() + b"\n")
            fresh_candidates = build_series_editions.discover_events(
                [fixture["input_root"]], allow_legacy=False
            )
            with self.assertRaisesRegex(ValueError, "sidecar hash mismatch"):
                build_series_editions.build_series(
                    "ac0001",
                    fresh_candidates,
                    set(),
                    root / "out-tampered-sidecar",
                    fixture["production_root"],
                    True,
                    "ffmpeg",
                    "ffprobe",
                    True,
                    ["none", "ja", "zh"],
                    ["with_bgm", "no_bgm"],
                    False,
                    fixture["order_manifest"],
                    False,
                )

    def test_single_event_can_only_be_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = self.make_fixture(
                root,
                events=("ac0001_001",),
                ordered_events=("ac0001_001",),
            )
            with self.assertRaisesRegex(ValueError, "review-only"):
                self.build(fixture, root)
            result = self.build(
                fixture,
                root,
                order_manifest=None,
                manifest_root=None,
                review_only=True,
            )
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "review_only")
            self.assertFalse(result["publishable"])
            self.assertFalse(manifest["release_eligible"])
            self.assertIn("review-only", manifest["ordering"])


if __name__ == "__main__":
    unittest.main()
