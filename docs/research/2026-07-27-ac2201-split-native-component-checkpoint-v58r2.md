# 2026-07-27 ac2201 split-native component checkpoint v58r2

This checkpoint closes the exact visual-component inventory for `ac2201_005`
and `ac2201_006`. It does not reconstruct a natural gameplay session, mix
native dimensions, authorize an audible release, or alter uploaded, approved,
frozen-handoff, or quarantined media.

## Exact visual inventory

The v25 audience ledger classifies both events as
`gameplay_effect_collection` and `planned_unproduced`:

- `ac2201_005` contains two exact native 512x416 result clips;
- `ac2201_006` contains four already-current native 416x232 entry clips, two
  new native 416x232 CU clips, and two native 512x416 target-text clips.

The current products are:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_collections_v58r2_ac2201_split_delta_review_20260727
```

- `ac2201_kuroe_cu_gameplay_delta_416_v1`: 2 clips, 8.000 seconds,
  manifest SHA-256
  `5D50393641003B14EA6D60394F94854CE014DE272C513DD0E21C871EC15C3058`,
  output SHA-256
  `2E48FC6909127C935BF441308926488F5A183920426B8E62F562F10FBAB1E58F`;
- `ac2201_result_and_target_components_512x416_v1`: 4 clips,
  15.166 seconds, manifest SHA-256
  `3849D664A67CDD7A456DF02BB95CADD7E4506057CB6AF88E906487542C3F13D0`,
  output SHA-256
  `3F0D873F8179AE1C658FAE9D0A85A946ACEE1B0EB97D97BA3349D440ABC24D77`.

The two new 416x232 CU sources contain embedded ALAC. One is audible and one
is digital silence, but the audible source's semantic role is unresolved.
Both embedded tracks are deliberately dropped. The product is visual-only,
has `unknown_audio_count=2`, and is prohibited from serving as an audible
edition. The four 512x416 sources have no audio stream.

The named-material builder now supports a fail-closed
`component_official_name_allowlist` for a delta selected from a hash-bound
audience event inventory. The allowlist is accepted only for derived component
events, must be unique, and must resolve exactly at the declared native
dimensions. This lets the ac2201 delta bind to `ac2201_006` without duplicating
the four sources already present in the current ac2201 catalog.

## Coverage boundary

The split-native coverage audit is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
material_component_coverage_v58r2_ac2201_20260727\
ac2201_005_006_split_native_components_v1.json
```

SHA-256:
`E6F14E9A14EFD5931305F003A374777249E6520A75822AEF6B85A2793220CF6E`.

It passes 2/2 events and all 10 exact component occurrences. Four sources in
the older eight-source ac2201 catalog are explicitly allowed unused because
they do not occur in `_005/_006`; the other four old sources and all six new
sources are used. This is visual component coverage only. Placement, z-order,
alpha/blend, parent holds, loop counts and the natural event timeline remain
outside the claim.

The earlier `material_collections_v58_ac2201_split_delta_review_20260727` and
`material_collections_v58r1_ac2201_split_delta_review_20260727` roots are
superseded audit-only attempts. They are not current and must not be uploaded.
Only v58r2 is indexed.

## Review delivery

The two incremental review packages are:

- U142:
  `bilibili_incremental_review_v58r2_material_native416x232_20260727`;
- U143:
  `bilibili_incremental_review_v58r2_material_native512x416_20260727`.

Each package contains separate none/JA/ZH target aliases backed by same-volume
hardlinks to one canonical visual-only MP4. All exact files remain
human-playback-required. Both roots contain zero `UPLOAD_NOW` media and zero
quarantine media. Package-summary SHA-256 values are:

```text
U142  05A53C5A050A51B1D3028E88BE958A80A6F1CCE63808DF222B6F2DBCE17AF427
U143  70BE5327E6F77A82D5CF89992E2D1F6E26541D2CB6007B3628FD058A99C0B4DA
```

## Ledger and upload guide

`production_ledger_v26_20260727` is current:

- produced audience events: 195;
- material-covered audience events: 630;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

Its `SUMMARY.json` SHA-256 is
`F842ACB0409CCA00EC4B01F5711AB2F51C92A5A67F69B764F2D915A299059C4A`.

`upload_guide_v58r2_20260727` contains 10 already-uploaded exact files,
17 exact files currently allowed for upload, 318 human-playback-required
files and 8 explicit exclusions, 345 indexed exact files total. Its JSON
SHA-256 is
`C2BF7A21BDC397DB4C43DB93D8E799E9E13AB9783AB88F53D9F47E571E1C134D`.

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. Formal
with-BGM production still has zero evidence-closed candidates. The nearest
ac7114/ac7115/ac7116 plus BGM 835/836 queue still lacks same-run target
binding, event-zero phase, target volume, full fade/duck behavior and exit
stop/replacement timing. ac4913 also remains blocked from safe no-BGM route
production until route-level direct-parent audio can cross an event boundary
without extending or corrupting the first visual event.

Final repository regression: `python -m unittest` — 474 passed, 4 skipped.
