#!/usr/bin/env python3
"""Build one hash-bound pointer to the current MagiaReco production state.

The media batches remain immutable in their versioned D: roots.  This builder
does not copy or encode media; it verifies the exhaustive ledger, upload guide,
and narrow metadata corrections, then publishes one small control-plane index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_bound_json(binding: Mapping[str, Any], *, label: str) -> tuple[Path, Any]:
    path = Path(str(binding.get("path", ""))).resolve()
    expected = str(binding.get("sha256", "")).upper()
    if not path.is_file():
        raise ValueError(f"{label} path is not a file: {path}")
    actual = file_sha256(path)
    if not expected or actual != expected:
        raise ValueError(
            f"{label} SHA-256 differs: expected {expected}, got {actual}: {path}"
        )
    return path, read_json(path)


def validate_guide_files(guide: Mapping[str, Any]) -> dict[str, Any]:
    items = guide.get("items")
    counts = guide.get("counts")
    if not isinstance(items, list) or not isinstance(counts, Mapping):
        raise ValueError("upload guide items/counts are malformed")

    states = Counter(str(item.get("state", "")) for item in items)
    expected_states = {
        "already_uploaded": int(counts.get("already_uploaded", -1)),
        "ready_to_upload": int(counts.get("ready_to_upload", -1)),
        "human_playback_required": int(counts.get("human_playback_required", -1)),
    }
    if any(states[name] != expected for name, expected in expected_states.items()):
        raise ValueError(
            f"upload guide state counts differ: actual={dict(states)} "
            f"expected={expected_states}"
        )
    if len(items) != int(counts.get("total_exact_files", -1)):
        raise ValueError("upload guide total_exact_files differs from item count")

    aggregate = hashlib.sha256()
    folders: set[str] = set()
    for item in items:
        folder = Path(str(item.get("absolute_folder", ""))).resolve()
        filename = str(item.get("exact_filename", ""))
        media = (folder / filename).resolve()
        try:
            media.relative_to(folder)
        except ValueError as exc:
            raise ValueError(f"guide media escapes its declared folder: {media}") from exc
        if not media.is_file():
            raise ValueError(f"guide media is missing: {media}")
        expected = str(item.get("sha256", "")).upper()
        actual = file_sha256(media)
        if not expected or actual != expected:
            raise ValueError(
                f"guide media SHA-256 differs: expected {expected}, got {actual}: {media}"
            )
        canonical = f"{media}|{actual}\n".encode("utf-8")
        aggregate.update(canonical)
        folders.add(str(folder))

    return {
        "exact_file_count": len(items),
        "unique_declared_folder_count": len(folders),
        "ordered_path_sha256_aggregate": aggregate.hexdigest().upper(),
        "state_counts": dict(sorted(states.items())),
    }


def is_single_material(item: Mapping[str, Any]) -> bool:
    label = str(item.get("subtitle_track", "")).lower()
    return "no audio" in label and (
        "material" in label or "visual-only" in label
    )


def edition_folder(item: Mapping[str, Any]) -> str:
    if is_single_material(item):
        return "material"
    name = str(item.get("exact_filename", "")).lower()
    label = str(item.get("subtitle_track", "")).lower()
    if name.endswith("__zh.mp4") or label.startswith("zh "):
        return "zh"
    if name.endswith("__ja.mp4") or label.startswith("ja "):
        return "jp"
    return "none"


def state_folder(state: str) -> str:
    return {
        "ready_to_upload": "01_已审查可上传",
        "human_playback_required": "02_待人工审查",
        "already_uploaded": "03_已投稿勿重复",
    }.get(state, "")


def material_filename(item: Mapping[str, Any], source_name: str) -> str:
    title = str(item.get("suggested_part_name", "")).strip()
    title = re.sub(r'[<>:"/\\|?*]', "_", title).rstrip(". ")
    dimensions = re.search(r"__([0-9]+x[0-9]+)_", source_name)
    suffix = f" [{dimensions.group(1)}]" if dimensions else ""
    if not title:
        title = Path(source_name).stem
    return f"{title}{suffix}.mp4"


def build_human_view(
    *,
    guide: Mapping[str, Any],
    human_root: Path,
    filename_overrides: Mapping[str, str],
    material_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one same-volume hardlink view without copying media or manifests."""

    human_root = human_root.resolve()
    if human_root.exists():
        raise ValueError(f"human current root already exists: {human_root}")
    staging = human_root.with_name(human_root.name + f".staging.{os.getpid()}")
    if staging.exists():
        raise ValueError(f"human current staging root already exists: {staging}")
    staging.mkdir(parents=True)
    rows: list[dict[str, str]] = []
    material_hashes: set[str] = set()
    try:
        for state in (
            "01_已审查可上传",
            "02_待人工审查",
            "03_已投稿勿重复",
        ):
            for edition in ("zh", "jp", "none", "material"):
                (staging / state / edition).mkdir(parents=True)
        (staging / "04_隔离禁止上传").mkdir()

        for item in guide["items"]:
            state = str(item["state"])
            state_dir = state_folder(state)
            if not state_dir:
                raise ValueError(f"unknown upload guide state: {state}")
            sha256 = str(item["sha256"]).upper()
            track = edition_folder(item)
            if track == "material":
                if sha256 in material_hashes:
                    raise ValueError(
                        f"duplicate material SHA entered unified human view: {sha256}"
                    )
                material_hashes.add(sha256)
            source = (
                Path(str(item["absolute_folder"])) / str(item["exact_filename"])
            ).resolve()
            source_dimensions = re.search(r"__([0-9]+x[0-9]+)_", source.name)
            filename = filename_overrides.get(
                sha256,
                material_filename(item, source.name)
                if track == "material"
                else source.name,
            )
            if Path(filename).name != filename or not filename.lower().endswith(".mp4"):
                raise ValueError(f"invalid unified human filename: {filename}")
            relative = Path(state_dir) / track / filename
            destination = staging / relative
            if destination.exists():
                raise ValueError(f"unified human filename collision: {relative}")
            os.link(source, destination)
            if not os.path.samefile(source, destination):
                raise ValueError(f"unified human file is not a hardlink: {relative}")
            if file_sha256(destination) != sha256:
                raise ValueError(f"unified human hardlink SHA differs: {relative}")
            rows.append(
                {
                    "state": state,
                    "track": track,
                    "relative_path": relative.as_posix(),
                    "sha256": sha256,
                    "suggested_part_name": str(item["suggested_part_name"]),
                    "native_dimensions": (
                        source_dimensions.group(1)
                        if source_dimensions is not None
                        else ""
                    ),
                    "scope_note": str(item.get("scope_note", "")),
                    "source_path": str(source),
                }
            )

        guide_lines = [
            "# MagiaReco Slot 统一上传与人工审查入口",
            "",
            "今后人工只使用本目录；旧的版本化目录是只读机器证据，不再作为人工入口。",
            "目录内 MP4 均为同卷 hardlink，没有重新编码或占用重复媒体空间。",
            "纯视觉无声素材只放在 `material`，不生成 none/JP/ZH 语言副本。",
            "",
            f"- 已审查可上传：{sum(row['state'] == 'ready_to_upload' for row in rows)}",
            f"- 待人工审查：{sum(row['state'] == 'human_playback_required' for row in rows)}",
            f"- 已投稿勿重复：{sum(row['state'] == 'already_uploaded' for row in rows)}",
            f"- 当前精确文件：{len(rows)}",
            "",
            "## 已审查可上传（精确路径）",
            "",
        ]
        for row in rows:
            if row["state"] == "ready_to_upload":
                guide_lines.append(
                    f"- `{human_root / Path(row['relative_path'])}` — "
                    f"{row['suggested_part_name']} — SHA-256 `{row['sha256']}`"
                )
        guide_lines.extend(["", "## 已投稿勿重复（精确路径）", ""])
        for row in rows:
            if row["state"] == "already_uploaded":
                guide_lines.append(
                    f"- `{human_root / Path(row['relative_path'])}` — "
                    f"{row['suggested_part_name']} — SHA-256 `{row['sha256']}`"
                )
        guide_lines.extend(
            [
                "",
                "## 待人工审查",
                "",
                "所有待审文件均位于 `02_待人工审查`，再按 zh/jp/none/material "
                "分类；逐文件状态由统一 CURRENT 的 hash-bound guide 管理。",
                "",
                "## 永久隔离",
                "",
                "P16/ac6003、P17/ac6004、P18/ac6005 不在媒体目录中；"
                "只有精确证据闭合并重新生成 CURRENT 后才可进入。",
                "",
            ]
        )
        preferred = material_metadata.get("preferred_sha256_order", [])
        if not isinstance(preferred, list):
            raise ValueError("material preferred SHA order is malformed")
        preferred_rank = {
            str(value).upper(): index for index, value in enumerate(preferred)
        }
        material_rows = [row for row in rows if row["track"] == "material"]
        material_rows.sort(
            key=lambda row: (
                preferred_rank.get(row["sha256"], len(preferred_rank)),
                row["suggested_part_name"].casefold(),
            )
        )
        description = material_metadata.get("description_lines", [])
        if not isinstance(description, list) or any(
            not isinstance(value, str) for value in description
        ):
            raise ValueError("material Bilibili description is malformed")
        guide_lines.extend(
            [
                "## 纯素材多P投稿文案",
                "",
                f"**标题：** {material_metadata.get('title', '')}",
                "",
                *description,
                "",
                "### 建议分P顺序与名称",
                "",
            ]
        )
        for index, row in enumerate(material_rows, 1):
            title = row["suggested_part_name"]
            dimensions = row["native_dimensions"].replace("x", "×")
            role = (
                "｜叠加层素材"
                if "layer_component_material" in row["scope_note"]
                else ""
            )
            suffix = f" [{dimensions}{role}]" if dimensions or role else ""
            guide_lines.append(f"{index}. {title}{suffix}")
        guide_lines.append("")
        (staging / "00_上传指引.md").write_text(
            "\n".join(guide_lines), encoding="utf-8"
        )
        (staging / "00_今后只打开此目录.txt").write_text(
            "所有人工上传与审查都从本目录进入。旧目录保留为只读技术证据。\n",
            encoding="utf-8",
        )
        os.replace(staging, human_root)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    aggregate = hashlib.sha256()
    for row in rows:
        aggregate.update(
            f"{row['relative_path']}|{row['sha256']}\n".encode("utf-8")
        )
    return {
        "path": str(human_root),
        "exact_file_count": len(rows),
        "single_material_file_count": len(material_hashes),
        "hardlink_path_sha256_aggregate": aggregate.hexdigest().upper(),
        "counts": dict(Counter(row["state"] for row in rows)),
        "guide_path": str(human_root / "00_上传指引.md"),
        "material_bilibili_part_count": len(material_rows),
    }


