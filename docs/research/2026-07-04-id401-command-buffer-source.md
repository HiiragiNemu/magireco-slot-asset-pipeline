# 2026-07-04 ID401 command-buffer source

This note continues the `SdGmData` lottery-dispatch work.  It moves one layer
upstream from `ID401::accessSubProcess()` and documents where
`CSlotBody::analysPacket()` obtains the 8-byte packets that later become
`fnRxCom*` callback payloads.

## Why this matters

The current Bilibili-delivery blocker is not codec QA.  The blocker is proving
the game scheduling path that selects a concrete story scene and its full audio
state.  For `ac7114/ac7115/ac7116`, forced official event playback already gives
strong voice/subtitle and Z2D visual-tail evidence, but the natural outer slot
route and possible outer-flow BGM still need proof.

The previous note proved that the story-lottery route depends on:

```text
fnRxComDirInfo3 callback payload[6] = 8
```

Because `ID401::accessSubProcess()` reverses the raw 8-byte packet before
calling `fnRxComDirInfo3`, the upstream packet condition is:

```text
packet_id = 19
raw_packet[1] = 8
```

The command-buffer layer identifies the producer-side buffer that must be
watched for that condition.

## Static evidence

Static outputs:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_slotbody_analys_packet_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_id401_cmd_buffer_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_id401_bank_cmd_queue_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_xref_id401_user_label_work_plt_20260704
```

All four were produced from:

```text
D:\magia\MyProducts\casino\magireco_corrected_research_20260612\native_analysis\libGameProc.so
sha256 = 5a0ae3ce7f25b89a3b9a13d11bf36aaa1de04faceb612357fa04f42426f17ebf
```

Relevant functions:

```text
CSlotBody::analysPacket()                  0x424d480
ID401::accessSubProcess(unsigned char*)    0x443f430
ID401::getCmdBuf(unsigned char*, int)      0x43f24c4
LC701A_SLOT::mn_getCmdBuf(unsigned char*, int) 0x43f3b38
LC701A_SLOT::USER_LABEL_WORK()             0x43f32b4
LC701A_SLOT::SET_BANKBUFFER()              0x43f3a6c
```

`CSlotBody::analysPacket()` calls `ID401::getCmdBuf(dst, 0xc00)`, then iterates
8-byte records in its temporary packet buffer and dispatches each valid record
through `ID401::accessSubProcess(packet)`.  The runtime return address observed
after the dispatch call is:

```text
CSlotBody::analysPacket()+0x2b4 = 0x424d734
```

`ID401::getCmdBuf()` forwards to `LC701A_SLOT::mn_getCmdBuf()` on the fixed
ID401 slot object.  Runtime observations show the object at:

```text
0x7446b2eecab0
```

Static layout currently used by the probe:

| Field | Meaning in current analysis |
| --- | --- |
| `this+0x200ed` | command queue flag |
| `this+0x200ee` | queued command packet buffer, up to `0xc00` bytes |
| `this+0x20cee` | queue tail/counter-like field |
| `this+0xf298` | staging/pending packet buffer |
| `this+0xf0fe` | staging/pending byte length |

`LC701A_SLOT::mn_getCmdBuf()` behavior:

- if the command queue flag is set, it appends pending staging bytes from
  `this+0xf298` length `this+0xf0fe` into the queued buffer at `this+0x200ee`,
  copies the queued buffer to the caller destination, then clears the queue;
- otherwise it copies the first 0x100 bytes of staging to the caller destination
  and clears staging/pending length.

`LC701A_SLOT::Reset()` and `LC701A_SLOT::mnInitialization()` clear
`this+0x200ee`, `this+0x200ed`, and `this+0x20cee`.

`LC701A_SLOT::USER_LABEL_WORK()` and `LC701A_SLOT::SET_BANKBUFFER()` contain the
same queue-enqueue logic.  `USER_LABEL_WORK()` is called directly by
`LC701A_SLOT::_USER_FC_CALL()`:

```text
0x43f2f74: bl 0x449f9a0  # USER_LABEL_WORK_PLT
```

This means the real packet source is the LC701A emulated program/slot-firmware
layer, not a hand-authored per-`ac` table.  The useful next target is therefore
the LC701A program state and labels that populate `this+0xf298` and enqueue it
into `this+0x200ee`.

## Runtime evidence

Runtime output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_real_input_20260704
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_real_input_20260704\summary_light_id401_cmd_buffer_real_input.json
```

Result:

```text
hooks installed: 42
ID401::getCmdBuf leave events: 1
LC701A_SLOT::mn_getCmdBuf leave events: 1
SP Story hooks: 0
story-lottery hooks: 0
BGM helper rows: 24
final queue enqueue rows: 1
```

The only packet copied in this short run was:

```text
raw packet = [4, 3, 3, 156, 240, 0, 0, 150]
packet_id  = 4
callback0  = fnRxComMedalIN
callback1  = fnRxSubMedalIN
```

It is not the target `DirInfo3` lottery-dispatch candidate:

```text
packet_id != 19
raw_packet[1] != 8
```

