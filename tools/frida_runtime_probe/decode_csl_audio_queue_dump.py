#!/usr/bin/env python3
"""Decode `csl_audio_queue_probe.js` OpenSL queue chunks to a diagnostic WAV.

This decodes data captured at `CSLAndroidSimpleBufferQueue::Enqueue`, the
libAMAIN/OpenSL playback queue used by the game runtime.  Unlike visual or
manifest-only matching, this is evidence from the game's audible output path.

The expected runtime format for the observed slot build is signed 16-bit
little-endian PCM, 48 kHz, stereo.  The script keeps metadata and basic signal
statistics so bad captures can be rejected before any delivery render.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import struct
import wave
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--metadata-json")
    parser.add_argument("--sample-rate", type=int, default=48_000)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--sample-width", type=int, default=2)
    parser.add_argument(
        "--layout",
        choices=("concat", "timeline"),
        default="concat",
        help=(
            "concat writes queue chunks back-to-back. timeline places chunks at "
            "their runtime unix_ms offsets and saturating-mixes overlaps."
        ),
    )
    parser.add_argument(
        "--sound-id",
        type=int,
        action="append",
        help="Keep only chunks whose inferred sound_id_u16_at_0x2 matches this value.",
    )
    return parser.parse_args()


def iter_i16_samples(chunk: bytes) -> Iterable[int]:
    usable = len(chunk) - (len(chunk) % 2)
    for (sample,) in struct.iter_unpack("<h", chunk[:usable]):
        yield sample


def pcm_stats(chunks: list[bytes]) -> dict:
    sample_count = 0
    zero_count = 0
    clipped_count = 0
    peak_abs = 0
    sum_abs = 0
    sum_square = 0

    for chunk in chunks:
        for sample in iter_i16_samples(chunk):
            value = abs(sample)
            sample_count += 1
            if sample == 0:
                zero_count += 1
            if value >= 32767:
                clipped_count += 1
            peak_abs = max(peak_abs, value)
            sum_abs += value
            sum_square += sample * sample

    if sample_count == 0:
        return {
            "sample_count": 0,
            "zero_ratio": None,
            "clipped_ratio": None,
            "peak_abs": 0,
            "peak_dbfs": None,
            "mean_abs": None,
            "rms": None,
            "rms_dbfs": None,
        }

    rms = math.sqrt(sum_square / sample_count)
    return {
        "sample_count": sample_count,
        "zero_ratio": zero_count / sample_count,
        "clipped_ratio": clipped_count / sample_count,
        "peak_abs": peak_abs,
        "peak_dbfs": 20 * math.log10(peak_abs / 32768) if peak_abs > 0 else None,
        "mean_abs": sum_abs / sample_count,
        "rms": rms,
        "rms_dbfs": 20 * math.log10(rms / 32768) if rms > 0 else None,
    }


def clamp_i16(value: int) -> int:
    return max(-32768, min(32767, value))


def render_concat(chunks: list[bytes]) -> bytes:
    return b"".join(chunks)


def render_timeline(chunks: list[bytes], rows: list[dict], args: argparse.Namespace) -> tuple[bytes, list[dict]]:
    if not chunks:
        return b"", rows
    if args.sample_width != 2:
        raise ValueError("timeline layout currently requires 16-bit PCM")
    bytes_per_frame = args.channels * args.sample_width
    if bytes_per_frame <= 0:
        raise ValueError("invalid channel/sample width")

    first_unix_ms = min(row["unix_ms"] for row in rows if row["unix_ms"] is not None)
    placements: list[dict] = []
    total_samples = 0
    for chunk, row in zip(chunks, rows):
        relative_ms = (row["unix_ms"] or first_unix_ms) - first_unix_ms
        start_frame = round(relative_ms * args.sample_rate / 1000)
        start_sample = start_frame * args.channels
        sample_count = len(chunk) // args.sample_width
        total_samples = max(total_samples, start_sample + sample_count)
        placement = {
            "chunk_index": row.get("chunk_index"),
            "request_id_i32": row.get("request_id_i32"),
            "sound_id_u16_at_0x2": row.get("sound_id_u16_at_0x2"),
            "unix_ms": row.get("unix_ms"),
            "relative_ms": relative_ms,
            "start_frame": start_frame,
            "start_sample": start_sample,
            "sample_count": sample_count,
            "duration_seconds": sample_count / args.channels / args.sample_rate,
        }
        placements.append(placement)
        row["timeline"] = placement

    mix = [0] * total_samples
    overlap_samples = 0
    for chunk, placement in zip(chunks, placements):
        start_sample = placement["start_sample"]
        for index, sample in enumerate(iter_i16_samples(chunk)):
            target_index = start_sample + index
            if target_index >= len(mix):
                break
            if mix[target_index] != 0:
                overlap_samples += 1
            mix[target_index] = clamp_i16(mix[target_index] + sample)

    out = bytearray()
    for sample in mix:
        out += struct.pack("<h", sample)
    for placement in placements:
        placement["overlap_samples_total"] = overlap_samples
    return bytes(out), rows


def chunk_sound_id(payload: dict) -> int | None:
    value = payload.get("sound_id_u16_at_0x2")
    if isinstance(value, int):
        return value
    mapped = payload.get("sound", {})
    if isinstance(mapped, dict):
        value = mapped.get("sound_id_u16_at_0x2")
        if isinstance(value, int):
            return value
    return None


def main() -> int:
    args = parse_args()
    jsonl_path = Path(args.jsonl).resolve()
    wav_path = Path(args.wav).resolve()
    metadata_path = (
        Path(args.metadata_json).resolve()
        if args.metadata_json
        else wav_path.with_suffix(".metadata.json")
    )
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    wanted_sound_ids = set(args.sound_id or [])
    chunks: list[bytes] = []
    rows: list[dict] = []
    seen_kinds: dict[str, int] = {}

    with jsonl_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            payload = record.get("message", {}).get("payload", {})
            kind = payload.get("kind")
            if isinstance(kind, str):
                seen_kinds[kind] = seen_kinds.get(kind, 0) + 1
            if kind != "queue_enqueue_chunk":
                continue
            sound_id = chunk_sound_id(payload)
            if wanted_sound_ids and sound_id not in wanted_sound_ids:
                continue
            data_base64 = record.get("data_base64")
            if not data_base64:
                continue
            chunk = base64.b64decode(data_base64)
            chunks.append(chunk)
            rows.append(
                {
                    "line_number": line_number,
                    "host_unix_ms": record.get("host_unix_ms"),
                    "unix_ms": payload.get("unix_ms"),
                    "enqueue_call_count": payload.get("enqueue_call_count"),
                    "chunk_index": payload.get("chunk_index"),
                    "queue_object": payload.get("queue_object"),
                    "csl_sound": payload.get("csl_sound"),
                    "request_id_i32": payload.get("request_id_i32"),
                    "request_arg2_i32": payload.get("request_arg2_i32"),
                    "sound_data": payload.get("sound_data"),
                    "sound_id_u16_at_0x2": sound_id,
                    "buffer_pointer": payload.get("buffer_pointer"),
                    "buffer_bytes": payload.get("buffer_bytes"),
                    "source_byte_count": len(chunk),
                    "preview_hex": payload.get("preview", {}).get("hex", ""),
                }
            )

    if args.layout == "timeline":
        rendered_pcm, rows = render_timeline(chunks, rows, args)
    else:
        rendered_pcm = render_concat(chunks)

    with wave.open(str(wav_path), "wb") as target:
        target.setnchannels(args.channels)
        target.setsampwidth(args.sample_width)
        target.setframerate(args.sample_rate)
        target.writeframes(rendered_pcm)

    source_total_bytes = sum(len(chunk) for chunk in chunks)
    total_bytes = len(rendered_pcm)
    bytes_per_frame = args.channels * args.sample_width
    frame_count = total_bytes // bytes_per_frame if bytes_per_frame else 0
    sound_ids = sorted(
        {row["sound_id_u16_at_0x2"] for row in rows if row["sound_id_u16_at_0x2"] is not None}
    )
    summary = {
        "source_jsonl": str(jsonl_path),
        "output_wav": str(wav_path),
        "chunk_count": len(chunks),
        "source_total_pcm_bytes": source_total_bytes,
        "rendered_total_pcm_bytes": total_bytes,
        "sample_rate": args.sample_rate,
        "channels": args.channels,
        "sample_width": args.sample_width,
        "layout": args.layout,
        "frame_count": frame_count,
        "duration_seconds": frame_count / args.sample_rate if args.sample_rate else None,
        "filtered_sound_ids": sorted(wanted_sound_ids),
        "observed_sound_ids": sound_ids,
        "seen_kinds": seen_kinds,
        "source_signal": pcm_stats(chunks),
        "rendered_signal": pcm_stats([rendered_pcm]),
        "chunks": rows,
    }
    metadata_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "chunks"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
