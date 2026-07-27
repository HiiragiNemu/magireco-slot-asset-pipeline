# 2026-07-27 ac8005 independent silent-gameplay checkpoint v55r2

## Scope

This checkpoint produces six independent native 416x232 gameplay or
announcement routes. They are not story chapters and are never concatenated
into a natural session.

The exact DirInfo source is kind 214:

| Row | Event | EventInfo | Code |
| ---: | --- | ---: | --- |
| 0 | ac8005_001 | 8776 | `0x6c7a50582b473179` |
| 1 | ac8005_002 | 8777 | `0x344e4d4c2b473179` |
| 2 | ac8005_003 | 8778 | `0x736673712b473179` |
| 3 | ac8005_004 | 8779 | `0x245673642b473179` |
| 4 | ac8005_005 | 8780 | `0x5976404b2b473179` |
| 13 | ac8005_014 | 8789 | `0x537576382b473179` |

Every row has selector 0, one exact event and route status `ok`.

## Exact visual and absence evidence

The six sources are single-layer, exact-duration, 416x232 H.264 video-only,
30 fps:

```text
ac8005_001  ac8005_kyo_hatten      480f  16s
  39B0EBBB1F3C3A822E3B993FDCC2C43A4D52CB4A087FFEBA343E1B0722B82907
ac8005_002  ac8005_kyo_choseiya    480f  16s
  636F3DAAD1CC94E4C635809268CAC7D721684ADD0A7302D1EC70481BA4A05E91
ac8005_003  ac8005_kyo_magichalle  480f  16s
  D00542D9B18ECC5720E961471A52380E52E8DBEC3E677AEE529CB73B49D6C25A
ac8005_004  ac8005_hat_WIN          60f   2s
  B5265790A49F241097F35AC6559FE172A32C90F8E76D5B31FBA08CEF1DD62EB8
ac8005_005  ac8005_kyo_gekiatu     480f  16s
  2A47BC2F4CCE9EB48F9067A74D507D46A940460F52975CA39F4D89243EFBA559
ac8005_014  ac8005_kyo_chance      480f  16s
  1893719CCB6C37F0F829EDDF5F0537FA955881C5C9A6E886DFEF7574A42D4FEE
```

The direct-parent audio, child-Z2D audio and subtitle catalogs contain zero
exact rows for all six events. The sources have zero SHA overlap with the
current material index. Total scope is 2,460 frames / 82 seconds.

`ac8005_012` is excluded because it has intro-plus-loop semantics not closed by
this batch. `ac8005_006`, `_017`, `_018` and `_019` are native 512x416
component-only events and are not mixed into these full-frame products.

## Production

Current manifest root:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_manifests_v55r1_ac8005_six_silent_gameplay_routes_20260727
```

`event_production_summary.json` SHA-256:

```text
55A9ED4D5C6DA78260817808C3D64DF8341A24604A28E6ACE8F0FAB1255C71B6
```

Current edition root:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v55r1_ac8005_six_silent_gameplay_routes_review_20260727
```

There are six products and 18 none/JA/ZH target files. Within each product,
the three files are legal exact-hash hardlink aliases because there is no
dialogue, subtitle or verified event audio. All media passed native 416x232,
30 fps, H.264/AAC 48 kHz stereo and no-upscale checks. `BATCH_SUMMARY.json`
SHA-256:

```text
6C560C5BEAF8ACA8DE00B992ABD528566419B75951EF1B30DAACF5636F1F0B5E
```

## Correct human-review and upload guide

The only current review package is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v55r2_ac8005_gameplay_six_routes_20260727
```

U131–U136 are under `02_REVIEW_MATERIAL\batch_001`; all 18 target files are
present, with six canonical SHA values and six NTFS file IDs. There are zero
story-queue media, zero upload-now media and zero quarantine media. Package
summary SHA-256:

```text
256A8B44899F1D965AE2567CDFA37E764AD7C803C2400FD6F3497301AB287858
```

The target catalogs are:

- none: `新建：MagiaReco Slot 原生416玩法／告知动画 none BV`;
- JA: `新建：MagiaReco Slot 原生416玩法／告知动画 JA BV`;
- ZH: `新建：MagiaReco Slot 原生416玩法／告知动画 ZH BV`.

Suggested part names are `玩法告知动画路线N ac8005_XXX`, with `__ja` for JA
and `中文版` for ZH. Every action remains HOLD until exact-file human playback
approval.

The earlier `upload_guide_v55r1_20260727` and
`bilibili_incremental_review_v55r1_ac8005_six_routes_20260727` incorrectly
classified these files as story targets. They are superseded audit-only roots
and must not be uploaded. Media itself was not renamed, overwritten or deleted.

## Ledger

`production_ledger_v23_20260727` is current:

- produced audience events: 195;
- material-covered audience events: 603;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

Its `SUMMARY.json` SHA-256 is
`0B40B3B9BAA259D80A27D60CFE40CDD6A3F32F9D49B019A2D7B9C96CF5326192`.

The current guide is `upload_guide_v55r2_20260727`: 10 already uploaded,
17 ready to upload, 311 human-playback-required and 8 excluded exact files,
338 total. `UPLOAD_GUIDE.json` SHA-256:

```text
54024E1AAB22F4DDD427B1F4E9151C4901A6E7ADED2F82BB77C33BEFF8D3D428
```

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. Formal with-BGM
candidates remain zero.

Final repository regression: `python -m unittest` — 472 passed, 4 skipped.
