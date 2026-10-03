#!/usr/bin/env python3
"""Build a human-review package for visual-only materials.

New plans default to one canonical ``material`` item.  The historical
three-target hardlink layout is supported only when a plan explicitly requests
``legacy_three_target_aliases`` so old checkpoints remain reproducible.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


LEGACY_EDITIONS = ("none", "ja", "zh")
MATERIAL_EDITION = "material"
PACKAGING_MODES = (
    "single_visual_canonical",
    "legacy_three_target_aliases",
)
FORBIDDEN = (
    "ac6003",
    "ac6004",
    "ac6005",
    "p16",
    "p17",
    "p18",
    "quarantine",
    "superseded",
)


def validate_publication_state(human_status: str, publication_state: str) -> None:
    if human_status not in {"human_playback_required", "human_playback_approved"}:
        raise ValueError("v2 material human approval status differs")
    if publication_state not in {
        "human_playback_required", "ready_to_upload", "already_uploaded"
    }:
        raise ValueError("v2 material publication state differs")
    if publication_state != "human_playback_required" and human_status != "human_playback_approved":
        raise ValueError("material publication requires exact human playback approval")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_bound_file(raw: object, *, label: str, base: Path) -> Path:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} binding must be an object")
    path = Path(str(raw.get("path", "")))
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    expected = str(raw.get("sha256", "")).strip().upper()
    if not path.is_file() or not re.fullmatch(r"[0-9A-F]{64}", expected):
        raise ValueError(f"{label} binding is incomplete: {path}")
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(
            f"{label} SHA-256 differs: {path}; expected={expected} actual={actual}"
        )
    return path


def probe_video(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    streams = value.get("streams", [])
    video = next(
        (row for row in streams if row.get("codec_type") == "video"),
        None,
    )
    audio = next(
        (row for row in streams if row.get("codec_type") == "audio"),
        None,
    )
    if not video:
        raise ValueError(f"material output lacks video: {path}")
    return {
        "duration_seconds": round(float(value["format"]["duration"]), 6),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "frame_rate": str(video.get("r_frame_rate", "")),
        "video_codec": str(video.get("codec_name", "")),
        "audio_codec": str(audio.get("codec_name", "")) if audio else "",
        "audio_sample_rate": str(audio.get("sample_rate", "")) if audio else "",
        "audio_channels": int(audio.get("channels", 0) or 0) if audio else 0,
    }


def _part_name(title: str, family: str, edition: str) -> str:
    base = f"{title} {family}"
    if edition == MATERIAL_EDITION:
        return base + "（视觉素材）"
    if edition == "ja":
        return base + "__ja"
    if edition == "zh":
        return base + " 中文版"
    return base


def _packaged_filename(
    upload_id: str,
    title: str,
    family: str,
    edition: str,
) -> str:
    base = f"{upload_id}_{title}_{family}"
    if edition == MATERIAL_EDITION:
        return base + ".mp4"
    return f"{base}__{edition}.mp4"


def assign_review_batches(
    products: list[dict],
    *,
    max_products: int = 10,
    max_duration_seconds: float = 1800.0,
) -> dict[str, str]:
    """Assign human-review products to bounded, stable batch names."""

    if max_products < 1 or max_duration_seconds <= 0:
        raise ValueError("review batch limits must be positive")
    assignments: dict[str, str] = {}
    batch_number = 1
    batch_count = 0
    batch_duration = 0.0
    for product in products:
        if product.get("publication_state") != "human_playback_required":
            continue
        duration = float(product.get("duration_seconds", 0.0))
        if duration < 0:
            raise ValueError("material review duration must be non-negative")
        if batch_count and (
            batch_count >= max_products
            or batch_duration + duration > max_duration_seconds
        ):
            batch_number += 1
            batch_count = 0
            batch_duration = 0.0
        collection = str(product.get("collection", ""))
        if not collection or collection in assignments:
            raise ValueError("material review collection cannot be batched")
        assignments[collection] = f"batch_{batch_number:03d}"
        batch_count += 1
        batch_duration += duration
    return assignments


def review_batch_directories(
    packaging_mode: str,
    editions: tuple[str, ...],
    assignments: dict[str, str],
) -> list[str]:
    batches = sorted(set(assignments.values())) or ["batch_001"]
    if packaging_mode == "single_visual_canonical":
        return [f"02_REVIEW_MATERIAL/{batch}" for batch in batches]
    return [
        f"02_REVIEW_MATERIAL/{batch}/{edition}"
        for batch in batches
        for edition in editions
    ]


def _target(edition: str, width: int = 416, height: int = 232) -> str:
    if edition == MATERIAL_EDITION:
        return f"新建建议：MagiaReco Slot 原生{width}x{height}玩法／素材合集 BV"
    return (
        f"新建建议：MagiaReco Slot 原生{width}x{height}玩法／素材合集 "
        f"({edition}) BV"
    )


INDEX_FIELDS = (
    "upload_id",
    "queue",
    "batch",
    "packaged_file",
    "packaged_absolute_path",
    "source_absolute_path",
    "link_mode",
    "sha256",
    "canonical_sha256",
    "canonical_packaged_file",
    "is_canonical_exact_hash",
    "physical_duplicate",
    "duration_seconds",
    "width",
    "height",
    "frame_rate",
    "video_codec",
    "audio_codec",
    "audio_sample_rate",
    "audio_channels",
    "family",
    "route",
    "presentation_role",
    "edition",
    "subtitle_track",
    "automated_qa_status",
    "human_approval_status",
    "publication_state",
    "suggested_action",
    "target_bv",
    "suggested_part_name",
    "source_manifest",
    "source_manifest_sha256",
)


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build(*, plan_path: Path, output_root: Path, ffprobe: str) -> Path:
    plan_path = plan_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite review root: {output_root}")
    plan = read_json(plan_path)
    schema = str(plan.get("schema", ""))
    if schema not in {
        "magireco-incremental-material-review-plan-v1",
        "magireco-incremental-material-review-plan-v2",
    }:
        raise ValueError("incremental material review plan schema differs")
    guide_path = validate_bound_file(
        plan.get("source_upload_guide"),
        label="source upload guide",
        base=plan_path.parent,
    )
    products = plan.get("products")
    if not isinstance(products, list) or not products:
        raise ValueError("incremental material review plan has no products")
    start_id = int(plan.get("start_upload_id", 0))
    if start_id < 1:
        raise ValueError("start_upload_id must be positive")
    expected_dimensions = plan.get("expected_dimensions")
    if expected_dimensions is None and schema.endswith("-v1"):
        expected_dimensions = {"width": 416, "height": 232}
    if expected_dimensions is not None and (
        not isinstance(expected_dimensions, dict)
        or set(expected_dimensions) != {"width", "height"}
    ):
        raise ValueError("incremental material expected_dimensions differs")
    expected_width = (
        int(expected_dimensions["width"])
        if expected_dimensions is not None
        else None
    )
    expected_height = (
        int(expected_dimensions["height"])
        if expected_dimensions is not None
        else None
    )
    if expected_width is not None and (
        expected_width < 1 or expected_height is None or expected_height < 1
    ):
        raise ValueError("incremental material expected dimensions are invalid")
    checkpoint_label = str(plan.get("checkpoint_label", "v42")).strip()
    if not re.fullmatch(r"v\d+(?:r\d+)?", checkpoint_label):
        raise ValueError("incremental material checkpoint label differs")
    source_guide_copy_name = str(
        plan.get(
            "source_guide_copy_name",
            "SOURCE_GLOBAL_UPLOAD_GUIDE_V42.json",
        )
    ).strip()
    if not re.fullmatch(r"[A-Z0-9_]+\.json", source_guide_copy_name):
        raise ValueError("incremental material guide copy name differs")
    packaging_mode = str(
        plan.get(
            "packaging_mode",
            (
                "legacy_three_target_aliases"
                if schema.endswith("-v1")
                else "single_visual_canonical"
            ),
        )
    ).strip()
    if packaging_mode not in PACKAGING_MODES:
        raise ValueError("incremental material packaging_mode differs")
    if schema.endswith("-v2") and packaging_mode != "single_visual_canonical":
        raise ValueError("v2 material plans require single_visual_canonical")
    editions = (
        LEGACY_EDITIONS
        if packaging_mode == "legacy_three_target_aliases"
        else (MATERIAL_EDITION,)
    )
    specific_exclusions = plan.get("specific_exclusions", [])
    if not isinstance(specific_exclusions, list) or any(
        not isinstance(value, str) or not value.strip()
        for value in specific_exclusions
    ):
        raise ValueError("incremental material specific exclusions differ")
    superseded_packages = plan.get("superseded_packages", [])
    if not isinstance(superseded_packages, list):
        raise ValueError("incremental material superseded_packages differs")
    prepared_superseded: list[dict] = []
    seen_superseded_ids: set[str] = set()
    for raw in superseded_packages:
        if not isinstance(raw, dict):
            raise ValueError("superseded package declaration must be an object")
        upload_id = str(raw.get("upload_id", "")).strip().upper()
        disposition = str(raw.get("disposition", "")).strip()
        reason = str(raw.get("reason", "")).strip()
        if (
            not re.fullmatch(r"U\d{3}", upload_id)
            or upload_id in seen_superseded_ids
            or disposition not in {
                "superseded_by_single_visual_canonical",
                "superseded_by_review_batch_metadata_fix",
                "withdrawn_nonstandalone_overlay",
            }
            or not reason
        ):
            raise ValueError("superseded package contract differs")
        seen_superseded_ids.add(upload_id)
        summary_path = validate_bound_file(
            raw.get("package_summary"),
            label=f"{upload_id} superseded package summary",
            base=plan_path.parent,
        )
        summary = read_json(summary_path)
        preserved_manifest_path: Path | None = None
        preserved_manifest = raw.get("preserved_source_manifest")
        if preserved_manifest is not None:
            preserved_manifest_path = validate_bound_file(
                preserved_manifest,
                label=f"{upload_id} preserved source manifest",
                base=plan_path.parent,
            )
        prepared_superseded.append(
            {
                "upload_id": upload_id,
                "disposition": disposition,
                "reason": reason,
                "legacy_package_summary": str(summary_path),
                "legacy_package_summary_sha256": file_sha256(summary_path),
                "legacy_output_root": str(summary.get("output_root", "")),
                "legacy_target_file_count": int(
                    summary.get("target_file_count", 0)
                ),
                "preserved_source_manifest": (
                    str(preserved_manifest_path)
                    if preserved_manifest_path is not None
                    else ""
                ),
                "preserved_source_manifest_sha256": (
                    file_sha256(preserved_manifest_path)
                    if preserved_manifest_path is not None
                    else ""
                ),
                "media_deleted_or_modified": False,
                "active_review_or_upload_eligible": False,
            }
        )

    prepared: list[dict] = []
    seen_collections: set[str] = set()
    for raw in products:
        if not isinstance(raw, dict):
            raise ValueError("product declaration must be an object")
        if schema.endswith("-v2") and raw.get("material_product_eligible") is not True:
            raise ValueError("v2 material product lacks product approval")
        presentation_role = str(
            raw.get("presentation_role", "standalone_visual_catalog")
        ).strip()
        if presentation_role not in {
            "standalone_visual_catalog",
            "layer_component_material",
        }:
            raise ValueError("v2 material presentation_role differs")
        human_approval_status = str(
            raw.get("human_approval_status", "human_playback_required")
        ).strip()
        publication_state = str(
            raw.get("publication_state", "human_playback_required")
        ).strip()
        validate_publication_state(human_approval_status, publication_state)
        suggested_action = str(
            raw.get("suggested_action", "HOLD_FOR_HUMAN_PLAYBACK")
        ).strip()
        if not suggested_action:
            raise ValueError("v2 material suggested action differs")
        product_dimensions = raw.get("expected_dimensions", expected_dimensions)
        if (
            not isinstance(product_dimensions, dict)
            or set(product_dimensions) != {"width", "height"}
        ):
            raise ValueError("material product expected_dimensions differs")
        product_width = int(product_dimensions["width"])
        product_height = int(product_dimensions["height"])
        if product_width < 1 or product_height < 1:
            raise ValueError("material product expected dimensions are invalid")
        collection = str(raw.get("collection", ""))
        if not collection or collection in seen_collections:
            raise ValueError(f"duplicate or empty collection: {collection}")
        seen_collections.add(collection)
        manifest_path = validate_bound_file(
            raw.get("manifest"),
            label=f"{collection} manifest",
            base=plan_path.parent,
        )
        manifest = read_json(manifest_path)
        output = Path(str(manifest.get("output", ""))).resolve()
        expected_output = str(raw.get("output_sha256", "")).strip().upper()
        folded = str(output).casefold()
        if any(fragment in folded for fragment in FORBIDDEN):
            raise ValueError(f"forbidden material output: {output}")
        if (
            manifest.get("collection") != collection
            or manifest.get("technical_qa_status") != "passed"
            or manifest.get("publication_status") != "review_only"
            or manifest.get("release_eligible") is not False
            or manifest.get("expected_audio_state") != "digital_silence"
            or not output.is_file()
            or str(manifest.get("output_sha256", "")).upper()
            != expected_output
            or file_sha256(output) != expected_output
        ):
            raise ValueError(f"{collection} material contract differs")
        probe = probe_video(output, ffprobe)
        if (
            probe["width"] != product_width
            or probe["height"] != product_height
            or probe["frame_rate"] != "30/1"
            or probe["video_codec"] != "h264"
            or probe["audio_codec"]
            or probe["audio_channels"]
        ):
            raise ValueError(f"{collection} media contract differs: {probe}")
        prepared.append(
            {
                "collection": collection,
                "title": str(raw.get("title", "")).strip(),
                "family": str(raw.get("family", "")).strip().casefold(),
                "manifest_path": manifest_path,
                "manifest_sha256": file_sha256(manifest_path),
                "output": output,
                "output_sha256": expected_output,
                "presentation_role": presentation_role,
                "human_approval_status": human_approval_status,
                "publication_state": publication_state,
                "suggested_action": suggested_action,
                **probe,
            }
        )
    if any(
        not row["title"] or not re.fullmatch(r"ac\d+", row["family"])
        for row in prepared
    ):
        raise ValueError("product title/family contract differs")
    total_duration = sum(row["duration_seconds"] for row in prepared)
    review_batches = assign_review_batches(prepared)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    try:
        base_directories = [
            "00_UPLOAD_NOW",
            "01_REVIEW_STORY",
            "03_QUARANTINED_DO_NOT_UPLOAD",
            "manifests",
        ]
        if packaging_mode == "single_visual_canonical":
            base_directories.extend(
                (
                    "00_UPLOAD_NOW/material",
                    "04_ALREADY_UPLOADED/material",
                )
            )
        base_directories.extend(
            review_batch_directories(
                packaging_mode, editions, review_batches
            )
        )
        for relative in base_directories:
            (staging / relative).mkdir(parents=True, exist_ok=True)

        index_rows: list[dict] = []
        alias_rows: list[dict] = []
        for offset, product in enumerate(prepared):
            upload_id = f"U{start_id + offset:03d}"
            canonical_destination: Path | None = None
            canonical_relative = ""
            for edition in editions:
                filename = _packaged_filename(
                    upload_id,
                    product["title"],
                    product["family"],
                    edition,
                )
                if packaging_mode == "single_visual_canonical":
                    if product["publication_state"] == "already_uploaded":
                        queue = "04_ALREADY_UPLOADED"
                        batch = ""
                        relative = Path(queue) / "material"
                    elif product["publication_state"] == "ready_to_upload":
                        queue = "00_UPLOAD_NOW"
                        batch = ""
                        relative = Path(queue) / "material"
                    else:
                        queue = "02_REVIEW_MATERIAL"
                        batch = review_batches[product["collection"]]
                        relative = Path(queue) / batch
                else:
                    queue = "02_REVIEW_MATERIAL"
                    batch = review_batches[product["collection"]]
                    relative = Path(queue) / batch
                    relative /= edition
                relative /= filename
                destination = staging / relative
                if canonical_destination is None:
                    try:
                        os.link(product["output"], destination)
                        link_mode = "hardlink"
                    except OSError:
                        shutil.copy2(product["output"], destination)
                        link_mode = "copy_fallback"
                    canonical_destination = destination
                    canonical_relative = relative.as_posix()
                    is_canonical = True
                else:
                    os.link(canonical_destination, destination)
                    link_mode = "hardlink_alias_same_canonical_sha"
                    is_canonical = False
                actual = file_sha256(destination)
                if actual != product["output_sha256"]:
                    raise ValueError(f"packaged material hash differs: {destination}")
                row = {
                    "upload_id": upload_id,
                    "queue": queue,
                    "batch": batch,
                    "packaged_file": relative.as_posix(),
                    "packaged_absolute_path": str(output_root / relative),
                    "source_absolute_path": str(product["output"]),
                    "link_mode": link_mode,
                    "sha256": actual,
                    "canonical_sha256": actual,
                    "canonical_packaged_file": canonical_relative,
                    "is_canonical_exact_hash": is_canonical,
                    "physical_duplicate": False,
                    "duration_seconds": product["duration_seconds"],
                    "width": product["width"],
                    "height": product["height"],
                    "frame_rate": product["frame_rate"],
                    "video_codec": product["video_codec"],
                    "audio_codec": product["audio_codec"],
                    "audio_sample_rate": product["audio_sample_rate"],
                    "audio_channels": product["audio_channels"],
                    "family": product["family"],
                    "route": "",
                    "presentation_role": product["presentation_role"],
                    "edition": edition,
                    "subtitle_track": (
                        "visual-only; no audio; no language edition"
                        if edition == MATERIAL_EDITION
                        else (
                            "visual-only; no audio; no burned-in subtitles; "
                            f"legacy {edition} target alias"
                        )
                    ),
                    "automated_qa_status": (
                        "passed_visual_only_native"
                        f"{product['width']}x{product['height']}"
                    ),
                    "human_approval_status": product["human_approval_status"],
                    "publication_state": product["publication_state"],
                    "suggested_action": product["suggested_action"],
                    "target_bv": (
                        "owner-uploaded material; exact BV id pending ledger"
                        if product["publication_state"] == "already_uploaded"
                        else _target(
                            edition, product["width"], product["height"]
                        )
                    ),
                    "suggested_part_name": _part_name(
                        product["title"], product["family"], edition
                    ),
                    "source_manifest": str(product["manifest_path"]),
                    "source_manifest_sha256": product["manifest_sha256"],
                }
                index_rows.append(row)
                if not is_canonical:
                    alias_rows.append(
                        {
                            "upload_id": upload_id,
                            "family": product["family"],
                            "alias_edition": edition,
                            "alias_packaged_file": relative.as_posix(),
                            "sha256": actual,
                            "canonical_packaged_file": canonical_relative,
                            "physical_duplicate": False,
                            "target_bv": _target(
                                edition, product["width"], product["height"]
                            ),
                            "reason": (
                                "legal cross-target exact-hash alias; separate "
                                "hardlink name, same canonical physical data"
                            ),
                        }
                    )

        manifests = staging / "manifests"
        _write_csv(manifests / "UPLOAD_INDEX.csv", INDEX_FIELDS, index_rows)
        if alias_rows:
            _write_csv(
                manifests / "ALIASES.csv",
                (
                    "upload_id",
                    "family",
                    "alias_edition",
                    "alias_packaged_file",
                    "sha256",
                    "canonical_packaged_file",
                    "physical_duplicate",
                    "target_bv",
                    "reason",
                ),
                alias_rows,
            )
        shutil.copy2(plan_path, manifests / "SOURCE_INCREMENTAL_PLAN.json")
        shutil.copy2(guide_path, manifests / source_guide_copy_name)
        if prepared_superseded:
            write_json(
                manifests / "SUPERSEDED_PACKAGES.json",
                {
                    "schema": "magireco-superseded-material-packages-v1",
                    "items": prepared_superseded,
                    "source_media_deleted_or_modified": False,
                },
            )

        if packaging_mode == "single_visual_canonical":
            table = [
                "| U号 | 单一视觉文件 | 建议动作 |",
                "| --- | --- | --- |",
            ]
        else:
            table = [
                "| U号 | none 文件 | JA 文件 | ZH 文件 | 建议动作 |",
                "| --- | --- | --- | --- | --- |",
            ]
        for product_index, product in enumerate(prepared):
            upload_id = f"U{start_id + product_index:03d}"
            names = {
                row["edition"]: Path(row["packaged_file"]).name
                for row in index_rows
                if row["upload_id"] == upload_id
            }
            if packaging_mode == "single_visual_canonical":
                product_row = next(
                    row for row in index_rows if row["upload_id"] == upload_id
                )
                table.append(
                    f"| {upload_id} | `{names[MATERIAL_EDITION]}` | "
                    f"{product_row['publication_state']} / "
                    f"{product_row['suggested_action']} |"
                )
            else:
                table.append(
                    f"| {upload_id} | `{names['none']}` | `{names['ja']}` | "
                    f"`{names['zh']}` | 完整播放后按 exact hash 批准 |"
                )
        packaging_description = (
            "每个作品只有一个 `material` 文件；纯视觉素材没有语言版本，"
            "不得生成 none/JA/ZH 别名。"
            if packaging_mode == "single_visual_canonical"
            else (
                "本计划显式启用了历史兼容模式：none/JA/ZH 是三个目标轨的"
                "同哈希 hardlink。新检查点禁止使用此模式。"
            )
        )
        native_dimensions = sorted(
            {(row["width"], row["height"]) for row in prepared}
        )
        dimension_description = "、".join(
            f"{width}×{height}" for width, height in native_dimensions
        )
        review_count = sum(
            row["publication_state"] == "human_playback_required"
            for row in prepared
        )
        upload_count = sum(
            row["publication_state"] == "ready_to_upload" for row in prepared
        )
        uploaded_count = sum(
            row["publication_state"] == "already_uploaded" for row in prepared
        )
        (manifests / "START_HERE_UPLOAD_GUIDE.md").write_text(
            "\n".join(
                [
                    f"# {checkpoint_label} 增量人工审查与上传指南",
                    "",
                    f"本批状态：立即可上传 {upload_count}，待人工播放 {review_count}，"
                    f"已上传留档 {uploaded_count}。纯素材没有 none/JA/ZH 语言轨。",
                    "",
                    "先完整播放：",
                    f"`{output_root}\\02_REVIEW_MATERIAL\\batch_001`。",
                    "",
                    f"{len(prepared)} 个作品覆盖原生尺寸 {dimension_description}，"
                    "均为 30fps、H.264、"
                    "无音轨、无"
                    "烧录字幕的视觉素材。" + packaging_description,
                    "",
                    *table,
                    "",
                    "建议分P名、目标 BV、自动 QA、人工状态和逐项动作详见"
                    "`UPLOAD_INDEX.csv`；已上传素材不重复上传。",
                    "",
                    "P16/ac6003、P17/ac6004、P18/ac6005、superseded、"
                    "未闭合 child-local 项均未进入媒体目录。",
                    (
                        "旧错误三语素材包装详见 `SUPERSEDED_PACKAGES.json`；"
                        "这里只废止重复语言入口，不废弃任何素材内容。"
                        if prepared_superseded
                        else ""
                    ),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (manifests / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            f"# {checkpoint_label} 素材人工播放检查表\n\n"
            "- [ ] 从头到尾完整播放，无截断、异常黑帧或卡死\n"
            "- [ ] 命名画面顺序合理，重复视觉已去重但别名仍在 manifest\n"
            "- [ ] 全程静音，无意外对白、SE 或 BGM\n"
            f"- [ ] 原生尺寸为 {dimension_description}、30fps，无 upscale\n"
            "- [ ] 作品是玩法／素材合集，不冒充 clean story\n"
            + (
                "- [ ] 只有一个 material 文件，没有 none/JA/ZH 语言别名\n"
                if packaging_mode == "single_visual_canonical"
                else "- [ ] 历史 none/JA/ZH 三入口为同 inode 别名\n"
            )
            + "- [ ] 按 `UPLOAD_INDEX.csv` 中 exact SHA-256 记录批准或失败\n",
            encoding="utf-8",
        )
        (manifests / "EXCLUSIONS.md").write_text(
            f"# {checkpoint_label} 明确排除项\n\n"
            "- P16/ac6003、P17/ac6004、P18/ac6005：继续隔离。\n"
            "- 所有 superseded、quarantine、旧错误或已投稿 exact hash。\n"
            + (
                "- `SUPERSEDED_PACKAGES.json` 中的旧三语素材包装；组件内容仍保留。\n"
                if prepared_superseded
                else ""
            )
            + "- 未闭合 child-local Z2D 音频／字幕时序项目。\n"
            + "- 互斥路线机械串联，以及任何 upscale。\n"
            + "".join(f"- {value.strip()}\n" for value in specific_exclusions),
            encoding="utf-8",
        )
        (
            staging
            / "03_QUARANTINED_DO_NOT_UPLOAD"
            / "README_ONLY_MANIFESTS.md"
        ).write_text(
            "# 隔离清单区\n\n本目录故意不放 MP4；详见 "
            "`..\\manifests\\EXCLUSIONS.md`。\n",
            encoding="utf-8",
        )
        summary = {
            "schema": (
                "magireco-incremental-material-review-package-v2"
                if schema.endswith("-v2")
                else "magireco-incremental-material-review-package-v1"
            ),
            "status": (
                "HUMAN_PLAYBACK_REQUIRED"
                if review_count
                else "OWNER_STATUS_RECORDED"
            ),
            "checkpoint_id": str(plan.get("checkpoint_id", "")),
            "packaging_mode": packaging_mode,
            "output_root": str(output_root),
            "product_count": len(prepared),
            "target_file_count": len(index_rows),
            "unique_canonical_sha256_count": len(prepared),
            "legal_cross_target_alias_count": len(alias_rows),
            "language_edition_count": (
                len(index_rows)
                if packaging_mode == "legacy_three_target_aliases"
                else 0
            ),
            "visual_review_file_count": (
                len(index_rows)
                if packaging_mode == "single_visual_canonical"
                else 0
            ),
            "superseded_package_count": len(prepared_superseded),
            "withdrawn_product_count": sum(
                row["disposition"] == "withdrawn_nonstandalone_overlay"
                for row in prepared_superseded
            ),
            "upload_now_file_count": upload_count,
            "already_uploaded_file_count": uploaded_count,
            "review_material_batch_count": len(set(review_batches.values())),
            "native_dimensions": [
                {"width": width, "height": height}
                for width, height in native_dimensions
            ],
            "unique_duration_seconds": round(total_duration, 6),
            "quarantine_media_file_count": 0,
            "claim_boundary": (
                "Automatic QA and owner state are recorded per exact hash. "
                "No language aliases are created for visual-only material."
            ),
        }
        write_json(manifests / "PACKAGE_SUMMARY.json", summary)

        hash_lines = []
        for path in sorted(
            (value for value in staging.rglob("*") if value.is_file()),
            key=lambda value: value.relative_to(staging).as_posix().casefold(),
        ):
            if path.name == "SHA256SUMS.txt":
                continue
            hash_lines.append(
                f"{file_sha256(path)}  {path.relative_to(staging).as_posix()}"
            )
        (manifests / "SHA256SUMS.txt").write_text(
            "\n".join(hash_lines) + "\n",
            encoding="utf-8",
        )

        media = list(staging.rglob("*.mp4"))
        if len(media) != len(index_rows):
            raise ValueError("packaged media count differs")
        for product_index in range(len(prepared)):
            upload_id = f"U{start_id + product_index:03d}"
            rows = [row for row in index_rows if row["upload_id"] == upload_id]
            paths = [staging / row["packaged_file"] for row in rows]
            if len(paths) != len(editions):
                raise ValueError(f"{upload_id} packaged file count differs")
            if packaging_mode == "legacy_three_target_aliases" and not all(
                os.path.samefile(paths[0], path) for path in paths[1:]
            ):
                raise ValueError(f"{upload_id} edition aliases are not hardlinks")
        if list(
            (staging / "03_QUARANTINED_DO_NOT_UPLOAD").rglob("*.mp4")
        ):
            raise ValueError("quarantine directory contains media")
        staging.replace(output_root)
        return output_root
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    destination = build(
        plan_path=args.plan,
        output_root=args.output_root,
        ffprobe=args.ffprobe,
    )
    print(
        json.dumps(
            read_json(destination / "manifests" / "PACKAGE_SUMMARY.json"),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
