#!/usr/bin/env python3
"""Build two finite P25/ac7210 Chinese route-completion review candidates.

DirInfo proves two mutually exclusive clean-story routes:

* row 0: ac7210_001 -> _002 -> _003 -> _004
* row 1: ac7210_001 -> _005 -> _003 -> _004

The existing uploaded P25 is preserved and never overwritten.  Static evidence
does not prove whether the long parent scene sounds for _002 and _003 overlap
the next event.  These candidates therefore hold the final visual frame through
the verified sound tail and remain explicitly presentation-boundary-risk.
"""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
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
        parse_srt,
        run,
        subtitle_filter,
        write_json,
    )
    from .build_sp_story_chapter_reviews import FORBIDDEN_AUDIO_REQUESTS
except ImportError:  # direct script execution
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
        parse_srt,
        run,
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
    resolved = validate_plan(
        read_json(plan_path), plan_path=plan_path, ffprobe=args.ffprobe
    )
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
