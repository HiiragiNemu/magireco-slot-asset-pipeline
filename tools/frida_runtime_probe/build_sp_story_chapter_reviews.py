#!/usr/bin/env python3
"""Build auditable no-BGM Chinese review chapters for reviewed story families.

This is deliberately a review-candidate lane, not a release promotion lane.
It rebuilds or revalidates every clean visual against a hash-bound v20 manifest,
reconstructs voice/SE from the v20 audio rows while rejecting known BGM and gold-band
requests, concatenates continuous PCM, burns only voice-bound Chinese cues,
and leaves all human/publication flags false.  Both verified linear full-frame
events and authored timed full-frame compositions are supported.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_audio_base_masters as audio_gate
    from .build_independent_scene_release import (
        build_event_pcm,
        concat_binary,
        file_sha256,
        frame_count,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        stream_bit_rate,
        subtitle_filter,
        volume_audit,
        write_json,
        write_srt,
    )
    from .output_path_contract import (
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )
except ImportError:  # direct script execution
    import build_audio_base_masters as audio_gate  # type: ignore
    from build_independent_scene_release import (  # type: ignore
        build_event_pcm,
        concat_binary,
        file_sha256,
        frame_count,
        media_streams,
        packet_hash,
        parse_srt,
        probe,
        run,
        stream_bit_rate,
        subtitle_filter,
        volume_audit,
        write_json,
        write_srt,
    )
    from output_path_contract import (  # type: ignore
        ensure_resolved_containment,
        resolve_output_child,
        validate_output_identifier,
    )


BATCH_SCHEMA = "magireco-sp-story-chapter-review-batch-v1"
MANIFEST_SCHEMA = "magireco-no-bgm-zh-chapter-review-v1"
QA_SCHEMA = "magireco-no-bgm-zh-chapter-review-qa-v1"
READY_SCHEMA = "magireco-chapter-review-ready-v1"
TRANSLATION_SCHEMA = "magireco-sp-story-zh-dialogue-map-v1"
GENERIC_TRANSLATION_SCHEMA = "magireco-reviewed-story-zh-dialogue-map-v1"
FORBIDDEN_AUDIO_REQUESTS = {"835", "836", "1681"}
DEFAULT_SP_FAMILIES = {"ac7114", "ac7115", "ac7116"}
SUPPORTED_DIMENSIONS = {(416, 232), (512, 288), (512, 416)}
SUPPORTED_COMPOSITION_MODELS = {
    "linear_full_frame_sequence",
    "timed_full_frame_layers",
}
SUPPORTED_EXTENSION_POLICIES = {
    "none",
    "hold_last_frame",
    "loop_last_clip",
    "composition_plan_loops",
    "black_tail",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def snapshot(path: Path, *, label: str) -> dict[str, str]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    return {"label": label, "path": str(path), "sha256": file_sha256(path)}


def rehash(rows: Sequence[Mapping[str, str]]) -> None:
    for row in rows:
        path = Path(row["path"])
        if not path.is_file() or file_sha256(path) != row["sha256"]:
            raise RuntimeError(f"source changed during build: {row['label']}: {path}")


def validate_audio_absence_evidence(
    manifest: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Revalidate all three current catalogs behind an exact no-audio claim."""

    event = str(manifest.get("event", ""))
    evidence = manifest.get("audio_absence_evidence")
    rows = evidence.get("source_snapshots") if isinstance(evidence, Mapping) else None
    expected_labels = {
        "direct_parent_audio_catalog",
        "child_z2d_audio_catalog",
        "subtitle_timeline_catalog",
    }
    if (
        not isinstance(rows, list)
        or len(rows) != len(expected_labels)
        or any(
            not isinstance(row, Mapping)
            or set(row) != {"label", "path", "sha256"}
            for row in rows
        )
        or {str(row["label"]) for row in rows} != expected_labels
    ):
        raise ValueError(f"{event} audio absence source snapshots differ")
    resolved: list[dict[str, str]] = []
    for row in rows:
        label = str(row["label"])
        path = Path(str(row["path"]))
        expected_sha256 = str(row["sha256"]).upper()
        if (
            not path.is_absolute()
            or len(expected_sha256) != 64
            or any(value not in "0123456789ABCDEF" for value in expected_sha256)
        ):
            raise ValueError(f"{event} audio absence source snapshot differs")
        current = snapshot(path, label=label)
        if current["sha256"] != expected_sha256:
            raise ValueError(f"{event} audio absence source SHA-256 differs")
        resolved.append(current)
    return resolved


def validate_reusable_clean_visual(
    *, event: str, prepared_path: Path, clean_visual: Path, clean_report: Path
) -> None:
    if not clean_visual.is_file() or not clean_report.is_file():
        raise RuntimeError(f"{event} existing clean-visual release is incomplete")
    report = read_json(clean_report)
    source_manifest = report.get("source_manifest")
    if (
        report.get("event") != event
        or report.get("status") != "passed"
        or not isinstance(source_manifest, Mapping)
    ):
        raise RuntimeError(f"{event} existing clean-visual report is not reusable")
    try:
        bound_path = Path(str(source_manifest["path"])).resolve()
        bound_sha256 = str(source_manifest["sha256"]).upper()
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"{event} existing clean-visual report lacks source-manifest provenance"
        ) from error
    if bound_path != prepared_path.resolve() or bound_sha256 != file_sha256(
        prepared_path
    ):
        raise RuntimeError(
            f"{event} existing clean visual is stale for the prepared manifest; "
            "rerun with --overwrite"
        )
    if (
        Path(str(report.get("output", ""))).resolve() != clean_visual.resolve()
        or str(report.get("output_sha256", "")).upper() != file_sha256(clean_visual)
    ):
        raise RuntimeError(f"{event} existing clean-visual artifact hash differs")


