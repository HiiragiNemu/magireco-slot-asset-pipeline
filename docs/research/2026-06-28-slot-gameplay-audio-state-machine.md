# Slot gameplay audio state-machine capture

Date: 2026-06-28

This note records the first useful outer-gameplay capture after user review
showed that forced single-event rendering is not sufficient for trustworthy
Bilibili-facing output.  The practical conclusion is that the game does not
manually classify every `ac` family the way the recovery pipeline had been
doing.  It runs a state machine that requests scenes by GBoss event code and
requests sound through native sound-code/request layers.  Future production
must follow that mechanism instead of visual matching.

## Capture scope

Runtime evidence directory:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628
```

Inputs were sent only after the emulator was visibly in the slot main screen.
The screen before input had medals available; the post-input screenshot shows
real slot gameplay/reel state and a character cut-in, not the title screen.

Important artifacts:

```text
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\runtime_probe.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\csl_audio_queue.jsonl
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\slot_gameplay_runtime_audio_timeline.wav
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\slot_gameplay_runtime_audio_metadata.json
A:\magireco_corrected_research_20260612\runtime_av_repair_20260627\slot_gameplay_input_probe_20260628\slot_gameplay_input_probe.png
```

The timeline WAV is a diagnostic reconstruction from the game's final
`CSLAndroidSimpleBufferQueue::Enqueue` PCM payloads.  It is not an externally
matched OGG/SMZ guess.

## Event-code result

The runtime capture saw these GBoss event codes.  They were then resolved
through `event_scene_host.py inspect-code`, not visual inference:

| Event code | Scene group | Scene | Sound count |
| --- | --- | --- | ---: |
| `0x692d37696d484971` | `ac0001` | `ac0001_001` | 0 |
| `0x4c67596b43665968` | `ac9902` | `ac9902_001` | 0 |
| `0x244e726f36552f73` | `ac9010` | `ac9010_060` | 0 |
| `0x24493723314f4c56` | `ac9071` | `ac9071_001` | 0 |
| `0x46324b7267476b39` | `ac9100` | `ac9100_001` | 0 |
| `0x2f5025663440584b` | `ac9903` | `ac9903_001` | 0 |
| `0x396b436a2a234a73` | `ac9920` | `ac9920_001` | 0 |
| `0x6a457236314f4c56` | `ac9071` | `ac9071_002` | 0 |
| `0x664e476845597a74` | `ac0910` | `ac0910_001` | 1 |
| `0x4776506945597a74` | `ac0910` | `ac0910_002` | 1 |

The visible DGM strings in the same run include:

```text
[ac0001_001_c1_MR.dgm]
[ac0001_001_c2.dgm]
[ac0001_001_c3_MR.dgm]
[ac0001_001_c4.dgm]
[ac0001_001_c5_MR.dgm]
[ac9920_sub_reel_bg.png]
[ac0910_001_MR.dgm]
[ac0910_001_MR_LP.dgm]
[ac0910_002_MR.dgm]
[ac0910_002_MR_LP.dgm]
```

This proves that the outer gameplay state machine can load normal `ac` scenes
and their LP tails through runtime event-code dispatch.  Forced single-event
playback of a leaf event is not equivalent to the game path.

## Sound request result

The real gameplay run triggered high-level BGM/sound helpers that the forced
`ac0921_001` single-event run did not trigger:

- `C_ObjNml::fnSndRequest_BGM_*` was called repeatedly during gameplay;
- `C_DirectionControllerBase::Macro_SND_BGM_PLAY` fired once;
- `C_CtrlSndLib::fnReqSndSoundCode` requested sound codes `814`, `295`, and
  later `271`;
- `zgSndReqCode -> RequestCtrl::codeName2ReqId -> SoundMng` resolved the actual
  string sound codes.

Observed string sound-code resolution:

| Time (s) | Code string | Request table id | Active event |
| ---: | ---: | ---: | --- |
| 4.002 | `301` | 107 | `0x396b436a2a234a73` |
| 4.879 | `302` | 108 | `0x396b436a2a234a73` |
| 4.880 | `303` | 109 | `0x396b436a2a234a73` |
| 5.613 | `304` | 110 | `0x396b436a2a234a73` |
| 7.975 | `304` | 110 | `0x396b436a2a234a73` |
| 8.909 | `304` | 110 | `0x396b436a2a234a73` |
| 8.997 | `305` | 111 | `0x6a457236314f4c56` |
| 9.242 | `301` | 107 | `0x6a457236314f4c56` |
| 9.720 | `302` | 108 | `0x664e476845597a74` |
| 9.724 | `303` | 109 | `0x664e476845597a74` |
| 9.725 | `814` | 344 | `0x664e476845597a74` |
| 9.725 | `295` | 100 | `0x664e476845597a74` |
| 12.015 | `304` | 110 | `0x4776506945597a74` |
| 12.945 | `304` | 110 | `0x4776506945597a74` |
| 13.346 | `304` | 110 | `0x4776506945597a74` |
| 13.347 | `271` | 89 | `0x4776506945597a74` |
| 13.453 | `305` | 111 | `0x6a457236314f4c56` |
| 13.714 | `301` | 107 | `0x6a457236314f4c56` |

Observed `SoundMng::sndPlayReq` / `CSndMng::SndReq` values include:

```text
43200, 302, 303, 304, 305, 814, 2701, 2702
```

The important trap is that these are not one namespace.  For example, runtime
code `301` resolved through `SoundMng` and ultimately requested `CSndMng`
id `43200`, whose final OpenSL sound id was `9002`.  Treating the visible
numeric code as an OGG index or as an `ac` suffix would be wrong.

## Final OpenSL queue result

`decode_csl_audio_queue_dump.py` decoded the final queue capture as:

```json
{
  "chunk_count": 15,
  "source_total_pcm_bytes": 7071584,
  "rendered_total_pcm_bytes": 2972924,
  "sample_rate": 48000,
  "channels": 2,
  "duration_seconds": 15.483979166666666,
  "observed_sound_ids": [60, 61, 62, 6758, 6759, 9002]
}
```

Queue chunks:

| Time (s) | Chunk | Sound id at `SSound_Data+0x2` | Bytes | Play index |
| ---: | ---: | ---: | ---: | ---: |
| 4.030 | 0 | 9002 | 265884 | 12 |
| 4.905 | 1 | 60 | 286788 | 2 |
| 5.636 | 2 | 61 | 386568 | 2 |
| 8.003 | 3 | 61 | 386568 | 2 |
| 8.936 | 4 | 61 | 386568 | 2 |
| 9.014 | 5 | 62 | 373672 | 11 |
| 9.274 | 6 | 9002 | 265884 | 12 |
| 9.757 | 7 | 60 | 286788 | 2 |
| 9.783 | 8 | 6758 | 1871996 | 3 |
| 12.039 | 9 | 61 | 386568 | 2 |
| 12.049 | 10 | 6759 | 761608 | 3 |
| 12.975 | 11 | 61 | 386568 | 2 |
| 13.372 | 12 | 61 | 386568 | 2 |
| 13.472 | 13 | 62 | 373672 | 11 |
| 13.738 | 14 | 9002 | 265884 | 12 |

One additional chunk with sound id `287` and `buffer_bytes=3072004` was recorded
as metadata only because it exceeded the per-chunk dump cap.  That corresponds
to the `814` gameplay sound-code path and should be captured with a larger cap
only in a targeted diagnostic run, not during broad rendering.

## Static table cross-check

The request table and `sound_id.dat` confirm why numeric shortcuts are unsafe:

| Runtime code / request | Request table evidence | Final sound-id evidence |
| --- | --- | --- |
| `301` | code `301` -> request table id `107`, PCM media `12AAE6B60208B6465D97D24E0750.pcm` | runtime `CSndMng` id `43200`, final sound id `9002`, `sound_id.dat` resource `43200` -> `snd_43200_bank12_ogg_09002.ogg` |
| `302` | code `302` -> request id `108`, PCM media `D438622A187AA39537CE691A1B20.pcm` | gameplay one-shot region, final queue near sound id `60` |
| `303` | code `303` -> request id `109`, PCM media `40B69A330CB53BE572ED542B6830.pcm` | gameplay one-shot region, final queue near sound id `60/61` |
| `304` | code `304` -> request id `110`, PCM media `1B2FFF73330976E5EB1184115980.pcm` | repeated final sound id `61` |
| `305` | code `305` -> request id `111`, PCM media `2BB1FD6CCC7187BEA9D225241F90.pcm` | final sound id `62` |
| `814` | code `814` -> request id `344`, SMZ `213B22458D11890FF6BEEC183F22.smz` | `sound_id.dat` resource `814` -> `snd_00814_bank01_ogg_00287.ogg`; large final chunk was capped as metadata |
| `2701` | request id `2701`, label `15459_iro_ひとりぼっち_はっ`, SMZ `4F96B2BA5124CE842AB751305412.smz` | final sound id `6758`, `snd_02701_bank03_ogg_06758.ogg` |
| `2702` | request id `2702`, label `15460_iro_ひとりぼっち_さなちゃんどこにいる-`, SMZ `4A0A85E444D904F48A54BA3C8E62.smz` | final sound id `6759`, `snd_02702_bank03_ogg_06759.ogg` |

The correct generic rule is therefore:

1. resolve runtime event code to official scene/layer plan;
2. record runtime sound-code/request timeline;
3. map request/code through `zg_snd_request_tbl.bin` and `sound_id.dat`;
4. verify final audible output through OpenSL queue capture or a proven official
   game decoder;
5. only then render subtitle/no-subtitle editions and assemble long Bilibili
   parts.

## Game WAV conversion probe status

`zgSndCaptureConvertWav` and `zgSndCaptureConvertWavByHashCode` are exported
from `split_config.arm64_v8a.apk` at runtime, not from a standalone
`libGameProc.so` module name.  `tools/frida_smz_wav_probe.py` was updated to
search all loaded modules instead of hard-coding `libGameProc.so`.

Status probe:

```text
convertByHashExport: split_config.arm64_v8a.apk!zgSndCaptureConvertWavByHashCode
convertRawExport:    split_config.arm64_v8a.apk!zgSndCaptureConvertWav
```

Direct conversion attempts for code `814` and raw media
`213B22458D11890FF6BEEC183F22.smz` returned `0` and produced no WAV.  Static
disassembly explains the failure: these exports require the `zg::snd::SndSystem`
global at the slot used by `zgSndWinDllConstruction` / `zgSndInit`.  The current
MuMu runtime plays audible audio through `libAMAIN.so` `CSLSound` / OpenSL, so
the zgsnd conversion subsystem is not automatically initialized in this state.

Do not treat this as an audio absence.  It only means the direct conversion
route needs more initialization work before it can replace OpenSL capture.

## Delivery impact

No new Bilibili-facing output is authorized from this capture alone.  It is a
mechanism proof and a listening artifact for user verification.

Allowed next actions:

- repeat this capture with a targeted larger per-chunk cap for sound id `287`
  / code `814`;
- add a generic resolver that turns runtime event-code + sound-code logs into a
  machine-readable manifest skeleton;
- continue reversing `zgSndWinDllConstruction -> zgSndInit -> SndSystem::init`
  only as a separate official-decoder route;
- use `slot_gameplay_runtime_audio_timeline.wav` for human listening checks.

Forbidden next actions:

- promoting forced single-event `ac0921_001` as complete;
- producing new clean-story or Bilibili uploads from contact sheets only;
- using numeric `ac` suffixes or sound-code numbers as direct CRI/OGG indices;
- merging gameplay UI, slot foregrounds, or gold-frame/particle effects into
  normal animation editions.
