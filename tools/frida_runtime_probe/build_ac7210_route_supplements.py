#!/usr/bin/env python3
"""Build the finite P25/ac7210 route review and approved sibling editions.

DirInfo proves two mutually exclusive clean-story routes:

* row 0: ac7210_001 -> _002 -> _003 -> _004
* row 1: ac7210_001 -> _005 -> _003 -> _004

The historical v29 mode preserves the existing uploaded P25 and builds the two
Chinese review candidates.  The v30 mode is narrower still: it accepts only the
owner-approved v29 row-0/row-1 presentation contract, renders ``none`` and
``JA`` siblings from the same event presentation timeline, and hard-links the
two exact approved ``ZH`` files without re-encoding them.

Static evidence still does not turn the approved editorial hold used by
``ac7210_002`` and ``ac7210_003`` into new runtime timing evidence.  DirInfo
rows 2-4 remain explicitly excluded because their terminal events are
component-only and lack a closed clean-story composition/timing contract.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_audio_base_masters as audio_gate
    from .build_ac0908_reference_showcase import (
        FPS,
        HEIGHT,
        SAMPLE_RATE,
        SAMPLES_PER_FRAME,
        WIDTH,
        assert_srt_round_trip,
        milliseconds_for_samples,
        normalized_path,
        read_json,
        relative_output_path,
        validate_bound_file,
        validate_output_media,
        validate_video_grid,
    )
    from .build_independent_scene_release import (
        build_event_pcm,
        file_sha256,
        frame_count,
        media_streams,
        parse_srt,
        packet_hash,
        probe,
        run,
        stream_bit_rate,
        subtitle_filter,
        write_json,
    )
    from .build_sp_story_chapter_reviews import FORBIDDEN_AUDIO_REQUESTS
except ImportError:  # direct script execution
    import build_audio_base_masters as audio_gate  # type: ignore
    from build_ac0908_reference_showcase import (  # type: ignore
        FPS,
        HEIGHT,
        SAMPLE_RATE,
        SAMPLES_PER_FRAME,
        WIDTH,
        assert_srt_round_trip,
        milliseconds_for_samples,
        normalized_path,
        read_json,
        relative_output_path,
        validate_bound_file,
        validate_output_media,
        validate_video_grid,
    )
    from build_independent_scene_release import (  # type: ignore
        build_event_pcm,
        file_sha256,
        frame_count,
        media_streams,
        parse_srt,
        packet_hash,
        probe,
        run,
        stream_bit_rate,
        subtitle_filter,
        write_json,
    )
    from build_sp_story_chapter_reviews import (  # type: ignore
        FORBIDDEN_AUDIO_REQUESTS,
    )


PLAN_SCHEMA = "magireco-ac7210-route-supplement-plan-v1"
MANIFEST_SCHEMA = "magireco-ac7210-route-supplement-manifest-v1"
QA_SCHEMA = "magireco-ac7210-route-supplement-qa-v1"
STATUS = "PRESENTATION_BOUNDARY_RISK_HUMAN_REVIEW_REQUIRED"

PRODUCTION_PLAN_SCHEMA = "magireco-ac7210-approved-route-editions-plan-v1"
PRODUCTION_MANIFEST_SCHEMA = "magireco-ac7210-approved-route-editions-manifest-v1"
PRODUCTION_QA_SCHEMA = "magireco-ac7210-approved-route-editions-qa-v1"
PRODUCTION_STATUS = "OWNER_APPROVED_PRESENTATION_FULL_PRODUCTION_COMPLETE"
PRODUCTION_EDITIONS = ("none", "ja", "zh")
EXPECTED_ROUTES = {
    0: ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_004"],
    1: ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_004"],
}
EXCLUDED_ROUTES = {
    2: ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_006"],
    3: ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_006"],
    4: ["ac7210_007", "ac7210_008"],
}
APPROVED_ZH_SHA256 = {
    0: "8927CFDF7497B63B4FA47D7D9DB0C340FC837596547F3B9F4E8E15C764079088",
    1: "990407DD95ABC18911782AFA9F2EC7AA3E2F17997BA9F716892D1AFFB1A06849",
}


def validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "finite_human_review_candidate"
        or plan.get("series") != "ac7210"
    ):
        raise ValueError("unsupported ac7210 route supplement plan")
    if (
        plan.get("uploaded_media_policy")
        != "preserve_exact_uploaded_p25_read_only_never_overwrite"
    ):
        raise ValueError("uploaded P25 preservation policy differs")
    if (
        plan.get("presentation_boundary_policy")
        != "hold_last_frame_to_verified_parent_scene_audio_tail_manual_review_only"
    ):
        raise ValueError("ac7210 presentation-boundary policy differs")

    plan_dir = plan_path.parent
    sources: list[dict[str, str]] = []
    dirinfo_path, snapshot = validate_bound_file(
        plan["dirinfo"], label="DirInfo route evidence", plan_dir=plan_dir
    )
    sources.append(snapshot)
    uploaded_path, snapshot = validate_bound_file(
        plan["uploaded_p25_zh"],
        label="owner-uploaded exact P25 ZH",
        plan_dir=plan_dir,
    )
    sources.append(snapshot)
    family_manifest_path, snapshot = validate_bound_file(
        plan["v24_family_manifest"],
        label="P25 v24 family manifest",
        plan_dir=plan_dir,
    )
    sources.append(snapshot)
    srt_path, snapshot = validate_bound_file(
        plan["v24_zh_srt"],
        label="P25 v24 Chinese subtitle timing",
        plan_dir=plan_dir,
    )
    sources.append(snapshot)
    layout_path, snapshot = validate_bound_file(
        plan["subtitle_layout"], label="416x232 subtitle layout", plan_dir=plan_dir
    )
    sources.append(snapshot)
    font_path, snapshot = validate_bound_file(
        plan["font"], label="audited subtitle font", plan_dir=plan_dir
    )
    sources.append(snapshot)

    family_manifest = read_json(family_manifest_path)
    if (
        family_manifest.get("schema")
        != "magireco-no-bgm-story-family-editions-v1"
        or family_manifest.get("family") != "ac7210"
        or family_manifest.get("ordered_events")
        != ["ac7210_001", "ac7210_004", "ac7210_005"]
    ):
        raise ValueError("P25 v24 family manifest identity differs")
    source_by_path = {
        normalized_path(Path(str(row["path"]))): str(row["sha256"]).upper()
        for row in family_manifest.get("source_snapshots", [])
        if isinstance(row, Mapping)
        and str(row.get("path", "")).strip()
        and str(row.get("sha256", "")).strip()
    }
    timeline_by_event = {
        str(row["event"]): row
        for row in family_manifest.get("timeline", [])
        if isinstance(row, Mapping)
    }
    full_srt = parse_srt(srt_path)

    events: dict[str, dict[str, Any]] = {}
    existing = plan.get("existing_events")
    if not isinstance(existing, Mapping) or set(existing) != {
        "ac7210_001",
        "ac7210_004",
        "ac7210_005",
    }:
        raise ValueError("ac7210 existing event bindings differ")
    for event_name, row in existing.items():
        if not isinstance(row, Mapping):
            raise ValueError(f"{event_name} binding is invalid")
        prepared_path, prepared_snapshot = validate_bound_file(
            row["prepared_manifest"],
            label=f"{event_name} prepared v24 manifest",
            plan_dir=plan_dir,
        )
        clean_path, clean_snapshot = validate_bound_file(
            row["clean_visual"],
            label=f"{event_name} clean visual",
            plan_dir=plan_dir,
        )
        sources.extend([prepared_snapshot, clean_snapshot])
        prepared = read_json(prepared_path)
        frames = int(row["frame_count"])
        if (
            prepared.get("schema") != "magireco-event-production-v3"
            or prepared.get("event") != event_name
            or int(prepared.get("render_frame_count", -1)) != frames
            or prepared.get("native_dimensions") != {"width": WIDTH, "height": HEIGHT}
            or prepared.get("native_frame_rate") != "30/1"
        ):
            raise ValueError(f"{event_name} prepared manifest differs")
        validate_video_grid(
            clean_path,
            expected_frames=frames,
            ffprobe=ffprobe,
            label=f"{event_name} clean visual",
        )
        audio_layers = []
        for audio in prepared.get("audio", []):
            if (
                not isinstance(audio, Mapping)
                or str(audio.get("request_id", "")) in FORBIDDEN_AUDIO_REQUESTS
            ):
                raise ValueError(f"{event_name} contains forbidden audio")
            audio_path = Path(str(audio["path"])).resolve()
            expected_hash = source_by_path.get(normalized_path(audio_path))
            if (
                not audio_path.is_file()
                or expected_hash is None
                or file_sha256(audio_path) != expected_hash
            ):
                raise ValueError(f"{event_name} audio source binding differs")
            sources.append(
                {
                    "label": f"{event_name} audio request {audio['request_id']}",
                    "path": str(audio_path),
                    "sha256": expected_hash,
                }
            )
            audio_layers.append(
                {
                    "path": audio_path,
                    "start_ms": int(audio["start_ms"]),
                    "request_id": str(audio["request_id"]),
                    "role": (
                        "voice"
                        if str(audio.get("request_id", ""))
                        in {
                            str(cue.get("voice_request_id", ""))
                            for cue in prepared.get("subtitles", [])
                            if isinstance(cue, Mapping)
                        }
                        else "scene_se"
                    ),
                }
            )
        timeline = timeline_by_event.get(event_name)
        if not isinstance(timeline, Mapping):
            raise ValueError(f"{event_name} lacks one v24 timeline row")
        offset_ms = milliseconds_for_samples(int(timeline["start_sample"]))
        end_ms = milliseconds_for_samples(int(timeline["end_sample"]))
        local_cues = [
            {
                "start_ms": int(cue["start_ms"]) - offset_ms,
                "end_ms": int(cue["end_ms"]) - offset_ms,
                "text": str(cue["text"]),
            }
            for cue in full_srt
            if offset_ms <= int(cue["start_ms"]) < end_ms
        ]
        if len(local_cues) != int(row["expected_zh_cue_count"]):
            raise ValueError(f"{event_name} Chinese cue count differs")
        events[event_name] = {
            "event": event_name,
            "frame_count": frames,
            "presentation_samples": frames * SAMPLES_PER_FRAME,
            "clean_visual": clean_path,
            "audio_layers": audio_layers,
            "local_zh_cues": local_cues,
            "evidence_class": "v24_existing_event",
        }

    manual = plan.get("manual_events")
    if not isinstance(manual, Mapping) or set(manual) != {
        "ac7210_002",
        "ac7210_003",
    }:
        raise ValueError("ac7210 manual event bindings differ")
    manual_specs: dict[str, dict[str, Any]] = {}
    for event_name, row in manual.items():
        if not isinstance(row, Mapping):
            raise ValueError(f"{event_name} manual event binding is invalid")
        clips = []
        source_frame_total = 0
        for index, clip in enumerate(row.get("clips", [])):
            if not isinstance(clip, Mapping):
                raise ValueError(f"{event_name} clip binding is invalid")
            path, clip_snapshot = validate_bound_file(
                {"path": clip["path"], "sha256": clip["sha256"]},
                label=f"{event_name} official visual clip {index}",
                plan_dir=plan_dir,
            )
            frames = int(clip["frame_count"])
            validate_video_grid(
                path,
                expected_frames=frames,
                ffprobe=ffprobe,
                label=f"{event_name} official visual clip {index}",
            )
            sources.append(clip_snapshot)
            clips.append({"path": path, "frame_count": frames})
            source_frame_total += frames
        audio_path, audio_snapshot = validate_bound_file(
            row["scene_audio"],
            label=f"{event_name} verified parent scene audio",
            plan_dir=plan_dir,
        )
        sources.append(audio_snapshot)
        target_frames = int(row["target_frame_count"])
        if source_frame_total <= 0 or target_frames <= source_frame_total:
            raise ValueError(f"{event_name} hold-tail frame contract differs")
        manual_specs[event_name] = {
            "event": event_name,
            "clips": clips,
            "source_frame_count": source_frame_total,
            "frame_count": target_frames,
            "audio_path": audio_path,
            "audio_request_id": str(row["audio_request_id"]),
        }
        events[event_name] = {
            "event": event_name,
            "frame_count": target_frames,
            "presentation_samples": target_frames * SAMPLES_PER_FRAME,
            "audio_layers": [
                {
                    "path": audio_path,
                    "start_ms": 0,
                    "request_id": str(row["audio_request_id"]),
                    "role": "scene_se",
                }
            ],
            "local_zh_cues": [],
            "evidence_class": "static_parent_scene_audio_hold_tail_candidate",
        }

    routes = plan.get("routes")
    if not isinstance(routes, list) or len(routes) != 2:
        raise ValueError("exactly two ac7210 route candidates are required")
    expected_routes = {
        0: ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_004"],
        1: ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_004"],
    }
    resolved_routes = []
    for route in routes:
        if not isinstance(route, Mapping):
            raise ValueError("invalid ac7210 route row")
        row_number = int(route["dirinfo_row"])
        ordered = [str(value) for value in route["ordered_events"]]
        if expected_routes.get(row_number) != ordered:
            raise ValueError(f"ac7210 DirInfo row {row_number} order differs")
        expected_frames = sum(events[event]["frame_count"] for event in ordered)
        if expected_frames != int(route["expected_frame_count"]):
            raise ValueError(f"ac7210 row {row_number} frame count differs")
        resolved_routes.append(
            {
                "dirinfo_row": row_number,
                "route_id": str(route["route_id"]),
                "title": str(route["title"]),
                "ordered_events": ordered,
                "expected_frame_count": expected_frames,
            }
        )

    return {
        "release_id": str(plan["release_id"]),
        "dirinfo_path": dirinfo_path,
        "uploaded_p25_path": uploaded_path,
        "layout": read_json(layout_path),
        "font_path": font_path,
        "events": events,
        "manual_specs": manual_specs,
        "routes": resolved_routes,
        "source_snapshots": sources,
    }


def build_manual_visual(
    *,
    event: Mapping[str, Any],
    output: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    filters = []
    labels = []
    for index, clip in enumerate(event["clips"]):
        command.extend(["-i", str(clip["path"])])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={clip['frame_count']},"
            f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=1:a=0,"
        "tpad=stop_mode=clone:stop_duration=10,"
        f"trim=end_frame={event['frame_count']},"
        f"setpts=N/({FPS}*TB),format=yuv420p[out]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(event["frame_count"]),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run(command)
    return validate_video_grid(
        output,
        expected_frames=int(event["frame_count"]),
        ffprobe=ffprobe,
        label=f"{event['event']} manual clean visual",
    )


def copy_pcm(source: Path, target: Any) -> None:
    with source.open("rb") as handle:
        shutil.copyfileobj(handle, target, 1024 * 1024)


def build_route(
    *,
    route: Mapping[str, Any],
    events: Mapping[str, Mapping[str, Any]],
    event_pcm: Mapping[str, Path],
    clean_visuals: Mapping[str, Path],
    layout: Mapping[str, Any],
    staged_font_dir: Path,
    staging: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    route_id = str(route["route_id"])
    route_root = staging / route_id
    route_root.mkdir()
    work = route_root / "work"
    work.mkdir()
    timeline = []
    cues = []
    total_frames = 0
    total_samples = 0
    scene_pcm = work / "scene.f32le"
    with scene_pcm.open("wb") as target:
        for event_name in route["ordered_events"]:
            event = events[event_name]
            start_frame = total_frames
            start_sample = total_samples
            copy_pcm(event_pcm[event_name], target)
            offset_ms = milliseconds_for_samples(start_sample)
            for cue in event["local_zh_cues"]:
                cues.append(
                    {
                        "start_ms": offset_ms + int(cue["start_ms"]),
                        "end_ms": offset_ms + int(cue["end_ms"]),
                        "text": str(cue["text"]),
                    }
                )
            total_frames += int(event["frame_count"])
            total_samples += int(event["presentation_samples"])
            timeline.append(
                {
                    "event": event_name,
                    "start_frame": start_frame,
                    "end_frame": total_frames,
                    "start_sample": start_sample,
                    "end_sample": total_samples,
                    "evidence_class": event["evidence_class"],
                }
            )
    if total_frames != int(route["expected_frame_count"]):
        raise RuntimeError(f"{route_id} frame total differs")
    if scene_pcm.stat().st_size != total_samples * 8:
        raise RuntimeError(f"{route_id} PCM byte count differs")

    audio_master = route_root / f"{route_id}__no_bgm_audio_master.m4a"
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
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-i",
            str(scene_pcm),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(audio_master),
        ]
    )
    srt_path = route_root / f"{route_id}__zh.srt"
    assert_srt_round_trip(srt_path, cues)
    visuals = [clean_visuals[event] for event in route["ordered_events"]]
    filters = []
    labels = []
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for index, (event_name, visual) in enumerate(
        zip(route["ordered_events"], visuals, strict=True)
    ):
        command.extend(["-i", str(visual)])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={events[event_name]['frame_count']},"
            f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[joined]"
    )
    subtitle_value = subtitle_filter(
        layout,
        srt_path=srt_path.relative_to(staging).as_posix(),
        fonts_dir=staged_font_dir.relative_to(staging).as_posix(),
    )
    filters.append(f"[joined]{subtitle_value}[outv]")
    audio_index = len(visuals)
    command.extend(["-i", str(audio_master)])
    review_dir = staging / "REVIEW_NOW_2_MP4"
    review_dir.mkdir(exist_ok=True)
    output = review_dir / f"{route['title']}__zh.mp4"
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map",
            f"{audio_index}:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-frames:v",
            str(total_frames),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run(command, cwd=staging)
    media = validate_output_media(
        output, expected_frames=total_frames, ffprobe=ffprobe
    )
    media["path"] = relative_output_path(output, staging=staging)
    return {
        "route_id": route_id,
        "dirinfo_row": int(route["dirinfo_row"]),
        "ordered_events": list(route["ordered_events"]),
        "timeline": timeline,
        "subtitle_cue_count": len(cues),
        "media": media,
    }


def build(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> Path:
    plan = read_json(plan_path)
    resolved = validate_plan(plan, plan_path=plan_path, ffprobe=ffprobe)
    destination = output_root.resolve()
    if destination.exists():
        raise FileExistsError(f"versioned P25 supplement root exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        work = staging / "work"
        work.mkdir()
        staged_font_dir = work / "fonts"
        staged_font_dir.mkdir()
        shutil.copy2(
            resolved["font_path"], staged_font_dir / resolved["font_path"].name
        )
        clean_visuals = {
            event_name: Path(str(event["clean_visual"]))
            for event_name, event in resolved["events"].items()
            if event.get("clean_visual")
        }
        manual_visual_audits = {}
        for event_name, spec in resolved["manual_specs"].items():
            output = work / f"{event_name}__clean_visual.mp4"
            manual_visual_audits[event_name] = build_manual_visual(
                event=spec,
                output=output,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            clean_visuals[event_name] = output

        event_pcm = {}
        event_pcm_audits = {}
        for event_name, event in resolved["events"].items():
            output = work / f"{event_name}.f32le"
            event_pcm_audits[event_name] = build_event_pcm(
                event, output=output, ffmpeg=ffmpeg
            )
            event_pcm[event_name] = output

        route_results = [
            build_route(
                route=route,
                events=resolved["events"],
                event_pcm=event_pcm,
                clean_visuals=clean_visuals,
                layout=resolved["layout"],
                staged_font_dir=staged_font_dir,
                staging=staging,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            for route in resolved["routes"]
        ]
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": STATUS,
            "release_id": resolved["release_id"],
            "family": "ac7210",
            "product_scope": "two independent DirInfo route-completion candidates",
            "uploaded_media_policy": "preserve_exact_uploaded_p25_read_only_never_overwrite",
            "presentation_boundary_policy": (
                "hold_last_frame_to_verified_parent_scene_audio_tail_manual_review_only"
            ),
            "human_playback_approved": False,
            "publication_approved": False,
            "routes": route_results,
            "manual_visual_audits": manual_visual_audits,
            "event_pcm_audits": event_pcm_audits,
            "source_snapshots": resolved["source_snapshots"],
        }
        manifest_path = staging / "SUPPLEMENT_MANIFEST.json"
        write_json(manifest_path, manifest)
        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS,
            "automated_spec_qa_passed": True,
            "human_playback_approved": False,
            "publication_approved": False,
            "checks": {
                "two_routes_independent": True,
                "dirinfo_order_exact": True,
                "native_416x232_30fps": True,
                "h264_aac_48khz_stereo": True,
                "no_upscale": True,
                "bgm_intentionally_excluded": True,
                "uploaded_p25_not_overwritten": True,
                "presentation_boundary_risk_declared": True,
            },
        }
        qa_path = staging / "AUTOMATED_QA.json"
        write_json(qa_path, qa)
        review_dir = staging / "REVIEW_NOW_2_MP4"
        review_status = {
            "schema": "magireco-human-review-status-v1",
            "status": STATUS,
            "human_playback_approved": False,
            "publication_approved": False,
            "review_files": [
                {
                    "filename": Path(result["media"]["path"]).name,
                    "sha256": result["media"]["sha256"],
                    "dirinfo_row": result["dirinfo_row"],
                }
                for result in route_results
            ],
            "review_focus": [
                "row0 must be 001-002-003-004",
                "row1 must be 001-005-003-004",
                "review each hold-tail boundary entering ac7210_003 and ac7210_004",
                "recheck the ac7210_004 and ac7210_005 voice/mouth/subtitle timing",
                "no BGM; verified dialogue and scene SE remain audible"
            ],
            "warning": (
                "Static evidence does not prove whether ac7210_002/_003 scene "
                "audio overlaps the next event. These candidates hold the last "
                "frame through each sound tail."
            ),
        }
        write_json(review_dir / "HUMAN_REVIEW_REQUIRED.json", review_status)
        hash_manifest = {
            "schema": "magireco-review-directory-sha256-v1",
            "status": STATUS,
            "files": [
                {
                    "path": Path(result["media"]["path"]).name,
                    "sha256": result["media"]["sha256"],
                    "byte_count": result["media"]["byte_count"],
                }
                for result in route_results
            ],
            "supplement_manifest_sha256": file_sha256(manifest_path),
            "automated_qa_sha256": file_sha256(qa_path),
            "human_playback_approved": False,
            "publication_approved": False,
        }
        write_json(review_dir / "MANIFEST_SHA256.json", hash_manifest)
        (review_dir / "README_REVIEW_NOW.md").write_text(
            "# P25 ac7210 路线补全人工审查\n\n"
            "本目录只有两个 ZH 候选：DirInfo row0 与 row1。它们互斥，不能合称"
            "一次自然播放。原先已投稿 P25 保持只读，没有被覆盖。\n\n"
            "`ac7210_002` 和 `_003` 暂按已验证父场景声音尾部保持最后一帧，"
            "因此仍需重点观看进入下一事件的边界；人工确认前不得投稿。\n",
            encoding="utf-8",
        )
        staging.replace(destination)
        return destination
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def deduplicate_source_snapshots(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Return one immutable SHA binding per source path, failing on disagreement."""

    by_path: dict[str, dict[str, str]] = {}
    ordered_paths: list[str] = []
    for raw in rows:
        path = Path(str(raw.get("path", ""))).resolve()
        sha256 = str(raw.get("sha256", "")).strip().upper()
        label = str(raw.get("label", "")).strip()
        if not path.is_file() or len(sha256) != 64:
            raise ValueError(f"invalid source snapshot: {raw}")
        key = normalized_path(path)
        existing = by_path.get(key)
        if existing is not None:
            if existing["sha256"] != sha256:
                raise ValueError(f"conflicting source hashes for {path}")
            continue
        by_path[key] = {"label": label, "path": str(path), "sha256": sha256}
        ordered_paths.append(key)
    return [by_path[key] for key in ordered_paths]


