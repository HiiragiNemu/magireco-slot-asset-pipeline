#!/usr/bin/env python3
"""Recover full Japanese dialogue for truncated official sound labels."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--download-root", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    return parser.parse_args()


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return "".join(char for char in normalized if char.isalnum())


def compact_segments(segments) -> tuple[str, float, float]:
    rows = list(segments)
    text = "".join(row.text.strip() for row in rows).strip()
    if not rows:
        return "", -99.0, 1.0
    avg_logprob = sum(row.avg_logprob for row in rows) / len(rows)
    no_speech_prob = max(row.no_speech_prob for row in rows)
    return text, avg_logprob, no_speech_prob


def main() -> int:
    args = parse_args()
    manifest_root = Path(args.manifest_root).resolve()
    manifest_dir = manifest_root / "events"
    if not manifest_dir.is_dir():
        manifest_dir = manifest_root
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates: dict[str, dict[str, str | int]] = {}
    for manifest_path in sorted(manifest_dir.glob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("quality_gates", {}).get("ready"):
            continue
        audio_by_key = {
            (str(row["request_id"]), int(row["start_ms"])): row
            for row in manifest["audio"]
            if row["source"] == "z2d_req_sound"
        }
        for subtitle in manifest["subtitles"]:
            if subtitle.get("subtitle_source") != "official_voice_label":
                continue
            key = (
                str(subtitle["voice_request_id"]),
                int(subtitle["voice_start_ms"]),
            )
            audio = audio_by_key.get(key)
            if not audio or not str(audio["code_name"]).endswith("-"):
                continue
            request_id = str(audio["request_id"])
            candidate = candidates.setdefault(
                request_id,
                {
                    "request_id": request_id,
                    "code_name": str(audio["code_name"]),
                    "ogg_path": str(audio["path"]),
                    "label_prefix": str(subtitle["text"]).rstrip("…"),
                    "duration_ms": int(audio["duration_ms"]),
                    "events": [],
                },
            )
            candidate["events"].append(str(manifest["event"]))

    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        download_root=args.download_root,
    )
    rows: list[dict[str, object]] = []
    accepted: dict[str, dict[str, object]] = {}
    for request_id, candidate in sorted(
        candidates.items(), key=lambda item: int(item[0])
    ):
        ogg_path = Path(str(candidate["ogg_path"]))
        prefix = str(candidate["label_prefix"])
        segments, info = model.transcribe(
            str(ogg_path),
            language="ja",
            beam_size=5,
            condition_on_previous_text=False,
            vad_filter=False,
            initial_prompt=prefix,
        )
        text, avg_logprob, no_speech_prob = compact_segments(segments)
        normalized_prefix = normalize_text(prefix)
        normalized_text = normalize_text(text)
        prefix_matches = bool(normalized_prefix) and normalized_text.startswith(
            normalized_prefix
        )
        auto_accepted = (
            prefix_matches
            and info.language == "ja"
            and info.language_probability >= 0.95
            and avg_logprob >= -0.8
            and no_speech_prob <= 0.35
            and len(normalized_text) > len(normalized_prefix)
        )
        row = {
            "request_id": request_id,
            "code_name": candidate["code_name"],
            "label_prefix": prefix,
            "asr_text": text,
            "prefix_matches": "yes" if prefix_matches else "no",
            "language": info.language,
            "language_probability": f"{info.language_probability:.6f}",
            "avg_logprob": f"{avg_logprob:.6f}",
            "no_speech_prob": f"{no_speech_prob:.6f}",
            "auto_accepted": "yes" if auto_accepted else "no",
            "duration_ms": candidate["duration_ms"],
            "ogg_path": str(ogg_path),
            "events": ";".join(sorted(set(candidate["events"]))),
        }
        rows.append(row)
        if auto_accepted:
            accepted[request_id] = {
                "text": text,
                "source": "faster_whisper_large_v3_turbo",
                "model": args.model,
                "prefix": prefix,
                "prefix_matches": True,
                "language_probability": info.language_probability,
                "avg_logprob": avg_logprob,
                "no_speech_prob": no_speech_prob,
                "ogg_path": str(ogg_path),
            }
        print(
            f"[{'accepted' if auto_accepted else 'review'}] "
            f"{request_id}: {text}",
            flush=True,
        )

    fields = [
        "request_id",
        "code_name",
        "label_prefix",
        "asr_text",
        "prefix_matches",
        "language",
        "language_probability",
        "avg_logprob",
        "no_speech_prob",
        "auto_accepted",
        "duration_ms",
        "ogg_path",
        "events",
    ]
    audit_path = out_dir / "truncated_voice_asr_audit.csv"
    with audit_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    overrides = {
        "schema": "magireco-voice-subtitle-overrides-v1",
        "model": args.model,
        "accepted": accepted,
        "review_required": [
            row["request_id"]
            for row in rows
            if row["auto_accepted"] != "yes"
        ],
        "audit_csv": str(audit_path),
    }
    override_path = out_dir / "voice_subtitle_overrides.json"
    override_path.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "unique_truncated_requests": len(rows),
        "auto_accepted": len(accepted),
        "review_required": len(rows) - len(accepted),
        "audit_csv": str(audit_path),
        "override_json": str(override_path),
    }
    (out_dir / "truncated_voice_asr_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
