# Native 416 ac4904 Material Checkpoint v41

Date: 2026-07-26

## Scope and outputs

This checkpoint produces three native 416x232 visual-only SU character-window
review collections:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v41_native416_ac4904_review_20260726
```

| Collection | Characters / sources | Clips | Duration | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `ac4904_su_window_group_01_v1` | common antenna + Iroha, Yachiyo, Sana, Tsuruno, Felicia | 16 | 55.666 s | `AB6500D70BD71BF2DE366DB11E6FADE39805D356AF89D3C92F2DF9D672138E0E` |
| `ac4904_su_window_group_02_v1` | Madoka, Sayaka, Mami, Kyoko, Homura | 15 | 48.000 s | `8A5868D05AB7B3E2C12CA5599AC68DE6996C67F805061C2EAE2B07D51C5CF628` |
| `ac4904_su_window_group_03_v1` | Nemu, Touka, Alina, Iroha variant, Ui | 15 | 60.999 s | `76B1E742728B1948A0DB1FEDE89376630B70FF4EF35DC4E3D93DACCC00247593` |

All 15 current ac4904 event manifests and the durable D: official-name video
map are hash-bound. The common antenna source is retained once in group 01,
not repeated in groups 02 or 03. Each character contributes intro, additional
layer and loop material.

All MP4s retain native 416x232 at 30 fps by direct H.264 stream copy. They
contain neither audio nor subtitles and do not consume or claim child-local
audio timing. They are gameplay/material, not clean story and not native
single-session routes.

Automated technical QA passed. All three exact files remain `review_only` and
require owner playback before upload. The batch summary SHA-256 is:

```text
A9CE3511DBA2726215B0246530F8CEB011FAAAA66D6A04B434B1DA159F746F81
```

## Ledger v10

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v10_20260726
```

The current material index now contains 11 manifests covering 105 unique
events. All 15 ac4904 gameplay/material events move from planned to produced
review-only material. Planned production-manifest gameplay/material items
decrease from 318 to 303.

```text
SUMMARY.json
  0F29B74C717507F181CF67AE346350A8FBE1D9EEB86B223EC1B1DB3FF9B2B875
CURRENT_MATERIAL_COLLECTION_INDEX.json
  3C48B7C22AC4CF413864370BCF0C1624CB1F9DFA3B0FD4B7EB1E0F57D968C2C5
SHA256SUMS.json
  9A501C6DED8E78D2FF44E7D57CA8DF471F9E82DF527ED6D0783B1FBB3CDA4F78
```

## Upload guide v41

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v41_20260726
```

The guide contains 206 exact files: 10 already uploaded, 17 ready to upload,
179 requiring human playback, and 8 explicit exclusions.

All three new files target a future native-416 gameplay/material BV, have no
subtitle track, and are held for owner playback rather than appended or
replaced. Suggested parts are the five-character group labels recorded in the
durable `README_HUMAN_REVIEW.md`. Automated QA passed; human approval is
pending. Explicit exclusions are event audio, clean-story/native-session
claims, P16/P17/P18, and all superseded ac7210 audit output.

```text
UPLOAD_GUIDE.json  3E223C4A6718D4B7FA91C8BB7AED8AE52568F309A41DCA59BA8E987834761B70
UPLOAD_GUIDE.md    AD05FA5E82F3C28F965015D1A7CE7CA24F6C578055061A4A082830A9A8326116
UPLOAD_GUIDE.csv   CD57600762E0FD4EDEE03DE19161A88B6CA4195C8F7C8E2FCFFD2E4A7DAB8922
SHA256SUMS.json    835B527362E8BC140A4082B7207C475163E331DDED014B7BCDF607EA00E08B42
```

P16/ac6003, P17/ac6004, and P18/ac6005 remain quarantined.
`ac7210_superseded_verbose_audit` remains audit-only and excluded. Codex does
not upload.
