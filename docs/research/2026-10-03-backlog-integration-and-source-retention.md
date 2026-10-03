# 2026-10-03 Backlog integration and source retention

## Scope and decision

The owner requested integration of the 112 pending files, not another backup
or a production batch. Baseline: `a58b43f4e5772186f40accf77ec03dbb836702b6`
on `codex/corrected-runtime-pipeline`. No new branch, PR, device operation,
render, media copy, backup archive, or human-approval promotion is involved.

All 112 files have a useful retained role: 9 implementations, 8 test files,
6 reconciled/historical documents, 63 exact-source material plans and 26
checkpoint plans. The per-file disposition is
`2026-10-03-backlog-disposition.json` beside this document. Historical plans
remain evidence and reconstruction inputs; committing them does not make
them CURRENT, authorize replay, or certify their media for upload.

## Integration repairs

- Preserve one silent `material` file without `__none`; retain exact U144/U145
  owner decisions. Require human approval before `ready_to_upload` or
  `already_uploaded`; use the computed batch in the legacy replay layout too.
- Identical JA/ZH alone does not prove absence of subtitles. Require a matching
  NONE baseline for that label; byte identity does not prove absence of dialogue.
- Drop an uncalled upload-guide ingestion draft whose expected summary status
  did not match the actual material builder; retain tested exact-item overrides.
- Keep ac4903_015's missing layered-component blocker, strict SOUND_DIVIDE_TBL
  exclusions, resolved parent/child timing checks, and exact merged-voice cues.
  Add regression coverage for malformed or unproven merged requests.
- Require an explicit ADB-verified PID in `event_scene_host.py`, never enumerate
  processes as fallback, and default to no explicit unload. Tests are offline;
  no live attach or runtime equivalence is claimed. Legacy dual-host capture
  wrappers are not a supported single-session workflow and were not invoked.
- Replace obsolete top-level August "current" claims with the actual D: working
  tree and the later native416 pointer. Mark the old coordination protocol and
  v59 material upload list historical; do not revive their tasks or timers.

## Exact-source replay and line endings

89 pending JSON files parsed. 678 small metadata bindings were checked using
180 unique source reads. Five old v60/v60r1/v61/v62/v63 plans referenced a live
guide that was subsequently rewritten. The original expected SHA-256 was
`1B4B99447E4C24BB96E8E111D6192681AD53B305A1166C6316E953AF6F737A67`;
the rewritten file is `6EA70F468742D8D7C3B0D17763E0CB800EF5D6FA420F96BB670E625BD95FCAD9`.

Each old package already contains an exact original
`manifests/SOURCE_GLOBAL_UPLOAD_GUIDE_V59R2.json`. Rebind those five plans to
their existing snapshots, leaving expected hashes unchanged and recording
the historical live path. No source was copied, and no changed content was
accepted by replacing its expected hash. Original failed observations and
resolutions are retained in the local binding audit; unresolved bindings: 0.

64 historical JSON inputs in this backlog are themselves hash-bound and use
CRLF. Exact per-path `.gitattributes` entries prevent Git's normal LF conversion
from silently invalidating those hashes. All other paths retain the existing
attributes. The staged Git blobs are checked against the bound source bytes.

## Old primary directory: source, not current production

Location:
`D:\magia\MyProducts\casino\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==`

The old `main` branch name has been removed; this retained checkout is detached
at `50e4f5d5a4d9541f7b405960137e3530c4dd4f33`. Its `.git` is the **shared Git
common directory of the current worktree**. Deleting that directory would break
the active repository. Age of the checkout is not age of every data source.

| Retained content | Observed logical size | Present role |
| --- | ---: | --- |
| downloaded_assets: official OBB plus extracted CRI | 12,316,704,146 bytes | Original inputs still referenced by modern extraction/research; packed/unpacked is not duplicate audience video |
| split_InstallTimePack.apk | 742,410,022 bytes | Official source container |
| unpacked_assets | 742,396,261 bytes | OGG/DGI/GDB and other source tables |
| unpacked_lib | 83,635,557 bytes | Includes exact libGameProc.so used by code-level sound-bus evidence |
| asset_manifests | 36,932,699 bytes | Historical indexes/source mappings; old heuristic conclusions are not current authority |
| final_mp4_videos | 2,947,672 bytes | 21 preliminary fragments/candidate outputs, not modern longform or approved upload sources |
| _research | 456,218,539 bytes | Separate gacha/Totentanz/remote inventory research; ownership and uniqueness not established by this Slot integration |

These files are physically local on D:, not merely names on GitHub. Large raw
inputs/media and generated source indexes are excluded by `.gitignore`; neither
the retained old main tree nor the current baseline tree tracks MP4/OBB/APK/BIN/
SO/USM/OGG files. The uploaded repository contains code, tests, small manifests
and research documentation. Do not assume GitHub can restore the local media.

The v69 plan directly names the retained `unpacked_lib/lib/arm64-v8a/libGameProc.so`.
Modern production is recorded in the corrected research root and commits such
as ac0001–ac0005, not the old `final_mp4_videos` directory. No media is deleted
or newly duplicated in this integration. Unrelated research and unproved
unique sources are not removed for cosmetic cleanliness.

## Verification and rollback boundary

Durable logs/metadata, not another backup:
`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\repository_cleanup_20261003`

- `integration-targeted-tests.txt`: focused unit tests.
- `integration-full-tests.txt`: final full regression, command `python -B -m unittest`.
- `integration-plan-binding-audit.json`: original checks and exact-snapshot repairs.
- `integration-preserved-guide-snapshots.json`: existing snapshot identities.
- `integration-source-retention.json` / `OLD_ROOT_SIZE_INVENTORY.json`: local-only source evidence and size inventory.
- `integration-final-verification.json`: final test counts, staged tree and publication evidence.

Use the commit's diff or a reviewed `git revert` on the existing branch for a
code rollback; do not reset/clean the shared tree. The five plans' previous live
bindings are explicitly recorded, but those stale live files should still fail
hash validation. This integration does not change CURRENT, raw assets, produced
MP4s, quarantine, or any human playback decision. Passing tests are not complete
game inventory coverage or human media acceptance.
