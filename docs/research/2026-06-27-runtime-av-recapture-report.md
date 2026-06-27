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

## First repaired user-review sample

`ac0921_001` now has an explicit composition plan:

```text
tools/frida_runtime_probe/composition_plans/ac0921_001.json
```

The plan keeps the official full-frame video sequence at native 416x232:

1. `ac0921_jikai_yokoku_lev_01`
2. `ac0921_jikai_yokoku_3on_01`
3. `ac0921_jikai_yokoku_3on_01_lp`

It uses the long-window runtime audio/subtitle evidence: five actual OGG plays
and four subtitle rows.  The mute control request
`259_ボタン音ボイス消音` is filtered out of the production audio mix because it
has no OGG media and zero duration.

Rebuilt production manifest:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\production_manifests_runtime_repair_v1_ac0921\events\ac0921_001.json
```

User-review render:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\without_subtitles\ac0921_001.mp4
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\with_subtitles\ac0921_001__subtitles.mp4
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\subtitles\ac0921_001.srt
```

QA summary:

```json
{
  "audited_events": 1,
  "passed": 1,
  "failed": 0,
  "subtitle_and_no_subtitle_audio_identical": 1,
  "non_silent_audio": 1,
  "duration_ms": 32766,
  "video": "416x232 30/1",
  "audio": "AAC 48000 Hz stereo"
}
```

This is a review sample, not a blanket approval of the old v18 batch.  The
remaining bad-sample families still require the same runtime-timeline and
classification gates before rendering.

## Role-voice lane gate

`audit_runtime_av_trust.py` now separates role voice from BGM/SE/effect audio.
It no longer treats every `z2d_req_sound` as voice.  The lane gate uses subtitle
voice request IDs plus speaker tokens such as `iro`, `nemu`, and `yac` to count
only role voice, then writes `semantic_lane` and `role_voice_count` to the audit
CSV.

Bad-sample lane audit:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_lane_audit_bad_samples_v1\runtime_av_trust_audit.csv
```

Summary:

```json
{
  "audited_events": 5,
  "status_counts": {
    "blocked_pending_runtime_av_verification": 5
  },
  "semantic_lane_counts": {
    "normal_animation_candidate_needs_visual_speech_review": 2,
    "blocked_short_role_voice_variant": 2,
    "audible_gameplay_result_with_role_voice": 1
  }
}
```

This is the machine-checkable form of the user correction:

- `ac4901_025` and `ac4901_026` are short role-voice variants and remain blocked
  from Bilibili/clean-story promotion.
- `ac7204_003` is gameplay/result with role voice and must not be pure material.
- `ac7204_017` has role voice and remains blocked pending visual/speech review,
  not pure material.
- `ac0921_001` remains a user-review sample until the repaired render is
  visually accepted.

The v18 strategy audit was also regenerated without overwriting the older audit:

```text
A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_role_lane_20260627
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_role_lane_20260627
```

The regenerated strategy keeps the existing 51 AV-blocked ready-missing events
out of the actionable render queue and adds `av_semantic_lane` to queue CSVs.
The blocked lanes are:

```json
{
  "audible_gameplay_result_with_role_voice": 41,
  "blocked_short_role_voice_variant": 36,
  "normal_animation_candidate_needs_visual_speech_review": 11
}
```

## Source integrity audit

`audit_render_source_integrity.py` was added to make a rendered event auditable
without re-rendering.  It reads a `render_manifest.json`, follows its source
production manifest, and writes:

- `source_integrity_manifest.json`;
- `source_hashes.csv`;
- `source_timeline.csv`.

For `ac0921_001`, the audit output is:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\audit
```

Important audited values:

```json
{
  "event": "ac0921_001",
  "event_code_hex": "0x544549382d424c4d",
  "event_index": "2814",
  "event_key": "MLB-8IET",
  "clip_count": 3,
  "audio_count": 5,
  "subtitle_count": 4,
  "output_hash_match": true
}
```

The timeline CSV records the cumulative event timeline and input hashes.  The
first entries prove the corrected BGM and main voice timings:

```text
video    0-27433    ac0921_jikai_yokoku_lev_01
audio    74-1840    2990_次回予告_レバー
audio    2579-9318  30031_037_iro_私どうして忘れちゃ
audio    9694-16167 30032_075_iro_上手く言えないけど
video    27433-32433 ac0921_jikai_yokoku_3on_01
video    32433-32766 ac0921_jikai_yokoku_3on_01_lp
```
