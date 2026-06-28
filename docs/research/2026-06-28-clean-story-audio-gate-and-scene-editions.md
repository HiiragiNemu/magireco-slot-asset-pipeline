# Clean-story audio gate and explicit scene editions

Date: 2026-06-28

## Why this change exists

The project cannot treat a normal stream/codec QA pass as final delivery proof.
`ac7114_001`, `ac7115_001`, and `ac7116_001` had correct clean-story visual
composition plans, but the v18 manifests still mixed the slot foreground sound
`8040_シネスコ変化音_金帯` / request `1681` into the audience clean edition.
That sound belongs with the excluded gold-frame/foreground slot material, not
with the normal animation upload version.

The broader mechanism conclusion is unchanged: the game does not manually
classify every `ac` family the way a visual review spreadsheet would.  It uses
GDB/Z2D/DGM data, native event state, `zgSndReqCode`/`SoundMng` requests, and
the final `libAMAIN.so` CSLSound/OpenSL queue.  External reproduction must
therefore be driven by event timelines, request chains, and final audio-output
evidence, not by contact sheets alone.

## Tooling changes

`tools/frida_runtime_probe/audit_runtime_av_trust.py` now:

- audits all production manifests by default when no explicit event/render root
  scope is supplied;
- separates bed/base-scene audio from role voice and foreground/slot effects;
- adds `slot_or_foreground_effect_audio_in_clean_story_candidate`;
- adds `bed_audio_count`, `slot_effect_audio_count`, and
  `slot_effect_audio_names` to the audit CSV;
- uses bed/base-scene audio, not only literal `BGM`, for the missing-bed-audio
  gate.

The all-v18 manifest-only audit is:

```text
A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_clean_audio_gate_20260628
```

Summary:

```json
{
  "audited_events": 926,
  "status_counts": {
    "blocked_pending_runtime_av_verification": 897,
    "no_av_trust_flags_detected": 29
  },
  "semantic_lane_counts": {
    "audible_excluded_component_with_role_voice": 56,
    "normal_animation_candidate_needs_visual_speech_review": 317,
    "non_dialogue_audio_or_effect_component": 14,
    "audible_gameplay_result_with_role_voice": 351,
    "pure_gameplay_or_effect_material": 126,
    "excluded_material_or_component": 17,
    "blocked_short_role_voice_variant": 45
  }
}
```

New risk flag counts include:

```text
slot_or_foreground_effect_audio_in_clean_story_candidate    134
role_voice_scene_without_bed_audio_evidence                 17
```

This confirms a general gate is needed; the issue was not isolated to one
family.

The strategy queue was also regenerated with this full AV trust CSV:

```text
A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_clean_audio_gate_20260628
```

Key queue effect:

```json
{
  "ready_missing_single_event_QA": 217,
  "ready_missing_single_event_QA_delivery_actionable": 4,
  "ready_missing_single_event_QA_av_blocked": 213,
  "runtime_av_trust_status_counts": {
    "blocked_pending_runtime_av_verification": 897,
    "no_av_trust_flags_detected": 29
  }
}
```

This is intentionally conservative.  It prevents the next batch runner from
promoting technically render-ready events that still lack reliable AV evidence.

## ac7114/ac7115/ac7116 clean-audio correction

The composition plans now exclude request `1681` /
`8040_シネスコ変化音_金帯`:

```text
tools/frida_runtime_probe/composition_plans/ac7114_001.json
tools/frida_runtime_probe/composition_plans/ac7115_001.json
tools/frida_runtime_probe/composition_plans/ac7116_001.json
```

The corrected small production-manifest rebuild is:

```text
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628
```

It contains 14 runtime/composition-plan events.  The three corrected events are
ready, with the foreground effect removed:

| event | audio count | retained audio summary |
| --- | ---: | --- |
| `ac7114_001` | 4 | `42040_SPストーリー3_01_2G` + 3 role voices |
| `ac7115_001` | 9 | `42060_SPストーリー4_かえでドッペル_01` + 8 role voices |
| `ac7116_001` | 2 | `42080_SPストーリー5_みふゆとももこ_01` + 1 role voice |

