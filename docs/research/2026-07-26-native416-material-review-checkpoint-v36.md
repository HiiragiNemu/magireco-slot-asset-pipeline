# Native 416 Material Review Checkpoint v36

Date: 2026-07-26

## Scope

After exhausting the currently evidence-ready native 416x232 clean-story
route expansions, this checkpoint classifies three finite visual-only groups
as gameplay/material review collections. It does not promote them to audience
story products and does not treat automatic technical QA as human approval.

The durable output root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v36_native416_review_20260726
```

The builder accepts named, hash-bound evidence sources and an explicit
`source_root_overrides` mapping. The override is intentionally limited to
translating stale A: paths embedded in historical maps to the current durable
D: source root. No A: input is read. Each plan declares `covered_events`; the
builder verifies that the exact set matches the bound event production
manifests.

Visual-only collections may bind source clips with different embedded audio
signatures only because every source audio stream is discarded. The manifest
records each source audio signature, and final QA requires a video-only output.
This exception does not apply to audible review or audience products.

## Exact outputs

| Collection | Events | Clips | Duration | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `ac0906_small_kyubey_actions_v1` | 6 | 6 | 15.333 s | `248E3C6A1A7ADB5564A02E1D0AB161636FDFBD5C2D5FD98CE6CA030064A0A8E6` |
| `ac0931_uwasa_battle_intros_v1` | 5 | 5 | 105.000 s | `BCB19F3C3C5B14070DCE0C5153C125A71EB67E0B9899D662A9360B88F783294D` |
| `ac5004_chance_color_titles_v1` | 6 | 7 | 34.000 s | `C8728053A829D1FC89CB20B3EC3B88C6084B4053433CCCF7041C4686381D14AE` |

All three outputs are native 416x232, 30 fps, direct H.264 video stream copies,
with no final audio stream and no subtitle track. Automated technical QA
passed. Publication status remains `review_only`; all three exact files require
human playback and are not upload-ready.

The collection summary SHA-256 is:

```text
911CE3A5AC1F273CD1E1893362AF420730BC28334E62CEE9EA236207FE3057B0
```

## Exhaustive ledger

The v5 ledger consumes the v4 ledger plan through a hash-bound `base_plan`
overlay and adds only the v36 material root:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v5_20260726
```

It now distinguishes `produced_review_only_material_collection` from
clean-story output. It records 24 current production manifests, 3 current
material manifests, 173 produced audience events, 17 produced material events,
and 62 produced DirInfo routes. The remaining planned gameplay/material count
decreases from 408 to 391 without changing story readiness.

`ac7210_superseded_verbose_audit` is explicitly excluded from the current scan.
Only the v30 `ac7210` root is current. P16/ac6003, P17/ac6004 and P18/ac6005
remain quarantined.

Ledger hashes:

```text
SUMMARY.json     7BC3C52490C849512A11D93B876F18268A5768984B113ED2BA9804D60D95C72C
SHA256SUMS.json  9BF7647370C4BD50D6B1068568B3F04818FD0D7DAA5799D8EF297D495C8435D8
```

## Upload guide

The required per-file upload guide is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v36_20260726
```

It contains 194 exact files: 10 already uploaded, 13 upload-ready, and 171
requiring human playback, plus 8 explicit exclusion entries. The three v36
files are targeted only at a future new “native 416 gameplay/material
collection” BV. They have no subtitle track and are currently neither append
nor replace actions.

Guide hashes:

```text
UPLOAD_GUIDE.json  AA072277B54C0D26907990175410941BE83ABE9B6F91804DC0DE07D91A42A0F2
UPLOAD_GUIDE.md    08EEC6972F3FDD24610E71B66EE4F6FEF4A7132217B56BD58652F59FCDAC9278
UPLOAD_GUIDE.csv   7C28A2BFF2C966E2E603D9837E6E7EB522D166991F133C674462C43A984EB7A6
SHA256SUMS.json    02E4C9591E5D57212BA002973B7DE8644153F1D771A94BAB6CD0F3EF6D9FBA45
```

No media is uploaded to GitHub, and Codex does not upload to Bilibili.
