# 2026-07-11 generic runtime timeline and LC701A helper closure

This note records the current mechanism-first checkpoint after the game tree
moved to `D:\\magia\\MyProducts\\casino`.  It supersedes the 2026-07-04
instruction to keep searching visually or to treat `0xfff0` as an unexplained
source byte.

## Scope and evidence policy

The publication target is still the clean animation layer, not the slot frame,
gold frame, particles, buttons, or other foreground gameplay effects.  The
project must retain per-event subtitle/no-subtitle files and later build
same-scene Bilibili editions only after image, voice, subtitle, BGM/bed, SE, and
timeline behavior are tied to the game's own scheduler.

No conclusion in this note comes from visual similarity.  The evidence chain is:

```text
LC701A VM/helper execution
  -> ID401 command-buffer dispatch
  -> SdGmData story lottery and stage/selector
  -> DirectionController table/macro dispatch
  -> scene and sound-code requests
  -> sound request PLAY/STOP semantics
  -> CSL final play start
```

Authoritative code worktree and durable evidence root:

```text
C:\\Users\\cryne\\.codex\\worktrees\\7454\\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
D:\\magia\\MyProducts\\casino
```

`A:` remains disposable scratch.  The checkout at the D game root is the old
local `main` and is not the code-editing worktree.

## Omission review

The earlier trace had four important gaps:

1. The opcode installer generated only exact two-digit names
   `ASM_0x00..ASM_0xff`, so extended helpers such as `ASM_0xED31` were never
   hooked.
2. Repeated command-buffer snapshots were counted as if every observation were
   a real `accessSubProcess` dispatch.
3. ID19 story permission was treated in isolation, without requiring the legal
   ID24 stage/selector packet from the same copied command-buffer batch.
4. Direction BGM/SE/fade helper entry was treated too close to audible playback;
   queue mutation, request function type, and CSL play start were not kept as
   separate evidence levels.

These are now corrected in the working probe and summarizer.  The remaining
open audio question is narrower: a run can prove that a scene starts no new
BGM, but that alone does not prove an outer-gameplay BGM was not already
playing before the capture window.

## LC701A helper closure

Static disassembly places `_USER_FC_CALL` at `0x43f2f64`.  The address
`0x43f2f74`, used in some older notes as the entry, is an internal call site to
`USER_LABEL_WORK`, not the function entry.

The relevant branch near `_USER_FC_CALL+0x2a0` is:

```text
CALL(0x30) -> A5 -> ED31 -> F9 -> set r6=0xf076 -> JPE(0x53)
```

`ASM_0xED31` at `0x442b178` pushes three u16 values (`r4`, `r6`, `r8`) while
adjusting the VM stack pointer.  Runtime attribution now shows that, on this
path, the bytes later copied into DirInfo3 are not an arbitrary visual/event
guess:

```text
DirInfo3 raw[1] <- low byte of ED31 r8
DirInfo3 raw[2] <- high byte of ED31 r8
```

In the canonical natural run, ED31 had `r8=0x0400`; the resulting ID19 packet
contained `raw[1]=0, raw[2]=4`.  Therefore the proved story-dispatch value
`raw[1]=8` corresponds to ED31 `r8` having low byte `8` on this helper branch.

The probe now explicitly hooks `CALL`, `_USER_FC_CALL`, and extended helpers
`CB33`, `ED31`, `EDC7`, and `EDD7`.  It also records a bounded VM stack window
and the `CALL` target.  The high-volume `FuncTableExe` hook is disabled by
default.

## Packet semantics and exact counts

Packet ID is `raw[0] & 0x7f`; high-bit forms such as `0x93` and `0x98` must not
be dropped.

The complete SP Story gate is a same-dispatch-batch conjunction:

```text
ID19: raw[1] == 8
ID24: raw[3] == stage and raw[2] is legal for that stage
```

Legal ID24 pairs are:

```text
stage 11 -> selector 1 or 2
stage 12 -> selector 1, 2, 3, 4, 13, or 14
stage 13 -> selector 1 or 2
```

Do not use a Cartesian product and do not accept ID19 and ID24 from different
command buffers.

