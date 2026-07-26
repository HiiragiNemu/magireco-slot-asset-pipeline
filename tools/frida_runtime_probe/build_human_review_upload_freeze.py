#!/usr/bin/env python3
"""Build a read-only-source human review/upload freeze package."""

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
from collections import Counter, defaultdict
from pathlib import Path


ALLOWED_STATES = frozenset({"ready_to_upload", "human_playback_required"})
EDITION_ORDER = {"none": 0, "ja": 1, "zh": 2}
FORBIDDEN_MEDIA_FRAGMENTS = (
    "ac6003",
    "ac6004",
    "ac6005",
    "p16",
    "p17",
    "p18",
    "superseded",
    "quarantine",
    "human_playback_failed",
)
BASELINE_BV = {
    "none": "BV1rUKN6iEcj",
    "ja": "BV1zQKN6eEC6",
    "zh": "BV13bKN6nEsd",
}
MATERIAL_TITLES = {
    "ac0906_small_kyubey_actions_v1": "小丘比动作素材",
    "ac0931_uwasa_battle_intros_v1": "传闻战斗开场素材",
    "ac5004_chance_color_titles_v1": "机会颜色标题素材",
    "ac8000_next_continue_ui_v1": "下一段与继续界面素材",
    "ac8004_shutter_transitions_v1": "快门转场素材",
    "ac0912_small_kyubey_3on_guides_v1": "小丘比三停引导素材",
    "ac7204_small_result_color_cards_v1": "小尺寸六色结果卡素材",
    "ac7204_large_result_color_cards_v1": "大尺寸六色与烟花彩虹结果卡素材",
    "ac4904_su_window_group_01_v1": "环彩羽等五人窗框素材",
    "ac4904_su_window_group_02_v1": "鹿目圆等五人窗框素材",
    "ac4904_su_window_group_03_v1": "音梦等五人窗框素材",
}
FAMILY_TITLES = {
    "ac0908": "六种菜品选项",
    "ac0911": "互斥分支路线",
    "ac4902": "迎战神滨魔女群路线",
    "ac4903": "互斥分支路线",
    "ac6007": "完整入口路线",
    "ac7206": "互斥分支路线",
    "ac7210": "火箭突击路线",
}


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


def edition_for(row: dict) -> str:
    track = str(row.get("subtitle_track", "")).casefold()
    name = str(row.get("exact_filename", "")).casefold()
    if "ja burned" in track or name.endswith("__ja.mp4"):
        return "ja"
    if "zh burned" in track or name.endswith("__zh.mp4"):
        return "zh"
    if (
        "no burned" in track
        or "visual-only" in track
        or name.endswith("__none.mp4")
    ):
        return "none"
    raise ValueError(f"cannot resolve edition for {row.get('exact_filename')}")


def family_for(row: dict) -> str:
    values = (
        row.get("exact_filename"),
        row.get("suggested_part_name"),
        row.get("absolute_folder"),
    )
    for value in values:
        match = re.search(r"ac\d+", str(value or ""), flags=re.IGNORECASE)
        if match:
            return match.group(0).casefold()
    raise ValueError(f"cannot resolve family for {row.get('exact_filename')}")


