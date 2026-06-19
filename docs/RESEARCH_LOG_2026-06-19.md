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

## Additional completed families

After the initial v18 release, official runtime captures closed three near-complete families:

- `ac5301_018`: the main and LP clips follow the same 3333+2733 ms sequence as its
  verified sibling. The complete `ac5301` family passes 21/21 event QA; its 512x288 long
  edition is 149024 ms with 21 subtitle cues.
- `ac6003_005`: runtime evidence replaced an overlong static audio timeline. The clean
  edition uses only `c01+c02`; the separate slot title layers are excluded. The complete
  `ac6003` family passes 7/7 QA; its 416x232 long edition is 74621 ms with 9 cues.
- `ac6005_013`: the clean timed composition keeps the four battle backgrounds and the
  opaque Iroha character close-up. The 192x320 battle-title layers and decorative
  `CU_add` border are excluded. The complete `ac6005` family passes 8/8 QA; its 416x232
  long edition is 67188 ms with 16 cues.

The renderer now supports an explicitly declared `opaque` screen-overlay mode for native
full-frame cut-ins. This is a replacement operation, not a screen blend, and remains behind
the composition-plan blend-mode whitelist.

`ac6007_004` required a different clean policy. Runtime evidence confirmed two native
416x232 defeat clips, two vocalizations, an 8-second official sound, and a 208x120 generic
slot dark-transition clip. The transition is not upscaled. The clean edition shows the
3-second native animation followed by native-size black frames while preserving the complete
official audio. Resource-context prefixes were removed from the two vocalization subtitles.
The complete `ac6007` family passes 5/5 QA; its long edition is 39387 ms with 7 cues.
