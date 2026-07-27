#!/usr/bin/env python3
"""Build exact production manifests for audience events proven to have no audio.

This lane is intentionally narrow.  It accepts only native full-frame events
whose visual intervals are exact, whose DirInfo row contains exactly one event,
and whose direct-parent audio, child-Z2D audio, and subtitle catalogs all have
zero rows for that event.  Every catalog and every source clip is SHA-256 bound.
An empty audio list is therefore a positive, revalidated claim rather than an
absence accidentally promoted to READY.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

try:
    from .output_path_contract import ensure_resolved_containment
except ImportError:
    from output_path_contract import ensure_resolved_containment  # type: ignore


PLAN_SCHEMA = "magireco-silent-audience-event-manifest-plan-v1"
MANIFEST_SCHEMA = "magireco-event-production-v3"
SUMMARY_SCHEMA = "magireco-silent-audience-event-manifest-summary-v1"
EVENT_PATTERN = r"^ac[0-9]{4}_[0-9]{3}$"
INPUT_LABELS = {
    "audience_event_catalog": "audience_event_catalog",
    "audience_event_clips": "audience_event_clips",
    "audience_event_ledger": "audience_event_ledger",
    "dirinfo_routes": "dirinfo_routes",
    "dirinfo_route_ledger": "dirinfo_route_ledger",
    "direct_parent_audio": "direct_parent_audio_catalog",
    "child_audio": "child_z2d_audio_catalog",
    "subtitles": "subtitle_timeline_catalog",
}
AUDIO_ABSENCE_KEYS = {
    "direct_parent_audio",
    "child_audio",
    "subtitles",
}
BASE_EVENT_DECLARATION_FIELDS = {
    "event",
    "title_zh",
    "dirinfo",
    "source_sha256_by_official_name",
}
BOUNDED_PRODUCT_CONTRACT_FIELDS = {
    "product_scope",
    "natural_session_claimed",
    "loop_scope",
}
LOOP_SCOPE_FIELDS = {
    "policy",
    "loop_clip_official_name",
    "loop_source_frame_count",
    "runtime_loop_count_claimed",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def resolve_locator(
    raw: object, *, plan_dir: Path, label: str
) -> tuple[Path, dict[str, str]]:
    if not isinstance(raw, Mapping) or set(raw) != {"path", "sha256"}:
        raise ValueError(f"{label} locator fields differ")
    path = Path(str(raw["path"]))
    if not path.is_absolute():
        path = plan_dir / path
    path = path.resolve()
    expected = str(raw["sha256"]).upper()
    if (
        len(expected) != 64
        or any(value not in "0123456789ABCDEF" for value in expected)
        or not path.is_file()
        or file_sha256(path) != expected
    ):
        raise ValueError(f"{label} SHA-256 differs")
    return path, {"label": label, "path": str(path), "sha256": expected}


def only(rows: list[dict[str, str]], *, label: str) -> dict[str, str]:
    if len(rows) != 1:
        raise ValueError(f"{label} row count differs: {len(rows)}")
    return rows[0]


def parse_int(value: object, *, label: str) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not an integer") from error


def parse_declared_bool(value: object, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    raise ValueError(f"{label} is not boolean")


def probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-count_frames",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = json.loads(completed.stdout)
    streams = value.get("streams")
    if not isinstance(streams, list):
        raise ValueError(f"ffprobe streams differ: {path}")
    videos = [row for row in streams if row.get("codec_type") == "video"]
    audios = [row for row in streams if row.get("codec_type") == "audio"]
    subtitles = [row for row in streams if row.get("codec_type") == "subtitle"]
    if len(videos) != 1 or audios or subtitles:
        raise ValueError(f"silent source stream contract differs: {path}")
    video = videos[0]
    frame_count = parse_int(
        video.get("nb_read_frames") or video.get("nb_frames"),
        label=f"{path} frame count",
    )
    if (
        video.get("codec_name") != "h264"
        or int(video.get("width", 0)) != 416
        or int(video.get("height", 0)) != 232
        or video.get("r_frame_rate") != "30/1"
        or frame_count <= 0
    ):
        raise ValueError(f"silent source native media contract differs: {path}")
    return {
        "frame_count": frame_count,
        "width": 416,
        "height": 232,
        "frame_rate": "30/1",
        "codec": "h264",
    }


def resolve_source_path(
    raw_path: str, overrides: list[tuple[Path, Path]]
) -> Path:
    source = Path(raw_path)
    for old, new in overrides:
        try:
            relative = source.relative_to(old)
        except ValueError:
            continue
        return (new / relative).resolve()
    return source.resolve()


def zero_audio_matches(
    *,
    event: str,
    direct_rows: list[dict[str, str]],
    child_rows: list[dict[str, str]],
    subtitle_rows: list[dict[str, str]],
) -> dict[str, int]:
    direct = [
        row
        for row in direct_rows
        if str(row.get("primary_animation", "")).strip() == event
    ]
    child = [
        row
        for row in child_rows
        if str(row.get("event_name", "")).strip() == event
    ]
    subtitles = [
        row
        for row in subtitle_rows
        if str(row.get("event_name", "")).strip() == event
    ]
    counts = {
        "direct_parent_audio_matches": len(direct),
        "child_audio_matches": len(child),
        "subtitle_matches": len(subtitles),
    }
    if any(counts.values()):
        raise ValueError(f"{event} no-audio evidence has matches: {counts}")
    return counts


def validate_bounded_product_contract(
    raw: object,
    *,
    event: str,
    clip_rows: list[dict[str, str]],
    frame_counts: Mapping[str, int],
) -> dict[str, Any]:
    """Validate a finite review product that deliberately avoids session claims."""

    if not isinstance(raw, Mapping) or set(raw) != BOUNDED_PRODUCT_CONTRACT_FIELDS:
        raise ValueError(f"{event} bounded product contract fields differ")
    product_scope = str(raw["product_scope"]).strip()
    if not product_scope:
        raise ValueError(f"{event} bounded product scope is empty")
    if raw["natural_session_claimed"] is not False:
        raise ValueError(f"{event} bounded product claims a natural session")
    loop_scope = raw["loop_scope"]
    if not isinstance(loop_scope, Mapping) or set(loop_scope) != LOOP_SCOPE_FIELDS:
        raise ValueError(f"{event} bounded loop scope fields differ")
    if loop_scope["policy"] != "intro_then_exactly_one_complete_source_loop":
        raise ValueError(f"{event} bounded loop policy differs")
    if loop_scope["runtime_loop_count_claimed"] is not False:
        raise ValueError(f"{event} bounded loop count claims runtime evidence")
    loop_name = str(loop_scope["loop_clip_official_name"]).strip()
    expected_frames = parse_int(
        loop_scope["loop_source_frame_count"],
        label=f"{event} bounded loop frame count",
    )
    matching_rows = [
        row for row in clip_rows if str(row.get("official_name", "")) == loop_name
    ]
    if (
        len(matching_rows) != 1
        or matching_rows[0].get("dgm_role") != "orphan_loop_cycle"
        or frame_counts.get(loop_name) != expected_frames
    ):
        raise ValueError(f"{event} bounded loop source binding differs")
    if len(clip_rows) != 2 or clip_rows[0].get("dgm_role") != "single_layer_segment":
        raise ValueError(f"{event} bounded intro/loop occurrence set differs")
    return {
        "product_scope": product_scope,
        "natural_session_claimed": False,
        "loop_scope": {
            "policy": "intro_then_exactly_one_complete_source_loop",
            "loop_clip_official_name": loop_name,
            "loop_source_frame_count": expected_frames,
            "runtime_loop_count_claimed": False,
        },
    }


def write_series_proposals(
    *,
    output_root: Path,
    published_root: Path,
    catalog_rows: list[dict[str, Any]],
    dirinfo_snapshot: Mapping[str, str],
) -> dict[str, Any]:
    """Write hash-bound source catalogs and one proposal per DirInfo event."""

    proposal_root = output_root / "series_proposals"
    proposal_root.mkdir()
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in catalog_rows:
        event = str(row["event"])
        by_family.setdefault(event.split("_", 1)[0], []).append(row)
    proposal_rows: list[dict[str, str]] = []
    for family, rows in by_family.items():
        kinds = {int(row["kind"]) for row in rows}
        if len(kinds) != 1:
            raise ValueError(f"{family} silent source series mixes DirInfo kinds")
        source_name = f"{family}_dirinfo_silent_event_source_v1.json"
        source_path = proposal_root / source_name
        source_series = {
            "schema": "magireco-series-editions-v1",
            "series": family,
            "proposal_id": f"{family}_dirinfo_silent_event_source_v1",
            "status": "passed",
            "errors": [],
            "ordering": (
                f"DirInfo kind {next(iter(kinds))} row order; every row is an "
                "independent event and sibling rows must never be concatenated."
            ),
            "event_count": len(rows),
            "native_dimensions": {"width": 416, "height": 232},
            "native_frame_rate": "30/1",
            "dimension_policy": (
                "exact_native_only_no_resize_no_pad_no_crop_no_upscale"
            ),
            "dirinfo_evidence": {
                "path": str(dirinfo_snapshot["path"]),
                "sha256": str(dirinfo_snapshot["sha256"]),
                "kind": next(iter(kinds)),
                "rows": [
                    {
                        "row_index": int(row["row_index"]),
                        "event": str(row["event"]),
                        "event_info_index": int(row["event_info_index"]),
                        "code_hex": str(row["code_hex"]),
                    }
                    for row in rows
                ],
            },
            "family_state": {
                "production_manifest_root": str(published_root.resolve()),
                "ready_event_names": [str(row["event"]) for row in rows],
            },
            "product_scopes": {
                str(row["event"]): str(
                    row.get("product_scope") or "independent_event_exact"
                )
                for row in rows
            },
            "natural_session_claims": {
                str(row["event"]): parse_declared_bool(
                    row.get("natural_session_claimed", True),
                    label=f"{row['event']} natural-session claim",
                )
                for row in rows
            },
        }
        write_json(source_path, source_series)
        source_sha256 = file_sha256(source_path)
        for row in rows:
            event = str(row["event"])
            manifest_path = output_root / "events" / f"{event}.json"
            if (
                not manifest_path.is_file()
                or file_sha256(manifest_path)
                != str(row["manifest_sha256"]).upper()
            ):
                raise ValueError(f"{event} current silent manifest SHA differs")
            proposal_path = (
                proposal_root / f"{event}_silent_event_exact_editions_v1.json"
            )
            proposal = {
                "schema": "magireco-series-editions-v1",
                "series": event,
                "proposal_id": f"{event}_silent_event_exact_editions_v1",
                "status": "passed",
                "errors": [],
                "ordering": (
                    f"single DirInfo kind {row['kind']} row {row['row_index']} "
                    "event; independent product only"
                ),
                "event_count": 1,
                "native_dimensions": {"width": 416, "height": 232},
                "native_frame_rate": "30/1",
                "dimension_policy": (
                    "exact_native_only_no_resize_no_pad_no_crop_no_upscale"
                ),
                "source_series_manifest": {
                    "path": source_name,
                    "sha256": source_sha256,
                    "evidence": (
                        f"Hash-bound DirInfo kind {row['kind']} row "
                        f"{row['row_index']} proves exactly {event}."
                    ),
                },
                "family_state": {
                    "production_manifest_root": str(published_root.resolve()),
                    "ready_event_names": [event],
                },
                "event_manifest_sha256": {
                    event: str(row["manifest_sha256"]).upper()
                },
                "scope_boundary": (
                    (
                        f"Independent DirInfo row {row['row_index']} only; "
                        "finite profile-material review product contains the "
                        "intro and exactly one complete source loop. It does "
                        "not claim a natural runtime session or runtime loop "
                        "count, and does not concatenate any sibling event."
                    )
                    if not parse_declared_bool(
                        row.get("natural_session_claimed", True),
                        label=f"{event} natural-session claim",
                    )
                    else (
                        f"Independent DirInfo row {row['row_index']} only; "
                        "does not concatenate any sibling event or outcome."
                    )
                ),
                "product_scope": str(
                    row.get("product_scope") or "independent_event_exact"
                ),
                "natural_session_claimed": parse_declared_bool(
                    row.get("natural_session_claimed", True),
                    label=f"{event} natural-session claim",
                ),
            }
            if row.get("loop_scope"):
                loop_scope = row["loop_scope"]
                if isinstance(loop_scope, str):
                    loop_scope = json.loads(loop_scope)
                if not isinstance(loop_scope, Mapping):
                    raise ValueError(f"{event} proposal loop scope differs")
                proposal["loop_scope"] = dict(loop_scope)
            write_json(proposal_path, proposal)
            proposal_rows.append(
                {
                    "family": family,
                    "event": event,
                    "source_series_manifest": str(
                        (
                            published_root
                            / "series_proposals"
                            / source_path.name
                        ).resolve()
                    ),
                    "source_series_sha256": source_sha256,
                    "proposal": str(
                        (
                            published_root
                            / "series_proposals"
                            / proposal_path.name
                        ).resolve()
                    ),
                    "proposal_sha256": file_sha256(proposal_path),
                }
            )
    index_path = proposal_root / "SERIES_PROPOSAL_INDEX.csv"
    write_csv(
        index_path,
        proposal_rows,
        [
            "family",
            "event",
            "source_series_manifest",
            "source_series_sha256",
            "proposal",
            "proposal_sha256",
        ],
    )
    return {
        "source_series_count": len(by_family),
        "event_proposal_count": len(proposal_rows),
        "index_path": str(
            (published_root / "series_proposals" / index_path.name).resolve()
        ),
        "index_sha256": file_sha256(index_path),
    }


def build_manifest_root(
    plan_path: Path,
    out_root: Path,
    *,
    published_root: Path | None = None,
    ffprobe: str,
) -> dict[str, Any]:
    plan_path = plan_path.resolve()
    plan = read_json(plan_path)
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("silent audience event plan schema differs")
    inputs = plan.get("inputs")
    if not isinstance(inputs, Mapping) or set(inputs) != set(INPUT_LABELS):
        raise ValueError("silent audience event input set differs")
    input_paths: dict[str, Path] = {}
    snapshots: dict[str, dict[str, str]] = {}
    for key, label in INPUT_LABELS.items():
        path, source = resolve_locator(
            inputs[key], plan_dir=plan_path.parent, label=label
        )
        input_paths[key] = path
        snapshots[key] = source

    overrides_raw = plan.get("source_root_overrides")
    if not isinstance(overrides_raw, list):
        raise ValueError("silent source-root overrides differ")
    overrides: list[tuple[Path, Path]] = []
    for raw in overrides_raw:
        if not isinstance(raw, Mapping) or set(raw) != {"from", "to"}:
            raise ValueError("silent source-root override fields differ")
        old = Path(str(raw["from"]))
        new = Path(str(raw["to"])).resolve()
        if not old.is_absolute() or not new.is_dir():
            raise ValueError("silent source-root override differs")
        overrides.append((old, new))

    tables = {key: read_csv(path) for key, path in input_paths.items()}
    events_raw = plan.get("events")
    if not isinstance(events_raw, list) or not events_raw:
        raise ValueError("silent audience event plan has no events")
    event_names = [str(row.get("event", "")) for row in events_raw]
    if len(set(event_names)) != len(event_names):
        raise ValueError("silent audience event plan contains duplicates")

    published_root = (published_root or out_root).resolve()
    events_dir = out_root / "events"
    events_dir.mkdir(parents=True)
    catalog_rows: list[dict[str, Any]] = []
    for declaration in events_raw:
        if not isinstance(declaration, Mapping) or set(declaration) not in (
            BASE_EVENT_DECLARATION_FIELDS,
            BASE_EVENT_DECLARATION_FIELDS | {"product_contract"},
        ):
            raise ValueError("silent audience event declaration fields differ")
        event = str(declaration["event"])
        if not re.fullmatch(EVENT_PATTERN, event):
            raise ValueError(f"silent audience event identity differs: {event}")
        title = str(declaration["title_zh"]).strip()
        if not title:
            raise ValueError(f"{event} title is empty")
        source_hashes = declaration["source_sha256_by_official_name"]
        if not isinstance(source_hashes, Mapping) or not source_hashes:
            raise ValueError(f"{event} source hash map differs")
        normalized_hashes = {
            str(name): str(value).upper() for name, value in source_hashes.items()
        }
        if any(
            not name
            or len(value) != 64
            or any(character not in "0123456789ABCDEF" for character in value)
            for name, value in normalized_hashes.items()
        ):
            raise ValueError(f"{event} source hash differs")

        audience = only(
            [
                row
                for row in tables["audience_event_catalog"]
                if row.get("event_name") == event
            ],
            label=f"{event} audience event",
        )
        ledger = only(
            [
                row
                for row in tables["audience_event_ledger"]
                if row.get("event_name") == event
            ],
            label=f"{event} audience ledger",
        )
        if any(
            (
                audience.get("classification") != "native_full_frame_only",
                audience.get("dimensions") != "416x232",
                audience.get("has_auto_voice") != "no",
                audience.get("auto_voice_count") != "0",
                audience.get("automatic_candidate") != "yes",
                audience.get("clip_count")
                != audience.get("resolved_clip_count"),
                audience.get("clip_count")
                != audience.get("full_frame_clip_count"),
                ledger.get("production_state")
                != "missing_modern_event_manifest",
                ledger.get("classification") != "native_full_frame_only",
                ledger.get("disposition") != "blocked",
            )
        ):
            raise ValueError(f"{event} audience readiness state differs")

        dirinfo = declaration["dirinfo"]
        if not isinstance(dirinfo, Mapping) or set(dirinfo) != {
            "kind",
            "row_index",
            "event_info_index",
            "code_hex",
        }:
            raise ValueError(f"{event} DirInfo declaration fields differ")
        route = only(
            [
                row
                for row in tables["dirinfo_routes"]
                if parse_int(row.get("kind"), label="DirInfo kind")
                == int(dirinfo["kind"])
                and parse_int(row.get("row_index"), label="DirInfo row")
                == int(dirinfo["row_index"])
            ],
            label=f"{event} raw DirInfo",
        )
        route_ledger = only(
            [
                row
                for row in tables["dirinfo_route_ledger"]
                if parse_int(row.get("kind"), label="route-ledger kind")
                == int(dirinfo["kind"])
                and parse_int(row.get("row_index"), label="route-ledger row")
                == int(dirinfo["row_index"])
            ],
            label=f"{event} DirInfo ledger",
        )
        if (
            route.get("scene_name") != event
            or parse_int(
                route.get("event_info_index"), label=f"{event} event-info index"
            )
            != int(dirinfo["event_info_index"])
            or route.get("code_hex") != dirinfo["code_hex"]
            or route.get("route_status") != "ok"
            or parse_int(route.get("selector_raw"), label=f"{event} selector")
            != 0
            or route_ledger.get("ordered_events") != event
            or route_ledger.get("selector_count") != "1"
            or route_ledger.get("route_statuses") != "ok"
        ):
            raise ValueError(f"{event} DirInfo identity/order differs")
        if audience.get("code_hex") != dirinfo["code_hex"]:
            raise ValueError(f"{event} audience code differs from DirInfo")

        absence_counts = zero_audio_matches(
            event=event,
            direct_rows=tables["direct_parent_audio"],
            child_rows=tables["child_audio"],
            subtitle_rows=tables["subtitles"],
        )
        clip_rows = [
            row
            for row in tables["audience_event_clips"]
            if row.get("event_name") == event
        ]
        clip_rows.sort(
            key=lambda row: (
                parse_int(row.get("event_start_ms"), label=f"{event} start"),
                parse_int(row.get("z2d_order"), label=f"{event} z2d order"),
                parse_int(row.get("dgm_order"), label=f"{event} dgm order"),
            )
        )
        if (
            len(clip_rows) != parse_int(
                audience["clip_count"], label=f"{event} clip count"
            )
            or {str(row.get("official_name", "")) for row in clip_rows}
            != set(normalized_hashes)
        ):
            raise ValueError(f"{event} clip occurrence set differs")

        clips: list[dict[str, Any]] = []
        plan_clips: list[dict[str, Any]] = []
        frame_counts_by_name: dict[str, int] = {}
        cumulative_frames = 0
        for order, row in enumerate(clip_rows):
            name = str(row.get("official_name", "")).strip()
            if (
                row.get("interval_confidence") != "exact_duration_unique"
                or row.get("width") != "416"
                or row.get("height") != "232"
                or row.get("frame_rate") != "30/1"
            ):
                raise ValueError(f"{event} exact native clip evidence differs: {name}")
            raw_path = str(row.get("source_mp4") or "").strip()
            source_path = resolve_source_path(raw_path, overrides)
            expected_hash = normalized_hashes[name]
            if (
                not source_path.is_file()
                or file_sha256(source_path) != expected_hash
            ):
                raise ValueError(f"{event} source SHA-256 differs: {name}")
            media = probe_video(source_path, ffprobe)
            frame_counts_by_name[name] = int(media["frame_count"])
            start_ms = round(Fraction(cumulative_frames * 1000, 30))
            cumulative_frames += int(media["frame_count"])
            end_ms = round(Fraction(cumulative_frames * 1000, 30))
            if (
                parse_int(row.get("event_start_ms"), label=f"{event} start")
                != start_ms
                or parse_int(row.get("event_end_ms"), label=f"{event} end")
                != end_ms
            ):
                raise ValueError(f"{event} clip frame interval differs: {name}")
            clips.append(
                {
                    "order": order,
                    "dgm_name": name,
                    "dgm_role": str(row.get("dgm_role", "")).strip(),
                    "path": str(source_path),
                    "event_start_ms": start_ms,
                    "event_end_ms": end_ms,
                    "interval_confidence": "exact_duration_unique",
                    "source_sha256": expected_hash,
                }
            )
            plan_clips.append(
                {
                    "dgm_name": name,
                    "role": "background",
                    "start_ms": start_ms,
                }
            )
        product_contract = None
        if "product_contract" in declaration:
            product_contract = validate_bounded_product_contract(
                declaration["product_contract"],
                event=event,
                clip_rows=clip_rows,
                frame_counts=frame_counts_by_name,
            )
        render_duration_ms = round(Fraction(cumulative_frames * 1000, 30))
        total_source_duration_ms = round(
            float(audience["total_source_duration_sec"]) * 1000
        )
        if total_source_duration_ms != render_duration_ms:
            raise ValueError(f"{event} total source duration differs")
        samples = cumulative_frames * 1600
        absence_sources = [
            snapshots[key] for key in INPUT_LABELS if key in AUDIO_ABSENCE_KEYS
        ]
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "event": event,
            "event_code_hex": str(dirinfo["code_hex"]),
            "title_zh": title,
            "classification": "native_full_frame_only",
            "audience_exclusion_reason": "",
            "native_dimensions": {"width": 416, "height": 232},
            "native_frame_rate": "30/1",
            "video_duration_ms": render_duration_ms,
            "timeline_duration_ms": render_duration_ms,
            "timeline_content_end_ms": render_duration_ms,
            "raw_render_duration_ms": render_duration_ms,
            "render_frame_count": cumulative_frames,
            "render_duration_ms": render_duration_ms,
            "render_duration_quantization": {
                "policy": "exact_complete_cfr_frame_grid",
                "frame_rate": "30/1",
                "frame_count": cumulative_frames,
                "content_end_ms": render_duration_ms,
                "duration_ms": render_duration_ms,
                "exact_duration_ms_numerator": cumulative_frames * 100,
                "exact_duration_ms_denominator": 3,
                "audio_sample_rate": 48000,
                "audio_sample_count": samples,
                "padding_ms": 0,
            },
            "video_extension_policy": "none",
            "video_composition_model": "linear_full_frame_sequence",
            "composition_plan": {
                "schema": "magireco-video-composition-v1",
                "event": event,
                "model": "linear_full_frame_sequence",
                "duration_ms": render_duration_ms,
                "extension_policy": "none",
                "native_dimensions": {"width": 416, "height": 232},
                "evidence": (
                    "Hash-bound audience clip catalog exact_duration_unique "
                    "intervals and the exact one-event DirInfo row prove this "
                    "native full-frame linear sequence."
                ),
                "clips": plan_clips,
            },
            "composition_plan_source": str(plan_path),
            "overlap_count": 0,
            "gap_count": 0,
            "timeline_tolerance_ms": 0,
            "clips": clips,
            "audio": [],
            "subtitles": [],
            "audio_absence_evidence": {
                "status": "hash_bound_zero_matches",
                **absence_counts,
                "matching_policy": {
                    "direct_parent_audio": "primary_animation_equals_event",
                    "child_audio": "event_name_equals_event",
                    "subtitles": "event_name_equals_event",
                },
                "source_snapshots": absence_sources,
            },
            "source_catalog_snapshots": list(snapshots.values()),
            "dirinfo_binding": {
                "kind": int(dirinfo["kind"]),
                "row_index": int(dirinfo["row_index"]),
                "event_info_index": int(dirinfo["event_info_index"]),
                "code_hex": str(dirinfo["code_hex"]),
                "selector_raw": 0,
                "ordered_events": [event],
            },
            "quality_gates": {
                "all_full_frame": True,
                "all_clips_exist": True,
                "all_audio_exist": True,
                "verified_subtitle_voice_count": 0,
                "exact_z2d_req_sound_count": 0,
                "linear_video_timeline": True,
                "video_composition_model": "linear_full_frame_sequence",
                "composition_resolved": True,
                "composition_evidence": (
                    "hash_bound_exact_duration_unique_and_single_dirinfo_event"
                ),
                "video_extension_supported": True,
                "audio_timeline_ready": True,
                "verified_no_event_audio": True,
                "errors": [],
                "render_ready": True,
                "ready": True,
            },
        }
        if product_contract is not None:
            manifest.update(product_contract)
            manifest["composition_plan"]["evidence"] = (
                "Hash-bound audience clip catalog exact-duration intervals "
                "prove the finite intro plus one complete source-loop product. "
                "The exact one-event DirInfo row binds event identity only; "
                "runtime loop count and natural-session duration are not claimed."
            )
            manifest["composition_plan"]["product_scope"] = product_contract[
                "product_scope"
            ]
            manifest["composition_plan"]["natural_session_claimed"] = False
            manifest["composition_plan"]["loop_scope"] = product_contract[
                "loop_scope"
            ]
            manifest["quality_gates"]["natural_session_timeline_proven"] = False
        manifest_path = events_dir / f"{event}.json"
        write_json(manifest_path, manifest)
        catalog_rows.append(
            {
                "event": event,
                "title_zh": title,
                "kind": int(dirinfo["kind"]),
                "row_index": int(dirinfo["row_index"]),
                "event_info_index": int(dirinfo["event_info_index"]),
                "code_hex": str(dirinfo["code_hex"]),
                "clip_count": len(clips),
                "frame_count": cumulative_frames,
                "duration_ms": render_duration_ms,
                "width": 416,
                "height": 232,
                "audio_match_count": 0,
                "subtitle_match_count": 0,
                "product_scope": (
                    product_contract["product_scope"]
                    if product_contract is not None
                    else "independent_event_exact"
                ),
                "natural_session_claimed": (
                    "no" if product_contract is not None else "yes"
                ),
                "loop_scope": (
                    json.dumps(
                        product_contract["loop_scope"],
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if product_contract is not None
                    else ""
                ),
                "ready": "yes",
                "manifest_path": str(
                    (published_root / "events" / manifest_path.name).resolve()
                ),
                "manifest_sha256": file_sha256(manifest_path),
            }
        )

    catalog_path = out_root / "event_production_catalog.csv"
    write_csv(
        catalog_path,
        catalog_rows,
        [
            "event",
            "title_zh",
            "kind",
            "row_index",
            "event_info_index",
            "code_hex",
            "clip_count",
            "frame_count",
            "duration_ms",
            "width",
            "height",
            "audio_match_count",
            "subtitle_match_count",
            "product_scope",
            "natural_session_claimed",
            "loop_scope",
            "ready",
            "manifest_path",
            "manifest_sha256",
        ],
    )
    write_json(
        out_root / "SOURCE_SNAPSHOTS.json",
        {
            "schema": "magireco-source-snapshots-v1",
            "plan": {
                "label": "silent audience event manifest plan",
                "path": str(plan_path),
                "sha256": file_sha256(plan_path),
            },
            "sources": list(snapshots.values()),
        },
    )
    proposal_summary = write_series_proposals(
        output_root=out_root,
        published_root=published_root,
        catalog_rows=catalog_rows,
        dirinfo_snapshot=snapshots["dirinfo_routes"],
    )
    summary = {
        "schema": SUMMARY_SCHEMA,
        "status": "passed",
        "event_count": len(catalog_rows),
        "total_frames": sum(int(row["frame_count"]) for row in catalog_rows),
        "total_duration_ms": sum(int(row["duration_ms"]) for row in catalog_rows),
        "native_dimensions": {"width": 416, "height": 232},
        "native_frame_rate": "30/1",
        "verified_no_event_audio_count": len(catalog_rows),
        "events": [row["event"] for row in catalog_rows],
        "series_proposals": proposal_summary,
        "catalog": {
            "path": str(
                (published_root / "event_production_catalog.csv").resolve()
            ),
            "sha256": file_sha256(catalog_path),
        },
        "human_playback_approved": False,
        "bilibili_release_ready": False,
    }
    write_json(out_root / "event_production_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--augment-existing-proposals", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan_path = Path(args.plan).resolve()
    destination = Path(args.out_root).resolve()
    parent = destination.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"output parent is missing: {parent}")
    ensure_resolved_containment(parent, destination, label="silent manifest root")
    if args.augment_existing_proposals:
        if not destination.is_dir():
            raise FileNotFoundError(f"existing output root is missing: {destination}")
        proposal_root = destination / "series_proposals"
        if proposal_root.exists():
            raise FileExistsError(
                f"series proposal root already exists: {proposal_root}"
            )
        plan = read_json(plan_path)
        dirinfo_path, dirinfo_snapshot = resolve_locator(
            plan["inputs"]["dirinfo_routes"],
            plan_dir=plan_path.parent,
            label="dirinfo_routes",
        )
        del dirinfo_path
        catalog_path = destination / "event_production_catalog.csv"
        catalog_rows = read_csv(catalog_path)
        summary = write_series_proposals(
            output_root=destination,
            published_root=destination,
            catalog_rows=catalog_rows,
            dirinfo_snapshot=dirinfo_snapshot,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if destination.exists():
        raise FileExistsError(f"output root already exists: {destination}")
    staging = parent / f".{destination.name}.staging.{uuid.uuid4().hex}"
    ensure_resolved_containment(parent, staging, label="silent manifest staging")
    staging.mkdir()
    try:
        summary = build_manifest_root(
            plan_path,
            staging.resolve(),
            published_root=destination,
            ffprobe=args.ffprobe,
        )
        staging.rename(destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
