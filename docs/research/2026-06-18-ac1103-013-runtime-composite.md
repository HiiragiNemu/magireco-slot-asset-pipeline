# ac1103_013 Runtime Composite Correction - 2026-06-18

## Scope

This note records the corrected single-event pipeline for `ac1103_013`.
The goal was to fix the earlier failure mode where bulk outputs mixed
subtitle/no-subtitle variants, upscaled native assets, and still missed the
official character voice path.

This pass only accepts evidence that is either:

- observed directly from official runtime capture, or
- explicitly encoded in a reviewed composition plan tied back to that capture.

## Corrected conclusions

`ac1103_013` is not a simple linear concat clip and it is not a silent
subtitle-only event.

Runtime capture proves that the event contains:

- a sequence of full-frame background clips
  `c017 -> c018 -> c019 -> c020 -> c012 -> c012_LP`;
- a native scaled victory sparkle overlay;
- a later win-logo overlay with loop;
- independent voice playback through runtime `reqSound` callbacks;
- graphical subtitle text that aligns with the spoken lines.

This invalidates the earlier failure mode where subtitle presence was treated
as the only signal for character voice.

## Runtime evidence

Capture root:

```text
A:\magireco_corrected_research_20260612\runtime_sequence_20260613\captures\ac1103_011_to_013_v1
```

Resolved runtime manifest:

```text
A:\magireco_corrected_research_20260612\runtime_sequence_20260613\resolved\ac1103_013_v1\event_manifest.json
```

Resolved subtitle timeline:

```text
A:\magireco_corrected_research_20260612\runtime_sequence_20260613\resolved\ac1103_013_v1\subtitle_timeline.csv
```

The subtitle resolver was corrected to merge adjacent duplicate runtime text
rows caused by split voice callbacks. The line `ぃよっしゃあー！` is now emitted
as one subtitle row instead of two overlapping rows.

## Official audio recovered

The corrected runtime manifest for `ac1103_013` includes 8 official OGG-backed
audio tracks:

1. `4312_出前修行【CLEAR】_013`
2. `16822_tur_出前修行_神浜の地理を知り尽くした-`
3. `16823_tur_出前修行_なめるなよ`
4. `17758_fer_出前修行_ぃよっ`
5. `17759_fer_出前修行_しゃあー`
6. `16816_tur_出前修行_一件落着だね`
7. `4030_CZ_WINロゴ表示`
8. `0554 CZ用勝利ジングル`

The final rendered event uses the same mixed audio timeline for subtitle and
no-subtitle editions.

## Production manifest

The corrected event was promoted into:

```text
A:\magireco_corrected_research_20260612\production_manifests_v15\events\ac1103_013.json
```

Important properties:

- `classification = verified_native_composite`
- `native_dimensions = 416x232`
- `native_frame_rate = 30/1`
- `video_duration_ms = 17567`
- `timeline_duration_ms = 17987`
- `render_duration_ms = 17987`
- `video_extension_policy = loop_last_clip`
- `video_composition_model = timed_full_frame_layers`

## Rendered outputs

Validated output root:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013
```

Rendered files:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013\ac1103_013\without_subtitles\ac1103_013.mp4
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013\ac1103_013\with_subtitles\ac1103_013__subtitles.mp4
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013\ac1103_013\subtitles\ac1103_013.srt
```

Observed render properties:

- output resolution remains `416x232`
- output frame rate remains `30 fps`
- both editions contain AAC audio at `48 kHz`
- subtitle and no-subtitle outputs are kept in separate directories

## QA result

QA command result:

```text
[passed] ac1103_013
subtitle_and_no_subtitle_audio_identical = 1
non_silent_audio = 1
```

QA artifacts:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013\full_qa_audit.csv
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_013\full_qa_summary.json
```

## Clean review set

For manual review, only the currently validated `ac1103` outputs were copied
into:

```text
A:\magireco_corrected_research_20260612\validated_ac1103_runtime_set_v1
```

This directory contains:

- `ac1103_006`
- `ac1103_012`
- `ac1103_013`

These are copies of already validated outputs. The source validation
directories remain unchanged.

## Next work

1. Extend the same runtime-proof pipeline to more dialogue-heavy events that
   previously rendered as silent or subtitle-only.
2. Use runtime capture to confirm additional composite families before enabling
   any broader batch render.
3. Keep subtitle/no-subtitle editions separate and preserve native dimensions
   for every future validated event.

## Follow-up on 2026-06-18

After the initial `ac1103_013` correction, the production-manifest builder was
audited again. Two regressions were found and fixed:

1. `asset_manifests/event_audio_components.csv` currently preserves
   `ogg_name` but leaves `ogg_path` blank. The builder now backfills the path
   from known official OGG roots instead of marking the event silent or
   incomplete.
2. Accepted graphical subtitle rows for several `ac1103` events use
   `timeline_confidence = exact_gdb_frame_only`. The builder now accepts these
   rows again and reads their `subtitle_start_ms` / `subtitle_end_ms` fields
   correctly.

The fallback `official_voice_label` subtitle path was also tightened so it no
longer duplicates a graphical subtitle that already covers the same
`voice_request_id`.

## ac1103 family v15 validation

With those regressions fixed, the following four `ac1103` events were rendered
again from `production_manifests_v15` and passed QA together:

- `ac1103_005`
- `ac1103_006`
- `ac1103_012`
- `ac1103_013`

Validation root:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_family
```

QA summary:

```text
audited_events = 4
passed = 4
subtitle_and_no_subtitle_audio_identical = 4
non_silent_audio = 4
```

Clean review set:

```text
A:\magireco_corrected_research_20260612\validated_ac1103_runtime_set_v2
```

## Full ac1103 render set

Once the builder regressions were fixed, every `ac1103_*` event in
`production_manifests_v15` became render-ready.

Full render root:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1103_all
```

Full QA summary:

```text
audited_events = 13
passed = 13
subtitle_and_no_subtitle_audio_identical = 13
non_silent_audio = 13
```

Full review set:

```text
A:\magireco_corrected_research_20260612\validated_ac1103_full_v15
```
