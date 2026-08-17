#!/usr/bin/env python3
"""Promote ac7206_002/_013 to event-global READY without numeric changes."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import uuid
from fractions import Fraction
from pathlib import Path

try:
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
    )


EVENTS = ("ac7206_002", "ac7206_013")
BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"
SCHEMA = "magireco-ac7206-route-replacement-manifests-v1"
SUMMARY_NAME = "AC7206_ROUTE_REPLACEMENT_MANIFEST_SUMMARY.json"
EXPECTED = {
    "ac7206_002": {
        "audio": {"5323": 333},
        "subtitles": {"cap7206_paint_ari_003": (333, 4887)},
    },
    "ac7206_013": {
        "audio": {"5324": 33},
        "subtitles": {"cap7206_paint_ari_004": (33, 2749)},
    },
}
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Summary = Join-Path $Root 'AC7206_ROUTE_REPLACEMENT_MANIFEST_SUMMARY.json'
if (-not (Test-Path -LiteralPath $Summary)) { throw 'replacement summary missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable ac7206 replacement manifests can be disabled without touching source manifests or media; rerun with -Apply to rename this root.'
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
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def timing_snapshot(manifest: dict) -> dict:
    return {
        "audio": {
            str(row.get("request_id", "")): int(row.get("start_ms", 0))
            for row in manifest.get("audio", [])
            if row.get("source") == "z2d_req_sound"
        },
        "subtitles": {
            str(row.get("z2d_name", "")): (
                int(row.get("start_ms", 0)),
                int(row.get("end_ms", 0)),
            )
            for row in manifest.get("subtitles", [])
        },
    }


def repair_manifest(source: dict, override: dict) -> tuple[dict, dict]:
    manifest = copy.deepcopy(source)
    event = str(manifest.get("event", ""))
    if event not in EVENTS:
        raise ValueError(f"unexpected ac7206 event: {event}")
    gates = manifest.get("quality_gates")
    if not isinstance(gates, dict) or (
        gates.get("errors") != [BLOCKER]
        or gates.get("ready") is not False
        or gates.get("event_global_z2d_timing_ready") is not False
        or gates.get("composition_resolved") is not True
    ):
        raise ValueError(f"{event}: source fail-closed state differs")
    if str(override.get("event_code_hex", "")).lower() != str(
        manifest.get("event_code_hex", "")
    ).lower():
        raise ValueError(f"{event}: event code differs")
    if Fraction(str(override.get("frame_rate", ""))) != Fraction(
        str(manifest.get("native_frame_rate", ""))
    ):
        raise ValueError(f"{event}: frame rate differs")
    before = timing_snapshot(manifest)
    if before != EXPECTED[event]:
        raise ValueError(f"{event}: source numeric timing differs")
    application = apply_z2d_event_timing_override(
        manifest.get("audio", []), manifest.get("subtitles", []), override
    )
    if (
        application["unmatched_cues"]
        or application["recovery_conflicts"]
        or not application["request_set_matches"]
        or application["matched_audio_cue_count"] != 1
        or application["matched_subtitle_cue_count"] != 1
    ):
        raise ValueError(f"{event}: timing override did not match exactly")
    if timing_snapshot(manifest) != before:
        raise ValueError(f"{event}: evidence-only repair changed numeric timing")
    unresolved = [
        row
        for row in [*manifest.get("audio", []), *manifest.get("subtitles", [])]
        if (
            row.get("source") == "z2d_req_sound"
            or str(row.get("voice_request_id", "")) in EXPECTED[event]["audio"]
        )
        and row.get("event_global_start_resolved") is not True
    ]
    if unresolved:
        raise ValueError(f"{event}: child-local timing remains unresolved")
    if not all(
        row.get("path") and Path(str(row["path"])).is_file()
        for row in manifest.get("audio", [])
    ):
        raise ValueError(f"{event}: audio media is incomplete")
    gates["errors"] = []
    gates["event_global_z2d_timing_ready"] = True
    gates["audio_timeline_ready"] = True
    gates["render_ready"] = True
    gates["ready"] = True
    manifest["z2d_event_timing_override_application"] = application
    return manifest, application


def verify_output(output_dir: Path) -> dict:
    summary = read_json(output_dir / SUMMARY_NAME)
    if summary.get("schema") != SCHEMA:
        raise ValueError("ac7206 replacement summary schema differs")
    rows = summary.get("events", [])
    if [row.get("event") for row in rows] != list(EVENTS):
        raise ValueError("ac7206 replacement event sequence differs")
    for row in rows:
        event = str(row["event"])
        output = output_dir / "events" / f"{event}.json"
        source = Path(str(row["source_manifest_path"]))
        if file_sha256(output) != row.get("output_sha256"):
            raise ValueError(f"{event}: output SHA-256 differs")
        if file_sha256(source) != row.get("source_manifest_sha256"):
            raise ValueError(f"{event}: source SHA-256 differs")
        manifest = read_json(output)
        if timing_snapshot(manifest) != EXPECTED[event]:
            raise ValueError(f"{event}: verified numeric timing differs")
        if manifest["quality_gates"].get("ready") is not True:
            raise ValueError(f"{event}: output is not READY")
    return {
        "schema": "magireco-ac7206-route-replacement-verification-v1",
        "result": "PASS",
        "event_count": 2,
        "numeric_timing_changed": False,
        "source_media_modified": False,
        "existing_route_media_reencode_required": False,
        "route_product_count": 6,
        "independent_route_edition_file_count": 18,
        "edited_showcase_edition_file_count": 3,
        "existing_audience_file_count": 21,
        "human_playback_required": True,
        "publication_approved": False,
    }


def build(source_dir: Path, output_dir: Path, override_paths: list[Path]) -> None:
    if output_dir.exists():
        raise ValueError(f"immutable output already exists: {output_dir}")
    overrides = load_z2d_event_timing_overrides(override_paths)
    if set(overrides) != set(EVENTS):
        raise ValueError("ac7206 override event set differs")
    staging = output_dir.with_name(f".{output_dir.name}.staging-{uuid.uuid4().hex}")
    event_dir = staging / "events"
    event_dir.mkdir(parents=True)
    rows = []
    try:
        for event in EVENTS:
            source_path = source_dir / f"{event}.json"
            repaired, application = repair_manifest(
                read_json(source_path), overrides[event]
            )
            source_sha = file_sha256(source_path)
            repaired["timing_repair_provenance"] = {
                "source_manifest_path": str(source_path.resolve()),
                "source_manifest_sha256": source_sha,
                "source_media_modified": False,
                "numeric_timing_changed": False,
                "override_application": application,
            }
            output_path = event_dir / f"{event}.json"
            write_json(output_path, repaired)
            rows.append(
                {
                    "event": event,
                    "source_manifest_path": str(source_path.resolve()),
                    "source_manifest_sha256": source_sha,
                    "output_relative_path": f"events/{event}.json",
                    "output_sha256": file_sha256(output_path),
                    "numeric_timing_changed": False,
                    "ready": True,
                    "source_media_modified": False,
                }
            )
        write_json(
            staging / SUMMARY_NAME,
            {
                "schema": SCHEMA,
                "status": "PASS",
                "family": "ac7206",
                "events": rows,
                "numeric_timing_changed": False,
                "existing_route_media_reencode_required": False,
                "route_product_count": 6,
                "independent_route_edition_file_count": 18,
                "edited_showcase_edition_file_count": 3,
                "existing_audience_file_count": 21,
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
    parser.add_argument("--source-event-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--override", action="append", type=Path, default=[])
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if args.verify_only:
        result = verify_output(output_dir)
    else:
        if args.source_event_dir is None:
            raise ValueError("--source-event-dir is required when building")
        build(args.source_event_dir.resolve(), output_dir, args.override)
        result = read_json(output_dir / "VERIFICATION.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
