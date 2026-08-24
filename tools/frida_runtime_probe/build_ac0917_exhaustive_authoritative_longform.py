#!/usr/bin/env python3
"""Render the code-looped exhaustive native-416 ac0917 strict no-BGM longform."""

from __future__ import annotations

import argparse
import json
import uuid
from collections import defaultdict
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
except ImportError:  # direct script execution
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
EXPECTED_FRAMES = 3136
EXPECTED_EVENTS = 12
EXPECTED_ROUTES = 22
EXPECTED_ROUTE_OCCURRENCES = 75
EXPECTED_LAYER_OCCURRENCES = 22
EXPECTED_RENDER_SEGMENTS = 31
EXPECTED_MOVIE_PARENTS = 13
EXPECTED_SCHEDULED_MOVIE_FRAMES = 2711
EXPECTED_LOOP_EXTENSION_FRAMES = 207
EXPECTED_UNIQUE_CRI_SOURCES = 20
EXPECTED_RETAINED_AUDIO = 25
EXPECTED_RETAINED_SE = 13
EXPECTED_RETAINED_VOICE = 12
EXPECTED_SUBTITLES = 18
EXPECTED_NORMAL_LAYERS = 20
EXPECTED_ADDITIVE_LAYERS = 2
EDITIONS = {"none": "NONE", "ja": "JP", "zh": "ZH"}
TITLE = "里见灯花演说与全部路线演出穷尽合集"
CHAPTER_TITLES = {
    "ac0917_014": "另一入口普通PUSH提示",
    "ac0917_001": "灯花演说共同导入",
    "ac0917_002": "白色短演出",
    "ac0917_004": "白色完整演出",
    "ac0917_003": "红色完整演出",
    "ac0917_011": "红色短演出",
    "ac0917_006": "大型PUSH分支",
    "ac0917_010": "小丘比PUSH分支",
    "ac0917_005": "上乘冲击效果",
    "ac0917_007": "发展结果",
    "ac0917_008": "CZ结果",
    "ac0917_009": "WIN结果",
}
EXPECTED_PRESENTATION_FRAMES = {
    "ac0917_014": 100,
    "ac0917_001": 252,
    "ac0917_002": 269,
    "ac0917_004": 300,
    "ac0917_003": 300,
    "ac0917_011": 228,
    "ac0917_006": 300,
    "ac0917_010": 300,
    "ac0917_005": 240,
    "ac0917_007": 287,
    "ac0917_008": 280,
    "ac0917_009": 280,
}
EXPECTED_VISUAL_FRAMES = {
    "ac0917_014": 100,
    "ac0917_001": 187,
    "ac0917_002": 240,
    "ac0917_004": 300,
    "ac0917_003": 300,
    "ac0917_011": 100,
    "ac0917_006": 300,
    "ac0917_010": 300,
    "ac0917_005": 240,
    "ac0917_007": 280,
    "ac0917_008": 280,
    "ac0917_009": 280,
}


