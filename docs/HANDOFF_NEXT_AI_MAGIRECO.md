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
D:\magia\MyProducts\casino
D:\MagiReco_Reverse
```

Space policy:

- A: RAM-disk scratch/current working outputs.  After the 2026-07-03 power loss,
  A: may only contain the restored 2026-06-29 backup plus disposable scratch.
- C: fast P5801X scratch for many small files if A is tight.
- D: repository, durable recovery evidence, final verified long/review
  collections, and the replacement progress root
  `D:\magia\MyProducts\casino` for data that must survive another power loss.

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

2026-07-03 update:

- `csl_audio_queue_probe.js` now combines high-level `libGameProc.so`
  sound-code/BGM hooks with final `libAMAIN.so`
  `CSLAndroidSimpleBufferQueue::Enqueue` hooks in one Frida script.
- `summarize_runtime_audio_capture.py` now understands the combined-probe
  sound-code fields.
- Forced `ac7116_001` same-run capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703\summary_v2\summary.json
```

  Result: 38 hooks installed, one `SndIsAlreadyPlayingBGM` attach error,
  0 BGM helper rows, 13 high-level sound-code rows, and only three final
  OpenSL queue chunks: `42080...` / sound id `8912`, `8040...` / sound id
  `9544`, and `31186...` / sound id `8008`.
- Passive current live slot-state 20 s capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703\summary\summary.json
```

  Result: no sound request, no BGM helper, no OpenSL queue chunk.
- This strengthens the forced ac7116 "no extra BGM" evidence, but it still does
  not prove the natural outer gameplay transition into `ac7114/ac7115/ac7116`
  lacks or carries BGM.  Do not remove the outer-flow BGM gate yet.

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

2026-07-03 selector update:

- `body_force_main` post-clear force kinds `0..19` were validly scanned, but
  none reached `ac7114_001`, `ac7115_001`, `ac7115_013`, or `ac7116_001`.
- Do not extend that scan blindly.  Static analysis now shows the SP Story
  selector chain:

```text
MSTCOMCBK()+0x2378
  -> C_AnmBase::fnDataSetDir_DIR() writes C_AnmBase+0x31a
  -> C_ObjStageAT_SP_Story::pre()/fnSetData() copies +0x31a to +0x34a
  -> C_ObjStageAT_SP_Story::fnSetEventCode() uses +0x34a for event-code setup
```

The writer side is now also identified:

```text
SdGmData+0x788
  -> fnKndCalUsr_SetGR_DirPrmCopy()
  -> MSTCOMCBK()+0x2378
```

`fnKndCalUsr_SetGR_DirPrmCopy` is called through PLT `0x449fec0` from the
KndCal lot state functions including `fnKndCalLot_Start`,
`fnKndCalLot_RlStart`, `fnKndCalLot_Prize`, `fnKndCalLot_Demo`, and related
state handlers.

Important correction from the route-table decoder: the target is not
`SdGmData+0x788 = 3/4/5` and not any number inferred from the `ac` suffix.  The
base SP Story route is selected by a pair:

```text
MSTCOMCBK()+0x2376 -> C_AnmBase+0x318      # stage kind
MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a -> C_ObjStageAT_SP_Story+0x34a
```

Decoded target rows:

| target | required route values |
| --- | --- |
| `ac7114_001` | stage kind `11`, selector `1` or `2` |
| `ac7115_001` | stage kind `12`, selector `1` through `4` |
| `ac7115_013` | stage kind `12`, selector `13` or `14` |
| `ac7116_001` | stage kind `13`, selector `1` or `2` |

Durable decoded output:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\sp_story_event_code_extract_routes_v2_20260703
```

- New durable static evidence root:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_sp_story_selector_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_set_gr_dir_prm_copy_plt_20260703
```

- New runtime evidence hook in
  `tools/frida_runtime_probe/csl_audio_queue_probe.js`:
  `anm_base_data_set_dir_enter` / `anm_base_data_set_dir_leave`.
- New upstream copy hook:
  `gr_dir_prm_copy_enter` / `gr_dir_prm_copy_leave`.
- New summarizer output:

```text
runtime_anm_dir_data.csv
runtime_gr_dir_prm_copy.csv
```

Smoke evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\selector_hook_smoke_v2_20260703
```

The hook installed and emitted 2253 selector rows in a 2 s idle capture without
suppression after raising the selector hook cap to 20000 rows per kind.  Idle
state still showed selector value `0`, so this is only a hook-validation smoke,
not an ac7114-16 route proof.

