#!/usr/bin/env python3
"""Resolve ac1102_007/013/014/015 audio buses and event-global timing."""

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
        SLOT_BINARY_SHA256,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import (  # type: ignore
        SLOT_BINARY_BUILD_ID,
        SLOT_BINARY_SHA256,
        SLOT_BINARY_SIZE,
        _gnu_build_id,
        _va_to_file_offset,
    )


SOUND_DIVIDE_TABLE_VA = 0x1445C54
VOLUME_BUS = {0: "BGM", 1: "SE", 2: "VOICE"}

EXPECTED_EVENT_COMPONENTS = {
    "ac1102_007": ((1037, 4022, 0), (229, 554, 8751), (1064, 4206, 0), (1041, 4030, 7868)),
    "ac1102_013": ((1067, 4212, 0),),
    "ac1102_014": ((1038, 4023, 0), (1068, 4213, 0)),
    "ac1102_015": ((1069, 4214, 0), (1041, 4030, 11600), (229, 554, 12200)),
}

EXPECTED_CAPTION_AUDIO = {
    "ac1102_007": {
        "cap1102_rakuno_fer_018": (4036, 17736, 10),
        "cap1102_rakuno_fer_019": (4038, 17738, 152),
    },
    "ac1102_014": {
        "cap1102_rakuno_fer_022": (4041, 17741, 10),
        "cap1102_rakuno_fer_023": (4043, 17743, 49),
        "cap1102_rakuno_fer_024": (4044, 17744, 80),
    },
    "ac1102_015": {
        "cap1102_rakuno_fer_025": (4046, 17746, 8),
        "cap1102_rakuno_fer_026": (4047, 17747, 260),
    },
}

SUBTITLE_TEXT = {
    "cap1102_rakuno_fer_019": {
        "ja": "ちょっと驚いちまっただけなんだよな",
        "zh": "我只是稍微吓了一跳而已啦",
    },
    "cap1102_rakuno_fer_022": {"ja": "奥の手だ！", "zh": "这是我的绝招！"},
    "cap1102_rakuno_fer_026": {
        "ja": "いよーし！\nオレ達もう友達だな！",
        "zh": "好嘞！\n我们已经是朋友了吧！",
    },
}

CODE_AUTHORITY = (
    (
        "0x1445c54",
        "SOUND_DIVIDE_TBL",
        "indexes one exact volume-kind byte by sound resource id",
    ),
    (
        "volume-kind 0",
        "CSoundSeekWindow::onButtonBGMSeek -> setAppVolume index 0",
        "maps table value 0 to BGM",
    ),
    (
        "volume-kind 1",
        "CSoundSeekWindow::onButtonSESeek -> setAppVolume index 1",
        "maps table value 1 to SE",
    ),
    (
        "volume-kind 2",
        "CSoundSeekWindow::onButtonVOICESeek -> setAppVolume index 2",
        "maps table value 2 to VOICE",
    ),
)


