#!/usr/bin/env python3
"""Summarize the current runtime-pipeline queue and automation lanes.

This report is intentionally derived from machine-readable manifests. It is used
to decide what can be batch-rendered, what belongs in material collections, and
where new runtime/compositor research is more valuable than per-family manual
handling.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


AV_BLOCKING_STATUSES = {
    "invalidated_do_not_use",
    "blocked_pending_runtime_av_verification",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-catalog", required=True)
    parser.add_argument("--coverage-csv", required=True)
    parser.add_argument("--audience-catalog", required=True)
    parser.add_argument("--composition-plans", required=True)
    parser.add_argument("--audience-exclusions", required=True)
    parser.add_argument(
        "--runtime-av-trust-csv",
        default="",
        help="optional output from audit_runtime_av_trust.py",
    )
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--top", type=int, default=12)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def event_prefix(event: str) -> str:
    return event.split("_", 1)[0]


def is_av_blocked(row: dict) -> bool:
    return row.get("av_delivery_status", "") in AV_BLOCKING_STATUSES


def group_prefix(rows: list[dict], event_key: str = "event") -> list[dict]:
    counts = Counter(event_prefix(row[event_key]) for row in rows if row.get(event_key))
    return [
        {"series": series, "count": count}
        for series, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def first_rows_by_prefix(rows: list[dict], limit: int, event_key: str = "event") -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[event_prefix(row[event_key])].append(row)
    result: list[dict] = []
    for series, members in sorted(
        grouped.items(), key=lambda item: (-len(item[1]), item[0])
    ):
        for row in sorted(members, key=lambda item: item[event_key])[:2]:
            result.append(row)
            if len(result) >= limit:
                return result
    return result


def main() -> int:
    args = parse_args()
    production_rows = read_csv(Path(args.production_catalog))
    coverage_rows = read_csv(Path(args.coverage_csv))
    audience_rows = read_csv(Path(args.audience_catalog))
    av_rows = (
        read_csv(Path(args.runtime_av_trust_csv))
        if args.runtime_av_trust_csv and Path(args.runtime_av_trust_csv).exists()
        else []
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    production_by_event = {row["event_name"]: row for row in production_rows}
    av_by_event = {row["event"]: row for row in av_rows if row.get("event")}
    ready_missing = [
        row
        for row in coverage_rows
        if row.get("next_action") == "render_single_event_and_QA"
    ]
    series_review = [
        row
        for row in coverage_rows
        if row.get("next_action") == "review_for_series_or_keep_single_event"
    ]
    material_candidates = [
        row
        for row in coverage_rows
        if row.get("next_action")
        == "material_review_candidate_or_document_exclusion_only"
    ]
    covered_by_material = [
        row
        for row in coverage_rows
        if row.get("next_action") == "covered_by_material_collection"
    ]
    covered_by_single_and_series = [
        row
        for row in coverage_rows
        if row.get("next_action") == "covered_by_single_and_series"
    ]

    ready_missing_rows: list[dict] = []
    for row in ready_missing:
        event = row["event"]
        production = production_by_event.get(event, {})
        av = av_by_event.get(event, {})
        ready_missing_rows.append(
            {
                "event": event,
                "series": event_prefix(event),
                "video_composition_model": production.get(
                    "video_composition_model", ""
                ),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "frame_rate": row.get("frame_rate", ""),
                "render_duration_ms": row.get("render_duration_ms", ""),
                "subtitle_count": row.get("subtitle_count", ""),
                "video_extension_policy": production.get(
                    "video_extension_policy", ""
                ),
                "av_delivery_status": av.get("delivery_status", ""),
                "av_semantic_lane": av.get("semantic_lane", ""),
                "av_risk_flags": av.get("risk_flags", ""),
                "production_manifest": row.get("production_manifest", ""),
            }
        )

    material_rows: list[dict] = []
    for row in material_candidates:
        event = row["event"]
        production = production_by_event.get(event, {})
        av = av_by_event.get(event, {})
        material_rows.append(
            {
                "event": event,
                "series": event_prefix(event),
                "errors": row.get("errors", ""),
                "classification": row.get("classification", ""),
                "video_composition_model": production.get(
                    "video_composition_model", ""
                ),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "subtitle_count": row.get("subtitle_count", ""),
                "audience_exclusion_reason": row.get(
                    "audience_exclusion_reason", ""
                ),
                "av_delivery_status": av.get("delivery_status", ""),
                "av_semantic_lane": av.get("semantic_lane", ""),
                "av_risk_flags": av.get("risk_flags", ""),
                "production_manifest": row.get("production_manifest", ""),
            }
        )

    av_blocked_rows = [
        {
            "event": row["event"],
            "series": event_prefix(row["event"]),
            "delivery_status": row.get("delivery_status", ""),
            "semantic_lane": row.get("semantic_lane", ""),
            "risk_flags": row.get("risk_flags", ""),
            "audio_names": row.get("audio_names", ""),
            "subtitle_texts": row.get("subtitle_texts", ""),
            "production_manifest": row.get("production_manifest", ""),
        }
        for row in av_rows
        if row.get("delivery_status")
        in {"invalidated_do_not_use", "blocked_pending_runtime_av_verification"}
    ]
    ready_missing_actionable_rows = [
        row for row in ready_missing_rows if not is_av_blocked(row)
    ]
    ready_missing_av_blocked_rows = [
        row for row in ready_missing_rows if is_av_blocked(row)
    ]

    write_csv(
        out_dir / "ready_missing_queue.csv",
        ready_missing_actionable_rows,
        [
            "event",
            "series",
            "video_composition_model",
            "width",
            "height",
            "frame_rate",
            "render_duration_ms",
            "subtitle_count",
            "video_extension_policy",
            "av_delivery_status",
            "av_semantic_lane",
            "av_risk_flags",
            "production_manifest",
        ],
    )
    write_csv(
        out_dir / "av_blocked_ready_missing_queue.csv",
        ready_missing_av_blocked_rows,
        [
            "event",
            "series",
            "video_composition_model",
            "width",
            "height",
            "frame_rate",
            "render_duration_ms",
            "subtitle_count",
            "video_extension_policy",
            "av_delivery_status",
            "av_semantic_lane",
            "av_risk_flags",
            "production_manifest",
        ],
    )
    write_csv(
        out_dir / "material_candidate_queue.csv",
        material_rows,
        [
            "event",
            "series",
            "errors",
            "classification",
            "video_composition_model",
            "width",
            "height",
            "subtitle_count",
            "audience_exclusion_reason",
            "av_delivery_status",
            "av_semantic_lane",
            "av_risk_flags",
            "production_manifest",
        ],
    )
    write_csv(
        out_dir / "av_blocked_queue.csv",
        av_blocked_rows,
        [
            "event",
            "series",
            "delivery_status",
            "semantic_lane",
            "risk_flags",
            "audio_names",
            "subtitle_texts",
            "production_manifest",
        ],
    )

    verification_rows: list[dict] = []
    for lane, rows, event_key in (
        ("batch_render_ready_missing", ready_missing_actionable_rows, "event"),
        ("material_review_candidate", material_rows, "event"),
    ):
        for row in first_rows_by_prefix(rows, args.top, event_key):
            verification_rows.append(
                {
                    "lane": lane,
                    "event": row["event"],
                    "series": row["series"],
                    "why": (
                        "ready and only missing render/QA"
                        if lane == "batch_render_ready_missing"
                        else "excluded from clean story and needs material decision"
                    ),
                    "av_delivery_status": row.get("av_delivery_status", ""),
                    "av_semantic_lane": row.get("av_semantic_lane", ""),
                    "av_risk_flags": row.get("av_risk_flags", ""),
                    "production_manifest": row.get("production_manifest", ""),
                }
            )
    write_csv(
        out_dir / "verification_sample_queue.csv",
        verification_rows,
        [
            "lane",
            "event",
            "series",
            "why",
            "av_delivery_status",
            "av_semantic_lane",
            "av_risk_flags",
            "production_manifest",
        ],
    )

    model_counts = Counter(
        f"{row.get('ready', '')}:{row.get('video_composition_model', '')}"
        for row in production_rows
    )
    error_counts: Counter[str] = Counter()
    for row in production_rows:
        for error in row.get("errors", "").split(";"):
            if error:
                error_counts[error] += 1

    audience_class_counts = Counter(row.get("classification", "") for row in audience_rows)
    automatic_counts = Counter(row.get("automatic_candidate", "") for row in audience_rows)
    exclusions_payload = json.loads(Path(args.audience_exclusions).read_text(encoding="utf-8"))
    exclusions_count = len(exclusions_payload.get("events", {}))
    composition_plan_count = len(list(Path(args.composition_plans).glob("*.json")))
    av_status_counts = Counter(row.get("delivery_status", "") for row in av_rows)
    av_risk_counts: Counter[str] = Counter()
    for row in av_rows:
        for flag in row.get("risk_flags", "").split(";"):
            if flag:
                av_risk_counts[flag] += 1

    summary = {
        "production_events": len(production_rows),
        "production_ready_events": sum(row.get("ready") == "yes" for row in production_rows),
        "production_failed_events": sum(row.get("ready") != "yes" for row in production_rows),
        "production_audience_excluded_events": sum(
            bool(row.get("audience_exclusion_reason")) for row in production_rows
        ),
        "ready_missing_single_event_QA": len(ready_missing),
        "ready_missing_single_event_QA_delivery_actionable": len(
            ready_missing_actionable_rows
        ),
        "ready_missing_single_event_QA_av_blocked": len(
            ready_missing_av_blocked_rows
        ),
        "ready_missing_linear": sum(
            production_by_event.get(row["event"], {}).get("video_composition_model")
            == "linear_full_frame_sequence"
            for row in ready_missing
        ),
        "ready_missing_layered": sum(
            production_by_event.get(row["event"], {}).get("video_composition_model")
            == "timed_full_frame_layers"
            for row in ready_missing
        ),
        "ready_series_review_or_keep_single": len(series_review),
        "covered_by_single_and_series": len(covered_by_single_and_series),
        "covered_by_material_collection": len(covered_by_material),
        "material_candidates_without_collection": len(material_candidates),
        "composition_plan_count": composition_plan_count,
        "audience_exclusion_count": exclusions_count,
        "production_ready_by_model": dict(sorted(model_counts.items())),
        "production_error_counts": dict(error_counts.most_common()),
        "audience_catalog_classification_counts": dict(
            audience_class_counts.most_common()
        ),
        "audience_catalog_automatic_candidate_counts": dict(
            automatic_counts.most_common()
        ),
        "runtime_av_trust_status_counts": dict(av_status_counts.most_common()),
        "runtime_av_trust_risk_counts": dict(av_risk_counts.most_common()),
        "ready_missing_top_series": group_prefix(ready_missing, "event")[: args.top],
        "delivery_actionable_ready_missing_top_series": group_prefix(
            ready_missing_actionable_rows, "event"
        )[: args.top],
        "av_blocked_ready_missing_top_series": group_prefix(
            ready_missing_av_blocked_rows, "event"
        )[: args.top],
        "material_candidate_top_series": group_prefix(
            material_candidates, "event"
        )[: args.top],
        "outputs": {
            "ready_missing_queue_csv": str(out_dir / "ready_missing_queue.csv"),
            "av_blocked_ready_missing_queue_csv": str(
                out_dir / "av_blocked_ready_missing_queue.csv"
            ),
            "material_candidate_queue_csv": str(out_dir / "material_candidate_queue.csv"),
            "av_blocked_queue_csv": str(out_dir / "av_blocked_queue.csv"),
            "verification_sample_queue_csv": str(
                out_dir / "verification_sample_queue.csv"
            ),
        },
    }
    (out_dir / "pipeline_strategy_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_lines = [
        "# Runtime pipeline strategy report",
        "",
        "This report is generated from the current production and coverage manifests.",
        "",
        "## Current queue",
        "",
        f"- Production events: {summary['production_events']}",
        f"- Clean-story ready events: {summary['production_ready_events']}",
        f"- Audience-excluded material/gameplay events: {summary['production_audience_excluded_events']}",
        f"- Ready events still missing single-event render/QA: {summary['ready_missing_single_event_QA']}",
        f"- Ready missing render/QA and not AV-blocked: {summary['ready_missing_single_event_QA_delivery_actionable']}",
        f"- Ready missing render/QA but AV-blocked: {summary['ready_missing_single_event_QA_av_blocked']}",
        f"- Of those, linear full-frame batch candidates: {summary['ready_missing_linear']}",
        f"- Of those, already-resolved layered candidates: {summary['ready_missing_layered']}",
        f"- Ready events that have single-event QA but still need series/keep-single decision: {summary['ready_series_review_or_keep_single']}",
        f"- Material/gameplay candidates still without collection coverage: {summary['material_candidates_without_collection']}",
        "",
        "## Runtime audiovisual trust gates",
        "",
    ]
    if av_rows:
        report_lines.extend(
            f"- {key or '<blank>'}: {value}"
            for key, value in summary["runtime_av_trust_status_counts"].items()
        )
        report_lines.extend(["", "Top AV risk flags:", ""])
        report_lines.extend(
            f"- {key}: {value}"
            for key, value in list(
                summary["runtime_av_trust_risk_counts"].items()
            )[: args.top]
        )
    else:
        report_lines.append("- No runtime AV trust audit CSV was provided.")
    report_lines.extend(
        [
            "",
            "## Top delivery-actionable ready families still missing render/QA",
            "",
        ]
    )
    report_lines.extend(
        f"- {row['series']}: {row['count']}"
        for row in summary["delivery_actionable_ready_missing_top_series"]
    )
    report_lines.extend(["", "## Top AV-blocked ready families", ""])
    report_lines.extend(
        f"- {row['series']}: {row['count']}"
        for row in summary["av_blocked_ready_missing_top_series"]
    )
    report_lines.extend(["", "## Top material/gameplay families without collection", ""])
    report_lines.extend(
        f"- {row['series']}: {row['count']}"
        for row in summary["material_candidate_top_series"]
    )
    report_lines.extend(
        [
            "",
            "## Automation conclusion",
            "",
            "The remaining video-composition queue can still be processed in batches: "
            f"{summary['ready_missing_linear']} of "
            f"{summary['ready_missing_single_event_QA']} missing single-event QA items "
            "are linear full-frame sequences. However, technical render/QA is no longer "
            "sufficient for delivery. Promotion to Bilibili-ready single-event or series "
            "outputs must require runtime-complete audio evidence, BGM/SE/voice coverage, "
            "subtitle evidence, and a visual/speech consistency gate. The expensive "
            "research work should now prioritize the missing runtime audio mechanism and "
            "unresolved compositions before more broad rendering.",
            "",
        ]
    )
    (out_dir / "pipeline_strategy_report.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
