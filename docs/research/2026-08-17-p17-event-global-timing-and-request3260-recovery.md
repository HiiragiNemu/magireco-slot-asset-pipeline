# P17 ac6004 event-global timing and request 3260 recovery

## Result

P17 remains **not uploadable** until project-owner playback, but the former
mechanical blocker is closed and a new bounded review candidate exists.  The
old P17 none/JA/ZH family remains quarantined and is not overwritten.

Authoritative review root:

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\bilibili_incremental_review_v71r3_p17_ac6004_event_global_timing_20260817`

The three files are 416x232, 30fps, H.264/AAC 48kHz stereo, 46.900 s, and
`HUMAN_PLAYBACK_REQUIRED`.  The root uses same-volume hardlinks to the immutable
production output.  `START_HERE.md` lists the exact review intervals.

## Evidence chain

The bounded runtime capture reopened the five family events without starting,
stopping, or switching any foreground game:

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\runtime_p17_family_scene_motion_v16_20260817\P17_AC6004_FAMILY_RUNTIME_SCENE_MOTION.json`

Slot, Exedra, and Totentanz retained the same PIDs, and the Android crash buffer
was empty.  For ac6004_005, _006, _008, and _012, the matching parent cut has
instance offset 0 and cut start 0; each matching player layer has speed 1; the
child Z2D node has no time remap.  Runtime-loaded motion keys therefore give the
event-global cue frames directly.  ac6004_011 retains its previous resolved
runtime manifest.

The derived family authority is:

`D:\magia\MyProducts\casino\magireco_corrected_research_20260612\p17_ac6004_family_event_global_timing_authority_v1_20260817\P17_AC6004_FAMILY_EVENT_GLOBAL_TIMING_AUTHORITY.json`

The authority binds the exact libGameProc sample, IDA parent/child field
semantics, runtime capture and scripts, four old manifests, both Z2D catalogs,
and the official request-3260 OGG.

## Exact corrections

- ac6004_005: requests 3736 and 3259 start at frames 1 and 137.
- ac6004_006: request 3735 starts at frame 5.  Missing request 3260 is restored
  at frame 124 (4.133 s inside the event) with its official 7.899 s OGG.
- The request-3260 graphical text is presented in three exact ranges inside the
  event: frames 124-160, 179-280, and 290-355.
- ac6004_008: request 2787 starts at frame 10; the parent event remains 172
  frames rather than being shortened to the last audio endpoint.
- ac6004_012: requests 3261 and 3262 start at frames 3 and 110.

The family timeline is 0-8.400, 8.400-22.600, 22.600-28.333,
28.333-38.400, and 38.400-46.900 seconds.  No family-wide visual shift is used.

## Fail-closed implementation

`build_event_production_manifests.py` now accepts an optional exact expected
Z2D request set and exact recovery records.  A recovered audio row must bind an
existing file, SHA-256, duration, request identity, callback frame, source
catalog, and authority.  A recovered subtitle requires an exact end boundary.
Unexpected request sets, unmatched cues, or existing-row conflicts remain
blocked.

`build_no_bgm_story_family_editions.py` now restores an unvoiced graphical
continuation only when it is `graphical_display_text`, event-global resolved,
has the exact parent-scene/motion-key timing scope, and identifies the bound
timing override.  Child-local graphical rows and unrelated material text remain
excluded.

## Rejected checkpoints retained for audit

- v71 restored request 3260 but shortened ac6004_008 to 129 frames.
- v71r1 preserved the cut but used a quantized duration as raw content end; no
  media was rendered from it.
- v71r2 had correct audio and event lengths but its subtitle edition omitted the
  two exact request-3260 continuation texts.

Each rejected D: root has an adjacent `.FAILED.md`.  None is a review or upload
source.

## Current gate

Automated QA and package verification pass.  Owner playback must confirm the
ZH candidate first, especially 8.400-20.432 s, then 22.600-28.333 s and
38.400-46.900 s.  Until that happens, old P17 and the v71r3 replacement both
remain outside upload-ready status.  P16 and P18 status is unchanged.