This is not negative evidence for the mechanism.  The capture ended after
bet/lever progression and did not reach a complete stop/result packet sequence.
A later status probe showed the game sitting in:

```text
body_state = 3
body_mode  = 3
credit     = 41
bet        = 3
```

which is the STOP-side state that should be used for the next longer capture.

### Full physical-input spin after second A: loss

A later run used the stable route recommended above: one lightweight observer
plus ADB physical taps for BET x3, lever, and three stops.  No long
`force_selector_probe --control-sequence` was used.

Runtime output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704
```

Reusable parser:

```text
tools/frida_runtime_probe/summarize_lightweight_spin_probe.py
```

Parser output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704\summary_lightweight_spin_probe_v2.json
```

Result:

```text
observer bytes:            6,232,052
packet observations:       9,660
unique raw packet forms:   35
DirInfo3 packet rows:      768
target candidates:         0
RxCom rows:                6
lottery rows:              10
BGM helper rows:           162
final audio queue rows:    2
hook errors:               0
parse errors:              0
```

The run reached real slot input/state transitions:

```text
body_state/body_mode: 1, 2, 3
credit:               50 -> 47
bet:                  0 -> 3
input masks:          0, 8, 32, 524288
```

The complete command buffer included the ordinary DirInfo3 packet:

```text
raw packet = [19, 0, 8, 0, 0, 1, 1, 29]
callback0  = fnRxComDirInfo3
callback1  = fnRxSubDirInfo3
```

This is still not the target story-dispatch candidate.  The value `8` is at raw
byte 2, not raw byte 1.  After `ID401::accessSubProcess()` byte reversal, raw
byte 2 becomes callback payload byte 5, not payload byte 6.  All sampled
SdGmData story-dispatch fields stayed at zero in this run, including:

```text
SdGmData+0x130 = 0
SdGmData+0x0a8 = 0
SdGmData+0x184 = 0
SdGmData+0x358 = 0
SdGmData+0x13be = 0
```

The same run did observe natural outer slot sound activity:

```text
BGM helper calls: 162
final queue sound_id: 9002
final queue sound_id: 60
```

This proves the outer slot runtime can issue BGM helper requests and final
OpenSL queue chunks during real play, but it is not target SP Story evidence.
It should be treated as a reason to keep the target-scene BGM/bed gate open,
not as proof that `ac7114/ac7115/ac7116` require or do not require extra BGM.

## Tooling change

`tools/frida_runtime_probe/lightweight_spin_audio_probe.js` now records:

- copied packet buffers returned by `ID401::getCmdBuf`;
- copied packet buffers returned by `LC701A_SLOT::mn_getCmdBuf`;
- LC701A command queue/staging state before and after `mn_getCmdBuf`;
- LC701A command queue/staging state around `USER_LABEL_WORK`;
- LC701A command queue/staging state around `SET_BANKBUFFER`;
- per-record packet id and callback symbols, including the special marker:

```text
is_dirinfo3_lottery_dispatch_candidate =
  packet_id == 19 && raw_packet[1] == 8
```

`tools/frida_runtime_probe/summarize_lightweight_spin_probe.py` summarizes
lightweight JSONL captures into auditable JSON and CSV tables for packet,
RxCom, lottery, BGM helper, queue, event-code, play-start, and slot-state data.
Use it to compare future natural runs against the `packet_id=19 &&
raw_packet[1]=8` target condition without redoing ad-hoc parsing.

Use this probe for narrow runtime mechanism captures.  Do not use it as a
renderer or production-output proof by itself.

## Current conclusion

The packet path is now:

```text
LC701A program / USER_LABEL_WORK / SET_BANKBUFFER
  -> staging buffer at LC701A_SLOT+0xf298
  -> queued command buffer at LC701A_SLOT+0x200ee
  -> ID401::getCmdBuf(dst, 0xc00)
  -> CSlotBody::analysPacket() 8-byte packet loop
  -> ID401::accessSubProcess(packet)
  -> rev64 callback payload
  -> fnRxComDirInfo3 callback payload[6]
  -> SdGmData+0x130 -> +0x0a8 -> +0x184 -> +0x358
  -> story lottery dispatch
```

Still open:

- capture a natural `packet_id=19 && raw_packet[1]=8`;
- prove which LC701A labels/program state produce that packet;
- connect that natural route to concrete SP Story stage/selector values for
  `ac7114/ac7115/ac7116`;
- close natural outer-flow BGM for Bilibili-facing long scenes.

Do not return to manual `ac` suffix guessing or visual-only matching.  The
current path is a general packet/scheduler mechanism and should scale to the
remaining scenes once the LC701A producer side is decoded.

## 2026-07-04 follow-up: PLT correction and LC701A byte builder

The earlier static disassembly labels for some branch targets were
over-broad.  They used nearest containing-symbol lookup and could mislabel PLT
entries as unrelated `.text` symbols.  The static tools now parse `.rela.plt`,
`.dynsym`, and `.dynstr` so AArch64 PLT entries resolve to their imported
symbol names.  This corrected the important LC701A helper calls:

