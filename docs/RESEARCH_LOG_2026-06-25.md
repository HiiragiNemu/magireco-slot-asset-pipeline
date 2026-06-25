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