Canonical state-driven evidence:

```text
D:\\magia\\MyProducts\\casino\\runtime_recovery_20260711\\evidence\\light_logic_state_driven_full_spin_20260711_02
```

Re-parsing the 38,899,404-byte JSONL with the current summarizer gives:

```text
packet observations:                  11149
accessSubProcess dispatches:             13
copied-buffer packet observations:       26
snapshot packet observations:         11110
DirInfo3 observations / dispatches:    899 / 1
DirInfo8 observations / dispatches:   1843 / 1
dispatch batches:                         2
ID19 story candidates:                    0
ID24 legal selector candidates:           0
complete same-batch SP candidates:         0
hook errors / parse errors:                0 / 0
```

This is an ordinary natural spin, not ac7114/ac7115/ac7116 evidence.  The second
dispatch batch contains ID24 with zero stage/selector and ID19
`[19,0,4,0,0,1,1,25]`.

## SP Story lottery state

The previous probe covered `fnLot_OT_AT_StryKnd` and character selection but
missed `fnLot_OT_AT_SpStryKnd` at `0x445e698`.  Static behavior for the missing
function includes:

```text
SdGmData+0x13be == 16
SdGmData+0x45a  == 1
SdGmData+0x1f82 <= 8
probability input at +0x592
result written at +0x1f82 and later copied to PreMdl +0x2cde
```

The working probe now captures these fields, the eight-entry pools at
`+0x1f84..+0x1f92` and `+0x2ce0..+0x2cee`, and the result at `+0x2fdc`.

## DirectionController is the generic composition scheduler

The reusable runtime path is:

```text
C_DirectionControllerBase::pre()
  -> derived Pre()
  -> PlayTableData()
  -> AnalyzeMasterTable()/AnalyzeCallTableAll()
  -> PlayMacroData()
  -> Macro_*()
  -> DevicePlaySound() / scene request
```

The lowercase `Base::pre()` is the shared per-frame entry.  Hooking uppercase
`Base::Pre()` missed the active derived path and produced a false frame sequence
of zero.  The working probe now uses `_ZN25C_DirectionControllerBase3preEv`.

Verified `PlayMacroData` AArch64 arguments:

```text
x0 controller
x1 row macro bits
x2 active/allowed mask
x3 pointer to 0x28-byte DeviceData
w4 table index
effective macro = x1 & x2
```

Verified queue layouts:

```text
SE    controller+0x370, stride 0x18
BGM   controller+0x488, stride 0x18
FADE  controller+0x5a0, stride 0x18
EVENT controller+0xd18, stride 0x10
```

`Macro_*` functions are void, so a residual return register must not be called
success/failure.  For SE/BGM/fade, queue state `1` means pending work, not yet
audible playback.  Fade uses only the first code slot.  Arbitrary EVENT or
CHANGE_ANM operands must not be decoded as strings.

## Canonical natural scene/audio closure

At about 111.423 seconds in the canonical run, DirectionController dispatched
`CALL_TBL` and then effective macro bit `0x4` (fade).  The fade payload was sound
code `295`, and the same controller requested event code
`0x385a5f7378376f43`.  The event-code table maps its little-endian text key
`Co7xs_Z8` to `ac0902_276`.

Runtime play starts around the event were:

```text
sound id 60   -> resource 303, bank 2, short CSLNormal one-shot
sound id 1360 -> resource 16048, bank 10, ac0902_276 Yachiyo dialogue
sound id 9002 -> resource 43200, about 46 seconds earlier and unrelated
```

Static `zg_snd_request_tbl.bin` resolution is:

```text
code 291 -> request 96  -> function type 2 (STOP), channel 0x303ff8fb73e203fd
code 295 -> request 100 -> function type 2 (STOP), channel 0x9
```

Neither request has media or fade payload.  Channel `0x9` is the role-voice
channel, so `295` is a voice-channel STOP scheduled by the fade macro; it is not
a BGM, SE, or fade audio track.

The actual voice maps through:

```text
resource 16048
request 3094
16048_yac_セリフ_弱いまま変われなければあな-
347C89341E98C43D577F35FDF142.smz
snd_16048_bank10_ogg_01360.ogg
```

