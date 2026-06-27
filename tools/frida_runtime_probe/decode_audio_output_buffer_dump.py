#!/usr/bin/env python3
"""Decode `audio_output_buffer_probe.js` JSONL chunks to a diagnostic WAV.

The probe hooks `zg::snd::OutputCtrl::output(bool, TransBuf const&)` at the
internal tail point immediately before the game calls its audio-device write
function.  In normal operation `output_buffer_chunk` payloads are the final
output buffer prepared by the game.  When the runtime `OutputCtrl` device pointer
is null, the probe can also dump `transbuf_chunk` payloads as mechanism evidence;
those diagnostic modes decode the upstream four-plane `TransBuf` layout and are
not delivery-quality scene audio.

Expected format:

- signed 16-bit little-endian PCM;
- 48 kHz;
- stereo;
- 0x2000 bytes per output buffer.
"""

from __future__ import annotations

import argparse
import base64
import struct
import json
import wave
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--metadata-json")
    parser.add_argument("--sample-rate", type=int, default=48_000)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--sample-width", type=int, default=2)
    parser.add_argument(
        "--decode-mode",
        choices=("direct-output-buffer", "transbuf-interleave", "transbuf-fold-listen1"),
        default="direct-output-buffer",
        help=(
            "direct-output-buffer writes output_buffer_chunk payloads as-is. "
            "transbuf-interleave converts four 0x800-byte TransBuf planes to "
            "chronological stereo frames. transbuf-fold-listen1 mirrors the "
            "OutputCtrl listen-mode-1 fold observed in the disassembly."
        ),
    )
    return parser.parse_args()


def clamp_i16(value: int) -> int:
    return max(-32768, min(32767, value))


def iter_stereo_i16_frames(chunk: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<hh", chunk, offset)


def decode_transbuf_interleave(chunk: bytes) -> bytes:
    if len(chunk) < 0x2000:
        raise ValueError(f"TransBuf chunk is too small: {len(chunk)}")
    output = bytearray()
    for offset in range(0, 0x800, 4):
        for plane in (0, 0x800, 0x1000, 0x1800):
            left, right = iter_stereo_i16_frames(chunk, plane + offset)
            output += struct.pack("<hh", left, right)
    return bytes(output)


def decode_transbuf_fold_listen1(chunk: bytes) -> bytes:
    if len(chunk) < 0x2000:
        raise ValueError(f"TransBuf chunk is too small: {len(chunk)}")
    output = bytearray()
    for offset in range(0, 0x800, 4):
        left_sum = 0
        right_sum = 0
        for plane in (0, 0x800, 0x1000, 0x1800):
            left, right = iter_stereo_i16_frames(chunk, plane + offset)
            left_sum += left
            right_sum += right
        # The listen-mode-1 branch in OutputCtrl uses signed halving add after
        # summing the first three planes with the fourth plane.  This is a
        # faithful approximation for diagnostic listening.
        left = clamp_i16(left_sum // 2)
        right = clamp_i16(right_sum // 2)
        frame = struct.pack("<hh", left, right)
        output += frame * 4
    return bytes(output)


def decode_chunk(chunk: bytes, mode: str) -> bytes:
    if mode == "direct-output-buffer":
        return chunk
    if mode == "transbuf-interleave":
        return decode_transbuf_interleave(chunk)
    if mode == "transbuf-fold-listen1":
        return decode_transbuf_fold_listen1(chunk)
    raise ValueError(f"unsupported decode mode: {mode}")


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

    chunks: list[bytes] = []
    rows: list[dict] = []
    with jsonl_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            payload = record.get("message", {}).get("payload", {})
            wanted_kind = (
                "output_buffer_chunk"
                if args.decode_mode == "direct-output-buffer"
                else "transbuf_chunk"
            )
            if payload.get("kind") != wanted_kind:
                continue
            data_base64 = record.get("data_base64")
            if not data_base64:
                continue
            chunk = base64.b64decode(data_base64)
            decoded_chunk = decode_chunk(chunk, args.decode_mode)
            chunks.append(decoded_chunk)
            rows.append(
                {
                    "line_number": line_number,
                    "host_unix_ms": record.get("host_unix_ms"),
                    "unix_ms": payload.get("unix_ms"),
                    "call_count": payload.get("call_count"),
                    "chunk_index": payload.get("chunk_index"),
                    "output_buffer_bytes": payload.get("output_buffer_bytes"),
                    "output_buffer_pointer": payload.get("output_buffer_pointer"),
                    "transbuf_pointer": payload.get("transbuf_pointer"),
                    "device_write_function": payload.get("device_write_function"),
                    "head_hex": (
                        payload.get("output_buffer_head", {}).get("hex", "")
                        or payload.get("transbuf_head", {}).get("hex", "")
                    ),
                    "source_byte_count": len(chunk),
                    "decoded_byte_count": len(decoded_chunk),
                }
            )

    with wave.open(str(wav_path), "wb") as target:
        target.setnchannels(args.channels)
        target.setsampwidth(args.sample_width)
        target.setframerate(args.sample_rate)
        for chunk in chunks:
            target.writeframes(chunk)

    total_bytes = sum(len(chunk) for chunk in chunks)
    frame_count = total_bytes // (args.channels * args.sample_width)
    summary = {
        "source_jsonl": str(jsonl_path),
        "output_wav": str(wav_path),
        "chunk_count": len(chunks),
        "total_pcm_bytes": total_bytes,
        "sample_rate": args.sample_rate,
        "channels": args.channels,
        "sample_width": args.sample_width,
        "decode_mode": args.decode_mode,
        "frame_count": frame_count,
        "duration_seconds": frame_count / args.sample_rate,
        "chunks": rows,
    }
    metadata_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "chunks"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
