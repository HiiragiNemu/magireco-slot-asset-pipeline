#!/usr/bin/env python3
"""Promote the owner-approved ac0908 routes and showcase to a 21-MP4 release.

The release is deliberately narrow:

* the 18 existing row-52--57 route editions are hard-linked byte-for-byte;
* the approved showcase ZH MP4 is hard-linked byte-for-byte;
* showcase ``none`` and ``ja`` are built from the exact approved presentation
  timeline, clean visuals, and encoded-once AAC master;
* Japanese cues are sliced from the corresponding v27 route JA SRT using that
  route's event presentation interval;
* the showcase remains an edited cross-route product, never a native-session
  claim.

All input media and attestations are SHA-256 bound.  The destination is created
through a sibling staging directory and is rejected if it already exists.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_audio_base_masters as audio_gate
    from .build_ac0908_reference_showcase import (
        FPS,
        HEIGHT,
        SAMPLE_RATE,
        SAMPLES_PER_FRAME,
        WIDTH,
        milliseconds_for_samples,
        read_json,
        relative_output_path,
        validate_bound_file,
        validate_output_media,
        validate_plan as validate_showcase_plan,
        validate_video_grid,
    )
    from .build_independent_scene_release import (
        file_sha256,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        write_json,
        write_srt,
    )
except ImportError:  # direct script execution
    import build_audio_base_masters as audio_gate  # type: ignore
    from build_ac0908_reference_showcase import (  # type: ignore
        FPS,
        HEIGHT,
        SAMPLE_RATE,
        SAMPLES_PER_FRAME,
        WIDTH,
        milliseconds_for_samples,
        read_json,
        relative_output_path,
        validate_bound_file,
        validate_output_media,
        validate_plan as validate_showcase_plan,
        validate_video_grid,
    )
    from build_independent_scene_release import (  # type: ignore
        file_sha256,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        write_json,
        write_srt,
    )


PLAN_SCHEMA = "magireco-ac0908-approved-production-plan-v1"
MANIFEST_SCHEMA = "magireco-ac0908-approved-production-manifest-v1"
QA_SCHEMA = "magireco-ac0908-approved-production-qa-v1"
STATUS = "OWNER_APPROVED_FULL_PRODUCTION_READY"
EDITIONS = ("none", "ja", "zh")
ROUTE_ROWS = tuple(range(52, 58))
SHOWCASE_FRAMES = 2745
SHOWCASE_SAMPLES = SHOWCASE_FRAMES * SAMPLES_PER_FRAME
SHOWCASE_ZH_NAME = "ac0908 六种菜品入口补全参考合集__zh.mp4"
SHOWCASE_JA_NAME = "ac0908 六种菜品入口补全参考合集__ja.mp4"
SHOWCASE_NONE_NAME = "ac0908 六种菜品入口补全参考合集__none.mp4"


def _valid_sha256(value: object) -> str:
    text = str(value).strip().upper()
    if len(text) != 64 or any(character not in "0123456789ABCDEF" for character in text):
        raise ValueError(f"invalid SHA-256: {value!r}")
    return text


def _bound_media(
    row: Mapping[str, Any],
    *,
    label: str,
    plan_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    if set(row) != {"path", "sha256", "bytes"}:
        raise ValueError(f"{label} must contain path, sha256, and bytes")
    path, snapshot = validate_bound_file(
        {"path": row["path"], "sha256": row["sha256"]},
        label=label,
        plan_dir=plan_dir,
    )
    expected_bytes = int(row["bytes"])
    if expected_bytes <= 0 or path.stat().st_size != expected_bytes:
        raise ValueError(f"{label} byte count differs")
    return path, {**snapshot, "byte_count": expected_bytes}


def _validate_owner_authorization(
    path: Path,
    *,
    expected_showcase_sha256: str,
    expected_showcase_bytes: int,
) -> dict[str, Any]:
    value = read_json(path)
    if (
        value.get("schema")
        != "magireco-owner-playback-production-authorization-v1"
        or value.get("status")
        != "owner_playback_approved_and_full_production_authorized"
    ):
        raise ValueError("owner full-production authorization identity differs")
    authorization = value.get("production_authorization")
    if (
        not isinstance(authorization, Mapping)
        or authorization.get("audio_profile") != "no_bgm"
        or tuple(authorization.get("editions", [])) != EDITIONS
        or not str(authorization.get("ac0908", "")).strip()
    ):
        raise ValueError("owner ac0908 production authorization differs")
    matches = [
        row
        for row in value.get("approved_review_media", [])
        if isinstance(row, Mapping)
        and row.get("family") == "ac0908"
        and row.get("filename") == SHOWCASE_ZH_NAME
    ]
    if len(matches) != 1:
        raise ValueError("owner authorization lacks one approved ac0908 showcase")
    approved = matches[0]
    if (
        _valid_sha256(approved.get("sha256"))
        != expected_showcase_sha256
        or int(approved.get("bytes", -1)) != expected_showcase_bytes
    ):
        raise ValueError("owner-approved ac0908 showcase identity differs")
    boundaries = value.get("non_expansion_boundaries")
    if not isinstance(boundaries, list) or not any(
        "native gameplay session" in str(row) for row in boundaries
    ):
        raise ValueError("owner authorization lacks cross-route session boundary")
    return value


def _validate_route_playback_attestation(
    path: Path,
    *,
    expected_zh_by_row: Mapping[int, str],
) -> dict[str, Any]:
    value = read_json(path)
    if (
        value.get("schema") != "magireco-owner-human-playback-approvals-v1"
        or value.get("status") != "project_owner_playback_approved"
    ):
        raise ValueError("route playback attestation identity differs")
    observed: dict[int, str] = {}
    for row in value.get("files", []):
        if not isinstance(row, Mapping) or row.get("edition") != "zh":
            continue
        part = str(row.get("part", ""))
        if not part.startswith("ac0908 route "):
            continue
        route_row = int(part.rsplit(" ", 1)[-1])
        if route_row in observed:
            raise ValueError("duplicate ac0908 route approval")
        observed[route_row] = _valid_sha256(row.get("sha256"))
    if observed != dict(expected_zh_by_row):
        raise ValueError("approved ac0908 route ZH hash set differs")
    scope_note = str(value.get("ac0908_scope_note", ""))
    if "does not make" not in scope_note or "one native session" not in scope_note:
        raise ValueError("route playback attestation lacks session-scope boundary")
    return value


def _timeline_by_event(
    family_manifest: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for raw in family_manifest.get("timeline", []):
        if not isinstance(raw, Mapping):
            raise ValueError("route family timeline contains a non-object")
        event = str(raw.get("event", ""))
        if not event or event in output:
            raise ValueError("route family timeline event identity is not unique")
        output[event] = dict(raw)
    return output


def extract_event_local_cues(
    cues: Sequence[Mapping[str, Any]],
    *,
    timeline_row: Mapping[str, Any],
    event: str,
) -> list[dict[str, Any]]:
    """Slice one event's cues from a route SRT and return event-local times."""

    if timeline_row.get("event") != event:
        raise ValueError("subtitle timeline row event differs")
    start_ms = milliseconds_for_samples(int(timeline_row["start_sample"]))
    end_ms = milliseconds_for_samples(int(timeline_row["end_sample"]))
    if end_ms <= start_ms:
        raise ValueError("subtitle timeline interval is empty")
    local: list[dict[str, Any]] = []
    for cue in cues:
        cue_start = int(cue["start_ms"])
        cue_end = int(cue["end_ms"])
        if start_ms <= cue_start < end_ms:
            if cue_end > end_ms or cue_end <= cue_start:
                raise ValueError(f"{event} JA subtitle crosses its event interval")
            local.append(
                {
                    "start_ms": cue_start - start_ms,
                    "end_ms": cue_end - start_ms,
                    "text": str(cue["text"]),
                }
            )
    return local


