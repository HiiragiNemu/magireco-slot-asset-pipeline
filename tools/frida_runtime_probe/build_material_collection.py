#!/usr/bin/env python3
"""Build audited material-review collections at native visual resolution."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

try:
    from .output_path_contract import (
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )
except ImportError:  # direct script execution
    from output_path_contract import (  # type: ignore
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )


SOUND_ID_RE = re.compile(r"^(\d{4,5})(?:_|\s|$)")
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
EVENT_NAME_RE = re.compile(r"^ac\d+(?:_\d+)+$")
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
VERIFIED_TRANSCRIPT_SOURCES = frozenset(
    {
        "official_runtime_capture",
        "official_voice_asr_verified",
    }
)
VERIFIED_HUMAN_REVIEW_STATUSES = frozenset(
    {"approved", "human_verified", "verified"}
)
VERIFIED_AUDIO_SEMANTIC_SOURCES = frozenset(
    {
        "official_runtime_capture",
        "verified_static_sound_table",
        "human_reviewed_semantic_map",
    }
)
ROLE_VOICE_SEMANTICS = frozenset(
    {"role_voice", "character_voice", "dialogue", "voice"}
)
NON_DIALOGUE_SEMANTICS = frozenset(
    {
        "bgm",
        "music",
        "sound_effect",
        "se",
        "system",
        "ambient",
        "non_dialogue",
        "digital_silence",
    }
)
NATIVE_VOLUME_UNITS = frozenset(
    {"linear", "percent", "db", "game_percent", "game_index"}
)
VERIFIED_MIX_EVIDENCE_SOURCES = frozenset(
    {
        "official_runtime_capture",
        "verified_static_sound_table",
        "runtime_pre_gate_volume_probe",
        "native_embedded_stream",
    }
)
VISUAL_SEMANTIC_CLASSES = frozenset(
    {"material_effect", "gameplay", "story_animation", "hybrid"}
)
MATERIAL_ROUTE_VISUAL_CLASSES = frozenset({"material_effect", "gameplay"})
VISUAL_SEMANTIC_ALIASES = {
    "material/effect": "material_effect",
    "material-effect": "material_effect",
    "material_effect": "material_effect",
    "material": "material_effect",
    "effect": "material_effect",
    "gameplay": "gameplay",
    "story_animation": "story_animation",
    "story-animation": "story_animation",
    "story animation": "story_animation",
    "hybrid": "hybrid",
}
MATERIAL_SOURCE_SNAPSHOT_SCHEMA = "magireco-material-source-snapshot-v1"
MATERIAL_SOURCE_REHASH_SCHEMA = "magireco-material-source-rehash-v1"


def file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _canonical_sha256(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest().upper()


def _add_material_source_role(
    paths: dict[Path, set[str]], path: Path, role: str
) -> None:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    paths.setdefault(resolved, set()).add(str(role))


def resolve_covered_event_index(
    raw: object,
    *,
    plan_path: Path,
    covered_events: list[str],
    source_roles: dict[Path, set[str]],
    collection: str,
) -> list[dict[str, str]]:
    """Resolve exact event manifests through one hash-bound ledger snapshot."""

    if raw is None:
        return []
    required = {
        "path",
        "sha256",
        "production_state",
        "disposition",
        "native_dimensions",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("named material covered_event_index fields differ")
    index_path = Path(str(raw["path"]))
    if not index_path.is_absolute():
        index_path = plan_path.parent / index_path
    index_path = index_path.resolve()
    expected_index_sha = str(raw["sha256"]).strip().upper()
    if (
        not index_path.is_file()
        or not SHA256_RE.fullmatch(expected_index_sha)
        or file_sha256(index_path) != expected_index_sha
    ):
        raise ValueError("named material covered event index SHA-256 differs")
    _add_material_source_role(
        source_roles,
        index_path,
        f"{collection}:covered_event_index",
    )
    selected: dict[str, dict[str, str]] = {}
    with index_path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            event = str(row.get("event_name", "")).strip()
            if event not in covered_events:
                continue
            if event in selected:
                raise ValueError(
                    f"covered event index contains duplicate event: {event}"
                )
            if (
                str(row.get("production_state", ""))
                != str(raw["production_state"])
                or str(row.get("disposition", ""))
                != str(raw["disposition"])
                or str(row.get("native_dimensions", ""))
                != str(raw["native_dimensions"])
            ):
                raise ValueError(
                    f"covered event index state differs: {event}"
                )
            selected[event] = row
    if set(selected) != set(covered_events):
        raise ValueError(
            "covered event index set differs: "
            f"expected={sorted(covered_events)} actual={sorted(selected)}"
        )
    resolved = [
        {
            "label": "hash-bound exhaustive production event ledger",
            "path": str(index_path),
            "sha256": expected_index_sha,
        }
    ]
    for event in covered_events:
        row = selected[event]
        manifest_path = Path(str(row.get("manifest_path", ""))).resolve()
        expected_manifest_sha = str(
            row.get("manifest_sha256", "")
        ).strip().upper()
        if (
            not manifest_path.is_file()
            or not SHA256_RE.fullmatch(expected_manifest_sha)
            or file_sha256(manifest_path) != expected_manifest_sha
        ):
            raise ValueError(
                f"covered event manifest binding differs: {event}"
            )
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if (
            not str(payload.get("schema", "")).startswith(
                "magireco-event-production-"
            )
            or payload.get("event") != event
        ):
            raise ValueError(
                f"covered event manifest identity differs: {event}"
            )
        _add_material_source_role(
            source_roles,
            manifest_path,
            f"{collection}:covered_event_manifest:{event}",
        )
        resolved.append(
            {
                "label": f"{event} production manifest via event ledger",
                "path": str(manifest_path),
                "sha256": expected_manifest_sha,
            }
        )
    return resolved


def capture_material_source_snapshot(
    paths: dict[Path, set[str]],
) -> dict[str, object]:
    """Hash the exact external manifest, visual and audio input set."""

    rows: list[dict[str, object]] = []
    for path in sorted(paths, key=lambda value: str(value).casefold()):
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        before = resolved.stat()
        sha256 = file_sha256(resolved)
        after = resolved.stat()
        if (before.st_size, before.st_mtime_ns) != (
            after.st_size,
            after.st_mtime_ns,
        ):
            raise RuntimeError(
                f"material source changed while hashing: {resolved}"
            )
        roles = sorted({str(role) for role in paths[path] if str(role)})
        if not roles:
            raise RuntimeError(f"material source has no audit role: {resolved}")
        rows.append(
            {
                "path": str(resolved),
                "roles": roles,
                "size": after.st_size,
                "sha256": sha256,
            }
        )
    if not rows:
        raise RuntimeError("material source snapshot is empty")
    return {
        "schema": MATERIAL_SOURCE_SNAPSHOT_SCHEMA,
        "sources": rows,
        "snapshot_sha256": _canonical_sha256(rows),
    }


def _material_source_roles_from_snapshot(
    snapshot: object,
) -> dict[Path, set[str]]:
    if not isinstance(snapshot, dict) or snapshot.get("schema") != (
        MATERIAL_SOURCE_SNAPSHOT_SCHEMA
    ):
        raise RuntimeError("material source snapshot schema mismatch")
    rows = snapshot.get("sources")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("material source snapshot has no sources")
    roles_by_path: dict[Path, set[str]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(
                f"material source snapshot row {index} is malformed"
            )
        raw_path = Path(str(row.get("path", "")))
        if not raw_path.is_absolute():
            raise RuntimeError(
                f"material source snapshot row {index} path is not absolute"
            )
        path = raw_path.resolve()
        roles = row.get("roles")
        if not isinstance(roles, list) or not roles:
            raise RuntimeError(
                f"material source snapshot row {index} lacks roles"
            )
        if path in roles_by_path:
            raise RuntimeError(f"duplicate material source snapshot path: {path}")
        roles_by_path[path] = {str(role) for role in roles if str(role)}
        if not roles_by_path[path]:
            raise RuntimeError(
                f"material source snapshot row {index} has blank roles"
            )
        if not _valid_sha256(row.get("sha256")):
            raise RuntimeError(
                f"material source snapshot row {index} SHA-256 is invalid"
            )
        try:
            size = int(row.get("size", -1))
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                f"material source snapshot row {index} size is invalid"
            ) from error
        if size < 0 or size != row.get("size"):
            raise RuntimeError(
                f"material source snapshot row {index} size is invalid"
            )
    expected_snapshot_sha256 = str(
        snapshot.get("snapshot_sha256", "")
    ).strip().upper()
    if not _valid_sha256(expected_snapshot_sha256):
        raise RuntimeError("material source snapshot SHA-256 is invalid")
    if _canonical_sha256(rows) != expected_snapshot_sha256:
        raise RuntimeError("material source snapshot binding is invalid")
    return roles_by_path


def assert_material_source_snapshot_unchanged(
    start: object, end: object
) -> None:
    start_roles = _material_source_roles_from_snapshot(start)
    end_roles = _material_source_roles_from_snapshot(end)
    if start_roles != end_roles:
        raise RuntimeError("material source set/roles changed during build")
    assert isinstance(start, dict) and isinstance(end, dict)
    if start.get("snapshot_sha256") == end.get("snapshot_sha256"):
        return
    start_rows = {
        str(row["path"]): row
        for row in start.get("sources", [])
        if isinstance(row, dict) and "path" in row
    }
    end_rows = {
        str(row["path"]): row
        for row in end.get("sources", [])
        if isinstance(row, dict) and "path" in row
    }
    changes = []
    for path in sorted(set(start_rows) | set(end_rows), key=str.casefold):
        before = start_rows.get(path)
        after = end_rows.get(path)
        if before != after:
            changes.append(
                {
                    "path": path,
                    "start_sha256": (
                        None if before is None else before.get("sha256")
                    ),
                    "end_sha256": (
                        None if after is None else after.get("sha256")
                    ),
                }
            )
    raise RuntimeError(
        "material source changed during build; refusing TOCTOU publication: "
        + json.dumps(changes, ensure_ascii=False, sort_keys=True)
    )


def _material_source_rehash_contract(
    start: dict[str, object], end: dict[str, object]
) -> dict[str, object]:
    assert_material_source_snapshot_unchanged(start, end)
    return {
        "schema": MATERIAL_SOURCE_REHASH_SCHEMA,
        "status": "passed",
        "start_sha256": start["snapshot_sha256"],
        "end_sha256": end["snapshot_sha256"],
        "match": True,
        "source_count": len(end["sources"]),
    }


def _verify_material_source_contract(
    manifest: dict, *, stage: str
) -> dict[str, object]:
    start = manifest.get("source_snapshot_start")
    end = manifest.get("source_snapshot_end")
    rehash = manifest.get("source_rehash")
    assert_material_source_snapshot_unchanged(start, end)
    if not isinstance(start, dict) or not isinstance(end, dict):
        raise RuntimeError("material source snapshots are missing")
    expected = _material_source_rehash_contract(start, end)
    if rehash != expected:
        raise RuntimeError("material source rehash contract mismatch")
    current = capture_material_source_snapshot(
        _material_source_roles_from_snapshot(end)
    )
    try:
        assert_material_source_snapshot_unchanged(end, current)
    except RuntimeError as error:
        raise RuntimeError(
            f"material source changed at {stage}; refusing publication"
        ) from error
    return current


def event_sort_key(event: str) -> tuple:
    return tuple(
        int(token) if token.isdigit() else token.casefold()
        for token in re.split(r"(\d+)", event)
    )


def _valid_sha256(value: object) -> bool:
    return bool(SHA256_RE.fullmatch(str(value or "").strip()))


def audit_evidence_artifact(
    *, path_value: object, sha256_value: object, locator_value: object
) -> dict:
    """Verify that a semantic/mix claim names a real immutable artifact."""

    errors = []
    path_text = str(path_value or "").strip()
    declared_sha256 = str(sha256_value or "").strip().upper()
    locator = str(locator_value or "").strip()
    resolved_path = ""
    actual_sha256 = ""
    if not path_text:
        errors.append("evidence_path_missing")
    else:
        source_path = Path(path_text).resolve()
        resolved_path = str(source_path)
        if not source_path.is_file():
            errors.append("evidence_path_not_file")
        else:
            actual_sha256 = file_sha256(source_path)
    if not _valid_sha256(declared_sha256):
        errors.append("evidence_sha256_missing_or_invalid")
    elif actual_sha256 and declared_sha256 != actual_sha256:
        errors.append("evidence_sha256_mismatch")
    if not locator:
        errors.append("evidence_locator_missing")
    return {
        "verified": not errors,
        "path": resolved_path,
        "declared_sha256": declared_sha256,
        "actual_sha256": actual_sha256,
        "locator": locator,
        "errors": errors,
    }


def classify_audio_semantic(row: dict) -> dict:
    """Classify audio without a character-name allowlist.

    Explicit semantics are accepted only with an authoritative provenance record.
    The game's ``<id>_<speaker>_AT_*`` naming convention is independently strong
    static evidence for character speech.  Everything else remains ``unknown``;
    an unknown is never silently counted as non-dialogue audio.
    """

    semantic_review = row.get("semantic_review", {})
    if not isinstance(semantic_review, dict):
        semantic_review = {}
    semantic = str(
        semantic_review.get("semantic")
        or row.get("semantic_class")
        or row.get("audio_semantic")
        or row.get("semantic_kind")
        or row.get("audio_role")
        or ""
    ).strip().casefold()
    evidence_source = str(
        semantic_review.get("evidence_source")
        or row.get("semantic_evidence_source")
        or ""
    ).strip().casefold()
    evidence_hash = str(
        semantic_review.get("source_sha256")
        or row.get("semantic_source_sha256")
        or ""
    ).strip().upper()
    reviewer = str(
        semantic_review.get("reviewer")
        or row.get("semantic_reviewer")
        or ""
    ).strip()
    review_status = str(
        semantic_review.get("human_review_status")
        or row.get("semantic_review_status")
        or ""
    ).strip().casefold()
    evidence_artifact = audit_evidence_artifact(
        path_value=(
            semantic_review.get("evidence_path")
            or row.get("semantic_evidence_path")
        ),
        sha256_value=evidence_hash,
        locator_value=(
            semantic_review.get("evidence_locator")
            or row.get("semantic_evidence_locator")
        ),
    )

    code_name = str(row.get("code_name", "")).strip()
    parts = [part.casefold() for part in code_name.split("_")]
    match = SOUND_ID_RE.match(code_name)
    try:
        at_index = parts.index("at")
    except ValueError:
        at_index = -1
    # Structural role-voice evidence is conservative and cannot be overridden
    # by a contradictory explicit ``se``/``non_dialogue`` label.
    if match and at_index >= 2 and any(parts[1:at_index]):
        return {
            "semantic": "role_voice",
            "status": "conservative_role_voice",
            "basis": "static_at_voice_naming_pattern",
            "evidence_sha256": "",
        }

    source_is_authoritative = (
        evidence_source in VERIFIED_AUDIO_SEMANTIC_SOURCES
        and evidence_artifact["verified"]
        and (
            evidence_source != "human_reviewed_semantic_map"
            or (
                reviewer
                and review_status in VERIFIED_HUMAN_REVIEW_STATUSES
            )
        )
    )
    if semantic in ROLE_VOICE_SEMANTICS and source_is_authoritative:
        return {
            "semantic": "role_voice",
            "status": "verified",
            "basis": evidence_source,
            "evidence_sha256": evidence_hash,
            "evidence_artifact": evidence_artifact,
        }
    if semantic in NON_DIALOGUE_SEMANTICS and source_is_authoritative:
        return {
            "semantic": "non_dialogue",
            "status": "verified",
            "basis": evidence_source,
            "evidence_sha256": evidence_hash,
            "evidence_artifact": evidence_artifact,
        }

    reason = "semantic_evidence_missing"
    if semantic:
        reason = "semantic_evidence_not_authoritative"
    return {
        "semantic": "unknown",
        "status": "unresolved",
        "basis": "",
        "evidence_sha256": evidence_hash,
        "evidence_artifact": evidence_artifact,
        "reason": reason,
    }


def is_role_voice_audio(row: dict) -> bool:
    return classify_audio_semantic(row)["semantic"] == "role_voice"


def has_gameplay_marker(values: list[str]) -> bool:
    joined = "\n".join(values)
    return any(term in joined for term in GAMEPLAY_TERMS)


def material_lane(
    *,
    role_voice_audio_count: int,
    gameplay_marker: bool,
    hybrid_slot_story: bool,
) -> str:
    if hybrid_slot_story:
        return "hybrid_slot_story_material_not_clean_animation"
    if role_voice_audio_count and gameplay_marker:
        return "audible_gameplay_result_with_role_voice_not_pure_material"
    if role_voice_audio_count:
        return "audible_component_with_role_voice_not_pure_material"
    if gameplay_marker:
        return "pure_gameplay_or_effect_material"
    return "reviewed_audience_components_not_standalone_animation"


def _normalized_hash_set(values: object) -> set[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return set()
    return {
        str(value).strip().upper()
        for value in values
        if _valid_sha256(value)
    }


def material_semantic_review_gate(
    review: object,
    *,
    expected_source_sha256s: list[str] | set[str] | None = None,
) -> dict:
    """Validate a hash-bound human visual-semantic review.

    Visual semantics are deliberately independent of audio.  In particular,
    the absence of role voice is never evidence that a clip is material.  A
    reviewer must select one of the four routing classes and, when source
    hashes are supplied by the caller, bind the review to that exact media set.
    """

    if not isinstance(review, dict):
        return {
            "status": "review_required",
            "verified": False,
            "classification": "",
            "material_route_eligible": False,
            "expected_source_sha256s": sorted(
                {
                    str(value).strip().upper()
                    for value in (expected_source_sha256s or [])
                    if _valid_sha256(value)
                }
            ),
            "reviewed_source_sha256s": [],
            "errors": ["semantic_review_missing"],
        }
    errors = []
    declared_classification = str(review.get("classification", "")).strip()
    classification = VISUAL_SEMANTIC_ALIASES.get(
        declared_classification.casefold(), declared_classification.casefold()
    )
    evidence_source = str(review.get("evidence_source", "")).strip().casefold()
    evidence_sha256 = str(
        review.get("evidence_sha256") or review.get("source_sha256") or ""
    ).strip().upper()
    reviewer = str(review.get("reviewer", "")).strip()
    human_status = str(review.get("human_review_status", "")).strip().casefold()
    evidence_artifact = audit_evidence_artifact(
        path_value=review.get("evidence_path"),
        sha256_value=evidence_sha256,
        locator_value=review.get("evidence_locator"),
    )
    if classification not in VISUAL_SEMANTIC_CLASSES:
        errors.append("semantic_classification_missing_or_invalid")
    if evidence_source not in VERIFIED_AUDIO_SEMANTIC_SOURCES:
        errors.append("semantic_evidence_source_not_authoritative")
    errors.extend(f"semantic_{error}" for error in evidence_artifact["errors"])
    if not reviewer:
        errors.append("semantic_reviewer_missing")
    if human_status not in VERIFIED_HUMAN_REVIEW_STATUSES:
        errors.append("semantic_human_review_not_approved")
    expected_hashes = {
        str(value).strip().upper()
        for value in (expected_source_sha256s or [])
        if _valid_sha256(value)
    }
    reviewed_hashes = _normalized_hash_set(
        review.get("reviewed_source_sha256s")
        or review.get("reviewed_media_sha256s")
        or review.get("reviewed_source_sha256")
    )
    if expected_source_sha256s is not None:
        if not reviewed_hashes:
            errors.append("semantic_reviewed_source_hashes_missing")
        elif reviewed_hashes != expected_hashes:
            errors.append("semantic_reviewed_source_hashes_mismatch")
    route_eligible = classification in MATERIAL_ROUTE_VISUAL_CLASSES
    return {
        "status": "verified" if not errors else "review_required",
        "verified": not errors,
        "classification": classification,
        "declared_classification": declared_classification,
        "material_route_eligible": not errors and route_eligible,
        "evidence_source": evidence_source,
        "evidence_sha256": evidence_sha256,
        "source_sha256": evidence_sha256,
        "evidence_artifact": evidence_artifact,
        "expected_source_sha256s": sorted(expected_hashes),
        "reviewed_source_sha256s": sorted(reviewed_hashes),
        "reviewer": reviewer,
        "human_review_status": human_status,
        "errors": errors,
    }


def aggregate_visual_semantic_gates(gates: list[dict]) -> dict:
    """Combine per-event reviews without deriving semantics from sound."""

    errors = []
    if not gates:
        errors.append("visual_semantic_review_missing")
    for index, gate in enumerate(gates):
        for error in gate.get("errors", []):
            errors.append(f"review_{index}_{error}")
    classifications = sorted(
        {
            str(gate.get("classification", ""))
            for gate in gates
            if str(gate.get("classification", ""))
        }
    )
    verified = bool(gates) and all(bool(gate.get("verified")) for gate in gates)
    route_eligible = verified and all(
        bool(gate.get("material_route_eligible")) for gate in gates
    )
    if not classifications:
        classification = "unreviewed"
    elif len(classifications) == 1:
        classification = classifications[0]
    else:
        classification = "mixed:" + "+".join(classifications)
    return {
        "status": "verified" if verified else "review_required",
        "verified": verified,
        "material_route_eligible": route_eligible,
        "classification": classification,
        "classifications": classifications,
        "reviews": gates,
        "errors": errors,
    }


def transcript_gate(
    role_voice_audio_rows: list[dict],
    transcript_rows: list[dict],
    *,
    transcript_required_hint: bool = False,
) -> dict:
    """Validate formal, human-reviewed transcript cues and fail closed.

    A release cue must identify its exact event/request/start, an end time, the
    SHA-256 of the voice source, a reviewer and an explicit human approval.  A
    duplicate cue key is invalid even when the duplicate text is identical; a
    conflicting duplicate is reported separately.
    """

    transcript_required = (
        bool(role_voice_audio_rows)
        or transcript_required_hint
        or bool(transcript_rows)
    )
    required_keys: set[tuple[str, str, int, str]] = set()
    missing_request_rows = []
    for row in role_voice_audio_rows:
        event = str(row.get("event", "")).strip()
        request_id = str(row.get("request_id", "")).strip()
        source_sha256 = str(row.get("source_sha256", "")).strip().upper()
        if request_id and event and _valid_sha256(source_sha256):
            required_keys.add(
                (event, request_id, int(row.get("start_ms", 0)), source_sha256)
            )
        else:
            if not request_id:
                reason = "role_voice_request_id_missing"
            elif not event:
                reason = "role_voice_event_missing"
            else:
                reason = "role_voice_source_hash_missing"
            missing_request_rows.append(
                {
                    "event": event,
                    "request_id": request_id,
                    "code_name": str(row.get("code_name", "")).strip(),
                    "reason": reason,
                }
            )

    candidates: dict[tuple[str, str, int, str], list[dict]] = {}
    validation_errors = []
    for row_index, row in enumerate(transcript_rows):
        source = str(row.get("subtitle_source", "")).strip().casefold()
        text = str(row.get("text", "")).strip()
        request_id = str(row.get("voice_request_id", "")).strip()
        event = str(row.get("event", "")).strip()
        reviewer = str(row.get("reviewer", "")).strip()
        review_status = str(row.get("human_review_status", "")).strip().casefold()
        source_sha256 = str(row.get("source_sha256", "")).strip().upper()
        start_value = row.get("voice_start_ms", row.get("start_ms"))
        end_value = row.get("voice_end_ms", row.get("end_ms"))
        row_errors = []
        if source not in VERIFIED_TRANSCRIPT_SOURCES:
            row_errors.append("subtitle_source_not_verified")
        if not text:
            row_errors.append("text_missing")
        if not event:
            row_errors.append("event_missing")
        if not request_id:
            row_errors.append("voice_request_id_missing")
        if not _valid_sha256(source_sha256):
            row_errors.append("source_sha256_missing_or_invalid")
        if not reviewer:
            row_errors.append("reviewer_missing")
        if review_status not in VERIFIED_HUMAN_REVIEW_STATUSES:
            row_errors.append("human_review_not_approved")
        try:
            start_ms = int(start_value)
            end_ms = int(end_value)
        except (TypeError, ValueError):
            start_ms = 0
            end_ms = 0
            row_errors.append("cue_timing_missing_or_invalid")
        else:
            if start_ms < 0 or end_ms <= start_ms:
                row_errors.append("cue_timing_missing_or_invalid")
        if row_errors:
            validation_errors.append(
                {"row_index": row_index, "errors": row_errors}
            )
            continue
        audited_row = dict(row)
        audited_row["event"] = event
        audited_row["voice_request_id"] = request_id
        audited_row["text"] = text
        audited_row["subtitle_source"] = source
        audited_row["voice_start_ms"] = start_ms
        audited_row["voice_end_ms"] = end_ms
        audited_row["source_sha256"] = source_sha256
        audited_row["reviewer"] = reviewer
        audited_row["human_review_status"] = review_status
        key = (event, request_id, start_ms, source_sha256)
        candidates.setdefault(key, []).append(audited_row)

    duplicate_keys: set[tuple[str, str, int, str]] = set()
    for key, rows in candidates.items():
        if len(rows) <= 1:
            continue
        duplicate_keys.add(key)
        texts = sorted({str(row["text"]) for row in rows})
        validation_errors.append(
            {
                "event": key[0],
                "request_id": key[1],
                "start_ms": key[2],
                "source_sha256": key[3],
                "reason": (
                    "conflicting_transcript_cues"
                    if len(texts) > 1
                    else "duplicate_transcript_cues"
                ),
                "texts": texts,
            }
        )

    verified_keys = set(candidates) - duplicate_keys
    for key in sorted(verified_keys - required_keys):
        validation_errors.append(
            {
                "event": key[0],
                "request_id": key[1],
                "start_ms": key[2],
                "source_sha256": key[3],
                "reason": "transcript_cue_has_no_matching_role_voice",
            }
        )
    verified_keys &= required_keys
    verified_rows = [candidates[key][0] for key in sorted(verified_keys)]

    missing_rows = [
        {
            "event": event,
            "request_id": request_id,
            "start_ms": start_ms,
            "source_sha256": source_sha256,
            "reason": "verified_transcript_missing",
        }
        for event, request_id, start_ms, source_sha256 in sorted(
            required_keys - verified_keys
        )
    ]
    missing_rows.extend(missing_request_rows)
    if transcript_required_hint and not role_voice_audio_rows:
        missing_rows.append(
            {
                "event": "",
                "request_id": "",
                "reason": "manifest_transcript_requirement_unresolved",
            }
        )

    if not transcript_required:
        transcript_status = "not_applicable"
    elif missing_rows or validation_errors:
        transcript_status = "required_not_verified"
    else:
        transcript_status = "verified"
    return {
        "transcript_required": transcript_required,
        "transcript_status": transcript_status,
        "transcript_verified": transcript_status == "verified",
        "required_role_voice_key_count": len(required_keys) + len(missing_request_rows),
        "verified_transcript_count": len(verified_rows),
        "verified_transcripts": verified_rows,
        "missing_transcript_role_voice": missing_rows,
        "transcript_validation_errors": validation_errors,
    }


def _native_gain_filter(row: dict) -> tuple[str, dict]:
    """Resolve the evidence-bound native volume into one ffmpeg filter."""

    value = float(row.get("native_volume"))
    if isinstance(row.get("native_volume"), bool) or not math.isfinite(value):
        raise ValueError("native_volume_missing_or_invalid")
    unit = str(row.get("volume_unit", "")).strip().casefold()
    mix_contract = row.get("mix_contract", {})
    if unit == "linear":
        if value < 0:
            raise ValueError("native_volume_out_of_range")
        linear_gain = value
        expression = f"volume={linear_gain:.12g}"
    elif unit in {"percent", "game_percent"}:
        if value < 0:
            raise ValueError("native_volume_out_of_range")
        linear_gain = value / 100.0
        expression = f"volume={linear_gain:.12g}"
    elif unit == "db":
        linear_gain = 10 ** (value / 20.0)
        expression = f"volume={value:.12g}dB"
    elif unit == "game_index":
        if not isinstance(mix_contract, dict):
            raise ValueError("game_index_gain_mapping_missing")
        if mix_contract.get("linear_gain") is not None:
            linear_gain = float(mix_contract["linear_gain"])
            if not math.isfinite(linear_gain) or linear_gain < 0:
                raise ValueError("game_index_gain_mapping_invalid")
            expression = f"volume={linear_gain:.12g}"
        elif mix_contract.get("gain_db") is not None:
            gain_db = float(mix_contract["gain_db"])
            if not math.isfinite(gain_db):
                raise ValueError("game_index_gain_mapping_invalid")
            linear_gain = 10 ** (gain_db / 20.0)
            expression = f"volume={gain_db:.12g}dB"
        else:
            raise ValueError("game_index_gain_mapping_missing")
    else:
        raise ValueError("native_volume_unit_missing_or_invalid")
    return expression, {
        "native_volume": value,
        "volume_unit": unit,
        "linear_gain": linear_gain,
        "filter": expression,
    }


def _ducking_filter(row: dict) -> tuple[str, dict]:
    """Resolve a supported, evidence-bound ducking contract."""

    contract = row.get("ducking_contract", row.get("ducking"))
    if not isinstance(contract, dict):
        raise ValueError("ducking_contract_missing")
    mode = str(contract.get("mode", "")).strip().casefold()
    if mode in {"none", "off", "disabled"}:
        return "", {"mode": "none", "linear_gain": 1.0, "filter": ""}
    if mode not in {"fixed_gain", "gain"}:
        raise ValueError("ducking_mode_not_supported_by_renderer")
    if contract.get("gain_db") is not None:
        gain_db = float(contract["gain_db"])
        if not math.isfinite(gain_db):
            raise ValueError("ducking_gain_invalid")
        linear_gain = 10 ** (gain_db / 20.0)
        expression = f"volume={gain_db:.12g}dB"
    elif contract.get("linear_gain") is not None:
        linear_gain = float(contract["linear_gain"])
        if not math.isfinite(linear_gain) or linear_gain < 0:
            raise ValueError("ducking_gain_invalid")
        expression = f"volume={linear_gain:.12g}"
    else:
        raise ValueError("ducking_gain_missing")
    return expression, {
        "mode": "fixed_gain",
        "linear_gain": linear_gain,
        "filter": expression,
    }


def audible_audio_contract_gate(audio_rows: list[dict]) -> dict:
    """Require a per-source native mix contract for an audible release."""

    if not audio_rows:
        return {
            "audible_audio_contract_status": "not_applicable",
            "audible_audio_contract_verified": True,
            "audible_audio_contract_errors": [],
        }
    errors = []
    for row_index, row in enumerate(audio_rows):
        row_errors = []
        if not _valid_sha256(row.get("source_sha256")):
            row_errors.append("per_source_sha256_missing_or_invalid")
        try:
            start_ms = int(row.get("start_ms", 0))
            source_offset_ms = int(row.get("source_offset_ms", 0))
            duration_ms = int(row.get("duration_ms"))
        except (TypeError, ValueError):
            row_errors.append("audio_timing_missing_or_invalid")
        else:
            if start_ms < 0 or source_offset_ms < 0 or duration_ms <= 0:
                row_errors.append("audio_timing_missing_or_invalid")
        volume_unit = str(row.get("volume_unit", "")).strip().casefold()
        if volume_unit not in NATIVE_VOLUME_UNITS:
            row_errors.append("native_volume_unit_missing_or_invalid")
        try:
            _native_gain_filter(row)
        except (TypeError, ValueError) as exc:
            error = str(exc) or "native_volume_missing_or_invalid"
            if error not in row_errors:
                row_errors.append(error)
        ducking = row.get("ducking_contract", row.get("ducking"))
        if not isinstance(ducking, dict) or not ducking:
            row_errors.append("ducking_contract_missing")
        else:
            if not str(ducking.get("mode", "")).strip():
                row_errors.append("ducking_mode_missing")
            if (
                str(ducking.get("evidence_source", "")).strip().casefold()
                not in VERIFIED_MIX_EVIDENCE_SOURCES
            ):
                row_errors.append("ducking_evidence_source_not_authoritative")
            ducking_artifact = audit_evidence_artifact(
                path_value=ducking.get("evidence_path"),
                sha256_value=ducking.get("evidence_sha256"),
                locator_value=ducking.get("evidence_locator"),
            )
            row_errors.extend(
                f"ducking_{error}" for error in ducking_artifact["errors"]
            )
            try:
                _ducking_filter(row)
            except (TypeError, ValueError) as exc:
                error = str(exc) or "ducking_contract_invalid"
                if error not in row_errors:
                    row_errors.append(error)
        mix_contract = row.get("mix_contract")
        if not isinstance(mix_contract, dict) or not mix_contract:
            row_errors.append("mix_contract_missing")
        else:
            if not str(mix_contract.get("mode", "")).strip():
                row_errors.append("mix_mode_missing")
            if (
                str(mix_contract.get("evidence_source", "")).strip().casefold()
                not in VERIFIED_MIX_EVIDENCE_SOURCES
            ):
                row_errors.append("mix_evidence_source_not_authoritative")
            mix_artifact = audit_evidence_artifact(
                path_value=mix_contract.get("evidence_path"),
                sha256_value=mix_contract.get("evidence_sha256"),
                locator_value=mix_contract.get("evidence_locator"),
            )
            row_errors.extend(
                f"mix_{error}" for error in mix_artifact["errors"]
            )
            if str(mix_contract.get("mode", "")).strip().casefold() not in {
                "runtime_additive",
                "additive",
                "single_source",
                "native_embedded",
            }:
                row_errors.append("mix_mode_not_supported_by_renderer")
        if row_errors:
            errors.append(
                {
                    "row_index": row_index,
                    "event": str(row.get("event", "")),
                    "request_id": str(row.get("request_id", "")),
                    "code_name": str(row.get("code_name", "")),
                    "errors": row_errors,
                }
            )
    return {
        "audible_audio_contract_status": (
            "verified" if not errors else "required_not_verified"
        ),
        "audible_audio_contract_verified": not errors,
        "audible_audio_contract_errors": errors,
    }


def collection_release_gate(
    *,
    errors: list[str],
    role_voice_audio_rows: list[dict],
    transcript_rows: list[dict],
    transcript_required_hint: bool = False,
    all_audio_rows: list[dict] | None = None,
    unknown_audio_rows: list[dict] | None = None,
    material_semantics_release_approved: bool | None = None,
    visual_semantic_gate: dict | None = None,
    explicit_release_authorized: bool = True,
    audible_render_contract_applied: bool = True,
) -> dict:
    if all_audio_rows is None:
        all_audio_rows = list(role_voice_audio_rows)
    role_voice_audio_rows = list(role_voice_audio_rows)
    unknown_audio_rows = list(unknown_audio_rows or [])
    for row in all_audio_rows:
        semantic = classify_audio_semantic(row)["semantic"]
        if semantic == "role_voice" and row not in role_voice_audio_rows:
            role_voice_audio_rows.append(row)
        elif semantic == "unknown" and row not in unknown_audio_rows:
            unknown_audio_rows.append(row)
    transcript = transcript_gate(
        role_voice_audio_rows,
        transcript_rows,
        transcript_required_hint=transcript_required_hint,
    )
    audio_contract = audible_audio_contract_gate(all_audio_rows)
    if not isinstance(visual_semantic_gate, dict):
        visual_semantic_gate = aggregate_visual_semantic_gates([])
    if material_semantics_release_approved is None:
        material_semantics_release_approved = True

    technical_ok = not errors
    semantic_ok = (
        bool(material_semantics_release_approved)
        and bool(visual_semantic_gate.get("verified"))
        and bool(visual_semantic_gate.get("material_route_eligible"))
        and not unknown_audio_rows
        and not role_voice_audio_rows
    )
    transcript_ok = transcript["transcript_status"] in {"not_applicable", "verified"}
    visual_release_eligible = (
        technical_ok and semantic_ok and explicit_release_authorized
    )
    if all_audio_rows:
        audible_status = "publishable" if (
            visual_release_eligible
            and transcript_ok
            and audio_contract["audible_audio_contract_verified"]
            and audible_render_contract_applied
        ) else "review_only"
        audible_release_eligible: bool | None = audible_status == "publishable"
        overall_release_eligible = bool(audible_release_eligible)
    else:
        audible_status = "not_applicable"
        audible_release_eligible = None
        overall_release_eligible = visual_release_eligible
    if errors:
        status = "failed"
        publication_status = "blocked_technical_qa"
    elif not overall_release_eligible:
        status = "review_only"
        publication_status = "review_only"
    else:
        status = "passed"
        publication_status = "publishable"
    return {
        **transcript,
        **audio_contract,
        "visual_semantic_gate": visual_semantic_gate,
        "technical_qa_status": "failed" if errors else "passed",
        "semantic_gate_status": "verified" if semantic_ok else "review_required",
        "unknown_audio_count": len(unknown_audio_rows),
        "unknown_audio": unknown_audio_rows,
        "visual_only_gate": {
            "status": "publishable" if visual_release_eligible else "review_only",
            "release_eligible": visual_release_eligible,
        },
        "audible_review_gate": {
            "status": audible_status,
            "release_eligible": audible_release_eligible,
            "native_mix_contract_applied": (
                audible_render_contract_applied if all_audio_rows else None
            ),
        },
        "status": status,
        "publication_status": publication_status,
        "release_eligible": overall_release_eligible,
        "publishable": overall_release_eligible,
    }


def format_srt_time(value_ms: int) -> str:
    value_ms = max(0, value_ms)
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--series", action="append", default=[])
    parser.add_argument(
        "--plan",
        action="append",
        default=[],
        help="Named material collection plan resolved through --video-map.",
    )
    parser.add_argument(
        "--video-map",
        default="",
        help="Official-name video map required by --plan.",
    )
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.series and not args.plan:
        parser.error("at least one --series or --plan is required")
    if args.plan and not args.video_map:
        parser.error("--video-map is required with --plan")
    return args


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,profile,level,width,height,pix_fmt,"
            "r_frame_rate,time_base,duration,bit_rate,sample_rate,channels,"
            "channel_layout:format=duration,size,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def video_signature(payload: dict) -> dict:
    stream = next(
        row
        for row in payload.get("streams", [])
        if row.get("codec_type") == "video"
    )
    return {
        key: stream.get(key, "")
        for key in (
            "codec_name",
            "profile",
            "level",
            "width",
            "height",
            "pix_fmt",
            "r_frame_rate",
            "time_base",
        )
    }


def _canonical_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _canonical_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value.resolve())
    return value


def _canonical_evidence_rows(rows: object) -> list[dict]:
    canonical = []
    if not isinstance(rows, list):
        return canonical
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Event, local path, and source code-name identities are
        # aliases/provenance, not media identity.  Source hashes, cue times,
        # text and mix fields remain.
        normalized = {
            key: value
            for key, value in row.items()
            if key not in {"event", "path", "code_name"}
        }
        canonical.append(_canonical_json_value(normalized))
    return sorted(
        canonical,
        key=lambda row: json.dumps(
            row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    )


def material_av_signature(source: dict) -> dict:
    """Return the complete visual/audio/subtitle identity used for deduping."""

    visual_packet_sha256 = str(
        source.get("source_video_packet_sha256")
        or source.get("video_packet_sha256")
        or source.get("source_sha256")
        or ""
    ).strip().upper()
    signature = {
        "visual_packet_sha256": visual_packet_sha256,
        "embedded_audio_packet_sha256": str(
            source.get("source_audio_packet_sha256")
            or source.get("embedded_audio_packet_sha256")
            or ""
        ).strip().upper(),
        "video_stream_signature": _canonical_json_value(
            source.get("video_stream_signature")
            or source.get("source_video_signature")
            or {}
        ),
        "duration_ms": int(source.get("duration_ms", 0)),
        "official_audio": _canonical_evidence_rows(
            source.get("official_audio_evidence", [])
        ),
        "transcript_cues": _canonical_evidence_rows(
            source.get("transcript_evidence", [])
        ),
    }
    serialized = json.dumps(
        signature, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        **signature,
        "sha256": hashlib.sha256(serialized).hexdigest().upper(),
    }


def source_event_alias(source: dict) -> dict:
    return {
        "event": str(source.get("event", "")),
        "dgm_name": str(source.get("dgm_name", "")),
        "clip_index": int(source.get("clip_index", 0)),
        "path": str(source.get("path", "")),
        "production_manifest": str(source.get("production_manifest", "")),
    }


def deduplicate_material_sources_by_av_signature(sources: list[dict]) -> list[dict]:
    """Deduplicate exact AV+cues while retaining every source-event alias."""

    groups: dict[str, list[dict]] = {}
    output: list[dict] = []
    for raw_source in sources:
        source = copy.deepcopy(raw_source)
        signature = material_av_signature(source)
        signature_hash = str(signature["sha256"])
        alias_rows = source.get("source_event_aliases")
        if not isinstance(alias_rows, list) or not alias_rows:
            alias_rows = [source_event_alias(source)]
        candidates = groups.setdefault(signature_hash, [])
        target = next(
            (
                candidate
                for candidate in candidates
                if candidate.get("av_signature") == signature
            ),
            None,
        )
        if target is None:
            source["av_signature"] = signature
            source["source_event_aliases"] = []
            for alias in alias_rows:
                if alias not in source["source_event_aliases"]:
                    source["source_event_aliases"].append(alias)
            source["source_occurrence_count"] = len(source["source_event_aliases"])
            candidates.append(source)
            output.append(source)
            continue
        for alias in alias_rows:
            if alias not in target["source_event_aliases"]:
                target["source_event_aliases"].append(alias)
        target["source_occurrence_count"] = len(target["source_event_aliases"])
    return output


def audit_official_audio_evidence(
    rows: object,
    *,
    hash_cache: dict[str, str] | None = None,
) -> list[dict]:
    """Attach and verify a SHA-256 for every referenced official audio source."""

    if hash_cache is None:
        hash_cache = {}
    audited = []
    if not isinstance(rows, list):
        return audited
    for row in rows:
        if not isinstance(row, dict):
            continue
        result = copy.deepcopy(row)
        path_value = str(result.get("path", "")).strip()
        declared_hash = str(
            result.get("source_sha256") or result.get("sha256") or ""
        ).strip().upper()
        if path_value:
            source_path = Path(path_value).resolve()
            if not source_path.is_file():
                raise FileNotFoundError(source_path)
            cache_key = str(source_path).casefold()
            actual_hash = hash_cache.get(cache_key)
            if actual_hash is None:
                actual_hash = file_sha256(source_path)
                hash_cache[cache_key] = actual_hash
            if declared_hash and declared_hash != actual_hash:
                raise ValueError(
                    f"official audio source hash mismatch: {source_path}: "
                    f"{declared_hash} != {actual_hash}"
                )
            result["path"] = str(source_path)
            result["source_sha256"] = actual_hash
        else:
            result["source_sha256"] = declared_hash
        result["semantic_audit"] = classify_audio_semantic(result)
        audited.append(result)
    return audited


def ffconcat_line(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{value}'"


def stream_packet_hash(path: Path, ffmpeg: str, stream: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            stream,
            "-c",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip().split("=", 1)[-1].upper()


def video_packet_hash(path: Path, ffmpeg: str) -> str:
    return stream_packet_hash(path, ffmpeg, "0:v:0")


def audio_packet_hash(path: Path, ffmpeg: str) -> str:
    return stream_packet_hash(path, ffmpeg, "0:a:0")


def write_label_srt(path: Path, rows: list[dict]) -> None:
    blocks = []
    for index, row in enumerate(rows, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_srt_time(row['start_ms'])} --> "
            f"{format_srt_time(row['end_ms'])}\n"
            f"{row['event']} | {row['dgm_name']}"
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def render_audible_segment(
    source: dict,
    output_path: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    audio_rows = [
        row
        for row in source.get("official_audio_evidence", [])
        if str(row.get("path", "")).strip()
    ]
    missing_audio = [
        str(row.get("path", ""))
        for row in audio_rows
        if not Path(str(row.get("path", ""))).is_file()
    ]
    if missing_audio:
        raise FileNotFoundError(
            f"missing official material audio for {source['event']}: {missing_audio}"
        )
    contract = audible_audio_contract_gate(audio_rows)
    if audio_rows and not contract["audible_audio_contract_verified"]:
        raise ValueError(
            f"official material audio contract invalid for {source['event']}: "
            f"{contract['audible_audio_contract_errors']}"
        )
    audible_duration_ms = max(
        [int(source["duration_ms"])]
        + [
            int(row.get("start_ms", 0)) + int(row.get("duration_ms", 0))
            for row in audio_rows
        ]
    )
    extension_ms = max(0, audible_duration_ms - int(source["duration_ms"]))
    source_probe = source["source_probe"]
    source_video = next(
        row
        for row in source_probe.get("streams", [])
        if row.get("codec_type") == "video"
    )
    frame_rate = str(source_video.get("r_frame_rate", "30/1"))
    pixel_format = str(source_video.get("pix_fmt", "yuv420p"))
    inputs = ["-i", str(Path(source["path"]).resolve())]
    filters = [
        "[0:v:0]"
        f"tpad=stop_mode=clone:stop_duration={extension_ms / 1000:.6f},"
        f"trim=duration={audible_duration_ms / 1000:.6f},"
        f"setpts=PTS-STARTPTS,fps={frame_rate},format={pixel_format}[v]"
    ]
    audio_labels = []
    applied_audio_rows = []
    for index, row in enumerate(audio_rows, start=1):
        inputs.extend(["-i", str(Path(str(row["path"])).resolve())])
        label = f"a{index}"
        source_offset_ms = int(row.get("source_offset_ms", 0))
        duration_ms = int(row.get("duration_ms", 0))
        start_ms = int(row.get("start_ms", 0))
        source_audio_probe = probe(Path(str(row["path"])), ffprobe)
        source_audio_duration_ms = round(
            float(source_audio_probe.get("format", {}).get("duration", 0))
            * 1000
        )
        if source_audio_duration_ms <= 0 or (
            source_offset_ms + duration_ms > source_audio_duration_ms + 50
        ):
            raise ValueError(
                f"official material audio trim exceeds source for "
                f"{source['event']}: offset={source_offset_ms}, "
                f"duration={duration_ms}, source={source_audio_duration_ms}"
            )
        native_filter, native_audit = _native_gain_filter(row)
        duck_filter, duck_audit = _ducking_filter(row)
        chain = [
            f"[{index}:a:0]atrim=start={source_offset_ms / 1000:.6f}:"
            f"duration={duration_ms / 1000:.6f}",
            "asetpts=PTS-STARTPTS",
            "aresample=48000",
            "aformat=sample_fmts=s16:channel_layouts=stereo",
            native_filter,
        ]
        if duck_filter:
            chain.append(duck_filter)
        chain.append(f"adelay={start_ms}:all=1[{label}]")
        filters.append(",".join(chain))
        audio_labels.append(f"[{label}]")
        applied_audio_rows.append(
            {
                "path": str(Path(str(row["path"])).resolve()),
                "source_sha256": str(row.get("source_sha256", "")),
                "start_ms": start_ms,
                "source_offset_ms": source_offset_ms,
                "duration_ms": duration_ms,
                "source_duration_ms": source_audio_duration_ms,
                "native_gain": native_audit,
                "ducking": duck_audit,
                "mix_mode": str(row.get("mix_contract", {}).get("mode", "")),
            }
        )
    if audio_labels:
        filters.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audio_labels)}:duration=longest:"
            + "normalize=0:dropout_transition=0,"
            + f"apad=whole_dur={audible_duration_ms / 1000:.6f},"
            + f"atrim=duration={audible_duration_ms / 1000:.6f}[a]"
        )
    else:
        filters.append(
            "anullsrc=r=48000:cl=stereo,"
            f"atrim=duration={audible_duration_ms / 1000:.6f}[a]"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            pixel_format,
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-f",
            "matroska",
            str(output_path),
        ],
        check=True,
    )
    output_probe = probe(output_path, ffprobe)
    return {
        "path": str(output_path.resolve()),
        "duration_ms": round(float(output_probe["format"]["duration"]) * 1000),
        "planned_duration_ms": audible_duration_ms,
        "extension_ms": extension_ms,
        "audio_intermediate_codec": "pcm_s16le",
        "applied_audio_rows": applied_audio_rows,
        "unproven_limiter_applied": False,
        "sha256": file_sha256(output_path),
        "video_packet_sha256": video_packet_hash(output_path, ffmpeg),
        "audio_packet_sha256": audio_packet_hash(output_path, ffmpeg),
        "probe": output_probe,
    }


def render_audible_collection(
    *,
    collection_name: str,
    event_sources: list[dict],
    collection_dir: Path,
    audit_dir: Path,
    signature: dict,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    """Render PCM event intermediates and encode AAC exactly once.

    Independent AAC event files are intentionally never packet-concatenated:
    that would preserve encoder delay/padding at every boundary.  Each event is
    mixed into PCM after its evidence-bound trim/gain/duck operations; the final
    collection is the only AAC encode.
    """

    collection_name = validate_output_identifier(
        collection_name, label="audible collection"
    )
    for source in event_sources:
        validate_output_identifier(
            source.get("event"), label="audible material event"
        )

    has_audio = any(
        any(str(row.get("path", "")).strip() for row in source.get(
            "official_audio_evidence", []
        ))
        for source in event_sources
    )
    if not has_audio:
        return {
            "status": "not_applicable",
            "contract_applied": False,
            "output": "",
            "labels": "",
            "labels_sha256": "",
            "duration_ms": 0,
            "probe": {},
            "video": {},
            "audio": {},
            "event_sources": event_sources,
            "encoding": {
                "pcm_intermediates": 0,
                "final_aac_encode_count": 0,
                "aac_segment_packet_copy": False,
                "unproven_limiter_applied": False,
            },
            "errors": [],
        }

    contract_rows = [
        row
        for source in event_sources
        for row in source.get("official_audio_evidence", [])
        if isinstance(row, dict)
    ]
    contract_gate = audible_audio_contract_gate(contract_rows)
    missing_path_rows = [
        index
        for index, row in enumerate(contract_rows)
        if not str(row.get("path", "")).strip()
    ]
    if missing_path_rows or not contract_gate["audible_audio_contract_verified"]:
        return {
            "status": "blocked_contract",
            "contract_applied": False,
            "contract_gate": contract_gate,
            "missing_source_path_rows": missing_path_rows,
            "output": "",
            "labels": "",
            "labels_sha256": "",
            "duration_ms": 0,
            "probe": {},
            "video": {},
            "audio": {},
            "event_sources": event_sources,
            "encoding": {
                "pcm_intermediates": 0,
                "final_aac_encode_count": 0,
                "aac_segment_packet_copy": False,
                "unproven_limiter_applied": False,
            },
            # An unavailable audible review is a release-gate state, not a
            # failure of the already completed visual collection.
            "errors": [],
        }

    segments_dir = ensure_resolved_containment(
        collection_dir,
        audit_dir / "audible_pcm_segments",
        label="audible PCM segment directory",
    )
    rows = []
    offset_ms = 0
    for source in event_sources:
        event = validate_output_identifier(
            source.get("event"), label="audible material event"
        )
        segment_path = ensure_resolved_containment(
            collection_dir,
            segments_dir / f"{event}__audible_pcm.mkv",
            label=f"{event} audible PCM segment",
        )
        segment = render_audible_segment(
            source, segment_path, ffmpeg, ffprobe, overwrite
        )
        source["audible_segment"] = segment
        source["audible_start_ms"] = offset_ms
        source["audible_end_ms"] = offset_ms + int(
            segment["planned_duration_ms"]
        )
        rows.append(
            {
                "event": source["event"],
                "dgm_name": source["dgm_name"],
                "start_ms": source["audible_start_ms"],
                "end_ms": source["audible_end_ms"],
            }
        )
        offset_ms = source["audible_end_ms"]

    list_path = audit_dir / "materials_with_official_audio_pcm.ffconcat"
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(
            ffconcat_line(Path(row["audible_segment"]["path"]))
            for row in event_sources
        )
        + "\n",
        encoding="utf-8",
    )
    width = int(signature["width"])
    height = int(signature["height"])
    rate_label = str(signature["r_frame_rate"]).replace("/", "-")
    output_path = (
        collection_dir
        / f"{collection_name}__material_components_with_official_audio__"
        f"{width}x{height}_{rate_label}.mp4"
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c:v",
            "copy",
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
            str(output_path),
        ],
        check=True,
    )
    label_path = collection_dir / f"{collection_name}__material_audio_labels.srt"
    write_label_srt(label_path, rows)
    output_probe = probe(output_path, ffprobe)
    video = next(
        (row for row in output_probe.get("streams", []) if row.get("codec_type") == "video"),
        {},
    )
    audio = next(
        (row for row in output_probe.get("streams", []) if row.get("codec_type") == "audio"),
        {},
    )
    errors = []
    if (
        video.get("width") != width
        or video.get("height") != height
        or video.get("pix_fmt") != signature["pix_fmt"]
        or video.get("r_frame_rate") != signature["r_frame_rate"]
    ):
        errors.append("audible_native_video_signature_changed")
    if audio.get("sample_rate") != "48000" or audio.get("channels") != 2:
        errors.append("audible_audio_signature_invalid")
    duration_ms = round(float(output_probe["format"]["duration"]) * 1000)
    if abs(duration_ms - offset_ms) > max(200, len(event_sources) * 35):
        errors.append("audible_duration_mismatch")
    return {
        "status": "rendered" if not errors else "failed",
        "contract_applied": not errors,
        "output": str(output_path.resolve()),
        "labels": str(label_path.resolve()),
        "labels_sha256": file_sha256(label_path),
        "duration_ms": duration_ms,
        "planned_duration_ms": offset_ms,
        "probe": output_probe,
        "video": video,
        "audio": audio,
        "event_sources": event_sources,
        "contract_gate": contract_gate,
        "output_sha256": file_sha256(output_path),
        "video_packet_sha256": video_packet_hash(output_path, ffmpeg),
        "audio_packet_sha256": audio_packet_hash(output_path, ffmpeg),
        "encoding": {
            "pcm_intermediates": len(event_sources),
            "intermediate_audio_codec": "pcm_s16le",
            "final_audio_codec": "aac",
            "final_aac_encode_count": 1,
            "aac_segment_packet_copy": False,
            "unproven_limiter_applied": False,
        },
        "errors": errors,
    }


def _build_collection_in_place(
    series: str,
    manifest_dir: Path,
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    series = validate_output_identifier(series, label="collection")
    manifests: list[tuple[Path, dict]] = []
    source_roles: dict[Path, set[str]] = {}
    manifest_bytes_sha256: dict[Path, str] = {}
    candidate_paths = sorted(
        manifest_dir.glob(f"{series}_*.json"),
        key=lambda path: event_sort_key(path.stem),
    )
    for path in candidate_paths:
        resolved_manifest = path.resolve()
        manifest_bytes = resolved_manifest.read_bytes()
        manifest_bytes_sha256[resolved_manifest] = hashlib.sha256(
            manifest_bytes
        ).hexdigest().upper()
        _add_material_source_role(
            source_roles,
            resolved_manifest,
            f"{series}:production_manifest_candidate",
        )
        payload = json.loads(manifest_bytes.decode("utf-8-sig"))
        reason = str(payload.get("audience_exclusion_reason", "")).strip()
        if not reason:
            continue
        payload["event"] = validate_output_identifier(
            payload.get("event"), label=f"production manifest event ({path.name})"
        )
        errors = set(payload.get("quality_gates", {}).get("errors", []))
        if "audience_component_only" not in errors:
            raise ValueError(f"excluded event lacks component gate: {path}")
        event = str(payload["event"])
        source_roles[resolved_manifest].add(f"{event}:production_manifest")
        for clip in payload.get("clips", []):
            if not isinstance(clip, dict):
                continue
            _add_material_source_role(
                source_roles,
                Path(str(clip.get("path", ""))),
                f"{event}:visual_input",
            )
        for audio_index, audio_row in enumerate(payload.get("audio", [])):
            if not isinstance(audio_row, dict):
                continue
            audio_path = str(audio_row.get("path", "")).strip()
            if audio_path:
                _add_material_source_role(
                    source_roles,
                    Path(audio_path),
                    f"{event}:audio_input:{audio_index}",
                )
        manifests.append((resolved_manifest, payload))
    if not manifests:
        raise ValueError(f"no reviewed audience components found for {series}")

    source_snapshot_start = capture_material_source_snapshot(source_roles)
    snapshot_rows = {
        Path(str(row["path"])).resolve(): row
        for row in source_snapshot_start["sources"]
        if isinstance(row, dict)
    }
    for path, expected_sha256 in manifest_bytes_sha256.items():
        if str(snapshot_rows[path]["sha256"]) != expected_sha256:
            raise RuntimeError(
                f"material production manifest changed during discovery: {path}"
            )

    source_occurrences = []
    source_probe_cache: dict[str, dict] = {}
    source_sha_cache: dict[str, str] = {}
    source_video_hash_cache: dict[str, str] = {}
    audio_hash_cache: dict[str, str] = {}
    visual_semantic_gates: list[dict] = []
    signature: dict | None = None
    for manifest_path, payload in manifests:
        audited_audio = audit_official_audio_evidence(
            payload.get("audio", []), hash_cache=audio_hash_cache
        )
        transcript_evidence = copy.deepcopy(payload.get("subtitles", []))
        manifest_source_hashes: list[str] = []
        for clip_index, clip in enumerate(payload.get("clips", []), start=1):
            source_path = Path(str(clip.get("path", ""))).resolve()
            if not source_path.is_file():
                raise FileNotFoundError(source_path)
            key = str(source_path).casefold()
            source_probe = source_probe_cache.get(key)
            if source_probe is None:
                source_probe = probe(source_path, ffprobe)
                source_probe_cache[key] = source_probe
            source_signature = video_signature(source_probe)
            if signature is None:
                signature = source_signature
            elif source_signature != signature:
                raise ValueError(
                    f"material stream mismatch for {payload['event']}: "
                    f"{source_signature} != {signature}"
                )
            audio_streams = [
                row
                for row in source_probe.get("streams", [])
                if row.get("codec_type") == "audio"
            ]
            embedded_audio_peak_db = None
            if audio_streams:
                embedded_audio_peak_db = audio_peak_db(source_path, ffmpeg)
                if (
                    embedded_audio_peak_db is not None
                    and embedded_audio_peak_db > -90.0
                ):
                    raise ValueError(
                        "raw material source has audible embedded audio: "
                        f"{source_path} ({embedded_audio_peak_db} dB)"
                    )
            duration_ms = round(float(source_probe["format"]["duration"]) * 1000)
            source_sha256 = source_sha_cache.get(key)
            if source_sha256 is None:
                source_sha256 = file_sha256(source_path)
                source_sha_cache[key] = source_sha256
            manifest_source_hashes.append(source_sha256)
            source_video_packet_sha256 = source_video_hash_cache.get(key)
            if source_video_packet_sha256 is None:
                source_video_packet_sha256 = video_packet_hash(source_path, ffmpeg)
                source_video_hash_cache[key] = source_video_packet_sha256
            source_occurrences.append(
                {
                    "order": len(source_occurrences) + 1,
                    "event": str(payload.get("event", "")),
                    "dgm_name": str(clip.get("dgm_name", "")),
                    "clip_index": clip_index,
                    "start_ms": 0,
                    "end_ms": duration_ms,
                    "duration_ms": duration_ms,
                    "path": str(source_path),
                    "source_sha256": source_sha256,
                    "source_video_packet_sha256": source_video_packet_sha256,
                    "source_video_signature": source_signature,
                    "source_probe": source_probe,
                    "embedded_audio_dropped": bool(audio_streams),
                    "embedded_audio_peak_db": embedded_audio_peak_db,
                    "audience_exclusion_reason": str(
                        payload.get("audience_exclusion_reason", "")
                    ),
                    "official_audio_evidence": copy.deepcopy(audited_audio),
                    "transcript_evidence": copy.deepcopy(transcript_evidence),
                    "production_manifest": str(manifest_path.resolve()),
                }
            )
        review = payload.get("visual_semantic_review", payload.get("semantic_review"))
        gate = material_semantic_review_gate(
            review,
            expected_source_sha256s=manifest_source_hashes,
        )
        gate["event"] = str(payload.get("event", ""))
        gate["production_manifest"] = str(manifest_path.resolve())
        visual_semantic_gates.append(gate)
    sources = deduplicate_material_sources_by_av_signature(source_occurrences)
    visual_semantic_gate = aggregate_visual_semantic_gates(
        visual_semantic_gates
    )
    offset_ms = 0
    for order, source in enumerate(sources, start=1):
        source["order"] = order
        source["start_ms"] = offset_ms
        source["end_ms"] = offset_ms + int(source["duration_ms"])
        offset_ms = source["end_ms"]
    if len(sources) < 2:
        raise ValueError(f"{series} needs at least two unique AV material clips")
    if signature is None:
        raise ValueError(f"{series} has no material signature")

    width = signature["width"]
    height = signature["height"]
    rate_label = str(signature["r_frame_rate"]).replace("/", "-")
    collection_dir = resolve_output_child(out_root, series, label="collection")
    audit_dir = collection_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    list_path = audit_dir / "materials.ffconcat"
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(Path(row["path"])) for row in sources)
        + "\n",
        encoding="utf-8",
    )
    output_path = (
        collection_dir
        / f"{series}__material_components__{width}x{height}_{rate_label}.mp4"
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )
    label_path = collection_dir / f"{series}__material_labels.srt"
    write_label_srt(label_path, sources)
    output_probe = probe(output_path, ffprobe)
    errors: list[str] = []
    if video_signature(output_probe) != signature:
        errors.append("stream_signature_changed")
    output_duration_ms = round(float(output_probe["format"]["duration"]) * 1000)
    if abs(output_duration_ms - offset_ms) > max(100, len(sources) * 35):
        errors.append("duration_mismatch")
    if any(
        stream.get("codec_type") == "audio"
        for stream in output_probe.get("streams", [])
    ):
        errors.append("unexpected_audio_stream")

    audible_event_sources = []
    event_order = []
    sources_by_event: dict[str, list[dict]] = {}
    for source in sources:
        event = validate_output_identifier(
            source.get("event"), label="material source event"
        )
        if event not in sources_by_event:
            event_order.append(event)
            sources_by_event[event] = []
        sources_by_event[event].append(source)
    event_visuals_dir = ensure_resolved_containment(
        collection_dir,
        audit_dir / "audible_event_visuals",
        label="audible event visual directory",
    )
    event_visuals_dir.mkdir(parents=True, exist_ok=True)
    for event in event_order:
        event_sources = sources_by_event[event]
        if len(event_sources) == 1:
            event_source = dict(event_sources[0])
        else:
            event_list = ensure_resolved_containment(
                collection_dir,
                event_visuals_dir / f"{event}.ffconcat",
                label=f"{event} audible event concat list",
            )
            event_list.write_text(
                "ffconcat version 1.0\n"
                + "\n".join(
                    ffconcat_line(Path(row["path"])) for row in event_sources
                )
                + "\n",
                encoding="utf-8",
            )
            event_video = ensure_resolved_containment(
                collection_dir,
                event_visuals_dir / f"{event}.mp4",
                label=f"{event} audible event visual",
            )
            subprocess.run(
                [
                    ffmpeg,
                    "-y" if overwrite else "-n",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(event_list),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-c:v",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(event_video),
                ],
                check=True,
            )
            event_probe = probe(event_video, ffprobe)
            event_duration_ms = round(
                float(event_probe["format"]["duration"]) * 1000
            )
            expected_event_duration_ms = sum(
                int(row["duration_ms"]) for row in event_sources
            )
            if abs(event_duration_ms - expected_event_duration_ms) > max(
                100, len(event_sources) * 35
            ):
                raise RuntimeError(
                    f"{event} material event visual duration mismatch: "
                    f"{event_duration_ms} != {expected_event_duration_ms}"
                )
            event_source = dict(event_sources[0])
            event_source.update(
                {
                    "dgm_name": "+".join(
                        str(row["dgm_name"]) for row in event_sources
                    ),
                    "path": str(event_video.resolve()),
                    "start_ms": 0,
                    "end_ms": event_duration_ms,
                    "duration_ms": event_duration_ms,
                    "source_sha256": file_sha256(event_video),
                    "source_video_packet_sha256": video_packet_hash(
                        event_video, ffmpeg
                    ),
                    "source_probe": event_probe,
                }
            )
            merged_aliases = []
            for component_source in event_sources:
                for alias in component_source.get("source_event_aliases", []):
                    if alias not in merged_aliases:
                        merged_aliases.append(alias)
            event_source["source_event_aliases"] = merged_aliases
            event_source["source_occurrence_count"] = len(merged_aliases)
        event_source["component_count"] = len(event_sources)
        event_source["component_names"] = [
            str(row["dgm_name"]) for row in event_sources
        ]
        audible_event_sources.append(event_source)

    audible_render = render_audible_collection(
        collection_name=series,
        event_sources=audible_event_sources,
        collection_dir=collection_dir,
        audit_dir=audit_dir,
        signature=signature,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        overwrite=overwrite,
    )
    errors.extend(audible_render["errors"])
    audible_output_path = audible_render["output"]
    audible_label_path = audible_render["labels"]
    audible_output_probe = audible_render["probe"]
    audible_video = audible_render["video"]
    audible_audio = audible_render["audio"]
    audible_output_duration_ms = audible_render["duration_ms"]

    hybrid_slot_story = any(
        "hybrid" in str(row.get("audience_exclusion_reason", "")).casefold()
        for row in sources
    )
    role_voice_audio_rows = []
    non_dialogue_audio_rows = []
    unknown_audio_rows = []
    all_audio_rows = []
    for source in audible_event_sources:
        alias_events = sorted(
            {
                str(alias.get("event", "")).strip()
                for alias in source.get("source_event_aliases", [])
                if str(alias.get("event", "")).strip()
            }
            or {str(source["event"])},
            key=event_sort_key,
        )
        for audio_row in source.get("official_audio_evidence", []):
            if not isinstance(audio_row, dict):
                continue
            for alias_event in alias_events:
                audited_row = copy.deepcopy(audio_row)
                audited_row.update(
                    {
                        "event": alias_event,
                        "request_id": str(audio_row.get("request_id", "")),
                        "code_name": str(audio_row.get("code_name", "")),
                        "start_ms": int(audio_row.get("start_ms", 0)),
                        "duration_ms": int(audio_row.get("duration_ms", 0)),
                        "path": str(audio_row.get("path", "")),
                        "evidence": str(audio_row.get("evidence", "")),
                    }
                )
                semantic = classify_audio_semantic(audited_row)
                audited_row["semantic_audit"] = semantic
                all_audio_rows.append(audited_row)
                if semantic["semantic"] == "role_voice":
                    role_voice_audio_rows.append(audited_row)
                elif semantic["semantic"] == "non_dialogue":
                    non_dialogue_audio_rows.append(audited_row)
                else:
                    unknown_audio_rows.append(audited_row)
    role_voice_events = sorted(
        {row["event"] for row in role_voice_audio_rows}, key=event_sort_key
    )
    transcript_rows = []
    for source in audible_event_sources:
        alias_events = sorted(
            {
                str(alias.get("event", "")).strip()
                for alias in source.get("source_event_aliases", [])
                if str(alias.get("event", "")).strip()
            }
            or {str(source["event"])},
            key=event_sort_key,
        )
        for transcript_row in source.get("transcript_evidence", []):
            if not isinstance(transcript_row, dict):
                continue
            for alias_event in alias_events:
                audited_row = copy.deepcopy(transcript_row)
                audited_row["event"] = alias_event
                transcript_rows.append(audited_row)
    gameplay_marker = has_gameplay_marker(
        [
            *(str(row.get("dgm_name", "")) for row in sources),
            *(str(row.get("audience_exclusion_reason", "")) for row in sources),
            *(str(row.get("code_name", "")) for row in all_audio_rows),
        ]
    )
    lane = material_lane(
        role_voice_audio_count=len(role_voice_audio_rows),
        gameplay_marker=gameplay_marker,
        hybrid_slot_story=hybrid_slot_story,
    )
    transcript_required_hint = any(
        "transcript remains required"
        in str(row.get("audience_exclusion_reason", "")).casefold()
        for row in sources
    )
    release_gate = collection_release_gate(
        errors=errors,
        role_voice_audio_rows=role_voice_audio_rows,
        transcript_rows=transcript_rows,
        transcript_required_hint=transcript_required_hint,
        all_audio_rows=all_audio_rows,
        unknown_audio_rows=unknown_audio_rows,
        material_semantics_release_approved=True,
        visual_semantic_gate=visual_semantic_gate,
        audible_render_contract_applied=audible_render["contract_applied"],
    )
    source_snapshot_end = capture_material_source_snapshot(source_roles)
    source_rehash = _material_source_rehash_contract(
        source_snapshot_start, source_snapshot_end
    )
    manifest = {
        "schema": "magireco-material-component-collection-v6",
        "series": series,
        "status": release_gate["status"],
        "technical_qa_status": release_gate["technical_qa_status"],
        "publication_status": release_gate["publication_status"],
        "release_eligible": release_gate["release_eligible"],
        "publishable": release_gate["publishable"],
        "errors": errors,
        "classification": visual_semantic_gate["classification"],
        "semantic_lane": visual_semantic_gate["classification"],
        "visual_semantic_gate": visual_semantic_gate,
        "legacy_marker_lane_diagnostic_only": lane,
        "pure_material": bool(
            visual_semantic_gate["material_route_eligible"]
            and not role_voice_audio_rows
            and not unknown_audio_rows
        ),
        "role_voice_audio_count": len(role_voice_audio_rows),
        "non_dialogue_audio_count": len(non_dialogue_audio_rows),
        "unknown_audio_count": len(unknown_audio_rows),
        "role_voice_events": role_voice_events,
        "role_voice_audio": role_voice_audio_rows,
        "non_dialogue_audio": non_dialogue_audio_rows,
        "unknown_audio": unknown_audio_rows,
        "gameplay_marker": gameplay_marker,
        "transcript_required": release_gate["transcript_required"],
        "transcript_status": release_gate["transcript_status"],
        "visual_only_release_eligible": release_gate["visual_only_gate"][
            "release_eligible"
        ],
        "audible_review_release_eligible": release_gate["audible_review_gate"][
            "release_eligible"
        ],
        "transcript_verified": release_gate["transcript_verified"],
        "required_role_voice_key_count": release_gate[
            "required_role_voice_key_count"
        ],
        "verified_transcript_count": release_gate["verified_transcript_count"],
        "verified_transcripts": release_gate["verified_transcripts"],
        "missing_transcript_role_voice": release_gate[
            "missing_transcript_role_voice"
        ],
        "transcript_validation_errors": release_gate[
            "transcript_validation_errors"
        ],
        "audible_audio_contract_status": release_gate[
            "audible_audio_contract_status"
        ],
        "audible_audio_contract_verified": release_gate[
            "audible_audio_contract_verified"
        ],
        "audible_audio_contract_errors": release_gate[
            "audible_audio_contract_errors"
        ],
        "visual_only_gate": release_gate["visual_only_gate"],
        "audible_review_gate": release_gate["audible_review_gate"],
        "direct_video_stream_copy": True,
        "audible_video_reencoded_at_native_signature": bool(audible_output_path),
        "audible_status": audible_render["status"],
        "audible_encoding": audible_render["encoding"],
        "audible_render_contract_gate": audible_render.get(
            "contract_gate", {}
        ),
        "audible_missing_source_path_rows": audible_render.get(
            "missing_source_path_rows", []
        ),
        "audio_policy": (
            "the original visual-only collection remains a direct H.264 stream copy; "
            "audible review uses evidence-bound source_offset/duration, native gain and "
            "ducking; PCM event intermediates are followed by exactly one final AAC "
            "encode, with no unproven limiter; pure visual collections have no audible "
            "edition"
        ),
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "video_signature": signature,
        "output": str(output_path.resolve()),
        "labels": str(label_path.resolve()),
        "labels_sha256": file_sha256(label_path),
        "output_sha256": file_sha256(output_path),
        "output_video_packet_sha256": video_packet_hash(output_path, ffmpeg),
        "output_probe": output_probe,
        "audible_output": str(audible_output_path),
        "audible_labels": str(audible_label_path),
        "audible_labels_sha256": audible_render.get("labels_sha256", ""),
        "audible_duration_ms": audible_output_duration_ms,
        "audible_output_sha256": audible_render.get("output_sha256", ""),
        "audible_video_packet_sha256": audible_render.get(
            "video_packet_sha256", ""
        ),
        "audible_audio_packet_sha256": audible_render.get(
            "audio_packet_sha256", ""
        ),
        "audible_output_probe": audible_output_probe,
        "audible_event_sources": audible_event_sources,
        "sources": sources,
        "source_snapshot_start": source_snapshot_start,
        "source_snapshot_end": source_snapshot_end,
        "source_rehash": source_rehash,
    }
    manifest_path = collection_dir / "material_collection_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(f"{series} material collection QA failed: {errors}")
    return {
        "series": series,
        "status": release_gate["status"],
        "technical_qa_status": release_gate["technical_qa_status"],
        "publication_status": release_gate["publication_status"],
        "release_eligible": release_gate["release_eligible"],
        "publishable": release_gate["publishable"],
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "width": width,
        "height": height,
        "frame_rate": signature["r_frame_rate"],
        "output": str(output_path.resolve()),
        "audible_output": str(audible_output_path),
        "audible_duration_ms": audible_output_duration_ms,
        "audio_sample_rate": audible_audio.get("sample_rate", ""),
        "audio_channels": audible_audio.get("channels", 0),
        "manifest": str(manifest_path.resolve()),
        "visual_only_release_eligible": release_gate["visual_only_gate"][
            "release_eligible"
        ],
        "audible_review_release_eligible": release_gate["audible_review_gate"][
            "release_eligible"
        ],
        "semantic_lane": visual_semantic_gate["classification"],
        "pure_material": bool(
            visual_semantic_gate["material_route_eligible"]
            and not role_voice_audio_rows
            and not unknown_audio_rows
        ),
        "role_voice_audio_count": len(role_voice_audio_rows),
        "unknown_audio_count": len(unknown_audio_rows),
        "role_voice_events": "|".join(role_voice_events),
        "transcript_required": release_gate["transcript_required"],
        "transcript_status": release_gate["transcript_status"],
    }


def audio_signature(payload: dict) -> dict:
    stream = next(
        (
            row
            for row in payload.get("streams", [])
            if row.get("codec_type") == "audio"
        ),
        {},
    )
    return {
        key: stream.get(key, "")
        for key in (
            "codec_name",
            "sample_rate",
            "channels",
            "channel_layout",
            "time_base",
        )
    }


def audio_peak_db(path: Path, ffmpeg: str) -> float | None:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "NUL",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    match = re.search(r"max_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB", result.stderr)
    if not match or match.group(1) == "-inf":
        return None
    return float(match.group(1))


def read_video_map(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return {
            str(row.get("official_name", "")).casefold(): row
            for row in csv.DictReader(source)
            if str(row.get("official_name", "")).strip()
        }


def _build_named_collection_in_place(
    plan_path: Path,
    video_map: dict[str, dict[str, str]],
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    resolved_plan = plan_path.resolve()
    plan_bytes = resolved_plan.read_bytes()
    plan_bytes_sha256 = hashlib.sha256(plan_bytes).hexdigest().upper()
    plan = json.loads(plan_bytes.decode("utf-8-sig"))
    collection = str(plan.get("collection", "")).strip()
    if not collection:
        raise ValueError(f"named material plan has no collection: {plan_path}")
    collection = validate_output_identifier(collection, label="plan.collection")
    planned_clips = plan.get("clips", [])
    if not isinstance(planned_clips, list) or len(planned_clips) < 2:
        raise ValueError(f"named material plan needs at least two clips: {plan_path}")
    source_roles: dict[Path, set[str]] = {}
    _add_material_source_role(
        source_roles, resolved_plan, f"{collection}:named_source_plan"
    )
    evidence_sources = plan.get("evidence_sources", [])
    if not isinstance(evidence_sources, list):
        raise ValueError(
            f"named material plan evidence_sources must be a list: {plan_path}"
        )
    resolved_evidence_sources: list[dict[str, str]] = []
    for evidence_index, raw_evidence in enumerate(evidence_sources, start=1):
        if not isinstance(raw_evidence, dict):
            raise ValueError(
                "named material plan evidence source "
                f"{evidence_index} is not an object"
            )
        raw_path = str(raw_evidence.get("path", "")).strip()
        expected_sha256 = str(raw_evidence.get("sha256", "")).strip().upper()
        label = str(raw_evidence.get("label", "")).strip()
        if not raw_path or not label or not SHA256_RE.fullmatch(expected_sha256):
            raise ValueError(
                "named material plan evidence source "
                f"{evidence_index} requires path, label and SHA-256"
            )
        evidence_path = Path(raw_path)
        if not evidence_path.is_absolute():
            evidence_path = resolved_plan.parent / evidence_path
        evidence_path = evidence_path.resolve()
        if not evidence_path.is_file():
            raise FileNotFoundError(evidence_path)
        actual_sha256 = file_sha256(evidence_path)
        if actual_sha256 != expected_sha256:
            raise ValueError(
                "named material evidence SHA-256 mismatch for "
                f"{evidence_path}: expected={expected_sha256}, "
                f"actual={actual_sha256}"
            )
        _add_material_source_role(
            source_roles,
            evidence_path,
            f"{collection}:evidence_source:{evidence_index}:{label}",
        )
        resolved_evidence_sources.append(
            {
                "label": label,
                "path": str(evidence_path),
                "sha256": expected_sha256,
            }
        )
    covered_events_raw = plan.get("covered_events", [])
    if not isinstance(covered_events_raw, list):
        raise ValueError(
            f"named material plan covered_events must be a list: {plan_path}"
        )
    covered_events = [str(event).strip() for event in covered_events_raw]
    if any(not EVENT_NAME_RE.fullmatch(event) for event in covered_events):
        raise ValueError("named material plan covered_events contains invalid event")
    if len(set(covered_events)) != len(covered_events):
        raise ValueError("named material plan covered_events contains duplicates")
    resolved_evidence_sources.extend(
        resolve_covered_event_index(
            plan.get("covered_event_index"),
            plan_path=resolved_plan,
            covered_events=covered_events,
            source_roles=source_roles,
            collection=collection,
        )
    )
    if covered_events:
        evidence_events = set()
        for evidence in resolved_evidence_sources:
            evidence_path = Path(evidence["path"])
            if evidence_path.suffix.casefold() != ".json":
                continue
            try:
                evidence_payload = json.loads(
                    evidence_path.read_text(encoding="utf-8-sig")
                )
            except (UnicodeError, json.JSONDecodeError):
                continue
            event = str(evidence_payload.get("event", "")).strip()
            if (
                str(evidence_payload.get("schema", "")).startswith(
                    "magireco-event-production-"
                )
                and EVENT_NAME_RE.fullmatch(event)
            ):
                evidence_events.add(event)
        if evidence_events != set(covered_events):
            raise ValueError(
                "named material covered_events do not match bound event "
                f"production manifests: declared={sorted(covered_events)}, "
                f"evidence={sorted(evidence_events)}"
            )
    source_root_overrides = plan.get("source_root_overrides", [])
    if not isinstance(source_root_overrides, list):
        raise ValueError(
            f"named material plan source_root_overrides must be a list: {plan_path}"
        )
    resolved_source_root_overrides: list[dict[str, str]] = []
    for override_index, raw_override in enumerate(
        source_root_overrides, start=1
    ):
        if not isinstance(raw_override, dict):
            raise ValueError(
                "named material source root override "
                f"{override_index} is not an object"
            )
        source_root = Path(str(raw_override.get("from", "")).strip())
        durable_root = Path(str(raw_override.get("to", "")).strip())
        if not source_root.is_absolute() or not durable_root.is_absolute():
            raise ValueError(
                "named material source root override "
                f"{override_index} requires absolute from/to paths"
            )
        durable_root = durable_root.resolve()
        if not durable_root.is_dir():
            raise FileNotFoundError(durable_root)
        resolved_source_root_overrides.append(
            {"from": str(source_root), "to": str(durable_root)}
        )

    def resolve_named_source(map_row: dict[str, str]) -> Path:
        raw_path = str(
            map_row.get("target_mp4") or map_row.get("source_mp4") or ""
        ).strip()
        if not raw_path:
            return Path()
        mapped_path = Path(raw_path)
        for override in resolved_source_root_overrides:
            try:
                relative = mapped_path.relative_to(Path(override["from"]))
            except ValueError:
                continue
            return (Path(override["to"]) / relative).resolve()
        return mapped_path.resolve()

    for clip_index, planned in enumerate(planned_clips, start=1):
        if not isinstance(planned, dict):
            raise ValueError(
                f"named material plan clip {clip_index} is not an object"
            )
        official_name = str(planned.get("official_name", "")).strip()
        map_row = video_map.get(official_name.casefold(), {})
        source_path = resolve_named_source(map_row)
        if not source_path.is_file():
            raise FileNotFoundError(
                f"unresolved named material {official_name}: {source_path}"
            )
        _add_material_source_role(
            source_roles,
            source_path,
            f"{collection}:visual_or_embedded_audio_input:{clip_index}",
        )
        for audio_index, audio_row in enumerate(planned.get("audio", [])):
            if not isinstance(audio_row, dict):
                continue
            audio_path = str(audio_row.get("path", "")).strip()
            if audio_path:
                _add_material_source_role(
                    source_roles,
                    Path(audio_path),
                    f"{collection}:audio_input:{clip_index}:{audio_index}",
                )
    source_snapshot_start = capture_material_source_snapshot(source_roles)
    plan_snapshot_row = next(
        row
        for row in source_snapshot_start["sources"]
        if isinstance(row, dict)
        and Path(str(row.get("path", ""))).resolve() == resolved_plan
    )
    if str(plan_snapshot_row["sha256"]) != plan_bytes_sha256:
        raise RuntimeError(
            f"named material plan changed during discovery: {resolved_plan}"
        )
    source_occurrences = []
    audio_hash_cache: dict[str, str] = {}
    signature: dict | None = None
    embedded_audio_signatures: list[dict[str, object]] = []
    for clip_index, planned in enumerate(planned_clips, start=1):
        official_name = str(planned.get("official_name", "")).strip()
        map_row = video_map.get(official_name.casefold(), {})
        source_path = resolve_named_source(map_row)
        if not source_path.is_file():
            raise FileNotFoundError(
                f"unresolved named material {official_name}: {source_path}"
            )
        source_probe = probe(source_path, ffprobe)
        source_signature = video_signature(source_probe)
        source_audio_signature = audio_signature(source_probe)
        if signature is None:
            signature = source_signature
        elif source_signature != signature:
            raise ValueError(
                f"named material video mismatch for {official_name}: "
                f"{source_signature} != {signature}"
            )
        if source_audio_signature.get("codec_name") and (
            source_audio_signature not in embedded_audio_signatures
        ):
            embedded_audio_signatures.append(source_audio_signature)
        duration_ms = round(float(source_probe["format"]["duration"]) * 1000)
        peak_db = (
            audio_peak_db(source_path, ffmpeg)
            if source_audio_signature.get("codec_name")
            else None
        )
        planned_audio = audit_official_audio_evidence(
            planned.get("audio", []), hash_cache=audio_hash_cache
        )
        if (
            source_audio_signature.get("codec_name")
            and peak_db is not None
            and not planned_audio
        ):
            # An audible embedded track with no semantic/mix evidence must not
            # disappear from the unified gate merely because it is muxed.
            planned_audio = [
                {
                    "path": str(source_path),
                    "source_sha256": file_sha256(source_path),
                    "request_id": "",
                    "code_name": official_name,
                    "start_ms": 0,
                    "duration_ms": duration_ms,
                    "evidence": "embedded_audio_without_release_contract",
                    "semantic_audit": {
                        "semantic": "unknown",
                        "status": "unresolved",
                        "basis": "",
                        "reason": "semantic_evidence_missing",
                    },
                }
            ]
        source_occurrences.append(
            {
                "order": len(source_occurrences) + 1,
                "event": str(planned.get("label") or official_name),
                "dgm_name": official_name,
                "official_name": official_name,
                "clip_index": clip_index,
                "start_ms": 0,
                "end_ms": duration_ms,
                "duration_ms": duration_ms,
                "path": str(source_path),
                "source_sha256": file_sha256(source_path),
                "source_video_packet_sha256": video_packet_hash(source_path, ffmpeg),
                "source_audio_packet_sha256": (
                    audio_packet_hash(source_path, ffmpeg)
                    if source_audio_signature.get("codec_name")
                    else ""
                ),
                "source_audio_signature": source_audio_signature,
                "source_audio_peak_db": peak_db,
                "source_video_signature": source_signature,
                "official_audio_evidence": planned_audio,
                "transcript_evidence": copy.deepcopy(
                    planned.get("subtitles", [])
                ),
                "production_manifest": str(plan_path.resolve()),
                "source_probe": source_probe,
            }
        )
    sources = deduplicate_material_sources_by_av_signature(source_occurrences)
    offset_ms = 0
    for order, source in enumerate(sources, start=1):
        source["order"] = order
        source["start_ms"] = offset_ms
        source["end_ms"] = offset_ms + int(source["duration_ms"])
        offset_ms = source["end_ms"]
    if signature is None:
        raise ValueError(f"named material plan resolved no sources: {plan_path}")
    if len(sources) < 2:
        raise ValueError(
            f"named material plan needs at least two unique AV clips: {plan_path}"
        )

    width = signature["width"]
    height = signature["height"]
    rate_label = str(signature["r_frame_rate"]).replace("/", "-")
    collection_dir = resolve_output_child(
        out_root, collection, label="plan.collection"
    )
    audit_dir = collection_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    list_path = audit_dir / "materials.ffconcat"
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(Path(row["path"])) for row in sources)
        + "\n",
        encoding="utf-8",
    )
    output_path = (
        collection_dir
        / f"{collection}__material_components__{width}x{height}_{rate_label}.mp4"
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    command = [
        ffmpeg,
        "-y" if overwrite else "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(command, check=True)
    label_path = collection_dir / f"{collection}__material_labels.srt"
    write_label_srt(label_path, sources)
    output_probe = probe(output_path, ffprobe)
    errors = []
    if video_signature(output_probe) != signature:
        errors.append("stream_signature_changed")
    if any(
        stream.get("codec_type") == "audio"
        for stream in output_probe.get("streams", [])
    ):
        errors.append("unexpected_audio_stream")
    output_duration_ms = round(float(output_probe["format"]["duration"]) * 1000)
    if abs(output_duration_ms - offset_ms) > max(100, len(sources) * 35):
        errors.append("duration_mismatch")
    output_peak_db = None
    expected_audio_state = str(plan.get("expected_audio_state", "")).strip()
    if expected_audio_state == "digital_silence" and (
        output_peak_db is not None and output_peak_db > -90.0
    ):
        errors.append("expected_digital_silence_but_audio_is_audible")

    all_audio_rows = []
    role_voice_audio_rows = []
    non_dialogue_audio_rows = []
    unknown_audio_rows = []
    transcript_rows = []
    for source in sources:
        alias_events = sorted(
            {
                str(alias.get("event", "")).strip()
                for alias in source.get("source_event_aliases", [])
                if str(alias.get("event", "")).strip()
            }
            or {str(source["event"])},
            key=event_sort_key,
        )
        for audio_row in source.get("official_audio_evidence", []):
            for alias_event in alias_events:
                audited_row = copy.deepcopy(audio_row)
                audited_row["event"] = alias_event
                semantic = classify_audio_semantic(audited_row)
                audited_row["semantic_audit"] = semantic
                all_audio_rows.append(audited_row)
                if semantic["semantic"] == "role_voice":
                    role_voice_audio_rows.append(audited_row)
                elif semantic["semantic"] == "non_dialogue":
                    non_dialogue_audio_rows.append(audited_row)
                else:
                    unknown_audio_rows.append(audited_row)
        for cue in source.get("transcript_evidence", []):
            if not isinstance(cue, dict):
                continue
            for alias_event in alias_events:
                audited_cue = copy.deepcopy(cue)
                audited_cue["event"] = alias_event
                transcript_rows.append(audited_cue)
    for cue in plan.get("subtitles", []):
        if isinstance(cue, dict):
            transcript_rows.append(copy.deepcopy(cue))

    semantic_review = material_semantic_review_gate(
        plan.get("visual_semantic_review", plan.get("semantic_review")),
        expected_source_sha256s={
            str(source.get("source_sha256", "")) for source in sources
        },
    )
    visual_semantic_gate = aggregate_visual_semantic_gates([semantic_review])
    release_gate = collection_release_gate(
        errors=errors,
        role_voice_audio_rows=role_voice_audio_rows,
        transcript_rows=transcript_rows,
        transcript_required_hint=bool(plan.get("transcript_required", False)),
        all_audio_rows=all_audio_rows,
        unknown_audio_rows=unknown_audio_rows,
        material_semantics_release_approved=True,
        visual_semantic_gate=visual_semantic_gate,
        # This function is a review compositor.  A plan-supplied boolean is not
        # evidence that a release authorization or native mix was applied.
        explicit_release_authorized=False,
        audible_render_contract_applied=False,
    )
    source_snapshot_end = capture_material_source_snapshot(source_roles)
    source_rehash = _material_source_rehash_contract(
        source_snapshot_start, source_snapshot_end
    )
    manifest = {
        "schema": "magireco-named-material-collection-v4",
        "collection": collection,
        "status": release_gate["status"],
        "technical_qa_status": release_gate["technical_qa_status"],
        "publication_status": release_gate["publication_status"],
        "release_eligible": release_gate["release_eligible"],
        "publishable": release_gate["publishable"],
        "errors": errors,
        "classification": str(plan.get("classification", "material_components")),
        "semantic_review": semantic_review,
        "visual_semantic_gate": visual_semantic_gate,
        "explicit_release_authorized": False,
        "plan_release_authorized_flag_ignored": (
            plan.get("release_authorized") is True
        ),
        "plan_embedded_native_mix_verified_flag_ignored": (
            plan.get("embedded_native_mix_verified") is True
        ),
        "renderer_release_capability": "review_only",
        "role_voice_audio_count": len(role_voice_audio_rows),
        "non_dialogue_audio_count": len(non_dialogue_audio_rows),
        "unknown_audio_count": len(unknown_audio_rows),
        "role_voice_audio": role_voice_audio_rows,
        "non_dialogue_audio": non_dialogue_audio_rows,
        "unknown_audio": unknown_audio_rows,
        "transcript_required": release_gate["transcript_required"],
        "transcript_status": release_gate["transcript_status"],
        "transcript_verified": release_gate["transcript_verified"],
        "verified_transcripts": release_gate["verified_transcripts"],
        "missing_transcript_role_voice": release_gate[
            "missing_transcript_role_voice"
        ],
        "transcript_validation_errors": release_gate[
            "transcript_validation_errors"
        ],
        "audible_audio_contract_status": release_gate[
            "audible_audio_contract_status"
        ],
        "audible_audio_contract_verified": release_gate[
            "audible_audio_contract_verified"
        ],
        "audible_audio_contract_errors": release_gate[
            "audible_audio_contract_errors"
        ],
        "visual_only_gate": release_gate["visual_only_gate"],
        "audible_review_gate": release_gate["audible_review_gate"],
        "evidence": str(plan.get("evidence", "")),
        "evidence_sources": resolved_evidence_sources,
        "covered_events": covered_events,
        "source_root_overrides": resolved_source_root_overrides,
        "direct_stream_copy": True,
        "visual_only_output": True,
        "embedded_audio_dropped": bool(embedded_audio_signatures),
        "audible_status": (
            "blocked_contract"
            if all_audio_rows
            else "not_applicable"
        ),
        "aac_segment_packet_copy": False,
        "expected_audio_state": expected_audio_state,
        "output_audio_peak_db": output_peak_db,
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "video_signature": signature,
        "embedded_audio_signature": (
            embedded_audio_signatures[0]
            if len(embedded_audio_signatures) == 1
            else (
                {
                    "mode": "mixed_source_audio_signatures_dropped",
                    "signatures": embedded_audio_signatures,
                }
                if embedded_audio_signatures
                else audio_signature({})
            )
        ),
        "embedded_audio_signatures": embedded_audio_signatures,
        "output": str(output_path.resolve()),
        "labels": str(label_path.resolve()),
        "labels_sha256": file_sha256(label_path),
        "output_sha256": file_sha256(output_path),
        "output_video_packet_sha256": video_packet_hash(output_path, ffmpeg),
        "output_audio_packet_sha256": "",
        "output_probe": output_probe,
        "source_plan": str(plan_path.resolve()),
        "sources": sources,
        "audible_output": "",
        "audible_labels": "",
        "audible_labels_sha256": "",
        "audible_output_sha256": "",
        "source_snapshot_start": source_snapshot_start,
        "source_snapshot_end": source_snapshot_end,
        "source_rehash": source_rehash,
    }
    manifest_path = collection_dir / "material_collection_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(
            f"{collection} named material collection QA failed: {errors}"
        )
    return {
        "series": collection,
        "status": release_gate["status"],
        "technical_qa_status": release_gate["technical_qa_status"],
        "publication_status": release_gate["publication_status"],
        "release_eligible": release_gate["release_eligible"],
        "publishable": release_gate["publishable"],
        "clip_count": len(sources),
        "duration_ms": output_duration_ms,
        "width": width,
        "height": height,
        "frame_rate": signature["r_frame_rate"],
        "audio_sample_rate": "",
        "audio_channels": 0,
        "audio_peak_db": output_peak_db,
        "output": str(output_path.resolve()),
        "manifest": str(manifest_path.resolve()),
        "visual_only_release_eligible": release_gate["visual_only_gate"][
            "release_eligible"
        ],
        "audible_review_release_eligible": release_gate["audible_review_gate"][
            "release_eligible"
        ],
    }


def _rebase_staged_paths(value: object, staged_dir: Path, published_dir: Path) -> object:
    """Translate only paths rooted in a staging collection directory."""

    staged = str(staged_dir.resolve())
    published = str(published_dir.resolve())
    if isinstance(value, dict):
        return {
            key: _rebase_staged_paths(item, staged_dir, published_dir)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rebase_staged_paths(item, staged_dir, published_dir) for item in value]
    if isinstance(value, str) and value.casefold().startswith(staged.casefold()):
        return published + value[len(staged):]
    return value


def _verify_published_material_manifest(
    *,
    published_dir: Path,
    manifest_name: str,
    expected_sha256: str,
) -> dict:
    """Read back the promoted manifest and verify its exact staged hash."""

    published_manifest = published_dir / manifest_name
    if not published_manifest.is_file():
        raise RuntimeError("published material manifest is missing")
    if file_sha256(published_manifest) != expected_sha256:
        raise RuntimeError("published material manifest hash changed during promotion")
    manifest = json.loads(published_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("published material manifest is not a JSON object")
    return manifest


def _verify_published_material_ready(
    *,
    published_dir: Path,
    expected_payload: dict,
) -> dict:
    """Verify that READY survived promotion byte-semantically intact."""

    ready_path = published_dir / "READY.json"
    if not ready_path.is_file():
        raise RuntimeError("published material READY marker is missing")
    if (published_dir / ".READY.json.tmp").exists():
        raise RuntimeError("published material READY temporary marker remains")
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    if ready != expected_payload:
        raise RuntimeError("published material READY payload changed during promotion")
    return ready


def _published_material_file(
    *,
    published_dir: Path,
    value: object,
    label: str,
) -> Path:
    """Resolve one critical artifact and keep it inside its published tree."""

    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"published material {label} path is missing")
    path = Path(text).resolve()
    try:
        path.relative_to(published_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"published material {label} escapes collection directory: {path}"
        ) from exc
    if not path.is_file():
        raise RuntimeError(f"published material {label} is missing: {path}")
    return path


def _verify_published_material_outputs(
    *,
    published_dir: Path,
    manifest: dict,
    ready: dict,
) -> None:
    """Hash-check the promoted visual/audible videos and audit label files."""

    visual_output = str(manifest.get("output", "")).strip()
    if visual_output != str(ready.get("visual_output", "")).strip():
        raise RuntimeError("published material visual output path disagrees with READY")
    visual_path = _published_material_file(
        published_dir=published_dir,
        value=visual_output,
        label="visual output",
    )
    expected_visual_hash = str(manifest.get("output_sha256", "")).strip().upper()
    if not expected_visual_hash or file_sha256(visual_path) != expected_visual_hash:
        raise RuntimeError("published material visual output hash mismatch")

    visual_labels = str(manifest.get("labels", "")).strip()
    if visual_labels != str(ready.get("visual_labels", "")).strip():
        raise RuntimeError(
            "published material visual labels path disagrees with READY"
        )
    visual_label_path = _published_material_file(
        published_dir=published_dir,
        value=visual_labels,
        label="visual labels",
    )
    expected_visual_label_hash = str(
        manifest.get("labels_sha256", "")
    ).strip().upper()
    ready_visual_label_hash = str(
        ready.get("visual_labels_sha256", "")
    ).strip().upper()
    if (
        not _valid_sha256(expected_visual_label_hash)
        or ready_visual_label_hash != expected_visual_label_hash
        or file_sha256(visual_label_path) != expected_visual_label_hash
    ):
        raise RuntimeError("published material visual labels hash mismatch")

    audible_output = str(manifest.get("audible_output", "")).strip()
    ready_audible_output = str(ready.get("audible_output", "")).strip()
    if audible_output != ready_audible_output:
        raise RuntimeError("published material audible output path disagrees with READY")
    audible_status = str(manifest.get("audible_status", "")).strip()
    if audible_status == "rendered" and not audible_output:
        raise RuntimeError("rendered material audible output path is missing")
    if audible_output:
        audible_path = _published_material_file(
            published_dir=published_dir,
            value=audible_output,
            label="audible output",
        )
        expected_audible_hash = str(
            manifest.get("audible_output_sha256", "")
        ).strip().upper()
        if (
            not expected_audible_hash
            or file_sha256(audible_path) != expected_audible_hash
        ):
            raise RuntimeError("published material audible output hash mismatch")
        audible_labels = str(manifest.get("audible_labels", "")).strip()
        if audible_labels != str(ready.get("audible_labels", "")).strip():
            raise RuntimeError(
                "published material audible labels path disagrees with READY"
            )
        audible_label_path = _published_material_file(
            published_dir=published_dir,
            value=audible_labels,
            label="audible labels",
        )
        expected_audible_label_hash = str(
            manifest.get("audible_labels_sha256", "")
        ).strip().upper()
        ready_audible_label_hash = str(
            ready.get("audible_labels_sha256", "")
        ).strip().upper()
        if (
            not _valid_sha256(expected_audible_label_hash)
            or ready_audible_label_hash != expected_audible_label_hash
            or file_sha256(audible_label_path) != expected_audible_label_hash
        ):
            raise RuntimeError("published material audible labels hash mismatch")
    elif any(
        str(value or "").strip()
        for value in (
            manifest.get("audible_labels"),
            manifest.get("audible_labels_sha256"),
            ready.get("audible_labels"),
            ready.get("audible_labels_sha256"),
        )
    ):
        raise RuntimeError(
            "material without audible output has an audible labels contract"
        )


def _rollback_material_promotion(
    *,
    published_dir: Path,
    previous_dir: Path | None,
) -> None:
    """Quarantine a bad promotion, restore the old tree, then remove quarantine."""

    failed_dir: Path | None = None
    if published_dir.exists():
        failed_dir = published_dir.parent / (
            f".{published_dir.name}.failed-{uuid.uuid4().hex}"
        )
        published_dir.replace(failed_dir)
    if previous_dir is not None:
        if not previous_dir.exists():
            raise RuntimeError("previous material collection vanished during rollback")
        previous_dir.replace(published_dir)
    if failed_dir is not None:
        shutil.rmtree(failed_dir)


def _promote_material_collection(
    *,
    staged_dir: Path,
    published_dir: Path,
    summary: dict,
    overwrite: bool,
) -> dict:
    """Write READY last and promote a complete same-volume directory."""

    staged_manifest = staged_dir / "material_collection_manifest.json"
    if not staged_manifest.is_file():
        raise RuntimeError("staged material collection lacks manifest")
    manifest = json.loads(staged_manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("staged material manifest is not a JSON object")
    _verify_material_source_contract(manifest, stage="pre-READY")
    staged_artifact_contract = {
        "visual_output": str(manifest.get("output", "")),
        "visual_labels": str(manifest.get("labels", "")),
        "visual_labels_sha256": str(manifest.get("labels_sha256", "")),
        "audible_output": str(manifest.get("audible_output", "")),
        "audible_labels": str(manifest.get("audible_labels", "")),
        "audible_labels_sha256": str(
            manifest.get("audible_labels_sha256", "")
        ),
    }
    _verify_published_material_outputs(
        published_dir=staged_dir,
        manifest=manifest,
        ready=staged_artifact_contract,
    )
    manifest = _rebase_staged_paths(manifest, staged_dir, published_dir)
    staged_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = _rebase_staged_paths(summary, staged_dir, published_dir)
    manifest_sha256 = file_sha256(staged_manifest)
    ready_payload = {
        "schema": "magireco-material-collection-ready-v2",
        "status": "READY",
        "collection": str(summary.get("series", published_dir.name)),
        "build_status": str(summary.get("status", "")),
        "technical_qa_status": str(summary.get("technical_qa_status", "")),
        "publication_status": str(summary.get("publication_status", "")),
        "release_eligible": bool(summary.get("release_eligible", False)),
        "visual_only_release_eligible": bool(
            summary.get("visual_only_release_eligible", False)
        ),
        "audible_review_release_eligible": summary.get(
            "audible_review_release_eligible"
        ),
        "manifest": str((published_dir / staged_manifest.name).resolve()),
        "manifest_sha256": manifest_sha256,
        "visual_output": str(summary.get("output", "")),
        "visual_labels": str(manifest.get("labels", "")),
        "visual_labels_sha256": str(manifest.get("labels_sha256", "")),
        "audible_output": str(summary.get("audible_output", "")),
        "audible_labels": str(manifest.get("audible_labels", "")),
        "audible_labels_sha256": str(
            manifest.get("audible_labels_sha256", "")
        ),
        "source_rehash": copy.deepcopy(manifest.get("source_rehash")),
        "publication_rule": (
            "READY certifies a complete transactional review artifact; only "
            "release_eligible=true permits publication"
        ),
    }
    ready_path = staged_dir / "READY.json"
    ready_temp = staged_dir / ".READY.json.tmp"
    ready_temp.write_text(
        json.dumps(ready_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ready_temp.replace(ready_path)
    _verify_material_source_contract(manifest, stage="pre-promotion")

    previous_dir: Path | None = None
    if published_dir.exists():
        if not overwrite:
            raise FileExistsError(
                "READY material collection already exists; pass --overwrite: "
                f"{published_dir}"
            )
        previous_dir = published_dir.parent / (
            f".{published_dir.name}.previous-{uuid.uuid4().hex}"
        )
        published_dir.replace(previous_dir)
    try:
        staged_dir.replace(published_dir)
        published_manifest = _verify_published_material_manifest(
            published_dir=published_dir,
            manifest_name=staged_manifest.name,
            expected_sha256=manifest_sha256,
        )
        published_ready = _verify_published_material_ready(
            published_dir=published_dir,
            expected_payload=ready_payload,
        )
        _verify_published_material_outputs(
            published_dir=published_dir,
            manifest=published_manifest,
            ready=published_ready,
        )
        _verify_material_source_contract(
            published_manifest, stage="post-promotion"
        )
    except BaseException:
        try:
            _rollback_material_promotion(
                published_dir=published_dir,
                previous_dir=previous_dir,
            )
        except BaseException as rollback_error:
            raise RuntimeError(
                "material collection promotion failed and rollback was incomplete"
            ) from rollback_error
        raise
    if previous_dir is not None:
        shutil.rmtree(previous_dir)
    return summary


def _transactional_material_build(
    *,
    collection_name: str,
    out_root: Path,
    overwrite: bool,
    build,
) -> dict:
    collection_name = validate_output_identifier(
        collection_name, label="collection"
    )
    published_dir = resolve_output_child(
        out_root, collection_name, label="collection"
    )
    if published_dir.exists() and not overwrite:
        marker = "READY " if (published_dir / "READY.json").is_file() else ""
        raise FileExistsError(
            f"{marker}material collection already exists; pass --overwrite: "
            f"{published_dir}"
        )
    out_root.mkdir(parents=True, exist_ok=True)
    staging_container = Path(
        tempfile.mkdtemp(
            prefix=f".material-staging-{uuid.uuid4().hex[:12]}-",
            dir=out_root,
        )
    )
    staged_dir = resolve_output_child(
        staging_container, collection_name, label="collection"
    )
    try:
        summary = build(staging_container)
        return _promote_material_collection(
            staged_dir=staged_dir,
            published_dir=published_dir,
            summary=summary,
            overwrite=overwrite,
        )
    finally:
        shutil.rmtree(staging_container, ignore_errors=True)


def build_collection(
    series: str,
    manifest_dir: Path,
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    """Build and transactionally publish one manifest-driven collection."""

    return _transactional_material_build(
        collection_name=series,
        out_root=out_root,
        overwrite=overwrite,
        build=lambda staging_root: _build_collection_in_place(
            series,
            manifest_dir,
            staging_root,
            ffmpeg,
            ffprobe,
            True,
        ),
    )


def build_named_collection(
    plan_path: Path,
    video_map: dict[str, dict[str, str]],
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict:
    """Build and transactionally publish one named-plan collection."""

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    collection = str(plan.get("collection", "")).strip()
    if not collection:
        raise ValueError(f"named material plan has no collection: {plan_path}")
    collection = validate_output_identifier(collection, label="plan.collection")
    return _transactional_material_build(
        collection_name=collection,
        out_root=out_root,
        overwrite=overwrite,
        build=lambda staging_root: _build_named_collection_in_place(
            plan_path,
            video_map,
            staging_root,
            ffmpeg,
            ffprobe,
            True,
        ),
    )


def main() -> int:
    args = parse_args()
    requested_series = [
        validate_output_identifier(series, label="collection")
        for series in args.series
    ]
    plan_paths = [Path(plan) for plan in args.plan]
    # Plan files are read-only preflight inputs.  Validate every collection
    # before creating even the common output root; the build rereads and
    # revalidates the plan to close a replacement/TOCTOU window.
    for plan_path in plan_paths:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        collection = str(plan.get("collection", "")).strip()
        if not collection:
            raise ValueError(f"named material plan has no collection: {plan_path}")
        validate_output_identifier(collection, label="plan.collection")
    root = Path(args.manifest_root).resolve()
    manifest_dir = root / "events" if (root / "events").is_dir() else root
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for series in requested_series:
        row = build_collection(
            series,
            manifest_dir,
            out_root,
            args.ffmpeg,
            args.ffprobe,
            args.overwrite,
        )
        rows.append(row)
        print(
            f"[{row['status']}] {series}: {row['clip_count']} material clips",
            flush=True,
        )
    if args.plan:
        video_map = read_video_map(Path(args.video_map))
        for plan in plan_paths:
            row = build_named_collection(
                plan,
                video_map,
                out_root,
                args.ffmpeg,
                args.ffprobe,
                args.overwrite,
            )
            rows.append(row)
            print(
                f"[{row['status']}] {row['series']}: "
                f"{row['clip_count']} named material clips",
                flush=True,
            )
    summary = {
        "schema": "magireco-material-collection-summary-v5",
        "collection_count": len(rows),
        "passed": sum(row.get("status") == "passed" for row in rows),
        "review_only": sum(row.get("status") == "review_only" for row in rows),
        "failed": sum(row.get("status") == "failed" for row in rows),
        "release_eligible": sum(
            bool(row.get("release_eligible", False)) for row in rows
        ),
        "publishable": sum(bool(row.get("publishable", False)) for row in rows),
        "visual_only_release_eligible": sum(
            bool(row.get("visual_only_release_eligible", False)) for row in rows
        ),
        "audible_review_release_eligible": sum(
            bool(row.get("audible_review_release_eligible", False)) for row in rows
        ),
        "direct_video_stream_copy": True,
        "audible_review_edition": True,
        "collections": rows,
    }
    (out_root / "material_collection_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
