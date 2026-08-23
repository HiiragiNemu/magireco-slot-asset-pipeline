#!/usr/bin/env python3
"""Resolve ac7205 native-416 event audio, subtitles, and unique-content tails."""

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
    from resolve_ac7206_event_audio_authority import VOLUME_BUS, read_sound_divide_values  # type: ignore


NATIVE416_EVENTS = tuple(
    f"ac7205_{index:03d}" for index in (*range(1, 18), *range(19, 23))
)
EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER = (
    "ac7205_001", "ac7205_003", "ac7205_004", "ac7205_005", "ac7205_006",
    "ac7205_002", "ac7205_019", "ac7205_020", "ac7205_021", "ac7205_022",
    "ac7205_007", "ac7205_011", "ac7205_012", "ac7205_013", "ac7205_014",
    "ac7205_008", "ac7205_009", "ac7205_010", "ac7205_015", "ac7205_016",
    "ac7205_017",
)
EXPECTED_EVENT_COMPONENTS = {
    "ac7205_001": {(10385, 42300, 0)},
    "ac7205_002": {(10386, 42301, 0)},
    "ac7205_003": {(10387, 42302, 0)},
    "ac7205_004": {(10387, 42302, 0)},
    "ac7205_005": {(10387, 42302, 0), (10388, 42303, 334)},
    "ac7205_006": {(10387, 42302, 0), (10389, 42304, 334)},
    "ac7205_007": {(10390, 42305, 0)},
    "ac7205_008": {(10390, 42305, 0), (10392, 42307, 680)},
    "ac7205_009": {(10390, 42305, 0), (10393, 42308, 680)},
    "ac7205_010": {(10390, 42305, 0), (10394, 42309, 680)},
    "ac7205_011": {(10391, 42306, 0)},
    "ac7205_012": {(10392, 42307, 0)},
    "ac7205_013": {(10393, 42308, 0)},
    "ac7205_014": {(10394, 42309, 0)},
    "ac7205_015": {(419, 1005, 0), (226, 551, 1409), (10395, 42310, 449)},
    "ac7205_016": {(10390, 42305, 0), (10394, 42309, 680), (419, 1005, 2444), (226, 551, 3344)},
    "ac7205_017": {(10394, 42309, 0), (419, 1005, 1770), (226, 551, 2384)},
    "ac7205_019": {(10387, 42302, 0)},
    "ac7205_020": {(10387, 42302, 0)},
    "ac7205_021": {(10387, 42302, 0), (10388, 42303, 334)},
    "ac7205_022": {(10387, 42302, 0), (10389, 42304, 334)},
}
EXPECTED_VOICE_BY_EVENT = {event: () for event in NATIVE416_EVENTS}
EXPECTED_VOICE_BY_EVENT.update({
    "ac7205_008": (("cap7205_news_qb_002", 8312, 21),),
    "ac7205_009": (("cap7205_news_qb_003", 8313, 21),),
    "ac7205_010": (("cap7205_news_qb_004", 8310, 21),),
    "ac7205_011": (("cap7205_news_qb_001", 8311, 1),),
    "ac7205_012": (("cap7205_news_qb_002", 8312, 1),),
    "ac7205_013": (("cap7205_news_qb_003", 8313, 1),),
    "ac7205_014": (("cap7205_news_qb_004", 8310, 1),),
    "ac7205_016": (("cap7205_news_qb_005", 8314, 21),),
    "ac7205_017": (("cap7205_news_qb_005", 8314, 1),),
})
EXPECTED_UNIQUE_VIDEO_CONTENT_FRAMES = dict(zip(NATIVE416_EVENTS, (
    58, 58, 130, 510, 160, 100, 20, 163, 140, 185, 60, 143, 120, 165,
    101, 155, 135, 130, 510, 160, 100,
)))
EXPECTED_PRESENTATION_FRAMES = dict(zip(NATIVE416_EVENTS, (
    120, 152, 130, 510, 160, 170, 77, 186, 150, 211, 100, 166, 130, 191,
    114, 155, 135, 130, 510, 160, 170,
)))
EXPECTED_BGM_COMPONENTS = {
    ("ac7205_015", 226, 551, 1409),
    ("ac7205_016", 226, 551, 3344),
    ("ac7205_017", 226, 551, 2384),
}
CODE_AUTHORITY = (
    ("0x1445c54", "SOUND_DIVIDE_TBL", "indexes one exact volume-kind byte by sound resource id"),
    ("volume-kind 0", "setAppVolume index 0", "maps table value 0 to BGM"),
    ("volume-kind 1", "setAppVolume index 1", "maps table value 1 to SE"),
    ("volume-kind 2", "setAppVolume index 2", "maps table value 2 to VOICE"),
    ("0x42b12bc", "zg::CGFDirectionNodeMotionZ2D::GetKey", "key byte +0x1e bit 0 persists after nominal end"),
    ("0x42b342c", "zg::CGFDirectionNodeMotionZ2D::SetKeyTime", "key byte +0x1d selects clamp/full-scene/scene-loop-point playback"),
)


