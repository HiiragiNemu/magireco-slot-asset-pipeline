#!/usr/bin/env python3
"""Publish the corrected long-form review hub using NTFS hardlinks only."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable, Mapping


APPROVED_DIR = "00_APPROVED_CURRENT"
REVIEW_DIR = "01_TO_REVIEW"
LANGUAGE_LANES = {"zh": "ZH", "ja": "JP", "none": "NONE"}
TYPE_LANES = {
    "clean_story": "story",
    "story_route": "routes",
    "gameplay_effect": "gameplay_effect",
}
MATERIAL_TYPES = {"material", "component_archive"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    values = list(rows)
    fields: list[str] = []
    for row in values:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def as_bool(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes"}


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    return value[:150] or "未命名"


def material_item(row: Mapping[str, str]) -> bool:
    return row.get("content_type", "") in MATERIAL_TYPES


def classify(row: Mapping[str, str], audit: Mapping[str, str]) -> tuple[str, str]:
    action = audit.get("new_longform_action", "")
    approved = as_bool(row.get("owner_approved"))
    superseded = as_bool(row.get("superseded"))
    quarantine = row.get("quarantine_flags", "").strip()
    sound_bus_withdrawn = (
        row.get("sound_bus_audit_action", "")
        == "withdraw_from_strict_no_bgm_review_ready"
    )
    corrected_material_packaging = material_item(row) and (
        row.get("exclusion_reason", "") == "superseded_language_track_material_packaging"
    )

    if approved:
        if action == "WITHDRAW_FROM_LONGFORM_REVIEW":
            return "WITHDRAWN", "long-form authority withdrawn after owner playback"
        if sound_bus_withdrawn:
            return "WITHDRAWN", "strict no-BGM claim withdrawn by sound-bus evidence"
        if quarantine not in {"", "[]"}:
            return "WITHDRAWN", "quarantine remains active"
        if superseded and not corrected_material_packaging:
            return "WITHDRAWN", "superseded exact output"
        return "APPROVED", "exact owner playback approval remains current"

    if (
        row.get("review_disposition") == "REVIEW_READY"
        and action == "PRESERVE_CURRENT_METADATA_PENDING_AUDIT"
        and material_item(row)
        and not superseded
        and quarantine in {"", "[]"}
    ):
        return "TO_REVIEW", "language-neutral material awaiting owner playback"

    return "INDEX_ONLY", audit.get("reason", "not eligible under long-form policy")


def relative_media_path(row: Mapping[str, str], bucket: str, sequence: int) -> Path:
    family = safe_name(row.get("family", "unknown"))
    title = safe_name(row.get("title", "") or family)
    edition = row.get("edition", "").casefold()
    root = APPROVED_DIR if bucket == "APPROVED" else REVIEW_DIR
    if material_item(row):
        return Path("MATERIAL", safe_name(f"M{sequence:04d}_{title}_{family}.mp4"))
    prefix = "A" if bucket == "APPROVED" else "Q"
    language = LANGUAGE_LANES.get(edition)
    content = TYPE_LANES.get(row.get("content_type", ""))
    if not language or not content:
        raise ValueError(f"invalid audience classification for {row['inventory_item_id']}")
    filename = safe_name(f"{prefix}{sequence:04d}_{title}_{family}__{edition}.mp4")
    return Path(root, language, content, filename)


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"ffprobe failed for {path}: {error}")
    payload = json.loads(completed.stdout.decode("utf-8"))
    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None:
        raise ValueError(f"no video stream: {path}")
    duration = payload.get("format", {}).get("duration") or video.get("duration")
    return {
        "duration_sec": float(duration),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "frame_rate": video.get("r_frame_rate") or video.get("avg_frame_rate"),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_sample_rate": int(audio["sample_rate"])
        if audio and audio.get("sample_rate")
        else None,
        "audio_channels": int(audio["channels"])
        if audio and audio.get("channels")
        else None,
    }


def validate_probe(row: Mapping[str, str], actual: Mapping[str, Any]) -> None:
    item_id = row["inventory_item_id"]
    if f"{actual['width']}x{actual['height']}" != row.get("resolution"):
        raise ValueError(f"{item_id} resolution mismatch")
    if abs(float(actual["duration_sec"]) - float(row["duration_sec"])) > 0.08:
        raise ValueError(f"{item_id} duration mismatch")
    expected_rate = row.get("frame_rate")
    if expected_rate and actual.get("frame_rate") != expected_rate:
        raise ValueError(f"{item_id} frame-rate mismatch")


def build(
    *,
    source_index: Path,
    reassessment: Path,
    output_root: Path,
    release_id: str,
    ffprobe: str = "ffprobe",
    dry_run: bool = False,
) -> dict[str, Any]:
    rows = read_csv(source_index)
    audits = {row["inventory_item_id"]: row for row in read_csv(reassessment)}
    if len(rows) != len(audits) or any(row["inventory_item_id"] not in audits for row in rows):
        raise ValueError("source index and reassessment coverage differ")

    planned: list[dict[str, Any]] = []
    index_only: list[dict[str, Any]] = []
    sequence = {"APPROVED": 0, "TO_REVIEW": 0, "MATERIAL": 0}
    seen_sources: dict[str, str] = {}
    ordered = sorted(
        rows,
        key=lambda row: (
            0 if as_bool(row.get("owner_approved")) else 1,
            row.get("family", ""),
            row.get("edition", ""),
            row["inventory_item_id"],
        ),
    )
    for row in ordered:
        audit = audits[row["inventory_item_id"]]
        bucket, reason = classify(row, audit)
        record = dict(row)
        record.update(
            {
                "corrected_bucket": bucket,
                "corrected_reason": reason,
                "new_longform_action": audit.get("new_longform_action", ""),
                "new_longform_reason": audit.get("reason", ""),
                "corrected_review_absolute_path": "",
                "canonical_inventory_item_id": row["inventory_item_id"],
                "is_source_alias": False,
            }
        )
        if bucket not in {"APPROVED", "TO_REVIEW"}:
            index_only.append(record)
            continue

        source = Path(row["source_absolute_path"])
        if not source.is_file():
            raise FileNotFoundError(source)
        actual_probe = probe(source, ffprobe)
        validate_probe(row, actual_probe)
        source_key = os.path.normcase(str(source.resolve()))
        if source_key in seen_sources:
            record["canonical_inventory_item_id"] = seen_sources[source_key]
            record["is_source_alias"] = True
            record["corrected_reason"] += "; same source indexed without another link"
            index_only.append(record)
            continue

        counter = "MATERIAL" if material_item(row) else bucket
        sequence[counter] += 1
        relative = relative_media_path(row, bucket, sequence[counter])
        record["corrected_review_absolute_path"] = str(
            output_root / "releases" / release_id / relative
        )
        record.update({f"verified_{key}": value for key, value in actual_probe.items()})
        seen_sources[source_key] = row["inventory_item_id"]
        planned.append({"record": record, "relative": relative, "source": source})

    summary = {
        "schema": "magireco-corrected-longform-review-hub-verification-v1",
        "status": "DRY_RUN_PASS" if dry_run else "PASS",
        "release_id": release_id,
        "inventory_items": len(rows),
        "approved_current_files": sum(
            item["record"]["corrected_bucket"] == "APPROVED" for item in planned
        ),
        "to_review_files": sum(
            item["record"]["corrected_bucket"] == "TO_REVIEW" for item in planned
        ),
        "to_review_audience_files": sum(
            item["record"]["corrected_bucket"] == "TO_REVIEW"
            and not material_item(item["record"])
            for item in planned
        ),
        "pending_material_files": sum(
            item["record"]["corrected_bucket"] == "TO_REVIEW"
            and material_item(item["record"])
            for item in planned
        ),
        "material_files": sum(material_item(item["record"]) for item in planned),
        "approved_audience_files": sum(
            item["record"]["corrected_bucket"] == "APPROVED"
            and not material_item(item["record"])
            for item in planned
        ),
        "canonical_hardlinks": len(planned),
        "index_only_items": len(index_only),
        "source_media_moved": False,
        "source_media_deleted": False,
        "source_media_transcoded": False,
        "physical_copy_created": False,
        "hardlink_only": True,
        "source_index": str(source_index),
        "reassessment": str(reassessment),
    }
    if dry_run:
        return summary

    releases = output_root / "releases"
    release = releases / release_id
    staging = releases / f".{release_id}.staging"
    if release.exists() or staging.exists():
        raise FileExistsError(f"immutable release already exists: {release}")
    staging.mkdir(parents=True)
    for status_root in (APPROVED_DIR, REVIEW_DIR):
        for lane in LANGUAGE_LANES.values():
            for content in TYPE_LANES.values():
                (staging / status_root / lane / content).mkdir(parents=True, exist_ok=True)
    (staging / "MATERIAL").mkdir(parents=True, exist_ok=True)

    published: list[dict[str, Any]] = []
    for item in planned:
        target = staging / item["relative"]
        if item["source"].stat().st_dev != target.parent.stat().st_dev:
            raise ValueError(f"hardlink would cross volumes: {item['source']}")
        os.link(item["source"], target)
        if not os.path.samefile(item["source"], target):
            raise ValueError(f"published file is not a hardlink: {target}")
        item["record"]["corrected_review_absolute_path"] = str(release / item["relative"])
        published.append(item["record"])

    all_records = sorted(published + index_only, key=lambda row: row["inventory_item_id"])
    write_json(staging / "HUB_INDEX.json", {"summary": summary, "items": all_records})
    write_csv(staging / "HUB_INDEX.csv", all_records)
    inactive = [row for row in all_records if row["corrected_bucket"] not in {"APPROVED", "TO_REVIEW"}]
    write_json(staging / "WITHDRAWN_OR_INDEX_ONLY.json", inactive)
    write_csv(staging / "WITHDRAWN_OR_INDEX_ONLY.csv", inactive)
    write_json(staging / "VERIFICATION_RECORD.json", summary)
    (staging / "00_START_HERE.md").write_text(
        "# 纠正后的单一人工入口\n\n"
        "- `00_APPROVED_CURRENT`：历史人工通过且当前证据仍有效的观众长片。\n"
        "- `01_TO_REVIEW`：达到长片门槛但仍待播放的观众产品；当前为空。\n"
        "- `MATERIAL`：全部64个素材统一平铺，审批状态只记录在索引。\n"
        "- 故事短事件和未闭合路线只保留索引，不进入人工播放目录。\n"
        "- 所有 MP4 都是 D: 同卷 hardlink；没有复制、移动、删除或转码源媒体。\n"
        "- MATERIAL 文件名没有语言后缀或 `__none`。\n",
        encoding="utf-8",
    )
    rollback = staging / "_rollback"
    rollback.mkdir()
    previous_current = output_root / "CURRENT.json"
    if previous_current.is_file():
        (rollback / "CURRENT.before.json").write_bytes(previous_current.read_bytes())
    (rollback / "ROLLBACK.ps1").write_text(
        "$ErrorActionPreference='Stop'\n"
        f"Copy-Item -LiteralPath '{rollback / 'CURRENT.before.json'}' "
        f"-Destination '{previous_current}' -Force\n"
        "Write-Output 'CURRENT restored; immutable releases were not deleted.'\n",
        encoding="utf-8-sig",
    )
    (staging / "READY").write_text("PASS\n", encoding="ascii")
    staging.rename(release)

    current = {
        "schema": "magireco-corrected-longform-review-hub-current-v1",
        "release_id": release_id,
        "release_path": str(release),
        "approved_root": str(release / APPROVED_DIR),
        "to_review_root": str(release / REVIEW_DIR),
        "material_root": str(release / "MATERIAL"),
        "start_here": str(release / "00_START_HERE.md"),
        "index": str(release / "HUB_INDEX.csv"),
        "counts": {
            "approved_current_files": summary["approved_current_files"],
            "to_review_files": summary["to_review_files"],
            "to_review_audience_files": summary["to_review_audience_files"],
            "pending_material_files": summary["pending_material_files"],
            "material_files": summary["material_files"],
            "approved_audience_files": summary["approved_audience_files"],
            "canonical_hardlinks": summary["canonical_hardlinks"],
        },
    }
    temporary_current = output_root / "CURRENT.json.tmp"
    write_json(temporary_current, current)
    os.replace(temporary_current, output_root / "CURRENT.json")
    (output_root / "00_START_HERE.md").write_text(
        f"# 当前人工入口\n\n请打开：\n\n`{release}`\n\n"
        f"已通过：`{release / APPROVED_DIR}`\n\n"
        f"待审查：`{release / REVIEW_DIR}`\n\n"
        f"全部素材：`{release / 'MATERIAL'}`\n",
        encoding="utf-8",
    )
    return {**summary, "release_path": str(release)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-index", type=Path, required=True)
    parser.add_argument("--reassessment", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = build(
        source_index=args.source_index.resolve(),
        reassessment=args.reassessment.resolve(),
        output_root=args.output_root.resolve(),
        release_id=args.release_id,
        ffprobe=args.ffprobe,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
