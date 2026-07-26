# 2026-07-27 ac0916 split-native component checkpoint v53

This checkpoint closes the currently discovered ac0916 component inventory. It
does not compose the three native sizes into event videos and does not alter
any uploaded, approved, frozen-handoff, or quarantined media.

## Exact inventory

The covered set contains 104 `mixed_full_frame_and_components` gameplay/effect
events:

`001–006, 008–049, 051–074, 076–107`.

The hash-bound audience catalog contains 652/652 resolved
`exact_duration_unique` occurrences and 39 unique source files. None of those
source SHA-256 values overlaps the 464 sources in the v20 current material
index.

The durable output is:

```
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_collections_v53_ac0916_split_components_review_20260727
```

It contains three separate, non-upscaled visual-only review products:

- `ac0916_character_action_components_416_v1`: 23 native 416x232 sources,
  236 occurrences, 155.632 seconds, output SHA-256
  `1297757D7E2F4990FE0E543BC37A86803A54FF7CD2FF6FFA367DD443ED69C6DA`;
- `ac0916_text_in_add_components_416x120_v1`: 4 native 416x120 sources,
  104 occurrences, 5.333 seconds, output SHA-256
  `1F567908F1F0106E990C59833E99188ABA88345FF705B07B1136657820F65275`;
- `ac0916_text_effect_components_160x120_v1`: 12 native 160x120 sources,
  312 occurrences, 21.332 seconds, output SHA-256
  `40F02363A369F6BE49FE6864C78F60B0B899C8D79E93389081EC70CDE70D131B`.

One source, `ac0916_lev_sana_hensin_c01_ren_c05`, carries a 48 kHz stereo ALAC
track. Its decoded mean and maximum are both -91 dB and its decoded audio hash
is `4E8131B524A1C5C7A9F3193502516D496F67246C04E7C83AD6C98BEFD3CD2F13`.
The formal outputs therefore drop it as digital silence; it is not relabeled
as dialogue, SE, or BGM. The other 38 sources have no audio stream.

## Coverage and review delivery

The coverage audit passes 104/104 events, 652/652 occurrences, 39/39 sources
and zero unused sources:

```
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_component_coverage_v53_ac0916_20260727\
ac0916_split_native_components_v1.json
```

SHA-256:
`84991B6F433F6FE6205A16B2D7F8AB3BA007DA78BAB34775D60B743304294C28`.

The three review packages are:

- U127: `bilibili_incremental_review_v53_material_native416x232_20260727`;
- U128: `bilibili_incremental_review_v53_material_native416x120_20260727`;
- U129: `bilibili_incremental_review_v53_material_native160x120_20260727`.

Each has separate none/JA/ZH entry names backed by same-volume hardlinks to one
canonical silent visual file. Every exact file remains human-playback-required;
all three roots have zero `UPLOAD_NOW` media and zero quarantine media.

## Ledger and upload guide

`production_ledger_v21_20260727` is current:

- produced audience events: 188;
- material-covered audience events: 603;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

`upload_guide_v53_20260727` contains 10 already-uploaded exact files, 17 exact
files currently allowed for upload, 290 human-playback-required files and
8 explicit exclusions, 317 indexed exact files total. Its JSON SHA-256 is
`08A7852D27F651FA2FC6B84CC428E3860CE56C3620E99230977C7C93A274CAAE`.

## ac0903 fail-closed compositor blocker

`ac0903_001` has exact DirInfo identity, exact parent-Z2D frame intervals and
direct-parent request 680 at event-global 0 ms. It is not rendered. The current
evidence does not prove the native add/mlt blend equations, color/alpha model,
final z-order, canvas transform, renderer quantization, shader state, or a
reference framebuffer hash; the formal renderer also does not support these
unproven modes.

The durable JSON-only blocker is:

```
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
composition_blockers_v53_ac0903_20260727
```

It records `render_authorized=false`, `publishable=false` and
`media_outputs_written=0`. File suffixes are retained only as unproven
candidates; neither guessed FFmpeg blend modes nor visual similarity may
promote this item.

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. Formal with-BGM
candidates remain zero.

Final repository regression on the committed-code candidate:
`python -m unittest` — 469 passed, 4 skipped.
