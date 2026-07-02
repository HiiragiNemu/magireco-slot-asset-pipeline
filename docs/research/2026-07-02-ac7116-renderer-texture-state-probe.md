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

## Interpretation

The combined evidence now supports this mechanism:

1. The official main clean story CRI is loaded and is only 338 frames.
2. LP/gold-frame foreground CRIs switch around 6.7 s and remain excluded from
   the clean upload edition.
3. In the 11.267-13.05 s final voice/subtitle tail, the same sprite renderer
   texture-state object continues to be checked/bound.
4. No ordinary GL texture upload/draw continuation was observed in that tail.

This is stronger than the earlier animation-object-only proof: the renderer
path itself remains active through the voice tail with a stable texture-state
tuple after the 338-frame movie boundary.

It is still not exact clean-layer pixel proof.  No framebuffer hash, clean layer
texture hash, or decoded post-frame-338 pixel was captured.  For final Bilibili
publication, the project still needs either:

- a clean-layer texture/pixel proof, or
- an explicit acceptance decision that the current runtime mechanism evidence
  is sufficient for `hold_last_frame`.

The full outer-flow BGM question also remains separate and unresolved.
