# 2026-07-04 SdGmData lottery dispatch route

This note records the post-outage recovery state for the SP Story lottery route.
It is intentionally narrow: it proves one internal game dispatch path, but it
does not yet prove a natural route to ac7114/ac7115/ac7116 or final BGM state.

## Storage boundary after power loss

The A: RAM-disk lost newer temporary data.  Treat A: as disposable scratch and
do not make it the only copy of new evidence.

Current durable immediate work root:

```text
D:\magia\MyProducts\casino
```

The restored 2026-06-29 backup exists on A:, and the same restored files were
also unpacked to the durable D: root above.

## Static evidence

Current static output directories:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_mem_offsets_sdgm_lottery_source_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_sdgm_lottery_source_candidates_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_gr_dir_copy_and_kndcal_callers_20260704
```

Important PLT / dispatch addresses:

```text
fnKndCalUsr_SetGR_DirPrmCopy@plt = 0x449fec0
fnLotDirPreMdl@plt                 = 0x44a0740
fnLot_OT_AT_StryKnd@plt            = 0x44a0ad0
fnLot_OT_AT_SpStryKnd@plt          = 0x44a0ae0
fnLot_OT_AT_StryChara@plt          = 0x44a0af0
```

`fnLotOther_AfterGetParam` is a direct story-lottery caller.  Its
`SdGmData+0x13be` switch includes:

```text
0x13be = 16
  -> fnLot_OT_AT_Navi()
  -> fnLot_OT_AT_StryKnd(0)
  -> fnLot_OT_AT_SpStryKnd()
  -> fnLot_OT_AT_StryChara()
```

`fnLotOther_AfterKndCal_ST` also directly calls:

```text
fnLot_OT_AT_Navi()
fnLot_OT_AT_StryKnd(0)
fnLot_OT_AT_SpStryKnd()
fnLot_OT_AT_StryChara()
```

`fnLotDirGmStart` is the observed writer of `SdGmData+0x13be`.  It reads
`SdGmData+0x358`, dispatches through a 16-entry jump table, and maps:

```text
SdGmData+0x358 = 8  -> write SdGmData+0x13be = 0x10
```

Therefore this causal path is now proved statically:

```text
SdGmData+0x358 = 8
  -> fnLotDirGmStart writes SdGmData+0x13be = 16
  -> fnLotOther_AfterGetParam calls story kind / SP-story kind / story character lottery
```

Important caveat: a raw executable-wide search for offset `0x358` produces many
false positives, because other classes also have a `+0x358` field.  For
example, `C_ObjStageAT_SP_Story+0x358` is an event-code field, not
`SdGmData+0x358`.  Do not treat raw `+0x358` write hits as SdGmData writes
unless the base register is proven to come from `fnGetAddrSdGmData()`.

## Runtime evidence

### Immediate write before input is insufficient

Evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_sdgm358_force8_real_input_20260704
```

Writing `SdGmData+0x358=8` before real input succeeded initially, but by the
time `fnLotDirGmStart` and `fnLotOther_AfterGetParam` ran, the field had already
returned to `0`.  No story lottery hooks fired.  This means the game resets or
overwrites the field before the relevant dispatch window.

### Entry-time write proves the causal route

Evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_force358_on_lotdirstart_real_input_20260704
```

Useful files:

```text
observer_light_force358_on_lotdirstart.jsonl
summary_light_force358_on_lotdirstart.json
```

The control script was armed to write `SdGmData+0x358=8` once, exactly at
`fnLotDirGmStart` entry.  Result:

```text
sdgm_control_force_on_lot_dir_gm_start:
  before +0x358 = 0
  after  +0x358 = 8

kndcal_lot_start_enter:
  +0x358  = 8
  +0x13be = 16
  +0x13c0 = 16
  +0x14cc = 41

lot_other_after_get_param_enter:
  +0x358  = 8
  +0x13be = 16

observed hooks:
  lot_ot_at_stryknd_enter/leave
  lot_ot_at_strychara_enter/leave
```

The run did not observe `C_ObjStageAT_SP_Story::*` hooks.  This proves the
lottery dispatch path, not final SP Story object creation or target ac
selection.

Runtime result from `summary_light_force358_on_lotdirstart.json`:

```json
{
  "forced_sdgm_0x358_on_fnLotDirGmStart_entry": true,
  "forced_value": 8,
  "observed_sdgm_0x13be_16": true,
  "observed_fnLot_OT_AT_StryKnd": true,
  "observed_fnLot_OT_AT_StryChara": true,
  "observed_sp_story_object_hooks": false,
  "natural_writer_of_sdgm_0x358": "not_proven_in_this_run"
}
```

## Tooling changes

`tools/frida_runtime_probe/lightweight_spin_audio_probe.js` now also snapshots
the SdGmData story-dispatch fields at:

```text
fnRxComGmStart
fnInitGmData_GmStart
fnInitGmData_PowerOn
fnKndCalLot_Start
fnKndCalLot_PreMdl
fnKndCalUsr_SetGR_DirPrmCopy
```

`tools/frida_runtime_probe/sdgm_state_control_probe.js` adds the one-shot
control action:

```text
arm_force_sdgm_0x358_on_lot_dir_gm_start_once=8
```

Use this only for mechanism proof.  It is not a final render or production
evidence path.

## Current conclusion

The path from `SdGmData+0x358=8` to story lottery is now proved both statically
and dynamically.

Still open:

- the natural writer/source that sets `SdGmData+0x358=8`;
- how the lottery outputs become concrete SP Story object stage/selector values;
- whether target ac7114/ac7115/ac7116 scenes have extra BGM/bed beyond current
  voice/event audio;
- whether visual tail-hold in rendered outputs matches native runtime behavior.

Do not generate or promote Bilibili-facing long videos from this force-route
alone.  The next useful work is to trace the natural writer of `SdGmData+0x358`
and then capture final sound queues and SP Story object hooks in the same run.

