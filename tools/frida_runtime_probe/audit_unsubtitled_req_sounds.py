#!/usr/bin/env python3
"""Transcribe exact reqSound tracks that have no linked subtitle row."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from faster_whisper import WhisperModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--download-root", required=True)
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    return parser.parse_args()


def compact_segments(segments) -> tuple[str, float, float, list[dict[str, object]]]:
    rows = list(segments)
    text = "".join(row.text.strip() for row in rows).strip()
    if not rows:
        return "", -99.0, 1.0, []
    return (
        text,
        sum(row.avg_logprob for row in rows) / len(rows),
        max(row.no_speech_prob for row in rows),
        [
            {
                "start_ms": round(row.start * 1000),
                "end_ms": round(row.end * 1000),
                "text": row.text.strip(),
                "avg_logprob": row.avg_logprob,
                "no_speech_prob": row.no_speech_prob,
            }
            for row in rows
            if row.text.strip()
        ],
    )


def main() -> int:
    args = parse_args()
    manifest_root = Path(args.manifest_root).resolve()
    manifest_dir = manifest_root / "events"
    if not manifest_dir.is_dir():
        manifest_dir = manifest_root
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates: dict[tuple[str, str], dict[str, object]] = {}
    occurrences: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for manifest_path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("quality_gates", {}).get("ready"):
            continue
        subtitle_keys = {
            (str(row.get("voice_request_id", "")), int(row.get("voice_start_ms", 0)))
            for row in manifest.get("subtitles", [])
        }
        for audio in manifest.get("audio", []):
            if audio.get("source") != "z2d_req_sound":
                continue
            request_id = str(audio["request_id"])
            start_ms = int(audio["start_ms"])
            if (request_id, start_ms) in subtitle_keys:
                continue
            path = str(audio["path"])
            key = (request_id, path)
            candidates.setdefault(
                key,
                {
                    "request_id": request_id,
                    "code_name": str(audio.get("code_name", "")),
                    "ogg_path": path,
                    "duration_ms": int(audio.get("duration_ms", 0)),
                },
            )
            occurrences[key].append(
                {
                    "event": str(manifest["event"]),
                    "start_ms": start_ms,
                }
            )

    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        download_root=args.download_root,
    )
    rows: list[dict[str, object]] = []
    for key, candidate in sorted(
        candidates.items(),
        key=lambda item: (int(item[1]["request_id"]), str(item[1]["ogg_path"])),
    ):
        variants = []
        for variant, beam_size in (("beam5", 5), ("beam10", 10)):
            segments, info = model.transcribe(
                str(candidate["ogg_path"]),
                language="ja",
                beam_size=beam_size,
                best_of=beam_size,
                condition_on_previous_text=False,
                vad_filter=False,
                temperature=0.0,
            )
            text, avg_logprob, no_speech_prob, timeline = compact_segments(segments)
            variants.append(
                {
                    "variant": variant,
                    "text": text,
                    "language": info.language,
                    "language_probability": info.language_probability,
                    "avg_logprob": avg_logprob,
                    "no_speech_prob": no_speech_prob,
                    "timeline": timeline,
                }
            )
        consensus = variants[0]["text"] if variants[0]["text"] == variants[1]["text"] else ""
        row = {
            **candidate,
            "asr_beam5": variants[0]["text"],
            "asr_beam10": variants[1]["text"],
            "exact_consensus": "yes" if consensus else "no",
            "consensus_text": consensus,
            "beam5_timeline_json": json.dumps(
                variants[0]["timeline"],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "language_probability": f"{min(item['language_probability'] for item in variants):.6f}",
            "avg_logprob": f"{min(item['avg_logprob'] for item in variants):.6f}",
            "max_no_speech_prob": f"{max(item['no_speech_prob'] for item in variants):.6f}",
            "events": ";".join(
                f"{item['event']}@{item['start_ms']}"
                for item in occurrences[key]
            ),
        }
        rows.append(row)
        print(
            f"[{candidate['request_id']}] {candidate['code_name']}: "
            f"{variants[0]['text']} | {variants[1]['text']}",
            flush=True,
        )

    fields = list(rows[0]) if rows else [
        "request_id",
        "code_name",
        "ogg_path",
        "duration_ms",
        "asr_beam5",
        "asr_beam10",
        "exact_consensus",
        "consensus_text",
        "beam5_timeline_json",
        "language_probability",
        "avg_logprob",
        "max_no_speech_prob",
        "events",
    ]
    csv_path = out_dir / "unsubtitled_req_sound_asr.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "unique_unsubtitled_req_sounds": len(rows),
        "exact_asr_consensus": sum(row["exact_consensus"] == "yes" for row in rows),
        "csv": str(csv_path),
    }
    (out_dir / "unsubtitled_req_sound_asr_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