```text
0x44902a0 memset
0x44902f0 memcpy
0x449f910 ID401::CLC701A::_JP(unsigned short)
0x449f980 ID401::CLC701A::_RET()
0x449f9d0 ID401::CLC701A::ASM_0xA7()
0x449f9e0 ID401::CLC701A::ASM_0xF8()
0x449faa0 ID401::CLC701A::SET_ENC_SUBFUNC()
0x449fab0 ID401::fnGameLot_Force_TPL_Request()
0x449fac0 ID401::CLC701A::_RETEX()
0x449fad0 ID401::CLC701A::ASM_0xAF()
0x449fae0 ID401::CLC701A::RESET_ENC_SUBFUNC()
0x449faf0 ID401::fnGameLot_Force_TPL_Reset()
```

`LC701A_SLOT::USER_LABEL_WORK()` is a PC dispatch on `this+0x20`, not an `ac`
table.  PCs `0x58a` and `0x1156`, and `SET_BANKBUFFER()`, enter the block that
copies staging bytes from `this+0xf298` with length `this+0xf0fe` into the
queued command buffer at `this+0x200ee`, then clears staging.  The byte source
therefore sits inside the LC701A VM/slot-firmware execution before this enqueue
block, not in `CSlotBody::analysPacket()`.

The full-spin JSONL was re-summarized with the new LC701A enter-sequence table:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704\summary_lightweight_spin_probe_v4.json
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_id401_cmd_buffer_full_spin_adb_continuation_20260704\summary_lightweight_spin_probe_v4_lc701a_enter_sequence.csv
```

Important result:

```text
USER_LABEL_WORK enter sequence rows: 2448
rows where staging changed:       32
enter/leave staging changes:      0
target packet candidates:         0
```

This proves the staging bytes are built between consecutive
`USER_LABEL_WORK` calls, not during the hooked `USER_LABEL_WORK` body itself.
The ordinary DirInfo3 packet was assembled byte-by-byte:

```text
call 2067 -> 2068: new packet starts at byte 48: 19 0 0 0 0 0 0 0
call 2069 -> 2070: byte 50 changes 0 -> 8, producing raw[2]=8
call 2072 -> 2073: byte 53 changes 0 -> 1
call 2073 -> 2074: byte 54 changes 0 -> 1
call 2084 -> 2085: byte 55 changes 0 -> 29
```

This is still ordinary non-target routing because raw byte 1 remains `0`.

`tools/frida_runtime_probe/lightweight_spin_audio_probe.js` now has an
additional low-noise LC701A command-state-change hook for `_OUTI`, `_OUTIC`,
`_IN`, `_INI`, `_INIC`, `_JP`, `_RET`, `_RETEX`, `ASM_0xA7`, `ASM_0xAF`,
`ASM_0xF8`, `SET_ENC_SUBFUNC`, and `RESET_ENC_SUBFUNC`.  It emits only when
the ID401 staging or queue signature changes.  Use this for the next natural
spin capture to identify the exact helper that writes DirInfo3 raw byte 1 or
byte 2.

## 2026-07-04 follow-up: ordinary packet opcode writers

After relaunching from the title screen and starting a clean ready-state spin,
the adjusted physical-input capture produced packet construction again:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\evidence\light_lc701a_state_change_from_ready_20260704
observer bytes:                 3,627,626
packet observations:            1,436
unique raw packet forms:        10
DirInfo3 packet observations:   0
target candidates:              0
BGM helper rows:                198
queue rows:                     0
LC701A enter-sequence changes:  10
hook errors:                    0
```

This run built ordinary packet ids `25`, `24`, `23`, and `22`.  The changed
enter-sequence rows showed the same PC pattern seen in the larger run:

```text
PC 101 / 0x65: create or read packet byte source
PC 102 / 0x66: adjacent byte-source helper
PC 113 / 0x71: write/checksum-style VM RAM store
PC 114 / 0x72: adjacent VM RAM store helper
```

The relevant static opcode disassembly is:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260704\static_disasm_lc701a_packet_builder_opcodes_20260704
```

Key interpretation:

- `ASM_0x65` reads from `this+0x88+addr` and stores the result into register
  byte `this+0x08`.
- `ASM_0x66` reads from `this+0x88+addr` and combines it into the register
  word at `this+0x08`.
- `ASM_0x71` writes register byte `this+0x04` to `this+0x88+addr` when
  `addr >= 0x4000`.
- `ASM_0x72` writes register byte `this+0x07` to `this+0x88+addr` when
  `addr >= 0x4000`.

Because staging `this+0xf298` equals LC701A VM address `0xf210` plus the
`this+0x88` VM RAM base, `ASM_0x71/0x72` are now the best concrete write-side
opcode candidates for packet staging bytes.

`lightweight_spin_audio_probe.js` was updated again to include command-state
change hooks for `ASM_0x65`, `ASM_0x66`, `ASM_0x71`, and `ASM_0x72`.  The next
valid ready-state capture should directly attribute staging byte creation to
these opcode helpers.  A later attempted capture installed the new hooks, but
its physical input did not enter a clean packet-building window and should not
be treated as mechanism evidence.
