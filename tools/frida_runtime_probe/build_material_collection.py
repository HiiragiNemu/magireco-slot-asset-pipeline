#!/usr/bin/env python3
"""Concatenate reviewed audience-component clips without re-encoding them."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path


SOUND_ID_RE = re.compile(r"^(\d{4,5})(?:_|\s|$)")
ROLE_VOICE_SPEAKER_TOKENS = {
    "ai",
    "ari",
    "fel",
    "fer",
    "hom",
    "iro",
    "kae",
    "kan",
    "kuro",
    "kuroe",
    "mad",
    "mam",
    "mami",
    "mif",
    "mihu",
    "mit",
    "mita",
    "mom",
    "nag",
    "nem",
    "nemu",
    "ren",
    "rena",
    "qb",
    "riko",
    "sana",
    "say",
    "sigure",
    "sqb",
    "toka",
    "tou",
    "tsu",
    "tukasa",
    "tukuyo",
    "tur",
    "turk",
    "ui",
    "uwa",
    "yac",
    "yach",
}
GAMEPLAY_TERMS = (
    "地図",
    "結果表示",
    "CHANCE",
    "WIN",
    "PUSH",
    "押し",
    "押して",
    "狙え",
    "告弱",
    "告強",
    "上乗せ",
    "連撃",
    "長押し",
    "連打",
    "ルーレット",
    "roulette",
    "chance_btn",
    "mekure",
    "card",
)


def file_sha256(path: Path) -> str:
    import hashlib

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


def is_role_voice_audio(row: dict) -> bool:
    code_name = str(row.get("code_name", "")).strip()
    parts = [part.casefold() for part in code_name.split("_")]
    has_speaker = any(part in ROLE_VOICE_SPEAKER_TOKENS for part in parts[1:-1])
    has_at_marker = "at" in parts[1:-1]
    match = SOUND_ID_RE.match(code_name)
    resource_id = int(match.group(1)) if match else 0
    return has_speaker and (has_at_marker or 30000 <= resource_id < 40000)


def has_gameplay_marker(values: list[str]) -> bool:
    joined = "\n".join(values)
    return any(term in joined for term in GAMEPLAY_TERMS)


def material_lane(
    *,
    role_voice_audio_count: int,
    gameplay_marker: bool,
    hybrid_slot_story: bool,
) -> str:
    if hybrid_slot_story:
        return "hybrid_slot_story_material_not_clean_animation"
    if role_voice_audio_count and gameplay_marker:
        return "audible_gameplay_result_with_role_voice_not_pure_material"
    if role_voice_audio_count:
        return "audible_component_with_role_voice_not_pure_material"
    if gameplay_marker:
        return "pure_gameplay_or_effect_material"
    return "reviewed_audience_components_not_standalone_animation"


def format_srt_time(value_ms: int) -> str:
    value_ms = max(0, value_ms)
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--series", action="append", default=[])
    parser.add_argument(
        "--plan",
        action="append",
        default=[],
        help="Named material collection plan resolved through --video-map.",
    )
    parser.add_argument(
        "--video-map",
        default="",
        help="Official-name video map required by --plan.",
    )
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.series and not args.plan:
        parser.error("at least one --series or --plan is required")
    if args.plan and not args.video_map:
        parser.error("--video-map is required with --plan")
    return args


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,profile,level,width,height,pix_fmt,"
            "r_frame_rate,time_base,duration,bit_rate,sample_rate,channels,"
            "channel_layout:format=duration,size,bit_rate",
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


def video_signature(payload: dict) -> dict:
    stream = next(
        row
        for row in payload.get("streams", [])
        if row.get("codec_type") == "video"
    )
    return {
        key: stream.get(key, "")
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
    }


def ffconcat_line(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{value}'"


def stream_packet_hash(path: Path, ffmpeg: str, stream: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            stream,
            "-c",
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


def video_packet_hash(path: Path, ffmpeg: str) -> str:
    return stream_packet_hash(path, ffmpeg, "0:v:0")


def audio_packet_hash(path: Path, ffmpeg: str) -> str:
    return stream_packet_hash(path, ffmpeg, "0:a:0")


def write_label_srt(path: Path, rows: list[dict]) -> None:
    blocks = []
    for index, row in enumerate(rows, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_srt_time(row['start_ms'])} --> "
            f"{format_srt_time(row['end_ms'])}\n"
            f"{row['event']} | {row['dgm_name']}"
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def render_audible_segment(
    source: dict,
    output_path: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    audio_rows = [
        row
        for row in source.get("official_audio_evidence", [])
        if str(row.get("path", "")).strip()
    ]
    if not audio_rows:
        raise ValueError(f"material event has no official audio: {source['event']}")
    missing_audio = [
        str(row.get("path", ""))
        for row in audio_rows
        if not Path(str(row.get("path", ""))).is_file()
    ]
    if missing_audio:
        raise FileNotFoundError(
            f"missing official material audio for {source['event']}: {missing_audio}"
        )
    audible_duration_ms = max(
        int(source["duration_ms"]),
        max(
            int(row.get("start_ms", 0)) + int(row.get("duration_ms", 0))
            for row in audio_rows
        ),
    )
    extension_ms = max(0, audible_duration_ms - int(source["duration_ms"]))
    source_probe = source["source_probe"]
    source_video = next(
        row
        for row in source_probe.get("streams", [])
        if row.get("codec_type") == "video"
    )
    frame_rate = str(source_video.get("r_frame_rate", "30/1"))
    pixel_format = str(source_video.get("pix_fmt", "yuv420p"))
    inputs = ["-i", str(Path(source["path"]).resolve())]
    filters = [
        "[0:v:0]"
        f"tpad=stop_mode=clone:stop_duration={extension_ms / 1000:.6f},"
        f"trim=duration={audible_duration_ms / 1000:.6f},"
        f"setpts=PTS-STARTPTS,fps={frame_rate},format={pixel_format}[v]"
    ]
    audio_labels = []
    for index, row in enumerate(audio_rows, start=1):
        inputs.extend(["-i", str(Path(str(row["path"])).resolve())])
        label = f"a{index}"
        filters.append(
            f"[{index}:a:0]adelay={int(row.get('start_ms', 0))}:all=1,"
            f"aresample=48000[{label}]"
        )
        audio_labels.append(f"[{label}]")
    filters.append(
        "".join(audio_labels)
        + f"amix=inputs={len(audio_labels)}:duration=longest:normalize=0,"
        + "alimiter=limit=0.95,"
        + f"apad=whole_dur={audible_duration_ms / 1000:.6f},"
        + f"atrim=duration={audible_duration_ms / 1000:.6f}[a]"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            pixel_format,
            "-video_track_timescale",
            "15360",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )
    output_probe = probe(output_path, ffprobe)
    return {
        "path": str(output_path.resolve()),
        "duration_ms": round(float(output_probe["format"]["duration"]) * 1000),
        "planned_duration_ms": audible_duration_ms,
        "extension_ms": extension_ms,
        "sha256": file_sha256(output_path),
        "video_packet_sha256": video_packet_hash(output_path, ffmpeg),
        "audio_packet_sha256": audio_packet_hash(output_path, ffmpeg),
        "probe": output_probe,
    }


def build_collection(
    series: str,
    manifest_dir: Path,
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    manifests = []
    for path in sorted(manifest_dir.glob(f"{series}_*.json"), key=lambda p: event_sort_key(p.stem)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        reason = str(payload.get("audience_exclusion_reason", "")).strip()
        if not reason:
            continue
        errors = set(payload.get("quality_gates", {}).get("errors", []))
        if "audience_component_only" not in errors:
            raise ValueError(f"excluded event lacks component gate: {path}")
        manifests.append((path, payload))
    if not manifests:
        raise ValueError(f"no reviewed audience components found for {series}")

    sources = []
    seen_paths: set[str] = set()
    signature: dict | None = None
    offset_ms = 0
    for manifest_path, payload in manifests:
        for clip in payload.get("clips", []):
            source_path = Path(str(clip.get("path", ""))).resolve()
            if not source_path.is_file():
                raise FileNotFoundError(source_path)
            key = str(source_path).casefold()
            if key in seen_paths:
                continue
            seen_paths.add(key)
            source_probe = probe(source_path, ffprobe)
            source_signature = video_signature(source_probe)
            if signature is None:
                signature = source_signature
            elif source_signature != signature:
                raise ValueError(
                    f"material stream mismatch for {payload['event']}: "
                    f"{source_signature} != {signature}"
                )
            audio_streams = [
                row
                for row in source_probe.get("streams", [])
                if row.get("codec_type") == "audio"
            ]
            embedded_audio_peak_db = None
            if audio_streams:
                embedded_audio_peak_db = audio_peak_db(source_path, ffmpeg)
                if (
                    embedded_audio_peak_db is not None
                    and embedded_audio_peak_db > -90.0
                ):
                    raise ValueError(
                        "raw material source has audible embedded audio: "
                        f"{source_path} ({embedded_audio_peak_db} dB)"
                    )
            duration_ms = round(float(source_probe["format"]["duration"]) * 1000)
            sources.append(
                {
                    "order": len(sources) + 1,
                    "event": str(payload.get("event", "")),
                    "dgm_name": str(clip.get("dgm_name", "")),
                    "start_ms": offset_ms,
                    "end_ms": offset_ms + duration_ms,
                    "duration_ms": duration_ms,
                    "path": str(source_path),
                    "source_sha256": file_sha256(source_path),
                    "source_video_packet_sha256": video_packet_hash(source_path, ffmpeg),
                    "source_probe": source_probe,
                    "embedded_audio_dropped": bool(audio_streams),
                    "embedded_audio_peak_db": embedded_audio_peak_db,
                    "audience_exclusion_reason": str(
                        payload.get("audience_exclusion_reason", "")
                    ),
                    "official_audio_evidence": payload.get("audio", []),
                    "production_manifest": str(manifest_path.resolve()),
                }
            )
            offset_ms += duration_ms
    if len(sources) < 2:
        raise ValueError(f"{series} needs at least two unique material clips")
    if signature is None:
        raise ValueError(f"{series} has no material signature")

    width = signature["width"]
    height = signature["height"]
    rate_label = str(signature["r_frame_rate"]).replace("/", "-")
    collection_dir = out_root / series
    audit_dir = collection_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    list_path = audit_dir / "materials.ffconcat"
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(Path(row["path"])) for row in sources)
        + "\n",
        encoding="utf-8",
    )
    output_path = (
        collection_dir
        / f"{series}__material_components__{width}x{height}_{rate_label}.mp4"
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
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
            "-an",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )
    label_path = collection_dir / f"{series}__material_labels.srt"
    write_label_srt(label_path, sources)
    output_probe = probe(output_path, ffprobe)
    errors: list[str] = []
    if video_signature(output_probe) != signature:
        errors.append("stream_signature_changed")
    output_duration_ms = round(float(output_probe["format"]["duration"]) * 1000)
    if abs(output_duration_ms - offset_ms) > max(100, len(sources) * 35):
        errors.append("duration_mismatch")
    if any(
        stream.get("codec_type") == "audio"
        for stream in output_probe.get("streams", [])
    ):
        errors.append("unexpected_audio_stream")

    audible_event_sources = []
    event_order = []
    sources_by_event: dict[str, list[dict]] = {}
    for source in sources:
        event = str(source["event"])
        if event not in sources_by_event:
            event_order.append(event)
            sources_by_event[event] = []
        sources_by_event[event].append(source)
    event_visuals_dir = audit_dir / "audible_event_visuals"
    event_visuals_dir.mkdir(parents=True, exist_ok=True)
    for event in event_order:
        event_sources = sources_by_event[event]
        if len(event_sources) == 1:
            event_source = dict(event_sources[0])
        else:
            event_list = event_visuals_dir / f"{event}.ffconcat"
            event_list.write_text(
                "ffconcat version 1.0\n"
                + "\n".join(
                    ffconcat_line(Path(row["path"])) for row in event_sources
                )
                + "\n",
                encoding="utf-8",
            )
            event_video = event_visuals_dir / f"{event}.mp4"
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
                    str(event_list),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-c:v",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(event_video),
                ],
                check=True,
            )
            event_probe = probe(event_video, ffprobe)
            event_duration_ms = round(
                float(event_probe["format"]["duration"]) * 1000
            )
            expected_event_duration_ms = sum(
                int(row["duration_ms"]) for row in event_sources
            )
            if abs(event_duration_ms - expected_event_duration_ms) > max(
                100, len(event_sources) * 35
            ):
                raise RuntimeError(
                    f"{event} material event visual duration mismatch: "
                    f"{event_duration_ms} != {expected_event_duration_ms}"
                )
            event_source = dict(event_sources[0])
            event_source.update(
                {
                    "dgm_name": "+".join(
                        str(row["dgm_name"]) for row in event_sources
                    ),
                    "path": str(event_video.resolve()),
                    "start_ms": 0,
                    "end_ms": event_duration_ms,
                    "duration_ms": event_duration_ms,
                    "source_sha256": file_sha256(event_video),
                    "source_video_packet_sha256": video_packet_hash(
                        event_video, ffmpeg
                    ),
                    "source_probe": event_probe,
                }
            )
        event_source["component_count"] = len(event_sources)
        event_source["component_names"] = [
            str(row["dgm_name"]) for row in event_sources
        ]
        audible_event_sources.append(event_source)

    audible_segments_dir = audit_dir / "audible_segments"
    audible_rows = []
    audible_offset_ms = 0
    for source in audible_event_sources:
        segment_path = audible_segments_dir / f"{source['event']}__audible.mp4"
        audible_segment = render_audible_segment(
            source,
            segment_path,
            ffmpeg,
            ffprobe,
            overwrite,
        )
        source["audible_segment"] = audible_segment
        source["audible_start_ms"] = audible_offset_ms
        source["audible_end_ms"] = (
            audible_offset_ms + int(audible_segment["planned_duration_ms"])
        )
        audible_rows.append(
            {
                "event": source["event"],
                "dgm_name": source["dgm_name"],
                "start_ms": source["audible_start_ms"],
                "end_ms": source["audible_end_ms"],
            }
        )
        audible_offset_ms = source["audible_end_ms"]

    audible_list_path = audit_dir / "materials_with_official_audio.ffconcat"
    audible_list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(
            ffconcat_line(Path(row["audible_segment"]["path"]))
            for row in audible_event_sources
        )
        + "\n",
        encoding="utf-8",
    )
    audible_output_path = (
        collection_dir
        / f"{series}__material_components_with_official_audio__"
        f"{width}x{height}_{rate_label}.mp4"
    )
    if audible_output_path.exists() and not overwrite:
        raise FileExistsError(
            f"output exists; pass --overwrite: {audible_output_path}"
        )
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
            str(audible_list_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-vf",
            f"fps={signature['r_frame_rate']},format={signature['pix_fmt']}",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            str(signature["pix_fmt"]),
            "-video_track_timescale",
            "15360",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(audible_output_path),
        ],
        check=True,
    )
    audible_label_path = collection_dir / f"{series}__material_audio_labels.srt"
    write_label_srt(audible_label_path, audible_rows)
    audible_output_probe = probe(audible_output_path, ffprobe)
    audible_video = next(
        (
            row
            for row in audible_output_probe.get("streams", [])
            if row.get("codec_type") == "video"
        ),
        {},
    )
    audible_audio = next(
        (
            row
            for row in audible_output_probe.get("streams", [])
            if row.get("codec_type") == "audio"
        ),
        {},
    )
    if (
        audible_video.get("width") != width
        or audible_video.get("height") != height
        or audible_video.get("pix_fmt") != signature["pix_fmt"]
        or audible_video.get("r_frame_rate") != signature["r_frame_rate"]
    ):
        errors.append("audible_native_video_signature_changed")
    if (
        audible_audio.get("sample_rate") != "48000"
        or audible_audio.get("channels") != 2
    ):
        errors.append("audible_audio_signature_invalid")
    audible_output_duration_ms = round(
        float(audible_output_probe["format"]["duration"]) * 1000
    )
    if abs(audible_output_duration_ms - audible_offset_ms) > max(
        200, len(audible_event_sources) * 35
    ):
        errors.append("audible_duration_mismatch")

    hybrid_slot_story = any(
        "hybrid" in str(row.get("audience_exclusion_reason", "")).casefold()
        for row in sources
    )
    role_voice_audio_rows = []
    all_audio_rows = []
    for source in audible_event_sources:
        for audio_row in source.get("official_audio_evidence", []):
            if not isinstance(audio_row, dict):
                continue
            audited_row = {
                "event": source["event"],
                "request_id": str(audio_row.get("request_id", "")),
                "code_name": str(audio_row.get("code_name", "")),
                "start_ms": int(audio_row.get("start_ms", 0)),
                "duration_ms": int(audio_row.get("duration_ms", 0)),
                "path": str(audio_row.get("path", "")),
                "evidence": str(audio_row.get("evidence", "")),
            }
            all_audio_rows.append(audited_row)
            if is_role_voice_audio(audio_row):
                role_voice_audio_rows.append(audited_row)
    role_voice_events = sorted(
        {row["event"] for row in role_voice_audio_rows}, key=event_sort_key
    )
    gameplay_marker = has_gameplay_marker(
        [
            *(str(row.get("dgm_name", "")) for row in sources),
            *(str(row.get("audience_exclusion_reason", "")) for row in sources),
            *(str(row.get("code_name", "")) for row in all_audio_rows),
        ]
    )
    lane = material_lane(
        role_voice_audio_count=len(role_voice_audio_rows),
        gameplay_marker=gameplay_marker,
        hybrid_slot_story=hybrid_slot_story,
    )
    transcript_required = any(
        "transcript remains required"
        in str(row.get("audience_exclusion_reason", "")).casefold()
        for row in sources
    )
    manifest = {
        "schema": "magireco-material-component-collection-v2",
        "series": series,
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "classification": lane,
        "semantic_lane": lane,
        "pure_material": not role_voice_audio_rows,
        "role_voice_audio_count": len(role_voice_audio_rows),
        "non_dialogue_audio_count": len(all_audio_rows) - len(role_voice_audio_rows),
        "role_voice_events": role_voice_events,
        "role_voice_audio": role_voice_audio_rows,
        "gameplay_marker": gameplay_marker,
        "transcript_status": (
            "required_not_verified" if transcript_required else "not_applicable"
        ),
        "direct_video_stream_copy": True,
        "audible_video_reencoded_at_native_signature": True,
        "audio_policy": (
            "the original visual-only collection remains a direct H.264 stream copy; "
            "the audible review edition mixes only official manifest audio at verified "
            "event offsets and holds each final source frame until its audio ends"
        ),
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "video_signature": signature,
        "output": str(output_path.resolve()),
        "labels": str(label_path.resolve()),
        "output_sha256": file_sha256(output_path),
        "output_video_packet_sha256": video_packet_hash(output_path, ffmpeg),
        "output_probe": output_probe,
        "audible_output": str(audible_output_path.resolve()),
        "audible_labels": str(audible_label_path.resolve()),
        "audible_duration_ms": audible_output_duration_ms,
        "audible_output_sha256": file_sha256(audible_output_path),
        "audible_video_packet_sha256": video_packet_hash(
            audible_output_path, ffmpeg
        ),
        "audible_audio_packet_sha256": audio_packet_hash(
            audible_output_path, ffmpeg
        ),
        "audible_output_probe": audible_output_probe,
        "audible_event_sources": audible_event_sources,
        "sources": sources,
    }
    manifest_path = collection_dir / "material_collection_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(f"{series} material collection QA failed: {errors}")
    return {
        "series": series,
        "status": "passed",
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "width": width,
        "height": height,
        "frame_rate": signature["r_frame_rate"],
        "output": str(output_path.resolve()),
        "audible_output": str(audible_output_path.resolve()),
        "audible_duration_ms": audible_output_duration_ms,
        "audio_sample_rate": audible_audio.get("sample_rate", ""),
        "audio_channels": audible_audio.get("channels", 0),
        "manifest": str(manifest_path.resolve()),
        "semantic_lane": lane,
        "pure_material": not role_voice_audio_rows,
        "role_voice_audio_count": len(role_voice_audio_rows),
        "role_voice_events": "|".join(role_voice_events),
    }


def audio_signature(payload: dict) -> dict:
    stream = next(
        (
            row
            for row in payload.get("streams", [])
            if row.get("codec_type") == "audio"
        ),
        {},
    )
    return {
        key: stream.get(key, "")
        for key in (
            "codec_name",
            "sample_rate",
            "channels",
            "channel_layout",
            "time_base",
        )
    }


def audio_peak_db(path: Path, ffmpeg: str) -> float | None:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
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
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    match = re.search(r"max_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB", result.stderr)
    if not match or match.group(1) == "-inf":
        return None
    return float(match.group(1))


def read_video_map(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return {
            str(row.get("official_name", "")).casefold(): row
            for row in csv.DictReader(source)
            if str(row.get("official_name", "")).strip()
        }


def build_named_collection(
    plan_path: Path,
    video_map: dict[str, dict[str, str]],
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    collection = str(plan.get("collection", "")).strip()
    if not collection:
        raise ValueError(f"named material plan has no collection: {plan_path}")
    planned_clips = plan.get("clips", [])
    if not isinstance(planned_clips, list) or len(planned_clips) < 2:
        raise ValueError(f"named material plan needs at least two clips: {plan_path}")
    sources = []
    signature: dict | None = None
    embedded_audio_signature: dict | None = None
    offset_ms = 0
    for planned in planned_clips:
        official_name = str(planned.get("official_name", "")).strip()
        map_row = video_map.get(official_name.casefold(), {})
        source_path = Path(
            str(map_row.get("target_mp4") or map_row.get("source_mp4") or "")
        ).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(
                f"unresolved named material {official_name}: {source_path}"
            )
        source_probe = probe(source_path, ffprobe)
        source_signature = video_signature(source_probe)
        source_audio_signature = audio_signature(source_probe)
        if signature is None:
            signature = source_signature
            embedded_audio_signature = source_audio_signature
        elif source_signature != signature:
            raise ValueError(
                f"named material video mismatch for {official_name}: "
                f"{source_signature} != {signature}"
            )
        elif source_audio_signature != embedded_audio_signature:
            raise ValueError(
                f"named material audio mismatch for {official_name}: "
                f"{source_audio_signature} != {embedded_audio_signature}"
            )
        duration_ms = round(float(source_probe["format"]["duration"]) * 1000)
        peak_db = (
            audio_peak_db(source_path, ffmpeg)
            if source_audio_signature.get("codec_name")
            else None
        )
        sources.append(
            {
                "order": len(sources) + 1,
                "event": str(planned.get("label") or official_name),
                "dgm_name": official_name,
                "official_name": official_name,
                "start_ms": offset_ms,
                "end_ms": offset_ms + duration_ms,
                "duration_ms": duration_ms,
                "path": str(source_path),
                "source_sha256": file_sha256(source_path),
                "source_video_packet_sha256": video_packet_hash(source_path, ffmpeg),
                "source_audio_packet_sha256": (
                    audio_packet_hash(source_path, ffmpeg)
                    if source_audio_signature.get("codec_name")
                    else ""
                ),
                "source_audio_peak_db": peak_db,
                "source_probe": source_probe,
            }
        )
        offset_ms += duration_ms
    if signature is None or embedded_audio_signature is None:
        raise ValueError(f"named material plan resolved no sources: {plan_path}")

    width = signature["width"]
    height = signature["height"]
    rate_label = str(signature["r_frame_rate"]).replace("/", "-")
    collection_dir = out_root / collection
    audit_dir = collection_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    list_path = audit_dir / "materials.ffconcat"
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(Path(row["path"])) for row in sources)
        + "\n",
        encoding="utf-8",
    )
    output_path = (
        collection_dir
        / f"{collection}__material_components__{width}x{height}_{rate_label}.mp4"
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    command = [
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
    ]
    if embedded_audio_signature.get("codec_name"):
        command.extend(["-map", "0:a:0"])
    command.extend(["-c", "copy", "-movflags", "+faststart", str(output_path)])
    subprocess.run(command, check=True)
    label_path = collection_dir / f"{collection}__material_labels.srt"
    write_label_srt(label_path, sources)
    output_probe = probe(output_path, ffprobe)
    errors = []
    if video_signature(output_probe) != signature:
        errors.append("stream_signature_changed")
    if audio_signature(output_probe) != embedded_audio_signature:
        errors.append("embedded_audio_signature_changed")
    output_duration_ms = round(float(output_probe["format"]["duration"]) * 1000)
    if abs(output_duration_ms - offset_ms) > max(100, len(sources) * 35):
        errors.append("duration_mismatch")
    output_peak_db = (
        audio_peak_db(output_path, ffmpeg)
        if embedded_audio_signature.get("codec_name")
        else None
    )
    expected_audio_state = str(plan.get("expected_audio_state", "")).strip()
    if expected_audio_state == "digital_silence" and (
        output_peak_db is not None and output_peak_db > -90.0
    ):
        errors.append("expected_digital_silence_but_audio_is_audible")
    manifest = {
        "schema": "magireco-named-material-collection-v1",
        "collection": collection,
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "classification": str(plan.get("classification", "material_components")),
        "evidence": str(plan.get("evidence", "")),
        "direct_stream_copy": True,
        "expected_audio_state": expected_audio_state,
        "output_audio_peak_db": output_peak_db,
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "video_signature": signature,
        "embedded_audio_signature": embedded_audio_signature,
        "output": str(output_path.resolve()),
        "labels": str(label_path.resolve()),
        "output_sha256": file_sha256(output_path),
        "output_video_packet_sha256": video_packet_hash(output_path, ffmpeg),
        "output_audio_packet_sha256": (
            audio_packet_hash(output_path, ffmpeg)
            if embedded_audio_signature.get("codec_name")
            else ""
        ),
        "output_probe": output_probe,
        "source_plan": str(plan_path.resolve()),
        "sources": sources,
    }
    manifest_path = collection_dir / "material_collection_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(
            f"{collection} named material collection QA failed: {errors}"
        )
    return {
        "series": collection,
        "status": "passed",
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "width": width,
        "height": height,
        "frame_rate": signature["r_frame_rate"],
        "audio_sample_rate": embedded_audio_signature.get("sample_rate", ""),
        "audio_channels": embedded_audio_signature.get("channels", 0),
        "audio_peak_db": output_peak_db,
        "output": str(output_path.resolve()),
        "manifest": str(manifest_path.resolve()),
    }


def main() -> int:
    args = parse_args()
    root = Path(args.manifest_root).resolve()
    manifest_dir = root / "events" if (root / "events").is_dir() else root
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for series in args.series:
        row = build_collection(
            series,
            manifest_dir,
            out_root,
            args.ffmpeg,
            args.ffprobe,
            args.overwrite,
        )
        rows.append(row)
        print(f"[passed] {series}: {row['clip_count']} material clips", flush=True)
    if args.plan:
        video_map = read_video_map(Path(args.video_map))
        for plan in args.plan:
            row = build_named_collection(
                Path(plan),
                video_map,
                out_root,
                args.ffmpeg,
                args.ffprobe,
                args.overwrite,
            )
            rows.append(row)
            print(
                f"[passed] {row['series']}: {row['clip_count']} named material clips",
                flush=True,
            )
    summary = {
        "schema": "magireco-material-collection-summary-v2",
        "collection_count": len(rows),
        "passed": len(rows),
        "failed": 0,
        "direct_video_stream_copy": True,
        "audible_review_edition": True,
        "collections": rows,
    }
    (out_root / "material_collection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
