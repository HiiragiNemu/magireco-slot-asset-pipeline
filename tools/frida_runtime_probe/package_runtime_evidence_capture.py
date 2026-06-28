#!/usr/bin/env python3
"""Package a runtime capture into auditable evidence files.

This is a reproducibility/gating tool, not a video renderer.  It takes an
existing capture directory containing `runtime_probe.jsonl` and
`csl_audio_queue.jsonl`, then builds:

- decoded OpenSL diagnostic WAV + metadata;
- normalized summary tables;
- evidence-only runtime skeleton;
- SHA-256 manifest for raw and generated files;
- cumulative timeline CSV for event and OpenSL queue rows;
- QA/gate report that states whether the capture is usable evidence.

The pass state is intentionally named `passed_evidence_not_delivery`; it never
marks a capture as Bilibili-ready or production-render-ready.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLE_WIDTH = 2
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def normalize_float(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def queue_duration_s(row: dict[str, str]) -> float | None:
    value = normalize_float(row.get("buffer_bytes"))
    if value is None:
        return None
    return value / BYTES_PER_SECOND


def build_timeline(package_dir: Path) -> list[dict[str, Any]]:
    skeleton_dir = package_dir / "evidence_skeleton"
    event_rows = read_csv(skeleton_dir / "event_sequence.csv")
    queue_rows = read_csv(skeleton_dir / "queue_sequence.csv")
    sound_code_rows = read_csv(skeleton_dir / "sound_code_sequence.csv")

    timeline: list[dict[str, Any]] = []
    for row in event_rows:
        start_s = normalize_float(row.get("time_s"))
        timeline.append(
            {
                "kind": "runtime_event",
                "start_s": start_s,
                "duration_s": "",
                "end_s": "",
                "event_code": row.get("event_code", ""),
                "event_key": row.get("event_key", ""),
                "event_index": row.get("event_index", ""),
                "root": row.get("root", ""),
                "primary_animation": row.get("primary_animation", ""),
                "sound_code": "",
                "request_table_id": "",
                "sound_id": "",
                "buffer_bytes": "",
                "mapped_name": "",
                "mapping_status": row.get("mapping_status", ""),
                "is_metadata_only": "",
            }
        )

    for row in sound_code_rows:
        start_s = normalize_float(row.get("time_s"))
        timeline.append(
            {
                "kind": "runtime_sound_code",
                "start_s": start_s,
                "duration_s": "",
                "end_s": "",
                "event_code": row.get("active_event_code", ""),
                "event_key": row.get("active_event_key", ""),
                "event_index": "",
                "root": row.get("active_root", ""),
                "primary_animation": row.get("active_primary_animation", ""),
                "sound_code": row.get("code_string", ""),
                "request_table_id": row.get("request_table_id", ""),
                "sound_id": "",
                "buffer_bytes": "",
                "mapped_name": row.get("first_smz_media", ""),
                "mapping_status": row.get("mapping_status", ""),
                "is_metadata_only": "",
            }
        )

    for row in queue_rows:
        start_s = normalize_float(row.get("time_s"))
        duration_s = queue_duration_s(row)
        timeline.append(
            {
                "kind": "opensl_queue_chunk",
                "start_s": start_s,
                "duration_s": duration_s,
                "end_s": start_s + duration_s if start_s is not None and duration_s is not None else "",
                "event_code": "",
                "event_key": "",
                "event_index": "",
                "root": "",
                "primary_animation": "",
                "sound_code": "",
                "request_table_id": "",
                "sound_id": row.get("sound_id_u16_at_0x2", ""),
                "buffer_bytes": row.get("buffer_bytes", ""),
                "mapped_name": row.get("mapped_suggested_name", ""),
                "mapping_status": row.get("mapping_status", ""),
                "is_metadata_only": row.get("is_metadata_only", ""),
            }
        )

    timeline.sort(key=lambda item: (item["start_s"] is None, item["start_s"] or 0.0, item["kind"]))
    for index, row in enumerate(timeline):
        row["timeline_index"] = index
    return timeline


def collect_hashes(capture_dir: Path, package_dir: Path, label: str) -> list[dict[str, Any]]:
    wanted_roots = [
        capture_dir / "runtime_probe.jsonl",
        capture_dir / "csl_audio_queue.jsonl",
        capture_dir / "adb_taps.jsonl",
        capture_dir / "slot_targeted_before.png",
        capture_dir / "slot_targeted_after.png",
        package_dir / f"{label}_runtime_audio_timeline.wav",
        package_dir / f"{label}_runtime_audio_metadata.json",
        package_dir / "commands.json",
        package_dir / "summary_tables" / "summary.json",
        package_dir / "evidence_skeleton" / "runtime_evidence_skeleton.json",
        package_dir / "cumulative_runtime_timeline.csv",
        package_dir / "qa_report.json",
    ]
    rows: list[dict[str, Any]] = []
    for path in wanted_roots:
        if not path.exists() or not path.is_file():
            continue
        rows.append(
            {
                "path": str(path),
                "relative_to_capture": str(path.relative_to(capture_dir)) if path.is_relative_to(capture_dir) else "",
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def gate_report(
    capture_dir: Path,
    package_dir: Path,
    decode_metadata: dict[str, Any],
    summary: dict[str, Any],
    skeleton: dict[str, Any],
    timeline: list[dict[str, Any]],
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    runtime_jsonl = capture_dir / "runtime_probe.jsonl"
    csl_jsonl = capture_dir / "csl_audio_queue.jsonl"
    add_check("runtime_jsonl_exists", runtime_jsonl.exists(), str(runtime_jsonl))
    add_check("csl_jsonl_exists", csl_jsonl.exists(), str(csl_jsonl))
    add_check("commands_succeeded", all(item["returncode"] == 0 for item in commands), [item["returncode"] for item in commands])

    runtime_summary = summary.get("runtime", {})
    csl_summary = summary.get("csl", {})
    add_check("runtime_event_codes_present", int(runtime_summary.get("event_code_count") or 0) > 0, runtime_summary.get("event_code_count"))
    add_check("runtime_sound_codes_present", int(runtime_summary.get("sound_code_lookup_count") or 0) > 0, runtime_summary.get("sound_code_lookup_count"))
    add_check("csl_queue_chunks_present", int(csl_summary.get("queue_chunk_count") or 0) > 0, csl_summary.get("queue_chunk_count"))
    add_check("no_metadata_only_queue_chunks", int(csl_summary.get("queue_metadata_count") or 0) == 0, csl_summary.get("queue_metadata_count"))

    rendered_signal = decode_metadata.get("rendered_signal", {})
    rms_dbfs = rendered_signal.get("rms_dbfs")
    add_check("decoded_wav_not_digitally_silent", rms_dbfs is not None and rms_dbfs > -80.0, rms_dbfs)
    add_check("decoded_wav_native_audio_shape", decode_metadata.get("sample_rate") == SAMPLE_RATE and decode_metadata.get("channels") == CHANNELS and decode_metadata.get("sample_width") == SAMPLE_WIDTH, {
        "sample_rate": decode_metadata.get("sample_rate"),
        "channels": decode_metadata.get("channels"),
        "sample_width": decode_metadata.get("sample_width"),
    })

    skeleton_warnings = skeleton.get("warnings", [])
    queue_unmapped = [row for row in timeline if row.get("kind") == "opensl_queue_chunk" and row.get("mapping_status") != "mapped_ogg_chunk"]
    event_unmapped = [row for row in timeline if row.get("kind") == "runtime_event" and row.get("mapping_status") != "mapped_static_event"]
    add_check("skeleton_has_no_warnings", not skeleton_warnings, skeleton_warnings)
    add_check("runtime_events_static_mapped", not event_unmapped, len(event_unmapped))
    add_check("queue_sound_ids_static_mapped", not queue_unmapped, len(queue_unmapped))
    add_check("delivery_status_is_evidence_only", skeleton.get("delivery_status") == "evidence_only_not_render_ready", skeleton.get("delivery_status"))

    passed = all(check["passed"] for check in checks)
    return {
        "schema": "magireco_runtime_evidence_package_qa.v1",
        "status": "passed_evidence_not_delivery" if passed else "failed_evidence_package",
        "capture_dir": str(capture_dir),
        "package_dir": str(package_dir),
        "checks": checks,
        "summary": {
            "event_code_count": runtime_summary.get("event_code_count"),
            "sound_code_lookup_count": runtime_summary.get("sound_code_lookup_count"),
            "bgm_call_count": runtime_summary.get("bgm_call_count"),
            "queue_chunk_count": csl_summary.get("queue_chunk_count"),
            "queue_metadata_count": csl_summary.get("queue_metadata_count"),
            "observed_sound_ids": csl_summary.get("observed_sound_ids"),
            "duration_seconds": decode_metadata.get("duration_seconds"),
            "rendered_rms_dbfs": rms_dbfs,
        },
        "explicit_non_delivery_reason": (
            "This package proves runtime evidence quality only. It does not prove "
            "clean-story visual eligibility, subtitle correctness, or Bilibili-ready output."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--asset-manifests", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--layout", choices=("timeline", "concat"), default="timeline")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tool_dir = Path(__file__).resolve().parent
    capture_dir = args.capture_dir.resolve()
    label = args.label or capture_dir.name
    package_dir = (args.out_dir.resolve() if args.out_dir else capture_dir / "evidence_package_v1")
    package_dir.mkdir(parents=True, exist_ok=True)

    runtime_jsonl = capture_dir / "runtime_probe.jsonl"
    csl_jsonl = capture_dir / "csl_audio_queue.jsonl"
    wav_path = package_dir / f"{label}_runtime_audio_timeline.wav"
    wav_metadata_path = package_dir / f"{label}_runtime_audio_metadata.json"
    summary_dir = package_dir / "summary_tables"
    skeleton_dir = package_dir / "evidence_skeleton"

    commands = [
        run_command(
            [
                sys.executable,
                str(tool_dir / "decode_csl_audio_queue_dump.py"),
                "--jsonl",
                str(csl_jsonl),
                "--wav",
                str(wav_path),
                "--metadata-json",
                str(wav_metadata_path),
                "--layout",
                args.layout,
            ],
            cwd=tool_dir.parent.parent,
        ),
        run_command(
            [
                sys.executable,
                str(tool_dir / "summarize_runtime_audio_capture.py"),
                "--runtime-jsonl",
                str(runtime_jsonl),
                "--csl-jsonl",
                str(csl_jsonl),
                "--out-dir",
                str(summary_dir),
            ],
            cwd=tool_dir.parent.parent,
        ),
        run_command(
            [
                sys.executable,
                str(tool_dir / "build_runtime_evidence_skeleton.py"),
                "--summary-dir",
                str(summary_dir),
                "--asset-manifests",
                str(args.asset_manifests.resolve()),
                "--out-dir",
                str(skeleton_dir),
            ],
            cwd=tool_dir.parent.parent,
        ),
    ]

    command_rows = [
        {
            "index": index,
            "returncode": item["returncode"],
            "command": " ".join(item["command"]),
            "stdout": item["stdout"][-4000:],
            "stderr": item["stderr"][-4000:],
        }
        for index, item in enumerate(commands)
    ]
    write_json(package_dir / "commands.json", command_rows)

    decode_metadata = read_json(wav_metadata_path)
    summary = read_json(summary_dir / "summary.json")
    skeleton = read_json(skeleton_dir / "runtime_evidence_skeleton.json")
    timeline = build_timeline(package_dir)
    write_csv(
        package_dir / "cumulative_runtime_timeline.csv",
        timeline,
        [
            "timeline_index",
            "kind",
            "start_s",
            "duration_s",
            "end_s",
            "event_code",
            "event_key",
            "event_index",
            "root",
            "primary_animation",
            "sound_code",
            "request_table_id",
            "sound_id",
            "buffer_bytes",
            "mapped_name",
            "mapping_status",
            "is_metadata_only",
        ],
    )

    qa = gate_report(capture_dir, package_dir, decode_metadata, summary, skeleton, timeline, commands)
    write_json(package_dir / "qa_report.json", qa)

    hashes = collect_hashes(capture_dir, package_dir, label)
    write_csv(package_dir / "source_hashes.csv", hashes, ["path", "relative_to_capture", "size_bytes", "sha256"])
    package_manifest = {
        "schema": "magireco_runtime_evidence_package.v1",
        "label": label,
        "capture_dir": str(capture_dir),
        "package_dir": str(package_dir),
        "asset_manifests": str(args.asset_manifests.resolve()),
        "qa_status": qa["status"],
        "files": hashes,
    }
    write_json(package_dir / "package_manifest.json", package_manifest)

    print(
        json.dumps(
            {
                "package_dir": str(package_dir),
                "qa_status": qa["status"],
                "timeline_rows": len(timeline),
                "hashed_files": len(hashes),
                "summary": qa["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if qa["status"] == "passed_evidence_not_delivery" else 2


if __name__ == "__main__":
    raise SystemExit(main())
