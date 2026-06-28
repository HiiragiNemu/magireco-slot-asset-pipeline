# ac7116 visual-tail runtime probe

Date: 2026-06-28

## Question

The current v19 clean render of `ac7116_001` keeps the last frame of
`ac7116_AT_SP_story5_01.mp4` from about 11.267 s to the final dialogue/subtitle
end at 13.027 s.  The user correctly identified that this is only acceptable if
the live game also holds or locks the clean main-story visual while the voice
tail continues.  If the live game shows another visual state during that tail,
the external render must reproduce that state instead of holding a still frame.

This report records the first visual-tail runtime probe results.  The current
answer is: the clean main-story tail hold is still not proven native.

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

## BGM state during this probe

The v3 visual-tail run saw repeated
`C_ObjNml::fnSndRequest_BGM_DIR/STG/END` calls, but those are per-frame helper
paths and were not accompanied by an additional concrete sound-code/BGM request
for the forced scene.  The only concrete late sound request was:

```text
31186_282_mihu_く…ぐ…
```

Therefore the BGM question remains unresolved.  The current safe statement is:
the v19 render retains `42080_SPストーリー5_みふゆとももこ_01` as the scene bed/base
audio, but there is not yet final proof that no additional outer-state BGM
should be mixed in.

## Current decision

`ac7116_001` remains blocked for final Bilibili publication:

- voice/subtitle timing is currently user-accepted;
- foreground gold-frame SE/layers are correctly excluded from the clean story
  edition;
- the clean tail hold is still not proven native;
- additional BGM remains unproven absent.

Keep the v19 ac7114-16 joined scene as a review/mechanism-validation output
until the visual tail and BGM gates are resolved.

## Next proof route

Use the least invasive route first:

1. Re-run `visual_tail_probe.js` from a known-good game state where
   `event_scene_host` can find an active `C_AnmBase` object.
2. Keep passive lifecycle/metadata hooks enabled: `SetData`, `SetLoop`,
   `Start`, `Stop`, `GetStatus`, `GetMovieInfo`, `GetFrameInfo`,
   `NotifyMovieStart`, `NotifyStartAnim`, `DirGetFrame`, and
   `CScreenObjectMng` lock/draw helpers.
3. Treat passive frame extraction hooks as experimental until a run proves they
   do not interfere.
4. In parallel, capture final audio through `CSLAndroidSimpleBufferQueue` or a
   direct game-produced recording to decide whether extra BGM exists.
5. Only after the runtime state is understood should the renderer decide
   between `hold_last_frame`, a real visual continuation layer, a loop, or a
   cut/black transition.
