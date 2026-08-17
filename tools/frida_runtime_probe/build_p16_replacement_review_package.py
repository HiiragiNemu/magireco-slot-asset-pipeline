#!/usr/bin/env python3
"""Build the bounded P16 v70r1 human-review package.

The package is language-first and flat below the content type, matching the
current human-review hub contract.  It uses same-volume hardlinks when possible
and never edits or transcodes the source editions.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import uuid
from pathlib import Path, PurePosixPath

try:
    from tools.frida_runtime_probe.build_incremental_material_review_package import (
        file_sha256,
        probe_video,
        read_json,
        write_json,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_incremental_material_review_package import (
        file_sha256,
        probe_video,
        read_json,
        write_json,
    )


SCHEMA = "magireco-p16-replacement-review-plan-v1"
EDITIONS = ("none", "ja", "zh")
LANGUAGE_ROOT = {"none": "NONE", "ja": "JP", "zh": "ZH"}
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Index = Join-Path $Root 'manifests/REVIEW_INDEX.csv'
if (-not (Test-Path -LiteralPath $Index)) { throw 'review index missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: review hardlinks can be disabled without touching production media; rerun with -Apply to rename this root.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def validate_bound_path(row: dict, *, label: str) -> Path:
    path = Path(str(row.get("path", ""))).resolve()
    expected = str(row.get("sha256", "")).upper()
    if not path.is_file() or file_sha256(path) != expected:
        raise ValueError(f"{label} path or SHA-256 differs: {path}")
    return path


def safe_relative_path(value: str, *, edition: str) -> Path:
    normalized = value.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe review path: {value}")
    if len(relative.parts) != 3:
        raise ValueError(f"review path must be language/type/file: {value}")
    if relative.parts[0] != LANGUAGE_ROOT[edition] or relative.parts[1] != "story":
        raise ValueError(f"review path language/type differs: {value}")
    if not relative.name.lower().endswith(f"__{edition}.mp4"):
        raise ValueError(f"review filename edition differs: {value}")
    return Path(*relative.parts)


def validate_probe(probe: dict, expected: dict, *, edition: str) -> None:
    checks = {
        "width": int(expected["width"]),
        "height": int(expected["height"]),
        "frame_rate": str(expected["frame_rate"]),
        "video_codec": str(expected["video_codec"]),
        "audio_codec": str(expected["audio_codec"]),
        "audio_sample_rate": str(expected["audio_sample_rate"]),
        "audio_channels": int(expected["audio_channels"]),
    }
    for key, value in checks.items():
        if probe.get(key) != value:
            raise ValueError(
                f"{edition} probe mismatch for {key}: {probe.get(key)!r} != {value!r}"
            )
    actual_ms = round(float(probe["duration_seconds"]) * 1000)
    if abs(actual_ms - int(expected["duration_ms"])) > 50:
        raise ValueError(f"{edition} duration differs: {actual_ms} ms")


def load_contract(plan_path: Path, ffprobe: str) -> tuple[dict, Path, list[dict]]:
    plan = read_json(plan_path)
    if plan.get("schema") != SCHEMA:
        raise ValueError("P16 review plan schema differs")
    if plan.get("family") != "ac6003" or plan.get("publishable") is not False:
        raise ValueError("P16 review plan identity/readiness differs")
    if plan.get("review_status") != "HUMAN_PLAYBACK_REQUIRED":
        raise ValueError("P16 review plan must remain human-playback-required")

    manifest_path = validate_bound_path(
        plan["source_family_manifest"], label="source family manifest"
    )
    qa_path = validate_bound_path(plan["source_qa"], label="source QA")
    validate_bound_path(
        plan["replacement_manifest_summary"], label="replacement manifest summary"
    )
    validate_bound_path(plan["timing_authority"], label="timing authority")
    manifest = read_json(manifest_path)
    qa = read_json(qa_path)
    if (
        manifest.get("schema") != "magireco-no-bgm-story-family-editions-v1"
        or manifest.get("status") != "AUTOMATED_QA_PASSED"
        or manifest.get("family") != "ac6003"
        or manifest.get("human_review_status") != "pending"
        or manifest.get("publishable") is not False
        or qa.get("status") != "passed"
        or qa.get("family") != "ac6003"
    ):
        raise ValueError("P16 source manifest/QA state differs")
    if manifest.get("audio_profile") != "no_bgm":
        raise ValueError("P16 source audio profile differs")

    family_root = manifest_path.parent.parent
    expected = plan["expected_media"]
    rows = []
    for edition in EDITIONS:
        contract = plan["editions"][edition]
        source = (family_root / contract["source_relative_path"]).resolve()
        expected_sha = str(contract["sha256"]).upper()
        artifact = manifest["artifacts"][f"video_{edition}"]
        if (
            not source.is_file()
            or file_sha256(source) != expected_sha
            or str(artifact.get("sha256", "")).upper() != expected_sha
            or (family_root / artifact["path"]).resolve() != source
        ):
            raise ValueError(f"{edition} source artifact binding differs")
        probe = probe_video(source, ffprobe)
        validate_probe(probe, expected, edition=edition)
        rows.append(
            {
                "edition": edition,
                "source": source,
                "sha256": expected_sha,
                "relative": safe_relative_path(
                    str(contract["hub_relative_path"]), edition=edition
                ),
                "probe": probe,
            }
        )
    return plan, manifest_path, rows


def verify_output(plan_path: Path, output_root: Path, ffprobe: str) -> dict:
    plan, _, source_rows = load_contract(plan_path, ffprobe)
    index_path = output_root / "manifests" / "REVIEW_INDEX.csv"
    if not index_path.is_file():
        raise ValueError("P16 review index is missing")
    with index_path.open("r", encoding="utf-8-sig", newline="") as source:
        index_rows = list(csv.DictReader(source))
    if [row.get("edition") for row in index_rows] != list(EDITIONS):
        raise ValueError("P16 review index edition order differs")
    verified = []
    for source_row, index_row in zip(source_rows, index_rows):
        target = output_root / source_row["relative"]
        if file_sha256(target) != source_row["sha256"]:
            raise ValueError(f"{source_row['edition']} packaged SHA-256 differs")
        if index_row.get("sha256") != source_row["sha256"]:
            raise ValueError(f"{source_row['edition']} index SHA-256 differs")
        if index_row.get("human_status") != "HUMAN_PLAYBACK_REQUIRED":
            raise ValueError("review index promoted P16 without owner playback")
        probe = probe_video(target, ffprobe)
        validate_probe(probe, plan["expected_media"], edition=source_row["edition"])
        verified.append(
            {
                "edition": source_row["edition"],
                "path": str(target),
                "sha256": source_row["sha256"],
                "samefile": os.path.samefile(source_row["source"], target),
                "probe": probe,
            }
        )
    return {
        "schema": "magireco-p16-replacement-review-verification-v1",
        "result": "PASS",
        "file_count": len(verified),
        "human_status": "HUMAN_PLAYBACK_REQUIRED",
        "publishable": False,
        "source_media_modified": False,
        "files": verified,
    }


def build(plan_path: Path, output_root: Path, ffprobe: str) -> None:
    if output_root.exists():
        raise FileExistsError(f"immutable review root already exists: {output_root}")
    plan, manifest_path, rows = load_contract(plan_path, ffprobe)
    staging = output_root.with_name(f".{output_root.name}.staging-{uuid.uuid4().hex}")
    staging.mkdir(parents=True)
    try:
        index_rows = []
        for row in rows:
            target = staging / row["relative"]
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(row["source"], target)
                mode = "hardlink"
            except OSError:
                shutil.copy2(row["source"], target)
                mode = "copy"
            if file_sha256(target) != row["sha256"]:
                raise ValueError(f"{row['edition']} packaged file SHA-256 differs")
            index_rows.append(
                {
                    "edition": row["edition"],
                    "packaged_absolute_path": str(output_root / row["relative"]),
                    "source_absolute_path": str(row["source"]),
                    "link_mode": mode,
                    "samefile": str(os.path.samefile(row["source"], target)).lower(),
                    "sha256": row["sha256"],
                    "duration_seconds": row["probe"]["duration_seconds"],
                    "width": row["probe"]["width"],
                    "height": row["probe"]["height"],
                    "frame_rate": row["probe"]["frame_rate"],
                    "audio_profile": "no_bgm",
                    "automated_qa": "passed",
                    "human_status": "HUMAN_PLAYBACK_REQUIRED",
                    "suggested_action": "review_do_not_upload_yet",
                }
            )

        manifest_dir = staging / "manifests"
        manifest_dir.mkdir(parents=True)
        with (manifest_dir / "REVIEW_INDEX.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as target:
            writer = csv.DictWriter(target, fieldnames=list(index_rows[0]))
            writer.writeheader()
            writer.writerows(index_rows)
        shutil.copy2(plan_path, manifest_dir / "SOURCE_PLAN.json")
        shutil.copy2(manifest_path, manifest_dir / "SOURCE_FAMILY_MANIFEST.json")
        (staging / "ROLLBACK.ps1").write_text(ROLLBACK_SCRIPT, encoding="utf-8")
        lines = [
            "# P16 ac6003 人工复核",
            "",
            "状态：自动 QA 已通过；三轨均需项目所有者完整播放确认，当前禁止投稿。",
            "",
            "## 建议顺序",
            "1. 先看 `ZH/story/P16_八千代与美冬的冲突_ac6003__zh.mp4`。",
            "2. ZH 通过后，再抽查 JP 与 NONE 的相同时间边界。",
            "",
            "## 重点区间",
        ]
        for interval in plan["review_intervals"]:
            lines.append(
                f"- {interval['start_ms'] / 1000:.3f}–{interval['end_ms'] / 1000:.3f}s：{interval['focus']}"
            )
        lines.extend(
            [
                "",
                "## 不变量",
                "- 416×232、30fps、H.264/AAC 48kHz stereo，无 upscale。",
                "- no-BGM 表示有意排除 BGM，只保留证据绑定的对白与场景 SE。",
                "- 旧 P16 隔离文件继续隔离；本目录不会自动替换或晋升它们。",
                "- P17、P18 未进入本目录。",
                "",
            ]
        )
        (staging / "START_HERE.md").write_text("\n".join(lines), encoding="utf-8")
        os.replace(staging, output_root)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    verification = verify_output(plan_path, output_root, ffprobe)
    write_json(output_root / "manifests" / "VERIFICATION.json", verification)
    sums = []
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            sums.append(
                f"{file_sha256(path)}  {path.relative_to(output_root).as_posix()}"
            )
    (output_root / "manifests" / "SHA256SUMS.txt").write_text(
        "\n".join(sums) + "\n", encoding="utf-8"
    )
    print(json.dumps(verification, ensure_ascii=False, sort_keys=True))


def main() -> int:
    args = parse_args()
    try:
        plan = args.plan.resolve()
        output = args.output_root.resolve()
        if args.verify_only:
            result = verify_output(plan, output, args.ffprobe)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            build(plan, output, args.ffprobe)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
