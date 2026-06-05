# Bilibili Production Workflow

## Production inputs

Use the verified production plan:

```text
A:\magireco_bili_fulltest_20260603\
  event_production_plan_v4_verified\
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
  bilibili_part_plan_audible_v3_limited
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
  --sequence-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v3_limited\bilibili_event_sequence.csv `
  --parts-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v3_limited\bilibili_parts.csv `
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

Verified P002 result:

- Events: 12
- Duration: 158.617 seconds
- Video: H.264, 1920x1080, 30 fps
- Audio: AAC, 48 kHz, stereo
- Mean decoded level: -18.6 dBFS
- Maximum decoded level: -3.0 dBFS
- Subtitle and no-subtitle frames differ at dialogue time
- Event separator sample is pure black

## Quality gates

Do not publish a part unless all conditions pass:

- source path exists for every event
- video and audio streams both decode
- output is actually audible
- output resolution is 1920x1080
- output frame rate is 30 fps
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
  --parts-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v3_limited\bilibili_parts.csv `
  --root-labels-csv A:\magireco_bili_fulltest_20260603\bilibili_part_plan_audible_v3_limited\bilibili_root_label_candidates.csv `
  --out-dir A:\magireco_bili_fulltest_20260603\bilibili_upload_review_v1
```

Fill `review_status`, `approved_title`, and `review_notes` before upload.

The old smali/debug `ac_code_labels.csv` table is intentionally excluded from
title generation. It contains labels from unrelated residual game content and
is not reliable evidence for this title.
