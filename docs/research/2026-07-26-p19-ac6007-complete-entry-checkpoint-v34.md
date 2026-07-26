# 2026-07-26 P19/ac6007 complete-entry checkpoint v34

## Outcome

This checkpoint produces two finite native 416x232 no-BGM ac6007 clean-story
route candidates. It does not alter or replace the already uploaded P19 ZH
file. P16/ac6003, P17/ac6004, and P18/ac6005 remain in hard quarantine. Codex
did not upload media.

The review root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  manual_review_candidates_v34_p19_ac6007_complete_routes_20260726\ac6007
```

## Route boundary

DirInfo kind 174 has five rows:

| Row | Ordered events | Disposition |
|---:|---|---|
| 0 | 001 → 002 → 003 → 004 | finite clean-story candidate |
| 1 | 001 → 005 → 006 → 004 | finite clean-story candidate |
| 2 | 001 → 002 → 003 → 007 | gameplay/effect collection |
| 3 | 001 → 005 → 006 → 008 | gameplay/effect collection |
| 4 | 009 → 010 | gameplay/effect collection |

Events 007–010 are component-only 320x256/512x416 content. Rows 2–4 are not
silently dropped: they are explicitly assigned to the gameplay/effect
collection and are not clean-story products.

## Entry composition

The parent interval evidence for `ac6007_001` has two Z2D branches. The lower
branch starts with a 36-frame scene and continues under the title. The upper
title branch starts at 1.200 seconds and is opaque:

```text
0.000–1.200  ac6007_lev_c001_MR       36 frames
1.200–3.767  ac6007_AT_kuma_title     77 frames
3.767–6.767  ac6007_AT_kuma_title_LP  90 frames
```

`ac6007_lev_c002` and `_LP` are bound and validated as the lower underlay but
are not linearly appended after the title. The missing
`ac6007_AT_kuma_title_add` and `_add_LP` layers are explicitly excluded as
title effects. This clean omission is the reason the exact outputs still need
owner playback.

Two direct-parent scene-SE requests begin at event-global zero:

| Request | Sound code | Duration | Source SHA-256 |
|---:|---:|---:|---|
| 1034 | 4010 | 10.000 s | `F7F1F56DBF6A4ADF00C861EC2C2A0DE96E15F55A5CE43CDF0E75954712496401` |
| 2192 | 10000 | 7.566 s | `9E2EF4B82A6B06CCC7A6BEDD137FA8EBE5FF24D5951467E9C351DE24F14435B8` |

Both are mixed on the complete route timeline so their tails can cross the
6.767-second entry boundary. Source events 002–006 are extracted from the
hash-bound v24 family master. The owner's approval of the uploaded P19 ZH
source confirms only that exact source file; it is not inherited by the new
route outputs.

## Outputs and review

Each row has none, JA, and ZH editions:

```text
routes\dirinfo-row-000\video\ac6007__dirinfo-row-000__none.mp4
routes\dirinfo-row-000\video\ac6007__dirinfo-row-000__ja.mp4
routes\dirinfo-row-000\video\ac6007__dirinfo-row-000__zh.mp4
routes\dirinfo-row-001\video\ac6007__dirinfo-row-001__none.mp4
routes\dirinfo-row-001\video\ac6007__dirinfo-row-001__ja.mp4
routes\dirinfo-row-001\video\ac6007__dirinfo-row-001__zh.mp4
```

Automated QA confirms native 416x232, 30 fps, H.264/AAC 48 kHz stereo, no
upscale, exact frame/sample grids, subtitle round-trip, and sibling-edition
audio packet/decoded-PCM identity. Review focus:

1. entry 0–10 seconds;
2. title replacement at 1.200 seconds;
3. entry-to-branch boundary at 6.767 seconds;
4. full-route mouth/voice/subtitle/scene-SE presentation.

```text
BATCH_MANIFEST.json
16C639C62688AE3570FB01EFE48E39861B64E87E3692DB213B6C9676B0E8380E

AUTOMATED_QA.json
D9149F5CCDA81B55358CC303315067E2123191DAA4DE460CF5D39A405D7EDBDB
```

All six exact outputs remain `human_playback_required` and must not be
uploaded yet.

## Ledger and upload guide

The exhaustive ledger is now:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v3_20260726
```

It records 173 produced audience events, 53 produced DirInfo routes, 23
current production manifests, and one explicitly excluded superseded audit
manifest. P16/P17/P18 quarantine overrides all other states.

The required per-file upload guide is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v34_20260726
```

It contains target BV/track, absolute folder, exact filename, SHA-256,
suggested part name, append/replace action, automated QA, human approval, and
explicit exclusions for every item. Counts are 10 already uploaded, 13
ready-to-upload, 138 human-playback-required, and 7 exclusion scopes. All six
new ac6007 files are in the human-playback-required group.
