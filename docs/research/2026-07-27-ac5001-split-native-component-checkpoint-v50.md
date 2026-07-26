# 2026-07-27 ac5001 split-native component checkpoint v50

## Scope

This checkpoint closes the exact visual-component inventory for:

```text
ac5001_001 through ac5001_036
```

The 36 unique events contain 287 component occurrences and 16 unique official
sources.  Thirty-five events contain eight sources.  `ac5001_007` contains
exactly seven and deliberately omits `ac5101_1G_lev_lp`; that source was not
filled in from the other events.

All source rows are `source_exists=yes`,
`interval_confidence=exact_duration_unique`, 30 fps and have no embedded audio
stream.  Their event intervals are complete.  One source is native 512x416 and
the other fifteen are native 416x232, so this checkpoint preserves them as two
separate component catalogs.  It does not concatenate or resize them into a
synthetic event canvas.

## Material products

The production root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v50_ac5001_split_components_review_20260727
```

Products:

```text
ac5001_flying_combination_components_416_v1
  15 unique native 416x232 clips, 55.663 s
  manifest 970EEE9147F0178F32BFE5992FDE92FB91269FDB33060C491D59452EB5F4B54C
  output   5B5A6BEE49C7E5CF4237A297AB2F474C7415FB7ABE040F949D6208CD0F1FB201

ac5001_attack_title_component_512x416_v1
  1 unique native 512x416 clip, 2.500 s
  manifest 18E87694038D1BB8F982B9560E1859EDC0795DA70E414F75D8BB546EBCCADAF6
  output   5255F6396023AB80424EFBDC169B437CC7B4A1F755BAF9B0A3E56AF255B06F7B
```

The official source typo `ac5101_attack_tittle` remains intact in provenance.
The 512x416 product uses the explicit single-source component contract: it
stores the source once and does not fabricate a duplicate.

Both manifests passed the current-material no-overlap gate against ledger v17.
The gate rehashed the current material index and every current manifest and
found zero overlapping source SHA-256 values.  Both outputs are H.264 at 30 fps
with no audio or subtitle and remain `review_only`.

## Component coverage

The fail-closed coverage result is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_component_coverage_v50_ac5001_20260727\
  ac5001_split_native_components_v1.json

SHA-256
AFE555BE21C5F3BA92C42A74B0D1213F627CD4B291A7343BCE86D2269BE58769
```

It passed for 36/36 events, 287/287 occurrences, two native-size catalogs and
16/16 unique sources, with zero unused sources.  Per-source occurrence counts
also preserve the exceptional event:

```text
flying_all_bg       36
1G_lev_lp            35
2G_BG                36
2G_BG_LP             36
attack_tittle        36
flower01/flower02    18 each
person01/02/03       12 each
zokusei01 through 06  6 each
```

This claim is visual component coverage only.  It does not claim dialogue, SE,
BGM, subtitle or game-session semantics.

## Ledger and upload guide

The exhaustive ledger advanced to:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v18_20260727
```

`SUMMARY.json` SHA-256:

```text
90ECA23445025E17D0B3D746A7E6FD73DAE0B711A802DA311EB975F93DAF20D2
```

It records 185 current produced audience events, 491 material-covered events,
62 produced DirInfo routes, 330 timing blockers and 53 quarantined audience
events.  P16/ac6003, P17/ac6004 and P18/ac6005 remain hard quarantines.

The current global upload guide is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v50_20260727
```

`UPLOAD_GUIDE.json` SHA-256:

```text
B6ABB2EA5954904E6E58ADF218DA8CDAA771B298FC3794FA26956585CCEAD056
```

It contains 10 already-uploaded exact files, 17 exact files ready to upload,
234 files requiring human playback and 8 explicit exclusions, for 261 exact
file entries.

## Human-review upload handoff

The bounded review roots are:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v50_material_native416x232_20260727
    U106_飞行组合背景与属性组件_ac5001__none.mp4
    U106_飞行组合背景与属性组件_ac5001__ja.mp4
    U106_飞行组合背景与属性组件_ac5001__zh.mp4

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v50_material_native512x416_20260727
    U107_飞行演出攻击标题组件_ac5001__none.mp4
    U107_飞行演出攻击标题组件_ac5001__ja.mp4
    U107_飞行演出攻击标题组件_ac5001__zh.mp4
```

Each product has three target aliases, one canonical SHA-256 and one NTFS file
ID.  This is an intentional hardlink alias across target BVs because the
product has no audio or subtitle.  All six entries are
`HOLD_FOR_HUMAN_PLAYBACK`; both `00_UPLOAD_NOW` directories and both quarantine
media directories contain zero MP4 files.  The copied global guide in each
package rehashes to the v50 guide hash above.  No P16/P17/P18 or superseded
source leaked into either package.

The exact final repository state passed `python -m unittest`: 450 tests passed
and 4 were skipped.  Python compilation, repository JSON parsing and
`git diff --check` also passed.

Suggested destinations:

```text
U106 -> MagiaReco Slot native 416x232 gameplay/material collection BV
U107 -> new native 512x416 gameplay/material collection BV
```

## Next boundary

The strict v48 silent-story gate was rerun conceptually against the current
v17 inventory.  Beyond the already-produced v48 set, no new event simultaneously
has a single selector-0 DirInfo row, native 416x232 exact full-frame clips and
zero matches in the direct-parent audio, child-audio and subtitle catalogs.
That lane therefore cannot be widened by assuming silence.

No formal with-BGM candidate is ready.  Continue the no-BGM inventory from
ledger v18; switch to formal with-BGM production only after every discovered
no-BGM item is produced or precisely blocked.
