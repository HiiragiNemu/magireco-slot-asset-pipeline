# ac7116 visual-tail runtime probe

Date: 2026-06-28

## Question

The current v19 clean render of `ac7116_001` keeps the last frame of
`ac7116_AT_SP_story5_01.mp4` from about 11.267 s to the final dialogue/subtitle
end at 13.027 s.  The user correctly identified that this is only acceptable if
the live game also holds or locks the clean main-story visual while the voice
tail continues.  If the live game shows another visual state during that tail,
the external render must reproduce that state instead of holding a still frame.

This report records the visual-tail runtime probe results.  The current answer
after v6/v7 plus the 2026-07-02 animation-state sampler follow-up is:

- the official main story payload identity is now proven:
  `ac7116_AT_SP_story5_01.usm`, 512x288, 30 fps, 338 frames, about 11.267 s;
- the official final voice/subtitle tail after that movie duration is proven;
- no additional main-story USM continuation was observed;
- the 2026-07-02 sampler proved `C_AnmMain+0x350` continues to render the same
  selected animation object through 16.817 s, including the 11.267-13.027 s
  voice/subtitle tail;
- the clean main-story tail hold is runtime-supported for mechanism-validation
  renders, but final publication still needs exact clean/story compositor pixel
  proof after the main CRI movie reaches its last frame.

## Existing resolved runtime evidence

Resolved official event manifest:

```text
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved\ac7116_001_v1\event_manifest.json
```

Relevant source event logs:

```text
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\raw\ac7116_001__event.jsonl
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\raw\ac7116_001__runtime.jsonl
```

Known official event sequence:

- main DGM: `ac7116_AT_SP_story5_01.dgm`;
- foreground slot presentation: `AT_SPstory_gold_frame_add.dgm`,
  `AT_SPstory_gold_frame_add_LP.dgm`, `AT_SPstory_gold_frame.dgm`,
  `AT_SPstory_gold_frame_LP.dgm`;
- base/bed audio: `42080_SPストーリー5_みふゆとももこ_01`, start 86 ms,
  duration 11266 ms;
- slot foreground SE: `8040_シネスコ変化音_金帯`, excluded from clean story;
- final role voice: `31186_282_mihu_く…ぐ…`, starts 8883 ms, duration
  4144 ms, subtitle ends 13027 ms.

Current v19 production manifest:

```text
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628\events\ac7116_001.json
```

Current v19 render:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628\ac7116_001\with_subtitles\ac7116_001__subtitles.mp4
```

It is 512x288, 30/1, AAC 48000 Hz stereo, and about 13.033 s.  The source
`ac7116_AT_SP_story5_01.mp4` is about 11.267 s.  Therefore the current 1.760 s
visual tail is renderer-created `hold_last_frame` behavior, not source-video
content.

## Probe tooling added

`capture_official_event.py` now accepts a custom runtime script:

```powershell
python tools\frida_runtime_probe\capture_official_event.py `
  --runtime-script tools\frida_runtime_probe\visual_tail_probe.js `
  --code 0x2476304366614152 `
  --label ac7116_001_visual_tail_v3 `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v3_20260628
```

`visual_tail_probe.js` is metadata-only.  It records lifecycle, CRI player,
screen-object, direction-controller, and selected BGM/sound request metadata.
It must not dump frame buffers, PCM, game media payloads, or APK assets.

## v3 runtime result

Capture directory:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v3_20260628
```

Runtime counts included:

| kind | count |
| --- | ---: |
| `cri_get_status` | 566 |
| `cri_update` | 153 |
| `direction_play_animation` | 94 |
| `cri_create_player` | 6 |
| `cri_set_data` | 6 |
| `cri_set_loop` | 6 |
| `cri_movie_info` | 6 |
| `cri_start` | 6 |
| `cri_destroy_player` | 6 |
| `ctrl_snd_req_sequence_sc` | 1 |
| `zg_snd_req_code` | 1 |

The official event path played:

