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


def resolve(
    runtime: dict[str, Any],
    prior: dict[str, Any],
    dgm_rows: dict[str, list[dict[str, str]]],
    ida_playlist: dict[str, Any],
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
    blanks: list[dict[str, Any]] = []
    containers: list[dict[str, Any]] = []
    for event in REQUIRED_EVENTS:
        wrapper = runtime["events"][event]
        if wrapper.get("status") != "captured":
            raise ValueError(f"runtime event was not captured: {event}")
        value = wrapper["value"]
        if value.get("group_name") != "ac0908":
            raise ValueError(f"runtime event group differs: {event}")
        container_frames = 0
        prefix_blank_frames = 0
        visible_keys: list[str] = []
        for scene in value.get("scenes", []):
            cuts = scene.get("cuts", [])
            if len(cuts) != 1:
                raise ValueError(f"expected one cut in {event}/{scene.get('name')}")
            cut = cuts[0]
            frames = cut_frames(cut)
            container_frames += frames
            row = {
                "event": event,
                "scene_name": scene["name"],
                "cut_name": cut["cut_name"],
                "frames": frames,
                "seconds": frames / 30,
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
                blanks.append(row)
                if not visible_keys:
                    prefix_blank_frames += frames
                continue
            key = structure_key(cut_structure(cut))
            row["structure_key"] = key
            row["container_prefix_blank_frames"] = prefix_blank_frames
            visible.append(row)
            visible_keys.append(key)
        containers.append(
            {
                "event": event,
                "scene_count": len(value.get("scenes", [])),
                "container_frames_including_blank": container_frames,
                "container_seconds_including_blank": container_frames / 30,
                "prefix_blank_frames": prefix_blank_frames,
                "static_audio_component_span_ms": audio_spans.get(event),
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
            "container_prefix_blank_frames": sorted(
                {item["container_prefix_blank_frames"] for item in occurrences}
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
    if len(blanks) != 7 or {row["frames"] for row in blanks} != {100}:
        raise ValueError("ac0908 blank-prefix state changed")
    observed_aliases = {
        row["canonical_cut_name"]: tuple(row["source_events"]) for row in aliases
    }
    if observed_aliases != EXPECTED_ALIASES:
        raise ValueError(f"ac0908 exact alias groups changed: {observed_aliases}")
    exact_visual_frames = sum(row["frames"] for row in canonical)
    if exact_visual_frames != 3751:
        raise ValueError(f"ac0908 canonical visual frame sum changed: {exact_visual_frames}")

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
            group_rows.append(
                {
                    "z2d_name": z2d_name,
                    "known_source_frames": known_frames,
                    "parent_visible_frame_limit": primary["frames"],
                    "known_frames_outside_parent_cut": max(0, known_frames - primary["frames"]),
                    "missing_media": [
                        row["dgm_name"]
                        for row in rows
                        if row["source_exists"] != "True"
                    ],
                }
            )
        dgm_coverage.append(
            {
                "event": event,
                "parent_visible_frames": primary["frames"],
                "parent_visible_seconds": primary["seconds"],
                "missing_media": [
                    row["dgm_name"]
                    for row in source_rows
                    if row["source_exists"] != "True"
                ],
                "z2d_groups": group_rows,
            }
        )
    ac016 = next(row for row in dgm_coverage if row["event"] == "ac0908_016")
    if ac016["parent_visible_frames"] != 180 or sorted(ac016["missing_media"]) != [
        "ac8040_premia_EF_add",
        "ac8040_premia_EF_add_LP",
    ]:
        raise ValueError("ac0908_016 exact parent/missing-layer state changed")

    return {
        "schema": "magireco-ac0908-runtime-unique-scene-authority-v1",
        "result": "RUNTIME_UNIQUE_SCENE_UNIVERSE_RESOLVED_PRODUCTION_FAIL_CLOSED",
        "production_paused": True,
        "authority": {
            "identity": "EventInfo exact event codes",
            "timing": "runtime Direction scene/cut structures interpreted by IDA SetScene/AddBlank/AddCut/AdvanceTime/SetTime",
            "deduplication": "direct equality of pointer-free runtime cut/node/motion/key structures",
            "machine_vision_used_as_authority": False,
            "exact_slot_binary_sha256": ida_playlist["binary"]["sha256"],
        },
        "counts": {
            "event_container_count": len(REQUIRED_EVENTS),
            "scene_instance_count": len(visible) + len(blanks),
            "visible_scene_occurrence_count": len(visible),
            "canonical_unique_visible_scene_count": len(canonical),
            "exact_duplicate_visible_surplus_count": sum(
                row["surplus_occurrence_count"] for row in aliases
            ),
            "blank_hold_occurrence_count": len(blanks),
            "blank_hold_unique_profile_count": len(
                {row["blank_profile"] for row in blanks}
            ),
        },
        "duration_audit": {
            "canonical_unique_visual_frames": exact_visual_frames,
            "canonical_unique_visual_seconds_exact": f"{exact_visual_frames}/30",
            "canonical_unique_visual_seconds_decimal": exact_visual_frames / 30,
            "final_audience_duration_resolved": False,
            "reason": "container audio/tail boundaries still need exact scene-relative binding; blank holds are not unique visible content",
        },
        "canonical_visible_scenes": canonical,
        "exact_alias_groups": aliases,
        "blank_holds": blanks,
        "event_containers": containers,
        "dgm_coverage": dgm_coverage,
        "old_showcase_decision": {
            "playback_approval_retained": True,
            "complete_claim_withdrawn": True,
            "reason": "old showcase covers only ac0908_001..009 and repeats ac0908_009; runtime proves four additional unique shutters plus ac0908_016",
        },
        "production_blockers": [
            "ac0908_016 missing ac8040_premia_EF_add and ac8040_premia_EF_add_LP",
            "container audio/tail timing for newly admitted shutter scenes is not yet bound to the scene-relative exhaustive timeline",
        ],
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
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    runtime_path = Path(args.runtime).resolve()
    prior_path = Path(args.prior_audit).resolve()
    dgm_path = Path(args.dgm_bindings).resolve()
    ida_path = Path(args.ida_playlist_evidence).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    authority = resolve(
        read_json(runtime_path),
        read_json(prior_path),
        load_dgm_rows(dgm_path),
        read_json(ida_path),
    )
    authority["source_paths"] = {
        "runtime_scene_motion": str(runtime_path),
        "prior_reverse_audit": str(prior_path),
        "dgm_media_bindings": str(dgm_path),
        "ida_playlist_evidence": str(ida_path),
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
            "container_prefix_blank_frames",
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
        "Seven 100-frame instances contain zero Direction nodes and are blank holds, not "
        "unique visible content. The other 17 visible occurrences reduce by direct equality "
        "of pointer-free runtime structures to 14 unique visible scenes. HATTEN, CZ, and WIN "
        "each have one exact alias occurrence. The exact unique visual-cut minimum is 3751 "
        "frames (3751/30 seconds); this is not the final audience duration because new shutter "
        "audio/tail placement remains unresolved. ac0908_016 is parent-limited to 180 frames, "
        "while two required effect layers remain missing. The old 001-009 showcase remains a "
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
