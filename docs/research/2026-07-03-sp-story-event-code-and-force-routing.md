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

The extractor now also decodes the `fnSetEvCdBase` stage-kind jump tables and
writes:

```text
sp_story_event_code_routes.csv
sp_story_event_code_routes.json
```

Regenerated durable output after the RAM-disk loss:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\sp_story_event_code_extract_routes_v2_20260703
```

Route-table result:

- `route_row_count`: 180
- `route_resolved_count`: 10
- resolved target route rows:

| stage kind (`this+0x318`) | selector (`this+0x34a`) | jump target | code | resolved event |
| --- | ---: | --- | --- | --- |
| 11 | 1 | `0x43dcaa0` | `0x4f71466b3d723041` | `ac7114_001` |
| 11 | 2 | `0x43dcaa0` | `0x4f71466b3d723041` | `ac7114_001` |
| 12 | 1 | `0x43dc60c` | `0x5773382374447854` | `ac7115_001` |
| 12 | 2 | `0x43dc60c` | `0x5773382374447854` | `ac7115_001` |
| 12 | 3 | `0x43dc60c` | `0x5773382374447854` | `ac7115_001` |
| 12 | 4 | `0x43dc60c` | `0x5773382374447854` | `ac7115_001` |
| 12 | 13 | `0x43dc98c` | `0x4c792a5a74447854` | `ac7115_013` |
| 12 | 14 | `0x43dc98c` | `0x4c792a5a74447854` | `ac7115_013` |
| 13 | 1 | `0x43dca28` | `0x2476304366614152` | `ac7116_001` |
| 13 | 2 | `0x43dca28` | `0x2476304366614152` | `ac7116_001` |

Interpretation: target SP Story selection is a pair, not a suffix-derived
number and not a selector alone.  Runtime work must observe or set both:

```text
MSTCOMCBK()+0x2376 -> C_AnmBase+0x318      # stage kind
MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a -> C_ObjStageAT_SP_Story+0x34a
```

Known target pairs are:

- `ac7114_001`: stage kind `11`, selector `1` or `2`;
- `ac7115_001`: stage kind `12`, selector `1` through `4`;
- `ac7115_013`: stage kind `12`, selector `13` or `14`;
- `ac7116_001`: stage kind `13`, selector `1` or `2`.

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

## Power-loss recovery continuation

After the A: RAM disk loss, the runtime path was restored on 2026-07-03 using
the durable D: evidence root:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

Recovery facts:

- ADB target restored with `adb connect 127.0.0.1:16384`.
- The app was already foregrounded as
  `com.universal777.magireco/.SlotMainActivity`.
- x86 frida-server had to be restarted as root:

```powershell
adb -s 127.0.0.1:16384 forward tcp:27042 tcp:27042
adb -s 127.0.0.1:16384 shell "su -c 'nohup /data/local/tmp/frida-server -l 0.0.0.0:27042 >/data/local/tmp/frida-server.log 2>&1 &'"
python tools\frida_runtime_probe\reinject_gadget.py --out-dir D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gadget_reinject_after_root_frida_20260703
adb -s 127.0.0.1:16384 forward tcp:27043 tcp:27043
```

The first `reinject_gadget.py` summary after root frida showed
`gadget_loaded` and device-side listen on `127.0.0.1:27043`; host-side Gadget
use required the explicit `adb forward tcp:27043 tcp:27043`.

Confirmed status after forward:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\frida_gadget_status_after_forward_20260703.jsonl
```

Key state: `architecture=arm64`, `_ZN8CScnSlot4CalcEv` resolved, `slot_input_enabled=1`,
`body_credit=50` initially.  `body_force_main` was reset to `-1` before further
tests:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_body_main_reset_after_recovery_20260703.jsonl
```

### Natural one-spin baseline after recovery

Evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_baseline_one_spin_after_recovery_20260703
```

Result:

- `body-bet` successfully prepared the slot (`body_bet=3`).
- Natural lever/stop via game input produced `CSlotBody::START` and
  `CSlotBody::STOP` traces.
- Independent CSL observer captured normal gameplay sound flow:
  - `force_flag_clear=1`
  - `force_flag_get_kind=1`
  - no `force_flag_set`
  - `ctrl_snd_req_event_code=4`
  - `queue_enqueue_chunk=10`
  - observed sound ids: `60`, `61`, `291`, `1764`, `1765`, `1772`, `6717`, `6720`

This is the post-recovery baseline for an unforced spin.

### Why naive body-force-main is insufficient

Evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index0_chain_check_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index0_chain_check_v2_20260703
```

Findings:

- A spin must start from `body_state=1`, `body_mode=1`; having `body_bet=3` is
  not sufficient if the state is still `0/0`.
- Writing `body_force_main` before lever is still not robust.  In v2,
  `CSlotBody::START` entered with `body_force_main=0`, but no independent
  `force_flag_set` appeared and the field was cleared to `-1` during the early
  start path.

Interpretation: the game has an early start/init cleanup path before the force
check.  A valid diagnostic mapping must inject after that cleanup or reach the
same timing through the real force selector path.

### Post-clear force diagnostic

New diagnostic action:

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-force-next-lever --index <kind>
```

This action arms one pending force kind, presses lever, and writes
`[CSlotBody+0x520]` immediately after `ID401::fnClrForceFlag()` returns.  It is
a diagnostic route for mapping `ID401::fnSetForceFlag(kind, parameter)` behavior.
It is not the same as user-visible force UI and must not by itself approve final
Bilibili renders.

Validation:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index0_postclear_chain_20260703
```

The independent observer captured:

- `force_flag_clear=1`
- `force_flag_set arg0_u16=0 arg1_u16=0`
- `force_flag_set_return retval_i32=0`

Therefore the diagnostic can make the game-owned
`START -> fnSetForceFlag -> mReelStart` chain observable.

### Force kind 8 has non-target mappings, including one ac0922_001 run

Initial evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index8_postclear_probe_20260703
```

Observer summary:

- `force_flag_set arg0_u16=8 arg1_u16=0`
- `force_flag_set_return retval_i32=1`
- `force_flag_get_kind_return retval_i32=4`
- event code `0x31434e5a38404764`
- sound requests include `31043` through `31061`
- observed sound ids include `6895`, `6907`, and `7865`-`7883`
- no `C_ObjStageAT_SP_Story` runtime event fired.

The restored manifest identifies `0x31434e5a38404764` as:

```text
ac0922_001
```

`subtitle_voice_v4/subtitle_voice_catalog.csv` maps the observed voice range to
`ac0922_001` lines such as `cap0922_freeze_nem_001` and
`cap0922_freeze_tou_014`.

Later selector-calibration runs with kind 8 did not reproduce `ac0922_001`;
they reached ordinary routes such as `ac0101`, `ac0102`, `ac9071`, and
`ac9920`.  Therefore kind 8 should be treated as a non-target diagnostic route,
not as a stable ac0922 selector and not as the ac7114/ac7115/ac7116 SP Story
target.

### Automated post-clear force-kind scan

New reusable tool:

```powershell
python tools\frida_runtime_probe\run_force_kind_scan.py --candidates 3-7,9-19 --restart-each --duration 40 --out-dir D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_3_7_9_19_v2_20260703
```

Important automation fixes:

- MuMu input coordinates are physical `2160x3840`, not the scaled viewer size.
- App restart lands on the title screen.  A clean scan must tap:
  - `1080 3000` for `シミュレーション`;
  - `600 2670` for `ゲームスタート`.
- Reel stop taps are `880 2860`, `1160 2860`, `1440 2860`.
- Samples without a valid `slot_pointer` and `slot_body_pointer` must be
  treated as invalid setup, not as negative force-kind evidence.

Invalid setup directories from before this fix:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_2_7_9_19_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_kind2_v2_20260703
```

Valid evidence roots:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_kind2_v3_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_3_7_9_19_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index8_postclear_probe_20260703
```

Summary:

- force kind 0 validated the post-clear route but returned `0`; it did not
  reach the target SP Story path.
- force kind 8 produced a valid non-target route; one run mapped to
  `ac0922_001` / Episode Bonus, later selector-calibration runs mapped to
  ordinary `ac0101`/`ac0102`/`ac9071`/`ac9920` routes.
- force kinds 1 through 7 and 9 through 19 all emitted real
  `force_flag_set(kind, 0)` evidence, produced ordinary slot/gameplay event-code
  requests, and had `sp_story_state_count=0`.
- No tested kind in `0..19` emitted target event codes:
  - `0x4f71466b3d723041` / `ac7114_001`;
  - `0x5773382374447854` / `ac7115_001`;
  - `0x4c792a5a74447854` / `ac7115_013`;
  - `0x2476304366614152` / `ac7116_001`.
- Static selector tracing now shows why broad `body_force_main` scanning is the
  wrong next step: SP Story event selection is driven by
  `C_AnmBase::fnDataSetDir_DIR()` copying a `MSTCOMCBK()` global selector into
  `C_AnmBase+0x31a`, which `C_ObjStageAT_SP_Story` later copies to
  `+0x34a` before setting event codes.

