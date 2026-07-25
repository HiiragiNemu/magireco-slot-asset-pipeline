#!/usr/bin/env python3
"""Build the finite, reference-ordered ac0908 Chinese review showcase.

This builder is deliberately narrow.  It does not claim that the edited
showcase is one native game session.  It combines:

* the locally verified weak-entry visuals for ``ac0908_001``;
* exact no-BGM event assets already used by the six owner-playback-approved
  Chinese route segments;
* the external reference only as an ordering and entry-presentation oracle.

No pixels or audio are copied from the external reference.  Every production
input is hash-bound, the output remains native 416x232 at 30 fps, and the
result remains human-review-required.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_independent_scene_release import (
        build_event_pcm,
        file_sha256,
        frame_count,
        media_streams,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        write_json,
        write_srt,
    )
    from .build_sp_story_chapter_reviews import FORBIDDEN_AUDIO_REQUESTS
except ImportError:  # direct script execution
    from build_independent_scene_release import (  # type: ignore
        build_event_pcm,
        file_sha256,
        frame_count,
        media_streams,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        write_json,
        write_srt,
    )
    from build_sp_story_chapter_reviews import (  # type: ignore
        FORBIDDEN_AUDIO_REQUESTS,
    )


PLAN_SCHEMA = "magireco-ac0908-reference-showcase-plan-v1"
MANIFEST_SCHEMA = "magireco-ac0908-reference-showcase-manifest-v1"
QA_SCHEMA = "magireco-ac0908-reference-showcase-qa-v1"
STATUS = "REFERENCE_DERIVED_ALL_OUTCOMES_SHOWCASE_HUMAN_REVIEW_REQUIRED"
WIDTH = 416
HEIGHT = 232
FPS = 30
SAMPLES_PER_FRAME = 1600
SAMPLE_RATE = 48000


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _valid_sha256(value: object) -> str:
    text = str(value).strip().upper()
    if len(text) != 64 or any(character not in "0123456789ABCDEF" for character in text):
        raise ValueError(f"invalid SHA-256: {value!r}")
    return text


def validate_bound_file(
    row: Mapping[str, Any],
    *,
    label: str,
    plan_dir: Path,
) -> tuple[Path, dict[str, str]]:
    if set(row) != {"path", "sha256"}:
        raise ValueError(f"{label} must contain only path and sha256")
    path = Path(str(row["path"]))
    if not path.is_absolute():
        path = plan_dir / path
    path = path.resolve()
    expected = _valid_sha256(row["sha256"])
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(
            f"{label} SHA-256 differs: expected {expected}, got {actual}: {path}"
        )
    return path, {"label": label, "path": str(path), "sha256": actual}


def normalized_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def relative_output_path(path: Path, *, staging: Path) -> str:
    try:
        return path.resolve().relative_to(staging.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"output is outside the versioned staging root: {path}") from exc


def milliseconds_for_samples(samples: int) -> int:
    return round(Fraction(samples * 1000, SAMPLE_RATE))


def validate_video_grid(
    path: Path,
    *,
    expected_frames: int,
    ffprobe: str,
    label: str,
) -> dict[str, Any]:
    value = probe(path, ffprobe)
    videos = media_streams(value, "video")
    if (
        len(videos) != 1
        or media_streams(value, "audio")
        or media_streams(value, "subtitle")
    ):
        raise RuntimeError(f"{label} stream contract failed: {path}")
    video = videos[0]
    actual_frames = frame_count(video)
    if (
        video.get("codec_name") != "h264"
        or int(video.get("width", 0)) != WIDTH
        or int(video.get("height", 0)) != HEIGHT
        or video.get("r_frame_rate") != "30/1"
        or actual_frames != expected_frames
    ):
        raise RuntimeError(
            f"{label} native grid differs: frames={actual_frames}, stream={video}"
        )
    return {
        "codec": "h264",
        "width": WIDTH,
        "height": HEIGHT,
        "frame_rate": "30/1",
        "frame_count": actual_frames,
        "sha256": file_sha256(path),
    }


def validate_output_media(
    path: Path,
    *,
    expected_frames: int,
    ffprobe: str,
) -> dict[str, Any]:
    value = probe(path, ffprobe)
    videos = media_streams(value, "video")
    audios = media_streams(value, "audio")
    if len(videos) != 1 or len(audios) != 1 or media_streams(value, "subtitle"):
        raise RuntimeError("showcase output stream contract failed")
    video = videos[0]
    audio = audios[0]
    if (
        video.get("codec_name") != "h264"
        or int(video.get("width", 0)) != WIDTH
        or int(video.get("height", 0)) != HEIGHT
        or video.get("r_frame_rate") != "30/1"
        or frame_count(video) != expected_frames
        or audio.get("codec_name") != "aac"
        or int(audio.get("sample_rate", 0)) != SAMPLE_RATE
        or int(audio.get("channels", 0)) != 2
    ):
        raise RuntimeError("showcase output native AV contract failed")
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "byte_count": path.stat().st_size,
        "video": {
            "codec": "h264",
            "width": WIDTH,
            "height": HEIGHT,
            "frame_rate": "30/1",
            "frame_count": expected_frames,
        },
        "audio": {
            "codec": "aac",
            "sample_rate": SAMPLE_RATE,
            "channels": 2,
        },
    }


def build_entry_visual(
    *,
    output: Path,
    exterior: Path,
    side: Path,
    include_exterior: bool,
    frame_count_value: int,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    if frame_count_value <= 0:
        raise ValueError("entry occurrence must contain at least one frame")
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if include_exterior:
        exterior_probe = probe(exterior, ffprobe)
        exterior_streams = media_streams(exterior_probe, "video")
        if len(exterior_streams) != 1:
            raise RuntimeError("ac0908_001 exterior source stream contract failed")
        exterior_frames = frame_count(exterior_streams[0])
        if exterior_frames >= frame_count_value:
            raise ValueError("entry occurrence does not leave room for side cooking")
        side_frames = frame_count_value - exterior_frames
        command.extend(
            [
                "-i",
                str(exterior),
                "-stream_loop",
                "-1",
                "-i",
                str(side),
                "-filter_complex",
                (
                    f"[0:v:0]trim=end_frame={exterior_frames},"
                    f"setpts=N/({FPS}*TB)[outside];"
                    f"[1:v:0]trim=end_frame={side_frames},"
                    f"setpts=N/({FPS}*TB)[side];"
                    "[outside][side]concat=n=2:v=1:a=0,"
                    "format=yuv420p[out]"
                ),
            ]
        )
    else:
        command.extend(
            [
                "-stream_loop",
                "-1",
                "-i",
                str(side),
                "-filter_complex",
                (
                    f"[0:v:0]trim=end_frame={frame_count_value},"
                    f"setpts=N/({FPS}*TB),format=yuv420p[out]"
                ),
            ]
        )
    command.extend(
        [
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
            str(frame_count_value),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run(command)
    return validate_video_grid(
        output,
        expected_frames=frame_count_value,
        ffprobe=ffprobe,
        label="ac0908_001 entry occurrence",
    )


def validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffprobe: str,
) -> dict[str, Any]:
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("unsupported ac0908 showcase plan schema")
    if plan.get("status") != "finite_human_review_candidate":
        raise ValueError("ac0908 showcase plan is not a finite review candidate")
    if plan.get("series") != "ac0908":
        raise ValueError("showcase plan series differs")
    native = plan.get("native_media")
    if not isinstance(native, Mapping) or (
        int(native.get("width", 0)),
        int(native.get("height", 0)),
        str(native.get("frame_rate", "")),
    ) != (WIDTH, HEIGHT, "30/1"):
        raise ValueError("showcase plan native media contract differs")
    if (
        plan.get("external_reference_policy")
        != "ordering_and_entry_presentation_only_no_reference_pixels_or_audio"
    ):
        raise ValueError("external reference policy is not fail-closed")
    if plan.get("session_claim") != "edited_cross_route_showcase_not_one_native_session":
        raise ValueError("showcase must not claim one native game session")

    plan_dir = plan_path.parent
    source_snapshots: list[dict[str, str]] = []
    reference_path, reference_snapshot = validate_bound_file(
        plan["reference"], label="external ordering reference", plan_dir=plan_dir
    )
    source_snapshots.append(reference_snapshot)
    dirinfo_path, dirinfo_snapshot = validate_bound_file(
        plan["dirinfo"], label="DirInfo route evidence", plan_dir=plan_dir
    )
    source_snapshots.append(dirinfo_snapshot)
    layout_path, layout_snapshot = validate_bound_file(
        plan["subtitle_layout"], label="416x232 subtitle layout", plan_dir=plan_dir
    )
    source_snapshots.append(layout_snapshot)
    font_path, font_snapshot = validate_bound_file(
        plan["font"], label="audited subtitle font", plan_dir=plan_dir
    )
    source_snapshots.append(font_snapshot)

    entry = plan.get("entry_sources")
    if not isinstance(entry, Mapping):
        raise ValueError("showcase plan lacks entry_sources")
    exterior_path, exterior_snapshot = validate_bound_file(
        entry["exterior_visual"],
        label="ac0908_001 exterior visual",
        plan_dir=plan_dir,
    )
    side_path, side_snapshot = validate_bound_file(
        entry["side_cooking_visual"],
        label="ac0908_001 side-cooking visual",
        plan_dir=plan_dir,
    )
    audio_path, audio_snapshot = validate_bound_file(
        entry["scene_audio"],
        label="ac0908_001 verified scene audio",
        plan_dir=plan_dir,
    )
    source_snapshots.extend([exterior_snapshot, side_snapshot, audio_snapshot])
    for path, frames, label in (
        (exterior_path, 22, "ac0908_001 exterior source"),
        (side_path, 65, "ac0908_001 side-cooking source"),
    ):
        validate_video_grid(path, expected_frames=frames, ffprobe=ffprobe, label=label)

    approved = plan.get("owner_playback_approved_zh_routes")
    if not isinstance(approved, list) or len(approved) != 6:
        raise ValueError("exactly six approved Chinese route files are required")
    approved_rows: set[int] = set()
    for row in approved:
        if not isinstance(row, Mapping) or set(row) != {
            "dirinfo_row",
            "path",
            "sha256",
        }:
            raise ValueError("invalid approved Chinese route binding")
        route_row = int(row["dirinfo_row"])
        if route_row in approved_rows or route_row not in range(52, 58):
            raise ValueError("approved Chinese route rows must be exactly 52 through 57")
        approved_rows.add(route_row)
        _, snapshot = validate_bound_file(
            {"path": row["path"], "sha256": row["sha256"]},
            label=f"owner-playback-approved ZH route {route_row}",
            plan_dir=plan_dir,
        )
        source_snapshots.append(snapshot)
    if approved_rows != set(range(52, 58)):
        raise ValueError("approved Chinese route row set differs")

    raw_events = plan.get("events")
    if not isinstance(raw_events, Mapping):
        raise ValueError("showcase plan lacks events")
    required_events = {f"ac0908_{suffix:03d}" for suffix in range(2, 10)}
    if set(raw_events) != required_events:
        raise ValueError("showcase plan event set must be ac0908_002 through _009")

    events: dict[str, dict[str, Any]] = {}
    for event_name in sorted(required_events):
        row = raw_events[event_name]
        if not isinstance(row, Mapping):
            raise ValueError(f"{event_name} event binding is invalid")
        route_row = int(row.get("route_row", -1))
        if route_row not in range(52, 58):
            raise ValueError(f"{event_name} route row is invalid")
        family_manifest_path, family_snapshot = validate_bound_file(
            row["family_manifest"],
            label=f"{event_name} v27 family manifest",
            plan_dir=plan_dir,
        )
        prepared_path, prepared_snapshot = validate_bound_file(
            row["prepared_manifest"],
            label=f"{event_name} prepared production manifest",
            plan_dir=plan_dir,
        )
        clean_path, clean_snapshot = validate_bound_file(
            row["clean_visual"],
            label=f"{event_name} clean visual",
            plan_dir=plan_dir,
        )
        srt_path, srt_snapshot = validate_bound_file(
            row["zh_srt"],
            label=f"{event_name} approved-timing Chinese SRT",
            plan_dir=plan_dir,
        )
        source_snapshots.extend(
            [family_snapshot, prepared_snapshot, clean_snapshot, srt_snapshot]
        )

        family_manifest = read_json(family_manifest_path)
        if (
            family_manifest.get("schema")
            != "magireco-no-bgm-story-family-editions-v1"
            or family_manifest.get("family") != "ac0908"
            or "zh" not in family_manifest.get("selected_editions", [])
        ):
            raise ValueError(f"{event_name} v27 family manifest identity differs")
        source_by_path = {
            normalized_path(Path(str(snapshot["path"]))): _valid_sha256(snapshot["sha256"])
            for snapshot in family_manifest.get("source_snapshots", [])
            if isinstance(snapshot, Mapping)
            and str(snapshot.get("path", "")).strip()
            and str(snapshot.get("sha256", "")).strip()
        }

        prepared = read_json(prepared_path)
        frame_count_value = int(row.get("frame_count", -1))
        if (
            prepared.get("schema") != "magireco-event-production-v3"
            or prepared.get("event") != event_name
            or int(prepared.get("render_frame_count", -1)) != frame_count_value
            or prepared.get("native_dimensions") != {"width": WIDTH, "height": HEIGHT}
            or prepared.get("native_frame_rate") != "30/1"
        ):
            raise ValueError(f"{event_name} prepared manifest identity differs")
        if any(
            str(audio.get("request_id", "")) in FORBIDDEN_AUDIO_REQUESTS
            for audio in prepared.get("audio", [])
            if isinstance(audio, Mapping)
        ):
            raise ValueError(f"{event_name} contains a forbidden BGM/effect request")
        audio_layers: list[dict[str, Any]] = []
        audio_snapshots: list[dict[str, str]] = []
        for audio in prepared.get("audio", []):
            if not isinstance(audio, Mapping) or audio.get("source") not in {
                "event_audio_component",
                "z2d_req_sound",
            }:
                raise ValueError(f"{event_name} contains unresolved audio semantics")
            audio_source = Path(str(audio["path"])).resolve()
            expected = source_by_path.get(normalized_path(audio_source))
            if expected is None or not audio_source.is_file():
                raise ValueError(f"{event_name} audio lacks a v27 hash binding")
            actual = file_sha256(audio_source)
            if actual != expected:
                raise ValueError(f"{event_name} audio source SHA-256 differs")
            audio_layers.append(
                {
                    "path": audio_source,
                    "start_ms": int(audio["start_ms"]),
                    "request_id": str(audio["request_id"]),
                    "role": (
                        "voice"
                        if audio.get("source") == "z2d_req_sound"
                        else "scene_se"
                    ),
                }
            )
            audio_snapshots.append(
                {
                    "label": f"{event_name} audio request {audio['request_id']}",
                    "path": str(audio_source),
                    "sha256": actual,
                }
            )
        source_snapshots.extend(audio_snapshots)

        clean_grid = validate_video_grid(
            clean_path,
            expected_frames=frame_count_value,
            ffprobe=ffprobe,
            label=f"{event_name} clean visual",
        )
        timeline_rows = [
            timeline
            for timeline in family_manifest.get("timeline", [])
            if isinstance(timeline, Mapping) and timeline.get("event") == event_name
        ]
        if len(timeline_rows) != 1:
            raise ValueError(f"{event_name} lacks one v27 route timeline row")
        timeline = timeline_rows[0]
        if int(timeline["end_frame"]) - int(timeline["start_frame"]) != frame_count_value:
            raise ValueError(f"{event_name} v27 route frame interval differs")
        event_offset_ms = milliseconds_for_samples(int(timeline["start_sample"]))
        event_end_ms = milliseconds_for_samples(int(timeline["end_sample"]))
        local_cues = []
        for cue in parse_srt(srt_path):
            if event_offset_ms <= int(cue["start_ms"]) < event_end_ms:
                if int(cue["end_ms"]) > event_end_ms:
                    raise ValueError(f"{event_name} subtitle crosses its event boundary")
                local_cues.append(
                    {
                        "start_ms": int(cue["start_ms"]) - event_offset_ms,
                        "end_ms": int(cue["end_ms"]) - event_offset_ms,
                        "text": str(cue["text"]),
                    }
                )
        if len(local_cues) != int(row.get("expected_zh_cue_count", -1)):
            raise ValueError(f"{event_name} Chinese cue count differs")
        events[event_name] = {
            "event": event_name,
            "frame_count": frame_count_value,
            "presentation_samples": frame_count_value * SAMPLES_PER_FRAME,
            "clean_visual": clean_path,
            "clean_grid": clean_grid,
            "audio_layers": audio_layers,
            "local_zh_cues": local_cues,
            "route_row": route_row,
        }

    occurrences = plan.get("occurrences")
    if not isinstance(occurrences, list) or not occurrences:
        raise ValueError("showcase plan lacks occurrences")
    occurrence_ids: set[str] = set()
    resolved_occurrences: list[dict[str, Any]] = []
    for index, raw in enumerate(occurrences):
        if not isinstance(raw, Mapping):
            raise ValueError("invalid showcase occurrence")
        occurrence_id = str(raw.get("id", "")).strip()
        event_name = str(raw.get("event", "")).strip()
        if not occurrence_id or occurrence_id in occurrence_ids:
            raise ValueError("showcase occurrence IDs must be unique")
        occurrence_ids.add(occurrence_id)
        if event_name == "ac0908_001":
            frame_count_value = int(raw.get("frame_count", -1))
            include_exterior = raw.get("include_exterior")
            if not isinstance(include_exterior, bool) or frame_count_value <= 0:
                raise ValueError("invalid ac0908_001 occurrence")
            resolved_occurrences.append(
                {
                    "id": occurrence_id,
                    "event": event_name,
                    "kind": "reference_timed_entry",
                    "frame_count": frame_count_value,
                    "include_exterior": include_exterior,
                }
            )
        elif event_name in events:
            if set(raw) != {"id", "event"}:
                raise ValueError(f"{occurrence_id} event occurrence has extra fields")
            resolved_occurrences.append(
                {
                    "id": occurrence_id,
                    "event": event_name,
                    "kind": "approved_v27_event",
                    "frame_count": events[event_name]["frame_count"],
                }
            )
        else:
            raise ValueError(f"unsupported showcase event: {event_name}")
    expected_order = [
        "ac0908_001",
        "ac0908_002",
        "ac0908_001",
        "ac0908_003",
        "ac0908_001",
        "ac0908_004",
        "ac0908_009",
        "ac0908_006",
        "ac0908_009",
        "ac0908_005",
        "ac0908_009",
        "ac0908_007",
        "ac0908_008",
    ]
    if [row["event"] for row in resolved_occurrences] != expected_order:
        raise ValueError("showcase occurrence order differs from the reviewed reference")

    return {
        "release_id": str(plan["release_id"]),
        "title": str(plan["title"]),
        "reference_path": reference_path,
        "dirinfo_path": dirinfo_path,
        "layout": read_json(layout_path),
        "font_path": font_path,
        "entry_exterior": exterior_path,
        "entry_side": side_path,
        "entry_audio": audio_path,
        "events": events,
        "occurrences": resolved_occurrences,
        "source_snapshots": source_snapshots,
    }


def copy_pcm(source: Path, target_handle: Any) -> None:
    with source.open("rb") as source_handle:
        shutil.copyfileobj(source_handle, target_handle, 1024 * 1024)


def write_silence(target_handle: Any, samples: int) -> None:
    remaining = samples * 8
    block = b"\0" * (1024 * 1024)
    while remaining:
        chunk = min(remaining, len(block))
        target_handle.write(block[:chunk])
        remaining -= chunk


def assert_srt_round_trip(path: Path, cues: Sequence[Mapping[str, Any]]) -> None:
    write_srt(path, cues)
    expected = [
        {
            "start_ms": int(cue["start_ms"]),
            "end_ms": int(cue["end_ms"]),
            "text": str(cue["text"]),
        }
        for cue in cues
    ]
    if parse_srt(path) != expected:
        raise RuntimeError("showcase Chinese SRT round-trip differs")


def build_showcase(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> Path:
    plan = read_json(plan_path)
    resolved = validate_plan(plan, plan_path=plan_path, ffprobe=ffprobe)
    release_id = resolved["release_id"]
    if (
        not release_id
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in release_id)
    ):
        raise ValueError("unsafe showcase release_id")
    destination = output_root.resolve()
    if destination.exists():
        raise FileExistsError(f"versioned showcase root already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        work = staging / "work"
        work.mkdir()
        entry_visuals: dict[str, Path] = {}
        entry_visual_audits: dict[str, dict[str, Any]] = {}
        for occurrence in resolved["occurrences"]:
            if occurrence["event"] != "ac0908_001":
                continue
            output = work / f"{occurrence['id']}__visual.mp4"
            entry_visual_audits[occurrence["id"]] = build_entry_visual(
                output=output,
                exterior=resolved["entry_exterior"],
                side=resolved["entry_side"],
                include_exterior=bool(occurrence["include_exterior"]),
                frame_count_value=int(occurrence["frame_count"]),
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            entry_visuals[occurrence["id"]] = output

        event_pcm: dict[str, Path] = {}
        event_pcm_audits: dict[str, dict[str, Any]] = {}
        for event_name, event in resolved["events"].items():
            output = work / f"{event_name}.f32le"
            event_pcm_audits[event_name] = build_event_pcm(
                event, output=output, ffmpeg=ffmpeg
            )
            event_pcm[event_name] = output

        timeline: list[dict[str, Any]] = []
        subtitle_cues: list[dict[str, Any]] = []
        total_frames = 0
        total_samples = 0
        base_pcm = work / "base_scene.f32le"
        with base_pcm.open("wb") as target:
            for occurrence in resolved["occurrences"]:
                start_frame = total_frames
                start_sample = total_samples
                frames = int(occurrence["frame_count"])
                samples = frames * SAMPLES_PER_FRAME
                if occurrence["event"] == "ac0908_001":
                    write_silence(target, samples)
                else:
                    copy_pcm(event_pcm[occurrence["event"]], target)
                    offset_ms = milliseconds_for_samples(start_sample)
                    for cue in resolved["events"][occurrence["event"]]["local_zh_cues"]:
                        subtitle_cues.append(
                            {
                                "start_ms": offset_ms + int(cue["start_ms"]),
                                "end_ms": offset_ms + int(cue["end_ms"]),
                                "text": str(cue["text"]),
                                "event": occurrence["event"],
                                "occurrence_id": occurrence["id"],
                            }
                        )
                total_frames += frames
                total_samples += samples
                timeline.append(
                    {
                        "occurrence_id": occurrence["id"],
                        "event": occurrence["event"],
                        "kind": occurrence["kind"],
                        "start_frame": start_frame,
                        "end_frame": total_frames,
                        "start_sample": start_sample,
                        "end_sample": total_samples,
                        "include_exterior": occurrence.get("include_exterior"),
                    }
                )
        if base_pcm.stat().st_size != total_samples * 8:
            raise RuntimeError("showcase base PCM byte count differs")

        entry_occurrences = [
            row for row in timeline if row["event"] == "ac0908_001"
        ]
        mixed_pcm = work / "scene.f32le"
        command = [
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
            str(base_pcm),
        ]
        for _ in entry_occurrences:
            command.extend(["-i", str(resolved["entry_audio"])])
        filters = [
            (
                "[0:a:0]aformat=sample_fmts=fltp:"
                "sample_rates=48000:channel_layouts=stereo[base]"
            )
        ]
        labels = ["[base]"]
        for index, occurrence in enumerate(entry_occurrences, start=1):
            filters.append(
                f"[{index}:a:0]adelay={occurrence['start_sample']}S:all=1,"
                "aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:"
                f"channel_layouts=stereo[entry{index}]"
            )
            labels.append(f"[entry{index}]")
        filters.append(
            "".join(labels)
            + f"amix=inputs={len(labels)}:duration=longest:"
            "normalize=0:dropout_transition=0,"
            "alimiter=limit=0.95,"
            f"apad=whole_len={total_samples},atrim=end_sample={total_samples},"
            "asetpts=N/SR/TB[mix]"
        )
        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[mix]",
                "-f",
                "f32le",
                "-acodec",
                "pcm_f32le",
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "2",
                str(mixed_pcm),
            ]
        )
        run(command)
        if mixed_pcm.stat().st_size != total_samples * 8:
            raise RuntimeError("showcase mixed PCM byte count differs")

        masters = staging / "masters"
        masters.mkdir()
        audio_master = masters / f"{release_id}__no_bgm_audio_master.m4a"
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
                str(mixed_pcm),
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

        subtitle_dir = staging / "subtitles"
        subtitle_dir.mkdir()
        srt_path = subtitle_dir / f"{release_id}__zh.srt"
        assert_srt_round_trip(srt_path, subtitle_cues)
        staged_font_dir = work / "fonts"
        staged_font_dir.mkdir()
        staged_font = staged_font_dir / resolved["font_path"].name
        shutil.copy2(resolved["font_path"], staged_font)

        visual_inputs: list[Path] = []
        visual_filters: list[str] = []
        visual_labels: list[str] = []
        for index, occurrence in enumerate(resolved["occurrences"]):
            if occurrence["event"] == "ac0908_001":
                visual = entry_visuals[occurrence["id"]]
            else:
                visual = resolved["events"][occurrence["event"]]["clean_visual"]
            visual_inputs.append(visual)
            label = f"v{index}"
            visual_filters.append(
                f"[{index}:v:0]trim=end_frame={occurrence['frame_count']},"
                f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
            )
            visual_labels.append(f"[{label}]")
        joined_label = "joined"
        visual_filters.append(
            "".join(visual_labels)
            + f"concat=n={len(visual_labels)}:v=1:a=0[{joined_label}]"
        )
        subtitle_value = subtitle_filter(
            resolved["layout"],
            srt_path=srt_path.relative_to(staging).as_posix(),
            fonts_dir=staged_font_dir.relative_to(staging).as_posix(),
        )
        visual_filters.append(f"[{joined_label}]{subtitle_value}[outv]")
        review_dir = staging / "REVIEW_NOW_1_MP4"
        review_dir.mkdir()
        output_video = review_dir / "ac0908 六种菜品入口补全参考合集__zh.mp4"
        command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        for visual in visual_inputs:
            command.extend(["-i", str(visual)])
        audio_input_index = len(visual_inputs)
        command.extend(
            [
                "-i",
                str(audio_master),
                "-filter_complex",
                ";".join(visual_filters),
                "-map",
                "[outv]",
                "-map",
                f"{audio_input_index}:a:0",
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
                str(output_video),
            ]
        )
        run(command, cwd=staging)
        media_audit = validate_output_media(
            output_video,
            expected_frames=total_frames,
            ffprobe=ffprobe,
        )
        media_audit["path"] = relative_output_path(
            output_video,
            staging=staging,
        )

        qa_dir = staging / "qa"
        qa_dir.mkdir()
        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS,
            "automated_spec_qa_passed": True,
            "human_playback_approved": False,
            "publication_approved": False,
            "checks": {
                "native_416x232": True,
                "frame_rate_30fps": True,
                "h264_aac_48khz_stereo": True,
                "no_upscale": True,
                "no_external_reference_pixels_or_audio": True,
                "all_production_inputs_hash_bound": True,
                "six_exact_zh_route_approvals_bound": True,
                "edited_cross_route_showcase_declared": True,
                "single_native_session_claimed": False,
                "bgm_intentionally_excluded": True,
            },
            "media": media_audit,
        }
        write_json(qa_dir / "AUTOMATED_QA.json", qa)

        manifest_dir = staging / "manifest"
        manifest_dir.mkdir()
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": STATUS,
            "release_id": release_id,
            "title": resolved["title"],
            "product_scope": "reference-derived all-outcomes showcase",
            "session_claim": "edited_cross_route_showcase_not_one_native_session",
            "external_reference_policy": (
                "ordering_and_entry_presentation_only_no_reference_pixels_or_audio"
            ),
            "audio_profile": "no_bgm",
            "bgm_policy": "intentionally_excluded",
            "voice_se_policy": "preserve_v27_owner-playback-approved_timing_and_verified_scene_audio",
            "human_playback_approved": False,
            "publication_approved": False,
            "media": {
                "width": WIDTH,
                "height": HEIGHT,
                "frame_rate": "30/1",
                "frame_count": total_frames,
                "duration_ms": milliseconds_for_samples(total_samples),
                "audio_samples": total_samples,
                "output": media_audit,
            },
            "timeline": timeline,
            "subtitle_cue_count": len(subtitle_cues),
            "entry_audio_overlap_policy": (
                "ac0908_001 scene audio starts at each entry presentation and may "
                "continue across the following event boundary, matching the "
                "reference-observed presentation duration"
            ),
            "event_pcm_audits": event_pcm_audits,
            "entry_visual_audits": entry_visual_audits,
            "source_snapshots": resolved["source_snapshots"],
        }
        manifest_path = manifest_dir / "SHOWCASE_MANIFEST.json"
        write_json(manifest_path, manifest)

        review = {
            "schema": "magireco-human-review-status-v1",
            "status": STATUS,
            "human_playback_approved": False,
            "publication_approved": False,
            "review_file": str(output_video.relative_to(staging)),
            "review_focus": [
                "00:00 opening must show the restaurant exterior, then side cooking",
                "the edited outcome order must be 002, 003, 004, 006, 005, 007",
                "each voice and Chinese subtitle must remain aligned with its source event",
                "the final ac0908_008 score dialogue must appear exactly once",
                "no BGM; verified dialogue and scene SE remain audible",
            ],
            "warning": (
                "This is an edited all-outcomes showcase across mutually exclusive "
                "routes, not one native game session."
            ),
        }
        write_json(staging / "HUMAN_REVIEW_REQUIRED.json", review)
        readme = (
            "# ac0908 六种菜品入口补全参考合集\n\n"
            f"当前状态：`{STATUS}`。\n\n"
            "只需人工观看 `REVIEW_NOW_1_MP4` 中的一个 ZH MP4。它补回 "
            "`ac0908_001` 的饭店外景与侧身炒菜，并按参考片的编辑顺序排列六种"
            "互斥菜品结果。它不是一次游戏自然播放；原有六条独立 ZH 路线继续保留。\n\n"
            "参考视频只用于画面顺序与入口呈现时长；成片没有使用参考视频的像素或"
            "音频。BGM 有意排除，保留现有证据绑定的对白与场景音效。\n"
        )
        (review_dir / "README_REVIEW_NOW.md").write_text(readme, encoding="utf-8")
        hash_manifest = {
            "schema": "magireco-review-directory-sha256-v1",
            "status": STATUS,
            "files": [
                {
                    "path": output_video.name,
                    "sha256": file_sha256(output_video),
                    "byte_count": output_video.stat().st_size,
                }
            ],
            "showcase_manifest_sha256": file_sha256(manifest_path),
            "automated_qa_sha256": file_sha256(qa_dir / "AUTOMATED_QA.json"),
            "human_playback_approved": False,
            "publication_approved": False,
        }
        write_json(review_dir / "MANIFEST_SHA256.json", hash_manifest)

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
    plan = read_json(plan_path)
    resolved = validate_plan(plan, plan_path=plan_path, ffprobe=args.ffprobe)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "schema": PLAN_SCHEMA,
                    "status": "validated",
                    "release_id": resolved["release_id"],
                    "occurrence_count": len(resolved["occurrences"]),
                    "source_snapshot_count": len(resolved["source_snapshots"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    destination = build_showcase(
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
                "human_playback_approved": False,
                "publication_approved": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
