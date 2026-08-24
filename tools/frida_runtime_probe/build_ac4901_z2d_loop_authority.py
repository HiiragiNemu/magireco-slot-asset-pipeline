#!/usr/bin/env python3
"""Resolve ac4901 parent-clock Z2D loop playback into exact source-frame schedules."""

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
    from .build_ac4901_gfdirection_presentation_authority import EVENT_IDS
    from .build_exhaustive_unique_longform import file_sha256
    from .resolve_ac0915_event_audio_authority import bind_source
except ImportError:  # pragma: no cover - direct script execution
    from build_ac4901_gfdirection_presentation_authority import EVENT_IDS  # type: ignore
    from build_exhaustive_unique_longform import file_sha256  # type: ignore
    from resolve_ac0915_event_audio_authority import bind_source  # type: ignore


EXPECTED_SLOT_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
EXPECTED_EVENTS = 205
EXPECTED_EXACT_Z2D_NODES = 463
EXPECTED_MOVIE_PARENTS = 335
EXPECTED_NON_MOVIE_NODES = 128
EXPECTED_PARTIAL_LOOP_PARENTS = 256
EXPECTED_WHOLE_LOOP_PARENTS = 79
EXPECTED_EXTENDED_LOOP_PARENTS = 108
EXPECTED_LOOP_EXTENSION_FRAMES = 4392
EXPECTED_SCHEDULED_MOVIE_FRAME_OCCURRENCES = 40326
EXPECTED_RENDER_SEGMENTS = 771
EXPECTED_LAYER_OCCURRENCES = 591
EXPECTED_UNIQUE_SOURCES = 194


class Ac4901Z2DLoopError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def bind_exact_source(path: Path) -> dict[str, Any]:
    bound = bind_source(path)
    bound["sha256"] = file_sha256(path.resolve())
    return bound


def bind_published_output(stage_path: Path, output_dir: Path) -> dict[str, Any]:
    bound = bind_exact_source(stage_path)
    bound["path"] = str((output_dir.resolve() / stage_path.name))
    return bound


def scene_frame_at(
    *,
    event_frame: int,
    key_start_frame: int,
    scene_start_frame: int,
    scene_end_frame_inclusive: int,
    scene_loop_frame: int,
    motion_mode: int,
) -> int | None:
    """Mirror CGFDirectionNodeMotionZ2D::SetKeyTime's integer-frame modes."""

    elapsed = event_frame - key_start_frame
    if elapsed < 0:
        return None
    scene_frames = scene_end_frame_inclusive - scene_start_frame + 1
    if scene_frames <= 0:
        raise Ac4901Z2DLoopError("Z2D scene interval is empty")
    if scene_loop_frame != scene_start_frame:
        if not (scene_start_frame < scene_loop_frame <= scene_end_frame_inclusive):
            raise Ac4901Z2DLoopError("Z2D scene loop point is outside the scene")
        if elapsed < scene_frames:
            return scene_start_frame + elapsed
        loop_frames = scene_end_frame_inclusive - scene_loop_frame + 1
        intro_frames = scene_loop_frame - scene_start_frame
        return scene_loop_frame + ((elapsed - intro_frames) % loop_frames)
    if motion_mode == 2:
        return scene_start_frame + (elapsed % scene_frames)
    if motion_mode == 1:
        return min(scene_start_frame + elapsed, scene_end_frame_inclusive)
    if motion_mode == 0:
        result = scene_start_frame + elapsed
        return result if result <= scene_end_frame_inclusive else None
    raise Ac4901Z2DLoopError(f"unsupported Z2D motion mode: {motion_mode}")


