#!/usr/bin/env python3
"""Build a native-code-first uniqueness ledger for 416x232 audience families."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT_RE = re.compile(r"ac\d{4}")
EVENT_RE = re.compile(r"ac\d{4}_\d{3}")
AUDIENCE_TYPES = {"clean_story", "story_route", "gameplay_effect"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def root_of(value: str) -> str:
    match = ROOT_RE.search(value or "")
    return match.group(0) if match else ""


def parse_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def direct_manifest_events(payload: Any) -> set[str]:
    """Read composition keys, excluding provenance/source-snapshot subtrees."""
    events: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str):
            events.update(EVENT_RE.findall(value))
        elif isinstance(value, list):
            for item in value:
                add(item)

    if not isinstance(payload, dict):
        return events
    for key in ("ordered_events", "route_order", "event_ids", "events"):
        add(payload.get(key))
    timeline = payload.get("timeline")
    if isinstance(timeline, list):
        for row in timeline:
            if isinstance(row, dict):
                add(row.get("event"))
                add(row.get("event_id"))
    routes = payload.get("routes")
    if isinstance(routes, list):
        for route in routes:
            if isinstance(route, dict):
                for key in ("ordered_events", "route_order", "event_ids"):
                    add(route.get(key))
    showcase = payload.get("showcase")
    if isinstance(showcase, dict):
        events.update(direct_manifest_events(showcase))
    return events


def manifest_events(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if path in cache:
        return cache[path]
    if not path.is_file():
        cache[path] = set()
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache[path] = set()
        return set()
    events = direct_manifest_events(payload)
    if isinstance(payload, dict):
        artifacts = payload.get("artifacts")
        child = artifacts.get("manifest") if isinstance(artifacts, dict) else None
        child_path = child.get("path") if isinstance(child, dict) else None
        if isinstance(child_path, str) and child_path:
            events.update(manifest_events(path.parent / child_path, cache))
    cache[path] = events
    return cache[path]


def build_ledger(
    inventory_rows: list[dict[str, str]],
    event_info_rows: list[dict[str, str]],
    dirinfo_rows: list[dict[str, str]],
    dgm_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    scope = [
        row
        for row in inventory_rows
        if row.get("resolution") == "416x232" and row.get("content_type") in AUDIENCE_TYPES
    ]
    inventory_by_root: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in scope:
        root = root_of(row.get("family", "") or row.get("series", ""))
        if root:
            inventory_by_root[root].append(row)

    native_by_root: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in event_info_rows:
        root = row.get("base_name", "")
        if ROOT_RE.fullmatch(root) and EVENT_RE.fullmatch(row.get("scene_name", "")):
            native_by_root[root].append(row)

    route_events: dict[str, dict[int, list[tuple[int, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in dirinfo_rows:
        root = row.get("base_name", "")
        event = row.get("scene_name", "")
        if root in inventory_by_root and EVENT_RE.fullmatch(event):
            route_events[root][int(row["row_index"])].append((int(row["selector_raw"]), event))

    dgm_by_root: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in dgm_rows:
        event = row.get("event_name", "")
        root = root_of(event)
        if root in inventory_by_root and EVENT_RE.fullmatch(event):
            dgm_by_root[root].append(row)

    manifest_cache: dict[Path, set[str]] = {}
    family_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for root in sorted(inventory_by_root):
        items = inventory_by_root[root]
        native = native_by_root.get(root, [])
        native_events = {row["scene_name"] for row in native}
        native_codes = {row["code_hex"] for row in native}
        routes = route_events.get(root, {})
        reachable = {
            event
            for values in routes.values()
            for _, event in values
            if root_of(event) == root
        }
        inventory_events: set[str] = set()
        manifest_path_count = 0
        parsed_manifest_count = 0
        for item in items:
            inventory_events.update(
                event for event in parse_list(item.get("event_ids", "")) if root_of(event) == root
            )
            raw_manifest = item.get("source_manifest", "")
            if raw_manifest:
                manifest_path_count += 1
                path = Path(raw_manifest)
                parsed = manifest_events(path, manifest_cache)
                if path.is_file():
                    parsed_manifest_count += 1
                inventory_events.update(event for event in parsed if root_of(event) == root)

        # A container reached only through a direct macro/component path must not
        # disappear merely because it is absent from the decoded DirInfo rows.
        candidate_events = reachable | native_events
        dgms = dgm_by_root.get(root, [])
        by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in dgms:
            by_event[row["event_name"]].append(row)
        source_identities = {
            f"{row.get('package','')}:{row.get('package_index','')}:{row.get('official_name','')}"
            for row in dgms
            if row.get("cri_match") == "yes"
        }
        duration_by_identity: dict[str, float] = {}
        for row in dgms:
            if row.get("cri_match") != "yes" or not row.get("media_duration_sec"):
                continue
            identity = f"{row.get('package','')}:{row.get('package_index','')}:{row.get('official_name','')}"
            duration_by_identity.setdefault(identity, float(row["media_duration_sec"]))
        source_duration_sum = sum(duration_by_identity.values())

        fully_bound = 0
        missing_layer_events = []
        needs_direction = []
        for event in sorted(candidate_events):
            rows = by_event.get(event, [])
            missing = [row for row in rows if row.get("cri_match") != "yes"]
            exact_identities = {
                f"{row.get('package','')}:{row.get('package_index','')}:{row.get('official_name','')}"
                for row in rows
                if row.get("cri_match") == "yes"
            }
            parent_span = max(
                (int(float(row["event_end_ms"])) for row in rows if row.get("event_end_ms")),
                default=None,
            )
            if rows and not missing:
                fully_bound += 1
            elif rows:
                missing_layer_events.append(event)
            else:
                needs_direction.append(event)
            event_rows.append(
                {
                    "family_root": root,
                    "event": event,
                    "reachable_from_dirinfo": event in reachable,
                    "eventinfo_present": event in native_events,
                    "covered_by_old_product_manifest": event in inventory_events,
                    "exact_dgm_source_count": len(exact_identities),
                    "missing_dgm_layer_count": len(missing),
                    "known_parent_z2d_span_ms": "" if parent_span is None else parent_span,
                    "next_authority_step": (
                        "ROUTE_UNION_AND_SHARED_COMPONENT_DEDUP"
                        if rows and not missing
                        else "RESOLVE_MISSING_DGM_LAYERS"
                        if rows
                        else "DECODE_DIRECTION_CUT_BLANK_LAYER_TIMELINE"
                    ),
                }
            )

        approved = [row for row in items if str(row.get("owner_approved", "")).casefold() == "true"]
        family_rows.append(
            {
                "family_root": root,
                "inventory_family_labels": "|".join(sorted({row.get("family", "") for row in items})),
                "inventory_item_count": len(items),
                "owner_playback_approved_item_count": len(approved),
                "native_eventinfo_container_count": len(native_events),
                "native_unique_event_code_count": len(native_codes),
                "dirinfo_route_count": len(routes),
                "dirinfo_reachable_event_count": len(reachable),
                "old_manifest_covered_event_count": len(inventory_events & candidate_events),
                "old_manifest_missing_event_count": len(candidate_events - inventory_events),
                "old_manifest_missing_events": "|".join(sorted(candidate_events - inventory_events)),
                "manifest_path_count": manifest_path_count,
                "parsed_manifest_count": parsed_manifest_count,
                "unique_bound_dgm_source_count": len(source_identities),
                "sum_unique_bound_dgm_source_duration_sec": f"{source_duration_sum:.6f}",
                "fully_bound_event_count": fully_bound,
                "missing_layer_event_count": len(missing_layer_events),
                "missing_layer_events": "|".join(missing_layer_events),
                "direction_scene_decode_required_event_count": len(needs_direction),
                "direction_scene_decode_required_events": "|".join(needs_direction),
                "final_unique_visible_segment_count": "UNRESOLVED",
                "final_longform_authority": "BLOCKED_PENDING_CODE_LEVEL_UNIQUE_SEGMENT_AND_DURATION_CLOSURE",
            }
        )

    summary = {
        "schema": "magireco-416-native-family-uniqueness-ledger-v1",
        "result": "PASS_FAIL_CLOSED",
        "production_paused": True,
        "family_root_count": len(family_rows),
        "inventory_item_count": len(scope),
        "event_candidate_count": len(event_rows),
        "certified_exhaustive_family_count": 0,
        "families_with_known_old_manifest_gaps": sum(
            row["old_manifest_missing_event_count"] > 0 for row in family_rows
        ),
        "families_requiring_direction_scene_decode": sum(
            row["direction_scene_decode_required_event_count"] > 0 for row in family_rows
        ),
        "machine_vision_used_as_authority": False,
        "source_media_modified": False,
    }
    return family_rows, event_rows, summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    families, events, summary = build_ledger(
        read_csv(args.review_index),
        read_csv(args.event_info_csv),
        read_csv(args.dirinfo_routes_csv),
        read_csv(args.dgm_timeline),
    )
    args.output_root.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_root / "NATIVE_FAMILY_UNIQUENESS_LEDGER.csv", families)
    write_csv(args.output_root / "NATIVE_EVENT_DURATION_GATES.csv", events)
    write_json(args.output_root / "NATIVE_FAMILY_UNIQUENESS_SUMMARY.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-index", type=Path, required=True)
    parser.add_argument("--event-info-csv", type=Path, required=True)
    parser.add_argument("--dirinfo-routes-csv", type=Path, required=True)
    parser.add_argument("--dgm-timeline", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
