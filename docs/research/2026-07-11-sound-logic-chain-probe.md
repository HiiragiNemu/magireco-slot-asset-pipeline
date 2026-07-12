# Sound logic-chain probe

Date: 2026-07-11; generic v2 update: 2026-07-12

`tools/frida_runtime_probe/sound_logic_chain_probe.js` is an independent,
low-noise observer for the native sound request chain. It does not depend on,
or modify, `lightweight_spin_audio_probe.js`.

## Purpose and v2 scope

The first revision filtered for three known request identities. That was too
narrow for a reusable game-wide mechanism probe. Generic v2 records all code
lookups, all request IDs and bounded ReqData metadata, all perform orders, all
`sndPlayReq` metadata, and all CSL play-start metadata. It does not classify a
sound from a numeric suffix or from visual similarity.

The previously known identities remain useful regression rows, not a capture
filter:

| code | request id | runtime ReqData | interpretation |
| --- | ---: | --- | --- |
| `291` | 96 | `ch=0x303ff8fb73e203fd`, function type 2 | `STOP`, no media |
| `295` | 100 | `ch=0x9`, function type 2 | voice-channel `STOP`, no media |
| `16048_*` | 3094 | `ch=0x9`, function type 1, SMZ media | dialogue `PLAY` |

The function-type names come from the game's own
`RequestCtrl::dbgPrintReqTblReqData` enum table (`1=PLAY`, `2=STOP`), not from
numeric filename guessing. The static reference `libGameProc.so` SHA-256 is:

```text
5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF
```

The probe verifies the loaded export offsets against that ELF before recording
the chain. The required AArch64 ABI is:

```text
RequestCtrl::codeName2ReqId(x0=this, x1=code) -> w0 request id
zgSndReqId(w0=request id, w1, w2)
RequestCtrl::getRequest(x0=this, w1=request id, x2=out Request)
RequestCtrl::setRequestList(x0=this, x1=Request const*)
PlayerImpl::performRequest(x0=this, x1=RequestCtrl, x2=ReqOrder, w3=bool)
SoundMng::sndPlayReq(x0=this, w1=resource id, w2, w3)
CSLMng::PlayStart(x0=this, x1=SSound_Data, w2=play index)
```

## Captured metadata and allowed joins

The probe records:

- code string to request-ID resolution;
- exact request ID passed to `zgSndReqId` and `getRequest`;
- each runtime ReqData's channel, official function type, media name, media
  format, master-volume index, own/target IDs, fade attribute, and ducking
  attribute;
- `PlayerImpl` channel, `ReqOrder+0x28` request ID, and `ReqOrder+0x50`
  function type;
- actual `SoundMng::sndPlayReq` resource ID;
- final `SSound_Data+0x2` ID passed to `CSLMng::PlayStart`.

It does not call `Thread.backtrace`, read or send PCM/compressed payloads, or
dump arbitrary memory windows. Return addresses are metadata only.

Generic v2 permits only these causal associations:

1. `codeName2ReqId` return value and the code string from that exact call;
2. request ID supplied to `zgSndReqId`/`getRequest`, plus the ReqData `own_id`
   used by `setRequestList`;
3. `ReqOrder+0x28` as the request-ID join key for `performRequest`;
4. a `sndPlayReq` call only when it is actually nested inside the active
   `performRequest` on the same thread.

`CSLMng::PlayStart` commonly runs on a different sound thread. V2 intentionally
sets its causal request context to null with basis
`none_static_sound_id_join_required`; the final sound ID must be joined through
the version-matched static `sound_id.dat`/request tables. Mere temporal
proximity, including `same_thread_recent` and `global_recent_window`, is not a
causal join.

## Run

From the repository worktree:

```powershell
python tools/frida_runtime_probe/runtime_probe_host.py `
  --script tools/frida_runtime_probe/sound_logic_chain_probe.js `
  --out D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\sound_logic_chain_natural_spin_v2_01\observer_sound_logic_chain.jsonl `
  --duration 135 `
  --quiet `
  --no-unload
```

Start the observer before the natural spin or scene transition. Do not run a
second probe that attaches the same seven exports in the same process.

## First joint run: valid rows and invalid legacy context

The first joint Direction/sound natural run is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260711\evidence\joint_natural_spin_direction_sound_20260711_01
```

