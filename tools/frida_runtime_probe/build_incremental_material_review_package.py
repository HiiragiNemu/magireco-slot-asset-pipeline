#!/usr/bin/env python3
"""Build a three-target hardlink review package for visual-only materials."""

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
    if edition == "ja":
        return base + "__ja"
    if edition == "zh":
        return base + " 中文版"
    return base


def _target(edition: str) -> str:
    return (
        "新建建议：MagiaReco Slot 原生416玩法／素材合集 "
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


def build(*, plan_path: Path, output_root: Path, ffprobe: str) -> Path:
    plan_path = plan_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite review root: {output_root}")
    plan = read_json(plan_path)
    if plan.get("schema") != "magireco-incremental-material-review-plan-v1":
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

    prepared: list[dict] = []
    seen_collections: set[str] = set()
    for raw in products:
        if not isinstance(raw, dict):
            raise ValueError("product declaration must be an object")
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
            probe["width"] != 416
            or probe["height"] != 232
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
                **probe,
            }
        )
    if any(
        not row["title"] or not re.fullmatch(r"ac\d+", row["family"])
        for row in prepared
    ):
        raise ValueError("product title/family contract differs")
    total_duration = sum(row["duration_seconds"] for row in prepared)
    if len(prepared) > 10 or total_duration > 1800:
        raise ValueError("incremental review batch exceeds size limit")

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
            "02_REVIEW_MATERIAL/batch_001/none",
            "02_REVIEW_MATERIAL/batch_001/ja",
            "02_REVIEW_MATERIAL/batch_001/zh",
            "03_QUARANTINED_DO_NOT_UPLOAD",
            "manifests",
        ):
            (staging / relative).mkdir(parents=True, exist_ok=True)

        index_rows: list[dict] = []
        alias_rows: list[dict] = []
        for offset, product in enumerate(prepared):
            upload_id = f"U{start_id + offset:03d}"
            canonical_destination: Path | None = None
            canonical_relative = ""
            for edition in EDITIONS:
                filename = (
                    f"{upload_id}_{product['title']}_{product['family']}"
                    f"__{edition}.mp4"
                )
                relative = (
                    Path("02_REVIEW_MATERIAL")
                    / "batch_001"
                    / edition
                    / filename
                )
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
                    "queue": "02_REVIEW_MATERIAL",
                    "batch": "batch_001",
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
                    "edition": edition,
                    "subtitle_track": (
                        "visual-only; no audio; no burned-in subtitles; "
                        f"legal {edition} target alias"
                    ),
                    "automated_qa_status": "passed_visual_only_native416",
                    "human_approval_status": "human_playback_required",
                    "suggested_action": "HOLD_FOR_HUMAN_PLAYBACK",
                    "target_bv": _target(edition),
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
                            "target_bv": _target(edition),
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
        shutil.copy2(guide_path, manifests / "SOURCE_GLOBAL_UPLOAD_GUIDE_V42.json")

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
            table.append(
                f"| {upload_id} | `{names['none']}` | `{names['ja']}` | "
                f"`{names['zh']}` | 完整播放后按 exact hash 批准 |"
            )
        (manifests / "START_HERE_UPLOAD_GUIDE.md").write_text(
            "\n".join(
                [
                    "# v42 增量人工审查与上传指南",
                    "",
                    "本批没有立即可上传文件；`00_UPLOAD_NOW` 为空是因为这些"
                    "新合集尚未获得 exact-file 人工播放批准，不代表 none 未生产。",
                    "",
                    "先完整播放：",
                    f"`{output_root}\\02_REVIEW_MATERIAL\\batch_001`。",
                    "",
                    "4 个作品均为原生 416×232、30fps、H.264、无音轨、无"
                    "烧录字幕的视觉素材。none/JA/ZH 是分别面向三个目标轨的"
                    "合法同哈希 hardlink；每个作品只占一份物理数据。",
                    "",
                    *table,
                    "",
                    "建议分P名、目标 BV、新增或暂缓、自动 QA 与人工状态详见"
                    "`UPLOAD_INDEX.csv`。当前建议动作统一为 HOLD，不得在未完整"
                    "播放前上传。",
                    "",
                    "P16/ac6003、P17/ac6004、P18/ac6005、superseded、"
                    "未闭合 child-local 项均未进入媒体目录。",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (manifests / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            "# v42 素材人工播放检查表\n\n"
            "- [ ] 从头到尾完整播放，无截断、异常黑帧或卡死\n"
            "- [ ] 命名画面顺序合理，重复视觉已去重但别名仍在 manifest\n"
            "- [ ] 全程静音，无意外对白、SE 或 BGM\n"
            "- [ ] 原生 416×232、30fps，无 upscale\n"
            "- [ ] 作品是玩法／素材合集，不冒充 clean story\n"
            "- [ ] none/JA/ZH 三入口为同 inode 合法别名\n"
            "- [ ] 按 `UPLOAD_INDEX.csv` 中 exact SHA-256 记录批准或失败\n",
            encoding="utf-8",
        )
        (manifests / "EXCLUSIONS.md").write_text(
            "# v42 明确排除项\n\n"
            "- P16/ac6003、P17/ac6004、P18/ac6005：继续隔离。\n"
            "- 所有 superseded、quarantine、旧错误或已投稿 exact hash。\n"
            "- 未闭合 child-local Z2D 音频／字幕时序项目。\n"
            "- 互斥路线机械串联，以及任何 upscale。\n"
            "- ac1103 的 256×144 `ac8040_shouri_EF` 系列：留待其他"
            "原生尺寸效果合集，本批不放大也不混入 416 合集。\n",
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
            "schema": "magireco-incremental-material-review-package-v1",
            "status": "HUMAN_PLAYBACK_REQUIRED",
            "checkpoint_id": str(plan.get("checkpoint_id", "")),
            "output_root": str(output_root),
            "product_count": len(prepared),
            "target_file_count": len(index_rows),
            "unique_canonical_sha256_count": len(prepared),
            "legal_cross_target_alias_count": len(alias_rows),
            "upload_now_file_count": 0,
            "review_material_batch_count": 1,
            "unique_duration_seconds": round(total_duration, 6),
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
            raise ValueError("packaged media count differs")
        for product_index in range(len(prepared)):
            upload_id = f"U{start_id + product_index:03d}"
            rows = [row for row in index_rows if row["upload_id"] == upload_id]
            paths = [staging / row["packaged_file"] for row in rows]
            if len(paths) != 3 or not all(
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
