#!/usr/bin/env python3
"""Resolve Frida runtime events to game scene, subtitle, SMZ, and OGG metadata."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
from pathlib import Path


SCENE_RE = re.compile(r"\[(ac\d{4}_\d{3}(?:_[A-Za-z0-9_]+)?)\.dgm\]", re.IGNORECASE)
EVENT_RE = re.compile(r"^(ac\d{4}_\d{3})", re.IGNORECASE)
SOUND_RESOURCE_RE = re.compile(r"^(\d{4,5})(?:_|$)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--manifest-dir", default="asset_manifests")
    parser.add_argument("--ogg-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def read_csv_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return {row.get(key, ""): row for row in csv.DictReader(source) if row.get(key, "")}


def decode_data(record: dict) -> tuple[str, str]:
    encoded = record.get("data_base64", "")
    if not encoded:
        payload = record.get("message", {}).get("payload", {})
        return str(payload.get("text_utf8", "")), ""
    raw = base64.b64decode(encoded)
    utf8 = raw.decode("utf-8", errors="replace")
    cp932 = raw.decode("cp932", errors="replace")
    return utf8, cp932


def is_dialogue_text(text: str) -> bool:
    value = text.strip()
    if not value or value in {"<空白のテキストレイヤー>", "空白のテキストレイヤー"}:
        return False
    if value.startswith(("[", "<<", "null_", "ac")):
        return False
    return any(ord(char) > 127 for char in value)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def srt_timestamp(milliseconds: int) -> str:
    milliseconds = max(milliseconds, 0)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def main() -> int:
    args = parse_args()
    log_path = Path(args.log)
    manifest_dir = Path(args.manifest_dir)
    ogg_dir = Path(args.ogg_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    request_by_id = read_csv_index(manifest_dir / "sound_request_struct_requests.csv", "request_id")
    request_by_code = {
        row.get("code_name", ""): row for row in request_by_id.values() if row.get("code_name", "")
    }
    hash_by_id = read_csv_index(manifest_dir / "sound_hashreq_records.csv", "request_id")
    sound_by_resource = read_csv_index(manifest_dir / "sound_id_records.csv", "sound_resource_id")
    ogg_by_name = {path.name.lower(): path for path in ogg_dir.rglob("*.ogg")}

    current_scene = ""
    current_event = ""
    current_scene_ms: int | None = None
    current_text = ""
    current_text_ms: int | None = None
    text_rows: list[dict] = []
    sound_rows: list[dict] = []

    with log_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("message", {}).get("payload", {})
            kind = payload.get("kind", "")
            event_ms = int(payload.get("unix_ms") or record.get("host_unix_ms") or 0)
            text_utf8, text_cp932 = decode_data(record)

            if kind == "z2d_string_set":
                scene_match = SCENE_RE.fullmatch(text_utf8.strip())
                if scene_match:
                    current_scene = scene_match.group(1)
                    event_match = EVENT_RE.match(current_scene)
                    current_event = event_match.group(1) if event_match else ""
                    current_scene_ms = event_ms
                elif is_dialogue_text(text_utf8):
                    current_text = text_utf8.strip()
                    current_text_ms = event_ms
                    text_rows.append(
                        {
                            "line_number": line_number,
                            "unix_ms": event_ms,
                            "scene": current_scene,
                            "event": current_event,
                            "relative_to_scene_ms": (
                                event_ms - current_scene_ms if current_scene_ms is not None else ""
                            ),
                            "text_utf8": current_text,
                            "text_cp932": text_cp932.strip(),
                        }
                    )
                continue

            if kind not in {"sound_code_lookup", "sound_mng_play_bytes"}:
                continue

            code_name = text_utf8.strip()
            if kind == "sound_code_lookup":
                request_id = str(payload.get("return_u32", ""))
                request = request_by_id.get(request_id, {})
                timing_confidence = "request_lookup"
            else:
                request = request_by_code.get(code_name, {})
                request_id = request.get("request_id", "")
                timing_confidence = "actual_play_call"
            hash_row = hash_by_id.get(request_id, {})
            resource_match = SOUND_RESOURCE_RE.match(code_name)
            sound_resource_id = resource_match.group(1) if resource_match else ""
            sound = sound_by_resource.get(sound_resource_id, {})
            ogg_name = sound.get("suggested_name", "")
            ogg_path = ogg_by_name.get(ogg_name.lower()) if ogg_name else None
            label_text = ""
            parts = code_name.split("_", 3)
            if len(parts) == 4:
                label_text = parts[3]

            sound_rows.append(
                {
                    "line_number": line_number,
                    "unix_ms": event_ms,
                    "scene": current_scene,
                    "event": current_event,
                    "relative_to_scene_ms": (
                        event_ms - current_scene_ms if current_scene_ms is not None else ""
                    ),
                    "nearest_text": current_text,
                    "relative_to_text_ms": (
                        event_ms - current_text_ms if current_text_ms is not None else ""
                    ),
                    "code_name": code_name,
                    "trigger_kind": kind,
                    "timing_confidence": timing_confidence,
                    "request_id": request_id,
                    "request_table_code_name": request.get("code_name", ""),
                    "sound_resource_id": sound_resource_id,
                    "duration_ms": hash_row.get("duration_ms_u32", ""),
                    "smz_media": request.get("first_smz_media", ""),
                    "ogg_chunk_index": sound.get("ogg_chunk_index", ""),
                    "ogg_name": ogg_name,
                    "ogg_path": str(ogg_path) if ogg_path else "",
                    "label_text": label_text,
                    "is_dialogue": "yes" if label_text and any(ord(char) > 127 for char in label_text) else "no",
                }
            )

    text_fields = [
        "line_number",
        "unix_ms",
        "scene",
        "event",
        "relative_to_scene_ms",
        "text_utf8",
        "text_cp932",
    ]
    sound_fields = [
        "line_number",
        "unix_ms",
        "scene",
        "event",
        "relative_to_scene_ms",
        "nearest_text",
        "relative_to_text_ms",
        "code_name",
        "trigger_kind",
        "timing_confidence",
        "request_id",
        "request_table_code_name",
        "sound_resource_id",
        "duration_ms",
        "smz_media",
        "ogg_chunk_index",
        "ogg_name",
        "ogg_path",
        "label_text",
        "is_dialogue",
    ]
    write_csv(out_dir / "runtime_text_events.csv", text_rows, text_fields)
    write_csv(out_dir / "runtime_sound_requests.csv", sound_rows, sound_fields)

    actual_dialogue_keys = {
        (row["code_name"], row["scene"])
        for row in sound_rows
        if row["is_dialogue"] == "yes" and row["trigger_kind"] == "sound_mng_play_bytes"
    }
    dialogue_rows = [
        row
        for row in sound_rows
        if row["is_dialogue"] == "yes"
        and (
            row["trigger_kind"] == "sound_mng_play_bytes"
            or (row["code_name"], row["scene"]) not in actual_dialogue_keys
        )
    ]
    write_csv(out_dir / "runtime_dialogue_timeline.csv", dialogue_rows, sound_fields)

    capture_start_ms = min(
        [int(row["unix_ms"]) for row in text_rows + sound_rows if row.get("unix_ms")],
        default=0,
    )
    with (out_dir / "runtime_dialogue_timeline.srt").open("w", encoding="utf-8") as output:
        for index, row in enumerate(dialogue_rows, 1):
            start_ms = int(row["unix_ms"]) - capture_start_ms
            duration_ms = int(row["duration_ms"] or 2000)
            end_ms = start_ms + max(duration_ms, 500)
            output.write(
                f"{index}\n{srt_timestamp(start_ms)} --> {srt_timestamp(end_ms)}\n"
                f"{row['label_text']}\n\n"
            )

    print(f"[runtime-timeline] text events: {len(text_rows)}")
    print(f"[runtime-timeline] sound requests: {len(sound_rows)}")
    print(f"[runtime-timeline] dialogue requests: {len(dialogue_rows)}")
    print(f"[runtime-timeline] output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
