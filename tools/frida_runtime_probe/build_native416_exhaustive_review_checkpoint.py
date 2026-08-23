#!/usr/bin/env python3
"""Build one flat hard-linked review checkpoint for proven native416 longforms."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
DEFAULT_V94_INDEX = (
    RESEARCH_ROOT
    / "native416_exhaustive_longform_checkpoint_v94_20260819"
    / "PRODUCTION_INDEX.csv"
)
DEFAULT_V99_INDEX = (
    RESEARCH_ROOT
    / "native416_exhaustive_longform_checkpoint_v99_20260819"
    / "LONGFORM_BATCH_INDEX.csv"
)
DEFAULT_AC0908_MANIFEST = (
    RESEARCH_ROOT
    / "no_bgm_editions_v102_ac0908_exhaustive_authoritative_20260823"
    / "manifests"
    / "PRODUCTION_MANIFEST.json"
)
DEFAULT_AC1102_VERIFICATION = (
    RESEARCH_ROOT
    / "no_bgm_editions_v120_ac1102_exhaustive_authoritative_20260823"
    / "PRODUCTION_VERIFICATION.json"
)
DEFAULT_AC1103_VERIFICATION = (
    RESEARCH_ROOT
    / "no_bgm_editions_v121r1_ac1103_exhaustive_authoritative_20260823"
    / "PRODUCTION_VERIFICATION.json"
)
DEFAULT_AC1104_VERIFICATION = (
    RESEARCH_ROOT
    / "no_bgm_editions_v126_ac1104_exhaustive_authoritative_20260824"
    / "PRODUCTION_VERIFICATION.json"
)
DEFAULT_OUTPUT = (
    RESEARCH_ROOT
    / "manual_review_hub_v2_flat"
    / "releases"
    / "native416_exhaustive_new_standard_v126_20260824"
)
EXPECTED_V94_FAMILIES = {
    "ac4002", "ac4003", "ac4004", "ac7002", "ac7118", "ac8005"
}
EXPECTED_V99_FAMILIES = {f"ac710{i}" for i in range(1, 8)}
BLOCKED_TOKENS = ("ac6003", "ac6004", "ac6005", "P16", "P17", "P18")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def safe_title(value: str) -> str:
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    if not value:
        raise ValueError("empty review title")
    return value


def title_from_v99_path(path: Path, family: str, edition: str) -> str:
    prefix = family + "_"
    suffix = f"_严格无BGM__{edition}"
    if not path.stem.startswith(prefix) or not path.stem.endswith(suffix):
        raise ValueError(f"unexpected v99 filename: {path.name}")
    return safe_title(path.stem[len(prefix) : -len(suffix)])


def probe_media(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error", "-count_frames", "-show_entries",
        (
            "stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,"
            "channels,start_time,nb_read_frames:format=duration"
        ),
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise ValueError(f"ffprobe failed for {path}: {completed.stderr.strip()}")
    probe = json.loads(completed.stdout)
    videos = [row for row in probe["streams"] if row["codec_type"] == "video"]
    audios = [row for row in probe["streams"] if row["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) != 1:
        raise ValueError("expected one video and one audio stream")
    video, audio = videos[0], audios[0]
    checks = {
        "h264": video.get("codec_name") == "h264",
        "native_416x232": (video.get("width"), video.get("height")) == (416, 232),
        "fps_30": video.get("r_frame_rate") == "30/1",
        "video_zero_start": float(video.get("start_time", "nan")) == 0.0,
        "aac": audio.get("codec_name") == "aac",
        "audio_48khz_stereo": (audio.get("sample_rate"), audio.get("channels"))
        == ("48000", 2),
        "audio_zero_start": float(audio.get("start_time", "nan")) == 0.0,
    }
    if not all(checks.values()):
        raise ValueError(f"media contract failed: {checks}")
    return {
        "checks": checks,
        "video_frames": int(video["nb_read_frames"]),
        "duration_seconds": float(probe["format"]["duration"]),
    }


def rows_from_ac0908_manifest(path: Path, group_number: int) -> list[dict[str, Any]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "ac0908_exhaustive_authoritative_longform_v2"
        or manifest.get("status") != "AUTOMATED_QA_PASS_HUMAN_PLAYBACK_REQUIRED"
        or manifest.get("canonical_presentation_count") != 14
        or manifest.get("event_container_count") != 17
        or manifest.get("frames") != 3915
    ):
        raise ValueError("ac0908 exhaustive manifest contract differs")
    outputs = manifest.get("outputs", [])
    if len(outputs) != 3 or {row.get("edition") for row in outputs} != {"none", "ja", "zh"}:
        raise ValueError("ac0908 edition matrix differs")
    result = []
    for row in outputs:
        edition = row["edition"]
        if row.get("human_status") != "HUMAN_PLAYBACK_REQUIRED" or not all(
            row.get("automatic_qa", {}).values()
        ):
            raise ValueError("ac0908 output is not automated-QA-passed review input")
        result.append(
            {
                "group_number": group_number,
                "family": "ac0908",
                "content_type": "story",
                "title": "六种菜品与全部结局完整合集",
                "edition": edition,
                "source": Path(row["path"]),
                "expected_frames": 3915,
                "existing_digest": "",
                "authority_path": str(path.resolve()),
                "primary": edition == "zh",
            }
        )
    return sorted(result, key=lambda row: row["edition"])


def rows_from_ac1102_verification(
    path: Path, group_number: int
) -> list[dict[str, Any]]:
    verification = json.loads(path.read_text(encoding="utf-8"))
    if (
        verification.get("schema")
        != "magireco-ac1102-exhaustive-production-verification-v1"
        or verification.get("status")
        != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or verification.get("content_group_count") != 1
        or verification.get("edition_file_count") != 3
        or verification.get("ordered_complete_event_presentations") != 15
        or verification.get("exact_duplicate_complete_presentation_count") != 0
        or verification.get("dirinfo_route_coverage") != "31/31"
        or verification.get("native_416x232_only") is not True
        or verification.get("strict_no_bgm") is not True
        or verification.get("blocked_p16_p17_p18_leak_count") != 0
    ):
        raise ValueError("ac1102 exhaustive production verification differs")
    media = verification.get("media", [])
    if len(media) != 3 or {row.get("edition") for row in media} != {
        "none",
        "ja",
        "zh",
    }:
        raise ValueError("ac1102 exhaustive edition matrix differs")
    authority = (
        RESEARCH_ROOT
        / "ac1102_exhaustive_longform_inputs_v120_20260823"
        / "AC1102_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
    )
    return sorted(
        [
            {
                "group_number": group_number,
                "family": "ac1102",
                "content_type": "story",
                "title": "菲莉希亚牧场 全入口·全选项·全结局完整合集",
                "edition": row["edition"],
                "source": Path(row["path"]),
                "expected_frames": int(row["frame_count"]),
                "existing_digest": str(row["sha256"]),
                "authority_path": str(authority.resolve()),
                "primary": row["edition"] == "zh",
            }
            for row in media
        ],
        key=lambda row: row["edition"],
    )


def rows_from_ac1103_verification(
    path: Path, group_number: int
) -> list[dict[str, Any]]:
    verification = json.loads(path.read_text(encoding="utf-8"))
    if (
        verification.get("schema")
        != "magireco-ac1103-exhaustive-production-verification-v1"
        or verification.get("status")
        != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or verification.get("content_group_count") != 1
        or verification.get("edition_file_count") != 3
        or verification.get("ordered_complete_event_presentations") != 13
        or verification.get("exact_duplicate_complete_presentation_count") != 0
        or verification.get("dirinfo_route_coverage") != "31/31"
        or verification.get("legacy_ac1103_013_18s_standalone_role")
        != "chapter_evidence_only"
        or verification.get("native_416x232_only") is not True
        or verification.get("strict_no_bgm") is not True
        or verification.get("blocked_p16_p17_p18_leak_count") != 0
    ):
        raise ValueError("ac1103 exhaustive production verification differs")
    media = verification.get("media", [])
    if len(media) != 3 or {row.get("edition") for row in media} != {
        "none",
        "ja",
        "zh",
    }:
        raise ValueError("ac1103 exhaustive edition matrix differs")
    authority = (
        RESEARCH_ROOT
        / "ac1103_exhaustive_longform_inputs_v121r1_20260823"
        / "AC1103_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
    )
    return sorted(
        [
            {
                "group_number": group_number,
                "family": "ac1103",
                "content_type": "story",
                "title": "鹤乃外送修行 全入口·全选项·全结局完整合集",
                "edition": row["edition"],
                "source": Path(row["path"]),
                "expected_frames": int(row["frame_count"]),
                "existing_digest": str(row["sha256"]),
                "authority_path": str(authority.resolve()),
                "primary": row["edition"] == "zh",
            }
            for row in media
        ],
        key=lambda row: row["edition"],
    )


def rows_from_ac1104_verification(
    path: Path, group_number: int
) -> list[dict[str, Any]]:
    verification = json.loads(path.read_text(encoding="utf-8"))
    if (
        verification.get("schema")
        != "magireco-ac1104-exhaustive-production-verification-v1"
        or verification.get("status")
        != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED"
        or verification.get("content_group_count") != 1
        or verification.get("edition_file_count") != 3
        or verification.get("ordered_complete_event_presentations") != 17
        or verification.get("exact_duplicate_complete_presentation_count") != 0
        or verification.get("dirinfo_route_coverage") != "15/15"
        or verification.get("native_416x232_only") is not True
        or verification.get("strict_no_bgm") is not True
        or verification.get("blocked_p16_p17_p18_leak_count") != 0
    ):
        raise ValueError("ac1104 exhaustive production verification differs")
    media = verification.get("media", [])
    if len(media) != 3 or {row.get("edition") for row in media} != {
        "none",
        "ja",
        "zh",
    }:
        raise ValueError("ac1104 exhaustive edition matrix differs")
    authority = (
        RESEARCH_ROOT
        / "ac1104_exhaustive_longform_inputs_v126_20260824"
        / "AC1104_EXHAUSTIVE_EDITORIAL_AUTHORITY.json"
    )
    return sorted(
        [
            {
                "group_number": group_number,
                "family": "ac1104",
                "content_type": "story",
                "title": "香蕉船对决 全入口·全选项·全结局完整合集",
                "edition": row["edition"],
                "source": Path(row["path"]),
                "expected_frames": int(row["frame_count"]),
                "existing_digest": str(row["sha256"]),
                "authority_path": str(authority.resolve()),
                "primary": row["edition"] == "zh",
            }
            for row in media
        ],
        key=lambda row: row["edition"],
    )


def collect(
    v94_path: Path,
    v99_path: Path,
    ac0908_manifest: Path,
    ac1102_verification: Path,
    ac1103_verification: Path,
    ac1104_verification: Path,
) -> list[dict[str, Any]]:
    v94, v99 = read_csv(v94_path), read_csv(v99_path)
    if len(v94) != 6 or {row["family"] for row in v94} != EXPECTED_V94_FAMILIES:
        raise ValueError("v94 family set differs")
    if len(v99) != 21 or {row["family"] for row in v99} != EXPECTED_V99_FAMILIES:
        raise ValueError("v99 family set differs")
    editions: defaultdict[str, set[str]] = defaultdict(set)
    for row in v99:
        editions[row["family"]].add(row["edition"])
    if any(value != {"none", "ja", "zh"} for value in editions.values()):
        raise ValueError("v99 edition matrix differs")

    families = sorted(EXPECTED_V94_FAMILIES | EXPECTED_V99_FAMILIES)
    numbers = {family: number for number, family in enumerate(families, 1)}
    result: list[dict[str, Any]] = []
    for row in v94:
        content_type = row["type"]
        result.append(
            {
                "group_number": numbers[row["family"]],
                "family": row["family"],
                "content_type": content_type,
                "title": safe_title(row["title"]),
                "edition": "material" if content_type == "material" else "none",
                "source": Path(row["canonical_path"]),
                "expected_frames": int(row["video_frames"]),
                "existing_digest": row[next(key for key in row if key.startswith("sha"))],
                "authority_path": row["authority_path"],
                "primary": True,
            }
        )
    for row in v99:
        source = Path(row["path"])
        result.append(
            {
                "group_number": numbers[row["family"]],
                "family": row["family"],
                "content_type": "story",
                "title": title_from_v99_path(source, row["family"], row["edition"]),
                "edition": row["edition"],
                "source": source,
                "expected_frames": round(float(row["duration_sec"]) * 30),
                "existing_digest": row[next(key for key in row if key.startswith("sha"))],
                "authority_path": str(
                    RESEARCH_ROOT
                    / "ac7101_ac7107_longform_authority_v97r1_20260819"
                    / "LONGFORM_AUTHORITY.json"
                ),
                "primary": row["edition"] == "zh",
            }
        )
    result.extend(rows_from_ac0908_manifest(ac0908_manifest, 14))
    result.extend(rows_from_ac1102_verification(ac1102_verification, 15))
    result.extend(rows_from_ac1103_verification(ac1103_verification, 16))
    result.extend(rows_from_ac1104_verification(ac1104_verification, 17))
    text = "\n".join(str(row["source"]) for row in result)
    if any(token.casefold() in text.casefold() for token in BLOCKED_TOKENS):
        raise ValueError("blocked family leaked into review checkpoint")
    return sorted(result, key=lambda row: (row["group_number"], row["edition"]))


def relative_target(row: dict[str, Any]) -> Path:
    prefix = f"G{row['group_number']:03d}_{row['family']}_{row['title']}"
    if row["edition"] == "material":
        return Path("MATERIAL") / f"{prefix}.mp4"
    language = {"none": "NONE", "ja": "JP", "zh": "ZH"}[row["edition"]]
    category = "gameplay_effect" if row["content_type"] == "gameplay_effect" else "story"
    suffix = {"none": "__none", "ja": "__ja", "zh": "__zh"}[row["edition"]]
    return Path(language) / category / f"{prefix}{suffix}.mp4"


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v94-index", type=Path, default=DEFAULT_V94_INDEX)
    parser.add_argument("--v99-index", type=Path, default=DEFAULT_V99_INDEX)
    parser.add_argument("--ac0908-manifest", type=Path, default=DEFAULT_AC0908_MANIFEST)
    parser.add_argument(
        "--ac1102-verification",
        type=Path,
        default=DEFAULT_AC1102_VERIFICATION,
    )
    parser.add_argument(
        "--ac1103-verification",
        type=Path,
        default=DEFAULT_AC1103_VERIFICATION,
    )
    parser.add_argument(
        "--ac1104-verification",
        type=Path,
        default=DEFAULT_AC1104_VERIFICATION,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"immutable checkpoint exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        rows = collect(
            args.v94_index.resolve(),
            args.v99_index.resolve(),
            args.ac0908_manifest.resolve(),
            args.ac1102_verification.resolve(),
            args.ac1103_verification.resolve(),
            args.ac1104_verification.resolve(),
        )
        index: list[dict[str, Any]] = []
        primary_count: defaultdict[str, int] = defaultdict(int)
        digest_families: defaultdict[str, set[str]] = defaultdict(set)
        for row in rows:
            source = row["source"].resolve()
            if not source.is_file():
                raise FileNotFoundError(source)
            relative = relative_target(row)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, target)
            if not os.path.samefile(source, target):
                raise ValueError(f"not a hardlink: {target}")
            media = probe_media(target)
            if media["video_frames"] != row["expected_frames"]:
                raise ValueError(f"frame count differs: {target}")
            if row["existing_digest"]:
                digest_families[row["existing_digest"]].add(row["family"])
            if row["primary"]:
                primary_count[row["family"]] += 1
            index.append(
                {
                    "group_number": row["group_number"],
                    "review_group_id": row["family"],
                    "title": row["title"],
                    "content_type": row["content_type"],
                    "edition": row["edition"],
                    "primary_review_file": row["primary"],
                    "review_relative_path": str(relative),
                    "source_path": str(source),
                    "existing_source_digest": row["existing_digest"],
                    "hardlink_samefile": True,
                    "physical_duplicate": False,
                    "duration_seconds": f"{media['duration_seconds']:.6f}",
                    "video_frames": media["video_frames"],
                    "resolution": "416x232",
                    "frame_rate": "30/1",
                    "audio": "AAC 48000Hz stereo",
                    "automatic_qa": "PASS",
                    "human_status": "HUMAN_PLAYBACK_REQUIRED",
                    "authority_path": row["authority_path"],
                }
            )
        families = sorted({row["review_group_id"] for row in index})
        if len(families) != 17 or any(primary_count[family] != 1 for family in families):
            raise ValueError("primary review mapping differs")
        crossing = {value: sorted(names) for value, names in digest_families.items() if len(names) > 1}
        if crossing:
            raise ValueError(f"exact duplicate crosses groups: {crossing}")

        with (staging / "REVIEW_INDEX.csv").open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(index[0]))
            writer.writeheader()
            writer.writerows(index)
        write_json(staging / "REVIEW_INDEX.json", index)
        primary = [row for row in index if row["primary_review_file"]]
        (staging / "00_START_HERE.md").write_text(
            "# 原生 416×232 新标准人工验收入口\n\n"
            "- 共 **17 组内容**；NONE/JP/ZH 伴随版不重复计组。\n"
            "- 优先播放每组的主验收文件：有中文版时位于 `ZH\\story`；"
            "无语言版位于 `NONE`；纯素材位于 `MATERIAL`。\n"
            "- 39 个媒体入口全部是同盘 NTFS 硬链接，未新增物理媒体副本。\n"
            "- 全部仍待人工播放，当前不是投稿目录。\n"
            "- 短事件均已嵌入 family 长片，没有独立短片产品。\n\n"
            "## 主验收顺序\n\n"
            + "".join(
                f"{row['group_number']}. `{row['review_group_id']}` — {row['title']} "
                f"({row['duration_seconds']} 秒，`{row['review_relative_path']}`)\n"
                for row in primary
            ),
            encoding="utf-8",
        )
        write_json(
            staging / "VERIFICATION_RECORD.json",
            {
                "schema": "magireco-native416-exhaustive-review-checkpoint-v1",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "status": "PASS_HUMAN_PLAYBACK_REQUIRED",
                "content_group_count": 17,
                "primary_review_file_count": 17,
                "edition_file_count": 39,
                "hardlink_samefile_count": 39,
                "physical_duplicate_count": 0,
                "cross_group_exact_digest_duplicate_count": 0,
                "native_416x232_only": True,
                "short_fragment_standalone_count": 0,
                "blocked_p16_p17_p18_leak_count": 0,
                "source_indexes": [
                    str(args.v94_index.resolve()),
                    str(args.v99_index.resolve()),
                    str(args.ac0908_manifest.resolve()),
                    str(args.ac1102_verification.resolve()),
                    str(args.ac1103_verification.resolve()),
                    str(args.ac1104_verification.resolve()),
                ],
                "source_media_modified": False,
                "bilibili_uploaded": False,
            },
        )
        staging.rename(output)
    except Exception:
        if staging.exists() and staging.parent == output.parent and staging.name.startswith("."):
            shutil.rmtree(staging)
        raise
    print(f"PASS {output}")
    print("content_groups=17 primary_files=17 edition_files=39 hardlinks=39")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
