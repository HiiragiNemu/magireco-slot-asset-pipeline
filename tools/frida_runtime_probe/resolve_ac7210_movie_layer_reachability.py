#!/usr/bin/env python3
"""Resolve ac7210 native-416 story reachability and component boundaries."""

from __future__ import annotations

import argparse
import csv
import filecmp
import json
import subprocess
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .extract_crivideo_filename_table_authority import CODE_AUTHORITY as CRI_CODE_AUTHORITY
    from .extract_z2d_movie_layer_blend_authority import (
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )
except ImportError:  # direct script execution
    from extract_crivideo_filename_table_authority import CODE_AUTHORITY as CRI_CODE_AUTHORITY  # type: ignore
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        CODE_AUTHORITY as Z2D_CODE_AUTHORITY,
        parse_movie_layer,
        parse_z2d_header,
        read_filename_table,
        validate_exact_binary,
    )


EVENTS = tuple(f"ac7210_{index:03d}" for index in range(1, 9))
NATIVE416_STORY_EVENTS = EVENTS[:5]
LOWER_PRIORITY_COMPONENT_EVENTS = EVENTS[5:]
DIRINFO_ROUTES = {
    0: ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_004"],
    1: ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_004"],
    2: ["ac7210_001", "ac7210_002", "ac7210_003", "ac7210_006"],
    3: ["ac7210_001", "ac7210_005", "ac7210_003", "ac7210_006"],
    4: ["ac7210_007", "ac7210_008"],
}
EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER = (
    "ac7210_001", "ac7210_002", "ac7210_005", "ac7210_003", "ac7210_004"
)
EXPECTED_MODULE = {
    "name": "split_config.arm64_v8a.apk",
    "path": (
        "/data/app/~~w196OEQ5FYrNgE6LHA9tnQ==/com.universal777.magireco-"
        "rHM8me-Z6EdQJaFV4cbnQA==/split_config.arm64_v8a.apk"
    ),
    "size": 80689936,
}

# event -> (scene, cut, instance offset, cut start, cut end)
EXPECTED_CUTS = {
    "ac7210_001": (("ac7210_001", "ac7210_001", 0, 0, 254),),
    "ac7210_002": (("ac7210_002", "ac7210_002", 0, 0, 179),),
    "ac7210_003": (("ac7210_003", "ac7210_003", 0, 0, 124),),
    "ac7210_004": (("ac7210_004", "ac7210_004", 0, 0, 207), ("ANTEN", "ac8040_001", 100, 0, 29)),
    "ac7210_005": (("ac7210_005", "ac7210_005", 0, 0, 148),),
    "ac7210_006": (("ac7210_006", "ac7210_006", 0, 0, 259), ("WIN", "ac8000_001", 140, 0, 259)),
    "ac7210_007": (("ac7210_007", "ac7210_007", 0, 0, 259),),
    "ac7210_008": (("ac7210_008", "ac7210_008", 0, 0, 510), ("WIN_fukkatu", "ac8000_001", 480, 0, 259)),
}

