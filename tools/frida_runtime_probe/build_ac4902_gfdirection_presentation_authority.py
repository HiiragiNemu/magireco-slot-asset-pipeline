#!/usr/bin/env python3
"""Build the exact event-global GFDirection presentation authority for ac4902.

The shared parser/validator lives in the ac0915 authority builder because both
families use the same Slot binary/GDB/GDP/runtime contract.  This wrapper binds
that generic core to ac4902's independently extracted 64-event scene group,
including 33 events with a second Type-2 presentation that starts in parallel
at event-global frame zero.

This checkpoint deliberately stops before output projection.  It establishes
which Z2D nodes exist, their exact Type-3 cut offsets, their owning GDP layers,
and the event extent.  A later authority must still bind every movie layer to
the native 416x232 output before media production can be marked ready.
"""

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
    from .extract_jm_dgi_glyph_catalog import sha256_bytes
except ImportError:  # pragma: no cover - direct script execution
    from build_ac0915_gfdirection_presentation_authority import (  # type: ignore
        PresentationAuthorityError,
        _flatten_rows,
        _write_rollback,
        build_authority as _build_core,
    )
    from extract_jm_dgi_glyph_catalog import sha256_bytes  # type: ignore


EXPECTED_EVENT_FRAMES = {
    "ac4902_001": 120,
    "ac4902_002": 321,
    "ac4902_003": 163,
    "ac4902_004": 181,
    "ac4902_005": 603,
    "ac4902_006": 360,
    "ac4902_007": 360,
    "ac4902_008": 1090,
    "ac4902_009": 1200,
    "ac4902_010": 317,
    "ac4902_011": 317,
    "ac4902_012": 1090,
    "ac4902_013": 1050,
    "ac4902_014": 159,
    "ac4902_015": 90,
    "ac4902_016": 136,
    "ac4902_017": 189,
    "ac4902_018": 300,
    "ac4902_019": 300,
    "ac4902_020": 181,
    "ac4902_021": 181,
    "ac4902_022": 240,
    "ac4902_023": 84,
    "ac4902_024": 498,
    "ac4902_025": 299,
    "ac4902_026": 181,
    "ac4902_027": 84,
    "ac4902_028": 280,
    "ac4902_029": 136,
    "ac4902_030": 1090,
    "ac4902_031": 84,
    "ac4902_032": 300,
    "ac4902_033": 1200,
    "ac4902_034": 84,
    "ac4902_035": 299,
    "ac4902_036": 1090,
    "ac4902_037": 84,
    "ac4902_038": 299,
    "ac4902_039": 1050,
    "ac4902_040": 136,
    "ac4902_041": 136,
    "ac4902_042": 300,
    "ac4902_043": 300,
    "ac4902_054": 120,
    "ac4902_055": 321,
    "ac4902_056": 603,
    "ac4902_057": 159,
    "ac4902_058": 189,
    "ac4902_059": 163,
    "ac4902_060": 181,
    "ac4902_061": 181,
    "ac4902_062": 360,
    "ac4902_063": 360,
    "ac4902_064": 1090,
    "ac4902_065": 1200,
    "ac4902_066": 317,
    "ac4902_067": 317,
    "ac4902_068": 1090,
    "ac4902_069": 1050,
    "ac4902_070": 90,
    "ac4902_071": 136,
    "ac4902_072": 136,
    "ac4902_073": 300,
    "ac4902_074": 300,
}
EVENT_IDS = tuple(EXPECTED_EVENT_FRAMES)
EXPECTED_COUNTS = {
    "event_count": 64,
    "scene_instance_count": 97,
    "cut_count": 97,
    "z2d_node_occurrence_count": 164,
    "unique_z2d_node_count": 55,
    "archive_backed_z2d_occurrence_count": 159,
    "unique_archive_backed_z2d_count": 50,
    "runtime_symbolic_z2d_occurrence_count": 5,
    "unique_runtime_symbolic_z2d_count": 5,
}
EXPECTED_PARALLEL_EVENT_COUNT = 33
EXPECTED_GROUP_NAME = "ac4902"
EXPECTED_GROUP_INDEX = 113


