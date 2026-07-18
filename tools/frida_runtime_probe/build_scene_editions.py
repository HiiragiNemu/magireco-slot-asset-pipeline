#!/usr/bin/env python3
"""Build auditable same-scene long editions from an explicit event sequence.

Unlike build_series_editions.py, this tool is intentionally not prefix based.
It is for upload/review cuts where one narrative scene spans multiple event
families such as ac7114_001 -> ac7115_001 -> ac7116_001.  Inputs must already
be QA-passed single-event subtitle/no-subtitle pairs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from . import build_audio_base_masters as audio_gate
    from . import build_series_editions as series_gate
    from .composition_contract import presentation_sample_count
    from .output_path_contract import (
        resolve_output_child,
        validate_output_identifier,
    )
    from .render_subtitle_editions import (
        probe_video_timeline,
        validate_transaction_ready_marker,
    )
    from .subtitle_edition_contract import (
        AUDIO_PROFILES,
        LEGACY_AUDIO_PROFILE,
        SUPPORTED_EDITIONS,
        normalize_render_editions,
        normalize_requested_audio_profiles,
        normalize_requested_editions,
    )
except ImportError:  # direct script execution
    import build_audio_base_masters as audio_gate  # type: ignore
    import build_series_editions as series_gate  # type: ignore
    from composition_contract import presentation_sample_count  # type: ignore
    from output_path_contract import (  # type: ignore
        resolve_output_child,
        validate_output_identifier,
    )
    from render_subtitle_editions import (  # type: ignore
        probe_video_timeline,
        validate_transaction_ready_marker,
    )
    from subtitle_edition_contract import (  # type: ignore
        AUDIO_PROFILES,
        LEGACY_AUDIO_PROFILE,
        SUPPORTED_EDITIONS,
        normalize_render_editions,
        normalize_requested_audio_profiles,
        normalize_requested_editions,
    )


SRT_BLOCK_RE = re.compile(
    r"(?:^|\n)\s*\d+\s*\n"
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})\s*\n"
    r"(?P<text>.*?)(?=\n\s*\d+\s*\n\d{2}:|\Z)",
    re.DOTALL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", action="append", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--event", action="append", required=True)
    parser.add_argument("--production-manifest-root", default="")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--edition",
        action="append",
        choices=SUPPORTED_EDITIONS,
        dest="editions",
        help=(
            "repeat none/ja/zh; modern publication defaults to all three, "
            "legacy mode is fixed to none+ja"
        ),
    )
    parser.add_argument(
        "--legacy-two-edition",
        action="store_true",
        help="explicitly build the old unclassified-audio none+ja scene",
    )
    parser.add_argument(
        "--audio-profile",
        action="append",
        choices=AUDIO_PROFILES,
        dest="audio_profiles",
        help="repeat for with_bgm/no_bgm; publication requires both",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def srt_time_ms(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int(milliseconds)
    )


def format_srt_time(value_ms: int) -> str:
    value_ms = max(0, value_ms)
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def shifted_srt_cues(text: str, offset_ms: int) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    normalized = text.replace("\r\n", "\n").strip()
    for match in SRT_BLOCK_RE.finditer(normalized):
        cues.append(
            {
                "start_ms": srt_time_ms(match.group("start")) + offset_ms,
                "end_ms": srt_time_ms(match.group("end")) + offset_ms,
                "text": match.group("text").strip(),
            }
        )
    return cues


def write_srt(path: Path, cues: list[dict[str, Any]]) -> None:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_srt_time(int(cue['start_ms']))} --> "
            f"{format_srt_time(int(cue['end_ms']))}\n"
            f"{cue['text']}"
        )
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def _cue_projection(
    cues: list[dict[str, Any]], *, label: str
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict):
            raise ValueError(f"{label} cue {index} is not an object")
        try:
            start_ms = int(cue["start_ms"])
            end_ms = int(cue["end_ms"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"{label} cue {index} has invalid start_ms/end_ms"
            ) from error
        text = str(cue.get("text", ""))
        if start_ms < 0 or end_ms <= start_ms or not text.strip():
            raise ValueError(f"{label} cue {index} is invalid")
        projected.append(
            {"start_ms": start_ms, "end_ms": end_ms, "text": text}
        )
    return projected


def audited_edition_plan_cues(
    render_manifest: dict[str, Any], *, event: str, language: str
) -> list[dict[str, Any]]:
    plan = render_manifest.get("edition_plan")
    if not isinstance(plan, dict):
        raise ValueError(f"{event} render manifest lacks an audited edition_plan")
    if str(plan.get("event", "")) != event:
        raise ValueError(f"{event} edition_plan event mismatch")
    tracks = plan.get("tracks")
    if not isinstance(tracks, dict):
        raise ValueError(f"{event} edition_plan lacks subtitle tracks")
    track = tracks.get(language)
    if not isinstance(track, dict):
        raise ValueError(f"{event} edition_plan lacks {language} track")
    cues = track.get("cues")
    if not isinstance(cues, list):
        raise ValueError(f"{event} edition_plan {language} track lacks cues")
    expected_count = track.get("cue_count")
    try:
        expected_count = int(expected_count)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{event} edition_plan {language} track lacks cue_count"
        ) from error
    if expected_count != len(cues):
        raise ValueError(
            f"{event} edition_plan {language} cue_count mismatch"
        )
    return _cue_projection(cues, label=f"{event} edition_plan {language}")


def validate_srt_cues_against_expected(
    *,
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    label: str,
) -> None:
    actual_projection = _cue_projection(actual, label=f"{label} parsed SRT")
    expected_projection = _cue_projection(expected, label=f"{label} audited source")
    if actual_projection != expected_projection:
        raise ValueError(
            f"{label} parsed SRT does not match audited edition_plan cues"
        )


def validate_written_srt_round_trip(
    path: Path, expected: list[dict[str, Any]], *, label: str
) -> None:
    parsed = shifted_srt_cues(path.read_text(encoding="utf-8"), 0)
    try:
        validate_srt_cues_against_expected(
            actual=parsed, expected=expected, label=label
        )
    except ValueError as error:
        raise RuntimeError(f"{label} written SRT round-trip mismatch") from error


def video_presentation_sample_count(
    *, frame_count: int, frame_rate: str, sample_rate: int = 48000
) -> int:
    try:
        rate = Fraction(str(frame_rate))
    except (ValueError, ZeroDivisionError) as error:
        raise RuntimeError(f"invalid video frame rate: {frame_rate!r}") from error
    if frame_count <= 0 or rate <= 0 or sample_rate <= 0:
        raise RuntimeError("video presentation sample inputs must be positive")
    return math.ceil(Fraction(frame_count * sample_rate, 1) / rate)


def load_event_presentation_contract(row: dict[str, Any]) -> dict[str, Any]:
    event = str(row["event"])
    render_manifest = row["render_manifest"]
    source_text = str(render_manifest.get("source_manifest", "")).strip()
    declared_sha256 = str(
        render_manifest.get("source_manifest_sha256", "")
    ).strip().upper()
    if not source_text or not re.fullmatch(r"[0-9A-F]{64}", declared_sha256):
        raise ValueError(f"{event} render manifest lacks a bound source manifest")
    source_path = Path(source_text)
    if not source_path.is_absolute():
        source_path = Path(row["render_manifest_path"]).parent / source_path
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if file_sha256(source_path) != declared_sha256:
        raise ValueError(f"{event} source manifest SHA-256 mismatch")
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or str(payload.get("event", "")) != event:
        raise ValueError(f"{event} source manifest event mismatch")
    try:
        frame_count = int(payload["render_frame_count"])
        duration_ms = int(payload["render_duration_ms"])
        frame_rate = str(payload["native_frame_rate"])
        sample_count = presentation_sample_count(payload)
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        raise ValueError(f"{event} source presentation contract is invalid") from error
    return {
        "path": source_path,
        "sha256": declared_sha256,
        "manifest": payload,
        "frame_count": frame_count,
        "duration_ms": duration_ms,
        "frame_rate": frame_rate,
        "presentation_sample_count": sample_count,
    }


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,profile,level,width,height,pix_fmt,"
            "r_frame_rate,avg_frame_rate,time_base,sample_rate,channels,"
            "channel_layout,duration,bit_rate:format=duration,size,bit_rate",
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


def stream_signature(payload: dict[str, Any]) -> dict[str, Any]:
    video = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "video"
    )
    audio = next(
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "audio"
    )
    return {
        "video": {
            key: video.get(key, "")
            for key in (
                "codec_name",
                "profile",
                "level",
                "width",
                "height",
                "pix_fmt",
                "r_frame_rate",
                "time_base",
            )
        },
        "audio": {
            key: audio.get(key, "")
            for key in (
                "codec_name",
                "sample_rate",
                "channels",
                "channel_layout",
                "time_base",
            )
        },
    }


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


def ffconcat_line(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{value}'"


def concat_copy(
    sources: list[Path],
    list_path: Path,
    output_path: Path,
    ffmpeg: str,
    overwrite: bool,
) -> None:
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(path) for path in sources)
        + "\n",
        encoding="utf-8",
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )


def concat_video_copy(
    sources: list[Path],
    list_path: Path,
    output_path: Path,
    ffmpeg: str,
    overwrite: bool,
) -> None:
    list_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(path) for path in sources)
        + "\n",
        encoding="utf-8",
    )
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )


def build_scene_audio_master(
    segments: list[dict[str, Any]],
    output_path: Path,
    target_bit_rate: int,
    ffmpeg: str,
    overwrite: bool,
) -> dict[str, Any]:
    if len(segments) < 2:
        raise ValueError("scene audio master requires at least two segments")
    if target_bit_rate < 64_000 or target_bit_rate > 512_000:
        raise ValueError("scene AAC target bitrate is outside 64k..512k")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    cumulative_samples = 0
    segment_provenance: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        source = Path(segment["path"])
        sample_count = int(segment["presentation_sample_count"])
        if not source.is_file() or sample_count <= 0:
            raise ValueError(f"invalid scene audio segment {index}: {segment}")
        inputs.extend(["-i", str(source)])
        label = f"seg{index}"
        labels.append(f"[{label}]")
        filters.append(
            f"[{index}:a:0]atrim=start_sample=0:end_sample={sample_count},"
            f"asetpts=N/SR/TB[{label}]"
        )
        segment_provenance.append(
            {
                "order": index + 1,
                "event": str(segment["event"]),
                "source": str(source.resolve()),
                "source_sha256": file_sha256(source),
                "presentation_sample_count": sample_count,
                "start_sample": cumulative_samples,
                "end_sample": cumulative_samples + sample_count,
                "sidecar": str(segment["sidecar"]),
                "sidecar_sha256": str(segment["sidecar_sha256"]),
            }
        )
        cumulative_samples += sample_count
    filters.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1[scene_audio]"
    )
    filter_graph = ";".join(filters)
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            filter_graph,
            "-map",
            "[scene_audio]",
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            str(target_bit_rate),
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )
    return {
        "method": "effective_pcm_concat_then_single_aac_encode",
        "source_decode": "AAC decode with sidecar-bound effective sample trim",
        "filter_graph": filter_graph,
        "codec": "aac",
        "sample_rate": 48000,
        "channels": 2,
        "channel_layout": "stereo",
        "target_bit_rate": target_bit_rate,
        "presentation_sample_count": cumulative_samples,
        "segments": segment_provenance,
    }


def mux_scene_av_copy(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    ffmpeg: str,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-hide_banner",
            "-loglevel",
            "error",
            "-copyts",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        check=True,
    )


def verify_ffconcat_order(list_path: Path, sources: list[Path]) -> None:
    expected = (
        "ffconcat version 1.0\n"
        + "\n".join(ffconcat_line(path) for path in sources)
        + "\n"
    )
    if list_path.read_text(encoding="utf-8") != expected:
        raise ValueError(f"ffconcat explicit event order was altered: {list_path}")


def concat_stream_hash(list_path: Path, media_type: str, ffmpeg: str) -> str:
    if media_type not in {"video", "audio"}:
        raise ValueError(f"unsupported concat stream hash type: {media_type}")
    selector = "0:v:0" if media_type == "video" else "0:a:0"
    codec_args = ["-c:v", "copy"] if media_type == "video" else ["-c:a", "copy"]
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            selector,
            *codec_args,
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


def decoded_video_hash(path: Path, ffmpeg: str) -> str:
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "rawvideo",
            "-pix_fmt",
            "yuv420p",
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


def concat_decoded_hash(list_path: Path, media_type: str, ffmpeg: str) -> str:
    if media_type == "video":
        stream_args = [
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "rawvideo",
            "-pix_fmt",
            "yuv420p",
        ]
    elif media_type == "audio":
        stream_args = [
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
        ]
    else:
        raise ValueError(f"unsupported concat decoded hash type: {media_type}")
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            *stream_args,
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


def load_qa_status(root: Path) -> dict[str, str]:
    path = root / "full_qa_audit.csv"
    if not path.is_file():
        raise FileNotFoundError(f"QA audit is required: {path}")
    return {row.get("event", ""): row.get("status", "") for row in read_csv(path)}


def resolve_manifest_file(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def discover_events(
    input_roots: list[Path], *, allow_legacy: bool = True
) -> dict[str, dict[str, Any]]:
    """Reuse the series builder's evidence-bound discovery implementation.

    The default remains legacy-compatible for callers which only inspect old
    manifests.  The verified scene path always calls this with
    ``allow_legacy=False`` and therefore cannot relabel an unclassified audio
    stream as either production profile.
    """

    return series_gate.discover_events(input_roots, allow_legacy=allow_legacy)


def manifest_path_for_event(root: Path | None, event: str) -> str:
    if root is None:
        return ""
    event_dir = root / "events"
    if not event_dir.is_dir():
        event_dir = root
    path = event_dir / f"{event}.json"
    return str(path.resolve()) if path.is_file() else ""


def scene_edition_paths(
    scene_dir: Path,
    scene: str,
    edition: str,
    audio_profile: str = LEGACY_AUDIO_PROFILE,
) -> tuple[Path, Path | None]:
    if audio_profile != LEGACY_AUDIO_PROFILE:
        profile_dir = scene_dir / audio_profile
        if edition == "none":
            return (
                profile_dir / "without_subtitles" / f"{scene}__scene.mp4",
                None,
            )
        video_dir = (
            "with_subtitles" if edition == "ja" else f"with_subtitles_{edition}"
        )
        video_suffix = "subtitles" if edition == "ja" else f"{edition}_subtitles"
        return (
            profile_dir / video_dir / f"{scene}__scene__{video_suffix}.mp4",
            scene_dir / "subtitles" / edition / f"{scene}__scene.{edition}.srt",
        )
    if edition == "none":
        return scene_dir / "without_subtitles" / f"{scene}__scene.mp4", None
    if edition == "ja":
        return (
            scene_dir / "with_subtitles" / f"{scene}__scene__subtitles.mp4",
            scene_dir / "subtitles" / f"{scene}__scene.srt",
        )
    return (
        scene_dir
        / f"with_subtitles_{edition}"
        / f"{scene}__scene__{edition}_subtitles.mp4",
        scene_dir / f"subtitles_{edition}" / f"{scene}__scene.{edition}.srt",
    )


def candidate_edition(row: dict[str, Any], profile: str, edition: str) -> dict:
    return row["edition_matrix"][profile]["editions"][edition]


def load_scene_audio_sidecar(row: dict[str, Any], profile: str) -> dict[str, Any]:
    event = str(row["event"])
    references = row["render_manifest"].get("base_master_manifests")
    reference = references.get(profile) if isinstance(references, dict) else None
    if not isinstance(reference, dict):
        raise ValueError(f"{event} {profile} has no verified base-master sidecar")
    path_text = str(reference.get("path", "")).strip()
    locator = str(reference.get("locator", "")).strip()
    declared_sha256 = str(reference.get("sha256", "")).strip().upper()
    if not path_text or not locator or not re.fullmatch(r"[0-9A-F]{64}", declared_sha256):
        raise ValueError(
            f"{event} {profile} base-master sidecar reference is incomplete"
        )
    sidecar_path = Path(path_text)
    if not sidecar_path.is_absolute():
        sidecar_path = Path(row["render_manifest_path"]).parent / sidecar_path
    sidecar_path = sidecar_path.resolve()
    if not sidecar_path.is_file():
        raise FileNotFoundError(sidecar_path)
    actual_sha256 = file_sha256(sidecar_path)
    if actual_sha256 != declared_sha256:
        raise ValueError(f"{event} {profile} base-master sidecar hash mismatch")
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    embedded = reference.get("manifest")
    if isinstance(embedded, dict) and embedded != payload:
        raise ValueError(f"{event} {profile} embedded sidecar payload mismatch")
    expected = {
        "schema": "magireco-audio-base-master-render-v1",
        "status": "passed",
        "publishable": True,
        "event": event,
        "audio_profile": profile,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ValueError(
                f"{event} {profile} base-master sidecar {field} mismatch"
            )
    try:
        presentation_sample_count = int(payload["presentation_sample_count"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"{event} {profile} sidecar lacks presentation_sample_count"
        ) from error
    if presentation_sample_count <= 0:
        raise ValueError(
            f"{event} {profile} sidecar presentation_sample_count is invalid"
        )
    render_method = payload.get("render_method")
    encoding = (
        render_method.get("output_encoding_contract")
        if isinstance(render_method, dict)
        else None
    )
    if not isinstance(encoding, dict):
        raise ValueError(f"{event} {profile} sidecar lacks encoding provenance")
    normalized_encoding = {
        "codec": str(encoding.get("codec", "")),
        "sample_rate": int(encoding.get("sample_rate", 0)),
        "channels": int(encoding.get("channels", 0)),
        "channel_layout": str(encoding.get("channel_layout", "")),
        "bit_rate": int(encoding.get("bit_rate", 0)),
    }
    if {
        key: normalized_encoding[key]
        for key in ("codec", "sample_rate", "channels", "channel_layout")
    } != {
        "codec": "aac",
        "sample_rate": 48000,
        "channels": 2,
        "channel_layout": "stereo",
    } or not 64_000 <= normalized_encoding["bit_rate"] <= 512_000:
        raise ValueError(f"{event} {profile} sidecar AAC encoding is invalid")
    effective_pcm_sha256 = str(
        payload.get("output_effective_decoded_pcm_sha256", "")
    ).strip().upper()
    if not re.fullmatch(r"[0-9A-F]{64}", effective_pcm_sha256):
        raise ValueError(
            f"{event} {profile} sidecar lacks effective PCM hash"
        )
    output_audio_packet_sha256 = str(
        payload.get("output_audio_packet_sha256", "")
    ).strip().upper()
    if not re.fullmatch(r"[0-9A-F]{64}", output_audio_packet_sha256):
        raise ValueError(
            f"{event} {profile} sidecar lacks audio packet hash"
        )
    output_path = Path(str(payload.get("output", "")))
    if not output_path.is_absolute():
        output_path = sidecar_path.parent / output_path
    output_path = output_path.resolve()
    if not output_path.is_file():
        raise FileNotFoundError(output_path)
    ready = validate_transaction_ready_marker(
        event=event,
        profile=profile,
        base_path=output_path,
        base_manifest_path=sidecar_path,
        base_manifest=payload,
        expected_event_contract_sha256=str(
            payload.get("source_event_contract_sha256", "")
        ),
    )
    return {
        "path": str(sidecar_path),
        "sha256": actual_sha256,
        "locator": locator,
        "presentation_sample_count": presentation_sample_count,
        "encoding": normalized_encoding,
        "effective_pcm_sha256": effective_pcm_sha256,
        "audio_packet_sha256": output_audio_packet_sha256,
        "ready_marker": ready,
    }


def _cue_timeline(cues: list[dict[str, Any]]) -> list[tuple[int, int]]:
    return [
        (int(cue["start_ms"]), int(cue["end_ms"]))
        for cue in cues
    ]


def _validate_event_cues(
    event: str,
    cues_by_language: dict[str, list[dict[str, Any]]],
    duration_ms: int,
) -> None:
    timelines = {
        language: _cue_timeline(cues)
        for language, cues in cues_by_language.items()
    }
    if timelines and len({tuple(value) for value in timelines.values()}) != 1:
        raise ValueError(f"subtitle timeline mismatch: {event}")
    for language, cues in cues_by_language.items():
        for index, cue in enumerate(cues):
            start_ms = int(cue["start_ms"])
            end_ms = int(cue["end_ms"])
            if start_ms < 0 or end_ms <= start_ms:
                raise ValueError(
                    f"{event} {language} cue {index} has invalid timing"
                )
            if end_ms > duration_ms + 50:
                raise ValueError(
                    f"{event} {language} cue {index} exceeds event duration"
                )


def _timeline_summary(
    path: Path,
    ffprobe: str,
    *,
    duration_ms: int,
    frame_rate: str,
    label: str,
) -> dict[str, Any]:
    return dict(
        probe_video_timeline(
            path,
            ffprobe,
            expected_duration_ms=duration_ms,
            expected_frame_rate=frame_rate,
            label=label,
        )
    )


def audio_presentation_audit(
    path: Path,
    media_probe: dict[str, Any],
    video_timeline: dict[str, Any],
    ffprobe: str,
    ffmpeg: str,
    *,
    expected_samples: int | None = None,
) -> dict[str, Any]:
    audio_streams = [
        stream
        for stream in media_probe.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise RuntimeError(f"{path} must contain exactly one audio stream")
    video_samples = video_presentation_sample_count(
        frame_count=int(video_timeline["frame_count"]),
        frame_rate=str(video_timeline["frame_rate"]),
    )
    if expected_samples is None:
        expected_samples = video_samples
    if expected_samples != video_samples:
        raise RuntimeError(
            f"{path} sidecar audio samples {expected_samples} != "
            f"video presentation samples {video_samples}"
        )
    packet_timeline = audio_gate._audio_packet_timeline(
        output=path,
        audio_stream=audio_streams[0],
        expected_samples=expected_samples,
        ffprobe=ffprobe,
    )
    effective_pcm = audio_gate._effective_decoded_pcm_audit(
        output=path,
        expected_samples=expected_samples,
        ffmpeg=ffmpeg,
    )
    return {
        "expected_presentation_samples": expected_samples,
        "packet_frame_timeline": packet_timeline,
        "effective_decoded_pcm": effective_pcm,
    }


def audit_audio_only_master(
    path: Path,
    expected_samples: int,
    target_bit_rate: int,
    ffprobe: str,
    ffmpeg: str,
) -> dict[str, Any]:
    payload = probe(path, ffprobe)
    audio_streams = [
        stream
        for stream in payload.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise RuntimeError(f"{path} scene audio master lacks one audio stream")
    audio = audio_streams[0]
    if (
        audio.get("codec_name") != "aac"
        or str(audio.get("sample_rate")) != "48000"
        or int(audio.get("channels", 0)) != 2
        or str(audio.get("channel_layout")) != "stereo"
    ):
        raise RuntimeError(f"{path} scene audio master encoding signature changed")
    try:
        actual_bit_rate = int(audio["bit_rate"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"{path} scene audio master lacks bitrate") from error
    tolerance = max(2_000, round(target_bit_rate * 0.10))
    if abs(actual_bit_rate - target_bit_rate) > tolerance:
        raise RuntimeError(
            f"{path} AAC bitrate {actual_bit_rate} is outside target "
            f"{target_bit_rate} +/- {tolerance}"
        )
    packet_timeline = audio_gate._audio_packet_timeline(
        output=path,
        audio_stream=audio,
        expected_samples=expected_samples,
        ffprobe=ffprobe,
    )
    effective_pcm = audio_gate._effective_decoded_pcm_audit(
        output=path,
        expected_samples=expected_samples,
        ffmpeg=ffmpeg,
    )
    return {
        "expected_presentation_samples": expected_samples,
        "target_bit_rate": target_bit_rate,
        "actual_bit_rate": actual_bit_rate,
        "audio_packet_sha256": audio_hash(path, ffmpeg),
        "packet_frame_timeline": packet_timeline,
        "effective_decoded_pcm": effective_pcm,
    }


def _published_release_path(
    path: Path, *, staging_scene_dir: Path, published_scene_dir: Path
) -> str:
    """Return the post-promotion path for a file written in staging."""

    resolved = path.resolve()
    try:
        relative = resolved.relative_to(staging_scene_dir.resolve())
    except ValueError:
        return str(resolved)
    return str(published_scene_dir.resolve() / relative)


def _promote_scene_release(
    *,
    staging_scene_dir: Path,
    published_scene_dir: Path,
    overwrite: bool,
) -> None:
    """Promote a complete same-volume scene directory with rollback."""

    ready_path = staging_scene_dir / "READY.json"
    if not ready_path.is_file():
        raise RuntimeError("staged scene release lacks READY.json")

    previous_dir: Path | None = None
    if published_scene_dir.exists():
        if not overwrite:
            raise FileExistsError(
                "scene release already exists; pass --overwrite: "
                f"{published_scene_dir}"
            )
        previous_dir = published_scene_dir.parent / (
            f".{published_scene_dir.name}.previous-{uuid.uuid4().hex}"
        )
        published_scene_dir.replace(previous_dir)

    try:
        staging_scene_dir.replace(published_scene_dir)
    except BaseException:
        if previous_dir is not None and not published_scene_dir.exists():
            previous_dir.replace(published_scene_dir)
        raise
    if previous_dir is not None:
        shutil.rmtree(previous_dir, ignore_errors=True)


def _build_verified_scene_in_staging(
    scene: str,
    selected: list[dict[str, Any]],
    scene_dir: Path,
    published_scene_dir: Path,
    manifest_root: Path | None,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict[str, Any]:
    """Build the exact 2 audio profiles x 3 subtitle scene matrix.

    Source event order is deliberately the caller's explicit ``--event``
    order.  Video is packet-copy concatenated without scaling.  Independent
    per-event AAC streams are decoded only through their sidecar-bound
    effective presentation samples, concatenated as PCM, and encoded once per
    audio profile so intermediate encoder priming/padding cannot leak across
    scene boundaries.  READY is created atomically and last after all gates.
    Files are written below ``scene_dir`` while serialized paths already name
    ``published_scene_dir``; promotion therefore never rewrites hashed files.
    """

    if len(selected) < 2:
        raise ValueError("scene edition needs at least two events")
    event_names = [str(row["event"]) for row in selected]
    if len(set(event_names)) != len(event_names):
        raise ValueError(f"scene has duplicate explicit events: {event_names}")

    requested_editions = list(SUPPORTED_EDITIONS)
    requested_profiles = list(AUDIO_PROFILES)
    matrix_keys = [
        (profile, edition)
        for profile in requested_profiles
        for edition in requested_editions
    ]
    audit_dir = scene_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    ready_path = scene_dir / "READY.json"

    def publish_path(path: Path) -> str:
        return _published_release_path(
            path,
            staging_scene_dir=scene_dir,
            published_scene_dir=published_scene_dir,
        )

    source_rows: list[dict[str, Any]] = []
    expected_signature: dict[str, Any] | None = None
    expected_frame_rate = ""
    offset_ms = 0
    offset_samples = 0
    combined_cues_by_language: dict[str, list[dict[str, Any]]] = {
        edition: [] for edition in requested_editions if edition != "none"
    }
    scene_audio_segments: dict[str, list[dict[str, Any]]] = {
        profile: [] for profile in requested_profiles
    }
    scene_audio_encoding: dict[str, dict[str, Any]] = {}

    for order, row in enumerate(selected, start=1):
        event = str(row["event"])
        missing_profiles = [
            profile
            for profile in requested_profiles
            if profile not in row.get("edition_matrix", {})
        ]
        missing_editions = [
            f"{profile}.{edition}"
            for profile in requested_profiles
            if profile in row.get("edition_matrix", {})
            for edition in requested_editions
            if edition
            not in row["edition_matrix"][profile].get("editions", {})
        ]
        if missing_profiles or missing_editions:
            raise ValueError(
                f"{event} is missing profiles={missing_profiles}, "
                f"editions={missing_editions}"
            )

        render_manifest_path = Path(row["render_manifest_path"])
        refreshed_render_manifest = json.loads(
            render_manifest_path.read_text(encoding="utf-8")
        )
        if refreshed_render_manifest != row["render_manifest"]:
            raise ValueError(
                f"{event} render manifest changed after input discovery"
            )
        qa_provenance = series_gate.validate_qa_binding(row)
        render_source_audit = series_gate.validate_source_render_manifest(
            row,
            requested_profiles,
            requested_editions,
            ffmpeg,
            strict=True,
        )
        event_contract = load_event_presentation_contract(row)
        edition_probes = {
            key: probe(candidate_edition(row, *key)["video_path"], ffprobe)
            for key in matrix_keys
        }
        edition_signatures = {
            key: stream_signature(value)
            for key, value in edition_probes.items()
        }
        event_signature = edition_signatures[(AUDIO_PROFILES[0], "none")]
        if any(value != event_signature for value in edition_signatures.values()):
            raise ValueError(f"edition stream mismatch: {event}")
        if expected_signature is None:
            expected_signature = event_signature
            expected_frame_rate = str(event_signature["video"]["r_frame_rate"])
        elif event_signature != expected_signature:
            raise ValueError(f"scene native stream signature mismatch: {event}")
        try:
            contract_rate = Fraction(event_contract["frame_rate"])
            stream_rate = Fraction(str(event_signature["video"]["r_frame_rate"]))
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError(f"{event} has an invalid native frame rate") from error
        if contract_rate != stream_rate:
            raise ValueError(f"{event} source contract frame rate mismatch")

        duration_ms = int(event_contract["duration_ms"])
        if duration_ms <= 0:
            raise ValueError(f"{event} has a non-positive duration")
        for key, payload in edition_probes.items():
            actual_duration_ms = round(float(payload["format"]["duration"]) * 1000)
            if abs(actual_duration_ms - duration_ms) > 50:
                raise ValueError(
                    f"edition duration mismatch: {event} {key[0]}.{key[1]}"
                )

        timeline_audits = {
            key: _timeline_summary(
                candidate_edition(row, *key)["video_path"],
                ffprobe,
                duration_ms=duration_ms,
                frame_rate=expected_frame_rate,
                label=f"{event} {key[0]}.{key[1]}",
            )
            for key in matrix_keys
        }
        if len(
            {
                str(value["timeline_sha256"])
                for value in timeline_audits.values()
            }
        ) != 1:
            raise ValueError(f"{event} six editions have different video timelines")

        sidecars = {
            profile: load_scene_audio_sidecar(row, profile)
            for profile in requested_profiles
        }
        actual_frame_count = int(
            timeline_audits[(AUDIO_PROFILES[0], "none")]["frame_count"]
        )
        if actual_frame_count != int(event_contract["frame_count"]):
            raise ValueError(f"{event} frame count differs from source contract")
        event_video_sample_count = video_presentation_sample_count(
            frame_count=actual_frame_count,
            frame_rate=str(event_contract["frame_rate"]),
        )
        if event_video_sample_count != int(
            event_contract["presentation_sample_count"]
        ):
            raise ValueError(
                f"{event} video samples differ from source presentation contract"
            )
        for profile, sidecar in sidecars.items():
            if sidecar["presentation_sample_count"] != event_video_sample_count:
                raise ValueError(
                    f"{event} {profile} sidecar samples do not match video timeline"
                )
            encoding = sidecar["encoding"]
            if profile not in scene_audio_encoding:
                scene_audio_encoding[profile] = encoding
            elif scene_audio_encoding[profile] != encoding:
                raise ValueError(
                    f"{event} {profile} AAC encoding contract changed within scene"
                )
        event_start_ms = round(offset_samples / 48)
        event_end_ms = round((offset_samples + event_video_sample_count) / 48)
        if event_start_ms != offset_ms:
            raise RuntimeError("internal cumulative scene timeline drift")
        cumulative_duration_ms = event_end_ms - event_start_ms

        audio_packet_by_key = {
            key: audio_hash(candidate_edition(row, *key)["video_path"], ffmpeg)
            for key in matrix_keys
        }
        audio_presentation_by_key = {
            key: audio_presentation_audit(
                candidate_edition(row, *key)["video_path"],
                edition_probes[key],
                timeline_audits[key],
                ffprobe,
                ffmpeg,
                expected_samples=sidecars[key[0]][
                    "presentation_sample_count"
                ],
            )
            for key in matrix_keys
        }
        decoded_pcm_by_key = {
            key: str(
                value["effective_decoded_pcm"]["pcm_sha256"]
            )
            for key, value in audio_presentation_by_key.items()
        }
        video_packet_by_key = {
            key: series_gate.video_packet_hash(
                candidate_edition(row, *key)["video_path"], ffmpeg
            )
            for key in matrix_keys
        }
        for profile in requested_profiles:
            if len(
                {
                    audio_packet_by_key[(profile, edition)]
                    for edition in requested_editions
                }
            ) != 1:
                raise ValueError(
                    f"{event} {profile} editions have different audio packets"
                )
            if len(
                {
                    decoded_pcm_by_key[(profile, edition)]
                    for edition in requested_editions
                }
            ) != 1:
                raise ValueError(
                    f"{event} {profile} editions have different decoded PCM"
                )
            if len(
                {
                    audio_presentation_by_key[(profile, edition)][
                        "packet_frame_timeline"
                    ]["timeline_sha256"]
                    for edition in requested_editions
                }
            ) != 1:
                raise ValueError(
                    f"{event} {profile} editions have different audio timelines"
                )
        if len(
            {
                value["packet_frame_timeline"]["timeline_sha256"]
                for value in audio_presentation_by_key.values()
            }
        ) != 1:
            raise ValueError(
                f"{event} with_bgm/no_bgm have different audio timelines"
            )
        for edition in requested_editions:
            if len(
                {
                    video_packet_by_key[(profile, edition)]
                    for profile in requested_profiles
                }
            ) != 1:
                raise ValueError(
                    f"{event} {edition} video packets differ by audio profile"
                )
            if len(
                {
                    timeline_audits[(profile, edition)]["timeline_sha256"]
                    for profile in requested_profiles
                }
            ) != 1:
                raise ValueError(
                    f"{event} {edition} video timeline differs by audio profile"
                )
        if len(
            {
                audio_packet_by_key[(profile, "none")]
                for profile in requested_profiles
            }
        ) != 2:
            raise ValueError(f"{event} with_bgm/no_bgm audio packets are identical")
        if len(
            {
                decoded_pcm_by_key[(profile, "none")]
                for profile in requested_profiles
            }
        ) != 2:
            raise ValueError(f"{event} with_bgm/no_bgm decoded PCM is identical")
        for profile in requested_profiles:
            if decoded_pcm_by_key[(profile, "none")] != sidecars[profile][
                "effective_pcm_sha256"
            ]:
                raise ValueError(
                    f"{event} {profile} effective PCM differs from sidecar"
                )
            if audio_packet_by_key[(profile, "none")] != sidecars[profile][
                "audio_packet_sha256"
            ]:
                raise ValueError(
                    f"{event} {profile} audio packets differ from sidecar"
                )
            scene_audio_segments[profile].append(
                {
                    "event": event,
                    "path": candidate_edition(row, profile, "none")[
                        "video_path"
                    ],
                    "presentation_sample_count": sidecars[profile][
                        "presentation_sample_count"
                    ],
                    "sidecar": sidecars[profile]["path"],
                    "sidecar_sha256": sidecars[profile]["sha256"],
                }
            )

        event_cues: dict[str, list[dict[str, Any]]] = {}
        subtitle_source_audit: dict[str, dict[str, str]] = {}
        for language in combined_cues_by_language:
            subtitle_paths = [
                candidate_edition(row, profile, language)["subtitle_path"]
                for profile in requested_profiles
            ]
            if not all(isinstance(path, Path) for path in subtitle_paths):
                raise ValueError(f"{event} {language} subtitle path is missing")
            subtitle_hashes = {file_sha256(path) for path in subtitle_paths}
            if len(subtitle_hashes) != 1:
                raise ValueError(
                    f"{event} {language} subtitle differs by audio profile"
                )
            subtitle_path = subtitle_paths[0]
            cues = shifted_srt_cues(
                subtitle_path.read_text(encoding="utf-8"), 0
            )
            expected_cues = audited_edition_plan_cues(
                row["render_manifest"], event=event, language=language
            )
            validate_srt_cues_against_expected(
                actual=cues,
                expected=expected_cues,
                label=f"{event} {language}",
            )
            event_cues[language] = cues
            combined_cues_by_language[language].extend(
                {
                    **cue,
                    "start_ms": int(cue["start_ms"]) + offset_ms,
                    "end_ms": int(cue["end_ms"]) + offset_ms,
                }
                for cue in cues
            )
            subtitle_source_audit[language] = {
                "path": str(subtitle_path),
                "sha256": next(iter(subtitle_hashes)),
            }
        _validate_event_cues(event, event_cues, duration_ms)

        edition_source_audit: dict[str, dict[str, Any]] = {}
        for profile in requested_profiles:
            profile_rows: dict[str, Any] = {}
            for edition in requested_editions:
                source = candidate_edition(row, profile, edition)
                source_video = source["video_path"]
                source_subtitle = source["subtitle_path"]
                profile_rows[edition] = {
                    "video": str(source_video),
                    "video_sha256": file_sha256(source_video),
                    "video_packet_sha256": video_packet_by_key[(profile, edition)],
                    "video_timeline_sha256": timeline_audits[(profile, edition)][
                        "timeline_sha256"
                    ],
                    "audio_packet_sha256": audio_packet_by_key[(profile, edition)],
                    "decoded_pcm_sha256": decoded_pcm_by_key[(profile, edition)],
                    "audio_timeline_sha256": audio_presentation_by_key[
                        (profile, edition)
                    ]["packet_frame_timeline"]["timeline_sha256"],
                    "audio_presentation_samples": audio_presentation_by_key[
                        (profile, edition)
                    ]["expected_presentation_samples"],
                    "subtitles": str(source_subtitle) if source_subtitle else "",
                    "subtitle_sha256": (
                        file_sha256(source_subtitle) if source_subtitle else ""
                    ),
                }
            edition_source_audit[profile] = {
                "audio_packet_sha256": audio_packet_by_key[(profile, "none")],
                "decoded_pcm_sha256": decoded_pcm_by_key[(profile, "none")],
                "editions": profile_rows,
            }

        production_manifest = manifest_path_for_event(manifest_root, event)
        source_rows.append(
            {
                "order": order,
                "event": event,
                "start_ms": offset_ms,
                "end_ms": event_end_ms,
                "duration_ms": cumulative_duration_ms,
                "presentation_sample_count": event_video_sample_count,
                "subtitle_cues_ja": len(event_cues.get("ja", [])),
                "subtitle_cues_zh": len(event_cues.get("zh", [])),
                "render_manifest": row["render_manifest_path"],
                "render_manifest_sha256": render_source_audit[
                    "render_manifest_sha256"
                ],
                "source_event_manifest": str(event_contract["path"]),
                "source_event_manifest_sha256": event_contract["sha256"],
                "qa_report": qa_provenance["path"],
                "qa_report_sha256": qa_provenance["sha256"],
                "qa_locator": qa_provenance["locator"],
                "qa_row_sha256": qa_provenance["row_sha256"],
                "production_manifest": production_manifest,
                "production_manifest_sha256": (
                    file_sha256(Path(production_manifest))
                    if production_manifest
                    else ""
                ),
                "subtitles_json": json.dumps(
                    subtitle_source_audit, ensure_ascii=False, sort_keys=True
                ),
                "edition_matrix_json": json.dumps(
                    edition_source_audit, ensure_ascii=False, sort_keys=True
                ),
                "audio_sidecars_json": json.dumps(
                    sidecars, ensure_ascii=False, sort_keys=True
                ),
            }
        )
        offset_samples += event_video_sample_count
        offset_ms = event_end_ms

    assert expected_signature is not None
    if len(
        {
            json.dumps(value, sort_keys=True)
            for value in scene_audio_encoding.values()
        }
    ) != 1:
        raise ValueError(
            "with_bgm/no_bgm sidecars declare different AAC encoding contracts"
        )
    edition_outputs: dict[str, dict[str, dict[str, Path | None]]] = {}
    concat_lists: dict[tuple[str, str], Path] = {}
    expected_concat_decoded_video: dict[tuple[str, str], str] = {}
    expected_concat_audio_packets: dict[tuple[str, str], str] = {}
    canonical_video_by_edition: dict[str, Path] = {}
    canonical_video_packet_by_edition: dict[str, str] = {}
    canonical_video_timeline_by_edition: dict[str, dict[str, Any]] = {}
    canonical_profile = requested_profiles[0]
    for edition in requested_editions:
        sources = [
            candidate_edition(row, canonical_profile, edition)["video_path"]
            for row in selected
        ]
        list_path = audit_dir / f"video__{edition}.ffconcat"
        video_only = (
            audit_dir / "video_only" / f"{scene}__{edition}__video_only.mp4"
        )
        concat_video_copy(sources, list_path, video_only, ffmpeg, overwrite)
        verify_ffconcat_order(list_path, sources)
        expected_decoded_video = concat_decoded_hash(
            list_path, "video", ffmpeg
        )
        if decoded_video_hash(video_only, ffmpeg) != expected_decoded_video:
            raise RuntimeError(
                f"{scene} {edition} video-only concat changed ordered frames"
            )
        video_packet_sha256 = series_gate.video_packet_hash(video_only, ffmpeg)
        video_timeline = _timeline_summary(
            video_only,
            ffprobe,
            duration_ms=offset_ms,
            frame_rate=expected_frame_rate,
            label=f"{scene} {edition} canonical video-only concat",
        )
        canonical_video_by_edition[edition] = video_only
        canonical_video_packet_by_edition[edition] = video_packet_sha256
        canonical_video_timeline_by_edition[edition] = video_timeline
        for profile in requested_profiles:
            key = (profile, edition)
            concat_lists[key] = list_path
            expected_concat_decoded_video[key] = expected_decoded_video

    scene_audio_masters: dict[str, Path] = {}
    scene_audio_provenance: dict[str, dict[str, Any]] = {}
    scene_audio_master_audits: dict[str, dict[str, Any]] = {}
    scene_audio_master_audit_paths: dict[str, Path] = {}
    for profile in requested_profiles:
        encoding = scene_audio_encoding[profile]
        target_bit_rate = int(encoding["bit_rate"])
        audio_master = audit_dir / "audio_master" / f"{scene}__{profile}.m4a"
        provenance = build_scene_audio_master(
            scene_audio_segments[profile],
            audio_master,
            target_bit_rate,
            ffmpeg,
            overwrite,
        )
        expected_samples = sum(
            int(row["presentation_sample_count"])
            for row in scene_audio_segments[profile]
        )
        if provenance["presentation_sample_count"] != expected_samples:
            raise RuntimeError(
                f"{scene} {profile} audio provenance sample total mismatch"
            )
        if expected_samples != offset_samples:
            raise RuntimeError(
                f"{scene} {profile} audio samples do not match video timeline"
            )
        audit = audit_audio_only_master(
            audio_master,
            expected_samples,
            target_bit_rate,
            ffprobe,
            ffmpeg,
        )
        audit_path = (
            audit_dir / "audio_master" / f"{scene}__{profile}.audit.json"
        )
        audit_payload = {
            "schema": "magireco-scene-audio-master-audit-v1",
            "status": "passed",
            "scene": scene,
            "audio_profile": profile,
            "output": publish_path(audio_master),
            "output_sha256": file_sha256(audio_master),
            "encoding_contract": encoding,
            "reencode_provenance": provenance,
            "qa": audit,
        }
        audit_path.write_text(
            json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        scene_audio_masters[profile] = audio_master
        scene_audio_provenance[profile] = provenance
        scene_audio_master_audits[profile] = audit
        scene_audio_master_audit_paths[profile] = audit_path
    if len(
        {
            audit["expected_presentation_samples"]
            for audit in scene_audio_master_audits.values()
        }
    ) != 1:
        raise RuntimeError("scene audio profiles have different sample totals")
    if len(
        {
            audit["audio_packet_sha256"]
            for audit in scene_audio_master_audits.values()
        }
    ) != 2:
        raise RuntimeError("scene audio profile packets are identical")
    if len(
        {
            audit["effective_decoded_pcm"]["pcm_sha256"]
            for audit in scene_audio_master_audits.values()
        }
    ) != 2:
        raise RuntimeError("scene audio profile effective PCM is identical")

    written_subtitles: set[str] = set()
    for profile in requested_profiles:
        profile_outputs: dict[str, dict[str, Path | None]] = {}
        for edition in requested_editions:
            video_output, subtitle_output = scene_edition_paths(
                scene_dir, scene, edition, profile
            )
            mux_scene_av_copy(
                canonical_video_by_edition[edition],
                scene_audio_masters[profile],
                video_output,
                ffmpeg,
                overwrite,
            )
            key = (profile, edition)
            expected_concat_audio_packets[key] = scene_audio_master_audits[
                profile
            ]["audio_packet_sha256"]
            if subtitle_output is not None and edition not in written_subtitles:
                subtitle_output.parent.mkdir(parents=True, exist_ok=True)
                write_srt(subtitle_output, combined_cues_by_language[edition])
                validate_written_srt_round_trip(
                    subtitle_output,
                    combined_cues_by_language[edition],
                    label=f"{scene} {edition}",
                )
                written_subtitles.add(edition)
            profile_outputs[edition] = {
                "video": video_output,
                "subtitles": subtitle_output,
            }
        edition_outputs[profile] = profile_outputs

    index_path = audit_dir / "scene_index.csv"
    write_csv(
        index_path,
        source_rows,
        [
            "order",
            "event",
            "start_ms",
            "end_ms",
            "duration_ms",
            "presentation_sample_count",
            "subtitle_cues_ja",
            "subtitle_cues_zh",
            "render_manifest",
            "render_manifest_sha256",
            "source_event_manifest",
            "source_event_manifest_sha256",
            "qa_report",
            "qa_report_sha256",
            "qa_locator",
            "qa_row_sha256",
            "production_manifest",
            "production_manifest_sha256",
            "subtitles_json",
            "edition_matrix_json",
            "audio_sidecars_json",
        ],
    )

    errors: list[str] = []
    for row in source_rows:
        if file_sha256(Path(row["render_manifest"])) != row["render_manifest_sha256"]:
            errors.append(f"{row['event']}_render_manifest_changed_during_build")
        if file_sha256(Path(row["source_event_manifest"])) != row[
            "source_event_manifest_sha256"
        ]:
            errors.append(f"{row['event']}_source_event_manifest_changed_during_build")
        if file_sha256(Path(row["qa_report"])) != row["qa_report_sha256"]:
            errors.append(f"{row['event']}_qa_report_changed_during_build")
        if row["production_manifest"] and file_sha256(
            Path(row["production_manifest"])
        ) != row["production_manifest_sha256"]:
            errors.append(f"{row['event']}_production_manifest_changed_during_build")
        source_matrix = json.loads(row["edition_matrix_json"])
        for profile, profile_row in source_matrix.items():
            for edition, edition_row in profile_row["editions"].items():
                source_video = Path(edition_row["video"])
                if file_sha256(source_video) != edition_row["video_sha256"]:
                    errors.append(
                        f"{row['event']}_{profile}.{edition}_source_video_changed"
                    )
                source_subtitle = str(edition_row.get("subtitles", ""))
                if source_subtitle and file_sha256(
                    Path(source_subtitle)
                ) != edition_row["subtitle_sha256"]:
                    errors.append(
                        f"{row['event']}_{profile}.{edition}_source_subtitle_changed"
                    )
        source_sidecars = json.loads(row["audio_sidecars_json"])
        for profile, sidecar in source_sidecars.items():
            if file_sha256(Path(sidecar["path"])) != sidecar["sha256"]:
                errors.append(
                    f"{row['event']}_{profile}_audio_sidecar_changed"
                )
            ready = sidecar["ready_marker"]
            if file_sha256(Path(ready["path"])) != ready["sha256"]:
                errors.append(
                    f"{row['event']}_{profile}_audio_ready_marker_changed"
                )

    output_probes: dict[tuple[str, str], dict[str, Any]] = {}
    output_timelines: dict[tuple[str, str], dict[str, Any]] = {}
    output_audio_packets: dict[tuple[str, str], str] = {}
    output_decoded_pcm: dict[tuple[str, str], str] = {}
    output_decoded_video: dict[tuple[str, str], str] = {}
    output_audio_presentation: dict[tuple[str, str], dict[str, Any]] = {}
    output_audio_audit_files: dict[tuple[str, str], Path] = {}
    output_video_packets: dict[tuple[str, str], str] = {}
    output_files: dict[tuple[str, str], str] = {}
    output_subtitles: dict[tuple[str, str], str] = {}
    for key in matrix_keys:
        profile, edition = key
        output_row = edition_outputs[profile][edition]
        video_output = output_row["video"]
        assert isinstance(video_output, Path)
        try:
            verify_ffconcat_order(
                concat_lists[key],
                [
                    candidate_edition(
                        row, canonical_profile, edition
                    )["video_path"]
                    for row in selected
                ],
            )
        except ValueError as error:
            errors.append(f"{profile}.{edition}_concat_order_changed: {error}")
        payload = probe(video_output, ffprobe)
        output_probes[key] = payload
        if stream_signature(payload) != expected_signature:
            errors.append(f"{profile}.{edition}_native_stream_signature_changed")
        actual_duration_ms = round(float(payload["format"]["duration"]) * 1000)
        if abs(actual_duration_ms - offset_ms) > max(50, len(selected) * 35):
            errors.append(f"{profile}.{edition}_duration_mismatch")
        try:
            output_timelines[key] = _timeline_summary(
                video_output,
                ffprobe,
                duration_ms=offset_ms,
                frame_rate=expected_frame_rate,
                label=f"{scene} {profile}.{edition}",
            )
        except RuntimeError as error:
            errors.append(f"{profile}.{edition}_video_timeline_failed: {error}")
            output_timelines[key] = {"status": "failed", "error": str(error)}
        output_audio_packets[key] = audio_hash(video_output, ffmpeg)
        output_decoded_video[key] = decoded_video_hash(video_output, ffmpeg)
        output_video_packets[key] = series_gate.video_packet_hash(video_output, ffmpeg)
        if key in output_timelines and output_timelines[key].get("status") == "passed":
            try:
                output_audio_presentation[key] = audio_presentation_audit(
                    video_output,
                    payload,
                    output_timelines[key],
                    ffprobe,
                    ffmpeg,
                )
                output_decoded_pcm[key] = str(
                    output_audio_presentation[key]["effective_decoded_pcm"][
                        "pcm_sha256"
                    ]
                )
                audio_audit_path = (
                    audit_dir / f"audio_timeline__{profile}__{edition}.json"
                )
                audio_audit_path.write_text(
                    json.dumps(
                        output_audio_presentation[key],
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                output_audio_audit_files[key] = audio_audit_path
            except RuntimeError as error:
                errors.append(
                    f"{profile}.{edition}_audio_timeline_failed: {error}"
                )
                output_audio_presentation[key] = {
                    "status": "failed",
                    "error": str(error),
                }
                output_decoded_pcm[key] = ""
        else:
            output_audio_presentation[key] = {
                "status": "failed",
                "error": "video timeline prerequisite failed",
            }
            output_decoded_pcm[key] = ""
        output_files[key] = file_sha256(video_output)
        subtitle_path = output_row["subtitles"]
        output_subtitles[key] = (
            file_sha256(subtitle_path)
            if isinstance(subtitle_path, Path)
            else ""
        )
        if output_decoded_video[key] != expected_concat_decoded_video[key]:
            errors.append(f"{profile}.{edition}_video_not_exact_ordered_content")
        if output_video_packets[key] != canonical_video_packet_by_edition[edition]:
            errors.append(f"{profile}.{edition}_video_packet_changed_during_mux")
        if str(output_timelines[key].get("timeline_sha256", "")) != str(
            canonical_video_timeline_by_edition[edition].get(
                "timeline_sha256", ""
            )
        ):
            errors.append(f"{profile}.{edition}_video_timeline_changed_during_mux")
        if output_audio_packets[key] != expected_concat_audio_packets[key]:
            errors.append(f"{profile}.{edition}_audio_packet_changed_during_mux")
        if output_decoded_pcm[key] != scene_audio_master_audits[profile][
            "effective_decoded_pcm"
        ]["pcm_sha256"]:
            errors.append(f"{profile}.{edition}_effective_pcm_changed_during_mux")
        output_audio_timeline_hash = str(
            output_audio_presentation[key]
            .get("packet_frame_timeline", {})
            .get("timeline_sha256", "")
        )
        if output_audio_timeline_hash != scene_audio_master_audits[profile][
            "packet_frame_timeline"
        ]["timeline_sha256"]:
            errors.append(f"{profile}.{edition}_audio_timeline_changed_during_mux")

    for profile in requested_profiles:
        if len(
            {output_audio_packets[(profile, edition)] for edition in requested_editions}
        ) != 1:
            errors.append(f"{profile}_subtitle_edition_audio_packet_mismatch")
        if len(
            {output_decoded_pcm[(profile, edition)] for edition in requested_editions}
        ) != 1:
            errors.append(f"{profile}_subtitle_edition_decoded_pcm_mismatch")
        profile_audio_timeline_hashes = {
            str(
                output_audio_presentation[(profile, edition)]
                .get("packet_frame_timeline", {})
                .get("timeline_sha256", "")
            )
            for edition in requested_editions
        }
        if "" in profile_audio_timeline_hashes or len(
            profile_audio_timeline_hashes
        ) != 1:
            errors.append(f"{profile}_subtitle_edition_audio_timeline_mismatch")
    if len({output_audio_packets[(profile, "none")] for profile in requested_profiles}) != 2:
        errors.append("audio_master_profiles_packet_identical")
    if len({output_decoded_pcm[(profile, "none")] for profile in requested_profiles}) != 2:
        errors.append("audio_master_profiles_decoded_pcm_identical")
    all_audio_timeline_hashes = {
        str(
            value.get("packet_frame_timeline", {}).get("timeline_sha256", "")
        )
        for value in output_audio_presentation.values()
    }
    if "" in all_audio_timeline_hashes or len(all_audio_timeline_hashes) != 1:
        errors.append("six_output_audio_timelines_differ")
    for edition in requested_editions:
        if len(
            {output_video_packets[(profile, edition)] for profile in requested_profiles}
        ) != 1:
            errors.append(f"{edition}_video_packet_mismatch_between_audio_profiles")
        timeline_hashes = {
            str(output_timelines[(profile, edition)].get("timeline_sha256", ""))
            for profile in requested_profiles
        }
        if "" in timeline_hashes or len(timeline_hashes) != 1:
            errors.append(f"{edition}_video_timeline_mismatch_between_audio_profiles")
    all_timeline_hashes = {
        str(value.get("timeline_sha256", "")) for value in output_timelines.values()
    }
    if "" in all_timeline_hashes or len(all_timeline_hashes) != 1:
        errors.append("six_output_video_timelines_differ")

    output_manifest_matrix: dict[str, dict[str, Any]] = {}
    output_sha_matrix: dict[str, dict[str, Any]] = {}
    for profile in requested_profiles:
        manifest_editions: dict[str, dict[str, Any]] = {}
        sha_editions: dict[str, dict[str, str]] = {}
        for edition in requested_editions:
            key = (profile, edition)
            output_row = edition_outputs[profile][edition]
            video_output = output_row["video"]
            subtitle_output = output_row["subtitles"]
            assert isinstance(video_output, Path)
            manifest_editions[edition] = {
                "language": edition,
                "video": publish_path(video_output),
                "subtitles": (
                    publish_path(subtitle_output)
                    if isinstance(subtitle_output, Path)
                    else ""
                ),
                "video_sha256": output_files[key],
                "video_packet_sha256": output_video_packets[key],
                "video_timeline_sha256": output_timelines[key].get(
                    "timeline_sha256", ""
                ),
                "audio_sha256": output_audio_packets[key],
                "decoded_pcm_sha256": output_decoded_pcm[key],
                "decoded_video_sha256": output_decoded_video[key],
                "audio_timeline_sha256": output_audio_presentation[key]
                .get("packet_frame_timeline", {})
                .get("timeline_sha256", ""),
                "audio_timeline_audit": (
                    publish_path(output_audio_audit_files[key])
                    if key in output_audio_audit_files
                    else ""
                ),
                "audio_timeline_audit_sha256": (
                    file_sha256(output_audio_audit_files[key])
                    if key in output_audio_audit_files
                    else ""
                ),
                "subtitle_sha256": output_subtitles[key],
            }
            sha_editions[edition] = {
                "video": output_files[key],
                "video_packet": output_video_packets[key],
                "video_timeline": str(
                    output_timelines[key].get("timeline_sha256", "")
                ),
                "audio_packet": output_audio_packets[key],
                "decoded_pcm": output_decoded_pcm[key],
                "decoded_video": output_decoded_video[key],
                "audio_timeline": str(
                    output_audio_presentation[key]
                    .get("packet_frame_timeline", {})
                    .get("timeline_sha256", "")
                ),
                "audio_timeline_audit": (
                    file_sha256(output_audio_audit_files[key])
                    if key in output_audio_audit_files
                    else ""
                ),
                "subtitles": output_subtitles[key],
            }
        output_manifest_matrix[profile] = {
            "audio_profile": profile,
            "audio_sha256": output_audio_packets[(profile, "none")],
            "decoded_pcm_sha256": output_decoded_pcm[(profile, "none")],
            "editions": manifest_editions,
        }
        output_sha_matrix[profile] = sha_editions

    scene_manifest = {
        "schema": "magireco-scene-editions-v3",
        "legacy_schema_compatible": False,
        "scene": scene,
        "status": "failed" if errors else "passed",
        "errors": errors,
        "publishable": not errors,
        "release_eligible": not errors,
        "direct_stream_copy": False,
        "media_processing": {
            "video": "ordered_packet_copy_concat_then_packet_copy_mux",
            "audio": "sidecar_trimmed_effective_pcm_concat_single_aac_encode",
            "scaling": "forbidden",
        },
        "ordering": "explicit --event order",
        "event_count": len(selected),
        "expected_duration_ms": offset_ms,
        "subtitle_cue_count_by_language": {
            language: len(cues)
            for language, cues in combined_cues_by_language.items()
        },
        "requested_editions": requested_editions,
        "requested_audio_profiles": requested_profiles,
        "stream_signature": expected_signature,
        "outputs": {
            "edition_matrix": output_manifest_matrix,
            "scene_index": publish_path(index_path),
            "audio_masters": {
                profile: {
                    "path": publish_path(scene_audio_masters[profile]),
                    "sha256": file_sha256(scene_audio_masters[profile]),
                    "audit": publish_path(
                        scene_audio_master_audit_paths[profile]
                    ),
                    "audit_sha256": file_sha256(
                        scene_audio_master_audit_paths[profile]
                    ),
                    "encoding_contract": scene_audio_encoding[profile],
                    "reencode_provenance": scene_audio_provenance[profile],
                }
                for profile in requested_profiles
            },
            "canonical_video_only": {
                edition: {
                    "path": publish_path(canonical_video_by_edition[edition]),
                    "sha256": file_sha256(canonical_video_by_edition[edition]),
                    "video_packet_sha256": canonical_video_packet_by_edition[
                        edition
                    ],
                    "video_timeline_sha256": (
                        canonical_video_timeline_by_edition[edition][
                            "timeline_sha256"
                        ]
                    ),
                }
                for edition in requested_editions
            },
            "ffconcat_by_matrix": {
                profile: {
                    edition: {
                        "path": publish_path(concat_lists[(profile, edition)]),
                        "sha256": file_sha256(
                            concat_lists[(profile, edition)]
                        ),
                    }
                    for edition in requested_editions
                }
                for profile in requested_profiles
            },
        },
        "output_sha256": {
            "edition_matrix": output_sha_matrix,
            "scene_index": file_sha256(index_path),
        },
        "probes_by_matrix": {
            profile: {
                edition: output_probes[(profile, edition)]
                for edition in requested_editions
            }
            for profile in requested_profiles
        },
        "video_timeline_audits_by_matrix": {
            profile: {
                edition: output_timelines[(profile, edition)]
                for edition in requested_editions
            }
            for profile in requested_profiles
        },
        "sources": source_rows,
    }
    manifest_path = scene_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(scene_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema": "magireco-scene-build-summary-v3",
        "scene": scene,
        "status": scene_manifest["status"],
        "errors": errors,
        "publishable": not errors,
        "release_eligible": not errors,
        "event_count": len(selected),
        "ordered_events": event_names,
        "duration_ms": offset_ms,
        "requested_editions": requested_editions,
        "requested_audio_profiles": requested_profiles,
        "width": expected_signature["video"]["width"],
        "height": expected_signature["video"]["height"],
        "frame_rate": expected_signature["video"]["r_frame_rate"],
        "audio_sample_rate": expected_signature["audio"]["sample_rate"],
        "audio_channels": expected_signature["audio"]["channels"],
        "manifest": publish_path(manifest_path),
        "manifest_sha256": file_sha256(manifest_path),
        "ready_marker": publish_path(ready_path) if not errors else "",
    }
    summary_path = scene_dir / "scene_editions_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(f"{scene} scene QA failed: {errors}")

    ready_payload = {
        "schema": "magireco-scene-editions-ready-v1",
        "status": "READY",
        "scene": scene,
        "manifest": publish_path(manifest_path),
        "manifest_sha256": file_sha256(manifest_path),
        "summary": publish_path(summary_path),
        "summary_sha256": file_sha256(summary_path),
        "scene_index": publish_path(index_path),
        "scene_index_sha256": file_sha256(index_path),
        "ordered_events": event_names,
        "event_count": len(selected),
        "edition_matrix_sha256": output_sha_matrix,
        "audio_masters": {
            profile: {
                "path": publish_path(scene_audio_masters[profile]),
                "sha256": file_sha256(scene_audio_masters[profile]),
                "audit": publish_path(scene_audio_master_audit_paths[profile]),
                "audit_sha256": file_sha256(
                    scene_audio_master_audit_paths[profile]
                ),
            }
            for profile in requested_profiles
        },
    }
    ready_temp = ready_path.with_suffix(".json.tmp")
    ready_temp.write_text(
        json.dumps(ready_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ready_temp.replace(ready_path)
    return summary


def build_verified_scene(
    scene: str,
    selected: list[dict[str, Any]],
    out_root: Path,
    manifest_root: Path | None,
    ffmpeg: str,
    ffprobe: str,
    overwrite: bool,
) -> dict[str, Any]:
    """Build and transactionally publish one verified scene release.

    A pre-existing release is never used as a work directory.  The complete
    candidate is built in a sibling directory on the same volume and promoted
    only after its READY marker has been written.  A failed build therefore
    leaves every byte of the previous READY release untouched.
    """

    published_scene_dir = resolve_output_child(out_root, scene, label="scene")
    published_ready = published_scene_dir / "READY.json"
    if published_ready.exists() and not overwrite:
        raise FileExistsError(
            "READY scene release already exists; pass --overwrite: "
            f"{published_scene_dir}"
        )
    if published_scene_dir.exists() and not overwrite:
        raise FileExistsError(
            "scene output already exists; pass --overwrite: "
            f"{published_scene_dir}"
        )

    out_root.mkdir(parents=True, exist_ok=True)
    staging_container = Path(
        tempfile.mkdtemp(
            prefix=f".scene-staging-{uuid.uuid4().hex[:12]}-",
            dir=out_root,
        )
    )
    staging_scene_dir = staging_container / "release"
    try:
        summary = _build_verified_scene_in_staging(
            scene,
            selected,
            staging_scene_dir,
            published_scene_dir,
            manifest_root,
            ffmpeg,
            ffprobe,
            True,
        )
        _promote_scene_release(
            staging_scene_dir=staging_scene_dir,
            published_scene_dir=published_scene_dir,
            overwrite=overwrite,
        )
        return summary
    finally:
        shutil.rmtree(staging_container, ignore_errors=True)


def main() -> int:
    args = parse_args()
    # A scene is release metadata, never a caller-controlled relative path.
    # Validate it before either the modern transaction or the legacy branch can
    # create the output root/audit tree.
    scene = validate_output_identifier(args.scene, label="scene")
    if not args.legacy_two_edition:
        requested_editions = normalize_requested_editions(args.editions)
        requested_profiles = normalize_requested_audio_profiles(
            args.audio_profiles
        )
        if set(requested_editions) != set(SUPPORTED_EDITIONS) or set(
            requested_profiles
        ) != set(AUDIO_PROFILES):
            raise SystemExit(
                "verified scene publication requires all none/ja/zh editions "
                "for both with_bgm and no_bgm"
            )
        if len(set(args.event)) != len(args.event):
            raise SystemExit("duplicate --event entries are not allowed")
        input_roots = [Path(path).resolve() for path in args.input_root]
        candidates = discover_events(input_roots, allow_legacy=False)
        missing = [event for event in args.event if event not in candidates]
        if missing:
            raise SystemExit(
                "missing QA-passed verified input events: " + ", ".join(missing)
            )
        manifest_root = (
            Path(args.production_manifest_root).resolve()
            if args.production_manifest_root
            else None
        )
        summary = build_verified_scene(
            scene,
            [candidates[event] for event in args.event],
            Path(args.out_root).resolve(),
            manifest_root,
            args.ffmpeg,
            args.ffprobe,
            args.overwrite,
        )
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    if args.audio_profiles:
        raise SystemExit(
            "--legacy-two-edition cannot relabel audio with --audio-profile"
        )
    requested_editions = normalize_requested_editions(
        args.editions, legacy_compat=True
    )
    input_roots = [Path(path).resolve() for path in args.input_root]
    candidates = discover_events(input_roots)
    missing = [event for event in args.event if event not in candidates]
    if missing:
        raise SystemExit("missing QA-passed input events: " + ", ".join(missing))
    selected = [candidates[event] for event in args.event]
    if len(selected) < 2:
        raise SystemExit("scene edition needs at least two events")
    for row in selected:
        missing_editions = [
            edition
            for edition in requested_editions
            if edition not in row["editions"]
        ]
        if missing_editions:
            raise SystemExit(
                f"{row['event']} is missing requested edition(s): {missing_editions}"
            )

    manifest_root = (
        Path(args.production_manifest_root).resolve()
        if args.production_manifest_root
        else None
    )
    out_root = Path(args.out_root).resolve()
    scene_dir = resolve_output_child(out_root, scene, label="scene")
    audit_dir = scene_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    source_rows: list[dict[str, Any]] = []
    combined_cues_by_language: dict[str, list[dict[str, Any]]] = {
        edition: [] for edition in requested_editions if edition != "none"
    }
    expected_signature: dict[str, Any] | None = None
    offset_ms = 0
    for order, row in enumerate(selected, start=1):
        edition_probes = {
            edition: probe(
                row["editions"][edition]["video_path"], args.ffprobe
            )
            for edition in requested_editions
        }
        edition_signatures = {
            edition: stream_signature(item)
            for edition, item in edition_probes.items()
        }
        without_signature = edition_signatures["none"]
        if any(
            signature != without_signature
            for signature in edition_signatures.values()
        ):
            raise SystemExit(f"edition stream mismatch: {row['event']}")
        if expected_signature is None:
            expected_signature = without_signature
        elif without_signature != expected_signature:
            raise SystemExit(f"scene stream mismatch: {row['event']}")
        duration_ms = round(
            float(edition_probes["none"]["format"]["duration"]) * 1000
        )
        for edition, item in edition_probes.items():
            edition_duration_ms = round(float(item["format"]["duration"]) * 1000)
            if abs(edition_duration_ms - duration_ms) > 50:
                raise SystemExit(
                    f"edition duration mismatch: {row['event']} {edition}"
                )

        event_cues: dict[str, list[dict[str, Any]]] = {}
        for language in combined_cues_by_language:
            subtitle_path = row["editions"][language]["subtitle_path"]
            unshifted = shifted_srt_cues(
                subtitle_path.read_text(encoding="utf-8"), 0
            )
            event_cues[language] = unshifted
            combined_cues_by_language[language].extend(
                {
                    **cue,
                    "start_ms": int(cue["start_ms"]) + offset_ms,
                    "end_ms": int(cue["end_ms"]) + offset_ms,
                }
                for cue in unshifted
            )
        cue_timelines = {
            language: [
                (int(cue["start_ms"]), int(cue["end_ms"])) for cue in cues
            ]
            for language, cues in event_cues.items()
        }
        if cue_timelines and len({tuple(value) for value in cue_timelines.values()}) != 1:
            raise SystemExit(f"subtitle timeline mismatch: {row['event']}")

        edition_source_audit: dict[str, dict[str, str]] = {}
        for edition in requested_editions:
            edition_row = row["editions"][edition]
            subtitle_path = edition_row["subtitle_path"]
            edition_source_audit[edition] = {
                "video": str(edition_row["video_path"]),
                "video_sha256": file_sha256(edition_row["video_path"]),
                "subtitles": str(subtitle_path) if subtitle_path else "",
                "subtitle_sha256": (
                    file_sha256(subtitle_path) if subtitle_path else ""
                ),
            }
        ja_audit = edition_source_audit.get("ja", {})
        source_rows.append(
            {
                "order": order,
                "event": row["event"],
                "start_ms": offset_ms,
                "end_ms": offset_ms + duration_ms,
                "duration_ms": duration_ms,
                "subtitle_cues": len(event_cues.get("ja", [])),
                "without_subtitles": str(row["without_path"]),
                "with_subtitles": str(row["with_path"]),
                "subtitles": str(row["subtitle_path"]),
                "render_manifest": row["render_manifest_path"],
                "production_manifest": manifest_path_for_event(
                    manifest_root, row["event"]
                ),
                "without_sha256": file_sha256(row["without_path"]),
                "with_sha256": ja_audit.get("video_sha256", ""),
                "subtitle_sha256": ja_audit.get("subtitle_sha256", ""),
                "editions_json": json.dumps(
                    edition_source_audit, ensure_ascii=False, sort_keys=True
                ),
            }
        )
        offset_ms += duration_ms

    edition_outputs: dict[str, dict[str, Path | None]] = {}
    for edition in requested_editions:
        video_output, subtitle_output = scene_edition_paths(
            scene_dir, scene, edition
        )
        concat_stem = (
            "without_subtitles"
            if edition == "none"
            else "with_subtitles" if edition == "ja" else f"with_subtitles_{edition}"
        )
        concat_copy(
            [row["editions"][edition]["video_path"] for row in selected],
            audit_dir / f"{concat_stem}.ffconcat",
            video_output,
            args.ffmpeg,
            args.overwrite,
        )
        if subtitle_output is not None:
            subtitle_output.parent.mkdir(parents=True, exist_ok=True)
            write_srt(subtitle_output, combined_cues_by_language[edition])
        edition_outputs[edition] = {
            "video": video_output,
            "subtitles": subtitle_output,
        }
    without_output = edition_outputs["none"]["video"]
    ja_output = edition_outputs.get("ja", {})
    with_output = ja_output.get("video")
    subtitle_output = ja_output.get("subtitles")
    write_csv(
        audit_dir / "scene_index.csv",
        source_rows,
        [
            "order",
            "event",
            "start_ms",
            "end_ms",
            "duration_ms",
            "subtitle_cues",
            "without_subtitles",
            "with_subtitles",
            "subtitles",
            "render_manifest",
            "production_manifest",
            "without_sha256",
            "with_sha256",
            "subtitle_sha256",
            "editions_json",
        ],
    )

    output_probes = {
        edition: probe(row["video"], args.ffprobe)
        for edition, row in edition_outputs.items()
    }
    errors: list[str] = []
    assert expected_signature is not None
    for edition, item in output_probes.items():
        if stream_signature(item) != expected_signature:
            errors.append(f"{edition}_stream_signature_changed")
    output_durations_ms = {
        edition: round(float(item["format"]["duration"]) * 1000)
        for edition, item in output_probes.items()
    }
    without_duration_ms = output_durations_ms["none"]
    tolerance_ms = max(100, len(selected) * 35)
    for edition, duration_ms in output_durations_ms.items():
        if abs(duration_ms - offset_ms) > tolerance_ms:
            errors.append(f"{edition}_duration_mismatch")
    output_audio_hashes = {
        edition: audio_hash(row["video"], args.ffmpeg)
        for edition, row in edition_outputs.items()
    }
    without_audio_hash = output_audio_hashes["none"]
    for edition, value in output_audio_hashes.items():
        if value != without_audio_hash:
            errors.append(f"{edition}_audio_mismatch")

    output_manifest_editions: dict[str, dict[str, str]] = {}
    output_sha256_by_edition: dict[str, dict[str, str]] = {}
    for edition, row in edition_outputs.items():
        video_output = row["video"]
        subtitle_output_for_edition = row["subtitles"]
        output_manifest_editions[edition] = {
            "language": edition,
            "video": str(video_output.resolve()),
            "subtitles": (
                str(subtitle_output_for_edition.resolve())
                if subtitle_output_for_edition is not None
                else ""
            ),
        }
        output_sha256_by_edition[edition] = {
            "video": file_sha256(video_output),
            "subtitles": (
                file_sha256(subtitle_output_for_edition)
                if subtitle_output_for_edition is not None
                else ""
            ),
        }

    scene_manifest = {
        "schema": "magireco-scene-editions-v2",
        "legacy_schema_compatible": "ja" in output_manifest_editions,
        "scene": scene,
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "direct_stream_copy": True,
        "ordering": "explicit --event order",
        "event_count": len(selected),
        "expected_duration_ms": offset_ms,
        "subtitle_cue_count": len(combined_cues_by_language.get("ja", [])),
        "subtitle_cue_count_by_language": {
            language: len(cues)
            for language, cues in combined_cues_by_language.items()
        },
        "requested_editions": requested_editions,
        "stream_signature": expected_signature,
        "outputs": {
            "without_subtitles": str(without_output.resolve()),
            "with_subtitles": str(with_output.resolve()) if with_output else "",
            "subtitles": str(subtitle_output.resolve()) if subtitle_output else "",
            "editions": output_manifest_editions,
            "scene_index": str((audit_dir / "scene_index.csv").resolve()),
        },
        "output_sha256": {
            "without_subtitles": file_sha256(without_output),
            "with_subtitles": file_sha256(with_output) if with_output else "",
            "subtitles": file_sha256(subtitle_output) if subtitle_output else "",
            "editions": output_sha256_by_edition,
        },
        "edition_audio_sha256": without_audio_hash,
        "edition_audio_sha256_by_edition": output_audio_hashes,
        "probe_without_subtitles": output_probes["none"],
        "probe_with_subtitles": output_probes.get("ja", {}),
        "probes_by_edition": output_probes,
        "sources": source_rows,
    }
    manifest_path = scene_dir / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(scene_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema": "magireco-scene-build-summary-v2",
        "scene": scene,
        "status": scene_manifest["status"],
        "errors": errors,
        "event_count": len(selected),
        "duration_ms": without_duration_ms,
        "subtitle_cue_count": len(combined_cues_by_language.get("ja", [])),
        "subtitle_cue_count_by_language": {
            language: len(cues)
            for language, cues in combined_cues_by_language.items()
        },
        "requested_editions": requested_editions,
        "width": expected_signature["video"]["width"],
        "height": expected_signature["video"]["height"],
        "frame_rate": expected_signature["video"]["r_frame_rate"],
        "audio_sample_rate": expected_signature["audio"]["sample_rate"],
        "audio_channels": expected_signature["audio"]["channels"],
        "manifest": str(manifest_path.resolve()),
    }
    (out_root / "scene_editions_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
