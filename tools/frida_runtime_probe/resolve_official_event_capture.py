#!/usr/bin/env python3
"""Resolve one official event capture to video, sound, and subtitle assets."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
from pathlib import Path


DGM_RE = re.compile(r"^\[(.+\.dgm)\]$", re.IGNORECASE)
SOUND_ID_RE = re.compile(r"^(\d{4,5})(?:_|\s|$)")
JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-log", required=True)
    parser.add_argument("--runtime-log", required=True)
    parser.add_argument("--manifest-dir", required=True)
    parser.add_argument("--ogg-dir", required=True)
    parser.add_argument("--video-map", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--window-before-ms", type=int, default=100)
    parser.add_argument("--window-after-ms", type=int, default=15000)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def payload(record: dict) -> dict:
    value = record.get("message", {}).get("payload", {})
    return value if isinstance(value, dict) else {}


def decode_text(record: dict) -> str:
    encoded = record.get("data_base64")
    if encoded:
        return base64.b64decode(encoded).decode("utf-8", errors="replace")
    return str(payload(record).get("text_utf8", ""))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def srt_time(milliseconds: int) -> str:
    value = max(milliseconds, 0)
    hours, value = divmod(value, 3_600_000)
    minutes, value = divmod(value, 60_000)
    seconds, millis = divmod(value, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def event_context(records: list[dict]) -> dict:
    context: dict = {}
    for record in records:
        item = payload(record)
        if item.get("kind") == "forced_event_context_started":
            context = {
                "event": item.get("forced_event_label", ""),
                "code_hex": item.get("forced_event_code", ""),
                "context_unix_ms": int(item.get("unix_ms", 0)),
                "request_id": item.get("forced_event_request_id"),
            }
        elif item.get("kind") == "scene_request_executed":
            context.setdefault("event", item.get("forced_event_label", ""))
            context.setdefault("code_hex", item.get("forced_event_code", ""))
            context["scene_request_unix_ms"] = int(item.get("unix_ms", 0))
            context["scene_object_source"] = (
                item.get("animation_state", {}).get("selected_source", "")
            )
    if not context:
        raise SystemExit("event log has no forced event context")
    context.setdefault("scene_request_unix_ms", context["context_unix_ms"])
    return context


def is_dialogue_text(text: str) -> bool:
    value = text.strip()
    if not value or value.startswith(("[", "<<")):
        return False
    if value in {"<空白のテキストレイヤー>", "空白のテキストレイヤー"}:
        return False
    return bool(JAPANESE_RE.search(value))


def main() -> int:
    args = parse_args()
    event_records = read_jsonl(Path(args.event_log))
    runtime_records = read_jsonl(Path(args.runtime_log))
    context = event_context(event_records)
    origin_ms = int(context["context_unix_ms"])
    start_ms = origin_ms - max(args.window_before_ms, 0)
    end_ms = origin_ms + max(args.window_after_ms, 0)

    manifest_dir = Path(args.manifest_dir)
    request_rows = read_csv(manifest_dir / "sound_request_struct_requests.csv")
    sound_rows_static = read_csv(manifest_dir / "sound_id_records.csv")
    hash_rows = read_csv(manifest_dir / "sound_hashreq_records.csv")
    request_by_id = {row["request_id"]: row for row in request_rows}
    request_by_code = {
        row["code_name"]: row for row in request_rows if row.get("code_name")
    }
    sound_by_id: dict[str, list[dict[str, str]]] = {}
    for row in sound_rows_static:
        sound_by_id.setdefault(row.get("sound_resource_id", ""), []).append(row)
    hash_by_request = {row["request_id"]: row for row in hash_rows}

    ogg_dir = Path(args.ogg_dir)
    ogg_by_name = {path.name.lower(): path for path in ogg_dir.rglob("*.ogg")}
    video_map_rows = read_csv(Path(args.video_map))
    video_by_name = {
        row.get("official_name", "").lower(): row
        for row in video_map_rows
        if row.get("official_name")
    }

    dgms: list[dict] = []
    texts: list[dict] = []
    sounds: list[dict] = []
    request_id_by_code: dict[str, str] = {}

    for line_number, record in enumerate(runtime_records, 1):
        item = payload(record)
        kind = str(item.get("kind", ""))
        unix_ms = int(item.get("unix_ms") or record.get("host_unix_ms") or 0)
        if unix_ms < start_ms or unix_ms > end_ms:
            continue
        relative_ms = unix_ms - origin_ms
        text = decode_text(record).strip()

        if kind == "z2d_string_set":
            match = DGM_RE.fullmatch(text)
            if match:
                dgm_name = match.group(1)
                official_name = Path(dgm_name).stem
                map_row = video_by_name.get(official_name.lower(), {})
                dgms.append(
                    {
                        "sequence": len(dgms),
                        "line_number": line_number,
                        "relative_ms": relative_ms,
                        "dgm_name": dgm_name,
                        "official_name": official_name,
                        "source_mp4": map_row.get("source_mp4", ""),
                        "target_mp4": map_row.get("target_mp4", ""),
                        "source_exists": map_row.get("source_exists", ""),
                        "event_prefix_match": (
                            "yes"
                            if official_name.lower().startswith(
                                str(context["event"]).lower()
                            )
                            else "no"
                        ),
                    }
                )
            elif is_dialogue_text(text):
                texts.append(
                    {
                        "sequence": len(texts),
                        "line_number": line_number,
                        "relative_ms": relative_ms,
                        "text": text,
                    }
                )
            continue

        if kind not in {"sound_code_lookup", "sound_mng_play_bytes"}:
            continue
        code_name = text
        if not code_name:
            continue
        if kind == "sound_code_lookup":
            request_id = str(item.get("return_u32", ""))
            if request_id:
                request_id_by_code[code_name] = request_id
        else:
            request_id = request_id_by_code.get(code_name, "")
        request_row = request_by_id.get(request_id, {}) or request_by_code.get(
            code_name, {}
        )
        if not request_id:
            request_id = request_row.get("request_id", "")
        hash_row = hash_by_request.get(request_id, {})
        match = SOUND_ID_RE.match(code_name)
        resource_id = str(int(match.group(1))) if match else ""
        sound_candidates = sound_by_id.get(resource_id, [])
        sound_row = sound_candidates[0] if sound_candidates else {}
        ogg_name = sound_row.get("suggested_name", "")
        ogg_path = ogg_by_name.get(ogg_name.lower()) if ogg_name else None
        label_text = code_name.split("_", 3)[-1] if code_name.count("_") >= 3 else ""
        sounds.append(
            {
                "sequence": len(sounds),
                "line_number": line_number,
                "relative_ms": relative_ms,
                "kind": kind,
                "code_name": code_name,
                "request_id": request_id,
                "sound_resource_id": resource_id,
                "duration_ms": hash_row.get("duration_ms_u32", ""),
                "ogg_name": ogg_name,
                "ogg_path": str(ogg_path) if ogg_path else "",
                "label_text": label_text,
                "is_dialogue": (
                    "yes" if label_text and JAPANESE_RE.search(label_text) else "no"
                ),
            }
        )

    actual_play_codes = {
        row["code_name"] for row in sounds if row["kind"] == "sound_mng_play_bytes"
    }
    sounds = [
        row
        for row in sounds
        if row["kind"] == "sound_mng_play_bytes"
        or row["code_name"] not in actual_play_codes
    ]
    for sequence, row in enumerate(sounds):
        row["sequence"] = sequence

    subtitles: list[dict] = []
    dialogue_sounds = [row for row in sounds if row["is_dialogue"] == "yes"]
    for index, sound in enumerate(dialogue_sounds):
        sound_time = int(sound["relative_ms"])
        preceding = [
            row for row in texts if int(row["relative_ms"]) <= sound_time + 100
        ]
        text_row = preceding[-1] if preceding else None
        subtitle_text = (
            text_row["text"] if text_row else sound.get("label_text", "").strip()
        )
        subtitle_start = (
            int(text_row["relative_ms"]) if text_row else max(sound_time - 100, 0)
        )
        duration_ms = int(sound.get("duration_ms") or 2000)
        subtitles.append(
            {
                "sequence": index,
                "start_ms": subtitle_start,
                "end_ms": sound_time + max(duration_ms, 500),
                "text": subtitle_text,
                "voice_start_ms": sound_time,
                "voice_code_name": sound["code_name"],
                "ogg_path": sound["ogg_path"],
                "mapping_basis": (
                    "runtime_text_before_voice" if text_row else "voice_code_label"
                ),
            }
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    video_fields = [
        "sequence",
        "line_number",
        "relative_ms",
        "dgm_name",
        "official_name",
        "source_mp4",
        "target_mp4",
        "source_exists",
        "event_prefix_match",
    ]
    sound_fields = [
        "sequence",
        "line_number",
        "relative_ms",
        "kind",
        "code_name",
        "request_id",
        "sound_resource_id",
        "duration_ms",
        "ogg_name",
        "ogg_path",
        "label_text",
        "is_dialogue",
    ]
    subtitle_fields = [
        "sequence",
        "start_ms",
        "end_ms",
        "text",
        "voice_start_ms",
        "voice_code_name",
        "ogg_path",
        "mapping_basis",
    ]
    write_csv(out_dir / "video_assets.csv", dgms, video_fields)
    write_csv(out_dir / "sound_assets.csv", sounds, sound_fields)
    write_csv(out_dir / "subtitle_timeline.csv", subtitles, subtitle_fields)
    with (out_dir / "subtitles.srt").open("w", encoding="utf-8") as output:
        for index, row in enumerate(subtitles, 1):
            output.write(
                f"{index}\n{srt_time(int(row['start_ms']))} --> "
                f"{srt_time(int(row['end_ms']))}\n{row['text']}\n\n"
            )

    manifest = {
        **context,
        "event_log": str(Path(args.event_log).resolve()),
        "runtime_log": str(Path(args.runtime_log).resolve()),
        "capture_window_relative_ms": [
            -max(args.window_before_ms, 0),
            max(args.window_after_ms, 0),
        ],
        "video_asset_count": len(dgms),
        "resolved_video_count": sum(
            1 for row in dgms if row.get("target_mp4") or row.get("source_mp4")
        ),
        "sound_asset_count": len(sounds),
        "resolved_ogg_count": sum(1 for row in sounds if row.get("ogg_path")),
        "runtime_text_count": len(texts),
        "subtitle_count": len(subtitles),
        "video_assets": dgms,
        "sound_assets": sounds,
        "subtitles": subtitles,
    }
    with (out_dir / "event_manifest.json").open("w", encoding="utf-8") as output:
        json.dump(manifest, output, ensure_ascii=False, indent=2)

    print(json.dumps(
        {
            "event": context["event"],
            "video_assets": len(dgms),
            "resolved_videos": manifest["resolved_video_count"],
            "sounds": len(sounds),
            "resolved_ogg": manifest["resolved_ogg_count"],
            "subtitles": len(subtitles),
            "out_dir": str(out_dir),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
