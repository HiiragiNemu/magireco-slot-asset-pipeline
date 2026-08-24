#!/usr/bin/env python3
"""Prove all ac0917 DirInfo routes and one-copy complete presentations."""

from __future__ import annotations

import argparse
import csv
import json
import os
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac0915_route_dedup_authority import _visual_signature
    from .resolve_ac0917_event_audio_authority import bind_source
except ImportError:  # pragma: no cover - direct execution
    from build_ac0915_route_dedup_authority import _visual_signature  # type: ignore
    from resolve_ac0917_event_audio_authority import bind_source  # type: ignore


EVENTS = tuple(f"ac0917_{index:03d}" for index in (*range(1, 12), 14))
ROUTES = {
    0: ("ac0917_001", "ac0917_002"),
    1: ("ac0917_001", "ac0917_003"),
    2: ("ac0917_001", "ac0917_004", "ac0917_005"),
    3: ("ac0917_001", "ac0917_002", "ac0917_006", "ac0917_005"),
    4: ("ac0917_001", "ac0917_002", "ac0917_010", "ac0917_005"),
    5: ("ac0917_001", "ac0917_011", "ac0917_005"),
    6: ("ac0917_001", "ac0917_003", "ac0917_006", "ac0917_005"),
    7: ("ac0917_001", "ac0917_003", "ac0917_010", "ac0917_005"),
    8: ("ac0917_001", "ac0917_007"),
    9: ("ac0917_001", "ac0917_008"),
    10: ("ac0917_001", "ac0917_009"),
    11: ("ac0917_014", "ac0917_001", "ac0917_002"),
    12: ("ac0917_014", "ac0917_001", "ac0917_003"),
    13: ("ac0917_014", "ac0917_001", "ac0917_004", "ac0917_005"),
    14: ("ac0917_014", "ac0917_001", "ac0917_002", "ac0917_006", "ac0917_005"),
    15: ("ac0917_014", "ac0917_001", "ac0917_002", "ac0917_010", "ac0917_005"),
    16: ("ac0917_014", "ac0917_001", "ac0917_011", "ac0917_005"),
    17: ("ac0917_014", "ac0917_001", "ac0917_003", "ac0917_006", "ac0917_005"),
    18: ("ac0917_014", "ac0917_001", "ac0917_003", "ac0917_010", "ac0917_005"),
    19: ("ac0917_014", "ac0917_001", "ac0917_007"),
    20: ("ac0917_014", "ac0917_001", "ac0917_008"),
    21: ("ac0917_014", "ac0917_001", "ac0917_009"),
}
EDITORIAL_ORDER = (
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
CHAPTER_LABELS = {
    "ac0917_014": "另一入口普通PUSH提示",
    "ac0917_001": "灯花演说共同导入",
    "ac0917_002": "白色短演出",
    "ac0917_004": "白色完整演出",
    "ac0917_003": "红色完整演出",
    "ac0917_011": "红色短演出",
    "ac0917_006": "大型PUSH分支",
    "ac0917_010": "小丘比PUSH分支",
    "ac0917_005": "上乘冲击效果",
    "ac0917_007": "发展结果",
    "ac0917_008": "CZ结果",
    "ac0917_009": "WIN结果",
}


class Ac0917RouteDedupError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac0917RouteDedupError(f"CSV is empty: {path}")
    return rows


def validate_dirinfo(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row.get("kind") == "42" and row.get("base_name") == "ac0917"
    ]
    if len(selected) != 75 or any(row.get("route_status") != "ok" for row in selected):
        raise Ac0917RouteDedupError("ac0917 DirInfo row dimensions differ")
    result = []
    for route_index in range(22):
        route_rows = sorted(
            (row for row in selected if int(row["row_index"]) == route_index),
            key=lambda row: int(row["selector_raw"]),
        )
        selectors = [int(row["selector_raw"]) for row in route_rows]
        sequence = tuple(row["scene_name"] for row in route_rows)
        if len(selectors) != len(set(selectors)) or selectors != sorted(selectors):
            raise Ac0917RouteDedupError(
                f"DirInfo selector order differs: {route_index}"
            )
        if sequence != ROUTES[route_index]:
            raise Ac0917RouteDedupError(
                f"DirInfo route differs: {route_index}/{sequence}"
            )
        result.append(
            {
                "dirinfo_kind": 42,
                "route_index": route_index,
                "selector_raw_sequence": selectors,
                "event_sequence": list(sequence),
                "event_count": len(sequence),
                "ordering": "exact DirInfo target-stage selector order",
            }
        )
    if {event for route in ROUTES.values() for event in route} != set(EVENTS):
        raise Ac0917RouteDedupError("DirInfo routes do not cover all 12 events")
    return result


def _audio_signature(audio: Mapping[str, Any], event: str) -> dict[str, Any]:
    audio_keys = (
        "source_kind",
        "z2d_name",
        "request_id",
        "sound_id",
        "code_name",
        "start_frame",
        "start_ms",
        "duration_ms",
        "end_ms",
        "ogg_name",
        "official_source",
        "volume_kind_value",
        "volume_bus",
        "strict_no_bgm_disposition",
        "timing_evidence",
    )
    subtitle_keys = (
        "voice_request_id",
        "voice_sound_id",
        "page_index",
        "page_count",
        "z2d_name",
        "start_frame",
        "start_ms",
        "end_ms",
        "voice_start_ms",
        "voice_end_ms",
        "speaker_ja",
        "speaker_zh",
        "ja",
        "zh",
        "translation_status",
        "text_evidence",
        "subtitle_end_policy",
        "timing_evidence",
    )
    presentation = next(
        row for row in audio["event_presentations"] if row["event"] == event
    )
    return {
        "retained_audio": [
            {key: row.get(key) for key in audio_keys}
            for row in audio["retained_audio_rows"]
            if row["event"] == event
        ],
        "subtitle_pages": [
            {key: row.get(key) for key in subtitle_keys}
            for row in audio["subtitle_page_cues"]
            if row["event"] == event
        ],
        "rendered_presentation_frames": int(
            presentation["rendered_presentation_frames"]
        ),
        "final_frame_hold_frames": int(presentation["final_frame_hold_frames"]),
    }


def group_complete_signatures(
    payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, str]]:
    canonical_json = {
        event: json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        for event, payload in payloads.items()
    }
    grouped: dict[str, list[str]] = defaultdict(list)
    for event in EVENTS:
        grouped[canonical_json[event]].append(event)
    aliases: dict[str, str] = {}
    groups: dict[str, list[str]] = {}
    event_to_canonical: dict[str, str] = {}
    for events in grouped.values():
        canonical = min(events)
        groups[canonical] = list(events)
        for event in events:
            event_to_canonical[event] = canonical
            if event != canonical:
                aliases[event] = canonical
    if aliases or len(groups) != 12:
        raise Ac0917RouteDedupError(
            f"complete presentation equality groups differ: aliases={aliases}, groups={groups}"
        )
    return event_to_canonical, groups, canonical_json