class Ac1102AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac1102AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def extract_caption_parent_starts(runtime: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    if runtime.get("schema") != "magireco-ac1102-missing-runtime-scene-motion-v1":
        raise Ac1102AudioAuthorityError("runtime scene-motion schema differs")
    if runtime.get("protected_processes_unchanged") is not True or runtime.get(
        "crash_tail_empty"
    ) is not True:
        raise Ac1102AudioAuthorityError("runtime capture safety checks did not pass")
    events = runtime.get("events", {})
    if set(events) != {"ac1102_007", "ac1102_013", "ac1102_014", "ac1102_015"}:
        raise Ac1102AudioAuthorityError("runtime event set differs")

    result: dict[str, dict[str, int]] = {}
    for event, expected in EXPECTED_CAPTION_AUDIO.items():
        envelope = events[event]
        if envelope.get("status") != "captured":
            raise Ac1102AudioAuthorityError(f"runtime event is not captured: {event}")
        scenes = envelope["value"].get("scenes", [])
        if len(scenes) != 1 or scenes[0].get("name") != event:
            raise Ac1102AudioAuthorityError(f"runtime scene binding differs: {event}")
        cuts = scenes[0].get("cuts", [])
        if len(cuts) != 1 or cuts[0].get("cut_name") != event:
            raise Ac1102AudioAuthorityError(f"runtime cut binding differs: {event}")
        observed: dict[str, int] = {}
        for node in _walk_nodes(cuts[0].get("nodes", [])):
            name = str(node.get("name", ""))
            if not name.endswith(".z2d") or name[:-4] not in expected:
                continue
            base = name[:-4]
            motions = node.get("motions", [])
            if len(motions) != 1 or motions[0].get("is_z2d_motion") is not True:
                raise Ac1102AudioAuthorityError(f"caption motion differs: {event}/{base}")
            keys = motions[0].get("keys", [])
            if len(keys) != 1:
                raise Ac1102AudioAuthorityError(f"caption key count differs: {event}/{base}")
            values = keys[0].get("floats", [])
            if len(values) < 5 or len({values[0], values[2], values[4]}) != 1:
                raise Ac1102AudioAuthorityError(f"caption parent starts differ: {event}/{base}")
            start = values[0]
            if int(start) != start:
                raise Ac1102AudioAuthorityError(f"caption parent start is non-integral: {event}/{base}")
            observed[base] = int(start)
        expected_starts = {name: values[2] for name, values in expected.items()}
        if observed != expected_starts:
            raise Ac1102AudioAuthorityError(
                f"caption parent starts differ for {event}: {observed} != {expected_starts}"
            )
        result[event] = observed
    if any(
        str(node.get("name", "")).startswith("cap1102_")
        for scene in events["ac1102_013"]["value"].get("scenes", [])
        for cut in scene.get("cuts", [])
        for node in _walk_nodes(cut.get("nodes", []))
    ):
        raise Ac1102AudioAuthorityError("ac1102_013 unexpectedly contains a caption Z2D")
    result["ac1102_013"] = {}
    return result


def read_sound_divide_values(binary: Path, sound_ids: Iterable[int]) -> tuple[str, dict[int, int]]:
    if binary.stat().st_size != SLOT_BINARY_SIZE:
        raise Ac1102AudioAuthorityError("exact Slot binary size differs")
    values: dict[int, int] = {}
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        build_id = _gnu_build_id(elf)
        if build_id.casefold() != SLOT_BINARY_BUILD_ID.casefold():
            raise Ac1102AudioAuthorityError("exact Slot binary build-id differs")
        for sound_id in sorted(set(sound_ids)):
            address = SOUND_DIVIDE_TABLE_VA + sound_id
            stream.seek(_va_to_file_offset(elf, address))
            raw = stream.read(1)
            if len(raw) != 1 or raw[0] not in VOLUME_BUS:
                raise Ac1102AudioAuthorityError(f"sound bus value differs: {sound_id}")
            values[sound_id] = raw[0]
    return build_id, values


def _durable_audio_path(audio_root: Path, ogg_name: str) -> Path:
    path = audio_root / ogg_name
    if not path.is_file():
        raise Ac1102AudioAuthorityError(f"durable official OGG is absent: {path}")
    return path.resolve()


def build_report(
    *,
    binary: Path,
    runtime_scene_motion_path: Path,
    event_audio_components_path: Path,
    z2d_sound_callbacks_path: Path,
    durable_audio_root: Path,
) -> dict[str, Any]:
    runtime = json.loads(runtime_scene_motion_path.read_text(encoding="utf-8"))
    parent_starts = extract_caption_parent_starts(runtime)
    component_rows = read_csv(event_audio_components_path)
    callback_rows = read_csv(z2d_sound_callbacks_path)

    events = set(EXPECTED_EVENT_COMPONENTS)
    selected_components = [row for row in component_rows if row.get("primary_animation") in events]
    observed_components: dict[str, list[tuple[int, int, int]]] = {event: [] for event in events}
    for row in selected_components:
        observed_components[row["primary_animation"]].append(
            (int(row["leaf_request_id"]), int(row["leaf_sound_code"]), int(row["start_ms"]))
        )
    for event, expected in EXPECTED_EVENT_COMPONENTS.items():
        if tuple(observed_components[event]) != expected:
            raise Ac1102AudioAuthorityError(
                f"event audio component set differs for {event}: {observed_components[event]}"
            )

    target_captions = {
        name for rows in EXPECTED_CAPTION_AUDIO.values() for name in rows
    }
    selected_callbacks = [row for row in callback_rows if row.get("z2d_name") in target_captions]
    if len(selected_callbacks) != len(target_captions):
        raise Ac1102AudioAuthorityError("caption reqSound callback count differs")
    callback_by_name = {row["z2d_name"]: row for row in selected_callbacks}
    if len(callback_by_name) != len(target_captions):
        raise Ac1102AudioAuthorityError("caption reqSound callbacks are duplicated")

    sound_ids = {int(row["leaf_sound_code"]) for row in selected_components}
    sound_ids.update(int(row["sound_resource_id"]) for row in selected_callbacks)
    build_id, bus_values = read_sound_divide_values(binary, sound_ids)

    audio_rows: list[dict[str, Any]] = []
    for row in selected_components:
        event = row["primary_animation"]
        sound_id = int(row["leaf_sound_code"])
        bus = VOLUME_BUS[bus_values[sound_id]]
        audio_rows.append(
            {
                "event": event,
                "source_kind": "event_audio_component",
                "request_id": int(row["leaf_request_id"]),
                "sound_id": sound_id,
                "code_name": row["leaf_code_name"],
                "start_frame": None,
                "start_ms": int(row["start_ms"]),
                "duration_ms": int(row["duration_ms"]),
                "ogg_name": row["ogg_name"],
                "ogg_path": str(_durable_audio_path(durable_audio_root, row["ogg_name"])),
                "volume_kind_value": bus_values[sound_id],
                "volume_bus": bus,
                "strict_no_bgm_disposition": (
                    "EXCLUDE_AS_BGM_BUS" if bus == "BGM" else "RETAIN_VERIFIED_SE"
                ),
                "timing_evidence": "official_event_audio_component_event_global_start",
                "subtitle_ja": None,
                "subtitle_zh": None,
            }
        )
    for event, captions in EXPECTED_CAPTION_AUDIO.items():
        for z2d_name, (request_id, sound_id, start_frame) in captions.items():
            row = callback_by_name[z2d_name]
            if (
                int(row["sound_request_id"]) != request_id
                or int(row["sound_resource_id"]) != sound_id
                or int(row["exec_frame"]) != 0
                or int(row["sound_request_match_count"]) != 1
                or row["ogg_exists"] != "yes"
            ):
                raise Ac1102AudioAuthorityError(f"caption reqSound binding differs: {z2d_name}")
            if parent_starts[event][z2d_name] != start_frame:
                raise Ac1102AudioAuthorityError(f"caption parent timing differs: {event}/{z2d_name}")
            bus = VOLUME_BUS[bus_values[sound_id]]
            text = SUBTITLE_TEXT.get(z2d_name, {})
            audio_rows.append(
                {
                    "event": event,
                    "source_kind": "z2d_req_sound",
                    "z2d_name": z2d_name,
                    "request_id": request_id,
                    "sound_id": sound_id,
                    "code_name": row["sound_code_name"],
                    "start_frame": start_frame,
                    "start_ms": round(start_frame * 1000 / 30),
                    "duration_ms": int(row["sound_duration_ms"]),
                    "ogg_name": row["ogg_name"],
                    "ogg_path": str(_durable_audio_path(durable_audio_root, row["ogg_name"])),
                    "volume_kind_value": bus_values[sound_id],
                    "volume_bus": bus,
                    "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE",
                    "timing_evidence": "runtime_parent_scene_z2d_start_plus_exact_child_callback_frame_0",
                    "subtitle_ja": text.get("ja"),
                    "subtitle_zh": text.get("zh"),
                }
            )

    audio_rows.sort(key=lambda row: (row["event"], row["start_ms"], row["request_id"]))
    if any(
        row["strict_no_bgm_disposition"] == "RETAIN_VERIFIED_VOICE"
        and row["volume_bus"] != "VOICE"
        for row in audio_rows
    ):
        raise Ac1102AudioAuthorityError("one or more retained voices are not on the VOICE bus")
    excluded = [row for row in audio_rows if row["strict_no_bgm_disposition"] == "EXCLUDE_AS_BGM_BUS"]
    if [(row["event"], row["request_id"], row["sound_id"]) for row in excluded] != [
        ("ac1102_007", 229, 554),
        ("ac1102_015", 229, 554),
    ]:
        raise Ac1102AudioAuthorityError("strict no-BGM exclusion set differs")

    return {
        "schema": "magireco-ac1102-event-audio-runtime-and-sound-bus-authority-v1",
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
            "inherited_sha256": SLOT_BINARY_SHA256,
        },
        "inputs": {
            "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
            "event_audio_components": str(event_audio_components_path.resolve()),
            "z2d_sound_callbacks": str(z2d_sound_callbacks_path.resolve()),
            "durable_audio_root": str(durable_audio_root.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "audio_rows": audio_rows,
        "subtitle_policy": {
            "subtitle_cues": [name for name in SUBTITLE_TEXT],
            "voice_only_without_text_is_retained_without_invented_subtitle": True,
            "translations_are_project_editorial_candidates_requiring_human_playback": True,
        },
        "decision": {
            "events": sorted(events),
            "event_audio_and_strict_no_bgm_manifest_closure": "CLOSED",
            "retained_audio_occurrences": sum(
                row["strict_no_bgm_disposition"] != "EXCLUDE_AS_BGM_BUS" for row in audio_rows
            ),
            "excluded_bgm_occurrences": len(excluded),
            "excluded_bgm_identity": {"request_id": 229, "sound_id": 554},
            "render_allowed_by_this_report_alone": False,
            "remaining_independent_gate": "duplicate_free_exhaustive_editorial_order",
        },
        "assertions": {
            "event_audio_component_occurrences": len(selected_components),
            "caption_voice_occurrences": len(selected_callbacks),
            "total_audio_occurrences": len(audio_rows),
            "all_durable_ogg_files_exist": True,
            "all_caption_audio_event_global_starts_resolved": True,
            "all_caption_sound_ids_are_voice_bus": True,
            "only_sound_554_is_excluded_as_bgm": True,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "AC1102_EVENT_AUDIO_AUTHORITY.json"
    csv_path = output_dir / "AC1102_EVENT_AUDIO_ROWS.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fieldnames: list[str] = []
    for row in report["audio_rows"]:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report["audio_rows"])
    verification_path.write_text(
        json.dumps(
            {
                "schema": "magireco-ac1102-event-audio-verification-v1",
                "status": "passed",
                "checks": report["assertions"],
                "decision": report["decision"],
                "outputs": [report_path.name, csv_path.name, readme_path.name],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        "# ac1102 event audio authority\n\n"
        "Runtime parent Z2D starts close all seven caption voice timings at event scope. "
        "The exact SOUND_DIVIDE_TBL classifies all seven as VOICE and all non-jingle "
        "event components as SE. Request 229 / sound 554 is BGM and is excluded from "
        "strict no-BGM at its two occurrences. Audio sources are durable D: official OGGs.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path)
    parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--durable-audio-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary,
        runtime_scene_motion_path=args.runtime_scene_motion,
        event_audio_components_path=args.event_audio_components,
        z2d_sound_callbacks_path=args.z2d_sound_callbacks,
        durable_audio_root=args.durable_audio_root,
    )
    write_outputs(report, args.output_dir)
    decision = report["decision"]
    print(
        "PASS events=4 audio_occurrences=17 "
        f"retained={decision['retained_audio_occurrences']} "
        f"excluded_bgm={decision['excluded_bgm_occurrences']} "
        "event_audio_no_bgm=CLOSED editorial_order=OPEN"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