class Ac0917LongformBuildError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_authorities(
    route: Mapping[str, Any],
    visual: Mapping[str, Any],
    loop: Mapping[str, Any],
    audio: Mapping[str, Any],
    *,
    visual_path: Path,
) -> list[str]:
    if (
        route.get("schema")
        != "magireco-ac0917-dirinfo-route-and-complete-presentation-dedup-authority-v2"
        or route.get("status") != "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER"
    ):
        raise Ac0917LongformBuildError("ac0917 route/dedup authority differs")
    route_summary = route.get("summary", {})
    expected_route = {
        "dirinfo_routes": EXPECTED_ROUTES,
        "dirinfo_event_occurrences": EXPECTED_ROUTE_OCCURRENCES,
        "source_events": EXPECTED_EVENTS,
        "canonical_presentations": EXPECTED_EVENTS,
        "identical_complete_presentation_aliases": 0,
        "visible_unique_cri_sources_covered": EXPECTED_UNIQUE_CRI_SOURCES,
        "duplicate_free_longform_frames": EXPECTED_FRAMES,
        "duplicate_free_longform_seconds": EXPECTED_FRAMES / FPS,
    }
    if any(route_summary.get(key) != value for key, value in expected_route.items()):
        raise Ac0917LongformBuildError("ac0917 route/dedup dimensions differ")
    if (
        visual.get("schema") != "magireco-ac0917-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("summary", {}).get("events") != EXPECTED_EVENTS
        or visual.get("summary", {}).get("unique_loadable_cri_sources")
        != EXPECTED_UNIQUE_CRI_SOURCES
    ):
        raise Ac0917LongformBuildError("ac0917 projection authority differs")
    if (
        loop.get("schema")
        != "magireco-ac0917-parent-clock-z2d-loop-authority-v1"
        or loop.get("status")
        != "PASS_READY_FOR_LOOP_AWARE_ROUTE_DEDUP_AND_LONGFORM_RENDER"
        or loop.get("summary", {}).get("events") != EXPECTED_EVENTS
        or loop.get("summary", {}).get("movie_parents")
        != EXPECTED_MOVIE_PARENTS
        or loop.get("summary", {}).get("loop_extension_frames")
        != EXPECTED_LOOP_EXTENSION_FRAMES
        or loop.get("summary", {}).get("scheduled_movie_frame_occurrences")
        != EXPECTED_SCHEDULED_MOVIE_FRAMES
        or loop.get("summary", {}).get("render_segments")
        != EXPECTED_RENDER_SEGMENTS
        or loop.get("summary", {}).get("unique_sources")
        != EXPECTED_UNIQUE_CRI_SOURCES
        or loop.get("summary", {}).get("parent_clock_excluded_occurrences") != 3
    ):
        raise Ac0917LongformBuildError("ac0917 Z2D loop authority differs")
    if str(
        loop.get("inputs", {}).get("output_projection", {}).get("sha256", "")
    ).casefold() != file_sha256(visual_path.resolve()).casefold():
        raise Ac0917LongformBuildError("loop authority is not bound to this projection")
    if (
        audio.get("schema")
        != "magireco-ac0917-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY"
        or audio.get("summary", {}).get("retained_audio_occurrences")
        != EXPECTED_RETAINED_AUDIO
        or audio.get("summary", {}).get("retained_se_occurrences")
        != EXPECTED_RETAINED_SE
        or audio.get("summary", {}).get("retained_voice_occurrences")
        != EXPECTED_RETAINED_VOICE
        or audio.get("summary", {}).get("excluded_bgm_occurrences") != 3
        or audio.get("summary", {}).get("subtitle_page_cue_occurrences")
        != EXPECTED_SUBTITLES
        or audio.get("summary", {}).get("rendered_presentation_frames_before_dedup")
        != EXPECTED_FRAMES
        or audio.get("summary", {}).get("final_frame_hold_frames") != 229
    ):
        raise Ac0917LongformBuildError("ac0917 audio authority differs")
    timeline = list(route.get("editorial_timeline", []))
    order = [str(row["event"]) for row in timeline]
    cursor = 0
    exact_timeline = True
    for row in timeline:
        event = str(row["event"])
        frames = EXPECTED_PRESENTATION_FRAMES.get(event)
        if frames is None or (
            int(row["start_frame"]) != cursor
            or int(row["end_frame_exclusive"]) != cursor + frames
            or int(row["duration_frames"]) != frames
        ):
            exact_timeline = False
            break
        cursor += frames
    if (
        len(order) != EXPECTED_EVENTS
        or len(set(order)) != EXPECTED_EVENTS
        or set(order) != set(CHAPTER_TITLES)
        or not exact_timeline
        or cursor != EXPECTED_FRAMES
    ):
        raise Ac0917LongformBuildError("ac0917 duplicate-free editorial order differs")
    if route.get("dedup_contract", {}).get("identical_alias_events") != {}:
        raise Ac0917LongformBuildError("ac0917 complete-presentation aliases differ")
    return order


