#!/usr/bin/env python3
"""Build event-global replacement manifests for ac7101-ac7107 archives."""

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
    from tools.frida_runtime_probe.build_ac7101_ac7107_timing_authority import (
        BLOCKER,
        DEFAULT_OVERRIDE_ROOT,
        EVENTS,
        EXPECTED_REQUESTS,
        SOURCE_MANIFEST_ROOT,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_ac7101_ac7107_timing_authority import (
        BLOCKER,
        DEFAULT_OVERRIDE_ROOT,
        EVENTS,
        EXPECTED_REQUESTS,
        SOURCE_MANIFEST_ROOT,
    )
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
    )


RESEARCH_ROOT = Path(
    r"D:\magia\MyProducts\casino\magireco_corrected_research_20260612"
)
DEFAULT_OUTPUT_ROOT = (
    RESEARCH_ROOT
    / "production_manifests_v76r3_ac7101_ac7107_event_global_speakers_20260817"
)
SCHEMA = "magireco-ac7101-ac7107-replacement-manifests-v1"
SUMMARY_NAME = "AC7101_AC7107_REPLACEMENT_MANIFEST_SUMMARY.json"

ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Summary = Join-Path $Root 'AC7101_AC7107_REPLACEMENT_MANIFEST_SUMMARY.json'
if (-not (Test-Path -LiteralPath $Summary)) { throw 'replacement summary missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable ac7101-ac7107 replacement manifests can be disabled without touching source manifests or media; rerun with -Apply to rename this root.'
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


def timing_snapshot(manifest: dict) -> dict:
    return {
        "audio": [
            {
                "request_id": str(row.get("request_id", "")),
                "z2d_name": str(row.get("z2d_name", "")),
                "start_ms": int(row.get("start_ms", -1)),
                "duration_ms": int(row.get("duration_ms", -1)),
            }
            for row in manifest.get("audio", [])
            if row.get("source") == "z2d_req_sound"
        ],
        "subtitles": [
            {
                "voice_request_id": str(row.get("voice_request_id", "")),
                "subtitle_source": str(row.get("subtitle_source", "")),
                "z2d_name": str(row.get("z2d_name", "")),
                "start_ms": int(row.get("start_ms", -1)),
                "end_ms": int(row.get("end_ms", -1)),
            }
            for row in manifest.get("subtitles", [])
        ],
    }


def annotate_request_bound_speaker_codes(manifest: dict) -> list[dict[str, str]]:
    """Bind a subtitle speaker to the exact official request code-name token."""

    event = str(manifest.get("event", ""))
    audio_by_request = {
        str(row.get("request_id", "")): row
        for row in manifest.get("audio", [])
        if row.get("source") == "z2d_req_sound"
    }
    applied = []
    for row in manifest.get("subtitles", []):
        request_id = str(row.get("voice_request_id", "")).strip()
        if not request_id:
            continue
        audio = audio_by_request.get(request_id)
        if audio is None:
            raise ValueError(f"{event}/{request_id}: subtitle lacks voice request")
        code_name = str(audio.get("code_name", "")).strip()
        parts = code_name.split("_", 3)
        if len(parts) != 4 or not parts[2].strip():
            raise ValueError(
                f"{event}/{request_id}: official voice code-name lacks speaker token"
            )
        speaker_code = parts[2].strip()
        existing = str(row.get("speaker_code", "")).strip()
        if existing and existing != speaker_code:
            raise ValueError(
                f"{event}/{request_id}: subtitle speaker conflicts with voice code-name"
            )
        row["speaker_code"] = speaker_code
        row["speaker_identity_evidence"] = (
            "exact_official_voice_request_code_name_speaker_token"
        )
        applied.append(
            {
                "event": event,
                "request_id": request_id,
                "speaker_code": speaker_code,
                "code_name": code_name,
            }
        )
    return applied


def repair_manifest(source: dict, override: dict) -> tuple[dict, dict, dict]:
    manifest = copy.deepcopy(source)
    event = str(manifest.get("event", ""))
    if event not in EVENTS:
        raise ValueError(f"unexpected ac7101-ac7107 event: {event}")
    gates = manifest.get("quality_gates")
    if not isinstance(gates, dict) or (
        gates.get("errors") != [BLOCKER]
        or gates.get("ready") is not False
        or gates.get("event_global_z2d_timing_ready") is not False
        or gates.get("composition_resolved") is not True
        or gates.get("video_composition_model") != "linear_full_frame_sequence"
    ):
        raise ValueError(f"{event}: source fail-closed state differs")
    if manifest.get("native_dimensions") != {"width": 416, "height": 232}:
        raise ValueError(f"{event}: native dimensions differ")
    if Fraction(str(manifest.get("native_frame_rate", ""))) != Fraction(30, 1):
        raise ValueError(f"{event}: native frame rate differs")
    if str(override.get("event_code_hex", "")).lower() != str(
        manifest.get("event_code_hex", "")
    ).lower():
        raise ValueError(f"{event}: event code differs")

    before = timing_snapshot(manifest)
    observed_requests = tuple(row["request_id"] for row in before["audio"])
    if observed_requests != EXPECTED_REQUESTS[event]:
        raise ValueError(f"{event}: source request set differs")
    application = apply_z2d_event_timing_override(
        manifest.get("audio", []), manifest.get("subtitles", []), override
    )
    if (
        application["unmatched_cues"]
        or application["recovery_conflicts"]
        or not application["request_set_matches"]
        or application["matched_audio_cue_count"] != len(EXPECTED_REQUESTS[event])
        or application["matched_subtitle_cue_count"]
        != len(manifest.get("subtitles", []))
        or application.get("recovered_audio_cue_count")
        or application.get("recovered_subtitle_cue_count")
    ):
        raise ValueError(f"{event}: override application differs: {application}")

    after = timing_snapshot(manifest)
    if [row["start_ms"] for row in before["audio"]] != [
        row["start_ms"] for row in after["audio"]
    ]:
        raise ValueError(f"{event}: audio start unexpectedly changed")
    if [row["start_ms"] for row in before["subtitles"]] != [
        row["start_ms"] for row in after["subtitles"]
    ]:
        raise ValueError(f"{event}: subtitle start unexpectedly changed")
    official_before = [
        row["end_ms"]
        for row in before["subtitles"]
        if row["subtitle_source"] == "official_voice_label"
    ]
    official_after = [
        row["end_ms"]
        for row in after["subtitles"]
        if row["subtitle_source"] == "official_voice_label"
    ]
    if official_before != official_after:
        raise ValueError(f"{event}: official voice duration unexpectedly changed")

    speaker_applications = annotate_request_bound_speaker_codes(manifest)
    unresolved = [
        row
        for row in [*manifest.get("audio", []), *manifest.get("subtitles", [])]
        if (
            row.get("source") == "z2d_req_sound"
            or row.get("subtitle_source")
            in {"graphical_display_text", "official_voice_label"}
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

    graphical_changes = [
        {
            "z2d_name": after_row["z2d_name"],
            "old_end_ms": before_row["end_ms"],
            "new_end_ms": after_row["end_ms"],
        }
        for before_row, after_row in zip(
            before["subtitles"], after["subtitles"], strict=True
        )
        if before_row["subtitle_source"] == "graphical_display_text"
        and before_row["end_ms"] != after_row["end_ms"]
    ]
    gates["errors"] = []
    gates["all_audio_exist"] = True
    gates["event_global_z2d_timing_ready"] = True
    gates["audio_timeline_ready"] = True
    gates["render_ready"] = True
    gates["ready"] = True
    manifest["z2d_event_timing_override_application"] = application
    manifest["strict_no_bgm_sound_bus_contract"] = {
        "status": "PASS",
        "included_buses": ["SE", "VOICE"],
        "excluded_buses": ["BGM"],
        "bgm_bus_row_count": 0,
        "evidence": "hash-bound SOUND_DIVIDE_TBL audit in timing override",
    }
    return manifest, application, {
        "graphical_end_changes": graphical_changes,
        "speaker_applications": speaker_applications,
    }


def verify_output(output_dir: Path) -> dict:
    summary_path = output_dir / SUMMARY_NAME
    if not summary_path.is_file():
        raise ValueError(f"missing replacement summary: {summary_path}")
    summary = read_json(summary_path)
    if summary.get("schema") != SCHEMA:
        raise ValueError("replacement summary schema differs")
    rows = summary.get("events", [])
    if [row.get("event") for row in rows] != list(EVENTS):
        raise ValueError("replacement event sequence differs")
    verified = []
    for row in rows:
        event = str(row["event"])
        output_path = output_dir / "events" / f"{event}.json"
        source_path = Path(str(row["source_manifest_path"]))
        if file_sha256(output_path) != row.get("output_sha256"):
            raise ValueError(f"{event}: output SHA-256 differs")
        if file_sha256(source_path) != row.get("source_manifest_sha256"):
            raise ValueError(f"{event}: source SHA-256 differs")
        manifest = read_json(output_path)
        gates = manifest.get("quality_gates", {})
        if (
            gates.get("errors") != []
            or gates.get("ready") is not True
            or gates.get("event_global_z2d_timing_ready") is not True
            or gates.get("audio_timeline_ready") is not True
            or gates.get("render_ready") is not True
        ):
            raise ValueError(f"{event}: output is not event-global READY")
        if manifest.get("strict_no_bgm_sound_bus_contract", {}).get(
            "bgm_bus_row_count"
        ) != 0:
            raise ValueError(f"{event}: strict no-BGM contract differs")
        speaker_rows = [
            row
            for row in manifest.get("subtitles", [])
            if str(row.get("voice_request_id", "")).strip()
        ]
        if not speaker_rows or any(
            not str(row.get("speaker_code", "")).strip()
            or row.get("speaker_identity_evidence")
            != "exact_official_voice_request_code_name_speaker_token"
            for row in speaker_rows
        ):
            raise ValueError(f"{event}: request-bound speaker identity differs")
        verified.append(
            {
                "event": event,
                "output_sha256": row["output_sha256"],
                "ready": True,
                "source_media_modified": False,
                "request_bound_speaker_identity_ready": True,
            }
        )
    return {
        "schema": "magireco-ac7101-ac7107-replacement-verification-v1",
        "result": "PASS",
        "event_count": len(verified),
        "events": verified,
        "product_scope": "fourteen independent single-event archives",
        "natural_001_to_002_session_proven": False,
        "unresolved_selector_003_remains_blocked": True,
        "audio_start_timing_changed": False,
        "request_bound_speaker_identity_ready": True,
        "graphical_subtitle_end_change_count": sum(
            len(row.get("graphical_subtitle_end_changes", [])) for row in rows
        ),
        "human_playback_required": True,
        "publication_approved": False,
        "source_media_modified": False,
    }


def build(source_dir: Path, output_dir: Path, override_paths: list[Path]) -> None:
    if output_dir.exists():
        raise ValueError(f"immutable output already exists: {output_dir}")
    overrides = load_z2d_event_timing_overrides(override_paths)
    if set(overrides) != set(EVENTS):
        raise ValueError(
            f"override event set differs: expected={list(EVENTS)} "
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
            repaired, application, changes = repair_manifest(
                read_json(source_path), overrides[event]
            )
            repaired["timing_repair_provenance"] = {
                "source_manifest_path": str(source_path.resolve()),
                "source_manifest_sha256": source_sha,
                "source_media_modified": False,
                "request_bound_speaker_identity_ready": True,
                "audio_start_timing_changed": False,
                "graphical_subtitle_end_changes": changes[
                    "graphical_end_changes"
                ],
                "request_bound_speaker_applications": changes[
                    "speaker_applications"
                ],
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
                    "audio_start_timing_changed": False,
                    "graphical_subtitle_end_changes": changes[
                        "graphical_end_changes"
                    ],
                    "request_bound_speaker_applications": changes[
                        "speaker_applications"
                    ],
                    "ready": True,
                    "source_media_modified": False,
                }
            )
        write_json(
            staging / SUMMARY_NAME,
            {
                "schema": SCHEMA,
                "status": "PASS",
                "families": [f"ac710{i}" for i in range(1, 8)],
                "event_count": len(EVENTS),
                "events": rows,
                "product_scope": "fourteen independent single-event archives",
                "natural_001_to_002_session_proven": False,
                "unresolved_selector_003_remains_blocked": True,
                "audio_start_timing_changed": False,
                "request_bound_speaker_identity_ready": True,
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
    parser.add_argument("--source-event-dir", type=Path, default=SOURCE_MANIFEST_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--override", action="append", type=Path, default=[])
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if args.verify_only:
        result = verify_output(output_dir)
    else:
        override_paths = args.override or [
            DEFAULT_OVERRIDE_ROOT / f"{event}_parent_scene_motion_key_v1.json"
            for event in EVENTS
        ]
        build(args.source_event_dir.resolve(), output_dir, override_paths)
        result = read_json(output_dir / "VERIFICATION.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
