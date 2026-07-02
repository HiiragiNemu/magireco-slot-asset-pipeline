# libAMAIN CSLSound/OpenSL runtime audio queue capture

Date: 2026-06-28

This note records the first successful capture from the game's actual
`libAMAIN.so` sound playback queue.  It supersedes the earlier assumption that
`zg::snd::OutputCtrl` is the final audible path in the current MuMu route.

## Why this matters

The failed `ac0921_001` repair render had two separate defects:

- no continuous BGM/bed audio;
- the rendered audio ended before the visual event tail.

The earlier `zg::snd::OutputCtrl` probe showed non-zero upstream `TransBuf`
data, but runtime `OutputCtrl + 0x10` was always a null device pointer.  Static
and runtime evidence now show that the audible one-shot voice/SE path used by
this game route is `libAMAIN.so`:

```text
CSndMng::SndReq(int, int)
  -> CSLMng::SndReq(int, int)
  -> CSLMng::PlayStart(SSound_Data*, int)
  -> CSLAndroidSimpleBufferQueue::Enqueue(void const*, unsigned int)
  -> OpenSL ES buffer queue
```

Therefore future render audio must be derived from this runtime request/queue
timeline, or from a proven equivalent decoded request table.  It must not be
matched visually or by `ac` suffix numbers.

## Repository tools

New tools:

```text
tools/frida_runtime_probe/csl_audio_queue_probe.js
tools/frida_runtime_probe/decode_csl_audio_queue_dump.py
```

The probe hooks:

- `CSndMng::SndReq(int, int)`;
- `CSLMng::SndReq(int, int)`;
- `CSLMng::PlayStart(SSound_Data*, int)`;
- `CSLAndroidSimpleBufferQueue::Enqueue(void const*, unsigned int)`;
- selected clear/callback/create helpers when symbols are present.

The decoder can emit:

- `concat` WAV: raw queue chunks back-to-back;
- `timeline` WAV: chunks placed at runtime `unix_ms` offsets and mixed with
  saturating 16-bit PCM arithmetic.

## Runtime captures

Base directory:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627
```

### `ac0921_001`, official event request without explicit event sound

Capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_post_slot_v2_20260628
```

Timeline WAV for listening verification:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_post_slot_v2_20260628\ac0921_001_runtime_audio_timeline.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_post_slot_v2_20260628\ac0921_001_runtime_audio_timeline_inferred.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_post_slot_v2_20260628\ac0921_001_runtime_audio_timeline_inferred.json
```

Observed queue data:

| Runtime request | Sound id | Start | Duration | PCM bytes |
| ---: | ---: | ---: | ---: | ---: |
| `2990` | `6893` | 0.000 s | 1.767 s | 339188 |
| `30031` | `6930` | 2.526 s | 3.370 s | 646964 |
| `30032` | `6931` | 9.660 s | 3.237 s | 621448 |
| `30077` | `6976` | 16.425 s | 3.275 s | 314382 |
| `30078` | `6977` | 20.291 s | 2.449 s | 235102 |

The original global-stereo timeline render is 21.515 s and is now considered a
legacy diagnostic.  The corrected per-chunk inferred timeline is 22.740 s,
reports `observed_source_channels=[1, 2]`, and contains only these discrete
one-shot buffers, not continuous BGM.

### `ac0921_001`, official event request with `--with-sound`

Capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628
```

