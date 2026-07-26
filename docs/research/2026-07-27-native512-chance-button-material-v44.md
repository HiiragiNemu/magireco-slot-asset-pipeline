# Native 512 Chance-button Material v44

Date: 2026-07-27

## Result

The durable production root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v44_native512_chance_buttons_review_20260727
```

It contains one visual-only gameplay material product:

| Collection | Events | Clips | Duration | Native media | SHA-256 |
| --- | ---: | ---: | ---: | --- | --- |
| `ac8002_chance_button_prompt_catalog_v1` | 59 | 10 | 14.000 s | 512x288, 30fps, H.264, no audio | `D2C2E4F08ABE40751976BAEF4E30F2D35FB9EA7BD04E4426923362D2654EBAC2` |

The five semantic prompt types are generic CHANCE, press, multi-hit,
long-press and rapid-tap. Each type retains its exact intro and loop source once.
The output directly copies the native H.264 packets; it has no audio stream and
is not upscaled.

## Exact event coverage

The catalog covers 59 planned gameplay/effect events:

- 25 `ac0909` events;
- `ac6101_2_01`;
- `ac7221_005`;
- 12 `ac8002` events;
- 20 `ac9051` events.

Every covered event's complete visual clip set resolves exclusively to one of
the ten catalogued MP4s. The plan binds
`production_ledger_v12_20260727/PRODUCTION_EVENT_LEDGER.csv` at SHA-256
`2AFBB7FE04EB34DFED9E2B75575C85C5752787D6FF32AC67AA17AE08B0D062AA`.
The builder then rehashes the 59 manifest paths and SHA-256 values named by that
ledger before accepting coverage.

The material source snapshot has 72 exact files: the plan, the bound ledger,
the official-name map, 59 v20 event manifests and ten source MP4s. All 72 were
rehash-verified after the build.

The multi-segment event identity `ac6101_2_01` required the material event-name
gate to accept `ac` identifiers with more than one numeric suffix. The expanded
gate remains numeric-only and is covered by a regression test.

## Audio and subtitle boundary

The 59 source events contain 105 audio layers and 302 subtitle cues. They are
all deliberately excluded from this visual-only product. Many source manifests
carry unresolved child-local timing risk, but that risk is neither consumed nor
claimed fixed here.

This product means only:

- the five exact native button visuals are preserved;
- repeated occurrences are represented by one gameplay material catalog;
- event audio, subtitle timing and natural-session playback are outside this
  product.

It is not a clean-story animation and is not an event-session concat.

## Incremental human-review package

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v44_native512_chance_buttons_20260727
```

U085 has separate none/JA/ZH filenames in
`02_REVIEW_MATERIAL\batch_001`. Because the product has no audio and no burned-in
subtitles, all three names are legal same-hash, same-inode hardlink aliases.
They use one physical media file and keep distinct target-track entries.

There are zero files in `00_UPLOAD_NOW` and zero quarantined MP4s. The exact
file remains on hold until owner playback approval.

```text
PACKAGE_SUMMARY.json  71B9982FB0DB37771A156399907DAFB570211F266EFDCEA0AC4A4FD959042E28
UPLOAD_INDEX.csv      77D2110242AA1C25FF05EA2B843DE363C0EA42F232DA01AB1FF5AE6285F45597
SHA256SUMS.txt        65528F421C0A2EE5172BC2B0164A26A7755FC5A9A973223A26F2711F86295F56
```

## Ledger and upload guide

`production_ledger_v13_20260727` advances material coverage from 122 to 181
events and reduces production-manifest `planned_unproduced` from 286 to 227.
Blocked timing and quarantine counts are unchanged.

```text
SUMMARY.json
  EF949DF5251C78AB659A9FE28604AEA3ED2B6880047635BFEF5BA1D0CE0CB9D3
CURRENT_MATERIAL_COLLECTION_INDEX.json
  FC612D01941DD16B9FE25DD92AF06BB78270EA2250659F5E9E228237FE283199
SHA256SUMS.json
  68A8A10A557FE846FAC1F8C90F28E5E1772BDF704D025FE08FD58BBA870187C2
```

`upload_guide_v44_20260727` contains 10 already-uploaded files, 17 exact
ready-to-upload files, 196 exact files requiring playback and eight explicit
exclusions, for 223 exact files total.

```text
UPLOAD_GUIDE.json  82430859FEA06B30A6DA88F8B3362E964ED0523FAB612CBB0AEF42D6DB6BA773
UPLOAD_GUIDE.md    9F13F118FD931AB75EA32F6E2C71A44F91C195BAF5F8C177A036F8DF1C969531
UPLOAD_GUIDE.csv   79AD53FE803F34B86C3F56CE2CAB316145B3C8FCFB73D9281F6787979F92DD66
SHA256SUMS.json    503C78AAAE60355E62B080E71D3AFDD90A250A4E094E4621506CD1EC4BB7293F
```

## Next inventory

The remaining 227 production-manifest gameplay/effect events are:

| Family | Events | Visual boundary |
| --- | ---: | --- |
| `ac3102` | 57 | 118 unique native 512x288 clips |
| `ac3103` | 24 | 32 unique native 512x288 clips |
| `ac3407` | 12 | 28 unique native 512x288 clips |
| `ac3409` | 12 | 28 unique native 512x288 clips |
| `ac5102` | 120 | mixed 49 native 416x232 and 8 native 512x288 clips |
| `ac8000` | 2 | four unique native 512x288 clips |

The pure 512 groups can proceed as separate visual-only review catalogs.
`ac5102` must be split by native layer size and cannot be linearly concatenated
or upscaled.
