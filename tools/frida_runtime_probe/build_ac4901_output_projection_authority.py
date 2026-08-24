#!/usr/bin/env python3
"""Resolve complete ac4901 layers onto native 416x232 route compositions."""

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
        ProjectionError,
        _binding,
        _flatten_csv_rows,
        resolve,
    )
    from .build_ac4901_gfdirection_presentation_authority import EVENT_IDS
    from .build_exhaustive_unique_longform import read_json, write_json
    from .resolve_ac4903_exhaustive_authority import validate_renderer_authority
except ImportError:  # pragma: no cover - direct script execution
    from build_ac0915_output_projection_authority import (  # type: ignore
        GFDIRECTION_DRAW_AUTHORITY,
        NORMAL_CROP_LTRB,
        OUTPUT,
        RENDERBUFFER,
        ProjectionError,
        _binding,
        _flatten_csv_rows,
        resolve,
    )
    from build_ac4901_gfdirection_presentation_authority import EVENT_IDS  # type: ignore
    from build_exhaustive_unique_longform import read_json, write_json  # type: ignore
    from resolve_ac4903_exhaustive_authority import (  # type: ignore
        validate_renderer_authority,
    )


SCHEMA = "magireco-ac4901-output-projection-authority-v1"
VERIFY_SCHEMA = "magireco-ac4901-output-projection-verification-v1"
PRESENTATION_SCHEMA = "magireco-ac4901-gfdirection-presentation-authority-v1"
EXPECTED_COUNTS = {
    "events": 205,
    "archive_backed_z2d_occurrences": 463,
    "movie_bearing_z2d_occurrences": 335,
    "non_movie_text_z2d_occurrences": 128,
    "runtime_symbolic_node_occurrences": 5,
    "loadable_movie_layer_occurrences": 591,
    "unique_loadable_cri_sources": 194,
    "unreachable_movie_layer_occurrences": 0,
    "unique_unreachable_movie_layer_names": 0,
    "renderer_state_1_occurrences": 589,
    "renderer_state_3_occurrences": 2,
    "authored_tail_trim_occurrences": 0,
    "partial_viewport_movie_layer_occurrences": 2,
    "prior_underlay_required_events": 1,
}
EXPECTED_STATE3_NAMES = frozenset(
    {"ac8050_uwanose_impact_ef", "ac8050_uwanose_impact_ef_LP"}
)
PRIOR_UNDERLAY_EVENTS = frozenset({"ac4901_091"})


def resolve_ac4901(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    cri: Mapping[str, Any],
    project: Mapping[str, Any],
    renderer: Mapping[str, Any],
) -> dict[str, Any]:
    return resolve(
        presentation,
        movie,
        cri,
        project,
        renderer,
        expected_events=EVENT_IDS,
        expected_presentation_schema=PRESENTATION_SCHEMA,
        family_label="ac4901",
        expected_counts=EXPECTED_COUNTS,
        expected_chunk_count=103,
        expected_movie_layer_count=194,
        expected_unique_loadable_layer_count=194,
        expected_unique_unreachable_layer_count=0,
        expected_state3_names=EXPECTED_STATE3_NAMES,
        expected_unreachable_names=frozenset(),
        allowed_partial_viewport_events=PRIOR_UNDERLAY_EVENTS,
    )


def _authority_document(
    result: Mapping[str, Any],
    renderer: Mapping[str, Any],
    inputs: Sequence[Path],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "PASS_READY_FOR_ROUTE_STATE_CARRY_AUDIO_AND_DEDUP_AUTHORITY",
        "family": "ac4901",
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
            "compose_all_parallel_layers_before_crop": True,
            "normal_sources_map_to_native_416x232_without_editorial_upscale": True,
            "ac4901_091_partial_button_layers_require_route_prior_frame_underlay": True,
        },
        "events": result["events"],
        "summary": {
            **result["counts"],
            "runtime_authored_component_scale_sources": result[
                "runtime_authored_component_scale_sources"
            ],
            "prior_underlay_events": sorted(PRIOR_UNDERLAY_EVENTS),
        },
        "assertions": {
            "all_205_events_projected": True,
            "all_194_exact_cri_sources_reachable": True,
            "all_591_loadable_occurrences_have_exact_source_bindings": True,
            "five_symbolic_counter_nodes_are_not_missing_videos": True,
            "one_hundred_twenty_eight_non_movie_z2d_occurrences_are_not_missing_videos": True,
            "no_authored_movie_layer_is_unreachable": True,
            "renderer_state_1_and_3_are_exact_slot_ida_bound": True,
            "renderer_state_3_is_premultiplied_addition_not_screen": True,
            "only_ac4901_091_requires_prior_frame_underlay": True,
            "two_partial_button_layers_are_not_stretched_to_full_canvas": True,
            "no_source_tail_is_editorially_trimmed": True,
            "source_media_untouched": True,
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
        authority_path = staging / "AC4901_OUTPUT_PROJECTION_AUTHORITY.json"
        write_json(authority_path, authority)
        csv_path = staging / "MOVIELAYER_OUTPUT_PROJECTIONS.csv"
        rows = _flatten_csv_rows(result)
        if not rows:
            raise ProjectionError("ac4901 projection has no MovieLayer rows")
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        readme_path = staging / "README.md"
        readme_path.write_text(
            "# ac4901 native-416 output projection authority\n\n"
            "All 205 events compose on the exact 1280x1024 virtual buffer and "
            "then crop `[128,0,1152,576]` to native 416x232. Of 591 loadable "
            "MovieLayer occurrences, only the two ac4901_091 chance-button layers "
            "are partial. They retain exact geometry and require the prior route "
            "frame as underlay; they are never stretched into standalone video.\n",
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
            "status": "PASS_READY_FOR_ROUTE_STATE_CARRY_AUDIO_AND_DEDUP_AUTHORITY",
            "literal_result": (
                f"PASS events={result['counts']['events']} "
                f"loadable_occurrences={result['counts']['loadable_movie_layer_occurrences']} "
                f"unique_sources={result['counts']['unique_loadable_cri_sources']} "
                f"partial_layers={result['counts']['partial_viewport_movie_layer_occurrences']} "
                f"prior_underlay_events={result['counts']['prior_underlay_required_events']} "
                f"state3={result['counts']['renderer_state_3_occurrences']} "
                f"unreachable={result['counts']['unreachable_movie_layer_occurrences']} "
                "output=416x232"
            ),
            "checks": authority["assertions"],
            "output_byte_counts": {
                path.name: path.stat().st_size
                for path in (authority_path, csv_path, readme_path, rollback_path)
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
    if not binary_path.is_file():
        raise ProjectionError("exact Slot binary is absent")
    renderer = validate_renderer_authority(read_json(renderer_order_path), binary_path)
    inputs = [
        presentation_path.resolve(),
        movie_path.resolve(),
        cri_path.resolve(),
        project_path.resolve(),
        renderer_order_path.resolve(),
        binary_path,
    ]
    result = resolve_ac4901(
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