class Ac7205AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac7205AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def translation_map(path: Path) -> dict[int, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {int(row["request_id"]): row for row in rows}
    expected = {value[1] for values in EXPECTED_VOICE_BY_EVENT.values() for value in values}
    if (
        document.get("schema") != "magireco-reviewed-story-zh-dialogue-map-v1"
        or document.get("scope") != "ac7205_exhaustive_native416_runtime_bound_dialogue"
        or set(result) != expected or len(result) != len(rows)
    ):
        raise Ac7205AudioAuthorityError("ac7205 translation map dimensions differ")
    return result


def durable_audio(root: Path, name: str) -> str:
    path = (root / name).resolve()
    if not path.is_file():
        raise Ac7205AudioAuthorityError(f"durable official OGG is absent: {path}")
    return str(path)


def caption_rows(visual: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    runtime = visual.get("runtime_bindings", {}).get("events", {})
    if set(runtime) != set(NATIVE416_EVENTS) | {"ac7205_018"}:
        raise Ac7205AudioAuthorityError("ac7205 visual runtime event set differs")
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for event in NATIVE416_EVENTS:
        expected = {value[0] for value in EXPECTED_VOICE_BY_EVENT[event]}
        rows = {row["parent_z2d"]: row for row in runtime[event] if row["parent_z2d"] in expected}
        if set(rows) != expected:
            raise Ac7205AudioAuthorityError(f"caption host set differs: {event}")
        result[event] = rows
    return result


def event_visual_plan(visual: Mapping[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    chunks = {row["name"]: row for row in visual.get("z2d_chunks", [])}
    runtime = visual["runtime_bindings"]["events"]
    plans: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    for event in NATIVE416_EVENTS:
        primary: list[dict[str, Any]] = []
        overlays: list[dict[str, Any]] = []
        for binding in runtime[event]:
            parent = binding["parent_z2d"]
            chunk = chunks.get(parent)
            if not chunk or not chunk.get("movie_layers"):
                continue
            native_rows = [
                row for row in chunk["movie_layers"]
                if row.get("content_class") == "native416_family_source"
            ]
            if not native_rows:
                continue
            canonical_rows = [
                row for row in native_rows
                if row.get("source_identity_disposition") == "CANONICAL_SOURCE_IDENTITY"
            ]
            aliases = [
                row["z2d_reference"] for row in native_rows
                if row.get("source_identity_disposition")
                == "BYTE_IDENTICAL_LOOP_ALIAS_NOT_A_SEPARATE_SOURCE_IDENTITY"
            ]
            source = {
                "event": event,
                "parent_z2d": parent,
                "event_global_start_frame": int(binding["event_global_start_frame"]),
                "runtime_motion_flags": binding["motion_key_flags"],
                "runtime_playback_mode": binding["motion_playback_mode"],
                "runtime_key_persists": bool(binding["motion_key_persists_after_nominal_end"]),
                "z2d_scene_loop_frame": int(chunk["header"]["scene_loop_frame"]),
                "canonical_unique_frames": sum(int(row["frame_count"]) for row in canonical_rows),
                "canonical_dgm_references": [row["z2d_reference"] for row in canonical_rows],
                "canonical_media_paths": [row["media_path"] for row in canonical_rows],
                "byte_identical_aliases_omitted": aliases,
            }
            if parent.startswith("ac7205_news_waku_"):
                source["visual_role"] = "runtime_looping_frame_overlay"
                overlays.append(source)
            else:
                source["visual_role"] = "primary_unique_visual_content"
                primary.append(source)
        if not primary:
            raise Ac7205AudioAuthorityError(f"no native416 primary visual source: {event}")
        first = min(row["event_global_start_frame"] for row in primary)
        visible_end = max(
            row["event_global_start_frame"] + row["canonical_unique_frames"]
            for row in primary
        )
        total = visible_end - first
        if total != EXPECTED_UNIQUE_VIDEO_CONTENT_FRAMES[event]:
            raise Ac7205AudioAuthorityError(f"deduplicated visual content differs: {event}/{total}")
        for row in primary + overlays:
            row["normalized_start_frame"] = row["event_global_start_frame"] - first
            row["primary_visual_origin_event_frame"] = first
            plans.append(row)
        totals[event] = total
    return totals, plans


def build_report(
    *, binary: Path, visual_authority_path: Path, event_audio_components_path: Path,
    z2d_sound_callbacks_path: Path, translation_path: Path, durable_audio_root: Path,
) -> dict[str, Any]:
    visual = json.loads(visual_authority_path.read_text(encoding="utf-8"))
    if (
        visual.get("schema") != "magireco-ac7205-movielayer-runtime-reachability-authority-v1"
        or visual.get("status") != "passed"
        or visual.get("decision", {}).get("native416_visual_reachability_gate") != "CLOSED"
        or tuple(visual.get("decision", {}).get("native416_exhaustive_editorial_order", []))
        != EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER
    ):
        raise Ac7205AudioAuthorityError("ac7205 visual authority differs")
    captions = caption_rows(visual)
    video_frames, visual_plan = event_visual_plan(visual)
    translations = translation_map(translation_path)

    component_rows = [
        row for row in read_csv(event_audio_components_path)
        if row.get("root") == "ac7205" and row.get("primary_animation") in NATIVE416_EVENTS
    ]
    by_event: dict[str, list[dict[str, Any]]] = {event: [] for event in NATIVE416_EVENTS}
    for row in component_rows:
        by_event[row["primary_animation"]].append({
            "event": row["primary_animation"],
            "source_kind": "event_audio_component",
            "request_id": int(row["leaf_request_id"]),
            "sound_id": int(row["leaf_sound_code"]),
            "code_name": row["leaf_code_name"],
            "start_ms": int(row["start_ms"]),
            "duration_ms": int(row["duration_ms"]),
            "ogg_name": row["ogg_name"],
        })
    observed = {
        event: {(row["request_id"], row["sound_id"], row["start_ms"]) for row in rows}
        for event, rows in by_event.items()
    }
    if observed != EXPECTED_EVENT_COMPONENTS:
        raise Ac7205AudioAuthorityError(f"event component set differs: {observed}")

    expected_z2d = {value[0] for values in EXPECTED_VOICE_BY_EVENT.values() for value in values}
    callbacks = {
        row["z2d_name"]: row for row in read_csv(z2d_sound_callbacks_path)
        if row.get("z2d_name") in expected_z2d
    }
    if set(callbacks) != expected_z2d:
        raise Ac7205AudioAuthorityError("ac7205 callback set differs")
    sound_ids = {row["sound_id"] for rows in by_event.values() for row in rows}
    sound_ids.update(int(row["sound_resource_id"]) for row in callbacks.values())
    build_id, buses = read_sound_divide_values(binary, sound_ids)

    retained_audio: list[dict[str, Any]] = []
    excluded_audio: list[dict[str, Any]] = []
    for event, rows in by_event.items():
        for row in rows:
            bus = VOLUME_BUS[buses[row["sound_id"]]]
            row.update({
                "ogg_path": durable_audio(durable_audio_root, row["ogg_name"]),
                "volume_kind_value": buses[row["sound_id"]],
                "volume_bus": bus,
                "timing_evidence": "official_event_audio_component_event_global_start",
            })
            if bus == "BGM":
                row["strict_no_bgm_disposition"] = "EXCLUDE_VERIFIED_BGM"
                excluded_audio.append(row)
            elif bus == "SE":
                row["strict_no_bgm_disposition"] = "RETAIN_VERIFIED_SE"
                retained_audio.append(row)
            else:
                raise Ac7205AudioAuthorityError(
                    f"unexpected event component bus: {event}/{row['request_id']}/{bus}"
                )
    excluded_contract = {
        (row["event"], row["request_id"], row["sound_id"], row["start_ms"])
        for row in excluded_audio
    }
    if excluded_contract != EXPECTED_BGM_COMPONENTS:
        raise Ac7205AudioAuthorityError(f"excluded BGM component set differs: {excluded_contract}")

    subtitle_cues: list[dict[str, Any]] = []
    for event, specs in EXPECTED_VOICE_BY_EVENT.items():
        for z2d_name, request_id, start_frame in specs:
            callback = callbacks[z2d_name]
            caption = captions[event][z2d_name]
            translation = translations[request_id]
            if (
                int(callback["sound_request_id"]) != request_id
                or int(callback["exec_frame"]) != 0
                or callback["sound_request_match_count"] != "1"
                or int(caption["event_global_start_frame"]) != start_frame
                or caption["motion_key_flags"] != [0, 2, 1]
                or caption["motion_playback_mode"] != "loop_full_z2d_scene"
            ):
                raise Ac7205AudioAuthorityError(
                    f"runtime reqSound/caption binding differs: {event}/{request_id}"
                )
            sound_id = int(callback["sound_resource_id"])
            if VOLUME_BUS[buses[sound_id]] != "VOICE":
                raise Ac7205AudioAuthorityError(f"reqSound is not VOICE bus: {event}/{request_id}")
            start_ms = round(start_frame * 1000 / 30)
            duration_ms = int(callback["sound_duration_ms"])
            retained_audio.append({
                "event": event, "source_kind": "z2d_req_sound", "z2d_name": z2d_name,
                "request_id": request_id, "sound_id": sound_id,
                "code_name": callback["sound_code_name"], "start_frame": start_frame,
                "start_ms": start_ms, "duration_ms": duration_ms,
                "ogg_name": callback["ogg_name"],
                "ogg_path": durable_audio(durable_audio_root, callback["ogg_name"]),
                "volume_kind_value": buses[sound_id], "volume_bus": "VOICE",
                "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE",
                "timing_evidence": "runtime_parent_scene_z2d_start_plus_exact_child_callback_frame_0",
            })
            if translation["subtitle_end_policy"] == "graphical_parent_motion_end":
                end_frame_exclusive = int(caption["event_global_end_frame_inclusive"]) + 1
                # Milliseconds are only a transport projection of the exact frame edge.
                # Floor avoids crossing into the following CFR frame (for example,
                # frame 191 is 6366.6..., while 6367 ms would quantize to frame 192).
                end_ms = end_frame_exclusive * 1000 // 30
            elif translation["subtitle_end_policy"] == "official_voice_duration":
                end_ms = start_ms + duration_ms
                end_frame_exclusive = math.ceil(end_ms * 30 / 1000)
            else:
                raise Ac7205AudioAuthorityError(f"unknown subtitle end policy: {request_id}")
            subtitle_cues.append({
                "event": event, "z2d_name": z2d_name, "voice_request_id": request_id,
                "start_frame": start_frame, "start_ms": start_ms,
                "end_frame_exclusive": end_frame_exclusive, "end_ms": end_ms,
                "speaker_ja": translation["speaker_ja"], "speaker_zh": translation["speaker_zh"],
                "ja": translation["render_ja"], "zh": translation["render_zh"],
                "translation_status": translation["status"],
                "subtitle_end_policy": translation["subtitle_end_policy"],
                "evidence": "runtime_parent_scene_z2d_start_and_official_reqSound",
            })

    retained_audio.sort(key=lambda row: (row["event"], row["start_ms"], row["request_id"]))
    excluded_audio.sort(key=lambda row: (row["event"], row["start_ms"], row["request_id"]))
    subtitle_cues.sort(key=lambda row: (row["event"], row["start_ms"], row["voice_request_id"]))
    presentation_rows: list[dict[str, Any]] = []
    for event in NATIVE416_EVENTS:
        event_audio = [row for row in retained_audio if row["event"] == event]
        audio_tail = max(
            math.ceil((row["start_ms"] + row["duration_ms"]) * 30 / 1000)
            for row in event_audio
        )
        subtitle_tail = max(
            [row["end_frame_exclusive"] for row in subtitle_cues if row["event"] == event]
            or [0]
        )
        frames = max(video_frames[event], audio_tail, subtitle_tail)
        if frames != EXPECTED_PRESENTATION_FRAMES[event]:
            raise Ac7205AudioAuthorityError(f"event presentation frame count differs: {event}/{frames}")
        primary_rows = [
            row for row in visual_plan
            if row["event"] == event and row["visual_role"] == "primary_unique_visual_content"
        ]
        visible_end = max(
            row["event_global_start_frame"] + row["canonical_unique_frames"]
            for row in primary_rows
        )
        presentation_rows.append({
            "event": event,
            "unique_visual_content_frames": video_frames[event],
            "unique_visual_event_end_frame_exclusive": visible_end,
            "retained_audio_tail_frames": audio_tail,
            "subtitle_tail_frames": subtitle_tail,
            "presentation_frames": frames,
            "post_visual_tail_extension_frames": max(0, frames - visible_end),
            "tail_extension_policy": "preserve_runtime_overlay_and_caption_timing_without_replaying_byte_identical_dgm_alias",
            "native_width": 416, "native_height": 232, "frame_rate": "30/1",
        })

    if len(retained_audio) != 41 or len(excluded_audio) != 3 or len(subtitle_cues) != 9:
        raise Ac7205AudioAuthorityError("ac7205 audio dimensions differ")
    return {
        "schema": "magireco-ac7205-native416-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "passed", "family": "ac7205",
        "binary": {
            "path": str(binary.resolve()), "size": binary.stat().st_size,
            "gnu_build_id": build_id,
        },
        "inputs": {
            "visual_authority": str(visual_authority_path.resolve()),
            "event_audio_components": str(event_audio_components_path.resolve()),
            "z2d_sound_callbacks": str(z2d_sound_callbacks_path.resolve()),
            "translation": str(translation_path.resolve()),
            "durable_audio_root": str(durable_audio_root.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "event_visual_source_plan": visual_plan,
        "retained_audio_rows": retained_audio,
        "excluded_audio_rows": excluded_audio,
        "subtitle_cues": subtitle_cues,
        "event_presentations": presentation_rows,
        "decision": {
            "native416_events": list(NATIVE416_EVENTS),
            "editorial_order": list(EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER),
            "strict_no_bgm_gate": "CLOSED_THREE_EXACT_BGM_ROWS_EXCLUDED",
            "event_global_voice_subtitle_gate": "CLOSED",
            "event_presentation_tail_gate": "CLOSED",
            "byte_identical_visual_alias_gate": "CLOSED_TWO_DGM_ALIASES_OMITTED",
            "total_presentation_frames": sum(row["presentation_frames"] for row in presentation_rows),
            "expected_longform_seconds": sum(row["presentation_frames"] for row in presentation_rows) / 30,
            "old_short_route_products": "SUPERSEDED_AS_PRIMARY_PRODUCT_BY_EXHAUSTIVE_LONGFORM",
            "owner_playback_status": "HUMAN_PLAYBACK_REQUIRED",
        },
        "assertions": {
            "event_audio_component_occurrences": len(component_rows),
            "runtime_voice_occurrences": len(subtitle_cues),
            "retained_audio_occurrences": len(retained_audio),
            "retained_se_occurrences": sum(row["volume_bus"] == "SE" for row in retained_audio),
            "retained_voice_occurrences": sum(row["volume_bus"] == "VOICE" for row in retained_audio),
            "excluded_bgm_occurrences": len(excluded_audio),
            "subtitle_cues": len(subtitle_cues),
            "presentation_frames": sum(row["presentation_frames"] for row in presentation_rows),
            "all_durable_ogg_files_exist": True,
            "all_components_sound_divide_classified": True,
            "all_callbacks_are_voice_bus": True,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    fields = list(dict.fromkeys(field for row in rows for field in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            })


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac7205AudioAuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC7205_EVENT_AUDIO_AUTHORITY.json"
    retained_path = output_dir / "AC7205_RETAINED_AUDIO_ROWS.csv"
    excluded_path = output_dir / "AC7205_EXCLUDED_BGM_ROWS.csv"
    subtitle_path = output_dir / "AC7205_SUBTITLE_CUES.csv"
    visual_path = output_dir / "AC7205_EVENT_VISUAL_SOURCE_PLAN.csv"
    presentation_path = output_dir / "AC7205_EVENT_PRESENTATIONS.csv"
    verify_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(retained_path, report["retained_audio_rows"])
    write_csv(excluded_path, report["excluded_audio_rows"])
    write_csv(subtitle_path, report["subtitle_cues"])
    write_csv(visual_path, report["event_visual_source_plan"])
    write_csv(presentation_path, report["event_presentations"])
    readme_path.write_text(
        "# ac7205 native416 event-global audio authority\n\n"
        "Compiled SOUND_DIVIDE_TBL classifies 32 event components as SE, nine parent-bound reqSound occurrences as VOICE, and only request 226 / sound 551 in events 015-017 as BGM. The three BGM rows are explicitly excluded. IDA-decoded Z2D motion-key modes bind every caption and loop/tail decision; two byte-identical DGM loop aliases are omitted as additional source identities. The 21 exhaustive native-416 presentations total 3827 frames (127.567 s) before chapter joins. New none/JA/ZH longforms remain HUMAN_PLAYBACK_REQUIRED.\n",
        encoding="utf-8",
    )
    verify_path.write_text(json.dumps({
        "schema": "magireco-ac7205-native416-audio-verification-v1",
        "status": "passed", "checks": report["assertions"],
        "decision": report["decision"],
        "outputs": [
            report_path.name, retained_path.name, excluded_path.name, subtitle_path.name,
            visual_path.name, presentation_path.name, readme_path.name,
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
        binary=args.binary, visual_authority_path=args.visual_authority,
        event_audio_components_path=args.event_audio_components,
        z2d_sound_callbacks_path=args.z2d_sound_callbacks,
        translation_path=args.translation, durable_audio_root=args.durable_audio_root,
    )
    write_outputs(report, args.output_dir)
    print("PASS events=21 components=35 retained_se=32 voices=9 subtitles=9 excluded_bgm=3 frames=3827 audio_gate=CLOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
