# ac7114/ac7115/ac7116 CRI receiver tail sampler

Date: 2026-07-02

## Purpose

This report extends the `ac7116_001` tail-hold investigation to the full
`ac7114_001 + ac7115_001 + ac7116_001` scene.  The goal is to replace manual
visual guessing with runtime evidence:

- which CRI receiver is the clean main story movie;
- how long the official movie is;
- when the game stops actively updating/querying that receiver;
- whether the receiver remains resident while the higher animation object can
  continue through the voice/subtitle tail.

This report is still metadata-only.  It does not contain decoded frames,
textures, PCM, or source assets.

## Tools

Runtime probe:

```text
tools/frida_runtime_probe/visual_tail_probe.js
```

Summarizer:

```text
tools/frida_runtime_probe/summarize_cri_receiver_samples.py
```

The summarizer writes:

```text
summary\cri_receiver_summary.json
summary\cri_receiver_events.csv
```

## Event codes

| Event | Runtime code |
| --- | --- |
| `ac7114_001` | `0x4f71466b3d723041` |
| `ac7115_001` | `0x5773382374447854` |
| `ac7116_001` | `0x2476304366614152` |

## Captures

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7114_v1_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7115_v1_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702
```

## Main story receiver summary

| Event | Main story FNV | Size | Movie info | Update span | `GetStatus=5` span | Sample span |
| --- | --- | ---: | --- | --- | --- | --- |
| `ac7114_001` | `a5b2c906` | 1903456 | 512x288, 30 fps, 275 frames | 3-8131 ms | 263-9065 ms | 180-20727 ms |
| `ac7115_001` | `4ad69770` | 3940544 | 512x288, 30 fps, 636 frames | 3-20145 ms | 278-20959 ms | 152-28734 ms |
| `ac7116_001` | `1e31c4fa` | 1955904 | 512x288, 30 fps, 338 frames | 4-11134 ms | 267-10973 ms | 195-20746 ms |

The movie durations implied by frame count at 30 fps are:

| Event | Movie duration | Clean render duration | Tail policy |
| --- | ---: | ---: | --- |
| `ac7114_001` | 9167 ms | 9629 ms | `hold_last_frame` |
| `ac7115_001` | 21200 ms | 22167 ms | `hold_last_frame` |
| `ac7116_001` | 11267 ms | 13027 ms | `hold_last_frame` |

These captures support the current mechanism model:

1. The clean main story movie reaches its official CRI duration.
2. The game stops actively updating/querying the main story CRI receiver around
   that duration.
3. The receiver remains resident afterward.
4. Separate animation-state captures prove the higher animation object can
   continue ticking after the main movie duration.
5. Therefore the current clean `hold_last_frame` policy is runtime-supported
   for review/mechanism-validation renders.

## 2026-07-03 Z2D movie-layer closure

The CRI receiver evidence above was extended with the metadata-only Z2D
movie-layer probe:

```text
tools/frida_runtime_probe/z2d_movie_layer_probe.js
tools/frida_runtime_probe/summarize_z2d_movie_layer_probe.py
```

Capture summaries:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7114_v1_20260703\summary_v1\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7115_v1_20260703\summary_v1\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703\summary_v2\z2d_movie_layer_summary.json
```

All three captures exited cleanly and observed the official main story
`CriManaWrapper::SetData` plus the named clean story Z2D movie object in the
same run:

| Event | Main story `SetData` | Named Z2D movie | Z2D object | End frame | Texture / primitive |
| --- | --- | --- | --- | ---: | --- |
| `ac7114_001` | 119 ms, `a5b2c906`, 1903456 bytes | `ac7114_AT_SP_story3_01.dgm` | play `0x72affba47728`, elem `0x72affba476d8` | 274 | texture-like `165`, primitive `0x72af4e66e168` / texture id `165` |
| `ac7115_001` | 157 ms, `4ad69770`, 3940544 bytes | `ac7115_AT_SP_story4_01.dgm` | play `0x72affb9d0c28`, elem `0x72affb9d0bd8` | 635 | texture-like `197`, primitive `0x72af4e66e168` / texture id `197` |
| `ac7116_001` | 121 ms, `1e31c4fa`, 1955904 bytes | `ac7116_AT_SP_story5_01.dgm` | play `0x72affb9c0ae8`, elem `0x72affb9c0a98` | 337 | texture-like `153`, primitive `0x72af4e66e168` / texture id `153` |