Representative valid mapping table:

| Force kind | Runtime mapping observed | Target SP Story? |
| --- | --- | --- |
| 1 | `ac0101`, `ac0907`, `ac9071`, `ac9920` | no |
| 2 | `ac0902`, `ac0907`, `ac9071`, `ac9920` | no |
| 3 | `ac0910`, `ac9071`, `ac9920` | no |
| 4 | `ac0909`, `ac0910`, `ac9071`, `ac9920` | no |
| 5 | `ac0904_055`, `ac9071`, `ac9920` | no |
| 6 | `ac0905`, `ac0912`, `ac9071`, `ac9920` | no |
| 7 | `ac0911`, `ac9071`, `ac9920` | no |
| 8 | non-target; observed as `ac0922_001` in one run and ordinary `ac0101`/`ac0102`/`ac9071`/`ac9920` in later calibration | no |
| 9 | `ac0901`, `ac9071`, `ac9920` | no |
| 10 | `ac0902_277`, `ac0906_001`, `ac9071`, `ac9920` | no |
| 11 | `ac0103`, `ac0902_126`, `ac9071`, `ac9920` | no |
| 12 | `ac0907`, `ac9071`, `ac9920` | no |
| 13 | `ac0907`, `ac0915`, `ac9071`, `ac9920` | no |
| 14 | `ac0103`, `ac0912`, `ac9071`, `ac9920` | no |
| 15 | `ac0905`, `ac0917`, `ac9071`, `ac9920` | no |
| 16 | `ac0910`, `ac0914`, `ac9071`, `ac9920` | no |
| 17 | `ac0102`, `ac0907`, `ac9071`, `ac9920` | no |
| 18 | `ac0904`, `ac0906_005`, `ac9071`, `ac9920` | no |
| 19 | `ac0101`, `ac0904`, `ac9071`, `ac9920` | no |

Interpretation: broad blind scanning above 19 is not the right next move.  The
target ac7114/ac7115/ac7116 path is likely selected by a different SP Story
state/caller/parameter path, not the simple `CSlotBody+0x520` main force kind
range tested here.  The next useful work is static caller analysis around
`C_ObjStageAT_SP_Story::fnSetEvCdBase/Next` and the state that selects the
target `(stage kind, selector)` pairs above, then a narrow runtime probe for
those exact route values.

## Static SP Story selector source

New static survey tool:

```powershell
python tools\frida_runtime_probe\survey_aarch64_xrefs.py --lib D:\magia\MyProducts\casino\magireco_corrected_research_20260612\native_analysis\libGameProc.so --target sp_pre=0x43dc260 --target sp_set_data=0x43dc30c --target sp_set_event_code=0x43dc33c --target sp_play_anm=0x43dc378 --target sp_set_base=0x43dc3e8 --target sp_set_next=0x43dcbbc --target plt_set_base=0x449f060 --target plt_set_next=0x449f070 --target anm_data_set_dir=0x43891d0 --target mstcom_cbk_plt=0x4492190 --out-dir D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_sp_story_selector_20260703
```

Stable output root:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_sp_story_selector_20260703
```

Important static facts from `libGameProc.so`:

- `_ZN9C_AnmBase16fnDataSetDir_DIREv` starts at `0x4387f90`.
- It calls `MSTCOMCBK()` and reads:
  - `MSTCOMCBK()+0x2376` -> stores to `[this+0x318]`;
  - `MSTCOMCBK()+0x2378` -> stores to `[this+0x31a]`;
  - `MSTCOMCBK()+0x238a` -> stores to `[this+0x31e]`;
  - `MSTCOMCBK()+0x23be` -> stores to `[this+0x322]`.
- `C_ObjStageAT_SP_Story::pre()` loads `[this+0x31a]` and stores it to
  `[this+0x34a]`, then passes `[this+0x34a]` to `fnSetEvCdBase` and
  `fnSetEvCdNext`.
- `C_ObjStageAT_SP_Story::fnSetData()` performs the same
  `[this+0x31a] -> [this+0x34a]` copy.
- `C_ObjStageAT_SP_Story::fnSetEventCode()` uses `[this+0x34a]` as the event
  selector argument.

Therefore the next runtime targets are both the `MSTCOMCBK()+0x2376` stage kind
and the `MSTCOMCBK()+0x2378` selector copied through `C_AnmBase+0x31a` /
`C_ObjStageAT_SP_Story+0x34a`, not another blind force-kind range.

`csl_audio_queue_probe.js` now also hooks:

```text
C_AnmBase::fnDataSetDir_DIR()
```

and emits:

```text
anm_base_data_set_dir_enter
anm_base_data_set_dir_leave
```

with the object fields at `+0x318`, `+0x31a`, `+0x31c`, `+0x31e`, `+0x322`,
`+0x34a`, `+0x34c`, `+0x358`, `+0x368`, plus the current `MSTCOMCBK()` values
at `+0x2376`, `+0x2378`, `+0x238a`, and `+0x23be`.

`summarize_runtime_audio_capture.py` now writes:

```text
runtime_anm_dir_data.csv
```

This CSV is the next join table for proving which global stage/selector values
lead to `ac7114_001`, `ac7115_001`, `ac7115_013`, and `ac7116_001`.

Smoke evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\selector_hook_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\selector_hook_smoke_v2_20260703
```

