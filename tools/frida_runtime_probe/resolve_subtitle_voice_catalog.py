#!/usr/bin/env python3
"""Resolve static subtitle rows to high-quality OGG voice requests."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


PLACEHOLDER_RE = re.compile(
    r"^(?:空白のテキストレイヤー|ブラック(?:\s|$)|ホワイト(?:\s|$)|"
    r"平面(?:\s|$)|null_|none$)",
    re.IGNORECASE,
)
JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
SOUND_ID_RE = re.compile(r"^(\d{4,5})(?:_|$)")
SPEAKER_TOKEN_RE = re.compile(
    r"(?:^|_)(mad|iro|hom|say|kyk|mam|nag|nem|tou|toka|ari|"
    r"fel|ui|mif|yach|tur|mit|kan|ren|riko|mom|kae|tsu|kuro)(?:_|$)",
    re.IGNORECASE,
)
SPEAKER_ALIASES = {
    "tou": "toka",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--manifest-dir", required=True)
    parser.add_argument("--ogg-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--voice-delay-ms", type=int, default=60)
    parser.add_argument("--fuzzy-threshold", type=float, default=0.88)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.replace("\\n", "")
    return "".join(char for char in normalized if char.isalnum()).casefold()


def request_label(code_name: str) -> str:
    parts = code_name.split("_", 3)
    return parts[3] if len(parts) == 4 else ""


def speaker_hint(z2d_name: str) -> str:
    match = SPEAKER_TOKEN_RE.search(z2d_name)
    value = match.group(1).lower() if match else ""
    return SPEAKER_ALIASES.get(value, value)


def request_speaker(code_name: str) -> str:
    parts = code_name.split("_", 2)
    return parts[1].lower() if len(parts) > 1 else ""


def main() -> int:
    args = parse_args()
    timeline_rows = read_csv(Path(args.timeline))
    manifest_dir = Path(args.manifest_dir)
    request_rows = read_csv(manifest_dir / "sound_request_struct_requests.csv")
    hash_rows = read_csv(manifest_dir / "sound_hashreq_records.csv")
    sound_id_rows = read_csv(manifest_dir / "sound_id_records.csv")
    duration_by_request = {
        row.get("request_id", ""): row.get("duration_ms_u32", "")
        for row in hash_rows
    }
    sound_by_resource: dict[str, list[dict[str, str]]] = {}
    for row in sound_id_rows:
        sound_by_resource.setdefault(row.get("sound_resource_id", ""), []).append(row)
    ogg_by_name = {
        path.name.lower(): path for path in Path(args.ogg_dir).rglob("*.ogg")
    }

    requests: list[dict[str, str]] = []
    exact_index: dict[str, list[dict[str, str]]] = {}
    for row in request_rows:
        code_name = row.get("code_name", "")
        label = request_label(code_name)
        normalized = normalize_text(label)
        if not normalized or not JAPANESE_RE.search(label):
            continue
        item = {
            **row,
            "label_text": label,
            "normalized_label": normalized,
            "speaker": request_speaker(code_name),
        }
        requests.append(item)
        exact_index.setdefault(normalized, []).append(item)
    request_by_id = {row.get("request_id", ""): row for row in requests}

    result_rows: list[dict] = []
    for timeline in timeline_rows:
        display_text = timeline.get("display_text", "").strip()
        if (
            not display_text
            or PLACEHOLDER_RE.match(display_text)
            or not JAPANESE_RE.search(display_text)
        ):
            continue
        normalized = normalize_text(display_text)
        hint = speaker_hint(timeline.get("z2d_name", ""))
        previous_request_id = timeline.get("sound_request_id", "")
        previous_request = request_by_id.get(previous_request_id)
        previous_valid = False
        if previous_request:
            previous_label = previous_request["normalized_label"]
            speaker_matches = (
                not hint or previous_request.get("speaker", "") == hint
            )
            previous_valid = speaker_matches and (
                normalized in previous_label or previous_label in normalized
            )
        if previous_valid:
            candidates = [previous_request]
            match_method = "existing_request_id_verified"
        else:
            candidates = list(exact_index.get(normalized, []))
            match_method = "exact_normalized"

        if not previous_valid and hint and len(candidates) > 1:
            speaker_candidates = [
                row for row in candidates if row.get("speaker") == hint
            ]
            if speaker_candidates:
                candidates = speaker_candidates
                match_method = "exact_normalized_speaker"

        if not candidates:
            containment = [
                row
                for row in requests
                if len(normalized) >= 4
                and (
                    normalized in row["normalized_label"]
                    or row["normalized_label"] in normalized
                )
            ]
            if hint:
                speaker_containment = [
                    row for row in containment if row.get("speaker") == hint
                ]
                if speaker_containment:
                    containment = speaker_containment
                    match_method = "containment_speaker"
                else:
                    match_method = "containment"
            else:
                match_method = "containment"
            candidates = containment

        fuzzy_score = 0.0
        fuzzy_candidate: dict[str, str] | None = None
        if not candidates:
            pool = (
                [row for row in requests if row.get("speaker") == hint]
                if hint
                else requests
            )
            scored = sorted(
                (
                    (
                        SequenceMatcher(
                            None, normalized, row["normalized_label"]
                        ).ratio(),
                        row,
                    )
                    for row in pool
                ),
                key=lambda item: item[0],
                reverse=True,
            )
            if scored:
                fuzzy_score, fuzzy_candidate = scored[0]
                if fuzzy_score >= args.fuzzy_threshold:
                    candidates = [fuzzy_candidate]
                    match_method = "fuzzy_review"

        unique_candidate = candidates[0] if len(candidates) == 1 else None
        candidate_normalized_label = (
            unique_candidate.get("normalized_label", "")
            if unique_candidate
            else ""
        )
        coverage_ratio = (
            min(len(normalized), len(candidate_normalized_label))
            / max(len(normalized), len(candidate_normalized_label))
            if normalized and candidate_normalized_label
            else 0.0
        )
        strong_truncated_match = (
            unique_candidate is not None
            and len(candidate_normalized_label) >= 8
            and (
                (
                    match_method == "containment_speaker"
                    and coverage_ratio >= 0.55
                )
                or (
                    match_method == "containment"
                    and coverage_ratio >= 0.80
                )
            )
        )
        auto_accepted = (
            unique_candidate is not None
            and (
                match_method
                in {
                    "existing_request_id_verified",
                    "exact_normalized",
                    "exact_normalized_speaker",
                }
                or strong_truncated_match
            )
        )
        request_id = unique_candidate.get("request_id", "") if unique_candidate else ""
        code_name = unique_candidate.get("code_name", "") if unique_candidate else ""
        sound_match = SOUND_ID_RE.match(code_name)
        sound_resource_id = sound_match.group(1) if sound_match else ""
        sound_rows = sound_by_resource.get(sound_resource_id, [])
        sound_row = sound_rows[0] if sound_rows else {}
        ogg_name = sound_row.get("suggested_name", "")
        ogg_path = ogg_by_name.get(ogg_name.lower()) if ogg_name else None
        duration_ms = int(duration_by_request.get(request_id, "") or 0)
        subtitle_start_ms = int(float(timeline.get("start_ms", "0") or 0))
        visual_end_ms = int(float(timeline.get("visual_end_ms", "0") or 0))
        voice_start_ms = subtitle_start_ms + args.voice_delay_ms
        subtitle_end_ms = max(visual_end_ms, voice_start_ms + duration_ms)

        result_rows.append(
            {
                "event_name": timeline.get("event_name", ""),
                "event_index": timeline.get("event_index", ""),
                "z2d_order": timeline.get("z2d_order", ""),
                "z2d_name": timeline.get("z2d_name", ""),
                "display_text": display_text,
                "srt_text": timeline.get("srt_text", ""),
                "subtitle_start_ms": subtitle_start_ms,
                "subtitle_end_ms": subtitle_end_ms,
                "voice_start_ms": voice_start_ms,
                "voice_delay_ms": args.voice_delay_ms,
                "speaker_hint": hint,
                "normalized_text": normalized,
                "match_method": match_method,
                "candidate_count": len(candidates),
                "candidate_normalized_label": candidate_normalized_label,
                "coverage_ratio": (
                    f"{coverage_ratio:.6f}" if coverage_ratio else ""
                ),
                "auto_accepted": "yes" if auto_accepted else "no",
                "fuzzy_score": f"{fuzzy_score:.6f}" if fuzzy_score else "",
                "sound_request_id": request_id,
                "sound_request_code_name": code_name,
                "sound_resource_id": sound_resource_id,
                "sound_duration_ms": duration_ms,
                "ogg_name": ogg_name,
                "ogg_path": str(ogg_path) if ogg_path else "",
                "ogg_exists": "yes" if ogg_path else "no",
                "previous_sound_request_id": timeline.get("sound_request_id", ""),
                "previous_ogg_name": timeline.get("ogg_name", ""),
                "timeline_confidence": timeline.get("timeline_confidence", ""),
                "video_source_path": timeline.get("video_source_path", ""),
            }
        )

    fields = [
        "event_name",
        "event_index",
        "z2d_order",
        "z2d_name",
        "display_text",
        "srt_text",
        "subtitle_start_ms",
        "subtitle_end_ms",
        "voice_start_ms",
        "voice_delay_ms",
        "speaker_hint",
        "normalized_text",
        "match_method",
        "candidate_count",
        "candidate_normalized_label",
        "coverage_ratio",
        "auto_accepted",
        "fuzzy_score",
        "sound_request_id",
        "sound_request_code_name",
        "sound_resource_id",
        "sound_duration_ms",
        "ogg_name",
        "ogg_path",
        "ogg_exists",
        "previous_sound_request_id",
        "previous_ogg_name",
        "timeline_confidence",
        "video_source_path",
    ]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "subtitle_voice_catalog.csv", result_rows, fields)
    accepted = [
        row
        for row in result_rows
        if row["auto_accepted"] == "yes" and row["ogg_exists"] == "yes"
    ]
    unresolved = [
        row
        for row in result_rows
        if row["auto_accepted"] != "yes" or row["ogg_exists"] != "yes"
    ]
    ambiguous = [row for row in result_rows if int(row["candidate_count"]) > 1]
    write_csv(out_dir / "subtitle_voice_auto_accepted.csv", accepted, fields)
    write_csv(out_dir / "subtitle_voice_unresolved.csv", unresolved, fields)
    write_csv(out_dir / "subtitle_voice_ambiguous.csv", ambiguous, fields)

    counts = Counter(row["match_method"] for row in result_rows)
    summary = {
        "input_timeline_rows": len(timeline_rows),
        "real_text_rows": len(result_rows),
        "auto_accepted_rows": len(accepted),
        "unresolved_rows": len(unresolved),
        "ambiguous_rows": len(ambiguous),
        "events_with_auto_voice": len({row["event_name"] for row in accepted}),
        "voice_delay_calibration_ms": args.voice_delay_ms,
        "match_method_counts": dict(sorted(counts.items())),
    }
    with (out_dir / "subtitle_voice_summary.json").open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
