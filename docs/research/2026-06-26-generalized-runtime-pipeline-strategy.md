# Generalized runtime pipeline strategy - 2026-06-26

## User concern

The project must not depend on manually reviewing every `ac` family one by one.
That approach is too expensive in conversation time, does not scale, and makes it
unclear whether the remaining animation catalog can be completed before usage
limits are exhausted.

The correct target is a generalized offline reconstruction pipeline: recover how
the game schedules videos, sounds, and subtitles at runtime; encode that as
manifests; batch-render safe events; and reserve human review for policy choices
that the game itself does not know, such as whether a slot/gameplay presentation
belongs in a Bilibili story upload or only in a material collection.

## What the game does

The game does not hand-edit one `ac` family at a time. It schedules an event by
runtime data and engine code:

- `C_AnmBase::fnReqScene` is the official event scheduler.
- Native `EventInfo` maps event labels to event request codes.
- GDB/Z2D data links event objects to DGM video names, callback frames, dynamic
  text objects, and `reqSound` calls.
- Sound requests resolve to official OGG/SMZ/PCM media through the game's sound
  request tables.
- Runtime callback timing determines whether clips are sequential, looped, or
  overlaid by the compositor.

The offline pipeline must therefore reproduce this scheduling model. A raw CRI
video file is only a component. For many events the correct audience video is:

```text
event code -> official DGM timeline -> official OGG timeline -> official subtitle/text evidence -> renderer -> QA
```

Manual family analysis is only justified when a generic rule is still missing or
when a rendered sample is needed to decide audience policy.

## Current generalized state

Generated with:

```powershell
python tools\frida_runtime_probe\report_pipeline_strategy.py `
  --production-catalog A:\magireco_corrected_research_20260612\production_manifests_v18\event_production_catalog.csv `
  --coverage-csv A:\magireco_corrected_research_20260612\coverage_audits_v18_20260626\event_coverage_v18.csv `
  --audience-catalog A:\magireco_corrected_research_20260612\manifests\audience_event_catalog_v1\audience_event_catalog.csv `
  --composition-plans tools\frida_runtime_probe\composition_plans `
  --audience-exclusions tools\frida_runtime_probe\audience_exclusions.json `
  --out-dir A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626
```

Machine-readable outputs:

```text
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\pipeline_strategy_summary.json
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\pipeline_strategy_report.md
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\ready_missing_queue.csv
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\material_candidate_queue.csv
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_20260626\verification_sample_queue.csv
```

Current counts:

| Item | Count |
| --- | ---: |
| Audience event catalog rows | 7753 |
| Catalog rows marked automatic candidate | 2245 |
| v18 production events | 926 |
| Clean-story render-ready events | 521 |
| Already covered by single-event QA and series/preserved output | 310 |
| Ready events with single-event QA but still needing series/keep-single decision | 45 |
| Ready events still missing single-event render/QA | 166 |
| Missing-QA events that are linear full-frame batch candidates | 162 |
| Missing-QA events that are already-resolved layered candidates | 4 |
| Audience-excluded gameplay/material events | 405 |
| Audience-excluded events already covered by material collection | 82 |
| Material/gameplay events still needing material collection or documented exclusion | 323 |
| Explicit composition plans | 154 |
| Explicit audience exclusions | 405 |

Important conclusion: the immediate clean-story backlog is mostly not a research
problem, but `ac7204` proves that a visual/semantic gate is still required after
technical QA. After the generic sample, `ac4901`, and corrected `ac7204`
processing, `162 / 166` ready-but-unrendered events are still linear full-frame
batch candidates. They should be rendered and QAed in controlled chunks, then
checked by contact sheet before any long Bilibili edition is promoted.

## Why manual family passes still happened

The game knows how to play an event, but it does not know this project's upload
policy. It will happily play normal story animation, title cards, attack cuts,
slot prompts, small-Kyubey guide overlays, CHANCE/WIN material, reel UI, and
button prompts. The Bilibili target requires:

- normal animation/story/character output in the clean-story queue;
- slot/gameplay/effect material in separate material collections;
- no upscaling;
- no mixing subtitle/no-subtitle editions;
- no guessed audio/video pairing.

Manual passes so far were used to teach the pipeline these distinctions:

- explicit `composition_plans/*.json` for verified layered events;
- `audience_exclusions.json` for reviewed gameplay/material events;
- material collection manifests for excluded components that should still be
  preserved as videos;
- QA and contact sheets that make the result auditable.

That process should now become a batch workflow: generate queue, render small
sample, run QA, generate contact sheet, accept/reject as a batch, then continue.

## Verification sample generated from the generic queue

