# 2026-06-27 Runtime AV recapture report

This report records the repair work after user review invalidated the v18
generic/contact-sheet samples.  The invalidated renders must not be used as
delivery evidence, and no new upload-ready render should be promoted until the
runtime AV timeline is complete.

## Trust boundary

The only acceptable source for audio/subtitle promotion is official runtime
evidence or static evidence that can be traced to the same runtime mechanism.
The rejected v18 outputs showed why visual contact sheets are insufficient:

- a contact sheet cannot reveal missing BGM;
- a contact sheet cannot prove that voice and subtitles are synchronized;
- short near-duplicate clips are not Bilibili-ready long-form animations;
- a clip with role voice is not a pure material/effect component just because
  the visual layer looks like a slot/gameplay asset.

## Mechanism findings

The game does not need a hand-curated per-`ac` classification table to play
events.  The observable mechanism is data-driven:

1. An official event code selects an event object from the runtime event table.
   The event code must come from the official catalog/timeline.  Hashes derived
   directly from the `acNNNN_MMM` suffix are not reliable event selectors.
2. The event object schedules one or more Z2D scenes.  Z2D data can contain DGM
   references such as `[ac0921_jikai_yokoku_3on_01.dgm]`, text layers, and sound
   callbacks.
3. Actual audible output is proven by `SoundMng::play*` runtime calls.  Higher
   level requests are useful evidence, but a production manifest is not complete
   unless the actual play requests resolve to OGG assets.
4. Subtitles must be derived from runtime text layers or from verified voice
   labels when the runtime text layer is blank or non-dialogue.  Voice-label
   fallback is auditable but weaker than visible runtime text.
5. The composition timeline must follow the runtime order and timestamps.  It
   is invalid to concatenate all visually related DGM files or to truncate the
   resolver window before the event finishes.

The generic path is therefore: official event code -> runtime event capture ->
runtime DGM/text/sound timeline -> asset resolution -> classification gate ->
composition plan -> render -> AV QA -> user review sample.

## Resolver correction

`resolve_official_event_capture.py` now separates empty string sound callbacks
from real unresolved sound requests:

- `unresolved_sound_events.csv` is reserved for actual incomplete audio
  evidence;
- `ignored_sound_events.csv` records empty callback noise such as an empty
  `ctrl_snd_req_sound_code_callback`;
- the default post-event resolve window is now 60 seconds, because
  `ac0921_001` loads later DGM assets at about 27.46 seconds and was previously
  truncated by the 15 second default.

## Re-capture evidence

Raw official-code captures:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\bad_sample_recapture_raw_official_codes
```

Long-window resolved manifests:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\bad_sample_recapture_resolved_official_codes_v3_long_window
```

| Event | Official code | Runtime videos | Actual audible OGG plays | Subtitles | Unresolved sounds | Finding |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `ac0921_001` | `0x544549382d424c4d` | 3 | 5 | 4 | 0 | Missing-BGM complaint confirmed against old render: runtime plays `2990_次回予告_レバー` at ~74 ms, then four Iroha voice lines. The later `3on` and `3on_lp` DGM assets appear at ~27465 ms, so short-window resolution was incomplete. |
| `ac4901_025` | `0x32642b4334422a25` | 2 | 2 | 1 | 0 | Official runtime plays the effect `8104_働きｸﾞﾏ_ﾎﾞｰｶﾞﾝ_大爆発` and Iroha voice `15498_iro_AT_働きグマ_よし`. This should not be promoted as clean story animation when visual speech validation fails. |
| `ac4901_026` | `0x6624235234422a25` | 2 | 2 | 1 | 0 | Same AV structure as `ac4901_025`, with blue visual variant. This is not a useful Bilibili long-form story unit by itself. |
| `ac7204_003` | `0x3546596753252d6e` | 2 | 2 | 1 | 0 | Contains role voice `21061_nemu_AT_イブねむと灯花_見滝原に進路を向-`; therefore it is not pure material. |
| `ac7204_017` | `0x4c34762453252d6e` | 3 | 2 | 1 | 0 | Contains role voice `16232_yac_AT_イブねむと灯花_させないわ`; therefore it is not pure material. |

## Classification consequences

The next manifest layer needs three separate buckets:

1. **Normal animation/story candidate**: runtime AV timeline is complete and
   visual/subtitle/voice checks support a watchable animation unit.
2. **Audible gameplay/result component**: contains official role voice or
   dialogue, but the visual layer is slot/gameplay/result UI rather than normal
   story animation.  These can be reviewed in their own collection, not merged
   into pure materials and not promoted as story uploads.
3. **Silent or non-dialogue material/effect**: no official role voice/dialogue.
   These can go to material/effect collections.

`ac7204` belongs in bucket 2 until a more specific per-event review proves a
normal animation sequence.  `ac4901_025/026` also belong in bucket 2 or blocked
review, not in clean-story delivery.

## Required next work before rendering

- Build composition plans from the long-window runtime manifests, preserving
  single-event segments and producing only small user-review samples first.
- Add an AV QA gate that fails any upload candidate when actual-play OGG,
  subtitle timeline, video timeline, or expected BGM evidence is missing.
- Add a classification gate that prevents audible gameplay/result clips from
  entering pure material collections or clean-story Bilibili collections.
- Replace contact-sheet-only QA with AV timeline reports plus short watchable
  review samples that the user can verify directly.
