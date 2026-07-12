# 2026-07-12 runtime reconnect and completion-gap audit

This is the authoritative delta after the latest MuMu restart and the two A:
RAM-disk losses.  Read it together with
`docs/HANDOFF_NEXT_AI_MAGIRECO.md`; older reports remain chronological audit
evidence and must not override this checkpoint.

## Durable and Git state

- Code worktree:
  `C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==`
- Production branch: `codex/corrected-runtime-pipeline`
- Asset/game root:
  `D:\magia\MyProducts\casino\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==`
- Durable runtime evidence:
  `D:\magia\MyProducts\casino\runtime_recovery_20260711` and
  `runtime_recovery_20260712`
- A: is disposable scratch only.
- The remote has only the corrected production branch.  The D: asset root's
  clean local `main@50e4f5d` is obsolete and must not be used for code work.
- `build_series_editions.py`, `build_material_collection.py`, and 155
  composition plans are already committed.  The plans include
  `ac7114_001`, `ac7115_001`, and `ac7116_001`.

The repository tree is consolidated by authority, not by deleting history:
`HANDOFF_NEXT_AI_MAGIRECO.md` is the single entry point,
`PROJECT_STATUS.md` is the rolling status, and dated research documents are
append-only evidence.  Repeated current-state guidance is merged into the
handoff/status files; older dated evidence is retained for auditability.

## Current MuMu reconnect

After the latest restart ADB first reported `emulator-5554 offline`.
`adb reconnect offline` restored the device.  The foreground game process is
PID `2636`.  The root x86 Frida server then had to be restarted on port
`27042`, after which the ARM64 Gadget was re-injected successfully:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\gadget_reinject_pid2636_20260712_02
```

The reinjection summary reports ARM64 and `libGameProc.so` visible.  A
three-second post-restart gate smoke installed the logical state hook and
observed state 0, credit 50, bet 0 with no hook error:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\post_restart_slot_gate_pid2636_20260712_01
```

Audit hashes:

- reinjection summary: `267A547BFC7071130A65D5DD9086E40225BC480F5C6182CAE40B0FED45300B4C`;
- post-restart gate JSONL:
  `DF9CDF4FA754767C534B533270285DA792EB019D7B44A2C85D4F9D6561E877ED`.

## Corrected input authority

`CSlotBody+0x454` and `+0x455` are not per-reel stop permission.  Button
colour is not evidence.  The only accepted-input proof is a nonzero
`CSlotBody::process` input in the same run.

The current exact observed mappings are:

| operation | accepted `process_input_a_i32` |
| --- | ---: |
| max bet | 1048576 |
| lever | 524288 |
| left stop | 2 |
| middle stop | 4 |
| right stop | 8 |

The nearby `state+0x64` values changed through
`0 -> 0x200000 -> 0x600000 -> 0xe00000` as reels were stopped.  That is
consistent with a stop-progress/result mask, not a readiness gate.  Do not
wait for or infer permission from this field; retain it only as state
corroboration after an accepted input.

Low-noise state evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\stop_coordinate_logic_calibration_v2_20260712_01
```

## Generic sound-chain repair and clean natural validation

`sound_logic_chain_probe.js` now captures all bounded metadata and accepts
only exact request IDs, `ReqOrder+0x28`, and a same-thread
`sndPlayReq` actually nested inside `performRequest`.  CSL rows receive no
recent/global request context.

The first generic-v2 natural logs exposed
`TypeError: no setter for property`: the probe tried to assign Frida's
read-only `InvocationContext.context`.  It now uses
`soundLogicContext`; a regression test forbids `this.context =`.

The repaired same-run validation is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\joint_natural_spin_mechanism_v5_20260712_01
```

It has zero sound-probe errors and exact runtime nested chains:

- request 107 / code 301 / channel 11 -> resource 301 -> static final 58;
- request 108 / code 302 / channel 1 -> resource 302 -> static final 59;
- request 109 / code 303 / channel 1 -> resource 303 -> static final 60;
- final 60 was also observed by CSL, so the request 109 chain is complete.

Raw observer SHA-256 values:

- lightweight, 17,825,388 bytes:
  `1BC85A2AE8F029CA098C9AC9B03AA1FE418C3E55028673966ABCB3FB83214B92`;
- sound logic, 30,652 bytes:
  `D078F189B617C00575200C69A00980966CDF7D1A5801CC052D98CE50605EDEB7`;
- slot gate, 23,918 bytes:
  `F5E3F06E86A26053807E42D0ED8B27DF1F08A171953401E4C8D2EF10376A0990`.

The same capture has 13 real packet dispatches in two batches, no parser/hook
error, ordinary DirInfo3 `19 0 2 0 0 1 0 22`, and zero complete target
SP-Story batch.  Its scene codes resolve to `ac9071_001` and
`ac9920_001`; it is mechanism validation, not ac7114/15/16 publication
evidence.

`summarize_sound_logic_chain_probe.py` writes auditable code/get/set/
perform/nested/CSL/chain tables.  Legacy
`same_thread_recent/global_recent_window` associations are explicitly
rejected, so the earlier ac0910 log cannot create a false causal chain.

## What is already preserved

- ac7114/15/16 clean v19: six per-event MP4s plus two 44.854-second scene
  editions; voice/subtitles were user-confirmed, and structure QA is 3/3.
  They remain validation outputs because outer BGM/bed is not closed.
- ac1102/ac1103/ac1104: six family MP4s, manifests, hashes and cumulative
  timelines; 11/11, 13/13 and 13/13 events.  They are review archives, not all
  final clean-story uploads: ac1103 has gameplay/result hybrids and ac1104 has
  effect-only components.
- ac0906: 6/6 auditable material components, correctly kept in the material
  lane; it contains audible character/creature sounds and is not a silent
  story animation.
- ac0908: three good food samples only, not the complete eight-event family.

Six v18 roots remain explicitly invalid: generic strategy sample, ac4901
per-event/full-series, and ac7204 subset/full-series.  Their files may remain
for audit but must never count toward delivery.

The July 2-3 Z2D conclusions survived in Git, but their raw A:-only capture
directories did not survive.  Re-capture them only if final release requires
the complete raw provenance chain; do not repeat broad visual probing.

## Quantified remaining work

The latest catalog-wide audit baseline is 926 events:

| gate | count |
| --- | ---: |
| technical-ready | 521 / 926 |
| ready with per-event QA | 304 / 521 |
| ready but missing per-event QA | 217 |
| ready already represented in a series/preserved set | 267 / 521 |
| ready still lacking a series decision | 254 |
| material/excluded events already in a collection | 82 / 405 |
| material candidates still lacking a collection | 323 |
| still blocked by the strict AV gate | 897 / 926 |

These counts describe pipeline inventory, not publication completion.
Technical QA does not prove correct voice, subtitle, BGM, or scene semantics.

### Short-term target: ac7114/15/16

Remaining stages:

1. Capture one natural target SP-Story run with, in the same real dispatch
   batch, ID19 `raw[1]=8` and a legal ID24 stage/selector.
2. In that run bind lottery, Direction macro/scene code, exact PLAY/STOP
   request chain, final CSL ID, and active-player/BGM state before and after
   the story.  Prove BGM present or absent; absence of a new BGM request is
   insufficient.
3. Rebuild only ac7114/15/16 from the clean main-story layer, preserve native
   media properties and the game-proved tail hold, render subtitle/no-subtitle
   pairs and the same-scene long pair, then run AV/timeline/hash QA.
4. Obtain human playback confirmation before promotion.

### Full-game target

After the target gate is proven, apply the generic mechanism catalog-wide:
resolve the 897 strict AV blocks, render/QA the 217 ready-but-unrendered
events, make 254 series decisions, and build 323 remaining material
collections.  This is still a substantial production phase; the whole archive
is not close enough to claim completion.

## Next efficient action

With limited weekly quota, do not spend it on random long spins or mass
renders.  Use a state-driven capture loop that keeps the low-noise gate active,
records only accepted inputs, and starts the heavier packet/sound probes around
the real dispatch window.  Stop immediately when a complete target batch is
seen; only then spend compute on the three-event rebuild.
