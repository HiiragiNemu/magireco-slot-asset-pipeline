#!/usr/bin/env python3
"""Build a hash-bound, per-file Bilibili upload guide for one checkpoint."""

from __future__ import annotations

import argparse
import csv
import json
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac0908_reference_showcase import read_json, validate_bound_file
    from .build_independent_scene_release import file_sha256, write_json
except ImportError:  # direct script execution
    from build_ac0908_reference_showcase import (  # type: ignore
        read_json,
        validate_bound_file,
    )
    from build_independent_scene_release import file_sha256, write_json  # type: ignore


PLAN_SCHEMA = "magireco-checkpoint-upload-guide-plan-v1"
GUIDE_SCHEMA = "magireco-checkpoint-upload-guide-v1"
FIELDS = (
    "state",
    "target_bv",
    "subtitle_track",
    "absolute_folder",
    "exact_filename",
    "sha256",
    "suggested_part_name",
    "action",
    "automated_qa_status",
    "human_approval_status",
    "publication_instruction",
    "scope_note",
)


def _bound(
    raw: Mapping[str, Any],
    *,
    label: str,
    plan_dir: Path,
) -> tuple[Path, dict[str, str]]:
    path, snapshot = validate_bound_file(raw, label=label, plan_dir=plan_dir)
    return path, {
        "label": label,
        "path": str(path.resolve()),
        "sha256": str(snapshot["sha256"]).upper(),
    }


def _item(
    *,
    path: Path,
    expected_sha256: str,
    state: str,
    target_bv: str,
    subtitle_track: str,
    suggested_part_name: str,
    action: str,
    automated_qa_status: str,
    human_approval_status: str,
    publication_instruction: str,
    scope_note: str,
) -> dict[str, str]:
    path = path.resolve()
    expected = expected_sha256.upper()
    if not path.is_file() or file_sha256(path) != expected:
        raise ValueError(f"upload-guide file binding differs: {path}")
    return {
        "state": state,
        "target_bv": target_bv,
        "subtitle_track": subtitle_track,
        "absolute_folder": str(path.parent),
        "exact_filename": path.name,
        "sha256": expected,
        "suggested_part_name": suggested_part_name,
        "action": action,
        "automated_qa_status": automated_qa_status,
        "human_approval_status": human_approval_status,
        "publication_instruction": publication_instruction,
        "scope_note": scope_note,
    }


def _target(plan: Mapping[str, Any], name: str) -> str:
    targets = plan.get("target_bvs")
    if not isinstance(targets, Mapping) or not isinstance(targets.get(name), str):
        raise ValueError(f"upload guide lacks target BV {name}")
    return str(targets[name])


