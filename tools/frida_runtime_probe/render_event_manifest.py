#!/usr/bin/env python3
"""Render one verified event manifest at its native video dimensions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
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
            "stream=codec_name,codec_type,width,height,r_frame_rate,pix_fmt,"
            "sample_rate,channels,duration:format=duration,size",
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def srt_time(milliseconds: int) -> str:
    value = max(milliseconds, 0)
    hours, value = divmod(value, 3_600_000)
    minutes, value = divmod(value, 60_000)
    seconds, millis = divmod(value, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    event = manifest["event"]
    gates = manifest.get("quality_gates", {})
    if not gates.get("ready"):
        raise SystemExit(
            f"manifest is not ready: {', '.join(gates.get('errors', []))}"
        )
    if manifest.get("classification") != "native_full_frame_only":
        raise SystemExit("refusing to render non-full-frame event")

    out_root = Path(args.out_root).resolve() / event
    without_dir = out_root / "without_subtitles"
    with_dir = out_root / "with_subtitles"
    subtitle_dir = out_root / "subtitles"
    work_dir = out_root / "_work"
    for directory in (without_dir, with_dir, subtitle_dir, work_dir):
        directory.mkdir(parents=True, exist_ok=True)

    without_path = without_dir / f"{event}.mp4"
    with_path = with_dir / f"{event}__subtitles.mp4"
    output_manifest_path = out_root / "render_manifest.json"
    existing = [
        path
        for path in (without_path, with_path, output_manifest_path)
        if path.exists()
    ]
    if existing and not args.overwrite:
        raise SystemExit(
            "refusing to overwrite existing output: "
            + ", ".join(str(path) for path in existing)
        )

    clips = [Path(row["path"]).resolve() for row in manifest["clips"]]
    clip_probes = [probe(path, args.ffprobe) for path in clips]
    signatures = set()
    for item in clip_probes:
        stream = next(
            stream
            for stream in item["streams"]
            if stream.get("codec_type") == "video"
        )
        signatures.add(
            (
                stream.get("width"),
                stream.get("height"),
                stream.get("r_frame_rate"),
                stream.get("pix_fmt"),
            )
        )
    if len(signatures) != 1:
        raise SystemExit(f"source signature mismatch: {sorted(signatures)}")
    width, height, frame_rate, pixel_format = next(iter(signatures))
    expected = manifest["native_dimensions"]
    if width != expected["width"] or height != expected["height"]:
        raise SystemExit(
            f"native dimension mismatch: source={width}x{height}, "
            f"manifest={expected['width']}x{expected['height']}"
        )
    if frame_rate != manifest["native_frame_rate"]:
        raise SystemExit(
            f"native frame-rate mismatch: source={frame_rate}, "
            f"manifest={manifest['native_frame_rate']}"
        )

    base_video_only = work_dir / f"{event}__base_video_only.mp4"
    video_only = work_dir / f"{event}__video_only.mp4"
    video_inputs: list[str] = []
    video_labels: list[str] = []
    for index, clip in enumerate(clips):
        video_inputs.extend(["-i", str(clip)])
        video_labels.append(f"[{index}:v:0]")
    run(
        [
            args.ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *video_inputs,
            "-filter_complex",
            "".join(video_labels)
            + f"concat=n={len(clips)}:v=1:a=0[v]",
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
            str(base_video_only),
        ]
    )

    render_duration_ms = int(
        manifest.get("render_duration_ms", manifest["video_duration_ms"])
    )
    extension_ms = max(0, render_duration_ms - int(manifest["video_duration_ms"]))
    extension_policy = manifest.get("video_extension_policy", "none")
    if extension_ms == 0:
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(base_video_only),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                str(video_only),
            ]
        )
    elif extension_policy == "loop_last_clip":
        extension_path = work_dir / f"{event}__loop_extension.mp4"
        extension_sec = extension_ms / 1000.0
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-stream_loop",
                "-1",
                "-i",
                str(clips[-1]),
                "-an",
                "-t",
                f"{extension_sec:.6f}",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                str(pixel_format),
                str(extension_path),
            ]
        )
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(base_video_only),
                "-i",
                str(extension_path),
                "-filter_complex",
                "[0:v:0][1:v:0]concat=n=2:v=1:a=0[v]",
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
                str(video_only),
            ]
        )
    elif extension_policy == "hold_last_frame":
        extension_sec = extension_ms / 1000.0
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(base_video_only),
                "-vf",
                f"tpad=stop_mode=clone:stop_duration={extension_sec:.6f}",
                "-an",
                "-t",
                f"{render_duration_ms / 1000.0:.6f}",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                str(pixel_format),
                str(video_only),
            ]
        )
    else:
        raise SystemExit(
            f"unsupported video extension policy: {extension_policy} "
            f"for {extension_ms} ms"
        )

    audio = manifest["audio"]
    audio_inputs: list[str] = []
    audio_filters: list[str] = []
    audio_labels: list[str] = []
    for index, row in enumerate(audio, 1):
        audio_inputs.extend(["-i", str(Path(row["path"]).resolve())])
        label = f"a{index}"
        audio_filters.append(
            f"[{index}:a:0]adelay={int(row['start_ms'])}:all=1,"
            f"aresample=48000[{label}]"
        )
        audio_labels.append(f"[{label}]")
    video_duration_sec = render_duration_ms / 1000.0
    audio_filters.append(
        "".join(audio_labels)
        + f"amix=inputs={len(audio)}:duration=longest:normalize=0,"
        + f"alimiter=limit=0.95,apad=whole_dur={video_duration_sec:.6f}[mix]"
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
            f"{video_duration_sec:.6f}",
            "-movflags",
            "+faststart",
            str(without_path),
        ]
    )

    subtitle_path = subtitle_dir / f"{event}.srt"
    subtitle_lines: list[str] = []
    for index, row in enumerate(manifest["subtitles"], 1):
        subtitle_lines.extend(
            [
                str(index),
                f"{srt_time(int(row['start_ms']))} --> "
                f"{srt_time(int(row['end_ms']))}",
                row["text"],
                "",
            ]
        )
    subtitle_path.write_text("\n".join(subtitle_lines), encoding="utf-8")
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

    without_probe = probe(without_path, args.ffprobe)
    with_probe = probe(with_path, args.ffprobe)
    for label, item in (
        ("without_subtitles", without_probe),
        ("with_subtitles", with_probe),
    ):
        video = next(
            stream
            for stream in item["streams"]
            if stream.get("codec_type") == "video"
        )
        audio_stream = next(
            stream
            for stream in item["streams"]
            if stream.get("codec_type") == "audio"
        )
        if video.get("width") != width or video.get("height") != height:
            raise SystemExit(f"{label} output was resized")
        if video.get("r_frame_rate") != frame_rate:
            raise SystemExit(f"{label} output frame rate changed")
        if audio_stream.get("sample_rate") != "48000":
            raise SystemExit(f"{label} output audio is not 48 kHz")
        actual_duration_ms = round(float(item["format"]["duration"]) * 1000)
        if abs(actual_duration_ms - render_duration_ms) > 50:
            raise SystemExit(
                f"{label} duration mismatch: actual={actual_duration_ms} ms, "
                f"expected={render_duration_ms} ms"
            )

    output = {
        "source_manifest": str(manifest_path),
        "event": event,
        "render_duration_ms": render_duration_ms,
        "video_extension_policy": extension_policy,
        "without_subtitles": str(without_path),
        "with_subtitles": str(with_path),
        "subtitles": str(subtitle_path),
        "sha256": {
            "without_subtitles": sha256(without_path),
            "with_subtitles": sha256(with_path),
            "subtitles": sha256(subtitle_path),
        },
        "probe_without_subtitles": without_probe,
        "probe_with_subtitles": with_probe,
    }
    output_manifest_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
