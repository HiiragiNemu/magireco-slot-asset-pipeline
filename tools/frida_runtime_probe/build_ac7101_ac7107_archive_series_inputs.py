#!/usr/bin/env python3
"""Build hash-bound series inputs for fourteen independent event archives."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

try:
    from tools.frida_runtime_probe.build_ac7101_ac7107_timing_authority import (
        EVENTS,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import (
        file_sha256,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_ac7101_ac7107_timing_authority import (
        EVENTS,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import (
        file_sha256,
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
DEFAULT_PLAN = (
    REPO_ROOT
    / "tools"
    / "frida_runtime_probe"
    / "series_proposals"
    / "ac7101_ac7107_event_global_archives_v76r3_20260817.json"
)
DEFAULT_OUTPUT = (
    RESEARCH_ROOT / "ac7101_ac7107_event_archive_series_inputs_v1r3_20260817"
)
SCHEMA = "magireco-ac7101-ac7107-event-archives-plan-v1"
SUMMARY_SCHEMA = "magireco-ac7101-ac7107-archive-series-inputs-v1"
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Summary = Join-Path $Root 'SUMMARY.json'
if (-not (Test-Path -LiteralPath $Summary)) { throw 'series input summary missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable archive series inputs can be disabled without touching manifests or media; rerun with -Apply to rename this root.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def binding(path: Path) -> dict[str, object]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def validate_plan(plan: dict) -> dict[str, object]:
    if (
        plan.get("schema") != SCHEMA
        or plan.get("status")
        != "approved_for_bounded_render_human_playback_required"
        or plan.get("native_dimensions") != {"width": 416, "height": 232}
        or plan.get("native_frame_rate") != "30/1"
        or plan.get("audio_profile") != "strict_no_bgm"
        or plan.get("natural_001_to_002_session_proven") is not False
        or plan.get("unresolved_selector_003_remains_blocked") is not True
        or Path(str(plan.get("renderer", ""))).name
        != "render_event_manifest.py"
        or plan.get("human_playback_required") is not True
        or plan.get("publication_approved") is not False
    ):
        raise ValueError("ac7101-ac7107 archive plan contract differs")
    rows = plan.get("events")
    if not isinstance(rows, list) or [row.get("event") for row in rows] != list(EVENTS):
        raise ValueError("ac7101-ac7107 archive event order differs")
    replacement_root = resolve_path(str(plan["replacement_manifest_root"]))
    event_dir = replacement_root / "events"
    for row in rows:
        event = str(row["event"])
        if (
            not str(row.get("title_zh", "")).strip()
            or file_sha256(event_dir / f"{event}.json")
            != str(row.get("manifest_sha256", "")).upper()
        ):
            raise ValueError(f"{event}: replacement manifest binding differs")
    authority = read_json(resolve_path(str(plan["timing_authority"])))
    if (
        authority.get("status") != "PASS"
        or authority.get("event_count") != len(EVENTS)
        or set(authority.get("events", {})) != set(EVENTS)
        or authority.get("human_playback_required") is not True
        or authority.get("publication_approved") is not False
    ):
        raise ValueError("ac7101-ac7107 timing authority differs")
    translation = read_json(resolve_path(str(plan["translation_map"])))
    translations = translation.get("translations")
    required = {
        str(row["text"]).strip()
        for event in EVENTS
        for row in read_json(event_dir / f"{event}.json").get("subtitles", [])
    }
    supplied = {
        str(row.get("ja", "")).strip()
        for row in translations
        if isinstance(row, dict)
    } if isinstance(translations, list) else set()
    if supplied != required:
        raise ValueError("ac7101-ac7107 translation coverage differs")
    speaker_registry = plan.get("speaker_display_registry")
    speaker_overrides = plan.get("speaker_identity_overrides")
    if not isinstance(speaker_registry, dict) or not isinstance(
        speaker_overrides, dict
    ):
        raise ValueError("ac7101-ac7107 speaker identity inputs are missing")
    for label, row in (
        ("speaker display registry", speaker_registry),
        ("speaker identity overrides", speaker_overrides),
    ):
        path = resolve_path(str(row.get("path", "")))
        if file_sha256(path) != str(row.get("sha256", "")).upper():
            raise ValueError(f"ac7101-ac7107 {label} binding differs")
    return {
        "rows": rows,
        "replacement_root": replacement_root,
        "source_bindings": [
            binding(DEFAULT_PLAN),
            binding(resolve_path(str(plan["replacement_summary"]))),
            binding(resolve_path(str(plan["timing_authority"]))),
            binding(resolve_path(str(plan["dirinfo_routes"]))),
            binding(resolve_path(str(plan["translation_map"]))),
            binding(resolve_path(str(plan["subtitle_layout"]))),
            binding(resolve_path(str(speaker_registry["path"]))),
            binding(resolve_path(str(speaker_overrides["path"]))),
            binding(resolve_path(str(plan["font"]))),
            binding(resolve_path(str(plan["renderer"]))),
        ],
    }


def verify_output(output_dir: Path) -> dict:
    summary = read_json(output_dir / "SUMMARY.json")
    if summary.get("schema") != SUMMARY_SCHEMA:
        raise ValueError("archive series input summary schema differs")
    rows = summary.get("archives", [])
    if [row.get("event") for row in rows] != list(EVENTS):
        raise ValueError("archive series input event order differs")
    for row in rows:
        for prefix in ("source_catalog", "series_proposal"):
            path = Path(str(row[f"{prefix}_path"]))
            if file_sha256(path) != row[f"{prefix}_sha256"]:
                raise ValueError(f"{row['event']}: {prefix} SHA-256 differs")
        proposal = read_json(Path(str(row["series_proposal_path"])))
        if (
            proposal.get("natural_session_claimed") is not False
            or proposal.get("event_count") != 1
            or proposal.get("family_state", {}).get("ready_event_names")
            != [row["event"]]
        ):
            raise ValueError(f"{row['event']}: archive proposal boundary differs")
    return {
        "schema": "magireco-ac7101-ac7107-archive-series-inputs-verification-v1",
        "result": "PASS",
        "archive_count": len(rows),
        "family_count": 7,
        "natural_001_to_002_session_proven": False,
        "unresolved_selector_003_remains_blocked": True,
        "human_playback_required": True,
        "publication_approved": False,
        "source_media_modified": False,
    }


def build(plan_path: Path, output_dir: Path) -> None:
    if output_dir.exists():
        raise ValueError(f"immutable series input output already exists: {output_dir}")
    plan = read_json(plan_path)
    if plan_path.resolve() != DEFAULT_PLAN.resolve():
        raise ValueError("archive plan path differs from the hash-bound plan")
    state = validate_plan(plan)
    staging = output_dir.with_name(f".{output_dir.name}.staging-{uuid.uuid4().hex}")
    catalogs = staging / "source_series_catalogs"
    proposals = staging / "archive_series_proposals"
    catalogs.mkdir(parents=True)
    proposals.mkdir(parents=True)
    try:
        catalog_bindings: dict[str, dict[str, object]] = {}
        for family in [f"ac710{i}" for i in range(1, 8)]:
            events = [f"{family}_001", f"{family}_002"]
            path = catalogs / f"{family}.json"
            write_json(
                path,
                {
                    "schema": "magireco-series-editions-v1",
                    "series": family,
                    "status": "passed",
                    "event_count": 2,
                    "family_state": {"ready_event_names": events},
                    "product_scopes": {
                        event: "independent_single_event_archive" for event in events
                    },
                    "natural_session_claims": {event: False for event in events},
                    "ordering_evidence": "DirInfo repeated single-event occurrence grid; no _001 to _002 native-session edge",
                    "unresolved_selector_003_remains_blocked": True,
                },
            )
            staged_binding = binding(path)
            catalog_bindings[family] = {
                **staged_binding,
                "path": str(
                    (output_dir / "source_series_catalogs" / path.name).resolve()
                ),
            }

        rows = []
        replacement_root = Path(str(state["replacement_root"]))
        for plan_row in state["rows"]:
            event = str(plan_row["event"])
            family = event.split("_", 1)[0]
            product = f"{event}_event_archive"
            catalog = catalog_bindings[family]
            proposal_path = proposals / f"{product}.json"
            write_json(
                proposal_path,
                {
                    "schema": "magireco-runtime-exact-event-archive-series-v1",
                    "series": product,
                    "status": "passed",
                    "errors": [],
                    "event_count": 1,
                    "title_zh": plan_row["title_zh"],
                    "ordering": "single exact event; repeated DirInfo occurrences are aliases; no natural-family sequence claim",
                    "product_scope": "independent_single_event_archive",
                    "natural_session_claimed": False,
                    "loop_scope": {
                        "status": "full event archive",
                        "event": event,
                    },
                    "family_state": {
                        "production_manifest_root": str(replacement_root.resolve()),
                        "known_family_events": 1,
                        "ready_family_events": 1,
                        "not_ready_family_events": [],
                        "ready_event_names": [event],
                    },
                    "event_manifest_sha256": {
                        event: str(plan_row["manifest_sha256"]).upper()
                    },
                    "source_series_manifest": {
                        "path": str(catalog["path"]),
                        "sha256": catalog["sha256"],
                        "evidence": "hash-bound family occurrence catalog derived from exact DirInfo boundary and event-global timing authority",
                    },
                    "human_playback_required": True,
                    "bilibili_release_ready": False,
                },
            )
            staged_proposal_binding = binding(proposal_path)
            proposal_binding = {
                **staged_proposal_binding,
                "path": str(
                    (
                        output_dir
                        / "archive_series_proposals"
                        / proposal_path.name
                    ).resolve()
                ),
            }
            rows.append(
                {
                    "event": event,
                    "series": product,
                    "title_zh": plan_row["title_zh"],
                    "source_catalog_path": catalog["path"],
                    "source_catalog_sha256": catalog["sha256"],
                    "series_proposal_path": proposal_binding["path"],
                    "series_proposal_sha256": proposal_binding["sha256"],
                    "event_manifest_sha256": plan_row["manifest_sha256"],
                }
            )
        write_json(
            staging / "SUMMARY.json",
            {
                "schema": SUMMARY_SCHEMA,
                "status": "PASS",
                "archive_count": len(rows),
                "family_count": 7,
                "archives": rows,
                "source_bindings": state["source_bindings"],
                "natural_001_to_002_session_proven": False,
                "unresolved_selector_003_remains_blocked": True,
                "human_playback_required": True,
                "publication_approved": False,
                "source_media_modified": False,
            },
        )
        (staging / "ROLLBACK.ps1").write_text(ROLLBACK_SCRIPT, encoding="utf-8")
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    write_json(output_dir / "VERIFICATION.json", verify_output(output_dir))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if args.verify_only:
        result = verify_output(output_dir)
    else:
        build(args.plan.resolve(), output_dir)
        result = read_json(output_dir / "VERIFICATION.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
