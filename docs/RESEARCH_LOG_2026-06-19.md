# Corrected clean-story production update — 2026-06-19

## Audience output policy

The Bilibili-facing animation editions contain the native story image only. Slot gold-frame,
particle, reel, and UI layers are excluded from those editions and retained as separately
auditable material collections. No source is upscaled.

## Official runtime captures

Official runtime captures resolved `ac7112_001`, `ac7113_001`, and `ac7117_001`.
The resolver now treats a Japanese-labelled base event sound as dialogue only when its code
contains a verified speaker token or its resource id is in the voice range. This prevents
labels such as `突入` and `パート01` from becoming false subtitles.

Clean composition plans use:

- `ac7112_001`: `ac7112_AT_SP_story1_01`, native 512x288, 190 ms final-frame hold;
- `ac7113_001`: native 512x416 `_00` opening, then native 512x288 `_01` padded only at the
  bottom to the 512x416 viewport, with no scaling or crop;
- `ac7117_001`: `ac7117_AT_SP_story6_01`, native 512x288, two-frame final hold.

All three plans deliberately omit the four gold-frame/particle DGM layers.

## Render and QA results

The complete `ac7112`, `ac7113`, and `ac7117` families produced 35 subtitle/no-subtitle
event pairs. QA passed 35/35; every pair has identical audio essence and non-silent 48 kHz
stereo audio.

The long stream-copy editions are:

- `ac7112`: 14 events, 197138 ms, 44 subtitle cues, 512x288;
- `ac7113`: 9 uniform events, 131527 ms, 32 cues, 512x288;
- `ac7117`: 11 events, 145905 ms, 32 cues, 512x288.

`ac7113_001` remains a separate 512x416 native event. The series manifest records it as
deliberately preserved separately because its native stream signature differs. It is not
upscaled, cropped, or silently omitted.

## Reproducibility boundary

`reproducibility/` now records the expected local input layout, 39 verified size/SHA-256
fingerprints, the tested toolchain, and scripts for input verification and derived-evidence
packaging.

The public evidence bundle contains only CSV/JSON/Markdown/TXT/SRT analysis artifacts.
It excludes APK, OBB, native libraries, raw binary tables, media, screenshots, and decoded
game data. Absolute local paths are replaced by portable placeholders before packaging.
