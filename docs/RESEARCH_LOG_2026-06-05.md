# Research Log: 2026-06-05

## Corrected failures

- Deprecated motion-based `low_motion`, `short_static`, and `static_like`
  classifications. They produced false positives on blinking characters,
  localized animation, and ordinary long videos.
- Corrected Bilibili source paths that accidentally contained
  `events\events`.
- Excluded non-`cap*` Z2D visual text from dialogue/subtitle counts.
  `ac4908_014` changed from a false audible/subtitle classification to
  `silent_video`.
- Replaced audio-stream-presence checks with decoded signal measurement.
- Added AAC headroom after proving that AAC encoding could overshoot a limited
  PCM source by approximately 2.9 dB.

## Verified official reconstruction

- Built exact GDB -> Z2D -> DGM -> native CRI mapping.
- Recovered Z2D canvas dimensions and DGM placement.
- Implemented simultaneous DGM layer composition.
- Implemented official intro plus `_LP` loop repetition.
- Implemented `hold-base` for short visual layers with longer official audio.
- Joined EventCn sound components and exact Z2D dialogue OGGs.
- Generated no-subtitle MP4, burned-subtitle MP4, and SRT outputs.

## Full audible result

- Authoritative audible event/canvas rows: 5,485
- Burned-subtitle event/canvas outputs: 284
- Missing sources: 0
- Invalid streams: 0
- Silent outputs: 0
- Duration mismatches above 0.12 seconds: 0
- Highest decoded peak after repair: -0.9 dBFS

The repaired tree is:

```text
D:\MagiReco_Reverse\
  magireco_bili_event_renders_limited_20260606
```

The original 2026-06-05 render tree was retained and not overwritten.

## Bilibili merge result

The production grouping uses official event roots and canvas groups, not old
candidate-count suffixes.

- Audible events: 5,485
- Planned audible parts: 294
- Target part length: 20 minutes
- Maximum events per part: 100
- Separator: 0.25 seconds black/silence
- Output canvas: 1920x1080
- Editions: no subtitles and burned subtitles

P002 (`ac0006`, 12 events) passed video, audio, subtitle, black separator, and
true-peak checks.

## Upload metadata

EventCn provides a current-title sound label candidate for 177 of 187 audible
event roots. Ten roots remain code-only.

The old smali/debug `ac_code_labels.csv` table was rejected as an upload naming
source because it contains labels from unrelated residual game content.

`bilibili-upload-review` now generates an editable 294-row review table with
candidate title, description, event range, subtitle count, review flags, and
blank approval fields.

## Installed-data completeness

The emulator pull was compared with the local source archives:

- `main.9.com.universal777.magireco.obb`: exact SHA-256 match
- `patch.9.com.universal777.magireco.obb`: exact SHA-256 match
- `split_InstallTimePack.apk`: exact SHA-256 match

The installed pull adds the runtime OnDemand SMZ pack:

- SMZ chunks: 9,752
- Native SMZ names: 9,752
- Structured request names missing from the installed runtime table: 6

Therefore the OBB and install-time inputs used by the current pipeline are exact
copies of the installed game files, not incomplete reconstructions produced by
the downloader script. The installed SMZ pack remains useful as independent
sound-request evidence.

## Work still running at log creation

The final tree is being completed with 2,997 silent visual event/canvas rows.
These rows retain a silent AAC stream so all later merge inputs have a uniform
video-plus-audio contract.

## Bilibili output audit added

Added `bilibili-part-output-audit` to verify completed upload parts independently
from the builder.

It checks:

- H.264 video and AAC audio streams
- 1920x1080 upload canvas
- average playback rate near 30 fps
- 48 kHz stereo audio
- decoded audibility against the plan
- decoded peak safety
- planned duration within timestamp-rounding bounds
- hard-link reuse for subtitle aliases with no subtitle events

An incremental audit during the full build found:

- 48 completed logical outputs
- 48 passed all media checks
- 24 completed edition pairs
- 24 correct storage relations
- 0 failures among existing outputs

Two files initially appeared to be 60 fps because their container
`r_frame_rate` was inferred from a few 50 ms packets at concat boundaries.
Their `avg_frame_rate`, frame count, and duration prove that playback is
approximately 30 fps. The audit now uses `avg_frame_rate`.

