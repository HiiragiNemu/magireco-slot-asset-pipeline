#!/usr/bin/env python3
"""Prove ac0915 DirInfo coverage and duplicate-free complete presentations."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

try:
    from .resolve_ac0915_event_audio_authority import bind_source
except ImportError:  # direct script execution
    from resolve_ac0915_event_audio_authority import bind_source  # type: ignore


EVENTS = tuple(f"ac0915_{index:03d}" for index in range(1, 22))
ROUTES = {
    0: ("ac0915_001", "ac0915_002", "ac0915_003"),
    1: ("ac0915_001", "ac0915_002", "ac0915_008", "ac0915_009"),
    2: ("ac0915_001", "ac0915_002", "ac0915_003", "ac0915_010", "ac0915_009"),
    3: ("ac0915_001", "ac0915_002", "ac0915_003", "ac0915_011", "ac0915_009"),
    4: ("ac0915_001", "ac0915_002", "ac0915_012"),
    5: ("ac0915_001", "ac0915_002", "ac0915_013"),
    6: ("ac0915_001", "ac0915_002", "ac0915_014"),
    7: ("ac0915_001", "ac0915_004", "ac0915_005"),
    8: ("ac0915_001", "ac0915_004", "ac0915_019", "ac0915_009"),
    9: ("ac0915_001", "ac0915_004", "ac0915_005", "ac0915_010", "ac0915_009"),
    10: ("ac0915_001", "ac0915_004", "ac0915_005", "ac0915_011", "ac0915_009"),
    11: ("ac0915_001", "ac0915_004", "ac0915_012"),
    12: ("ac0915_001", "ac0915_004", "ac0915_015"),
    13: ("ac0915_001", "ac0915_004", "ac0915_018"),
    14: ("ac0915_001", "ac0915_006", "ac0915_007"),
    15: ("ac0915_001", "ac0915_006", "ac0915_021", "ac0915_009"),
    16: ("ac0915_001", "ac0915_006", "ac0915_007", "ac0915_010", "ac0915_009"),
    17: ("ac0915_001", "ac0915_006", "ac0915_007", "ac0915_011", "ac0915_009"),
    18: ("ac0915_001", "ac0915_006", "ac0915_012"),
    19: ("ac0915_001", "ac0915_006", "ac0915_016"),
    20: ("ac0915_001", "ac0915_006", "ac0915_020"),
    21: ("ac0915_017", "ac0915_002", "ac0915_003", "ac0915_001"),
    22: ("ac0915_017", "ac0915_002", "ac0915_008", "ac0915_009", "ac0915_001"),
    23: ("ac0915_017", "ac0915_002", "ac0915_003", "ac0915_010", "ac0915_009", "ac0915_001"),
    24: ("ac0915_017", "ac0915_002", "ac0915_003", "ac0915_011", "ac0915_009", "ac0915_001"),
    25: ("ac0915_017", "ac0915_002", "ac0915_012", "ac0915_001"),
    26: ("ac0915_017", "ac0915_002", "ac0915_013", "ac0915_001"),
    27: ("ac0915_017", "ac0915_002", "ac0915_014", "ac0915_001"),
    28: ("ac0915_017", "ac0915_004", "ac0915_005", "ac0915_001"),
    29: ("ac0915_017", "ac0915_004", "ac0915_019", "ac0915_009", "ac0915_001"),
    30: ("ac0915_017", "ac0915_004", "ac0915_005", "ac0915_010", "ac0915_009", "ac0915_001"),
    31: ("ac0915_017", "ac0915_004", "ac0915_005", "ac0915_011", "ac0915_009", "ac0915_001"),
    32: ("ac0915_017", "ac0915_004", "ac0915_012", "ac0915_001"),
    33: ("ac0915_017", "ac0915_004", "ac0915_015", "ac0915_001"),
    34: ("ac0915_017", "ac0915_004", "ac0915_018", "ac0915_001"),
    35: ("ac0915_017", "ac0915_006", "ac0915_007", "ac0915_001"),
    36: ("ac0915_017", "ac0915_006", "ac0915_021", "ac0915_009", "ac0915_001"),
    37: ("ac0915_017", "ac0915_006", "ac0915_007", "ac0915_010", "ac0915_009", "ac0915_001"),
    38: ("ac0915_017", "ac0915_006", "ac0915_007", "ac0915_011", "ac0915_009", "ac0915_001"),
    39: ("ac0915_017", "ac0915_006", "ac0915_012", "ac0915_001"),
    40: ("ac0915_017", "ac0915_006", "ac0915_016", "ac0915_001"),
    41: ("ac0915_017", "ac0915_006", "ac0915_020", "ac0915_001"),
}

EXPECTED_ALIASES = {
    "ac0915_008": "ac0915_003",
    "ac0915_019": "ac0915_005",
    "ac0915_021": "ac0915_007",
}

EDITORIAL_ORDER = (
    "ac0915_001",
    "ac0915_017",
    "ac0915_002",
    "ac0915_003",
    "ac0915_013",
    "ac0915_014",
    "ac0915_004",
    "ac0915_005",
    "ac0915_015",
    "ac0915_018",
    "ac0915_006",
    "ac0915_007",
    "ac0915_016",
    "ac0915_020",
    "ac0915_010",
    "ac0915_011",
    "ac0915_012",
    "ac0915_009",
)

CHAPTER_LABELS = {
    "ac0915_001": "Magius共通导入",
    "ac0915_017": "另一入口PUSH提示",
    "ac0915_002": "柊音梦路线导入",
    "ac0915_003": "柊音梦告知",
    "ac0915_013": "柊音梦WIN",
    "ac0915_014": "柊音梦南岛特别画面",
    "ac0915_004": "里见灯花路线导入",
    "ac0915_005": "里见灯花告知",
    "ac0915_015": "里见灯花WIN",
    "ac0915_018": "里见灯花南岛特别画面",
    "ac0915_006": "阿莉娜路线导入",
    "ac0915_007": "阿莉娜告知",
    "ac0915_016": "阿莉娜WIN",
    "ac0915_020": "阿莉娜南岛特别画面",
    "ac0915_010": "大型PUSH提示",
    "ac0915_011": "小丘比PUSH提示",
    "ac0915_012": "发展快门",
    "ac0915_009": "上乘冲击计数画面",
}


class Ac0915RouteDedupError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac0915RouteDedupError(f"CSV is empty: {path}")
    return rows


def validate_dirinfo(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("kind") == "40" and row.get("base_name") == "ac0915"]
    if len(selected) != 177 or any(row.get("route_status") != "ok" for row in selected):
        raise Ac0915RouteDedupError("ac0915 DirInfo row dimensions differ")
    result = []
    for route_index in range(42):
        route_rows = sorted(
            (row for row in selected if int(row["row_index"]) == route_index),
            key=lambda row: int(row["selector_raw"]),
        )
        selectors = [int(row["selector_raw"]) for row in route_rows]
        sequence = tuple(row["scene_name"] for row in route_rows)
        if len(selectors) != len(set(selectors)) or selectors != sorted(selectors):
            raise Ac0915RouteDedupError(f"DirInfo selector order differs: {route_index}")
        if sequence != ROUTES[route_index]:
            raise Ac0915RouteDedupError(f"DirInfo route differs: {route_index}/{sequence}")
        result.append(
            {
                "dirinfo_kind": 40,
                "route_index": route_index,
                "selector_raw_sequence": selectors,
                "event_sequence": list(sequence),
                "event_count": len(sequence),
                "ordering": "exact DirInfo target-stage selector order",
            }
        )
    if {event for route in ROUTES.values() for event in route} != set(EVENTS):
        raise Ac0915RouteDedupError("DirInfo routes do not cover all 21 events")
    return result


def _visual_signature(event: Mapping[str, Any]) -> dict[str, Any]:
    layer_keys = (
        "parent_z2d",
        "parent_composition_order",
        "owning_gdp_layer_index",
        "authored_tag_index",
        "authored_blend_enum",
        "effective_renderer_state",
        "source_name",
        "event_start_frame",
        "event_end_frame_inclusive",
        "authored_frame_count",
        "runtime_load_disposition",
        "source",
        "frame_policy",
        "virtual_layer_rect_ltrb",
        "physical_viewport_crop_ltrb",
        "output_rect_xywh",
        "runtime_authored_source_to_layer_scale",
        "effective_source_to_output_scale",
        "runtime_authored_component_scaling",
        "renderer_contract",
    )
    node_keys = (
        "node",
        "event_global_start_frame",
        "event_global_end_frame_inclusive",
        "owning_gdp_layer_index",
        "disposition",
    )
    return {
        "presentation_frame_count": int(event["presentation_frame_count"]),
        "output_canvas": event["output_canvas"],
        "projection": event["projection"],
        "layers_in_exact_render_order": [
            {key: row.get(key) for key in layer_keys} for row in event["layers_in_render_pass_order_under_to_top"]
        ],
        "non_movie_text_nodes": [
            {key: row.get(key) for key in node_keys} for row in event["non_movie_text_z2d_nodes"]
        ],
        "runtime_symbolic_nodes": [
            {key: row.get(key) for key in node_keys} for row in event["runtime_symbolic_nodes"]
        ],
    }


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
        "z2d_name",
        "voice_request_id",
        "start_frame",
        "start_ms",
        "voice_end_ms",
        "parent_host_end_frame_inclusive",
        "parent_host_end_ms",
        "end_ms",
        "speaker_ja",
        "speaker_zh",
        "ja",
        "zh",
        "translation_status",
        "text_evidence",
        "subtitle_end_policy",
        "timing_evidence",
    )
    return {
        "retained_audio": [
            {key: row.get(key) for key in audio_keys}
            for row in audio["retained_audio_rows"]
            if row["event"] == event
        ],
        "subtitles": [
            {key: row.get(key) for key in subtitle_keys}
            for row in audio["subtitle_cues"]
            if row["event"] == event
        ],
    }


def group_complete_signatures(
    payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, str]]:
    canonical_json = {
        event: json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for event, payload in payloads.items()
    }
    grouped: dict[str, list[str]] = defaultdict(list)
    for event in EVENTS:
        grouped[canonical_json[event]].append(event)
    aliases: dict[str, str] = {}
    groups: dict[str, list[str]] = {}
    event_to_canonical: dict[str, str] = {}
    for signature, events in grouped.items():
        canonical = min(events)
        groups[canonical] = list(events)
        for event in events:
            event_to_canonical[event] = canonical
            if event != canonical:
                aliases[event] = canonical
    if aliases != EXPECTED_ALIASES or len(groups) != 18:
        raise Ac0915RouteDedupError(
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
        visual.get("schema") != "magireco-ac0915-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("summary", {}).get("events") != 21
        or visual.get("summary", {}).get("unique_loadable_cri_sources") != 42
    ):
        raise Ac0915RouteDedupError("ac0915 visual projection authority differs")
    if (
        audio.get("schema")
        != "magireco-ac0915-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY"
        or audio.get("summary", {}).get("retained_audio_occurrences") != 40
        or audio.get("summary", {}).get("excluded_bgm_occurrences") != 1
        or audio.get("summary", {}).get("subtitle_cue_occurrences") != 18
    ):
        raise Ac0915RouteDedupError("ac0915 audio authority differs")
    visual_events = {row["event"]: row for row in visual["events"]}
    if set(visual_events) != set(EVENTS):
        raise Ac0915RouteDedupError("ac0915 visual event set differs")

    payloads = {
        event: {
            "visual": _visual_signature(visual_events[event]),
            "audio_and_subtitles": _audio_signature(audio, event),
        }
        for event in EVENTS
    }
    event_to_canonical, groups, canonical_json = group_complete_signatures(payloads)
    if tuple(event_to_canonical[event] for event in EDITORIAL_ORDER) != EDITORIAL_ORDER:
        raise Ac0915RouteDedupError("editorial order contains an alias")

    occurrences: dict[str, list[dict[str, int]]] = {event: [] for event in EVENTS}
    route_rows = []
    for route in routes:
        sequence = route["event_sequence"]
        canonical_sequence = [event_to_canonical[event] for event in sequence]
        for position, event in enumerate(sequence):
            occurrences[event].append({"route_index": route["route_index"], "position": position})
        route_rows.append(
            {
                **route,
                "canonical_presentation_sequence": canonical_sequence,
                "alias_occurrences": sum(event in EXPECTED_ALIASES for event in sequence),
            }
        )
    if sum(len(rows) for rows in occurrences.values()) != 177 or any(not rows for rows in occurrences.values()):
        raise Ac0915RouteDedupError("route occurrence coverage differs")

    canonical_rows = []
    for event in EVENTS:
        canonical = event_to_canonical[event]
        canonical_rows.append(
            {
                "event": event,
                "canonical_event": canonical,
                "disposition": "CANONICAL_RETAIN_ONCE" if event == canonical else "IDENTICAL_COMPLETE_PRESENTATION_ALIAS",
                "equivalent_events": groups[canonical],
                "route_occurrence_count": len(occurrences[event]),
                "route_occurrences": occurrences[event],
                "equality_basis": "exact canonical JSON equality over projected visual, retained no-BGM audio, and JA/ZH cue timeline",
                "canonical_payload_characters": len(canonical_json[event]),
            }
        )

    frame_map = {row["event"]: int(row["presentation_frames"]) for row in audio["event_presentations"]}
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
    if cursor != 3933:
        raise Ac0915RouteDedupError(f"duplicate-free timeline frame total differs: {cursor}")

    return {
        "schema": "magireco-ac0915-dirinfo-route-and-complete-presentation-dedup-authority-v1",
        "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
        "family": "ac0915",
        "goal": "one exhaustive native416 longform containing every distinct complete presentation exactly once",
        "inputs": {
            "dirinfo_routes": bind_source(dirinfo_path),
            "visual_projection_authority": bind_source(visual_path),
            "event_audio_authority": bind_source(audio_path),
        },
        "route_contract": {
            "dirinfo_kind": 40,
            "routes": 42,
            "event_occurrences": 177,
            "route_order_semantics": "target-stage order only; no fixed inter-event wall-clock gap claimed",
            "all_mutually_exclusive_routes_retained_in_manifest": True,
        },
        "dedup_contract": {
            "unit": "complete projected event presentation including retained audio and JA/ZH cue timeline",
            "canonical_presentations": 18,
            "identical_alias_events": EXPECTED_ALIASES,
            "partial_shared_layers_are_not_removed": (
                "required overlays shared by distinct presentations remain inside each composition"
            ),
            "single_session_claimed": False,
        },
        "routes": route_rows,
        "canonicalization": canonical_rows,
        "canonical_signature_payloads": {event: payloads[event] for event in EDITORIAL_ORDER},
        "editorial_timeline": timeline_rows,
        "summary": {
            "dirinfo_routes": 42,
            "dirinfo_event_occurrences": 177,
            "source_events": 21,
            "canonical_presentations": 18,
            "identical_complete_presentation_aliases": 3,
            "unique_loadable_cri_sources_covered": 42,
            "duplicate_free_longform_frames": 3933,
            "duplicate_free_longform_seconds": 131.1,
        },
        "assertions": {
            "all_42_dirinfo_routes_exact": True,
            "all_177_route_occurrences_accounted": True,
            "all_21_events_covered": True,
            "only_three_complete_presentation_aliases_exist": True,
            "ac0915_008_equals_003_complete_av_subtitle": True,
            "ac0915_019_equals_005_complete_av_subtitle": True,
            "ac0915_021_equals_007_complete_av_subtitle": True,
            "all_18_canonical_presentations_retained_once": True,
            "all_42_loadable_cri_sources_covered": True,
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
    serialised = [{key: _csv_value(value) for key, value in row.items()} for row in rows]
    fields = list(dict.fromkeys(key for row in serialised for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(serialised)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac0915RouteDedupError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC0915_ROUTE_DEDUP_AUTHORITY.json"
    routes_path = output_dir / "AC0915_DIRINFO_ROUTES.csv"
    canonical_path = output_dir / "AC0915_PRESENTATION_CANONICALIZATION.csv"
    timeline_path = output_dir / "AC0915_CANONICAL_EDITORIAL_TIMELINE.csv"
    readme_path = output_dir / "README.md"
    rollback_path = output_dir / "ROLLBACK.ps1"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(routes_path, list(report["routes"]))
    _write_csv(canonical_path, list(report["canonicalization"]))
    _write_csv(timeline_path, list(report["editorial_timeline"]))
    readme_path.write_text(
        "# ac0915 route coverage and complete-presentation dedup authority\n\n"
        "DirInfo kind 40 contains 42 exact routes and 177 event occurrences covering all 21 events. "
        "Code-level canonical equality over projected visuals, retained no-BGM audio, and JA/ZH cue "
        "timelines proves only three complete aliases: 008=003, 019=005, and 021=007. The render "
        "input therefore retains 18 complete presentations once, totaling 3933 frames (131.100 s). "
        "Required shared overlay layers remain in every distinct composition.\n",
        encoding="utf-8",
    )
    root_literal = str(output_dir.resolve()).replace("'", "''")
    rollback_path.write_text(
        "param([switch]$Apply)\n"
        f"$Root = '{root_literal}'\n"
        "if (-not $Apply) {\n"
        "  Write-Output 'ROLLBACK_VALIDATED: immutable route/dedup authority can be disabled by same-volume rename; source media is untouched.'\n"
        "  exit 0\n"
        "}\n"
        "$Parent = Split-Path -Parent $Root\n"
        "$Leaf = Split-Path -Leaf $Root\n"
        "$Target = Join-Path $Parent ($Leaf + '.disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))\n"
        "Move-Item -LiteralPath $Root -Destination $Target\n"
        "Write-Output ('ROLLBACK_APPLIED: ' + $Target)\n",
        encoding="utf-8",
    )
    outputs = [report_path, routes_path, canonical_path, timeline_path, readme_path, rollback_path]
    verification_path.write_text(
        json.dumps(
            {
                "schema": "magireco-ac0915-route-dedup-verification-v1",
                "status": report["status"],
                "literal_result": (
                    "PASS routes=42 occurrences=177 events=21 canonical_presentations=18 "
                    "aliases=3 frames=3933 seconds=131.100"
                ),
                "checks": report["assertions"],
                "summary": report["summary"],
                "outputs": {path.name: bind_source(path) for path in outputs},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dirinfo", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--audio-authority", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        dirinfo_path=args.dirinfo,
        visual_path=args.visual_authority,
        audio_path=args.audio_authority,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS routes=42 occurrences=177 events=21 canonical_presentations=18 "
        "aliases=3 frames=3933 seconds=131.100"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
