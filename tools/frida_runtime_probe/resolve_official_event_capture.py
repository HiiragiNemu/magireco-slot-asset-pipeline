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
VOICE_SPEAKER_TOKENS = {
    "ari", "fel", "fer", "hom", "iro", "kae", "kan", "kyo",
    "kuro", "kuroe", "mad", "mam", "mami", "mif", "mihu",
    "mit", "mita", "mom", "nag", "nem", "nemu", "ren", "rena",
    "qb", "riko", "sana", "say", "sigure", "sqb", "toka", "tou", "tsu",
    "tukasa", "tukuyo", "tur", "turk", "ui", "uwa", "yac", "yach",
}
STRING_SOUND_KINDS = {"sound_code_lookup", "sound_mng_play_bytes"}
HIGH_LEVEL_STRING_SOUND_KINDS = {
    "sound_mng_play_by_sound_cd",
    "snd_req_by_sound_cd",
    "ctrl_snd_req_sound_code",
    "ctrl_snd_req_sound_code_timed",
    "ctrl_snd_req_sequence_sc",
    "ctrl_snd_req_sound_code_callback",
    "ctrl_snd_req_now",
    "ctrl_snd_call_code_callback",
    "snd_proc_code_callback",
    "zg_snd_req_code",
    "zg_snd_req_fade_code",
    "zg_snd_req_volume_code",
    "zg_snd_req_pause_code",
}
HIGH_LEVEL_EVENT_SOUND_KINDS = {
    "ctrl_snd_req_event_code",
}
BGM_CONTROL_KINDS = {
    "obj_nml_snd_request_bgm_sequence",
    "obj_nml_snd_request_bgm_dir",
    "obj_nml_snd_request_bgm_stg",
    "obj_nml_snd_request_bgm_end",
    "obj_nml_snd_request_bgm_dir_next",
    "obj_nml_snd_request_bgm_fade_next",
    "obj_nml_snd_request_bgm_fade",
    "direction_macro_snd_bgm_play",
    "obj_select_bns_snd_request_bgm",
    "sound_mng_is_already_playing_bgm",
    "snd_is_already_playing_bgm",
}
INT_SOUND_KINDS = {
    "sound_mng_play",
    "sound_mng_play_request",
    "sound_mng_wrap_request",
    "sound_mng_wrap_request_channel",
    "request_get",
    "sound_system_get_request",
}
ACTUAL_PLAY_KINDS = {
    "sound_mng_play_bytes",
    "sound_mng_play_by_sound_cd",
    "snd_req_by_sound_cd",
    "sound_mng_play",
    "sound_mng_play_request",
    "sound_mng_wrap_request",
    "sound_mng_wrap_request_channel",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-log", required=True)
    parser.add_argument("--runtime-log", required=True)
    parser.add_argument("--manifest-dir", required=True)
    parser.add_argument("--ogg-dir", required=True)
    parser.add_argument("--video-map", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--window-before-ms", type=int, default=100)
    parser.add_argument("--window-after-ms", type=int, default=60000)
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


def decode_sound_text(record: dict) -> str:
    text = decode_text(record).strip()
    if text:
        return text
    item = payload(record)
    for key in ("arg0_text_utf8", "arg1_text_utf8"):
        text = str(item.get(key, "")).strip()
        if text:
            return text
    return ""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv(path)


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
    event_sound_request_sent_count = 0
    for record in records:
        item = payload(record)
        if item.get("kind") == "forced_event_context_started":
            request = item.get("request", {})
            if not isinstance(request, dict):
                request = {}
            context = {
                "event": item.get("forced_event_label", ""),
                "code_hex": item.get("forced_event_code", ""),
                "context_unix_ms": int(item.get("unix_ms", 0)),
                "request_id": item.get("forced_event_request_id"),
                "event_sound_requested": bool(request.get("with_sound")),
            }
        elif item.get("kind") == "forced_event_sound_request_sent":
            event_sound_request_sent_count += 1
        elif item.get("kind") == "scene_request_executed":
            context.setdefault("event", item.get("forced_event_label", ""))
            context.setdefault("code_hex", item.get("forced_event_code", ""))
            context["scene_request_unix_ms"] = int(item.get("unix_ms", 0))
            context["scene_object_source"] = (
                item.get("animation_state", {}).get("selected_source", "")
            )
            request = item.get("request", {})
            if isinstance(request, dict) and "event_sound_requested" not in context:
                context["event_sound_requested"] = bool(request.get("with_sound"))
    if not context:
        raise SystemExit("event log has no forced event context")
    context.setdefault("scene_request_unix_ms", context["context_unix_ms"])
    context.setdefault("event_sound_requested", False)
    context["event_sound_request_sent_count"] = event_sound_request_sent_count
    return context


def is_dialogue_text(text: str) -> bool:
    value = text.strip()
    if not value or value.startswith(("[", "<<")):
        return False
    if value in {"<空白のテキストレイヤー>", "空白のテキストレイヤー"}:
        return False
    return bool(JAPANESE_RE.search(value))


def is_dialogue_sound(code_name: str, label_text: str) -> bool:
    if not label_text or not JAPANESE_RE.search(label_text):
        return False
    # Runtime effect labels sometimes occupy the broad 30k voice-id range.
    # A label explicitly ending in SE/BGM is an effect track even when it
    # contains a character name or Japanese scene description.
    if label_text.strip().casefold().endswith(("se", "bgm")):
        return False
    parts = [part.casefold() for part in code_name.split("_")]
    match = SOUND_ID_RE.match(code_name)
    resource_id = int(match.group(1)) if match else 0
    has_speaker = any(part in VOICE_SPEAKER_TOKENS for part in parts[1:-1])
    return has_speaker or 30000 <= resource_id < 40000


def sound_resource_id(code_name: str) -> str:
    if re.fullmatch(r"\d{1,5}", code_name):
        return str(int(code_name))
    match = SOUND_ID_RE.match(code_name)
    return str(int(match.group(1))) if match else ""


def voice_label_text(code_name: str) -> str:
    parts = code_name.split("_")
    folded = [part.casefold() for part in parts]
    if len(parts) >= 5 and any(
        part in VOICE_SPEAKER_TOKENS for part in folded[1:-1]
    ):
        return parts[-1]
    return code_name.split("_", 3)[-1] if code_name.count("_") >= 3 else ""


def resolve_request_media(
    *,
    code_name: str,
    request_id: str,
    request_by_id: dict[str, dict[str, str]],
    request_by_code: dict[str, dict[str, str]],
    sound_by_id: dict[str, list[dict[str, str]]],
    sound_by_ogg_chunk: dict[str, list[dict[str, str]]],
    hash_by_request: dict[str, dict[str, str]],
    ogg_by_name: dict[str, Path],
) -> dict[str, str]:
    request_row = request_by_id.get(request_id, {}) or request_by_code.get(
        code_name, {}
    )
    if not request_id:
        request_id = request_row.get("request_id", "")
    if not code_name:
        code_name = request_row.get("code_name", "")
    hash_row = hash_by_request.get(request_id, {})
    resource_id = sound_resource_id(code_name)
    sound_candidates = sound_by_id.get(resource_id, [])
    mapping_basis_suffix = "sound_resource_id"
    if not sound_candidates and resource_id:
        sound_candidates = sound_by_ogg_chunk.get(resource_id, [])
        mapping_basis_suffix = "ogg_chunk_index"
    sound_row = sound_candidates[0] if sound_candidates else {}
    ogg_name = sound_row.get("suggested_name", "")
    ogg_path = ogg_by_name.get(ogg_name.lower()) if ogg_name else None
    label_text = voice_label_text(code_name)
    return {
        "code_name": code_name,
        "request_id": request_id,
        "sound_resource_id": resource_id,
        "duration_ms": hash_row.get("duration_ms_u32", ""),
        "ogg_name": ogg_name,
        "ogg_path": str(ogg_path) if ogg_path else "",
        "label_text": label_text,
        "is_dialogue": "yes" if is_dialogue_sound(code_name, label_text) else "no",
        "media_mapping_basis": mapping_basis_suffix if sound_row else "",
    }


def resolve_int_sound_candidates(
    item: dict,
    *,
    kind: str,
    request_by_id: dict[str, dict[str, str]],
    request_by_code: dict[str, dict[str, str]],
    sound_by_id: dict[str, list[dict[str, str]]],
    sound_by_ogg_chunk: dict[str, list[dict[str, str]]],
    hash_by_request: dict[str, dict[str, str]],
    ogg_by_name: dict[str, Path],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    if kind in {
        "sound_mng_play",
        "sound_mng_play_request",
        "sound_mng_wrap_request",
        "sound_mng_wrap_request_channel",
    }:
        candidate_keys = [("arg0_i32", "sound_resource_or_numeric_code")]
    elif kind in {"request_get", "sound_system_get_request"}:
        candidate_keys = [("arg0_i32", "request_id")]
    else:
        candidate_keys = []
    for key, basis_kind in candidate_keys:
        if key not in item:
            continue
        value = item[key]
        candidate = str(value)
        if basis_kind == "request_id" and candidate in request_by_id:
            request = request_by_id[candidate]
            media = resolve_request_media(
                code_name=request.get("code_name", ""),
                request_id=candidate,
                request_by_id=request_by_id,
                request_by_code=request_by_code,
                sound_by_id=sound_by_id,
                sound_by_ogg_chunk=sound_by_ogg_chunk,
                hash_by_request=hash_by_request,
                ogg_by_name=ogg_by_name,
            )
            media["mapping_basis"] = f"{key}:request_id"
        elif candidate in request_by_code:
            request = request_by_code[candidate]
            media = resolve_request_media(
                code_name=candidate,
                request_id=request.get("request_id", ""),
                request_by_id=request_by_id,
                request_by_code=request_by_code,
                sound_by_id=sound_by_id,
                sound_by_ogg_chunk=sound_by_ogg_chunk,
                hash_by_request=hash_by_request,
                ogg_by_name=ogg_by_name,
            )
            media["mapping_basis"] = f"{key}:numeric_code_name"
        elif candidate in sound_by_id:
            request = request_by_code.get(candidate, {})
            media = resolve_request_media(
                code_name=request.get("code_name", candidate),
                request_id=request.get("request_id", ""),
                request_by_id=request_by_id,
                request_by_code=request_by_code,
                sound_by_id=sound_by_id,
                sound_by_ogg_chunk=sound_by_ogg_chunk,
                hash_by_request=hash_by_request,
                ogg_by_name=ogg_by_name,
            )
            media["mapping_basis"] = f"{key}:sound_resource_id"
        elif candidate in sound_by_ogg_chunk:
            request = request_by_code.get(candidate, {})
            media = resolve_request_media(
                code_name=request.get("code_name", candidate),
                request_id=request.get("request_id", ""),
                request_by_id=request_by_id,
                request_by_code=request_by_code,
                sound_by_id=sound_by_id,
                sound_by_ogg_chunk=sound_by_ogg_chunk,
                hash_by_request=hash_by_request,
                ogg_by_name=ogg_by_name,
            )
            media["mapping_basis"] = f"{key}:ogg_chunk_index"
        else:
            continue
        row_key = (
            media.get("request_id", ""),
            media.get("code_name", ""),
            media.get("mapping_basis", ""),
        )
        if row_key in seen:
            continue
        seen.add(row_key)
        rows.append(media)
    return rows


def high_level_unresolved_reason(media: dict[str, str]) -> str:
    reasons: list[str] = []
    if not media.get("request_id"):
        reasons.append("no_request_id")
    if not media.get("ogg_path"):
        reasons.append("no_resolved_ogg")
    return ";".join(reasons)


def merge_adjacent_subtitles(rows: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for row in rows:
        if (
            merged
            and row["text"] == merged[-1]["text"]
            and int(row["start_ms"]) <= int(merged[-1]["end_ms"]) + 150
        ):
            merged[-1]["end_ms"] = max(
                int(merged[-1]["end_ms"]),
                int(row["end_ms"]),
            )
            merged[-1]["voice_code_name"] = ";".join(
                filter(
                    None,
                    [
                        merged[-1].get("voice_code_name", ""),
                        row.get("voice_code_name", ""),
                    ],
                )
            )
            merged[-1]["mapping_basis"] = "runtime_text_merged_adjacent_voice"
            continue
        merged.append(dict(row))
    for index, row in enumerate(merged):
        row["sequence"] = index
    return merged


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
    sound_rows_static.extend(
        read_csv_if_exists(manifest_dir / "internal_audit" / "sound_id_records.csv")
    )
    hash_rows = read_csv(manifest_dir / "sound_hashreq_records.csv")
    request_by_id = {row["request_id"]: row for row in request_rows}
    request_by_code = {
        row["code_name"]: row for row in request_rows if row.get("code_name")
    }
    sound_by_id: dict[str, list[dict[str, str]]] = {}
    for row in sound_rows_static:
        sound_by_id.setdefault(row.get("sound_resource_id", ""), []).append(row)
    sound_by_ogg_chunk: dict[str, list[dict[str, str]]] = {}
    for row in sound_rows_static:
        sound_by_ogg_chunk.setdefault(row.get("ogg_chunk_index", ""), []).append(row)
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
    unresolved_sound_events: list[dict] = []
    ignored_sound_events: list[dict] = []
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

        if kind not in (
            STRING_SOUND_KINDS
            | HIGH_LEVEL_STRING_SOUND_KINDS
            | HIGH_LEVEL_EVENT_SOUND_KINDS
            | INT_SOUND_KINDS
            | BGM_CONTROL_KINDS
        ):
            continue

        raw_int_args = ";".join(
            f"{key}={value}"
            for key, value in sorted(item.items())
            if key.endswith("_i32")
        )
        raw_u64_args = ";".join(
            f"{key}={value}"
            for key, value in sorted(item.items())
            if key.endswith("_u64_hex") or key.endswith("_u64_pointer")
        )

        if kind in HIGH_LEVEL_EVENT_SOUND_KINDS:
            unresolved_sound_events.append(
                {
                    "sequence": len(unresolved_sound_events),
                    "line_number": line_number,
                    "relative_ms": relative_ms,
                    "kind": kind,
                    "code_name": "",
                    "event_code_hex": str(item.get("arg1_u64_hex", "")),
                    "mapping_basis": "high_level_event_code_request",
                    "unresolved_reason": (
                        "event_code_request_requires_runtime_followup_sound_calls"
                    ),
                    "raw_int_args": raw_int_args,
                    "raw_u64_args": raw_u64_args,
                }
            )
            continue

        if kind in BGM_CONTROL_KINDS:
            unresolved_sound_events.append(
                {
                    "sequence": len(unresolved_sound_events),
                    "line_number": line_number,
                    "relative_ms": relative_ms,
                    "kind": kind,
                    "code_name": "",
                    "event_code_hex": "",
                    "mapping_basis": "bgm_control_or_status_call",
                    "unresolved_reason": (
                        "bgm_control_call_requires_followup_sound_code_or_mix_capture"
                    ),
                    "raw_int_args": raw_int_args,
                    "raw_u64_args": raw_u64_args,
                }
            )
            continue

        resolved_media: list[dict[str, str]]
        if kind in STRING_SOUND_KINDS | HIGH_LEVEL_STRING_SOUND_KINDS:
            code_name = decode_sound_text(record)
            if not code_name:
                ignored_sound_events.append(
                    {
                        "sequence": len(ignored_sound_events),
                        "line_number": line_number,
                        "relative_ms": relative_ms,
                        "kind": kind,
                        "code_name": "",
                        "event_code_hex": "",
                        "mapping_basis": "empty_string_sound_request",
                        "ignored_reason": "empty_sound_code_string",
                        "raw_int_args": raw_int_args,
                        "raw_u64_args": raw_u64_args,
                    }
                )
                continue
            if kind == "sound_code_lookup":
                request_id = str(item.get("return_u32", ""))
                if request_id:
                    request_id_by_code[code_name] = request_id
                mapping_basis = "code_name_lookup"
            elif kind == "sound_mng_play_bytes":
                request_id = request_id_by_code.get(code_name, "")
                mapping_basis = "actual_play_code_name"
            elif kind in {"sound_mng_play_by_sound_cd", "snd_req_by_sound_cd"}:
                request_id = request_id_by_code.get(code_name, "")
                mapping_basis = "actual_play_sound_cd"
            else:
                request_id = request_id_by_code.get(code_name, "")
                mapping_basis = f"high_level_request:{kind}"
            media = resolve_request_media(
                code_name=code_name,
                request_id=request_id,
                request_by_id=request_by_id,
                request_by_code=request_by_code,
                sound_by_id=sound_by_id,
                sound_by_ogg_chunk=sound_by_ogg_chunk,
                hash_by_request=hash_by_request,
                ogg_by_name=ogg_by_name,
            )
            media["mapping_basis"] = mapping_basis
            if kind in HIGH_LEVEL_STRING_SOUND_KINDS:
                media["unresolved_reason"] = high_level_unresolved_reason(media)
            resolved_media = [media]
        else:
            resolved_media = resolve_int_sound_candidates(
                item,
                kind=kind,
                request_by_id=request_by_id,
                request_by_code=request_by_code,
                sound_by_id=sound_by_id,
                sound_by_ogg_chunk=sound_by_ogg_chunk,
                hash_by_request=hash_by_request,
                ogg_by_name=ogg_by_name,
            )

        for media in resolved_media:
            unresolved_reason = media.get("unresolved_reason", "")
            if unresolved_reason:
                unresolved_sound_events.append(
                    {
                        "sequence": len(unresolved_sound_events),
                        "line_number": line_number,
                        "relative_ms": relative_ms,
                        "kind": kind,
                        "code_name": media.get("code_name", ""),
                        "event_code_hex": "",
                        "mapping_basis": media.get("mapping_basis", ""),
                        "unresolved_reason": unresolved_reason,
                        "raw_int_args": raw_int_args,
                        "raw_u64_args": raw_u64_args,
                    }
                )
            sounds.append(
                {
                    "sequence": len(sounds),
                    "line_number": line_number,
                    "relative_ms": relative_ms,
                    "kind": kind,
                    "code_name": media.get("code_name", ""),
                    "request_id": media.get("request_id", ""),
                    "sound_resource_id": media.get("sound_resource_id", ""),
                    "duration_ms": media.get("duration_ms", ""),
                    "ogg_name": media.get("ogg_name", ""),
                    "ogg_path": media.get("ogg_path", ""),
                    "label_text": media.get("label_text", ""),
                    "is_dialogue": media.get("is_dialogue", "no"),
                    "mapping_basis": media.get("mapping_basis", ""),
                    "media_mapping_basis": media.get("media_mapping_basis", ""),
                    "is_actual_play": (
                        "yes" if kind in ACTUAL_PLAY_KINDS else "no"
                    ),
                    "is_high_level_request": (
                        "yes" if kind in HIGH_LEVEL_STRING_SOUND_KINDS else "no"
                    ),
                    "unresolved_reason": unresolved_reason,
                    "raw_int_args": raw_int_args,
                    "raw_u64_args": raw_u64_args,
                }
            )

    actual_play_codes = {
        row["code_name"] for row in sounds if row["kind"] in ACTUAL_PLAY_KINDS
    }
    actual_play_resource_times = [
        (row["sound_resource_id"], row["relative_ms"])
        for row in sounds
        if row["kind"] == "sound_mng_play_bytes" and row.get("sound_resource_id")
    ]

    def duplicates_string_play(row: dict) -> bool:
        if row["kind"] == "sound_mng_play_bytes":
            return False
        resource_id = row.get("sound_resource_id")
        if not resource_id:
            return False
        try:
            row_time = int(row.get("relative_ms", 0))
        except ValueError:
            return False
        for known_resource_id, known_time_value in actual_play_resource_times:
            if known_resource_id != resource_id:
                continue
            try:
                known_time = int(known_time_value)
            except ValueError:
                continue
            if abs(row_time - known_time) <= 5:
                return True
        return False

    sounds = [
        row
        for row in sounds
        if (
            row["kind"] in ACTUAL_PLAY_KINDS
            and not duplicates_string_play(row)
        )
        or row["code_name"] not in actual_play_codes
    ]
    for sequence, row in enumerate(sounds):
        row["sequence"] = sequence

    subtitles: list[dict] = []
    dialogue_sounds = [row for row in sounds if row["is_dialogue"] == "yes"]
    for index, sound in enumerate(dialogue_sounds):
        sound_time = int(sound["relative_ms"])
        duration_ms = int(sound.get("duration_ms") or 2000)
        next_sound_time = (
            int(dialogue_sounds[index + 1]["relative_ms"])
            if index + 1 < len(dialogue_sounds)
            else sound_time + duration_ms + 100
        )
        preceding = [
            row for row in texts if int(row["relative_ms"]) <= sound_time + 100
        ]
        text_row = preceding[-1] if preceding else None
        spanning_rows = [
            row
            for row in texts
            if sound_time + 100 < int(row["relative_ms"])
            <= min(sound_time + duration_ms, next_sound_time - 101)
        ]
        subtitle_parts = []
        if text_row:
            subtitle_parts.append(str(text_row["text"]))
        for spanning_row in spanning_rows:
            text = str(spanning_row["text"])
            if text not in subtitle_parts:
                subtitle_parts.append(text)
        subtitle_text = "\n".join(subtitle_parts) or sound.get(
            "label_text", ""
        ).strip()
        subtitle_start = (
            int(text_row["relative_ms"]) if text_row else max(sound_time - 100, 0)
        )
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
                    "runtime_text_spanning_voice"
                    if spanning_rows
                    else (
                        "runtime_text_before_voice" if text_row else "voice_code_label"
                    )
                ),
            }
        )
    subtitles = merge_adjacent_subtitles(subtitles)

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
        "mapping_basis",
        "media_mapping_basis",
        "is_actual_play",
        "is_high_level_request",
        "unresolved_reason",
        "raw_int_args",
        "raw_u64_args",
    ]
    unresolved_sound_event_fields = [
        "sequence",
        "line_number",
        "relative_ms",
        "kind",
        "code_name",
        "event_code_hex",
        "mapping_basis",
        "unresolved_reason",
        "raw_int_args",
        "raw_u64_args",
    ]
    ignored_sound_event_fields = [
        "sequence",
        "line_number",
        "relative_ms",
        "kind",
        "code_name",
        "event_code_hex",
        "mapping_basis",
        "ignored_reason",
        "raw_int_args",
        "raw_u64_args",
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
    write_csv(
        out_dir / "unresolved_sound_events.csv",
        unresolved_sound_events,
        unresolved_sound_event_fields,
    )
    write_csv(
        out_dir / "ignored_sound_events.csv",
        ignored_sound_events,
        ignored_sound_event_fields,
    )
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
        "actual_play_sound_count": sum(
            1 for row in sounds if row.get("is_actual_play") == "yes"
        ),
        "high_level_sound_request_count": sum(
            1 for row in sounds if row.get("is_high_level_request") == "yes"
        ),
        "unresolved_sound_event_count": len(unresolved_sound_events),
        "ignored_sound_event_count": len(ignored_sound_events),
        "runtime_text_count": len(texts),
        "subtitle_count": len(subtitles),
        "video_assets": dgms,
        "sound_assets": sounds,
        "unresolved_sound_events": unresolved_sound_events,
        "ignored_sound_events": ignored_sound_events,
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
            "actual_play_sounds": manifest["actual_play_sound_count"],
            "high_level_sound_requests": manifest["high_level_sound_request_count"],
            "unresolved_sound_events": manifest["unresolved_sound_event_count"],
            "ignored_sound_events": manifest["ignored_sound_event_count"],
            "subtitles": len(subtitles),
            "out_dir": str(out_dir),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
