# 2026-07-03 SP Story event-code and force-routing notes

This note records the current mechanism work for the ac7114/ac7115/ac7116 Bilibili
delivery gate.  It is not a final-output approval.

## Current conclusion

- `ac7114_001`, `ac7115_001`, and `ac7116_001` are native
  `C_ObjStageAT_SP_Story` events, not filename guesses.
- The forced official event paths for the three events still show no additional
  BGM helper or continuous BGM queue chunk beyond the scene/base bed audio,
  gold-band SE, and role voices already captured in the CSL queue.
- Natural slot input does trigger BGM helper paths, so forced single-event
  playback is not a complete model of outer gameplay state.
- The natural captures performed here did not reach the target SP Story scene;
  they reached restaurant/ordinary slot presentation.  Therefore they do not
  close the ac7114-16 outer-flow BGM gate.
- The public force UI is blocked by the add-on purchase gate.  The usable route
  is now internal force state, not the visible UI.
- After the 2026-07-03 power loss, treat any A:-only 2026-07-03 capture path in
  this note as potentially lost/non-authoritative unless it is present in the
  restored filesystem or mirrored to Git/C/D.  The repository records the
  mechanism findings and probe code; runtime JSONL evidence that lived only on
  A: must be regenerated.

## Static SP Story event-code table

The APK native library used in this run was extracted from:

```text
A:\magireco_installed_pull_20260603\data_app_package\split_config.arm64_v8a.apk
```

to:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\apk_native_extract_20260703b\lib\arm64-v8a\libGameProc.so
```

`C_ObjStageAT_SP_Story::fnSetEvCdBase(unsigned short)` stores official 64-bit
event codes at `[this+0x358]`.  The companion `fnSetEvCdNext(unsigned short)`
computes the next/rewind event code into `[this+0x368]`.

New extractor:

```text
tools/frida_runtime_probe/extract_sp_story_event_codes.py
```

Validated command:

```powershell
python tools\frida_runtime_probe\extract_sp_story_event_codes.py `
  --lib A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\apk_native_extract_20260703b\lib\arm64-v8a\libGameProc.so `
  --resolved-root A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\sp_story_event_code_extract_20260703b_v2
```

Result:

- `row_count`: 72
- `resolved_count`: 4
- resolved official rows:
  - `0x4f71466b3d723041` -> `ac7114_001`
  - `0x5773382374447854` -> `ac7115_001`
  - `0x4c792a5a74447854` -> `ac7115_013`
  - `0x2476304366614152` -> `ac7116_001`

## Runtime SP Story state hook

`tools/frida_runtime_probe/csl_audio_queue_probe.js` now also hooks:

- `C_ObjStageAT_SP_Story::pre()`
- `fnSetData()`
- `fnSetEventCode()`
- `fnSetEvCdBase(unsigned short)`
- `fnSetEvCdNext(unsigned short)`
- `fnPlayAnm()`

The hook emits `sp_story_*` rows with:

- stage kind at `this+0x318`;
- source story number at `this+0x31a`;
- active story number at `this+0x34a`;
- direction number at `this+0x34c`;
- base event code at `this+0x358`;
- next event code at `this+0x368`.

`tools/frida_runtime_probe/summarize_runtime_audio_capture.py` now writes:

```text
runtime_sp_story_state.csv
```

when these events are present.  This is the intended evidence join table for
event code, scene state, BGM helper calls, high-level sound-code requests, and
final CSL queue chunks.

## Natural slot captures

The old half-resolution tap coordinates were wrong for the current 2160x3840
MuMu window.  Use physical coordinates:

- lever/bet: `(330,2820)`
- left stop: `(880,2860)`
- middle stop: `(1160,2860)`
- right stop: `(1440,2860)`

Natural capture v1:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\natural_slot_csl_bgm_input_v1_20260703
```

Summary v3:

- BGM helper rows: 6002
- high-level sound requests: 47
- final queue chunks: 41
- observed sound ids include ordinary gameplay/restaurant IDs, not ac7114-16.
- `sp_story_state_count`: 0

Natural capture v2:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\natural_slot_sp_story_audio_v2_20260703
```

Summary v1:

- BGM helper rows: 6002
- high-level sound requests: 53
- final queue chunks: 46
- observed sound ids include ordinary gameplay/restaurant IDs.
- `sp_story_state_count`: 0

Interpretation: ordinary slot flow can call BGM helper paths that forced
single-event playback does not call.  However, these captures did not enter
`C_ObjStageAT_SP_Story`, so they do not answer whether ac7114-16 has an
additional outer-flow BGM.

## Force UI and internal force state

The visible force selector route is not currently usable.  With debug enabled,
`force-toggle` opens the add-on purchase gate:

```text
コンテンツが未購入です
こちらの機能をお使いになるにはアドオンが必要となります。
```

Evidence screenshots/captures:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\screen_force_toggle_20260703b.png
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\natural_slot_sp_story_audio_v1_20260703\screen_after.png
```

Static routing result:

- `CScnSlot::addonForceSelectExecute()` returns the `CForceWindow` selection
  index, clipped to 0..19.
- `CScnSlot::addonForceSelectExecute_fnSet()` is a stub returning 0.
- `CScnSlot::onStartInit()` clears force state, calls
  `addonForceSelectExecute()`, then writes the result to
  `CSlotBody::setForceMainFlag(int)`.
