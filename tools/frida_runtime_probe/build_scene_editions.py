#!/usr/bin/env python3
"""Build auditable same-scene long editions from an explicit event sequence.

Unlike build_series_editions.py, this tool is intentionally not prefix based.
It is for upload/review cuts where one narrative scene spans multiple event
families such as ac7114_001 -> ac7115_001 -> ac7116_001.  Inputs must already
be QA-passed single-event subtitle/no-subtitle pairs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SRT_BLOCK_RE = re.compile(
    r"(?:^|\n)\s*\d+\s*\n"
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(?P<text>.*?)(?=\n\s*\d+\s*\n\d{2}:|\Z)",
    re.DOTALL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", action="append", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--event", action="append", required=True)
    parser.add_argument("--production-manifest-root", default="")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def srt_time_ms(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int(milliseconds)
    )


def format_srt_time(value_ms: int) -> str:
    value_ms = max(0, value_ms)
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def shifted_srt_cues(text: str, offset_ms: int) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    normalized = text.replace("\r\n", "\n").strip()
    for match in SRT_BLOCK_RE.finditer(normalized):
        cues.append(
            {
                "start_ms": srt_time_ms(match.group("start")) + offset_ms,
                "end_ms": srt_time_ms(match.group("end")) + offset_ms,
                "text": match.group("text").strip(),
            }
        )
    return cues


def write_srt(path: Path, cues: list[dict[str, Any]]) -> None:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_srt_time(int(cue['start_ms']))} --> "
            f"{format_srt_time(int(cue['end_ms']))}\n"
            f"{cue['text']}"
        )
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,profile,level,width,height,pix_fmt,"
            "r_frame_rate,avg_frame_rate,time_base,sample_rate,channels,"
            "channel_layout,duration:format=duration,size,bit_rate",
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


def stream_signature(payload: dict[str, Any]) -> dict[str, Any]:
    video = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "video"
    )
    audio = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "audio"
    )
    return {
        "video": {
            key: video.get(key, "")
            for key in (
                "codec_name",
                "profile",
                "level",
                "width",
                "height",
                "pix_fmt",
                "r_frame_rate",
                "time_base",
            )
        },
        "audio": {
            key: audio.get(key, "")
            for key in (
                "codec_name",
                "sample_rate",
                "channels",
                "channel_layout",
                "time_base",
            )
        },
    }


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
    return result.stdout.strip().split("=", 1)[-1].upper()


def ffconcat_line(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{value}'"


def concat_copy(
    sources: list[Path],
    list_path: Path,
    output_path: Path,
    ffmpeg: str,
    overwrite: bool,
) -> None:
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(path) for path in sources)
        + "\n",
        encoding="utf-8",
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )


def load_qa_status(root: Path) -> dict[str, str]:
    path = root / "full_qa_audit.csv"
    if not path.is_file():
        raise FileNotFoundError(f"QA audit is required: {path}")
    return {row.get("event", ""): row.get("status", "") for row in read_csv(path)}


def discover_events(input_roots: list[Path]) -> dict[str, dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    for root in input_roots:
        qa_status = load_qa_status(root)
        for render_path in sorted(root.glob("*/render_manifest.json")):
            payload = json.loads(render_path.read_text(encoding="utf-8"))
            event = str(payload.get("event", "")).strip()
            if not event or qa_status.get(event) != "passed":
                continue
            if event in events:
                raise ValueError(f"duplicate QA-passed event input: {event}")
            without_path = Path(str(payload.get("without_subtitles", ""))).resolve()
            with_path = Path(str(payload.get("with_subtitles", ""))).resolve()
            subtitle_path = Path(str(payload.get("subtitles", ""))).resolve()
            for label, path in (
                ("without_subtitles", without_path),
                ("with_subtitles", with_path),
                ("subtitles", subtitle_path),
            ):
                if not path.is_file():
                    raise FileNotFoundError(f"{event} missing {label}: {path}")
            events[event] = {
                "event": event,
                "render_manifest": payload,
                "render_manifest_path": str(render_path.resolve()),
                "without_path": without_path,
                "with_path": with_path,
                "subtitle_path": subtitle_path,
                "qa_root": str(root.resolve()),
            }
    return events


def manifest_path_for_event(root: Path | None, event: str) -> str:
    if root is None:
        return ""
    event_dir = root / "events"
    if not event_dir.is_dir():
        event_dir = root
    path = event_dir / f"{event}.json"
    return str(path.resolve()) if path.is_file() else ""


def main() -> int:
    args = parse_args()
    input_roots = [Path(path).resolve() for path in args.input_root]
    candidates = discover_events(input_roots)
    missing = [event for event in args.event if event not in candidates]
    if missing:
        raise SystemExit("missing QA-passed input events: " + ", ".join(missing))
    selected = [candidates[event] for event in args.event]
    if len(selected) < 2:
        raise SystemExit("scene edition needs at least two events")

    manifest_root = (
        Path(args.production_manifest_root).resolve()
        if args.production_manifest_root
        else None
    )
    out_root = Path(args.out_root).resolve()
    scene_dir = out_root / args.scene
    audit_dir = scene_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    source_rows: list[dict[str, Any]] = []
    combined_cues: list[dict[str, Any]] = []
    expected_signature: dict[str, Any] | None = None
    offset_ms = 0
    for order, row in enumerate(selected, start=1):
        without_probe = probe(row["without_path"], args.ffprobe)
        with_probe = probe(row["with_path"], args.ffprobe)
        without_signature = stream_signature(without_probe)
        with_signature = stream_signature(with_probe)
        if without_signature != with_signature:
            raise SystemExit(f"subtitle/no-subtitle stream mismatch: {row['event']}")
        if expected_signature is None:
            expected_signature = without_signature
        elif without_signature != expected_signature:
            raise SystemExit(f"scene stream mismatch: {row['event']}")
        duration_ms = round(float(without_probe["format"]["duration"]) * 1000)
        cues = shifted_srt_cues(
            row["subtitle_path"].read_text(encoding="utf-8"), offset_ms
        )
        combined_cues.extend(cues)
        source_rows.append(
            {
                "order": order,
                "event": row["event"],
                "start_ms": offset_ms,
                "end_ms": offset_ms + duration_ms,
                "duration_ms": duration_ms,
                "subtitle_cues": len(cues),
                "without_subtitles": str(row["without_path"]),
                "with_subtitles": str(row["with_path"]),
                "subtitles": str(row["subtitle_path"]),
                "render_manifest": row["render_manifest_path"],
                "production_manifest": manifest_path_for_event(
                    manifest_root, row["event"]
                ),
                "without_sha256": file_sha256(row["without_path"]),
                "with_sha256": file_sha256(row["with_path"]),
                "subtitle_sha256": file_sha256(row["subtitle_path"]),
            }
        )
        offset_ms += duration_ms

    without_output = scene_dir / "without_subtitles" / f"{args.scene}__scene.mp4"
    with_output = (
        scene_dir
        / "with_subtitles"
        / f"{args.scene}__scene__subtitles.mp4"
    )
    subtitle_output = scene_dir / "subtitles" / f"{args.scene}__scene.srt"
    subtitle_output.parent.mkdir(parents=True, exist_ok=True)
    concat_copy(
        [row["without_path"] for row in selected],
        audit_dir / "without_subtitles.ffconcat",
        without_output,
        args.ffmpeg,
        args.overwrite,
    )
    concat_copy(
        [row["with_path"] for row in selected],
        audit_dir / "with_subtitles.ffconcat",
        with_output,
        args.ffmpeg,
        args.overwrite,
    )
    write_srt(subtitle_output, combined_cues)
    write_csv(
        audit_dir / "scene_index.csv",
        source_rows,
        [
            "order",
            "event",
            "start_ms",
            "end_ms",
            "duration_ms",
            "subtitle_cues",
            "without_subtitles",
            "with_subtitles",
            "subtitles",
            "render_manifest",
            "production_manifest",
            "without_sha256",
            "with_sha256",
            "subtitle_sha256",
        ],
    )

    without_probe = probe(without_output, args.ffprobe)
    with_probe = probe(with_output, args.ffprobe)
    errors: list[str] = []
    assert expected_signature is not None
    if stream_signature(without_probe) != expected_signature:
        errors.append("without_stream_signature_changed")
    if stream_signature(with_probe) != expected_signature:
        errors.append("with_stream_signature_changed")
    without_duration_ms = round(float(without_probe["format"]["duration"]) * 1000)
    with_duration_ms = round(float(with_probe["format"]["duration"]) * 1000)
    tolerance_ms = max(100, len(selected) * 35)
    if abs(without_duration_ms - offset_ms) > tolerance_ms:
        errors.append("without_duration_mismatch")
    if abs(with_duration_ms - offset_ms) > tolerance_ms:
        errors.append("with_duration_mismatch")
    without_audio_hash = audio_hash(without_output, args.ffmpeg)
    with_audio_hash = audio_hash(with_output, args.ffmpeg)
    if without_audio_hash != with_audio_hash:
        errors.append("edition_audio_mismatch")

    scene_manifest = {
        "schema": "magireco-scene-editions-v1",
        "scene": args.scene,
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "direct_stream_copy": True,
        "ordering": "explicit --event order",
        "event_count": len(selected),
        "expected_duration_ms": offset_ms,
        "subtitle_cue_count": len(combined_cues),
        "stream_signature": expected_signature,
        "outputs": {
            "without_subtitles": str(without_output.resolve()),
            "with_subtitles": str(with_output.resolve()),
            "subtitles": str(subtitle_output.resolve()),
            "scene_index": str((audit_dir / "scene_index.csv").resolve()),
        },
        "output_sha256": {
            "without_subtitles": file_sha256(without_output),
            "with_subtitles": file_sha256(with_output),
            "subtitles": file_sha256(subtitle_output),
        },
        "edition_audio_sha256": without_audio_hash,
        "probe_without_subtitles": without_probe,
        "probe_with_subtitles": with_probe,
        "sources": source_rows,
    }
    manifest_path = scene_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(scene_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "scene": args.scene,
        "status": scene_manifest["status"],
        "errors": errors,
        "event_count": len(selected),
        "duration_ms": without_duration_ms,
        "subtitle_cue_count": len(combined_cues),
        "width": expected_signature["video"]["width"],
        "height": expected_signature["video"]["height"],
        "frame_rate": expected_signature["video"]["r_frame_rate"],
        "audio_sample_rate": expected_signature["audio"]["sample_rate"],
        "audio_channels": expected_signature["audio"]["channels"],
        "manifest": str(manifest_path.resolve()),
    }
    (out_root / "scene_editions_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
