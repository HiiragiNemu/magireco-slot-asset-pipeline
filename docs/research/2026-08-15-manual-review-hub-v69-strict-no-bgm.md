# Manual review hub v69 strict-no-BGM integration (2026-08-15)

## Current human entry point

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v1\CURRENT.json
```

`CURRENT.json` now selects the immutable release:

```text
authoritative_inventory_v1_plus_v69_strict_no_bgm_20260815
```

The release contains 407 semantic inventory items.  Exactly 127 canonical MP4
files are exposed under `REVIEW_READY`; 223 items remain `NEEDS_DECISION` and
57 remain `EXCLUDED_REFERENCE`.  `AUTO_QA_PASS` is not human playback approval.

## Integrated corrections

The release adds nine runtime-exact strict-no-BGM candidates:

- ac0911 DirInfo row 006: none / JA / ZH;
- ac7205_016: none / JA / ZH;
- ac1103_013 bounded 18-second event: none / JA / ZH.

Six ac0911/ac7205 products directly replace the corresponding versions that
contained an IDA-proven BGM-bus request.  The old files remain preserved and
indexed as `NEEDS_DECISION`.

The ac1103_013 event is only a bounded playback candidate.  It does not replace
the owner-approved full ac1103 chapter, and the full chapter's exact-file human
approval remains recorded.  Its strict-no-BGM admission stays withdrawn until
the full chapter is rebuilt without request 229 / sound 554.

All nine new candidates still require owner playback and must not be uploaded
until approved.  P16/ac6003, P17/ac6004, P18/ac6005 and child-local-only timing
products remain fail-closed.

## Reproduce

From the repository root on `codex/corrected-runtime-pipeline`:

```powershell
python tools\frida_runtime_probe\build_manual_review_hub.py `
  --plan tools\frida_runtime_probe\series_proposals\manual_review_hub_v1_strict_no_bgm_replacements_20260815.json `
  --dry-run

python tools\frida_runtime_probe\build_manual_review_hub.py `
  --plan tools\frida_runtime_probe\series_proposals\manual_review_hub_v1_strict_no_bgm_replacements_20260815.json
```

The builder verifies every inventory source, publishes same-volume NTFS
hardlinks through staging, validates every destination, atomically advances
`CURRENT.json`, and includes a pointer-only rollback script.  It never moves,
deletes, transcodes or upscales source media.

## Human playback focus

Review the nine new files under these directories:

```text
REVIEW_READY\routes\ac0911\{none,ja,zh}
REVIEW_READY\routes\ac7205\{none,ja,zh}
REVIEW_READY\gameplay_effect\ac1103\{none,ja,zh}
```

For ac0911, inspect the full 37.933-second route and especially 20.933-37.933.
For ac7205_016, inspect the full 9.567 seconds and especially after 3.371.
For ac1103_013, inspect the full 18 seconds, especially 5.486-7.290 and from
13.333 to the end.
