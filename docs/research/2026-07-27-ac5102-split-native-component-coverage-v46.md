# ac5102 Split Native Component Coverage v46

Date: 2026-07-27

## Result

The durable native-416 production root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v46_ac5102_split_components_review_20260727
```

It contains one visual-only product:

| Collection | Component events | Unique clips | Duration | Native size | SHA-256 |
| --- | ---: | ---: | ---: | --- | --- |
| `ac5102_416_component_visual_catalog_v1` | 116 | 49 | 45.428971 s | 416x232 | `D067F5393576CF4A85EF9105A30571A18DF25DC39913B252E1588078D0707357` |

The output is H.264 at 30fps and has no audio stream or subtitles. Video
packets are copied directly from the exact native sources. No source is
resized or upscaled.

## Why this is a split catalog

The remaining 120 ac5102 production-manifest events do not have one common
native canvas:

- 116 events reference native 416x232 character/action components and native
  512x288 chance-button components;
- four events (`ac5102_246`, `_248`, `_250`, `_252`) use only the native
  512x288 button components;
- the complete unique source set is 49 native-416 clips plus eight native-512
  clips.

The eight 512x288 sources are already exact members of the v44
`ac8002_chance_button_prompt_catalog_v1`. Re-encoding or copying them into the
416 product would create a misleading mixed-size linear render. The v46
product therefore contains only the native-416 components, while the v44
product remains the canonical review product for the 512 components.

## Cross-catalog fail-closed audit

The coverage audit is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_component_coverage_v46_ac5102_20260727\
  ac5102_split_native_components_v1.json
```

SHA-256:

```text
53B179EFD8CB2305B9AD62ADE8AB39A8FD29F8B6999EE3D300B647029174BE6B
```

The auditor:

1. binds the v14 production-event ledger by SHA-256;
2. selects exactly the 120 ac5102 rows still classified as
   `gameplay_effect_collection/planned_unproduced`;
3. rehashes every event manifest named by those rows;
4. walks every manifest clip and requires its exact official name, path and
   source SHA-256 to exist in exactly one declared native-size catalog;
5. checks that every 416 clip is present in the v46 per-event component map;
6. checks that every 512 clip is present in the current v44 catalog;
7. requires all 49 v46 sources and all eight event-used v44 sources to be
   consumed;
8. permits only the two declared generic v44 sources
   `ac8002_chance_btn` and `ac8002_chance_btn_LP` to remain unused.

The result is 120/120 event manifests and all 57 event-used unique source clips
covered. The audit records 126 immutable source snapshots.

This claim is deliberately narrow. It proves visual component inventory
coverage, not:

- a reconstructed natural event/session timeline;
- a mixed-size composition;
- resolved dialogue, SE or subtitles;
- resolved parent-DGM to child-Z2D timing;
- release eligibility.

## Incremental human-review package

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v46_ac5102_split_components_20260727
```

U091 is in `02_REVIEW_MATERIAL\batch_001`. The none, JA and ZH entries are
correctly named same-volume hardlinks to the same canonical silent MP4.
There are three target entries, one unique SHA-256, two legal cross-target
aliases and 45.428971 seconds of unique playback.

There are no files in `00_UPLOAD_NOW` and no quarantined media. Automatic QA
passed, but every exact file remains on hold until project-owner playback
approval.

```text
PACKAGE_SUMMARY.json  4E618E251926162C9AFD4E876C78635421EA3B8F58B95E9773A824ECB08795D0
UPLOAD_INDEX.csv      5B018AE93BE5069EC03F86F18D486D9008B3374886888FCDDD9C62148EC0EF14
SHA256SUMS.txt        DBFC7E033C5B68A31C180B53A2F09D7B9510EF9956885C726B163F417D025F4B
```

## Ledger and upload guide

`production_ledger_v15_20260727` contains 22 current material manifests and
one split-component coverage bundle. Material coverage advances from 288 to
408 events.

Within the hash-bound 926-event production-manifest inventory:

- 168 events are in current clean-story production roots;
- 408 events are covered by review-only material products;
- 330 events are blocked by unresolved child-local timing;
- 20 events remain quarantined in P16/P17/P18;
- zero events remain `planned_unproduced`.

This closes only the existing modern production-manifest inventory. The larger
audience and DirInfo mother sets still contain unresolved classifications,
missing modern manifests and route evidence blockers; v46 does not authorize
switching to with-BGM.

```text
SUMMARY.json
  96E2BDFF648606EA4E7AF134FAA7FD6E590304E06093E125EE142BB814C06A33
CURRENT_MATERIAL_COLLECTION_INDEX.json
  44D0A0142B531F4ADD9CF79ADC417E7A8595B9A65D83C549ACAF5D20789B58B7
SHA256SUMS.json
  F311DA351B8726B1D78BCFD27A3C7843DDBE60695B1BFCC14291346C8D45F983
```

`upload_guide_v46_20260727` contains 10 already-uploaded files, 17 exact
ready-to-upload files, 202 exact files requiring playback and eight explicit
exclusions, for 229 exact files total.

```text
UPLOAD_GUIDE.json  57D65BF7E7A0D55F24BD0B841CCDEBF506D4E6CED46D10771F2312D0AC5CEF21
UPLOAD_GUIDE.md    E586DA680C1455BB6689FAFD50A18CFE53224D665883E9B392A8331127D4B819
UPLOAD_GUIDE.csv   0918CD1CAADAA32AB29BD6A6F9B7E28D5057A4DB63775DD3C44B9898843CEB18
SHA256SUMS.json    46F83B9900F644AF997B0E88CB3F08D4582DC21D15191AB015018F5FE88E1B5C
```

The immutable freeze handoff was not modified. P16/ac6003, P17/ac6004 and
P18/ac6005 remain quarantined. All unresolved child-local timing and
superseded outputs remain fail-closed.
