# Corrected clean-story production update — 2026-06-25

## ac7206 complete family

Official runtime captures in
`A:\magireco_corrected_research_20260619_round2\resolved` resolved the remaining
`ac7206_003`, `_004`, `_005`, `_006`, `_008`, `_009`, `_010`, `_011`, `_012`, and `_014`
gaps. Each gap is a native 416x232, 30 fps one-second `ac7206_arina_kaiga_3on_kok_*`
animation with official runtime sounds that continue beyond the video. Source contact-sheet
inspection in `A:\magireco_corrected_research_20260612\frame_audits_v18_ac7206` confirms
the S1/S2/M/L/hat clips are normal event animation frames rather than slot UI, so the clean
audience edition holds the stable tail frame through the verified runtime audio/subtitle end.

The `_005` runtime capture also starts unrelated `ac9901_op`; that layer is excluded from
the clean audience plan. `_008` and `_014` include numeric runtime sound code `551`; it is
resolved through the sound request mapping to `snd_00551_bank50_ogg_00172.ogg`, not inferred
from an event suffix or CRI index.

Request `5324` only exposes the official runtime prefix `アリナが代わりにマ`. The curated
subtitle override completes it as `アリナが代わりにマスタリングしてあげる` using the official
prefix plus large-v3-turbo prefix-parameter ASR; 0.75x and 0.5x atempo checks preserve the
official prefix and the same マスタリング/マストリング phonetic suffix. The override is marked
`official_voice_asr_verified` rather than complete-official-label evidence.

After adding the ten composition plans and the 5324 override, production manifests v18 still
cover 926 events and now contain 550 render-ready events, 644 resolved video compositions,
and 1611 retained subtitles. The complete `ac7206` family (`_002` through `_014`, 13 events)
passes 13/13 single-event QA in
`A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7206_full`;
all subtitle/no-subtitle pairs have identical audio essence and non-silent 48 kHz stereo
audio.

The Bilibili-oriented same-scene long edition is stored at
`D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac7206_20260625`. It preserves
the single-event files separately on A:, uses direct stream copy for the series, and produces
both subtitled and non-subtitled outputs at 416x232, 30/1 fps, 48 kHz stereo. The series
contains 13 events, 13 subtitle cues, and a 63184 ms manifest duration; ffprobe reports a
63.16-second video stream and 63.18-second audio stream. The two long-edition audio streams
share MD5 `a39cc612c6b1ffe11a455e01216e98c3`.

## ac1102/ac1103/ac1104 and ac0906 collection audit

The current authoritative clean-story review output for the cooking/restaurant families is
`A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac1102_04_full`
plus the same-scene long-edition root
`D:\MagiReco_Reverse\magireco_verified_series_v18_clean_story_ac1102_04_20260619`.
Legacy 1024x576 render directories under older Bilibili batch roots are not authoritative
for the corrected native pipeline.

`full_qa_audit.csv` in the v18 validation root contains 37 rows and all pass: `ac1102`
11/11, `ac1103` 13/13, and `ac1104` 13/13. The production manifest prefix sets exactly
match those rows: `ac1102` has 11 render-ready events (`_001`, `_002`, `_003`, `_004`,
`_005`, `_006`, `_008`, `_009`, `_010`, `_011`, `_012`), `ac1103` has 13 render-ready
events (`_001` through `_013`), and `ac1104` has 13 render-ready events (`_001`, `_003`,
`_004`, `_005`, `_006`, `_007`, `_008`, `_009`, `_010`, `_011`, `_012`, `_014`, `_015`).
No additional v18 production manifests for these prefixes are omitted from the long-edition
review sets.

The three long-edition `series_index.csv` files provide continuous cumulative timelines and
SHA-256 for every single-event subtitled file, no-subtitle file, subtitle file, and render
manifest. Recomputing the hashes found no mismatch. The resulting direct-stream-copy
long editions are all native 416x232 at 30/1 fps with 48 kHz stereo audio. The paired
subtitle/no-subtitle long editions have identical audio packet MD5 values:
`ac1102` = `f626fe7da7e563a02d4a5fc4f9a56cf4`, `ac1103` =
`4a492ae23a2a3774dcb1de2c91b7353b`, and `ac1104` =
`06837e74e65dff5f7f62248b28926806`.

The current authoritative `ac0906` material collection is
`D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260619\ac0906`, not the
older v17 output. Its `material_collection_manifest.json` is schema
`magireco-material-component-collection-v2` and status `passed`. It contains six
black-matte small-Kyubey components (`ac0906_001` through `_006`) with source SHA-256,
video-packet SHA-256, official audio evidence, production manifest paths, and per-event
audible segment hashes. The material timeline is continuous for 15333 ms; the official-audio
edition is 18908 ms. Recomputing the six source hashes, six audible segment hashes, final
output hashes, and timeline durations found no mismatch.

All six `ac0906` production manifests remain excluded from clean story output with the reason
`Reviewed black-matte Kyubey character overlay; requires official runtime background
composition.` They are therefore correctly archived as material/effect components rather than
mixed into the audience story/review families. A visual contact sheet at
`A:\magireco_corrected_research_20260612\frame_audits_v18_ac0906_material` confirms the
collection is the expected black-background small-Kyubey material, not story animation.

## ac5209 single clean result animation

The next non-excluded one-event failure was `ac5209_001`. Source-frame inspection of
`ac5209_end_bg01` confirms it is a native 512x288 Mami result/character animation rather
than a chance-button or slot UI component. The clean plan therefore keeps the single
`ac5209_end_bg01` clip and holds its stable tail through the 4192 ms official result-screen
sound.

The event also exposed a subtitle coverage bug: the official voice label
`25177_mamik_UT_汎用告知_導きのままに` was not recognized because `mamik` was missing from
the speaker-token set. Adding `mamik` recovers the subtitle from the official code name;
no ASR is used for this line. Existing truncated `mamik` labels that end in `-` remain
filtered by the established incomplete-label rule.

After rebuilding production manifests v18, the catalog has 551 render-ready events and
1612 subtitles. `ac5209_001` passes 1/1 QA in
`A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac5209_full`.
Both subtitle and no-subtitle editions are 512x288 at 30/1 fps with 48 kHz stereo audio,
and their audio streams share MD5 `07d40198a36ef7e730bbf75f2e6e7e1b`. The single cue is
`導きのままに` from 0 to 1496 ms. A same-scene long edition is not generated because the
series builder intentionally requires at least two QA-passed events; the single-event files
are the uploadable outputs for this one-event family.
