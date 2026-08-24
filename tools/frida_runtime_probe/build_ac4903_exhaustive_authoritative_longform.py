#!/usr/bin/env python3
"""Render the exact native-416 ac4903 exhaustive no-BGM longform."""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_manual_review_hub import file_sha256
except ImportError:  # pragma: no cover - direct script execution
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_manual_review_hub import file_sha256


FPS = 30
RATE = 48_000
SAMPLES_PER_FRAME = RATE // FPS
EXPECTED_FRAMES = 4204
EXPECTED_EVENTS = 16
EDITIONS = {"none": "NONE", "ja": "JP", "zh": "ZH"}
TITLE = "Magius作战会议全部选择与胜利穷尽合集"
CHAPTER_TITLES = {
    "ac4903_001": "Magius监视器公共入口",
    "ac4903_002": "柊音梦弱告知分支",
    "ac4903_003": "柊音梦强告知分支",
    "ac4903_004": "音梦与灯花进入战场",
    "ac4903_005": "里见灯花弱告知分支",
    "ac4903_006": "里见灯花强告知分支",
    "ac4903_007": "轮盘砂岚入口一",
    "ac4903_008": "三人监视器结果",
    "ac4903_009": "由两人执行",
    "ac4903_010": "由梓美冬执行",
    "ac4903_011": "由比鹤乃分支",
    "ac4903_012": "Magius亲自执行",
    "ac4903_013": "巴麻美分支",
    "ac4903_016": "轮盘砂岚入口二",
    "ac4903_018": "轮盘砂岚入口三",
    "ac4903_015": "胜利与目标上钩",
}


class Ac4903BuildError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def published(path: Path, staging: Path, output_root: Path) -> str:
    return str(output_root / path.resolve().relative_to(staging.resolve()))


