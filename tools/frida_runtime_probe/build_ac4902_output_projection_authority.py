#!/usr/bin/env python3
"""Resolve every exact ac4902 MovieLayer onto the native 416x232 surface."""

from __future__ import annotations

import argparse
import csv
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac0915_output_projection_authority import (
        GFDIRECTION_DRAW_AUTHORITY,
        NORMAL_CROP_LTRB,
        OUTPUT,
        RENDERBUFFER,
        SLOT_BINARY_SHA256,
        ProjectionError,
        _binding,
        _flatten_csv_rows,
        resolve,
    )
    from .build_ac4902_gfdirection_presentation_authority import EVENT_IDS
    from .build_exhaustive_unique_longform import file_sha256, read_json, write_json
    from .resolve_ac4903_exhaustive_authority import validate_renderer_authority
except ImportError:  # pragma: no cover - direct script execution
    from build_ac0915_output_projection_authority import (  # type: ignore
        GFDIRECTION_DRAW_AUTHORITY,
        NORMAL_CROP_LTRB,
        OUTPUT,
        RENDERBUFFER,
        SLOT_BINARY_SHA256,
        ProjectionError,
        _binding,
        _flatten_csv_rows,
        resolve,
    )
    from build_ac4902_gfdirection_presentation_authority import EVENT_IDS  # type: ignore
    from build_exhaustive_unique_longform import file_sha256, read_json, write_json  # type: ignore
    from resolve_ac4903_exhaustive_authority import validate_renderer_authority  # type: ignore


SCHEMA = "magireco-ac4902-output-projection-authority-v1"
VERIFY_SCHEMA = "magireco-ac4902-output-projection-verification-v1"
PRESENTATION_SCHEMA = "magireco-ac4902-gfdirection-presentation-authority-v1"
EXPECTED_COUNTS = {
    "events": 64,
    "archive_backed_z2d_occurrences": 159,
    "movie_bearing_z2d_occurrences": 87,
    "non_movie_text_z2d_occurrences": 72,
    "runtime_symbolic_node_occurrences": 5,
    "loadable_movie_layer_occurrences": 171,
    "unique_loadable_cri_sources": 56,
    "unreachable_movie_layer_occurrences": 0,
    "unique_unreachable_movie_layer_names": 0,
    "renderer_state_1_occurrences": 169,
    "renderer_state_3_occurrences": 2,
    "authored_tail_trim_occurrences": 0,
}
EXPECTED_STATE3_NAMES = frozenset(
    {"ac8050_uwanose_impact_ef", "ac8050_uwanose_impact_ef_LP"}
)


