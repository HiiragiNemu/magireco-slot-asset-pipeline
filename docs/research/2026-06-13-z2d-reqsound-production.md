# Z2D reqSound Production Audit - 2026-06-13

## Corrected model

Voice and subtitles are independent event outputs.

- Every exact `CZ2DReader::ReadCB` `reqSound` callback is an audio event,
  whether or not its Z2D object also has graphical display text.
- A subtitle row is created only when the graphical text timeline contains
  real display text.
- No-subtitle events still receive all official OGG tracks.
- Subtitle and no-subtitle editions use the same mixed audio timeline.
- Validation output preserves native dimensions and frame rate. No 1920x1080
  upload canvas or other upscaling is used.
- Auxiliary machine UI, reel overlays, phone frames, and isolated icon assets
  are excluded from the raw animation render.

The full static scan currently resolves:

| Item | Count |
| --- | ---: |
| Z2D resources parsed | 12,083 |
| Exact `reqSound` callbacks linked to official OGG | 4,454 |
| Exact event sound timeline rows | 7,056 |
| Actual display-text rows | 3,697 |
| Native full-frame events with exact sound timelines | 922 |
| Events with more Z2D sounds than subtitles | 616 |
| Events with Z2D sounds and zero subtitles | 385 |

This invalidates the earlier rule that selected voice only through subtitle
text.

## Runtime proof

### `ac1101_001`

The official scheduler and independent runtime probe observed:

- base sound `4020_CZ共通_タイトル白` at event start;
- `18168_sana_さなねこ鍋_さなの` at frame 1;
- `28020_CZタイトル_mix_ねこ鍋チャレンジ` at frame 30;
- `18171_sana_さなねこ鍋_今日こそ成功させます` at frame 77;
- only the third callback has display text:
  `今日こそ成功させます！`.

The event therefore has four audio tracks but one subtitle cue.

Its video is not a concat list. Runtime capture shows:

- `ac1101_lev_c001_S` is the initial background;
- `ac1101_lev_c002` replaces it at 1,100 ms;
- `ac1101_lev_c002_LP` loops from 5,100 ms;
- `ac1101_lev_title_wht` is a black-matte screen-blend overlay.

### `ac1102_005`

This event has no display subtitle. Runtime execution still played:

- `4204_牛抑え込む_005`;
- `17734_fer_酪農体験_ふんっ`;
- `17735_fer_酪農体験_ぐおーっ`.

The runtime Z2D text layer was blank. The latter two request IDs and their
timings match the full static `reqSound` timeline. This is direct proof that an
empty subtitle timeline must not suppress character voice.

Capture evidence:

```text
A:\magireco_corrected_research_20260612\runtime_validation_20260613\ac1102_005
```

### `ac0912_104`

Runtime screenshots and a 14-second MuMu screen recording verify the layered
family:

- the chance animation is the background and background loop;
- the black-matte QB animation is a screen-blend overlay and overlay loop;
- the flash clip is a short screen-blend overlay;
- reel, prompt, phone, and cabinet graphics belong to the runtime shell and are
  intentionally absent from the raw 416x232 animation.

The continuous recording aligned to the generated event at approximately
2.933 seconds after recording start. The flash, background, QB overlay, and
loop order agree after alignment.

Evidence:

```text
A:\magireco_corrected_research_20260612\runtime_validation_20260613\ac0912_104_screens
A:\magireco_corrected_research_20260612\runtime_validation_20260613\ac0912_104_screenrecord
A:\magireco_corrected_research_20260612\validation_outputs_v6\ac0912_104
```

## Production gates

`production_manifests_v5` separates three independent states:

- `audio_timeline_ready`: all official base and Z2D OGG files exist;
- `composition_resolved`: the video timeline is linear or has an explicit
  verified composition plan;
- `render_ready`: all media and composition gates pass.

Current counts:

| State | Count |
| --- | ---: |
| Audio timeline ready | 922 |
| Composition resolved | 619 |
| Render ready | 552 |
| Blocked | 370 |
| Linear and render ready | 494 |
| Explicit layered plans and render ready | 58 |

The 58 explicit layered plans cover the verified `ac0912` and
`ac1101`-`ac1104` families. The remaining layered events are not rendered by
the batch tool.

Blocked reasons include unresolved composition, mixed dimensions, unsupported
timeline overruns, and non-zero video starts. These errors are retained in:

```text
A:\magireco_corrected_research_20260612\production_manifests_v5\event_production_catalog.csv
```

## Validation output

