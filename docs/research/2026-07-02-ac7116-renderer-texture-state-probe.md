# ac7116 renderer texture-state probe

Date: 2026-07-02

## Purpose

The user asked for proof that the visible `ac7116_001` tail is native game
behavior, not an external renderer artifact.  Earlier evidence already proved:

- official main story payload: `ac7116_AT_SP_story5_01.usm`;
- first-4KiB FNV: `1e31c4fa`;
- movie info: 512x288, 30 fps, 338 frames, about 11.267 s;
- final role voice/subtitle continues to about 13.027-13.044 s;
- the higher animation object continues ticking during the voice tail.

This report adds lower renderer-path evidence.  It is metadata-only: no decoded
frames, textures, pixels, PCM, or game payloads are dumped.

## New tools

Runtime symbol survey:

```text
tools/frida_runtime_probe/runtime_symbol_survey.js
```

CRI/renderer texture-state probe:

```text
tools/frida_runtime_probe/cri_video_texture_probe.js
```

Summarizer:

```text
tools/frida_runtime_probe/summarize_cri_video_texture_probe.py
```

Validation:

```powershell
node --check tools\frida_runtime_probe\runtime_symbol_survey.js
node --check tools\frida_runtime_probe\cri_video_texture_probe.js
python -m py_compile tools\frida_runtime_probe\summarize_cri_video_texture_probe.py
```

## Symbol survey result

Full-module survey output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_symbol_survey_renderer_cri_20260702\runtime_symbol_survey_renderer_cri.jsonl
```

The important discovery was that the active module
`split_config.arm64_v8a.apk` exports renderer symbols below the previous
`GLtask_display1/2` level, including:

```text
_ZN2zg6sprite14RendererImplGL25checkAndBindTextureStatesEPNS0_14TextureStateGLEj
_ZN2zg6sprite14TextureStateGL4bindEv
_ZN16CScreenObjectMng4drawEv
_ZN16CScreenObjectMng16calcFrameControlEv
_ZN8CriVideo19GFDirectionRenderer13UpdateTextureEjPKhiiii
_ZN8CriVideo19GFDirectionRenderer13CreateTextureEiii
```

This explains why the older compositor/GLtask hooks were too high or on the
wrong path.

## GL export probe result

Capture roots:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gl_texture_probe_ac7116_v2_draw_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gl_texture_probe_ac7116_v3_eglproc_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gl_texture_probe_ac7116_v5_bind_timeline_20260702
```

`gl_texture_probe.js` was expanded from single global-export hooks to:

- all matching GLES/EGL module exports;
- `eglGetProcAddress`-returned function pointers;
- ES1/OES draw candidates;
- `glBindTexture`, `glDeleteTextures`, `glFlush`, and `glFinish` timelines.

Findings:

- v2 saw no GL calls because the initial hook layer was wrong.
- v3/v5 showed the game does hit `libGLESv1_CM.so` `glBindTexture` and
  `glTexImage2D`.
- Four 512x288 GL texture allocations occurred around 0.074-0.080 s and
  6.707-6.715 s.
- No `glBindTexture`, `glTexImage2D`, `glDeleteTextures`, draw, sync, or swap
  metadata occurred in the 11.267-13.05 s voice-tail window.

This does not prove pixels by itself, but it rules out a normal GL texture
upload continuation during the voice tail.

## Combined CRI/renderer capture

Before the final combined run, the app was cleanly restarted, Gadget was
reinjected, and the slot screen was re-entered:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_cri_video_texture_v5_20260702
```

Combined capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v5_combined_after_restart_20260702
```

