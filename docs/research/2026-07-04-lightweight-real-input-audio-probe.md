# 2026-07-04 lightweight real-input audio probe

This note records the post-power-loss recovery state and the stable runtime
probe route for observing real MuMu screen input without destabilizing the game.

## Current storage rule

After the RAM-disk loss, A: is no longer a durable evidence root.  The user
restored a 2026-06-29 backup to A: and also unpacked the same working data to:

```text
D:\magia\MyProducts\casino
```

Treat that D: directory as the durable immediate work root.  A: may be used for
disposable high-write scratch and may be cleaned if space is needed, but any
evidence required for handoff, QA, manifests, or final review must be copied to
D: or committed to the repository.

## Why a lighter probe was needed

The physical-input observer run at:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\physical_input_spin_observe_20260704
```

used the full CSL/audio probe plus force-selector observer hooks.  It was too
heavy for real spin input:

- `C_AnmBase::fnDataSetDir_DIR` emitted thousands of events;
- only one `CSlotBody::BET` call was useful, and that call left `body_bet=0`;
- the app crashed on `GLThread 41`;
- the crash log's first native frame is in
  `libmagireco_gadget.so!libfrida-gadget-raw.so`.

Interpretation: this is observer-induced instability from heavy hooks/backtrace
or high-frequency instrumentation.  It is not a valid negative result for the
game's SP Story path and must not be used to prove that a target scene cannot be
reached.

## New reusable probe

New script:

```text
tools/frida_runtime_probe/lightweight_spin_audio_probe.js
```

It deliberately avoids high-frequency renderer hooks and `Thread.backtrace()`.
It observes only:

- `CSlotBody::BET`, `START`, `STOP`;
- `fnRxComDirInfo8`, `fnRxComPreMdl`, `fnLotDirPreMdl`;
- `fnLot_OT_AT_StryKnd`, `fnLot_OT_AT_StryChara`;
- selected `C_ObjStageAT_SP_Story::*` state hooks;
- high-level sound/event-code requests;
- `CSLMng::PlayStart`;
- final `CSLAndroidSimpleBufferQueue::Enqueue` metadata;
- rate-limited BGM helper calls.

`tools/frida_runtime_probe/runtime_probe_host.py` was also updated so unload or
detach races after a script has already detached do not turn a usable capture
into a host-side failure.

## Stable real-input capture

Evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_physical_bet_calibration_20260704
```

Useful files:

```text
observer_light.jsonl
summary.json
screen_after_bet_candidate_620_2475.png
screen_after_lever_stop_visual_coords.png
```

Result summary:

- the lightweight probe remained stable under real ADB screen input;
- the game stayed foreground after lever and stop taps;
- `CSlotBody::START` fired twice;
- `CSlotBody::STOP` fired 114 times;
- `fnRxComDirInfo8` fired twice;
- `fnRxComPreMdl` and `fnLotDirPreMdl` each fired once;
- `fnReqSndEventCode` fired 10 times;
- `CSLMng::PlayStart` and final queue metadata each fired 5 times;
- `fnLot_OT_AT_StryKnd`, `fnLot_OT_AT_StryChara`, and SP Story hooks did not
  fire.

Resolved event-code requests:

```text
FL_UNIV_001
ac0001_001
ac9902_001
ac9010_060
ac9071_001
ac9100_001
ac9903_001
ac9920_001
ac9920_001
ac9071_002
```

Audio queue observations:

```text
sound_id=9002  queue bytes=265884
sound_id=60    queue bytes=286788
sound_id=61    queue bytes=386568
sound_id=61    queue bytes=386568
sound_id=61    queue bytes=386568
```

Observed slot state:

- before START, the state had `body_credit=47`, `body_bet=3`;
- START left `body_force_main=-1`;
- STOP input later showed `input_a=8` once around the reel-stop sequence;
- body mode eventually advanced to `4`.

Observed RxCom/story fields:

- `fnRxComDirInfo8` payload bytes `[4]`, `[5]`, and `[6]` were all `0`;
- all tracked SdGm stage/selector fields remained `0`;
- no SP Story object hook fired.

Interpretation: this was a successful real-input instrumentation test, but it
was an ordinary slot spin, not the target ac7114/ac7115/ac7116 SP Story path.
It proves the lightweight observer route can be used safely and that runtime
audio/BGM/SE queues exist during ordinary gameplay.  It does not close the
ac7114-16 BGM gate.

## Coordinate correction

The MuMu input coordinate system for the current game view is `2160x3840`.
Screenshots may be scaled for display, but ADB taps must use physical
coordinates.

Current useful coordinates from the 2026-07-04 calibration:

```text
title simulation button: about 1080,3000
game start button:       about 600,2670
lever:                   about 300,2680
stop buttons:            about 830,2700 / 1080,2700 / 1320,2700
BET/red oval candidate:  about 620,2475 to 620,2520
```

Earlier stop coordinates around `y=2860` were below the visible stop buttons and
should not be reused.

## Current mechanism conclusion

The game does not need manual per-`ac` visual classification.  Current static
and runtime evidence supports a table-driven route:

```text
RxCom payload
  -> SdGmData stage/selector fields
  -> SP Story or DirInfo manager kind/selector
  -> DirInfoTable grid
  -> EventInfo event code
  -> Z2D/DGM/movie layer and sound-code requests
  -> final OpenSL/CSL queue
```

The decoded `DirInfoTable/EventInfo` catalog is good for scene discovery and
family ordering.  It is not audiovisual proof.  Final Bilibili outputs still
require runtime evidence for voice, subtitle, SE, BGM/bed, layer selection, and
tail-hold behavior.

## Next investigation

Continue from the lightweight route, not the heavy full observer:

1. identify how to trigger nonzero `fnRxComDirInfo8` payload bytes for target
   SP Story values;
2. specifically seek payload `[4]` stage kinds `11/12/13` and payload `[5]`
   selectors `1/2/3/4/13/14`;
3. capture BGM helpers and final CSL queue in the same run that reaches target
   `ac7114_001`, `ac7115_001`, or `ac7116_001`;
4. only then decide whether the current no-extra-BGM forced renders can be
   promoted to final long-video material.

## Follow-up: SdGmData+0x358 dispatch proof

The next same-day checkpoint is:

```text
docs/research/2026-07-04-sdgm-lottery-dispatch-route.md
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_force358_on_lotdirstart_real_input_20260704
```

Key result: forcing `SdGmData+0x358=8` exactly at `fnLotDirGmStart` entry is
sufficient for native code to set `SdGmData+0x13be=16` and call
`fnLot_OT_AT_StryKnd` plus `fnLot_OT_AT_StryChara`.

This proves the internal lottery-dispatch path.  It does not yet prove the
natural writer of `+0x358`, target SP Story object creation, or target-scene BGM
state.

Follow-up static/runtime work narrows the upstream source:

```text
fnRxComDirInfo3 payload[6]
  -> SdGmData+0x130
  -> +0x0a8
  -> +0x184
  -> +0x358
```

Natural observation:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_natural_dirinfo3_chain_real_input_20260704
```

That run saw `fnRxComDirInfo3 payload=[29,1,1,0,0,8,0,19]`; because
`payload[6]=0`, the `+0x358` chain stayed zero.  The `8` at `payload[5]` is not
the dispatch field for this route.
