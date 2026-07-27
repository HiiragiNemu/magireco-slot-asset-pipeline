# MagiaReco animation recovery handoff for the next AI

Original date: 2026-06-28
Current checkpoint: 2026-07-24

Current production delta (2026-07-27):

```text
docs/research/2026-07-27-ac7211-split-native-component-checkpoint-v56.md
```

The owner lifted the production freeze.  Continue from
`production_ledger_v24_20260727`; keep the old freeze package immutable.
The current upload guide is `upload_guide_v56_20260727`.
P16/P17/P18 and unresolved child-local timing remain fail-closed.  Formal
with-BGM production still has zero ready candidates and starts only after the
discovered no-BGM inventory is produced or precisely blocked.

The v56 delta closes the currently resolved ac7211 component inventory as
three separate native visual-only products: 416x232, 512x288 and 192x320.
Use U137/U138/U139 for playback review.  Do not cross-compose those dimensions
or describe the catalogs as complete events or natural sessions.
`ac7211_002–004` and `_016–018` remain unresolved and excluded.

The newest transfer delta is:

```text
docs/HANDOFF_CODEX_2026-07-25.md
```

It records the project owner's latest playback corrections, especially the
three distinct identities Black Feather / Kuro / Kuroe, the P16 audio-lead
review boundary, the missing P18 second half, and the audience-route duplicate
gate. Read that file before using any older `kuro` mapping or expanding v25.

This is the core handoff document for continuing the project.  Treat it as the
first file to read before touching any renders, manifests, probes, or GitHub
state.

The highest-priority delta is:

```text
docs/research/2026-07-24-mass-no-bgm-production-and-environment-recovery.md
```

The owner has published the earlier approved material as three manually named,
multi-part Bilibili editions:

```text
BV13bKN6nEsd  no_bgm_zh
魔法纪录 街机版 动画整合 无BGM中文版｜游戏资源解包与技术还原

BV1zQKN6eEC6  no_bgm_ja
魔法纪录 街机版 动画整合 无BGM原始日文官方字幕版｜游戏资源解包与技术还原

BV1rUKN6iEcj  no_bgm_none
魔法纪录 街机版 动画整合 无BGM无字幕版｜游戏资源解包与技术还原
```

Reuse the owner's edition-title and per-part classification/naming style during
future upload preparation. Do not invent a human story title from an `ac`
identifier, and do not treat these three publications as playback approval for
newly rendered families.

After the Windows reinstall, the live production environment is restored:
Python 3.14.6, Git 2.55.0.windows.3, GitHub CLI 2.96.0, FFmpeg 8.1.2,
Node.js LTS 24.18.0, npm 11.16.0, Frida 17.16.4, frida-tools 14.10.4, and all
`requirements.txt` packages. FFmpeg/ffprobe are in the WinGet links directory;
Node is under `C:\Program Files\nodejs`. A terminal inherited before installation
may require an explicit PATH prefix or restart.

The current durable no-BGM expansion is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v24_mass_20260724
```

v24 passed 11 families, 95 events, 111 dialogue cues, 116 scene-SE layers,
22,308 frames, 743.599 seconds, and 33 none/JA/ZH MP4s. The families are
`ac0911/ac4903/ac5203/ac5301/ac5303/ac6003/ac6004/ac6005/ac6007/ac7206/ac7210`.
All retain native 416x232 or 512x288, 30/1 fps H.264, and AAC 48 kHz stereo,
with no inserted black frame, upscale, BGM layer, or unresolved audio role.

The next-story expansion is:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_editions_v25_next_story_20260724
```

- `ac4902`: 46 events, 46 cues, 690.267 seconds, 416x232;
- `ac7117`: 11 events, 32 cues, 146.033 seconds, 512x288;
- `ac7112`: 14 events, 45 cues, 197.200 seconds, 512x288.
- `ac7113_main_512x288`: 9 events, 32 cues, 131.600 seconds,
  native 512x288;
- `ac7113_opening_512x416`: 1 event, 2 cues, 11.400 seconds,
  native 512x416 and intentionally preserved separately.

All fifteen v25 MP4s passed the same exact source/frame/sample/subtitle/audio-role
gates. The combined authoritative audit passed 16 families, 176 events, 48
edition MP4s, 268 dialogue cues, and 1,920.099 seconds:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\
  no_bgm_aggregate_audits_20260724\
  final_audit_v24_v25_strict_media_20260724_230000\aggregate_audit.json
```

This strict rerun parses every JA/ZH SRT and independently recalculates AAC
packet identity, packet presentation timing, exact decoded sample count, and
decoded PCM identity for each audio master and all three edition MP4s.

The old v23 `ac5203` artifact is invalid because it omitted request 7856
(`負けるもんか！`) and imported chance-button presentation text. The v24
`batch02_ac5203_ac6005` rebuild carries the reviewed `ac5203_2_001` cue and is
the only current ac5203 production edition.

Do not force unresolved inventory into the production count. `ac4901` remains
invalidated for repeated short variants and unproven visible speaking;
`ac7204` remains gameplay/result with role voice pending a story/result/effect
split; `ac1101` remains blocked by missing manifests, branch collisions,
unresolved voice timing, and unclosed mixed win/recovery compositions.

The no-BGM none/JA/ZH lane is independently authorized for continued
production. The with-BGM lane is still unclosed and none of the v24/v25 outputs
claims a complete original-game BGM mix.

The final correctness review closed four additional release hazards:
same-target concurrent promotion now uses an OS lock and owned-only rollback;
the aggregate auditor independently parses SRT and recomputes AAC/PCM evidence;
series proposals bind the current event and upstream-series hashes; and the
owner's `環さん`/`黒江さん` Chinese relationship forms are enforced during
build and QA. The current full repository regression is 354 passed, 5 skipped,
and 0 failed/errors with the real FFmpeg integration enabled.

The previous 2026-07-18 expansion delta is:

```text
docs/research/2026-07-18-mixed-composition-expansion-review-batch.md
```

The owner has now played and approved all three complete Story 3/4/5 chapters,
and explicitly authorized full production while asking for prompt coverage
beyond single-full-frame linear SP Story. The exact statement and the three
approved artifact sets are hash-bound in
`tools/frida_runtime_probe/owner_attestations/sp_story_3_5_full_chapters_owner_playback_20260718.json`.

The first mixed-composition checkpoint was built on durable D:
`ac1102`, `ac1103`, `ac1104`, and `ac5208`, totaling 40 events, 99 voice-bound
Chinese cues, 175 audio layers, and 315.067 seconds. It includes 21 linear and
19 `timed_full_frame_layers` events, multiple ordered clips, loop backgrounds,
screen/loop overlays, and both 416x232 and 512x288 native media. All four passed
automated frame/sample/source/subtitle QA. The owner subsequently completed
playback and approved all four, including the 416x232 layout and overlapping
`ac5208` dialogue. The former stop instruction is historical and has been
superseded by the 2026-07-24 mass-production authorization.

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_mixed_composition_reviews_v22_20260718
```

The old six-edition atomic blocker remains overridden for the named independent
no-BGM Chinese lane. The complete two-audio by three-subtitle matrix is still
the final archive target; none of these candidates claims a complete original-
game mix.

Storage authority changed on 2026-07-16: A: RAMDISK is disabled and must not be
used for scratch, input, or output. Durable research/media belongs under
`D:\magia\MyProducts\casino`; the C: worktree and system temp are SSD-backed and
may hold repository/small temporary files. Old A: strings are provenance only
and may be resolved through an explicit, hash-verified D: prefix map; never make
new work depend on A:.

The newest BGM-research delta, including the natural SP Story hunter, exact
STOP/calcStop/setStopAngle authority, static kind lottery, current runtime
failure/reconnect point, surviving outputs, and quantified completion gap, is:

```text
docs/research/2026-07-13-natural-sp-story-hunter-and-lottery.md
```

The mandatory Sound Pack/BGM continuation delta is:

```text
docs/research/2026-07-14-sound-pack-entitlement-gate.md
docs/research/2026-07-14-sound-pack-pre-gate-runtime-volume.md
docs/research/2026-07-14-audible-bgm-observation.md
docs/research/2026-07-14-two-audio-master-six-edition-contract.md
docs/research/2026-07-15-bgm-dir-and-csl-cross-thread-identity.md
docs/research/2026-07-15-target-sp-story-bgm-state-upstream.md
docs/research/2026-07-16-paid-addon-gates-and-archive-impact.md
docs/research/2026-07-16-setting-character-force-variant-space.md
docs/research/2026-07-16-release-pipeline-hardening.md
```

It proves that the unentitled PID3125 instance still exposes the original
pre-gate volume chain.  ID826 was requested with authorized final volume 50 and
then reduced to CSL runtime volume 0 by the native gate.  Do not interpret an
unentitled instance as permission to stop the BGM track.  Use it to recover the
with-BGM mix while separately retaining a no-BGM voice/SE master.

The current read-only reconnect checkpoint is PID3188 on 2026-07-16. Its
14-field addon snapshot and exact hashes are in the paid-addon report. PID3207
is the preceding 2026-07-15 sound-chain checkpoint; its zero-input journal is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\audible_bgm_pid3207_current_probe_readonly_20260715_01\hunt_journal.jsonl
SHA-256 68ECC94DF1C3B08C5CD51EAC72636FECBDA0E2CCCF67A9A983C15D34F3585A6D
```

All 13 Sound Pack table key checks match and the initial active vector is empty.
That is probe-health evidence only.  The owner's audible-BGM confirmation
belongs to the earlier five-round PID3125 batch: ID800 had runtime volume zero,
while ID835/836 were contemporaneous non-gated transports. Static disassembly
now proves that both are generated by `C_ObjNml::fnSndRequest_BGM_DIR()` and
therefore have native BGM business semantics. They are still not uniquely tied
to the owner's listening instant: the later zero-input check began about
14m35s after the five-round journal ended, not immediately.

The target upstream observer is now live-ready on PID3188. MuMu exposes
GameProc as an uncompressed APK-backed ELF mapping, so the hunter verifies the
installed split APK hash, the fixed STORED GameProc entry hash/AArch64 header,
then the derived runtime ELF base and five export offsets. The successful
zero-input journal is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\target_bgm_upstream_pid3188_readonly_20260716_03\hunt_journal.jsonl
SHA-256 562A8F16864D6D0377CDC32E3F603338C4133A3DA37F4B5CF96D2204631C0F11
```

It has 13/13 hooks installed, no unavailable/attach/probe errors, 973 retained
sound metadata rows, zero drops and `adb_input_sent=false`. The idle upstream
window had no state change, which is expected; use this exact observer on the
next bounded natural round rather than broadening the hook set.

The first real round then correctly failed closed at the 1024-event bound: the
initial high-frequency signature included call identity and crossed object
instances. That incomplete `_04` journal is retained as failure evidence. The
signature now partitions by hook+object and excludes call ID; an executable
1000-repeat test and a second real bounded round both pass. The authoritative
real-load checkpoint is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260716\evidence\target_bgm_upstream_pid3188_execute_20260716_06\hunt_journal.jsonl
SHA-256 7D8FA6761DAD9AF55405EC845FB0CB53CB0DF62D59D7CEC4C2234E4A4C84826E
```

It is a non-target with 40 closed-window upstream rows, 141 complete sound
rows, zero drops/errors and final slot state 0/0. It does not contain
`kind=0x2f` or 835/836; use it as observer-load proof, not target BGM evidence.

The 835/836 production-mix fields are now statically closed. Both request rows
are channel 0 `PLAY`, master-volume index 1, `SMZ`, seek 0, and packed
`loop=1`; fade and duck attributes are both `NONE`, with no extra records or
request-level markers. `DecoderSmz` clears any media-embedded loop points for
this request mode and reopens the normal stream start at EOF, so each track
loops as a whole until stopped or replaced. Native volume 50 reaches libAMAIN
as int 50, becomes linear gain `0.5` with the default fade factor 100, and maps
to `-602` millibel (about -6.02 dB). If an old 835/836 player is still active,
the pair's own default replacement is `sndStop(false,false)` followed by
`sndOpen`; the rows themselves do not encode crossfade or ducking. Static
analysis cannot exclude a separate `VOL_EFCT` or duck request issued around
the same frame.

The minimal remaining target-run capture is deliberately bounded:

1. libGameProc `zgSndReqCode@0x4273058` for the `835/836` business code;
2. `PlayerImpl::performRequest@0x4282a3c`, recording x0 PlayerImpl and x2
   ReqOrder `+0x50/+0x88/+0x98/+0x9c`; inspect type 4 `VOL_EFCT`, type 9
   `SET_DUCKING`, and type 10 `RST_DUCKING` on the same player timeline;
3. `PlayerImpl::sndStop@0x4282538` and `sndOpen@0x428336c` for the actual
   replacement order and open result;
4. `DecoderSmz::reopen@0x426a64c`, reading decoder
   `+0x7f20/+0x28/+0x2c` (expected `0/0/0` for whole-media restart);
5. libAMAIN `CSLMng::SndSetVol@0x13066c` and
   `CSound::GetVolNow@0x13646c`, expecting int/fade `50/100`; optionally read
   w1 at instruction `0x1356b0` inside `CSLVolume::SetVolumeF@0x13565c`,
   expected `-602`.

Use the binary hashes and exact field proof in
`docs/research/2026-07-15-bgm-dir-and-csl-cross-thread-identity.md`; fail closed
on another build. This is the smallest capture that closes per-event code,
phase, transition, and sink-volume attribution without returning to a broad
black-box sound hook.

The hardened historical snapshot audit is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\runtime_sound_pack_snapshot_join_pid3125_hardened_20260715_01
runtime_sound_pack_audit.json
  7BD36419637B711A5C4CA051C35C289274673F944E93E6264686B2832B04D295
runtime_sound_pack_rows.csv
  3F28CDB1131A08A5EF19E6773A50FCEA9C61AC336099F733C8424F4C5D597094
runtime_sound_pack_pre_gate_volume_rows.csv
  7C01DC8CC2E14C5ABAFD1E8A5716C235D3AEB503BEEDB4C3232879EC76FBE992
```

It contains 32 active rows; all four gate rows (unique IDs 800/801/821)
are runtime-volume zero, with 4 corroborating unentitled rows, 0 conflicts and
0 invalid snapshots.  It has 0 pre-gate rows and therefore does not identify
the audible track or recover authorized volume.

The real two-profile audio base-master compositor and the modern six-edition
scene assembler now exist and have passed tiny real-media end-to-end tests. The
event compositor stream-copies H.264 into two independent AAC 48 kHz stereo
with-BGM/no-BGM masters, audits effective PCM and packet/frame PTS, rehashes
every source before promotion, rejects unknown loop/fade/game-parameter
semantics, and publishes READY last. The scene assembler does not concatenate
AAC packets: it trims each event to the sidecar's exact presentation sample
count, concatenates continuous PCM, encodes AAC once per audio profile, and
muxes that same profile master into none/JA/ZH editions. It rejects any video
packet, frame-grid, sample-count, cue, hash, or READY mismatch.

Real v20 production manifests and clean visual inputs are now built on durable
D: storage:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\production_manifests_v20_frame_grid_20260715
event_production_summary.json SHA-256 9025608499EE13760A817CF8DF630AC08EE92F539EF6C13E1E2042835C2A58B2
event_production_catalog.csv  SHA-256 6E6D7C01CD98B11704543266D7E523254CBDCE37BA9A2C21CA8FCE90AC06A927

D:\magia\MyProducts\casino\magireco_corrected_research_20260612\validation_outputs_v20_clean_visual_ac7114_16_20260715
```

The catalog contains 926 events, 521 READY and 405 fail-closed. Explicit
`--path-prefix-map` relocated lost A: provenance to its verified D: copy without
rewriting source manifests; ac7114/15/16 are READY and contain zero A: paths.
Their clean visuals passed as 512x288, 30 fps, H.264, video-only: 289, 666 and
391 frames respectively. Their audio presentation grids are 462400, 1065600
and 625600 samples at 48 kHz. These are trusted visual inputs, not finished
uploads. Target-scene BGM ID/phase/volume/transitions, reviewed Chinese cues,
and the final game-layout/font approval remain open, so no real six-edition
ac7114-16 release has been promoted.

Repository validation at this checkpoint is 289/289 passed, 0 skipped and
0 failures/errors after setting `MAGIRECO_SLOT_ASSET_ROOT` to the durable D:
asset root; this includes all four installed-asset glyph vectors. All
changed/new Python files passed `py_compile`; the current merged tree passed
`compileall`, the Frida JavaScript passed
`node --check`, and `git diff --check` reported no whitespace errors.

The final pre-push review also closed two audit hazards: modern scene summaries
are stored inside each scene directory so a later scene cannot invalidate an
older READY hash, and every parsed JA/ZH SRT cue must exactly match the audited
`edition_plan` count/time/text before concatenation. Combined SRT files are
round-trip parsed after writing. Frame-to-audio sample calculation now uses the
declared rational frame rate rather than a 30-fps-only constant and is checked
against the source event manifest and both audio sidecars.

The final fault-injection pass also closed publication-transaction hazards:
modern series uses sidecar-bound PCM trim/concat and one AAC encode per profile;
scene, subtitle batch, series and material collection complete all post-build
hash/READY checks in same-volume staging and preserve the previous READY tree
even when a post-promotion verification is fault-injected; event audio promotion uses a
cross-process mutex plus no-replace/inode-safe rollback. Material routing now
requires hash-bound human visual semantics and evidence-bound trim/gain/duck.
Every identifier-derived output component is also validated before any
identifier-derived media write or recursive operation; absolute/drive/ADS/traversal/reserved-name inputs and
resolved symlink escapes fail closed.
See `docs/research/2026-07-16-release-pipeline-hardening.md` before changing any
promotion or concat code.

The exact cross-thread runtime proof is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\natural_hunter_pid3207_cross_thread_csl_execute_20260715_03\hunt_journal.jsonl
SHA-256 42081908D49850F992AD7E58F892555505B7A964A6756C0D9947775DCFDD2E52
```

