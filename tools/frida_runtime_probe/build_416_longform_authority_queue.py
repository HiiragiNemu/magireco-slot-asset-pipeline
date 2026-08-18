#!/usr/bin/env python3
"""Compile the current native-416 longform code-audit queue.

The queue counts one family once, never counts none/JA/ZH editions as separate
content, and never promotes playback approval to exhaustive authority.  Deep
family authority records override the broad static candidate ledger while all
unresolved families remain render-blocked.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    values = list(rows)
    fields = list(values[0]) if values else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)


def compact_blockers(rows: Any) -> str:
    result: list[str] = []
    for row in rows or []:
        if isinstance(row, str):
            result.append(row)
        elif isinstance(row, dict):
            result.append(str(row.get("kind") or row.get("reason") or "blocker"))
    return "|".join(result)


def deep_authority(payload: Mapping[str, Any], source_path: Path) -> dict[str, Any]:
    schema = payload.get("schema")
    if schema == "magireco-ac0908-runtime-unique-scene-authority-v2":
        comparison = payload["legacy_longform_code_comparison"]
        return {
            "family_root": "ac0908",
            "audit_state": "AUDITED_BLOCKED",
            "authority_level": "RUNTIME_DIRECTION_PLUS_EXACT_SLOT_IDA_VISIBLE_STRUCTURE",
            "complete_event_container_count": int(payload["counts"]["event_container_count"]),
            "canonical_unique_unit_kind": "visible_runtime_structure",
            "canonical_unique_unit_count": int(
                payload["counts"]["canonical_unique_visible_scene_count"]
            ),
            "old_product_missing_unique_unit_count": int(
                comparison["missing_canonical_visible_scene_count"]
            ),
            "old_product_exact_duplicate_surplus_count": int(
                comparison["guaranteed_exact_duplicate_render_occurrence_surplus_count"]
            ),
            "old_product_authoritative": False,
            "render_allowed": False,
            "blockers": compact_blockers(payload.get("production_blockers")),
            "next_exact_action": "resolve ac0908_016 missing layers and event stop/tail; then bind one 14-structure duplicate-free editorial timeline",
            "authority_path": str(source_path.resolve()),
        }
    if schema == "magireco-ac1102-exhaustive-unique-segment-authority-v1":
        old = payload["legacy_longform"]
        return {
            "family_root": "ac1102",
            "audit_state": "AUDITED_BLOCKED",
            "authority_level": "DIRINFO_RUNTIME_PLUS_EXACT_BINARY_SOURCE_IDENTITY",
            "complete_event_container_count": int(payload["route_universe"]["unique_event_count"]),
            "canonical_unique_unit_kind": "native_source_binary",
            "canonical_unique_unit_count": int(
                payload["native_source_universe"]["unique_sha256_count"]
            ),
            "old_product_missing_unique_unit_count": int(
                old["missing_required_unique_sha256_count"]
            ),
            "old_product_exact_duplicate_surplus_count": int(
                old["duplicate_surplus_occurrence_count"]
            ),
            "old_product_authoritative": False,
            "render_allowed": False,
            "blockers": compact_blockers(payload["decision"]["blockers"]),
            "next_exact_action": "resolve four missing layer identities and strict no-BGM audio for 007/013/014/015; bind each of 36 binaries once",
            "authority_path": str(source_path.resolve()),
        }
    if schema == "magireco-exhaustive-family-source-identity-audit-v1":
        family = str(payload["family"])
        old = payload["legacy_longform"]
        return {
            "family_root": family,
            "audit_state": "AUDITED_BLOCKED",
            "authority_level": "DIRINFO_RUNTIME_PLUS_EXACT_CRI_SOURCE_IDENTITY",
            "complete_event_container_count": int(payload["route_universe"]["unique_event_count"]),
            "canonical_unique_unit_kind": "native_cri_source_identity",
            "canonical_unique_unit_count": int(
                payload["native_source_universe"]["unique_source_identity_count"]
            ),
            "old_product_missing_unique_unit_count": int(
                old["missing_required_unique_source_identity_count"]
            ),
            "old_product_exact_duplicate_surplus_count": int(
                old["duplicate_surplus_occurrence_count"]
            ),
            "old_product_authoritative": False,
            "render_allowed": False,
            "blockers": compact_blockers(payload["decision"]["blockers"]),
            "next_exact_action": "resolve missing component layers and bind one duplicate-free event-global editorial timeline",
            "authority_path": str(source_path.resolve()),
        }
    raise ValueError(f"unsupported deep authority schema: {schema}")


def pending_priority(row: Mapping[str, str]) -> tuple[str, str]:
    missing_layers = int(row["missing_layer_event_count"])
    direction = int(row["direction_scene_decode_required_event_count"])
    old_gap = int(row["old_manifest_missing_event_count"])
    if not missing_layers and not direction:
        lane = "P1_STATIC_MEDIA_BOUND_NEEDS_RUNTIME_STRUCTURE"
    elif missing_layers and not direction:
        lane = "P2_MISSING_LAYERS"
    elif direction and not missing_layers:
        lane = "P3_DIRECTION_STRUCTURE_GAPS"
    else:
        lane = "P4_MIXED_LAYER_AND_DIRECTION_GAPS"
    action = (
        "capture/decode the complete runtime Direction structure and deduplicate exact source identities"
        if not missing_layers and not direction
        else "resolve missing layer media, then capture/decode the complete runtime Direction structure"
        if missing_layers and not direction
        else "decode missing Direction scene/cut/blank structures, then deduplicate exact source identities"
        if direction and not missing_layers
        else "resolve missing media and Direction structures before unique-segment enumeration"
    )
    if old_gap:
        action += f"; old manifests currently omit {old_gap} event candidates"
    return lane, action


def build_queue(
    ledger_rows: list[dict[str, str]],
    authorities: list[tuple[dict[str, Any], Path]],
    expected_family_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(ledger_rows) != expected_family_count:
        raise ValueError("native-416 family count differs")
    by_family = {row["family_root"]: row for row in ledger_rows}
    if len(by_family) != expected_family_count:
        raise ValueError("native-416 family roots are not unique")
    deep = {}
    for payload, path in authorities:
        row = deep_authority(payload, path)
        family = row["family_root"]
        if family in deep or family not in by_family:
            raise ValueError(f"deep authority family differs: {family}")
        deep[family] = row

    queue: list[dict[str, Any]] = []
    for family, base in sorted(by_family.items()):
        common = {
            "family_root": family,
            "content_group_count": 1,
            "inventory_edition_item_count": int(base["inventory_item_count"]),
            "owner_playback_approved_edition_count": int(
                base["owner_playback_approved_item_count"]
            ),
            "static_event_candidate_count": int(base["native_eventinfo_container_count"]),
            "dirinfo_route_count": int(base["dirinfo_route_count"]),
            "old_manifest_missing_event_count": int(base["old_manifest_missing_event_count"]),
            "missing_layer_event_count": int(base["missing_layer_event_count"]),
            "direction_structure_gap_event_count": int(
                base["direction_scene_decode_required_event_count"]
            ),
        }
        if family in deep:
            queue.append({**common, **deep[family]})
            continue
        lane, action = pending_priority(base)
        queue.append(
            {
                **common,
                "audit_state": "PENDING_CODE_AUDIT",
                "authority_level": "STATIC_EVENT_DGM_CANDIDATE_LEDGER_ONLY",
                "complete_event_container_count": int(
                    base["native_eventinfo_container_count"]
                ),
                "canonical_unique_unit_kind": "UNRESOLVED",
                "canonical_unique_unit_count": "UNRESOLVED",
                "old_product_missing_unique_unit_count": "UNRESOLVED",
                "old_product_exact_duplicate_surplus_count": "UNRESOLVED",
                "old_product_authoritative": False,
                "render_allowed": False,
                "blockers": lane,
                "next_exact_action": action,
                "authority_path": "",
            }
        )

    lane_order = {
        "AUDITED_BLOCKED": 5,
        "PENDING_CODE_AUDIT": 0,
    }
    queue.sort(
        key=lambda row: (
            lane_order[row["audit_state"]],
            row["blockers"].split("|", 1)[0],
            row["static_event_candidate_count"],
            row["family_root"],
        )
    )
    for index, row in enumerate(queue, 1):
        row["queue_order"] = index

    summary = {
        "schema": "magireco-native416-longform-code-audit-queue-v1",
        "result": "PASS_RENDER_PAUSED",
        "family_content_group_count": len(queue),
        "inventory_edition_item_count": sum(
            row["inventory_edition_item_count"] for row in queue
        ),
        "deep_audited_family_count": len(deep),
        "pending_code_audit_family_count": len(queue) - len(deep),
        "certified_authoritative_longform_count": 0,
        "render_allowed_family_count": 0,
        "materials_in_scope": False,
        "larger_resolution_in_scope": False,
        "edition_counted_as_content_group": False,
        "machine_vision_used_as_authority": False,
        "source_media_modified": False,
    }
    return queue, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--authority", type=Path, action="append", default=[])
    parser.add_argument("--expected-family-count", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    queue, summary = build_queue(
        read_csv(args.ledger),
        [(read_json(path), path) for path in args.authority],
        args.expected_family_count,
    )
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(args.output_dir / "NATIVE416_LONGFORM_CODE_AUDIT_QUEUE.csv", queue)
    (args.output_dir / "NATIVE416_LONGFORM_CODE_AUDIT_QUEUE.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
