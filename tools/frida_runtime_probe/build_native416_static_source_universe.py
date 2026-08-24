#!/usr/bin/env python3
"""Build the complete static 416x232 CRI/Z2D family mother set.

This inventory is intentionally broader than the legacy audience inventory.  It
starts from every compiled CRI filename, binds the durable D: named-video probe
to that exact table, and then links every exact APK Z2D DGM reference back to
the probed source.  The result is a candidate universe, not production
approval: each audience family still needs its own Direction/event-global,
deduplication, audio, subtitle, loop, and tail authority before rendering.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import re
import subprocess
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

try:
    from .extract_named_z2d_chunks_from_apk import (
        NAME_COUNT,
        NAME_TABLE_OFFSET,
        Z2D_ADD_ENTRY,
        Z2D_BIN_ENTRY,
        parse_offsets,
        read_native_relative_name_table,
        validate_exact_binary,
    )
    from .extract_z2d_movie_layer_blend_authority import parse_z2d_header
except ImportError:  # pragma: no cover - direct script execution
    from extract_named_z2d_chunks_from_apk import (  # type: ignore
        NAME_COUNT,
        NAME_TABLE_OFFSET,
        Z2D_ADD_ENTRY,
        Z2D_BIN_ENTRY,
        parse_offsets,
        read_native_relative_name_table,
        validate_exact_binary,
    )
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        parse_z2d_header,
    )


SCHEMA = "magireco-native416-static-source-universe-v1"
FAMILY_RE = re.compile(r"^(ac\d{4})")
EVENT_RE = re.compile(r"ac\d{4}_\d{3}")
DGM_RE = re.compile(rb"(?:\[)?([A-Za-z0-9_]+\.dgm)(?:\])?\x00")
TARGET_WIDTH = 416
TARGET_HEIGHT = 232


class UniverseError(RuntimeError):
    """An exact input or fail-closed universe assertion differs."""


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    values = list(rows)
    fields: list[str] = []
    for row in values:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def family_of(value: str) -> str:
    match = FAMILY_RE.match(value or "")
    return match.group(1) if match else ""


def parse_pipe_events(value: str) -> list[str]:
    return EVENT_RE.findall(value or "")


def read_compiled_names(path: Path) -> list[str]:
    rows = read_csv(path)
    if not rows or not {"table_index", "name"}.issubset(rows[0]):
        raise UniverseError("compiled CRI filename table columns differ")
    ordered = sorted(rows, key=lambda row: int(row["table_index"]))
    indexes = [int(row["table_index"]) for row in ordered]
    if indexes != list(range(len(ordered))):
        raise UniverseError("compiled CRI filename table indexes are not contiguous")
    names = [row["name"] for row in ordered]
    if len(names) != len(set(names)):
        raise UniverseError("compiled CRI filename table contains duplicate names")
    return names


def align_catalog(
    catalog_rows: list[dict[str, str]], compiled_names: list[str]
) -> list[dict[str, str]]:
    if len(catalog_rows) != len(compiled_names):
        raise UniverseError("official catalog and compiled filename count differ")
    ordered = sorted(catalog_rows, key=lambda row: int(row["global_index"]))
    indexes = [int(row["global_index"]) for row in ordered]
    if indexes != list(range(len(ordered))):
        raise UniverseError("official catalog indexes are not contiguous")
    catalog_names = [row["official_name"] for row in ordered]
    if catalog_names != compiled_names:
        raise UniverseError("official catalog names differ from exact compiled order")
    return ordered


def resolve_durable_media_path(row: Mapping[str, str], media_root: Path) -> Path:
    directory = media_root / row["package"] / row["group"]
    exact = directory / f"{row['official_name']}.mp4"
    if exact.is_file():
        return exact
    collision = directory / f"{row['official_name']}_idx{row['global_index']}.mp4"
    if collision.is_file():
        return collision
    raise UniverseError(f"durable named media is absent: {row['official_name']}")


def ffprobe_media(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,nb_frames,duration",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8"
    )
    if completed.returncode:
        raise UniverseError(
            f"ffprobe failed for {path}: {completed.stderr.strip()}"
        )
    streams = json.loads(completed.stdout).get("streams", [])
    if len(streams) != 1:
        raise UniverseError(f"named media video stream count differs: {path}")
    stream = streams[0]
    return {
        "codec_name": stream.get("codec_name", ""),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frame_rate": str(stream.get("r_frame_rate", "")),
        "frame_count": int(stream.get("nb_frames") or 0),
        "duration_seconds": float(stream.get("duration") or 0.0),
    }


Probe = Callable[[Path], Mapping[str, Any]]


def probe_catalog(
    catalog_rows: list[dict[str, str]],
    media_root: Path,
    *,
    workers: int,
    probe: Probe = ffprobe_media,
) -> list[dict[str, Any]]:
    if workers < 1:
        raise UniverseError("workers must be positive")

    def one(row: dict[str, str]) -> dict[str, Any]:
        if row.get("source_exists") != "yes":
            return {
                **row,
                "durable_media_path": "",
                "media_open_status": "SOURCE_ABSENT",
                "codec_name": "",
                "width": "",
                "height": "",
                "frame_rate": "",
                "frame_count": "",
                "duration_seconds": "",
            }
        path = resolve_durable_media_path(row, media_root)
        metadata = dict(probe(path))
        return {
            **row,
            "durable_media_path": str(path.resolve()),
            "media_open_status": "PASS",
            **metadata,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(one, catalog_rows))


def extract_dgm_names(data: bytes) -> list[str]:
    result: list[str] = []
    for match in DGM_RE.finditer(data):
        value = match.group(1).decode("ascii")[:-4]
        if value not in result:
            result.append(value)
    return result


def scan_exact_z2d_archive(
    binary: Path,
    apk: Path,
    media_by_name: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    build_id = validate_exact_binary(binary)
    names = read_native_relative_name_table(binary, NAME_TABLE_OFFSET, NAME_COUNT)
    with zipfile.ZipFile(apk) as archive:
        z2d_info = archive.getinfo(Z2D_BIN_ENTRY)
        add_info = archive.getinfo(Z2D_ADD_ENTRY)
        blob = archive.read(Z2D_BIN_ENTRY)
        offsets = parse_offsets(archive.read(Z2D_ADD_ENTRY), len(blob))
    if len(names) + 1 != len(offsets):
        raise UniverseError("exact Z2D name and chunk counts differ")

    chunks: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    parse_errors = 0
    for index, name in enumerate(names):
        data = blob[offsets[index] : offsets[index + 1]]
        try:
            header = parse_z2d_header(data)
            header_status = "PASS"
            error = ""
        except Exception as exc:  # preserve malformed authored UI chunks
            header = {}
            header_status = "PARSE_BLOCKED_RECORDED"
            error = str(exc)
            parse_errors += 1
        dgm_names = extract_dgm_names(data)
        root = family_of(name)
        chunks.append(
            {
                "chunk_index": index,
                "z2d_name": name,
                "family_root": root,
                "chunk_offset": offsets[index],
                "chunk_size": offsets[index + 1] - offsets[index],
                "header_status": header_status,
                "header_error": error,
                "canvas_width": header.get("canvas_width", ""),
                "canvas_height": header.get("canvas_height", ""),
                "scene_frame_count": header.get("scene_frame_count", ""),
                "authored_dgm_count": len(dgm_names),
            }
        )
        for dgm_name in dgm_names:
            media = media_by_name.get(dgm_name)
            edges.append(
                {
                    "chunk_index": index,
                    "z2d_name": name,
                    "family_root": root,
                    "dgm_name": dgm_name,
                    "compiled_table_present": media is not None,
                    "source_exists": media.get("source_exists", "") if media else "",
                    "media_open_status": media.get("media_open_status", "") if media else "",
                    "width": media.get("width", "") if media else "",
                    "height": media.get("height", "") if media else "",
                    "frame_rate": media.get("frame_rate", "") if media else "",
                    "frame_count": media.get("frame_count", "") if media else "",
                    "duration_seconds": media.get("duration_seconds", "") if media else "",
                }
            )
    identity = {
        "binary_path": str(binary.resolve()),
        "binary_build_id": build_id,
        "binary_name_count": len(names),
        "apk_path": str(apk.resolve()),
        "z2d_bin_size": z2d_info.file_size,
        "z2d_bin_crc32": f"{z2d_info.CRC:08X}",
        "z2d_add_size": add_info.file_size,
        "z2d_add_crc32": f"{add_info.CRC:08X}",
        "z2d_header_parse_blocked_count": parse_errors,
    }
    return chunks, edges, identity


def load_statuses(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("families", [])
    result = {str(row["family"]): dict(row) for row in rows}
    if len(result) != len(rows):
        raise UniverseError("family status overlay contains duplicates")
    return result


def build_family_rows(
    media_rows: list[dict[str, Any]],
    z2d_edges: list[dict[str, Any]],
    event_info_rows: list[dict[str, str]],
    dirinfo_rows: list[dict[str, str]],
    statuses: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    sources_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in media_rows:
        if row.get("media_open_status") != "PASS":
            continue
        if (int(row["width"]), int(row["height"])) != (
            TARGET_WIDTH,
            TARGET_HEIGHT,
        ):
            continue
        root = family_of(str(row.get("group", "")))
        if root:
            sources_by_group[root].append(row)

    linked_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in z2d_edges:
        if not edge.get("family_root") or not edge.get("compiled_table_present"):
            continue
        if str(edge.get("width")) != str(TARGET_WIDTH) or str(
            edge.get("height")
        ) != str(TARGET_HEIGHT):
            continue
        linked_by_root[str(edge["family_root"])].append(edge)

    event_info_by_root: dict[str, set[str]] = defaultdict(set)
    for row in event_info_rows:
        root = family_of(row.get("base_name", ""))
        event = row.get("scene_name", "")
        if root and EVENT_RE.fullmatch(event):
            event_info_by_root[root].add(event)

    dirinfo_route_count: Counter[str] = Counter()
    dirinfo_events: dict[str, set[str]] = defaultdict(set)
    dirinfo_kinds: dict[str, set[int]] = defaultdict(set)
    dirinfo_dispositions: dict[str, set[str]] = defaultdict(set)
    dirinfo_production_states: dict[str, set[str]] = defaultdict(set)
    for row in dirinfo_rows:
        roots = {family_of(value) for value in (row.get("base_names", "")).split("|")}
        roots.discard("")
        events = parse_pipe_events(row.get("ordered_events", ""))
        roots.update(family_of(event) for event in events)
        roots.discard("")
        for root in roots:
            dirinfo_route_count[root] += 1
            dirinfo_events[root].update(event for event in events if family_of(event) == root)
            raw_kind = str(row.get("kind", "")).strip()
            if re.fullmatch(r"-?\d+", raw_kind):
                dirinfo_kinds[root].add(int(raw_kind))
            disposition = str(row.get("disposition", "")).strip()
            if disposition:
                dirinfo_dispositions[root].add(disposition)
            production_state = str(row.get("production_state", "")).strip()
            if production_state:
                dirinfo_production_states[root].add(production_state)

    roots = set(sources_by_group) | set(linked_by_root)
    result: list[dict[str, Any]] = []
    for root in roots:
        sources = sources_by_group.get(root, [])
        linked = linked_by_root.get(root, [])
        linked_names = sorted({str(edge["dgm_name"]) for edge in linked})
        status = dict(statuses.get(root, {}))
        state = str(status.get("state", "UNCLASSIFIED_CODE_AUDIT_PENDING"))
        blocker = str(status.get("blocker", ""))
        dispositions = dirinfo_dispositions.get(root, set())
        effect_or_material_only = bool(dispositions) and all(
            any(token in disposition.lower() for token in ("gameplay", "effect", "material", "component"))
            for disposition in dispositions
        )
        if state == "FAIL_CLOSED":
            lane = "P0_FAIL_CLOSED_NO_RENDER"
        elif state.startswith("PRODUCED_") or state.startswith("MATERIAL_"):
            lane = "P4_EXISTING_OUTPUT_REAUDIT_OR_REVIEW"
        elif effect_or_material_only:
            lane = "P3_GAMEPLAY_EFFECT_OR_MATERIAL_CLASSIFICATION"
        elif event_info_by_root.get(root) and dirinfo_route_count[root] and linked_names:
            lane = "P1_AUDIENCE_ROUTE_CODE_AUDIT"
        elif event_info_by_root.get(root) and linked_names:
            lane = "P2_DIRECT_EVENT_CODE_AUDIT"
        else:
            lane = "P3_GAMEPLAY_EFFECT_OR_MATERIAL_CLASSIFICATION"
        result.append(
            {
                "family_root": root,
                "priority_lane": lane,
                "status_state": state,
                "status_authority": status.get("authority", ""),
                "blocker": blocker,
                "source_group_native416_count": len(sources),
                "source_group_native416_total_frames": sum(
                    int(row.get("frame_count") or 0) for row in sources
                ),
                "z2d_linked_native416_unique_source_count": len(linked_names),
                "z2d_linked_native416_occurrence_count": len(linked),
                "z2d_linked_native416_source_names": "|".join(linked_names),
                "eventinfo_container_count": len(event_info_by_root.get(root, set())),
                "dirinfo_route_count": dirinfo_route_count[root],
                "dirinfo_event_count": len(dirinfo_events.get(root, set())),
                "dirinfo_kinds": "|".join(str(value) for value in sorted(dirinfo_kinds.get(root, set()))),
                "min_dirinfo_kind": min(dirinfo_kinds[root]) if dirinfo_kinds.get(root) else None,
                "dirinfo_dispositions": "|".join(sorted(dispositions)),
                "dirinfo_production_states": "|".join(
                    sorted(dirinfo_production_states.get(root, set()))
                ),
                "dirinfo_priority_hint_only_not_production_authority": True,
                "deep_authority_required_before_render": True,
                "production_allowed": False,
                "next_action": (
                    blocker
                    if lane == "P0_FAIL_CLOSED_NO_RENDER"
                    else "reverify existing output against current duplicate-free loop/tail contract"
                    if lane == "P4_EXISTING_OUTPUT_REAUDIT_OR_REVIEW"
                    else "resolve complete parent Direction/Z2D presentation, exact CRI sources, AV/subtitles, loops, tail, and duplicate-free editorial order"
                    if lane.startswith("P1") or lane.startswith("P2")
                    else "classify exact mechanism as audience gameplay/effect or material before any product is rendered"
                ),
            }
        )
    lane_order = {
        "P0_FAIL_CLOSED_NO_RENDER": 9,
        "P1_AUDIENCE_ROUTE_CODE_AUDIT": 0,
        "P2_DIRECT_EVENT_CODE_AUDIT": 1,
        "P3_GAMEPLAY_EFFECT_OR_MATERIAL_CLASSIFICATION": 2,
        "P4_EXISTING_OUTPUT_REAUDIT_OR_REVIEW": 8,
    }
    result.sort(
        key=lambda row: (
            lane_order[row["priority_lane"]],
            row["min_dirinfo_kind"] if row["min_dirinfo_kind"] is not None else 10**9,
            row["eventinfo_container_count"] or 10**9,
            row["source_group_native416_count"],
            row["family_root"],
        )
    )
    for index, row in enumerate(result, 1):
        row["queue_order"] = index
    return result


def build(
    *,
    binary: Path,
    apk: Path,
    compiled_table: Path,
    official_catalog: Path,
    media_root: Path,
    event_info: Path,
    dirinfo: Path,
    status_json: Path | None,
    output_dir: Path,
    workers: int,
) -> dict[str, Any]:
    if output_dir.exists():
        raise UniverseError(f"immutable output already exists: {output_dir}")
    compiled_names = read_compiled_names(compiled_table)
    catalog_rows = align_catalog(read_csv(official_catalog), compiled_names)
    media_rows = probe_catalog(catalog_rows, media_root, workers=workers)
    if any(row["media_open_status"] not in {"PASS", "SOURCE_ABSENT"} for row in media_rows):
        raise UniverseError("media probe state differs")
    media_by_name = {str(row["official_name"]): row for row in media_rows}
    z2d_chunks, z2d_edges, z2d_identity = scan_exact_z2d_archive(
        binary, apk, media_by_name
    )
    family_rows = build_family_rows(
        media_rows,
        z2d_edges,
        read_csv(event_info),
        read_csv(dirinfo),
        load_statuses(status_json),
    )
    native416_rows = [
        row
        for row in media_rows
        if row.get("media_open_status") == "PASS"
        and int(row["width"]) == TARGET_WIDTH
        and int(row["height"]) == TARGET_HEIGHT
    ]
    summary = {
        "schema": SCHEMA,
        "status": "PASS_FAIL_CLOSED_CANDIDATE_UNIVERSE",
        "compiled_cri_filename_count": len(compiled_names),
        "durable_media_probe_pass_count": sum(
            row["media_open_status"] == "PASS" for row in media_rows
        ),
        "source_absent_count": sum(
            row["media_open_status"] == "SOURCE_ABSENT" for row in media_rows
        ),
        "native416_source_count": len(native416_rows),
        "native416_source_group_count": len(
            {family_of(str(row["group"])) for row in native416_rows if family_of(str(row["group"]))}
        ),
        "native416_family_candidate_count": len(family_rows),
        "exact_z2d_chunk_count": len(z2d_chunks),
        "exact_z2d_dgm_edge_count": len(z2d_edges),
        "exact_z2d_header_parse_blocked_count": z2d_identity[
            "z2d_header_parse_blocked_count"
        ],
        "p1_audience_route_code_audit_count": sum(
            row["priority_lane"] == "P1_AUDIENCE_ROUTE_CODE_AUDIT"
            for row in family_rows
        ),
        "p2_direct_event_code_audit_count": sum(
            row["priority_lane"] == "P2_DIRECT_EVENT_CODE_AUDIT"
            for row in family_rows
        ),
        "p3_classification_count": sum(
            row["priority_lane"]
            == "P3_GAMEPLAY_EFFECT_OR_MATERIAL_CLASSIFICATION"
            for row in family_rows
        ),
        "fail_closed_count": sum(
            row["priority_lane"] == "P0_FAIL_CLOSED_NO_RENDER"
            for row in family_rows
        ),
        "existing_output_reaudit_count": sum(
            row["priority_lane"] == "P4_EXISTING_OUTPUT_REAUDIT_OR_REVIEW"
            for row in family_rows
        ),
        "source_inputs": {
            key: str(path)
            for key, path in {
                "binary": binary,
                "apk": apk,
                "compiled_table": compiled_table,
                "official_catalog": official_catalog,
                "event_info": event_info,
                "dirinfo": dirinfo,
                **({"status_json": status_json} if status_json is not None else {}),
            }.items()
        },
        "durable_media_root": str(media_root),
        "z2d_identity": z2d_identity,
        "source_media_modified": False,
        "media_reencoded": False,
        "production_approved_by_this_inventory": False,
    }
    output_dir.mkdir(parents=True)
    write_csv(output_dir / "ALL_COMPILED_CRI_MEDIA_PROBES.csv", media_rows)
    write_csv(output_dir / "NATIVE416_CRI_SOURCES.csv", native416_rows)
    write_csv(output_dir / "EXACT_Z2D_CHUNKS.csv", z2d_chunks)
    write_csv(output_dir / "EXACT_Z2D_DGM_EDGES.csv", z2d_edges)
    write_csv(output_dir / "NATIVE416_FAMILY_UNIVERSE.csv", family_rows)
    (output_dir / "NATIVE416_FAMILY_UNIVERSE.json").write_text(
        json.dumps(family_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        "# Native 416x232 static source universe\n\n"
        "This is the complete compiled CRI candidate mother set projected through exact APK Z2D references. It does not authorize rendering. Each P1/P2 family still requires exact parent Direction/Z2D, AV/subtitle, loop, tail, and duplicate-free editorial authority. P3 remains gameplay/effect/material classification. Source media was read only.\n",
        encoding="utf-8",
    )
    print(
        "PASS_NATIVE416_STATIC_UNIVERSE "
        f"compiled={len(compiled_names)} media_pass={summary['durable_media_probe_pass_count']} "
        f"native416_sources={len(native416_rows)} families={len(family_rows)} "
        f"p1={summary['p1_audience_route_code_audit_count']} "
        f"p2={summary['p2_direct_event_code_audit_count']} "
        f"p3={summary['p3_classification_count']} "
        f"blocked={summary['fail_closed_count']} root={output_dir}"
    )
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--compiled-table", type=Path, required=True)
    parser.add_argument("--official-catalog", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--event-info", type=Path, required=True)
    parser.add_argument("--dirinfo", type=Path, required=True)
    parser.add_argument("--status-json", type=Path)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    build(**vars(parse_args(argv)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