def _validate_route(
    raw: Mapping[str, Any],
    *,
    plan_dir: Path,
    ffprobe: str,
) -> dict[str, Any]:
    route_row = int(raw.get("dirinfo_row", -1))
    if route_row not in ROUTE_ROWS:
        raise ValueError("ac0908 route row is outside 52 through 57")
    expected_order = [
        "ac0908_009",
        f"ac0908_{route_row - 50:03d}",
        "ac0908_008",
    ]
    if raw.get("route_order") != expected_order:
        raise ValueError(f"ac0908 route {route_row} order differs")
    family_path, family_snapshot = validate_bound_file(
        raw["family_manifest"],
        label=f"ac0908 route {route_row} family manifest",
        plan_dir=plan_dir,
    )
    qa_path, qa_snapshot = validate_bound_file(
        raw["automated_qa"],
        label=f"ac0908 route {route_row} automated QA",
        plan_dir=plan_dir,
    )
    ja_srt_path, ja_srt_snapshot = validate_bound_file(
        raw["ja_srt"],
        label=f"ac0908 route {route_row} JA SRT",
        plan_dir=plan_dir,
    )
    family = read_json(family_path)
    qa = read_json(qa_path)
    timeline = _timeline_by_event(family)
    if (
        family.get("schema") != "magireco-no-bgm-story-family-editions-v1"
        or family.get("family") != "ac0908"
        or tuple(family.get("selected_editions", [])) != EDITIONS
        or list(timeline) != expected_order
    ):
        raise ValueError(f"ac0908 route {route_row} family identity differs")
    if (
        qa.get("schema") != "magireco-no-bgm-story-family-editions-qa-v1"
        or qa.get("status") != "passed"
        or qa.get("events") != expected_order
        or not qa.get("checks", {}).get("aac_encoded_once_and_packet_identical")
        or not qa.get("checks", {}).get("selected_srt_files_round_trip")
    ):
        raise ValueError(f"ac0908 route {route_row} QA contract differs")
    total_frames = int(qa.get("total_frames", -1))
    total_samples = int(qa.get("total_presentation_samples", -1))
    if total_frames <= 0 or total_samples != total_frames * SAMPLES_PER_FRAME:
        raise ValueError(f"ac0908 route {route_row} frame/sample grid differs")
    if int(timeline[expected_order[-1]]["end_frame"]) != total_frames:
        raise ValueError(f"ac0908 route {route_row} timeline endpoint differs")

    parsed_ja = parse_srt(ja_srt_path)
    if len(parsed_ja) != 6:
        raise ValueError(f"ac0908 route {route_row} JA cue count differs")
    outputs_raw = raw.get("outputs")
    if not isinstance(outputs_raw, Mapping) or set(outputs_raw) != set(EDITIONS):
        raise ValueError(f"ac0908 route {route_row} output edition set differs")
    outputs: dict[str, dict[str, Any]] = {}
    snapshots = [family_snapshot, qa_snapshot, ja_srt_snapshot]
    for edition in EDITIONS:
        path, snapshot = _bound_media(
            outputs_raw[edition],
            label=f"ac0908 route {route_row} {edition} MP4",
            plan_dir=plan_dir,
        )
        validate_output_media(path, expected_frames=total_frames, ffprobe=ffprobe)
        outputs[edition] = {
            "path": path,
            "sha256": snapshot["sha256"],
            "byte_count": snapshot["byte_count"],
        }
        snapshots.append(snapshot)
    return {
        "dirinfo_row": route_row,
        "label": str(raw.get("label", "")),
        "route_order": expected_order,
        "family_manifest": family,
        "qa": qa,
        "timeline": timeline,
        "ja_cues": parsed_ja,
        "outputs": outputs,
        "total_frames": total_frames,
        "total_samples": total_samples,
        "source_snapshots": snapshots,
    }


