#!/usr/bin/env python3
"""Build the single human review hub from a hash-bound production inventory.

The builder never moves or transcodes source media.  REVIEW_READY media are
published as same-volume hardlinks; every semantic item remains traceable in
the JSON/CSV index, including aliases, blocked items, and excluded references.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from typing import Any, Callable, Mapping


DISPOSITIONS = {"REVIEW_READY", "NEEDS_DECISION", "EXCLUDED_REFERENCE"}
CONTENT_FOLDERS = {"story", "routes", "gameplay_effect", "material"}
EDITIONS = {"none", "ja", "zh", "material"}
QUARANTINE_TOKENS = {"ac6003", "ac6004", "ac6005", "p16", "p17", "p18"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(json_bytes(value))


def load_bound_json(binding: Mapping[str, Any], label: str) -> tuple[Path, Any]:
    path = Path(str(binding.get("path", ""))).resolve()
    expected = str(binding.get("sha256", "")).upper()
    if not path.is_file() or len(expected) != 64:
        raise ValueError(f"invalid {label} binding")
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def load_bound_csv(binding: Mapping[str, Any], label: str) -> tuple[Path, list[dict[str, str]]]:
    path = Path(str(binding.get("path", ""))).resolve()
    expected = str(binding.get("sha256", "")).upper()
    if not path.is_file() or len(expected) != 64:
        raise ValueError(f"invalid {label} binding")
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return path, list(csv.DictReader(handle))


def safe_relative_path(raw: str) -> Path:
    if not raw or "\\" in raw:
        raise ValueError(f"unsafe hub path: {raw!r}")
    posix = PurePosixPath(raw)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"unsafe hub path: {raw!r}")
    if any(":" in part for part in posix.parts):
        raise ValueError(f"unsafe hub path: {raw!r}")
    if len(posix.parts) < 5 or posix.parts[0] != "REVIEW_READY":
        raise ValueError(f"hub path is outside REVIEW_READY: {raw!r}")
    if posix.parts[1] not in CONTENT_FOLDERS or posix.parts[-2] not in EDITIONS:
        raise ValueError(f"invalid hub classification: {raw!r}")
    if posix.suffix.casefold() != ".mp4":
        raise ValueError(f"hub media is not MP4: {raw!r}")
    return Path(*posix.parts)


def probe_media(path: Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    # ffprobe emits UTF-8 JSON even when the Windows process locale is GBK.
    # Capture bytes explicitly so non-ASCII path/tag data cannot be decoded by
    # Python's locale-dependent text-mode reader thread.
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"ffprobe failed for {path}: {error}")
    payload = json.loads(completed.stdout.decode("utf-8"))
    video = next((s for s in payload.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in payload.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video is None:
        raise ValueError(f"media has no video stream: {path}")
    duration = payload.get("format", {}).get("duration") or video.get("duration")
    result = {
        "duration_sec": float(duration),
        "width": int(video["width"]),
        "height": int(video["height"]),
        # The authoritative inventory records ffprobe r_frame_rate.  Concatenated
        # streams can have a non-canonical avg_frame_rate (for example
        # 3671040/122363) even though their encoded cadence is exactly 30/1.
        "frame_rate": video.get("r_frame_rate") or video.get("avg_frame_rate"),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_sample_rate": int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        "audio_channels": int(audio["channels"]) if audio and audio.get("channels") else None,
    }
    result["probe_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest().upper()
    return result


def validate_probe(item: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    item_id = item["inventory_item_id"]
    for field in ("width", "height", "frame_rate", "video_codec"):
        if actual.get(field) != item.get(field):
            raise ValueError(f"{item_id} probe mismatch for {field}")
    expected_audio = item.get("audio_codec") or None
    if actual.get("audio_codec") != expected_audio:
        raise ValueError(f"{item_id} probe mismatch for audio_codec")
    for field in ("audio_sample_rate", "audio_channels"):
        expected = item.get(field)
        # The authoritative inventory serializes a missing audio stream as an
        # empty codec plus numeric zeroes; ffprobe naturally exposes nulls.
        expected = int(expected) if expected not in (None, "", 0, "0") else None
        if actual.get(field) != expected:
            raise ValueError(f"{item_id} probe mismatch for {field}")
    if abs(float(actual["duration_sec"]) - float(item["duration_sec"])) > 0.06:
        raise ValueError(f"{item_id} probe mismatch for duration_sec")


def read_edges(path: Path) -> None:
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"empty media: {path}")
    with path.open("rb") as handle:
        if not handle.read(1):
            raise ValueError(f"unreadable media start: {path}")
        handle.seek(-1, os.SEEK_END)
        if not handle.read(1):
            raise ValueError(f"unreadable media end: {path}")


def normalized_source(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def normalized_route_identity(value: Any) -> str:
    """Normalize the known numeric and ``dirinfo-row-NNN`` route spellings."""

    text = str(value or "").strip().casefold()
    match = re.fullmatch(r"dirinfo-row-(\d+)", text)
    if match:
        return str(int(match.group(1)))
    if text.isdigit():
        return str(int(text))
    return text


def apply_inventory_deltas(
    *,
    plan: Mapping[str, Any],
    inventory_path: Path,
    inventory_sha256: str,
    base_items: list[Mapping[str, Any]],
    base_mapping: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    """Apply hash-bound additive items and explicit reference supersessions."""

    items = copy.deepcopy(base_items)
    mapping = [dict(row) for row in base_mapping]
    bindings: list[dict[str, Any]] = []
    inputs = plan.get("inputs", {})
    configured = inputs.get("deltas", [])
    if not isinstance(configured, list):
        raise ValueError("inventory deltas are malformed")
    for index, config in enumerate(configured):
        if not isinstance(config, Mapping):
            raise ValueError("inventory delta binding is malformed")
        delta_path, delta = load_bound_json(
            config["inventory_delta"], f"inventory delta {index}"
        )
        supersession_path, supersession = load_bound_json(
            config["supersession_delta"], f"supersession delta {index}"
        )
        delta_schema = str(delta.get("schema", ""))
        supersession_schema = str(supersession.get("schema", ""))
        if delta_schema not in {
            "magireco-authoritative-production-inventory-delta-v2",
            "magireco-authoritative-production-inventory-delta-v3",
        }:
            raise ValueError("unexpected inventory delta schema")
        if supersession_schema not in {
            "magireco-production-inventory-supersession-delta-v1",
            "magireco-production-inventory-supersession-delta-v2",
        }:
            raise ValueError("unexpected supersession delta schema")
        base_binding = delta.get("base_inventory", {})
        if (
            normalized_source(str(base_binding.get("path", "")))
            != normalized_source(str(inventory_path))
            or str(base_binding.get("sha256", "")).upper() != inventory_sha256
        ):
            raise ValueError("inventory delta is bound to a different base inventory")
        additions = copy.deepcopy(delta.get("items", []))
        if not isinstance(additions, list):
            raise ValueError("inventory delta items are malformed")
        existing_ids = {str(item.get("inventory_item_id", "")) for item in items}
        addition_by_id: dict[str, dict[str, Any]] = {}
        for item in additions:
            item_id = str(item.get("inventory_item_id", ""))
            if not item_id or item_id in existing_ids or item_id in addition_by_id:
                raise ValueError(f"duplicate delta inventory item: {item_id}")
            addition_by_id[item_id] = item

        extra_bindings: dict[str, dict[str, Any]] = {}
        if delta_schema.endswith("-v3"):
            prior = delta.get("prior_delta", {})
            prior_path = normalized_source(str(prior.get("path", "")))
            prior_sha = str(prior.get("sha256", "")).upper()
            loaded_prior = {
                (
                    normalized_source(str(binding["inventory_delta"]["path"])),
                    str(binding["inventory_delta"]["sha256"]).upper(),
                )
                for binding in bindings
            }
            if (prior_path, prior_sha) not in loaded_prior:
                raise ValueError("v3 inventory delta is not bound to the loaded prior delta")
            verification_path, verification = load_bound_json(
                config["verification_record"], f"inventory delta verification {index}"
            )
            source_bindings_path, source_bindings = load_bound_json(
                config["source_bindings"], f"inventory delta source bindings {index}"
            )
            if (
                verification.get("schema")
                != "magireco-authoritative-production-inventory-delta-verification-v3"
                or verification.get("result") != "PASS"
                or int(verification.get("counts", {}).get("items", -1)) != len(additions)
            ):
                raise ValueError("v3 inventory delta verification did not pass")
            if source_bindings.get("schema") != "magireco-inventory-delta-source-bindings-v2":
                raise ValueError("unexpected v3 inventory source binding schema")
            measured = {
                normalized_source(str(path)): str(sha).upper()
                for path, sha in source_bindings.get("measured_source_hashes", {}).items()
            }
            required_evidence = {
                normalized_source(str(path))
                for item in additions
                for path in [item.get("source_manifest", ""), *item.get("evidence_paths", [])]
                if path
            }
            if not required_evidence <= set(measured):
                raise ValueError("v3 inventory source bindings do not cover all evidence")
            for path_text, expected_sha in measured.items():
                path = Path(path_text)
                if not path.is_file() or file_sha256(path) != expected_sha:
                    raise ValueError(f"v3 inventory evidence SHA-256 mismatch: {path}")
            extra_bindings = {
                "verification_record": {
                    "path": str(verification_path),
                    "sha256": file_sha256(verification_path),
                },
                "source_bindings": {
                    "path": str(source_bindings_path),
                    "sha256": file_sha256(source_bindings_path),
                },
            }

        for rule in supersession.get("items", []):
            if supersession_schema.endswith("-v2"):
                old_sha = str(rule.get("withdrawn_sha256", "")).upper()
                old_path = normalized_source(str(rule.get("withdrawn_source_path", "")))
                old_id = str(rule.get("withdrawn_inventory_item_id", ""))
            else:
                old_sha = str(rule.get("superseded_sha256", "")).upper()
                old_path = normalized_source(str(rule.get("superseded_source_path", "")))
                old_id = ""
            candidates = [
                item
                for item in items
                if str(item.get("sha256", "")).upper() == old_sha
                and normalized_source(str(item.get("source_path", ""))) == old_path
                and str(item.get("family", "")) == str(rule.get("family", ""))
                and str(item.get("edition", "")) == str(rule.get("edition", ""))
                and (not old_id or str(item.get("inventory_item_id", "")) == old_id)
                and (
                    supersession_schema.endswith("-v2")
                    or normalized_route_identity(item.get("route_id"))
                    == normalized_route_identity(rule.get("route_id"))
                )
            ]
            if len(candidates) != 1:
                raise ValueError(f"supersession source did not resolve uniquely: {old_sha}")
            old = candidates[0]
            replacement_id = str(rule.get("replacement_inventory_item_id", ""))
            replacement = addition_by_id.get(replacement_id)
            if replacement is None:
                raise ValueError(f"supersession replacement is absent: {replacement_id}")
            if str(replacement.get("sha256", "")).upper() != str(
                rule.get("replacement_sha256", replacement.get("sha256", ""))
            ).upper():
                raise ValueError("supersession replacement SHA-256 differs")
            replacement_scope = str(rule.get("replacement_scope", "exact_reference_replacement"))
            is_bounded_candidate = replacement_scope == (
                "bounded_event_candidate_only_not_full_chapter_replacement"
            )
            if not is_bounded_candidate:
                for field in ("family", "edition"):
                    if (
                        str(old.get(field, "")) != str(rule.get(field, ""))
                        or str(old.get(field, "")) != str(replacement.get(field, ""))
                    ):
                        raise ValueError(f"supersession identity mismatch for {field}")
                route_identities = {
                    normalized_route_identity(old.get("route_id")),
                    normalized_route_identity(rule.get("route_id", old.get("route_id"))),
                    normalized_route_identity(replacement.get("route_id")),
                }
                if len(route_identities) != 1:
                    raise ValueError("supersession identity mismatch for route_id")
                if old.get("already_uploaded") or old.get("owner_approved"):
                    raise ValueError("supersession attempted to demote an owner-approved exact file")
            elif (
                not old.get("owner_approved")
                or not rule.get("owner_playback_approval_preserved")
            ):
                raise ValueError("bounded candidate did not preserve exact owner approval")
            old["strict_no_bgm_review_ready_withdrawn"] = bool(
                rule.get("strict_no_bgm_review_ready_withdrawn", False)
            )
            old["replacement_scope"] = replacement_scope
            old["strict_no_bgm_withdrawal_reason"] = str(rule.get("reason", ""))
            if is_bounded_candidate:
                old["bounded_replacement_candidate_inventory_item_id"] = replacement_id
                old["bounded_replacement_candidate_sha256"] = str(
                    replacement.get("sha256", "")
                ).upper()
                continue
            old["not_in_primary_review_reason"] = str(
                rule.get("reason", "superseded_reference")
            )
            old["superseded"] = True
            old["superseded_by_inventory_item_id"] = replacement_id
            old["physical_link_policy"] = "index_only"
            old["proposed_hub_relative_path"] = ""
            old["proposed_review_filename"] = ""
            mapping = [
                row
                for row in mapping
                if str(row.get("inventory_item_id", ""))
                != str(old.get("inventory_item_id", ""))
                and str(row.get("sha256", "")).upper() != old_sha
            ]

        items.extend(additions)
        for item in additions:
            if item.get("review_disposition") == "REVIEW_READY":
                mapping.append(
                    {
                        "inventory_item_id": str(item["inventory_item_id"]),
                        "source_path": str(item["source_path"]),
                        "sha256": str(item["sha256"]),
                        "proposed_hub_relative_path": str(
                            item["proposed_hub_relative_path"]
                        ),
                    }
                )
        binding_record = {
                "inventory_delta": {
                    "path": str(delta_path),
                    "sha256": file_sha256(delta_path),
                },
                "supersession_delta": {
                    "path": str(supersession_path),
                    "sha256": file_sha256(supersession_path),
                },
            }
        binding_record.update(extra_bindings)
        bindings.append(binding_record)
    return items, mapping, bindings


def apply_authority_audit(
    plan: Mapping[str, Any], items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Bind IDA applicability decisions without treating them as human approval."""

    config = plan.get("inputs", {}).get("authority_audit")
    if config is None:
        return []
    if not isinstance(config, Mapping):
        raise ValueError("authority audit binding is malformed")
    safe_path, safe = load_bound_json(config["safe_review_index"], "safe review index")
    audit_path, audit = load_bound_json(config["product_accuracy_audit"], "product accuracy audit")
    verification_path, verification = load_bound_json(
        config["verification_record"], "authority verification record"
    )
    if safe.get("schema") != "magireco.ida_safe_review_index.v1":
        raise ValueError("unexpected safe review index schema")
    if audit.get("schema") != "magireco.ida_past_product_accuracy_audit.v1":
        raise ValueError("unexpected product accuracy audit schema")
    if (
        verification.get("schema")
        != "magireco.ida_past_product_accuracy_verification.v1"
        or verification.get("status") != "PASS"
    ):
        raise ValueError("authority verification record did not pass")
    by_id = {str(item["inventory_item_id"]): item for item in items}
    audit_rows = list(audit.get("items", []))
    safe_rows = list(safe.get("items", []))
    extension_bindings: list[dict[str, Any]] = []
    for index, binding in enumerate(config.get("extensions", [])):
        extension_path, extension = load_bound_json(
            binding["audit_extension"], f"authority audit extension {index}"
        )
        extension_verification_path, extension_verification = load_bound_json(
            binding["verification_record"],
            f"authority audit extension verification {index}",
        )
        if (
            extension.get("schema")
            != "magireco.ida_past_product_accuracy_audit_extension.v1"
            or extension_verification.get("schema")
            != "magireco.ida_past_product_accuracy_audit_extension_verification.v1"
            or extension_verification.get("status") != "PASS"
        ):
            raise ValueError("authority audit extension did not pass")
        delta_path, delta = load_bound_json(
            extension["inventory_delta"], f"authority extension inventory delta {index}"
        )
        extension_rows = list(extension.get("items", []))
        extension_ids = {str(row.get("inventory_item_id", "")) for row in extension_rows}
        delta_ids = {str(item.get("inventory_item_id", "")) for item in delta.get("items", [])}
        safe_ids = {str(value) for value in extension.get("safe_review_item_ids", [])}
        if (
            delta.get("schema") != "magireco-authoritative-production-inventory-delta-v3"
            or not extension_ids
            or extension_ids != delta_ids
            or safe_ids != extension_ids
            or int(extension_verification.get("counts", {}).get("items", -1))
            != len(extension_rows)
        ):
            raise ValueError("authority audit extension coverage differs from inventory delta")
        for evidence in extension.get("evidence_bindings", []):
            evidence_path = Path(str(evidence.get("path", ""))).resolve()
            expected_sha = str(evidence.get("sha256", "")).upper()
            if not evidence_path.is_file() or file_sha256(evidence_path) != expected_sha:
                raise ValueError(f"authority extension evidence SHA differs: {evidence_path}")
        audit_rows.extend(extension_rows)
        safe_rows.extend(extension_rows)
        extension_bindings.append(
            {
                "audit_extension": {
                    "path": str(extension_path),
                    "sha256": file_sha256(extension_path),
                },
                "verification_record": {
                    "path": str(extension_verification_path),
                    "sha256": file_sha256(extension_verification_path),
                },
                "inventory_delta": {
                    "path": str(delta_path),
                    "sha256": file_sha256(delta_path),
                },
            }
        )
    audit_by_id = {str(row.get("inventory_item_id", "")): row for row in audit_rows}
    if len(audit_by_id) != len(audit_rows) or set(audit_by_id) != set(by_id):
        raise ValueError("authority audit does not cover inventory exactly")
    ready_ids = {
        item_id
        for item_id, item in by_id.items()
        if item.get("review_disposition") == "REVIEW_READY"
    }
    safe_by_id = {str(row.get("inventory_item_id", "")): row for row in safe_rows}
    if len(safe_by_id) != len(safe_rows) or set(safe_by_id) != ready_ids:
        raise ValueError("safe review index does not equal REVIEW_READY inventory")
    for item_id, item in by_id.items():
        row = audit_by_id[item_id]
        if (
            str(row.get("sha256", "")).upper()
            != str(item.get("sha256", "")).upper()
            or normalized_source(str(row.get("source_path", "")))
            != normalized_source(str(item.get("source_path", "")))
            or str(row.get("effective_review_disposition", ""))
            != str(item.get("review_disposition", ""))
        ):
            raise ValueError(f"authority audit differs from inventory: {item_id}")
        if (
            row.get("ida_accuracy_category") == "CHILD_LOCAL_FAIL_CLOSED"
            and item_id in ready_ids
        ):
            raise ValueError(f"child-local item entered REVIEW_READY: {item_id}")
        item["ida_accuracy_category"] = row.get("ida_accuracy_category", "")
        item["ida_audit_action"] = row.get("audit_action", "")
        item["ida_rationale"] = row.get("rationale", "")
        item["ida_authority_report"] = row.get("ida_authority_report", "")
        item["ida_authority_report_sha256"] = row.get(
            "ida_authority_report_sha256", ""
        )
    for item_id, row in safe_by_id.items():
        if str(row.get("sha256", "")).upper() != str(by_id[item_id]["sha256"]).upper():
            raise ValueError(f"safe review SHA differs: {item_id}")
    return [
        {
            "safe_review_index": {
                "path": str(safe_path),
                "sha256": file_sha256(safe_path),
            },
            "product_accuracy_audit": {
                "path": str(audit_path),
                "sha256": file_sha256(audit_path),
            },
            "verification_record": {
                "path": str(verification_path),
                "sha256": file_sha256(verification_path),
            },
            "extensions": extension_bindings,
        }
    ]


