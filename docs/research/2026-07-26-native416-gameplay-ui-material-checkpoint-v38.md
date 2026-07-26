# Native 416 Gameplay UI Material Checkpoint v38

Date: 2026-07-26

## Scope and outputs

This checkpoint produces two finite visual-only gameplay UI review collections:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v38_native416_ui_review_20260726
```

| Collection | Covered events | Clips | Duration | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `ac8000_next_continue_ui_v1` | `ac8000_002`, `ac8000_003` | 4 | 10.000 s | `9996E71365100D31E011109EFCAF2885B8A7818B9819D95A07016DD9C0276A89` |
| `ac8004_shutter_transitions_v1` | `ac8004_005`, `ac8004_006` | 3 | 2.333 s | `094CF75827BDDC4751086EA22EF82FC129137470C4D71B2A62F7D983689F8666` |

Both are native 416x232 at 30 fps. The H.264 streams are copied directly; final
outputs contain neither audio nor subtitles. Source event manifests and the
durable D: official-name video map are hash-bound. The visual collection does
not consume or claim child-local audio timing. In particular, the shutter
source's external slot sound is deliberately outside this product.

Automated technical QA passed. Both exact files remain `review_only` and require
human playback before upload. The batch summary SHA-256 is:

```text
F90BD5209CCCBFD3CAA7889647294C0A4BE318292DAFF3B3C44336E60F8AE823
```

## Ledger v7

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v7_20260726
```

The current material index now contains 5 manifests covering 21 events. Planned
production-manifest gameplay/material items decrease from 391 to 387. The four
exact owner-approved v22 products and 40-event exact-product coverage remain
indexed separately. Current event-manifest timing-risk flags are not cleared.

```text
SUMMARY.json
  8C2C3CA25A714FA3392151D482345EC3FF3BC11C3F79C849F9D034098A675099
CURRENT_MATERIAL_COLLECTION_INDEX.json
  727CD928883C2CF462558DCB223D520D6E161CFC77212F349D062279BAA75E1E
SHA256SUMS.json
  246E80D363C1D9D6B0CC202BC123FC0DBB32FC56A805FC93F72151451EDCA4E7
```

## Upload guide v38

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v38_20260726
```

The guide contains 200 exact files: 10 already uploaded, 17 ready to upload,
173 requiring human playback, and 8 explicit exclusions. The two v38 material
files are the only new review-required entries; no new file is promoted to
upload-ready in this checkpoint.

```text
UPLOAD_GUIDE.json  034911985AC003F3A9C7FE519A4844877FED7A463B611DA49F4938777E6AD1D5
UPLOAD_GUIDE.md    F172970838B25279A20CBC7B0DD55C3EA32F04DDCF5CD51BED717AA407750C24
UPLOAD_GUIDE.csv   71A6B42765348A078C93FB0581D59D0747652346F88FCCE38010D752782E911C
SHA256SUMS.json    51BD737368C15E1210B57066521B691EE901FCB87112A771A47CA2A82E91AE6F
```

P16/ac6003, P17/ac6004, and P18/ac6005 remain quarantined.
`ac7210_superseded_verbose_audit` remains excluded. Codex does not upload.
