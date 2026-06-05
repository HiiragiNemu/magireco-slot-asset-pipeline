# Bilibili Production Workflow

## Production inputs

Use the verified production plan:

```text
A:\magireco_bili_fulltest_20260603\
  event_production_plan_v5_media_fallback\
  event_canvas_production_plan.csv
```

Use limited official-audio event outputs:

```text
D:\MagiReco_Reverse\
  magireco_bili_event_renders_limited_20260606\events
```

The audible upload plan is:

```text
A:\magireco_bili_fulltest_20260603\
  bilibili_part_plan_audible_v4_media_fallback
```

It contains 5,485 event/canvas rows in 294 planned parts.

## Grouping rules

- Event order follows the recovered EventCn event index and natural event name.
- Events are never merged across an official `acXXXX` root.
- Different decoded Z2D canvases remain separate groups.
- A part targets 20 minutes and at most 100 events.
- A 0.25 second black frame and silence separate adjacent events.
- Subtitle editions use a burned-subtitle source only for exact dialogue
  events; all other events reuse the no-subtitle source.
- EventCn sound labels are title candidates and require human review.

This reduces thousands of short fragments without inventing continuity across
unrelated official event roots.

## Build command

Example for one part:

```powershell
python magireco_asset_pipeline.py build-bilibili-part `
  --sequence-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v4_media_fallback\bilibili_event_sequence.csv `
  --parts-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v4_media_fallback\bilibili_parts.csv `
  --part-number 2 `
  --out-dir A:\magireco_bili_fulltest_20260603\bilibili_parts `
  --edition both `
  --encoder h264_nvenc `
  --cq 19 `
  --audio-bitrate 256k `
  --loudness-i -16 `
  --true-peak-db -3 `
  --cleanup-work `
  --execute
```

The builder:

1. Scales each event into a 1920x1080 black-padded canvas.
2. Converts intermediate audio to lossless FLAC.
3. Adds the planned black/silent separator.
4. Concatenates uniform intermediate segments.
5. Copies the final H.264 stream.
6. Applies whole-part loudness and true-peak control.
7. Encodes one final 48 kHz stereo AAC stream.

When a part contains no subtitle events, the subtitle filename is created as a
hard link to the no-subtitle output on the same volume. Both filenames remain
available without storing duplicate media bytes.

The complete 8,482-event plan can also reuse an already-built audible plan.
Pass the three `--reuse-*` arguments together:

```powershell
python magireco_asset_pipeline.py build-bilibili-part `
  --sequence-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_all_v4_media_fallback\bilibili_event_sequence.csv `
  --parts-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_all_v4_media_fallback\bilibili_parts.csv `
  --out-dir D:\MagiReco_Reverse\magireco_bilibili_parts_all_20260606 `
  --all-parts --edition both `
  --reuse-sequence-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v4_media_fallback\bilibili_event_sequence.csv `
  --reuse-parts-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v4_media_fallback\bilibili_parts.csv `
  --reuse-output-dir D:\MagiReco_Reverse\magireco_bilibili_parts_audible_20260606 `
  --encoder h264_nvenc --cq 19 --audio-bitrate 256k `
  --loudness-i -16 --true-peak-db -3 --cleanup-work --execute
```

Reuse requires an exact event-sequence signature: event name, canvas, planned
duration, separator duration, no-subtitle input, and subtitle-edition input.
The output is hard-linked when both directories are on the same volume, with a
copy fallback only when linking is unavailable.

Verified P002 result:

- Events: 12
- Duration: 158.617 seconds
- Video: H.264, 1920x1080, 30 fps
- Audio: AAC, 48 kHz, stereo
- Mean decoded level: -18.6 dBFS
- Maximum decoded level: -3.0 dBFS
- Subtitle and no-subtitle frames differ at dialogue time
- Event separator sample is pure black

## Output audit

Audit all completed part files with:

```powershell
python magireco_asset_pipeline.py bilibili-part-output-audit `
  --parts-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v4_media_fallback\bilibili_parts.csv `
  --output-dir D:\MagiReco_Reverse\magireco_bilibili_parts_audible_20260606 `
  --out-dir A:\magireco_bili_fulltest_20260603\bilibili_part_output_audit_audible_final `
  --workers 4
```

The audit verifies streams, canvas, average frame rate, 48 kHz stereo AAC,
decoded audibility, decoded peak, planned duration, and the hard-link relation
between editions that contain no subtitle events.

The completed audible set passed all 588 logical-output checks. It contains
359 unique physical media files and 229 verified no-dialogue hard-link pairs;
the highest decoded peak is -0.5 dBFS.

Verify all burned-subtitle event sources independently with:

```powershell
python magireco_asset_pipeline.py subtitle-burn-audit `
  --sequence-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_all_v4_media_fallback\bilibili_event_sequence.csv `
  --out-dir A:\magireco_bili_fulltest_20260603\subtitle_burn_audit_v1 `
  --max-samples 3 `
  --difference-threshold 0.5 `
  --workers 4
```

This samples actual SRT cue midpoints and compares the no-subtitle and
burned-subtitle frames. The full 284-row audit passed with no probe errors;
the lowest per-event maximum luma difference was 0.846662.

Use `avg_frame_rate` for the effective playback rate. A concatenated file can
report `r_frame_rate=60/1` when a few boundary packets last 50 ms even though
its frame count and duration are approximately 30 fps. Duration tolerance is
the configured base plus one frame per normalized event, which bounds the
timestamp rounding accumulated across the part.

Average-frame-rate tolerance uses the configured base plus half a frame per
normalized event divided by the part duration. Full frame counts measured on
the initially flagged outputs differed from `planned duration * 30` by only
0.045 to 0.476 frame per event. This distinguishes event-boundary timestamp
quantization from a genuinely wrong playback rate.

The final audio chain applies a hard limiter after loudness normalization. Its
limit includes 1 dB of AAC encoding headroom below the requested true-peak
target; decoded output is still checked independently.

## Quality gates

Do not publish a part unless all conditions pass:

- source path exists for every event
- video and audio streams both decode
- output is actually audible
- output resolution is 1920x1080
- output average frame rate is within 0.05 fps of 30 fps
- output audio is 48 kHz stereo
- decoded peak does not exceed -0.5 dBFS
- subtitle and no-subtitle editions differ where dialogue exists
- separator frames are black
- part title label has been reviewed manually

## Human review files

Review these before upload:

```text
bilibili_parts.csv
bilibili_event_sequence.csv
bilibili_root_label_candidates.csv
```

The label candidate file is evidence for naming, not a final official title
table.

Generate the editable upload review table with:

```powershell
python magireco_asset_pipeline.py bilibili-upload-review `
  --parts-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v4_media_fallback\bilibili_parts.csv `
  --root-labels-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v4_media_fallback\bilibili_root_label_candidates.csv `
  --out-dir A:\magireco_bili_fulltest_20260603\bilibili_upload_review_v1
```

Fill `review_status`, `approved_title`, and `review_notes` before upload.

The review table preserves raw EventCn labels for evidence and also includes
NFKC-normalized display labels for readable Japanese titles. Descriptions list
audible, silent-video, and subtitle event counts separately.

The old smali/debug `ac_code_labels.csv` table is intentionally excluded from
title generation. It contains labels from unrelated residual game content and
is not reliable evidence for this title.
