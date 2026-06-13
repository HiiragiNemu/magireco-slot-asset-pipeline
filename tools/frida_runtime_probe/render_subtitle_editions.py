#!/usr/bin/env python3
"""Create native-resolution subtitle editions from verified audible base videos."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--base-video-dir", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--only", nargs="*")
    return parser.parse_args()


def srt_time(milliseconds: int) -> str:
    value = max(milliseconds, 0)
    hours, value = divmod(value, 3_600_000)
    minutes, value = divmod(value, 60_000)
    seconds, millis = divmod(value, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def link_or_copy(source: Path, target: Path) -> str:
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate,pix_fmt",
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


def render_one(
    manifest_path: Path,
    base_video_dir: Path,
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    event = str(manifest["event"])
    base_path = base_video_dir / f"{event}.mp4"
    if not base_path.is_file():
        raise FileNotFoundError(f"missing verified base video: {base_path}")

    without_path = out_root / "without_subtitles" / f"{event}.mp4"
    with_path = out_root / "with_subtitles" / f"{event}__subtitles.mp4"
    subtitle_path = out_root / "subtitles" / f"{event}.srt"
    output_manifest_path = out_root / "manifests" / f"{event}.json"
    without_method = link_or_copy(base_path, without_path)
    manifest_method = link_or_copy(manifest_path, output_manifest_path)

    subtitle_lines: list[str] = []
    for index, row in enumerate(manifest["subtitles"], 1):
        subtitle_lines.extend(
            [
                str(index),
                f"{srt_time(int(row['start_ms']))} --> "
                f"{srt_time(int(row['end_ms']))}",
                str(row["text"]),
                "",
            ]
        )
    subtitle_path.parent.mkdir(parents=True, exist_ok=True)
    subtitle_path.write_text("\n".join(subtitle_lines), encoding="utf-8")

    base_probe = probe(base_path, ffprobe)
    video = next(
        stream
        for stream in base_probe["streams"]
        if stream.get("codec_type") == "video"
    )
    expected = manifest["native_dimensions"]
    signature = (
        int(video["width"]),
        int(video["height"]),
        str(video["r_frame_rate"]),
    )
    expected_signature = (
        int(expected["width"]),
        int(expected["height"]),
        str(manifest["native_frame_rate"]),
    )
    if signature != expected_signature:
        raise RuntimeError(
            f"{event} base signature {signature} != manifest {expected_signature}"
        )

    if not subtitle_lines:
        with_method = link_or_copy(base_path, with_path)
    else:
        with_path.parent.mkdir(parents=True, exist_ok=True)
        relative_subtitle = subtitle_path.relative_to(out_root).as_posix()
        subtitle_filter = (
            f"subtitles=filename='{relative_subtitle}':"
            "force_style='FontName=Yu Gothic,FontSize=16,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=1,Shadow=0,MarginV=12,Alignment=2'"
        )
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(base_path),
                "-vf",
                subtitle_filter,
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                str(video.get("pix_fmt") or "yuv420p"),
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(with_path),
            ],
            cwd=out_root,
            check=True,
        )
        with_method = "rendered_video_audio_copy"

    with_probe = probe(with_path, ffprobe)
    with_video = next(
        stream
        for stream in with_probe["streams"]
        if stream.get("codec_type") == "video"
    )
    output_signature = (
        int(with_video["width"]),
        int(with_video["height"]),
        str(with_video["r_frame_rate"]),
    )
    if output_signature != expected_signature:
        raise RuntimeError(
            f"{event} subtitle output {output_signature} != {expected_signature}"
        )
    return {
        "event": event,
        "width": expected_signature[0],
        "height": expected_signature[1],
        "frame_rate": expected_signature[2],
        "subtitle_count": len(manifest["subtitles"]),
        "without_subtitles_method": without_method,
        "with_subtitles_method": with_method,
        "manifest_method": manifest_method,
    }


def main() -> int:
    args = parse_args()
    manifest_root = Path(args.manifest_root).resolve()
    manifest_dir = manifest_root / "events"
    if not manifest_dir.is_dir():
        manifest_dir = manifest_root
    base_video_dir = Path(args.base_video_dir).resolve()
    out_root = Path(args.out_root).resolve()
    if out_root.exists() and any(out_root.iterdir()):
        raise SystemExit(f"refusing to use non-empty output root: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)

    manifests = []
    for path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (
            manifest.get("quality_gates", {}).get("ready")
            and (not args.only or manifest["event"] in set(args.only))
        ):
            manifests.append(path)

    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                render_one,
                path,
                base_video_dir,
                out_root,
                args.ffmpeg,
                args.ffprobe,
            ): path
            for path in manifests
        }
        for completed, future in enumerate(as_completed(futures), 1):
            row = future.result()
            rows.append(row)
            print(
                f"[{completed}/{len(futures)}] {row['event']}",
                flush=True,
            )

    rows.sort(key=lambda row: str(row["event"]))
    summary = {
        "schema": "magireco-native-subtitle-editions-v1",
        "events": len(rows),
        "native_resolution_preserved": len(rows),
        "without_subtitles_hardlinks": sum(
            row["without_subtitles_method"] == "hardlink" for row in rows
        ),
        "subtitle_video_renders": sum(
            row["with_subtitles_method"] == "rendered_video_audio_copy"
            for row in rows
        ),
        "subtitle_free_hardlinks": sum(
            row["with_subtitles_method"] == "hardlink" for row in rows
        ),
        "manifest_root": str(manifest_root),
        "base_video_dir": str(base_video_dir),
        "out_root": str(out_root),
        "events_detail": rows,
    }
    (out_root / "subtitle_editions_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "events_detail"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
