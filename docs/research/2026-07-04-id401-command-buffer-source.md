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
