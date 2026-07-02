# ac7116 animation-state sampler follow-up

Date: 2026-07-02

## Question

The user flagged the visible tail in the v19 clean render:

- `ac7116_001` picture appears still at about 11 s;
- voice/subtitle continue until about 13 s;
- this is acceptable only if the live game also keeps the main story visual held
  while the final voice plays.

This follow-up does not replace the earlier visual-tail report.  It adds one
piece of runtime evidence: whether the official animation system is still
actively rendering the same story animation object during and after the
11.267 s main-USM duration.

## Prior facts this depends on

Earlier report:

```text
docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md
```

Important prior evidence:

- v6 runtime probe directly observed `CriManaWrapper::SetData` for
  `ac7116_AT_SP_story5_01.usm`.
- v6 `GetMovieInfo` reported 512x288, 30 fps, 338 frames, which is about
  11.267 s.
- v6 observed official foreground gold-frame movies and the LP switch around
  6.7 s.
- CSL queue capture proved the forced official event queues:
  - `42080` / sound id `8912`, stereo, about 11.267 s source duration;
  - `8040` / sound id `9544`, stereo, foreground SE;
  - `31186` / sound id `8008`, mono, about 4.144 s, starting around 8.879 s and
    ending around 13.044 s.
- No additional forced-event BGM/OpenSL queue chunk was observed.  This does
  not yet prove that a full outer gameplay flow lacks BGM.

## Tooling change

`tools/frida_runtime_probe/event_scene_probe.js` now includes a passive
animation-state sampler.  When a forced event context is active, it emits
`animation_state_sample` about every 250 ms.

The sample records pointers and metadata only:

- selected animation object source, currently `C_AnmMain+0x350`;
- selected object pointer;
- frame animation object pointer;
- active animation child pointer;
- last observed animation-frame callback age;
- current task id.

It does not dump media frames, audio data, textures, or APK/game assets.

Follow-up numeric probing added after v10:

- `numeric_probe.selected_object` and `numeric_probe.frame_animation_object`
  sample 4-byte-aligned u32/float candidates in the first 0x500 bytes of the
  selected/frame animation objects.
- This is intentionally small and metadata-only.  It is meant to identify
  possible frame/time/lock fields before adding more specific hooks.
- A broad pointer-field scan was tried as v12 and proved too invasive: Frida
  `create_script` timed out afterward and Gadget had to be reinjected.  The
  pointer scan is therefore left disabled by default in code and should not be
  enabled for normal captures without narrowing the offset list first.

Smoke test:

```powershell
node --check tools\frida_runtime_probe\event_scene_probe.js
```

## Runtime setup and capture

MuMu/Gadget had to be recovered before the successful run:

- app package: `com.universal777.magireco`;
- device: `127.0.0.1:16384`;
- x86 frida-server exposed on host `127.0.0.1:27042`;
- arm64 Gadget exposed on host `127.0.0.1:27043`;
- capture-state check after forwarding reported `runtime_capture_ready_via_arm64_gadget`.

Useful recovery screenshots:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\current_mumu_after_title_tap_20260702.png
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\current_mumu_after_game_start_20260702.png
```

Successful capture:

```powershell
python tools\frida_runtime_probe\capture_official_event.py `
  --host 127.0.0.1:27043 `
  --code 0x2476304366614152 `
  --label ac7116_001_animation_state_v10_after_recovery `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_state_sampler_ac7116_v10_after_recovery_20260702 `
  --pre-wait 3 `
  --object-wait 12 `
  --post-wait 17 `
  --overwrite
