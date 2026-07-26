# 2026-07-27 silent native-416 and split-material checkpoint v48

## Scope

The project-owner production freeze is lifted.  The immutable freeze handoff
root remains unchanged:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_human_review_upload_freeze_20260727
```

This checkpoint adds one narrow clean-story lane for events whose lack of
dialogue, SE and subtitles is positively proven by current hash-bound
catalogs.  It does **not** treat missing audio rows as evidence by default, and
it does not relax the child-local Z2D timing gate.

## Eight exact silent native-416 products

The manifest root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_manifests_v47_silent_native416_exact_20260727
```

It contains eight native 416x232, 30 fps, single-event DirInfo products:

```text
ac4002_001  回廊追逐动画
ac4003_001  游乐园追逐动画
ac4004_001  火焰中的魔法少女动画
ac7002_001  夜空魔女登场短片
ac7002_002  魔法少女迎战魔女短片
ac7002_003  白色斗篷魔法少女飞行战斗
ac7002_004  魔女追逐战动画
ac7002_005  红夜魔女决战动画
```

The builder accepts each event only when all of the following are true:

- one exact single-event DirInfo row with selector 0;
- one native 416x232 H.264, 30 fps video-only source;
- exact-duration-unique visual interval and source SHA-256;
- exactly zero matching rows in the direct-parent audio catalog;
- exactly zero matching rows in the child-Z2D audio catalog;
- exactly zero matching rows in the subtitle timeline catalog;
- all catalogs, ledgers and source clips rehash to the plan-bound values.

The resulting summary reports 8 events, 5,720 frames and 190.667 seconds.
Every manifest records `audio_absence_evidence.status=hash_bound_zero_matches`.
Important hashes:

```text
event_production_summary.json
CD23744134015180CBC6032DC6BD52A08FE6C7D5EAE086AC3D19DEFF9C09017F

event_production_catalog.csv
46BFDD238C7C8D149E0EE8EB41492532FED0F08EFFA97CACAC353936BA0CDD0F

series_proposals\SERIES_PROPOSAL_INDEX.csv
887D115E8B7A8B9CE5F3D5125AB1F48D7001860B67B4993BDE4F3D33D737685A
```

The edition root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v47_silent_native416_review_20260727
```

All 8 products and 24 none/JA/ZH target entries passed automated media QA:
416x232, 30 fps, H.264, AAC 48 kHz stereo, no upscale.  The verified-silent
AAC peak is `-91.0 dBFS`.  There are no SRT files and no burned-in subtitles.
Within each product, none/JA/ZH are legal cross-target hardlink aliases of the
same exact hash because there is no dialogue or subtitle content.  This keeps a
correct upload entry for every target BV without storing three physical media
copies.  `BATCH_SUMMARY.json` SHA-256:

```text
79E12C42897F8B9363EDAA74AAFD3A71DE5BB6373C228F9903522DBE0324D2C9
```

Automatic QA does not imply human approval or publication readiness.

## Split native-dimension material collections

The visual-only material root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v48_ac0504_ac4921_split_components_review_20260727
```

It contains:

```text
ac0504_win_raw_components_v1
  11 unique native 416x232 clips, 24.896 s
  manifest 0A80D6A1DAB8B9710DDECA070233C55EAF29F760007E2F5B0480480CB292BABD
  output   3E528BDA567644148B7D7CBDC97E6F8F62F0C7B1FBAF1547FA0E8337996559C4

ac4921_character_action_components_v1
  6 unique native 416x232 clips, 16.133 s
  manifest FE99294863C2455CC58D61DA51742467398D1311206886E5C92BA11B3C248A68
  output   B9B53AE9ACF967B7F02B22EDA2E47FB8E68C4A1AB44E7B29994B70B89C333173

ac4921_result_frame_components_v1
  10 unique native 416x120 clips, 10.000 s
  manifest 2978969D3C80E2D05BDC9C221ABE385467A9C3767B23F6B3EFAD080E600A2F2C
  output   322968D878FE085DC025192E0B7E250A98701CE06A960D5D5D7D06BC324669C9
```

The two dimensions are deliberately separate: no scaling and no
cross-dimension concatenation.

ac0504 remains a raw-component collection because its four event variant
intervals are still ambiguous.  It is not presented as a reconstructed event
timeline.  The ac4921 coverage audit rehashes every source and proves all six
416x232 action clips and all ten 416x120 result frames are used across the 22
catalogued events, with no unused source:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_component_coverage_v48_ac4921_20260727\
  ac4921_split_native_components_v1.json

SHA-256
904D950B8890869B464E3A0FE4A56436D3A7F291C05E53F0C42C66C916690C2B
```

These are visual-only review products.  They claim no dialogue, SE, BGM,
subtitle or native-session semantics.

## Ledger and human-review handoff

The exhaustive ledger advanced to:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v16_20260727
```

`SUMMARY.json` SHA-256 is
`87159FF55907957CAD2D4DB87455335DD2A99F5EB93464D6FDAA4250A1864958`.
It records 185 current produced audience events, 434 material-covered events,
62 produced DirInfo routes, 330 timing blockers and 53 quarantined audience
events.  P16/ac6003, P17/ac6004 and P18/ac6005 remain hard quarantines.

The only current v48 global guide is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v48_final_20260727
```

`UPLOAD_GUIDE.json` SHA-256:

```text
DBB0F84FE029D73D4DBFFF0A9D26DF5550A162EF837FEA8321419C06CB5B73DF
```

It records 10 already-uploaded exact files, 17 exact files ready to upload,
229 files requiring human playback and 8 explicit exclusions, for 256 exact
file entries.  The new v48 items are not automatically promoted.

The bounded review roots are:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v48_silent_native416_final_20260727
    U092-U099, 8 products, 24 target files, 8 unique hashes, 190.667 s

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v48_material_native416x232_final_20260727
    U100-U101, 2 products, 6 target files, 2 unique hashes, 41.029 s

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v48_material_native416x120_final_20260727
    U102, 1 product, 3 target files, 1 unique hash, 10.000 s
```

Every review package has zero files in `00_UPLOAD_NOW` and zero quarantined
media.  Intermediate v48 guide/review roots are marked superseded and must not
be used; no media was deleted.

The final repository state passed `python -m unittest`: 445 tests passed and
4 were skipped.  Python compile checks, repository JSON parsing and
`git diff --check` also passed.  Independent package validation found 24/8,
6/2 and 3/1 target-file/unique-file-ID counts respectively, confirming the
intended hardlink alias contract without unintended physical duplicates.

## Runtime prerequisite

The durable runtime-recovery record is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260725\
  RUNTIME_RECOVERY_FRIDA_17_16_4.md
```

The previous Frida 17.5.2 server injected agents into Android 15 zygotes and
caused inherited child-process faults at address `0x58`.  The validated,
zygote-clean toolchain is host Frida 17.16.4 / frida-tools 14.10.4, device
server 17.16.4 and ARM64 Gadget 17.16.4.  Runtime work must use ADB `pidof`,
known numeric-PID attach and a single 27043 session only; process enumeration,
spawn, zygote attach and broad observers remain prohibited.  The repository
toolchain lock now records the recovered versions.  No Frida binary is stored
in Git.

## Boundary for the next checkpoint

No formal with-BGM candidate is ready.  Continue no-BGM inventory expansion
from ledger v16.  Switch to formal with-BGM production only after all discovered
no-BGM items are either produced or assigned an exact blocker.  BGM work must
bind track identity, entry phase, volume, fade/duck/stop behavior, source hash
and event/route timing; guessed tracks must never be marked READY.
