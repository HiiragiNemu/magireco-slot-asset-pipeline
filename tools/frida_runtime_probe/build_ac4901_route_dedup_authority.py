#!/usr/bin/env python3
"""Prove complete ac4901 DirInfo coverage and route-state-aware deduplication."""

from __future__ import annotations

import argparse
import csv
import json
import os
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac4901_gfdirection_presentation_authority import EVENT_IDS
    from .resolve_ac0915_event_audio_authority import bind_source
except ImportError:  # pragma: no cover - direct script execution
    from build_ac4901_gfdirection_presentation_authority import EVENT_IDS  # type: ignore
    from resolve_ac0915_event_audio_authority import bind_source  # type: ignore


EVENTS = tuple(EVENT_IDS)
EXPECTED_ALIASES = {
    "ac4901_112": "ac4901_105",
    "ac4901_232": "ac4901_105",
}
PRIOR_UNDERLAY_EVENT = "ac4901_091"
PRIOR_UNDERLAY_EVENTS = frozenset(
    f"ac4901_{index:03d}"
    for index in (
        *range(25, 31),
        *range(55, 61),
        *range(85, 91),
    )
)
EXPECTED_ROUTES = 162
EXPECTED_ROUTE_OCCURRENCES = 720
EXPECTED_CANONICAL_EVENT_PRESENTATIONS = 203
EXPECTED_EDITORIAL_UNITS = 220
EXPECTED_EDITORIAL_FRAMES = 35654


class Ac4901RouteDedupError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac4901RouteDedupError(f"CSV is empty: {path}")
    return rows


