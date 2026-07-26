# 2026-07-27 ac4902 selector-entry routes and ac0905 components checkpoint v52

This checkpoint adds one clean-route batch and one split-native material batch.
It does not modify the immutable freeze handoff, any previously approved or
uploaded media, or the P16/P17/P18 quarantine roots.

## ac4902 independent selector-entry routes

The current DirInfo kind 113 evidence contains 17 independent, non-duplicate
selector-entry rows that were absent from the earlier mature route batch:

`14, 15, 16, 17, 24, 25, 26, 27, 34, 35, 37, 44, 45, 46, 55, 58, 59`.

Nine other rows are exact audience aliases and are not rendered twice:

`36, 38, 39, 40, 41, 53, 54, 66, 67`.

The three entry events are exact direct-parent products:

- `ac4902_005` / alias `_056`: 603 frames, request 1691, sound code 8155;
- `ac4902_014` / alias `_057`: 100 frames, request 1698, sound code 8163;
- `ac4902_017` / alias `_058`: 189 frames, request 1702, sound code 8167.

Their child-audio and subtitle row counts are zero. The direct-parent action SE
begins at event-global sample zero. The route tails and subtitles are
hash-bound to the owner-approved v26 P12 family master. The builder also
fail-closed validates that the source master still contains the two authorized
`黑羽：可恶！` corrections; these 17 selected route slices do not themselves
include those two cues. No cross-route showcase is produced.

The durable output is:

```
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
no_bgm_editions_v51_ac4902_selector_entry_routes_review_20260727\
ac4902_selector_entry_routes_v1
```

It contains 17 route products and 51 final none/JA/ZH MP4s, all native
416x232, 30 fps, H.264/AAC 48 kHz stereo. Packet-audio and decoded PCM are
identical across the three editions of every route. All products remain
`AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED`.

- `BATCH_MANIFEST.json` SHA-256:
  `A979444F85A3C7A358A53902892E28FC88511D77B69D6199E5F726A46279B39F`
- `BATCH_SUMMARY.json` SHA-256:
  `057ECDADD480346BB8AAC649DFE0C26BDA44468F3D346BA5733561964027E25F`

The 17 routes are split at the ten-product limit:

- U108–U117:
  `bilibili_incremental_review_v52_ac4902_routes_batch01_final_20260727`
  (10 products, 30 MP4s, 457.87 seconds);
- U118–U124:
  `bilibili_incremental_review_v52_ac4902_routes_batch02_final_20260727`
  (7 products, 21 MP4s, 150.63 seconds).

Both review roots have zero `UPLOAD_NOW` media and zero quarantine media.
The earlier same-name roots without `_final_` are pre-handoff audit outputs and
must not be used as the current review entry points.

## ac0905 split-native visual components

Only the eight `mixed_full_frame_and_components` events are covered here:

`ac0905_003, _004, _005, _008, _011, _012, _013, _016`.

Fifteen exact sources are preserved in two non-upscaled visual-only catalogs:

- `ac0905_su_gameplay_components_416_v1`: 8 native 416x232 sources,
  27.998 seconds, output SHA-256
  `2961389CA76CF45D0F889CAE5B8FBAF26ABDEB3667B9F4D5BA8E65C6627108BF`;
- `ac0905_su_effect_frames_512x416_v1`: 7 native 512x416 sources,
  19.499 seconds, output SHA-256
  `2F229946300C6D5178C240ED550660254D78BAE80D1B32A6E7CCAA5ACBF2F2B0`.

The coverage audit passes 8/8 events, 15/15 unique sources and 16/16 audience
occurrences with zero unused sources:

```
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_component_coverage_v52_ac0905_20260727\
ac0905_split_native_components_v1.json
```

SHA-256:
`76E272A62930B8FA04E0ACA3CA5ED0F24CF45F789F574518B86ACDDF9CCA39F7`.

U125 and U126 are the 416x232 and 512x416 review roots. Their none/JA/ZH
entries are legal same-volume hardlink aliases of one silent visual product,
not three physical encodes. All remain human-playback-required.

The other eight `native_full_frame_only` ac0905 events remain blocked by a
missing modern event manifest. The unbound source
`ac0905_SU3_ef_waku_S_2` is not included.

## Ledger and upload guide

`production_ledger_v20_20260727` is the current exhaustive ledger. A failed
pre-publication v19 audit exposed that singular `dirinfo_source_row` records
were not counted; the builder now recognizes them and has a regression test.
The current v20 counts are:

- produced audience events: 188;
- material-covered audience events: 499;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

The active guide is `upload_guide_v52_20260727`:

- already uploaded: 10;
- exact files ready to upload: 17;
- human playback required: 287;
- explicit exclusions: 8;
- total indexed exact files: 314.

`UPLOAD_GUIDE.json` SHA-256:
`A6B1F7C198A4CE69BFDB7B51F6EB7FBADDB7940B11CE53C975BB30818DCB6B53`.

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. No v51/v52
review output is promoted merely because automated QA passed.

The final repository state passed `python -m unittest`: 468 passed, 4 skipped.
