#!/usr/bin/env python3
"""Build immutable P18 CU-success manifests from event-global timing evidence."""

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
        production_content_end_ms,
        quantize_duration_to_frame_grid,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
        production_content_end_ms,
        quantize_duration_to_frame_grid,
    )


EVENTS = ("ac6005_010", "ac6005_013", "ac6005_014")
OVERRIDE_EVENTS = ("ac6005_010", "ac6005_014")
BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"
SCHEMA = "magireco-p18-cu-success-replacement-manifests-v1"
SUMMARY_NAME = "P18_AC6005_CU_SUCCESS_REPLACEMENT_MANIFEST_SUMMARY.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
EVENT_014_PLAN = (
    REPO_ROOT
    / "tools"
    / "frida_runtime_probe"
    / "composition_plans"
    / "ac6005_014_event_global_clean_story.json"
)
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Summary = Join-Path $Root 'P18_AC6005_CU_SUCCESS_REPLACEMENT_MANIFEST_SUMMARY.json'
if (-not (Test-Path -LiteralPath $Summary)) { throw 'replacement summary missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable P18 replacement manifests can be disabled without touching source manifests or media; rerun with -Apply to rename this root.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-event-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--override", action="append", type=Path, default=[])
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def timeline_end_ms(manifest: dict) -> int:
    return max(
        [int(row.get("event_end_ms", 0)) for row in manifest.get("clips", [])]
        + [
            int(row.get("start_ms", 0)) + int(row.get("duration_ms", 0))
            for row in manifest.get("audio", [])
        ]
        + [int(row.get("end_ms", 0)) for row in manifest.get("subtitles", [])]
        + [0]
    )


def _bind_event_014_plan(manifest: dict) -> dict[str, str]:
    plan = read_json(EVENT_014_PLAN)
    if (
        plan.get("event") != "ac6005_014"
        or plan.get("model") != "timed_full_frame_layers"
        or plan.get("duration_ms") != 15333
        or plan.get("excluded_audio_request_ids") != ["225"]
        or "excluded_subtitle_z2d_names" in plan
        or [row.get("dgm_name") for row in plan.get("clips", [])]
        != [
            "ac6005_014_c01",
            "ac6005_014_c03",
            "ac6005_014_c04",
            "ac6005_014_c05",
            "ac6005_014_c06",
            "ac6005_014_c06_LP",
        ]
    ):
        raise ValueError("ac6005_014 event-global clean-story plan differs")
    manifest["composition_plan"] = plan
    manifest["composition_plan_source"] = str(EVENT_014_PLAN.resolve())
    return {
        "path": str(EVENT_014_PLAN.resolve()),
        "sha256": file_sha256(EVENT_014_PLAN),
    }


def repair_manifest(source: dict, override: dict | None) -> tuple[dict, dict]:
    manifest = copy.deepcopy(source)
    event = str(manifest.get("event", ""))
    if event not in EVENTS:
        raise ValueError(f"unexpected P18 event: {event}")
    gates = manifest.get("quality_gates")
    if not isinstance(gates, dict):
        raise ValueError(f"{event}: missing quality_gates")

    if event == "ac6005_013":
        if override is not None:
            raise ValueError("ac6005_013 must retain its resolved runtime manifest")
        runtime_sources = manifest.get("runtime_event_manifest_sources", [])
        if (
            not gates.get("ready")
            or not gates.get("event_global_z2d_timing_ready")
            or len(runtime_sources) != 1
            or file_sha256(Path(runtime_sources[0]["path"]))
            != runtime_sources[0]["sha256"]
        ):
            raise ValueError("ac6005_013 source is no longer runtime-exact READY")
        return manifest, {
            "applied": False,
            "reason": "source_manifest_already_runtime_exact_ready",
        }

    if override is None:
        raise ValueError(f"{event}: required timing override is missing")
    if str(override.get("event_code_hex", "")).lower() != str(
        manifest.get("event_code_hex", "")
    ).lower():
        raise ValueError(f"{event}: event code differs")
    if Fraction(str(override.get("frame_rate", ""))) != Fraction(
        str(manifest.get("native_frame_rate", ""))
    ):
        raise ValueError(f"{event}: frame rate differs")

    application = apply_z2d_event_timing_override(
        manifest.get("audio", []), manifest.get("subtitles", []), override
    )
    if application["unmatched_cues"]:
        raise ValueError(f"{event}: unmatched override cues {application['unmatched_cues']}")
    if application["recovery_conflicts"]:
        raise ValueError(f"{event}: recovery conflicts {application['recovery_conflicts']}")
    if not application["request_set_matches"]:
        raise ValueError(f"{event}: Z2D request set differs")
    if application["matched_audio_cue_count"] != len(
        override["expected_z2d_request_ids"]
    ):
        raise ValueError(f"{event}: not every voice timing cue was applied")
    if event == "ac6005_010" and (
        application["recovered_audio_cue_count"]
        or application["recovered_subtitle_cue_count"]
    ):
        raise ValueError("ac6005_010 unexpectedly recovered source rows")
    if event == "ac6005_014" and (
        application["recovered_audio_cue_count"] != 0
        or application["recovered_subtitle_cue_count"] != 1
    ):
        raise ValueError("ac6005_014 graphical continuation recovery differs")

    if event == "ac6005_014":
        plan_binding = _bind_event_014_plan(manifest)
        application["replacement_composition_plan"] = plan_binding
    unresolved = [
        row
        for row in [*manifest.get("audio", []), *manifest.get("subtitles", [])]
        if (
            row.get("source") == "z2d_req_sound"
            or row.get("subtitle_source") == "graphical_display_text"
        )
        and row.get("event_global_start_resolved") is not True
    ]
    if unresolved:
        raise ValueError(f"{event}: child-local timing remains unresolved")

    errors = [error for error in gates.get("errors", []) if error != BLOCKER]
    if errors:
        raise ValueError(f"{event}: unrelated source blocker remains: {errors}")
    if not all(
        row.get("path") and Path(row["path"]).is_file()
        for row in manifest.get("audio", [])
    ):
        raise ValueError(f"{event}: audio media is incomplete")
    gates["errors"] = []
    gates["all_audio_exist"] = True
    gates["exact_z2d_req_sound_count"] = sum(
        row.get("source") == "z2d_req_sound" for row in manifest.get("audio", [])
    )
    gates["verified_subtitle_voice_count"] = len(manifest.get("subtitles", []))
    gates["graphical_display_subtitle_count"] = sum(
        row.get("subtitle_source") == "graphical_display_text"
        for row in manifest.get("subtitles", [])
    )
    gates["event_global_z2d_timing_ready"] = True
    gates["audio_timeline_ready"] = bool(manifest.get("audio"))
    gates["render_ready"] = bool(gates.get("composition_resolved"))
    gates["ready"] = bool(gates.get("composition_resolved"))
    if not gates["ready"]:
        raise ValueError(f"{event}: composition is not ready")

    manifest["audio"].sort(
        key=lambda row: (int(row.get("start_ms", 0)), str(row.get("request_id", "")))
    )
    manifest["subtitles"].sort(
        key=lambda row: (
            int(row.get("start_ms", 0)),
            int(row.get("end_ms", 0)),
            str(row.get("z2d_name", "")),
        )
    )
    evidence_end = timeline_end_ms(manifest)
    source_content_end_ms = int(
        manifest.get("raw_render_duration_ms", manifest.get("timeline_content_end_ms", 0))
    )
    raw_end = max(
        source_content_end_ms,
        production_content_end_ms(
            int(manifest.get("video_duration_ms", 0)),
            evidence_end,
            manifest.get("composition_plan") or None,
        ),
    )
    quantized = quantize_duration_to_frame_grid(
        raw_end, str(manifest.get("native_frame_rate", ""))
    )
    if (
        int(quantized["duration_ms"]) > int(manifest.get("video_duration_ms", 0))
        and manifest.get("video_extension_policy")
        not in {"loop_last_clip", "hold_last_frame", "black_tail"}
    ):
        raise ValueError(f"{event}: repaired tail lacks extension policy")
    manifest["timeline_duration_ms"] = evidence_end
    manifest["timeline_content_end_ms"] = raw_end
    manifest["raw_render_duration_ms"] = raw_end
    manifest["render_frame_count"] = int(quantized["frame_count"])
    manifest["render_duration_ms"] = int(quantized["duration_ms"])
    manifest["render_duration_quantization"] = quantized
    manifest["z2d_event_timing_override_application"] = application
    return manifest, application


def verify_output(output_dir: Path) -> dict:
    summary_path = output_dir / SUMMARY_NAME
    if not summary_path.is_file():
        raise ValueError(f"missing P18 replacement summary: {summary_path}")
    summary = read_json(summary_path)
    if summary.get("schema") != SCHEMA:
        raise ValueError("P18 replacement summary schema differs")
    rows = summary.get("events", [])
    if [row.get("event") for row in rows] != list(EVENTS):
        raise ValueError("P18 replacement event sequence differs")

    verified = []
    for row in rows:
        event = str(row["event"])
        path = output_dir / "events" / f"{event}.json"
        if file_sha256(path) != row["output_sha256"]:
            raise ValueError(f"{event}: output SHA-256 differs")
        source_path = Path(row["source_manifest_path"])
        if file_sha256(source_path) != row["source_manifest_sha256"]:
            raise ValueError(f"{event}: source SHA-256 differs")
        manifest = read_json(path)
        gates = manifest["quality_gates"]
        if not gates["ready"] or not gates["event_global_z2d_timing_ready"]:
            raise ValueError(f"{event}: output is not event-global ready")
        if BLOCKER in gates.get("errors", []):
            raise ValueError(f"{event}: timing blocker leaked")
        if event == "ac6005_010":
            starts = {
                str(item.get("request_id")): int(item.get("start_ms", -1))
                for item in manifest["audio"]
            }
            if starts.get("5612") != 900 or starts.get("5409") != 3200:
                raise ValueError("ac6005_010 voice timing differs")
        if event == "ac6005_013" and row["override_applied"]:
            raise ValueError("ac6005_013 received an override")
        if event == "ac6005_014":
            subtitles = {
                item["z2d_name"]: (int(item["start_ms"]), int(item["end_ms"]))
                for item in manifest["subtitles"]
            }
            expected = {
                "cap6005_mb_iro_014": (33, 1700),
                "cap6005_mb_iro_015": (4567, 6867),
                "cap6005_mb_iro_015_01": (7567, 9667),
                "cap6005_mb_iro_015_02": (9833, 11033),
                "cap6005_mb_iro_015_03": (11167, 14467),
            }
            if subtitles != expected:
                raise ValueError(f"ac6005_014 subtitle timing differs: {subtitles}")
            if "excluded_subtitle_z2d_names" in manifest["composition_plan"]:
                raise ValueError("ac6005_014 exact continuation remains excluded")
        verified.append(
            {
                "event": event,
                "output_sha256": row["output_sha256"],
                "ready": True,
                "source_media_modified": False,
            }
        )
    return {
        "schema": "magireco-p18-cu-success-replacement-verification-v1",
        "result": "PASS",
        "event_count": len(verified),
        "events": verified,
        "source_media_modified": False,
        "human_playback_required": True,
        "publishable": False,
    }


def build(source_dir: Path, output_dir: Path, override_paths: list[Path]) -> None:
    if output_dir.exists():
        raise ValueError(f"immutable output already exists: {output_dir}")
    overrides = load_z2d_event_timing_overrides(override_paths)
    if set(overrides) != set(OVERRIDE_EVENTS):
        raise ValueError(
            f"override event set differs: expected={list(OVERRIDE_EVENTS)} "
            f"actual={sorted(overrides)}"
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
                read_json(source_path), overrides.get(event)
            )
            repaired["timing_repair_provenance"] = {
                "source_manifest_path": str(source_path.resolve()),
                "source_manifest_sha256": source_sha,
                "source_media_modified": False,
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
                    "override_applied": bool(application.get("applied")),
                    "ready": True,
                    "source_media_modified": False,
                }
            )
        write_json(
            staging / SUMMARY_NAME,
            {
                "schema": SCHEMA,
                "status": "PASS",
                "route": {
                    "kind": 173,
                    "row_index": 10,
                    "meaning": "CU success",
                    "events": list(EVENTS),
                },
                "events": rows,
                "old_candidate_superseded": False,
                "human_playback_required": True,
                "publishable": False,
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
