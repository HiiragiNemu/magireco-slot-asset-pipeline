"""Extract every exact parent Z2D referenced by the complete ac4901 scene tree."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

try:
    from .extract_named_z2d_chunks_from_apk import (
        NAME_COUNT,
        NAME_TABLE_OFFSET,
        extract,
        read_native_relative_name_table,
    )
except ImportError:  # direct script execution
    from extract_named_z2d_chunks_from_apk import (  # type: ignore
        NAME_COUNT,
        NAME_TABLE_OFFSET,
        extract,
        read_native_relative_name_table,
    )


EXPECTED_EVENT_IDS = tuple(
    [f"ac4901_{index:03d}" for index in range(1, 91)]
    + [f"ac4901_{index:03d}" for index in (91, 92, 93, 94, 98, 105, 112)]
    + [f"ac4901_{index:03d}" for index in range(149, 257)]
)
EXPECTED_EVENT_COUNT = 205
EXPECTED_Z2D_OCCURRENCE_COUNT = 468
EXPECTED_UNIQUE_Z2D_COUNT = 108
EXPECTED_EXTRACTABLE_Z2D_COUNT = 103
EXPECTED_RUNTIME_ONLY_NODE_COUNT = 5


class AuthorityError(RuntimeError):
    pass


def validate_runtime_capture(runtime: dict[str, Any]) -> None:
    if runtime.get("status") != "PASSED":
        raise AuthorityError("ac4901 runtime capture is not PASSED")
    if runtime.get("transport") != "known_pid_single_session_127.0.0.1_27043":
        raise AuthorityError("ac4901 runtime capture transport differs")
    target_pid = runtime.get("target_pid")
    if not isinstance(target_pid, int) or target_pid <= 0:
        raise AuthorityError("ac4901 runtime capture target PID is invalid")
    if runtime.get("protected_processes_unchanged") is not True:
        raise AuthorityError("ac4901 runtime capture changed a protected process")
    if runtime.get("crash_buffer_unchanged") is not True:
        raise AuthorityError("ac4901 runtime capture changed the crash buffer")


def walk_nodes(node: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield node
    for child in node.get("children", []):
        yield from walk_nodes(child)


def normalize_z2d_name(name: str) -> str:
    return name[:-4] if name.casefold().endswith(".z2d") else name


def partition_archive_names(
    runtime_names: list[str], archive_names: set[str]
) -> tuple[list[str], list[str]]:
    extractable = sorted(name for name in runtime_names if name in archive_names)
    runtime_only = sorted(name for name in runtime_names if name not in archive_names)
    return extractable, runtime_only


def rebind_extracted_paths(extracted: dict[str, Any], final_root: Path) -> None:
    for row in extracted["chunks"]:
        row["output_path"] = str((final_root / f"{row['name']}.z2d").resolve())


def collect_event_z2d_bindings(
    runtime: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    events = runtime.get("events")
    if not isinstance(events, dict) or len(events) != EXPECTED_EVENT_COUNT:
        raise AuthorityError(f"ac4901 runtime event count differs: {len(events or {})}")
    foreign_events = sorted(
        event_name for event_name in events if not event_name.startswith("ac4901_")
    )
    if foreign_events:
        raise AuthorityError(f"foreign runtime event: {foreign_events[0]}")
    actual_event_ids = set(events)
    expected_event_ids = set(EXPECTED_EVENT_IDS)
    if actual_event_ids != expected_event_ids:
        missing = sorted(expected_event_ids - actual_event_ids)
        extra = sorted(actual_event_ids - expected_event_ids)
        raise AuthorityError(
            f"ac4901 exact event set differs: missing={missing} extra={extra}"
        )

    bindings: list[dict[str, Any]] = []
    all_names: list[str] = []
    for event_name in EXPECTED_EVENT_IDS:
        event = events[event_name]
        occurrences: list[dict[str, Any]] = []
        for scene in event.get("scenes", []):
            for cut in scene.get("cuts", []):
                for root in cut.get("nodes", []):
                    for node in walk_nodes(root):
                        if node.get("type") != 20:
                            continue
                        raw_name = str(node.get("name", ""))
                        name = normalize_z2d_name(raw_name)
                        if not name:
                            raise AuthorityError(
                                f"empty parent Z2D name in {event_name}"
                            )
                        motion_keys = [
                            {
                                "floats": key.get("floats"),
                                "flags": key.get("flags"),
                            }
                            for motion in node.get("motions", [])
                            for key in motion.get("keys", [])
                        ]
                        occurrences.append(
                            {
                                "scene": scene.get("name"),
                                "cut": cut.get("cut_name"),
                                "cut_start_frame": cut.get("cut_start_frame"),
                                "cut_end_frame": cut.get("cut_end_frame"),
                                "runtime_node_name": raw_name,
                                "z2d_name": name,
                                "motion_keys": motion_keys,
                            }
                        )
                        all_names.append(name)
        if not occurrences:
            raise AuthorityError(f"event lacks a parent Z2D node: {event_name}")
        bindings.append(
            {
                "event": event_name,
                "event_code": runtime.get("requested_events", {}).get(event_name),
                "z2d_occurrence_count": len(occurrences),
                "z2d_occurrences": occurrences,
            }
        )
    if len(all_names) != EXPECTED_Z2D_OCCURRENCE_COUNT:
        raise AuthorityError(
            f"ac4901 parent Z2D occurrence count differs: {len(all_names)}"
        )
    unique_names = sorted(set(all_names))
    if len(unique_names) != EXPECTED_UNIQUE_Z2D_COUNT:
        raise AuthorityError(
            f"ac4901 unique parent Z2D count differs: {len(unique_names)}"
        )
    return bindings, unique_names


def write_rollback(output_dir: Path, final_root: Path) -> None:
    escaped_root = str(final_root).replace("'", "''")
    text = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$root = '{escaped_root}'",
            "if (-not (Test-Path -LiteralPath $root)) { throw 'authority root is absent' }",
            "Write-Output 'ROLLBACK_VALIDATED: disable this immutable authority root by same-volume rename; exact APK and runtime inputs remain untouched.'",
            "",
        ]
    )
    (output_dir / "ROLLBACK.ps1").write_text(text, encoding="utf-8")


def build(
    *, runtime_path: Path, apk: Path, binary: Path, output_dir: Path
) -> dict[str, Any]:
    if output_dir.exists():
        raise AuthorityError(f"immutable output already exists: {output_dir}")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    validate_runtime_capture(runtime)
    bindings, unique_names = collect_event_z2d_bindings(runtime)
    stage = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
    if stage.exists():
        raise AuthorityError(f"staging output already exists: {stage}")
    try:
        archive_names = set(
            read_native_relative_name_table(binary, NAME_TABLE_OFFSET, NAME_COUNT)
        )
        extractable_names, runtime_only_names = partition_archive_names(
            unique_names, archive_names
        )
        if len(extractable_names) != EXPECTED_EXTRACTABLE_Z2D_COUNT:
            raise AuthorityError(
                "ac4901 exact archive-backed parent count differs: "
                f"{len(extractable_names)}"
            )
        if len(runtime_only_names) != EXPECTED_RUNTIME_ONLY_NODE_COUNT:
            raise AuthorityError(
                "ac4901 runtime-only type-20 node count differs: "
                f"{len(runtime_only_names)}"
            )
        extracted = extract(
            apk=apk,
            binary=binary,
            target_names=extractable_names,
            output_dir=stage,
        )
        rebind_extracted_paths(extracted, output_dir)
        (stage / "NAMED_Z2D_CHUNKS.json").write_text(
            json.dumps(extracted, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        extracted_by_name = {row["name"]: row for row in extracted["chunks"]}
        if set(extracted_by_name) != set(extractable_names):
            raise AuthorityError("exact extracted Z2D set differs from runtime set")
        report = {
            "schema": "magireco-ac4901-parent-z2d-event-bindings-v1",
            "status": "PASSED",
            "runtime_scene_motion": {
                "path": str(runtime_path.resolve()),
                "target_pid": runtime.get("target_pid"),
                "transport": runtime.get("transport"),
                "protected_processes_unchanged": runtime.get(
                    "protected_processes_unchanged"
                ),
                "crash_buffer_unchanged": runtime.get("crash_buffer_unchanged"),
            },
            "exact_apk": extracted["apk"],
            "exact_binary": extracted["binary"],
            "counts": {
                "events": len(bindings),
                "z2d_occurrences": sum(
                    row["z2d_occurrence_count"] for row in bindings
                ),
                "unique_runtime_type20_names": len(unique_names),
                "exact_archive_z2d_chunks": len(extractable_names),
                "runtime_only_type20_names": len(runtime_only_names),
            },
            "events": bindings,
            "exact_archive_z2d_names": extractable_names,
            "runtime_only_type20_names": runtime_only_names,
            "claim_boundary": (
                "The exact 205-event DirInfo set and runtime parent scene tree prove "
                "event-global parent Z2D selection and motion keys. Exact APK "
                "extraction proves authored Z2D bytes through archive and native "
                "name-table bindings. MovieLayer reachability and composition remain "
                "separate downstream gates."
            ),
            "source_media_modified": False,
        }
        (stage / "AC4901_PARENT_Z2D_EVENT_BINDINGS.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (stage / "README.md").write_text(
            "# ac4901 exact parent Z2D authority\n\n"
            "205 exact DirInfo/runtime event containers reference 468 type-20 "
            "occurrences: 103 unique exact APK Z2D chunks and 5 runtime-only "
            "numeric nodes. No media was rendered or modified.\n",
            encoding="utf-8",
        )
        write_rollback(stage, output_dir)
        output_names = (
            "AC4901_PARENT_Z2D_EVENT_BINDINGS.json",
            "NAMED_Z2D_CHUNKS.json",
            "README.md",
            "ROLLBACK.ps1",
        )
        verification = {
            "schema": "magireco-ac4901-parent-z2d-verification-v1",
            "status": "passed",
            "literal_result": (
                "PASS events=205 occurrences=468 unique=108 "
                "archive_z2d=103 runtime_only=5 protected_processes_unchanged=True "
                "crash_buffer_unchanged=True"
            ),
            "checks": {
                "exact_dirinfo_event_set": True,
                "all_events_have_parent_z2d": True,
                "all_103_archive_z2d_chunks_extracted": True,
                "five_runtime_only_nodes_are_numeric_counters": runtime_only_names
                == [
                    "ac8050_null_uwa_suji_keta",
                    "ac8050_tx_count_uwa_suji_0001",
                    "ac8050_tx_count_uwa_suji_0010",
                    "ac8050_tx_count_uwa_suji_0100",
                    "ac8050_tx_count_uwa_suji_1000",
                ],
                "known_pid_single_session": True,
                "protected_processes_unchanged": True,
                "crash_buffer_unchanged": True,
                "source_media_untouched": True,
            },
            "output_byte_counts": {
                name: (stage / name).stat().st_size for name in output_names
            },
            "preexisting_source_bindings": {
                "z2d_bin_zip_crc32": extracted["apk"]["z2d_bin_zip_crc32"],
                "z2d_add_zip_crc32": extracted["apk"]["z2d_add_zip_crc32"],
                "game_proc_inherited_sha256": extracted["binary"][
                    "inherited_sha256"
                ],
            },
        }
        if not all(verification["checks"].values()):
            raise AuthorityError("ac4901 parent Z2D verification check failed")
        (stage / "VERIFICATION_RECORD.json").write_text(
            json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stage.rename(output_dir)
    except Exception:
        if stage.exists():
            (stage / "FAILED_DO_NOT_USE.txt").write_text(
                "The staged authority is incomplete. Preserve it only as failure evidence.\n",
                encoding="utf-8",
            )
        raise
    occurrence_count = sum(row["z2d_occurrence_count"] for row in bindings)
    print(
        "PASS_AC4901_PARENT_Z2D "
        f"events={len(bindings)} occurrences={occurrence_count} "
        f"archive_z2d={len(extractable_names)} runtime_only={len(runtime_only_names)} "
        f"root={output_dir}"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    build(
        runtime_path=args.runtime_scene_motion,
        apk=args.apk,
        binary=args.binary,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