def _manifest_media(
    value: object,
    *,
    family_root: Path,
    family: str,
    product_prefix: str = "",
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        media_groups = [
            raw
            for raw in (value.get("media"), value.get("editions"))
            if isinstance(raw, Mapping)
        ]
        for media in media_groups:
            product = str(
                value.get("title")
                or value.get("product_id")
                or value.get("route_id")
                or product_prefix
                or family
            )
            for edition in ("none", "ja", "zh"):
                raw = media.get(edition)
                if not isinstance(raw, Mapping) or not raw.get("path") or not raw.get("sha256"):
                    continue
                path = Path(str(raw["path"]))
                if not path.is_absolute():
                    path = family_root / path
                output.append(
                    {
                        "family": family,
                        "product": product,
                        "edition": edition,
                        "path": str(path.resolve()),
                        "sha256": str(raw["sha256"]).upper(),
                    }
                )
        for key, child in value.items():
            if key not in {
                "media",
                "editions",
                "source_snapshots",
                "excluded_dirinfo_rows",
                "route_failures",
            }:
                output.extend(
                    _manifest_media(
                        child,
                        family_root=family_root,
                        family=family,
                        product_prefix=product_prefix,
                    )
                )
    elif isinstance(value, list):
        for child in value:
            output.extend(
                _manifest_media(
                    child,
                    family_root=family_root,
                    family=family,
                    product_prefix=product_prefix,
                )
            )
    unique: dict[str, dict[str, str]] = {}
    for row in output:
        unique[str(Path(row["path"]).resolve()).casefold()] = row
    return list(unique.values())


def _batch_target(plan: Mapping[str, Any], family: str, product: str) -> str:
    if family == "ac0908" and "参考合集" in product:
        return _target(plan, "ac0908_reference_showcase")
    names = {
        "ac0908": "ac0908_route_catalog",
        "ac4902": "ac4902_route_catalog",
        "ac4903": "ac4903_route_catalog",
        "ac6007": "ac6007_route_catalog",
        "ac7206": "ac7206_route_catalog",
        "ac7210": "story_collection",
    }
    return _target(plan, names.get(family, "future_catalog"))


def _track_target(plan: Mapping[str, Any], family: str, edition: str, product: str) -> str:
    if edition == "ja":
        return _target(plan, "future_ja_catalog")
    return _batch_target(plan, family, product)


def build(*, plan_path: Path, output_root: Path) -> Path:
    plan = read_json(plan_path)
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "active_upload_checkpoint"
        or not isinstance(plan.get("explicit_exclusions"), list)
    ):
        raise ValueError("unsupported checkpoint upload-guide plan")
    snapshots: list[dict[str, str]] = [
        {
            "label": "checkpoint upload-guide plan",
            "path": str(plan_path.resolve()),
            "sha256": file_sha256(plan_path),
        }
    ]
    source_paths: dict[str, Path] = {}
    for name, raw in plan["sources"].items():
        path, snapshot = _bound(
            raw,
            label=f"upload guide source {name}",
            plan_dir=plan_path.parent,
        )
        source_paths[name] = path
        snapshots.append(snapshot)

    items: list[dict[str, str]] = []

    uploaded = read_json(source_paths["owner_uploaded_exact_zh"])
    uploaded_root = Path(str(plan["directories"]["uploaded_zh"])).resolve()
    if uploaded.get("status") != "uploaded_by_project_owner":
        raise ValueError("owner-uploaded exact ZH source identity differs")
    for raw in uploaded.get("files", []):
        path = uploaded_root / str(raw["filename"])
        items.append(
            _item(
                path=path,
                expected_sha256=str(raw["sha256"]),
                state="already_uploaded",
                target_bv=_target(plan, "story_collection"),
                subtitle_track="ZH burned-in",
                suggested_part_name=str(raw["filename"]).removesuffix(".mp4"),
                action="none_already_uploaded_do_not_repeat",
                automated_qa_status="passed_at_original_checkpoint",
                human_approval_status="exact_file_owner_playback_approved_and_uploaded",
                publication_instruction="DO NOT REUPLOAD",
                scope_note="Approval and upload history bind only this exact ZH MP4 hash.",
            )
        )

    corrections = read_json(source_paths["owner_approved_corrections"])
    corrections_root = Path(str(plan["directories"]["corrections_review_now"])).resolve()
    if corrections.get("status") != "project_owner_playback_approved":
        raise ValueError("owner-approved correction source identity differs")
    approved_route_zh: dict[str, str] = {}
    for raw in corrections.get("files", []):
        part = str(raw["part"])
        edition = str(raw["edition"])
        if part.startswith("ac0908 route "):
            approved_route_zh[str(raw["filename"])] = str(raw["sha256"]).upper()
            continue
        path = corrections_root / str(raw["filename"])
        target = (
            _target(plan, "story_collection")
            if edition == "zh"
            else _target(plan, "future_ja_catalog")
        )
        items.append(
            _item(
                path=path,
                expected_sha256=str(raw["sha256"]),
                state="ready_to_upload",
                target_bv=target,
                subtitle_track=f"{edition.upper()} burned-in",
                suggested_part_name=str(raw["filename"]).removesuffix(".mp4"),
                action=(
                    "append_missing_story_part"
                    if edition == "zh"
                    else "append_to_future_ja_track_bv"
                ),
                automated_qa_status="passed",
                human_approval_status="exact_file_owner_playback_approved",
                publication_instruction="UPLOAD ALLOWED FOR THIS EXACT HASH",
                scope_note=(
                    "P12 is a route-aware deduplicated showcase; P23 carries the "
                    "owner-corrected 黑江/黑 identities."
                ),
            )
        )

    ac0908_path = source_paths["v30_ac0908_manifest"]
    ac0908 = read_json(ac0908_path)
    ac0908_root = ac0908_path.parent.parent
    if ac0908.get("status") != "OWNER_APPROVED_FULL_PRODUCTION_READY":
        raise ValueError("v30 ac0908 manifest identity differs")
    for row in _manifest_media(
        ac0908,
        family_root=ac0908_root,
        family="ac0908",
    ):
        path = Path(row["path"])
        edition = row["edition"]
        exact_route_approved = (
            edition == "zh"
            and (
                path.name in approved_route_zh
                and approved_route_zh[path.name] == row["sha256"]
            )
        )
        exact_showcase_approved = (
            edition == "zh"
            and "参考合集" in path.name
            and row["sha256"]
            == str(ac0908["showcase"]["approved_zh_hardlink"]["sha256"]).upper()
        )
        ready = exact_route_approved or exact_showcase_approved
        items.append(
            _item(
                path=path,
                expected_sha256=row["sha256"],
                state="ready_to_upload" if ready else "human_playback_required",
                target_bv=(
                    _target(plan, "ac0908_reference_showcase")
                    if "参考合集" in path.name
                    else _track_target(
                        plan, "ac0908", edition, row["product"]
                    )
                ),
                subtitle_track=(
                    "no burned-in subtitles"
                    if edition == "none"
                    else f"{edition.upper()} burned-in"
                ),
                suggested_part_name=path.stem,
                action=(
                    "create_or_append_route_part"
                    if ready and "参考合集" not in path.name
                    else (
                        "create_separate_reference_showcase_bv"
                        if ready
                        else "hold_for_owner_playback"
                    )
                ),
                automated_qa_status="passed",
                human_approval_status=(
                    "exact_file_owner_playback_approved"
                    if ready
                    else "not_approved_for_this_edition"
                ),
                publication_instruction=(
                    "UPLOAD ALLOWED FOR THIS EXACT HASH"
                    if ready
                    else "DO NOT UPLOAD YET"
                ),
                scope_note=(
                    "Six routes are mutually exclusive independent segments. The "
                    "reference showcase is an edited cross-route product, not one session."
                ),
            )
        )

    ac7210_path = source_paths["v30_ac7210_manifest"]
    ac7210 = read_json(ac7210_path)
    ac7210_root = ac7210_path.parent.parent
    if ac7210.get("status") != "OWNER_APPROVED_PRESENTATION_FULL_PRODUCTION_COMPLETE":
        raise ValueError("v30 ac7210 manifest identity differs")
    for row in _manifest_media(
        ac7210,
        family_root=ac7210_root,
        family="ac7210",
    ):
        path = Path(row["path"])
        ready = row["edition"] == "zh"
        items.append(
            _item(
                path=path,
                expected_sha256=row["sha256"],
                state="ready_to_upload" if ready else "human_playback_required",
                target_bv=(
                    _target(plan, "story_collection")
                    if ready
                    else _target(plan, "future_ja_catalog")
                    if row["edition"] == "ja"
                    else _target(plan, "ac7210_route_supplement")
                ),
                subtitle_track=(
                    "no burned-in subtitles"
                    if row["edition"] == "none"
                    else f"{row['edition'].upper()} burned-in"
                ),
                suggested_part_name=path.stem,
                action=(
                    "append_after_existing_P25"
                    if ready
                    else "hold_for_owner_playback"
                ),
                automated_qa_status="passed",
                human_approval_status=(
                    "exact_ZH_file_owner_playback_approved"
                    if ready
                    else "sibling_edition_not_playback_approved"
                ),
                publication_instruction=(
                    "UPLOAD ALLOWED FOR THIS EXACT HASH"
                    if ready
                    else "DO NOT UPLOAD YET"
                ),
                scope_note="Only DirInfo rows 0 and 1 are in this current product.",
            )
        )

    for source_name in (
        "v31_ac4902_manifest",
        "v31_ac7206_manifest",
        "v32_ac0908_manifest",
        "v33_ac4903_manifest",
        "v34_ac6007_manifest",
    ):
        if source_name not in source_paths:
            continue
        manifest_path = source_paths[source_name]
        value = read_json(manifest_path)
        family = str(value.get("family") or value.get("series") or "")
        for row in _manifest_media(
            value,
            family_root=manifest_path.parent,
            family=family,
        ):
            path = Path(row["path"])
            items.append(
                _item(
                    path=path,
                    expected_sha256=row["sha256"],
                    state="human_playback_required",
                    target_bv=_track_target(
                        plan, family, row["edition"], row["product"]
                    ),
                    subtitle_track=(
                        "no burned-in subtitles"
                        if row["edition"] == "none"
                        else f"{row['edition'].upper()} burned-in"
                    ),
                    suggested_part_name=path.stem,
                    action="hold_for_owner_playback",
                    automated_qa_status="passed",
                    human_approval_status="exact_output_not_yet_playback_approved",
                    publication_instruction="DO NOT UPLOAD YET",
                    scope_note=(
                        "Source/production contract is approved or evidence-ready, "
                        "but approval does not automatically transfer to this exact output."
                    ),
                )
            )

    keys = [(row["absolute_folder"].casefold(), row["exact_filename"].casefold()) for row in items]
    if len(keys) != len(set(keys)):
        raise RuntimeError("upload guide contains duplicate exact files")
    if any("superseded" in (folder + filename) for folder, filename in keys):
        raise RuntimeError("superseded media entered the upload guide")

    destination = output_root.resolve()
    if destination.exists():
        raise FileExistsError(f"versioned upload guide exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        with (staging / "UPLOAD_GUIDE.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(items)
        guide = {
            "schema": GUIDE_SCHEMA,
            "status": "UPLOAD_GUIDE_BUILT",
            "checkpoint_id": plan["checkpoint_id"],
            "target_bvs": plan["target_bvs"],
            "counts": {
                "already_uploaded": sum(row["state"] == "already_uploaded" for row in items),
                "ready_to_upload": sum(row["state"] == "ready_to_upload" for row in items),
                "human_playback_required": sum(
                    row["state"] == "human_playback_required" for row in items
                ),
                "explicit_exclusions": len(plan["explicit_exclusions"]),
                "total_exact_files": len(items),
            },
            "items": items,
            "explicit_exclusions": plan["explicit_exclusions"],
            "source_snapshots": snapshots,
            "codex_upload_performed": False,
        }
        write_json(staging / "UPLOAD_GUIDE.json", guide)

        sections = [
            "# MagiaReco Slot 本轮上传指南",
            "",
            "Codex 不执行上传。本指南只允许标为 `ready_to_upload` 的精确文件与 SHA-256；"
            "`human_playback_required`、隔离项和 superseded 审计项均禁止投稿。",
            "",
            f"- 已投稿且不要重复：{guide['counts']['already_uploaded']} 个",
            f"- 现在可投稿：{guide['counts']['ready_to_upload']} 个",
            f"- 必须先人工播放：{guide['counts']['human_playback_required']} 个",
            f"- 明确排除：{guide['counts']['explicit_exclusions']} 项",
            "",
            "## 现在可投稿",
            "",
            "| 目标 BV | 字幕轨 | 绝对文件夹 | 精确文件名 | 建议分P名 | 动作 | 自动QA | 人工批准 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in items:
            if row["state"] != "ready_to_upload":
                continue
            sections.append(
                "| {target_bv} | {subtitle_track} | `{absolute_folder}` | "
                "`{exact_filename}` | {suggested_part_name} | {action} | "
                "{automated_qa_status} | {human_approval_status} |".format(**row)
            )
        sections.extend(
            [
                "",
                "## 已投稿：不要重复",
                "",
            ]
        )
        for row in items:
            if row["state"] == "already_uploaded":
                sections.append(
                    f"- `{row['absolute_folder']}\\{row['exact_filename']}` "
                    f"SHA-256 `{row['sha256']}`"
                )
        sections.extend(
            [
                "",
                "## 必须先人工播放",
                "",
            ]
        )
        for row in items:
            if row["state"] == "human_playback_required":
                sections.append(
                    f"- [{row['subtitle_track']}] `{row['absolute_folder']}\\"
                    f"{row['exact_filename']}` → {row['target_bv']}；"
                    f"建议分P `{row['suggested_part_name']}`；当前禁止上传。"
                )
        sections.extend(["", "## 明确排除", ""])
        for row in plan["explicit_exclusions"]:
            sections.append(
                f"- **{row['scope']}**：{row['disposition']}；{row['reason']}"
            )
        (staging / "UPLOAD_GUIDE.md").write_text(
            "\n".join(sections) + "\n", encoding="utf-8"
        )
        hashes = [
            {
                "path": path.name,
                "sha256": file_sha256(path),
                "byte_count": path.stat().st_size,
            }
            for path in sorted(staging.iterdir())
            if path.is_file() and path.name != "SHA256SUMS.json"
        ]
        write_json(
            staging / "SHA256SUMS.json",
            {
                "schema": "magireco-versioned-output-sha256-v1",
                "files": hashes,
            },
        )
        staging.replace(destination)
        return destination
    except BaseException:
        import shutil

        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination = build(
        plan_path=args.plan.resolve(),
        output_root=args.output_root.resolve(),
    )
    value = read_json(destination / "UPLOAD_GUIDE.json")
    print(
        json.dumps(
            {
                "destination": str(destination),
                "counts": value["counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