# event -> (scene, cut, parent Z2D, local start, local end, role)
EXPECTED_BINDINGS = {
    "ac7210_001": (
        ("ac7210_001", "ac7210_001", "ac7210_001", 0, 254, "story_visual"),
        ("ac7210_001", "ac7210_001", "ac7210_AT_ibu_cap_title", 10, 174, "presentation_overlay_416"),
        ("ac7210_001", "ac7210_001", "cap7210_hobaku_yac_001", 30, 80, "caption_audio_host"),
    ),
    "ac7210_002": (("ac7210_002", "ac7210_002", "ac7210_002", 0, 179, "story_visual"),),
    "ac7210_003": (("ac7210_003", "ac7210_003", "ac7210_003", 0, 124, "story_visual"),),
    "ac7210_004": (
        ("ac7210_004", "ac7210_004", "ac7210_004", 0, 213, "story_visual"),
        ("ac7210_004", "ac7210_004", "cap7210_hobaku_yac_004", 65, 94, "caption_audio_host"),
        ("ac7210_004", "ac7210_004", "cap7210_hobaku_tur_005", 65, 94, "caption_audio_host"),
        ("ANTEN", "ac8040_001", "ac8040_kyo_anten", 0, 29, "gameplay_effect_component_native208x120"),
    ),
    "ac7210_005": (
        ("ac7210_005", "ac7210_005", "ac7210_005", 0, 429, "story_visual"),
        ("ac7210_005", "ac7210_005", "cap7210_hobaku_tur_002", 15, 44, "caption_audio_host"),
    ),
    "ac7210_006": (
        ("ac7210_006", "ac7210_006", "ac7210_006_c01", 0, 44, "component_visual_512x416"),
        ("ac7210_006", "ac7210_006", "ac7210_006_c02", 45, 254, "component_visual_512x416"),
        ("ac7210_006", "ac7210_006", "ac8040_shouri_EF_large", 0, 259, "gameplay_effect_component_native320x256"),
        ("ac7210_006", "ac7210_006", "ac8040_shouri_EF_middle", 45, 244, "gameplay_effect_component_native320x256"),
        ("ac7210_006", "ac7210_006", "cap7210_hobaku_tur_003", 4, 70, "caption_audio_host"),
        ("WIN", "ac8000_001", "ac8000_cmn_tx_WIN", 0, 259, "gameplay_overlay_512x416"),
    ),
    "ac7210_007": (
        ("ac7210_007", "ac7210_007", "ac7210_007_c01", 0, 43, "component_visual_512x416"),
        ("ac7210_007", "ac7210_007", "ac7210_007_c02", 44, 192, "component_visual_512x416"),
        ("ac7210_007", "ac7210_007", "ac8040_shouri_EF_large", 0, 259, "gameplay_effect_component_native320x256"),
        ("ac7210_007", "ac7210_007", "ac8040_shouri_EF_middle", 44, 243, "gameplay_effect_component_native320x256"),
        ("ac7210_007", "ac7210_007", "cap7210_hobaku_ren_006", 6, 53, "caption_audio_host"),
        ("ac7210_007", "ac7210_007", "cap7210_hobaku_kae_007", 58, 87, "caption_audio_host"),
    ),
    "ac7210_008": (
        ("ac7210_008", "ac7210_008", "ac7210_008", 0, 509, "component_visual_512x416"),
        ("ac7210_008", "ac7210_008", "ac8040_shouri_EF_middle", 0, 199, "gameplay_effect_component_native320x256"),
        ("ac7210_008", "ac7210_008", "cap7210_hobaku_kae_008", 250, 347, "caption_audio_host"),
        ("ac7210_008", "ac7210_008", "cap7210_hobaku_ren_009", 352, 390, "caption_audio_host"),
        ("ac7210_008", "ac7210_008", "cap7210_hobaku_ren_010", 395, 475, "caption_audio_host"),
        ("WIN_fukkatu", "ac8000_001", "ac8000_cmn_tx_WIN", 0, 259, "gameplay_overlay_512x416"),
    ),
}
REQUIRED_Z2D_NAMES = tuple(dict.fromkeys(row[2] for values in EXPECTED_BINDINGS.values() for row in values))
EXPECTED_STORY_DUPLICATE_ALIAS = {
    "canonical": "ac7210_002_c03_LP_MR.dgm",
    "alias": "ac7210_002_c03_MR.dgm",
}
EXPECTED_DIMENSIONS = {
    "native416_story_visual": (416, 232),
    "native416_presentation_overlay": (416, 232),
    "native208x120_gameplay_effect_component": (208, 120),
    "native512x416_component_or_gameplay_visual": (512, 416),
    "native320x256_gameplay_effect_component": (320, 256),
}


class Ac7210ReachabilityError(ValueError):
    pass