def resolve_ac4902(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    cri: Mapping[str, Any],
    project: Mapping[str, Any],
    renderer: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the exact ac4902 cardinalities to the shared projection resolver."""

    return resolve(
        presentation,
        movie,
        cri,
        project,
        renderer,
        expected_events=EVENT_IDS,
        expected_presentation_schema=PRESENTATION_SCHEMA,
        family_label="ac4902",
        expected_counts=EXPECTED_COUNTS,
        expected_chunk_count=50,
        expected_movie_layer_count=60,
        expected_unique_loadable_layer_count=60,
        expected_unique_unreachable_layer_count=0,
        expected_state3_names=EXPECTED_STATE3_NAMES,
        expected_unreachable_names=frozenset(),
    )


def _authority_document(
    result: Mapping[str, Any],
    renderer: Mapping[str, Any],
    inputs: Sequence[Path],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
        "family": "ac4902",
        "product_semantics": (
            "duplicate_free_exhaustive_editorial_collection_not_native_single_session"
        ),
        "output_canvas": list(OUTPUT),
        "frame_rate": "30/1",
        "inputs": [_binding(path) for path in inputs],
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in GFDIRECTION_DRAW_AUTHORITY
        ],
        "exact_renderer_contract": dict(renderer),
        "projection_policy": {
            "virtual_renderbuffer": list(RENDERBUFFER),
            "physical_story_crop_ltrb": list(NORMAL_CROP_LTRB),
            "physical_story_surface": [1024, 576],
            "native_output": list(OUTPUT),
            "all_gdp_layers_draw_in_ascending_compiled_index": True,
            "normal_1024x576_sources_map_to_native_416x232_without_editorial_upscale": True,
            "full_1280x720_or_1280x1024_sources_are_composed_before_the_same_crop": True,
            "runtime_authored_component_scaling_is_not_a_postproduction_upscale": True,
        },
        "events": result["events"],
        "summary": {
            **result["counts"],
            "runtime_authored_component_scale_sources": result[
                "runtime_authored_component_scale_sources"
            ],
        },
        "assertions": {
            "all_64_events_projected": True,
            "all_56_exact_cri_sources_reachable": True,
            "all_171_loadable_occurrences_have_exact_source_hashes": True,
            "five_symbolic_counter_nodes_are_not_missing_cri_videos": True,
            "seventy_two_non_movie_z2d_occurrences_are_not_missing_cri_videos": True,
            "no_authored_movie_layer_is_unreachable": True,
            "renderer_state_1_and_3_are_exact_slot_ida_bound": True,
            "renderer_state_3_is_premultiplied_addition_not_screen": True,
            "all_events_use_exact_normal_story_crop": True,
            "no_source_tail_is_editorially_trimmed": True,
            "source_media_modified": False,
            "media_rendered": False,
            "P16_P17_P18_reference_count": 0,
        },
    }


def _write_checkpoint(
    authority: Mapping[str, Any],
    result: Mapping[str, Any],
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
        authority_path = staging / "AC4902_OUTPUT_PROJECTION_AUTHORITY.json"
        write_json(authority_path, authority)
        csv_path = staging / "MOVIELAYER_OUTPUT_PROJECTIONS.csv"
        rows = _flatten_csv_rows(result)
        if not rows:
            raise ProjectionError("ac4902 projection has no MovieLayer rows")
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        readme_path = staging / "README.md"
        readme_path.write_text(
            "# ac4902 native-416 output projection authority\n\n"
            "全部 64 个事件先在精确 1280×1024 虚拟缓冲区按 GDP 层序合成，再统一裁切 "
            "`[128,0,1152,576]` 并映射为原生 416×232。171 个可加载 MovieLayer "
            "occurrence 覆盖 56 个官方 CRI 源，60 个已编写 MovieLayer 全部可达。两层 "
            "`ac8050` 冲击效果使用 IDA 证明的预乘加算 `src*alpha+dst`，不是 screen。"
            "72 个无影片 Z2D occurrence 和 5 个动态计数节点不是缺失影片。本检查点没有"
            "渲染、裁尾或修改媒体。\n",
            encoding="utf-8",
        )
        rollback_path = staging / "ROLLBACK.ps1"
        rollback_path.write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not (Test-Path -LiteralPath (Join-Path $Root 'VERIFICATION_RECORD.json'))) { throw 'verification missing' }\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable projection checkpoint can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8",
        )
        verification = {
            "schema": VERIFY_SCHEMA,
            "status": "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY",
            "literal_result": (
                f"PASS events={result['counts']['events']} "
                f"loadable_occurrences={result['counts']['loadable_movie_layer_occurrences']} "
                f"unique_sources={result['counts']['unique_loadable_cri_sources']} "
                f"state3={result['counts']['renderer_state_3_occurrences']} "
                f"unreachable={result['counts']['unreachable_movie_layer_occurrences']} "
                "output=416x232"
            ),
            "checks": authority["assertions"],
            "outputs": {
                authority_path.name: file_sha256(authority_path),
                csv_path.name: file_sha256(csv_path),
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
    if not binary_path.is_file() or file_sha256(binary_path) != SLOT_BINARY_SHA256:
        raise ProjectionError("exact Slot binary SHA-256 differs")
    renderer_document = read_json(renderer_order_path)
    renderer = validate_renderer_authority(renderer_document, binary_path)
    inputs = [
        presentation_path.resolve(),
        movie_path.resolve(),
        cri_path.resolve(),
        project_path.resolve(),
        renderer_order_path.resolve(),
        binary_path,
    ]
    result = resolve_ac4902(
        read_json(presentation_path),
        read_json(movie_path),
        read_json(cri_path),
        read_json(project_path),
        renderer,
    )
    authority = _authority_document(result, renderer, inputs)
    return _write_checkpoint(authority, result, output_dir)


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
    verification = read_json(output / "VERIFICATION_RECORD.json")
    print(verification["literal_result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
