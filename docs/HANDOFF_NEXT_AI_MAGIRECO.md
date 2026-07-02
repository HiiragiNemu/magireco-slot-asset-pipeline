# MagiaReco animation recovery handoff for the next AI

Date: 2026-06-28

This is the core handoff document for continuing the project.  Treat it as the
first file to read before touching any renders, manifests, probes, or GitHub
state.

## Objective

Recover the game's animation/video content into auditable, watchable outputs:

- preserve original media resolution, frame rate, bitrate class, audio sample
  rate, and channel layout;
- produce both subtitle and no-subtitle editions;
- keep original per-event segment files;
- also produce same-scene long videos suitable for Bilibili upload when the
  scene is verified;
- keep slot/gameplay/foreground effects and pure material clips in separate
  material collections, not in normal animation uploads;
- base voice, subtitle, BGM/bed, and SE timing on game runtime evidence or
  static evidence that is directly traceable to game data;
- keep source hashes, manifests, event indexes, cumulative timelines, QA
  reports, and invalidation records.

The user does not want slot foreground/gold-frame/particle gimmicks mixed into
normal story animation.  If the game has a slot effect that should be preserved,
make a separate material/gameplay collection for it.

## Hard constraints

Do not violate these:

- Do not delete source files.
- Do not generate the old 124 GB 1080p/upscaled output.
- Do not upscale.
- Do not use the old motion/static classification as final evidence.
- Do not infer CRI indices from the numeric suffix of an `ac` event.
- Do not mix subtitle and no-subtitle editions.
- Do not promote contact-sheet or stream/codec QA as delivery proof.
- Do not classify an event as pure material if it contains role voice, dialogue,
  or subtitle-relevant sound.
- Do not batch-render AV-blocked role-voice scenes for publication.

## Authoritative working locations

Repository/worktree:

```text
C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
```

Production branch:

```text
codex/corrected-runtime-pipeline
```

The accidental `main` branch is not authoritative for this project.

Runtime/game extraction roots currently in scope:

```text
C:\Users\cryne\Downloads\MagiaRe\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==
A:\magireco_installed_pull_20260603
A:\magireco_corrected_research_20260612
A:\magireco_bili_fulltest_20260603
D:\MagiReco_Reverse
```

Space policy:

- A: current working/research outputs while space remains.
- C: fast P5801X scratch for many small files if A is tight.
- D: repository and final verified long/review collections.

## Current repo state at handoff

Before this handoff update, the branch was clean at:

```text
186ccef Add clean story audio gate and scene editions
```

After this handoff, expect a newer commit containing:

- the new tail-hold risk gate in `tools/frida_runtime_probe/audit_runtime_av_trust.py`;
- this handoff document;
- updated project status.

Always start with:

```powershell
git -C C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw== status --short --branch
git -C C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw== log -5 --oneline --decorate
```

## User-verified current state

The user reviewed:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628
```

User feedback:

- voice and subtitles are correct for `ac7114_001`, `ac7115_001`, and
  `ac7116_001`;
- `ac7116_001__subtitles.mp4` visibly freezes around 11 seconds while voice
  continues to about 13 seconds;
- the same tail-hold symptom is present less strongly in the other segments and
  in the joined scene;
- no obvious BGM is heard; user is unsure whether the original slot game has no
  BGM here or whether the pipeline removed it.

Do not ignore this feedback.  The v19 audio/subtitle correctness is progress,
but the visual-tail and BGM/bed completeness questions remain open delivery
gates.

## ac7114/ac7115/ac7116 current audit

Relevant runtime resolved manifests:

```text
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved\ac7114_001_v1\event_manifest.json
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved\ac7115_001_v1\event_manifest.json
A:\magireco_corrected_research_20260612\runtime_sequence_20260618\resolved\ac7116_001_v1\event_manifest.json
```

Current v19 production manifests:

```text
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628\events\ac7114_001.json
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628\events\ac7115_001.json
A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628\events\ac7116_001.json
```

Current v19 single-event renders:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628
```

Current same-scene long review output:

```text
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate
```

Important correction already made:

