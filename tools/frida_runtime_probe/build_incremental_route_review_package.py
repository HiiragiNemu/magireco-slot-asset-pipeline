#!/usr/bin/env python3
"""Build one bounded hardlink review package for independent no-BGM routes."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

try:
    from .build_incremental_material_review_package import (
        file_sha256,
        probe_video,
        read_json,
        validate_bound_file,
        write_json,
    )
except ImportError:  # direct script execution
    from build_incremental_material_review_package import (  # type: ignore
        file_sha256,
        probe_video,
        read_json,
        validate_bound_file,
        write_json,
    )


EDITIONS = ("none", "ja", "zh")
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
    "edition",
    "subtitle_track",
    "automated_qa_status",
    "human_approval_status",
    "suggested_action",
    "target_bv",
    "suggested_part_name",
    "source_manifest",
    "source_manifest_sha256",
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _guide_by_path(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = value.get("items")
    if not isinstance(rows, list):
        raise ValueError("source upload guide lacks items")
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("source upload guide row is malformed")
        path = (
            Path(str(row.get("absolute_folder", "")))
            / str(row.get("exact_filename", ""))
        ).resolve()
        key = str(path).casefold()
        if key in output:
            raise ValueError(f"duplicate upload-guide path: {path}")
        output[key] = row
    return output


def _part_name(title: str, family: str, edition: str) -> str:
    value = f"{title} {family}"
    if edition == "ja":
        return value + "__ja"
    if edition == "zh":
        return value + " 中文版"
    return value


def _safe_fragment(value: str, *, label: str) -> str:
    value = value.strip()
    if (
        not value
        or value in {".", ".."}
        or any(char in value for char in '<>:"/\\|?*')
        or value.endswith((" ", "."))
    ):
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def build(*, plan_path: Path, output_root: Path, ffprobe: str) -> Path:
    plan_path = plan_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite route review root: {output_root}")
    plan = read_json(plan_path)
    if plan.get("schema") != "magireco-incremental-route-review-plan-v1":
        raise ValueError("incremental route review plan schema differs")
    guide_path = validate_bound_file(
        plan.get("source_upload_guide"),
        label="source upload guide",
        base=plan_path.parent,
    )
    batch_path = validate_bound_file(
        plan.get("source_batch_manifest"),
        label="source route batch manifest",
        base=plan_path.parent,
    )
    guide = read_json(guide_path)
    guide_paths = _guide_by_path(guide)
    batch = read_json(batch_path)
    if (
        batch.get("schema")
        != "magireco-ac4902-selector-entry-route-batch-v1"
        or batch.get("status")
        != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or batch.get("family") != "ac4902"
        or batch.get("audio_profile") != "no_bgm"
        or batch.get("bgm_policy") != "intentionally_excluded"
        or batch.get("showcase") is not None
        or batch.get("human_playback_approved") is not False
        or batch.get("publication_approved") is not False
    ):
        raise ValueError("source route batch contract differs")
    raw_routes = batch.get("routes")
    if not isinstance(raw_routes, list):
        raise ValueError("source route batch lacks routes")
    routes_by_id = {
        str(row.get("product_id")): row
        for row in raw_routes
        if isinstance(row, dict)
    }
    specs = plan.get("routes")
    if not isinstance(specs, list) or not specs:
        raise ValueError("incremental route review plan has no routes")
    if len(specs) > 10:
        raise ValueError("incremental route review batch exceeds ten products")
    start_id = int(plan.get("start_upload_id", 0))
    if start_id < 1:
        raise ValueError("start_upload_id must be positive")
    expected = plan.get("expected_dimensions")
    if (
        not isinstance(expected, dict)
        or set(expected) != {"width", "height"}
        or int(expected["width"]) != 416
        or int(expected["height"]) != 232
    ):
        raise ValueError("incremental route expected dimensions differ")
    batch_root = batch_path.parent
    prepared: list[dict[str, Any]] = []
    seen: set[str] = set()
    for spec in specs:
        if not isinstance(spec, dict):
            raise ValueError("route review spec is malformed")
        product_id = str(spec.get("product_id", ""))
        title = _safe_fragment(str(spec.get("title", "")), label="route title")
        filename_title = _safe_fragment(
            str(spec.get("filename_title", "")),
            label="route filename title",
        )
        route_suffix = _safe_fragment(
            str(spec.get("route_suffix", "")),
            label="route suffix",
        )
        route = routes_by_id.get(product_id)
        if (
            route is None
            or product_id in seen
            or not re.fullmatch(r"ac4902__row\d{3}_\d{3}_\d{3}", product_id)
        ):
            raise ValueError(f"route review identity differs: {product_id}")
        seen.add(product_id)
        if (
            route.get("schema") != "magireco-ac4902-selector-entry-route-v1"
            or route.get("status")
            != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
            or route.get("product_scope")
            != "independent_dirinfo_selector_entry_route"
            or route.get("composition_claim")
            != "independent_native_dirinfo_routes_no_showcase"
            or route.get("single_native_session_claimed") is not True
            or route.get("human_playback_approved") is not False
            or route.get("publication_approved") is not False
        ):
            raise ValueError(f"route review contract differs: {product_id}")
        media = route.get("media")
        if not isinstance(media, dict):
            raise ValueError(f"route media differs: {product_id}")
        editions: dict[str, dict[str, Any]] = {}
        for edition in EDITIONS:
            artifact = media.get(edition)
            if not isinstance(artifact, dict):
                raise ValueError(f"route lacks {edition}: {product_id}")
            source = Path(str(artifact.get("path", "")))
            if not source.is_absolute():
                source = batch_root / source
            source = source.resolve()
            sha256 = str(artifact.get("sha256", "")).upper()
            folded = str(source).casefold()
            if any(fragment in folded for fragment in FORBIDDEN):
                raise ValueError(f"forbidden route output: {source}")
            if (
                not source.is_file()
                or not re.fullmatch(r"[0-9A-F]{64}", sha256)
                or file_sha256(source) != sha256
            ):
                raise ValueError(f"route artifact binding differs: {source}")
            guide_row = guide_paths.get(str(source).casefold())
            if (
                not guide_row
                or str(guide_row.get("sha256", "")).upper() != sha256
                or guide_row.get("state") != "human_playback_required"
                or guide_row.get("publication_instruction") != "DO NOT UPLOAD YET"
            ):
                raise ValueError(f"route upload-guide state differs: {source}")
            probe = probe_video(source, ffprobe)
            if (
                probe["width"] != 416
                or probe["height"] != 232
                or probe["frame_rate"] != "30/1"
                or probe["video_codec"] != "h264"
                or probe["audio_codec"] != "aac"
                or probe["audio_sample_rate"] != "48000"
                or probe["audio_channels"] != 2
            ):
                raise ValueError(f"route media contract differs: {source}")
            editions[edition] = {
                "source": source,
                "sha256": sha256,
                "guide": guide_row,
                **probe,
            }
        durations = {round(row["duration_seconds"], 3) for row in editions.values()}
        if len(durations) != 1:
            raise ValueError(f"route edition durations differ: {product_id}")
        prepared.append(
            {
                "product_id": product_id,
                "title": title,
                "filename_title": filename_title,
                "route_suffix": route_suffix,
                "route": route,
                "editions": editions,
                "duration_seconds": editions["none"]["duration_seconds"],
            }
        )
    if sum(row["duration_seconds"] for row in prepared) > 1800:
        raise ValueError("incremental route review batch exceeds thirty minutes")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    try:
        for relative in (
            "00_UPLOAD_NOW/none",
            "00_UPLOAD_NOW/ja",
            "00_UPLOAD_NOW/zh",
            "01_REVIEW_STORY/batch_001/none",
            "01_REVIEW_STORY/batch_001/ja",
            "01_REVIEW_STORY/batch_001/zh",
            "02_REVIEW_MATERIAL",
            "03_QUARANTINED_DO_NOT_UPLOAD",
            "manifests",
        ):
            (staging / relative).mkdir(parents=True, exist_ok=True)
        index_rows: list[dict[str, Any]] = []
        for offset, product in enumerate(prepared):
            upload_id = f"U{start_id + offset:03d}"
            for edition in EDITIONS:
                media = product["editions"][edition]
                filename = (
                    f"{upload_id}_{product['filename_title']}_ac4902_"
                    f"{product['route_suffix']}__{edition}.mp4"
                )
                relative = (
                    Path("01_REVIEW_STORY")
                    / "batch_001"
                    / edition
                    / filename
                )
                destination = staging / relative
                try:
                    os.link(media["source"], destination)
                    link_mode = "hardlink"
                except OSError:
                    shutil.copy2(media["source"], destination)
                    link_mode = "copy_fallback"
                if file_sha256(destination) != media["sha256"]:
                    raise ValueError(f"packaged route hash differs: {destination}")
                guide_row = media["guide"]
                index_rows.append(
                    {
                        "upload_id": upload_id,
                        "queue": "01_REVIEW_STORY",
                        "batch": "batch_001",
                        "packaged_file": relative.as_posix(),
                        "packaged_absolute_path": str(output_root / relative),
                        "source_absolute_path": str(media["source"]),
                        "link_mode": link_mode,
                        "sha256": media["sha256"],
                        "canonical_sha256": media["sha256"],
                        "canonical_packaged_file": relative.as_posix(),
                        "is_canonical_exact_hash": True,
                        "physical_duplicate": False,
                        "duration_seconds": media["duration_seconds"],
                        "width": media["width"],
                        "height": media["height"],
                        "frame_rate": media["frame_rate"],
                        "video_codec": media["video_codec"],
                        "audio_codec": media["audio_codec"],
                        "audio_sample_rate": media["audio_sample_rate"],
                        "audio_channels": media["audio_channels"],
                        "family": "ac4902",
                        "route": product["product_id"],
                        "edition": edition,
                        "subtitle_track": guide_row["subtitle_track"],
                        "automated_qa_status": guide_row["automated_qa_status"],
                        "human_approval_status": guide_row["human_approval_status"],
                        "suggested_action": "hold_for_owner_playback",
                        "target_bv": guide_row["target_bv"],
                        "suggested_part_name": _part_name(
                            product["title"], "ac4902", edition
                        ),
                        "source_manifest": str(batch_path),
                        "source_manifest_sha256": file_sha256(batch_path),
                    }
                )
        manifests = staging / "manifests"
        _write_csv(manifests / "UPLOAD_INDEX.csv", index_rows)
        with (manifests / "ALIASES.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "canonical_sha256",
                    "canonical_packaged_file",
                    "alias_packaged_file",
                    "alias_edition",
                    "physical_duplicate",
                ),
            )
            writer.writeheader()
        shutil.copy2(guide_path, manifests / "SOURCE_GLOBAL_UPLOAD_GUIDE.json")
        write_json(
            manifests / "PACKAGE_MANIFEST.json",
            {
                "schema": "magireco-incremental-route-review-package-v1",
                "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                "checkpoint_id": plan["checkpoint_id"],
                "product_count": len(prepared),
                "media_file_count": len(index_rows),
                "total_unique_route_duration_seconds": round(
                    sum(row["duration_seconds"] for row in prepared), 6
                ),
                "source_batch_manifest": {
                    "path": str(batch_path),
                    "sha256": file_sha256(batch_path),
                },
                "source_upload_guide": {
                    "path": str(guide_path),
                    "sha256": file_sha256(guide_path),
                },
                "upload_now_file_count": 0,
                "quarantine_media_file_count": 0,
                "human_playback_approved": False,
                "publication_approved": False,
                "codex_upload_performed": False,
            },
        )
        (manifests / "START_HERE_UPLOAD_GUIDE.md").write_text(
            "# 本批 ac4902 独立路线人工审查\n\n"
            f"- 共 {len(prepared)} 条独立原生路线、{len(index_rows)} 个 "
            "none/JA/ZH 文件。\n"
            "- 当前全部只可人工播放，不可投稿。\n"
            "- 请逐路线对照三轨，重点检查入口动作音效、对白开口、字幕与"
            "结尾边界；路线互斥，不要串成单次自然流程。\n"
            "- 人工通过后，只按 `UPLOAD_INDEX.csv` 的目标 BV、建议分P名与"
            "精确 SHA-256 操作。\n",
            encoding="utf-8",
        )
        (manifests / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            "# 人工审查清单\n\n"
            "- [ ] 入口画面、入口动作音效从 0 开始且无裁切\n"
            "- [ ] 角色开口与对白一致\n"
            "- [ ] JA/ZH 字幕出现和消失时点一致\n"
            "- [ ] ZH 不把未获证据的 kuro 强行标成黑羽、黑或黑江\n"
            "- [ ] 结尾无截断、无互斥路线机械串联\n"
            "- [ ] 只批准实际播放过的精确文件与 SHA-256\n",
            encoding="utf-8",
        )
        (manifests / "EXCLUSIONS.md").write_text(
            "# 明确排除\n\n"
            "- P16/ac6003、P17/ac6004、P18/ac6005 全 family 隔离。\n"
            "- superseded、quarantine、已投稿精确哈希均不在本包。\n"
            "- 9 条精确 audience 别名行不重复渲染。\n"
            "- 不生成跨互斥路线 showcase。\n",
            encoding="utf-8",
        )
        media_files = list(staging.rglob("*.mp4"))
        if (
            len(media_files) != len(index_rows)
            or list((staging / "00_UPLOAD_NOW").rglob("*.mp4"))
            or list(
                (staging / "03_QUARANTINED_DO_NOT_UPLOAD").rglob("*.mp4")
            )
        ):
            raise ValueError("packaged route media isolation differs")
        hashes: list[str] = []
        for path in sorted(
            item for item in staging.rglob("*") if item.is_file()
        ):
            relative = path.relative_to(staging).as_posix()
            hashes.append(f"{file_sha256(path)}  {relative}")
        (manifests / "SHA256SUMS.txt").write_text(
            "\n".join(hashes) + "\n",
            encoding="utf-8",
        )
        staging.replace(output_root)
        return output_root
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination = build(
        plan_path=args.plan,
        output_root=args.output_root,
        ffprobe=args.ffprobe,
    )
    print(json.dumps({"destination": str(destination)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
