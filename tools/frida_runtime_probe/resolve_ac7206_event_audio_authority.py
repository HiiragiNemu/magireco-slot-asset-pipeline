#!/usr/bin/env python3
"""Resolve ac7206 event-global audio/subtitles and strict no-BGM buses."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

from elftools.elf.elffile import ELFFile

try:
    from .extract_crivideo_filename_table_authority import (
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )
    from .resolve_ac7206_movie_layer_reachability import (
        EVENTS,
        GAMEPLAY_EVENT,
        STORY_EVENTS,
        extract_runtime_bindings,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import (  # type: ignore
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )
    from resolve_ac7206_movie_layer_reachability import (  # type: ignore
        EVENTS,
        GAMEPLAY_EVENT,
        STORY_EVENTS,
        extract_runtime_bindings,
    )


SOUND_DIVIDE_TABLE_VA = 0x1445C54
VOLUME_BUS = {0: "BGM", 1: "SE", 2: "VOICE"}
EXPECTED_EVENT_COMPONENTS = {
    "ac7206_001": {(10404, 42350, 0)},
    "ac7206_002": {(10405, 42351, 0)},
    "ac7206_003": {(10406, 42352, 0)},
    "ac7206_004": {(10407, 42353, 0)},
    "ac7206_005": {(10408, 42354, 0)},
    "ac7206_006": {(10409, 42355, 0)},
    "ac7206_007": {(10410, 42356, 0)},
    "ac7206_008": {(419, 1005, 0), (226, 551, 3260)},
    "ac7206_009": {(10406, 42352, 0)},
    "ac7206_010": {(10407, 42353, 0)},
    "ac7206_011": {(10408, 42354, 0)},
    "ac7206_012": {(10409, 42355, 0)},
    "ac7206_013": {(10410, 42356, 0)},
    "ac7206_014": {(419, 1005, 0), (226, 551, 3260)},
    "ac7206_015": set(),
}
VOICE_TEXT = {
    5321: "グッジョブ、灯花、ねむ",
    5322: "それこそが本物のアート",
    5323: "あなた達とその翼共",
    5324: "アリナが代わりにマスタリングしてあげる",
}
EXPECTED_VOICE_BY_EVENT = {
    "ac7206_001": ("cap7206_paint_ari_001", 5321, 1),
    "ac7206_002": ("cap7206_paint_ari_003", 5323, 10),
    **{
        f"ac7206_{index:03d}": ("cap7206_paint_ari_002", 5322, 1)
        for index in range(3, 9)
    },
    **{
        f"ac7206_{index:03d}": ("cap7206_paint_ari_004", 5324, 1)
        for index in range(9, 15)
    },
}
CODE_AUTHORITY = (
    ("0x1445c54", "SOUND_DIVIDE_TBL", "indexes one exact volume-kind byte by sound resource id"),
    ("volume-kind 0", "setAppVolume index 0", "maps table value 0 to BGM"),
    ("volume-kind 1", "setAppVolume index 1", "maps table value 1 to SE"),
    ("volume-kind 2", "setAppVolume index 2", "maps table value 2 to VOICE"),
)


class Ac7206AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac7206AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def read_sound_divide_values(binary: Path, sound_ids: set[int]) -> tuple[str, dict[int, int]]:
    if binary.stat().st_size != SLOT_BINARY_SIZE:
        raise Ac7206AudioAuthorityError("exact Slot binary size differs")
    values: dict[int, int] = {}
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        build_id = _gnu_build_id(elf)
        if build_id.casefold() != SLOT_BINARY_BUILD_ID.casefold():
            raise Ac7206AudioAuthorityError("exact Slot binary build-id differs")
        for sound_id in sorted(sound_ids):
            stream.seek(_va_to_file_offset(elf, SOUND_DIVIDE_TABLE_VA + sound_id))
            raw = stream.read(1)
            if len(raw) != 1 or raw[0] not in VOLUME_BUS:
                raise Ac7206AudioAuthorityError(f"sound bus value differs: {sound_id}")
            values[sound_id] = raw[0]
    return build_id, values


def _durable_audio_path(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise Ac7206AudioAuthorityError(f"durable official OGG is absent: {path}")
    return path.resolve()


def _translation_map(path: Path) -> dict[str, dict[str, str]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {row["ja"]: row for row in rows}
    if (
        document.get("schema") != "magireco-reviewed-story-zh-dialogue-map-v1"
        or document.get("scope") != "ac7206_exhaustive_runtime_bound_dialogue"
        or set(result) != set(VOICE_TEXT.values())
        or len(result) != len(rows)
    ):
        raise Ac7206AudioAuthorityError("ac7206 translation map dimensions differ")
    return result


def _load_legacy_manifests(primary: Path, replacement: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for event in STORY_EVENTS[1:]:
        candidate = replacement / f"{event}.json"
        if not candidate.is_file():
            candidate = primary / f"{event}.json"
        if not candidate.is_file():
            raise Ac7206AudioAuthorityError(f"legacy event manifest is absent: {event}")
        value = json.loads(candidate.read_text(encoding="utf-8"))
        if value.get("event") != event:
            raise Ac7206AudioAuthorityError(f"legacy event manifest differs: {event}")
        result[event] = value
    return result


def _legacy_timing_deltas(
    legacy: Mapping[str, Mapping[str, Any]],
    exact_components: Mapping[str, list[dict[str, Any]]],
    exact_voices: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []
    for event, manifest in legacy.items():
        old_audio = {str(row["request_id"]): row for row in manifest.get("audio", [])}
        old_subtitles = {str(row["voice_request_id"]): row for row in manifest.get("subtitles", [])}
        for row in exact_components[event]:
            old = old_audio.get(str(row["request_id"]))
            if old is None:
                raise Ac7206AudioAuthorityError(f"legacy component request is absent: {event}/{row['request_id']}")
            if int(old["start_ms"]) != row["start_ms"]:
                result.append({
                    "event": event, "kind": "event_audio_component", "request_id": row["request_id"],
                    "legacy_start_ms": int(old["start_ms"]), "code_exact_start_ms": row["start_ms"],
                })
        voice = exact_voices[event]
        request = str(voice["request_id"])
        old_voice = old_audio.get(request)
        old_subtitle = old_subtitles.get(request)
        if old_voice is None or old_subtitle is None:
            raise Ac7206AudioAuthorityError(f"legacy voice/subtitle is absent: {event}/{request}")
        if int(old_voice["start_ms"]) != voice["start_ms"]:
            result.append({
                "event": event, "kind": "voice", "request_id": voice["request_id"],
                "legacy_start_ms": int(old_voice["start_ms"]), "code_exact_start_ms": voice["start_ms"],
            })
        if int(old_subtitle["start_ms"]) != voice["start_ms"]:
            result.append({
                "event": event, "kind": "subtitle", "request_id": voice["request_id"],
                "legacy_start_ms": int(old_subtitle["start_ms"]), "code_exact_start_ms": voice["start_ms"],
            })
    result.sort(key=lambda row: (row["event"], row["kind"], row["request_id"]))
    if len(result) != 32:
        raise Ac7206AudioAuthorityError(f"legacy manifest timing delta count differs: {len(result)}")
    return result


def build_report(
    *, binary: Path, runtime_scene_motion_path: Path, visual_authority_path: Path,
    event_audio_components_path: Path, z2d_sound_callbacks_path: Path,
    legacy_event_sound_timeline_path: Path, translation_path: Path,
    legacy_manifest_dir: Path, replacement_manifest_dir: Path,
    durable_audio_root: Path,
) -> dict[str, Any]:
    visual = json.loads(visual_authority_path.read_text(encoding="utf-8"))
    if (
        visual.get("schema") != "magireco-ac7206-movielayer-runtime-reachability-authority-v1"
        or visual.get("status") != "passed"
        or visual.get("decision", {}).get("visual_reachability_gate") != "CLOSED"
    ):
        raise Ac7206AudioAuthorityError("ac7206 visual authority differs")
    runtime = extract_runtime_bindings(json.loads(runtime_scene_motion_path.read_text(encoding="utf-8")))
    caption_rows = {}
    for event in STORY_EVENTS:
        rows = [row for row in runtime["events"][event] if row["role"] == "caption_audio_host"]
        if len(rows) != 1:
            raise Ac7206AudioAuthorityError(f"runtime caption node differs: {event}")
        caption_rows[event] = rows[0]

    component_rows = [row for row in read_csv(event_audio_components_path) if row.get("root") == "ac7206"]
    component_by_event: dict[str, list[dict[str, Any]]] = {event: [] for event in EVENTS}
    for row in component_rows:
        event = row["primary_animation"]
        if event not in component_by_event:
            raise Ac7206AudioAuthorityError(f"unexpected ac7206 component event: {event}")
        component_by_event[event].append({
            "request_id": int(row["leaf_request_id"]),
            "sound_id": int(row["leaf_sound_code"]),
            "code_name": row["leaf_code_name"],
            "start_ms": int(row["start_ms"]),
            "duration_ms": int(row["duration_ms"]),
            "ogg_name": row["ogg_name"],
        })
    observed = {
        event: {(row["request_id"], row["sound_id"], row["start_ms"]) for row in rows}
        for event, rows in component_by_event.items()
    }
    if observed != EXPECTED_EVENT_COMPONENTS:
        raise Ac7206AudioAuthorityError("event audio component set differs")

    callbacks = {
        row["z2d_name"]: row
        for row in read_csv(z2d_sound_callbacks_path)
        if row["z2d_name"].startswith("cap7206_")
    }
    if set(callbacks) != {spec[0] for spec in EXPECTED_VOICE_BY_EVENT.values()}:
        raise Ac7206AudioAuthorityError("ac7206 reqSound callback set differs")
    legacy_timeline = {
        (row["event_name"], row["z2d_name"], int(row["sound_request_id"])): row
        for row in read_csv(legacy_event_sound_timeline_path)
        if row["event_name"].startswith("ac7206_")
    }
    translations = _translation_map(translation_path)
    sound_ids = {row["sound_id"] for rows in component_by_event.values() for row in rows}
    sound_ids.update(int(row["sound_resource_id"]) for row in callbacks.values())
    build_id, bus_values = read_sound_divide_values(binary, sound_ids)

    audio_rows: list[dict[str, Any]] = []
    exact_component_rows: dict[str, list[dict[str, Any]]] = {event: [] for event in EVENTS}
    for event, rows in component_by_event.items():
        for source in rows:
            bus = VOLUME_BUS[bus_values[source["sound_id"]]]
            row = {
                "event": event, "source_kind": "event_audio_component", **source,
                "ogg_path": str(_durable_audio_path(durable_audio_root, source["ogg_name"])),
                "volume_kind_value": bus_values[source["sound_id"]], "volume_bus": bus,
                "strict_no_bgm_disposition": "EXCLUDE_AS_BGM_BUS" if bus == "BGM" else "RETAIN_VERIFIED_SE",
                "timing_evidence": "official_event_audio_component_event_global_start",
            }
            exact_component_rows[event].append(row)
            audio_rows.append(row)

    exact_voices: dict[str, dict[str, Any]] = {}
    subtitle_cues = []
    legacy_child_delta = []
    for event, (z2d_name, request_id, start_frame) in EXPECTED_VOICE_BY_EVENT.items():
        caption = caption_rows[event]
        callback = callbacks[z2d_name]
        if (
            caption["parent_z2d"] != z2d_name
            or caption["event_global_start_frame"] != start_frame
            or int(callback["sound_request_id"]) != request_id
            or int(callback["exec_frame"]) != 0
            or callback["sound_request_match_count"] != "1"
        ):
            raise Ac7206AudioAuthorityError(f"runtime reqSound binding differs: {event}/{z2d_name}")
        legacy = legacy_timeline.get((event, z2d_name, request_id))
        if legacy is None:
            raise Ac7206AudioAuthorityError(f"legacy callback identity is absent: {event}/{request_id}")
        raw_legacy_frame = legacy["absolute_start_frame"]
        legacy_frame = None if not raw_legacy_frame else int(float(raw_legacy_frame))
        if legacy_frame != start_frame:
            legacy_child_delta.append({
                "event": event, "z2d_name": z2d_name, "request_id": request_id,
                "legacy_start_frame": legacy_frame, "runtime_exact_start_frame": start_frame,
            })
        sound_id = int(callback["sound_resource_id"])
        if VOLUME_BUS[bus_values[sound_id]] != "VOICE":
            raise Ac7206AudioAuthorityError(f"reqSound is not VOICE bus: {event}/{request_id}")
        start_ms = round(start_frame * 1000 / 30)
        duration_ms = int(callback["sound_duration_ms"])
        text = VOICE_TEXT[request_id]
        translation = translations[text]
        voice = {
            "event": event, "source_kind": "z2d_req_sound", "z2d_name": z2d_name,
            "request_id": request_id, "sound_id": sound_id, "code_name": callback["sound_code_name"],
            "start_frame": start_frame, "start_ms": start_ms, "duration_ms": duration_ms,
            "ogg_name": callback["ogg_name"],
            "ogg_path": str(_durable_audio_path(durable_audio_root, callback["ogg_name"])),
            "volume_kind_value": bus_values[sound_id], "volume_bus": "VOICE",
            "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE",
            "timing_evidence": "runtime_parent_scene_z2d_start_plus_exact_child_callback_frame_0",
            "subtitle_ja": text, "subtitle_zh": translation["zh"],
            "translation_status": translation["status"],
        }
        exact_voices[event] = voice
        audio_rows.append(voice)
        visual_end_ms = round((caption["local_end_frame_inclusive"] + 1) * 1000 / 30)
        subtitle_cues.append({
            "event": event, "z2d_name": z2d_name, "voice_request_id": request_id,
            "start_ms": start_ms, "end_ms": max(start_ms + duration_ms, visual_end_ms),
            "speaker_ja": "アリナ・グレイ", "speaker_zh": "阿莉娜·格雷",
            "ja": text, "zh": translation["zh"], "translation_status": translation["status"],
            "evidence": "runtime_parent_scene_z2d_start_and_official_reqSound",
        })

    expected_child_delta = [{
        "event": "ac7206_001", "z2d_name": "cap7206_paint_ari_001", "request_id": 5321,
        "legacy_start_frame": None, "runtime_exact_start_frame": 1,
    }]
    if legacy_child_delta != expected_child_delta:
        raise Ac7206AudioAuthorityError(f"legacy child timing delta differs: {legacy_child_delta}")
    legacy_manifests = _load_legacy_manifests(legacy_manifest_dir, replacement_manifest_dir)
    manifest_deltas = _legacy_timing_deltas(legacy_manifests, exact_component_rows, exact_voices)
    audio_rows.sort(key=lambda row: (row["event"], row["start_ms"], row["request_id"]))
    subtitle_cues.sort(key=lambda row: row["event"])
    excluded = [row for row in audio_rows if row["strict_no_bgm_disposition"] == "EXCLUDE_AS_BGM_BUS"]
    if [(row["event"], row["request_id"], row["sound_id"]) for row in excluded] != [
        ("ac7206_008", 226, 551), ("ac7206_014", 226, 551),
    ]:
        raise Ac7206AudioAuthorityError("strict no-BGM exclusion set differs")
    if len(audio_rows) != 30 or len(subtitle_cues) != 14:
        raise Ac7206AudioAuthorityError("ac7206 final audio/subtitle dimensions differ")

    return {
        "schema": "magireco-ac7206-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "passed", "family": "ac7206",
        "binary": {"path": str(binary.resolve()), "size": binary.stat().st_size, "gnu_build_id": build_id},
        "inputs": {
            "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
            "visual_authority": str(visual_authority_path.resolve()),
            "event_audio_components": str(event_audio_components_path.resolve()),
            "z2d_sound_callbacks": str(z2d_sound_callbacks_path.resolve()),
            "legacy_event_sound_timeline": str(legacy_event_sound_timeline_path.resolve()),
            "translation": str(translation_path.resolve()),
            "legacy_manifest_dir": str(legacy_manifest_dir.resolve()),
            "replacement_manifest_dir": str(replacement_manifest_dir.resolve()),
            "durable_audio_root": str(durable_audio_root.resolve()),
        },
        "code_authority": [{"address": address, "function": function, "proves": proves}
                           for address, function, proves in CODE_AUTHORITY],
        "audio_rows": audio_rows, "subtitle_cues": subtitle_cues,
        "corrected_legacy_child_timing": legacy_child_delta,
        "corrected_legacy_manifest_timing": manifest_deltas,
        "decision": {
            "story_events": list(STORY_EVENTS),
            "gameplay_event": GAMEPLAY_EVENT,
            "event_global_child_audio_timing": "CLOSED_FOR_STORY_EVENTS_001_TO_014",
            "event_audio_and_strict_no_bgm_manifest_closure": "CLOSED_FOR_STORY_EVENTS_001_TO_014",
            "gameplay_event_owned_audio": "ZERO_ROWS_IN_EXACT_EVENT_COMPONENT_AND_CAPTION_TABLES",
            "retained_audio_occurrences": 28, "excluded_bgm_occurrences": 2,
            "excluded_bgm_identity": {"request_id": 226, "sound_id": 551},
            "legacy_v31_v68_v74_timing": "WITHDRAWN_FOR_32_CAPTURE_JITTER_OR_EARLY_SUBTITLE_STARTS",
            "render_allowed_by_this_report_alone": False,
            "remaining_independent_gate": "duplicate_free_exhaustive_editorial_order_and_gameplay_015_composition",
        },
        "assertions": {
            "event_audio_component_occurrences": len(component_rows),
            "runtime_caption_reqSound_occurrences": len(exact_voices),
            "total_audio_occurrences": len(audio_rows),
            "retained_audio_occurrences": len(audio_rows) - len(excluded),
            "excluded_bgm_occurrences": len(excluded),
            "subtitle_cues": len(subtitle_cues),
            "corrected_legacy_child_rows": len(legacy_child_delta),
            "corrected_legacy_manifest_timing_rows": len(manifest_deltas),
            "gameplay_event_owned_audio_rows": len(component_by_event[GAMEPLAY_EVENT]),
            "all_durable_ogg_files_exist": True,
            "all_reqSound_ids_are_voice_bus": True,
            "all_retained_event_components_are_se_bus": all(
                row["volume_bus"] == "SE" for row in audio_rows
                if row["source_kind"] == "event_audio_component"
                and row["strict_no_bgm_disposition"] != "EXCLUDE_AS_BGM_BUS"
            ),
            "only_sound_551_is_excluded_as_bgm": True,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac7206AudioAuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC7206_EVENT_AUDIO_AUTHORITY.json"
    audio_csv = output_dir / "AC7206_EVENT_AUDIO_ROWS.csv"
    subtitle_csv = output_dir / "AC7206_SUBTITLE_CUES.csv"
    delta_csv = output_dir / "AC7206_LEGACY_TIMING_DELTAS.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path, rows in ((audio_csv, report["audio_rows"]), (subtitle_csv, report["subtitle_cues"]),
                       (delta_csv, report["corrected_legacy_manifest_timing"])):
        fields = list(dict.fromkeys(field for row in rows for field in row))
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
    verification_path.write_text(json.dumps({
        "schema": "magireco-ac7206-event-audio-verification-v1", "status": "passed",
        "checks": report["assertions"], "decision": report["decision"],
        "outputs": [report_path.name, audio_csv.name, subtitle_csv.name, delta_csv.name, readme_path.name],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        "# ac7206 event audio authority\n\n"
        "Runtime parent Z2D keys close all fourteen story reqSound starts. The newly "
        "covered event 001 moves request 5321 from unresolved to frame 1. Exact EventInfo "
        "component starts replace 32 capture-jitter or early-subtitle timestamps in old "
        "manifests. SOUND_DIVIDE_TBL retains 28 VOICE/SE occurrences and excludes request "
        "226 / sound 551 at two BGM-bus occurrences. Event 015 owns no row in these exact "
        "audio tables and remains a separate gameplay composition gate. No media changed.\n",
        encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--visual-authority", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path)
    parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--legacy-event-sound-timeline", required=True, type=Path)
    parser.add_argument("--translation", required=True, type=Path)
    parser.add_argument("--legacy-manifest-dir", required=True, type=Path)
    parser.add_argument("--replacement-manifest-dir", required=True, type=Path)
    parser.add_argument("--durable-audio-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary, runtime_scene_motion_path=args.runtime_scene_motion,
        visual_authority_path=args.visual_authority,
        event_audio_components_path=args.event_audio_components,
        z2d_sound_callbacks_path=args.z2d_sound_callbacks,
        legacy_event_sound_timeline_path=args.legacy_event_sound_timeline,
        translation_path=args.translation, legacy_manifest_dir=args.legacy_manifest_dir,
        replacement_manifest_dir=args.replacement_manifest_dir,
        durable_audio_root=args.durable_audio_root)
    write_outputs(report, args.output_dir)
    print("PASS events=15 story_voice=14 audio=30 retained=28 excluded_bgm=2 "
          "legacy_timing_corrected=32 gameplay_owned_audio=0 audio_gate=CLOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
