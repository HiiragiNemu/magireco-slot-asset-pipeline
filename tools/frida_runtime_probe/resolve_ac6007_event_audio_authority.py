#!/usr/bin/env python3
"""Resolve every ac6007 audio occurrence on the event-global GFD timeline."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .build_exhaustive_unique_longform import file_sha256
    from .resolve_ac1101_event_audio_authority import VOLUME_BUS, read_sound_divide_values
except ImportError:  # direct script execution
    from build_exhaustive_unique_longform import file_sha256  # type: ignore
    from resolve_ac1101_event_audio_authority import VOLUME_BUS, read_sound_divide_values  # type: ignore


EVENTS = tuple(f"ac6007_{index:03d}" for index in range(1, 11))
SLOT_BINARY_SHA256 = "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
EXPECTED_PRESENTATION_FRAMES = {
    "ac6007_001": 227,
    "ac6007_002": 120,
    "ac6007_003": 120,
    "ac6007_004": 120,
    "ac6007_005": 135,
    "ac6007_006": 150,
    "ac6007_007": 415,
    "ac6007_008": 440,
    "ac6007_009": 290,
    "ac6007_010": 450,
}
EXPECTED_EVENT_COMPONENTS = {
    "ac6007_001": {(1034, 4010, 0), (2192, 10000, 0)},
    "ac6007_002": {(2193, 10001, 0)},
    "ac6007_003": {(2194, 10002, 0)},
    "ac6007_004": {(2199, 10010, 0)},
    "ac6007_005": {(2195, 10004, 0), (2202, 10013, 0)},
    "ac6007_006": {(2196, 10005, 0)},
    "ac6007_007": {(1029, 4004, 0), (2200, 10011, 0), (225, 550, 9240)},
    "ac6007_008": {(1029, 4004, 0), (2201, 10012, 0), (225, 550, 10065)},
    "ac6007_009": {(1030, 4005, 0), (2197, 10008, 0)},
    "ac6007_010": {(2198, 10009, 0), (225, 550, 10395)},
}
EXPECTED_CALLBACK_OCCURRENCES = {
    "ac6007_002": {
        "cap6007_qkuma_fer_001": (1, 30),
        "cap6007_qkuma_san_002": (19, 48),
    },
    "ac6007_003": {"cap6007_qkuma_fer_003": (1, 30)},
    "ac6007_004": {
        "cap6007_qkuma_fer_010": (30, 59),
        "cap6007_qkuma_san_011": (40, 69),
        "ac8040_kyo_anten": (75, 104),
    },
    "ac6007_005": {"cap6007_qkuma_fer_005": (1, 85)},
    "ac6007_006": {"cap6007_qkuma_fer_006": (1, 45)},
    "ac6007_007": {
        "cap6007_qkuma_fer_004": (15, 34),
        "cap6007_qkuma_fer_009": (115, 155),
        "ac8000_cmn_tx_WIN": (155, 414),
    },
    "ac6007_008": {
        "cap6007_qkuma_fer_007": (15, 44),
        "cap6007_qkuma_san_008": (15, 44),
        "cap6007_qkuma_fer_009": (138, 178),
        "ac8000_cmn_tx_WIN": (180, 439),
    },
    "ac6007_009": {
        "cap6007_qkuma_fer_012": (13, 42),
        "cap6007_qkuma_san_013": (13, 42),
        "cap6007_qkuma_fer_014": (66, 101),
        "cap6007_qkuma_san_015": (106, 135),
    },
    "ac6007_010": {
        "cap6007_qkuma_fer_006": (1, 41),
        "cap6007_qkuma_fer_007": (47, 76),
        "cap6007_qkuma_san_008": (47, 76),
        "cap6007_qkuma_fer_009": (150, 189),
        "ac8000_cmn_tx_WIN": (190, 449),
    },
}
VOICE_REQUESTS = {
    4090, 4091, 4092, 4093, 4094, 4095, 4096, 4097, 4098, 4099,
    4356, 4358, 4359, 4360, 4361,
}


class Ac6007AudioAuthorityError(ValueError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac6007AudioAuthorityError(f"CSV is empty: {path}")
    return rows


def normalize_z2d_name(name: str) -> str:
    if name.endswith(".z2d1"):
        return name[:-5]
    if name.endswith(".z2d"):
        return name[:-4]
    return name


def extract_callback_occurrences(authority: Mapping[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    if authority.get("schema") != "magireco-ac6007-gfdirection-presentation-authority-v1":
        raise Ac6007AudioAuthorityError("GFD presentation schema differs")
    events = authority.get("events", [])
    if [row.get("event_id") for row in events] != list(EVENTS):
        raise Ac6007AudioAuthorityError("GFD presentation event order differs")
    observed_frames = {row["event_id"]: int(row["presentation_frame_count"]) for row in events}
    if observed_frames != EXPECTED_PRESENTATION_FRAMES:
        raise Ac6007AudioAuthorityError("GFD presentation frame counts differ")

    expected_names = {name for rows in EXPECTED_CALLBACK_OCCURRENCES.values() for name in rows}
    occurrences: list[dict[str, Any]] = []
    all_node_names: set[str] = set()
    for event in events:
        event_id = event["event_id"]
        for scene in event.get("scenes", []):
            for cut in scene.get("cuts", []):
                for node in cut.get("z2d_nodes", []):
                    name = normalize_z2d_name(str(node["z2d_node"]))
                    all_node_names.add(name)
                    if name not in expected_names:
                        continue
                    keys = node.get("motion_keys", [])
                    if len(keys) != 1:
                        raise Ac6007AudioAuthorityError(f"audio node motion-key count differs: {event_id}/{name}")
                    key = keys[0]
                    occurrences.append(
                        {
                            "event": event_id,
                            "z2d_name": name,
                            "start_frame": int(key["event_global_start_frame"]),
                            "end_frame_inclusive": int(key["event_global_end_frame_inclusive"]),
                        }
                    )
    observed = {
        event: {
            row["z2d_name"]: (row["start_frame"], row["end_frame_inclusive"])
            for row in occurrences
            if row["event"] == event
        }
        for event in EXPECTED_CALLBACK_OCCURRENCES
    }
    if observed != EXPECTED_CALLBACK_OCCURRENCES:
        raise Ac6007AudioAuthorityError(f"event-global callback occurrence set differs: {observed}")
    if len(occurrences) != 24 or len(all_node_names) != 32:
        raise Ac6007AudioAuthorityError("GFD Z2D/callback dimensions differ")
    return occurrences, all_node_names


def load_translations(path: Path) -> dict[int, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("translations", [])
    result = {int(row["request_id"]): dict(row) for row in rows}
    if set(result) != VOICE_REQUESTS or len(rows) != len(result):
        raise Ac6007AudioAuthorityError("ac6007 translation request set differs")
    for request_id, row in result.items():
        if not row.get("ja") or not row.get("zh") or not row.get("status"):
            raise Ac6007AudioAuthorityError(f"translation fields differ: {request_id}")
    return result


def durable_audio_path(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise Ac6007AudioAuthorityError(f"durable official OGG is absent: {path}")
    return path.resolve()


def build_report(
    *,
    binary: Path,
    presentation_authority_path: Path,
    event_audio_components_path: Path,
    z2d_sound_callbacks_path: Path,
    translation_path: Path,
    durable_audio_root: Path,
) -> dict[str, Any]:
    binary_hash = file_sha256(binary)
    if binary_hash != SLOT_BINARY_SHA256:
        raise Ac6007AudioAuthorityError("exact Slot binary SHA-256 differs")
    presentation = json.loads(presentation_authority_path.read_text(encoding="utf-8"))
    callback_occurrences, all_node_names = extract_callback_occurrences(presentation)
    translations = load_translations(translation_path)

    components = [row for row in read_csv(event_audio_components_path) if row.get("root") == "ac6007"]
    component_by_key: dict[tuple[str, int, int, int], dict[str, str]] = {}
    for row in components:
        key = (
            row["primary_animation"],
            int(row["leaf_request_id"]),
            int(row["leaf_sound_code"]),
            int(row["start_ms"]),
        )
        if key in component_by_key:
            raise Ac6007AudioAuthorityError(f"duplicate event audio component: {key}")
        component_by_key[key] = row
    observed_components = {event: set() for event in EVENTS}
    for event, request_id, sound_id, start_ms in component_by_key:
        observed_components[event].add((request_id, sound_id, start_ms))
    if observed_components != EXPECTED_EVENT_COMPONENTS or len(component_by_key) != 18:
        raise Ac6007AudioAuthorityError("event audio component set differs")

    callback_rows = [
        row
        for row in read_csv(z2d_sound_callbacks_path)
        if row.get("z2d_name") in all_node_names and row.get("function_name") == "reqSound"
    ]
    callbacks: dict[str, dict[str, str]] = {}
    for row in callback_rows:
        if row["z2d_name"] in callbacks:
            raise Ac6007AudioAuthorityError(f"duplicate reqSound callback: {row['z2d_name']}")
        callbacks[row["z2d_name"]] = row
    expected_callback_names = {name for rows in EXPECTED_CALLBACK_OCCURRENCES.values() for name in rows}
    if set(callbacks) != expected_callback_names or len(callbacks) != 17:
        raise Ac6007AudioAuthorityError("reqSound callback-name set differs")

    sound_ids = {sound_id for _, _, sound_id, _ in component_by_key}
    sound_ids.update(int(callbacks[row["z2d_name"]]["sound_resource_id"]) for row in callback_occurrences)
    build_id, bus_values = read_sound_divide_values(binary, sound_ids)
    audio_rows: list[dict[str, Any]] = []
    subtitle_cues: list[dict[str, Any]] = []

    for (event, request_id, sound_id, start_ms), row in component_by_key.items():
        bus = VOLUME_BUS[bus_values[sound_id]]
        audio_rows.append(
            {
                "event": event,
                "source_kind": "event_audio_component",
                "z2d_name": None,
                "request_id": request_id,
                "sound_id": sound_id,
                "code_name": row["leaf_code_name"],
                "start_frame": None,
                "start_ms": start_ms,
                "duration_ms": int(row["duration_ms"]),
                "ogg_name": row["ogg_name"],
                "ogg_path": str(durable_audio_path(durable_audio_root, row["ogg_name"])),
                "volume_kind_value": bus_values[sound_id],
                "volume_bus": bus,
                "strict_no_bgm_disposition": "EXCLUDE_AS_BGM_BUS" if bus == "BGM" else "RETAIN_VERIFIED_SE",
                "timing_evidence": "official_event_audio_component_event_global_start",
                "subtitle_ja": None,
                "subtitle_zh": None,
            }
        )

    for occurrence in callback_occurrences:
        callback = callbacks[occurrence["z2d_name"]]
        request_id = int(callback["sound_request_id"])
        sound_id = int(callback["sound_resource_id"])
        bus = VOLUME_BUS[bus_values[sound_id]]
        if (
            int(callback["exec_frame"]) != 0
            or callback["sound_request_match_count"] != "1"
            or callback["ogg_exists"] != "yes"
        ):
            raise Ac6007AudioAuthorityError(
                f"reqSound callback binding differs: {occurrence['event']}/{occurrence['z2d_name']}"
            )
        expected_bus = "VOICE" if request_id in VOICE_REQUESTS else "SE"
        if bus != expected_bus:
            raise Ac6007AudioAuthorityError(
                f"reqSound bus differs: {occurrence['event']}/{occurrence['z2d_name']}/{bus}"
            )
        start_ms = round(occurrence["start_frame"] * 1000 / 30)
        duration_ms = int(callback["sound_duration_ms"])
        translation = translations.get(request_id)
        subtitle_ja = None if translation is None else translation["ja"]
        subtitle_zh = None if translation is None else translation["zh"]
        audio_rows.append(
            {
                "event": occurrence["event"],
                "source_kind": "z2d_req_sound",
                "z2d_name": occurrence["z2d_name"],
                "request_id": request_id,
                "sound_id": sound_id,
                "code_name": callback["sound_code_name"],
                "start_frame": occurrence["start_frame"],
                "start_ms": start_ms,
                "duration_ms": duration_ms,
                "ogg_name": callback["ogg_name"],
                "ogg_path": str(durable_audio_path(durable_audio_root, callback["ogg_name"])),
                "volume_kind_value": bus_values[sound_id],
                "volume_bus": bus,
                "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE" if bus == "VOICE" else "RETAIN_VERIFIED_SE",
                "timing_evidence": "static_parent_gfd_z2d_event_global_start_plus_exact_child_callback_frame_0",
                "subtitle_ja": subtitle_ja,
                "subtitle_zh": subtitle_zh,
            }
        )
        if translation is not None:
            visual_end_ms = round((occurrence["end_frame_inclusive"] + 1) * 1000 / 30)
            subtitle_cues.append(
                {
                    "event": occurrence["event"],
                    "z2d_name": occurrence["z2d_name"],
                    "voice_request_id": request_id,
                    "start_frame": occurrence["start_frame"],
                    "start_ms": start_ms,
                    "end_ms": max(start_ms + duration_ms, visual_end_ms),
                    "ja": translation["ja"],
                    "zh": translation["zh"],
                    "translation_status": translation["status"],
                    "evidence": "static_parent_gfd_z2d_event_global_start_and_official_reqSound",
                }
            )

    audio_rows.sort(key=lambda row: (row["event"], row["start_ms"], row["request_id"], str(row["z2d_name"])))
    subtitle_cues.sort(key=lambda row: (row["event"], row["start_ms"], row["voice_request_id"]))
    excluded = [row for row in audio_rows if row["strict_no_bgm_disposition"] == "EXCLUDE_AS_BGM_BUS"]
    excluded_identity = [(row["event"], row["request_id"], row["sound_id"], row["start_ms"]) for row in excluded]
    if excluded_identity != [
        ("ac6007_007", 225, 550, 9240),
        ("ac6007_008", 225, 550, 10065),
        ("ac6007_010", 225, 550, 10395),
    ]:
        raise Ac6007AudioAuthorityError(f"strict no-BGM exclusion set differs: {excluded_identity}")
    if len(audio_rows) != 42 or len(subtitle_cues) != 20:
        raise Ac6007AudioAuthorityError("ac6007 final audio/subtitle dimensions differ")

    input_paths = {
        "presentation_authority": presentation_authority_path,
        "event_audio_components": event_audio_components_path,
        "z2d_sound_callbacks": z2d_sound_callbacks_path,
        "translation": translation_path,
    }
    return {
        "schema": "magireco-ac6007-event-audio-gfdirection-and-sound-bus-authority-v1",
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "sha256": binary_hash,
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
        },
        "inputs": {
            name: {"path": str(path.resolve()), "sha256": file_sha256(path)}
            for name, path in input_paths.items()
        }
        | {"durable_audio_root": str(durable_audio_root.resolve())},
        "code_authority": [
            {
                "address": "0x1445c54",
                "function": "SOUND_DIVIDE_TBL",
                "proves": "indexes the exact BGM/SE/VOICE volume-kind byte by sound resource id",
            },
            {
                "address": "0x42b0374/0x42b7824/0x42b74b4",
                "function": "CGFDirectionNodeLayer::Load / parameter Load / Calc",
                "proves": "binds each parent Z2D node to its event-global keyed frame interval",
            },
        ],
        "audio_rows": audio_rows,
        "subtitle_cues": subtitle_cues,
        "decision": {
            "events": list(EVENTS),
            "event_global_child_audio_timing": "CLOSED",
            "event_audio_and_strict_no_bgm_manifest_closure": "CLOSED",
            "retained_audio_occurrences": 39,
            "excluded_bgm_occurrences": 3,
            "excluded_bgm_identity": {"request_id": 225, "sound_id": 550},
            "render_allowed_by_this_report_alone": False,
            "remaining_independent_gate": "duplicate_free_exhaustive_editorial_order_and_visual_composition",
        },
        "assertions": {
            "event_audio_component_occurrences_after_exact_dedup": len(component_by_key),
            "gfdirection_reqSound_occurrences": len(callback_occurrences),
            "total_audio_occurrences": len(audio_rows),
            "retained_audio_occurrences": len(audio_rows) - len(excluded),
            "excluded_bgm_occurrences": len(excluded),
            "subtitle_cues": len(subtitle_cues),
            "all_durable_ogg_files_exist": True,
            "all_voice_request_ids_are_voice_bus": all(
                row["volume_bus"] == "VOICE"
                for row in audio_rows
                if row["request_id"] in VOICE_REQUESTS
            ),
            "all_retained_non_voice_rows_are_se_bus": all(
                row["volume_bus"] == "SE"
                for row in audio_rows
                if row["request_id"] not in VOICE_REQUESTS
                and row["strict_no_bgm_disposition"] != "EXCLUDE_AS_BGM_BUS"
            ),
            "only_sound_550_is_excluded_as_bgm": all(row["sound_id"] == 550 for row in excluded),
            "child_local_timing_used_as_event_global_authority": False,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = list(rows)
    fields: list[str] = []
    for row in materialized:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(materialized)


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac6007AudioAuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC6007_EVENT_AUDIO_AUTHORITY.json"
    audio_path = output_dir / "EVENT_AUDIO_OCCURRENCES.csv"
    subtitle_path = output_dir / "EVENT_SUBTITLE_CUES.csv"
    verification_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    rollback_path = output_dir / "ROLLBACK.ps1"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(audio_path, report["audio_rows"])
    _write_csv(subtitle_path, report["subtitle_cues"])
    readme_path.write_text(
        "# ac6007 event-global audio authority\n\n"
        "The exact GFD parent node keys bind 24 reqSound occurrences to event-global frames. "
        "SOUND_DIVIDE_TBL retains 39 SE/VOICE occurrences and excludes three request 225 / "
        "sound 550 BGM occurrences. Twenty dialogue cues are bound; new-route translations "
        "remain explicit human-review candidates. No media was changed.\n",
        encoding="utf-8",
    )
    rollback_path.write_text(
        "param([string]$Checkpoint = $PSScriptRoot)\n"
        "$target = $Checkpoint + '.disabled'\n"
        "if (Test-Path -LiteralPath $target) { throw \"Rollback target already exists: $target\" }\n"
        "Move-Item -LiteralPath $Checkpoint -Destination $target\n"
        "Write-Output \"ROLLBACK_OK $target\"\n",
        encoding="utf-8-sig",
    )
    output_hashes = {
        path.name: file_sha256(path)
        for path in (report_path, audio_path, subtitle_path, readme_path, rollback_path)
    }
    verification_path.write_text(
        json.dumps(
            {
                "schema": "magireco-ac6007-event-audio-verification-v1",
                "status": "passed",
                "checks": report["assertions"],
                "decision": report["decision"],
                "output_sha256": output_hashes,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--presentation-authority", required=True, type=Path)
    parser.add_argument("--event-audio-components", required=True, type=Path)
    parser.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    parser.add_argument("--translation", required=True, type=Path)
    parser.add_argument("--durable-audio-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary,
        presentation_authority_path=args.presentation_authority,
        event_audio_components_path=args.event_audio_components,
        z2d_sound_callbacks_path=args.z2d_sound_callbacks,
        translation_path=args.translation,
        durable_audio_root=args.durable_audio_root,
    )
    write_outputs(report, args.output_dir)
    print("PASS events=10 audio=42 retained=39 excluded_bgm=3 subtitles=20 audio_gate=CLOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
