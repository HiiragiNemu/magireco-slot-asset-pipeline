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

## Important ac7115 non-story receiver

The `ac7115_001` capture also observed:

| FNV | Size | Movie info | Note |
| --- | ---: | --- | --- |
| `89802b19` | 33574784 | 512x416, 30 fps, 5277 frames | persistent slot/machine or background receiver; not the clean `ac7115_AT_SP_story4_01` continuation |

Do not use this large 512x416 receiver as a substitute for the clean story DGM.
It is outside the clean upload layer and must remain excluded unless a separate
material/gameplay collection intentionally uses it.

## Remaining gates

This evidence still does not finish the Bilibili delivery gate:

- no clean-layer texture hash or pixel/framebuffer capture after the last CRI
  frame has been captured;
- no full outer-flow BGM absence proof exists for this story trigger;
- foreground gold-frame/slot receivers are still excluded from clean story and
  belong in material/effect collections.

The next proof step is targeted compositor/texture metadata in the
tail windows, not more manual contact sheets.
