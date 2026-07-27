#!/usr/bin/env python3
"""Build a bounded hardlink review package for no-BGM story editions."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

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


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _guide_item_by_path(guide: dict) -> dict[str, dict]:
    items = guide.get("items")
    if not isinstance(items, list):
        raise ValueError("source upload guide lacks items")
    result: dict[str, dict] = {}
    for row in items:
        if not isinstance(row, dict):
            raise ValueError("source upload guide row is malformed")
        path = (
            Path(str(row.get("absolute_folder", "")))
            / str(row.get("exact_filename", ""))
        ).resolve()
        key = str(path).casefold()
        if key in result:
            raise ValueError(f"duplicate upload-guide path: {path}")
        result[key] = row
    return result


def _part_name(title: str, family: str, edition: str) -> str:
    value = f"{title} {family}"
    if edition == "ja":
        return value + "__ja"
    if edition == "zh":
        return value + " 中文版"
    return value


def build(*, plan_path: Path, output_root: Path, ffprobe: str) -> Path:
    plan_path = plan_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite review root: {output_root}")
    plan = read_json(plan_path)
    if plan.get("schema") != "magireco-incremental-story-review-plan-v1":
        raise ValueError("incremental story review plan schema differs")
    guide_path = validate_bound_file(
        plan.get("source_upload_guide"),
        label="source upload guide",
        base=plan_path.parent,
    )
    guide = read_json(guide_path)
    guide_by_path = _guide_item_by_path(guide)
    products = plan.get("products")
    if not isinstance(products, list) or not products:
        raise ValueError("incremental story review plan has no products")
    start_id = int(plan.get("start_upload_id", 0))
    if start_id < 1:
        raise ValueError("start_upload_id must be positive")
    expected_dimensions = plan.get(
        "expected_dimensions", {"width": 512, "height": 288}
    )
    if (
        not isinstance(expected_dimensions, dict)
        or set(expected_dimensions) != {"width", "height"}
        or int(expected_dimensions["width"]) <= 0
        or int(expected_dimensions["height"]) <= 0
    ):
        raise ValueError("incremental story expected dimensions differ")
    expected_width = int(expected_dimensions["width"])
    expected_height = int(expected_dimensions["height"])
    no_dialogue_aliases = plan.get("no_dialogue_aliases") is True
    review_queue = str(
        plan.get("review_queue", "01_REVIEW_STORY")
    ).strip()
    if review_queue not in {"01_REVIEW_STORY", "02_REVIEW_MATERIAL"}:
        raise ValueError("incremental story review queue differs")
    product_category = str(
        plan.get("product_category", "story")
    ).strip()
    if product_category not in {"story", "gameplay_announcement"}:
        raise ValueError("incremental story product category differs")
    if (
        product_category == "gameplay_announcement"
        and review_queue != "02_REVIEW_MATERIAL"
    ):
        raise ValueError("gameplay announcement review queue differs")
    checkpoint_label = str(plan.get("checkpoint_label", "")).strip() or "incremental"
    source_guide_copy_name = str(
        plan.get("source_guide_copy_name", "SOURCE_GLOBAL_UPLOAD_GUIDE.json")
    ).strip()
    if (
        not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", source_guide_copy_name)
        or "/" in source_guide_copy_name
        or "\\" in source_guide_copy_name
    ):
        raise ValueError("incremental story guide copy name differs")

    prepared: list[dict] = []
    seen_families: set[str] = set()
    for raw in products:
        if not isinstance(raw, dict):
            raise ValueError("story product declaration must be an object")
        family = str(raw.get("family", "")).casefold()
        title = str(raw.get("title", "")).strip()
        filename_title = str(raw.get("filename_title", "")).strip()
        bounded_product_scope = str(
            raw.get("bounded_product_scope", "")
        ).strip()
        if (
            not re.fullmatch(r"ac\d+_\d+", family)
            or family in seen_families
            or not title
            or not filename_title
        ):
            raise ValueError(f"story product identity differs: {family}")
        seen_families.add(family)
        manifest_path = validate_bound_file(
            raw.get("manifest"),
            label=f"{family} family editions manifest",
            base=plan_path.parent,
        )
        manifest_sha256 = file_sha256(manifest_path)
        manifest = read_json(manifest_path)
        if (
            manifest.get("schema")
            != "magireco-no-bgm-story-family-editions-v1"
            or manifest.get("status") != "AUTOMATED_QA_PASSED"
            or manifest.get("family") != family
            or manifest.get("ordered_events") != [family]
            or manifest.get("audio_profile") != "no_bgm"
            or manifest.get("bgm_policy") != "intentionally_excluded"
            or manifest.get("human_review_status") != "pending"
            or manifest.get("publishable") is not False
        ):
            raise ValueError(f"{family} story release contract differs")
        if no_dialogue_aliases and (
            manifest.get("dialogue_cue_count") != 0
            or set(manifest.get("verified_no_event_audio_events", []))
            != {family}
            or any(
                manifest.get("subtitle_profiles", {}).get(edition)
                != "no_dialogue_cross_target_alias"
                for edition in ("ja", "zh")
            )
        ):
            raise ValueError(f"{family} no-dialogue alias contract differs")
        if bounded_product_scope and (
            manifest.get("product_scope") != bounded_product_scope
            or manifest.get("natural_session_claimed") is not False
            or manifest.get("loop_scope", {}).get("policy")
            != "intro_then_exactly_one_complete_source_loop"
            or manifest.get("loop_scope", {}).get(
                "runtime_loop_count_claimed"
            )
            is not False
        ):
            raise ValueError(f"{family} bounded product contract differs")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict):
            raise ValueError(f"{family} story artifacts differ")
        editions: dict[str, dict] = {}
        for edition in EDITIONS:
            artifact = artifacts.get(f"video_{edition}")
            if not isinstance(artifact, dict):
                raise ValueError(f"{family} lacks {edition} video artifact")
            source = Path(str(artifact.get("path", "")))
            if not source.is_absolute():
                source = manifest_path.parent.parent / source
            source = source.resolve()
            expected_sha = str(artifact.get("sha256", "")).upper()
            folded = str(source).casefold()
            if any(fragment in folded for fragment in FORBIDDEN):
                raise ValueError(f"forbidden story output: {source}")
            if (
                not source.is_file()
                or not re.fullmatch(r"[0-9A-F]{64}", expected_sha)
                or file_sha256(source) != expected_sha
            ):
                raise ValueError(f"{family} {edition} artifact binding differs")
            guide_row = guide_by_path.get(str(source).casefold())
            if (
                not guide_row
                or str(guide_row.get("sha256", "")).upper() != expected_sha
                or guide_row.get("state") != "human_playback_required"
                or guide_row.get("publication_instruction")
                != "DO NOT UPLOAD YET"
            ):
                raise ValueError(f"{family} {edition} upload-guide state differs")
            probe = probe_video(source, ffprobe)
            if (
                probe["width"] != expected_width
                or probe["height"] != expected_height
                or probe["frame_rate"] != "30/1"
                or probe["video_codec"] != "h264"
                or probe["audio_codec"] != "aac"
                or probe["audio_sample_rate"] != "48000"
                or probe["audio_channels"] != 2
            ):
                raise ValueError(
                    f"{family} {edition} media contract differs: {probe}"
                )
            editions[edition] = {
                "source": source,
                "sha256": expected_sha,
                "guide": guide_row,
                **probe,
            }
        durations = {round(row["duration_seconds"], 3) for row in editions.values()}
        if len(durations) != 1:
            raise ValueError(f"{family} edition durations differ")
        if no_dialogue_aliases and len(
            {row["sha256"] for row in editions.values()}
        ) != 1:
            raise ValueError(f"{family} no-dialogue edition hashes differ")
        prepared.append(
            {
                "family": family,
                "title": title,
                "filename_title": filename_title,
                "bounded_product_scope": bounded_product_scope,
                "manifest_path": manifest_path,
                "manifest_sha256": manifest_sha256,
                "editions": editions,
                "duration_seconds": editions["none"]["duration_seconds"],
            }
        )
    if len(prepared) > 10 or sum(
        row["duration_seconds"] for row in prepared
    ) > 1800:
        raise ValueError("incremental story review batch exceeds size limit")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    try:
        for relative in (
            "00_UPLOAD_NOW/none",
            "00_UPLOAD_NOW/ja",
            "00_UPLOAD_NOW/zh",
            "01_REVIEW_STORY",
            "02_REVIEW_MATERIAL",
            "03_QUARANTINED_DO_NOT_UPLOAD",
            "manifests",
        ):
            (staging / relative).mkdir(parents=True, exist_ok=True)
        for edition in EDITIONS:
            (staging / review_queue / "batch_001" / edition).mkdir(
                parents=True,
                exist_ok=True,
            )

        index_rows: list[dict] = []
        alias_rows: list[dict] = []
        canonical_by_product_sha: dict[tuple[str, str], tuple[Path, str]] = {}
        for offset, product in enumerate(prepared):
            upload_id = f"U{start_id + offset:03d}"
            for edition in EDITIONS:
                media = product["editions"][edition]
                filename = (
                    f"{upload_id}_{product['filename_title']}_{product['family']}"
                    f"__{edition}.mp4"
                )
                relative = (
                    Path(review_queue)
                    / "batch_001"
                    / edition
                    / filename
                )
                destination = staging / relative
                canonical_key = (product["family"], media["sha256"])
                canonical = canonical_by_product_sha.get(canonical_key)
                if canonical is None:
                    try:
                        os.link(media["source"], destination)
                        link_mode = "hardlink"
                    except OSError:
                        shutil.copy2(media["source"], destination)
                        link_mode = "copy_fallback"
                    canonical_relative = relative.as_posix()
                    canonical_by_product_sha[canonical_key] = (
                        destination,
                        canonical_relative,
                    )
                    is_canonical = True
                else:
                    os.link(canonical[0], destination)
                    link_mode = "hardlink_alias_same_canonical_sha"
                    canonical_relative = canonical[1]
                    is_canonical = False
                if file_sha256(destination) != media["sha256"]:
                    raise ValueError(f"packaged story hash differs: {destination}")
                guide_row = media["guide"]
                index_rows.append(
                    {
                        "upload_id": upload_id,
                        "queue": review_queue,
                        "batch": "batch_001",
                        "packaged_file": relative.as_posix(),
                        "packaged_absolute_path": str(output_root / relative),
                        "source_absolute_path": str(media["source"]),
                        "link_mode": link_mode,
                        "sha256": media["sha256"],
                        "canonical_sha256": media["sha256"],
                        "canonical_packaged_file": canonical_relative,
                        "is_canonical_exact_hash": is_canonical,
                        "physical_duplicate": False,
                        "duration_seconds": media["duration_seconds"],
                        "width": media["width"],
                        "height": media["height"],
                        "frame_rate": media["frame_rate"],
                        "video_codec": media["video_codec"],
                        "audio_codec": media["audio_codec"],
                        "audio_sample_rate": media["audio_sample_rate"],
                        "audio_channels": media["audio_channels"],
                        "family": product["family"],
                        "route": product["family"].split("_", 1)[1],
                        "edition": edition,
                        "subtitle_track": guide_row["subtitle_track"],
                        "automated_qa_status": guide_row["automated_qa_status"],
                        "human_approval_status": guide_row[
                            "human_approval_status"
                        ],
                        "suggested_action": "HOLD_FOR_HUMAN_PLAYBACK",
                        "target_bv": guide_row["target_bv"],
                        "suggested_part_name": _part_name(
                            product["title"], product["family"], edition
                        ),
                        "source_manifest": str(product["manifest_path"]),
                        "source_manifest_sha256": product["manifest_sha256"],
                    }
                )
                if not is_canonical:
                    alias_rows.append(
                        {
                            "upload_id": upload_id,
                            "family": product["family"],
                            "alias_edition": edition,
                            "alias_packaged_file": relative.as_posix(),
                            "sha256": media["sha256"],
                            "canonical_packaged_file": canonical_relative,
                            "physical_duplicate": False,
                            "target_bv": guide_row["target_bv"],
                            "reason": (
                                "legal cross-target exact-hash alias; separate "
                                "hardlink name, same canonical physical data"
                            ),
                        }
                    )

        manifests = staging / "manifests"
        _write_csv(manifests / "UPLOAD_INDEX.csv", INDEX_FIELDS, index_rows)
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

        table = [
            "| U号 | 作品 | none | JA | ZH | 状态 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for offset, product in enumerate(prepared):
            upload_id = f"U{start_id + offset:03d}"
            names = {
                row["edition"]: Path(row["packaged_file"]).name
                for row in index_rows
                if row["upload_id"] == upload_id
            }
            table.append(
                f"| {upload_id} | {product['title']} {product['family']} | "
                f"`{names['none']}` | `{names['ja']}` | `{names['zh']}` | "
                "完整播放后按 exact SHA-256 批准 |"
            )
        bounded_count = sum(
            bool(product["bounded_product_scope"]) for product in prepared
        )
        (manifests / "START_HERE_UPLOAD_GUIDE.md").write_text(
            "\n".join(
                [
                    f"# {checkpoint_label} 增量人工审查与上传指南",
                    "",
                    "本批没有立即可上传文件；`00_UPLOAD_NOW` 为空只表示这 "
                    f"{len(index_rows)} 个 exact MP4 尚未获得人工播放批准，"
                    "绝不表示 none 未生产。",
                    "",
                    "请先完整播放：",
                    f"`{output_root}\\{review_queue}\\batch_001`。",
                    "",
                    f"{len(prepared)} 个作品均为独立 event-exact 原生 "
                    f"{expected_width}×{expected_height} 单事件产品，每个都有 "
                    "none/JA/ZH；它们不宣称完整 natural family，也没有把"
                    "互斥路线机械串联。",
                    *(
                        [
                            "",
                            "本批属于玩法／告知动画，不是剧情；六条 sibling "
                            "DirInfo 路线必须分别审查，禁止合并成自然会话。",
                        ]
                        if product_category == "gameplay_announcement"
                        else []
                    ),
                    *(
                        [
                            "",
                            f"其中 {bounded_count} 个是有限资料型产品：仅含"
                            "精确开场与一遍完整源循环，不宣称自然运行时会话"
                            "或运行时循环次数。",
                        ]
                        if bounded_count
                        else []
                    ),
                    *(
                        [
                            "",
                            "本批三套证据目录均精确无事件音频或字幕命中；"
                            "none/JA/ZH 是面向不同目标 BV 的合法同哈希硬链接"
                            "别名，不生成空 SRT，也不伪造字幕或 SE。",
                        ]
                        if no_dialogue_aliases
                        else []
                    ),
                    "",
                    *table,
                    "",
                    "目标 BV、建议分P名、自动 QA、人工状态与来源 manifest "
                    "详见 `UPLOAD_INDEX.csv`。人工批准前一律 HOLD。",
                    "",
                    "P16/ac6003、P17/ac6004、P18/ac6005、superseded、"
                    "quarantine、未闭合 child-local 项均未进入媒体目录。",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        timing_check = (
            "- [ ] 三轨均无烧录字幕；AAC 仅为经证据批准的 48kHz stereo "
            "silence presentation，未伪造对白或 SE\n"
            if no_dialogue_aliases
            else "- [ ] 角色开口、对白、SE 与字幕时序自然\n"
            "- [ ] none 无烧录字幕；JA/ZH 字幕语言与目标轨一致\n"
        )
        (manifests / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            f"# {checkpoint_label} 剧情人工播放检查表\n\n"
            "- [ ] 每个版本从头到尾完整播放，无截断、异常黑帧或卡死\n"
            f"{timing_check}"
            f"- [ ] 原生 {expected_width}×{expected_height}、30fps、"
            "H.264/AAC 48kHz stereo，无 upscale\n"
            "- [ ] 单事件边界自然，但不把它误认作完整 family\n"
            + (
                "- [ ] 有限资料型产品仅核对开场与一遍完整源循环；"
                "不得把它误认作自然运行时停留时长\n"
                if bounded_count
                else ""
            )
            + "- [ ] 按 `UPLOAD_INDEX.csv` 的 exact SHA-256 记录批准或失败\n",
            encoding="utf-8",
        )
        (manifests / "EXCLUSIONS.md").write_text(
            f"# {checkpoint_label} 明确排除项\n\n"
            "- P16/ac6003、P17/ac6004、P18/ac6005：继续隔离。\n"
            "- 所有 superseded、quarantine、旧错误或已投稿 exact hash。\n"
            "- 未闭合 child-local Z2D 音频／字幕时序项目。\n"
            "- 互斥路线机械串联、完整 family 的无证据外推、任何 upscale。\n"
            f"- 本批仅含 {len(prepared)} 个独立 event-exact 单事件；"
            "其他 family 继续由总账"
            "分流，不在这里冒充完成。\n",
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
            "schema": "magireco-incremental-story-review-package-v1",
            "status": "HUMAN_PLAYBACK_REQUIRED",
            "checkpoint_id": str(plan.get("checkpoint_id", "")),
            "output_root": str(output_root),
            "product_count": len(prepared),
            "target_file_count": len(index_rows),
            "unique_canonical_sha256_count": len(
                {row["sha256"] for row in index_rows}
            ),
            "legal_cross_target_alias_count": len(alias_rows),
            "upload_now_file_count": 0,
            "review_story_batch_count": (
                1 if review_queue == "01_REVIEW_STORY" else 0
            ),
            "review_material_batch_count": (
                1 if review_queue == "02_REVIEW_MATERIAL" else 0
            ),
            "unique_duration_seconds": round(
                sum(row["duration_seconds"] for row in prepared), 6
            ),
            "quarantine_media_file_count": 0,
            "claim_boundary": (
                "Automatic QA passed; every exact hash remains non-publishable "
                "until project-owner playback approval."
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
            raise ValueError("packaged story media count differs")
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