def run(command: Sequence[str], log_path: Path) -> None:
    result = subprocess.run(
        list(command), capture_output=True, text=True, encoding="utf-8", errors="replace"
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
        raise Ac4903BuildError(
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
        authority.get("schema")
        != "magireco-ac4903-exhaustive-native416-authority-v1"
        or authority.get("status")
        != "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER"
    ):
        raise Ac4903BuildError("ac4903 authority is not production ready")
    summary = authority.get("summary", {})
    expected = {
        "dirinfo_routes": 22,
        "unique_complete_event_presentations": 16,
        "authored_movie_layer_occurrences": 41,
        "loadable_movie_layer_occurrences": 39,
        "unique_loadable_cri_identities": 35,
        "code_unreachable_alias_occurrences": 2,
        "retained_no_bgm_audio_occurrences": 28,
        "excluded_bgm_occurrences": 7,
        "subtitle_cues": 12,
        "total_frames": EXPECTED_FRAMES,
    }
    if any(summary.get(key) != value for key, value in expected.items()):
        raise Ac4903BuildError("ac4903 authority dimensions differ")
    if authority.get("editorial_order", [])[-3:] != [
        "ac4903_016", "ac4903_018", "ac4903_015"
    ]:
        raise Ac4903BuildError("victory is not last in the editorial order")
    assertions = authority.get("assertions", {})
    required = {
        "all_22_dirinfo_routes_covered",
        "all_16_complete_event_presentations_once",
        "no_exact_duplicate_complete_presentations",
        "all_35_loadable_cri_sources_bound",
        "all_cri_sources_have_exact_color_alpha_streams",
        "renderer_state_1_and_3_code_closed",
    }
    if any(assertions.get(name) is not True for name in required):
        raise Ac4903BuildError("required positive authority assertion failed")
    if (
        assertions.get("child_local_only_timing_occurrences") != 0
        or assertions.get("P16_P17_P18_references") != 0
        or assertions.get("machine_vision_used_as_authority") is not False
    ):
        raise Ac4903BuildError("fail-closed authority boundary differs")


def _layer_filters(
    input_index: int,
    layer_index: int,
    row: Mapping[str, Any],
    visual_frames: int,
    current: str,
) -> tuple[list[str], str]:
    label = f"l{layer_index}"
    source = row["source"]
    frame_count = int(source["frame_count"])
    start_frame = int(row["event_start_frame"])
    parts = [
        f"[{input_index}:v:0]format=rgb24,vflip,trim=end_frame={frame_count},"
        f"setpts=PTS-STARTPTS[{label}c]",
        f"[{input_index}:v:1]format=gray,vflip,trim=end_frame={frame_count},"
        f"setpts=PTS-STARTPTS[{label}a]",
    ]
    scale = ""
    if (int(source["width"]), int(source["height"])) != (416, 232):
        scale = "scale=416:232:flags=lanczos,"
    parts.append(
        f"[{label}c][{label}a]alphamerge,{scale}"
        f"setpts=PTS-STARTPTS+{start_frame}/30/TB[{label}]"
    )
    next_label = f"base{layer_index + 1}"
    state = int(row["effective_renderer_state"])
    if state == 1:
        parts += [
            f"[{current}]format=rgba[{label}base]",
            f"[{label}base][{label}]overlay=0:0:eof_action=pass:repeatlast=0:"
            f"shortest=0:format=auto[{next_label}]",
        ]
    elif state == 3:
        duration = visual_frames / FPS
        parts += [
            f"color=c=black:s=416x232:r=30:d={duration:.9f},format=rgba[{label}black]",
            f"[{label}black][{label}]overlay=0:0:eof_action=pass:repeatlast=0:"
            f"shortest=0:format=auto[{label}premul]",
            f"[{current}]format=gbrp[{label}base]",
            f"[{label}premul]format=gbrp[{label}add]",
            f"[{label}base][{label}add]blend=all_mode=addition:shortest=1[{next_label}]",
        ]
    else:
        raise Ac4903BuildError(f"unsupported exact renderer state: {state}")
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
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for row in layers:
        path = Path(str(row["source"]["path"]))
        if not path.is_file():
            raise Ac4903BuildError(f"missing CRI source: {event}/{path}")
        command += ["-i", str(path)]
    for row in audio:
        path = Path(str(row["ogg_path"]))
        if not path.is_file():
            raise Ac4903BuildError(f"missing official audio: {event}/{path}")
        command += ["-i", str(path)]
    parts = [
        f"color=c=black:s=416x232:r=30:d={visual_frames / FPS:.9f},"
        "format=rgba[base0]"
    ]
    current = "base0"
    for index, row in enumerate(layers):
        filters, current = _layer_filters(index, index, row, visual_frames, current)
        parts += filters
    hold = presentation_frames - visual_frames
    if hold:
        parts.append(
            f"[{current}]tpad=stop_mode=clone:stop={hold},"
            f"trim=end_frame={presentation_frames},setpts=PTS-STARTPTS,"
            "format=yuv420p[v]"
        )
    else:
        parts.append(
            f"[{current}]trim=end_frame={presentation_frames},"
            "setpts=PTS-STARTPTS,format=yuv420p[v]"
        )
    audio_labels = []
    first_audio_index = len(layers)
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
        f"apad=whole_len={samples},atrim=end_sample={samples},"
        "asetpts=PTS-STARTPTS[a]"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += encode_args(12) + [str(output)]
    run(command, log)


def write_chapters(path: Path, authority: Mapping[str, Any]) -> list[dict[str, Any]]:
    chapters = []
    cursor = 0
    lines = [";FFMETADATA1"]
    for event in authority["editorial_order"]:
        frames = int(authority["event_manifests"][event]["presentation_frames"])
        chapter = {
            "event": event,
            "start_frame": cursor,
            "end_frame_exclusive": cursor + frames,
            "title": CHAPTER_TITLES[event],
        }
        chapters.append(chapter)
        lines += [
            "[CHAPTER]", "TIMEBASE=1/30", f"START={cursor}",
            f"END={cursor + frames}", f"title={CHAPTER_TITLES[event]} ({event})",
        ]
        cursor += frames
    if cursor != EXPECTED_FRAMES:
        raise Ac4903BuildError("chapter timeline frame count differs")
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
        "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
        "-map_metadata", str(metadata_index), "-map_chapters", str(metadata_index),
    ]
    command += encode_args(16) + [str(output)]
    run(command, log)


def frame_to_ms(frame: int) -> int:
    return round(frame * 1000 / FPS)


