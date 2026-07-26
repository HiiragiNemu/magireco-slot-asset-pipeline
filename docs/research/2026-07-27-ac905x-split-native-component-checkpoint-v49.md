# 2026-07-27 ac905x split-native component checkpoint v49

## Scope

The production freeze remains lifted.  The completed freeze handoff root is
still immutable and was not used as a production input:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_human_review_upload_freeze_20260727
```

This checkpoint closes one exact visual-component inventory shared by 21
gameplay/effect events:

```text
ac9051_031 through ac9051_040
ac9053_011 through ac9053_020
ac9060_001
```

Every event references the same five exact visual components.  The evidence
does not provide an event-global interval for the impact layer, so the result is
three raw component catalogs rather than a reconstructed event timeline.
Nothing is scaled and clips with different native dimensions are never
concatenated.

## Three native-dimension products

The material root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v49_ac905x_uwanose_split_components_review_20260727
```

Products:

```text
ac905x_uwanose_backdrop_impact_416_v1
  2 exact clips, native 416x232, 10.000 s
  manifest 937A3042794A4AABC1F528BC6D53E3AEC9A22A349B97813CCA98F59271D1B348
  output   0BA294418C440277B076035BBD38E2A2526F00A1D99132C7F1656B2586CAFF2E

ac905x_uwanose_g_plus_counter_144_v1
  2 exact clips, native 144x160, 8.000 s
  manifest ECAD1CC5A24587F965690A3E31038F6EE9D8C915E7877DF7800439B54BFC3A57
  output   CCFE3764E19532EDB0B2658C4B0EBB52B8BAFC2D5954B3A8C2ACAB886EA90C97

ac905x_uwanose_total_counter_128_v1
  1 exact clip, native 128x64, 8.000 s
  manifest A8E0B852FF724268F95FAE6368F80F0C8EDC8BDD71903F5F90E2AC161C0FBA66
  output   1734E58877E3038C6E0AC156A4E0D342FE8983E5FFA670B0097A013483FF7C19
```

All three are H.264 at 30 fps with no audio track or subtitle.  They are
`review_only`, not human-approved.  The current-material overlap gate rehashed
the current material index and every current manifest and found zero source
SHA-256 overlap; this prevents an already-current component from being silently
repackaged.  The 128x64 catalog uses a declared single-source component mode:
the source appears once and no artificial duplicate is introduced.

## Cross-family coverage

The coverage result is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_component_coverage_v49_ac905x_20260727\
  ac9051_ac9053_ac9060_uwanose_split_native_components_v1.json

SHA-256
2F16E8433B41C4C9EAFC71750B622CF24C80FC0695953479C361F519F1D0046C
```

It passed for all 21 events, 105 component occurrences, five unique exact
sources and three native-size catalogs, with zero unused sources.  This claim
is limited to visual component coverage.  It does not establish dialogue, SE,
BGM, subtitle, layer interval or natural-session timing.

## Ledger, guide and bounded human review

The exhaustive ledger advanced to:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v17_20260727
```

`SUMMARY.json` SHA-256:

```text
099C9C0E042CEE79975D15F02D88BB829C6C78C4D8C700EECDF5427D50CCACDF
```

The ledger now records 185 current produced audience events, 455
material-covered events, 62 produced DirInfo routes, 330 timing blockers and 53
quarantined audience events.  P16/ac6003, P17/ac6004 and P18/ac6005 remain
hard quarantines.

The only current v49 global guide is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v49_final_20260727
```

`UPLOAD_GUIDE.json` SHA-256:

```text
CB14E9BF41C49C1A1B328AAFEA0FC1A94033A19822BC26F2EF43B41E7E08478C
```

It contains 10 already-uploaded exact files, 17 exact files ready to upload,
232 files requiring human playback and 8 explicit exclusions, for 259 exact
file entries.  The first v49 guide root was marked superseded after the
dimension-specific target-BV wording was tightened.

The three bounded review roots are:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v49_material_native416x232_final_20260727
    U103_传闻连打背景与冲击组件_ac9053__none.mp4
    U103_传闻连打背景与冲击组件_ac9053__ja.mp4
    U103_传闻连打背景与冲击组件_ac9053__zh.mp4

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v49_material_native144x160_final_20260727
    U104_传闻连打G与Plus计数组件_ac9053__none.mp4
    U104_传闻连打G与Plus计数组件_ac9053__ja.mp4
    U104_传闻连打G与Plus计数组件_ac9053__zh.mp4

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v49_material_native128x64_final_20260727
    U105_传闻连打总计数组件_ac9053__none.mp4
    U105_传闻连打总计数组件_ac9053__ja.mp4
    U105_传闻连打总计数组件_ac9053__zh.mp4
```

Each root contains three target aliases, one canonical SHA-256 and one NTFS
file ID.  This is an intentional cross-target hardlink alias because the
product has no audio or subtitle.  All nine entries remain
`HOLD_FOR_HUMAN_PLAYBACK`; all three `00_UPLOAD_NOW` directories and all three
quarantine-media directories contain zero MP4 files.  The copied global guide
in every package rehashes to the v49 guide hash above, and no P16/P17/P18 or
superseded source leaked into the packages.

The exact final repository state passed `python -m unittest`: 450 tests passed
and 4 were skipped.  Python compilation, repository JSON parsing and
`git diff --check` also passed.

Suggested upload destinations remain separated by native size:

```text
U103 -> MagiaReco Slot native 416x232 gameplay/material collection BV
U104 -> new native 144x160 gameplay/material collection BV
U105 -> new native 128x64 gameplay/material collection BV
```

## Fail-closed direct-parent story blockers

Three native 512x288 single-event SP-story candidates were inspected but not
rendered:

```text
ac7113_015  request 10323
ac7115_007  request 10343
ac7116_028  request 10364
```

Each has one direct-parent SP-story OGG at event time zero and no child-audio
or subtitle row.  Nearby events prove that a parent SP-story track can coexist
with separate child dialogue, so its dialogue/BGM semantics cannot be inferred
from the filename or timing.  The exact source paths, source hashes, DirInfo
identities and required resolution are preserved in:

```text
tools/frida_runtime_probe/series_proposals/
  direct_parent_story_soundpack_blockers_v1.json
```

None/JA/ZH production remains blocked until a resolved runtime event manifest
or equivalent hash-bound evidence classifies the parent track, separates or
positively excludes BGM, and supplies any required subtitle timeline.

## Next boundary

No formal with-BGM candidate is ready.  Continue exhausting the no-BGM
inventory from ledger v17.  Formal with-BGM production begins only after every
discovered no-BGM item is either produced or assigned a precise blocker, and
only with bound track identity, entry phase, volume, fade/duck/stop, source hash
and event/route timing.
