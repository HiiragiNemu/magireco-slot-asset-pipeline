from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REQUIRED_EVENTS = tuple(f"ac0908_{index:03d}" for index in range(1, 18))
EXPECTED_ALIASES = {
    "ac8004_001": ("ac0908_010", "ac0908_013"),
    "ac8004_003": ("ac0908_011", "ac0908_014"),
    "ac8004_004": ("ac0908_012", "ac0908_015"),
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def motion_structure(motion: dict[str, Any]) -> dict[str, Any]:
    return {
        "is_z2d_motion": motion.get("is_z2d_motion"),
        "keys": [
            {
                "index": key.get("index"),
                "floats": key.get("floats"),
                "flags": key.get("flags"),
            }
            for key in motion.get("keys", [])
        ],
    }


def node_structure(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": node.get("type"),
        "name": node.get("name"),
        "motions": [motion_structure(row) for row in node.get("motions", [])],
        "children": [node_structure(row) for row in node.get("children", [])],
    }


def cut_structure(cut: dict[str, Any]) -> dict[str, Any]:
    return {
        "cut_name": cut["cut_name"],
        "instance_offset_frames": int(cut["instance_offset_frames"]),
        "cut_start_frame": int(cut["cut_start_frame"]),
        "cut_end_frame": int(cut["cut_end_frame"]),
        "nodes": [node_structure(row) for row in cut.get("nodes", [])],
    }


def structure_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def cut_frames(cut: dict[str, Any]) -> int:
    start = int(cut["cut_start_frame"])
    end = int(cut["cut_end_frame"])
    offset = int(cut["instance_offset_frames"])
    if offset < 0 or end < start:
        raise ValueError(f"invalid cut interval: {cut}")
    return offset + end - start + 1


def descendants(node: dict[str, Any]):
    yield node
    for child in node.get("children", []):
        yield from descendants(child)


def z2d_names(cut: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for root in cut.get("nodes", []):
        for node in descendants(root):
            name = node.get("name")
            if isinstance(name, str) and name.endswith(".z2d"):
                result.append(name)
    return result


def load_audio_spans(prior: dict[str, Any]) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for row in prior.get("event_containers", []):
        value = row.get("static_audio_component_span_ms")
        result[row["event"]] = int(value) if str(value).strip() else None
    return result


def load_dgm_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            result[row["event"]].append(row)
    return result


def load_audio_component_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            event = row.get("primary_animation", "")
            if event in REQUIRED_EVENTS:
                result[event].append(row)
    return result


def validate_event_av_evidence(evidence: dict[str, Any]) -> None:
    assertions = evidence.get("semantic_assertions", {})
    if (
        evidence.get("schema") != "magireco-ida-event-av-parallel-start-evidence-v1"
        or evidence.get("status") != "passed"
        or str(evidence.get("binary", {}).get("sha256", "")).casefold()
        != "5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf"
        or assertions.get("graphics_and_sound_receive_same_event_code") is not True
        or assertions.get("all_scene_names_are_set_at_time_zero") is not True
        or assertions.get("same_event_scene_scheduling")
        != "parallel_shared_event_global_origin"
        or assertions.get("scene_container_duration_rule")
        != "maximum_scene_duration_not_sum"
        or assertions.get("ac0908_control_commands_empty") is not True
        or assertions.get("machine_vision_used_as_authority") is not False
    ):
        raise ValueError("exact Slot IDA event A/V evidence differs")


def validate_dgm_reachability_evidence(evidence: dict[str, Any]) -> dict[str, str]:
    assertions = evidence.get("assertions", {})
    binary = evidence.get("binary", {})
    if (
        evidence.get("schema")
        != "magireco-ac0908-016-crivideo-name-reachability-v1"
        or evidence.get("status") != "passed"
        or str(binary.get("inherited_sha256", "")).casefold()
        != "5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf"
        or str(binary.get("gnu_build_id", "")).casefold()
        != "a1aceffc5be1f2380cdcd9af4d8f9764ac2bf40b"
        or assertions.get(
            "add_and_add_lp_are_authored_but_unloadable_in_exact_current_binary"
        )
        is not True
        or assertions.get("base_and_base_lp_are_loadable") is not True
        or assertions.get("zen_is_not_an_authored_substitute_for_this_z2d")
        is not True
        or assertions.get("ac0908_016_resource_resolution_status") != "CLOSED"
        or assertions.get("machine_vision_used_as_authority") is not False
    ):
        raise ValueError("exact Slot CRI DGM reachability evidence differs")
    rows = {
        str(row["cri_lookup_base_name"]): str(row["runtime_load_disposition"])
        for row in evidence.get("z2d_dgm_reachability", [])
    }
    expected = {
        "ac8040_premia_EF_add": "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE",
        "ac8040_premia_EF_add_LP": "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE",
        "ac8040_premia_EF": "LOADABLE_BY_EXACT_NAME",
        "ac8040_premia_EF_LP": "LOADABLE_BY_EXACT_NAME",
    }
    if rows != expected:
        raise ValueError(f"ac0908_016 exact DGM reachability set changed: {rows}")
    if assertions.get("ac0908_016_visible_media_set") != [
        "ac0908_pre_c10",
        "ac0908_pre_c10_LP",
        "ac8040_premia_EF",
        "ac8040_premia_EF_LP",
    ]:
        raise ValueError("ac0908_016 exact visible-media assertion differs")
    return rows


def load_sound_divide_values(evidence: dict[str, Any]) -> dict[int, int]:
    if (
        evidence.get("schema") != "magireco-ac0908-sound-divide-values-v1"
        or evidence.get("status") != "passed"
        or str(evidence.get("binary", {}).get("sha256", "")).casefold()
        != "5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf"
        or evidence.get("table", {}).get("base_ea", "").casefold() != "0x1445c54"
        or evidence.get("assertions", {}).get(
            "all_ac0908_nonzero_duration_leaf_sound_ids_covered"
        )
        is not True
    ):
        raise ValueError("exact Slot SOUND_DIVIDE_TBL evidence differs")
    result = {
        int(row["sound_id"]): int(row["volume_kind_value"])
        for row in evidence.get("values", [])
    }
    if {sound_id for sound_id, kind in result.items() if kind == 0} != {551, 552, 553}:
        raise ValueError("ac0908 BGM-bus sound-id set changed")
    return result


def audio_component_signature(rows: list[dict[str, Any]]) -> str:
    return structure_key(
        [
            {
                "parent_request_id": row["parent_request_id"],
                "start_ms": row["start_ms"],
                "leaf_request_id": row["leaf_request_id"],
                "leaf_sound_code": row["leaf_sound_code"],
                "duration_ms": row["duration_ms"],
                "volume_kind_value": row["volume_kind_value"],
                "role": row["role"],
            }
            for row in rows
        ]
    )


def resolve(
    runtime: dict[str, Any],
    prior: dict[str, Any],
    dgm_rows: dict[str, list[dict[str, str]]],
    ida_playlist: dict[str, Any],
    ida_event_av: dict[str, Any],
    audio_component_rows: dict[str, list[dict[str, str]]],
    sound_divide_evidence: dict[str, Any],
    dgm_reachability_evidence: dict[str, Any],
) -> dict[str, Any]:
    if (
        ida_playlist.get("schema") != "magireco-ida-playlist-chain-evidence-v1"
        or ida_playlist.get("status") != "passed"
        or str(ida_playlist.get("binary", {}).get("sha256", "")).casefold()
        != "5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf"
    ):
        raise ValueError("exact Slot IDA playlist evidence differs")
    required_labels = {
        "CGFDirectionPlayer_SetScene",
        "CGFDirectionPlaylist_AddCut",
        "CGFDirectionPlaylist_AddBlank",
        "CGFDirectionPlaylist_AdvanceTime",
        "CGFDirectionPlaylist_SetTime",
    }
    if not required_labels.issubset(set(ida_playlist.get("labels", []))):
        raise ValueError("IDA playlist evidence lacks the required timing functions")
    validate_event_av_evidence(ida_event_av)
    sound_divide_values = load_sound_divide_values(sound_divide_evidence)
    dgm_reachability = validate_dgm_reachability_evidence(
        dgm_reachability_evidence
    )
    if runtime.get("schema") != "magireco-ac0908-runtime-scene-motion-v1":
        raise ValueError("unexpected runtime scene-motion schema")
    if runtime.get("host_frida_version") != "17.16.4":
        raise ValueError("unexpected runtime Frida version")
    if runtime.get("protected_processes_unchanged") is not True:
        raise ValueError("runtime capture changed a protected foreground game")
    if runtime.get("crash_tail_empty") is not True:
        raise ValueError("runtime capture has a non-empty crash tail")
    if tuple(runtime.get("events", {})) != REQUIRED_EVENTS:
        raise ValueError("runtime capture does not contain all 17 ac0908 containers")

    audio_spans = load_audio_spans(prior)
    visible: list[dict[str, Any]] = []
    parallel_empty_scenes: list[dict[str, Any]] = []
    containers: list[dict[str, Any]] = []
    event_audio: list[dict[str, Any]] = []
    for event in REQUIRED_EVENTS:
        wrapper = runtime["events"][event]
        if wrapper.get("status") != "captured":
            raise ValueError(f"runtime event was not captured: {event}")
        value = wrapper["value"]
        if value.get("group_name") != "ac0908":
            raise ValueError(f"runtime event group differs: {event}")
        scene_frame_lengths: list[int] = []
        visible_keys: list[str] = []
        event_visible: list[dict[str, Any]] = []
        event_empty: list[dict[str, Any]] = []
        for scene in value.get("scenes", []):
            cuts = scene.get("cuts", [])
            if len(cuts) != 1:
                raise ValueError(f"expected one cut in {event}/{scene.get('name')}")
            cut = cuts[0]
            frames = cut_frames(cut)
            scene_frame_lengths.append(frames)
            row = {
                "event": event,
                "scene_name": scene["name"],
                "cut_name": cut["cut_name"],
                "frames": frames,
                "seconds": frames / 30,
                "scene_start_frame": 0,
                "scheduling": "parallel_shared_event_global_origin",
                "node_count": int(cut.get("node_count", len(cut.get("nodes", [])))),
                "z2d_names": z2d_names(cut),
            }
            if row["node_count"] == 0:
                row["blank_profile"] = structure_key(
                    {
                        "frames": frames,
                        "instance_offset_frames": cut["instance_offset_frames"],
                    }
                )
                parallel_empty_scenes.append(row)
                event_empty.append(row)
                continue
            key = structure_key(cut_structure(cut))
            row["structure_key"] = key
            visible.append(row)
            event_visible.append(row)
            visible_keys.append(key)
        parallel_empty_frames = sorted(row["frames"] for row in event_empty)
        for row in event_visible:
            row["parallel_empty_scene_frames"] = parallel_empty_frames
        container_frames = max(scene_frame_lengths, default=0)

        resolved_audio_rows: list[dict[str, Any]] = []
        for source_row in audio_component_rows.get(event, []):
            duration_ms = int(source_row["duration_ms"])
            if duration_ms <= 0:
                continue
            sound_id = int(source_row["leaf_sound_code"])
            if sound_id not in sound_divide_values:
                raise ValueError(f"SOUND_DIVIDE_TBL lacks {event} sound {sound_id}")
            kind = sound_divide_values[sound_id]
            role = {0: "BGM", 1: "SE", 2: "VOICE"}.get(kind, "INVALID")
            resolved_audio_rows.append(
                {
                    "parent_request_id": int(source_row["parent_request_id"]),
                    "start_ms": int(source_row["start_ms"]),
                    "leaf_request_id": int(source_row["leaf_request_id"]),
                    "leaf_sound_code": sound_id,
                    "leaf_code_name": source_row["leaf_code_name"],
                    "duration_ms": duration_ms,
                    "end_ms": int(source_row["start_ms"]) + duration_ms,
                    "volume_kind_value": kind,
                    "role": role,
                    "strict_no_bgm_disposition": (
                        "EXCLUDE_AS_BGM_BUS" if kind == 0 else "RETAIN_VERIFIED_SE_OR_VOICE"
                    ),
                }
            )
        if not resolved_audio_rows:
            raise ValueError(f"official static audio components missing: {event}")
        full_audio_span_ms = max(row["end_ms"] for row in resolved_audio_rows)
        if full_audio_span_ms != audio_spans.get(event):
            raise ValueError(
                f"official audio span differs for {event}: "
                f"{full_audio_span_ms} != {audio_spans.get(event)}"
            )
        retained_audio_rows = [row for row in resolved_audio_rows if row["role"] != "BGM"]
        if any(row["role"] == "INVALID" for row in retained_audio_rows):
            raise ValueError(f"invalid SOUND_DIVIDE role in {event}")
        strict_no_bgm_span_ms = max(
            (row["end_ms"] for row in retained_audio_rows), default=0
        )
        event_audio.append(
            {
                "event": event,
                "event_global_start_ms": 0,
                "full_component_span_ms": full_audio_span_ms,
                "strict_no_bgm_component_span_ms": strict_no_bgm_span_ms,
                "components": resolved_audio_rows,
                "strict_no_bgm_signature": audio_component_signature(retained_audio_rows),
                "full_component_signature": audio_component_signature(resolved_audio_rows),
            }
        )
        containers.append(
            {
                "event": event,
                "scene_count": len(value.get("scenes", [])),
                "container_frames_parallel_max": container_frames,
                "container_seconds_parallel_max": container_frames / 30,
                "parallel_empty_scene_frames": parallel_empty_frames,
                "static_audio_component_span_ms": audio_spans.get(event),
                "strict_no_bgm_audio_span_ms": strict_no_bgm_span_ms,
                "visible_structure_keys": visible_keys,
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in visible:
        grouped[row["structure_key"]].append(row)
    canonical: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    for number, (key, occurrences) in enumerate(grouped.items(), start=1):
        first = occurrences[0]
        events = [row["event"] for row in occurrences]
        row = {
            "scene_key_id": f"S{number:02d}",
            "canonical_cut_name": first["cut_name"],
            "frames": first["frames"],
            "seconds": first["seconds"],
            "z2d_names": first["z2d_names"],
            "source_events": events,
            "occurrence_count": len(occurrences),
            "surplus_occurrence_count": len(occurrences) - 1,
            "parallel_empty_scene_frames": sorted(
                {
                    frames
                    for item in occurrences
                    for frames in item["parallel_empty_scene_frames"]
                }
            ),
            "structure": json.loads(key),
        }
        canonical.append(row)
        if len(occurrences) > 1:
            aliases.append(
                {
                    "scene_key_id": row["scene_key_id"],
                    "canonical_cut_name": first["cut_name"],
                    "source_events": events,
                    "surplus_occurrence_count": len(occurrences) - 1,
                }
            )

    if len(visible) != 17 or len(canonical) != 14:
        raise ValueError("ac0908 visible occurrence/canonical counts changed")
    if (
        len(parallel_empty_scenes) != 7
        or {row["frames"] for row in parallel_empty_scenes} != {100}
    ):
        raise ValueError("ac0908 parallel empty-scene state changed")
    observed_aliases = {
        row["canonical_cut_name"]: tuple(row["source_events"]) for row in aliases
    }
    if observed_aliases != EXPECTED_ALIASES:
        raise ValueError(f"ac0908 exact alias groups changed: {observed_aliases}")
    exact_visual_frames = sum(row["frames"] for row in canonical)
    if exact_visual_frames != 3751:
        raise ValueError(f"ac0908 canonical visual frame sum changed: {exact_visual_frames}")

    showcase = prior.get("current_showcase", {})
    included_showcase_events = set(showcase.get("included_events", []))
    showcase_occurrence_counts = {
        str(event): int(count)
        for event, count in showcase.get("event_occurrence_counts", {}).items()
    }
    if (
        not included_showcase_events
        or included_showcase_events != set(showcase_occurrence_counts)
        or not included_showcase_events.issubset(REQUIRED_EVENTS)
        or int(showcase.get("occurrence_count", -1))
        != sum(showcase_occurrence_counts.values())
    ):
        raise ValueError("prior showcase occurrence evidence differs")
    represented_showcase_scenes = [
        row
        for row in canonical
        if included_showcase_events.intersection(row["source_events"])
    ]
    missing_showcase_scenes = [
        row
        for row in canonical
        if not included_showcase_events.intersection(row["source_events"])
    ]
    guaranteed_duplicate_groups = list(
        showcase.get("guaranteed_duplicate_occurrence_groups", [])
    )
    repeated_container_events = sorted(
        event for event, count in showcase_occurrence_counts.items() if count > 1
    )
    exact_duplicate_events = {
        str(row["event"]) for row in guaranteed_duplicate_groups
    }
    legacy_longform_code_comparison = {
        "referenced_event_occurrence_count": sum(showcase_occurrence_counts.values()),
        "unique_event_container_count": len(included_showcase_events),
        "complete_event_container_count": len(REQUIRED_EVENTS),
        "repeated_event_container_reference_surplus_count": sum(
            count - 1 for count in showcase_occurrence_counts.values()
        ),
        "repeated_event_container_events": repeated_container_events,
        "guaranteed_exact_duplicate_render_occurrence_surplus_count": sum(
            int(row["surplus_occurrence_count"])
            for row in guaranteed_duplicate_groups
        ),
        "guaranteed_exact_duplicate_render_occurrence_groups": guaranteed_duplicate_groups,
        "same_container_different_trim_overlap_not_quantified": sorted(
            set(repeated_container_events) - exact_duplicate_events
        ),
        "represented_canonical_visible_scene_count": len(represented_showcase_scenes),
        "represented_canonical_scene_keys": [
            row["scene_key_id"] for row in represented_showcase_scenes
        ],
        "missing_canonical_visible_scene_count": len(missing_showcase_scenes),
        "missing_canonical_visible_scenes": [
            {
                "scene_key_id": row["scene_key_id"],
                "canonical_cut_name": row["canonical_cut_name"],
                "source_events": row["source_events"],
                "frames": row["frames"],
            }
            for row in missing_showcase_scenes
        ],
        "exhaustive_authoritative": False,
        "comparison_authority": "DirInfo/EventInfo plus pointer-free runtime Direction cut structures; no machine-vision identity claim",
    }

    audio_by_event = {row["event"]: row for row in event_audio}
    canonical_envelopes: list[dict[str, Any]] = []
    for row in canonical:
        events = row["source_events"]
        no_bgm_signatures = {
            audio_by_event[event]["strict_no_bgm_signature"] for event in events
        }
        full_signatures = {
            audio_by_event[event]["full_component_signature"] for event in events
        }
        if len(no_bgm_signatures) != 1 or len(full_signatures) != 1:
            raise ValueError(
                f"visual aliases do not share exact audio components: {events}"
            )
        representative_audio = audio_by_event[events[0]]
        visual_ms = row["frames"] * 1000 / 30
        strict_audio_ms = representative_audio["strict_no_bgm_component_span_ms"]
        canonical_envelopes.append(
            {
                "scene_key_id": row["scene_key_id"],
                "canonical_cut_name": row["canonical_cut_name"],
                "source_events": events,
                "visual_frames": row["frames"],
                "visual_seconds": row["frames"] / 30,
                "strict_no_bgm_audio_span_ms": strict_audio_ms,
                "strict_no_bgm_envelope_seconds_candidate": max(
                    visual_ms, strict_audio_ms
                )
                / 1000,
                "excluded_bgm_sound_ids": sorted(
                    {
                        component["leaf_sound_code"]
                        for component in representative_audio["components"]
                        if component["role"] == "BGM"
                    }
                ),
            }
        )
    strict_no_bgm_candidate_seconds = sum(
        row["strict_no_bgm_envelope_seconds_candidate"]
        for row in canonical_envelopes
    )

    dgm_coverage: list[dict[str, Any]] = []
    for event in (*REQUIRED_EVENTS[:9], "ac0908_016"):
        primary = next(row for row in canonical if event in row["source_events"])
        source_rows = dgm_rows.get(event, [])
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in source_rows:
            groups[row["z2d_name"]].append(row)
        group_rows = []
        for z2d_name, rows in groups.items():
            known_frames = sum(
                int(row["expected_frames"])
                for row in rows
                if row["source_exists"] == "True" and row["expected_frames"].strip()
            )
            authored_unloadable = [
                row["dgm_name"]
                for row in rows
                if row["source_exists"] != "True"
                and dgm_reachability.get(row["dgm_name"])
                == "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"
            ]
            unresolved_missing = [
                row["dgm_name"]
                for row in rows
                if row["source_exists"] != "True"
                and row["dgm_name"] not in authored_unloadable
            ]
            group_rows.append(
                {
                    "z2d_name": z2d_name,
                    "known_source_frames": known_frames,
                    "parent_visible_frame_limit": primary["frames"],
                    "known_frames_outside_parent_cut": max(0, known_frames - primary["frames"]),
                    "authored_unloadable_in_exact_binary": authored_unloadable,
                    "unresolved_missing_media": unresolved_missing,
                }
            )
        authored_unloadable = [
            row["dgm_name"]
            for row in source_rows
            if row["source_exists"] != "True"
            and dgm_reachability.get(row["dgm_name"])
            == "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"
        ]
        unresolved_missing = [
            row["dgm_name"]
            for row in source_rows
            if row["source_exists"] != "True"
            and row["dgm_name"] not in authored_unloadable
        ]
        dgm_coverage.append(
            {
                "event": event,
                "parent_visible_frames": primary["frames"],
                "parent_visible_seconds": primary["seconds"],
                "authored_unloadable_in_exact_binary": authored_unloadable,
                "unresolved_missing_media": unresolved_missing,
                "z2d_groups": group_rows,
            }
        )
    ac016 = next(row for row in dgm_coverage if row["event"] == "ac0908_016")
    if (
        ac016["parent_visible_frames"] != 180
        or sorted(ac016["authored_unloadable_in_exact_binary"])
        != ["ac8040_premia_EF_add", "ac8040_premia_EF_add_LP"]
        or ac016["unresolved_missing_media"]
    ):
        raise ValueError("ac0908_016 exact parent/resource-resolution state changed")

    return {
        "schema": "magireco-ac0908-runtime-unique-scene-authority-v3",
        "result": "RUNTIME_UNIQUE_SCENE_AND_EVENT_AV_ORIGIN_RESOLVED_PRODUCTION_READY",
        "production_paused": False,
        "authority": {
            "identity": "EventInfo exact event codes",
            "timing": "runtime Direction scene/cut structures plus exact Slot IDA: every scene name is SetScene at 0.0 and graphics/sound receive the same event code",
            "same_event_scene_scheduling": "parallel_shared_event_global_origin",
            "strict_no_bgm": "SOUND_DIVIDE_TBL exact values; exclude volume kind 0 BGM and retain verified kind 1 SE / kind 2 VOICE",
            "deduplication": "direct equality of pointer-free runtime cut/node/motion/key structures",
            "machine_vision_used_as_authority": False,
            "exact_slot_binary_sha256": ida_playlist["binary"]["sha256"],
            "dgm_reachability": "exact compiled CRI filename table and LoadUSMFileByName exact-name failure path",
        },
        "counts": {
            "event_container_count": len(REQUIRED_EVENTS),
            "scene_instance_count": len(visible) + len(parallel_empty_scenes),
            "visible_scene_occurrence_count": len(visible),
            "canonical_unique_visible_scene_count": len(canonical),
            "exact_duplicate_visible_surplus_count": sum(
                row["surplus_occurrence_count"] for row in aliases
            ),
            "parallel_empty_scene_occurrence_count": len(parallel_empty_scenes),
            "parallel_empty_scene_unique_profile_count": len(
                {row["blank_profile"] for row in parallel_empty_scenes}
            ),
            "strict_no_bgm_excluded_bgm_component_occurrence_count": sum(
                component["role"] == "BGM"
                for event in event_audio
                for component in event["components"]
            ),
        },
        "duration_audit": {
            "canonical_unique_visual_frames": exact_visual_frames,
            "canonical_unique_visual_seconds_exact": f"{exact_visual_frames}/30",
            "canonical_unique_visual_seconds_decimal": exact_visual_frames / 30,
            "strict_no_bgm_exhaustive_envelope_seconds_candidate": strict_no_bgm_candidate_seconds,
            "strict_no_bgm_exhaustive_envelope_seconds": strict_no_bgm_candidate_seconds,
            "final_audience_duration_resolved": True,
            "editorial_exhaustive_envelope_resolved": True,
            "native_single_session_stop_policy_claimed": False,
            "terminal_visual_policy": "hold_last_frame_only_when_verified_retained_audio_outlasts_exact_visual_cut",
            "reason": "the owner-defined product is an exhaustive editorial longform, not a native single-session trace; each unique presentation uses the exact visual cut or the longer verified retained no-BGM audio span, while the native single-session stop policy remains explicitly unclaimed",
        },
        "canonical_visible_scenes": canonical,
        "canonical_strict_no_bgm_envelopes": canonical_envelopes,
        "exact_alias_groups": aliases,
        "parallel_empty_scenes": parallel_empty_scenes,
        "event_containers": containers,
        "event_audio": event_audio,
        "dgm_coverage": dgm_coverage,
        "old_showcase_decision": {
            "playback_approval_retained": True,
            "complete_claim_withdrawn": True,
            "reason": "old showcase covers only ac0908_001..009 and repeats ac0908_009; runtime and exact Slot IDA prove four additional unique parallel-start shutters plus ac0908_016",
        },
        "legacy_longform_code_comparison": legacy_longform_code_comparison,
        "production_blockers": [],
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        "|".join(map(str, row.get(key, [])))
                        if isinstance(row.get(key), list)
                        else row.get(key, "")
                    )
                    for key in fields
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--prior-audit", required=True)
    parser.add_argument("--dgm-bindings", required=True)
    parser.add_argument("--ida-playlist-evidence", required=True)
    parser.add_argument("--ida-event-av-evidence", required=True)
    parser.add_argument("--audio-components", required=True)
    parser.add_argument("--sound-divide-evidence", required=True)
    parser.add_argument("--dgm-reachability-evidence", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    runtime_path = Path(args.runtime).resolve()
    prior_path = Path(args.prior_audit).resolve()
    dgm_path = Path(args.dgm_bindings).resolve()
    ida_path = Path(args.ida_playlist_evidence).resolve()
    ida_event_av_path = Path(args.ida_event_av_evidence).resolve()
    audio_components_path = Path(args.audio_components).resolve()
    sound_divide_path = Path(args.sound_divide_evidence).resolve()
    dgm_reachability_path = Path(args.dgm_reachability_evidence).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    authority = resolve(
        read_json(runtime_path),
        read_json(prior_path),
        load_dgm_rows(dgm_path),
        read_json(ida_path),
        read_json(ida_event_av_path),
        load_audio_component_rows(audio_components_path),
        read_json(sound_divide_path),
        read_json(dgm_reachability_path),
    )
    authority["source_paths"] = {
        "runtime_scene_motion": str(runtime_path),
        "prior_reverse_audit": str(prior_path),
        "dgm_media_bindings": str(dgm_path),
        "ida_playlist_evidence": str(ida_path),
        "ida_event_av_parallel_start_evidence": str(ida_event_av_path),
        "official_event_audio_components": str(audio_components_path),
        "sound_divide_evidence": str(sound_divide_path),
        "dgm_reachability_evidence": str(dgm_reachability_path),
    }
    output = out_dir / "AC0908_RUNTIME_UNIQUE_SCENE_AUTHORITY.json"
    output.write_text(
        json.dumps(authority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(
        out_dir / "AC0908_CANONICAL_VISIBLE_SCENES.csv",
        authority["canonical_visible_scenes"],
        [
            "scene_key_id",
            "canonical_cut_name",
            "frames",
            "seconds",
            "source_events",
            "occurrence_count",
            "surplus_occurrence_count",
            "parallel_empty_scene_frames",
            "z2d_names",
        ],
    )
    write_csv(
        out_dir / "AC0908_EXACT_ALIAS_GROUPS.csv",
        authority["exact_alias_groups"],
        ["scene_key_id", "canonical_cut_name", "source_events", "surplus_occurrence_count"],
    )
    (out_dir / "README.md").write_text(
        "# ac0908 code-level exhaustive scene audit\n\n"
        "The runtime capture resolves 17 EventInfo containers into 24 scene instances. "
        "Exact Slot IDA proves every scene name in one event animation is SetScene at time "
        "0.0, so the seven 100-frame zero-node scenes run in parallel with their shutter "
        "scenes; they are not sequential prefixes. The other 17 visible occurrences reduce by direct equality "
        "of pointer-free runtime structures to 14 unique visible scenes. HATTEN, CZ, and WIN "
        "each have one exact alias occurrence. The exact unique visual-cut minimum is 3751 "
        "frames (3751/30 seconds). The same event request path starts graphics and sound with "
        "the same event code, and SOUND_DIVIDE_TBL excludes 551/552/553 as BGM. This still is "
        "the exhaustive editorial duration is the maximum of each exact visual cut and its "
        "verified retained no-BGM audio span; this does not claim a native single-session stop. "
        "The exact CRI filename table proves ac0908_016 add/add_LP references are unloadable in "
        "this build, while base/base_LP are loadable, so no physical effect layer remains unresolved. "
        "The old 001-009 showcase remains a "
        "playback-approved historical file but is not exhaustive.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": authority["result"],
                "output": str(output),
                **authority["counts"],
                "canonical_unique_visual_frames": authority["duration_audit"][
                    "canonical_unique_visual_frames"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
