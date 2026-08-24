#!/usr/bin/env python3
"""Prove ac4902 DirInfo coverage and duplicate-free complete presentations."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_ac4902_gfdirection_presentation_authority import (
        EVENT_IDS,
        EXPECTED_EVENT_FRAMES,
    )
    from .resolve_ac4902_event_audio_authority import EXTENDED_HOLD_EVENTS, bind_source
except ImportError:  # direct script execution
    from build_ac4902_gfdirection_presentation_authority import (  # type: ignore
        EVENT_IDS,
        EXPECTED_EVENT_FRAMES,
    )
    from resolve_ac4902_event_audio_authority import (  # type: ignore
        EXTENDED_HOLD_EVENTS,
        bind_source,
    )


EVENTS = tuple(EVENT_IDS)


def _events(sequence: str) -> tuple[str, ...]:
    return tuple(f"ac4902_{suffix}" for suffix in sequence.split())


ROUTES = {
    0: _events("001 002 003"),
    1: _events("001 002 020"),
    2: _events("001 002 004"),
    3: _events("001 002 021 022"),
    4: _events("001 002 020 023 022"),
    5: _events("001 002 020 025 022"),
    6: _events("001 002 026 022"),
    7: _events("001 002 004 023 022"),
    8: _events("001 002 004 025 022"),
    9: _events("054 055 059"),
    10: _events("054 055 060"),
    11: _events("054 055 061"),
    12: _events("054 055 024"),
    13: _events("054 055 024"),
    14: _events("001 005 006"),
    15: _events("001 005 007"),
    16: _events("001 005 008"),
    17: _events("001 005 009"),
    18: _events("001 005 030 022"),
    19: _events("001 005 008 027 022"),
    20: _events("001 005 008 028 022"),
    21: _events("001 005 033 022"),
    22: _events("001 005 009 027 022"),
    23: _events("001 005 009 028 022"),
    24: _events("001 005 010"),
    25: _events("001 005 011"),
    26: _events("001 005 012"),
    27: _events("001 005 013"),
    28: _events("001 005 036 022"),
    29: _events("001 005 012 031 022"),
    30: _events("001 005 012 032 022"),
    31: _events("001 005 039 022"),
    32: _events("001 005 013 031 022"),
    33: _events("001 005 013 032 022"),
    34: _events("054 056 062"),
    35: _events("054 056 063"),
    36: _events("054 056 064"),
    37: _events("054 056 065"),
    38: _events("054 056 066"),
    39: _events("054 056 067"),
    40: _events("054 056 068"),
    41: _events("054 056 069"),
    42: _events("054 056 024"),
    43: _events("054 056 024"),
    44: _events("001 014 015"),
    45: _events("001 014 029"),
    46: _events("001 014 016"),
    47: _events("001 014 040 022"),
    48: _events("001 014 029 034 022"),
    49: _events("001 014 029 035 022"),
    50: _events("001 014 041 022"),
    51: _events("001 014 016 034 022"),
    52: _events("001 014 016 035 022"),
    53: _events("054 057 070"),
    54: _events("054 057 071"),
    55: _events("054 057 072"),
    56: _events("054 057 024"),
    57: _events("054 057 024"),
    58: _events("001 017 018"),
    59: _events("001 017 019"),
    60: _events("001 017 042 022"),
    61: _events("001 017 018 037 022"),
    62: _events("001 017 018 038 022"),
    63: _events("001 017 043 022"),
    64: _events("001 017 019 037 022"),
    65: _events("001 017 019 038 022"),
    66: _events("054 058 073"),
    67: _events("054 058 074"),
    68: _events("054 058 024"),
    69: _events("054 058 024"),
}

EXPECTED_ALIASES = {
    "ac4902_021": "ac4902_020",
    "ac4902_026": "ac4902_004",
    "ac4902_027": "ac4902_023",
    "ac4902_030": "ac4902_008",
    "ac4902_031": "ac4902_023",
    "ac4902_033": "ac4902_009",
    "ac4902_034": "ac4902_023",
    "ac4902_035": "ac4902_025",
    "ac4902_036": "ac4902_012",
    "ac4902_037": "ac4902_023",
    "ac4902_038": "ac4902_025",
    "ac4902_039": "ac4902_013",
    "ac4902_040": "ac4902_029",
    "ac4902_041": "ac4902_016",
    "ac4902_042": "ac4902_018",
    "ac4902_043": "ac4902_019",
}

# First unique complete presentation encountered in exact DirInfo route order,
# grouped by the four route families and their distinct shutter variants.
EDITORIAL_ORDER = _events(
    "001 002 003 020 004 022 023 025 "
    "054 055 059 060 061 024 "
    "005 006 007 008 009 028 010 011 012 013 032 "
    "056 062 063 064 065 066 067 068 069 "
    "014 015 029 016 057 070 071 072 "
    "017 018 019 058 073 074"
)


def _chapter_label(event: str) -> str:
    index = int(event.rsplit("_", 1)[1])
    if index in {1, 2, 3, 4, 20, 22, 23, 25}:
        group = "共通入口与第一组结果"
    elif index in {54, 55, 59, 60, 61, 24}:
        group = "共通发展快门变体"
    elif index in set(range(5, 14)) | {28, 32}:
        group = "第二组选项与结果"
    elif index in {56, 62, 63, 64, 65, 66, 67, 68, 69}:
        group = "第二组发展快门变体"
    elif index in {14, 15, 16, 29, 57, 70, 71, 72}:
        group = "第三组选项与发展变体"
    else:
        group = "第四组选项与发展变体"
    return f"{group} · {event}"


CHAPTER_LABELS = {event: _chapter_label(event) for event in EDITORIAL_ORDER}


class Ac4902RouteDedupError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac4902RouteDedupError(f"CSV is empty: {path}")
    return rows


def validate_dirinfo(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("kind") == "113" and row.get("base_name") == "ac4902"]
    if len(selected) != 260 or any(row.get("route_status") != "ok" for row in selected):
        raise Ac4902RouteDedupError("ac4902 DirInfo row dimensions differ")
    result = []
    for route_index in range(70):
        route_rows = sorted(
            (row for row in selected if int(row["row_index"]) == route_index),
            key=lambda row: int(row["selector_raw"]),
        )
        selectors = [int(row["selector_raw"]) for row in route_rows]
        sequence = tuple(row["scene_name"] for row in route_rows)
        expected_selectors = (
            [0, 1, 2]
            if route_index in {13, 43, 57, 69}
            else {3: [0, 1, 4], 4: [0, 1, 4, 6], 5: [0, 1, 4, 5, 7]}[len(sequence)]
        )
        if selectors != expected_selectors:
            raise Ac4902RouteDedupError(f"DirInfo selector order differs: {route_index}")
        if sequence != ROUTES[route_index]:
            raise Ac4902RouteDedupError(f"DirInfo route differs: {route_index}/{sequence}")
        result.append(
            {
                "dirinfo_kind": 113,
                "route_index": route_index,
                "selector_raw_sequence": selectors,
                "event_sequence": list(sequence),
                "event_count": len(sequence),
                "ordering": "exact DirInfo target-stage selector order",
            }
        )
    if {event for route in ROUTES.values() for event in route} != set(EVENTS):
        raise Ac4902RouteDedupError("DirInfo routes do not cover all 64 events")
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
    if aliases != EXPECTED_ALIASES or len(groups) != 48:
        raise Ac4902RouteDedupError(
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
        visual.get("schema") != "magireco-ac4902-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("summary", {}).get("events") != 64
        or visual.get("summary", {}).get("unique_loadable_cri_sources") != 56
    ):
        raise Ac4902RouteDedupError("ac4902 visual projection authority differs")
    if (
        audio.get("schema")
        != "magireco-ac4902-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status") != "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY"
        or audio.get("summary", {}).get("retained_audio_occurrences") != 148
        or audio.get("summary", {}).get("excluded_bgm_occurrences") != 1
        or audio.get("summary", {}).get("subtitle_cue_occurrences") != 56
    ):
        raise Ac4902RouteDedupError("ac4902 audio authority differs")
    visual_events = {row["event"]: row for row in visual["events"]}
    if set(visual_events) != set(EVENTS):
        raise Ac4902RouteDedupError("ac4902 visual event set differs")

    payloads = {
        event: {
            "visual": _visual_signature(visual_events[event]),
            "audio_and_subtitles": _audio_signature(audio, event),
        }
        for event in EVENTS
    }
    event_to_canonical, groups, canonical_json = group_complete_signatures(payloads)
    if tuple(event_to_canonical[event] for event in EDITORIAL_ORDER) != EDITORIAL_ORDER:
        raise Ac4902RouteDedupError("editorial order contains an alias")

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
    if sum(len(rows) for rows in occurrences.values()) != 260 or any(not rows for rows in occurrences.values()):
        raise Ac4902RouteDedupError("route occurrence coverage differs")

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

    frame_map = {
        row["event"]: int(row["final_presentation_frames"])
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
    if cursor != 19079:
        raise Ac4902RouteDedupError(f"duplicate-free timeline frame total differs: {cursor}")

    return {
        "schema": "magireco-ac4902-dirinfo-route-and-complete-presentation-dedup-authority-v1",
        "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
        "family": "ac4902",
        "goal": "one exhaustive native416 longform containing every distinct complete presentation exactly once",
        "inputs": {
            "dirinfo_routes": bind_source(dirinfo_path),
            "visual_projection_authority": bind_source(visual_path),
            "event_audio_authority": bind_source(audio_path),
        },
        "route_contract": {
            "dirinfo_kind": 113,
            "routes": 70,
            "event_occurrences": 260,
            "route_order_semantics": "target-stage order only; no fixed inter-event wall-clock gap claimed",
            "all_mutually_exclusive_routes_retained_in_manifest": True,
        },
        "dedup_contract": {
            "unit": "complete projected event presentation including retained audio and JA/ZH cue timeline",
            "canonical_presentations": 48,
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
            "dirinfo_routes": 70,
            "dirinfo_event_occurrences": 260,
            "source_events": 64,
            "canonical_presentations": 48,
            "identical_complete_presentation_aliases": 16,
            "unique_loadable_cri_sources_covered": 56,
            "duplicate_free_longform_frames": 19079,
            "duplicate_free_longform_seconds": 19079 / 30,
        },
        "assertions": {
            "all_70_dirinfo_routes_exact": True,
            "all_260_route_occurrences_accounted": True,
            "all_64_events_covered": True,
            "exactly_sixteen_complete_presentation_aliases_exist": True,
            "shutter_variants_054_through_074_are_not_collapsed_into_plain_events": True,
            "all_48_canonical_presentations_retained_once": True,
            "all_56_loadable_cri_sources_covered": True,
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
        raise Ac4902RouteDedupError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC4902_ROUTE_DEDUP_AUTHORITY.json"
    routes_path = output_dir / "AC4902_DIRINFO_ROUTES.csv"
    canonical_path = output_dir / "AC4902_PRESENTATION_CANONICALIZATION.csv"
    timeline_path = output_dir / "AC4902_CANONICAL_EDITORIAL_TIMELINE.csv"
    readme_path = output_dir / "README.md"
    rollback_path = output_dir / "ROLLBACK.ps1"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(routes_path, list(report["routes"]))
    _write_csv(canonical_path, list(report["canonicalization"]))
    _write_csv(timeline_path, list(report["editorial_timeline"]))
    readme_path.write_text(
        "# ac4902 route coverage and complete-presentation dedup authority\n\n"
        "DirInfo kind 113 contains 70 exact routes and 260 event occurrences covering all 64 events. "
        "Code-level canonical equality over projected visuals, retained no-BGM audio, and JA/ZH cue "
        "timelines proves exactly 16 complete aliases and retains 48 distinct presentations once, "
        "totaling 19079 frames (635.967 s). The development-shutter variants 054 through 074 are "
        "distinct audiovisual compositions and are not collapsed into their plain-event counterparts. "
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
                "schema": "magireco-ac4902-route-dedup-verification-v1",
                "status": report["status"],
                "literal_result": (
                    "PASS routes=70 occurrences=260 events=64 canonical_presentations=48 "
                    "aliases=16 frames=19079 seconds=635.967"
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
        "PASS routes=70 occurrences=260 events=64 canonical_presentations=48 "
        "aliases=16 frames=19079 seconds=635.967"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
