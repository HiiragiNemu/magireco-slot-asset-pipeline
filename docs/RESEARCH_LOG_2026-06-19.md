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

`ac6004_011` follows the same verified policy: three native 416x232 clips, then black
frames instead of upscaling the 208x120 slot transition, with its complete official sound.
The four separate battle-title layers are excluded. The complete `ac6004` family passes
5/5 QA; its long edition is 46888 ms with 7 cues.

Further runtime captures completed two clean families:

- `ac5303_004` keeps only the native 512x288 Arina punch animation. Nine ac8050/ac8052
  slot count and impact layers are excluded; native-size black frames preserve the complete
  6.149-second vocalization. The `ac5303` family passes 4/4 QA and its long edition is
  30454 ms with 3 cues.
- `ac7210_001` uses the native MR then LP_MR sequence and excludes four separate capture-title
  layers. The `ac7210` family passes 3/3 QA and its long edition is 29988 ms with 4 cues.

The five `ac0931` rumor-introduction videos were reclassified as
`hybrid_slot_story_material_not_clean_animation`: their NEXT/stage-title graphics are burned
into the sole video stream and cannot be removed without destructive editing. A separate
416x232 material collection passes QA with five clips, a 105000 ms direct-video edition and
a 114235 ms official-audio edition. `ac0931_005` contains a -91 dB ALAC control track; the
material builder now permits dropping an embedded track only after proving it is digital
silence. The five CV narration transcripts remain explicitly `required_not_verified`.

`ac8004_005` and `ac8004_006` were runtime-verified as shutter-close/open slot transition
components with external official sound, not audience animation. Their material collection
passes QA with three raw visual components and two audible event segments. Multi-clip material
events are now assembled to one event visual before official audio is mixed, preventing the
same sound from being duplicated for every component. The audible collection remains native
416x232 at 30/1 fps with 48 kHz stereo audio; its duration is 5381 ms and peak is -0.5 dB.

Official captures closed both remaining `ac0911` gaps. `ac0911_001` keeps the native c01/c02
story sequence and excludes the unrelated 512x416, 175.9-second `ac9901_op` slot opening that
the runtime starts separately. Its stable crowd tail is held for 891 ms. `ac0911_005` holds
its stable character close-up for 633 ms. The complete family passes 12/12 QA; its 416x232
long edition is 123655 ms with 11 cues. The evidence bundle script now accepts additional
research roots so independent runtime-capture batches are included without moving their source
files.
