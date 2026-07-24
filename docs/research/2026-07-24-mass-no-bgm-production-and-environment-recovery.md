# 2026-07-24 no-BGM expansion and environment recovery

This is the durable checkpoint after the Windows reinstall, restoration of the
production toolchain, the owner's first two Bilibili publications, and the
first v24/v25 mass-production batches. It records automated production facts;
it does not convert unreviewed outputs into owner-approved publications.

## Owner publication and naming evidence

The owner has published the earlier reviewed material in three multi-part
Bilibili videos and manually classified and named their parts:

- `BV13bKN6nEsd`, `no_bgm_zh`:
  [魔法纪录 街机版 动画整合 无BGM中文版｜游戏资源解包与技术还原](https://www.bilibili.com/video/BV13bKN6nEsd/)
- `BV1zQKN6eEC6`, `no_bgm_ja`:
  [魔法纪录 街机版 动画整合 无BGM原始日文官方字幕版｜游戏资源解包与技术还原](https://www.bilibili.com/video/BV1zQKN6eEC6/)
- `BV1rUKN6iEcj`, `no_bgm_none`:
  [魔法纪录 街机版 动画整合 无BGM无字幕版｜游戏资源解包与技术还原](https://www.bilibili.com/video/BV1rUKN6iEcj/)

These titles were read from the owner's logged-in Bilibili creator center and
already-open Chrome pages on
2026-07-24. Future upload preparation may reuse this edition-level title style
and the owner's per-part classification/naming style. The three publications do
not prove human playback approval of any newly rendered v24/v25 family and do
not authorize inventing a public-facing story name from an `ac` identifier.

The exact owner expansion authorization and the two BVIDs are also preserved in:

```text
tools/frida_runtime_probe/owner_attestations/
  mass_no_bgm_and_bilibili_followup_authorization_20260724.json
```

Current production order remains:

1. finish evidence-bound `no_bgm_none`, `no_bgm_ja`, and `no_bgm_zh`;
2. expand natural story coverage without waiting for one-family review stops;
3. start the already-authorized JA/ZH bilingual edition after Chinese coverage;
4. keep `with_bgm` blocked until the inherited BGM identity, entry phase,
   volume, fade/duck, replacement, and stop timeline are closed.

## Restored Windows toolchain

The post-reinstall machine was checked directly on 2026-07-24.

Already present:

| Tool | Live version |
| --- | --- |
| Python | 3.14.6 |
| Git for Windows | 2.55.0.windows.3 |
| GitHub CLI | 2.96.0 |

Restored for this production run:

| Tool | Live version or result |
| --- | --- |
| FFmpeg full build | 8.1.2, with `ffmpeg`, `ffprobe`, and `ffplay` under the WinGet links directory |
| Node.js LTS | 24.18.0 under `C:\Program Files\nodejs` |
| npm | 11.16.0 |
| Frida Python package | 17.16.4 |
| frida-tools | 14.10.4 |
| requests | 2.34.2 |
| tqdm | 4.69.0 |
| mitmproxy | 12.2.3 |
| fonttools | 4.63.0 |

The four optional packages in `requirements.txt` are installed and satisfy its
minimum versions. The current desktop process may need a new terminal, or an
explicit PATH prefix, before it sees newly installed Node and the WinGet FFmpeg
links. Production commands in this checkpoint used:

```text
C:\Users\proje\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe
C:\Users\proje\AppData\Local\Microsoft\WinGet\Links\ffprobe.exe
C:\Program Files\nodejs\node.exe
```

`reproducibility/toolchain.lock.json` remains the older 2026-06-19 reproducible
baseline and was not silently rewritten as part of the media run. The live
post-reinstall versions above are the authoritative environment record for this
checkpoint.

## v24 mass-production result

Durable output root:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v24_mass_20260724
```

All 11 families passed the automated family and aggregate gates:

```text
ac0911  ac4903  ac5203  ac5301  ac5303  ac6003
ac6004  ac6005  ac6007  ac7206  ac7210
```

Aggregate:

| Measure | Result |
| --- | ---: |
| Families | 11 |
| Events | 95 |
| Edition MP4 files | 33 |
| Dialogue cues / voice layers | 111 |
| Scene-SE layers | 116 |
| Total audio layers | 227 |
| Frames | 22,308 |
| Duration | 743.599 seconds |
| Native sizes | eight 416x232 families; three 512x288 families |

Every family has three independent no-BGM editions (`none`, `ja`, `zh`),
native-size H.264 at 30/1 fps, and AAC 48 kHz stereo. The aggregate audit found
no unresolved audio role, BGM layer, inserted black separator, upscale,
frame/sample mismatch, missing edition, or failed family.

### ac5203 supersession

The old artifact below is invalidated and must remain audit-only:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v23_20260718\ac5203_full_no_bgm_editions_v1
```

It omitted the reviewed `ac5203_2_001` request 7856 cue
`負けるもんか！` while importing chance-button presentation text. Passing media
stream QA did not make that edition content-complete.

The authoritative rebuild is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v24_mass_20260724\batch02_ac5203_ac6005\
  ac5203_full_no_bgm_editions_v1
```

It contains 7 events, 7 dialogue cues, 14 evidence-bound audio layers,
1,216 frames, and 40.533 seconds at native 512x288. Its no-subtitle, Japanese,
and Chinese MP4s all passed the current automated QA.

## v25 next-story result

Durable output root:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v25_next_story_20260724
```

| Family | Events | Cues | Audio layers | Frames | Duration | Native size |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `ac4902` | 46 | 46 | 98 (46 voice, 52 SE) | 20,708 | 690.267 s | 416x232 |
| `ac7117` | 11 | 32 | 43 (32 voice, 11 SE) | 4,381 | 146.033 s | 512x288 |
| `ac7112` | 14 | 45 | 59 (45 voice, 14 SE) | 5,916 | 197.200 s | 512x288 |
| `ac7113_main_512x288` | 9 | 32 | 41 (32 voice, 9 SE) | 3,948 | 131.600 s | 512x288 |
| `ac7113_opening_512x416` | 1 | 2 | 3 (2 voice, 1 SE) | 342 | 11.400 s | 512x416 |

All fifteen edition MP4s passed the same native-size H.264, 30/1 fps, AAC
48 kHz stereo, exact frame/sample, source-hash, subtitle, audio-role,
no-upscale, and no-BGM gates. The five families add 81 events, 157 dialogue
cues, 35,295 frames, and 1,176.500 seconds.

The combined v24/v25 aggregate audit is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_aggregate_audits_20260724\
  final_audit_v24_v25_strict_media_20260724_230000\aggregate_audit.json
```

It passed 16 families, 176 events, 48 edition MP4s, 268 dialogue cues,
57,603 frames, and 1,920.099 seconds. The 471 audio layers are 268 voice plus
203 scene SE, with zero unresolved audio. Native sizes are nine 416x232
families, six 512x288 families, and one 512x416 family. The strict rerun also
parsed every JA/ZH SRT and independently recalculated AAC packet identity,
packet presentation timing, exact decoded sample count, and decoded PCM
identity for every audio master and all three editions. The report SHA-256 is
`1F80589A4F3CE047CCD8A61CB4098DC97E6A422CBEE4EF4A1F2E6DD86F52DD0D`;
its CSV SHA-256 is
`7BB36A790A96149165CE41D1AA268E16922237BE9ECCB18E940D531C0E6AD0F3`.
`HUMAN_PLAYBACK_APPROVED` and Bilibili publication approval remain separate
owner decisions for these new families.

For manual owner upload, the audited media are exposed through same-volume
NTFS hard links at:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  bilibili_upload_ready_v25_no_bgm_20260724_16families
```

The `zh`, `ja`, and `none` directories are named in proposed P11-P25 order.
Corrected `ac5203` files are isolated under `replace_old_p10_ac5203` instead of
being silently appended as a second authoritative part. All 45 P11-P25 links
and three P10 replacement links (48 edition links in total) were re-hashed
against the aggregate CSV with zero differences.

## Final release-safety review

Four content-integrity gaps were closed before Git synchronization:

- same-target chapter promotion now uses a persistent OS lock and removes a
  failed destination only while its private ownership marker still matches;
- the aggregate auditor parses each JA/ZH SRT and recomputes real AAC packet,
  presentation-timeline, exact-sample, and decoded-PCM evidence;
- every series proposal binds the current event-manifest hashes and the exact
  upstream passed series manifest and ordering identity;
- the owner-authorized `環さん`/`黒江さん` Chinese relationship forms are
  loaded by default and enforced in build and QA rather than remaining a
  documentation-only convention.

The final repository regression passed 354 tests with 5 unrelated skips and
zero failures/errors. The real FFmpeg integration test ran, all 219 JSON files
parsed, 21 tracked JavaScript files passed `node --check`, `compileall` passed,
and `git diff --check` reported no whitespace error.

## Fail-closed families not counted as production

The expansion did not force every candidate into a linear story video:

- `ac4901` remains excluded from clean-story production. Its old v18 promotion
  contains repeated short near-identical variants and voice/subtitle cues not
  supported by visible speaking animation. It needs a new evidence-bound
  natural grouping and audiovisual review.
- `ac7204` remains a gameplay/result family with role voice, not pure material
  and not an automatically valid clean-story family. Its story, result, and
  effect variants still need an evidence-bound split before either story or
  material publication.
- `ac1101` remains fail-closed because four of thirteen registered events lack
  accepted production manifests, alternative title/result branches collide,
  `ac1101_002` voice timing is unresolved, and the mixed win/recovery events
  still lack accepted composition plans. A nine-event linear subset would
  normalize an incomplete and semantically false route.

These failures demonstrate the intended policy: mass production expands only
families whose composition, dialogue, voice/SE roles, and event order are
already closed. A family count is never increased by visual similarity or
filename order alone.

## Current boundary

The no-BGM lane is now proven at mass-production scale across linear and mixed
native sizes, and may continue independently. It means “verified original
voice and scene SE, BGM intentionally excluded”; it does not mean “the game had
no BGM.”

The with-BGM archive lane remains open. The static 835/836 BGM mechanism and
cross-thread playback identity are known, but target-family inherited track,
entry phase, volume, transition, and stop evidence are not closed generally.
No v24/v25 output in this checkpoint claims a complete original-game BGM mix.