def validate_quarantine(
    ledger: Mapping[str, Any],
    guide: Mapping[str, Any],
    expected: Mapping[str, str],
) -> None:
    ledger_families = ledger.get("hard_quarantine_families")
    exclusions = guide.get("explicit_exclusions")
    if not isinstance(ledger_families, Mapping) or not isinstance(exclusions, list):
        raise ValueError("quarantine sources are malformed")
    exclusion_text = json.dumps(exclusions, ensure_ascii=False)
    for family, part in expected.items():
        row = ledger_families.get(family)
        if not isinstance(row, Mapping) or str(row.get("part")) != part:
            raise ValueError(f"hard quarantine differs for {part}/{family}")
        if family not in exclusion_text or part not in exclusion_text:
            raise ValueError(f"upload guide does not exclude {part}/{family}")


def validate_v43_summary(summary: Mapping[str, Any], expected_names: list[str]) -> None:
    families = summary.get("families")
    if not isinstance(families, list):
        raise ValueError("v43 families are malformed")
    actual_names = [Path(str(value)).name for value in families]
    if actual_names != expected_names:
        raise ValueError(
            f"v43 family list differs: expected={expected_names}, actual={actual_names}"
        )
    for value in families:
        if not Path(str(value)).is_dir():
            raise ValueError(f"v43 family directory is missing: {value}")
    for flag in (
        "human_playback_approved",
        "publication_approved",
        "bilibili_release_ready",
    ):
        if summary.get(flag) is not False:
            raise ValueError(f"v43 approval flag must remain false: {flag}")


