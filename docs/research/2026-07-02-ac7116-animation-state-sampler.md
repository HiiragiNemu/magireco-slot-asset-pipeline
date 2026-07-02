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

## Current interpretation

The combined evidence is now stronger than the previous state:

1. v6 proves the official main story movie is `ac7116_AT_SP_story5_01.usm` and
   it is only about 11.267 s long.
2. v6/v10 do not show a second clean main-story movie replacing it after
   11.267 s.
3. CSL queue capture proves official voice continues to about 13.044 s.
4. v10 proves the official animation object remains actively rendered through
   the voice tail and beyond.

Therefore, for mechanism-validation renders, `hold_last_frame` for the clean
main story after 11.267 s is now runtime-supported for `ac7116_001`.  This is
not merely a blind external concat artifact.

The remaining limitation is exact clean-layer pixel proof: this run still did
not capture the clean compositor texture/pixels after frame 338.  That matters
for final publication QA, especially if foreground/title/slot layers might
cover or alter the machine presentation while the clean story layer itself is
held.

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