A cross-family sample was selected from `verification_sample_queue.csv` and
rendered without per-family manual rules:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626
```

Events:

```text
ac0921_001
ac0921_002
ac4901_025
ac4901_026
ac4908_008
ac4908_009
ac5102_001
ac5102_020
ac5202_001
ac5202_002
ac7204_003
ac7204_004
```

QA result:

```json
{
  "audited_events": 12,
  "passed": 12,
  "failed": 0,
  "subtitle_and_no_subtitle_audio_identical": 12,
  "non_silent_audio": 12,
  "total_output_bytes": 25060345
}
```

Frame audit result:

```json
{
  "videos": 12,
  "accepted_by_frame_screen": 12,
  "review": 0
}
```

Human verification contact sheet:

```text
A:\magireco_corrected_research_20260612\frame_audits_v18_generic_strategy_sample_20260626\generic_strategy_sample_contact_sheet.jpg
```

This sample confirms that the ready-linear queue can produce technically valid
native renders in batch mode. It does not prove that every remaining ready event
is semantically appropriate for the clean-story lane; `ac7204_003` and
`ac7204_004` were later reclassified as material after a fuller family contact
sheet review. The sample still proves the scalable workflow: batch render, QA,
contact-sheet review, then promote or reclassify.

## First full batch after the strategy report

`ac4901` was processed as the first full family using this batch policy:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac4901_full
D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac4901_20260626
A:\magireco_corrected_research_20260612\frame_audits_v18_ac4901_full_render\ac4901_full_contact_sheet.jpg
```

Results:

```json
{
  "single_event_QA": "36/36 passed",
  "frame_audit": "36/36 accepted_by_frame_screen",
  "series_status": "passed",
  "series_event_count": 36,
  "series_expected_duration_ms": 96012,
  "series_actual_duration_ms": 96033,
  "subtitle_cue_count": 36,
  "width": 416,
  "height": 232,
  "frame_rate": "30/1",
  "audio_sample_rate": "48000",
  "audio_channels": 2,
  "direct_stream_copy": true
}
```

This reduced the ready events still missing single-event QA from 244 to 198.
The regenerated coverage audit now reports 350 ready events with single-event QA
and 303 ready events with series/preserved coverage.

## Semantic-gate correction from ac7204

The next batch, `ac7204`, showed why the pipeline cannot treat technical readiness
as the final audience decision. A full 34-event render passed technical QA, but
the contact sheet showed many `地図`, `CHANCE`, `WIN`, colored result-card,
rainbow, and hanabi result presentations. These are gameplay/result materials,
not normal clean-story upload content.

The corrected split is:

```text
Material/result presentation:
ac7204_003..016 and ac7204_029..041

Clean character/serif subset:
ac7204_017 ac7204_021 ac7204_022 ac7204_023 ac7204_042 ac7204_043 ac7204_044
```

Outputs:

```text
D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260626\ac7204
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7204_character_subset
D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac7204_character_subset_20260626
```

This reduced the ready events still missing single-event QA from 198 to 166, but
more importantly it added a hard process rule: a batch can be technically valid
and still be semantically wrong for the clean-story/Bilibili lane.

## Scalable execution policy

### Lane A: clean-story ready queue

Process `ready_missing_queue.csv` in chunks.

Recommended chunk size:

- 20 to 40 events when A drive space is comfortable;
- 8 to 12 events when validating a new event shape;
- stop the chunk only if QA fails or contact sheets show gameplay/material UI.

For each chunk:

1. render with `render_event_batch.py`;
2. run `qa_event_batch.py`;
3. generate frame/contact-sheet audit;
4. keep original single-event files;
5. add successful events to series review only after the single-event outputs are
   proven;
6. build same-scene long editions only when all included events share compatible
   native stream signatures and the family content is appropriate for upload.

### Lane B: material/gameplay queue

Process `material_candidate_queue.csv` by prefix. The largest remaining groups
are:

```text
ac5102 120
ac3102 57
ac0909 25
ac3103 24
ac9051 20
ac4904 15
```

These should not be mixed into normal animation uploads. Use material collection
builders and contact sheets. Human review should decide collection grouping, not
every individual resource unless the group is visually inconsistent.

### Lane C: unresolved compositor/mechanism research

The expensive research should target generic rules, not more manual output:

- recover more runtime `fnReqScene` captures for unresolved composition patterns;
- infer common roles from DGM suffixes only after runtime evidence confirms the
  role, not from name alone;
- improve automatic classification of known gameplay markers such as PUSH,
  CHANCE, WIN, reel UI, black-matte prompt layers, card frames, and small icon
  components;
- keep mixed-dimension events blocked until official canvas placement is known;
- never flatten icons/particle/UI components into a clean-story video just
  because they are available as media files.

## Quota and completion risk

If work continues as pure manual family analysis, it is not acceptable: token
usage will be wasted on classification that can be represented by manifests and
batch reports.

If work follows the lane policy above, the immediate clean-story backlog is
tractable:

- `166` events still need single-event render/QA;
- `162` of those are already linear full-frame candidates;
- rendering/QA cost is compute and disk space, not large model token cost;
- model attention should be spent on failed chunks, visual anomalies, series
  grouping, and missing generic rules.

The main remaining uncertainty is not whether every ready event can be rendered;
the uncertainty is how many excluded/unresolved events should become material
collections versus documented exclusions, and how many mixed/layered compositions
need new runtime captures.

## Required user verification

The user should inspect:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626
A:\magireco_corrected_research_20260612\frame_audits_v18_generic_strategy_sample_20260626\generic_strategy_sample_contact_sheet.jpg
```

If this sample plus the corrected `ac4901/ac7204` batches are acceptable, the
next safe action is to batch-render the top ready families from
`ready_missing_queue.csv`, starting with `ac4908`, while retaining all
single-event files and producing QA/contact-sheet evidence before any long
Bilibili edition is promoted.
