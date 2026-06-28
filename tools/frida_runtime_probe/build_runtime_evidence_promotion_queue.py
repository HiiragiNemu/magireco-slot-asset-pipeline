#!/usr/bin/env python3
"""Build a conservative promotion/isolation queue from runtime evidence packages.

This tool consumes the package index emitted by
`audit_runtime_evidence_packages.py`.  It does not generate production
manifests.  It decides only which evidence packages are:

- blocked because their evidence package failed;
- passed runtime evidence but must be isolated as slot/gameplay/material;
- passed runtime evidence and may be manually reviewed as a clean-story
  candidate later.

The purpose is to stop broad batch work from reading a passed audio package as
permission to render a Bilibili-facing animation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


GAMEPLAY_TERMS = {
    "slot",
    "reel",
    "subreel",
    "push",
    "chance",
    "win",
    "bb",
    "rb",
    "pt",
    "count",
    "coin",
    "medal",
    "btn",
    "button",
    "roulette",
}
GAMEPLAY_ROOT_RE = re.compile(r"^ac(?:09|90|91|92|93|94|95|96|97|98|99)")
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
NON_DIALOGUE_TERMS = (
    "BGM",
    "SE",
    "Voiceのみ停止",
    "停止",
    "消音",
    "ジングル",
    "タイトルSE",
)
DIALOGUE_OR_CHARACTER_PRESENTATION_TERMS = (
    "セリフ",
    "私服",
    "ﾜﾝﾋﾟ",
    "ワンピ",
    "撮影",
    "ﾓﾃﾞﾙ",
    "モデル",
    "注文演出",
    "喧嘩",
    "中華",
    "ﾊﾞｰｶﾞｰ",
    "バーガー",
)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def split_values(text: str) -> list[str]:
    if not text:
        return []
    values: list[str] = []
    for part in re.split(r"[;|,]", text):
        part = part.strip()
        if part:
            values.append(part)
    return values


def has_gameplay_marker(package: dict[str, Any], event_rows: list[dict[str, str]]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    capture_name = str(package.get("capture_name", "")).lower()
    label = str(package.get("label", "")).lower()
    if "slot" in capture_name or "slot" in label:
        reasons.append("package_name_contains_slot")

    for row in event_rows:
        root = str(row.get("root", ""))
        primary = str(row.get("primary_animation", ""))
        overlays = str(row.get("overlays", ""))
        video_mapping = str(row.get("video_mapping", ""))
        if root and GAMEPLAY_ROOT_RE.match(root):
            reasons.append(f"gameplay_root:{root}")
        joined = " ".join([root, primary, overlays, video_mapping]).lower()
        for term in GAMEPLAY_TERMS:
            if term in joined:
                reasons.append(f"gameplay_term:{term}")
    return bool(reasons), sorted(set(reasons))


def role_or_dialogue_audio_count(static_sounds: list[dict[str, str]]) -> int:
    count = 0
    for row in static_sounds:
        speaker = str(row.get("speaker_hint", "")).strip()
        subtitle = str(row.get("subtitle_text", "")).strip()
        label = str(row.get("label", "")).strip()
        code_name = str(row.get("code_name", "")).strip()
        combined = f"{code_name} {label}"
        speaker_match = re.search(r"^\d+_([A-Za-z]+)_", combined)
        if any(term in combined for term in NON_DIALOGUE_TERMS):
            continue
        if speaker or subtitle:
            count += 1
        elif speaker_match and speaker_match.group(1).lower() in ROLE_VOICE_SPEAKER_TOKENS:
            count += 1
        elif any(term in combined for term in DIALOGUE_OR_CHARACTER_PRESENTATION_TERMS):
            count += 1
    return count


def package_to_queue_row(package: dict[str, Any]) -> dict[str, Any]:
    package_dir = Path(str(package.get("package_dir", "")))
    event_rows = read_csv(package_dir / "evidence_skeleton" / "event_sequence.csv")
    static_sounds = read_csv(package_dir / "evidence_skeleton" / "static_event_sounds.csv")
    queue_rows = read_csv(package_dir / "evidence_skeleton" / "queue_sequence.csv")
    qa_path = Path(str(package.get("qa_report", "")))
    qa = read_json(qa_path) if qa_path.exists() else {}
    status = str(package.get("status", ""))
    gameplay_marker, gameplay_reasons = has_gameplay_marker(package, event_rows)
    roots = sorted({row.get("root", "") for row in event_rows if row.get("root")})
    primary = sorted({row.get("primary_animation", "") for row in event_rows if row.get("primary_animation")})
    sound_ids = sorted({row.get("sound_id_u16_at_0x2", "") for row in queue_rows if row.get("sound_id_u16_at_0x2")}, key=lambda value: int(value) if value.isdigit() else 999999)
    role_or_dialogue_count = role_or_dialogue_audio_count(static_sounds)

    if status != "passed_evidence_not_delivery":
        lane = "blocked_failed_runtime_evidence_package"
        clean_story_status = "not_eligible"
        next_action = "repair_or_recapture_before_any_manifest_promotion"
    elif gameplay_marker:
        lane = (
            "runtime_gameplay_or_slot_material_with_dialogue_audio"
            if role_or_dialogue_count
            else "runtime_gameplay_or_slot_material"
        )
        clean_story_status = "not_eligible_gameplay_or_slot_sequence"
        next_action = "review_for_material_or_gameplay_collection_only"
    else:
        lane = (
            "runtime_animation_candidate_with_dialogue_audio_needs_visual_subtitle_review"
            if role_or_dialogue_count
            else "runtime_animation_candidate_needs_visual_review"
        )
        clean_story_status = "candidate_needs_manual_visual_subtitle_review"
        next_action = "manual_review_before_production_manifest"

    return {
        "capture_name": package.get("capture_name", ""),
        "status": status,
        "promotion_lane": lane,
        "clean_story_status": clean_story_status,
        "next_action": next_action,
        "gameplay_marker": "yes" if gameplay_marker else "no",
        "gameplay_reasons": ";".join(gameplay_reasons),
        "role_or_dialogue_audio_count": role_or_dialogue_count,
        "root_count": len(roots),
        "roots": ";".join(roots),
        "primary_animation_count": len(primary),
        "primary_animations": ";".join(primary),
        "event_code_count": package.get("event_code_count", ""),
        "sound_code_lookup_count": package.get("sound_code_lookup_count", ""),
        "queue_chunk_count": package.get("queue_chunk_count", ""),
        "queue_metadata_count": package.get("queue_metadata_count", ""),
        "duration_seconds": package.get("duration_seconds", ""),
        "observed_sound_ids": package.get("observed_sound_ids", ";".join(sound_ids)),
        "failed_checks": package.get("failed_checks", ""),
        "package_dir": package.get("package_dir", ""),
        "qa_report": package.get("qa_report", ""),
        "explicit_guard": "not_render_ready;not_bilibili_ready",
        "qa_summary_status": qa.get("status", ""),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-index-json", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index = read_json(args.package_index_json.resolve())
    packages = index.get("packages", [])
    if not isinstance(packages, list):
        raise SystemExit("package index JSON has no packages list")
    rows = [package_to_queue_row(package) for package in packages if isinstance(package, dict)]
    lane_counts = Counter(row["promotion_lane"] for row in rows)
    clean_story_counts = Counter(row["clean_story_status"] for row in rows)

    fieldnames = [
        "capture_name",
        "status",
        "promotion_lane",
        "clean_story_status",
        "next_action",
        "gameplay_marker",
        "gameplay_reasons",
        "role_or_dialogue_audio_count",
        "root_count",
        "roots",
        "primary_animation_count",
        "primary_animations",
        "event_code_count",
        "sound_code_lookup_count",
        "queue_chunk_count",
        "queue_metadata_count",
        "duration_seconds",
        "observed_sound_ids",
        "failed_checks",
        "package_dir",
        "qa_report",
        "explicit_guard",
        "qa_summary_status",
    ]
    out_dir = args.out_dir.resolve()
    write_csv(out_dir / "runtime_evidence_promotion_queue.csv", rows, fieldnames)
    summary = {
        "schema": "magireco_runtime_evidence_promotion_queue.v1",
        "source_package_index": str(args.package_index_json.resolve()),
        "package_count": len(rows),
        "promotion_lane_counts": dict(lane_counts),
        "clean_story_status_counts": dict(clean_story_counts),
        "rows": rows,
    }
    write_json(out_dir / "runtime_evidence_promotion_queue.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