Timeline WAV for listening verification:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628\ac0921_001_with_sound_runtime_audio_timeline.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628\ac0921_001_with_sound_runtime_audio_timeline_inferred.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628\ac0921_001_with_sound_runtime_audio_timeline_inferred.json
```

The event host confirmed that `with_sound=true` sent the official event sound
request:

```text
forced_event_sound_request_sent
event sound_count=2
```

However the actual `CSndMng` calls were:

```text
2990, 2990, 30031, 30032, 30077, 30078
```

The duplicate `2990` did not produce an extra `PlayStart`/queue buffer.  The
actual OpenSL queue output remained the same five chunks:

| Runtime request | Sound id | Start | Duration | PCM bytes |
| ---: | ---: | ---: | ---: | ---: |
| `2990` | `6893` | 0.000 s | 1.767 s | 339188 |
| `30031` | `6930` | 2.507 s | 3.370 s | 646964 |
| `30032` | `6931` | 9.641 s | 3.237 s | 621448 |
| `30077` | `6976` | 16.407 s | 3.275 s | 314382 |
| `30078` | `6977` | 20.274 s | 2.449 s | 235102 |

Conclusion: for `ac0921_001`, manually adding official event sound only
duplicates the lever SE request and does not recover any BGM.

The corrected per-chunk inferred with-sound timeline is 22.723 s and also
reports `observed_source_channels=[1, 2]`.  The duplicate `2990` still does not
produce an extra queue chunk.

### `ac7116_001`, official event request

Capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628
```

Runtime log:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1__runtime.jsonl
```

Diagnostic output files:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_runtime_audio_timeline.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_runtime_audio_timeline.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_runtime_audio_timeline_inferred.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_runtime_audio_timeline_inferred.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_sound_id_8008_voice_mono.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac7116_v1_20260628\ac7116_001_csl_audio_v1_sound_id_8008_voice_mono.json
```

Observed `CSndMng` requests and queue chunks:

| Runtime request | Sound id | Queue start | Queue clear / inferred end | Format inference | PCM bytes |
| ---: | ---: | ---: | ---: | --- | ---: |
| `42080` | `8912` | 0.066 s | 11.344 s | 48 kHz stereo PCM | 2163204 |
| `8040` | `9544` | 0.070 s | 2.744 s | 48 kHz stereo PCM | 500736 |
| `31186` | `8008` | 8.879 s | 13.044 s | 48 kHz mono PCM | 397838 |

Important decoder correction: the first ac7116 timeline WAV was generated with
a single global stereo interpretation, which made final voice sound id `8008`
appear to last only about 2.072 s.  This was wrong: its chunk is 397838 bytes,
not divisible by a 16-bit stereo frame, and is therefore mono in this capture.

`decode_csl_audio_queue_dump.py` now defaults to `--channel-mode infer`:

- chunks that fit the requested output channel frame keep the output channel
  count, currently stereo by default;
- 16-bit chunks that cannot form full stereo frames are treated as mono;
- mono chunks are duplicated into the stereo diagnostic WAV so the output WAV
  remains playable as a single stream;
- explicit overrides are available with `--sound-id-channel SOUND_ID=CHANNELS`.

The inferred ac7116 timeline metadata reports:

```text
duration_seconds=12.957145833333334
observed_source_channels=[1, 2]
mixed_source_channels=true
sound_id 8008 source_channels=1 source_duration_seconds=4.144145833333333
```

This matches the queue timing: `31186` starts at about 8.879 s and its queue is
cleared near 13.044 s.

Within the forced official event path, no additional BGM request or continuous
BGM queue chunk was observed beyond `42080` bed/base audio, the excluded
foreground SE `8040`, and final role voice `31186`.  This is stronger than a
manifest-only `bgm_request_count=0`, but still does not prove that an outer
gameplay state could not add BGM in a non-forced full-flow capture.

### 2026-07-03 combined CSL+BGM probe update

`csl_audio_queue_probe.js` now also installs high-level `libGameProc.so`
sound-code/BGM hooks in the same run as the final
`CSLAndroidSimpleBufferQueue::Enqueue` hook.  This is still metadata-first:
high-level calls are capped per kind and queue PCM dumping keeps the existing
bounded CSL limits.

The relevant tool changes are:

```text
tools/frida_runtime_probe/csl_audio_queue_probe.js
tools/frida_runtime_probe/summarize_runtime_audio_capture.py
```