- request `1681` / `8040_シネスコ変化音_金帯` is excluded from clean story;
- it belongs to gold-frame/foreground slot presentation, not the normal upload
  animation edition;
- the clean edition keeps the main story screen, not the gold frame layer.

Timing table:

| Event | Source DGM | Native video duration | Render duration | Tail extension | Policy | Retained bed/base-scene audio |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `ac7114_001` | `ac7114_AT_SP_story3_01.mp4` | 9.167 s | 9.629 s | 0.462 s | `hold_last_frame` | `42040_SPストーリー3_01_2G` |
| `ac7115_001` | `ac7115_AT_SP_story4_01.mp4` | 21.200 s | 22.167 s | 0.967 s | `hold_last_frame` | `42060_SPストーリー4_かえでドッペル_01` |
| `ac7116_001` | `ac7116_AT_SP_story5_01.mp4` | 11.267 s | 13.027 s | 1.760 s | `hold_last_frame` | `42080_SPストーリー5_みふゆとももこ_01` |

`ac7116_001` audio timeline:

- `10351 / 42080_SPストーリー5_みふゆとももこ_01`: starts 86 ms,
  duration 11266 ms, ends 11352 ms; this is retained;
- `9537 / 31186_282_mihu_く…ぐ…`: starts 8883 ms, duration 4144 ms,
  ends 13027 ms; this is the dialogue tail and subtitle end;
- `1681 / 8040_シネスコ変化音_金帯`: excluded from clean story because it is
  foreground/gold-frame slot effect audio.

Freeze check:

- source `ac7116_AT_SP_story5_01.mp4` did not show a 0.5 s+ freeze under
  `ffmpeg -vf freezedetect=n=0.003:d=0.5`;
- rendered `ac7116_001__subtitles.mp4` reports `freeze_start: 11.2`;
- this matches the manifest: the renderer holds the final main-story frame from
  the end of the DGM to the end of the last voice/subtitle.

Current interpretation:

- the user is right that the render freezes at the end;
- the freeze is introduced by the current clean renderer's
  `hold_last_frame` policy, not by the source DGM itself;
- this was done to avoid cutting off official voice/subtitle tail;
- it is not yet proven that the live game would show exactly the same clean
  main-story final-frame hold after excluding gold-frame foreground layers.

Current gate:

`audit_runtime_av_trust.py` now emits:

```text
visual_tail_hold_needs_runtime_confirmation
```

when a role-voice event uses `hold_last_frame` or `black_tail` and the visual
tail is at least 750 ms.  The current v19 subset audit is:

```text
A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v19_clean_audio_gate_tail_hold_20260628
```

Summary:

```json
{
  "audited_events": 3,
  "status_counts": {
    "blocked_pending_runtime_av_verification": 3
  },
  "semantic_lane_counts": {
    "normal_animation_candidate_needs_visual_speech_review": 3
  }
}
```

`ac7115_001` and `ac7116_001` currently hit the visual-tail flag.  Therefore the
joined long scene is a user-review/mechanism-validation output, not a final
Bilibili upload candidate yet.

## BGM/bed audio state

Do not equate `bgm_request_count=0` with "the pipeline removed BGM".

For `ac7114/ac7115/ac7116`, the manifests retain one `420xx_SPストーリー...`
audio track each.  The current audit treats this as bed/base-scene audio even
though the literal name is not `BGM`.

Open question:

- Is the retained `420xx_SPストーリー...` track the full native scene bed for
  this slot story event, or should an outer gameplay/state BGM also be present?

Required proof before final publication:

- runtime sound-code/BGM hook trace for this scene path, or
- final `CSLAndroidSimpleBufferQueue::Enqueue` capture proving the full
  audible output, or
- a direct game-produced capture that proves no additional BGM exists.

## Invalidated outputs that must not be promoted

