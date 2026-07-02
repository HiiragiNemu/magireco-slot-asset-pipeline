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

### Outer slot gameplay state-machine capture

A later real slot-input capture confirmed why forced single-event playback is
not enough.  With the emulator already in the slot main screen, a minimal
lever/stop-button input sequence triggered the outer gameplay state machine and
produced non-empty final OpenSL queue output:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628
```

Detailed report:

```text
docs/research/2026-06-28-slot-gameplay-audio-state-machine.md
```

Key evidence:

- the runtime resolved event codes to `ac0001_001`, `ac9902_001`,
  `ac9010_060`, `ac9071_001`, `ac9100_001`, `ac9903_001`,
  `ac9920_001`, `ac9071_002`, `ac0910_001`, and `ac0910_002`;
- real gameplay called `C_ObjNml::fnSndRequest_BGM_*` repeatedly and fired
  `C_DirectionControllerBase::Macro_SND_BGM_PLAY`, unlike the forced
  `ac0921_001` single-event path;
- `zgSndReqCode -> RequestCtrl::codeName2ReqId -> SoundMng` resolved string
  codes `301/302/303/304/305/814/295/271`;
- final `CSLAndroidSimpleBufferQueue::Enqueue` capture produced 15 dumped
  chunks, 48 kHz stereo, about 15.48 seconds, with observed sound ids
  `60/61/62/6758/6759/9002`;
- one large code `814` / sound id `287` chunk was metadata-only because it
  exceeded the per-chunk dump cap, so it needs a focused recapture before use
  as final audio evidence.

The follow-up capture raised the CSL per-chunk dump cap from 2 MiB to 8 MiB
while keeping the total cap at 96 MiB.  That run entered a different random
gameplay branch (`ac0908/ac0909`) and captured 25 complete OpenSL queue chunks,
about 19.86 seconds, with no metadata-only chunks.  It proves the larger cap is
safe for focused diagnostics, but it did not reproduce the earlier `814` /
sound id `287` branch.

A subsequent targeted slot-input recapture did reproduce that branch.  It
captured 47 complete OpenSL queue chunks, about 41.40 seconds, with no
metadata-only chunks.  The `814` sound-code lookup occurred during the
`ac0910_001` active event window and mapped to request table id `344` /
`213B22458D11890FF6BEEC183F22.smz`; the final queue row had sound id `287`,
3,072,004 bytes, and static `sound_id.dat` mapping
`snd_00814_bank01_ogg_00287.ogg`.

This changes the general strategy: the recovery pipeline must derive manifests
from runtime event-code dispatch plus sound-code/request timelines and final
OpenSL/game-decoder evidence.  It must not continue classifying every `ac`
family manually or promoting outputs from visual contact sheets.

### Game WAV conversion export status

`zgSndCaptureConvertWav` and `zgSndCaptureConvertWavByHashCode` do exist in the
ARM64 runtime, but the loaded module name is `split_config.arm64_v8a.apk`, not
`libGameProc.so`.  `tools/frida_smz_wav_probe.py` now searches all loaded
modules for these exports.

Direct conversion attempts for code `814` and raw media
`213B22458D11890FF6BEEC183F22.smz` returned `0` and produced no WAV.  Static
disassembly shows the exports require the zgsnd `SndSystem` global constructed
by `zgSndWinDllConstruction` / initialized by `zgSndInit`.  The current MuMu
runtime's audible path is `libAMAIN.so` `CSLSound` / OpenSL, so direct zgsnd
conversion remains a separate cracking route and is not yet a replacement for
OpenSL queue capture.

## Repository tools added

These probes are diagnostic tools only.  They do not generate delivery video:

```text
tools/frida_runtime_probe/audio_output_buffer_probe.js
tools/frida_runtime_probe/decode_audio_output_buffer_dump.py
tools/frida_runtime_probe/sound_device_state_probe.js
tools/frida_runtime_probe/csl_audio_queue_probe.js
tools/frida_runtime_probe/decode_csl_audio_queue_dump.py
tools/frida_runtime_probe/summarize_runtime_audio_capture.py
tools/frida_runtime_probe/build_runtime_evidence_skeleton.py
tools/frida_runtime_probe/package_runtime_evidence_capture.py
tools/frida_runtime_probe/audit_runtime_evidence_packages.py
tools/frida_runtime_probe/build_runtime_evidence_promotion_queue.py
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
- `summarize_runtime_audio_capture.py`: reduce `runtime_probe.jsonl` and
  `csl_audio_queue.jsonl` into CSV/JSON tables for event codes, DGM strings,
  sound-code lookups, play requests, BGM calls, and OpenSL queue chunks.  This
  is the bridge toward a manifest skeleton generator and keeps the next work
  evidence-first instead of screenshot/contact-sheet-first.