Summary:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v5_combined_after_restart_20260702\summary\cri_video_texture_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v5_combined_after_restart_20260702\summary\cri_video_texture_events.csv
```

The same run captured the official main story movie and foreground movies:

| Relative ms | Kind | Receiver | Size | FNV | Movie info |
| ---: | --- | --- | ---: | --- | --- |
| 119 | `cri_set_data` | `0x72af8b990160` | 1955904 | `1e31c4fa` | 512x288, 30 fps, 338 frames |
| 128 | `cri_set_data` | `0x72af8bcedca0` | 1507616 | `c8fd6fe7` | 512x288, 30 fps, 200 frames |
| 135 | `cri_set_data` | `0x72af8bcedd90` | 2159168 | `72e6f81c` | 512x288, 30 fps, 200 frames |
| 6688 | `cri_set_data` | `0x72af8bcf0220` | 1483776 | `c9cc7d28` | 512x288, 30 fps, 200 frames |
| 6695 | `cri_set_data` | `0x72af8bceeb10` | 2157056 | `f32a4a6b` | 512x288, 30 fps, 200 frames |

The same run also captured renderer activity:

| Window | Count | Stable renderer/texture-state tuple |
| --- | ---: | --- |
| 9.000-11.000 s | 8 | `0x72b10b97f910`, `0x72af3cccff78`, flag `1` |
| 11.267-13.050 s | 6 | `0x72b10b97f910`, `0x72af3cccff78`, flag `1` |
| 14.000-20.000 s | 23 | `0x72b10b97f910`, `0x72af3cccff78`, flag `1` |

The hook kind is:

```text
sprite_renderer_check_bind_texture_states
```

Symbol:

```text
_ZN2zg6sprite14RendererImplGL25checkAndBindTextureStatesEPNS0_14TextureStateGLEj
```

`CriVideo::GFDirectionRenderer::UpdateTexture` did not fire in the combined run.
Therefore this function is not the active video frame upload path for this
event, or the current build routes updates through lower/internal code.

## 2026-07-03 TextureStateGL field sampler

`cri_video_texture_probe.js` was extended to sample only numeric candidates from
the first 0x80 bytes of the `TextureStateGL` pointer passed to
`RendererImplGL::checkAndBindTextureStates`.

This is still metadata-only:

- no framebuffer dump;
- no texture bytes;
- no decoded movie frame;
- no PCM/audio data.

The summarizer now writes renderer check groups and per-window numeric field
stability:

```text
tools/frida_runtime_probe/summarize_cri_video_texture_probe.py
```

After an app restart and Gadget reinjection, v2 captured both the main story
payload and the TextureStateGL fields in one run:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\texture_state_fields_ac7116_v2_after_restart_20260703
```

Summary:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\texture_state_fields_ac7116_v2_after_restart_20260703\summary\cri_video_texture_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\texture_state_fields_ac7116_v2_after_restart_20260703\summary\cri_video_texture_events.csv
```

The run again captured the official main story movie:

| Relative ms | Kind | Receiver | Size | FNV | Movie info |
| ---: | --- | --- | ---: | --- | --- |
| 120 | `cri_set_data` | `0x72af8bcef7d0` | 1955904 | `1e31c4fa` | 512x288, 30 fps, 338 frames |
| 131 | `cri_set_data` | `0x72af8bcee2d0` | 1507616 | `c8fd6fe7` | 512x288, 30 fps, 200 frames |
| 145 | `cri_set_data` | `0x72af8bcee030` | 2159168 | `72e6f81c` | 512x288, 30 fps, 200 frames |
| 6725 | `cri_set_data` | `0x72af8b9e47c0` | 1483776 | `c9cc7d28` | 512x288, 30 fps, 200 frames |
| 6733 | `cri_set_data` | `0x72af8bcef1d0` | 2157056 | `f32a4a6b` | 512x288, 30 fps, 200 frames |

The same run emitted 284 `sprite_renderer_check_bind_texture_states` records.
Window counts:

| Window | Count |
| --- | ---: |
| 9.000-11.000 s | 22 |
| 11.267-13.050 s | 20 |
| 14.000-20.000 s | 68 |

Three `TextureStateGL` pointers were active in the key windows:

| Texture state | Total count | 9-11 s | 11.267-13.05 s | 14-20 s |
| --- | ---: | ---: | ---: | ---: |
| `0x72af42645f58` | 95 | 7 | 7 | 23 |
| `0x72af42645f78` | 95 | 7 | 7 | 23 |
| `0x72af42646148` | 94 | 8 | 6 | 22 |

Stable numeric fields across the tail window included:

| Texture state | Stable examples in 11.267-13.05 s |
| --- | --- |
| `0x72af42645f58` | `+0x4 = 3553`, `+0xc = 3`, `+0x48 = 57.094604`, `+0x50 = 67243.9375`, `+0x68 = 194423728` |
| `0x72af42645f78` | `+0x4 = 3553`, `+0xc = 3`, `+0x48 = 57.094727`, `+0x50 = 67243.9375`, `+0x68 = 194423728` |
| `0x72af42646148` | `+0x4 = 3553`, `+0x8 = 148`, `+0xc = 3`, `+0x58 = 1024`, `+0x60 = 1`, `+0x68 = 194423728` |

Do not over-interpret individual offsets yet.  `+0x4 = 3553` is consistent
with `GL_TEXTURE_2D`, and `+0x8` behaves like a texture/id-like field, but the
structure layout is not fully named.  The safe conclusion is that the same
renderer and three stable TextureStateGL records remain active in the voice-tail
window after the main 338-frame movie boundary.

## 2026-07-03 renderer drawCall primitive sampler

`cri_video_texture_probe.js` was extended again to sample
`RendererImplGL::drawCall(Primitive*)` and the `Primitive` texture slots passed
into the renderer.  The summarizer now groups both
`sprite_renderer_check_bind_texture_states` and `sprite_renderer_draw_call`
records by pointer/signature and reports the same source/tail/late windows.

This remains metadata-only:

- no framebuffer dump;
- no texture byte dump;
- no decoded movie frame;
- no audio/PCM data.

Important failed/incomplete run note:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v6_primitive_20260703
```