The user found major defects in earlier v18/generic outputs:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626\ac0921_001
A:\magireco_corrected_research_20260612\validation_outputs_v18_generic_strategy_sample_20260626\ac4901_025
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac4901_full
A:\magireco_corrected_research_20260612\validation_outputs_v18_clean_story_ac7204_character_subset
D:\MagiReco_Reverse\magireco_material_collections_v18_audible_20260626\ac7204
```

Reasons:

- missing or unreliable BGM/bed;
- role voices/subtitles not matching mouth movement;
- many 2 s near-identical clips were generated as if they were meaningful final
  outputs;
- `ac7204` with role voice is not pure material;
- contact sheets cannot reveal audio/subtitle correctness.

The invalidation registry is:

```text
tools/frida_runtime_probe/invalidated_output_roots.json
```

Any strategy/coverage/audit script should read it.  The files stay on disk for
audit history but are not completion evidence.

## Mechanism model: what is now known

The game is not manually classifying every `ac` family the way early recovery
work did.  It uses runtime state and native request paths:

```text
GBoss/event code
  -> scene group / scene id
  -> GDB/Z2D/DGM visual assets and timing
  -> native sound-code/request helpers
  -> SoundMng / CSndMng / CSLMng
  -> CSLAndroidSimpleBufferQueue::Enqueue
  -> OpenSL ES audible queue
```

Important evidence files:

```text
docs/research/2026-06-28-audio-output-mechanism.md
docs/research/2026-06-28-csl-audio-queue-runtime-capture.md
docs/research/2026-06-28-slot-gameplay-audio-state-machine.md
docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md
docs/research/2026-06-27-runtime-av-recapture-report.md
docs/research/2026-06-27-runtime-bgm-gap-report.md
docs/research/2026-06-27-runtime-av-trust-correction.md
```

Critical audio correction:

- earlier `zg::snd::OutputCtrl` probes saw upstream data but the final device
  pointer was null in this MuMu/Gadget state;
- the actually audible one-shot path currently observed is in `libAMAIN.so`:

```text
CSndMng::SndReq(int, int)
  -> CSLMng::SndReq(int, int)
  -> CSLMng::PlayStart(SSound_Data*, int)
  -> CSLAndroidSimpleBufferQueue::Enqueue(void const*, unsigned int)
```

Do not treat `zg::snd::OutputCtrl` capture alone as final mixed audio proof.

Important gameplay-state evidence:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_large_chunk_20260628
```

These prove that a real outer slot-input path triggers high-level BGM helpers
and sound-code mapping that forced single-event playback may not trigger.

Additional 2026-06-28 ac7116 BGM note:

- `visual_tail_probe_ac7116_v3_20260628` saw repeated
  `C_ObjNml::fnSndRequest_BGM_DIR/STG/END` helper calls, but no additional
  concrete BGM/sound-code request for the forced scene beyond the retained
  `42080...` bed and `31186...` role voice.
- `visual_tail_probe_ac7116_v6_after_reinject_20260628` saw one
  `snd_is_already_playing_bgm` hook event plus the same concrete bed/SE/voice
  path, but still did not prove an additional audible BGM stream for this forced
  scene.
- `csl_audio_queue_ac7116_v1_20260628` captured final OpenSL queue chunks for
  the forced official event: request `42080` / sound id `8912`, request `8040`
  / sound id `9544`, and request `31186` / sound id `8008`.  No additional BGM
  request or continuous BGM queue chunk appeared in the forced-event path.
- sound id `8008` is mono in this capture.  The decoder now defaults to
  per-chunk channel inference; older global-stereo timeline WAVs under this
  directory are diagnostic only and understate the final voice duration.
- Therefore those per-frame `C_ObjNml` helper calls are not proof of audible
  BGM.  The remaining BGM gate is specifically an outer-gameplay/full-flow
  question, not a forced-event-only queue question.