| relative time | event |
| ---: | --- |
| 0.060 s | `42080_SPストーリー5_みふゆとももこ_01` |
| 0.061 s | `8040_シネスコ変化音_金帯` |
| 8.890 s | Z2D sound callback for `31186_282_mihu_く…ぐ…` |
| 8.895 s | `31186_282_mihu_く…ぐ…` |

The CRI `SetData` calls seen during this run were:

| relative time from first event sound | receiver | size | FNV-1a first 4 KiB | matched raw CRI evidence |
| ---: | --- | ---: | --- | --- |
| 0.014 s | `0x793f333b82a0` | 1507616 | `c8fd6fe7` | `patch_index=2582` / `AT_SPstory_gold_frame_add.usm` |
| 0.026 s | `0x793f333b49d0` | 2159168 | `72e6f81c` | `patch_index=2581` / `AT_SPstory_gold_frame.usm` |
| 1.814 s | `0x793f333b7130` | 1730240 | `85a81c24` | unresolved 416x232 CRID payload |
| 6.652 s | `0x793f333b8510` | 1483776 | `c9cc7d28` | `patch_index=2583` / `AT_SPstory_gold_frame_add_LP.usm` |
| 6.662 s | `0x793f3319afe0` | 2157056 | `f32a4a6b` | `patch_index=2584` / `AT_SPstory_gold_frame_LP.usm` |
| 12.984 s | `0x793f333b4520` | 1259744 | `4525de55` | unresolved 416x232 CRID payload |

Raw CRI2 validation was by offset/size and first-4KiB hash only; no source
payload was copied into Git:

| raw source | patch index | size | FNV-1a first 4 KiB | meaning |
| --- | ---: | ---: | --- | --- |
| `cri2.bin` | 1321 | 1955904 | `1e31c4fa` | `ac7116_AT_SP_story5_01.usm` |
| `cri2.bin` | 2581 | 2159168 | `72e6f81c` | `AT_SPstory_gold_frame.usm` |
| `cri2.bin` | 2582 | 1507616 | `c8fd6fe7` | `AT_SPstory_gold_frame_add.usm` |
| `cri2.bin` | 2583 | 1483776 | `c9cc7d28` | `AT_SPstory_gold_frame_add_LP.usm` |
| `cri2.bin` | 2584 | 2157056 | `f32a4a6b` | `AT_SPstory_gold_frame_LP.usm` |

The main clean story payload `ac7116_AT_SP_story5_01.usm`
(`patch_index=1321`, size `1955904`, FNV `1e31c4fa`) was not observed in v3
`cri_set_data`.  This does not prove that the game did not display it; it may
have been preloaded or reached through a different path.  It does mean v3 proves
only the slot foreground/gold-frame layer identities and the LP foreground
switch, not the clean main-story tail.

All six observed CRI players called `SetLoop(true)`.  Do not over-interpret this
as proof that the clean story movie loops or holds visually.  It is only
lifecycle metadata.

## Visual comparison lead that is not yet authoritative

Contact sheets generated for comparison:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_source_compare_20260628
```

Findings:

- `ac7116_AT_SP_story5_01.mp4` and the current v19 render show the same
  moon/white-character visual, with the render holding the final frame.
- `main_video_0000_candidates264.mp4` is visually different: 416x232,
  restaurant/table four-girl scene, about 12.767 s.
- Older timeline evidence maps `ac7116_001` to `main_video_0000_candidates264`
  with `video_mapping=exact_context_candidate`, but this conflicts with the
  2026-06-18 official runtime `z2d_string_set` evidence for
  `[ac7116_AT_SP_story5_01.dgm]`.

Therefore `main_video_0000_candidates264.mp4` is a lead, not a replacement.
Do not silently swap it into the clean render without stronger runtime proof.

## Failed or inconclusive follow-up captures

v4 attempted an active status query strategy, calling CRI `NativeFunction`
lookups such as `GetMovieInfo`/`GetFrameInfo` from the probe side.  It caused
the runtime host to time out and the event host failed with:

```text
RuntimeError: no active C_AnmBase-derived scene object was found within 12.0s
```

Do not call CRI NativeFunctions from hot hooks or probe-side timers unless a
separate minimal smoke proves the target is safe.  Prefer passive interception
of calls the game already makes.

v5 added passive `GetFrameYUVA` / `CopyFrameYUVA` / `GetFrameYUVA_WithInfo`
metadata hooks, but the test run did not reach the event:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v5_frame_yuva_20260628
```