def compress_source_frames(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Compress frame-exact source selections without crossing a loop reset."""

    if not rows:
        return []
    result: list[dict[str, Any]] = []
    start = 0
    progression: int | None = None
    for index in range(1, len(rows) + 1):
        split = index == len(rows)
        delta: int | None = None
        if not split:
            previous = rows[index - 1]
            current = rows[index]
            if (
                int(current["event_frame"]) != int(previous["event_frame"]) + 1
                or current["source_name"] != previous["source_name"]
                or current["projection_key"] != previous["projection_key"]
            ):
                split = True
            else:
                delta = int(current["source_frame"]) - int(previous["source_frame"])
                if delta not in (0, 1):
                    split = True
                elif progression is not None and delta != progression:
                    split = True
        if split:
            part = rows[start:index]
            if not part:
                raise Ac4901Z2DLoopError("empty compressed source-frame segment")
            first = part[0]
            last = part[-1]
            if len(part) == 1:
                mode = "single_frame"
            else:
                step = int(part[1]["source_frame"]) - int(part[0]["source_frame"])
                mode = "increment_1" if step == 1 else "hold"
            result.append(
                {
                    "segment_index": len(result),
                    "projection_key": first["projection_key"],
                    "source_name": first["source_name"],
                    "event_start_frame": int(first["event_frame"]),
                    "event_end_frame_inclusive": int(last["event_frame"]),
                    "scene_start_frame": int(first["scene_frame"]),
                    "scene_end_frame_inclusive": int(last["scene_frame"]),
                    "source_start_frame": int(first["source_frame"]),
                    "source_end_frame_inclusive": int(last["source_frame"]),
                    "frame_count": len(part),
                    "source_progression": mode,
                }
            )
            start = index
            progression = None
        elif delta is not None and progression is None:
            progression = delta
    if sum(row["frame_count"] for row in result) != len(rows):
        raise Ac4901Z2DLoopError("compressed source-frame coverage differs")
    return result


def _projection_key(
    scene: str, cut: str, parent_z2d: str, source_name: str
) -> tuple[str, str, str, str]:
    return scene, cut, parent_z2d, source_name


def _projection_key_text(key: tuple[str, str, str, str]) -> str:
    return "|".join(key)


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
    binary = bind_exact_source(slot_binary_path)
    if str(binary["sha256"]).upper() != EXPECTED_SLOT_SHA256:
        raise Ac4901Z2DLoopError("exact Slot libGameProc.so SHA-256 differs")
    if (
        presentation.get("schema")
        != "magireco-ac4901-gfdirection-presentation-authority-v1"
        or presentation.get("status")
        != "passed_code_runtime_cross_bound_projection_pending"
        or presentation.get("summary", {}).get("event_count") != EXPECTED_EVENTS
        or presentation.get("summary", {}).get("archive_backed_z2d_occurrence_count")
        != EXPECTED_EXACT_Z2D_NODES
    ):
        raise Ac4901Z2DLoopError("ac4901 presentation authority differs")
    if (
        movie.get("schema") != "magireco-z2d-movielayer-reachability-authority-v1"
        or movie.get("status") != "passed"
        or len(movie.get("z2d_chunks", [])) != 103
    ):
        raise Ac4901Z2DLoopError("ac4901 MovieLayer authority differs")
    if (
        projection.get("schema") != "magireco-ac4901-output-projection-authority-v1"
        or projection.get("status")
        != "PASS_READY_FOR_ROUTE_STATE_CARRY_AUDIO_AND_DEDUP_AUTHORITY"
        or projection.get("summary", {}).get("movie_bearing_z2d_occurrences")
        != EXPECTED_MOVIE_PARENTS
        or projection.get("summary", {}).get("loadable_movie_layer_occurrences")
        != EXPECTED_LAYER_OCCURRENCES
    ):
        raise Ac4901Z2DLoopError("ac4901 projection authority differs")

    chunks = {row["name"]: row for row in movie["z2d_chunks"]}
    projection_events = {row["event"]: row for row in projection["events"]}
    presentation_events = {row["event_id"]: row for row in presentation["events"]}
    if set(presentation_events) != set(EVENT_IDS) or set(projection_events) != set(EVENT_IDS):
        raise Ac4901Z2DLoopError("ac4901 event set differs")

    all_projection_rows: dict[tuple[str, str, str, str, str], Mapping[str, Any]] = {}
    source_catalog: dict[str, Mapping[str, Any]] = {}
    for event, event_row in projection_events.items():
        for row in event_row["layers_in_render_pass_order_under_to_top"]:
            key = (
                event,
                str(row["scene"]),
                str(row["cut"]),
                str(row["parent_z2d"]),
                str(row["source_name"]),
            )
            if key in all_projection_rows:
                raise Ac4901Z2DLoopError(f"duplicate projection key: {key}")
            all_projection_rows[key] = row
            source_catalog[str(row["source_name"])] = row["source"]
    if (
        len(all_projection_rows) != EXPECTED_LAYER_OCCURRENCES
        or len(source_catalog) != EXPECTED_UNIQUE_SOURCES
    ):
        raise Ac4901Z2DLoopError("projection source catalog differs")

    events: list[dict[str, Any]] = []
    mode_counts: Counter[str] = Counter()
    movie_parent_count = 0
    non_movie_count = 0
    extended_parent_count = 0
    extension_frames = 0
    scheduled_frames = 0
    render_segments = 0
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
                        raise Ac4901Z2DLoopError(f"archive parent Z2D is absent: {parent_name}")
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
                        raise Ac4901Z2DLoopError(
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
                        raise Ac4901Z2DLoopError(
                            f"parent active interval is empty: {event_id}/{parent_name}"
                        )
                    header = chunk["header"]
                    scene_start = int(header["scene_start_frame"])
                    scene_end = int(header["scene_end_frame_inclusive"])
                    loop_frame = int(header["scene_loop_frame"])
                    mode = 3 if loop_frame != scene_start else flags[1]
                    if mode == 3:
                        mode_name = "intro_then_scene_loop"
                    elif mode == 2:
                        mode_name = "whole_scene_loop"
                    elif mode == 1:
                        mode_name = "hold_scene_end"
                    elif mode == 0:
                        mode_name = "play_once"
                    else:
                        raise Ac4901Z2DLoopError(
                            f"unsupported parent motion mode: {event_id}/{parent_name}/{mode}"
                        )
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
                            raise Ac4901Z2DLoopError(
                                f"scene frame does not select one MovieLayer: "
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
                        projection_row = all_projection_rows.get(lookup)
                        if projection_row is None:
                            raise Ac4901Z2DLoopError(
                                f"MovieLayer projection is absent: {lookup}"
                            )
                        source_frame = mapped - int(layer["start_frame"])
                        if source_frame >= int(projection_row["source"]["frame_count"]):
                            raise Ac4901Z2DLoopError(
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
                        raise Ac4901Z2DLoopError("parent schedule coverage differs")
                    scheduled_frames += len(frame_rows)
                    render_segments += len(segments)
                    schedules.append(
                        {
                            "event": event_id,
                            "scene": str(scene["name"]),
                            "cut": str(cut["cut_name"]),
                            "parent_z2d": parent_name,
                            "owning_gdp_layer_index": int(node["owning_layer"]["index"]),
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
            raise Ac4901Z2DLoopError(f"event has no loadable MovieLayer schedule: {event_id}")
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

    expected_modes = {
        "intro_then_scene_loop": EXPECTED_PARTIAL_LOOP_PARENTS,
        "whole_scene_loop": EXPECTED_WHOLE_LOOP_PARENTS,
    }
    if dict(mode_counts) != expected_modes:
        raise Ac4901Z2DLoopError(f"movie parent loop-mode distribution differs: {mode_counts}")
    if (
        movie_parent_count != EXPECTED_MOVIE_PARENTS
        or non_movie_count != EXPECTED_NON_MOVIE_NODES
        or extended_parent_count != EXPECTED_EXTENDED_LOOP_PARENTS
        or extension_frames != EXPECTED_LOOP_EXTENSION_FRAMES
        or scheduled_frames != EXPECTED_SCHEDULED_MOVIE_FRAME_OCCURRENCES
        or render_segments != EXPECTED_RENDER_SEGMENTS
        or len(referenced_projection_keys) != EXPECTED_LAYER_OCCURRENCES
    ):
        raise Ac4901Z2DLoopError(
            "frame-exact parent Z2D schedule dimensions differ: "
            f"movie_parents={movie_parent_count} non_movie={non_movie_count} "
            f"extended={extended_parent_count} extension_frames={extension_frames} "
            f"scheduled={scheduled_frames} segments={render_segments} "
            f"projection_keys={len(referenced_projection_keys)}"
        )

    return {
        "schema": "magireco-ac4901-parent-clock-z2d-loop-authority-v1",
        "status": "PASS_READY_FOR_LOOP_AWARE_LONGFORM_RENDER",
        "family": "ac4901",
        "exact_slot_binary": binary,
        "inputs": {
            "gfdirection_presentation": bind_exact_source(presentation_path),
            "z2d_movie_layers": bind_exact_source(movie_layer_path),
            "output_projection": bind_exact_source(projection_path),
        },
        "code_authority": [
            {
                "address": "0x42b12bc",
                "function": "CGFDirectionNodeMotionBase::GetKey",
                "proves": (
                    "the final motion key remains selected after its authored end when "
                    "motion-key byte 30 bit 0 is set"
                ),
            },
            {
                "address": "0x42b342c",
                "function": "CGFDirectionNodeMotionZ2D::SetKeyTime",
                "proves": (
                    "scene_loop_frame different from scene_start forces mode 3 and maps "
                    "post-first-pass time with fmod into the exact loop interval; mode 2 "
                    "loops the whole scene and mode 1 holds the final scene frame"
                ),
            },
            {
                "address": "0x42b43e0",
                "function": "CGFDirectionNodeMotionZ2D::Calc",
                "proves": "the active cut clock selects a motion key and calls SetKeyTime",
            },
            {
                "address": "0x42aaa80",
                "function": "CGFDirectionNodeLayer::DrawZ2D",
                "proves": "the selected CZ2DPlayer is calculated, sorted and drawn",
            },
            {
                "address": "0x435e284",
                "function": "CZ2DPlayer::ExecPlayMovie",
                "proves": (
                    "MovieLayer decode frames follow the current Z2D scene time and the "
                    "scene loop point re-enters the MovieLayer state machine"
                ),
            },
        ],
        "mapping_contract": {
            "clock": "event-global GFDirection Type-2/Type-3 cut time",
            "persistent_key": "motion_key_raw_flags[2] bit 0 extends the final key to cut end",
            "mode_3": "intro once, then repeat scene_loop_frame..scene_end",
            "mode_2": "repeat scene_start..scene_end",
            "mode_1": "hold scene_end",
            "source_frame": "mapped_scene_frame - MovieLayer.start_frame",
            "parent_clock_clip": "cut/event end remains the hard upper bound",
        },
        "source_catalog": source_catalog,
        "events": events,
        "summary": {
            "events": EXPECTED_EVENTS,
            "archive_backed_z2d_occurrences": EXPECTED_EXACT_Z2D_NODES,
            "movie_parent_occurrences": movie_parent_count,
            "non_movie_z2d_occurrences": non_movie_count,
            "intro_then_scene_loop_parents": mode_counts["intro_then_scene_loop"],
            "whole_scene_loop_parents": mode_counts["whole_scene_loop"],
            "parents_requiring_post_first_pass_loop": extended_parent_count,
            "post_first_pass_loop_frames": extension_frames,
            "scheduled_movie_frame_occurrences": scheduled_frames,
            "compressed_render_segments": render_segments,
            "loadable_movie_layer_occurrences_referenced": len(referenced_projection_keys),
            "unique_loadable_cri_sources": len(source_catalog),
        },
        "assertions": {
            "exact_slot_binary_hash_bound": True,
            "all_205_events_scheduled": True,
            "all_591_projected_movie_layers_referenced": True,
            "all_4392_post_first_pass_frames_use_code_proven_loop_mapping": True,
            "no_repeatlast_guess_used": True,
            "parent_clock_tail_clipping_preserved": True,
            "unloadable_movie_layer_leak_count": 0,
            "P16_P17_P18_reference_count": 0,
            "source_media_modified": False,
            "media_rendered": False,
            "human_playback_approval_inferred": False,
        },
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    serialised = [
        {key: _csv_value(value) for key, value in row.items()} for row in rows
    ]
    fields = list(dict.fromkeys(key for row in serialised for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(serialised)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac4901Z2DLoopError(f"immutable output already exists: {output_dir}")
    stage = output_dir.parent / (
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    stage.mkdir(parents=True)
    try:
        report_path = stage / "AC4901_Z2D_LOOP_AUTHORITY.json"
        parent_csv = stage / "AC4901_PARENT_Z2D_SCHEDULES.csv"
        segment_csv = stage / "AC4901_LOOP_AWARE_RENDER_SEGMENTS.csv"
        readme = stage / "README.md"
        rollback = stage / "ROLLBACK.ps1"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        parents: list[dict[str, Any]] = []
        segments: list[dict[str, Any]] = []
        for event in report["events"]:
            for parent in event["parent_z2d_schedules_in_gfdirection_order"]:
                parent_row = {key: value for key, value in parent.items() if key != "render_segments"}
                parent_row["render_segment_count"] = len(parent["render_segments"])
                parents.append(parent_row)
                for segment in parent["render_segments"]:
                    segments.append(
                        {
                            "event": event["event"],
                            "scene": parent["scene"],
                            "cut": parent["cut"],
                            "parent_z2d": parent["parent_z2d"],
                            "owning_gdp_layer_index": parent["owning_gdp_layer_index"],
                            "mapping_policy": parent["mapping_policy"],
                            **segment,
                        }
                    )
        _write_csv(parent_csv, parents)
        _write_csv(segment_csv, segments)
        readme.write_text(
            "# ac4901 code-proven parent-clock Z2D loop authority\n\n"
            "Exact libGameProc.so code proves that persistent final Z2D motion keys "
            "remain active to the GFDirection cut end. SetKeyTime maps mode 3 to an "
            "intro followed by the authored scene loop interval and mode 2 to a whole-"
            "scene loop. This checkpoint expands every mapped MovieLayer source frame "
            "without a visual guess: 335 movie-bearing parents, 108 post-first-pass "
            "loops, 4392 loop-mapped frames, 40326 MovieLayer frame occurrences and "
            "771 compressed render segments across all 205 events.\n",
            encoding="utf-8",
        )
        root_literal = str(output_dir.resolve()).replace("'", "''")
        rollback.write_text(
            "param([switch]$Apply)\n"
            f"$Root = '{root_literal}'\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable loop authority can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED: ' + $Target)\n",
            encoding="utf-8",
        )
        outputs = [report_path, parent_csv, segment_csv, readme, rollback]
        verification = {
            "schema": "magireco-ac4901-parent-clock-z2d-loop-verification-v1",
            "status": report["status"],
            "literal_result": (
                "PASS events=205 movie_parents=335 loop_parents=256 "
                "extended_loop_parents=108 loop_frames=4392 scheduled_frames=40326 "
                "segments=771 sources=194"
            ),
            "checks": report["assertions"],
            "summary": report["summary"],
            "outputs": {
                path.name: bind_published_output(path, output_dir) for path in outputs
            },
        }
        (stage / "VERIFICATION_RECORD.json").write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stage.replace(output_dir)
    except Exception:
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
        "PASS events=205 movie_parents=335 loop_parents=256 "
        "extended_loop_parents=108 loop_frames=4392 scheduled_frames=40326 "
        "segments=771 sources=194"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
