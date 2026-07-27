# 2026-07-27 ac5102 nerae split-component checkpoint v57

This checkpoint closes ten ac5102 nerae gameplay/effect events that remained
outside the existing 120-event ac5102 split-component bundle. It does not
replace that bundle, cross-compose native dimensions, claim complete event
timelines, or alter uploaded, approved, frozen-handoff, or quarantined media.

## Exact event and source inventory

The covered events are:

```text
ac5102_025  ac5102_051  ac5102_077  ac5102_103  ac5102_129
ac5102_155  ac5102_181  ac5102_207  ac5102_233  ac5102_259
```

All ten audience rows are `mixed_full_frame_and_components`,
`gameplay_effect_collection`, and `planned_unproduced` in the v24 ledger.
Their 70/70 component occurrences are resolved as `exact_duration_unique`;
`auto_voice_count` is zero for every event.

The durable output is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_collections_v57_ac5102_nerae_delta_review_20260727
```

It contains two separate, non-upscaled visual-only review products:

- `ac5102_nerae_gameplay_components_416_v1`: 24 native 416x232 sources,
  60 occurrences, 51.498 seconds, manifest SHA-256
  `43FF9B102CD01F57869EF7706D3548D72D43F08800879E057EEC0910935AE6CB`,
  output SHA-256
  `0B07572E2C6B23B9FA29564EB7C7108DDC75F811C6CC5C160A896A3CC0E2A4F4`;
- `ac5102_gyakuosi_indicator_144x56_v1`: one native 144x56 source,
  `ac3405_gyakuosi_no_move`, shared by all ten events, 4.000 seconds,
  manifest SHA-256
  `38DF8249FEDFA8AE0D655C2DBCCD8E16592AEED3F1398414AD9AD61A963B9763`,
  output SHA-256
  `A35943125B664D359E46FC0612547D16F5AECA6DABEB0E129EE5FFB003C18189`.

All 25 unique sources are native 30 fps and have no audio stream. None of
their SHA-256 values overlaps the 542 sources in the v24 current material
index.

## Coverage boundary

The exact split-native coverage audit passes 10/10 events, 70/70 occurrences,
25/25 sources and zero unused sources:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_component_coverage_v57_ac5102_nerae_20260727\
ac5102_nerae_split_native_components_v1.json
```

SHA-256:
`507BD5134FCA0BA98F2973F3535DE16925D9FF3E493C222B4E7A668273B13612`.

Each event maps to six 416x232 occurrences and one 144x56 occurrence. The
coverage claim is limited to exact visual components. It does not authorize
overlay placement, z-order, alpha/blend behavior, parent holds, loop counts,
or a natural gameplay session. The two dimensions remain separate catalogs.

## Review delivery

The two review packages are:

- U140:
  `bilibili_incremental_review_v57_material_native416x232_20260727`;
- U141:
  `bilibili_incremental_review_v57_material_native144x56_20260727`.

Each package has separate none/JA/ZH target names backed by same-volume
hardlinks to one canonical silent visual file. Every exact file remains
human-playback-required. Both roots have zero `UPLOAD_NOW` media and zero
quarantine media. Package-summary SHA-256 values are:

```text
U140  C874CB613052AC791561F6BE6D729B4C30C2776D269B73295DB23EEA0DF899A2
U141  1B3C859E93CC20BF94BD01CD22390801C2DB32EBE489A7FE8EFF4481F5C7827E
```

## Ledger and upload guide

`production_ledger_v25_20260727` is current:

- produced audience events: 195;
- material-covered audience events: 628;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

Its `SUMMARY.json` SHA-256 is
`CF7FF685479AC3FD8E1B8470C0DCB32D6AC6927A50D8C7485999550D3EBD3C6E`.

`upload_guide_v57_20260727` contains 10 already-uploaded exact files, 17 exact
files currently allowed for upload, 316 human-playback-required files and
8 explicit exclusions, 343 indexed exact files total. Its JSON SHA-256 is
`EDB43526CC27D8E3127FD9992242C60DC80AFB9BD61F77F18727FB618CC5E723`.

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. The independent
with-BGM readiness audit still finds zero formally closed candidates: the
nearest ac7114/ac7115/ac7116 + BGM 835/836 queue still lacks same-run target
binding, event-zero phase, target volume state, full fade/duck control and
exit stop/replacement timing.

Final repository regression: `python -m unittest` — 473 passed, 4 skipped.
