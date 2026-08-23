#!/usr/bin/env python3
"""Close the code-reachable ac7205 native-video universe.

The report deliberately separates three questions:

* DirInfo proves every reachable event sequence.
* Runtime scene keys prove the parent Z2D intervals used by those events.
* Exact APK Z2D chunks and the compiled CRI filename table prove every DGM
  MovieLayer that can actually load.

This is source and presentation authority, not a native single-session claim.
The eventual audience product may place mutually exclusive presentations in a
logical editorial order, but it must retain each distinct complete AV
presentation once and keep the native-512 ac8050 terminal on a separate,
lower-priority gameplay-effect track.
"""

from __future__ import annotations

import argparse
import csv
import filecmp
import json
import subprocess
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .build_event_production_manifests import file_sha256
    from .extract_crivideo_filename_table_authority import (
        CODE_AUTHORITY as CRI_CODE_AUTHORITY,
    )
    from .extract_z2d_movie_layer_blend_authority import (
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )
except ImportError:  # direct script execution
    from build_event_production_manifests import file_sha256  # type: ignore
    from extract_crivideo_filename_table_authority import (  # type: ignore
        CODE_AUTHORITY as CRI_CODE_AUTHORITY,
    )
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )


EVENTS = tuple(f"ac7205_{index:03d}" for index in range(1, 23))
DEFERRED_NATIVE512_EVENTS = ("ac7205_018",)
NATIVE416_EVENTS = tuple(event for event in EVENTS if event not in DEFERRED_NATIVE512_EVENTS)

# This ordering follows the two entry colors, their four short outcomes, the
# shared long-form lead-in, the four explanatory outcomes, the three
# lead-in variants, and the two final choice variants.  It covers every
# native-416 event exactly once; it is editorial, not a native-session claim.
EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER = (
    "ac7205_001", "ac7205_003", "ac7205_004", "ac7205_005", "ac7205_006",
    "ac7205_002", "ac7205_019", "ac7205_020", "ac7205_021", "ac7205_022",
    "ac7205_007", "ac7205_011", "ac7205_012", "ac7205_013", "ac7205_014",
    "ac7205_008", "ac7205_009", "ac7205_010",
    "ac7205_015", "ac7205_016", "ac7205_017",
)

EXPECTED_RUNTIME_SHA256 = "21CA2892B8DB68A3A3CC5C13EA0327AA09C64F90D9EEA7506B5A9C35AB686086"
EXPECTED_DIRINFO_SHA256 = "44202FCB8186D9577C33A4A20C492CFC84BFDD94DEC4EE76EB22DF8F4444DC01"
EXPECTED_NAMED_Z2D_MANIFEST_SHA256 = "BA02B43978E5FE9C1C95F564E85C7FBA2F29E81FA970FD63357781EF53F56AAC"
EXPECTED_RUNTIME_ONLY_NODE_REPORT_SHA256 = "438C3DEB27BB65E7B26063EA17CA717CCCE36EFE5675EFFC9DA40940441CB752"

EXPECTED_MODULE = {
    "name": "split_config.arm64_v8a.apk",
    "path": (
        "/data/app/~~w196OEQ5FYrNgE6LHA9tnQ==/com.universal777.magireco-"
        "rHM8me-Z6EdQJaFV4cbnQA==/split_config.arm64_v8a.apk"
    ),
    "size": 80689936,
}

EXPECTED_ROUTE_LENGTHS = {2: 8, 3: 58, 4: 32}
EXPECTED_ROUTE_EVENT_FREQUENCIES = {
    "ac7205_001": 49, "ac7205_002": 49,
    "ac7205_003": 10, "ac7205_004": 10, "ac7205_005": 10, "ac7205_006": 10,
    "ac7205_007": 18,
    "ac7205_008": 16, "ac7205_009": 16, "ac7205_010": 16,
    "ac7205_011": 4, "ac7205_012": 4, "ac7205_013": 4, "ac7205_014": 4,
    "ac7205_015": 8, "ac7205_016": 8, "ac7205_017": 2, "ac7205_018": 40,
    "ac7205_019": 10, "ac7205_020": 10, "ac7205_021": 10, "ac7205_022": 10,
}

