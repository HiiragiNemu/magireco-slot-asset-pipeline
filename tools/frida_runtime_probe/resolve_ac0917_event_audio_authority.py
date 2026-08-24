#!/usr/bin/env python3
"""Resolve exact ac0917 event-global audio, page subtitles, and no-BGM tails."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_exhaustive_unique_longform import file_sha256
    from .resolve_ac0915_event_audio_authority import _write_csv
    from .resolve_ac7206_event_audio_authority import VOLUME_BUS, read_sound_divide_values
except ImportError:  # pragma: no cover - direct execution
    from build_exhaustive_unique_longform import file_sha256  # type: ignore
    from resolve_ac0915_event_audio_authority import _write_csv  # type: ignore
    from resolve_ac7206_event_audio_authority import (  # type: ignore
        VOLUME_BUS,
        read_sound_divide_values,
    )


EVENTS = tuple(f"ac0917_{index:03d}" for index in (*range(1, 12), 14))
EXPECTED_PRESENTATION_FRAMES = {
    "ac0917_001": 187,
    "ac0917_002": 240,
    "ac0917_003": 300,
    "ac0917_004": 300,
    "ac0917_005": 240,
    "ac0917_006": 300,
    "ac0917_007": 280,
    "ac0917_008": 280,
    "ac0917_009": 280,
    "ac0917_010": 300,
    "ac0917_011": 100,
    "ac0917_014": 100,
}
EXPECTED_EVENT_COMPONENTS = {
    "ac0917_001": {(863, 2950, 0)},
    "ac0917_002": {(864, 2951, 0)},
    "ac0917_003": {(865, 2952, 0)},
    "ac0917_004": {(864, 2951, 0)},
    "ac0917_005": set(),
    "ac0917_006": {(865, 2952, 0)},
    "ac0917_007": {(419, 1005, 0), (226, 551, 9700)},
    "ac0917_008": {(422, 1008, 0), (227, 552, 4500)},
    "ac0917_009": {(424, 1010, 0), (228, 553, 4500)},
    "ac0917_010": {(864, 2951, 0)},
    "ac0917_011": {(865, 2952, 0)},
    "ac0917_014": set(),
}
# host, request, sound, exact event-global host start frame, bus
EXPECTED_CALLBACKS_BY_EVENT = {
    "ac0917_001": (
        ("cap0917_enzetu_tou_001", 5368, 20543, 20, "VOICE"),
        ("cap0917_enzetu_tou_002", 5369, 20544, 92, "VOICE"),
    ),
    "ac0917_002": (("cap0917_enzetu_tou_004", 5370, 20545, 3, "VOICE"),),
    "ac0917_003": (("cap0917_enzetu_tou_006", 5371, 20546, 3, "VOICE"),),
    "ac0917_004": (("cap0917_enzetu_tou_004", 5370, 20545, 3, "VOICE"),),
    "ac0917_005": (),
    "ac0917_006": (
        ("cap5102_iro_oshite_001", 2439, 15100, 0, "VOICE"),
        ("ac8002_chance_btn_deka", 453, 1072, 0, "SE"),
    ),
    "ac0917_007": (("cap0917_enzetu_tou_008", 5372, 20547, 3, "VOICE"),),
    "ac0917_008": (("cap0917_enzetu_tou_010", 5373, 20548, 3, "VOICE"),),
    "ac0917_009": (("cap0917_enzetu_tou_011", 5374, 20549, 3, "VOICE"),),
    "ac0917_010": (
        ("ac8002_chance_btn_mokyu", 8209, 26401, 0, "VOICE"),
        ("ac8002_chance_btn_mokyu", 450, 1069, 0, "SE"),
    ),
    "ac0917_011": (("cap0917_enzetu_tou_006", 5371, 20546, 3, "VOICE"),),
    "ac0917_014": (
        ("cap5102_iro_oshite_001", 2439, 15100, 0, "VOICE"),
        ("ac8002_chance_btn_lev", 451, 1070, 0, "SE"),
    ),
}
EXPECTED_PAGE_HOSTS = {
    5368: ("cap0917_enzetu_tou_001",),
    5369: ("cap0917_enzetu_tou_002", "cap0917_enzetu_tou_003"),
    5370: ("cap0917_enzetu_tou_004", "cap0917_enzetu_tou_005"),
    5371: ("cap0917_enzetu_tou_006", "cap0917_enzetu_tou_007"),
    5372: ("cap0917_enzetu_tou_008", "cap0917_enzetu_tou_009"),
    5373: ("cap0917_enzetu_tou_010",),
    5374: ("cap0917_enzetu_tou_011",),
    2439: ("cap5102_iro_oshite_001",),
    8209: ("ac8002_chance_btn_mokyu",),
}
EXPECTED_BGM = {
    ("ac0917_007", 226, 551),
    ("ac0917_008", 227, 552),
    ("ac0917_009", 228, 553),
}
EXPECTED_FINAL_HOLDS = {
    "ac0917_001": 65,
    "ac0917_002": 29,
    "ac0917_007": 7,
    "ac0917_011": 128,
}


class Ac0917AudioAuthorityError(ValueError):
    pass


def bind_source(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise Ac0917AudioAuthorityError(f"source file is absent: {path}")
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac0917AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def _translation_map(path: Path) -> dict[int, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {int(row["request_id"]): row for row in rows}
    required = {"request_id", "speaker_ja", "speaker_zh", "status", "text_evidence", "pages"}
    if (
        document.get("schema") != "magireco-reviewed-story-zh-dialogue-pages-v1"
        or document.get("scope")
        != "ac0917_exhaustive_native416_event_global_dialogue_pages"
        or set(result) != set(EXPECTED_PAGE_HOSTS)
        or len(result) != len(rows)
        or any(not required.issubset(row) for row in rows)
    ):
        raise Ac0917AudioAuthorityError("ac0917 translation dimensions differ")
    for request_id, row in result.items():
        pages = row["pages"]
        if (
            tuple(page.get("z2d_name") for page in pages)
            != EXPECTED_PAGE_HOSTS[request_id]
            or any(not str(page.get("ja", "")).strip() for page in pages)
            or any(not str(page.get("zh", "")).strip() for page in pages)
        ):
            raise Ac0917AudioAuthorityError(
                f"ac0917 translation page dimensions differ: {request_id}"
            )
    return result


def _visual_host_intervals(
    visual: Mapping[str, Any],
) -> tuple[dict[str, dict[str, tuple[int, int]]], dict[str, int]]:
    if (
        visual.get("schema") != "magireco-ac0917-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("family") != "ac0917"
        or visual.get("frame_rate") != "30/1"
        or visual.get("output_canvas") != [416, 232]
    ):
        raise Ac0917AudioAuthorityError("ac0917 projection authority differs")
    events = visual.get("events", [])
    if [row.get("event") for row in events] != list(EVENTS):
        raise Ac0917AudioAuthorityError("ac0917 projection event order differs")
    frames = {str(row["event"]): int(row["presentation_frame_count"]) for row in events}
    if frames != EXPECTED_PRESENTATION_FRAMES:
        raise Ac0917AudioAuthorityError(
            f"ac0917 presentation frame totals differ: {frames}"
        )
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
            name: (min(start for start, _ in spans), max(end for _, end in spans))
            for name, spans in intervals.items()
        }
        if any(
            start < 0 or end < start or end >= frames[event]
            for start, end in result[event].values()
        ):
            raise Ac0917AudioAuthorityError(
                f"visual host interval escapes event: {event}"
            )
    return result, frames


def _durable_audio_identity(
    root: Path, name: str, cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if name not in cache:
        cache[name] = {"ogg_name": name, "official_source": bind_source(root / name)}
    return dict(cache[name])


def _render_text(speaker: str, text: str) -> str:
    return f"{speaker}：{text}" if speaker else text


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
    host_intervals, visual_frames = _visual_host_intervals(visual)
    translations = _translation_map(translation_path)

    component_rows = [
        row for row in read_csv(event_audio_components_path) if row.get("root") == "ac0917"
    ]
    components_by_event: dict[str, list[dict[str, str]]] = {event: [] for event in EVENTS}
    for row in component_rows:
        event = row.get("primary_animation", "")
        if event not in components_by_event:
            raise Ac0917AudioAuthorityError(f"unexpected ac0917 component event: {event}")
        components_by_event[event].append(row)
    observed_components = {
        event: {
            (int(row["leaf_request_id"]), int(row["leaf_sound_code"]), int(row["start_ms"]))
            for row in rows
        }
        for event, rows in components_by_event.items()
    }
    if observed_components != EXPECTED_EVENT_COMPONENTS or len(component_rows) != 13:
        raise Ac0917AudioAuthorityError(
            f"ac0917 event component set differs: {observed_components}"
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
    callbacks = {
        (row["z2d_name"], int(row["sound_request_id"])): row for row in callback_rows
    }
    if set(callbacks) != expected_callback_pairs or len(callbacks) != len(callback_rows):
        raise Ac0917AudioAuthorityError("ac0917 callback host/request set differs")

    sound_ids = {int(row["leaf_sound_code"]) for row in component_rows}
    sound_ids.update(int(row["sound_resource_id"]) for row in callback_rows)
    build_id, buses = read_sound_divide_values(binary, sound_ids)
    audio_cache: dict[str, dict[str, Any]] = {}
    retained: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for event in EVENTS:
        for source in components_by_event[event]:
            request_id = int(source["leaf_request_id"])
            sound_id = int(source["leaf_sound_code"])
            start_ms = int(source["start_ms"])
            duration_ms = int(source["duration_ms"])
            bus = VOLUME_BUS[buses[sound_id]]
            if (
                source.get("smz_matches_leaf_request") != "yes"
                or source.get("ogg_duration_match") != "yes"
            ):
                raise Ac0917AudioAuthorityError(
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
            key = (event, request_id, sound_id)
            if bus == "BGM":
                if key not in EXPECTED_BGM:
                    raise Ac0917AudioAuthorityError(f"unexpected ac0917 BGM: {key}")
                row["strict_no_bgm_disposition"] = "EXCLUDE_EXACT_BGM_BUS"
                excluded.append(row)
            else:
                if bus != "SE":
                    raise Ac0917AudioAuthorityError(
                        f"ac0917 component is not SE/BGM: {event}/{request_id}/{bus}"
                    )
                row["strict_no_bgm_disposition"] = "RETAIN_VERIFIED_SE"
                retained.append(row)
    if {(row["event"], row["request_id"], row["sound_id"]) for row in excluded} != EXPECTED_BGM:
        raise Ac0917AudioAuthorityError("exact ac0917 BGM exclusion set differs")

    subtitle_pages: list[dict[str, Any]] = []
    for event in EVENTS:
        for host, request_id, expected_sound, expected_frame, expected_bus in EXPECTED_CALLBACKS_BY_EVENT[event]:
            callback = callbacks[(host, request_id)]
            if host not in host_intervals[event]:
                raise Ac0917AudioAuthorityError(
                    f"callback host is absent from exact visual event: {event}/{host}"
                )
            host_start, _ = host_intervals[event][host]
            sound_id = int(callback["sound_resource_id"])
            if (
                sound_id != expected_sound
                or int(callback["exec_frame"]) != 0
                or callback.get("sound_request_match_count") != "1"
                or callback.get("ogg_exists") != "yes"
                or host_start != expected_frame
            ):
                raise Ac0917AudioAuthorityError(
                    f"exact callback binding differs: {event}/{host}/{request_id}"
                )
            bus = VOLUME_BUS[buses[sound_id]]
            if bus != expected_bus or bus == "BGM":
                raise Ac0917AudioAuthorityError(
                    f"callback bus differs: {event}/{host}/{request_id}/{bus}"
                )
            start_frame = host_start
            start_ms = round(start_frame * 1000 / 30)
            duration_ms = int(callback["sound_duration_ms"])
            audio_row = {
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
                    "v208_v209_exact_event_global_parent_host_start_plus_exact_child_callback_frame_0"
                ),
            }
            retained.append(audio_row)
            if bus != "VOICE":
                continue
            translation = translations[request_id]
            pages = translation["pages"]
            page_intervals = []
            for page in pages:
                page_host = str(page["z2d_name"])
                if page_host not in host_intervals[event]:
                    raise Ac0917AudioAuthorityError(
                        f"subtitle page host absent: {event}/{request_id}/{page_host}"
                    )
                page_intervals.append(host_intervals[event][page_host])
            if page_intervals[0][0] != start_frame or any(
                page_intervals[index][0] <= page_intervals[index - 1][0]
                for index in range(1, len(page_intervals))
            ):
                raise Ac0917AudioAuthorityError(
                    f"subtitle page order differs: {event}/{request_id}"
                )
            voice_end_ms = start_ms + duration_ms
            for index, (page, (page_start, page_end)) in enumerate(
                zip(pages, page_intervals, strict=True)
            ):
                page_start_ms = round(page_start * 1000 / 30)
                if index + 1 < len(pages):
                    end_ms = round(page_intervals[index + 1][0] * 1000 / 30)
                    end_policy = "until_exact_next_graphical_page_start"
                else:
                    host_end_ms = round((page_end + 1) * 1000 / 30)
                    end_ms = max(voice_end_ms, host_end_ms)
                    end_policy = "max_official_voice_end_and_exact_final_page_host_end"
                if end_ms <= page_start_ms:
                    raise Ac0917AudioAuthorityError(
                        f"subtitle page interval empty: {event}/{request_id}/{index}"
                    )
                subtitle_pages.append(
                    {
                        "event": event,
                        "voice_request_id": request_id,
                        "voice_sound_id": sound_id,
                        "page_index": index + 1,
                        "page_count": len(pages),
                        "z2d_name": page["z2d_name"],
                        "start_frame": page_start,
                        "start_ms": page_start_ms,
                        "end_ms": end_ms,
                        "voice_start_ms": start_ms,
                        "voice_end_ms": voice_end_ms,
                        "speaker_ja": translation["speaker_ja"],
                        "speaker_zh": translation["speaker_zh"],
                        "ja": _render_text(translation["speaker_ja"], page["ja"]),
                        "zh": _render_text(translation["speaker_zh"], page["zh"]),
                        "translation_status": translation["status"],
                        "text_evidence": translation["text_evidence"],
                        "subtitle_end_policy": end_policy,
                        "timing_evidence": audio_row["timing_evidence"],
                    }
                )

    retained.sort(key=lambda row: (row["event"], int(row["start_ms"]), int(row["request_id"])))
    excluded.sort(key=lambda row: (row["event"], int(row["start_ms"]), int(row["request_id"])))
    subtitle_pages.sort(
        key=lambda row: (
            row["event"],
            int(row["start_ms"]),
            int(row["voice_request_id"]),
            int(row["page_index"]),
        )
    )

    presentations = []
    actual_holds: dict[str, int] = {}
    for event in EVENTS:
        event_audio = [row for row in retained if row["event"] == event]
        audio_tail = max(
            (math.ceil(int(row["end_ms"]) * 30 / 1000) for row in event_audio),
            default=0,
        )
        frames = visual_frames[event]
        rendered_frames = max(frames, audio_tail)
        hold = rendered_frames - frames
        if hold:
            actual_holds[event] = hold
        presentations.append(
            {
                "event": event,
                "visual_presentation_frames": frames,
                "retained_audio_tail_frame_exclusive": audio_tail,
                "final_frame_hold_frames": hold,
                "rendered_presentation_frames": rendered_frames,
                "rendered_presentation_seconds": rendered_frames / 30,
                "retained_audio_occurrences": len(event_audio),
                "excluded_bgm_occurrences": sum(
                    row["event"] == event for row in excluded
                ),
                "native_width": 416,
                "native_height": 232,
                "frame_rate": "30/1",
            }
        )
    if actual_holds != EXPECTED_FINAL_HOLDS:
        raise Ac0917AudioAuthorityError(f"exact final-frame holds differ: {actual_holds}")

    voices = sum(row["volume_bus"] == "VOICE" for row in retained)
    ses = sum(row["volume_bus"] == "SE" for row in retained)
    rendered_frames_total = sum(row["rendered_presentation_frames"] for row in presentations)
    if (
        len(retained) != 25
        or len(excluded) != 3
        or voices != 12
        or ses != 13
        or len(subtitle_pages) != 18
        or len(audio_cache) != 21
        or sum(visual_frames.values()) != 2907
        or rendered_frames_total != 3136
    ):
        raise Ac0917AudioAuthorityError("ac0917 audio authority dimensions differ")

    return {
        "schema": "magireco-ac0917-native416-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
        "family": "ac0917",
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
            {
                "address": "0x1445c54",
                "function": "SOUND_DIVIDE_TBL",
                "proves": "exact BGM/SE/VOICE bus per sound resource id",
            },
            {
                "address": "v208/v209 GFDirection chain",
                "function": "parent Type20 instance start and event clock",
                "proves": "callback frame zero and final-frame hold are event-global",
            },
        ],
        "strict_no_bgm_contract": {
            "excluded": "only exact SOUND_DIVIDE_TBL BGM rows 551/552/553",
            "retained": "all exact SOUND_DIVIDE_TBL SE and VOICE rows",
            "mix_policy_for_renderer": "unity source gain; amix normalize=0; 48000 Hz stereo output",
            "claim": "BGM intentionally excluded while all verified dialogue and SE are retained",
        },
        "edition_contract": {
            "none": "strict no-BGM audio, no burned subtitle",
            "JA": "same strict no-BGM audio plus exact page-timed JA cues",
            "ZH": "same strict no-BGM audio plus reviewed page-timed ZH cues",
            "human_status": "HUMAN_PLAYBACK_REQUIRED_FOR_NEW_LONGFORM",
        },
        "retained_audio_rows": retained,
        "excluded_audio_rows": excluded,
        "subtitle_page_cues": subtitle_pages,
        "event_presentations": presentations,
        "summary": {
            "events": 12,
            "official_event_component_occurrences": 13,
            "exact_parent_bound_callback_occurrences": 15,
            "retained_audio_occurrences": 25,
            "retained_se_occurrences": ses,
            "retained_voice_occurrences": voices,
            "excluded_bgm_occurrences": 3,
            "subtitle_page_cue_occurrences": len(subtitle_pages),
            "unique_dialogue_request_ids": len(translations),
            "unique_official_ogg_sources": len(audio_cache),
            "visual_presentation_frames_before_dedup": 2907,
            "rendered_presentation_frames_before_dedup": rendered_frames_total,
            "final_frame_hold_occurrences": len(actual_holds),
            "final_frame_hold_frames": sum(actual_holds.values()),
        },
        "assertions": {
            "all_12_visual_events_bound": True,
            "all_13_event_audio_components_bound": True,
            "all_15_parent_bound_callback_occurrences_are_event_global": True,
            "only_sounds_551_552_553_are_excluded_as_bgm": True,
            "all_13_se_occurrences_retained": True,
            "all_12_voice_occurrences_retained": True,
            "all_voice_occurrences_have_page_timed_subtitles": True,
            "all_21_unique_official_ogg_sources_are_hash_bound": True,
            "four_audio_tails_use_exact_final_frame_holds": True,
            "excluded_bgm_does_not_extend_no_bgm_visuals": True,
            "child_local_timing_without_parent_offset_used": False,
            "P16_P17_P18_reference_count": 0,
            "source_media_modified": False,
            "media_rendered": False,
            "human_playback_approval_inferred": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise Ac0917AudioAuthorityError(f"immutable output already exists: {output_dir}")
    staging = output_dir.with_name(
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    staging.mkdir(parents=True)
    try:
        report_path = staging / "AC0917_EVENT_AUDIO_AUTHORITY.json"
        retained_path = staging / "AC0917_RETAINED_AUDIO_ROWS.csv"
        excluded_path = staging / "AC0917_EXCLUDED_BGM_ROWS.csv"
        subtitle_path = staging / "AC0917_SUBTITLE_PAGE_CUES.csv"
        presentation_path = staging / "AC0917_EVENT_PRESENTATIONS.csv"
        readme_path = staging / "README.md"
        rollback_path = staging / "ROLLBACK.ps1"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv(retained_path, list(report["retained_audio_rows"]))
        _write_csv(excluded_path, list(report["excluded_audio_rows"]))
        _write_csv(subtitle_path, list(report["subtitle_page_cues"]))
        _write_csv(presentation_path, list(report["event_presentations"]))
        readme_path.write_text(
            "# ac0917 原生 416×232 事件音频权威\n\n"
            "12 个事件保留 13 次 SE 与 12 次 VOICE；仅 SOUND_DIVIDE_TBL 证明为 "
            "BGM 的 551/552/553 三次出现被排除。7 组灯花演说字幕按 11 个图形页面"
            "切换，另含两次环彩羽和一次无人物前缀的按键语音，共 18 个页面 cue。"
            "4 个事件使用合计 229 帧的精确尾帧保持覆盖已验证语音尾部。新长片仍需"
            "人工播放验收。\n",
            encoding="utf-8",
        )
        root_literal = str(output_dir).replace("'", "''")
        rollback_path.write_text(
            "param([switch]$Apply)\n"
            f"$Root = '{root_literal}'\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: immutable ac0917 audio authority can be disabled by same-volume rename; source media is untouched.'; exit 0 }\n"
            "$Target = $Root + '.disabled_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED: ' + $Target)\n",
            encoding="utf-8",
        )
        outputs = [
            report_path,
            retained_path,
            excluded_path,
            subtitle_path,
            presentation_path,
            readme_path,
            rollback_path,
        ]
        verification = {
            "schema": "magireco-ac0917-native416-audio-verification-v1",
            "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
            "literal_result": (
                "PASS events=12 retained=25 se=13 voice=12 excluded_bgm=3 "
                "subtitle_pages=18 unique_ogg=21 visual_frames=2907 "
                "render_frames=3136 holds=4/229 audio_gate=CLOSED"
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
                "Audio authority construction failed; inspect the command error.\n",
                encoding="utf-8",
            )
        raise
    return output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path)
    parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--translation", required=True, type=Path)
    parser.add_argument("--durable-audio-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        binary=args.binary,
        visual_authority_path=args.visual_authority,
        event_audio_components_path=args.event_audio_components,
        z2d_sound_callbacks_path=args.z2d_sound_callbacks,
        translation_path=args.translation,
        durable_audio_root=args.durable_audio_root,
    )
    output = write_outputs(report, args.output_dir)
    verification = json.loads(
        (output / "VERIFICATION_RECORD.json").read_text(encoding="utf-8")
    )
    print(verification["literal_result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