Upstream-copy calibration:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gr_dir_copy_force_kind8_v1_20260703
```

This non-target force-kind run emitted six `gr_dir_prm_copy_enter/leave` pairs,
but `SdGmData+0x788`, `MSTCOMCBK()+0x2378`, and `C_AnmBase+0x31a` stayed `0`.
It reached ordinary events only, not SP Story.  Therefore the next unknown is
the state/table write that sets both stage kind and selector to one of the
decoded target route pairs above.

Use that CSV with `runtime_sp_story_state.csv`, `runtime_event_codes.csv`,
`runtime_bgm_calls.csv`, and final CSL queue CSVs to identify the real outer
SP Story route.  This is the current highest-value path toward Bilibili-ready
long videos because it attacks the scheduling problem instead of guessing
individual `ac` families.

2026-07-03 later static lead:

- New offset scanner:

```text
tools/frida_runtime_probe/scan_aarch64_memory_offsets.py
```

- Durable static outputs:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_register_index_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_mem_offsets_rx_stage_source_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\static_xref_rxcom_dirinfo_20260703
```

- `MSTCOMCBK()+0x2376` has a decoded read in
  `C_AnmBase::fnDataSetDir_DIR()` but no decoded direct writer.
- `fnKndCalUsr_SetGR_DirPrmCopy()` should not be treated as the stage writer:
  its `str x21, [x0,#0x2370]` comes from zero-extended `ldrh SdGmData+0x786`
  and therefore clears the high bytes containing `MSTCOMCBK()+0x2376`.
- Stronger upstream lead: `fnRxComDirInfo8()` writes payload byte `5` to
  `SdGmData+0x16e` and byte `4` to `SdGmData+0x170`; then
  `fnRxComPreMdl()` copies:

```text
SdGmData+0x16e -> SdGmData+0x0ee -> SdGmData+0x31a
SdGmData+0x170 -> SdGmData+0x0ec -> SdGmData+0x318
```

This is not yet a closed proof that `SdGmData+0x318/0x31a` equals the final
`C_AnmBase+0x318/0x31a` path for SP Story objects, but it is the current best
lead for where the target `(stage kind, selector)` pair enters the runtime
state.

Runtime probe update: `csl_audio_queue_probe.js` now hooks
`fnRxComDirInfo8`, `fnRxComPreMdl`, and `fnLotDirPreMdl`, and
`summarize_runtime_audio_capture.py` writes `runtime_rxcom_dir_flow.csv`.
Live validation:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_hook_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_force_kind8_probe_20260703
```

The hooks installed successfully.  A single kind 8 diagnostic produced
`rxcom_dir_flow_count=10` but remained a non-target ordinary route:
`sp_story_state_count=0`, `fnRxComDirInfo8` payload byte `4` and byte `5` were
both `0`, and all observed RxCom/SdGm stage/selector fields stayed `0`.
`run_force_kind_scan.py` now carries RxCom counts and unique payload/source
stage/selector values in `candidate_summary.json`.

Important evidence files:

```text
docs/research/2026-06-28-audio-output-mechanism.md
docs/research/2026-06-28-csl-audio-queue-runtime-capture.md
docs/research/2026-06-28-slot-gameplay-audio-state-machine.md
docs/research/2026-06-28-ac7116-visual-tail-runtime-probe.md
docs/research/2026-06-27-runtime-av-recapture-report.md
docs/research/2026-06-27-runtime-bgm-gap-report.md
docs/research/2026-06-27-runtime-av-trust-correction.md
docs/research/2026-07-03-sp-story-event-code-and-force-routing.md
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

2026-07-03 same-run CSL+BGM combined probe:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703
```

For forced `ac7116_001`, the same JSONL captured high-level sound-code requests
and final OpenSL queue chunks.  It found exactly three high-level/final audible
items: `42080_SPストーリー5_みふゆとももこ_01`, `8040_シネスコ変化音_金帯 `,
and `31186_282_mihu_く…ぐ…`.  It found 0 BGM helper rows and no additional
continuous queue chunk.  The passive current-state run found no non-hook
request or queue activity.  This is not a natural-trigger capture; keep the
outer-flow BGM gate open.

2026-07-03 follow-up forced CSL+BGM captures:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_ac7114_v1_20260703\summary_v1\summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_ac7115_v1_20260703\summary_v1\summary.json
docs/research/2026-06-28-csl-audio-queue-runtime-capture.md
```

Results:

- `ac7114_001`: 5 `SoundMng::sndPlayReq` rows, 5 final queue chunks, 0 BGM
  helper rows.  Observed sound-code chain:
  `42040_SPストーリー3_01_2G`, `8040_シネスコ変化音_金帯 `, and role voices
  `30949_228_tur_鶴乃ちゃんハ、サイ`,
  `30950_229_iro_嘘ついちゃダメだよ`,
  `30951_230_yac_鶴乃…！`.
- `ac7115_001`: 10 `SoundMng::sndPlayReq` rows, 10 final queue chunks, 0 BGM
  helper rows.  Observed sound-code chain:
  `42060_SPストーリー4_かえでドッペル_01`, `8040_シネスコ変化音_金帯 `, and
  role voices `30746`, `30739`, `30740`, `30741`, `30742`, `30743`, `30744`,
  `30745`.

Interpretation: all three forced official event paths now show no additional
BGM helper row beyond the scene/base audio, gold-band SE, and role voices.  This
does not prove natural outer-flow no-BGM; it only narrows the remaining BGM
work to the natural transition/full-flow path.

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

2026-07-02 renderer texture-state follow-up:

```text
docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md
tools/frida_runtime_probe/runtime_symbol_survey.js
tools/frida_runtime_probe/gl_texture_probe.js
tools/frida_runtime_probe/summarize_gl_texture_probe.py
tools/frida_runtime_probe/cri_video_texture_probe.js
tools/frida_runtime_probe/summarize_cri_video_texture_probe.py
```

Important captures:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gl_texture_probe_ac7116_v5_bind_timeline_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_symbol_survey_renderer_cri_20260702
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v5_combined_after_restart_20260702
```

Findings:

- the original GLES global-export hooks were blind; after hooking all GLES/EGL
  module exports and `eglGetProcAddress`, the game showed 512x288
  `libGLESv1_CM.so` texture allocation/bind/delete only around event start and
  the 6.7 s LP switch;
- no normal GL texture upload/bind/delete/draw/sync/swap was observed in the
  11.267-13.05 s voice tail;
- full-module symbol survey found better renderer candidates in
  `split_config.arm64_v8a.apk`, especially
  `RendererImplGL::checkAndBindTextureStates`;
- the combined after-restart run captured main story `1e31c4fa`/1955904 with
  512x288, 30 fps, 338 frames, and the same renderer/texture-state tuple
  continued in all key windows:

| Window | `sprite_renderer_check_bind_texture_states` count | tuple |
| --- | ---: | --- |
| 9.000-11.000 s | 8 | `0x72b10b97f910` + `0x72af3cccff78` + flag `1` |
| 11.267-13.050 s | 6 | `0x72b10b97f910` + `0x72af3cccff78` + flag `1` |
| 14.000-20.000 s | 23 | `0x72b10b97f910` + `0x72af3cccff78` + flag `1` |

This strengthens ac7116 hold evidence from animation-object/CRI-lifecycle
support to renderer-path support.  It still is not an exact clean-layer
framebuffer or pixel hash.

2026-07-03 narrow TextureStateGL field sampler:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\texture_state_fields_ac7116_v2_after_restart_20260703
```

This run extended `cri_video_texture_probe.js` to sample only numeric
candidates in the first 0x80 bytes of each `TextureStateGL` pointer passed to
`RendererImplGL::checkAndBindTextureStates`.  It again captured the main story
`1e31c4fa`/1955904 payload as 512x288, 30 fps, 338 frames.  Renderer check
counts:

| Window | count |
| --- | ---: |
| 9.000-11.000 s | 22 |
| 11.267-13.050 s | 20 |
| 14.000-20.000 s | 68 |

Three texture-state pointers stayed active through the tail:

| Texture state | total | 9-11 s | 11.267-13.05 s | 14-20 s |
| --- | ---: | ---: | ---: | ---: |
| `0x72af42645f58` | 95 | 7 | 7 | 23 |
| `0x72af42645f78` | 95 | 7 | 7 | 23 |
| `0x72af42646148` | 94 | 8 | 6 | 22 |

Stable tail-window fields included `+0x4=3553`, `+0xc=3`, and
`+0x68=194423728` across the active texture-state records; one state also had
`+0x8=148`, `+0x58=1024`, `+0x60=1` stable.  Treat `+0x4=3553` as consistent
with `GL_TEXTURE_2D`, not as a fully reverse-engineered struct layout.  This is
stronger steady-renderer-state evidence, but it still is not clean-layer
framebuffer/pixel proof.