def assert_source_snapshots_unchanged(
    rows: Sequence[Mapping[str, Any]],
) -> None:
    for raw in rows:
        path = Path(str(raw["path"])).resolve()
        expected = str(raw["sha256"]).upper()
        if not path.is_file() or file_sha256(path) != expected:
            raise RuntimeError(f"production source changed during build: {path}")


def extract_event_local_cues(
    cues: Sequence[Mapping[str, Any]],
    timeline: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Split one family SRT by the v24 event presentation sample timeline."""

    by_event: dict[str, list[dict[str, Any]]] = {}
    assigned = 0
    for raw_timeline in timeline:
        event = str(raw_timeline.get("event", "")).strip()
        if not event or event in by_event:
            raise ValueError("v24 subtitle timeline has a missing or repeated event")
        start_ms = milliseconds_for_samples(int(raw_timeline["start_sample"]))
        end_ms = milliseconds_for_samples(int(raw_timeline["end_sample"]))
        if start_ms < 0 or end_ms <= start_ms:
            raise ValueError(f"{event} has an invalid presentation interval")
        local: list[dict[str, Any]] = []
        for raw_cue in cues:
            cue_start = int(raw_cue["start_ms"])
            if not start_ms <= cue_start < end_ms:
                continue
            cue_end = int(raw_cue["end_ms"])
            if cue_end <= cue_start or cue_end > end_ms:
                raise ValueError(f"{event} subtitle crosses its presentation boundary")
            local.append(
                {
                    "start_ms": cue_start - start_ms,
                    "end_ms": cue_end - start_ms,
                    "text": str(raw_cue["text"]),
                }
            )
            assigned += 1
        by_event[event] = local
    if assigned != len(cues):
        raise ValueError("one or more source subtitle cues lack an event presentation")
    return by_event


def validate_excluded_route_declarations(
    rows: object,
) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("ac7210 production must declare exactly DirInfo rows 2-4 excluded")
    resolved: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in rows:
        if not isinstance(raw, Mapping) or set(raw) != {
            "dirinfo_row",
            "ordered_events",
            "excluded_component_events",
            "production_disposition",
        }:
            raise ValueError("invalid ac7210 excluded-route declaration")
        row_number = int(raw["dirinfo_row"])
        if row_number in seen or row_number not in EXCLUDED_ROUTES:
            raise ValueError("ac7210 excluded DirInfo rows must be unique rows 2-4")
        seen.add(row_number)
        ordered = [str(value) for value in raw["ordered_events"]]
        if ordered != EXCLUDED_ROUTES[row_number]:
            raise ValueError(f"ac7210 excluded DirInfo row {row_number} differs")
        expected_components = (
            ["ac7210_006"] if row_number in {2, 3} else ["ac7210_007", "ac7210_008"]
        )
        components = [str(value) for value in raw["excluded_component_events"]]
        if components != expected_components:
            raise ValueError(f"ac7210 row {row_number} component-event set differs")
        disposition = str(raw["production_disposition"])
        if (
            disposition
            != "excluded_until_layered_composition_and_parent_child_timing_are_closed"
        ):
            raise ValueError(f"ac7210 row {row_number} exclusion policy differs")
        resolved.append(
            {
                "dirinfo_row": row_number,
                "ordered_events": ordered,
                "excluded_component_events": components,
                "production_disposition": disposition,
            }
        )
    if seen != set(EXCLUDED_ROUTES):
        raise ValueError("ac7210 production omitted one excluded DirInfo row")
    return sorted(resolved, key=lambda row: row["dirinfo_row"])


def validate_production_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PRODUCTION_PLAN_SCHEMA
        or plan.get("status")
        != "owner_playback_approved_and_full_production_authorized"
        or plan.get("series") != "ac7210"
        or plan.get("audio_profile") != "no_bgm"
        or tuple(plan.get("editions", ())) != PRODUCTION_EDITIONS
    ):
        raise ValueError("unsupported ac7210 approved-route production plan")
    native = plan.get("native_media")
    if not isinstance(native, Mapping) or (
        int(native.get("width", 0)),
        int(native.get("height", 0)),
        str(native.get("frame_rate", "")),
        str(native.get("video_codec", "")),
        str(native.get("audio_codec", "")),
        int(native.get("audio_sample_rate", 0)),
        int(native.get("audio_channels", 0)),
    ) != (WIDTH, HEIGHT, "30/1", "h264", "aac", SAMPLE_RATE, 2):
        raise ValueError("ac7210 native production media contract differs")
    if (
        plan.get("approved_zh_policy")
        != "hardlink_exact_owner_approved_files_no_reencode"
        or plan.get("sibling_subtitle_policy")
        != "extract_v24_ja_zh_by_event_presentation_timeline"
        or plan.get("route_policy")
        != "rows_0_1_independent_never_concat_as_one_native_session"
    ):
        raise ValueError("ac7210 production policy differs")

    plan_dir = plan_path.parent
    snapshots: list[dict[str, str]] = [
        {
            "label": "ac7210 approved-route production plan",
            "path": str(plan_path.resolve()),
            "sha256": file_sha256(plan_path.resolve()),
        }
    ]
    review_plan_path, snapshot = validate_bound_file(
        plan["review_plan"],
        label="ac7210 v29 review plan",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    review_plan = read_json(review_plan_path)
    reviewed = validate_plan(
        review_plan,
        plan_path=review_plan_path,
        ffprobe=ffprobe,
    )
    if {row["dirinfo_row"] for row in reviewed["routes"]} != {0, 1}:
        raise ValueError("v29 review plan does not contain only rows 0 and 1")
    for route in reviewed["routes"]:
        if route["ordered_events"] != EXPECTED_ROUTES[int(route["dirinfo_row"])]:
            raise ValueError("v29 reviewed route identity differs")

    attestation_path, snapshot = validate_bound_file(
        plan["owner_attestation"],
        label="owner ac7210 playback and full-production authorization",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    attestation = read_json(attestation_path)
    authorization = attestation.get("production_authorization")
    if (
        attestation.get("schema")
        != "magireco-owner-playback-production-authorization-v1"
        or attestation.get("status")
        != "owner_playback_approved_and_full_production_authorized"
        or not isinstance(authorization, Mapping)
        or authorization.get("audio_profile") != "no_bgm"
        or tuple(authorization.get("editions", ())) != PRODUCTION_EDITIONS
        or not str(authorization.get("ac7210", "")).startswith(
            "Promote the approved DirInfo row 0 and row 1"
        )
    ):
        raise ValueError("owner ac7210 production authorization differs")
    attested_by_product = {
        str(row.get("product", "")): row
        for row in attestation.get("approved_review_media", [])
        if isinstance(row, Mapping) and row.get("family") == "ac7210"
    }
    if set(attested_by_product) != {
        "DirInfo kind 201 row 0",
        "DirInfo kind 201 row 1",
    }:
        raise ValueError("owner attestation lacks the exact two ac7210 ZH approvals")

    family_manifest_path, snapshot = validate_bound_file(
        plan["v24_family_manifest"],
        label="ac7210 v24 family presentation timeline",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    family_manifest = read_json(family_manifest_path)
    timeline = family_manifest.get("timeline")
    if (
        family_manifest.get("schema")
        != "magireco-no-bgm-story-family-editions-v1"
        or family_manifest.get("family") != "ac7210"
        or not isinstance(timeline, list)
        or [str(row.get("event", "")) for row in timeline]
        != ["ac7210_001", "ac7210_004", "ac7210_005"]
    ):
        raise ValueError("ac7210 v24 subtitle presentation timeline differs")

    subtitle_sources = plan.get("subtitle_sources")
    if not isinstance(subtitle_sources, Mapping) or set(subtitle_sources) != {
        "ja",
        "zh",
    }:
        raise ValueError("ac7210 production requires exact JA and ZH SRT sources")
    source_cues: dict[str, dict[str, list[dict[str, Any]]]] = {}
    subtitle_paths: dict[str, Path] = {}
    for language in ("ja", "zh"):
        srt_path, snapshot = validate_bound_file(
            subtitle_sources[language],
            label=f"ac7210 v24 {language.upper()} subtitle timeline",
            plan_dir=plan_dir,
        )
        snapshots.append(snapshot)
        subtitle_paths[language] = srt_path
        source_cues[language] = extract_event_local_cues(parse_srt(srt_path), timeline)
    if set(source_cues["ja"]) != set(source_cues["zh"]):
        raise ValueError("ac7210 JA/ZH source subtitle event sets differ")
    for event_name in source_cues["ja"]:
        ja_intervals = [
            (int(cue["start_ms"]), int(cue["end_ms"]))
            for cue in source_cues["ja"][event_name]
        ]
        zh_intervals = [
            (int(cue["start_ms"]), int(cue["end_ms"]))
            for cue in source_cues["zh"][event_name]
        ]
        if ja_intervals != zh_intervals:
            raise ValueError(f"{event_name} v24 JA/ZH subtitle timings differ")

    events = reviewed["events"]
    for event_name, event in events.items():
        if event_name in source_cues["zh"]:
            if event["local_zh_cues"] != source_cues["zh"][event_name]:
                raise ValueError(f"{event_name} reviewed ZH extraction differs")
            event["local_cues"] = {
                "ja": source_cues["ja"][event_name],
                "zh": source_cues["zh"][event_name],
            }
        else:
            event["local_cues"] = {"ja": [], "zh": []}

    raw_approved = plan.get("approved_zh")
    if not isinstance(raw_approved, list) or len(raw_approved) != 2:
        raise ValueError("ac7210 production requires exactly two approved ZH bindings")
    approved_by_row: dict[int, dict[str, Any]] = {}
    route_by_row = {int(row["dirinfo_row"]): row for row in reviewed["routes"]}
    for raw in raw_approved:
        if not isinstance(raw, Mapping) or set(raw) != {
            "dirinfo_row",
            "byte_count",
            "source",
        }:
            raise ValueError("invalid ac7210 approved ZH binding")
        row_number = int(raw["dirinfo_row"])
        if row_number in approved_by_row or row_number not in EXPECTED_ROUTES:
            raise ValueError("approved ac7210 ZH rows must be unique rows 0 and 1")
        source_path, snapshot = validate_bound_file(
            raw["source"],
            label=f"owner-approved ac7210 row {row_number} ZH",
            plan_dir=plan_dir,
        )
        snapshots.append(snapshot)
        expected_sha256 = APPROVED_ZH_SHA256[row_number]
        expected_name = f"{route_by_row[row_number]['title']}__zh.mp4"
        if (
            snapshot["sha256"] != expected_sha256
            or source_path.name != expected_name
            or source_path.stat().st_size != int(raw["byte_count"])
        ):
            raise ValueError(f"owner-approved ac7210 row {row_number} ZH differs")
        attested = attested_by_product[f"DirInfo kind 201 row {row_number}"]
        if (
            str(attested.get("filename", "")) != expected_name
            or int(attested.get("bytes", -1)) != source_path.stat().st_size
            or str(attested.get("sha256", "")).upper() != expected_sha256
        ):
            raise ValueError(f"attested ac7210 row {row_number} ZH differs")
        validate_output_media(
            source_path,
            expected_frames=int(route_by_row[row_number]["expected_frame_count"]),
            ffprobe=ffprobe,
        )
        approved_by_row[row_number] = {
            "path": source_path,
            "sha256": expected_sha256,
            "byte_count": source_path.stat().st_size,
        }
    if set(approved_by_row) != {0, 1}:
        raise ValueError("approved ac7210 ZH bindings omit one reviewed route")

    excluded_routes = validate_excluded_route_declarations(
        plan.get("excluded_dirinfo_rows")
    )
    source_snapshots = deduplicate_source_snapshots(
        [*reviewed["source_snapshots"], *snapshots]
    )
    return {
        **reviewed,
        "release_id": str(plan["release_id"]),
        "production_plan_path": plan_path.resolve(),
        "owner_attestation_path": attestation_path,
        "subtitle_paths": subtitle_paths,
        "approved_zh_by_row": approved_by_row,
        "excluded_routes": excluded_routes,
        "source_snapshots": source_snapshots,
    }


def hardlink_exact(source: Path, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"hard-link target already exists: {target}")
    os.link(source, target, follow_symlinks=False)
    if not os.path.samefile(source, target):
        raise RuntimeError("approved ZH target is not the exact source hard link")
    source_hash = file_sha256(source)
    target_hash = file_sha256(target)
    if source_hash != target_hash or source.stat().st_size != target.stat().st_size:
        raise RuntimeError("approved ZH hard link content differs")
    return {
        "source_path": str(source.resolve()),
        "output_path": str(target),
        "same_file_identity": True,
        "sha256": target_hash,
        "byte_count": target.stat().st_size,
        "link_count": target.stat().st_nlink,
    }


def audit_audio_master(
    path: Path,
    *,
    total_samples: int,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    value = probe(path, ffprobe)
    audios = media_streams(value, "audio")
    if (
        len(audios) != 1
        or media_streams(value, "video")
        or media_streams(value, "subtitle")
    ):
        raise RuntimeError(f"route AAC master stream contract failed: {path}")
    audio = audios[0]
    if (
        audio.get("codec_name") != "aac"
        or int(audio.get("sample_rate", 0)) != SAMPLE_RATE
        or int(audio.get("channels", 0)) != 2
    ):
        raise RuntimeError(f"route AAC master encoding contract failed: {path}")
    timeline = audio_gate._audio_packet_timeline(
        output=path,
        audio_stream=audio,
        expected_samples=total_samples,
        ffprobe=ffprobe,
    )
    decoded_pcm = audio_gate._effective_decoded_pcm_audit(
        output=path,
        expected_samples=total_samples,
        ffmpeg=ffmpeg,
    )
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "byte_count": path.stat().st_size,
        "audio_bit_rate": stream_bit_rate(audio, label=f"{path.name} audio"),
        "audio_packet_sha256": packet_hash(path, kind="audio", ffmpeg=ffmpeg),
        "audio_timeline": timeline,
        "decoded_pcm": decoded_pcm,
    }


def compact_audio_timeline(timeline: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the exact timeline identity without repeating every AAC packet/frame."""

    keys = (
        "schema",
        "time_base",
        "expected_presentation_samples",
        "packet_count",
        "first_packet_pts",
        "encoder_priming_samples",
        "packet_raw_end_sample",
        "packet_presentation_end_sample",
        "decoded_frame_count",
        "raw_decoded_sample_count_per_channel",
        "raw_decoder_padding_samples",
        "timeline_sha256",
    )
    return {key: timeline[key] for key in keys}


def audit_route_edition(
    path: Path,
    *,
    expected_frames: int,
    total_samples: int,
    master_audit: Mapping[str, Any],
    staging: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    media = validate_output_media(
        path,
        expected_frames=expected_frames,
        ffprobe=ffprobe,
    )
    value = probe(path, ffprobe)
    video = media_streams(value, "video")[0]
    audio = media_streams(value, "audio")[0]
    timeline = audio_gate._audio_packet_timeline(
        output=path,
        audio_stream=audio,
        expected_samples=total_samples,
        ffprobe=ffprobe,
    )
    decoded_pcm = audio_gate._effective_decoded_pcm_audit(
        output=path,
        expected_samples=total_samples,
        ffmpeg=ffmpeg,
    )
    audio_packets = packet_hash(path, kind="audio", ffmpeg=ffmpeg)
    if (
        timeline != master_audit["audio_timeline"]
        or decoded_pcm != master_audit["decoded_pcm"]
        or audio_packets != master_audit["audio_packet_sha256"]
    ):
        raise RuntimeError(f"edition AAC/decoded PCM differs from route master: {path}")
    media["path"] = relative_output_path(path, staging=staging)
    media["video"]["bit_rate"] = stream_bit_rate(video, label=f"{path.name} video")
    media["audio"]["bit_rate"] = stream_bit_rate(audio, label=f"{path.name} audio")
    media["audio_packet_sha256"] = audio_packets
    media["audio_timeline"] = compact_audio_timeline(timeline)
    media["decoded_pcm"] = decoded_pcm
    return media


def build_production_route(
    *,
    route: Mapping[str, Any],
    events: Mapping[str, Mapping[str, Any]],
    event_pcm: Mapping[str, Path],
    clean_visuals: Mapping[str, Path],
    approved_zh: Mapping[str, Any],
    layout: Mapping[str, Any],
    staged_font_dir: Path,
    staging: Path,
    work: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    route_id = str(route["route_id"])
    total_frames = 0
    total_samples = 0
    timeline: list[dict[str, Any]] = []
    route_cues: dict[str, list[dict[str, Any]]] = {"ja": [], "zh": []}
    route_pcm = work / f"{route_id}.scene.f32le"
    with route_pcm.open("wb") as target:
        for event_name in route["ordered_events"]:
            event = events[event_name]
            start_frame = total_frames
            start_sample = total_samples
            copy_pcm(event_pcm[event_name], target)
            offset_ms = milliseconds_for_samples(start_sample)
            for language in ("ja", "zh"):
                for cue in event["local_cues"][language]:
                    route_cues[language].append(
                        {
                            "start_ms": offset_ms + int(cue["start_ms"]),
                            "end_ms": offset_ms + int(cue["end_ms"]),
                            "text": str(cue["text"]),
                        }
                    )
            total_frames += int(event["frame_count"])
            total_samples += int(event["presentation_samples"])
            timeline.append(
                {
                    "event": event_name,
                    "start_frame": start_frame,
                    "end_frame": total_frames,
                    "start_sample": start_sample,
                    "end_sample": total_samples,
                    "evidence_class": event["evidence_class"],
                }
            )
    if (
        total_frames != int(route["expected_frame_count"])
        or total_samples != total_frames * SAMPLES_PER_FRAME
        or route_pcm.stat().st_size != total_samples * 8
    ):
        raise RuntimeError(f"{route_id} frame/sample presentation grid differs")

    subtitle_dir = staging / "subtitles"
    subtitle_dir.mkdir(exist_ok=True)
    subtitle_paths: dict[str, Path] = {}
    subtitle_audits: dict[str, dict[str, Any]] = {}
    for language in ("ja", "zh"):
        path = subtitle_dir / f"{route_id}__{language}.srt"
        assert_srt_round_trip(path, route_cues[language])
        subtitle_paths[language] = path
        subtitle_audits[language] = {
            "path": relative_output_path(path, staging=staging),
            "sha256": file_sha256(path),
            "cue_count": len(route_cues[language]),
            "round_trip_exact": True,
        }
    if [
        (cue["start_ms"], cue["end_ms"]) for cue in route_cues["ja"]
    ] != [
        (cue["start_ms"], cue["end_ms"]) for cue in route_cues["zh"]
    ]:
        raise RuntimeError(f"{route_id} JA/ZH route cue timings differ")

    masters_dir = staging / "masters"
    masters_dir.mkdir(exist_ok=True)
    audio_master = masters_dir / f"{route_id}__no_bgm_audio_master.m4a"
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
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-i",
            str(route_pcm),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(audio_master),
        ]
    )
    master_audit = audit_audio_master(
        audio_master,
        total_samples=total_samples,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    master_audit["path"] = relative_output_path(audio_master, staging=staging)

    clean_master = work / f"{route_id}__clean_visual_master.mp4"
    visual_command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    filters: list[str] = []
    labels: list[str] = []
    for index, event_name in enumerate(route["ordered_events"]):
        visual_command.extend(["-i", str(clean_visuals[event_name])])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={events[event_name]['frame_count']},"
            f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]"
    )
    visual_command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(total_frames),
            "-movflags",
            "+faststart",
            str(clean_master),
        ]
    )
    run(visual_command)
    validate_video_grid(
        clean_master,
        expected_frames=total_frames,
        ffprobe=ffprobe,
        label=f"{route_id} clean visual master",
    )

    video_dir = staging / "video"
    video_dir.mkdir(exist_ok=True)
    outputs = {
        edition: video_dir / f"{route['title']}__{edition}.mp4"
        for edition in PRODUCTION_EDITIONS
    }
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(clean_master),
            "-i",
            str(audio_master),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(outputs["none"]),
        ]
    )
    ja_filter = subtitle_filter(
        layout,
        srt_path=subtitle_paths["ja"].relative_to(staging).as_posix(),
        fonts_dir=staged_font_dir.relative_to(staging).as_posix(),
    )
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            clean_master.relative_to(staging).as_posix(),
            "-i",
            audio_master.relative_to(staging).as_posix(),
            "-vf",
            ja_filter,
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
            "-c:a",
            "copy",
            "-frames:v",
            str(total_frames),
            "-movflags",
            "+faststart",
            outputs["ja"].relative_to(staging).as_posix(),
        ],
        cwd=staging,
    )
    hardlink_audit = hardlink_exact(Path(approved_zh["path"]), outputs["zh"])
    if (
        hardlink_audit["sha256"] != approved_zh["sha256"]
        or hardlink_audit["byte_count"] != approved_zh["byte_count"]
    ):
        raise RuntimeError(f"{route_id} approved ZH hard link differs")
    hardlink_audit["output_path"] = relative_output_path(
        outputs["zh"], staging=staging
    )

    edition_audits = {
        edition: audit_route_edition(
            output,
            expected_frames=total_frames,
            total_samples=total_samples,
            master_audit=master_audit,
            staging=staging,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )
        for edition, output in outputs.items()
    }
    if {row["audio_packet_sha256"] for row in edition_audits.values()} != {
        master_audit["audio_packet_sha256"]
    }:
        raise RuntimeError(f"{route_id} editions do not share one AAC packet identity")
    public_master_audit = {
        **master_audit,
        "audio_timeline": compact_audio_timeline(master_audit["audio_timeline"]),
    }
    return {
        "route_id": route_id,
        "dirinfo_row": int(route["dirinfo_row"]),
        "title": str(route["title"]),
        "ordered_events": list(route["ordered_events"]),
        "timeline": timeline,
        "total_frames": total_frames,
        "total_presentation_samples": total_samples,
        "subtitle_audits": subtitle_audits,
        "audio_master": public_master_audit,
        "editions": edition_audits,
        "owner_approved_zh_hardlink": hardlink_audit,
        "human_playback_approved_editions": ["zh"],
        "production_authorized_editions": list(PRODUCTION_EDITIONS),
    }


