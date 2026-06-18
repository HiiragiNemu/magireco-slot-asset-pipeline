#!/usr/bin/env python3
"""Create per-event production manifests from verified static evidence."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
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
GRAPHICAL_SUBTITLE_CONFIDENCE = {
    "exact_gdb_frame_and_official_ogg",
    "exact_gdb_frame_only",
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
    parser.add_argument(
        "--runtime-event-manifests",
        action="append",
        default=[],
        help="directories or event_manifest.json files resolved from official runtime captures",
    )
    parser.add_argument(
        "--ogg-search-root",
        action="append",
        default=[],
        help="optional directory containing official decoded OGG files",
    )
    parser.add_argument("--ffprobe", default="ffprobe")
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


def load_runtime_event_manifests(paths: list[Path]) -> dict[str, dict]:
    manifests: dict[str, dict] = {}
    for path in paths:
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(path.rglob("event_manifest.json"))
        else:
            raise FileNotFoundError(f"runtime event manifest path not found: {path}")
        for candidate in candidates:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            event = str(payload.get("event", "")).strip()
            if not event:
                raise ValueError(f"runtime event manifest has no event: {candidate}")
            payload["_source_path"] = str(candidate.resolve())
            manifests[event] = payload
    return manifests


def probe_runtime_video(path: Path, ffprobe: str, cache: dict[str, dict]) -> dict:
    resolved = str(path.resolve())
    if resolved in cache:
        return cache[resolved]
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(result.stdout)
    video = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "video"
    )
    probed = {
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "frame_rate": str(video.get("r_frame_rate", "")),
        "duration_ms": round(float(payload["format"]["duration"]) * 1000),
    }
    cache[resolved] = probed
    return probed


def infer_ogg_search_roots(
    event_sounds: list[dict[str, str]],
    subtitle_timeline: list[dict[str, str]],
    runtime_event_manifests: dict[str, dict],
    explicit_roots: list[Path],
) -> list[Path]:
    candidates: list[Path] = []
    for path in explicit_roots:
        if path.is_dir():
            candidates.append(path.resolve())
    for row in event_sounds:
        ogg_path = str(row.get("ogg_path", "")).strip()
        if ogg_path:
            path = Path(ogg_path)
            if path.is_file():
                candidates.append(path.parent.resolve())
    for row in subtitle_timeline:
        ogg_path = str(row.get("ogg_path", "")).strip()
        if ogg_path:
            path = Path(ogg_path)
            if path.is_file():
                candidates.append(path.parent.resolve())
    for manifest in runtime_event_manifests.values():
        for row in manifest.get("sound_assets", []):
            ogg_path = str(row.get("ogg_path", "")).strip()
            if ogg_path:
                path = Path(ogg_path)
                if path.is_file():
                    candidates.append(path.parent.resolve())
    roots: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def resolve_ogg_path(
    ogg_name: str,
    raw_path: str,
    search_roots: list[Path],
    cache: dict[str, str],
) -> str:
    path = str(raw_path or "").strip()
    if path and Path(path).is_file():
        return str(Path(path).resolve())
    name = str(ogg_name or "").strip()
    if not name:
        return ""
    if name in cache:
        return cache[name]
    for root in search_roots:
        candidate = root / name
        if candidate.is_file():
            cache[name] = str(candidate.resolve())
            return cache[name]
    cache[name] = ""
    return ""


def normalize_runtime_subtitles(rows: list[dict]) -> list[dict]:
    merged: list[dict] = []
    ordered = sorted(
        rows,
        key=lambda row: (
            number(row.get("start_ms", "")),
            number(row.get("end_ms", "")),
            str(row.get("text", "")),
        ),
    )
    for row in ordered:
        candidate = {
            "text": str(row.get("text", "")).replace("\\n", "\n"),
            "start_ms": number(row.get("start_ms", "")),
            "end_ms": number(row.get("end_ms", "")),
            "voice_start_ms": number(row.get("voice_start_ms", "")),
            "voice_code_name": str(row.get("voice_code_name", "")),
            "ogg_path": str(row.get("ogg_path", "")),
            "mapping_basis": str(row.get("mapping_basis", "")),
        }
        if (
            merged
            and candidate["text"] == merged[-1]["text"]
            and candidate["start_ms"] <= merged[-1]["end_ms"] + 150
        ):
            merged[-1]["end_ms"] = max(merged[-1]["end_ms"], candidate["end_ms"])
            if candidate["voice_code_name"]:
                merged[-1]["voice_code_name"] = ";".join(
                    filter(
                        None,
                        [
                            merged[-1]["voice_code_name"],
                            candidate["voice_code_name"],
                        ],
                    )
                )
            merged[-1]["mapping_basis"] = "runtime_text_merged_adjacent_voice"
            continue
        merged.append(candidate)
    return merged


def runtime_render_duration_ms(runtime_manifest: dict, composition_plan: dict) -> int:
    duration_ms = number(composition_plan.get("duration_ms", ""))
    for row in runtime_manifest.get("sound_assets", []):
        duration_ms = max(
            duration_ms,
            number(row.get("relative_ms", "")) + number(row.get("duration_ms", "")),
        )
    for row in runtime_manifest.get("subtitles", []):
        duration_ms = max(duration_ms, number(row.get("end_ms", "")))
    return duration_ms


def synthesize_runtime_event_clips(
    runtime_manifest: dict,
    composition_plan: dict,
    ffprobe: str,
    media_cache: dict[str, dict],
) -> list[dict[str, str]]:
    runtime_assets = {
        str(row.get("official_name", "")): row
        for row in runtime_manifest.get("video_assets", [])
        if str(row.get("official_name", ""))
    }
    plan_rows = composition_plan.get("clips", [])
    if not plan_rows:
        return []
    video_duration_ms = number(composition_plan.get("duration_ms", ""))
    backgrounds = sorted(
        [row for row in plan_rows if row.get("role") == "background"],
        key=lambda row: number(row.get("start_ms", "")),
    )
    loop_backgrounds = [
        row for row in plan_rows if row.get("role") == "loop_background"
    ]
    next_background_start: dict[str, int] = {}
    boundaries = [
        *(number(row.get("start_ms", "")) for row in backgrounds[1:]),
        *(
            [number(loop_backgrounds[0].get("start_ms", ""))]
            if loop_backgrounds
            else [video_duration_ms]
        ),
    ]
    for row, end_ms in zip(backgrounds, boundaries):
        next_background_start[str(row.get("dgm_name", ""))] = end_ms
    if loop_backgrounds:
        next_background_start[
            str(loop_backgrounds[0].get("dgm_name", ""))
        ] = video_duration_ms

    synthesized: list[dict[str, str]] = []
    for index, row in enumerate(plan_rows):
        dgm_name = str(row.get("dgm_name", ""))
        asset = runtime_assets.get(dgm_name, {})
        clip_path = str(asset.get("target_mp4") or asset.get("source_mp4") or "")
        probe = (
            probe_runtime_video(Path(clip_path), ffprobe, media_cache)
            if clip_path
            else {
                "width": 0,
                "height": 0,
                "frame_rate": "",
                "duration_ms": 0,
            }
        )
        role = str(row.get("role", ""))
        start_ms = number(row.get("start_ms", ""))
        if role in {"background", "loop_background"}:
            end_ms = next_background_start.get(dgm_name, start_ms + probe["duration_ms"])
        elif role == "screen_overlay":
            end_ms = start_ms + probe["duration_ms"]
        elif role == "loop_screen_overlay":
            end_ms = video_duration_ms
        else:
            end_ms = start_ms + probe["duration_ms"]
        synthesized.append(
            {
                "event_name": str(runtime_manifest.get("event", "")),
                "dgm_name": dgm_name,
                "dgm_role": role,
                "width": str(probe["width"]),
                "height": str(probe["height"]),
                "frame_rate": probe["frame_rate"],
                "event_start_ms": str(start_ms),
                "event_end_ms": str(end_ms),
                "interval_confidence": "runtime_verified_composition_plan",
                "media_class": (
                    "full_frame_landscape"
                    if probe["width"] == 416 and probe["height"] == 232
                    else "other_component"
                ),
                "source_mp4": str(asset.get("source_mp4", "")),
                "target_mp4": str(asset.get("target_mp4", "")),
                "z2d_order": str(index),
                "dgm_order": str(index),
            }
        )
    return synthesized


def synthesize_runtime_audio_rows(
    runtime_manifest: dict,
    static_audio_rows: list[dict[str, str]],
) -> list[dict]:
    static_base_keys = {
        (row.get("leaf_request_id", ""), number(row.get("start_ms", "")))
        for row in static_audio_rows
    }
    audio_rows: list[dict] = []
    for row in sorted(
        runtime_manifest.get("sound_assets", []),
        key=lambda item: (
            number(item.get("relative_ms", "")),
            str(item.get("request_id", "")),
        ),
    ):
        request_id = str(row.get("request_id", ""))
        start_ms = number(row.get("relative_ms", ""))
        source = "z2d_req_sound"
        for static_request_id, static_start_ms in static_base_keys:
            if request_id == static_request_id and abs(start_ms - static_start_ms) <= 50:
                source = "event_audio_component"
                break
        audio_rows.append(
            {
                "source": source,
                "request_id": request_id,
                "code_name": str(row.get("code_name", "")),
                "ogg_name": str(row.get("ogg_name", "")),
                "path": str(row.get("ogg_path", "")),
                "start_ms": start_ms,
                "duration_ms": number(row.get("duration_ms", "")),
                "evidence": "official_runtime_capture",
            }
        )
    return audio_rows


def synthesize_runtime_subtitle_rows(runtime_manifest: dict) -> list[dict]:
    subtitle_rows: list[dict] = []
    sound_request_by_code = {
        str(row.get("code_name", "")): str(row.get("request_id", ""))
        for row in runtime_manifest.get("sound_assets", [])
    }
    for row in normalize_runtime_subtitles(runtime_manifest.get("subtitles", [])):
        code_name = str(row.get("voice_code_name", "")).split(";", 1)[0]
        speaker_code, _ = official_voice_label(code_name)
        subtitle_rows.append(
            {
                "text": str(row.get("text", "")),
                "start_ms": number(row.get("start_ms", "")),
                "end_ms": number(row.get("end_ms", "")),
                "voice_request_id": sound_request_by_code.get(code_name, ""),
                "voice_start_ms": number(row.get("voice_start_ms", "")),
                "z2d_name": "",
                "speaker_code": speaker_code,
                "subtitle_source": "official_runtime_capture",
                "evidence": str(row.get("mapping_basis", "official_runtime_capture")),
            }
        )
    return subtitle_rows


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
    runtime_event_manifests = load_runtime_event_manifests(
        [Path(path) for path in args.runtime_event_manifests]
    )
    runtime_media_cache: dict[str, dict] = {}
    ogg_search_roots = infer_ogg_search_roots(
        event_sounds,
        subtitle_timeline,
        runtime_event_manifests,
        [Path(path) for path in args.ogg_search_root],
    )
    ogg_path_cache: dict[str, str] = {}
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
        if (
            (
                row.get("event_name") in exact_sound_events
                and (
                    (
                        row.get("automatic_candidate") == "yes"
                        and row.get("classification") == "native_full_frame_only"
                    )
                    or row.get("event_name") in composition_plans
                )
            )
            or (
                row.get("event_name") in runtime_event_manifests
                and row.get("event_name") in composition_plans
            )
        )
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
            and row.get("timeline_confidence") in GRAPHICAL_SUBTITLE_CONFIDENCE
        ):
            subtitles_by_event[event].append(row)

    summary_rows: list[dict] = []
    for event in sorted(selected):
        event_row = selected[event]
        composition_plan = composition_plans.get(event)
        runtime_manifest = runtime_event_manifests.get(event)
        if runtime_manifest and composition_plan:
            event_clips = synthesize_runtime_event_clips(
                runtime_manifest,
                composition_plan,
                args.ffprobe,
                runtime_media_cache,
            )
        else:
            all_event_clips = sorted(
                clips_by_event.get(event, []),
                key=lambda row: (
                    number(row.get("z2d_order", "")),
                    number(row.get("event_start_ms", "")),
                    number(row.get("dgm_order", "")),
                ),
            )
            if composition_plan and composition_plan.get("clips"):
                planned_names = {
                    str(row.get("dgm_name", ""))
                    for row in composition_plan.get("clips", [])
                }
                event_clips = [
                    row
                    for row in all_event_clips
                    if row.get("dgm_name", "") in planned_names
                ]
            else:
                event_clips = all_event_clips
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
        plan_native_dimensions = (
            composition_plan.get("native_dimensions", {})
            if composition_plan
            else {}
        )
        native_width = number(plan_native_dimensions.get("width", ""))
        native_height = number(plan_native_dimensions.get("height", ""))
        has_plan_native_dimensions = native_width > 0 and native_height > 0
        if len(dimensions) != 1 and not has_plan_native_dimensions:
            errors.append("mixed_dimensions")
        if len(frame_rates) != 1:
            errors.append("mixed_frame_rates")
        if (
            not composition_plan
            and any(
                row.get("media_class") != "full_frame_landscape"
                for row in event_clips
            )
        ):
            errors.append("component_media_present")
        if any(not path or not Path(path).exists() for path in clip_paths):
            errors.append("missing_clip")

        if runtime_manifest:
            audio_rows = synthesize_runtime_audio_rows(
                runtime_manifest,
                audio_by_event.get(event, []),
            )
            subtitle_rows = synthesize_runtime_subtitle_rows(runtime_manifest)
        else:
            audio_rows = []
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
                path = resolve_ogg_path(
                    row.get("ogg_name", ""),
                    row.get("ogg_path", ""),
                    ogg_search_roots,
                    ogg_path_cache,
                )
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
                path = resolve_ogg_path(
                    row.get("ogg_name", ""),
                    row.get("ogg_path", ""),
                    ogg_search_roots,
                    ogg_path_cache,
                )
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

            subtitle_rows = []
            for row in sorted(
                subtitles_by_event.get(event, []),
                key=lambda item: (
                    number(item.get("start_ms") or item.get("subtitle_start_ms", "")),
                    number(item.get("z2d_order", "")),
                ),
            ):
                request_id = row.get("sound_request_id", "")
                voice_start_ms = number(
                    row.get("audio_start_ms") or row.get("voice_start_ms", "")
                )
                text = row.get("srt_text") or row.get("display_text", "")
                subtitle_start_ms = number(
                    row.get("start_ms") or row.get("subtitle_start_ms", "")
                )
                subtitle_end_ms = number(
                    row.get("effective_end_ms") or row.get("subtitle_end_ms", "")
                )
                subtitle_rows.append(
                    {
                        "text": text.replace("\\n", "\n"),
                        "start_ms": subtitle_start_ms,
                        "end_ms": subtitle_end_ms,
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
                plan_rows = {
                    str(row.get("dgm_name", "")): row
                    for row in composition_plan.get("clips", [])
                }
                for clip in event_clips:
                    plan_row = plan_rows.get(clip.get("dgm_name", ""), {})
                    role = plan_row.get("role")
                    clip_dimensions = (
                        number(clip.get("width", "")),
                        number(clip.get("height", "")),
                    )
                    if (
                        role in {"background", "loop_background"}
                        and has_plan_native_dimensions
                        and clip_dimensions != (native_width, native_height)
                    ):
                        errors.append("composition_background_dimension_mismatch")
                        composition_resolved = False
                    if (
                        role in {"screen_overlay", "loop_screen_overlay"}
                        and has_plan_native_dimensions
                        and clip_dimensions != (native_width, native_height)
                        and not plan_row.get("scale_to_native")
                    ):
                        errors.append("composition_overlay_scale_not_verified")
                        composition_resolved = False
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
        verified_extension_policy = (
            str(composition_plan.get("extension_policy", ""))
            if composition_plan
            else ""
        )
        if verified_extension_policy not in {"", "hold_last_frame"}:
            errors.append("composition_plan_extension_policy_invalid")
        if extension_ms <= 0:
            video_extension_policy = "none"
        elif "_lp" in last_dgm_name.lower():
            video_extension_policy = "loop_last_clip"
        elif verified_extension_policy == "hold_last_frame":
            video_extension_policy = "hold_last_frame"
            errors = [
                error
                for error in errors
                if error != "timeline_exceeds_video_without_loop"
            ]
        elif extension_ms <= short_hold_limit_ms:
            video_extension_policy = "hold_last_frame"
        elif plan_has_loops:
            video_extension_policy = "composition_plan_loops"
        else:
            video_extension_policy = "unsupported_timeline_overrun"
            errors.append("timeline_exceeds_video_without_loop")

        verified_native_composite = bool(composition_plan) and (
            len(dimensions) != 1
            or any(
                row.get("media_class") != "full_frame_landscape"
                for row in event_clips
            )
        )
        manifest = {
            "schema": "magireco-event-production-v3",
            "event": event,
            "event_code_hex": event_row.get("code_hex", ""),
            "classification": (
                "verified_native_composite"
                if verified_native_composite
                else event_row.get("classification", "")
            ),
            "audience_exclusion_reason": audience_exclusion_reason,
            "native_dimensions": (
                {"width": native_width, "height": native_height}
                if has_plan_native_dimensions
                else (
                    {
                        "width": next(iter(dimensions))[0],
                        "height": next(iter(dimensions))[1],
                    }
                    if len(dimensions) == 1
                    else {}
                )
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
