# Corrective Runtime Audit - 2026-06-12

> Superseded in part by
> `docs/research/2026-06-13-z2d-reqsound-production.md`. In particular, the
> 146-event/119-render result below selected events through verified subtitle
> text and therefore omitted valid character sounds whose Z2D layer had no
> display text. Do not use that subset as the final production catalog.

## Invalidated assumptions

- The previous Bilibili builder defaulted to a 1920x1080 upload canvas. This
  inflated native 416x232 and similar media and is not acceptable for archival
  output.
- A filename ending in `__subtitles.mp4` did not prove that verified subtitle
  text existed. Parts with zero subtitle rows could be hard-linked under that
  misleading name.
- EventCn audio is not a complete dialogue timeline. For `ac3102`, all 157
  resolved components are slot effects such as PUSH, failure, cloth glow, and
  symbol movement. Character voice requests are absent from that table.
- `cap3102_*` Z2D resources are blank text-layer templates. Treating the
  template label as subtitle text was incorrect. The real text is populated at
  runtime.

## Verified native entry points

`libGameProc.so` retains exported symbols. The corrective runtime probe targets:

- `zg::snd::RequestCtrl::codeName2ReqId(char const*)`
- `zg::snd::RequestCtrl::setRequestList(zg::snd::Request const&)`
- `SoundMng::play(int, int)`
- `zg::Z2DreqSoundCallback(...)`
- `zg::CZ2DString::SetString(char const*)`
- `zg::sprite::FontImpl::drawText(...)`

The MuMu process is x86_64 and loads ARM64 game code through `libnb.so` and
`libhoudini.so`. A matching x86_64 Frida server can inspect Java/native-bridge
state, while an ARM64 Frida Gadget is required to instrument the exported game
functions directly.

## Output policy

- New experiments must stay under
  `A:\magireco_corrected_research_20260612`.
- Do not modify or delete previous output trees; they remain failure evidence.
- Do not upscale or normalize native media dimensions during validation.
- Subtitle and no-subtitle editions must use separate directories.
- Do not create a subtitle edition unless verified non-placeholder text exists.
- Do not classify auxiliary canvases, icons, or overlay-only loops as complete
  audience-facing animation.

## Official event execution

`C_AnmBase::fnReqScene` is the official event scheduler. The stable live object
is the current `C_ObjDemo` child stored at `C_AnmMain + 0x350`; the task-manager
wrapper returned by `TSK_GAME()` is not a valid replacement for this object.

Two events have been executed through the official scheduler:

- `ac0915_004` (`0x35485f2a564b744f`) requested
  `ac0915_004_c05_MR.dgm`, `ac0915_004_c06_MR.dgm`, and
  `ac0915_004_c06_LP_MR.dgm`. Runtime text was
  `わたくしは里見灯花`; voice request 5364 resolved to
  `snd_20539_bank08_ogg_03684.ogg`.
- `ac0915_005` (`0x7372492d564b744f`) requested
  `ac0915_005_c07_MR.dgm` and `ac0915_005_c07_LP_MR.dgm`. Runtime text was
  `マギウスのひとりだよ`; voice request 5365 resolved to
  `snd_20540_bank08_ogg_03686.ogg`.

This proves that character voice is scheduled independently from both the USM
video and the dynamic text layer. A silent extracted USM is therefore expected;
the correct archival result must reconstruct the event from the game's runtime
timeline and high-quality source OGG, not from the degraded embedded SMZ audio.

## Probe architecture

Calling `fnReqScene` from a Frida JavaScript callback suppresses interceptors for
synchronous nested calls such as `CZ2DString::SetString` because of Frida's
re-entry guard. Deferred sound calls are still observable. Reliable automated
capture therefore uses two simultaneous sessions:

- the event probe supplies the exact event code, label, active object, and start
  time;
- the independent runtime probe records DGM names, dynamic Japanese text, sound
  code lookups, and actual sound playback;
- the resolver joins both logs by their shared Unix clock and emits explicit
  video, OGG, and subtitle tables.

The event probe deliberately does not attach to `CZ2DString::SetString`.
Attaching both sessions to that synchronous call prevented the independent
runtime session from observing the DGM and text records.

No media is rendered until that event-level manifest resolves its official DGM
and OGG assets.

## Static voice recovery

The existing subtitle timeline already maps caption Z2D objects to GDB events
and frame times. It failed for some events because its old matcher expected a
direct sound identifier. Runtime verification shows that the reliable join key
is the normalized displayed Japanese text against the final label segment of
`sound_request_struct_requests.csv`.

For example:

- `アリナ・グレイ ヨロシク` normalizes to
  `アリナグレイヨロシク` and uniquely resolves to request 5133,
  `snd_20025_bank08_ogg_03441.ogg`;
- `わたくしは里見灯花` uniquely resolves to request 5364,
  `snd_20539_bank08_ogg_03684.ogg`;
