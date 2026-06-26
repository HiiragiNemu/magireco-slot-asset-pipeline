# Runtime AV trust correction - 2026-06-27

## Problem confirmed

User review found that the v18 technical render pipeline had promoted outputs
that were not trustworthy as final animation:

- `ac0921_001` has no expected BGM in the rendered output.
- `ac4901_025` and `ac4901_026` contain voice/subtitle cues while the visible
  character does not visibly speak; the family is also a set of very short,
  near-duplicate variants and not a Bilibili-ready long animation by itself.
- `ac7204` material/result outputs contain role voice audio; these are not pure
  silent/material clips and must not be described as such.

The previous QA only proved stream properties, non-silent audio, and
subtitle/no-subtitle audio equality.  It did not prove runtime-complete audio,
BGM/SE/voice coverage, subtitle correctness, or visual speech consistency.

## Invalidated outputs

The following roots are now explicitly invalidated for coverage and delivery in
`tools/frida_runtime_probe/invalidated_output_roots.json`:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac4901_full
D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac4901_20260626
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7204_full
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7204_character_subset
D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac7204_character_subset_20260626
```

These files are preserved on disk for audit, but `build_coverage_audit.py` now
ignores them when calculating completed single-event QA, series coverage, or
material coverage.

## Recomputed state

After applying the invalidation list:

```json
{
  "ready_events": 521,
  "ready_with_single_event_QA": 304,
  "ready_missing_single_event_QA": 217,
  "ready_with_series_or_preserved": 267,
  "ready_without_series": 254,
  "excluded_with_material_collection": 82,
  "excluded_without_material_collection": 323,
  "invalidated_output_root_count": 6
}
```

The strategy report now also consumes the runtime AV trust audit and writes:

```text
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\av_blocked_queue.csv
```

Current AV trust audit status:

```json
{
  "invalidated_do_not_use": 78,
  "blocked_pending_runtime_av_verification": 10
}
```

## Resolver correction

`resolve_official_event_capture.py` now parses more runtime sound evidence:

- string-based `sound_mng_play_bytes` remains the strongest actual playback
  evidence;
- integer playback calls such as `sound_mng_play_request` and
  `sound_mng_wrap_request` only resolve `arg0`, preventing channel/bank
  arguments from becoming false request IDs;
- integer helper calls are de-duplicated when a same-resource string playback is
  present within five milliseconds;
- pure numeric sound requests can fall back from `sound_resource_id` to
  `ogg_chunk_index` using `internal_audit/sound_id_records.csv`.

Smoke test using the existing official runtime capture
`ac7114_001__runtime.jsonl`:

```json
{
  "event": "ac7114_001",
  "video_assets": 5,
  "resolved_videos": 5,
  "sounds": 5,
  "resolved_ogg": 5,
  "subtitles": 3
}
```

Function-level check for the old BGM clue `9078` now resolves:

```text
request_id=2074
ogg=snd_04718_bank03_ogg_09078.ogg
media_mapping_basis=ogg_chunk_index
```

## New promotion rule

No newly rendered event or series can be promoted to Bilibili-ready output from
technical QA alone.  Promotion now requires:

1. runtime-complete audio evidence, including BGM, SE, and voice where the game
   plays them;
2. subtitle evidence from runtime text, verified override, or another auditable
   source, not merely a sound label when visual speech is questionable;
3. visual/speech consistency review for events containing role voice;
4. semantic lane separation: normal animation, gameplay/result with role voice,
   and pure material/effect collections must remain separate.

The next engineering work should prioritize capturing and resolving the missing
runtime sound mechanism for known bad samples (`ac0921_001`, `ac4901_025/026`,
and representative `ac7204` events) before more broad rendering.