2026-07-02 idle slot audio smoke:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_runtime_probe_20260702\slot_idle_runtime_probe_20s.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_csl_queue_probe_20260702\slot_idle_csl_queue_20s.jsonl
```

Both 20 s probes were run from a live slot gameplay screen without forcing an
event.  `runtime_probe.js` produced no non-hook BGM/sound events, and
`csl_audio_queue_probe.js` produced no non-hook play/enqueue events.  This
narrows the BGM problem: the current idle slot screen was not continuously
enqueueing a visible BGM stream during the probe window.  It still does not
settle whether a real transition into `ac7114/ac7115/ac7116` starts or carries
BGM.

## Visual tail/compositor hook candidates

`libGameProc.so` has no normal symbol table, but dynamic exports provide useful
visual hook candidates.  A read-only symbol survey on 2026-06-28 found these
addresses/names:

```text
0x4261e50 Java_util_JniBridge_nscnCalc
0x424791c GLtask_display1()
0x424797c GLtask_display2()
0x42545d8 DirDrawCtrl
0x42545fc DirGetFrame
0x4254558 DirSetFrame
0x4253f38 CDirMngListener::NotifyStartAnim(int, long long, CDirAnim*)
0x4253d58 CSlotBody::NotifyMovieStart(int, long long, CDirCriAnim*)
0x4253d50 CSlotBody::GetRenderTarget(int, long long)
0x4258238 CriManaWrapper::ExecuteVideoProcess()
0x4258284 CriManaWrapper::IsFrameReady()
0x42582c8 CriManaWrapper::GetFrameInfo(int*, int*, int*, int*)
0x42582c0 CriManaWrapper::GetFrameYUVA(unsigned char**, unsigned char**, unsigned char**, unsigned char**, int*, int*, int*)
0x42582d0 CriManaWrapper::CopyFrameYUVA(unsigned char*, unsigned char*, unsigned char*, unsigned char*, int, int, int)
0x424b574 CScreenObjectMng::calcFrameControl()
0x424b578 CScreenObjectMng::draw()
0x424b5c8 CScreenObjectMng::setLockFrame(int)
0x43b4e9c C_DirectionControllerBase::PlayAnimation()
0x43c2098 C_DirectionControllerBase::Macro_CHANGE_ANM(tagDirectionControllerDeviceData, unsigned short)
0x43c21cc C_DirectionControllerBase::Macro_EVENT_PLAY(tagDirectionControllerDeviceData)
```

### 2026-06-28 ac7116 visual-tail probe update

Read the detailed report before changing the renderer:

```text
docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md
```

Runtime capture directories:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v3_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v4_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v5_frame_yuva_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v6_after_reinject_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v8_offset_compositor_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_probe_ac7116_v9_offset_compositor_20260628
```

Current conclusion:

- `ac7116_001` clean main-story tail hold is still not proven native.
- v3 proves official CRI lifecycle/data identity for gold-frame foreground
  layers and the LP foreground switch near 6.66 s.
- v6, after app restart and Gadget reinjection, did observe the main clean story
  payload `ac7116_AT_SP_story5_01.usm` in `CriManaWrapper::SetData`.
- v6 `GetMovieInfo` for the main receiver reported 512x288, 30 fps, 338 frames,
  implying 11.267 s.  Therefore the source identity and native movie duration
  are now runtime-proven.
- v4 active CRI query probing timed out and must not be repeated as-is.
- v5 installed passive frame-extraction metadata hooks but did not reach the
  event because `event_scene_host` found no active `C_AnmBase` scene object; it
  is inconclusive.
- v6 did not fire the downstream frame/compositor hooks needed to prove the
  exact clean/story layer state after frame 338.  The current hold is supported,
  but not yet compositor-proven.
- v8/v9 added module/offset fallback to `visual_tail_probe.js`.  v8 was only a
  tool smoke because global exports were accidentally missed after resolving the
  module as `split_config.arm64_v8a.apk`.  v9 fixed that, restored CRI/audio
  hooks, and installed `GLtask_display1/2` offset hooks, but those visual hooks
  still did not fire in the forced event window.  The actual clean/story
  compositor hot path remains unidentified.

Important v6 `SetData` identities:

| relative time | size | first-4KiB FNV | matched raw CRI |
| ---: | ---: | --- | --- |
| 0.107 s | 1955904 | `1e31c4fa` | `ac7116_AT_SP_story5_01.usm` |
| 0.129 s | 1507616 | `c8fd6fe7` | `AT_SPstory_gold_frame_add.usm` |
| 0.138 s | 2159168 | `72e6f81c` | `AT_SPstory_gold_frame.usm` |
| 6.747 s | 1483776 | `c9cc7d28` | `AT_SPstory_gold_frame_add_LP.usm` |
| 6.759 s | 2157056 | `f32a4a6b` | `AT_SPstory_gold_frame_LP.usm` |