def apply_sound_bus_audit(
    plan: Mapping[str, Any],
    items: list[dict[str, Any]],
    mapping: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, Any]], set[str]]:
    """Apply a hash-bound, demotion-only strict-no-BGM eligibility audit."""

    config = plan.get("inputs", {}).get("sound_bus_audit")
    if config is None:
        return mapping, [], set()
    if not isinstance(config, Mapping):
        raise ValueError("sound bus audit binding is malformed")
    impact_path, impact = load_bound_json(config["product_impact_delta"], "sound bus impact")
    risk_path, risk = load_bound_json(config["ready_risk"], "sound bus ready risk")
    v68_path, v68 = load_bound_json(config["v68_withdrawal"], "v68 withdrawal")
    verification_path, verification = load_bound_json(
        config["verification_record"], "sound bus verification record"
    )
    if impact.get("schema") != "magireco-ida-sound-volume-bus-product-impact-delta-v1":
        raise ValueError("unexpected sound bus impact schema")
    if risk.get("schema") != "magireco-ready-event-bgm-volume-bus-risk-v1":
        raise ValueError("unexpected sound bus ready risk schema")
    if v68.get("schema") != "magireco-v68-ac0911-no-bgm-semantic-withdrawal-v1":
        raise ValueError("unexpected v68 withdrawal schema")
    if (
        verification.get("schema")
        != "magireco-ida-sound-volume-bus-product-impact-verification-v1"
        or verification.get("status") != "PASS"
    ):
        raise ValueError("sound bus verification record did not pass")

    by_id = {str(item["inventory_item_id"]): item for item in items}
    impact_rows = impact.get("items", [])
    impact_by_id = {str(row.get("inventory_item_id", "")): row for row in impact_rows}
    if len(impact_by_id) != len(impact_rows) or not set(impact_by_id) <= set(by_id):
        raise ValueError("sound bus impact contains unknown or duplicate items")
    withdrawn: set[str] = set()
    for item_id, row in impact_by_id.items():
        item = by_id[item_id]
        if (
            str(row.get("sha256", "")).upper()
            != str(item.get("sha256", "")).upper()
            or normalized_source(str(row.get("source_path", "")))
            != normalized_source(str(item.get("source_path", "")))
            or str(row.get("source_review_disposition", ""))
            != str(item.get("review_disposition", ""))
            or str(row.get("effective_review_disposition", ""))
            != "NEEDS_DECISION"
        ):
            raise ValueError(f"sound bus impact differs from inventory: {item_id}")
        action = str(row.get("action", ""))
        if item["review_disposition"] == "REVIEW_READY":
            if action != "withdraw_from_strict_no_bgm_review_ready":
                raise ValueError(f"sound bus ready item was not explicitly withdrawn: {item_id}")
            if row.get("owner_approval_preserved") and not item.get("owner_approved"):
                raise ValueError(f"sound bus audit invented owner approval: {item_id}")
            item["pre_sound_bus_review_disposition"] = "REVIEW_READY"
            item["review_disposition"] = "NEEDS_DECISION"
            item["not_in_primary_review_reason"] = str(row.get("reason", ""))
            item["proposed_hub_relative_path"] = ""
            item["proposed_review_filename"] = ""
            item["physical_link_policy"] = "index_only"
            withdrawn.add(item_id)
        elif action != "retain_existing_fail_closed_status":
            raise ValueError(f"sound bus non-ready item has an invalid action: {item_id}")
        item["sound_bus_audit_action"] = action
        item["sound_bus_audit_reason"] = str(row.get("reason", ""))
        item["bgm_bus_sound_ids"] = row.get("bgm_bus_sound_ids", [])
        item["bgm_bus_requests"] = row.get("bgm_bus_requests", [])
        item["sound_bus_product_impact_path"] = str(impact_path)
        item["sound_bus_product_impact_sha256"] = file_sha256(impact_path)

    risk_rows = risk.get("items", [])
    risk_by_id = {str(row.get("inventory_item_id", "")): row for row in risk_rows}
    if len(risk_by_id) != len(risk_rows) or set(risk_by_id) != withdrawn:
        raise ValueError("sound bus ready risk does not equal the withdrawal set")
    for item_id, row in risk_by_id.items():
        if (
            str(row.get("sha256", "")).upper()
            != str(by_id[item_id].get("sha256", "")).upper()
            or normalized_source(str(row.get("source_path", "")))
            != normalized_source(str(by_id[item_id].get("source_path", "")))
        ):
            raise ValueError(f"sound bus ready risk identity differs: {item_id}")
    v68_rows = v68.get("items", [])
    v68_by_id = {str(row.get("inventory_item_id", "")): row for row in v68_rows}
    if len(v68_by_id) != len(v68_rows) or not set(v68_by_id) <= withdrawn:
        raise ValueError("v68 withdrawal is not a unique subset of withdrawals")
    for item_id, row in v68_by_id.items():
        if (
            str(row.get("sha256", "")).upper()
            != str(by_id[item_id].get("sha256", "")).upper()
            or normalized_source(str(row.get("source_path", "")))
            != normalized_source(str(by_id[item_id].get("source_path", "")))
        ):
            raise ValueError(f"v68 withdrawal identity differs: {item_id}")
    counts = impact.get("counts", {})
    if (
        int(counts.get("items", -1)) != len(impact_rows)
        or int(counts.get("review_ready_withdrawals", -1)) != len(withdrawn)
    ):
        raise ValueError("sound bus impact counts differ")
    mapping = [row for row in mapping if str(row.get("inventory_item_id", "")) not in withdrawn]
    return (
        mapping,
        [
            {
                "product_impact_delta": {
                    "path": str(impact_path),
                    "sha256": file_sha256(impact_path),
                },
                "ready_risk": {"path": str(risk_path), "sha256": file_sha256(risk_path)},
                "v68_withdrawal": {"path": str(v68_path), "sha256": file_sha256(v68_path)},
                "verification_record": {
                    "path": str(verification_path),
                    "sha256": file_sha256(verification_path),
                },
            }
        ],
        withdrawn,
    )


