# Native 416 ac7204 Material Checkpoint v40

Date: 2026-07-26

## Scope and outputs

This checkpoint produces two finite native 416x232 visual-only result-card
review collections:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v40_native416_ac7204_review_20260726
```

| Collection | Covered events | Clips | Duration | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `ac7204_small_result_color_cards_v1` | 12 | 12 | 12.000 s | `99631E653AA9A0756E32E9D2B29CE31DF8234FAE292285A901EA790E77EB0F5E` |
| `ac7204_large_result_color_cards_v1` | 15 | 16 | 16.000 s | `26828847F15CC76A2837ABCAD12D9C63EB88D59C0AE4647B572D76728D250D9F` |

The small collection preserves white, blue, yellow, green, red and purple
intro/loop pairs. The large collection preserves those six colors plus
fireworks and rainbow intro/loop pairs. All source event manifests and the
durable D: official-name video map are hash-bound.

Both MP4s retain native 416x232 at 30 fps by direct H.264 stream copy. They
contain neither audio nor subtitles and do not consume or claim child-local
audio timing. They are gameplay/result material, not clean story and not
native single-session routes.

Automated technical QA passed. Both exact files remain `review_only` and
require owner playback before upload. The batch summary SHA-256 is:

```text
FD21F357069DD0657ADFD42DB69EE9043A3B0B8066B69EE2CA8D1155452E95B8
```

Seven other ac7204 events (`_017`, `_021`, `_022`, `_023`, `_042`, `_043`,
`_044`) remain blocked by unresolved parent DGM to child Z2D event-global
timing. They are not counted as produced by this material checkpoint.

## Ledger v9

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v9_20260726
```

The current material index now contains 8 manifests covering 90 unique events.
All 27 ac7204 gameplay/result events move from planned to produced review-only
material. Planned production-manifest gameplay/material items decrease from
345 to 318. The seven timing-blocked ac7204 events remain blocked.

```text
SUMMARY.json
  9AE86965DDE7AB466BB442C0BE4B2FF2AAF972853EEABA6F289C11E76231581A
CURRENT_MATERIAL_COLLECTION_INDEX.json
  B1A30C1C7829FC9169365C6DE7CE944DC52A38A351226F0AAC00A1AC59ACB854
SHA256SUMS.json
  9F701DFD7616062ECA08679C0899F1745A7AACDF774221B6AA9F0B6D9392B185
```

## Upload guide v40

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v40_20260726
```

The guide contains 203 exact files: 10 already uploaded, 17 ready to upload,
176 requiring human playback, and 8 explicit exclusions.

| Exact file | Target / track | Suggested part | Action | Auto QA | Human |
| --- | --- | --- | --- | --- | --- |
| `ac7204_small_result_color_cards_v1__material_components__416x232_30-1.mp4` | new native-416 gameplay/material BV; visual-only | 小尺寸六色结果卡素材 ac7204 | hold; neither append nor replace | passed | pending |
| `ac7204_large_result_color_cards_v1__material_components__416x232_30-1.mp4` | new native-416 gameplay/material BV; visual-only | 大尺寸六色与烟花彩虹结果卡素材 ac7204 | hold; neither append nor replace | passed | pending |

The exact absolute folders are recorded in `UPLOAD_GUIDE.json`, `.csv`, and
the durable root `README_HUMAN_REVIEW.md`. Explicit exclusions are unverified
audio/subtitles, natural-story/session claims, the seven timing-blocked ac7204
events, P16/P17/P18, and all superseded ac7210 audit output.

```text
UPLOAD_GUIDE.json  34022B6A4D556A31C135F8AE230DD59F9FBE4B15B980961AE3EB713A370E7896
UPLOAD_GUIDE.md    7891A78A7FF7F3D93861A8E591D125A44FFE3621B3B18785D98FC97317F27537
UPLOAD_GUIDE.csv   6002980A4B091A19DD6A6A15E31D19631E89EC7382FD28A57FC0DDC273E43B28
SHA256SUMS.json    D264B36CF8AC9E956AD957FB8D74CB369CEE7CF45A956C04F6CEE64E18932BDB
```

P16/ac6003, P17/ac6004, and P18/ac6005 remain quarantined.
`ac7210_superseded_verbose_audit` remains audit-only and excluded. Codex does
not upload.
