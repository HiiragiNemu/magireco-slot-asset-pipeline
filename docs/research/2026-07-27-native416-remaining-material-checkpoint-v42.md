# Native 416 Remaining Material Checkpoint v42

Date: 2026-07-27

## Freeze boundary and scope

The project owner explicitly lifted the 2026-07-27 production freeze. The
completed frozen handoff remains immutable at:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_human_review_upload_freeze_20260727
```

This checkpoint did not overwrite or add files to that root. It resumed the
exhaustive ledger from v10/v41, first rechecked the native 416x232 story/route
lane, and found no additional event-exact natural family or DirInfo route that
was not already produced or precisely blocked. The next evidence-ready native
416 work was the remaining gameplay/material set.

## Four visual-only review products

The new durable production root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v42_native416_remaining_review_20260727
```

| Collection | Events | Unique clips | Duration | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `ac0914_uwasa_narration_transition_layers_v1` | 3 | 4 | 11.566 s | `A70F07643BF5E9C0EC94A8338272CAF5437CE32E63B8648D5FEA2E989468C2D9` |
| `ac0914_uwasa_outcome_layers_v1` | 10 | 13 | 93.566 s | `C413407DA0ADD4E44CABABA7289CA5802DD2F27162AAE2DB16811505D58D1B80` |
| `ac1103_demae_victory_revival_layers_v1` | 3 | 13 | 25.466 s | `F7570B8D186670C85900C1ECBE0BBCBC867868C0BF7029739E6DE5EE098E1393` |
| `ac2201_kuroe_nerae_gameplay_layers_v1` | 1 | 8 | 16.965 s | `D6F5711C1C606EBFC58D626491BEB18F6DB0A5C3927D6297437045A3418BD506` |

The ac0914 outcome plan contains 20 official names. Seven are exact media
aliases, so the visual-only dedupe gate emits 13 unique clips while retaining
all 20 source occurrences and their official-name provenance. The gate now
treats a code name as an alias when the visual packet, embedded audio packet,
stream signature, duration, cue times, text and mix evidence are otherwise
identical. Different audio/cue evidence still prevents deduplication.

The initially separate ac1103 background and WIN-logo drafts were consolidated
into one audience product because both claimed the same events. The two draft
outputs remain only under `superseded_overlap_split_audit`; they are excluded
from current ledger scanning and must not be uploaded.

All four current MP4s are native 416x232, 30 fps H.264 with no audio or subtitle
stream. Embedded source audio is intentionally dropped where present. Automated
technical QA passed, but every output remains `review_only`,
`human_playback_required`, and non-publishable. They are gameplay/material
collections, not clean story and not native single-session routes.

## Three target-track review aliases

The incremental human-review package is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v42_native416_materials_20260727
```

It contains four products (`U077`-`U080`) and 12 correctly named review
entries: none, JA and ZH for every product. Because these products contain no
audio and no burned-in subtitles, each three-edition set is one canonical
physical file plus two same-inode hardlink aliases. `physical_duplicate=false`
and the per-target recommendation are recorded in `UPLOAD_INDEX.csv` and
`ALIASES.csv`.

There are no files in `00_UPLOAD_NOW`: this means no new exact file has owner
playback approval, not that the none edition was omitted. The only review batch
is:

```text
02_REVIEW_MATERIAL\batch_001
```

It has four products, 12 target entries, four unique hashes and 147.563022
seconds of unique playback. No quarantined MP4 is present.

```text
PACKAGE_SUMMARY.json  567FACD9B846376110736B24B5C5C210E320B37D828808DDDD261FF92910E0FA
UPLOAD_INDEX.csv      CE5C713D0FACE947BDAF3531221ECAEE7EFD8AC128B2F8322E6A229980C21991
SHA256SUMS.txt        BBF10AC85C2AD96F243810E2033C1E4E689355DB514EE091BFEA7B88D4E3D8B6
```

## Exhaustive ledger v11

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v11_20260727
```

The current material index advances from 11 to 15 manifests and from 105 to
122 covered events. All 17 remaining evidence-ready native-416
gameplay/material events move from planned to produced review-only material;
the production-manifest gameplay/effect planned count falls from 303 to 286.
The four other-native-size event-exact candidates remain separately classified
as `evidence_ready_event_waiting_route_product`.

```text
SUMMARY.json
  134781A59BB2000A69853B51D2468ECCB1681C3B38B9EEF732E2F02F69177F3E
CURRENT_MATERIAL_COLLECTION_INDEX.json
  1B1CA86BFDCA584FF62C3AE0C597E997755CB96B15D7465D2C5E09C869010BF6
SHA256SUMS.json
  CC0B68ECD37B8D60D0478AC63405E4B4CEA1F38A8A696FDD0B7BA1C59AEB89FD
```

## Upload guide v42

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v42_20260727
```

The global guide contains 210 exact files: 10 already uploaded, 17 exact-file
approved, 183 requiring human playback, and 8 explicit exclusions. Its four
new canonical material outputs are complemented by the 12 direct target-track
entries in the incremental review package above.

```text
UPLOAD_GUIDE.json  9CEDBCB81A30029290297ADA943F6ED3EC05BF37BAA67EB502CA87B7CF77BD08
UPLOAD_GUIDE.md    72204E2DBFA1E3818BF2FEC1F02080E6256ED57EA70274752BACFA97A6D63EBA
UPLOAD_GUIDE.csv   84B8155F671A19E6567F21A1B96C7E07E138F2EE0BA08A324D4F2E3C50F99427
SHA256SUMS.json    E13964DAD59446C37A05C620CDE0AFD77528DF4BAE888F7D9CE2355C715C42DE
```

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. Unresolved
child-local timing, mutually exclusive route concatenation, superseded output,
old errors, and already-uploaded exact hashes remain excluded.

## BGM readiness boundary

No formal with-BGM render candidate is currently evidence-closed. Exact source
identity is known for BGM resources 835 and 836 and the Sound Pack 826 gate,
but family/route binding, event-zero phase, loop count, same-frame fade/duck/
stop control, pre-entry player state and Sound Pack transition timing are not
closed. BGM preparation therefore stays independent and cannot contaminate
the stable no-BGM outputs. Formal with-BGM production begins only after the
discovered no-BGM inventory is produced or precisely block-listed and an
individual route has all required BGM evidence bound.

Codex does not upload or modify Bilibili.
