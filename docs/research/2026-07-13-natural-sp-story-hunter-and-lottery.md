# 2026-07-13 natural SP Story hunter and static lottery audit

This is the authoritative delta after the 2026-07-12 reconnect report.  Read
it together with `docs/HANDOFF_NEXT_AI_MAGIRECO.md`.  It records mechanism
evidence and failures as failures; it does not promote any new video.

The owner-facing Chinese summary of the static/dynamic boundary, three-edition
subtitle requirement, CDN/high-resolution research track, GitHub state, and
catalog-scale completion gap is `docs/HUMAN_PROGRESS_REPORT_2026-07-13.md`.

## 2026-07-14 reconnect addendum

After MuMu restart the foreground PID is 3125; PID3083 is now historical.  A
direct x86 server smoke failed closed without input because that view is x64
and cannot resolve ARM64 gameplay exports.  ARM64 Gadget reinjection then
succeeded.  The successful read-only smoke captured all 65 CSL slots at both
endpoints, no truncation, no active rows and no ADB gameplay input.

Three bounded rounds then completed in 3.934/4.013/3.898 seconds.  Every round
accepted five one-shot controls, observed exact reel axes 0/1/2 and seven real
dispatch batches, and ended without overflow.  Every ID19 was
`19 0 2 0 0 1 0 22`, so no legal target existed.  ID304 remained present after
all three rounds but is still transport evidence only.  Durable hashes:

```text
x86 failed smoke journal  76024DABC98C089D9EC18C13D71079DAEE90E1EC405EF2D5711C29694356F887
ARM64 reinject summary     179E136AF6E2B5B1DC0C90691F1F625C3D48CDD46F68CAA57DE7BF2BCB653AC5
ARM64 read-only journal    E7BA647DDFBC8B166478367B53669D7786EBE4247DB4A442AAD9C661D4A941C1
three-round journal        5A1D45FEF85D9EE706907172FFE7229FEBD592B43DF1F8FE7B572804EB3E6E6C
```

Official store text adds a new BGM provenance gate: the separately sold Sound
Pack unlocks main normal-play BGM and bonus music.  Installed SMZ data alone
does not prove current entitlement, volume or native playback state.  A silent
run must not be promoted as proof that the original route has no BGM.

## Outcome in plain language

The ac7114/ac7115/ac7116 clean story files are still the nearest publication
target.  Their clean picture, role voice, subtitles, subtitle/no-subtitle
editions, and 44.854-second same-scene editions survive on D:.  They are not
final because the outer gameplay BGM/active-player state has not yet been
proved in the same natural target run.  A bounded CSL active-transport snapshot
is now implemented; the remaining claim is narrower and harder: bind it to ZG
or equivalent authoritative playback identity and prove BGM semantics.

This checkpoint replaces manual button timing with a generic state-driven
hunter.  It also statically decodes the complete five-table SP Story kind
lottery.  No legal ac7114/ac7115/ac7116 target batch was captured during this
checkpoint, so the BGM gate remains open.

## Durable locations and code authority

```text
worktree  C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
branch    codex/corrected-runtime-pipeline
assets    D:\magia\MyProducts\casino\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
evidence  D:\magia\MyProducts\casino\runtime_recovery_20260713
```

The D: asset checkout is still obsolete local `main` and must not receive code
changes.  A: remains disposable scratch only.

## Natural hunter

New files:

```text
tools/frida_runtime_probe/natural_sp_story_hunt.py
tools/frida_runtime_probe/sp_story_dispatch_hunt_probe.js
test_natural_sp_story_hunt.py
test_sp_story_dispatch_hunt_probe.py
```

The command is read-only unless `--execute` is supplied.  One Gadget session
owns the logical state, packet, and sound observers.  Before any input it
requires the foreground package and PID to remain unchanged and drains the
observer queue to a live waterline.  Every control is issued once; missing or
ambiguous confirmation fails closed and is never automatically repeated.

The legal target matrix is deliberately narrow:

| stage | selectors | resolved event | exact event code | scene key |
| ---: | --- | --- | --- | --- |
| 11 | 1, 2 | ac7114_001 | `0x4f71466b3d723041` | `A0r=kFqO` |
| 12 | 1, 2, 3, 4 | ac7115_001 | `0x5773382374447854` | `TxDt#8sW` |
| 13 | 1, 2 | ac7116_001 | `0x2476304366614152` | `RAafC0v$` |