Fixed duration tolerance was also rejected. Concatenating many independently
normalized events accumulates sub-frame timestamp rounding, so the accepted
bound is now a small base tolerance plus one frame per event.

## Complete-plan reuse

The final plan contains:

- 8,482 event/canvas rows
- 413 upload parts
- 5,485 audible events
- 2,997 silent visual events
- 284 subtitle events
- 65 parts with independent subtitle media
- 348 parts eligible for no-dialogue hard-link aliases

Exact comparison with the 294-part audible plan found 202 complete parts with
identical event sequences. These parts cover 3,186 events and can be reused
without re-encoding; 211 complete-plan parts still require encoding.

The builder now accepts a reusable sequence, part table, and output directory.
It matches event name, canvas, duration, separator, and both edition input
paths. A live P002 -> complete-plan P006 test produced two
`linked_reused_part` results, and both target file IDs matched the source file
IDs.

## Complete event tree

The first complete pass exposed four failed `ac8050` canvases. Each event had
94 simultaneous layer tracks; its generated FFmpeg command was approximately
33.9 KB and exceeded the Windows process command-line limit. The assets and all
94 rendered layer tracks were valid.

The compositor now writes the filter graph to
`composite_filter_complex.txt` and passes it with
`-filter_complex_script`. This reduced the process command line from about
33.9 KB to about 16.5 KB without changing the filter graph.

The repair pass completed all four events. Final event-tree counts:

- production rows: 8,482
- no-subtitle MP4 files: 8,482
- burned-subtitle MP4 files: 284
- SRT files: 284
- missing planned inputs: 0
- failed batch rows: 0
- generated layer residues: 0

## Zero-duration correction and final audit

The first 8,482-row output audit found one invalid file:
`ac7114_100` at 1280x720. The old plan assigned it zero seconds because its Z2D
relation omitted outer `end_frame` and `relation_end_ms` values.

The exact DGM/CRI mapping still contained:

- interval confidence: `exact_duration_unique`
- official media duration: 1.000 seconds
- valid official H.264 source: 512x288, 30 fps

Duration calculation now falls back to `media_duration_sec` only when every
timed layer in the event resolves to zero. This conservative rule changed the
visual-duration fields of four events but changed final output duration only
for `ac7114_100`. The event was rebuilt as a valid 1.000-second 1280x720
H.264/AAC file.

The v5 production plan retains:

- 8,482 event/canvas rows
- 7,753 unique events
- 5,201 audible events without subtitles
- 284 audible events with subtitles
- 2,997 silent visual events

Final full-tree audit:

- rows: 8,482
- missing sources: 0
- invalid video/audio streams: 0
- decoded audio expectation mismatches: 0
- duration mismatches above 0.120 seconds: 0
- decoded audible outputs: 5,485
- decoded silent outputs: 2,997
- maximum decoded peak: -0.9 dBFS
- minimum decoded peak: -91.0 dBFS

Authoritative current manifests:

```text
A:\magireco_bili_fulltest_20260603\
  event_production_plan_v5_media_fallback
  bilibili_part_plan_all_v4_media_fallback
  bilibili_part_plan_audible_v4_media_fallback
  event_output_audit_all_v5_media_fallback
```

## Burned-subtitle visual audit

Added `subtitle-burn-audit` to verify subtitle pixels against the corresponding
no-subtitle event source. It parses each SRT, selects up to three evenly
distributed cue midpoints, decodes both editions at those times, and measures
their luma difference with FFmpeg.

Full result:

- event/canvas rows: 284
- visual-change failures: 0
- probe errors: 0
- minimum per-event maximum difference: 0.846662
- maximum per-event maximum difference: 7.465500
- acceptance threshold: 0.500000

Output:

```text
A:\magireco_bili_fulltest_20260603\
  subtitle_burn_audit_v1\
    subtitle_burn_audit.csv
    subtitle_burn_audit_summary.md
```

## Upload-title review normalization

The upload review manifest now keeps both the original EventCn label and an
NFKC-normalized display form. This converts half-width Japanese characters for
readability without deleting technical prefixes, variant numbers, or the raw
evidence. Each description now reports audible, silent-video, and subtitle
event counts separately.