2026-07-03 renderer drawCall primitive sampler:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary\cri_video_texture_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary\cri_video_texture_events.csv
```

This is the strongest ac7116 hold evidence so far.  v8 was captured after app
restart, Gadget reinjection, and title-flow taps.  It captured the main story
`1e31c4fa`/1955904 as 512x288, 30 fps, 338 frames in the same run as renderer
primitive samples.  Counts:

| Window | `checkAndBindTextureStates` | `drawCall` | `cri_update` / `cri_get_status` |
| --- | ---: | ---: | ---: |
| 9.000-11.000 s | 24 | 24 | 30 / 30 |
| 11.267-13.050 s | 19 | 19 | 20 / 20 |
| 14.000-20.000 s | 69 | 69 | 69 / 69 |

Tail-window primitive groups:

| Primitive | Total | 9-11 s | 11.267-13.05 s | 14-20 s | Texture signature |
| --- | ---: | ---: | ---: | ---: | --- |
| `0x72af405bd370` | 79 | 8 | 6 | 23 | mode `2`, vertices `4`, texture id `155`, `+0xc=29359` |
| `0x72af405bd168` | 75 | 6 | 6 | 23 | mode `2`, vertices `4`, texture id `151`, `+0xc=2606733044` |
| `0x72af405bd148` | 74 | 8 | 6 | 21 | mode `2`, vertices `4`, texture id `150`, `+0xc=29360` |

Fine-window resummary from the same v8 JSONL:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary_fine_windows\cri_video_texture_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703\summary_fine_windows\cri_video_texture_events.csv
```

| Primitive | 0-0.5 s | 0.5-6.6 s | 6.6-7.2 s | 7.2-11.0 s | 11.267-13.05 s | 14-20 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0x72af405bd370` / tex `155` | 1 | 22 | 2 | 14 | 6 | 23 |
| `0x72af405bd168` / tex `151` | 2 | 22 | 1 | 10 | 6 | 23 |
| `0x72af405bd148` / tex `150` | 1 | 20 | 1 | 13 | 6 | 21 |

The safe conclusion is that the game renderer keeps submitting stable
single-texture quad primitives during the final voice/subtitle tail after the
main 338-frame movie boundary.  This supports the current external
`hold_last_frame` behavior as runtime-mechanism-matched.

Caveats:

- v6 primitive capture worked but did not see the main story `1e31c4fa`
  `SetData`; use v8 for same-run identity.
- This is still not a clean-layer framebuffer/pixel hash.  If final release
  policy requires pixel identity, capture a clean-layer texture or framebuffer
  hash next.
- The same run also saw `89802b19`, 512x416, 5277 frames.  Keep treating it as
  slot/gameplay/material state, not clean story continuation.

2026-07-03 visual-tail lock rerun:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\diag_visual_tail_lock_probe_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703\summary_animation\animation_state_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\visual_tail_lock_ac7116_v10_20260703\summary_cri_receiver\cri_receiver_summary.json
```

This reran `visual_tail_probe.js` after `diagnose_runtime_capture_state.py`
reported `runtime_capture_ready_via_arm64_gadget`.  Event and runtime sides
both exited 0.  The animation summary is useful:

| Field | Value |
| --- | --- |
| sample count | 88 |
| first / last forced-event relative sample | 18 ms / 21829 ms |
| selected source | `C_AnmMain+0x350` for all 88 samples |
| selected object | `0x72b06b9870c0` for all 88 samples |
| frame object | `0x72b06b987510` for all 88 samples |
| last-frame age | 17-51 ms, avg 32.65 ms |
| selected object `+0x350` | 4289 -> 4944, 87 increasing steps, 0 decreasing steps |

The frame-lock route itself was negative:

| Hook kind | Calls |
| --- | ---: |
| `dir_get_frame` / `dir_set_frame` / `dir_draw_ctrl` | 0 |
| `notify_movie_start` / `notify_start_anim` | 0 |
| `cri_get_frame_info` / `cri_is_frame_ready` | 0 |
| `screen_object_calc_frame_control` / `screen_object_draw` | 0 |
| `screen_object_set_lock_frame` / `screen_object_check_lock` / `screen_object_is_lock` | 0 |

The hooks installed, so this is negative/inconclusive mechanism evidence, not a
setup failure.  Also, v10 did not recapture main story `1e31c4fa`; it only saw
foreground/gold-frame `SetData` rows (`c8fd6fe7`, `72e6f81c`, `c9cc7d28`,
`f32a4a6b`) plus pre-existing receiver pointers.  Do not use v10 for main-clean
identity.  Use v8 primitive capture for that.