Selectors 13 and 14 at stage 12 belong to ac7115_013 and are rejected.  A hit
requires one real `accessSubProcess` batch containing ID19 with
`(raw[0] & 0x7f) == 19 && raw[1] == 8` and a legal ID24 pair.  The exact event
code must then be observed after the same lever host-time and sequence
waterline.  Staging snapshots or a Cartesian product of packets are invalid.

The live hunt no longer loads the old high-volume staging/stack observer.  Its
minimal dispatch probe hooks only `ID401::getCmdBuf`, the real
`ID401::accessSubProcess` dispatch, exact scene/sound event-code requests, and
the low-frequency SP Story kind lottery.  It performs no memory scan, PCM/media
dump, stack capture, or backtrace.  Under Houdini the ARM64 game mapping is
physically named `split_config.arm64_v8a.apk`; the probe therefore resolves the
owner of a game-specific export instead of assuming the loader display name is
`libGameProc.so`.

### Correct stop authority

Earlier reports said a nonzero `CSlotBody::process` input was acceptance proof.
That is required for MAX BET and lever, but is only routing corroboration for a
reel stop.  Static and runtime evidence now separates four layers:

1. touch input reaches `process` as bit 2, 4, or 8;
2. `CSlotBody::STOP` and `calcStop` pass their internal wait gates;
3. `CReel::setStopAngle(int,int)` is called for axis 0, 1, or 2;
4. `state+0x64` accumulates `0x200000`, `0x600000`, then `0xe00000`.

Key ARM64 addresses in `libGameProc.so` SHA-256
`5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf`:

```text
CSlotBody::STOP                 0x4251908
CSlotBody::calcStop             0x425279c
CSlotBody::updateReel           0x4253058
CReel::setStopAngle             0x424a888
```

In the normal non-FastAuto path, STOP increments `body+0x538`; the old value
must reach 15, after which the stored value is 16 and `calcStop` is entered.
`calcStop` also requires `body+0x53c >= 5` and `body+0x540 == -1`.  The latter
becomes the selected axis until `updateReel` consumes it.  These bounded fields
are now exposed by `slot_state_gate_probe.js`, and the probe also hooks the
low-frequency mangled symbol `_ZN5CReel12setStopAngleEii`.

The state age at `state+0x08 >= 17` is a corroborating normal-mode proxy, not a
universal FastAuto/RLES rule.  The authoritative post-input proof for STOP is
the exact post-gesture `setStopAngle` axis together with the cumulative progress
mask; a sampled process callback may be absent under load.  MAX BET and lever
still require their exact process bits.  Button colour, `body+0x454/+0x455`,
and the progress mask by itself are not readiness gates.

Because the old three-probe combination could stall render sampling, a very
short ADB `tap` could be lost even at a valid coordinate.  A single 500 ms
stationary swipe was tested for MAX BET, lever, and each stop.  It spans
multiple render frames but remains one bounded gesture.  The hunter records
the gesture type and duration and still refuses to repeat it; the minimal
observer now removes the high-volume source of that slowdown.

### Trial audit

