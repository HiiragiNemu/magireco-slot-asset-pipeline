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
