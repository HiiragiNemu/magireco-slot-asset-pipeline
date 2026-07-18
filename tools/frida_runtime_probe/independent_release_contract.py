#!/usr/bin/env python3
"""Fail-closed contract for the first independently releasable edition.

The existing archive pipeline deliberately treats the complete two-audio by
three-subtitle matrix as one transaction.  This module does not relax that
contract.  It defines a separate, explicitly named product whose BUILD_READY
marker proves only that the no-BGM Chinese-dialogue candidate and its automatic
QA artifacts are complete.  Human playback approval and Bilibili release
approval remain separate attestations and are always false in this schema.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

try:
    from .output_path_contract import validate_output_identifier
except ImportError:  # direct script execution
    from output_path_contract import validate_output_identifier  # type: ignore


RELEASE_PROFILE = "bilibili_no_bgm_zh_v1"
RELEASE_CONTRACT_SCHEMA = "magireco-independent-edition-release-contract-v1"
BUILD_READY_SCHEMA = "magireco-independent-edition-build-ready-v1"
BUILD_READY_STATUS = "AUTOMATED_QA_PASSED"
REQUIRED_ARTIFACT_ROLES = (
    "video",
    "subtitles",
    "manifest",
    "qa_report",
)
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
FRAME_RATE_RE = re.compile(r"^(?P<numerator>[1-9][0-9]*)/(?P<denominator>[1-9][0-9]*)$")


_RELEASE_CONTRACT = {
    "schema": RELEASE_CONTRACT_SCHEMA,
    "release_profile": RELEASE_PROFILE,
    "audio_profile": "no_bgm",
    "subtitle_profile": "zh_dialogue_only",
    "release_scope": "independent_edition",
    "bgm_policy": "intentionally_excluded",
    "voice_se_policy": "preserve_verified_original",
    "archive_complete": False,
    "six_edition_complete": False,
}

_RELEASE_CONTRACT_FIELDS = frozenset(_RELEASE_CONTRACT)
_ARTIFACT_FIELDS = frozenset({"path", "sha256"})
_MEDIA_FIELDS = frozenset(
    {
        "duration_ms",
        "width",
        "height",
        "frame_rate",
        "video_codec",
        "video_bit_rate",
        "audio_codec",
        "audio_bit_rate",
        "audio_sample_rate",
        "audio_channels",
        "audio_channel_layout",
        "upscaled",
    }
)
_READINESS_FIELDS = frozenset(
    {
        "BUILD_READY",
        "AUTOMATED_QA_PASSED",
        "HUMAN_PLAYBACK_APPROVED",
        "BILIBILI_RELEASE_READY",
    }
)
_BUILD_READY_FIELDS = frozenset(
    {
        "schema",
        "status",
        "release_id",
        "release_contract",
        "release_contract_sha256",
        "release_profile",
        "audio_profile",
        "subtitle_profile",
        "release_scope",
        "bgm_policy",
        "voice_se_policy",
        "translation_status",
        "human_review_status",
        "readiness",
        "publishable",
        "archive_complete",
        "six_edition_complete",
        "ordered_events",
        "dialogue_cue_count",
        "media",
        "artifacts",
        "artifact_set_sha256",
    }
)


def canonical_sha256(value: Any) -> str:
    """Return an uppercase SHA-256 of canonical UTF-8 JSON."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], *, label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} fields differ: missing={missing}, unknown={unknown}")


def _same_typed_value(actual: Any, expected: Any) -> bool:
    """Compare JSON scalars without treating ``0`` as ``False``."""

    return type(actual) is type(expected) and actual == expected


def release_contract(profile: str = RELEASE_PROFILE) -> dict[str, Any]:
    """Return the sole supported independent-edition contract."""

    if profile != RELEASE_PROFILE:
        raise ValueError(
            f"unsupported independent release profile {profile!r}; "
            f"expected {RELEASE_PROFILE!r}"
        )
    return copy.deepcopy(_RELEASE_CONTRACT)


