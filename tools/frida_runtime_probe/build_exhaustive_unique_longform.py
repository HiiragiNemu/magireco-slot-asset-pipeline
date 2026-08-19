#!/usr/bin/env python3
# hash=allow; consumer=exhaustive-longform QA; cost=one pass per bound input;
# decision=reject duplicate or changed media before producing a review candidate.
"""Build an evidence-bound, duplicate-free exhaustive family longform."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

PLAN_SCHEMA = "magireco-exhaustive-unique-longform-plan-v1"
MANIFEST_SCHEMA = "magireco-exhaustive-unique-longform-release-v1"
QA_SCHEMA = "magireco-exhaustive-unique-longform-qa-v1"
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
FAMILY_RE = re.compile(r"^ac\d{4}$")
RELEASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EDITIONS = frozenset({"none", "ja", "zh", "material"})
CONTENT_TYPES = frozenset({"story", "routes", "gameplay_effect", "material"})
AUDIO_PROFILES = frozenset({"no_bgm", "silent"})
ROOT_FIELDS = frozenset({
    "schema", "release_id", "family", "title", "content_type", "native",
    "audio_profile", "authority", "editions", "expected_chapter_count",
    "expected_unique_source_count", "expected_total_video_frames", "human_status",
    "production_scope",
})
NATIVE_FIELDS = frozenset({
    "width", "height", "frame_rate", "video_codec", "audio_codec",
    "audio_sample_rate", "audio_channels",
})
AUTHORITY_FIELDS = frozenset({"role", "path", "sha256"})
EDITION_FIELDS = frozenset({"edition", "output_filename", "sources"})
SILENT_EDITION_FIELDS = EDITION_FIELDS | {"audio_assembly"}
AUDIO_ASSEMBLIES = frozenset({"preserve", "synthesize_silence"})
SOURCE_FIELDS = frozenset({
    "order", "event", "source_identities", "chapter_title", "path", "sha256",
    "video_frames",
})
TRIM_SOURCE_FIELDS = SOURCE_FIELDS | {"input_video_frames"}
EXACT_SCOPE = {
    "native_416_only": True,
    "include_mutually_exclusive_outcomes": True,
    "each_unique_source_once": True,
    "single_exhaustive_longform": True,
    "source_media_modified": False,
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def exact_fields(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def normalize_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value.strip()):
        raise ValueError(f"{label} requires a full SHA-256")
    return value.strip().upper()


def absolute_file(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be an absolute file path")
    path = Path(value.strip())
    if not path.is_absolute() or not path.is_file():
        raise ValueError(f"{label} is not an existing absolute file: {path}")
    return path.resolve(strict=True)


def safe_output_filename(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty filename")
    name = value.strip()
    if Path(name).name != name or Path(name).suffix.lower() != ".mp4":
        raise ValueError(f"{label} must be one MP4 filename without directories")
    if any(char in name for char in '<>:"/\\|?*\x00'):
        raise ValueError(f"{label} contains a forbidden Windows filename character")
    return name


def validate_plan_structure(plan: Mapping[str, Any]) -> dict[str, Any]:
    exact_fields(plan, ROOT_FIELDS, "plan")
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"unsupported plan schema: {plan.get('schema')!r}")
    release_id = plan.get("release_id")
    if not isinstance(release_id, str) or not RELEASE_RE.fullmatch(release_id):
        raise ValueError("release_id is not path-safe")
    family = plan.get("family")
    if not isinstance(family, str) or not FAMILY_RE.fullmatch(family):
        raise ValueError("family must match acNNNN")
    if plan.get("content_type") not in CONTENT_TYPES:
        raise ValueError("content_type is unsupported")
    if plan.get("audio_profile") not in AUDIO_PROFILES:
        raise ValueError("unsupported audio profile")
    if plan.get("human_status") != "HUMAN_PLAYBACK_REQUIRED":
        raise ValueError("new products must remain HUMAN_PLAYBACK_REQUIRED")
    if plan.get("production_scope") != EXACT_SCOPE:
        raise ValueError("production_scope must exactly bind the exhaustive contract")

    native = plan.get("native")
    if not isinstance(native, Mapping):
        raise ValueError("native must be an object")
    exact_fields(native, NATIVE_FIELDS, "native")
    dimensions = (
        positive_int(native.get("width"), "native.width"),
        positive_int(native.get("height"), "native.height"),
    )
    if dimensions != (416, 232):
        raise ValueError("only native 416x232 products are accepted")
    if native.get("frame_rate") != "30/1" or native.get("video_codec") != "h264":
        raise ValueError("native video must be H.264 at 30/1 fps")
    audio = (
        native.get("audio_codec"),
        native.get("audio_sample_rate"),
        native.get("audio_channels"),
    )
    if audio != ("aac", 48000, 2):
        raise ValueError("audio must be AAC 48 kHz stereo")

    authorities = plan.get("authority")
    if not isinstance(authorities, list) or not authorities:
        raise ValueError("authority must be a non-empty list")
    for index, row in enumerate(authorities):
        if not isinstance(row, Mapping):
            raise ValueError(f"authority[{index}] must be an object")
        exact_fields(row, AUTHORITY_FIELDS, f"authority[{index}]")
        if not isinstance(row.get("role"), str) or not row["role"].strip():
            raise ValueError(f"authority[{index}].role is empty")
        normalize_sha256(row.get("sha256"), f"authority[{index}].sha256")

    expected_chapter_count = positive_int(
        plan.get("expected_chapter_count"), "expected_chapter_count"
    )
    expected_unique_count = positive_int(
        plan.get("expected_unique_source_count"), "expected_unique_source_count"
    )
    expected_frames = positive_int(
        plan.get("expected_total_video_frames"), "expected_total_video_frames"
    )
    editions = plan.get("editions")
    if not isinstance(editions, list) or not editions:
        raise ValueError("editions must be a non-empty list")
    seen_editions: set[str] = set()
    seen_filenames: set[str] = set()
    semantic_timeline: list[tuple[str, str, int]] | None = None
    normalized_editions: list[dict[str, Any]] = []
    for edition_index, edition in enumerate(editions):
        if not isinstance(edition, Mapping):
            raise ValueError(f"editions[{edition_index}] must be an object")
        if frozenset(edition) not in {EDITION_FIELDS, SILENT_EDITION_FIELDS}:
            raise ValueError(f"editions[{edition_index}] fields differ from contract")
        edition_name = edition.get("edition")
        if edition_name not in EDITIONS or edition_name in seen_editions:
            raise ValueError(f"duplicate or unsupported edition: {edition_name!r}")
        seen_editions.add(str(edition_name))
        audio_assembly = edition.get("audio_assembly", "preserve")
        if audio_assembly not in AUDIO_ASSEMBLIES:
            raise ValueError(f"unsupported audio_assembly: {audio_assembly!r}")
        filename = safe_output_filename(
            edition.get("output_filename"),
            f"editions[{edition_index}].output_filename",
        )
        if filename.casefold() in seen_filenames:
            raise ValueError("output filenames collide case-insensitively")
        seen_filenames.add(filename.casefold())
        sources = edition.get("sources")
        if not isinstance(sources, list) or len(sources) != expected_chapter_count:
            raise ValueError(
                f"edition {edition_name} must contain exactly {expected_chapter_count} chapters"
            )
        source_ids: set[str] = set()
        source_hashes: set[str] = set()
        timeline: list[tuple[str, str, int]] = []
        frame_total = 0
        for source_index, source in enumerate(sources):
            if not isinstance(source, Mapping):
                raise ValueError(f"source {source_index} must be an object")
            actual_source_fields = frozenset(source)
            if actual_source_fields not in {SOURCE_FIELDS, frozenset(TRIM_SOURCE_FIELDS)}:
                raise ValueError(
                    f"source[{source_index}] fields differ from exact or trimmed contract"
                )
            if source.get("order") != source_index:
                raise ValueError("source order must be contiguous and zero-based")
            event = source.get("event")
            identities = source.get("source_identities")
            if not isinstance(event, str) or not event.startswith(str(family) + "_"):
                raise ValueError(f"source[{source_index}].event is outside {family}")
            if not isinstance(identities, list) or not identities or any(
                not isinstance(identity, str) or not identity.strip()
                for identity in identities
            ):
                raise ValueError(f"source[{source_index}].source_identities is invalid")
            for identity in identities:
                if identity in source_ids:
                    raise ValueError(f"duplicate semantic source identity: {identity}")
                source_ids.add(identity)
            digest = normalize_sha256(
                source.get("sha256"), f"source[{source_index}].sha256"
            )
            if digest in source_hashes:
                raise ValueError(f"duplicate exact source binary: {digest}")
            source_hashes.add(digest)
            frames = positive_int(
                source.get("video_frames"), f"source[{source_index}].video_frames"
            )
            input_frames = positive_int(
                source.get("input_video_frames", frames),
                f"source[{source_index}].input_video_frames",
            )
            if frames > input_frames:
                raise ValueError("trimmed chapter cannot exceed its input frame count")
            frame_total += frames
            timeline.append((event, "|".join(identities), frames))
        if len(source_ids) != expected_unique_count:
            raise ValueError(
                f"edition {edition_name} has {len(source_ids)} unique sources, expected {expected_unique_count}"
            )
        if frame_total != expected_frames:
            raise ValueError(
                f"edition {edition_name} frames {frame_total} != expected {expected_frames}"
            )
        if semantic_timeline is None:
            semantic_timeline = timeline
        elif timeline != semantic_timeline:
            raise ValueError("all editions must share one exact semantic timeline")
        normalized_editions.append(
            {
                "edition": edition_name,
                "output_filename": filename,
                "audio_assembly": audio_assembly,
                "sources": [dict(row) for row in sources],
            }
        )
    normalized = dict(plan)
    normalized["editions"] = normalized_editions
    if plan["content_type"] == "material":
        if plan["audio_profile"] != "silent" or seen_editions != {"material"}:
            raise ValueError("material must be one silent material edition")
        only_edition = normalized_editions[0]
        if only_edition["audio_assembly"] != "synthesize_silence":
            raise ValueError("material audio must be synthesized bounded silence")
        if re.search(r"__(?:none|ja|zh)\.mp4$", only_edition["output_filename"], re.I):
            raise ValueError("material filename must not carry a language suffix")
    elif "material" in seen_editions:
        raise ValueError("material edition is reserved for material content")
    return normalized


def run_probe(ffprobe: str, path: Path) -> dict[str, Any]:
    command = [
        ffprobe, "-v", "error", "-count_frames", "-show_entries",
        "format=start_time,duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,time_base,start_time,duration,nb_read_frames,sample_rate,channels",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8"
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {completed.stderr.strip()}")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError(f"ffprobe returned a non-object for {path}")
    return value


def validate_probe(
    probe: Mapping[str, Any],
    native: Mapping[str, Any],
    expected_frames: int,
    label: str,
    exact_timeline: bool = False,
    audio_policy: str = "required",
) -> dict[str, Any]:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise ValueError(f"{label} has no streams")
    videos = [row for row in streams if row.get("codec_type") == "video"]
    audios = [row for row in streams if row.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise ValueError(f"{label} must have exactly one video stream")
    if audio_policy == "required" and len(audios) != 1:
        raise ValueError(f"{label} must have exactly one audio stream")
    if audio_policy == "absent" and audios:
        raise ValueError(f"{label} must not contain an audio stream")
    if audio_policy == "absent_or_verified_silence" and len(audios) > 1:
        raise ValueError(f"{label} has more than one candidate silent audio stream")
    if audio_policy not in {"required", "absent", "absent_or_verified_silence"}:
        raise ValueError(f"unsupported audio policy: {audio_policy}")
    video = videos[0]
    checks = {
        "video_codec": video.get("codec_name") == native["video_codec"],
        "width": int(video.get("width", -1)) == native["width"],
        "height": int(video.get("height", -1)) == native["height"],
        "frame_rate": video.get("r_frame_rate") == native["frame_rate"],
        "video_frames": int(video.get("nb_read_frames", -1)) == expected_frames,
    }
    audio: Mapping[str, Any] | None = None
    if audio_policy == "required":
        audio = audios[0]
        checks.update({
            "audio_codec": audio.get("codec_name") == native["audio_codec"],
            "audio_sample_rate": int(audio.get("sample_rate", -1))
            == native["audio_sample_rate"],
            "audio_channels": int(audio.get("channels", -1))
            == native["audio_channels"],
        })
    elif audio_policy == "absent":
        checks["audio_stream_absent"] = len(audios) == 0
    else:
        checks["audio_stream_absent_or_single"] = len(audios) <= 1
        if audios:
            audio = audios[0]
            checks.update({
                "candidate_silent_audio_sample_rate": int(
                    audio.get("sample_rate", -1)
                ) == native["audio_sample_rate"],
                "candidate_silent_audio_channels": int(audio.get("channels", -1))
                == native["audio_channels"],
            })
    if exact_timeline:
        if audio is None:
            raise ValueError("exact_timeline requires a final audio stream")
        expected_duration = expected_frames / 30
        video_start = float(video.get("start_time", "nan"))
        audio_start = float(audio.get("start_time", "nan"))
        video_duration = float(video.get("duration", "nan"))
        audio_duration = float(audio.get("duration", "nan"))
        format_row = probe.get("format")
        format_duration = (
            float(format_row.get("duration", "nan"))
            if isinstance(format_row, Mapping) else float("nan")
        )
        one_sample = 1 / int(native["audio_sample_rate"])
        one_aac_frame = 1024 / int(native["audio_sample_rate"])
        video_clock_tolerance = 1 / 3000  # 0.01 frame at the required 30 fps.
        checks.update({
            "video_zero_start": abs(video_start) <= one_sample,
            "audio_zero_start": abs(audio_start) <= one_sample,
            "video_duration_within_0_01_frame": abs(
                video_duration - expected_duration
            ) <= video_clock_tolerance,
            "audio_not_over_video": audio_start + audio_duration
            <= expected_duration + one_sample,
            "audio_not_shorter_than_one_aac_frame": audio_start + audio_duration
            >= expected_duration - one_aac_frame,
            "format_duration_within_0_01_frame": abs(
                format_duration - expected_duration
            ) <= video_clock_tolerance,
        })
    if not all(checks.values()):
        raise ValueError(f"{label} media contract failed: {checks}")
    return {"checks": checks, "probe": probe}


def ffconcat_quote(path: Path) -> str:
    return "'" + str(path).replace("\\", "/").replace("'", "'\\''") + "'"


def output_materialization_strategy(
    paths: Sequence[Path], audio_assembly: str = "preserve"
) -> str:
    if not paths:
        raise ValueError("an edition must contain at least one effective chapter")
    if audio_assembly not in AUDIO_ASSEMBLIES:
        raise ValueError(f"unsupported audio assembly: {audio_assembly}")
    if audio_assembly == "synthesize_silence":
        return "split_video_copy_synthetic_silence_bounded"
    if len(paths) == 1:
        return "exact_single_chapter_copy"
    return "split_video_copy_audio_once_bounded"


def run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8"
    )
    record = {
        "command": command,
        "exit_status": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            + completed.stderr
        )
    return record


def decoded_pcm_is_zero(value: bytes) -> bool:
    return bool(value) and not any(value)


def verify_audio_decodes_to_zero(ffmpeg: str, path: Path) -> dict[str, Any]:
    command = [
        ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0",
        "-f", "s16le", "-acodec", "pcm_s16le", "-",
    ]
    completed = subprocess.run(command, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"silent-audio decode failed for {path}: "
            + completed.stderr.decode("utf-8", errors="replace")
        )
    if not decoded_pcm_is_zero(completed.stdout):
        raise ValueError(f"audio is not exact decoded digital zero: {path}")
    return {
        "command": command,
        "exit_status": 0,
        "decoded_pcm_bytes": len(completed.stdout),
        "all_decoded_samples_zero": True,
    }


def resolve_and_verify_inputs(
    plan: Mapping[str, Any], ffmpeg: str, ffprobe: str
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    authority_snapshots: list[dict[str, Any]] = []
    for index, row in enumerate(plan["authority"]):
        path = absolute_file(row["path"], f"authority[{index}].path")
        actual = file_sha256(path)
        expected = normalize_sha256(row["sha256"], f"authority[{index}].sha256")
        if actual != expected:
            raise ValueError(f"authority hash mismatch: {path}")
        authority_snapshots.append({**row, "path": str(path), "sha256": actual})
    source_snapshots: dict[str, list[dict[str, Any]]] = {}
    for edition in plan["editions"]:
        rows: list[dict[str, Any]] = []
        for index, row in enumerate(edition["sources"]):
            label = f"{edition['edition']} source[{index}]"
            path = absolute_file(row["path"], f"{label}.path")
            actual = file_sha256(path)
            expected = normalize_sha256(row["sha256"], f"{label}.sha256")
            if actual != expected:
                raise ValueError(f"source hash mismatch: {path}")
            probe = run_probe(ffprobe, path)
            synthesize_silence = edition["audio_assembly"] == "synthesize_silence"
            qa = validate_probe(
                probe,
                plan["native"],
                row.get("input_video_frames", row["video_frames"]),
                str(path),
                audio_policy=(
                    "absent_or_verified_silence"
                    if synthesize_silence
                    else "required"
                ),
            )
            audios = [
                stream for stream in probe.get("streams", [])
                if stream.get("codec_type") == "audio"
            ]
            input_audio_verification: dict[str, Any] | None = None
            if synthesize_silence:
                input_audio_verification = (
                    verify_audio_decodes_to_zero(ffmpeg, path)
                    if audios else {
                        "status": "NOT_APPLICABLE_NO_AUDIO_STREAM",
                        "all_decoded_samples_zero": True,
                    }
                )
            rows.append(
                {
                    **row, "path": str(path), "sha256": actual,
                    "media_qa": qa,
                    "input_audio_verification": input_audio_verification,
                }
            )
        source_snapshots[str(edition["edition"])] = rows
    return authority_snapshots, source_snapshots


def reverify_inputs(
    authorities: Sequence[Mapping[str, Any]],
    source_editions: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    for row in authorities:
        if file_sha256(Path(row["path"])) != row["sha256"]:
            raise RuntimeError(f"authority changed during build: {row['path']}")
    for rows in source_editions.values():
        for row in rows:
            if file_sha256(Path(row["path"])) != row["sha256"]:
                raise RuntimeError(f"source changed during build: {row['path']}")



def build(
    plan_path: Path,
    out_root: Path,
    ffmpeg: str,
    ffprobe: str,
    validate_only: bool,
) -> dict[str, Any]:
    plan = validate_plan_structure(read_json(plan_path))
    authorities, source_editions = resolve_and_verify_inputs(plan, ffmpeg, ffprobe)
    if validate_only:
        result = {
            "status": "PASS_VALIDATE_ONLY",
            "release_id": plan["release_id"],
            "family": plan["family"],
            "edition_count": len(plan["editions"]),
            "unique_source_count": plan["expected_unique_source_count"],
            "total_video_frames": plan["expected_total_video_frames"],
            "authority_count": len(authorities),
        }
        print(json.dumps(result, ensure_ascii=False))
        return result

    out_root = out_root.resolve()
    if out_root.exists():
        raise FileExistsError(f"immutable output root already exists: {out_root}")
    out_root.parent.mkdir(parents=True, exist_ok=True)
    staging = out_root.parent / f".{out_root.name}.staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        video_dir = staging / "video"
        manifest_dir = staging / "manifests"
        video_dir.mkdir()
        manifest_dir.mkdir()
        command_records: list[dict[str, Any]] = []
        derived_chapters: list[dict[str, Any]] = []
        effective_paths: dict[str, list[Path]] = {}
        chapter_dir = staging / ".derived-chapters"
        chapter_dir.mkdir()
        assembly_dir = staging / ".assembly"
        assembly_dir.mkdir()
        for edition in plan["editions"]:
            edition_name = str(edition["edition"])
            audio_assembly = str(edition["audio_assembly"])
            effective_paths[edition_name] = []
            for source_index, row in enumerate(source_editions[edition_name]):
                input_path = Path(row["path"])
                input_frames = row.get("input_video_frames", row["video_frames"])
                if input_frames == row["video_frames"]:
                    effective_paths[edition_name].append(input_path)
                    continue
                derived = chapter_dir / f"{edition_name}_{source_index:03d}.mp4"
                trim_seconds = row["video_frames"] / 30
                if audio_assembly == "synthesize_silence":
                    trim_command = [
                        ffmpeg, "-v", "error", "-i", str(input_path),
                        "-map", "0:v:0", "-an", "-c:v", "copy",
                        "-frames:v", str(row["video_frames"]),
                        "-movflags", "+faststart", str(derived),
                    ]
                else:
                    trim_command = [
                        ffmpeg, "-v", "error", "-i", str(input_path),
                        "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
                        "-frames:v", str(row["video_frames"]),
                        "-af", f"atrim=duration={trim_seconds:.9f},asetpts=PTS-STARTPTS",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        "-shortest", "-movflags", "+faststart", str(derived),
                    ]
                command_records.append(run_command(trim_command))
                derived_qa = validate_probe(
                    run_probe(ffprobe, derived),
                    plan["native"], row["video_frames"], str(derived),
                    exact_timeline=audio_assembly == "preserve",
                    audio_policy=(
                        "absent" if audio_assembly == "synthesize_silence"
                        else "required"
                    ),
                )
                derived_chapters.append({
                    "edition": edition_name,
                    "source_index": source_index,
                    "event": row["event"],
                    "input_video_frames": input_frames,
                    "output_video_frames": row["video_frames"],
                    "sha256": file_sha256(derived),
                    "media_qa": derived_qa,
                })
                effective_paths[edition_name].append(derived)

        outputs: list[dict[str, Any]] = []
        for edition in plan["editions"]:
            edition_name = str(edition["edition"])
            output = video_dir / edition["output_filename"]
            paths = effective_paths[edition_name]
            audio_assembly = str(edition["audio_assembly"])
            strategy = output_materialization_strategy(paths, audio_assembly)
            if strategy == "exact_single_chapter_copy":
                shutil.copy2(paths[0], output)
                command_records.append({
                    "operation": strategy,
                    "source": str(paths[0]),
                    "destination": str(output),
                    "exit_status": 0,
                    "source_sha256": file_sha256(paths[0]),
                    "destination_sha256": file_sha256(output),
                })
            else:
                concat_path = manifest_dir / f"{edition_name}.ffconcat"
                concat_path.write_text(
                    "ffconcat version 1.0\n"
                    + "".join(
                        f"file {ffconcat_quote(path)}\n"
                        f"duration {source['video_frames'] / 30:.9f}\n"
                        for path, source in zip(paths, edition["sources"], strict=True)
                    ),
                    encoding="utf-8",
                )
                video_only = assembly_dir / f"{edition_name}.video.mp4"
                audio_only = assembly_dir / f"{edition_name}.audio.m4a"
                if len(paths) == 1:
                    shutil.copy2(paths[0], video_only)
                    command_records.append({
                        "operation": "exact_single_video_copy",
                        "source": str(paths[0]), "destination": str(video_only),
                        "exit_status": 0,
                    })
                else:
                    video_command = [
                        ffmpeg, "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", str(concat_path), "-map", "0:v:0", "-an",
                        "-c:v", "copy", "-movflags", "+faststart", str(video_only),
                    ]
                    command_records.append(run_command(video_command))
                duration = plan["expected_total_video_frames"] / 30
                if audio_assembly == "synthesize_silence":
                    audio_command = [
                        ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-t", f"{duration:.9f}", "-c:a", "aac", "-b:a", "192k",
                        "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
                        str(audio_only),
                    ]
                else:
                    audio_command = [
                        ffmpeg, "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", str(concat_path), "-map", "0:a:0", "-vn",
                        "-af",
                        f"atrim=duration={duration:.9f},asetpts=PTS-STARTPTS",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        "-movflags", "+faststart", str(audio_only),
                    ]
                mux_command = [
                    ffmpeg, "-v", "error", "-i", str(video_only),
                    "-i", str(audio_only), "-map", "0:v:0", "-map", "1:a:0",
                    "-c", "copy", "-movflags", "+faststart", str(output),
                ]
                command_records.append(run_command(audio_command))
                command_records.append(run_command(mux_command))
            qa = validate_probe(
                run_probe(ffprobe, output),
                plan["native"],
                plan["expected_total_video_frames"],
                str(output),
                exact_timeline=True,
            )
            outputs.append({
                "edition": edition_name,
                "filename": output.name,
                "relative_path": output.relative_to(staging).as_posix(),
                "sha256": file_sha256(output),
                "assembly_method": strategy,
                "audio_assembly": audio_assembly,
                "media_qa": qa,
            })
        reverify_inputs(authorities, source_editions)
        shutil.rmtree(chapter_dir)
        shutil.rmtree(assembly_dir)

        plan_snapshot = dict(plan)
        plan_snapshot["canonical_plan_sha256"] = canonical_sha256(plan)
        write_json(manifest_dir / "PLAN_SNAPSHOT.json", plan_snapshot)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": "AUTO_QA_PASS_HUMAN_PLAYBACK_REQUIRED",
            "release_id": plan["release_id"],
            "family": plan["family"],
            "title": plan["title"],
            "content_type": plan["content_type"],
            "audio_profile": plan["audio_profile"],
            "production_scope": plan["production_scope"],
            "expected_chapter_count": plan["expected_chapter_count"],
            "expected_unique_source_count": plan["expected_unique_source_count"],
            "expected_total_video_frames": plan["expected_total_video_frames"],
            "expected_duration_seconds": plan["expected_total_video_frames"] / 30,
            "authority": authorities,
            "source_editions": source_editions,
            "derived_parent_cut_chapters": derived_chapters,
            "outputs": outputs,
            "source_media_modified": False,
        }
        write_json(manifest_dir / "RELEASE_MANIFEST.json", manifest)
        verification = {
            "schema": QA_SCHEMA,
            "result": "PASS_HUMAN_PLAYBACK_REQUIRED",
            "plan_path": str(plan_path.resolve(strict=True)),
            "plan_file_sha256": file_sha256(plan_path.resolve(strict=True)),
            "commands": command_records,
            "checks": {
                "authority_hashes_reverified": True,
                "source_hashes_reverified": True,
                "semantic_source_identities_unique_per_edition": True,
                "exact_source_binaries_unique_per_edition": True,
                "all_editions_share_semantic_timeline": True,
                "parent_cut_trim_commands_verified": True,
                "trimmed_chapter_audio_reencoded_aac_192k": True,
                "output_video_frame_count_exact": True,
                "native_416x232_30fps_h264": True,
                "aac_48khz_stereo": True,
                "source_media_modified": False,
            },
            "outputs": outputs,
        }
        write_json(manifest_dir / "VERIFICATION_RECORD.json", verification)
        (manifest_dir / "SHA256SUMS.txt").write_text(
            "".join(
                f"{row['sha256']}  {row['relative_path']}\n" for row in outputs
            ),
            encoding="utf-8",
        )
        (staging / "READY_FOR_HUMAN_REVIEW").write_text(
            "AUTO_QA_PASS; HUMAN_PLAYBACK_REQUIRED; DO_NOT_UPLOAD_BEFORE_APPROVAL\n",
            encoding="utf-8",
        )
        expected_outputs = {
            row["relative_path"]: row["sha256"] for row in outputs
        }
        rollback_code = (
            "import argparse, hashlib, json, os\n"
            "from pathlib import Path\n"
            f"ROOT = Path({str(out_root)!r})\n"
            f"EXPECTED = json.loads({json.dumps(json.dumps(expected_outputs))})\n"
            "def digest(path):\n"
            "    value = hashlib.sha256()\n"
            "    with path.open('rb') as stream:\n"
            "        for block in iter(lambda: stream.read(1048576), b''):\n"
            "            value.update(block)\n"
            "    return value.hexdigest().upper()\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--execute', action='store_true')\n"
            "args = parser.parse_args()\n"
            "for rel, expected in EXPECTED.items():\n"
            "    path = ROOT / rel\n"
            "    if not path.is_file() or digest(path) != expected:\n"
            "        raise SystemExit('ROLLBACK_PREFLIGHT_FAILED: ' + str(path))\n"
            "if args.execute:\n"
            "    target = ROOT.with_name(ROOT.name + '.rolled-back')\n"
            "    if target.exists():\n"
            "        raise SystemExit('rollback target already exists: ' + str(target))\n"
            "    os.replace(ROOT, target)\n"
            "    print('ROLLBACK_EXECUTED: ' + str(target))\n"
            "else:\n"
            "    print('ROLLBACK_PREFLIGHT_PASS')\n"
        )
        (staging / "ROLLBACK.py").write_text(rollback_code, encoding="utf-8")
        os.replace(staging, out_root)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    result = {
        "status": "PASS_HUMAN_PLAYBACK_REQUIRED",
        "release_id": plan["release_id"],
        "family": plan["family"],
        "output_root": str(out_root),
        "edition_count": len(outputs),
        "unique_source_count": plan["expected_unique_source_count"],
        "total_video_frames": plan["expected_total_video_frames"],
        "outputs": [
            {"path": str(out_root / row["relative_path"]), "sha256": row["sha256"]}
            for row in outputs
        ],
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    build(
        Path(args.plan), Path(args.out_root), args.ffmpeg, args.ffprobe,
        args.validate_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
