#!/usr/bin/env python3
"""Resolve all ac1104 event audio from runtime child bindings and SOUND_DIVIDE_TBL."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from elftools.elf.elffile import ELFFile

try:
    from .extract_crivideo_filename_table_authority import (
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import (  # type: ignore
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )


EVENTS = tuple(f"ac1104_{index:03d}" for index in range(1, 18))
SOUND_DIVIDE_TABLE_VA = 0x1445C54
VOLUME_BUS = {0: "BGM", 1: "SE", 2: "VOICE"}
EXPECTED_EVENT_COMPONENTS = {
    "ac1104_001": {(1035, 4020, 0), (1094, 4400, 0)},
    "ac1104_002": {(1095, 4401, 0)},
    "ac1104_003": {(1096, 4402, 0)},
    "ac1104_004": {(1097, 4403, 0), (1108, 4418, 0)},
    "ac1104_005": {(1036, 4021, 0), (1094, 4400, 0)},
    "ac1104_006": {(1035, 4020, 0), (1039, 4024, 0), (1094, 4400, 0)},
    "ac1104_007": {(1036, 4021, 0), (1039, 4024, 0), (1094, 4400, 0)},
    "ac1104_008": {(1098, 4407, 0)},
    "ac1104_009": {(1099, 4408, 0)},
    "ac1104_010": {(1100, 4409, 0)},
    "ac1104_011": {(1101, 4410, 0)},
    "ac1104_012": {(1102, 4411, 0)},
    "ac1104_013": {(1103, 4412, 0), (1037, 4022, 0), (1041, 4030, 3509), (229, 554, 4083)},
    "ac1104_014": {(1104, 4413, 0), (1109, 4419, 0)},
    "ac1104_015": {(1105, 4414, 0)},
    "ac1104_016": {(1038, 4023, 0), (1106, 4415, 0)},
    "ac1104_017": {(1107, 4416, 0), (1041, 4030, 12800), (229, 554, 13400)},
}
OFFICIAL_LABEL_TEXT = {
    "3194": "やちよの",
    "8372": "バナナボート対決！",
    "8376": "バナナボート対決！",
    "5831": "はっ",
    "6213": "発射っ",
    "3204": "きゃー",
    "2673": "きゃー",
    "3555": "きゃー",
    "5832": "きゃー",
    "6026": "きゃー",
    "6212": "きゃー",
    "3209": "やぁー",
    "2676": "やぁー",
    "5835": "きゃっ",
    "6028": "きゃっ",
    "6214": "きゃっ",
    "2677": "やりましたね",
}
NO_CALLBACK_CAPTION_NODES = {
    ("ac1104_003", "cap1104_banana_mif_010_01"),
    ("ac1104_004", "cap1104_banana_yac_011_01"),
}
CODE_AUTHORITY = (
    ("0x1445c54", "SOUND_DIVIDE_TBL", "indexes one exact volume-kind byte by sound resource id"),
    ("volume-kind 0", "setAppVolume index 0", "maps table value 0 to BGM"),
    ("volume-kind 1", "setAppVolume index 1", "maps table value 1 to SE"),
    ("volume-kind 2", "setAppVolume index 2", "maps table value 2 to VOICE"),
)


class Ac1104AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac1104AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def normalize_caption_name(name: str) -> str:
    if name.endswith(".z2d1"):
        return name[:-5]
    if name.endswith(".z2d"):
        return name[:-4]
    return name


def extract_runtime_caption_nodes(runtime: Mapping[str, Any]) -> list[dict[str, Any]]:
    if runtime.get("schema") != "magireco-ac1104-runtime-scene-motion-v1":
        raise Ac1104AudioAuthorityError("runtime scene-motion schema differs")
    if runtime.get("protected_processes_unchanged") is not True or runtime.get("crash_buffer_unchanged") is not True:
        raise Ac1104AudioAuthorityError("runtime capture protection checks differ")
    events = runtime.get("events", {})
    if set(events) != set(EVENTS):
        raise Ac1104AudioAuthorityError("runtime event set differs")
    result: list[dict[str, Any]] = []
    for event in EVENTS:
        scenes = [row for row in events[event].get("scenes", []) if row.get("name") == event]
        if len(scenes) != 1:
            raise Ac1104AudioAuthorityError(f"primary runtime scene differs: {event}")
        cuts = [row for row in scenes[0].get("cuts", []) if row.get("cut_name") == event]
        if len(cuts) != 1:
            raise Ac1104AudioAuthorityError(f"primary runtime cut differs: {event}")
        for node in _walk_nodes(cuts[0].get("nodes", [])):
            raw_name = str(node.get("name", ""))
            if not raw_name.startswith("cap1104_"):
                continue
            name = normalize_caption_name(raw_name)
            motions = node.get("motions", [])
            if len(motions) != 1 or motions[0].get("is_z2d_motion") is not True:
                raise Ac1104AudioAuthorityError(f"caption motion differs: {event}/{name}")
            keys = motions[0].get("keys", [])
            if len(keys) != 1 or len(keys[0].get("floats", [])) < 6:
                raise Ac1104AudioAuthorityError(f"caption key differs: {event}/{name}")
            values = keys[0]["floats"]
            starts = values[0], values[2], values[4]
            if len(set(starts)) != 1 or int(starts[0]) != starts[0]:
                raise Ac1104AudioAuthorityError(f"caption parent start differs: {event}/{name}")
            result.append(
                {
                    "event": event,
                    "z2d_name": name,
                    "raw_runtime_name": raw_name,
                    "start_frame": int(starts[0]),
                    "end_frame_inclusive": int(values[1]),
                }
            )
    if len(result) != 54:
        raise Ac1104AudioAuthorityError(f"runtime caption node count differs: {len(result)}")
    return result


def read_sound_divide_values(binary: Path, sound_ids: Iterable[int]) -> tuple[str, dict[int, int]]:
    if binary.stat().st_size != SLOT_BINARY_SIZE:
        raise Ac1104AudioAuthorityError("exact Slot binary size differs")
    values: dict[int, int] = {}
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        build_id = _gnu_build_id(elf)
        if build_id.casefold() != SLOT_BINARY_BUILD_ID.casefold():
            raise Ac1104AudioAuthorityError("exact Slot binary build-id differs")
        for sound_id in sorted(set(sound_ids)):
            stream.seek(_va_to_file_offset(elf, SOUND_DIVIDE_TABLE_VA + sound_id))
            raw = stream.read(1)
            if len(raw) != 1 or raw[0] not in VOLUME_BUS:
                raise Ac1104AudioAuthorityError(f"sound bus value differs: {sound_id}")
            values[sound_id] = raw[0]
    return build_id, values


def _durable_audio_path(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise Ac1104AudioAuthorityError(f"durable official OGG is absent: {path}")
    return path.resolve()


def _translation_map(path: Path) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {row["ja"]: row["zh"] for row in rows}
    if len(result) != 31 or len(rows) != len(result):
        raise Ac1104AudioAuthorityError("ac1104 translation map dimensions differ")
    return result


def build_report(
    *,
    binary: Path,
    runtime_scene_motion_path: Path,
    event_audio_components_path: Path,
    z2d_sound_callbacks_path: Path,
    legacy_event_sound_timeline_path: Path,
    subtitle_timeline_path: Path,
    translation_path: Path,
    durable_audio_root: Path,
) -> dict[str, Any]:
    runtime = json.loads(runtime_scene_motion_path.read_text(encoding="utf-8"))
    caption_nodes = extract_runtime_caption_nodes(runtime)
    components = [row for row in read_csv(event_audio_components_path) if row.get("root") == "ac1104"]
    callbacks = {row["z2d_name"]: row for row in read_csv(z2d_sound_callbacks_path) if row["z2d_name"].startswith("cap1104_")}
    legacy_sounds = [row for row in read_csv(legacy_event_sound_timeline_path) if row["event_name"].startswith("ac1104_")]
    subtitle_rows = [row for row in read_csv(subtitle_timeline_path) if row["event_name"].startswith("ac1104_")]
    translations = _translation_map(translation_path)

    component_by_key: dict[tuple[str, int, int, int], dict[str, str]] = {}
    for row in components:
        key = (row["primary_animation"], int(row["leaf_request_id"]), int(row["leaf_sound_code"]), int(row["start_ms"]))
        component_by_key[key] = row
    observed_components = {event: set() for event in EVENTS}
    for event, request_id, sound_id, start_ms in component_by_key:
        observed_components[event].add((request_id, sound_id, start_ms))
    if observed_components != EXPECTED_EVENT_COMPONENTS:
        raise Ac1104AudioAuthorityError("event audio component set differs")

    callback_nodes: list[tuple[dict[str, Any], dict[str, str]]] = []
    no_callback: set[tuple[str, str]] = set()
    for node in caption_nodes:
        callback = callbacks.get(node["z2d_name"])
        if callback is None:
            no_callback.add((node["event"], node["z2d_name"]))
        else:
            callback_nodes.append((node, callback))
    if no_callback != NO_CALLBACK_CAPTION_NODES or len(callback_nodes) != 52:
        raise Ac1104AudioAuthorityError("runtime reqSound caption partition differs")

    sound_ids = {sound_id for _, _, sound_id, _ in component_by_key}
    sound_ids.update(int(callback["sound_resource_id"]) for _, callback in callback_nodes)
    build_id, bus_values = read_sound_divide_values(binary, sound_ids)
    legacy_by_key = {(row["event_name"], row["z2d_name"], row["sound_request_id"]): row for row in legacy_sounds}
    subtitle_by_key = {(row["event_name"], row["z2d_name"], row["sound_request_id"]): row for row in subtitle_rows}

    audio_rows: list[dict[str, Any]] = []
    for (event, request_id, sound_id, start_ms), row in component_by_key.items():
        bus = VOLUME_BUS[bus_values[sound_id]]
        audio_rows.append(
            {
                "event": event,
                "source_kind": "event_audio_component",
                "request_id": request_id,
                "sound_id": sound_id,
                "code_name": row["leaf_code_name"],
                "start_frame": None,
                "start_ms": start_ms,
                "duration_ms": int(row["duration_ms"]),
                "ogg_name": row["ogg_name"],
                "ogg_path": str(_durable_audio_path(durable_audio_root, row["ogg_name"])),
                "volume_kind_value": bus_values[sound_id],
                "volume_bus": bus,
                "strict_no_bgm_disposition": "EXCLUDE_AS_BGM_BUS" if bus == "BGM" else "RETAIN_VERIFIED_SE",
                "timing_evidence": "official_event_audio_component_event_global_start",
                "subtitle_ja": None,
                "subtitle_zh": None,
            }
        )

    corrected_deltas: list[dict[str, Any]] = []
    subtitle_cues: list[dict[str, Any]] = []
    for node, callback in callback_nodes:
        request_id = callback["sound_request_id"]
        sound_id = int(callback["sound_resource_id"])
        bus = VOLUME_BUS[bus_values[sound_id]]
        if bus != "VOICE" or int(callback["exec_frame"]) != 0 or callback["sound_request_match_count"] != "1":
            raise Ac1104AudioAuthorityError(f"reqSound binding differs: {node['event']}/{node['z2d_name']}")
        start_ms = round(node["start_frame"] * 1000 / 30)
        key = (node["event"], node["z2d_name"], request_id)
        legacy = legacy_by_key.get(key)
        legacy_frame = None if legacy is None else int(float(legacy["absolute_start_frame"]))
        if legacy_frame != node["start_frame"]:
            corrected_deltas.append(
                {
                    "event": node["event"],
                    "z2d_name": node["z2d_name"],
                    "request_id": int(request_id),
                    "legacy_start_frame": legacy_frame,
                    "runtime_exact_start_frame": node["start_frame"],
                }
            )
        subtitle_source = subtitle_by_key.get(key)
        ja = ""
        if subtitle_source is not None:
            ja = subtitle_source["srt_text"].replace("\\n", "\n")
        if not ja:
            ja = OFFICIAL_LABEL_TEXT.get(request_id, "")
        if not ja or ja not in translations:
            raise Ac1104AudioAuthorityError(f"subtitle translation is absent: {node['event']}/{request_id}/{ja!r}")
        duration_ms = int(callback["sound_duration_ms"])
        if legacy_frame == node["start_frame"] and subtitle_source is not None:
            end_ms = int(subtitle_source["effective_end_ms"])
        else:
            visual_end_ms = round((node["end_frame_inclusive"] + 1) * 1000 / 30)
            end_ms = max(start_ms + duration_ms, visual_end_ms)
        audio_rows.append(
            {
                "event": node["event"],
                "source_kind": "z2d_req_sound",
                "z2d_name": node["z2d_name"],
                "request_id": int(request_id),
                "sound_id": sound_id,
                "code_name": callback["sound_code_name"],
                "start_frame": node["start_frame"],
                "start_ms": start_ms,
                "duration_ms": duration_ms,
                "ogg_name": callback["ogg_name"],
                "ogg_path": str(_durable_audio_path(durable_audio_root, callback["ogg_name"])),
                "volume_kind_value": bus_values[sound_id],
                "volume_bus": bus,
                "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE",
                "timing_evidence": "runtime_parent_scene_z2d_start_plus_exact_child_callback_frame_0",
                "subtitle_ja": ja,
                "subtitle_zh": translations[ja],
            }
        )
        subtitle_cues.append(
            {
                "event": node["event"],
                "z2d_name": node["z2d_name"],
                "voice_request_id": int(request_id),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "ja": ja,
                "zh": translations[ja],
                "evidence": "runtime_parent_scene_z2d_start_and_official_reqSound",
            }
        )

    for event, name in sorted(no_callback):
        node = next(row for row in caption_nodes if row["event"] == event and row["z2d_name"] == name)
        rows = [row for row in subtitle_rows if row["event_name"] == event and row["z2d_name"] == name and not row["sound_request_id"]]
        if len(rows) != 1:
            raise Ac1104AudioAuthorityError(f"text-only continuation cue differs: {event}/{name}")
        source = rows[0]
        if int(source["start_ms"]) != round(node["start_frame"] * 1000 / 30):
            raise Ac1104AudioAuthorityError(f"text-only continuation timing differs: {event}/{name}")
        ja = source["srt_text"].replace("\\n", "\n")
        if ja not in translations:
            raise Ac1104AudioAuthorityError(f"text-only translation is absent: {ja!r}")
        subtitle_cues.append(
            {
                "event": event,
                "z2d_name": name,
                "voice_request_id": None,
                "start_ms": int(source["start_ms"]),
                "end_ms": int(source["effective_end_ms"]),
                "ja": ja,
                "zh": translations[ja],
                "evidence": "runtime_parent_scene_z2d_start_and_graphical_display_text",
            }
        )

    audio_rows.sort(key=lambda row: (row["event"], row["start_ms"], row["request_id"]))
    subtitle_cues.sort(key=lambda row: (row["event"], row["start_ms"], str(row["voice_request_id"])))
    corrected_deltas.sort(key=lambda row: (row["event"], row["runtime_exact_start_frame"]))
    expected_deltas = [
        {"event": "ac1104_017", "z2d_name": "cap1104_banana_tks_041", "request_id": 6214, "legacy_start_frame": 302, "runtime_exact_start_frame": 159},
        {"event": "ac1104_017", "z2d_name": "cap1104_banana_iro_043", "request_id": 2677, "legacy_start_frame": None, "runtime_exact_start_frame": 302},
    ]
    if corrected_deltas != expected_deltas:
        raise Ac1104AudioAuthorityError(f"legacy child timing delta differs: {corrected_deltas}")
    excluded = [row for row in audio_rows if row["strict_no_bgm_disposition"] == "EXCLUDE_AS_BGM_BUS"]
    if [(row["event"], row["request_id"], row["sound_id"]) for row in excluded] != [
        ("ac1104_013", 229, 554),
        ("ac1104_017", 229, 554),
    ]:
        raise Ac1104AudioAuthorityError("strict no-BGM exclusion set differs")
    if len(audio_rows) != 83 or len(subtitle_cues) != 54:
        raise Ac1104AudioAuthorityError("ac1104 final audio/subtitle dimensions differ")

    return {
        "schema": "magireco-ac1104-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "passed",
        "binary": {"path": str(binary.resolve()), "size": binary.stat().st_size, "gnu_build_id": build_id},
        "inputs": {
            "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
            "event_audio_components": str(event_audio_components_path.resolve()),
            "z2d_sound_callbacks": str(z2d_sound_callbacks_path.resolve()),
            "legacy_event_sound_timeline": str(legacy_event_sound_timeline_path.resolve()),
            "subtitle_timeline": str(subtitle_timeline_path.resolve()),
            "translation": str(translation_path.resolve()),
            "durable_audio_root": str(durable_audio_root.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "audio_rows": audio_rows,
        "subtitle_cues": subtitle_cues,
        "corrected_legacy_child_timing": corrected_deltas,
        "decision": {
            "events": list(EVENTS),
            "event_global_child_audio_timing": "CLOSED",
            "event_audio_and_strict_no_bgm_manifest_closure": "CLOSED",
            "retained_audio_occurrences": 81,
            "excluded_bgm_occurrences": 2,
            "excluded_bgm_identity": {"request_id": 229, "sound_id": 554},
            "legacy_event_sound_timeline": "WITHDRAWN_FOR_AC1104_017_TIMING_AND_OMISSION",
            "render_allowed_by_this_report_alone": False,
            "remaining_independent_gate": "duplicate_free_exhaustive_editorial_order",
        },
        "assertions": {
            "event_audio_component_occurrences_after_exact_dedup": len(component_by_key),
            "runtime_caption_reqSound_occurrences": len(callback_nodes),
            "text_only_continuation_cues": len(no_callback),
            "total_audio_occurrences": len(audio_rows),
            "retained_audio_occurrences": len(audio_rows) - len(excluded),
            "subtitle_cues": len(subtitle_cues),
            "corrected_legacy_rows": len(corrected_deltas),
            "all_durable_ogg_files_exist": True,
            "all_reqSound_ids_are_voice_bus": True,
            "all_non_jingle_event_components_are_se_bus": all(
                row["volume_bus"] == "SE"
                for row in audio_rows
                if row["source_kind"] == "event_audio_component" and row["request_id"] != 229
            ),
            "only_sound_554_is_excluded_as_bgm": True,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac1104AudioAuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC1104_EVENT_AUDIO_AUTHORITY.json"
    audio_csv = output_dir / "AC1104_EVENT_AUDIO_ROWS.csv"
    subtitle_csv = output_dir / "AC1104_SUBTITLE_CUES.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path, rows in ((audio_csv, report["audio_rows"]), (subtitle_csv, report["subtitle_cues"])):
        fields: list[str] = []
        for row in rows:
            for field in row:
                if field not in fields:
                    fields.append(field)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    verification_path.write_text(
        json.dumps(
            {
                "schema": "magireco-ac1104-event-audio-verification-v1",
                "status": "passed",
                "checks": report["assertions"],
                "decision": report["decision"],
                "outputs": [report_path.name, audio_csv.name, subtitle_csv.name, readme_path.name],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        "# ac1104 event audio authority\n\n"
        "Runtime parent child-Z2D starts close 52 reqSound occurrences and two "
        "text-only continuations. The old timeline placed request 6214 at frame 302; "
        "runtime binds it to frame 159 and binds the previously omitted request 2677 "
        "to frame 302. SOUND_DIVIDE_TBL retains 81 VOICE/SE occurrences and excludes "
        "only request 229 / sound 554 at two BGM occurrences. No media was changed.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path)
    parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--legacy-event-sound-timeline", required=True, type=Path)
    parser.add_argument("--subtitle-timeline", required=True, type=Path)
    parser.add_argument("--translation", required=True, type=Path)
    parser.add_argument("--durable-audio-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary,
        runtime_scene_motion_path=args.runtime_scene_motion,
        event_audio_components_path=args.event_audio_components,
        z2d_sound_callbacks_path=args.z2d_sound_callbacks,
        legacy_event_sound_timeline_path=args.legacy_event_sound_timeline,
        subtitle_timeline_path=args.subtitle_timeline,
        translation_path=args.translation,
        durable_audio_root=args.durable_audio_root,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS events=17 audio=83 retained=81 excluded_bgm=2 subtitles=54 "
        "legacy_corrected=2 audio_gate=CLOSED editorial_order=OPEN"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