Results:

- the new `anm_base_data_set_dir` hook installed at runtime;
- smoke v1 hit the old per-kind cap of 1000 rows in an 8 s idle capture, proving
  the hook is hot enough that the default cap could drop later target selectors;
- `csl_audio_queue_probe.js` now gives `anm_base_data_set_dir_enter/leave` a
  per-kind cap of 20000 rows;
- smoke v2 captured 1127 enter rows and 1126 leave rows in 2 s with no
  suppression;
- current idle selector values were still zero:
  `unique_anm_dir_source_story_numbers=["0"]` and
  `unique_mst_source_story_numbers=["0"]`.

This validates the probe mechanism only.  It does not prove the target
ac7114-16 route yet.

`runtime_probe_host.py` now has `--quiet` to avoid echoing every hook event to
the terminal.  `run_force_kind_scan.py` uses `--quiet`; JSONL/CSV evidence is
unchanged.

## Static SP Story selector writer

The reader side above still left the question "who writes
`MSTCOMCBK()+0x2378`?".  Static disassembly found the writer:

```text
fnKndCalUsr_SetGR_DirPrmCopy
```

Important static facts:

- `fnKndCalUsr_SetGR_DirPrmCopy` starts at `0x443fa64`.
- It calls `fnGetAddrSdGmData()` through PLT `0x4490390`.
- It reads `SdGmData+0x788` and stores it to `MSTCOMCBK()+0x2378` at
  `0x443fd20`.
- The PLT stub for `fnKndCalUsr_SetGR_DirPrmCopy` is `0x449fec0`.
- Direct callers of that PLT stub are:
  - `fnKndCalLot_PowerOn`;
  - `fnKndCalLot_Demo`;
  - `fnKndCalLot_SetChg`;
  - `fnKndCalLot_Start`;
  - `fnKndCalLot_GijiStart`;
  - `fnKndCalLot_RlStart`;
  - `fnKndCalLot_Prize`;
  - `fnKndCalLot_CcDirStt`;
  - `fnLotDirDummy`.

Stable static output roots:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_set_gr_dir_prm_copy_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_set_gr_dir_prm_copy_entry_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_set_gr_dir_prm_copy_plt_20260703
```

`csl_audio_queue_probe.js` now hooks `fnKndCalUsr_SetGR_DirPrmCopy` and emits:

```text
gr_dir_prm_copy_enter
gr_dir_prm_copy_leave
```

`summarize_runtime_audio_capture.py` now writes:

```text
runtime_gr_dir_prm_copy.csv
```

with `SdGmData+0x788`, `MSTCOMCBK()+0x2378`, neighboring direction slots, and
the same MSTCOM selector fields used by `runtime_anm_dir_data.csv`.

Runtime calibration:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gr_dir_copy_hook_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gr_dir_copy_force_kind8_v1_20260703
```

Results:

- idle smoke installed the hook but did not call the copy function, which is
  expected;
- force kind 8 calibration called `gr_dir_prm_copy_enter/leave` six times each;
- in that run, `SdGmData+0x788`, `MSTCOMCBK()+0x2378`, and
  `C_AnmBase+0x31a` were all still `0`;
- the run produced normal/ordinary event codes such as `ac0101`, `ac0102`,
  `ac9071`, and `ac9920`, with `sp_story_state_count=0`.

Interpretation: the upstream selector-copy hook works, but the tested ordinary
force route still does not populate the SP Story selector and does not set the
stage kind.  The next target is now the code path that sets both
`MSTCOMCBK()+0x2376`/`C_AnmBase+0x318` and
`SdGmData+0x788 -> MSTCOMCBK()+0x2378` to one of the target route pairs before
`C_ObjStageAT_SP_Story::fnSetEventCode()` runs.

## Static RxCom stage/selector source

New static offset scanner:

```text
tools/frida_runtime_probe/scan_aarch64_memory_offsets.py
```

It scans AArch64 load/store memory operands by structure offset and now also
tracks short-range register-index constants such as:

```text
mov w8, #0x2376
ldrh w8, [x0, x8]
```

Durable outputs:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_register_index_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_rx_stage_source_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_rxcom_dirinfo_20260703
```

Important findings:

- `MSTCOMCBK()+0x2376` has one decoded read in
  `C_AnmBase::fnDataSetDir_DIR()` and no direct decoded write.
- `MSTCOMCBK()+0x2378` has one decoded read in
  `C_AnmBase::fnDataSetDir_DIR()` and one write in
  `fnKndCalUsr_SetGR_DirPrmCopy()`.
- `fnKndCalUsr_SetGR_DirPrmCopy()` writes `MSTCOMCBK()+0x2370` with a 64-bit
  `str x21` where `x21` is zero-extended from `ldrh SdGmData+0x786`; therefore
  this copy clears the high bytes that include `MSTCOMCBK()+0x2376`.  It should
  not be treated as the target stage-kind writer.
- `fnRxComDirInfo8()` is a likely upstream RxCom route parameter ingress:
  it copies payload byte `5` to `SdGmData+0x16e` and payload byte `4` to
  `SdGmData+0x170`.
- `fnRxComPreMdl()` then copies:

```text
SdGmData+0x16e -> SdGmData+0x0ee -> SdGmData+0x31a
SdGmData+0x170 -> SdGmData+0x0ec -> SdGmData+0x318
```

This is not yet a closed proof that `SdGmData+0x318/0x31a` is the same path as
`C_AnmBase+0x318/0x31a` for SP Story playback.  It is the current best static
lead for where the `(stage kind, selector)` pair enters the game-owned runtime
state before animation/event-code dispatch.

Runtime probe updates:

- `csl_audio_queue_probe.js` now hooks:
  - `fnRxComDirInfo8`;
  - `fnRxComPreMdl`;
  - `fnLotDirPreMdl`.
- `describeSdGmDirData()` now records:
  - `SdGmData+0x16e`, `+0x170`, `+0x0ee`, `+0x0ec`, `+0x318`, `+0x31a`;
  - existing `+0x782..+0x79a` GR direction slots.
- `summarize_runtime_audio_capture.py` now writes:

```text
runtime_rxcom_dir_flow.csv
```

and includes the new `SdGmData` fields in `runtime_gr_dir_prm_copy.csv`.

Live validation:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_hook_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_force_kind8_probe_20260703
```

Results:

- idle smoke installed `rxcom_dirinfo8`, `rxcom_pre_mdl`, and
  `lot_dir_pre_mdl` hooks successfully; no RxCom flow was expected or observed
  in 3 s idle.
- single-candidate kind 8 diagnostic produced:
  - `rxcom_dir_flow_count=10`;
  - `rxcom_dirinfo8_enter/leave=3/3`;
  - `rxcom_pre_mdl_enter/leave=1/1`;
  - `lot_dir_pre_mdl_enter/leave=1/1`;
  - `sp_story_state_count=0`.
- In that non-target kind 8 run, `fnRxComDirInfo8` payload byte `4` and byte
  `5` were both `0`, and all observed RxCom/SdGm stage/selector fields stayed
  `0`.  This explains the ordinary-event result and validates the new evidence
  path, but it does not reach any target SP Story row.
- `run_force_kind_scan.py` now includes RxCom count and unique payload/source
  stage/selector values in `candidate_summary.json`.

## Next work

1. Keep the durable evidence root as the source of truth after the power loss:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

Use A: only for disposable high-frequency scratch.
2. Do not continue blind `body_force_main` scanning just because `0..19` missed.
   The static event route is now identified as a `(stage kind, selector)` pair:
   `MSTCOMCBK()+0x2376 -> C_AnmBase+0x318` plus
   `SdGmData+0x788 -> MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a ->
   C_ObjStageAT_SP_Story+0x34a`.
3. Run a narrow runtime probe with the new `anm_base_data_set_dir_*` events and
   `gr_dir_prm_copy_*` / `rxcom_*` events and capture combined CSL/BGM/SP Story
   JSONL.  The first target is to identify who sets stage kinds `11`/`12`/`13`
   and selectors `1`/`2`/`3`/`4`/`13`/`14` for the resolved target rows.
4. Only after a target SP Story is reached through the native outer path can the
   ac7114-16 BGM gate be closed.

Final Bilibili upload editions remain blocked until the outer-flow BGM question
is resolved or explicitly proven absent for the target scene.