It has 130 complete sound-trace rows, no drops/errors, and eight exact
`CSLMng::SndReq` pending-row to cross-thread `PlayStart` joins. Preserve
original request, effective resource, final SSound_Data ID and OGG chunk as
separate fields. The current post-overwrite-fix read-only source checkpoint is
`audible_bgm_pid3207_cross_thread_csl_preflight_readonly_20260715_04`, journal
SHA-256 `0368D91A6C786E64EFB72F95CBB154240ED7E8096013FC25C1CE45FB19DF0143`.

After a later ARM64 Gadget reinjection, the durable summary SHA-256 is
`44F1AB99BCD728C34AAD4A4838D97D444CE9FE27EC9B6B959E53E5F978C67534`.
The subsequent zero-input preflight journal is
`audible_bgm_pid3207_cross_thread_csl_preflight_readonly_20260715_05`, SHA-256
`E7B4FF3BC2DBE30702A74D48BA2BA5E6A6459A0F9345F5F668388B3D7CCFA8E6`.
Two further bounded five-attempt batches completed without overflow, drops, or
false target promotion; all ten attempts were non-target and normal credit
ended at 19:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\natural_hunter_pid3207_cross_thread_csl_execute_20260715_06\hunt_journal.jsonl
SHA-256 6DA701E60A8CD3D5BAB25925C3DFAACC854FA3D6E139E1DB032D5855E7F2ECDE
D:\magia\MyProducts\casino\runtime_recovery_20260715\evidence\natural_hunter_pid3207_cross_thread_csl_execute_20260715_07\hunt_journal.jsonl
SHA-256 26902C0927129A1E0A7C4BBAD12F857768EA23FE56D8217A14BF41A6DA78436F
```

Do not burn the remaining credit in an unbounded search. Neither batch binds
an exact target event to 835/836, so the target BGM production gate remains
closed.

Static upstream tracing now explains why this cannot be filled from the event
number. `SdGmData+0x13da/+0x13de` is copied through
`MSTCOMCBK+0xa72/+0xa76` into `C_ObjNml+0xca/+0x11a`; when kind is `0x2f`,
Direction no `1..24` selects 835 and `>=25` selects 836. The state has several
commit/restore/clear writers, while the SP Story object's local sound methods
return without requesting BGM. DirInfo records 190/191/192 for ac7114/15/16 are
a different field and must never be used as Direction no. Capture the bounded
writer/commit/BGM_DIR/PlayerImpl chain listed in the new upstream report on the
next natural target.

The current LC701A scheduler/static-analysis delta is:

```text
docs/research/2026-07-15-lc701a-f070-native-writer.md
```

It closes the read path from VM `f070..f075` through
PC 040a/040c/040f and F7/ED31 into DirInfo3, and identifies
`CplayData::LoadData` as a persistent native writer.  The last writer during a
natural lottery remains unknown; use the report's minimal read-only
writer-change probe instead of visual inference.

静态通用性、游戏字体和 Slot CDN/官网高清路线的只读审计：

```text
docs/research/2026-07-13-static-generality-font-and-cdn.md
```

The newest owner-facing Chinese report, including the static/dynamic boundary,
two-audio-master by three-subtitle requirement, CDN/high-resolution research track, and
GitHub/CI clarification, is:

```text
docs/HUMAN_PROGRESS_REPORT_2026-07-13.md
```

The ten ac7114/15/16 Chinese cue candidates and their explicit human-review
slots are in `docs/review/2026-07-15-ac7114-16-chinese-subtitle-review.md`.
They are deliberately NOT HUMAN APPROVED. A read-only JM coverage run found
19/34 candidate codepoints covered and 15 missing. The Chinese path now pins
Noto Sans CJK 2.004 to an immutable upstream commit, exact font/license hashes
and OFL-1.1; the real pinned font covers all 34/34 candidate codepoints and can
be verified offline through `reproducibility/scripts/fetch_font_dependencies.py`.
See `reproducibility/fonts/README.md`. It is explicitly an audited non-game
Chinese font, while translation and layout remain unapproved, so do not mark
these cues release-ready or call the fallback game-native.

The paid-gate audit is now complete enough for production planning. There are
exactly seven SKUs: save, wait cut, setting, auto, forced role, a bundle for
indices 0..4, and Sound Pack. Only Sound Pack directly removes audible content;
the others alter convenience or route probability. Fixed settings 1..6 require
index 2, but the five character buttons are not purchase-gated and write
`g_CustomChara/g_CustomVoice`. No purchase callback downloads a separate media
pack. PID3188 was re-read on 2026-07-16 with all 14 active/saved fields zero and
no calls/writes/input; exact hashes are in the paid-addon report.

The complete static variant audit closes the apparent 7×5×20 brute-force
space. Free random setting UI value 6 resolves strictly to effective 0..5;
fixed setting changes ordinary Story probability descriptors, but the target
SP Story lottery does not read setting. The five UI characters are five
profiles with normal `custom_voice=0`, not a 5×5 matrix. Forced-role indices
0..19 are a separate domain from target `(stage,selector)` and produced no
target SP Story in the complete existing scan. Preserve setting/character/
force as provenance, then split editions only when event/video/voice/subtitle
canonical signatures differ. Changing an addon flag does not close the natural
target BGM inheritance gate.

When a dated report conflicts with this handoff or those deltas, use the newer
2026-07-16 statement.  Keep older dated reports as audit history rather than
deleting them.

## Objective

Recover the game's animation/video content into auditable, watchable outputs:

- preserve original media resolution, frame rate, bitrate class, audio sample
  rate, and channel layout;
- produce two synchronized audio masters: `with_bgm` (BGM + original voice/SE)
  and `no_bgm` (no BGM, same original voice/SE); derive no-subtitle, Japanese-
  subtitle, and reviewed Chinese-subtitle editions from each, for six required
  publication editions;
- keep one verified cue timeline and placement/safe-area profile for Japanese
  and Chinese, while binding each language to its own explicit font file,
  family, SHA-256, provenance and complete cmap. Japanese should use the game
  glyph path where practical; Chinese may use a different audited complete font
  and must not silently inherit the old `Yu Gothic` default;
- keep original per-event segment files;
- also produce same-scene long videos suitable for Bilibili upload when the
  scene is verified;
- keep slot/gameplay/foreground effects and pure material clips in separate
  material collections, not in normal animation uploads;
- base voice, subtitle, BGM/bed, and SE timing on game runtime evidence or
  static evidence that is directly traceable to game data;
- keep source hashes, manifests, event indexes, cumulative timelines, QA
  reports, and invalidation records.

The user does not want slot foreground/gold-frame/particle gimmicks mixed into
normal story animation.  If the game has a slot effect that should be preserved,
make a separate material/gameplay collection for it.

## Hard constraints

Do not violate these:

- Do not delete source files.
- Do not generate the old 124 GB 1080p/upscaled output.
- Do not upscale.
- Do not use the old motion/static classification as final evidence.
- Do not infer CRI indices from the numeric suffix of an `ac` event.
- Do not mix no-subtitle, Japanese-subtitle, and Chinese-subtitle editions.
- Do not publish machine-only Chinese translation or an unverified substitute
  font as the game font.
- Do not promote contact-sheet or stream/codec QA as delivery proof.
- Do not classify an event as pure material if it contains role voice, dialogue,
  or subtitle-relevant sound.
- Do not batch-render AV-blocked role-voice scenes for publication.
- Do not use the current missing Sound Pack entitlement as a reason to omit the
  required BGM master; recover pre-gate track, volume, phase, loop and ducking
  from read-only game logic/runtime evidence, without spoofing entitlement.

## 2026-07-14 family/material audit correction

The June review media survived on D: even though the old A: paths no longer
exist.  ac1102/ac1103/ac1104 v15 and the v18 aggregate are file-complete and
hash-clean (11/11, 13/13, 13/13 and 37/37 technical QA).  The v18 series
timelines are continuous and 416x232/30 fps/AAC 48 kHz stereo, but they are
**review-only**: the newest AV trust audit blocks 35/37, all 37 have zero
observed BGM requests rather than proof of BGM absence, and ac1103_006/_012/
_013 include `ac8040_shouri_EF_small[_LP]` victory effects.  Do not publish or
rename those series as clean story.

Material classification is now explicit:

- ac0906: black-matte small-Kyubey overlay material; six events, no named role
  dialogue;
- ac0912: pure gameplay/effect material; 42 excluded events represented by ten
  unique AV signatures and 24 DGM, no role voice;
- ac7204: gameplay/result animation with 27 source-manifest role-voice events,
  currently folded into 14 unique AV representatives from four unique Nemu
  OGGs; not pure material and not yet Bilibili-ready because its label SRT is
  not dialogue transcription.  Preserve the complete event-to-representative
  alias map; never deduplicate on visual path before auditing audio/subtitles.

`build_material_collection.py` must treat known role voice and unknown audio
semantics fail-closed, require formal transcript evidence, and lower incomplete
coverage to `review_only` with `release_eligible=false`.  Visual-only technical
QA is separate from audible publication: the legacy audible mixes lack native
volume/ducking and complete per-OGG hashes, so they remain review-only.  Do not
confuse this semantic gate with file loss: a 2026-07-15 read-only relocation
rehash checked 120 family source/output files with 0 missing or hash errors.
The ac0906 material collection separately checked 36 referenced files with 0
errors; its schema-v2 classification remains
`reviewed_audience_components_not_standalone_animation`, with six black-matte
small-Kyubey components and 16 audio-evidence rows. Both collections are
auditable, but neither legacy audible mix is current publishable audio. Do not
re-encode the existing hash-matched media; repair manifests/indexes and
subtitles first.  The existing top-level v18 material summary also omits ac0912
and must be rebuilt non-destructively.

Official store provenance adds a mandatory BGM caveat: the separately sold
Sound Pack unlocks main normal-play BGM and bonus music.  Installed OnDemand
SMZ data does not prove the current account entitlement, volume setting, or
native playback gate.  Record those states together with PLAY/STOP evidence
before claiming that a natural target has no BGM or before adding any external
bed.  See the 2026-07-13 static/font/CDN audit linked above.

## Authoritative working locations

Repository/worktree:

```text
C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
```

Production branch:

```text
codex/corrected-runtime-pipeline
```

The accidental `main` branch is not authoritative for this project.

Runtime/game extraction roots currently in scope:

```text
D:\magia\MyProducts\casino\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
D:\magia\MyProducts\casino
D:\MagiReco_Reverse
```

The former `C:\Users\cryne\Downloads\MagiaRe\...` game tree was moved to the
D path above and no longer exists.  The D game-root checkout is the obsolete
local `main`; use it for extracted assets/manifests, not for code changes.

Space policy:

- A: volatile RAM-disk scratch only.  It was cleared again before the
  2026-07-11 checkpoint.  Existing files may belong to the user; do not delete
  them merely to obtain space.  Never leave the only evidence copy on A:.
- C: fast P5801X scratch for many small files if A is tight.
- D: repository, durable recovery evidence, final verified long/review
  collections, and the replacement progress root
  `D:\magia\MyProducts\casino` for data that must survive another power loss.

## 2026-07-14 authoritative checkpoint - read before all older input guidance

The current foreground instance after MuMu restart is PID 3125.  Every older
PID below is dated evidence only.  Direct x86 frida-server attach correctly
failed closed because it saw `Process.arch=x64` and could not resolve the ARM64
gameplay exports; no gameplay input was sent.  Its journal SHA-256 is
`76024DABC98C089D9EC18C13D71079DAEE90E1EC405EF2D5711C29694356F887`.

ARM64 Gadget reinjection then succeeded without restarting the game.  The
summary SHA-256 is
`179E136AF6E2B5B1DC0C90691F1F625C3D48CDD46F68CAA57DE7BF2BCB653AC5`.
The subsequent read-only smoke captured all 65 declared CSL slots at both
endpoints, no truncation and no active rows; its journal SHA-256 is
`E7BA647DDFBC8B166478367B53669D7786EBE4247DB4A442AAD9C661D4A941C1`.

Three bounded natural rounds then completed in 3.934/4.013/3.898 seconds.  All
15 one-shot controls, nine reel axes and all seven dispatch batches per round
were valid; there was no overflow.  Every real ID19 packet was
`19 0 2 0 0 1 0 22`, so all three were conservative non-targets.  The journal
SHA-256 is
`5A1D45FEF85D9EE706907172FFE7229FEBD592B43DF1F8FE7B572804EB3E6E6C`.
ID304 survived across all three rounds but remains an unlabeled transport row,
not confirmed BGM.

Two static corrections are now mandatory.  First, the official store says the
separately sold Sound Pack unlocks main normal-play BGM and bonus music;
installed SMZ does not prove entitlement or enabled playback.  This is no
longer only a caveat: the PID3125 read-only snapshot shows all seven saved and
active addon values are zero.  Native addon index 6 gates a sorted 222-ID table
through `SoundMng::changeVolume` and `checkEnableSoundID`; both generic play
routes pass through it.  The provenance-complete capture manifest SHA-256 is
`5932A15AF90BAA831B9EE2C7C08A4ADE077C4823C4567A81DC2D4214F694C89F`.
Current BGM/SE/Voice volumes are 50/50/50, master is 100, and Android media is
not muted.  Read
`docs/research/2026-07-14-sound-pack-entitlement-gate.md`; never alter the flag
or guess a replacement track.  Second,
`utf8_font_package.bin`/`sjis_font_package.bin` are missing disabled debug-print
paths, not story fonts.  The story path is the exact DGI catalog of 4,124
`JM_<Unicode>_<family>_<variant>` ASTC glyphs plus Z2D-authored placement.  The
existing Japanese corpus has complete glyph coverage, while the set covers
only about 8.46% of GB2312 CJK; Chinese therefore requires a per-codepoint gate
and an explicitly disclosed fallback when an official glyph is absent.
The read-only catalog/coverage implementation is
`tools/frida_runtime_probe/extract_jm_dgi_glyph_catalog.py`; its dedicated
research note is `docs/research/2026-07-14-jm-dgi-glyph-catalog.md`.

Do not reopen the ac7116 visual-tail mechanism as an unknown.  The committed
2026-07-03 same-run Z2D evidence names `ac7116_AT_SP_story5_01.dgm`, gives end
frame 337, and observes `GetDecodeFrame=337` with `IsDrawTime=1` and continued
draw calls through the 11.267--13.05 s voice tail.  This proves the clean
last-frame hold at runtime-mechanism level.  The outage destroyed that July 3
raw A: JSONL, so a natural target recapture is still useful to restore the raw
audit chain and close outer BGM; it is not needed to re-prove the hold.  The
current v19 two-edition files are also transcoded at roughly 1.09--1.11 Mb/s
versus the existing main-story source around 1.506 Mb/s, so they remain review
artifacts rather than native-bitstream/bitrate-class final uploads.

Durable 2026-07-14 paths:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\gadget_reinject_pid3125_20260714_01
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\natural_hunter_pid3125_server_readonly_smoke_20260714_01
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\natural_hunter_pid3125_gadget_readonly_smoke_20260714_01
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\natural_hunter_pid3125_active_csl_execute_20260714_01
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\addon_state_pid3125_readonly_20260714_02
D:\magia\MyProducts\casino\runtime_recovery_20260714\evidence\sound_pack_gate_static_v31_20260714_02
```

## 2026-07-13 authoritative checkpoint - historical but still valid

The generic natural hunter and its static lottery extractor are documented in:

```text
docs/research/2026-07-13-natural-sp-story-hunter-and-lottery.md
```

Do not treat a stop `CSlotBody::process` bit as logical stop acceptance.  The
new four-layer rule is: internal `body+0x538/+0x53c/+0x540` ready fields,
process input as routing corroboration, exact post-input
`CReel::setStopAngle` axis, and cumulative `state+0x64` progress.  The exact
process bit remains mandatory for MAX BET and lever; a STOP may be accepted by
the exact post-gesture axis plus progress even if its process callback sample is
absent.  The normal-mode first-stop threshold is `body+0x538 >= 16`,
`body+0x53c >= 5`, `body+0x540 == -1`; button colour remains non-evidence.  All
controls use one bounded 500 ms stationary gesture, and missing confirmation
fails closed without retry.

The five relocated SP Story kind tables are now reproducibly decoded by
`extract_sp_story_kind_lottery.py`; every table sums to 32768.  This explains
search cost but does not replace a natural same-run target packet and exact
event-code capture.

PID 3189 and the later PID 8528 both crashed in GLThread with the same Houdini
illegal-PC / SIGSEGV signature ending at fault `0xdead1005`; neither is a target
result and neither may be reused.  The matching signature does not prove which
hook caused the crash.  PID8528 evidence is
`D:\magia\MyProducts\casino\runtime_recovery_20260713\evidence\crash_pid8528_20260713_01`.