The hooks installed, but `event_scene_host` again failed to find an active
`C_AnmBase` scene object within 12 seconds.  This run is not evidence for or
against native tail hold.

## Runtime capture surface recovery before v6

After v5, the capture surface degraded: the x86 Frida endpoint could still
attach to the process shell, but could not see the arm64 game code, while the
arm64 Gadget endpoint timed out.

Diagnostic output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_visual_tail_recovery_20260628
```

The verdict was:

```text
blocked_x86_frida_cannot_see_arm64_game_code
```

Reinjecting Gadget without an app restart still timed out:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_visual_tail_recovery_20260628
```

Restarting the app and then reinjecting Gadget recovered the arm64 runtime
surface:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_visual_tail_recovery_after_restart_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_visual_tail_after_reinject_20260628
```

The recovered verdict was:

```text
runtime_capture_ready_via_arm64_gadget
```

MuMu screenshots in this state were 2160x3840.  ADB taps must use physical
coordinates, not half-resolution coordinates.  Known useful taps in this run:

```text
title simulation button: adb -s 127.0.0.1:16384 shell input tap 1080 3000
game start button:        adb -s 127.0.0.1:16384 shell input tap 600 2670
```

## v6 runtime result after app restart and Gadget reinjection

Capture directory:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v6_after_reinject_20260628
```

Event log:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v6_after_reinject_20260628\ac7116_001_visual_tail_v6_after_reinject__event.jsonl
```

Runtime log:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v6_after_reinject_20260628\ac7116_001_visual_tail_v6_after_reinject__runtime.jsonl
```

The forced event started at runtime unix ms `1782634408007` and was executed
through `CScnSlot::Calc`.  The event host selected an active
`C_AnmMain+0x350` child and the final `last_animation_frame.unix_ms` was
`1782634424995`, about 16.988 s after event start.

The official event path played:

| relative time | event |
| ---: | --- |
| 0.087 s | `42080_SPストーリー5_みふゆとももこ_01` |
| 0.088 s | `8040_シネスコ変化音_金帯` |
| 8.918 s | Z2D sound callback for `31186_282_mihu_く…ぐ…` |
| 8.923 s | `31186_282_mihu_く…ぐ…` sound-code lookup/play |

The `CriManaWrapper::SetData` identities seen in v6 were:

| relative time | receiver | size | FNV-1a first 4 KiB | matched raw CRI evidence |
| ---: | --- | ---: | --- | --- |
| 0.107 s | `0x793f333b3980` | 1955904 | `1e31c4fa` | `patch_index=1321` / `ac7116_AT_SP_story5_01.usm` |
| 0.129 s | `0x793f33383c50` | 1507616 | `c8fd6fe7` | `patch_index=2582` / `AT_SPstory_gold_frame_add.usm` |
| 0.138 s | `0x793f333b2810` | 2159168 | `72e6f81c` | `patch_index=2581` / `AT_SPstory_gold_frame.usm` |
| 6.747 s | `0x793f333b3770` | 1483776 | `c9cc7d28` | `patch_index=2583` / `AT_SPstory_gold_frame_add_LP.usm` |
| 6.759 s | `0x793f333b1e20` | 2157056 | `f32a4a6b` | `patch_index=2584` / `AT_SPstory_gold_frame_LP.usm` |

This resolves the v3 gap: the clean main story payload was not merely a guess or
an older candidate.  In a recovered v6 official run, the game itself loaded
`ac7116_AT_SP_story5_01.usm` for this event.

