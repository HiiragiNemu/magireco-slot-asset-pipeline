# 2026-07-26 P11/ac0911 mature-route checkpoint v35

## Outcome

This checkpoint expands P11/ac0911 into nine independent native 416x232
DirInfo route products and one edited route-chapter showcase. Every product
has none, JA, and ZH editions: 10 content products and 30 final MP4 files.

The source P11 ZH file is exact-hash owner-approved and already uploaded. It
remains read-only. That approval is recorded only as source playback evidence
and is not inherited by any new route or showcase file. P16/ac6003,
P17/ac6004, and P18/ac6005 remain in hard quarantine. Codex did not upload.

## Route partition

DirInfo kind 36 contains 14 rows. Nine are fully represented in the current
hash-bound source family:

```text
row 0:  001 → 002 → 003
row 1:  001 → 002 → 004
row 2:  001 → 002 → 005
row 3:  001 → 002 → 009
row 4:  001 → 002 → 017
row 5:  001 → 002 → 010
row 6:  001 → 002 → 011
row 7:  001 → 002 → 012
row 9:  001 → 006 → 008
```

Five rows are fail-closed blockers:

| Row | Missing endpoint | Blocker |
|---:|---|---|
| 8 | ac0911_007 | lacks a current modern event manifest and is absent from the source family |
| 10 | ac0911_013 | absent from current audience catalog and source family |
| 11 | ac0911_016 | absent from current audience catalog and source family |
| 12 | ac0911_014 | absent from current audience catalog and source family |
| 13 | ac0911_015 | absent from current audience catalog and source family |

The plan exhaustively partitions every DirInfo row into either a rendered
route or an explicit blocker. No missing endpoint is guessed.

## Products

The durable root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v35_ac0911_mature_routes_20260726\ac0911
```

The nine route segments remain separate. A tenth product concatenates the
nine mutually exclusive routes as chapters and is explicitly labelled:

```text
edited_route_chapter_showcase_not_single_native_session
```

It is a browsing/catalog product, not a claim about one natural game session.
All files preserve the current source-family no-BGM audio: BGM is
intentionally excluded while verified voice and scene SE remain.

Automated QA confirms:

- 9/9 requested routes completed with zero failure;
- exact DirInfo rows and an exhaustive rendered/excluded partition;
- hash-bound source family masters;
- native 416x232 at 30/1 fps with no upscale;
- H.264 video and AAC 48 kHz stereo;
- exact frame/sample grids and subtitle round-trip;
- packet-identical and decoded-PCM-identical audio across none/JA/ZH for each
  product;
- the already uploaded P11 source file was not modified.

```text
BATCH_MANIFEST.json
86136C5611B3169D830C22A103057DEA46E7A03AB54D49D719C925F5D2DFC31F

AUTOMATED_QA.json
7B635566FB268C6D68C1D3676F09EA1B10DFA240C0EFEC0EE031CAD6C653FFDD
```

All 30 exact outputs remain `human_playback_required`.

## Ledger and upload guide

The current exhaustive ledger is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_ledger_v4_20260726
```

It now records 24 current manifests, 173 produced audience events, and 62
produced DirInfo routes. The five blocked ac0911 rows are explicit exclusions,
not produced routes. The ac7210 superseded audit root remains excluded from
current production and upload.

The required per-file upload guide is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  upload_guide_v35_20260726
```

It records target BV/track, absolute folder, exact filename, SHA-256,
suggested part name, append/replace action, automated QA, human approval, and
explicit exclusions. Counts:

- 10 exact files already uploaded; never repeat;
- 13 exact files currently allowed for upload;
- 168 exact files requiring owner playback;
- 8 explicit exclusion scopes;
- 191 exact files total.

All 30 new ac0911 files are in the human-playback-required group.
