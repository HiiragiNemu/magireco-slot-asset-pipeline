#!/usr/bin/env python3
"""Create per-event production manifests from verified static evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

try:
    from .output_path_contract import (
        resolve_output_child,
        validate_output_identifier,
    )
except ImportError:  # direct script execution
    from output_path_contract import (  # type: ignore
        resolve_output_child,
        validate_output_identifier,
    )


JAPANESE_TEXT_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u9fff！？…？]"
)
VOICE_SPEAKER_TOKENS = {
    "ai",
    "ari",
    "bur",
    "etc",
    "fel",
    "fer",
    "hom",
    "iro",
    "kae",
    "kan",
    "kuro",
    "kuroe",
    "kyk",
    "kyo",
    "mad",
    "mam",
    "mami",
    "mamik",
    "mif",
    "mihu",
    "mit",
    "mita",
    "mobd",
    "mom",
    "nag",
    "nem",
    "nemu",
    "qb",
    "ren",
    "rena",
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
    "uwa",
    "ui",
    "yac",
    "yach",
}
GRAPHICAL_SUBTITLE_CONFIDENCE = {
    "exact_gdb_frame_and_official_ogg",
    "exact_gdb_frame_only",
}
RUNTIME_MANIFEST_LOADER_PROVENANCE_FIELDS = {
    "_source_path",
    "_source_paths",
    "_source_provenance",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-catalog", required=True)
    parser.add_argument("--event-clips", required=True)
    parser.add_argument("--audio-components", required=True)
    parser.add_argument(
        "--event-sounds",
        required=True,
        help="exact GDB child-frame plus Z2D reqSound callback timeline",
    )
    parser.add_argument(
        "--subtitle-timeline",
        required=True,
        help="verified graphical display text timeline",
    )
    parser.add_argument(
        "--composition-plans",
        default=str(Path(__file__).with_name("composition_plans")),
        help="directory containing explicitly verified per-event composition plans",
    )
    parser.add_argument(
        "--audience-exclusions",
        default=str(Path(__file__).with_name("audience_exclusions.json")),
        help="explicitly reviewed events that are components, not standalone videos",
    )
    parser.add_argument(
        "--voice-subtitle-overrides",
        action="append",
        default=[],
        help="accepted full dialogue recovered for truncated official labels",
    )
    parser.add_argument(
        "--runtime-event-manifests",
        action="append",
        default=[],
        help="directories or event_manifest.json files resolved from official runtime captures",
    )
    parser.add_argument(
        "--reviewed-subtitle-manifests",
        action="append",
        default=[],
        help=(
            "prior event-production roots or JSON files whose reviewed subtitle "
            "identity/text is authoritative; current evidence timing is retained"
        ),
    )
    parser.add_argument(
        "--ogg-search-root",
        action="append",
        default=[],
        help="optional directory containing official decoded OGG files",
    )
    parser.add_argument(
        "--path-prefix-map",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help=(
            "repeatable explicit relocation for paths embedded in backed-up "
            "CSV/JSON evidence; source files are never rewritten"
        ),
    )
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def parse_path_prefix_maps(values: list[str]) -> list[tuple[str, str]]:
    mappings: list[tuple[str, str]] = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"path prefix map must be OLD=NEW: {value!r}")
        old, new = (part.strip() for part in value.split("=", 1))
        old = old.rstrip("\\/")
        new = new.rstrip("\\/")
        if not old or not new:
            raise ValueError(f"path prefix map has a blank endpoint: {value!r}")
        mappings.append((old, new))
    return mappings


def apply_path_prefix_maps(value, mappings: list[tuple[str, str]]):
    """Relocate embedded evidence paths without mutating their source files."""

    if isinstance(value, dict):
        return {
            key: apply_path_prefix_maps(item, mappings)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [apply_path_prefix_maps(item, mappings) for item in value]
    if not isinstance(value, str):
        return value
    normalized_value = value.replace("\\", "/")
    for old, new in mappings:
        normalized_old = old.replace("\\", "/")
        folded_value = normalized_value.casefold()
        folded_old = normalized_old.casefold()
        if folded_value != folded_old and not folded_value.startswith(
            folded_old + "/"
        ):
            continue
        relative = normalized_value[len(normalized_old) :].lstrip("/")
        separator = "\\" if "\\" in new or re.match(r"^[A-Za-z]:", new) else "/"
        relative = relative.replace("/", separator)
        return new if not relative else new + separator + relative
    return value


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def quantize_duration_to_frame_grid(
    content_end_ms: int, frame_rate: str
) -> dict[str, int | str]:
    """Extend, never trim, an integer-ms content tail to a whole video frame.

    Event/audio/subtitle evidence is recorded in milliseconds, while a CFR
    video can end only on a rational frame boundary.  Keeping the unquantized
    value as the MP4 target creates false duration failures (for example,
    13027 ms at 30 fps is necessarily 391 frames, or 13033.333... ms).
    """

    if content_end_ms <= 0:
        raise ValueError("content_end_ms must be positive")
    try:
        numerator_text, denominator_text = str(frame_rate).split("/", 1)
        rate = Fraction(int(numerator_text), int(denominator_text))
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise ValueError(f"invalid rational frame rate: {frame_rate!r}") from error
    if rate <= 0:
        raise ValueError(f"invalid non-positive frame rate: {frame_rate!r}")
    frame_position = Fraction(content_end_ms, 1000) * rate
    frame_count = math.ceil(frame_position)
    exact_duration_ms = Fraction(frame_count * 1000, 1) / rate
    audio_sample_count = math.ceil(Fraction(frame_count * 48000, 1) / rate)
    rounded_duration_ms = max(content_end_ms, int(round(exact_duration_ms)))
    return {
        "policy": "ceil_content_tail_to_complete_cfr_frame",
        "frame_rate": f"{rate.numerator}/{rate.denominator}",
        "frame_count": frame_count,
        "content_end_ms": content_end_ms,
        "duration_ms": rounded_duration_ms,
        "exact_duration_ms_numerator": exact_duration_ms.numerator,
        "exact_duration_ms_denominator": exact_duration_ms.denominator,
        "audio_sample_rate": 48000,
        "audio_sample_count": audio_sample_count,
        "padding_ms": rounded_duration_ms - content_end_ms,
    }


def load_composition_plans(path: Path) -> dict[str, dict]:
    if not path.is_dir():
        return {}
    plans: dict[str, dict] = {}
    for plan_path in sorted(path.glob("*.json")):
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        event = str(plan.get("event", "")).strip()
        if not event:
            raise ValueError(f"composition plan has no event: {plan_path}")
        event = validate_output_identifier(
            event, label=f"composition plan event in {plan_path}"
        )
        if event in plans:
            raise ValueError(f"duplicate composition plan for {event}")
        plan["_source_path"] = str(plan_path.resolve())
        plans[event] = plan
    return plans


def load_audience_exclusions(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events", {})
    if not isinstance(events, dict):
        raise ValueError(f"audience exclusions must contain an events object: {path}")
    return {
        str(event).strip(): str(reason).strip()
        for event, reason in events.items()
        if str(event).strip() and str(reason).strip()
    }


def load_voice_subtitle_overrides(paths: list[Path]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"voice subtitle overrides not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        accepted = payload.get("accepted", {})
        if not isinstance(accepted, dict):
            raise ValueError(
                f"voice subtitle overrides have no accepted object: {path}"
            )
        for request_id, row in accepted.items():
            has_text = isinstance(row, dict) and bool(
                str(row.get("text", "")).strip()
            )
            has_cues = isinstance(row, dict) and any(
                isinstance(cue, dict) and str(cue.get("text", "")).strip()
                for cue in row.get("cues", [])
            )
            if has_text or has_cues:
                merged[str(request_id)] = row
    return merged


def load_runtime_event_manifests(paths: list[Path]) -> dict[str, dict]:
    manifests: dict[str, dict] = {}
    for path in paths:
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(path.rglob("event_manifest.json"))
        else:
            raise FileNotFoundError(f"runtime event manifest path not found: {path}")
        for candidate in candidates:
            candidate_bytes = candidate.read_bytes()
            payload = json.loads(candidate_bytes.decode("utf-8"))
            event = str(payload.get("event", "")).strip()
            if not event:
                raise ValueError(f"runtime event manifest has no event: {candidate}")
            event = validate_output_identifier(
                event, label=f"runtime event manifest event in {candidate}"
            )
            content = {
                key: value
                for key, value in payload.items()
                if key not in RUNTIME_MANIFEST_LOADER_PROVENANCE_FIELDS
            }
            source = {
                "path": str(candidate.resolve()),
                "sha256": hashlib.sha256(candidate_bytes).hexdigest().upper(),
            }
            if event in manifests:
                existing = manifests[event]
                existing_content = {
                    key: value
                    for key, value in existing.items()
                    if key not in RUNTIME_MANIFEST_LOADER_PROVENANCE_FIELDS
                }
                if existing_content != content:
                    existing_paths = existing.get("_source_paths", [])
                    raise ValueError(
                        f"conflicting runtime event manifests for {event}: "
                        f"{', '.join([*existing_paths, source['path']])}"
                    )
                if source["path"] not in existing.get("_source_paths", []):
                    existing["_source_paths"].append(source["path"])
                    existing["_source_provenance"].append(source)
                continue

            content["_source_path"] = source["path"]
            content["_source_paths"] = [source["path"]]
            content["_source_provenance"] = [source]
            manifests[event] = content
    return manifests


def load_reviewed_subtitle_manifests(paths: list[Path]) -> dict[str, dict]:
    """Load a hash-bound, conflict-intolerant reviewed subtitle baseline."""

    manifests: dict[str, dict] = {}
    for path in paths:
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            event_dir = path / "events"
            candidates = sorted(
                (event_dir if event_dir.is_dir() else path).glob("*.json")
            )
        else:
            raise FileNotFoundError(
                f"reviewed subtitle manifest path not found: {path}"
            )
        for candidate in candidates:
            candidate_bytes = candidate.read_bytes()
            payload = json.loads(candidate_bytes.decode("utf-8"))
            event = str(payload.get("event", "")).strip()
            if not event:
                raise ValueError(
                    f"reviewed subtitle manifest has no event: {candidate}"
                )
            event = validate_output_identifier(
                event, label=f"reviewed subtitle manifest event in {candidate}"
            )
            quality_gates = payload.get("quality_gates")
            quality_ready = (
                isinstance(quality_gates, dict)
                and quality_gates.get("ready") is True
            )
            subtitles = payload.get("subtitles")
            if not isinstance(subtitles, list) or any(
                not isinstance(row, dict) for row in subtitles
            ):
                raise ValueError(
                    f"reviewed subtitle manifest has invalid subtitles: {candidate}"
                )
            source = {
                "path": str(candidate.resolve()),
                "sha256": hashlib.sha256(candidate_bytes).hexdigest().upper(),
            }
            if event in manifests:
                existing = manifests[event]
                if (
                    existing["subtitles"] != subtitles
                    or existing["_quality_ready"] != quality_ready
                ):
                    existing_paths = [
                        row["path"]
                        for row in existing.get("_source_provenance", [])
                    ]
                    raise ValueError(
                        f"conflicting reviewed subtitle manifests for {event}: "
                        f"{', '.join([*existing_paths, source['path']])}"
                    )
                if source not in existing["_source_provenance"]:
                    existing["_source_provenance"].append(source)
                continue
            manifests[event] = {
                "event": event,
                "subtitles": subtitles,
                "_quality_ready": quality_ready,
                "_source_provenance": [source],
            }
    return manifests


def reconcile_reviewed_subtitle_rows(
    event: str,
    current_rows: list[dict],
    audio_rows: list[dict],
    reviewed_manifest: dict,
    accepted_current_voice_overrides: Mapping[str, dict] | None = None,
) -> tuple[list[dict], dict]:
    """Carry reviewed dialogue forward without reverting corrected AV timing.

    The reviewed manifest owns cue identity and text.  A matching current cue
    owns start/end timing, so a later timing repair is not discarded.  If a
    reviewed voice cue disappeared from the current subtitle extraction, its
    timing is reconstructed relative to the current hash-bound audio row.
    Current-only subtitle candidates are intentionally excluded pending review,
    except for request IDs supplied by the explicit curated voice-override
    registry.  Those rows are accepted only when their generated text matches
    the registry exactly.
    """

    reviewed_rows = reviewed_manifest.get("subtitles")
    if not isinstance(reviewed_rows, list):
        raise ValueError(f"{event} reviewed subtitle baseline is invalid")

    current_voice: dict[str, list[dict]] = defaultdict(list)
    reviewed_voice: dict[str, list[dict]] = defaultdict(list)
    audio_by_request: dict[str, list[dict]] = defaultdict(list)
    for row in current_rows:
        request_id = str(row.get("voice_request_id", "")).strip()
        if request_id:
            current_voice[request_id].append(row)
    for row in reviewed_rows:
        request_id = str(row.get("voice_request_id", "")).strip()
        if request_id:
            reviewed_voice[request_id].append(row)
    for row in audio_rows:
        request_id = str(row.get("request_id", "")).strip()
        if request_id:
            audio_by_request[request_id].append(row)

    sort_key = lambda row: (
        number(row.get("start_ms", "")),
        number(row.get("end_ms", "")),
        str(row.get("text", "")),
    )
    for rows in current_voice.values():
        rows.sort(key=sort_key)
    for rows in reviewed_voice.values():
        rows.sort(key=sort_key)
    for rows in audio_by_request.values():
        rows.sort(key=lambda row: number(row.get("start_ms", "")))

    output: list[dict] = []
    matched_voice_cues = 0
    carried_voice_cues = 0
    for request_id, prior_rows in sorted(reviewed_voice.items()):
        audio_candidates = audio_by_request.get(request_id, [])
        if not audio_candidates:
            raise ValueError(
                f"{event} reviewed subtitle request {request_id} has no "
                "current verified audio row"
            )
        current_candidates = current_voice.get(request_id, [])
        for index, prior in enumerate(prior_rows):
            current = (
                current_candidates[index]
                if index < len(current_candidates)
                else None
            )
            if current is not None:
                reconciled = dict(current)
                matched_voice_cues += 1
            else:
                audio = audio_candidates[min(index, len(audio_candidates) - 1)]
                audio_start = number(audio.get("start_ms", ""))
                prior_start = number(prior.get("start_ms", ""))
                prior_end = number(prior.get("end_ms", ""))
                prior_voice_start = number(
                    prior.get("voice_start_ms", ""),
                    prior_start,
                )
                start_ms = max(0, audio_start + prior_start - prior_voice_start)
                end_ms = max(
                    start_ms + 500,
                    audio_start + prior_end - prior_voice_start,
                )
                reconciled = {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "voice_request_id": request_id,
                    "voice_start_ms": audio_start,
                    "z2d_name": str(
                        audio.get("z2d_name", prior.get("z2d_name", ""))
                    ),
                }
                carried_voice_cues += 1
            reconciled.update(
                {
                    "text": str(prior.get("text", "")).strip(),
                    "voice_request_id": request_id,
                    "speaker_code": str(prior.get("speaker_code", "")).strip(),
                    "subtitle_source": str(
                        prior.get("subtitle_source", "")
                    ).strip(),
                    "evidence": str(prior.get("evidence", "")).strip(),
                }
            )
            if not reconciled["text"]:
                raise ValueError(
                    f"{event} reviewed subtitle request {request_id} has blank text"
                )
            output.append(reconciled)

    accepted_current_voice_overrides = accepted_current_voice_overrides or {}
    accepted_current_voice: list[dict] = []
    for request_id in sorted(set(current_voice) - set(reviewed_voice)):
        override = accepted_current_voice_overrides.get(request_id)
        if override is None:
            continue
        current_candidates = current_voice[request_id]
        override_cues = override.get("cues", [])
        if isinstance(override_cues, list) and override_cues:
            expected_texts = [
                str(cue.get("text", "")).strip()
                for cue in override_cues
                if isinstance(cue, dict) and str(cue.get("text", "")).strip()
            ]
        else:
            expected_text = str(override.get("text", "")).strip()
            expected_texts = [expected_text] if expected_text else []
        observed_texts = [
            str(row.get("text", "")).strip() for row in current_candidates
        ]
        if not expected_texts or observed_texts != expected_texts:
            raise ValueError(
                f"{event} curated current-only subtitle request {request_id} "
                "differs from its accepted voice override"
            )
        for row in current_candidates:
            output.append(dict(row))
            accepted_current_voice.append(
                {
                    "voice_request_id": request_id,
                    "text": str(row.get("text", "")).strip(),
                    "subtitle_source": str(
                        row.get("subtitle_source", "")
                    ).strip(),
                }
            )

    reviewed_graphical = [
        dict(row)
        for row in reviewed_rows
        if not str(row.get("voice_request_id", "")).strip()
    ]
    output.extend(reviewed_graphical)
    accepted_request_ids = {
        row["voice_request_id"] for row in accepted_current_voice
    }
    reviewed_request_ids = set(reviewed_voice) | accepted_request_ids
    excluded_current_voice = [
        {
            "voice_request_id": str(row.get("voice_request_id", "")).strip(),
            "text": str(row.get("text", "")).strip(),
            "subtitle_source": str(row.get("subtitle_source", "")).strip(),
        }
        for row in current_rows
        if str(row.get("voice_request_id", "")).strip()
        and str(row.get("voice_request_id", "")).strip()
        not in reviewed_request_ids
    ]
    excluded_current_graphical = [
        {
            "text": str(row.get("text", "")).strip(),
            "subtitle_source": str(row.get("subtitle_source", "")).strip(),
        }
        for row in current_rows
        if not str(row.get("voice_request_id", "")).strip()
        and row not in reviewed_graphical
    ]
    audit = {
        "policy": (
            "reviewed_identity_and_text_with_current_timing;"
            "reviewed_missing_voice_reconstructed_from_current_audio;"
            "curated_voice_overrides_expand_reviewed_baseline;"
            "other_current_only_candidates_excluded"
        ),
        "source_provenance": reviewed_manifest.get("_source_provenance", []),
        "reviewed_cue_count": len(reviewed_rows),
        "matched_voice_cue_count": matched_voice_cues,
        "carried_voice_cue_count": carried_voice_cues,
        "reviewed_graphical_cue_count": len(reviewed_graphical),
        "accepted_current_voice_override_candidates": accepted_current_voice,
        "excluded_current_voice_candidates": excluded_current_voice,
        "excluded_current_graphical_candidates": excluded_current_graphical,
    }
    return output, audit


def probe_runtime_video(path: Path, ffprobe: str, cache: dict[str, dict]) -> dict:
    resolved = str(path.resolve())
    if resolved in cache:
        return cache[resolved]
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(result.stdout)
    video = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "video"
    )
    probed = {
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "frame_rate": str(video.get("r_frame_rate", "")),
        "duration_ms": round(float(payload["format"]["duration"]) * 1000),
    }
    cache[resolved] = probed
    return probed


def infer_ogg_search_roots(
    event_sounds: list[dict[str, str]],
    subtitle_timeline: list[dict[str, str]],
    runtime_event_manifests: dict[str, dict],
    explicit_roots: list[Path],
) -> list[Path]:
    candidates: list[Path] = []
    for path in explicit_roots:
        if path.is_dir():
            candidates.append(path.resolve())
    for row in event_sounds:
        ogg_path = str(row.get("ogg_path", "")).strip()
        if ogg_path:
            path = Path(ogg_path)
            if path.is_file():
                candidates.append(path.parent.resolve())
    for row in subtitle_timeline:
        ogg_path = str(row.get("ogg_path", "")).strip()
        if ogg_path:
            path = Path(ogg_path)
            if path.is_file():
                candidates.append(path.parent.resolve())
    for manifest in runtime_event_manifests.values():
        for row in manifest.get("sound_assets", []):
            ogg_path = str(row.get("ogg_path", "")).strip()
            if ogg_path:
                path = Path(ogg_path)
                if path.is_file():
                    candidates.append(path.parent.resolve())
    roots: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def resolve_ogg_path(
    ogg_name: str,
    raw_path: str,
    search_roots: list[Path],
    cache: dict[str, str],
) -> str:
    path = str(raw_path or "").strip()
    if path and Path(path).is_file():
        return str(Path(path).resolve())
    name = str(ogg_name or "").strip()
    if not name:
        return ""
    if name in cache:
        return cache[name]
    for root in search_roots:
        candidate = root / name
        if candidate.is_file():
            cache[name] = str(candidate.resolve())
            return cache[name]
    cache[name] = ""
    return ""


def normalize_runtime_subtitles(rows: list[dict]) -> list[dict]:
    merged: list[dict] = []
    ordered = sorted(
        rows,
        key=lambda row: (
            number(row.get("start_ms", "")),
            number(row.get("end_ms", "")),
            str(row.get("text", "")),
        ),
    )
    for row in ordered:
        candidate = {
            "text": str(row.get("text", "")).replace("\\n", "\n"),
            "start_ms": number(row.get("start_ms", "")),
            "end_ms": number(row.get("end_ms", "")),
            "voice_start_ms": number(row.get("voice_start_ms", "")),
            "voice_code_name": str(row.get("voice_code_name", "")),
            "ogg_path": str(row.get("ogg_path", "")),
            "mapping_basis": str(row.get("mapping_basis", "")),
        }
        if (
            merged
            and candidate["text"] == merged[-1]["text"]
            and candidate["start_ms"] <= merged[-1]["end_ms"] + 150
        ):
            merged[-1]["end_ms"] = max(merged[-1]["end_ms"], candidate["end_ms"])
            if candidate["voice_code_name"]:
                merged[-1]["voice_code_name"] = ";".join(
                    filter(
                        None,
                        [
                            merged[-1]["voice_code_name"],
                            candidate["voice_code_name"],
                        ],
                    )
                )
            merged[-1]["mapping_basis"] = "runtime_text_merged_adjacent_voice"
            continue
        merged.append(candidate)
    return merged


def runtime_render_duration_ms(runtime_manifest: dict, composition_plan: dict) -> int:
    duration_ms = number(composition_plan.get("duration_ms", ""))
    for row in runtime_manifest.get("sound_assets", []):
        duration_ms = max(
            duration_ms,
            number(row.get("relative_ms", "")) + number(row.get("duration_ms", "")),
        )
    for row in runtime_manifest.get("subtitles", []):
        duration_ms = max(duration_ms, number(row.get("end_ms", "")))
    return duration_ms


def synthesize_runtime_event_clips(
    runtime_manifest: dict,
    composition_plan: dict,
    ffprobe: str,
    media_cache: dict[str, dict],
) -> list[dict[str, str]]:
    runtime_assets = {
        str(row.get("official_name", "")): row
        for row in runtime_manifest.get("video_assets", [])
        if str(row.get("official_name", ""))
    }
    plan_rows = composition_plan.get("clips", [])
    if not plan_rows:
        return []
    linear_clean_plan = (
        composition_plan.get("model") == "linear_full_frame_sequence"
    )
    video_duration_ms = number(composition_plan.get("duration_ms", ""))
    plan_native_dimensions = composition_plan.get("native_dimensions", {})
    plan_native_size = (
        number(plan_native_dimensions.get("width", "")),
        number(plan_native_dimensions.get("height", "")),
    )
    backgrounds = sorted(
        [row for row in plan_rows if row.get("role") == "background"],
        key=lambda row: number(row.get("start_ms", "")),
    )
    loop_backgrounds = [
        row for row in plan_rows if row.get("role") == "loop_background"
    ]
    next_background_start: dict[str, int] = {}
    boundaries = [
        *(number(row.get("start_ms", "")) for row in backgrounds[1:]),
        *(
            [number(loop_backgrounds[0].get("start_ms", ""))]
            if loop_backgrounds
            else [video_duration_ms]
        ),
    ]
    for row, end_ms in zip(backgrounds, boundaries):
        next_background_start[str(row.get("dgm_name", ""))] = end_ms
    if loop_backgrounds:
        next_background_start[
            str(loop_backgrounds[0].get("dgm_name", ""))
        ] = video_duration_ms

    synthesized: list[dict[str, str]] = []
    for index, row in enumerate(plan_rows):
        dgm_name = str(row.get("dgm_name", ""))
        asset = runtime_assets.get(dgm_name, {})
        clip_path = str(asset.get("target_mp4") or asset.get("source_mp4") or "")
        probe = (
            probe_runtime_video(Path(clip_path), ffprobe, media_cache)
            if clip_path
            else {
                "width": 0,
                "height": 0,
                "frame_rate": "",
                "duration_ms": 0,
            }
        )
        role = str(row.get("role", ""))
        start_ms = number(row.get("start_ms", ""))
        if linear_clean_plan and role == "background":
            end_ms = start_ms + probe["duration_ms"]
        elif role in {"background", "loop_background"}:
            end_ms = next_background_start.get(dgm_name, start_ms + probe["duration_ms"])
        elif role == "screen_overlay":
            end_ms = start_ms + probe["duration_ms"]
        elif role == "loop_screen_overlay":
            end_ms = video_duration_ms
        else:
            end_ms = start_ms + probe["duration_ms"]
        if not linear_clean_plan:
            end_ms = min(end_ms, video_duration_ms)
        synthesized.append(
            {
                "event_name": str(runtime_manifest.get("event", "")),
                "dgm_name": dgm_name,
                "dgm_role": role,
                "width": str(probe["width"]),
                "height": str(probe["height"]),
                "frame_rate": probe["frame_rate"],
                "event_start_ms": str(start_ms),
                "event_end_ms": str(end_ms),
                "interval_confidence": "runtime_verified_composition_plan",
                "media_class": (
                    "full_frame_landscape"
                    if (probe["width"], probe["height"])
                    in {(416, 232), plan_native_size}
                    else "other_component"
                ),
                "source_mp4": str(asset.get("source_mp4", "")),
                "target_mp4": str(asset.get("target_mp4", "")),
                "z2d_order": str(index),
                "dgm_order": str(index),
            }
        )
    return synthesized


def source_clip_duration_ms(row: dict[str, str]) -> int:
    duration_sec = row.get("media_duration_sec", "")
    if duration_sec:
        return round(float(duration_sec) * 1000)
    return max(
        0,
        number(row.get("event_end_ms", "")) - number(row.get("event_start_ms", "")),
    )


def composition_plan_authored_duration_ms(composition_plan: dict | None) -> int:
    """Return the evidence-bound duration floor authored by a plan."""

    if not composition_plan:
        return 0
    event = str(composition_plan.get("event", "<unknown>"))
    duration_ms = number(composition_plan.get("duration_ms", ""))
    if duration_ms <= 0:
        raise ValueError(
            f"composition plan {event} has no positive authored duration_ms"
        )
    if not str(composition_plan.get("evidence", "")).strip():
        raise ValueError(f"composition plan {event} has no evidence statement")
    return duration_ms


def production_content_end_ms(
    video_duration_ms: int,
    evidence_timeline_end_ms: int,
    composition_plan: dict | None,
) -> int:
    """Keep both the authored duration floor and every proven AV tail.

    A plan duration is a lower bound for the clean presentation, not a license
    to truncate a later verified voice, SE, or subtitle.  Conversely, a short
    encoded visual may intentionally be extended by a plan's hold/loop/black
    policy even when its currently indexed audio ends a few milliseconds early.
    """

    return max(
        video_duration_ms,
        evidence_timeline_end_ms,
        composition_plan_authored_duration_ms(composition_plan),
    )


def composition_plan_uses_authored_timing(composition_plan: dict) -> bool:
    """Return whether static clips must use the plan's authored intervals.

    ``timed_full_frame_layers`` is itself an explicit timing contract.  Falling
    back to source-media intervals for that model can incorrectly append an LP
    source at its full encoded duration, even when the verified plan ends part
    way through the loop.  Legacy plan models retain their opt-in
    ``use_plan_timing`` behaviour.

    Timed plans fail closed unless the authored duration, evidence statement,
    and every clip start are present and internally bounded.  This keeps the
    duration preference tied to a reviewed composition plan rather than to a
    filename or source-media heuristic.
    """

    if composition_plan.get("model") != "timed_full_frame_layers":
        return bool(composition_plan.get("use_plan_timing"))

    event = str(composition_plan.get("event", "<unknown>"))
    duration_ms = composition_plan_authored_duration_ms(composition_plan)

    plan_rows = composition_plan.get("clips", [])
    if not isinstance(plan_rows, list) or not plan_rows:
        raise ValueError(f"timed composition plan {event} has no clips")
    for index, row in enumerate(plan_rows):
        if not isinstance(row, dict) or "start_ms" not in row:
            raise ValueError(
                f"timed composition plan {event} clip {index} has no start_ms"
            )
        start_ms = number(row.get("start_ms", ""), -1)
        if start_ms < 0 or start_ms > duration_ms:
            raise ValueError(
                f"timed composition plan {event} clip {index} start_ms "
                f"{start_ms} is outside 0..{duration_ms}"
            )
    return True


def synthesize_static_event_clips_from_plan(
    all_event_clips: list[dict[str, str]],
    composition_plan: dict,
) -> list[dict[str, str]]:
    source_by_name: dict[str, dict[str, str]] = {}
    for row in all_event_clips:
        source_by_name.setdefault(str(row.get("dgm_name", "")), row)

    plan_rows = composition_plan.get("clips", [])
    if not plan_rows:
        return []

    linear_clean_plan = (
        composition_plan.get("model") == "linear_full_frame_sequence"
    )
    video_duration_ms = number(composition_plan.get("duration_ms", ""))
    backgrounds = sorted(
        [row for row in plan_rows if row.get("role") == "background"],
        key=lambda row: number(row.get("start_ms", "")),
    )
    loop_backgrounds = [
        row for row in plan_rows if row.get("role") == "loop_background"
    ]
    next_background_start: dict[str, int] = {}
    boundaries = [
        *(number(row.get("start_ms", "")) for row in backgrounds[1:]),
        *(
            [number(loop_backgrounds[0].get("start_ms", ""))]
            if loop_backgrounds
            else [video_duration_ms]
        ),
    ]
    for row, end_ms in zip(backgrounds, boundaries):
        next_background_start[str(row.get("dgm_name", ""))] = end_ms
    if loop_backgrounds:
        next_background_start[
            str(loop_backgrounds[0].get("dgm_name", ""))
        ] = video_duration_ms

    synthesized: list[dict[str, str]] = []
    for index, plan_row in enumerate(plan_rows):
        dgm_name = str(plan_row.get("dgm_name", ""))
        source = source_by_name.get(dgm_name, {})
        role = str(plan_row.get("role", ""))
        start_ms = number(plan_row.get("start_ms", ""))
        source_duration = source_clip_duration_ms(source)
        if linear_clean_plan and role == "background":
            end_ms = start_ms + source_duration
        elif role in {"background", "loop_background"}:
            end_ms = next_background_start.get(dgm_name, start_ms + source_duration)
        elif role == "screen_overlay":
            end_ms = start_ms + source_duration
        elif role == "loop_screen_overlay":
            end_ms = video_duration_ms
        else:
            end_ms = start_ms + source_duration
        if not linear_clean_plan:
            end_ms = min(end_ms, video_duration_ms)

        row = dict(source)
        row.update(
            {
                "dgm_role": role,
                "event_start_ms": str(start_ms),
                "event_end_ms": str(end_ms),
                "interval_confidence": "static_verified_composition_plan",
                "z2d_order": str(index),
                "dgm_order": str(index),
            }
        )
        synthesized.append(row)
    return synthesized


def synthesize_runtime_audio_rows(
    runtime_manifest: dict,
    static_audio_rows: list[dict[str, str]],
) -> list[dict]:
    static_base_keys = {
        (row.get("leaf_request_id", ""), number(row.get("start_ms", "")))
        for row in static_audio_rows
    }
    audio_rows: list[dict] = []
    for row in sorted(
        runtime_manifest.get("sound_assets", []),
        key=lambda item: (
            number(item.get("relative_ms", "")),
            str(item.get("request_id", "")),
        ),
    ):
        is_actual_play = str(row.get("is_actual_play", "")).strip().lower()
        if is_actual_play and is_actual_play != "yes":
            continue
        if not str(row.get("ogg_path", "")).strip() and not number(
            row.get("duration_ms", "")
        ):
            continue
        request_id = str(row.get("request_id", ""))
        start_ms = number(row.get("relative_ms", ""))
        source = "z2d_req_sound"
        for static_request_id, static_start_ms in static_base_keys:
            if request_id == static_request_id and abs(start_ms - static_start_ms) <= 50:
                source = "event_audio_component"
                break
        audio_rows.append(
            {
                "source": source,
                "request_id": request_id,
                "code_name": str(row.get("code_name", "")),
                "ogg_name": str(row.get("ogg_name", "")),
                "path": str(row.get("ogg_path", "")),
                "start_ms": start_ms,
                "duration_ms": number(row.get("duration_ms", "")),
                "evidence": "official_runtime_capture",
            }
        )
    return audio_rows


def synthesize_runtime_subtitle_rows(runtime_manifest: dict) -> list[dict]:
    subtitle_rows: list[dict] = []
    sound_request_by_code = {
        str(row.get("code_name", "")): str(row.get("request_id", ""))
        for row in runtime_manifest.get("sound_assets", [])
    }
    for row in normalize_runtime_subtitles(runtime_manifest.get("subtitles", [])):
        code_name = str(row.get("voice_code_name", "")).split(";", 1)[0]
        speaker_code, _ = official_voice_label(code_name)
        subtitle_rows.append(
            {
                "text": str(row.get("text", "")),
                "start_ms": number(row.get("start_ms", "")),
                "end_ms": number(row.get("end_ms", "")),
                "voice_request_id": sound_request_by_code.get(code_name, ""),
                "voice_start_ms": number(row.get("voice_start_ms", "")),
                "z2d_name": "",
                "speaker_code": speaker_code,
                "subtitle_source": "official_runtime_capture",
                "evidence": str(row.get("mapping_basis", "official_runtime_capture")),
            }
        )
    return subtitle_rows


def apply_runtime_voice_subtitle_overrides(
    rows: list[dict],
    overrides: dict[str, dict],
) -> list[dict]:
    resolved: list[dict] = []
    for row in rows:
        override = overrides.get(str(row.get("voice_request_id", "")))
        if not override:
            resolved.append(row)
            continue
        source = str(
            override.get("source", "accepted_voice_subtitle_override")
        )
        cues = override.get("cues", [])
        if isinstance(cues, list) and cues:
            voice_start_ms = number(row.get("voice_start_ms", ""))
            for cue in cues:
                if not isinstance(cue, dict):
                    continue
                text = str(cue.get("text", "")).strip()
                if not text:
                    continue
                start_ms = voice_start_ms + max(0, number(cue.get("start_ms", 0)))
                end_ms = voice_start_ms + max(
                    number(cue.get("end_ms", 0)),
                    number(cue.get("start_ms", 0)) + 500,
                )
                resolved.append(
                    {
                        **row,
                        "text": text,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "speaker_code": str(
                            override.get("speaker_code", row.get("speaker_code", ""))
                        ),
                        "subtitle_source": "official_voice_asr_verified",
                        "evidence": source,
                    }
                )
            continue
        text = str(override.get("text", "")).strip()
        if text:
            resolved.append(
                {
                    **row,
                    "text": text,
                    "speaker_code": str(
                        override.get("speaker_code", row.get("speaker_code", ""))
                    ),
                    "subtitle_source": "official_voice_asr_verified",
                    "evidence": source,
                }
            )
        else:
            resolved.append(row)
    return resolved


def is_meaningful_subtitle_text(text: str) -> bool:
    return text.strip() not in {
        "",
        "<空白のテキストレイヤー>",
        "空白のテキストレイヤー",
    }


def graphical_subtitle_row(row: dict) -> dict:
    text = str(row.get("srt_text") or row.get("display_text", ""))
    return {
        "text": text.replace("\\n", "\n"),
        "start_ms": number(row.get("start_ms") or row.get("subtitle_start_ms", "")),
        "end_ms": number(
            row.get("effective_end_ms") or row.get("subtitle_end_ms", "")
        ),
        "voice_request_id": str(row.get("sound_request_id", "")),
        "voice_start_ms": number(
            row.get("audio_start_ms") or row.get("voice_start_ms", "")
        ),
        "z2d_name": str(row.get("z2d_name", "")),
        "speaker_code": "",
        "subtitle_source": "graphical_display_text",
        "evidence": str(row.get("timeline_confidence", "")),
    }


def merge_runtime_graphical_subtitle_rows(
    runtime_rows: list[dict],
    static_rows: list[dict],
) -> list[dict]:
    merged = list(runtime_rows)
    represented = [
        (
            "".join(str(row.get("text", "")).split()),
            number(row.get("start_ms", "")),
            number(row.get("end_ms", "")),
        )
        for row in runtime_rows
    ]
    for source_row in sorted(
        static_rows,
        key=lambda row: (
            number(row.get("start_ms") or row.get("subtitle_start_ms", "")),
            number(row.get("z2d_order", "")),
        ),
        ):
        candidate = graphical_subtitle_row(source_row)
        if not is_meaningful_subtitle_text(candidate["text"]):
            continue
        text_key = "".join(candidate["text"].split())
        candidate_start = number(candidate.get("start_ms", ""))
        candidate_end = number(candidate.get("end_ms", ""))
        if not text_key or any(
            candidate_start <= represented_end
            and candidate_end >= represented_start
            and (
                text_key == represented_key
                or text_key in represented_key
                or represented_key in text_key
            )
            for represented_key, represented_start, represented_end in represented
            if represented_key
        ):
            continue
        merged.append(candidate)
        represented.append((text_key, candidate_start, candidate_end))
    return merged


def official_voice_label(code_name: str) -> tuple[str, str]:
    parts = [part.strip() for part in (code_name or "").split("_")]
    speaker = next(
        (
            part.casefold()
            for part in parts[1:-1]
            if part.casefold() in VOICE_SPEAKER_TOKENS
        ),
        "",
    )
    if not speaker or len(parts) < 3:
        return "", ""
    text = parts[-1].strip()
    if not text or not JAPANESE_TEXT_RE.search(text):
        return "", ""
    return speaker, text


def plan_exclusion_values(composition_plan: dict | None, key: str) -> set[str]:
    if not composition_plan:
        return set()
    values = composition_plan.get(key, [])
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def filter_audio_rows_for_plan(
    audio_rows: list[dict],
    composition_plan: dict | None,
) -> list[dict]:
    request_ids = plan_exclusion_values(
        composition_plan,
        "excluded_audio_request_ids",
    )
    z2d_names = plan_exclusion_values(
        composition_plan,
        "excluded_audio_z2d_names",
    )
    code_names = plan_exclusion_values(
        composition_plan,
        "excluded_audio_code_names",
    )
    if not request_ids and not z2d_names and not code_names:
        return audio_rows
    return [
        row
        for row in audio_rows
        if str(row.get("request_id", "")).strip() not in request_ids
        and str(row.get("z2d_name", "")).strip() not in z2d_names
        and str(row.get("code_name", "")).strip() not in code_names
    ]


def filter_subtitle_rows_for_plan(
    subtitle_rows: list[dict],
    composition_plan: dict | None,
) -> list[dict]:
    graphical_only_z2d_names = plan_exclusion_values(
        composition_plan,
        "graphical_only_subtitle_z2d_names",
    )
    if graphical_only_z2d_names:
        subtitle_rows = [
            {
                **row,
                "voice_request_id": "",
                "voice_start_ms": 0,
                "speaker_code": "",
                "subtitle_source": "graphical_display_text",
                "evidence": (
                    f"{row.get('evidence', '')};"
                    "composition_plan_graphical_only_no_voice_binding"
                ).strip(";"),
            }
            if str(row.get("z2d_name", "")).strip() in graphical_only_z2d_names
            else row
            for row in subtitle_rows
        ]
    request_ids = plan_exclusion_values(
        composition_plan,
        "excluded_audio_request_ids",
    ) | plan_exclusion_values(
        composition_plan,
        "excluded_subtitle_voice_request_ids",
    )
    z2d_names = plan_exclusion_values(
        composition_plan,
        "excluded_audio_z2d_names",
    ) | plan_exclusion_values(
        composition_plan,
        "excluded_subtitle_z2d_names",
    )
    if not request_ids and not z2d_names:
        return subtitle_rows
    return [
        row
        for row in subtitle_rows
        if str(row.get("voice_request_id", "")).strip() not in request_ids
        and str(row.get("z2d_name", "")).strip() not in z2d_names
    ]


def main() -> int:
    args = parse_args()
    try:
        path_prefix_maps = parse_path_prefix_maps(args.path_prefix_map)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    catalog = apply_path_prefix_maps(
        read_csv(Path(args.event_catalog)), path_prefix_maps
    )
    for index, row in enumerate(catalog):
        raw_event = str(row.get("event_name", "")).strip()
        if raw_event:
            row["event_name"] = validate_output_identifier(
                raw_event, label=f"event catalog row {index} event_name"
            )
    clips = apply_path_prefix_maps(
        read_csv(Path(args.event_clips)), path_prefix_maps
    )
    audio_components = apply_path_prefix_maps(
        read_csv(Path(args.audio_components)), path_prefix_maps
    )
    event_sounds = apply_path_prefix_maps(
        read_csv(Path(args.event_sounds)), path_prefix_maps
    )
    subtitle_timeline = apply_path_prefix_maps(
        read_csv(Path(args.subtitle_timeline)), path_prefix_maps
    )
    composition_plans = load_composition_plans(Path(args.composition_plans))
    audience_exclusions = load_audience_exclusions(
        Path(args.audience_exclusions)
    )
    voice_subtitle_overrides = load_voice_subtitle_overrides(
        [Path(path) for path in args.voice_subtitle_overrides]
    )
    runtime_event_manifests = apply_path_prefix_maps(
        load_runtime_event_manifests(
            [Path(path) for path in args.runtime_event_manifests]
        ),
        path_prefix_maps,
    )
    reviewed_subtitle_manifests = apply_path_prefix_maps(
        load_reviewed_subtitle_manifests(
            [Path(path) for path in args.reviewed_subtitle_manifests]
        ),
        path_prefix_maps,
    )
    runtime_media_cache: dict[str, dict] = {}
    ogg_search_roots = infer_ogg_search_roots(
        event_sounds,
        subtitle_timeline,
        runtime_event_manifests,
        [Path(path) for path in args.ogg_search_root],
    )
    ogg_path_cache: dict[str, str] = {}
    clip_sha256_cache: dict[str, str] = {}
    out_dir = Path(args.out_dir).resolve()
    event_dir = resolve_output_child(out_dir, "events", label="events directory")
    event_dir.mkdir(parents=True, exist_ok=True)

    exact_sound_events = {
        row.get("event_name", "")
        for row in event_sounds
        if row.get("ogg_exists") == "yes"
        and row.get("timeline_confidence")
        == "exact_gdb_child_frame_callback_frame_and_official_ogg"
    }
    selected = {
        row["event_name"]: row
        for row in catalog
        if (
            (
                row.get("event_name") in exact_sound_events
                and (
                    (
                        row.get("automatic_candidate") == "yes"
                        and row.get("classification") == "native_full_frame_only"
                    )
                    or row.get("event_name") in composition_plans
                )
            )
            or (
                row.get("event_name") in runtime_event_manifests
                and row.get("event_name") in composition_plans
            )
        )
    }
    if args.reviewed_subtitle_manifests:
        missing_reviewed = sorted(set(selected) - set(reviewed_subtitle_manifests))
        if missing_reviewed:
            raise ValueError(
                "reviewed subtitle baseline lacks selected events: "
                + ", ".join(missing_reviewed)
            )
        unready_reviewed = sorted(
            event
            for event in selected
            if reviewed_subtitle_manifests[event].get("_quality_ready") is not True
        )
        if unready_reviewed:
            raise ValueError(
                "reviewed subtitle baseline is not READY for selected events: "
                + ", ".join(unready_reviewed)
            )
    clips_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in clips:
        if row.get("event_name") in selected:
            clips_by_event[row["event_name"]].append(row)
    audio_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in audio_components:
        event = row.get("primary_animation", "")
        if event in selected:
            audio_by_event[event].append(row)
    sounds_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in event_sounds:
        event = row.get("event_name", "")
        if (
            event in selected
            and row.get("ogg_exists") == "yes"
            and row.get("timeline_confidence")
            == "exact_gdb_child_frame_callback_frame_and_official_ogg"
        ):
            sounds_by_event[event].append(row)
    subtitles_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in subtitle_timeline:
        event = row.get("event_name", "")
        if (
            event in selected
            and row.get("display_text", "").strip()
            and row.get("timeline_confidence") in GRAPHICAL_SUBTITLE_CONFIDENCE
        ):
            subtitles_by_event[event].append(row)

    summary_rows: list[dict] = []
    for event in sorted(selected):
        event_row = selected[event]
        composition_plan = composition_plans.get(event)
        runtime_manifest = runtime_event_manifests.get(event)
        reviewed_subtitle_manifest = reviewed_subtitle_manifests.get(event)
        reviewed_subtitle_reconciliation: dict = {}
        authored_plan_timing = bool(composition_plan) and (
            composition_plan_uses_authored_timing(composition_plan)
        )
        if runtime_manifest and composition_plan:
            event_clips = synthesize_runtime_event_clips(
                runtime_manifest,
                composition_plan,
                args.ffprobe,
                runtime_media_cache,
            )
        else:
            all_event_clips = sorted(
                clips_by_event.get(event, []),
                key=lambda row: (
                    number(row.get("z2d_order", "")),
                    number(row.get("event_start_ms", "")),
                    number(row.get("dgm_order", "")),
                ),
            )
            if composition_plan and composition_plan.get("clips"):
                planned_names = {
                    str(row.get("dgm_name", ""))
                    for row in composition_plan.get("clips", [])
                }
                if authored_plan_timing:
                    event_clips = synthesize_static_event_clips_from_plan(
                        [
                            row
                            for row in all_event_clips
                            if row.get("dgm_name", "") in planned_names
                        ],
                        composition_plan,
                    )
                else:
                    event_clips = [
                        row
                        for row in all_event_clips
                        if row.get("dgm_name", "") in planned_names
                    ]
            else:
                event_clips = all_event_clips
        dimensions = {
            (number(row.get("width", "")), number(row.get("height", "")))
            for row in event_clips
        }
        frame_rates = {
            row.get("frame_rate", "") for row in event_clips if row.get("frame_rate")
        }
        clip_paths = [
            row.get("target_mp4") or row.get("source_mp4", "")
            for row in event_clips
        ]
        errors: list[str] = []
        audience_exclusion_reason = audience_exclusions.get(event, "")
        if audience_exclusion_reason:
            errors.append("audience_component_only")
        if not event_clips:
            errors.append("no_clips")
        plan_native_dimensions = (
            composition_plan.get("native_dimensions", {})
            if composition_plan
            else {}
        )
        native_width = number(plan_native_dimensions.get("width", ""))
        native_height = number(plan_native_dimensions.get("height", ""))
        has_plan_native_dimensions = native_width > 0 and native_height > 0
        if len(dimensions) != 1 and not has_plan_native_dimensions:
            errors.append("mixed_dimensions")
        if len(frame_rates) != 1:
            errors.append("mixed_frame_rates")
        if (
            not composition_plan
            and any(
                row.get("media_class") != "full_frame_landscape"
                for row in event_clips
            )
        ):
            errors.append("component_media_present")
        if any(not path or not Path(path).exists() for path in clip_paths):
            errors.append("missing_clip")
        clip_source_sha256s: list[str] = []
        for clip_path in clip_paths:
            source_sha256 = ""
            if clip_path and Path(clip_path).is_file():
                resolved_clip = str(Path(clip_path).resolve())
                try:
                    if resolved_clip not in clip_sha256_cache:
                        clip_sha256_cache[resolved_clip] = file_sha256(
                            Path(resolved_clip)
                        )
                    source_sha256 = clip_sha256_cache[resolved_clip]
                except OSError:
                    source_sha256 = ""
            clip_source_sha256s.append(source_sha256)
        if any(not value for value in clip_source_sha256s):
            errors.append("unbound_clip_source_sha256")

        if runtime_manifest:
            audio_rows = synthesize_runtime_audio_rows(
                runtime_manifest,
                audio_by_event.get(event, []),
            )
            subtitle_rows = merge_runtime_graphical_subtitle_rows(
                apply_runtime_voice_subtitle_overrides(
                    synthesize_runtime_subtitle_rows(runtime_manifest),
                    voice_subtitle_overrides,
                ),
                subtitles_by_event.get(event, []),
            )
        else:
            audio_rows = []
            seen_audio: set[tuple[str, int]] = set()
            for row in sorted(
                audio_by_event.get(event, []),
                key=lambda item: (
                    number(item.get("start_ms", "")),
                    number(item.get("parent_sound_order", "")),
                    number(item.get("reqdata_index", "")),
                ),
            ):
                request_id = row.get("leaf_request_id", "")
                start_ms = number(row.get("start_ms", ""))
                key = (request_id, start_ms)
                if key in seen_audio:
                    continue
                seen_audio.add(key)
                path = resolve_ogg_path(
                    row.get("ogg_name", ""),
                    row.get("ogg_path", ""),
                    ogg_search_roots,
                    ogg_path_cache,
                )
                if not path or not Path(path).exists():
                    errors.append(f"missing_base_audio:{request_id}")
                audio_rows.append(
                    {
                        "source": "event_audio_component",
                        "request_id": request_id,
                        "code_name": row.get("leaf_code_name", ""),
                        "ogg_name": row.get("ogg_name", ""),
                        "path": path,
                        "start_ms": start_ms,
                        "duration_ms": number(row.get("duration_ms", "")),
                        "evidence": "gdb_event_sound_to_smz_leaf",
                    }
                )

            for row in sorted(
                sounds_by_event.get(event, []),
                key=lambda item: (
                    number(item.get("audio_start_ms", "")),
                    number(item.get("z2d_order", "")),
                    number(item.get("callback_index", "")),
                ),
            ):
                request_id = row.get("sound_request_id", "")
                start_ms = number(row.get("audio_start_ms", ""))
                code_name = row.get("sound_code_name", "")
                key = (f"{request_id}:{code_name}", start_ms)
                if key in seen_audio:
                    continue
                seen_audio.add(key)
                path = resolve_ogg_path(
                    row.get("ogg_name", ""),
                    row.get("ogg_path", ""),
                    ogg_search_roots,
                    ogg_path_cache,
                )
                if not path or not Path(path).exists():
                    errors.append(f"missing_z2d_audio:{request_id}")
                audio_rows.append(
                    {
                        "source": "z2d_req_sound",
                        "request_id": request_id,
                        "code_name": code_name,
                        "ogg_name": row.get("ogg_name", ""),
                        "path": path,
                        "start_ms": start_ms,
                        "duration_ms": number(row.get("sound_duration_ms", "")),
                        "z2d_name": row.get("z2d_name", ""),
                        "callback_exec_frame": number(
                            row.get("callback_exec_frame", "")
                        ),
                        "absolute_start_frame": row.get(
                            "absolute_start_frame", ""
                        ),
                        "evidence": row.get("timeline_confidence", ""),
                    }
                )

            subtitle_rows = []
            for row in sorted(
                subtitles_by_event.get(event, []),
                key=lambda item: (
                    number(item.get("start_ms") or item.get("subtitle_start_ms", "")),
                    number(item.get("z2d_order", "")),
                ),
            ):
                candidate = graphical_subtitle_row(row)
                if is_meaningful_subtitle_text(candidate["text"]):
                    subtitle_rows.append(candidate)

            audio_rows.sort(key=lambda row: (row["start_ms"], row["request_id"]))
            for audio_row in audio_rows:
                if audio_row["source"] != "z2d_req_sound":
                    continue
                already_subtitled = any(
                    subtitle.get("voice_request_id") == audio_row["request_id"]
                    for subtitle in subtitle_rows
                )
                if already_subtitled:
                    continue
                override = voice_subtitle_overrides.get(audio_row["request_id"])
                if override:
                    override_source = str(
                        override.get(
                            "source",
                            "accepted_voice_subtitle_override",
                        )
                    )
                    override_cues = override.get("cues", [])
                    if isinstance(override_cues, list) and override_cues:
                        for cue in override_cues:
                            if not isinstance(cue, dict):
                                continue
                            cue_text = str(cue.get("text", "")).strip()
                            if not cue_text:
                                continue
                            relative_start = max(0, number(cue.get("start_ms", 0)))
                            relative_end = max(
                                relative_start + 500,
                                number(cue.get("end_ms", 0)),
                            )
                            subtitle_rows.append(
                                {
                                    "text": cue_text,
                                    "start_ms": audio_row["start_ms"] + relative_start,
                                    "end_ms": audio_row["start_ms"] + relative_end,
                                    "voice_request_id": audio_row["request_id"],
                                    "voice_start_ms": audio_row["start_ms"],
                                    "z2d_name": audio_row.get("z2d_name", ""),
                                    "speaker_code": str(
                                        override.get("speaker_code", "")
                                    ),
                                    "subtitle_source": "official_voice_asr_verified",
                                    "evidence": override_source,
                                }
                            )
                        continue
                    override_text = str(override.get("text", "")).strip()
                    if override_text:
                        subtitle_rows.append(
                            {
                                "text": override_text,
                                "start_ms": audio_row["start_ms"],
                                "end_ms": max(
                                    audio_row["start_ms"]
                                    + audio_row["duration_ms"],
                                    audio_row["start_ms"] + 500,
                                ),
                                "voice_request_id": audio_row["request_id"],
                                "voice_start_ms": audio_row["start_ms"],
                                "z2d_name": audio_row.get("z2d_name", ""),
                                "speaker_code": str(
                                    override.get("speaker_code", "")
                                ),
                                "subtitle_source": "official_voice_asr_verified",
                                "evidence": override_source,
                            }
                        )
                        continue
                speaker, text = official_voice_label(audio_row["code_name"])
                if not text:
                    continue
                subtitle_source = "official_voice_label"
                subtitle_evidence = "official_sound_request_code_name"
                if text.endswith("-"):
                    continue
                subtitle_rows.append(
                    {
                        "text": text,
                        "start_ms": audio_row["start_ms"],
                        "end_ms": max(
                            audio_row["start_ms"] + audio_row["duration_ms"],
                            audio_row["start_ms"] + 500,
                        ),
                        "voice_request_id": audio_row["request_id"],
                        "voice_start_ms": audio_row["start_ms"],
                        "z2d_name": audio_row.get("z2d_name", ""),
                        "speaker_code": speaker,
                        "subtitle_source": subtitle_source,
                        "evidence": subtitle_evidence,
                    }
                )

        audio_rows = filter_audio_rows_for_plan(audio_rows, composition_plan)
        if any(
            not row["path"] or not Path(row["path"]).exists()
            for row in audio_rows
        ):
            errors.append("missing_audio_media")
        subtitle_rows = filter_subtitle_rows_for_plan(
            subtitle_rows,
            composition_plan,
        )
        if reviewed_subtitle_manifest:
            reviewed_projection = {
                **reviewed_subtitle_manifest,
                "subtitles": filter_subtitle_rows_for_plan(
                    reviewed_subtitle_manifest["subtitles"],
                    composition_plan,
                ),
            }
            subtitle_rows, reviewed_subtitle_reconciliation = (
                reconcile_reviewed_subtitle_rows(
                    event,
                    subtitle_rows,
                    audio_rows,
                    reviewed_projection,
                    voice_subtitle_overrides,
                )
            )
        subtitle_rows.sort(
            key=lambda row: (
                row["start_ms"],
                row["end_ms"],
                row["subtitle_source"],
            )
        )
        duration_ms = max(
            [number(row.get("event_end_ms", "")) for row in event_clips]
            + [
                row["start_ms"] + row["duration_ms"]
                for row in audio_rows
            ]
            + [row["end_ms"] for row in subtitle_rows]
            + [0]
        )
        video_duration_ms = max(
            [number(row.get("event_end_ms", "")) for row in event_clips] + [0]
        )
        timeline_tolerance_ms = 34
        short_hold_limit_ms = 200
        if event_clips and min(
            number(row.get("event_start_ms", "")) for row in event_clips
        ) > timeline_tolerance_ms:
            errors.append("video_timeline_nonzero_start")
        overlap_count = 0
        gap_count = 0
        for previous, current in zip(event_clips, event_clips[1:]):
            delta_ms = number(current.get("event_start_ms", "")) - number(
                previous.get("event_end_ms", "")
            )
            if delta_ms < -timeline_tolerance_ms:
                overlap_count += 1
            elif delta_ms > timeline_tolerance_ms:
                gap_count += 1

        planned_model = str((composition_plan or {}).get("model", ""))
        if planned_model == "timed_full_frame_layers":
            video_composition_model = "timed_full_frame_layers"
        elif overlap_count:
            video_composition_model = "timed_full_frame_layers"
        elif gap_count:
            video_composition_model = "timed_full_frame_with_gaps"
        else:
            video_composition_model = "linear_full_frame_sequence"

        if video_composition_model == "linear_full_frame_sequence":
            composition_resolved = True
            composition_evidence = "non_overlapping_static_timeline"
        elif composition_plan:
            valid_roles = {
                "background",
                "loop_background",
                "screen_overlay",
                "loop_screen_overlay",
            }
            valid_blend_modes = {"screen", "black_key", "opaque"}
            planned_names = {
                str(row.get("dgm_name", ""))
                for row in composition_plan.get("clips", [])
            }
            actual_names = {row.get("dgm_name", "") for row in event_clips}
            if planned_names != actual_names:
                errors.append("composition_plan_clip_mismatch")
                composition_resolved = False
            elif any(
                row.get("role") not in valid_roles
                for row in composition_plan.get("clips", [])
            ):
                errors.append("composition_plan_role_invalid")
                composition_resolved = False
            elif any(
                row.get("role") in {"screen_overlay", "loop_screen_overlay"}
                and row.get("blend_mode", "screen") not in valid_blend_modes
                for row in composition_plan.get("clips", [])
            ):
                errors.append("composition_plan_blend_mode_invalid")
                composition_resolved = False
            else:
                composition_resolved = True
                plan_rows = {
                    str(row.get("dgm_name", "")): row
                    for row in composition_plan.get("clips", [])
                }
                for clip in event_clips:
                    plan_row = plan_rows.get(clip.get("dgm_name", ""), {})
                    role = plan_row.get("role")
                    clip_dimensions = (
                        number(clip.get("width", "")),
                        number(clip.get("height", "")),
                    )
                    if (
                        role in {"background", "loop_background"}
                        and has_plan_native_dimensions
                        and clip_dimensions != (native_width, native_height)
                        and not plan_row.get("pad_to_native")
                    ):
                        errors.append("composition_background_dimension_mismatch")
                        composition_resolved = False
                    if (
                        role in {"screen_overlay", "loop_screen_overlay"}
                        and has_plan_native_dimensions
                        and clip_dimensions != (native_width, native_height)
                        and not plan_row.get("scale_to_native")
                    ):
                        errors.append("composition_overlay_scale_not_verified")
                        composition_resolved = False
            composition_evidence = str(
                composition_plan.get("evidence", "explicit_verified_plan")
            )
        else:
            composition_resolved = False
            composition_evidence = ""
            errors.append("unresolved_video_composition")

        plan_has_loops = bool(composition_plan) and any(
            row.get("role") in {"loop_background", "loop_screen_overlay"}
            for row in composition_plan.get("clips", [])
        )
        if plan_has_loops:
            errors = [
                error
                for error in errors
                if error != "timeline_exceeds_video_without_loop"
            ]

        raw_render_duration_ms = production_content_end_ms(
            video_duration_ms,
            duration_ms,
            composition_plan,
        )
        render_quantization: dict[str, int | str] = {}
        if len(frame_rates) == 1:
            try:
                render_quantization = quantize_duration_to_frame_grid(
                    raw_render_duration_ms, next(iter(frame_rates))
                )
            except ValueError:
                errors.append("invalid_native_frame_rate")
        else:
            errors.append("invalid_native_frame_rate")
        render_duration_ms = number(
            render_quantization.get("duration_ms", raw_render_duration_ms),
            raw_render_duration_ms,
        )
        extension_ms = max(0, render_duration_ms - video_duration_ms)
        last_dgm_name = event_clips[-1].get("dgm_name", "") if event_clips else ""
        verified_extension_policy = (
            str(composition_plan.get("extension_policy", ""))
            if composition_plan
            else ""
        )
        if verified_extension_policy not in {
            "",
            "none",
            "loop_last_clip",
            "hold_last_frame",
            "black_tail",
        }:
            errors.append("composition_plan_extension_policy_invalid")
        if verified_extension_policy == "none":
            if extension_ms > 0:
                errors.append("composition_plan_none_extension_conflict")
                video_extension_policy = "unsupported_timeline_overrun"
            else:
                video_extension_policy = "none"
        elif verified_extension_policy == "loop_last_clip":
            video_extension_policy = "loop_last_clip"
            errors = [
                error
                for error in errors
                if error != "timeline_exceeds_video_without_loop"
            ]
        elif verified_extension_policy == "hold_last_frame":
            video_extension_policy = "hold_last_frame"
        elif verified_extension_policy == "black_tail":
            video_extension_policy = "black_tail"
            errors = [
                error
                for error in errors
                if error != "timeline_exceeds_video_without_loop"
            ]
        elif extension_ms <= 0:
            video_extension_policy = "none"
        elif "_lp" in last_dgm_name.lower():
            video_extension_policy = "loop_last_clip"
        elif extension_ms <= short_hold_limit_ms:
            video_extension_policy = "hold_last_frame"
        elif plan_has_loops:
            video_extension_policy = "composition_plan_loops"
        else:
            video_extension_policy = "unsupported_timeline_overrun"
            errors.append("timeline_exceeds_video_without_loop")

        verified_native_composite = bool(composition_plan) and (
            composition_plan.get("model") == "timed_full_frame_layers"
            or len(dimensions) != 1
            or any(
                row.get("media_class") != "full_frame_landscape"
                for row in event_clips
            )
        )
        manifest = {
            "schema": "magireco-event-production-v3",
            "event": event,
            "event_code_hex": event_row.get("code_hex", ""),
            "classification": (
                "verified_native_composite"
                if verified_native_composite
                else event_row.get("classification", "")
            ),
            "audience_exclusion_reason": audience_exclusion_reason,
            "native_dimensions": (
                {"width": native_width, "height": native_height}
                if has_plan_native_dimensions
                else (
                    {
                        "width": next(iter(dimensions))[0],
                        "height": next(iter(dimensions))[1],
                    }
                    if len(dimensions) == 1
                    else {}
                )
            ),
            "native_frame_rate": next(iter(frame_rates)) if len(frame_rates) == 1 else "",
            "video_duration_ms": video_duration_ms,
            "timeline_duration_ms": duration_ms,
            "timeline_content_end_ms": raw_render_duration_ms,
            "raw_render_duration_ms": raw_render_duration_ms,
            "render_frame_count": number(
                render_quantization.get("frame_count", "")
            ),
            "render_duration_ms": render_duration_ms,
            "render_duration_quantization": render_quantization,
            "video_extension_policy": video_extension_policy,
            "video_composition_model": video_composition_model,
            "composition_plan": (
                {
                    key: value
                    for key, value in composition_plan.items()
                    if key != "_source_path"
                }
                if composition_plan
                else {}
            ),
            "composition_plan_source": (
                composition_plan.get("_source_path", "")
                if composition_plan
                else ""
            ),
            "runtime_event_manifest_sources": (
                runtime_manifest.get("_source_provenance", [])
                if runtime_manifest
                else []
            ),
            "reviewed_subtitle_manifest_sources": (
                reviewed_subtitle_manifest.get("_source_provenance", [])
                if reviewed_subtitle_manifest
                else []
            ),
            "reviewed_subtitle_reconciliation": (
                reviewed_subtitle_reconciliation
            ),
            "overlap_count": overlap_count,
            "gap_count": gap_count,
            "timeline_tolerance_ms": timeline_tolerance_ms,
            "clips": [
                {
                    "order": index,
                    "dgm_name": row.get("dgm_name", ""),
                    "dgm_role": row.get("dgm_role", ""),
                    "path": path,
                    "source_sha256": source_sha256,
                    "event_start_ms": number(row.get("event_start_ms", "")),
                    "event_end_ms": number(row.get("event_end_ms", "")),
                    "interval_confidence": row.get("interval_confidence", ""),
                }
                for index, (row, path, source_sha256) in enumerate(
                    zip(event_clips, clip_paths, clip_source_sha256s)
                )
            ],
            "audio": audio_rows,
            "subtitles": subtitle_rows,
            "quality_gates": {
                "all_full_frame": all(
                    row.get("media_class") == "full_frame_landscape"
                    for row in event_clips
                ),
                "all_clips_exist": all(
                    path and Path(path).exists() for path in clip_paths
                ),
                "all_clip_source_hashes_bound": all(
                    bool(value) for value in clip_source_sha256s
                ),
                "all_audio_exist": all(
                    row["path"] and Path(row["path"]).exists() for row in audio_rows
                ),
                "verified_subtitle_voice_count": len(subtitle_rows),
                "graphical_display_subtitle_count": sum(
                    row["subtitle_source"] == "graphical_display_text"
                    for row in subtitle_rows
                ),
                "official_voice_label_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_label"
                    for row in subtitle_rows
                ),
                "asr_verified_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_asr_verified"
                    for row in subtitle_rows
                ),
                "reviewed_subtitle_baseline_applied": bool(
                    reviewed_subtitle_manifest
                ),
                "reviewed_subtitle_current_only_voice_candidate_count": len(
                    reviewed_subtitle_reconciliation.get(
                        "excluded_current_voice_candidates",
                        [],
                    )
                ),
                "reviewed_subtitle_current_only_graphical_candidate_count": len(
                    reviewed_subtitle_reconciliation.get(
                        "excluded_current_graphical_candidates",
                        [],
                    )
                ),
                "exact_z2d_req_sound_count": sum(
                    row["source"] == "z2d_req_sound"
                    for row in audio_rows
                ),
                "linear_video_timeline": (
                    video_composition_model == "linear_full_frame_sequence"
                    and "video_timeline_nonzero_start" not in errors
                ),
                "video_composition_model": video_composition_model,
                "composition_resolved": composition_resolved,
                "composition_evidence": composition_evidence,
                "video_extension_supported": (
                    video_extension_policy != "unsupported_timeline_overrun"
                ),
                "audio_timeline_ready": (
                    bool(audio_rows)
                    and all(
                        row["path"] and Path(row["path"]).exists()
                        for row in audio_rows
                    )
                ),
                "errors": sorted(set(errors)),
                "render_ready": not errors and composition_resolved,
                "ready": not errors and composition_resolved,
            },
        }
        manifest_path = resolve_output_child(
            event_dir, f"{event}.json", label="event production manifest"
        )
        with manifest_path.open("w", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
        summary_rows.append(
            {
                "event_name": event,
                "event_code_hex": event_row.get("code_hex", ""),
                "audience_exclusion_reason": audience_exclusion_reason,
                "width": manifest.get("native_dimensions", {}).get("width", ""),
                "height": manifest.get("native_dimensions", {}).get("height", ""),
                "frame_rate": manifest.get("native_frame_rate", ""),
                "clip_count": len(event_clips),
                "base_audio_count": sum(
                    row["source"] == "event_audio_component" for row in audio_rows
                ),
                "z2d_sound_count": sum(
                    row["source"] == "z2d_req_sound" for row in audio_rows
                ),
                "subtitle_count": len(subtitle_rows),
                "graphical_subtitle_count": sum(
                    row["subtitle_source"] == "graphical_display_text"
                    for row in subtitle_rows
                ),
                "voice_label_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_label"
                    for row in subtitle_rows
                ),
                "asr_verified_subtitle_count": sum(
                    row["subtitle_source"] == "official_voice_asr_verified"
                    for row in subtitle_rows
                ),
                "video_composition_model": video_composition_model,
                "composition_resolved": (
                    "yes" if composition_resolved else "no"
                ),
                "overlap_count": overlap_count,
                "gap_count": gap_count,
                "video_duration_ms": video_duration_ms,
                "timeline_duration_ms": duration_ms,
                "timeline_content_end_ms": raw_render_duration_ms,
                "render_frame_count": number(
                    render_quantization.get("frame_count", "")
                ),
                "render_duration_ms": render_duration_ms,
                "video_extension_policy": video_extension_policy,
                "audio_timeline_ready": (
                    "yes"
                    if audio_rows
                    and all(
                        row["path"] and Path(row["path"]).exists()
                        for row in audio_rows
                    )
                    else "no"
                ),
                "render_ready": (
                    "yes" if not errors and composition_resolved else "no"
                ),
                "ready": (
                    "yes" if not errors and composition_resolved else "no"
                ),
                "errors": ";".join(sorted(set(errors))),
                "manifest_path": str(manifest_path),
            }
        )

    fields = [
        "event_name",
        "event_code_hex",
        "audience_exclusion_reason",
        "width",
        "height",
        "frame_rate",
        "clip_count",
        "base_audio_count",
        "z2d_sound_count",
        "subtitle_count",
        "graphical_subtitle_count",
        "voice_label_subtitle_count",
        "asr_verified_subtitle_count",
        "video_composition_model",
        "composition_resolved",
        "overlap_count",
        "gap_count",
        "video_duration_ms",
        "timeline_duration_ms",
        "timeline_content_end_ms",
        "render_frame_count",
        "render_duration_ms",
        "video_extension_policy",
        "audio_timeline_ready",
        "render_ready",
        "ready",
        "errors",
        "manifest_path",
    ]
    write_csv(out_dir / "event_production_catalog.csv", summary_rows, fields)
    summary = {
        "events": len(summary_rows),
        "ready_events": sum(row["ready"] == "yes" for row in summary_rows),
        "failed_events": sum(row["ready"] != "yes" for row in summary_rows),
        "audio_timeline_ready_events": sum(
            row["audio_timeline_ready"] == "yes" for row in summary_rows
        ),
        "composition_resolved_events": sum(
            row["composition_resolved"] == "yes" for row in summary_rows
        ),
        "audience_excluded_events": sum(
            bool(row["audience_exclusion_reason"]) for row in summary_rows
        ),
        "clips": sum(int(row["clip_count"]) for row in summary_rows),
        "base_audio_tracks": sum(
            int(row["base_audio_count"]) for row in summary_rows
        ),
        "z2d_sound_tracks": sum(
            int(row["z2d_sound_count"]) for row in summary_rows
        ),
        "subtitles": sum(int(row["subtitle_count"]) for row in summary_rows),
        "graphical_subtitles": sum(
            int(row["graphical_subtitle_count"]) for row in summary_rows
        ),
        "voice_label_subtitles": sum(
            int(row["voice_label_subtitle_count"]) for row in summary_rows
        ),
        "asr_verified_subtitles": sum(
            int(row["asr_verified_subtitle_count"]) for row in summary_rows
        ),
    }
    with (out_dir / "event_production_summary.json").open(
        "w", encoding="utf-8"
    ) as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
