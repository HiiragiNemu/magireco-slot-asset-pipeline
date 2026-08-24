#!/usr/bin/env python3
"""Resolve exact ac4902 event-global audio, subtitles, and strict no-BGM buses."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac4902_gfdirection_presentation_authority import (
        EVENT_IDS,
        EXPECTED_EVENT_FRAMES,
    )
    from .resolve_ac0915_event_audio_authority import _write_csv, bind_source
    from .resolve_ac7206_event_audio_authority import VOLUME_BUS, read_sound_divide_values
except ImportError:  # pragma: no cover - direct script execution
    from build_ac4902_gfdirection_presentation_authority import (  # type: ignore
        EVENT_IDS,
        EXPECTED_EVENT_FRAMES,
    )
    from resolve_ac0915_event_audio_authority import _write_csv, bind_source  # type: ignore
    from resolve_ac7206_event_audio_authority import (  # type: ignore
        VOLUME_BUS,
        read_sound_divide_values,
    )


VOICE_REQUEST_IDS = frozenset(
    {
        2439, 2742, 2743, 2745, 2746, 3228, 3229, 3230, 3576, 3577,
        4070, 4071, 4072, 4073, 4340, 4341, 4342, 4343, 8209, 8340,
    }
)
COMPONENT_REQUEST_SOUND_PAIRS = frozenset(
    {
        (226, 551), (419, 1005), (438, 1035), (439, 1036), (892, 3123),
        (1686, 8150), (1687, 8151), (1688, 8152), (1689, 8153),
        (1691, 8155), (1692, 8156), (1693, 8157), (1694, 8158),
        (1695, 8159), (1696, 8161), (1697, 8162), (1698, 8163),
        (1699, 8164), (1700, 8165), (1701, 8166), (1702, 8167),
        (1703, 8181), (1704, 8182), (1707, 8186),
    }
)
CALLBACK_REQUEST_SOUND_PAIRS = frozenset(
    {
        (450, 1069), (453, 1072), (893, 3125), (894, 3126),
        (2439, 15100), (2742, 15500), (2743, 15501), (2745, 15503),
        (2746, 15504), (3228, 16182), (3229, 16183), (3230, 16184),
        (3576, 16849), (3577, 16850), (4070, 17770), (4071, 17771),
        (4072, 17772), (4073, 17773), (4340, 18198), (4341, 18199),
        (4342, 18200), (4343, 18201), (8209, 26401), (8340, 26704),
    }
)
EXTENDED_HOLD_EVENTS = frozenset(
    {
        "ac4902_004", "ac4902_020", "ac4902_021",
        "ac4902_026", "ac4902_060", "ac4902_061",
    }
)
EXPECTED_RETAINED_AUDIO = 148
EXPECTED_RETAINED_SE = 92
EXPECTED_RETAINED_VOICE = 56
EXPECTED_UNIQUE_RETAINED_OGG = 47
EXPECTED_VISUAL_FRAMES = 25625
EXPECTED_OUTPUT_FRAMES = 25703


class Ac4902AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac4902AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def _translation_map(path: Path) -> dict[int, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {int(row["request_id"]): row for row in rows}
    required_fields = {
        "request_id", "ja", "zh", "speaker_ja", "speaker_zh",
        "render_ja", "render_zh", "status", "text_evidence",
    }
    if (
        document.get("schema") != "magireco-reviewed-story-zh-dialogue-map-v1"
        or document.get("scope")
        != "ac4902_exhaustive_native416_event_global_dialogue"
        or set(result) != set(VOICE_REQUEST_IDS)
        or len(result) != len(rows)
        or any(not required_fields.issubset(row) for row in rows)
        or any(not str(row["ja"]).strip() or not str(row["zh"]).strip() for row in rows)
        or result[8340]["speaker_ja"] != "黒羽"
        or result[8340]["speaker_zh"] != "黑羽"
    ):
        raise Ac4902AudioAuthorityError("ac4902 translation map dimensions differ")
    return result


def _visual_host_intervals(
    visual: Mapping[str, Any],
) -> tuple[dict[str, dict[str, tuple[int, int]]], dict[str, int]]:
    if (
        visual.get("schema") != "magireco-ac4902-output-projection-authority-v1"
        or visual.get("status") != "PASS_READY_FOR_EVENT_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("family") != "ac4902"
        or visual.get("frame_rate") != "30/1"
        or visual.get("output_canvas") != [416, 232]
    ):
        raise Ac4902AudioAuthorityError("ac4902 projection authority differs")
    events = visual.get("events", [])
    if [row.get("event") for row in events] != list(EVENT_IDS):
        raise Ac4902AudioAuthorityError("ac4902 projection event order differs")
    frames = {str(row["event"]): int(row["presentation_frame_count"]) for row in events}
    if frames != EXPECTED_EVENT_FRAMES:
        raise Ac4902AudioAuthorityError("ac4902 presentation frame totals differ")

    result: dict[str, dict[str, tuple[int, int]]] = {}
    for event_row in events:
        event = str(event_row["event"])
        intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for row in event_row.get("non_movie_text_z2d_nodes", []):
            intervals[str(row["node"])].append(
                (int(row["event_global_start_frame"]), int(row["event_global_end_frame_inclusive"]))
            )
        for row in event_row.get("layers_in_render_pass_order_under_to_top", []):
            intervals[str(row["parent_z2d"])].append(
                (int(row["event_start_frame"]), int(row["event_end_frame_inclusive"]))
            )
        result[event] = {
            name: (min(start for start, _ in rows), max(end for _, end in rows))
            for name, rows in intervals.items()
        }
        if any(
            start < 0 or end < start or end >= frames[event]
            for start, end in result[event].values()
        ):
            raise Ac4902AudioAuthorityError(f"visual host interval escapes event: {event}")
    return result, frames


def _durable_audio_identity(
    root: Path, name: str, cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if name not in cache:
        path = (root / name).resolve()
        cache[name] = {"ogg_name": name, "official_source": bind_source(path)}
    return dict(cache[name])


def _speaker_override_map(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if (
        document.get("schema")
        != "magireco-hash-bound-speaker-identity-overrides-v1"
        or document.get("status") != "project_owner_authorized"
    ):
        raise Ac4902AudioAuthorityError("speaker identity override authority differs")
    rows = {
        (str(row["event"]), int(row["request_id"])): row
        for row in document.get("overrides", [])
        if str(row.get("event", "")).startswith("ac4902_")
    }
    if set(rows) != {("ac4902_003", 8340), ("ac4902_059", 8340)}:
        raise Ac4902AudioAuthorityError("ac4902 speaker override event set differs")
    return rows


def build_report(
    *,
    binary: Path,
    visual_authority_path: Path,
    event_audio_components_path: Path,
    z2d_sound_callbacks_path: Path,
    translation_path: Path,
    speaker_overrides_path: Path,
    durable_audio_root: Path,
) -> dict[str, Any]:
    visual = json.loads(visual_authority_path.read_text(encoding="utf-8"))
    host_intervals, visual_frames = _visual_host_intervals(visual)
    translations = _translation_map(translation_path)
    speaker_overrides = _speaker_override_map(speaker_overrides_path)

    component_rows = [
        row for row in read_csv(event_audio_components_path) if row.get("root") == "ac4902"
    ]
    component_pairs = {
        (int(row["leaf_request_id"]), int(row["leaf_sound_code"]))
        for row in component_rows
    }
    if (
        len(component_rows) != 62
        or component_pairs != COMPONENT_REQUEST_SOUND_PAIRS
        or len({row["primary_animation"] for row in component_rows}) != 53
        or any(row["primary_animation"] not in EVENT_IDS for row in component_rows)
        or any(
            row["smz_matches_leaf_request"] != "yes"
            or row["ogg_duration_match"] != "yes"
            or not row["ogg_name"].endswith(".ogg")
            for row in component_rows
        )
    ):
        raise Ac4902AudioAuthorityError("ac4902 event component set differs")

    all_host_names = {
        name for event_hosts in host_intervals.values() for name in event_hosts
    }
    callback_rows = [
        row
        for row in read_csv(z2d_sound_callbacks_path)
        if row.get("z2d_name") in all_host_names
    ]
    callback_pairs = {
        (int(row["sound_request_id"]), int(row["sound_resource_id"]))
        for row in callback_rows
    }
    if (
        len(callback_rows) != 24
        or callback_pairs != CALLBACK_REQUEST_SOUND_PAIRS
        or len({row["z2d_name"] for row in callback_rows}) != 23
        or any(
            int(row["exec_frame"]) != 0
            or row["sound_request_match_count"] != "1"
            or row["ogg_exists"] != "yes"
            or not row["ogg_name"].endswith(".ogg")
            for row in callback_rows
        )
    ):
        raise Ac4902AudioAuthorityError("ac4902 callback identity set differs")
    callbacks_by_host: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in callback_rows:
        callbacks_by_host[row["z2d_name"]].append(row)
    callback_occurrences = [
        (event, host, row)
        for event, event_hosts in host_intervals.items()
        for host in event_hosts
        for row in callbacks_by_host.get(host, [])
    ]
    if len(callback_occurrences) != 87:
        raise Ac4902AudioAuthorityError("ac4902 callback occurrence set differs")

    sound_ids = {int(row["leaf_sound_code"]) for row in component_rows}
    sound_ids.update(int(row["sound_resource_id"]) for row in callback_rows)
    build_id, buses = read_sound_divide_values(binary, sound_ids)
    audio_cache: dict[str, dict[str, Any]] = {}
    retained: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for source in component_rows:
        event = source["primary_animation"]
        request_id = int(source["leaf_request_id"])
        sound_id = int(source["leaf_sound_code"])
        start_ms = int(source["start_ms"])
        duration_ms = int(source["duration_ms"])
        bus = VOLUME_BUS[buses[sound_id]]
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
            if (event, request_id, sound_id) != ("ac4902_024", 226, 551):
                raise Ac4902AudioAuthorityError(
                    f"unexpected ac4902 BGM component: {event}/{request_id}/{sound_id}"
                )
            row["strict_no_bgm_disposition"] = "EXCLUDE_EXACT_BGM_BUS"
            excluded.append(row)
        elif bus == "SE":
            row["strict_no_bgm_disposition"] = "RETAIN_VERIFIED_SE"
            retained.append(row)
        else:
            raise Ac4902AudioAuthorityError(
                f"ac4902 event component is not SE/BGM: {event}/{request_id}/{bus}"
            )

    subtitles: list[dict[str, Any]] = []
    for event in EVENT_IDS:
        for host, (host_start, host_end) in host_intervals[event].items():
            for callback in callbacks_by_host.get(host, []):
                request_id = int(callback["sound_request_id"])
                sound_id = int(callback["sound_resource_id"])
                bus = VOLUME_BUS[buses[sound_id]]
                if bus not in {"SE", "VOICE"}:
                    raise Ac4902AudioAuthorityError(
                        f"callback bus differs: {event}/{host}/{request_id}/{bus}"
                    )
                start_frame = host_start
                start_ms = round(start_frame * 1000 / 30)
                duration_ms = int(callback["sound_duration_ms"])
                identity = _durable_audio_identity(
                    durable_audio_root, callback["ogg_name"], audio_cache
                )
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
                    **identity,
                    "volume_kind_value": buses[sound_id],
                    "volume_bus": bus,
                    "strict_no_bgm_disposition": f"RETAIN_VERIFIED_{bus}",
                    "timing_evidence": (
                        "v187_v188_exact_event_global_parent_host_start_plus_exact_child_callback_frame_0"
                    ),
                }
                override = speaker_overrides.get((event, request_id))
                if override is not None:
                    if (
                        callback["sound_code_name"] != override["code_name"]
                        or override["canonical_speaker_code"] != "kuro_black_feather"
                        or override["audio_sha256"]
                        != "A0C8B0D4B5CD3116446358AAFEA35C85B11EC745339BCCF7A20EAA5530D2766A"
                    ):
                        raise Ac4902AudioAuthorityError(
                            f"speaker override differs: {event}/{request_id}"
                        )
                    row["speaker_identity_override"] = dict(override)
                retained.append(row)
                if bus == "VOICE":
                    translation = translations.get(request_id)
                    if translation is None:
                        raise Ac4902AudioAuthorityError(
                            f"voice request lacks translation: {event}/{request_id}"
                        )
                    subtitles.append(
                        {
                            "event": event,
                            "z2d_name": host,
                            "voice_request_id": request_id,
                            "start_frame": start_frame,
                            "start_ms": start_ms,
                            "voice_end_ms": start_ms + duration_ms,
                            "parent_host_end_frame_inclusive": host_end,
                            "parent_host_end_ms": round((host_end + 1) * 1000 / 30),
                            "speaker_ja": translation["speaker_ja"],
                            "speaker_zh": translation["speaker_zh"],
                            "ja": translation["render_ja"],
                            "zh": translation["render_zh"],
                            "translation_status": translation["status"],
                            "text_evidence": translation["text_evidence"],
                            "subtitle_end_policy": (
                                "max_official_voice_end_and_exact_parent_host_end_capped_by_final_event_extent"
                            ),
                            "timing_evidence": row["timing_evidence"],
                        }
                    )

    retained.sort(key=lambda row: (row["event"], int(row["start_ms"]), int(row["request_id"])))
    excluded.sort(key=lambda row: (row["event"], int(row["start_ms"]), int(row["request_id"])))
    subtitles.sort(
        key=lambda row: (row["event"], int(row["start_ms"]), int(row["voice_request_id"]))
    )

    event_presentations: list[dict[str, Any]] = []
    for event in EVENT_IDS:
        rows = [row for row in retained if row["event"] == event]
        audio_tail = max(
            (math.ceil(int(row["end_ms"]) * 30 / 1000) for row in rows),
            default=0,
        )
        visual_count = visual_frames[event]
        output_count = max(visual_count, audio_tail)
        extension = output_count - visual_count
        if (extension > 0) != (event in EXTENDED_HOLD_EVENTS) or extension not in (0, 13):
            raise Ac4902AudioAuthorityError(
                f"event tail extension differs: {event}/{visual_count}/{audio_tail}"
            )
        for cue in (row for row in subtitles if row["event"] == event):
            cue["end_ms"] = min(
                round(output_count * 1000 / 30),
                max(int(cue["voice_end_ms"]), int(cue["parent_host_end_ms"])),
            )
            if int(cue["end_ms"]) <= int(cue["start_ms"]):
                raise Ac4902AudioAuthorityError(
                    f"subtitle interval is empty: {event}/{cue['voice_request_id']}"
                )
        event_presentations.append(
            {
                "event": event,
                "visual_presentation_frames": visual_count,
                "retained_audio_tail_frame_exclusive": audio_tail,
                "final_presentation_frames": output_count,
                "final_presentation_seconds": output_count / 30,
                "tail_hold_frames": extension,
                "tail_policy": (
                    "freeze_last_exact_composed_frame_until_verified_retained_SE_ends"
                    if extension
                    else "exact_visual_presentation_extent"
                ),
                "retained_audio_occurrences": len(rows),
                "excluded_bgm_occurrences": sum(
                    row["event"] == event for row in excluded
                ),
                "native_width": 416,
                "native_height": 232,
                "frame_rate": "30/1",
            }
        )

    voice_count = sum(row["volume_bus"] == "VOICE" for row in retained)
    se_count = sum(row["volume_bus"] == "SE" for row in retained)
    if (
        len(retained) != EXPECTED_RETAINED_AUDIO
        or se_count != EXPECTED_RETAINED_SE
        or voice_count != EXPECTED_RETAINED_VOICE
        or len(excluded) != 1
        or len(subtitles) != EXPECTED_RETAINED_VOICE
        or len(audio_cache) != 48
        or len({row["ogg_name"] for row in retained}) != EXPECTED_UNIQUE_RETAINED_OGG
        or sum(visual_frames.values()) != EXPECTED_VISUAL_FRAMES
        or sum(row["final_presentation_frames"] for row in event_presentations)
        != EXPECTED_OUTPUT_FRAMES
        or sum(row["tail_hold_frames"] for row in event_presentations) != 78
    ):
        raise Ac4902AudioAuthorityError("ac4902 audio authority dimensions differ")

    return {
        "schema": "magireco-ac4902-native416-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
        "family": "ac4902",
        "product_semantics": (
            "duplicate_free_exhaustive_editorial_collection_not_native_single_session"
        ),
        "binary": {"source": bind_source(binary), "gnu_build_id": build_id},
        "inputs": {
            "visual_projection_authority": bind_source(visual_authority_path),
            "event_audio_components": bind_source(event_audio_components_path),
            "z2d_sound_callbacks": bind_source(z2d_sound_callbacks_path),
            "translation": bind_source(translation_path),
            "speaker_identity_overrides": bind_source(speaker_overrides_path),
            "durable_audio_root": str(durable_audio_root.resolve()),
        },
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
        "retained_audio_rows": retained,
        "excluded_audio_rows": excluded,
        "subtitle_cues": subtitles,
        "event_presentations": event_presentations,
        "summary": {
            "events": 64,
            "official_event_component_occurrences": 62,
            "exact_parent_bound_callback_identities": 24,
            "exact_parent_bound_callback_occurrences": 87,
            "retained_audio_occurrences": len(retained),
            "retained_se_occurrences": se_count,
            "retained_voice_occurrences": voice_count,
            "excluded_bgm_occurrences": len(excluded),
            "subtitle_cue_occurrences": len(subtitles),
            "unique_dialogue_request_ids": len(translations),
            "unique_retained_official_ogg_sources": len(
                {row["ogg_name"] for row in retained}
            ),
            "unique_all_bound_official_ogg_sources": len(audio_cache),
            "visual_presentation_frames_before_dedup": EXPECTED_VISUAL_FRAMES,
            "final_presentation_frames_before_dedup": EXPECTED_OUTPUT_FRAMES,
            "tail_hold_event_count": len(EXTENDED_HOLD_EVENTS),
            "tail_hold_frames_total": 78,
        },
        "assertions": {
            "all_64_visual_events_bound": True,
            "all_62_event_audio_components_bound": True,
            "all_87_parent_bound_callback_occurrences_are_event_global": True,
            "only_ac4902_024_sound_551_request_226_is_excluded_as_bgm": True,
            "all_92_se_occurrences_retained": True,
            "all_56_voice_occurrences_retained": True,
            "all_56_voice_occurrences_have_subtitle_cues": True,
            "request_8340_is_authority_bound_to_owner_approved_black_feather_only_in_ac4902_003_and_059": True,
            "six_exact_long_SE_tails_hold_the_last_composed_frame_for_13_frames": True,
            "child_local_timing_without_parent_offset_used": False,
            "P16_P17_P18_reference_count": 0,
            "source_media_modified": False,
            "media_rendered": False,
            "human_playback_approval_inferred": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac4902AudioAuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC4902_EVENT_AUDIO_AUTHORITY.json"
    retained_path = output_dir / "AC4902_RETAINED_AUDIO_ROWS.csv"
    excluded_path = output_dir / "AC4902_EXCLUDED_BGM_ROWS.csv"
    subtitle_path = output_dir / "AC4902_SUBTITLE_CUES.csv"
    presentation_path = output_dir / "AC4902_EVENT_PRESENTATIONS.csv"
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
        "# ac4902 native416 event audio authority\n\n"
        "Exact v187/v188 parent Z2D starts bind 87 reqSound callback occurrences to "
        "event-global time. SOUND_DIVIDE_TBL retains 92 SE and 56 VOICE occurrences; "
        "only ac4902_024 request 226 / sound 551 is excluded as BGM. Request 8340 is "
        "bound to the owner-approved 黒羽/黑羽 identity only in ac4902_003 and "
        "ac4902_059. Six 6.466-second retained SE occurrences extend their 181-frame "
        "visual events by exactly 13 held frames. New exhaustive editions remain "
        "HUMAN_PLAYBACK_REQUIRED.\n",
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
        report_path, retained_path, excluded_path, subtitle_path,
        presentation_path, readme_path, rollback_path,
    ]
    verification = {
        "schema": "magireco-ac4902-native416-audio-verification-v1",
        "status": "PASS_READY_FOR_ROUTE_DEDUP_AUTHORITY",
        "literal_result": (
            "PASS events=64 retained=148 se=92 voice=56 excluded_bgm=1 "
            "subtitles=56 unique_retained_ogg=47 visual_frames=25625 "
            "final_frames=25703 audio_gate=CLOSED"
        ),
        "checks": report["assertions"],
        "summary": report["summary"],
        "outputs": {path.name: bind_source(path) for path in output_files},
    }
    verification_path.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path)
    parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--translation", required=True, type=Path)
    parser.add_argument("--speaker-overrides", required=True, type=Path)
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
        speaker_overrides_path=args.speaker_overrides,
        durable_audio_root=args.durable_audio_root,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS events=64 retained=148 se=92 voice=56 excluded_bgm=1 "
        "subtitles=56 unique_retained_ogg=47 visual_frames=25625 "
        "final_frames=25703 audio_gate=CLOSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
