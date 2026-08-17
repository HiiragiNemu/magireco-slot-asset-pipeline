#!/usr/bin/env python3
"""Build an immutable P16 manifest replacement from exact parent-scene timing.

This is deliberately a repair of an already audited seven-event manifest set,
not a second discovery pipeline.  Six events receive hash-bound Z2D timing
overrides; the already runtime-exact ac6003_005 manifest is copied unchanged.
No source manifest or media file is modified.
"""

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
    # Keep both ``python -m`` and direct script execution reproducible.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.frida_runtime_probe.build_event_production_manifests import (
        apply_z2d_event_timing_override,
        file_sha256,
        load_z2d_event_timing_overrides,
        production_content_end_ms,
        quantize_duration_to_frame_grid,
    )


EVENTS = (
    "ac6003_005",
    "ac6003_006",
    "ac6003_007",
    "ac6003_009",
    "ac6003_010",
    "ac6003_014",
    "ac6003_015",
)
OVERRIDE_EVENTS = EVENTS[1:]
BLOCKER = "unresolved_parent_dgm_to_child_z2d_instantiation_offset"
SCHEMA = "magireco-p16-family-replacement-manifests-v1"
ROLLBACK_SCRIPT = """param([switch]$Apply)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Summary = Join-Path $Root 'P16_AC6003_REPLACEMENT_MANIFEST_SUMMARY.json'
if (-not (Test-Path -LiteralPath $Summary)) { throw 'replacement summary missing' }
if (-not $Apply) {
  Write-Output 'ROLLBACK_VALIDATED: immutable replacement can be disabled without touching source manifests or media; rerun with -Apply to rename this root.'
  exit 0
}
$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
Move-Item -LiteralPath $Root -Destination $Target
Write-Output ('ROLLBACK_APPLIED=' + $Target)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-event-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--override", action="append", type=Path, default=[])
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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


def repair_manifest(source: dict, override: dict | None) -> tuple[dict, dict]:
    manifest = copy.deepcopy(source)
    event = str(manifest.get("event", ""))
    if event not in EVENTS:
        raise ValueError(f"unexpected P16 event: {event}")
    gates = manifest.get("quality_gates")
    if not isinstance(gates, dict):
        raise ValueError(f"{event}: missing quality_gates")

    if event == "ac6003_005":
        if override is not None:
            raise ValueError("ac6003_005 must not receive a timing override")
        if not gates.get("ready") or not gates.get("event_global_z2d_timing_ready"):
            raise ValueError("ac6003_005 source is no longer runtime-exact READY")
        return manifest, {
            "applied": False,
            "reason": "source_manifest_already_runtime_exact_ready",
        }

    if override is None:
        raise ValueError(f"{event}: missing required timing override")
    if str(override.get("event_code_hex", "")).lower() != str(
        manifest.get("event_code_hex", "")
    ).lower():
        raise ValueError(f"{event}: event code mismatch")
    if Fraction(str(override.get("frame_rate", ""))) != Fraction(
        str(manifest.get("native_frame_rate", ""))
    ):
        raise ValueError(f"{event}: frame-rate mismatch")

    application = apply_z2d_event_timing_override(
        manifest.get("audio", []),
        manifest.get("subtitles", []),
        override,
    )
    if application["unmatched_cues"]:
        raise ValueError(f"{event}: unmatched override cues {application['unmatched_cues']}")
    if application["matched_audio_cue_count"] < 1:
        raise ValueError(f"{event}: no audio timing cue was applied")
    if any(
        row.get("event_global_start_resolved") is False
        for row in [*manifest.get("audio", []), *manifest.get("subtitles", [])]
    ):
        raise ValueError(f"{event}: child-local timing remains unresolved")

    errors = [error for error in gates.get("errors", []) if error != BLOCKER]
    if errors:
        raise ValueError(f"{event}: unrelated source blocker remains: {errors}")
    gates["errors"] = []
    gates["event_global_z2d_timing_ready"] = True
    gates["audio_timeline_ready"] = bool(manifest.get("audio")) and bool(
        gates.get("all_audio_exist")
    )
    gates["render_ready"] = bool(gates.get("composition_resolved"))
    gates["ready"] = bool(gates.get("composition_resolved"))
    if not gates["ready"]:
        raise ValueError(f"{event}: composition is not READY")

    evidence_end = timeline_end_ms(manifest)
    raw_end = production_content_end_ms(
        int(manifest.get("video_duration_ms", 0)),
        evidence_end,
        manifest.get("composition_plan") or None,
    )
    quantized = quantize_duration_to_frame_grid(
        raw_end, str(manifest.get("native_frame_rate", ""))
    )
    if (
        int(quantized["duration_ms"]) > int(manifest.get("video_duration_ms", 0))
        and manifest.get("video_extension_policy")
        not in {"loop_last_clip", "hold_last_frame", "black_tail"}
    ):
        raise ValueError(f"{event}: repaired tail lacks an extension policy")
    manifest["timeline_duration_ms"] = evidence_end
    manifest["timeline_content_end_ms"] = raw_end
    manifest["raw_render_duration_ms"] = raw_end
    manifest["render_frame_count"] = int(quantized["frame_count"])
    manifest["render_duration_ms"] = int(quantized["duration_ms"])
    manifest["render_duration_quantization"] = quantized
    manifest["z2d_event_timing_override_application"] = application
    return manifest, application


def verify_output(output_dir: Path) -> dict:
    summary_path = output_dir / "P16_AC6003_REPLACEMENT_MANIFEST_SUMMARY.json"
    if not summary_path.is_file():
        raise ValueError(f"missing summary: {summary_path}")
    summary = read_json(summary_path)
    if summary.get("schema") != SCHEMA:
        raise ValueError("replacement summary schema mismatch")
    rows = summary.get("events", [])
    if [row.get("event") for row in rows] != list(EVENTS):
        raise ValueError("replacement event sequence mismatch")

    checked = []
    for row in rows:
        event = str(row["event"])
        path = output_dir / "events" / f"{event}.json"
        if file_sha256(path) != row["output_sha256"]:
            raise ValueError(f"{event}: output SHA-256 mismatch")
        source_path = Path(row["source_manifest_path"])
        if file_sha256(source_path) != row["source_manifest_sha256"]:
            raise ValueError(f"{event}: source SHA-256 mismatch")
        manifest = read_json(path)
        gates = manifest["quality_gates"]
        if not gates["ready"] or not gates["event_global_z2d_timing_ready"]:
            raise ValueError(f"{event}: output is not event-global READY")
        if BLOCKER in gates.get("errors", []):
            raise ValueError(f"{event}: blocker leaked into output")
        if timeline_end_ms(manifest) != manifest["timeline_duration_ms"]:
            raise ValueError(f"{event}: timeline duration mismatch")
        checked.append(
            {
                "event": event,
                "output_sha256": row["output_sha256"],
                "ready": True,
                "media_modified": False,
            }
        )
    return {
        "schema": "magireco-p16-family-replacement-verification-v1",
        "result": "PASS",
        "event_count": len(checked),
        "events": checked,
        "source_media_modified": False,
    }


def build(source_dir: Path, output_dir: Path, override_paths: list[Path]) -> None:
    if output_dir.exists():
        raise ValueError(f"immutable output already exists: {output_dir}")
    overrides = load_z2d_event_timing_overrides(override_paths)
    if set(overrides) != set(OVERRIDE_EVENTS):
        raise ValueError(
            "override event set mismatch: "
            f"expected={list(OVERRIDE_EVENTS)} actual={sorted(overrides)}"
        )

    staging = output_dir.with_name(f".{output_dir.name}.staging-{uuid.uuid4().hex}")
    if staging.exists():
        raise ValueError(f"unexpected staging collision: {staging}")
    event_dir = staging / "events"
    event_dir.mkdir(parents=True)
    rows = []
    try:
        for event in EVENTS:
            source_path = source_dir / f"{event}.json"
            source_sha = file_sha256(source_path)
            source = read_json(source_path)
            repaired, application = repair_manifest(source, overrides.get(event))
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

        summary = {
            "schema": SCHEMA,
            "family": "ac6003",
            "title_zh": "八千代与美冬的冲突",
            "event_sequence": list(EVENTS),
            "source_event_dir": str(source_dir.resolve()),
            "source_media_modified": False,
            "supersedes_media": False,
            "status": "MANIFEST_READY_MEDIA_REBUILD_REQUIRED",
            "events": rows,
        }
        write_json(staging / "P16_AC6003_REPLACEMENT_MANIFEST_SUMMARY.json", summary)
        shutil.copy2(Path(__file__), staging / Path(__file__).name)
        (staging / "ROLLBACK.ps1").write_text(
            ROLLBACK_SCRIPT, encoding="utf-8"
        )
        os.replace(staging, output_dir)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    verification = verify_output(output_dir)
    write_json(output_dir / "VERIFICATION.json", verification)
    checksum_rows = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            checksum_rows.append(
                f"{file_sha256(path)}  {path.relative_to(output_dir).as_posix()}"
            )
    (output_dir / "SHA256SUMS.txt").write_text(
        "\n".join(checksum_rows) + "\n", encoding="utf-8"
    )
    print(json.dumps(verification, ensure_ascii=False, sort_keys=True))


def main() -> int:
    args = parse_args()
    try:
        if args.verify_only:
            result = verify_output(args.output_dir.resolve())
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            if len(args.override) != len(OVERRIDE_EVENTS):
                raise ValueError(
                    f"exactly {len(OVERRIDE_EVENTS)} --override arguments are required"
                )
            build(
                args.source_event_dir.resolve(),
                args.output_dir.resolve(),
                [path.resolve() for path in args.override],
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
