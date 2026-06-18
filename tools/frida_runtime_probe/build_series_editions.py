#!/usr/bin/env python3
"""Build auditable stream-copy series editions from QA-passed event pairs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path


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
    parser.add_argument("--series", action="append", required=True)
    parser.add_argument("--production-manifest-root", default="")
    parser.add_argument("--require-complete-family", action="store_true")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def event_sort_key(event: str) -> tuple:
    return tuple(
        int(token) if token.isdigit() else token.casefold()
        for token in re.split(r"(\d+)", event)
    )


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


def shifted_srt_cues(text: str, offset_ms: int) -> list[dict]:
    cues: list[dict] = []
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


def write_srt(path: Path, cues: list[dict]) -> None:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_srt_time(int(cue['start_ms']))} --> "
            f"{format_srt_time(int(cue['end_ms']))}\n"
            f"{cue['text']}"
        )
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,profile,level,width,height,pix_fmt,"
            "r_frame_rate,avg_frame_rate,time_base,sample_rate,channels,channel_layout,duration:"
            "format=duration,size,bit_rate",
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


def stream_signature(payload: dict) -> dict:
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


def discover_events(input_roots: list[Path]) -> dict[str, dict]:
    events: dict[str, dict] = {}
    for root in input_roots:
        qa_status = load_qa_status(root)
        for render_path in sorted(root.glob("*/render_manifest.json")):
            payload = json.loads(render_path.read_text(encoding="utf-8"))
            event = str(payload.get("event", "")).strip()
            if not event:
                raise ValueError(f"render manifest has no event: {render_path}")
            if qa_status.get(event) != "passed":
                continue
            if event in events:
                raise ValueError(
                    f"duplicate QA-passed event {event}: "
                    f"{events[event]['render_manifest_path']} and {render_path}"
                )
            without_path = Path(str(payload.get("without_subtitles", "")))
            with_path = Path(str(payload.get("with_subtitles", "")))
            subtitle_path = Path(str(payload.get("subtitles", "")))
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
                "without_path": without_path.resolve(),
                "with_path": with_path.resolve(),
                "subtitle_path": subtitle_path.resolve(),
                "qa_root": str(root.resolve()),
            }
    return events


def family_state(series: str, manifest_root: Path | None) -> dict:
    if manifest_root is None:
        return {}
    event_dir = manifest_root / "events"
    if not event_dir.is_dir():
        event_dir = manifest_root
    rows = []
    for path in sorted(event_dir.glob(f"{series}_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "event": str(payload.get("event", path.stem)),
                "ready": bool(payload.get("quality_gates", {}).get("ready")),
                "errors": payload.get("quality_gates", {}).get("errors", []),
            }
        )
    return {
        "production_manifest_root": str(manifest_root.resolve()),
        "known_family_events": len(rows),
        "ready_family_events": sum(row["ready"] for row in rows),
        "not_ready_family_events": [row for row in rows if not row["ready"]],
        "ready_event_names": [row["event"] for row in rows if row["ready"]],
    }


def build_series(
    series: str,
    candidates: dict[str, dict],
    out_root: Path,
    manifest_root: Path | None,
    require_complete: bool,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    selected = sorted(
        [row for event, row in candidates.items() if event.startswith(f"{series}_")],
        key=lambda row: event_sort_key(row["event"]),
    )
    if len(selected) < 2:
        raise ValueError(f"{series} needs at least two QA-passed events")

    state = family_state(series, manifest_root)
    selected_names = {row["event"] for row in selected}
    missing_ready = sorted(set(state.get("ready_event_names", [])) - selected_names)
    not_ready = state.get("not_ready_family_events", [])
    if require_complete and (missing_ready or not_ready):
        raise ValueError(
            f"{series} is not a complete family; missing ready={missing_ready}, "
            f"not ready={[row['event'] for row in not_ready]}"
        )

    source_rows: list[dict] = []
    expected_signature: dict | None = None
    offset_ms = 0
    combined_cues: list[dict] = []
    for order, row in enumerate(selected, start=1):
        without_probe = probe(row["without_path"], ffprobe)
        with_probe = probe(row["with_path"], ffprobe)
        without_signature = stream_signature(without_probe)
        with_signature = stream_signature(with_probe)
        if without_signature != with_signature:
            raise ValueError(f"edition stream mismatch: {row['event']}")
        if expected_signature is None:
            expected_signature = without_signature
        elif without_signature != expected_signature:
            raise ValueError(f"series stream mismatch: {row['event']}")
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
                "without_sha256": file_sha256(row["without_path"]),
                "with_sha256": file_sha256(row["with_path"]),
                "subtitle_sha256": file_sha256(row["subtitle_path"]),
            }
        )
        offset_ms += duration_ms

    series_dir = out_root / series
    audit_dir = series_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    without_output = series_dir / "without_subtitles" / f"{series}__series.mp4"
    with_output = series_dir / "with_subtitles" / f"{series}__series__subtitles.mp4"
    subtitle_output = series_dir / "subtitles" / f"{series}__series.srt"
    subtitle_output.parent.mkdir(parents=True, exist_ok=True)
    concat_copy(
        [row["without_path"] for row in selected],
        audit_dir / "without_subtitles.ffconcat",
        without_output,
        ffmpeg,
        overwrite,
    )
    concat_copy(
        [row["with_path"] for row in selected],
        audit_dir / "with_subtitles.ffconcat",
        with_output,
        ffmpeg,
        overwrite,
    )
    write_srt(subtitle_output, combined_cues)
    write_csv(
        audit_dir / "series_index.csv",
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
            "without_sha256",
            "with_sha256",
            "subtitle_sha256",
        ],
    )

    without_probe = probe(without_output, ffprobe)
    with_probe = probe(with_output, ffprobe)
    errors: list[str] = []
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
    without_audio_hash = audio_hash(without_output, ffmpeg)
    with_audio_hash = audio_hash(with_output, ffmpeg)
    if without_audio_hash != with_audio_hash:
        errors.append("edition_audio_mismatch")

    manifest = {
        "schema": "magireco-series-editions-v1",
        "series": series,
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "direct_stream_copy": True,
        "ordering": "natural event identifier order",
        "event_count": len(selected),
        "expected_duration_ms": offset_ms,
        "subtitle_cue_count": len(combined_cues),
        "stream_signature": expected_signature,
        "family_state": state,
        "outputs": {
            "without_subtitles": str(without_output.resolve()),
            "with_subtitles": str(with_output.resolve()),
            "subtitles": str(subtitle_output.resolve()),
            "series_index": str((audit_dir / "series_index.csv").resolve()),
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
    manifest_path = series_dir / "series_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(f"{series} series QA failed: {errors}")
    return {
        "series": series,
        "status": "passed",
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


def main() -> int:
    args = parse_args()
    input_roots = [Path(path).resolve() for path in args.input_root]
    candidates = discover_events(input_roots)
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    manifest_root = (
        Path(args.production_manifest_root).resolve()
        if args.production_manifest_root
        else None
    )
    rows = []
    for series in args.series:
        row = build_series(
            series,
            candidates,
            out_root,
            manifest_root,
            args.require_complete_family,
            args.ffmpeg,
            args.ffprobe,
            args.overwrite,
        )
        rows.append(row)
        print(f"[passed] {series}: {row['event_count']} events", flush=True)
    summary = {
        "schema": "magireco-series-build-summary-v1",
        "series_count": len(rows),
        "passed": len(rows),
        "failed": 0,
        "direct_stream_copy": True,
        "series": rows,
    }
    (out_root / "series_build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