def build_ac4902_authority(
    *,
    scene_group_path: Path,
    gdp_path: Path,
    runtime_scene_path: Path,
    type3_records_dir: Path,
    parent_z2d_authority_path: Path,
) -> dict[str, Any]:
    """Bind the generic presentation core to the exact ac4902 contract."""

    authority = _build_core(
        scene_group_path=scene_group_path,
        gdp_path=gdp_path,
        runtime_scene_path=runtime_scene_path,
        type3_records_dir=type3_records_dir,
        parent_z2d_authority_path=parent_z2d_authority_path,
        expected_event_ids=EVENT_IDS,
        expected_event_frames=EXPECTED_EVENT_FRAMES,
        expected_counts=EXPECTED_COUNTS,
        expected_group_name=EXPECTED_GROUP_NAME,
        expected_group_index=EXPECTED_GROUP_INDEX,
    )
    event_presentations = authority["summary"]["event_presentations"]
    parallel_event_count = sum(
        len(row["parallel_scenes"]) == 2 for row in event_presentations.values()
    )
    unexpected_parallel_counts = {
        event_id: len(row["parallel_scenes"])
        for event_id, row in event_presentations.items()
        if len(row["parallel_scenes"]) not in (1, 2)
    }
    if unexpected_parallel_counts:
        raise PresentationAuthorityError(
            f"ac4902 scene multiplicity differs: {unexpected_parallel_counts}"
        )
    if parallel_event_count != EXPECTED_PARALLEL_EVENT_COUNT:
        raise PresentationAuthorityError(
            "ac4902 parallel event count differs: "
            f"expected={EXPECTED_PARALLEL_EVENT_COUNT} actual={parallel_event_count}"
        )

    authority["schema"] = "magireco-ac4902-gfdirection-presentation-authority-v1"
    authority["summary"]["parallel_event_count"] = parallel_event_count
    authority["summary"]["single_scene_event_count"] = (
        len(EVENT_IDS) - parallel_event_count
    )
    authority["assertions"] = {
        "all_64_runtime_events_are_present": True,
        "all_97_runtime_scenes_bind_exact_type2_presentations": True,
        "all_97_runtime_cuts_match_type2_scene_references": True,
        "all_97_runtime_cuts_bind_exact_hashed_type3_records": True,
        "owning_gdp_layers_resolved_by_exact_two_word_hash_not_label": True,
        "thirty_three_secondary_presentations_share_event_global_frame_zero": True,
        "event_extent_is_maximum_of_parallel_type2_presentations": True,
        "all_164_type20_nodes_partition_into_archive_or_symbolic": True,
        "five_symbolic_counter_nodes_are_not_claimed_as_missing_cri_movies": True,
        "keyed_float_layout_is_code_exact_time_curve_value": True,
        "event_global_motion_ranges_include_cut_instance_offsets": True,
        "machine_vision_used_as_authority": False,
        "media_modified": False,
        "final_416x232_projection_resolved": False,
        "production_disposition": (
            "FAIL_CLOSED_UNTIL_FINAL_OUTPUT_PROJECTION_IS_CODE_BOUND"
        ),
    }
    return authority


def write_outputs(authority: dict[str, Any], output_dir: Path) -> None:
    """Atomically write the immutable ac4902 authority and its audit roles."""

    if output_dir.exists():
        raise PresentationAuthorityError(
            f"immutable output already exists: {output_dir}"
        )
    stage = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
    if stage.exists():
        raise PresentationAuthorityError(f"staging output already exists: {stage}")
    stage.mkdir(parents=True)
    try:
        authority_path = stage / "AC4902_GFDIRECTION_PRESENTATION_AUTHORITY.json"
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
            raise PresentationAuthorityError("ac4902 authority has no node rows")
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        _write_rollback(rollback_path, output_dir)
        readme_path.write_text(
            "# ac4902 GFDirection event-global presentation authority\n\n"
            "This immutable checkpoint binds all 64 events, 97 scene instances, "
            "97 exact Type-3 cuts, and 164 Type-20 node occurrences to the exact "
            "Slot binary, GDB/GDP bytes, runtime scene graph, and parent-Z2D "
            "partition. Thirty-three events have two Type-2 presentations that "
            "start together at event-global frame zero; they are parallel rather "
            "than serial fragments. Five numeric upper-counter nodes are symbolic "
            "runtime overlays, not missing CRI movies. Final native 416x232 output "
            "projection remains fail-closed, and no media was rendered or changed.\n",
            encoding="utf-8",
        )
        verification = {
            "schema": "magireco-ac4902-gfdirection-presentation-verification-v1",
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
            "outputs": {
                authority_path.name: sha256_bytes(authority_path.read_bytes()),
                csv_path.name: sha256_bytes(csv_path.read_bytes()),
                readme_path.name: sha256_bytes(readme_path.read_bytes()),
                rollback_path.name: sha256_bytes(rollback_path.read_bytes()),
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
    authority = build_ac4902_authority(
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
        f"archive_occurrences={authority['summary']['archive_backed_z2d_occurrence_count']} "
        f"symbolic_occurrences={authority['summary']['runtime_symbolic_z2d_occurrence_count']} "
        f"parallel_events={authority['summary']['parallel_event_count']} "
        "projection=FAIL_CLOSED_PENDING"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