def _walk_nodes(nodes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def _scene_cut(event: str, value: Mapping[str, Any], scene_name: str, cut_name: str) -> Mapping[str, Any]:
    scenes = [row for row in value.get("scenes", []) if row.get("name") == scene_name]
    if len(scenes) != 1:
        raise Ac7210ReachabilityError(f"runtime scene differs: {event}/{scene_name}")
    cuts = [row for row in scenes[0].get("cuts", []) if row.get("cut_name") == cut_name]
    if len(cuts) != 1:
        raise Ac7210ReachabilityError(f"runtime cut differs: {event}/{cut_name}")
    return cuts[0]


def _z2d_values(node: Mapping[str, Any], event: str, name: str) -> list[int]:
    motions = [row for row in node.get("motions", []) if row.get("is_z2d_motion") is True]
    if len(motions) != 1 or len(motions[0].get("keys", [])) != 1:
        raise Ac7210ReachabilityError(f"Z2D motion binding differs: {event}/{name}")
    values = motions[0]["keys"][0].get("floats", [])
    if len(values) < 6 or any(int(value) != value for value in values[:6]):
        raise Ac7210ReachabilityError(f"Z2D motion payload differs: {event}/{name}")
    return [int(value) for value in values]


def extract_runtime_bindings(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if runtime.get("schema") != "magireco-ac7210-runtime-scene-motion-v1":
        raise Ac7210ReachabilityError("runtime scene-motion schema differs")
    if runtime.get("host_frida_version") != "17.16.4":
        raise Ac7210ReachabilityError("runtime Frida version differs")
    if runtime.get("protected_processes_unchanged") is not True or runtime.get("crash_tail_empty") is not True:
        raise Ac7210ReachabilityError("runtime process-safety evidence differs")
    events, requested = runtime.get("events"), runtime.get("requested_events")
    if not isinstance(events, Mapping) or set(events) != set(EVENTS):
        raise Ac7210ReachabilityError("runtime event set differs")
    if not isinstance(requested, Mapping) or set(requested) != set(EVENTS):
        raise Ac7210ReachabilityError("requested runtime event set differs")
    result = {}
    for event in EVENTS:
        value = events[event]
        module = value.get("module", {})
        if any(module.get(key) != expected for key, expected in EXPECTED_MODULE.items()):
            raise Ac7210ReachabilityError(f"runtime ARM64 module differs: {event}")
        if value.get("event_code") != requested[event]:
            raise Ac7210ReachabilityError(f"runtime event code differs: {event}")
        cuts = EXPECTED_CUTS[event]
        if {row.get("name") for row in value.get("scenes", [])} != {row[0] for row in cuts}:
            raise Ac7210ReachabilityError(f"runtime scene set differs: {event}")
        offsets = {}
        for scene_name, cut_name, offset, start, end in cuts:
            cut = _scene_cut(event, value, scene_name, cut_name)
            observed = (int(cut.get("instance_offset_frames", -1)), int(cut.get("cut_start_frame", -1)), int(cut.get("cut_end_frame", -1)))
            if observed != (offset, start, end):
                raise Ac7210ReachabilityError(f"runtime cut interval differs: {event}/{cut_name}")
            offsets[(scene_name, cut_name)] = offset
        rows = []
        for scene_name, cut_name, name, start, end, role in EXPECTED_BINDINGS[event]:
            cut = _scene_cut(event, value, scene_name, cut_name)
            matches = []
            for node in _walk_nodes(cut.get("nodes", [])):
                observed = str(node.get("name", ""))
                if (observed[:-4] if observed.endswith(".z2d") else observed) == name:
                    matches.append(node)
            if len(matches) != 1:
                raise Ac7210ReachabilityError(f"runtime parent Z2D differs: {event}/{name}")
            values = _z2d_values(matches[0], event, name)
            if values[:2] != [start, end]:
                raise Ac7210ReachabilityError(f"runtime parent range differs: {event}/{name}")
            offset = offsets[(scene_name, cut_name)]
            rows.append({
                "scene_name": scene_name, "cut_name": cut_name,
                "cut_instance_offset_frames": offset, "parent_z2d": name, "role": role,
                "motion_values": values, "local_start_frame": start,
                "local_end_frame_inclusive": end, "event_global_start_frame": offset + start,
                "event_global_end_frame_inclusive": offset + end,
            })
        result[event] = rows
    return {"events": result}


def read_dirinfo_routes(path: Path) -> dict[int, list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for row in rows:
        if row.get("kind") == "201" and row.get("base_name") == "ac7210":
            if row.get("route_status") != "ok":
                raise Ac7210ReachabilityError("ac7210 DirInfo contains a non-ok row")
            grouped[int(row["row_index"])].append((int(row["selector_raw"]), row["scene_name"]))
    result = {number: [event for _, event in sorted(values)] for number, values in grouped.items()}
    if result != DIRINFO_ROUTES:
        raise Ac7210ReachabilityError(f"ac7210 DirInfo route map differs: {result}")
    return result


def _probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    completed = subprocess.run([
        ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames,nb_frames",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True, encoding="utf-8")
    streams = json.loads(completed.stdout).get("streams", [])
    if len(streams) != 1:
        raise Ac7210ReachabilityError(f"source video stream count differs: {path}")
    stream = streams[0]
    frames = stream.get("nb_read_frames") or stream.get("nb_frames")
    if stream.get("codec_name") != "h264" or stream.get("avg_frame_rate") != "30/1" or not frames:
        raise Ac7210ReachabilityError(f"source video codec/fps/frame count differs: {path}")
    return {"codec_name": "h264", "width": int(stream["width"]), "height": int(stream["height"]),
            "avg_frame_rate": "30/1", "frame_count": int(frames)}


def _source_path(media_root: Path, reference: str) -> Path:
    base = reference[:-4]
    return (media_root / base.split("_", 1)[0] / f"{base}.mp4").resolve()


def _content_class(parent: str) -> str:
    if parent in NATIVE416_STORY_EVENTS:
        return "native416_story_visual"
    if parent == "ac7210_AT_ibu_cap_title":
        return "native416_presentation_overlay"
    if parent == "ac8040_kyo_anten":
        return "native208x120_gameplay_effect_component"
    if parent.startswith("ac7210_") or parent == "ac8000_cmn_tx_WIN":
        return "native512x416_component_or_gameplay_visual"
    if parent.startswith("ac8040_shouri_EF_"):
        return "native320x256_gameplay_effect_component"
    raise Ac7210ReachabilityError(f"unclassified parent Z2D: {parent}")


def build_report(*, binary: Path, z2d_manifest_path: Path, filename_table_csv: Path,
                 runtime_scene_motion_path: Path, dirinfo_csv: Path, media_root: Path,
                 ffprobe: str) -> dict[str, Any]:
    build_id, blend_states, blend_offset = validate_exact_binary(binary)
    manifest = json.loads(z2d_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1" or manifest.get("status") != "passed":
        raise Ac7210ReachabilityError("named Z2D extraction differs")
    chunks = manifest.get("chunks", [])
    if {row.get("name") for row in chunks} != set(REQUIRED_Z2D_NAMES):
        raise Ac7210ReachabilityError("named Z2D set differs")
    if manifest.get("binary", {}).get("gnu_build_id") != build_id:
        raise Ac7210ReachabilityError("named Z2D binary build differs")
    runtime = extract_runtime_bindings(json.loads(runtime_scene_motion_path.read_text(encoding="utf-8")))
    routes = read_dirinfo_routes(dirinfo_csv)
    compiled = read_filename_table(filename_table_csv)
    parsed_chunks, all_layers = [], []
    for source in chunks:
        path = Path(source["output_path"])
        data = path.read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{source['name']}.z2d" or header["frame_rate"] != 30.0:
            raise Ac7210ReachabilityError(f"Z2D header differs: {source['name']}")
        layers = []
        for reference in source.get("dgm_references", []):
            layer = parse_movie_layer(data, reference, blend_states)
            table_index, classification = compiled.get(reference[:-4]), _content_class(source["name"])
            layer.update({"parent_z2d": source["name"], "content_class": classification,
                          "compiled_table_present": table_index is not None, "compiled_table_index": table_index,
                          "runtime_load_disposition": "LOADABLE_BY_EXACT_NAME" if table_index is not None else "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"})
            if table_index is not None:
                media = _source_path(media_root, reference)
                if not media.is_file():
                    raise Ac7210ReachabilityError(f"compiled DGM source is absent: {media}")
                probe = _probe_video(media, ffprobe)
                if (probe["width"], probe["height"]) != EXPECTED_DIMENSIONS[classification]:
                    raise Ac7210ReachabilityError(f"source dimensions differ: {reference}")
                layer.update({"media_path": str(media), "media_byte_count": media.stat().st_size, "media_probe": probe})
            else:
                layer.update({"media_path": "", "media_byte_count": 0, "media_probe": None})
            layers.append(layer); all_layers.append(layer)
        parsed_chunks.append({"name": source["name"], "path": str(path.resolve()), "header": header, "movie_layers": layers})

    story = [row for row in all_layers if row["content_class"] == "native416_story_visual"]
    if len(story) != 14 or any(not row["compiled_table_present"] for row in story):
        raise Ac7210ReachabilityError("native416 story MovieLayer set differs")
    equal_pairs = []
    for left, right in combinations(story, 2):
        if left["media_byte_count"] == right["media_byte_count"] and filecmp.cmp(left["media_path"], right["media_path"], shallow=False):
            equal_pairs.append({left["z2d_reference"], right["z2d_reference"]})
    if equal_pairs != [set(EXPECTED_STORY_DUPLICATE_ALIAS.values())]:
        raise Ac7210ReachabilityError(f"native416 story byte-identical pair set differs: {equal_pairs}")
    alias, canonical = EXPECTED_STORY_DUPLICATE_ALIAS["alias"], EXPECTED_STORY_DUPLICATE_ALIAS["canonical"]
    for row in story:
        row["audience_dedup_disposition"] = f"ALIAS_SKIP_USE_{canonical}" if row["z2d_reference"] == alias else "CANONICAL_RETAIN_ONCE"
    unreachable = [row for row in all_layers if not row["compiled_table_present"]]
    if {row["z2d_reference"] for row in unreachable} != {
        "ac8040_shouri_EF_large_add.dgm", "ac8040_shouri_EF_large_add_LP.dgm", "ac8040_shouri_EF_middle_add_LP.dgm"
    }:
        raise Ac7210ReachabilityError("authored non-loadable DGM set differs")
    canonical_story = [row for row in story if row["audience_dedup_disposition"] == "CANONICAL_RETAIN_ONCE"]
    route_rows = []
    for number, ordered in routes.items():
        components = [event for event in ordered if event in LOWER_PRIORITY_COMPONENT_EVENTS]
        route_rows.append({"dirinfo_row": number, "ordered_events": ordered,
                           "native416_story_events": [event for event in ordered if event in NATIVE416_STORY_EVENTS],
                           "lower_priority_component_events": components,
                           "native416_story_projection_status": "CLOSED",
                           "full_route_single_canvas_status": "NATIVE416_ONLY" if not components else "MIXED_416_PREFIX_AND_512_COMPONENT_TERMINAL"})
    return {
        "schema": "magireco-ac7210-movielayer-runtime-reachability-authority-v1", "status": "passed", "family": "ac7210",
        "binary": {"path": str(binary.resolve()), "size": binary.stat().st_size, "gnu_build_id": build_id},
        "inputs": {"named_z2d_manifest": str(z2d_manifest_path.resolve()),
                   "compiled_crivideo_filename_table": str(filename_table_csv.resolve()),
                   "runtime_scene_motion": str(runtime_scene_motion_path.resolve()),
                   "dirinfo_routes": str(dirinfo_csv.resolve()), "official_named_video_root": str(media_root.resolve())},
        "blend_state_table": {"file_offset_hex": f"0x{blend_offset:x}", "entry_count": len(blend_states),
                              "renderer_states_by_blend_enum_1_to_30": blend_states},
        "code_authority": [{"address": a, "function": f, "proves": p} for a, f, p in (*CRI_CODE_AUTHORITY, *Z2D_CODE_AUTHORITY)],
        "runtime_bindings": runtime, "dirinfo_routes": route_rows, "z2d_chunks": parsed_chunks, "movie_layers": all_layers,
        "exact_story_duplicate_alias": {**EXPECTED_STORY_DUPLICATE_ALIAS,
                                        "proof": "byte-identical official MP4 sources and two exact Z2D MovieLayer references",
                                        "audience_policy": "retain the canonical complete presentation once"},
        "decision": {"native416_story_events": list(NATIVE416_STORY_EVENTS),
                     "lower_priority_512_component_events": list(LOWER_PRIORITY_COMPONENT_EVENTS),
                     "native416_exhaustive_editorial_order": list(EXHAUSTIVE_NATIVE416_EDITORIAL_ORDER),
                     "native416_visual_reachability_gate": "CLOSED", "native416_canonical_story_source_count": len(canonical_story),
                     "native416_story_duplicate_alias_count": 1,
                     "native416_title_overlay_policy": "separate_gameplay_effect_not_clean_story",
                     "native208_dark_overlay_policy": "separate_material_or_effect_not_clean_story",
                     "native512_component_policy": "recorded_and_deferred_below_native416_priority",
                     "render_allowed_by_this_report_alone": False,
                     "remaining_independent_gate": "event_audio_sound_bus_and_event_global_subtitle_authority"},
        "assertions": {"dirinfo_route_count": 5, "runtime_event_count": 8, "required_z2d_count": len(REQUIRED_Z2D_NAMES),
                       "movie_layer_reference_count": len(all_layers), "loadable_movie_layer_count": len(all_layers) - len(unreachable),
                       "authored_nonloadable_alias_count": len(unreachable), "native416_story_layer_occurrence_count": len(story),
                       "native416_canonical_story_identity_count": len(canonical_story), "native416_byte_identical_pair_count": len(equal_pairs),
                       "all_native416_story_sources_are_416x232": True,
                       "all_story_sources_unique_after_alias_dedup": True,
                       "machine_vision_used_as_authority": False, "source_media_modified": False},
    }


def write_outputs(report: Mapping[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise Ac7210ReachabilityError(f"immutable output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path, layer_path = output_dir / "AC7210_MOVIELAYER_REACHABILITY_AUTHORITY.json", output_dir / "AC7210_DGM_SOURCE_ROWS.csv"
    route_path, verify_path, readme_path = output_dir / "AC7210_ROUTE_CLASSIFICATION.csv", output_dir / "VERIFICATION_RECORD.json", output_dir / "README.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path, rows in ((layer_path, report["movie_layers"]), (route_path, report["dirinfo_routes"])):
        fields = list(dict.fromkeys(field for row in rows for field in row))
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    readme_path.write_text(
        "# ac7210 MovieLayer and route authority\n\n"
        "Exact DirInfo, runtime scene keys, APK Z2D MovieLayers, the compiled CRI filename table, and official media probes close events 001..005 as the native 416x232 story universe. Events 006..008 are 512x416 component/gameplay presentations and remain a lower-priority separate track. Event 002 authors two names for one byte-identical 30-frame clip; the audience longform retains that presentation once. No media changed.\n",
        encoding="utf-8")
    verify_path.write_text(json.dumps({"schema": "magireco-ac7210-movielayer-verification-v1", "status": "passed",
                                       "checks": report["assertions"], "decision": report["decision"],
                                       "outputs": [report_path.name, layer_path.name, route_path.name, readme_path.name]},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path); parser.add_argument("--z2d-manifest", required=True, type=Path)
    parser.add_argument("--filename-table", required=True, type=Path); parser.add_argument("--runtime-scene-motion", required=True, type=Path)
    parser.add_argument("--dirinfo", required=True, type=Path); parser.add_argument("--media-root", required=True, type=Path)
    parser.add_argument("--ffprobe", default="ffprobe"); parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = build_report(binary=args.binary, z2d_manifest_path=args.z2d_manifest, filename_table_csv=args.filename_table,
                          runtime_scene_motion_path=args.runtime_scene_motion, dirinfo_csv=args.dirinfo,
                          media_root=args.media_root, ffprobe=args.ffprobe)
    write_outputs(report, args.output_dir)
    print("PASS routes=5 events=8 native416_story_events=5 story_layers=14 canonical_story=13 byte_identical_pairs=1 deferred_512_events=3 visual_gate=CLOSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