PID11160 is now historical.  The latest captured instance is PID 3083; as with
every dated PID, re-read foreground PID after any MuMu restart instead of
reusing it.  The reliable order remains: force-stop, start the title, enter
Simulation without Gadget, press `ゲームスタート`, wait for the real slot
screen, and only then inject Gadget.  Under Houdini the ARM64 game export
belongs to a mapping physically named `split_config.arm64_v8a.apk`, so probes
must resolve the module from a game-specific export rather than hard code the
display name `libGameProc.so`.  Reinjection evidence is
`D:\magia\MyProducts\casino\runtime_recovery_20260713\evidence\gadget_reinject_pid3083_20260713_01`;
the summary SHA-256 is
`DA752417710EF91EFDE6B28F7EACA79E65B5215A1AC97AF35100453AEAAE924F`.

The bounded active CSL transport snapshot is now implemented.  The current
read-only smoke is
`natural_hunter_pid3083_active_csl_readonly_smoke_20260713_03`: zero gameplay
input, declared/captured `65/65`, `truncated=false`, no active rows at either
endpoint, journal SHA-256
`DA92840BC7E140AF1EF8A25E6BA77F97133E36ECA06BE375DDB666BE31F1A6CB`.
Each RPC attaches to the next `CSLMng::Calc`, snapshots on that Calc thread,
then detaches.  The 128-row cap is defensive, not a declared game limit.

`natural_hunter_pid3083_active_csl_execute_20260713_01` is one valid ordinary
non-target round.  Its post snapshot has four playing transport rows, all with
`bgm_semantics_proven=false`: ID820/ch1 (statically an Iroha dialogue),
ID304/ch2, ID2655/ch3 (Sana title call), and ID308/ch11.  ID304/resource834 and
ID308/resource839 remain unlabeled BGM candidates only; channel and loop flags
are not semantic proof.

`natural_hunter_pid3083_active_csl_execute_20260713_02` adds three bounded
ordinary rounds.  All 15 one-shot controls were accepted, all nine STOP axes
and cumulative masks were exact, each round ended without overflow, and every
real ID19 packet still had `raw[1]=0, raw[2]=8`; no legal target was observed.
The journal SHA-256 is
`16B2929BD3FF6B6137AD29CF245F7708AA76D762024B1E11E572C77B581BD828`.

The remaining audio gate is no longer “implement any active snapshot”.  It is
to bind CSL transport to ZG published play-info or equivalent authoritative
identity and prove outer-BGM semantics in the same natural target run.  CSL
transport state by itself must never be described as confirmed BGM.

## 2026-07-11 authoritative checkpoint - read this before older next steps

The repo/worktree link was repaired after the game-root move.  Read-only audit:

```text
D game-root checkout: main @ 50e4f5d, origin/main gone, not authoritative
C 7454 worktree:      codex/corrected-runtime-pipeline @ 6f1bddc before this update
```

The corrected worktree already contains the v17/v19 pipeline history,
composition plans, `build_series_editions.py`, and
`build_material_collection.py`; they were not stranded in the moved D
checkout.  The newest mechanism work is summarized in:

```text
docs/research/2026-07-11-generic-runtime-timeline-and-lc701a-helpers.md
```

The main correction to all older “next step” sections is:

- `0xfff0` is no longer an unexplained byte.  Extended LC701A helper
  `ASM_0xED31` pushes `r8`; its low/high bytes become DirInfo3
  `raw[1]/raw[2]` on the relevant `_USER_FC_CALL` path.
- ID19 `raw[1]=8` is only story permission.  A complete SP Story candidate also
  needs legal ID24 stage/selector in the same real `accessSubProcess` batch.
- Count actual dispatches separately from staging/snapshot observations.
- The generic composition layer is DirectionController
  `pre -> PlayTableData -> PlayMacroData -> Macro_* -> scene/sound request`.
- A Direction BGM/fade macro is not audible-play proof.  Preserve queue mutation,
  request function type (PLAY/STOP), and final CSL play as separate levels.

Latest durable natural-spin evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260711\evidence\light_logic_state_driven_full_spin_20260711_02
```

Current parser result for that capture:

```text
packet observations 11149; actual dispatches 13
copied-buffer observations 26; state/staging snapshots 11110
DirInfo3 observations/dispatches 899/1
DirInfo8 observations/dispatches 1843/1
dispatch batches 2; complete SP Story batches 0
hook errors 0; parse errors 0
```

This run is ordinary `ac0902_276`, not ac7114/ac7115/ac7116.  Its event chain
proves that sound code `295` is a voice-channel STOP request and that the actual
`CSLStream` id 1360 is the official 9.120375-second Yachiyo dialogue.  No new
BGM queue mutation occurred, but already-playing outer BGM is still an open
state question.

The low-noise dynamic request-chain probe is now implemented and has been
generalized (v2):

```text
tools/frida_runtime_probe/sound_logic_chain_probe.js
docs/research/2026-07-11-sound-logic-chain-probe.md
D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\sound_logic_chain_probe_smoke_20260712_01
```

Its smoke has 7/7 hook installs and zero attach/unavailable errors.  It records
all bounded request metadata, not a hard-coded list, across `codeName2ReqId ->
request list -> performRequest -> sndPlayReq -> CSLMng::PlayStart`; it does not
dump audio buffers or full backtraces.  Causal joins are deliberately limited
to the runtime request ID, `ReqOrder+0x28`, and a `sndPlayReq` call actually
nested inside the same `performRequest` on the same thread.  `CSLMng::PlayStart`
is left unassociated and must be joined through the static sound-id table.

The first joint natural log is durable at:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260711\evidence\joint_natural_spin_direction_sound_20260711_01
```

It is an `ac0910_001` run.  Its legacy `same_thread_recent` and
`global_recent_window` fields incorrectly make later request orders, resources,
and final CSL IDs look like children of code 295.  Those temporal/global
associations are invalid and must be ignored.  The underlying rows still show
request 344 as channel-0 `PLAY` with resource 814, and request 774 as channel-2
`PLAY` with resource 2701.  Static tables close `344 -> code 814 -> resource
814 -> final sound id 287` and `774 -> resource 2701 -> final sound id 6758`;
the same run observes final IDs 287 and 6758, but CSL itself has no causal
request context.  Code 814/channel 0 is therefore a strong outer-BGM candidate,
not yet a final BGM semantic classification.  A clean v2 target run plus
before/after active-player state is still required.

The next spin must be controlled by executed game logic, not by button
appearance or a guessed field.  `CSlotBody+0x454` and `CSlotBody+0x455` are both
disproved as per-reel stop-permission gates: their values do not track accepted
individual stops.  Confirm the slot activity is foreground, reach the relevant
logical spin state, then accept a lever/stop action only when that same run's
`CSlotBody::process` call records the corresponding nonzero input bit.  Send one
candidate input at a time and retain the process row that proves acceptance.
The audit anchors are `slot_state_gate_smoke_20260712_02` (idle
`+0x454=1/+0x455=0`), `joint_natural_spin_mechanism_v3_20260712_01` (the same
bytes at state 3, while lever acceptance is `input_a=524288`), and
`light_logic_state_driven_full_spin_20260711_02` (accepted STOP `input_a=2`
from `CSlotBody::process`).
Keep one capture alive through those accepted inputs, same-batch ID19+ID24, SP
Story lottery, Direction macro, sound request PLAY/STOP, final CSL play, and
before/after active-BGM state.

## Current repo state at handoff

2026-07-04 recovery checkpoint:

- A: lost newer temporary data during the power outage.  Treat A: as restored
  2026-06-29 backup plus disposable scratch only.
- A: was lost again in a later power outage on 2026-07-04 and was not restored
  from backup that time.  Treat A: only as disposable scratch.  Do not cite A:
  as the only copy of evidence unless the file has been re-created in the
  current session and also copied to D: or Git.
- Durable immediate progress root is now:

```text
D:\magia\MyProducts\casino
```

- Current authoritative branch is still:

```text
codex/corrected-runtime-pipeline
```

- Latest mechanism direction is not per-`ac` manual sorting.  It is the generic
  ID401/LC701A packet scheduler:

```text
LC701A_SLOT staging/queue
  -> ID401::getCmdBuf(dst, 0xc00)
  -> CSlotBody::analysPacket() 8-byte packet loop
  -> ID401::accessSubProcess(packet)
  -> rev64 callback payload
  -> fnRxComDirInfo3 payload[6]
  -> SdGmData story-lottery route
```

Read these first for the latest runtime/scheduler state:

```text
docs/research/2026-07-04-sdgm-lottery-dispatch-route.md
docs/research/2026-07-04-id401-command-buffer-source.md
```

The target upstream packet for the currently proved story-lottery route is:

```text
packet_id == 19
raw_packet[1] == 8
```

because `ID401::accessSubProcess()` reverses the 8 raw bytes before
`fnRxComDirInfo3` sees them.  Do not search by `ac` suffix number or by visual
contact-sheet similarity.

Second power-loss runtime recovery details:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\gadget_reinject_after_app_restart_second_loss_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_probe_smoke_after_app_restart_second_loss_20260704
```

After the second outage, ADB exposed the device as `emulator-5554` rather than
the older `127.0.0.1:16384`.  Recovery sequence:

```powershell
adb -s emulator-5554 shell "su -c '/data/local/tmp/frida-server -l 0.0.0.0:27042 >/data/local/tmp/frida-server.log 2>&1 &'"
adb -s emulator-5554 forward tcp:27042 tcp:27042
python tools\frida_runtime_probe\reinject_gadget.py --adb-serial emulator-5554 --out-dir <durable evidence dir>
adb -s emulator-5554 forward tcp:27043 tcp:27043
```

Known-good recovery result: PID `4207`, `gadget_arch=arm64`, and
`gadget_sees_libGameProc=true`.  A 5-second lightweight smoke installed 42 hooks
with no error-like rows.

Avoid long `force_selector_probe` `--control-sequence` runs until the queue is
made synchronous.  It can fail with `another action is still pending`, drop the
27043 Gadget connection, and in one attempt terminate the app process.  For the
next full-spin observation, use one lightweight observer plus ADB physical taps,
or patch the control host/script to wait for `action_complete` before sending
the next action.

Before the 2026-07-04 full-spin-summary update, the branch was clean at:

```text
fa73d24 Record second outage recovery state
```

After this update, expect a newer commit containing:

- `tools/frida_runtime_probe/summarize_lightweight_spin_probe.py`;
- `docs/HUMAN_PROGRESS_REPORT_2026-07-04.md`;
- updated project status and ID401/SdGmData research notes.

Always start with:

```powershell
git -C C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw== status --short --branch
git -C C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw== log -5 --oneline --decorate
```

## User-verified current state

The user reviewed:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628
```

User feedback:

- voice and subtitles are correct for `ac7114_001`, `ac7115_001`, and
  `ac7116_001`;
- `ac7116_001__subtitles.mp4` visibly freezes around 11 seconds while voice
  continues to about 13 seconds;
- the same tail-hold symptom is present less strongly in the other segments and
  in the joined scene;
- no obvious BGM is heard; user is unsure whether the original slot game has no
  BGM here or whether the pipeline removed it.

Do not ignore this feedback.  The v19 audio/subtitle correctness is progress,
but the visual-tail and BGM/bed completeness questions remain open delivery
gates.

2026-07-04 correction: the visual-tail gate for
`ac7114_001 + ac7115_001 + ac7116_001` now has runtime-mechanism evidence from
the Z2D movie-layer / CRI receiver route recorded in the project status and
research docs.  Treat the remaining hard gate as natural outer-flow BGM/audio
and full scheduler proof, not as a need to manually remove the hold tail.

## ac7114/ac7115/ac7116 current audit

Relevant runtime resolved manifests:

```text
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved\ac7114_001_v1\event_manifest.json
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved\ac7115_001_v1\event_manifest.json
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved\ac7116_001_v1\event_manifest.json
```

Current v19 production manifests:

```text
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628\events\ac7114_001.json
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628\events\ac7115_001.json
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628\events\ac7116_001.json
```

Current v19 single-event renders:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628
```

Current same-scene long review output:

```text
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate
```

Important correction already made:

- request `1681` / `8040_シネスコ変化音_金帯` is excluded from clean story;
- it belongs to gold-frame/foreground slot presentation, not the normal upload
  animation edition;
- the clean edition keeps the main story screen, not the gold frame layer.

Timing table:

| Event | Source DGM | Native video duration | Render duration | Tail extension | Policy | Retained bed/base-scene audio |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `ac7114_001` | `ac7114_AT_SP_story3_01.mp4` | 9.167 s | 9.629 s | 0.462 s | `hold_last_frame` | `42040_SPストーリー3_01_2G` |
| `ac7115_001` | `ac7115_AT_SP_story4_01.mp4` | 21.200 s | 22.167 s | 0.967 s | `hold_last_frame` | `42060_SPストーリー4_かえでドッペル_01` |
| `ac7116_001` | `ac7116_AT_SP_story5_01.mp4` | 11.267 s | 13.027 s | 1.760 s | `hold_last_frame` | `42080_SPストーリー5_みふゆとももこ_01` |

`ac7116_001` audio timeline:

- `10351 / 42080_SPストーリー5_みふゆとももこ_01`: starts 86 ms,
  duration 11266 ms, ends 11352 ms; this is retained;
- `9537 / 31186_282_mihu_く…ぐ…`: starts 8883 ms, duration 4144 ms,
  ends 13027 ms; this is the dialogue tail and subtitle end;
- `1681 / 8040_シネスコ変化音_金帯`: excluded from clean story because it is
  foreground/gold-frame slot effect audio.

Freeze check:

- source `ac7116_AT_SP_story5_01.mp4` did not show a 0.5 s+ freeze under
  `ffmpeg -vf freezedetect=n=0.003:d=0.5`;
- rendered `ac7116_001__subtitles.mp4` reports `freeze_start: 11.2`;
- this matches the manifest: the renderer holds the final main-story frame from
  the end of the DGM to the end of the last voice/subtitle.

Current interpretation:

- the user is right that the render freezes at the end;
- the freeze is introduced by the current clean renderer's
  `hold_last_frame` policy, not by the source DGM itself;
- this was done to avoid cutting off official voice/subtitle tail;
- it is not yet proven that the live game would show exactly the same clean
  main-story final-frame hold after excluding gold-frame foreground layers.

Current gate:

`audit_runtime_av_trust.py` now emits:

```text
visual_tail_hold_needs_runtime_confirmation
```

when a role-voice event uses `hold_last_frame` or `black_tail` and the visual
tail is at least 750 ms.  The current v19 subset audit is:

```text
A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v19_clean_audio_gate_tail_hold_20260628
```

Summary:

```json
{
  "audited_events": 3,
  "status_counts": {
    "blocked_pending_runtime_av_verification": 3
  },
  "semantic_lane_counts": {
    "normal_animation_candidate_needs_visual_speech_review": 3
  }
}
```

`ac7115_001` and `ac7116_001` currently hit the visual-tail flag.  Therefore the
joined long scene is a user-review/mechanism-validation output, not a final
Bilibili upload candidate yet.

## BGM/bed audio state

Do not equate `bgm_request_count=0` with "the pipeline removed BGM".

For `ac7114/ac7115/ac7116`, the manifests retain one `420xx_SPストーリー...`
audio track each.  The current audit treats this as bed/base-scene audio even
though the literal name is not `BGM`.

Open question:

- Is the retained `420xx_SPストーリー...` track the full native scene bed for
  this slot story event, or should an outer gameplay/state BGM also be present?

Required proof before final publication:

- runtime sound-code/BGM hook trace for this scene path, or
- final `CSLAndroidSimpleBufferQueue::Enqueue` capture proving the full
  audible output, or
- a direct game-produced capture that proves no additional BGM exists.

2026-07-03 update:

- `csl_audio_queue_probe.js` now combines high-level `libGameProc.so`
  sound-code/BGM hooks with final `libAMAIN.so`
  `CSLAndroidSimpleBufferQueue::Enqueue` hooks in one Frida script.
- `summarize_runtime_audio_capture.py` now understands the combined-probe
  sound-code fields.
- Forced `ac7116_001` same-run capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703\summary_v2\summary.json
```

  Result: 38 hooks installed, one `SndIsAlreadyPlayingBGM` attach error,
  0 BGM helper rows, 13 high-level sound-code rows, and only three final
  OpenSL queue chunks: `42080...` / sound id `8912`, `8040...` / sound id
  `9544`, and `31186...` / sound id `8008`.
- Passive current live slot-state 20 s capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703\summary\summary.json
```

  Result: no sound request, no BGM helper, no OpenSL queue chunk.
- This strengthens the forced ac7116 "no extra BGM" evidence, but it still does
  not prove the natural outer gameplay transition into `ac7114/ac7115/ac7116`
  lacks or carries BGM.  Do not remove the outer-flow BGM gate yet.

## Invalidated outputs that must not be promoted

The user found major defects in earlier v18/generic outputs:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626\ac0921_001
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626\ac4901_025
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac4901_full
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7204_character_subset
D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260626\ac7204
```

Reasons:

- missing or unreliable BGM/bed;
- role voices/subtitles not matching mouth movement;
- many 2 s near-identical clips were generated as if they were meaningful final
  outputs;
- `ac7204` with role voice is not pure material;
- contact sheets cannot reveal audio/subtitle correctness.

The invalidation registry is:

```text
tools/frida_runtime_probe/invalidated_output_roots.json
```

Any strategy/coverage/audit script should read it.  The files stay on disk for
audit history but are not completion evidence.

## Mechanism model: what is now known

The game is not manually classifying every `ac` family the way early recovery
work did.  It uses runtime state and native request paths:

```text
GBoss/event code
  -> scene group / scene id
  -> GDB/Z2D/DGM visual assets and timing
  -> native sound-code/request helpers
  -> SoundMng / CSndMng / CSLMng
  -> CSLAndroidSimpleBufferQueue::Enqueue
  -> OpenSL ES audible queue
```