def route_for(row: dict) -> str:
    text = " ".join(
        str(row.get(key, ""))
        for key in ("exact_filename", "suggested_part_name", "absolute_folder")
    )
    match = re.search(r"路线\s*0*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(
        r"dirinfo[-_]rows?[-_]?0*(\d+)(?:[-_]0*(\d+))?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        if match.group(2):
            return f"{match.group(1)}-{match.group(2)}"
        return match.group(1)
    match = re.search(
        r"(?:route[-_]?row|row)[-_]?0*(\d+)", text, flags=re.IGNORECASE
    )
    return match.group(1) if match else ""


def is_material(row: dict) -> bool:
    text = " ".join(
        str(row.get(key, ""))
        for key in (
            "absolute_folder",
            "target_bv",
            "subtitle_track",
            "scope_note",
        )
    ).casefold()
    return (
        "material_collections_" in text
        or "玩法／素材" in text
        or "visual-only" in text
    )


def content_stem(row: dict) -> str:
    value = Path(str(row["exact_filename"])).stem
    return re.sub(r"__(?:none|ja|zh)$", "", value, flags=re.IGNORECASE)


def product_key(row: dict) -> str:
    folder = str(Path(str(row["absolute_folder"])).resolve()).casefold()
    return f"{folder}|{content_stem(row).casefold()}"


def _has_chinese(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def short_title(row: dict, family: str, route: str) -> str:
    stem = content_stem(row)
    for collection, title in MATERIAL_TITLES.items():
        if stem.startswith(collection):
            return title
    value = str(row.get("suggested_part_name") or stem)
    value = re.sub(r"__(?:none|ja|zh)$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^P\d+\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"ac\d+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"路线\s*0*\d+", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"(?:dirinfo|showcase|route)[A-Za-z0-9_\-]*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"【([^】]+)】", r"\1", value)
    value = re.sub(r"[<>:\"/\\|?*]", "", value)
    value = re.sub(r"[_\s]+", "", value).strip(" .-_")
    if not _has_chinese(value):
        value = FAMILY_TITLES.get(family, "分支路线或玩法素材")
    if route and value.endswith(f"路线{route}"):
        value = value[: -len(f"路线{route}")]
    return (value or FAMILY_TITLES.get(family, "待审视频"))[:48]


def suggested_part_name(
    *, title: str, family: str, route: str, edition: str
) -> str:
    base = f"{title} {family}"
    if route:
        base += f"_路线{route}"
    if edition == "ja":
        return base + "__ja"
    if edition == "zh":
        return base + " 中文版"
    return base


def target_bv_for(row: dict, edition: str, material: bool) -> str:
    source_target = str(row.get("target_bv", "")).strip()
    if material:
        return "新建：MagiaReco Slot 原生416玩法／素材合集 BV"
    if (
        "当前已投稿的 ZH" in source_target
        or "clean-story 中文" in source_target
    ):
        return BASELINE_BV["zh"]
    if source_target == "新建：MagiaReco Slot 日文字幕路线合集 BV":
        return BASELINE_BV["ja"]
    if "新建或追加：ac7210" in source_target:
        return BASELINE_BV[edition]
    return source_target or BASELINE_BV[edition]


def probe_video(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels",
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
        (item for item in streams if item.get("codec_type") == "video"), None
    )
    if not video:
        raise ValueError(f"source has no video stream: {path}")
    audio = next(
        (item for item in streams if item.get("codec_type") == "audio"), {}
    )
    return {
        "duration_seconds": round(float(value["format"]["duration"]), 6),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "frame_rate": str(video.get("r_frame_rate", "")),
        "video_codec": str(video.get("codec_name", "")),
        "audio_codec": str(audio.get("codec_name", "")),
        "audio_sample_rate": str(audio.get("sample_rate", "")),
        "audio_channels": int(audio.get("channels", 0) or 0),
    }


def review_priority(entry: dict) -> tuple:
    source = entry["source_path"].casefold()
    if "no_bgm_editions_v30_" in source:
        root_priority = 0
    elif "no_bgm_editions_v31_" in source:
        root_priority = 1
    elif "no_bgm_editions_v34_" in source:
        root_priority = 2
    elif "no_bgm_editions_v35_" in source:
        root_priority = 3
    else:
        root_priority = 4
    return (
        root_priority,
        entry["family"],
        entry["route"],
        entry["product_key"],
    )


def make_batches(
    groups: list[list[dict]], *, max_products: int = 10, max_seconds: int = 1800
) -> list[list[list[dict]]]:
    batches: list[list[list[dict]]] = []
    current: list[list[dict]] = []
    current_seconds = 0.0
    current_hashes: set[str] = set()
    for group in groups:
        seen_hashes: set[str] = set()
        group_seconds = 0.0
        for row in group:
            sha256 = row["expected_sha256"]
            if sha256 in seen_hashes or sha256 in current_hashes:
                continue
            seen_hashes.add(sha256)
            group_seconds += float(row["duration_seconds"])
        if current and (
            len(current) >= max_products
            or current_seconds + group_seconds > max_seconds
        ):
            batches.append(current)
            current = []
            current_seconds = 0.0
            current_hashes = set()
            seen_hashes = set()
            group_seconds = 0.0
            for row in group:
                sha256 = row["expected_sha256"]
                if sha256 in seen_hashes:
                    continue
                seen_hashes.add(sha256)
                group_seconds += float(row["duration_seconds"])
        current.append(group)
        current_seconds += group_seconds
        current_hashes.update(seen_hashes)
    if current:
        batches.append(current)
    return batches


def unique_duration_seconds(groups: list[list[dict]], hash_field: str) -> float:
    seen_hashes: set[str] = set()
    total = 0.0
    for group in groups:
        for row in group:
            sha256 = row[hash_field]
            if sha256 in seen_hashes:
                continue
            seen_hashes.add(sha256)
            total += float(row["duration_seconds"])
    return round(total, 6)


def link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy_fallback"


def csv_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value if value is not None else "")


def write_index(path: Path, rows: list[dict]) -> None:
    fields = [
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
        "source_guide_target",
        "source_guide_action",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def build(*, guide_path: Path, output_root: Path, ffprobe: str) -> Path:
    guide_path = guide_path.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite freeze root: {output_root}")
    guide = read_json(guide_path)
    items = guide.get("items")
    if not isinstance(items, list):
        raise ValueError("upload guide items must be a list")
    selected = [row for row in items if row.get("state") in ALLOWED_STATES]
    uploaded = [row for row in items if row.get("state") == "already_uploaded"]
    if len(selected) != 196 or len(uploaded) != 10:
        raise ValueError(
            "v41 freeze cardinality mismatch: "
            f"selected={len(selected)} uploaded={len(uploaded)}"
        )
    selected_by_sha: dict[str, list[dict]] = defaultdict(list)
    for row in selected:
        selected_by_sha[str(row.get("sha256", "")).strip().upper()].append(row)
    canonical_source_by_sha = {}
    for sha256, rows in selected_by_sha.items():
        canonical = min(
            rows,
            key=lambda row: (
                0 if row.get("state") == "ready_to_upload" else 1,
                EDITION_ORDER[edition_for(row)],
                str(row.get("absolute_folder", "")).casefold(),
                str(row.get("exact_filename", "")).casefold(),
            ),
        )
        canonical_source_by_sha[sha256] = str(
            (
                Path(str(canonical["absolute_folder"]))
                / str(canonical["exact_filename"])
            ).resolve()
        ).casefold()

    parent = output_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=parent)
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

        prepared: list[dict] = []
        seen_source_paths: set[str] = set()
        for index, row in enumerate(selected, start=1):
            source = (
                Path(str(row["absolute_folder"])) / str(row["exact_filename"])
            ).resolve()
            source_text = str(source)
            folded = source_text.casefold()
            if any(fragment in folded for fragment in FORBIDDEN_MEDIA_FRAGMENTS):
                raise ValueError(f"forbidden media leaked into guide: {source}")
            if not source.is_file():
                raise FileNotFoundError(source)
            source_key = source_text.casefold()
            if source_key in seen_source_paths:
                raise ValueError(f"duplicate source path in guide: {source}")
            seen_source_paths.add(source_key)
            expected_sha = str(row.get("sha256", "")).strip().upper()
            if not re.fullmatch(r"[0-9A-F]{64}", expected_sha):
                raise ValueError(f"invalid guide SHA-256: {source}")
            is_hash_canonical = (
                source_key == canonical_source_by_sha[expected_sha]
            )
            if not is_hash_canonical:
                alias_actual_sha = file_sha256(source)
                if alias_actual_sha != expected_sha:
                    raise ValueError(
                        f"deduplicated alias SHA-256 mismatch: {source}; "
                        f"expected={expected_sha} actual={alias_actual_sha}"
                    )
            edition = edition_for(row)
            family = family_for(row)
            route = route_for(row)
            material = is_material(row)
            title = short_title(row, family, route)
            probe = probe_video(source, ffprobe)
            prepared.append(
                {
                    "source_row": row,
                    "source": source,
                    "source_path": source_text,
                    "expected_sha256": expected_sha,
                    "is_hash_canonical": is_hash_canonical,
                    "edition": edition,
                    "family": family,
                    "route": route,
                    "material": material,
                    "title": title,
                    "product_key": product_key(row),
                    **probe,
                }
            )
            if index % 20 == 0 or index == len(selected):
                print(
                    f"[preflight] {index}/{len(selected)} exact files",
                    flush=True,
                )

        groups_by_key: dict[str, list[dict]] = defaultdict(list)
        for entry in prepared:
            groups_by_key[entry["product_key"]].append(entry)
        for group in groups_by_key.values():
            editions = [entry["edition"] for entry in group]
            if len(editions) != len(set(editions)):
                raise ValueError(
                    f"same product has duplicate edition: {group[0]['product_key']}"
                )
            if len({entry["material"] for entry in group}) != 1:
                raise ValueError("same product crosses story/material lanes")
        groups = list(groups_by_key.values())

        ready_groups = sorted(
            [
                [
                    entry
                    for entry in group
                    if entry["source_row"]["state"] == "ready_to_upload"
                ]
                for group in groups
                if any(
                    entry["source_row"]["state"] == "ready_to_upload"
                    for entry in group
                )
            ],
            key=lambda group: review_priority(group[0]),
        )
        review_story_groups = sorted(
            [
                [
                    entry
                    for entry in group
                    if entry["source_row"]["state"]
                    == "human_playback_required"
                ]
                for group in groups
                if not group[0]["material"]
                and any(
                    entry["source_row"]["state"]
                    == "human_playback_required"
                    for entry in group
                )
            ],
            key=lambda group: review_priority(group[0]),
        )
        review_material_groups = sorted(
            [
                [
                    entry
                    for entry in group
                    if entry["source_row"]["state"]
                    == "human_playback_required"
                ]
                for group in groups
                if group[0]["material"]
                and any(
                    entry["source_row"]["state"]
                    == "human_playback_required"
                    for entry in group
                )
            ],
            key=lambda group: review_priority(group[0]),
        )
        ordered_keys = []
        for group in ready_groups + review_story_groups + review_material_groups:
            key = group[0]["product_key"]
            if key not in ordered_keys:
                ordered_keys.append(key)
        id_by_key = {
            key: f"U{index:03d}"
            for index, key in enumerate(ordered_keys, start=1)
        }

        story_batches = make_batches(review_story_groups)
        material_batches = make_batches(review_material_groups)
        batch_by_key: dict[str, tuple[str, str]] = {}
        for number, batch in enumerate(story_batches, start=1):
            batch_name = f"batch_{number:03d}"
            (staging / "01_REVIEW_STORY" / batch_name).mkdir()
            for group in batch:
                batch_by_key[group[0]["product_key"]] = (
                    "01_REVIEW_STORY",
                    batch_name,
                )
        for number, batch in enumerate(material_batches, start=1):
            batch_name = f"batch_{number:03d}"
            (staging / "02_REVIEW_MATERIAL" / batch_name).mkdir()
            for group in batch:
                batch_by_key[group[0]["product_key"]] = (
                    "02_REVIEW_MATERIAL",
                    batch_name,
                )

        index_rows: list[dict] = []
        canonical_destination_by_sha: dict[str, dict] = {}
        packaging_entries = sorted(
            prepared,
            key=lambda entry: (
                0 if entry["is_hash_canonical"] else 1,
                entry["expected_sha256"],
                EDITION_ORDER[entry["edition"]],
            ),
        )
        for index, entry in enumerate(packaging_entries, start=1):
            row = entry["source_row"]
            upload_id = id_by_key[entry["product_key"]]
            route_suffix = (
                f"_路线{entry['route']}" if entry["route"] else ""
            )
            filename = (
                f"{upload_id}_{entry['title']}_{entry['family']}"
                f"{route_suffix}__{entry['edition']}.mp4"
            )
            if row["state"] == "ready_to_upload":
                queue = "00_UPLOAD_NOW"
                batch = entry["edition"]
                relative = Path(queue) / batch / filename
                action = "UPLOAD_NOW_OWNER_ACTION_ONLY"
            else:
                queue, batch = batch_by_key[entry["product_key"]]
                relative = Path(queue) / batch / entry["edition"] / filename
                action = "HOLD_FOR_HUMAN_PLAYBACK"
            destination = staging / relative
            if entry["is_hash_canonical"]:
                link_mode = link_or_copy(entry["source"], destination)
                canonical_destination_by_sha[entry["expected_sha256"]] = {
                    "staged_path": destination,
                    "packaged_file": relative.as_posix(),
                    "edition": entry["edition"],
                }
            else:
                canonical = canonical_destination_by_sha.get(
                    entry["expected_sha256"]
                )
                if canonical is None:
                    raise ValueError("exact-hash alias preceded its canonical file")
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(canonical["staged_path"], destination)
                except OSError as error:
                    raise RuntimeError(
                        "same-volume exact-hash alias hardlink failed; refusing "
                        "a physical duplicate copy"
                    ) from error
                link_mode = "hardlink_alias_same_canonical_sha"
            actual_sha = file_sha256(destination)
            if actual_sha != entry["expected_sha256"]:
                raise ValueError(
                    f"packaged SHA-256 mismatch: {destination}; "
                    f"expected={entry['expected_sha256']} actual={actual_sha}"
                )
            resolved_destination = output_root / relative
            canonical = canonical_destination_by_sha[actual_sha]
            index_rows.append(
                {
                    "upload_id": upload_id,
                    "queue": queue,
                    "batch": batch,
                    "packaged_file": relative.as_posix(),
                    "packaged_absolute_path": str(resolved_destination),
                    "source_absolute_path": entry["source_path"],
                    "link_mode": link_mode,
                    "sha256": actual_sha,
                    "canonical_sha256": actual_sha,
                    "canonical_packaged_file": canonical["packaged_file"],
                    "is_canonical_exact_hash": entry["is_hash_canonical"],
                    "physical_duplicate": False,
                    "duration_seconds": entry["duration_seconds"],
                    "width": entry["width"],
                    "height": entry["height"],
                    "frame_rate": entry["frame_rate"],
                    "video_codec": entry["video_codec"],
                    "audio_codec": entry["audio_codec"],
                    "audio_sample_rate": entry["audio_sample_rate"],
                    "audio_channels": entry["audio_channels"],
                    "family": entry["family"],
                    "route": entry["route"],
                    "edition": entry["edition"],
                    "subtitle_track": row["subtitle_track"],
                    "automated_qa_status": row["automated_qa_status"],
                    "human_approval_status": row["human_approval_status"],
                    "suggested_action": action,
                    "target_bv": target_bv_for(
                        row, entry["edition"], entry["material"]
                    ),
                    "suggested_part_name": suggested_part_name(
                        title=entry["title"],
                        family=entry["family"],
                        route=entry["route"],
                        edition=entry["edition"],
                    ),
                    "source_guide_target": row["target_bv"],
                    "source_guide_action": row["action"],
                    "product_key": entry["product_key"],
                }
            )
            if index % 20 == 0 or index == len(packaging_entries):
                print(
                    f"[package] {index}/{len(packaging_entries)} target files",
                    flush=True,
                )

        index_rows.sort(
            key=lambda row: (
                int(row["upload_id"][1:]),
                EDITION_ORDER[row["edition"]],
            )
        )
        manifest_root = staging / "manifests"
        write_index(manifest_root / "UPLOAD_INDEX.csv", index_rows)
        alias_rows = []
        for row in index_rows:
            if row["is_canonical_exact_hash"]:
                continue
            alias_rows.append(
                {
                    "upload_id": row["upload_id"],
                    "family": row["family"],
                    "route": row["route"],
                    "alias_edition": row["edition"],
                    "alias_packaged_file": row["packaged_file"],
                    "source_absolute_path": row["source_absolute_path"],
                    "sha256": row["sha256"],
                    "canonical_packaged_file": row["canonical_packaged_file"],
                    "physical_duplicate": False,
                    "target_bv": row["target_bv"],
                    "reason": (
                        "legal cross-target exact-hash alias; separate hardlink "
                        "name, same canonical physical data"
                    ),
                }
            )
        alias_fields = [
            "upload_id",
            "family",
            "route",
            "alias_edition",
            "alias_packaged_file",
            "source_absolute_path",
            "sha256",
            "canonical_packaged_file",
            "physical_duplicate",
            "target_bv",
            "reason",
        ]
        with (manifest_root / "ALIASES.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as target:
            writer = csv.DictWriter(target, fieldnames=alias_fields)
            writer.writeheader()
            writer.writerows(alias_rows)
        shutil.copy2(guide_path, manifest_root / "SOURCE_UPLOAD_GUIDE_V41.json")

        uploaded_lines = []
        for row in uploaded:
            uploaded_lines.append(
                f"- `{row['sha256']}` — "
                f"`{row['absolute_folder']}\\{row['exact_filename']}`"
            )
        exclusions = guide.get("explicit_exclusions", [])
        exclusion_lines = [
            "# 明确排除项",
            "",
            "以下内容均未放入任何可上传或待审媒体目录：",
            "",
        ]
        for row in exclusions:
            exclusion_lines.append(
                f"- **{row['scope']}**：`{row['disposition']}`；"
                f"{row['reason']}"
            )
        exclusion_lines.extend(
            [
                "- 所有路径包含 `superseded`、旧错误、quarantine、P16/ac6003、"
                "P17/ac6004、P18/ac6005 的媒体。",
                "- 未进入 v41 精确文件指南的 child-local 起点未闭合项目；"
                "不得因自动 QA 或相邻版本通过而晋升。",
                "- 下列 10 个精确哈希已投稿，不在交接媒体队列中，禁止重复上传：",
                "",
                *uploaded_lines,
                "",
                "## 合法跨目标精确哈希别名",
                "",
                "下列 edition 字节完全相同，但分别对应不同目标轨。交接包保留"
                "各自正确命名的 hardlink；它们指向同一 canonical 物理数据，"
                "`physical_duplicate=false`。对应关系也写入 `ALIASES.csv`：",
                "",
                *[
                    f"- `{row['alias_packaged_file']}` → "
                    f"`{row['canonical_packaged_file']}`；SHA-256 "
                    f"`{row['sha256']}`；目标 `{row['target_bv']}`"
                    for row in alias_rows
                ],
                "",
            ]
        )
        (manifest_root / "EXCLUSIONS.md").write_text(
            "\n".join(exclusion_lines), encoding="utf-8"
        )
        (staging / "03_QUARANTINED_DO_NOT_UPLOAD" / "README_ONLY_MANIFESTS.md").write_text(
            "# 隔离区\n\n"
            "本目录故意不放任何 MP4，避免误传。P16/ac6003、P17/ac6004、"
            "P18/ac6005、所有 superseded、旧错误/重复和未闭合 child-local "
            "项目的精确状态请查看 `..\\manifests\\EXCLUSIONS.md`。\n",
            encoding="utf-8",
        )

        ready_rows = [row for row in index_rows if row["queue"] == "00_UPLOAD_NOW"]
        first_story_batch = (
            output_root / "01_REVIEW_STORY" / "batch_001"
            if story_batches
            else None
        )
        start_lines = [
            "# 从这里开始：人工审查与上传指南",
            "",
            "生产已冻结。本交接包只整理 v41 已存在的精确文件；没有重新编码、"
            "没有改名或覆盖源媒体，也没有上传或修改 Bilibili。",
            "",
            "## 当前 Bilibili 只读基线",
            "",
            "- ZH：`BV13bKN6nEsd`（24P）",
            "- none：`BV1rUKN6iEcj`（11P）",
            "- JA：`BV1zQKN6eEC6`（13P）",
            "",
            "## 立即可上传",
            "",
            f"共 {len(ready_rows)} 个精确文件。目录："
            f"`{output_root}\\00_UPLOAD_NOW`。",
            "只有此目录中的文件具备 exact-file 人工批准；实际上传仍由项目所有者"
            "完成。none 子目录当前为空是预期状态。",
            "",
            "| U号 | edition | 精确文件 | 建议分P名 | 目标BV/新建建议 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in ready_rows:
            start_lines.append(
                f"| {row['upload_id']} | {row['edition']} | "
                f"`{Path(row['packaged_file']).name}` | "
                f"{row['suggested_part_name']} | {row['target_bv']} |"
            )
        start_lines.extend(
            [
                "",
                "## 人工审查顺序",
                "",
                f"先看 `{first_story_batch}`。" if first_story_batch else "无剧情待审批次。",
                "每批最多 10 个作品，并以该批不同 exact hash 的合计播放时长约"
                " 30 分钟为更严格上限；合法跨目标 hardlink alias 不重复计时，"
                "同一作品的 none/JA/ZH 不拆批。",
                "每个 `batch_###` 内再按 `none/ja/zh` 分目录；同一 U号可直接"
                "对应，且不会混用不同来源版本。",
                "",
                f"- 剧情待审：{len(review_story_groups)} 个作品，"
                f"{sum(len(group) for group in review_story_groups)} 个文件，"
                f"{len(story_batches)} 批。",
                f"- 素材待审：{len(review_material_groups)} 个作品，"
                f"{sum(len(group) for group in review_material_groups)} 个文件，"
                f"{len(material_batches)} 批。",
                f"- 另有 {len(alias_rows)} 个 edition 与规范文件 exact hash "
                "完全相同；已保留不同目标所需的同 inode hardlink，见 "
                "`ALIASES.csv`。",
                "- 待审文件即使自动 QA 通过，也必须完整播放后才能逐 exact hash "
                "批准；不得批量外推 sibling edition。",
                "",
                "## 命名规则",
                "",
                "`U###_中文短标题_acXXXX[_路线N]__none|ja|zh.mp4`。U号按本次"
                "作品键重新分配，不采用旧 P 号推断播放顺序。建议 B站分P名已写入"
                "`UPLOAD_INDEX.csv`。",
                "",
                "## 明确禁止",
                "",
                "不要上传 `03_QUARANTINED_DO_NOT_UPLOAD` 中列出的任何对象；"
                "不要重复上传已投稿的 10 个 exact hash；不要把素材片当 clean story；"
                "不要把互斥路线拼成一条原生 session。Codex 不上传。",
                "",
            ]
        )
        (manifest_root / "START_HERE_UPLOAD_GUIDE.md").write_text(
            "\n".join(start_lines), encoding="utf-8"
        )

        checklist_lines = [
            "# 人工播放检查表",
            "",
            "对每个 U 号逐项记录；同一 U 号的不同 edition 分别确认。",
            "",
            "- [ ] 从头到尾完整播放，无截断、黑帧异常或卡死",
            "- [ ] 画面顺序、入口、选项与路线边界自然",
            "- [ ] 角色张嘴与声音同步，无提前/滞后",
            "- [ ] 字幕起止与声音同步，人物身份和译名正确",
            "- [ ] none/JA/ZH 画面与音频包一致，仅字幕轨按 edition 改变",
            "- [ ] 30fps、原生分辨率，无 upscale",
            "- [ ] no-BGM 只表达有意排除 BGM，已验证对白与 SE 保留",
            "- [ ] 互斥路线没有被冒充同一自然 session",
            "- [ ] 素材/玩法片保持独立，不冒充 clean story",
            "- [ ] 在 `UPLOAD_INDEX.csv` 中按 exact SHA-256 记录批准或失败",
            "",
            "身份规则：黑羽（黒羽）、黑（黒）、黑江（黒江）是三人；"
            "`speaker_code=kuro` 禁止全局映射，`kuroe` 才是黑江。"
            "其他未获证据的 `kuro` 不加人物名前缀。",
            "",
        ]
        (manifest_root / "HUMAN_REVIEW_CHECKLIST.md").write_text(
            "\n".join(checklist_lines), encoding="utf-8"
        )

        batch_rows = []
        for lane, batches in (
            ("story", story_batches),
            ("material", material_batches),
        ):
            for batch_number, batch in enumerate(batches, start=1):
                batch_rows.append(
                    {
                        "lane": lane,
                        "batch": f"batch_{batch_number:03d}",
                        "product_count": len(batch),
                        "file_count": sum(len(group) for group in batch),
                        "duration_seconds": unique_duration_seconds(
                            batch, "expected_sha256"
                        ),
                        "upload_ids": [
                            id_by_key[group[0]["product_key"]] for group in batch
                        ],
                    }
                )
        summary = {
            "schema": "magireco-human-review-upload-freeze-v1",
            "status": "PRODUCTION_FROZEN_HANDOFF_READY",
            "source_upload_guide": str(guide_path),
            "source_upload_guide_sha256": file_sha256(guide_path),
            "output_root": str(output_root),
            "source_selected_exact_row_count": len(prepared),
            "packaged_target_file_count": len(index_rows),
            "unique_canonical_sha256_count": len(
                {row["sha256"] for row in index_rows}
            ),
            "legal_cross_target_alias_count": len(alias_rows),
            "upload_now_file_count": len(ready_rows),
            "review_story_file_count": sum(
                len(group) for group in review_story_groups
            ),
            "review_story_product_count": len(review_story_groups),
            "review_story_batch_count": len(story_batches),
            "review_material_file_count": sum(
                len(group) for group in review_material_groups
            ),
            "review_material_product_count": len(review_material_groups),
            "review_material_batch_count": len(material_batches),
            "already_uploaded_excluded_count": len(uploaded),
            "explicit_exclusion_count": len(exclusions),
            "link_modes": dict(Counter(row["link_mode"] for row in index_rows)),
            "quarantine_media_file_count": 0,
            "batches": batch_rows,
            "claim_boundary": (
                "Only 00_UPLOAD_NOW exact files are playback-approved. Review "
                "queues remain non-publishable until owner playback approval. "
                "No Bilibili mutation was performed."
            ),
        }
        write_json(manifest_root / "PACKAGE_SUMMARY.json", summary)

        media_hashes = {
            row["packaged_file"]: row["sha256"] for row in index_rows
        }
        hash_lines = []
        for path in sorted(
            (path for path in staging.rglob("*") if path.is_file()),
            key=lambda value: value.relative_to(staging).as_posix().casefold(),
        ):
            if path.name == "SHA256SUMS.txt":
                continue
            relative = path.relative_to(staging).as_posix()
            sha256 = media_hashes.get(relative) or file_sha256(path)
            hash_lines.append(f"{sha256}  {relative}")
        (manifest_root / "SHA256SUMS.txt").write_text(
            "\n".join(hash_lines) + "\n", encoding="utf-8"
        )

        # Final fail-closed audit before publication.
        media = list(staging.rglob("*.mp4"))
        if len(media) != len(index_rows):
            raise ValueError(
                f"packaged MP4 count mismatch: {len(media)} != {len(index_rows)}"
            )
        quarantine_media = list(
            (staging / "03_QUARANTINED_DO_NOT_UPLOAD").rglob("*.mp4")
        )
        if quarantine_media:
            raise ValueError("quarantine directory contains media")
        rows_by_sha: dict[str, list[dict]] = defaultdict(list)
        for row in index_rows:
            rows_by_sha[row["sha256"]].append(row)
        for sha256, rows in rows_by_sha.items():
            canonical = [
                row for row in rows if row["is_canonical_exact_hash"]
            ]
            if len(canonical) != 1:
                raise ValueError(
                    f"exact-hash group lacks one canonical row: {sha256}"
                )
            canonical_path = staging / canonical[0]["packaged_file"]
            for row in rows:
                path = staging / row["packaged_file"]
                if not os.path.samefile(canonical_path, path):
                    raise ValueError(
                        "exact-hash alias is a physical duplicate instead of "
                        f"a hardlink: {path}"
                    )
                if row["physical_duplicate"] is not False:
                    raise ValueError("physical_duplicate flag must be false")
        for batch in batch_rows:
            if batch["product_count"] > 10:
                raise ValueError(f"batch exceeds 10 products: {batch}")
            if batch["duration_seconds"] > 1800 and batch["product_count"] > 1:
                raise ValueError(f"batch exceeds 30 minutes: {batch}")
        staging.replace(output_root)
        return output_root
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guide", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    destination = build(
        guide_path=args.guide,
        output_root=args.output_root,
        ffprobe=args.ffprobe,
    )
    summary = read_json(destination / "manifests" / "PACKAGE_SUMMARY.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
