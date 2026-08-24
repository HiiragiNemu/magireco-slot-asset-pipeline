"""Extract every exact parent Z2D referenced by the ac4902 runtime scene tree."""

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


EXPECTED_EVENT_COUNT = 64
EXPECTED_Z2D_OCCURRENCE_COUNT = 164
EXPECTED_UNIQUE_Z2D_COUNT = 55
EXPECTED_EXTRACTABLE_Z2D_COUNT = 50
EXPECTED_RUNTIME_ONLY_NODE_COUNT = 5


class AuthorityError(RuntimeError):
    pass


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


def rebind_extracted_paths(
    extracted: dict[str, Any], final_root: Path
) -> None:
    for row in extracted["chunks"]:
        row["output_path"] = str(
            (final_root / f"{row['name']}.z2d").resolve()
        )


def collect_event_z2d_bindings(
    runtime: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    events = runtime.get("events")
    if not isinstance(events, dict) or len(events) != EXPECTED_EVENT_COUNT:
        raise AuthorityError(
            f"ac4902 runtime event count differs: {len(events or {})}"
        )
    foreign_events = sorted(
        event_name for event_name in events if not event_name.startswith("ac4902_")
    )
    if foreign_events:
        raise AuthorityError(f"foreign runtime event: {foreign_events[0]}")
    bindings: list[dict[str, Any]] = []
    all_names: list[str] = []
    for event_name in sorted(events):
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
            f"ac4902 parent Z2D occurrence count differs: {len(all_names)}"
        )
    unique_names = sorted(set(all_names))
    if len(unique_names) != EXPECTED_UNIQUE_Z2D_COUNT:
        raise AuthorityError(
            f"ac4902 unique parent Z2D count differs: {len(unique_names)}"
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
    bindings, unique_names = collect_event_z2d_bindings(runtime)
    stage = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
    if stage.exists():
        raise AuthorityError(f"staging output already exists: {stage}")
    try:
        archive_names = set(
            read_native_relative_name_table(
                binary, NAME_TABLE_OFFSET, NAME_COUNT
            )
        )
        extractable_names, runtime_only_names = partition_archive_names(
            unique_names, archive_names
        )
        if len(extractable_names) != EXPECTED_EXTRACTABLE_Z2D_COUNT:
            raise AuthorityError(
                "ac4902 exact archive-backed parent count differs: "
                f"{len(extractable_names)}"
            )
        if len(runtime_only_names) != EXPECTED_RUNTIME_ONLY_NODE_COUNT:
            raise AuthorityError(
                "ac4902 runtime-only type-20 node count differs: "
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
            "schema": "magireco-ac4902-parent-z2d-event-bindings-v1",
            "status": "PASSED",
            "runtime_scene_motion": {
                "path": str(runtime_path.resolve()),
                "target_pid": runtime.get("target_pid"),
                "transport": runtime.get("transport"),
                "protected_processes_unchanged": runtime.get(
                    "protected_processes_unchanged"
                ),
                "crash_tail_empty": runtime.get("crash_tail_empty"),
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
                "The runtime parent scene tree proves event-global parent Z2D "
                "selection and motion keys. Exact APK extraction proves authored "
                "Z2D bytes through the archive CRC, native name-table index, byte "
                "offset, and byte length. MovieLayer reachability and media "
                "composition remain separate downstream gates."
            ),
            "source_media_modified": False,
        }
        (stage / "AC4902_PARENT_Z2D_EVENT_BINDINGS.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (stage / "README.md").write_text(
            "# ac4902 exact parent Z2D authority\n\n"
            "64 runtime event containers reference 164 type-20 occurrences: "
            "50 unique exact APK Z2D chunks and 5 runtime-only numeric nodes. "
            "No media was rendered or modified.\n",
            encoding="utf-8",
        )
        write_rollback(stage, output_dir)
        stage.rename(output_dir)
    except Exception:
        if stage.exists():
            (stage / "FAILED_DO_NOT_USE.txt").write_text(
                "The staged authority is incomplete. Preserve it only as failure evidence.\n",
                encoding="utf-8",
            )
        raise
    occurrence_count = sum(
        row["z2d_occurrence_count"] for row in bindings
    )
    print(
        "PASS_AC4902_PARENT_Z2D "
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
