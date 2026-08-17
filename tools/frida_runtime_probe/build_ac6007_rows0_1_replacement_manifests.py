#!/usr/bin/env python3
"""Promote the four ac6007 rows 0/1 dialogue events to event-global READY."""

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


EVENTS = ("ac6007_002", "ac6007_003", "ac6007_005", "ac6007_006")
BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"
SCHEMA = "magireco-ac6007-rows0-1-replacement-manifests-v1"
SUMMARY_NAME = "AC6007_ROWS0_1_REPLACEMENT_MANIFEST_SUMMARY.json"
EXPECTED_REQUESTS = {
    "ac6007_002": ("4093", "4356"),
    "ac6007_003": ("4090",),
    "ac6007_005": ("4091",),
    "ac6007_006": ("4096",),
}
EXPECTED_BEFORE = {
    "ac6007_002": {
        "audio": {"4093": 33, "4356": 633},
        "subtitles": {
            "cap6007_qkuma_fer_001": (33, 1033),
            "cap6007_qkuma_san_002": (633, 1655),
        },
    },
    "ac6007_003": {
        "audio": {"4090": 33},
        "subtitles": {"cap6007_qkuma_fer_003": (33, 1335)},
    },
    "ac6007_005": {
        "audio": {"4091": 33},
        "subtitles": {"cap6007_qkuma_fer_005": (33, 3030)},
    },
    "ac6007_006": {
        "audio": {"4096": 33},
        "subtitles": {"cap6007_qkuma_fer_006": (33, 1533)},
    },
}
EXPECTED_AFTER = copy.deepcopy(EXPECTED_BEFORE)
EXPECTED_AFTER["ac6007_005"]["subtitles"]["cap6007_qkuma_fer_005"] = (
    33,
    2867,
)
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Summary = Join-Path $Root 'AC6007_ROWS0_1_REPLACEMENT_MANIFEST_SUMMARY.json'
if (-not (Test-Path -LiteralPath $Summary)) { throw 'replacement summary missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable ac6007 replacement manifests can be disabled without touching source manifests or media; rerun with -Apply to rename this root.'
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
        raise ValueError(f"unexpected ac6007 event: {event}")
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
    if before != EXPECTED_BEFORE[event]:
        raise ValueError(f"{event}: source numeric timing differs")
    application = apply_z2d_event_timing_override(
        manifest.get("audio", []), manifest.get("subtitles", []), override
    )
    if application["unmatched_cues"]:
        raise ValueError(f"{event}: unmatched override cues {application['unmatched_cues']}")
    if application["recovery_conflicts"]:
        raise ValueError(f"{event}: recovery conflicts {application['recovery_conflicts']}")
    if not application["request_set_matches"]:
        raise ValueError(f"{event}: Z2D request set differs")
    expected_count = len(EXPECTED_REQUESTS[event])
    if application["matched_audio_cue_count"] != expected_count:
        raise ValueError(f"{event}: not every audio cue was promoted")
    if application["matched_subtitle_cue_count"] != expected_count:
        raise ValueError(f"{event}: not every subtitle cue was promoted")
    if application.get("recovered_audio_cue_count") or application.get(
        "recovered_subtitle_cue_count"
    ):
        raise ValueError(f"{event}: source rows unexpectedly recovered")
    after = timing_snapshot(manifest)
    if after != EXPECTED_AFTER[event]:
        raise ValueError(f"{event}: promoted numeric timing differs")

    unresolved = [
        row
        for row in [*manifest.get("audio", []), *manifest.get("subtitles", [])]
        if (
            row.get("source") == "z2d_req_sound"
            or str(row.get("voice_request_id", "")) in EXPECTED_REQUESTS[event]
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
    gates["all_audio_exist"] = True
    gates["event_global_z2d_timing_ready"] = True
    gates["audio_timeline_ready"] = True
    gates["render_ready"] = True
    gates["ready"] = True
    manifest["z2d_event_timing_override_application"] = application
    return manifest, application


def verify_output(output_dir: Path) -> dict:
    summary_path = output_dir / SUMMARY_NAME
    if not summary_path.is_file():
        raise ValueError(f"missing ac6007 replacement summary: {summary_path}")
    summary = read_json(summary_path)
    if summary.get("schema") != SCHEMA:
        raise ValueError("ac6007 replacement summary schema differs")
    rows = summary.get("events", [])
    if [row.get("event") for row in rows] != list(EVENTS):
        raise ValueError("ac6007 replacement event sequence differs")
    verified = []
    for row in rows:
        event = str(row["event"])
        output_path = output_dir / "events" / f"{event}.json"
        if file_sha256(output_path) != row.get("output_sha256"):
            raise ValueError(f"{event}: output SHA-256 differs")
        source_path = Path(str(row["source_manifest_path"]))
        if file_sha256(source_path) != row.get("source_manifest_sha256"):
            raise ValueError(f"{event}: source SHA-256 differs")
        manifest = read_json(output_path)
        if timing_snapshot(manifest) != EXPECTED_AFTER[event]:
            raise ValueError(f"{event}: verified numeric timing differs")
        gates = manifest["quality_gates"]
        if (
            gates.get("ready") is not True
            or gates.get("event_global_z2d_timing_ready") is not True
            or BLOCKER in gates.get("errors", [])
        ):
            raise ValueError(f"{event}: output is not event-global READY")
        verified.append(
            {
                "event": event,
                "output_sha256": row["output_sha256"],
                "numeric_timing_changed": event == "ac6007_005",
                "ready": True,
                "source_media_modified": False,
            }
        )
    return {
        "schema": "magireco-ac6007-rows0-1-replacement-verification-v1",
        "result": "PASS",
        "event_count": len(verified),
        "events": verified,
        "audio_start_timing_changed": False,
        "graphical_subtitle_end_changed": {
            "event": "ac6007_005",
            "request_id": "4091",
            "old_end_ms": 3030,
            "new_end_ms": 2867,
        },
        "source_media_modified": False,
        "route_0_media_reencode_required": False,
        "route_1_none_reencode_required": False,
        "route_1_ja_zh_reencode_required": True,
        "human_playback_required": True,
        "publication_approved": False,
    }


def build(source_dir: Path, output_dir: Path, override_paths: list[Path]) -> None:
    if output_dir.exists():
        raise ValueError(f"immutable output already exists: {output_dir}")
    overrides = load_z2d_event_timing_overrides(override_paths)
    if set(overrides) != set(EVENTS):
        raise ValueError(
            f"override event set differs: expected={list(EVENTS)} actual={sorted(overrides)}"
        )
    staging = output_dir.with_name(f".{output_dir.name}.staging-{uuid.uuid4().hex}")
    event_dir = staging / "events"
    event_dir.mkdir(parents=True)
    rows = []
    try:
        for event in EVENTS:
            source_path = source_dir / f"{event}.json"
            source_sha = file_sha256(source_path)
            repaired, application = repair_manifest(
                read_json(source_path), overrides[event]
            )
            repaired["timing_repair_provenance"] = {
                "source_manifest_path": str(source_path.resolve()),
                "source_manifest_sha256": source_sha,
                "source_media_modified": False,
                "audio_start_timing_changed": False,
                "graphical_subtitle_end_changed": event == "ac6007_005",
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
                    "override_applied": True,
                    "numeric_timing_changed": event == "ac6007_005",
                    "ready": True,
                    "source_media_modified": False,
                }
            )
        write_json(
            staging / SUMMARY_NAME,
            {
                "schema": SCHEMA,
                "status": "PASS",
                "family": "ac6007",
                "dirinfo_rows": [0, 1],
                "events": rows,
                "audio_start_timing_changed": False,
                "graphical_subtitle_end_changed": {
                    "event": "ac6007_005",
                    "request_id": "4091",
                    "old_end_ms": 3030,
                    "new_end_ms": 2867,
                },
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-event-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--override", action="append", type=Path, default=[])
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