Practical instruction: do not spend another run repeating the same high-level
`DirGetFrame` / `NotifyMovieStart` / `NotifyStartAnim` / `GetFrameInfo` /
`CScreenObjectMng` lock hook set by itself.  The next useful visual proof is
either lower-level compositor/renderer metadata on a path already known to fire,
or direct clean-layer texture/framebuffer hash.

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
2. Read
   `docs/research/2026-07-02-ac7116-renderer-texture-state-probe.md`; do not
   repeat blind `GLtask_display1/2` work.
3. Do not repeat the v10 high-level lock/notification route by itself:
   `DirGetFrame`, `NotifyMovieStart`, `NotifyStartAnim`, `GetFrameInfo`,
   `IsFrameReady`, and `CScreenObjectMng` lock/draw hooks installed but produced
   zero call records.
4. The narrower `TextureStateGL` and primitive sampler route has now been done
   through `texture_state_fields_ac7116_v2_after_restart_20260703` and
   `cri_video_texture_ac7116_v8_primitive_after_restart_taps_20260703`.
   If more visual proof is needed, target a clean-layer texture/pixel hash or a
   compositor/frame-lock state hook.  The goal is clean/story layer state, not
   another full-machine screenrecord.

If the live game locks the final main-story frame while the voice tail plays,
the current hold is acceptable.  If the game switches to another visual layer or
state, the external render must reproduce that instead of holding a still.

### 2026-07-03 Z2D movie-layer proof update

Do not continue spending time on the old high-level frame-lock hook set as the
primary ac7116 visual-tail route.  The useful route is now the Z2D movie-layer
path.

New metadata-only tools:

```text
tools/frida_runtime_probe/z2d_movie_layer_probe.js
tools/frida_runtime_probe/summarize_z2d_movie_layer_probe.py
```

Static symbol survey artifacts:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\renderer_symbol_candidates_20260703.txt
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\animation_direction_symbol_candidates_20260703.txt
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\movie_layer_symbol_candidates_20260703.jsonl
```

Useful v1 capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703\summary_v2\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v1_20260703\summary_v2\z2d_movie_layer_events.csv
```

Key facts for `ac7116_001`:

- The probe found an active Z2D movie object:
  `play_movie_pointer=0x72affba2cae8`,
  `elem_movie_pointer=0x72affba2ca98`.
- That object is 512x288, start/end frame 0/337, and its frame/decode fields
  remain fixed at 337.
- `CZ2DElemMovie::IsDrawTime(337)` returns 1 in the voice tail.
- Its texture-like field is constant `151`, matching renderer primitive
  `0x72af405bd168` / texture id `151`.
- In 11.267-13.05 s, the game continues `ExecPlayMovie`, `GetDecodeFrame`,
  `DecodeMovie`, and `drawCall` for this object/primitive.
- First/last observed times for the correlated object cover roughly -1.48 s to
  25.96 s relative to the forced event start, well past the 13.027 s final voice
  endpoint.

Interpretation: for `ac7116_001`, the current external `hold_last_frame` policy
is now strongly supported by the game's own Z2D movie-layer mechanism.  The
game appears to keep the clean 512x288 movie element drawable at final frame 337
while audio/subtitle tail continues.

v1 caveat: v1 did not recapture the main story `1e31c4fa`
`CriManaWrapper::SetData` in the same run; it only recaptured
foreground/gold-frame CRIs.  That caveat was closed by v2.

