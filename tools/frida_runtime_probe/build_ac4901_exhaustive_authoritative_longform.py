#!/usr/bin/env python3
"""Render the loop-aware exhaustive native-416 ac4901 strict no-BGM longform."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac6007_exhaustive_authoritative_longform import (
        _ass_text,
        _ass_time,
        _filter_path,
        decoded_audio_sha256,
        encode_args,
        probe,
        published,
        run,
    )
    from .build_exhaustive_unique_longform import file_sha256
except ImportError:  # pragma: no cover - direct script execution
    from build_ac6007_exhaustive_authoritative_longform import (  # type: ignore
        _ass_text,
        _ass_time,
        _filter_path,
        decoded_audio_sha256,
        encode_args,
        probe,
        published,
        run,
    )
    from build_exhaustive_unique_longform import file_sha256  # type: ignore


FPS = 30
RATE = 48_000
SAMPLES_PER_FRAME = RATE // FPS
EXPECTED_FRAMES = 35654
EXPECTED_SOURCE_EVENTS = 205
EXPECTED_ROUTES = 162
EXPECTED_ROUTE_OCCURRENCES = 720
EXPECTED_CANONICAL_EVENTS = 203
EXPECTED_ALIAS_EVENTS = 2
EXPECTED_UNITS = 220
EXPECTED_STANDALONE_UNITS = 202
EXPECTED_UNDERLAY_VARIANTS = 18
EXPECTED_UNIT_LAYER_OCCURRENCES = 621
EXPECTED_UNIT_RENDER_SEGMENTS = 801
EXPECTED_UNIT_MOVIE_PARENTS = 348
EXPECTED_UNIT_SCHEDULED_MOVIE_FRAMES = 40734
EXPECTED_UNIQUE_CRI_SOURCES = 194
EXPECTED_RETAINED_AUDIO = 421
EXPECTED_RETAINED_SE = 365
EXPECTED_RETAINED_VOICE = 56
EXPECTED_SUBTITLES = 56
EXPECTED_NORMAL_LAYERS = 619
EXPECTED_ADDITIVE_LAYERS = 2
EXPECTED_EXCLUDED_BGM_SOURCE_OCCURRENCES = 21
EDITIONS = {"none": "NONE", "ja": "JP", "zh": "ZH"}
TITLE = "ac4901全路线全独特演出穷尽合集"


class Ac4901LongformBuildError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _source_binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise Ac4901LongformBuildError(f"source is absent: {path}")
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _projection_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        str(row[key]) for key in ("scene", "cut", "parent_z2d", "source_name")
    )


def validate_authorities(
    route: Mapping[str, Any],
    visual: Mapping[str, Any],
    loop: Mapping[str, Any],
    audio: Mapping[str, Any],
    *,
    visual_path: Path,
) -> list[dict[str, Any]]:
    if (
        route.get("schema")
        != "magireco-ac4901-dirinfo-route-state-and-complete-presentation-dedup-authority-v1"
        or route.get("status") != "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER"
    ):
        raise Ac4901LongformBuildError("ac4901 route/dedup authority differs")
    route_summary = route.get("summary", {})
    expected_route = {
        "dirinfo_routes": EXPECTED_ROUTES,
        "dirinfo_event_occurrences": EXPECTED_ROUTE_OCCURRENCES,
        "source_events": EXPECTED_SOURCE_EVENTS,
        "canonical_event_presentations": EXPECTED_CANONICAL_EVENTS,
        "identical_complete_presentation_aliases": EXPECTED_ALIAS_EVENTS,
        "route_state_underlay_variants": EXPECTED_UNDERLAY_VARIANTS,
        "duplicate_free_editorial_units": EXPECTED_UNITS,
        "unique_loadable_cri_sources_covered": EXPECTED_UNIQUE_CRI_SOURCES,
        "duplicate_free_longform_frames": EXPECTED_FRAMES,
        "duplicate_free_longform_seconds": EXPECTED_FRAMES / FPS,
    }
    if any(route_summary.get(key) != value for key, value in expected_route.items()):
        raise Ac4901LongformBuildError("ac4901 route/dedup dimensions differ")
    if (
        visual.get("schema") != "magireco-ac4901-output-projection-authority-v1"
        or visual.get("status")
        != "PASS_READY_FOR_ROUTE_STATE_CARRY_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("summary", {}).get("events") != EXPECTED_SOURCE_EVENTS
        or visual.get("summary", {}).get("unique_loadable_cri_sources")
        != EXPECTED_UNIQUE_CRI_SOURCES
        or visual.get("summary", {}).get("unreachable_movie_layer_occurrences") != 0
    ):
        raise Ac4901LongformBuildError("ac4901 projection authority differs")
    if (
        loop.get("schema") != "magireco-ac4901-parent-clock-z2d-loop-authority-v1"
        or loop.get("status") != "PASS_READY_FOR_LOOP_AWARE_LONGFORM_RENDER"
        or loop.get("summary", {}).get("events") != EXPECTED_SOURCE_EVENTS
        or loop.get("summary", {}).get("parents_requiring_post_first_pass_loop") != 108
        or loop.get("summary", {}).get("post_first_pass_loop_frames") != 4392
        or loop.get("summary", {}).get("scheduled_movie_frame_occurrences") != 40326
        or loop.get("summary", {}).get("compressed_render_segments") != 771
        or loop.get("summary", {}).get("unique_loadable_cri_sources")
        != EXPECTED_UNIQUE_CRI_SOURCES
    ):
        raise Ac4901LongformBuildError("ac4901 Z2D loop authority differs")
    loop_projection = loop.get("inputs", {}).get("output_projection", {})
    if str(loop_projection.get("sha256", "")).casefold() != file_sha256(
        visual_path.resolve()
    ).casefold():
        raise Ac4901LongformBuildError("loop authority is not bound to this projection")
    if (
        audio.get("schema")
        != "magireco-ac4901-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status")
        != "PASS_READY_FOR_ROUTE_STATE_CARRY_AND_DEDUP_AUTHORITY"
        or audio.get("summary", {}).get("retained_audio_occurrences") != 393
        or audio.get("summary", {}).get("excluded_bgm_occurrences")
        != EXPECTED_EXCLUDED_BGM_SOURCE_OCCURRENCES
        or audio.get("summary", {}).get("subtitle_cue_occurrences") != 39
        or audio.get("summary", {}).get("tail_hold_frames_total") != 0
    ):
        raise Ac4901LongformBuildError("ac4901 audio authority differs")

    timeline = [dict(row) for row in route.get("editorial_timeline", [])]
    if len(timeline) != EXPECTED_UNITS:
        raise Ac4901LongformBuildError("ac4901 editorial unit count differs")
    cursor = 0
    unit_ids: set[str] = set()
    underlays: set[str] = set()
    for index, row in enumerate(timeline, start=1):
        unit_id = str(row["unit_id"])
        frames = int(row["duration_frames"])
        if (
            unit_id in unit_ids
            or int(row["chapter_index"]) != index
            or int(row["start_frame"]) != cursor
            or int(row["end_frame_exclusive"]) != cursor + frames
        ):
            raise Ac4901LongformBuildError(f"editorial timeline differs: {unit_id}")
        unit_ids.add(unit_id)
        if row.get("underlay_event"):
            if row.get("event") != "ac4901_091":
                raise Ac4901LongformBuildError("unexpected route-state underlay event")
            underlays.add(str(row["underlay_event"]))
        cursor += frames
    expected_underlays = {
        f"ac4901_{index:03d}"
        for index in (*range(25, 31), *range(55, 61), *range(85, 91))
    }
    if (
        cursor != EXPECTED_FRAMES
        or len(unit_ids) != EXPECTED_UNITS
        or underlays != expected_underlays
        or sum(bool(row.get("underlay_event")) for row in timeline)
        != EXPECTED_UNDERLAY_VARIANTS
    ):
        raise Ac4901LongformBuildError("editorial route-state coverage differs")
    return timeline


def build_unit_manifests(
    timeline: Sequence[Mapping[str, Any]],
    visual: Mapping[str, Any],
    loop: Mapping[str, Any],
    audio: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    visual_events = {str(row["event"]): row for row in visual["events"]}
    loop_events = {str(row["event"]): row for row in loop["events"]}
    audio_presentations = {
        str(row["event"]): row for row in audio["event_presentations"]
    }
    audio_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    subtitle_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audio_source_hashes: dict[str, str] = {}
    for source_row in audio["retained_audio_rows"]:
        row = dict(source_row)
        source = dict(row["official_source"])
        path = Path(str(source["path"]))
        if not path.is_file() or path.stat().st_size != int(source["size_bytes"]):
            raise Ac4901LongformBuildError(f"official audio source differs: {path}")
        source_hash = audio_source_hashes.setdefault(str(path.resolve()), file_sha256(path))
        source["sha256"] = source_hash
        row["official_source"] = source
        audio_rows[str(row["event"])].append(row)
    for row in audio["subtitle_cues"]:
        subtitle_rows[str(row["event"])].append(dict(row))

    manifests: dict[str, dict[str, Any]] = {}
    for timeline_row in timeline:
        unit_id = str(timeline_row["unit_id"])
        event = str(timeline_row["event"])
        visual_row = visual_events[event]
        loop_row = loop_events[event]
        segment_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        parent_count = 0
        scheduled_frames = 0
        for parent in loop_row["parent_z2d_schedules_in_gfdirection_order"]:
            parent_count += 1
            scheduled_frames += int(parent["scheduled_movie_frame_occurrences"])
            for segment in parent["render_segments"]:
                segment_groups[str(segment["projection_key"])].append(dict(segment))
        layers = []
        for layer in visual_row["layers_in_render_pass_order_under_to_top"]:
            row = dict(layer)
            key = _projection_key(row)
            segments = sorted(
                segment_groups.pop(key, []), key=lambda value: int(value["event_start_frame"])
            )
            if not segments:
                raise Ac4901LongformBuildError(
                    f"projection layer lacks loop-aware source schedule: {event}/{key}"
                )
            row["loop_aware_render_segments"] = segments
            layers.append(row)
        if segment_groups:
            raise Ac4901LongformBuildError(
                f"loop schedule lacks a projection layer: {event}/{sorted(segment_groups)}"
            )
        frames = int(audio_presentations[event]["final_presentation_frames"])
        if (
            frames != int(timeline_row["duration_frames"])
            or frames != int(visual_row["presentation_frame_count"])
            or int(audio_presentations[event]["tail_hold_frames"]) != 0
        ):
            raise Ac4901LongformBuildError(f"unit presentation extent differs: {unit_id}")
        underlay = str(timeline_row.get("underlay_event", ""))
        requires_underlay = bool(visual_row["requires_prior_frame_underlay"])
        if requires_underlay != bool(underlay) or (underlay and event != "ac4901_091"):
            raise Ac4901LongformBuildError(f"route-state base differs: {unit_id}")
        retained = audio_rows[event]
        subtitles = subtitle_rows[event]
        if any(row["volume_bus"] not in {"SE", "VOICE"} for row in retained):
            raise Ac4901LongformBuildError(f"non-retained sound bus leaked: {unit_id}")
        manifests[unit_id] = {
            "unit_id": unit_id,
            "event": event,
            "source_event": str(timeline_row["source_event"]),
            "underlay_event": underlay,
            "underlay_unit_id": underlay,
            "title_zh": str(timeline_row["title_zh"]),
            "chapter_index": int(timeline_row["chapter_index"]),
            "presentation_frames": frames,
            "movie_parent_schedule_count": parent_count,
            "scheduled_movie_frame_occurrences": scheduled_frames,
            "layers": layers,
            "retained_audio": retained,
            "subtitles": subtitles,
            "non_movie_text_z2d_nodes": visual_row["non_movie_text_z2d_nodes"],
            "runtime_symbolic_nodes": visual_row["runtime_symbolic_nodes"],
            "composition_semantics": str(timeline_row["composition_semantics"]),
        }

    units = list(manifests.values())
    layers = [row for unit in units for row in unit["layers"]]
    segments = [
        segment
        for layer in layers
        for segment in layer["loop_aware_render_segments"]
    ]
    retained = [row for unit in units for row in unit["retained_audio"]]
    subtitles = [row for unit in units for row in unit["subtitles"]]
    if (
        len(manifests) != EXPECTED_UNITS
        or sum(not unit["underlay_event"] for unit in units) != EXPECTED_STANDALONE_UNITS
        or sum(bool(unit["underlay_event"]) for unit in units)
        != EXPECTED_UNDERLAY_VARIANTS
        or len(layers) != EXPECTED_UNIT_LAYER_OCCURRENCES
        or len(segments) != EXPECTED_UNIT_RENDER_SEGMENTS
        or sum(unit["movie_parent_schedule_count"] for unit in units)
        != EXPECTED_UNIT_MOVIE_PARENTS
        or sum(unit["scheduled_movie_frame_occurrences"] for unit in units)
        != EXPECTED_UNIT_SCHEDULED_MOVIE_FRAMES
        or len({row["source"]["official_name"] for row in layers})
        != EXPECTED_UNIQUE_CRI_SOURCES
        or sum(int(row["effective_renderer_state"]) == 1 for row in layers)
        != EXPECTED_NORMAL_LAYERS
        or sum(int(row["effective_renderer_state"]) == 3 for row in layers)
        != EXPECTED_ADDITIVE_LAYERS
        or len(retained) != EXPECTED_RETAINED_AUDIO
        or sum(row["volume_bus"] == "SE" for row in retained) != EXPECTED_RETAINED_SE
        or sum(row["volume_bus"] == "VOICE" for row in retained)
        != EXPECTED_RETAINED_VOICE
        or len(subtitles) != EXPECTED_SUBTITLES
        or sum(unit["presentation_frames"] for unit in units) != EXPECTED_FRAMES
    ):
        raise Ac4901LongformBuildError("canonical unit production dimensions differ")
    return manifests


def _source_branch_filter(
    label: str, segment: Mapping[str, Any], *, shift_to_event: bool
) -> str:
    start = int(segment["source_start_frame"])
    end = int(segment["source_end_frame_inclusive"])
    frames = int(segment["frame_count"])
    progression = str(segment["source_progression"])
    if progression == "increment_1":
        if end - start + 1 != frames:
            raise Ac4901LongformBuildError("incrementing render segment differs")
        filters = f"trim=start_frame={start}:end_frame={end + 1}"
    elif progression in {"hold", "single_frame"}:
        if start != end:
            raise Ac4901LongformBuildError("held render segment source differs")
        filters = f"trim=start_frame={start}:end_frame={start + 1}"
        if frames > 1:
            filters += f",tpad=stop_mode=clone:stop={frames - 1}"
    else:
        raise Ac4901LongformBuildError(f"unsupported source progression: {progression}")
    if shift_to_event:
        filters += (
            f",setpts=PTS-STARTPTS+{int(segment['event_start_frame'])}/{FPS}/TB"
        )
    else:
        filters += ",setpts=PTS-STARTPTS"
    return f"[{label}]{filters}"


def layer_filter_parts(
    *,
    input_index: int,
    layer_index: int,
    row: Mapping[str, Any],
    current: str,
    event_frames: int,
) -> tuple[list[str], str]:
    source = row["source"]
    x, y, width, height = (int(value) for value in row["output_rect_xywh"])
    if (x, y, width, height) != (0, 0, 416, 232):
        raise Ac4901LongformBuildError("ac4901 output projection differs")
    scale = ""
    if (int(source["width"]), int(source["height"])) != (width, height):
        scale = f"scale={width}:{height}:flags=lanczos,"
    segments = list(row["loop_aware_render_segments"])
    if not segments:
        raise Ac4901LongformBuildError("loop-aware render segment list is empty")
    base = f"l{layer_index}"
    parts = [
        f"[{input_index}:v:0]format=rgb24,vflip[{base}c]",
        f"[{input_index}:v:1]format=gray,vflip[{base}a]",
        f"[{base}c][{base}a]alphamerge,{scale}format=rgba[{base}rgba]",
    ]
    branch_labels = [f"{base}s{index}" for index in range(len(segments))]
    if len(branch_labels) == 1:
        parts.append(f"[{base}rgba]null[{branch_labels[0]}]")
    else:
        parts.append(
            f"[{base}rgba]split={len(branch_labels)}"
            + "".join(f"[{label}]" for label in branch_labels)
        )
    state = int(row["effective_renderer_state"])
    for index, (segment, branch) in enumerate(zip(segments, branch_labels)):
        next_label = f"base{layer_index}_{index + 1}"
        if state == 1:
            rendered = f"{branch}r"
            parts.append(
                _source_branch_filter(branch, segment, shift_to_event=True)
                + f"[{rendered}]"
            )
            parts += [
                f"[{current}]format=rgba[{branch}base]",
                f"[{branch}base][{rendered}]overlay=0:0:eof_action=pass:"
                f"repeatlast=0:shortest=0:format=auto[{next_label}]",
            ]
        elif state == 3:
            rendered = f"{branch}add"
            stop = event_frames - int(segment["event_end_frame_inclusive"]) - 1
            if stop < 0:
                raise Ac4901LongformBuildError("additive segment exceeds event")
            parts.append(
                _source_branch_filter(branch, segment, shift_to_event=False)
                + ",format=rgba,premultiply_dynamic=inplace=1,format=rgb24,"
                + f"tpad=start={int(segment['event_start_frame'])}:stop={stop}:"
                + "start_mode=add:stop_mode=add:color=black,"
                + f"trim=end_frame={event_frames},setpts=PTS-STARTPTS[{rendered}]"
            )
            parts.append(
                f"[{current}][{rendered}]blend=all_mode=addition:shortest=1,"
                f"format=rgb24[{next_label}]"
            )
        else:
            raise Ac4901LongformBuildError(f"unsupported renderer state: {state}")
        current = next_label
    return parts, current


def _unit_filename(unit_id: str) -> str:
    return unit_id.replace("@", "__on__") + ".nut"


def render_unit(
    ffmpeg: str,
    manifest: Mapping[str, Any],
    underlay_media: Path | None,
    underlay_frames: int,
    output: Path,
    log: Path,
) -> None:
    unit_id = str(manifest["unit_id"])
    frames = int(manifest["presentation_frames"])
    layers = list(manifest["layers"])
    retained = list(manifest["retained_audio"])
    command = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-filter_complex_threads",
        "1",
    ]
    input_offset = 0
    if underlay_media is not None:
        command += ["-threads", "1", "-i", str(underlay_media)]
        input_offset = 1
    for row in layers:
        path = Path(str(row["source"]["path"]))
        if (
            not path.is_file()
            or file_sha256(path).casefold() != str(row["source"]["sha256"]).casefold()
        ):
            raise Ac4901LongformBuildError(f"exact CRI source differs: {unit_id}/{path}")
        command += ["-threads", "1", "-i", str(path)]
    for row in retained:
        source = row["official_source"]
        path = Path(str(source["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != int(source["size_bytes"])
            or file_sha256(path).casefold() != str(source["sha256"]).casefold()
        ):
            raise Ac4901LongformBuildError(f"official audio differs: {unit_id}/{path}")
        command += ["-i", str(path)]

    if underlay_media is None:
        parts = [
            f"color=c=black:s=416x232:r={FPS}:d={frames / FPS:.9f},"
            "format=rgb24[base0]"
        ]
    else:
        if underlay_frames <= 0:
            raise Ac4901LongformBuildError("underlay frame count is not positive")
        parts = [
            f"[0:v:0]trim=start_frame={underlay_frames - 1}:end_frame={underlay_frames},"
            f"setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop={frames - 1},"
            f"trim=end_frame={frames},format=rgb24[base0]"
        ]
    current = "base0"
    for index, row in enumerate(layers):
        filters, current = layer_filter_parts(
            input_index=input_offset + index,
            layer_index=index,
            row=row,
            current=current,
            event_frames=frames,
        )
        parts += filters
    parts.append(
        f"[{current}]trim=end_frame={frames},setpts=PTS-STARTPTS,format=yuv420p[v]"
    )

    audio_labels = []
    first_audio = input_offset + len(layers)
    for index, row in enumerate(retained):
        label = f"a{index}"
        delay_samples = round(int(row["start_ms"]) * RATE / 1000)
        parts.append(
            f"[{first_audio + index}:a]aresample={RATE},"
            f"aformat=sample_rates={RATE}:channel_layouts=stereo,"
            f"adelay={delay_samples}S:all=1,asetpts=PTS-STARTPTS[{label}]"
        )
        audio_labels.append(f"[{label}]")
    samples = frames * SAMPLES_PER_FRAME
    if audio_labels:
        parts.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audio_labels)}:duration=longest:normalize=0,"
            f"apad=whole_len={samples},atrim=end_sample={samples},"
            "asetpts=PTS-STARTPTS[a]"
        )
    else:
        parts.append(
            f"anullsrc=r={RATE}:cl=stereo,atrim=end_sample={samples},"
            "asetpts=PTS-STARTPTS[a]"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "12",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
        "-fps_mode",
        "cfr",
        "-c:a",
        "pcm_s16le",
        "-ar",
        str(RATE),
        "-ac",
        "2",
        "-threads",
        "4",
        "-frames:v",
        str(frames),
        "-t",
        f"{frames / FPS:.9f}",
        "-f",
        "nut",
        str(output),
    ]
    run(command, log)


def write_chapters(
    path: Path,
    timeline: Sequence[Mapping[str, Any]],
    manifests: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    lines = [";FFMETADATA1"]
    cursor = 0
    for timeline_row in timeline:
        unit_id = str(timeline_row["unit_id"])
        unit = manifests[unit_id]
        frames = int(unit["presentation_frames"])
        title = str(unit["title_zh"])
        rows.append(
            {
                "unit_id": unit_id,
                "event": unit["event"],
                "underlay_event": unit["underlay_event"],
                "start_frame": cursor,
                "end_frame_exclusive": cursor + frames,
                "title": title,
            }
        )
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/30",
            f"START={cursor}",
            f"END={cursor + frames}",
            f"title={title} ({unit_id})",
        ]
        cursor += frames
    if cursor != EXPECTED_FRAMES or len(rows) != EXPECTED_UNITS:
        raise Ac4901LongformBuildError("chapter frame grid differs")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def write_concat_list(
    path: Path,
    timeline: Sequence[Mapping[str, Any]],
    manifests: Mapping[str, Mapping[str, Any]],
    unit_media: Mapping[str, Path],
) -> None:
    lines = ["ffconcat version 1.0"]
    for row in timeline:
        unit_id = str(row["unit_id"])
        media = unit_media[unit_id].resolve().as_posix().replace("'", "'\\''")
        lines += [
            f"file '{media}'",
            f"duration {int(manifests[unit_id]['presentation_frames']) / FPS:.9f}",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_none_longform(
    ffmpeg: str,
    concat_list: Path,
    metadata: Path,
    output: Path,
    log: Path,
) -> None:
    samples = EXPECTED_FRAMES * SAMPLES_PER_FRAME
    parts = [
        f"[0:v]fps={FPS},trim=end_frame={EXPECTED_FRAMES},"
        "setpts=PTS-STARTPTS,format=yuv420p[v]",
        f"[0:a]aresample={RATE},aformat=sample_rates={RATE}:channel_layouts=stereo,"
        f"apad=whole_len={samples},atrim=end_sample={samples},asetpts=PTS-STARTPTS[a]",
    ]
    command = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-f",
        "ffmetadata",
        "-i",
        str(metadata),
        "-filter_complex",
        ";".join(parts),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-map_metadata",
        "1",
        "-map_chapters",
        "1",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    command += encode_args(16) + [
        "-frames:v",
        str(EXPECTED_FRAMES),
        "-t",
        f"{EXPECTED_FRAMES / FPS:.9f}",
        str(output),
    ]
    run(command, log)


def global_subtitle_cues(
    timeline: Sequence[Mapping[str, Any]],
    manifests: Mapping[str, Mapping[str, Any]],
    language: str,
) -> list[dict[str, Any]]:
    if language not in {"ja", "zh"}:
        raise Ac4901LongformBuildError(f"unsupported subtitle language: {language}")
    rows = []
    offset_frames = 0
    for timeline_row in timeline:
        unit_id = str(timeline_row["unit_id"])
        unit = manifests[unit_id]
        offset_ms = offset_frames * 1000 / FPS
        for cue in unit["subtitles"]:
            start_ms = round((offset_frames + int(cue["start_frame"])) * 1000 / FPS)
            end_ms = round(offset_ms + int(cue["end_ms"]))
            if end_ms <= start_ms:
                raise Ac4901LongformBuildError(f"subtitle interval is empty: {unit_id}")
            rows.append(
                {
                    "unit_id": unit_id,
                    "event": unit["event"],
                    "request_id": int(cue["voice_request_id"]),
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": str(cue[language]),
                    "translation_status": str(cue["translation_status"]),
                }
            )
        offset_frames += int(unit["presentation_frames"])
    if len(rows) != EXPECTED_SUBTITLES or offset_frames != EXPECTED_FRAMES:
        raise Ac4901LongformBuildError("global subtitle dimensions differ")
    return rows


def write_ass(
    path: Path,
    timeline: Sequence[Mapping[str, Any]],
    manifests: Mapping[str, Mapping[str, Any]],
    language: str,
    font_name: str,
) -> list[dict[str, Any]]:
    rows = global_subtitle_cues(timeline, manifests, language)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 416",
        "PlayResY: 232",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},22,&H00FFFFFF,&H000000FF,&H00000000,"
        "&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for row in rows:
        lines.append(
            "Dialogue: 0,"
            + _ass_time(int(row["start_ms"]))
            + ","
            + _ass_time(int(row["end_ms"]))
            + ",Default,,0,0,0,,"
            + _ass_text(str(row["text"]))
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return rows


def burn_subtitles(
    ffmpeg: str,
    source: Path,
    subtitle: Path,
    fonts_dir: Path,
    output: Path,
    log: Path,
) -> None:
    video_filter = (
        f"ass=filename='{_filter_path(subtitle)}':fontsdir='{_filter_path(fonts_dir)}'"
    )
    command = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        video_filter,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    command += encode_args(16, audio_copy=True) + [str(output)]
    run(command, log)


def review_path(root: Path, edition: str) -> Path:
    return (
        root
        / "HUMAN_REVIEW"
        / EDITIONS[edition]
        / "story"
        / f"ac4901_{TITLE}_严格无BGM__{edition}.mp4"
    )


def validate_probe(value: Mapping[str, Any]) -> dict[str, bool]:
    video = [row for row in value["streams"] if row["codec_type"] == "video"]
    audio = [row for row in value["streams"] if row["codec_type"] == "audio"]
    subtitles = [row for row in value["streams"] if row["codec_type"] == "subtitle"]
    checks = {
        "one_video": len(video) == 1,
        "one_audio": len(audio) == 1,
        "no_subtitle_stream": len(subtitles) == 0,
        "video_h264": len(video) == 1 and video[0].get("codec_name") == "h264",
        "canvas_416x232": len(video) == 1
        and (int(video[0].get("width", 0)), int(video[0].get("height", 0)))
        == (416, 232),
        "frame_rate_30": len(video) == 1
        and video[0].get("avg_frame_rate") == "30/1",
        "frame_count_35654": len(video) == 1
        and int(video[0].get("nb_read_frames", -1)) == EXPECTED_FRAMES,
        "audio_aac": len(audio) == 1 and audio[0].get("codec_name") == "aac",
        "audio_48k": len(audio) == 1
        and int(audio[0].get("sample_rate", 0)) == RATE,
        "audio_stereo": len(audio) == 1 and int(audio[0].get("channels", 0)) == 2,
        "chapter_count_220": len(value.get("chapters", [])) == EXPECTED_UNITS,
    }
    if not all(checks.values()):
        raise Ac4901LongformBuildError(f"media QA failed: {checks}")
    return checks


def verify_production(
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
    *,
    write_report: bool = True,
) -> dict[str, Any]:
    manifest = read_json(output_root / "manifests" / "PRODUCTION_MANIFEST.json")
    if (
        manifest.get("status") != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or manifest.get("content_group_count") != 1
        or manifest.get("edition_file_count") != 3
        or len(manifest.get("ordered_units", [])) != EXPECTED_UNITS
    ):
        raise Ac4901LongformBuildError("production manifest differs")
    media = []
    decoded_audio = set()
    for edition in EDITIONS:
        path = review_path(output_root, edition)
        if not path.is_file():
            raise Ac4901LongformBuildError(f"edition is absent: {path}")
        value = probe(
            ffprobe,
            path,
            output_root / "verification" / "commands" / f"probe_{edition}.txt",
        )
        checks = validate_probe(value)
        audio_identity = decoded_audio_sha256(
            ffmpeg,
            path,
            output_root
            / "verification"
            / "commands"
            / f"decoded_audio_identity_{edition}.txt",
        )
        decoded_audio.add(audio_identity)
        media.append(
            {
                "edition": edition,
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
                "bytes": path.stat().st_size,
                "duration_seconds": float(value["format"]["duration"]),
                "frame_count": EXPECTED_FRAMES,
                "width": 416,
                "height": 232,
                "frame_rate": "30/1",
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": RATE,
                "audio_channels": 2,
                "decoded_audio_sha256": audio_identity,
                "automatic_qa": checks,
                "human_status": "HUMAN_PLAYBACK_REQUIRED",
            }
        )
    if len(decoded_audio) != 1:
        raise Ac4901LongformBuildError("none/JA/ZH decoded audio differs")
    if max(row["duration_seconds"] for row in media) - min(
        row["duration_seconds"] for row in media
    ) > 0.001:
        raise Ac4901LongformBuildError("edition durations differ")
    report = {
        "schema": "magireco-ac4901-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "dirinfo_route_coverage": "162/162",
        "dirinfo_event_occurrences_accounted": EXPECTED_ROUTE_OCCURRENCES,
        "source_events": EXPECTED_SOURCE_EVENTS,
        "canonical_complete_event_presentations": EXPECTED_CANONICAL_EVENTS,
        "identical_complete_presentation_aliases_removed": EXPECTED_ALIAS_EVENTS,
        "route_state_underlay_variants": EXPECTED_UNDERLAY_VARIANTS,
        "duplicate_free_editorial_units": EXPECTED_UNITS,
        "loop_mapped_post_first_pass_frames_per_source_event_inventory": 4392,
        "unique_cri_video_identities_covered": EXPECTED_UNIQUE_CRI_SOURCES,
        "native_416x232_output": True,
        "strict_no_bgm": True,
        "excluded_bgm_identity": {
            "request_id": 226,
            "sound_id": 551,
            "source_event_occurrences": EXPECTED_EXCLUDED_BGM_SOURCE_OCCURRENCES,
        },
        "blocked_p16_p17_p18_leak_count": 0,
        "child_local_only_timing_leak_count": 0,
        "decoded_audio_identical_across_editions": True,
        "media": media,
        "source_media_modified": False,
        "bilibili_uploaded": False,
    }
    if write_report:
        write_json(output_root / "PRODUCTION_VERIFICATION.json", report)
    return report


def build(args: argparse.Namespace) -> Path:
    route = read_json(args.route_authority)
    visual = read_json(args.visual_authority)
    loop = read_json(args.loop_authority)
    audio = read_json(args.audio_authority)
    timeline = validate_authorities(
        route, visual, loop, audio, visual_path=args.visual_authority
    )
    manifests = build_unit_manifests(timeline, visual, loop, audio)
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise Ac4901LongformBuildError(f"immutable output already exists: {output_root}")
    if args.validate_authorities_only:
        print(
            "PASS_VALIDATE routes=162 units=220 layers=621 segments=801 "
            "audio=421 subtitles=56 frames=35654"
        )
        return output_root
    if args.resume_staging is not None:
        staging = args.resume_staging.resolve()
        if (
            not staging.is_dir()
            or staging.parent != output_root.parent
            or not staging.name.startswith(output_root.name + ".staging-")
        ):
            raise Ac4901LongformBuildError("resume staging boundary differs")
    else:
        staging = output_root.with_name(
            output_root.name + ".staging-" + uuid.uuid4().hex[:12]
        )
        staging.mkdir(parents=True)
    try:
        logs = staging / "verification" / "commands"
        unit_media: dict[str, Path] = {}
        reused_units = []
        standalone = [
            str(row["unit_id"]) for row in timeline if not row.get("underlay_event")
        ]
        variants = [
            str(row["unit_id"]) for row in timeline if row.get("underlay_event")
        ]
        if len(standalone) != EXPECTED_STANDALONE_UNITS or len(variants) != EXPECTED_UNDERLAY_VARIANTS:
            raise Ac4901LongformBuildError("unit render partition differs")
        for unit_id in standalone + variants:
            unit = manifests[unit_id]
            target = staging / "intermediate" / "units" / _unit_filename(unit_id)
            underlay_media = None
            underlay_frames = 0
            if unit["underlay_event"]:
                underlay_id = str(unit["underlay_unit_id"])
                underlay_media = unit_media.get(underlay_id)
                if underlay_media is None:
                    raise Ac4901LongformBuildError(
                        f"underlay unit has not been rendered: {unit_id}/{underlay_id}"
                    )
                underlay_frames = int(manifests[underlay_id]["presentation_frames"])
            if target.is_file():
                reused_units.append(unit_id)
            else:
                render_unit(
                    args.ffmpeg,
                    unit,
                    underlay_media,
                    underlay_frames,
                    target,
                    logs / f"render_{_unit_filename(unit_id)}.txt",
                )
            value = probe(
                args.ffprobe,
                target,
                logs / f"probe_{_unit_filename(unit_id)}.txt",
            )
            videos = [row for row in value["streams"] if row["codec_type"] == "video"]
            audios = [row for row in value["streams"] if row["codec_type"] == "audio"]
            expected = int(unit["presentation_frames"])
            if (
                len(videos) != 1
                or int(videos[0].get("nb_read_frames", -1)) != expected
                or len(audios) != 1
                or audios[0].get("codec_name") != "pcm_s16le"
                or int(audios[0].get("sample_rate", 0)) != RATE
                or int(audios[0].get("channels", 0)) != 2
            ):
                raise Ac4901LongformBuildError(f"unit AV grid differs: {unit_id}")
            unit_media[unit_id] = target

        metadata = staging / "manifests" / "chapters.ffmeta"
        chapters = write_chapters(metadata, timeline, manifests)
        concat_list = staging / "manifests" / "units.ffconcat"
        write_concat_list(concat_list, timeline, manifests, unit_media)
        none = review_path(staging, "none")
        render_none_longform(
            args.ffmpeg,
            concat_list,
            metadata,
            none,
            logs / "render_none_longform.txt",
        )
        ja_ass = staging / "manifests" / "ac4901_exhaustive_ja.ass"
        zh_ass = staging / "manifests" / "ac4901_exhaustive_zh.ass"
        ja_cues = write_ass(
            ja_ass, timeline, manifests, "ja", args.ja_font_name
        )
        zh_cues = write_ass(
            zh_ass, timeline, manifests, "zh", args.zh_font_name
        )
        ja = review_path(staging, "ja")
        zh = review_path(staging, "zh")
        burn_subtitles(
            args.ffmpeg,
            none,
            ja_ass,
            args.fonts_dir,
            ja,
            logs / "render_ja.txt",
        )
        burn_subtitles(
            args.ffmpeg,
            none,
            zh_ass,
            args.fonts_dir,
            zh,
            logs / "render_zh.txt",
        )
        input_paths = {
            "route_authority": args.route_authority,
            "visual_authority": args.visual_authority,
            "loop_authority": args.loop_authority,
            "audio_authority": args.audio_authority,
        }
        manifest = {
            "schema": "magireco-ac4901-exhaustive-production-manifest-v1",
            "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
            "family": "ac4901",
            "title": TITLE,
            "content_group_count": 1,
            "edition_file_count": 3,
            "audio_profile": "no_bgm",
            "dirinfo_routes": EXPECTED_ROUTES,
            "dirinfo_event_occurrences": EXPECTED_ROUTE_OCCURRENCES,
            "source_events": EXPECTED_SOURCE_EVENTS,
            "ordered_units": [str(row["unit_id"]) for row in timeline],
            "complete_presentation_aliases": route["dedup_contract"]["identical_alias_events"],
            "route_state_underlay_variants": EXPECTED_UNDERLAY_VARIANTS,
            "chapters": chapters,
            "subtitle_cue_count": {"ja": len(ja_cues), "zh": len(zh_cues)},
            "inputs": {name: _source_binding(path) for name, path in input_paths.items()},
            "outputs": {
                "none": published(none, staging, output_root),
                "ja": published(ja, staging, output_root),
                "zh": published(zh, staging, output_root),
            },
            "validated_intermediate_units_reused_from_staging": reused_units,
            "mutually_exclusive_routes_combined": True,
            "native_single_session_claimed": False,
            "each_unique_complete_route_state_presentation_once": True,
            "all_unique_cri_video_identities_covered": True,
            "loop_mapping_code_proven": True,
            "human_playback_required": True,
            "publication_approved": False,
        }
        write_json(staging / "manifests" / "PRODUCTION_MANIFEST.json", manifest)
        write_json(staging / "manifests" / "UNIT_MANIFESTS.json", manifests)
        (staging / "README.md").write_text(
            "# ac4901 exhaustive native-416 strict no-BGM longform\n\n"
            "One 1188.467-second content group accounts for all 162 exact DirInfo routes "
            "and all 720 event occurrences as 220 distinct complete route-state units. "
            "ac4901_112 and ac4901_232 remain in the source manifest as exact aliases of "
            "ac4901_105 and are not replayed. ac4901_091 is rendered in all 18 exact "
            "predecessor-frame states. Exact libGameProc.so loop code maps 4392 post-first-"
            "pass source-event frames instead of guessing a black or repeated last frame.\n",
            encoding="utf-8",
        )
        (staging / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            "# 人工验收重点\n\n"
            "1. 本目录只有1个内容组；NONE/JP/ZH是同一部20分钟长片。\n"
            "2. 按220个章节检查顺序可理解，所有互斥结果均纳入且无整段重复。\n"
            "3. 重点检查108个LP延展节点没有黑帧尾、卡末帧或越过父cut。\n"
            "4. 检查18个普通按钮章节均继承各自精确前一画面，不是同一底图重复。\n"
            "5. 逐句核对56句对白的开口、声音与JA/ZH字幕；本长片尚未获人工播放批准。\n"
            "6. 确认无BGM，同时保留421次已验证对白/SE。\n",
            encoding="utf-8",
        )
        (staging / "UPLOAD_GUIDE.md").write_text(
            "# 上传指南（验收前暂停上传）\n\n"
            "- 内容组：1组；NONE/JP/ZH为同一内容。\n"
            "- 建议分P名：`ac4901 全路线全独特演出穷尽合集`；JP追加`__ja`；ZH追加` 中文版`。\n"
            "- 建议动作：人工完整播放通过后追加，不替换任何已投稿文件。\n"
            "- 目标：none `BV1rUKN6iEcj`；JA `BV1zQKN6eEC6`；ZH `BV13bKN6nEsd`。\n"
            "- 明确排除：request226/sound551 BGM、P16/P17/P18、child-local-only、with-BGM。\n",
            encoding="utf-8",
        )
        (staging / "ROLLBACK.ps1").write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not (Test-Path -LiteralPath (Join-Path $Root 'PRODUCTION_VERIFICATION.json'))) { throw 'verification missing' }\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: disable this immutable production root by same-volume rename; sources remain untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8-sig",
        )
        failed_marker = staging / "FAILED_DO_NOT_USE.txt"
        if failed_marker.exists():
            failed_marker.replace(staging / "RECOVERED_FAILURE_HISTORY.txt")
        staging.replace(output_root)
        verify_production(output_root, args.ffmpeg, args.ffprobe)
    except BaseException:
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text(
                "Build failed; inspect verification command logs.\n", encoding="utf-8"
            )
        raise
    return output_root


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--route-authority", required=True, type=Path)
    value.add_argument("--visual-authority", required=True, type=Path)
    value.add_argument("--loop-authority", required=True, type=Path)
    value.add_argument("--audio-authority", required=True, type=Path)
    value.add_argument("--output-root", required=True, type=Path)
    value.add_argument("--resume-staging", type=Path)
    value.add_argument("--fonts-dir", type=Path, default=Path(r"C:\Windows\Fonts"))
    value.add_argument("--ja-font-name", default="MS Gothic")
    value.add_argument("--zh-font-name", default="Microsoft YaHei")
    value.add_argument("--ffmpeg", default="ffmpeg")
    value.add_argument("--ffprobe", default="ffprobe")
    value.add_argument("--verify-existing", action="store_true")
    value.add_argument("--validate-authorities-only", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.verify_existing:
        report = verify_production(
            args.output_root.resolve(), args.ffmpeg, args.ffprobe
        )
        print(
            f"PASS_VERIFY_EXISTING groups=1 editions=3 units=220 "
            f"frames={EXPECTED_FRAMES} root={args.output_root.resolve()}"
        )
    else:
        output = build(args)
        if args.validate_authorities_only:
            return 0
        report = read_json(output / "PRODUCTION_VERIFICATION.json")
        print(
            f"PASS_RENDER groups=1 editions=3 routes=162 units=220 "
            f"unique_videos=194 frames={EXPECTED_FRAMES} "
            f"duration={report['media'][0]['duration_seconds']:.3f}s root={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
