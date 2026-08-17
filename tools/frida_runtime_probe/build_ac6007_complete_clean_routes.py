#!/usr/bin/env python3
"""Build two finite native ac6007 clean-story route candidates.

DirInfo kind 174 rows 0 and 1 are the only routes that remain entirely on the
native 416x232 clean-story surface.  Both begin with ac6007_001.  The entry
event is reconstructed from its parent presentation intervals: the lower scene
is visible for 36 frames, then the opaque title intro and title loop replace it.
Two missing additive title-effect components are deliberately excluded.

Rows 2-4 terminate in component-only gameplay/effect events and are not clean
story products.  The exact new files remain human-playback candidates because
the clean omission of the missing additive title layer has not been approved.
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
    from . import build_ac4903_mature_clean_routes as route_utils
    from . import build_mature_416_route_batch as mature
except ImportError:  # direct script execution
    import build_ac0908_approved_production as approved  # type: ignore
    import build_ac0908_reference_showcase as reference  # type: ignore
    import build_ac4903_mature_clean_routes as route_utils  # type: ignore
    import build_mature_416_route_batch as mature  # type: ignore


PLAN_SCHEMA = "magireco-ac6007-complete-clean-routes-plan-v1"
PLAN_OVERLAY_SCHEMA = "magireco-ac6007-complete-clean-routes-plan-overlay-v1"
MANIFEST_SCHEMA = "magireco-ac6007-complete-clean-routes-manifest-v1"
ROUTE_SCHEMA = "magireco-ac6007-complete-clean-route-manifest-v1"
QA_SCHEMA = "magireco-ac6007-complete-clean-routes-qa-v1"
STATUS = "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
FAMILY = "ac6007"
DIRINFO_KIND = 174
EDITIONS = ("none", "ja", "zh")
SOURCE_EVENTS = (
    "ac6007_002",
    "ac6007_003",
    "ac6007_004",
    "ac6007_005",
    "ac6007_006",
)
INCLUDED_ROWS = (0, 1)
EXCLUDED_ROWS = (2, 3, 4)
ENTRY_EVENT = "ac6007_001"
ENTRY_VISIBLE_SEQUENCE = (
    "ac6007_lev_c001_MR",
    "ac6007_AT_kuma_title",
    "ac6007_AT_kuma_title_LP",
)
ENTRY_UNDERLAY_ONLY = ("ac6007_lev_c002", "ac6007_lev_c002_LP")
ENTRY_MISSING_EFFECTS = (
    "ac6007_AT_kuma_title_add",
    "ac6007_AT_kuma_title_add_LP",
)
ENTRY_FRAMES = 203


def _read_json(path: Path) -> dict[str, Any]:
    return reference.read_json(path)


def _load_plan(path: Path) -> dict[str, Any]:
    raw = _read_json(path)
    if raw.get("schema") != PLAN_OVERLAY_SCHEMA:
        return raw
    if set(raw) != {
        "schema",
        "status",
        "base_plan",
        "event_timing_replacement_manifests",
    } or raw.get("status") != "finite_human_review_candidate":
        raise ValueError("ac6007 route overlay identity differs")
    base_path, snapshot = _bound(
        raw["base_plan"], label="ac6007 inherited route plan", plan_dir=path.parent
    )
    base = _read_json(base_path)
    if base.get("schema") != PLAN_SCHEMA:
        raise ValueError("ac6007 inherited plan schema differs")
    base["event_timing_replacement_manifests"] = raw[
        "event_timing_replacement_manifests"
    ]
    base["_inherited_plan_binding"] = snapshot
    return base


def _bound(
    raw: Mapping[str, Any], *, label: str, plan_dir: Path
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
        raise ValueError("ac6007 native media contract differs")


def _dirinfo_routes(path: Path) -> dict[int, list[str]]:
    grouped: dict[int, list[tuple[int, str, str]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if int(raw["kind"]) != DIRINFO_KIND:
                continue
            grouped.setdefault(int(raw["row_index"]), []).append(
                (
                    int(raw["selector_raw"]),
                    str(raw["scene_name"]),
                    str(raw["route_status"]),
                )
            )
    routes: dict[int, list[str]] = {}
    for row, values in grouped.items():
        values.sort()
        if any(status != "ok" for _, _, status in values):
            raise ValueError(f"DirInfo kind {DIRINFO_KIND} row {row} is unresolved")
        routes[row] = [event for _, event, _ in values]
    expected = {
        0: ["ac6007_001", "ac6007_002", "ac6007_003", "ac6007_004"],
        1: ["ac6007_001", "ac6007_005", "ac6007_006", "ac6007_004"],
        2: ["ac6007_001", "ac6007_002", "ac6007_003", "ac6007_007"],
        3: ["ac6007_001", "ac6007_005", "ac6007_006", "ac6007_008"],
        4: ["ac6007_009", "ac6007_010"],
    }
    if routes != expected:
        raise ValueError("DirInfo kind 174 route set differs")
    return routes


def _validate_uploaded_p19(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if (
        value.get("schema") != "magireco-owner-upload-confirmation-v1"
        or value.get("status") != "uploaded_by_project_owner"
    ):
        raise ValueError("owner-upload attestation identity differs")
    matches = [
        row
        for row in value.get("files", [])
        if isinstance(row, Mapping) and row.get("part") == "P19"
    ]
    if len(matches) != 1 or (
        str(matches[0].get("filename", "")),
        str(matches[0].get("sha256", "")).upper(),
    ) != (
        "P19 菲莉希亚与莎奈驰援彩羽 ac6007__zh.mp4",
        "28D58FED9909D65D73FFFC50F9B771D3DB39739DBFFF80E5C12FE82B136C87A8",
    ):
        raise ValueError("owner-uploaded P19 exact-file binding differs")
    return {
        "part": "P19",
        "filename": str(matches[0]["filename"]),
        "sha256": str(matches[0]["sha256"]).upper(),
        "scope": (
            "uploaded flattened source-family ZH only; validates source-event "
            "playback but does not approve either new complete-entry route"
        ),
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
            label=f"ac6007 source family {key}",
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
        raise ValueError("ac6007 source family identity differs")
    if (
        qa.get("schema") != "magireco-no-bgm-story-family-editions-qa-v1"
        or qa.get("status") != "passed"
        or tuple(qa.get("events", [])) != SOURCE_EVENTS
        or tuple(qa.get("selected_editions", [])) != EDITIONS
    ):
        raise ValueError("ac6007 source family QA identity differs")
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
        raise ValueError("ac6007 source family required QA check is not true")
    timeline: dict[str, dict[str, Any]] = {}
    for raw_row in family.get("timeline", []):
        row = dict(raw_row)
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
            raise ValueError("ac6007 source family timeline differs")
        timeline[event] = row
    if tuple(timeline) != SOURCE_EVENTS:
        raise ValueError("ac6007 source family event order differs")
    reference.validate_video_grid(
        bound["clean_visual_master"],
        expected_frames=int(family["timeline"][-1]["end_frame"]),
        ffprobe=ffprobe,
        label="ac6007 source family clean visual",
    )
    mature._validate_audio_master(bound["no_bgm_audio_master"], ffprobe=ffprobe)
    ja_cues = mature.parse_srt(bound["subtitles_ja"])
    zh_cues = mature.parse_srt(bound["subtitles_zh"])
    if len(ja_cues) != 7 or len(zh_cues) != 7:
        raise ValueError("ac6007 source family subtitle cue count differs")
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

    wanted = {f"ac6007_{index:03d}" for index in range(1, 11)}
    rows: dict[str, dict[str, str]] = {}
    with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            event = str(raw["event_name"])
            if event in wanted:
                rows[event] = dict(raw)
    if set(rows) != wanted:
        raise ValueError("ac6007 audience catalog coverage differs")
    if (
        rows[ENTRY_EVENT]["classification"] != "mixed_full_frame_and_components"
        or rows[ENTRY_EVENT]["dimensions"] != "416x232"
        or int(rows[ENTRY_EVENT]["clip_count"]) != 7
        or int(rows[ENTRY_EVENT]["resolved_clip_count"]) != 5
        or int(rows[ENTRY_EVENT]["full_frame_clip_count"]) != 5
    ):
        raise ValueError("ac6007_001 mixed entry catalog contract differs")
    for event in SOURCE_EVENTS:
        if (
            rows[event]["classification"] != "native_full_frame_only"
            or rows[event]["dimensions"] != "416x232"
        ):
            raise ValueError(f"{event} is no longer native clean-story")
    for event in ("ac6007_007", "ac6007_008", "ac6007_009", "ac6007_010"):
        if rows[event]["classification"] != "component_only":
            raise ValueError(f"{event} is no longer component-only")

    entry_rows: list[dict[str, str]] = []
    with clips_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if raw["event_name"] == ENTRY_EVENT:
                entry_rows.append(dict(raw))
    entry_rows.sort(key=lambda row: (int(row["z2d_order"]), int(row["dgm_order"])))
    expected = [
        (0, 0, "ac6007_lev_c001_MR", 0, 1200, "yes"),
        (0, 1, "ac6007_lev_c002", 1200, 2200, "yes"),
        (0, 2, "ac6007_lev_c002_LP", 2200, 3200, "yes"),
        (1, 0, "ac6007_AT_kuma_title_add", 1200, 6767, "no"),
        (1, 1, "ac6007_AT_kuma_title_add_LP", 1200, 6767, "no"),
        (1, 2, "ac6007_AT_kuma_title", 1200, 3767, "yes"),
        (1, 3, "ac6007_AT_kuma_title_LP", 3767, 6767, "yes"),
    ]
    actual = [
        (
            int(row["z2d_order"]),
            int(row["dgm_order"]),
            row["dgm_name"],
            int(row["event_start_ms"]),
            int(row["event_end_ms"]),
            row["source_exists"],
        )
        for row in entry_rows
    ]
    if actual != expected:
        raise ValueError("ac6007_001 parent presentation intervals differ")

    audio_rows: list[dict[str, str]] = []
    with audio_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if (
                raw.get("root") == FAMILY
                and raw.get("primary_animation") == ENTRY_EVENT
            ):
                audio_rows.append(dict(raw))
    audio_rows.sort(key=lambda row: int(row["parent_sound_order"]))
    planned = plan["entry_event"]["audio_sources"]
    if len(audio_rows) != 2 or len(planned) != 2:
        raise ValueError("ac6007_001 direct parent audio count differs")
    for row, item in zip(audio_rows, planned):
        path = Path(str(item["path"]))
        if (
            int(row["start_ms"]) != 0
            or int(item["start_ms"]) != 0
            or int(row["parent_request_id"]) != int(item["request_id"])
            or int(row["leaf_request_id"]) != int(item["request_id"])
            or int(row["leaf_sound_code"]) != int(item["sound_code"])
            or int(row["duration_ms"]) != int(item["duration_ms"])
            or row["ogg_name"] != path.name
            or row["ogg_duration_match"] != "yes"
            or str(row["subtitle_text"]).strip()
        ):
            raise ValueError("ac6007_001 direct parent scene-SE evidence differs")


def _apply_event_timing_replacements(
    *,
    plan: Mapping[str, Any],
    plan_path: Path,
    source: dict[str, Any],
    snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_replacements = plan.get("event_timing_replacement_manifests")
    if raw_replacements is None:
        return []
    if not isinstance(raw_replacements, Mapping) or set(raw_replacements) != {
        "ac6007_002",
        "ac6007_003",
        "ac6007_005",
        "ac6007_006",
    }:
        raise ValueError("ac6007 timing replacement event set differs")

    corrections: list[dict[str, Any]] = []
    for event, raw in raw_replacements.items():
        path, snapshot = _bound(
            raw,
            label=f"{event} event-global replacement manifest",
            plan_dir=plan_path.parent,
        )
        snapshots.append(snapshot)
        manifest = _read_json(path)
        gates = manifest.get("quality_gates", {})
        if (
            manifest.get("schema") != "magireco-event-production-v3"
            or manifest.get("event") != event
            or gates.get("ready") is not True
            or gates.get("event_global_z2d_timing_ready") is not True
            or gates.get("errors") != []
        ):
            raise ValueError(f"{event} replacement manifest is not event-global READY")
        subtitles = list(manifest.get("subtitles", []))
        if any(row.get("event_global_start_resolved") is not True for row in subtitles):
            raise ValueError(f"{event} replacement subtitle remains child-local")
        subtitles.sort(key=lambda row: (int(row["start_ms"]), int(row["end_ms"])))
        for edition in ("ja", "zh"):
            cues = source["local_cues"][edition][event]
            if len(cues) != len(subtitles):
                raise ValueError(f"{event}/{edition} replacement cue count differs")
            for cue, subtitle in zip(cues, subtitles):
                before = (int(cue["start_ms"]), int(cue["end_ms"]))
                child_before = (
                    int(subtitle.get("child_local_start_ms", subtitle["start_ms"])),
                    int(subtitle.get("child_local_end_ms", subtitle["end_ms"])),
                )
                if before != child_before:
                    raise ValueError(
                        f"{event}/{edition} source cue does not match bound child-local cue"
                    )
                after = (int(subtitle["start_ms"]), int(subtitle["end_ms"]))
                cue["start_ms"], cue["end_ms"] = after
                if after != before:
                    corrections.append(
                        {
                            "event": event,
                            "edition": edition,
                            "request_id": str(subtitle.get("voice_request_id", "")),
                            "before_ms": list(before),
                            "after_ms": list(after),
                        }
                    )
    expected = [
        {
            "event": "ac6007_005",
            "edition": edition,
            "request_id": "4091",
            "before_ms": [33, 3030],
            "after_ms": [33, 2867],
        }
        for edition in ("ja", "zh")
    ]
    if corrections != expected:
        raise ValueError("ac6007 route subtitle correction set differs")
    return corrections


def validate_plan(
    plan: Mapping[str, Any], *, plan_path: Path, ffprobe: str
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "finite_human_review_candidate"
        or plan.get("family") != FAMILY
        or plan.get("audio_profile") != "no_bgm"
        or tuple(plan.get("editions", [])) != EDITIONS
        or tuple(plan.get("included_dirinfo_rows", [])) != INCLUDED_ROWS
        or tuple(int(row["row"]) for row in plan.get("excluded_dirinfo_rows", []))
        != EXCLUDED_ROWS
    ):
        raise ValueError("ac6007 complete clean route plan identity differs")
    _validate_native_media(plan.get("native_media"))
    entry_plan = plan.get("entry_event", {})
    if (
        entry_plan.get("event") != ENTRY_EVENT
        or tuple(entry_plan.get("visible_sequence", [])) != ENTRY_VISIBLE_SEQUENCE
        or tuple(entry_plan.get("underlay_not_linearly_appended", []))
        != ENTRY_UNDERLAY_ONLY
        or tuple(entry_plan.get("excluded_missing_effect_layers", []))
        != ENTRY_MISSING_EFFECTS
        or int(entry_plan.get("output_frames", -1)) != ENTRY_FRAMES
    ):
        raise ValueError("ac6007_001 clean composition policy differs")

    snapshots: list[dict[str, Any]] = [
        {
            "label": "ac6007 complete clean route plan",
            "path": str(plan_path.resolve()),
            "sha256": mature.file_sha256(plan_path),
        }
    ]
    if plan.get("_inherited_plan_binding"):
        snapshots.append(dict(plan["_inherited_plan_binding"]))
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
    timing_corrections = _apply_event_timing_replacements(
        plan=plan,
        plan_path=plan_path,
        source=source,
        snapshots=snapshots,
    )
    _validate_catalogs(plan=plan, plan_path=plan_path, snapshots=snapshots)

    owner_path, snapshot = _bound(
        plan["owner_uploaded_zh_attestation"],
        label="owner-uploaded P19 exact ZH attestation",
        plan_dir=plan_path.parent,
    )
    snapshots.append(snapshot)
    uploaded_p19 = _validate_uploaded_p19(owner_path)
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

    clips: dict[str, dict[str, Any]] = {}
    for raw in entry_plan["clips"]:
        path, snapshot = _bound(
            raw,
            label=f"ac6007_001 official clip {raw['name']}",
            plan_dir=plan_path.parent,
        )
        snapshots.append(snapshot)
        name = str(raw["name"])
        if name in clips:
            raise ValueError("duplicate ac6007_001 clip name")
        frames = int(raw["frames"])
        audit = reference.validate_video_grid(
            path,
            expected_frames=frames,
            ffprobe=ffprobe,
            label=f"ac6007_001 official clip {name}",
        )
        probe = mature.probe(path, ffprobe)
        if mature.media_streams(probe, "audio") or mature.media_streams(
            probe, "subtitle"
        ):
            raise ValueError(f"ac6007_001 clip {name} is not video-only")
        clips[name] = {
            "path": path,
            "frames": frames,
            "sha256": mature.file_sha256(path),
            "audit": audit,
        }
    if set(clips) != set(ENTRY_VISIBLE_SEQUENCE) | set(ENTRY_UNDERLAY_ONLY):
        raise ValueError("ac6007_001 official clip set differs")
    if tuple(clips[name]["frames"] for name in ENTRY_VISIBLE_SEQUENCE) != (
        36,
        77,
        90,
    ):
        raise ValueError("ac6007_001 visible frame intervals differ")
    if tuple(clips[name]["frames"] for name in ENTRY_UNDERLAY_ONLY) != (30, 30):
        raise ValueError("ac6007_001 underlay frame intervals differ")

    audio_sources: list[dict[str, Any]] = []
    for raw in entry_plan["audio_sources"]:
        path, snapshot = _bound(
            raw,
            label=f"ac6007_001 direct parent scene SE {raw['request_id']}",
            plan_dir=plan_path.parent,
        )
        snapshots.append(snapshot)
        probe = mature.probe(path, ffprobe)
        if (
            mature.media_streams(probe, "video")
            or mature.media_streams(probe, "subtitle")
            or len(mature.media_streams(probe, "audio")) != 1
        ):
            raise ValueError("ac6007_001 scene-SE media contract differs")
        audio_sources.append(
            {
                "path": path,
                "sha256": mature.file_sha256(path),
                "request_id": int(raw["request_id"]),
                "sound_code": int(raw["sound_code"]),
                "start_sample": 0,
                "duration_ms": int(raw["duration_ms"]),
            }
        )
    return {
        "title": str(plan["title"]),
        "routes": routes,
        "source": source,
        "layout": layout,
        "font": font_path,
        "entry_clips": clips,
        "entry_audio_sources": audio_sources,
        "snapshots": snapshots,
        "uploaded_p19": uploaded_p19,
        "timing_corrections": timing_corrections,
    }


def _build_entry_asset(
    *,
    resolved: Mapping[str, Any],
    output_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    visual = output_dir / f"{ENTRY_EVENT}.mp4"
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    filters = []
    labels = []
    for index, name in enumerate(ENTRY_VISIBLE_SEQUENCE):
        clip = resolved["entry_clips"][name]
        command.extend(["-i", str(clip["path"])])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={int(clip['frames'])},"
            f"setpts=N/({reference.FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append("".join(labels) + "concat=n=3:v=1:a=0[outv]")
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
            str(ENTRY_FRAMES),
            "-an",
            "-movflags",
            "+faststart",
            str(visual),
        ]
    )
    mature.run(command)
    reference.validate_video_grid(
        visual,
        expected_frames=ENTRY_FRAMES,
        ffprobe=ffprobe,
        label="ac6007_001 clean entry candidate",
    )
    samples = ENTRY_FRAMES * reference.SAMPLES_PER_FRAME
    pcm = output_dir / f"{ENTRY_EVENT}.f32le"
    with pcm.open("wb") as handle:
        handle.truncate(samples * 8)
    return {
        "event": ENTRY_EVENT,
        "frames": ENTRY_FRAMES,
        "samples": samples,
        "visual": visual,
        "pcm": pcm,
        "cues": {"ja": [], "zh": []},
        "source_policy": (
            "parent_interval_clean_selection_36f_lower_scene_then_77f_title_intro_"
            "then_90f_title_loop_missing_additive_effects_excluded"
        ),
        "scene_se_overlays": list(resolved["entry_audio_sources"]),
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
        raise RuntimeError("ac6007 route base PCM byte count differs")
    overlays: list[tuple[int, Mapping[str, Any], str]] = []
    cursor = 0
    for event in events:
        for scene_se in assets[event].get("scene_se_overlays", []):
            overlays.append((cursor + int(scene_se["start_sample"]), scene_se, event))
        cursor += int(assets[event]["samples"])
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
        f"[0:a:0]atrim=end_sample={total_samples},asetpts=PTS-STARTPTS,"
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
        f"atrim=end_sample={total_samples},aresample=48000,"
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
        raise RuntimeError("ac6007 route mixed PCM byte count differs")
    return {
        "sample_count": total_samples,
        "byte_count": total_samples * 8,
        "sha256": mature.file_sha256(output),
        "scene_se_overlays": audit_rows,
    }


def build(
    *, plan_path: Path, output_root: Path, ffmpeg: str, ffprobe: str
) -> tuple[Path, dict[str, Any]]:
    plan = _load_plan(plan_path)
    resolved = validate_plan(plan, plan_path=plan_path, ffprobe=ffprobe)
    destination = output_root.resolve() / FAMILY
    if destination.exists():
        raise FileExistsError(f"versioned ac6007 output exists: {destination}")
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
        assets: dict[str, dict[str, Any]] = {
            ENTRY_EVENT: _build_entry_asset(
                resolved=resolved,
                output_dir=event_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
        }
        for event in SOURCE_EVENTS:
            assets[event] = route_utils._extract_source_event_assets(
                event=event,
                source=resolved["source"],
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
            route_utils._concat_route_visual(
                events=events,
                assets=assets,
                output=clean,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            timeline = route_utils._route_timeline(events, assets)
            pcm_audit = _build_route_pcm(
                events=events,
                assets=assets,
                output=pcm,
                ffmpeg=ffmpeg,
            )
            if pcm_audit["sample_count"] != int(timeline[-1]["end_sample"]):
                raise RuntimeError(f"ac6007 route {row} PCM duration differs")
            cues = route_utils._route_cues(events=events, assets=assets)
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
                    "product_scope": "finite_independent_dirinfo_clean_story_route",
                    "dirinfo_kind": DIRINFO_KIND,
                    "dirinfo_row": row,
                    "ordered_events": events,
                    "entry_clean_composition": {
                        "event": ENTRY_EVENT,
                        "visible_sequence": list(ENTRY_VISIBLE_SEQUENCE),
                        "underlay_not_linearly_appended": list(ENTRY_UNDERLAY_ONLY),
                        "excluded_missing_effect_layers": list(ENTRY_MISSING_EFFECTS),
                        "output_frames": ENTRY_FRAMES,
                    },
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
            raise RuntimeError("ac6007 final audience MP4 count differs")
        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS,
            "automated_spec_qa_passed": True,
            "human_playback_approved": False,
            "publication_approved": False,
            "checks": {
                "dirinfo_kind_174_five_rows_hash_bound_and_exact": True,
                "rows_0_1_built_as_two_independent_routes": True,
                "rows_2_3_4_excluded_as_component_gameplay_effect_routes": True,
                "source_family_hash_bound_and_automated_qa_passed": True,
                "source_p19_exact_zh_owner_uploaded_but_not_inherited": True,
                "four_dialogue_events_event_global_timing_bound": bool(
                    resolved["timing_corrections"]
                ),
                "ac6007_005_graphical_subtitle_end_corrected_to_frame_86": (
                    len(resolved["timing_corrections"]) == 2
                ),
                "entry_parent_intervals_hash_bound": True,
                "entry_visible_sequence_is_not_mechanical_component_concat": True,
                "entry_missing_additive_effect_layers_explicitly_excluded": True,
                "entry_two_direct_parent_scene_se_preserved_with_cross_boundary_tails": True,
                "native_416x232_30fps_no_upscale": True,
                "h264_aac_48khz_stereo": True,
                "exact_frame_and_sample_grid": True,
                "subtitle_round_trip": True,
                "none_ja_zh_audio_packets_and_decoded_pcm_identical_per_route": True,
                "owner_uploaded_p19_source_untouched": True,
            },
            "route_count": len(products),
            "final_mp4_count": len(final_videos),
            "excluded_dirinfo_rows": list(EXCLUDED_ROWS),
            "review_focus": [
                "entry 0-10 seconds, including title transition at 1.200 seconds",
                "entry-to-branch boundary at 6.767 seconds",
                "full route voice, mouth, subtitle, and scene-SE presentation",
            ],
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
                "preserve source-family verified voice/SE and both hash-bound "
                "entry direct parent scene-SE requests with cross-boundary tails"
            ),
            "editions": list(EDITIONS),
            "native_media": plan["native_media"],
            "routes": products,
            "included_dirinfo_rows": list(INCLUDED_ROWS),
            "excluded_dirinfo_rows": plan["excluded_dirinfo_rows"],
            "source_snapshots": resolved["snapshots"],
            "owner_uploaded_source_p19": resolved["uploaded_p19"],
            "event_global_timing_corrections": resolved["timing_corrections"],
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
            "# P19 ac6007 原生 416×232 两条完整入口路线复看\n\n"
            "本批仅含 DirInfo kind 174 rows 0/1 两条互斥 clean-story 路线，"
            "每条均有 none / JA / ZH。请重点检查 0–10 秒、1.200 秒标题"
            "切换、6.767 秒入口转入分支，以及全片对白、张嘴、字幕和场景音。\n\n"
            "入口的两个缺失 additive title 层被明确排除；底层 c002/c002_LP "
            "是同一时段的下层画面，未机械接到片尾。rows 2/3/4 属于 component-only "
            "玩法/效果路线，未纳入干净剧情。旧 P19 已投稿文件保持原样；本批六个"
            "新文件均尚未获得人工播放或投稿批准。\n",
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
        resolved = validate_plan(
            _load_plan(plan_path), plan_path=plan_path, ffprobe=args.ffprobe
        )
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
            {
                "status": qa["status"],
                "output": str(destination),
                "routes": qa["route_count"],
                "final_mp4": qa["final_mp4_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
