# Manual review hub v1 (2026-08-13)

## Purpose

`manual_review_hub_v1` is the single durable entry point for human playback of
all media currently represented by the authoritative production inventory.  It
does not move, delete, transcode, or upscale source media.  Review files on D:
are NTFS hardlinks to the exact source bytes.

Current local entry point:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v1\CURRENT.json
```

The current immutable release is:

```text
authoritative_inventory_v1_plus_v68_reverified_20260813
```

## Current gate result

| Disposition | Count | Physical review files |
| --- | ---: | ---: |
| `REVIEW_READY` | 118 | 118 |
| `NEEDS_DECISION` | 223 | 0 |
| `EXCLUDED_REFERENCE` | 57 | 0 |
| Total semantic inventory | 398 | 118 |

`REVIEW_READY` means eligible for owner playback.  It is not human approval,
publication approval, or evidence that the file has been uploaded.

The release reopens and hashes all 398 source MP4 files, checks their ffprobe
contract, and then reopens, hashes, probes, and verifies the hardlink identity
of all 118 canonical review files.  Same-hash aliases remain in the index but
are not repeated for playback.

## Cumulative evidence gates

The builder applies these gates in order and binds every input by SHA-256:

1. authoritative inventory and proposed hub mapping;
2. additive v68 inventory and explicit v35 supersession records;
3. IDA parent/child timing applicability audit;
4. IDA `SOUND_DIVIDE_TBL` volume-bus audit.

The last gate demotes seven previously eligible products to
`NEEDS_DECISION`: three ac0911 row-006 editions, three ac7205_016 editions,
and the exact owner-approved ac1103 Chinese file.  The ac1103 perceptual
approval is preserved; only its strict `no_bgm` admission is withdrawn.  No
source media is removed.

The older local release `authoritative_inventory_v1_plus_v68_20260810` is kept
as immutable provenance but is superseded by `CURRENT.json` because it predates
this sound-bus gate.

## Reproduce

From the repository root on `codex/corrected-runtime-pipeline`:

```powershell
python tools\frida_runtime_probe\build_manual_review_hub.py `
  --plan tools\frida_runtime_probe\series_proposals\manual_review_hub_v1_authoritative_inventory_20260806.json `
  --dry-run

python tools\frida_runtime_probe\build_manual_review_hub.py `
  --plan tools\frida_runtime_probe\series_proposals\manual_review_hub_v1_authoritative_inventory_20260806.json
```

The first command performs the full input/hash/media gate without writing.  The
second stages a complete immutable release, validates it, atomically promotes
the directory, and finally replaces the `CURRENT.json` pointer.  `READY` is
created only after automated verification and explicitly records
`HUMAN_PLAYBACK_APPROVED=false`.

## Audit and rollback

Each release contains:

```text
00_START_HERE.md
review_index.json
review_index.csv
NEEDS_DECISION.json
EXCLUDED_REFERENCE.json
SOURCE_BINDINGS.json
VERIFICATION_RECORD.json
SHA256SUMS.json
READY
_rollback\ROLLBACK.ps1
```

The rollback changes only the `CURRENT.json` pointer to its predecessor; it
does not delete either release or any source media.  P16/ac6003, P17/ac6004,
P18/ac6005, child-local-only timing products, and unresolved with-BGM media
remain outside the primary review directory.
