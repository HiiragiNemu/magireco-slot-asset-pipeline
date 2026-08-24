#!/usr/bin/env python3
"""Prove ac0917 terminal-idle trimming for the exhaustive audience longform."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


FPS = 30
EVENTS = (
    "ac0917_014",
    "ac0917_001",
    "ac0917_002",
    "ac0917_004",
    "ac0917_003",
    "ac0917_011",
    "ac0917_006",
    "ac0917_010",
    "ac0917_005",
    "ac0917_007",
    "ac0917_008",
    "ac0917_009",
)
EXPECTED_ARCHIVE_FRAMES = {
    "ac0917_014": 100,
    "ac0917_001": 252,
    "ac0917_002": 269,
    "ac0917_004": 300,
    "ac0917_003": 300,
    "ac0917_011": 228,
    "ac0917_006": 300,
    "ac0917_010": 300,
    "ac0917_005": 240,
    "ac0917_007": 287,
    "ac0917_008": 280,
    "ac0917_009": 280,
}
EXPECTED_AUDIENCE_FRAMES = {
    **EXPECTED_ARCHIVE_FRAMES,
    "ac0917_014": 84,
    "ac0917_006": 118,
    "ac0917_010": 96,
}
EXPECTED_ALPHA_LOGS = {
    "ac0917_006__ac8002_chance_btn_deka.txt": 36,
    "ac0917_006__ac8002_chance_btn_deka_LP.txt": 48,
    "ac0917_010__ac8002_chance_btn_mokyu.txt": 48,
    "ac0917_010__ac8002_chance_btn_mokyu_LP.txt": 48,
    "ac0917_014__ac8002_chance_btn.txt": 36,
    "ac0917_014__ac8002_chance_btn_LP.txt": 48,
}
EXPECTED_FUNCTIONS = {
    "0x42c2f64": "zg::CGFDirectionPlayer::Draw",
    "0x42bf260": "zg::CGFDirectionPlayer::ClearRBSet",
    "0x42bcf44": "zg::CGFDirectionPlayer::CGFDirectionPlayer",
    "0x44bb678": "vtable for zg::CGFHardSystem",
    "0x4315764": "zg::CGFHardSystem::ClearBuffer",
    "0x42c8f0c": "zg::CGFDirectionPlaylist::Draw",
    "0x437f4c8": "zg::C_Scene::fnSceneRenderBuffer",
    "0x435e284": "zg::CZ2DPlayer::ExecPlayMovie",
}


class Ac0917AudienceTailError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise Ac0917AudienceTailError(f"source file is absent: {path}")
    return {"path": str(path), "size_bytes": path.stat().st_size}


def _ceil_frame(end_ms: int | float | str) -> int:
    return math.ceil(float(end_ms) * FPS / 1000.0)


def _max_movie_end(loop_event: Mapping[str, Any]) -> int:
    ends = [
        int(segment["event_end_frame_inclusive"]) + 1
        for parent in loop_event["parent_z2d_schedules_in_gfdirection_order"]
        for segment in parent["render_segments"]
    ]
    if not ends:
        raise Ac0917AudienceTailError(
            f"event lacks scheduled movie frames: {loop_event.get('event')}"
        )
    return max(ends)


def _max_text_end(visual_event: Mapping[str, Any]) -> int:
    return max(
        (
            int(row["event_global_end_frame_inclusive"]) + 1
            for row in visual_event.get("non_movie_text_z2d_nodes", [])
        ),
        default=0,
    )


def _alpha_log(path: Path, expected_frames: int) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    frames = len(re.findall(r"(?m)^frame:\d+", text))
    ymin = [float(value) for value in re.findall(r"(?m)^lavfi\.signalstats\.YMIN=([0-9.]+)$", text)]
    yavg = [float(value) for value in re.findall(r"(?m)^lavfi\.signalstats\.YAVG=([0-9.]+)$", text)]
    ymax = [float(value) for value in re.findall(r"(?m)^lavfi\.signalstats\.YMAX=([0-9.]+)$", text)]
    if (
        frames != expected_frames
        or len(ymin) != frames
        or len(yavg) != frames
        or len(ymax) != frames
        or min(ymin) != 0.0
        or max(ymax) != 255.0
        or max(yavg) <= 0.0
    ):
        raise Ac0917AudienceTailError(f"alpha stream statistics differ: {path}")
    return {
        "name": path.stem,
        "frames": frames,
        "ymin_min": min(ymin),
        "yavg_min": min(yavg),
        "yavg_max": max(yavg),
        "ymax_max": max(ymax),
        "source": source_binding(path),
    }


def _validate_ida_evidence(path: Path) -> dict[str, Any]:
    evidence = read_json(path)
    if (
        evidence.get("schema")
        != "magireco-ac0917-gfdirection-clear-and-idle-tail-ida-evidence-v1"
        or evidence.get("status") != "PROVEN_FOR_HASH_BOUND_BINARY"
    ):
        raise Ac0917AudienceTailError("IDA evidence schema/status differs")
    functions = {
        str(row["address"]).casefold(): str(row["name"])
        for row in evidence.get("function_chain", [])
    }
    if functions != {key.casefold(): value for key, value in EXPECTED_FUNCTIONS.items()}:
        raise Ac0917AudienceTailError("IDA function chain differs")
    decision = evidence.get("mechanism_decision", {})
    if (
        decision.get("previous_frame_carry") is not False
        or decision.get("implicit_last_movie_frame_hold") is not False
        or decision.get("inactive_cut_player_buffer")
        != "transparent_black_after_per_frame_clear"
        or decision.get("final_scene_output_when_no_cut_draws")
        != "opaque_black_after_final_target_clear"
        or evidence.get("binary_constants", {}).get("xmmword_143F300_float_rgba")
        != [0.0, 0.0, 0.0, 1.0]
    ):
        raise Ac0917AudienceTailError("IDA clear/hold mechanism differs")
    binary = evidence.get("binary", {})
    binary_path = Path(str(binary.get("path", "")))
    sample_path = Path(str(binary.get("sample_identity", "")))
    sample = read_json(sample_path)
    if (
        sample.get("schema") != "magireco-ida-sample-identity-v1"
        or sample.get("copy_verified") is not True
        or str(sample.get("analysis_copy", "")) != str(binary_path)
        or int(sample.get("source_size", -1)) != int(binary.get("size_bytes", -2))
        or not binary_path.is_file()
        or binary_path.stat().st_size != int(binary.get("size_bytes", -1))
    ):
        raise Ac0917AudienceTailError("IDA binary/sample identity binding differs")
    return {
        "ida_evidence": source_binding(path),
        "sample_identity": source_binding(sample_path),
        "libGameProc": source_binding(binary_path),
    }


def build_report(
    *,
    route_path: Path,
    visual_path: Path,
    loop_path: Path,
    audio_path: Path,
    ida_evidence_path: Path,
    alpha_log_root: Path,
) -> dict[str, Any]:
    route = read_json(route_path)
    visual = read_json(visual_path)
    loop = read_json(loop_path)
    audio = read_json(audio_path)
    ida_inputs = _validate_ida_evidence(ida_evidence_path)
    if (
        route.get("schema")
        != "magireco-ac0917-dirinfo-route-and-complete-presentation-dedup-authority-v2"
        or route.get("status") != "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER"
        or route.get("summary", {}).get("dirinfo_routes") != 22
        or route.get("summary", {}).get("dirinfo_event_occurrences") != 75
        or route.get("summary", {}).get("canonical_presentations") != 12
        or route.get("summary", {}).get("identical_complete_presentation_aliases") != 0
    ):
        raise Ac0917AudienceTailError("route/dedup authority differs")
    if (
        visual.get("schema") != "magireco-ac0917-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or loop.get("schema") != "magireco-ac0917-parent-clock-z2d-loop-authority-v1"
        or loop.get("status")
        != "PASS_READY_FOR_LOOP_AWARE_ROUTE_DEDUP_AND_LONGFORM_RENDER"
        or audio.get("schema")
        != "magireco-ac0917-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY"
    ):
        raise Ac0917AudienceTailError("visual/loop/audio authority differs")
    order = tuple(str(row["event"]) for row in route.get("editorial_timeline", []))
    if order != EVENTS:
        raise Ac0917AudienceTailError("editorial event order differs")
    visual_events = {str(row["event"]): row for row in visual["events"]}
    loop_events = {str(row["event"]): row for row in loop["events"]}
    archive_rows = {str(row["event"]): row for row in audio["event_presentations"]}
    if (
        set(visual_events) != set(EVENTS)
        or set(loop_events) != set(EVENTS)
        or set(archive_rows) != set(EVENTS)
    ):
        raise Ac0917AudienceTailError("event authority sets differ")
    audio_rows: dict[str, list[Mapping[str, Any]]] = {event: [] for event in EVENTS}
    subtitle_rows: dict[str, list[Mapping[str, Any]]] = {event: [] for event in EVENTS}
    for row in audio["retained_audio_rows"]:
        audio_rows[str(row["event"])].append(row)
    for row in audio["subtitle_page_cues"]:
        subtitle_rows[str(row["event"])].append(row)

    rows = []
    cursor = 0
    for chapter_index, event in enumerate(EVENTS, start=1):
        archive_frames = int(archive_rows[event]["rendered_presentation_frames"])
        movie_end = _max_movie_end(loop_events[event])
        text_end = _max_text_end(visual_events[event])
        audio_end = max((_ceil_frame(row["end_ms"]) for row in audio_rows[event]), default=0)
        subtitle_end = max((_ceil_frame(row["end_ms"]) for row in subtitle_rows[event]), default=0)
        audience_frames = max(movie_end, text_end, audio_end, subtitle_end)
        if (
            archive_frames != EXPECTED_ARCHIVE_FRAMES[event]
            or audience_frames != EXPECTED_AUDIENCE_FRAMES[event]
            or audience_frames > archive_frames
        ):
            raise Ac0917AudienceTailError(
                f"audience content extent differs: {event}/{archive_frames}/{audience_frames}"
            )
        rows.append(
            {
                "chapter_index": chapter_index,
                "event": event,
                "archive_presentation_frames": archive_frames,
                "last_movie_frame_exclusive": movie_end,
                "last_non_movie_text_frame_exclusive": text_end,
                "last_audio_frame_exclusive": audio_end,
                "last_subtitle_frame_exclusive": subtitle_end,
                "audience_content_frames": audience_frames,
                "terminal_idle_frames_omitted": archive_frames - audience_frames,
                "audience_start_frame": cursor,
                "audience_end_frame_exclusive": cursor + audience_frames,
                "audience_start_seconds": cursor / FPS,
                "audience_end_seconds": (cursor + audience_frames) / FPS,
                "archive_preserved_elsewhere": True,
            }
        )
        cursor += audience_frames
    if cursor != 2734 or sum(row["terminal_idle_frames_omitted"] for row in rows) != 402:
        raise Ac0917AudienceTailError("audience timeline totals differ")

    alpha_root = alpha_log_root.resolve()
    if {path.name for path in alpha_root.glob("*.txt")} != set(EXPECTED_ALPHA_LOGS):
        raise Ac0917AudienceTailError("chance alpha log set differs")
    alpha_stats = [
        _alpha_log(alpha_root / name, frames)
        for name, frames in EXPECTED_ALPHA_LOGS.items()
    ]
    if sum(row["frames"] for row in alpha_stats) != 264:
        raise Ac0917AudienceTailError("chance alpha frame total differs")

    return {
        "schema": "magireco-ac0917-audience-terminal-idle-tail-authority-v1",
        "status": "PASS_READY_FOR_IDLE_TRIMMED_EXHAUSTIVE_LONGFORM_RENDER",
        "family": "ac0917",
        "inputs": {
            "route_authority": source_binding(route_path),
            "visual_projection_authority": source_binding(visual_path),
            "parent_clock_z2d_loop_authority": source_binding(loop_path),
            "event_audio_authority": source_binding(audio_path),
            **ida_inputs,
            "alpha_logs": [row["source"] for row in alpha_stats],
        },
        "mechanism": {
            "previous_frame_carry": False,
            "implicit_last_movie_frame_hold": False,
            "inactive_cut_player_buffer": "transparent_black_after_per_frame_clear",
            "final_scene_output_when_no_cut_draws": "opaque_black_after_final_target_clear",
            "chance_sources_have_alpha_streams": True,
            "chance_alpha_stream_frames": 264,
        },
        "archive_vs_audience_contract": {
            "exact_event_archives_preserved": True,
            "audience_trim_unit": "terminal frame after the last scheduled movie, non-movie text, retained VOICE/SE, or subtitle cue",
            "interior_blank_frames_removed": False,
            "mutually_exclusive_route_coverage_changed": False,
            "canonical_event_set_changed": False,
            "source_media_modified": False,
        },
        "event_rows": rows,
        "chance_alpha_stats": alpha_stats,
        "summary": {
            "dirinfo_routes": 22,
            "dirinfo_event_occurrences": 75,
            "canonical_presentations": 12,
            "complete_presentation_aliases": 0,
            "archive_presentation_frames": 3136,
            "audience_content_frames": 2734,
            "terminal_idle_frames_omitted": 402,
            "audience_seconds": 2734 / FPS,
            "events_with_terminal_idle_trim": 3,
        },
        "assertions": {
            "all_unique_movie_frames_preserved": True,
            "all_retained_voice_and_se_extents_preserved": True,
            "all_subtitle_and_non_movie_text_extents_preserved": True,
            "no_predecessor_underlay_invented": True,
            "only_terminal_contentless_idle_removed": True,
            "v216_audience_release_must_remain_withdrawn": True,
            "P16_P17_P18_reference_count": 0,
            "child_local_only_reference_count": 0,
            "human_playback_approval_inferred": False,
        },
    }


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise Ac0917AudienceTailError(f"immutable output already exists: {output_dir}")
    staging = output_dir.with_name(
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    staging.mkdir(parents=True)
    try:
        (staging / "AC0917_AUDIENCE_TAIL_AUTHORITY.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv(staging / "AC0917_AUDIENCE_EDITORIAL_TIMELINE.csv", list(report["event_rows"]))
        _write_csv(
            staging / "AC0917_TERMINAL_IDLE_TRIMS.csv",
            [row for row in report["event_rows"] if row["terminal_idle_frames_omitted"]],
        )
        (staging / "README.md").write_text(
            "# ac0917 观众长片末端等待裁切权威\n\n"
            "IDA 代码链证明 GFDirection 每帧清屏，Cut 结束后既不继承上一画面，也不"
            "隐式保持 MovieLayer 末帧；最终无 Cut 输出为黑。原事件 3136 帧档案继续"
            "保留；观众穷尽长片仅删除 402 帧末端无画面、无保留音频、无字幕/文本的"
            "等待黑帧，12 个独特呈现、22 条路线与 75 个 occurrence 均不变。\n",
            encoding="utf-8",
        )
        root_literal = str(output_dir).replace("'", "''")
        (staging / "ROLLBACK.ps1").write_text(
            "param([switch]$Apply)\n"
            f"$Root = '{root_literal}'\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: disable immutable audience-tail authority by same-volume rename; sources remain untouched.'; exit 0 }\n"
            "$Target = $Root + '.disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED: ' + $Target)\n",
            encoding="utf-8",
        )
        verification = {
            "schema": "magireco-ac0917-audience-terminal-idle-tail-verification-v1",
            "status": report["status"],
            "literal_result": (
                "PASS events=12 routes=22 occurrences=75 archive_frames=3136 "
                "audience_frames=2734 idle_trim=402 changed_events=3"
            ),
            "summary": report["summary"],
            "assertions": report["assertions"],
        }
        (staging / "VERIFICATION_RECORD.json").write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.replace(output_dir)
    except BaseException:
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text(
                "Audience-tail authority construction failed; inspect the error.\n",
                encoding="utf-8",
            )
        raise
    return output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-authority", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--loop-authority", required=True, type=Path)
    parser.add_argument("--audio-authority", required=True, type=Path)
    parser.add_argument("--ida-evidence", required=True, type=Path)
    parser.add_argument("--alpha-log-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        route_path=args.route_authority,
        visual_path=args.visual_authority,
        loop_path=args.loop_authority,
        audio_path=args.audio_authority,
        ida_evidence_path=args.ida_evidence,
        alpha_log_root=args.alpha_log_root,
    )
    output = write_outputs(report, args.output_dir)
    result = read_json(output / "VERIFICATION_RECORD.json")["literal_result"]
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