2026-07-03 selector update:

- `body_force_main` post-clear force kinds `0..19` were validly scanned, but
  none reached `ac7114_001`, `ac7115_001`, `ac7115_013`, or `ac7116_001`.
- Do not extend that scan blindly.  Static analysis now shows the SP Story
  selector chain:

```text
MSTCOMCBK()+0x2378
  -> C_AnmBase::fnDataSetDir_DIR() writes C_AnmBase+0x31a
  -> C_ObjStageAT_SP_Story::pre()/fnSetData() copies +0x31a to +0x34a
  -> C_ObjStageAT_SP_Story::fnSetEventCode() uses +0x34a for event-code setup
```

The writer side is now also identified:

```text
SdGmData+0x788
  -> fnKndCalUsr_SetGR_DirPrmCopy()
  -> MSTCOMCBK()+0x2378
```

`fnKndCalUsr_SetGR_DirPrmCopy` is called through PLT `0x449fec0` from the
KndCal lot state functions including `fnKndCalLot_Start`,
`fnKndCalLot_RlStart`, `fnKndCalLot_Prize`, `fnKndCalLot_Demo`, and related
state handlers.

Important correction from the route-table decoder: the target is not
`SdGmData+0x788 = 3/4/5` and not any number inferred from the `ac` suffix.  The
base SP Story route is selected by a pair:

```text
MSTCOMCBK()+0x2376 -> C_AnmBase+0x318      # stage kind
MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a -> C_ObjStageAT_SP_Story+0x34a
```

Decoded target rows:

| target | required route values |
| --- | --- |
| `ac7114_001` | stage kind `11`, selector `1` or `2` |
| `ac7115_001` | stage kind `12`, selector `1` through `4` |
| `ac7115_013` | stage kind `12`, selector `13` or `14` |
| `ac7116_001` | stage kind `13`, selector `1` or `2` |

Durable decoded output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\sp_story_event_code_extract_routes_v2_20260703
```

- New durable static evidence root:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_sp_story_selector_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_set_gr_dir_prm_copy_plt_20260703
```

- New runtime evidence hook in
  `tools/frida_runtime_probe/csl_audio_queue_probe.js`:
  `anm_base_data_set_dir_enter` / `anm_base_data_set_dir_leave`.
- New upstream copy hook:
  `gr_dir_prm_copy_enter` / `gr_dir_prm_copy_leave`.
- New summarizer output:

```text
runtime_anm_dir_data.csv
runtime_gr_dir_prm_copy.csv
```

Smoke evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\selector_hook_smoke_v2_20260703
```

The hook installed and emitted 2253 selector rows in a 2 s idle capture without
suppression after raising the selector hook cap to 20000 rows per kind.  Idle
state still showed selector value `0`, so this is only a hook-validation smoke,
not an ac7114-16 route proof.

Upstream-copy calibration:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gr_dir_copy_force_kind8_v1_20260703
```

This non-target force-kind run emitted six `gr_dir_prm_copy_enter/leave` pairs,
but `SdGmData+0x788`, `MSTCOMCBK()+0x2378`, and `C_AnmBase+0x31a` stayed `0`.
It reached ordinary events only, not SP Story.  Therefore the next unknown is
the state/table write that sets both stage kind and selector to one of the
decoded target route pairs above.

Use that CSV with `runtime_sp_story_state.csv`, `runtime_event_codes.csv`,
`runtime_bgm_calls.csv`, and final CSL queue CSVs to identify the real outer
SP Story route.  This is the current highest-value path toward Bilibili-ready
long videos because it attacks the scheduling problem instead of guessing
individual `ac` families.

2026-07-03 later static lead:

- New offset scanner:

```text
tools/frida_runtime_probe/scan_aarch64_memory_offsets.py
```

