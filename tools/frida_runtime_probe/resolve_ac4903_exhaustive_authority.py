#!/usr/bin/env python3
"""Resolve exact native-416 ac4903 exhaustive production evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .extract_z2d_movie_layer_blend_authority import (
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )
    from .resolve_ac1101_event_audio_authority import VOLUME_BUS, read_sound_divide_values
except ImportError:  # direct execution from repository root
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )
    from resolve_ac1101_event_audio_authority import (  # type: ignore
        VOLUME_BUS,
        read_sound_divide_values,
    )


FPS = 30
EVENTS = (
    "ac4903_001", "ac4903_002", "ac4903_003", "ac4903_004",
    "ac4903_005", "ac4903_006", "ac4903_007", "ac4903_008",
    "ac4903_009", "ac4903_010", "ac4903_011", "ac4903_012",
    "ac4903_013", "ac4903_015", "ac4903_016", "ac4903_018",
)
EDITORIAL_ORDER = (
    "ac4903_001", "ac4903_002", "ac4903_003", "ac4903_004",
    "ac4903_005", "ac4903_006", "ac4903_007", "ac4903_008",
    "ac4903_009", "ac4903_010", "ac4903_011", "ac4903_012",
    "ac4903_013", "ac4903_016", "ac4903_018", "ac4903_015",
)
EXPECTED_ROUTES = (
    ("ac4903_001", "ac4903_002"),
    ("ac4903_001", "ac4903_003"),
    ("ac4903_001", "ac4903_002", "ac4903_004"),
    ("ac4903_001", "ac4903_003", "ac4903_004"),
    ("ac4903_001", "ac4903_005"),
    ("ac4903_001", "ac4903_006"),
    ("ac4903_001", "ac4903_005", "ac4903_004"),
    ("ac4903_001", "ac4903_006", "ac4903_004"),
    ("ac4903_001", "ac4903_007", "ac4903_008"),
    ("ac4903_001", "ac4903_007", "ac4903_009"),
    ("ac4903_001", "ac4903_007", "ac4903_010"),
    ("ac4903_001", "ac4903_007", "ac4903_011"),
    ("ac4903_001", "ac4903_007", "ac4903_012"),
    ("ac4903_001", "ac4903_007", "ac4903_013"),
    ("ac4903_001", "ac4903_007", "ac4903_015"),
    ("ac4903_001", "ac4903_016", "ac4903_011"),
    ("ac4903_001", "ac4903_016", "ac4903_012"),
    ("ac4903_001", "ac4903_016", "ac4903_013"),
    ("ac4903_001", "ac4903_016", "ac4903_015"),
    ("ac4903_001", "ac4903_018", "ac4903_012"),
    ("ac4903_001", "ac4903_018", "ac4903_013"),
    ("ac4903_001", "ac4903_018", "ac4903_015"),
)
PARENT_BINDINGS = {
    "ac4903_001": (("ac4903_lev_c001_FB", 0, 89, 0),),
    "ac4903_002": (("ac4903_1on_s_c002", 0, 119, 0),),
    "ac4903_003": (("ac4903_1on_l_c003", 0, 164, 0),),
    "ac4903_004": (("ac4903_3on_c006_007_008", 0, 223, 0),),
    "ac4903_005": (("ac4903_1on_s_c004", 0, 119, 0),),
    "ac4903_006": (("ac4903_1on_l_c005", 0, 149, 0),),
    "ac4903_007": (("ac4903_1on_roul_c009_01", 0, 105, 0),),
    "ac4903_008": (("ac4903_3on_c010", 0, 179, 0),),
    "ac4903_009": (("ac4903_3on_c012", 0, 479, 0),),
    "ac4903_010": (("ac4903_3on_c011", 0, 479, 0),),
    "ac4903_011": (("ac4903_3on_c013", 0, 479, 0),),
    "ac4903_012": (("ac4903_3on_c014", 0, 479, 0),),
    "ac4903_013": (("ac4903_3on_c015", 0, 479, 0),),
    "ac4903_015": (
        ("ac4903_3on_c017", 0, 119, 0),
        ("ac8040_shouri_EF_small", 0, 259, 1),
    ),
    "ac4903_016": (("ac4903_1on_roul_c009_02", 0, 55, 0),),
    "ac4903_018": (("ac4903_1on_roul_c009_03", 0, 31, 0),),
}
CAPTION_BINDINGS = {
    "ac4903_002": (("cap4903_magimoni_nem_001", 8, 37),),
    "ac4903_003": (("cap4903_magimoni_nem_002", 8, 37),),
    "ac4903_004": (
        ("cap4903_magimoni_nem_005", 1, 73),
        ("cap4903_magimoni_tou_006", 96, 125),
    ),
    "ac4903_005": (("cap4903_magimoni_tou_003", 6, 35),),
    "ac4903_006": (("cap4903_magimoni_tou_004", 5, 34),),
    "ac4903_009": (("cap4903_magimoni_tou_007", 15, 44),),
    "ac4903_010": (("cap4903_magimoni_tou_008", 15, 44),),
    "ac4903_011": (("cap4903_magimoni_tou_009", 15, 44),),
    "ac4903_012": (("cap4903_magimoni_tou_010", 15, 44),),
    "ac4903_013": (("cap4903_magimoni_tou_011", 15, 44),),
    "ac4903_015": (("cap4903_magimoni_nem_013", 15, 44),),
}
UNREACHABLE_TO_LOADABLE_TWIN = {
    "ac8040_shouri_EF_small_add": "ac8040_shouri_EF_small",
    "ac8040_shouri_EF_small_add_LP": "ac8040_shouri_EF_small_LP",
}
EXPECTED_DIRECT_AUDIO = {
    ("ac4903_001", 1709, 8200, 0), ("ac4903_002", 1710, 8201, 0),
    ("ac4903_003", 1711, 8202, 0), ("ac4903_004", 226, 551, 5300),
    ("ac4903_004", 419, 1005, 0), ("ac4903_005", 1713, 8204, 0),
    ("ac4903_006", 1714, 8205, 0), ("ac4903_007", 1715, 8206, 0),
    ("ac4903_008", 1716, 8207, 0), ("ac4903_009", 226, 551, 2400),
    ("ac4903_009", 419, 1005, 0), ("ac4903_010", 226, 551, 2700),
    ("ac4903_010", 419, 1005, 0), ("ac4903_011", 226, 551, 3400),
    ("ac4903_011", 419, 1005, 0), ("ac4903_012", 226, 551, 3100),
    ("ac4903_012", 419, 1005, 0), ("ac4903_013", 231, 556, 4500),
    ("ac4903_013", 434, 1027, 0), ("ac4903_015", 228, 553, 4500),
    ("ac4903_015", 424, 1010, 0), ("ac4903_016", 1715, 8206, 0),
    ("ac4903_018", 1715, 8206, 0),
}
EXPECTED_VOICE_REQUESTS = {
    5602, 5603, 5604, 5384, 5382, 5383,
    5386, 5387, 5388, 5389, 5391, 5606,
}


class Ac4903AuthorityError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac4903AuthorityError(f"CSV is empty: {path}")
    return rows


def binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Ac4903AuthorityError(f"bound file is absent: {path}")
    return {"path": str(path.resolve()), "bytes": path.stat().st_size}


def frame_to_ms(frame: int) -> int:
    return round(frame * 1000 / FPS)


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def _node_range(node: Mapping[str, Any], label: str) -> tuple[int, int]:
    motions = node.get("motions", [])
    if len(motions) != 1 or motions[0].get("is_z2d_motion") is not True:
        raise Ac4903AuthorityError(f"runtime Z2D motion differs: {label}")
    keys = motions[0].get("keys", [])
    if len(keys) != 1 or len(keys[0].get("floats", [])) < 6:
        raise Ac4903AuthorityError(f"runtime Z2D key differs: {label}")
    values = keys[0]["floats"]
    starts = (values[0], values[2], values[4])
    if len(set(starts)) != 1 or int(starts[0]) != starts[0]:
        raise Ac4903AuthorityError(f"runtime Z2D start differs: {label}")
    return int(starts[0]), int(values[1])


def resolve_routes(rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        if int(row["kind"]) == 114:
            grouped[int(row["row_index"])].append(str(row["scene_name"]))
    routes = [tuple(grouped[index]) for index in range(22)]
    if sorted(grouped) != list(range(22)) or tuple(routes) != EXPECTED_ROUTES:
        raise Ac4903AuthorityError("ac4903 DirInfo route universe differs")
    return [{"row_index": index, "events": list(route)} for index, route in enumerate(routes)]


def extract_runtime_bindings(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if runtime.get("schema") != "magireco-ac4903-runtime-scene-motion-v1":
        raise Ac4903AuthorityError("runtime scene-motion schema differs")
    if runtime.get("host_frida_version") != "17.16.4":
        raise Ac4903AuthorityError("runtime Frida version differs")
    if runtime.get("protected_processes_unchanged") is not True or runtime.get("crash_tail_empty") is not True:
        raise Ac4903AuthorityError("runtime process/crash guard differs")
    events = runtime.get("events", {})
    if set(events) != set(EVENTS):
        raise Ac4903AuthorityError("runtime event set differs")
    result: dict[str, Any] = {}
    for event in EVENTS:
        scenes = [row for row in events[event].get("scenes", []) if row.get("name") == event]
        if len(scenes) != 1:
            raise Ac4903AuthorityError(f"runtime scene differs: {event}")
        cuts = [row for row in scenes[0].get("cuts", []) if row.get("cut_name") == event]
        if len(cuts) != 1 or int(cuts[0].get("instance_offset_frames", -1)) != 0:
            raise Ac4903AuthorityError(f"runtime cut differs: {event}")
        nodes = {
            str(row.get("name", "")).removesuffix(".z2d"): row
            for row in _walk_nodes(cuts[0].get("nodes", []))
            if row.get("type") == 20
        }
        parents = []
        for name, start, end, parent_order in PARENT_BINDINGS[event]:
            node = nodes.get(name)
            if node is None or _node_range(node, f"{event}/{name}") != (start, end):
                raise Ac4903AuthorityError(f"runtime parent binding differs: {event}/{name}")
            parents.append({
                "parent_z2d": name,
                "event_global_start_frame": start,
                "event_global_end_frame_inclusive": end,
                "parent_composition_order": parent_order,
            })
        captions = []
        expected_captions = CAPTION_BINDINGS.get(event, ())
        for name, start, end in expected_captions:
            node = nodes.get(name)
            if node is None or _node_range(node, f"{event}/{name}") != (start, end):
                raise Ac4903AuthorityError(f"runtime caption binding differs: {event}/{name}")
            captions.append({
                "z2d_name": name,
                "event_global_start_frame": start,
                "event_global_end_frame_inclusive": end,
            })
        if {name for name in nodes if name.startswith("cap4903_")} != {row[0] for row in expected_captions}:
            raise Ac4903AuthorityError(f"runtime caption set differs: {event}")
        result[event] = {
            "event_code": str(events[event]["event_code"]),
            "parents": parents,
            "captions": captions,
        }
    return result


def validate_renderer_authority(value: Mapping[str, Any], binary: Path) -> dict[str, Any]:
    if value.get("schema") != "magireco-ida-z2d-renderer-order-extract-v1" or value.get("status") != "PASS":
        raise Ac4903AuthorityError("IDA renderer-order authority differs")
    if Path(str(value.get("input_path", ""))).resolve() != binary.resolve():
        raise Ac4903AuthorityError("IDA authority is not bound to the exact Slot binary")
    targets = {str(row["label"]): row for row in value.get("targets", [])}
    required = {
        "RendererImplGL_setBlendMode", "CZ2DPlayer_DrawLayer",
        "CZ2DPlayGlobal_GetNextPrim", "CZ2DPlayBufferHandle_Exec_Sort",
        "CZ2DPlayBufferHandle_Exec_Draw",
    }
    if not required <= set(targets) or any(targets[name].get("decompile_error") for name in required):
        raise Ac4903AuthorityError("IDA renderer target set differs")
    blend = str(targets["RendererImplGL_setBlendMode"]["pseudocode"])
    draw_layer = str(targets["CZ2DPlayer_DrawLayer"]["pseudocode"])
    next_prim = str(targets["CZ2DPlayGlobal_GetNextPrim"]["pseudocode"])
    exec_draw = str(targets["CZ2DPlayBufferHandle_Exec_Draw"]["pseudocode"])
    if "glBlendFuncSeparate(770, 1, 1, 1)" not in blend or "n770 = 770" not in blend or "n768 = 771" not in blend:
        raise Ac4903AuthorityError("IDA GL blend-state contract differs")
    if "v24 + 8LL * (unsigned int)(v23 - 1)" not in draw_layer or "--v23" not in draw_layer:
        raise Ac4903AuthorityError("IDA reverse authored-layer traversal differs")
    if "*(_DWORD *)(v4 + 440) = v5 + 1" not in next_prim or "*(_QWORD *)(v7 + 8 * v5) = result" not in next_prim:
        raise Ac4903AuthorityError("IDA primitive append contract differs")
    if "v14 = *(__int64 **)(v12 + 464)" not in exec_draw or "++v14" not in exec_draw:
        raise Ac4903AuthorityError("IDA forward primitive draw contract differs")
    return {
        "renderer_state_1": {
            "rgb": "src_rgb*src_alpha + dst_rgb*(1-src_alpha)",
            "gl_blend_func_separate": [770, 771, 1, 771],
            "equation": 32774,
        },
        "renderer_state_3": {
            "rgb": "src_rgb*src_alpha + dst_rgb",
            "gl_blend_func_separate": [770, 1, 1, 1],
            "equation": 32774,
        },
        "movie_layer_draw_order": (
            "authored indices descend into the primitive list, which is then drawn forward; "
            "smaller authored index is later and topmost"
        ),
        "machine_vision_used_as_authority": False,
    }


def _probe_usm(path: Path, ffprobe: str) -> dict[str, Any]:
    command = [ffprobe, "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(path)]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode:
        raise Ac4903AuthorityError(f"ffprobe failed for {path}: {result.stderr}")
    value = json.loads(result.stdout)
    videos = [row for row in value.get("streams", []) if row.get("codec_type") == "video"]
    if len(videos) != 2:
        raise Ac4903AuthorityError(f"CRI USM lacks exact color+alpha streams: {path}")
    return {
        "video_stream_count": 2,
        "stream_indices": [int(row["index"]) for row in videos],
        "frame_counts": [
            int(row.get("nb_read_frames", row.get("nb_frames", -1))) for row in videos
        ],
        "frame_rates": [str(row.get("avg_frame_rate")) for row in videos],
        "dimensions": [[int(row["width"]), int(row["height"])] for row in videos],
        "codecs": [str(row.get("codec_name")) for row in videos],
    }


def resolve_movie_layers(
    *,
    binary: Path,
    named_manifest: Mapping[str, Any],
    filename_table_csv: Path,
    cri_authority: Mapping[str, Any],
    runtime_bindings: Mapping[str, Any],
    ffprobe: str,
) -> dict[str, Any]:
    build_id, blend_table, blend_offset = validate_exact_binary(binary)
    if (
        named_manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1"
        or named_manifest.get("status") != "passed"
    ):
        raise Ac4903AuthorityError("named Z2D authority differs")
    chunks = {str(row["name"]): row for row in named_manifest.get("chunks", [])}
    required_chunks = {row[0] for rows in PARENT_BINDINGS.values() for row in rows}
    if set(chunks) != required_chunks or len(chunks) != 17:
        raise Ac4903AuthorityError("exact parent Z2D set differs")
    compiled = read_filename_table(filename_table_csv)
    if (
        cri_authority.get("schema") != "magireco-selected-cri-usm-argb-authority-v1"
        or cri_authority.get("status") != "passed_exact_color_alpha_streams_resolved"
    ):
        raise Ac4903AuthorityError("CRI ARGB authority differs")
    artifacts = {
        str(row["official_name"]): dict(row)
        for row in cri_authority.get("artifacts", [])
    }
    if len(artifacts) != 35:
        raise Ac4903AuthorityError("exact CRI identity count differs")
    source_rows: dict[str, dict[str, Any]] = {}
    for name, artifact in sorted(artifacts.items()):
        path = Path(str(artifact["path"])).resolve()
        if not path.is_file() or compiled.get(name) != int(artifact["global_index"]):
            raise Ac4903AuthorityError(f"compiled CRI source binding differs: {name}")
        probe = _probe_usm(path, ffprobe)
        expected_frames = int(artifact["frame_count"])
        if (
            probe["frame_counts"] != [expected_frames, expected_frames]
            or probe["frame_rates"] != ["30/1", "30/1"]
        ):
            raise Ac4903AuthorityError(f"CRI stream frame grid differs: {name}")
        dimensions = [[int(artifact["width"]), int(artifact["height"])]] * 2
        if probe["dimensions"] != dimensions:
            raise Ac4903AuthorityError(f"CRI stream dimensions differ: {name}")
        source_rows[name] = {
            **artifact,
            "path": str(path),
            "bytes": path.stat().st_size,
            "probe": probe,
        }

    parsed_chunks: dict[str, Any] = {}
    all_authored: list[dict[str, Any]] = []
    for name, source in sorted(chunks.items()):
        path = Path(str(source["output_path"])).resolve()
        data = path.read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{name}.z2d" or header["frame_rate"] != 30.0:
            raise Ac4903AuthorityError(f"Z2D header differs: {name}")
        layers = []
        for reference in source.get("dgm_references", []):
            row = parse_movie_layer(data, str(reference), blend_table)
            identity = str(reference).removesuffix(".dgm")
            row.update({
                "parent_z2d": name,
                "source_identity": identity,
                "authored_tag_index": (
                    int(row["movie_layer_tag_value_hex"], 16) & 0x07FFFFFF
                ),
                "compiled_table_present": identity in compiled,
                "compiled_table_index": compiled.get(identity),
            })
            layers.append(row)
            all_authored.append(row)
        parsed_chunks[name] = {
            "name": name,
            "path": str(path),
            "bytes": path.stat().st_size,
            "header": header,
            "movie_layers": layers,
        }

    authored_by_name = {str(row["source_identity"]): row for row in all_authored}
    twin_rows = []
    for alias, twin in UNREACHABLE_TO_LOADABLE_TWIN.items():
        unreachable = authored_by_name.get(alias)
        loadable = authored_by_name.get(twin)
        if (
            unreachable is None
            or loadable is None
            or unreachable["compiled_table_present"] is not False
            or loadable["compiled_table_present"] is not True
        ):
            raise Ac4903AuthorityError(f"unreachable/loadable twin differs: {alias}")
        comparable = (
            "start_frame", "end_frame_inclusive", "position", "pivot",
            "layer_width", "layer_height",
        )
        if any(unreachable[key] != loadable[key] for key in comparable):
            raise Ac4903AuthorityError(f"unreachable/loadable interval differs: {alias}")
        twin_rows.append({
            "unreachable_authored_layer": alias,
            "loadable_same_interval_twin": twin,
            "unreachable_renderer_state": int(unreachable["effective_renderer_state"]),
            "loadable_renderer_state": int(loadable["effective_renderer_state"]),
            "decision": (
                "render the independently authored loadable layer only; do not copy "
                "the unreachable alias blend state onto it"
            ),
        })

    occurrences: list[dict[str, Any]] = []
    unreachable_occurrences: list[dict[str, Any]] = []
    for event in EVENTS:
        for parent in runtime_bindings[event]["parents"]:
            name = str(parent["parent_z2d"])
            chunk = parsed_chunks[name]
            expected_frames = (
                int(parent["event_global_end_frame_inclusive"])
                - int(parent["event_global_start_frame"])
                + 1
            )
            if int(chunk["header"]["scene_frame_count"]) != expected_frames:
                raise Ac4903AuthorityError(
                    f"runtime parent/Z2D span differs: {event}/{name}"
                )
            for layer in chunk["movie_layers"]:
                identity = str(layer["source_identity"])
                base = {
                    "event": event,
                    "parent_z2d": name,
                    "parent_composition_order": int(parent["parent_composition_order"]),
                    "source_identity": identity,
                    "authored_tag_index": int(layer["authored_tag_index"]),
                    "authored_blend_enum": int(layer["authored_blend_enum"]),
                    "effective_renderer_state": int(layer["effective_renderer_state"]),
                    "event_start_frame": (
                        int(parent["event_global_start_frame"])
                        + int(layer["start_frame"])
                    ),
                    "event_end_frame_exclusive": (
                        int(parent["event_global_start_frame"])
                        + int(layer["end_frame_inclusive"])
                        + 1
                    ),
                    "layer_width": int(layer["layer_width"]),
                    "layer_height": int(layer["layer_height"]),
                }
                if layer["compiled_table_present"] is not True:
                    unreachable_occurrences.append(base)
                    continue
                source_row = source_rows.get(identity)
                if (
                    source_row is None
                    or int(source_row["frame_count"])
                    != base["event_end_frame_exclusive"] - base["event_start_frame"]
                ):
                    raise Ac4903AuthorityError(
                        f"authored/source frame count differs: {event}/{identity}"
                    )
                occurrences.append({**base, "source": source_row})
    if (
        len(all_authored) != 41
        or len(occurrences) != 39
        or len(unreachable_occurrences) != 2
    ):
        raise Ac4903AuthorityError("MovieLayer occurrence dimensions differ")
    if {row["source_identity"] for row in occurrences} != set(source_rows):
        raise Ac4903AuthorityError("loadable MovieLayer identity coverage differs")
    if {
        row["source_identity"] for row in unreachable_occurrences
    } != set(UNREACHABLE_TO_LOADABLE_TWIN):
        raise Ac4903AuthorityError("unreachable MovieLayer alias set differs")
    return {
        "binary_build_id": build_id,
        "blend_state_table_file_offset_hex": f"0x{blend_offset:x}",
        "z2d_chunks": parsed_chunks,
        "source_media": source_rows,
        "loadable_occurrences": occurrences,
        "unreachable_occurrences": unreachable_occurrences,
        "unreachable_aliases_and_loadable_twins": twin_rows,
    }


def _translation_map(path: Path) -> tuple[dict[str, str], str]:
    value = read_json(path)
    rows = value.get("translations", [])
    mapping = {str(row["ja"]): str(row["zh"]) for row in rows}
    if len(rows) != 12 or len(mapping) != 12:
        raise Ac4903AuthorityError("ac4903 exhaustive translation dimensions differ")
    return mapping, str(value.get("status", ""))


def resolve_audio(
    *,
    binary: Path,
    runtime_bindings: Mapping[str, Any],
    event_audio_components: Path,
    z2d_sound_callbacks: Path,
    subtitle_timeline: Path,
    translation_path: Path,
    durable_audio_root: Path,
) -> dict[str, Any]:
    components = [
        row for row in read_csv(event_audio_components) if row.get("root") == "ac4903"
    ]
    observed = {
        (
            row["primary_animation"], int(row["leaf_request_id"]),
            int(row["leaf_sound_code"]), int(row["start_ms"]),
        )
        for row in components
    }
    if observed != EXPECTED_DIRECT_AUDIO or len(components) != 23:
        raise Ac4903AuthorityError("ac4903 direct event-audio universe differs")
    callback_rows = {
        row["z2d_name"]: row
        for row in read_csv(z2d_sound_callbacks)
        if row["z2d_name"].startswith("cap4903_magimoni_")
    }
    subtitle_rows = {
        (row["event_name"], row["z2d_name"], int(row["sound_request_id"])): row
        for row in read_csv(subtitle_timeline)
        if row["event_name"] in EVENTS and row["sound_request_id"]
    }
    translations, translation_status = _translation_map(translation_path)
    captions = [
        (event, row)
        for event in EVENTS
        for row in runtime_bindings[event]["captions"]
    ]
    if len(captions) != 12:
        raise Ac4903AuthorityError("runtime caption occurrence count differs")
    sound_ids = {int(row["leaf_sound_code"]) for row in components}
    for _, caption in captions:
        callback = callback_rows.get(str(caption["z2d_name"]))
        if callback is None:
            raise Ac4903AuthorityError(f"reqSound callback absent: {caption['z2d_name']}")
        sound_ids.add(int(callback["sound_resource_id"]))
    build_id, bus_values = read_sound_divide_values(binary, sound_ids)

    audio_rows: list[dict[str, Any]] = []
    for row in components:
        event = str(row["primary_animation"])
        request_id = int(row["leaf_request_id"])
        sound_id = int(row["leaf_sound_code"])
        start_ms = int(row["start_ms"])
        bus = VOLUME_BUS[bus_values[sound_id]]
        path = (durable_audio_root / row["ogg_name"]).resolve()
        if not path.is_file():
            raise Ac4903AuthorityError(f"durable official OGG absent: {path}")
        audio_rows.append({
            "event": event,
            "source_kind": "event_audio_component",
            "request_id": request_id,
            "sound_id": sound_id,
            "code_name": row["leaf_code_name"],
            "start_frame": None,
            "start_ms": start_ms,
            "duration_ms": int(row["duration_ms"]),
            "ogg_name": row["ogg_name"],
            "ogg_path": str(path),
            "ogg_bytes": path.stat().st_size,
            "volume_kind_value": bus_values[sound_id],
            "volume_bus": bus,
            "strict_no_bgm_disposition": (
                "EXCLUDE_AS_BGM_BUS" if bus == "BGM" else "RETAIN_VERIFIED_SE"
            ),
            "timing_evidence": "official_event_audio_component_event_global_start",
        })

    subtitles: list[dict[str, Any]] = []
    for event, caption in captions:
        name = str(caption["z2d_name"])
        callback = callback_rows[name]
        request_id = int(callback["sound_request_id"])
        sound_id = int(callback["sound_resource_id"])
        if (
            request_id not in EXPECTED_VOICE_REQUESTS
            or int(callback["exec_frame"]) != 0
            or callback["sound_request_match_count"] != "1"
        ):
            raise Ac4903AuthorityError(f"reqSound binding differs: {event}/{name}")
        if VOLUME_BUS[bus_values[sound_id]] != "VOICE":
            raise Ac4903AuthorityError(f"reqSound is not VOICE bus: {event}/{name}")
        source = subtitle_rows.get((event, name, request_id))
        if source is None:
            raise Ac4903AuthorityError(f"subtitle source absent: {event}/{name}")
        ja = source["srt_text"].replace("\\n", "\n")
        if ja not in translations:
            raise Ac4903AuthorityError(f"translation absent: {event}/{ja!r}")
        start_frame = int(caption["event_global_start_frame"])
        start_ms = frame_to_ms(start_frame)
        duration_ms = int(callback["sound_duration_ms"])
        visual_end_ms = frame_to_ms(
            int(caption["event_global_end_frame_inclusive"]) + 1
        )
        end_ms = max(start_ms + duration_ms, visual_end_ms)
        path = (durable_audio_root / callback["ogg_name"]).resolve()
        if not path.is_file():
            raise Ac4903AuthorityError(f"durable official OGG absent: {path}")
        audio_rows.append({
            "event": event,
            "source_kind": "z2d_req_sound",
            "z2d_name": name,
            "request_id": request_id,
            "sound_id": sound_id,
            "code_name": callback["sound_code_name"],
            "start_frame": start_frame,
            "start_ms": start_ms,
            "duration_ms": duration_ms,
            "ogg_name": callback["ogg_name"],
            "ogg_path": str(path),
            "ogg_bytes": path.stat().st_size,
            "volume_kind_value": bus_values[sound_id],
            "volume_bus": "VOICE",
            "strict_no_bgm_disposition": "RETAIN_VERIFIED_VOICE",
            "timing_evidence": (
                "same_run_parent_DGM_event_global_Z2D_key_plus_exact_"
                "child_callback_frame_0"
            ),
        })
        subtitles.append({
            "event": event,
            "z2d_name": name,
            "voice_request_id": request_id,
            "start_frame": start_frame,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "ja": ja,
            "zh": translations[ja],
            "evidence": "same-run runtime parent key + exact callback + official OGG",
        })

    audio_rows.sort(
        key=lambda row: (row["event"], int(row["start_ms"]), int(row["request_id"]))
    )
    subtitles.sort(
        key=lambda row: (
            row["event"], int(row["start_ms"]), int(row["voice_request_id"])
        )
    )
    excluded = [
        row for row in audio_rows
        if row["strict_no_bgm_disposition"] == "EXCLUDE_AS_BGM_BUS"
    ]
    expected_excluded = {
        ("ac4903_004", 226, 551), ("ac4903_009", 226, 551),
        ("ac4903_010", 226, 551), ("ac4903_011", 226, 551),
        ("ac4903_012", 226, 551), ("ac4903_013", 231, 556),
        ("ac4903_015", 228, 553),
    }
    if {
        (row["event"], row["request_id"], row["sound_id"]) for row in excluded
    } != expected_excluded:
        raise Ac4903AuthorityError("strict no-BGM exclusion set differs")
    retained = [row for row in audio_rows if row not in excluded]
    if (
        len(audio_rows) != 35
        or len(retained) != 28
        or len(excluded) != 7
        or len(subtitles) != 12
    ):
        raise Ac4903AuthorityError("audio/subtitle occurrence dimensions differ")
    return {
        "binary_build_id": build_id,
        "translation_status": translation_status,
        "audio_rows": audio_rows,
        "retained_audio_rows": retained,
        "excluded_bgm_rows": excluded,
        "subtitle_cues": subtitles,
    }


def event_manifests(
    runtime: Mapping[str, Any],
    movie: Mapping[str, Any],
    audio: Mapping[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for event in EVENTS:
        layers = [
            dict(row) for row in movie["loadable_occurrences"]
            if row["event"] == event
        ]
        layers.sort(
            key=lambda row: (
                int(row["parent_composition_order"]),
                -int(row["authored_tag_index"]),
            )
        )
        retained = [
            dict(row) for row in audio["retained_audio_rows"]
            if row["event"] == event
        ]
        excluded = [
            dict(row) for row in audio["excluded_bgm_rows"]
            if row["event"] == event
        ]
        subtitles = [
            dict(row) for row in audio["subtitle_cues"]
            if row["event"] == event
        ]
        visual_frames = max(int(row["event_end_frame_exclusive"]) for row in layers)
        audio_end_ms = max(
            (int(row["start_ms"]) + int(row["duration_ms"]) for row in retained),
            default=0,
        )
        subtitle_end_ms = max(
            (int(row["end_ms"]) for row in subtitles), default=0
        )
        presentation_frames = max(
            visual_frames,
            math.ceil(max(audio_end_ms, subtitle_end_ms) * FPS / 1000),
        )
        result[event] = {
            "event": event,
            "event_code": runtime[event]["event_code"],
            "native_dimensions": [416, 232],
            "frame_rate": "30/1",
            "visual_frames": visual_frames,
            "presentation_frames": presentation_frames,
            "visual_hold_frames_for_verified_audio_tail": (
                presentation_frames - visual_frames
            ),
            "layers_in_render_pass_order_under_to_top": layers,
            "retained_audio": retained,
            "excluded_bgm": excluded,
            "subtitles": subtitles,
            "strict_no_bgm": True,
            "child_local_only_timing": False,
        }
    if sum(int(row["presentation_frames"]) for row in result.values()) != 4204:
        raise Ac4903AuthorityError("exhaustive presentation frame count differs")
    return result


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    routes = resolve_routes(read_csv(args.dirinfo))
    runtime_document = read_json(args.runtime_scene_motion)
    runtime = extract_runtime_bindings(runtime_document)
    lockframe = read_json(args.runtime_lockframe)
    if (
        lockframe.get("schema") != "magireco-ac4903-runtime-lockframe-v1"
        or set(lockframe.get("events", {})) != set(EVENTS)
        or lockframe.get("protected_processes_unchanged") is not True
        or lockframe.get("crash_tail_empty") is not True
    ):
        raise Ac4903AuthorityError("runtime lock-frame authority differs")
    renderer = validate_renderer_authority(
        read_json(args.renderer_order_authority), args.binary
    )
    movie = resolve_movie_layers(
        binary=args.binary,
        named_manifest=read_json(args.named_z2d_authority),
        filename_table_csv=args.cri_filename_table,
        cri_authority=read_json(args.cri_argb_authority),
        runtime_bindings=runtime,
        ffprobe=args.ffprobe,
    )
    audio = resolve_audio(
        binary=args.binary,
        runtime_bindings=runtime,
        event_audio_components=args.event_audio_components,
        z2d_sound_callbacks=args.z2d_sound_callbacks,
        subtitle_timeline=args.subtitle_timeline,
        translation_path=args.translation,
        durable_audio_root=args.durable_audio_root,
    )
    manifests = event_manifests(runtime, movie, audio)
    return {
        "schema": "magireco-ac4903-exhaustive-native416-authority-v1",
        "status": "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
        "family": "ac4903",
        "product_scope": (
            "exhaustive_duplicate_free_event_presentation_editorial_longform"
        ),
        "native_dimensions": [416, 232],
        "frame_rate": "30/1",
        "editorial_order": list(EDITORIAL_ORDER),
        "natural_single_session_claimed": False,
        "mutually_exclusive_routes_combined": True,
        "route_count": len(routes),
        "routes": routes,
        "runtime_event_bindings": runtime,
        "renderer_contract": renderer,
        "movie_layer_authority": movie,
        "audio_authority": audio,
        "event_manifests": manifests,
        "summary": {
            "dirinfo_routes": 22,
            "unique_complete_event_presentations": 16,
            "authored_movie_layer_occurrences": 41,
            "loadable_movie_layer_occurrences": 39,
            "unique_loadable_cri_identities": 35,
            "code_unreachable_alias_occurrences": 2,
            "retained_no_bgm_audio_occurrences": 28,
            "excluded_bgm_occurrences": 7,
            "subtitle_cues": 12,
            "total_frames": 4204,
            "duration_seconds": 4204 / FPS,
        },
        "closed_gates": {
            "route_universe": "CLOSED_22_OF_22",
            "event_presentation_universe": "CLOSED_16_OF_16_ONCE",
            "movie_layer_reachability": (
                "CLOSED_35_LOADABLE_IDENTITIES_2_UNREACHABLE_ALIASES"
            ),
            "renderer_blend_and_order": "CLOSED_BY_EXACT_SLOT_IDA",
            "event_global_voice_subtitle_timing": (
                "CLOSED_12_OF_12_SAME_RUN_PARENT_KEYS"
            ),
            "strict_no_bgm": (
                "CLOSED_28_RETAINED_7_BGM_EXCLUDED_BY_SOUND_DIVIDE_TBL"
            ),
        },
        "assertions": {
            "all_22_dirinfo_routes_covered": True,
            "all_16_complete_event_presentations_once": True,
            "no_exact_duplicate_complete_presentations": True,
            "all_35_loadable_cri_sources_bound": True,
            "all_cri_sources_have_exact_color_alpha_streams": True,
            "renderer_state_1_and_3_code_closed": True,
            "child_local_only_timing_occurrences": 0,
            "P16_P17_P18_references": 0,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
        "input_bindings": [
            binding(path)
            for path in (
                args.binary, args.dirinfo, args.runtime_scene_motion,
                args.runtime_lockframe, args.named_z2d_authority,
                args.cri_argb_authority, args.renderer_order_authority,
                args.cri_filename_table, args.event_audio_components,
                args.z2d_sound_callbacks, args.subtitle_timeline,
                args.translation,
            )
        ],
        "production_decision": {
            "legacy_19_safe_routes_authoritative": False,
            "legacy_event_tail_lengths_authoritative": False,
            "event_015_old_component_blocker": (
                "CLOSED_AS_REQUIRED_LOADABLE_SAME_INTERVAL_LAYERS_EXIST"
            ),
            "new_exhaustive_longform_render_allowed": True,
            "human_playback_required": True,
            "publication_approved": False,
        },
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise Ac4903AuthorityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    main = output_dir / "AC4903_EXHAUSTIVE_NATIVE416_AUTHORITY.json"
    main.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    events = output_dir / "events"
    events.mkdir()
    for event, value in report["event_manifests"].items():
        (events / f"{event}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    source_bindings = {
        "schema": "magireco-ac4903-exhaustive-source-bindings-v1",
        "status": "PASS",
        "authority": binding(main),
        "inputs": report["input_bindings"],
        "event_manifests": {
            event: binding(events / f"{event}.json") for event in EVENTS
        },
        "source_media_modified": False,
    }
    (output_dir / "SOURCE_BINDINGS.json").write_text(
        json.dumps(source_bindings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    verification = {
        "schema": "magireco-ac4903-exhaustive-authority-verification-v1",
        "status": "PASS_READY_FOR_RENDER",
        "checks": report["summary"],
        "assertions": report["assertions"],
        "source_media_modified": False,
    }
    (output_dir / "VERIFICATION_RECORD.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        "# ac4903 native-416 exhaustive authority\n\n"
        "All 22 DirInfo routes are represented by 16 unique complete event "
        "presentations, each once. Exact runtime parent keys, APK MovieLayers, "
        "original CRI color+alpha streams, IDA draw/blend semantics and "
        "SOUND_DIVIDE_TBL close the render contract. The product is an exhaustive "
        "editorial collection, not a natural single-session claim. Human playback "
        "remains required.\n",
        encoding="utf-8",
    )
    (output_dir / "ROLLBACK.ps1").write_text(
        "param([switch]$Apply)\n"
        "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        "if (-not (Test-Path -LiteralPath (Join-Path $Root 'VERIFICATION_RECORD.json'))) { throw 'verification missing' }\n"
        "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: disable this immutable checkpoint by same-volume rename; sources remain untouched.'; exit 0 }\n"
        "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
        "Move-Item -LiteralPath $Root -Destination $Target\n"
        "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
        encoding="utf-8",
    )
    return main


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--binary", required=True, type=Path)
    value.add_argument("--dirinfo", required=True, type=Path)
    value.add_argument("--runtime-scene-motion", required=True, type=Path)
    value.add_argument("--runtime-lockframe", required=True, type=Path)
    value.add_argument("--named-z2d-authority", required=True, type=Path)
    value.add_argument("--cri-argb-authority", required=True, type=Path)
    value.add_argument("--renderer-order-authority", required=True, type=Path)
    value.add_argument("--cri-filename-table", required=True, type=Path)
    value.add_argument("--event-audio-components", required=True, type=Path)
    value.add_argument("--z2d-sound-callbacks", required=True, type=Path)
    value.add_argument("--subtitle-timeline", required=True, type=Path)
    value.add_argument("--translation", required=True, type=Path)
    value.add_argument("--durable-audio-root", required=True, type=Path)
    value.add_argument("--output-dir", required=True, type=Path)
    value.add_argument("--ffprobe", default="ffprobe")
    return value


def main() -> int:
    args = parser().parse_args()
    report = build_report(args)
    path = write_outputs(report, args.output_dir)
    print(
        "PASS routes=22 events=16 movie_occurrences=39 cri_identities=35 "
        "audio_retained=28 bgm_excluded=7 subtitles=12 frames=4204 "
        f"authority={path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
