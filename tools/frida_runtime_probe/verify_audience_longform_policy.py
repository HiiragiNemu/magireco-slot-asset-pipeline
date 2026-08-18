#!/usr/bin/env python3
"""Build a non-destructive authority overlay for the manual-review inventory."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


DEFAULT_POLICY = Path(__file__).with_name("audience_longform_policy_v1.json")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def withdrawal_map(policy: dict) -> dict[str, dict]:
    result = {}
    for group in policy["withdraw_inventory_items_from_longform_review"]:
        for item_id in group["inventory_item_ids"]:
            if item_id in result:
                raise ValueError(f"duplicate withdrawal inventory id: {item_id}")
            result[item_id] = group
    return result


def is_single_event_family(value: str) -> bool:
    return bool(re.fullmatch(r"ac\d{4}_\d{3}", value or ""))


def classify_item(item: dict, withdrawals: dict[str, dict]) -> tuple[str, str]:
    item_id = str(item.get("inventory_item_id", ""))
    if item_id in withdrawals:
        return "WITHDRAW_FROM_LONGFORM_REVIEW", withdrawals[item_id]["reason"]
    if item.get("resolution") == "512x288":
        return "DEFER_512X288", "record evidence; 416x232 production has priority"
    if (
        item.get("review_disposition") == "REVIEW_READY"
        and item.get("content_type") in {"story_route", "gameplay_effect", "clean_story"}
        and is_single_event_family(str(item.get("family", "")))
    ):
        return (
            "REQUIRES_FAMILY_LONGFORM_AUDIT",
            "single-event audience archive requires a family/route long-form composition",
        )
    return "PRESERVE_CURRENT_METADATA_PENDING_AUDIT", "not changed by this bounded pass"


def load_review_items(path: Path) -> list[dict]:
    items = read_json(path).get("items")
    if not isinstance(items, list):
        raise ValueError("review index has no items list")
    return items


def load_ledger(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def route_memberships(rows: list[dict], event: str) -> list[dict]:
    return [row for row in rows if event in row["ordered_events"].split("|")]


def compare_ac1102(old_manifest: Path, v77_root: Path) -> dict:
    old = read_json(old_manifest)
    manifests = sorted(v77_root.glob("ac1102_route*_full_no_bgm_editions_v1/manifests/family_editions_manifest.json"))
    if len(manifests) != 16:
        raise ValueError(f"expected 16 v77 route manifests, got {len(manifests)}")
    routes = []
    union = set()
    for path in manifests:
        payload = read_json(path)
        ordered = payload["ordered_events"]
        union.update(ordered)
        routes.append(
            {
                "release_id": payload["release_id"],
                "ordered_events": ordered,
                "duration_ms": payload["media"]["duration_ms"],
                "natural_session_claimed": payload["natural_session_claimed"],
                "manifest_path": str(path),
            }
        )
    old_order = old["ordered_events"]
    return {
        "schema": "magireco-ac1102-longform-authority-comparison-v1",
        "legacy": {
            "path": str(old_manifest),
            "duration_ms": old["media"]["duration_ms"],
            "ordered_events": old_order,
            "authority": "WITHDRAWN_AS_NATURAL_OR_AUTHORITATIVE_CHAPTER",
            "reason": "contains mutually exclusive DirInfo nodes in one linear event list",
        },
        "v77": {
            "root": str(v77_root),
            "route_count": len(routes),
            "unique_event_count": len(union),
            "unique_events": sorted(union),
            "same_unique_event_set_as_legacy": set(old_order) == union,
            "routes": routes,
            "authority": "ROUTE_ORDER_EVIDENCE_AND_LONGFORM_SOURCE_SEGMENTS_ONLY",
        },
        "longform_decision": {
            "render_now": False,
            "required_product": "chaptered_ac1102_family_longform",
            "deduplicate_shared_events": True,
            "label_mutually_exclusive_outcomes": True,
            "claim_native_single_session": False,
            "remaining_dirinfo_rows_must_be_closed": True
        }
    }


def build_audit(args: argparse.Namespace) -> dict:
    policy = read_json(args.policy)
    withdrawals = withdrawal_map(policy)
    items = load_review_items(args.review_index)
    ledger = load_ledger(args.dirinfo_ledger)
    classified = []
    matched = set()
    for item in items:
        action, reason = classify_item(item, withdrawals)
        item_id = str(item.get("inventory_item_id", ""))
        if action == "WITHDRAW_FROM_LONGFORM_REVIEW":
            matched.add(item_id)
        classified.append(
            {
                "inventory_item_id": item_id,
                "family": item.get("family", ""),
                "content_type": item.get("content_type", ""),
                "edition": item.get("edition", ""),
                "duration_sec": item.get("duration_sec", ""),
                "resolution": item.get("resolution", ""),
                "source_absolute_path": item.get("source_absolute_path", ""),
                "review_absolute_path": item.get("review_absolute_path", ""),
                "old_review_disposition": item.get("review_disposition", ""),
                "new_longform_action": action,
                "reason": reason
            }
        )
    missing = sorted(set(withdrawals) - matched)
    route_targets = {}
    for event in ("ac1103_013", "ac7205_008", "ac7205_016", "ac7002_001"):
        memberships = route_memberships(ledger, event)
        route_targets[event] = {
            "membership_count": len(memberships),
            "rows": [
                {
                    "kind": row["kind"],
                    "row_index": int(row["row_index"]),
                    "ordered_events": row["ordered_events"].split("|")
                }
                for row in memberships
            ]
        }
    comparison = compare_ac1102(args.ac1102_legacy_manifest, args.ac1102_v77_root)
    summary = {
        "schema": "magireco-audience-longform-authority-audit-v1",
        "result": "PASS" if not missing else "FAIL",
        "production_paused": True,
        "review_item_count": len(items),
        "action_counts": dict(Counter(row["new_longform_action"] for row in classified)),
        "explicit_withdrawal_item_count": len(withdrawals),
        "matched_withdrawal_item_count": len(matched),
        "missing_withdrawal_inventory_ids": missing,
        "route_memberships": route_targets,
        "ac1102": comparison,
        "immutable_review_hub_modified": False,
        "source_media_modified": False
    }
    if args.output_root:
        args.output_root.mkdir(parents=True, exist_ok=False)
        write_json(args.output_root / "POLICY_SNAPSHOT.json", policy)
        write_json(args.output_root / "AC1102_AUTHORITY_COMPARISON.json", comparison)
        write_json(args.output_root / "VERIFICATION.json", summary)
        with (args.output_root / "REVIEW_HUB_REASSESSMENT.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(classified[0]))
            writer.writeheader()
            writer.writerows(classified)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--review-index", type=Path, required=True)
    parser.add_argument("--dirinfo-ledger", type=Path, required=True)
    parser.add_argument("--ac1102-legacy-manifest", type=Path, required=True)
    parser.add_argument("--ac1102-v77-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    return parser.parse_args()


def main() -> int:
    summary = build_audit(parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
