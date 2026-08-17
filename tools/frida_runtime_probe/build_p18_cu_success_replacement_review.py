#!/usr/bin/env python3
"""Render the bounded P18 CU-success event-global no-BGM review candidate."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import uuid
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from tools.frida_runtime_probe import build_audio_base_masters as audio_gate
    from tools.frida_runtime_probe.build_independent_scene_release import (
        build_event_pcm,
        concat_binary,
        file_sha256,
        frame_count,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        volume_audit,
        write_srt,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe import build_audio_base_masters as audio_gate
    from tools.frida_runtime_probe.build_independent_scene_release import (
        build_event_pcm,
        concat_binary,
        file_sha256,
        frame_count,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        volume_audit,
        write_srt,
    )


SCHEMA = "magireco-p18-cu-success-replacement-review-plan-v1"
OUTPUT_SCHEMA = "magireco-p18-cu-success-replacement-review-v1"
QA_SCHEMA = "magireco-p18-cu-success-replacement-review-qa-v1"
EDITIONS = ("none", "ja", "zh")
LANGUAGE_ROOT = {"none": "NONE", "ja": "JP", "zh": "ZH"}
MANIFEST_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
    r"\production_manifests_v72_p18_ac6005_cu_success_event_global_timing_20260817"
)
OLD_REJECTED_HASHES = {
    "D06DE03FD23B5EF8B267141ECE0E1DB596EAEBD520FABBAD7C274F223FBA7161",
    "DCD58F978093AA401752E6623911888ECBF370AD964DFE52F02B0979EF5601FA",
    "DE095E2BC8F1A56D09FF9B642A092B14D00DACEF33B3C706B2DD71A83629B438",
}
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manifest = Join-Path $Root 'manifests/REVIEW_MANIFEST.json'
if(-not (Test-Path -LiteralPath $Manifest)){ throw 'P18 review manifest missing' }
if(-not $Apply){
  Write-Output 'ROLLBACK_VALIDATED: immutable P18 review candidate can be disabled by same-volume rename; old quarantine and source media remain untouched.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def validate_bound(row: dict, label: str) -> Path:
    if not isinstance(row, dict) or not {"path", "sha256"} <= set(row):
        raise ValueError(f"{label} binding differs")
    path = Path(str(row["path"])).resolve()
    expected = str(row["sha256"]).upper()
    if not path.is_file() or file_sha256(path) != expected:
        raise ValueError(f"{label} path or SHA-256 differs: {path}")
    return path


def safe_review_path(value: str, edition: str) -> Path:
    relative = PurePosixPath(value.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 3:
        raise ValueError(f"unsafe P18 review path: {value}")
    if relative.parts[:2] != (LANGUAGE_ROOT[edition], "routes"):
        raise ValueError(f"P18 review path lane differs: {value}")
    if not relative.name.endswith(f"__{edition}.mp4"):
        raise ValueError(f"P18 review path edition differs: {value}")
    return Path(*relative.parts)


def _video_contract(path: Path, *, ffprobe: str, expected: dict, audio: bool) -> dict:
    value = probe(path, ffprobe)
    videos = media_streams(value, "video")
    audios = media_streams(value, "audio")
    if len(videos) != 1 or len(audios) != int(audio) or media_streams(value, "subtitle"):
        raise ValueError(f"P18 stream contract differs: {path}")
    video = videos[0]
    if (
        video.get("codec_name") != expected["video_codec"]
        or int(video.get("width", 0)) != expected["width"]
        or int(video.get("height", 0)) != expected["height"]
        or video.get("r_frame_rate") != expected["frame_rate"]
        or frame_count(video) != expected["frame_count"]
    ):
        raise ValueError(f"P18 video grid differs: {path}")
    if audio:
        stream = audios[0]
        if (
            stream.get("codec_name") != expected["audio_codec"]
            or int(stream.get("sample_rate", 0)) != expected["audio_sample_rate"]
            or int(stream.get("channels", 0)) != expected["audio_channels"]
        ):
            raise ValueError(f"P18 audio format differs: {path}")
    return value


def _format_cue(dialogue: dict, *, language: str, start_ms: int, end_ms: int) -> dict:
    speaker = str(dialogue[f"speaker_{language}"]).strip()
    text = str(dialogue[f"{language}_text"]).strip()
    if not speaker or not text or not str(dialogue["speaker_evidence"]).strip():
        raise ValueError("P18 dialogue speaker/text evidence differs")
    return {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "text": f"{speaker}：{text}",
    }


def load_contract(plan_path: Path, ffprobe: str) -> tuple[dict, list[dict], list[dict]]:
    plan = read_json(plan_path)
    if (
        plan.get("schema") != SCHEMA
        or plan.get("status") != "AUTOMATED_BUILD_AUTHORIZED_HUMAN_PLAYBACK_REQUIRED"
        or plan.get("family") != "ac6005"
        or plan.get("route_id") != "kind173_row10_cu_success"
        or plan.get("ordered_events") != ["ac6005_010", "ac6005_013", "ac6005_014"]
        or plan.get("audio_profile") != "no_bgm"
        or plan.get("bgm_policy") != "intentionally_excluded"
        or plan.get("human_playback_required") is not True
        or plan.get("publishable") is not False
    ):
        raise ValueError("P18 review plan identity/readiness differs")
    expected = plan["expected_media"]
    if expected != {
        "width": 512,
        "height": 416,
        "frame_rate": "30/1",
        "frame_count": 941,
        "presentation_samples": 1505600,
        "duration_ms": 31367,
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "upscaled": False,
    }:
        raise ValueError("P18 expected media contract differs")

    summary_path = validate_bound(plan["replacement_manifest_summary"], "summary")
    authority_path = validate_bound(plan["timing_authority"], "authority")
    visual_path = validate_bound(plan["clean_visual_source"], "clean visual")
    old_route_path = validate_bound(plan["old_rejected_route_manifest"], "old route")
    rejection_path = validate_bound(plan["old_rejection_status"], "old rejection")
    validate_bound(plan["font"], "font")
    validate_bound(plan["layout"], "layout")
    summary = read_json(summary_path)
    authority = read_json(authority_path)
    old_route = read_json(old_route_path)
    rejection = read_json(rejection_path)
    if (
        summary.get("status") != "PASS"
        or summary.get("route", {}).get("events") != plan["ordered_events"]
        or authority.get("status") != "PASS"
        or authority.get("route", {}).get("events") != plan["ordered_events"]
        or old_route.get("candidate_id") != "ac6005_cu_success_route_v1"
        or rejection.get("schema") != "magireco-human-review-rejection-v1"
        or rejection.get("part") != "P18"
        or rejection.get("family") != "ac6005"
        or rejection.get("route") != plan["ordered_events"]
        or rejection.get("status") != "REJECTED_BY_PROJECT_OWNER"
        or rejection.get("publication_approved") is not False
        or {
            str(row.get("sha256", "")).upper()
            for row in rejection.get("files", [])
            if isinstance(row, dict)
        }
        != OLD_REJECTED_HASHES
    ):
        raise ValueError("P18 source state differs")
    _video_contract(visual_path, ffprobe=ffprobe, expected=expected, audio=False)

    summary_rows = {row["event"]: row for row in summary["events"]}
    plan_events = plan.get("events")
    if not isinstance(plan_events, list) or [row.get("event") for row in plan_events] != plan[
        "ordered_events"
    ]:
        raise ValueError("P18 plan event order differs")
    dialogue_rows = plan.get("dialogue")
    if not isinstance(dialogue_rows, list) or len(dialogue_rows) != 8:
        raise ValueError("P18 dialogue contract differs")
    dialogue_by_event: dict[str, list[dict]] = {event: [] for event in plan["ordered_events"]}
    seen_keys = set()
    for row in dialogue_rows:
        key = (str(row["event"]), str(row["request_id"]), str(row["z2d_name"]))
        if key in seen_keys or key[0] not in dialogue_by_event:
            raise ValueError(f"P18 duplicate/unknown dialogue key: {key}")
        seen_keys.add(key)
        dialogue_by_event[key[0]].append(row)

    event_rows: list[dict] = []
    sources = [
        binding(plan_path),
        binding(summary_path),
        binding(authority_path),
        binding(visual_path),
        binding(old_route_path),
        binding(rejection_path),
        binding(Path(plan["font"]["path"])),
        binding(Path(plan["layout"]["path"])),
    ]
    total_frames = total_samples = 0
    for event_spec in plan_events:
        event = str(event_spec["event"])
        manifest_path = MANIFEST_ROOT / "events" / f"{event}.json"
        expected_sha = str(event_spec["manifest_sha256"]).upper()
        if (
            file_sha256(manifest_path) != expected_sha
            or summary_rows[event]["output_sha256"] != expected_sha
        ):
            raise ValueError(f"{event} replacement manifest binding differs")
        manifest = read_json(manifest_path)
        gates = manifest.get("quality_gates", {})
        if (
            manifest.get("event") != event
            or gates.get("ready") is not True
            or gates.get("event_global_z2d_timing_ready") is not True
            or gates.get("audio_timeline_ready") is not True
            or gates.get("errors") != []
        ):
            raise ValueError(f"{event} replacement readiness differs")
        frame_total = int(event_spec["frame_count"])
        sample_total = int(event_spec["presentation_samples"])
        if (
            frame_total != int(manifest["render_frame_count"])
            or sample_total != frame_total * 1600
        ):
            raise ValueError(f"{event} frame/sample contract differs")
        audio_request_ids = {str(row["request_id"]) for row in manifest["audio"]}
        if "225" in audio_request_ids:
            raise ValueError(f"{event} leaked excluded BGM/victory request 225")
        subtitle_request_ids = {
            str(row["voice_request_id"])
            for row in manifest["subtitles"]
            if str(row["voice_request_id"])
        }
        runtime_sound_exact: dict[str, dict] = {}
        for index, runtime_binding in enumerate(
            manifest.get("runtime_event_manifest_sources", [])
        ):
            runtime_path = validate_bound(
                runtime_binding, f"{event} runtime event manifest {index}"
            )
            sources.append(binding(runtime_path))
            runtime_manifest = read_json(runtime_path)
            if runtime_manifest.get("event") != event:
                raise ValueError(f"{event} runtime event manifest identity differs")
            for runtime_sound in runtime_manifest.get("sound_assets", []):
                request_id = str(runtime_sound.get("request_id", ""))
                if request_id:
                    runtime_sound_exact[request_id] = runtime_sound
        audio_layers = []
        for row in manifest["audio"]:
            source = Path(row["path"]).resolve()
            source_binding = binding(source)
            sources.append(source_binding)
            request_id = str(row["request_id"])
            role = "voice" if request_id in subtitle_request_ids else "scene_se"
            if row.get("source") == "z2d_req_sound" and role != "voice":
                runtime_sound = runtime_sound_exact.get(request_id)
                if (
                    row.get("evidence") != "official_runtime_capture"
                    or runtime_sound is None
                    or int(runtime_sound.get("relative_ms", -1)) != int(row["start_ms"])
                    or int(runtime_sound.get("duration_ms", -1)) != int(row["duration_ms"])
                    or Path(str(runtime_sound.get("ogg_path", ""))).name != source.name
                    or runtime_sound.get("is_dialogue") != "no"
                ):
                    raise ValueError(f"{event}/{request_id} is unresolved Z2D audio")
            audio_layers.append(
                {
                    "request_id": request_id,
                    "role": role,
                    "path": str(source),
                    "start_ms": int(row["start_ms"]),
                    "duration_ms": int(row["duration_ms"]),
                    "source": source_binding,
                }
            )
        manifest_cues = {
            (str(row["voice_request_id"]), str(row.get("z2d_name", ""))): row
            for row in manifest["subtitles"]
        }
        expected_keys = {
            (str(row["request_id"]), str(row["z2d_name"]))
            for row in dialogue_by_event[event]
        }
        if set(manifest_cues) != expected_keys:
            raise ValueError(f"{event} dialogue key set differs")
        cues = []
        for dialogue in dialogue_by_event[event]:
            key = (str(dialogue["request_id"]), str(dialogue["z2d_name"]))
            source_cue = manifest_cues[key]
            if source_cue["text"] != dialogue["ja_text"]:
                raise ValueError(f"{event}/{key} Japanese text differs")
            cues.append(
                {
                    "request_id": key[0],
                    "z2d_name": key[1],
                    "start_ms": int(source_cue["start_ms"]),
                    "end_ms": int(source_cue["end_ms"]),
                    "dialogue": dialogue,
                }
            )
        cues.sort(key=lambda row: (row["start_ms"], row["end_ms"], row["z2d_name"]))
        event_rows.append(
            {
                "event": event,
                "frame_count": frame_total,
                "presentation_samples": sample_total,
                "audio_layers": audio_layers,
                "dialogue_cues": cues,
                "manifest_path": str(manifest_path),
                "manifest_sha256": expected_sha,
            }
        )
        sources.append(binding(manifest_path))
        total_frames += frame_total
        total_samples += sample_total
    if total_frames != expected["frame_count"] or total_samples != expected[
        "presentation_samples"
    ]:
        raise ValueError("P18 route total frame/sample contract differs")
    return plan, event_rows, sources


def _media_audit(
    path: Path,
    *,
    expected: dict,
    audio_master: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict:
    value = _video_contract(path, ffprobe=ffprobe, expected=expected, audio=True)
    audio = media_streams(value, "audio")[0]
    timeline = audio_gate._audio_packet_timeline(
        output=path,
        audio_stream=audio,
        expected_samples=expected["presentation_samples"],
        ffprobe=ffprobe,
    )
    pcm = audio_gate._effective_decoded_pcm_audit(
        output=path,
        expected_samples=expected["presentation_samples"],
        ffmpeg=ffmpeg,
    )
    return {
        "sha256": file_sha256(path),
        "video_packet_sha256": packet_hash(path, kind="video", ffmpeg=ffmpeg),
        "audio_packet_sha256": packet_hash(path, kind="audio", ffmpeg=ffmpeg),
        "audio_packet_timeline": timeline,
        "decoded_pcm": pcm,
        "same_audio_packet_as_master": packet_hash(
            path, kind="audio", ffmpeg=ffmpeg
        )
        == packet_hash(audio_master, kind="audio", ffmpeg=ffmpeg),
    }


def verify_output(plan_path: Path, output_root: Path, ffmpeg: str, ffprobe: str) -> dict:
    plan, _, sources = load_contract(plan_path, ffprobe)
    manifest_path = output_root / "manifests" / "REVIEW_MANIFEST.json"
    qa_path = output_root / "qa" / "AUTOMATED_QA.json"
    if not manifest_path.is_file() or not qa_path.is_file():
        raise ValueError("P18 review manifest or QA is missing")
    manifest = read_json(manifest_path)
    qa = read_json(qa_path)
    if (
        manifest.get("schema") != OUTPUT_SCHEMA
        or manifest.get("status") != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or manifest.get("publishable") is not False
        or qa.get("schema") != QA_SCHEMA
        or qa.get("status") != "passed"
        or qa.get("human_playback_approved") is not False
        or qa.get("publication_approved") is not False
    ):
        raise ValueError("P18 review readiness differs")
    expected = plan["expected_media"]
    audio_master = output_root / manifest["artifacts"]["audio_master"]["relative_path"]
    visual_master = output_root / manifest["artifacts"]["visual_master"]["relative_path"]
    if (
        file_sha256(audio_master)
        != manifest["artifacts"]["audio_master"]["sha256"]
        or file_sha256(visual_master)
        != manifest["artifacts"]["visual_master"]["sha256"]
        or not os.path.samefile(visual_master, Path(plan["clean_visual_source"]["path"]))
    ):
        raise ValueError("P18 master binding differs")
    verified = []
    audio_hashes = set()
    for edition in EDITIONS:
        relative = safe_review_path(plan["review_paths"][edition], edition)
        path = output_root / relative
        artifact = manifest["artifacts"][f"video_{edition}"]
        if (
            path.relative_to(output_root).as_posix() != artifact["relative_path"]
            or file_sha256(path) != artifact["sha256"]
            or artifact["sha256"] in OLD_REJECTED_HASHES
        ):
            raise ValueError(f"P18 {edition} artifact binding differs")
        audit = _media_audit(
            path,
            expected=expected,
            audio_master=audio_master,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )
        if not audit["same_audio_packet_as_master"]:
            raise ValueError(f"P18 {edition} audio packet identity differs")
        audio_hashes.add(audit["audio_packet_sha256"])
        verified.append(
            {
                "edition": edition,
                "path": str(path),
                "sha256": artifact["sha256"],
                "media": audit,
            }
        )
    if len(audio_hashes) != 1:
        raise ValueError("P18 editions do not share one AAC packet identity")
    for source in sources:
        if file_sha256(Path(source["path"])) != source["sha256"]:
            raise ValueError(f"P18 source changed during verification: {source['path']}")
    return {
        "schema": "magireco-p18-cu-success-replacement-review-verification-v1",
        "result": "PASS",
        "file_count": len(verified),
        "route_events": plan["ordered_events"],
        "human_playback_status": "HUMAN_PLAYBACK_REQUIRED",
        "publishable": False,
        "old_rejected_media_reused": False,
        "source_media_modified": False,
        "files": verified,
    }


def build(plan_path: Path, output_root: Path, ffmpeg: str, ffprobe: str) -> None:
    if output_root.exists():
        raise FileExistsError(f"immutable P18 review root exists: {output_root}")
    plan, events, sources = load_contract(plan_path, ffprobe)
    expected = plan["expected_media"]
    staging = output_root.with_name(f".{output_root.name}.staging-{uuid.uuid4().hex}")
    staging.mkdir(parents=True)
    work = staging / "work"
    work.mkdir()
    try:
        font_dir = work / "fonts"
        font_dir.mkdir()
        font_path = Path(plan["font"]["path"])
        shutil.copy2(font_path, font_dir / font_path.name)
        layout = read_json(Path(plan["layout"]["path"]))
        if (layout.get("target_width"), layout.get("target_height")) != (512, 416):
            raise ValueError("P18 subtitle layout dimensions differ")

        event_pcm = []
        event_pcm_audits = []
        timeline = []
        route_cues = []
        start_frame = start_sample = 0
        for event in events:
            pcm = work / f"{event['event']}.f32le"
            event_pcm_audits.append(build_event_pcm(event, output=pcm, ffmpeg=ffmpeg))
            event_pcm.append(pcm)
            offset_ms = round(Fraction(start_sample * 1000, 48000))
            for cue in event["dialogue_cues"]:
                route_cues.append(
                    {
                        **cue,
                        "route_start_ms": offset_ms + cue["start_ms"],
                        "route_end_ms": offset_ms + cue["end_ms"],
                    }
                )
            timeline.append(
                {
                    "event": event["event"],
                    "start_frame": start_frame,
                    "end_frame": start_frame + event["frame_count"],
                    "start_sample": start_sample,
                    "end_sample": start_sample + event["presentation_samples"],
                    "inserted_gap_frames": 0,
                }
            )
            start_frame += event["frame_count"]
            start_sample += event["presentation_samples"]
        scene_pcm = work / "scene.f32le"
        concat_binary(event_pcm, scene_pcm)
        if scene_pcm.stat().st_size != expected["presentation_samples"] * 8:
            raise ValueError("P18 route PCM byte count differs")

        masters = staging / "masters"
        masters.mkdir()
        visual_master = masters / "p18_ac6005_cu_success__clean_visual_master.mp4"
        try:
            os.link(Path(plan["clean_visual_source"]["path"]), visual_master)
            visual_link_mode = "hardlink"
        except OSError:
            shutil.copy2(Path(plan["clean_visual_source"]["path"]), visual_master)
            visual_link_mode = "copy"
        audio_master = masters / "p18_ac6005_cu_success__no_bgm_audio_master.m4a"
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "f32le",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-i",
                str(scene_pcm),
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
                str(audio_master),
            ]
        )
        audio_probe = probe(audio_master, ffprobe)
        audio_streams = media_streams(audio_probe, "audio")
        if len(audio_streams) != 1:
            raise ValueError("P18 audio master stream contract differs")
        master_timeline = audio_gate._audio_packet_timeline(
            output=audio_master,
            audio_stream=audio_streams[0],
            expected_samples=expected["presentation_samples"],
            ffprobe=ffprobe,
        )
        master_pcm = audio_gate._effective_decoded_pcm_audit(
            output=audio_master,
            expected_samples=expected["presentation_samples"],
            ffmpeg=ffmpeg,
        )
        master_packet_hash = packet_hash(audio_master, kind="audio", ffmpeg=ffmpeg)
        volume = volume_audit(audio_master, ffmpeg)
        if str(volume["max_volume_db"]).lower() == "-inf":
            raise ValueError("P18 no-BGM master is unexpectedly silent")

        subtitle_dir = staging / "subtitles"
        subtitle_dir.mkdir()
        srt_paths = {}
        for language in ("ja", "zh"):
            rows = [
                _format_cue(
                    cue["dialogue"],
                    language=language,
                    start_ms=cue["route_start_ms"],
                    end_ms=cue["route_end_ms"],
                )
                for cue in route_cues
            ]
            path = subtitle_dir / f"p18_ac6005_cu_success__{language}.srt"
            write_srt(path, rows)
            parsed = parse_srt(path)
            if parsed != rows:
                raise ValueError(f"P18 {language} SRT round trip differs")
            srt_paths[language] = path

        output_paths = {}
        media_audits = {}
        for edition in EDITIONS:
            relative = safe_review_path(plan["review_paths"][edition], edition)
            output = staging / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            command = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                visual_master.relative_to(staging).as_posix(),
                "-i",
                audio_master.relative_to(staging).as_posix(),
            ]
            if edition == "none":
                command.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy"])
            else:
                filter_value = subtitle_filter(
                    layout,
                    srt_path=srt_paths[edition].relative_to(staging).as_posix(),
                    fonts_dir=font_dir.relative_to(staging).as_posix(),
                )
                command.extend(
                    [
                        "-vf",
                        filter_value,
                        "-map",
                        "0:v:0",
                        "-map",
                        "1:a:0",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "slow",
                        "-crf",
                        "14",
                        "-pix_fmt",
                        "yuv420p",
                        "-frames:v",
                        str(expected["frame_count"]),
                    ]
                )
            command.extend(["-c:a", "copy", "-movflags", "+faststart", output.relative_to(staging).as_posix()])
            run(command, cwd=staging)
            output_paths[edition] = output
            media_audits[edition] = _media_audit(
                output,
                expected=expected,
                audio_master=audio_master,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            if media_audits[edition]["sha256"] in OLD_REJECTED_HASHES:
                raise ValueError(f"P18 {edition} reused rejected media")
        if {row["audio_packet_sha256"] for row in media_audits.values()} != {
            master_packet_hash
        }:
            raise ValueError("P18 selected editions do not share one AAC packet")
        if media_audits["none"]["video_packet_sha256"] != packet_hash(
            visual_master, kind="video", ffmpeg=ffmpeg
        ):
            raise ValueError("P18 none edition changed the visual packet stream")

        for source in sources:
            if file_sha256(Path(source["path"])) != source["sha256"]:
                raise ValueError(f"P18 source changed during render: {source['path']}")
        source_index = {(row["path"], row["sha256"]): row for row in sources}
        source_snapshots = list(source_index.values())

        qa = {
            "schema": QA_SCHEMA,
            "status": "passed",
            "candidate_only": True,
            "human_playback_approved": False,
            "publication_approved": False,
            "checks": {
                "dirinfo_route_exact": True,
                "parent_scene_timing_exact": True,
                "ac6005_013_runtime_exact_retained": True,
                "request5409_parent_frame96_start": True,
                "request2795_graphical_continuation_split": True,
                "old_rejected_media_not_reused": True,
                "no_bgm_request225_excluded": True,
                "voice_and_scene_se_hash_bound": True,
                "native_pixels_preserved_without_upscale": True,
                "exact_941_frame_1505600_sample_grid": True,
                "aac_encoded_once_and_packet_identical": True,
                "none_video_packet_equals_visual_master": True,
                "ja_zh_srt_round_trip": True,
                "source_hashes_unchanged": True,
                "human_and_publication_status_false": True,
            },
            "timeline": timeline,
            "event_pcm_audits": event_pcm_audits,
            "audio_master_packet_sha256": master_packet_hash,
            "audio_master_packet_timeline": master_timeline,
            "audio_master_decoded_pcm": master_pcm,
            "volume": volume,
            "media": media_audits,
        }
        qa_path = staging / "qa" / "AUTOMATED_QA.json"
        write_json(qa_path, qa)
        artifacts = {
            "visual_master": {
                "relative_path": visual_master.relative_to(staging).as_posix(),
                "sha256": file_sha256(visual_master),
                "link_mode": visual_link_mode,
            },
            "audio_master": {
                "relative_path": audio_master.relative_to(staging).as_posix(),
                "sha256": file_sha256(audio_master),
            },
            "qa": {
                "relative_path": qa_path.relative_to(staging).as_posix(),
                "sha256": file_sha256(qa_path),
            },
        }
        for edition, path in output_paths.items():
            artifacts[f"video_{edition}"] = {
                "relative_path": path.relative_to(staging).as_posix(),
                "sha256": file_sha256(path),
            }
        for language, path in srt_paths.items():
            artifacts[f"subtitles_{language}"] = {
                "relative_path": path.relative_to(staging).as_posix(),
                "sha256": file_sha256(path),
            }
        review_manifest = {
            "schema": OUTPUT_SCHEMA,
            "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
            "family": "ac6005",
            "route_id": plan["route_id"],
            "ordered_events": plan["ordered_events"],
            "audio_profile": "no_bgm",
            "bgm_policy": "intentionally_excluded",
            "human_playback_status": "HUMAN_PLAYBACK_REQUIRED",
            "publishable": False,
            "old_quarantine_retained": True,
            "old_candidate_superseded": False,
            "source_media_modified": False,
            "expected_media": expected,
            "timeline": timeline,
            "source_snapshots": source_snapshots,
            "artifacts": artifacts,
        }
        manifest_path = staging / "manifests" / "REVIEW_MANIFEST.json"
        write_json(manifest_path, review_manifest)
        with (staging / "manifests" / "REVIEW_INDEX.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as target:
            fields = [
                "edition",
                "relative_path",
                "sha256",
                "duration_ms",
                "width",
                "height",
                "frame_rate",
                "audio_profile",
                "automated_qa",
                "human_status",
                "suggested_action",
            ]
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            for edition in EDITIONS:
                writer.writerow(
                    {
                        "edition": edition,
                        "relative_path": artifacts[f"video_{edition}"]["relative_path"],
                        "sha256": artifacts[f"video_{edition}"]["sha256"],
                        "duration_ms": expected["duration_ms"],
                        "width": expected["width"],
                        "height": expected["height"],
                        "frame_rate": expected["frame_rate"],
                        "audio_profile": "no_bgm",
                        "automated_qa": "passed",
                        "human_status": "HUMAN_PLAYBACK_REQUIRED",
                        "suggested_action": "review_do_not_upload_yet",
                    }
                )
        lines = [
            "# P18 ac6005 CU成功路线修复候选",
            "",
            "状态：自动 QA 已通过；旧 P18 仍保持隔离。请先完整播放 ZH，当前不要投稿。",
            "",
            "## 首看文件",
            f"`{plan['review_paths']['zh']}`",
            "",
            "## 重点区间",
        ]
        for interval in plan["review_intervals"]:
            lines.append(
                f"- {interval['start_ms']/1000:.3f}–{interval['end_ms']/1000:.3f}s：{interval['focus']}"
            )
        lines.extend(
            [
                "",
                "## 验收边界",
                "- 检查人物张嘴、语音起点、字幕起止与三事件边界。",
                "- 确认后才可 supersede 旧隔离版本；自动 QA 本身不代表人工通过。",
            ]
        )
        (staging / "START_HERE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (staging / "ROLLBACK.ps1").write_text(ROLLBACK_SCRIPT, encoding="utf-8")
        shutil.rmtree(work)
        os.replace(staging, output_root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    write_json(
        output_root / "manifests" / "VERIFICATION.json",
        verify_output(plan_path, output_root, ffmpeg, ffprobe),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.verify_only:
        result = verify_output(
            args.plan.resolve(), args.output_root.resolve(), args.ffmpeg, args.ffprobe
        )
    else:
        build(args.plan.resolve(), args.output_root.resolve(), args.ffmpeg, args.ffprobe)
        result = read_json(args.output_root / "manifests" / "VERIFICATION.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
