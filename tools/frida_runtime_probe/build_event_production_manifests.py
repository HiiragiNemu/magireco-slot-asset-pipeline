#!/usr/bin/env python3
"""Create per-event production manifests from verified static evidence."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-catalog", required=True)
    parser.add_argument("--event-clips", required=True)
    parser.add_argument("--audio-components", required=True)
    parser.add_argument("--voice-catalog", required=True)
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


def main() -> int:
    args = parse_args()
    catalog = read_csv(Path(args.event_catalog))
    clips = read_csv(Path(args.event_clips))
    audio_components = read_csv(Path(args.audio_components))
    voices = read_csv(Path(args.voice_catalog))
    out_dir = Path(args.out_dir)
    event_dir = out_dir / "events"
    event_dir.mkdir(parents=True, exist_ok=True)

    selected = {
        row["event_name"]: row
        for row in catalog
        if row.get("automatic_candidate") == "yes"
        and row.get("has_auto_voice") == "yes"
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
    voices_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in voices:
        event = row.get("event_name", "")
        if (
            event in selected
            and row.get("auto_accepted") == "yes"
            and row.get("ogg_exists") == "yes"
        ):
            voices_by_event[event].append(row)

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

        subtitle_rows: list[dict] = []
        for row in sorted(
            voices_by_event.get(event, []),
            key=lambda item: (
                number(item.get("subtitle_start_ms", "")),
                number(item.get("z2d_order", "")),
            ),
        ):
            request_id = row.get("sound_request_id", "")
            start_ms = number(row.get("voice_start_ms", ""))
            key = (request_id, start_ms)
            if key not in seen_audio:
                seen_audio.add(key)
                path = row.get("ogg_path", "")
                if not path or not Path(path).exists():
                    errors.append(f"missing_voice_audio:{request_id}")
                audio_rows.append(
                    {
                        "source": "subtitle_voice",
                        "request_id": request_id,
                        "code_name": row.get("sound_request_code_name", ""),
                        "ogg_name": row.get("ogg_name", ""),
                        "path": path,
                        "start_ms": start_ms,
                        "duration_ms": number(row.get("sound_duration_ms", "")),
                        "evidence": row.get("match_method", ""),
                    }
                )
            text = row.get("srt_text") or row.get("display_text", "")
            if not text:
                errors.append(f"missing_subtitle_text:{request_id}")
            subtitle_rows.append(
                {
                    "text": text.replace("\\n", "\n"),
                    "start_ms": number(row.get("subtitle_start_ms", "")),
                    "end_ms": number(row.get("subtitle_end_ms", "")),
                    "voice_request_id": request_id,
                    "voice_start_ms": start_ms,
                    "evidence": row.get("match_method", ""),
                }
            )

        if not subtitle_rows:
            errors.append("no_verified_subtitle_voice")
        audio_rows.sort(key=lambda row: (row["start_ms"], row["request_id"]))
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
        if event_clips and number(event_clips[0].get("event_start_ms", "")) > (
            timeline_tolerance_ms
        ):
            errors.append("video_timeline_nonzero_start")
        for previous, current in zip(event_clips, event_clips[1:]):
            delta_ms = number(current.get("event_start_ms", "")) - number(
                previous.get("event_end_ms", "")
            )
            if delta_ms < -timeline_tolerance_ms:
                errors.append("overlapping_video_segments")
            elif delta_ms > timeline_tolerance_ms:
                errors.append("video_timeline_gap")

        render_duration_ms = max(video_duration_ms, duration_ms)
        extension_ms = max(0, render_duration_ms - video_duration_ms)
        last_dgm_name = event_clips[-1].get("dgm_name", "") if event_clips else ""
        if extension_ms <= 0:
            video_extension_policy = "none"
        elif "_lp" in last_dgm_name.lower():
            video_extension_policy = "loop_last_clip"
        elif extension_ms <= short_hold_limit_ms:
            video_extension_policy = "hold_last_frame"
        else:
            video_extension_policy = "unsupported_timeline_overrun"
            errors.append("timeline_exceeds_video_without_loop")

        manifest = {
            "schema": "magireco-event-production-v2",
            "event": event,
            "event_code_hex": event_row.get("code_hex", ""),
            "classification": event_row.get("classification", ""),
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
                "linear_video_timeline": not any(
                    error
                    in {
                        "video_timeline_nonzero_start",
                        "overlapping_video_segments",
                        "video_timeline_gap",
                    }
                    for error in errors
                ),
                "video_extension_supported": (
                    video_extension_policy != "unsupported_timeline_overrun"
                ),
                "errors": sorted(set(errors)),
                "ready": not errors,
            },
        }
        manifest_path = event_dir / f"{event}.json"
        with manifest_path.open("w", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
        summary_rows.append(
            {
                "event_name": event,
                "event_code_hex": event_row.get("code_hex", ""),
                "width": manifest.get("native_dimensions", {}).get("width", ""),
                "height": manifest.get("native_dimensions", {}).get("height", ""),
                "frame_rate": manifest.get("native_frame_rate", ""),
                "clip_count": len(event_clips),
                "base_audio_count": sum(
                    row["source"] == "event_audio_component" for row in audio_rows
                ),
                "voice_count": sum(
                    row["source"] == "subtitle_voice" for row in audio_rows
                ),
                "subtitle_count": len(subtitle_rows),
                "video_duration_ms": video_duration_ms,
                "timeline_duration_ms": duration_ms,
                "render_duration_ms": render_duration_ms,
                "video_extension_policy": video_extension_policy,
                "ready": "yes" if not errors else "no",
                "errors": ";".join(sorted(set(errors))),
                "manifest_path": str(manifest_path),
            }
        )

    fields = [
        "event_name",
        "event_code_hex",
        "width",
        "height",
        "frame_rate",
        "clip_count",
        "base_audio_count",
        "voice_count",
        "subtitle_count",
        "video_duration_ms",
        "timeline_duration_ms",
        "render_duration_ms",
        "video_extension_policy",
        "ready",
        "errors",
        "manifest_path",
    ]
    write_csv(out_dir / "event_production_catalog.csv", summary_rows, fields)
    summary = {
        "events": len(summary_rows),
        "ready_events": sum(row["ready"] == "yes" for row in summary_rows),
        "failed_events": sum(row["ready"] != "yes" for row in summary_rows),
        "clips": sum(int(row["clip_count"]) for row in summary_rows),
        "base_audio_tracks": sum(
            int(row["base_audio_count"]) for row in summary_rows
        ),
        "voice_tracks": sum(int(row["voice_count"]) for row in summary_rows),
        "subtitles": sum(int(row["subtitle_count"]) for row in summary_rows),
    }
    with (out_dir / "event_production_summary.json").open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
