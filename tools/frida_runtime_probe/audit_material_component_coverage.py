#!/usr/bin/env python3
"""Audit split native-size material catalogs against exact event manifests.

Some gameplay/effect events contain layers at more than one native resolution.
They must not be linearly concatenated or resized merely to make one video.
This auditor proves that every source clip in a hash-bound family inventory is
present in one of the declared native-size catalogs while keeping those
catalogs as separate review products.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac0908_reference_showcase import read_json, validate_bound_file
    from .build_independent_scene_release import file_sha256, write_json
except ImportError:  # direct script execution
    from build_ac0908_reference_showcase import (  # type: ignore
        read_json,
        validate_bound_file,
    )
    from build_independent_scene_release import file_sha256, write_json  # type: ignore


PLAN_SCHEMA = "magireco-material-component-coverage-plan-v1"
RESULT_SCHEMA = "magireco-material-component-coverage-audit-v1"
EVENT_PATTERN = re.compile(r"^ac\d+(?:_\d+)+$")


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


def _source_index(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    expected_dimensions: tuple[int, int],
) -> dict[str, dict[str, Any]]:
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"component catalog has no sources: {manifest_path}")
    result: dict[str, dict[str, Any]] = {}
    for raw in sources:
        if not isinstance(raw, Mapping):
            raise ValueError(f"component catalog source is not an object: {manifest_path}")
        name = str(raw.get("official_name", ""))
        path = Path(str(raw.get("path", ""))).resolve()
        sha256 = str(raw.get("source_sha256", "")).upper()
        signature = raw.get("source_video_signature")
        if (
            not name
            or name in result
            or not path.is_file()
            or not re.fullmatch(r"[0-9A-F]{64}", sha256)
            or file_sha256(path) != sha256
            or not isinstance(signature, Mapping)
            or (
                int(signature.get("width", 0)),
                int(signature.get("height", 0)),
            )
            != expected_dimensions
        ):
            raise ValueError(
                f"component catalog source identity differs: {manifest_path} {name}"
            )
        result[name] = dict(raw)
    return result


def audit(
    *,
    plan_path: Path,
    output_path: Path,
) -> Path:
    plan = read_json(plan_path)
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "active_fail_closed"
        or plan.get("composition_policy")
        != "separate_native_size_catalogs_never_concat_or_upscale"
    ):
        raise ValueError("unsupported material component coverage plan")
    plan_dir = plan_path.parent
    ledger_path, ledger_snapshot = _bound(
        plan.get("event_ledger", {}),
        label="component coverage event ledger",
        plan_dir=plan_dir,
    )
    family = str(plan.get("family", ""))
    expected_state = str(plan.get("expected_production_state", ""))
    expected_disposition = str(plan.get("expected_disposition", ""))
    expected_count = int(plan.get("expected_event_count", 0))
    rows = [
        row
        for row in _read_csv(ledger_path)
        if row.get("family") == family
        and row.get("production_state") == expected_state
        and row.get("disposition") == expected_disposition
    ]
    if (
        not family
        or len(rows) != expected_count
        or len({row.get("event_name") for row in rows}) != len(rows)
        or any(
            not EVENT_PATTERN.fullmatch(str(row.get("event_name", "")))
            for row in rows
        )
    ):
        raise ValueError("component coverage ledger event set differs")

    catalog_declarations = plan.get("component_catalogs")
    if not isinstance(catalog_declarations, list) or len(catalog_declarations) < 2:
        raise ValueError("component coverage plan lacks split catalogs")
    catalog_by_name: dict[str, dict[str, Any]] = {}
    source_owner: dict[str, str] = {}
    snapshots = [
        {
            "label": "material component coverage plan",
            "path": str(plan_path.resolve()),
            "sha256": file_sha256(plan_path),
        },
        ledger_snapshot,
    ]
    for raw in catalog_declarations:
        if not isinstance(raw, Mapping):
            raise ValueError("component catalog declaration is not an object")
        name = str(raw.get("name", ""))
        role = str(raw.get("role", ""))
        dimensions_raw = raw.get("native_dimensions")
        if (
            not name
            or name in catalog_by_name
            or role not in {"event_components", "shared_components"}
            or not isinstance(dimensions_raw, Mapping)
        ):
            raise ValueError("component catalog declaration differs")
        dimensions = (
            int(dimensions_raw.get("width", 0)),
            int(dimensions_raw.get("height", 0)),
        )
        manifest_path, manifest_snapshot = _bound(
            raw.get("manifest", {}),
            label=f"{name} component catalog manifest",
            plan_dir=plan_dir,
        )
        manifest = read_json(manifest_path)
        output = Path(str(manifest.get("output", ""))).resolve()
        output_sha256 = str(manifest.get("output_sha256", "")).upper()
        if (
            manifest.get("technical_qa_status") != "passed"
            or not output.is_file()
            or file_sha256(output) != output_sha256
        ):
            raise ValueError(f"component catalog QA/output differs: {manifest_path}")
        sources = _source_index(
            manifest=manifest,
            manifest_path=manifest_path,
            expected_dimensions=dimensions,
        )
        for source_name in sources:
            if source_name in source_owner:
                raise ValueError(
                    f"component source appears in multiple native catalogs: {source_name}"
                )
            source_owner[source_name] = name
        catalog_by_name[name] = {
            "name": name,
            "role": role,
            "native_dimensions": {
                "width": dimensions[0],
                "height": dimensions[1],
            },
            "manifest_path": str(manifest_path),
            "manifest_sha256": manifest_snapshot["sha256"],
            "output_path": str(output),
            "output_sha256": output_sha256,
            "sources": sources,
            "component_events": {
                str(value) for value in manifest.get("component_events", [])
            },
            "component_event_clip_map": manifest.get(
                "component_event_clip_map", {}
            ),
            "allowed_unused_sources": {
                str(value) for value in raw.get("allowed_unused_sources", [])
            },
        }
        snapshots.extend(
            [
                manifest_snapshot,
                {
                    "label": f"{name} component catalog output",
                    "path": str(output),
                    "sha256": output_sha256,
                },
            ]
        )

    event_component_catalogs = [
        value
        for value in catalog_by_name.values()
        if value["role"] == "event_components"
    ]
    if len(event_component_catalogs) != 1:
        raise ValueError("exactly one event-components catalog is required")
    event_catalog = event_component_catalogs[0]
    event_map_raw = event_catalog["component_event_clip_map"]
    if not isinstance(event_map_raw, Mapping):
        raise ValueError("event-components catalog lacks component event map")

    used_by_catalog: dict[str, set[str]] = {
        name: set() for name in catalog_by_name
    }
    event_rows: list[dict[str, Any]] = []
    event_names_with_local_components: set[str] = set()
    for row in sorted(rows, key=lambda value: str(value["event_name"])):
        event = str(row["event_name"])
        manifest_path = Path(str(row.get("manifest_path", ""))).resolve()
        manifest_sha256 = str(row.get("manifest_sha256", "")).upper()
        if (
            not manifest_path.is_file()
            or file_sha256(manifest_path) != manifest_sha256
        ):
            raise ValueError(f"event manifest snapshot differs: {event}")
        manifest = read_json(manifest_path)
        if manifest.get("event") != event:
            raise ValueError(f"event manifest identity differs: {event}")
        clips = manifest.get("clips")
        if not isinstance(clips, list) or not clips:
            raise ValueError(f"event has no component clips: {event}")
        per_catalog: dict[str, list[str]] = {
            name: [] for name in catalog_by_name
        }
        for clip in clips:
            if not isinstance(clip, Mapping):
                raise ValueError(f"event clip is not an object: {event}")
            source_name = str(clip.get("dgm_name", ""))
            catalog_name = source_owner.get(source_name)
            if catalog_name is None:
                raise ValueError(
                    f"event clip is absent from split catalogs: {event} {source_name}"
                )
            source = catalog_by_name[catalog_name]["sources"][source_name]
            clip_path = Path(str(clip.get("path", ""))).resolve()
            if (
                clip_path != Path(str(source["path"])).resolve()
                or file_sha256(clip_path)
                != str(source["source_sha256"]).upper()
            ):
                raise ValueError(
                    f"event clip source differs from catalog: {event} {source_name}"
                )
            per_catalog[catalog_name].append(source_name)
            used_by_catalog[catalog_name].add(source_name)
        local_names = per_catalog[event_catalog["name"]]
        mapped_raw = event_map_raw.get(event, [])
        if not isinstance(mapped_raw, list):
            raise ValueError(f"component event map row differs: {event}")
        mapped_names = [str(value) for value in mapped_raw]
        if set(mapped_names) != set(local_names) or len(mapped_names) != len(
            set(mapped_names)
        ):
            raise ValueError(f"component event map is incomplete: {event}")
        if local_names:
            event_names_with_local_components.add(event)
        event_rows.append(
            {
                "event": event,
                "event_manifest_path": str(manifest_path),
                "event_manifest_sha256": manifest_sha256,
                "catalog_sources": {
                    name: names
                    for name, names in per_catalog.items()
                    if names
                },
            }
        )
        snapshots.append(
            {
                "label": f"{event} production manifest",
                "path": str(manifest_path),
                "sha256": manifest_sha256,
            }
        )

    if event_catalog["component_events"] != event_names_with_local_components:
        raise ValueError("event-components catalog event set differs")
    catalog_results = []
    for name, catalog in catalog_by_name.items():
        all_sources = set(catalog["sources"])
        unused = all_sources - used_by_catalog[name]
        if unused != catalog["allowed_unused_sources"]:
            raise ValueError(f"component catalog unused source set differs: {name}")
        catalog_results.append(
            {
                key: catalog[key]
                for key in (
                    "name",
                    "role",
                    "native_dimensions",
                    "manifest_path",
                    "manifest_sha256",
                    "output_path",
                    "output_sha256",
                )
            }
            | {
                "source_count": len(all_sources),
                "used_source_count": len(used_by_catalog[name]),
                "unused_source_names": sorted(unused),
            }
        )

    unique_snapshots: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    for snapshot in snapshots:
        key = str(Path(snapshot["path"]).resolve()).casefold()
        previous = seen.get(key)
        if previous is not None and previous != snapshot["sha256"]:
            raise ValueError(f"conflicting component snapshot: {snapshot['path']}")
        if previous is None:
            seen[key] = snapshot["sha256"]
            unique_snapshots.append(snapshot)
    if any(
        not Path(snapshot["path"]).is_file()
        or file_sha256(Path(snapshot["path"])) != snapshot["sha256"]
        for snapshot in unique_snapshots
    ):
        raise RuntimeError("component coverage input changed during audit")

    result = {
        "schema": RESULT_SCHEMA,
        "status": "PASSED",
        "coverage_id": str(plan.get("coverage_id", "")),
        "family": family,
        "composition_policy": plan["composition_policy"],
        "coverage_claim": (
            "Every hash-bound event clip is present in the declared native-size "
            "component catalogs. This is visual component coverage only; the "
            "catalogs remain separate review products and are not a reconstructed "
            "natural event timeline."
        ),
        "covered_events": sorted(row["event"] for row in event_rows),
        "covered_event_count": len(event_rows),
        "component_catalogs": catalog_results,
        "events": event_rows,
        "source_snapshots": unique_snapshots,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"versioned component audit exists: {output_path}")
    write_json(output_path, result)
    return output_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = audit(plan_path=args.plan, output_path=args.output)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