def validate_inputs(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != "magireco-manual-review-hub-plan-v1":
        raise ValueError("unexpected manual review hub plan schema")
    inputs = plan.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError("plan inputs are malformed")
    inventory_path, inventory = load_bound_json(inputs["inventory"], "inventory")
    mapping_path, mapping = load_bound_csv(inputs["mapping"], "mapping")
    if inventory.get("schema") != "magireco-authoritative-production-inventory-v1":
        raise ValueError("unexpected inventory schema")
    base_items = inventory.get("items")
    if not isinstance(base_items, list):
        raise ValueError("inventory items are malformed")
    inventory_sha256 = file_sha256(inventory_path)
    items, mapping, delta_bindings = apply_inventory_deltas(
        plan=plan,
        inventory_path=inventory_path,
        inventory_sha256=inventory_sha256,
        base_items=base_items,
        base_mapping=mapping,
    )
    authority_bindings = apply_authority_audit(plan, items)
    mapping, sound_bus_bindings, sound_bus_withdrawals = apply_sound_bus_audit(
        plan, items, mapping
    )
    expected_sound_bus_withdrawals = {
        str(item.get("inventory_item_id", ""))
        for item in items
        if item.get("strict_no_bgm_review_ready_withdrawn")
    }
    if not expected_sound_bus_withdrawals <= sound_bus_withdrawals:
        missing = sorted(expected_sound_bus_withdrawals - sound_bus_withdrawals)
        raise ValueError(f"v3 strict-no-BGM withdrawals were not applied: {missing}")
    expected = plan.get("expected_counts", {})
    dispositions = {name: 0 for name in DISPOSITIONS}
    by_id: dict[str, Mapping[str, Any]] = {}
    for item in items:
        item_id = str(item.get("inventory_item_id", ""))
        disposition = str(item.get("review_disposition", ""))
        if not item_id or item_id in by_id or disposition not in DISPOSITIONS:
            raise ValueError("invalid or duplicate inventory item")
        by_id[item_id] = item
        dispositions[disposition] += 1
    actual_counts = {
        "inventory_items": len(items),
        "review_ready": dispositions["REVIEW_READY"],
        "needs_decision": dispositions["NEEDS_DECISION"],
        "excluded_reference": dispositions["EXCLUDED_REFERENCE"],
        "mapping_rows": len(mapping),
    }
    for key, value in expected.items():
        if actual_counts.get(key) != int(value):
            raise ValueError(f"count mismatch for {key}: {actual_counts.get(key)} != {value}")

    ready_ids = {key for key, item in by_id.items() if item["review_disposition"] == "REVIEW_READY"}
    mapped_ids: set[str] = set()
    mapped_sha: set[str] = set()
    mapped_paths: set[str] = set()
    allowed_root = Path(str(plan["allowed_source_root"])).resolve()
    inventory_media: list[dict[str, Any]] = []
    for item_id, item in by_id.items():
        source = Path(str(item.get("source_path", ""))).resolve()
        if os.path.commonpath([str(allowed_root), str(source)]) != str(allowed_root):
            raise ValueError(f"inventory source escapes allowed root: {source}")
        if not source.is_file() or item.get("media_open_status") != "open_ok":
            raise ValueError(f"inventory source is not open-ready: {source}")
        sha = str(item.get("sha256", "")).upper()
        if len(sha) != 64 or str(item.get("actual_sha256", sha)).upper() != sha:
            raise ValueError(f"inventory SHA contract is invalid: {item_id}")
        if source.stat().st_size != int(item.get("size", -1)):
            raise ValueError(f"inventory source size differs: {item_id}")
        inventory_media.append({"item": item, "source": source, "sha256": sha})
    prepared: list[dict[str, Any]] = []
    for row in mapping:
        item_id = row.get("inventory_item_id", "")
        if item_id not in by_id or item_id in mapped_ids:
            raise ValueError(f"unknown or duplicate mapping item: {item_id}")
        item = by_id[item_id]
        sha = str(row.get("sha256", "")).upper()
        relative = safe_relative_path(row.get("proposed_hub_relative_path", ""))
        relative_key = relative.as_posix().casefold()
        if sha in mapped_sha or relative_key in mapped_paths:
            raise ValueError("duplicate canonical SHA or hub path")
        if item["review_disposition"] != "REVIEW_READY":
            raise ValueError(f"non-ready item entered mapping: {item_id}")
        if item.get("superseded") or item.get("already_uploaded") or item.get("quarantine_flags"):
            raise ValueError(f"unsafe ready item: {item_id}")
        if item.get("is_alias") or item.get("source_identity_alias"):
            raise ValueError(f"alias entered canonical mapping: {item_id}")
        if item.get("audio_profile") not in {"no_bgm", "silent"}:
            raise ValueError(f"unclosed audio profile entered hub: {item_id}")
        searchable = " ".join(
            [item_id, str(item.get("family", "")), str(item.get("title_zh", "")), str(item.get("source_path", ""))]
        ).casefold()
        if any(token in searchable for token in QUARANTINE_TOKENS):
            raise ValueError(f"quarantined product entered hub: {item_id}")
        if sha != str(item.get("sha256", "")).upper():
            raise ValueError(f"mapping SHA differs from inventory: {item_id}")
        if normalized_source(row.get("source_path", "")) != normalized_source(str(item.get("source_path", ""))):
            raise ValueError(f"mapping source differs from inventory: {item_id}")
        source = Path(str(item["source_path"])).resolve()
        if os.path.commonpath([str(allowed_root), str(source)]) != str(allowed_root):
            raise ValueError(f"source escapes allowed root: {source}")
        if not source.is_file() or item.get("media_open_status") != "open_ok":
            raise ValueError(f"source is not open-ready: {source}")
        if str(item.get("physical_link_policy")) != "hardlink":
            raise ValueError(f"review mapping is not hardlink-safe: {item_id}")
        if item.get("edition") == "material":
            lowered = relative.name.casefold()
            if any(tag in lowered for tag in ("__none", "__ja", "__jp", "__zh")):
                raise ValueError(f"material has a language suffix: {relative.name}")
        mapped_ids.add(item_id)
        mapped_sha.add(sha)
        mapped_paths.add(relative_key)
        prepared.append({"item": item, "source": source, "relative": relative, "sha256": sha})
    if mapped_ids != ready_ids:
        missing = sorted(ready_ids - mapped_ids)
        extra = sorted(mapped_ids - ready_ids)
        raise ValueError(f"mapping does not cover REVIEW_READY exactly: missing={missing}, extra={extra}")
    return {
        "inventory_path": inventory_path,
        "mapping_path": mapping_path,
        "inventory": inventory,
        "items": items,
        "by_id": by_id,
        "inventory_media": inventory_media,
        "prepared": prepared,
        "counts": actual_counts,
        "delta_bindings": delta_bindings,
        "authority_bindings": authority_bindings,
        "sound_bus_bindings": sound_bus_bindings,
        "sound_bus_withdrawals": sound_bus_withdrawals,
    }


def review_row(item: Mapping[str, Any], review_path: str, canonical_path: str) -> dict[str, Any]:
    evidence = item.get("evidence_paths", [])
    return {
        "review_id": item.get("canonical_review_item_id") or item.get("source_identity_canonical_item_id") or item["inventory_item_id"],
        "inventory_item_id": item["inventory_item_id"],
        "title": item.get("title_zh", ""),
        "series": item.get("series", ""),
        "family": item.get("family", ""),
        "content_type": item.get("content_type", ""),
        "edition": item.get("edition", ""),
        "duration_sec": item.get("duration_sec"),
        "resolution": f"{item.get('width')}x{item.get('height')}",
        "width": item.get("width"),
        "height": item.get("height"),
        "frame_rate": item.get("frame_rate"),
        "video_codec": item.get("video_codec"),
        "audio_profile": item.get("audio_profile"),
        "audio_codec": item.get("audio_codec"),
        "audio_sample_rate": item.get("audio_sample_rate"),
        "audio_channels": item.get("audio_channels"),
        "auto_qa_status": item.get("auto_qa_status", ""),
        "human_status": item.get("human_status", ""),
        "review_disposition": item.get("review_disposition", ""),
        "source_absolute_path": item.get("source_path", ""),
        "review_absolute_path": review_path,
        "canonical_review_absolute_path": canonical_path,
        "sha256": item.get("sha256", ""),
        "canonical_sha256": item.get("canonical_sha256", ""),
        "is_alias": bool(item.get("is_alias") or item.get("source_identity_alias")),
        "alias_reason": item.get("alias_reason") or item.get("source_identity_reason") or "",
        "source_ids": item.get("source_ids", []),
        "event_ids": item.get("event_ids", []),
        "evidence": evidence,
        "source_manifest": item.get("source_manifest", ""),
        "source_manifest_sha256": item.get("source_manifest_sha256", ""),
        "exclusion_reason": item.get("not_in_primary_review_reason", ""),
        "quarantine_flags": item.get("quarantine_flags", []),
        "already_uploaded": bool(item.get("already_uploaded")),
        "owner_approved": bool(item.get("owner_approved")),
        "superseded": bool(item.get("superseded")),
        "superseded_by_inventory_item_id": item.get(
            "superseded_by_inventory_item_id", ""
        ),
        "replacement_scope": item.get("replacement_scope", ""),
        "bounded_replacement_candidate_inventory_item_id": item.get(
            "bounded_replacement_candidate_inventory_item_id", ""
        ),
        "bounded_replacement_candidate_sha256": item.get(
            "bounded_replacement_candidate_sha256", ""
        ),
        "ida_accuracy_category": item.get("ida_accuracy_category", ""),
        "ida_audit_action": item.get("ida_audit_action", ""),
        "ida_rationale": item.get("ida_rationale", ""),
        "ida_authority_report": item.get("ida_authority_report", ""),
        "ida_authority_report_sha256": item.get(
            "ida_authority_report_sha256", ""
        ),
        "target_bv": item.get("target_bv", ""),
        "pre_sound_bus_review_disposition": item.get(
            "pre_sound_bus_review_disposition", ""
        ),
        "sound_bus_audit_action": item.get("sound_bus_audit_action", ""),
        "sound_bus_audit_reason": item.get("sound_bus_audit_reason", ""),
        "bgm_bus_sound_ids": item.get("bgm_bus_sound_ids", []),
        "bgm_bus_requests": item.get("bgm_bus_requests", []),
        "sound_bus_product_impact_path": item.get(
            "sound_bus_product_impact_path", ""
        ),
        "sound_bus_product_impact_sha256": item.get(
            "sound_bus_product_impact_sha256", ""
        ),
    }


CSV_FIELDS = [
    "review_id", "inventory_item_id", "title", "series", "family", "content_type",
    "edition", "duration_sec", "resolution", "width", "height", "frame_rate",
    "video_codec", "audio_profile", "audio_codec", "audio_sample_rate",
    "audio_channels", "auto_qa_status", "human_status", "review_disposition",
    "source_absolute_path", "review_absolute_path", "canonical_review_absolute_path",
    "sha256", "canonical_sha256", "is_alias", "alias_reason", "source_ids",
    "event_ids", "evidence", "source_manifest", "source_manifest_sha256",
    "exclusion_reason", "quarantine_flags", "already_uploaded", "owner_approved",
    "superseded", "superseded_by_inventory_item_id", "ida_accuracy_category",
    "replacement_scope", "bounded_replacement_candidate_inventory_item_id",
    "bounded_replacement_candidate_sha256",
    "ida_audit_action", "ida_rationale", "ida_authority_report",
    "ida_authority_report_sha256", "target_bv",
    "pre_sound_bus_review_disposition", "sound_bus_audit_action",
    "sound_bus_audit_reason", "bgm_bus_sound_ids", "bgm_bus_requests",
    "sound_bus_product_impact_path", "sound_bus_product_impact_sha256",
]


def write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            for key in (
                "source_ids", "event_ids", "evidence", "quarantine_flags",
                "bgm_bus_sound_ids", "bgm_bus_requests",
            ):
                rendered[key] = json.dumps(rendered[key], ensure_ascii=False, separators=(",", ":"))
            writer.writerow(rendered)


def build(
    plan_path: Path,
    *,
    output_root: Path | None = None,
    dry_run: bool = False,
    ffprobe: str = "ffprobe",
    probe_func: Callable[[Path, str], dict[str, Any]] = probe_media,
) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validated = validate_inputs(plan)
    root = (output_root or Path(str(plan["output_root"]))).resolve()
    release_id = str(plan["release_id"])
    if not release_id or Path(release_id).name != release_id:
        raise ValueError("unsafe release_id")
    release = root / "releases" / release_id
    staging = release.with_name(release.name + f".staging.{os.getpid()}")
    if release.exists() or staging.exists():
        raise ValueError(f"release or staging already exists: {release}")
    current_path = root / "CURRENT.json"
    previous_current = current_path.read_bytes() if current_path.is_file() else None

    probe_rows: dict[str, dict[str, Any]] = {}
    source_hashes: dict[str, str] = {}
    source_records: list[dict[str, Any]] = []
    for entry in validated["inventory_media"]:
        source = entry["source"]
        read_edges(source)
        actual_hash = file_sha256(source)
        if actual_hash != entry["sha256"]:
            raise ValueError(f"source SHA mismatch: {source}")
        actual_probe = probe_func(source, ffprobe)
        validate_probe(entry["item"], actual_probe)
        item_id = entry["item"]["inventory_item_id"]
        source_hashes[item_id] = actual_hash
        probe_rows[item_id] = actual_probe
        source_records.append(
            {
                "inventory_item_id": item_id,
                "review_disposition": entry["item"]["review_disposition"],
                "source_path": str(source),
                "sha256": actual_hash,
                "probe": actual_probe,
            }
        )

    if dry_run:
        return {
            "status": "DRY_RUN_PASS",
            "inventory_items": len(validated["items"]),
            "review_ready_files": len(validated["prepared"]),
            "needs_decision": validated["counts"]["needs_decision"],
            "excluded_reference": validated["counts"]["excluded_reference"],
            "output_root": str(root),
            "release_path": str(release),
        }

    root.mkdir(parents=True, exist_ok=True)
    (root / "releases").mkdir(exist_ok=True)
    staging.mkdir()
    try:
        review_paths: dict[str, str] = {}
        link_records: list[dict[str, Any]] = []
        for entry in validated["prepared"]:
            item = entry["item"]
            destination = staging / entry["relative"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.link(entry["source"], destination)
            if not os.path.samefile(entry["source"], destination):
                raise ValueError(f"destination is not a source hardlink: {destination}")
            read_edges(destination)
            if file_sha256(destination) != entry["sha256"]:
                raise ValueError(f"destination SHA mismatch: {destination}")
            probe = probe_func(destination, ffprobe)
            validate_probe(item, probe)
            relative = entry["relative"].as_posix()
            review_paths[item["inventory_item_id"]] = str(release / entry["relative"])
            link_records.append(
                {
                    "inventory_item_id": item["inventory_item_id"],
                    "relative_path": relative,
                    "source_path": str(entry["source"]),
                    "sha256": entry["sha256"],
                    "samefile": True,
                    "source_link_count": entry["source"].stat().st_nlink,
                    "destination_link_count": destination.stat().st_nlink,
                    "probe": probe,
                }
            )

        rows: list[dict[str, Any]] = []
        by_id = validated["by_id"]
        for item in validated["items"]:
            direct = review_paths.get(item["inventory_item_id"], "")
            canonical_id = item.get("canonical_review_item_id") or item.get("source_identity_canonical_item_id") or ""
            canonical = review_paths.get(str(canonical_id), "")
            rows.append(review_row(item, direct, canonical))
        rows.sort(key=lambda row: str(row["inventory_item_id"]))

        write_json(
            staging / "review_index.json",
            {
                "schema": "magireco-manual-review-index-v1",
                "summary": {
                    **validated["counts"],
                    "canonical_review_files": len(link_records),
                    "auto_qa_is_human_approval": False,
                },
                "items": rows,
            },
        )
        write_review_csv(staging / "review_index.csv", rows)
        write_json(
            staging / "NEEDS_DECISION.json",
            {"schema": "magireco-manual-review-needs-decision-v1", "items": [r for r in rows if r["review_disposition"] == "NEEDS_DECISION"]},
        )
        write_json(
            staging / "EXCLUDED_REFERENCE.json",
            {"schema": "magireco-manual-review-excluded-reference-v1", "items": [r for r in rows if r["review_disposition"] == "EXCLUDED_REFERENCE"]},
        )
        write_json(
            staging / "SOURCE_BINDINGS.json",
            {
                "schema": "magireco-manual-review-source-bindings-v1",
                "inventory": {"path": str(validated["inventory_path"]), "sha256": file_sha256(validated["inventory_path"])},
                "mapping": {"path": str(validated["mapping_path"]), "sha256": file_sha256(validated["mapping_path"])},
                "deltas": validated["delta_bindings"],
                "authority_audit": validated["authority_bindings"],
                "sound_bus_audit": validated["sound_bus_bindings"],
                "plan": {"path": str(plan_path.resolve()), "sha256": file_sha256(plan_path.resolve())},
            },
        )
        verification = {
            "schema": "magireco-manual-review-hub-verification-v1",
            "status": "PASS",
            "checks": {
                "inventory_count_matches": True,
                "mapping_covers_review_ready_exactly": True,
                "needs_decision_not_linked": True,
                "excluded_reference_not_linked": True,
                "quarantine_not_linked": True,
                "with_bgm_not_linked": True,
                "sound_bus_withdrawals_not_linked": not any(
                    item_id in review_paths
                    for item_id in validated["sound_bus_withdrawals"]
                ),
                "unique_canonical_sha": len({r["sha256"] for r in link_records}) == len(link_records),
                "all_sources_rehashed_before_and_after": True,
                "all_destinations_samefile": all(r["samefile"] for r in link_records),
                "all_inventory_media_reopened_and_probed": len(source_records)
                == len(validated["items"]),
                "all_review_destinations_reopened_and_probed": len(link_records)
                == len(validated["prepared"]),
                "auto_qa_not_promoted_to_human": True,
            },
            "counts": validated["counts"],
            "source_records": source_records,
            "link_records": link_records,
        }
        for entry in validated["inventory_media"]:
            if file_sha256(entry["source"]) != source_hashes[entry["item"]["inventory_item_id"]]:
                raise ValueError(f"source changed during build: {entry['source']}")
        write_json(staging / "VERIFICATION_RECORD.json", verification)

        start = "\n".join(
            [
                "# MagiaReco Slot 单一人工审查入口",
                "",
                "本版本从权威 production inventory 原子构建；原始视频未移动、未删除、未转码、未超分。",
                "所有 MP4 均为 D: 同卷 hardlink；同一 SHA-256 只提供一个规范审查文件。",
                "",
                f"- 待人工审查或复核的规范文件：{len(link_records)}",
                f"- NEEDS_DECISION（仅索引，不进入主目录）：{validated['counts']['needs_decision']}",
                f"- EXCLUDED_REFERENCE（仅索引）：{validated['counts']['excluded_reference']}",
                "- AUTO_QA_PASS 不代表人工已经看过。",
                "",
                "从 `REVIEW_READY` 开始播放；按 story/routes/gameplay_effect/material、系列、none/ja/zh/material 分层。",
                "完整状态请看 `review_index.csv` 或 `review_index.json`。",
                "",
            ]
        )
        (staging / "00_START_HERE.md").write_text(start, encoding="utf-8")
        rollback_dir = staging / "_rollback"
        rollback_dir.mkdir()
        if previous_current is not None:
            (rollback_dir / "PREVIOUS_CURRENT.json").write_bytes(previous_current)
        rollback = """$ErrorActionPreference='Stop'
$release=Split-Path -Parent $PSScriptRoot
$releases=Split-Path -Parent $release
$root=Split-Path -Parent $releases
$current=Join-Path $root 'CURRENT.json'
$previous=Join-Path $PSScriptRoot 'PREVIOUS_CURRENT.json'
if(Test-Path -LiteralPath $previous){Copy-Item -LiteralPath $previous -Destination ($current+'.tmp') -Force; Move-Item -LiteralPath ($current+'.tmp') -Destination $current -Force}
elseif(Test-Path -LiteralPath $current){Move-Item -LiteralPath $current -Destination (Join-Path $root ('CURRENT.rolledback.'+[DateTime]::UtcNow.ToString('yyyyMMddHHmmssfff')+'.json'))}
Write-Output 'ROLLBACK_POINTER_PASS'
"""
        (rollback_dir / "ROLLBACK.ps1").write_text(rollback, encoding="utf-8")
        sums = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                sums[path.relative_to(staging).as_posix()] = {"sha256": file_sha256(path), "size": path.stat().st_size}
        write_json(staging / "SHA256SUMS.json", {"schema": "magireco-manual-review-hub-sums-v1", "files": sums})
        (staging / "READY").write_text("BUILD_READY\nAUTOMATED_QA_PASSED\nHUMAN_PLAYBACK_APPROVED=false\n", encoding="utf-8")
        os.replace(staging, release)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    current = {
        "schema": "magireco-manual-review-hub-current-v1",
        "release_id": release_id,
        "release_path": str(release),
        "start_here": str(release / "00_START_HERE.md"),
        "review_index_json": str(release / "review_index.json"),
        "review_index_csv": str(release / "review_index.csv"),
        "verification_record": str(release / "VERIFICATION_RECORD.json"),
        "ready_marker": str(release / "READY"),
        "counts": validated["counts"],
    }
    temp_current = root / "CURRENT.json.tmp"
    temp_current.write_bytes(json_bytes(current))
    os.replace(temp_current, current_path)
    root_start = root / "00_START_HERE.md"
    root_text = "# MagiaReco Slot 人工审查中心\n\n当前权威入口：`CURRENT.json`。请按其中 `start_here` 打开当前不可变版本。\n"
    temp_start = root / "00_START_HERE.md.tmp"
    temp_start.write_text(root_text, encoding="utf-8")
    os.replace(temp_start, root_start)
    return {"status": "PASS", **current, "current_sha256": file_sha256(current_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = build(args.plan, output_root=args.output_root, dry_run=args.dry_run, ffprobe=args.ffprobe)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
