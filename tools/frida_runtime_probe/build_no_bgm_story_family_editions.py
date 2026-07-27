#!/usr/bin/env python3
"""Build auditable no-BGM story-family editions from reviewed manifests.

This is an independent expansion lane.  It deliberately reuses the proven event
preparation, clean-visual rendering, and voice/SE reconstruction mechanisms from
``build_sp_story_chapter_reviews.py`` without changing that already-reviewed
builder.  One clean visual master and one encoded-once AAC master feed any selected
subset of these editions:

* ``none``: no subtitles, stream-copy video and AAC;
* ``ja``: Japanese voice-bound dialogue burned into the native picture;
* ``zh``: reviewed-map Chinese voice-bound dialogue burned into the picture;
* ``ja_zh``: Japanese above Chinese in one burned subtitle cue.

The default expansion order is ``none``, ``ja``, and ``zh``.  ``ja_zh`` remains an
explicit opt-in edition so producing the first three never waits for bilingual
layout review.  Every generated MP4 is checked for the exact native frame grid and
for bit-identical AAC packets copied from the single audio master.  Human playback
and publication flags always remain false.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_audio_base_masters as audio_gate
    from .build_independent_scene_release import (
        build_event_pcm,
        concat_binary,
        file_sha256,
        frame_count,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        stream_bit_rate,
        subtitle_filter,
        volume_audit,
        write_json,
        write_srt,
    )
    from .build_event_production_manifests import load_voice_subtitle_overrides
    from .build_sp_story_chapter_reviews import (
        FORBIDDEN_AUDIO_REQUESTS,
        canonical_sha256,
        ffconcat_quote,
        load_layout_profiles,
        load_translation_map,
        prepare_manifest,
        promote,
        read_json,
        rehash,
        resolve_event,
        resolve_series_manifests,
        scene_audio_role,
        snapshot,
        validate_audio_layer_roles,
        validate_audio_absence_evidence,
        validate_reusable_clean_visual,
    )
    from .output_path_contract import resolve_output_child, validate_output_identifier
except ImportError:  # direct script execution
    import build_audio_base_masters as audio_gate  # type: ignore
    from build_independent_scene_release import (  # type: ignore
        build_event_pcm,
        concat_binary,
        file_sha256,
        frame_count,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        stream_bit_rate,
        subtitle_filter,
        volume_audit,
        write_json,
        write_srt,
    )
    from build_event_production_manifests import (  # type: ignore
        load_voice_subtitle_overrides,
    )
    from build_sp_story_chapter_reviews import (  # type: ignore
        FORBIDDEN_AUDIO_REQUESTS,
        canonical_sha256,
        ffconcat_quote,
        load_layout_profiles,
        load_translation_map,
        prepare_manifest,
        promote,
        read_json,
        rehash,
        resolve_event,
        resolve_series_manifests,
        scene_audio_role,
        snapshot,
        validate_audio_layer_roles,
        validate_audio_absence_evidence,
        validate_reusable_clean_visual,
    )
    from output_path_contract import (  # type: ignore
        resolve_output_child,
        validate_output_identifier,
    )


BATCH_SCHEMA = "magireco-no-bgm-story-family-editions-batch-v1"
MANIFEST_SCHEMA = "magireco-no-bgm-story-family-editions-v1"
QA_SCHEMA = "magireco-no-bgm-story-family-editions-qa-v1"
READY_SCHEMA = "magireco-no-bgm-story-family-editions-ready-v1"
SPEAKER_SCHEMA = "magireco-audited-speaker-display-registry-v1"
SPEAKER_IDENTITY_OVERRIDE_SCHEMA = (
    "magireco-hash-bound-speaker-identity-overrides-v1"
)
RELATIONSHIP_RULE_SCHEMA = "magireco-dialogue-relationship-rules-v1"
AUDIO_OVERRIDE_SCHEMAS = {
    "magireco-hash-bound-audio-role-overrides-v1",
    "magireco-evidence-bound-audio-role-overrides-v1",
}
EXPLICITLY_EXCLUDABLE_SLOT_EFFECT_REQUESTS = {"1681"}
SUPPORTED_EDITIONS = ("none", "ja", "zh", "ja_zh")
DEFAULT_EDITIONS = ("none", "ja", "zh")
SUBTITLE_EDITIONS = {"ja", "zh", "ja_zh"}
OMITTED_SPEAKER_CODES = {"", "multiple", "narration", "unknown", "conflicting"}


def normalize_editions(values: Sequence[str] | None) -> tuple[str, ...]:
    """Return a stable, duplicate-free edition selection."""

    requested = list(values) if values else list(DEFAULT_EDITIONS)
    invalid = sorted(set(requested) - set(SUPPORTED_EDITIONS))
    if invalid:
        raise ValueError(f"unsupported editions: {invalid}")
    if not requested:
        raise ValueError("at least one edition is required")
    seen: set[str] = set()
    result: list[str] = []
    for edition in SUPPORTED_EDITIONS:
        if edition in requested and edition not in seen:
            result.append(edition)
            seen.add(edition)
    return tuple(result)


def load_speaker_registry(path: Path | None) -> tuple[dict[str, dict[str, str]], dict[str, str] | None]:
    """Load the owner-authorized display registry used only with cue evidence."""

    if path is None:
        return {}, None
    value = read_json(path.resolve())
    if value.get("schema") != SPEAKER_SCHEMA:
        raise ValueError("unsupported speaker registry schema")
    policy = value.get("policy")
    if not isinstance(policy, Mapping) or policy.get(
        "prefix_only_when_speaker_identity_is_evidence_bound"
    ) is not True:
        raise ValueError("speaker registry does not require evidence-bound identities")
    rows = value.get("speakers")
    if not isinstance(rows, Mapping):
        raise ValueError("speaker registry lacks speakers")
    result: dict[str, dict[str, str]] = {}
    for raw_code, raw_names in rows.items():
        code = str(raw_code).strip()
        if not code or code in OMITTED_SPEAKER_CODES or not isinstance(raw_names, Mapping):
            raise ValueError(f"invalid speaker registry row: {raw_code!r}")
        names = {language: str(raw_names.get(language, "")).strip() for language in ("ja", "zh")}
        if not all(names.values()):
            raise ValueError(f"speaker registry row lacks ja/zh names: {code}")
        result[code] = names
    if "kuro" in result:
        raise ValueError(
            "ambiguous raw speaker code kuro must not have a global display identity"
        )
    distinct_codes = ("kuro_black_feather", "kuro_character", "kuroe")
    distinct_names = [
        tuple(result[code][language] for language in ("ja", "zh"))
        for code in distinct_codes
        if code in result
    ]
    if len(distinct_names) != len(set(distinct_names)):
        raise ValueError("speaker registry collapses Black Feather, Kuro, and Kuroe")
    return result, snapshot(path.resolve(), label="audited speaker display registry")


def load_speaker_identity_overrides(
    path: Path | None,
) -> tuple[
    dict[tuple[str, str, str], dict[str, str]],
    dict[str, str] | None,
]:
    """Load owner-authorized contextual identities for ambiguous raw labels."""

    if path is None:
        return {}, None
    path = path.resolve()
    value = read_json(path)
    if (
        value.get("schema") != SPEAKER_IDENTITY_OVERRIDE_SCHEMA
        or value.get("status") != "project_owner_authorized"
    ):
        raise ValueError("speaker identity overrides are not owner-authorized")
    rows = value.get("overrides")
    if not isinstance(rows, list):
        raise ValueError("speaker identity overrides lack rows")
    required_fields = {
        "event",
        "request_id",
        "raw_speaker_code",
        "canonical_speaker_code",
        "code_name",
        "audio_sha256",
        "evidence",
        "owner_attestation_id",
    }
    result: dict[tuple[str, str, str], dict[str, str]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != required_fields:
            raise ValueError(f"speaker identity override {index} fields differ")
        normalized = {key: str(row[key]).strip() for key in required_fields}
        normalized["audio_sha256"] = normalized["audio_sha256"].upper()
        key = (
            normalized["event"],
            normalized["request_id"],
            normalized["raw_speaker_code"],
        )
        if (
            not all(normalized.values())
            or key in result
            or len(normalized["audio_sha256"]) != 64
            or any(
                character not in "0123456789ABCDEF"
                for character in normalized["audio_sha256"]
            )
            or normalized["raw_speaker_code"] != "kuro"
            or normalized["canonical_speaker_code"]
            not in {"kuro_black_feather", "kuro_character"}
        ):
            raise ValueError(f"speaker identity override {index} is invalid")
        result[key] = normalized
    return result, snapshot(path, label="hash-bound contextual speaker identities")


def load_dialogue_relationship_rules(
    path: Path,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Load the owner-authorized Japanese-address to Chinese-form contract."""

    path = path.resolve()
    value = read_json(path)
    if (
        value.get("schema") != RELATIONSHIP_RULE_SCHEMA
        or value.get("status") != "project_owner_authorized"
    ):
        raise ValueError("dialogue relationship rules are not owner-authorized")
    rows = value.get("rules")
    if not isinstance(rows, list) or not rows:
        raise ValueError("dialogue relationship rules must contain rows")
    required_fields = {
        "id",
        "speaker_codes",
        "ja_addressee_pattern",
        "required_zh_form",
        "forbidden_zh_forms",
    }
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != required_fields:
            raise ValueError(f"dialogue relationship rule {index} fields differ")
        rule_id = str(row["id"]).strip()
        speaker_codes = row["speaker_codes"]
        ja_pattern = str(row["ja_addressee_pattern"]).strip()
        required_zh = str(row["required_zh_form"]).strip()
        forbidden_zh = row["forbidden_zh_forms"]
        if (
            not rule_id
            or rule_id in seen_ids
            or not isinstance(speaker_codes, list)
            or not speaker_codes
            or any(not str(code).strip() for code in speaker_codes)
            or not ja_pattern
            or not required_zh
            or not isinstance(forbidden_zh, list)
            or not forbidden_zh
            or any(not str(value).strip() for value in forbidden_zh)
        ):
            raise ValueError(f"dialogue relationship rule {index} is invalid")
        seen_ids.add(rule_id)
        result.append(
            {
                "id": rule_id,
                "speaker_codes": [str(code).strip() for code in speaker_codes],
                "ja_addressee_pattern": ja_pattern,
                "required_zh_form": required_zh,
                "forbidden_zh_forms": [
                    str(value).strip() for value in forbidden_zh
                ],
            }
        )
    return result, snapshot(path, label="owner-authorized dialogue relationship rules")