```

Capture result:

```text
event_exit_code=0
runtime_exit_code=0
event_log=A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_state_sampler_ac7116_v10_after_recovery_20260702\ac7116_001_animation_state_v10_after_recovery__event.jsonl
runtime_log=A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_state_sampler_ac7116_v10_after_recovery_20260702\ac7116_001_animation_state_v10_after_recovery__runtime.jsonl
```

## Runtime findings

Event-side kind counts:

| kind | count |
| --- | ---: |
| `animation_state_sample` | 68 |
| `forced_z2d_make` | 6 |
| `forced_z2d_make_result` | 6 |
| `forced_direction_load_resource` | 4 |
| `forced_sound_play` | 3 |
| `hooks_installed` | 1 |
| `initial_status` | 1 |
| `animation_object_ready` | 1 |
| `request_queued` | 1 |
| `forced_event_context_started` | 1 |
| `scene_request_executed` | 1 |
| `forced_z2d_sound_callback` | 1 |
| `forced_sound_code_lookup` | 1 |
| `result` | 1 |

Event execution:

- forced context started at relative 0 ms;
- request executed from `CScnSlot::Calc` at 63 ms;
- `ac7116_AT_SP_story5_01.z2d` loaded at 67 ms;
- `ac7116_at_sp_story5_title.dgi` loaded at 81 ms;
- `AT_SPstory_gold_frame.z2d` loaded at 101 ms;
- official sound plays:
  - 116 ms: `42080_SP...story5...01`;
  - 117 ms: `8040_...gold frame...`;
  - 8922 ms: `31186_282_mihu_...`.

Animation-state samples:

| Relative time | Selected source | Selected object | Frame object | Last frame age | Task |
| ---: | --- | --- | --- | ---: | ---: |
| 16 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 20 ms | 2 |
| 9044 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 35 ms | 2 |
| 11049 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 40 ms | 2 |
| 11300 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 24 ms | 2 |
| 12052 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 43 ms | 2 |
| 13054 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 45 ms | 2 |
| 14058 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 49 ms | 2 |
| 16817 ms | `C_AnmMain+0x350` | `0x72b06b9bacc0` | `0x72b06b9bcf40` | 41 ms | 2 |

The low `last_frame_age_ms` values mean the animation-frame callback continued
to run during and after the 11.267 s source-video duration.  The game did not
destroy the scene at the end of the main USM and then leave only an external
renderer-side still frame.

## Numeric field follow-up

v11 first tested the numeric probe:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v11_20260702
```

v11 found one selected-object field that changed every sample:

| Object | Offset | Type | First | Last | 9-11 s | 11.3-13.2 s | 14-16.85 s | Direction |
| --- | ---: | --- | ---: | ---: | --- | --- | --- | --- |
| selected object | `0x350` | u32 | 1352 | 1856 | 1623-1675 | 1690-1743 | 1773-1856 | monotonic + |

The value increased by 504 over about 16.8 s, matching about 30 fps.  It kept
increasing during the 11.267-13.027 s voice/subtitle tail.

v12 attempted broad pointer-field scanning and hung the capture path.  Recovery
evidence:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_after_v12_timeout_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_after_v12_timeout_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_after_v12_reinject_20260702
```

After disabling pointer scanning by default and reinjecting Gadget, v13
validated the safe default:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v13_default_after_reinject_20260702
```

v13 again captured 68 samples through 16.813 s.  The only varying numeric field
in the selected object was again `+0x350`:

| Object | Offset | Type | First | Last | 9-11 s | 11.3-13.2 s | 14-16.85 s | Direction |
| --- | ---: | --- | ---: | ---: | --- | --- | --- | --- |
| selected object | `0x350` | u32 | 2163 | 2665 | 2432-2485 | 2507-2553 | 2583-2665 | monotonic + |

Interpretation: `selected+0x350` is probably an animation-object frame/time
clock, not the CRI movie frame index.  It proves the active story animation
object continues ticking at frame rate through the voice tail.  It does not by
itself prove whether the clean main movie texture is held, replaced, or masked.

## Generic summarizer added

Manual parsing is not acceptable as the project scales to more events, so a
generic summarizer was added:

```text
tools/frida_runtime_probe/summarize_animation_state_samples.py
```

Validation command used on v13:

```powershell
python tools\frida_runtime_probe\summarize_animation_state_samples.py `
  --event-log A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v13_default_after_reinject_20260702\ac7116_001_animation_numeric_v13_default_after_reinject__event.jsonl `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v13_default_after_reinject_20260702\summary `
  --window pre9_11:9000:11000 `
  --window tail11_3_13_2:11300:13200 `
  --window late14_16_85:14000:16850
```

Outputs:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v13_default_after_reinject_20260702\summary\animation_state_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v13_default_after_reinject_20260702\summary\animation_state_samples.csv
```

The generated summary reports:

- 68 samples, 22-16813 ms;
- selected source `C_AnmMain+0x350` for all samples;
- selected object `0x72b06b9a3590` for all samples;
- frame object `0x72b06b967830` for all samples;
- `last_frame_age_ms` min 16 ms, max 59 ms, average 32.68 ms;
- selected-object `+0x350` as the only varying numeric field:
  2163 -> 2665, 67 increasing steps, no decreasing steps.

Use this summarizer for future event captures instead of ad-hoc JSONL
inspection.

## CRI receiver follow-up

`visual_tail_probe.js` was extended with a metadata-only
`cri_receiver_numeric_sample` emitter:

- it tracks only receivers observed through `CriManaWrapper::SetData`;
- it samples numeric u32/float candidates in the first 0x400 bytes;
- it does not scan pointers by default and does not dump media/frame/audio
  buffers.

The first attempt, v14, still depended on `activeEvent` and emitted no receiver
samples.  v15 removed that dependency and proved the sampler worked, but it
only saw already-reused gold-frame receivers.  v16 restarted the app, reinjected
Gadget, entered the slot screen again, and captured the main story receiver:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702
```

Generic summarizer added:

```text
tools/frida_runtime_probe/summarize_cri_receiver_samples.py
```

Validation command:

```powershell
python tools\frida_runtime_probe\summarize_cri_receiver_samples.py `
  --runtime-log A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702\ac7116_001_cri_receiver_sampler_v16_after_restart__runtime.jsonl `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702\summary `
  --window pre9_11:9000:11000 `
  --window source_tail11_267_13_05:11267:13050 `
  --window late14_20_75:14000:20750
```

Outputs:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702\summary\cri_receiver_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702\summary\cri_receiver_events.csv
```

Main receiver summary:

| Field | Value |
| --- | --- |
| receiver | `0x72af8bceec90` |
| first-4KiB FNV | `1e31c4fa` |
| byte size | `1955904` |
| movie info | 512x288, 30 fps, 338 frames |
| `cri_update` span | 4-11134 ms |
| `cri_get_status=5` span | 267-10973 ms |
| receiver numeric sample span | 195-20746 ms |

Interpretation: the main CRI movie wrapper is updated and queried until just
before the 11.267 s source duration, then it is no longer observed as an active
updating CRI movie, while the receiver object remains resident and the higher
animation object from v10/v13 continues ticking.  This is consistent with the
game reaching the last movie frame and the animation/compositor layer holding
that output while the final voice/subtitle tail continues.

This still is not exact pixel proof: no clean-layer texture hash, framebuffer,
or CRI frame index after frame 338 has been captured.

## Current interpretation

The combined evidence is now stronger than the previous state:

1. v6 proves the official main story movie is `ac7116_AT_SP_story5_01.usm` and
   it is only about 11.267 s long.
2. v6/v10 do not show a second clean main-story movie replacing it after
   11.267 s.
3. CSL queue capture proves official voice continues to about 13.044 s.
4. v10/v13 prove the official animation object remains actively rendered
   through the voice tail and beyond.
5. v16 proves the main CRI receiver is the 338-frame story movie, is updated
   only through about 11.134 s, and remains resident while the higher animation
   object continues.

Therefore, for mechanism-validation renders, `hold_last_frame` for the clean
main story after 11.267 s is now runtime-supported for `ac7116_001`.  This is
not merely a blind external concat artifact.

The remaining limitation is exact clean-layer pixel proof: these runs still did
not capture the clean compositor texture/pixels or the CRI movie frame index
after frame 338.  That matters for final publication QA, especially if
foreground/title/slot layers might cover or alter the machine presentation while
the clean story layer itself is held.

## Delivery decision

Do not mark `ac7116_001` or the joined `ac7114+ac7115+ac7116` scene as final
Bilibili-upload candidates yet.

Updated status:

- voice/subtitle timing remains user-accepted;
- the ac7116 final visual hold is now runtime-supported, not disproven;
- exact clean-layer pixels after frame 338 are still not captured;
- forced-event CSL/OpenSL capture still shows no extra BGM, but full outer-flow
  BGM absence remains unproven.

The next AI should keep the current render as a review/mechanism-validation
output, then resolve the remaining BGM/full-flow and clean-layer compositor
gates before final upload packaging.