Forced ac7116 capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703\summary_v2\summary.json
```

The same JSONL was summarized as both runtime high-level evidence and CSL final
queue evidence.  Counts:

| Evidence class | Count / value |
| --- | --- |
| successful hooks | 38 |
| hook missing | 1 queue callback-register symbol; `Enqueue` hook installed |
| hook attach error | 1, `SndIsAlreadyPlayingBGM`; `SoundMng_isAlreadyPlayingBGM` and later hooks installed |
| high-level sound-code rows | 13 |
| BGM helper rows | 0 |
| `SoundMng::sndPlayReq` rows | 3 |
| final queue chunks | 3 |
| observed sound ids | `8912`, `9544`, `8008` |

The sound-code chain is:

| Time | Kind | Code |
| ---: | --- | --- |
| 3.082 s | `snd_req_by_sound_cd` / `sound_mng_play_by_sound_cd` / `sound_mng_play_bytes` | `42080_SPストーリー5_みふゆとももこ_01` |
| 3.084-3.085 s | `snd_req_by_sound_cd` / `sound_mng_play_by_sound_cd` / `sound_mng_play_bytes` | `8040_シネスコ変化音_金帯 ` |
| 11.902-11.905 s | callback / sequence / `zg_snd_req_code` / SoundMng path | `31186_282_mihu_く…ぐ…` |

The final OpenSL queue chain is:

| Time | Sound id | Bytes | Play index |
| ---: | ---: | ---: | ---: |
| 3.131 s | `8912` | 2163204 | 3 |
| 3.145 s | `9544` | 500736 | 21 |
| 11.928 s | `8008` | 397838 | 8 |

Interpretation: in the forced `ac7116_001` official event path, the retained
`42080...` bed/base-scene audio, foreground SE `8040...`, and voice
`31186...` are the only observed high-level sound-code requests that reach the
final OpenSL queue.  No BGM helper call and no additional continuous queue
chunk appeared in this run.

Current live slot-state smoke with the same combined probe:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703\summary\summary.json
```

For this 20 s passive window, the probe installed the same 38 hooks and observed
no high-level sound request, no BGM helper row, and no final OpenSL queue chunk.
This is only negative evidence for the current screen/state.  It still does not
prove that a natural gameplay transition into `ac7114/ac7115/ac7116` lacks
outer-flow BGM.

## Current interpretation

Evidence now supports these points:

- the game does not need per-`ac` manual visual matching for voice timing; it
  already emits an authoritative runtime request timeline;
- the correct low-level capture point for these audible one-shot sounds is
  `CSLAndroidSimpleBufferQueue::Enqueue`, not `zg::snd::OutputCtrl`;
- `ac0921_001` single-event forcing produces lever SE plus four Iroha voice
  requests, but no BGM request or continuous BGM buffer;
- `ac7116_001` single-event forcing produces only the scene bed/base audio,
  excluded foreground SE, and final role voice in the final queue; its final
  role voice is mono while the bed/SE chunks are stereo;
- the earlier repair render failed because it did not preserve this runtime
  timing and because it tried to treat incomplete audio evidence as delivery
  audio.

## Delivery decision

Do not generate or promote Bilibili-facing `ac0921_001` output from this capture
yet.  The generated WAV files are diagnostic listening artifacts only.  They
prove the official one-shot audio timeline, but they still do not prove complete
scene bed/BGM for a final upload.

## Next required cracking work

1. Capture the outer gameplay transition that enters the `ac0921` preview
   state, not only the forced GBoss event.  The missing BGM may be owned by an
   outer scene/state object rather than the event itself.
2. Hook high-level BGM request symbols in the same run as the OpenSL queue:
   - `C_DirectionControllerBase::Macro_SND_BGM_PLAY`;
   - `C_ObjSelectBNS::fnSndRequestBGM`;
   - `SoundMng_isAlreadyPlayingBGM`;
   - `SndIsAlreadyPlayingBGM`;
   - `zgSndReqCode`, `zgSndReqHashCode`, `zgSndReqId`;
   - `C_CtrlSndLib::fnReqSndEventCode` and `fnReqSndSoundCode`.
3. If no BGM request appears in the outer flow, classify `ac0921_001` as a
   no-BGM official scene and only require correct one-shot SE/voice timing.
4. If BGM appears in the outer flow, derive a general rule from runtime request
   timeline + queue PCM, then update production manifests and QA gates before
   any new render.
