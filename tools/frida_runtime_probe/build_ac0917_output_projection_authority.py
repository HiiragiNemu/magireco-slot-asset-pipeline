#!/usr/bin/env python3
"""Bind ``ac0917`` MovieLayers to the exact native 416x232 output schedule.

The family reuses the code-exact GFDirection projection resolver, but it has
three authored MovieLayer occurrences whose first frame is later than the
active parent event clock.  Those occurrences are retained as exact source
provenance and explicitly excluded from rendering; they are not treated as
missing media and they do not extend the event.
"""

from __future__ import annotations

import argparse
import csv
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_ac0915_output_projection_authority as generic
    from .build_exhaustive_unique_longform import file_sha256, read_json, write_json
    from .resolve_ac4903_exhaustive_authority import validate_renderer_authority
except ImportError:  # pragma: no cover - direct script execution
    import build_ac0915_output_projection_authority as generic  # type: ignore
    from build_exhaustive_unique_longform import file_sha256, read_json, write_json  # type: ignore
    from resolve_ac4903_exhaustive_authority import validate_renderer_authority  # type: ignore


SCHEMA = "magireco-ac0917-output-projection-authority-v1"
VERIFY_SCHEMA = "magireco-ac0917-output-projection-verification-v1"
EVENTS = tuple(
    f"ac0917_{index:03d}" for index in (*range(1, 12), 14)
)
EXPECTED_COUNTS = {
    "events": 12,
    "archive_backed_z2d_occurrences": 30,
    "movie_bearing_z2d_occurrences": 13,
    "non_movie_text_z2d_occurrences": 17,
    "runtime_symbolic_node_occurrences": 5,
    "loadable_movie_layer_occurrences": 22,
    "unique_loadable_cri_sources": 20,
    "exact_cri_source_identity_count": 21,
    "parent_clock_excluded_movie_layer_occurrences": 3,
    "unique_parent_clock_excluded_source_names": 3,
    "unreachable_movie_layer_occurrences": 0,
    "unique_unreachable_movie_layer_names": 0,
    "renderer_state_1_occurrences": 20,
    "renderer_state_3_occurrences": 2,
    "authored_tail_trim_occurrences": 0,
    "parent_clock_tail_clip_occurrences": 3,
    "parent_clock_clipped_frames": 220,
    "partial_viewport_movie_layer_occurrences": 0,
    "prior_underlay_required_events": 0,
}
PARENT_CLOCK_EXCLUDED = frozenset(
    {
        (
            "ac0917_002",
            "ac0917_3on_01_c03_MR",
            "ac0917_3on_01_lp_c03_MR",
        ),
        (
            "ac0917_007",
            "ac0917_3on_hat_c03_MR",
            "ac0917_3on_hat_lp_c03_MR",
        ),
        (
            "ac0917_011",
            "ac0917_3on_02_c03_MR",
            "ac0917_3on_02_lp_c03_MR",
        ),
    }
)
STATE3_SOURCES = frozenset(
    {"ac8050_uwanose_impact_ef", "ac8050_uwanose_impact_ef_LP"}
)


def resolve_ac0917(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    cri: Mapping[str, Any],
    project: Mapping[str, Any],
    renderer: Mapping[str, Any],
) -> dict[str, Any]:
    return generic.resolve(
        presentation,
        movie,
        cri,
        project,
        renderer,
        expected_events=EVENTS,
        expected_presentation_schema=(
            "magireco-ac0917-gfdirection-presentation-authority-v1"
        ),
        family_label="ac0917",
        expected_counts=EXPECTED_COUNTS,
        expected_chunk_count=23,
        expected_movie_layer_count=21,
        expected_unique_loadable_layer_count=21,
        expected_unique_unreachable_layer_count=0,
        expected_cri_source_identity_count=21,
        expected_state3_names=STATE3_SOURCES,
        expected_unreachable_names=frozenset(),
        expected_parent_clock_excluded_occurrences=PARENT_CLOCK_EXCLUDED,
    )


def _excluded_csv_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in result["parent_clock_excluded_occurrences"]:
        source = row["source"]
        rows.append(
            {
                "event": row["event"],
                "scene": row["scene"],
                "cut": row["cut"],
                "parent_z2d": row["parent_z2d"],
                "source_name": row["source_name"],
                "source_sha256": source["sha256"],
                "authored_event_start_frame": row["authored_event_start_frame"],
                "authored_event_end_frame_inclusive": row[
                    "authored_event_end_frame_inclusive"
                ],
                "active_parent_start_frame": row["active_parent_start_frame"],
                "active_parent_end_frame_inclusive": row[
                    "active_parent_end_frame_inclusive"
                ],
                "schedule_disposition": row["schedule_disposition"],
            }
        )
    return rows


