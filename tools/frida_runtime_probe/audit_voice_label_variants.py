#!/usr/bin/env python3
"""Run several deterministic ASR passes for unresolved truncated voice labels."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from faster_whisper import WhisperModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--download-root", required=True)
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument(
        "--request-id",
        action="append",
        default=[],
        help="limit to one or more request IDs; defaults to review-required rows",
    )
    return parser.parse_args()


def compact_segments(segments) -> tuple[str, float, float]:
    rows = list(segments)
    text = "".join(row.text.strip() for row in rows).strip()
    if not rows:
        return "", -99.0, 1.0
    return (
        text,
        sum(row.avg_logprob for row in rows) / len(rows),
        max(row.no_speech_prob for row in rows),
    )


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    requested = {str(value) for value in args.request_id}
    with Path(args.audit_csv).open(encoding="utf-8-sig", newline="") as source:
        source_rows = list(csv.DictReader(source))
    candidates = [
        row
        for row in source_rows
        if (
            row["request_id"] in requested
            if requested
            else row["auto_accepted"] != "yes"
        )
    ]

    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        download_root=args.download_root,
    )
    configurations = [
        ("no_prompt_beam5", "", 5),
        ("prefix_beam5", "{prefix}", 5),
        ("no_prompt_beam10", "", 10),
        ("prefix_beam10", "{prefix}", 10),
    ]
    output_rows: list[dict[str, object]] = []
    for candidate in candidates:
        for variant, prompt_template, beam_size in configurations:
            prompt = prompt_template.format(prefix=candidate["label_prefix"])
            segments, info = model.transcribe(
                candidate["ogg_path"],
                language="ja",
                beam_size=beam_size,
                best_of=beam_size,
                condition_on_previous_text=False,
                vad_filter=False,
                initial_prompt=prompt or None,
                temperature=0.0,
            )
            text, avg_logprob, no_speech_prob = compact_segments(segments)
            row = {
                "request_id": candidate["request_id"],
                "code_name": candidate["code_name"],
                "label_prefix": candidate["label_prefix"],
                "variant": variant,
                "beam_size": beam_size,
                "initial_prompt": prompt,
                "asr_text": text,
                "language": info.language,
                "language_probability": f"{info.language_probability:.6f}",
                "avg_logprob": f"{avg_logprob:.6f}",
                "no_speech_prob": f"{no_speech_prob:.6f}",
                "duration_ms": candidate["duration_ms"],
                "ogg_path": candidate["ogg_path"],
                "events": candidate["events"],
            }
            output_rows.append(row)
            print(
                f"[{candidate['request_id']}:{variant}] {text}",
                flush=True,
            )

    fields = list(output_rows[0]) if output_rows else [
        "request_id",
        "code_name",
        "label_prefix",
        "variant",
        "beam_size",
        "initial_prompt",
        "asr_text",
        "language",
        "language_probability",
        "avg_logprob",
        "no_speech_prob",
        "duration_ms",
        "ogg_path",
        "events",
    ]
    csv_path = out_dir / "voice_label_variant_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    summary = {
        "candidate_count": len(candidates),
        "variant_count": len(output_rows),
        "model": args.model,
        "csv": str(csv_path),
    }
    (out_dir / "voice_label_variant_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