COMPILED_RESOURCE_NAMES = {
    "ac7205_news_1on_kok_L_dounyuu",
    "ac7205_news_3on_kok_L_01", "ac7205_news_3on_kok_L_02",
    "ac7205_news_3on_kok_L_03", "ac7205_news_3on_kok_L_gekiatu",
    "ac7205_news_3on_kok_L_hat",
    "ac7205_news_3on_kok_S_01", "ac7205_news_3on_kok_S_02",
    "ac7205_news_3on_kok_S_03", "ac7205_news_3on_kok_S_04",
    "ac7205_news_3on_kok_S_hat",
    "ac7205_news_gamen_lev_in", "ac7205_news_null",
    "ac7205_news_waku_blue_lp", "ac7205_news_waku_red_lp",
    "ac8050_ef_bg_uwa_zen_01", "ac8050_uwa_impact_ZEN_ef",
    "cap7205_news_qb_001", "cap7205_news_qb_002", "cap7205_news_qb_003",
    "cap7205_news_qb_004", "cap7205_news_qb_005",
}
RUNTIME_ONLY_NONRESOURCE_NODES = {
    "ac8050_null_uwa_suji_keta",
    "ac8050_tx_count_uwa_suji_1000", "ac8050_tx_count_uwa_suji_0100",
    "ac8050_tx_count_uwa_suji_0010", "ac8050_tx_count_uwa_suji_0001",
}
EXPECTED_EXACT_DUPLICATE_DGM_GROUPS = (
    frozenset({"ac7205_news_3on_kok_L_01.dgm", "ac7205_news_3on_kok_L_01_lp.dgm"}),
    frozenset({"ac7205_news_3on_kok_L_03.dgm", "ac7205_news_3on_kok_L_03_lp.dgm"}),
)

EXPECTED_DIMENSIONS = {
    "native416_family_source": (416, 232),
    "native512_gameplay_effect_source": (512, 416),
}

# Exact ARM64 libGameProc.so control flow for CGFDirectionNodeMotionZ2D.
# These bytes are captured per runtime motion key below; the mapping is not
# inferred from resource names such as ``_lp``.
MOTION_PLAYBACK_MODE = {
    0: "finite_no_extension",
    1: "clamp_last_frame",
    2: "loop_full_z2d_scene",
    3: "loop_from_z2d_scene_loop_frame",
    4: "loop_from_explicit_key_loop_frame",
}
MOTION_CODE_AUTHORITY = (
    (
        "0x42b12bc",
        "zg::CGFDirectionNodeMotionBase::GetKey",
        "reads motion-key byte +0x1e bit 0; a set bit keeps the final key selected after its nominal end",
    ),
    (
        "0x42b342c",
        "zg::CGFDirectionNodeMotionZ2D::SetKeyTime",
        "reads playback mode byte +0x1d; mode 2 uses fmod over the full Z2D scene and mode 3 uses CZ2DRoot::GetSceneLoopPointTime",
    ),
)


class Ac7205ReachabilityError(ValueError):
    pass


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def _node_name(node: Mapping[str, Any]) -> str:
    name = str(node.get("name", ""))
    return name[:-4] if name.endswith(".z2d") else name


def decode_motion_key_flags(flags: Iterable[Any]) -> dict[str, Any]:
    values = [int(value) for value in flags]
    if len(values) != 3 or any(value < 0 or value > 255 for value in values):
        raise Ac7205ReachabilityError(f"invalid runtime motion-key flags: {values}")
    mode = values[1]
    if mode not in MOTION_PLAYBACK_MODE:
        raise Ac7205ReachabilityError(f"unknown runtime Z2D playback mode: {mode}")
    return {
        "motion_key_flags": values,
        "motion_playback_mode_value": mode,
        "motion_playback_mode": MOTION_PLAYBACK_MODE[mode],
        "motion_key_persists_after_nominal_end": bool(values[2] & 1),
    }


