#!/usr/bin/env python3
"""Build the current strict-no-BGM ac0911 mature-route review set.

Unchanged route artifacts are hard-linked from the immutable v35 source;
DirInfo row 006 is hard-linked from the strict-no-BGM v69r2 replacement.
Only the JA/ZH editions whose graphical caption ends changed are re-encoded.
The edited showcase is rebuilt from the resulting route set and is explicitly
not described as a single native game session.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

try:
    from tools.frida_runtime_probe.build_ac0908_reference_showcase import (
        assert_srt_round_trip,
        milliseconds_for_samples,
        validate_output_media,
        validate_video_grid,
    )
    from tools.frida_runtime_probe.build_independent_scene_release import (
        file_sha256,
        parse_srt,
        read_json,
        run,
        write_json,
    )
    from tools.frida_runtime_probe.build_mature_416_route_batch import (
        _audio_packet_pcm_audit,
        _copy_pcm,
        _encode_audio_master,
        _encode_edition,
    )
except ModuleNotFoundError:
    from build_ac0908_reference_showcase import (  # type: ignore
        assert_srt_round_trip,
        milliseconds_for_samples,
        validate_output_media,
        validate_video_grid,
    )
    from build_independent_scene_release import (  # type: ignore
        file_sha256,
        parse_srt,
        read_json,
        run,
        write_json,
    )
    from build_mature_416_route_batch import (  # type: ignore
        _audio_packet_pcm_audit,
        _copy_pcm,
        _encode_audio_master,
        _encode_edition,
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
DEFAULT_PLAN = (
    REPO_ROOT
    / "tools"
    / "frida_runtime_probe"
    / "series_proposals"
    / "ac0911_event_global_mature_routes_v75r1_20260817.json"
)
DEFAULT_OUTPUT = RESEARCH_ROOT / "no_bgm_editions_v75r1_ac0911_event_global_routes_20260817"
SCHEMA = "magireco-ac0911-event-global-mature-routes-plan-v1"
STATUS = "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
SHOWCASE_CLAIM = "edited_route_chapter_showcase_not_single_native_session"
EDITIONS = ("none", "ja", "zh")
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Manifest = Join-Path $Root 'BATCH_MANIFEST.json'
if (-not (Test-Path -LiteralPath $Manifest)) { throw 'ac0911 v75 batch manifest missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable ac0911 v75 can be disabled without touching v35, v69r2, event manifests, or source media; rerun with -Apply to rename this root.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def resolve_path(value: str, *, plan_path: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "byte_count": path.stat().st_size,
    }


def link_or_copy(source: Path, target: Path) -> dict[str, Any]:
    if not source.is_file() or target.exists():
        raise ValueError(f"invalid immutable materialization: {source} -> {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
        policy = "hardlink"
        if not os.path.samefile(source, target):
            raise RuntimeError("hardlink samefile verification failed")
    except OSError:
        shutil.copy2(source, target)
        policy = "copy"
        if file_sha256(source) != file_sha256(target):
            raise RuntimeError("copy SHA-256 verification failed")
    return {
        "source_path": str(source.resolve()),
        "target_path": str(target.resolve()),
        "policy": policy,
        "samefile": os.path.samefile(source, target),
        "sha256": file_sha256(target),
        "byte_count": target.stat().st_size,
    }


def validate_source_artifact(path: Path, expected_sha: str, label: str) -> None:
    if file_sha256(path) != str(expected_sha).upper():
        raise ValueError(f"{label} source SHA-256 differs")


def validate_plan(plan: dict, plan_path: Path) -> dict[str, Any]:
    if (
        plan.get("schema") != SCHEMA
        or plan.get("family") != "ac0911"
        or plan.get("status") != "approved_for_bounded_render_human_playback_required"
        or plan.get("native_dimensions") != {"width": 416, "height": 232}
        or plan.get("native_frame_rate") != "30/1"
        or plan.get("audio_profile") != "strict_no_bgm"
        or plan.get("edited_showcase_claim") != SHOWCASE_CLAIM
        or len(str(plan.get("strict_row006_route_manifest_sha256", ""))) != 64
        or plan.get("human_playback_required") is not True
        or plan.get("publication_approved") is not False
    ):
        raise ValueError("ac0911 v75 plan contract differs")
    routes = list(plan.get("route_order", []))
    if routes != [
        "dirinfo-row-000",
        "dirinfo-row-001",
        "dirinfo-row-002",
        "dirinfo-row-003",
        "dirinfo-row-004",
        "dirinfo-row-005",
        "dirinfo-row-006",
        "dirinfo-row-007",
        "dirinfo-row-009",
    ] or plan.get("excluded_dirinfo_rows") != [8, 10, 11, 12, 13]:
        raise ValueError("ac0911 route/exclusion boundary differs")
    return {
        "plan": plan,
        "routes": routes,
        "v35": resolve_path(plan["source_v35_root"], plan_path=plan_path),
        "v69": resolve_path(plan["strict_row006_root"], plan_path=plan_path),
        "strict_plan": resolve_path(plan["strict_no_bgm_plan"], plan_path=plan_path),
        "authority": resolve_path(plan["timing_authority_summary"], plan_path=plan_path),
        "replacement": resolve_path(plan["replacement_manifest_root"], plan_path=plan_path),
        "source_events": resolve_path(plan["source_event_manifest_root"], plan_path=plan_path),
        "layout": resolve_path(plan["subtitle_layout"], plan_path=plan_path),
        "font": resolve_path(plan["font"], plan_path=plan_path),
    }


def validate_authorities(state: dict[str, Any]) -> dict[str, Any]:
    authority = read_json(state["authority"])
    if (
        authority.get("status") != "PASS"
        or authority.get("mature_route_count") != 9
        or len(authority.get("events", [])) != 9
        or authority.get("publication_approved") is not False
    ):
        raise ValueError("ac0911 timing authority summary differs")
    for row in [authority.get("authority"), *authority.get("overrides", [])]:
        path = Path(str(row["path"]))
        validate_source_artifact(path, row["sha256"], "timing authority")

    replacement_summary = read_json(
        state["replacement"] / "AC0911_MATURE_ROUTES_REPLACEMENT_MANIFEST_SUMMARY.json"
    )
    if (
        replacement_summary.get("status") != "PASS"
        or replacement_summary.get("mature_route_count") != 9
        or replacement_summary.get("graphical_subtitle_end_changed_events")
        != ["ac0911_004", "ac0911_006", "ac0911_008", "ac0911_012"]
    ):
        raise ValueError("ac0911 replacement summary differs")
    event_manifests: dict[str, dict[str, Any]] = {}
    for row in replacement_summary.get("events", []):
        event = str(row["event"])
        path = state["replacement"] / str(row["output_relative_path"])
        validate_source_artifact(path, row["output_sha256"], event)
        manifest = read_json(path)
        if manifest.get("quality_gates", {}).get("ready") is not True:
            raise ValueError(f"{event}: replacement is not READY")
        event_manifests[event] = {**binding(path), "timing_source": "v75_replacement"}
    return {
        "authority_summary": binding(state["authority"]),
        "replacement_summary": binding(
            state["replacement"]
            / "AC0911_MATURE_ROUTES_REPLACEMENT_MANIFEST_SUMMARY.json"
        ),
        "event_manifests": event_manifests,
    }


def source_ready_binding(state: dict[str, Any], event: str) -> dict[str, Any]:
    path = state["source_events"] / f"{event}.json"
    manifest = read_json(path)
    if manifest.get("quality_gates", {}).get("ready") is not True:
        raise ValueError(f"{event}: source event manifest is not READY")
    return {**binding(path), "timing_source": "v68_already_ready"}


def v35_sha_map(root: Path) -> dict[str, str]:
    payload = read_json(root / "SHA256SUMS.json")
    rows = payload.get("files", [])
    mapping = {str(row["path"]): str(row["sha256"]).upper() for row in rows}
    if len(mapping) != len(rows):
        raise ValueError("v35 SHA manifest contains duplicate paths")
    validate_source_artifact(root / "BATCH_MANIFEST.json", mapping["BATCH_MANIFEST.json"], "v35 batch")
    return mapping


def source_file_binding(root: Path, rel: str, sha_map: dict[str, str] | None, expected_sha: str | None = None) -> Path:
    path = root / rel
    expected = expected_sha or (sha_map or {}).get(rel)
    if not expected:
        raise ValueError(f"no source hash binding for {path}")
    validate_source_artifact(path, expected, rel)
    return path


def patch_cues(cues: list[dict[str, Any]], rows: list[dict[str, Any]], route: str) -> list[dict[str, Any]]:
    output = copy.deepcopy(cues)
    for row in rows:
        index = int(row["cue_index"])
        cue = output[index]
        if (cue["start_ms"], cue["end_ms"]) != (
            int(row["expected_start_ms"]),
            int(row["expected_old_end_ms"]),
        ):
            raise ValueError(f"{route} cue {index} source timing differs")
        cue["end_ms"] = int(row["new_end_ms"])
        if cue["end_ms"] <= cue["start_ms"]:
            raise ValueError(f"{route} cue {index} collapsed")
    return output


def route_artifact_paths(root: Path, route: str) -> dict[str, Path]:
    base = root / "routes" / route
    stem = f"ac0911__{route}"
    return {
        "manifest": base / "ROUTE_MANIFEST.json",
        "clean": base / "masters" / f"{stem}__clean_visual_master.mp4",
        "pcm": base / "masters" / f"{stem}__no_bgm_master.f32le",
        "audio": base / "masters" / f"{stem}__no_bgm_audio_master.m4a",
        "srt_ja": base / "subtitles" / f"{stem}__ja.srt",
        "srt_zh": base / "subtitles" / f"{stem}__zh.srt",
        "video_none": base / "video" / f"{stem}__none.mp4",
        "video_ja": base / "video" / f"{stem}__ja.mp4",
        "video_zh": base / "video" / f"{stem}__zh.mp4",
    }


def build_route(
    *,
    state: dict[str, Any],
    authorities: dict[str, Any],
    route: str,
    destination_root: Path,
    staging: Path,
    font_dir: Path,
    v35_sums: dict[str, str],
    strict_media: dict[str, str],
    ffmpeg: str,
    ffprobe: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    strict = route == state["plan"]["strict_no_bgm_route"]
    source_root = state["v69"] if strict else state["v35"]
    source = route_artifact_paths(source_root, route)
    target = route_artifact_paths(destination_root, route)
    manifest = read_json(source["manifest"])
    if strict:
        validate_source_artifact(
            source["manifest"],
            state["plan"]["strict_row006_route_manifest_sha256"],
            f"{route}/strict route manifest",
        )
    else:
        manifest_rel = str(source["manifest"].relative_to(state["v35"])).replace(
            "\\", "/"
        )
        validate_source_artifact(
            source["manifest"], v35_sums[manifest_rel], f"{route}/v35 route manifest"
        )
    expected_sequence = list(manifest.get("render_event_sequence", []))
    if not expected_sequence:
        raise ValueError(f"{route}: source event sequence missing")

    links: list[dict[str, Any]] = []
    artifact_specs = {
        "clean": manifest["clean_visual"]["sha256"],
        "pcm": manifest["pcm"]["sha256"],
        "audio": manifest["audio_master"]["sha256"],
        "srt_ja": manifest["subtitles"]["ja"]["sha256"],
        "srt_zh": manifest["subtitles"]["zh"]["sha256"],
        "video_none": manifest["media"]["none"]["sha256"],
        "video_ja": manifest["media"]["ja"]["sha256"],
        "video_zh": manifest["media"]["zh"]["sha256"],
    }
    if strict:
        for edition in EDITIONS:
            if artifact_specs[f"video_{edition}"].upper() != strict_media[edition]:
                raise ValueError(f"{route}/{edition}: strict-plan media binding differs")
    for key, expected_sha in artifact_specs.items():
        validate_source_artifact(source[key], expected_sha, f"{route}/{key}")

    for key in ("clean", "pcm", "audio"):
        links.append(link_or_copy(source[key], target[key]))
    corrections = list(state["plan"].get("subtitle_end_corrections", {}).get(route, []))
    if corrections:
        for edition in ("ja", "zh"):
            cues = patch_cues(parse_srt(source[f"srt_{edition}"]), corrections, route)
            assert_srt_round_trip(target[f"srt_{edition}"], cues)
        links.append(link_or_copy(source["video_none"], target["video_none"]))
        total_frames = int(manifest["total_frames"])
        for edition in ("ja", "zh"):
            _encode_edition(
                clean_visual=target["clean"],
                audio_master=target["audio"],
                subtitle_path=target[f"srt_{edition}"],
                layout=read_json(state["layout"]),
                fonts_dir=font_dir,
                output=target[f"video_{edition}"],
                total_frames=total_frames,
                staging=staging,
                ffmpeg=ffmpeg,
            )
    else:
        for key in ("srt_ja", "srt_zh", "video_none", "video_ja", "video_zh"):
            links.append(link_or_copy(source[key], target[key]))

    qa_dir = target["manifest"].parent / ".qa"
    qa_dir.mkdir(parents=True)
    media = {}
    packet = {}
    for edition in EDITIONS:
        path = target[f"video_{edition}"]
        audit = validate_output_media(path, expected_frames=int(manifest["total_frames"]), ffprobe=ffprobe)
        audit.update({"path": str(path.relative_to(destination_root)).replace("\\", "/"), "sha256": file_sha256(path), "byte_count": path.stat().st_size})
        media[edition] = audit
        packet[edition] = _audio_packet_pcm_audit(
            path,
            expected_samples=int(manifest["total_samples"]),
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            work_dir=qa_dir,
        )
    shutil.rmtree(qa_dir)
    if len({row["packet_data_signature_sha256"] for row in packet.values()}) != 1:
        raise ValueError(f"{route}: none/JA/ZH audio packet identity differs")

    event_bindings = {}
    for event in expected_sequence:
        event_bindings[event] = authorities["event_manifests"].get(event) or source_ready_binding(state, event)
    result = copy.deepcopy(manifest)
    result.update(
        {
            "schema": "magireco-ac0911-v75-route-manifest-v1",
            "status": STATUS,
            "audio_profile": "strict_no_bgm",
            "media": media,
            "audio_packet_pcm_audits": packet,
            "event_manifest_bindings": event_bindings,
            "timing_authority_summary": authorities["authority_summary"],
            "replacement_manifest_summary": authorities["replacement_summary"],
            "strict_no_bgm_replacement_applied": strict,
            "graphical_subtitle_end_corrections": corrections,
            "source_route_manifest": binding(source["manifest"]),
            "human_playback_approved": False,
            "publication_approved": False,
        }
    )
    result["clean_visual"] = {"path": str(target["clean"].relative_to(destination_root)).replace("\\", "/"), "sha256": file_sha256(target["clean"])}
    result["pcm"] = {"path": str(target["pcm"].relative_to(destination_root)).replace("\\", "/"), "sha256": file_sha256(target["pcm"]), "byte_count": target["pcm"].stat().st_size}
    result["audio_master"] = {"path": str(target["audio"].relative_to(destination_root)).replace("\\", "/"), "sha256": file_sha256(target["audio"])}
    result["subtitles"] = {
        edition: {"path": str(target[f"srt_{edition}"].relative_to(destination_root)).replace("\\", "/"), "sha256": file_sha256(target[f"srt_{edition}"])}
        for edition in ("ja", "zh")
    }
    write_json(target["manifest"], result)
    return result, links


def concat_video_only(sources: list[Path], output: Path, list_path: Path, total_frames: int, ffmpeg: str, ffprobe: str) -> None:
    lines = ["ffconcat version 1.0"]
    for source in sources:
        escaped = str(source.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run(
        [
            ffmpeg,
            "-y",
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
            "-c:v",
            "copy",
            "-an",
            "-frames:v",
            str(total_frames),
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    validate_video_grid(output, expected_frames=total_frames, ffprobe=ffprobe, label=output.stem)


def build_showcase(*, route_manifests: list[dict[str, Any]], destination_root: Path, ffmpeg: str, ffprobe: str) -> dict[str, Any]:
    root = destination_root / "edited_route_chapter_showcase"
    work = root / ".work"
    masters = root / "masters"
    subtitles = root / "subtitles"
    videos = root / "video"
    for path in (work, masters, subtitles, videos):
        path.mkdir(parents=True, exist_ok=True)
    total_frames = sum(int(row["total_frames"]) for row in route_manifests)
    total_samples = sum(int(row["total_samples"]) for row in route_manifests)
    pcm_sources = [destination_root / row["pcm"]["path"] for row in route_manifests]
    pcm = masters / "ac0911__edited_route-chapter_showcase__no_bgm_master.f32le"
    _copy_pcm(pcm_sources, pcm)
    if pcm.stat().st_size != total_samples * 8:
        raise ValueError("showcase PCM grid differs")
    audio = masters / "ac0911__edited_route-chapter_showcase__no_bgm_audio_master.m4a"
    _encode_audio_master(pcm, audio, ffmpeg=ffmpeg)

    chapters = []
    frame_cursor = sample_cursor = 0
    for row in route_manifests:
        chapters.append(
            {
                "route_id": row["product_id"].split("__", 1)[1],
                "title": row["title"],
                "start_frame": frame_cursor,
                "end_frame": frame_cursor + int(row["total_frames"]),
                "start_sample": sample_cursor,
                "end_sample": sample_cursor + int(row["total_samples"]),
                "start_ms": milliseconds_for_samples(sample_cursor),
                "end_ms": milliseconds_for_samples(sample_cursor + int(row["total_samples"])),
                "event_sequence": row["render_event_sequence"],
            }
        )
        frame_cursor += int(row["total_frames"])
        sample_cursor += int(row["total_samples"])

    for edition in ("ja", "zh"):
        cues = []
        shift = 0
        for row in route_manifests:
            route_srt = destination_root / row["subtitles"][edition]["path"]
            cues.extend({**cue, "start_ms": shift + cue["start_ms"], "end_ms": shift + cue["end_ms"]} for cue in parse_srt(route_srt))
            shift += milliseconds_for_samples(int(row["total_samples"]))
        assert_srt_round_trip(subtitles / f"ac0911__edited_route-chapter_showcase__{edition}.srt", cues)

    visual_paths = {}
    for edition in EDITIONS:
        sources = [destination_root / row["media"][edition]["path"] for row in route_manifests]
        visual = (
            masters / "ac0911__edited_route-chapter_showcase__clean_visual_master.mp4"
            if edition == "none"
            else work / f"{edition}.video-only.mp4"
        )
        concat_video_only(sources, visual, work / f"{edition}.ffconcat", total_frames, ffmpeg, ffprobe)
        visual_paths[edition] = visual

    media = {}
    packet = {}
    qa_work = work / "qa"
    qa_work.mkdir()
    for edition in EDITIONS:
        output = videos / f"ac0911__edited_route-chapter_showcase__{edition}.mp4"
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(visual_paths[edition]),
                "-i",
                str(audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c",
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
        audit = validate_output_media(output, expected_frames=total_frames, ffprobe=ffprobe)
        audit.update({"path": str(output.relative_to(destination_root)).replace("\\", "/"), "sha256": file_sha256(output), "byte_count": output.stat().st_size})
        media[edition] = audit
        packet[edition] = _audio_packet_pcm_audit(output, expected_samples=total_samples, ffmpeg=ffmpeg, ffprobe=ffprobe, work_dir=qa_work)
    if len({row["packet_data_signature_sha256"] for row in packet.values()}) != 1:
        raise ValueError("showcase none/JA/ZH audio packet identity differs")
    write_json(root / "CHAPTER_TIMELINE.json", {"chapters": chapters})
    manifest = {
        "schema": "magireco-ac0911-v75-edited-showcase-manifest-v1",
        "status": STATUS,
        "product_id": "ac0911__edited_route-chapter_showcase",
        "title": "P11 ac0911 九条成熟路线（编辑章节合集）",
        "product_scope": "edited_route_chapter_showcase",
        "session_claim": SHOWCASE_CLAIM,
        "single_native_session_claimed": False,
        "audio_profile": "strict_no_bgm",
        "total_frames": total_frames,
        "total_samples": total_samples,
        "duration_ms": milliseconds_for_samples(total_samples),
        "chapter_timeline": chapters,
        "media": media,
        "audio_packet_pcm_audits": packet,
        "human_playback_approved": False,
        "publication_approved": False,
    }
    write_json(root / "SHOWCASE_MANIFEST.json", manifest)
    shutil.rmtree(work)
    return manifest


def verify_output(output_root: Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    manifest = read_json(output_root / "BATCH_MANIFEST.json")
    if manifest.get("schema") != "magireco-ac0911-event-global-route-batch-v1":
        raise ValueError("ac0911 v75 batch schema differs")
    routes = manifest.get("routes", [])
    if len(routes) != 9 or manifest.get("excluded_dirinfo_rows") != [8, 10, 11, 12, 13]:
        raise ValueError("ac0911 v75 route boundary differs")
    media = []
    for product in [*routes, manifest["showcase"]]:
        for edition in EDITIONS:
            row = product["media"][edition]
            path = output_root / row["path"]
            if file_sha256(path) != row["sha256"]:
                raise ValueError(f"{path}: SHA-256 differs")
            validate_output_media(path, expected_frames=int(product["total_frames"]), ffprobe=ffprobe)
            media.append(path)
    if len(media) != 30 or any(token in str(path).lower() for path in media for token in ("ac6003", "ac6004", "ac6005")):
        raise ValueError("audience count or P16/P17/P18 leakage differs")
    return {
        "schema": "magireco-ac0911-event-global-route-verification-v1",
        "result": "PASS",
        "independent_route_count": 9,
        "independent_route_edition_file_count": 27,
        "edited_showcase_edition_file_count": 3,
        "audience_mp4_count": 30,
        "native_416x232_30fps_h264_aac48k_stereo": True,
        "strict_no_bgm_row006_applied": True,
        "graphical_end_corrected_routes": ["dirinfo-row-001", "dirinfo-row-007", "dirinfo-row-009"],
        "source_media_modified": False,
        "p16_p17_p18_leakage_count": 0,
        "human_playback_required": True,
        "publication_approved": False,
    }


def build(plan_path: Path, output_root: Path, ffmpeg: str, ffprobe: str) -> Path:
    if output_root.exists():
        raise ValueError(f"immutable output already exists: {output_root}")
    plan = read_json(plan_path)
    state = validate_plan(plan, plan_path)
    authorities = validate_authorities(state)
    v35_sums = v35_sha_map(state["v35"])
    v35_manifest = read_json(state["v35"] / "BATCH_MANIFEST.json")
    if [row["product_id"].split("__", 1)[1] for row in v35_manifest.get("routes", [])] != state["routes"]:
        raise ValueError("v35 route order differs")
    strict_plan = read_json(state["strict_plan"])
    strict_product = next(row for row in strict_plan.get("products", []) if row.get("product_id") == "ac0911_dirinfo_row006_v69r2_strict_no_bgm")
    strict_media = {edition: str(strict_product["media"][edition]["sha256"]).upper() for edition in EDITIONS}

    staging = output_root.with_name(f".{output_root.name}.staging-{uuid.uuid4().hex}")
    family_root = staging / "ac0911"
    family_root.mkdir(parents=True)
    links = []
    try:
        font_dir = staging / "work" / "fonts"
        font_link = link_or_copy(state["font"], font_dir / state["font"].name)
        routes = []
        for route in state["routes"]:
            product, route_links = build_route(
                state=state,
                authorities=authorities,
                route=route,
                destination_root=family_root,
                staging=staging,
                font_dir=font_dir,
                v35_sums=v35_sums,
                strict_media=strict_media,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            routes.append(product)
            links.extend(route_links)
        showcase = build_showcase(route_manifests=routes, destination_root=family_root, ffmpeg=ffmpeg, ffprobe=ffprobe)
        shutil.rmtree(staging / "work")
        batch = {
            "schema": "magireco-ac0911-event-global-route-batch-v1",
            "status": STATUS,
            "family": "ac0911",
            "checkpoint_id": plan["checkpoint_id"],
            "audio_profile": "strict_no_bgm",
            "bgm_policy": "intentionally_excluded_using_sound_divide_tbl_authority",
            "routes": routes,
            "showcase": showcase,
            "edited_showcase_claim": SHOWCASE_CLAIM,
            "excluded_dirinfo_rows": plan["excluded_dirinfo_rows"],
            "source_bindings": {
                "plan": binding(plan_path),
                "v35_batch_manifest": binding(state["v35"] / "BATCH_MANIFEST.json"),
                "v35_sha256s": binding(state["v35"] / "SHA256SUMS.json"),
                "strict_no_bgm_plan": binding(state["strict_plan"]),
                "timing_authority": authorities["authority_summary"],
                "replacement_manifest_summary": authorities["replacement_summary"],
                "subtitle_layout": binding(state["layout"]),
                "font": font_link,
            },
            "materialization": {
                "reused_file_count": len(links),
                "hardlink_count": sum(row["policy"] == "hardlink" for row in links),
                "copy_count": sum(row["policy"] == "copy" for row in links),
                "all_reused_targets_verified": True,
            },
            "human_playback_approved": False,
            "publication_approved": False,
            "source_media_modified": False,
        }
        write_json(family_root / "BATCH_MANIFEST.json", batch)
        (family_root / "ROLLBACK.ps1").write_text(ROLLBACK_SCRIPT, encoding="utf-8")
        (family_root / "README_REVIEW.md").write_text(
            "# ac0911 v75 人工审查\n\n九条 DirInfo 成熟路线各有 none / JA / ZH；另有一个明确标注为编辑章节合集的三轨长版。row006 使用严格 no-BGM 修正版。全部文件仍需人工完整播放，自动 QA 不等于投稿批准。\n",
            encoding="utf-8",
        )
        sums = [
            {"path": str(path.relative_to(family_root)).replace("\\", "/"), "sha256": file_sha256(path), "byte_count": path.stat().st_size}
            for path in sorted(family_root.rglob("*"))
            if path.is_file() and path.name not in {"SHA256SUMS.json", "VERIFICATION.json"}
        ]
        write_json(family_root / "SHA256SUMS.json", {"schema": "magireco-versioned-output-sha256-v1", "family": "ac0911", "files": sums})
        os.replace(staging, output_root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    final = output_root / "ac0911"
    write_json(final / "VERIFICATION.json", verify_output(final, ffprobe))
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    final = args.output_root.resolve() / "ac0911"
    if args.verify_only:
        result = verify_output(final, args.ffprobe)
    else:
        final = build(args.plan.resolve(), args.output_root.resolve(), args.ffmpeg, args.ffprobe)
        result = read_json(final / "VERIFICATION.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