The clean main story raw CRI identity is:

```text
patch_index=1321
size=1955904
first-4KiB FNV=1e31c4fa
name=ac7116_AT_SP_story5_01.usm
```

Do not use the older `main_video_0000_candidates264.mp4` lead as a replacement
without stronger proof.  It is a 416x232 restaurant/table scene and conflicts
with both the official 2026-06-18 runtime DGM string
`[ac7116_AT_SP_story5_01.dgm]` and the v6 direct `SetData` hit for
`ac7116_AT_SP_story5_01.usm`.

Runtime capture recovery notes:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_visual_tail_recovery_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_visual_tail_recovery_after_restart_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\capture_state_visual_tail_after_reinject_20260628
```

The working recovery sequence was: force-stop app, start
`com.universal777.magireco/.SlotMainActivity`, then run `reinject_gadget.py`.
MuMu screenshots are 2160x3840; use physical ADB coordinates.  Useful taps from
this run: `1080 3000` for the title simulation button, then `600 2670` for
`ゲームスタート`.

Full-machine screenrecord diagnostic:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_20260628.mp4
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_contact.jpg
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\ac7116_visual_tail_native_screen_v7_late_tail_frames.jpg
```

This proves the live full-machine presentation enters/holds foreground
slot/title layers after the main story section, but it does not prove the clean
story layer state after those foreground layers are excluded.

Forced-event final audio queue diagnostic:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_runtime_audio_timeline_inferred.json
```

Current ac7116 queue facts:

| Runtime request | Sound id | Queue start | Queue clear / inferred end | Format |
| ---: | ---: | ---: | ---: | --- |
| `42080` | `8912` | 0.066 s | 11.344 s | stereo |
| `8040` | `9544` | 0.070 s | 2.744 s | stereo |
| `31186` | `8008` | 8.879 s | 13.044 s | mono |

`decode_csl_audio_queue_dump.py` now has `--channel-mode infer` by default and
supports `--sound-id-channel SOUND_ID=CHANNELS`.  This matters for role voices:
sound id `8008` is 397838 bytes and cannot be interpreted as 16-bit stereo.

2026-07-02 animation-state sampler follow-up:

```text
docs/research/2026-07-02-ac7116-animation-state-sampler.md
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_state_sampler_ac7116_v10_after_recovery_20260702
```

`event_scene_probe.js` now emits passive `animation_state_sample` records every
about 250 ms while a forced event context is active.  For `ac7116_001`, v10
captured 68 samples through 16.817 s.  The selected source stayed
`C_AnmMain+0x350`, selected object `0x72b06b9bacc0`, frame object
`0x72b06b9bcf40`, and `last_frame_age_ms` remained low during the
11.267-13.027 s voice/subtitle tail.  This proves the live official animation
system is still actively rendering the same story animation object after the
main USM duration.  Combined with v6's 338-frame `GetMovieInfo`, the current
clean `hold_last_frame` behavior is now runtime-supported for
mechanism-validation renders.  It is still not exact clean-layer pixel proof,
so final publication remains gated on compositor/pixel evidence and BGM/full
outer-flow evidence.

v11/v13 numeric follow-up:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v11_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_numeric_sampler_ac7116_v13_default_after_reinject_20260702
```

Both runs found selected-object offset `+0x350` increasing monotonically at
about 30 fps through the 11.267-13.027 s tail.  Treat this as the active
animation object's clock, not as the CRI movie frame index.  A broad pointer
scan was attempted in v12 and caused capture timeout/Gadget reinjection; leave
`includePointerProbe=false` unless the offset list is narrowed first.

