# Native 416×232 exhaustive longform checkpoint v94

This checkpoint replaces fragment-oriented audience products with a source-exact family rule:

- one exhaustive editorial longform per family or scene;
- include mutually exclusive outcomes;
- retain every distinct visible source exactly once;
- keep a logical readable order without claiming a native single session;
- preserve native 416×232 at 30 fps with H.264 and bounded AAC 48 kHz stereo;
- group none/JA/ZH as editions of one content item;
- keep suffix-free material as one item;
- keep every new result at `HUMAN_PLAYBACK_REQUIRED` until owner playback.

## Closed products

The durable index is:

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\native416_exhaustive_longform_checkpoint_v94_20260819\PRODUCTION_INDEX.csv`

It currently binds six complete groups:

- existing authoritative: `ac4002`, `ac4004`;
- new exact longforms: `ac4003`, `ac7002`, `ac8005`;
- reclassified suffix-free material: `ac7118`.

`ac7002` contains six distinct CRI sources once across five logical chapters. `ac4003` uses the parent inclusive cut boundary (1300 presentation frames) rather than the 1301-frame child Z2D range. `ac8005` excludes eight node-less control cuts and collapses one exact binary alias. `ac7118` contains 45 distinct profile sources; its only two embedded audio streams decode to digital zero, so one bounded silent playback track is synthesized.

## Timing assembly correction

The first multi-chapter remux exposed one AAC priming packet as a 21.333 ms global shift. The active builder now:

1. keeps H.264 video packet data;
2. supplies explicit per-chapter frame durations to the concat demuxer;
3. assembles audio once and bounds it to the video-frame total;
4. remuxes both tracks from zero;
5. rejects non-zero starts, AAC overhang, frame-count drift, or container-duration drift beyond 0.01 frame.

Superseded v90/v91r1/v91r2/v91r3 roots remain provenance only and are excluded from upload.

## Verification

- full repository regression: `Ran 629 tests in 113.567s` — `OK (skipped=4)`;
- all six checkpoint groups: 416×232, 30 fps, zero-start audio/video;
- P16/P17/P18 leakage: zero;
- source media changed: false;
- Bilibili upload performed: false;
- branch or PR created: false.

The remaining 12 family groups stay fail-closed in `BLOCKED_FAMILIES.json`; production continues only when their exact source, layer, parent-cut/tail, audio, and duplicate-free ordering evidence closes.
