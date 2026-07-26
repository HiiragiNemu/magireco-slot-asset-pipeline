#!/usr/bin/env python3
"""Build the six owner-authorized ac0908 complete-entry route editions.

DirInfo kind 33 rows 6-11 are independent routes:

    ac0908_001 -> ac0908_002..007 -> ac0908_008

The 187-frame ``ac0908_001`` presentation is the owner-approved v28 restaurant
exterior plus side-cooking entry.  Its verified scene audio is deliberately
mixed across the following outcome boundary, matching the approved v28
presentation contract.  Outcome/outro visuals, no-BGM event PCM, and subtitles
come from the already approved v27 route sources.  Every input is SHA-256 bound.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from . import build_ac0908_approved_production as approved
    from . import build_ac0908_reference_showcase as reference
    from . import build_mature_416_route_batch as mature
except ImportError:  # direct script execution
    import build_ac0908_approved_production as approved  # type: ignore
    import build_ac0908_reference_showcase as reference  # type: ignore
    import build_mature_416_route_batch as mature  # type: ignore


PLAN_SCHEMA = "magireco-ac0908-complete-entry-routes-plan-v1"
MANIFEST_SCHEMA = "magireco-ac0908-complete-entry-routes-manifest-v1"
QA_SCHEMA = "magireco-ac0908-complete-entry-routes-qa-v1"
STATUS = "OWNER_APPROVED_CONTRACT_AUTOMATED_QA_PASSED"
EDITIONS = ("none", "ja", "zh")
ENTRY_FRAMES = 187
ENTRY_SAMPLES = ENTRY_FRAMES * reference.SAMPLES_PER_FRAME
OUTRO_EVENT = "ac0908_008"
OUTRO_FRAMES = 241
EXPECTED_ROUTES = {
    6: ("ac0908_002", 52),
    7: ("ac0908_003", 53),
    8: ("ac0908_004", 54),
    9: ("ac0908_005", 55),
    10: ("ac0908_006", 56),
    11: ("ac0908_007", 57),
}


def _bound(
    raw: Mapping[str, Any],
    *,
    label: str,
    plan_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    if "path" not in raw or "sha256" not in raw:
        raise ValueError(f"{label} lacks path or sha256")
    return reference.validate_bound_file(
        {"path": raw["path"], "sha256": raw["sha256"]},
        label=label,
        plan_dir=plan_dir,
    )


def _validate_owner_attestation(path: Path) -> None:
    value = reference.read_json(path)
    if (
        value.get("schema") != "magireco-owner-approved-route-expansion-v1"
        or value.get("status") != "owner_approved_full_production"
        or value.get("family") != "ac0908"
    ):
        raise ValueError("ac0908 complete-entry owner attestation identity differs")
    contract = value.get("approved_presentation_contract")
    if not isinstance(contract, Mapping) or (
        contract.get("entry_event"),
        int(contract.get("entry_frames", -1)),
        contract.get("approved_reference_zh_sha256"),
    ) != (
        "ac0908_001",
        ENTRY_FRAMES,
        "53C0A918C043F78D8CB70DC643747C7DEC3FC45D5FA107A91251A347586AFD51",
    ):
        raise ValueError("ac0908 complete-entry approved presentation differs")
    observed: dict[int, list[str]] = {}
    for raw in value.get("authorized_dirinfo_routes", []):
        if not isinstance(raw, Mapping) or int(raw.get("kind", -1)) != 33:
            raise ValueError("ac0908 complete-entry attestation route differs")
        row = int(raw.get("row", -1))
        if row in observed:
            raise ValueError("duplicate attested ac0908 route")
        observed[row] = [str(event) for event in raw.get("ordered_events", [])]
    expected = {
        row: ["ac0908_001", outcome, OUTRO_EVENT]
        for row, (outcome, _) in EXPECTED_ROUTES.items()
    }
    if observed != expected:
        raise ValueError("attested ac0908 route matrix differs")
    authorization = value.get("production_authorization")
    if (
        not isinstance(authorization, Mapping)
        or authorization.get("audio_profile") != "no_bgm"
        or tuple(authorization.get("editions", [])) != EDITIONS
        or "independent" not in str(authorization.get("route_policy", ""))
    ):
        raise ValueError("ac0908 complete-entry production authorization differs")


def _validate_dirinfo(path: Path) -> dict[int, list[dict[str, str]]]:
    selected: dict[int, list[dict[str, str]]] = {row: [] for row in EXPECTED_ROUTES}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if int(raw["kind"]) != 33:
                continue
            row = int(raw["row_index"])
            if row in selected:
                selected[row].append(dict(raw))
    for row, rows in selected.items():
        rows.sort(key=lambda value: int(value["selector_raw"]))
        expected = [
            "ac0908_001",
            EXPECTED_ROUTES[row][0],
            OUTRO_EVENT,
        ]
        if (
            [value["scene_name"] for value in rows] != expected
            or [int(value["selector_raw"]) for value in rows] != [1, 2, 4]
            or any(value["route_status"] != "ok" for value in rows)
        ):
            raise ValueError(f"DirInfo kind 33 row {row} differs")
    return selected


def _artifact(
    *,
    family_path: Path,
    family: Mapping[str, Any],
    key: str,
) -> tuple[Path, dict[str, Any]]:
    artifacts = family.get("artifacts")
    if not isinstance(artifacts, Mapping) or not isinstance(
        artifacts.get(key), Mapping
    ):
        raise ValueError(f"source family lacks artifact {key}")
    raw = artifacts[key]
    path = Path(str(raw["path"]))
    if not path.is_absolute():
        path = family_path.parent.parent / path
    expected = str(raw["sha256"]).upper()
    if not path.is_file() or mature.file_sha256(path) != expected:
        raise ValueError(f"source family artifact changed: {path}")
    return path, {
        "label": f"source family {key}",
        "path": str(path.resolve()),
        "sha256": expected,
    }


def _local_cues(
    cues: Sequence[Mapping[str, Any]],
    *,
    route: Mapping[str, Any],
    event: str,
) -> list[dict[str, Any]]:
    return approved.extract_event_local_cues(
        cues,
        timeline_row=route["timeline"][event],
        event=event,
    )


def _route_cues(
    *,
    route: Mapping[str, Any],
    zh_cues: Sequence[Mapping[str, Any]],
    outcome: str,
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    outcome_start = ENTRY_SAMPLES
    outro_start = ENTRY_SAMPLES + int(
        route["timeline"][outcome]["end_sample"]
        - route["timeline"][outcome]["start_sample"]
    )
    for edition, source in (("ja", route["ja_cues"]), ("zh", zh_cues)):
        combined: list[dict[str, Any]] = []
        for event, start_sample in (
            (outcome, outcome_start),
            (OUTRO_EVENT, outro_start),
        ):
            offset_ms = reference.milliseconds_for_samples(start_sample)
            for cue in _local_cues(source, route=route, event=event):
                combined.append(
                    {
                        "start_ms": offset_ms + int(cue["start_ms"]),
                        "end_ms": offset_ms + int(cue["end_ms"]),
                        "text": str(cue["text"]),
                    }
                )
        if len(combined) != 4:
            raise ValueError(f"{edition} complete-entry route cue count differs")
        output[edition] = combined
    return output


def validate_plan(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("status") != "owner_approved_full_production"
        or plan.get("series") != "ac0908"
        or plan.get("audio_profile") != "no_bgm"
        or tuple(plan.get("editions", [])) != EDITIONS
        or plan.get("route_policy")
        != "dirinfo_rows_6_11_are_six_independent_native_route_segments"
        or plan.get("entry_audio_policy")
        != "approved_v28_ac0908_001_scene_audio_overlay_continues_across_outcome_boundary"
    ):
        raise ValueError("ac0908 complete-entry plan identity differs")
    native = plan.get("native_media")
    if not isinstance(native, Mapping) or (
        int(native.get("width", -1)),
        int(native.get("height", -1)),
        str(native.get("frame_rate", "")),
        str(native.get("video_codec", "")),
        str(native.get("audio_codec", "")),
        int(native.get("audio_sample_rate", -1)),
        int(native.get("audio_channels", -1)),
        bool(native.get("upscale", True)),
    ) != (416, 232, "30/1", "h264", "aac", 48000, 2, False):
        raise ValueError("ac0908 complete-entry native media differs")

    plan_dir = plan_path.parent
    snapshots: list[dict[str, Any]] = [
        {
            "label": "ac0908 complete-entry production plan",
            "path": str(plan_path.resolve()),
            "sha256": mature.file_sha256(plan_path),
        }
    ]

    owner_path, snapshot = _bound(
        plan["owner_attestation"],
        label="owner-approved ac0908 complete-entry routes",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    _validate_owner_attestation(owner_path)

    dirinfo_path, snapshot = _bound(
        plan["dirinfo"], label="DirInfo route evidence", plan_dir=plan_dir
    )
    snapshots.append(snapshot)
    dirinfo_rows = _validate_dirinfo(dirinfo_path)

    approved_plan_path, snapshot = _bound(
        plan["approved_strong_route_plan"],
        label="approved ac0908 strong-route source plan",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    approved_plan = reference.read_json(approved_plan_path)
    approved_resolved = approved.validate_plan(
        approved_plan,
        plan_path=approved_plan_path,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )

    reference_plan_path, snapshot = _bound(
        plan["reference_showcase_plan"],
        label="approved ac0908 v28 reference plan",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    reference_resolved = reference.validate_plan(
        reference.read_json(reference_plan_path),
        plan_path=reference_plan_path,
        ffprobe=ffprobe,
    )
    if (
        reference_resolved["entry_audio"]
        != approved_resolved["showcase"]["resolved_plan"]["entry_audio"]
    ):
        raise ValueError("approved entry audio source identity differs")

    showcase_manifest_path, snapshot = _bound(
        plan["approved_reference_showcase_manifest"],
        label="approved ac0908 v28 showcase manifest",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    showcase_manifest = reference.read_json(showcase_manifest_path)
    if (
        showcase_manifest.get("schema")
        != "magireco-ac0908-reference-showcase-manifest-v1"
        or showcase_manifest.get("timeline", [])[0].get("event") != "ac0908_001"
        or int(showcase_manifest.get("timeline", [])[0].get("end_frame", -1))
        != ENTRY_FRAMES
        or showcase_manifest.get("entry_audio_overlap_policy")
        != "ac0908_001 scene audio starts at each entry presentation and may continue across the following event boundary, matching the reference-observed presentation duration"
    ):
        raise ValueError("approved v28 complete-entry contract differs")

    showcase_qa_path, snapshot = _bound(
        plan["approved_reference_showcase_qa"],
        label="approved ac0908 v28 showcase QA",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    showcase_qa = reference.read_json(showcase_qa_path)
    if (
        showcase_qa.get("schema") != "magireco-ac0908-reference-showcase-qa-v1"
        or not showcase_qa.get("automated_spec_qa_passed")
        or not showcase_qa.get("checks", {}).get("all_production_inputs_hash_bound")
        or not showcase_qa.get("checks", {}).get(
            "no_external_reference_pixels_or_audio"
        )
    ):
        raise ValueError("approved ac0908 v28 showcase QA differs")

    entry_raw = plan.get("entry_visual")
    if not isinstance(entry_raw, Mapping):
        raise ValueError("complete-entry visual binding is missing")
    entry_path, snapshot = _bound(
        entry_raw, label="approved 187-frame complete entry", plan_dir=plan_dir
    )
    if (
        entry_path.stat().st_size != int(entry_raw.get("bytes", -1))
        or int(entry_raw.get("frame_count", -1)) != ENTRY_FRAMES
    ):
        raise ValueError("complete-entry visual byte/frame binding differs")
    reference.validate_video_grid(
        entry_path,
        expected_frames=ENTRY_FRAMES,
        ffprobe=ffprobe,
        label="approved complete-entry visual",
    )
    approved_entry = approved_resolved["showcase"]["entry_visuals"].get(
        "weak_entry_with_exterior_01"
    )
    if approved_entry is None or mature.file_sha256(approved_entry) != snapshot["sha256"]:
        raise ValueError("complete-entry visual differs from approved v28 media")
    snapshots.append(snapshot)

    layout_path, snapshot = _bound(
        plan["subtitle_layout"],
        label="416x232 subtitle layout",
        plan_dir=plan_dir,
    )
    snapshots.append(snapshot)
    layout = reference.read_json(layout_path)
    font_path, snapshot = _bound(
        plan["font"], label="audited subtitle font", plan_dir=plan_dir
    )
    snapshots.append(snapshot)

    pcm_raw = plan.get("event_pcm")
    if not isinstance(pcm_raw, Mapping) or set(pcm_raw) != {
        *(outcome for outcome, _ in EXPECTED_ROUTES.values()),
        OUTRO_EVENT,
    }:
        raise ValueError("ac0908 complete-entry event PCM set differs")
    pcm: dict[str, dict[str, Any]] = {}
    declared_audits = showcase_manifest.get("event_pcm_audits", {})
    for event, raw in pcm_raw.items():
        if not isinstance(raw, Mapping):
            raise ValueError("event PCM binding must be an object")
        path, snapshot = _bound(
            raw, label=f"approved v28 {event} PCM", plan_dir=plan_dir
        )
        samples = int(raw.get("samples", -1))
        if path.stat().st_size != samples * 8:
            raise ValueError(f"{event} PCM byte count differs")
        declared = declared_audits.get(event)
        if (
            not isinstance(declared, Mapping)
            or int(declared.get("presentation_samples", -1)) != samples
            or str(declared.get("sha256", "")).upper() != snapshot["sha256"]
        ):
            raise ValueError(f"{event} PCM differs from approved v28 manifest")
        pcm[event] = {"path": path, "samples": samples, "sha256": snapshot["sha256"]}
        snapshots.append(snapshot)

    routes_raw = plan.get("routes")
    if not isinstance(routes_raw, list) or len(routes_raw) != len(EXPECTED_ROUTES):
        raise ValueError("ac0908 complete-entry plan must contain six routes")
    source_plan_routes = {
        int(raw["dirinfo_row"]): raw for raw in approved_plan.get("routes", [])
    }
    routes: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in routes_raw:
        if not isinstance(raw, Mapping):
            raise ValueError("ac0908 complete-entry route must be an object")
        row = int(raw.get("dirinfo_row", -1))
        outcome, strong_row = EXPECTED_ROUTES.get(row, ("", -1))
        if (
            row in seen
            or raw.get("outcome_event") != outcome
            or int(raw.get("source_strong_row", -1)) != strong_row
        ):
            raise ValueError("ac0908 complete-entry route matrix differs")
        seen.add(row)
        route = approved_resolved["routes"][strong_row]
        if route["route_order"] != ["ac0908_009", outcome, OUTRO_EVENT]:
            raise ValueError(f"source strong route {strong_row} differs")
        source_raw = source_plan_routes[strong_row]
        family_path, family_snapshot = _bound(
            source_raw["family_manifest"],
            label=f"source strong route {strong_row} family manifest",
            plan_dir=approved_plan_path.parent,
        )
        snapshots.append(family_snapshot)
        zh_srt_path, zh_snapshot = _artifact(
            family_path=family_path,
            family=route["family_manifest"],
            key="subtitles_zh",
        )
        snapshots.append(zh_snapshot)
        zh_cues = mature.parse_srt(zh_srt_path)
        cues = _route_cues(route=route, zh_cues=zh_cues, outcome=outcome)
        outcome_frames = int(
            route["timeline"][outcome]["end_frame"]
            - route["timeline"][outcome]["start_frame"]
        )
        if outcome_frames * reference.SAMPLES_PER_FRAME != pcm[outcome]["samples"]:
            raise ValueError(f"{outcome} frame/sample duration differs")
        if pcm[OUTRO_EVENT]["samples"] != OUTRO_FRAMES * reference.SAMPLES_PER_FRAME:
            raise ValueError("ac0908_008 frame/sample duration differs")
        routes.append(
            {
                "dirinfo_row": row,
                "source_strong_row": strong_row,
                "title": str(raw.get("title", "")),
                "ordered_events": ["ac0908_001", outcome, OUTRO_EVENT],
                "outcome": outcome,
                "outcome_frames": outcome_frames,
                "total_frames": ENTRY_FRAMES + outcome_frames + OUTRO_FRAMES,
                "total_samples": (
                    ENTRY_SAMPLES
                    + pcm[outcome]["samples"]
                    + pcm[OUTRO_EVENT]["samples"]
                ),
                "source_route": route,
                "cues": cues,
                "dirinfo_evidence": dirinfo_rows[row],
            }
        )
    if seen != set(EXPECTED_ROUTES):
        raise ValueError("ac0908 complete-entry route row set differs")

    unique: list[dict[str, Any]] = []
    identities: dict[str, str] = {}
    for snapshot in snapshots:
        path = str(Path(str(snapshot["path"])).resolve())
        sha256 = str(snapshot["sha256"]).upper()
        existing = identities.get(path.casefold())
        if existing is not None and existing != sha256:
            raise ValueError(f"conflicting source snapshot for {path}")
        if existing is None:
            identities[path.casefold()] = sha256
            unique.append(
                {
                    "label": str(snapshot.get("label", "")),
                    "path": path,
                    "sha256": sha256,
                }
            )
    return {
        "release_id": str(plan.get("release_id", "")),
        "routes": sorted(routes, key=lambda value: value["dirinfo_row"]),
        "entry_visual": entry_path,
        "entry_audio": reference_resolved["entry_audio"],
        "events": reference_resolved["events"],
        "pcm": pcm,
        "layout": layout,
        "font": font_path,
        "source_snapshots": unique,
    }


def _build_clean_visual(
    *,
    resolved: Mapping[str, Any],
    route: Mapping[str, Any],
    output: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    outcome = str(route["outcome"])
    sources = [
        resolved["entry_visual"],
        resolved["events"][outcome]["clean_visual"],
        resolved["events"][OUTRO_EVENT]["clean_visual"],
    ]
    frames = [ENTRY_FRAMES, int(route["outcome_frames"]), OUTRO_FRAMES]
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    filters: list[str] = []
    labels: list[str] = []
    for index, (source, frame_count) in enumerate(zip(sources, frames)):
        command.extend(["-i", str(source)])
        label = f"v{index}"
        filters.append(
            f"[{index}:v:0]trim=end_frame={frame_count},"
            f"setpts=N/({reference.FPS}*TB),format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[outv]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "14",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(route["total_frames"]),
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    mature.run(command)
    return reference.validate_video_grid(
        output,
        expected_frames=int(route["total_frames"]),
        ffprobe=ffprobe,
        label=f"ac0908 complete-entry route {route['dirinfo_row']} visual",
    )


def _build_pcm(
    *,
    resolved: Mapping[str, Any],
    route: Mapping[str, Any],
    output: Path,
    work: Path,
    ffmpeg: str,
) -> dict[str, Any]:
    base = work / "base.f32le"
    with base.open("wb") as target:
        target.write(b"\x00" * (ENTRY_SAMPLES * 8))
        for event in (route["outcome"], OUTRO_EVENT):
            with resolved["pcm"][event]["path"].open("rb") as source:
                shutil.copyfileobj(source, target, 1024 * 1024)
    if base.stat().st_size != int(route["total_samples"]) * 8:
        raise RuntimeError("ac0908 complete-entry base PCM byte count differs")
    mature.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "f32le",
            "-ar",
            str(reference.SAMPLE_RATE),
            "-ac",
            "2",
            "-i",
            str(base),
            "-i",
            str(resolved["entry_audio"]),
            "-filter_complex",
            (
                "[0:a:0]aformat=sample_fmts=fltp:sample_rates=48000:"
                "channel_layouts=stereo[base];"
                "[1:a:0]aresample=48000,aformat=sample_fmts=fltp:"
                "sample_rates=48000:channel_layouts=stereo[entry];"
                "[base][entry]amix=inputs=2:duration=longest:normalize=0:"
                "dropout_transition=0,alimiter=limit=0.95,"
                f"apad=whole_len={route['total_samples']},"
                f"atrim=end_sample={route['total_samples']},"
                "asetpts=N/SR/TB[mix]"
            ),
            "-map",
            "[mix]",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(reference.SAMPLE_RATE),
            "-ac",
            "2",
            str(output),
        ]
    )
    if output.stat().st_size != int(route["total_samples"]) * 8:
        raise RuntimeError("ac0908 complete-entry mixed PCM byte count differs")
    return {
        "sample_count": int(route["total_samples"]),
        "byte_count": output.stat().st_size,
        "sha256": mature.file_sha256(output),
        "entry_audio_overlay_crosses_outcome_boundary": True,
    }


def _timeline(route: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    frame = 0
    sample = 0
    for event, frames in (
        ("ac0908_001", ENTRY_FRAMES),
        (route["outcome"], route["outcome_frames"]),
        (OUTRO_EVENT, OUTRO_FRAMES),
    ):
        start_frame = frame
        start_sample = sample
        frame += int(frames)
        sample += int(frames) * reference.SAMPLES_PER_FRAME
        rows.append(
            {
                "event": event,
                "start_frame": start_frame,
                "end_frame": frame,
                "start_sample": start_sample,
                "end_sample": sample,
            }
        )
    if frame != route["total_frames"] or sample != route["total_samples"]:
        raise RuntimeError("ac0908 complete-entry timeline endpoint differs")
    return rows


def _tree_hashes(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": mature.file_sha256(path),
            "byte_count": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS.json"
    ]


def build(
    *,
    plan_path: Path,
    output_root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[Path, dict[str, Any]]:
    resolved = validate_plan(
        reference.read_json(plan_path),
        plan_path=plan_path,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )
    destination = output_root.resolve() / "ac0908"
    if destination.exists():
        raise FileExistsError(f"versioned ac0908 complete-entry root exists: {destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    staging = output_root.resolve() / f".ac0908.staging.{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        fonts_dir = staging / "work" / "fonts"
        fonts_dir.mkdir(parents=True)
        shutil.copy2(resolved["font"], fonts_dir / resolved["font"].name)
        products: list[dict[str, Any]] = []
        for route in resolved["routes"]:
            route_id = f"dirinfo_row{route['dirinfo_row']:02d}_complete_entry"
            route_dir = staging / "routes" / route_id
            work = route_dir / ".work"
            work.mkdir(parents=True)
            clean = work / "clean.mp4"
            pcm = work / "scene.f32le"
            clean_audit = _build_clean_visual(
                resolved=resolved,
                route=route,
                output=clean,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            pcm_audit = _build_pcm(
                resolved=resolved,
                route=route,
                output=pcm,
                work=work,
                ffmpeg=ffmpeg,
            )
            product, _ = mature._build_one_product(
                product_id=f"ac0908__{route_id}",
                title=route["title"],
                timeline=_timeline(route),
                clean_visual=clean,
                pcm=pcm,
                cues=route["cues"],
                output_dir=route_dir,
                staging=staging,
                layout=resolved["layout"],
                fonts_dir=fonts_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            product.update(
                {
                    "schema": "magireco-ac0908-complete-entry-route-manifest-v1",
                    "status": STATUS,
                    "product_scope": "independent_dirinfo_route_segment",
                    "session_claim": "one_hash_bound_dirinfo_route",
                    "dirinfo_kind": 33,
                    "dirinfo_row": route["dirinfo_row"],
                    "ordered_events": route["ordered_events"],
                    "source_strong_row": route["source_strong_row"],
                    "entry_contract": {
                        "event": "ac0908_001",
                        "frames": ENTRY_FRAMES,
                        "presentation": "restaurant_exterior_then_side_cooking",
                        "scene_audio_overlay_crosses_outcome_boundary": True,
                    },
                    "dirinfo_evidence": route["dirinfo_evidence"],
                    "source_clean_visual_audit": clean_audit,
                    "source_pcm_audit": pcm_audit,
                    "human_playback_approved_exact_output": False,
                    "publication_approved": False,
                }
            )
            mature.write_json(route_dir / "ROUTE_MANIFEST.json", product)
            shutil.rmtree(work)
            products.append(product)

        shutil.rmtree(staging / "work")
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": STATUS,
            "release_id": resolved["release_id"],
            "family": "ac0908",
            "audio_profile": "no_bgm",
            "native_media": {
                "width": 416,
                "height": 232,
                "frame_rate": "30/1",
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": 48000,
                "audio_channels": 2,
                "upscale": False,
            },
            "content_product_count": len(products),
            "edition_mp4_count": len(products) * len(EDITIONS),
            "routes": products,
            "source_snapshots": resolved["source_snapshots"],
            "owner_approved_presentation_contract": True,
            "human_playback_approved_exact_outputs": False,
            "publication_approved": False,
        }
        qa = {
            "schema": QA_SCHEMA,
            "status": STATUS,
            "automated_spec_qa_passed": True,
            "checks": {
                "dirinfo_rows_6_11_hash_bound_and_exact": True,
                "approved_187_frame_entry_exact": True,
                "entry_audio_overlay_crosses_outcome_boundary": True,
                "outcome_and_outro_pcm_match_approved_v28": True,
                "native_416x232_30fps_no_upscale": True,
                "h264_aac_48khz_stereo": True,
                "none_ja_zh_audio_packets_identical_per_route": True,
                "subtitle_round_trip": True,
                "routes_remain_independent": True,
            },
            "route_count_completed": len(products),
            "final_mp4_count": len(products) * len(EDITIONS),
            "human_playback_approved_exact_outputs": False,
            "publication_approved": False,
        }
        mature.write_json(staging / "BATCH_MANIFEST.json", manifest)
        mature.write_json(staging / "AUTOMATED_QA.json", qa)
        (staging / "README_REVIEW.md").write_text(
            "# ac0908 完整入口六路线\n\n"
            "本目录包含 DirInfo kind 33 rows 6–11 的六条独立路线，每条均为 "
            "none/JA/ZH 三版，共 18 个 MP4。开头固定使用已批准的 187 帧"
            "饭店外景→侧身炒菜入口；入口场景声按 v28 合同跨入菜品结果段。\n\n"
            "自动规格 QA 已通过；新生成的具体 MP4 尚未登记为逐文件人工播放或投稿批准。"
            "rows 52–57 的强入口六路线继续独立保留，未被替换。\n",
            encoding="utf-8",
        )
        sums = {
            "schema": "magireco-versioned-output-sha256-v1",
            "family": "ac0908",
            "files": _tree_hashes(staging),
        }
        mature.write_json(staging / "SHA256SUMS.json", sums)
        staging.replace(destination)
        return destination, qa
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    destination, qa = build(
        plan_path=args.plan.resolve(),
        output_root=args.output_root.resolve(),
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(
        json.dumps(
            {
                "destination": str(destination),
                "status": qa["status"],
                "route_count": qa["route_count_completed"],
                "final_mp4_count": qa["final_mp4_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