- `CSlotBody::setForceMainFlag(int)` only stores to `[body+0x520]`.
- `CSlotBody::setForceSubFlag(int)` stores to `[body+0x524]`.
- `CSlotBody::setForceFlagPalam(int)` stores to `[body+0x528]`.

New direct internal-force commands:

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-force-main --index <n>
python tools\frida_runtime_probe\force_selector_host.py body-force-sub --index <n>
python tools\frida_runtime_probe\force_selector_host.py body-force-param --index <n>
```

Validated write/reset evidence:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\force_body_main_write0_20260703c.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\force_body_main_reset_minus1_20260703c.jsonl
```

`body-force-main --index 0` changed `body_force_main` from `-1` to `0` without
opening the purchase UI.  `body-force-main --index -1` reset it.

First one-spin index mapping result:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\force_index_map_0_capture_20260703
```

Summary:

- `body-force-main --index 0` was written before the capture.
- The following spin consumed the flag and the status after reel stop returned
  to `body_force_main=-1`.
- `runtime_sp_story_state.csv` is empty and `sp_story_state_count=0`.
- Runtime event codes were only:
  - `0x24493723314f4c56`
  - `0x396b436a2a234a73`
- Final CSL queue chunks were ordinary slot/SE sound ids `60`, `61`, and
  `9002`.
- Screenshot showed restaurant/ordinary slot flow, not target SP Story.

Interpretation: body-force-main index 0 is not the ac7114-16 SP Story route.

## ID401 force-flag table notes

`ID401::fnSetForceFlag(unsigned short kind, unsigned short parameter)` records
requested kinds and writes global force state used by `LC701A_SLOT::SetForceFlag`.
Important static points:

- `fnGetForceFlagKind()` reads one byte from global state at the `0x4cf3938`
  area.
- `LC701A_SLOT::SetForceFlag()` calls `fnGetForceFlagKind()`, then uses a byte
  table at `0x1586274` to write slot state before jumping to `_JP(0x471)`.
- `fnSetForceFlag()` uses a 32-bit kind table at `0x158944c`.
- `fnGameLot_SetEPBforce(int)` writes a one-shot EPB force value consumed by
  `fnGameLot_GetEPBforce()`.

Do not assume any of these values map to ac suffix numbers.  The next safe step
is empirical index mapping with runtime event-code/SP-state capture.

## Post-commit force-consumption refinement

The first idea after the `3d15644` commit was to avoid the blocked force UI by
writing `CSlotBody` internal force fields and then calling game-owned entry
points.  The added probe support is intentionally narrow:

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-reel-start
```

This calls `CSlotBody::reelStartExec()` through Frida and logs
`body_reel_start_exec_call`; the force selector probe also traces
`CSlotBody::reelStartExec()` when a natural game path calls it.

Important refinement:

- `touch_Lever()` only writes input/lever state.  It does not directly consume
  `[body+0x520]` or call `ID401::fnSetForceFlag`.
- `CSlotBody::START(int,int)` contains the force-consumption block, but in the
  observed idle state it returns early because the body state initialization
  gate is already set.
- `CSlotBody::reelStartExec()` statically contains the force-consumption block:
  it calls `ID401::fnClrForceFlag()`, checks `[body+0x520]`, and if non-negative
  calls `ID401::fnSetForceFlag(kind, parameter)` before `ID401::mReelStart()`.
- Directly calling `reelStartExec()` by `NativeFunction` is a diagnostic tool,
  not a proof of the real outer gameplay route.  Frida does not guarantee that
  another interceptor in the same control script will observe calls made by that
  script, so force-consumption proof must come from an independent observer
  script or from a natural path trace.

Therefore an index test is only valid when its capture contains the evidence
chain below in the same run:

1. the requested force value is written (`body_force_main`/parameter snapshot);
2. the native path invokes `CSlotBody::reelStartExec()` or the equivalent real
   game start path;
3. an independent observer captures `force_flag_set` with the requested kind;
4. runtime event-code/SP-story state or CSL queue evidence proves what scene
   actually played.

Do not count the old `body-force-main=8` direct-input attempt as an index-8
mapping result.  It only proved that direct `touch_Lever/touch_Reel` input did
not consume the force flag.

## Next work

1. Recreate any A:-only 2026-07-03 evidence under the durable root:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

Use A: only for disposable high-frequency scratch.
2. Run a small, auditable index-mapping experiment:
   - set `body-force-main` to one candidate index;
   - capture combined CSL/BGM/SP Story JSONL with an independent observer;
   - perform exactly one natural lever/stop cycle or a traced game-owned start
     path that actually emits `force_flag_set`;
   - summarize to `summary_v1`;
   - inspect `runtime_sp_story_state.csv`, `runtime_event_codes.csv`,
     `runtime_force_calls.csv`, `runtime_sound_code_calls.csv`, and
     `csl_queue_chunks.csv`.
3. If no SP Story state appears for body-force-main indices, add a separate
   direct `ID401::fnSetForceFlag(kind, parameter)` action and test only with
   documented kind/parameter candidates from the static table.
4. Only after a target SP Story is reached through the native outer path can the
   ac7114-16 BGM gate be closed.

Final Bilibili upload editions remain blocked until the outer-flow BGM question
is resolved or explicitly proven absent for the target scene.