Useful v2 same-run closure capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\gadget_reinject_z2d_same_run_closure_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703\summary_v2\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7116_v2_same_run_closure_20260703\summary_v2\z2d_movie_layer_events.csv
```

v2 was captured after force-stop/start, arm64 Gadget reinjection, and the known
title-flow taps.  Event and runtime exit codes were both 0.  It captured both
required facts in one JSONL:

1. main story `ac7116_AT_SP_story5_01.usm` / `1e31c4fa` / 1955904 bytes /
   512x288 / 338 frames at 121 ms; and
2. named Z2D movie object `ac7116_AT_SP_story5_01.dgm`:
   `play_movie_pointer=0x72affb9c0ae8`,
   `elem_movie_pointer=0x72affb9c0a98`, 512x288, start/end frame 0/337,
   texture-like id `153`, renderer primitive `0x72af4e66e168` / texture id
   `153`.

In the 11.267-13.05 s voice/subtitle tail, v2 shows the named clean story object
holding frame 337:

```text
rel_ms=11302 IsDrawTime elem=0x72affb9c0a98 input=337 return=1
rel_ms=11302 GetDecodeFrame elem=0x72affb9c0a98 input=337 return=337
rel_ms=11331 ExecPlayMovie play=0x72affb9c0ae8 +0x4=337 +0x20=153 +0x28=337 +0x38=512 +0x40=288
rel_ms=11331 GetEndTime elem=0x72affb9c0a98 return=337
rel_ms=11331 DecodeMovie play=0x72affb9c0ae8 +0x4=337 +0x20=153 +0x28=337 +0x38=512 +0x40=288
rel_ms=11465 drawCall primitive=0x72af4e66e168
```

The same object is observed through about 25.93 s.  Therefore `ac7116_001`
visual-tail hold is now runtime-mechanism proven: the game itself keeps the
named clean story movie element drawable at final frame 337 while the voice tail
continues.  A framebuffer/texture-byte hash would be stricter pixel proof, but
it is no longer necessary to explain the external render's final-frame hold for
`ac7116_001`.

The same Z2D route was then extended to the other two events in the same scene:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7114_v1_20260703\summary_v1\z2d_movie_layer_summary.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\z2d_movie_layer_ac7115_v1_20260703\summary_v1\z2d_movie_layer_summary.json
docs/research/2026-07-02-ac7114-16-cri-receiver-tail-sampler.md
```

Additional results:

- `ac7114_001`: same run captured main story `a5b2c906` / 1903456 bytes /
  512x288 / 275 frames and named Z2D movie
  `ac7114_AT_SP_story3_01.dgm`; play `0x72affba47728`,
  elem `0x72affba476d8`, end frame 274, texture-like id `165`, renderer
  primitive `0x72af4e66e168` / texture id `165`.  Tail rows show
  `IsDrawTime(274)=1`, `GetDecodeFrame(274)=274`, and continued drawCall.
- `ac7115_001`: same run captured main story `4ad69770` / 3940544 bytes /
  512x288 / 636 frames and named Z2D movie
  `ac7115_AT_SP_story4_01.dgm`; play `0x72affb9d0c28`,
  elem `0x72affb9d0bd8`, end frame 635, texture-like id `197`, renderer
  primitive `0x72af4e66e168` / texture id `197`.  Tail rows show
  `IsDrawTime(635)=1`, `GetDecodeFrame(635)=635`, and continued drawCall.
  The same run also saw small CRIs `7fc38d87` and `400d7791`; they are
  transition/follow-up CRIs and must not replace the named clean story DGM.

Current visual-tail conclusion: the clean story `hold_last_frame` policy for
`ac7114_001 + ac7115_001 + ac7116_001` is now runtime-mechanism proven.  Do not
spend more work on this gate unless a stricter framebuffer/texture-byte hash is
explicitly required.

The separate BGM/outer-flow gate remains open.  Do not mark the Bilibili long
scene final until BGM/bed presence is proven or proven absent.

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
tools/frida_runtime_probe/runtime_symbol_survey.js
tools/frida_runtime_probe/gl_texture_probe.js
tools/frida_runtime_probe/summarize_gl_texture_probe.py
tools/frida_runtime_probe/cri_video_texture_probe.js
tools/frida_runtime_probe/summarize_cri_video_texture_probe.py
tools/frida_runtime_probe/z2d_movie_layer_probe.js
tools/frida_runtime_probe/summarize_z2d_movie_layer_probe.py
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

## 2026-07-03 SP Story / force-routing update

Read this detailed report before continuing the ac7114-16 BGM gate:

```text
docs/research/2026-07-03-sp-story-event-code-and-force-routing.md
```

## 2026-07-03 power-loss recovery note

The RAM disk A: lost the 2026-07-03 transient captures after a power loss.  The
user restored a 2026-06-29 backup to A: and also unpacked the same backup to:

```text
D:\magia\MyProducts\casino
```

Use the repository, GitHub branch, C: worktree, and D: as durable state.  Treat
2026-07-03 A:-only runtime JSONL/screenshots as lost unless the file still
exists after restore.  New durable runtime evidence should go under:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

A: may still be used for disposable high-frequency scratch, but do not make it
the only copy of evidence needed for the handoff, QA, manifests, or Bilibili
delivery decisions.

Correct repository state after recovery:

- branch: `codex/corrected-runtime-pipeline`
- force-kind recovery commits through
  `6af86e8 Add auditable force kind scan` were pushed before the selector
  tracing work.
- The current local diff adds static xref survey support, the
  `C_AnmBase::fnDataSetDir_DIR` runtime hook, `runtime_anm_dir_data.csv`
  summarization, and updated handoff/status notes.

Current facts:

- `C_ObjStageAT_SP_Story::fnSetEvCdBase` statically contains the official
  base event codes for `ac7114_001`, `ac7115_001`, and `ac7116_001`.
- New extractor:
  `tools/frida_runtime_probe/extract_sp_story_event_codes.py`.
- New runtime state table from combined CSL/BGM captures:
  `runtime_sp_story_state.csv`, emitted by
  `tools/frida_runtime_probe/summarize_runtime_audio_capture.py`.
- Natural slot input captures on 2026-07-03 proved ordinary gameplay can call
  BGM helper paths, but the captures reached restaurant/ordinary slot flow, not
  target SP Story.  They do not close the ac7114-16 BGM gate.
- The visible force selector is currently blocked by the add-on purchase gate.
  Do not use the purchase popup path as evidence.
- Internal `CSlotBody` force state can now be written reproducibly:

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-force-main --index <n>
python tools\frida_runtime_probe\force_selector_host.py body-force-sub --index <n>
python tools\frida_runtime_probe\force_selector_host.py body-force-param --index <n>
```

Validated evidence:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\force_body_main_write0_20260703c.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\force_body_main_reset_minus1_20260703c.jsonl
```

Historical note: the next experiment was previously to map `body-force-main`
index `0..19`.  That work is now done via the post-clear diagnostic route and
did not reach ac7114-16.  Do not repeat or extend it blindly.  The recommended
next experiment is now a narrow selector capture using
`anm_base_data_set_dir_enter/leave`, `runtime_anm_dir_data.csv`,
`runtime_sp_story_state.csv`, `runtime_event_codes.csv`,
`runtime_bgm_calls.csv`, `runtime_sound_code_calls.csv`, and final CSL queue
CSVs in the same run.

Additional 2026-07-03 recovery results:

- Gadget recovery after the power loss required:
  - root x86 frida-server on `127.0.0.1:27042`;
  - `reinject_gadget.py`;
  - explicit `adb forward tcp:27043 tcp:27043`.
- Durable evidence root:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence
```

- Natural one-spin baseline after recovery:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_baseline_one_spin_after_recovery_20260703
```

- Naive `body-force-main` before lever is not reliable because early
  `CSlotBody::START` cleanup can clear the field before `fnSetForceFlag`.
- New diagnostic action:

```powershell
python tools\frida_runtime_probe\force_selector_host.py body-force-next-lever --index <kind>
```

It injects the force kind after `ID401::fnClrForceFlag()` and before
`fnSetForceFlag`.  This is for force-kind mapping only; it is not a final
render approval mechanism.
- `force_index0_postclear_chain_20260703` validated the diagnostic route:
  independent observer captured `force_flag_set arg0=0`.
- `force_index8_postclear_probe_20260703` mapped force kind 8 to
  `ac0922_001` (`0x31434e5a38404764`, voices `31043`-`31061`), with no
  `C_ObjStageAT_SP_Story` runtime event.  Later selector-calibration runs with
  kind 8 reached ordinary `ac0101`/`ac0102`/`ac9071`/`ac9920` routes instead.
  Treat kind 8 as a non-target diagnostic route, not a stable ac0922 selector
  and not ac7114-16.
- `run_force_kind_scan.py` now automates clean restart/title-entry/ready-state
  force-kind mapping.  Current MuMu input coordinates are physical `2160x3840`:
  title `シミュレーション` is `1080 3000`, `ゲームスタート` is `600 2670`,
  reel stops are `880/1160/1440 2860`.
- Invalid samples before that coordinate/title-entry fix:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_2_7_9_19_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_kind2_v2_20260703
```

- Valid post-clear scan evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_smoke_kind2_v3_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_kind_scan_3_7_9_19_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\force_index8_postclear_probe_20260703
```

- Conclusion from valid evidence:
  - force kinds `1..7` and `9..19` each emitted real
    `force_flag_set(kind, 0)` but mapped to ordinary slot/gameplay event-code
    groups, with `sp_story_state_count=0`;
  - force kind `8` is non-target; it has produced one `ac0922_001` / Episode
    Bonus run and later ordinary-route calibration runs, but no SP Story target;
  - force kind `0` validated the diagnostic route but did not reach the target;
  - no tested `0..19` kind reached any target code for `ac7114_001`,
    `ac7115_001`, `ac7115_013`, or `ac7116_001`.
