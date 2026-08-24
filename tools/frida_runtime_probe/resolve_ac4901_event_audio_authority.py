#!/usr/bin/env python3
"""Resolve exact ac4901 event-global audio, subtitles, and strict no-BGM buses."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac4901_gfdirection_presentation_authority import EVENT_IDS
    from .resolve_ac0915_event_audio_authority import _write_csv, bind_source
    from .resolve_ac7206_event_audio_authority import VOLUME_BUS, read_sound_divide_values
except ImportError:  # pragma: no cover - direct script execution
    from build_ac4901_gfdirection_presentation_authority import EVENT_IDS  # type: ignore
    from resolve_ac0915_event_audio_authority import _write_csv, bind_source  # type: ignore
    from resolve_ac7206_event_audio_authority import (  # type: ignore
        VOLUME_BUS,
        read_sound_divide_values,
    )


VOICE_REQUEST_IDS = frozenset({2439, 2740, 8209})
COMPONENT_REQUEST_SOUND_COUNTS = {
    (226, 551): 21,
    (419, 1005): 21,
    (438, 1035): 21,
    (439, 1036): 21,
    (889, 3120): 12,
    (893, 3125): 6,
    (1682, 8100): 36,
    (1683, 8101): 108,
    (1684, 8104): 36,
}
CALLBACK_REQUEST_SOUND_PAIRS = frozenset(
    {
        (450, 1069),
        (451, 1070),
        (453, 1072),
        (893, 3125),
        (894, 3126),
        (2439, 15100),
        (2740, 15498),
        (8209, 26401),
    }
)
NO_COMPONENT_EVENTS = frozenset(
    {"ac4901_091", "ac4901_092", "ac4901_093", "ac4901_094"}
)
BGM_EVENTS = frozenset(
    {
        "ac4901_105",
        "ac4901_112",
        "ac4901_172",
        "ac4901_173",
        "ac4901_174",
        "ac4901_175",
        "ac4901_176",
        "ac4901_177",
        "ac4901_184",
        "ac4901_185",
        "ac4901_186",
        "ac4901_187",
        "ac4901_188",
        "ac4901_189",
        "ac4901_196",
        "ac4901_197",
        "ac4901_198",
        "ac4901_199",
        "ac4901_200",
        "ac4901_201",
        "ac4901_232",
    }
)
EXPECTED_VISUAL_FRAMES = 34236
EXPECTED_RETAINED_AUDIO = 393
EXPECTED_RETAINED_SE = 354
EXPECTED_RETAINED_VOICE = 39
EXPECTED_EXCLUDED_BGM = 21
EXPECTED_UNIQUE_RETAINED_OGG = 15


class Ac4901AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac4901AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def _translation_map(path: Path) -> dict[int, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {int(row["request_id"]): row for row in rows}
    required = {
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
        or document.get("scope")
        != "ac4901_exhaustive_native416_event_global_dialogue"
        or set(result) != set(VOICE_REQUEST_IDS)
        or len(result) != len(rows)
        or any(not required.issubset(row) for row in rows)
        or result[2439]["speaker_ja"] != "環いろは"
        or result[2439]["speaker_zh"] != "环彩羽"
        or result[2740]["speaker_ja"] != "環いろは"
        or result[2740]["speaker_zh"] != "环彩羽"
        or result[8209]["speaker_ja"]
        or result[8209]["speaker_zh"]
    ):
        raise Ac4901AudioAuthorityError("ac4901 translation map dimensions differ")
    return result


def _visual_host_intervals(
    visual: Mapping[str, Any],
) -> tuple[dict[str, dict[str, tuple[int, int]]], dict[str, int]]:
    if (
        visual.get("schema") != "magireco-ac4901-output-projection-authority-v1"
        or visual.get("status")
        != "PASS_READY_FOR_ROUTE_STATE_CARRY_AUDIO_AND_DEDUP_AUTHORITY"
        or visual.get("family") != "ac4901"
        or visual.get("frame_rate") != "30/1"
        or visual.get("output_canvas") != [416, 232]
    ):
        raise Ac4901AudioAuthorityError("ac4901 projection authority differs")
    rows = visual.get("events", [])
    if [row.get("event") for row in rows] != list(EVENT_IDS):
        raise Ac4901AudioAuthorityError("ac4901 projection event order differs")
    frames = {str(row["event"]): int(row["presentation_frame_count"]) for row in rows}
    if len(frames) != 205 or sum(frames.values()) != EXPECTED_VISUAL_FRAMES:
        raise Ac4901AudioAuthorityError("ac4901 visual frame dimensions differ")

    result: dict[str, dict[str, tuple[int, int]]] = {}
    for event_row in rows:
        event = str(event_row["event"])
        intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for row in event_row.get("layers_in_render_pass_order_under_to_top", []):
            intervals[str(row["parent_z2d"])].append(
                (int(row["event_start_frame"]), int(row["event_end_frame_inclusive"]))
            )
        for row in event_row.get("non_movie_text_z2d_nodes", []):
            intervals[str(row["node"])].append(
                (
                    int(row["event_global_start_frame"]),
                    int(row["event_global_end_frame_inclusive"]),
                )
            )
        result[event] = {
            name: (min(start for start, _ in spans), max(end for _, end in spans))
            for name, spans in intervals.items()
        }
        if any(
            start < 0 or end < start or end >= frames[event]
            for start, end in result[event].values()
        ):
            raise Ac4901AudioAuthorityError(f"visual host interval escapes event: {event}")
    if (
        len({name for hosts in result.values() for name in hosts}) != 103
        or sum(len(hosts) for hosts in result.values()) != 463
    ):
        raise Ac4901AudioAuthorityError("ac4901 visual host dimensions differ")
    return result, frames


def _durable_audio_identity(
    root: Path, name: str, cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if name not in cache:
        cache[name] = {"ogg_name": name, "official_source": bind_source(root / name)}
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
    host_intervals, visual_frames = _visual_host_intervals(visual)
    translations = _translation_map(translation_path)

    component_rows = [
        row
        for row in read_csv(event_audio_components_path)
        if row.get("root") == "ac4901"
    ]
    component_counts = Counter(
        (int(row["leaf_request_id"]), int(row["leaf_sound_code"]))
        for row in component_rows
    )
    if (
        len(component_rows) != 282
        or dict(component_counts) != COMPONENT_REQUEST_SOUND_COUNTS
        or {row["primary_animation"] for row in component_rows}
        != set(EVENT_IDS) - set(NO_COMPONENT_EVENTS)
        or any(
            row["smz_matches_leaf_request"] != "yes"
            or row["ogg_duration_match"] != "yes"
            or not row["ogg_name"].endswith(".ogg")
            for row in component_rows
        )
    ):
        raise Ac4901AudioAuthorityError("ac4901 event component set differs")

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
        len(callback_rows) != 8
        or callback_pairs != CALLBACK_REQUEST_SOUND_PAIRS
        or len({row["z2d_name"] for row in callback_rows}) != 7
        or any(
            int(row["exec_frame"]) != 0
            or row["sound_request_match_count"] != "1"
            or row["ogg_exists"] != "yes"
            or not row["ogg_name"].endswith(".ogg")
            for row in callback_rows
        )
    ):
        raise Ac4901AudioAuthorityError("ac4901 callback identity set differs")
    callbacks_by_host: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in callback_rows:
        callbacks_by_host[row["z2d_name"]].append(row)
    callback_occurrences = [
        (event, host, row)
        for event, event_hosts in host_intervals.items()
        for host in event_hosts
        for row in callbacks_by_host.get(host, [])
    ]
    if len(callback_occurrences) != 132:
        raise Ac4901AudioAuthorityError("ac4901 callback occurrence set differs")

    sound_ids = {int(row["leaf_sound_code"]) for row in component_rows}
    sound_ids.update(int(row["sound_resource_id"]) for row in callback_rows)
    build_id, buses = read_sound_divide_values(binary, sound_ids)
    cache: dict[str, dict[str, Any]] = {}
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
            **_durable_audio_identity(durable_audio_root, source["ogg_name"], cache),
            "volume_kind_value": buses[sound_id],
            "volume_bus": bus,
            "timing_evidence": "official_event_audio_component_event_global_start_ms",
        }
        if bus == "BGM":
            if (
                request_id != 226
                or sound_id != 551
                or event not in BGM_EVENTS
            ):
                raise Ac4901AudioAuthorityError(
                    f"unexpected ac4901 BGM component: {event}/{request_id}/{sound_id}"
                )
            row["strict_no_bgm_disposition"] = "EXCLUDE_EXACT_BGM_BUS"
            excluded.append(row)
        elif bus == "SE":
            row["strict_no_bgm_disposition"] = "RETAIN_VERIFIED_SE"
            retained.append(row)
        else:
            raise Ac4901AudioAuthorityError(
                f"ac4901 event component is not SE/BGM: {event}/{request_id}/{bus}"
            )
    if {row["event"] for row in excluded} != set(BGM_EVENTS):
        raise Ac4901AudioAuthorityError("ac4901 exact BGM event set differs")

    subtitles: list[dict[str, Any]] = []
    for event in EVENT_IDS:
        for host, (host_start, host_end) in host_intervals[event].items():
            for callback in callbacks_by_host.get(host, []):
                request_id = int(callback["sound_request_id"])
                sound_id = int(callback["sound_resource_id"])
                bus = VOLUME_BUS[buses[sound_id]]
                if bus not in {"SE", "VOICE"}:
                    raise Ac4901AudioAuthorityError(
                        f"callback bus differs: {event}/{host}/{request_id}/{bus}"
                    )
                start_frame = host_start + int(callback["exec_frame"])
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
                    **_durable_audio_identity(
                        durable_audio_root, callback["ogg_name"], cache
                    ),
                    "volume_kind_value": buses[sound_id],
                    "volume_bus": bus,
                    "strict_no_bgm_disposition": f"RETAIN_VERIFIED_{bus}",
                    "timing_evidence": (
                        "v195_v198_exact_event_global_parent_host_start_plus_exact_child_callback_frame_0"
                    ),
                }
                retained.append(row)
                if bus == "VOICE":
                    translation = translations.get(request_id)
                    if translation is None:
                        raise Ac4901AudioAuthorityError(
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
        if audio_tail > visual_count:
            raise Ac4901AudioAuthorityError(
                f"unexpected ac4901 audio tail extension: {event}/{visual_count}/{audio_tail}"
            )
        for cue in (row for row in subtitles if row["event"] == event):
            cue["end_ms"] = min(
                round(visual_count * 1000 / 30),
                max(int(cue["voice_end_ms"]), int(cue["parent_host_end_ms"])),
            )
            if int(cue["end_ms"]) <= int(cue["start_ms"]):
                raise Ac4901AudioAuthorityError(
                    f"subtitle interval is empty: {event}/{cue['voice_request_id']}"
                )
        event_presentations.append(
            {
                "event": event,
                "visual_presentation_frames": visual_count,
                "retained_audio_tail_frame_exclusive": audio_tail,
                "final_presentation_frames": visual_count,
                "final_presentation_seconds": visual_count / 30,
                "tail_hold_frames": 0,
                "tail_policy": "exact_visual_presentation_extent",
                "retained_audio_occurrences": len(rows),
                "excluded_bgm_occurrences": sum(
                    row["event"] == event for row in excluded
                ),
                "native_width": 416,
                "native_height": 232,
                "frame_rate": "30/1",
                "requires_prior_frame_underlay": event == "ac4901_091",
            }
        )

    voice_count = sum(row["volume_bus"] == "VOICE" for row in retained)
    se_count = sum(row["volume_bus"] == "SE" for row in retained)
    if (
        len(retained) != EXPECTED_RETAINED_AUDIO
        or se_count != EXPECTED_RETAINED_SE
        or voice_count != EXPECTED_RETAINED_VOICE
        or len(excluded) != EXPECTED_EXCLUDED_BGM
        or len(subtitles) != EXPECTED_RETAINED_VOICE
        or len(cache) != 16
        or len({row["ogg_name"] for row in retained}) != EXPECTED_UNIQUE_RETAINED_OGG
        or sum(row["final_presentation_frames"] for row in event_presentations)
        != EXPECTED_VISUAL_FRAMES
        or any(row["tail_hold_frames"] for row in event_presentations)
    ):
        raise Ac4901AudioAuthorityError("ac4901 audio authority dimensions differ")

    return {
        "schema": "magireco-ac4901-native416-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "PASS_READY_FOR_ROUTE_STATE_CARRY_AND_DEDUP_AUTHORITY",
        "family": "ac4901",
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
            "events": 205,
            "official_event_component_occurrences": 282,
            "exact_parent_bound_callback_identities": 8,
            "exact_parent_bound_callback_occurrences": 132,
            "retained_audio_occurrences": len(retained),
            "retained_se_occurrences": se_count,
            "retained_voice_occurrences": voice_count,
            "excluded_bgm_occurrences": len(excluded),
            "subtitle_cue_occurrences": len(subtitles),
            "unique_dialogue_request_ids": len(translations),
            "unique_retained_official_ogg_sources": len(
                {row["ogg_name"] for row in retained}
            ),
            "unique_all_bound_official_ogg_sources": len(cache),
            "visual_presentation_frames_before_dedup": EXPECTED_VISUAL_FRAMES,
            "final_presentation_frames_before_dedup": EXPECTED_VISUAL_FRAMES,
            "tail_hold_event_count": 0,
            "tail_hold_frames_total": 0,
            "prior_underlay_event_count": 1,
        },
        "assertions": {
            "all_205_visual_events_bound": True,
            "all_282_event_audio_components_bound": True,
            "all_132_parent_bound_callback_occurrences_are_event_global": True,
            "only_21_request_226_sound_551_rows_are_excluded_as_bgm": True,
            "all_354_se_occurrences_retained": True,
            "all_39_voice_occurrences_retained": True,
            "all_39_voice_occurrences_have_subtitle_cues": True,
            "ac4901_091_prior_frame_underlay_requirement_preserved": True,
            "child_local_timing_without_parent_offset_used": False,
            "P16_P17_P18_reference_count": 0,
            "source_media_modified": False,
            "media_rendered": False,
            "human_playback_approval_inferred": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac4901AudioAuthorityError(f"immutable output already exists: {output_dir}")
    stage = output_dir.parent / (
        f".{output_dir.name}.staging-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    stage.mkdir(parents=True)
    try:
        report_path = stage / "AC4901_EVENT_AUDIO_AUTHORITY.json"
        retained_path = stage / "AC4901_RETAINED_AUDIO_ROWS.csv"
        excluded_path = stage / "AC4901_EXCLUDED_BGM_ROWS.csv"
        subtitle_path = stage / "AC4901_SUBTITLE_CUES.csv"
        presentation_path = stage / "AC4901_EVENT_PRESENTATIONS.csv"
        readme_path = stage / "README.md"
        rollback_path = stage / "ROLLBACK.ps1"
        verification_path = stage / "VERIFICATION_RECORD.json"

        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv(retained_path, list(report["retained_audio_rows"]))
        _write_csv(excluded_path, list(report["excluded_audio_rows"]))
        _write_csv(subtitle_path, list(report["subtitle_cues"]))
        _write_csv(presentation_path, list(report["event_presentations"]))
        readme_path.write_text(
            "# ac4901 native416 event audio authority\n\n"
            "All 282 official event-audio components and 132 parent-bound reqSound "
            "callback occurrences are resolved at event-global time. Exact "
            "SOUND_DIVIDE_TBL values retain 354 SE and 39 VOICE occurrences; only "
            "21 request 226 / sound 551 BGM occurrences are excluded. No retained "
            "audio exceeds its exact visual event extent. ac4901_091 remains "
            "route-state-dependent and must inherit the preceding composed frame.\n",
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
        verification = {
            "schema": "magireco-ac4901-native416-audio-verification-v1",
            "status": "PASS_READY_FOR_ROUTE_STATE_CARRY_AND_DEDUP_AUTHORITY",
            "literal_result": (
                "PASS events=205 retained=393 se=354 voice=39 excluded_bgm=21 "
                "subtitles=39 unique_retained_ogg=15 visual_frames=34236 "
                "final_frames=34236 prior_underlay_events=1 audio_gate=CLOSED"
            ),
            "checks": report["assertions"],
            "summary": report["summary"],
            "outputs": {path.name: bind_source(path) for path in output_files},
        }
        verification_path.write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stage.replace(output_dir)
    except Exception:
        raise


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
    write_outputs(report, args.output_dir)
    print(
        "PASS events=205 retained=393 se=354 voice=39 excluded_bgm=21 "
        "subtitles=39 unique_retained_ogg=15 visual_frames=34236 "
        "final_frames=34236 prior_underlay_events=1 audio_gate=CLOSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
