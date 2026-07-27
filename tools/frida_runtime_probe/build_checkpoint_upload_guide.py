#!/usr/bin/env python3
"""Build a hash-bound, per-file Bilibili upload guide for one checkpoint."""

from __future__ import annotations

import argparse
import csv
import json
import re
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_ac0908_reference_showcase import read_json, validate_bound_file
    from .build_independent_scene_release import file_sha256, write_json
except ImportError:  # direct script execution
    from build_ac0908_reference_showcase import (  # type: ignore
        read_json,
        validate_bound_file,
    )
    from build_independent_scene_release import file_sha256, write_json  # type: ignore


PLAN_SCHEMA = "magireco-checkpoint-upload-guide-plan-v1"
GUIDE_SCHEMA = "magireco-checkpoint-upload-guide-v1"
FIELDS = (
    "state",
    "target_bv",
    "subtitle_track",
    "absolute_folder",
    "exact_filename",
    "sha256",
    "suggested_part_name",
    "action",
    "automated_qa_status",
    "human_approval_status",
    "publication_instruction",
    "scope_note",
)
MATERIAL_PART_NAMES = {
    "ac0906_small_kyubey_actions_v1": "小丘比动作素材 ac0906",
    "ac0931_uwasa_battle_intros_v1": "传闻战斗开场素材 ac0931",
    "ac5004_chance_color_titles_v1": "机会颜色标题素材 ac5004",
    "ac8000_next_continue_ui_v1": "下一段与继续界面素材 ac8000",
    "ac8004_shutter_transitions_v1": "快门转场素材 ac8004",
    "ac0912_small_kyubey_3on_guides_v1": "小丘比三停引导素材 ac0912",
    "ac7204_small_result_color_cards_v1": "小尺寸六色结果卡素材 ac7204",
    "ac7204_large_result_color_cards_v1": (
        "大尺寸六色与烟花彩虹结果卡素材 ac7204"
    ),
    "ac4904_su_window_group_01_v1": "环彩羽等五人窗框素材 ac4904",
    "ac4904_su_window_group_02_v1": "鹿目圆等五人窗框素材 ac4904",
    "ac4904_su_window_group_03_v1": "音梦等五人窗框素材 ac4904",
    "ac0914_uwasa_narration_transition_layers_v1": "谣叙事转场素材 ac0914",
    "ac0914_uwasa_outcome_layers_v1": "谣五类十种结果素材 ac0914",
    "ac1103_demae_victory_revival_layers_v1": (
        "出前胜利复活背景与标志素材 ac1103"
    ),
    "ac2201_kuroe_nerae_gameplay_layers_v1": "黑江瞄准玩法素材 ac2201",
    "ac8002_chance_button_prompt_catalog_v1": (
        "五类机会按钮提示素材 ac8002"
    ),
    "ac3102_roulette_battle_visual_catalog_v1": (
        "轮盘战斗玩法视觉素材 ac3102"
    ),
    "ac3103_roulette_color_visual_catalog_v1": (
        "轮盘颜色玩法视觉素材 ac3103"
    ),
    "ac3407_character_reveal_visual_catalog_v1": (
        "角色揭示玩法视觉素材 ac3407"
    ),
    "ac3409_character_reveal_visual_catalog_v1": (
        "角色揭示玩法视觉素材 ac3409"
    ),
    "ac8000_next_story_visual_catalog_v1": (
        "下一段剧情界面视觉素材 ac8000"
    ),
    "ac905x_uwanose_components_416_v1": "上乗せ玩法组件素材 ac905x",
    "ac905x_uwanose_badges_144x160_v1": "上乗せ徽章素材 ac905x",
    "ac905x_uwanose_numbers_128x64_v1": "上乗せ数字素材 ac905x",
    "ac5001_flying_combination_components_416_v1": (
        "角色飞行与合体玩法素材 ac5001"
    ),
    "ac5001_attack_title_component_512x416_v1": (
        "攻击标题效果素材 ac5001"
    ),
    "ac0905_su_gameplay_components_416_v1": "SU玩法组件素材 ac0905",
    "ac0905_su_effect_frames_512x416_v1": "SU效果框素材 ac0905",
    "ac0916_character_action_components_416_v1": (
        "角色变身与决定动作素材 ac0916"
    ),
    "ac0916_text_in_add_components_416x120_v1": (
        "玩法文字入场叠加素材 ac0916"
    ),
    "ac0916_text_effect_components_160x120_v1": (
        "玩法文字循环效果素材 ac0916"
    ),
    "ac7211_character_sequence_components_416_v1": (
        "角色序列动作素材 ac7211"
    ),
    "ac7211_event014_components_512x288_v1": (
        "事件014角色序列素材 ac7211"
    ),
    "ac7211_portrait_standby_component_192x320_v1": (
        "角色立绘待机素材 ac7211"
    ),
    "ac5102_nerae_gameplay_components_416_v1": (
        "瞄准玩法组件素材 ac5102"
    ),
    "ac5102_gyakuosi_indicator_144x56_v1": (
        "逆押提示组件素材 ac5102"
    ),
    "ac2201_kuroe_cu_gameplay_delta_416_v1": (
        "黑江CU瞄准玩法组件素材 ac2201"
    ),
    "ac2201_result_and_target_components_512x416_v1": (
        "成功结果与瞄准文字组件素材 ac2201"
    ),
}
ROUTE_BATCH_SOURCE_NAMES = (
    "v31_ac4902_manifest",
    "v31_ac7206_manifest",
    "v32_ac0908_manifest",
    "v33_ac4903_manifest",
    "v34_ac6007_manifest",
    "v35_ac0911_manifest",
    "v51_ac4902_selector_routes_manifest",
)