Its runtime buffer is 875,556 bytes, exactly the decoded size of the official
9.120375-second, 48 kHz, mono OGG.  Therefore `CSLStream` is transport behavior,
not a BGM classification.

The run has `bgm_pending_queue_mutation_count=0`: it did not schedule a new BGM
through the observed Direction queue.  This does **not** yet prove that no BGM
was already active before this scene.

The metadata-only dynamic chain is implemented separately in the generic v2
`sound_logic_chain_probe.js`; see
`docs/research/2026-07-11-sound-logic-chain-probe.md`.  It captures all bounded
request metadata and uses only exact request/order/nested-call joins.  Its 7/7
installation smoke is durable at
`D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence\sound_logic_chain_probe_smoke_20260712_01`.
That idle smoke did not contain a target request, so it validates hook coverage,
not the final target-session runtime sequence.

## Corrected slot-input authority

`CSlotBody+0x454` and `CSlotBody+0x455` are not per-reel stop-permission
flags.  Durable evidence is:

- `slot_state_gate_smoke_20260712_02` records idle
  `body_state=1/body_mode=1`, `+0x454=1`, and `+0x455=0`;
- `joint_natural_spin_mechanism_v3_20260712_01` records the same
  `+0x454=1/+0x455=0` through the transition to
  `body_state=3/body_mode=3`; the accepted lever is instead visible as
  `CSlotBody::process input_a=524288`;
- `light_logic_state_driven_full_spin_20260711_02` records an actually accepted
  stop inside `CSlotBody::STOP`, called from `CSlotBody::process`, with
  `input_a=2`, `body_state=3`, `body_mode=3`, `body_input_mask=2`,
  `body_touch_mask=48`, and `body_button_state=1`.

The evidence directories are under
`D:\magia\MyProducts\casino\runtime_recovery_20260711\evidence` and
`D:\magia\MyProducts\casino\runtime_recovery_20260712\evidence`.  Therefore
the only current runtime control authority is a foreground-confirmed game plus
the nonzero input bit actually received by `CSlotBody::process` in that same
run.  A state value or screen appearance may guide when to try an input, but it
cannot prove acceptance.

## Next evidence gate

The next natural run must be driven by logic state rather than by looking for
blue buttons:

1. confirm the slot game activity is foreground and reach bet 3;
2. send one lever candidate and accept it only when `CSlotBody::process` records
   the corresponding nonzero input bit in this run;
3. wait until the logical state reaches the spin state; do **not** use
   `CSlotBody+0x454` or `CSlotBody+0x455` as a per-reel permission flag, because
   both have been disproved for that purpose;
4. send one stop candidate at a time and proceed only after the same-run
   `CSlotBody::process` row records its nonzero input bit;
5. keep one observer alive through result, story dispatch, Direction macros,
   sound request execution, and CSL play start.

The acceptance gate for a target run is all of the following in the same
logical session:

- same-batch ID19 story candidate plus legal ID24 selector/stage;
- `fnLot_OT_AT_SpStryKnd`/PreMdl state agreement;
- nonzero monotonic Direction frame sequence;
- scene event code resolved by the event table;
- sound code resolved to request id and PLAY/STOP function type;
- any new BGM queue mutation correlated to final player/CSL activity;
- a before/after snapshot of already-active BGM/player state.

Only after this gate closes should the target event be converted into a clean
composition plan and publication manifest.  The slot foreground remains a
separate material/gameplay output.  Do not mass-render blocked events merely
because MP4 codec QA passes.

## Regression checks

Current working-tree checks pass:

```text
node --check tools/frida_runtime_probe/lightweight_spin_audio_probe.js
python -m py_compile tools/frida_runtime_probe/summarize_lightweight_spin_probe.py
python -m unittest -v test_lightweight_spin_summary.py
python -m unittest -v test_runtime_pipeline.py test_usm_headers.py
```

The focused tests cover high-bit packet IDs, exact legal stage/selector pairs,
same-batch dispatch correlation, repeated snapshot suppression, and legacy/new
BGM event compatibility.