def _motion_key(node: Mapping[str, Any], event: str) -> dict[str, Any]:
    motions = [row for row in node.get("motions", []) if row.get("is_z2d_motion") is True]
    if len(motions) != 1 or len(motions[0].get("keys", [])) != 1:
        raise Ac7205ReachabilityError(f"Z2D motion binding differs: {event}/{_node_name(node)}")
    key = motions[0]["keys"][0]
    values = key.get("floats", [])
    if len(values) < 6 or any(int(value) != value for value in values[:6]):
        raise Ac7205ReachabilityError(f"Z2D motion payload differs: {event}/{_node_name(node)}")
    result = {"motion_values": [int(value) for value in values]}
    result.update(decode_motion_key_flags(key.get("flags", [])))
    return result


def extract_runtime_bindings(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if runtime.get("schema") != "magireco-ac7205-runtime-scene-motion-v1":
        raise Ac7205ReachabilityError("runtime scene-motion schema differs")
    if runtime.get("host_frida_version") != "17.16.4":
        raise Ac7205ReachabilityError("runtime Frida version differs")
    if runtime.get("protected_processes_unchanged") is not True or runtime.get("crash_tail_empty") is not True:
        raise Ac7205ReachabilityError("runtime process-safety evidence differs")
    events, requested = runtime.get("events"), runtime.get("requested_events")
    if not isinstance(events, Mapping) or set(events) != set(EVENTS):
        raise Ac7205ReachabilityError("runtime event set differs")
    if not isinstance(requested, Mapping) or set(requested) != set(EVENTS):
        raise Ac7205ReachabilityError("requested runtime event set differs")

    result: dict[str, list[dict[str, Any]]] = {}
    observed_names: set[str] = set()
    for event in EVENTS:
        value = events[event]
        module = value.get("module", {})
        if any(module.get(key) != expected for key, expected in EXPECTED_MODULE.items()):
            raise Ac7205ReachabilityError(f"runtime ARM64 module differs: {event}")
        if value.get("event_code") != requested[event]:
            raise Ac7205ReachabilityError(f"runtime event code differs: {event}")
        expected_scene_count = 2 if event == "ac7205_018" else 1
        if len(value.get("scenes", [])) != expected_scene_count:
            raise Ac7205ReachabilityError(f"runtime scene count differs: {event}")
        rows: list[dict[str, Any]] = []
        for scene in value.get("scenes", []):
            cuts = scene.get("cuts", [])
            if len(cuts) != 1:
                raise Ac7205ReachabilityError(f"runtime cut count differs: {event}/{scene.get('name')}")
            cut = cuts[0]
            cut_start, cut_end = int(cut.get("cut_start_frame", -1)), int(cut.get("cut_end_frame", -1))
            if cut_start != 0:
                raise Ac7205ReachabilityError(f"runtime cut start differs: {event}/{cut.get('cut_name')}")
            expected_end = 239 if cut.get("cut_name") == "ac8050_004" else (99 if event in {
                "ac7205_001", "ac7205_002", "ac7205_003", "ac7205_004", "ac7205_005",
                "ac7205_006", "ac7205_007", "ac7205_015", "ac7205_018", "ac7205_019",
                "ac7205_020", "ac7205_021", "ac7205_022",
            } else 199)
            if cut_end != expected_end or int(cut.get("instance_offset_frames", -1)) != 0:
                raise Ac7205ReachabilityError(f"runtime cut interval differs: {event}/{cut.get('cut_name')}")
            for node in _walk_nodes(cut.get("nodes", [])):
                if not any(row.get("is_z2d_motion") is True for row in node.get("motions", [])):
                    continue
                name = _node_name(node)
                key = _motion_key(node, event)
                values = key["motion_values"]
                observed_names.add(name)
                rows.append({
                    "scene_name": str(scene.get("name", "")),
                    "cut_name": str(cut.get("cut_name", "")),
                    "cut_start_frame": cut_start,
                    "cut_end_frame_inclusive": cut_end,
                    "parent_z2d": name,
                    "motion_values": values,
                    "motion_key_flags": key["motion_key_flags"],
                    "motion_playback_mode_value": key["motion_playback_mode_value"],
                    "motion_playback_mode": key["motion_playback_mode"],
                    "motion_key_persists_after_nominal_end": key[
                        "motion_key_persists_after_nominal_end"
                    ],
                    "local_start_frame": values[0],
                    "local_end_frame_inclusive": values[1],
                    "event_global_start_frame": values[0],
                    "event_global_end_frame_inclusive": values[1],
                    "motion_frame_count": values[1] - values[0] + 1,
                    "resource_disposition": (
                        "compiled_z2d_resource" if name in COMPILED_RESOURCE_NAMES
                        else "runtime_only_nonresource_node"
                    ),
                })
        result[event] = rows
    if observed_names != COMPILED_RESOURCE_NAMES | RUNTIME_ONLY_NONRESOURCE_NODES:
        raise Ac7205ReachabilityError("runtime Z2D motion-name universe differs")
    return {"events": result, "observed_names": sorted(observed_names)}


def read_dirinfo_routes(path: Path) -> dict[int, list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for row in rows:
        if row.get("kind") == "199" and row.get("base_name") == "ac7205":
            if row.get("route_status") != "ok":
                raise Ac7205ReachabilityError("ac7205 DirInfo contains a non-ok row")
            grouped[int(row["row_index"])].append((int(row["selector_raw"]), row["scene_name"]))
    result = {number: [event for _, event in sorted(values)] for number, values in grouped.items()}
    if set(result) != set(range(98)) or len(set(map(tuple, result.values()))) != 98:
        raise Ac7205ReachabilityError("ac7205 DirInfo row universe differs")
    if Counter(map(len, result.values())) != Counter(EXPECTED_ROUTE_LENGTHS):
        raise Ac7205ReachabilityError("ac7205 DirInfo route lengths differ")
    if Counter(event for values in result.values() for event in values) != Counter(EXPECTED_ROUTE_EVENT_FREQUENCIES):
        raise Ac7205ReachabilityError("ac7205 DirInfo event frequencies differ")
    if set().union(*map(set, result.values())) != set(EVENTS):
        raise Ac7205ReachabilityError("ac7205 DirInfo event coverage differs")
    return result


def _probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    completed = subprocess.run([
        ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames,nb_frames",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True, encoding="utf-8")
    streams = json.loads(completed.stdout).get("streams", [])
    if len(streams) != 1:
        raise Ac7205ReachabilityError(f"source video stream count differs: {path}")
    stream = streams[0]
    frames = stream.get("nb_read_frames") or stream.get("nb_frames")
    if stream.get("codec_name") != "h264" or stream.get("avg_frame_rate") != "30/1" or not frames:
        raise Ac7205ReachabilityError(f"source video codec/fps/frame count differs: {path}")
    return {
        "codec_name": "h264", "width": int(stream["width"]), "height": int(stream["height"]),
        "avg_frame_rate": "30/1", "frame_count": int(frames),
    }


def _source_path(media_root: Path, reference: str) -> Path:
    base = reference[:-4]
    return (media_root / base.split("_", 1)[0] / f"{base}.mp4").resolve()


def _content_class(reference: str) -> str:
    return "native512_gameplay_effect_source" if reference.startswith("ac8050_") else "native416_family_source"


def _event_visual_signatures(runtime: Mapping[str, Any]) -> dict[str, tuple[Any, ...]]:
    signatures: dict[str, tuple[Any, ...]] = {}
    for event in NATIVE416_EVENTS:
        rows = runtime["events"][event]
        signatures[event] = tuple(
            (row["scene_name"], row["cut_name"], row["parent_z2d"],
             row["event_global_start_frame"], row["event_global_end_frame_inclusive"])
            for row in rows
        )
    if len(set(signatures.values())) != len(NATIVE416_EVENTS):
        raise Ac7205ReachabilityError("native416 complete visual presentation signatures are not unique")
    return signatures


def build_report(
    *, binary: Path, z2d_manifest_path: Path, runtime_only_nodes_path: Path,
    filename_table_csv: Path, runtime_scene_motion_path: Path, dirinfo_csv: Path,
    media_root: Path, ffprobe: str,
) -> dict[str, Any]:
    expected_hashes = {
        runtime_scene_motion_path: EXPECTED_RUNTIME_SHA256,
        dirinfo_csv: EXPECTED_DIRINFO_SHA256,
        z2d_manifest_path: EXPECTED_NAMED_Z2D_MANIFEST_SHA256,
        runtime_only_nodes_path: EXPECTED_RUNTIME_ONLY_NODE_REPORT_SHA256,
    }
    for path, expected in expected_hashes.items():
        if file_sha256(path) != expected:
            raise Ac7205ReachabilityError(f"hash-bound input differs: {path}")

    build_id, blend_states, blend_offset = validate_exact_binary(binary)
    manifest = json.loads(z2d_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1" or manifest.get("status") != "passed":
        raise Ac7205ReachabilityError("named Z2D extraction differs")
    chunks = manifest.get("chunks", [])
    if {row.get("name") for row in chunks} != COMPILED_RESOURCE_NAMES:
        raise Ac7205ReachabilityError("named Z2D resource set differs")
    if manifest.get("binary", {}).get("gnu_build_id") != build_id:
        raise Ac7205ReachabilityError("named Z2D binary build differs")
    runtime_only = json.loads(runtime_only_nodes_path.read_text(encoding="utf-8"))
    if set(runtime_only.get("runtime_only_names", [])) != RUNTIME_ONLY_NONRESOURCE_NODES:
        raise Ac7205ReachabilityError("runtime-only node set differs")

    runtime = extract_runtime_bindings(json.loads(runtime_scene_motion_path.read_text(encoding="utf-8")))
    routes = read_dirinfo_routes(dirinfo_csv)
    compiled = read_filename_table(filename_table_csv)
    parsed_chunks: list[dict[str, Any]] = []
    all_layers: list[dict[str, Any]] = []
    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in chunks:
        path = Path(source["output_path"])
        data = path.read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{source['name']}.z2d" or header["frame_rate"] != 30.0:
            raise Ac7205ReachabilityError(f"Z2D header differs: {source['name']}")
        layers: list[dict[str, Any]] = []
        for reference in source.get("dgm_references", []):
            layer = parse_movie_layer(data, reference, blend_states)
            table_index = compiled.get(reference[:-4])
            if table_index is None:
                raise Ac7205ReachabilityError(f"compiled DGM source is absent: {reference}")
            classification = _content_class(reference)
            media = _source_path(media_root, reference)
            if not media.is_file():
                raise Ac7205ReachabilityError(f"official DGM media is absent: {media}")
            probe = _probe_video(media, ffprobe)
            if (probe["width"], probe["height"]) != EXPECTED_DIMENSIONS[classification]:
                raise Ac7205ReachabilityError(f"source dimensions differ: {reference}")
            if probe["frame_count"] != int(layer["frame_count"]):
                raise Ac7205ReachabilityError(f"MovieLayer/source frame count differs: {reference}")
            layer.update({
                "parent_z2d": source["name"], "content_class": classification,
                "compiled_table_index": table_index, "media_path": str(media),
                "media_sha256": file_sha256(media), "media_byte_count": media.stat().st_size,
                "media_probe": probe, "runtime_load_disposition": "LOADABLE_BY_EXACT_COMPILED_NAME",
            })
            layers.append(layer)
            all_layers.append(layer)
            by_parent[source["name"]].append(layer)
        parsed_chunks.append({
            "name": source["name"], "path": str(path.resolve()), "header": header,
            "dgm_reference_status": source.get("dgm_reference_status"), "movie_layers": layers,
        })

    if len(all_layers) != 28:
        raise Ac7205ReachabilityError("authored DGM MovieLayer count differs")
    native416 = [row for row in all_layers if row["content_class"] == "native416_family_source"]
    native512 = [row for row in all_layers if row["content_class"] == "native512_gameplay_effect_source"]
    if len(native416) != 25 or len(native512) != 3:
        raise Ac7205ReachabilityError("native source class counts differ")

    # The runtime parent Z2D motion span is a shifted placement of the exact
    # authored MovieLayer interval.  This closes the old unresolved-duration
    # blocker without assuming the parent cut is the final audience duration.
    runtime_rows = [row for values in runtime["events"].values() for row in values]
    duration_bindings: list[dict[str, Any]] = []
    for parent, layers in sorted(by_parent.items()):
        starts = [int(row["start_frame"]) for row in layers]
        ends = [int(row["end_frame_inclusive"]) for row in layers]
        authored_span = max(ends) - min(starts) + 1
        if sum(int(row["frame_count"]) for row in layers) != authored_span:
            raise Ac7205ReachabilityError(f"authored MovieLayer timeline is not contiguous: {parent}")
        occurrences = [row for row in runtime_rows if row["parent_z2d"] == parent]
        if not occurrences or any(int(row["motion_frame_count"]) != authored_span for row in occurrences):
            raise Ac7205ReachabilityError(f"runtime parent span differs from MovieLayers: {parent}")
        duration_bindings.append({
            "parent_z2d": parent, "authored_start_frame": min(starts),
            "authored_end_frame_inclusive": max(ends), "authored_frame_count": authored_span,
            "runtime_occurrence_count": len(occurrences),
            "runtime_motion_ranges": [[row["event_global_start_frame"], row["event_global_end_frame_inclusive"]]
                                      for row in occurrences],
            "status": "EXACT_MOVIELAYER_SPAN_MATCHES_EVERY_RUNTIME_PARENT_OCCURRENCE",
        })

    equal_groups: list[frozenset[str]] = []
    for left, right in combinations(all_layers, 2):
        if left["media_byte_count"] == right["media_byte_count"] and filecmp.cmp(
            left["media_path"], right["media_path"], shallow=False
        ):
            equal_groups.append(frozenset({left["z2d_reference"], right["z2d_reference"]}))
    if set(equal_groups) != set(EXPECTED_EXACT_DUPLICATE_DGM_GROUPS):
        raise Ac7205ReachabilityError(f"exact DGM duplicate groups differ: {equal_groups}")
    alias_names = {next(name for name in group if name.endswith("_lp.dgm")) for group in equal_groups}
    for layer in all_layers:
        layer["source_identity_disposition"] = (
            "BYTE_IDENTICAL_LOOP_ALIAS_NOT_A_SEPARATE_SOURCE_IDENTITY"
            if layer["z2d_reference"] in alias_names else "CANONICAL_SOURCE_IDENTITY"
        )

    signatures = _event_visual_signatures(runtime)
    route_rows = [{"dirinfo_row": number, "ordered_events": ordered} for number, ordered in routes.items()]
    return {
        "schema": "magireco-ac7205-movielayer-runtime-reachability-authority-v1",
        "status": "passed", "family": "ac7205",
        "binary": {"path": str(binary.resolve()), "size": binary.stat().st_size, "gnu_build_id": build_id},
        "inputs": {
            "named_z2d_manifest": str(z2d_manifest_path.resolve()),
            "runtime_only_nodes": str(runtime_only_nodes_path.resolve()),
            "compiled_crivideo_filename_table": str(filename_table_csv.resolve()),
            "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
            "dirinfo_routes": str(dirinfo_csv.resolve()),
            "official_named_video_root": str(media_root.resolve()),
            "sha256": {str(path.resolve()): expected for path, expected in expected_hashes.items()},
        },
        "blend_state_table": {
            "file_offset_hex": f"0x{blend_offset:x}", "entry_count": len(blend_states),
            "renderer_states_by_blend_enum_1_to_30": blend_states,
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in (
                *CRI_CODE_AUTHORITY,
                *Z2D_CODE_AUTHORITY,
                *MOTION_CODE_AUTHORITY,
            )
        ],
        "runtime_bindings": runtime, "dirinfo_routes": route_rows,
        "z2d_chunks": parsed_chunks, "movie_layers": all_layers,
        "runtime_parent_duration_bindings": duration_bindings,
        "exact_byte_duplicate_dgm_groups": [sorted(group) for group in equal_groups],
        "native416_event_visual_signatures": {
            event: [list(row) for row in signature] for event, signature in signatures.items()
        },
        "product_standard": {
            "one_exhaustive_longform": True,
            "include_mutually_exclusive_outcomes": True,
            "complete_av_presentation_is_dedupe_unit": True,
            "logical_editorial_order_required": True,
            "native_single_session_claimed": False,
        },
        "decision": {
            "native416_events": list(NATIVE416_EVENTS),
            "native416_exhaustive_editorial_order": list(EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER),
            "deferred_native512_gameplay_effect_events": list(DEFERRED_NATIVE512_EVENTS),
            "native416_visual_reachability_gate": "CLOSED",
            "native416_source_occurrence_count": len(native416),
            "native416_canonical_source_identity_count": len(native416) - len(equal_groups),
            "native416_distinct_complete_visual_event_count": len(signatures),
            "native512_gameplay_effect_source_count": len(native512),
            "old_25_source_audit_superseded": True,
            "render_allowed_by_this_report_alone": False,
            "remaining_independent_gate": "event_audio_sound_bus_and_event_global_subtitle_authority",
        },
        "assertions": {
            "dirinfo_route_count": len(routes), "runtime_event_count": len(EVENTS),
            "runtime_z2d_motion_name_count": len(COMPILED_RESOURCE_NAMES | RUNTIME_ONLY_NONRESOURCE_NODES),
            "compiled_z2d_resource_count": len(COMPILED_RESOURCE_NAMES),
            "runtime_only_nonresource_node_count": len(RUNTIME_ONLY_NONRESOURCE_NODES),
            "authored_dgm_reference_count": len(all_layers),
            "native416_source_occurrence_count": len(native416),
            "native416_canonical_source_identity_count": len(native416) - len(equal_groups),
            "native416_byte_identical_alias_group_count": len(equal_groups),
            "native416_distinct_complete_visual_event_count": len(signatures),
            "native512_gameplay_effect_source_count": len(native512),
            "all_parent_movie_layer_durations_runtime_bound": True,
            "all_sources_exact_compiled_names": True,
            "all_sources_native_resolution": True,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
        "source_media_modified": False,
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac7205ReachabilityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "AC7205_MOVIELAYER_REACHABILITY_AUTHORITY.json"
    layer_path = output_dir / "AC7205_DGM_SOURCE_ROWS.csv"
    route_path = output_dir / "AC7205_ROUTE_ROWS.csv"
    verify_path = output_dir / "VERIFICATION_RECORD.json"
    readme_path = output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path, rows in ((layer_path, report["movie_layers"]), (route_path, report["dirinfo_routes"])):
        fields = list(dict.fromkeys(field for row in rows for field in row))
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    readme_path.write_text(
        "# ac7205 code-reachable MovieLayer authority\n\n"
        "DirInfo closes 98 route rows over 22 events. Exact runtime parent Z2D keys, APK MovieLayers, "
        "the compiled CRI filename table, and official media probes close 21 native-416 event presentations "
        "and 25 authored native-416 DGM occurrences (23 byte-unique source identities). Event ac7205_018 is "
        "a native-512 ac8050 gameplay-effect terminal and remains on a separate lower-priority track. Five "
        "runtime count/null nodes are not compiled Z2D resources and are not independent videos. No machine "
        "vision was used as authority and no source media changed. Audio/subtitle/no-BGM closure remains an "
        "independent gate before rendering.\n",
        encoding="utf-8",
    )
    verify_path.write_text(json.dumps({
        "schema": "magireco-ac7205-movielayer-verification-v1", "status": "passed",
        "checks": report["assertions"], "decision": report["decision"],
        "outputs": [report_path.name, layer_path.name, route_path.name, readme_path.name],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d-manifest", required=True, type=Path)
    parser.add_argument("--runtime-only-nodes", required=True, type=Path)
    parser.add_argument("--filename-table", required=True, type=Path)
    parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--dirinfo", required=True, type=Path)
    parser.add_argument("--media-root", required=True, type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        binary=args.binary, z2d_manifest_path=args.z2d_manifest,
        runtime_only_nodes_path=args.runtime_only_nodes,
        filename_table_csv=args.filename_table, runtime_scene_motion_path=args.runtime_scene_motion,
        dirinfo_csv=args.dirinfo, media_root=args.media_root, ffprobe=args.ffprobe,
    )
    write_outputs(report, args.output_dir)
    print(
        "PASS routes=98 events=22 native416_events=21 native416_dgm=25 "
        "canonical_source_identities=23 complete_visual_presentations=21 "
        "deferred_native512_events=1 visual_gate=CLOSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
