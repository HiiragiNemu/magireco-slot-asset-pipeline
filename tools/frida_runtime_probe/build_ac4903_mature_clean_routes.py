#!/usr/bin/env python3
"""Build the nineteen evidence-ready native ac4903 DirInfo route segments.

The already produced ac4903 family master supplies event-exact visuals, no-BGM
audio, and JA/ZH subtitle timing for events 002-006 and 009-013.  Five simple
native 416x232 events (001, 007, 008, 016, 018) are reconstructed from their
hash-bound official clips.  Each simple event also has one verified direct
parent scene-SE request at event-global time zero.  Those SE tails are allowed
to continue across the next event boundary, as they would on the route timeline.

DirInfo rows 14, 18, and 21 terminate in ac4903_015, whose evidence mixes
416x232 story content with a 256x144 victory/effect layer.  They are excluded
from this clean-story batch and remain assigned to layered gameplay/effect
composition.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_ac0908_approved_production as approved
    from . import build_ac0908_reference_showcase as reference
    from . import build_mature_416_route_batch as mature
except ImportError:  # direct script execution
    import build_ac0908_approved_production as approved  # type: ignore
    import build_ac0908_reference_showcase as reference  # type: ignore
    import build_mature_416_route_batch as mature  # type: ignore


PLAN_SCHEMA = "magireco-ac4903-mature-clean-routes-plan-v1"
MANIFEST_SCHEMA = "magireco-ac4903-mature-clean-routes-manifest-v1"
ROUTE_SCHEMA = "magireco-ac4903-mature-clean-route-manifest-v1"
QA_SCHEMA = "magireco-ac4903-mature-clean-routes-qa-v1"
STATUS = "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
FAMILY = "ac4903"
DIRINFO_KIND = 114
EDITIONS = ("none", "ja", "zh")
SIMPLE_EVENTS = ("ac4903_001", "ac4903_007", "ac4903_008", "ac4903_016", "ac4903_018")
SOURCE_EVENTS = (
    "ac4903_002",
    "ac4903_003",
    "ac4903_004",
    "ac4903_005",
    "ac4903_006",
    "ac4903_009",
    "ac4903_010",
    "ac4903_011",
    "ac4903_012",
    "ac4903_013",
)
INCLUDED_ROWS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 19, 20)
EXCLUDED_ROWS = (14, 18, 21)


def _read_json(path: Path) -> dict[str, Any]:
    return reference.read_json(path)


def _bound(
    raw: Mapping[str, Any],
    *,
    label: str,
    plan_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    return reference.validate_bound_file(
        {"path": raw["path"], "sha256": raw["sha256"]},
        label=label,
        plan_dir=plan_dir,
    )


def _validate_native_media(value: Any) -> None:
    if not isinstance(value, Mapping) or (
        int(value.get("width", -1)),
        int(value.get("height", -1)),
        str(value.get("frame_rate", "")),
        str(value.get("video_codec", "")),
        str(value.get("audio_codec", "")),
        int(value.get("audio_sample_rate", -1)),
        int(value.get("audio_channels", -1)),
        bool(value.get("upscale", True)),
    ) != (416, 232, "30/1", "h264", "aac", 48000, 2, False):
        raise ValueError("ac4903 native media contract differs")


def _dirinfo_routes(path: Path) -> dict[int, list[str]]:
    routes: dict[int, list[tuple[int, str, str]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if int(raw["kind"]) != DIRINFO_KIND:
                continue
            row = int(raw["row_index"])
            routes.setdefault(row, []).append(
                (
                    int(raw["selector_raw"]),
                    str(raw["scene_name"]),
                    str(raw["route_status"]),
                )
            )
    output: dict[int, list[str]] = {}
    for row, values in routes.items():
        values.sort()
        if any(status != "ok" for _, _, status in values):
            raise ValueError(f"DirInfo kind {DIRINFO_KIND} row {row} is not resolved")
        output[row] = [event for _, event, _ in values]
    if set(output) != set(INCLUDED_ROWS) | set(EXCLUDED_ROWS):
        raise ValueError("DirInfo kind 114 row set differs")
    for row in EXCLUDED_ROWS:
        if not output[row] or output[row][-1] != "ac4903_015":
            raise ValueError(f"excluded DirInfo row {row} no longer terminates in ac4903_015")
    for row in INCLUDED_ROWS:
        if "ac4903_015" in output[row]:
            raise ValueError(f"included DirInfo row {row} contains ac4903_015")
    return output


def _validate_uploaded_p13(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if (
        value.get("schema") != "magireco-owner-upload-confirmation-v1"
        or value.get("status") != "uploaded_by_project_owner"
    ):
        raise ValueError("owner-upload attestation identity differs")
    matches = [
        row
        for row in value.get("files", [])
        if isinstance(row, Mapping) and row.get("part") == "P13"
    ]
    if len(matches) != 1 or (
        str(matches[0].get("filename", "")),
        str(matches[0].get("sha256", "")).upper(),
    ) != (
        "P13 Magius启动魔法少女解放计划 ac4903__zh.mp4",
        "CE7B7B7D7646437464DC84B9700F86C2A0F7C241E5AB904D833603FB84070A7C",
    ):
        raise ValueError("owner-uploaded P13 exact-file binding differs")
    return {
        "part": "P13",
        "filename": str(matches[0]["filename"]),
        "sha256": str(matches[0]["sha256"]).upper(),
        "scope": "source family ZH only; does not approve new route outputs",
    }


def _validate_source_family(
    *,
    plan: Mapping[str, Any],
    plan_path: Path,
    snapshots: list[dict[str, Any]],
    ffprobe: str,
) -> dict[str, Any]:
    raw = plan["source_family"]
    bound: dict[str, Path] = {}
    for key in (
        "manifest",
        "automated_qa",
        "clean_visual_master",
        "no_bgm_audio_master",
        "subtitles_ja",
        "subtitles_zh",
    ):
        path, snapshot = _bound(
            raw[key],
            label=f"ac4903 source family {key}",
            plan_dir=plan_path.parent,
        )
        bound[key] = path
        snapshots.append(snapshot)

    family = _read_json(bound["manifest"])
    qa = _read_json(bound["automated_qa"])
    if (
        family.get("schema") != "magireco-no-bgm-story-family-editions-v1"
        or family.get("status") != "AUTOMATED_QA_PASSED"
        or family.get("family") != FAMILY
        or tuple(family.get("ordered_events", [])) != SOURCE_EVENTS
        or tuple(family.get("selected_editions", [])) != EDITIONS
        or family.get("publishable") is not False
    ):
        raise ValueError("ac4903 source family identity differs")
    if (
        qa.get("schema") != "magireco-no-bgm-story-family-editions-qa-v1"
        or qa.get("status") != "passed"
        or tuple(qa.get("events", [])) != SOURCE_EVENTS
        or tuple(qa.get("selected_editions", [])) != EDITIONS
    ):
        raise ValueError("ac4903 source family automated QA differs")
    required_checks = (
        "source_hashes_unchanged",
        "all_events_technical_ready",
        "clean_visual_master_shared",
        "no_bgm_layers_present",
        "retained_audio_roles_are_evidence_bound_voice_or_scene_se",
        "unresolved_audio_layer_count_zero",
        "native_dimensions_30fps_no_upscale",
        "exact_frame_and_sample_grid",
        "aac_encoded_once_and_packet_identical",
        "selected_srt_files_round_trip",
    )
    if any(qa.get("checks", {}).get(key) is not True for key in required_checks):
        raise ValueError("ac4903 source family required QA check is not true")

    timeline: dict[str, dict[str, Any]] = {}
    for row in family.get("timeline", []):
        if not isinstance(row, Mapping):
            raise ValueError("source family timeline row is not an object")
        event = str(row.get("event", ""))
        frames = int(row["end_frame"]) - int(row["start_frame"])
        samples = int(row["end_sample"]) - int(row["start_sample"])
        if (
            event not in SOURCE_EVENTS
            or event in timeline
            or frames <= 0
            or samples != frames * reference.SAMPLES_PER_FRAME
            or int(row.get("inserted_gap_frames", -1)) != 0
        ):
            raise ValueError("source family event timeline differs")
        timeline[event] = dict(row)
    if tuple(timeline) != SOURCE_EVENTS:
        raise ValueError("source family timeline order differs")
    reference.validate_video_grid(
        bound["clean_visual_master"],
        expected_frames=int(family["timeline"][-1]["end_frame"]),
        ffprobe=ffprobe,
        label="ac4903 source family clean visual",
    )
    mature._validate_audio_master(bound["no_bgm_audio_master"], ffprobe=ffprobe)
    ja_cues = mature.parse_srt(bound["subtitles_ja"])
    zh_cues = mature.parse_srt(bound["subtitles_zh"])
    if len(ja_cues) != int(family["dialogue_cue_count"]) or len(zh_cues) != len(ja_cues):
        raise ValueError("source family subtitle cue count differs")
    return {
        "manifest": family,
        "qa": qa,
        "bound": bound,
        "timeline": timeline,
        "local_cues": {
            edition: {
                event: approved.extract_event_local_cues(
                    cues, timeline_row=timeline[event], event=event
                )
                for event in SOURCE_EVENTS
            }
            for edition, cues in (("ja", ja_cues), ("zh", zh_cues))
        },
    }


def _validate_catalogs(
    *,
    plan: Mapping[str, Any],
    plan_path: Path,
    snapshots: list[dict[str, Any]],
) -> None:
    catalog_path, snapshot = _bound(
        plan["audience_event_catalog"],
        label="audience event catalog",
        plan_dir=plan_path.parent,
    )
    snapshots.append(snapshot)
    clips_path, snapshot = _bound(
        plan["audience_event_clips"],
        label="audience event clips",
        plan_dir=plan_path.parent,
    )
    snapshots.append(snapshot)
    audio_path, snapshot = _bound(
        plan["event_audio_components"],
        label="event audio components",
        plan_dir=plan_path.parent,
    )
    snapshots.append(snapshot)

    catalog_rows: dict[str, dict[str, str]] = {}
    with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            event = str(raw["event_name"])
            if event in SIMPLE_EVENTS:
                catalog_rows[event] = dict(raw)
    if set(catalog_rows) != set(SIMPLE_EVENTS):
        raise ValueError("simple event catalog coverage differs")
    for event, row in catalog_rows.items():
        if (
            row["classification"] != "native_full_frame_only"
            or row["dimensions"] != "416x232"
            or int(row["clip_count"]) != 2
            or int(row["resolved_clip_count"]) != 2
            or int(row["full_frame_clip_count"]) != 2
            or int(row["auto_voice_count"]) != 0
            or row["automatic_candidate"] != "yes"
        ):
            raise ValueError(f"{event} simple event catalog contract differs")

    clip_rows: dict[str, list[dict[str, str]]] = {event: [] for event in SIMPLE_EVENTS}
    with clips_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            event = str(raw["event_name"])
            if event in clip_rows:
                clip_rows[event].append(dict(raw))
    for event, rows in clip_rows.items():
        rows.sort(key=lambda row: (int(row["z2d_order"]), int(row["dgm_order"])))
        planned = plan["simple_events"][event]["clips"]
        if len(rows) != len(planned) or not rows:
            raise ValueError(f"{event} simple event clip count differs")
        for row, clip in zip(rows, planned):
            path = Path(str(clip["path"]))
            if (
                row["official_name"] != path.stem
                or row["source_exists"] != "yes"
                or row["media_class"] != "full_frame_landscape"
                or (int(row["width"]), int(row["height"]), row["frame_rate"])
                != (416, 232, "30/1")
            ):
                raise ValueError(f"{event} clip catalog row differs")

    audio_rows: dict[str, list[dict[str, str]]] = {
        event: [] for event in SIMPLE_EVENTS
    }
    with audio_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            root = str(raw.get("root", ""))
            primary = str(raw.get("primary_animation", ""))
            if root == FAMILY and primary in audio_rows:
                audio_rows[primary].append(dict(raw))
    for event, rows in audio_rows.items():
        planned = plan["simple_events"][event]["audio_source"]
        if len(rows) != 1:
            raise ValueError(f"{event} requires exactly one direct parent scene-SE row")
        row = rows[0]
        path = Path(str(planned["path"]))
        request_id = int(planned["request_id"])
        sound_code = int(planned["sound_code"])
        duration_ms = int(planned["duration_ms"])
        if (
            int(row["start_ms"]) != int(planned["start_ms"])
            or int(planned["start_ms"]) != 0
            or int(row["parent_request_id"]) != request_id
            or int(row["leaf_request_id"]) != request_id
            or int(row["leaf_sound_code"]) != sound_code
            or int(row["duration_ms"]) != duration_ms
            or row["ogg_name"] != path.name
            or row["ogg_duration_match"] != "yes"
            or str(row["subtitle_text"]).strip()
        ):
            raise ValueError(f"{event} direct parent scene-SE evidence differs")


def validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "evidence_ready_full_production"
        or plan.get("family") != FAMILY
        or plan.get("audio_profile") != "no_bgm"
        or tuple(plan.get("editions", [])) != EDITIONS
        or tuple(plan.get("included_dirinfo_rows", [])) != INCLUDED_ROWS
        or tuple(int(row["row"]) for row in plan.get("excluded_dirinfo_rows", []))
        != EXCLUDED_ROWS
    ):
        raise ValueError("ac4903 route plan identity differs")
    _validate_native_media(plan.get("native_media"))
    snapshots: list[dict[str, Any]] = [
        {
            "label": "ac4903 mature clean route plan",
            "path": str(plan_path.resolve()),
            "sha256": mature.file_sha256(plan_path),
        }
    ]
    dirinfo_path, snapshot = _bound(
        plan["dirinfo"], label="DirInfo route evidence", plan_dir=plan_path.parent
    )
    snapshots.append(snapshot)
    routes = _dirinfo_routes(dirinfo_path)

    source = _validate_source_family(
        plan=plan,
        plan_path=plan_path,
        snapshots=snapshots,
        ffprobe=ffprobe,
    )
    _validate_catalogs(plan=plan, plan_path=plan_path, snapshots=snapshots)

    owner_path, snapshot = _bound(
        plan["owner_uploaded_zh_attestation"],
        label="owner-uploaded P13 exact ZH attestation",
        plan_dir=plan_path.parent,
    )
    snapshots.append(snapshot)
    uploaded_p13 = _validate_uploaded_p13(owner_path)
    layout_path, snapshot = _bound(
        plan["subtitle_layout"],
        label="approved 416x232 subtitle layout",
        plan_dir=plan_path.parent,
    )
    snapshots.append(snapshot)
    layout = _read_json(layout_path)
    font_path, snapshot = _bound(
        plan["font"], label="subtitle font", plan_dir=plan_path.parent
    )
    snapshots.append(snapshot)

    simple: dict[str, dict[str, Any]] = {}
    for event in SIMPLE_EVENTS:
        raw = plan["simple_events"][event]
        if (
            raw.get("audio_policy")
            != "verified_direct_parent_scene_se_at_event_global_zero_may_continue_across_boundary"
        ):
            raise ValueError(f"{event} audio policy differs")
        audio_path, snapshot = _bound(
            raw["audio_source"],
            label=f"{event} verified direct parent scene SE",
            plan_dir=plan_path.parent,
        )
        snapshots.append(snapshot)
        audio_probe = mature.probe(audio_path, ffprobe)
        if (
            mature.media_streams(audio_probe, "video")
            or mature.media_streams(audio_probe, "subtitle")
            or len(mature.media_streams(audio_probe, "audio")) != 1
        ):
            raise ValueError(f"{event} verified scene SE media contract differs")
        clips = []
        for index, clip in enumerate(raw["clips"]):
            path, snapshot = _bound(
                clip,
                label=f"{event} official clip {index}",
                plan_dir=plan_path.parent,
            )
            snapshots.append(snapshot)
            expected_frames = int(clip["frames"])
            audit = reference.validate_video_grid(
                path,
                expected_frames=expected_frames,
                ffprobe=ffprobe,
                label=f"{event} official clip {index}",
            )
            value = mature.probe(path, ffprobe)
            if mature.media_streams(value, "audio") or mature.media_streams(value, "subtitle"):
                raise ValueError(f"{event} official clip {index} is not video-only")
            clips.append(
                {
                    "path": path,
                    "frames": expected_frames,
                    "sha256": mature.file_sha256(path),
                    "audit": audit,
                }
            )
        if len(clips) != 2:
            raise ValueError(f"{event} requires exactly two official clips")
        simple[event] = {
            "clips": clips,
            "frames": sum(int(row["frames"]) for row in clips),
            "audio_policy": raw["audio_policy"],
            "audio_source": audio_path,
            "audio_sha256": mature.file_sha256(audio_path),
            "audio_request_id": int(raw["audio_source"]["request_id"]),
            "audio_sound_code": int(raw["audio_source"]["sound_code"]),
            "audio_duration_ms": int(raw["audio_source"]["duration_ms"]),
        }

    return {
        "title": str(plan["title"]),
        "routes": routes,
        "source": source,
        "simple": simple,
        "layout": layout,
        "font": font_path,
        "snapshots": snapshots,
        "uploaded_p13": uploaded_p13,
    }


def _extract_source_event_assets(
    *,
    event: str,
    source: Mapping[str, Any],
    output_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    row = source["timeline"][event]
    frames = int(row["end_frame"]) - int(row["start_frame"])
    samples = int(row["end_sample"]) - int(row["start_sample"])
    visual = output_dir / f"{event}.mp4"
    pcm = output_dir / f"{event}.f32le"
    mature._build_clean_visual(
        source=source["bound"]["clean_visual_master"],
        timeline=[
            {
                "source_start_frame": int(row["start_frame"]),
                "source_end_frame": int(row["end_frame"]),
            }
        ],
        output=visual,
        total_frames=frames,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    mature._build_pcm(
        source=source["bound"]["no_bgm_audio_master"],
        timeline=[
            {
                "source_start_sample": int(row["start_sample"]),
                "source_end_sample": int(row["end_sample"]),
            }
        ],
        output=pcm,
        total_samples=samples,
        ffmpeg=ffmpeg,
    )
    return {
        "event": event,
        "frames": frames,
        "samples": samples,
        "visual": visual,
        "pcm": pcm,
        "cues": {
            edition: list(source["local_cues"][edition][event])
            for edition in ("ja", "zh")
        },
        "source_policy": "hash_bound_event_interval_from_approved_source_family",
    }


def _build_simple_event_assets(
    *,
    event: str,
    simple: Mapping[str, Any],
    output_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    visual = output_dir / f"{event}.mp4"
    filters = []
    labels = []
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for index, clip in enumerate(simple["clips"]):
        command.extend(["-i", str(clip["path"])])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={int(clip['frames'])},"
            f"setpts=N/({reference.FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]")
    frames = int(simple["frames"])
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(frames),
            "-an",
            "-movflags",
            "+faststart",
            str(visual),
        ]
    )
    mature.run(command)
    reference.validate_video_grid(
        visual,
        expected_frames=frames,
        ffprobe=ffprobe,
        label=f"{event} simple event asset",
    )
    samples = frames * reference.SAMPLES_PER_FRAME
    pcm = output_dir / f"{event}.f32le"
    with pcm.open("wb") as handle:
        handle.truncate(samples * 8)
    return {
        "event": event,
        "frames": frames,
        "samples": samples,
        "visual": visual,
        "pcm": pcm,
        "cues": {"ja": [], "zh": []},
        "source_policy": "official_native_clips_plus_verified_direct_parent_scene_se",
        "scene_se": {
            "path": simple["audio_source"],
            "sha256": simple["audio_sha256"],
            "request_id": simple["audio_request_id"],
            "sound_code": simple["audio_sound_code"],
            "start_sample": 0,
            "duration_ms": simple["audio_duration_ms"],
        },
    }


def _build_route_pcm(
    *,
    events: Sequence[str],
    assets: Mapping[str, Mapping[str, Any]],
    output: Path,
    ffmpeg: str,
) -> dict[str, Any]:
    base = output.with_name(output.stem + ".base.f32le")
    mature._copy_pcm([assets[event]["pcm"] for event in events], base)
    total_samples = sum(int(assets[event]["samples"]) for event in events)
    if base.stat().st_size != total_samples * 8:
        raise RuntimeError("ac4903 route base PCM byte count differs")

    overlays: list[tuple[int, Mapping[str, Any], str]] = []
    sample_cursor = 0
    for event in events:
        scene_se = assets[event].get("scene_se")
        if isinstance(scene_se, Mapping):
            overlays.append((sample_cursor, scene_se, event))
        sample_cursor += int(assets[event]["samples"])
    if not overlays:
        shutil.copy2(base, output)
        base.unlink()
        return {
            "sample_count": total_samples,
            "byte_count": total_samples * 8,
            "sha256": mature.file_sha256(output),
            "scene_se_overlays": [],
        }

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "f32le",
        "-ar",
        str(reference.SAMPLE_RATE),
        "-ac",
        "2",
        "-i",
        str(base),
    ]
    for _, scene_se, _ in overlays:
        command.extend(["-i", str(scene_se["path"])])
    filters = [
        f"[0:a:0]atrim=end_sample={total_samples},"
        "asetpts=PTS-STARTPTS,"
        "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[base]"
    ]
    labels = ["[base]"]
    audit_rows = []
    for index, (start_sample, scene_se, event) in enumerate(overlays, start=1):
        label = f"se{index}"
        filters.append(
            f"[{index}:a:0]aresample=48000,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"asetpts=PTS-STARTPTS+{start_sample}/48000/TB[{label}]"
        )
        labels.append(f"[{label}]")
        audit_rows.append(
            {
                "event": event,
                "start_sample": start_sample,
                "request_id": int(scene_se["request_id"]),
                "sound_code": int(scene_se["sound_code"]),
                "source_sha256": str(scene_se["sha256"]),
            }
        )
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0,"
        f"atrim=end_sample={total_samples},"
        "aresample=48000,"
        "aformat=sample_fmts=flt:sample_rates=48000:channel_layouts=stereo[outa]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outa]",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(reference.SAMPLE_RATE),
            "-ac",
            "2",
            str(output),
        ]
    )
    mature.run(command)
    base.unlink()
    if output.stat().st_size != total_samples * 8:
        raise RuntimeError("ac4903 route mixed PCM byte count differs")
    return {
        "sample_count": total_samples,
        "byte_count": total_samples * 8,
        "sha256": mature.file_sha256(output),
        "scene_se_overlays": audit_rows,
    }


def _route_timeline(
    events: Sequence[str], assets: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    frame_cursor = sample_cursor = 0
    for event in events:
        asset = assets[event]
        frames = int(asset["frames"])
        samples = int(asset["samples"])
        if samples != frames * reference.SAMPLES_PER_FRAME:
            raise ValueError(f"{event} event asset is off the 30fps sample grid")
        timeline.append(
            {
                "event": event,
                "start_frame": frame_cursor,
                "end_frame": frame_cursor + frames,
                "start_sample": sample_cursor,
                "end_sample": sample_cursor + samples,
                "source_policy": asset["source_policy"],
            }
        )
        frame_cursor += frames
        sample_cursor += samples
    return timeline


def _route_cues(
    *,
    events: Sequence[str],
    assets: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {"ja": [], "zh": []}
    sample_cursor = 0
    for event in events:
        offset_ms = reference.milliseconds_for_samples(sample_cursor)
        for edition in ("ja", "zh"):
            for cue in assets[event]["cues"][edition]:
                output[edition].append(
                    {
                        "start_ms": offset_ms + int(cue["start_ms"]),
                        "end_ms": offset_ms + int(cue["end_ms"]),
                        "text": str(cue["text"]),
                    }
                )
        sample_cursor += int(assets[event]["samples"])
    return output


def _concat_route_visual(
    *,
    events: Sequence[str],
    assets: Mapping[str, Mapping[str, Any]],
    output: Path,
    ffmpeg: str,
    ffprobe: str,
) -> None:
    filters = []
    labels = []
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for index, event in enumerate(events):
        asset = assets[event]
        command.extend(["-i", str(asset["visual"])])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={int(asset['frames'])},"
            f"setpts=N/({reference.FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]")
    total_frames = sum(int(assets[event]["frames"]) for event in events)
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
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
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    mature.run(command)
    reference.validate_video_grid(
        output,
        expected_frames=total_frames,
        ffprobe=ffprobe,
        label="ac4903 route clean visual",
    )


def build(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[Path, dict[str, Any]]:
    plan = _read_json(plan_path)
    resolved = validate_plan(plan, plan_path=plan_path, ffprobe=ffprobe)
    destination = output_root.resolve() / FAMILY
    if destination.exists():
        raise FileExistsError(f"versioned ac4903 output exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root.resolve() / f".{FAMILY}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        work = staging / ".work"
        event_dir = work / "events"
        event_dir.mkdir(parents=True)
        fonts_dir = work / "fonts"
        fonts_dir.mkdir()
        shutil.copy2(resolved["font"], fonts_dir / resolved["font"].name)

        assets: dict[str, dict[str, Any]] = {}
        for event in SOURCE_EVENTS:
            assets[event] = _extract_source_event_assets(
                event=event,
                source=resolved["source"],
                output_dir=event_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
        for event in SIMPLE_EVENTS:
            assets[event] = _build_simple_event_assets(
                event=event,
                simple=resolved["simple"][event],
                output_dir=event_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )

        products = []
        for row in INCLUDED_ROWS:
            events = resolved["routes"][row]
            route_id = f"dirinfo-row-{row:03d}"
            route_dir = staging / "routes" / route_id
            route_work = route_dir / ".work"
            route_work.mkdir(parents=True)
            clean = route_work / "clean.mp4"
            pcm = route_work / "audio.f32le"
            _concat_route_visual(
                events=events,
                assets=assets,
                output=clean,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            timeline = _route_timeline(events, assets)
            total_samples = int(timeline[-1]["end_sample"])
            pcm_audit = _build_route_pcm(
                events=events,
                assets=assets,
                output=pcm,
                ffmpeg=ffmpeg,
            )
            if pcm_audit["sample_count"] != total_samples:
                raise RuntimeError(f"ac4903 route {row} PCM duration differs")
            cues = _route_cues(events=events, assets=assets)
            product, _ = mature._build_one_product(
                product_id=f"{FAMILY}__{route_id}",
                title=f"{resolved['title']}（DirInfo 路线 {row}）",
                timeline=timeline,
                clean_visual=clean,
                pcm=pcm,
                cues=cues,
                output_dir=route_dir,
                staging=staging,
                layout=resolved["layout"],
                fonts_dir=fonts_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            product.update(
                {
                    "schema": ROUTE_SCHEMA,
                    "status": STATUS,
                    "product_scope": "independent_dirinfo_clean_story_route",
                    "dirinfo_kind": DIRINFO_KIND,
                    "dirinfo_row": row,
                    "ordered_events": events,
                    "single_native_session_claimed": True,
                    "simple_event_audio_scope_note": (
                        "Each simple event preserves its hash-bound direct parent scene SE "
                        "from event-global time zero, including cross-boundary tails."
                    ),
                    "route_pcm_audit": pcm_audit,
                    "human_playback_approved": False,
                    "publication_approved": False,
                }
            )
            reference.write_json(route_dir / "ROUTE_MANIFEST.json", product)
            shutil.rmtree(route_work)
            products.append(product)

        final_videos = sorted(staging.rglob("video/*.mp4"))
        if len(final_videos) != len(INCLUDED_ROWS) * len(EDITIONS):
            raise RuntimeError("ac4903 final audience MP4 count differs")
        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS,
            "automated_spec_qa_passed": True,
            "human_playback_approved": False,
            "publication_approved": False,
            "checks": {
                "dirinfo_kind_114_rows_hash_bound_and_exact": True,
                "nineteen_independent_routes_built": True,
                "rows_14_18_21_excluded_for_ac4903_015_layered_effect": True,
                "source_family_hash_bound_and_automated_qa_passed": True,
                "simple_events_are_native_full_frame_only": True,
                "simple_event_official_clips_sha256_bound": True,
                "simple_event_direct_parent_scene_se_rows_exact": True,
                "simple_event_scene_se_cross_boundary_tails_preserved": True,
                "native_416x232_30fps_no_upscale": True,
                "h264_aac_48khz_stereo": True,
                "exact_frame_and_sample_grid": True,
                "subtitle_round_trip": True,
                "none_ja_zh_audio_packets_and_decoded_pcm_identical_per_route": True,
                "source_uploaded_p13_untouched": True,
            },
            "route_count": len(products),
            "final_mp4_count": len(final_videos),
            "excluded_dirinfo_rows": list(EXCLUDED_ROWS),
        }
        reference.write_json(staging / "AUTOMATED_QA.json", qa)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": STATUS,
            "family": FAMILY,
            "title": resolved["title"],
            "audio_profile": "no_bgm",
            "bgm_policy": "intentionally_excluded",
            "voice_se_policy": (
                "preserve hash-bound source-family voice/SE and hash-bound simple-event "
                "direct parent scene SE, including cross-boundary tails"
            ),
            "editions": list(EDITIONS),
            "native_media": plan["native_media"],
            "routes": products,
            "included_dirinfo_rows": list(INCLUDED_ROWS),
            "excluded_dirinfo_rows": plan["excluded_dirinfo_rows"],
            "source_snapshots": resolved["snapshots"],
            "owner_uploaded_source_p13": resolved["uploaded_p13"],
            "human_playback_approved": False,
            "publication_approved": False,
        }
        reference.write_json(staging / "BATCH_MANIFEST.json", manifest)
        files = [
            {
                "path": reference.relative_output_path(path, staging=staging),
                "sha256": mature.file_sha256(path),
                "byte_count": path.stat().st_size,
            }
            for path in sorted(staging.rglob("*"))
            if path.is_file()
            and ".work" not in path.parts
            and path.name != "SHA256SUMS.json"
        ]
        reference.write_json(
            staging / "SHA256SUMS.json",
            {
                "schema": "magireco-versioned-output-sha256-v1",
                "family": FAMILY,
                "files": files,
            },
        )
        (staging / "README_REVIEW.md").write_text(
            "# ac4903 原生 416×232 分支路线人工复看\n\n"
            "本批包含 DirInfo kind 114 的 19 条独立 clean-story 路线，每条均有 "
            "none / JA / ZH。请逐路线观看，不要把互斥路线合称为一次自然播放。\n\n"
            "DirInfo rows 14、18、21 因终点 ac4903_015 混合 416×232 剧情与 "
            "256×144 胜利/玩法效果，未纳入本批。BGM 有意排除；来源 family "
            "中已验证的对白与场景音效予以保留。新生成文件尚未获人工播放或投稿批准。\n",
            encoding="utf-8",
        )
        shutil.rmtree(work)
        staging.replace(destination)
        return destination, qa
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan_path = args.plan.resolve()
    if args.validate_only:
        plan = _read_json(plan_path)
        resolved = validate_plan(plan, plan_path=plan_path, ffprobe=args.ffprobe)
        print(
            json.dumps(
                {
                    "status": "VALID",
                    "included_routes": len(INCLUDED_ROWS),
                    "excluded_routes": len(EXCLUDED_ROWS),
                    "source_snapshots": len(resolved["snapshots"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    destination, qa = build(
        plan_path=plan_path,
        output_root=args.output_root.resolve(),
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(
        json.dumps(
            {"destination": str(destination), "qa": qa},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
