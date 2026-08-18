#!/usr/bin/env python3
"""Conservatively audit native 416x232 audience products for family completeness."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


EVENT_RE = re.compile(r"ac\d{4}_\d{3}")
ROOT_RE = re.compile(r"ac\d{4}")
AUDIENCE_TYPES = {"clean_story", "story_route", "gameplay_effect"}
TARGET_RESOLUTION = "416x232"
DEFAULT_POLICY = Path(__file__).with_name("audience_longform_policy_v1.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    values = list(rows)
    fields: list[str] = []
    for row in values:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def parse_json_list(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def event_ids_from_inventory(row: Mapping[str, str]) -> list[str]:
    values = parse_json_list(row.get("event_ids", ""))
    if not values:
        values = parse_json_list(row.get("source_ids", ""))
    return [value for value in values if EVENT_RE.fullmatch(value)]


def family_root(value: str) -> str:
    match = ROOT_RE.search(value or "")
    return match.group(0) if match else ""


def split_ordered_events(value: str) -> list[str]:
    return [item for item in (value or "").split("|") if EVENT_RE.fullmatch(item)]


def build_ledger(
    inventory_rows: list[dict[str, str]],
    dirinfo_rows: list[dict[str, str]],
    policy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    scope = [
        row
        for row in inventory_rows
        if row.get("resolution") == TARGET_RESOLUTION
        and row.get("content_type") in AUDIENCE_TYPES
    ]
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in scope:
        by_family[row.get("family", "unknown")].append(row)

    dirinfo_by_root: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in dirinfo_rows:
        events = split_ordered_events(row.get("ordered_events", ""))
        for root in {family_root(event) for event in events} - {""}:
            dirinfo_by_root[root].append(row)

    known = {str(row["family"]): row for row in policy.get("known_family_coverage", [])}
    family_rows: list[dict[str, Any]] = []
    withdrawals: list[dict[str, Any]] = []

    for family in sorted(by_family):
        items = by_family[family]
        root = family_root(family)
        route_rows = dirinfo_by_root.get(root, [])
        discovered = sorted(
            {
                event
                for route in route_rows
                for event in split_ordered_events(route.get("ordered_events", ""))
                if family_root(event) == root
            }
        )
        inventory_events = sorted({event for row in items for event in event_ids_from_inventory(row)})
        override = known.get(root)
        if override:
            included = list(override["included_unique_events"])
            discovered = list(override["discovered_event_candidates"])
            missing = list(override["missing_event_candidates"])
            status = "KNOWN_INCOMPLETE"
            reason = str(override["reason"])
            authority = str(override["current_authority"])
        else:
            included = inventory_events
            missing = sorted(set(discovered) - set(included))
            status = (
                "NEEDS_STATIC_UNIVERSE_CLASSIFICATION"
                if not discovered
                else "NEEDS_EXHAUSTIVE_REVERSE_AUDIT"
            )
            reason = (
                "no DirInfo event universe is bound to this inventory family"
                if not discovered
                else "DirInfo candidates are not yet classified into unique visible variants, aliases, nonvisual nodes, and the final deduplicated family order"
            )
            authority = "NOT_CERTIFIED_EXHAUSTIVE"

        approved = [row for row in items if str(row.get("owner_approved", "")).casefold() == "true"]
        editions = Counter(row.get("edition", "") for row in items)
        canonical_media = {row.get("canonical_sha256") or row.get("sha256") for row in items}
        canonical_media.discard("")
        record = {
            "inventory_family": family,
            "reverse_family_root": root,
            "status": status,
            "authority": authority,
            "final_family_product_gate": "BLOCKED_PENDING_EXHAUSTIVE_UNIQUE_VARIANT_CLOSURE",
            "inventory_item_count": len(items),
            "canonical_media_count": len(canonical_media),
            "none_item_count": editions.get("none", 0),
            "ja_item_count": editions.get("ja", 0),
            "zh_item_count": editions.get("zh", 0),
            "owner_playback_approved_item_count": len(approved),
            "dirinfo_route_row_count": len(route_rows),
            "discovered_event_candidate_count": len(discovered),
            "known_included_event_container_count": len(included),
            "known_included_unique_event_count": len(included),
            "missing_event_candidate_count": len(missing),
            "discovered_event_candidates": "|".join(discovered),
            "known_included_unique_events": "|".join(included),
            "missing_event_candidates": "|".join(missing),
            "final_unique_visible_segment_count": (
                override.get("final_unique_visible_segment_count", "UNRESOLVED")
                if override
                else "UNRESOLVED"
            ),
            "known_duplicate_occurrence_surplus_count": (
                override.get("old_showcase_duplicate_evidence", {}).get(
                    "surplus_occurrence_count", 0
                )
                if override
                else 0
            ),
            "reason": reason,
        }
        family_rows.append(record)
        for row in approved:
            withdrawals.append(
                {
                    "inventory_item_id": row.get("inventory_item_id", ""),
                    "family": family,
                    "edition": row.get("edition", ""),
                    "title": row.get("title", ""),
                    "source_absolute_path": row.get("source_absolute_path", ""),
                    "sha256": row.get("sha256", ""),
                    "old_human_status": row.get("human_status", ""),
                    "new_authority": authority,
                    "action": "REMOVE_FROM_AUTHORITATIVE_COMPLETE_REVIEW_LANE_KEEP_SOURCE_AND_PLAYBACK_APPROVAL_RECORD",
                    "reason": reason,
                }
            )

    summary = {
        "schema": "magireco-416-exhaustive-family-coverage-audit-v1",
        "result": "PASS",
        "scope": "416x232 non-material audience products",
        "inventory_item_count": len(scope),
        "inventory_family_label_count": len(family_rows),
        "reverse_family_root_count": len({row["reverse_family_root"] for row in family_rows}),
        "owner_approved_items_requiring_completeness_reaudit": len(withdrawals),
        "known_incomplete_family_labels": sum(row["status"] == "KNOWN_INCOMPLETE" for row in family_rows),
        "certified_exhaustive_family_labels": 0,
        "production_paused": True,
        "source_media_modified": False,
        "materials_in_scope": False,
        "larger_resolutions_in_scope": False,
    }
    return family_rows, withdrawals, summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    policy = read_json(args.policy)
    families, withdrawals, summary = build_ledger(
        read_csv(args.review_index), read_csv(args.dirinfo_ledger), policy
    )
    if args.output_root:
        args.output_root.mkdir(parents=True, exist_ok=False)
        write_json(args.output_root / "POLICY_SNAPSHOT.json", policy)
        write_json(args.output_root / "FAMILY_COVERAGE_LEDGER.json", families)
        write_csv(args.output_root / "FAMILY_COVERAGE_LEDGER.csv", families)
        write_json(args.output_root / "WITHDRAW_FROM_COMPLETE_CLAIM.json", withdrawals)
        write_csv(args.output_root / "WITHDRAW_FROM_COMPLETE_CLAIM.csv", withdrawals)
        ac0908 = next(row for row in families if row["reverse_family_root"] == "ac0908")
        write_json(args.output_root / "AC0908_COVERAGE.json", ac0908)
        write_json(args.output_root / "VERIFICATION.json", summary)
        (args.output_root / "README.md").write_text(
            "# 416x232 非素材穷尽合并复核\n\n"
            "- 本总账把 DirInfo/EventInfo/IDA/runtime/composition 发现的所有候选变体作为母集。\n"
            "- EventInfo 容器数不是可见视频数；必须继续解 Cut/Blank/Layer 与共享组件后才能给出最终唯一片段数。\n"
            "- 互斥路线必须进入同一个 family 长片；共用片段只出现一次。\n"
            "- 人工播放通过只证明具体文件的观看结果，不证明 family 已穷尽。\n"
            "- 当前没有任何 family 获得穷尽证书，故生产与权威长片准入保持暂停。\n"
            "- 素材和非 416x232 产品不在本轮范围；源媒体没有移动、删除或转码。\n",
            encoding="utf-8",
        )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--review-index", type=Path, required=True)
    parser.add_argument("--dirinfo-ledger", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    return parser.parse_args()


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