- Do not blindly extend the force-kind scan above 19.  Next useful work is
  the SP Story route now identified statically:
  `MSTCOMCBK()+0x2376 -> C_AnmBase+0x318` plus
  `SdGmData+0x788 -> MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a ->
  C_ObjStageAT_SP_Story+0x34a`.  The new `gr_dir_prm_copy_*` and
  `anm_base_data_set_dir_*` runtime events should be used to observe it live.

Additional same-session control update:

- The 27043 ARM64 Gadget can become unstable when two host processes attach at
  the same time.  In current runs, `runtime_probe_host.py` as observer plus a
  second `force_selector_host.py` trigger can fail with
  `frida.TransportError: connection closed` before the trigger is sent.
- `runtime_probe_host.py` now supports loading both scripts in one Gadget
  session:

```powershell
python tools\frida_runtime_probe\runtime_probe_host.py `
  --script tools\frida_runtime_probe\csl_audio_queue_probe.js `
  --control-script tools\frida_runtime_probe\force_selector_probe.js `
  --control-sequence body_bet=1,body_bet=1,body_force_next_lever=8 `
  --out D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\<run>\observer_control_csl.jsonl `
  --duration 30 --quiet --no-unload
```

- `--no-unload` is intentional for fragile Gadget cleanup; the JSONL is closed
  before the forced process exit.
- `csl_audio_queue_probe.js` now captures RxCom/SdGm and BGM helper
  backtraces.  `runtime_bgm_calls.csv` now contains `symbol`, `address`,
  arguments, and backtrace fields.
- Valid recovery evidence:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\gadget_reinject_after_app_restart_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\natural_bgm_backtrace_smoke_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\single_session_force_kind8_control_v1_20260703
```

- `natural_bgm_backtrace_smoke_20260703` only proves the combined probe still
  sees final OpenSL queue chunks after reinjection: sound ids `8993` and
  `8998`.  It had 0 BGM helper rows and is not target SP Story evidence.
- `single_session_force_kind8_control_v1_20260703` proves observer + control
  can share a JSONL in one Gadget session, but the initial control state was
  not ready (`body_state=0`, `body_mode=0`, `body_bet=0`).  It emitted event
  code `0x43454f646b32615a` with `sp_story_state_count=0`,
  `rxcom_dir_flow_count=0`, and `bgm_call_count=0`.  Treat it as a tooling
  proof only.
- Failed evidence to avoid overclaiming:

```text
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\diagnose_gadget_after_transport_closed_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\rxcom_force_kind8_backtrace_v2_20260703
D:\magia\MyProducts\casino\runtime_recovery_20260703\evidence\single_session_force_kind8_control_v2_20260703
```

These document transport/injection failures.  Do not treat them as route
negatives or no-BGM evidence.

## Immediate next tasks

1. Prove whether the ac7114-16 scene has additional BGM.
   - The visual-tail gate for `ac7114_001`, `ac7115_001`, and `ac7116_001` is
     now runtime-mechanism proven by the 2026-07-03 Z2D captures.
   - Do not remove `420xx_SPストーリー...`; it is current bed/base-scene audio.
   - Capture the outer state and `CSLAndroidSimpleBufferQueue::Enqueue` queue
     while the scene is reached through the real SP Story selector if possible.
   - Use high-level BGM hooks in `runtime_probe.js` or the combined CSL+BGM
     probe in the same run.
   - Until BGM/bed presence is proven or proven absent, keep the v19 long scene
     as review-only.

2. Find the real SP Story selector before more force-kind scanning.
   - `body_force_main` kinds `0..19` are now ruled out for ac7114-16.
   - The current static route is
     `MSTCOMCBK()+0x2376 -> C_AnmBase+0x318` plus
     `SdGmData+0x788 -> MSTCOMCBK()+0x2378 -> C_AnmBase+0x31a ->
     C_ObjStageAT_SP_Story+0x34a`.
   - Run the combined CSL/BGM/SP Story probe and inspect
     `runtime_rxcom_dir_flow.csv`, `runtime_gr_dir_prm_copy.csv`, and
     `runtime_anm_dir_data.csv` to observe which stage/selector values
     correspond to the decoded target rows:
     stage `11`/`12`/`13` with selectors `1`/`2`/`3`/`4`/`13`/`14`.

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
