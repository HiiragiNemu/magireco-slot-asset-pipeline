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
```

Observed queue data:

| Runtime request | Sound id | Start | Duration | PCM bytes |
| ---: | ---: | ---: | ---: | ---: |
| `2990` | `6893` | 0.000 s | 1.767 s | 339188 |
| `30031` | `6930` | 2.526 s | 3.370 s | 646964 |
| `30032` | `6931` | 9.660 s | 3.237 s | 621448 |
| `30077` | `6976` | 16.425 s | 1.637 s | 314382 |
| `30078` | `6977` | 20.291 s | 1.224 s | 235102 |

The timeline render is 21.515 s.  It contains only these discrete one-shot
buffers, not continuous BGM.

### `ac0921_001`, official event request with `--with-sound`

Capture:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628
```

Timeline WAV for listening verification:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628\ac0921_001_with_sound_runtime_audio_timeline.wav
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
| `30077` | `6976` | 16.407 s | 1.637 s | 314382 |
| `30078` | `6977` | 20.274 s | 1.224 s | 235102 |

Conclusion: for `ac0921_001`, manually adding official event sound only
duplicates the lever SE request and does not recover any BGM.

## Current interpretation

Evidence now supports these points:

- the game does not need per-`ac` manual visual matching for voice timing; it
  already emits an authoritative runtime request timeline;
- the correct low-level capture point for these audible one-shot sounds is
  `CSLAndroidSimpleBufferQueue::Enqueue`, not `zg::snd::OutputCtrl`;
- `ac0921_001` single-event forcing produces lever SE plus four Iroha voice
  requests, but no BGM request or continuous BGM buffer;
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