def load_translation_map(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    value = read_json(path)
    if value.get("schema") not in {TRANSLATION_SCHEMA, GENERIC_TRANSLATION_SCHEMA}:
        raise ValueError("unsupported translation-map schema")
    rows = value.get("translations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("translation map must contain rows")
    result: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != {"ja", "zh", "status"}:
            raise ValueError(f"translation row {index} fields differ")
        ja = str(row["ja"]).strip()
        zh = str(row["zh"]).strip()
        if not ja or not zh or row["status"] != "machine_draft_pending_owner":
            raise ValueError(f"translation row {index} is invalid")
        if ja in result:
            raise ValueError(f"duplicate Japanese translation key: {ja!r}")
        result[ja] = zh
    return result, snapshot(path, label="Chinese dialogue translation map")


def generated_linear_plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    clips = manifest.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError(f"{manifest.get('event')} implicit plan has no full-frame clips")
    if manifest.get("video_composition_model") != "linear_full_frame_sequence":
        raise ValueError(f"{manifest.get('event')} implicit model is not linear")
    ordered = sorted(
        clips,
        key=lambda row: (
            int(row.get("event_start_ms", -1)) if isinstance(row, Mapping) else -1,
            int(row.get("order", -1)) if isinstance(row, Mapping) else -1,
        ),
    )
    projected: list[dict[str, Any]] = []
    previous_start = -1
    names: set[str] = set()
    for index, clip in enumerate(ordered):
        if not isinstance(clip, Mapping):
            raise ValueError(f"{manifest.get('event')} implicit clip {index} is invalid")
        start_ms = int(clip.get("event_start_ms", -1))
        name = str(clip.get("dgm_name", ""))
        if (index == 0 and start_ms != 0) or start_ms <= previous_start or not name:
            raise ValueError(f"{manifest.get('event')} implicit clip order is invalid")
        if name in names:
            raise ValueError(f"{manifest.get('event')} implicit clip name is duplicated")
        names.add(name)
        previous_start = start_ms
        projected.append({"dgm_name": name, "role": "background", "start_ms": start_ms})
    return {
        "schema": "magireco-video-composition-v1",
        "event": manifest["event"],
        "model": "linear_full_frame_sequence",
        "duration_ms": int(manifest["timeline_content_end_ms"]),
        "extension_policy": manifest["video_extension_policy"],
        "native_dimensions": manifest["native_dimensions"],
        "evidence": (
            "deterministic explicit projection of the v20 ordered full-frame clip "
            "timeline; clip identities, starts, exact intervals, native dimensions, "
            "extension policy, and CFR presentation grid are bound by the copied "
            "v20 production manifest and source SHA-256"
        ),
        "clips": projected,
    }


def prepare_manifest(
    source_path: Path,
    *,
    plan_dir: Path,
    manifest_dir: Path,
    permitted_forbidden_audio_request_ids: set[str] | None = None,
) -> tuple[dict[str, Any], Path, list[dict[str, str]]]:
    source_path = source_path.resolve()
    manifest = read_json(source_path)
    event = validate_output_identifier(manifest.get("event"), label="event")
    gates = manifest.get("quality_gates")
    if not isinstance(gates, Mapping) or not all(
        gates.get(field) is True
        for field in ("ready", "render_ready", "audio_timeline_ready", "composition_resolved")
    ):
        raise ValueError(f"{event} is not v20 technical-ready")
    if manifest.get("classification") not in {
        "native_full_frame_only",
        "verified_native_composite",
    }:
        raise ValueError(f"{event} is not a clean-story visual classification")
    dimensions = manifest.get("native_dimensions")
    if not isinstance(dimensions, Mapping):
        raise ValueError(f"{event} lacks native dimensions")
    dimension_tuple = (int(dimensions.get("width", 0)), int(dimensions.get("height", 0)))
    if manifest.get("native_frame_rate") != "30/1" or dimension_tuple not in SUPPORTED_DIMENSIONS:
        raise ValueError(f"{event} is outside the reviewed native-size 30 fps lanes")
    model = str(manifest.get("video_composition_model", ""))
    if model not in SUPPORTED_COMPOSITION_MODELS:
        raise ValueError(f"{event} has an unsupported composition model")
    if manifest.get("video_extension_policy") not in SUPPORTED_EXTENSION_POLICIES:
        raise ValueError(f"{event} has an unsupported extension policy")

    sources = [snapshot(source_path, label=f"{event} v20 production manifest")]
    prepared = copy.deepcopy(manifest)
    plan = prepared.get("composition_plan")
    plan_missing_clips = (
        not isinstance(plan, dict)
        or not plan
        or not isinstance(plan.get("clips"), list)
        or not plan["clips"]
    )
    if plan_missing_clips:
        if model != "linear_full_frame_sequence":
            raise ValueError(f"{event} timed composition lacks authored clip rows")
        plan = generated_linear_plan(prepared)
    if plan.get("event") != event or plan.get("model") != model:
        raise ValueError(f"{event} composition identity mismatch")
    if plan.get("extension_policy") is None:
        plan = copy.deepcopy(plan)
        plan["extension_policy"] = prepared.get("video_extension_policy")
    elif plan.get("extension_policy") != prepared.get("video_extension_policy"):
        raise ValueError(f"{event} extension policy mismatch")

    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{event}.json"
    write_json(plan_path, plan)
    prepared["composition_plan"] = plan
    prepared["composition_plan_source"] = str(plan_path.resolve())

    clip_rows = prepared.get("clips")
    if not isinstance(clip_rows, list) or not clip_rows:
        raise ValueError(f"{event} has no clips")
    for index, clip in enumerate(clip_rows):
        if not isinstance(clip, dict):
            raise ValueError(f"{event} clip {index} is invalid")
        clip_path = Path(str(clip.get("path", ""))).resolve()
        clip_snapshot = snapshot(clip_path, label=f"{event} clip {index}")
        sources.append(clip_snapshot)
        clip["source_sha256"] = clip_snapshot["sha256"]

    audio = prepared.get("audio")
    if not isinstance(audio, list):
        raise ValueError(f"{event} has invalid audio rows")
    verified_no_event_audio = (
        not audio
        and gates.get("verified_no_event_audio") is True
        and isinstance(prepared.get("audio_absence_evidence"), Mapping)
        and prepared["audio_absence_evidence"].get("status")
        == "hash_bound_zero_matches"
    )
    if not audio and not verified_no_event_audio:
        raise ValueError(
            f"{event} has no audio rows without exact absence evidence"
        )
    if verified_no_event_audio:
        sources.extend(validate_audio_absence_evidence(prepared))
    request_ids = {str(row.get("request_id")) for row in audio if isinstance(row, Mapping)}
    permitted_forbidden_audio_request_ids = (
        permitted_forbidden_audio_request_ids or set()
    )
    if not permitted_forbidden_audio_request_ids <= FORBIDDEN_AUDIO_REQUESTS:
        raise ValueError(
            f"{event} permits audio requests outside the forbidden registry"
        )
    forbidden = sorted(
        (request_ids & FORBIDDEN_AUDIO_REQUESTS)
        - permitted_forbidden_audio_request_ids
    )
    if forbidden:
        raise ValueError(f"{event} contains forbidden BGM/effect requests: {forbidden}")
    for index, row in enumerate(audio):
        if not isinstance(row, Mapping):
            raise ValueError(f"{event} audio row {index} is invalid")
        audio_path = Path(str(row.get("path", ""))).resolve()
        sources.append(snapshot(audio_path, label=f"{event} audio {row.get('request_id')}"))

    manifest_dir.mkdir(parents=True, exist_ok=True)
    prepared_path = manifest_dir / f"{event}.json"
    write_json(prepared_path, prepared)
    return prepared, prepared_path, sources


def scene_audio_role(
    row: Mapping[str, Any], voice_request_ids: set[str] | None = None
) -> str:
    request_id = str(row.get("request_id", ""))
    if voice_request_ids is not None and request_id in voice_request_ids:
        return "voice"
    if row.get("source") == "event_audio_component":
        return "scene_se"
    code = str(row.get("code_name", ""))
    if "SPストーリー" in code:
        return "scene_se"
    if voice_request_ids is None:
        return "voice"
    return "unsubtitled_audio"


def validate_audio_layer_roles(
    event: str,
    roles: Sequence[str],
    *,
    require_scene_se: bool,
    reject_unsubtitled_audio: bool,
) -> None:
    """Fail before encoding when retained audio semantics are incomplete."""

    if not roles:
        raise ValueError(f"{event} has no retained evidence-bound audio layers")
    if require_scene_se and "scene_se" not in roles:
        raise ValueError(f"{event} does not have an evidence-bound base scene-SE layer")
    if reject_unsubtitled_audio and "unsubtitled_audio" in roles:
        raise ValueError(f"{event} contains unresolved unsubtitled audio layers")


def resolve_event(
    manifest: Mapping[str, Any],
    *,
    clean_visual: Path,
    clean_report: Path,
    translations: Mapping[str, str],
    require_scene_se: bool = True,
    reject_unsubtitled_audio: bool = False,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    event = str(manifest["event"])
    sources = [
        snapshot(clean_visual, label=f"{event} clean visual"),
        snapshot(clean_report, label=f"{event} clean visual render manifest"),
    ]
    report = read_json(clean_report)
    if report.get("event") != event or report.get("status") != "passed":
        raise ValueError(f"{event} clean visual report is not passed")
    if str(report.get("output_sha256", "")).upper() != sources[0]["sha256"]:
        raise ValueError(f"{event} clean visual hash differs from report")

    subtitle_rows = manifest.get("subtitles", [])
    voice_request_ids = {
        str(row.get("voice_request_id", "")).strip()
        for row in subtitle_rows
        if isinstance(row, Mapping) and str(row.get("voice_request_id", "")).strip()
    }
    audio_rows = manifest["audio"]
    layers: list[dict[str, Any]] = []
    for row in audio_rows:
        audio_path = Path(str(row["path"])).resolve()
        source = snapshot(audio_path, label=f"{event} audio request {row['request_id']}")
        sources.append(source)
        layers.append(
            {
                "role": scene_audio_role(row, voice_request_ids),
                "request_id": str(row["request_id"]),
                "ogg_name": str(row["ogg_name"]),
                "code_name": str(row.get("code_name", "")),
                "start_ms": int(row["start_ms"]),
                "duration_ms": int(row["duration_ms"]),
                "path": audio_path,
                "source": source,
            }
        )
    validate_audio_layer_roles(
        event,
        [str(layer["role"]) for layer in layers],
        require_scene_se=require_scene_se,
        reject_unsubtitled_audio=reject_unsubtitled_audio,
    )
    unresolved_audio = [
        {
            "request_id": layer["request_id"],
            "code_name": layer["code_name"],
            "ogg_name": layer["ogg_name"],
        }
        for layer in layers
        if layer["role"] == "unsubtitled_audio"
    ]
    if reject_unsubtitled_audio and unresolved_audio:
        raise ValueError(
            f"{event} contains unresolved unsubtitled audio layers: "
            f"{unresolved_audio}"
        )
    if any(layer["request_id"] in FORBIDDEN_AUDIO_REQUESTS for layer in layers):
        raise ValueError(f"{event} contains a forbidden BGM/effect audio layer")

    voice_layers = [layer for layer in layers if layer["role"] == "voice"]
    voice_by_id = {layer["request_id"]: layer for layer in voice_layers}
    if len(voice_by_id) != len(voice_layers):
        raise ValueError(f"{event} has duplicate voice request IDs")
    cues: list[dict[str, Any]] = []
    excluded_source: list[dict[str, Any]] = []
    for row in subtitle_rows:
        request_id = str(row.get("voice_request_id", "")).strip()
        text = str(row.get("text", "")).strip()
        if not request_id:
            excluded_source.append(
                {
                    "text": text,
                    "start_ms": int(row["start_ms"]),
                    "end_ms": int(row["end_ms"]),
                    "subtitle_source": str(row.get("subtitle_source", "")),
                    "reason": "unvoiced graphical text excluded from dialogue-only subtitles",
                }
            )
            continue
        if request_id not in voice_by_id:
            if row.get("subtitle_source") == "graphical_display_text":
                excluded_source.append(
                    {
                        "text": text,
                        "start_ms": int(row["start_ms"]),
                        "end_ms": int(row["end_ms"]),
                        "subtitle_source": str(row.get("subtitle_source", "")),
                        "reason": (
                            "graphical text references no retained voice layer; "
                            "excluded from dialogue-only subtitles"
                        ),
                    }
                )
                continue
            raise ValueError(f"{event} subtitle request {request_id} lacks one voice layer")
        if text not in translations:
            raise ValueError(f"{event} lacks Chinese translation for {text!r}")
        cues.append(
            {
                "event": event,
                "request_id": request_id,
                "start_ms": int(row["start_ms"]),
                "end_ms": int(row["end_ms"]),
                "ja_text": text,
                "zh_text": translations[text],
                "subtitle_source": str(row.get("subtitle_source", "")),
                "translation_status": "machine_draft_pending_owner",
                "voice_source_sha256": voice_by_id[request_id]["source"]["sha256"],
            }
        )
    included_ids = {cue["request_id"] for cue in cues}
    excluded_voice = [
        {
            "request_id": request_id,
            "code_name": layer["code_name"],
            "reason": "audio retained; no official voice-bound subtitle row",
        }
        for request_id, layer in {
            layer["request_id"]: layer
            for layer in layers
            if layer["role"] == "unsubtitled_audio"
        }.items()
        if request_id not in included_ids
    ]
    frame_count_value = int(manifest["render_frame_count"])
    quantization = manifest.get("render_duration_quantization")
    if not isinstance(quantization, Mapping):
        raise ValueError(f"{event} lacks CFR quantization evidence")
    samples = int(quantization["audio_sample_count"])
    if samples != frame_count_value * 1600:
        raise ValueError(f"{event} frame/sample grids differ")
    return (
        {
            "event": event,
            "width": int(manifest["native_dimensions"]["width"]),
            "height": int(manifest["native_dimensions"]["height"]),
            "composition_model": str(manifest["video_composition_model"]),
            "frame_count": frame_count_value,
            "presentation_samples": samples,
            "clean_visual": clean_visual,
            "clean_report": clean_report,
            "audio_layers": layers,
            "dialogue_cues": cues,
            "excluded_voice_requests": excluded_voice,
            "excluded_source_cues": excluded_source,
        },
        sources,
    )


def ffconcat_quote(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")


def _path_lexists(path: Path) -> bool:
    """Return true for every directory entry, including dangling symlinks."""

    return os.path.lexists(path)


@contextmanager
def _chapter_promotion_mutex(lock_path: Path):
    """Serialize one destination's check, promotion, verification, and rollback."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError(
                    f"chapter promotion is already active: {lock_path}"
                ) from error
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError(
                    f"chapter promotion is already active: {lock_path}"
                ) from error
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _rollback_owned_chapter(
    destination: Path, *, owner_marker_name: str, owner_token: str
) -> bool:
    """Remove a failed destination only while its private owner marker matches."""

    marker = destination / owner_marker_name
    try:
        if marker.is_symlink() or not marker.is_file():
            return False
        if marker.read_text(encoding="ascii") != owner_token:
            return False
    except OSError:
        return False
    shutil.rmtree(destination)
    return True


def promote(staging: Path, destination: Path, root: Path, *, overwrite: bool) -> None:
    ensure_resolved_containment(root, staging, label="chapter staging")
    ensure_resolved_containment(root, destination, label="chapter destination")
    backup = resolve_output_child(
        root, f".{destination.name}.backup.{uuid.uuid4().hex}", label="chapter backup"
    )
    lock_path = resolve_output_child(
        root,
        f".{destination.name}.chapter-promotion.lock",
        label="chapter promotion lock",
    )
    owner_token = uuid.uuid4().hex
    owner_marker_name = f".chapter-promotion-owner.{owner_token}"
    staged_owner_marker = staging / owner_marker_name
    if _path_lexists(staged_owner_marker):
        raise RuntimeError(f"unexpected chapter owner marker: {staged_owner_marker}")
    staged_owner_marker.write_text(owner_token, encoding="ascii")
    try:
        with _chapter_promotion_mutex(lock_path):
            if _path_lexists(destination) and not overwrite:
                raise FileExistsError(f"chapter already exists: {destination}")
            had_previous = _path_lexists(destination)
            promoted_by_this_call = False
            try:
                if had_previous:
                    destination.rename(backup)
                staging.rename(destination)
                promoted_by_this_call = True
                marker = read_json(destination / "BATCH_REVIEW_READY.json")
                if marker.get("status") != "AUTOMATED_QA_PASSED":
                    raise RuntimeError("promoted review marker is invalid")
                for artifact in marker["artifacts"].values():
                    path = (destination / artifact["path"]).resolve()
                    ensure_resolved_containment(
                        destination, path, label="review artifact"
                    )
                    if not path.is_file() or file_sha256(path) != artifact["sha256"]:
                        raise RuntimeError(f"promoted artifact hash mismatch: {path}")
                (destination / owner_marker_name).unlink()
                promoted_by_this_call = False
            except BaseException as error:
                if promoted_by_this_call:
                    _rollback_owned_chapter(
                        destination,
                        owner_marker_name=owner_marker_name,
                        owner_token=owner_token,
                    )
                if _path_lexists(backup):
                    if _path_lexists(destination):
                        raise RuntimeError(
                            "chapter promotion failed and the previous release "
                            f"was preserved at {backup}; destination is now owned "
                            "by another writer"
                        ) from error
                    backup.rename(destination)
                raise
            else:
                if _path_lexists(backup):
                    shutil.rmtree(backup)
    finally:
        if _path_lexists(staged_owner_marker):
            try:
                if (
                    not staged_owner_marker.is_symlink()
                    and staged_owner_marker.read_text(encoding="ascii") == owner_token
                ):
                    staged_owner_marker.unlink()
            except OSError:
                pass


def build_chapter(
    family: str,
    events: Sequence[Mapping[str, Any]],
    *,
    out_root: Path,
    layout: Mapping[str, Any],
    font_path: Path,
    source_snapshots: Sequence[Mapping[str, str]],
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> Path:
    dimension_set = {(int(event["width"]), int(event["height"])) for event in events}
    if len(dimension_set) != 1:
        raise RuntimeError(f"{family} mixes native dimensions: {sorted(dimension_set)}")
    width, height = next(iter(dimension_set))
    if (
        int(layout.get("target_width", 0)) != width
        or int(layout.get("target_height", 0)) != height
    ):
        raise RuntimeError(f"{family} has no exact native-size subtitle layout")
    release_id = validate_output_identifier(
        f"{family}_full_no_bgm_zh_review_v1", label="chapter release id"
    )
    destination = resolve_output_child(out_root, release_id, label="chapter release")
    staging = resolve_output_child(
        out_root, f".{release_id}.staging.{uuid.uuid4().hex}", label="chapter staging"
    )
    staging.mkdir(parents=True)
    work = staging / "work"
    work.mkdir()
    try:
        staged_font_dir = work / "fonts"
        staged_font_dir.mkdir()
        staged_font = staged_font_dir / font_path.name
        shutil.copy2(font_path, staged_font)

        event_pcm_paths: list[Path] = []
        pcm_audits: list[dict[str, Any]] = []
        total_frames = 0
        total_samples = 0
        scene_cues: list[dict[str, Any]] = []
        timeline: list[dict[str, Any]] = []
        for event in events:
            event_pcm = work / f"{event['event']}.f32le"
            pcm_audits.append(build_event_pcm(event, output=event_pcm, ffmpeg=ffmpeg))
            event_pcm_paths.append(event_pcm)
            start_frame = total_frames
            start_sample = total_samples
            for cue in event["dialogue_cues"]:
                offset_ms = round(Fraction(start_sample * 1000, 48000))
                scene_cues.append(
                    {
                        "start_ms": offset_ms + int(cue["start_ms"]),
                        "end_ms": offset_ms + int(cue["end_ms"]),
                        "text": cue["zh_text"],
                        "event": event["event"],
                        "request_id": cue["request_id"],
                        "ja_text": cue["ja_text"],
                    }
                )
            total_frames += int(event["frame_count"])
            total_samples += int(event["presentation_samples"])
            timeline.append(
                {
                    "event": event["event"],
                    "start_frame": start_frame,
                    "end_frame": total_frames,
                    "start_sample": start_sample,
                    "end_sample": total_samples,
                    "inserted_gap_frames": 0,
                }
            )
        if total_samples != total_frames * 1600:
            raise RuntimeError("chapter frame/sample grids differ")

        scene_pcm = work / "scene.f32le"
        concat_binary(event_pcm_paths, scene_pcm)
        if scene_pcm.stat().st_size != total_samples * 8:
            raise RuntimeError("chapter PCM byte count mismatch")
        scene_pcm_hash = file_sha256(scene_pcm)

        masters = staging / "masters"
        masters.mkdir()
        audio_master = masters / f"{release_id}__no_bgm_audio_master.m4a"
        run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "f32le", "-ar", "48000", "-ac", "2", "-i", str(scene_pcm),
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart", str(audio_master),
            ]
        )
        audio_probe = probe(audio_master, ffprobe)
        audio_stream = media_streams(audio_probe, "audio")[0]
        audio_timeline = audio_gate._audio_packet_timeline(
            output=audio_master,
            audio_stream=audio_stream,
            expected_samples=total_samples,
            ffprobe=ffprobe,
        )
        audio_pcm = audio_gate._effective_decoded_pcm_audit(
            output=audio_master, expected_samples=total_samples, ffmpeg=ffmpeg
        )

        concat_file = work / "visuals.ffconcat"
        concat_file.write_text(
            "ffconcat version 1.0\n"
            + "".join(f"file '{ffconcat_quote(Path(event['clean_visual']))}'\n" for event in events),
            encoding="utf-8",
        )
        clean_scene = masters / f"{release_id}__clean_visual_master.mp4"
        run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-an", "-c:v", "copy", "-movflags", "+faststart", str(clean_scene),
            ]
        )
        clean_probe = probe(clean_scene, ffprobe)
        clean_video = media_streams(clean_probe, "video")[0]
        if (
            frame_count(clean_video) != total_frames
            or int(clean_video.get("width", 0)) != width
            or int(clean_video.get("height", 0)) != height
            or clean_video.get("r_frame_rate") != "30/1"
        ):
            raise RuntimeError("chapter clean visual grid mismatch")

        subtitle_dir = staging / "subtitles"
        subtitle_dir.mkdir()
        subtitle_path = subtitle_dir / f"{release_id}__zh_dialogue.srt"
        write_srt(subtitle_path, scene_cues)
        parsed = parse_srt(subtitle_path)
        expected_parsed = [
            {"start_ms": row["start_ms"], "end_ms": row["end_ms"], "text": row["text"]}
            for row in scene_cues
        ]
        if parsed != expected_parsed:
            raise RuntimeError("chapter SRT round-trip mismatch")

        video_dir = staging / "video"
        video_dir.mkdir()
        final_video = video_dir / f"{release_id}.mp4"
        filter_value = subtitle_filter(
            layout,
            srt_path=subtitle_path.relative_to(staging).as_posix(),
            fonts_dir=staged_font_dir.relative_to(staging).as_posix(),
        )
        run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", clean_scene.relative_to(staging).as_posix(),
                "-i", audio_master.relative_to(staging).as_posix(),
                "-vf", filter_value,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                "-pix_fmt", "yuv420p", "-c:a", "copy",
                "-frames:v", str(total_frames), "-movflags", "+faststart",
                final_video.relative_to(staging).as_posix(),
            ],
            cwd=staging,
        )
        final_probe = probe(final_video, ffprobe)
        videos = media_streams(final_probe, "video")
        audios = media_streams(final_probe, "audio")
        if len(videos) != 1 or len(audios) != 1 or media_streams(final_probe, "subtitle"):
            raise RuntimeError("chapter final stream contract failed")
        final_video_stream = videos[0]
        final_audio_stream = audios[0]
        if (
            frame_count(final_video_stream) != total_frames
            or int(final_video_stream.get("width", 0)) != width
            or int(final_video_stream.get("height", 0)) != height
            or final_video_stream.get("r_frame_rate") != "30/1"
            or final_audio_stream.get("codec_name") != "aac"
            or int(final_audio_stream.get("sample_rate", 0)) != 48000
            or int(final_audio_stream.get("channels", 0)) != 2
        ):
            raise RuntimeError("chapter final native media contract failed")
        final_audio_timeline = audio_gate._audio_packet_timeline(
            output=final_video,
            audio_stream=final_audio_stream,
            expected_samples=total_samples,
            ffprobe=ffprobe,
        )
        final_audio_pcm = audio_gate._effective_decoded_pcm_audit(
            output=final_video, expected_samples=total_samples, ffmpeg=ffmpeg
        )
        if final_audio_pcm != audio_pcm or final_audio_timeline != audio_timeline:
            raise RuntimeError("chapter final audio differs from encoded-once master")
        if packet_hash(audio_master, kind="audio", ffmpeg=ffmpeg) != packet_hash(
            final_video, kind="audio", ffmpeg=ffmpeg
        ):
            raise RuntimeError("chapter final AAC packets differ from master")
        volume = volume_audit(final_video, ffmpeg)
        if volume["max_volume_db"].lower() == "-inf":
            raise RuntimeError("chapter final audio is silent")

        review_dir = staging / "review"
        frames_dir = review_dir / "layout_frames"
        frames_dir.mkdir(parents=True)
        review_frames: list[dict[str, Any]] = []
        if scene_cues:
            count = min(12, len(scene_cues))
            indices = sorted({round(index * (len(scene_cues) - 1) / max(count - 1, 1)) for index in range(count)})
            for output_index, cue_index in enumerate(indices, start=1):
                cue = scene_cues[cue_index]
                midpoint = (int(cue["start_ms"]) + int(cue["end_ms"])) // 2
                frame_path = frames_dir / f"sample_{output_index:02d}_cue_{cue_index + 1:03d}.png"
                run(
                    [
                        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{midpoint / 1000:.3f}", "-i", str(final_video),
                        "-frames:v", "1", str(frame_path),
                    ]
                )
                review_frames.append(
                    {
                        "cue_index": cue_index + 1,
                        "event": cue["event"],
                        "midpoint_ms": midpoint,
                        "path": frame_path.relative_to(staging).as_posix(),
                        "sha256": file_sha256(frame_path),
                    }
                )

        review_form = review_dir / "HUMAN_PLAYBACK_REVIEW.md"
        review_form.write_text(
            f"# {family} 完整章节人工播放审查\n\n"
            f"候选：`{final_video.name}`\n\n"
            f"事件数：{len(events)}；中文字幕：{len(scene_cues)} 条；BGM：有意排除。\n\n"
            "- [ ] 事件顺序和边界自然，无自动黑场\n"
            "- [ ] clean story 画面完整，无金框、粒子或老虎机前景\n"
            "- [ ] 所有角色语音存在且人物匹配\n"
            "- [ ] 场景 SE 正确，没有意外 BGM\n"
            "- [ ] 中文字幕只对应可听角色声，翻译和称呼正确\n"
            "- [ ] 字幕时间、换行和遮挡可接受\n"
            "- [ ] 音画同步，首尾和尾帧保持自然\n\n"
            "```text\nHUMAN_PLAYBACK_APPROVED =\n需要修改：\n```\n",
            encoding="utf-8",
        )

        shutil.rmtree(work)
        rehash(source_snapshots)
        qa_path = staging / "qa" / "automated_qa.json"
        qa = {
            "schema": QA_SCHEMA,
            "status": "passed",
            "family": family,
            "checks": {
                "source_hashes_unchanged": True,
                "all_events_v20_technical_ready": True,
                "explicit_clean_visual_compositions": True,
                "forbidden_bgm_and_gold_requests_absent": True,
                "evidence_bound_scene_audio_per_event": True,
                "all_voice_layers_accounted": True,
                "zero_inserted_black_frames": True,
                "native_dimensions_30fps": True,
                "exact_frame_and_sample_grid": True,
                "aac_encoded_once_and_packet_copied": True,
                "dialogue_only_chinese_srt_round_trip": True,
                "human_and_publication_status_false": True,
            },
            "events": [event["event"] for event in events],
            "timeline": timeline,
            "total_frames": total_frames,
            "total_presentation_samples": total_samples,
            "duration_ms": round(Fraction(total_samples * 1000, 48000)),
            "dialogue_cue_count": len(scene_cues),
            "audio_layer_count": sum(len(event["audio_layers"]) for event in events),
            "excluded_voice_requests": [
                {"event": event["event"], **row}
                for event in events
                for row in event["excluded_voice_requests"]
            ],
            "excluded_source_cues": [
                {"event": event["event"], **row}
                for event in events
                for row in event["excluded_source_cues"]
            ],
            "source_scene_pcm_f32le_sha256": scene_pcm_hash,
            "audio_master_timeline": audio_timeline,
            "final_audio_timeline": final_audio_timeline,
            "audio_master_decoded_pcm": audio_pcm,
            "final_audio_decoded_pcm": final_audio_pcm,
            "volume": volume,
            "review_frames": review_frames,
            "warnings": [
                "This is an expansion review candidate, not a Bilibili release approval.",
                "Chinese translations await project-owner playback review.",
                "BGM is intentionally excluded; voice and scene SE are retained.",
            ],
        }
        write_json(qa_path, qa)

        manifest_path = staging / "manifests" / "chapter_review_manifest.json"
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": "AUTOMATED_QA_PASSED",
            "release_id": release_id,
            "family": family,
            "release_profile": "no_bgm_zh_expansion_review_v1",
            "audio_profile": "no_bgm",
            "subtitle_profile": "zh_voice_bound_dialogue",
            "bgm_policy": "intentionally_excluded",
            "voice_se_policy": "preserve_v20_evidence_bound_original",
            "translation_status": "machine_draft_pending_owner",
            "human_review_status": "pending",
            "publishable": False,
            "readiness": {
                "AUTOMATED_QA_PASSED": True,
                "HUMAN_PLAYBACK_APPROVED": False,
                "BILIBILI_RELEASE_READY": False,
            },
            "ordered_events": [event["event"] for event in events],
            "timeline": timeline,
            "media": {
                "duration_ms": round(Fraction(total_samples * 1000, 48000)),
                "width": width,
                "height": height,
                "frame_rate": "30/1",
                "video_codec": "h264",
                "video_bit_rate": stream_bit_rate(final_video_stream, label="chapter video"),
                "audio_codec": "aac",
                "audio_bit_rate": stream_bit_rate(final_audio_stream, label="chapter audio"),
                "audio_sample_rate": 48000,
                "audio_channels": 2,
                "upscaled": False,
            },
            "dialogue_cue_count": len(scene_cues),
            "audio_layer_count": sum(len(event["audio_layers"]) for event in events),
            "source_snapshots": list(source_snapshots),
            "artifacts": {
                "video": {"path": final_video.relative_to(staging).as_posix(), "sha256": file_sha256(final_video)},
                "subtitles": {"path": subtitle_path.relative_to(staging).as_posix(), "sha256": file_sha256(subtitle_path)},
                "qa": {"path": qa_path.relative_to(staging).as_posix(), "sha256": file_sha256(qa_path)},
                "review_form": {"path": review_form.relative_to(staging).as_posix(), "sha256": file_sha256(review_form)},
                "clean_visual_master": {"path": clean_scene.relative_to(staging).as_posix(), "sha256": file_sha256(clean_scene)},
                "no_bgm_audio_master": {"path": audio_master.relative_to(staging).as_posix(), "sha256": file_sha256(audio_master)},
            },
        }
        write_json(manifest_path, manifest)
        marker_artifacts = {
            role: manifest["artifacts"][role]
            for role in ("video", "subtitles", "qa", "review_form")
        }
        marker_artifacts["manifest"] = {
            "path": manifest_path.relative_to(staging).as_posix(),
            "sha256": file_sha256(manifest_path),
        }
        marker = {
            "schema": READY_SCHEMA,
            "status": "AUTOMATED_QA_PASSED",
            "release_id": release_id,
            "family": family,
            "publishable": False,
            "readiness": {
                "AUTOMATED_QA_PASSED": True,
                "HUMAN_PLAYBACK_APPROVED": False,
                "BILIBILI_RELEASE_READY": False,
            },
            "artifacts": marker_artifacts,
            "artifact_set_sha256": canonical_sha256(marker_artifacts),
        }
        write_json(staging / "BATCH_REVIEW_READY.json", marker)
        rehash(source_snapshots)
        promote(staging, destination, out_root, overwrite=overwrite)
        return destination
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--series-root")
    parser.add_argument(
        "--series-manifest",
        action="append",
        metavar="FAMILY=PATH",
        help="explicit passed family series manifest; repeat for a mixed batch",
    )
    parser.add_argument("--translation-map", required=True)
    parser.add_argument("--layout-profile", action="append", required=True)
    parser.add_argument("--font", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--renderer", required=True)
    parser.add_argument("--family", action="append")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def resolve_series_manifests(args: argparse.Namespace) -> dict[str, Path]:
    if args.series_manifest:
        if args.family or args.series_root:
            raise ValueError(
                "explicit --series-manifest cannot be combined with --family/--series-root"
            )
        result: dict[str, Path] = {}
        for spec in args.series_manifest:
            family_text, separator, path_text = str(spec).partition("=")
            if not separator or not path_text:
                raise ValueError(f"invalid --series-manifest value: {spec!r}")
            family = validate_output_identifier(family_text, label="series family")
            if family in result:
                raise ValueError(f"duplicate series family: {family}")
            result[family] = Path(path_text).resolve()
        return dict(sorted(result.items()))
    if not args.series_root:
        raise ValueError("--series-root is required without --series-manifest")
    root = Path(args.series_root).resolve()
    families = args.family or sorted(DEFAULT_SP_FAMILIES)
    result = {}
    for value in families:
        family = validate_output_identifier(value, label="series family")
        if family in result:
            raise ValueError(f"duplicate series family: {family}")
        result[family] = root / family / "series_manifest.json"
    return result


def load_layout_profiles(paths: Sequence[str]) -> tuple[dict[tuple[int, int], dict[str, Any]], list[dict[str, str]]]:
    layouts: dict[tuple[int, int], dict[str, Any]] = {}
    sources: list[dict[str, str]] = []
    for value in paths:
        path = Path(value).resolve()
        layout = read_json(path)
        dimensions = (
            int(layout.get("target_width", 0)),
            int(layout.get("target_height", 0)),
        )
        if (
            dimensions not in SUPPORTED_DIMENSIONS
            or layout.get("approval_status") != "pending_owner_review"
            or layout.get("original_game_layout") is not False
        ):
            raise ValueError(f"subtitle layout is not an audited pending-owner profile: {path}")
        if dimensions in layouts:
            raise ValueError(f"duplicate subtitle layout dimensions: {dimensions}")
        layouts[dimensions] = layout
        sources.append(snapshot(path, label=f"Chinese subtitle layout {dimensions[0]}x{dimensions[1]}"))
    return layouts, sources


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_root = Path(args.manifest_root).resolve()
    series_manifests = resolve_series_manifests(args)
    families = list(series_manifests)
    translation_path = Path(args.translation_map).resolve()
    font_path = Path(args.font).resolve()
    renderer_path = Path(args.renderer).resolve()
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    translations, translation_snapshot = load_translation_map(translation_path)
    layouts, layout_sources = load_layout_profiles(args.layout_profile)
    shared_sources = [
        translation_snapshot,
        *layout_sources,
        snapshot(font_path, label="Chinese subtitle font"),
        snapshot(renderer_path, label="clean visual renderer"),
    ]

    manifest_out = out_root / "_batch_inputs" / "events"
    plan_out = out_root / "_batch_inputs" / "composition_plans"
    clean_root = out_root / "_event_clean_visuals"
    batch_rows: dict[str, list[dict[str, Any]]] = {}
    all_sources = list(shared_sources)
    for family in families:
        series_path = series_manifests[family]
        series = read_json(series_path)
        all_sources.append(snapshot(series_path, label=f"{family} series ordering manifest"))
        if series.get("status") != "passed" or series.get("series") != family:
            raise ValueError(f"{family} series manifest is not passed")
        ordered = series.get("family_state", {}).get("ready_event_names")
        if not isinstance(ordered, list) or len(ordered) != int(series.get("event_count", -1)):
            raise ValueError(f"{family} series ordering is invalid")
        rows: list[dict[str, Any]] = []
        for event in ordered:
            event = validate_output_identifier(event, label=f"{family} event")
            source_manifest = manifest_root / "events" / f"{event}.json"
            prepared, prepared_path, sources = prepare_manifest(
                source_manifest, plan_dir=plan_out, manifest_dir=manifest_out
            )
            all_sources.extend(sources)
            clean_visual = clean_root / event / "clean_visual" / f"{event}__clean_visual.mp4"
            clean_report = clean_root / event / "render_manifest.json"
            rows.append(
                {
                    "event": event,
                    "prepared": prepared,
                    "prepared_path": prepared_path,
                    "clean_visual": clean_visual,
                    "clean_report": clean_report,
                }
            )
        batch_rows[family] = rows

    required_texts = {
        str(row.get("text", "")).strip()
        for rows in batch_rows.values()
        for event in rows
        for row in event["prepared"].get("subtitles", [])
        if str(row.get("voice_request_id", "")).strip()
    }
    missing = sorted(required_texts - set(translations))
    unused = sorted(set(translations) - required_texts)
    if missing:
        raise ValueError(f"translation coverage is incomplete: missing={missing}")
    if args.validate_only:
        print(
            json.dumps(
                {
                    "schema": BATCH_SCHEMA,
                    "status": "validated",
                    "families": {
                        family: {
                            "events": len(rows),
                            "dialogue_cues": sum(
                                1
                                for event in rows
                                for row in event["prepared"].get("subtitles", [])
                                if str(row.get("voice_request_id", "")).strip()
                            ),
                            "audio_layers": sum(len(event["prepared"]["audio"]) for event in rows),
                        }
                        for family, rows in batch_rows.items()
                    },
                    "source_snapshot_count": len(all_sources),
                    "unused_translation_count": len(unused),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    for family, rows in batch_rows.items():
        for row in rows:
            clean_exists = row["clean_visual"].is_file()
            report_exists = row["clean_report"].is_file()
            if clean_exists and report_exists and not args.overwrite:
                validate_reusable_clean_visual(
                    event=row["event"],
                    prepared_path=row["prepared_path"],
                    clean_visual=row["clean_visual"],
                    clean_report=row["clean_report"],
                )
                continue
            if clean_exists != report_exists and not args.overwrite:
                raise RuntimeError(
                    f"{row['event']} existing clean-visual release is incomplete; "
                    "rerun with --overwrite"
                )
            command = [
                sys.executable,
                str(renderer_path),
                "--manifest",
                str(row["prepared_path"]),
                "--out-root",
                str(clean_root),
                "--clean-visual-only",
                "--ffmpeg",
                args.ffmpeg,
                "--ffprobe",
                args.ffprobe,
            ]
            if args.overwrite:
                command.append("--overwrite")
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
            validate_reusable_clean_visual(
                event=row["event"],
                prepared_path=row["prepared_path"],
                clean_visual=row["clean_visual"],
                clean_report=row["clean_report"],
            )
    resolved_by_family: dict[str, list[dict[str, Any]]] = {}
    media_sources = list(all_sources)
    for family, rows in batch_rows.items():
        resolved_rows: list[dict[str, Any]] = []
        for row in rows:
            resolved, sources = resolve_event(
                row["prepared"],
                clean_visual=row["clean_visual"],
                clean_report=row["clean_report"],
                translations=translations,
            )
            resolved_rows.append(resolved)
            media_sources.extend(sources)
        resolved_by_family[family] = resolved_rows
    rehash(media_sources)

    destinations = []
    for family in families:
        dimensions = {
            (int(event["width"]), int(event["height"]))
            for event in resolved_by_family[family]
        }
        if len(dimensions) != 1 or next(iter(dimensions)) not in layouts:
            raise RuntimeError(f"{family} lacks one exact native-size subtitle layout")
        destination = build_chapter(
            family,
            resolved_by_family[family],
            out_root=out_root,
            layout=layouts[next(iter(dimensions))],
            font_path=font_path,
            source_snapshots=media_sources,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
            overwrite=args.overwrite,
        )
        destinations.append(str(destination))
    batch_summary = {
        "schema": BATCH_SCHEMA,
        "status": "AUTOMATED_QA_PASSED",
        "families": destinations,
        "human_playback_approved": False,
        "bilibili_release_ready": False,
    }
    write_json(out_root / "BATCH_SUMMARY.json", batch_summary)
    print(json.dumps(batch_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