def validate_release_contract(value: Any) -> dict[str, Any]:
    """Require an exact R1 contract; arbitrary partial matrices are forbidden."""

    if not isinstance(value, Mapping):
        raise ValueError("independent release contract must be an object")
    _exact_fields(value, _RELEASE_CONTRACT_FIELDS, label="release contract")
    normalized = dict(value)
    if normalized != _RELEASE_CONTRACT:
        differences = sorted(
            key
            for key in _RELEASE_CONTRACT_FIELDS
            if not _same_typed_value(normalized.get(key), _RELEASE_CONTRACT[key])
        )
        raise ValueError(
            "independent release contract does not match the named profile: "
            f"{differences}"
        )
    return copy.deepcopy(_RELEASE_CONTRACT)


def _validate_artifacts(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, Mapping):
        raise ValueError("BUILD_READY artifacts must be an object")
    if frozenset(value) != frozenset(REQUIRED_ARTIFACT_ROLES):
        missing = sorted(set(REQUIRED_ARTIFACT_ROLES) - set(value))
        unknown = sorted(set(value) - set(REQUIRED_ARTIFACT_ROLES))
        raise ValueError(
            f"BUILD_READY artifact roles differ: missing={missing}, unknown={unknown}"
        )
    result: dict[str, dict[str, str]] = {}
    for role in REQUIRED_ARTIFACT_ROLES:
        row = value[role]
        if not isinstance(row, Mapping):
            raise ValueError(f"BUILD_READY artifact {role} must be an object")
        _exact_fields(row, _ARTIFACT_FIELDS, label=f"artifact {role}")
        if not isinstance(row.get("path"), str) or not isinstance(
            row.get("sha256"), str
        ):
            raise ValueError(
                f"BUILD_READY artifact {role} path and SHA-256 must be strings"
            )
        path = row["path"].strip()
        sha256 = row["sha256"].strip().upper()
        if not path or any(character in path for character in ("\n", "\r", "\x00")):
            raise ValueError(f"BUILD_READY artifact {role} has an invalid path")
        if not SHA256_RE.fullmatch(sha256):
            raise ValueError(f"BUILD_READY artifact {role} requires a full SHA-256")
        result[role] = {"path": path, "sha256": sha256}
    return result


def _positive_integer(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _validate_media(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("BUILD_READY media must be an object")
    _exact_fields(value, _MEDIA_FIELDS, label="media")
    duration_ms = _positive_integer(value.get("duration_ms"), label="duration_ms")
    width = _positive_integer(value.get("width"), label="width")
    height = _positive_integer(value.get("height"), label="height")
    if not isinstance(value.get("frame_rate"), str):
        raise ValueError("frame_rate must be a positive rational such as 30/1")
    frame_rate = value["frame_rate"].strip()
    if not FRAME_RATE_RE.fullmatch(frame_rate):
        raise ValueError("frame_rate must be a positive rational such as 30/1")
    video_bit_rate = _positive_integer(
        value.get("video_bit_rate"), label="video_bit_rate"
    )
    audio_bit_rate = _positive_integer(
        value.get("audio_bit_rate"), label="audio_bit_rate"
    )
    expected = {
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "audio_channel_layout": "stereo",
        "upscaled": False,
    }
    differences = [
        key
        for key, expected_value in expected.items()
        if not _same_typed_value(value.get(key), expected_value)
    ]
    if differences:
        raise ValueError(f"BUILD_READY media contract mismatch: {differences}")
    if not 64_000 <= audio_bit_rate <= 512_000:
        raise ValueError("audio_bit_rate must be within the audited AAC range")
    return {
        "duration_ms": duration_ms,
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "video_codec": "h264",
        "video_bit_rate": video_bit_rate,
        "audio_codec": "aac",
        "audio_bit_rate": audio_bit_rate,
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "audio_channel_layout": "stereo",
        "upscaled": False,
    }


def _validate_ordered_events(value: Any) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("ordered_events must be a non-empty list")
    events = [
        validate_output_identifier(event, label="ordered event")
        for event in value
    ]
    if not events:
        raise ValueError("ordered_events must be a non-empty list")
    if len(set(events)) != len(events):
        raise ValueError("ordered_events must not contain duplicates")
    return events


def _expected_readiness() -> dict[str, bool]:
    return {
        "BUILD_READY": True,
        "AUTOMATED_QA_PASSED": True,
        "HUMAN_PLAYBACK_APPROVED": False,
        "BILIBILI_RELEASE_READY": False,
    }


def build_build_ready_marker(
    *,
    release_id: str,
    ordered_events: Sequence[str],
    dialogue_cue_count: int,
    media: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, str]],
    profile: str = RELEASE_PROFILE,
) -> dict[str, Any]:
    """Build an immutable automatic-QA marker with no human approval claims."""

    contract = release_contract(profile)
    release_id = validate_output_identifier(release_id, label="release id")
    events = _validate_ordered_events(ordered_events)
    if (
        isinstance(dialogue_cue_count, bool)
        or not isinstance(dialogue_cue_count, int)
        or dialogue_cue_count <= 0
    ):
        raise ValueError("dialogue_cue_count must be a positive integer")
    cue_count = dialogue_cue_count
    normalized_media = _validate_media(media)
    normalized_artifacts = _validate_artifacts(artifacts)
    marker = {
        "schema": BUILD_READY_SCHEMA,
        "status": BUILD_READY_STATUS,
        "release_id": release_id,
        "release_contract": contract,
        "release_contract_sha256": canonical_sha256(contract),
        "release_profile": contract["release_profile"],
        "audio_profile": contract["audio_profile"],
        "subtitle_profile": contract["subtitle_profile"],
        "release_scope": contract["release_scope"],
        "bgm_policy": contract["bgm_policy"],
        "voice_se_policy": contract["voice_se_policy"],
        "translation_status": "machine_draft_pending_owner",
        "human_review_status": "pending",
        "readiness": _expected_readiness(),
        "publishable": False,
        "archive_complete": False,
        "six_edition_complete": False,
        "ordered_events": events,
        "dialogue_cue_count": cue_count,
        "media": normalized_media,
        "artifacts": normalized_artifacts,
        "artifact_set_sha256": canonical_sha256(normalized_artifacts),
    }
    return validate_build_ready_marker(marker)