Tail-window proof examples:

| Event | Tail window | Representative rows |
| --- | --- | --- |
| `ac7114_001` | 9.167-9.629 s | `IsDrawTime(input=274)=1`, `GetDecodeFrame(input=274)=274`, `ExecPlayMovie +0x4=274 +0x20=165 +0x28=274 +0x38=512 +0x40=288`, then `drawCall primitive=0x72af4e66e168` |
| `ac7115_001` | 21.200-22.167 s | `IsDrawTime(input=635)=1`, `GetDecodeFrame(input=635)=635`, `ExecPlayMovie +0x4=635 +0x20=197 +0x28=635 +0x38=512 +0x40=288`, then `drawCall primitive=0x72af4e66e168` |
| `ac7116_001` | 11.267-13.027 s | `IsDrawTime(input=337)=1`, `GetDecodeFrame(input=337)=337`, `ExecPlayMovie +0x4=337 +0x20=153 +0x28=337 +0x38=512 +0x40=288`, then `drawCall primitive=0x72af4e66e168` |

The named clean story objects remain observable beyond each audio/subtitle tail:

| Event | `ExecPlayMovie` span | `GetDecodeFrame` span | Correlated `drawCall` span |
| --- | --- | --- | --- |
| `ac7114_001` | 113-17834 ms | 114-17737 ms | -1504-17968 ms |
| `ac7115_001` | 135-31787 ms | 136-31788 ms | -1491-31789 ms |
| `ac7116_001` | 115-25931 ms | 116-25932 ms | -1453-25832 ms |

Conclusion: for all three clean story events, the game itself keeps the named
512x288 clean-story Z2D movie element drawable at its final frame while the
voice/subtitle tail continues.  The current `hold_last_frame` policy for
`ac7114_001`, `ac7115_001`, and `ac7116_001` is therefore runtime-mechanism
proven, not a visual guess.

This still does not answer the separate BGM/outer-flow question.  Do not mark
the Bilibili long scene final until BGM/bed presence is proven or proven absent.

## Important ac7115 non-story receiver

The `ac7115_001` capture also observed:

| FNV | Size | Movie info | Note |
| --- | ---: | --- | --- |
| `89802b19` | 33574784 | 512x416, 30 fps, 5277 frames | persistent slot/machine or background receiver; not the clean `ac7115_AT_SP_story4_01` continuation |

Do not use this large 512x416 receiver as a substitute for the clean story DGM.
It is outside the clean upload layer and must remain excluded unless a separate
material/gameplay collection intentionally uses it.

The 2026-07-03 Z2D `ac7115_001` run also observed small CRI loads during/after
the tail:

| Relative ms | FNV | Size | Note |
| ---: | --- | ---: | --- |
| 21272 | `7fc38d87` | 900160 | additional transition/follow-up CRI, not the named main clean story object |
| 27473 | `400d7791` | 560128 | later transition/follow-up CRI, not the named main clean story object |

These must not replace `ac7115_AT_SP_story4_01.dgm` for the clean story layer.

## Remaining gates

This evidence still does not finish the Bilibili delivery gate:

- no full outer-flow BGM absence proof exists for this story trigger;
- foreground gold-frame/slot receivers are still excluded from clean story and
  belong in material/effect collections.

The visual tail-hold gate is now resolved at runtime-mechanism level for this
three-event clean story sequence.  The next proof step is BGM/outer-flow audio
capture, not more manual contact sheets.
