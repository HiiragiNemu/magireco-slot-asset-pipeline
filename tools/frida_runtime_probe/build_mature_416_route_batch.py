#!/usr/bin/env python3
"""Build hash-bound mature 416x232 route segments and edited showcases.

The input family masters were already produced from event-exact manifests and
have a cumulative frame/sample timeline.  This builder reuses those masters
without changing event timing:

* DirInfo rows are checked against the hash-bound CSV before rendering.
* Exact audience duplicate substitutions are checked against a hash-bound
  deduplication proposal.
* Each route is rendered independently as none/JA/ZH.
* A separate long product is explicitly labelled an edited route-chapter
  showcase, never a single native session.

One bad route is quarantined in the batch summary and does not stop unrelated
routes or another family.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac0908_reference_showcase import (
        FPS,
        HEIGHT,
        SAMPLE_RATE,
        SAMPLES_PER_FRAME,
        WIDTH,
        assert_srt_round_trip,
        milliseconds_for_samples,
        read_json,
        relative_output_path,
        validate_bound_file,
        validate_output_media,
        validate_video_grid,
    )
    from .build_independent_scene_release import (
        file_sha256,
        frame_count,
        media_streams,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        write_json,
    )
except ImportError:  # direct script execution
    from build_ac0908_reference_showcase import (  # type: ignore
        FPS,
        HEIGHT,
        SAMPLE_RATE,
        SAMPLES_PER_FRAME,
        WIDTH,
        assert_srt_round_trip,
        milliseconds_for_samples,
        read_json,
        relative_output_path,
        validate_bound_file,
        validate_output_media,
        validate_video_grid,
    )
    from build_independent_scene_release import (  # type: ignore
        file_sha256,
        frame_count,
        media_streams,
        parse_srt,
        probe,
        run,
        subtitle_filter,
        write_json,
    )


PLAN_SCHEMA = "magireco-mature-416-route-batch-plan-v1"
MANIFEST_SCHEMA = "magireco-mature-416-route-batch-manifest-v1"
ROUTE_MANIFEST_SCHEMA = "magireco-mature-416-route-manifest-v1"
QA_SCHEMA = "magireco-mature-416-route-batch-qa-v1"
STATUS = "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
SHOWCASE_CLAIM = "edited_route_chapter_showcase_not_single_native_session"
UPLOAD_POLICY = "source_and_uploaded_media_read_only_never_overwrite"
EDITIONS = ("none", "ja", "zh")


def _artifact_path(family_root: Path, row: Mapping[str, Any]) -> Path:
    path = Path(str(row["path"]))
    return path if path.is_absolute() else family_root / path


def _validate_audio_master(path: Path, *, ffprobe: str) -> dict[str, Any]:
    value = probe(path, ffprobe)
    videos = media_streams(value, "video")
    audios = media_streams(value, "audio")
    if videos or len(audios) != 1 or media_streams(value, "subtitle"):
        raise RuntimeError(f"audio master stream contract failed: {path}")
    audio = audios[0]
    if (
        audio.get("codec_name") != "aac"
        or int(audio.get("sample_rate", 0)) != SAMPLE_RATE
        or int(audio.get("channels", 0)) != 2
    ):
        raise RuntimeError(f"audio master native contract failed: {path}")
    return {
        "codec": "aac",
        "sample_rate": SAMPLE_RATE,
        "channels": 2,
        "sha256": file_sha256(path),
    }


def _dirinfo_sequences(path: Path, *, kind: int) -> dict[int, list[str]]:
    grouped: dict[int, list[tuple[int, str]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["kind"]) != kind:
                continue
            grouped.setdefault(int(row["row_index"]), []).append(
                (int(row["selector_raw"]), str(row["scene_name"]))
            )
    return {
        row_index: [event for _, event in sorted(values)]
        for row_index, values in grouped.items()
    }


def duplicate_alias_map(proposal: Mapping[str, Any] | None) -> dict[str, str]:
    aliases: dict[str, str] = {}
    if proposal is None:
        return aliases
    deduplication = proposal.get("deduplication")
    if not isinstance(deduplication, Mapping):
        raise ValueError("deduplication proposal lacks a deduplication object")
    for group in deduplication.get("groups", []):
        if not isinstance(group, Mapping):
            raise ValueError("deduplication group must be an object")
        kept = str(group["kept"])
        for removed in group.get("removed", []):
            removed_name = str(removed)
            if removed_name in aliases:
                raise ValueError(f"duplicate alias appears twice: {removed_name}")
            aliases[removed_name] = kept
    return aliases


def normalize_sequence(
    sequence: Sequence[str], aliases: Mapping[str, str]
) -> list[str]:
    return [aliases.get(str(event), str(event)) for event in sequence]


def route_timeline(
    events: Sequence[str],
    timeline_by_event: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    rows: list[dict[str, Any]] = []
    frame_cursor = 0
    sample_cursor = 0
    for event in events:
        source = timeline_by_event[event]
        frames = int(source["end_frame"]) - int(source["start_frame"])
        samples = int(source["end_sample"]) - int(source["start_sample"])
        if frames <= 0 or samples != frames * SAMPLES_PER_FRAME:
            raise ValueError(f"{event} source timeline is not on the 30fps grid")
        rows.append(
            {
                "event": event,
                "start_frame": frame_cursor,
                "end_frame": frame_cursor + frames,
                "start_sample": sample_cursor,
                "end_sample": sample_cursor + samples,
                "source_start_frame": int(source["start_frame"]),
                "source_end_frame": int(source["end_frame"]),
                "source_start_sample": int(source["start_sample"]),
                "source_end_sample": int(source["end_sample"]),
            }
        )
        frame_cursor += frames
        sample_cursor += samples
    return rows, frame_cursor, sample_cursor


def route_subtitle_cues(
    events: Sequence[str],
    timeline_by_event: Mapping[str, Mapping[str, Any]],
    source_cues: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    destination_sample = 0
    for event in events:
        source = timeline_by_event[event]
        source_start_ms = milliseconds_for_samples(int(source["start_sample"]))
        source_end_ms = milliseconds_for_samples(int(source["end_sample"]))
        event_samples = int(source["end_sample"]) - int(source["start_sample"])
        event_duration_ms = milliseconds_for_samples(event_samples)
        destination_start_ms = milliseconds_for_samples(destination_sample)
        for cue in source_cues:
            cue_start = int(cue["start_ms"])
            if not source_start_ms <= cue_start < source_end_ms:
                continue
            local_start = max(0, cue_start - source_start_ms)
            local_end = min(event_duration_ms, int(cue["end_ms"]) - source_start_ms)
            if local_end <= local_start:
                raise ValueError(f"{event} subtitle cue collapses at its event boundary")
            output.append(
                {
                    "start_ms": destination_start_ms + local_start,
                    "end_ms": destination_start_ms + local_end,
                    "text": str(cue["text"]),
                    "event": event,
                }
            )
        destination_sample += event_samples
    return output


def _validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "mature_route_batch_approved_for_render"
        or plan.get("composition_claim") != SHOWCASE_CLAIM
        or plan.get("uploaded_media_policy") != UPLOAD_POLICY
    ):
        raise ValueError("unsupported mature 416 route batch plan")
    family = str(plan.get("family", ""))
    if not family.startswith("ac") or not family[2:].isdigit():
        raise ValueError("unsafe family name")
    if plan.get("native_dimensions") != {"width": WIDTH, "height": HEIGHT}:
        raise ValueError("plan is not native 416x232")
    if plan.get("native_frame_rate") != "30/1":
        raise ValueError("plan is not 30fps")

    plan_dir = plan_path.parent
    snapshots: list[dict[str, str]] = []
    bound: dict[str, Path] = {}
    for key, label in (
        ("dirinfo", "DirInfo route evidence"),
        ("family_manifest", f"{family} source family manifest"),
        ("clean_visual_master", f"{family} clean visual master"),
        ("no_bgm_audio_master", f"{family} no-BGM audio master"),
        ("subtitles_ja", f"{family} Japanese subtitles"),
        ("subtitles_zh", f"{family} Chinese subtitles"),
        ("subtitle_layout", "416x232 subtitle layout"),
        ("font", "audited subtitle font"),
    ):
        path, snapshot = validate_bound_file(
            plan[key], label=label, plan_dir=plan_dir
        )
        bound[key] = path
        snapshots.append(snapshot)

    proposal: dict[str, Any] | None = None
    if "deduplication_proposal" in plan:
        path, snapshot = validate_bound_file(
            plan["deduplication_proposal"],
            label=f"{family} exact audience duplicate proposal",
            plan_dir=plan_dir,
        )
        bound["deduplication_proposal"] = path
        snapshots.append(snapshot)
        proposal = read_json(path)
        if proposal.get("series") != family:
            raise ValueError("deduplication proposal family differs")
    aliases = duplicate_alias_map(proposal)

    family_manifest = read_json(bound["family_manifest"])
    if (
        family_manifest.get("schema")
        != "magireco-no-bgm-story-family-editions-v1"
        or family_manifest.get("family") != family
        or family_manifest.get("media", {}).get("width") != WIDTH
        or family_manifest.get("media", {}).get("height") != HEIGHT
        or family_manifest.get("media", {}).get("frame_rate") != "30/1"
    ):
        raise ValueError(f"{family} source family manifest identity differs")
    family_root = bound["family_manifest"].parent.parent
    artifacts = family_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise ValueError("source family manifest lacks artifacts")
    for key, artifact_key in (
        ("clean_visual_master", "clean_visual_master"),
        ("no_bgm_audio_master", "no_bgm_audio_master"),
        ("subtitles_ja", "subtitles_ja"),
        ("subtitles_zh", "subtitles_zh"),
    ):
        artifact = artifacts.get(artifact_key)
        if not isinstance(artifact, Mapping):
            raise ValueError(f"source family artifact is missing: {artifact_key}")
        if (
            _artifact_path(family_root, artifact).resolve() != bound[key]
            or str(artifact["sha256"]).upper() != file_sha256(bound[key])
        ):
            raise ValueError(f"plan binding differs from family artifact: {key}")

    timeline_values = family_manifest.get("timeline")
    if not isinstance(timeline_values, list) or not timeline_values:
        raise ValueError("source family timeline is empty")
    timeline_by_event: dict[str, Mapping[str, Any]] = {}
    previous_frame = previous_sample = 0
    for row in timeline_values:
        if not isinstance(row, Mapping):
            raise ValueError("source family timeline row is invalid")
        event = str(row["event"])
        if event in timeline_by_event:
            raise ValueError(f"duplicate source family timeline event: {event}")
        if (
            int(row["start_frame"]) != previous_frame
            or int(row["start_sample"]) != previous_sample
        ):
            raise ValueError("source family timeline is not cumulative")
        frames = int(row["end_frame"]) - previous_frame
        samples = int(row["end_sample"]) - previous_sample
        if frames <= 0 or samples != frames * SAMPLES_PER_FRAME:
            raise ValueError(f"{event} source family timeline grid differs")
        timeline_by_event[event] = row
        previous_frame = int(row["end_frame"])
        previous_sample = int(row["end_sample"])

    validate_video_grid(
        bound["clean_visual_master"],
        expected_frames=previous_frame,
        ffprobe=ffprobe,
        label=f"{family} clean visual master",
    )
    _validate_audio_master(bound["no_bgm_audio_master"], ffprobe=ffprobe)

    dirinfo_kind = int(plan["dirinfo_kind"])
    source_routes = _dirinfo_sequences(bound["dirinfo"], kind=dirinfo_kind)
    routes_raw = plan.get("routes")
    if not isinstance(routes_raw, list) or not routes_raw:
        raise ValueError("route plan is empty")
    routes: list[dict[str, Any]] = []
    route_ids: set[str] = set()
    normalized_sequences: set[tuple[str, ...]] = set()
    used_source_rows: set[int] = set()
    for raw in routes_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("route plan row must be an object")
        route_id = str(raw["route_id"])
        if (
            not route_id
            or route_id in route_ids
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
                for character in route_id
            )
        ):
            raise ValueError(f"unsafe or duplicate route id: {route_id}")
        route_ids.add(route_id)
        render_sequence = [str(value) for value in raw["render_event_sequence"]]
        if not render_sequence or any(
            event not in timeline_by_event for event in render_sequence
        ):
            raise ValueError(f"{route_id} render sequence is unresolved")
        sources = raw.get("source_rows")
        if not isinstance(sources, list) or not sources:
            raise ValueError(f"{route_id} has no DirInfo source rows")
        checked_rows = []
        for source in sources:
            if not isinstance(source, Mapping):
                raise ValueError(f"{route_id} source row is invalid")
            row_index = int(source["row_index"])
            expected_raw = [str(value) for value in source["raw_event_sequence"]]
            if source_routes.get(row_index) != expected_raw:
                raise ValueError(
                    f"{route_id} DirInfo row {row_index} differs: "
                    f"{source_routes.get(row_index)}"
                )
            normalized = normalize_sequence(expected_raw, aliases)
            if normalized != render_sequence:
                raise ValueError(
                    f"{route_id} row {row_index} is not an exact dedup alias: "
                    f"{normalized} != {render_sequence}"
                )
            checked_rows.append(
                {
                    "row_index": row_index,
                    "raw_event_sequence": expected_raw,
                    "normalized_event_sequence": normalized,
                }
            )
            used_source_rows.add(row_index)
        signature = tuple(render_sequence)
        if signature in normalized_sequences:
            raise ValueError(f"{route_id} duplicates another rendered route")
        normalized_sequences.add(signature)
        timeline, total_frames, total_samples = route_timeline(
            render_sequence, timeline_by_event
        )
        routes.append(
            {
                "route_id": route_id,
                "title": str(raw["title"]),
                "render_event_sequence": render_sequence,
                "source_rows": checked_rows,
                "timeline": timeline,
                "total_frames": total_frames,
                "total_samples": total_samples,
            }
        )

    excluded_rows: list[dict[str, Any]] = []
    if "excluded_dirinfo_rows" in plan:
        raw_exclusions = plan.get("excluded_dirinfo_rows")
        if not isinstance(raw_exclusions, list):
            raise ValueError("excluded DirInfo row declaration is not a list")
        excluded_indices: set[int] = set()
        for raw in raw_exclusions:
            if not isinstance(raw, Mapping):
                raise ValueError("excluded DirInfo row declaration is invalid")
            row_index = int(raw["row_index"])
            raw_sequence = [str(value) for value in raw["raw_event_sequence"]]
            disposition = str(raw["disposition"])
            blocker = str(raw["blocker"]).strip()
            if (
                row_index in used_source_rows
                or row_index in excluded_indices
                or source_routes.get(row_index) != raw_sequence
                or disposition not in {"blocked", "gameplay_effect_collection"}
                or not blocker
            ):
                raise ValueError(f"excluded DirInfo row {row_index} differs")
            excluded_indices.add(row_index)
            excluded_rows.append(
                {
                    "dirinfo_row": row_index,
                    "raw_event_sequence": raw_sequence,
                    "disposition": disposition,
                    "blocker": blocker,
                }
            )
        if set(source_routes) != used_source_rows | excluded_indices:
            raise ValueError("DirInfo route partition is not exhaustive")

    owner_source_approval: dict[str, Any] | None = None
    if "owner_source_approval" in plan:
        raw = plan["owner_source_approval"]
        if not isinstance(raw, Mapping):
            raise ValueError("owner source approval declaration is invalid")
        path, snapshot = validate_bound_file(
            {"path": raw["path"], "sha256": raw["sha256"]},
            label=f"{family} owner-approved exact source ZH",
            plan_dir=plan_dir,
        )
        bound["owner_source_approval"] = path
        snapshots.append(snapshot)
        approval = read_json(path)
        part = str(raw["part"])
        filename = str(raw["filename"])
        media_sha256 = str(raw["media_sha256"]).upper()
        matches = [
            row
            for row in approval.get("files", [])
            if isinstance(row, Mapping)
            and str(row.get("part", "")) == part
            and str(row.get("filename", "")) == filename
            and str(row.get("sha256", "")).upper() == media_sha256
        ]
        source_zh = artifacts.get("video_zh")
        if (
            approval.get("status") != "uploaded_by_project_owner"
            or len(matches) != 1
            or not isinstance(source_zh, Mapping)
            or str(source_zh.get("sha256", "")).upper() != media_sha256
        ):
            raise ValueError("owner source approval exact-file binding differs")
        owner_source_approval = {
            "part": part,
            "filename": filename,
            "sha256": media_sha256,
            "scope": (
                "owner-approved source ZH only; exact new route and showcase "
                "outputs do not inherit playback or publication approval"
            ),
        }

    return {
        "family": family,
        "title": str(plan["title"]),
        "bound": bound,
        "snapshots": snapshots,
        "family_manifest_sha256": file_sha256(bound["family_manifest"]),
        "timeline_by_event": timeline_by_event,
        "routes": routes,
        "layout": read_json(bound["subtitle_layout"]),
        "source_cues": {
            "ja": parse_srt(bound["subtitles_ja"]),
            "zh": parse_srt(bound["subtitles_zh"]),
        },
        "dedup_aliases": aliases,
        "dirinfo_kind": dirinfo_kind,
        "excluded_dirinfo_rows": excluded_rows,
        "owner_source_approval": owner_source_approval,
    }


def _build_clean_visual(
    *,
    source: Path,
    timeline: Sequence[Mapping[str, Any]],
    output: Path,
    total_frames: int,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    filters = []
    labels = []
    for index, row in enumerate(timeline):
        label = f"v{index}"
        filters.append(
            f"[0:v:0]trim=start_frame={row['source_start_frame']}:"
            f"end_frame={row['source_end_frame']},"
            f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]")
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(total_frames),
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    return validate_video_grid(
        output,
        expected_frames=total_frames,
        ffprobe=ffprobe,
        label="route clean visual",
    )


def _build_pcm(
    *,
    source: Path,
    timeline: Sequence[Mapping[str, Any]],
    output: Path,
    total_samples: int,
    ffmpeg: str,
) -> dict[str, Any]:
    filters = []
    labels = []
    for index, row in enumerate(timeline):
        label = f"a{index}"
        filters.append(
            f"[0:a:0]atrim=start_sample={row['source_start_sample']}:"
            f"end_sample={row['source_end_sample']},asetpts=N/SR/TB[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1,"
        f"atrim=end_sample={total_samples},"
        "aresample=48000,"
        "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[outa]"
    )
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outa]",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            str(output),
        ]
    )
    expected_bytes = total_samples * 8
    if output.stat().st_size != expected_bytes:
        raise RuntimeError(
            f"route PCM byte count differs: {output.stat().st_size} != {expected_bytes}"
        )
    return {
        "sample_count": total_samples,
        "byte_count": expected_bytes,
        "sha256": file_sha256(output),
    }


def _encode_audio_master(
    pcm: Path,
    output: Path,
    *,
    ffmpeg: str,
) -> None:
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "f32le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-i",
            str(pcm),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def _encode_edition(
    *,
    clean_visual: Path,
    audio_master: Path,
    subtitle_path: Path | None,
    layout: Mapping[str, Any],
    fonts_dir: Path,
    output: Path,
    total_frames: int,
    staging: Path,
    ffmpeg: str,
) -> None:
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(clean_visual),
        "-i",
        str(audio_master),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
    ]
    if subtitle_path is None:
        command.extend(["-c:v", "copy"])
    else:
        command.extend(
            [
                "-vf",
                subtitle_filter(
                    layout,
                    srt_path=subtitle_path.relative_to(staging).as_posix(),
                    fonts_dir=fonts_dir.relative_to(staging).as_posix(),
                ),
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                "yuv420p",
            ]
        )
    command.extend(
        [
            "-c:a",
            "copy",
            "-frames:v",
            str(total_frames),
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run(command, cwd=staging)


def _audio_packet_pcm_audit(
    path: Path,
    *,
    expected_samples: int,
    ffmpeg: str,
    ffprobe: str,
    work_dir: Path,
) -> dict[str, Any]:
    packet_result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_packets",
            "-show_entries",
            "packet=duration,size,data_hash",
            "-show_data_hash",
            "sha256",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    packet_json = json.loads(packet_result.stdout)
    packets = packet_json.get("packets", [])
    # ffprobe's packet JSON names this integer time-base duration ``duration``
    # (not the stream-level ``duration_ts`` field).
    packet_samples = sum(int(row.get("duration", 0)) for row in packets)
    if packet_samples < expected_samples or packet_samples > expected_samples + 2048:
        raise RuntimeError(
            f"AAC packet sample coverage differs: {packet_samples}, "
            f"expected {expected_samples}..{expected_samples + 2048}"
        )
    packet_signature = hashlib.sha256(
        "\n".join(str(row.get("data_hash", "")) for row in packets).encode("ascii")
    ).hexdigest().upper()
    decoded = work_dir / f"{path.stem}.decoded-prefix.f32le"
    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-af",
            f"atrim=end_sample={expected_samples}",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "2",
            str(decoded),
        ]
    )
    expected_bytes = expected_samples * 8
    if decoded.stat().st_size != expected_bytes:
        raise RuntimeError("decoded AAC prefix does not cover the exact route PCM grid")
    result = {
        "packet_count": len(packets),
        "packet_duration_samples": packet_samples,
        "packet_data_signature_sha256": packet_signature,
        "decoded_prefix_samples": expected_samples,
        "decoded_prefix_sha256": file_sha256(decoded),
    }
    decoded.unlink()
    return result


def _copy_pcm(sources: Sequence[Path], output: Path) -> None:
    with output.open("wb") as target:
        for source in sources:
            with source.open("rb") as handle:
                shutil.copyfileobj(handle, target, 1024 * 1024)


def _build_one_product(
    *,
    product_id: str,
    title: str,
    timeline: Sequence[Mapping[str, Any]],
    clean_visual: Path,
    pcm: Path,
    cues: Mapping[str, Sequence[Mapping[str, Any]]],
    output_dir: Path,
    staging: Path,
    layout: Mapping[str, Any],
    fonts_dir: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[dict[str, Any], dict[str, Path]]:
    total_frames = int(timeline[-1]["end_frame"])
    total_samples = int(timeline[-1]["end_sample"])
    masters = output_dir / "masters"
    subtitles = output_dir / "subtitles"
    videos = output_dir / "video"
    qa_work = output_dir / ".qa_work"
    for directory in (masters, subtitles, videos, qa_work):
        directory.mkdir(parents=True, exist_ok=True)
    final_clean = masters / f"{product_id}__clean_visual_master.mp4"
    if clean_visual != final_clean:
        shutil.copy2(clean_visual, final_clean)
    final_pcm = masters / f"{product_id}__no_bgm_master.f32le"
    if pcm != final_pcm:
        shutil.copy2(pcm, final_pcm)
    audio_master = masters / f"{product_id}__no_bgm_audio_master.m4a"
    _encode_audio_master(final_pcm, audio_master, ffmpeg=ffmpeg)

    subtitle_paths: dict[str, Path] = {}
    for edition in ("ja", "zh"):
        subtitle_path = subtitles / f"{product_id}__{edition}.srt"
        assert_srt_round_trip(subtitle_path, cues[edition])
        subtitle_paths[edition] = subtitle_path

    media: dict[str, Any] = {}
    video_paths: dict[str, Path] = {}
    packet_audits: dict[str, Any] = {}
    for edition in EDITIONS:
        output = videos / f"{product_id}__{edition}.mp4"
        _encode_edition(
            clean_visual=final_clean,
            audio_master=audio_master,
            subtitle_path=(
                subtitle_paths.get(edition)
                if edition == "none" or cues.get(edition)
                else None
            ),
            layout=layout,
            fonts_dir=fonts_dir,
            output=output,
            total_frames=total_frames,
            staging=staging,
            ffmpeg=ffmpeg,
        )
        audit = validate_output_media(
            output, expected_frames=total_frames, ffprobe=ffprobe
        )
        audit["path"] = relative_output_path(output, staging=staging)
        media[edition] = audit
        packet_audits[edition] = _audio_packet_pcm_audit(
            output,
            expected_samples=total_samples,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            work_dir=qa_work,
        )
        video_paths[edition] = output
    packet_signatures = {
        row["packet_data_signature_sha256"] for row in packet_audits.values()
    }
    decoded_signatures = {
        row["decoded_prefix_sha256"] for row in packet_audits.values()
    }
    if len(packet_signatures) != 1 or len(decoded_signatures) != 1:
        raise RuntimeError("none/JA/ZH audio packets or decoded PCM differ")
    shutil.rmtree(qa_work)
    return (
        {
            "product_id": product_id,
            "title": title,
            "total_frames": total_frames,
            "total_samples": total_samples,
            "duration_ms": milliseconds_for_samples(total_samples),
            "timeline": list(timeline),
            "subtitle_cue_counts": {
                edition: len(cues[edition]) for edition in ("ja", "zh")
            },
            "clean_visual": {
                "path": relative_output_path(final_clean, staging=staging),
                "sha256": file_sha256(final_clean),
            },
            "pcm": {
                "path": relative_output_path(final_pcm, staging=staging),
                "sha256": file_sha256(final_pcm),
                "byte_count": final_pcm.stat().st_size,
            },
            "audio_master": {
                "path": relative_output_path(audio_master, staging=staging),
                "sha256": file_sha256(audio_master),
            },
            "subtitles": {
                edition: {
                    "path": relative_output_path(path, staging=staging),
                    "sha256": file_sha256(path),
                }
                for edition, path in subtitle_paths.items()
            },
            "media": media,
            "audio_packet_pcm_audits": packet_audits,
        },
        video_paths,
    )


def build_family(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[Path, dict[str, Any]]:
    plan = read_json(plan_path)
    resolved = _validate_plan(plan, plan_path=plan_path, ffprobe=ffprobe)
    family = resolved["family"]
    destination = output_root.resolve() / family
    if destination.exists():
        raise FileExistsError(f"versioned family output already exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root.resolve() / f".{family}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    failures: list[dict[str, str]] = []
    completed: list[dict[str, Any]] = []
    route_assets: list[dict[str, Any]] = []
    try:
        fonts_dir = staging / "work" / "fonts"
        fonts_dir.mkdir(parents=True)
        shutil.copy2(resolved["bound"]["font"], fonts_dir / resolved["bound"]["font"].name)
        for route in resolved["routes"]:
            route_dir = staging / "routes" / route["route_id"]
            try:
                route_dir.mkdir(parents=True)
                work = route_dir / ".work"
                work.mkdir()
                clean = work / "clean.mp4"
                pcm = work / "audio.f32le"
                clean_audit = _build_clean_visual(
                    source=resolved["bound"]["clean_visual_master"],
                    timeline=route["timeline"],
                    output=clean,
                    total_frames=route["total_frames"],
                    ffmpeg=ffmpeg,
                    ffprobe=ffprobe,
                )
                pcm_audit = _build_pcm(
                    source=resolved["bound"]["no_bgm_audio_master"],
                    timeline=route["timeline"],
                    output=pcm,
                    total_samples=route["total_samples"],
                    ffmpeg=ffmpeg,
                )
                cues = {
                    edition: route_subtitle_cues(
                        route["render_event_sequence"],
                        resolved["timeline_by_event"],
                        resolved["source_cues"][edition],
                    )
                    for edition in ("ja", "zh")
                }
                product, videos = _build_one_product(
                    product_id=f"{family}__{route['route_id']}",
                    title=route["title"],
                    timeline=route["timeline"],
                    clean_visual=clean,
                    pcm=pcm,
                    cues=cues,
                    output_dir=route_dir,
                    staging=staging,
                    layout=resolved["layout"],
                    fonts_dir=fonts_dir,
                    ffmpeg=ffmpeg,
                    ffprobe=ffprobe,
                )
                product.update(
                    {
                        "schema": ROUTE_MANIFEST_SCHEMA,
                        "status": STATUS,
                        "product_scope": "independent_dirinfo_route_segment",
                        "session_claim": "one_hash_bound_dirinfo_route",
                        "render_event_sequence": route["render_event_sequence"],
                        "dirinfo_source_rows": route["source_rows"],
                        "source_clean_visual_audit": clean_audit,
                        "source_pcm_audit": pcm_audit,
                    }
                )
                write_json(route_dir / "ROUTE_MANIFEST.json", product)
                shutil.rmtree(work)
                completed.append(product)
                route_assets.append(
                    {
                        "route": route,
                        "clean": route_dir
                        / "masters"
                        / f"{family}__{route['route_id']}__clean_visual_master.mp4",
                        "pcm": route_dir
                        / "masters"
                        / f"{family}__{route['route_id']}__no_bgm_master.f32le",
                        "cues": cues,
                        "videos": videos,
                    }
                )
            except BaseException as exc:
                shutil.rmtree(route_dir, ignore_errors=True)
                failures.append(
                    {
                        "route_id": route["route_id"],
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

        showcase: dict[str, Any] | None = None
        if not failures and len(route_assets) == len(resolved["routes"]):
            showcase_dir = staging / "edited_route_chapter_showcase"
            work = showcase_dir / ".work"
            work.mkdir(parents=True)
            clean = work / "showcase-clean.mp4"
            pcm = work / "showcase.f32le"
            visual_filters = []
            labels = []
            command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
            for index, asset in enumerate(route_assets):
                command.extend(["-i", str(asset["clean"])])
                label = f"v{index}"
                frames = asset["route"]["total_frames"]
                visual_filters.append(
                    f"[{index}:v:0]trim=end_frame={frames},"
                    f"setpts=N/({FPS}*TB),format=yuv420p[{label}]"
                )
                labels.append(f"[{label}]")
            visual_filters.append(
                "".join(labels)
                + f"concat=n={len(labels)}:v=1:a=0[outv]"
            )
            total_frames = sum(asset["route"]["total_frames"] for asset in route_assets)
            total_samples = sum(asset["route"]["total_samples"] for asset in route_assets)
            command.extend(
                [
                    "-filter_complex",
                    ";".join(visual_filters),
                    "-map",
                    "[outv]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "14",
                    "-pix_fmt",
                    "yuv420p",
                    "-frames:v",
                    str(total_frames),
                    "-an",
                    "-movflags",
                    "+faststart",
                    str(clean),
                ]
            )
            run(command)
            validate_video_grid(
                clean,
                expected_frames=total_frames,
                ffprobe=ffprobe,
                label=f"{family} edited route-chapter showcase",
            )
            _copy_pcm([asset["pcm"] for asset in route_assets], pcm)
            if pcm.stat().st_size != total_samples * 8:
                raise RuntimeError("showcase PCM byte count differs")

            chapters = []
            timeline = []
            cues: dict[str, list[dict[str, Any]]] = {"ja": [], "zh": []}
            frame_cursor = sample_cursor = 0
            for asset in route_assets:
                route = asset["route"]
                chapters.append(
                    {
                        "route_id": route["route_id"],
                        "title": route["title"],
                        "start_frame": frame_cursor,
                        "end_frame": frame_cursor + route["total_frames"],
                        "start_sample": sample_cursor,
                        "end_sample": sample_cursor + route["total_samples"],
                        "start_ms": milliseconds_for_samples(sample_cursor),
                        "end_ms": milliseconds_for_samples(
                            sample_cursor + route["total_samples"]
                        ),
                        "event_sequence": route["render_event_sequence"],
                    }
                )
                for row in route["timeline"]:
                    timeline.append(
                        {
                            **row,
                            "route_id": route["route_id"],
                            "start_frame": frame_cursor + int(row["start_frame"]),
                            "end_frame": frame_cursor + int(row["end_frame"]),
                            "start_sample": sample_cursor + int(row["start_sample"]),
                            "end_sample": sample_cursor + int(row["end_sample"]),
                        }
                    )
                shift_ms = milliseconds_for_samples(sample_cursor)
                for edition in ("ja", "zh"):
                    cues[edition].extend(
                        {
                            **cue,
                            "start_ms": shift_ms + int(cue["start_ms"]),
                            "end_ms": shift_ms + int(cue["end_ms"]),
                            "route_id": route["route_id"],
                        }
                        for cue in asset["cues"][edition]
                    )
                frame_cursor += route["total_frames"]
                sample_cursor += route["total_samples"]

            showcase, _ = _build_one_product(
                product_id=f"{family}__edited_route-chapter_showcase",
                title=f"{resolved['title']}（编辑路线章节合集）",
                timeline=timeline,
                clean_visual=clean,
                pcm=pcm,
                cues=cues,
                output_dir=showcase_dir,
                staging=staging,
                layout=resolved["layout"],
                fonts_dir=fonts_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            showcase.update(
                {
                    "schema": ROUTE_MANIFEST_SCHEMA,
                    "status": STATUS,
                    "product_scope": "edited_route_chapter_showcase",
                    "session_claim": SHOWCASE_CLAIM,
                    "single_native_session_claimed": False,
                    "chapter_timeline": chapters,
                }
            )
            write_json(showcase_dir / "SHOWCASE_MANIFEST.json", showcase)
            write_json(showcase_dir / "CHAPTER_TIMELINE.json", {"chapters": chapters})
            shutil.rmtree(work)

        final_videos = sorted(staging.rglob("video/*.mp4"))
        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS if not failures else "PARTIAL_ROUTE_FAILURE",
            "automated_spec_qa_passed": not failures,
            "human_playback_approved": False,
            "publication_approved": False,
            "checks": {
                "dirinfo_rows_hash_bound_and_exact": True,
                "dirinfo_route_partition_fail_closed": True,
                "exact_duplicate_aliases_fail_closed": True,
                "source_family_masters_hash_bound": True,
                "native_416x232": True,
                "frame_rate_30fps": True,
                "h264_aac_48khz_stereo": True,
                "no_upscale": True,
                "subtitle_round_trip": True,
                "packet_and_decoded_pcm_audited": True,
                "none_ja_zh_audio_packets_identical_per_product": True,
                "edited_showcase_not_single_session": True,
                "uploaded_files_untouched": True,
            },
            "route_count_requested": len(resolved["routes"]),
            "route_count_completed": len(completed),
            "route_failures": failures,
            "final_mp4_count": len(final_videos),
        }
        write_json(staging / "AUTOMATED_QA.json", qa)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": qa["status"],
            "family": family,
            "title": resolved["title"],
            "audio_profile": "no_bgm",
            "bgm_policy": "intentionally_excluded",
            "voice_se_policy": "preserve_hash_bound_source_family_master",
            "composition_claim": SHOWCASE_CLAIM,
            "single_native_session_claimed": False,
            "editions": list(EDITIONS),
            "routes": completed,
            "showcase": showcase,
            "route_failures": failures,
            "source_snapshots": resolved["snapshots"],
            "family_manifest_sha256": resolved["family_manifest_sha256"],
            "dirinfo_kind": resolved["dirinfo_kind"],
            "excluded_dirinfo_rows": resolved["excluded_dirinfo_rows"],
            "exact_duplicate_alias_map": resolved["dedup_aliases"],
            "owner_source_approval": resolved["owner_source_approval"],
            "human_playback_approved": False,
            "publication_approved": False,
        }
        write_json(staging / "BATCH_MANIFEST.json", manifest)
        hashes = [
            {
                "path": relative_output_path(path, staging=staging),
                "sha256": file_sha256(path),
                "byte_count": path.stat().st_size,
            }
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "SHA256SUMS.json"
        ]
        write_json(
            staging / "SHA256SUMS.json",
            {
                "schema": "magireco-versioned-output-sha256-v1",
                "family": family,
                "files": hashes,
            },
        )
        readme = (
            f"# {resolved['title']} — mature 416 route expansion\n\n"
            f"独立路线：{len(completed)} 条，每条均有 none / JA / ZH。\n\n"
            "长版文件名含 `edited_route-chapter_showcase`，它是把互斥路线分章"
            "编辑成的合集，不代表一次游戏自然播放。BGM 有意排除；保留来源 "
            "family master 中已验证的对白与场景音效。所有文件仍需人工完整播放"
            "确认后才能投稿。\n"
        )
        (staging / "README_REVIEW.md").write_text(readme, encoding="utf-8")
        staging.replace(destination)
        return destination, qa
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="append", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summaries = []
    hard_failures = []
    for plan_path in args.plan:
        try:
            destination, qa = build_family(
                plan_path=plan_path.resolve(),
                output_root=args.output_root.resolve(),
                ffmpeg=args.ffmpeg,
                ffprobe=args.ffprobe,
            )
            summaries.append(
                {
                    "plan": str(plan_path.resolve()),
                    "destination": str(destination),
                    "qa": qa,
                }
            )
        except BaseException as exc:
            hard_failures.append(
                {
                    "plan": str(plan_path.resolve()),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    print(
        json.dumps(
            {"completed": summaries, "hard_failures": hard_failures},
            ensure_ascii=False,
            indent=2,
        )
    )
    if hard_failures or any(row["qa"]["route_failures"] for row in summaries):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