def _ass_time(milliseconds: int) -> str:
    units = max(0, round(milliseconds / 10))
    hours, units = divmod(units, 360_000)
    minutes, units = divmod(units, 6_000)
    seconds, centiseconds = divmod(units, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _ass_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def global_subtitle_cues(
    authority: Mapping[str, Any], language: str
) -> list[dict[str, Any]]:
    if language not in {"ja", "zh"}:
        raise Ac4903BuildError(f"unsupported subtitle language: {language}")
    rows = []
    offset_frames = 0
    for event in authority["editorial_order"]:
        manifest = authority["event_manifests"][event]
        offset_ms = offset_frames * 1000 / FPS
        for cue in manifest["subtitles"]:
            start_ms = frame_to_ms(offset_frames + int(cue["start_frame"]))
            end_ms = round(offset_ms + int(cue["end_ms"]))
            if end_ms <= start_ms:
                raise Ac4903BuildError(f"subtitle interval is empty: {event}")
            rows.append({
                "event": event,
                "request_id": int(cue["voice_request_id"]),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": str(cue[language]),
            })
        offset_frames += int(manifest["presentation_frames"])
    if len(rows) != 12 or offset_frames != EXPECTED_FRAMES:
        raise Ac4903BuildError("global subtitle timeline dimensions differ")
    return rows


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
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
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
    video_filter = (
        f"ass=filename='{_filter_path(subtitle)}':"
        f"fontsdir='{_filter_path(fonts_dir)}'"
    )
    command = [
        ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-vf", video_filter,
        "-map", "0:v:0", "-map", "0:a:0", "-map_metadata", "0",
        "-map_chapters", "0",
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
        "COMMAND\n"
        + subprocess.list2cmdline(command)
        + "\n\nSTDOUT\n"
        + result.stdout
        + "\nSTDERR\n"
        + result.stderr
        + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode:
        raise Ac4903BuildError(f"ffprobe failed for {path}")
    return json.loads(result.stdout)


def validate_probe(value: Mapping[str, Any], *, chapters: int) -> dict[str, bool]:
    video = [row for row in value["streams"] if row["codec_type"] == "video"]
    audio = [row for row in value["streams"] if row["codec_type"] == "audio"]
    checks = {
        "one_video": len(video) == 1,
        "one_audio": len(audio) == 1,
        "video_h264": len(video) == 1 and video[0].get("codec_name") == "h264",
        "canvas_416x232": len(video) == 1
        and (int(video[0].get("width", 0)), int(video[0].get("height", 0)))
        == (416, 232),
        "frame_rate_30": len(video) == 1
        and video[0].get("avg_frame_rate") == "30/1",
        "frame_count_4204": len(video) == 1
        and int(video[0].get("nb_read_frames", -1)) == EXPECTED_FRAMES,
        "audio_aac": len(audio) == 1 and audio[0].get("codec_name") == "aac",
        "audio_48k": len(audio) == 1
        and int(audio[0].get("sample_rate", 0)) == RATE,
        "audio_stereo": len(audio) == 1 and int(audio[0].get("channels", 0)) == 2,
        "chapter_count_16": len(value.get("chapters", [])) == chapters,
    }
    if not all(checks.values()):
        raise Ac4903BuildError(f"media QA failed: {checks}")
    return checks


def verify_production(
    output_root: Path, ffprobe: str, *, write_report: bool = True
) -> dict[str, Any]:
    manifest = read_json(output_root / "manifests" / "PRODUCTION_MANIFEST.json")
    if (
        manifest.get("status")
        != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or manifest.get("content_group_count") != 1
        or manifest.get("edition_file_count") != 3
        or manifest.get("ordered_events", [])[-3:]
        != ["ac4903_016", "ac4903_018", "ac4903_015"]
    ):
        raise Ac4903BuildError("production manifest differs")
    media = []
    for edition, folder in EDITIONS.items():
        path = (
            output_root
            / "HUMAN_REVIEW"
            / folder
            / "story"
            / f"ac4903_{TITLE}_严格无BGM__{edition}.mp4"
        )
        if not path.is_file():
            raise Ac4903BuildError(f"produced edition is absent: {path}")
        value = probe(
            ffprobe, path, output_root / "verification" / "commands" / f"probe_{edition}.txt"
        )
        checks = validate_probe(value, chapters=EXPECTED_EVENTS)
        media.append({
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
            "automatic_qa": checks,
            "human_status": "HUMAN_PLAYBACK_REQUIRED",
        })
    if max(row["duration_seconds"] for row in media) - min(
        row["duration_seconds"] for row in media
    ) > 0.001:
        raise Ac4903BuildError("edition container durations differ")
    report = {
        "schema": "magireco-ac4903-exhaustive-production-verification-v1",
        "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
        "content_group_count": 1,
        "edition_file_count": 3,
        "dirinfo_route_coverage": "22/22",
        "ordered_unique_event_presentations": 16,
        "exact_duplicate_event_presentation_count": 0,
        "native_416x232_only": True,
        "strict_no_bgm": True,
        "blocked_p16_p17_p18_leak_count": 0,
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
        raise Ac4903BuildError(f"immutable output already exists: {output_root}")
    staging = output_root.with_name(output_root.name + ".staging-" + uuid.uuid4().hex[:12])
    staging.mkdir(parents=True)
    try:
        logs = staging / "verification" / "commands"
        event_dir = staging / "intermediate" / "events"
        event_media: dict[str, Path] = {}
        for event in authority["editorial_order"]:
            target = event_dir / f"{event}.mp4"
            render_event(
                args.ffmpeg,
                authority["event_manifests"][event],
                target,
                logs / f"render_{event}.txt",
            )
            value = probe(args.ffprobe, target, logs / f"probe_{event}.txt")
            video = [row for row in value["streams"] if row["codec_type"] == "video"]
            expected = int(authority["event_manifests"][event]["presentation_frames"])
            if len(video) != 1 or int(video[0].get("nb_read_frames", -1)) != expected:
                raise Ac4903BuildError(f"event frame grid differs: {event}")
            event_media[event] = target

        metadata = staging / "manifests" / "chapters.ffmeta"
        chapters = write_chapters(metadata, authority)
        none = (
            staging / "HUMAN_REVIEW" / "NONE" / "story"
            / f"ac4903_{TITLE}_严格无BGM__none.mp4"
        )
        render_none_longform(
            args.ffmpeg,
            authority,
            event_media,
            metadata,
            none,
            logs / "render_none_longform.txt",
        )
        ja_ass = staging / "manifests" / "ac4903_exhaustive_ja.ass"
        zh_ass = staging / "manifests" / "ac4903_exhaustive_zh.ass"
        ja_cues = write_ass(ja_ass, authority, "ja", args.ja_font_name)
        zh_cues = write_ass(zh_ass, authority, "zh", args.zh_font_name)
        ja = (
            staging / "HUMAN_REVIEW" / "JP" / "story"
            / f"ac4903_{TITLE}_严格无BGM__ja.mp4"
        )
        zh = (
            staging / "HUMAN_REVIEW" / "ZH" / "story"
            / f"ac4903_{TITLE}_严格无BGM__zh.mp4"
        )
        burn_subtitles(
            args.ffmpeg, none, ja_ass, args.fonts_dir, ja, logs / "render_ja.txt"
        )
        burn_subtitles(
            args.ffmpeg, none, zh_ass, args.fonts_dir, zh, logs / "render_zh.txt"
        )
        manifest = {
            "schema": "magireco-ac4903-exhaustive-production-manifest-v1",
            "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
            "family": "ac4903",
            "title": TITLE,
            "content_group_count": 1,
            "edition_file_count": 3,
            "audio_profile": "no_bgm",
            "ordered_events": list(authority["editorial_order"]),
            "chapters": chapters,
            "subtitle_cue_count": {"ja": len(ja_cues), "zh": len(zh_cues)},
            "authority": str(args.authority.resolve()),
            "outputs": {
                "none": published(none, staging, output_root),
                "ja": published(ja, staging, output_root),
                "zh": published(zh, staging, output_root),
            },
            "natural_single_session_claimed": False,
            "mutually_exclusive_routes_combined": True,
            "each_unique_complete_event_presentation_once": True,
            "human_playback_required": True,
            "publication_approved": False,
        }
        write_json(staging / "manifests" / "PRODUCTION_MANIFEST.json", manifest)
        (staging / "README.md").write_text(
            "# ac4903 exhaustive native-416 no-BGM longform\n\n"
            "One content group contains all 22 DirInfo routes as 16 unique complete "
            "event presentations in an understandable editorial order, with victory "
            "last. NONE, JP and ZH are editions of the same group. Human playback is "
            "required before publication.\n",
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
            encoding="utf-8",
        )
        staging.replace(output_root)
        verify_production(output_root, args.ffprobe)
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
        report = verify_production(args.output_root.resolve(), args.ffprobe)
        print(
            f"PASS_VERIFY_EXISTING groups=1 editions=3 frames={EXPECTED_FRAMES} "
            f"root={args.output_root.resolve()}"
        )
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