v16 CRI receiver follow-up:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702\summary\cri_receiver_summary.json
```

After app restart and Gadget reinjection, `visual_tail_probe.js` captured the
main CRI receiver:

| receiver | FNV | size | movie info | update/status |
| --- | --- | ---: | --- | --- |
| `0x72af8bceec90` | `1e31c4fa` | `1955904` | 512x288, 30 fps, 338 frames | `cri_update` 4-11134 ms; `GetStatus=5` 267-10973 ms |

The same receiver remained numerically sampleable through 20746 ms, while the
higher animation object remained active in v10/v13.  This supports the model:
main CRI reaches the end near the source duration, then the animation/compositor
layer holds its output while the final voice continues.  It still is not a
clean-layer texture/pixel hash after frame 338.

Full ac7114-16 receiver summary:

```text
docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7114_v1_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7115_v1_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_receiver_sampler_ac7116_v16_after_restart_20260702
```

| Event | Main FNV | Movie info | Update/status summary |
| --- | --- | --- | --- |
| `ac7114_001` | `a5b2c906` | 512x288, 30 fps, 275 frames | update 3-8131 ms; `GetStatus=5` 263-9065 ms |
| `ac7115_001` | `4ad69770` | 512x288, 30 fps, 636 frames | update 3-20145 ms; `GetStatus=5` 278-20959 ms |
| `ac7116_001` | `1e31c4fa` | 512x288, 30 fps, 338 frames | update 4-11134 ms; `GetStatus=5` 267-10973 ms |

The `ac7115_001` run also saw `89802b19`, a 512x416, 5277-frame, 33.5 MiB CRI
receiver.  Treat it as slot/gameplay/material state, not a clean story
continuation.

Recommended next visual proof route for the ac7116 tail:

1. Start from a known-good recovered Gadget state; if 27043 times out, restart
   app and reinject Gadget before forcing the event.
2. Hook `CSlotBody::NotifyMovieStart` and `CDirMngListener::NotifyStartAnim` to
   identify which movie/animation object is active.  v6 did not see those calls,
   so a lower-level call site or different hook point may be needed.
3. Passively intercept `CriManaWrapper::GetFrameInfo` / `IsFrameReady` /
   `ExecuteVideoProcess` during the 10-13.5 s window to see whether the movie
   decoder has ended or is still producing frames.  Do not call those CRI
   methods from a Frida `NativeFunction` inside hot hooks.
4. Hook `DirGetFrame` and `CScreenObjectMng::setLockFrame/checkLock/draw` to
   determine whether the game explicitly locks/holds a frame.
5. If those hooks still do not fire, move to throttled GL/texture metadata for
   the 10-13.5 s window.  The goal is to prove the clean/story layer state, not
   to generate a replacement movie from screenrecord.

If the live game locks the final main-story frame while the voice tail plays,
the current hold is acceptable.  If the game switches to another visual layer or
state, the external render must reproduce that instead of holding a still.

## Current important tools

Read these before changing pipeline behavior:

```text
tools/frida_runtime_probe/runtime_probe.js
tools/frida_runtime_probe/event_scene_probe.js
tools/frida_runtime_probe/csl_audio_queue_probe.js
tools/frida_runtime_probe/resolve_official_event_capture.py
tools/frida_runtime_probe/build_event_production_manifests.py
tools/frida_runtime_probe/render_event_batch.py
tools/frida_runtime_probe/qa_event_batch.py
tools/frida_runtime_probe/audit_runtime_av_trust.py
tools/frida_runtime_probe/report_pipeline_strategy.py
tools/frida_runtime_probe/build_scene_editions.py
tools/frida_runtime_probe/build_series_editions.py
tools/frida_runtime_probe/build_material_collection.py
tools/frida_runtime_probe/summarize_runtime_audio_capture.py
tools/frida_runtime_probe/decode_csl_audio_queue_dump.py
tools/frida_runtime_probe/summarize_animation_state_samples.py
tools/frida_runtime_probe/summarize_cri_receiver_samples.py
tools/frida_runtime_probe/package_runtime_evidence_capture.py
tools/frida_runtime_probe/reinject_gadget.py
```

Key distinction:

- `build_series_editions.py` is prefix/family based.  It is valid for a single
  `acXXXX` family when the family is verified.
- `build_scene_editions.py` takes an explicit event sequence and should be used
  for same-scene long videos that span prefixes, such as
  `ac7114_001 + ac7115_001 + ac7116_001`.

## Known good or useful outputs

Earlier user-checked outputs that looked good:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1102_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac1104_family
A:\magireco_corrected_research_20260612\validation_outputs_v15_ac0908_food_sample
A:\magireco_corrected_research_20260612\validated_ac1103_full_v15
```

