#!/usr/bin/env python3
"""Resolve ac0917 parent-clock Z2D playback into exact source-frame schedules.

The authority is deliberately code driven.  It mirrors the proven
``CGFDirectionNodeMotionZ2D::SetKeyTime`` modes through the shared ac4901
implementation, clips every parent to the event-global GFDirection cut, and
then binds each mapped scene frame to exactly one projected CRI MovieLayer.
No filename-based ``_LP`` inference and no visual repeat-last heuristic is
used.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac4901_z2d_loop_authority import (
        bind_exact_source,
        compress_source_frames,
        scene_frame_at,
    )
    from .build_exhaustive_unique_longform import file_sha256, read_json
except ImportError:  # pragma: no cover - direct script execution
    from build_ac4901_z2d_loop_authority import (  # type: ignore
        bind_exact_source,
        compress_source_frames,
        scene_frame_at,
    )
    from build_exhaustive_unique_longform import file_sha256, read_json  # type: ignore


SLOT_BINARY_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
EVENT_IDS = tuple(f"ac0917_{index:03d}" for index in (*range(1, 12), 14))
EXPECTED = {
    "events": 12,
    "archive_nodes": 30,
    "movie_parents": 13,
    "non_movie_nodes": 17,
    "intro_then_scene_loop_parents": 12,
    "whole_scene_loop_parents": 1,
    "extended_loop_parents": 3,
    "loop_extension_frames": 207,
    "scheduled_movie_frame_occurrences": 2711,
    "render_segments": 31,
    "loadable_movie_layer_occurrences": 22,
    "unique_sources": 20,
    "parent_clock_excluded_occurrences": 3,
}


class Ac0917Z2DLoopError(ValueError):
    pass


def _projection_key_text(key: tuple[str, str, str, str]) -> str:
    return "|".join(key)


def _bind_output(stage_path: Path, output_dir: Path) -> dict[str, Any]:
    result = bind_exact_source(stage_path)
    result["path"] = str((output_dir.resolve() / stage_path.name))
    return result


def _validate_inputs(
    presentation: Mapping[str, Any],
    movie: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> None:
    if (
        presentation.get("schema")
        != "magireco-ac0917-gfdirection-presentation-authority-v1"
        or presentation.get("status")
        != "passed_code_runtime_cross_bound_projection_pending"
        or presentation.get("summary", {}).get("event_count") != EXPECTED["events"]
        or presentation.get("summary", {}).get(
            "archive_backed_z2d_occurrence_count"
        )
        != EXPECTED["archive_nodes"]
    ):
        raise Ac0917Z2DLoopError("ac0917 presentation authority differs")
    if (
        movie.get("schema") != "magireco-z2d-movielayer-reachability-authority-v1"
        or movie.get("status") != "passed"
        or movie.get("counts", {}).get("z2d_chunks") != 23
        or movie.get("counts", {}).get("loadable_movie_layers") != 21
        or movie.get("counts", {}).get("unreachable_movie_layers") != 0
    ):
        raise Ac0917Z2DLoopError("ac0917 MovieLayer authority differs")
    if (
        projection.get("schema")
        != "magireco-ac0917-output-projection-authority-v1"
        or projection.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or projection.get("summary", {}).get("movie_bearing_z2d_occurrences")
        != EXPECTED["movie_parents"]
        or projection.get("summary", {}).get("loadable_movie_layer_occurrences")
        != EXPECTED["loadable_movie_layer_occurrences"]
        or projection.get("summary", {}).get("parent_clock_excluded_movie_layer_occurrences")
        != EXPECTED["parent_clock_excluded_occurrences"]
    ):
        raise Ac0917Z2DLoopError("ac0917 projection authority differs")


def build_report(
    *,
    presentation_path: Path,
    movie_layer_path: Path,
    projection_path: Path,
    slot_binary_path: Path,
) -> dict[str, Any]:
    presentation = read_json(presentation_path)
    movie = read_json(movie_layer_path)
    projection = read_json(projection_path)
    binary = bind_exact_source(slot_binary_path.resolve())
    if str(binary["sha256"]).upper() != SLOT_BINARY_SHA256:
        raise Ac0917Z2DLoopError("exact Slot libGameProc.so SHA-256 differs")
    _validate_inputs(presentation, movie, projection)

    chunks = {str(row["name"]): row for row in movie["z2d_chunks"]}
    presentation_events = {str(row["event_id"]): row for row in presentation["events"]}
    projection_events = {str(row["event"]): row for row in projection["events"]}
    if set(presentation_events) != set(EVENT_IDS) or set(projection_events) != set(EVENT_IDS):
        raise Ac0917Z2DLoopError("ac0917 event set differs")

    projection_rows: dict[tuple[str, str, str, str, str], Mapping[str, Any]] = {}
    source_catalog: dict[str, Mapping[str, Any]] = {}
    for event_id, event in projection_events.items():
        for row in event["layers_in_render_pass_order_under_to_top"]:
            key = (
                event_id,
                str(row["scene"]),
                str(row["cut"]),
                str(row["parent_z2d"]),
                str(row["source_name"]),
            )
            if key in projection_rows:
                raise Ac0917Z2DLoopError(f"duplicate projection key: {key}")
            projection_rows[key] = row
            source_catalog[str(row["source_name"])] = row["source"]
    if (
        len(projection_rows) != EXPECTED["loadable_movie_layer_occurrences"]
        or len(source_catalog) != EXPECTED["unique_sources"]
    ):
        raise Ac0917Z2DLoopError("projection source catalog differs")

    events: list[dict[str, Any]] = []
    mode_counts: Counter[str] = Counter()
    movie_parent_count = 0
    non_movie_count = 0
    extended_parent_count = 0
    extension_frames = 0
    scheduled_frames = 0
    render_segment_count = 0
    referenced_projection_keys: set[tuple[str, str, str, str, str]] = set()

    for event_id in EVENT_IDS:
        event = presentation_events[event_id]
        event_frames = int(event["presentation_frame_count"])
        schedules: list[dict[str, Any]] = []
        for scene in event["scenes"]:
            scene_global_start = int(scene["event_global_start_frame"])
            for cut in scene["cuts"]:
                cut_offset = int(cut["instance_offset_frames"])
                cut_start = scene_global_start + cut_offset + int(cut["cut_start_frame"])
                cut_end = min(
                    scene_global_start
                    + cut_offset
                    + int(cut["cut_end_frame_inclusive"]),
                    event_frames - 1,
                )
                for node in cut["z2d_nodes"]:
                    if node["node_authority_class"] != "exact_apk_z2d":
                        continue
                    parent_name = str(node["normalised_z2d_name"])
                    chunk = chunks.get(parent_name)
                    if chunk is None:
                        raise Ac0917Z2DLoopError(
                            f"archive parent Z2D is absent: {parent_name}"
                        )
                    movie_layers = [
                        row
                        for row in chunk["movie_layers"]
                        if row["runtime_load_disposition"] == "LOADABLE_BY_EXACT_NAME"
                    ]
                    if not movie_layers:
                        non_movie_count += 1
                        continue
                    movie_parent_count += 1
                    keys = list(node["motion_keys"])
                    if len(keys) != 1:
                        raise Ac0917Z2DLoopError(
                            f"parent Z2D motion-key count differs: {event_id}/{parent_name}"
                        )
                    key = keys[0]
                    raw = [int(value) for value in key["raw_floats"]]
                    flags = [int(value) for value in key["raw_flags"]]
                    key_start = scene_global_start + cut_offset + raw[0]
                    raw_key_end = scene_global_start + cut_offset + raw[1]
                    persistent = bool(flags[2] & 1)
                    active_start = max(key_start, cut_start)
                    active_end = cut_end if persistent else min(raw_key_end, cut_end)
                    if active_end < active_start:
                        raise Ac0917Z2DLoopError(
                            f"parent active interval is empty: {event_id}/{parent_name}"
                        )

                    header = chunk["header"]
                    scene_start = int(header["scene_start_frame"])
                    scene_end = int(header["scene_end_frame_inclusive"])
                    loop_frame = int(header["scene_loop_frame"])
                    mode = 3 if loop_frame != scene_start else flags[1]
                    mode_names = {
                        3: "intro_then_scene_loop",
                        2: "whole_scene_loop",
                        1: "hold_scene_end",
                        0: "play_once",
                    }
                    if mode not in mode_names:
                        raise Ac0917Z2DLoopError(
                            f"unsupported parent motion mode: {event_id}/{parent_name}/{mode}"
                        )
                    mode_name = mode_names[mode]
                    mode_counts[mode_name] += 1
                    first_pass_end = key_start + (scene_end - scene_start)
                    extended = max(0, active_end - first_pass_end)
                    if extended:
                        extended_parent_count += 1
                        extension_frames += extended

                    frame_rows: list[dict[str, Any]] = []
                    for event_frame in range(active_start, active_end + 1):
                        mapped = scene_frame_at(
                            event_frame=event_frame,
                            key_start_frame=key_start,
                            scene_start_frame=scene_start,
                            scene_end_frame_inclusive=scene_end,
                            scene_loop_frame=loop_frame,
                            motion_mode=mode,
                        )
                        if mapped is None:
                            continue
                        matching = [
                            row
                            for row in movie_layers
                            if int(row["start_frame"])
                            <= mapped
                            <= int(row["end_frame_inclusive"])
                        ]
                        if len(matching) != 1:
                            raise Ac0917Z2DLoopError(
                                "scene frame does not select one MovieLayer: "
                                f"{event_id}/{parent_name}/{mapped}"
                            )
                        layer = matching[0]
                        source_name = str(layer["cri_lookup_base_name"])
                        lookup = (
                            event_id,
                            str(scene["name"]),
                            str(cut["cut_name"]),
                            parent_name,
                            source_name,
                        )
                        projection_row = projection_rows.get(lookup)
                        if projection_row is None:
                            raise Ac0917Z2DLoopError(
                                f"MovieLayer projection is absent: {lookup}"
                            )
                        source_frame = mapped - int(layer["start_frame"])
                        if source_frame >= int(projection_row["source"]["frame_count"]):
                            raise Ac0917Z2DLoopError(
                                f"mapped source frame exceeds CRI source: {lookup}/{source_frame}"
                            )
                        referenced_projection_keys.add(lookup)
                        frame_rows.append(
                            {
                                "event_frame": event_frame,
                                "scene_frame": mapped,
                                "source_frame": source_frame,
                                "source_name": source_name,
                                "projection_key": _projection_key_text(lookup[1:]),
                            }
                        )
                    segments = compress_source_frames(frame_rows)
                    if sum(row["frame_count"] for row in segments) != len(frame_rows):
                        raise Ac0917Z2DLoopError("parent schedule coverage differs")
                    scheduled_frames += len(frame_rows)
                    render_segment_count += len(segments)
                    schedules.append(
                        {
                            "event": event_id,
                            "scene": str(scene["name"]),
                            "cut": str(cut["cut_name"]),
                            "parent_z2d": parent_name,
                            "owning_gdp_layer_index": int(
                                node["owning_layer"]["index"]
                            ),
                            "motion_key_raw_floats": raw,
                            "motion_key_raw_flags": flags,
                            "persistent_last_key": persistent,
                            "active_event_start_frame": active_start,
                            "active_event_end_frame_inclusive": active_end,
                            "scene_start_frame": scene_start,
                            "scene_end_frame_inclusive": scene_end,
                            "scene_loop_frame": loop_frame,
                            "motion_mode": mode,
                            "mapping_policy": mode_name,
                            "first_pass_end_event_frame": first_pass_end,
                            "loop_extension_frames": extended,
                            "scheduled_movie_frame_occurrences": len(frame_rows),
                            "render_segments": segments,
                        }
                    )
        if not schedules:
            raise Ac0917Z2DLoopError(
                f"event has no loadable MovieLayer schedule: {event_id}"
            )
        events.append(
            {
                "event": event_id,
                "presentation_frame_count": event_frames,
                "movie_parent_schedule_count": len(schedules),
                "scheduled_movie_frame_occurrences": sum(
                    row["scheduled_movie_frame_occurrences"] for row in schedules
                ),
                "parent_z2d_schedules_in_gfdirection_order": schedules,
            }
        )

    actual = {
        "events": len(events),
        "archive_nodes": presentation["summary"]["archive_backed_z2d_occurrence_count"],
        "movie_parents": movie_parent_count,
        "non_movie_nodes": non_movie_count,
        "intro_then_scene_loop_parents": mode_counts["intro_then_scene_loop"],
        "whole_scene_loop_parents": mode_counts["whole_scene_loop"],
        "extended_loop_parents": extended_parent_count,
        "loop_extension_frames": extension_frames,
        "scheduled_movie_frame_occurrences": scheduled_frames,
        "render_segments": render_segment_count,
        "loadable_movie_layer_occurrences": len(referenced_projection_keys),
        "unique_sources": len(source_catalog),
        "parent_clock_excluded_occurrences": len(
            projection["parent_clock_excluded_occurrences"]
        ),
    }
    if actual != EXPECTED:
        raise Ac0917Z2DLoopError(f"frozen ac0917 loop dimensions differ: {actual}")
    if referenced_projection_keys != set(projection_rows):
        raise Ac0917Z2DLoopError("not every visible projection occurrence was scheduled")

    return {
        "schema": "magireco-ac0917-parent-clock-z2d-loop-authority-v1",
        "status": "PASS_READY_FOR_LOOP_AWARE_ROUTE_DEDUP_AND_LONGFORM_RENDER",
        "family": "ac0917",
        "exact_slot_binary": binary,
        "inputs": {
            "gfdirection_presentation": bind_exact_source(presentation_path.resolve()),
            "z2d_movie_layers": bind_exact_source(movie_layer_path.resolve()),
            "output_projection": bind_exact_source(projection_path.resolve()),
        },
        "code_authority": [
            {
                "address": "0x42b12bc",
                "function": "CGFDirectionNodeMotionBase::GetKey",
                "proves": "persistent final motion keys remain selected to the exact cut end",
            },
            {
                "address": "0x42b342c",
                "function": "CGFDirectionNodeMotionZ2D::SetKeyTime",
                "proves": "mode 3 repeats the exact scene loop interval and mode 2 repeats the whole scene",
            },
            {
                "address": "0x42b43e0",
                "function": "CGFDirectionNodeMotionZ2D::Calc",
                "proves": "the active GFDirection cut clock selects the key and calls SetKeyTime",
            },
            {
                "address": "0x435e284",
                "function": "CZ2DPlayer::ExecPlayMovie",
                "proves": "MovieLayer decode follows current Z2D scene time, including loop re-entry",
            },
        ],
        "mapping_contract": {
            "clock": "event-global GFDirection Type-2/Type-3 cut time",
            "persistent_key": "motion_key_raw_flags[2] bit 0 extends the final key only to cut end",
            "mode_3": "intro once, then repeat scene_loop_frame..scene_end",
            "mode_2": "repeat scene_start..scene_end",
            "source_frame": "mapped_scene_frame - MovieLayer.start_frame",
            "parent_clock_clip": "cut/event end is the hard upper bound",
            "parallel_parent_policy": "preserve each active GFDirection parent schedule independently",
        },
        "source_catalog": source_catalog,
        "events": events,
        "parent_clock_excluded_occurrences": projection[
            "parent_clock_excluded_occurrences"
        ],
        "summary": actual,
        "assertions": {
            "exact_slot_binary_hash_bound": True,
            "all_12_events_scheduled": True,
            "all_22_visible_projected_movie_layers_referenced": True,
            "three_parent_clock_excluded_layers_remain_excluded": True,
            "all_207_post_first_pass_frames_use_code_proven_loop_mapping": True,
            "no_filename_loop_inference_used": True,
            "no_repeatlast_guess_used": True,
            "parallel_gfdirection_parents_preserved": True,
            "unreachable_movie_layer_leak_count": 0,
            "P16_P17_P18_reference_count": 0,
            "source_media_modified": False,
            "media_rendered": False,
            "human_playback_approval_inferred": False,
        },
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise Ac0917Z2DLoopError(f"empty CSV rows: {path.name}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise Ac0917Z2DLoopError(f"immutable output already exists: {output_dir}")
    stage = output_dir.with_name(
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    stage.mkdir(parents=True)
    try:
        authority = stage / "AC0917_Z2D_LOOP_AUTHORITY.json"
        authority.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        parent_rows: list[dict[str, Any]] = []
        segment_rows: list[dict[str, Any]] = []
        for event in report["events"]:
            for parent in event["parent_z2d_schedules_in_gfdirection_order"]:
                parent_rows.append(
                    {
                        **{key: value for key, value in parent.items() if key != "render_segments"},
                        "render_segment_count": len(parent["render_segments"]),
                    }
                )
                for segment in parent["render_segments"]:
                    segment_rows.append(
                        {
                            "event": event["event"],
                            "parent_z2d": parent["parent_z2d"],
                            "owning_gdp_layer_index": parent["owning_gdp_layer_index"],
                            "mapping_policy": parent["mapping_policy"],
                            **segment,
                        }
                    )
        _write_csv(stage / "AC0917_PARENT_Z2D_SCHEDULES.csv", parent_rows)
        _write_csv(stage / "AC0917_LOOP_AWARE_RENDER_SEGMENTS.csv", segment_rows)
        (stage / "README.md").write_text(
            "# ac0917 code-proven parent-clock Z2D loop authority\n\n"
            "This checkpoint applies the exact Slot motion-key and Z2D scene-loop code "
            "to all 12 events. It schedules 2,711 visible MovieLayer frame occurrences "
            "as 31 render segments. Only three parents extend past their first authored "
            "pass (207 frames total); short chance-button cuts end at their authored cut "
            "boundary rather than being guessed to persist for the full event. Three "
            "MovieLayers outside the parent clock remain provenance-only. No media was "
            "rendered or modified.\n",
            encoding="utf-8",
        )
        (stage / "ROLLBACK.ps1").write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not (Test-Path -LiteralPath (Join-Path $Root 'VERIFICATION_RECORD.json'))) { throw 'verification missing' }\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable ac0917 loop checkpoint can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8",
        )
        literal = (
            "PASS events=12 movie_parents=13 loop_parents=12 "
            "extended_loop_parents=3 loop_frames=207 scheduled_frames=2711 "
            "segments=31 sources=20 clock_excluded=3"
        )
        outputs = [
            authority,
            stage / "AC0917_PARENT_Z2D_SCHEDULES.csv",
            stage / "AC0917_LOOP_AWARE_RENDER_SEGMENTS.csv",
            stage / "README.md",
            stage / "ROLLBACK.ps1",
        ]
        verification = {
            "schema": "magireco-ac0917-parent-clock-z2d-loop-verification-v1",
            "status": "PASS",
            "literal_result": literal,
            "checks": report["assertions"],
            "outputs": {
                path.name: _bind_output(path, output_dir) for path in outputs
            },
        }
        (stage / "VERIFICATION_RECORD.json").write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stage.replace(output_dir)
    except BaseException:
        if stage.exists():
            (stage / "FAILED_DO_NOT_USE.txt").write_text(
                "Loop authority construction failed; inspect the command error.\n",
                encoding="utf-8",
            )
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presentation-authority", required=True, type=Path)
    parser.add_argument("--movie-layer-authority", required=True, type=Path)
    parser.add_argument("--projection-authority", required=True, type=Path)
    parser.add_argument("--slot-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        presentation_path=args.presentation_authority,
        movie_layer_path=args.movie_layer_authority,
        projection_path=args.projection_authority,
        slot_binary_path=args.slot_binary,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS events=12 movie_parents=13 loop_parents=12 "
        "extended_loop_parents=3 loop_frames=207 scheduled_frames=2711 "
        "segments=31 sources=20 clock_excluded=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
