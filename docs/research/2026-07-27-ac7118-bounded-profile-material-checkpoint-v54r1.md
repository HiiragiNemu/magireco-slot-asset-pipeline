# 2026-07-27 ac7118 bounded profile-material checkpoint v54r1

## Scope

This checkpoint adds one finite native 416x232 no-BGM review product for
`ac7118_001`. It is a profile-material presentation, not a natural game
session. The immutable freeze handoff remains unchanged.

The exact DirInfo identity is kind 194, row 0, EventInfo 8292, code
`0x4d667a4b374d4554`, containing only `ac7118_001`. The two exact visual
sources in the current audience catalog are:

- `ac7118_at_ch_profile_iro_IN`: 100 frames / 3.333 seconds, SHA-256
  `738DB3B86BFB632A1B70C6A87FC54773762656F582C5DE8ABE1F150E534F77A4`;
- `ac7118_at_ch_profile_iro_LP`: 600 frames / 20 seconds,
  `orphan_loop_cycle`, SHA-256
  `82831D8E30BC52AA08A83D656C15440EE29513AA9AE5991D8292477A70D1DD11`.

The direct-parent audio, child-Z2D audio and subtitle catalogs have zero exact
rows for this event. Every catalog and media source is hash-bound.

## Bounded product contract

The current manifest root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  production_manifests_v54r1_ac7118_profile_bounded_silent_20260727
```

The product contains the complete 100-frame intro followed by exactly one
complete 600-frame source loop. Its manifest and series proposal explicitly
record:

```text
product_scope =
  profile_material_intro_plus_one_complete_source_loop_not_natural_session
natural_session_claimed = false
runtime_loop_count_claimed = false
```

Therefore 700 frames / 23.333 seconds is a finite review scope only. It is not
evidence for the game's runtime loop count, user dwell time or natural session
duration.

Important hashes:

```text
event_production_summary.json
DDDA4E1B4253AF7A137523255ED789538BCD03CBF0688410F4DB7D9B549505AE

events\ac7118_001.json
D3F3BC944CC17B1523634C8F403F75AABADAE82C4D21252B9612E35E028619CC
```

Two earlier v54 trial manifest roots and one trial edition root were created
while the boolean/loop-scope propagation was being tested. They are not listed
in the current ledger, guide or review plan. They are superseded audit-only
roots and must never be uploaded. The only current name contains `v54r1`.

## no-BGM editions and review handoff

The current edition root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v54r1_ac7118_profile_bounded_review_20260727
```

All three target files passed automated media QA: native 416x232, 30 fps,
H.264, AAC 48 kHz stereo, no upscale. Because there is no dialogue, subtitle or
verified event audio, none/JA/ZH are legal hardlink aliases with one exact
SHA-256:

```text
EE8D2BAAFB1C58D8EAE4A24337D6F41AE69D45C800F56F035A038FC0973ADC40
```

The family manifest SHA-256 is
`4382B43FEE9C37ECED22617F00023022DF24F05C5BE4D9A1E86FA8B44570E16B`.
Automatic QA does not grant human approval.

The review root is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_incremental_review_v54r1_ac7118_profile_bounded_20260727
```

U130 contains three target entry names, one canonical SHA and one NTFS file ID.
It has zero upload-now files and zero quarantine media. Review the transition
from the intro into the loop and the one complete loop boundary; do not judge
it as a natural runtime dwell duration. Package summary SHA-256:

```text
3ED4BE2B4A0B16B91011B12A4DF5C07BD5A85A11AAB883945183C88F68C7C568
```

Upload guide:

- none target: `BV1rUKN6iEcj`, suggested part
  `环彩羽角色资料动画 ac7118_001`;
- JA target: `BV1zQKN6eEC6`, suggested part
  `环彩羽角色资料动画 ac7118_001__ja`;
- ZH target: `BV13bKN6nEsd`, suggested part
  `环彩羽角色资料动画 ac7118_001 中文版`.

All three actions are HOLD until exact-file owner playback approval.

## Ledger and global guide

`production_ledger_v22_20260727` is current:

- produced audience events: 189;
- material-covered audience events: 603;
- produced DirInfo routes: 79;
- child-local timing blockers: 330;
- quarantined audience events: 53.

Its `SUMMARY.json` SHA-256 is
`EDAF2B392A55AEF379C1F34B4B9DA4F41C9BB53647FC8C658FF558F110BBB8CF`.

`upload_guide_v54r1_20260727` contains 10 already-uploaded exact files, 17 exact
files currently allowed for upload, 293 human-playback-required files and
8 exclusions, 320 exact files total. `UPLOAD_GUIDE.json` SHA-256:

```text
804532EB5E34F00C1CCB6F6DB40CCA8E5E188F21D75E07509A92E51F24438BCF
```

P16/ac6003, P17/ac6004 and P18/ac6005 remain hard-quarantined. Formal with-BGM
candidates remain zero; no-BGM inventory work continues.

Final repository regression: `python -m unittest` — 472 passed, 4 skipped.