def build_approved_editions(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> Path:
    plan = read_json(plan_path)
    resolved = validate_production_plan(
        plan,
        plan_path=plan_path,
        ffprobe=ffprobe,
    )
    destination = output_root.resolve()
    if destination.exists():
        raise FileExistsError(f"versioned ac7210 production root exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        work = staging / "work"
        work.mkdir()
        staged_font_dir = work / "fonts"
        staged_font_dir.mkdir()
        shutil.copy2(
            resolved["font_path"], staged_font_dir / resolved["font_path"].name
        )
        clean_visuals = {
            event_name: Path(str(event["clean_visual"]))
            for event_name, event in resolved["events"].items()
            if event.get("clean_visual")
        }
        manual_visual_audits: dict[str, dict[str, Any]] = {}
        for event_name, spec in resolved["manual_specs"].items():
            output = work / f"{event_name}__clean_visual.mp4"
            manual_visual_audits[event_name] = build_manual_visual(
                event=spec,
                output=output,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            clean_visuals[event_name] = output

        event_pcm: dict[str, Path] = {}
        event_pcm_audits: dict[str, dict[str, Any]] = {}
        for event_name, event in resolved["events"].items():
            output = work / f"{event_name}.f32le"
            event_pcm_audits[event_name] = build_event_pcm(
                event,
                output=output,
                ffmpeg=ffmpeg,
            )
            event_pcm[event_name] = output

        route_results = [
            build_production_route(
                route=route,
                events=resolved["events"],
                event_pcm=event_pcm,
                clean_visuals=clean_visuals,
                approved_zh=resolved["approved_zh_by_row"][
                    int(route["dirinfo_row"])
                ],
                layout=resolved["layout"],
                staged_font_dir=staged_font_dir,
                staging=staging,
                work=work,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            for route in sorted(
                resolved["routes"],
                key=lambda row: int(row["dirinfo_row"]),
            )
        ]
        if [
            (row["dirinfo_row"], row["ordered_events"]) for row in route_results
        ] != [
            (row_number, EXPECTED_ROUTES[row_number]) for row_number in (0, 1)
        ]:
            raise RuntimeError("ac7210 output routes are not the exact independent rows 0/1")

        shutil.rmtree(work)
        expected_output_paths = {
            str(row["editions"][edition]["path"])
            for row in route_results
            for edition in PRODUCTION_EDITIONS
        }
        if (
            len(expected_output_paths) != 6
            or any(Path(value).is_absolute() or ".." in Path(value).parts for value in expected_output_paths)
        ):
            raise RuntimeError("ac7210 output paths are not six stable relative MP4 paths")
        actual_mp4_paths = {
            relative_output_path(path, staging=staging)
            for path in staging.rglob("*.mp4")
        }
        if actual_mp4_paths != expected_output_paths:
            raise RuntimeError("ac7210 versioned root does not contain exactly six MP4 files")

        assert_source_snapshots_unchanged(resolved["source_snapshots"])
        manifest = {
            "schema": PRODUCTION_MANIFEST_SCHEMA,
            "status": PRODUCTION_STATUS,
            "release_id": resolved["release_id"],
            "family": "ac7210",
            "audio_profile": "no_bgm",
            "editions": list(PRODUCTION_EDITIONS),
            "product_scope": "two independent owner-approved DirInfo route products",
            "presentation_boundary_policy": (
                "owner_approved_editorial_hold_for_ac7210_002_003_not_new_runtime_proof"
            ),
            "route_policy": (
                "rows_0_1_independent_never_concat_as_one_native_session"
            ),
            "approved_zh_policy": "exact_hardlink_no_reencode",
            "human_playback_approved_editions": ["zh"],
            "sibling_editions_human_playback_approved": False,
            "publication_approved": False,
            "routes": route_results,
            "excluded_dirinfo_rows": resolved["excluded_routes"],
            "manual_visual_audits": manual_visual_audits,
            "event_pcm_audits": event_pcm_audits,
            "source_snapshots": resolved["source_snapshots"],
        }
        manifest_dir = staging / "manifest"
        manifest_dir.mkdir()
        manifest_path = manifest_dir / "PRODUCTION_MANIFEST.json"
        write_json(manifest_path, manifest)

        qa = {
            "schema": PRODUCTION_QA_SCHEMA,
            "status": "passed",
            "family": "ac7210",
            "selected_editions": list(PRODUCTION_EDITIONS),
            "exact_mp4_count": 6,
            "new_rendered_mp4_count": 4,
            "exact_approved_zh_hardlink_count": 2,
            "checks": {
                "owner_attestation_exact_hash_bound": True,
                "source_hashes_unchanged": True,
                "two_routes_independent": True,
                "dirinfo_rows_0_1_order_exact": True,
                "dirinfo_rows_2_3_4_fail_closed_excluded": True,
                "native_416x232_30fps_no_upscale": True,
                "h264_aac_48khz_stereo": True,
                "positive_auditable_native_bit_rates": True,
                "exact_frame_and_sample_grid": True,
                "aac_packet_identity_matches_route_master": True,
                "effective_decoded_pcm_matches_route_master": True,
                "ja_zh_extracted_from_v24_event_presentation_timeline": True,
                "selected_srt_files_round_trip": True,
                "none_uses_clean_visual_without_subtitles": True,
                "approved_zh_exact_hash_preserved_without_reencode": True,
                "all_artifact_paths_relative_to_versioned_root": True,
                "exactly_six_output_mp4_files": True,
                "bgm_intentionally_excluded": True,
            },
            "route_media_audits": [
                {
                    "route_id": row["route_id"],
                    "dirinfo_row": row["dirinfo_row"],
                    "audio_master": row["audio_master"],
                    "editions": row["editions"],
                    "subtitle_audits": row["subtitle_audits"],
                    "approved_zh_hardlink": row["owner_approved_zh_hardlink"],
                }
                for row in route_results
            ],
            "warnings": [
                "Only the exact ZH hashes were owner-playback-approved; none and JA are authorized sibling production outputs but are not marked human-playback-approved.",
                "The approved ac7210_002/_003 editorial hold is not represented as new runtime parent-child timing proof.",
                "DirInfo rows 2-4 remain excluded pending formal component composition and parent-child timing closure.",
                "BGM is intentionally excluded; verified dialogue and scene SE remain.",
                "Bilibili upload is not performed by this builder.",
            ],
        }
        qa_dir = staging / "qa"
        qa_dir.mkdir()
        qa_path = qa_dir / "AUTOMATED_QA.json"
        write_json(qa_path, qa)
        playback_status = {
            "schema": "magireco-owner-playback-status-v1",
            "status": "mixed_exact_zh_approved_sibling_editions_not_playback_approved",
            "production_authorized": True,
            "publication_approved": False,
            "routes": [
                {
                    "dirinfo_row": row["dirinfo_row"],
                    "zh": {
                        "path": row["editions"]["zh"]["path"],
                        "sha256": row["editions"]["zh"]["sha256"],
                        "human_playback_approved": True,
                    },
                    "none": {
                        "path": row["editions"]["none"]["path"],
                        "sha256": row["editions"]["none"]["sha256"],
                        "human_playback_approved": False,
                    },
                    "ja": {
                        "path": row["editions"]["ja"]["path"],
                        "sha256": row["editions"]["ja"]["sha256"],
                        "human_playback_approved": False,
                    },
                }
                for row in route_results
            ],
        }
        playback_path = qa_dir / "HUMAN_PLAYBACK_STATUS.json"
        write_json(playback_path, playback_status)
        hash_manifest = {
            "schema": "magireco-versioned-production-sha256-v1",
            "status": "passed",
            "files": [
                {
                    "path": row["editions"][edition]["path"],
                    "sha256": row["editions"][edition]["sha256"],
                    "byte_count": row["editions"][edition]["byte_count"],
                    "dirinfo_row": row["dirinfo_row"],
                    "edition": edition,
                }
                for row in route_results
                for edition in PRODUCTION_EDITIONS
            ],
            "production_manifest_sha256": file_sha256(manifest_path),
            "automated_qa_sha256": file_sha256(qa_path),
            "human_playback_status_sha256": file_sha256(playback_path),
        }
        write_json(staging / "MANIFEST_SHA256.json", hash_manifest)

        staging.replace(destination)
        for row in route_results:
            source = Path(
                resolved["approved_zh_by_row"][int(row["dirinfo_row"])]["path"]
            )
            target = destination / row["editions"]["zh"]["path"]
            if not os.path.samefile(source, target):
                raise RuntimeError("approved ZH hard link identity changed after promotion")
        return destination
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plan_path = Path(args.plan).resolve()
    plan = read_json(plan_path)
    if plan.get("schema") == PRODUCTION_PLAN_SCHEMA:
        resolved = validate_production_plan(
            plan,
            plan_path=plan_path,
            ffprobe=args.ffprobe,
        )
        if args.validate_only:
            print(
                json.dumps(
                    {
                        "schema": PRODUCTION_PLAN_SCHEMA,
                        "status": "validated",
                        "routes": len(resolved["routes"]),
                        "editions": list(PRODUCTION_EDITIONS),
                        "source_snapshots": len(resolved["source_snapshots"]),
                        "excluded_dirinfo_rows": [
                            row["dirinfo_row"]
                            for row in resolved["excluded_routes"]
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        destination = build_approved_editions(
            plan_path=plan_path,
            output_root=Path(args.out_root),
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
        )
        print(
            json.dumps(
                {
                    "schema": PRODUCTION_MANIFEST_SCHEMA,
                    "status": PRODUCTION_STATUS,
                    "destination": str(destination),
                    "mp4_count": 6,
                    "new_rendered_mp4_count": 4,
                    "approved_zh_hardlink_count": 2,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    resolved = validate_plan(plan, plan_path=plan_path, ffprobe=args.ffprobe)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "schema": PLAN_SCHEMA,
                    "status": "validated",
                    "routes": len(resolved["routes"]),
                    "source_snapshots": len(resolved["source_snapshots"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    destination = build(
        plan_path=plan_path,
        output_root=Path(args.out_root),
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "status": STATUS,
                "destination": str(destination),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