def validate_translation_relationship_rules(
    translations: Mapping[str, str],
    rules: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Fail closed when a registered Japanese address is mistranslated."""

    audit: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = str(rule["id"])
        ja_pattern = str(rule["ja_addressee_pattern"])
        required_zh = str(rule["required_zh_form"])
        forbidden_zh = [str(value) for value in rule["forbidden_zh_forms"]]
        matched: list[str] = []
        for ja, zh in translations.items():
            occurrence_count = ja.count(ja_pattern)
            if occurrence_count == 0:
                continue
            forbidden_hits = [value for value in forbidden_zh if value in zh]
            if forbidden_hits or zh.count(required_zh) < occurrence_count:
                raise ValueError(
                    f"translation relationship rule {rule_id} failed for {ja!r}: "
                    f"required={required_zh!r}, forbidden_hits={forbidden_hits}"
                )
            matched.append(ja)
        audit.append(
            {
                "rule_id": rule_id,
                "ja_addressee_pattern": ja_pattern,
                "required_zh_form": required_zh,
                "matched_translation_keys": matched,
            }
        )
    return audit


def load_audio_role_overrides(
    path: Path | None,
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, str] | None]:
    """Load exact, hash-bound exceptions for business audio-role classification."""

    if path is None:
        return {}, None
    value = read_json(path.resolve())
    if value.get("schema") not in AUDIO_OVERRIDE_SCHEMAS:
        raise ValueError("unsupported audio-role override schema")
    rows = value.get("overrides")
    if not isinstance(rows, list) or not rows:
        raise ValueError("audio-role override file must contain rows")
    result: dict[tuple[str, str], dict[str, str]] = {}
    required = {
        "event",
        "request_id",
        "code_name",
        "source_sha256",
        "role",
        "evidence",
    }
    for index, row in enumerate(rows):
        if (
            not isinstance(row, Mapping)
            or not required.issubset(row)
            or set(row) - required - {"ogg_name"}
        ):
            raise ValueError(f"audio-role override row {index} fields differ")
        normalized = {field: str(row[field]).strip() for field in required}
        if "ogg_name" in row:
            normalized["ogg_name"] = str(row["ogg_name"]).strip()
        key = (normalized["event"], normalized["request_id"])
        if (
            not all(normalized.values())
            or normalized["role"] not in {"scene_se", "exclude_slot_effect"}
            or len(normalized["source_sha256"]) != 64
            or key in result
        ):
            raise ValueError(f"audio-role override row {index} is invalid")
        normalized["source_sha256"] = normalized["source_sha256"].upper()
        result[key] = normalized
    return result, snapshot(path.resolve(), label="hash-bound audio-role overrides")


def apply_audio_role_overrides(
    manifest: Mapping[str, Any],
    overrides: Mapping[tuple[str, str], Mapping[str, str]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Project exact exceptions into the legacy resolver without weakening it."""

    projected = copy.deepcopy(manifest)
    event = str(projected["event"])
    applied: list[dict[str, str]] = []
    audio_rows = projected.get("audio")
    if not isinstance(audio_rows, list):
        raise ValueError(f"{event} lacks audio rows")
    seen_requests: set[str] = set()
    retained_audio_rows: list[dict[str, Any]] = []
    excluded_request_ids: set[str] = set()
    for row in audio_rows:
        if not isinstance(row, dict):
            raise ValueError(f"{event} has an invalid audio row")
        request_id = str(row.get("request_id", ""))
        key = (event, request_id)
        override = overrides.get(key)
        if override is None:
            retained_audio_rows.append(row)
            continue
        if request_id in seen_requests:
            raise ValueError(f"{event} override request is duplicated: {request_id}")
        seen_requests.add(request_id)
        audio_path = Path(str(row.get("path", ""))).resolve()
        observed_hash = file_sha256(audio_path)
        if (
            str(row.get("code_name", "")) != override["code_name"]
            or (
                "ogg_name" in override
                and str(row.get("ogg_name", "")) != override["ogg_name"]
            )
            or observed_hash != override["source_sha256"]
            or (
                request_id in FORBIDDEN_AUDIO_REQUESTS
                and not (
                    override["role"] == "exclude_slot_effect"
                    and request_id in EXPLICITLY_EXCLUDABLE_SLOT_EFFECT_REQUESTS
                )
            )
        ):
            raise ValueError(f"{event} audio-role override evidence mismatch: {request_id}")
        if override["role"] == "scene_se":
            if any(
                str(cue.get("voice_request_id", "")).strip() == request_id
                for cue in projected.get("subtitles", [])
                if isinstance(cue, Mapping)
            ):
                raise ValueError(
                    f"{event} scene-SE override conflicts with a subtitle-bound "
                    f"request: {request_id}"
                )
            row["source"] = "event_audio_component"
            retained_audio_rows.append(row)
        else:
            excluded_request_ids.add(request_id)
        applied.append(dict(override))
    projected["audio"] = retained_audio_rows
    if excluded_request_ids:
        subtitle_rows = projected.get("subtitles", [])
        if not isinstance(subtitle_rows, list):
            raise ValueError(f"{event} lacks subtitle rows for excluded slot audio")
        retained_subtitles: list[dict[str, Any]] = []
        for row in subtitle_rows:
            if not isinstance(row, dict):
                raise ValueError(f"{event} has an invalid subtitle row")
            request_id = str(row.get("voice_request_id", "")).strip()
            if request_id not in excluded_request_ids:
                retained_subtitles.append(row)
                continue
            if row.get("subtitle_source") != "graphical_display_text":
                raise ValueError(
                    f"{event} excluded slot audio is bound to non-graphical dialogue: "
                    f"{request_id}"
                )
        projected["subtitles"] = retained_subtitles
    return projected, applied


def apply_missing_voice_subtitle_overrides(
    manifest: Mapping[str, Any],
    overrides: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Add only exact, hash-bound official-label cues absent from old manifests."""

    projected = copy.deepcopy(manifest)
    event = str(projected["event"])
    audio_rows = projected.get("audio")
    subtitle_rows = projected.get("subtitles")
    if not isinstance(audio_rows, list) or not isinstance(subtitle_rows, list):
        raise ValueError(f"{event} lacks audio or subtitle rows")
    existing_request_ids = {
        str(row.get("voice_request_id", "")).strip()
        for row in subtitle_rows
        if isinstance(row, Mapping)
    }
    applied: list[dict[str, str]] = []
    for row in audio_rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{event} has an invalid audio row")
        request_id = str(row.get("request_id", "")).strip()
        override = overrides.get(request_id)
        if override is None or request_id in existing_request_ids:
            continue
        text = str(override.get("text", "")).strip()
        official_prefix = str(override.get("official_prefix", "")).strip()
        speaker_code = str(override.get("speaker_code", "")).strip()
        expected_hash = str(override.get("audio_sha256", "")).strip().upper()
        expected_ogg = str(override.get("ogg_name", "")).strip()
        audio_path = Path(str(row.get("path", ""))).resolve()
        if (
            not text
            or not official_prefix
            or official_prefix not in str(row.get("code_name", ""))
            or not speaker_code
            or len(expected_hash) != 64
            or file_sha256(audio_path) != expected_hash
            or (expected_ogg and str(row.get("ogg_name", "")) != expected_ogg)
        ):
            raise ValueError(
                f"{event} missing voice subtitle override evidence mismatch: "
                f"{request_id}"
            )
        start_ms = round(float(row.get("start_ms", 0)))
        duration_ms = max(500, round(float(row.get("duration_ms", 0))))
        source = str(
            override.get("source", "curated_official_sound_request_code_name")
        ).strip()
        subtitle_rows.append(
            {
                "text": text,
                "start_ms": start_ms,
                "end_ms": start_ms + duration_ms,
                "voice_request_id": request_id,
                "voice_start_ms": start_ms,
                "z2d_name": str(row.get("z2d_name", "")),
                "speaker_code": speaker_code,
                "subtitle_source": "official_voice_label",
                "evidence": source,
            }
        )
        existing_request_ids.add(request_id)
        applied.append(
            {
                "event": event,
                "request_id": request_id,
                "text": text,
                "speaker_code": speaker_code,
                "audio_sha256": expected_hash,
                "evidence": source,
            }
        )
    return projected, applied


def attach_speaker_evidence(
    resolved: dict[str, Any], manifest: Mapping[str, Any]
) -> None:
    """Copy official speaker evidence onto already voice-bound resolved cues."""

    event = str(resolved["event"])
    evidence_by_request: dict[str, dict[str, str]] = {}
    for row in manifest.get("subtitles", []):
        if not isinstance(row, Mapping):
            continue
        request_id = str(row.get("voice_request_id", "")).strip()
        if not request_id:
            continue
        if request_id in evidence_by_request:
            raise ValueError(f"{event} has duplicate subtitle speaker evidence: {request_id}")
        evidence_by_request[request_id] = {
            "speaker_code": str(row.get("speaker_code", "")).strip(),
            "subtitle_source": str(row.get("subtitle_source", "")).strip(),
            "evidence": str(row.get("evidence", "")).strip(),
        }
    for cue in resolved["dialogue_cues"]:
        request_id = str(cue["request_id"])
        evidence = evidence_by_request.get(request_id)
        if evidence is None:
            raise ValueError(f"{event} cue lacks source speaker evidence: {request_id}")
        cue.update(evidence)


def apply_speaker_identity_overrides(
    resolved: dict[str, Any],
    manifest: Mapping[str, Any],
    overrides: Mapping[tuple[str, str, str], Mapping[str, str]],
) -> list[dict[str, str]]:
    """Resolve an ambiguous raw code only for one exact event/request/audio."""

    event = str(resolved["event"])
    audio_by_request: dict[str, Mapping[str, Any]] = {}
    for row in manifest.get("audio", []):
        if not isinstance(row, Mapping):
            raise ValueError(f"{event} has an invalid audio row")
        request_id = str(row.get("request_id", "")).strip()
        if not request_id:
            continue
        if request_id in audio_by_request:
            raise ValueError(f"{event} has duplicate audio request: {request_id}")
        audio_by_request[request_id] = row

    applied: list[dict[str, str]] = []
    for cue in resolved["dialogue_cues"]:
        request_id = str(cue["request_id"]).strip()
        raw_code = str(cue.get("speaker_code", "")).strip()
        override = overrides.get((event, request_id, raw_code))
        if override is None:
            continue
        audio = audio_by_request.get(request_id)
        if audio is None:
            raise ValueError(
                f"{event} speaker identity override lacks audio request: {request_id}"
            )
        audio_path = Path(str(audio.get("path", ""))).resolve()
        expected_hash = str(override["audio_sha256"]).upper()
        if (
            str(audio.get("code_name", "")).strip()
            != str(override["code_name"]).strip()
            or not audio_path.is_file()
            or file_sha256(audio_path) != expected_hash
        ):
            raise ValueError(
                f"{event} speaker identity override evidence mismatch: {request_id}"
            )
        canonical_code = str(override["canonical_speaker_code"]).strip()
        cue["raw_speaker_code"] = raw_code
        cue["speaker_code"] = canonical_code
        cue["speaker_identity_evidence"] = str(override["evidence"]).strip()
        applied.append(
            {
                "event": event,
                "request_id": request_id,
                "raw_speaker_code": raw_code,
                "canonical_speaker_code": canonical_code,
                "code_name": str(override["code_name"]).strip(),
                "audio_sha256": expected_hash,
                "evidence": str(override["evidence"]).strip(),
                "owner_attestation_id": str(
                    override["owner_attestation_id"]
                ).strip(),
            }
        )
    return applied


def display_text(
    cue: Mapping[str, Any], language: str, speakers: Mapping[str, Mapping[str, str]]
) -> str:
    """Format one language, prefixing only an explicitly evidenced mapped speaker."""

    if language not in {"ja", "zh"}:
        raise ValueError(f"unsupported cue language: {language}")
    text = str(cue[f"{language}_text"]).strip()
    code = str(cue.get("speaker_code", "")).strip()
    source = str(cue.get("subtitle_source", "")).strip()
    evidence = str(cue.get("evidence", "")).strip()
    names = speakers.get(code)
    if (
        code in OMITTED_SPEAKER_CODES
        or not source
        or not evidence
        or names is None
    ):
        return text
    return f"{names[language]}：{text}"


def edition_cues(
    base_cues: Sequence[Mapping[str, Any]],
    edition: str,
    speakers: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    if edition not in SUBTITLE_EDITIONS:
        raise ValueError(f"edition has no subtitle cues: {edition}")
    result: list[dict[str, Any]] = []
    for cue in base_cues:
        if edition == "ja":
            text = display_text(cue, "ja", speakers)
        elif edition == "zh":
            text = display_text(cue, "zh", speakers)
        else:
            text = (
                f"{display_text(cue, 'ja', speakers)}\n"
                f"{display_text(cue, 'zh', speakers)}"
            )
        result.append(
            {
                "start_ms": int(cue["start_ms"]),
                "end_ms": int(cue["end_ms"]),
                "text": text,
                "event": str(cue["event"]),
                "request_id": str(cue["request_id"]),
                "speaker_code": str(cue.get("speaker_code", "")),
            }
        )
    return result


def assert_srt_round_trip(path: Path, cues: Sequence[Mapping[str, Any]]) -> None:
    write_srt(path, cues)
    parsed = parse_srt(path)
    expected = [
        {
            "start_ms": int(row["start_ms"]),
            "end_ms": int(row["end_ms"]),
            "text": str(row["text"]),
        }
        for row in cues
    ]
    if parsed != expected:
        raise RuntimeError(f"SRT round-trip mismatch: {path}")


def is_evidence_bound_silent_manifest(manifest: Mapping[str, Any]) -> bool:
    """Return true only for a manifest with exact, hash-bound zero-audio proof."""

    audio = manifest.get("audio")
    gates = manifest.get("quality_gates")
    evidence = manifest.get("audio_absence_evidence")
    return (
        audio == []
        and isinstance(gates, Mapping)
        and gates.get("verified_no_event_audio") is True
        and isinstance(evidence, Mapping)
        and evidence.get("status") == "hash_bound_zero_matches"
        and evidence.get("direct_parent_audio_matches") == 0
        and evidence.get("child_audio_matches") == 0
        and evidence.get("subtitle_matches") == 0
        and isinstance(evidence.get("source_snapshots"), list)
        and len(evidence["source_snapshots"]) == 3
    )


def resolve_story_event(
    manifest: Mapping[str, Any],
    *,
    clean_visual: Path,
    clean_report: Path,
    translations: Mapping[str, str],
    reject_unsubtitled_audio: bool,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Resolve a normal voiced event or one exactly proven silent event."""

    if not is_evidence_bound_silent_manifest(manifest):
        return resolve_event(
            manifest,
            clean_visual=clean_visual,
            clean_report=clean_report,
            translations=translations,
            require_scene_se=False,
            reject_unsubtitled_audio=reject_unsubtitled_audio,
        )
    absence_sources = validate_audio_absence_evidence(manifest)
    event = str(manifest["event"])
    report = read_json(clean_report)
    clean_source = snapshot(clean_visual, label=f"{event} clean visual")
    report_source = snapshot(
        clean_report, label=f"{event} clean visual render manifest"
    )
    if (
        report.get("event") != event
        or report.get("status") != "passed"
        or str(report.get("output_sha256", "")).upper()
        != clean_source["sha256"]
    ):
        raise ValueError(f"{event} clean visual report is not passed")
    quantization = manifest.get("render_duration_quantization")
    if not isinstance(quantization, Mapping):
        raise ValueError(f"{event} lacks CFR quantization evidence")
    frame_count_value = int(manifest["render_frame_count"])
    samples = int(quantization["audio_sample_count"])
    if samples != frame_count_value * 1600:
        raise ValueError(f"{event} frame/sample grids differ")
    if manifest.get("subtitles") != []:
        raise ValueError(f"{event} silent event unexpectedly contains subtitles")
    return (
        {
            "event": event,
            "width": int(manifest["native_dimensions"]["width"]),
            "height": int(manifest["native_dimensions"]["height"]),
            "composition_model": str(manifest["video_composition_model"]),
            "frame_count": frame_count_value,
            "presentation_samples": samples,
            "clean_visual": clean_visual,
            "clean_report": clean_report,
            "audio_layers": [],
            "dialogue_cues": [],
            "excluded_voice_requests": [],
            "excluded_source_cues": [],
            "verified_no_event_audio": True,
            "audio_absence_evidence": copy.deepcopy(
                manifest["audio_absence_evidence"]
            ),
        },
        [clean_source, report_source, *absence_sources],
    )


def build_event_pcm_or_verified_silence(
    event: Mapping[str, Any],
    *,
    output: Path,
    ffmpeg: str,
) -> dict[str, Any]:
    """Render event PCM, permitting zeros only after exact absence proof."""

    layers = event.get("audio_layers")
    if isinstance(layers, list) and layers:
        return build_event_pcm(event, output=output, ffmpeg=ffmpeg)
    if (
        layers != []
        or event.get("verified_no_event_audio") is not True
        or not isinstance(event.get("audio_absence_evidence"), Mapping)
    ):
        raise RuntimeError(
            f"{event.get('event')} has no audio layers without exact absence proof"
        )
    samples = int(event["presentation_samples"])
    expected_bytes = samples * 2 * 4
    with output.open("wb") as target:
        target.truncate(expected_bytes)
    return {
        "event": str(event["event"]),
        "presentation_samples": samples,
        "byte_count": expected_bytes,
        "sha256": file_sha256(output),
        "verified_digital_silence": True,
    }


def hardlink_or_copy(source: Path, target: Path) -> str:
    """Create a cross-edition alias without hiding a filesystem fallback."""

    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def is_aac_silence_floor(volume: Mapping[str, Any]) -> bool:
    """Accept only digital silence or the deterministic AAC encoder noise floor."""

    value = str(volume.get("max_volume_db", "")).lower()
    if value == "-inf":
        return True
    try:
        return float(value) <= -90.0
    except ValueError:
        return False


def validate_no_exact_audience_event_duplicates(
    family: str,
    events: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Reject exact repeated AV+dialogue units in one audience-facing series.

    Single-event archival outputs remain untouched.  A family proposal must
    remove the repeated occurrence (while preserving its provenance outside the
    audience cut) before it can be promoted as one long-form viewing product.
    """

    signatures: list[dict[str, str]] = []
    events_by_signature: dict[str, list[str]] = {}
    for event in events:
        event_name = str(event.get("event", "")).strip()
        clean_visual = Path(str(event.get("clean_visual", ""))).resolve()
        if not event_name or not clean_visual.is_file():
            raise RuntimeError(
                f"{family} cannot audit audience event content: {event_name!r}"
            )
        audio_rows = []
        for layer in event.get("audio_layers", []):
            if not isinstance(layer, Mapping):
                raise RuntimeError(f"{event_name} has an invalid audio layer")
            source = layer.get("source")
            if not isinstance(source, Mapping):
                raise RuntimeError(
                    f"{event_name} audio layer lacks a source snapshot"
                )
            audio_rows.append(
                {
                    "role": str(layer.get("role", "")),
                    "request_id": str(layer.get("request_id", "")),
                    "source_sha256": str(source.get("sha256", "")).upper(),
                    "start_ms": int(layer.get("start_ms", -1)),
                    "duration_ms": int(layer.get("duration_ms", -1)),
                }
            )
        cue_rows = []
        for cue in event.get("dialogue_cues", []):
            if not isinstance(cue, Mapping):
                raise RuntimeError(f"{event_name} has an invalid dialogue cue")
            cue_rows.append(
                {
                    "request_id": str(cue.get("request_id", "")),
                    "start_ms": int(cue.get("start_ms", -1)),
                    "end_ms": int(cue.get("end_ms", -1)),
                    "ja_text": str(cue.get("ja_text", "")),
                    "zh_text": str(cue.get("zh_text", "")),
                    "speaker_code": str(cue.get("speaker_code", "")),
                }
            )
        signature = canonical_sha256(
            {
                "clean_visual_sha256": file_sha256(clean_visual),
                "width": int(event.get("width", 0)),
                "height": int(event.get("height", 0)),
                "frame_count": int(event.get("frame_count", 0)),
                "presentation_samples": int(event.get("presentation_samples", 0)),
                "audio_layers": sorted(
                    audio_rows,
                    key=lambda row: (
                        row["start_ms"],
                        row["request_id"],
                        row["role"],
                        row["source_sha256"],
                        row["duration_ms"],
                    ),
                ),
                "dialogue_cues": sorted(
                    cue_rows,
                    key=lambda row: (
                        row["start_ms"],
                        row["end_ms"],
                        row["request_id"],
                        row["ja_text"],
                        row["zh_text"],
                        row["speaker_code"],
                    ),
                ),
            }
        )
        signatures.append({"event": event_name, "content_sha256": signature})
        events_by_signature.setdefault(signature, []).append(event_name)

    duplicate_groups = [
        names for names in events_by_signature.values() if len(names) > 1
    ]
    if duplicate_groups:
        raise RuntimeError(
            f"{family} audience series contains exact repeated AV+subtitle "
            f"events; use a deduplicated route-aware proposal: {duplicate_groups}"
        )
    return signatures


def _media_audit(
    path: Path,
    *,
    total_frames: int,
    total_samples: int,
    width: int,
    height: int,
    audio_master: Path,
    master_timeline: Mapping[str, Any],
    master_pcm: Mapping[str, Any],
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    value = probe(path, ffprobe)
    videos = media_streams(value, "video")
    audios = media_streams(value, "audio")
    if len(videos) != 1 or len(audios) != 1 or media_streams(value, "subtitle"):
        raise RuntimeError(f"edition stream contract failed: {path}")
    video = videos[0]
    audio = audios[0]
    if (
        video.get("codec_name") != "h264"
        or frame_count(video) != total_frames
        or int(video.get("width", 0)) != width
        or int(video.get("height", 0)) != height
        or video.get("r_frame_rate") != "30/1"
        or audio.get("codec_name") != "aac"
        or int(audio.get("sample_rate", 0)) != 48000
        or int(audio.get("channels", 0)) != 2
    ):
        raise RuntimeError(f"edition native media contract failed: {path}")
    timeline = audio_gate._audio_packet_timeline(
        output=path,
        audio_stream=audio,
        expected_samples=total_samples,
        ffprobe=ffprobe,
    )
    decoded_pcm = audio_gate._effective_decoded_pcm_audit(
        output=path, expected_samples=total_samples, ffmpeg=ffmpeg
    )
    if timeline != master_timeline or decoded_pcm != master_pcm:
        raise RuntimeError(f"edition audio presentation differs from master: {path}")
    master_packets = packet_hash(audio_master, kind="audio", ffmpeg=ffmpeg)
    edition_packets = packet_hash(path, kind="audio", ffmpeg=ffmpeg)
    if edition_packets != master_packets:
        raise RuntimeError(f"edition AAC packets differ from master: {path}")
    return {
        "frame_count": total_frames,
        "video_bit_rate": stream_bit_rate(video, label=f"{path.name} video"),
        "audio_bit_rate": stream_bit_rate(audio, label=f"{path.name} audio"),
        "audio_packet_sha256": edition_packets,
        "audio_timeline": timeline,
        "decoded_pcm": decoded_pcm,
    }


def build_family_editions(
    family: str,
    events: Sequence[Mapping[str, Any]],
    *,
    editions: Sequence[str],
    out_root: Path,
    layout: Mapping[str, Any],
    bilingual_layout: Mapping[str, Any] | None,
    font_path: Path,
    speakers: Mapping[str, Mapping[str, str]],
    source_snapshots: Sequence[Mapping[str, str]],
    audio_role_overrides: Sequence[Mapping[str, str]],
    voice_subtitle_overrides: Sequence[Mapping[str, str]] = (),
    speaker_identity_overrides: Sequence[Mapping[str, str]] = (),
    series_binding: Mapping[str, Any],
    audience_event_content_signatures: Sequence[Mapping[str, str]],
    relationship_rule_audit: Sequence[Mapping[str, Any]],
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> Path:
    selected = normalize_editions(editions)
    if [str(row.get("event", "")) for row in audience_event_content_signatures] != [
        str(event.get("event", "")) for event in events
    ]:
        raise RuntimeError(f"{family} audience event signature order differs")
    retained_role_counts = {"voice": 0, "scene_se": 0}
    verified_silent_events: list[str] = []
    for event in events:
        event_name = str(event.get("event", ""))
        layers = event.get("audio_layers")
        if not isinstance(layers, list):
            raise RuntimeError(
                f"{event_name} has invalid retained evidence-bound audio layers"
            )
        if not layers:
            if (
                event.get("verified_no_event_audio") is not True
                or not isinstance(event.get("audio_absence_evidence"), Mapping)
            ):
                raise RuntimeError(
                    f"{event_name} has no retained evidence-bound audio layers"
                )
            verified_silent_events.append(event_name)
            continue
        roles = [str(layer.get("role", "")) for layer in layers]
        invalid_roles = sorted(set(roles) - set(retained_role_counts))
        if invalid_roles:
            raise RuntimeError(
                f"{event_name} contains unresolved audio roles: {invalid_roles}"
            )
        for role in roles:
            retained_role_counts[role] += 1
    dimension_set = {(int(event["width"]), int(event["height"])) for event in events}
    if len(dimension_set) != 1:
        raise RuntimeError(f"{family} mixes native dimensions: {sorted(dimension_set)}")
    width, height = next(iter(dimension_set))
    if (int(layout.get("target_width", 0)), int(layout.get("target_height", 0))) != (
        width,
        height,
    ):
        raise RuntimeError(f"{family} lacks an exact native-size standard layout")
    if "ja_zh" in selected and (
        bilingual_layout is None
        or (
            int(bilingual_layout.get("target_width", 0)),
            int(bilingual_layout.get("target_height", 0)),
        )
        != (width, height)
    ):
        raise RuntimeError(f"{family} lacks an exact native-size bilingual layout")

    release_id = validate_output_identifier(
        f"{family}_full_no_bgm_editions_v1", label="family release id"
    )
    destination = resolve_output_child(out_root, release_id, label="family release")
    staging = resolve_output_child(
        out_root, f".{release_id}.staging.{uuid.uuid4().hex}", label="family staging"
    )
    staging.mkdir(parents=True)
    work = staging / "work"
    work.mkdir()
    try:
        staged_font_dir = work / "fonts"
        staged_font_dir.mkdir()
        staged_font = staged_font_dir / font_path.name
        shutil.copy2(font_path, staged_font)

        event_pcm_paths: list[Path] = []
        pcm_audits: list[dict[str, Any]] = []
        total_frames = 0
        total_samples = 0
        base_cues: list[dict[str, Any]] = []
        timeline: list[dict[str, Any]] = []
        for event in events:
            event_pcm = work / f"{event['event']}.f32le"
            pcm_audits.append(
                build_event_pcm_or_verified_silence(
                    event, output=event_pcm, ffmpeg=ffmpeg
                )
            )
            event_pcm_paths.append(event_pcm)
            start_frame = total_frames
            start_sample = total_samples
            offset_ms = round(Fraction(start_sample * 1000, 48000))
            for cue in event["dialogue_cues"]:
                base_cues.append(
                    {
                        "start_ms": offset_ms + int(cue["start_ms"]),
                        "end_ms": offset_ms + int(cue["end_ms"]),
                        "event": str(event["event"]),
                        "request_id": str(cue["request_id"]),
                        "ja_text": str(cue["ja_text"]),
                        "zh_text": str(cue["zh_text"]),
                        "speaker_code": str(cue.get("speaker_code", "")),
                        "subtitle_source": str(cue.get("subtitle_source", "")),
                        "evidence": str(cue.get("evidence", "")),
                    }
                )
            total_frames += int(event["frame_count"])
            total_samples += int(event["presentation_samples"])
            timeline.append(
                {
                    "event": str(event["event"]),
                    "start_frame": start_frame,
                    "end_frame": total_frames,
                    "start_sample": start_sample,
                    "end_sample": total_samples,
                    "inserted_gap_frames": 0,
                }
            )
        if total_samples != total_frames * 1600:
            raise RuntimeError("family frame/sample grids differ")

        scene_pcm = work / "scene.f32le"
        concat_binary(event_pcm_paths, scene_pcm)
        if scene_pcm.stat().st_size != total_samples * 8:
            raise RuntimeError("family PCM byte count mismatch")
        scene_pcm_hash = file_sha256(scene_pcm)

        masters = staging / "masters"
        masters.mkdir()
        audio_master = masters / f"{release_id}__no_bgm_audio_master.m4a"
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "f32le",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-i",
                str(scene_pcm),
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
                str(audio_master),
            ]
        )
        audio_probe = probe(audio_master, ffprobe)
        audio_stream = media_streams(audio_probe, "audio")[0]
        master_timeline = audio_gate._audio_packet_timeline(
            output=audio_master,
            audio_stream=audio_stream,
            expected_samples=total_samples,
            ffprobe=ffprobe,
        )
        master_pcm = audio_gate._effective_decoded_pcm_audit(
            output=audio_master, expected_samples=total_samples, ffmpeg=ffmpeg
        )
        master_packet_hash = packet_hash(audio_master, kind="audio", ffmpeg=ffmpeg)

        concat_file = work / "visuals.ffconcat"
        concat_file.write_text(
            "ffconcat version 1.0\n"
            + "".join(
                f"file '{ffconcat_quote(Path(event['clean_visual']))}'\n" for event in events
            ),
            encoding="utf-8",
        )
        clean_scene = masters / f"{release_id}__clean_visual_master.mp4"
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-an",
                "-c:v",
                "copy",
                "-movflags",
                "+faststart",
                str(clean_scene),
            ]
        )
        clean_probe = probe(clean_scene, ffprobe)
        clean_videos = media_streams(clean_probe, "video")
        if len(clean_videos) != 1:
            raise RuntimeError("family clean visual stream contract failed")
        clean_video = clean_videos[0]
        if (
            clean_video.get("codec_name") != "h264"
            or frame_count(clean_video) != total_frames
            or int(clean_video.get("width", 0)) != width
            or int(clean_video.get("height", 0)) != height
            or clean_video.get("r_frame_rate") != "30/1"
            or media_streams(clean_probe, "audio")
        ):
            raise RuntimeError("family clean visual grid mismatch")

        subtitle_dir = staging / "subtitles"
        subtitle_dir.mkdir()
        subtitle_paths: dict[str, Path] = {}
        edition_cue_rows: dict[str, list[dict[str, Any]]] = {}
        no_dialogue_aliases = not base_cues
        if not no_dialogue_aliases:
            for edition in selected:
                if edition not in SUBTITLE_EDITIONS:
                    continue
                rows = edition_cues(base_cues, edition, speakers)
                path = subtitle_dir / f"{release_id}__{edition}.srt"
                assert_srt_round_trip(path, rows)
                subtitle_paths[edition] = path
                edition_cue_rows[edition] = rows

        video_dir = staging / "video"
        video_dir.mkdir()
        video_paths: dict[str, Path] = {}
        media_audits: dict[str, dict[str, Any]] = {}
        edition_alias_modes: dict[str, str] = {}
        canonical_silent_edition = selected[0] if no_dialogue_aliases else ""
        for edition in selected:
            output = video_dir / f"{release_id}__{edition}.mp4"
            if no_dialogue_aliases and edition != canonical_silent_edition:
                source = video_paths[canonical_silent_edition]
                edition_alias_modes[edition] = hardlink_or_copy(source, output)
            elif edition == "none" or no_dialogue_aliases:
                command = [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    clean_scene.relative_to(staging).as_posix(),
                    "-i",
                    audio_master.relative_to(staging).as_posix(),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    output.relative_to(staging).as_posix(),
                ]
                run(command, cwd=staging)
                if no_dialogue_aliases:
                    edition_alias_modes[edition] = "canonical"
            else:
                selected_layout = bilingual_layout if edition == "ja_zh" else layout
                assert selected_layout is not None
                filter_value = subtitle_filter(
                    selected_layout,
                    srt_path=subtitle_paths[edition].relative_to(staging).as_posix(),
                    fonts_dir=staged_font_dir.relative_to(staging).as_posix(),
                )
                command = [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    clean_scene.relative_to(staging).as_posix(),
                    "-i",
                    audio_master.relative_to(staging).as_posix(),
                    "-vf",
                    filter_value,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "14",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    "-frames:v",
                    str(total_frames),
                    "-movflags",
                    "+faststart",
                    output.relative_to(staging).as_posix(),
                ]
                run(command, cwd=staging)
            video_paths[edition] = output
            media_audits[edition] = _media_audit(
                output,
                total_frames=total_frames,
                total_samples=total_samples,
                width=width,
                height=height,
                audio_master=audio_master,
                master_timeline=master_timeline,
                master_pcm=master_pcm,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )

        if {row["audio_packet_sha256"] for row in media_audits.values()} != {
            master_packet_hash
        }:
            raise RuntimeError("selected editions do not share one AAC packet identity")
        volume = volume_audit(audio_master, ffmpeg)
        exact_all_event_silence = len(verified_silent_events) == len(events)
        if (
            str(volume["max_volume_db"]).lower() == "-inf"
            and not exact_all_event_silence
        ):
            raise RuntimeError("family no-BGM audio master is silent")
        if exact_all_event_silence and not is_aac_silence_floor(volume):
            raise RuntimeError(
                "evidence-bound silent family produced non-silent audio"
            )

        review_dir = staging / "review"
        review_dir.mkdir()
        review_form = review_dir / "HUMAN_PLAYBACK_REVIEW.md"
        dialogue_review_note = (
            "- [ ] 本事件经三套哈希绑定目录证明没有事件对白、SE或字幕；"
            "none/JA/ZH 是面向不同目标轨的同内容别名\n"
            if no_dialogue_aliases
            else "- [ ] 日文、中文及已选择的中日对照版内容正确\n"
        )
        review_form.write_text(
            f"# {family} 无 BGM 多版本人工播放审查\n\n"
            f"版本：{', '.join(selected)}\n\n"
            f"事件数：{len(events)}；对白 cue：{len(base_cues)}；BGM：有意排除。\n\n"
            "- [ ] 无字幕版没有字幕或字幕流\n"
            f"{dialogue_review_note}"
            "- [ ] 有可靠说话人证据时姓名前缀正确；多人或未知说话人不加前缀\n"
            "- [ ] 事件顺序、画面、voice、SE、循环与边界正确\n"
            "- [ ] 所有版本保持原生分辨率和 30 fps，无 upscale\n"
            "- [ ] 所有版本音画同步且没有意外 BGM\n\n"
            "```text\nHUMAN_PLAYBACK_APPROVED =\n需要修改：\n```\n",
            encoding="utf-8",
        )

        shutil.rmtree(work)
        rehash(source_snapshots)
        qa_path = staging / "qa" / "automated_qa.json"
        qa = {
            "schema": QA_SCHEMA,
            "status": "passed",
            "family": family,
            "selected_editions": list(selected),
            "checks": {
                "source_hashes_unchanged": True,
                "all_events_technical_ready": True,
                "clean_visual_master_shared": True,
                "no_bgm_layers_present": True,
                "retained_audio_roles_are_evidence_bound_voice_or_scene_se": True,
                "unresolved_audio_layer_count_zero": True,
                "audio_role_overrides_exact_hash_bound": True,
                "voice_subtitle_overrides_exact_hash_bound": True,
                "ambiguous_speaker_identities_exact_hash_bound": True,
                "zero_inserted_black_frames": True,
                "native_dimensions_30fps_no_upscale": True,
                "exact_frame_and_sample_grid": True,
                "aac_encoded_once_and_packet_identical": True,
                "selected_srt_files_round_trip": True,
                "verified_silent_audio_only_when_exact_absence_bound": (
                    (exact_all_event_silence and is_aac_silence_floor(volume))
                    or (
                        not exact_all_event_silence
                        and str(volume["max_volume_db"]).lower() != "-inf"
                    )
                ),
                "no_dialogue_cross_target_aliases_audited": (
                    not no_dialogue_aliases
                    or set(edition_alias_modes) == set(selected)
                ),
                "speaker_prefix_requires_cue_evidence": True,
                "series_proposal_current_identity_bound": True,
                "no_exact_duplicate_audience_events": True,
                "dialogue_relationship_rules_enforced": True,
                "human_and_publication_status_false": True,
            },
            "events": [str(event["event"]) for event in events],
            "timeline": timeline,
            "total_frames": total_frames,
            "total_presentation_samples": total_samples,
            "duration_ms": round(Fraction(total_samples * 1000, 48000)),
            "dialogue_cue_count": len(base_cues),
            "audio_layer_count": sum(len(event["audio_layers"]) for event in events),
            "audio_role_counts": {
                **retained_role_counts,
                "unsubtitled_audio": 0,
            },
            "verified_no_event_audio_events": list(verified_silent_events),
            "edition_alias_modes": dict(edition_alias_modes),
            "applied_audio_role_overrides": list(audio_role_overrides),
            "applied_voice_subtitle_overrides": list(voice_subtitle_overrides),
            "applied_speaker_identity_overrides": list(
                speaker_identity_overrides
            ),
            "series_proposal_binding": dict(series_binding),
            "audience_event_content_signatures": list(
                audience_event_content_signatures
            ),
            "dialogue_relationship_rule_audit": list(relationship_rule_audit),
            "source_scene_pcm_f32le_sha256": scene_pcm_hash,
            "audio_master_packet_sha256": master_packet_hash,
            "audio_master_timeline": master_timeline,
            "audio_master_decoded_pcm": master_pcm,
            "edition_media_audits": media_audits,
            "event_pcm_audits": pcm_audits,
            "volume": volume,
            "warnings": [
                "These are automated expansion candidates, not owner-approved releases.",
                (
                    "BGM is intentionally excluded; events with audio retain only "
                    "verified voice/scene SE, while exact-silent events carry only "
                    "a 48 kHz stereo silence presentation track (AAC decoder "
                    "floor no higher than -90 dBFS)."
                ),
                "Human playback and Bilibili publication approval remain false.",
            ],
        }
        write_json(qa_path, qa)

        artifacts: dict[str, dict[str, str]] = {
            "qa": {
                "path": qa_path.relative_to(staging).as_posix(),
                "sha256": file_sha256(qa_path),
            },
            "review_form": {
                "path": review_form.relative_to(staging).as_posix(),
                "sha256": file_sha256(review_form),
            },
            "clean_visual_master": {
                "path": clean_scene.relative_to(staging).as_posix(),
                "sha256": file_sha256(clean_scene),
            },
            "no_bgm_audio_master": {
                "path": audio_master.relative_to(staging).as_posix(),
                "sha256": file_sha256(audio_master),
            },
        }
        for edition, path in video_paths.items():
            artifacts[f"video_{edition}"] = {
                "path": path.relative_to(staging).as_posix(),
                "sha256": file_sha256(path),
            }
        for edition, path in subtitle_paths.items():
            artifacts[f"subtitles_{edition}"] = {
                "path": path.relative_to(staging).as_posix(),
                "sha256": file_sha256(path),
            }

        manifest_path = staging / "manifests" / "family_editions_manifest.json"
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": "AUTOMATED_QA_PASSED",
            "release_id": release_id,
            "family": family,
            "release_scope": str(
                series_binding.get(
                    "product_scope",
                    "no_bgm_family_expansion_candidates",
                )
            ),
            "audio_profile": "no_bgm",
            "selected_editions": list(selected),
            "subtitle_profiles": {
                "none": "none",
                "ja": (
                    "no_dialogue_cross_target_alias"
                    if no_dialogue_aliases
                    else "ja_voice_bound_dialogue"
                ),
                "zh": (
                    "no_dialogue_cross_target_alias"
                    if no_dialogue_aliases
                    else "zh_voice_bound_dialogue"
                ),
                "ja_zh": (
                    "no_dialogue_cross_target_alias"
                    if no_dialogue_aliases
                    else "ja_above_zh_voice_bound_dialogue"
                ),
            },
            "bgm_policy": "intentionally_excluded",
            "voice_se_policy": "preserve_verified_evidence_bound_original",
            "translation_status": "machine_draft_pending_owner",
            "human_review_status": "pending",
            "publishable": False,
            "readiness": {
                "AUTOMATED_QA_PASSED": True,
                "HUMAN_PLAYBACK_APPROVED": False,
                "BILIBILI_RELEASE_READY": False,
            },
            "ordered_events": [str(event["event"]) for event in events],
            "timeline": timeline,
            "media": {
                "duration_ms": round(Fraction(total_samples * 1000, 48000)),
                "width": width,
                "height": height,
                "frame_rate": "30/1",
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": 48000,
                "audio_channels": 2,
                "upscaled": False,
                "edition_video_bit_rates": {
                    key: row["video_bit_rate"] for key, row in media_audits.items()
                },
            },
            "dialogue_cue_count": len(base_cues),
            "verified_no_event_audio_events": list(verified_silent_events),
            "edition_alias_modes": dict(edition_alias_modes),
            "source_snapshots": list(source_snapshots),
            "applied_audio_role_overrides": list(audio_role_overrides),
            "applied_voice_subtitle_overrides": list(voice_subtitle_overrides),
            "applied_speaker_identity_overrides": list(
                speaker_identity_overrides
            ),
            "series_proposal_binding": dict(series_binding),
            "audience_event_content_signatures": list(
                audience_event_content_signatures
            ),
            "dialogue_relationship_rule_audit": list(relationship_rule_audit),
            "artifacts": artifacts,
        }
        if "product_scope" in series_binding:
            manifest["product_scope"] = str(series_binding["product_scope"])
            manifest["natural_session_claimed"] = False
            manifest["loop_scope"] = dict(series_binding["loop_scope"])
        write_json(manifest_path, manifest)
        marker_artifacts = dict(artifacts)
        marker_artifacts["manifest"] = {
            "path": manifest_path.relative_to(staging).as_posix(),
            "sha256": file_sha256(manifest_path),
        }
        marker = {
            "schema": READY_SCHEMA,
            "status": "AUTOMATED_QA_PASSED",
            "release_id": release_id,
            "family": family,
            "selected_editions": list(selected),
            "publishable": False,
            "readiness": {
                "AUTOMATED_QA_PASSED": True,
                "HUMAN_PLAYBACK_APPROVED": False,
                "BILIBILI_RELEASE_READY": False,
            },
            **(
                {
                    "product_scope": str(series_binding["product_scope"]),
                    "natural_session_claimed": False,
                    "loop_scope": dict(series_binding["loop_scope"]),
                }
                if "product_scope" in series_binding
                else {}
            ),
            "artifacts": marker_artifacts,
            "artifact_set_sha256": canonical_sha256(marker_artifacts),
        }
        write_json(staging / "BATCH_REVIEW_READY.json", marker)
        rehash(source_snapshots)
        promote(staging, destination, out_root, overwrite=overwrite)
        return destination
    except Exception:
        if staging.exists() and os.environ.get("MAGIRECO_KEEP_FAILED_STAGING") != "1":
            shutil.rmtree(staging)
        elif staging.exists():
            print(f"retained failed staging for diagnosis: {staging}", file=sys.stderr)
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--series-root")
    parser.add_argument(
        "--series-manifest",
        action="append",
        metavar="FAMILY=PATH",
        help="explicit passed family ordering manifest; repeat for a mixed batch",
    )
    parser.add_argument("--translation-map", required=True)
    parser.add_argument(
        "--dialogue-relationship-rules",
        default=str(Path(__file__).with_name("dialogue_relationship_rules_v1.json")),
    )
    parser.add_argument("--layout-profile", action="append", required=True)
    parser.add_argument("--bilingual-layout-profile", action="append")
    parser.add_argument("--speaker-registry")
    parser.add_argument(
        "--speaker-identity-overrides",
        default=str(Path(__file__).with_name("speaker_identity_overrides_v1.json")),
    )
    parser.add_argument("--audio-role-overrides")
    parser.add_argument("--voice-subtitle-overrides")
    parser.add_argument(
        "--edition",
        action="append",
        choices=SUPPORTED_EDITIONS,
        help="repeat to choose editions; default: none, ja, zh",
    )
    parser.add_argument("--font", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--renderer", required=True)
    parser.add_argument("--family", action="append")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def validate_series_proposal_bindings(
    *,
    family: str,
    series: Mapping[str, Any],
    series_path: Path,
    manifest_root: Path,
    ordered_events: Sequence[str],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Bind a passed ordering proposal to its exact current evidence inputs."""

    family_state = series.get("family_state")
    event_hashes = series.get("event_manifest_sha256")
    source_row = series.get("source_series_manifest")
    if not isinstance(family_state, Mapping):
        raise ValueError(f"{family} series proposal lacks family_state")
    if not isinstance(event_hashes, Mapping):
        raise ValueError(f"{family} series proposal lacks event_manifest_sha256")
    if not isinstance(source_row, Mapping) or set(source_row) != {
        "path",
        "sha256",
        "evidence",
    }:
        raise ValueError(f"{family} series proposal lacks source_series_manifest")

    declared_root = Path(str(family_state.get("production_manifest_root", "")))
    if not str(declared_root):
        raise ValueError(f"{family} series proposal lacks production manifest root")
    if not declared_root.is_absolute():
        declared_root = series_path.parent / declared_root
    try:
        if not os.path.samefile(declared_root.resolve(), manifest_root.resolve()):
            raise ValueError(
                f"{family} series proposal production manifest root differs"
            )
    except OSError as error:
        raise ValueError(
            f"{family} series proposal production manifest root is inaccessible"
        ) from error

    ordered = list(ordered_events)
    if len(set(ordered)) != len(ordered):
        raise ValueError(f"{family} series proposal contains duplicate events")
    if set(event_hashes) != set(ordered):
        raise ValueError(
            f"{family} series proposal event_manifest_sha256 keys differ"
        )
    current_event_hashes: dict[str, str] = {}
    for event in ordered:
        expected = str(event_hashes[event]).strip().upper()
        if len(expected) != 64 or any(
            character not in "0123456789ABCDEF" for character in expected
        ):
            raise ValueError(
                f"{family} series proposal event manifest SHA-256 is invalid: {event}"
            )
        event_path = manifest_root / "events" / f"{event}.json"
        if not event_path.is_file():
            raise FileNotFoundError(
                f"{family} current event manifest is missing: {event_path}"
            )
        actual = file_sha256(event_path)
        if actual != expected:
            raise ValueError(
                f"{family} current event manifest SHA-256 differs: {event}"
            )
        current_event_hashes[event] = actual

    source_path = Path(str(source_row["path"]))
    if not source_path.is_absolute():
        source_path = series_path.parent / source_path
    source_path = source_path.resolve()
    expected_source_hash = str(source_row["sha256"]).strip().upper()
    if (
        not str(source_row["evidence"]).strip()
        or len(expected_source_hash) != 64
        or any(
            character not in "0123456789ABCDEF"
            for character in expected_source_hash
        )
        or not source_path.is_file()
        or file_sha256(source_path) != expected_source_hash
    ):
        raise ValueError(f"{family} source series manifest SHA-256 differs")
    source_series = read_json(source_path)
    source_events = source_series.get("family_state", {}).get("ready_event_names")
    base_families = {event.split("_", 1)[0] for event in ordered}
    if (
        source_series.get("schema") != "magireco-series-editions-v1"
        or source_series.get("status") != "passed"
        or len(base_families) != 1
        or source_series.get("series") != next(iter(base_families))
        or not isinstance(source_events, list)
        or len(set(source_events)) != len(source_events)
    ):
        raise ValueError(f"{family} source series manifest identity differs")
    source_positions = {event: index for index, event in enumerate(source_events)}
    if any(event not in source_positions for event in ordered) or [
        source_positions[event] for event in ordered
    ] != sorted(source_positions[event] for event in ordered):
        raise ValueError(f"{family} ordering is not an upstream ordered subsequence")

    bounded_scope: dict[str, Any] = {}
    if "natural_session_claimed" in series or "loop_scope" in series:
        product_scope = str(series["product_scope"]).strip()
        natural_session_claimed = series.get("natural_session_claimed")
        loop_scope = series.get("loop_scope")
        source_product_scopes = source_series.get("product_scopes")
        source_natural_claims = source_series.get("natural_session_claims")
        if (
            not product_scope
            or natural_session_claimed is not False
            or not isinstance(loop_scope, Mapping)
            or not isinstance(source_product_scopes, Mapping)
            or not isinstance(source_natural_claims, Mapping)
            or any(
                source_product_scopes.get(event) != product_scope
                or source_natural_claims.get(event) is not False
                for event in ordered
            )
        ):
            raise ValueError(f"{family} bounded product scope binding differs")
        bounded_scope = {
            "product_scope": product_scope,
            "natural_session_claimed": False,
            "loop_scope": dict(loop_scope),
        }

    source_snapshot = snapshot(
        source_path, label=f"{family} hash-bound source series manifest"
    )
    dirinfo_snapshot = validate_dirinfo_source_evidence(
        source_series=source_series,
        source_path=source_path,
    )
    return (
        {
            "status": "current_identity_bound",
            "production_manifest_root": str(manifest_root.resolve()),
            "event_manifest_sha256": current_event_hashes,
            "source_series_manifest": {
                "path": str(source_path),
                "sha256": expected_source_hash,
            },
            **bounded_scope,
        },
        [
            source_snapshot,
            *([dirinfo_snapshot] if dirinfo_snapshot else []),
        ],
    )


def validate_dirinfo_source_evidence(
    *,
    source_series: Mapping[str, Any],
    source_path: Path,
) -> dict[str, str] | None:
    """Validate an optional exact DirInfo row catalog behind a source series."""

    raw = source_series.get("dirinfo_evidence")
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or set(raw) != {
        "path",
        "sha256",
        "kind",
        "rows",
    }:
        raise ValueError("source series DirInfo evidence fields differ")
    path = Path(str(raw["path"]))
    if not path.is_absolute():
        path = source_path.parent / path
    path = path.resolve()
    expected_sha256 = str(raw["sha256"]).strip().upper()
    if (
        len(expected_sha256) != 64
        or any(value not in "0123456789ABCDEF" for value in expected_sha256)
        or not path.is_file()
        or file_sha256(path) != expected_sha256
    ):
        raise ValueError("source series DirInfo evidence SHA-256 differs")
    kind = int(raw["kind"])
    declarations = raw["rows"]
    if not isinstance(declarations, list) or not declarations:
        raise ValueError("source series DirInfo evidence has no rows")
    required = {"row_index", "event", "event_info_index", "code_hex"}
    expected_rows: dict[int, dict[str, str]] = {}
    for index, row in enumerate(declarations):
        if not isinstance(row, Mapping) or set(row) != required:
            raise ValueError(f"source series DirInfo row {index} fields differ")
        row_index = int(row["row_index"])
        event = str(row["event"])
        if (
            row_index in expected_rows
            or not re.fullmatch(r"ac\d+_\d+", event)
        ):
            raise ValueError(f"source series DirInfo row {index} is invalid")
        expected_rows[row_index] = {
            "event": event,
            "event_info_index": str(int(row["event_info_index"])),
            "code_hex": str(row["code_hex"]).casefold(),
        }
    actual_rows: dict[int, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if int(row["kind"]) != kind:
                continue
            row_index = int(row["row_index"])
            if row_index not in expected_rows:
                continue
            actual_rows[row_index] = {
                "event": str(row["resolved_events"] or row["scene_name"]),
                "event_info_index": str(int(row["event_info_index"])),
                "code_hex": str(row["code_hex"]).casefold(),
            }
    if actual_rows != expected_rows:
        raise ValueError(
            "source series DirInfo rows differ: "
            f"expected={expected_rows} actual={actual_rows}"
        )
    source_events = source_series.get("family_state", {}).get(
        "ready_event_names"
    )
    if source_events != [
        expected_rows[index]["event"] for index in sorted(expected_rows)
    ]:
        raise ValueError("source series event order differs from DirInfo rows")
    return snapshot(path, label="hash-bound DirInfo event route catalog")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    editions = normalize_editions(args.edition)
    if "ja_zh" in editions and not args.bilingual_layout_profile:
        raise ValueError("ja_zh requires --bilingual-layout-profile")

    manifest_root = Path(args.manifest_root).resolve()
    series_manifests = resolve_series_manifests(args)
    families = list(series_manifests)
    translation_path = Path(args.translation_map).resolve()
    font_path = Path(args.font).resolve()
    renderer_path = Path(args.renderer).resolve()
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    translations, translation_source = load_translation_map(translation_path)
    relationship_rules, relationship_source = load_dialogue_relationship_rules(
        Path(args.dialogue_relationship_rules)
    )
    relationship_rule_audit = validate_translation_relationship_rules(
        translations, relationship_rules
    )
    layouts, layout_sources = load_layout_profiles(args.layout_profile)
    bilingual_layouts: dict[tuple[int, int], dict[str, Any]] = {}
    bilingual_sources: list[dict[str, str]] = []
    if args.bilingual_layout_profile:
        bilingual_layouts, bilingual_sources = load_layout_profiles(
            args.bilingual_layout_profile
        )
    speakers, speaker_source = load_speaker_registry(
        Path(args.speaker_registry).resolve() if args.speaker_registry else None
    )
    speaker_identity_overrides, speaker_identity_source = (
        load_speaker_identity_overrides(
            Path(args.speaker_identity_overrides).resolve()
            if args.speaker_identity_overrides
            else None
        )
    )
    overrides, override_source = load_audio_role_overrides(
        Path(args.audio_role_overrides).resolve() if args.audio_role_overrides else None
    )
    voice_overrides: dict[str, dict[str, Any]] = {}
    voice_override_source: dict[str, str] | None = None
    if args.voice_subtitle_overrides:
        voice_override_path = Path(args.voice_subtitle_overrides).resolve()
        voice_overrides = load_voice_subtitle_overrides([voice_override_path])
        voice_override_source = snapshot(
            voice_override_path,
            label="hash-bound verified voice subtitle overrides",
        )
    shared_sources: list[dict[str, str]] = [
        translation_source,
        relationship_source,
        *layout_sources,
        *bilingual_sources,
        snapshot(font_path, label="audited subtitle font"),
        snapshot(renderer_path, label="clean visual renderer"),
    ]
    if speaker_source:
        shared_sources.append(speaker_source)
    if speaker_identity_source:
        shared_sources.append(speaker_identity_source)
    if override_source:
        shared_sources.append(override_source)
    if voice_override_source:
        shared_sources.append(voice_override_source)

    manifest_out = out_root / "_batch_inputs" / "events"
    plan_out = out_root / "_batch_inputs" / "composition_plans"
    clean_root = out_root / "_event_clean_visuals"
    batch_rows: dict[str, list[dict[str, Any]]] = {}
    family_sources: dict[str, list[dict[str, str]]] = {}
    series_bindings: dict[str, dict[str, Any]] = {}
    for family, series_path in series_manifests.items():
        series = read_json(series_path)
        sources = [
            *shared_sources,
            snapshot(series_path, label=f"{family} series ordering manifest"),
        ]
        if series.get("status") != "passed" or series.get("series") != family:
            raise ValueError(f"{family} series manifest is not passed")
        ordered = series.get("family_state", {}).get("ready_event_names")
        if not isinstance(ordered, list) or len(ordered) != int(series.get("event_count", -1)):
            raise ValueError(f"{family} series ordering is invalid")
        binding, binding_sources = validate_series_proposal_bindings(
            family=family,
            series=series,
            series_path=series_path,
            manifest_root=manifest_root,
            ordered_events=ordered,
        )
        sources.extend(binding_sources)
        series_bindings[family] = binding
        rows: list[dict[str, Any]] = []
        for event_value in ordered:
            event = validate_output_identifier(event_value, label=f"{family} event")
            permitted_forbidden_audio_request_ids = {
                request_id
                for (override_event, request_id), override in overrides.items()
                if override_event == event
                and override["role"] == "exclude_slot_effect"
                and request_id in EXPLICITLY_EXCLUDABLE_SLOT_EFFECT_REQUESTS
            }
            prepared, prepared_path, event_sources = prepare_manifest(
                manifest_root / "events" / f"{event}.json",
                plan_dir=plan_out,
                manifest_dir=manifest_out,
                permitted_forbidden_audio_request_ids=(
                    permitted_forbidden_audio_request_ids
                ),
            )
            sources.extend(event_sources)
            rows.append(
                {
                    "event": event,
                    "prepared": prepared,
                    "prepared_path": prepared_path,
                    "clean_visual": clean_root
                    / event
                    / "clean_visual"
                    / f"{event}__clean_visual.mp4",
                    "clean_report": clean_root / event / "render_manifest.json",
                }
            )
        batch_rows[family] = rows
        family_sources[family] = sources

    applied_by_family: dict[str, list[dict[str, str]]] = {}
    applied_voice_by_family: dict[str, list[dict[str, str]]] = {}
    for family, rows in batch_rows.items():
        applied_rows: list[dict[str, str]] = []
        applied_voice_rows: list[dict[str, str]] = []
        for row in rows:
            projected, applied = apply_audio_role_overrides(
                row["prepared"],
                overrides,
            )
            projected, applied_voice = apply_missing_voice_subtitle_overrides(
                projected,
                voice_overrides,
            )
            row["projected"] = projected
            row["applied_audio_role_overrides"] = applied
            row["applied_voice_subtitle_overrides"] = applied_voice
            applied_rows.extend(applied)
            applied_voice_rows.extend(applied_voice)
            voice_request_ids = {
                str(cue.get("voice_request_id", "")).strip()
                for cue in projected.get("subtitles", [])
                if isinstance(cue, Mapping)
                and str(cue.get("voice_request_id", "")).strip()
            }
            role_rows = [
                {
                    "request_id": str(audio.get("request_id", "")),
                    "code_name": str(audio.get("code_name", "")),
                    "role": scene_audio_role(audio, voice_request_ids),
                }
                for audio in projected.get("audio", [])
                if isinstance(audio, Mapping)
            ]
            unresolved = [
                item for item in role_rows if item["role"] == "unsubtitled_audio"
            ]
            if unresolved:
                raise ValueError(
                    f"{row['event']} contains unresolved unsubtitled audio "
                    f"layers: {unresolved}"
                )
            if role_rows:
                validate_audio_layer_roles(
                    str(row["event"]),
                    [item["role"] for item in role_rows],
                    require_scene_se=False,
                    reject_unsubtitled_audio=True,
                )
            elif not is_evidence_bound_silent_manifest(projected):
                raise ValueError(
                    f"{row['event']} has no retained evidence-bound audio layers"
                )
            audio_request_ids = {
                str(audio.get("request_id", "")).strip()
                for audio in projected.get("audio", [])
                if isinstance(audio, Mapping)
            }
            invalid_unbound_subtitles = [
                {
                    "request_id": str(cue.get("voice_request_id", "")).strip(),
                    "text": str(cue.get("text", "")).strip(),
                    "subtitle_source": str(cue.get("subtitle_source", "")).strip(),
                }
                for cue in projected.get("subtitles", [])
                if isinstance(cue, Mapping)
                and str(cue.get("voice_request_id", "")).strip()
                and str(cue.get("voice_request_id", "")).strip()
                not in audio_request_ids
                and cue.get("subtitle_source") != "graphical_display_text"
            ]
            if invalid_unbound_subtitles:
                raise ValueError(
                    f"{row['event']} contains non-graphical subtitles without "
                    f"voice layers: {invalid_unbound_subtitles}"
                )
        applied_by_family[family] = applied_rows
        applied_voice_by_family[family] = applied_voice_rows
        family_event_names = {str(row["event"]) for row in rows}
        expected_override_keys = {
            key for key in overrides if key[0] in family_event_names
        }
        applied_override_keys = {
            (row["event"], row["request_id"]) for row in applied_rows
        }
        if applied_override_keys != expected_override_keys:
            raise ValueError(
                f"{family} audio-role override application differs: "
                f"expected={sorted(expected_override_keys)}, "
                f"applied={sorted(applied_override_keys)}"
            )

    required_texts = {
        str(cue.get("text", "")).strip()
        for rows in batch_rows.values()
        for event in rows
        for cue in event["projected"].get("subtitles", [])
        if str(cue.get("voice_request_id", "")).strip()
        and str(cue.get("voice_request_id", "")).strip()
        in {
            str(audio.get("request_id", "")).strip()
            for audio in event["projected"].get("audio", [])
            if isinstance(audio, Mapping)
        }
    }
    missing = sorted(required_texts - set(translations))
    if missing:
        raise ValueError(f"translation coverage is missing voice-bound cues: {missing}")
    if args.validate_only:
        print(
            json.dumps(
                {
                    "schema": BATCH_SCHEMA,
                    "status": "validated",
                    "selected_editions": list(editions),
                    "families": {
                        family: {
                            "events": len(rows),
                            "dialogue_cues": sum(
                                1
                                for event in rows
                                for cue in event["projected"].get("subtitles", [])
                                if str(cue.get("voice_request_id", "")).strip()
                            ),
                        }
                        for family, rows in batch_rows.items()
                    },
                    "unused_translation_count": len(set(translations) - required_texts),
                    "dialogue_relationship_rule_audit": relationship_rule_audit,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    for rows in batch_rows.values():
        for row in rows:
            clean_exists = row["clean_visual"].is_file()
            report_exists = row["clean_report"].is_file()
            if clean_exists and report_exists and not args.overwrite:
                validate_reusable_clean_visual(
                    event=row["event"],
                    prepared_path=row["prepared_path"],
                    clean_visual=row["clean_visual"],
                    clean_report=row["clean_report"],
                )
                continue
            if clean_exists != report_exists and not args.overwrite:
                raise RuntimeError(
                    f"{row['event']} existing clean-visual release is incomplete; "
                    "rerun with --overwrite"
                )
            command = [
                sys.executable,
                str(renderer_path),
                "--manifest",
                str(row["prepared_path"]),
                "--out-root",
                str(clean_root),
                "--clean-visual-only",
                "--ffmpeg",
                args.ffmpeg,
                "--ffprobe",
                args.ffprobe,
            ]
            if args.overwrite:
                command.append("--overwrite")
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            validate_reusable_clean_visual(
                event=row["event"],
                prepared_path=row["prepared_path"],
                clean_visual=row["clean_visual"],
                clean_report=row["clean_report"],
            )

    resolved_by_family: dict[str, list[dict[str, Any]]] = {}
    content_signatures_by_family: dict[str, list[dict[str, str]]] = {}
    applied_speaker_identities_by_family: dict[str, list[dict[str, str]]] = {}
    for family, rows in batch_rows.items():
        resolved_rows: list[dict[str, Any]] = []
        applied_speaker_identities: list[dict[str, str]] = []
        for row in rows:
            resolved, sources = resolve_story_event(
                row["projected"],
                clean_visual=row["clean_visual"],
                clean_report=row["clean_report"],
                translations=translations,
                reject_unsubtitled_audio=True,
            )
            attach_speaker_evidence(resolved, row["projected"])
            applied_speaker_identities.extend(
                apply_speaker_identity_overrides(
                    resolved,
                    row["projected"],
                    speaker_identity_overrides,
                )
            )
            resolved_rows.append(resolved)
            family_sources[family].extend(sources)
        selected_events = {str(row["event"]) for row in rows}
        expected_identity_keys = {
            key
            for key in speaker_identity_overrides
            if key[0] in selected_events
        }
        applied_identity_keys = {
            (
                row["event"],
                row["request_id"],
                row["raw_speaker_code"],
            )
            for row in applied_speaker_identities
        }
        if applied_identity_keys != expected_identity_keys:
            raise ValueError(
                f"{family} speaker identity override application differs: "
                f"expected={sorted(expected_identity_keys)}, "
                f"applied={sorted(applied_identity_keys)}"
            )
        resolved_by_family[family] = resolved_rows
        applied_speaker_identities_by_family[family] = (
            applied_speaker_identities
        )
        content_signatures_by_family[family] = (
            validate_no_exact_audience_event_duplicates(family, resolved_rows)
        )
        rehash(family_sources[family])

    destinations: list[str] = []
    for family in families:
        dimensions = {
            (int(event["width"]), int(event["height"]))
            for event in resolved_by_family[family]
        }
        if len(dimensions) != 1:
            raise RuntimeError(f"{family} mixes native dimensions")
        dimension = next(iter(dimensions))
        if dimension not in layouts:
            raise RuntimeError(f"{family} lacks one standard native-size layout")
        if "ja_zh" in editions and dimension not in bilingual_layouts:
            raise RuntimeError(f"{family} lacks one bilingual native-size layout")
        destination = build_family_editions(
            family,
            resolved_by_family[family],
            editions=editions,
            out_root=out_root,
            layout=layouts[dimension],
            bilingual_layout=bilingual_layouts.get(dimension),
            font_path=font_path,
            speakers=speakers,
            source_snapshots=family_sources[family],
            audio_role_overrides=applied_by_family[family],
            voice_subtitle_overrides=applied_voice_by_family[family],
            speaker_identity_overrides=(
                applied_speaker_identities_by_family[family]
            ),
            series_binding=series_bindings[family],
            audience_event_content_signatures=content_signatures_by_family[family],
            relationship_rule_audit=relationship_rule_audit,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
            overwrite=args.overwrite,
        )
        destinations.append(str(destination))

    summary = {
        "schema": BATCH_SCHEMA,
        "status": "AUTOMATED_QA_PASSED",
        "selected_editions": list(editions),
        "families": destinations,
        "human_playback_approved": False,
        "bilibili_release_ready": False,
    }
    write_json(out_root / "BATCH_SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