def build(
    *,
    plan_path: Path,
    output_root: Path,
    pointer_path: Path,
    human_root: Path,
) -> Path:
    plan = read_json(plan_path)
    if plan.get("schema") != "magireco-unified-current-production-plan-v1":
        raise ValueError("unexpected unified production plan schema")

    sources = plan.get("sources")
    if not isinstance(sources, Mapping):
        raise ValueError("plan sources are malformed")
    resolved: dict[str, dict[str, Any]] = {}
    values: dict[str, Any] = {}
    for name, binding in sources.items():
        if not isinstance(binding, Mapping):
            raise ValueError(f"source binding is malformed: {name}")
        path, value = validate_bound_json(binding, label=name)
        resolved[name] = {
            "path": str(path),
            "sha256": file_sha256(path),
        }
        values[name] = value

    ledger = values["ledger_summary"]
    guide = values["upload_guide"]
    production_index = values["production_index"]
    material_index = values["material_index"]
    v43_summary = values["v43_batch_summary"]

    expected = plan.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError("plan expected contract is malformed")
    if ledger.get("status") != "ACTIVE_EXHAUSTIVE_LEDGER_BUILT":
        raise ValueError("ledger is not active")
    if guide.get("status") != "UPLOAD_GUIDE_BUILT":
        raise ValueError("upload guide is not built")
    if guide.get("counts") != expected.get("guide_counts"):
        raise ValueError("upload guide counts differ from the plan")
    if int(production_index.get("produced_event_count", -1)) != int(
        ledger.get("produced_event_count", -2)
    ):
        raise ValueError("production index/ledger event counts differ")
    if int(production_index.get("produced_dirinfo_route_count", -1)) != int(
        ledger.get("produced_dirinfo_route_count", -2)
    ):
        raise ValueError("production index/ledger route counts differ")
    if int(material_index.get("covered_event_count", -1)) != int(
        ledger.get("produced_material_event_count", -2)
    ):
        raise ValueError("material index/ledger event counts differ")

    quarantine = expected.get("hard_quarantine")
    if not isinstance(quarantine, Mapping):
        raise ValueError("expected hard quarantine is malformed")
    validate_quarantine(ledger, guide, quarantine)
    expected_v43 = expected.get("v43_families")
    if not isinstance(expected_v43, list):
        raise ValueError("expected v43 families are malformed")
    validate_v43_summary(v43_summary, [str(value) for value in expected_v43])
    guide_verification = validate_guide_files(guide)

    human = plan.get("human_view")
    if not isinstance(human, Mapping):
        raise ValueError("plan human_view is malformed")
    raw_overrides = human.get("filename_overrides", {})
    if not isinstance(raw_overrides, Mapping):
        raise ValueError("plan human filename overrides are malformed")
    filename_overrides = {
        str(key).upper(): str(value) for key, value in raw_overrides.items()
    }
    material_metadata = human.get("bilibili_material_metadata")
    if not isinstance(material_metadata, Mapping):
        raise ValueError("plan material Bilibili metadata is malformed")
    if Path(str(human.get("path", ""))).resolve() != human_root.resolve():
        raise ValueError("human root differs from the plan")
    human_view = build_human_view(
        guide=guide,
        human_root=human_root,
        filename_overrides=filename_overrides,
        material_metadata=material_metadata,
    )

    checkpoint = {
        "schema": "magireco-unified-current-production-checkpoint-v1",
        "status": "ACTIVE_AUTHORITATIVE_CONTROL_PLANE",
        "checkpoint_id": plan["checkpoint_id"],
        "recorded_date": plan["recorded_date"],
        "branch": plan["branch"],
        "production_owner_thread": plan["production_owner_thread"],
        "authority": plan["authority"],
        "production_contract": plan["production_contract"],
        "sources": resolved,
        "counts": {
            "ledger_produced_event_count": ledger["produced_event_count"],
            "ledger_material_covered_event_count": ledger[
                "produced_material_event_count"
            ],
            "ledger_produced_dirinfo_route_count": ledger[
                "produced_dirinfo_route_count"
            ],
            **guide["counts"],
        },
        "guide_verification": guide_verification,
        "human_view": human_view,
        "hard_quarantine": ledger["hard_quarantine_families"],
        "v43_metadata_correction": {
            "family_count": len(v43_summary["families"]),
            "human_playback_approved": False,
            "publication_approved": False,
            "bilibili_release_ready": False,
        },
        "mutation_statement": (
            "No media was copied, re-encoded, reclassified, approved, or uploaded "
            "while building this checkpoint."
        ),
    }

    output_root = output_root.resolve()
    pointer_path = pointer_path.resolve()
    if output_root.exists():
        raise ValueError(f"versioned output root already exists: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = output_root.with_name(output_root.name + f".staging.{os.getpid()}")
    if staging.exists():
        raise ValueError(f"staging root already exists: {staging}")
    staging.mkdir()
    try:
        current_path = staging / "CURRENT_PRODUCTION.json"
        write_json(current_path, checkpoint)
        readme = (
            "# MagiaReco current production control plane\n\n"
            "This is the single current entry point for both Codex tasks.  The "
            "versioned media roots referenced by `UPLOAD_GUIDE.json` remain "
            "immutable; they are not competing production trees.\n\n"
            "- Actual media production owner: `019f9520-0925-7cb0-b494-ab9282a9a3a7`.\n"
            "- Current exhaustive ledger: `production_ledger_v27r1_metadata_fix_20260730`.\n"
            "- Current upload/review guide: `upload_guide_v59r2_unified_20260802`.\n"
            "- This checkpoint does not grant human or publication approval.\n"
            "- P16/ac6003, P17/ac6004, and P18/ac6005 remain quarantined.\n"
            "- Future production must advance the ledger and guide together, then "
            "replace the stable pointer transactionally.\n"
        )
        (staging / "README.md").write_text(readme, encoding="utf-8")
        sums = {
            "schema": "magireco-versioned-output-sha256-v1",
            "files": [
                {
                    "path": name,
                    "sha256": file_sha256(staging / name),
                    "byte_count": (staging / name).stat().st_size,
                }
                for name in ("CURRENT_PRODUCTION.json", "README.md")
            ],
        }
        write_json(staging / "SHA256SUMS.json", sums)
        os.replace(staging, output_root)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    if pointer_path.exists():
        backup = pointer_path.with_name(pointer_path.name + ".previous")
        shutil.copy2(pointer_path, backup)
    pointer = {
        "schema": "magireco-current-production-pointer-v1",
        "status": "ACTIVE",
        "checkpoint_id": plan["checkpoint_id"],
        "checkpoint_root": str(output_root),
        "current_production_index": {
            "path": str(output_root / "CURRENT_PRODUCTION.json"),
            "sha256": file_sha256(output_root / "CURRENT_PRODUCTION.json"),
        },
        "read_this_first": str(output_root / "README.md"),
        "human_upload_and_review_root": str(human_root.resolve()),
    }
    pointer_tmp = pointer_path.with_name(pointer_path.name + f".tmp.{os.getpid()}")
    write_json(pointer_tmp, pointer)
    read_json(pointer_tmp)
    os.replace(pointer_tmp, pointer_path)
    return output_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--pointer", required=True, type=Path)
    parser.add_argument("--human-root", required=True, type=Path)
    args = parser.parse_args()
    output = build(
        plan_path=args.plan,
        output_root=args.output_root,
        pointer_path=args.pointer,
        human_root=args.human_root,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
