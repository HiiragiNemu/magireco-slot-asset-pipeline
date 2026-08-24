#!/usr/bin/env python3
"""Render the evidence-bound native-416 ac0911 exhaustive longform."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

try:
    from tools.frida_runtime_probe.build_independent_scene_release import file_sha256
except ModuleNotFoundError:  # direct script execution from the repository root
    from build_independent_scene_release import file_sha256  # type: ignore


# hash=allow authority consumer=ac0911_manifest cost=3_outputs decision=bind_human_review_media
FPS = 30
RATE = 48_000
SAMPLES_PER_FRAME = RATE // FPS
EXPECTED_FRAMES = 5515
EDITIONS = {"none": "NONE", "ja": "JP", "zh": "ZH"}
TITLE = "黑江邀请彩羽前往神滨与挑战演出全部分支"
CHAPTER_TITLES = {
    "ac0911_001": "第一路线公共入口",
    "ac0911_002": "第一路线公共展开",
    "ac0911_003": "第一路线结局003",
    "ac0911_004": "第一路线结局004",
    "ac0911_005": "第一路线结局005",
    "ac0911_009": "第一路线HATTEN预告",
    "ac0911_017": "第一路线前兆预告",
    "ac0911_010": "第一路线CZ预告",
    "ac0911_011": "第一路线WIN预告",
    "ac0911_012": "第一路线PREMIA预告",
    "ac0911_006": "第二路线公共展开",
    "ac0911_007": "第二路线结局007",
    "ac0911_008": "第二路线结局008",
    "ac0911_013": "第二路线HATTEN结局",
    "ac0911_016": "第二路线前兆结局",
    "ac0911_014": "第二路线CZ结局",
    "ac0911_015": "第二路线WIN结局",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def published(path: Path, staging: Path, output_root: Path) -> str:
    try:
        return str(output_root / path.resolve().relative_to(staging.resolve()))
    except ValueError:
        return str(path.resolve())


def run(command: list[str], log_path: Path) -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" + result.stdout
        + "\nSTDERR\n" + result.stderr + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log_path}")


def encode_args(crf: int) -> list[str]:
    return [
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-r", "30", "-fps_mode", "cfr",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
    ]


def argb_filter(input_index: int, label: str, frame_count: int) -> list[str]:
    duration = frame_count / FPS
    return [
        f"[{input_index}:v:0]format=rgb24,vflip,setpts=PTS-STARTPTS[{label}c]",
        f"[{input_index}:v:1]format=gray,vflip,setpts=PTS-STARTPTS[{label}a]",
        f"[{label}c][{label}a]alphamerge,trim=end_frame={frame_count},setpts=PTS-STARTPTS[{label}rgba]",
        f"color=c=black:s=416x232:r=30:d={duration:.9f},format=rgba[{label}bg]",
        f"[{label}bg][{label}rgba]overlay=shortest=1:format=auto,format=yuv420p[{label}]",
    ]


def render_007(ffmpeg: str, authority: dict, output: Path, log: Path) -> None:
    artifacts = {row["official_name"]: Path(row["path"]) for row in authority["ac0911_007"]["cri_argb_sources"]}
    main = artifacts["ac0911_007_c09_MR"]
    loop = artifacts["ac0911_007_c09_LP_MR"]
    audio = Path(authority["ac0911_007"]["audio"][0]["source"]["path"])
    for item in (main, loop, audio):
        if not item.is_file():
            raise RuntimeError(f"missing ac0911_007 source: {item}")
    parts = argb_filter(0, "m", 75) + argb_filter(1, "l", 30)
    parts += [
        "[m][l]concat=n=2:v=1:a=0,tpad=stop_mode=clone:stop_duration=2,"
        "trim=end_frame=165,setpts=PTS-STARTPTS[v]",
        "[2:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
        "apad=whole_len=264000,atrim=end_sample=264000,asetpts=PTS-STARTPTS[a]",
    ]
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for item in (main, loop, audio):
        command += ["-i", str(item)]
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += encode_args(12) + [str(output)]
    run(command, log)


def write_chapters(path: Path, chapters: list[dict]) -> None:
    lines = [";FFMETADATA1"]
    for chapter in chapters:
        event = chapter["event"]
        lines += [
            "[CHAPTER]", "TIMEBASE=1/30",
            f"START={chapter['start_frame']}",
            f"END={chapter['end_frame_exclusive']}",
            f"title={CHAPTER_TITLES[event]} ({event})",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def chapter_sources(authority: dict, edition: str, event_007: Path) -> list[dict]:
    sources = []
    for chapter in authority["chapters"]:
        event = chapter["event"]
        if event == "ac0911_007":
            source = event_007
            start = 0
        elif event in authority["shared_exact_outcomes"]:
            source = Path(authority["shared_exact_outcomes"][event]["path"])
            start = 0
        else:
            row = authority["v75_event_segments"][event]
            source = Path(row["media"][edition]["path"])
            start = int(row["route_media_start_frame"])
        if not source.is_file():
            raise RuntimeError(f"missing chapter source for {event}/{edition}: {source}")
        sources.append({
            "event": event,
            "path": source,
            "start_frame": start,
            "end_frame_exclusive": start + int(chapter["frames"]),
            "frames": int(chapter["frames"]),
        })
    return sources


def render_final(
    ffmpeg: str,
    sources: list[dict],
    metadata: Path,
    output: Path,
    log: Path,
) -> None:
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for row in sources:
        command += ["-i", str(row["path"])]
    command += ["-f", "ffmetadata", "-i", str(metadata)]
    parts = []
    for index, row in enumerate(sources):
        start = row["start_frame"]
        end = row["end_frame_exclusive"]
        start_sample = start * SAMPLES_PER_FRAME
        end_sample = end * SAMPLES_PER_FRAME
        parts += [
            f"[{index}:v]trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS[v{index}]",
            f"[{index}:a]atrim=start_sample={start_sample}:end_sample={end_sample},asetpts=PTS-STARTPTS[a{index}]",
        ]
    chain = "".join(f"[v{i}][a{i}]" for i in range(len(sources)))
    parts.append(f"{chain}concat=n={len(sources)}:v=1:a=1[v][a]")
    command += [
        "-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
        "-map_metadata", str(len(sources)),
    ]
    command += encode_args(18) + [str(output)]
    run(command, log)


def probe(ffprobe: str, media: Path, log: Path) -> dict:
    command = [
        ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_chapters",
        "-show_format", "-of", "json", str(media),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" + result.stdout
        + "\nSTDERR\n" + result.stderr + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(f"probe failed for {media}")
    return json.loads(result.stdout)


def validate_probe(value: dict) -> dict:
    video = [stream for stream in value["streams"] if stream["codec_type"] == "video"]
    audio = [stream for stream in value["streams"] if stream["codec_type"] == "audio"]
    checks = {
        "one_video": len(video) == 1,
        "one_audio": len(audio) == 1,
        "video_h264": len(video) == 1 and video[0].get("codec_name") == "h264",
        "canvas_416x232": len(video) == 1 and (video[0].get("width"), video[0].get("height")) == (416, 232),
        "frame_rate_30": len(video) == 1 and video[0].get("avg_frame_rate") == "30/1",
        "frame_count_5515": len(video) == 1 and int(video[0].get("nb_read_frames", -1)) == EXPECTED_FRAMES,
        "audio_aac": len(audio) == 1 and audio[0].get("codec_name") == "aac",
        "audio_48k": len(audio) == 1 and int(audio[0].get("sample_rate", 0)) == RATE,
        "audio_stereo": len(audio) == 1 and int(audio[0].get("channels", 0)) == 2,
        "chapter_count_17": len(value.get("chapters", [])) == 17,
    }
    if not all(checks.values()):
        raise RuntimeError(f"media QA failed: {checks}")
    return checks


def validate_authority(authority: dict) -> None:
    if authority.get("status") != "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER":
        raise RuntimeError("authority is not production ready")
    if authority.get("route_count") != 14 or authority.get("event_container_count") != 17:
        raise RuntimeError("route/event universe changed")
    if authority.get("canonical_presentation_count") != 17 or authority.get("exact_duplicate_surplus_count") != 0:
        raise RuntimeError("duplicate-free presentation contract changed")
    if authority.get("total_frames") != EXPECTED_FRAMES or len(authority.get("chapters", [])) != 17:
        raise RuntimeError("timeline contract changed")
    if authority.get("strict_no_bgm", {}).get("excluded_sound_ids") != [551, 552, 553]:
        raise RuntimeError("strict no-BGM contract changed")
    assertions = authority.get("automatic_assertions", {})
    required_true = {
        "all_14_dirinfo_routes_covered",
        "all_17_event_containers_covered_once",
        "runtime_all_events_same_bounded_capture",
        "runtime_process_and_map_guards_passed",
        "parent_audio_and_runtime_sound_sets_agree",
        "exact_cri_argb_sources_resolved_for_007",
        "bgm_551_552_553_excluded",
        "P16_P17_P18_not_referenced",
    }
    if any(assertions.get(name) is not True for name in required_true):
        raise RuntimeError("required positive authority assertion failed")
    if assertions.get("machine_vision_used_as_authority") is not False:
        raise RuntimeError("machine vision authority flag changed")


def build(args: argparse.Namespace) -> Path:
    authority = read_json(args.authority)
    validate_authority(authority)
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise RuntimeError(f"immutable output already exists: {output_root}")
    staging = output_root.with_name(output_root.name + ".staging-" + uuid.uuid4().hex[:12])
    staging.mkdir(parents=True)
    try:
        logs = staging / "verification" / "commands"
        intermediate = staging / "intermediate"
        intermediate.mkdir(parents=True)
        event_007 = intermediate / "ac0911_007_exact_argb_no_bgm.mp4"
        render_007(args.ffmpeg, authority, event_007, logs / "render_007.txt")
        check_007 = probe(args.ffprobe, event_007, logs / "probe_007.txt")
        video_007 = next(stream for stream in check_007["streams"] if stream["codec_type"] == "video")
        if int(video_007.get("nb_read_frames", -1)) != 165:
            raise RuntimeError("ac0911_007 presentation does not contain 165 frames")

        metadata = staging / "manifests" / "chapters.ffmeta"
        write_chapters(metadata, authority["chapters"])
        outputs = []
        edition_sources = {}
        for edition, folder in EDITIONS.items():
            target_dir = staging / "HUMAN_REVIEW" / folder / "story"
            target_dir.mkdir(parents=True)
            target = target_dir / f"ac0911_{TITLE}_严格无BGM__{edition}.mp4"
            sources = chapter_sources(authority, edition, event_007)
            render_final(args.ffmpeg, sources, metadata, target, logs / f"render_final_{edition}.txt")
            checks = validate_probe(probe(args.ffprobe, target, logs / f"probe_final_{edition}.txt"))
            outputs.append({
                "edition": edition,
                "path": published(target, staging, output_root),
                "sha256": file_sha256(target),
                "bytes": target.stat().st_size,
                "automatic_qa": checks,
                "human_status": "HUMAN_PLAYBACK_REQUIRED",
                "publication_approved": False,
            })
            edition_sources[edition] = [
                {
                    **{key: row[key] for key in ("event", "start_frame", "end_frame_exclusive", "frames")},
                    "path": published(row["path"], staging, output_root),
                }
                for row in sources
            ]

        manifest = {
            "schema": "ac0911_exhaustive_authoritative_longform_v1",
            "status": "AUTOMATED_QA_PASS_HUMAN_PLAYBACK_REQUIRED",
            "family": "ac0911",
            "title": TITLE,
            "product_semantics": "editorial_exhaustive_collection_not_native_single_session",
            "audio_profile": "strict_no_bgm_retains_verified_voice_and_se",
            "canvas": [416, 232],
            "frame_rate": FPS,
            "frames": EXPECTED_FRAMES,
            "duration_seconds": EXPECTED_FRAMES / FPS,
            "dirinfo_route_count": 14,
            "event_container_count": 17,
            "canonical_presentation_count": 17,
            "exact_duplicate_surplus_count": 0,
            "chapters": authority["chapters"],
            "authority": {"path": str(args.authority.resolve()), "sha256": file_sha256(args.authority)},
            "edition_source_inputs": edition_sources,
            "outputs": outputs,
            "excluded": {
                "bgm_sound_ids": [551, 552, 553],
                "blocked_families": ["ac6003", "ac6004", "ac6005"],
            },
        }
        write_json(staging / "manifests" / "PRODUCTION_MANIFEST.json", manifest)
        sums = [
            {
                "path": str(Path(row["path"]).relative_to(output_root)).replace("\\", "/"),
                "sha256": row["sha256"],
                "bytes": row["bytes"],
            }
            for row in outputs
        ]
        write_json(staging / "manifests" / "SHA256SUMS.json", {"files": sums})
        write_json(staging / "verification" / "VERIFICATION_RECORD.json", {
            "status": "PASS",
            "output_count": 3,
            "content_group_count": 1,
            "literal_result": "PASS outputs=3 groups=1 routes=14 events=17 unique_presentations=17 frames_each=5515 chapters_each=17 canvas=416x232 fps=30 audio=aac_48000_stereo bgm_leak=0 blocked_leak=0",
        })
        (staging / "00_START_HERE.md").write_text(
            "# ac0911 穷尽长片人工验收\n\n"
            "这是一个内容组，NONE/JP/ZH 是同一时间线的三个版本。\n\n"
            "- 覆盖全部 14 条 DirInfo 路线与 17 个代码级不同事件容器。\n"
            "- 每个事件呈现一次，不重复公共入口；总长 5515 帧 / 183.833 秒。\n"
            "- 原生 416×232、30fps、H.264/AAC 48kHz stereo，无 upscale。\n"
            "- BGM 551/552/553 已排除，保留 runtime 与 parent request 同时验证的 SE。\n"
            "- 建议重点检查 001→002 分支组、006→007/008 分支组，以及最后四个结局。\n"
            "- 自动 QA 通过不等于人工播放批准。\n",
            encoding="utf-8",
        )
        (staging / "ROLLBACK.ps1").write_text(
            "$ErrorActionPreference='Stop'\n"
            "$root=Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'\n"
            "Move-Item -LiteralPath $root -Destination ($root+'.withdrawn_'+$stamp)\n",
            encoding="utf-8",
        )
        (staging / "READY").write_text("AUTOMATED_QA_PASS_HUMAN_PLAYBACK_REQUIRED\n", encoding="utf-8")
        os.replace(staging, output_root)
        print("PASS outputs=3 groups=1 routes=14 events=17 frames=5515")
        return output_root
    except BaseException:
        (staging / "FAILED_BUILD.txt").write_text("Build failed; staging retained for diagnosis.\n", encoding="utf-8")
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--authority", type=Path, required=True)
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--ffmpeg", default="ffmpeg")
    value.add_argument("--ffprobe", default="ffprobe")
    return value


def main() -> int:
    try:
        build(parser().parse_args())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
