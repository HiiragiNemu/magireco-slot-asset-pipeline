#!/usr/bin/env python3
"""Build the fail-closed ac0903_001 no-BGM evidence bundle.

This deliberately narrow builder closes one native 416x232 DirInfo product.
The four official video inputs are components of one parent Z2D timeline.
Their intervals are exact, but the DGM suffixes ``mlt`` and ``add`` do not
prove the native blend equations, alpha model, color space, final draw order,
or render quantization. They must never be concatenated as four successive
clips or rendered with guessed FFmpeg blend modes.

The only retained sound is direct-parent request 680 at event-global sample
zero. There are no child-Z2D audio rows or subtitle rows. This module writes
JSON blocker manifests only; it never renders, copies, or authorizes media.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


PLAN_SCHEMA = "magireco-ac0903-stop-premonition-event-plan-v1"
EVENT_MANIFEST_SCHEMA = "magireco-event-production-v3"
EDITION_MANIFEST_SCHEMA = "magireco-identical-edition-alias-v1"
BUNDLE_SCHEMA = "magireco-ac0903-stop-premonition-event-bundle-v1"
EVENT = "ac0903_001"
FAMILY = "ac0903"
EDITIONS = ("none", "ja", "zh")
FRAME_RATE = "30/1"
FRAME_COUNT = 60
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = 1600
SAMPLE_COUNT = FRAME_COUNT * SAMPLES_PER_FRAME
STATUS = "BLOCKED_EXACT_COMPOSITOR_CONTRACT_MISSING"

EXPECTED_ROUTE = {
    "kind": 28,
    "row_index": 0,
    "selector_raw": 2,
    "selector_1based": 3,
    "event_info_index": 1580,
    "code_hex": "0x323757352a2f6f6b",
    "scene_name": EVENT,
    "route_status": "ok",
}

EXPECTED_VISUALS = (
    {
        "dgm_order": 0,
        "official_name": "ac0903_SU1_jaku_add",
        "dgm_role": "single_layer_segment",
        "start_frame": 0,
        "end_frame_exclusive": 10,
        "start_ms": 0,
        "end_ms": 333,
        "blend_operator": "candidate_from_dgm_suffix_unproven",
        "composition_role": "unresolved_parallel_layer",
        "layer_flags_hex": "0x037e",
        "frame_count": 10,
        "sha256": "366A62E38613BC02115FC4E6BA64335CD1D0C12311AAF5979DF5731C55DF5E84",
    },
    {
        "dgm_order": 1,
        "official_name": "ac0903_SU1_jaku_mlt",
        "dgm_role": "single_layer_segment",
        "start_frame": 0,
        "end_frame_exclusive": 10,
        "start_ms": 0,
        "end_ms": 333,
        "blend_operator": "candidate_from_dgm_suffix_unproven",
        "composition_role": "unresolved_parallel_layer",
        "layer_flags_hex": "0x037e",
        "frame_count": 10,
        "sha256": "114B0D955033CF7CDA3AC825CB35DBE00913A739AE12CE0F68A495125DC200EE",
    },
    {
        "dgm_order": 2,
        "official_name": "ac0903_SU1_jaku_nom",
        "dgm_role": "intro_before_loop",
        "start_frame": 0,
        "end_frame_exclusive": 30,
        "start_ms": 0,
        "end_ms": 1000,
        "blend_operator": "normal",
        "composition_role": "normal_base_intro",
        "layer_flags_hex": "0x077e",
        "frame_count": 30,
        "sha256": "28D68222A71D74A228EC0888D06D0AA89E82D7C7D3AD4661140DC4FDCBA23D3C",
    },
    {
        "dgm_order": 3,
        "official_name": "ac0903_SU1_jaku_nom_LP",
        "dgm_role": "loop_cycle",
        "start_frame": 30,
        "end_frame_exclusive": 60,
        "start_ms": 1000,
        "end_ms": 2000,
        "blend_operator": "normal",
        "composition_role": "normal_base_loop",
        "layer_flags_hex": "0x077e",
        "frame_count": 30,
        "sha256": "50B4C5D26EC5D19A747985A2FB3A85C2A12A301A27C3BA69AE90333785E9E1E4",
    },
)

EXPECTED_AUDIO = {
    "parent_request_id": 680,
    "parent_code_name": "2400_SU1_停止前兆_001",
    "leaf_request_id": 680,
    "leaf_sound_code": 2400,
    "leaf_label": "SU1_停止前兆_001",
    "start_ms": 0,
    "catalog_duration_ms": 1912,
    "decoded_sample_count": 91811,
    "ogg_name": "snd_02400_bank03_ogg_05133.ogg",
    "sha256": "C91FE6F1C0C098AB22F50743666ABB6FEB7AF0F478587035F138CE7D7E1F5AFB",
    "reqdata_type": 2,
    "reqdata_group_or_channel": 1,
    "reqdata_flag": 2,
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_locator(
    raw: object, *, plan_dir: Path, label: str
) -> tuple[Path, dict[str, str]]:
    if not isinstance(raw, Mapping) or set(raw) != {"path", "sha256"}:
        raise ValueError(f"{label} locator fields differ")
    path = Path(str(raw["path"]))
    if not path.is_absolute():
        path = plan_dir / path
    path = path.resolve()
    expected = str(raw["sha256"]).upper()
    if (
        len(expected) != 64
        or any(character not in "0123456789ABCDEF" for character in expected)
        or not path.is_file()
        or file_sha256(path) != expected
    ):
        raise ValueError(f"{label} SHA-256 differs")
    return path, {"label": label, "path": str(path), "sha256": expected}


def resolve_source_path(
    raw_path: str, overrides: Sequence[tuple[Path, Path]]
) -> Path:
    source = Path(raw_path)
    for old, new in overrides:
        try:
            relative = source.relative_to(old)
        except ValueError:
            continue
        return (new / relative).resolve()
    return source.resolve()


def _parse_int(value: object, *, label: str) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not an integer") from error


def _probe(path: Path, *, ffprobe: str, count_frames: bool = False) -> dict[str, Any]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
    ]
    if count_frames:
        command.append("-count_frames")
    command.extend(["-of", "json", str(path)])
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError(f"ffprobe output differs: {path}")
    return value


def validate_video(path: Path, *, expected_frames: int, ffprobe: str) -> None:
    value = _probe(path, ffprobe=ffprobe, count_frames=True)
    streams = value.get("streams")
    if not isinstance(streams, list):
        raise ValueError(f"video stream list differs: {path}")
    videos = [row for row in streams if row.get("codec_type") == "video"]
    other = [row for row in streams if row.get("codec_type") != "video"]
    if len(videos) != 1 or other:
        raise ValueError(f"source must be one video-only stream: {path}")
    video = videos[0]
    frames = _parse_int(
        video.get("nb_read_frames") or video.get("nb_frames"),
        label=f"{path} frame count",
    )
    if (
        video.get("codec_name") != "h264"
        or _parse_int(video.get("width"), label="video width") != 416
        or _parse_int(video.get("height"), label="video height") != 232
        or video.get("r_frame_rate") != FRAME_RATE
        or frames != expected_frames
    ):
        raise ValueError(f"native visual media contract differs: {path}")


def validate_audio(path: Path, *, ffprobe: str) -> None:
    value = _probe(path, ffprobe=ffprobe)
    streams = value.get("streams")
    if not isinstance(streams, list):
        raise ValueError(f"audio stream list differs: {path}")
    audios = [row for row in streams if row.get("codec_type") == "audio"]
    other = [row for row in streams if row.get("codec_type") != "audio"]
    if len(audios) != 1 or other:
        raise ValueError(f"source must be one audio-only stream: {path}")
    audio = audios[0]
    if (
        audio.get("codec_name") != "vorbis"
        or _parse_int(audio.get("sample_rate"), label="audio sample rate")
        != SAMPLE_RATE
        or _parse_int(audio.get("channels"), label="audio channels") != 2
        or audio.get("time_base") != "1/48000"
        or _parse_int(audio.get("duration_ts"), label="audio duration samples")
        != EXPECTED_AUDIO["decoded_sample_count"]
    ):
        raise ValueError(f"direct-parent audio media contract differs: {path}")


def validate_route(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if _parse_int(row.get("kind"), label="DirInfo kind")
        == EXPECTED_ROUTE["kind"]
        and _parse_int(row.get("row_index"), label="DirInfo row")
        == EXPECTED_ROUTE["row_index"]
    ]
    if len(selected) != 1:
        raise ValueError("DirInfo kind 28 row 0 is not one independent event")
    row = selected[0]
    observed = {
        "kind": _parse_int(row.get("kind"), label="DirInfo kind"),
        "row_index": _parse_int(row.get("row_index"), label="DirInfo row"),
        "selector_raw": _parse_int(
            row.get("selector_raw"), label="DirInfo selector"
        ),
        "selector_1based": _parse_int(
            row.get("selector_1based"), label="DirInfo selector 1-based"
        ),
        "event_info_index": _parse_int(
            row.get("event_info_index"), label="DirInfo event index"
        ),
        "code_hex": str(row.get("code_hex", "")),
        "scene_name": str(row.get("scene_name", "")),
        "route_status": str(row.get("route_status", "")),
    }
    if observed != EXPECTED_ROUTE:
        raise ValueError("DirInfo ac0903 row identity differs")
    return observed


def validate_ledgers(
    event_rows: Sequence[Mapping[str, str]],
    route_rows: Sequence[Mapping[str, str]],
) -> None:
    event = [row for row in event_rows if row.get("event_name") == EVENT]
    if len(event) != 1 or (
        event[0].get("dimensions"),
        event[0].get("production_state"),
        event[0].get("blocker"),
    ) != (
        "416x232",
        "missing_modern_event_manifest",
        "modern_event_manifest_and_audio_timeline_not_built",
    ):
        raise ValueError("v18 ac0903 event ledger state differs")
    route = [
        row
        for row in route_rows
        if _parse_int(row.get("kind"), label="route ledger kind") == 28
        and _parse_int(row.get("row_index"), label="route ledger row") == 0
    ]
    if len(route) != 1 or (
        route[0].get("base_names"),
        route[0].get("ordered_events"),
        route[0].get("production_state"),
    ) != (FAMILY, EVENT, "route_not_yet_produced"):
        raise ValueError("v18 ac0903 route ledger state differs")


def validate_visual_schedule(
    audience_rows: Sequence[Mapping[str, str]],
    gdb_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    audience = [row for row in audience_rows if row.get("event_name") == EVENT]
    gdb = [row for row in gdb_rows if row.get("event_name") == EVENT]
    audience.sort(key=lambda row: _parse_int(row["dgm_order"], label="DGM order"))
    gdb.sort(key=lambda row: _parse_int(row["dgm_order"], label="DGM order"))
    if len(audience) != 4 or len(gdb) != 4:
        raise ValueError("ac0903 visual component count differs")
    output: list[dict[str, Any]] = []
    for expected, catalog, timeline in zip(EXPECTED_VISUALS, audience, gdb):
        observed_catalog = (
            _parse_int(catalog["dgm_order"], label="catalog DGM order"),
            catalog["official_name"],
            catalog["dgm_role"],
            _parse_int(catalog["event_start_ms"], label="catalog start"),
            _parse_int(catalog["event_end_ms"], label="catalog end"),
            _parse_int(catalog["width"], label="catalog width"),
            _parse_int(catalog["height"], label="catalog height"),
            catalog["frame_rate"],
            catalog["interval_confidence"],
        )
        expected_catalog = (
            expected["dgm_order"],
            expected["official_name"],
            expected["dgm_role"],
            expected["start_ms"],
            expected["end_ms"],
            416,
            232,
            FRAME_RATE,
            "exact_duration_unique",
        )
        observed_timeline = (
            timeline["z2d_name"],
            _parse_int(timeline["z2d_loop_point"], label="Z2D loop"),
            _parse_int(timeline["relation_start_ms"], label="relation start"),
            _parse_int(timeline["relation_end_ms"], label="relation end"),
            _parse_int(timeline["dgm_order"], label="timeline DGM order"),
            timeline["official_name"],
            timeline["dgm_role"],
            _parse_int(timeline["event_start_frame"], label="event start frame"),
            _parse_int(timeline["event_end_frame"], label="event end frame") + 1,
            _parse_int(timeline["media_expected_frames"], label="media frames"),
            timeline["interval_confidence"],
            timeline["cri_match"],
            timeline["layer_flags_hex"],
        )
        expected_timeline = (
            "ac0903_cmn_stop_zen_SU1_S",
            30,
            0,
            2000,
            expected["dgm_order"],
            expected["official_name"],
            expected["dgm_role"],
            expected["start_frame"],
            expected["end_frame_exclusive"],
            expected["frame_count"],
            "exact_duration_unique",
            "yes",
            expected["layer_flags_hex"],
        )
        if observed_catalog != expected_catalog or observed_timeline != expected_timeline:
            raise ValueError(
                f"{expected['official_name']} parent-Z2D interval differs"
            )
        output.append(
            {
                **expected,
                "catalog_source_path": str(catalog["target_mp4"]),
            }
        )
    if (
        output[0]["start_frame"],
        output[1]["start_frame"],
        output[2]["start_frame"],
        output[3]["start_frame"],
    ) != (0, 0, 0, 30):
        raise ValueError("ac0903 components were linearized instead of overlaid")
    return output


def validate_direct_parent_audio(
    rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    selected = [row for row in rows if row.get("primary_animation") == EVENT]
    if len(selected) != 1:
        raise ValueError("ac0903 direct-parent audio row count differs")
    row = selected[0]
    observed = {
        "parent_request_id": _parse_int(
            row.get("parent_request_id"), label="parent request"
        ),
        "parent_code_name": str(row.get("parent_code_name", "")),
        "leaf_request_id": _parse_int(
            row.get("leaf_request_id"), label="leaf request"
        ),
        "leaf_sound_code": _parse_int(
            row.get("leaf_sound_code"), label="sound code"
        ),
        "leaf_label": str(row.get("leaf_label", "")),
        "start_ms": _parse_int(row.get("start_ms"), label="audio start"),
        "catalog_duration_ms": _parse_int(
            row.get("duration_ms"), label="audio duration"
        ),
        "ogg_name": str(row.get("ogg_name", "")),
        "reqdata_type": _parse_int(row.get("reqdata_type"), label="reqdata type"),
        "reqdata_group_or_channel": _parse_int(
            row.get("reqdata_group_or_channel"), label="reqdata group"
        ),
        "reqdata_flag": _parse_int(row.get("reqdata_flag"), label="reqdata flag"),
    }
    for key in (
        "parent_request_id",
        "parent_code_name",
        "leaf_request_id",
        "leaf_sound_code",
        "leaf_label",
        "start_ms",
        "catalog_duration_ms",
        "ogg_name",
        "reqdata_type",
        "reqdata_group_or_channel",
        "reqdata_flag",
    ):
        if observed[key] != EXPECTED_AUDIO[key]:
            raise ValueError(f"ac0903 direct-parent audio {key} differs")
    if (
        str(row.get("speaker_hint", "")).strip()
        or str(row.get("subtitle_text", "")).strip()
        or str(row.get("smz_matches_leaf_request", "")) != "yes"
        or str(row.get("ogg_duration_match", "")) != "yes"
    ):
        raise ValueError("request 680 scene-SE identity differs")
    observed["catalog_source_path"] = str(row["ogg_path"])
    observed["classification"] = "scene_se"
    observed["retain_in_no_bgm"] = True
    return observed


def validate_zero_child_and_subtitle_rows(
    child_rows: Sequence[Mapping[str, str]],
    subtitle_rows: Sequence[Mapping[str, str]],
) -> None:
    child = [row for row in child_rows if row.get("event_name") == EVENT]
    subtitles = [row for row in subtitle_rows if row.get("event_name") == EVENT]
    if child or subtitles:
        raise ValueError(
            "ac0903 review aliases require zero child-audio and subtitle rows"
        )


def edition_aliases() -> list[dict[str, Any]]:
    return [
        {
            "edition": edition,
            "output_filename": f"{EVENT}__{edition}.mp4",
            "canonical_edition": "none",
            "content_equivalence_group": f"{EVENT}_no_dialogue_no_subtitle_v1",
            "expected_media_sha256_relation": "identical_to_canonical",
            "materialization_policy": (
                "forbidden_until_exact_compositor_contract_is_hash_bound"
            ),
            "subtitle_track": None,
            "status": "blocked_no_media_authorized",
            "publishable": False,
        }
        for edition in EDITIONS
    ]


def validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("plan_id") != "ac0903_stop_premonition_event_v1"
        or plan.get("status") != "blocked_exact_compositor_contract_missing"
        or plan.get("event") != EVENT
        or tuple(plan.get("editions", [])) != EDITIONS
        or plan.get("audio_profile") != "no_bgm"
        or plan.get("publishable") is not False
        or plan.get("render_authorized") is not False
        or plan.get("media_outputs_written") != 0
    ):
        raise ValueError("ac0903 plan identity differs")
    blocker = plan.get("compositor_blocker")
    if (
        not isinstance(blocker, Mapping)
        or blocker.get("code") != "exact_native_compositor_contract_missing"
        or not isinstance(blocker.get("missing_fields"), list)
        or len(blocker["missing_fields"]) < 10
        or not isinstance(blocker.get("renderer_evidence"), list)
        or len(blocker["renderer_evidence"]) != 4
    ):
        raise ValueError("ac0903 compositor blocker differs")
    blocker_snapshots: list[dict[str, str]] = []
    for index, raw in enumerate(blocker["renderer_evidence"]):
        if (
            not isinstance(raw, Mapping)
            or set(raw) != {"path", "sha256", "finding"}
            or not str(raw["finding"]).strip()
        ):
            raise ValueError("ac0903 renderer evidence fields differ")
        source = Path(str(raw["path"]))
        if not source.is_absolute():
            source = plan_path.parent / source
        source = source.resolve()
        expected_sha = str(raw["sha256"]).upper()
        if not source.is_file() or file_sha256(source) != expected_sha:
            raise ValueError(f"ac0903 renderer evidence {index} SHA-256 differs")
        blocker_snapshots.append(
            {
                "label": f"compositor blocker evidence {index}",
                "path": str(source),
                "sha256": expected_sha,
            }
        )
    media = plan.get("native_media")
    if not isinstance(media, Mapping) or (
        media.get("width"),
        media.get("height"),
        media.get("frame_rate"),
        media.get("frame_count"),
        media.get("audio_sample_rate"),
        media.get("audio_channels"),
        media.get("upscale"),
    ) != (416, 232, FRAME_RATE, FRAME_COUNT, SAMPLE_RATE, 2, False):
        raise ValueError("ac0903 native media plan differs")

    plan_dir = plan_path.parent
    inputs = plan.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError("ac0903 plan inputs differ")
    expected_labels = (
        "audience_event_clips",
        "audience_event_ledger",
        "dirinfo_routes",
        "dirinfo_route_ledger",
        "gdb_event_dgm_timeline",
        "direct_parent_audio",
        "child_audio",
        "subtitles",
    )
    if set(inputs) != set(expected_labels):
        raise ValueError("ac0903 plan input labels differ")
    bound: dict[str, Path] = {}
    snapshots: list[dict[str, str]] = []
    for label in expected_labels:
        path, snapshot = resolve_locator(
            inputs[label], plan_dir=plan_dir, label=label
        )
        bound[label] = path
        snapshots.append(snapshot)
    snapshots.extend(blocker_snapshots)

    raw_overrides = plan.get("source_root_overrides")
    if not isinstance(raw_overrides, list) or len(raw_overrides) != 1:
        raise ValueError("ac0903 source root override differs")
    override = raw_overrides[0]
    if not isinstance(override, Mapping) or set(override) != {"from", "to"}:
        raise ValueError("ac0903 source root override fields differ")
    overrides = [
        (Path(str(override["from"])).resolve(), Path(str(override["to"])).resolve())
    ]

    route = validate_route(read_csv(bound["dirinfo_routes"]))
    validate_ledgers(
        read_csv(bound["audience_event_ledger"]),
        read_csv(bound["dirinfo_route_ledger"]),
    )
    visuals = validate_visual_schedule(
        read_csv(bound["audience_event_clips"]),
        read_csv(bound["gdb_event_dgm_timeline"]),
    )
    expected_visual_sha = plan.get("source_sha256_by_official_name")
    if not isinstance(expected_visual_sha, Mapping) or dict(expected_visual_sha) != {
        row["official_name"]: row["sha256"] for row in EXPECTED_VISUALS
    }:
        raise ValueError("ac0903 visual SHA plan differs")
    for visual in visuals:
        source = resolve_source_path(visual["catalog_source_path"], overrides)
        if (
            not source.is_file()
            or file_sha256(source) != visual["sha256"]
        ):
            raise ValueError(f"{visual['official_name']} SHA-256 differs")
        validate_video(
            source,
            expected_frames=int(visual["frame_count"]),
            ffprobe=ffprobe,
        )
        visual["source_path"] = str(source)
        snapshots.append(
            {
                "label": str(visual["official_name"]),
                "path": str(source),
                "sha256": str(visual["sha256"]),
            }
        )

    audio = validate_direct_parent_audio(read_csv(bound["direct_parent_audio"]))
    if plan.get("audio_source_sha256") != EXPECTED_AUDIO["sha256"]:
        raise ValueError("ac0903 audio SHA plan differs")
    audio_source = resolve_source_path(audio["catalog_source_path"], overrides)
    if (
        not audio_source.is_file()
        or file_sha256(audio_source) != EXPECTED_AUDIO["sha256"]
    ):
        raise ValueError("request 680 OGG SHA-256 differs")
    validate_audio(audio_source, ffprobe=ffprobe)
    audio["source_path"] = str(audio_source)
    audio["sha256"] = EXPECTED_AUDIO["sha256"]
    audio["decoded_sample_count"] = EXPECTED_AUDIO["decoded_sample_count"]
    snapshots.append(
        {
            "label": "direct-parent request 680 scene SE",
            "path": str(audio_source),
            "sha256": str(EXPECTED_AUDIO["sha256"]),
        }
    )
    validate_zero_child_and_subtitle_rows(
        read_csv(bound["child_audio"]),
        read_csv(bound["subtitles"]),
    )
    return {
        "route": route,
        "visuals": visuals,
        "audio": audio,
        "source_snapshots": snapshots,
    }


def build_event_manifest(
    validated: Mapping[str, Any], *, plan_path: Path
) -> dict[str, Any]:
    clips = [
        {
            "official_name": row["official_name"],
            "dgm_order": row["dgm_order"],
            "dgm_role": row["dgm_role"],
            "source_path": row["source_path"],
            "source_sha256": row["sha256"],
            "source_frame_count": row["frame_count"],
            "event_start_frame": row["start_frame"],
            "event_end_frame_exclusive": row["end_frame_exclusive"],
            "event_start_ms": row["start_ms"],
            "event_end_ms": row["end_ms"],
            "composition_role": row["composition_role"],
            "blend_operator": row["blend_operator"],
        }
        for row in validated["visuals"]
    ]
    audio = validated["audio"]
    manifest: dict[str, Any] = {
        "schema": EVENT_MANIFEST_SCHEMA,
        "status": STATUS,
        "publishable": False,
        "render_authorized": False,
        "event": EVENT,
        "family": FAMILY,
        "title_zh": "停止前兆 SU1 ac0903",
        "audio_profile": "no_bgm",
        "native_dimensions": {"width": 416, "height": 232},
        "native_frame_rate": FRAME_RATE,
        "video_duration_ms": 2000,
        "timeline_content_end_ms": 2000,
        "raw_render_duration_ms": 2000,
        "render_frame_count": FRAME_COUNT,
        "render_duration_ms": 2000,
        "render_duration_quantization": {
            "frame_rate": FRAME_RATE,
            "frame_count": FRAME_COUNT,
            "content_end_ms": 2000,
            "duration_ms": 2000,
            "exact_duration_ms_numerator": 2000,
            "exact_duration_ms_denominator": 1,
            "audio_sample_rate": SAMPLE_RATE,
            "audio_sample_count": SAMPLE_COUNT,
        },
        "video_extension_policy": "none_exact_parent_z2d_60_frames",
        "video_composition_model": "unresolved_parallel_parent_z2d_compositor",
        "composition_plan": {
            "parent_z2d": "ac0903_cmn_stop_zen_SU1_S",
            "parent_frames": {"start": 0, "end_exclusive": 60},
            "base_sequence": [
                {
                    "official_name": "ac0903_SU1_jaku_nom",
                    "start_frame": 0,
                    "end_frame_exclusive": 30,
                    "blend_operator": "normal",
                },
                {
                    "official_name": "ac0903_SU1_jaku_nom_LP",
                    "start_frame": 30,
                    "end_frame_exclusive": 60,
                    "blend_operator": "normal",
                },
            ],
            "parallel_overlays": [
                {
                    "official_name": "ac0903_SU1_jaku_mlt",
                    "start_frame": 0,
                    "end_frame_exclusive": 10,
                    "blend_operator": "candidate_from_dgm_suffix_unproven",
                },
                {
                    "official_name": "ac0903_SU1_jaku_add",
                    "start_frame": 0,
                    "end_frame_exclusive": 10,
                    "blend_operator": "candidate_from_dgm_suffix_unproven",
                },
            ],
            "render_layer_order": "unresolved",
            "raw_layer_flags": {
                "ac0903_SU1_jaku_add": "0x037e",
                "ac0903_SU1_jaku_mlt": "0x037e",
                "ac0903_SU1_jaku_nom": "0x077e",
                "ac0903_SU1_jaku_nom_LP": "0x077e",
            },
            "forbidden_model": "linear_concatenation_of_four_components",
            "forbidden_implementation": (
                "guessed_ffmpeg_multiply_addition_or_visual_similarity"
            ),
            "blocker": "exact_native_compositor_contract_missing",
            "unresolved_fields": [
                "native_add_blend_equation",
                "native_mlt_blend_equation",
                "working_color_space_and_transfer",
                "source_alpha_or_matte_semantics",
                "straight_or_premultiplied_alpha",
                "final_draw_order",
                "render_target_format_bit_depth_and_rounding",
                "chroma_upsampling_and_canvas_transform",
                "output_color_metadata",
                "shader_program_and_blend_state_identity",
                "reference_game_framebuffer_hash",
                "frame_enable_pts_quantization",
                "supported_exact_renderer_implementation",
            ],
        },
        "clips": clips,
        "audio_layers": [
            {
                "source_kind": "direct_parent_event_audio",
                "classification": "scene_se",
                "retain_in_no_bgm": True,
                "parent_request_id": audio["parent_request_id"],
                "leaf_request_id": audio["leaf_request_id"],
                "leaf_sound_code": audio["leaf_sound_code"],
                "leaf_label": audio["leaf_label"],
                "start_sample": 0,
                "start_ms": 0,
                "decoded_sample_count": audio["decoded_sample_count"],
                "source_path": audio["source_path"],
                "source_sha256": audio["sha256"],
            }
        ],
        "audio_mix": {
            "sample_rate": SAMPLE_RATE,
            "channels": 2,
            "presentation_sample_count": SAMPLE_COUNT,
            "source_end_sample": audio["decoded_sample_count"],
            "tail_silence_samples": SAMPLE_COUNT - audio["decoded_sample_count"],
            "unresolved_audio_layer_count": 0,
            "bgm_layer_count": 0,
            "child_z2d_audio_layer_count": 0,
        },
        "dialogue_cues": [],
        "subtitle_tracks": {"ja": [], "zh": []},
        "dirinfo_route": validated["route"],
        "source_snapshots": validated["source_snapshots"],
        "production_plan": {
            "path": str(plan_path.resolve()),
            "sha256": file_sha256(plan_path),
        },
        "editions": edition_aliases(),
        "review_gate": {
            "status": "blocked_before_human_playback",
            "focus": (
                "Obtain a hash-bound native compositor contract before any "
                "media exists. Request 680 timing is already event-global."
            ),
        },
    }
    manifest["content_contract_sha256"] = canonical_sha256(manifest)
    return manifest


def build_bundle(
    *, plan_path: Path, output_root: Path, ffprobe: str = "ffprobe"
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite output root: {output_root}")
    plan = read_json(plan_path)
    validated = validate_plan(plan, plan_path=plan_path, ffprobe=ffprobe)
    event_manifest = build_event_manifest(validated, plan_path=plan_path)
    event_path = output_root / "events" / f"{EVENT}.json"
    write_json(event_path, event_manifest)
    aliases: list[dict[str, Any]] = []
    for alias in edition_aliases():
        edition = str(alias["edition"])
        value = {
            "schema": EDITION_MANIFEST_SCHEMA,
            **alias,
            "event": EVENT,
            "audio_profile": "no_bgm",
            "canonical_content_contract_sha256": event_manifest[
                "content_contract_sha256"
            ],
            "event_manifest": {
                "path": str(event_path.resolve()),
                "sha256": file_sha256(event_path),
            },
        }
        path = output_root / "editions" / f"{EVENT}__{edition}.json"
        write_json(path, value)
        aliases.append(
            {
                "edition": edition,
                "manifest_path": str(path.resolve()),
                "manifest_sha256": file_sha256(path),
                "expected_output_filename": alias["output_filename"],
                "canonical_edition": alias["canonical_edition"],
                "expected_media_sha256_relation": alias[
                    "expected_media_sha256_relation"
                ],
            }
        )
    bundle = {
        "schema": BUNDLE_SCHEMA,
        "status": STATUS,
        "publishable": False,
        "render_authorized": False,
        "event": EVENT,
        "event_manifest": {
            "path": str(event_path.resolve()),
            "sha256": file_sha256(event_path),
            "content_contract_sha256": event_manifest[
                "content_contract_sha256"
            ],
        },
        "edition_aliases": aliases,
        "media_outputs_written": 0,
        "next_action": (
            "Recover and hash-bind the native blend/color/alpha/z-order/"
            "quantization contract and implement it in the formal renderer. "
            "Do not render or materialize edition hardlinks before that gate."
        ),
    }
    write_json(output_root / "MANIFEST.json", bundle)
    return bundle


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=(
            Path(__file__).resolve().parent
            / "series_proposals"
            / "ac0903_stop_premonition_event_v1.json"
        ),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args(argv)
    bundle = build_bundle(
        plan_path=args.plan.resolve(),
        output_root=args.output_root.resolve(),
        ffprobe=args.ffprobe,
    )
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
