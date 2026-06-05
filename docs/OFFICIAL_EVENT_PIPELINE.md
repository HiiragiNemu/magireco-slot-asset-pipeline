# Official Event Reconstruction Pipeline

## Authoritative mapping

The production mapping is:

```text
GDB event -> Z2D resource -> embedded DGM dependency
          -> native CRI name/index -> physical decoded MP4
```

The earlier numeric `main_video_NNNN_candidatesX` mapping is not authoritative
and must not be used for final naming, ordering, audio matching, or merging.

Verified dataset:

- DGM dependencies recovered from Z2D: 11,160
- Event-to-DGM timeline rows: 40,241
- Exact native CRI dependencies: 10,052
- Exact event rows: 37,850
- Unique exact events: 7,753
- Exact event/canvas production rows: 8,482
- Mixed-canvas events: 614

The root Z2D canvas is part of the event identity. Events with multiple decoded
canvases are rendered separately and are never implicitly composited together.

## Video behavior

- A normal DGM followed by `_LP` is an official intro plus loop cycle.
- `_LP` is repeated only when the recovered event/audio duration requires it.
- Overlapping DGM entries are simultaneous layers, not consecutive clips.
- DGM placement uses decoded Z2D coordinates and canvas dimensions.
- `hold-base` retains the final base layer when short overlays end before the
  official audio/event duration.
- Final event composition is not horizontally mirrored. The old raw CRI slice
  tree required `hflip`; the reconstructed event pipeline does not.

## Audio behavior

Audio comes from two official sources:

1. `EventCn.bin` event sound components.
2. Exact Z2D `cap*` dialogue rows tied to GDB frame timing.

An EventCn component is accepted only when its decoded OGG duration matches the
official request duration. A Z2D dialogue row is accepted only when all of the
following are true:

- `timeline_confidence=exact_gdb_frame_and_official_ogg`
- Z2D resource name starts with `cap`
- OGG exists
- decoded signal is actually audible

The full OGG signal audit found:

- OGG files scanned: 9,952
- Actually audible: 9,900
- Silent/control resources: 52

The event production plan contains:

- `audible_no_subtitles`: 5,201
- `audible_with_subtitles`: 284
- `silent_video`: 2,997

Total authoritative rows: 8,482.

## Audio quality

Presence of an AAC stream is not treated as proof of audible or healthy audio.
Every output is decoded and measured.

Official OGG mixtures use:

```text
amix normalize=0
-> alimiter limit=0.85, auto-level disabled
-> -3 dB encoding headroom
-> AAC 256 kbit/s
```

The headroom is required because native FFmpeg AAC can overshoot after encoding
even when the pre-encode PCM peak is limited.

Verified limited-audio output:

- Event/canvas rows: 5,485
- Missing files: 0
- Invalid video/audio streams: 0
- Actually silent outputs: 0
- Duration mismatches above 0.12 seconds: 0
- Highest decoded peak: -0.9 dBFS
- Independent burned-subtitle outputs: 284

Large simultaneous-layer events use a UTF-8 `filter_complex` script file
instead of an inline filter argument. This avoids the Windows process
command-line limit; `ac8050` includes four valid 94-layer canvases that exceed
the limit when represented inline.

## Subtitle behavior

Subtitles are generated only from exact `cap*` dialogue resources. Visual text
resources that are not dialogue are excluded.

Each dialogue event can produce:

- `event__no_subtitles.mp4`
- `event__subtitles_burned.mp4`
- `event.srt`

The current exact subtitle set contains 284 event/canvas outputs.

## Deprecated outputs

The following outputs are diagnostic only and must not drive production:

- `motion_audit_*`
- `low_motion`
- `short_static`
- `static_like`
- old numeric candidate-count merge groups
- old embedded CRI audio classifications

See `MOTION_AUDIT_DEPRECATED.md`.
