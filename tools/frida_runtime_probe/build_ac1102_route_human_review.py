#!/usr/bin/env python3
"""Build and independently verify the flat ac1102 v77 human-review entry."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

try:
    from tools.frida_runtime_probe.build_event_production_manifests import file_sha256
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import file_sha256


RESEARCH_ROOT = Path(r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612")
DEFAULT_SOURCE = RESEARCH_ROOT / "no_bgm_editions_v77_ac1102_event_global_routes_20260818"
DEFAULT_OUTPUT = DEFAULT_SOURCE / "HUMAN_REVIEW"
ROUTE_LABELS = {
    0: "白标题_回避",
    1: "白标题_回避CU",
    2: "白标题_压制失败",
    4: "白标题_压制CU失败",
    6: "红标题_回避",
    7: "红标题_回避CU",
    8: "红标题_压制失败",
    10: "红标题_压制CU失败",
    12: "黑江加入白标题_回避",
    13: "黑江加入白标题_回避CU",
    14: "黑江加入白标题_压制失败",
    16: "黑江加入白标题_压制CU失败",
    18: "黑江加入红标题_回避",
    19: "黑江加入红标题_回避CU",
    20: "黑江加入红标题_压制失败",
    22: "黑江加入红标题_压制CU失败",
}
EDITIONS = {"none": "NONE", "ja": "JP", "zh": "ZH"}
INDEX_FIELDS = (
    "route_row",
    "route_label",
    "edition",
    "review_relative_path",
    "review_absolute_path",
    "source_absolute_path",
    "sha256",
    "canonical_review_relative_path",
    "exact_hash_alias",
    "samefile_with_source",
    "duration_seconds",
    "width",
    "height",
    "frame_rate",
    "video_codec",
    "audio_codec",
    "audio_sample_rate",
    "audio_channels",
    "automated_qa",
    "human_playback",
    "publication_approved",
    "product_scope",
    "natural_session_claimed",
)
ROLLBACK = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $Root 'REVIEW_INDEX.csv'))) { throw 'review index missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: review hardlinks can be disabled by same-volume rename; production media remain untouched.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    process = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(process.stdout)
    video = next(row for row in payload["streams"] if row["codec_type"] == "video")
    audio = next(row for row in payload["streams"] if row["codec_type"] == "audio")
    result = {
        "duration_seconds": round(float(payload["format"]["duration"]), 6),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "frame_rate": str(video["avg_frame_rate"]),
        "video_codec": str(video["codec_name"]),
        "audio_codec": str(audio["codec_name"]),
        "audio_sample_rate": int(audio["sample_rate"]),
        "audio_channels": int(audio["channels"]),
    }
    if result != {
        **result,
        "width": 416,
        "height": 232,
        "frame_rate": "30/1",
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
    }:
        raise ValueError(f"media contract differs: {path}")
    return result


def source_rows(source_root: Path, ffprobe: str) -> list[dict[str, Any]]:
    summary = read_json(source_root / "BATCH_SUMMARY.json")
    if (
        summary.get("status") != "AUTOMATED_QA_PASSED"
        or summary.get("selected_editions") != ["none", "ja", "zh"]
        or summary.get("human_playback_approved") is not False
        or summary.get("bilibili_release_ready") is not False
    ):
        raise ValueError("ac1102 source batch contract differs")
    expected_families = {f"ac1102_route{row:02d}" for row in ROUTE_LABELS}
    rows: list[dict[str, Any]] = []
    observed: set[str] = set()
    for family_value in summary["families"]:
        family_root = Path(family_value).resolve()
        if family_root.parent != source_root.resolve():
            raise ValueError("ac1102 family root leaves source batch")
        ready = read_json(family_root / "BATCH_REVIEW_READY.json")
        manifest = read_json(family_root / "manifests" / "family_editions_manifest.json")
        qa = read_json(family_root / "qa" / "automated_qa.json")
        family = str(ready.get("family", ""))
        row = int(family.removeprefix("ac1102_route"))
        if (
            family not in expected_families
            or family in observed
            or ready.get("status") != "AUTOMATED_QA_PASSED"
            or ready.get("publishable") is not False
            or manifest.get("status") != "AUTOMATED_QA_PASSED"
            or manifest.get("audio_profile") != "no_bgm"
            or manifest.get("bgm_policy") != "intentionally_excluded"
            or manifest.get("human_review_status") != "pending"
            or manifest.get("publishable") is not False
            or manifest.get("release_scope")
            != "edited_full_occurrence_target_progression_route_archive"
            or qa.get("status") != "passed"
            or qa.get("series_proposal_binding", {}).get("natural_session_claimed")
            is not False
        ):
            raise ValueError(f"ac1102 family QA contract differs: {family}")
        observed.add(family)
        for edition in EDITIONS:
            artifact = ready["artifacts"][f"video_{edition}"]
            path = (family_root / artifact["path"]).resolve()
            sha256 = str(artifact["sha256"]).upper()
            if not path.is_file() or file_sha256(path) != sha256:
                raise ValueError(f"ac1102 media binding differs: {path}")
            rows.append(
                {
                    "route_row": row,
                    "route_label": ROUTE_LABELS[row],
                    "edition": edition,
                    "source": path,
                    "sha256": sha256,
                    "probe": probe(path, ffprobe),
                    "product_scope": manifest["release_scope"],
                    "natural_session_claimed": False,
                }
            )
    if observed != expected_families or len(rows) != 48:
        raise ValueError("ac1102 source family coverage differs")
    return sorted(rows, key=lambda row: (row["route_row"], row["edition"]))


def review_name(row: dict[str, Any]) -> str:
    edition = row["edition"]
    return (
        f"菲利希亚牧场_ac1102_路线{row['route_row']:02d}_{row['route_label']}"
        f"__{edition}.mp4"
    )


def verify(source_root: Path, output_root: Path, ffprobe: str) -> dict[str, Any]:
    index_path = output_root / "REVIEW_INDEX.csv"
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        index = list(csv.DictReader(handle))
    source = source_rows(source_root, ffprobe)
    expected = {(row["route_row"], row["edition"]): row for row in source}
    if len(index) != 48:
        raise ValueError("ac1102 review index count differs")
    aliases = 0
    for row in index:
        key = (int(row["route_row"]), row["edition"])
        source_row = expected.pop(key)
        target = (output_root / row["review_relative_path"]).resolve()
        if (
            not target.is_file()
            or file_sha256(target) != source_row["sha256"]
            or not os.path.samefile(target, source_row["source"])
            or probe(target, ffprobe) != source_row["probe"]
            or row["human_playback"] != "HUMAN_PLAYBACK_REQUIRED"
            or row["publication_approved"] != "false"
        ):
            raise ValueError(f"ac1102 review target differs: {target}")
        aliases += row["exact_hash_alias"] == "true"
    if expected:
        raise ValueError("ac1102 review index lacks source rows")
    return {
        "schema": "magireco-ac1102-route-human-review-verification-v1",
        "result": "PASS",
        "route_count": 16,
        "edition_count": 3,
        "review_file_count": 48,
        "exact_hash_alias_count": aliases,
        "source_target_samefile_count": 48,
        "native_dimensions": "416x232",
        "native_frame_rate": "30/1",
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "audio_profile": "strict_no_bgm",
        "human_playback_required": True,
        "publication_approved": False,
        "blocked_route_media_leak_count": 0,
        "source_media_modified": False,
    }


def build(source_root: Path, output_root: Path, ffprobe: str) -> None:
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite review root: {output_root}")
    rows = source_rows(source_root, ffprobe)
    staging = output_root.with_name(f".{output_root.name}.staging-{uuid.uuid4().hex}")
    staging.mkdir(parents=True)
    canonical_by_hash: dict[str, str] = {}
    index: list[dict[str, Any]] = []
    try:
        for row in rows:
            relative = Path(EDITIONS[row["edition"]]) / "routes" / review_name(row)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(row["source"], target)
            canonical = canonical_by_hash.setdefault(row["sha256"], relative.as_posix())
            index.append(
                {
                    "route_row": row["route_row"],
                    "route_label": row["route_label"],
                    "edition": row["edition"],
                    "review_relative_path": relative.as_posix(),
                    "review_absolute_path": str((output_root / relative).resolve()),
                    "source_absolute_path": str(row["source"]),
                    "sha256": row["sha256"],
                    "canonical_review_relative_path": canonical,
                    "exact_hash_alias": str(canonical != relative.as_posix()).lower(),
                    "samefile_with_source": "true",
                    **row["probe"],
                    "automated_qa": "AUTOMATED_QA_PASSED",
                    "human_playback": "HUMAN_PLAYBACK_REQUIRED",
                    "publication_approved": "false",
                    "product_scope": row["product_scope"],
                    "natural_session_claimed": "false",
                }
            )
        with (staging / "REVIEW_INDEX.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
            writer.writeheader()
            writer.writerows(index)
        (staging / "SHA256SUMS.txt").write_text(
            "".join(f"{row['sha256']} *{row['review_relative_path']}\n" for row in index),
            encoding="utf-8",
        )
        (staging / "START_HERE.md").write_text(
            "# ac1102 菲利希亚牧场路线人工审查\n\n"
            "- 先看 `ZH/routes` 的16条路线；再抽查 `JP/routes` 与 `NONE/routes`。\n"
            "- 这批是按官方 DirInfo target-stage 顺序制作的完整事件 occurrence 编辑档案，不声称是一次原生 session。\n"
            "- 重点检查：角色开口与 VOICE、字幕同步，事件边界，循环尾帧，以及黑江加入的路线12–22。\n"
            "- 自动 QA 已通过；当前仍是 `HUMAN_PLAYBACK_REQUIRED`，未获投稿批准。\n"
            "- 含 ac1102_007/013/014/015 的15条缺源路线未进入本目录。\n",
            encoding="utf-8",
        )
        (staging / "ROLLBACK.ps1").write_text(ROLLBACK, encoding="utf-8")
        os.replace(staging, output_root)
        write_json(output_root / "VERIFICATION.json", verify(source_root, output_root, ffprobe))
    except Exception:
        if staging.exists():
            import shutil

            shutil.rmtree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    output_root = args.output_root.resolve()
    if not args.verify_only:
        build(source_root, output_root, args.ffprobe)
    result = verify(source_root, output_root, args.ffprobe)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
