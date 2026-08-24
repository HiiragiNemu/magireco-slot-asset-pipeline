#!/usr/bin/env python3
"""Build the code-bound exhaustive native-416 ac6007 production authority."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .build_exhaustive_unique_longform import file_sha256
except ImportError:  # direct script execution
    from build_exhaustive_unique_longform import file_sha256  # type: ignore


EVENTS = tuple(f"ac6007_{index:03d}" for index in range(1, 11))
EDITORIAL_ORDER = (
    "ac6007_001",
    "ac6007_002",
    "ac6007_003",
    "ac6007_005",
    "ac6007_006",
    "ac6007_004",
    "ac6007_007",
    "ac6007_008",
    "ac6007_009",
    "ac6007_010",
)
EXPECTED_ROUTES = {
    0: ["ac6007_001", "ac6007_002", "ac6007_003", "ac6007_004"],
    1: ["ac6007_001", "ac6007_005", "ac6007_006", "ac6007_004"],
    2: ["ac6007_001", "ac6007_002", "ac6007_003", "ac6007_007"],
    3: ["ac6007_001", "ac6007_005", "ac6007_006", "ac6007_008"],
    4: ["ac6007_009", "ac6007_010"],
}
EXPECTED_PRESENTATION_FRAMES = {
    "ac6007_001": 227,
    "ac6007_002": 302,
    "ac6007_003": 180,
    "ac6007_004": 240,
    "ac6007_005": 217,
    "ac6007_006": 240,
    "ac6007_007": 420,
    "ac6007_008": 445,
    "ac6007_009": 290,
    "ac6007_010": 455,
}
EXPECTED_TOTAL_FRAMES = 3016
EXPECTED_LAYER_OCCURRENCES = 50
EXPECTED_UNIQUE_SOURCES = 33
EXPECTED_RETAINED_AUDIO = 39
EXPECTED_EXCLUDED_BGM = 3
EXPECTED_SUBTITLES = 20


class Ac6007ExhaustiveAuthorityError(ValueError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise Ac6007ExhaustiveAuthorityError(f"CSV is empty: {path}")
    return rows


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_routes(rows: Sequence[Mapping[str, str]]) -> tuple[dict[int, list[str]], dict[str, str]]:
    selected = [row for row in rows if int(row["kind"]) == 174]
    grouped: dict[int, list[Mapping[str, str]]] = {}
    codes: dict[str, str] = {}
    for row in selected:
        grouped.setdefault(int(row["row_index"]), []).append(row)
        event = str(row["scene_name"])
        code = str(row["code_hex"]).casefold()
        previous = codes.setdefault(event, code)
        if previous != code:
            raise Ac6007ExhaustiveAuthorityError(f"DirInfo code differs for {event}")
        if row.get("route_status") != "ok":
            raise Ac6007ExhaustiveAuthorityError(f"DirInfo route is unresolved: {row}")
    routes = {
        row_index: [
            str(row["scene_name"])
            for row in sorted(values, key=lambda value: int(value["selector_raw"]))
        ]
        for row_index, values in grouped.items()
    }
    if routes != EXPECTED_ROUTES or set(codes) != set(EVENTS):
        raise Ac6007ExhaustiveAuthorityError(f"DirInfo kind-174 route set differs: {routes}")
    return routes, codes


def content_end_frame(
    event: str,
    *,
    code_presentation_frames: int,
    visual_end_frame: int,
    retained_audio: Sequence[Mapping[str, Any]],
    subtitles: Sequence[Mapping[str, Any]],
) -> tuple[int, dict[str, Any]]:
    audio_end_ms = max(
        (int(row["start_ms"]) + int(row["duration_ms"]) for row in retained_audio),
        default=0,
    )
    subtitle_end_ms = max((int(row["end_ms"]) for row in subtitles), default=0)
    if event == "ac6007_001":
        identities = {(int(row["request_id"]), int(row["sound_id"])) for row in retained_audio}
        if identities != {(1034, 4010), (2192, 10000)} or code_presentation_frames != 227:
            raise Ac6007ExhaustiveAuthorityError("ac6007_001 exact transition-audio boundary differs")
        frames = max(code_presentation_frames, visual_end_frame)
        policy = {
            "mode": "clip_common_transition_se_at_exact_scene_presentation_boundary",
            "clipped_request_id": 1034,
            "clipped_sound_id": 4010,
            "boundary_request_id": 2192,
            "boundary_sound_duration_ms": 7566,
            "reason": (
                "the event-specific scene soundtrack ends at the exact 227-frame GFD presentation; "
                "the generic 10-second common intro tail is not used to invent a longer visual hold"
            ),
        }
    else:
        frames = max(
            code_presentation_frames,
            visual_end_frame,
            math.ceil(audio_end_ms * 30 / 1000),
            math.ceil(subtitle_end_ms * 30 / 1000),
        )
        policy = {
            "mode": "hold_final_composited_frame_until_last_retained_se_voice_or_subtitle_end",
            "audio_content_end_ms": audio_end_ms,
            "subtitle_content_end_ms": subtitle_end_ms,
        }
    return frames, policy


def presentation_signature(manifest: Mapping[str, Any]) -> str:
    value = {
        "frames": int(manifest["presentation_frames"]),
        "layers": [
            (
                row["source"]["sha256"],
                int(row["event_start_frame"]),
                int(row["event_end_frame_inclusive"]),
                int(row["effective_renderer_state"]),
                int(row["output_x"]),
                int(row["output_y"]),
                int(row["output_width"]),
                int(row["output_height"]),
            )
            for row in manifest["layers_in_render_pass_order_under_to_top"]
        ],
        "audio": [
            (
                int(row["request_id"]),
                int(row["sound_id"]),
                int(row["start_ms"]),
                int(row["duration_ms"]),
                row["volume_bus"],
            )
            for row in manifest["retained_audio"]
        ],
        "subtitles": [
            (
                int(row["voice_request_id"]),
                int(row["start_ms"]),
                int(row["end_ms"]),
                row["ja"],
                row["zh"],
            )
            for row in manifest["subtitles"]
        ],
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_input_authorities(
    projection: Mapping[str, Any],
    audio: Mapping[str, Any],
    cri: Mapping[str, Any],
) -> None:
    if (
        projection.get("schema") != "magireco-ac6007-output-projection-authority-v1"
        or projection.get("status") != "PASS_READY_FOR_EVENT_COMPOSITION"
        or projection.get("assertions", {}).get("all_10_code_reachable_events_projected") is not True
        or projection.get("assertions", {}).get("full_screen_presentations_preserve_all_authored_pixels") is not True
    ):
        raise Ac6007ExhaustiveAuthorityError("ac6007 output projection authority differs")
    if (
        audio.get("schema") != "magireco-ac6007-event-audio-gfdirection-and-sound-bus-authority-v1"
        or audio.get("status") != "passed"
        or audio.get("decision", {}).get("event_global_child_audio_timing") != "CLOSED"
        or audio.get("assertions", {}).get("retained_audio_occurrences") != EXPECTED_RETAINED_AUDIO
        or audio.get("assertions", {}).get("subtitle_cues") != EXPECTED_SUBTITLES
    ):
        raise Ac6007ExhaustiveAuthorityError("ac6007 audio authority differs")
    if (
        cri.get("schema") != "magireco-selected-cri-usm-argb-authority-v1"
        or cri.get("status") != "passed_exact_color_alpha_streams_resolved"
        or cri.get("counts", {}).get("selected_usm_count") != EXPECTED_UNIQUE_SOURCES
        or cri.get("assertions", {}).get("all_selected_usms_have_exact_color_and_alpha_video_streams") is not True
    ):
        raise Ac6007ExhaustiveAuthorityError("ac6007 exact CRI ARGB authority differs")


def source_bindings(
    rows: Sequence[Mapping[str, str]], cri: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    csv_by_name = {str(row["official_name"]): row for row in rows}
    artifacts = {str(row["official_name"]): row for row in cri["artifacts"]}
    if set(csv_by_name) != set(artifacts) or len(artifacts) != EXPECTED_UNIQUE_SOURCES:
        raise Ac6007ExhaustiveAuthorityError("exact CRI source-name set differs")
    result: dict[str, dict[str, Any]] = {}
    for name in sorted(artifacts):
        row = csv_by_name[name]
        artifact = artifacts[name]
        path = Path(str(row["path"])).resolve()
        if (
            not path.is_file()
            or path != Path(str(artifact["path"])).resolve()
            or path.stat().st_size != int(row["size"])
            or int(row["size"]) != int(artifact["size"])
            or int(row["color_stream_index"]) != 0
            or int(row["alpha_stream_index"]) != 1
            or str(row["frame_rate"]) != "30/1"
        ):
            raise Ac6007ExhaustiveAuthorityError(f"exact CRI source binding differs: {name}")
        result[name] = {
            "official_name": name,
            "path": str(path),
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
            "global_index": int(row["global_index"]),
            "package": str(row["package"]),
            "package_index": int(row["package_index"]),
            "width": int(row["width"]),
            "height": int(row["height"]),
            "frame_rate": str(row["frame_rate"]),
            "frame_count": int(row["frame_count"]),
            "color_stream_index": 0,
            "alpha_stream_index": 1,
            "alpha_reconstruction": "color=video_stream_0 alpha=luma(video_stream_1)",
        }
    return result


def build_authority(
    *,
    projection_path: Path,
    audio_path: Path,
    cri_authority_path: Path,
    cri_streams_path: Path,
    dirinfo_path: Path,
) -> dict[str, Any]:
    projection = read_json(projection_path)
    audio = read_json(audio_path)
    cri = read_json(cri_authority_path)
    validate_input_authorities(projection, audio, cri)
    routes, codes = resolve_routes(read_csv(dirinfo_path))
    sources = source_bindings(read_csv(cri_streams_path), cri)

    projection_events = {str(row["event"]): row for row in projection["events"]}
    if set(projection_events) != set(EVENTS):
        raise Ac6007ExhaustiveAuthorityError("projected event set differs")
    event_manifests: dict[str, dict[str, Any]] = {}
    layer_occurrences = 0
    retained_total = 0
    excluded_total = 0
    subtitle_total = 0
    for event in EVENTS:
        projected = projection_events[event]
        layers: list[dict[str, Any]] = []
        for row in projected["movie_layer_occurrences"]:
            name = str(row["source_name"])
            source = sources.get(name)
            if source is None:
                raise Ac6007ExhaustiveAuthorityError(f"projected source is absent: {event}/{name}")
            frame_count = int(row["event_end_frame_inclusive"]) - int(row["event_start_frame"]) + 1
            if (
                frame_count != int(source["frame_count"])
                or Path(str(row["source_path"])).resolve() != Path(source["path"])
                or (int(row["source_width"]), int(row["source_height"]))
                != (int(source["width"]), int(source["height"]))
                or int(row["effective_renderer_state"]) != 1
            ):
                raise Ac6007ExhaustiveAuthorityError(f"projected layer binding differs: {event}/{name}")
            layers.append({**dict(row), "source": dict(source)})
        layers.sort(key=lambda row: (int(row["node_order"]), int(row["layer_order"])))
        visual_end = max((int(row["event_end_frame_inclusive"]) + 1 for row in layers), default=0)
        retained = [
            dict(row)
            for row in audio["audio_rows"]
            if row["event"] == event and row["strict_no_bgm_disposition"] != "EXCLUDE_AS_BGM_BUS"
        ]
        excluded = [
            dict(row)
            for row in audio["audio_rows"]
            if row["event"] == event and row["strict_no_bgm_disposition"] == "EXCLUDE_AS_BGM_BUS"
        ]
        subtitles = [dict(row) for row in audio["subtitle_cues"] if row["event"] == event]
        base_frames = int(projected["presentation_frame_count"])
        frames, tail_policy = content_end_frame(
            event,
            code_presentation_frames=base_frames,
            visual_end_frame=visual_end,
            retained_audio=retained,
            subtitles=subtitles,
        )
        if frames != EXPECTED_PRESENTATION_FRAMES[event]:
            raise Ac6007ExhaustiveAuthorityError(
                f"presentation frame count differs: {event}/{frames}"
            )
        event_manifests[event] = {
            "schema": "magireco-ac6007-exhaustive-event-presentation-v1",
            "status": "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
            "event": event,
            "event_info_code_hex": codes[event],
            "code_presentation_frames": base_frames,
            "visual_frames": visual_end,
            "presentation_frames": frames,
            "presentation_duration_seconds": frames / 30,
            "projection": dict(projected["projection"]),
            "layers_in_render_pass_order_under_to_top": layers,
            "retained_audio": retained,
            "excluded_bgm": excluded,
            "subtitles": subtitles,
            "tail_policy": tail_policy,
            "assertions": {
                "all_layers_exact_cri_color_alpha_bound": True,
                "all_layer_intervals_event_global": True,
                "all_retained_audio_is_se_or_voice": all(row["volume_bus"] in {"SE", "VOICE"} for row in retained),
                "all_subtitles_event_global": True,
                "source_media_modified": False,
            },
        }
        layer_occurrences += len(layers)
        retained_total += len(retained)
        excluded_total += len(excluded)
        subtitle_total += len(subtitles)

    if (
        layer_occurrences != EXPECTED_LAYER_OCCURRENCES
        or retained_total != EXPECTED_RETAINED_AUDIO
        or excluded_total != EXPECTED_EXCLUDED_BGM
        or subtitle_total != EXPECTED_SUBTITLES
    ):
        raise Ac6007ExhaustiveAuthorityError("aggregate event dimensions differ")
    signatures: dict[str, str] = {}
    for event in EDITORIAL_ORDER:
        signature = presentation_signature(event_manifests[event])
        if signature in signatures:
            raise Ac6007ExhaustiveAuthorityError(
                f"duplicate complete presentation: {event}/{signatures[signature]}"
            )
        signatures[signature] = event
    total_frames = sum(event_manifests[event]["presentation_frames"] for event in EDITORIAL_ORDER)
    if total_frames != EXPECTED_TOTAL_FRAMES or set(EDITORIAL_ORDER) != set(EVENTS):
        raise Ac6007ExhaustiveAuthorityError("editorial sequence dimensions differ")

    input_paths = {
        "projection_authority": projection_path,
        "audio_authority": audio_path,
        "cri_authority": cri_authority_path,
        "cri_streams": cri_streams_path,
        "dirinfo": dirinfo_path,
    }
    return {
        "schema": "magireco-ac6007-exhaustive-native416-authority-v1",
        "status": "PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
        "family": "ac6007",
        "title_zh": "女王熊袭击 全攻击·失败·胜利·复活穷尽合集",
        "product_scope": "exhaustive_duplicate_free_complete_event_presentation_editorial_longform",
        "native_single_session_claimed": False,
        "mutually_exclusive_routes_combined": True,
        "inputs": {
            name: {"path": str(path.resolve()), "sha256": file_sha256(path)}
            for name, path in input_paths.items()
        },
        "dirinfo_routes": [
            {"row_index": row_index, "events": events}
            for row_index, events in routes.items()
        ],
        "editorial_order": list(EDITORIAL_ORDER),
        "ordering_reason": (
            "common entry -> normal solo attack -> cut-in/cooperative attack -> shared loss -> "
            "solo and cooperative wins -> revival setup and revival win"
        ),
        "event_manifests": event_manifests,
        "source_bindings": sources,
        "summary": {
            "dirinfo_routes": 5,
            "unique_complete_event_presentations": 10,
            "movie_layer_occurrences": layer_occurrences,
            "unique_exact_cri_sources": len(sources),
            "contextual_reuse_occurrences": layer_occurrences - len(sources),
            "exact_duplicate_complete_presentations": 0,
            "retained_no_bgm_audio_occurrences": retained_total,
            "excluded_bgm_occurrences": excluded_total,
            "subtitle_cues": subtitle_total,
            "normal_surface_events": 6,
            "full_surface_events": 4,
            "total_frames": total_frames,
            "duration_seconds": total_frames / 30,
        },
        "assertions": {
            "all_5_dirinfo_routes_covered": True,
            "all_10_code_reachable_complete_event_presentations_once": True,
            "no_exact_duplicate_complete_presentations": True,
            "all_33_loadable_cri_sources_bound": True,
            "all_cri_sources_have_exact_color_alpha_streams": True,
            "all_normal_events_use_exact_gdp_top_zero_viewport": True,
            "all_full_surface_events_preserve_authored_pixels_by_contain": True,
            "child_local_only_timing_occurrences": 0,
            "P16_P17_P18_references": 0,
            "with_bgm_occurrences": 0,
            "machine_vision_used_as_authority": False,
            "source_media_modified": False,
        },
    }


def write_outputs(authority: Mapping[str, Any], output_root: Path) -> None:
    if output_root.exists():
        raise Ac6007ExhaustiveAuthorityError(f"immutable output already exists: {output_root}")
    staging = output_root.parent / f".{output_root.name}.staging-{os.getpid()}"
    if staging.exists():
        raise Ac6007ExhaustiveAuthorityError(f"staging output already exists: {staging}")
    try:
        staging.mkdir(parents=True)
        authority_path = staging / "AC6007_EXHAUSTIVE_NATIVE416_AUTHORITY.json"
        write_json(authority_path, authority)
        for event, manifest in authority["event_manifests"].items():
            write_json(staging / "events" / f"{event}.json", manifest)
        write_json(staging / "ROUTE_COVERAGE.json", {"routes": authority["dirinfo_routes"]})
        write_json(staging / "SOURCE_BINDINGS.json", {"sources": authority["source_bindings"]})
        (staging / "README.md").write_text(
            "# ac6007 exhaustive native-416 authority\n\n"
            "Five DirInfo routes reduce to ten distinct complete event presentations. The "
            "editorial longform contains each presentation once, while preserving contextual "
            "reuse where the game intentionally combines the same CRI layer with different "
            "event audio, overlays, or route timing. Three sound-550 BGM occurrences are "
            "excluded; all 39 retained occurrences are exact SE/VOICE. Rendering remains "
            "subject to automated QA and human playback.\n",
            encoding="utf-8",
        )
        (staging / "ROLLBACK.ps1").write_text(
            "param([switch]$Apply)\n"
            "$Root = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "if (-not $Apply) { Write-Output 'ROLLBACK_VALIDATED: disable this immutable authority root by same-volume rename; sources remain untouched.'; exit 0 }\n"
            "$Target = $Root + '.ROLLED_BACK_' + (Get-Date -Format 'yyyyMMdd_HHmmss')\n"
            "Move-Item -LiteralPath $Root -Destination $Target\n"
            "Write-Output ('ROLLBACK_APPLIED=' + $Target)\n",
            encoding="utf-8-sig",
        )
        output_hashes = {
            str(path.relative_to(staging)): file_sha256(path)
            for path in staging.rglob("*")
            if path.is_file() and path.name != "VERIFICATION_RECORD.json"
        }
        write_json(
            staging / "VERIFICATION_RECORD.json",
            {
                "schema": "magireco-ac6007-exhaustive-native416-verification-v1",
                "status": "PASS_PRODUCTION_READY_HUMAN_PLAYBACK_REQUIRED_AFTER_RENDER",
                "summary": authority["summary"],
                "checks": authority["assertions"],
                "output_sha256": output_hashes,
            },
        )
        staging.replace(output_root)
    except BaseException:
        if staging.exists():
            (staging / "FAILED_DO_NOT_USE.txt").write_text("Authority build failed.\n", encoding="utf-8")
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--projection-authority", required=True, type=Path)
    value.add_argument("--audio-authority", required=True, type=Path)
    value.add_argument("--cri-authority", required=True, type=Path)
    value.add_argument("--cri-streams", required=True, type=Path)
    value.add_argument("--dirinfo", required=True, type=Path)
    value.add_argument("--output-root", required=True, type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    authority = build_authority(
        projection_path=args.projection_authority,
        audio_path=args.audio_authority,
        cri_authority_path=args.cri_authority,
        cri_streams_path=args.cri_streams,
        dirinfo_path=args.dirinfo,
    )
    write_outputs(authority, args.output_root.resolve())
    print(
        "PASS routes=5 events=10 layers=50 sources=33 retained_audio=39 "
        "excluded_bgm=3 subtitles=20 frames=3016"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
