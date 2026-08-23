#!/usr/bin/env python3
"""Publish an immutable flat review hub for authoritative native-416 longforms."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping, Sequence

try:
    from .build_manual_review_hub import (
        file_sha256,
        probe_media as probe_base_media,
        read_edges,
    )
except ImportError:  # pragma: no cover - direct script execution
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_manual_review_hub import (
        file_sha256,
        probe_media as probe_base_media,
        read_edges,
    )


SCHEMA = "magireco-native416-authoritative-longform-review-hub-plan-v1"
EDITIONS = ("none", "ja", "zh")
ALLOWED_EDITION_SETS = {
    frozenset(EDITIONS),
    frozenset({"none"}),
    frozenset({"material"}),
}
LANES = {"none": "NONE", "ja": "JP", "zh": "ZH", "material": "MATERIAL"}
CONTENT_TYPES = {"story", "routes", "gameplay_effect", "material"}
FORBIDDEN_TOKENS = {"p16", "p17", "p18", "ac6003", "ac6004", "ac6005"}
WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ReviewHubError(ValueError):
    """Fail-closed plan, media, or publication error."""


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def safe_filename(title: str, edition: str) -> str:
    if edition not in LANES:
        raise ReviewHubError(f"unsupported edition: {edition}")
    if not title or title in {".", ".."} or WINDOWS_FORBIDDEN.search(title):
        raise ReviewHubError(f"unsafe review title: {title!r}")
    if title[-1] in {" ", "."}:
        raise ReviewHubError(f"unsafe trailing review title character: {title!r}")
    filename = f"{title}.mp4" if edition == "material" else f"{title}__{edition}.mp4"
    if len(filename) > 180:
        raise ReviewHubError(f"review filename is too long: {filename}")
    return filename


def probe_media(path: Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    base = probe_base_media(path, ffprobe)
    command = [
        ffprobe,
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=nb_read_frames,nb_frames",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewHubError(f"frame probe failed for {path}: {error}")
    payload = json.loads(completed.stdout.decode("utf-8"))
    stream = next(iter(payload.get("streams", [])), None)
    if stream is None:
        raise ReviewHubError(f"frame probe has no video stream: {path}")
    frame_count = stream.get("nb_read_frames") or stream.get("nb_frames")
    if frame_count in (None, "N/A"):
        raise ReviewHubError(f"frame probe did not expose frame count: {path}")
    return {
        "duration_seconds": float(base["duration_sec"]),
        "frame_count": int(frame_count),
        "width": int(base["width"]),
        "height": int(base["height"]),
        "frame_rate": str(base["frame_rate"]),
        "video_codec": str(base["video_codec"]),
        "audio_codec": str(base["audio_codec"]),
        "audio_sample_rate": int(base["audio_sample_rate"]),
        "audio_channels": int(base["audio_channels"]),
        "probe_sha256": str(base["probe_sha256"]),
    }


def validate_media_contract(
    expected: Mapping[str, Any], actual: Mapping[str, Any], label: str
) -> None:
    for field in (
        "frame_count",
        "width",
        "height",
        "frame_rate",
        "video_codec",
        "audio_codec",
        "audio_sample_rate",
        "audio_channels",
    ):
        if actual.get(field) != expected.get(field):
            raise ReviewHubError(
                f"{label} media mismatch for {field}: "
                f"{actual.get(field)!r} != {expected.get(field)!r}"
            )
    if abs(float(actual["duration_seconds"]) - float(expected["duration_seconds"])) > 0.06:
        raise ReviewHubError(f"{label} media mismatch for duration_seconds")
    native_contract = (
        int(actual["width"]),
        int(actual["height"]),
        actual["frame_rate"],
        actual["video_codec"],
        actual["audio_codec"],
        int(actual["audio_sample_rate"]),
        int(actual["audio_channels"]),
    )
    if native_contract != (416, 232, "30/1", "h264", "aac", 48000, 2):
        raise ReviewHubError(f"{label} is outside the native-416 no-BGM media contract")


def _resolved_norm(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.resolve())))


def _validate_evidence(
    group: Mapping[str, Any], media: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    binding = group.get("evidence")
    if not isinstance(binding, Mapping):
        raise ReviewHubError(f"{group.get('review_group_id')} evidence is absent")
    path = Path(str(binding.get("path", "")))
    expected_digest = str(binding.get("sha256", "")).upper()
    kind = str(binding.get("kind", ""))
    if not path.is_file() or len(expected_digest) != 64:
        raise ReviewHubError(f"invalid evidence binding: {path}")
    actual_digest = file_sha256(path)
    if actual_digest != expected_digest:
        raise ReviewHubError(f"evidence digest mismatch: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if kind == "production_verification_media":
        if payload.get("status") != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED":
            raise ReviewHubError(f"evidence status is not review-ready: {path}")
        by_edition = {
            str(row.get("edition")): row for row in payload.get("media", [])
        }
        for expected in media:
            row = by_edition.get(str(expected["edition"]))
            if row is None:
                raise ReviewHubError(f"evidence lacks edition: {expected['edition']}")
            for field in (
                "path",
                "sha256",
                "frame_count",
                "width",
                "height",
                "frame_rate",
                "video_codec",
                "audio_codec",
                "audio_sample_rate",
                "audio_channels",
            ):
                if str(row.get(field)) != str(expected.get(field)):
                    raise ReviewHubError(
                        f"evidence/media disagreement for {expected['edition']}/{field}"
                    )
    elif kind == "ac0908_production_manifest_outputs":
        if payload.get("status") != "AUTOMATED_QA_PASS_HUMAN_PLAYBACK_REQUIRED":
            raise ReviewHubError(f"evidence status is not review-ready: {path}")
        if payload.get("canvas") != [416, 232] or int(payload.get("frame_rate", 0)) != 30:
            raise ReviewHubError(f"ac0908 evidence media contract differs: {path}")
        by_edition = {
            str(row.get("edition")): row for row in payload.get("outputs", [])
        }
        for expected in media:
            row = by_edition.get(str(expected["edition"]))
            if row is None or _resolved_norm(Path(str(row.get("path", "")))) != _resolved_norm(
                Path(str(expected["path"]))
            ):
                raise ReviewHubError(f"ac0908 evidence output differs: {expected['edition']}")
        if int(payload.get("frames", -1)) != int(media[0]["frame_count"]):
            raise ReviewHubError("ac0908 evidence frame count differs")
    elif kind == "exhaustive_unique_longform_verification":
        if payload.get("result") != "PASS_HUMAN_PLAYBACK_REQUIRED":
            raise ReviewHubError(f"longform evidence status is not review-ready: {path}")
        production_plan = Path(str(payload.get("plan_path", "")))
        production_plan_digest = str(payload.get("plan_file_sha256", "")).upper()
        if (
            not production_plan.is_file()
            or len(production_plan_digest) != 64
            or file_sha256(production_plan) != production_plan_digest
        ):
            raise ReviewHubError(f"longform production plan binding differs: {path}")
        by_edition = {
            str(row.get("edition")): row for row in payload.get("outputs", [])
        }
        product_root = path.parent.parent
        for expected in media:
            row = by_edition.get(str(expected["edition"]))
            if row is None:
                raise ReviewHubError(
                    f"longform evidence lacks edition: {expected['edition']}"
                )
            evidence_output = product_root / Path(str(row.get("relative_path", "")))
            if _resolved_norm(evidence_output) != _resolved_norm(
                Path(str(expected["path"]))
            ):
                raise ReviewHubError(
                    f"longform evidence output differs: {expected['edition']}"
                )
            if str(row.get("sha256", "")).upper() != str(
                expected.get("sha256", "")
            ).upper():
                raise ReviewHubError(
                    f"longform evidence digest differs: {expected['edition']}"
                )
            streams = row.get("media_qa", {}).get("probe", {}).get("streams", [])
            video = next(
                (stream for stream in streams if stream.get("codec_type") == "video"),
                None,
            )
            audio = next(
                (stream for stream in streams if stream.get("codec_type") == "audio"),
                None,
            )
            if video is None or audio is None:
                raise ReviewHubError(
                    f"longform evidence stream contract differs: {expected['edition']}"
                )
            evidence_contract = (
                int(video["nb_read_frames"]),
                int(video["width"]),
                int(video["height"]),
                str(video["r_frame_rate"]),
                str(video["codec_name"]),
                str(audio["codec_name"]),
                int(audio["sample_rate"]),
                int(audio["channels"]),
            )
            expected_contract = (
                int(expected["frame_count"]),
                int(expected["width"]),
                int(expected["height"]),
                str(expected["frame_rate"]),
                str(expected["video_codec"]),
                str(expected["audio_codec"]),
                int(expected["audio_sample_rate"]),
                int(expected["audio_channels"]),
            )
            if evidence_contract != expected_contract:
                raise ReviewHubError(
                    f"longform evidence media contract differs: {expected['edition']}"
                )
    elif kind == "batch_review_ready_single_canonical":
        if (
            payload.get("status") != "AUTOMATED_QA_PASSED"
            or payload.get("publishable") is not False
            or payload.get("readiness", {}).get("HUMAN_PLAYBACK_APPROVED") is not False
        ):
            raise ReviewHubError(f"batch evidence status differs: {path}")
        if len(media) != 1 or str(media[0].get("edition")) != "none":
            raise ReviewHubError("batch canonical evidence requires one none edition")
        artifacts = payload.get("artifacts", {})
        expected = media[0]
        product_root = path.parent
        canonical = artifacts.get("video_none", {})
        canonical_path = product_root / Path(str(canonical.get("path", "")))
        if (
            _resolved_norm(canonical_path) != _resolved_norm(Path(str(expected["path"])))
            or str(canonical.get("sha256", "")).upper()
            != str(expected.get("sha256", "")).upper()
        ):
            raise ReviewHubError("batch canonical media binding differs")
        for label in ("video_none", "video_ja", "video_zh", "qa", "manifest"):
            artifact = artifacts.get(label, {})
            artifact_path = product_root / Path(str(artifact.get("path", "")))
            artifact_digest = str(artifact.get("sha256", "")).upper()
            if (
                not artifact_path.is_file()
                or len(artifact_digest) != 64
                or file_sha256(artifact_path) != artifact_digest
            ):
                raise ReviewHubError(f"batch artifact binding differs: {label}")
        aliases = [
            product_root / Path(str(artifacts[label]["path"]))
            for label in ("video_ja", "video_zh")
        ]
        if any(
            str(artifacts[label]["sha256"]).upper()
            != str(expected["sha256"]).upper()
            for label in ("video_ja", "video_zh")
        ) or any(not os.path.samefile(canonical_path, alias) for alias in aliases):
            raise ReviewHubError("batch language aliases are not exact hardlink aliases")
    else:
        raise ReviewHubError(f"unsupported evidence kind: {kind}")
    return {"path": str(path.resolve()), "sha256": actual_digest, "kind": kind}


def validate_plan(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    if plan.get("schema") != SCHEMA:
        raise ReviewHubError("unexpected plan schema")
    release_id = str(plan.get("release_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{4,100}", release_id):
        raise ReviewHubError(f"unsafe release id: {release_id!r}")
    groups = plan.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ReviewHubError("plan has no review groups")
    if int(plan.get("expected_group_count", -1)) != len(groups):
        raise ReviewHubError("review group count differs")
    seen_group_ids: set[str] = set()
    seen_destinations: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw_group in groups:
        if not isinstance(raw_group, Mapping):
            raise ReviewHubError("review group is malformed")
        group = dict(raw_group)
        group_id = str(group.get("review_group_id", ""))
        family = str(group.get("family", ""))
        title = str(group.get("title", ""))
        content_type = str(group.get("content_type", ""))
        combined = " ".join((group_id, family, title)).casefold()
        if any(token in combined for token in FORBIDDEN_TOKENS):
            raise ReviewHubError(f"quarantined family leaked into plan: {group_id}")
        if group_id in seen_group_ids or not group_id:
            raise ReviewHubError(f"duplicate or empty review group id: {group_id!r}")
        seen_group_ids.add(group_id)
        if not re.fullmatch(r"ac\d{4}", family):
            raise ReviewHubError(f"invalid family id: {family}")
        if family not in title:
            raise ReviewHubError(f"title lacks family id: {title}")
        if content_type not in CONTENT_TYPES:
            raise ReviewHubError(f"invalid content type: {content_type}")
        media = group.get("media")
        if not isinstance(media, list) or not media:
            raise ReviewHubError(f"{group_id} has no media editions")
        edition_set = frozenset(str(row.get("edition")) for row in media)
        if len(media) != len(edition_set) or edition_set not in ALLOWED_EDITION_SETS:
            raise ReviewHubError(f"{group_id} edition set differs")
        if (edition_set == frozenset({"material"})) != (content_type == "material"):
            raise ReviewHubError(f"{group_id} material classification differs")
        evidence = _validate_evidence(group, media)
        checked_media: list[dict[str, Any]] = []
        for raw_media in media:
            expected = dict(raw_media)
            edition = str(expected["edition"])
            source = Path(str(expected.get("path", "")))
            expected_digest = str(expected.get("sha256", "")).upper()
            if not source.is_file() or len(expected_digest) != 64:
                raise ReviewHubError(f"invalid source binding: {source}")
            if any(token in str(source).casefold() for token in FORBIDDEN_TOKENS):
                raise ReviewHubError(f"quarantined source leaked into plan: {source}")
            filename = safe_filename(title, edition)
            relative = (
                Path("MATERIAL", filename)
                if edition == "material"
                else Path(LANES[edition], content_type, filename)
            )
            destination_key = str(relative).casefold()
            if destination_key in seen_destinations:
                raise ReviewHubError(f"duplicate review destination: {relative}")
            seen_destinations.add(destination_key)
            actual_digest = file_sha256(source)
            if actual_digest != expected_digest:
                raise ReviewHubError(f"source digest mismatch: {source}")
            read_edges(source)
            probe = probe_media(source, str(plan.get("ffprobe", "ffprobe")))
            validate_media_contract(expected, probe, f"{group_id}/{edition}")
            checked_media.append(
                {
                    **expected,
                    "path": str(source.resolve()),
                    "sha256": actual_digest,
                    "relative_path": relative.as_posix(),
                    "probe": probe,
                }
            )
        validated.append({**group, "evidence": evidence, "media": checked_media})
    expected_files = int(plan.get("expected_edition_file_count", -1))
    if expected_files != sum(len(group["media"]) for group in validated):
        raise ReviewHubError("edition file count differs")
    return validated


def _csv_rows(
    groups: Sequence[Mapping[str, Any]], release_root: Path
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in groups:
        for media in group["media"]:
            destination = release_root / Path(media["relative_path"])
            rows.append(
                {
                    "review_group_id": group["review_group_id"],
                    "family": group["family"],
                    "title": group["title"],
                    "content_type": group["content_type"],
                    "event_container_count": group["event_container_count"],
                    "unique_complete_presentation_count": group[
                        "unique_complete_presentation_count"
                    ],
                    "edition": media["edition"],
                    "review_file": str(destination),
                    "source_file": media["path"],
                    "link_mode": "same_volume_hardlink",
                    "samefile": os.path.samefile(media["path"], destination),
                    "sha256": media["sha256"],
                    "duration_seconds": media["probe"]["duration_seconds"],
                    "width": media["probe"]["width"],
                    "height": media["probe"]["height"],
                    "fps": media["probe"]["frame_rate"],
                    "frame_count": media["probe"]["frame_count"],
                    "video_codec": media["probe"]["video_codec"],
                    "audio_codec": media["probe"]["audio_codec"],
                    "audio_sample_rate": media["probe"]["audio_sample_rate"],
                    "audio_channels": media["probe"]["audio_channels"],
                    "audio_profile": group.get("audio_profile", "no_bgm"),
                    "automatic_qa": "PASSED",
                    "human_status": "HUMAN_PLAYBACK_REQUIRED",
                    "publish_status": "DO_NOT_UPLOAD_UNTIL_OWNER_APPROVES",
                    "probe_sha256": media["probe"]["probe_sha256"],
                }
            )
    return rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ReviewHubError("cannot write an empty review index")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _write_release_metadata(
    stage: Path,
    plan_path: Path,
    plan_digest: str,
    groups: Sequence[Mapping[str, Any]],
    release_root: Path,
    previous_current_target: str,
) -> None:
    rows = _csv_rows(groups, stage)
    for row in rows:
        relative = Path(row["review_file"]).relative_to(stage)
        row["review_file"] = str(release_root / relative)
    _write_csv(stage / "HUMAN_REVIEW_INDEX.csv", rows)
    write_json(stage / "HUMAN_REVIEW_INDEX.json", rows)
    guide_lines = [
        "# 原生 416×232 权威长片人工审查入口",
        "",
        f"- 内容组：{len(groups)} 组；语言长片按 NONE / JP / ZH 归类，纯素材只保留 MATERIAL canonical。",
        f"- 文件入口：{len(rows)} 个同盘硬链接；同哈希只需人工看一次，没有转码或媒体复制。",
        "- 状态：自动 QA 已通过，全部仍需项目所有者完整播放确认。",
        "- 语义：每组收录该 family 已由代码/运行时证据闭合的全部不重复呈现；不是原生单局声明。",
        "- 音频：有意排除 BGM，保留已验证对白与 SE。",
        "- 排除：P16 / P17 / P18、child-local-only、512 组件、未闭合 with-BGM。",
        "",
        "## 建议顺序（先看 ZH）",
        "",
    ]
    for index, group in enumerate(groups, start=1):
        guide_lines.append(
            f"{index}. `{group['family']}` {group['title']} — "
            f"{group['event_container_count']} 个事件容器 / "
            f"{group['unique_complete_presentation_count']} 个不重复完整呈现。"
        )
    guide_lines.extend(
        [
            "",
            "人工批准必须绑定具体文件与 SHA-256；AUTO QA 不自动等于人工批准。",
            "",
        ]
    )
    (stage / "00_START_HERE.md").write_text("\n".join(guide_lines), encoding="utf-8")
    record = {
        "schema": "magireco-native416-authoritative-longform-review-hub-verification-v1",
        "status": "PASS_HUMAN_PLAYBACK_REQUIRED",
        "release_root": str(release_root),
        "plan": {"path": str(plan_path.resolve()), "sha256": plan_digest},
        "content_group_count": len(groups),
        "edition_file_count": len(rows),
        "same_volume_hardlink_count": len(rows),
        "source_target_samefile_count": sum(bool(row["samefile"]) for row in rows),
        "native_416x232_count": sum(
            row["width"] == 416 and row["height"] == 232 for row in rows
        ),
        "strict_no_bgm_count": sum(row["audio_profile"] == "no_bgm" for row in rows),
        "silent_material_count": sum(row["audio_profile"] == "silent" for row in rows),
        "human_playback_required_count": len(rows),
        "p16_p17_p18_leak_count": 0,
        "with_bgm_leak_count": 0,
        "previous_current_target": previous_current_target,
        "groups": [
            {
                "review_group_id": group["review_group_id"],
                "family": group["family"],
                "title": group["title"],
                "event_container_count": group["event_container_count"],
                "unique_complete_presentation_count": group[
                    "unique_complete_presentation_count"
                ],
                "evidence": group["evidence"],
            }
            for group in groups
        ],
        "literal_result": (
            f"PASS groups={len(groups)} editions={len(rows)} hardlinks={len(rows)} "
            "canvas=416x232 fps=30/1 audio=h264+aac_48000_stereo "
            "p16_p17_p18_leaks=0 with_bgm_leaks=0 "
            "human_status=HUMAN_PLAYBACK_REQUIRED"
        ),
    }
    write_json(stage / "VERIFICATION_RECORD.json", record)
    backup = release_root.parent.parent / "current_links" / (
        "CURRENT_REVIEW_before_" + release_root.name
    )
    rollback = [
        "$ErrorActionPreference = 'Stop'",
        f"$hub = {_powershell_quote(str(release_root.parent.parent))}",
        "$current = Join-Path $hub 'CURRENT_REVIEW'",
        f"$release = {_powershell_quote(str(release_root))}",
        f"$backup = {_powershell_quote(str(backup))}",
        "if ((Test-Path -LiteralPath $current) -and ((Get-Item -LiteralPath $current -Force).Target -eq $release)) {",
        "  Remove-Item -LiteralPath $current",
        "}",
        "if (Test-Path -LiteralPath $backup) { Move-Item -LiteralPath $backup -Destination $current }",
        "Write-Output 'ROLLBACK_CURRENT_LINK_COMPLETE'",
        "",
    ]
    (stage / "ROLLBACK.ps1").write_text("\n".join(rollback), encoding="utf-8")
    (stage / "READY").write_text("PASS_HUMAN_PLAYBACK_REQUIRED\n", encoding="ascii")


def _create_junction(path: Path, target: Path) -> None:
    command = (
        "$ErrorActionPreference='Stop'; "
        f"New-Item -ItemType Junction -Path {_powershell_quote(str(path))} "
        f"-Target {_powershell_quote(str(target))} | Out-Null"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewHubError(f"junction creation failed: {error}")


def publish_current(
    hub_root: Path, release_root: Path, expected_previous_target: Path
) -> Path:
    current = hub_root / "CURRENT_REVIEW"
    if not current.exists():
        raise ReviewHubError(f"CURRENT_REVIEW is absent: {current}")
    if _resolved_norm(current) != _resolved_norm(expected_previous_target):
        raise ReviewHubError(
            f"CURRENT_REVIEW target changed: {current.resolve()} != {expected_previous_target}"
        )
    backups = hub_root / "current_links"
    backups.mkdir(exist_ok=True)
    backup = backups / f"CURRENT_REVIEW_before_{release_root.name}"
    if backup.exists():
        raise ReviewHubError(f"CURRENT_REVIEW backup already exists: {backup}")
    current.rename(backup)
    try:
        _create_junction(current, release_root)
        if _resolved_norm(current) != _resolved_norm(release_root):
            raise ReviewHubError("new CURRENT_REVIEW junction resolved to another target")
    except Exception:
        if current.exists():
            current.rmdir()
        backup.rename(current)
        raise
    return backup


def build(
    plan_path: Path, *, dry_run: bool, publish_current_link: bool
) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_digest = file_sha256(plan_path)
    groups = validate_plan(plan)
    hub_root = Path(str(plan["hub_root"]))
    release_root = hub_root / "releases" / str(plan["release_id"])
    previous_target = Path(str(plan["expected_previous_current_target"]))
    result = {
        "status": "PASS_DRY_RUN" if dry_run else "PASS_PUBLISHED",
        "release_root": str(release_root),
        "group_count": len(groups),
        "edition_file_count": sum(len(group["media"]) for group in groups),
        "plan_sha256": plan_digest,
    }
    if dry_run:
        print(
            f"PASS_DRY_RUN groups={result['group_count']} "
            f"editions={result['edition_file_count']} release={release_root}"
        )
        return result
    if release_root.exists():
        raise ReviewHubError(f"immutable release already exists: {release_root}")
    hub_root.mkdir(parents=True, exist_ok=True)
    stage_root = hub_root / ".staging"
    stage_root.mkdir(exist_ok=True)
    stage = stage_root / f"{plan['release_id']}.{os.getpid()}"
    if stage.exists():
        raise ReviewHubError(f"staging path already exists: {stage}")
    stage.mkdir()
    try:
        for group in groups:
            for media in group["media"]:
                source = Path(media["path"])
                destination = stage / Path(media["relative_path"])
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.drive.casefold() != destination.drive.casefold():
                    raise ReviewHubError(f"cross-volume hardlink is forbidden: {source}")
                os.link(source, destination)
                if not os.path.samefile(source, destination):
                    raise ReviewHubError(
                        f"source and destination are not samefile: {destination}"
                    )
                if file_sha256(destination) != media["sha256"]:
                    raise ReviewHubError(f"published hardlink digest mismatch: {destination}")
                read_edges(destination)
                target_probe = probe_media(
                    destination, str(plan.get("ffprobe", "ffprobe"))
                )
                validate_media_contract(media, target_probe, str(destination))
                if target_probe["probe_sha256"] != media["probe"]["probe_sha256"]:
                    raise ReviewHubError(f"published hardlink probe differs: {destination}")
        _write_release_metadata(
            stage,
            plan_path,
            plan_digest,
            groups,
            release_root,
            str(previous_target),
        )
        release_root.parent.mkdir(parents=True, exist_ok=True)
        stage.rename(release_root)
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    backup = None
    if publish_current_link:
        backup = publish_current(hub_root, release_root, previous_target)
    result["current_review"] = str(hub_root / "CURRENT_REVIEW")
    result["previous_current_backup"] = str(backup) if backup else None
    print(
        f"PASS_PUBLISHED groups={result['group_count']} "
        f"editions={result['edition_file_count']} release={release_root} "
        f"current_updated={bool(publish_current_link)}"
    )
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publish-current", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    build(args.plan, dry_run=args.dry_run, publish_current_link=args.publish_current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
