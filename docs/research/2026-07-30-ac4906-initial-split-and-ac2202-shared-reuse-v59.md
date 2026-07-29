# 2026-07-30 ac4906 initial split and ac2202 shared reuse v59

This checkpoint adds two visual-only ac4906 component review products and
closes one ac2202 event by reusing hash-identical current media. It does not
reconstruct natural gameplay sessions, cross-compose native dimensions,
duplicate existing media, or alter uploaded, approved, frozen-handoff, or
quarantined files.

## ac4906 exact split-native inventory

`ac4906_001`, `_002` and `_003` are the only current ac4906 planned events
whose 12/12 component occurrences are fully resolved, exact-duration and
audio-empty. The durable product root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_collections_v59_ac4906_initial_split_review_20260727
```

- `ac4906_magius_white_progression_components_416_v1`: six native 416x232
  sources, 17.966 seconds, manifest SHA-256
  `50220EB49E054A2FFC2FB4E4B2D7886202B1AE445BCFD71B9F5001036DF04DAB`,
  output SHA-256
  `D9E47A1F98CF5311AE4FC434D55ECE3EB6BD035CB3BD633D7205A574012F9259`;
- `ac4906_magius_dark_overlay_component_208x120_v1`: one native 208x120
  canonical source, 1.000 second, manifest SHA-256
  `18AB72E16838B862375BE430AAADA6F14C1B7658294F1A04B2964B6AC74CA12D`,
  output SHA-256
  `F71CA6911169A142C6DE1F9F7A5209AD2A69850E7CA1DFF69954589DDB4D489C`.

The overlay intro and loop official names point to files with the same
SHA-256 and video-packet SHA-256. The material manifest therefore preserves
one physical source plus both official aliases and all six event occurrences.
The coverage auditor now validates each alias path against the canonical
source hash while counting one physical source. This is not a missing clip.

Coverage passes 3/3 events, 12/12 occurrences and 7/7 physical sources:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_component_coverage_v59_ac4906_ac2202_20260727\
ac4906_001_003_split_native_components_v1.json
```

SHA-256:
`3202500D603BD4E22CC4A96668A02256D3DB5E096878FABC933F94B67CD02BEB`.

Placement, z-order, alpha/blend, parent holds and loop counts remain outside
the claim. Later unresolved ac4906 events are not silently classified or
included.

## ac2202 hash-identical current reuse

`ac2202_005` contains the same two native 512x416 result sources already
current in `ac2201_result_and_target_components_512x416_v1`. No new media is
created. The current-reuse audit passes both occurrences and explicitly marks
the two unrelated target-text sources unused:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_component_coverage_v59_ac4906_ac2202_20260727\
ac2202_005_shared_result_components_v1.json
```

SHA-256:
`086B496A7534547AA65820C6150527C9E2AB4C6A5E1FE51C823BBEBD2C5062BD`.

The ledger now distinguishes this from split-native coverage with
`current_hash_identical_component_reuse_passed`.

## Review delivery and current ledger

The incremental packages are:

- U144:
  `bilibili_incremental_review_v59_material_native416x232_20260730`,
  package-summary SHA-256
  `770CEBF936716CF0FAD7E1C2F6BFC994A31FEDEA33BC42207BD607AAF45EDF58`;
- U145:
  `bilibili_incremental_review_v59_material_native208x120_20260730`,
  package-summary SHA-256
  `236E102AE685537F008149ABC668ED93C5EE342F55978E894C2BFC4A4033540D`.

Each contains separate none/JA/ZH target aliases backed by same-volume
hardlinks to one canonical silent visual file. Both contain zero
`UPLOAD_NOW` media and require project-owner playback.

`production_ledger_v27_20260730` is current:

- produced audience events: 195;
- material-covered audience events: 634;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

Its `SUMMARY.json` SHA-256 is
`708EC0F5265EB69EAD11DEE375A6365B35A0CD78731C7AC8923DE9B7429CD2DB`.

`upload_guide_v59_20260730` contains 10 already-uploaded exact files, 17 exact
files currently allowed for upload, 320 human-playback-required files and
8 explicit exclusions, 347 indexed exact files total. Its JSON SHA-256 is
`AA3F2D4D6FE192A93CF1052EA92CA2398A958B80344F3496D4ADDB2A5E4AC280`.

P13/ac4903 remains correctly bound to the v33 checkpoint: 19 safe independent
routes and 57 none/JA/ZH files are current. DirInfo rows 14, 18 and 21 still
terminate in mixed `ac4903_015` component composition and remain fail-closed;
v59 does not reclassify or render them. P16/ac6003, P17/ac6004 and P18/ac6005
also remain hard-quarantined.

Final repository regression: `python -m unittest` — 477 passed, 4 skipped.