def write_outputs(
    *,
    result: Mapping[str, Any],
    renderer: Mapping[str, Any],
    input_paths: Sequence[Path],
    output_dir: Path,
) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"immutable output already exists: {output_dir}")
    staging = output_dir.with_name(
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    staging.mkdir(parents=True)
    try:
        counts = dict(result["counts"])
        authority = {
            "schema": SCHEMA,
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "family": "ac0917",
            "product_semantics": (
                "duplicate_free_exhaustive_editorial_collection_not_native_single_session"
            ),
            "output_canvas": list(generic.OUTPUT),
            "frame_rate": "30/1",
            "inputs": [generic._binding(path) for path in input_paths],
            "code_authority": [
                {"address": address, "function": function, "proves": proves}
                for address, function, proves in generic.GFDIRECTION_DRAW_AUTHORITY
            ],
            "exact_renderer_contract": dict(renderer),
            "projection_policy": {
                "virtual_renderbuffer": list(generic.RENDERBUFFER),
                "physical_story_crop_ltrb": list(generic.NORMAL_CROP_LTRB),
                "physical_story_surface": [1024, 576],
                "native_output": list(generic.OUTPUT),
                "all_gdp_layers_draw_in_ascending_compiled_index": True,
                "fully_parent_clock_excluded_layers_extend_event": False,
                "fully_parent_clock_excluded_layers_are_rendered": False,
                "exact_source_identity_is_retained_as_provenance": True,
            },
            "events": result["events"],
            "parent_clock_excluded_occurrences": result[
                "parent_clock_excluded_occurrences"
            ],
            "summary": {
                **counts,
                "runtime_authored_component_scale_sources": result[
                    "runtime_authored_component_scale_sources"
                ],
            },
            "assertions": {
                "all_12_events_projected": True,
                "all_21_exact_cri_identities_accounted": True,
                "all_22_scheduled_occurrences_have_exact_source_hashes": True,
                "three_out_of_clock_occurrences_are_not_rendered": True,
                "one_globally_unscheduled_hat_lp_source_is_not_forced_into_video": True,
                "five_symbolic_counter_nodes_are_not_missing_cri_videos": True,
                "seventeen_non_movie_z2d_occurrences_are_not_missing_cri_videos": True,
                "renderer_state_1_and_3_are_exact_slot_ida_bound": True,
                "renderer_state_3_is_premultiplied_addition_not_screen": True,
                "all_events_use_exact_normal_story_crop": True,
                "machine_vision_used_as_authority": False,
                "source_media_modified": False,
                "media_rendered": False,
                "P16_P17_P18_reference_count": 0,
            },
        }
        authority_path = staging / "AC0917_OUTPUT_PROJECTION_AUTHORITY.json"
        write_json(authority_path, authority)

        projection_rows = generic._flatten_csv_rows(result)
        projection_csv = staging / "MOVIELAYER_OUTPUT_PROJECTIONS.csv"
        with projection_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(projection_rows[0]))
            writer.writeheader()
            writer.writerows(projection_rows)

        excluded_rows = _excluded_csv_rows(result)
        excluded_csv = staging / "PARENT_CLOCK_EXCLUDED_MOVIELAYERS.csv"
        with excluded_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(excluded_rows[0]))
            writer.writeheader()
            writer.writerows(excluded_rows)

        readme_path = staging / "README.md"
        readme_path.write_text(
            "# ac0917 原生 416×232 输出投影权威\n\n"
            "12 个事件共 21 个精确 CRI 身份；其中 22 次 MovieLayer 出现在父事件"
            "有效时钟内并按代码投影。另 3 次尾层首帧晚于父事件终点，按游戏绘制"
            "时钟排除，不延长事件、不猜补帧；其源身份和哈希仍完整保留。"
            "`ac0917_3on_hat_lp_c03_MR` 在本 family 内没有可见调度，因此不强塞入"
            "剧情成片。当前检查点未渲染或修改媒体。\n",
            encoding="utf-8",
        )
        rollback_path = staging / "ROLLBACK.ps1"
        rollback_path.write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not (Test-Path -LiteralPath (Join-Path $Root 'VERIFICATION_RECORD.json'))) { throw 'verification missing' }\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable ac0917 projection checkpoint can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8",
        )
        verification = {
            "schema": VERIFY_SCHEMA,
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "literal_result": (
                "PASS events=12 visible_occurrences=22 visible_unique_sources=20 "
                "source_identities=21 clock_excluded_occurrences=3 output=416x232"
            ),
            "checks": authority["assertions"],
            "outputs": {
                authority_path.name: file_sha256(authority_path),
                projection_csv.name: file_sha256(projection_csv),
                excluded_csv.name: file_sha256(excluded_csv),
                readme_path.name: file_sha256(readme_path),
                rollback_path.name: file_sha256(rollback_path),
            },
        }
        write_json(staging / "VERIFICATION_RECORD.json", verification)
        staging.replace(output_dir)
    except BaseException:
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text(
                "Projection authority construction failed; inspect the command error.\n",
                encoding="utf-8",
            )
        raise
    return output_dir


def build(
    *,
    binary_path: Path,
    presentation_path: Path,
    movie_path: Path,
    cri_path: Path,
    project_path: Path,
    renderer_order_path: Path,
    output_dir: Path,
) -> Path:
    binary_path = binary_path.resolve()
    if (
        not binary_path.is_file()
        or file_sha256(binary_path) != generic.SLOT_BINARY_SHA256
    ):
        raise generic.ProjectionError("exact Slot binary SHA-256 differs")
    renderer = validate_renderer_authority(read_json(renderer_order_path), binary_path)
    result = resolve_ac0917(
        read_json(presentation_path),
        read_json(movie_path),
        read_json(cri_path),
        read_json(project_path),
        renderer,
    )
    return write_outputs(
        result=result,
        renderer=renderer,
        input_paths=(
            presentation_path.resolve(),
            movie_path.resolve(),
            cri_path.resolve(),
            project_path.resolve(),
            renderer_order_path.resolve(),
            binary_path,
        ),
        output_dir=output_dir,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--presentation", required=True, type=Path)
    parser.add_argument("--movie", required=True, type=Path)
    parser.add_argument("--cri", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--renderer-order", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = build(
        binary_path=args.binary,
        presentation_path=args.presentation,
        movie_path=args.movie,
        cri_path=args.cri,
        project_path=args.project,
        renderer_order_path=args.renderer_order,
        output_dir=args.output_dir,
    )
    print(read_json(output / "VERIFICATION_RECORD.json")["literal_result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
