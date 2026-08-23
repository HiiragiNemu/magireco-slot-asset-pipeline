#!/usr/bin/env python3
"""Render one verified event manifest at its native video dimensions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

try:
    from .composition_contract import (
        composition_contract_projection,
        composition_contract_sha256,
    )
    from .output_path_contract import (
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )
    from .render_subtitle_editions import (
        file_sha256 as production_file_sha256,
        probe as production_probe,
        probe_video_timeline,
        video_encoding_signature,
        video_packet_hash,
    )
    from .subtitle_edition_contract import (
        AUDIO_PROFILES,
        SUPPORTED_EDITIONS,
        build_edition_plan,
        load_font_config,
    )
except ImportError:  # direct script execution
    from composition_contract import (  # type: ignore
        composition_contract_projection,
        composition_contract_sha256,
    )
    from output_path_contract import (  # type: ignore
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )
    from render_subtitle_editions import (  # type: ignore
        file_sha256 as production_file_sha256,
        probe as production_probe,
        probe_video_timeline,
        video_encoding_signature,
        video_packet_hash,
    )
    from subtitle_edition_contract import (  # type: ignore
        AUDIO_PROFILES,
        SUPPORTED_EDITIONS,
        build_edition_plan,
        load_font_config,
    )


CLEAN_VISUAL_READY_SCHEMA = "magireco-clean-visual-release-ready-v1"
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument(
        "--edition",
        action="append",
        choices=SUPPORTED_EDITIONS,
        dest="editions",
        help="repeat to request none/ja/zh; verified default is the full three variants",
    )
    parser.add_argument("--font-config")
    parser.add_argument(
        "--audio-profile",
        action="append",
        choices=AUDIO_PROFILES,
        dest="audio_profiles",
        help="repeat to select verified with_bgm/no_bgm masters",
    )
    parser.add_argument(
        "--legacy-two-edition",
        action="store_true",
        help="explicitly retain the old unclassified-audio none+ja behavior",
    )
    parser.add_argument(
        "--clean-visual-only",
        action="store_true",
        help=(
            "render only the evidence-bound native H.264 composition, with no "
            "audio or subtitles, and emit a bound event-manifest copy"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "validate edition tracks, timing, and explicit font provenance/coverage "
            "without probing or rendering media"
        ),
    )
    return parser.parse_args()


def duration_metadata_matches_cfr_grid(actual_ms: int, expected_ms: int) -> bool:
    """Accept only the sub-millisecond MP4 duration-metadata rounding window.

    Exact CFR correctness is checked immediately afterwards from every decoded
    frame and encoded packet.  FFmpeg can serialize an otherwise exact 30 fps
    presentation duration just below the nearest millisecond (for example,
    14.566016 seconds for an exact 437/30-second packet grid), so the rounded
    container metadata can differ from the manifest's rounded value by 1 ms.
    """

    return abs(actual_ms - expected_ms) <= 1


def resolve_non_loop_overlay_duration_ms(
    row: dict,
    clip_probe: dict,
    render_duration_ms: int,
) -> int:
    """Resolve an optional authored overlay interval without extending media.

    Older plans omit ``duration_ms`` and retain the full source duration.  New
    exact MovieLayer plans may bind a shorter authored prefix of a longer
    official source; the explicit interval must remain positive, inside the
    source (allowing one CFR-frame of metadata rounding), and inside the event.
    """

    source_duration_ms = round(float(clip_probe["format"]["duration"]) * 1000)
    raw_duration = row.get("duration_ms")
    if raw_duration is None:
        duration_ms = source_duration_ms
    else:
        try:
            duration_ms = int(raw_duration)
        except (TypeError, ValueError) as error:
            raise RuntimeError("overlay duration_ms is not an integer") from error
        if str(raw_duration).strip() != str(duration_ms):
            raise RuntimeError("overlay duration_ms is not an exact integer")
    start_ms = int(row.get("start_ms", 0))
    if duration_ms <= 0:
        raise RuntimeError("overlay duration_ms must be positive")
    if duration_ms > source_duration_ms + 34:
        raise RuntimeError("overlay duration_ms exceeds the official source")
    if start_ms < 0 or start_ms + duration_ms > render_duration_ms + 34:
        raise RuntimeError("overlay authored interval exceeds the event")
    return duration_ms


def audited_video_frame_count(path: Path, ffprobe: str) -> int:
    payload = production_probe(path, ffprobe)
    streams = [
        row for row in payload.get("streams", []) if row.get("codec_type") == "video"
    ]
    if len(streams) != 1:
        raise RuntimeError(f"expected one video stream while counting frames: {path}")
    value = streams[0].get("nb_read_frames") or streams[0].get("nb_frames")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"video frame count is unavailable: {path}") from error
    if result <= 0:
        raise RuntimeError(f"video frame count is not positive: {path}")
    return result


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,r_frame_rate,pix_fmt,"
            "sample_rate,channels,duration:format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def snapshot_clip_source_hashes(manifest: dict) -> list[dict]:
    """Verify every clean-visual source against its production binding."""

    rows = manifest.get("clips")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("event manifest has no visual clips")
    actual_by_path: dict[str, str] = {}
    snapshots: list[dict] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(f"manifest clip {index} is not an object")
        source_path = Path(str(row.get("path", ""))).resolve()
        if not source_path.is_file():
            raise RuntimeError(f"manifest clip {index} source is missing: {source_path}")
        expected = str(row.get("source_sha256", "")).strip().upper()
        if not SHA256_RE.fullmatch(expected):
            raise RuntimeError(
                f"manifest clip {index} lacks a valid source_sha256 binding"
            )
        key = str(source_path)
        if key not in actual_by_path:
            actual_by_path[key] = production_file_sha256(source_path)
        actual = actual_by_path[key]
        if actual != expected:
            raise RuntimeError(
                f"manifest clip {index} source SHA-256 mismatch: "
                f"expected {expected}, found {actual}"
            )
        snapshots.append(
            {
                "order": index,
                "dgm_name": str(row.get("dgm_name", "")),
                "path": key,
                "source_sha256": expected,
            }
        )
    return snapshots


def verify_clip_source_hashes_unchanged(snapshots: list[dict]) -> None:
    """Fail if a source disappears or changes after rendering started."""

    actual_by_path: dict[str, str] = {}
    for row in snapshots:
        source_path = Path(str(row["path"]))
        if not source_path.is_file():
            raise RuntimeError(f"clean-visual source disappeared: {source_path}")
        key = str(source_path)
        if key not in actual_by_path:
            actual_by_path[key] = production_file_sha256(source_path)
        if actual_by_path[key] != row["source_sha256"]:
            raise RuntimeError(
                "clean-visual source changed during render: "
                f"{source_path}"
            )


def _validate_clean_visual_release(
    release_root: Path,
    *,
    event: str,
    published_root: Path,
) -> dict:
    """Validate the complete staged or promoted clean-visual release."""

    ready_path = release_root / "READY.json"
    if not ready_path.is_file():
        raise RuntimeError("clean-visual release lacks READY.json")
    try:
        ready = json.loads(ready_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("clean-visual READY.json is not valid JSON") from error
    if (
        ready.get("schema") != CLEAN_VISUAL_READY_SCHEMA
        or ready.get("status") != "READY"
        or ready.get("event") != event
    ):
        raise RuntimeError("clean-visual READY.json identity/status mismatch")
    artifacts = ready.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("clean-visual READY.json has no artifact list")
    expected_roles = {
        "clean_visual",
        "render_manifest",
        "bound_event_manifest",
    }
    roles: set[str] = set()
    artifact_paths: dict[str, Path] = {}
    for row in artifacts:
        if not isinstance(row, dict):
            raise RuntimeError("clean-visual READY artifact row is not an object")
        role = str(row.get("role", ""))
        relative_path = str(row.get("relative_path", ""))
        expected_sha256 = str(row.get("sha256", "")).upper()
        if role in roles or role not in expected_roles:
            raise RuntimeError("clean-visual READY artifact roles are invalid")
        if not relative_path or Path(relative_path).is_absolute():
            raise RuntimeError("clean-visual READY artifact path is invalid")
        artifact_path = ensure_resolved_containment(
            release_root,
            release_root / relative_path,
            label=f"{event} clean-visual READY artifact",
        )
        if not artifact_path.is_file():
            raise RuntimeError(f"clean-visual READY artifact is missing: {role}")
        if not SHA256_RE.fullmatch(expected_sha256):
            raise RuntimeError(f"clean-visual READY artifact hash is invalid: {role}")
        if production_file_sha256(artifact_path) != expected_sha256:
            raise RuntimeError(f"clean-visual READY artifact hash mismatch: {role}")
        roles.add(role)
        artifact_paths[role] = artifact_path
    if roles != expected_roles:
        raise RuntimeError("clean-visual READY artifact set is incomplete")

    report = json.loads(
        artifact_paths["render_manifest"].read_text(encoding="utf-8")
    )
    bound = json.loads(
        artifact_paths["bound_event_manifest"].read_text(encoding="utf-8")
    )
    published_video = (
        published_root / "clean_visual" / f"{event}__clean_visual.mp4"
    ).resolve()
    published_report = (published_root / "render_manifest.json").resolve()
    actual_video_sha256 = production_file_sha256(
        artifact_paths["clean_visual"]
    )
    if (
        report.get("schema") != "magireco-clean-visual-render-v1"
        or report.get("status") != "passed"
        or report.get("publishable") is not True
        or Path(str(report.get("output", ""))).resolve() != published_video
        or report.get("output_sha256") != actual_video_sha256
    ):
        raise RuntimeError("clean-visual render manifest release binding mismatch")
    binding = bound.get("clean_visual_master", {})
    artifact_binding = binding.get("artifact", {})
    report_binding = binding.get("render_manifest", {})
    if (
        Path(str(artifact_binding.get("path", ""))).resolve() != published_video
        or artifact_binding.get("sha256") != report.get("output_sha256")
        or Path(str(report_binding.get("path", ""))).resolve() != published_report
        or report_binding.get("sha256")
        != production_file_sha256(artifact_paths["render_manifest"])
    ):
        raise RuntimeError("bound event manifest clean_visual_master mismatch")
    return ready


def _promote_clean_visual_release(
    *,
    staging_root: Path,
    published_root: Path,
    event: str,
    overwrite: bool,
) -> None:
    """Promote one complete same-volume directory and restore on late failure."""

    _validate_clean_visual_release(
        staging_root,
        event=event,
        published_root=published_root,
    )
    previous_root: Path | None = None
    failed_root: Path | None = None
    if published_root.exists():
        if not overwrite:
            raise FileExistsError(
                f"clean-visual release exists; pass --overwrite: {published_root}"
            )
        previous_root = published_root.parent / (
            f".{published_root.name}.previous-{uuid.uuid4().hex}"
        )
        published_root.replace(previous_root)
    try:
        staging_root.replace(published_root)
        _validate_clean_visual_release(
            published_root,
            event=event,
            published_root=published_root,
        )
    except BaseException:
        if published_root.exists():
            failed_root = published_root.parent / (
                f".{published_root.name}.failed-{uuid.uuid4().hex}"
            )
            published_root.replace(failed_root)
        if previous_root is not None and not published_root.exists():
            previous_root.replace(published_root)
        if failed_root is not None:
            shutil.rmtree(failed_root, ignore_errors=True)
        raise
    if previous_root is not None:
        shutil.rmtree(previous_root, ignore_errors=True)


def audio_hash(path: Path, ffmpeg: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip().split("=", 1)[-1].upper()


def srt_time(milliseconds: int) -> str:
    value = max(milliseconds, 0)
    hours, value = divmod(value, 3_600_000)
    minutes, value = divmod(value, 60_000)
    seconds, millis = divmod(value, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def write_srt(path: Path, cues: list[dict]) -> None:
    lines: list[str] = []
    for index, row in enumerate(cues, 1):
        lines.extend(
            [
                str(index),
                f"{srt_time(int(row['start_ms']))} --> "
                f"{srt_time(int(row['end_ms']))}",
                str(row["text"]),
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def edition_paths(out_root: Path, event: str, language: str) -> tuple[Path, Path]:
    event = validate_output_identifier(event, label="event")
    if language == "ja":
        paths = (
            out_root / "with_subtitles" / f"{event}__subtitles.mp4",
            out_root / "subtitles" / f"{event}.srt",
        )
    else:
        paths = (
            out_root
            / f"with_subtitles_{language}"
            / f"{event}__{language}_subtitles.mp4",
            out_root / f"subtitles_{language}" / f"{event}.{language}.srt",
        )
    return tuple(
        ensure_resolved_containment(out_root, path, label=f"{event} edition output")
        for path in paths
    )


def link_or_copy(source: Path, target: Path, *, overwrite: bool) -> str:
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"output exists; pass --overwrite: {target}")
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def validate_explicit_composition_plan(manifest: dict) -> dict:
    """Fail closed unless the clean render has a complete explicit plan."""

    composition_model = manifest.get("video_composition_model")
    if composition_model not in {
        "linear_full_frame_sequence",
        "timed_full_frame_layers",
    }:
        raise RuntimeError(
            f"unsupported or blank video_composition_model: {composition_model!r}"
        )
    plan = manifest.get("composition_plan")
    if not isinstance(plan, dict) or not plan:
        raise RuntimeError("clean-visual production requires an explicit composition_plan")
    if plan.get("model") != composition_model:
        raise RuntimeError(
            "composition_plan.model does not match video_composition_model"
        )
    if plan.get("event") not in (None, manifest.get("event")):
        raise RuntimeError("composition_plan.event does not match manifest event")
    if plan.get("native_dimensions") not in (
        None,
        manifest.get("native_dimensions"),
    ):
        raise RuntimeError(
            "composition_plan.native_dimensions does not match manifest"
        )
    # Authored plans describe the evidence-backed content tail.  A production
    # manifest may extend that tail by less than one CFR frame so that video
    # packets and 48 kHz audio share an exact presentation boundary.  Keep the
    # authored value in the contract instead of silently rewriting it.
    plan_duration_ms = plan.get("duration_ms")
    accepted_plan_durations = {
        manifest.get("render_duration_ms"),
        manifest.get("raw_render_duration_ms"),
        manifest.get("timeline_content_end_ms"),
    }
    if manifest.get("video_composition_model") == "timed_full_frame_layers":
        accepted_plan_durations.add(manifest.get("video_duration_ms"))
    if plan_duration_ms is not None and plan_duration_ms not in accepted_plan_durations:
        raise RuntimeError(
            "composition_plan.duration_ms does not match the content or CFR "
            "presentation tail"
        )
    if plan.get("extension_policy") != manifest.get("video_extension_policy"):
        raise RuntimeError(
            "composition_plan.extension_policy does not match manifest"
        )
    clips = manifest.get("clips")
    plan_clips = plan.get("clips")
    if not isinstance(clips, list) or not clips:
        raise RuntimeError("event manifest has no visual clips")
    if not isinstance(plan_clips, list) or not plan_clips:
        raise RuntimeError("composition_plan has no clip rows")

    def names(rows: list, *, label: str) -> list[str]:
        result = [
            str(row.get("dgm_name", "")).strip()
            for row in rows
            if isinstance(row, dict)
        ]
        if len(result) != len(rows) or any(not value for value in result):
            raise RuntimeError(f"{label} contains a blank or non-object clip row")
        if len(set(result)) != len(result):
            raise RuntimeError(f"{label} contains duplicate dgm_name values")
        return result

    clip_names = names(clips, label="manifest clips")
    plan_names = names(plan_clips, label="composition_plan clips")
    if set(clip_names) != set(plan_names):
        raise RuntimeError(
            "composition_plan clip coverage does not exactly match manifest clips"
        )
    if composition_model == "linear_full_frame_sequence" and clip_names != plan_names:
        raise RuntimeError(
            "linear composition_plan clip order does not match manifest clips"
        )
    return plan


def _main(args: argparse.Namespace, transaction_cleanup: list[Path]) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_manifest_sha256 = production_file_sha256(manifest_path)
    event = validate_output_identifier(manifest["event"], label="manifest event")
    gates = manifest.get("quality_gates", {})
    if args.clean_visual_only:
        if gates.get("composition_resolved") is not True:
            raise SystemExit(
                "manifest does not have a verified resolved visual composition"
            )
    elif not gates.get("ready"):
        raise SystemExit(
            f"manifest is not ready: {', '.join(gates.get('errors', []))}"
        )
    if manifest.get("classification") not in {
        "native_full_frame_only",
        "verified_native_composite",
    }:
        raise SystemExit("refusing to render unverified event classification")

    if args.clean_visual_only and args.legacy_two_edition:
        raise SystemExit(
            "--clean-visual-only and --legacy-two-edition are mutually exclusive"
        )
    if args.clean_visual_only and any(
        (args.editions, args.audio_profiles, args.font_config)
    ):
        raise SystemExit(
            "clean-visual mode does not accept edition, audio-profile, or font options"
        )

    edition_plan: dict | None = None
    source_composition_projection: dict | None = None
    source_composition_sha256 = ""
    clip_source_snapshots: list[dict] = []
    if args.clean_visual_only:
        try:
            validate_explicit_composition_plan(manifest)
            clip_source_snapshots = snapshot_clip_source_hashes(manifest)
        except RuntimeError as error:
            raise SystemExit(str(error)) from error
        source_composition_projection = composition_contract_projection(manifest)
        source_composition_sha256 = composition_contract_sha256(manifest)
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "schema": "magireco-clean-visual-render-dry-run-v1",
                        "dry_run": True,
                        "rendered": False,
                        "source_manifest": str(manifest_path),
                        "source_composition_contract_sha256": (
                            source_composition_sha256
                        ),
                        "source_composition_contract": (
                            source_composition_projection
                        ),
                        "source_clips": clip_source_snapshots,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
    else:
        font_config = load_font_config(
            Path(args.font_config).resolve() if args.font_config else None
        )
        edition_plan = build_edition_plan(
            manifest,
            editions=args.editions,
            audio_profiles=args.audio_profiles,
            legacy_compat=args.legacy_two_edition,
            font_config=font_config,
            manifest_path=manifest_path,
        )
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "schema": "magireco-event-render-dry-run-v1",
                        "dry_run": True,
                        "rendered": False,
                        "source_manifest": str(manifest_path),
                        "edition_plan": edition_plan,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not args.legacy_two_edition:
            raise SystemExit(
                "verified 2x3 audio-master rendering is not implemented in this "
                "composition renderer yet; refusing to turn the existing audio list "
                "into a guessed BGM mix. Use --dry-run to validate evidence or the "
                "explicit --legacy-two-edition compatibility path."
            )

    output_parent = Path(args.out_root).resolve()
    published_out_root = resolve_output_child(
        output_parent, event, label="manifest event"
    )
    if args.clean_visual_only:
        if published_out_root.exists() and not args.overwrite:
            raise SystemExit(
                "refusing to overwrite existing clean-visual release: "
                f"{published_out_root}"
            )
        output_parent.mkdir(parents=True, exist_ok=True)
        staging_container = Path(
            tempfile.mkdtemp(
                prefix=f".{event}.clean-visual-staging-",
                dir=output_parent,
            )
        )
        transaction_cleanup.append(staging_container)
        out_root = staging_container / "release"
    else:
        out_root = published_out_root
    work_dir = ensure_resolved_containment(
        out_root, out_root / "_work", label=f"{event} work directory"
    )
    without_dir = ensure_resolved_containment(
        out_root,
        out_root / "without_subtitles",
        label=f"{event} subtitle-free directory",
    )
    clean_visual_dir = ensure_resolved_containment(
        out_root,
        out_root / "clean_visual",
        label=f"{event} clean-visual directory",
    )
    directories = (
        (clean_visual_dir, work_dir)
        if args.clean_visual_only
        else (without_dir, work_dir)
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    without_path = without_dir / f"{event}.mp4"
    output_manifest_path = out_root / "render_manifest.json"
    clean_visual_path = clean_visual_dir / f"{event}__clean_visual.mp4"
    bound_manifest_path = out_root / f"{event}.clean_visual.bound.json"
    published_output_manifest_path = published_out_root / "render_manifest.json"
    published_clean_visual_path = (
        published_out_root / "clean_visual" / f"{event}__clean_visual.mp4"
    )
    published_bound_manifest_path = (
        published_out_root / f"{event}.clean_visual.bound.json"
    )
    if args.clean_visual_only:
        requested: list[str] = []
        subtitle_outputs: dict[str, tuple[Path, Path]] = {}
        existing: list[Path] = []
    else:
        assert edition_plan is not None
        requested = list(edition_plan["requested_editions"])
        subtitle_outputs = {
            language: edition_paths(out_root, event, language)
            for language in requested
            if language != "none"
        }
        existing = [
            path
            for path in (
                without_path,
                output_manifest_path,
                *(path for pair in subtitle_outputs.values() for path in pair),
            )
            if path.exists()
        ]
    if existing and not args.overwrite:
        raise SystemExit(
            "refusing to overwrite existing output: "
            + ", ".join(str(path) for path in existing)
        )

    clips = [Path(row["path"]).resolve() for row in manifest["clips"]]
    clip_probes = [probe(path, args.ffprobe) for path in clips]
    composition_model = manifest.get(
        "video_composition_model", "linear_full_frame_sequence"
    )
    plan = manifest.get("composition_plan", {})
    plan_rows = {
        str(row.get("dgm_name", "")): row
        for row in plan.get("clips", [])
    }
    source_signatures: list[tuple[int, int, str, str]] = []
    for item in clip_probes:
        stream = next(
            stream
            for stream in item["streams"]
            if stream.get("codec_type") == "video"
        )
        source_signatures.append(
            (
                stream.get("width"),
                stream.get("height"),
                stream.get("r_frame_rate"),
                stream.get("pix_fmt"),
            )
        )
    expected = manifest["native_dimensions"]
    width = int(expected["width"])
    height = int(expected["height"])
    if composition_model == "timed_full_frame_layers":
        background_signatures = {
            signature
            for row, signature in zip(manifest["clips"], source_signatures)
            if plan_rows.get(row["dgm_name"], {}).get("role")
            in {"background", "loop_background"}
        }
        if len(background_signatures) != 1:
            raise SystemExit(
                "timed composition background signature mismatch: "
                f"{sorted(background_signatures)}"
            )
        background_signature = next(iter(background_signatures))
        _, _, frame_rate, pixel_format = background_signature
        for row, signature in zip(manifest["clips"], source_signatures):
            source_width, source_height, source_rate, source_pixel_format = signature
            plan_row = plan_rows.get(row["dgm_name"], {})
            role = plan_row.get("role")
            if source_rate != frame_rate or source_pixel_format != pixel_format:
                raise SystemExit(
                    f"source rate/pixel mismatch for {row['dgm_name']}: {signature}"
                )
            if role in {"background", "loop_background"} and (
                source_width != width or source_height != height
            ):
                raise SystemExit(
                    f"background dimension mismatch for {row['dgm_name']}: "
                    f"{source_width}x{source_height}"
                )
            if (
                role in {"screen_overlay", "loop_screen_overlay"}
                and (source_width != width or source_height != height)
                and not plan_row.get("scale_to_native")
            ):
                raise SystemExit(
                    f"overlay resize is not verified for {row['dgm_name']}: "
                    f"{source_width}x{source_height}"
                )
    else:
        signatures = set(source_signatures)
        padded_linear_plan = plan.get("model") == "linear_full_frame_sequence" and any(
            row.get("pad_to_native") for row in plan.get("clips", [])
        )
        if padded_linear_plan:
            rates = {signature[2] for signature in signatures}
            pixel_formats = {signature[3] for signature in signatures}
            if len(rates) != 1 or len(pixel_formats) != 1:
                raise SystemExit(
                    f"padded sequence rate/pixel mismatch: {sorted(signatures)}"
                )
            frame_rate = next(iter(rates))
            pixel_format = next(iter(pixel_formats))
            for row, signature in zip(manifest["clips"], source_signatures):
                source_width, source_height, _, _ = signature
                plan_row = plan_rows.get(row["dgm_name"], {})
                if source_width == width and source_height == height:
                    continue
                if (
                    not plan_row.get("pad_to_native")
                    or source_width > width
                    or source_height > height
                ):
                    raise SystemExit(
                        f"unverified padded source for {row['dgm_name']}: "
                        f"{source_width}x{source_height} -> {width}x{height}"
                    )
                pad_x = int(plan_row.get("pad_x", 0))
                pad_y = int(plan_row.get("pad_y", 0))
                if (
                    pad_x < 0
                    or pad_y < 0
                    or pad_x + source_width > width
                    or pad_y + source_height > height
                ):
                    raise SystemExit(
                        f"invalid pad placement for {row['dgm_name']}: "
                        f"{pad_x},{pad_y}"
                    )
        else:
            if len(signatures) != 1:
                raise SystemExit(f"source signature mismatch: {sorted(signatures)}")
            source_width, source_height, frame_rate, pixel_format = next(
                iter(signatures)
            )
            if source_width != width or source_height != height:
                raise SystemExit(
                    f"native dimension mismatch: source={source_width}x{source_height}, "
                    f"manifest={width}x{height}"
                )
    if width != expected["width"] or height != expected["height"]:
        raise SystemExit(
            f"native dimension mismatch: source={width}x{height}, "
            f"manifest={expected['width']}x{expected['height']}"
        )
    if frame_rate != manifest["native_frame_rate"]:
        raise SystemExit(
            f"native frame-rate mismatch: source={frame_rate}, "
            f"manifest={manifest['native_frame_rate']}"
        )

    video_only = work_dir / f"{event}__video_only.mp4"
    render_duration_ms = int(
        manifest.get("render_duration_ms", manifest["video_duration_ms"])
    )
    target_frame_count = int(
        manifest.get(
            "render_frame_count",
            round(render_duration_ms * int(str(frame_rate).split("/", 1)[0]) / 1000),
        )
    )
    if target_frame_count <= 0:
        raise SystemExit("render_frame_count must be positive")
    extension_policy = str(
        plan.get("extension_policy")
        or manifest.get("video_extension_policy", "none")
    )
    if composition_model == "timed_full_frame_layers":
        if plan.get("model") != "timed_full_frame_layers":
            raise SystemExit("timed composition has no verified composition plan")
        clip_by_name = {
            row["dgm_name"]: (Path(row["path"]).resolve(), clip_probes[index])
            for index, row in enumerate(manifest["clips"])
        }
        plan_clips = plan.get("clips", [])
        backgrounds = sorted(
            [row for row in plan_clips if row.get("role") == "background"],
            key=lambda row: int(row["start_ms"]),
        )
        loop_backgrounds = [
            row for row in plan_clips if row.get("role") == "loop_background"
        ]
        overlays = sorted(
            [row for row in plan_clips if row.get("role") == "screen_overlay"],
            key=lambda row: int(row["start_ms"]),
        )
        loop_overlays = sorted(
            [
                row
                for row in plan_clips
                if row.get("role") == "loop_screen_overlay"
            ],
            key=lambda row: int(row["start_ms"]),
        )
        if not backgrounds or len(loop_backgrounds) > 1:
            raise SystemExit("invalid timed composition background plan")
        loop_background = loop_backgrounds[0] if loop_backgrounds else None
        video_inputs: list[str] = []
        video_filters: list[str] = []
        background_labels: list[str] = []
        boundaries = [
            *(int(row["start_ms"]) for row in backgrounds[1:]),
            *(
                [int(loop_background["start_ms"])]
                if loop_background
                else [render_duration_ms]
            ),
        ]
        input_index = 0
        first_background_start_ms = int(backgrounds[0]["start_ms"])
        if first_background_start_ms > 0:
            video_filters.append(
                f"color=c=black:s={width}x{height}:r={frame_rate}:"
                f"d={first_background_start_ms / 1000:.6f}[bgpre]"
            )
            background_labels.append("[bgpre]")
        for row, end_ms in zip(backgrounds, boundaries):
            start_ms = int(row["start_ms"])
            duration_ms = end_ms - start_ms
            if duration_ms <= 0:
                raise SystemExit("background start times are not increasing")
            clip_path, clip_probe = clip_by_name[row["dgm_name"]]
            video_inputs.extend(["-i", str(clip_path)])
            label = f"bg{len(background_labels)}"
            source_duration_ms = round(float(clip_probe["format"]["duration"]) * 1000)
            if duration_ms > source_duration_ms + 34:
                if extension_policy != "hold_last_frame":
                    raise SystemExit(
                        "timed composition background ends before its planned "
                        f"interval: {row['dgm_name']}"
                    )
                hold_duration_sec = (duration_ms - source_duration_ms) / 1000
                video_filters.append(
                    f"[{input_index}:v:0]"
                    f"tpad=stop_mode=clone:stop_duration={hold_duration_sec:.6f},"
                    f"trim=duration={duration_ms / 1000:.6f},"
                    f"setpts=PTS-STARTPTS[{label}]"
                )
            else:
                video_filters.append(
                    f"[{input_index}:v:0]trim=duration={duration_ms / 1000:.6f},"
                    f"setpts=PTS-STARTPTS[{label}]"
                )
            background_labels.append(f"[{label}]")
            input_index += 1
        if loop_background:
            start_ms = int(loop_background["start_ms"])
            duration_ms = render_duration_ms - start_ms
            if duration_ms <= 0:
                raise SystemExit("loop background begins after render end")
            clip_path, _ = clip_by_name[loop_background["dgm_name"]]
            video_inputs.extend(["-stream_loop", "-1", "-i", str(clip_path)])
            label = f"bg{len(background_labels)}"
            video_filters.append(
                f"[{input_index}:v:0]trim=duration={duration_ms / 1000:.6f},"
                f"setpts=PTS-STARTPTS[{label}]"
            )
            background_labels.append(f"[{label}]")
            input_index += 1
        video_filters.append(
            "".join(background_labels)
            + f"concat=n={len(background_labels)}:v=1:a=0[base0]"
        )
        current_label = "base0"
        for overlay_index, row in enumerate(overlays):
            start_ms = int(row["start_ms"])
            clip_path, clip_probe = clip_by_name[row["dgm_name"]]
            duration_ms = resolve_non_loop_overlay_duration_ms(
                row, clip_probe, render_duration_ms
            )
            duration_sec = duration_ms / 1000
            blend_mode = str(row.get("blend_mode", "screen"))
            video_inputs.extend(["-i", str(clip_path)])
            overlay_label = f"overlay{overlay_index}"
            background_label = f"base_rgb{overlay_index}"
            output_label = f"base{overlay_index + 1}"
            base_pixel_format = (
                "rgba" if blend_mode in {"black_key", "opaque"} else "gbrp"
            )
            video_filters.append(
                f"[{current_label}]format={base_pixel_format}[{background_label}]"
            )
            video_filters.append(
                f"[{input_index}:v:0]trim=duration={duration_sec:.6f},"
                + (
                    f"scale={width}:{height}:flags=lanczos,"
                    if row.get("scale_to_native")
                    else ""
                )
                + (
                    "format=rgba,colorkey=0x000000:"
                    f"{float(row.get('black_similarity', 0.08)):.4f}:"
                    f"{float(row.get('black_blend', 0.12)):.4f},"
                    if blend_mode == "black_key"
                    else (
                        "format=rgba,"
                        if blend_mode == "opaque"
                        else "format=gbrp,"
                    )
                )
                + f"setpts=PTS-STARTPTS+{start_ms / 1000:.6f}/TB"
                f"[{overlay_label}]"
            )
            if blend_mode in {"black_key", "opaque"}:
                video_filters.append(
                    f"[{background_label}][{overlay_label}]"
                    "overlay=0:0:eof_action=pass:repeatlast=0:shortest=0:format=auto:"
                    f"enable='between(t,{start_ms / 1000:.6f},"
                    f"{start_ms / 1000 + duration_sec:.6f})'"
                    f"[{output_label}]"
                )
            elif blend_mode == "screen":
                video_filters.append(
                    f"[{background_label}][{overlay_label}]"
                    "blend=all_mode=screen:"
                    f"enable='between(t,{start_ms / 1000:.6f},"
                    f"{start_ms / 1000 + duration_sec:.6f})'"
                    f"[{output_label}]"
                )
            else:
                raise SystemExit(f"unsupported overlay blend mode: {blend_mode}")
            current_label = output_label
            input_index += 1
        for overlay_index, row in enumerate(
            loop_overlays, start=len(overlays)
        ):
            start_ms = int(row["start_ms"])
            duration_sec = (render_duration_ms - start_ms) / 1000
            if duration_sec <= 0:
                raise SystemExit("loop screen overlay begins after render end")
            clip_path, _ = clip_by_name[row["dgm_name"]]
            blend_mode = str(row.get("blend_mode", "screen"))
            video_inputs.extend(["-stream_loop", "-1", "-i", str(clip_path)])
            overlay_label = f"overlay{overlay_index}"
            background_label = f"base_rgb{overlay_index}"
            output_label = f"base{overlay_index + 1}"
            base_pixel_format = (
                "rgba" if blend_mode in {"black_key", "opaque"} else "gbrp"
            )
            video_filters.append(
                f"[{current_label}]format={base_pixel_format}[{background_label}]"
            )
            video_filters.append(
                f"[{input_index}:v:0]trim=duration={duration_sec:.6f},"
                + (
                    f"scale={width}:{height}:flags=lanczos,"
                    if row.get("scale_to_native")
                    else ""
                )
                + (
                    "format=rgba,colorkey=0x000000:"
                    f"{float(row.get('black_similarity', 0.08)):.4f}:"
                    f"{float(row.get('black_blend', 0.12)):.4f},"
                    if blend_mode == "black_key"
                    else (
                        "format=rgba,"
                        if blend_mode == "opaque"
                        else "format=gbrp,"
                    )
                )
                + f"setpts=PTS-STARTPTS+{start_ms / 1000:.6f}/TB"
                f"[{overlay_label}]"
            )
            if blend_mode in {"black_key", "opaque"}:
                video_filters.append(
                    f"[{background_label}][{overlay_label}]"
                    "overlay=0:0:eof_action=pass:repeatlast=0:shortest=0:format=auto:"
                    f"enable='gte(t,{start_ms / 1000:.6f})'"
                    f"[{output_label}]"
                )
            elif blend_mode == "screen":
                video_filters.append(
                    f"[{background_label}][{overlay_label}]"
                    "blend=all_mode=screen:"
                    f"enable='gte(t,{start_ms / 1000:.6f})'"
                    f"[{output_label}]"
                )
            else:
                raise SystemExit(f"unsupported overlay blend mode: {blend_mode}")
            current_label = output_label
            input_index += 1
        video_filters.append(
            f"[{current_label}]fps={frame_rate},"
            "tpad=stop_mode=clone:stop=2,"
            f"trim=end_frame={target_frame_count},setpts=PTS-STARTPTS,"
            f"format={pixel_format}[v]"
        )
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                *video_inputs,
                "-filter_complex",
                ";".join(video_filters),
                "-map",
                "[v]",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                str(pixel_format),
                "-frames:v",
                str(target_frame_count),
                "-movflags",
                "+faststart",
                str(video_only),
            ]
        )
    elif composition_model == "linear_full_frame_sequence":
        base_video_only = work_dir / f"{event}__base_video_only.mp4"
        video_inputs: list[str] = []
        video_labels: list[str] = []
        video_filters: list[str] = []
        for index, (clip, signature, clip_row) in enumerate(
            zip(clips, source_signatures, manifest["clips"])
        ):
            video_inputs.extend(["-i", str(clip)])
            source_width, source_height, _, _ = signature
            plan_row = plan_rows.get(clip_row["dgm_name"], {})
            label = f"linear{index}"
            transforms = ["setpts=PTS-STARTPTS"]
            if source_width != width or source_height != height:
                if not plan_row.get("pad_to_native"):
                    raise SystemExit(
                        f"linear source needs an explicit pad plan: {clip_row['dgm_name']}"
                    )
                transforms.append(
                    f"pad={width}:{height}:"
                    f"{int(plan_row.get('pad_x', 0))}:"
                    f"{int(plan_row.get('pad_y', 0))}:black"
                )
            transforms.extend([f"fps={frame_rate}", f"format={pixel_format}"])
            video_filters.append(
                f"[{index}:v:0]" + ",".join(transforms) + f"[{label}]"
            )
            video_labels.append(f"[{label}]")
        video_filters.append(
            "".join(video_labels) + f"concat=n={len(clips)}:v=1:a=0[v]"
        )
        run(
            [
                args.ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                *video_inputs,
                "-filter_complex",
                ";".join(video_filters),
                "-map",
                "[v]",
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "14",
                "-pix_fmt",
                str(pixel_format),
                "-movflags",
                "+faststart",
                str(base_video_only),
            ]
        )
        extension_ms = max(
            0, render_duration_ms - int(manifest["video_duration_ms"])
        )
        if extension_ms == 0:
            run(
                [
                    args.ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(base_video_only),
                    "-map",
                    "0:v:0",
                    "-c:v",
                    "copy",
                    str(video_only),
                ]
            )
        elif extension_policy == "loop_last_clip":
            extension_path = work_dir / f"{event}__loop_extension.mp4"
            base_frame_count = audited_video_frame_count(base_video_only, args.ffprobe)
            extension_frames = target_frame_count - base_frame_count
            if extension_frames <= 0:
                raise SystemExit(
                    "loop extension has no positive CFR frame budget: "
                    f"target={target_frame_count}, base={base_frame_count}"
                )
            run(
                [
                    args.ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(clips[-1]),
                    "-an",
                    "-frames:v",
                    str(extension_frames),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "14",
                    "-pix_fmt",
                    str(pixel_format),
                    str(extension_path),
                ]
            )
            run(
                [
                    args.ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(base_video_only),
                    "-i",
                    str(extension_path),
                    "-filter_complex",
                    "[0:v:0][1:v:0]concat=n=2:v=1:a=0[v]",
                    "-map",
                    "[v]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "14",
                    "-pix_fmt",
                    str(pixel_format),
                    "-frames:v",
                    str(target_frame_count),
                    str(video_only),
                ]
            )
        elif extension_policy == "hold_last_frame":
            extension_sec = extension_ms / 1000.0
            run(
                [
                    args.ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(base_video_only),
                    "-vf",
                    f"tpad=stop_mode=clone:stop_duration={extension_sec:.6f}",
                    "-an",
                    "-t",
                    f"{render_duration_ms / 1000.0:.6f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "14",
                    "-pix_fmt",
                    str(pixel_format),
                    "-frames:v",
                    str(target_frame_count),
                    str(video_only),
                ]
            )
        elif extension_policy == "black_tail":
            extension_sec = extension_ms / 1000.0
            run(
                [
                    args.ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(base_video_only),
                    "-vf",
                    f"tpad=stop_mode=add:stop_duration={extension_sec:.6f}:color=black",
                    "-an",
                    "-t",
                    f"{render_duration_ms / 1000.0:.6f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "14",
                    "-pix_fmt",
                    str(pixel_format),
                    "-frames:v",
                    str(target_frame_count),
                    str(video_only),
                ]
            )
        else:
            raise SystemExit(
                f"unsupported video extension policy: {extension_policy} "
                f"for {extension_ms} ms"
            )
    else:
        raise SystemExit(f"unsupported video composition model: {composition_model}")

    if args.clean_visual_only:
        clean_probe = production_probe(video_only, args.ffprobe)
        video_streams = [
            row
            for row in clean_probe.get("streams", [])
            if row.get("codec_type") == "video"
        ]
        audio_streams = [
            row
            for row in clean_probe.get("streams", [])
            if row.get("codec_type") == "audio"
        ]
        subtitle_streams = [
            row
            for row in clean_probe.get("streams", [])
            if row.get("codec_type") == "subtitle"
        ]
        qa_errors: list[str] = []
        if len(video_streams) != 1:
            qa_errors.append(
                f"expected exactly one video stream, found {len(video_streams)}"
            )
        if audio_streams:
            qa_errors.append(
                f"clean visual contains {len(audio_streams)} forbidden audio stream(s)"
            )
        if subtitle_streams:
            qa_errors.append(
                "clean visual contains "
                f"{len(subtitle_streams)} forbidden subtitle stream(s)"
            )
        clean_video = video_streams[0] if len(video_streams) == 1 else {}
        if clean_video.get("codec_name") != "h264":
            qa_errors.append("clean visual video codec is not H.264")
        if (
            clean_video.get("width") != width
            or clean_video.get("height") != height
        ):
            qa_errors.append("clean visual changed native dimensions")
        if clean_video.get("r_frame_rate") != frame_rate:
            qa_errors.append("clean visual changed native frame rate")
        try:
            stream_duration_ms = round(float(clean_video["duration"]) * 1000)
            container_duration_ms = round(
                float(clean_probe["format"]["duration"]) * 1000
            )
            start_ms = round(float(clean_video["start_time"]) * 1000)
        except (KeyError, TypeError, ValueError):
            qa_errors.append("clean visual lacks auditable start/duration metadata")
        else:
            if start_ms != 0:
                qa_errors.append(f"clean visual starts at {start_ms} ms")
            if not duration_metadata_matches_cfr_grid(
                stream_duration_ms, render_duration_ms
            ):
                qa_errors.append(
                    "clean visual stream duration differs from the CFR grid by "
                    "more than the 1 ms metadata rounding allowance: "
                    f"actual={stream_duration_ms} ms, expected={render_duration_ms} ms"
                )
            if not duration_metadata_matches_cfr_grid(
                container_duration_ms, render_duration_ms
            ):
                qa_errors.append(
                    "clean visual container duration differs from the CFR grid by "
                    "more than the 1 ms metadata rounding allowance: "
                    f"actual={container_duration_ms} ms, expected={render_duration_ms} ms"
                )
        if qa_errors:
            raise SystemExit("clean visual QA failed: " + "; ".join(qa_errors))

        try:
            video_timeline = probe_video_timeline(
                video_only,
                args.ffprobe,
                expected_duration_ms=render_duration_ms,
                expected_frame_rate=str(frame_rate),
                label=f"{event} clean visual",
            )
        except RuntimeError as error:
            raise SystemExit(f"clean visual timeline QA failed: {error}") from error
        output_video_packet_sha256 = video_packet_hash(video_only, args.ffmpeg)
        output_sha256 = production_file_sha256(video_only)
        current_manifest_bytes_sha256 = production_file_sha256(manifest_path)
        current_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if current_manifest_bytes_sha256 != source_manifest_sha256:
            raise SystemExit("source event manifest changed during clean render")
        if composition_contract_sha256(current_manifest) != source_composition_sha256:
            raise SystemExit("source composition contract changed during clean render")
        try:
            verify_clip_source_hashes_unchanged(clip_source_snapshots)
        except RuntimeError as error:
            raise SystemExit(str(error)) from error
        assert source_composition_projection is not None

        report = {
            "schema": "magireco-clean-visual-render-v1",
            "status": "passed",
            "publishable": True,
            "event": event,
            "source_manifest": {
                "path": str(manifest_path),
                "sha256": source_manifest_sha256,
                "locator": f"source event manifest for {event} clean visual",
            },
            "source_composition_contract_sha256": source_composition_sha256,
            "source_composition_contract": source_composition_projection,
            "source_clips": clip_source_snapshots,
            "output": str(published_clean_visual_path),
            "output_sha256": output_sha256,
            "duration_ms": render_duration_ms,
            "output_video_packet_sha256": output_video_packet_sha256,
            "output_video_timeline_sha256": video_timeline["timeline_sha256"],
            "video_encoding_signature": list(
                video_encoding_signature(clean_video)
            ),
            "output_video_timeline": video_timeline,
            "qa": {
                "status": "passed",
                "errors": [],
                "checks": {
                    "explicit_composition_plan": True,
                    "native_dimensions": True,
                    "native_frame_rate": True,
                    "h264_video": True,
                    "no_audio_stream": True,
                    "no_subtitle_stream": True,
                    "exact_duration": True,
                    "exact_video_presentation_timeline": True,
                    "source_manifest_unchanged_during_render": True,
                    "source_clip_hashes_bound": True,
                    "source_clips_unchanged_during_render": True,
                },
            },
        }
        clean_visual_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(video_only, clean_visual_path)
        output_manifest_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_reference = {
            "path": str(published_output_manifest_path),
            "sha256": production_file_sha256(output_manifest_path),
            "locator": f"passed clean-visual render QA for {event}",
        }
        bound_manifest = json.loads(
            json.dumps(manifest, ensure_ascii=False)
        )
        bound_manifest["clean_visual_master"] = {
            "artifact": {
                "path": str(published_clean_visual_path),
                "sha256": output_sha256,
                "locator": f"native clean visual artifact for {event}",
            },
            "render_manifest": report_reference,
        }
        if composition_contract_sha256(bound_manifest) != source_composition_sha256:
            raise SystemExit("clean_visual_master binding changed composition contract")
        bound_manifest_path.write_text(
            json.dumps(bound_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        # Work products are never part of a READY release.  The clean-visual
        # transaction publishes only the three evidence-bound artifacts plus
        # its marker, even if --keep-work is used by a legacy rendering mode.
        shutil.rmtree(work_dir, ignore_errors=True)
        ready = {
            "schema": CLEAN_VISUAL_READY_SCHEMA,
            "status": "READY",
            "event": event,
            "source_manifest_sha256": source_manifest_sha256,
            "source_composition_contract_sha256": source_composition_sha256,
            "artifacts": [
                {
                    "role": "clean_visual",
                    "relative_path": str(
                        clean_visual_path.relative_to(out_root)
                    ).replace("\\", "/"),
                    "sha256": production_file_sha256(clean_visual_path),
                },
                {
                    "role": "render_manifest",
                    "relative_path": str(
                        output_manifest_path.relative_to(out_root)
                    ).replace("\\", "/"),
                    "sha256": production_file_sha256(output_manifest_path),
                },
                {
                    "role": "bound_event_manifest",
                    "relative_path": str(
                        bound_manifest_path.relative_to(out_root)
                    ).replace("\\", "/"),
                    "sha256": production_file_sha256(bound_manifest_path),
                },
            ],
        }
        ready_temp = out_root / "READY.json.tmp"
        ready_path = out_root / "READY.json"
        ready_temp.write_text(
            json.dumps(ready, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(ready_temp, ready_path)
        try:
            _promote_clean_visual_release(
                staging_root=out_root,
                published_root=published_out_root,
                event=event,
                overwrite=args.overwrite,
            )
        except (OSError, RuntimeError) as error:
            raise SystemExit(f"clean-visual publication failed: {error}") from error
        result = {
            **report,
            "render_manifest": {
                "path": str(published_output_manifest_path),
                "sha256": production_file_sha256(
                    published_output_manifest_path
                ),
                "locator": f"passed clean-visual render QA for {event}",
            },
            "bound_event_manifest": {
                "path": str(published_bound_manifest_path),
                "sha256": production_file_sha256(
                    published_bound_manifest_path
                ),
                "locator": f"event manifest bound to clean visual for {event}",
            },
            "ready_marker": {
                "path": str(published_out_root / "READY.json"),
                "sha256": production_file_sha256(
                    published_out_root / "READY.json"
                ),
                "schema": CLEAN_VISUAL_READY_SCHEMA,
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    audio = manifest["audio"]
    audio_inputs: list[str] = []
    audio_filters: list[str] = []
    audio_labels: list[str] = []
    for index, row in enumerate(audio, 1):
        audio_inputs.extend(["-i", str(Path(row["path"]).resolve())])
        label = f"a{index}"
        audio_filters.append(
            f"[{index}:a:0]adelay={int(row['start_ms'])}:all=1,"
            f"aresample=48000[{label}]"
        )
        audio_labels.append(f"[{label}]")
    video_duration_sec = render_duration_ms / 1000.0
    audio_filters.append(
        "".join(audio_labels)
        + f"amix=inputs={len(audio)}:duration=longest:normalize=0,"
        + f"alimiter=limit=0.95,apad=whole_dur={video_duration_sec:.6f}[mix]"
    )
    run(
        [
            args.ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_only),
            *audio_inputs,
            "-filter_complex",
            ";".join(audio_filters),
            "-map",
            "0:v:0",
            "-map",
            "[mix]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-t",
            f"{video_duration_sec:.6f}",
            "-movflags",
            "+faststart",
            str(without_path),
        ]
    )

    edition_outputs: dict[str, dict] = {
        "none": {
            "language": "none",
            "video": str(without_path.resolve()),
            "subtitles": "",
            "video_method": "rendered_composition",
        }
    }
    plan_tracks = edition_plan["tracks"]
    for language in requested:
        if language == "none":
            continue
        track = plan_tracks[language]
        cues = track["cues"]
        font = track["font"]
        with_path, subtitle_path = subtitle_outputs[language]
        write_srt(subtitle_path, cues)
        staged_font = ""
        font_stage_method = ""
        if not cues:
            video_method = link_or_copy(
                without_path, with_path, overwrite=args.overwrite
            )
        else:
            if not isinstance(font, dict):
                raise RuntimeError(f"{event} {language} has cues without a font binding")
            source_font = Path(str(font["path"])).resolve()
            staged_font_path = (
                out_root
                / "fonts"
                / language
                / (str(font["sha256"])[:16] + source_font.suffix.lower())
            )
            font_stage_method = link_or_copy(
                source_font, staged_font_path, overwrite=args.overwrite
            )
            staged_font = str(staged_font_path.resolve())
            with_path.parent.mkdir(parents=True, exist_ok=True)
            relative_subtitle = subtitle_path.relative_to(out_root).as_posix()
            relative_fonts = staged_font_path.parent.relative_to(out_root).as_posix()
            subtitle_filter = (
                f"subtitles=filename='{relative_subtitle}':"
                f"fontsdir='{relative_fonts}':"
                f"force_style='FontName={font['family']},FontSize=16,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "BorderStyle=1,Outline=1,Shadow=0,MarginV=12,Alignment=2'"
            )
            run(
                [
                    args.ffmpeg,
                    "-y" if args.overwrite else "-n",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(without_path),
                    "-vf",
                    subtitle_filter,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "14",
                    "-pix_fmt",
                    str(pixel_format),
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(with_path),
                ],
                cwd=out_root,
            )
            video_method = "rendered_video_audio_copy"
        edition_outputs[language] = {
            "language": language,
            "video": str(with_path.resolve()),
            "subtitles": str(subtitle_path.resolve()),
            "video_method": video_method,
            "font": font,
            "staged_font": staged_font,
            "font_stage_method": font_stage_method,
        }

    edition_probes = {
        language: probe(Path(row["video"]), args.ffprobe)
        for language, row in edition_outputs.items()
    }
    for label, item in edition_probes.items():
        video = next(
            stream
            for stream in item["streams"]
            if stream.get("codec_type") == "video"
        )
        audio_stream = next(
            stream
            for stream in item["streams"]
            if stream.get("codec_type") == "audio"
        )
        if video.get("width") != width or video.get("height") != height:
            raise SystemExit(f"{label} edition output was resized")
        if video.get("r_frame_rate") != frame_rate:
            raise SystemExit(f"{label} edition output frame rate changed")
        if audio_stream.get("sample_rate") != "48000":
            raise SystemExit(f"{label} edition output audio is not 48 kHz")
        actual_duration_ms = round(float(item["format"]["duration"]) * 1000)
        if abs(actual_duration_ms - render_duration_ms) > 50:
            raise SystemExit(
                f"{label} edition duration mismatch: actual={actual_duration_ms} ms, "
                f"expected={render_duration_ms} ms"
            )

    edition_audio_hashes = {
        language: audio_hash(Path(row["video"]), args.ffmpeg)
        for language, row in edition_outputs.items()
    }
    base_audio_hash = edition_audio_hashes["none"]
    mismatched_audio = {
        language: value
        for language, value in edition_audio_hashes.items()
        if value != base_audio_hash
    }
    if mismatched_audio:
        raise SystemExit(
            "subtitle edition audio differs from none edition: "
            + json.dumps(mismatched_audio, ensure_ascii=False)
        )
    for language, value in edition_audio_hashes.items():
        edition_outputs[language]["audio_sha256"] = value
        edition_outputs[language]["video_sha256"] = sha256(
            Path(edition_outputs[language]["video"])
        )
        subtitle_value = str(edition_outputs[language].get("subtitles", ""))
        edition_outputs[language]["subtitle_sha256"] = (
            sha256(Path(subtitle_value)) if subtitle_value else ""
        )
        edition_outputs[language]["probe"] = edition_probes[language]

    subtitle_media_reused_by_edition = {
        language: row["video_method"] in {"hardlink", "copy"}
        for language, row in edition_outputs.items()
        if language != "none"
    }
    output = {
        "schema": "magireco-event-render-editions-v2",
        "legacy_schema_compatible": "ja" in edition_outputs,
        "source_manifest": str(manifest_path),
        "event": event,
        "render_duration_ms": render_duration_ms,
        "video_extension_policy": extension_policy,
        "subtitle_media_reused": subtitle_media_reused_by_edition.get(
            "ja", False
        ),
        "subtitle_media_reused_by_edition": subtitle_media_reused_by_edition,
        "without_subtitles": str(without_path),
        "with_subtitles": edition_outputs.get("ja", {}).get("video", ""),
        "subtitles": edition_outputs.get("ja", {}).get("subtitles", ""),
        "editions": edition_outputs,
        "edition_plan": edition_plan,
        "shared_audio_sha256": base_audio_hash,
        "sha256": {
            "without_subtitles": sha256(without_path),
            "with_subtitles": edition_outputs.get("ja", {}).get(
                "video_sha256", ""
            ),
            "subtitles": edition_outputs.get("ja", {}).get(
                "subtitle_sha256", ""
            ),
        },
        "probe_without_subtitles": edition_probes["none"],
        "probe_with_subtitles": edition_probes.get("ja", {}),
    }
    output_manifest_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not args.keep_work:
        shutil.rmtree(work_dir)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    transaction_cleanup: list[Path] = []
    try:
        return _main(parse_args(), transaction_cleanup)
    finally:
        for path in reversed(transaction_cleanup):
            shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
