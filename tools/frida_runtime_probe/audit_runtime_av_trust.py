#!/usr/bin/env python3
"""Audit whether rendered event outputs are trustworthy as final AV delivery.

This is stricter than the normal QA scripts.  A render can have valid H.264/AAC
streams, non-silent audio, and matching subtitle/no-subtitle audio hashes while
still being wrong for the project goal if the manifest only contains a partial
runtime sound timeline, if subtitles are inferred only from sound labels, or if
the event is a gameplay/result presentation with role voice mixed in.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


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

BGM_TERMS = ("BGM", "bgm", "ＢＧＭ", "次回予告", "レバー")
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
VOICE_SOURCES = ("z2d_req_sound",)
ASR_SOURCES = ("asr_verified", "voice_subtitle_override")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-manifest-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--event", action="append", default=[])
    parser.add_argument("--render-root", action="append", default=[])
    parser.add_argument("--series-root", action="append", default=[])
    parser.add_argument("--material-root", action="append", default=[])
    parser.add_argument("--invalidated-output-roots", action="append", default=[])
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_path(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def is_under(path: str | Path, root: str) -> bool:
    candidate = normalize_path(path)
    try:
        return os.path.commonpath([candidate, root]) == root
    except ValueError:
        return False


def load_invalidated(paths: list[Path]) -> tuple[list[dict[str, str]], set[str]]:
    rows: list[dict[str, str]] = []
    roots: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        payload = read_json(path)
        for row in payload.get("invalidated_roots", []):
            raw = str(row.get("path", "")).strip()
            if not raw:
                continue
            roots.add(normalize_path(raw))
            rows.append(
                {
                    "path": raw,
                    "scope": str(row.get("scope", "")),
                    "reason": str(row.get("reason", "")),
                }
            )
    return rows, roots


def manifest_dir(root: Path) -> Path:
    return root / "events" if (root / "events").is_dir() else root


def discover_render_events(roots: list[Path]) -> dict[str, set[str]]:
    events: dict[str, set[str]] = {}
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.name == "render_manifest.json" else root.rglob("render_manifest.json")
        for path in paths:
            if not path.is_file():
                continue
            try:
                payload = read_json(path)
            except json.JSONDecodeError:
                continue
            event = str(payload.get("event", "")).strip()
            if event:
                events.setdefault(event, set()).add(str(path))
    return events


def discover_series_events(roots: list[Path]) -> dict[str, set[str]]:
    events: dict[str, set[str]] = {}
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.name == "series_manifest.json" else root.rglob("series_manifest.json")
        for path in paths:
            if not path.is_file():
                continue
            payload = read_json(path)
            for row in payload.get("sources", []):
                if not isinstance(row, dict):
                    continue
                event = str(row.get("event", "")).strip()
                if event:
                    events.setdefault(event, set()).add(str(path))
    return events


def discover_material_events(roots: list[Path]) -> dict[str, set[str]]:
    events: dict[str, set[str]] = {}
    for root in roots:
        if not root.exists():
            continue
        paths = (
            [root]
            if root.name == "material_collection_manifest.json"
            else root.rglob("material_collection_manifest.json")
        )
        for path in paths:
            if not path.is_file():
                continue
            payload = read_json(path)
            for key in ("sources", "audible_event_sources"):
                for row in payload.get(key, []):
                    if not isinstance(row, dict):
                        continue
                    event = str(row.get("event", "")).strip()
                    if event:
                        events.setdefault(event, set()).add(str(path))
    return events


def has_term(values: list[str], terms: tuple[str, ...]) -> bool:
    joined = "\n".join(values)
    return any(term in joined for term in terms)


def is_role_voice_audio(row: dict[str, Any], subtitle_voice_requests: set[str]) -> bool:
    request_id = str(row.get("request_id", "")).strip()
    if request_id and request_id in subtitle_voice_requests:
        return True
    code_name = str(row.get("code_name", "")).strip()
    parts = [part.casefold() for part in code_name.split("_")]
    if any(part in ROLE_VOICE_SPEAKER_TOKENS for part in parts[1:-1]):
        return True
    return str(row.get("source", "")) in VOICE_SOURCES and str(
        row.get("code_name", "")
    ).startswith("3")


def semantic_lane(
    *,
    role_voice_count: int,
    gameplay_marker: bool,
    short_variant: bool,
    audience_excluded: bool,
    audio_count: int,
) -> str:
    if gameplay_marker and role_voice_count:
        return "audible_gameplay_result_with_role_voice"
    if gameplay_marker:
        return "pure_gameplay_or_effect_material"
    if audience_excluded and role_voice_count:
        return "audible_excluded_component_with_role_voice"
    if audience_excluded:
        return "excluded_material_or_component"
    if role_voice_count and short_variant:
        return "blocked_short_role_voice_variant"
    if role_voice_count:
        return "normal_animation_candidate_needs_visual_speech_review"
    if audio_count:
        return "non_dialogue_audio_or_effect_component"
    return "silent_or_video_only_material_candidate"


def event_prefix(event: str) -> str:
    return event.split("_", 1)[0]


def event_sort_key(event: str) -> tuple:
    return tuple(
        int(token) if token.isdigit() else token.casefold()
        for token in re.split(r"(\d+)", event)
    )


def summarize_manifest(
    event: str,
    manifest: dict[str, Any],
    render_paths: set[str],
    series_paths: set[str],
    material_paths: set[str],
    invalidated_roots: set[str],
) -> dict[str, Any]:
    audio = [row for row in manifest.get("audio", []) if isinstance(row, dict)]
    subtitles = [row for row in manifest.get("subtitles", []) if isinstance(row, dict)]
    clips = [row for row in manifest.get("clips", []) if isinstance(row, dict)]
    gates = manifest.get("quality_gates", {})

    audio_names = [str(row.get("code_name", "")) for row in audio]
    clip_names = [str(row.get("dgm_name", "")) for row in clips]
    subtitle_sources = [str(row.get("subtitle_source", "")) for row in subtitles]
    subtitle_texts = [str(row.get("text", "")) for row in subtitles]
    subtitle_voice_requests = {
        str(row.get("voice_request_id", "")).strip()
        for row in subtitles
        if str(row.get("voice_request_id", "")).strip()
    }

    role_voice_rows = [
        row for row in audio if is_role_voice_audio(row, subtitle_voice_requests)
    ]
    role_voice_count = len(role_voice_rows)
    non_dialogue_audio_count = len(audio) - role_voice_count
    base_audio_count = sum(str(row.get("source", "")) == "event_audio_component" for row in audio)
    bgm_request_count = sum(has_term([str(row.get("code_name", ""))], BGM_TERMS) for row in audio)
    asr_subtitle_count = sum(
        any(source_term in source for source_term in ASR_SOURCES)
        for source in subtitle_sources
    )
    runtime_capture_subtitle_count = sum(
        source == "official_runtime_capture" for source in subtitle_sources
    )
    official_label_count = sum(
        source in {"official_voice_label", "official_runtime_capture"}
        for source in subtitle_sources
    )
    gameplay_marker = has_term(audio_names + clip_names, GAMEPLAY_TERMS)
    short_variant = int(manifest.get("render_duration_ms") or 0) <= 3000
    audience_excluded = bool(manifest.get("audience_exclusion_reason"))
    lane = semantic_lane(
        role_voice_count=role_voice_count,
        gameplay_marker=gameplay_marker,
        short_variant=short_variant,
        audience_excluded=audience_excluded,
        audio_count=len(audio),
    )
    invalidated_paths = sorted(
        path
        for path in set(render_paths) | set(series_paths) | set(material_paths)
        if any(is_under(path, root) for root in invalidated_roots)
    )
    invalidated = bool(invalidated_paths)

    risk_flags: list[str] = []
    if invalidated:
        risk_flags.append("invalidated_output_root")
    if official_label_count and not asr_subtitle_count:
        risk_flags.append("subtitle_from_voice_label_only")
    if role_voice_count and not any(
        "runtime_capture" in str(row.get("evidence", "")) for row in role_voice_rows
    ):
        risk_flags.append("role_voice_timing_without_full_av_capture")
    if role_voice_count:
        risk_flags.append("role_voice_visual_speech_unverified")
    if gameplay_marker and role_voice_count:
        risk_flags.append("gameplay_or_result_with_role_voice")
    elif gameplay_marker:
        risk_flags.append("gameplay_or_result_material")
    if short_variant and role_voice_count:
        risk_flags.append("short_variant_with_role_voice")
    if gates.get("ready") and risk_flags:
        risk_flags.append("technical_ready_not_delivery_ready")

    if invalidated:
        delivery_status = "invalidated_do_not_use"
    elif risk_flags:
        delivery_status = "blocked_pending_runtime_av_verification"
    else:
        delivery_status = "no_av_trust_flags_detected"

    return {
        "event": event,
        "series": event_prefix(event),
        "delivery_status": delivery_status,
        "semantic_lane": lane,
        "risk_flags": ";".join(risk_flags),
        "ready": "yes" if gates.get("ready") else "no",
        "audience_excluded": "yes" if audience_excluded else "no",
        "render_duration_ms": manifest.get("render_duration_ms", ""),
        "video_composition_model": manifest.get("video_composition_model", ""),
        "clip_count": len(clips),
        "base_audio_count": base_audio_count,
        "role_voice_count": role_voice_count,
        "non_dialogue_audio_count": non_dialogue_audio_count,
        "bgm_request_count": bgm_request_count,
        "subtitle_count": len(subtitles),
        "official_voice_label_subtitle_count": official_label_count,
        "runtime_capture_subtitle_count": runtime_capture_subtitle_count,
        "asr_or_override_subtitle_count": asr_subtitle_count,
        "gameplay_marker": "yes" if gameplay_marker else "no",
        "audio_names": " | ".join(audio_names),
        "subtitle_texts": " | ".join(subtitle_texts),
        "clip_names": " | ".join(clip_names),
        "render_paths": "|".join(sorted(render_paths)),
        "series_paths": "|".join(sorted(series_paths)),
        "material_paths": "|".join(sorted(material_paths)),
        "invalidated_paths": "|".join(invalidated_paths),
        "production_manifest": str(manifest.get("_path", "")),
    }


def write_markdown(path: Path, rows: list[dict[str, Any]], invalidated: list[dict[str, str]]) -> None:
    counts = Counter(row["delivery_status"] for row in rows)
    lane_counts = Counter(row["semantic_lane"] for row in rows)
    risk_counts: Counter[str] = Counter()
    for row in rows:
        for flag in str(row["risk_flags"]).split(";"):
            if flag:
                risk_counts[flag] += 1
    lines = [
        "# Runtime audiovisual trust audit",
        "",
        "This report audits whether outputs are suitable for final delivery, not just whether they have decodable streams.",
        "",
        "## Status counts",
        "",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Semantic lanes", ""])
    for key, value in sorted(lane_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Risk flags", ""])
    for key, value in risk_counts.most_common():
        lines.append(f"- `{key}`: {value}")
    if invalidated:
        lines.extend(["", "## Invalidated output roots", ""])
        for row in invalidated:
            lines.append(f"- `{row['path']}` - {row['reason']}")
    lines.extend(["", "## Audited events", ""])
    for row in rows:
        lines.append(
            f"- `{row['event']}`: {row['delivery_status']} / "
            f"{row['semantic_lane']} "
            f"({row['risk_flags'] or 'no flags'})"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    invalidated_entries, invalidated_roots = load_invalidated(
        [Path(path) for path in args.invalidated_output_roots]
    )
    render_events = discover_render_events([Path(path) for path in args.render_root])
    series_events = discover_series_events([Path(path) for path in args.series_root])
    material_events = discover_material_events([Path(path) for path in args.material_root])

    requested = set(args.event)
    requested.update(render_events)
    requested.update(series_events)
    requested.update(material_events)

    production_dir = manifest_dir(Path(args.production_manifest_root))
    manifests: dict[str, dict[str, Any]] = {}
    for path in production_dir.glob("*.json"):
        payload = read_json(path)
        event = str(payload.get("event", "")).strip()
        if event:
            payload["_path"] = str(path)
            manifests[event] = payload

    rows: list[dict[str, Any]] = []
    for event in sorted(requested, key=event_sort_key):
        manifest = manifests.get(event)
        if not manifest:
            continue
        rows.append(
            summarize_manifest(
                event,
                manifest,
                render_events.get(event, set()),
                series_events.get(event, set()),
                material_events.get(event, set()),
                invalidated_roots,
            )
        )

    fields = [
        "event",
        "series",
        "delivery_status",
        "semantic_lane",
        "risk_flags",
        "ready",
        "audience_excluded",
        "render_duration_ms",
        "video_composition_model",
        "clip_count",
        "base_audio_count",
        "role_voice_count",
        "non_dialogue_audio_count",
        "bgm_request_count",
        "subtitle_count",
        "official_voice_label_subtitle_count",
        "runtime_capture_subtitle_count",
        "asr_or_override_subtitle_count",
        "gameplay_marker",
        "audio_names",
        "subtitle_texts",
        "clip_names",
        "render_paths",
        "series_paths",
        "material_paths",
        "invalidated_paths",
        "production_manifest",
    ]
    csv_path = out_dir / "runtime_av_trust_audit.csv"
    write_csv(csv_path, rows, fields)
    summary = {
        "audited_events": len(rows),
        "status_counts": dict(Counter(row["delivery_status"] for row in rows)),
        "semantic_lane_counts": dict(Counter(row["semantic_lane"] for row in rows)),
        "invalidated_output_root_count": len(invalidated_entries),
        "csv": str(csv_path),
        "report": str(out_dir / "runtime_av_trust_audit.md"),
    }
    (out_dir / "runtime_av_trust_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(out_dir / "runtime_av_trust_audit.md", rows, invalidated_entries)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
