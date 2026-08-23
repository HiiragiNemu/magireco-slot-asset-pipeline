#!/usr/bin/env python3
"""Resolve ac7210 native-416 event audio, subtitles, and presentation tails."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping

try:
    from .resolve_ac7206_event_audio_authority import VOLUME_BUS, read_sound_divide_values
    from .resolve_ac7210_movie_layer_reachability import (
        EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER,
        NATIVE416_STORY_EVENTS,
    )
except ImportError:  # direct script execution
    from resolve_ac7206_event_audio_authority import VOLUME_BUS, read_sound_divide_values  # type: ignore
    from resolve_ac7210_movie_layer_reachability import (  # type: ignore
        EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER,
        NATIVE416_STORY_EVENTS,
    )


EXPECTED_EVENT_COMPONENTS = {
    "ac7210_001": {(2257, 11200, 0)},
    "ac7210_002": {(2258, 11201, 0)},
    "ac7210_003": {(2259, 11202, 0)},
    "ac7210_004": {(2260, 11203, 0)},
    "ac7210_005": {(2258, 11201, 0), (2261, 11204, 510)},
}
EXPECTED_VOICE_BY_EVENT = {
    "ac7210_001": (("cap7210_hobaku_yac_001", 3279, 30),),
    "ac7210_002": (),
    "ac7210_003": (),
    "ac7210_004": (
        ("cap7210_hobaku_yac_004", 3280, 65),
        ("cap7210_hobaku_tur_005", 3594, 65),
    ),
    "ac7210_005": (("cap7210_hobaku_tur_002", 3593, 15),),
}
EXPECTED_VIDEO_CONTENT_FRAMES = {
    "ac7210_001": 255,
    "ac7210_002": 150,
    "ac7210_003": 125,
    "ac7210_004": 214,
    "ac7210_005": 430,
}
EXPECTED_PRESENTATION_FRAMES = {
    "ac7210_001": 255,
    "ac7210_002": 233,
    "ac7210_003": 222,
    "ac7210_004": 214,
    "ac7210_005": 430,
}
CODE_AUTHORITY = (
    ("0x1445c54", "SOUND_DIVIDE_TBL", "indexes one exact volume-kind byte by sound resource id"),
    ("volume-kind 0", "setAppVolume index 0", "maps table value 0 to BGM"),
    ("volume-kind 1", "setAppVolume index 1", "maps table value 1 to SE"),
    ("volume-kind 2", "setAppVolume index 2", "maps table value 2 to VOICE"),
)


class Ac7210AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac7210AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def _translation_map(path: Path) -> dict[int, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {int(row["request_id"]): row for row in rows}
    expected = {value[1] for rows in EXPECTED_VOICE_BY_EVENT.values() for value in rows}
    if (
        document.get("schema") != "magireco-reviewed-story-zh-dialogue-map-v1"
        or document.get("scope") != "ac7210_exhaustive_native416_runtime_bound_dialogue"
        or set(result) != expected
        or len(result) != len(rows)
    ):
        raise Ac7210AudioAuthorityError("ac7210 translation map dimensions differ")
    return result


def _durable_audio_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_file():
        raise Ac7210AudioAuthorityError(f"durable official OGG is absent: {path}")
    return path


def _caption_rows(visual: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    runtime = visual.get("runtime_bindings", {}).get("events", {})
    if set(runtime) != set(f"ac7210_{index:03d}" for index in range(1, 9)):
        raise Ac7210AudioAuthorityError("ac7210 visual runtime event set differs")
    result = {}
    for event in NATIVE416_STORY_EVENTS:
        rows = {
            row["parent_z2d"]: row
            for row in runtime[event]
            if row.get("role") == "caption_audio_host"
        }
        expected = {value[0] for value in EXPECTED_VOICE_BY_EVENT[event]}
        if set(rows) != expected:
            raise Ac7210AudioAuthorityError(f"caption host set differs: {event}")
        result[event] = rows
    return result


def _video_content_frames(visual: Mapping[str, Any]) -> dict[str, int]:
    grouped: dict[str, list[dict[str, Any]]] = {event: [] for event in NATIVE416_STORY_EVENTS}
    for row in visual.get("movie_layers", []):
        parent = row.get("parent_z2d")
        if parent in grouped and row.get("content_class") == "native416_story_visual":
            if row.get("audience_dedup_disposition") != "CANONICAL_RETAIN_ONCE":
                continue
            grouped[parent].append(row)
    result = {}
    for event, rows in grouped.items():
        rows.sort(key=lambda row: int(row["start_frame"]))
        result[event] = sum(int(row["media_probe"]["frame_count"]) for row in rows)
    if result != EXPECTED_VIDEO_CONTENT_FRAMES:
        raise Ac7210AudioAuthorityError(f"deduplicated story frame totals differ: {result}")
    return result


def build_report(
    *, binary: Path, visual_authority_path: Path, event_audio_components_path: Path,
    z2d_sound_callbacks_path: Path, translation_path: Path, durable_audio_root: Path,
    legacy_manifest_001_path: Path,
) -> dict[str, Any]:
    visual = json.loads(visual_authority_path.read_text(encoding="utf-8"))
    if (
        visual.get("schema") != "magireco-ac7210-movielayer-runtime-reachability-authority-v1"
        or visual.get("status") != "passed"
        or visual.get("decision", {}).get("native416_visual_reachability_gate") != "CLOSED"
    ):
        raise Ac7210AudioAuthorityError("ac7210 visual authority differs")
    captions = _caption_rows(visual)
    video_frames = _video_content_frames(visual)
    translations = _translation_map(translation_path)

    component_rows = [
        row for row in read_csv(event_audio_components_path)
        if row.get("root") == "ac7210" and row.get("primary_animation") in NATIVE416_STORY_EVENTS
    ]
    by_event: dict[str, list[dict[str, Any]]] = {event: [] for event in NATIVE416_STORY_EVENTS}
    for row in component_rows:
        by_event[row["primary_animation"]].append({
            "event": row["primary_animation"], "source_kind": "event_audio_component",
            "request_id": int(row["leaf_request_id"]), "sound_id": int(row["leaf_sound_code"]),
            "code_name": row["leaf_code_name"], "start_ms": int(row["start_ms"]),
            "duration_ms": int(row["duration_ms"]), "ogg_name": row["ogg_name"],
        })
    observed = {
        event: {(row["request_id"], row["sound_id"], row["start_ms"]) for row in rows}
        for event, rows in by_event.items()
    }
    if observed != EXPECTED_EVENT_COMPONENTS:
        raise Ac7210AudioAuthorityError(f"event component set differs: {observed}")

    expected_z2d = {value[0] for rows in EXPECTED_VOICE_BY_EVENT.values() for value in rows}
    callbacks = {
        row["z2d_name"]: row for row in read_csv(z2d_sound_callbacks_path)
        if row.get("z2d_name") in expected_z2d
    }
    if set(callbacks) != expected_z2d:
        raise Ac7210AudioAuthorityError("ac7210 native416 callback set differs")
    sound_ids = {row["sound_id"] for rows in by_event.values() for row in rows}
    sound_ids.update(int(row["sound_resource_id"]) for row in callbacks.values())
    build_id, buses = read_sound_divide_values(binary, sound_ids)

    audio_rows: list[dict[str, Any]] = []
    for event, rows in by_event.items():
        for row in rows:
            bus = VOLUME_BUS[buses[row["sound_id"]]]
            if bus != "SE":
                raise Ac7210AudioAuthorityError(f"native416 component is not SE bus: {event}/{row['request_id']}")
            row.update({
                "ogg_path": str(_durable_audio_path(durable_audio_root, row["ogg_name"])),
                "volume_kind_value": buses[row["sound_id"]], "volume_bus": bus,
                "strict_no_bgm_disposition": "RETAIN_VERIFIED_SE",
                "timing_evidence": "official_event_audio_component_event_global_start",
            })
            audio_rows.append(row)

    subtitle_cues: list[dict[str, Any]] = []
    for event, specs in EXPECTED_VOICE_BY_EVENT.items():
        for z2d_name, request_id, start_frame in specs:
            callback, caption, translation = callbacks[z2d_name], captions[event][z2d_name], translations[request_id]
            if (
                int(callback["sound_request_id"]) != request_id
                or int(callback["exec_frame"]) != 0
                or callback["sound_request_match_count"] != "1"
                or int(caption["event_global_start_frame"]) != start_frame
            ):
                raise Ac7210AudioAuthorityError(f"runtime reqSound binding differs: {event}/{request_id}")
            sound_id = int(callback["sound_resource_id"])
            if VOLUME_BUS[buses[sound_id]] != "VOICE":
                raise Ac7210AudioAuthorityError(f"reqSound is not VOICE bus: {event}/{request_id}")
            start_ms, duration_ms = round(start_frame * 1000 / 30), int(callback["sound_duration_ms"])
            voice = {
                "event": event, "source_kind": "z2d_req_sound", "z2d_name": z2d_name,
                "request_id": request_id, "sound_id": sound_id, "code_name": callback["sound_code_name"],
                "start_frame": start_frame, "start_ms": start_ms, "duration_ms": duration_ms,
                "ogg_name": callback["ogg_name"],
                "ogg_path": str(_durable_audio_path(durable_audio_root, callback["ogg_name"])),
                "volume_kind_value": buses[sound_id], "volume_bus": "VOICE",
                "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE",
                "timing_evidence": "runtime_parent_scene_z2d_start_plus_exact_child_callback_frame_0",
            }
            audio_rows.append(voice)
            if translation["subtitle_end_policy"] == "graphical_parent_motion_end":
                end_ms = round((int(caption["event_global_end_frame_inclusive"]) + 1) * 1000 / 30)
            else:
                end_ms = start_ms + duration_ms
            subtitle_cues.append({
                "event": event, "z2d_name": z2d_name, "voice_request_id": request_id,
                "start_frame": start_frame, "start_ms": start_ms, "end_ms": end_ms,
                "speaker_ja": translation["speaker_ja"], "speaker_zh": translation["speaker_zh"],
                "ja": translation["render_ja"], "zh": translation["render_zh"],
                "translation_status": translation["status"],
                "subtitle_end_policy": translation["subtitle_end_policy"],
                "evidence": "runtime_parent_scene_z2d_start_and_official_reqSound",
            })

    audio_rows.sort(key=lambda row: (row["event"], row["start_ms"], row["request_id"]))
    subtitle_cues.sort(key=lambda row: (row["event"], row["start_ms"], row["voice_request_id"]))
    presentation_rows = []
    for event in NATIVE416_STORY_EVENTS:
        event_audio = [row for row in audio_rows if row["event"] == event]
        audio_tail = max(math.ceil((row["start_ms"] + row["duration_ms"]) * 30 / 1000) for row in event_audio)
        frames = max(video_frames[event], audio_tail)
        if frames != EXPECTED_PRESENTATION_FRAMES[event]:
            raise Ac7210AudioAuthorityError(f"event presentation frame count differs: {event}/{frames}")
        presentation_rows.append({
            "event": event, "video_content_frames": video_frames[event], "audio_tail_frames": audio_tail,
            "presentation_frames": frames, "tail_hold_frames": frames - video_frames[event],
            "native_width": 416, "native_height": 232, "frame_rate": "30/1",
        })

    legacy = json.loads(legacy_manifest_001_path.read_text(encoding="utf-8"))
    if legacy.get("event") != "ac7210_001":
        raise Ac7210AudioAuthorityError("legacy ac7210_001 manifest differs")
    old_audio = {int(row["request_id"]): row for row in legacy.get("audio", [])}
    old_subtitle = {int(row["voice_request_id"]): row for row in legacy.get("subtitles", [])}
    legacy_deltas = [
        {"event": "ac7210_001", "kind": "event_audio_component", "request_id": 2257,
         "legacy_start_ms": int(old_audio[2257]["start_ms"]), "code_exact_start_ms": 0},
        {"event": "ac7210_001", "kind": "voice", "request_id": 3279,
         "legacy_start_ms": int(old_audio[3279]["start_ms"]), "code_exact_start_ms": 1000},
        {"event": "ac7210_001", "kind": "subtitle", "request_id": 3279,
         "legacy_start_ms": int(old_subtitle[3279]["start_ms"]), "code_exact_start_ms": 1000},
    ]
    if [(row["legacy_start_ms"], row["code_exact_start_ms"]) for row in legacy_deltas] != [(74, 0), (1128, 1000), (1035, 1000)]:
        raise Ac7210AudioAuthorityError("legacy ac7210_001 timing delta differs")
    if len(audio_rows) != 10 or len(subtitle_cues) != 4:
        raise Ac7210AudioAuthorityError("ac7210 native416 audio dimensions differ")

    return {
        "schema": "magireco-ac7210-native416-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "passed", "family": "ac7210",
        "binary": {"path": str(binary.resolve()), "size": binary.stat().st_size, "gnu_build_id": build_id},
        "inputs": {"visual_authority": str(visual_authority_path.resolve()),
                   "event_audio_components": str(event_audio_components_path.resolve()),
                   "z2d_sound_callbacks": str(z2d_sound_callbacks_path.resolve()),
                   "translation": str(translation_path.resolve()), "durable_audio_root": str(durable_audio_root.resolve()),
                   "legacy_manifest_001": str(legacy_manifest_001_path.resolve())},
        "code_authority": [{"address": address, "function": function, "proves": proves}
                           for address, function, proves in CODE_AUTHORITY],
        "audio_rows": audio_rows, "subtitle_cues": subtitle_cues,
        "event_presentations": presentation_rows, "corrected_legacy_timing": legacy_deltas,
        "decision": {"native416_story_events": list(NATIVE416_STORY_EVENTS),
                     "editorial_order": list(EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER),
                     "strict_no_bgm_gate": "CLOSED_ZERO_BGM_ROWS",
                     "event_global_voice_subtitle_gate": "CLOSED",
                     "event_presentation_tail_gate": "CLOSED",
                     "total_presentation_frames": sum(row["presentation_frames"] for row in presentation_rows),
                     "expected_longform_seconds": sum(row["presentation_frames"] for row in presentation_rows) / 30,
                     "old_route_owner_approval_scope": "does_not_approve_new_deduplicated_longform"},
        "assertions": {"event_audio_component_occurrences": len(component_rows),
                       "runtime_voice_occurrences": len(subtitle_cues), "total_audio_occurrences": len(audio_rows),
                       "retained_se_occurrences": len(component_rows), "retained_voice_occurrences": len(subtitle_cues),
                       "excluded_bgm_occurrences": 0, "subtitle_cues": len(subtitle_cues),
                       "presentation_frames": sum(row["presentation_frames"] for row in presentation_rows),
                       "all_durable_ogg_files_exist": True, "all_components_are_se_bus": True,
                       "all_callbacks_are_voice_bus": True, "machine_vision_used_as_authority": False,
                       "source_media_modified": False},
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac7210AudioAuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC7210_EVENT_AUDIO_AUTHORITY.json"
    audio_path, subtitle_path = output_dir / "AC7210_AUDIO_ROWS.csv", output_dir / "AC7210_SUBTITLE_CUES.csv"
    presentation_path, delta_path = output_dir / "AC7210_EVENT_PRESENTATIONS.csv", output_dir / "AC7210_LEGACY_TIMING_DELTAS.csv"
    verify_path, readme_path = output_dir / "VERIFICATION_RECORD.json", output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path, rows in ((audio_path, report["audio_rows"]), (subtitle_path, report["subtitle_cues"]),
                       (presentation_path, report["event_presentations"]), (delta_path, report["corrected_legacy_timing"])):
        fields = list(dict.fromkeys(field for row in rows for field in row))
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    readme_path.write_text(
        "# ac7210 native416 event audio authority\n\n"
        "SOUND_DIVIDE_TBL classifies all six event components as SE and all four parent-bound reqSound callbacks as VOICE. No BGM row enters the five-event story timeline. Exact parent Z2D keys close every subtitle start. The byte-identical ac7210_002 alias is omitted and its official audio tail is preserved with an 83-frame final hold; ac7210_003 uses a 97-frame hold. The five presentations total 1354 frames (45.133 s).\n",
        encoding="utf-8")
    verify_path.write_text(json.dumps({"schema": "magireco-ac7210-native416-audio-verification-v1", "status": "passed",
                                       "checks": report["assertions"], "decision": report["decision"],
                                       "outputs": [report_path.name, audio_path.name, subtitle_path.name,
                                                   presentation_path.name, delta_path.name, readme_path.name]},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path); parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path); parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--translation", required=True, type=Path); parser.add_argument("--durable-audio-root", required=True, type=Path)
    parser.add_argument("--legacy-manifest-001", required=True, type=Path); parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(binary=args.binary, visual_authority_path=args.visual_authority,
                          event_audio_components_path=args.event_audio_components,
                          z2d_sound_callbacks_path=args.z2d_sound_callbacks, translation_path=args.translation,
                          durable_audio_root=args.durable_audio_root, legacy_manifest_001_path=args.legacy_manifest_001)
    write_outputs(report, args.output_dir)
    print("PASS events=5 components=6 voices=4 subtitles=4 retained=10 excluded_bgm=0 frames=1354 audio_gate=CLOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
