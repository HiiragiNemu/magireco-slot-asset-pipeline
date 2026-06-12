#!/usr/bin/env python3
"""Build native-resolution event samples from verified video, audio, and subtitle timing."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TimedAudio:
    path: Path
    start_ms: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--clip", action="append", required=True)
    parser.add_argument(
        "--audio",
        action="append",
        default=[],
        help="PATH@START_MS; may be repeated",
    )
    parser.add_argument("--subtitle-text", default="")
    parser.add_argument("--subtitle-start-ms", type=int, default=0)
    parser.add_argument("--subtitle-end-ms", type=int, default=0)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,r_frame_rate,pix_fmt,duration:"
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def parse_audio(value: str) -> TimedAudio:
    path_text, separator, start_text = value.rpartition("@")
    if not separator:
        raise ValueError(f"audio argument must use PATH@START_MS: {value}")
    return TimedAudio(Path(path_text).resolve(), int(start_text))


def srt_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(max(milliseconds, 0), 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def main() -> int:
    args = parse_args()
    clips = [Path(value).resolve() for value in args.clip]
    audios = [parse_audio(value) for value in args.audio]
    out_root = Path(args.out_root).resolve()
    without_dir = out_root / "without_subtitles"
    with_dir = out_root / "with_subtitles"
    subtitle_dir = out_root / "subtitles"
    work_dir = out_root / "_work"
    for directory in (without_dir, with_dir, subtitle_dir, work_dir):
        directory.mkdir(parents=True, exist_ok=True)

    clip_probes = [probe(path, args.ffprobe) for path in clips]
    video_streams = [
        next(stream for stream in item["streams"] if stream.get("codec_type") == "video")
        for item in clip_probes
    ]
    signatures = {
        (
            stream.get("width"),
            stream.get("height"),
            stream.get("r_frame_rate"),
            stream.get("pix_fmt"),
        )
        for stream in video_streams
    }
    if len(signatures) != 1:
        raise RuntimeError(f"input clips do not share native video parameters: {sorted(signatures)}")
    width, height, frame_rate, pixel_format = next(iter(signatures))
    event_duration = sum(float(item["format"]["duration"]) for item in clip_probes)

    video_only = work_dir / f"{args.event}__video_only.mp4"
    concat_inputs: list[str] = []
    concat_labels: list[str] = []
    for index, clip in enumerate(clips):
        concat_inputs.extend(["-i", str(clip)])
        concat_labels.append(f"[{index}:v:0]")
    concat_filter = "".join(concat_labels) + f"concat=n={len(clips)}:v=1:a=0[v]"
    run(
        [
            args.ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *concat_inputs,
            "-filter_complex",
            concat_filter,
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            str(pixel_format),
            "-movflags",
            "+faststart",
            str(video_only),
        ]
    )

    without_path = without_dir / f"{args.event}.mp4"
    audio_inputs: list[str] = []
    audio_filters: list[str] = []
    audio_labels: list[str] = []
    for index, audio in enumerate(audios, 1):
        audio_inputs.extend(["-i", str(audio.path)])
        label = f"a{index}"
        audio_filters.append(
            f"[{index}:a:0]adelay={audio.start_ms}:all=1,aresample=48000[{label}]"
        )
        audio_labels.append(f"[{label}]")

    if audios:
        audio_filters.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audios)}:duration=longest:normalize=0,"
            + f"alimiter=limit=0.95,apad=whole_dur={event_duration:.6f}[mix]"
        )
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_only),
                *audio_inputs,
                "-filter_complex",
                ";".join(audio_filters),
                "-map",
                "0:v:0",
                "-map",
                "[mix]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-t",
                f"{event_duration:.6f}",
                "-movflags",
                "+faststart",
                str(without_path),
            ]
        )
    else:
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_only),
                "-c",
                "copy",
                str(without_path),
            ]
        )

    subtitle_path = subtitle_dir / f"{args.event}.srt"
    with_path = with_dir / f"{args.event}__subtitles.mp4"
    if args.subtitle_text and args.subtitle_end_ms > args.subtitle_start_ms:
        subtitle_path.write_text(
            "1\n"
            f"{srt_timestamp(args.subtitle_start_ms)} --> "
            f"{srt_timestamp(args.subtitle_end_ms)}\n"
            f"{args.subtitle_text}\n",
            encoding="utf-8",
        )
        relative_subtitle = subtitle_path.relative_to(out_root).as_posix()
        subtitle_filter = (
            f"subtitles=filename='{relative_subtitle}':"
            "force_style='FontName=Yu Gothic,FontSize=16,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=1,Shadow=0,MarginV=12,Alignment=2'"
        )
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(without_path),
                "-vf",
                subtitle_filter,
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                str(pixel_format),
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(with_path),
            ],
            cwd=out_root,
        )

    outputs = {
        "event": args.event,
        "source_clips": [str(path) for path in clips],
        "source_video_signature": {
            "width": width,
            "height": height,
            "frame_rate": frame_rate,
            "pixel_format": pixel_format,
        },
        "event_duration_sec": event_duration,
        "audio": [{"path": str(item.path), "start_ms": item.start_ms} for item in audios],
        "subtitle": {
            "text": args.subtitle_text,
            "start_ms": args.subtitle_start_ms,
            "end_ms": args.subtitle_end_ms,
        },
        "without_subtitles": str(without_path),
        "with_subtitles": str(with_path) if with_path.exists() else "",
        "probe_without_subtitles": probe(without_path, args.ffprobe),
        "probe_with_subtitles": probe(with_path, args.ffprobe) if with_path.exists() else {},
    }
    (out_root / "manifest.json").write_text(
        json.dumps(outputs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