`GetMovieInfo` for the main story receiver reported:

| receiver | width | height | frame rate | frame count/value3 | duration implied |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0x793f333b3980` | 512 | 288 | 30 | 338 | 11.267 s |

The current v19 clean render holds the last frame from that same 11.267 s
boundary to the final voice/subtitle end at about 13.027 s.  v6 therefore proves
that the renderer is not truncating hidden main-story video content after 11.267
s: the official main story USM itself is 338 frames.  It does not by itself prove
the exact clean compositor state during the tail, because no downstream
`GetFrameYUVA`, `CopyFrameYUVA`, `GetFrameInfo`, `DirGetFrame`,
`NotifyMovieStart`, `NotifyStartAnim`, or screen-object lock/draw metadata fired
in this v6 capture.

Runtime kind counts in v6:

| kind | count |
| --- | ---: |
| `cri_get_status` | 295 |
| `nscn_calc` | 99 |
| `cri_update` | 80 |
| `hook_installed` | 46 |
| `cri_create_player` | 5 |
| `cri_set_data` | 5 |
| `cri_set_loop` | 5 |
| `cri_movie_info` | 5 |
| `cri_start` | 5 |
| `cri_stop` | 4 |
| `cri_destroy_player` | 2 |
| `snd_is_already_playing_bgm` | 1 |
| `ctrl_snd_req_sequence_sc` | 1 |
| `zg_snd_req_code` | 1 |

The initial gold-frame foreground receivers stopped/destroyed near the LP
switch at about 6.74 s; the LP foreground receivers stayed active through the
post-wait.  The main receiver did not emit a stop/destroy event during the
capture window.  This supports, but does not conclusively prove, the clean-story
`hold_last_frame` interpretation.

## v7 native screenrecord diagnostic

To get an external visual reference from the live game, a small diagnostic
Android screenrecord was captured while forcing the same official event.  This
is not a production output and contains only the full machine screen, not the
clean story crop/layer.

Screenrecord:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_20260628.mp4
```

Event log:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_native_screen_v7_event.jsonl
```

Contact sheets:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_contact.jpg
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_tail_frames.jpg
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_late_tail_frames.jpg
```

The screenrecord stream is 720x1280 H.264, about 24.026 s, about 8.7 Mbps, with
no audio stream.  The event-side timing again showed the base bed at about
0.051 s, the foreground SE at about 0.052 s, and final voice request at about
8.901 s.  The event host final `last_animation_frame.unix_ms` was
`1782634634198`, about 16.966 s after event start.

Visual review of the contact sheets shows the official full-machine screen
transitions through the gold-frame/slot presentation and then into a white
title-like foreground display.  This is useful proof that the full live game has
foreground presentation after the main story movie starts, but it cannot answer
the clean-story tail question by itself: the foreground layers cover or dominate
the visible machine screen exactly in the time window where the clean edition
has removed those layers.

## v8/v9 compositor hook follow-up

`visual_tail_probe.js` was updated to reduce hook blindness:

- if the loaded game code is exposed as `split_config.arm64_v8a.apk` rather than
  `libGameProc.so`, the probe now resolves the game module through known anchor
  exports;
- if selected visual functions are not exported by name, the probe can fall back
  to known module offsets;
- if a module-specific export lookup fails, the probe now still tries
  `Module.findGlobalExportByName` before falling back to offsets.

v8 capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v8_offset_compositor_20260628
```

v8 proved the offset resolver installed the intended GL/Dir/screen-object hook
addresses, but a probe bug caused many global exports, including CRI/audio
symbols, to be missed after module resolution switched to
`split_config.arm64_v8a.apk`.  Treat v8 as a tool smoke only, not event
evidence.

v9 capture after fixing global-export fallback:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v9_offset_compositor_20260628
```

v9 restored CRI/audio hooks and installed offset fallback hooks for
`GLtask_display1` and `GLtask_display2`, but no visual/compositor events fired
in the forced event window.  CRI/audio evidence remained useful, but v9 still
did not identify the actual clean/story compositor hot path.

