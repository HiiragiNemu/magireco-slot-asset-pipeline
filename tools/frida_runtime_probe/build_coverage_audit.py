#!/usr/bin/env python3
"""Build an event coverage audit from production manifests and local QA outputs."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-manifest-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--single-event-root", action="append", default=[])
    parser.add_argument("--series-root", action="append", default=[])
    parser.add_argument("--material-root", action="append", default=[])
    parser.add_argument(
        "--material-prefix-coverage",
        action="store_true",
        help="treat a passed material collection as covering excluded events with the same prefix",
    )
    parser.add_argument(
        "--invalidated-output-roots",
        action="append",
        default=[],
        help=(
            "JSON file listing output roots that must not count as coverage. "
            "Entries use {'invalidated_roots': [{'path': '...', 'reason': '...'}]}."
        ),
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def event_prefix(event: str) -> str:
    return event.split("_", 1)[0]


def event_sort_key(event: str) -> tuple:
    import re

    return tuple(
        int(token) if token.isdigit() else token.casefold()
        for token in re.split(r"(\d+)", event)
    )


def normalize_path(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def is_under_any(path: Path | str, roots: set[str]) -> bool:
    if not roots:
        return False
    normalized = normalize_path(path)
    for root in roots:
        try:
            if os.path.commonpath([normalized, root]) == root:
                return True
        except ValueError:
            continue
    return False


def load_invalidated_roots(paths: list[Path]) -> tuple[set[str], list[dict]]:
    roots: set[str] = set()
    entries: list[dict] = []
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("invalidated_roots", []):
            raw_path = str(row.get("path", "")).strip()
            if not raw_path:
                continue
            normalized = normalize_path(raw_path)
            roots.add(normalized)
            entries.append(
                {
                    "path": raw_path,
                    "reason": str(row.get("reason", "")).strip(),
                    "source": str(path),
                }
            )
    return roots, entries


def discover_single_event_qa(
    paths: list[Path],
    invalidated_roots: set[str],
) -> dict[str, set[str]]:
    events: dict[str, set[str]] = defaultdict(set)
    for root in paths:
        if not root.exists():
            continue
        if is_under_any(root, invalidated_roots):
            continue
        audit_paths = [root] if root.name == "full_qa_audit.csv" else root.rglob("full_qa_audit.csv")
        for audit_path in audit_paths:
            if not audit_path.is_file():
                continue
            if is_under_any(audit_path, invalidated_roots):
                continue
            for row in read_csv(audit_path):
                if row.get("status") == "passed" and row.get("event"):
                    events[row["event"]].add(str(audit_path.parent))
    return events


def discover_render_manifests(
    paths: list[Path],
    invalidated_roots: set[str],
) -> dict[str, set[str]]:
    events: dict[str, set[str]] = defaultdict(set)
    for root in paths:
        if not root.exists():
            continue
        if is_under_any(root, invalidated_roots):
            continue
        manifest_paths = [root] if root.name == "render_manifest.json" else root.rglob("render_manifest.json")
        for manifest_path in manifest_paths:
            if not manifest_path.is_file():
                continue
            if is_under_any(manifest_path, invalidated_roots):
                continue
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            event = str(payload.get("event", "")).strip()
            if event:
                events[event].add(str(manifest_path))
    return events


def discover_series(
    paths: list[Path],
    invalidated_roots: set[str],
) -> dict[str, set[str]]:
    events: dict[str, set[str]] = defaultdict(set)
    for root in paths:
        if not root.exists():
            continue
        if is_under_any(root, invalidated_roots):
            continue
        manifest_paths = [root] if root.name == "series_manifest.json" else root.rglob("series_manifest.json")
        for manifest_path in manifest_paths:
            if not manifest_path.is_file():
                continue
            if is_under_any(manifest_path, invalidated_roots):
                continue
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("status") != "passed":
                continue
            source_events = {
                str(row.get("event", "")).strip()
                for row in payload.get("sources", [])
                if isinstance(row, dict)
            }
            family_state = payload.get("family_state", {})
            if isinstance(family_state, dict):
                source_events.update(
                    str(event).strip()
                    for event in family_state.get("ready_event_names", [])
                )
            for event in source_events:
                if event:
                    events[event].add(str(manifest_path))
    return events


def discover_material(
    paths: list[Path],
    production_events_for_prefix_coverage: list[str],
    prefix_coverage: bool,
    invalidated_roots: set[str],
) -> dict[str, set[str]]:
    events: dict[str, set[str]] = defaultdict(set)
    events_by_prefix: dict[str, list[str]] = defaultdict(list)
    for event in production_events_for_prefix_coverage:
        events_by_prefix[event_prefix(event)].append(event)
    for root in paths:
        if not root.exists():
            continue
        if is_under_any(root, invalidated_roots):
            continue
        manifest_paths = (
            [root]
            if root.name == "material_collection_manifest.json"
            else root.rglob("material_collection_manifest.json")
        )
        for manifest_path in manifest_paths:
            if not manifest_path.is_file():
                continue
            if is_under_any(manifest_path, invalidated_roots):
                continue
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if payload.get("status") != "passed":
                continue
            collection_series = str(payload.get("series", "")).strip()
            source_events = set()
            for key in ("sources", "audible_event_sources"):
                for row in payload.get(key, []):
                    if isinstance(row, dict) and str(row.get("event", "")).strip():
                        source_events.add(str(row["event"]).strip())
            for event in source_events:
                events[event].add(str(manifest_path))
            if prefix_coverage and collection_series:
                for event in events_by_prefix.get(collection_series, []):
                    events[event].add(str(manifest_path))
    return events


def main() -> int:
    args = parse_args()
    manifest_root = Path(args.production_manifest_root)
    manifest_dir = manifest_root / "events"
    if not manifest_dir.is_dir():
        manifest_dir = manifest_root
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifests: dict[str, dict] = {}
    manifest_paths: dict[str, str] = {}
    for path in sorted(manifest_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        event = str(payload.get("event", "")).strip()
        if event:
            manifests[event] = payload
            manifest_paths[event] = str(path)

    single_roots = [Path(path) for path in args.single_event_root]
    series_roots = [Path(path) for path in args.series_root]
    material_roots = [Path(path) for path in args.material_root]
    invalidated_roots, invalidated_entries = load_invalidated_roots(
        [Path(path) for path in args.invalidated_output_roots]
    )
    single_qa = discover_single_event_qa(single_roots, invalidated_roots)
    render_manifests = discover_render_manifests(single_roots, invalidated_roots)
    series = discover_series(series_roots, invalidated_roots)
    excluded_production_events = [
        event
        for event, manifest in manifests.items()
        if manifest.get("audience_exclusion_reason")
    ]
    material = discover_material(
        material_roots,
        excluded_production_events,
        args.material_prefix_coverage,
        invalidated_roots,
    )

    rows: list[dict] = []
    for event in sorted(manifests, key=event_sort_key):
        manifest = manifests[event]
        gates = manifest.get("quality_gates", {})
        ready = bool(gates.get("ready"))
        audience_excluded = bool(manifest.get("audience_exclusion_reason"))
        single_pass = event in single_qa
        series_memberships = sorted(series.get(event, set()))
        material_memberships = sorted(material.get(event, set()))
        if audience_excluded:
            next_action = (
                "covered_by_material_collection"
                if material_memberships
                else "material_review_candidate_or_document_exclusion_only"
            )
        elif ready and single_pass and series_memberships:
            next_action = "covered_by_single_and_series"
        elif ready and not single_pass:
            next_action = "render_single_event_and_QA"
        elif ready:
            next_action = "review_for_series_or_keep_single_event"
        else:
            next_action = "investigate_non_excluded_failed"
        rows.append(
            {
                "event": event,
                "ready": "yes" if ready else "no",
                "audience_excluded": "yes" if audience_excluded else "no",
                "audience_exclusion_reason": manifest.get("audience_exclusion_reason", ""),
                "errors": ";".join(gates.get("errors", [])),
                "classification": manifest.get("classification", ""),
                "width": manifest.get("native_dimensions", {}).get("width", ""),
                "height": manifest.get("native_dimensions", {}).get("height", ""),
                "frame_rate": manifest.get("native_frame_rate", ""),
                "render_duration_ms": manifest.get("render_duration_ms", ""),
                "subtitle_count": len(manifest.get("subtitles", [])),
                "production_manifest": manifest_paths[event],
                "single_event_qa_passed": "yes" if single_pass else "no",
                "single_event_qa_roots": "|".join(sorted(single_qa.get(event, set()))),
                "render_manifest_count": len(render_manifests.get(event, set())),
                "render_manifests": "|".join(sorted(render_manifests.get(event, set()))),
                "series_memberships": "|".join(series_memberships),
                "material_memberships": "|".join(material_memberships),
                "next_action": next_action,
            }
        )

    fields = [
        "event",
        "ready",
        "audience_excluded",
        "audience_exclusion_reason",
        "errors",
        "classification",
        "width",
        "height",
        "frame_rate",
        "render_duration_ms",
        "subtitle_count",
        "production_manifest",
        "single_event_qa_passed",
        "single_event_qa_roots",
        "render_manifest_count",
        "render_manifests",
        "series_memberships",
        "material_memberships",
        "next_action",
    ]
    csv_path = out_dir / "event_coverage_v18.csv"
    write_csv(csv_path, rows, fields)
    summary = {
        "events": len(rows),
        "ready_events": sum(row["ready"] == "yes" for row in rows),
        "audience_excluded_events": sum(
            row["audience_excluded"] == "yes" for row in rows
        ),
        "ready_with_single_event_QA": sum(
            row["ready"] == "yes" and row["single_event_qa_passed"] == "yes"
            for row in rows
        ),
        "ready_missing_single_event_QA": sum(
            row["ready"] == "yes" and row["single_event_qa_passed"] != "yes"
            for row in rows
        ),
        "ready_with_series_or_preserved": sum(
            row["ready"] == "yes" and bool(row["series_memberships"])
            for row in rows
        ),
        "ready_without_series": sum(
            row["ready"] == "yes" and not row["series_memberships"]
            for row in rows
        ),
        "excluded_with_material_collection": sum(
            row["audience_excluded"] == "yes" and bool(row["material_memberships"])
            for row in rows
        ),
        "excluded_without_material_collection": sum(
            row["audience_excluded"] == "yes" and not row["material_memberships"]
            for row in rows
        ),
        "next_action_counts": dict(
            sorted(
                (
                    (
                        action,
                        sum(row["next_action"] == action for row in rows),
                    )
                    for action in {row["next_action"] for row in rows}
                ),
                key=lambda item: item[0],
            )
        ),
        "material_prefix_coverage": bool(args.material_prefix_coverage),
        "invalidated_output_root_count": len(invalidated_entries),
        "invalidated_output_roots": invalidated_entries,
        "audit_csv": str(csv_path),
    }
    (out_dir / "event_coverage_v18_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