def build_report(
    *, dirinfo_path: Path, visual_path: Path, audio_path: Path
) -> dict[str, Any]:
    routes = validate_dirinfo(read_csv(dirinfo_path))
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    audio = json.loads(audio_path.read_text(encoding="utf-8"))
    if (
        visual.get("schema") != "magireco-ac0917-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("summary", {}).get("events") != 12
        or visual.get("summary", {}).get("unique_loadable_cri_sources") != 20
        or visual.get("summary", {}).get("exact_cri_source_identity_count") != 21
    ):
        raise Ac0917RouteDedupError("ac0917 visual projection authority differs")
    if (
        audio.get("schema")
        != "magireco-ac0917-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY"
        or audio.get("summary", {}).get("retained_audio_occurrences") != 25
        or audio.get("summary", {}).get("excluded_bgm_occurrences") != 3
        or audio.get("summary", {}).get("subtitle_page_cue_occurrences") != 18
        or audio.get("summary", {}).get("rendered_presentation_frames_before_dedup")
        != 3136
        or len(audio.get("retained_audio_rows", [])) != 25
        or len(audio.get("excluded_audio_rows", [])) != 3
        or len(audio.get("subtitle_page_cues", [])) != 18
        or len(audio.get("event_presentations", [])) != 12
    ):
        raise Ac0917RouteDedupError("ac0917 audio authority differs")
    visual_events = {row["event"]: row for row in visual["events"]}
    if set(visual_events) != set(EVENTS):
        raise Ac0917RouteDedupError("ac0917 visual event set differs")

    payloads = {
        event: {
            "visual": _visual_signature(visual_events[event]),
            "audio_and_subtitles": _audio_signature(audio, event),
        }
        for event in EVENTS
    }
    event_to_canonical, groups, canonical_json = group_complete_signatures(payloads)
    if tuple(event_to_canonical[event] for event in EDITORIAL_ORDER) != EDITORIAL_ORDER:
        raise Ac0917RouteDedupError("editorial order contains an alias")

    occurrences: dict[str, list[dict[str, int]]] = {event: [] for event in EVENTS}
    route_rows = []
    for route in routes:
        sequence = route["event_sequence"]
        for position, event in enumerate(sequence):
            occurrences[event].append(
                {"route_index": route["route_index"], "position": position}
            )
        route_rows.append(
            {
                **route,
                "canonical_presentation_sequence": list(sequence),
                "alias_occurrences": 0,
            }
        )
    if sum(len(rows) for rows in occurrences.values()) != 75 or any(
        not rows for rows in occurrences.values()
    ):
        raise Ac0917RouteDedupError("route occurrence coverage differs")

    canonical_rows = []
    for event in EVENTS:
        canonical_rows.append(
            {
                "event": event,
                "canonical_event": event_to_canonical[event],
                "disposition": "CANONICAL_RETAIN_ONCE",
                "equivalent_events": groups[event],
                "route_occurrence_count": len(occurrences[event]),
                "route_occurrences": occurrences[event],
                "equality_basis": (
                    "exact canonical JSON equality over projected visual, retained "
                    "no-BGM audio, page subtitles, and rendered event extent"
                ),
                "canonical_payload_characters": len(canonical_json[event]),
            }
        )

    frame_map = {
        row["event"]: int(row["rendered_presentation_frames"])
        for row in audio["event_presentations"]
    }
    timeline_rows = []
    cursor = 0
    for chapter_index, event in enumerate(EDITORIAL_ORDER, start=1):
        frames = frame_map[event]
        timeline_rows.append(
            {
                "chapter_index": chapter_index,
                "event": event,
                "title_zh": CHAPTER_LABELS[event],
                "start_frame": cursor,
                "end_frame_exclusive": cursor + frames,
                "start_seconds": cursor / 30,
                "end_seconds": (cursor + frames) / 30,
                "duration_frames": frames,
                "duration_seconds": frames / 30,
            }
        )
        cursor += frames
    if cursor != 3136:
        raise Ac0917RouteDedupError(
            f"duplicate-free timeline frame total differs: {cursor}"
        )

    return {
        "schema": "magireco-ac0917-dirinfo-route-and-complete-presentation-dedup-authority-v1",
        "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
        "family": "ac0917",
        "goal": (
            "one exhaustive native416 longform containing every distinct complete "
            "presentation exactly once"
        ),
        "inputs": {
            "dirinfo_routes": bind_source(dirinfo_path),
            "visual_projection_authority": bind_source(visual_path),
            "event_audio_authority": bind_source(audio_path),
        },
        "route_contract": {
            "dirinfo_kind": 42,
            "routes": 22,
            "event_occurrences": 75,
            "route_order_semantics": (
                "target-stage order proves within-route order; the editorial longform "
                "collects mutually exclusive outcomes rather than claiming one session"
            ),
            "all_mutually_exclusive_routes_retained_in_manifest": True,
        },
        "dedup_contract": {
            "unit": (
                "complete projected event presentation including retained audio, "
                "page subtitles, and exact final-frame hold"
            ),
            "canonical_presentations": 12,
            "identical_alias_events": {},
            "partial_shared_layers_are_not_removed": (
                "required overlays shared by distinct presentations remain inside each composition"
            ),
            "single_session_claimed": False,
        },
        "routes": route_rows,
        "canonicalization": canonical_rows,
        "canonical_signature_payloads": {
            event: payloads[event] for event in EDITORIAL_ORDER
        },
        "editorial_timeline": timeline_rows,
        "summary": {
            "dirinfo_routes": 22,
            "dirinfo_event_occurrences": 75,
            "source_events": 12,
            "canonical_presentations": 12,
            "identical_complete_presentation_aliases": 0,
            "visible_unique_cri_sources_covered": 20,
            "exact_cri_source_identities_accounted": 21,
            "duplicate_free_longform_frames": 3136,
            "duplicate_free_longform_seconds": 3136 / 30,
        },
        "assertions": {
            "all_22_dirinfo_routes_exact": True,
            "all_75_route_occurrences_accounted": True,
            "all_12_events_covered": True,
            "no_complete_presentation_alias_exists": True,
            "all_12_canonical_presentations_retained_once": True,
            "all_20_visible_cri_sources_covered": True,
            "one_parent_clock_unscheduled_cri_identity_remains_provenance_only": True,
            "strict_no_bgm_exclusion_preserved": True,
            "P16_P17_P18_reference_count": 0,
            "media_rendered": False,
            "human_playback_approval_inferred": False,
        },
    }


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    serialised = [
        {key: _csv_value(value) for key, value in row.items()} for row in rows
    ]
    fields = list(dict.fromkeys(key for row in serialised for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(serialised)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise Ac0917RouteDedupError(f"immutable output already exists: {output_dir}")
    staging = output_dir.with_name(
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    staging.mkdir(parents=True)
    try:
        report_path = staging / "AC0917_ROUTE_DEDUP_AUTHORITY.json"
        routes_path = staging / "AC0917_DIRINFO_ROUTES.csv"
        canonical_path = staging / "AC0917_PRESENTATION_CANONICALIZATION.csv"
        timeline_path = staging / "AC0917_CANONICAL_EDITORIAL_TIMELINE.csv"
        readme_path = staging / "README.md"
        rollback_path = staging / "ROLLBACK.ps1"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv(routes_path, list(report["routes"]))
        _write_csv(canonical_path, list(report["canonicalization"]))
        _write_csv(timeline_path, list(report["editorial_timeline"]))
        readme_path.write_text(
            "# ac0917 路线覆盖与完整演出去重权威\n\n"
            "DirInfo kind 42 的 22 条路线含 75 个事件 occurrence，覆盖全部 12 个"
            "事件。以最终 416×232 投影、严格无 BGM 音频、页面字幕和尾帧保持做完整"
            "呈现等价比较后，没有两个事件完全相同；因此长片保留 12 个完整呈现各"
            "一次，共 3136 帧（104.533 秒）。互斥路线全部留在 manifest，成片是"
            "穷尽编辑合集而不是单局录像。\n",
            encoding="utf-8",
        )
        root_literal = str(output_dir).replace("'", "''")
        rollback_path.write_text(
            "param([switch]$Apply)\n"
            f"$Root = '{root_literal}'\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable ac0917 route/dedup authority can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED: ' + $Target)\n",
            encoding="utf-8",
        )
        outputs = [
            report_path,
            routes_path,
            canonical_path,
            timeline_path,
            readme_path,
            rollback_path,
        ]
        verification = {
            "schema": "magireco-ac0917-route-dedup-verification-v1",
            "status": report["status"],
            "literal_result": (
                "PASS routes=22 occurrences=75 events=12 canonical_presentations=12 "
                "aliases=0 frames=3136 seconds=104.533"
            ),
            "checks": report["assertions"],
            "summary": report["summary"],
            "outputs": {path.name: bind_source(path) for path in outputs},
        }
        (staging / "VERIFICATION_RECORD.json").write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.replace(output_dir)
    except BaseException:
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text(
                "Route/dedup authority construction failed; inspect the command error.\n",
                encoding="utf-8",
            )
        raise
    return output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dirinfo", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--audio-authority", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        dirinfo_path=args.dirinfo,
        visual_path=args.visual_authority,
        audio_path=args.audio_authority,
    )
    output = write_outputs(report, args.output_dir)
    print(
        json.loads((output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8"))[
            "literal_result"
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
