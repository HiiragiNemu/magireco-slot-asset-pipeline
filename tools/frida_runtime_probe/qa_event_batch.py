#!/usr/bin/env python3
"""Audit rendered event pairs for native video and identical audible audio."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path


MAX_VOLUME_RE = re.compile(r"max_volume:\s+(-?inf|-?\d+(?:\.\d+)?)\s+dB")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,r_frame_rate,"
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


def audio_hash(path: Path, ffmpeg: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip().split("=", 1)[-1].lower()


def max_volume_db(path: Path, ffmpeg: str) -> float | None:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "NUL",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    match = MAX_VOLUME_RE.search(result.stderr)
    if not match or match.group(1).lower() == "-inf":
        return None
    return float(match.group(1))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    manifest_root = Path(args.manifest_root).resolve()
    manifest_dir = manifest_root / "events"
    if not manifest_dir.is_dir():
        manifest_dir = manifest_root
    output_root = Path(args.output_root).resolve()

    rows: list[dict] = []
    manifest_paths = sorted(manifest_dir.glob("*.json"))
    if args.only:
        selected = set(args.only)
        manifest_paths = [
            path for path in manifest_paths if path.stem in selected
        ]
        missing = selected - {path.stem for path in manifest_paths}
        if missing:
            raise SystemExit("missing manifests: " + ", ".join(sorted(missing)))
    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("quality_gates", {}).get("ready"):
            continue
        event = manifest["event"]
        root = output_root / event
        if root.is_dir():
            without_path = root / "without_subtitles" / f"{event}.mp4"
            with_path = root / "with_subtitles" / f"{event}__subtitles.mp4"
            subtitle_path = root / "subtitles" / f"{event}.srt"
        else:
            without_path = output_root / "without_subtitles" / f"{event}.mp4"
            with_path = (
                output_root
                / "with_subtitles"
                / f"{event}__subtitles.mp4"
            )
            subtitle_path = output_root / "subtitles" / f"{event}.srt"
        expected_subtitle_count = len(manifest["subtitles"])
        errors: list[str] = []
        for label, path in (
            ("without_subtitles", without_path),
            ("with_subtitles", with_path),
        ):
            if not path.is_file() or path.stat().st_size <= 0:
                errors.append(f"missing_{label}")
        if not subtitle_path.is_file():
            errors.append("missing_subtitles")
        elif expected_subtitle_count and subtitle_path.stat().st_size <= 0:
            errors.append("empty_subtitle")
        if errors:
            rows.append(
                {
                    "event": event,
                    "status": "failed",
                    "errors": ";".join(errors),
                }
            )
            continue

        without_probe = probe(without_path, args.ffprobe)
        with_probe = probe(with_path, args.ffprobe)
        expected_width = int(manifest["native_dimensions"]["width"])
        expected_height = int(manifest["native_dimensions"]["height"])
        expected_rate = manifest["native_frame_rate"]
        expected_duration_ms = int(manifest["render_duration_ms"])
        variants = (
            ("without", without_probe),
            ("with", with_probe),
        )
        for label, item in variants:
            video = next(
                (stream for stream in item["streams"] if stream["codec_type"] == "video"),
                None,
            )
            audio = next(
                (stream for stream in item["streams"] if stream["codec_type"] == "audio"),
                None,
            )
            if video is None:
                errors.append(f"{label}_missing_video")
            else:
                if (
                    int(video.get("width", 0)) != expected_width
                    or int(video.get("height", 0)) != expected_height
                ):
                    errors.append(f"{label}_resized")
                if video.get("r_frame_rate") != expected_rate:
                    errors.append(f"{label}_frame_rate_changed")
            if audio is None:
                errors.append(f"{label}_missing_audio")
            else:
                if audio.get("sample_rate") != "48000":
                    errors.append(f"{label}_audio_rate")
                if int(audio.get("channels", 0)) not in {1, 2}:
                    errors.append(f"{label}_audio_channels")
            duration_ms = round(float(item["format"]["duration"]) * 1000)
            if abs(duration_ms - expected_duration_ms) > 50:
                errors.append(f"{label}_duration")

        without_audio_hash = audio_hash(without_path, args.ffmpeg)
        with_audio_hash = audio_hash(with_path, args.ffmpeg)
        if without_audio_hash != with_audio_hash:
            errors.append("edition_audio_mismatch")
        max_db = max_volume_db(without_path, args.ffmpeg)
        if max_db is None or max_db <= -90.0:
            errors.append("silent_audio")
        subtitle_text = subtitle_path.read_text(encoding="utf-8").strip()
        if expected_subtitle_count and not subtitle_text:
            errors.append("empty_subtitle")
        if not expected_subtitle_count and subtitle_text:
            errors.append("unexpected_subtitle")

        rows.append(
            {
                "event": event,
                "status": "passed" if not errors else "failed",
                "errors": ";".join(errors),
                "width": expected_width,
                "height": expected_height,
                "frame_rate": expected_rate,
                "render_duration_ms": expected_duration_ms,
                "video_extension_policy": manifest["video_extension_policy"],
                "voice_tracks": sum(
                    row["source"] == "z2d_req_sound" for row in manifest["audio"]
                ),
                "base_audio_tracks": sum(
                    row["source"] == "event_audio_component"
                    for row in manifest["audio"]
                ),
                "subtitle_count": len(manifest["subtitles"]),
                "max_volume_db": "" if max_db is None else f"{max_db:.1f}",
                "edition_audio_sha256": without_audio_hash,
                "without_size": without_path.stat().st_size,
                "with_size": with_path.stat().st_size,
                "subtitle_sha256": file_sha256(subtitle_path),
            }
        )
        print(f"[{rows[-1]['status']}] {event}", flush=True)

    fields = [
        "event",
        "status",
        "errors",
        "width",
        "height",
        "frame_rate",
        "render_duration_ms",
        "video_extension_policy",
        "voice_tracks",
        "base_audio_tracks",
        "subtitle_count",
        "max_volume_db",
        "edition_audio_sha256",
        "without_size",
        "with_size",
        "subtitle_sha256",
    ]
    csv_path = output_root / "full_qa_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    failed = [row for row in rows if row["status"] != "passed"]
    summary = {
        "audited_events": len(rows),
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "subtitle_and_no_subtitle_audio_identical": sum(
            not row.get("errors", "").find("edition_audio_mismatch") >= 0
            for row in rows
        ),
        "non_silent_audio": sum(
            not row.get("errors", "").find("silent_audio") >= 0 for row in rows
        ),
        "total_output_bytes": sum(
            int(row.get("without_size", 0)) + int(row.get("with_size", 0))
            for row in rows
        ),
        "audit_csv": str(csv_path),
    }
    summary_path = output_root / "full_qa_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
