# Runtime BGM gap and game-mix strategy

Date: 2026-06-27

This note records the user review failure of the first `ac0921_001` runtime
repair sample and the current evidence about how the game schedules audio.

## User-reviewed failure

The following sample is not valid delivery output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\with_subtitles\ac0921_001__subtitles.mp4
```

User review found:

- no BGM for the whole video;
- no voice after about 23 seconds;
- subtitle/voice correctness cannot be accepted from the current evidence.

Therefore `runtime_repair_v1_ac0921` is demoted to failed diagnostic evidence.
It must not be promoted to clean-story/Bilibili output, and the old v18
technical QA/contact-sheet result is not sufficient delivery evidence.

## What the repaired capture actually proves

The long-window official event capture for `ac0921_001` proves only this single
event timeline:

- 3 DGM/video loads;
- 1 lever SE: `2990_次回予告_レバー`;
- 4 Iroha voice OGG plays:
  - `30031_037_iro_私どうして忘れちゃ`
  - `30032_075_iro_上手く言えないけど`
  - `30077_444_iro_うい、神浜市のどこ`
  - `30078_446_iro_絶対にあなたを見つ`
- 4 subtitle labels derived from the runtime voice labels.

The last voice/subtitle ends at about 22.8 seconds, while the visual timeline is
about 32.8 seconds.  There is no verified BGM/bed-audio track in that manifest.

## `--with-sound` diagnostic result

I fixed `event_scene_probe.js` so `--with-sound` can call
`C_CtrlSndLib::fnReqSndEventCode` even on the official request path.  Then I ran
a single diagnostic capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\official_with_event_sound_smoke_20260627
```

Result:

- `manual_event_sound_requested=true`;
- `actual_play_sounds=6`;
- the extra actual play is another `2990_次回予告_レバー` at event start;
- no BGM was discovered.

Conclusion: manually requesting event sound for this official event duplicates
the lever SE.  It is not a BGM fix and should remain a diagnostic option, not a
production default.

## BGM hook smoke

I added runtime hooks for low-frequency BGM/request-layer functions:

- `zgSndReqCode`
- `zgSndReqFadeCode`
- `zgSndReqVolumeCode`
- `zgSndReqPauseCode`
- `SoundMng_isAlreadyPlayingBGM`
- `C_ObjNml::fnSndRequest_BGM_*`
- `C_DirectionControllerBase::Macro_SND_BGM_PLAY`
- `C_ObjSelectBNS::fnSndRequestBGM`

Smoke output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\runtime_probe_bgm_hook_smoke2_20260627.jsonl
```

`SndIsAlreadyPlayingBGM` cannot currently be attached and is recorded as
`hook_attach_failed`; the other hooks continue to install.

Then I captured `ac0921_001` again with the BGM hooks enabled, without manual
event sound:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\official_bgm_hook_smoke_20260627
```

Observed in the event window:

- lever SE: `2990_次回予告_レバー`;
- 4 voice requests via `ctrl_snd_req_sequence_sc -> zgSndReqCode -> SoundMng`;
- no `C_ObjNml::fnSndRequest_BGM_*` call;
- no `Macro_SND_BGM_PLAY` call;
- no new BGM code string or resolvable BGM OGG.

Conclusion: forcing this single official event does not enter the outer BGM
state machine.  If the real game has BGM here, it is started by a broader
gameplay/story flow before this event, or it is part of an already-playing
global mix.

## Correct strategy from here

The pipeline must stop treating a single event manifest as final AV truth when
there is role voice plus a long tail without verified BGM/bed audio.

Two valid routes remain:

1. External reconstruction with complete runtime evidence:
   - capture the full trigger flow that starts the relevant BGM/state before the
     event;
   - resolve the BGM/SE/voice timeline from runtime logs;
   - render from original DGM/USM at native resolution/codec settings;
   - keep source hashes, event index, cumulative timeline and QA.

2. Direct game-output route:
   - use the game itself to play the full sequence;
   - capture or hook the final mixed audio/video output as truth evidence;
   - if the final upload render still uses extracted DGM/USM, use the captured
     game mix as the timing/audio oracle;
   - if direct game capture quality is used only for verification, it must not
     replace the native-source deliverable without explicit review.

No new Bilibili-facing long video should be generated from `ac0921`, `ac4901`,
or similar role-voice families until one of these routes produces auditable BGM,
voice and subtitle evidence.