The corrected single-event render/QA output is:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628
```

QA:

```json
{
  "audited_events": 3,
  "passed": 3,
  "failed": 0,
  "subtitle_and_no_subtitle_audio_identical": 3,
  "non_silent_audio": 3,
  "audio_tail_gap_passed": 3
}
```

The old v18 `validation_outputs_v18_clean_story_ac7114_16_001` and
`validation_outputs_v18_clean_story_ac7114_16_full` outputs should be treated as
old evidence/samples for this subset because they include the foreground gold
band SFX.

## Explicit same-scene long edition

`build_series_editions.py` is prefix/family based and is not suitable for a
scene that spans `ac7114`, `ac7115`, and `ac7116`.  New tool:

```text
tools/frida_runtime_probe/build_scene_editions.py
```

It takes an explicit `--event` sequence, requires QA-passed single-event inputs,
direct-stream-copies subtitle/no-subtitle long videos, shifts SRT cues, and
writes source hashes plus cumulative timeline.

Generated review scene:

```text
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate
```

Scene manifest:

```text
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate\scene_manifest.json
```

Outputs:

```text
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate\without_subtitles\ac7114_16_sp_story_clean_audio_gate__scene.mp4
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate\with_subtitles\ac7114_16_sp_story_clean_audio_gate__scene__subtitles.mp4
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate\subtitles\ac7114_16_sp_story_clean_audio_gate__scene.srt
```

Scene QA summary:

```json
{
  "status": "passed",
  "event_count": 3,
  "duration_ms": 44854,
  "subtitle_cue_count": 10,
  "width": 512,
  "height": 288,
  "frame_rate": "30/1",
  "audio_sample_rate": "48000",
  "audio_channels": 2
}
```

Important boundary: this fixes the known foreground-effect audio pollution and
creates an auditable same-scene review long edition.  It does not by itself
prove every role voice mouth movement; the runtime AV trust audit still flags
role-voice visual-speech verification as a delivery gate for final publication.

## Post-review tail-hold and BGM note

User review later confirmed that the v19 voice/subtitle mapping is correct, but
also identified a visible tail-hold problem: `ac7116_001__subtitles.mp4` freezes
around 11 seconds while audio/subtitles continue to about 13 seconds.  The same
class of short tail exists in the joined scene.

Manifest and stream checks show:

| event | source video duration | render duration | hold tail | retained bed/base-scene audio |
| --- | ---: | ---: | ---: | --- |
| `ac7114_001` | 9167 ms | 9629 ms | 462 ms | `42040_SPストーリー3_01_2G` |
| `ac7115_001` | 21200 ms | 22167 ms | 967 ms | `42060_SPストーリー4_かえでドッペル_01` |
| `ac7116_001` | 11267 ms | 13027 ms | 1760 ms | `42080_SPストーリー5_みふゆとももこ_01` |

For `ac7116_001`, the source DGM did not show a 0.5 s+ freeze under
`ffmpeg`'s `freezedetect`, while the rendered subtitle edition reported
`freeze_start: 11.2`.  Therefore the visible still tail is a render-policy
effect from `video_extension_policy=hold_last_frame`, used to preserve the
official final role voice `31186_282_mihu_く…ぐ…` through 13027 ms.  It is not
yet proven that the game itself displays the clean main-story final frame for
that whole tail after excluding the gold-frame foreground layer.

The current BGM interpretation is also narrower than "no BGM": these manifests
retain the `420xx_SPストーリー...` bed/base-scene audio tracks.  `bgm_request_count=0`
only means there is no literal `BGM`-named request in the production manifest.
Whether an additional outer-state BGM should be present remains a runtime
evidence question.

`tools/frida_runtime_probe/audit_runtime_av_trust.py` now adds
`visual_tail_hold_needs_runtime_confirmation` when a role-voice event relies on
a visible `hold_last_frame`/`black_tail` extension of at least 750 ms.  The
updated v19 subset audit is:

```text
A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v19_clean_audio_gate_tail_hold_20260628
```

Result:

```json
{
  "audited_events": 3,
  "status_counts": {
    "blocked_pending_runtime_av_verification": 3
  }
}
```

Consequently the ac7114-16 joined scene is a review/mechanism-validation output,
not a final Bilibili upload candidate, until runtime visual tail and BGM/bed
completeness are proven.

## ac7116 visual-tail probe follow-up

Follow-up report:

```text
docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md
```

The v3 visual-tail runtime probe captured CRI player lifecycle and `SetData`
metadata while forcing `ac7116_001`.  It confirmed the official gold-frame
foreground data and the LP foreground switch around 6.66 s, but it did not
observe the clean main story payload `ac7116_AT_SP_story5_01.usm` in
`CriManaWrapper::SetData`.  The main movie may have been preloaded or reached
through another path, so this is not proof that the clean main-story tail hold
is native.

Two follow-up attempts were inconclusive:

- v4 used active CRI `NativeFunction` queries and timed out; do not repeat that
  strategy as-is.
- v5 installed passive frame-YUVA metadata hooks, but `event_scene_host` did not
  find an active `C_AnmBase` scene object within 12 s, so no event was reached.

The delivery decision is unchanged: the v19 ac7114-16 scene is useful for
review because voice/subtitle timing is now correct, but it remains blocked as
a final Bilibili upload candidate until the visual tail and BGM/bed questions
are proven by runtime evidence.