Durable journals are under:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260713\evidence\natural_sp_story_hunt_*
```

Important failures and what they proved:

- `_execute_one_..._06`: MAX BET, lever, and a left input bit were observed,
  but `state+0x64` stayed zero.  The left reel had not logically stopped; moving
  to middle was invalid.  This produced the new progress postcondition.
- `_execute_one_..._07` and `_08`: the first stop gesture was too short under
  probe load and did not reach `process`; the tool did not retry.  Separate
  calibration proved one 500 ms gesture advances the exact progress mask.
- `_execute_one_..._09`: a short MAX BET tap was lost, again without retry.
  MAX BET and lever were then independently calibrated with the same bounded
  500 ms gesture.
- The running app later crashed back to Lawnchair after about 6559 seconds of
  app lifetime.  Old PID 3189 / GLThread 40 hit a Houdini illegal executable
  address and then SIGSEGV/SEGV_MAPERR at `0xdead1005`.  The available stack is
  insufficient to attribute the crash to one hook or game function.  This is a
  runtime failure, not a target result.  Durable evidence is
  `evidence\crash_pid3189_20260713_01` under the recovery root.
- A later clean-order instance, PID 8528, also crashed in GLThread with the same
  Houdini signature as PID 3189: illegal non-executable PC
  `0xaa0003f3910003fd`, then SIGSEGV/SEGV_MAPERR at `0xdead1005`.  The matching
  signature does not identify one hook as the cause, but it invalidates both
  sessions.  Evidence is `evidence\crash_pid8528_20260713_01`.
- The reliable recovery order is now explicit: force-stop; start the title;
  enter Simulation without Gadget; press `ゲームスタート`; wait for the real
  slot screen; only then inject Gadget.  PID 11160 was the first recovered
  minimal-probe instance and is now historical.  Its reinjection was ARM64 and
  resolved the game export inside the physical
  `split_config.arm64_v8a.apk` mapping.  Evidence is
  `evidence\gadget_reinject_pid11160_20260713_01`.
- `natural_hunter_pid11160_minimal_readonly_smoke_20260713_01` failed closed
  before input because the first minimal probe still assumed the logical module
  filename.  `_02` installed correctly but proved the UI was only at the
  Simulation settings page.  After one documented `ゲームスタート` click,
  `_03` completed a five-second read-only smoke with zero ADB gameplay input.
- `natural_hunter_pid11160_minimal_execute_20260713_01` completed one natural
  non-target round in 3.679 seconds.  MAX BET, lever, and all three STOP
  controls were each issued once; process bits were observed for all five,
  `setStopAngle` axes were exactly 0/1/2, and the final progress was
  `0xe00000`.  Seven real dispatch batches contained no complete target pair,
  so the tool correctly reported `target_hit=false`.  Buffered observer data
  was 178,732 bytes, 98.3% below the roughly 10.4 MB old heavy attempts; those
  incomplete heavy attempts took 56-60 seconds.  The compact journal SHA-256 is
  `C88FF4B4F759F09E6BA604C7A8CA24739A9B75B06E28A32C3ABAFEBDE9A1E3A3`.
- The latest captured instance is PID 3083.  This remains a dated evidence PID,
  not a value to reuse after restart.  Reinjection evidence is
  `evidence\gadget_reinject_pid3083_20260713_01`; its summary SHA-256 is
  `DA752417710EF91EFDE6B28F7EACA79E65B5215A1AC97AF35100453AEAAE924F`.
- `natural_hunter_pid3083_active_csl_readonly_smoke_20260713_03` sent no
  gameplay input and captured all 65 declared CSL active-vector slots at both
  endpoints without truncation.  Every snapshot RPC temporarily attaches to
  the next `CSLMng::Calc`, executes on that Calc thread, and detaches.  The
  defensive cap is 128 and is not a declared game limit.  Journal SHA-256:
  `DA92840BC7E140AF1EF8A25E6BA77F97133E36ECA06BE375DDB666BE31F1A6CB`.
- `natural_hunter_pid3083_active_csl_execute_20260713_01` completed one ordinary
  non-target round.  The ID19 packet was `19 0 8 0 0 10 1 38`: zero-based
  `raw[1]=0`, `raw[2]=8`, so it is not story permission.  The post snapshot had
  four playing transport rows, all deliberately marked
  `bgm_semantics_proven=false`: ID820/ch1, ID304/ch2, ID2655/ch3, ID308/ch11.
  Static joins identify ID820 as Iroha dialogue and ID2655 as a Sana title
  call.  ID304/resource834 and ID308/resource839 remain unlabeled; duration,
  channel, or loop state cannot classify them as BGM.
- `natural_hunter_pid3083_active_csl_execute_20260713_02` adds three bounded
  ordinary rounds.  Their durations were 4.080/3.990/3.780 seconds; all 15
  one-shot controls were accepted, all nine stop axes and cumulative masks
  matched, every round had seven real dispatch batches, and no buffer
  overflow occurred.  All three remained `raw[1]=0, raw[2]=8` non-targets.
  Journal SHA-256:
  `16B2929BD3FF6B6137AD29CF245F7708AA76D762024B1E11E572C77B581BD828`.

Recovery was always state checked.  Incomplete rounds were finished one axis
at a time only after snapshots showed the expected `0x200000` and `0x600000`
progress; the final `0xe00000` transition returned naturally to 0/0.  No source
or production media was deleted.

## Static SP Story kind lottery

New reproducible extractor:

```text
tools/frida_runtime_probe/extract_sp_story_kind_lottery.py
test_extract_sp_story_kind_lottery.py
```

It reads five relocated table descriptors at VMA `0x4b28e60`, parses
`(weight_u64, result_u64)` entries until the `0x8000` sentinel, maps
`kind = result + 9`, and writes JSON/CSV with the native library hash.

Durable output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260713\static_sp_story_kind_lottery_20260713\sp_story_kind_lottery_tables.json
D:\magia\MyProducts\casino\runtime_recovery_20260713\static_sp_story_kind_lottery_20260713\sp_story_kind_lottery_entries.csv
```

