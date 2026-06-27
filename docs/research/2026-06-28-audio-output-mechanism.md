# Audio output mechanism and current BGM blocker

Date: 2026-06-28

This note records the current reverse-engineering state after user review
confirmed that the `ac0921_001` repair sample has no expected BGM/audible scene
sound and loses voice after about 23 seconds.  The conclusion is that the next
work must target the game's own audio-output initialization and full trigger
flow, not more visual matching or manual sound stitching.

## Delivery impact

The following output remains invalid and must not be promoted:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\validation_outputs_runtime_repair_v1_ac0921\ac0921_001\with_subtitles\ac0921_001__subtitles.mp4
```

QA now rejects this file class with:

```text
manifest_audio_tail_gap;tail_digital_silence_after_manifest_audio
manifest_last_audio_end_ms=22777
manifest_audio_tail_gap_ms=9989
tail_max_volume_db=-91.0
```

No Bilibili-facing single-event or long-form output should be generated for
`ac0921`, `ac4901`, `ac7204`, or similar role-voice families until complete
runtime audio evidence exists for BGM/SE/voice/subtitle timing.

## Static mechanism evidence

The authoritative native library in the pulled APK analysis directory is:

```text
C:\Users\cryne\Downloads\MagiaRe\com.universal777.magireco-Ga9DaxEd9F9Lqn9OVKVSfw==\unpacked_lib\lib\arm64-v8a\libGameProc.so
```

Relevant exported symbols:

| Symbol | Address |
| --- | ---: |
| `zg::snd::OutputCtrl::output(bool, zg::snd::TransBuf const&)` | `0x4279200` |
| `zg::snd::OutputCtrl::OutputCtrl()` | `0x4278fe0` |
| `zg::snd::CaptureCtrlImpl::execute(zg::snd::TransBuf const&)` | `0x4264078` |
| `zg::snd::SndSystem::openDevice(int)` | `0x428e154` |
| `zg::snd::SndSystem::updateOutputBuf()` | `0x428da40` |
| `zg::snd::SndSystem::init(TagZGSndConfig const*)` | `0x428dee8` |
| `zgSndOpenDevice` | `0x4272bdc` |

Key static findings:

- `OutputCtrl::OutputCtrl()` stores zero at `[this + 0x10]`.  This field is the
  output-device pointer used later by `OutputCtrl::output`.
- `OutputCtrl::output()` immediately reads `[this + 0x10]` and returns if the
  pointer is null.  Therefore a null device pointer means no final device write
  can occur, even if upstream `TransBuf` data exists.
- The tail of `OutputCtrl::output()` loads the device vtable and branches to the
  function pointer at vtable offset `0x48`.  This is the final device-write
  handoff to hook after a real device object exists.
- `SndSystem::updateOutputBuf()` clears four 0x800-byte output planes at
  offsets `0xd9b0`, `0xe1b0`, `0xe9b0`, and `0xf1b0`, runs
  `PlayerCtrl::execMixing` when something is playing, converts the four
  internal mixing planes to signed 16-bit samples, then calls
  `OutputCtrl::output(system + 0xf78, playing != 0, system + 0xd9b0)`.
- `CaptureCtrlImpl::execute()` copies only the first 0x800 bytes of `TransBuf`
  into its capture buffer and advances by `smpl2Msec(512)`.  It is useful for
  resource/capture conversion research, but it is not by itself proof of final
  scene mix.
- `zgSndOpenDevice()` dispatches through the global `SndSystem` object if that
  object exists.  `SndSystem::openDevice(int)` then calls
  `OutputCtrl::openDevice(int)` on `system + 0xf78`, but
  `OutputCtrl::openDevice(int)` also returns immediately when `[this + 0x10]`
  is null.

## Runtime evidence

The current Gadget route can observe ARM64 game code.  The relevant runtime
evidence for this note is under:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627
```

### TransBuf dump smoke

Probe output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\audio_transbuf_ac0921_numeric_smoke3_20260627
```

Observed:

- `output_entry`: 1327
- `transbuf_chunk`: 15
- `output_enabled_i32`: 1 for dumped chunks
- `device_pointer`: `0x0`

Decoded diagnostics:

| Diagnostic WAV | Chunks | PCM bytes | Duration | Notes |
| --- | ---: | ---: | ---: | --- |
| `transbuf_interleave.wav` | 15 | 122880 | 0.64 s | 48 kHz stereo PCM, saturation ratio 0.172, zero ratio 0.654 |
| `transbuf_fold_listen1.wav` | 15 | 122880 | 0.64 s | 48 kHz stereo PCM, saturation ratio 0.146, zero ratio 0.533 |

This proves that non-zero upstream sound data can exist in `TransBuf`, but these
short, clipped/zero-heavy diagnostics are not final mixed scene audio.

### Device-state probe

Probe output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\sound_device_state_ac0921_numeric_v3_20260628
```

Observed during the 35-second official request window:

- 10 hooks installed successfully:
  - `zgSndOpenDevice`
  - `zgSndCloseDevice`
  - `SndSystem::init`
  - `SndSystem::openDevice`
  - `SndSystem::closeDevice`
  - `OutputCtrl::initDevice`
  - `OutputCtrl::openDevice`
  - `OutputCtrl::closeDevice`
  - `OutputCtrl::isOpened`
  - `OutputCtrl::output`
- no probe errors;
- no actual `zgSndOpenDevice`, `SndSystem::init`, `SndSystem::openDevice`,
  `OutputCtrl::initDevice`, or `OutputCtrl::openDevice` calls observed after
  attach;
- 46 throttled `OutputCtrl::output` samples;
- 23 samples with `output_enabled_i32=1`;
- 23 samples with `output_enabled_i32=0`;
- 46/46 samples had `output_device=0x0`.

Interpretation:

- the output/mix loop is running;
- the forced event can create enabled playback windows;
- the final output-device object is not present in this observed process state;
- attaching only after the app is already running can miss early init/open calls,
  so the next probe must start before or during sound-system initialization.

### Correction: audible one-shot path uses libAMAIN CSLSound/OpenSL

Later 2026-06-28 runtime work confirmed that the currently audible one-shot
voice/SE route does not use `zg::snd::OutputCtrl` as its final device path in
this MuMu/Gadget state.  The successful capture point is:

```text
CSndMng::SndReq(int, int)
  -> CSLMng::SndReq(int, int)
  -> CSLMng::PlayStart(SSound_Data*, int)
  -> CSLAndroidSimpleBufferQueue::Enqueue(void const*, unsigned int)
```

Detailed report:

```text
docs/research/2026-06-28-csl-audio-queue-runtime-capture.md
```

Key `ac0921_001` evidence:

- `--with-sound=false` and `--with-sound=true` were both captured through
  `CSLAndroidSimpleBufferQueue::Enqueue`;
- the explicit `--with-sound` route sent `forced_event_sound_request_sent`, but
  only duplicated request `2990` and did not create extra BGM buffers;
- actual queue output remained five one-shot chunks:
  `2990 -> 6893`, `30031 -> 6930`, `30032 -> 6931`,
  `30077 -> 6976`, `30078 -> 6977`;
- no continuous BGM/OpenSL buffer appeared in the forced single-event window.

Diagnostic listening artifacts:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_post_slot_v2_20260628\ac0921_001_runtime_audio_timeline.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_audio_queue_ac0921_with_sound_v3_20260628\ac0921_001_with_sound_runtime_audio_timeline.wav
```

## Repository tools added

These probes are diagnostic tools only.  They do not generate delivery video:

```text
tools/frida_runtime_probe/audio_output_buffer_probe.js
tools/frida_runtime_probe/decode_audio_output_buffer_dump.py
tools/frida_runtime_probe/sound_device_state_probe.js
tools/frida_runtime_probe/csl_audio_queue_probe.js
tools/frida_runtime_probe/decode_csl_audio_queue_dump.py
```

Use cases:

- `audio_output_buffer_probe.js`: hook `OutputCtrl::output`, dynamically hook a
  real device-write function when a non-null device pointer appears, and fall
  back to bounded `TransBuf` chunk dumping only as mechanism evidence.
- `decode_audio_output_buffer_dump.py`: decode final `output_buffer_chunk`
  payloads directly, or decode bounded `transbuf_chunk` diagnostics with
  explicit `TransBuf` modes.
- `sound_device_state_probe.js`: record sound-system init/open/close/output
  state, including the `OutputCtrl` device pointer at `[this + 0x10]`.
- `csl_audio_queue_probe.js`: hook `libAMAIN.so` `CSndMng`/`CSLMng` requests
  and `CSLAndroidSimpleBufferQueue::Enqueue` to dump the actual OpenSL queue
  chunks with runtime request id and `SSound_Data` sound id evidence.
- `decode_csl_audio_queue_dump.py`: decode queue chunks either as raw concat
  WAV or as a runtime-offset timeline WAV with simple 16-bit PCM mixing.

## Next cracking target

Valid next work is one of these routes:

1. Capture the full gameplay trigger that starts or transitions into the
   relevant scene, not only the forced GBoss single event.  The missing BGM, if
   real, is likely owned by an outer scene/state object.
2. Run the `CSLAndroidSimpleBufferQueue` capture together with high-level BGM
   hooks such as `Macro_SND_BGM_PLAY`, `SoundMng_isAlreadyPlayingBGM`,
   `SndIsAlreadyPlayingBGM`, `zgSndReqCode`, and `C_CtrlSndLib` request helpers.
3. If no BGM request appears in the outer flow either, classify the scene as
   no-BGM official runtime and use the five runtime one-shot requests as the
   authoritative audio timeline.
4. If BGM appears outside the single event, derive a general manifest rule from
   runtime request timeline + OpenSL queue PCM before resuming native-resolution
   rendering and long-form Bilibili assembly.

Until then, any file that merely has an AAC stream, visual contact sheet, or
partial voice/subtitle match remains diagnostic, not deliverable.
