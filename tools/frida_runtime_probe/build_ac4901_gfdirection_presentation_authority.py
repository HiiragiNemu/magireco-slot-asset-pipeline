#!/usr/bin/env python3
"""Build complete event-global GFDirection presentation authority for ac4901."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Sequence

try:
    from .build_ac0915_gfdirection_presentation_authority import (
        PresentationAuthorityError,
        _flatten_rows,
        _write_rollback,
        build_authority as _build_core,
    )
    from .build_ac4901_parent_z2d_authority import EXPECTED_EVENT_IDS
except ImportError:  # pragma: no cover - direct script execution
    from build_ac0915_gfdirection_presentation_authority import (  # type: ignore
        PresentationAuthorityError,
        _flatten_rows,
        _write_rollback,
        build_authority as _build_core,
    )
    from build_ac4901_parent_z2d_authority import EXPECTED_EVENT_IDS  # type: ignore


EVENT_IDS = EXPECTED_EVENT_IDS
EXPECTED_COUNTS = {
    "event_count": 205,
    "scene_instance_count": 320,
    "cut_count": 320,
    "z2d_node_occurrence_count": 468,
    "unique_z2d_node_count": 108,
    "archive_backed_z2d_occurrence_count": 463,
    "unique_archive_backed_z2d_count": 103,
    "runtime_symbolic_z2d_occurrence_count": 5,
    "unique_runtime_symbolic_z2d_count": 5,
}
EXPECTED_PARALLEL_EVENT_COUNT = 115
EXPECTED_GROUP_NAME = "ac4901"
EXPECTED_GROUP_INDEX = 112


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PresentationAuthorityError(f"JSON root must be an object: {path}")
    return value


def derive_expected_event_frames(
    scene_group_path: Path, runtime_scene_path: Path
) -> dict[str, int]:
    """Derive event extents from every static Type-2 scene named by runtime."""

    scene_report = _load_json(scene_group_path)
    runtime_report = _load_json(runtime_scene_path)
    group = scene_report.get("group", {})
    if group.get("name") != EXPECTED_GROUP_NAME:
        raise PresentationAuthorityError("ac4901 scene group name differs")
    if group.get("compiled_index") != EXPECTED_GROUP_INDEX:
        raise PresentationAuthorityError("ac4901 scene group index differs")

    type2_rows = group.get("type2_presentations", [])
    type2_by_name: dict[str, dict[str, Any]] = {}
    for row in type2_rows:
        name = str(row.get("name", ""))
        if not name or name in type2_by_name:
            raise PresentationAuthorityError(
                f"missing or duplicate Type-2 presentation name: {name!r}"
            )
        type2_by_name[name] = row
    primary_type2_names = {name for name in type2_by_name if name.startswith("ac4901_")}
    if primary_type2_names != set(EVENT_IDS):
        raise PresentationAuthorityError("ac4901 primary Type-2 event set differs")

    runtime_events = runtime_report.get("events")
    if not isinstance(runtime_events, dict) or set(runtime_events) != set(EVENT_IDS):
        raise PresentationAuthorityError("ac4901 runtime event set differs")
    frames: dict[str, int] = {}
    for event_id in EVENT_IDS:
        scene_names = [
            str(scene.get("name", ""))
            for scene in runtime_events[event_id].get("scenes", [])
        ]
        if not scene_names:
            raise PresentationAuthorityError(f"{event_id} has no runtime scenes")
        missing = [name for name in scene_names if name not in type2_by_name]
        if missing:
            raise PresentationAuthorityError(
                f"{event_id} runtime scene lacks Type-2 record: {missing}"
            )
        frame_counts = [
            int(type2_by_name[name].get("presentation_frame_count", 0))
            for name in scene_names
        ]
        if any(frame_count <= 0 for frame_count in frame_counts):
            raise PresentationAuthorityError(
                f"{event_id} has a non-positive Type-2 presentation extent"
            )
        frames[event_id] = max(frame_counts)
    return frames


def build_ac4901_authority(
    *,
    scene_group_path: Path,
    gdp_path: Path,
    runtime_scene_path: Path,
    type3_records_dir: Path,
    parent_z2d_authority_path: Path,
) -> dict[str, Any]:
    expected_frames = derive_expected_event_frames(
        scene_group_path, runtime_scene_path
    )
    authority = _build_core(
        scene_group_path=scene_group_path,
        gdp_path=gdp_path,
        runtime_scene_path=runtime_scene_path,
        type3_records_dir=type3_records_dir,
        parent_z2d_authority_path=parent_z2d_authority_path,
        expected_event_ids=EVENT_IDS,
        expected_event_frames=expected_frames,
        expected_counts=EXPECTED_COUNTS,
        expected_group_name=EXPECTED_GROUP_NAME,
        expected_group_index=EXPECTED_GROUP_INDEX,
    )
    event_presentations = authority["summary"]["event_presentations"]
    scene_multiplicity = {
        event_id: len(row["parallel_scenes"])
        for event_id, row in event_presentations.items()
    }
    unexpected = {
        event_id: count
        for event_id, count in scene_multiplicity.items()
        if count not in (1, 2)
    }
    if unexpected:
        raise PresentationAuthorityError(
            f"ac4901 scene multiplicity differs: {unexpected}"
        )
    parallel_event_count = sum(count == 2 for count in scene_multiplicity.values())
    if parallel_event_count != EXPECTED_PARALLEL_EVENT_COUNT:
        raise PresentationAuthorityError(
            "ac4901 parallel event count differs: "
            f"expected={EXPECTED_PARALLEL_EVENT_COUNT} actual={parallel_event_count}"
        )

    authority["schema"] = "magireco-ac4901-gfdirection-presentation-authority-v1"
    authority["summary"]["parallel_event_count"] = parallel_event_count
    authority["summary"]["single_scene_event_count"] = (
        len(EVENT_IDS) - parallel_event_count
    )
    authority["summary"]["event_frame_sum"] = sum(expected_frames.values())
    authority["assertions"] = {
        "all_205_dirinfo_events_are_present": True,
        "all_320_runtime_scenes_bind_exact_type2_presentations": True,
        "all_320_runtime_cuts_match_type2_scene_references": True,
        "all_320_runtime_cuts_bind_exact_type3_records": True,
        "all_event_extents_equal_static_parallel_type2_maximum": True,
        "one_hundred_fifteen_secondary_presentations_start_at_event_frame_zero": True,
        "all_468_type20_nodes_partition_into_archive_or_symbolic": True,
        "five_symbolic_counter_nodes_are_not_missing_media": True,
        "machine_vision_used_as_authority": False,
        "source_media_untouched": True,
        "final_416x232_projection_resolved": False,
        "production_disposition": (
            "FAIL_CLOSED_UNTIL_FINAL_OUTPUT_PROJECTION_IS_CODE_BOUND"
        ),
    }
    return authority


def write_outputs(authority: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise PresentationAuthorityError(
            f"immutable output already exists: {output_dir}"
        )
    stage = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
    if stage.exists():
        raise PresentationAuthorityError(f"staging output already exists: {stage}")
    stage.mkdir(parents=True)
    try:
        authority_path = stage / "AC4901_GFDIRECTION_PRESENTATION_AUTHORITY.json"
        csv_path = stage / "PRESENTATION_Z2D_NODES.csv"
        verification_path = stage / "VERIFICATION_RECORD.json"
        readme_path = stage / "README.md"
        rollback_path = stage / "ROLLBACK.ps1"
        authority_path.write_text(
            json.dumps(authority, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rows = _flatten_rows(authority)
        if not rows:
            raise PresentationAuthorityError("ac4901 authority has no node rows")
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        _write_rollback(rollback_path, output_dir)
        readme_path.write_text(
            "# ac4901 GFDirection event-global presentation authority\n\n"
            "This immutable checkpoint binds all 205 DirInfo events, 320 scene "
            "instances, 320 exact Type-3 cuts, and 468 Type-20 node occurrences. "
            "The 115 utility/effect scenes are parallel event layers, not serial "
            "story fragments. Final native 416x232 projection remains fail-closed.\n",
            encoding="utf-8",
        )
        verification = {
            "schema": "magireco-ac4901-gfdirection-presentation-verification-v1",
            "status": "passed",
            "literal_result": (
                f"PASS events={authority['summary']['event_count']} "
                f"scenes={authority['summary']['scene_instance_count']} "
                f"cuts={authority['summary']['cut_count']} "
                f"z2d_occurrences={authority['summary']['z2d_node_occurrence_count']} "
                f"archive_occurrences={authority['summary']['archive_backed_z2d_occurrence_count']} "
                f"symbolic_occurrences={authority['summary']['runtime_symbolic_z2d_occurrence_count']} "
                f"parallel_events={authority['summary']['parallel_event_count']} "
                "projection=FAIL_CLOSED_PENDING"
            ),
            "output_byte_counts": {
                path.name: path.stat().st_size
                for path in (authority_path, csv_path, readme_path, rollback_path)
            },
            "checks": authority["assertions"],
        }
        verification_path.write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stage.rename(output_dir)
    except Exception:
        if stage.exists():
            (stage / "FAILED_DO_NOT_USE.txt").write_text(
                "The staged authority is incomplete and must not be used.\n",
                encoding="utf-8",
            )
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-group", required=True, type=Path)
    parser.add_argument("--gdp", required=True, type=Path)
    parser.add_argument("--runtime-scene", required=True, type=Path)
    parser.add_argument("--type3-records-dir", required=True, type=Path)
    parser.add_argument("--parent-z2d-authority", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    authority = build_ac4901_authority(
        scene_group_path=args.scene_group,
        gdp_path=args.gdp,
        runtime_scene_path=args.runtime_scene,
        type3_records_dir=args.type3_records_dir,
        parent_z2d_authority_path=args.parent_z2d_authority,
    )
    write_outputs(authority, args.output_dir)
    print(
        f"PASS events={authority['summary']['event_count']} "
        f"scenes={authority['summary']['scene_instance_count']} "
        f"cuts={authority['summary']['cut_count']} "
        f"z2d_occurrences={authority['summary']['z2d_node_occurrence_count']} "
        f"parallel_events={authority['summary']['parallel_event_count']} "
        "projection=FAIL_CLOSED_PENDING"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