def read_route_contract(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    routes = document.get("routes", [])
    if (
        document.get("schema") != "magireco-ac4901-exact-dirinfo-route-contract-v1"
        or document.get("status") != "exact_static_dirinfo_snapshot"
        or document.get("family") != "ac4901"
        or document.get("dirinfo_kind") != 112
        or len(routes) != EXPECTED_ROUTES
        or [row.get("route_index") for row in routes] != list(range(EXPECTED_ROUTES))
        or sum(len(row.get("events", [])) for row in routes)
        != EXPECTED_ROUTE_OCCURRENCES
    ):
        raise Ac4901RouteDedupError("ac4901 route contract dimensions differ")
    return document


def validate_dirinfo(
    rows: list[dict[str, str]], route_contract: Mapping[str, Any]
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row.get("kind") == "112" and row.get("base_name") == "ac4901"
    ]
    if (
        len(selected) != EXPECTED_ROUTE_OCCURRENCES
        or any(row.get("route_status") != "ok" for row in selected)
    ):
        raise Ac4901RouteDedupError("ac4901 DirInfo row dimensions differ")
    expected = {int(row["route_index"]): row for row in route_contract["routes"]}
    result: list[dict[str, Any]] = []
    for route_index in range(EXPECTED_ROUTES):
        route_rows = sorted(
            (row for row in selected if int(row["row_index"]) == route_index),
            key=lambda row: int(row["selector_raw"]),
        )
        selectors = [int(row["selector_raw"]) for row in route_rows]
        sequence = [row["scene_name"] for row in route_rows]
        contract = expected[route_index]
        if selectors != contract["selectors"] or sequence != contract["events"]:
            raise Ac4901RouteDedupError(f"DirInfo route differs: {route_index}")
        result.append(
            {
                "dirinfo_kind": 112,
                "route_index": route_index,
                "selector_raw_sequence": selectors,
                "event_sequence": sequence,
                "event_count": len(sequence),
                "ordering": "exact DirInfo target-stage selector order",
            }
        )
    if Counter(len(row["event_sequence"]) for row in result) != {
        2: 18,
        4: 90,
        6: 54,
    }:
        raise Ac4901RouteDedupError("ac4901 route length distribution differs")
    if {event for route in result for event in route["event_sequence"]} != set(EVENTS):
        raise Ac4901RouteDedupError("DirInfo routes do not cover all 205 events")
    underlays = []
    branch_counts: Counter[str] = Counter()
    for route in result:
        sequence = route["event_sequence"]
        if len(sequence) == 6:
            if sequence[-1] != "ac4901_092" or sequence[-2] not in {
                "ac4901_091",
                "ac4901_093",
                "ac4901_094",
            }:
                raise Ac4901RouteDedupError(
                    f"button route suffix differs: {route['route_index']}"
                )
            branch_counts[sequence[-2]] += 1
            if sequence[-2] == PRIOR_UNDERLAY_EVENT:
                underlays.append(sequence[-3])
    if (
        branch_counts
        != {"ac4901_091": 18, "ac4901_093": 18, "ac4901_094": 18}
        or set(underlays) != set(PRIOR_UNDERLAY_EVENTS)
        or len(underlays) != len(PRIOR_UNDERLAY_EVENTS)
    ):
        raise Ac4901RouteDedupError("ac4901 prior-underlay route set differs")
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
        "authored_event_start_frame",
        "authored_event_end_frame_inclusive",
        "event_start_frame",
        "event_end_frame_inclusive",
        "authored_frame_count",
        "effective_frame_count",
        "runtime_load_disposition",
        "source",
        "frame_policy",
        "virtual_layer_rect_ltrb",
        "clipped_virtual_layer_rect_ltrb",
        "covers_physical_viewport",
        "physical_viewport_crop_ltrb",
        "output_rect_xywh",
        "runtime_authored_source_to_layer_scale",
        "effective_source_to_output_scale",
        "runtime_authored_component_scaling",
        "renderer_contract",
    )
    node_keys = (
        "node",
        "authored_event_global_start_frame",
        "authored_event_global_end_frame_inclusive",
        "event_global_start_frame",
        "event_global_end_frame_inclusive",
        "discarded_by_parent_clock_frames",
        "owning_gdp_layer_index",
        "disposition",
    )
    return {
        "presentation_frame_count": int(event["presentation_frame_count"]),
        "output_canvas": event["output_canvas"],
        "projection": event["projection"],
        "requires_prior_frame_underlay": bool(event["requires_prior_frame_underlay"]),
        "layers_in_exact_render_order": [
            {key: row.get(key) for key in layer_keys}
            for row in event["layers_in_render_pass_order_under_to_top"]
        ],
        "non_movie_text_nodes": [
            {key: row.get(key) for key in node_keys}
            for row in event["non_movie_text_z2d_nodes"]
        ],
        "runtime_symbolic_nodes": [
            {key: row.get(key) for key in node_keys}
            for row in event["runtime_symbolic_nodes"]
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
    presentation = next(
        row for row in audio["event_presentations"] if row["event"] == event
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
        "final_presentation_frames": int(presentation["final_presentation_frames"]),
        "tail_hold_frames": int(presentation["tail_hold_frames"]),
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
    if aliases != EXPECTED_ALIASES or len(groups) != EXPECTED_CANONICAL_EVENT_PRESENTATIONS:
        raise Ac4901RouteDedupError(
            f"complete presentation equality groups differ: aliases={aliases}"
        )
    return event_to_canonical, groups, canonical_json


def editorial_units(
    routes: Sequence[Mapping[str, Any]], event_to_canonical: Mapping[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: set[str] = set()
    units: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    for route in routes:
        sequence = list(route["event_sequence"])
        unit_sequence = []
        for position, event in enumerate(sequence):
            canonical = event_to_canonical[event]
            underlay = ""
            if event == PRIOR_UNDERLAY_EVENT:
                if position == 0 or sequence[position - 1] not in PRIOR_UNDERLAY_EVENTS:
                    raise Ac4901RouteDedupError(
                        f"prior-frame event lacks exact predecessor: {route['route_index']}"
                    )
                underlay = sequence[position - 1]
                unit_id = f"{event}@{underlay}"
            else:
                unit_id = canonical
            unit_sequence.append(unit_id)
            if unit_id not in seen:
                seen.add(unit_id)
                units.append(
                    {
                        "unit_id": unit_id,
                        "event": canonical,
                        "source_event": event,
                        "underlay_event": underlay,
                        "composition_semantics": (
                            "overlay_on_exact_predecessor_final_composed_frame"
                            if underlay
                            else "standalone_exact_complete_event_presentation"
                        ),
                        "first_route_index": int(route["route_index"]),
                        "first_route_position": position,
                    }
                )
        route_rows.append(
            {
                **route,
                "canonical_route_state_sequence": unit_sequence,
                "identical_alias_occurrences": sum(
                    event in EXPECTED_ALIASES for event in sequence
                ),
            }
        )
    underlay_units = [row for row in units if row["underlay_event"]]
    if (
        len(units) != EXPECTED_EDITORIAL_UNITS
        or len(underlay_units) != 18
        or {row["underlay_event"] for row in underlay_units}
        != set(PRIOR_UNDERLAY_EVENTS)
        or len([row for row in units if not row["underlay_event"]]) != 202
    ):
        raise Ac4901RouteDedupError("route-state editorial unit set differs")
    return units, route_rows


def _chapter_label(unit: Mapping[str, Any]) -> str:
    event = str(unit["event"])
    if unit["underlay_event"]:
        return f"普通按钮叠加 · {unit['underlay_event']}→{event}"
    suffix = int(event.rsplit("_", 1)[1])
    if suffix <= 30:
        group = "第一阶段"
    elif suffix <= 60:
        group = "第二阶段"
    elif suffix <= 90:
        group = "第三阶段"
    elif suffix <= 148:
        group = "按钮与共通结果"
    elif suffix <= 201:
        group = "发展与分歧"
    else:
        group = "结果与快门变体"
    return f"{group} · {event}"


def build_report(
    *,
    dirinfo_path: Path,
    route_contract_path: Path,
    visual_path: Path,
    audio_path: Path,
) -> dict[str, Any]:
    route_contract = read_route_contract(route_contract_path)
    routes = validate_dirinfo(read_csv(dirinfo_path), route_contract)
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    audio = json.loads(audio_path.read_text(encoding="utf-8"))
    if (
        visual.get("schema") != "magireco-ac4901-output-projection-authority-v1"
        or visual.get("status")
        != "PASS_READY_FOR_ROUTE_STATE_CARRY_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("summary", {}).get("events") != 205
        or visual.get("summary", {}).get("unique_loadable_cri_sources") != 194
        or visual.get("summary", {}).get("parent_clock_tail_clip_occurrences") != 90
    ):
        raise Ac4901RouteDedupError("ac4901 visual projection authority differs")
    if (
        audio.get("schema")
        != "magireco-ac4901-native416-event-audio-runtime-and-sound-bus-authority-v1"
        or audio.get("status")
        != "PASS_READY_FOR_ROUTE_STATE_CARRY_AND_DEDUP_AUTHORITY"
        or audio.get("summary", {}).get("retained_audio_occurrences") != 393
        or audio.get("summary", {}).get("excluded_bgm_occurrences") != 21
        or audio.get("summary", {}).get("subtitle_cue_occurrences") != 39
    ):
        raise Ac4901RouteDedupError("ac4901 audio authority differs")
    visual_events = {row["event"]: row for row in visual["events"]}
    if set(visual_events) != set(EVENTS):
        raise Ac4901RouteDedupError("ac4901 visual event set differs")
    if (
        not visual_events[PRIOR_UNDERLAY_EVENT]["requires_prior_frame_underlay"]
        or any(
            row["requires_prior_frame_underlay"]
            for event, row in visual_events.items()
            if event != PRIOR_UNDERLAY_EVENT
        )
    ):
        raise Ac4901RouteDedupError("ac4901 prior-underlay event set differs")

    payloads = {
        event: {
            "visual": _visual_signature(visual_events[event]),
            "audio_and_subtitles": _audio_signature(audio, event),
        }
        for event in EVENTS
    }
    event_to_canonical, groups, canonical_json = group_complete_signatures(payloads)
    units, route_rows = editorial_units(routes, event_to_canonical)

    occurrences: dict[str, list[dict[str, int]]] = {event: [] for event in EVENTS}
    for route in routes:
        for position, event in enumerate(route["event_sequence"]):
            occurrences[event].append(
                {"route_index": int(route["route_index"]), "position": position}
            )
    if (
        sum(len(rows) for rows in occurrences.values()) != EXPECTED_ROUTE_OCCURRENCES
        or any(not rows for rows in occurrences.values())
    ):
        raise Ac4901RouteDedupError("route occurrence coverage differs")

    canonical_rows = []
    for event in EVENTS:
        canonical = event_to_canonical[event]
        canonical_rows.append(
            {
                "event": event,
                "canonical_event": canonical,
                "disposition": (
                    "ROUTE_STATE_VARIANTS_REQUIRED"
                    if event == PRIOR_UNDERLAY_EVENT
                    else (
                        "CANONICAL_RETAIN_ONCE"
                        if event == canonical
                        else "IDENTICAL_COMPLETE_PRESENTATION_ALIAS"
                    )
                ),
                "equivalent_events": groups[canonical],
                "route_occurrence_count": len(occurrences[event]),
                "route_occurrences": occurrences[event],
                "equality_basis": (
                    "exact canonical JSON equality over parent-clock-clipped projected visual, "
                    "retained no-BGM audio, and JA/ZH cue timeline"
                ),
                "canonical_payload_characters": len(canonical_json[event]),
            }
        )

    frame_map = {
        row["event"]: int(row["final_presentation_frames"])
        for row in audio["event_presentations"]
    }
    timeline_rows = []
    cursor = 0
    for chapter_index, unit in enumerate(units, start=1):
        frames = frame_map[unit["event"]]
        timeline_rows.append(
            {
                **unit,
                "chapter_index": chapter_index,
                "title_zh": _chapter_label(unit),
                "start_frame": cursor,
                "end_frame_exclusive": cursor + frames,
                "start_seconds": cursor / 30,
                "end_seconds": (cursor + frames) / 30,
                "duration_frames": frames,
                "duration_seconds": frames / 30,
            }
        )
        cursor += frames
    if cursor != EXPECTED_EDITORIAL_FRAMES:
        raise Ac4901RouteDedupError(
            f"duplicate-free timeline frame total differs: {cursor}"
        )

    canonical_events = {row["event"] for row in units}
    unique_sources = {
        layer["source"]["official_name"]
        for event in canonical_events
        for layer in visual_events[event]["layers_in_render_pass_order_under_to_top"]
    }
    if len(unique_sources) != 194:
        raise Ac4901RouteDedupError("canonical unit source coverage differs")

    return {
        "schema": "magireco-ac4901-dirinfo-route-state-and-complete-presentation-dedup-authority-v1",
        "status": "PASS_READY_FOR_DUPLICATE_FREE_LONGFORM_RENDER",
        "family": "ac4901",
        "goal": (
            "one exhaustive native416 longform containing every distinct complete "
            "presentation and every exact prior-frame button composition once"
        ),
        "inputs": {
            "dirinfo_routes": bind_source(dirinfo_path),
            "route_contract": bind_source(route_contract_path),
            "visual_projection_authority": bind_source(visual_path),
            "event_audio_authority": bind_source(audio_path),
        },
        "route_contract": {
            "dirinfo_kind": 112,
            "routes": EXPECTED_ROUTES,
            "event_occurrences": EXPECTED_ROUTE_OCCURRENCES,
            "route_order_semantics": (
                "exact target-stage selector order; used as understandable first-seen "
                "editorial order, not claimed as one native session"
            ),
            "all_mutually_exclusive_routes_retained_in_manifest": True,
        },
        "dedup_contract": {
            "unit": (
                "complete projected event presentation including retained audio and "
                "JA/ZH cue timeline; ac4901_091 additionally includes exact predecessor "
                "final-frame state"
            ),
            "canonical_event_presentations": EXPECTED_CANONICAL_EVENT_PRESENTATIONS,
            "identical_alias_events": EXPECTED_ALIASES,
            "prior_underlay_event": PRIOR_UNDERLAY_EVENT,
            "prior_underlay_variants": sorted(PRIOR_UNDERLAY_EVENTS),
            "editorial_units": EXPECTED_EDITORIAL_UNITS,
            "shared_component_layers_are_not_independently_emitted": True,
            "single_session_claimed": False,
        },
        "routes": route_rows,
        "canonicalization": canonical_rows,
        "canonical_signature_payloads": {
            event: payloads[event]
            for event in EVENTS
            if event_to_canonical[event] == event
        },
        "editorial_timeline": timeline_rows,
        "summary": {
            "dirinfo_routes": EXPECTED_ROUTES,
            "dirinfo_event_occurrences": EXPECTED_ROUTE_OCCURRENCES,
            "source_events": 205,
            "canonical_event_presentations": EXPECTED_CANONICAL_EVENT_PRESENTATIONS,
            "identical_complete_presentation_aliases": 2,
            "route_state_underlay_variants": 18,
            "duplicate_free_editorial_units": EXPECTED_EDITORIAL_UNITS,
            "unique_loadable_cri_sources_covered": len(unique_sources),
            "duplicate_free_longform_frames": cursor,
            "duplicate_free_longform_seconds": cursor / 30,
        },
        "assertions": {
            "all_162_dirinfo_routes_exact": True,
            "all_720_route_occurrences_accounted": True,
            "all_205_events_covered": True,
            "exactly_two_complete_presentation_aliases_exist": True,
            "all_18_prior_frame_button_compositions_retained_once": True,
            "all_220_editorial_units_retained_once": True,
            "all_194_loadable_cri_sources_covered": True,
            "strict_no_bgm_exclusion_preserved": True,
            "parent_clock_tail_clipping_preserved": True,
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


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac4901RouteDedupError(f"immutable output already exists: {output_dir}")
    stage = output_dir.parent / (
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    stage.mkdir(parents=True)
    try:
        report_path = stage / "AC4901_ROUTE_DEDUP_AUTHORITY.json"
        routes_path = stage / "AC4901_DIRINFO_ROUTES.csv"
        canonical_path = stage / "AC4901_PRESENTATION_CANONICALIZATION.csv"
        timeline_path = stage / "AC4901_CANONICAL_EDITORIAL_TIMELINE.csv"
        readme_path = stage / "README.md"
        rollback_path = stage / "ROLLBACK.ps1"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv(routes_path, list(report["routes"]))
        _write_csv(canonical_path, list(report["canonicalization"]))
        _write_csv(timeline_path, list(report["editorial_timeline"]))
        readme_path.write_text(
            "# ac4901 route-state-aware complete-presentation dedup authority\n\n"
            "DirInfo kind 112 contains 162 exact routes and 720 event occurrences "
            "covering all 205 events. Parent-clock-clipped projected visuals, retained "
            "strict no-BGM audio, and JA/ZH cue timelines prove only ac4901_112 and "
            "ac4901_232 are complete aliases of ac4901_105. ac4901_091 is not a "
            "standalone clip: its normal button is composited over 18 distinct exact "
            "predecessor final frames, so all 18 route-state variants are retained. "
            "The final first-seen DirInfo editorial plan contains 220 units and 35654 "
            "frames (1188.467 s), with every exact presentation once.\n",
            encoding="utf-8",
        )
        root_literal = str(output_dir.resolve()).replace("'", "''")
        rollback_path.write_text(
            "param([switch]$Apply)\n"
            f"$Root = '{root_literal}'\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable route/dedup authority can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
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
            "schema": "magireco-ac4901-route-state-dedup-verification-v1",
            "status": report["status"],
            "literal_result": (
                "PASS routes=162 occurrences=720 events=205 canonical_events=203 "
                "aliases=2 prior_underlay_variants=18 editorial_units=220 "
                "frames=35654 seconds=1188.467"
            ),
            "checks": report["assertions"],
            "summary": report["summary"],
            "outputs": {path.name: bind_source(path) for path in outputs},
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
    parser.add_argument("--dirinfo", required=True, type=Path)
    parser.add_argument("--route-contract", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--audio-authority", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        dirinfo_path=args.dirinfo,
        route_contract_path=args.route_contract,
        visual_path=args.visual_authority,
        audio_path=args.audio_authority,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS routes=162 occurrences=720 events=205 canonical_events=203 "
        "aliases=2 prior_underlay_variants=18 editorial_units=220 "
        "frames=35654 seconds=1188.467"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