User spot checks showed files such as `ac1102_006`, `ac1104_014`, and
`ac0908_006` are 416x232, 30/1, 48000 Hz, stereo and visually acceptable.

Do not assume these families are fully final without auditing their long-edition
structure and current AV trust gates.  They are high-priority candidates for
same-scene/family long review collections because the user wants Bilibili-sized
long videos while preserving original segments.

Current v19 ac7114-16 useful-but-not-final output:

```text
A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628
D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628\ac7114_16_sp_story_clean_audio_gate
```

Use these for user visual/audio review and for investigating the tail-hold
question.  Do not present them as final upload-ready outputs yet.

## Reproducibility and GitHub release state

Project kit directory:

```text
reproducibility/project-kit/
```

Evidence release already published:

```text
https://github.com/HiiragiNemu/magireco-slot-asset-pipeline/releases/tag/analysis-evidence-v18.27-20260628
```

Release asset:

```text
magireco-analysis-evidence-v18-20260628-100858.zip
SHA-256: 2D440A240CEF5A2A7F08D0B4FDE6D356A10CAF80655CA5E8370657000AD06797
```

This release is text-only derived evidence.  It intentionally excludes raw
Frida JSONL, WAV, screenshots, videos, APK/OBB/native libraries, and game
payload binaries.

## Commands to reproduce current audits

Run v19 ac7114-16 AV trust audit:

```powershell
python C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\audit_runtime_av_trust.py `
  --production-manifest-root A:\magireco_corrected_research_20260612\production_manifests_v19_clean_audio_gate_20260628 `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v19_clean_audio_gate_tail_hold_20260628 `
  --render-root A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628 `
  --series-root D:\MagiReco_Reverse\magireco_verified_scenes_v19_clean_audio_gate_20260628 `
  --invalidated-output-roots C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\invalidated_output_roots.json
```

Check ac7116 source/render freeze:

```powershell
ffmpeg -hide_banner -nostats `
  -i A:\magireco_bili_fulltest_20260603\cri_official_video_map\official_named_videos\patch\ac7116\ac7116_AT_SP_story5_01.mp4 `
  -vf freezedetect=n=0.003:d=0.5 -an -f null -

ffmpeg -hide_banner -nostats `
  -i A:\magireco_corrected_research_20260612\validation_outputs_v19_clean_audio_gate_ac7114_16_001_20260628\ac7116_001\with_subtitles\ac7116_001__subtitles.mp4 `
  -vf freezedetect=n=0.003:d=0.5 -an -f null -
```

The rendered file reports `freeze_start: 11.2`.  The source check did not show
the equivalent freeze.

Run full v18 AV trust audit with current gates:

```powershell
python C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\audit_runtime_av_trust.py `
  --production-manifest-root A:\magireco_corrected_research_20260612\production_manifests_v18 `
  --out-dir A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628 `
  --invalidated-output-roots C:\Users\cryne\.codex\worktrees\7454\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\tools\frida_runtime_probe\invalidated_output_roots.json
```

Current output:

```text
A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628
```

Summary:

```json
{
  "audited_events": 926,
  "status_counts": {
    "blocked_pending_runtime_av_verification": 897,
    "no_av_trust_flags_detected": 29
  },
  "visual_tail_hold_needs_runtime_confirmation": 29
}
```

Only run broad renders after this audit and a strategy report show that events
are delivery-actionable, not just technically render-ready.

Rebuild strategy queues with the same AV trust CSV:

```powershell
python tools\frida_runtime_probe\report_pipeline_strategy.py `
  --production-catalog A:\magireco_corrected_research_20260612\production_manifests_v18\event_production_catalog.csv `
  --coverage-csv A:\magireco_corrected_research_20260612\coverage_audits_v18_20260626\event_coverage_v18.csv `
  --audience-catalog A:\magireco_corrected_research_20260612\manifests\audience_event_catalog_v1\audience_event_catalog.csv `
  --composition-plans tools\frida_runtime_probe\composition_plans `
  --audience-exclusions tools\frida_runtime_probe\audience_exclusions.json `
  --runtime-av-trust-csv A:\magireco_corrected_research_20260612\runtime_av_trust_audits_v18_tail_hold_gate_20260628\runtime_av_trust_audit.csv `
  --out-dir A:\magireco_corrected_research_20260612\pipeline_strategy_audits_v18_tail_hold_gate_20260628
```

Current strategy result:

```json
{
  "ready_missing_single_event_QA": 217,
  "ready_missing_single_event_QA_delivery_actionable": 4,
  "ready_missing_single_event_QA_av_blocked": 213,
  "visual_tail_hold_needs_runtime_confirmation": 29
}
```

## Immediate next tasks

1. Prove or reject the visual tail-hold for `ac7114_001`, `ac7115_001`, and
   `ac7116_001`.
   - Capture live game screen video or hook the compositor/frame submission
     around the final seconds.
   - The key question is whether clean main-story output should hold the final
     frame while voice continues, or whether another visual layer/state should
     be shown.
   - Until proven, keep the v19 long scene as review-only.

2. Prove whether the ac7114-16 scene has additional BGM.
   - Do not remove `420xx_SPストーリー...`; it is current bed/base-scene audio.
   - Capture the outer state and `CSLAndroidSimpleBufferQueue::Enqueue` queue
     while the scene is reached normally if possible.
   - Use high-level BGM hooks in `runtime_probe.js` in the same run.

3. Generalize the mechanism instead of manually processing every `ac` family.
   - Use runtime event-code dispatch, GDB/Z2D/DGM timing, sound-code/request
     resolution, and final queue evidence.
   - The target is a pipeline that can decide: normal story animation, same
     scene continuation, gameplay/material, foreground-only, or blocked pending
     evidence.

4. Re-audit known-good v15 families for long-edition delivery.
   - `ac1102`, `ac1103`, `ac1104`, and food/restaurant samples are likely
     high-value because the user already found them acceptable.
   - Keep original per-event files.
   - Build same-scene/family long versions only after current AV trust gates
     pass.

5. Keep material collections separate.
   - Small Kyubey / black-screen / CHANCE / PUSH / reel / gold-frame / particle
     effects can be combined into material videos.
   - If role voice appears, it is not pure material and must be handled as
     animation or gameplay-with-role-voice, not silently thrown into a material
     collection.

6. Preserve auditability.
   - Every new output needs manifest, source hash, event index, cumulative
     timeline, subtitle source, audio source, and QA report.
   - Broad batch work should begin with dry-run or small-batch validation.

## Acceptance gates for final Bilibili-facing output

An output is not final until all are true:

- source events are explicitly selected and documented;
- clean story excludes slot foreground/gold-frame/particle layers unless the
  user explicitly wants a gameplay/material collection;
- role voices and subtitles align with game runtime evidence;
- BGM/bed/SE presence is proven or explicitly proven absent by runtime
  evidence;
- visual tail-hold is runtime-confirmed when render duration exceeds native
  video duration by a visible amount;
- subtitle and no-subtitle editions have identical audio;
- native resolution and frame rate are preserved;
- no upscale, no accidental 1080p workflow;
- scene/family long videos include cumulative timeline and source hashes;
- the user can inspect a small validation sample before broad promotion.

## Practical warning for the next AI

The most expensive mistake so far was treating technically valid renders and
contact sheets as if they proved audiovisual correctness.  They do not.  A
short clip with a playable H.264/AAC stream can still have wrong BGM, wrong
voice timing, wrong subtitles, or wrong visual state.

Continue from runtime evidence first, then render.  If a render looks good but
the manifest cannot explain every voice, subtitle, bed/BGM, SE, visual layer,
and tail extension, keep it out of final delivery.
