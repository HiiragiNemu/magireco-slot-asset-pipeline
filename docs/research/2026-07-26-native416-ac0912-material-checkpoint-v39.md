# Native 416 ac0912 Material Checkpoint v39

Date: 2026-07-26

## Scope and output

This checkpoint produces one finite native 416x232 visual-only review
collection for all 42 reviewed ac0912 small-Kyubey three-stop guide events:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  material_collections_v39_native416_ac0912_review_20260726\
  ac0912_small_kyubey_3on_guides_v1\
  ac0912_small_kyubey_3on_guides_v1__material_components__416x232_30-1.mp4
```

The exact MP4 is 88.266 seconds, native 416x232 at 30 fps, and has SHA-256:

```text
B8C43A88E712BD11990C7D91C89E84C4D71E182E89C9AC3588CCD905E53862D6
```

The plan binds all 42 current v20 event manifests and the durable D:
official-name video map. It orders the official sources as common small-Kyubey
intro/loop, S-size flash plus five result-title intro/loop pairs, then the
corresponding L-size material. The S/L flash official names resolve to
byte-identical files, so the aggregate exact-AV duplicate gate records both
aliases and emits the content once. The final output therefore contains 23
unique segments from 24 planned names.

The H.264 streams are copied directly. The final MP4 contains neither audio nor
subtitles and does not consume or claim the child-local audio timing present in
the event manifests. It is a gameplay/material collection, not clean story and
not a native single-session route.

Automated technical QA passed. The exact file remains `review_only` and
requires owner playback before upload. The batch summary SHA-256 is:

```text
98AA7381186212812225825A799CF37E1FD460AED2BE398DE1865E0AF542DA64
```

## Ledger v8

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v8_20260726
```

The current material index now contains 6 manifests covering 63 unique events.
All 42 ac0912 events move from planned gameplay/material to produced
review-only material. Planned production-manifest gameplay/material items
decrease from 387 to 345. The four exact owner-approved v22 products and their
40-event exact-product coverage remain separately indexed; current event
timing-risk flags are not cleared.

```text
SUMMARY.json
  828D8EFCC038972F5945A97AF150E6757930FCE4B50DBAC91E044F9F27DED0BC
CURRENT_MATERIAL_COLLECTION_INDEX.json
  618E06CE83644CFF9B964CE04A7D8E1E41926986C20027FF9B40BE63EF4C7760
SHA256SUMS.json
  AACE910EEAF1DD2AE7166209967865B3C66D7BCFFBBEAF4C2E4AF10592333F26
```

## Upload guide v39

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v39_20260726
```

The guide contains 201 exact files: 10 already uploaded, 17 ready to upload,
174 requiring human playback, and 8 explicit exclusions. The only new exact
file is the ac0912 visual-only MP4 above:

- target: a future new native-416 gameplay/material BV;
- subtitle track: visual-only, no audio, no burned-in subtitles;
- suggested part name: `小丘比三停引导与结果文字素材 ac0912`;
- action: hold for owner playback, neither append nor replace yet;
- automated QA: passed visual-only review contract;
- human status: not yet playback approved;
- explicit exclusions: audio/subtitles, clean-story/native-session claims,
  P16/P17/P18, and all superseded ac7210 audit output.

```text
UPLOAD_GUIDE.json  700D9EB48B572D0B37A3CF538EE3553D64F9A70184D1C40C516EA1D35CB72945
UPLOAD_GUIDE.md    404F3E1DD77C4F6BD9C3E3EBEE94A39502C268B1F3C0A624E0278394D55289EE
UPLOAD_GUIDE.csv   396BE82EBF6D0C67BB2353E221F1E0C3426F158638C3C4C5C2BB3EEE692691EC
SHA256SUMS.json    14FBC7DF3DBDEAD7F0E5FC672B89C8B5F239AE11AF821C4FB3B8A3E1C5E8126A
```

P16/ac6003, P17/ac6004, and P18/ac6005 remain quarantined.
`ac7210_superseded_verbose_audit` remains audit-only and excluded. Codex does
not upload.