def compose_showcase_ja_cues(
    *,
    occurrences: Sequence[Mapping[str, Any]],
    routes: Mapping[int, Mapping[str, Any]],
    subtitle_bindings: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compose approved showcase JA cues from occurrence-specific route SRTs."""

    binding_by_id: dict[str, Mapping[str, Any]] = {}
    for row in subtitle_bindings:
        occurrence_id = str(row.get("occurrence_id", ""))
        if not occurrence_id or occurrence_id in binding_by_id:
            raise ValueError("showcase JA occurrence binding identity differs")
        binding_by_id[occurrence_id] = row
    expected_ids = {
        str(row["id"])
        for row in occurrences
        if str(row["event"]) != "ac0908_001"
    }
    if set(binding_by_id) != expected_ids:
        raise ValueError("showcase JA occurrence binding set differs")

    output: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    start_frame = 0
    for occurrence in occurrences:
        occurrence_id = str(occurrence["id"])
        event = str(occurrence["event"])
        frame_count_value = int(occurrence["frame_count"])
        if event != "ac0908_001":
            binding = binding_by_id[occurrence_id]
            route_row = int(binding.get("dirinfo_row", -1))
            if binding.get("event") != event or route_row not in routes:
                raise ValueError(f"{occurrence_id} JA route binding differs")
            route = routes[route_row]
            if event not in route["timeline"]:
                raise ValueError(f"{occurrence_id} event is absent from bound route")
            local = extract_event_local_cues(
                route["ja_cues"],
                timeline_row=route["timeline"][event],
                event=event,
            )
            expected_cues = int(binding.get("expected_cues", -1))
            if len(local) != expected_cues:
                raise ValueError(f"{occurrence_id} JA cue count differs")
            offset_ms = milliseconds_for_samples(start_frame * SAMPLES_PER_FRAME)
            for cue in local:
                output.append(
                    {
                        "start_ms": offset_ms + int(cue["start_ms"]),
                        "end_ms": offset_ms + int(cue["end_ms"]),
                        "text": str(cue["text"]),
                    }
                )
            provenance.append(
                {
                    "occurrence_id": occurrence_id,
                    "event": event,
                    "dirinfo_row": route_row,
                    "cue_count": len(local),
                }
            )
        start_frame += frame_count_value
    if start_frame != SHOWCASE_FRAMES:
        raise ValueError("showcase occurrence frame total differs")
    if len(output) != 15:
        raise ValueError("showcase JA total cue count differs")
    return output, provenance


def _validate_showcase(
    plan: Mapping[str, Any],
    *,
    plan_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    showcase_plan_path, showcase_plan_snapshot = validate_bound_file(
        plan["showcase_plan"],
        label="approved ac0908 showcase plan",
        plan_dir=plan_dir,
    )
    resolved = validate_showcase_plan(
        read_json(showcase_plan_path),
        plan_path=showcase_plan_path,
        ffprobe=ffprobe,
    )
    approved = plan.get("approved_showcase")
    if not isinstance(approved, Mapping):
        raise ValueError("approved_showcase binding is missing")
    manifest_path, manifest_snapshot = validate_bound_file(
        approved["manifest"],
        label="approved ac0908 showcase manifest",
        plan_dir=plan_dir,
    )
    qa_path, qa_snapshot = validate_bound_file(
        approved["automated_qa"],
        label="approved ac0908 showcase automated QA",
        plan_dir=plan_dir,
    )
    audio_path, audio_snapshot = _bound_media(
        approved["audio_master"],
        label="approved ac0908 showcase AAC master",
        plan_dir=plan_dir,
    )
    zh_path, zh_snapshot = _bound_media(
        approved["zh_output"],
        label="owner-approved ac0908 showcase ZH MP4",
        plan_dir=plan_dir,
    )
    zh_srt_path, zh_srt_snapshot = _bound_media(
        approved["zh_srt"],
        label="owner-approved ac0908 showcase ZH SRT",
        plan_dir=plan_dir,
    )
    manifest = read_json(manifest_path)
    qa = read_json(qa_path)
    if (
        manifest.get("schema")
        != "magireco-ac0908-reference-showcase-manifest-v1"
        or manifest.get("session_claim")
        != "edited_cross_route_showcase_not_one_native_session"
        or manifest.get("media", {}).get("frame_count") != SHOWCASE_FRAMES
        or manifest.get("media", {}).get("audio_samples") != SHOWCASE_SAMPLES
        or manifest.get("media", {}).get("output", {}).get("sha256")
        != zh_snapshot["sha256"]
    ):
        raise ValueError("approved ac0908 showcase manifest identity differs")
    if (
        qa.get("schema") != "magireco-ac0908-reference-showcase-qa-v1"
        or not qa.get("automated_spec_qa_passed")
        or not qa.get("checks", {}).get("no_external_reference_pixels_or_audio")
        or qa.get("media", {}).get("sha256") != zh_snapshot["sha256"]
    ):
        raise ValueError("approved ac0908 showcase QA identity differs")
    if len(parse_srt(zh_srt_path)) != 15:
        raise ValueError("approved ac0908 showcase ZH SRT cue count differs")
    validate_output_media(zh_path, expected_frames=SHOWCASE_FRAMES, ffprobe=ffprobe)

    audio_probe = probe(audio_path, ffprobe)
    audio_streams = media_streams(audio_probe, "audio")
    if (
        media_streams(audio_probe, "video")
        or media_streams(audio_probe, "subtitle")
        or len(audio_streams) != 1
        or audio_streams[0].get("codec_name") != "aac"
        or int(audio_streams[0].get("sample_rate", 0)) != SAMPLE_RATE
        or int(audio_streams[0].get("channels", 0)) != 2
    ):
        raise ValueError("approved ac0908 showcase AAC master contract differs")
    master_timeline = audio_gate._audio_packet_timeline(
        output=audio_path,
        audio_stream=audio_streams[0],
        expected_samples=SHOWCASE_SAMPLES,
        ffprobe=ffprobe,
    )
    master_pcm = audio_gate._effective_decoded_pcm_audit(
        output=audio_path,
        expected_samples=SHOWCASE_SAMPLES,
        ffmpeg=ffmpeg,
    )
    master_packet = packet_hash(audio_path, kind="audio", ffmpeg=ffmpeg)

    entries_raw = approved.get("entry_visuals")
    if not isinstance(entries_raw, Mapping):
        raise ValueError("approved showcase entry visual bindings are missing")
    expected_entries = {
        str(row["id"]): int(row["frame_count"])
        for row in resolved["occurrences"]
        if row["event"] == "ac0908_001"
    }
    if set(entries_raw) != set(expected_entries):
        raise ValueError("approved showcase entry visual set differs")
    entry_visuals: dict[str, Path] = {}
    entry_snapshots: list[dict[str, Any]] = []
    for occurrence_id, expected_frames in expected_entries.items():
        raw = entries_raw[occurrence_id]
        path, snapshot = _bound_media(
            raw,
            label=f"approved showcase entry visual {occurrence_id}",
            plan_dir=plan_dir,
        )
        validate_video_grid(
            path,
            expected_frames=expected_frames,
            ffprobe=ffprobe,
            label=f"approved showcase entry visual {occurrence_id}",
        )
        declared = manifest.get("entry_visual_audits", {}).get(occurrence_id)
        if not isinstance(declared, Mapping) or declared.get("sha256") != snapshot["sha256"]:
            raise ValueError(f"{occurrence_id} entry visual differs from v28 manifest")
        entry_visuals[occurrence_id] = path
        entry_snapshots.append(snapshot)
    return {
        "resolved_plan": resolved,
        "manifest": manifest,
        "qa": qa,
        "audio_master": audio_path,
        "master_timeline": master_timeline,
        "master_pcm": master_pcm,
        "master_packet_sha256": master_packet,
        "zh_output": zh_path,
        "zh_output_sha256": zh_snapshot["sha256"],
        "zh_output_bytes": zh_snapshot["byte_count"],
        "zh_srt": zh_srt_path,
        "entry_visuals": entry_visuals,
        "source_snapshots": [
            showcase_plan_snapshot,
            manifest_snapshot,
            qa_snapshot,
            audio_snapshot,
            zh_snapshot,
            zh_srt_snapshot,
            *entry_snapshots,
            *resolved["source_snapshots"],
        ],
    }


def validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "owner_approved_full_production"
        or plan.get("series") != "ac0908"
        or tuple(plan.get("editions", [])) != EDITIONS
        or plan.get("session_claim")
        != "six_native_dirinfo_routes_plus_one_edited_cross_route_showcase"
    ):
        raise ValueError("ac0908 approved production plan identity differs")
    native = plan.get("native_media")
    if not isinstance(native, Mapping) or (
        int(native.get("width", -1)),
        int(native.get("height", -1)),
        str(native.get("frame_rate", "")),
        bool(native.get("upscale", True)),
    ) != (WIDTH, HEIGHT, "30/1", False):
        raise ValueError("ac0908 approved production native media differs")
    if int(plan.get("expected_mp4_count", -1)) != 21:
        raise ValueError("ac0908 approved production output count differs")

    plan_dir = plan_path.parent
    showcase = _validate_showcase(
        plan,
        plan_dir=plan_dir,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    owner_path, owner_snapshot = validate_bound_file(
        plan["owner_authorization"],
        label="owner ac0908 full-production authorization",
        plan_dir=plan_dir,
    )
    route_attestation_path, route_attestation_snapshot = validate_bound_file(
        plan["route_playback_attestation"],
        label="owner ac0908 route playback attestation",
        plan_dir=plan_dir,
    )
    _validate_owner_authorization(
        owner_path,
        expected_showcase_sha256=showcase["zh_output_sha256"],
        expected_showcase_bytes=showcase["zh_output_bytes"],
    )

    routes_raw = plan.get("routes")
    if not isinstance(routes_raw, list) or len(routes_raw) != len(ROUTE_ROWS):
        raise ValueError("exactly six ac0908 route bindings are required")
    routes: dict[int, dict[str, Any]] = {}
    snapshots: list[dict[str, Any]] = [
        owner_snapshot,
        route_attestation_snapshot,
        *showcase["source_snapshots"],
    ]
    for raw in routes_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("ac0908 route binding must be an object")
        route = _validate_route(raw, plan_dir=plan_dir, ffprobe=ffprobe)
        route_row = route["dirinfo_row"]
        if route_row in routes:
            raise ValueError("duplicate ac0908 route row")
        routes[route_row] = route
        snapshots.extend(route["source_snapshots"])
    if set(routes) != set(ROUTE_ROWS):
        raise ValueError("ac0908 route row set differs")
    _validate_route_playback_attestation(
        route_attestation_path,
        expected_zh_by_row={
            row: routes[row]["outputs"]["zh"]["sha256"] for row in ROUTE_ROWS
        },
    )

    ja_cues, ja_provenance = compose_showcase_ja_cues(
        occurrences=showcase["resolved_plan"]["occurrences"],
        routes=routes,
        subtitle_bindings=plan.get("showcase_ja_subtitle_occurrences", []),
    )
    unique_snapshots: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for snapshot in snapshots:
        key = (str(snapshot["path"]), str(snapshot["sha256"]))
        if key not in seen:
            seen.add(key)
            unique_snapshots.append(dict(snapshot))
    return {
        "release_id": str(plan.get("release_id", "")),
        "routes": routes,
        "showcase": showcase,
        "showcase_ja_cues": ja_cues,
        "showcase_ja_provenance": ja_provenance,
        "source_snapshots": unique_snapshots,
    }


def assert_relative_output(path: str) -> str:
    value = Path(path)
    if value.is_absolute() or ".." in value.parts or not value.parts:
        raise ValueError(f"output path must be a safe relative path: {path!r}")
    return value.as_posix()


def hardlink_exact(
    source: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_bytes: int,
    staging: Path,
) -> dict[str, Any]:
    """Create and verify an exact same-volume hard link."""

    expected_sha256 = _valid_sha256(expected_sha256)
    if not source.is_file() or source.stat().st_size != expected_bytes:
        raise ValueError(f"hardlink source identity differs: {source}")
    if file_sha256(source) != expected_sha256:
        raise ValueError(f"hardlink source SHA-256 differs: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"hardlink destination already exists: {destination}")
    os.link(source, destination)
    if not os.path.samefile(source, destination):
        raise RuntimeError(f"promoted file is not a hard link: {destination}")
    if (
        destination.stat().st_size != expected_bytes
        or file_sha256(destination) != expected_sha256
    ):
        raise RuntimeError(f"promoted hardlink identity differs: {destination}")
    return {
        "path": assert_relative_output(relative_output_path(destination, staging=staging)),
        "sha256": expected_sha256,
        "byte_count": expected_bytes,
        "promotion": "exact_hardlink",
        "source_path": str(source),
        "same_file_identity_verified": True,
    }


def _write_srt_round_trip(
    path: Path,
    cues: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> None:
    write_srt(path, cues)
    expected = [
        {
            "start_ms": int(row["start_ms"]),
            "end_ms": int(row["end_ms"]),
            "text": str(row["text"]),
        }
        for row in cues
    ]
    if parse_srt(path) != expected:
        raise RuntimeError(f"{label} SRT round-trip differs")


def _audio_audit(
    path: Path,
    *,
    expected_frames: int,
    expected_samples: int,
    staging: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    media = validate_output_media(path, expected_frames=expected_frames, ffprobe=ffprobe)
    media["path"] = assert_relative_output(relative_output_path(path, staging=staging))
    value = probe(path, ffprobe)
    audios = media_streams(value, "audio")
    if len(audios) != 1:
        raise RuntimeError(f"one audio stream required: {path}")
    timeline = audio_gate._audio_packet_timeline(
        output=path,
        audio_stream=audios[0],
        expected_samples=expected_samples,
        ffprobe=ffprobe,
    )
    pcm = audio_gate._effective_decoded_pcm_audit(
        output=path,
        expected_samples=expected_samples,
        ffmpeg=ffmpeg,
    )
    media["audio_packet_sha256"] = packet_hash(path, kind="audio", ffmpeg=ffmpeg)
    media["audio_timeline_sha256"] = timeline["timeline_sha256"]
    media["decoded_pcm_sha256"] = pcm["pcm_sha256"]
    return media, timeline, pcm


def _build_showcase_clean_visual(
    *,
    output: Path,
    resolved: Mapping[str, Any],
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    showcase = resolved["showcase"]
    base = showcase["resolved_plan"]
    visual_inputs: list[Path] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, occurrence in enumerate(base["occurrences"]):
        if occurrence["event"] == "ac0908_001":
            visual = showcase["entry_visuals"][occurrence["id"]]
        else:
            visual = base["events"][occurrence["event"]]["clean_visual"]
        visual_inputs.append(visual)
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={occurrence['frame_count']},"
            f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=1:a=0,format=yuv420p[outv]"
    )
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for visual in visual_inputs:
        command.extend(["-i", str(visual)])
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(SHOWCASE_FRAMES),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run(command)
    return validate_video_grid(
        output,
        expected_frames=SHOWCASE_FRAMES,
        ffprobe=ffprobe,
        label="approved showcase clean visual master",
    )


def _render_showcase_siblings(
    *,
    staging: Path,
    resolved: Mapping[str, Any],
    video_dir: Path,
    subtitle_dir: Path,
    work_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    showcase = resolved["showcase"]
    clean_visual = work_dir / "ac0908_showcase_clean_visual_master.mp4"
    clean_audit = _build_showcase_clean_visual(
        output=clean_visual,
        resolved=resolved,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    ja_srt = subtitle_dir / "ac0908 六种菜品入口补全参考合集__ja.srt"
    _write_srt_round_trip(
        ja_srt,
        resolved["showcase_ja_cues"],
        label="ac0908 showcase JA",
    )
    zh_srt = subtitle_dir / "ac0908 六种菜品入口补全参考合集__zh.srt"
    zh_srt_link = hardlink_exact(
        showcase["zh_srt"],
        zh_srt,
        expected_sha256=file_sha256(showcase["zh_srt"]),
        expected_bytes=showcase["zh_srt"].stat().st_size,
        staging=staging,
    )
    if len(parse_srt(zh_srt)) != 15:
        raise RuntimeError("promoted showcase ZH SRT cue count differs")

    none_output = video_dir / SHOWCASE_NONE_NAME
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(clean_visual),
            "-i",
            str(showcase["audio_master"]),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(none_output),
        ]
    )

    staged_font_dir = work_dir / "fonts"
    staged_font_dir.mkdir()
    staged_font = staged_font_dir / showcase["resolved_plan"]["font_path"].name
    shutil.copy2(showcase["resolved_plan"]["font_path"], staged_font)
    ja_output = video_dir / SHOWCASE_JA_NAME
    subtitle_value = subtitle_filter(
        showcase["resolved_plan"]["layout"],
        srt_path=ja_srt.relative_to(staging).as_posix(),
        fonts_dir=staged_font_dir.relative_to(staging).as_posix(),
    )
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(clean_visual),
            "-i",
            str(showcase["audio_master"]),
            "-filter_complex",
            f"[0:v:0]{subtitle_value}[outv]",
            "-map",
            "[outv]",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-frames:v",
            str(SHOWCASE_FRAMES),
            "-movflags",
            "+faststart",
            str(ja_output),
        ],
        cwd=staging,
    )
    zh_output = video_dir / SHOWCASE_ZH_NAME
    zh_link = hardlink_exact(
        showcase["zh_output"],
        zh_output,
        expected_sha256=showcase["zh_output_sha256"],
        expected_bytes=showcase["zh_output_bytes"],
        staging=staging,
    )

    audits: dict[str, dict[str, Any]] = {}
    full_audio: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for edition, path in (
        ("none", none_output),
        ("ja", ja_output),
        ("zh", zh_output),
    ):
        media, timeline, pcm = _audio_audit(
            path,
            expected_frames=SHOWCASE_FRAMES,
            expected_samples=SHOWCASE_SAMPLES,
            staging=staging,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )
        audits[edition] = media
        full_audio[edition] = (timeline, pcm)
    if any(
        audits[edition]["audio_packet_sha256"]
        != showcase["master_packet_sha256"]
        or full_audio[edition][0] != showcase["master_timeline"]
        or full_audio[edition][1] != showcase["master_pcm"]
        for edition in EDITIONS
    ):
        raise RuntimeError("showcase sibling audio differs from approved AAC master")
    if audits["zh"]["sha256"] != showcase["zh_output_sha256"]:
        raise RuntimeError("approved showcase ZH SHA-256 changed during promotion")
    if packet_hash(none_output, kind="video", ffmpeg=ffmpeg) != packet_hash(
        clean_visual, kind="video", ffmpeg=ffmpeg
    ):
        raise RuntimeError("showcase none video packets differ from clean master")
    return audits, {
        "clean_visual_audit": clean_audit,
        "ja_srt": {
            "path": assert_relative_output(
                relative_output_path(ja_srt, staging=staging)
            ),
            "sha256": file_sha256(ja_srt),
            "cue_count": len(resolved["showcase_ja_cues"]),
            "round_trip_verified": True,
        },
        "zh_srt": {**zh_srt_link, "cue_count": 15, "round_trip_verified": True},
        "zh_hardlink": zh_link,
    }


def _promote_routes(
    *,
    staging: Path,
    routes: Mapping[int, Mapping[str, Any]],
    video_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    outputs: list[dict[str, Any]] = []
    route_audits: list[dict[str, Any]] = []
    for route_row in ROUTE_ROWS:
        route = routes[route_row]
        sibling_media: dict[str, dict[str, Any]] = {}
        sibling_timeline: dict[str, dict[str, Any]] = {}
        sibling_pcm: dict[str, dict[str, Any]] = {}
        for edition in EDITIONS:
            source = route["outputs"][edition]
            destination = video_dir / source["path"].name
            link = hardlink_exact(
                source["path"],
                destination,
                expected_sha256=source["sha256"],
                expected_bytes=source["byte_count"],
                staging=staging,
            )
            media, timeline, pcm = _audio_audit(
                destination,
                expected_frames=route["total_frames"],
                expected_samples=route["total_samples"],
                staging=staging,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            if media["sha256"] != source["sha256"]:
                raise RuntimeError(f"route {route_row} {edition} hash changed")
            sibling_media[edition] = media
            sibling_timeline[edition] = timeline
            sibling_pcm[edition] = pcm
            outputs.append({**link, "content": f"route_{route_row}", "edition": edition})
        if len({row["audio_packet_sha256"] for row in sibling_media.values()}) != 1:
            raise RuntimeError(f"route {route_row} sibling AAC packets differ")
        if len({row["audio_timeline_sha256"] for row in sibling_media.values()}) != 1:
            raise RuntimeError(f"route {route_row} sibling AAC timelines differ")
        if len({row["decoded_pcm_sha256"] for row in sibling_media.values()}) != 1:
            raise RuntimeError(f"route {route_row} sibling decoded PCM differs")
        declared_packet = _valid_sha256(route["qa"]["audio_master_packet_sha256"])
        if next(iter(sibling_media.values()))["audio_packet_sha256"] != declared_packet:
            raise RuntimeError(f"route {route_row} audio differs from v27 QA master")
        declared_pcm = route["qa"].get("audio_master_decoded_pcm")
        if not isinstance(declared_pcm, Mapping) or any(
            row != declared_pcm for row in sibling_pcm.values()
        ):
            raise RuntimeError(f"route {route_row} decoded PCM differs from v27 QA")
        route_audits.append(
            {
                "dirinfo_row": route_row,
                "label": route["label"],
                "route_order": route["route_order"],
                "frame_count": route["total_frames"],
                "presentation_samples": route["total_samples"],
                "media": sibling_media,
                "audio_packet_sha256": declared_packet,
                "audio_timeline_sha256": next(iter(sibling_media.values()))[
                    "audio_timeline_sha256"
                ],
                "decoded_pcm_sha256": next(iter(sibling_media.values()))[
                    "decoded_pcm_sha256"
                ],
                "exact_hardlinks_verified": True,
            }
        )
    return outputs, route_audits


def build_release(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> Path:
    plan = read_json(plan_path)
    resolved = validate_plan(
        plan,
        plan_path=plan_path,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    release_id = resolved["release_id"]
    if (
        not release_id
        or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
            for character in release_id
        )
    ):
        raise ValueError("unsafe ac0908 approved release_id")
    destination = output_root.resolve()
    if destination.exists():
        raise FileExistsError(f"versioned ac0908 root already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        video_dir = staging / "video"
        subtitle_dir = staging / "subtitles"
        work_dir = staging / "_work"
        for path in (video_dir, subtitle_dir, work_dir):
            path.mkdir()

        route_files, route_audits = _promote_routes(
            staging=staging,
            routes=resolved["routes"],
            video_dir=video_dir,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )
        showcase_media, showcase_aux = _render_showcase_siblings(
            staging=staging,
            resolved=resolved,
            video_dir=video_dir,
            subtitle_dir=subtitle_dir,
            work_dir=work_dir,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
        )
        showcase_files = [
            {
                "path": showcase_media[edition]["path"],
                "sha256": showcase_media[edition]["sha256"],
                "byte_count": showcase_media[edition]["byte_count"],
                "content": "reference_derived_showcase",
                "edition": edition,
                "promotion": (
                    "exact_hardlink" if edition == "zh" else "new_sibling_render"
                ),
            }
            for edition in EDITIONS
        ]
        output_files = [*route_files, *showcase_files]
        if len(output_files) != 21 or len({row["path"] for row in output_files}) != 21:
            raise RuntimeError("ac0908 approved output matrix differs from 21 files")
        actual_mp4 = sorted(video_dir.glob("*.mp4"))
        if len(actual_mp4) != 21:
            raise RuntimeError("ac0908 approved video directory does not contain 21 MP4s")
        declared_by_path = {row["path"]: row for row in output_files}
        for path in actual_mp4:
            relative = assert_relative_output(
                relative_output_path(path, staging=staging)
            )
            declared = declared_by_path.get(relative)
            if (
                declared is None
                or declared["sha256"] != file_sha256(path)
                or int(declared["byte_count"]) != path.stat().st_size
            ):
                raise RuntimeError(f"undeclared or changed output: {path}")

        shutil.rmtree(work_dir)
        manifest_dir = staging / "manifest"
        qa_dir = staging / "qa"
        manifest_dir.mkdir()
        qa_dir.mkdir()
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": STATUS,
            "release_id": release_id,
            "series": "ac0908",
            "audio_profile": "no_bgm",
            "native_media": {
                "width": WIDTH,
                "height": HEIGHT,
                "frame_rate": "30/1",
                "upscale": False,
            },
            "content_product_count": 7,
            "edition_mp4_count": 21,
            "editions": list(EDITIONS),
            "routes": route_audits,
            "showcase": {
                "scope": "reference-derived all-outcomes showcase",
                "session_claim": "edited_cross_route_showcase_not_one_native_session",
                "occurrence_count": 13,
                "unique_event_count": 9,
                "frame_count": SHOWCASE_FRAMES,
                "presentation_samples": SHOWCASE_SAMPLES,
                "media": showcase_media,
                "ja_subtitle_provenance": resolved["showcase_ja_provenance"],
                "subtitles": {
                    "none_cue_count": 0,
                    "ja": showcase_aux["ja_srt"],
                    "zh": showcase_aux["zh_srt"],
                },
                "approved_zh_hardlink": showcase_aux["zh_hardlink"],
            },
            "outputs": sorted(output_files, key=lambda row: row["path"]),
            "source_snapshots": resolved["source_snapshots"],
            "publication_approved": False,
            "upload_performed": False,
        }
        manifest_path = manifest_dir / "AC0908_APPROVED_PRODUCTION_MANIFEST.json"
        write_json(manifest_path, manifest)
        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS,
            "passed": True,
            "checks": {
                "owner_full_production_authorization_hash_bound": True,
                "six_owner_playback_approved_route_timelines_bound": True,
                "approved_showcase_zh_hash_preserved": True,
                "route_mp4_exact_hardlinks": True,
                "route_none_ja_zh_aac_packet_equal": True,
                "route_none_ja_zh_decoded_pcm_equal": True,
                "showcase_none_ja_zh_aac_packet_equal": True,
                "showcase_none_ja_zh_decoded_pcm_equal": True,
                "showcase_ja_sliced_from_occurrence_bound_v27_route_srt": True,
                "showcase_ja_and_zh_srt_round_trip": True,
                "all_output_paths_relative": True,
                "all_outputs_native_416x232_30fps_h264_aac_48khz_stereo": True,
                "exactly_21_mp4_outputs": True,
                "no_upscale": True,
                "no_bgm_intentionally_excluded": True,
                "showcase_declared_non_native_session": True,
            },
            "manifest_sha256": file_sha256(manifest_path),
            "output_sha256": {
                row["path"]: row["sha256"]
                for row in sorted(output_files, key=lambda item: item["path"])
            },
        }
        qa_path = qa_dir / "AUTOMATED_QA.json"
        write_json(qa_path, qa)
        ready = {
            "schema": "magireco-approved-production-ready-v1",
            "status": STATUS,
            "series": "ac0908",
            "content_product_count": 7,
            "edition_mp4_count": 21,
            "manifest": {
                "path": "manifest/AC0908_APPROVED_PRODUCTION_MANIFEST.json",
                "sha256": file_sha256(manifest_path),
            },
            "qa": {
                "path": "qa/AUTOMATED_QA.json",
                "sha256": file_sha256(qa_path),
            },
            "publication_approved": False,
            "upload_performed": False,
        }
        write_json(staging / "READY.json", ready)
        staging.replace(destination)
        return destination
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plan_path = Path(args.plan).resolve()
    plan = read_json(plan_path)
    resolved = validate_plan(
        plan,
        plan_path=plan_path,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    if args.validate_only:
        print(
            json.dumps(
                {
                    "schema": PLAN_SCHEMA,
                    "status": "validated",
                    "release_id": resolved["release_id"],
                    "route_count": len(resolved["routes"]),
                    "showcase_ja_cue_count": len(resolved["showcase_ja_cues"]),
                    "expected_mp4_count": 21,
                    "source_snapshot_count": len(resolved["source_snapshots"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    destination = build_release(
        plan_path=plan_path,
        output_root=Path(args.out_root),
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "status": STATUS,
                "destination": str(destination),
                "edition_mp4_count": 21,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