- `マギウスのひとりだよ` uniquely resolves to request 5365,
  `snd_20540_bank08_ogg_03686.ogg`.

Across those three events, the voice playback call follows the dynamic text
assignment by 55 to 63 ms. Static reconstruction uses a documented 60 ms voice
delay calibration. Only unique normalized matches are eligible for automatic
media generation. A second accepted class covers game labels deliberately
truncated with a trailing hyphen: the speaker code must agree, the candidate
must be unique, and its normalized label must contain at least eight characters
and cover at least 55 percent of the subtitle. Without speaker evidence the
coverage threshold is 80 percent. Low-coverage, fuzzy, and ambiguous matches
remain review-only.

## Audience-facing classification

The static GDB-to-Z2D-to-DGM map contains 7753 events and 40241 event-to-video
rows. That map is useful for official segment order, but it also contains small
icons, square effects, portrait overlays, and multi-layer components. These
must not be flattened into a Bilibili animation catalog.

The corrective catalog classifies each source at its native dimensions:

- `full_frame_landscape`: at least 400x220 with an aspect ratio from 1.55 to
  2.05;
- `mixed_full_frame_and_components`: a real background animation plus separate
  overlays that require the game's compositor;
- `component_only`: icons, effects, square assets, portrait layers, and other
  non-standalone media;
- `unresolved`: missing or unprobed media.

Only events whose official clips are all resolved native full-frame landscape
media and whose EventInfo code exists are eligible for automatic concatenation.
Mixed and component-only events require compositor research or manual review.

## Verified native samples

`A:\magireco_corrected_research_20260612\samples` contains separate
`with_subtitles` and `without_subtitles` directories. The verified `ac0915_004`
and `ac0915_005` outputs remain 416x232 at 30 fps. The subtitle edition differs
only by the verified runtime Japanese text; neither edition contains emulator
UI, slot cabinet icons, or an enlarged upload canvas.

## Corrected production manifests

The first production manifest set is deprecated. It treated every
dimensionally full-frame DGM as a linear clip and missed two runtime semantics:

- some DGM intervals overlap because they are branches or compositor layers;
- an event may continue beyond one pass of its final `_LP` clip.

`production_manifests_v2` adds explicit linear-timeline and extension gates:

- adjacent clips may differ by at most one 30 fps frame (34 ms);
- overlapping clips, gaps, and non-zero starts are rejected;
- a trailing `_LP` clip may repeat until the verified audio/subtitle timeline
  ends;
- a non-looping final frame may be held for at most 200 ms to cover frame
  rounding;
- longer overruns without an `_LP` suffix are rejected.

Of 146 full-frame events with automatically verified voice:

- 119 pass the v2 production gates;
- 27 are retained for runtime/compositor research;
- 20 contain overlapping video intervals;
- 5 overrun the video without a supported loop;
- 2 have both overlap and overrun/start-order defects.

The verified outputs are under:

```text
A:\magireco_corrected_research_20260612\production_outputs_v2
```

They occupy about 516 MB for the final subtitle and no-subtitle MP4 pairs. The
working tree, manifests, contact sheets, and intermediate videos together use
about 0.9 GB. No upload canvas or resolution enlargement is used.

## Full production QA

`qa_event_batch.py` audited every one of the 119 accepted events:

- 119/119 preserve the manifest's native dimensions and frame rate;
- 119/119 contain a non-silent 48 kHz stereo audio stream;
- 119/119 subtitle and no-subtitle editions have identical encoded audio
  hashes;
- 119/119 have non-empty verified SRT files;
- 119/119 match the expected render duration within 50 ms;
- failures: 0.

The machine-readable results are:

```text
A:\magireco_corrected_research_20260612\production_outputs_v2\full_qa_audit.csv
A:\magireco_corrected_research_20260612\production_outputs_v2\full_qa_summary.json
```

A midpoint contact sheet of all accepted events did not show emulator UI, slot
cabinet chrome, or isolated small icons. `ac7205_017`, initially suspicious
from one midpoint frame, was reviewed across five timestamps and confirmed to
be a full-screen Kyubey eye animation with official base audio, voice, and
subtitle.

## Debug-name table limitation

`DebugDispNameList.DIR_NAME_TBL` is a real Java debug-menu table, but the
68-entry table in this APK names Norse-mythology/Hades-style events. It is a
shared-engine or previous-machine remnant and is not authoritative Magia Record
classification data. It must not be merged into the production event catalog.

Authoritative Magia Record naming and ordering currently come from:

- the native `EventInfo` table;
- GDB to Z2D to DGM relationships;
- the official `C_AnmBase::fnReqScene` scheduler;
- runtime sound, text, and DGM probes.

## Remaining compositor set

The 27 rejected v2 events are deliberately not rendered into audience-facing
output. Their DGM overlap indicates branch selection or game-side composition.
The next runtime target is `ac1101_001`, whose title, character start, character
body, and loop intervals overlap. Capturing its official scheduler requests
will determine whether the game selects one branch or composites multiple
layers.