- Durable static outputs:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_register_index_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_rx_stage_source_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_rxcom_dirinfo_20260703
```

- `MSTCOMCBK()+0x2376` has a decoded read in
  `C_AnmBase::fnDataSetDir_DIR()` but no decoded direct writer.
- `fnKndCalUsr_SetGR_DirPrmCopy()` should not be treated as the stage writer:
  its `str x21, [x0,#0x2370]` comes from zero-extended `ldrh SdGmData+0x786`
  and therefore clears the high bytes containing `MSTCOMCBK()+0x2376`.
- Stronger upstream lead: `fnRxComDirInfo8()` writes payload byte `5` to
  `SdGmData+0x16e` and byte `4` to `SdGmData+0x170`; then
  `fnRxComPreMdl()` copies:

```text
SdGmData+0x16e -> SdGmData+0x0ee -> SdGmData+0x31a
SdGmData+0x170 -> SdGmData+0x0ec -> SdGmData+0x318
```

This is not yet a closed proof that `SdGmData+0x318/0x31a` equals the final
`C_AnmBase+0x318/0x31a` path for SP Story objects, but it is the current best
lead for where the target `(stage kind, selector)` pair enters the runtime
state.

Runtime probe update: `csl_audio_queue_probe.js` now hooks
`fnRxComDirInfo8`, `fnRxComPreMdl`, and `fnLotDirPreMdl`, and
`summarize_runtime_audio_capture.py` writes `runtime_rxcom_dir_flow.csv`.
Live validation:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_hook_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_force_kind8_probe_20260703
```

The hooks installed successfully.  A single kind 8 diagnostic produced
`rxcom_dir_flow_count=10` but remained a non-target ordinary route:
`sp_story_state_count=0`, `fnRxComDirInfo8` payload byte `4` and byte `5` were
both `0`, and all observed RxCom/SdGm stage/selector fields stayed `0`.
`run_force_kind_scan.py` now carries RxCom counts and unique payload/source
stage/selector values in `candidate_summary.json`.

Important evidence files:

```text
docs/research/2026-06-28-audio-output-mechanism.md
docs/research/2026-06-28-csl-audio-queue-runtime-capture.md
docs/research/2026-06-28-slot-gameplay-audio-state-machine.md
docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md
docs/research/2026-06-27-runtime-av-recapture-report.md
docs/research/2026-06-27-runtime-bgm-gap-report.md
docs/research/2026-06-27-runtime-av-trust-correction.md
docs/research/2026-07-03-sp-story-event-code-and-force-routing.md
```

Critical audio correction:

- earlier `zg::snd::OutputCtrl` probes saw upstream data but the final device
  pointer was null in this MuMu/Gadget state;
- the actually audible one-shot path currently observed is in `libAMAIN.so`:

```text
CSndMng::SndReq(int, int)
  -> CSLMng::SndReq(int, int)
  -> CSLMng::PlayStart(SSound_Data*, int)
  -> CSLAndroidSimpleBufferQueue::Enqueue(void const*, unsigned int)
```

Do not treat `zg::snd::OutputCtrl` capture alone as final mixed audio proof.

Important gameplay-state evidence:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628
```

These prove that a real outer slot-input path triggers high-level BGM helpers
and sound-code mapping that forced single-event playback may not trigger.

Additional 2026-06-28 ac7116 BGM note:

- `visual_tail_probe_ac7116_v3_20260628` saw repeated
  `C_ObjNml::fnSndRequest_BGM_DIR/STG/END` helper calls, but no additional
  concrete BGM/sound-code request for the forced scene beyond the retained
  `42080...` bed and `31186...` role voice.
- `visual_tail_probe_ac7116_v6_after_reinject_20260628` saw one
  `snd_is_already_playing_bgm` hook event plus the same concrete bed/SE/voice
  path, but still did not prove an additional audible BGM stream for this forced
  scene.
- `csl_audio_queue_ac7116_v1_20260628` captured final OpenSL queue chunks for
  the forced official event: request `42080` / sound id `8912`, request `8040`
  / sound id `9544`, and request `31186` / sound id `8008`.  No additional BGM
  request or continuous BGM queue chunk appeared in the forced-event path.
- sound id `8008` is mono in this capture.  The decoder now defaults to
  per-chunk channel inference; older global-stereo timeline WAVs under this
  directory are diagnostic only and understate the final voice duration.
- Therefore those per-frame `C_ObjNml` helper calls are not proof of audible
  BGM.  The remaining BGM gate is specifically an outer-gameplay/full-flow
  question, not a forced-event-only queue question.

2026-07-02 idle slot audio smoke:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_runtime_probe_20260702\slot_idle_runtime_probe_20s.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_csl_queue_probe_20260702\slot_idle_csl_queue_20s.jsonl
```

Both 20 s probes were run from a live slot gameplay screen without forcing an
event.  `runtime_probe.js` produced no non-hook BGM/sound events, and
`csl_audio_queue_probe.js` produced no non-hook play/enqueue events.  This
narrows the BGM problem: the current idle slot screen was not continuously
enqueueing a visible BGM stream during the probe window.  It still does not
settle whether a real transition into `ac7114/ac7115/ac7116` starts or carries
BGM.

2026-07-03 same-run CSL+BGM combined probe:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703
```

For forced `ac7116_001`, the same JSONL captured high-level sound-code requests
and final OpenSL queue chunks.  It found exactly three high-level/final audible
items: `42080_SPストーリー5_みふゆとももこ_01`, `8040_シネスコ変化音_金帯 `,
and `31186_282_mihu_く…ぐ…`.  It found 0 BGM helper rows and no additional
continuous queue chunk.  The passive current-state run found no non-hook
request or queue activity.  This is not a natural-trigger capture; keep the
outer-flow BGM gate open.

2026-07-03 follow-up forced CSL+BGM captures:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_ac7114_v1_20260703\summary_v1\summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_ac7115_v1_20260703\summary_v1\summary.json
docs/research/2026-06-28-csl-audio-queue-runtime-capture.md
```

Results:

- `ac7114_001`: 5 `SoundMng::sndPlayReq` rows, 5 final queue chunks, 0 BGM
  helper rows.  Observed sound-code chain:
  `42040_SPストーリー3_01_2G`, `8040_シネスコ変化音_金帯 `, and role voices
  `30949_228_tur_鶴乃ちゃんハ、サイ`,
  `30950_229_iro_嘘ついちゃダメだよ`,
  `30951_230_yac_鶴乃…！`.
- `ac7115_001`: 10 `SoundMng::sndPlayReq` rows, 10 final queue chunks, 0 BGM
  helper rows.  Observed sound-code chain:
  `42060_SPストーリー4_かえでドッペル_01`, `8040_シネスコ変化音_金帯 `, and
  role voices `30746`, `30739`, `30740`, `30741`, `30742`, `30743`, `30744`,
  `30745`.

Interpretation: all three forced official event paths now show no additional
BGM helper row beyond the scene/base audio, gold-band SE, and role voices.  This
does not prove natural outer-flow no-BGM; it only narrows the remaining BGM
work to the natural transition/full-flow path.

## Visual tail/compositor hook candidates

`libGameProc.so` has no normal symbol table, but dynamic exports provide useful
visual hook candidates.  A read-only symbol survey on 2026-06-28 found these
addresses/names:

```text
0x4261e50 Java_util_JniBridge_nscnCalc
0x424791c GLtask_display1()
0x424797c GLtask_display2()
0x42545d8 DirDrawCtrl
0x42545fc DirGetFrame
0x4254558 DirSetFrame
0x4253f38 CDirMngListener::NotifyStartAnim(int, long long, CDirAnim*)
0x4253d58 CSlotBody::NotifyMovieStart(int, long long, CDirCriAnim*)
0x4253d50 CSlotBody::GetRenderTarget(int, long long)
0x4258238 CriManaWrapper::ExecuteVideoProcess()
0x4258284 CriManaWrapper::IsFrameReady()
0x42582c8 CriManaWrapper::GetFrameInfo(int*, int*, int*, int*)
0x42582c0 CriManaWrapper::GetFrameYUVA(unsigned char**, unsigned char**, unsigned char**, unsigned char**, int*, int*, int*)
0x42582d0 CriManaWrapper::CopyFrameYUVA(unsigned char*, unsigned char*, unsigned char*, unsigned char*, int, int, int)
0x424b574 CScreenObjectMng::calcFrameControl()
0x424b578 CScreenObjectMng::draw()
0x424b5c8 CScreenObjectMng::setLockFrame(int)
0x43b4e9c C_DirectionControllerBase::PlayAnimation()
0x43c2098 C_DirectionControllerBase::Macro_CHANGE_ANM(tagDirectionControllerDeviceData, unsigned short)
0x43c21cc C_DirectionControllerBase::Macro_EVENT_PLAY(tagDirectionControllerDeviceData)
```

### 2026-06-28 ac7116 visual-tail probe update

Read the detailed report before changing the renderer:

```text
docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md
```

Runtime capture directories:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v3_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v4_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v5_frame_yuva_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v6_after_reinject_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v8_offset_compositor_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v9_offset_compositor_20260628
```

Current conclusion:

- `ac7116_001` clean main-story tail hold is still not proven native.
- v3 proves official CRI lifecycle/data identity for gold-frame foreground
  layers and the LP foreground switch near 6.66 s.
- v6, after app restart and Gadget reinjection, did observe the main clean story
  payload `ac7116_AT_SP_story5_01.usm` in `CriManaWrapper::SetData`.
- v6 `GetMovieInfo` for the main receiver reported 512x288, 30 fps, 338 frames,
  implying 11.267 s.  Therefore the source identity and native movie duration
  are now runtime-proven.
- v4 active CRI query probing timed out and must not be repeated as-is.
- v5 installed passive frame-extraction metadata hooks but did not reach the
  event because `event_scene_host` found no active `C_AnmBase` scene object; it
  is inconclusive.
- v6 did not fire the downstream frame/compositor hooks needed to prove the
  exact clean/story layer state after frame 338.  The current hold is supported,
  but not yet compositor-proven.
- v8/v9 added module/offset fallback to `visual_tail_probe.js`.  v8 was only a
  tool smoke because global exports were accidentally missed after resolving the
  module as `split_config.arm64_v8a.apk`.  v9 fixed that, restored CRI/audio
  hooks, and installed `GLtask_display1/2` offset hooks, but those visual hooks
  still did not fire in the forced event window.  The actual clean/story
  compositor hot path remains unidentified.

Important v6 `SetData` identities:

| relative time | size | first-4KiB FNV | matched raw CRI |
| ---: | ---: | --- | --- |
| 0.107 s | 1955904 | `1e31c4fa` | `ac7116_AT_SP_story5_01.usm` |
| 0.129 s | 1507616 | `c8fd6fe7` | `AT_SPstory_gold_frame_add.usm` |
| 0.138 s | 2159168 | `72e6f81c` | `AT_SPstory_gold_frame.usm` |
| 6.747 s | 1483776 | `c9cc7d28` | `AT_SPstory_gold_frame_add_LP.usm` |
| 6.759 s | 2157056 | `f32a4a6b` | `AT_SPstory_gold_frame_LP.usm` |

The clean main story raw CRI identity is:

```text
patch_index=1321
size=1955904
first-4KiB FNV=1e31c4fa
name=ac7116_AT_SP_story5_01.usm
```

Do not use the older `main_video_0000_candidates264.mp4` lead as a replacement
without stronger proof.  It is a 416x232 restaurant/table scene and conflicts
with both the official 2026-06-18 runtime DGM string
`[ac7116_AT_SP_story5_01.dgm]` and the v6 direct `SetData` hit for
`ac7116_AT_SP_story5_01.usm`.

Runtime capture recovery notes:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_visual_tail_recovery_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_visual_tail_recovery_after_restart_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_visual_tail_after_reinject_20260628
```

The working recovery sequence was: force-stop app, start
`com.universal777.magireco/.SlotMainActivity`, then run `reinject_gadget.py`.
MuMu screenshots are 2160x3840; use physical ADB coordinates.  Useful taps from
this run: `1080 3000` for the title simulation button, then `600 2670` for
`ゲームスタート`.

Full-machine screenrecord diagnostic:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_20260628.mp4
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_contact.jpg
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_late_tail_frames.jpg
```

This proves the live full-machine presentation enters/holds foreground
slot/title layers after the main story section, but it does not prove the clean
story layer state after those foreground layers are excluded.

Forced-event final audio queue diagnostic:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_runtime_audio_timeline_inferred.json
```

Current ac7116 queue facts:

| Runtime request | Sound id | Queue start | Queue clear / inferred end | Format |
| ---: | ---: | ---: | ---: | --- |
| `42080` | `8912` | 0.066 s | 11.344 s | stereo |
| `8040` | `9544` | 0.070 s | 2.744 s | stereo |
| `31186` | `8008` | 8.879 s | 13.044 s | mono |

`decode_csl_audio_queue_dump.py` now has `--channel-mode infer` by default and
supports `--sound-id-channel SOUND_ID=CHANNELS`.  This matters for role voices:
sound id `8008` is 397838 bytes and cannot be interpreted as 16-bit stereo.

2026-07-02 animation-state sampler follow-up:

```text
docs/research/2026-07-02-ac7116-animation-state-sampler.md
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_state_sampler_ac7116_v10_after_recovery_20260702
```

`event_scene_probe.js` now emits passive `animation_state_sample` records every
about 250 ms while a forced event context is active.  For `ac7116_001`, v10
captured 68 samples through 16.817 s.  The selected source stayed
`C_AnmMain+0x350`, selected object `0x72b06b9bacc0`, frame object
`0x72b06b9bcf40`, and `last_frame_age_ms` remained low during the
11.267-13.027 s voice/subtitle tail.  This proves the live official animation
system is still actively rendering the same story animation object after the
main USM duration.  Combined with v6's 338-frame `GetMovieInfo`, the current
clean `hold_last_frame` behavior is now runtime-supported for
mechanism-validation renders.  It is still not exact clean-layer pixel proof,
so final publication remains gated on compositor/pixel evidence and BGM/full
outer-flow evidence.

v11/v13 numeric follow-up:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v11_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v13_default_after_reinject_20260702
```

Both runs found selected-object offset `+0x350` increasing monotonically at
about 30 fps through the 11.267-13.027 s tail.  Treat this as the active
animation object's clock, not as the CRI movie frame index.  A broad pointer
scan was attempted in v12 and caused capture timeout/Gadget reinjection; leave
`includePointerProbe=false` unless the offset list is narrowed first.

v16 CRI receiver follow-up:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702\summary\cri_receiver_summary.json
```

After app restart and Gadget reinjection, `visual_tail_probe.js` captured the
main CRI receiver:

| receiver | FNV | size | movie info | update/status |
| --- | --- | ---: | --- | --- |
| `0x72af8bceec90` | `1e31c4fa` | `1955904` | 512x288, 30 fps, 338 frames | `cri_update` 4-11134 ms; `GetStatus=5` 267-10973 ms |

The same receiver remained numerically sampleable through 20746 ms, while the
higher animation object remained active in v10/v13.  This supports the model:
main CRI reaches the end near the source duration, then the animation/compositor
layer holds its output while the final voice continues.  It still is not a
clean-layer texture/pixel hash after frame 338.

2026-07-02 renderer texture-state follow-up:

```text
docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md
tools/frida_runtime_probe/runtime_symbol_survey.js
tools/frida_runtime_probe/gl_texture_probe.js
tools/frida_runtime_probe/summarize_gl_texture_probe.py
tools/frida_runtime_probe/cri_video_texture_probe.js
tools/frida_runtime_probe/summarize_cri_video_texture_probe.py
```

Important captures:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gl_texture_probe_ac7116_v5_bind_timeline_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_symbol_survey_renderer_cri_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v5_combined_after_restart_20260702
```

Findings:

- the original GLES global-export hooks were blind; after hooking all GLES/EGL
  module exports and `eglGetProcAddress`, the game showed 512x288
  `libGLESv1_CM.so` texture allocation/bind/delete only around event start and
  the 6.7 s LP switch;
- no normal GL texture upload/bind/delete/draw/sync/swap was observed in the
  11.267-13.05 s voice tail;
- full-module symbol survey found better renderer candidates in
  `split_config.arm64_v8a.apk`, especially
  `RendererImplGL::checkAndBindTextureStates`;
- the combined after-restart run captured main story `1e31c4fa`/1955904 with
  512x288, 30 fps, 338 frames, and the same renderer/texture-state tuple
  continued in all key windows:

| Window | `sprite_renderer_check_bind_texture_states` count | tuple |
| --- | ---: | --- |
| 9.000-11.000 s | 8 | `0x72b10b97f910` + `0x72af3cccff78` + flag `1` |
| 11.267-13.050 s | 6 | `0x72b10b97f910` + `0x72af3cccff78` + flag `1` |
| 14.000-20.000 s | 23 | `0x72b10b97f910` + `0x72af3cccff78` + flag `1` |

This strengthens ac7116 hold evidence from animation-object/CRI-lifecycle
support to renderer-path support.  It still is not an exact clean-layer
framebuffer or pixel hash.

2026-07-03 narrow TextureStateGL field sampler:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\texture_state_fields_ac7116_v2_after_restart_20260703
```

This run extended `cri_video_texture_probe.js` to sample only numeric
candidates in the first 0x80 bytes of each `TextureStateGL` pointer passed to
`RendererImplGL::checkAndBindTextureStates`.  It again captured the main story
`1e31c4fa`/1955904 payload as 512x288, 30 fps, 338 frames.  Renderer check
counts:

| Window | count |
| --- | ---: |
| 9.000-11.000 s | 22 |
| 11.267-13.050 s | 20 |
| 14.000-20.000 s | 68 |

Three texture-state pointers stayed active through the tail:

| Texture state | total | 9-11 s | 11.267-13.05 s | 14-20 s |
| --- | ---: | ---: | ---: | ---: |
| `0x72af42645f58` | 95 | 7 | 7 | 23 |
| `0x72af42645f78` | 95 | 7 | 7 | 23 |
| `0x72af42646148` | 94 | 8 | 6 | 22 |

Stable tail-window fields included `+0x4=3553`, `+0xc=3`, and
`+0x68=194423728` across the active texture-state records; one state also had
`+0x8=148`, `+0x58=1024`, `+0x60=1` stable.  Treat `+0x4=3553` as consistent
with `GL_TEXTURE_2D`, not as a fully reverse-engineered struct layout.  This is
stronger steady-renderer-state evidence, but it still is not clean-layer
framebuffer/pixel proof.

2026-07-03 renderer drawCall primitive sampler:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary\cri_video_texture_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary\cri_video_texture_events.csv
```

This is the strongest ac7116 hold evidence so far.  v8 was captured after app
restart, Gadget reinjection, and title-flow taps.  It captured the main story
`1e31c4fa`/1955904 as 512x288, 30 fps, 338 frames in the same run as renderer
primitive samples.  Counts:

| Window | `checkAndBindTextureStates` | `drawCall` | `cri_update` / `cri_get_status` |
| --- | ---: | ---: | ---: |
| 9.000-11.000 s | 24 | 24 | 30 / 30 |
| 11.267-13.050 s | 19 | 19 | 20 / 20 |
| 14.000-20.000 s | 69 | 69 | 69 / 69 |

Tail-window primitive groups:

| Primitive | Total | 9-11 s | 11.267-13.05 s | 14-20 s | Texture signature |
| --- | ---: | ---: | ---: | ---: | --- |
| `0x72af405bd370` | 79 | 8 | 6 | 23 | mode `2`, vertices `4`, texture id `155`, `+0xc=29359` |
| `0x72af405bd168` | 75 | 6 | 6 | 23 | mode `2`, vertices `4`, texture id `151`, `+0xc=2606733044` |
| `0x72af405bd148` | 74 | 8 | 6 | 21 | mode `2`, vertices `4`, texture id `150`, `+0xc=29360` |

Fine-window resummary from the same v8 JSONL:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary_fine_windows\cri_video_texture_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary_fine_windows\cri_video_texture_events.csv
```

| Primitive | 0-0.5 s | 0.5-6.6 s | 6.6-7.2 s | 7.2-11.0 s | 11.267-13.05 s | 14-20 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0x72af405bd370` / tex `155` | 1 | 22 | 2 | 14 | 6 | 23 |
| `0x72af405bd168` / tex `151` | 2 | 22 | 1 | 10 | 6 | 23 |
| `0x72af405bd148` / tex `150` | 1 | 20 | 1 | 13 | 6 | 21 |

The safe conclusion is that the game renderer keeps submitting stable
single-texture quad primitives during the final voice/subtitle tail after the
main 338-frame movie boundary.  This supports the current external
`hold_last_frame` behavior as runtime-mechanism-matched.

Caveats:

- v6 primitive capture worked but did not see the main story `1e31c4fa`
  `SetData`; use v8 for same-run identity.
- This is still not a clean-layer framebuffer/pixel hash.  If final release
  policy requires pixel identity, capture a clean-layer texture or framebuffer
  hash next.
- The same run also saw `89802b19`, 512x416, 5277 frames.  Keep treating it as
  slot/gameplay/material state, not clean story continuation.

2026-07-03 visual-tail lock rerun:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\diag_visual_tail_lock_probe_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703\summary_animation\animation_state_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703\summary_cri_receiver\cri_receiver_summary.json
```

This reran `visual_tail_probe.js` after `diagnose_runtime_capture_state.py`
reported `runtime_capture_ready_via_arm64_gadget`.  Event and runtime sides
both exited 0.  The animation summary is useful:

| Field | Value |
| --- | --- |
| sample count | 88 |
| first / last forced-event relative sample | 18 ms / 21829 ms |
| selected source | `C_AnmMain+0x350` for all 88 samples |
| selected object | `0x72b06b9870c0` for all 88 samples |
| frame object | `0x72b06b987510` for all 88 samples |
| last-frame age | 17-51 ms, avg 32.65 ms |
| selected object `+0x350` | 4289 -> 4944, 87 increasing steps, 0 decreasing steps |

The frame-lock route itself was negative:

| Hook kind | Calls |
| --- | ---: |
| `dir_get_frame` / `dir_set_frame` / `dir_draw_ctrl` | 0 |
| `notify_movie_start` / `notify_start_anim` | 0 |
| `cri_get_frame_info` / `cri_is_frame_ready` | 0 |
| `screen_object_calc_frame_control` / `screen_object_draw` | 0 |
| `screen_object_set_lock_frame` / `screen_object_check_lock` / `screen_object_is_lock` | 0 |

The hooks installed, so this is negative/inconclusive mechanism evidence, not a
setup failure.  Also, v10 did not recapture main story `1e31c4fa`; it only saw
foreground/gold-frame `SetData` rows (`c8fd6fe7`, `72e6f81c`, `c9cc7d28`,
`f32a4a6b`) plus pre-existing receiver pointers.  Do not use v10 for main-clean
identity.  Use v8 primitive capture for that.

Practical instruction: do not spend another run repeating the same high-level
`DirGetFrame` / `NotifyMovieStart` / `NotifyStartAnim` / `GetFrameInfo` /
`CScreenObjectMng` lock hook set by itself.  The next useful visual proof is
either lower-level compositor/renderer metadata on a path already known to fire,
or direct clean-layer texture/framebuffer hash.

Full ac7114-16 receiver summary:

```text
docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7114_v1_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7115_v1_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702
```

| Event | Main FNV | Movie info | Update/status summary |
| --- | --- | --- | --- |
| `ac7114_001` | `a5b2c906` | 512x288, 30 fps, 275 frames | update 3-8131 ms; `GetStatus=5` 263-9065 ms |
| `ac7115_001` | `4ad69770` | 512x288, 30 fps, 636 frames | update 3-20145 ms; `GetStatus=5` 278-20959 ms |
| `ac7116_001` | `1e31c4fa` | 512x288, 30 fps, 338 frames | update 4-11134 ms; `GetStatus=5` 267-10973 ms |

The `ac7115_001` run also saw `89802b19`, a 512x416, 5277-frame, 33.5 MiB CRI
receiver.  Treat it as slot/gameplay/material state, not a clean story
continuation.

Recommended next visual proof route for the ac7116 tail:

1. Start from a known-good recovered Gadget state; if 27043 times out, restart
   app and reinject Gadget before forcing the event.
2. Read
   `docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md`; do not
   repeat blind `GLtask_display1/2` work.
3. Do not repeat the v10 high-level lock/notification route by itself:
   `DirGetFrame`, `NotifyMovieStart`, `NotifyStartAnim`, `GetFrameInfo`,
   `IsFrameReady`, and `CScreenObjectMng` lock/draw hooks installed but produced
   zero call records.
4. The narrower `TextureStateGL` and primitive sampler route has now been done
   through `texture_state_fields_ac7116_v2_after_restart_20260703` and
   `cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703`.
   If more visual proof is needed, target a clean-layer texture/pixel hash or a
   compositor/frame-lock state hook.  The goal is clean/story layer state, not
   another full-machine screenrecord.

If the live game locks the final main-story frame while the voice tail plays,
the current hold is acceptable.  If the game switches to another visual layer or
state, the external render must reproduce that instead of holding a still.

### 2026-07-03 Z2D movie-layer proof update

Do not continue spending time on the old high-level frame-lock hook set as the
primary ac7116 visual-tail route.  The useful route is now the Z2D movie-layer
path.

New metadata-only tools:

```text
tools/frida_runtime_probe/z2d_movie_layer_probe.js
tools/frida_runtime_probe/summarize_z2d_movie_layer_probe.py
```

Static symbol survey artifacts:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\renderer_symbol_candidates_20260703.txt
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_direction_symbol_candidates_20260703.txt
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\movie_layer_symbol_candidates_20260703.jsonl
```

Useful v1 capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703\summary_v2\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703\summary_v2\z2d_movie_layer_events.csv
```

Key facts for `ac7116_001`:

- The probe found an active Z2D movie object:
  `play_movie_pointer=0x72affba2cae8`,
  `elem_movie_pointer=0x72affba2ca98`.
- That object is 512x288, start/end frame 0/337, and its frame/decode fields
  remain fixed at 337.
- `CZ2DElemMovie::IsDrawTime(337)` returns 1 in the voice tail.
- Its texture-like field is constant `151`, matching renderer primitive
  `0x72af405bd168` / texture id `151`.
- In 11.267-13.05 s, the game continues `ExecPlayMovie`, `GetDecodeFrame`,
  `DecodeMovie`, and `drawCall` for this object/primitive.
- First/last observed times for the correlated object cover roughly -1.48 s to
  25.96 s relative to the forced event start, well past the 13.027 s final voice
  endpoint.

Interpretation: for `ac7116_001`, the current external `hold_last_frame` policy
is now strongly supported by the game's own Z2D movie-layer mechanism.  The
game appears to keep the clean 512x288 movie element drawable at final frame 337
while audio/subtitle tail continues.

v1 caveat: v1 did not recapture the main story `1e31c4fa`
`CriManaWrapper::SetData` in the same run; it only recaptured
foreground/gold-frame CRIs.  That caveat was closed by v2.

Useful v2 same-run closure capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_z2d_same_run_closure_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703\summary_v2\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703\summary_v2\z2d_movie_layer_events.csv
```

v2 was captured after force-stop/start, arm64 Gadget reinjection, and the known
title-flow taps.  Event and runtime exit codes were both 0.  It captured both
required facts in one JSONL:

1. main story `ac7116_AT_SP_story5_01.usm` / `1e31c4fa` / 1955904 bytes /
   512x288 / 338 frames at 121 ms; and
2. named Z2D movie object `ac7116_AT_SP_story5_01.dgm`:
   `play_movie_pointer=0x72affb9c0ae8`,
   `elem_movie_pointer=0x72affb9c0a98`, 512x288, start/end frame 0/337,
   texture-like id `153`, renderer primitive `0x72af4e66e168` / texture id
   `153`.

In the 11.267-13.05 s voice/subtitle tail, v2 shows the named clean story object
holding frame 337:

```text
rel_ms=11302 IsDrawTime elem=0x72affb9c0a98 input=337 return=1
rel_ms=11302 GetDecodeFrame elem=0x72affb9c0a98 input=337 return=337
rel_ms=11331 ExecPlayMovie play=0x72affb9c0ae8 +0x4=337 +0x20=153 +0x28=337 +0x38=512 +0x40=288
rel_ms=11331 GetEndTime elem=0x72affb9c0a98 return=337
rel_ms=11331 DecodeMovie play=0x72affb9c0ae8 +0x4=337 +0x20=153 +0x28=337 +0x38=512 +0x40=288
rel_ms=11465 drawCall primitive=0x72af4e66e168
```

The same object is observed through about 25.93 s.  Therefore `ac7116_001`
visual-tail hold is now runtime-mechanism proven: the game itself keeps the
named clean story movie element drawable at final frame 337 while the voice tail
continues.  A framebuffer/texture-byte hash would be stricter pixel proof, but
it is no longer necessary to explain the external render's final-frame hold for
`ac7116_001`.

The same Z2D route was then extended to the other two events in the same scene:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7114_v1_20260703\summary_v1\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7115_v1_20260703\summary_v1\z2d_movie_layer_summary.json
docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md
```

Additional results:

- `ac7114_001`: same run captured main story `a5b2c906` / 1903456 bytes /
  512x288 / 275 frames and named Z2D movie
  `ac7114_AT_SP_story3_01.dgm`; play `0x72affba47728`,
  elem `0x72affba476d8`, end frame 274, texture-like id `165`, renderer
  primitive `0x72af4e66e168` / texture id `165`.  Tail rows show
  `IsDrawTime(274)=1`, `GetDecodeFrame(274)=274`, and continued drawCall.
- `ac7115_001`: same run captured main story `4ad69770` / 3940544 bytes /
  512x288 / 636 frames and named Z2D movie
  `ac7115_AT_SP_story4_01.dgm`; play `0x72affb9d0c28`,
  elem `0x72affb9d0bd8`, end frame 635, texture-like id `197`, renderer
  primitive `0x72af4e66e168` / texture id `197`.  Tail rows show
  `IsDrawTime(635)=1`, `GetDecodeFrame(635)=635`, and continued drawCall.
  The same run also saw small CRIs `7fc38d87` and `400d7791`; they are
  transition/follow-up CRIs and must not replace the named clean story DGM.

Current visual-tail conclusion: the clean story `hold_last_frame` policy for
`ac7114_001 + ac7115_001 + ac7116_001` is now runtime-mechanism proven.  Do not
spend more work on this gate unless a stricter framebuffer/texture-byte hash is
explicitly required.

The separate BGM/outer-flow gate remains open.  Do not mark the Bilibili long
scene final until BGM/bed presence is proven or proven absent.

## Current important tools

Read these before changing pipeline behavior:

```text
tools/frida_runtime_probe/runtime_probe.js
tools/frida_runtime_probe/event_scene_probe.js
tools/frida_runtime_probe/csl_audio_queue_probe.js
tools/frida_runtime_probe/resolve_official_event_capture.py
tools/frida_runtime_probe/build_event_production_manifests.py
tools/frida_runtime_probe/render_event_batch.py
tools/frida_runtime_probe/qa_event_batch.py
tools/frida_runtime_probe/audit_runtime_av_trust.py
tools/frida_runtime_probe/report_pipeline_strategy.py
tools/frida_runtime_probe/build_scene_editions.py
tools/frida_runtime_probe/build_series_editions.py
tools/frida_runtime_probe/build_material_collection.py
tools/frida_runtime_probe/summarize_runtime_audio_capture.py
tools/frida_runtime_probe/decode_csl_audio_queue_dump.py
tools/frida_runtime_probe/summarize_animation_state_samples.py
tools/frida_runtime_probe/summarize_cri_receiver_samples.py
tools/frida_runtime_probe/runtime_symbol_survey.js
tools/frida_runtime_probe/gl_texture_probe.js
tools/frida_runtime_probe/summarize_gl_texture_probe.py
tools/frida_runtime_probe/cri_video_texture_probe.js
tools/frida_runtime_probe/summarize_cri_video_texture_probe.py
tools/frida_runtime_probe/z2d_movie_layer_probe.js
tools/frida_runtime_probe/summarize_z2d_movie_layer_probe.py
tools/frida_runtime_probe/package_runtime_evidence_capture.py
tools/frida_runtime_probe/reinject_gadget.py
```

Key distinction:

- `build_series_editions.py` is prefix/family based.  It is valid for a single
  `acXXXX` family when the family is verified.
- `build_scene_editions.py` takes an explicit event sequence and should be used
  for same-scene long videos that span prefixes, such as
  `ac7114_001 + ac7115_001 + ac7116_001`.

## Known good or useful outputs

Earlier user-checked outputs that looked good:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1102_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1104_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac0908_food_sample
A:\magireco_corrected_research_20260612\validated_ac1103_full_v15
```

User spot checks showed files such as `ac1102_006`, `ac1104_014`, and
`ac0908_006` are 416x232, 30/1, 48000 Hz, stereo and visually acceptable.

Do not assume these families are fully final without auditing their long-edition
structure and current AV trust gates.  They are high-priority candidates for
same-scene/family long review collections because the user wants Bilibili-sized
long videos while preserving original segments.

Current v19 ac7114-16 useful-but-not-final output:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate
```

Use these for user visual/audio review and for investigating the tail-hold
question.  Do not present them as final upload-ready outputs yet.

## Reproducibility and GitHub release state

Project kit directory:

```text
reproducibility/project-kit/
```

Evidence release already published:

```text
https://github.com/HiiragiNemu/magireco-slot-asset-pipeline/releases/tag/analysis-evidence-v18.27-20260628
```

Release asset:

```text
magireco-analysis-evidence-v18-20260628-100858.zip
SHA-256: 2D440A240CEF5A2A7F08D0B4FDE6D356A10CAF80655CA5E8370657000AD06797
```

This release is text-only derived evidence.  It intentionally excludes raw
Frida JSONL, WAV, screenshots, videos, APK/OBB/native libraries, and game
payload binaries.

## Commands to reproduce current audits

Run v19 ac7114-16 AV trust audit:

```powershell
python C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\audit_runtime_av_trust.py `
  --production-manifest-root A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628 `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v19_clean_audio_gate_tail_hold_20260628 `
  --render-root A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628 `
  --series-root D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628 `
  --invalidated-output-roots C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\invalidated_output_roots.json
```

Check ac7116 source/render freeze:

```powershell
ffmpeg -hide_banner -nostats `
  -i A:\magireco_bili_fulltest_20260603\cri_official_video_map\official_named_videos\patch\ac7116\ac7116_AT_SP_story5_01.mp4 `
  -vf freezedetect=n=0.003:d=0.5 -an -f null -

ffmpeg -hide_banner -nostats `
  -i A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628\ac7116_001\with_subtitles\ac7116_001__subtitles.mp4 `
  -vf freezedetect=n=0.003:d=0.5 -an -f null -
```

The rendered file reports `freeze_start: 11.2`.  The source check did not show
the equivalent freeze.

Run full v18 AV trust audit with current gates:

```powershell
python C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\audit_runtime_av_trust.py `
  --production-manifest-root A:\magireco_corrected_research_20260612\production_manifests_v18 `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628 `
  --invalidated-output-roots C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\invalidated_output_roots.json
```

Current output:

```text
A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628
```

Summary:

```json
{
  "audited_events": 926,
  "status_counts": {
    "blocked_pending_runtime_av_verification": 897,
    "no_av_trust_flags_detected": 29
  },
  "visual_tail_hold_needs_runtime_confirmation": 29
}
```

Only run broad renders after this audit and a strategy report show that events
are delivery-actionable, not just technically render-ready.

Rebuild strategy queues with the same AV trust CSV:

```powershell
python tools\frida_runtime_probe\report_pipeline_strategy.py `
  --production-catalog A:\magireco_corrected_research_20260612\production_manifests_v18\event_production_catalog.csv `
  --coverage-csv A:\magireco_corrected_research_20260612\coverage_audits_v18_20260626\event_coverage_v18.csv `
  --audience-catalog A:\magireco_corrected_research_20260612\manifests\audience_event_catalog_v1\audience_event_catalog.csv `
  --composition-plans tools\frida_runtime_probe\composition_plans `
  --audience-exclusions tools\frida_runtime_probe\audience_exclusions.json `
  --runtime-av-trust-csv A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628\runtime_av_trust_audit.csv `
  --out-dir A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_tail_hold_gate_20260628
```

Current strategy result:

```json
{
  "ready_missing_single_event_QA": 217,
  "ready_missing_single_event_QA_delivery_actionable": 4,
  "ready_missing_single_event_QA_av_blocked": 213,
  "visual_tail_hold_needs_runtime_confirmation": 29
}
```

## 2026-07-03 SP Story / force-routing update

Read this detailed report before continuing the ac7114-16 BGM gate:

```text
docs/research/2026-07-03-sp-story-event-code-and-force-routing.md
```

## 2026-07-03 power-loss recovery note

The RAM disk A: lost the 2026-07-03 transient captures after a power loss.  The
user restored a 2026-06-29 backup to A: and also unpacked the same backup to:

```text
D:\magia\MyProducts\casino
```

Use the repository, GitHub branch, C: worktree, and D: as durable state.  Treat
2026-07-03 A:-only runtime JSONL/screenshots as lost unless the file still
exists after restore.  New durable runtime evidence should go under:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

A: may still be used for disposable high-frequency scratch, but do not make it
the only copy of evidence needed for the handoff, QA, manifests, or Bilibili
delivery decisions.

Correct repository state after recovery:

- branch: `codex/corrected-runtime-pipeline`
- force-kind recovery commits through
  `6af86e8 Add auditable force kind scan` were pushed before the selector
  tracing work.
- The current local diff adds static xref survey support, the
  `C_AnmBase::fnDataSetDir_DIR` runtime hook, `runtime_anm_dir_data.csv`
  summarization, and updated handoff/status notes.

Current facts:

- `C_ObjStageAT_SP_Story::fnSetEvCdBase` statically contains the official
  base event codes for `ac7114_001`, `ac7115_001`, and `ac7116_001`.
- New extractor:
  `tools/frida_runtime_probe/extract_sp_story_event_codes.py`.
- New runtime state table from combined CSL/BGM captures:
  `runtime_sp_story_state.csv`, emitted by
  `tools/frida_runtime_probe/summarize_runtime_audio_capture.py`.
- Natural slot input captures on 2026-07-03 proved ordinary gameplay can call
  BGM helper paths, but the captures reached restaurant/ordinary slot flow, not
  target SP Story.  They do not close the ac7114-16 BGM gate.
- The visible force selector is currently blocked by the add-on purchase gate.
  Do not use the purchase popup path as evidence.
- Internal `CSlotBody` force state can now be written reproducibly:

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-force-main --index <n>
python tools\frida_runtime_probe\force_selector_host.py body-force-sub --index <n>
python tools\frida_runtime_probe\force_selector_host.py body-force-param --index <n>
```

Validated evidence:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\force_body_main_write0_20260703c.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\force_body_main_reset_minus1_20260703c.jsonl
```

Historical note: the next experiment was previously to map `body-force-main`
index `0..19`.  That work is now done via the post-clear diagnostic route and
did not reach ac7114-16.  Do not repeat or extend it blindly.  The recommended
next experiment is now a narrow selector capture using
`anm_base_data_set_dir_enter/leave`, `runtime_anm_dir_data.csv`,
`runtime_sp_story_state.csv`, `runtime_event_codes.csv`,
`runtime_bgm_calls.csv`, `runtime_sound_code_calls.csv`, and final CSL queue
CSVs in the same run.

Additional 2026-07-03 recovery results:

- Gadget recovery after the power loss required:
  - root x86 frida-server on `127.0.0.1:27042`;
  - `reinject_gadget.py`;
  - explicit `adb forward tcp:27043 tcp:27043`.
- Durable evidence root:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

- Natural one-spin baseline after recovery:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_baseline_one_spin_after_recovery_20260703
```

- Naive `body-force-main` before lever is not reliable because early
  `CSlotBody::START` cleanup can clear the field before `fnSetForceFlag`.
- New diagnostic action:

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-force-next-lever --index <kind>
```

It injects the force kind after `ID401::fnClrForceFlag()` and before
`fnSetForceFlag`.  This is for force-kind mapping only; it is not a final
render approval mechanism.
- `force_index0_postclear_chain_20260703` validated the diagnostic route:
  independent observer captured `force_flag_set arg0=0`.
- `force_index8_postclear_probe_20260703` mapped force kind 8 to
  `ac0922_001` (`0x31434e5a38404764`, voices `31043`-`31061`), with no
  `C_ObjStageAT_SP_Story` runtime event.  Later selector-calibration runs with
  kind 8 reached ordinary `ac0101`/`ac0102`/`ac9071`/`ac9920` routes instead.
  Treat kind 8 as a non-target diagnostic route, not a stable ac0922 selector
  and not ac7114-16.
- `run_force_kind_scan.py` now automates clean restart/title-entry/ready-state
  force-kind mapping.  Current MuMu input coordinates are physical `2160x3840`:
  title `シミュレーション` is `1080 3000`, `ゲームスタート` is `600 2670`,
  reel stops are `880/1160/1440 2860`.
- Invalid samples before that coordinate/title-entry fix:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_2_7_9_19_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_kind2_v2_20260703
```

- Valid post-clear scan evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_kind2_v3_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_3_7_9_19_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index8_postclear_probe_20260703
```

- Conclusion from valid evidence:
  - force kinds `1..7` and `9..19` each emitted real
    `force_flag_set(kind, 0)` but mapped to ordinary slot/gameplay event-code
    groups, with `sp_story_state_count=0`;
  - force kind `8` is non-target; it has produced one `ac0922_001` / Episode
    Bonus run and later ordinary-route calibration runs, but no SP Story target;
  - force kind `0` validated the diagnostic route but did not reach the target;
  - no tested `0..19` kind reached any target code for `ac7114_001`,
    `ac7115_001`, `ac7115_013`, or `ac7116_001`.
- Do not blindly extend the force-kind scan above 19.  Next useful work is
  the SP Story route now identified statically:
  `MSTCOMCBK()+0x2376 -> C_AnmBase+0x318` plus
  `SdGmData+0x788 -> MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a ->
  C_ObjStageAT_SP_Story+0x34a`.  The new `gr_dir_prm_copy_*` and
  `anm_base_data_set_dir_*` runtime events should be used to observe it live.

Additional same-session control update:

- The 27043 ARM64 Gadget can become unstable when two host processes attach at
  the same time.  In current runs, `runtime_probe_host.py` as observer plus a
  second `force_selector_host.py` trigger can fail with
  `frida.TransportError: connection closed` before the trigger is sent.
- `runtime_probe_host.py` now supports loading both scripts in one Gadget
  session:

```powershell
python tools\frida_runtime_probe\runtime_probe_host.py `
  --script tools\frida_runtime_probe\csl_audio_queue_probe.js `
  --control-script tools\frida_runtime_probe\force_selector_probe.js `
  --control-sequence body_bet=1,body_bet=1,body_force_next_lever=8 `
  --out D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\<run>\observer_control_csl.jsonl `
  --duration 30 --quiet --no-unload
```

- `--no-unload` is intentional for fragile Gadget cleanup; the JSONL is closed
  before the forced process exit.
- `csl_audio_queue_probe.js` now captures RxCom/SdGm and BGM helper
  backtraces.  `runtime_bgm_calls.csv` now contains `symbol`, `address`,
  arguments, and backtrace fields.
- Valid recovery evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gadget_reinject_after_app_restart_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_bgm_backtrace_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\single_session_force_kind8_control_v1_20260703
```

- `natural_bgm_backtrace_smoke_20260703` only proves the combined probe still
  sees final OpenSL queue chunks after reinjection: sound ids `8993` and
  `8998`.  It had 0 BGM helper rows and is not target SP Story evidence.
- `single_session_force_kind8_control_v1_20260703` proves observer + control
  can share a JSONL in one Gadget session, but the initial control state was
  not ready (`body_state=0`, `body_mode=0`, `body_bet=0`).  It emitted event
  code `0x43454f646b32615a` with `sp_story_state_count=0`,
  `rxcom_dir_flow_count=0`, and `bgm_call_count=0`.  Treat it as a tooling
  proof only.
- Failed evidence to avoid overclaiming:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\diagnose_gadget_after_transport_closed_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_force_kind8_backtrace_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\single_session_force_kind8_control_v2_20260703
```

These document transport/injection failures.  Do not treat them as route
negatives or no-BGM evidence.

Static RxCom chain closure after the same-session work:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_rx_chain_0ec_0ee_20260703
```

The target selector path is now statically narrowed to RxCom payload bytes:

```text
fnRxComDirInfo8:
payload[5] -> SdGmData+0x16e
payload[4] -> SdGmData+0x170

fnRxComPreMdl:
SdGmData+0x16e -> SdGmData+0xee
SdGmData+0x170 -> SdGmData+0xec
SdGmData+0xec  -> SdGmData+0x318
SdGmData+0xee  -> SdGmData+0x31a
```

Relevant addresses:

```text
0x4486220  strh w20, [x0, #0x16e]
0x448622c  strh w20, [x0, #0x170]
0x44817fc  ldrh w19, [x0, #0x16e]
0x4481804  strh w19, [x0, #0xee]
0x448180c  ldrh w19, [x0, #0x170]
0x4481814  strh w19, [x0, #0xec]
0x4481d1c  ldrh w19, [x0, #0xec]
0x4481d24  strh w19, [x0, #0x318]
0x4481d2c  ldrh w19, [x0, #0xee]
0x4481d34  strh w19, [x0, #0x31a]
```

This means the next high-value runtime proof is a backtrace/caller capture for
`fnRxComDirInfo8` with nonzero payload bytes.  For the decoded target rows,
`payload[4]` must become stage kind `11/12/13` and `payload[5]` must become
selector `1/2/3/4/13/14`.  Do not spend time blindly expanding
`body_force_main` scans until this dispatcher is understood.

## Generic DirInfoTable / EventInfo dispatch proof

The project should now move away from manual per-`ac` family classification.
Static evidence shows that the game uses a generic table-driven event dispatch:

```text
RxCom payload -> SdGmData -> kind/selector -> DirInfoTable -> EventInfo -> event code
```

New durable evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_dirinfo_table_got_pc_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_eventinfo_got_pc_20260703
```

`survey_aarch64_xrefs.py` now detects `ADRP+ADD/LDR` PC-relative references,
which is required because `DirInfoTable` and `EventInfo` are reached through
GOT loads instead of direct branches.

Confirmed references:

```text
DirInfoTable_GOT 0x4b8ffa0:
0x43ccd7c  C_DirInfoManager::fnGetEventCodeEtlt
0x43cce44  C_DirInfoManager::fnGetActiveTrgEtlt
0x43ccf80  C_DirInfoManager::fnGetActiveEventCodeEtlt

EventInfo_GOT 0x4b8ffa8:
0x43c22cc  C_DirectionControllerBase::Macro_EVENT_PLAY
0x43ccdbc  C_DirInfoManager::fnGetEventCodeEtlt
0x43cce7c  C_DirInfoManager::fnGetActiveTrgEtlt
0x43ccfe0  C_DirInfoManager::fnGetActiveEventCodeEtlt
```

`DirInfoTable` is a 4640-byte object: 290 entries, 16 bytes per kind.  The
decoded `fnGetEventCodeEtlt` shape is:

```text
entry = DirInfoTable + kind * 16
entry+0     -> u16 index grid pointer
entry+8     -> first range/dimension
entry+0xa   -> second range/dimension
grid[...]   -> u16 EventInfo index
EventInfo + index * 24 -> final event code pointer
```

This is the strongest answer so far to the user's concern about token waste:
the correct path is to decode these tables and use the game mechanism for
scene/event discovery, then validate audio/subtitles/runtime timing.  Do not
return to visual matching or `ac` suffix assumptions.

### Decoded global table output

New tool:

```text
tools/frida_runtime_probe/decode_dirinfo_event_tables.py
```

Latest durable output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\dirinfo_event_table_decode_v3_20260703
```

Summary:

```text
DirInfoTable entries: 290
EventInfo records: 9732
relocation values applied: 598516
valid DirInfo grids: 290
route_cell_total: 122028
nonzero route rows: 37266
manifest-mapped unique event codes: 926
resolved route rows: 3908
```

Most useful files for the next AI:

```text
resolved_scene_catalog.csv   # de-duplicated, route-ordered scene candidates
base_scene_summary.csv       # per-base_name grouping and counts
resolved_dirinfo_event_routes.csv
event_info_records.csv
dirinfo_entries.csv
```

Important correction: `DirInfoTable kind` and SP Story `stage_kind` are not the
same field.  The current target scenes decode as:

```text
DirInfo kind 190 -> ac7114 rows, including ac7114_001 at row 0 selector_raw 0
DirInfo kind 191 -> ac7115 rows, including ac7115_001 at row 0 selector_raw 0
DirInfo kind 192 -> ac7116 rows, including ac7116_001 at row 0 selector_raw 0
```

The earlier SP Story object route still uses stage kinds `11/12/13`.  Use names
like `dirinfo_kind` and `sp_story_stage_kind` explicitly in new code and notes.

The decoded scene catalog is a discovery/order source, not an audiovisual trust
proof.  A scene still needs runtime-backed audio/subtitle/BGM/tail evidence
before becoming a final Bilibili-facing long edition.

### Post-power runtime recovery note

After the RAM disk loss/power recovery, the emulator was on Lawnchair.  The game
was relaunched with:

```text
adb -s 127.0.0.1:16384 shell monkey -p com.universal777.magireco -c android.intent.category.LAUNCHER 1
```

The emulator input coordinate system is `2160x3840`; pulled screenshots may
display smaller.  Use physical coordinates, e.g. title
`シミュレーション` around `1080,3000` and game start around `600,2670`.

Gadget recovery evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gadget_reinject_after_power_restore_20260703
```

`gadget_arch=arm64` and `gadget_sees_libGameProc=true`.

Control/audio smoke:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\post_power_restore_bet3_20260703
```

This confirmed `body_state=1/body_mode=1/body_bet=3` after three bet actions and
captured high-level BGM helper calls, event-code requests, and final OpenSL queue
audio (`sound_id=9002`).  The post-power runtime toolchain is usable again.

Do not use `DirInfoTable kind` directly as `body_force_main`: a targeted
`body_force_next_lever=190` test is stored at:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_dirinfo_kind190_probe_20260703
```

It wrote `fnSetForceFlag(190,0)`, got return `-1`, then `fnGetForceFlagKind()`
returned `0`; the script was destroyed and the game returned to launcher.  This
does not disprove ac7114.  It only proves `dirinfo_kind=190` is not the force
selector path.

## 2026-07-03 story lottery and BGM follow-up

New reusable analysis helper:

```text
tools/frida_runtime_probe/disassemble_aarch64_functions.py
```

It dumps named AArch64 ELF functions plus direct branch targets.  The current
story-dispatch disassembly output is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_disasm_story_dispatch_20260703
```

Static findings:

- `fnLot_OT_AT_StryKnd` reads a 19-record static table at `0x2f44406`.
  Each record has eight u16 values and is copied into `SdGmData+0x1f72` through
  `SdGmData+0x1f80`.
- `fnLot_OT_AT_StryChara` reads a 23-record static table at `0x2f44536`.
  Each record has five u16 values and is copied into `SdGmData+0x1f94` through
  `SdGmData+0x1f9c`; `SdGmData+0x1f9e` is a related flag.
- These functions are lottery/candidate-pool setup, not video rendering.

The decoded tables are stored at:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_story_lottery_tables_20260703
```

Runtime probe update:

- `tools/frida_runtime_probe/csl_audio_queue_probe.js` now records those
  `SdGmData+0x1f72..0x1f80` and `+0x1f94..0x1f9e` fields.
- It also hooks `fnLot_OT_AT_StryKnd` as `lot_ot_at_stryknd` and
  `fnLot_OT_AT_StryChara` as `lot_ot_at_strychara`.
- Hook installation was verified in:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\story_lottery_hook_smoke_20260703
```

Natural spin control test:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_spin_story_lottery_probe_20260703
```

This run used `set_debug=0, body_bet x3, body_lever`, with no force kind.  The
game returned to launcher before reel-stop actions, so this is negative/control
evidence only and must not be promoted as video correctness proof.

Useful facts from its summary:

- `lot_ot_at_stryknd/strychara` did not fire in this run.
- `fnReqSndEventCode` fired 7 times and resolved through `EventInfo` to
  `ac0001_001`, `ac9010_060`, `ac9071_001`, `ac9100_001`, `ac9902_001`,
  `ac9903_001`, and `ac9920_001`.
- BGM helper hooks did fire repeatedly:
  `C_ObjNml::fnSndRequest_BGM_DIR_NEXTEv`,
  `fnSndRequest_BGM_FADEEv`, `fnSndRequest_BGM_FADE_NEXTEv`,
  `fnSndRequest_BGM_ENDEv`, `fnSndRequest_BGM_STGEv`, and
  `fnSndRequest_BGM_DIREv` each appeared 76 times.
- One OpenSL queue chunk was captured: `sound_id=9002`, 265884 bytes.

Interpretation: the game runtime definitely has active BGM/sound queue
activity.  The missing-BGM bug in previous rendered clips should be treated as a
pipeline extraction/mixing issue unless a target scene is later proven to have
no event-specific BGM.  Do not claim ac7114/ac7115/ac7116 have no BGM merely
because prior renders lacked it.

After this failed natural-control run, the game was restored to the slot main
screen and Gadget was re-injected:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\recover_after_natural_spin_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\restore_after_natural_spin_reinject_20260703
```

## 2026-07-04 SdGmData lottery-dispatch checkpoint

Read this report before doing more SP Story force or render work:

```text
docs/research/2026-07-04-sdgm-lottery-dispatch-route.md
```

Evidence roots:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_mem_offsets_sdgm_lottery_source_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_sdgm_lottery_source_candidates_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_force358_on_lotdirstart_real_input_20260704
```

The dispatch chain now proved:

```text
fnRxComDirInfo3 payload[6] = 8
  -> SdGmData+0x130
  -> fnRxComPreMdl copies +0x130 to +0x0a8
  -> fnRxComPreMdl copies +0x0a8 to +0x184
  -> fnRxComPreMdl copies +0x184 to +0x358
  -> fnLotDirGmStart writes SdGmData+0x13be = 16
  -> fnLotOther_AfterGetParam calls:
       fnLot_OT_AT_StryKnd(0)
       fnLot_OT_AT_SpStryKnd()
       fnLot_OT_AT_StryChara()
```

This was proved two ways:

- statically, from `fnLotDirGmStart` and `fnLotOther_AfterGetParam`
  disassembly;
- dynamically, by a one-shot `fnLotDirGmStart` entry write of
  `SdGmData+0x358=8`, which produced `SdGmData+0x13be=16` and triggered
  `lot_ot_at_stryknd` / `lot_ot_at_strychara` hooks.
- statically upstream, by base-aware SdGmData scanning:
  `fnRxComDirInfo3 payload[6] -> +0x130 -> +0x0a8 -> +0x184 -> +0x358`.

Do not overclaim this.  The same run did not observe
`C_ObjStageAT_SP_Story::*` object hooks, and it did not prove the natural writer
of `SdGmData+0x358`.  The force-on-entry control is a mechanism proof only, not
final production evidence and not enough to promote Bilibili-facing videos.

Latest natural observation:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_natural_dirinfo3_chain_real_input_20260704
```

It observed `fnRxComDirInfo3 payload=[29,1,1,0,0,8,0,19]`.  Because
`payload[6]=0`, the `+0x130 -> +0x0a8 -> +0x184 -> +0x358` chain stayed zero.
The `8` at `payload[5]` is not the lottery-dispatch field.

Latest ID401 dispatcher closure:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_task_entry_real_input_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_task_entry_real_input_20260704\summary_light_id401_task_entry.json
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_id401_access_subprocess_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_id401_pio_task_table_20260704
```

`ID401::accessSubProcess(unsigned char*)` reads `packet[0] & 0x7f`, looks up a
runtime PIO task-table entry through `fnPioTaskTbl_SearchTblApp`, `rev64`s the
first eight packet bytes, then passes that reversed 8-byte stack buffer to the
`fnRxCom*` callbacks.  This means the `fnRxComDirInfo3 payload` logged by the
callback hook is not the original raw packet order.

The current real-input packet for `fnRxComDirInfo3` was:

```text
raw packet        = [19, 0, 8, 0, 0, 1, 1, 29]
packet_id         = 19
callback0         = fnRxComDirInfo3
callback payload  = [29, 1, 1, 0, 0, 8, 0, 19]
caller            = CSlotBody::analysPacket()+0x2b4
```

Therefore the natural route condition should now be written as either:

```text
fnRxComDirInfo3 callback payload[6] = 8
```

or, more precisely at the upstream packet level:

```text
ID401 packet id 19 with raw_packet[1] = 8
```

The observed ordinary packet had `raw_packet[1]=0`; its `8` was at raw byte 2
and only becomes callback `payload[5]`, which is not this lottery-dispatch
field.  The next reverse-engineering target is the producer feeding
`CSlotBody::analysPacket()` / `ID401::accessSubProcess()` with packet id 19,
not another broad `ac` or force-kind scan.

Important static-analysis warning: raw offset scans for `0x358` are polluted by
other structures such as `C_ObjStageAT_SP_Story+0x358` event-code fields.  A
candidate `+0x358` write is not a `SdGmData+0x358` write unless the base register
is proven to come from `fnGetAddrSdGmData()`.

## Immediate next tasks

0. Keep evidence durable after the RAM-disk loss.
   - Current durable immediate work root:
     `D:\magia\MyProducts\casino`.
   - A: is restored 2026-06-29 data plus disposable RAM-disk scratch.  Do not
     make A: the only copy of new evidence.
   - Read the 2026-07-04 lightweight-probe report before doing more runtime
     input work:

```text
docs/research/2026-07-04-lightweight-real-input-audio-probe.md
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_physical_bet_calibration_20260704
```

   - Do not use the heavy full CSL/backtrace observer for real spin input.  The
     run at
     `D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\physical_input_spin_observe_20260704`
     crashed with the native stack top in Frida Gadget; treat it as
     observer-induced instability, not as game-flow evidence.
   - Preferred real-input observer:
     `tools/frida_runtime_probe/lightweight_spin_audio_probe.js`.
   - Corrected physical coordinates: lever about `300,2680`; stop buttons
     about `830,2700`, `1080,2700`, `1320,2700`; BET candidate about
     `620,2475` to `620,2520`.  Do not reuse old stop `y=2860`.

1. Prove whether the ac7114-16 scene has additional BGM.
   - The visual-tail gate for `ac7114_001`, `ac7115_001`, and `ac7116_001` is
     now runtime-mechanism proven by the 2026-07-03 Z2D captures.
   - Do not remove `420xx_SPストーリー...`; it is current bed/base-scene audio.
   - Capture the outer state and `CSLAndroidSimpleBufferQueue::Enqueue` queue
     while the scene is reached through the real SP Story selector if possible.
   - Use high-level BGM hooks in `runtime_probe.js` or the combined CSL+BGM
     probe in the same run.
   - The 2026-07-04 lightweight ordinary-spin run captured final queue
     `sound_id=9002/60/61` and repeated BGM helper activity, but it did not
     reach SP Story: `fnRxComDirInfo8` payload `[4]/[5]/[6]` stayed `0`, and
     `fnLot_OT_AT_StryKnd/Chara` plus `C_ObjStageAT_SP_Story` hooks did not
     fire.  Use it as instrumentation proof only.
   - Until BGM/bed presence is proven or proven absent, keep the v19 long scene
     as review-only.

2. Find the real SP Story selector before more force-kind scanning.
   - `body_force_main` kinds `0..19` are now ruled out for ac7114-16.
   - The new lottery-dispatch route proves `SdGmData+0x358=8` is sufficient to
     reach `SdGmData+0x13be=16` and story kind/character lottery, but the
     natural condition for `fnRxComDirInfo3 payload[6]=8` is still unknown.
   - Because `ID401::accessSubProcess` byte-reverses the raw packet before
     callback dispatch, the upstream producer condition is packet id 19 with
     `raw_packet[1]=8`, not the ordinary observed packet where the value `8`
     sat at raw byte 2 / callback `payload[5]`.
   - Use the expanded lightweight probe hooks around `fnRxComGmStart`,
     `fnInitGmData_GmStart`, `fnKndCalLot_Start/PreMdl`, and
     `fnKndCalUsr_SetGR_DirPrmCopy` plus `fnRxComDirInfo3` to find when
     `payload[6]` becomes `8`.
   - The current static route is
     `MSTCOMCBK()+0x2376 -> C_AnmBase+0x318` plus
     `SdGmData+0x788 -> MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a ->
     C_ObjStageAT_SP_Story+0x34a`.
   - Run the combined CSL/BGM/SP Story probe and inspect
     `runtime_rxcom_dir_flow.csv`, `runtime_gr_dir_prm_copy.csv`, and
     `runtime_anm_dir_data.csv` to observe which stage/selector values
     correspond to the decoded target rows:
     stage `11`/`12`/`13` with selectors `1`/`2`/`3`/`4`/`13`/`14`.

3. Generalize the mechanism instead of manually processing every `ac` family.
   - Use runtime event-code dispatch, GDB/Z2D/DGM timing, sound-code/request
     resolution, and final queue evidence.
   - The target is a pipeline that can decide: normal story animation, same
     scene continuation, gameplay/material, foreground-only, or blocked pending
     evidence.

4. Re-audit known-good v15 families for long-edition delivery.
   - `ac1102`, `ac1103`, `ac1104`, and food/restaurant samples are likely
     high-value because the user already found them acceptable.
   - Keep original per-event files.
   - Build same-scene/family long versions only after current AV trust gates
     pass.

5. Keep material collections separate.
   - Small Kyubey / black-screen / CHANCE / PUSH / reel / gold-frame / particle
     effects can be combined into material videos.
   - If role voice appears, it is not pure material and must be handled as
     animation or gameplay-with-role-voice, not silently thrown into a material
     collection.

6. Preserve auditability.
   - Every new output needs manifest, source hash, event index, cumulative
     timeline, subtitle source, audio source, and QA report.
   - Broad batch work should begin with dry-run or small-batch validation.

## Acceptance gates for final Bilibili-facing output

An output is not final until all are true:

- source events are explicitly selected and documented;
- clean story excludes slot foreground/gold-frame/particle layers unless the
  user explicitly wants a gameplay/material collection;
- role voices and subtitles align with game runtime evidence;
- BGM/bed/SE presence is proven or explicitly proven absent by runtime
  evidence;
- visual tail-hold is runtime-confirmed when render duration exceeds native
  video duration by a visible amount;
- subtitle and no-subtitle editions have identical audio;
- native resolution and frame rate are preserved;
- no upscale, no accidental 1080p workflow;
- scene/family long videos include cumulative timeline and source hashes;
- the user can inspect a small validation sample before broad promotion.

## Practical warning for the next AI

The most expensive mistake so far was treating technically valid renders and
contact sheets as if they proved audiovisual correctness.  They do not.  A
short clip with a playable H.264/AAC stream can still have wrong BGM, wrong
voice timing, wrong subtitles, or wrong visual state.

Continue from runtime evidence first, then render.  If a render looks good but
the manifest cannot explain every voice, subtitle, bed/BGM, SE, visual layer,
and tail extension, keep it out of final delivery.

## 2026-07-04 full physical-spin summary update

The latest durable post-outage evidence is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704
```

It was captured with lightweight observer + ADB physical taps, not the unstable
long `force_selector_probe --control-sequence` path.  MuMu/ADB state at the
time of the update:

```text
device:     emulator-5554
game PID:   4207
resolution: 2160x3840
ports:      127.0.0.1:27042 and 127.0.0.1:27043 listening
```

Use the new parser:

```powershell
python tools\frida_runtime_probe\summarize_lightweight_spin_probe.py `
  D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704\observer_light_id401_cmd_buffer_full_spin_adb_continuation.jsonl `
  --prefix summary_lightweight_spin_probe_v2
```

Generated outputs in the same evidence directory:

```text
summary_lightweight_spin_probe_v2.json
summary_lightweight_spin_probe_v2_packets.csv
summary_lightweight_spin_probe_v2_rxcom.csv
summary_lightweight_spin_probe_v2_lottery.csv
summary_lightweight_spin_probe_v2_bgm.csv
summary_lightweight_spin_probe_v2_queue.csv
summary_lightweight_spin_probe_v2_event_codes.csv
summary_lightweight_spin_probe_v2_play_start.csv
```

Key facts:

- observer size: 6,232,052 bytes
- packet observations: 9,660, including repeated LC701A staging snapshots
- unique raw packet forms: 35
- DirInfo3 packet observations: 768
- target candidates: 0
- RxCom rows: 6
- lottery rows: 10
- BGM helper rows: 162
- final audio queue rows: 2
- hook errors: 0
- parse errors: 0

The run reached real slot state changes:

```text
body_state/body_mode: 1, 2, 3
credit:               50, 49, 48, 47
bet:                  0, 1, 2, 3
input masks:          0, 8, 32, 524288
```

The complete command buffer contained ordinary `fnRxComDirInfo3` packet:

```text
raw packet = [19, 0, 8, 0, 0, 1, 1, 29]
```

This is not the target route.  The target remains:

```text
packet_id == 19
raw_packet[1] == 8
```

The ordinary run has `raw_packet[2]=8`.  After `ID401::accessSubProcess()` byte
reversal, that becomes callback payload byte 5, not byte 6, so it does not feed
the proved `SdGmData+0x358=8` story-dispatch path.  All sampled SdGmData
story-dispatch fields stayed zero.

The same run did see outer slot sound activity:

```text
BGM helper calls: 162
final queue sound_id: 9002
final queue sound_id: 60
```

This proves normal slot play can request BGM helpers and final queue chunks, but
it is not target SP Story evidence.  Therefore the target-scene BGM/bed gate is
still open.  Do not say ac7114/ac7115/ac7116 have no BGM merely because old
renders or forced-path captures lacked a separate BGM stream.

For a human-readable project-distance summary, read:

```text
docs/HUMAN_PROGRESS_REPORT_2026-07-04.md
```

### 2026-07-04 follow-up after PLT/static correction

Do not trust old static disassembly labels that identify PLT calls by nearest
containing symbol.  The tools now resolve AArch64 PLT imports from
`.rela.plt/.dynsym/.dynstr`, and this changes the interpretation of the LC701A
code path.  The important helper calls are:

```text
memset
memcpy
ID401::CLC701A::_JP(unsigned short)
ID401::CLC701A::_RET()
ID401::CLC701A::ASM_0xA7()
ID401::CLC701A::ASM_0xF8()
ID401::CLC701A::ASM_0xAF()
ID401::CLC701A::SET_ENC_SUBFUNC()
ID401::CLC701A::RESET_ENC_SUBFUNC()
ID401::fnGameLot_Force_TPL_Request()
ID401::fnGameLot_Force_TPL_Reset()
```

`USER_LABEL_WORK()` is a LC701A PC dispatch (`this+0x20`).  PC `0x58a`, PC
`0x1156`, and `SET_BANKBUFFER()` copy staging bytes from `this+0xf298` /
`this+0xf0fe` into queue `this+0x200ee`.  Therefore the remaining producer-side
problem is inside the LC701A VM/helper execution before this copy, not in
`CSlotBody::analysPacket()`.

Re-run summary output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704\summary_lightweight_spin_probe_v4.json
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704\summary_lightweight_spin_probe_v4_lc701a_enter_sequence.csv
```

Observed facts:

- `USER_LABEL_WORK` enter-sequence rows: 2448
- rows where staging changed: 32
- enter/leave staging changes: 0
- target candidate count: 0

The ordinary DirInfo3 packet was built byte-by-byte between consecutive
`USER_LABEL_WORK` enter snapshots:

```text
19 0 0 0 0 0 0 0
19 0 8 0 0 0 0 0
19 0 8 0 0 1 0 0
19 0 8 0 0 1 1 0
19 0 8 0 0 1 1 29
```

This proves the trace method works, but the target remains raw byte 1:

```text
packet_id == 19 && raw_packet[1] == 8
```

Next run should use the updated
`tools/frida_runtime_probe/lightweight_spin_audio_probe.js`; it now has
low-noise LC701A command-state-change hooks for `_OUTI/_OUTIC/_IN/_INI/_INIC`,
`_JP/_RET/_RETEX`, `ASM_0xA7/0xAF/0xF8`, and enc-subfunc toggles.  These hooks
only emit when the ID401 staging or queue signature changes.  Use them to find
the exact helper responsible for writing DirInfo3 raw byte 1/2 during a natural
spin.

### 2026-07-04 follow-up: packet byte writer opcode candidates

The first follow-up ready-state capture that actually entered packet building:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_state_change_from_ready_20260704
```

Summary:

- packet observations: 1436
- unique packet forms: 10
- LC701A enter-sequence staging changes: 10
- DirInfo3 packet observations: 0
- target candidates: 0
- hook errors: 0

This run is not target SP Story evidence, but it identifies the ordinary packet
byte-builder PC pattern:

```text
101/102/113/114 decimal == 0x65/0x66/0x71/0x72
```

Static disassembly:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_packet_builder_opcodes_20260704
```

Interpretation:

- `ASM_0x71` writes register byte `this+0x04` into LC701A VM RAM.
- `ASM_0x72` writes register byte `this+0x07` into LC701A VM RAM.
- The write address is `this+0x88+addr` when `addr >= 0x4000`.
- ID401 command staging `this+0xf298` equals VM address `0xf210` plus the
  `this+0x88` base, so these opcodes are concrete packet-staging byte writer
  candidates.

`lightweight_spin_audio_probe.js` now also hooks:

```text
ID401::CLC701A::ASM_0x65()
ID401::CLC701A::ASM_0x66()
ID401::CLC701A::ASM_0x71()
ID401::CLC701A::ASM_0x72()
```

Next handoff action: relaunch from the title if needed, enter simulation, reach
a stopped/ready state, then capture a clean lever/stop sequence with the updated
probe.  The success condition is seeing `lc701a_asm_71_command_state_change` or
`lc701a_asm_72_command_state_change` rows that explain packet byte writes.  A
later capture installed the hooks but did not enter packet building; do not use
that failed-input capture as a negative result.

### 2026-07-04 latest correction: PC values are not opcode ids

The previous handoff action above is now superseded.  Do not continue assuming
that PC `101/102/113/114` means opcode `ASM_0x65/0x66/0x71/0x72`.  A later
full-opcode trace proved those values are LC701A program counter values, not
the opcode helper numbers.

Current tool behavior:

```text
tools/frida_runtime_probe/lightweight_spin_audio_probe.js
```

now installs low-noise command-state-change hooks for all opcode helpers:

```text
ID401::CLC701A::ASM_0x00() through ID401::CLC701A::ASM_0xff()
```

Only helpers that actually change ID401 staging or queue signatures are emitted,
so this is suitable for normal physical-input captures without returning to the
very noisy full observer path.

Corrected stop coordinates for the current 2160x3840 MuMu state:

```text
BET:   about 620,2475
lever: about 300,2670
stop:  about 820,2670 / 1080,2670 / 1360,2670
```

Latest durable capture:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_full_opcode_bet_lever_corrected_stops_20260704
```

Current live runtime at the time this correction was written:

```text
device:   emulator-5554
game PID: 5294
ports:    127.0.0.1:27042 and 127.0.0.1:27043 listening
```

If the app is relaunched again, re-check PID and re-run Gadget reinjection
before relying on port `27043`.

Generated with:

```powershell
python tools\frida_runtime_probe\summarize_lightweight_spin_probe.py `
  D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_full_opcode_bet_lever_corrected_stops_20260704\observer_light_lc701a_full_opcode_bet_lever_corrected_stops.jsonl `
  --out-dir D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_full_opcode_bet_lever_corrected_stops_20260704 `
  --prefix summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2
```

Important files:

```text
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2.json
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2_command_state_changes.csv
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2_lc701a_enter_sequence.csv
summary_light_lc701a_full_opcode_bet_lever_corrected_stops_v2_packets.csv
```

Key facts from that run:

```text
packet observations:             155
unique raw packet forms:         6
DirInfo3 packet rows:            0
target candidates:               0
BGM helper rows:                 468
slot event rows:                 1096
hook errors:                     0
command-state-change rows:       7
command-state-change opcodes:    ASM_0x7e x5, ASM_0x77 x2
```

Observed ordinary packet construction:

```text
ASM_0x77: pending_len 0 -> 8
ASM_0x7e: byte 0 -> 4
ASM_0x7e: byte 1 -> 1
ASM_0x7e: byte 2 -> 3
ASM_0x7e: byte 3 -> 156
ASM_0x7e: byte 4 -> 240
ASM_0x77: byte 7 -> 148
```

Static disassembly for the real writer opcodes:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_packet_writer_opcodes_77_7e_20260704
```

Interpretation:

- `ASM_0x77` is a single-byte VM RAM store from a register byte; in this run it
  also creates the 8-byte pending staging window and writes the final
  tail/check byte.
- `ASM_0x7e` is a one-byte VM RAM copy from source address to destination
  address; in this run it fills packet body bytes.
- The success condition for the next target run is no longer "see 0x71/0x72".
  It is "capture the packet id 19 byte construction and identify which opcode
  writes raw byte 1".  The target remains:

```text
packet_id == 19 && raw_packet[1] == 8
```

This is the highest-value next mechanism task.  Once the natural producer of
that packet is found, connect the same run to SP Story stage/selector values and
final audio queue/BGM state before doing Bilibili-facing mass renders.

### 2026-07-04 latest runtime sample: DirInfo3 ordinary packet byte attribution

After the correction above, another stopped/ready physical-input spin was
captured with the all-opcode hook:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_full_opcode_spinscan_20260704_01
```

Generated summary:

```text
summary_light_lc701a_full_opcode_spinscan_20260704_01.json
summary_light_lc701a_full_opcode_spinscan_20260704_01_command_state_changes.csv
summary_light_lc701a_full_opcode_spinscan_20260704_01_packets.csv
summary_light_lc701a_full_opcode_spinscan_20260704_01_rxcom.csv
summary_light_lc701a_full_opcode_spinscan_20260704_01_queue.csv
summary_light_lc701a_full_opcode_spinscan_20260704_01_bgm.csv
```

Key facts:

```text
observer bytes:                  6,671,629
packet observations:             10,034
unique raw packet forms:         29
DirInfo3 packet observations:    815
target candidates:               0
hook errors:                     0
BGM helper rows:                 234
final queue rows:                1
slot event rows:                 2,338
LC701A enter-sequence changes:   25
command-state-change rows:       37
command-state-change opcodes:    ASM_0x7e x17, ASM_0x77 x20
```

Observed DirInfo3:

```text
raw packet       = [19, 0, 6, 0, 0, 1, 0, 26]
callback payload = [26, 0, 1, 0, 0, 6, 0, 19]
```

This is ordinary non-target routing:

```text
raw_packet[1] = 0
raw_packet[2] = 6
```

The useful part is byte attribution:

```text
line 5283: ASM_0x7e creates DirInfo3 staging slot 48:
           19 0 0 0 0 0 0 0
line 5288: ASM_0x7e writes slot 50: 0 -> 6
line 5295: ASM_0x7e writes slot 53: 0 -> 1
line 5320: ASM_0x77 writes slot 55: 0 -> 26
```

RxCom confirmation:

```text
rxcom_dirinfo3_enter payload = 26 0 1 0 0 6 0 19
all sampled SdGmData story-dispatch fields stayed 0
```

Audio confirmation in the same run:

```text
BGM helper kinds:
  obj_nml_snd_request_bgm_dir       39
  obj_nml_snd_request_bgm_dir_next  39
  obj_nml_snd_request_bgm_end       39
  obj_nml_snd_request_bgm_fade      39
  obj_nml_snd_request_bgm_fade_next 39
  obj_nml_snd_request_bgm_stg       39

final queue:
  sound_id=60, 286,788 bytes
```

Next instrumentation improvement:

- add opcode-specific register/source/destination snapshots for `ASM_0x7e` and
  `ASM_0x77`;
- for `ASM_0x7e`, record destination address, source address, count field, and
  source byte before/after;
- for `ASM_0x77`, record destination address and register byte source;
- then rerun stopped/ready spins until the target packet id 19 appears with
  raw byte 1 nonzero, ideally `8`.

This is more valuable than another blind render run because it directly attacks
the generic scheduler mechanism.

### 2026-07-04 opcode address/source-field probe validation

The probe and summarizer were enhanced as described above:

```text
tools/frida_runtime_probe/lightweight_spin_audio_probe.js
tools/frida_runtime_probe/summarize_lightweight_spin_probe.py
```

New command-state CSV columns include:

```text
lc701a_addr06_before / lc701a_addr08_before
asm7e_dst_addr_before / asm7e_src_addr_before
asm7e_count_before
asm7e_src_byte_before / asm7e_dst_byte_before
asm77_dst_addr_before
asm77_src_reg_before / asm77_dst_byte_before
```

Validation capture:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_opcode_addr_spinscan_20260704_01
```

This capture did not emit DirInfo3, so it is not target evidence.  It does
validate the new address/source fields:

```text
ASM_0x7e:
  dst 0xf210 <- src 0xfff3, byte 4
  dst 0xf211 <- src 0xfff4, byte 1
  dst 0xf212 <- src 0xfff5, byte 3
  dst 0xf213 <- src 0xfff6, byte 156
  dst 0xf214 <- src 0xfff7, byte 240
  dst 0xf215 <- src 0xfff8, byte 1

ASM_0x77:
  dst 0xf217 <- register byte 149
```

Next run should aim for a longer result-window capture or a state where
DirInfo3 is known to occur, using the same enhanced fields.  When DirInfo3
appears, inspect whether packet slot `0xf211` / raw byte 1 is copied from a
specific VM source address and why it remains `0` in ordinary runs.

### 2026-07-04 latest: DirInfo3 source address found and zero-write logging added

A longer result-window capture with the enhanced source/destination fields did
reach ordinary DirInfo3:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_opcode_addr_dirinfo3_try_20260704_02
```

Summary:

```text
observer bytes:                  10,755,212
packet observations:             10,034
unique raw packet forms:         29
DirInfo3 packet observations:    815
target candidates:               0
hook errors:                     0
BGM helper rows:                 402
final queue rows:                1
command-state-change rows:       37
```

The packet remained ordinary non-target:

```text
raw packet       = [19, 0, 6, 0, 0, 1, 0, 26]
callback payload = [26, 0, 1, 0, 0, 6, 0, 19]
```

Important source-address attribution:

```text
line 6409: ASM_0x7e  staging 0xf240/raw[0] <- source 0xffef, byte 19
line 6414: ASM_0x7e  staging 0xf242/raw[2] <- source 0xfff1, byte 6
line 6421: ASM_0x7e  staging 0xf245/raw[5] <- source 0xfff4, byte 1
line 6446: ASM_0x77  staging 0xf247/raw[7] <- register byte 26
```

Raw byte 1 did not appear in the change-only table because ordinary raw byte 1
is `0` and writing `0` to an already-zero staging byte does not change the
staging signature.  To close that gap, the probe now emits explicit
`*_staging_write` rows for every `ASM_0x7e/0x77` write into the command staging
VM range, even when the value does not change.

New summarizer output:

```text
summary_<run>_opcode_staging_writes.csv
```

It includes:

```text
dst_addr_hex
src_addr_hex
packet_offset
packet_byte_index
src_byte_before / src_reg_byte_before
dst_byte_before / dst_byte_after
is_dirinfo3_raw_byte1
is_dirinfo3_raw_byte2
```

Validation run for this new CSV:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_staging_write_dirinfo3_try_20260704_01
```

That validation run did not reach DirInfo3, but its v2 CSV shows the intended
ordinary packet mapping:

```text
0xf210 <- 0xfff3 byte 4
0xf211 <- 0xfff4 byte 1
0xf212 <- 0xfff5 byte 3
0xf213 <- 0xfff6 byte 156
0xf214 <- 0xfff7 byte 240
0xf215 <- 0xfff8 byte 1
0xf216 <- 0xfff9 byte 0
0xf217 <- ASM_0x77 register byte
```

Next highest-value action: run the new `*_staging_write` probe until DirInfo3
appears again.  Then inspect the row where `is_dirinfo3_raw_byte1=True`.  This
should identify the ordinary raw byte 1 source address and make the target
condition (`raw[1]=8`) a concrete VM source-byte problem instead of a black-box
packet problem.

### 2026-07-04 latest: raw byte 1 source identified

The new staging-write table did capture DirInfo3 in:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_staging_write_dirinfo3_try_20260704_02
```

Key summary:

```text
observer bytes:                    11,101,512
packet observations:               10,034
DirInfo3 packet observations:      815
target candidates:                 0
opcode staging writes:             96
DirInfo3 raw byte 1 staging rows:  1
DirInfo3 raw byte 2 staging rows:  1
hook errors:                       0
```

Critical rows:

```text
raw[0]: 0xf240 <- 0xffef, byte 19
raw[1]: 0xf241 <- 0xfff0, byte 0
raw[2]: 0xf242 <- 0xfff1, byte 6
raw[3]: 0xf243 <- 0xfff2, byte 0
raw[4]: 0xf244 <- 0xfff3, byte 0
raw[5]: 0xf245 <- 0xfff4, byte 1
raw[6]: 0xf246 <- 0xfff5, byte 0
raw[7]: 0xf247 <- ASM_0x77 register byte 26
```

This is an important narrowing.  The target `packet_id=19 && raw_packet[1]=8`
is now specifically:

```text
LC701A VM source byte at 0xfff0 must be 8 when ASM_0x7e copies DirInfo3.
```

A follow-up source-window run:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_source_watch_full_spin_20260704_01
```

did not reach DirInfo3, but did prove the source-window signature catches
writers of `0xfff0/0xfff1`:

```text
ASM_0x48 changed 0xfff0:32->86 and 0xfff1:17->0
ASM_0x4a changed 0xfff0:86->91
ASM_0xd9 changed 0xfff0:91->16 and 0xfff1:0->242
```

Static disassembly outputs:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_source_watch_opcode_48_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_source_watch_opcode_4a_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_source_watch_opcode_d9_20260704
```

Interpretation:

- `ASM_0x48` decrements the LC701A stack pointer at `this+0x0e` by 2, stores a
  computed PC/control value as two bytes to `this+0x88+stack`, and updates
  `this+0x20` from a bytecode operand.
- `ASM_0x4a` is similar, but ORs the next PC/control byte with `0x200` before
  writing it back to `this+0x20`.
- `ASM_0xd9` decrements the same stack pointer by 2 and stores the u16 at
  `this+0x06` into the VM stack/source area.

Next target for the next AI:

```text
Run full source-window captures until DirInfo3 and source-window changes are in
the same JSONL.  Filter command_state_changes.csv for source_watch_changed_bytes
touching 0xfff0 and compare the last source value before the DirInfo3
staging_write row.  Then statically trace what state/bytecode path sets the
register or PC/control value that reaches 0xfff0.
```