Every table sums to 32768:

| table | weighted results |
| --- | --- |
| 00 | kind 11 33.334%; kind 12 33.334%; kind 14 33.331% |
| 01 | kind 11 33.334%; kind 12 33.334%; kind 14 33.331% |
| 02 | kind 11 3.125%; kind 12 3.125%; kind 13 90.625%; kind 14 3.125% |
| 03 | kind 9 85.938%; kind 11 1.563%; kind 12 1.563%; kind 13 9.375%; kind 14 1.563% |
| 04 | kind 9 93.750%; kinds 11, 12, 13, 14 each 1.563% |

`fnLot_OT_AT_SpStryKnd@0x445e698` chooses the table from
`SdGmData+0x592`: values <=1 use table 00, 2 uses 01, 3 uses 02, 4 uses 03,
and >4 uses 04.  The function requires the surrounding SP Story gates; these
probabilities explain expected search cost but do not authorize forced selector
or fabricated runtime evidence.

## ac7115 subtitle metadata correction

Graphical text `cap7115_sp4_kdpl_kae_006` (`ごめんね…`) was previously
associated with voice request 8894 by text similarity.  Runtime did not call
8894.  The audio render was not polluted, but the manifest provenance was
wrong.  The ac7115 composition plan now marks the cue graphical-only, retaining
its text/timing while clearing request, start, and speaker voice fields.  A
regression test protects this distinction.

## Human-readable completion gap

The 926-event baseline remains:

| gate | count |
| --- | ---: |
| technical-ready | 521 / 926 |
| ready with per-event QA | 304 / 521 |
| ready but missing per-event QA | 217 |
| ready represented in a preserved/series set | 267 / 521 |
| ready still needing a series decision | 254 |
| material/excluded already collected | 82 / 405 |
| material candidates still needing collections | 323 |
| blocked by strict AV evidence gate | 897 / 926 |

These are inventory counts, not a publication percentage.  The short-term
ac7114/15/16 trio is close in rendering terms but still needs one natural target
run that binds the exact packet/event/voice/outer-BGM state, followed by a
three-event rebuild, QA, and human playback.  The full archive remains a large
catalog-wide production phase after that generic gate is closed.

Final delivery now has three synchronized editions rather than the earlier
pair: no subtitles, Japanese subtitles, and reviewed Chinese subtitles.  The
Japanese and Chinese editions must share a verified game-font/game-text layout
profile.  The existing `Yu Gothic` default is not proof of the game font.

## Next action

1. Join the implemented CSL active-transport snapshot to ZG published
   play-info or equivalent authoritative playback identity.  Do not classify
   BGM from a channel number, loop flag, duration, or listening impression.
2. Continue small, auditable hunt batches only while foreground, PID, credit,
   queue waterline, and buffer bounds remain valid.
3. On a legal target, retain the full observer package and bind the exact
   packet, event code, request/CSL chain, and active outer-audio state.  Never
   infer BGM absence from request count alone.
4. Treat ac7116's held frame 337 as runtime-mechanism proven by the existing
   same-run Z2D evidence.  A natural target recapture is still required to
   restore the outage-lost raw audit chain and close outer BGM, not to reopen
   the hold mechanism question.
5. Resolve the remaining Z2D typography metrics and add reviewed cue-by-cue
   Chinese translations without changing the Japanese timing or audio.
6. Only then rebuild ac7114/ac7115/ac7116 and their three-edition long set, run
   hash/AV/subtitle/timeline QA, and request human playback confirmation.