def validate_build_ready_marker(value: Any) -> dict[str, Any]:
    """Re-open and validate a BUILD_READY marker without trusting its booleans."""

    if not isinstance(value, Mapping):
        raise ValueError("BUILD_READY marker must be an object")
    _exact_fields(value, _BUILD_READY_FIELDS, label="BUILD_READY marker")
    marker = copy.deepcopy(dict(value))
    contract = validate_release_contract(marker["release_contract"])
    expected_scalars = {
        "schema": BUILD_READY_SCHEMA,
        "status": BUILD_READY_STATUS,
        "release_profile": contract["release_profile"],
        "audio_profile": contract["audio_profile"],
        "subtitle_profile": contract["subtitle_profile"],
        "release_scope": contract["release_scope"],
        "bgm_policy": contract["bgm_policy"],
        "voice_se_policy": contract["voice_se_policy"],
        "translation_status": "machine_draft_pending_owner",
        "human_review_status": "pending",
        "publishable": False,
        "archive_complete": False,
        "six_edition_complete": False,
    }
    differences = [
        field
        for field, expected in expected_scalars.items()
        if not _same_typed_value(marker.get(field), expected)
    ]
    if differences:
        raise ValueError(f"BUILD_READY fixed fields mismatch: {differences}")
    release_id = validate_output_identifier(marker["release_id"], label="release id")
    if marker.get("release_contract_sha256") != canonical_sha256(contract):
        raise ValueError("BUILD_READY release contract SHA-256 mismatch")
    readiness = marker.get("readiness")
    if not isinstance(readiness, Mapping):
        raise ValueError("BUILD_READY readiness must be an object")
    _exact_fields(readiness, _READINESS_FIELDS, label="readiness")
    expected_readiness = _expected_readiness()
    if any(
        not _same_typed_value(readiness.get(field), expected)
        for field, expected in expected_readiness.items()
    ):
        raise ValueError("BUILD_READY cannot claim human or Bilibili approval")
    events = _validate_ordered_events(marker.get("ordered_events"))
    cue_count = marker.get("dialogue_cue_count")
    if isinstance(cue_count, bool) or not isinstance(cue_count, int) or cue_count <= 0:
        raise ValueError("dialogue_cue_count must be a positive integer")
    media = _validate_media(marker.get("media"))
    artifacts = _validate_artifacts(marker.get("artifacts"))
    if marker.get("artifact_set_sha256") != canonical_sha256(artifacts):
        raise ValueError("BUILD_READY artifact set SHA-256 mismatch")
    marker.update(
        {
            "release_id": release_id,
            "release_contract": contract,
            "ordered_events": events,
            "media": media,
            "artifacts": artifacts,
        }
    )
    return marker
