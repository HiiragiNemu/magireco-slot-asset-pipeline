#!/usr/bin/env python3
"""Build a hash-bound exhaustive production ledger from current durable catalogs.

This tool does not scan historical render roots.  It consumes only the catalog
and production roots explicitly named by the plan.  Every audience event,
production-manifest event, DirInfo route, and component/mixed candidate receives
one disposition category plus a production state or precise blocker.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .build_ac0908_reference_showcase import read_json, validate_bound_file
    from .build_independent_scene_release import file_sha256, write_json
except ImportError:  # direct script execution
    from build_ac0908_reference_showcase import (  # type: ignore
        read_json,
        validate_bound_file,
    )
    from build_independent_scene_release import file_sha256, write_json  # type: ignore


PLAN_SCHEMA = "magireco-exhaustive-video-production-ledger-plan-v1"
SUMMARY_SCHEMA = "magireco-exhaustive-video-production-ledger-summary-v1"
EVENT_PATTERN = re.compile(r"^ac\d+(?:_\d+)+$")
NON_CURRENT_SEMANTIC_FIELDS = {
    "source_snapshots",
    "dirinfo_evidence",
    "excluded_dirinfo_rows",
    "excluded_routes",
    "route_failures",
}
DISPOSITIONS = {
    "produced_clean_story_route",
    "gameplay_effect_collection",
    "material_collection",
    "blocked",
}
UNSAFE_CHILD_CONFIDENCE = (
    "exact_gdb_child_frame_callback_frame_and_official_ogg"
)
COMPONENT_CLASSIFICATIONS = {
    "component_only",
    "mixed_full_frame_and_components",
}


def _bound(
    raw: Mapping[str, Any],
    *,
    label: str,
    plan_dir: Path,
) -> tuple[Path, dict[str, str]]:
    path, snapshot = validate_bound_file(raw, label=label, plan_dir=plan_dir)
    return path, {
        "label": label,
        "path": str(path.resolve()),
        "sha256": str(snapshot["sha256"]).upper(),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _family(event: str) -> str:
    return event.split("_", 1)[0]


def _events_from_manifest(value: object) -> set[str]:
    """Extract event identities only from timeline/route semantic fields."""

    output: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"ordered_events", "route_order", "render_event_sequence"}:
                if isinstance(child, list):
                    output.update(
                        str(item) for item in child if EVENT_PATTERN.fullmatch(str(item))
                    )
            elif key == "event" and EVENT_PATTERN.fullmatch(str(child)):
                output.add(str(child))
            elif key not in NON_CURRENT_SEMANTIC_FIELDS:
                output.update(_events_from_manifest(child))
    elif isinstance(value, list):
        for child in value:
            output.update(_events_from_manifest(child))
    return output


def _infer_kind(value: Mapping[str, Any], manifest_path: Path) -> int | None:
    raw = value.get("dirinfo_kind")
    if raw is not None:
        return int(raw)
    identity = " ".join(
        [
            str(value.get("family", "")),
            str(value.get("series", "")),
            manifest_path.as_posix(),
        ]
    )
    if "ac0908" in identity:
        return 33
    if "ac4902" in identity:
        return 113
    if "ac4903" in identity:
        return 114
    if "ac7206" in identity:
        return 197
    if "ac7210" in identity:
        return 201
    return None


def _path_matches_exclusion(
    *,
    root: Path,
    path: Path,
    fragments: Sequence[str],
) -> bool:
    relative = path.resolve().relative_to(root.resolve()).as_posix().casefold()
    return any(str(fragment).casefold() in relative for fragment in fragments)


def _produced_dirinfo_rows(
    value: object,
    *,
    default_kind: int | None,
) -> set[tuple[int, int]]:
    output: set[tuple[int, int]] = set()
    if isinstance(value, Mapping):
        local_kind = default_kind
        if value.get("dirinfo_kind") is not None:
            local_kind = int(value["dirinfo_kind"])
        if local_kind is not None and value.get("dirinfo_row") is not None:
            output.add((local_kind, int(value["dirinfo_row"])))
        source_rows = value.get("dirinfo_source_rows")
        if local_kind is not None and isinstance(source_rows, list):
            for row in source_rows:
                if isinstance(row, Mapping) and row.get("row_index") is not None:
                    output.add((local_kind, int(row["row_index"])))
        for key, child in value.items():
            if key not in NON_CURRENT_SEMANTIC_FIELDS:
                output.update(
                    _produced_dirinfo_rows(child, default_kind=local_kind)
                )
    elif isinstance(value, list):
        for child in value:
            output.update(
                _produced_dirinfo_rows(child, default_kind=default_kind)
            )
    return output


def _excluded_dirinfo_rows(
    value: object,
    *,
    default_kind: int | None,
) -> dict[tuple[int, int], dict[str, str]]:
    output: dict[tuple[int, int], dict[str, str]] = {}
    if isinstance(value, Mapping):
        local_kind = default_kind
        if value.get("dirinfo_kind") is not None:
            local_kind = int(value["dirinfo_kind"])
        raw_exclusions = value.get("excluded_dirinfo_rows")
        if local_kind is not None and isinstance(raw_exclusions, list):
            for raw in raw_exclusions:
                if not isinstance(raw, Mapping):
                    continue
                raw_row = raw.get("dirinfo_row", raw.get("row"))
                if raw_row is None:
                    continue
                raw_disposition = str(raw.get("disposition", ""))
                production_disposition = str(
                    raw.get("production_disposition", "")
                )
                disposition = (
                    raw_disposition
                    if raw_disposition in DISPOSITIONS
                    else "blocked"
                )
                blocker = str(raw.get("blocker", "")).strip()
                if not blocker:
                    blocker = (
                        production_disposition
                        or "explicitly_excluded_by_current_production_manifest"
                    )
                output[(local_kind, int(raw_row))] = {
                    "disposition": disposition,
                    "production_state": (
                        "explicitly_excluded_by_current_production_manifest"
                    ),
                    "blocker": blocker,
                }
        for key, child in value.items():
            if key not in NON_CURRENT_SEMANTIC_FIELDS:
                output.update(
                    _excluded_dirinfo_rows(child, default_kind=local_kind)
                )
    elif isinstance(value, list):
        for child in value:
            output.update(
                _excluded_dirinfo_rows(child, default_kind=default_kind)
            )
    return output


def _child_local_timing_risk(manifest: Mapping[str, Any]) -> bool:
    unsafe = any(
        isinstance(row, Mapping)
        and row.get("source") == "z2d_req_sound"
        and row.get("evidence") == UNSAFE_CHILD_CONFIDENCE
        for row in manifest.get("audio", [])
    )
    runtime = manifest.get("runtime_event_manifest_sources")
    has_runtime = isinstance(runtime, list) and bool(runtime)
    return unsafe and not has_runtime


def _errors(row: Mapping[str, str]) -> str:
    value = str(row.get("errors", "")).strip().strip(";")
    return value or "modern_event_manifest_not_ready"


def _classify_production_event(
    *,
    event: str,
    row: Mapping[str, str],
    audience_classification: str,
    produced_events: set[str],
    timing_risk: bool,
    quarantines: Mapping[str, Mapping[str, str]],
) -> tuple[str, str, str]:
    family = _family(event)
    if family in quarantines:
        return "blocked", "quarantined", quarantines[family]["blocker"]
    if event in produced_events:
        return (
            "produced_clean_story_route",
            "produced_current_manifest_root",
            "",
        )
    if audience_classification in COMPONENT_CLASSIFICATIONS or (
        "audience_component_only" in str(row.get("errors", ""))
    ):
        return (
            "gameplay_effect_collection",
            "planned_unproduced",
            "",
        )
    if timing_risk:
        return (
            "blocked",
            "blocked_timing_evidence",
            "unresolved_parent_dgm_to_child_z2d_instantiation_offset",
        )
    if str(row.get("ready", "")).lower() == "yes":
        return (
            "blocked",
            "evidence_ready_event_waiting_route_product",
            "route_or_family_composition_product_not_yet_built",
        )
    return "blocked", "manifest_not_ready", _errors(row)


def _classify_audience_event(
    *,
    row: Mapping[str, str],
    production: Mapping[str, Mapping[str, Any]],
    produced_events: set[str],
    quarantines: Mapping[str, Mapping[str, str]],
) -> tuple[str, str, str]:
    event = row["event_name"]
    family = _family(event)
    if family in quarantines:
        return "blocked", "quarantined", quarantines[family]["blocker"]
    if event in produced_events:
        return (
            "produced_clean_story_route",
            "produced_current_manifest_root",
            "",
        )
    classification = row.get("classification", "")
    if classification in COMPONENT_CLASSIFICATIONS:
        return "gameplay_effect_collection", "planned_unproduced", ""
    current = production.get(event)
    if current is not None:
        if current["timing_risk"]:
            return (
                "blocked",
                "blocked_timing_evidence",
                "unresolved_parent_dgm_to_child_z2d_instantiation_offset",
            )
        if str(current["catalog"].get("ready", "")).lower() == "yes":
            return (
                "blocked",
                "evidence_ready_event_waiting_route_product",
                "route_or_family_composition_product_not_yet_built",
            )
        return (
            "blocked",
            "manifest_not_ready",
            _errors(current["catalog"]),
        )
    if classification == "native_full_frame_only":
        return (
            "blocked",
            "missing_modern_event_manifest",
            "modern_event_manifest_and_audio_timeline_not_built",
        )
    return (
        "blocked",
        "classification_unresolved",
        "visual_story_gameplay_material_classification_unresolved",
    )


def _source_is_unchanged(snapshot: Mapping[str, str]) -> bool:
    path = Path(snapshot["path"])
    return path.is_file() and file_sha256(path) == snapshot["sha256"]


def _count(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[key]) for row in rows).items()))


def build(
    *,
    plan_path: Path,
    output_root: Path,
) -> Path:
    plan = read_json(plan_path)
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "active_exhaustive_production_ledger"
        or set(plan.get("disposition_categories", [])) != DISPOSITIONS
        or plan.get("priority_policy")
        != "native_416x232_first_then_other_native_sizes_never_upscale"
    ):
        raise ValueError("unsupported exhaustive production-ledger plan")
    plan_dir = plan_path.parent
    snapshots: list[dict[str, str]] = [
        {
            "label": "exhaustive production-ledger plan",
            "path": str(plan_path.resolve()),
            "sha256": file_sha256(plan_path),
        }
    ]
    bound: dict[str, Path] = {}
    for key, label in (
        ("audience_event_catalog", "audience event catalog"),
        ("audience_event_summary", "audience event summary"),
        ("component_mixed_catalog", "component and mixed review catalog"),
        ("production_event_catalog_base", "v20 production event catalog"),
        ("production_event_summary_base", "v20 production event summary"),
        ("production_event_catalog_overlay", "v24 production event overlay"),
        ("production_event_summary_overlay", "v24 production event summary"),
        ("dirinfo_routes", "DirInfo route catalog"),
        ("human_playback_status", "audience human playback status"),
        ("active_upload_exclusions", "active upload exclusions"),
        ("owner_uploaded_exact_zh", "owner uploaded exact ZH attestation"),
        ("owner_approved_corrections", "owner approved correction files"),
        ("owner_reconfirmed_quarantine", "owner reconfirmed quarantine"),
    ):
        path, snapshot = _bound(plan[key], label=label, plan_dir=plan_dir)
        bound[key] = path
        snapshots.append(snapshot)

    quarantines_raw = plan.get("hard_quarantine_families")
    if not isinstance(quarantines_raw, Mapping) or set(quarantines_raw) != {
        "ac6003",
        "ac6004",
        "ac6005",
    }:
        raise ValueError("P16/P17/P18 hard quarantine set differs")
    quarantines = {
        str(family): {
            "part": str(value["part"]),
            "blocker": str(value["blocker"]),
        }
        for family, value in quarantines_raw.items()
        if isinstance(value, Mapping)
    }

    produced_events: set[str] = set()
    produced_rows: set[tuple[int, int]] = set()
    explicitly_excluded_rows: dict[tuple[int, int], dict[str, str]] = {}
    production_manifest_index: list[dict[str, Any]] = []
    superseded_audit_index: list[dict[str, Any]] = []
    roots = plan.get("current_production_roots")
    if not isinstance(roots, list) or len(roots) < 5:
        raise ValueError("current production-root set is incomplete")
    for raw_root in roots:
        if not isinstance(raw_root, Mapping):
            raise ValueError("production root declaration must be an object")
        root = Path(str(raw_root["path"])).resolve()
        glob = str(raw_root["manifest_glob"])
        label = str(raw_root["label"])
        exclusions = raw_root.get("exclude_path_fragments")
        if not isinstance(exclusions, list) or "superseded" not in {
            str(value).casefold() for value in exclusions
        }:
            raise ValueError(
                f"current production root lacks explicit superseded exclusion: {root}"
            )
        if not root.is_dir() or not glob:
            raise ValueError(f"current production root is missing: {root}")
        paths = sorted(path for path in root.glob(glob) if path.is_file())
        if not paths:
            raise ValueError(f"current production root has no manifests: {root}")
        for path in paths:
            if _path_matches_exclusion(
                root=root,
                path=path,
                fragments=[str(value) for value in exclusions],
            ):
                value = read_json(path)
                sha256 = file_sha256(path)
                snapshots.append(
                    {
                        "label": f"{label} superseded audit manifest",
                        "path": str(path.resolve()),
                        "sha256": sha256,
                    }
                )
                superseded_audit_index.append(
                    {
                        "root_label": label,
                        "manifest_path": str(path.resolve()),
                        "manifest_sha256": sha256,
                        "family": str(
                            value.get("family") or value.get("series") or ""
                        ),
                        "events": sorted(_events_from_manifest(value)),
                        "disposition": "superseded_audit_only_never_upload",
                        "included_as_current": False,
                    }
                )
                continue
            value = read_json(path)
            manifest_family = str(
                value.get("family") or value.get("series") or ""
            )
            events = _events_from_manifest(value)
            if manifest_family in quarantines or any(
                _family(event) in quarantines for event in events
            ):
                included = False
                disposition = "quarantine_excluded"
            else:
                included = True
                disposition = "current_produced_manifest"
                produced_events.update(events)
                produced_rows.update(
                    _produced_dirinfo_rows(
                        value,
                        default_kind=_infer_kind(value, path),
                    )
                )
                explicitly_excluded_rows.update(
                    _excluded_dirinfo_rows(
                        value,
                        default_kind=_infer_kind(value, path),
                    )
                )
            sha256 = file_sha256(path)
            snapshots.append(
                {
                    "label": f"{label} manifest",
                    "path": str(path.resolve()),
                    "sha256": sha256,
                }
            )
            production_manifest_index.append(
                {
                    "root_label": label,
                    "manifest_path": str(path.resolve()),
                    "manifest_sha256": sha256,
                    "family": manifest_family,
                    "event_count": len(events),
                    "events": sorted(events),
                    "included_as_produced": included,
                    "disposition": disposition,
                }
            )

    audience_rows = _read_csv(bound["audience_event_catalog"])
    audience_by_event = {row["event_name"]: row for row in audience_rows}
    if len(audience_by_event) != len(audience_rows):
        raise ValueError("audience event catalog contains duplicate events")
    audience_summary = read_json(bound["audience_event_summary"])
    if int(audience_summary.get("events", -1)) != len(audience_rows):
        raise ValueError("audience event summary count differs")

    production_rows: dict[str, dict[str, str]] = {}
    for path in (
        bound["production_event_catalog_base"],
        bound["production_event_catalog_overlay"],
    ):
        for row in _read_csv(path):
            production_rows[row["event_name"]] = row
    production: dict[str, dict[str, Any]] = {}
    for event, catalog_row in production_rows.items():
        manifest_path = Path(catalog_row["manifest_path"]).resolve()
        if not manifest_path.is_file():
            raise ValueError(f"production event manifest is missing: {manifest_path}")
        manifest = read_json(manifest_path)
        if manifest.get("event") != event:
            raise ValueError(f"production event manifest identity differs: {event}")
        sha256 = file_sha256(manifest_path)
        snapshots.append(
            {
                "label": f"current production event manifest {event}",
                "path": str(manifest_path),
                "sha256": sha256,
            }
        )
        production[event] = {
            "catalog": catalog_row,
            "manifest_path": str(manifest_path),
            "manifest_sha256": sha256,
            "timing_risk": _child_local_timing_risk(manifest),
        }

    production_ledger: list[dict[str, Any]] = []
    for event in sorted(production):
        current = production[event]
        audience_class = audience_by_event.get(event, {}).get("classification", "")
        disposition, state, blocker = _classify_production_event(
            event=event,
            row=current["catalog"],
            audience_classification=audience_class,
            produced_events=produced_events,
            timing_risk=bool(current["timing_risk"]),
            quarantines=quarantines,
        )
        production_ledger.append(
            {
                "event_name": event,
                "family": _family(event),
                "native_dimensions": (
                    f"{current['catalog'].get('width', '')}x"
                    f"{current['catalog'].get('height', '')}"
                ),
                "ready_in_current_manifest": current["catalog"].get("ready", ""),
                "child_local_timing_risk": str(bool(current["timing_risk"])).lower(),
                "disposition": disposition,
                "production_state": state,
                "blocker": blocker,
                "manifest_path": current["manifest_path"],
                "manifest_sha256": current["manifest_sha256"],
            }
        )

    audience_ledger: list[dict[str, Any]] = []
    for raw in audience_rows:
        disposition, state, blocker = _classify_audience_event(
            row=raw,
            production=production,
            produced_events=produced_events,
            quarantines=quarantines,
        )
        audience_ledger.append(
            {
                **raw,
                "family": _family(raw["event_name"]),
                "disposition": disposition,
                "production_state": state,
                "blocker": blocker,
            }
        )

    component_rows = _read_csv(bound["component_mixed_catalog"])
    component_ledger: list[dict[str, Any]] = []
    for raw in component_rows:
        event = raw["event_name"]
        family = _family(event)
        if family in quarantines:
            disposition = "blocked"
            state = "quarantined"
            blocker = quarantines[family]["blocker"]
        elif raw.get("classification") in COMPONENT_CLASSIFICATIONS:
            disposition = "gameplay_effect_collection"
            state = (
                "source_event_also_present_in_current_story_product"
                if event in produced_events
                else "planned_unproduced"
            )
            blocker = ""
        elif raw.get("classification") == "unresolved":
            disposition = "blocked"
            state = "classification_unresolved"
            blocker = "visual_story_gameplay_material_classification_unresolved"
        else:
            disposition = "blocked"
            state = "catalog_reconciliation_required"
            blocker = "component_review_catalog_contains_native_full_frame_event"
        component_ledger.append(
            {
                **raw,
                "family": family,
                "disposition": disposition,
                "production_state": state,
                "blocker": blocker,
            }
        )

    dirinfo_groups: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for raw in _read_csv(bound["dirinfo_routes"]):
        dirinfo_groups[(int(raw["kind"]), int(raw["row_index"]))].append(raw)
    dirinfo_ledger: list[dict[str, Any]] = []
    for (kind, row), values in sorted(dirinfo_groups.items()):
        values.sort(key=lambda value: int(value["selector_raw"]))
        events = [value["scene_name"] for value in values if value["scene_name"]]
        families = sorted({_family(event) for event in events})
        quarantined = next(
            (family for family in families if family in quarantines),
            None,
        )
        if quarantined is not None:
            disposition = "blocked"
            state = "quarantined"
            blocker = quarantines[quarantined]["blocker"]
        elif (kind, row) in explicitly_excluded_rows:
            explicit = explicitly_excluded_rows[(kind, row)]
            disposition = explicit["disposition"]
            state = explicit["production_state"]
            blocker = explicit["blocker"]
        elif (kind, row) in produced_rows:
            disposition = "produced_clean_story_route"
            state = "produced_current_manifest_root"
            blocker = ""
        elif any(
            audience_by_event.get(event, {}).get("classification")
            in COMPONENT_CLASSIFICATIONS
            for event in events
        ):
            disposition = "gameplay_effect_collection"
            state = "route_requires_clean_story_effect_layer_split"
            blocker = ""
        else:
            disposition = "blocked"
            state = "route_not_yet_produced"
            blocker = "route_event_manifest_composition_or_timing_not_closed"
        dirinfo_ledger.append(
            {
                "kind": kind,
                "row_index": row,
                "base_names": "|".join(
                    sorted({value["base_name"] for value in values if value["base_name"]})
                ),
                "ordered_events": "|".join(events),
                "selector_count": len(values),
                "route_statuses": "|".join(
                    sorted({value["route_status"] for value in values})
                ),
                "disposition": disposition,
                "production_state": state,
                "blocker": blocker,
            }
        )

    playback = read_json(bound["human_playback_status"])
    exclusions = read_json(bound["active_upload_exclusions"])
    uploaded = read_json(bound["owner_uploaded_exact_zh"])
    corrections = read_json(bound["owner_approved_corrections"])
    quarantine_attestation = read_json(bound["owner_reconfirmed_quarantine"])
    if (
        playback.get("schema") != "magireco-audience-human-playback-status-v1"
        or exclusions.get("status") != "active_fail_closed"
        or uploaded.get("status") != "uploaded_by_project_owner"
        or corrections.get("status") != "project_owner_playback_approved"
        or quarantine_attestation.get("status") != "quarantine_reconfirmed"
    ):
        raise ValueError("audience product status source identity differs")
    product_ledger = {
        "schema": "magireco-audience-product-production-ledger-v1",
        "uploaded_exact_zh": uploaded,
        "approved_exact_corrections_and_ac0908": corrections,
        "active_upload_exclusions": exclusions,
        "human_playback_failed_products": playback.get("failed_products", []),
        "hard_quarantine_families": quarantines,
        "historical_scope_gap": plan.get("historical_scope_gap"),
        "current_route_products_requiring_exact_file_playback": [
            {
                "root_label": row["root_label"],
                "manifest_path": row["manifest_path"],
                "family": row["family"],
            }
            for row in production_manifest_index
            if row["included_as_produced"]
            and row["root_label"].startswith(("v30", "v31", "v32", "v33"))
        ],
        "superseded_audit_only_never_upload": superseded_audit_index,
    }

    if any(row["disposition"] not in DISPOSITIONS for row in audience_ledger):
        raise RuntimeError("audience event lacks a final disposition")
    if any(row["disposition"] not in DISPOSITIONS for row in dirinfo_ledger):
        raise RuntimeError("DirInfo route lacks a final disposition")
    if any(row["disposition"] not in DISPOSITIONS for row in production_ledger):
        raise RuntimeError("production event lacks a final disposition")
    if any(row["disposition"] not in DISPOSITIONS for row in component_ledger):
        raise RuntimeError("component/mixed event lacks a final disposition")

    unique_snapshots: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    for snapshot in snapshots:
        key = str(Path(snapshot["path"]).resolve()).casefold()
        existing = seen.get(key)
        if existing is not None and existing != snapshot["sha256"]:
            raise ValueError(f"conflicting source snapshot: {snapshot['path']}")
        if existing is None:
            seen[key] = snapshot["sha256"]
            unique_snapshots.append(snapshot)
    if not all(_source_is_unchanged(snapshot) for snapshot in unique_snapshots):
        raise RuntimeError("one or more ledger inputs changed during the audit")

    destination = output_root.resolve()
    if destination.exists():
        raise FileExistsError(f"versioned exhaustive ledger root exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        _write_csv(
            staging / "AUDIENCE_EVENT_LEDGER.csv",
            audience_ledger,
            fieldnames=[
                *audience_rows[0].keys(),
                "family",
                "disposition",
                "production_state",
                "blocker",
            ],
        )
        _write_csv(
            staging / "PRODUCTION_EVENT_LEDGER.csv",
            production_ledger,
            fieldnames=list(production_ledger[0]),
        )
        _write_csv(
            staging / "COMPONENT_MIXED_LEDGER.csv",
            component_ledger,
            fieldnames=[
                *component_rows[0].keys(),
                "family",
                "disposition",
                "production_state",
                "blocker",
            ],
        )
        _write_csv(
            staging / "DIRINFO_ROUTE_LEDGER.csv",
            dirinfo_ledger,
            fieldnames=list(dirinfo_ledger[0]),
        )
        write_json(staging / "AUDIENCE_PRODUCT_LEDGER.json", product_ledger)
        write_json(
            staging / "CURRENT_PRODUCTION_MANIFEST_INDEX.json",
            {
                "schema": "magireco-current-production-manifest-index-v1",
                "manifests": production_manifest_index,
                "produced_event_count": len(produced_events),
                "produced_dirinfo_route_count": len(produced_rows),
            },
        )
        write_json(
            staging / "SUPERSEDED_AUDIT_INDEX.json",
            {
                "schema": "magireco-superseded-audit-index-v1",
                "scope": "preserved for provenance only; excluded from current production and upload",
                "manifests": superseded_audit_index,
            },
        )
        write_json(
            staging / "SOURCE_SNAPSHOTS.json",
            {
                "schema": "magireco-exhaustive-ledger-source-snapshots-v1",
                "sources": unique_snapshots,
            },
        )
        summary = {
            "schema": SUMMARY_SCHEMA,
            "status": "ACTIVE_EXHAUSTIVE_LEDGER_BUILT",
            "recorded_date": plan.get("recorded_date"),
            "mother_sets": {
                "audience_events": len(audience_ledger),
                "production_manifest_events": len(production_ledger),
                "dirinfo_routes": len(dirinfo_ledger),
                "component_or_mixed_events": len(component_ledger),
                "current_production_manifests": len(production_manifest_index),
                "superseded_audit_manifests_excluded": len(
                    superseded_audit_index
                ),
            },
            "audience_event_dispositions": _count(audience_ledger, "disposition"),
            "audience_event_states": _count(audience_ledger, "production_state"),
            "production_event_dispositions": _count(
                production_ledger, "disposition"
            ),
            "production_event_states": _count(
                production_ledger, "production_state"
            ),
            "dirinfo_route_dispositions": _count(dirinfo_ledger, "disposition"),
            "dirinfo_route_states": _count(dirinfo_ledger, "production_state"),
            "component_mixed_dispositions": _count(
                component_ledger, "disposition"
            ),
            "produced_event_count": len(produced_events),
            "produced_dirinfo_route_count": len(produced_rows),
            "hard_quarantine_families": quarantines,
            "priority_policy": plan.get("priority_policy"),
            "directory_policy": (
                "Only plan-listed current roots were scanned; historical render roots "
                "were not mixed into current production inputs."
            ),
        }
        write_json(staging / "SUMMARY.json", summary)
        (staging / "README.md").write_text(
            "# MagiaReco 穷尽式视频生产总账 v1\n\n"
            "本总账覆盖当前哈希绑定的 audience event、production event、DirInfo "
            "route 与 component/mixed 四个母集。P16/ac6003、P17/ac6004、"
            "P18/ac6005 始终为硬隔离；它们不会因其他批次 QA 通过而重新进入投稿。\n\n"
            "所有候选均有 disposition、production_state 与 blocker。"
            "gameplay/effect 项只表示已分流到独立合集，不表示合集已经完成；"
            "produced 只来自计划列出的当前 manifest 根。\n",
            encoding="utf-8",
        )
        hashed = [
            {
                "path": path.relative_to(staging).as_posix(),
                "sha256": file_sha256(path),
                "byte_count": path.stat().st_size,
            }
            for path in sorted(staging.iterdir())
            if path.is_file()
        ]
        write_json(
            staging / "SHA256SUMS.json",
            {
                "schema": "magireco-versioned-output-sha256-v1",
                "files": hashed,
            },
        )
        staging.replace(destination)
        return destination
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    destination = build(
        plan_path=args.plan.resolve(),
        output_root=args.output_root.resolve(),
    )
    summary = read_json(destination / "SUMMARY.json")
    print(
        json.dumps(
            {
                "destination": str(destination),
                "status": summary["status"],
                "mother_sets": summary["mother_sets"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
