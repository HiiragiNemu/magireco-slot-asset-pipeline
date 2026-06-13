#!/usr/bin/env python3
"""Create per-event production manifests from verified static evidence."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


JAPANESE_TEXT_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff！？…？]"
)
VOICE_SPEAKER_TOKENS = {
    "ai",
    "ari",
    "bur",
    "etc",
    "fel",
    "fer",
    "hom",
    "iro",
    "kae",
    "kan",
    "kuro",
    "kuroe",
    "kyk",
    "kyo",
    "mad",
    "mam",
    "mami",
    "mif",
    "mihu",
    "mit",
    "mita",
    "mobd",
    "mom",
    "nag",
    "nem",
    "nemu",
    "qb",
    "ren",
    "rena",
    "riko",
    "sana",
    "say",
    "sigure",
    "sqb",
    "toka",
    "tou",
    "tsu",
    "tukasa",
    "tukuyo",
    "tur",
    "turk",
    "uwa",
    "ui",
    "yac",
    "yach",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-catalog", required=True)
    parser.add_argument("--event-clips", required=True)
    parser.add_argument("--audio-components", required=True)
    parser.add_argument(
        "--event-sounds",
        required=True,
        help="exact GDB child-frame plus Z2D reqSound callback timeline",
    )
    parser.add_argument(
        "--subtitle-timeline",
        required=True,
        help="verified graphical display text timeline",
    )
    parser.add_argument(
        "--composition-plans",
        default=str(Path(__file__).with_name("composition_plans")),
        help="directory containing explicitly verified per-event composition plans",
    )
    parser.add_argument(
        "--audience-exclusions",
        default=str(Path(__file__).with_name("audience_exclusions.json")),
        help="explicitly reviewed events that are components, not standalone videos",
    )
    parser.add_argument(
        "--voice-subtitle-overrides",
        action="append",
        default=[],
        help="accepted full dialogue recovered for truncated official labels",
    )
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_composition_plans(path: Path) -> dict[str, dict]:
    if not path.is_dir():
        return {}
    plans: dict[str, dict] = {}
    for plan_path in sorted(path.glob("*.json")):
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        event = str(plan.get("event", "")).strip()
        if not event:
            raise ValueError(f"composition plan has no event: {plan_path}")
        if event in plans:
            raise ValueError(f"duplicate composition plan for {event}")
        plan["_source_path"] = str(plan_path.resolve())
        plans[event] = plan
    return plans


def load_audience_exclusions(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events", {})
    if not isinstance(events, dict):
        raise ValueError(f"audience exclusions must contain an events object: {path}")
    return {
        str(event).strip(): str(reason).strip()
        for event, reason in events.items()
        if str(event).strip() and str(reason).strip()
    }


def load_voice_subtitle_overrides(paths: list[Path]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"voice subtitle overrides not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        accepted = payload.get("accepted", {})
        if not isinstance(accepted, dict):
            raise ValueError(
                f"voice subtitle overrides have no accepted object: {path}"
            )
        for request_id, row in accepted.items():
            has_text = isinstance(row, dict) and bool(
                str(row.get("text", "")).strip()
            )
            has_cues = isinstance(row, dict) and any(
                isinstance(cue, dict) and str(cue.get("text", "")).strip()
                for cue in row.get("cues", [])
            )
            if has_text or has_cues:
                merged[str(request_id)] = row
    return merged


def official_voice_label(code_name: str) -> tuple[str, str]:
    parts = [part.strip() for part in (code_name or "").split("_")]
    speaker = next(
        (
            part.casefold()
            for part in parts[1:-1]
            if part.casefold() in VOICE_SPEAKER_TOKENS
        ),
        "",
    )
    if not speaker or len(parts) < 3:
        return "", ""
    text = parts[-1].strip()
    if not text or not JAPANESE_TEXT_RE.search(text):
        return "", ""
    return speaker, text


def main() -> int:
    args = parse_args()
    catalog = read_csv(Path(args.event_catalog))
    clips = read_csv(Path(args.event_clips))
    audio_components = read_csv(Path(args.audio_components))
    event_sounds = read_csv(Path(args.event_sounds))
    subtitle_timeline = read_csv(Path(args.subtitle_timeline))
    composition_plans = load_composition_plans(Path(args.composition_plans))
    audience_exclusions = load_audience_exclusions(
        Path(args.audience_exclusions)
    )
    voice_subtitle_overrides = load_voice_subtitle_overrides(
        [Path(path) for path in args.voice_subtitle_overrides]
    )
    out_dir = Path(args.out_dir)
    event_dir = out_dir / "events"
    event_dir.mkdir(parents=True, exist_ok=True)

    exact_sound_events = {
        row.get("event_name", "")
        for row in event_sounds
        if row.get("ogg_exists") == "yes"
        and row.get("timeline_confidence")
        == "exact_gdb_child_frame_callback_frame_and_official_ogg"
    }
    selected = {
        row["event_name"]: row
        for row in catalog
        if row.get("automatic_candidate") == "yes"
        and row.get("classification") == "native_full_frame_only"
        and row.get("event_name") in exact_sound_events
    }
    clips_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in clips:
        if row.get("event_name") in selected:
            clips_by_event[row["event_name"]].append(row)
    audio_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in audio_components:
        event = row.get("primary_animation", "")
        if event in selected:
            audio_by_event[event].append(row)
    sounds_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in event_sounds:
        event = row.get("event_name", "")
        if (
            event in selected
            and row.get("ogg_exists") == "yes"
            and row.get("timeline_confidence")
            == "exact_gdb_child_frame_callback_frame_and_official_ogg"
        ):
            sounds_by_event[event].append(row)
    subtitles_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in subtitle_timeline:
        event = row.get("event_name", "")
        if (
            event in selected
            and row.get("display_text", "").strip()
            and row.get("timeline_confidence")
            == "exact_gdb_frame_and_official_ogg"
        ):
            subtitles_by_event[event].append(row)

    summary_rows: list[dict] = []
    for event in sorted(selected):
        event_row = selected[event]
        event_clips = sorted(
            clips_by_event.get(event, []),
            key=lambda row: (
                number(row.get("z2d_order", "")),
                number(row.get("event_start_ms", "")),
                number(row.get("dgm_order", "")),
            ),
        )
        dimensions = {
            (number(row.get("width", "")), number(row.get("height", "")))
            for row in event_clips
        }
        frame_rates = {
            row.get("frame_rate", "") for row in event_clips if row.get("frame_rate")
        }
        clip_paths = [
            row.get("target_mp4") or row.get("source_mp4", "")
            for row in event_clips
        ]
        errors: list[str] = []
        audience_exclusion_reason = audience_exclusions.get(event, "")
        if audience_exclusion_reason:
            errors.append("audience_component_only")
        if not event_clips:
            errors.append("no_clips")
        if len(dimensions) != 1:
            errors.append("mixed_dimensions")
        if len(frame_rates) != 1:
            errors.append("mixed_frame_rates")
        if any(row.get("media_class") != "full_frame_landscape" for row in event_clips):
            errors.append("component_media_present")
        if any(not path or not Path(path).exists() for path in clip_paths):
            errors.append("missing_clip")

        audio_rows: list[dict] = []
        seen_audio: set[tuple[str, int]] = set()
        for row in sorted(
            audio_by_event.get(event, []),
            key=lambda item: (
                number(item.get("start_ms", "")),
                number(item.get("parent_sound_order", "")),
                number(item.get("reqdata_index", "")),
            ),
        ):
            request_id = row.get("leaf_request_id", "")
            start_ms = number(row.get("start_ms", ""))
            key = (request_id, start_ms)
            if key in seen_audio:
                continue
            seen_audio.add(key)
            path = row.get("ogg_path", "")
            if not path or not Path(path).exists():
                errors.append(f"missing_base_audio:{request_id}")
            audio_rows.append(
                {
                    "source": "event_audio_component",
                    "request_id": request_id,
                    "code_name": row.get("leaf_code_name", ""),
                    "ogg_name": row.get("ogg_name", ""),
                    "path": path,
                    "start_ms": start_ms,
                    "duration_ms": number(row.get("duration_ms", "")),
                    "evidence": "gdb_event_sound_to_smz_leaf",
                }
            )

        for row in sorted(
            sounds_by_event.get(event, []),
            key=lambda item: (
                number(item.get("audio_start_ms", "")),
                number(item.get("z2d_order", "")),
                number(item.get("callback_index", "")),
            ),
        ):
            request_id = row.get("sound_request_id", "")
            start_ms = number(row.get("audio_start_ms", ""))
            code_name = row.get("sound_code_name", "")
            key = (f"{request_id}:{code_name}", start_ms)
            if key in seen_audio:
                continue
            seen_audio.add(key)
            path = row.get("ogg_path", "")
            if not path or not Path(path).exists():
                errors.append(f"missing_z2d_audio:{request_id}")
            audio_rows.append(
                {
                    "source": "z2d_req_sound",
                    "request_id": request_id,
                    "code_name": code_name,
                    "ogg_name": row.get("ogg_name", ""),
                    "path": path,
                    "start_ms": start_ms,
                    "duration_ms": number(row.get("sound_duration_ms", "")),
                    "z2d_name": row.get("z2d_name", ""),
                    "callback_exec_frame": number(
                        row.get("callback_exec_frame", "")
                    ),
                    "absolute_start_frame": row.get(
                        "absolute_start_frame", ""
                    ),
                    "evidence": row.get("timeline_confidence", ""),
                }
            )

        subtitle_rows: list[dict] = []
        for row in sorted(
            subtitles_by_event.get(event, []),
            key=lambda item: (
                number(item.get("start_ms", "")),
                number(item.get("z2d_order", "")),
            ),
        ):
            request_id = row.get("sound_request_id", "")
            voice_start_ms = number(row.get("audio_start_ms", ""))
            text = row.get("srt_text") or row.get("display_text", "")
            subtitle_rows.append(
                {
                    "text": text.replace("\\n", "\n"),
                    "start_ms": number(row.get("start_ms", "")),
                    "end_ms": number(row.get("effective_end_ms", "")),
                    "voice_request_id": request_id,
                    "voice_start_ms": voice_start_ms,
                    "z2d_name": row.get("z2d_name", ""),
                    "speaker_code": "",
                    "subtitle_source": "graphical_display_text",
                    "evidence": row.get("timeline_confidence", ""),
                }
            )

        audio_rows.sort(key=lambda row: (row["start_ms"], row["request_id"]))
        for audio_row in audio_rows:
            if audio_row["source"] != "z2d_req_sound":
                continue
            already_subtitled = any(
                subtitle.get("voice_request_id") == audio_row["request_id"]
                and abs(
                    number(subtitle.get("voice_start_ms", ""))
                    - audio_row["start_ms"]
                )
                <= 50
                for subtitle in subtitle_rows
            )
            if already_subtitled:
                continue
            override = voice_subtitle_overrides.get(audio_row["request_id"])
            if override:
                override_source = str(
                    override.get(
                        "source",
                        "accepted_voice_subtitle_override",
                    )
                )
                override_cues = override.get("cues", [])
                if isinstance(override_cues, list) and override_cues:
                    for cue in override_cues:
                        if not isinstance(cue, dict):
                            continue
                        cue_text = str(cue.get("text", "")).strip()
                        if not cue_text:
                            continue
                        relative_start = max(0, number(cue.get("start_ms", 0)))
                        relative_end = max(
                            relative_start + 500,
                            number(cue.get("end_ms", 0)),
                        )
                        subtitle_rows.append(
                            {
                                "text": cue_text,
                                "start_ms": audio_row["start_ms"] + relative_start,
                                "end_ms": audio_row["start_ms"] + relative_end,
                                "voice_request_id": audio_row["request_id"],
                                "voice_start_ms": audio_row["start_ms"],
                                "z2d_name": audio_row.get("z2d_name", ""),
                                "speaker_code": str(
                                    override.get("speaker_code", "")
                                ),
                                "subtitle_source": "official_voice_asr_verified",
                                "evidence": override_source,
                            }
                        )
                    continue
                override_text = str(override.get("text", "")).strip()
                if override_text:
                    subtitle_rows.append(
                        {
                            "text": override_text,
                            "start_ms": audio_row["start_ms"],
                            "end_ms": max(
                                audio_row["start_ms"]
                                + audio_row["duration_ms"],
                                audio_row["start_ms"] + 500,
                            ),
                            "voice_request_id": audio_row["request_id"],
                            "voice_start_ms": audio_row["start_ms"],
                            "z2d_name": audio_row.get("z2d_name", ""),
                            "speaker_code": str(
                                override.get("speaker_code", "")
                            ),
                            "subtitle_source": "official_voice_asr_verified",
                            "evidence": override_source,
                        }
                    )
                    continue
            speaker, text = official_voice_label(audio_row["code_name"])
            if not text:
                continue
            subtitle_source = "official_voice_label"
            subtitle_evidence = "official_sound_request_code_name"
            if text.endswith("-"):
                continue
            subtitle_rows.append(
                {
                    "text": text,
                    "start_ms": audio_row["start_ms"],
                    "end_ms": max(
                        audio_row["start_ms"] + audio_row["duration_ms"],
                        audio_row["start_ms"] + 500,
                    ),
                    "voice_request_id": audio_row["request_id"],
                    "voice_start_ms": audio_row["start_ms"],
                    "z2d_name": audio_row.get("z2d_name", ""),
                    "speaker_code": speaker,
                    "subtitle_source": subtitle_source,
                    "evidence": subtitle_evidence,
                }
            )
        subtitle_rows.sort(
            key=lambda row: (
                row["start_ms"],
                row["end_ms"],
                row["subtitle_source"],
            )
        )
        duration_ms = max(
            [number(row.get("event_end_ms", "")) for row in event_clips]
            + [
                row["start_ms"] + row["duration_ms"]
                for row in audio_rows
            ]
            + [row["end_ms"] for row in subtitle_rows]
            + [0]
        )
        video_duration_ms = max(
            [number(row.get("event_end_ms", "")) for row in event_clips] + [0]
        )
        timeline_tolerance_ms = 34
        short_hold_limit_ms = 200
        if event_clips and min(
            number(row.get("event_start_ms", "")) for row in event_clips
        ) > timeline_tolerance_ms:
            errors.append("video_timeline_nonzero_start")
        overlap_count = 0
        gap_count = 0
        for previous, current in zip(event_clips, event_clips[1:]):
            delta_ms = number(current.get("event_start_ms", "")) - number(
                previous.get("event_end_ms", "")
            )
            if delta_ms < -timeline_tolerance_ms:
                overlap_count += 1
            elif delta_ms > timeline_tolerance_ms:
                gap_count += 1

        if overlap_count:
            video_composition_model = "timed_full_frame_layers"
        elif gap_count:
            video_composition_model = "timed_full_frame_with_gaps"
        else:
            video_composition_model = "linear_full_frame_sequence"

        composition_plan = composition_plans.get(event)
        if video_composition_model == "linear_full_frame_sequence":
            composition_resolved = True
            composition_evidence = "non_overlapping_static_timeline"
        elif composition_plan:
            valid_roles = {
                "background",
                "loop_background",
                "screen_overlay",
                "loop_screen_overlay",
            }
            planned_names = {
                str(row.get("dgm_name", ""))
                for row in composition_plan.get("clips", [])
            }
            actual_names = {row.get("dgm_name", "") for row in event_clips}
            if planned_names != actual_names:
                errors.append("composition_plan_clip_mismatch")
                composition_resolved = False
            elif any(
                row.get("role") not in valid_roles
                for row in composition_plan.get("clips", [])
            ):
                errors.append("composition_plan_role_invalid")
                composition_resolved = False
            else:
                composition_resolved = True
            composition_evidence = str(
                composition_plan.get("evidence", "explicit_verified_plan")
            )
        else:
            composition_resolved = False
            composition_evidence = ""
            errors.append("unresolved_video_composition")

        plan_has_loops = bool(composition_plan) and any(
            row.get("role") in {"loop_background", "loop_screen_overlay"}
            for row in composition_plan.get("clips", [])
        )
        if plan_has_loops:
            errors = [
                error
                for error in errors
                if error != "timeline_exceeds_video_without_loop"
            ]

        render_duration_ms = max(video_duration_ms, duration_ms)
        extension_ms = max(0, render_duration_ms - video_duration_ms)
        last_dgm_name = event_clips[-1].get("dgm_name", "") if event_clips else ""
        if extension_ms <= 0:
            video_extension_policy = "none"
        elif "_lp" in last_dgm_name.lower():
            video_extension_policy = "loop_last_clip"
        elif extension_ms <= short_hold_limit_ms:
            video_extension_policy = "hold_last_frame"
        elif plan_has_loops:
            video_extension_policy = "composition_plan_loops"
        else:
            video_extension_policy = "unsupported_timeline_overrun"
            errors.append("timeline_exceeds_video_without_loop")

        manifest = {
            "schema": "magireco-event-production-v3",
            "event": event,
            "event_code_hex": event_row.get("code_hex", ""),
            "classification": event_row.get("classification", ""),
            "audience_exclusion_reason": audience_exclusion_reason,
            "native_dimensions": (
                {"width": next(iter(dimensions))[0], "height": next(iter(dimensions))[1]}
                if len(dimensions) == 1
                else {}
            ),
            "native_frame_rate": next(iter(frame_rates)) if len(frame_rates) == 1 else "",
            "video_duration_ms": video_duration_ms,
            "timeline_duration_ms": duration_ms,
            "render_duration_ms": render_duration_ms,
            "video_extension_policy": video_extension_policy,
            "video_composition_model": video_composition_model,
            "composition_plan": (
                {
                    key: value
                    for key, value in composition_plan.items()
                    if key != "_source_path"
                }
                if composition_plan
                else {}
            ),
            "composition_plan_source": (
                composition_plan.get("_source_path", "")
                if composition_plan
                else ""
            ),
            "overlap_count": overlap_count,
            "gap_count": gap_count,
            "timeline_tolerance_ms": timeline_tolerance_ms,
            "clips": [
                {
                    "order": index,
                    "dgm_name": row.get("dgm_name", ""),
                    "dgm_role": row.get("dgm_role", ""),
                    "path": path,
                    "event_start_ms": number(row.get("event_start_ms", "")),
                    "event_end_ms": number(row.get("event_end_ms", "")),
                    "interval_confidence": row.get("interval_confidence", ""),
                }
                for index, (row, path) in enumerate(zip(event_clips, clip_paths))
            ],
            "audio": audio_rows,
            "subtitles": subtitle_rows,
            "quality_gates": {
                "all_full_frame": all(
                    row.get("media_class") == "full_frame_landscape"
                    for row in event_clips
                ),
                "all_clips_exist": all(
                    path and Path(path).exists() for path in clip_paths
                ),
                "all_audio_exist": all(
                    row["path"] and Path(row["path"]).exists() for row in audio_rows
                ),
                "verified_subtitle_voice_count": len(subtitle_rows),
                "graphical_display_subtitle_count": sum(
                    row["subtitle_source"] == "graphical_display_text"
                    for row in subtitle_rows
                ),
                "official_voice_label_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_label"
                    for row in subtitle_rows
                ),
                "asr_verified_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_asr_verified"
                    for row in subtitle_rows
                ),
                "exact_z2d_req_sound_count": sum(
                    row["source"] == "z2d_req_sound"
                    for row in audio_rows
                ),
                "linear_video_timeline": (
                    video_composition_model == "linear_full_frame_sequence"
                    and "video_timeline_nonzero_start" not in errors
                ),
                "video_composition_model": video_composition_model,
                "composition_resolved": composition_resolved,
                "composition_evidence": composition_evidence,
                "video_extension_supported": (
                    video_extension_policy != "unsupported_timeline_overrun"
                ),
                "audio_timeline_ready": (
                    bool(audio_rows)
                    and all(
                        row["path"] and Path(row["path"]).exists()
                        for row in audio_rows
                    )
                ),
                "errors": sorted(set(errors)),
                "render_ready": not errors and composition_resolved,
                "ready": not errors and composition_resolved,
            },
        }
        manifest_path = event_dir / f"{event}.json"
        with manifest_path.open("w", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
        summary_rows.append(
            {
                "event_name": event,
                "event_code_hex": event_row.get("code_hex", ""),
                "audience_exclusion_reason": audience_exclusion_reason,
                "width": manifest.get("native_dimensions", {}).get("width", ""),
                "height": manifest.get("native_dimensions", {}).get("height", ""),
                "frame_rate": manifest.get("native_frame_rate", ""),
                "clip_count": len(event_clips),
                "base_audio_count": sum(
                    row["source"] == "event_audio_component" for row in audio_rows
                ),
                "z2d_sound_count": sum(
                    row["source"] == "z2d_req_sound" for row in audio_rows
                ),
                "subtitle_count": len(subtitle_rows),
                "graphical_subtitle_count": sum(
                    row["subtitle_source"] == "graphical_display_text"
                    for row in subtitle_rows
                ),
                "voice_label_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_label"
                    for row in subtitle_rows
                ),
                "asr_verified_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_asr_verified"
                    for row in subtitle_rows
                ),
                "video_composition_model": video_composition_model,
                "composition_resolved": (
                    "yes" if composition_resolved else "no"
                ),
                "overlap_count": overlap_count,
                "gap_count": gap_count,
                "video_duration_ms": video_duration_ms,
                "timeline_duration_ms": duration_ms,
                "render_duration_ms": render_duration_ms,
                "video_extension_policy": video_extension_policy,
                "audio_timeline_ready": (
                    "yes"
                    if audio_rows
                    and all(
                        row["path"] and Path(row["path"]).exists()
                        for row in audio_rows
                    )
                    else "no"
                ),
                "render_ready": (
                    "yes" if not errors and composition_resolved else "no"
                ),
                "ready": (
                    "yes" if not errors and composition_resolved else "no"
                ),
                "errors": ";".join(sorted(set(errors))),
                "manifest_path": str(manifest_path),
            }
        )

    fields = [
        "event_name",
        "event_code_hex",
        "audience_exclusion_reason",
        "width",
        "height",
        "frame_rate",
        "clip_count",
        "base_audio_count",
        "z2d_sound_count",
        "subtitle_count",
        "graphical_subtitle_count",
        "voice_label_subtitle_count",
        "asr_verified_subtitle_count",
        "video_composition_model",
        "composition_resolved",
        "overlap_count",
        "gap_count",
        "video_duration_ms",
        "timeline_duration_ms",
        "render_duration_ms",
        "video_extension_policy",
        "audio_timeline_ready",
        "render_ready",
        "ready",
        "errors",
        "manifest_path",
    ]
    write_csv(out_dir / "event_production_catalog.csv", summary_rows, fields)
    summary = {
        "events": len(summary_rows),
        "ready_events": sum(row["ready"] == "yes" for row in summary_rows),
        "failed_events": sum(row["ready"] != "yes" for row in summary_rows),
        "audio_timeline_ready_events": sum(
            row["audio_timeline_ready"] == "yes" for row in summary_rows
        ),
        "composition_resolved_events": sum(
            row["composition_resolved"] == "yes" for row in summary_rows
        ),
        "audience_excluded_events": sum(
            bool(row["audience_exclusion_reason"]) for row in summary_rows
        ),
        "clips": sum(int(row["clip_count"]) for row in summary_rows),
        "base_audio_tracks": sum(
            int(row["base_audio_count"]) for row in summary_rows
        ),
        "z2d_sound_tracks": sum(
            int(row["z2d_sound_count"]) for row in summary_rows
        ),
        "subtitles": sum(int(row["subtitle_count"]) for row in summary_rows),
        "graphical_subtitles": sum(
            int(row["graphical_subtitle_count"]) for row in summary_rows
        ),
        "voice_label_subtitles": sum(
            int(row["voice_label_subtitle_count"]) for row in summary_rows
        ),
        "asr_verified_subtitles": sum(
            int(row["asr_verified_subtitle_count"]) for row in summary_rows
        ),
    }
    with (out_dir / "event_production_summary.json").open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