v6 proved that the primitive sampler could observe tail renderer activity, but
it did not capture the main story `1e31c4fa` `SetData` in the same run.
Therefore v6 must not be used as clean-main identity proof.

The usable run is v8, after app restart, Gadget reinjection, and title-flow
taps:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary\cri_video_texture_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary\cri_video_texture_events.csv
```

v8 captured the official main story movie and the foreground/slot CRIs in one
run:

| Event-relative ms | Receiver | Size | FNV | Movie info | Interpretation |
| ---: | --- | ---: | --- | --- | --- |
| 108 | `0x72af8bcef050` | 1955904 | `1e31c4fa` | 512x288, 30 fps, 338 frames | `ac7116_AT_SP_story5_01.usm` main clean story |
| 116 | `0x72af8bcee0c0` | 1507616 | `c8fd6fe7` | 512x288, 30 fps, 200 frames | gold-frame add foreground |
| 122 | `0x72af8bcef410` | 2159168 | `72e6f81c` | 512x288, 30 fps, 200 frames | gold-frame foreground |
| 314 | `0x72af8bcedbb0` | 33574784 | `89802b19` | 512x416, 30 fps, 5277 frames | large slot/gameplay/material receiver; not clean story continuation |
| 6813 | `0x72af8bced640` | 1483776 | `c9cc7d28` | 512x288, 30 fps, 200 frames | LP gold-frame add foreground |
| 6820 | `0x72af8bcefe60` | 2157056 | `f32a4a6b` | 512x288, 30 fps, 200 frames | LP gold-frame foreground |

The same run emitted 280 renderer checks and 280 renderer draw calls.
`RendererImplGL::makeupTextures` did not fire in this path.

| Window | `checkAndBindTextureStates` | `drawCall` | `cri_update` / `cri_get_status` |
| --- | ---: | ---: | ---: |
| 9.000-11.000 s | 24 | 24 | 30 / 30 |
| 11.267-13.050 s | 19 | 19 | 20 / 20 |
| 14.000-20.000 s | 69 | 69 | 69 / 69 |

The tail window keeps submitting stable single-texture quad primitives through
the same renderer:

| Primitive | Total | 9-11 s | 11.267-13.05 s | 14-20 s | Texture signature |
| --- | ---: | ---: | ---: | ---: | --- |
| `0x72af405bd370` | 79 | 8 | 6 | 23 | mode `2`, vertices `4`, texture id `155`, `+0xc=29359` |
| `0x72af405bd168` | 75 | 6 | 6 | 23 | mode `2`, vertices `4`, texture id `151`, `+0xc=2606733044` |
| `0x72af405bd148` | 74 | 8 | 6 | 21 | mode `2`, vertices `4`, texture id `150`, `+0xc=29360` |

There is one short-lived tail sample for `0x72af405bd168` with texture id `158`
instead of `151`; the stable pattern still remains the same renderer plus the
same primitive pointers and one texture slot per primitive.

Safe conclusion: in the same run that loaded the official main clean story
`1e31c4fa` 338-frame movie, the game renderer continued to submit stable
single-texture quad primitives during the 11.267-13.05 s final voice/subtitle
tail.  This strengthens `hold_last_frame` from "animation/CRI lifecycle
supported" to "renderer drawCall path continues with stable primitive state".

Do not overclaim this as clean-layer pixel proof.  The primitive sampler does
not yet identify which submitted primitive is the clean main layer versus
foreground/slot layers, and the 512x416 `89802b19` receiver must not be treated
as story continuation.

## Interpretation

The combined evidence now supports this mechanism:

1. The official main clean story CRI is loaded and is only 338 frames.
2. LP/gold-frame foreground CRIs switch around 6.7 s and remain excluded from
   the clean upload edition.
3. In the 11.267-13.05 s final voice/subtitle tail, the same sprite renderer
   texture-state objects continue to be checked/bound.
4. The 2026-07-03 drawCall primitive sampler shows that the renderer continues
   submitting stable single-texture quad primitives in the same tail window.
5. No ordinary GL texture upload/draw continuation was observed in that tail.
6. The 2026-07-03 field sampler shows that the active TextureStateGL numeric
   fields are stable through the tail window, strengthening the hold/steady
   compositor interpretation.

This is stronger than the earlier animation-object-only proof: the renderer
path itself remains active through the voice tail with stable texture-state and
drawCall primitive state after the 338-frame movie boundary.

It is still not exact clean-layer pixel proof.  No framebuffer hash, clean layer
texture hash, or decoded post-frame-338 pixel was captured.  For final Bilibili
publication, the project still needs either:

- a clean-layer texture/pixel proof, or
- an explicit acceptance decision that the current runtime mechanism evidence
  is sufficient for `hold_last_frame`.

The full outer-flow BGM question also remains separate and unresolved.