def material_part_name(collection: str) -> str:
    return MATERIAL_PART_NAMES.get(collection, collection)


def _bound(
    raw: Mapping[str, Any],
    *,
    label: str,
    plan_dir: Path,
) -> tuple[Path, dict[str, str]]:
    path, snapshot = validate_bound_file(raw, label=label, plan_dir=plan_dir)
    return path, {
        "label": label,
        "path": str(path.resolve()),
        "sha256": str(snapshot["sha256"]).upper(),
    }


def _load_plan_with_bases(
    plan_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Resolve a finite hash-bound overlay chain for successive checkpoints."""

    seen: set[Path] = set()

    def load(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
        resolved = path.resolve()
        if resolved in seen:
            raise ValueError("checkpoint upload-guide base plan cycle")
        seen.add(resolved)
        raw = read_json(resolved)
        if raw.get("base_plan") is None:
            return dict(raw), []
        base_path, base_snapshot = _bound(
            raw["base_plan"],
            label="base checkpoint upload-guide plan",
            plan_dir=resolved.parent,
        )
        base, snapshots = load(base_path)
        plan = dict(base)
        for key, value in raw.items():
            if key == "base_plan":
                continue
            if key in {
                "target_bvs",
                "directories",
                "sources",
                "incremental_story_products",
            }:
                if not isinstance(value, Mapping):
                    raise ValueError(f"upload guide overlay {key} must be an object")
                plan[key] = {**dict(plan.get(key, {})), **dict(value)}
            else:
                plan[key] = value
        return plan, [base_snapshot, *snapshots]

    return load(plan_path)


def _item(
    *,
    path: Path,
    expected_sha256: str,
    state: str,
    target_bv: str,
    subtitle_track: str,
    suggested_part_name: str,
    action: str,
    automated_qa_status: str,
    human_approval_status: str,
    publication_instruction: str,
    scope_note: str,
) -> dict[str, str]:
    path = path.resolve()
    expected = expected_sha256.upper()
    if not path.is_file() or file_sha256(path) != expected:
        raise ValueError(f"upload-guide file binding differs: {path}")
    return {
        "state": state,
        "target_bv": target_bv,
        "subtitle_track": subtitle_track,
        "absolute_folder": str(path.parent),
        "exact_filename": path.name,
        "sha256": expected,
        "suggested_part_name": suggested_part_name,
        "action": action,
        "automated_qa_status": automated_qa_status,
        "human_approval_status": human_approval_status,
        "publication_instruction": publication_instruction,
        "scope_note": scope_note,
    }


def _target(plan: Mapping[str, Any], name: str) -> str:
    targets = plan.get("target_bvs")
    if not isinstance(targets, Mapping) or not isinstance(targets.get(name), str):
        raise ValueError(f"upload guide lacks target BV {name}")
    return str(targets[name])


def _owner_approved_mixed_chapter_items(
    *,
    attestation: Mapping[str, Any],
    root: Path,
    specs: Sequence[Mapping[str, Any]],
    plan: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Bind exact owner-played v22 chapter files without approving siblings."""

    decisions = attestation.get("decisions")
    releases = attestation.get("releases")
    if (
        attestation.get("schema") != "magireco-owner-playback-attestation-v1"
        or attestation.get("attestation_id")
        != "mixed_composition_4_chapters_owner_playback_20260718"
        or not isinstance(decisions, Mapping)
        or decisions.get("HUMAN_PLAYBACK_APPROVED") is not True
        or not isinstance(releases, list)
    ):
        raise ValueError("mixed-composition owner attestation identity differs")
    by_id = {
        str(row.get("release_id", "")): row
        for row in releases
        if isinstance(row, Mapping)
    }
    if len(by_id) != len(releases):
        raise ValueError("mixed-composition owner attestation release IDs differ")
    spec_ids = [str(spec.get("release_id", "")) for spec in specs]
    if len(spec_ids) != len(set(spec_ids)) or set(spec_ids) != set(by_id):
        raise ValueError("mixed-composition upload-guide release set differs")

    items: list[dict[str, str]] = []
    support_names = {
        "subtitle_sha256": ("subtitles", "{id}__zh_dialogue.srt"),
        "manifest_sha256": ("manifests", "chapter_review_manifest.json"),
        "qa_sha256": ("qa", "automated_qa.json"),
        "ready_sha256": ("", "BATCH_REVIEW_READY.json"),
    }
    for spec in specs:
        release_id = str(spec["release_id"])
        release = by_id[release_id]
        release_root = root / release_id
        video = release_root / "video" / f"{release_id}.mp4"
        for hash_key, (folder, filename_pattern) in support_names.items():
            support = release_root / folder / filename_pattern.format(id=release_id)
            expected = str(release.get(hash_key, "")).upper()
            if not support.is_file() or file_sha256(support) != expected:
                raise ValueError(
                    f"owner-approved mixed chapter support binding differs: {support}"
                )
        items.append(
            _item(
                path=video,
                expected_sha256=str(release.get("video_sha256", "")),
                state="ready_to_upload",
                target_bv=_target(plan, str(spec["target_bv_key"])),
                subtitle_track="ZH burned-in",
                suggested_part_name=str(spec["suggested_part_name"]),
                action=str(spec["action"]),
                automated_qa_status="passed_at_v22_checkpoint",
                human_approval_status="exact_file_owner_playback_approved",
                publication_instruction="UPLOAD ALLOWED FOR THIS EXACT HASH",
                scope_note=(
                    "The project owner played this exact v22 ZH chapter. Approval "
                    "does not transfer to none/JA, rerenders, or extracted events."
                ),
            )
        )
    return items


def _manifest_media(
    value: object,
    *,
    family_root: Path,
    family: str,
    product_prefix: str = "",
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        artifacts = value.get("artifacts")
        if isinstance(artifacts, Mapping):
            product = str(
                value.get("title")
                or value.get("product_id")
                or value.get("route_id")
                or value.get("release_id")
                or product_prefix
                or family
            )
            for edition in ("none", "ja", "zh"):
                raw = artifacts.get(f"video_{edition}")
                if (
                    not isinstance(raw, Mapping)
                    or not raw.get("path")
                    or not raw.get("sha256")
                ):
                    continue
                path = Path(str(raw["path"]))
                if not path.is_absolute():
                    path = family_root / path
                output.append(
                    {
                        "family": family,
                        "product": product,
                        "edition": edition,
                        "path": str(path.resolve()),
                        "sha256": str(raw["sha256"]).upper(),
                    }
                )
        media_groups = [
            raw
            for raw in (value.get("media"), value.get("editions"))
            if isinstance(raw, Mapping)
        ]
        for media in media_groups:
            product = str(
                value.get("title")
                or value.get("product_id")
                or value.get("route_id")
                or product_prefix
                or family
            )
            for edition in ("none", "ja", "zh"):
                raw = media.get(edition)
                if not isinstance(raw, Mapping) or not raw.get("path") or not raw.get("sha256"):
                    continue
                path = Path(str(raw["path"]))
                if not path.is_absolute():
                    path = family_root / path
                output.append(
                    {
                        "family": family,
                        "product": product,
                        "edition": edition,
                        "path": str(path.resolve()),
                        "sha256": str(raw["sha256"]).upper(),
                    }
                )
        for key, child in value.items():
            if key not in {
                "media",
                "editions",
                "source_snapshots",
                "excluded_dirinfo_rows",
                "route_failures",
            }:
                output.extend(
                    _manifest_media(
                        child,
                        family_root=family_root,
                        family=family,
                        product_prefix=product_prefix,
                    )
                )
    elif isinstance(value, list):
        for child in value:
            output.extend(
                _manifest_media(
                    child,
                    family_root=family_root,
                    family=family,
                    product_prefix=product_prefix,
                )
            )
    unique: dict[str, dict[str, str]] = {}
    for row in output:
        unique[str(Path(row["path"]).resolve()).casefold()] = row
    return list(unique.values())


def _batch_target(plan: Mapping[str, Any], family: str, product: str) -> str:
    if family == "ac0908" and "参考合集" in product:
        return _target(plan, "ac0908_reference_showcase")
    names = {
        "ac0911": "ac0911_route_catalog",
        "ac0908": "ac0908_route_catalog",
        "ac4902": "ac4902_route_catalog",
        "ac4903": "ac4903_route_catalog",
        "ac6007": "ac6007_route_catalog",
        "ac7206": "ac7206_route_catalog",
        "ac7210": "story_collection",
    }
    return _target(plan, names.get(family, "future_catalog"))


def _track_target(plan: Mapping[str, Any], family: str, edition: str, product: str) -> str:
    if edition == "ja":
        return _target(plan, "future_ja_catalog")
    return _batch_target(plan, family, product)


def build(*, plan_path: Path, output_root: Path) -> Path:
    plan, base_plan_snapshots = _load_plan_with_bases(plan_path)
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "active_upload_checkpoint"
        or not isinstance(plan.get("explicit_exclusions"), list)
    ):
        raise ValueError("unsupported checkpoint upload-guide plan")
    snapshots: list[dict[str, str]] = [
        {
            "label": "checkpoint upload-guide plan",
            "path": str(plan_path.resolve()),
            "sha256": file_sha256(plan_path),
        }
    ]
    snapshots.extend(base_plan_snapshots)
    source_paths: dict[str, Path] = {}
    for name, raw in plan["sources"].items():
        path, snapshot = _bound(
            raw,
            label=f"upload guide source {name}",
            plan_dir=plan_path.parent,
        )
        source_paths[name] = path
        snapshots.append(snapshot)

    items: list[dict[str, str]] = []

    uploaded = read_json(source_paths["owner_uploaded_exact_zh"])
    uploaded_root = Path(str(plan["directories"]["uploaded_zh"])).resolve()
    if uploaded.get("status") != "uploaded_by_project_owner":
        raise ValueError("owner-uploaded exact ZH source identity differs")
    for raw in uploaded.get("files", []):
        path = uploaded_root / str(raw["filename"])
        items.append(
            _item(
                path=path,
                expected_sha256=str(raw["sha256"]),
                state="already_uploaded",
                target_bv=_target(plan, "story_collection"),
                subtitle_track="ZH burned-in",
                suggested_part_name=str(raw["filename"]).removesuffix(".mp4"),
                action="none_already_uploaded_do_not_repeat",
                automated_qa_status="passed_at_original_checkpoint",
                human_approval_status="exact_file_owner_playback_approved_and_uploaded",
                publication_instruction="DO NOT REUPLOAD",
                scope_note="Approval and upload history bind only this exact ZH MP4 hash.",
            )
        )

    corrections = read_json(source_paths["owner_approved_corrections"])
    corrections_root = Path(str(plan["directories"]["corrections_review_now"])).resolve()
    if corrections.get("status") != "project_owner_playback_approved":
        raise ValueError("owner-approved correction source identity differs")
    approved_route_zh: dict[str, str] = {}
    for raw in corrections.get("files", []):
        part = str(raw["part"])
        edition = str(raw["edition"])
        if part.startswith("ac0908 route "):
            approved_route_zh[str(raw["filename"])] = str(raw["sha256"]).upper()
            continue
        path = corrections_root / str(raw["filename"])
        target = (
            _target(plan, "story_collection")
            if edition == "zh"
            else _target(plan, "future_ja_catalog")
        )
        items.append(
            _item(
                path=path,
                expected_sha256=str(raw["sha256"]),
                state="ready_to_upload",
                target_bv=target,
                subtitle_track=f"{edition.upper()} burned-in",
                suggested_part_name=str(raw["filename"]).removesuffix(".mp4"),
                action=(
                    "append_missing_story_part"
                    if edition == "zh"
                    else "append_to_future_ja_track_bv"
                ),
                automated_qa_status="passed",
                human_approval_status="exact_file_owner_playback_approved",
                publication_instruction="UPLOAD ALLOWED FOR THIS EXACT HASH",
                scope_note=(
                    "P12 is a route-aware deduplicated showcase; P23 carries the "
                    "owner-corrected 黑江/黑 identities."
                ),
            )
        )

    ac0908_path = source_paths["v30_ac0908_manifest"]
    ac0908 = read_json(ac0908_path)
    ac0908_root = ac0908_path.parent.parent
    if ac0908.get("status") != "OWNER_APPROVED_FULL_PRODUCTION_READY":
        raise ValueError("v30 ac0908 manifest identity differs")
    for row in _manifest_media(
        ac0908,
        family_root=ac0908_root,
        family="ac0908",
    ):
        path = Path(row["path"])
        edition = row["edition"]
        exact_route_approved = (
            edition == "zh"
            and (
                path.name in approved_route_zh
                and approved_route_zh[path.name] == row["sha256"]
            )
        )
        exact_showcase_approved = (
            edition == "zh"
            and "参考合集" in path.name
            and row["sha256"]
            == str(ac0908["showcase"]["approved_zh_hardlink"]["sha256"]).upper()
        )
        ready = exact_route_approved or exact_showcase_approved
        items.append(
            _item(
                path=path,
                expected_sha256=row["sha256"],
                state="ready_to_upload" if ready else "human_playback_required",
                target_bv=(
                    _target(plan, "ac0908_reference_showcase")
                    if "参考合集" in path.name
                    else _track_target(
                        plan, "ac0908", edition, row["product"]
                    )
                ),
                subtitle_track=(
                    "no burned-in subtitles"
                    if edition == "none"
                    else f"{edition.upper()} burned-in"
                ),
                suggested_part_name=path.stem,
                action=(
                    "create_or_append_route_part"
                    if ready and "参考合集" not in path.name
                    else (
                        "create_separate_reference_showcase_bv"
                        if ready
                        else "hold_for_owner_playback"
                    )
                ),
                automated_qa_status="passed",
                human_approval_status=(
                    "exact_file_owner_playback_approved"
                    if ready
                    else "not_approved_for_this_edition"
                ),
                publication_instruction=(
                    "UPLOAD ALLOWED FOR THIS EXACT HASH"
                    if ready
                    else "DO NOT UPLOAD YET"
                ),
                scope_note=(
                    "Six routes are mutually exclusive independent segments. The "
                    "reference showcase is an edited cross-route product, not one session."
                ),
            )
        )

    ac7210_path = source_paths["v30_ac7210_manifest"]
    ac7210 = read_json(ac7210_path)
    ac7210_root = ac7210_path.parent.parent
    if ac7210.get("status") != "OWNER_APPROVED_PRESENTATION_FULL_PRODUCTION_COMPLETE":
        raise ValueError("v30 ac7210 manifest identity differs")
    for row in _manifest_media(
        ac7210,
        family_root=ac7210_root,
        family="ac7210",
    ):
        path = Path(row["path"])
        ready = row["edition"] == "zh"
        items.append(
            _item(
                path=path,
                expected_sha256=row["sha256"],
                state="ready_to_upload" if ready else "human_playback_required",
                target_bv=(
                    _target(plan, "story_collection")
                    if ready
                    else _target(plan, "future_ja_catalog")
                    if row["edition"] == "ja"
                    else _target(plan, "ac7210_route_supplement")
                ),
                subtitle_track=(
                    "no burned-in subtitles"
                    if row["edition"] == "none"
                    else f"{row['edition'].upper()} burned-in"
                ),
                suggested_part_name=path.stem,
                action=(
                    "append_after_existing_P25"
                    if ready
                    else "hold_for_owner_playback"
                ),
                automated_qa_status="passed",
                human_approval_status=(
                    "exact_ZH_file_owner_playback_approved"
                    if ready
                    else "sibling_edition_not_playback_approved"
                ),
                publication_instruction=(
                    "UPLOAD ALLOWED FOR THIS EXACT HASH"
                    if ready
                    else "DO NOT UPLOAD YET"
                ),
                scope_note="Only DirInfo rows 0 and 1 are in this current product.",
            )
        )

    for source_name in ROUTE_BATCH_SOURCE_NAMES:
        if source_name not in source_paths:
            continue
        manifest_path = source_paths[source_name]
        value = read_json(manifest_path)
        family = str(value.get("family") or value.get("series") or "")
        for row in _manifest_media(
            value,
            family_root=manifest_path.parent,
            family=family,
        ):
            path = Path(row["path"])
            items.append(
                _item(
                    path=path,
                    expected_sha256=row["sha256"],
                    state="human_playback_required",
                    target_bv=_track_target(
                        plan, family, row["edition"], row["product"]
                    ),
                    subtitle_track=(
                        "no burned-in subtitles"
                        if row["edition"] == "none"
                        else f"{row['edition'].upper()} burned-in"
                    ),
                    suggested_part_name=path.stem,
                    action="hold_for_owner_playback",
                    automated_qa_status="passed",
                    human_approval_status="exact_output_not_yet_playback_approved",
                    publication_instruction="DO NOT UPLOAD YET",
                    scope_note=(
                        "Source/production contract is approved or evidence-ready, "
                        "but approval does not automatically transfer to this exact output."
                    ),
                )
            )

    incremental_story_specs = plan.get("incremental_story_products")
    if incremental_story_specs is not None:
        if (
            "current_production_index" not in source_paths
            or not isinstance(incremental_story_specs, Mapping)
            or not incremental_story_specs
        ):
            raise ValueError(
                "incremental story products require current production index"
            )
        current_index = read_json(source_paths["current_production_index"])
        if (
            current_index.get("schema")
            != "magireco-current-production-manifest-index-v1"
            or not isinstance(current_index.get("manifests"), list)
        ):
            raise ValueError("current production index identity differs")
        selected_incremental: dict[str, Mapping[str, Any]] = {}
        for raw in current_index["manifests"]:
            if not isinstance(raw, Mapping):
                raise ValueError("current production index row is malformed")
            family = str(raw.get("family", ""))
            spec = incremental_story_specs.get(family)
            if spec is None:
                continue
            if not isinstance(spec, Mapping):
                raise ValueError(f"incremental story spec differs: {family}")
            if str(raw.get("root_label", "")) != str(
                spec.get("root_label", "")
            ):
                continue
            if family in selected_incremental:
                raise ValueError(
                    f"duplicate incremental story current manifest: {family}"
                )
            selected_incremental[family] = raw
        if set(selected_incremental) != set(incremental_story_specs):
            raise ValueError(
                "incremental story current manifest set differs: "
                f"expected={sorted(incremental_story_specs)} "
                f"actual={sorted(selected_incremental)}"
            )
        for family, spec in incremental_story_specs.items():
            raw = selected_incremental[family]
            manifest_path = Path(str(raw.get("manifest_path", ""))).resolve()
            expected_manifest_sha = str(
                raw.get("manifest_sha256", "")
            ).upper()
            if (
                not manifest_path.is_file()
                or file_sha256(manifest_path) != expected_manifest_sha
            ):
                raise ValueError(
                    f"incremental story manifest binding differs: {family}"
                )
            value = read_json(manifest_path)
            if (
                value.get("schema")
                != "magireco-no-bgm-story-family-editions-v1"
                or value.get("status") != "AUTOMATED_QA_PASSED"
                or value.get("family") != family
                or value.get("ordered_events") != [family]
                or value.get("audio_profile") != "no_bgm"
                or value.get("bgm_policy") != "intentionally_excluded"
                or value.get("human_review_status") != "pending"
                or value.get("publishable") is not False
            ):
                raise ValueError(
                    f"incremental story release contract differs: {family}"
                )
            rows = _manifest_media(
                value,
                family_root=manifest_path.parent.parent,
                family=family,
            )
            if (
                len(rows) != 3
                or {row["edition"] for row in rows}
                != {"none", "ja", "zh"}
            ):
                raise ValueError(
                    f"incremental story edition set differs: {family}"
                )
            no_dialogue_aliases = spec.get("no_dialogue_aliases") is True
            if no_dialogue_aliases and (
                value.get("dialogue_cue_count") != 0
                or set(value.get("verified_no_event_audio_events", []))
                != {family}
                or any(
                    value.get("subtitle_profiles", {}).get(edition)
                    != "no_dialogue_cross_target_alias"
                    for edition in ("ja", "zh")
                )
                or len({row["sha256"] for row in rows}) != 1
            ):
                raise ValueError(
                    f"incremental no-dialogue alias contract differs: {family}"
                )
            bounded_product_scope = str(
                spec.get("bounded_product_scope", "")
            ).strip()
            if bounded_product_scope and (
                value.get("product_scope") != bounded_product_scope
                or value.get("natural_session_claimed") is not False
                or value.get("loop_scope", {}).get("policy")
                != "intro_then_exactly_one_complete_source_loop"
                or value.get("loop_scope", {}).get(
                    "runtime_loop_count_claimed"
                )
                is not False
            ):
                raise ValueError(
                    f"incremental bounded product contract differs: {family}"
                )
            title = str(spec.get("title", "")).strip()
            if not title:
                raise ValueError(
                    f"incremental story title is empty: {family}"
                )
            product_category = str(
                spec.get("product_category", "story")
            ).strip()
            if product_category not in {"story", "gameplay_announcement"}:
                raise ValueError(
                    f"incremental product category differs: {family}"
                )
            target_keys = spec.get("target_bv_keys")
            if target_keys is not None and (
                not isinstance(target_keys, Mapping)
                or set(target_keys) != {"none", "ja", "zh"}
                or any(
                    not str(target_keys[edition]).strip()
                    for edition in ("none", "ja", "zh")
                )
            ):
                raise ValueError(
                    f"incremental product target keys differ: {family}"
                )
            for row in rows:
                edition = row["edition"]
                path = Path(row["path"])
                suggested = f"{title} {family}"
                if edition == "ja":
                    suggested += "__ja"
                elif edition == "zh":
                    suggested += " 中文版"
                target_key = (
                    str(target_keys[edition])
                    if target_keys is not None
                    else {
                        "none": "none_collection",
                        "ja": "future_ja_catalog",
                        "zh": "story_collection",
                    }[edition]
                )
                items.append(
                    _item(
                        path=path,
                        expected_sha256=row["sha256"],
                        state="human_playback_required",
                        target_bv=_target(plan, target_key),
                        subtitle_track=(
                            "no burned-in subtitles; exact no-dialogue alias"
                            if no_dialogue_aliases
                            else "no burned-in subtitles"
                            if edition == "none"
                            else f"{edition.upper()} burned-in"
                        ),
                        suggested_part_name=suggested,
                        action="hold_for_owner_playback",
                        automated_qa_status=(
                            "passed_bounded_profile_product_no_bgm"
                            if bounded_product_scope
                            else "passed_event_exact_no_bgm"
                        ),
                        human_approval_status=(
                            "exact_output_not_yet_playback_approved"
                        ),
                        publication_instruction="DO NOT UPLOAD YET",
                        scope_note=(
                            (
                                "Finite native-size profile-material product: "
                                "exact intro plus exactly one complete source "
                                "loop. It is not a natural runtime session and "
                                "does not claim a runtime loop count. Current "
                                "direct, child-Z2D and subtitle catalogs prove "
                                "zero event audio/subtitle rows; none/JA/ZH are "
                                "legal cross-target hardlink aliases."
                            )
                            if bounded_product_scope
                            else (
                                "Independent exact-silent native-size gameplay "
                                "or announcement route bound to one DirInfo row. "
                                "Sibling routes are mutually independent and "
                                "must not be concatenated as a story or natural "
                                "gameplay session. Current direct, child-Z2D and "
                                "subtitle catalogs prove zero event audio or "
                                "subtitle rows."
                            )
                            if product_category == "gameplay_announcement"
                            else (
                                "Independent event-exact native-size product "
                                "bound to one exact DirInfo row. Current direct, "
                                "child-Z2D and subtitle catalogs prove zero event "
                                "audio/subtitle rows; none/JA/ZH are legal "
                                "cross-target hardlink aliases of one exact hash."
                            )
                            if no_dialogue_aliases
                            else (
                                "Independent event-exact native-size story product "
                                "bound to one exact DirInfo row. It is not claimed "
                                "as a complete natural family or combined route."
                            )
                        ),
                    )
                )

    material_index_source = (
        "current_material_index"
        if "current_material_index" in source_paths
        else "v36_material_index"
        if "v36_material_index" in source_paths
        else ""
    )
    if material_index_source:
        material_index = read_json(source_paths[material_index_source])
        if (
            material_index.get("schema")
            != "magireco-current-material-collection-index-v1"
        ):
            raise ValueError("v36 material index identity differs")
        for collection in material_index.get("collections", []):
            if not isinstance(collection, Mapping):
                raise ValueError("v36 material index collection is malformed")
            path = Path(str(collection.get("output_path", "")))
            collection_name = str(collection.get("collection", ""))
            dimension_match = re.search(
                r"__(?P<width>[0-9]+)x(?P<height>[0-9]+)_",
                path.name,
            )
            if dimension_match is None:
                raise ValueError(
                    f"material output name lacks native dimensions: {path.name}"
                )
            native_dimensions = (
                f"{dimension_match.group('width')}x"
                f"{dimension_match.group('height')}"
            )
            material_target_bv = (
                _target(plan, "material_collection_catalog")
                if native_dimensions == "416x232"
                else (
                    "新建：MagiaReco Slot 原生"
                    f"{native_dimensions}玩法／素材合集 BV"
                )
            )
            items.append(
                _item(
                    path=path,
                    expected_sha256=str(collection.get("output_sha256", "")),
                    state="human_playback_required",
                    target_bv=material_target_bv,
                    subtitle_track="visual-only; no audio; no burned-in subtitles",
                    suggested_part_name=material_part_name(collection_name),
                    action="hold_for_owner_material_playback",
                    automated_qa_status="passed_visual_only_review_contract",
                    human_approval_status="not_yet_playback_approved",
                    publication_instruction="DO NOT UPLOAD YET",
                    scope_note=(
                        f"Native {native_dimensions} visual material collection; "
                        "not clean story, not a native route, and no audio "
                        "semantics claimed."
                    ),
                )
            )

    if "owner_approved_mixed_chapters" in source_paths:
        specs = plan.get("approved_mixed_chapter_parts")
        if not isinstance(specs, list):
            raise ValueError("upload guide lacks approved mixed-chapter part specs")
        items.extend(
            _owner_approved_mixed_chapter_items(
                attestation=read_json(
                    source_paths["owner_approved_mixed_chapters"]
                ),
                root=Path(
                    str(plan["directories"]["approved_mixed_chapters"])
                ).resolve(),
                specs=specs,
                plan=plan,
            )
        )

    keys = [(row["absolute_folder"].casefold(), row["exact_filename"].casefold()) for row in items]
    if len(keys) != len(set(keys)):
        raise RuntimeError("upload guide contains duplicate exact files")
    if any("superseded" in (folder + filename) for folder, filename in keys):
        raise RuntimeError("superseded media entered the upload guide")

    destination = output_root.resolve()
    if destination.exists():
        raise FileExistsError(f"versioned upload guide exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        with (staging / "UPLOAD_GUIDE.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(items)
        guide = {
            "schema": GUIDE_SCHEMA,
            "status": "UPLOAD_GUIDE_BUILT",
            "checkpoint_id": plan["checkpoint_id"],
            "target_bvs": plan["target_bvs"],
            "counts": {
                "already_uploaded": sum(row["state"] == "already_uploaded" for row in items),
                "ready_to_upload": sum(row["state"] == "ready_to_upload" for row in items),
                "human_playback_required": sum(
                    row["state"] == "human_playback_required" for row in items
                ),
                "explicit_exclusions": len(plan["explicit_exclusions"]),
                "total_exact_files": len(items),
            },
            "items": items,
            "explicit_exclusions": plan["explicit_exclusions"],
            "source_snapshots": snapshots,
            "codex_upload_performed": False,
        }
        write_json(staging / "UPLOAD_GUIDE.json", guide)

        sections = [
            "# MagiaReco Slot 本轮上传指南",
            "",
            "Codex 不执行上传。本指南只允许标为 `ready_to_upload` 的精确文件与 SHA-256；"
            "`human_playback_required`、隔离项和 superseded 审计项均禁止投稿。",
            "",
            f"- 已投稿且不要重复：{guide['counts']['already_uploaded']} 个",
            f"- 现在可投稿：{guide['counts']['ready_to_upload']} 个",
            f"- 必须先人工播放：{guide['counts']['human_playback_required']} 个",
            f"- 明确排除：{guide['counts']['explicit_exclusions']} 项",
            "",
            "## 现在可投稿",
            "",
            "| 目标 BV | 字幕轨 | 绝对文件夹 | 精确文件名 | 建议分P名 | 动作 | 自动QA | 人工批准 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in items:
            if row["state"] != "ready_to_upload":
                continue
            sections.append(
                "| {target_bv} | {subtitle_track} | `{absolute_folder}` | "
                "`{exact_filename}` | {suggested_part_name} | {action} | "
                "{automated_qa_status} | {human_approval_status} |".format(**row)
            )
        sections.extend(
            [
                "",
                "## 已投稿：不要重复",
                "",
            ]
        )
        for row in items:
            if row["state"] == "already_uploaded":
                sections.append(
                    f"- `{row['absolute_folder']}\\{row['exact_filename']}` "
                    f"SHA-256 `{row['sha256']}`"
                )
        sections.extend(
            [
                "",
                "## 必须先人工播放",
                "",
            ]
        )
        for row in items:
            if row["state"] == "human_playback_required":
                sections.append(
                    f"- [{row['subtitle_track']}] `{row['absolute_folder']}\\"
                    f"{row['exact_filename']}` → {row['target_bv']}；"
                    f"建议分P `{row['suggested_part_name']}`；当前禁止上传。"
                )
        sections.extend(["", "## 明确排除", ""])
        for row in plan["explicit_exclusions"]:
            sections.append(
                f"- **{row['scope']}**：{row['disposition']}；{row['reason']}"
            )
        (staging / "UPLOAD_GUIDE.md").write_text(
            "\n".join(sections) + "\n", encoding="utf-8"
        )
        hashes = [
            {
                "path": path.name,
                "sha256": file_sha256(path),
                "byte_count": path.stat().st_size,
            }
            for path in sorted(staging.iterdir())
            if path.is_file() and path.name != "SHA256SUMS.json"
        ]
        write_json(
            staging / "SHA256SUMS.json",
            {
                "schema": "magireco-versioned-output-sha256-v1",
                "files": hashes,
            },
        )
        staging.replace(destination)
        return destination
    except BaseException:
        import shutil

        shutil.rmtree(staging, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination = build(
        plan_path=args.plan.resolve(),
        output_root=args.output_root.resolve(),
    )
    value = read_json(destination / "UPLOAD_GUIDE.json")
    print(
        json.dumps(
            {
                "destination": str(destination),
                "counts": value["counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