The Direction event code is `0x664e476845597a74`, little-endian key `tzYEhGNf`,
which resolves to `ac0910_001`. This log was captured by the legacy revision.
Its `same_thread_recent` and `global_recent_window` fields incorrectly label a
whole later desired-state request batch, `sndPlayReq` resources, and CSL starts
as descendants of code 295/request 100. Every such temporal/global causal
association is invalid. In particular, final IDs 287, 60, and 6758 are **not**
proved to be children of code 295.

The underlying runtime and static rows are still independently useful:

| chain | direct runtime evidence | version-matched static join | evidence level |
| --- | --- | --- | --- |
| `request 344 -> code 814 -> resource 814 -> final 287` | a PLAY order with `ReqOrder+0x28=344` on player channel 0; resource 814 and final ID 287 also occur in the same execution cluster | request table maps 344 to code/resource 814 and channel 0; sound-id table maps resource 814 to final 287 / `snd_00814_bank01_ogg_00287.ogg` | request/order and static mappings are strong; the legacy log did not encode a strict nested/CSL causal join |
| `request 774 -> resource 2701 -> final 6758` | a PLAY order with `ReqOrder+0x28=774` on player channel 2; resource 2701 and final ID 6758 also occur in the same execution cluster | request table labels 774 as code `2701_やちよﾓﾃﾞﾙ導入_001`; sound-id table maps resource 2701 to final 6758 | request/order and static mappings are strong; the legacy log did not encode a strict nested/CSL causal join |

The event timeline for `ac0910_001` independently contains request 774/resource
2701. Code 814 is therefore a strong candidate for already-active outer
gameplay BGM because it is a channel-0 PLAY path coexisting with the scene, but
this is not yet final BGM semantics. Final classification requires a clean v2
same-run nested chain plus before/after active-player/BGM state; neither the
channel number nor CSL transport alone is sufficient.

## 2026-07-12 repaired natural validation

The first generic-v2 natural run revealed
`TypeError: no setter for property` because the script assigned Frida's
read-only `InvocationContext.context`.  The probe now stores its metadata in
`soundLogicContext`; a regression test forbids `this.context =`.

The repaired natural capture is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\joint_natural_spin_mechanism_v5_20260712_01
```

It has zero sound-probe errors and proves that the strict nested join works in
the live game.  Runtime chains were observed for request/resource 107/301,
108/302, and 109/303.  Static final IDs are 58, 59, and 60; CSL also observed
60, so request 109 -> resource 303 -> final 60 is complete without any temporal
request inference.  This validates the generic mechanism and summarizer.  The
run was an ordinary non-target batch, so it does not close the target
ac7114/15/16 BGM gate.

## Evidence gate

A successful target run should contain, in one logical session:

1. `291 -> request_id 96 -> ReqData STOP`;
2. `295 -> request_id 100 -> ReqData ch=0x9 STOP`;
3. `16048_* -> request_id 3094 -> ReqData ch=0x9 PLAY`;
4. actual resource `16048` nested within the matching `performRequest` at
   `SoundMng::sndPlayReq`;
5. final sound id `1360` at `CSLMng::PlayStart`, joined only through the static
   sound-id table;
6. before/after active-player state sufficient to distinguish newly scheduled
   sound from an already-active outer BGM.

Until one target natural run contains all rows, the target-specific dynamic
proof remains pending even though the generic nested mechanism is now
runtime-validated. `CSLStream`
versus `CSLNormal` is a transport property and must not be used by itself to
classify BGM, SE, or dialogue.

## Generic v2 installation smoke test

A no-input generic-v2 smoke test was captured at:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\sound_logic_chain_probe_smoke_20260712_01\observer_sound_logic_chain_smoke.jsonl
```

Result:

```text
installed hooks: 7
unavailable hooks: 0
attach errors: 0
module-offset matches: 7/7
capture scope: all code/request/order/resource/CSL metadata, bounded
temporal_context_is_causal: false
JSONL SHA-256: 5A6D26A5D4B05BC1627A0B1DE532DAFBAF3B2A13D69DAB6D193E4A6D6C844EB6
```

All six GameProc exports resolved from `split_config.arm64_v8a.apk`; the CSL
export resolved from `libAMAIN.so`. Every loaded module offset exactly matched
the same-version ELF reference. No target request occurred during this idle
smoke test, so it validates installation, ABI, and generic capture scope only,
not the natural-event evidence gate.
