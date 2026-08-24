#!/usr/bin/env python3
"""Render the exhaustive native-416 ac6007 strict no-BGM longform."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_exhaustive_unique_longform import file_sha256
except ImportError:  # direct script execution
    from build_exhaustive_unique_longform import file_sha256  # type: ignore


FPS = 30
RATE = 48_000
SAMPLES_PER_FRAME = RATE // FPS
EXPECTED_FRAMES = 3016
EXPECTED_EVENTS = 10
EXPECTED_SUBTITLES = 20
EDITIONS = {"none": "NONE", "ja": "JP", "zh": "ZH"}
TITLE = "女王熊袭击_全攻击失败胜利复活穷尽合集"
CHAPTER_TITLES = {
    "ac6007_001": "女王熊来袭公共入口",
    "ac6007_002": "菲莉希亚突击",
    "ac6007_003": "菲莉希亚单骑攻击",
    "ac6007_005": "莎奈与菲莉希亚突击（CU）",
    "ac6007_006": "莎奈与菲莉希亚协力攻击",
    "ac6007_004": "失败结局",
    "ac6007_007": "菲莉希亚单骑胜利",
    "ac6007_008": "两人协力胜利",
    "ac6007_009": "两人拒绝放弃·复活",
    "ac6007_010": "两人击破传闻·复活胜利",
}


class Ac6007LongformBuildError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def published(path: Path, staging: Path, output_root: Path) -> str:
    return str(output_root / path.resolve().relative_to(staging.resolve()))


def run(command: Sequence[str], log_path: Path) -> None:
    result = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND\n"
        + subprocess.list2cmdline(list(command))
        + "\n\nSTDOUT\n"
        + result.stdout
        + "\nSTDERR\n"
        + result.stderr
        + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode:
        raise Ac6007LongformBuildError(
            f"command failed ({result.returncode}); see {log_path}"
        )


def encode_args(crf: int, *, audio_copy: bool = False) -> list[str]:
    values = [
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-r", "30", "-fps_mode", "cfr",
    ]
    if audio_copy:
        values += ["-c:a", "copy"]
    else:
        values += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    return values + ["-movflags", "+faststart"]


def validate_authority(authority: Mapping[str, Any]) -> None:
    if (
        authority.get("schema") != "magireco-ac6007-exhaustive-native416-authority-v1"
        or authority.get("status") != "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER"
    ):
        raise Ac6007LongformBuildError("ac6007 authority is not production ready")
    expected_summary = {
        "dirinfo_routes": 5,
        "unique_complete_event_presentations": 10,
        "movie_layer_occurrences": 50,
        "unique_exact_cri_sources": 33,
        "contextual_reuse_occurrences": 17,
        "exact_duplicate_complete_presentations": 0,
        "retained_no_bgm_audio_occurrences": 39,
        "excluded_bgm_occurrences": 3,
        "subtitle_cues": EXPECTED_SUBTITLES,
        "normal_surface_events": 6,
        "full_surface_events": 4,
        "total_frames": EXPECTED_FRAMES,
    }
    summary = authority.get("summary", {})
    if any(summary.get(key) != value for key, value in expected_summary.items()):
        raise Ac6007LongformBuildError("ac6007 authority dimensions differ")
    order = list(authority.get("editorial_order", []))
    if len(order) != EXPECTED_EVENTS or set(order) != set(CHAPTER_TITLES):
        raise Ac6007LongformBuildError("ac6007 editorial event order differs")
    assertions = authority.get("assertions", {})
    required = {
        "all_5_dirinfo_routes_covered",
        "all_10_code_reachable_complete_event_presentations_once",
        "no_exact_duplicate_complete_presentations",
        "all_33_loadable_cri_sources_bound",
        "all_cri_sources_have_exact_color_alpha_streams",
        "all_normal_events_use_exact_gdp_top_zero_viewport",
        "all_full_surface_events_preserve_authored_pixels_by_contain",
    }
    if any(assertions.get(name) is not True for name in required):
        raise Ac6007LongformBuildError("required positive authority assertion failed")
    if (
        assertions.get("child_local_only_timing_occurrences") != 0
        or assertions.get("P16_P17_P18_references") != 0
        or assertions.get("with_bgm_occurrences") != 0
        or assertions.get("machine_vision_used_as_authority") is not False
    ):
        raise Ac6007LongformBuildError("fail-closed authority boundary differs")
    frames = sum(
        int(authority["event_manifests"][event]["presentation_frames"])
        for event in order
    )
    if frames != EXPECTED_FRAMES:
        raise Ac6007LongformBuildError("event frame sum differs")


def layer_filter_parts(
    input_index: int,
    layer_index: int,
    row: Mapping[str, Any],
    current: str,
) -> tuple[list[str], str]:
    source = row["source"]
    frame_count = int(source["frame_count"])
    if frame_count != int(row["event_end_frame_inclusive"]) - int(row["event_start_frame"]) + 1:
        raise Ac6007LongformBuildError("layer/source frame interval differs")
    if int(row["effective_renderer_state"]) != 1:
        raise Ac6007LongformBuildError("unsupported ac6007 renderer state")
    label = f"l{layer_index}"
    width = int(row["output_width"])
    height = int(row["output_height"])
    x = int(row["output_x"])
    y = int(row["output_y"])
    start_frame = int(row["event_start_frame"])
    scale = ""
    if (int(source["width"]), int(source["height"])) != (width, height):
        scale = f"scale={width}:{height}:flags=lanczos,"
    parts = [
        f"[{input_index}:v:0]format=rgb24,vflip,trim=end_frame={frame_count},"
        f"setpts=PTS-STARTPTS[{label}c]",
        f"[{input_index}:v:1]format=gray,vflip,trim=end_frame={frame_count},"
        f"setpts=PTS-STARTPTS[{label}a]",
        f"[{label}c][{label}a]alphamerge,{scale}"
        f"setpts=PTS-STARTPTS+{start_frame}/30/TB[{label}]",
    ]
    next_label = f"base{layer_index + 1}"
    parts += [
        f"[{current}]format=rgba[{label}base]",
        f"[{label}base][{label}]overlay={x}:{y}:eof_action=pass:repeatlast=0:"
        f"shortest=0:format=auto[{next_label}]",
    ]
    return parts, next_label


def render_event(
    ffmpeg: str,
    manifest: Mapping[str, Any],
    output: Path,
    log: Path,
) -> None:
    event = str(manifest["event"])
    layers = manifest["layers_in_render_pass_order_under_to_top"]
    audio = manifest["retained_audio"]
    visual_frames = int(manifest["visual_frames"])
    presentation_frames = int(manifest["presentation_frames"])
    if visual_frames > presentation_frames or not layers or not audio:
        raise Ac6007LongformBuildError(f"event composition dimensions differ: {event}")
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for row in layers:
        path = Path(str(row["source"]["path"]))
        if not path.is_file() or file_sha256(path) != row["source"]["sha256"]:
            raise Ac6007LongformBuildError(f"exact CRI source differs: {event}/{path}")
        command += ["-i", str(path)]
    for row in audio:
        path = Path(str(row["ogg_path"]))
        if not path.is_file():
            raise Ac6007LongformBuildError(f"official audio is absent: {event}/{path}")
        if row["volume_bus"] not in {"SE", "VOICE"}:
            raise Ac6007LongformBuildError(f"BGM leaked into event render: {event}")
        command += ["-i", str(path)]

    parts = [
        f"color=c=black:s=416x232:r=30:d={visual_frames / FPS:.9f},format=rgba[base0]"
    ]
    current = "base0"
    for index, row in enumerate(layers):
        filters, current = layer_filter_parts(index, index, row, current)
        parts += filters
    hold = presentation_frames - visual_frames
    if hold:
        parts.append(
            f"[{current}]tpad=stop_mode=clone:stop={hold},"
            f"trim=end_frame={presentation_frames},setpts=PTS-STARTPTS,format=yuv420p[v]"
        )
    else:
        parts.append(
            f"[{current}]trim=end_frame={presentation_frames},"
            "setpts=PTS-STARTPTS,format=yuv420p[v]"
        )

    first_audio_index = len(layers)
    audio_labels = []
    for index, row in enumerate(audio):
        label = f"a{index}"
        delay_samples = round(int(row["start_ms"]) * RATE / 1000)
        parts.append(
            f"[{first_audio_index + index}:a]aresample=48000,"
            "aformat=sample_rates=48000:channel_layouts=stereo,"
            f"adelay={delay_samples}S:all=1,asetpts=PTS-STARTPTS[{label}]"
        )
        audio_labels.append(f"[{label}]")
    samples = presentation_frames * SAMPLES_PER_FRAME
    parts.append(
        "".join(audio_labels)
        + f"amix=inputs={len(audio_labels)}:duration=longest:normalize=0,"
        f"apad=whole_len={samples},atrim=end_sample={samples},asetpts=PTS-STARTPTS[a]"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += encode_args(12) + [str(output)]
    run(command, log)


def write_chapters(path: Path, authority: Mapping[str, Any]) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    cursor = 0
    lines = [";FFMETADATA1"]
    for event in authority["editorial_order"]:
        frames = int(authority["event_manifests"][event]["presentation_frames"])
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
        raise Ac6007LongformBuildError("chapter timeline frame count differs")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chapters


def render_none_longform(
    ffmpeg: str,
    authority: Mapping[str, Any],
    event_media: Mapping[str, Path],
    metadata: Path,
    output: Path,
    log: Path,
) -> None:
    order = list(authority["editorial_order"])
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for event in order:
        command += ["-i", str(event_media[event])]
    command += ["-f", "ffmetadata", "-i", str(metadata)]
    parts = []
    for index, event in enumerate(order):
        frames = int(authority["event_manifests"][event]["presentation_frames"])
        samples = frames * SAMPLES_PER_FRAME
        parts += [
            f"[{index}:v]trim=end_frame={frames},setpts=PTS-STARTPTS[v{index}]",
            f"[{index}:a]atrim=end_sample={samples},asetpts=PTS-STARTPTS[a{index}]",
        ]
    chain = "".join(f"[v{i}][a{i}]" for i in range(len(order)))
    parts.append(f"{chain}concat=n={len(order)}:v=1:a=1[v][a]")
    metadata_index = len(order)
    output.parent.mkdir(parents=True, exist_ok=True)
    command += [
        "-filter_complex", ";".join(parts),
        "-map", "[v]", "-map", "[a]",
        "-map_metadata", str(metadata_index), "-map_chapters", str(metadata_index),
    ]
    command += encode_args(16) + [str(output)]
    run(command, log)


def frame_to_ms(frame: int) -> int:
    return round(frame * 1000 / FPS)


def global_subtitle_cues(authority: Mapping[str, Any], language: str) -> list[dict[str, Any]]:
    if language not in {"ja", "zh"}:
        raise Ac6007LongformBuildError(f"unsupported subtitle language: {language}")
    rows: list[dict[str, Any]] = []
    offset_frames = 0
    for event in authority["editorial_order"]:
        manifest = authority["event_manifests"][event]
        offset_ms = offset_frames * 1000 / FPS
        for cue in manifest["subtitles"]:
            start_ms = frame_to_ms(offset_frames + int(cue["start_frame"]))
            end_ms = round(offset_ms + int(cue["end_ms"]))
            if end_ms <= start_ms:
                raise Ac6007LongformBuildError(f"subtitle interval is empty: {event}")
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
        offset_frames += int(manifest["presentation_frames"])
    if len(rows) != EXPECTED_SUBTITLES or offset_frames != EXPECTED_FRAMES:
        raise Ac6007LongformBuildError("global subtitle timeline dimensions differ")
    return rows


def _ass_time(milliseconds: int) -> str:
    units = max(0, round(milliseconds / 10))
    hours, units = divmod(units, 360_000)
    minutes, units = divmod(units, 6_000)
    seconds, centiseconds = divmod(units, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _ass_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def write_ass(
    path: Path,
    authority: Mapping[str, Any],
    language: str,
    font_name: str,
) -> list[dict[str, Any]]:
    rows = global_subtitle_cues(authority, language)
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


def _filter_path(path: Path) -> str:
    value = path.resolve().as_posix().replace(":", "\\:")
    return value.replace("'", "\\'")


def burn_subtitles(
    ffmpeg: str,
    source: Path,
    subtitle: Path,
    fonts_dir: Path,
    output: Path,
    log: Path,
) -> None:
    video_filter = f"ass=filename='{_filter_path(subtitle)}':fontsdir='{_filter_path(fonts_dir)}'"
    command = [
        ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-vf", video_filter,
        "-map", "0:v:0", "-map", "0:a:0", "-map_metadata", "0", "-map_chapters", "0",
    ]
    command += encode_args(16, audio_copy=True) + [str(output)]
    output.parent.mkdir(parents=True, exist_ok=True)
    run(command, log)


def probe(ffprobe: str, path: Path, log: Path) -> dict[str, Any]:
    command = [
        ffprobe, "-v", "error", "-count_frames", "-show_streams",
        "-show_chapters", "-show_format", "-of", "json", str(path),
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" + result.stdout
        + "\nSTDERR\n" + result.stderr + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode:
        raise Ac6007LongformBuildError(f"ffprobe failed for {path}")
    return json.loads(result.stdout)


def validate_probe(value: Mapping[str, Any], *, chapters: int) -> dict[str, bool]:
    video = [row for row in value["streams"] if row["codec_type"] == "video"]
    audio = [row for row in value["streams"] if row["codec_type"] == "audio"]
    subtitles = [row for row in value["streams"] if row["codec_type"] == "subtitle"]
    checks = {
        "one_video": len(video) == 1,
        "one_audio": len(audio) == 1,
        "no_subtitle_stream": len(subtitles) == 0,
        "video_h264": len(video) == 1 and video[0].get("codec_name") == "h264",
        "canvas_416x232": len(video) == 1 and (int(video[0].get("width", 0)), int(video[0].get("height", 0))) == (416, 232),
        "frame_rate_30": len(video) == 1 and video[0].get("avg_frame_rate") == "30/1",
        "frame_count_3016": len(video) == 1 and int(video[0].get("nb_read_frames", -1)) == EXPECTED_FRAMES,
        "audio_aac": len(audio) == 1 and audio[0].get("codec_name") == "aac",
        "audio_48k": len(audio) == 1 and int(audio[0].get("sample_rate", 0)) == RATE,
        "audio_stereo": len(audio) == 1 and int(audio[0].get("channels", 0)) == 2,
        "chapter_count_10": len(value.get("chapters", [])) == chapters,
    }
    if not all(checks.values()):
        raise Ac6007LongformBuildError(f"media QA failed: {checks}")
    return checks


def decoded_audio_sha256(ffmpeg: str, path: Path, log: Path) -> str:
    command = [
        ffmpeg, "-nostdin", "-v", "error", "-i", str(path),
        "-map", "0:a:0", "-f", "hash", "-hash", "sha256", "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" + result.stdout
        + "\nSTDERR\n" + result.stderr + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode or not result.stdout.strip().startswith("SHA256="):
        raise Ac6007LongformBuildError(f"decoded audio hash failed: {path}")
    return result.stdout.strip().split("=", 1)[1].upper()


def review_path(output_root: Path, edition: str) -> Path:
    return (
        output_root / "HUMAN_REVIEW" / EDITIONS[edition] / "story"
        / f"ac6007_{TITLE}_严格无BGM__{edition}.mp4"
    )


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
        or len(manifest.get("ordered_events", [])) != EXPECTED_EVENTS
    ):
        raise Ac6007LongformBuildError("production manifest differs")
    media = []
    audio_hashes = set()
    for edition in EDITIONS:
        path = review_path(output_root, edition)
        if not path.is_file():
            raise Ac6007LongformBuildError(f"produced edition is absent: {path}")
        value = probe(ffprobe, path, output_root / "verification" / "commands" / f"probe_{edition}.txt")
        checks = validate_probe(value, chapters=EXPECTED_EVENTS)
        audio_hash = decoded_audio_sha256(
            ffmpeg, path, output_root / "verification" / "commands" / f"decoded_audio_hash_{edition}.txt"
        )
        audio_hashes.add(audio_hash)
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
                "decoded_audio_sha256": audio_hash,
                "automatic_qa": checks,
                "human_status": "HUMAN_PLAYBACK_REQUIRED",
            }
        )
    if len(audio_hashes) != 1:
        raise Ac6007LongformBuildError("none/JA/ZH decoded audio differs")
    if max(row["duration_seconds"] for row in media) - min(row["duration_seconds"] for row in media) > 0.001:
        raise Ac6007LongformBuildError("edition container durations differ")
    report = {
        "schema": "magireco-ac6007-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "dirinfo_route_coverage": "5/5",
        "ordered_unique_complete_event_presentations": 10,
        "exact_duplicate_complete_presentations": 0,
        "contextual_source_reuse_occurrences": 17,
        "native_416x232_output": True,
        "strict_no_bgm": True,
        "excluded_bgm_identity": {"request_id": 225, "sound_id": 550, "occurrences": 3},
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
    authority = read_json(args.authority)
    validate_authority(authority)
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise Ac6007LongformBuildError(f"immutable output already exists: {output_root}")
    staging = output_root.with_name(output_root.name + ".staging-" + uuid.uuid4().hex[:12])
    staging.mkdir(parents=True)
    try:
        logs = staging / "verification" / "commands"
        event_dir = staging / "intermediate" / "events"
        event_media: dict[str, Path] = {}
        for event in authority["editorial_order"]:
            target = event_dir / f"{event}.mp4"
            render_event(args.ffmpeg, authority["event_manifests"][event], target, logs / f"render_{event}.txt")
            value = probe(args.ffprobe, target, logs / f"probe_{event}.txt")
            video = [row for row in value["streams"] if row["codec_type"] == "video"]
            expected = int(authority["event_manifests"][event]["presentation_frames"])
            if len(video) != 1 or int(video[0].get("nb_read_frames", -1)) != expected:
                raise Ac6007LongformBuildError(f"event frame grid differs: {event}")
            event_media[event] = target

        metadata = staging / "manifests" / "chapters.ffmeta"
        chapters = write_chapters(metadata, authority)
        none = review_path(staging, "none")
        render_none_longform(args.ffmpeg, authority, event_media, metadata, none, logs / "render_none_longform.txt")
        ja_ass = staging / "manifests" / "ac6007_exhaustive_ja.ass"
        zh_ass = staging / "manifests" / "ac6007_exhaustive_zh.ass"
        ja_cues = write_ass(ja_ass, authority, "ja", args.ja_font_name)
        zh_cues = write_ass(zh_ass, authority, "zh", args.zh_font_name)
        ja = review_path(staging, "ja")
        zh = review_path(staging, "zh")
        burn_subtitles(args.ffmpeg, none, ja_ass, args.fonts_dir, ja, logs / "render_ja.txt")
        burn_subtitles(args.ffmpeg, none, zh_ass, args.fonts_dir, zh, logs / "render_zh.txt")

        manifest = {
            "schema": "magireco-ac6007-exhaustive-production-manifest-v1",
            "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
            "family": "ac6007",
            "title": TITLE,
            "content_group_count": 1,
            "edition_file_count": 3,
            "audio_profile": "no_bgm",
            "ordered_events": list(authority["editorial_order"]),
            "chapters": chapters,
            "subtitle_cue_count": {"ja": len(ja_cues), "zh": len(zh_cues)},
            "subtitle_translation_status": {
                "owner_approved_historical_wording_cues": sum(row["translation_status"] == "owner_playback_approved_in_p19" for row in zh_cues),
                "machine_draft_pending_owner_cues": sum(row["translation_status"] == "machine_draft_pending_owner" for row in zh_cues),
            },
            "authority": {"path": str(args.authority.resolve()), "sha256": file_sha256(args.authority)},
            "outputs": {
                "none": published(none, staging, output_root),
                "ja": published(ja, staging, output_root),
                "zh": published(zh, staging, output_root),
            },
            "native_single_session_claimed": False,
            "mutually_exclusive_routes_combined": True,
            "each_unique_complete_event_presentation_once": True,
            "human_playback_required": True,
            "publication_approved": False,
        }
        write_json(staging / "manifests" / "PRODUCTION_MANIFEST.json", manifest)
        (staging / "README.md").write_text(
            "# ac6007 exhaustive native-416 no-BGM longform\n\n"
            "One content group contains all five DirInfo routes as ten distinct complete "
            "event presentations in an understandable editorial order. NONE, JP and ZH are "
            "editions of the same 100.533-second group. Human playback is required.\n",
            encoding="utf-8",
        )
        (staging / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            "# 人工验收重点\n\n"
            "1. 依章节检查10段顺序是否自然，确认无整段重复或遗漏。\n"
            "2. 检查约0:07.6、0:17.6、0:23.6、0:31.6、0:38.8、0:46.8、1:00.8、1:15.6、1:25.3的事件边界。\n"
            "3. 重点核对所有20句开口、声音、JA/ZH字幕；新增胜利/复活台词仍待人工确认译文。\n"
            "4. 确认后四段左右黑边属于1280x1024完整画布的无裁切投影。\n"
            "5. 确认全片没有BGM，但保留对白、胜利文字音与已验证SE。\n",
            encoding="utf-8",
        )
        (staging / "UPLOAD_GUIDE.md").write_text(
            "# 上传指南（验收前暂停上传）\n\n"
            "- 内容组：1组；NONE/JA/ZH为同一内容的三种轨道。\n"
            "- 建议分P名：`女王熊袭击 全攻击·失败·胜利·复活穷尽合集 ac6007`；JA追加`__ja`；ZH追加` 中文版`。\n"
            "- 建议动作：人工播放通过后追加，不替换任何已投稿文件。\n"
            "- 目标：none `BV1rUKN6iEcj`；JA `BV1zQKN6eEC6`；ZH `BV13bKN6nEsd`（上传前由所有者核对当前BV）。\n"
            "- 自动QA：待本目录 `PRODUCTION_VERIFICATION.json`；人工状态：HUMAN_PLAYBACK_REQUIRED。\n"
            "- 明确排除：request225/sound550三次BGM、P16/P17/P18、child-local-only、with-BGM。\n",
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
    value.add_argument("--authority", required=True, type=Path)
    value.add_argument("--output-root", required=True, type=Path)
    value.add_argument("--fonts-dir", type=Path, default=Path(r"C:\Windows\Fonts"))
    value.add_argument("--ja-font-name", default="MS Gothic")
    value.add_argument("--zh-font-name", default="Microsoft YaHei")
    value.add_argument("--ffmpeg", default="ffmpeg")
    value.add_argument("--ffprobe", default="ffprobe")
    value.add_argument("--verify-existing", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.verify_existing:
        report = verify_production(args.output_root.resolve(), args.ffmpeg, args.ffprobe)
        print(f"PASS_VERIFY_EXISTING groups=1 editions=3 frames={EXPECTED_FRAMES} root={args.output_root.resolve()}")
    else:
        output = build(args)
        report = read_json(output / "PRODUCTION_VERIFICATION.json")
        print(
            f"PASS_RENDER groups=1 editions=3 frames={EXPECTED_FRAMES} "
            f"duration={report['media'][0]['duration_seconds']:.3f}s root={output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