Native samples are separate by edition:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v5
A:\magireco_corrected_research_20260612\validation_outputs_v6
```

The v5 seven-event sample and v6 two-event layered sample both pass:

- native dimensions and frame rate;
- 48 kHz stereo audio;
- non-silent decoded audio;
- identical audio between subtitle and no-subtitle editions;
- expected duration within 50 ms;
- empty SRT accepted only when the manifest expects zero subtitles.

No-subtitle events use a hard link for the separate subtitle-edition filename,
so directory separation does not duplicate media bytes.

## Regression tests

Run:

```powershell
python -m unittest test_runtime_pipeline.py -v
```

The tests protect:

- title overlay versus background roles;
- looping black-matte QB overlay roles;
- retention of Z2D voice when an event has zero subtitles.

## Remaining work

1. Resolve the remaining 303 unplanned full-frame layered events by repeated
   family analysis and runtime capture.
2. Resolve mixed-dimension events only after recovering their official canvas
   placement; do not flatten icons or portrait components into standalone
   videos.
3. Render and QA the 552 currently accepted events in a new A-drive output
   tree before producing any Bilibili part plan.
4. Group completed events by official event roots and narrative continuity,
   not by candidate-count filename suffix.
5. Keep the old 124 GB output only as failure evidence; it is not a production
   source.

No D-drive production archive was written during this phase.

## Native audience output v11

The corrected audience tree is:

```text
A:\magireco_corrected_research_20260612\production_outputs_v11_native_audience
```

It has four deliberately separate data products:

```text
without_subtitles\  verified audible MP4, no burned subtitles
with_subtitles\     the same audio stream with Japanese subtitles burned in
subtitles\          standalone UTF-8 SRT files
manifests\          event-level source, timing, and evidence records
```

The no-subtitle edition is hard-linked from the previously QA-approved native
audible render. It is not re-encoded or duplicated. The subtitle edition only
re-encodes the video plane at the source dimensions and frame rate. FFmpeg
copies the existing AAC audio packet stream without decoding or encoding it.

Full QA results:

| Gate | Result |
| --- | ---: |
| Ready audience events | 500 |
| Native dimensions and frame rate preserved | 500 / 500 |
| Non-silent audio | 500 / 500 |
| Subtitle/no-subtitle audio hash identical | 500 / 500 |
| Frame-screen component audit accepted | 500 / 500 |
| Subtitle video renders | 499 |
| Confirmed non-voice event with empty SRT | 1 |
| QA failures | 0 |

The one empty-SRT event is `ac8004_005`. Its only exact callback is
`3125_発展ｼｬｯﾀｰ_AT_閉じる`, a mechanical shutter-close sound. Japanese ASR
returned the stock hallucination `ご視聴ありがとうございました` with
`no_speech_prob=0.90`; the resource label, event role, and acoustic score all
support excluding it from subtitles while retaining its sound.

Machine-readable evidence:

```text
A:\magireco_corrected_research_20260612\production_outputs_v11_native_audience\full_qa_audit.csv
A:\magireco_corrected_research_20260612\production_outputs_v11_native_audience\subtitle_editions_summary.json
A:\magireco_corrected_research_20260612\production_outputs_v11_native_audience\visual_audit\audience_frame_audit.csv
```

The summed logical file size is about 1.46 GB. Because all 500 no-subtitle
files are hard links, that figure is not additional physical allocation for
both editions.

## Voice subtitle recovery

Graphical text is no longer treated as a prerequisite for voice. The v11
manifest has three explicit subtitle evidence classes:

- `graphical_display_text`: text actually drawn by a Z2D caption object;
- `official_voice_label`: complete dialogue in an official sound request name;
- `official_voice_asr_verified`: truncated or unnamed official requests
  completed from multiple agreeing evidence sources.

The full 922-event manifest contains:

| Subtitle source | Rows |
| --- | ---: |
| Graphical display text | 1,571 |
| Complete official voice label | 714 |
| ASR/curated verified voice text | 131 |
| Total | 2,416 |

Truncated labels were transcribed with both `large-v3-turbo` and `large-v3`.
Curated corrections are stored in:

```text
tools\frida_runtime_probe\verified_voice_subtitle_overrides.json
```

Examples:

- `20068 ... 世界を狂わせるビ-` resolves to
  `世界を狂わせるビューティフルな力！`;
- `25474 ... こいつで黙らせて-` resolves to
  `こいつで黙らせてやる！`;
- `24253 ... 私たちにまか-` and the next exact callback
  `24584 ... ください` remain two timed cues:
  `私たちにまかせて` followed by `ください`.

Two previously unnamed 19-second CV tracks are now split into readable timed
cues. ASR timing was corrected against the original story transcripts,
including `本体のウワサ` and `悲恋の伝説`. Title mixes such as
`出前修行`, `ねこ鍋チャレンジ`, `酪農体験`, and
`バナナボート対決` are also represented because the OGG files contain spoken
title calls, not only effects.

Across the 500 ready events, every exact Z2D callback is now either:

- linked to graphical or verified voice text; or
- the explicitly documented non-voice shutter-close request.

## Reference recordings

The user-provided Bilibili recordings were downloaded to the A-drive research
tree and used as behavioral references, not as source media:

```text
A:\magireco_corrected_research_20260612\reference_bilibili
```

Family mapping:

- `BV151VJ6nEDB` (鹤乃闪送) maps to the `ac1103` / `出前修行` family;
- `BV1bfVJ6rEuJ` (我炒锅都抡冒烟了) maps to the `ac0908` / `万々歳` family.

They confirm that the running game composes full-frame backgrounds,
black-matte title/effect layers, exact character voices, and event text. The
v11 outputs reproduce those event assets at their native 416x232 or 512x288
resolution. They do not add cabinet UI or upscale to an upload canvas.

## Remaining v11 blockers

The full candidate set is 922 events. The 422 events still blocked by the
production gate are:

| Primary blocker | Events |
| --- | ---: |
| Unresolved layered composition | 177 |
| Mixed dimensions plus unresolved composition | 88 |
| Explicit component-only audience exclusion | 52 |
| Timeline overrun without a verified loop | 41 |
| Mixed dimensions plus overrun/composition | 28 |
| Non-zero video start | 24 |
| Other combined composition/overrun/start conditions | 12 |

Those events remain absent from the audience tree. They require official
canvas placement, branch selection, loop semantics, or runtime capture. The
next phase must expand composition plans by event family; it must not flatten
portrait layers, icons, or black-matte overlays as standalone videos.