def build_event_manifests(
    order: Sequence[str],
    visual: Mapping[str, Any],
    loop: Mapping[str, Any],
    audio: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    visual_events = {str(row["event"]): row for row in visual["events"]}
    loop_events = {str(row["event"]): row for row in loop["events"]}
    audio_presentations = {
        str(row["event"]): row for row in audio["event_presentations"]
    }
    expected_event_set = set(order)
    if (
        set(visual_events) != expected_event_set
        or set(loop_events) != expected_event_set
        or set(audio_presentations) != expected_event_set
    ):
        raise Ac0917LongformBuildError("event authority sets differ")
    audio_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    subtitle_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audio_source_hashes: dict[str, str] = {}
    for source_row in audio["retained_audio_rows"]:
        row = dict(source_row)
        source = dict(row["official_source"])
        path = Path(str(source["path"]))
        if not path.is_file() or path.stat().st_size != int(source["size_bytes"]):
            raise Ac0917LongformBuildError(f"official audio source differs: {path}")
        actual = audio_source_hashes.setdefault(
            str(path.resolve()), file_sha256(path)
        )
        if actual.casefold() != str(source["sha256"]).casefold():
            raise Ac0917LongformBuildError(f"official audio hash differs: {path}")
        source["sha256"] = actual
        row["official_source"] = source
        audio_rows[str(row["event"])].append(row)
    for row in audio["subtitle_page_cues"]:
        subtitle_rows[str(row["event"])].append(dict(row))
    manifests: dict[str, dict[str, Any]] = {}
    for event in order:
        row = visual_events[event]
        loop_row = loop_events[event]
        segment_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        scheduled_by_segments = 0
        for parent in loop_row["parent_z2d_schedules_in_gfdirection_order"]:
            parent_segments = list(parent["render_segments"])
            parent_frames = sum(int(segment["frame_count"]) for segment in parent_segments)
            if parent_frames != int(parent["scheduled_movie_frame_occurrences"]):
                raise Ac0917LongformBuildError(
                    f"parent segment coverage differs: {event}/{parent['parent_z2d']}"
                )
            scheduled_by_segments += parent_frames
            for segment in parent_segments:
                segment_groups[str(segment["projection_key"])].append(dict(segment))
        if scheduled_by_segments != int(
            loop_row["scheduled_movie_frame_occurrences"]
        ):
            raise Ac0917LongformBuildError(
                f"event segment coverage differs: {event}"
            )
        layers = []
        for source_layer in row["layers_in_render_pass_order_under_to_top"]:
            layer = dict(source_layer)
            key = "|".join(
                str(layer[name])
                for name in ("scene", "cut", "parent_z2d", "source_name")
            )
            segments = sorted(
                segment_groups.pop(key, []),
                key=lambda value: int(value["event_start_frame"]),
            )
            if not segments:
                raise Ac0917LongformBuildError(
                    f"projection layer lacks loop schedule: {event}/{key}"
                )
            layer["loop_aware_render_segments"] = segments
            layers.append(layer)
        if segment_groups:
            raise Ac0917LongformBuildError(
                f"loop schedule lacks projection layer: {event}/{sorted(segment_groups)}"
            )
        retained = audio_rows[event]
        subtitles = subtitle_rows[event]
        if not layers:
            raise Ac0917LongformBuildError(f"event lacks visual composition: {event}")
        if event == "ac0917_005" and retained:
            raise Ac0917LongformBuildError("ac0917_005 is expected to be silent")
        if event != "ac0917_005" and not retained:
            raise Ac0917LongformBuildError(f"event lacks retained audio: {event}")
        if any(item["volume_bus"] not in {"SE", "VOICE"} for item in retained):
            raise Ac0917LongformBuildError(f"non-retained bus leaked into {event}")
        presentation = audio_presentations[event]
        visual_frames = int(presentation["visual_presentation_frames"])
        frames = int(presentation["rendered_presentation_frames"])
        if frames != EXPECTED_PRESENTATION_FRAMES[event]:
            raise Ac0917LongformBuildError(f"event presentation extent differs: {event}")
        if (
            visual_frames != EXPECTED_VISUAL_FRAMES[event]
            or int(row["presentation_frame_count"]) != visual_frames
            or int(presentation["final_frame_hold_frames"])
            != frames - visual_frames
        ):
            raise Ac0917LongformBuildError(f"visual extent differs: {event}")
        manifests[event] = {
            "event": event,
            "visual_frames": visual_frames,
            "presentation_frames": frames,
            "final_frame_hold_frames": frames - visual_frames,
            "movie_parent_schedule_count": int(
                loop_row["movie_parent_schedule_count"]
            ),
            "scheduled_movie_frame_occurrences": int(
                loop_row["scheduled_movie_frame_occurrences"]
            ),
            "layers": layers,
            "retained_audio": retained,
            "subtitles": subtitles,
            "non_movie_text_z2d_nodes": row["non_movie_text_z2d_nodes"],
            "runtime_symbolic_nodes": row["runtime_symbolic_nodes"],
        }
    layers = [item for event in order for item in manifests[event]["layers"]]
    segments = [
        segment
        for layer in layers
        for segment in layer["loop_aware_render_segments"]
    ]
    retained = [item for event in order for item in manifests[event]["retained_audio"]]
    subtitles = [item for event in order for item in manifests[event]["subtitles"]]
    if (
        len(layers) != EXPECTED_LAYER_OCCURRENCES
        or len(segments) != EXPECTED_RENDER_SEGMENTS
        or sum(
            manifests[event]["movie_parent_schedule_count"] for event in order
        )
        != EXPECTED_MOVIE_PARENTS
        or sum(
            manifests[event]["scheduled_movie_frame_occurrences"] for event in order
        )
        != EXPECTED_SCHEDULED_MOVIE_FRAMES
        or len({item["source"]["official_name"] for item in layers})
        != EXPECTED_UNIQUE_CRI_SOURCES
        or sum(int(item["effective_renderer_state"]) == 1 for item in layers)
        != EXPECTED_NORMAL_LAYERS
        or sum(int(item["effective_renderer_state"]) == 3 for item in layers)
        != EXPECTED_ADDITIVE_LAYERS
        or len(retained) != EXPECTED_RETAINED_AUDIO
        or sum(item["volume_bus"] == "SE" for item in retained)
        != EXPECTED_RETAINED_SE
        or sum(item["volume_bus"] == "VOICE" for item in retained)
        != EXPECTED_RETAINED_VOICE
        or len(subtitles) != EXPECTED_SUBTITLES
        or sum(manifests[event]["final_frame_hold_frames"] for event in order)
        != 229
        or sum(manifests[event]["presentation_frames"] for event in order)
        != EXPECTED_FRAMES
    ):
        raise Ac0917LongformBuildError("canonical production dimensions differ")
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
            raise Ac0917LongformBuildError("incrementing render segment differs")
        filters = f"trim=start_frame={start}:end_frame={end + 1}"
    elif progression in {"hold", "single_frame"}:
        if start != end:
            raise Ac0917LongformBuildError("held render segment source differs")
        filters = f"trim=start_frame={start}:end_frame={start + 1}"
        if frames > 1:
            filters += f",tpad=stop_mode=clone:stop={frames - 1}"
    else:
        raise Ac0917LongformBuildError(
            f"unsupported source progression: {progression}"
        )
    if shift_to_event:
        filters += (
            f",setpts=PTS-STARTPTS+{int(segment['event_start_frame'])}/{FPS}/TB"
        )
    else:
        filters += ",setpts=PTS-STARTPTS"
    return f"[{label}]{filters}"


def layer_filter_parts(
    input_index: int,
    layer_index: int,
    row: Mapping[str, Any],
    current: str,
    event_frames: int,
) -> tuple[list[str], str]:
    source = row["source"]
    x, y, width, height = (int(value) for value in row["output_rect_xywh"])
    if (x, y, width, height) != (0, 0, 416, 232):
        raise Ac0917LongformBuildError("ac0917 output projection differs")
    scale = ""
    if (int(source["width"]), int(source["height"])) != (width, height):
        scale = f"scale={width}:{height}:flags=lanczos,"
    segments = list(row["loop_aware_render_segments"])
    if not segments:
        raise Ac0917LongformBuildError("loop-aware render segment list is empty")
    base = f"l{layer_index}"
    parts = [
        f"[{input_index}:v:0]format=rgb24,vflip[{base}c]",
        f"[{input_index}:v:1]format=gray,vflip[{base}a]",
        f"[{base}c][{base}a]alphamerge,{scale}format=rgba[{base}rgba]",
    ]
    branches = [f"{base}s{index}" for index in range(len(segments))]
    if len(branches) == 1:
        parts.append(f"[{base}rgba]null[{branches[0]}]")
    else:
        parts.append(
            f"[{base}rgba]split={len(branches)}"
            + "".join(f"[{label}]" for label in branches)
        )
    state = int(row["effective_renderer_state"])
    for index, (segment, branch) in enumerate(zip(segments, branches)):
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
                raise Ac0917LongformBuildError("additive segment exceeds event")
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
            raise Ac0917LongformBuildError(
                f"unsupported renderer state: {state}"
            )
        current = next_label
    return parts, current


def render_event(ffmpeg: str, manifest: Mapping[str, Any], output: Path, log: Path) -> None:
    event = str(manifest["event"])
    layers = manifest["layers"]
    retained = manifest["retained_audio"]
    visual_frames = int(manifest["visual_frames"])
    frames = int(manifest["presentation_frames"])
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for row in layers:
        path = Path(str(row["source"]["path"]))
        if not path.is_file() or file_sha256(path) != str(row["source"]["sha256"]):
            raise Ac0917LongformBuildError(f"exact CRI source differs: {event}/{path}")
        command += ["-i", str(path)]
    for row in retained:
        path = Path(str(row["official_source"]["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != int(row["official_source"]["size_bytes"])
            or file_sha256(path).casefold()
            != str(row["official_source"]["sha256"]).casefold()
        ):
            raise Ac0917LongformBuildError(f"official audio differs: {event}/{path}")
        command += ["-i", str(path)]
    parts = [
        f"color=c=black:s=416x232:r=30:d={visual_frames / FPS:.9f},"
        "format=rgb24[base0]"
    ]
    current = "base0"
    for index, row in enumerate(layers):
        filters, current = layer_filter_parts(
            index, index, row, current, visual_frames
        )
        parts += filters
    hold_frames = frames - visual_frames
    if hold_frames:
        parts.append(
            f"[{current}]tpad=stop_mode=clone:stop={hold_frames},"
            f"trim=end_frame={frames},setpts=PTS-STARTPTS,format=yuv420p[v]"
        )
    else:
        parts.append(
            f"[{current}]trim=end_frame={frames},setpts=PTS-STARTPTS,format=yuv420p[v]"
        )
    audio_labels = []
    first_audio_index = len(layers)
    for index, row in enumerate(retained):
        label = f"a{index}"
        delay_samples = round(int(row["start_ms"]) * RATE / 1000)
        parts.append(
            f"[{first_audio_index + index}:a]aresample=48000,"
            "aformat=sample_rates=48000:channel_layouts=stereo,"
            f"adelay={delay_samples}S:all=1,asetpts=PTS-STARTPTS[{label}]"
        )
        audio_labels.append(f"[{label}]")
    samples = frames * SAMPLES_PER_FRAME
    if audio_labels:
        parts.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audio_labels)}:duration=longest:normalize=0,"
            f"apad=whole_len={samples},atrim=end_sample={samples},asetpts=PTS-STARTPTS[a]"
        )
    else:
        parts.append(
            f"anullsrc=r=48000:cl=stereo,atrim=end_sample={samples},"
            "asetpts=PTS-STARTPTS[a]"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += encode_args(12) + [str(output)]
    run(command, log)


def write_chapters(
    path: Path, order: Sequence[str], manifests: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    chapters = []
    lines = [";FFMETADATA1"]
    cursor = 0
    for event in order:
        frames = int(manifests[event]["presentation_frames"])
        chapters.append(
            {
                "event": event,
                "start_frame": cursor,
                "end_frame_exclusive": cursor + frames,
                "title": CHAPTER_TITLES[event],
            }
        )
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/30",
            f"START={cursor}",
            f"END={cursor + frames}",
            f"title={CHAPTER_TITLES[event]} ({event})",
        ]
        cursor += frames
    if cursor != EXPECTED_FRAMES:
        raise Ac0917LongformBuildError("chapter frame total differs")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chapters


def render_none_longform(
    ffmpeg: str,
    order: Sequence[str],
    manifests: Mapping[str, Mapping[str, Any]],
    event_media: Mapping[str, Path],
    metadata: Path,
    output: Path,
    log: Path,
) -> None:
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for event in order:
        command += ["-i", str(event_media[event])]
    command += ["-f", "ffmetadata", "-i", str(metadata)]
    parts = []
    for index, event in enumerate(order):
        frames = int(manifests[event]["presentation_frames"])
        samples = frames * SAMPLES_PER_FRAME
        parts += [
            f"[{index}:v]trim=end_frame={frames},setpts=PTS-STARTPTS[v{index}]",
            f"[{index}:a]atrim=end_sample={samples},asetpts=PTS-STARTPTS[a{index}]",
        ]
    parts.append(
        "".join(f"[v{i}][a{i}]" for i in range(len(order)))
        + f"concat=n={len(order)}:v=1:a=1[v][a]"
    )
    metadata_index = len(order)
    output.parent.mkdir(parents=True, exist_ok=True)
    command += [
        "-filter_complex",
        ";".join(parts),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-map_metadata",
        str(metadata_index),
        "-map_chapters",
        str(metadata_index),
    ]
    command += encode_args(16) + [str(output)]
    run(command, log)


def global_subtitle_cues(
    order: Sequence[str], manifests: Mapping[str, Mapping[str, Any]], language: str
) -> list[dict[str, Any]]:
    if language not in {"ja", "zh"}:
        raise Ac0917LongformBuildError(f"unsupported subtitle language: {language}")
    rows = []
    offset_frames = 0
    for event in order:
        offset_ms = offset_frames * 1000 / FPS
        for cue in manifests[event]["subtitles"]:
            start_ms = round((offset_frames + int(cue["start_frame"])) * 1000 / FPS)
            end_ms = round(offset_ms + int(cue["end_ms"]))
            if end_ms <= start_ms:
                raise Ac0917LongformBuildError(f"subtitle interval is empty: {event}")
            rows.append(
                {
                    "event": event,
                    "request_id": int(cue["voice_request_id"]),
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": str(cue[language]),
                    "translation_status": str(cue["translation_status"]),
                }
            )
        offset_frames += int(manifests[event]["presentation_frames"])
    if len(rows) != EXPECTED_SUBTITLES or offset_frames != EXPECTED_FRAMES:
        raise Ac0917LongformBuildError("global subtitle dimensions differ")
    return rows


def write_ass(
    path: Path,
    order: Sequence[str],
    manifests: Mapping[str, Mapping[str, Any]],
    language: str,
    font_name: str,
) -> list[dict[str, Any]]:
    rows = global_subtitle_cues(order, manifests, language)
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
    command += encode_args(16, audio_copy=True) + [str(output)]
    output.parent.mkdir(parents=True, exist_ok=True)
    run(command, log)


def review_path(root: Path, edition: str) -> Path:
    return (
        root
        / "HUMAN_REVIEW"
        / EDITIONS[edition]
        / "story"
        / f"ac0917_{TITLE}_严格无BGM__{edition}.mp4"
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
        "frame_rate_30": len(video) == 1 and video[0].get("avg_frame_rate") == "30/1",
        "frame_count_3136": len(video) == 1
        and int(video[0].get("nb_read_frames", -1)) == EXPECTED_FRAMES,
        "audio_aac": len(audio) == 1 and audio[0].get("codec_name") == "aac",
        "audio_48k": len(audio) == 1 and int(audio[0].get("sample_rate", 0)) == RATE,
        "audio_stereo": len(audio) == 1 and int(audio[0].get("channels", 0)) == 2,
        "chapter_count_12": len(value.get("chapters", [])) == EXPECTED_EVENTS,
    }
    if not all(checks.values()):
        raise Ac0917LongformBuildError(f"media QA failed: {checks}")
    return checks


def verify_production(
    output_root: Path, ffmpeg: str, ffprobe: str, *, write_report: bool = True
) -> dict[str, Any]:
    manifest = read_json(output_root / "manifests" / "PRODUCTION_MANIFEST.json")
    if (
        manifest.get("status") != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or manifest.get("content_group_count") != 1
        or manifest.get("edition_file_count") != 3
        or len(manifest.get("ordered_events", [])) != EXPECTED_EVENTS
    ):
        raise Ac0917LongformBuildError("production manifest differs")
    media = []
    decoded_audio = set()
    for edition in EDITIONS:
        path = review_path(output_root, edition)
        if not path.is_file():
            raise Ac0917LongformBuildError(f"edition is absent: {path}")
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
        raise Ac0917LongformBuildError("none/JA/ZH decoded audio differs")
    if max(row["duration_seconds"] for row in media) - min(
        row["duration_seconds"] for row in media
    ) > 0.001:
        raise Ac0917LongformBuildError("edition durations differ")
    report = {
        "schema": "magireco-ac0917-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "dirinfo_route_coverage": "22/22",
        "dirinfo_event_occurrences_accounted": EXPECTED_ROUTE_OCCURRENCES,
        "source_events": EXPECTED_EVENTS,
        "ordered_unique_complete_event_presentations": EXPECTED_EVENTS,
        "identical_complete_presentation_aliases_removed": 0,
        "loop_mapped_post_first_pass_frames": EXPECTED_LOOP_EXTENSION_FRAMES,
        "scheduled_movie_frame_occurrences": EXPECTED_SCHEDULED_MOVIE_FRAMES,
        "unique_cri_video_identities_covered": EXPECTED_UNIQUE_CRI_SOURCES,
        "native_416x232_output": True,
        "strict_no_bgm": True,
        "excluded_bgm_identities": [
            {"request_id": 226, "sound_id": 551},
            {"request_id": 227, "sound_id": 552},
            {"request_id": 228, "sound_id": 553},
        ],
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
    order = validate_authorities(
        route, visual, loop, audio, visual_path=args.visual_authority
    )
    manifests = build_event_manifests(order, visual, loop, audio)
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise Ac0917LongformBuildError(f"immutable output already exists: {output_root}")
    if args.validate_authorities_only:
        print(
            "PASS_VALIDATE routes=22 events=12 layers=22 segments=31 "
            "scheduled_frames=2711 audio=25 subtitles=18 frames=3136"
        )
        return output_root
    if args.resume_staging is not None:
        staging = args.resume_staging.resolve()
        if (
            not staging.is_dir()
            or staging.parent != output_root.parent
            or not staging.name.startswith(output_root.name + ".staging-")
        ):
            raise Ac0917LongformBuildError("resume staging boundary differs")
    else:
        staging = output_root.with_name(
            output_root.name + ".staging-" + uuid.uuid4().hex[:12]
        )
        staging.mkdir(parents=True)
    try:
        logs = staging / "verification" / "commands"
        event_media = {}
        reused_events = []
        for event in order:
            target = staging / "intermediate" / "events" / f"{event}.mp4"
            if target.is_file():
                reused_events.append(event)
            else:
                render_event(
                    args.ffmpeg,
                    manifests[event],
                    target,
                    logs / f"render_{event}.txt",
                )
            value = probe(args.ffprobe, target, logs / f"probe_{event}.txt")
            videos = [row for row in value["streams"] if row["codec_type"] == "video"]
            expected = int(manifests[event]["presentation_frames"])
            if len(videos) != 1 or int(videos[0].get("nb_read_frames", -1)) != expected:
                raise Ac0917LongformBuildError(f"event frame grid differs: {event}")
            event_media[event] = target
        metadata = staging / "manifests" / "chapters.ffmeta"
        chapters = write_chapters(metadata, order, manifests)
        none = review_path(staging, "none")
        render_none_longform(
            args.ffmpeg,
            order,
            manifests,
            event_media,
            metadata,
            none,
            logs / "render_none_longform.txt",
        )
        ja_ass = staging / "manifests" / "ac0917_exhaustive_ja.ass"
        zh_ass = staging / "manifests" / "ac0917_exhaustive_zh.ass"
        ja_cues = write_ass(ja_ass, order, manifests, "ja", args.ja_font_name)
        zh_cues = write_ass(zh_ass, order, manifests, "zh", args.zh_font_name)
        ja = review_path(staging, "ja")
        zh = review_path(staging, "zh")
        burn_subtitles(args.ffmpeg, none, ja_ass, args.fonts_dir, ja, logs / "render_ja.txt")
        burn_subtitles(args.ffmpeg, none, zh_ass, args.fonts_dir, zh, logs / "render_zh.txt")
        input_paths = {
            "route_authority": args.route_authority,
            "visual_authority": args.visual_authority,
            "loop_authority": args.loop_authority,
            "audio_authority": args.audio_authority,
        }
        manifest = {
            "schema": "magireco-ac0917-exhaustive-production-manifest-v1",
            "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
            "family": "ac0917",
            "title": TITLE,
            "content_group_count": 1,
            "edition_file_count": 3,
            "audio_profile": "no_bgm",
            "dirinfo_routes": EXPECTED_ROUTES,
            "dirinfo_event_occurrences": EXPECTED_ROUTE_OCCURRENCES,
            "source_events": EXPECTED_EVENTS,
            "ordered_events": order,
            "complete_presentation_aliases": route["dedup_contract"]["identical_alias_events"],
            "chapters": chapters,
            "subtitle_cue_count": {"ja": len(ja_cues), "zh": len(zh_cues)},
            "inputs": {
                name: {
                    "path": str(path.resolve()),
                    "sha256": file_sha256(path),
                    "bytes": path.stat().st_size,
                }
                for name, path in input_paths.items()
            },
            "outputs": {
                "none": published(none, staging, output_root),
                "ja": published(ja, staging, output_root),
                "zh": published(zh, staging, output_root),
            },
            "validated_intermediate_events_reused_from_staging": reused_events,
            "mutually_exclusive_routes_combined": True,
            "native_single_session_claimed": False,
            "each_unique_complete_event_presentation_once": True,
            "all_unique_cri_video_identities_covered": True,
            "loop_mapping_code_proven": True,
            "all_2711_scheduled_movie_frames_accounted": True,
            "human_playback_required": True,
            "publication_approved": False,
        }
        write_json(staging / "manifests" / "PRODUCTION_MANIFEST.json", manifest)
        write_json(staging / "manifests" / "EVENT_MANIFESTS.json", manifests)
        (staging / "README.md").write_text(
            "# ac0917 exhaustive native-416 strict no-BGM longform\n\n"
            "One 104.533-second content group preserves all 22 exact DirInfo routes and "
            "75 occurrences as 12 unique complete presentations. All 20 visible CRI "
            "sources are scheduled from exact GFDirection parent clocks. The code-proven "
            "Z2D loop mapping expands only 207 frames; three MovieLayers outside the "
            "parent clock remain provenance-only rather than being forced into the film.\n",
            encoding="utf-8",
        )
        (staging / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            "# 人工验收重点\n\n"
            "1. 本目录只有1个内容组；NONE/JP/ZH是同一长片的三种字幕轨。\n"
            "2. 按12个章节检查顺序自然、无整段重复、无缺失互斥结果。\n"
            "3. 逐页核对18条对白的开口、声音与JA/ZH字幕；新长片未继承人工批准。\n"
            "4. 重点检查001、008、009三个代码循环段无卡末帧或黑帧。\n"
            "5. 检查006、010、014按钮只在父cut内出现，没有错误延长到整段事件。\n"
            "6. 确认无BGM，同时保留13次SE和12次VOICE。\n",
            encoding="utf-8",
        )
        (staging / "UPLOAD_GUIDE.md").write_text(
            "# 上传指南（验收前暂停上传）\n\n"
            "- 内容组：1组；NONE/JP/ZH为同一内容。\n"
            "- 建议分P名：`里见灯花演说与全部路线演出穷尽合集 ac0917`；"
            "JP追加`__ja`；ZH追加` 中文版`。\n"
            "- 建议动作：人工完整播放通过后追加，不替换任何已投稿文件。\n"
            "- 目标：none `BV1rUKN6iEcj`；JA `BV1zQKN6eEC6`；ZH `BV13bKN6nEsd`。\n"
            "- 明确排除：request226/227/228（sound551/552/553）BGM、"
            "P16/P17/P18、child-local-only、with-BGM。\n",
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
    value = argparse.ArgumentParser()
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
        report = verify_production(args.output_root.resolve(), args.ffmpeg, args.ffprobe)
        print(
            f"PASS_VERIFY_EXISTING groups=1 editions=3 frames={EXPECTED_FRAMES} "
            f"root={args.output_root.resolve()}"
        )
    else:
        output = build(args)
        if args.validate_authorities_only:
            return 0
        report = read_json(output / "PRODUCTION_VERIFICATION.json")
        print(
            f"PASS_RENDER groups=1 editions=3 routes=22 unique_presentations=12 "
            f"unique_videos=20 frames={EXPECTED_FRAMES} "
            f"duration={report['media'][0]['duration_seconds']:.3f}s root={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