- `build_runtime_evidence_skeleton.py`: join those summary tables to static
  event/audio/request/sound-id manifests and emit evidence-only skeleton tables.
  Its output is intentionally marked `evidence_only_not_render_ready`; it is the
  auditable input for a future production-manifest builder, not a delivery
  approval.
- `package_runtime_evidence_capture.py`: run decode + summary + skeleton in one
  reproducible package step and write `source_hashes.csv`,
  `cumulative_runtime_timeline.csv`, `qa_report.json`, and
  `package_manifest.json`.  Its passing state is
  `passed_evidence_not_delivery`; a capture with metadata-only queue chunks is
  rejected as `failed_evidence_package`.
- `audit_runtime_evidence_packages.py`: scan a research root for
  `evidence_package_v*/qa_report.json` and produce a status index CSV/JSON.
  This makes the pass/fail state machine-readable across captures, so broad
  work can use package status instead of conversation memory.
- `build_runtime_evidence_promotion_queue.py`: convert package status into a
  conservative promotion/isolation queue.  Failed packages are blocked; passed
  packages containing slot/gameplay markers or dialogue audio are isolated as
  material/gameplay candidates and explicitly marked not clean-story eligible.
- `report_pipeline_strategy.py`: now accepts
  `--runtime-evidence-promotion-csv` and copies package-level runtime evidence
  gates into the global strategy report.  This makes runtime evidence status
  visible next to v18 production/coverage/AV-trust queues without promoting any
  package to delivery.

## 2026-07-02 slot idle audio smoke

After recovering MuMu/Gadget from the v12 animation pointer-scan timeout, the
game was left on the real slot gameplay screen and two passive 20 s probes were
run without forcing an event:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_runtime_probe_20260702\slot_idle_runtime_probe_20s.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_idle_csl_queue_probe_20260702\slot_idle_csl_queue_20s.jsonl
```

Results:

| Probe | Counts | Non-hook examples |
| --- | --- | ---: |
| `runtime_probe.js` | 40 `hook_installed`, 1 `host_attached`, 1 `probe_start`, 1 `hook_attach_failed` | 0 |
| `csl_audio_queue_probe.js` | 9 `hook_installed`, 1 `host_attached`, 1 `probe_start`, 1 `hook_missing` | 0 |

Interpretation: in this idle slot state there was no new high-level sound/BGM
request and no observed final OpenSL queue activity during the 20 s windows.
This is useful negative evidence for the idle state only.  It does not prove
that an outer gameplay transition into a story event lacks BGM; the full
trigger flow still has to be captured.

## 2026-07-03 combined CSL+BGM probe

`csl_audio_queue_probe.js` now combines the final `libAMAIN.so`
`CSLAndroidSimpleBufferQueue::Enqueue` hook with high-level `libGameProc.so`
sound-code and BGM request hooks in the same Frida script.  One failed high
level attach no longer aborts later hook installation.  This matters because a
single capture can now answer both questions:

- what high-level sound/BGM requests were made;
- which requests actually reached the final OpenSL queue.

Validation captures:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\csl_bgm_combined_ac7116_v3_20260703
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_current_csl_bgm_combined_v2_20260703
```

Forced `ac7116_001` summary:

| Field | Value |
| --- | --- |
| successful hooks | 38 |
| BGM helper rows | 0 |
| high-level sound-code rows | 13 |
| `SoundMng::sndPlayReq` rows | 3 |
| final OpenSL queue chunks | 3 |
| observed sound ids | `8912`, `9544`, `8008` |

The high-level sound-code rows resolve to exactly the same three audible items
already seen in the older CSL-only capture:

- `42080_SPストーリー5_みふゆとももこ_01`;
- `8040_シネスコ変化音_金帯 `;
- `31186_282_mihu_く…ぐ…`.

The passive current-state 20 s probe installed the same hook set and observed
no non-hook sound request, no BGM helper row, and no final OpenSL queue chunk.

Interpretation: the forced ac7116 path now has same-run high-level sound-code
and final queue evidence showing no extra BGM.  This still leaves the same
delivery gate: a natural outer gameplay transition into the scene has not yet
been captured, so an outer-flow BGM cannot be globally ruled out.

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
