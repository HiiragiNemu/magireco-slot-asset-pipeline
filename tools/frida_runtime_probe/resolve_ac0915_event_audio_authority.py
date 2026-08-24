#!/usr/bin/env python3
"""Resolve exact ac0915 event-global audio, subtitles, and strict no-BGM buses."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping

try:
    from .resolve_ac7206_event_audio_authority import VOLUME_BUS, read_sound_divide_values
except ImportError:  # direct script execution
    from resolve_ac7206_event_audio_authority import (  # type: ignore
        VOLUME_BUS,
        read_sound_divide_values,
    )


EVENTS = tuple(f"ac0915_{index:03d}" for index in range(1, 22))

EXPECTED_EVENT_COMPONENTS = {
    "ac0915_001": {(805, 2850, 0)},
    "ac0915_002": {(806, 2851, 0)},
    "ac0915_003": {(809, 2854, 0)},
    "ac0915_004": {(807, 2852, 0)},
    "ac0915_005": {(810, 2855, 0)},
    "ac0915_006": {(808, 2853, 0)},
    "ac0915_007": {(811, 2856, 0)},
    "ac0915_008": {(809, 2854, 0)},
    "ac0915_009": set(),
    "ac0915_010": set(),
    "ac0915_011": set(),
    "ac0915_012": {
        (438, 1035, 0),
        (439, 1036, 719),
        (419, 1005, 710),
        (226, 551, 1348),
    },
    "ac0915_013": {(812, 2857, 0)},
    "ac0915_014": {(426, 1012, 0)},
    "ac0915_015": {(812, 2857, 0)},
    "ac0915_016": {(812, 2857, 0)},
    "ac0915_017": set(),
    "ac0915_018": {(426, 1012, 0)},
    "ac0915_019": {(810, 2855, 0)},
    "ac0915_020": {(426, 1012, 0)},
    "ac0915_021": {(811, 2856, 0)},
}

# host Z2D, request id, sound id, exact event-global host frame, exact bus
EXPECTED_CALLBACKS_BY_EVENT = {
    "ac0915_001": (),
    "ac0915_002": (("cap0915_magius_nem_001", 5592, 21031, 9, "VOICE"),),
    "ac0915_003": (("cap0915_magius_nem_002", 5593, 21032, 6, "VOICE"),),
    "ac0915_004": (("cap0915_magius_tou_005", 5364, 20539, 10, "VOICE"),),
    "ac0915_005": (("cap0915_magius_tou_006", 5365, 20540, 6, "VOICE"),),
    "ac0915_006": (("cap0915_magius_ari_009", 5133, 20025, 10, "VOICE"),),
    "ac0915_007": (("cap0915_magius_ari_010", 5134, 20026, 6, "VOICE"),),
    "ac0915_008": (("cap0915_magius_nem_002", 5593, 21032, 6, "VOICE"),),
    "ac0915_009": (),
    "ac0915_010": (
        ("cap5102_iro_oshite_001", 2439, 15100, 0, "VOICE"),
        ("ac8002_chance_btn_deka", 453, 1072, 0, "SE"),
    ),
    "ac0915_011": (
        ("ac8002_chance_btn_mokyu", 8209, 26401, 0, "VOICE"),
        ("ac8002_chance_btn_mokyu", 450, 1069, 0, "SE"),
    ),
    "ac0915_012": (),
    "ac0915_013": (("cap0915_magius_nem_003", 5594, 21033, 6, "VOICE"),),
    "ac0915_014": (("cap0915_magius_nem_004", 5595, 21034, 6, "VOICE"),),
    "ac0915_015": (("cap0915_magius_tou_007", 5366, 20541, 6, "VOICE"),),
    "ac0915_016": (("cap0915_magius_ari_011", 5135, 20027, 6, "VOICE"),),
    "ac0915_017": (
        ("cap5102_iro_oshite_001", 2439, 15100, 0, "VOICE"),
        ("ac8002_chance_btn_lev", 451, 1070, 0, "SE"),
    ),
    "ac0915_018": (("cap0915_magius_tou_008", 5367, 20542, 6, "VOICE"),),
    "ac0915_019": (("cap0915_magius_tou_006", 5365, 20540, 6, "VOICE"),),
    "ac0915_020": (("cap0915_magius_ari_012", 5136, 20028, 6, "VOICE"),),
    "ac0915_021": (("cap0915_magius_ari_010", 5134, 20026, 6, "VOICE"),),
}

EXPECTED_PRESENTATION_FRAMES = {
    "ac0915_001": 232,
    "ac0915_002": 179,
    "ac0915_003": 299,
    "ac0915_004": 180,
    "ac0915_005": 150,
    "ac0915_006": 178,
    "ac0915_007": 240,
    "ac0915_008": 299,
    "ac0915_009": 240,
    "ac0915_010": 84,
    "ac0915_011": 100,
    "ac0915_012": 498,
    "ac0915_013": 299,
    "ac0915_014": 260,
    "ac0915_015": 150,
    "ac0915_016": 240,
    "ac0915_017": 84,
    "ac0915_018": 260,
    "ac0915_019": 150,
    "ac0915_020": 260,
    "ac0915_021": 240,
}

CODE_AUTHORITY = (
    ("0x1445c54", "SOUND_DIVIDE_TBL", "indexes one exact volume-kind byte by sound resource id"),
    ("volume-kind 0", "setAppVolume index 0", "maps table value 0 to BGM"),
    ("volume-kind 1", "setAppVolume index 1", "maps table value 1 to SE"),
    ("volume-kind 2", "setAppVolume index 2", "maps table value 2 to VOICE"),
    (
        "v178/v179 GFDirection chain",
        "parent Type20 instance start",
        "binds each child callback frame zero to one exact event-global frame",
    ),
)


class Ac0915AudioAuthorityError(ValueError):
    pass


def bind_source(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise Ac0915AudioAuthorityError(f"source file is absent: {path}")
    return {"path": str(path), "size_bytes": path.stat().st_size}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac0915AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def _translation_map(path: Path) -> dict[int, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {int(row["request_id"]): row for row in rows}
    expected = {
        request_id
        for specs in EXPECTED_CALLBACKS_BY_EVENT.values()
        for _, request_id, _, _, bus in specs
        if bus == "VOICE"
    }
    required_fields = {
        "request_id",
        "ja",
        "zh",
        "speaker_ja",
        "speaker_zh",
        "render_ja",
        "render_zh",
        "status",
        "text_evidence",
    }
    if (
        document.get("schema") != "magireco-reviewed-story-zh-dialogue-map-v1"
        or document.get("scope") != "ac0915_exhaustive_native416_event_global_dialogue"
        or set(result) != expected
        or len(result) != len(rows)
        or any(not required_fields.issubset(row) for row in rows)
        or any(not str(row["ja"]).strip() or not str(row["zh"]).strip() for row in rows)
    ):
        raise Ac0915AudioAuthorityError("ac0915 translation map dimensions differ")
    return result


def _visual_host_intervals(
    visual: Mapping[str, Any],
) -> tuple[dict[str, dict[str, tuple[int, int]]], dict[str, int]]:
    if (
        visual.get("schema") != "magireco-ac0915-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("family") != "ac0915"
        or visual.get("frame_rate") != "30/1"
        or visual.get("output_canvas") != [416, 232]
    ):
        raise Ac0915AudioAuthorityError("ac0915 projection authority differs")
    events = visual.get("events", [])
    if [row.get("event") for row in events] != list(EVENTS):
        raise Ac0915AudioAuthorityError("ac0915 projection event order differs")
    frames = {str(row["event"]): int(row["presentation_frame_count"]) for row in events}
    if frames != EXPECTED_PRESENTATION_FRAMES:
        raise Ac0915AudioAuthorityError(f"ac0915 presentation frame totals differ: {frames}")

    result: dict[str, dict[str, tuple[int, int]]] = {}
    for event_row in events:
        event = str(event_row["event"])
        intervals: dict[str, list[tuple[int, int]]] = {}
        for row in event_row.get("non_movie_text_z2d_nodes", []):
            intervals.setdefault(str(row["node"]), []).append(
                (
                    int(row["event_global_start_frame"]),
                    int(row["event_global_end_frame_inclusive"]),
                )
            )
        for row in event_row.get("layers_in_render_pass_order_under_to_top", []):
            intervals.setdefault(str(row["parent_z2d"]), []).append(
                (int(row["event_start_frame"]), int(row["event_end_frame_inclusive"]))
            )
        result[event] = {
            name: (min(start for start, _ in rows), max(end for _, end in rows))
            for name, rows in intervals.items()
        }
        if any(start < 0 or end < start or end >= frames[event] for start, end in result[event].values()):
            raise Ac0915AudioAuthorityError(f"visual host interval escapes event: {event}")
    return result, frames


def _durable_audio_identity(
    root: Path, name: str, cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if name not in cache:
        path = (root / name).resolve()
        if not path.is_file():
            raise Ac0915AudioAuthorityError(f"durable official OGG is absent: {path}")
        cache[name] = {"ogg_name": name, "official_source": bind_source(path)}
    return dict(cache[name])


def build_report(
    *,
    binary: Path,
    visual_authority_path: Path,
    event_audio_components_path: Path,
    z2d_sound_callbacks_path: Path,
    translation_path: Path,
    durable_audio_root: Path,
) -> dict[str, Any]:
    visual = json.loads(visual_authority_path.read_text(encoding="utf-8"))
    host_intervals, presentation_frames = _visual_host_intervals(visual)
    translations = _translation_map(translation_path)

    component_source_rows = [
        row for row in read_csv(event_audio_components_path) if row.get("root") == "ac0915"
    ]
    components_by_event: dict[str, list[dict[str, str]]] = {event: [] for event in EVENTS}
    for row in component_source_rows:
        event = row.get("primary_animation", "")
        if event not in components_by_event:
            raise Ac0915AudioAuthorityError(f"unexpected ac0915 component event: {event}")
        components_by_event[event].append(row)
    observed_components = {
        event: {
            (int(row["leaf_request_id"]), int(row["leaf_sound_code"]), int(row["start_ms"]))
            for row in rows
        }
        for event, rows in components_by_event.items()
    }
    if observed_components != EXPECTED_EVENT_COMPONENTS or len(component_source_rows) != 20:
        raise Ac0915AudioAuthorityError(
            f"ac0915 event component set differs: {observed_components}"
        )

    expected_callback_pairs = {
        (host, request_id)
        for specs in EXPECTED_CALLBACKS_BY_EVENT.values()
        for host, request_id, _, _, _ in specs
    }
    expected_hosts = {host for host, _ in expected_callback_pairs}
    callback_rows = [
        row
        for row in read_csv(z2d_sound_callbacks_path)
        if row.get("z2d_name") in expected_hosts
    ]
    callbacks = {(row["z2d_name"], int(row["sound_request_id"])): row for row in callback_rows}
    if set(callbacks) != expected_callback_pairs or len(callbacks) != len(callback_rows):
        raise Ac0915AudioAuthorityError("ac0915 callback host/request set differs")

    sound_ids = {int(row["leaf_sound_code"]) for row in component_source_rows}
    sound_ids.update(int(row["sound_resource_id"]) for row in callback_rows)
    build_id, buses = read_sound_divide_values(binary, sound_ids)
    audio_cache: dict[str, dict[str, Any]] = {}
    retained_audio_rows: list[dict[str, Any]] = []
    excluded_audio_rows: list[dict[str, Any]] = []

    for event in EVENTS:
        for source in components_by_event[event]:
            request_id = int(source["leaf_request_id"])
            sound_id = int(source["leaf_sound_code"])
            start_ms = int(source["start_ms"])
            duration_ms = int(source["duration_ms"])
            bus = VOLUME_BUS[buses[sound_id]]
            if source.get("smz_matches_leaf_request") != "yes" or source.get("ogg_duration_match") != "yes":
                raise Ac0915AudioAuthorityError(
                    f"official component media binding differs: {event}/{request_id}"
                )
            row = {
                "event": event,
                "source_kind": "official_event_audio_component",
                "z2d_name": "",
                "request_id": request_id,
                "sound_id": sound_id,
                "code_name": source["leaf_code_name"],
                "start_frame": "",
                "start_ms": start_ms,
                "duration_ms": duration_ms,
                "end_ms": start_ms + duration_ms,
                **_durable_audio_identity(durable_audio_root, source["ogg_name"], audio_cache),
                "volume_kind_value": buses[sound_id],
                "volume_bus": bus,
                "timing_evidence": "official_event_audio_component_event_global_start_ms",
            }
            if bus == "BGM":
                if (event, request_id, sound_id) != ("ac0915_012", 226, 551):
                    raise Ac0915AudioAuthorityError(
                        f"unexpected ac0915 BGM component: {event}/{request_id}/{sound_id}"
                    )
                row["strict_no_bgm_disposition"] = "EXCLUDE_EXACT_BGM_BUS"
                excluded_audio_rows.append(row)
            else:
                if bus != "SE":
                    raise Ac0915AudioAuthorityError(
                        f"ac0915 event component is not SE/BGM: {event}/{request_id}/{bus}"
                    )
                row["strict_no_bgm_disposition"] = "RETAIN_VERIFIED_SE"
                retained_audio_rows.append(row)

    subtitle_cues: list[dict[str, Any]] = []
    for event in EVENTS:
        for host, request_id, expected_sound_id, expected_frame, expected_bus in EXPECTED_CALLBACKS_BY_EVENT[event]:
            callback = callbacks[(host, request_id)]
            if host not in host_intervals[event]:
                raise Ac0915AudioAuthorityError(
                    f"callback host is absent from exact visual event: {event}/{host}"
                )
            host_start, host_end = host_intervals[event][host]
            sound_id = int(callback["sound_resource_id"])
            if (
                sound_id != expected_sound_id
                or int(callback["exec_frame"]) != 0
                or callback.get("sound_request_match_count") != "1"
                or callback.get("ogg_exists") != "yes"
                or host_start != expected_frame
            ):
                raise Ac0915AudioAuthorityError(
                    f"exact callback binding differs: {event}/{host}/{request_id}"
                )
            bus = VOLUME_BUS[buses[sound_id]]
            if bus != expected_bus or bus == "BGM":
                raise Ac0915AudioAuthorityError(
                    f"callback bus differs: {event}/{host}/{request_id}/{bus}"
                )
            start_frame = host_start
            start_ms = round(start_frame * 1000 / 30)
            duration_ms = int(callback["sound_duration_ms"])
            row = {
                "event": event,
                "source_kind": "exact_parent_bound_z2d_reqSound",
                "z2d_name": host,
                "request_id": request_id,
                "sound_id": sound_id,
                "code_name": callback["sound_code_name"],
                "start_frame": start_frame,
                "start_ms": start_ms,
                "duration_ms": duration_ms,
                "end_ms": start_ms + duration_ms,
                **_durable_audio_identity(durable_audio_root, callback["ogg_name"], audio_cache),
                "volume_kind_value": buses[sound_id],
                "volume_bus": bus,
                "strict_no_bgm_disposition": f"RETAIN_VERIFIED_{bus}",
                "timing_evidence": (
                    "v178_v179_exact_event_global_parent_host_start_plus_exact_child_callback_frame_0"
                ),
            }
            retained_audio_rows.append(row)
            if bus == "VOICE":
                translation = translations[request_id]
                voice_end_ms = start_ms + duration_ms
                host_end_ms = round((host_end + 1) * 1000 / 30)
                event_end_ms = round(presentation_frames[event] * 1000 / 30)
                end_ms = min(event_end_ms, max(voice_end_ms, host_end_ms))
                if end_ms <= start_ms:
                    raise Ac0915AudioAuthorityError(
                        f"subtitle interval is empty: {event}/{request_id}"
                    )
                subtitle_cues.append(
                    {
                        "event": event,
                        "z2d_name": host,
                        "voice_request_id": request_id,
                        "start_frame": start_frame,
                        "start_ms": start_ms,
                        "voice_end_ms": voice_end_ms,
                        "parent_host_end_frame_inclusive": host_end,
                        "parent_host_end_ms": host_end_ms,
                        "end_ms": end_ms,
                        "speaker_ja": translation["speaker_ja"],
                        "speaker_zh": translation["speaker_zh"],
                        "ja": translation["render_ja"],
                        "zh": translation["render_zh"],
                        "translation_status": translation["status"],
                        "text_evidence": translation["text_evidence"],
                        "subtitle_end_policy": (
                            "max_official_voice_end_and_exact_parent_host_end_capped_by_event"
                        ),
                        "timing_evidence": row["timing_evidence"],
                    }
                )

    retained_audio_rows.sort(
        key=lambda row: (row["event"], int(row["start_ms"]), int(row["request_id"]))
    )
    excluded_audio_rows.sort(
        key=lambda row: (row["event"], int(row["start_ms"]), int(row["request_id"]))
    )
    subtitle_cues.sort(
        key=lambda row: (row["event"], int(row["start_ms"]), int(row["voice_request_id"]))
    )

    event_presentations = []
    for event in EVENTS:
        rows = [row for row in retained_audio_rows if row["event"] == event]
        audio_tail_frames = max(
            (math.ceil(int(row["end_ms"]) * 30 / 1000) for row in rows),
            default=0,
        )
        frames = presentation_frames[event]
        if audio_tail_frames > frames:
            raise Ac0915AudioAuthorityError(
                f"retained audio escapes exact event presentation: {event}/{audio_tail_frames}>{frames}"
            )
        event_presentations.append(
            {
                "event": event,
                "presentation_frames": frames,
                "presentation_seconds": frames / 30,
                "retained_audio_occurrences": len(rows),
                "excluded_bgm_occurrences": sum(
                    1 for row in excluded_audio_rows if row["event"] == event
                ),
                "retained_audio_tail_frame_exclusive": audio_tail_frames,
                "trailing_visual_after_audio_frames": frames - audio_tail_frames,
                "native_width": 416,
                "native_height": 232,
                "frame_rate": "30/1",
            }
        )

    voice_occurrences = sum(row["volume_bus"] == "VOICE" for row in retained_audio_rows)
    se_occurrences = sum(row["volume_bus"] == "SE" for row in retained_audio_rows)
    if (
        len(retained_audio_rows) != 40
        or len(excluded_audio_rows) != 1
        or voice_occurrences != 18
        or se_occurrences != 22
        or len(subtitle_cues) != 18
        or len(audio_cache) != 30
        or sum(presentation_frames.values()) != 4622
    ):
        raise Ac0915AudioAuthorityError("ac0915 audio authority dimensions differ")

    return {
        "schema": "magireco-ac0915-native416-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
        "family": "ac0915",
        "product_semantics": (
            "duplicate_free_exhaustive_editorial_collection_not_native_single_session"
        ),
        "binary": {"source": bind_source(binary), "gnu_build_id": build_id},
        "inputs": {
            "visual_projection_authority": bind_source(visual_authority_path),
            "event_audio_components": bind_source(event_audio_components_path),
            "z2d_sound_callbacks": bind_source(z2d_sound_callbacks_path),
            "translation": bind_source(translation_path),
            "durable_audio_root": str(durable_audio_root.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "strict_no_bgm_contract": {
            "excluded": "only exact SOUND_DIVIDE_TBL BGM rows",
            "retained": "all exact SOUND_DIVIDE_TBL SE and VOICE rows",
            "mix_policy_for_renderer": "unity source gain; amix normalize=0; 48000 Hz stereo output",
            "claim": "BGM intentionally excluded while all verified dialogue and SE are retained",
        },
        "edition_contract": {
            "none": "strict no-BGM audio, no burned subtitle",
            "JA": "same strict no-BGM audio plus exact JA cues",
            "ZH": "same strict no-BGM audio plus project ZH cues",
            "human_status": "HUMAN_PLAYBACK_REQUIRED_FOR_NEW_LONGFORM",
        },
        "retained_audio_rows": retained_audio_rows,
        "excluded_audio_rows": excluded_audio_rows,
        "subtitle_cues": subtitle_cues,
        "event_presentations": event_presentations,
        "summary": {
            "events": 21,
            "official_event_component_occurrences": 20,
            "exact_parent_bound_callback_occurrences": 21,
            "retained_audio_occurrences": 40,
            "retained_se_occurrences": se_occurrences,
            "retained_voice_occurrences": voice_occurrences,
            "excluded_bgm_occurrences": 1,
            "subtitle_cue_occurrences": len(subtitle_cues),
            "unique_dialogue_request_ids": len(translations),
            "unique_official_ogg_sources": len(audio_cache),
            "total_event_presentation_frames_before_dedup": 4622,
            "total_event_presentation_seconds_before_dedup": 4622 / 30,
        },
        "assertions": {
            "all_21_visual_events_bound": True,
            "all_20_event_audio_components_bound": True,
            "all_21_parent_bound_callbacks_are_event_global": True,
            "only_sound_551_request_226_is_excluded_as_bgm": True,
            "all_22_se_occurrences_retained": True,
            "all_18_voice_occurrences_retained": True,
            "all_18_voice_occurrences_have_subtitle_cues": True,
            "all_30_unique_official_ogg_sources_are_durable_and_identity_bound": True,
            "all_retained_audio_ends_within_visual_event_extent": True,
            "child_local_timing_without_parent_offset_used": False,
            "P16_P17_P18_reference_count": 0,
            "source_media_modified": False,
            "media_rendered": False,
            "human_playback_approval_inferred": False,
        },
    }


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    serialised = []
    for row in rows:
        serialised.append(
            {
                key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
        )
    fields = list(dict.fromkeys(field for row in serialised for field in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(serialised)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac0915AudioAuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC0915_EVENT_AUDIO_AUTHORITY.json"
    retained_path = output_dir / "AC0915_RETAINED_AUDIO_ROWS.csv"
    excluded_path = output_dir / "AC0915_EXCLUDED_BGM_ROWS.csv"
    subtitle_path = output_dir / "AC0915_SUBTITLE_CUES.csv"
    presentation_path = output_dir / "AC0915_EVENT_PRESENTATIONS.csv"
    readme_path = output_dir / "README.md"
    rollback_path = output_dir / "ROLLBACK.ps1"
    verification_path = output_dir / "VERIFICATION_RECORD.json"

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_csv(retained_path, list(report["retained_audio_rows"]))
    _write_csv(excluded_path, list(report["excluded_audio_rows"]))
    _write_csv(subtitle_path, list(report["subtitle_cues"]))
    _write_csv(presentation_path, list(report["event_presentations"]))
    readme_path.write_text(
        "# ac0915 native416 event audio authority\n\n"
        "Exact v178/v179 parent Z2D starts bind 21 reqSound callback occurrences to "
        "event-global time. The exact Slot SOUND_DIVIDE_TBL retains 22 SE and 18 VOICE "
        "occurrences, while only ac0915_012 request 226 / sound 551 is excluded as BGM. "
        "All 30 unique official OGG sources are rebound to the durable D: root. The 18 JA/ZH "
        "cue occurrences remain HUMAN_PLAYBACK_REQUIRED for the new exhaustive longform.\n",
        encoding="utf-8",
    )
    root_literal = str(output_dir.resolve()).replace("'", "''")
    rollback_path.write_text(
        "param([switch]$Apply)\n"
        f"$Root = '{root_literal}'\n"
        "if (-not $Apply) {\n"
        "  Write-Output 'ROLLBACK_VALIDATED: immutable audio authority can be disabled by same-volume rename; source media is untouched.'\n"
        "  exit 0\n"
        "}\n"
        "$Parent = Split-Path -Parent $Root\n"
        "$Leaf = Split-Path -Leaf $Root\n"
        "$Target = Join-Path $Parent ($Leaf + '.disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))\n"
        "Move-Item -LiteralPath $Root -Destination $Target\n"
        "Write-Output ('ROLLBACK_APPLIED: ' + $Target)\n",
        encoding="utf-8",
    )
    output_files = [
        report_path,
        retained_path,
        excluded_path,
        subtitle_path,
        presentation_path,
        readme_path,
        rollback_path,
    ]
    literal_result = (
        "PASS events=21 retained=40 se=22 voice=18 excluded_bgm=1 "
        "subtitles=18 unique_ogg=30 frames=4622 audio_gate=CLOSED"
    )
    verification = {
        "schema": "magireco-ac0915-native416-audio-verification-v1",
        "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
        "literal_result": literal_result,
        "checks": report["assertions"],
        "summary": report["summary"],
        "outputs": {path.name: bind_source(path) for path in output_files},
    }
    verification_path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path)
    parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--translation", required=True, type=Path)
    parser.add_argument("--durable-audio-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary,
        visual_authority_path=args.visual_authority,
        event_audio_components_path=args.event_audio_components,
        z2d_sound_callbacks_path=args.z2d_sound_callbacks,
        translation_path=args.translation,
        durable_audio_root=args.durable_audio_root,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS events=21 retained=40 se=22 voice=18 excluded_bgm=1 "
        "subtitles=18 unique_ogg=30 frames=4622 audio_gate=CLOSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