Important v9 nuance: the main story USM did not appear in `SetData` during this
run, while the foreground gold-frame players did.  This is consistent with the
earlier v3 behavior and likely reflects preload/reuse state after v6.  Do not
use v9 to contradict v6; v6 remains the direct proof that the official event can
load `ac7116_AT_SP_story5_01.usm`.

## BGM state during this probe

The v3 visual-tail run saw repeated
`C_ObjNml::fnSndRequest_BGM_DIR/STG/END` calls, but those are per-frame helper
paths and were not accompanied by an additional concrete sound-code/BGM request
for the forced scene.  v6 saw one `snd_is_already_playing_bgm` probe-side hook
event, one `ctrl_snd_req_sequence_sc`, and one `zg_snd_req_code`, but the only
concrete late sound request was:

```text
31186_282_mihu_く…ぐ…
```

Therefore the BGM question remains unresolved.  The current safe statement is:
the v19 render retains `42080_SPストーリー5_みふゆとももこ_01` as the scene bed/base
audio, but there is not yet final proof that no additional outer-state BGM
should be mixed in.

Additional CSL queue capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628
```

This run captured final OpenSL queue chunks for the forced official event:

| Runtime request | Sound id | Queue start | Queue clear / inferred end | Format |
| ---: | ---: | ---: | ---: | --- |
| `42080` | `8912` | 0.066 s | 11.344 s | stereo |
| `8040` | `9544` | 0.070 s | 2.744 s | stereo |
| `31186` | `8008` | 8.879 s | 13.044 s | mono |

No additional BGM request or continuous BGM queue chunk was observed in the
forced official event.  This strengthens the current clean audio interpretation
for `ac7116_001`, but it still does not prove that a non-forced full outer
gameplay flow could not add BGM.

## Current decision

`ac7116_001` remains blocked for final Bilibili publication:

- voice/subtitle timing is currently user-accepted;
- foreground gold-frame SE/layers are correctly excluded from the clean story
  edition;
- the main-story source identity and duration are now runtime-proven;
- the clean tail hold is now runtime-supported by the 2026-07-02
  animation-state sampler and CRI receiver v16 sampler, but still not exact
  clean-layer pixel proven;
- forced-event audio queue contains bed/foreground SE/voice only; additional
  outer-state BGM remains unproven absent.

Keep the v19 ac7114-16 joined scene as a review/mechanism-validation output
until the visual tail and BGM gates are resolved.

## Next proof route

Use the least invasive route first:

1. Read the follow-up sampler report:
   `docs/research/2026-07-02-ac7116-animation-state-sampler.md`.
2. Use `summarize_animation_state_samples.py` and
   `summarize_cri_receiver_samples.py` for machine-readable summaries; do not
   hand-parse future JSONL captures.
3. Re-run `visual_tail_probe.js` from a known-good restarted/reinjected game
   state if main CRI `1e31c4fa` must be recaptured.
4. Keep passive lifecycle/metadata hooks enabled: `SetData`, `SetLoop`,
   `Start`, `Stop`, `GetStatus`, `GetMovieInfo`, `GetFrameInfo`,
   `NotifyMovieStart`, `NotifyStartAnim`, `DirGetFrame`, and
   `CScreenObjectMng` lock/draw helpers.
5. Add lower-level, throttled compositor/texture metadata for the 10-13.5 s
   window.  The proof target is not another full-machine screenrecord; it is the
   clean/story layer state after the main CRI movie reaches frame 338.
6. Treat passive frame extraction hooks as experimental until a run proves they
   do not interfere.
7. For audio, the forced-event CSL queue is now known.  The remaining BGM proof
   must come from full outer gameplay flow capture or a direct game-produced
   recording, not another forced-event-only run.
8. Only after the runtime state is understood should the renderer decide
   between `hold_last_frame`, a real visual continuation layer, a loop, or a
   cut/black transition.
